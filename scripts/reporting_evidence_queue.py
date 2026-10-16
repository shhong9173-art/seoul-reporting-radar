"""Source-date-first industrial reporting queue assembled from published evidence.

This is a research *verification queue*, never a scoop or a publishable pitch.
A new scrape, an old DART correction, or an unreviewed press index cannot
establish novel news. No external APIs or newsroom credentials are used.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

KST=timezone(timedelta(hours=9))
DART_RECEIPT=re.compile(r"20\d{12}\Z")
CATEGORIES={
    "new_official_receipt_review":"최근 공식 접수 확인·본문 검증 전",
    "verified_historical_investment_delta":"과거 DART 투자계획 기재 비교",
    "verified_historical_numeric_delta":"과거 DART 공시 수치 비교",
    "issuer_only_correction_unverified_original":"정정문 자체 기재변경·원공시 미대조",
    "older_public_contract_reference":"이전 공식 계약 공시 참고자료",
}
SCOPES={
    "officialEvents":("official_date_triage", "freshOfficialReview"),
    "investment":("source_changes_detected_not_exclusive", "investigations"),
    "metrics":(None,"items"),
    "contracts":("reporter_review_not_exclusive","items"),
}
MAX_RECORDS=140

def parse_timestamp(raw):
    if not isinstance(raw,str):return None
    try:
        out=datetime.fromisoformat(raw)
        return out if out.utcoffset() is not None else None
    except ValueError:return None

def date_value(raw):
    if not isinstance(raw,str):return None
    try:
        if re.fullmatch(r"20\d{6}",raw):
            return datetime.strptime(raw,"%Y%m%d").date()
        if re.fullmatch(r"20\d\d-\d\d-\d\d",raw):
            return date.fromisoformat(raw)
    except ValueError:pass
    return None

def dart_url(receipt,url):
    if not isinstance(receipt,str) or not DART_RECEIPT.fullmatch(receipt):
        return False
    if not isinstance(url,str):return False
    try:
        u=urlsplit(url)
        return (u.scheme=="https" and u.hostname=="dart.fss.or.kr"
                and u.username is None and u.password is None
                and u.path=="/dsaf001/main.do"
                and parse_qs(u.query)=={"rcpNo":[receipt]})
    except ValueError:return False

def foreign_url(url):
    if not isinstance(url,str):return False
    try:
        u=urlsplit(url)
        return (u.scheme=="https" and u.hostname in
                {"www.federalregister.gov","ted.europa.eu"}
                and u.username is None and u.password is None)
    except ValueError:return False

def source_health(sources,now):
    result={}
    for key,(required_status,collection) in SCOPES.items():
        s=sources.get(key)
        parsed=parse_timestamp(s.get("generatedAt")) if isinstance(s,dict) else None
        rows=s.get(collection) if isinstance(s,dict) else None
        status=s.get("status") if isinstance(s,dict) else None
        valid=(parsed is not None and isinstance(rows,list)
               and (required_status is None or status==required_status))
        future=valid and parsed>now+timedelta(minutes=15)
        stale=valid and (now-parsed)>timedelta(hours=48)
        result[key]={
            "status":("unavailable_or_schema_mismatch" if not valid else
                      "future_timestamp_invalid" if future else
                      "old_snapshot_not_a_current_scan" if stale else
                      "source_snapshot_checked"),
            "generatedAt":s.get("generatedAt") if valid else None,
            "rows":len(rows) if valid else None,
            "completeAcrossUniverse":False,
            "zeroItemsProvesNoEvent":False
        }
    event=sources.get("officialEvents") if isinstance(sources.get("officialEvents"),dict) else {}
    if result["officialEvents"]["status"]=="source_snapshot_checked":
        if event.get("sourceCompletenessVerified") is not True:
            result["officialEvents"]["status"]="source_partial_coverage"
        result["officialEvents"]["incompleteOrStaleFeeds"]=(
            event.get("incompleteOrStaleFeeds")
            if isinstance(event.get("incompleteOrStaleFeeds"),list) else [])
    return result

def record(tier,key,company,title,when,details,urls,checks):
    return {
      "id":tier+":"+key,
      "tier":tier,"tierLabel":CATEGORIES[tier],
      "company":company[:90],"title":title[:220],
      "officialDocumentDate":when.isoformat(),
      "officialDateIsSourcePublicationNotScrape":True,
      "evidenceSummary":details[:470],
      "officialUrls":urls[:3],
      "pressFulltextReviewed":False,
      "sameAngleCoverageVerified":False,
      "companyImpactVerified":False,
      "futurePlanVerified":False,
      "exclusiveConfirmed":False,
      "approvedForPitch":False,
      "nextChecks":checks[:4],
    }

def build(sources,*,now=None):
    now=now or datetime.now(KST)
    if now.utcoffset() is None or not isinstance(sources,dict):
        raise ValueError("timezone_and_source_mapping_required")
    now=now.astimezone(KST)
    health=source_health(sources,now)
    today=now.date()
    earliest=today-timedelta(days=2)
    records=[]
    skipped={"invalid_original_identity":0,"old_and_not_relevant":0,
             "unverified_correction":0,"same_receipt_merged":0}
    # This is an input fact, not merely a zero result on our side.
    events=sources.get("officialEvents") or {}
    if health["officialEvents"]["status"] in ("source_snapshot_checked","source_partial_coverage"):
        for item in events.get("freshOfficialReview",[])[:150]:
            if not isinstance(item,dict):continue
            when=date_value(item.get("officialDate"))
            if when is None or not earliest<=when<=today:
                skipped["old_and_not_relevant"]+=1;continue
            kind=item.get("source")
            url=item.get("sourceUrl")
            receipt=item.get("officialReceiptNo")
            if kind=="DART_FILING":
                if not dart_url(receipt,url):skipped["invalid_original_identity"]+=1;continue
                identity="DART:"+receipt
            elif kind=="FOREIGN_NOTICE":
                if not foreign_url(url):skipped["invalid_original_identity"]+=1;continue
                identity=str(item.get("id") or "")
                if not identity.startswith("FOREIGN_NOTICE:"):continue
            else:continue
            if (item.get("classification")!="public_official_document_not_a_scoop" or
                item.get("companyImpactVerified") is not False or
                item.get("exclusiveConfirmed") is not False or
                item.get("approvedForPitch") is not False):continue
            company=str(item.get("company") or "").strip()
            title=str(item.get("headline") or "").strip()
            if not company or not title:continue
            records.append(record("new_official_receipt_review",identity,
                 company,title,when,str(item.get("officialFact") or ""),
                 [url],[
                   "공식 문서 본문에서 실제 계약·규제·금액·효력 범위 확인",
                   "같은 사안의 기존 보도 전문 및 최초 공표 시각 확인",
                   "기업의 이미 발표한 실적·판매·공시 사실과 실제 영향 확인",
                 ]))
    investments=sources.get("investment") or {}
    if health["investment"]["status"]=="source_snapshot_checked":
        for inv in investments.get("investigations",[])[:40]:
            if not isinstance(inv,dict):continue
            company=str(inv.get("company") or "")
            for project in (inv.get("projects") or [])[:20]:
                if not isinstance(project,dict):continue
                urls=project.get("originalUrls")
                receipt=project.get("currentReceipt")
                old=project.get("annualReceipt")
                dt=date_value(receipt[:8]) if isinstance(receipt,str) else None
                if (dt is None or dt>today or (today-dt).days>365 or
                    not isinstance(urls,list) or len(urls)!=2 or
                    not dart_url(old,urls[0]) or not dart_url(receipt,urls[1]) or
                    project.get("company")!=company or
                    not isinstance(project.get("factVerified"),str) or
                    project.get("alreadyPublic") is not True):
                    skipped["invalid_original_identity"]+=1;continue
                proj=str(project.get("project") or "")
                shift=project.get("endMonthShift")
                if type(shift) is not int or not -180<=shift<=180:continue
                before=str(project.get("oldPlannedEnd") or "")
                after=str(project.get("newPlannedEnd") or "")
                if not re.fullmatch(r"20\d\d\.(?:0[1-9]|1[0-2])",before) or not re.fullmatch(r"20\d\d\.(?:0[1-9]|1[0-2])",after):
                    continue
                details=(f"기존 공시 계획상 종료월 {before} → 최근 공시 {after} "
                         f"({shift:+d}개월). 실제 준공·가동일 및 일정 지연은 검증되지 않음.")
                records.append(record("verified_historical_investment_delta",
                    receipt+":"+proj,company,proj+" · 공시상 투자기간 변경",dt,
                    details,urls,[
                      "동일 사업·시작월·설비 범위 및 이전/최근 공시 원문 재확인",
                      "회사 공개자료에서 실제 준공·가동일 확인 가능 여부",
                      "해당 변화가 보도된 적 있는지 기존 기사 전문 대조",
                    ]))
    metrics=sources.get("metrics") or {}
    if health["metrics"]["status"]=="source_snapshot_checked":
        for row in metrics.get("items",[])[:200]:
            if not isinstance(row,dict):continue
            receipts=row.get("originalReceipts")
            urls=row.get("sourceUrls")
            company=str(row.get("company") or "").strip()
            labels=row.get("rowIdentity")
            if not isinstance(receipts,list) or len(receipts)!=2 or not isinstance(urls,list) or len(urls)!=2 or not isinstance(labels,list) or not company:
                continue
            dt=date_value(str(receipts[1])[:8])
            if (dt is None or dt>today or (today-dt).days>365 or
                not dart_url(receipts[0],urls[0]) or not dart_url(receipts[1],urls[1]) or
                not isinstance(row.get("evidenceStatus"),str) or
                "일치 검증" not in row["evidenceStatus"]):
                skipped["invalid_original_identity"]+=1;continue
            metric=str(row.get("topic") or "")
            label=" / ".join(str(s) for s in labels[:2])[:130]
            if not label:continue
            details=(str(row.get("fromYear"))+"년 → "+str(row.get("toYear"))+
               "년 동일표 행값 "+str(row.get("priorValue"))+" → "+
               str(row.get("currentValue"))+" ("+str(row.get("unit"))+
               "). 공시 표기 수치이며 실제 출하·생산량은 별도 검증 필요.")
            records.append(record("verified_historical_numeric_delta",
                str(receipts[1])+":"+company+":"+metric+":"+label,
                company,label+" · "+metric+" 공시 수치 비교",dt,details,urls,
                ["회계연도·기간·단위·세그먼트의 정확한 모수 재확인",
                 "동일 분기/반기 수치 변경인지 공시 원문 대조",
                 "기존 보도 전문과 기업 공개 IR 자료 확인"]))
    contracts=sources.get("contracts") or {}
    if health["contracts"]["status"]=="source_snapshot_checked":
        for item in contracts.get("items",[])[:90]:
            if not isinstance(item,dict):continue
            receipt=item.get("receiptNo")
            url=item.get("officialSourceUrl")
            dt=date_value(receipt[:8]) if isinstance(receipt,str) else None
            if not dt or dt>today or (today-dt).days>180 or not dart_url(receipt,url):
                skipped["invalid_original_identity"]+=1;continue
            company=str(item.get("company") or "").strip()
            if not company or item.get("exclusiveConfirmed") is not False or item.get("approvedForPitch") is not False:
                continue
            if item.get("isCorrection") is True:
                if (item.get("originalReceiptNo") is not None or
                    item.get("comparisonStatus")!="original_unverified_no_comparison" or
                    item.get("officialSourceStatus")!="original_not_verified"):
                    # Do not infer a verified diff from unrecognized correction states.
                    skipped["unverified_correction"]+=1;continue
                changes=item.get("issuerDeclaredMaterialChanges") or []
                if not isinstance(changes,list):continue
                labels=[str(x.get("fieldLabel") or "")[:55] for x in changes[:4]
                        if isinstance(x,dict) and
                           x.get("basis")=="issuer_reported_amendment_table_only"
                           and x.get("originalDocumentCompared") is False]
                details=("정정 공시의 발행사 기재 변경란 참고 "+("·".join(labels) if labels else "원공시 확인 필요")+
                    ". 최초 원공시 미대조. 동일 계약·실제 계약 조건의 변화는 확정되지 않음.")
                tier="issuer_only_correction_unverified_original"
                checks=["최초 원공시 번호·정정 이력의 같은 계약 여부",
                        "원공시/직전 정정문의 계약조건 전후 실제 비교",
                        "동일 사건 기존 기사 전문·기업 공개 답변 확인"]
            else:
                if item.get("comparisonStatus")!="not_a_correction":continue
                tier="older_public_contract_reference"
                details="이미 접수된 공식 계약 공시. 상세 상대방·계약금액·현지 출하·기업 영향과 기존 보도는 별도 확인."
                checks=["원 공시 계약 상대방·계약금액·기간 확인",
                        "기존 언론 기사와 같은 계약인지 기사 전문 검증",
                        "해당 기업의 공개 사업부 자료 중 실제 실적 반영 확인"]
            records.append(record(tier,"DART:"+receipt,company,
                   str(item.get("headline") or company+" 계약 공시"),dt,
                   details,[url],checks))
    # One document can surface via the date engine AND contract follow-up.
    # Keep recent dated official identity; never duplicate it as a new story.
    ranks={k:i for i,k in enumerate(CATEGORIES)}
    order=sorted(records,key=lambda x:(
        ranks[x["tier"]],-int(x["officialDocumentDate"].replace("-","")),x["id"]))
    seen_receipt=set()
    unique=[]
    for row in order:
        urls=row["officialUrls"]
        this_receipt=next((parse_qs(urlsplit(z).query).get("rcpNo",[None])[0]
                           for z in urls if urlsplit(z).hostname=="dart.fss.or.kr"),None)
        # Only deduplicate generic contract reference vs same fresh filing.
        if this_receipt and row["tier"]=="older_public_contract_reference":
            if this_receipt in seen_receipt:
                skipped["same_receipt_merged"]+=1;continue
        if row["tier"]=="new_official_receipt_review" and this_receipt:
            seen_receipt.add(this_receipt)
        unique.append(row)
    counts={tier:sum(x["tier"]==tier for x in unique) for tier in CATEGORIES}
    overall="partial_source_coverage_not_zero_news" if any(
       x["status"]!="source_snapshot_checked" for x in health.values()) else "verified_inputs_only"
    return {
        "generatedAt":now.isoformat(timespec="seconds"),
        "status":"reporter_evidence_queue_not_exclusive",
        "sourceCoverage":overall,
        "sourceHealth":health,
        "countsByEvidenceTier":counts,
        "sourceDateWindow":{ "recentFrom":earliest.isoformat(),"through":today.isoformat()},
        "checkedOfficialRecentCandidates":counts["new_official_receipt_review"],
        "totalRows":len(unique[:MAX_RECORDS]),
        "excluded":skipped,
        "confirmedScoops":0,
        "approvedArticles":0,
        "warning":"공식 발행일≠수집일, 투자 종료 예정월 변경≠실제 지연, 정정문 변경란≠원공시 대조, 보도 검색 0건≠미보도. 미수집/부분수집≠사건 0건.",
        "items":unique[:MAX_RECORDS]
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",default="digests/reporting_evidence_queue_latest.json")
    p.add_argument("--official",default="digests/official_event_triage_latest.json")
    p.add_argument("--investments",default="digests/investigation_hunt_latest.json")
    p.add_argument("--metrics",default="digests/recent_metric_changes_latest.json")
    p.add_argument("--contracts",default="digests/dart_contract_followup_latest.json")
    a=p.parse_args()
    def read(path):
        try:return json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError,ValueError):return None
    result=build({
        "officialEvents":read(a.official),"investment":read(a.investments),
        "metrics":read(a.metrics),"contracts":read(a.contracts)})
    output=Path(a.out);output.parent.mkdir(parents=True,exist_ok=True)
    temp=output.with_suffix(".json.tmp")
    temp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    temp.replace(output)
    print("Evidence queue official recent",result["checkedOfficialRecentCandidates"],
          "historical/method review",result["totalRows"]-
          result["checkedOfficialRecentCandidates"],"exclusive approved",result["confirmedScoops"])

if __name__=="__main__":main()
