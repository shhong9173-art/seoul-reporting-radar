"""NHTSA ODI *investigations* (not merely manufacturer recall headlines).

Source: https://static.nhtsa.gov/odi/ffdd/inv/FLAT_INV.zip and its INV.txt
metadata. All records are tab-delimited. Opened investigations are not
established safety defects; investigative records can cover multiple models.
"""
from __future__ import annotations
import csv
import io
import json
import re
import zipfile
from datetime import datetime,timedelta,timezone
from pathlib import Path
from urllib.request import urlopen,Request

KST=timezone(timedelta(hours=9))
SOURCE="https://static.nhtsa.gov/odi/ffdd/inv/FLAT_INV.zip"
DOCS="https://www.nhtsa.gov/nhtsa-datasets-and-apis"
# Long, unambiguous identifiers. 'GM' by itself could name many unrelated entities.
MAKES={"HYUNDAI":"현대차","KIA":"기아","GENESIS":"현대차(제네시스)",
       "CHEVROLET":"한국GM 관련 가능성(미국 GM)","BUICK":"한국GM 관련 가능성(미국 GM)",
       "BMW":"BMW코리아 관련(미국 판매차)","AUDI":"아우디코리아 관련(미국 판매차)",
       "VOLKSWAGEN":"폭스바겐코리아 관련(미국 판매차)",
       "MERCEDES-BENZ":"벤츠코리아 관련(미국 판매차)",
       "HONDA":"혼다코리아 관련(미국 판매차)",
       "RENAULT":"르노코리아 연관 별도 확인"}
FIELDS=("actionNumber","make","model","modelYear","component","manufacturer",
        "openedDate","closedDate","recallCampaign","subject","summary")
DATE=re.compile(r"^(?:19|20)\d{6}$")
ACTION=re.compile(r"^[A-Z0-9-]{3,14}$")


def direct_make(make,manufacturer):
    tokens=re.findall(r"[A-Z0-9]+(?:-[A-Z0-9]+)*",str(make or "").upper())
    company=str(manufacturer or "").upper()
    # NHTSA MAKE field usually names primary manufacturer / marque. No alias
    # derived from a generic 'KIA' inside another word such as 'NOKIAN'.
    for key,label in MAKES.items():
        if key in tokens or (key in ("HYUNDAI","KIA") and
                             re.search(r"(?<![A-Z])"+key+r"(?![A-Z])",company)):
            return label
    return None


def parse_tab_data(content,now=None,lookback=100):
    now=now or datetime.now(KST)
    if not 1<=lookback<=365:raise ValueError("1..365 days only")
    if len(content)>120_000_000:raise ValueError("NHTSA uncompressed investigation file too large")
    decoded=content.decode("utf-8-sig",errors="replace")
    start=(now-timedelta(days=lookback)).strftime("%Y%m%d")
    end=now.strftime("%Y%m%d")
    leads={}
    inspected=0
    for row in csv.reader(io.StringIO(decoded),delimiter="\t"):
        if not row or len(row)!=11:continue
        inspected+=1
        obj=dict(zip(FIELDS,(str(x or "").strip() for x in row)))
        action=obj["actionNumber"]
        opened=obj["openedDate"]
        if not ACTION.fullmatch(action) or not DATE.fullmatch(opened):
            continue
        if not start<=opened<=end:continue
        owner=direct_make(obj["make"],obj["manufacturer"])
        if not owner:continue
        obj["coveredIssuerRelation"]=owner
        obj["sourceUrl"]=DOCS
        obj["sourceDataset"]=SOURCE
        obj["recallLinked"]=bool(obj["recallCampaign"])
        obj["summary"]=obj["summary"][:900]
        obj["discoveryType"]="official_us_investigation_opened"
        obj["caution"]="미국 NHTSA 조사 개시. 결함 확정·국내 판매 모델 동일성·국내 리콜/단독 아님"
        leads.setdefault(action,obj)
    return {"scannedRecords":inspected,"items":sorted(leads.values(),
                    key=lambda z:(z["openedDate"],z["actionNumber"]),reverse=True)}


def recent_changes(current,previous):
    old={x.get("actionNumber"):x for x in (previous or {}).get("items",[])}
    for x in current["items"]:
        before=old.get(x["actionNumber"])
        x["firstSeenInRadar"]=before.get("firstSeenInRadar") if before else current["generatedAt"]
        x["observationState"]="first_observed_in_this_radar" if before is None else "previously_observed"
        # First observed is NOT first published nor scoop. Keep source date.
    current["newlyObserved"]=sum(x["observationState"]=="first_observed_in_this_radar"
                                  for x in current["items"])
    return current


def fetch_zip(url=SOURCE):
    req=Request(url,headers={"User-Agent":"seoul-reporting-radar NHTSA public records/1.0"})
    with urlopen(req,timeout=35) as r:
        raw=r.read(12_000_001)
    if len(raw)>12_000_000:raise ValueError("NHTSA official compressed dataset larger than expected")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        names=[n for n in z.namelist() if n.lower().endswith((".txt",".lst"))]
        if len(names)!=1:raise ValueError("NHTSA ZIP expected one tab data text file")
        info=z.getinfo(names[0])
        if info.file_size>120_000_000:raise ValueError("NHTSA decompressed file too large")
        return z.read(info)


def write_health(data,output=Path("digests/nhtsa_source_status_latest.json")):
    output.parent.mkdir(parents=True,exist_ok=True)
    temp=output.with_suffix(".json.tmp")
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    temp.replace(output)


def main():
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--out",default="digests/nhtsa_investigations_latest.json")
    p.add_argument("--lookback",type=int,default=100)
    a=p.parse_args()
    out=Path(a.out)
    previous={}
    if out.is_file():
        try:previous=json.loads(out.read_text(encoding="utf-8"))
        except (OSError,ValueError):pass
    now=datetime.now(KST)
    try:
        downloaded=fetch_zip()
        result=parse_tab_data(downloaded,now=now,lookback=a.lookback)
        if result["scannedRecords"]<200:
            raise ValueError("NHTSA investigations original file was incomplete")
        status={"generatedAt":now.isoformat(timespec="seconds"),"status":"checked",
                "scannedRecords":result["scannedRecords"],"candidateCount":len(result["items"]),
                "sourceUrl":SOURCE}
    except (OSError,ValueError,TimeoutError,zipfile.BadZipFile) as err:
        status={"generatedAt":now.isoformat(timespec="seconds"),"status":"source_error",
                "errorType":type(err).__name__,"sourceUrl":SOURCE,
                "warning":"NHTSA 공식원천 다운로드/파싱 불완전, 이전 정상자료 보존"}
        write_health(status)
        raise SystemExit("NHTSA official source failed: "+type(err).__name__) from None
    write_health(status)
    result.update({"generatedAt":now.isoformat(timespec="seconds"),"sourceUrl":SOURCE,
                   "scope":"US ODI formal opened investigations among matched marques, not recalls or complaint allegation totals",
                   "lookbackDays":a.lookback,
                   "confirmedScoops":0,"domesticModelApplicabilityVerified":False})
    recent_changes(result,previous)
    # Empty for matched makes may be correct, but successful official scan is
    # required; neither failed download nor silent schema change means zero.
    out.parent.mkdir(parents=True,exist_ok=True)
    temp=out.with_suffix(".json.tmp")
    temp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    temp.replace(out)
    print("NHTSA investigations parsed",result["scannedRecords"],
          "matching opened",len(result["items"]),"newly observed",result["newlyObserved"])


if __name__=="__main__":main()
