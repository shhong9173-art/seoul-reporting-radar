"""Conservative primary-document lineage for amended DART filings.

Only an explicit original *receipt number* in the official amended document,
confirmed independently by the issuer's DART list.json, authorizes original-vs-
amended comparisons. A matching date or title is only an investigation hint.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import time
import zipfile
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dart_numeric_extractor import decode_web_bytes, html_to_text
from dart_corrections import Tables, compare_correction

KST = timezone(timedelta(hours=9))
RECEIPT = re.compile(r"(?<!\d)\d{14}(?!\d)")
FIELDS = {
    "계약금액(원)": "contract_amount",
    "계약금액": "contract_amount",
    "확정계약금액(원)": "contract_amount",
    "계약상대": "counterparty",
    "계약상대방": "counterparty",
    "계약상대방명": "counterparty",
    "계약시작일": "contract_start",
    "계약종료일": "contract_end",
    "계약기간시작일": "contract_start",
    "계약기간종료일": "contract_end",
    "투자금액(원)": "investment_amount",
    "투자금액": "investment_amount",
    "투자금액총액(원)": "investment_amount",
    "생산재개예정일자": "production_restart",
    "생산재개예정일": "production_restart",
    "생산중단분야": "production_site",
    "사업명": "project",
    "계약명": "project",
}
MATERIAL = {"contract_amount","contract_start","contract_end","investment_amount","production_restart"}
IDENTITY = {"counterparty","production_site","project"}
ALLOWED_TERMS = ("단일판매", "공급계약", "신규시설투자", "생산중단", "생산재개")
ORIGINAL_LINK = re.compile(
    r"(?:원공시|최초\s*공시|정정대상\s*공시)\s*(?:접수번호|접수\s*번호|공시번호)"
    r"\s*[:：=\-]?\s*(\d{14})", re.I
)


def valid_receipt(s):
    return isinstance(s, str) and re.fullmatch(r"\d{14}", s) is not None


def normal(s):
    return re.sub(r"\s+", "", str(s or "")).strip()


def source_link(receipt):
    if not valid_receipt(receipt):
        raise ValueError("잘못된 DART 접수번호")
    return f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt}"


def event_type(report):
    value = normal(report).replace("[기재정정]", "").replace("[첨부정정]", "")
    for token in ALLOWED_TERMS:
        if token in value:
            return "공급계약" if token in ("단일판매", "공급계약") else token
    return None


def has_correction(report):
    return "정정" in report and event_type(report) is not None


def explicit_origin_id(documents, amended_receipt):
    """Read only an expressly labelled original receipt, never a date-derived guess."""
    matches = set()
    for text in documents:
        if not isinstance(text, str):
            continue
        plain = html_to_text(text.encode("utf-8"))
        for match in ORIGINAL_LINK.finditer(plain):
            if match[1] != amended_receipt:
                matches.add(match[1])
    if len(matches) == 1:
        return {"status": "explicit_reference", "receiptNo": next(iter(matches))}
    return {"status": "ambiguous_explicit_references" if matches else "no_explicit_reference",
            "receiptNo": None, "referencesSeen": sorted(matches)[:5]}


def tabular_fields(documents):
    """Strict, non-nested two-cell or paired-cell rows; duplicate conflict = unknown."""
    gathered = defaultdict(set)
    for document in documents:
        parser = Tables()
        try:
            parser.feed(document)
        except Exception:
            continue
        for table in parser.tables:
            if table["ambiguous"]:
                continue
            for row in table["rows"]:
                if any(span for _, span in row) or len(row) not in (2, 4):
                    continue
                cells = [str(s).strip() for s, _ in row]
                for label, value in zip(cells[0::2], cells[1::2]):
                    key = normal(label)
                    key = re.sub(r"^(?:\d+|[가-하])\.", "", key)
                    canonical = FIELDS.get(key)
                    if not canonical or not value or len(value) > 220:
                        continue
                    gathered[canonical].add(normal(value))
    # Conflicting duplicates are not silently reduced to the first value.
    return {key: next(iter(values)) for key,values in gathered.items() if len(values) == 1}


def comparable_differences(before, after):
    """Only verbatim, unambiguous field values. Never compute numeric deltas."""
    changes=[]
    for key in sorted(set(before) & set(after) & MATERIAL):
        b,a = before[key],after[key]
        if b != a and b not in ("-", "미정", "미기재") and a not in ("-", "미정", "미기재"):
            changes.append({"field":key,"before":b,"after":a,
                            "basis":"independent_primary_documents",
                            "numericDelta":None,"needsCompanyConfirmation":True})
        elif b != a:
            changes.append({"field":key,"before":b,"after":a,
                            "basis":"independent_primary_documents",
                            "numericDelta":None,"needsCompanyConfirmation":True,
                            "oneSideUnspecified":True})
    return changes


def issuer_list(api_key, corp_code, day, fetch_json):
    """Check receipt and issuing corporation in a date-scoped official list call."""
    if not re.fullmatch(r"\d{8}",day) or not re.fullmatch(r"\d{8}",corp_code):
        return []
    address = ("https://opendart.fss.or.kr/api/list.json?" +
               urlencode({"crtfc_key":api_key, "corp_code":corp_code, "bgn_de":day,
                          "end_de":day, "page_no":1,"page_count":100}))
    obj=fetch_json(address)
    if obj.get("status")=="013":
        return []
    if obj.get("status")!="000":
        raise ValueError("OpenDART 목록 오류 코드 "+str(obj.get("status")))
    if int(obj.get("total_page",1))>1:
        raise ValueError("동일 날짜 공시 목록이 여러 페이지여서 후보 전체를 확인하지 못함")
    return obj.get("list",[]) if isinstance(obj.get("list",[]),list) else []


def official_fetch_bytes(url):
    request=Request(url,headers={"User-Agent":"reporter-evidence-radar/1.0",
                                 "Accept":"application/zip,application/xml,*/*"})
    with urlopen(request,timeout=16) as resp:
        data=resp.read(8*1024*1024+1)
    if len(data)>8*1024*1024:
        raise ValueError("공식 자료 8MB 안전 한도 초과")
    return data


def zip_documents(api_key, receipt, fetch_bytes=official_fetch_bytes):
    if not valid_receipt(receipt):
        raise ValueError("올바르지 않은 접수번호")
    url=("https://opendart.fss.or.kr/api/document.xml?" +
         urlencode({"crtfc_key":api_key,"rcept_no":receipt}))
    response=fetch_bytes(url)
    if not zipfile.is_zipfile(io.BytesIO(response)):
        raise ValueError("OpenDART 문서 응답이 ZIP이 아님 (점검·권한·API 오류 가능)")
    docs=[]
    with zipfile.ZipFile(io.BytesIO(response)) as bundle:
        if len(bundle.infolist())>30:
            raise ValueError("문서 항목 수가 안전 상한을 초과")
        for info in bundle.infolist():
            if not info.filename.lower().endswith((".xml",".html",".htm")):
                continue
            if info.file_size>2*1024*1024:
                raise ValueError("원문 XML 파일 안전 한도 초과")
            docs.append(decode_web_bytes(bundle.read(info)))
            if len(docs)>=12:
                break
    if not docs:
        raise ValueError("OpenDART ZIP에서 읽을 수 있는 본문 없음")
    return docs


def reference_date(documents, source_url):
    dates=set()
    for doc in documents:
        result=compare_correction(doc,source_url)
        value=result.get("referencedFilingDate")
        if value:
            dates.add(value)
    return next(iter(dates)) if len(dates)==1 else None


def review_lineage(row, corp_codes, *, api_key, fetch_documents=zip_documents,
                   fetch_list=issuer_list):
    receipt=row.get("receiptNo")
    company=row.get("company")
    report=row.get("report","")
    answer={"receiptNo":receipt,"company":company,"report":report,
            "status":"not_applicable","originReceiptNo":None,
            "originalDocumentVerified":False, "changes":[],
            "candidateOrigins":[], "sourceUrl":source_link(receipt),
            "questions":[]}
    if not has_correction(report):
        return answer
    answer["status"]="original_unverified"
    corp=corp_codes.get(company)
    code=corp.get("corp_code") if isinstance(corp,dict) else None
    if not isinstance(code,str) or not re.fullmatch(r"\d{8}",code):
        answer["reason"]="출입처 기업의 DART 고유번호 미확인"
        return answer
    try:
        amendment=fetch_documents(api_key,receipt)
        origin=explicit_origin_id(amendment,receipt)
        anchor=reference_date(amendment,answer["sourceUrl"])
        answer["referencedFilingDate"]=anchor
        if origin["status"]!="explicit_reference":
            if anchor:
                day=anchor.replace("-","")
                options=fetch_list(api_key,code,day)
                answer["candidateOrigins"]=[
                    {"receiptNo":item["rcept_no"],"report":item.get("report_nm",""),
                     "date":item.get("rcept_dt"),
                     "url":source_link(item["rcept_no"]),
                     "status":"같은 날짜의 후보일 뿐 동일 사건 미검증"}
                    for item in options if valid_receipt(item.get("rcept_no")) and
                    item.get("rcept_no")!=receipt and event_type(item.get("report_nm",""))==event_type(report)
                ][:10]
            answer["reason"]="원문에서 원공시의 명시적 접수번호 확인 불가; 날짜·제목만으로 계약 연결 금지"
            return answer
        original_no=origin["receiptNo"]
        options=fetch_list(api_key,code,original_no[:8])
        matched=[item for item in options
                 if item.get("rcept_no")==original_no and
                 item.get("corp_code",code)==code and
                 event_type(item.get("report_nm",""))==event_type(report)]
        if len(matched)!=1:
            answer["reason"]="원공시 접수번호가 발행회사·동일 사건 유형의 공식 공시 목록에서 확인되지 않음"
            return answer
        original=fetch_documents(api_key,original_no)
        old,new=tabular_fields(original),tabular_fields(amendment)
        # If one of the identity fields appears in both, a mismatch is a hard stop.
        common_identity=set(old)&set(new)&IDENTITY
        if any(old[key]!=new[key] for key in common_identity):
            answer["status"]="identity_mismatch"
            answer["reason"]="원공시/정정공시의 상대방·사업장·사업명이 달라 동일 사건으로 인정하지 않음"
            return answer
        changes=comparable_differences(old,new)
        answer.update({"originReceiptNo":original_no,
                       "originSourceUrl":source_link(original_no),
                       "originalDocumentVerified":True,
                       "status":"original_verified_changes" if changes else "original_verified_no_comparable_change",
                       "changes":changes,
                       "evidenceFieldsBefore":old,
                       "evidenceFieldsAfter":new,
                       "reason":"원공시 번호·회사·공시유형·두 원문을 각각 확인. 일치하는 표 항목만 비교",
                       "questions":["변경 전후 값이 확정 조건인지 회사에 확인",
                                    "계약·투자·생산 일정 변경의 실제 발생·효력 시점 확인",
                                    "상대방·사업장과 기존 보도에 이미 공개된 내용인지 확인"]})
        return answer
    except Exception as exc:
        answer["status"]="source_unavailable"
        answer["reason"]="원문·공시 목록 조회 실패: "+type(exc).__name__
        return answer


def build_lineage(digest,numeric,corp_codes,api_key,fetch_documents=zip_documents,
                  fetch_list=issuer_list,limit=3):
    if not isinstance(digest,dict) or not isinstance(digest.get("items"),list):
        raise ValueError("아침 공시 digest가 유효하지 않음")
    candidates=[r for r in digest["items"] if isinstance(r,dict) and
                valid_receipt(r.get("receiptNo")) and has_correction(r.get("report",""))]
    recent=candidates[:limit]
    outcomes=[review_lineage(r,corp_codes,api_key=api_key,fetch_documents=fetch_documents,
                             fetch_list=fetch_list) for r in recent]
    return {"generatedAt":datetime.now(KST).isoformat(timespec="seconds"),
            "digestGeneratedAt":digest.get("generatedAt"),
            "scope":"명시적 원공시 접수번호에 한해 독립 검증. 후보 매칭은 미확정",
            "correctionCount":len(candidates),"processedCount":len(outcomes),
            "collectionComplete":len(candidates)<=limit,
            "status":"checked" if candidates else "no_relevant_corrections",
            "items":outcomes}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--digest",default="digests/latest.json")
    p.add_argument("--corp-codes",default="dart_corp_codes.json")
    p.add_argument("--output",default="digests/lineage_latest.json")
    p.add_argument("--limit",type=int,default=3)
    args=p.parse_args()
    if not 1<=args.limit<=5:
        p.error("--limit must be between 1 and 5")
    digest=json.loads(Path(args.digest).read_text(encoding="utf-8"))
    path=Path(args.corp_codes)
    codes=json.loads(path.read_text(encoding="utf-8")).get("companies",{}) if path.exists() else {}
    key=os.environ.get("DART_API_KEY","").strip()
    result=build_lineage(digest,{},codes,key,limit=args.limit)
    dest=Path(args.output)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("원공시 독립 대조:", result["status"], "관련 정정 공시",result["correctionCount"],
          "건 / 검사",result["processedCount"],"건")


if __name__=="__main__":
    main()
