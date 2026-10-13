"""Link KIPRIS patent leads to *independent* public OpenDART evidence.

Evidence is layered:
  company_context: same exact legal reporting issuer, unrelated business context
  technical_overlap_to_verify: exact company AND distinctive technical phrase in a
     documented DART table/contract title -- NOT proof of the same project
  reporter_verified_link: never automatically assigned.
No automatic sales, project application, commercial impact or scoop claims.
"""
from __future__ import annotations
import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST=timezone(timedelta(hours=9))
DOC_ID=re.compile(r"^\d{14}$")
PATENT_ID=re.compile(r"^10\d{11}$")
TERM_PATTERNS={
    "부분방전":("부분방전",),"전력케이블":("전력케이블","송전케이블"),
    "상변태":("상변태",),"침투탐상":("침투탐상",),
    "비파괴검사":("비파괴검사","비파괴 검사"),
    "휠체어":("휠체어",),"고정자":("고정자",),
    "고정자냉각":("고정자 냉각","고정자냉각"),
    "액체냉각":("액체 냉각","액체냉각"),
    "수소환원":("수소환원","수소 환원"),
    "전고체":("전고체",),"고전압":("고전압",),
    "양극재":("양극재",),"음극재":("음극재",),
    "전력변환":("전력 변환","전력변환"),
    "전기로":("전기로",),"철심적층":("철심 적층","철심적층"),
}
ALIASES={
    "현대자동차":"현대차","기아":"기아","현대제철":"현대제철",
    "LS전선":"LS전선","엘에스전선":"LS전선",
    "엘에스일렉트릭":"LS일렉트릭","LS일렉트릭":"LS일렉트릭",
    "HD현대일렉트릭":"HD현대일렉트릭","두산에너빌리티":"두산에너빌리티",
    "포스코":"포스코","세아제강":"세아제강","효성중공업":"효성중공업",
    "현대모비스":"현대모비스","고려아연":"고려아연",
    "영풍":"영풍","KG스틸":"KG스틸",
}
def issuer(value):
    name=str(value or "").replace("주식회사","").replace("(주)","").replace(" ","").strip()
    # Only explicitly listed reporting entities; never map subsidiaries by guess.
    return ALIASES.get(name,"")

def concepts(lead):
    value=(str(lead.get("title") or "")+" "+str(lead.get("sourceAbstractExcerpt") or "")).lower()
    return {term for term,variants in TERM_PATTERNS.items()
            if any(v.lower() in value for v in variants)}

def matching_terms(needle,text):
    row=str(text or "").lower()
    return sorted(term for term in needle if any(x.lower() in row for x in TERM_PATTERNS[term]))

def receipt_url(value):
    n=str(value or "")
    return "https://dart.fss.or.kr/dsaf001/main.do?rcpNo="+n if DOC_ID.fullmatch(n) else None

def rows_to_strings(table):
    for row in (table.get("rows") or [])[:55]:
        if isinstance(row,list):
            # Most cells are individual labels or numeric values. Concatenate
            # row cells only; do not scan the multi-page context (false hits).
            yield " ".join(str(x) for x in row if x is not None)[:440]

def collect_public_sources(business,contracts,delta):
    entries=[]
    for co in business.get("companies",[]):
        if co.get("status")!="official_sections_retrieved":continue
        name=issuer(co.get("company"))
        current=co.get("current") or {}
        uri=receipt_url(current.get("receiptNo"))
        if not name or not uri:continue
        for table in (current.get("tables") or [])[:15]:
            for row in rows_to_strings(table):
                entries.append({"company":name,"sourceType":"dart_business_table",
                                "reference":str(table.get("topic") or ""),
                                "text":row,"url":uri,
                                "published":str(current.get("published") or ""),
                                "snapshotAt":business.get("generatedAt")})
    for event in contracts.get("items",[]):
        name=issuer(event.get("company"))
        url=receipt_url(event.get("receiptNo"))
        if not name or not url:continue
        # Do not use unverified 'changes', company-specific financial values,
        # or imply a supply contract for patented technology.
        entries.append({"company":name,"sourceType":"dart_contract_title",
                        "reference":str(event.get("category") or ""),
                        "text":str(event.get("report") or "")[:350],
                        "url":url,"published":str(event.get("published") or ""),
                        "snapshotAt":contracts.get("generatedAt")})
    for section in delta.get("investigations",[]):
        name=issuer(section.get("company"))
        if not name:continue
        for project in (section.get("projects") or [])[:20]:
            urls=project.get("originalUrls") or []
            receipts=project.get("annualReceipt"),project.get("currentReceipt")
            uri=receipt_url(receipts[1])
            if not uri:continue
            entries.append({"company":name,"sourceType":"dart_investment_schedule_change",
                            "reference":"공시상 계획변경, 실제 지연 미확인",
                            "text":str(project.get("project") or "")[:240],
                            "url":uri,"published":str(project.get("toPublished") or ""),
                            "snapshotAt":delta.get("generatedAt")})
    return entries

def latest_checks(ledger):
    if not isinstance(ledger,dict) or not isinstance(ledger.get("checks"),list):
        raise ValueError("Fact-check ledger must have checks list")
    reviews={}
    for event in ledger["checks"]:
        if (not isinstance(event,dict) or
            not PATENT_ID.fullmatch(str(event.get("publicationNumber") or "")) or
            event.get("checkType") not in
                ("prior_coverage","company_response","actual_application",
                 "industry_impact","reporting_angle")):
            continue
        reviews[(event["publicationNumber"],event["checkType"])]=event
    return reviews

def evaluate(desk,business,contracts,delta,ledger,now=None):
    now=now or datetime.now(KST)
    if desk.get("status")!="research_priorities_only" or not isinstance(desk.get("reviewQueue"),list):
        raise ValueError("No validated KIPRIS desk snapshot")
    entries=collect_public_sources(business,contracts,delta)
    reviewed=latest_checks(ledger)
    results=[]
    for row in desk["reviewQueue"]:
        number=str(row.get("publicationNumber") or "")
        if not PATENT_ID.fullmatch(number):continue
        owners={issuer(x) for x in row.get("coveredCompanies") or []}-{""}
        terms=concepts(row)
        same_issuer=[]
        technical=[]
        for entry in entries:
            if entry["company"] not in owners:continue
            hits=matching_terms(terms,entry["text"])
            if hits:
                technical.append({**entry,"technicalTermsShared":hits,
                                  "relation":"same_issuer_technical_words_not_project_identity"})
            else:
                same_issuer.append(entry)
        # Repeated financial tables are context, NOT a research project match.
        ranked=sorted(technical,key=lambda x:(-len(x["technicalTermsShared"]),
                                 -int(x["published"] or 0),x["sourceType"]))
        by_reference={}
        for event in ranked:
            by_reference.setdefault((event["sourceType"],event["url"],event["text"]),event)
        linked=list(by_reference.values())[:5]
        # Show independent *same issuer* DART sources even without technical
        # overlap. They are background reading, not evidence of application.
        background={}
        for entry in same_issuer:
            key=(entry["sourceType"],entry["url"],entry["reference"])
            if key not in background:
                background[key]={"company":entry["company"],
                    "sourceType":entry["sourceType"],"reference":entry["reference"],
                    "sourceUrl":entry["url"],"published":entry["published"],
                    "linkState":"same_company_only_no_patent_relation"}
        background=list(background.values())[:4]
        labels={kind:reviewed.get((number,kind),{}).get("result","not_reviewed")
                for kind in ("prior_coverage","company_response",
                             "actual_application","industry_impact","reporting_angle")}
        # A public URL with a reporter's check is a verified *review event*.
        # It still does not make the actual patent-project mapping verified.
        blockers=[kind for kind,result in labels.items() if result!="verified_public"]
        if row.get("retrospectiveKnownCase") or row.get("cautionFlags"):
            stage="hold_prior_coverage_or_known_case"
        elif not row.get("mediaReview",{}).get("checked"):
            stage="research_only_press_not_checked"
        elif any(labels.get(x)=="contradicted_public" for x in
                 ("actual_application","industry_impact","reporting_angle")):
            stage="hold_claim_disproved"
        elif not blockers:
            stage="editorial_review_possible_human_final_required"
        elif linked:
            stage="cross_document_context_needs_company_confirmation"
        else:
            stage="patent_only_no_project_identity"
        results.append({
            "publicationNumber":number,"title":row.get("title"),
            "coveredCompanies":list(owners),
            "topic":row.get("topic"),
            "technicalTerms":sorted(terms),
            "sameIssuerDartRowsObserved":len(same_issuer)+len(technical),
            "sameIssuerBackgroundSources":background,
            "independentDartTechnicalOverlap":linked,
            "humanPublicCheckStatuses":labels,
            "missingVerification":blockers,
            "stage":stage,
            "publicCompanyResponseMarkedByReporter":labels["company_response"]=="verified_public",
            "independentlyValidatedCompanyResponse":False,
            "specificProjectLinkVerified":False,
            "impactCausalityVerified":False,
            "approvedForPublication":False,
            "confirmedExclusive":False,
            "nextStep":("동일 기업의 DART 공시에서 기술어휘가 겹쳐도 실제 같은 프로젝트인지 회사 직접 확인"
                        if linked else "동일 출입처 DART 자료에서 특정 특허-사업 연결 근거 미발견 · 기업 문의 필요"),
        })
    selected={x["publicationNumber"]:x for x in results}
    return {
        "generatedAt":now.isoformat(timespec="seconds"),
        "deskSourceGeneratedAt":desk["generatedAt"],
        "crossSourceGeneratedAt":{
            "dartBusiness":business.get("generatedAt"),
            "dartContracts":contracts.get("generatedAt"),
            "dartInvestmentChange":delta.get("generatedAt")},
        "inputAvailability":{
            "dartBusiness":bool(business.get("generatedAt") and business.get("companies")),
            "dartContracts":bool(contracts.get("generatedAt") and isinstance(contracts.get("items"),list)),
            "dartInvestmentChange":bool(delta.get("generatedAt") and isinstance(delta.get("investigations"),list))},
        "candidateCount":len(results),
        "candidateWithSpecificTermOverlap":sum(bool(x["independentDartTechnicalOverlap"]) for x in results),
        "checkEvents":len(ledger["checks"]),
        "publicChecksOnCurrentCandidates":sum(any(v!="not_reviewed" for v in r["humanPublicCheckStatuses"].values()) for r in results),
        "stageCounts":{stage:sum(x["stage"]==stage for x in results) for stage in
                       sorted({x["stage"] for x in results})},
        "prioritized": [selected[x["publicationNumber"]] for x in desk.get("shortlist",[])
                        if x.get("publicationNumber") in selected],
        "reviews":results,"confirmedExclusives":0,"approvedArticles":0,
        "warning":"DART는 일부 법인·정기공시/21일 계약/확인된 투자계획 변경만 포함. 동일 회사/기술어휘로 특허-사업 연결 확정 금지. NTIS·IR·해외 문서 자동 연동은 아직 포함되지 않음.",
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--desk",default="digests/patent_desk_latest.json")
    p.add_argument("--business",default="digests/recent_business_latest.json")
    p.add_argument("--contracts",default="digests/recent_contracts_latest.json")
    p.add_argument("--delta",default="digests/investigation_hunt_latest.json")
    p.add_argument("--checks",default="data/patent_reporting_checks.json")
    p.add_argument("--out",default="digests/patent_cross_evidence_latest.json")
    args=p.parse_args()
    def load(name):return json.loads(Path(name).read_text(encoding="utf-8"))
    def optional(name):
        try:return load(name)
        except (OSError,ValueError):return {}
    report=evaluate(load(args.desk),optional(args.business),optional(args.contracts),
                    optional(args.delta),load(args.checks))
    path=Path(args.out);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    tmp.replace(path)
    print("DART cross-check",report["candidateCount"],"technical overlaps",
          report["candidateWithSpecificTermOverlap"],"articles approved",report["approvedArticles"])

if __name__=="__main__":main()
