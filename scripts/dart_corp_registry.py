"""Safely resolve missing newsroom beat DART corporation codes from corpCode.xml.

The official endpoint supplies a ZIP containing official corp_code and
corp_name entries. Match only unique exact legal names after stripping
legal-corporation wrappers; avoid approximate or semantic company matching.
Existing mappings are preserved, including if the official registry
disagrees (manual review required).
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import zipfile
from collections import defaultdict
from datetime import datetime,timedelta,timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request,urlopen
import xml.etree.ElementTree as ET

from dart_beat_monitor import TARGETS

KST=timezone(timedelta(hours=9))
CODE=re.compile(r"^\d{8}$")
# Only exact known Korean legal-style aliases, no fuzzy matching.
ALIASES={
  "한국GM":("한국지엠",),
  "KG스틸":("케이지스틸",),
  "KG모빌리티":("케이지모빌리티",),
  "LS전선":("엘에스전선",),
  "LS MnM":("엘에스엠앤엠",),
  "LS":("엘에스",),
  "동국씨엠":("동국씨엠",),
  "포스코홀딩스":("포스코홀딩스","POSCO홀딩스"),
  "OCI":("오씨아이",),
  "S-Oil":("S-Oil","에쓰-오일","에쓰오일"),
  "HD현대오일뱅크":("에이치디현대오일뱅크","현대오일뱅크"),
}
MAX_RESPONSE=8_000_000
MAX_XML=70_000_000
MAX_COMPANIES=175000
# Independent listed stock identity supplied by the official DART corpCode.xml.
# Unlike a name alias, an exact six-digit listed ticker can distinguish two
# records bearing the same cleaned Korean name. Never use a third-party stock
# value as a corporation ID: verify the code *inside the official ZIP*.
STOCK_IDENTITY={"KG스틸":"016380"}
STOCK_KEY_PREFIX="__official_listed_stock__:"


def issuer_name(value):
    if not isinstance(value,str):return ""
    s="".join(value.strip().split())
    s=re.sub(r"^(?:\(주\)|㈜|주식회사)","",s)
    s=re.sub(r"(?:\(주\)|㈜|주식회사)$","",s)
    return s.casefold()


def official_bytes(key):
    addr="https://opendart.fss.or.kr/api/corpCode.xml?"+urlencode({"crtfc_key":key})
    request=Request(addr,headers={"User-Agent":"newsroom-dart-beat-corp-ids/1.0",
                                  "Accept":"application/zip,*/*"})
    with urlopen(request,timeout=35) as r:
        payload=r.read(MAX_RESPONSE+1)
    if len(payload)>MAX_RESPONSE:raise ValueError("official_registry_zip_too_large")
    return payload


def official_index(payload,names=TARGETS):
    if not isinstance(payload,(bytes,bytearray)) or not zipfile.is_zipfile(io.BytesIO(payload)):
        raise ValueError("not_official_registry_zip")
    expected=set()
    for name in names:
        expected.add(issuer_name(name))
        for alias in ALIASES.get(name,()):
            expected.add(issuer_name(alias))
    found=defaultdict(set)
    count=0
    with zipfile.ZipFile(io.BytesIO(payload)) as bundle:
        members=[m for m in bundle.infolist() if m.filename.upper().endswith(".XML")
                 and not m.is_dir()]
        if len(members)!=1 or members[0].file_size>MAX_XML:
            raise ValueError("unexpected_registry_xml_layout")
        with bundle.open(members[0]) as stream:
            # ElementTree does not resolve external XML references.
            for evt,el in ET.iterparse(stream,events=("end",)):
                if el.tag!="list":continue
                count+=1
                if count>MAX_COMPANIES:raise ValueError("unexpected_registry_company_count")
                name=issuer_name(el.findtext("corp_name") or "")
                code=(el.findtext("corp_code") or "").strip()
                if name in expected and CODE.fullmatch(code):
                    found[name].add(code)
                    # The same official XML row MUST prove both legal name
                    # and 6-digit ticker, so an unrelated company with a
                    # coincidental ticker is never silently connected.
                    listed=(el.findtext("stock_code") or "").strip()
                    for target,ticker in STOCK_IDENTITY.items():
                        accepted={issuer_name(target)} | {
                            issuer_name(a) for a in ALIASES.get(target,())}
                        if name in accepted and listed==ticker:
                            found[STOCK_KEY_PREFIX+target+":"+ticker].add(code)
                el.clear()
    if count<1000:raise ValueError("incomplete_registry")
    return found,count


def resolve(codes,official,*,now=None,registry_count=0):
    now=now or datetime.now(KST)
    if not isinstance(codes,dict):raise ValueError("invalid_existing_code_map")
    new=dict(codes)
    lines=[]
    for name,group in TARGETS.items():
        old=codes.get(name)
        oldcode=old.get("corp_code") if isinstance(old,dict) else None
        keys={issuer_name(name)}|{issuer_name(x) for x in ALIASES.get(name,())}
        hits=set().union(*(official.get(k,set()) for k in keys))
        ticker=STOCK_IDENTITY.get(name)
        ticker_hits=(official.get(STOCK_KEY_PREFIX+name+":"+ticker,set())
                     if ticker else set())
        ticker_hits=set(ticker_hits)&hits
        if oldcode is not None and CODE.fullmatch(str(oldcode)):
            # Name aliases may refer to MULTIPLE real registered companies.
            # If the already-verified code is one of the matching official
            # IDs, do not falsely flag it as a mismatch just because another
            # unrelated entity has a similar legal company name.
            state=("existing_code_verified_in_official_registry" if oldcode in hits
                   else "already_known_registry_name_not_matched" if not hits
                   else "existing_code_official_name_mismatch_manual_review")
            final=oldcode
        elif len(hits)==1:
            final=next(iter(hits))
            new[name]={"corp_code":final,"stock_code":ticker if final in ticker_hits else ""}
            state="resolved_unique_official_legal_name"
        elif len(hits)>1 and len(ticker_hits)==1:
            # Requires BOTH exact legal name and exact official ticker.
            final=next(iter(ticker_hits))
            new[name]={"corp_code":final,"stock_code":ticker}
            state="resolved_unique_official_stock_and_legal_name"
        else:
            final=None
            state=("ambiguous_official_legal_name" if hits else
                   "no_exact_official_legal_name_match")
        lines.append({
            "company":name,"beat":group,"status":state,
            "corpCode":final,
            "officialMatchCount":len(hits),
            "officialListedStockCodeProof":(
                ticker if ticker and final is not None and final in ticker_hits else None)
        })
    return new,{
       "generatedAt":now.isoformat(timespec="seconds"),
       "status":"official_corp_code_registry_checked",
       "officialCompanyEntriesExamined":registry_count,
       "scope":len(TARGETS),
       "knownWithCode":sum(x["corpCode"] is not None for x in lines),
       "newUniqueCodesAdded":sum(x["status"] in (
            "resolved_unique_official_legal_name",
            "resolved_unique_official_stock_and_legal_name") for x in lines),
       "stillMissingCode":sum(x["corpCode"] is None for x in lines),
       "listedTickerNameAmbiguitiesResolved":sum(
            x["status"]=="resolved_unique_official_stock_and_legal_name" for x in lines),
       "manualConflicts":sum(x["status"] in (
           "ambiguous_official_legal_name",
           "existing_code_official_name_mismatch_manual_review") for x in lines),
       "companies":lines,
       "warning":"Exact official corporate registry names and name-matched listed stock identifiers only. No fuzzy alias matching and no evidence that a legally registered company files all contract information via DART. Existing IDs on official name mismatch are retained but require manual reconciliation."
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--codes",default="dart_corp_codes.json")
    p.add_argument("--coverage",default="digests/dart_corp_code_coverage_latest.json")
    a=p.parse_args()
    key=os.getenv("DART_API_KEY","").strip()
    if not key:raise SystemExit("DART_API_KEY missing: preserve official ID mapping")
    path=Path(a.codes)
    data=json.loads(path.read_text(encoding="utf-8"))
    codes=data.get("companies",{})
    registry,count=official_index(official_bytes(key))
    updated,coverage=resolve(codes,registry,registry_count=count)
    dest=Path(a.coverage);dest.parent.mkdir(parents=True,exist_ok=True)
    temp=dest.with_suffix(".tmp")
    temp.write_text(json.dumps(coverage,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    temp.replace(dest)
    if updated!=codes:
        data["companies"]=updated
        data["updatedAt"]=datetime.now(KST).isoformat(timespec="seconds")
        temp=path.with_suffix(".tmp")
        temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        temp.replace(path)
    print("Official DART issuer IDs:",coverage["scope"],"beat companies",
          coverage["knownWithCode"],"coded",coverage["newUniqueCodesAdded"],
          "new exact official IDs",coverage["stillMissingCode"],"not mapped",
          coverage["manualConflicts"],"conflicts")

if __name__=="__main__":main()
