"""Official event-time reporting queue independent of the KIPRIS API.

Key distinction: a dataset collected today can contain August filings,
January NHTSA recalls, or September trade figures. Only the document's own
official publication/receipt date may make a lead "recent". Never certify
scoops, awards, contract terms, project completion, or company impact.

Retains a limited public-history marker to distinguish a newly OBSERVED public
filing from an actually unpublished event. The first run is a baseline.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
from urllib.parse import urlsplit,parse_qs

KST=timezone(timedelta(hours=9))
RECEIPT=re.compile(r"^20\d{12}$")
NOTICE=re.compile(r"^[A-Za-z0-9-]{4,45}$")
REQUIRED=("recent_contracts","overseas_official","investigation_hunt",
          "recent_metric_changes","nhtsa_official")
NO_AUTO_SCOOP="공개 원문 확인 후 기보도·해당 회사 실제 영향·직접 답변 검증 필요. 단독 미확정."

def parsed_date(s):
    if not isinstance(s,str):return None
    try:
        if re.fullmatch(r"20\d{6}",s):
            return datetime.strptime(s,"%Y%m%d").date()
        if re.fullmatch(r"20\d{2}-\d{2}-\d{2}",s):
            return date.fromisoformat(s)
        if re.fullmatch(r"\d{2}/\d{2}/20\d{2}",s):
            return datetime.strptime(s,"%d/%m/%Y").date()
    except ValueError:
        return None
    return None

def parsed_time(s):
    try:
        t=datetime.fromisoformat(str(s))
        return t if t.utcoffset() is not None else None
    except (ValueError,TypeError):
        return None

def official_link(value,host):
    if not isinstance(value,str) or len(value)>380:return False
    try:
        u=urlsplit(value)
        return u.scheme=="https" and u.hostname==host and not u.username and not u.password
    except ValueError:
        return False

def dart_receipt_link(receipt,link):
    if not isinstance(receipt,str) or not RECEIPT.fullmatch(receipt):
        return False
    if not official_link(link,"dart.fss.or.kr"):return False
    return receipt in parse_qs(urlsplit(link).query).get("rcpNo",[])

def source_health(label, data, collection, now, required_check=None):
    if not isinstance(data,dict):data={}
    timestamp=parsed_time(data.get("generatedAt"))
    rows=data.get(collection)
    checks=data.get(required_check,[]) if required_check else []
    if not isinstance(checks,list):checks=[]
    valid=bool(timestamp is not None and isinstance(rows,list))
    errored=sum(x.get("status")=="source_error" for x in checks if isinstance(x,dict))
    inspected=sum(x.get("status")=="checked" for x in checks if isinstance(x,dict))
    future=timestamp is not None and timestamp>now+timedelta(minutes=10)
    age=((now-timestamp).total_seconds()/3600) if timestamp else None
    if not valid:status="source_missing_or_malformed"
    elif future:status="source_time_invalid"
    elif errored:status="partial_collection"
    elif age is not None and age>24:status="snapshot_older_than_24h"
    else:status="checked_source"
    return dict(name=label,status=status,sourceAt=data.get("generatedAt") if valid else None,
                sourceAgeHours=round(age,1) if age is not None else None,
                records=len(rows) if isinstance(rows,list) else None,
                checkedQueries=inspected if required_check else None,
                failedQueries=errored if required_check else None,
                scopeWarning="snapshot timestamp is not the filing or event date")

def event(kind,identifier,when,headline,company,fact,url,verification):
    if not isinstance(headline,str) or not headline.strip():
        return None
    return {
       "id":kind+":"+identifier,"source":kind,
       "officialDate":when.isoformat(),"headline":headline.strip()[:260],
       "company":company if company else None,
       "officialFact":fact[:500],
       "sourceUrl":url,
       "verification":verification,
       "classification":"public_official_document_not_a_scoop",
       "companyImpactVerified":False,"contractTermsVerified":False,
       "priorMediaCoverageVerified":False,"exclusiveConfirmed":False,
       "approvedForPitch":False
    }

def build(sources,*,now=None,previous=None):
    now=now or datetime.now(KST)
    if now.tzinfo is None:raise ValueError("timezone_required")
    now=now.astimezone(KST)
    if not isinstance(sources,dict):raise ValueError("source_mapping_required")
    previous=previous if isinstance(previous,dict) else {}
    seen=previous.get("seen",{}) if isinstance(previous.get("seen"),dict) else {}
    initialized=previous.get("status")=="official_date_triage" and bool(seen)
    today=now.date()
    start=today-timedelta(days=2)
    status=[]
    event_rows=[]
    skipped={"correction_without_original":0,"unverified_foreign_search_hit":0,
             "source_without_official_identity":0,"duplicate_event_id":0}
    datasets={}
    keys={
        "recent_contracts":("items","sourceChecks"),
        "overseas_official":("documents","checks"),
        "investigation_hunt":("investigations",None),
        "recent_metric_changes":("items",None),
        "nhtsa_official":("records","checks"),
    }
    for src in REQUIRED:
        value=sources.get(src,{})
        value=value if isinstance(value,dict) else {}
        datasets[src]=value
        coll,checks=keys[src]
        status.append(source_health(src,value,coll,now,checks))
    def add(lead,reason):
        if lead is None:
            skipped["source_without_official_identity"]+=1
            return
        lead["evidenceClass"]=reason
        event_rows.append(lead)

    # DART supply-contract/investment events. Public receipt means a notice
    # exists, NOT proof that the contract amount or counterparty was verified.
    for item in datasets["recent_contracts"].get("items",[]) or []:
        if not isinstance(item,dict):continue
        receipt=str(item.get("receiptNo") or "")
        url=item.get("sourceUrl")
        dt=parsed_date(item.get("published"))
        if not dt or not dart_receipt_link(receipt,url):
            skipped["source_without_official_identity"]+=1
            continue
        if item.get("isCorrection") is True:
            if (item.get("status")!="original_verified" or
                not item.get("originalReceiptNo")):
                skipped["correction_without_original"]+=1
                continue
            # Even an original-verified correction is a follow-up, never a
            # new contract. Company statement and change terms still unverified.
        company=str(item.get("company") or "").strip()
        if not company:
            skipped["source_without_official_identity"]+=1
            continue
        correction=item.get("isCorrection") is True
        headline=company+" · "+str(item.get("category") or "공시")+" · "+str(item.get("report") or "원문")[:90].strip()
        fact=("기존 공시의 정정 접수번호 확인(정정 전후 동일 사건·계약 조건 검토 필요)" if correction
              else "DART 공식 접수번호와 공시 제목 확인 · 계약금액·거래 상대방·기간은 별도 원문 확인")
        lead=event("DART_FILING",receipt,dt,headline,company,fact,url,
                   "공시 원문 필드, 원·정정 공시, 기보도 및 해당 회사 영향·상대방 확인")
        if lead:
            lead["officialReceiptNo"]=receipt
            lead["correction"]=correction
            lead["originalDocumentFieldsVerified"]=bool(item.get("observedFields"))
        add(lead,"official_filing_receipt" if not correction else "corrected_filing_review_only")

    # US Federal Register or EU TED: exact named companies are the minimum.
    # Keyword-index search matches cannot identify a Korean supplier or award.
    for item in datasets["overseas_official"].get("documents",[]) or []:
        if not isinstance(item,dict):continue
        if item.get("nameVerified") is not True or not item.get("companiesMentioned"):
            skipped["unverified_foreign_search_hit"]+=1
            continue
        when=parsed_date(item.get("published"))
        identifier=str(item.get("sourceId") or "")
        url=item.get("sourceUrl")
        valid=(official_link(url,"www.federalregister.gov") if item.get("source")=="US Federal Register"
               else official_link(url,"ted.europa.eu") if item.get("source")=="EU TED"
               else False)
        if not when or not NOTICE.fullmatch(identifier) or not valid:
            skipped["source_without_official_identity"]+=1
            continue
        companies=[str(v).strip() for v in item.get("companiesMentioned",[])
                   if isinstance(v,str) and v.strip()]
        if not companies:continue
        lead=event("FOREIGN_NOTICE",str(item.get("source"))+":"+identifier,when,
                   str(item.get("title") or "")[:260],"·".join(companies),
                   "미국 연방고시/유럽 공고의 제목·요약에 출입처 법인명 명시(실제 적용·사업 영향 미확인)",
                   url,"정부 원문 판정/효력일/품목/상대방과 국내 출입처 직접 영향 조사")
        add(lead,"named_company_in_official_notice")

    # Two historic DART filings form a supported difference, but the 2026
    # interim filing date controls freshness. Do not infer plant delay.
    for row in datasets["investigation_hunt"].get("investigations",[]) or []:
        for p in (row.get("projects",[]) if isinstance(row,dict) else []):
            links=p.get("originalUrls") if isinstance(p,dict) else None
            if not isinstance(links,list) or len(links)!=2:continue
            receipt_match=re.search(r"rcpNo=(20\d{12})",str(links[-1]))
            receipt=receipt_match.group(1) if receipt_match else ""
            dt=parsed_date(receipt[:8])
            if not dt or not dart_receipt_link(receipt,links[-1]):
                skipped["source_without_official_identity"]+=1
                continue
            lead=event("DART_DELTA",receipt+":"+str(p.get("project") or "")[:50],dt,
                 str(row.get("company") or "")+" · "+str(p.get("project") or ""),
                 str(row.get("company") or ""),
                 "과거·최근 사업보고서상 투자 종료 예정월 항목 차이(실제 준공 지연 증명 아님)",
                 links[-1],"공개된 공시 간 예상 종료월의 차이·이후 완공 공시·기보도 확인(미공개 생산계획 질의 금지)")
            add(lead,"comparison_of_two_public_reports")

    # Historic filings underpin DART numeric changes; collected date is
    # NOT a new business announcement. Receipt is the authoritative date.
    for row in datasets["recent_metric_changes"].get("items",[]) or []:
        if not isinstance(row,dict):continue
        receipts=row.get("originalReceipts")
        urls=row.get("sourceUrls")
        if not isinstance(receipts,list) or len(receipts)!=2 or not isinstance(urls,list) or len(urls)!=2:continue
        receipt=str(receipts[-1])
        dt=parsed_date(receipt[:8])
        if not dt or not dart_receipt_link(receipt,urls[-1]):
            skipped["source_without_official_identity"]+=1
            continue
        topic="/".join(str(x) for x in (row.get("rowIdentity") or [])[:2])
        lead=event("DART_METRIC",receipt+":"+topic[:90],dt,
                   str(row.get("company") or "")+" · "+topic,
                   str(row.get("company") or ""),
                   "동일 회계기간·단위 DART 기재 수치 "+
                   str(row.get("priorValue"))+" → "+str(row.get("currentValue"))+
                   " ("+str(row.get("unit") or "")+"), 실제 제품 출하량·사업 확정 아님",
                   urls[-1],"공시의 기간·단위·모수와 기보도 대조(생산·출하량은 공표 수치만 확인)")
        add(lead,"historical_official_numeric_comparison")

    # NHTSA model-specific searches can return January 2026 recalls in October.
    # Never put already-public recall in "fresh original report" tier.
    for row in datasets["nhtsa_official"].get("records",[]) or []:
        if not isinstance(row,dict):continue
        dt=parsed_date(row.get("reportDate"))
        no=str(row.get("id") or "")
        url=row.get("officialApi")
        if not dt or not re.fullmatch(r"[A-Z0-9]{6,18}",no) or not official_link(url,"api.nhtsa.gov"):
            skipped["source_without_official_identity"]+=1
            continue
        lead=event("NHTSA",no,dt,
                   str(row.get("make") or "")+" "+str(row.get("model") or "")+" · "+no,
                   str(row.get("make") or ""),
                   "이미 공개된 미국 "+str(row.get("kind") or "당국 기록")+
                   " · API 검색 결과(원문 상세 공고 링크 아님)",
                   url,"한국 판매 차종·실제 영향 확인, 미국 당국 원문과 기보도 대조")
        add(lead,"already_public_safety_reference")

    # Event identity: multiple independently repeated keyword searches must
    # not inflate the number of verified official changes.
    unique={}
    for lead in event_rows:
        if lead["id"] in unique:
            skipped["duplicate_event_id"]+=1
            continue
        unique[lead["id"]]=lead
    queue=[]
    reference=[]
    seen_out={}
    first=not initialized
    for item in unique.values():
        when=parsed_date(item["officialDate"])
        if when>today:
            skipped["source_without_official_identity"]+=1
            continue
        official_recent=start<=when<=today
        key=item["id"]
        was_seen=key in seen
        item["firstObservedAt"]=seen.get(key) if was_seen else now.date().isoformat()
        item["firstObservedThisRun"]=(None if first else not was_seen)
        item["publicDocumentAgeDays"]=(today-when).days
        item["officialDateInRecentWindow"]=official_recent
        # No safety recall as a fresh exclusive/contract lead, even if a very
        # recent public recall is in the cache.
        recent_usable=(official_recent and item["source"] in ("DART_FILING","FOREIGN_NOTICE")
                       and not item.get("correction",False))
        item["editorialBucket"]="recent_official_filing_review" if recent_usable else "published_background"
        item["freshArticleConfirmed"]=False
        item["sourceSnapshotAt"]=datasets[
          "recent_contracts" if item["source"]=="DART_FILING" else
          "overseas_official" if item["source"]=="FOREIGN_NOTICE" else
          "investigation_hunt" if item["source"]=="DART_DELTA" else
          "recent_metric_changes" if item["source"]=="DART_METRIC" else
          "nhtsa_official"
        ].get("generatedAt")
        (queue if recent_usable else reference).append(item)
        seen_out[key]=item["firstObservedAt"]
    queue.sort(key=lambda x:(-int(x["officialDate"].replace("-","")),x["source"],x["id"]))
    reference.sort(key=lambda x:(-int(x["officialDate"].replace("-","")),x["source"],x["id"]))
    # Preserve first-seen state for 120 days, without claiming press exclusivity.
    for k,v in seen.items():
        ts=parsed_date(v)
        if ts and ts>=today-timedelta(days=120):
            seen_out.setdefault(k,v)
    sources_bad=[s["name"] for s in status if s["status"]!="checked_source"]
    return {
      "generatedAt":now.isoformat(timespec="seconds"),
      "status":"official_date_triage",
      "windowStart":start.isoformat(),"windowEnd":today.isoformat(),
      "firstRunBaseline":first,
      "feedHealth":status,"incompleteOrStaleFeeds":sources_bad,
      "sourceCompletenessVerified":not sources_bad,
      "freshOfficialReviewCount":len(queue),
      "backgroundReferenceCount":len(reference),
      "excluded":skipped,
      "seen":seen_out,
      "freshOfficialReview":queue[:40],
      "backgroundReference":reference[:25],
      "truncatedBackgroundReference":max(0,len(reference)-25),
      "confirmedScoops":0,"approvedArticles":0,
      "warning":NO_AUTO_SCOOP+" 지난 데이터 수집시각은 공시/고시 발생일과 다름; 원천 미수집/부분수집을 0건으로 해석하지 말 것."
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",default="digests/official_event_triage_latest.json")
    args=p.parse_args()
    paths={
      "recent_contracts":"recent_contracts_latest.json",
      "overseas_official":"overseas_official_latest.json",
      "investigation_hunt":"investigation_hunt_latest.json",
      "recent_metric_changes":"recent_metric_changes_latest.json",
      "nhtsa_official":"nhtsa_official_latest.json"
    }
    def get(path):
        try:return json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError,ValueError):return {}
    sources={k:get("digests/"+v) for k,v in paths.items()}
    previous=get(args.output)
    report=build(sources,previous=previous)
    dest=Path(args.output);dest.parent.mkdir(parents=True,exist_ok=True)
    temp=dest.with_suffix(".json.tmp")
    temp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    temp.replace(dest)
    print("Official event-date triage",report["windowStart"],report["windowEnd"],
       "fresh public filings for human review",report["freshOfficialReviewCount"],
       "old/background",report["backgroundReferenceCount"],
       "source issues",len(report["incompleteOrStaleFeeds"]),
       "confirmed scoops 0")
if __name__=="__main__":main()
