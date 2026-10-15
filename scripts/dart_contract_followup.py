"""Conservative DART contract change/press-index review, independent of KIPRIS.

Exact DART receipt, same-issuer original reference and separately retrieved
official documents are required for an amended-vs-original comparison.
Google News RSS hits are discovery results, NOT verified prior coverage of the
same contract, and zero results NEVER proves an unpublished exclusive.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

from dart_lineage import MATERIAL, source_link, valid_receipt
from official_event_triage import dart_receipt_link

KST=timezone(timedelta(hours=9))
FIELD_NAMES={
 "contract_amount":"계약금액",
 "contract_start":"계약 시작일",
 "contract_end":"계약 종료일",
 "investment_amount":"시설투자금액",
 "production_restart":"생산재개 예정일",
 "counterparty":"계약 상대방",
 "project":"계약·사업명",
 "production_site":"사업장/중단 분야",
}
CATS=("공급계약","신규시설투자","생산중단","생산재개")
MAX_RSS_BYTES=450000


def from_rss(url):
    req=Request(url,headers={"User-Agent":"industry-dart-press-evidence/1.0",
                             "Accept":"application/rss+xml,application/xml"})
    with urlopen(req,timeout=9) as reply:
        return reply.read(MAX_RSS_BYTES+1)


def queries_for(item):
    """Exact DART receipt and company/category phrasing: 2 limited queries."""
    company=str(item["company"]).strip()
    name=company.replace("엘에스일렉트릭","LS일렉트릭").replace("HD현대일렉트릭","HD현대일렉트릭")
    category=str(item.get("category") or "공시")
    words={
      "공급계약":"공급계약",
      "신규시설투자":"시설투자",
      "생산중단":"생산중단",
      "생산재개":"생산재개"
    }
    r=str(item["receiptNo"])
    return ['"'+r+'"', '"'+name[:32]+'" "'+words.get(category,"공시")+'"']


def rss_index(query, *,fetch=from_rss,now=None):
    """Never claim that a broad result actually reports this DART event."""
    now=now or datetime.now(KST)
    address="https://news.google.com/rss/search?q="+quote(query,safe="")+"&hl=ko&gl=KR&ceid=KR:ko"
    try:
        raw=fetch(address)
        if not isinstance(raw,(bytes,bytearray)) or len(raw)>MAX_RSS_BYTES:
            raise ValueError("invalid RSS bytes")
        if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
            raise ValueError("DTD blocked")
        root=ET.fromstring(raw)
        if root.tag!="rss" or root.find("channel") is None:
            raise ValueError("invalid RSS document")
        stories=[]
        for row in root.findall("./channel/item")[:12]:
            headline=" ".join(str(row.findtext("title") or "").split())[:200]
            uri=str(row.findtext("link") or "").strip()
            if not (headline and uri.startswith("https://news.google.com/") and len(uri)<750):
                continue
            pubtext=str(row.findtext("pubDate") or "").strip()
            published=None
            try:
                dt=parsedate_to_datetime(pubtext)
                if dt.tzinfo and dt<=now+timedelta(minutes=10):
                    published=dt.astimezone(KST).isoformat(timespec="seconds")
            except (ValueError,TypeError,OverflowError):
                pass
            stories.append({"title":headline,"url":uri,"publishedAt":published,
                            "indexResultNotVerifiedSameEvent":True})
            if len(stories)>=3:break
        return {"query":query,"status":"hits" if stories else "no_index_hits",
                "articles":stories,"errorType":None}
    except (ET.ParseError,OSError,TimeoutError,ValueError,TypeError) as exc:
        return {"query":query,"status":"lookup_error","articles":[],
                "errorType":type(exc).__name__}


def safe_document(item):
    receipt=item.get("receiptNo")
    return (valid_receipt(receipt)
        and dart_receipt_link(receipt,item.get("sourceUrl"))
        and item.get("company") and item.get("category") in CATS
        and item.get("published")==receipt[:8])


def verified_changes(item):
    """Require explicit original receipt and independent source-verified changes."""
    if not item.get("isCorrection"):
        return "not_a_correction",[],None
    if (item.get("status")!="original_verified"
        or not valid_receipt(item.get("originalReceiptNo"))
        or not dart_receipt_link(item.get("originalReceiptNo"),item.get("originalSourceUrl"))
        or item["originalReceiptNo"]==item["receiptNo"]):
        return "original_unverified_no_comparison",[],None
    before=item["originalReceiptNo"]
    payload=item.get("changes")
    if not isinstance(payload,list):
        return "invalid_independent_comparison",[],None
    approved=[]
    for change in payload:
        if not isinstance(change,dict) or change.get("field") not in MATERIAL:
            continue
        if (change.get("basis")!="independent_primary_documents"
            or change.get("needsCompanyConfirmation") is not True):
            return "invalid_independent_comparison",[],None
        a,b=change.get("before"),change.get("after")
        if any(not isinstance(x,str) or not x or len(x)>220 for x in (a,b)):
            return "invalid_independent_comparison",[],None
        if a!=b:
            approved.append({
              "field":change["field"],"fieldLabel":FIELD_NAMES[change["field"]],
              "before":a,"after":b,"basis":"independent_primary_documents",
              "sourceBefore":source_link(before),"sourceAfter":item["sourceUrl"],
              "businessImpactVerified":False,"sameContractVerifiedByOfficialReceipts":True,
              "numericDifference":None,
              "oneSideUnspecified":change.get("oneSideUnspecified") is True
            })
    return ("original_verified_changes_needs_reporting" if approved
            else "original_verified_no_comparable_material_change"),approved,before


def review_one(item,*,rss_fetch=from_rss,now=None,search=True):
    now=now or datetime.now(KST)
    if not isinstance(item,dict) or not safe_document(item):
        raise ValueError("unverified_dart_receipt_or_identity")
    receipt=item["receiptNo"]
    label=item["company"]+" · "+str(item.get("report") or item["category"]).strip()[:110]
    comparison, changes, original=verified_changes(item)
    current={}
    fields=item.get("observedFields")
    if not item.get("isCorrection") and item.get("status")=="official_document_read" and isinstance(fields,dict):
        for k,v in fields.items():
            if k in FIELD_NAMES and isinstance(v,str) and 0<len(v)<=220:
                current[k]=v
    qs=queries_for(item)
    results=[rss_index(q,fetch=rss_fetch,now=now) if search else
             {"query":q,"status":"not_searched","articles":[],"errorType":None}
             for q in qs]
    failed=any(p["status"]=="lookup_error" for p in results)
    hits=any(p["status"]=="hits" for p in results)
    press=("press_index_partial_failure" if failed else
           "indexed_possible_articles_require_fulltext" if hits else
           "index_no_hits_not_proof_unreported" if search else
           "press_not_searched")
    # Only a strict number query is strong enough to warrant an exact-receipt
    # *index lead*, still not primary confirmation that the article matches.
    precise=results[0].get("status")=="hits"
    indexed=sum(len(x["articles"]) for x in results)
    suspected_pre_filing=0
    for group in results:
        for a in group["articles"]:
            try:
                dt=datetime.fromisoformat(a["publishedAt"])
            except (ValueError,TypeError):
                continue
            # Publication timestamps on the same filing day may be after filing.
            # These are potential follow-ups only, not established earlier news.
            if dt.date()<=datetime.strptime(item["published"],"%Y%m%d").date():
                suspected_pre_filing+=1
    outstanding=["기보도 전문 원문과 동일 계약 여부 확인","공시 계약 상대방·금액·기간·실제 효력 별도 검증",
                 "해당 출입처 사업부·납품 물량·매출 영향 직접 답변"]
    if item.get("isCorrection") and original is None:
        outstanding.insert(0,"원공시 접수번호가 정정문에 명시됐는지 추가 확인(동일 날짜 추정 연결 금지)")
    elif changes:
        outstanding.insert(0,"변경 전후 공시 값의 계약상 효력·실제 물량 변경 여부 확인")
    elif not current:
        outstanding.insert(0,"공시 표 필드 자동 추출 불가: DART 원문 직접 확인")
    return {
      "id":"DART:"+receipt,"company":item["company"],"receiptNo":receipt,
      "published":item["published"],"category":item["category"],"headline":label,
      "officialSourceUrl":item["sourceUrl"],
      "officialSourceStatus":item.get("status"),
      "isCorrection":item.get("isCorrection") is True,
      "originalReceiptNo":original,
      "originalSourceUrl":source_link(original) if original else None,
      "comparisonStatus":comparison,"materialFieldChanges":changes,
      "unambiguousCurrentDocumentFields":current,
      "fieldValuesAreIssuerTextNotIndependentCommercialProof":True,
      "pressIndexStatus":press,
      "pressSearchCompleted":search and not failed,
      "pressSearchQueries":results,
      "indexedArticleCount":indexed,
      "possiblePreOrSameFilingDayIndexedCount":suspected_pre_filing,
      "exactReceiptNumberIndexLead":precise,
      "priorCoverageOfSameContractVerified":False,
      "companyImpactVerified":False,"actualShipmentChangeVerified":False,
      "exclusiveConfirmed":False,"approvedForPitch":False,
      "nextChecks":outstanding,
      "warnings":"공개 공시/뉴스 RSS 색인 참고자료. 검색 미발견=미보도 증거 아님. 원공시 번호 확인 전 변경 확정 금지."
    }


def build(source,*,now=None,fetch=from_rss,search=True,max_events=9):
    now=now or datetime.now(KST)
    if not isinstance(source,dict) or not isinstance(source.get("items"),list):
        raise ValueError("missing_dart_ledger")
    if not isinstance(source.get("sourceChecks"),list):
        raise ValueError("missing_issuer_coverage")
    if not 1<=max_events<=15:raise ValueError("invalid_review_limit")
    read=source.get("generatedAt")
    try:
        t=datetime.fromisoformat(read)
        if not t.utcoffset():raise ValueError()
    except (TypeError,ValueError):
        raise ValueError("missing_or_untimed_official_source") from None
    if t>now+timedelta(minutes=10):raise ValueError("future_source_time")
    known={}
    for item in source["items"][:max_events]:
        if not isinstance(item,dict) or not safe_document(item):
            raise ValueError("unsafe_filing_identity")
        receipt=item["receiptNo"]
        if receipt in known:
            raise ValueError("duplicate_receipt")
        known[receipt]=item
    # Multi-worker network IO; each RSS failure remains an explicit partial
    # source error, never a silently omitted or "0 earlier reports" response.
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(review_one,v,rss_fetch=fetch,now=now,search=search)
                 for v in known.values()]
        records=[f.result() for f in futures]
    issues=sum(1 for r in records if not r["pressSearchCompleted"])
    pending=sum(1 for r in records if r["comparisonStatus"]=="original_unverified_no_comparison")
    verified=sum(len(r["materialFieldChanges"]) for r in records)
    return {
      "generatedAt":now.isoformat(timespec="seconds"),
      "dartSourceGeneratedAt":read,
      "status":"reporter_review_not_exclusive",
      "sourceItemCount":len(source["items"]),
      "sourceCompanyChecks":len(source["sourceChecks"]),
      "uninspectedDartListCount":source.get("uninspectedListCount"),
      "reviewedEvents":len(records),
      "reviewLimit":max_events,
      "unreviewedDartItems":len(source["items"])-len(records),
      "mediaLookupFailedEvents":issues,
      "correctionsWithoutVerifiedOriginal":pending,
      "independentlyComparedMaterialFields":verified,
      "confirmedScoops":0,"approvedArticles":0,
      "warning":"언론 기사 검색 결과가 없는 것은 미보도 증명 아님. 정정공시 원번호/원문 독립 확인 없는 변경은 표시하지 않음. 기업 계약·실제 물량 영향은 직접 취재 필요.",
      "items":records
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",default="digests/recent_contracts_latest.json")
    p.add_argument("--output",default="digests/dart_contract_followup_latest.json")
    p.add_argument("--limit",type=int,default=9)
    p.add_argument("--no-press-network",action="store_true")
    args=p.parse_args()
    doc=json.loads(Path(args.source).read_text(encoding="utf-8"))
    out=build(doc,max_events=args.limit,search=not args.no_press_network)
    target=Path(args.output);target.parent.mkdir(parents=True,exist_ok=True)
    tmp=target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    tmp.replace(target)
    print("Contract followup: DART",out["reviewedEvents"],
          "material independently compared",out["independentlyComparedMaterialFields"],
          "original not verified",out["correctionsWithoutVerifiedOriginal"],
          "news index error events",out["mediaLookupFailedEvents"],"scoops 0")


if __name__=="__main__":main()
