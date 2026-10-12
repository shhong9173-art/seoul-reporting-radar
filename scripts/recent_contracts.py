"""Recent DART direct-beat contract event audit.

Lists are evidence that a report was filed, NOT independent evidence a
contract was won. Only parsed official source fields carry reported terms.
Correction changes require explicit original receipt and independent files.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime,timedelta,timezone
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlencode

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"scripts"))
from business_content import api_json
from dart_lineage import event_type,has_correction,review_lineage,zip_documents,tabular_fields

KST=timezone(timedelta(hours=9))
DIRECT=("현대자동차","기아","현대제철","세아제강",
        "HD현대일렉트릭","엘에스일렉트릭","효성중공업","두산에너빌리티",
        "고려아연","영풍","포스코","KG스틸","동국제강")
NUMBER=re.compile(r"\d{14}\Z")
CORP=re.compile(r"\d{8}\Z")
DAYS=21


def company_filings(key,company,code,start,end,fetch=api_json):
    if not key or not CORP.fullmatch(str(code)) or company not in DIRECT:
        raise ValueError("공식 조회 회사 코드가 직접 출입처와 일치하지 않음")
    if not (re.fullmatch(r"\d{8}",start) and re.fullmatch(r"\d{8}",end) and start<=end):
        raise ValueError("공시 기간 형식 오류")
    url="https://opendart.fss.or.kr/api/list.json?"+urlencode({
        "crtfc_key":key,"corp_code":code,"bgn_de":start,"end_de":end,
        "last_reprt_at":"N","page_no":1,"page_count":100})
    response=fetch(url)
    if not isinstance(response,dict):
        raise ValueError("공식 목록 응답 객체 아님")
    if response.get("status")=="013":
        return []
    if response.get("status")!="000":
        raise RuntimeError("OpenDART 조회 코드 "+str(response.get("status")))
    if int(response.get("total_page",1))>1:
        raise ValueError("공시 목록 페이지 2개 이상: 누락 방지를 위해 중단")
    items=[]
    for row in response.get("list",[]):
        if not isinstance(row,dict) or row.get("corp_code")!=code:
            continue
        receipt=str(row.get("rcept_no") or "")
        report=str(row.get("report_nm") or "")
        issued=str(row.get("rcept_dt") or "")
        category=event_type(report)
        if (not NUMBER.fullmatch(receipt) or not category
            or not re.fullmatch(r"20\d{6}",issued) or not start<=issued<=end):
            continue
        items.append({
            "company":company,"corpCode":code,"receiptNo":receipt,
            "published":issued,"report":report,"category":category,
            "isCorrection":has_correction(report),
            "sourceUrl":"https://dart.fss.or.kr/dsaf001/main.do?rcpNo="+receipt,
            "status":"official_list_verified",
            "evidenceStatus":"접수 회사·공시명·일자만 확인; 원문 조건은 별도 조회 필요",
        })
    return items


def document_evidence(item,key,documents=zip_documents,lineage=review_lineage):
    result=dict(item)
    if item["isCorrection"]:
        info=lineage({
            "company":item["company"],"receiptNo":item["receiptNo"],
            "report":item["report"]
        },{item["company"]:{"corp_code":item["corpCode"]}},api_key=key)
        original_ok=bool(info.get("originalDocumentVerified"))
        result.update({
            "status":"original_verified" if original_ok else "original_not_verified",
            "originalReceiptNo":info.get("originReceiptNo") if original_ok else None,
            "originalSourceUrl":info.get("originSourceUrl") if original_ok else None,
            "changes":info.get("changes",[]) if original_ok else [],
            "unverifiedSameDateCandidates":info.get("candidateOrigins",[])[:8],
            "evidenceStatus":info.get("reason","원공시 근거 미확인"),
            "sourceError":info.get("status")=="source_unavailable",
        })
    else:
        try:
            texts=documents(key,item["receiptNo"])
            fields=tabular_fields(texts)
            result.update({
                "status":"official_document_read",
                "observedFields":fields,
                "evidenceStatus":"공식 접수·공시 원문 발췌; 계약 체결/금액·상대방·효력은 원문과 기업 확인 필요",
            })
        except (ValueError,RuntimeError,URLError,TimeoutError,OSError) as exc:
            result.update({"status":"document_unavailable","sourceError":True,
                           "errorType":type(exc).__name__,
                           "evidenceStatus":"원문 읽기 실패: 공시 목록 정보만 확인"})
    result["scoopStatus"]="기보도 및 원자료·회사 답변 확인 전 · 단독 미확정"
    result["questions"]=[
        "원문 원계약·정정 전후 계약금액, 고객사, 적용 기간이 명시됐는가?",
        "해당 공급계약·투자에 관한 이전 DART 공시·기업 발표·전문지 보도가 있는가?",
        "공식 계약 확정과 입찰/협약/옵션 계약의 구분 및 실제 산업 영향은 무엇인가?",
    ]
    return result


def collect(codes,key,now=None,fetch=company_filings,detail=document_evidence,limit=9):
    now=now or datetime.now(KST)
    start=(now-timedelta(days=DAYS)).strftime("%Y%m%d")
    end=now.strftime("%Y%m%d")
    checks=[]
    rows=[]
    for company in DIRECT:
        obj=codes.get(company)
        corp=(obj or {}).get("corp_code") if isinstance(obj,dict) else None
        if not isinstance(corp,str) or not CORP.fullmatch(corp):
            checks.append({"company":company,"status":"corp_code_unavailable"})
            continue
        try:
            group=fetch(key,company,corp,start,end)
            rows.extend(group)
            checks.append({"company":company,"status":"checked",
                           "matchedContractEvents":len(group)})
        except (ValueError,RuntimeError,URLError,TimeoutError,OSError) as exc:
            checks.append({"company":company,"status":"source_error",
                           "errorType":type(exc).__name__})
    # Corrections first; only these can yield independently verified change.
    rows.sort(key=lambda x:(not x["isCorrection"],x["published"],x["receiptNo"]),
              reverse=False)
    corrections=[r for r in rows if r["isCorrection"]]
    new=[r for r in rows if not r["isCorrection"]]
    top=(sorted(corrections,key=lambda r:r["published"],reverse=True)+
         sorted(new,key=lambda r:r["published"],reverse=True))[:limit]
    details=[]
    for r in top:
        try:
            details.append(detail(r,key))
        except (ValueError,RuntimeError,URLError,TimeoutError,OSError) as exc:
            details.append({**r,"status":"source_error","errorType":type(exc).__name__,
                            "evidenceStatus":"원문 검증 실패","scoopStatus":"단독 미확정"})
    return {
        "generatedAt":now.isoformat(timespec="seconds"),
        "periodStart":start,"periodEnd":end,
        "source":"OpenDART 회사별 공시검색 list.json 및 조회된 경우 document.xml",
        "scope":"직접 출입처 13개사의 21일 내 공급계약·신규시설투자·생산중단·재개 공시",
        "sourceChecks":checks,"totalMatchingListEvents":len(rows),
        "inspectedDetails":len(details),"allEventsInspected":len(rows)<=limit,
        "items":details,"uninspectedListCount":max(0,len(rows)-len(details)),
        "confirmedOriginalComparisons":sum(x.get("status")=="original_verified" for x in details),
        "scoopConfirmed":0,
        "limitations":"DART 이외 비상장 해외법인 개별 계약 미포함. 같은 날짜·회사·비슷한 제목만으로 원계약 연결 금지",
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--codes",default="dart_corp_codes.json")
    ap.add_argument("--output",default="digests/recent_contracts_latest.json")
    ap.add_argument("--limit",type=int,default=9)
    args=ap.parse_args()
    if not 1<=args.limit<=15:
        ap.error("원문 검증 상한은 1~15건")
    key=os.getenv("DART_API_KEY","").strip()
    if not key:
        raise SystemExit("DART_API_KEY 미설정: 기존 공급계약 자료 보존")
    codes=json.loads(Path(args.codes).read_text(encoding="utf-8")).get("companies",{})
    result=collect(codes,key,limit=args.limit)
    checks=[x for x in result["sourceChecks"] if x["status"]=="checked"]
    if not checks:
        raise SystemExit("공식 DART 조회 성공 0개사: 기존 자료 보존")
    path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    temp.replace(path)
    print(f"DART 직접 출입처 공급/생산/투자 사건 {result['totalMatchingListEvents']}건, "
          f"원문·정정 조회 {result['inspectedDetails']}건, 원계약 교차확인 {result['confirmedOriginalComparisons']}건")


if __name__=="__main__":
    main()
