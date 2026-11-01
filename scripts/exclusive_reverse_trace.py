"""Evidence-first reverse tracing of Korean '[단독]' press to earlier sources.

Candidate headline discovery is automatic. Y/P/N judgments are NEVER automatic:
they require human-reviewed story fulltext, a documented pre-story public trace
(Y exact fact, P partial hint) or an explicit no-public-trace research log (N).
A title "[단독]" does not prove original reporting or exclusive story status.
"""
from __future__ import annotations
import argparse
import json
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

KST=timezone(timedelta(hours=9))
STATUS="automotive_industry_exclusive_reverse_trace_unverified_candidates"
LABELS=frozenset({"Y","P","N"})
MAX_ARTICLES=100_000
SCOOP_MARKER=re.compile(r"^\s*(?:\[[^\]]*단독[^\]]*\]|\([^)]*단독[^)]*\)|【[^】]*단독[^】]*】)")
SPORTS=re.compile(r"KIA\s*타이거즈|기아\s*타이거즈|현대모비스\s*(?:피버스|농구|농구단)|프로야구|야구단|프로농구|KBL|KBO|축구단|농구단",re.I)
INDUSTRY_COMPANIES={
    "현대차","현대자동차","기아","제네시스","현대모비스","현대위아","HL만도",
    "한국GM","KG모빌리티","르노코리아","한국타이어","넥센타이어","금호타이어",
    "포스코홀딩스","포스코","현대제철","KG스틸","세아제강","고려아연","영풍",
    "HD현대일렉트릭","LS일렉트릭","엘에스일렉트릭","LS전선","대한전선",
    "효성중공업","일진전기","두산에너빌리티","한화솔루션","OCI","OCI홀딩스",
    "SK이노베이션","LG에너지솔루션","삼성SDI","SK온","천보","씨에스윈드",
    # 11-01 기자 명시: 석유화학·정유
    "LG화학","롯데케미칼","금호석유화학","금호석화","S-OIL","에쓰오일","HD현대오일뱅크","현대오일뱅크",
}
KINDS=(
    # SUBJECT categories detected from article HEADLINES only. They do not
    # establish whether the event occurred, which official source existed,
    # or whether the story was an exclusive. Preserve U/Y/P/N independently.
    ("리콜·안전",re.compile(
        r"리콜|결함|화재|발화|침수|누수|빗물.{0,10}유입|"
        r"에어백|품질불량|안전성|NHTSA|제작결함",re.I)),
    ("정책·규제·입법",re.compile(
        r"입법|법안|시행령|행정예고|규제|법제화|국회|"
        r"환경기준|배출가스 기준|자율주행.{0,12}(법|제도)",re.I)),
    ("통상·관세",re.compile(
        r"관세|반덤핑|상계관세|무역구제|수출규제|세이프가드",re.I)),
    ("회생·소송",re.compile(
        r"회생|파산|소송|법원|법정관리|가처분|채권단|승소|"
        r"배상|구상권|무혐의|검찰|피의자|과태료|세금.{0,8}분쟁|"
        r"개인정보.{0,8}유출|담합",re.I)),
    ("노사·인사",re.compile(
        r"노사|임단협|노조|파업|인사|대표이사|임원|해고|노동자|"
        r"중대재해|임금협상|잠정합의|조직개편|노무조직|영입|"
        r"선임|인재 흡수|사업총괄|경조휴가|TFT.{0,6}신설",re.I)),
    ("자본·지배구조",re.compile(
        r"자사주|자기주식|분할|합병|배당|지분|경영권|인수|매각|"
        r"합작법인|공모채|회사채|자금\s*조달|"
        r"채권.{0,7}(?:발행|승인|심의)",re.I)),
    ("공장·생산·투자",re.compile(
        r"공장|생산중단|생산계획|가동|증설|투자부지|생산라인|"
        r"시설투자|\d+조\s*투자|\d+억\s*투자|"
        r"투자.{0,12}(확대|발표|결정|착수|착공|규모|첫삽)|"
        r"양산|증산|셧다운|생산설비|설비\s*확충|제철소|"
        r"생산량|생산능력|투자",re.I)),
    ("수주·입찰",re.compile(
        r"계약|수주|입찰|낙찰|발주|고객사|공급|납품|운영권|"
        r"전력망.{0,7}구축|시설.{0,7}구축",re.I)),
    ("판매·가격·서비스",re.compile(
        r"판매|가격인상|가격인하|요금제|할인|물량\s*축소|"
        r"단산|내수\s*판매|서비스\s*(?:출시|개시|첫선)|"
        r"국내외\s*판매|수요\s*(?:급감|감소)",re.I)),
    ("신차·인증·허가",re.compile(
        r"신차|차종|출시|전기차|인허가|형식승인|인증|환경영향평가|"
        r"모델 출시|전동화|사용승인|행정.{0,5}승인|상용화",re.I)),
    ("특허·상표",re.compile(
        r"특허|상표|디자인|지식재산",re.I)),
    ("기술·연구·사업화",re.compile(
        r"R&D|로봇|자율주행|전고체|배터리|재활용|수소환원제철|"
        r"기술\s*(?:검증|개발|도입)|검증\s*플랫폼|"
        r"(?<![A-Za-z])AI(?![A-Za-z])|V2C|ESS",re.I)),
)

SOURCE_CLASSES={
    "company_notice","government_notice","court_ruling","regulatory_filing",
    "patent_original","public_tender","overseas_register","corporate_registry",
    "vehicle_recall","other_official",
}


def aware(value):
    if not isinstance(value,str) or not value or len(value)>45:return None
    try:
        v=datetime.fromisoformat(value.replace("Z","+00:00"))
        return v if v.tzinfo is not None and v.utcoffset() is not None else None
    except (ValueError,TypeError,OverflowError):
        return None


def article_id(row):
    if not isinstance(row,dict):return None
    key=row.get("id")
    return key if isinstance(key,str) and re.fullmatch(r"[a-z0-9]{24}",key) else None


def candidate(row):
    if (not isinstance(row,dict) or row.get("global") is True
        or not isinstance(row.get("title"),str)
        or not SCOOP_MARKER.search(row["title"])
        or SPORTS.search(row["title"])):
        return False
    companies=row.get("companies")
    if not isinstance(companies,list) or not any(x in INDUSTRY_COMPANIES for x in companies):
        return False
    return article_id(row) is not None and aware(row.get("published")) is not None


def kind_for(headline):
    for label,pattern in KINDS:
        if pattern.search(headline):return label
    return "기타·원문 분류 필요"


def safe_public_url(url):
    if not isinstance(url,str) or len(url)>1600:return False
    try:
        loc=urlsplit(url)
        return loc.scheme=="https" and bool(loc.hostname) and not loc.username and not loc.password
    except ValueError:
        return False


def validate_review(row,original):
    """Accept only an explicit human evidence sheet; fail closed on mistakes."""
    if not isinstance(row,dict) or row.get("articleId")!=original["id"]:
        return None
    verdict=row.get("verdict")
    if verdict not in LABELS or row.get("reviewedByHuman") is not True:
        return None
    if row.get("articleFulltextReviewed") is not True:
        return None
    reviewer=row.get("reviewer")
    notes=row.get("evidenceReason")
    reviewed_at=aware(row.get("reviewedAt"))
    if (not isinstance(reviewer,str) or not 2<=len(reviewer)<=80
        or not isinstance(notes,str) or not 12<=len(notes)<=1500
        or reviewed_at is None):
        return None
    # Google News RSS dates are observation/index timestamps. They cannot
    # establish when a publisher first released the article. A human must
    # inspect the publisher's original and verify its initial publication time
    # before ANY Y/P/N claim enters the measured denominator.
    publisher_url=row.get("publisherOriginalUrl")
    publisher_first=aware(row.get("publisherFirstPublishedAt"))
    publisher_host=(urlsplit(publisher_url).hostname or "").lower() if safe_public_url(publisher_url) else ""
    if (not publisher_first or not publisher_host
        or publisher_host=="news.google.com"
        or publisher_host.endswith(".google.com")
        or row.get("publisherPublicationTimeVerifiedByHuman") is not True
        or publisher_first>reviewed_at):
        return None
    if verdict in ("Y","P"):
        source_dt=aware(row.get("primaryPublishedAt"))
        story_dt=publisher_first
        source=row.get("primarySourceUrl")
        category=row.get("primarySourceType")
        trace=row.get("publicTraceOverlap")
        if (not safe_public_url(source) or source_dt is None or story_dt is None
            or source_dt >= story_dt
            or row.get("primaryPublicationTimeVerifiedByHuman") is not True
            or source_dt > reviewed_at
            or category not in SOURCE_CLASSES
            or trace!=("exact" if verdict=="Y" else "partial")
            or row.get("primaryTextComparedAgainstArticle") is not True):
            return None
    else:
        # 'N' is a recorded human research outcome, NOT logical proof that
        # no public hint anywhere in the world could ever have existed.
        if (row.get("multiplePublicSourcesChecked") is not True
            or row.get("primarySourceUrl")
            or row.get("publicTraceOverlap") not in (None,"none")
            or row.get("reporterEvidenceReviewed") is not True):
            return None
    return {
        "verdict":verdict, "reviewedBy":reviewer[:80],
        "reviewedAt":reviewed_at.isoformat(),
        "publisherOriginalUrl":publisher_url,
        "publisherFirstPublishedAt":publisher_first.isoformat(),
        "publisherPublicationTimeVerifiedByHuman":True,
        "rssTimestampUsedForChronology":False,
        "evidenceReason":notes[:1500],
        "primarySourceType":row.get("primarySourceType") if verdict!="N" else None,
        "primarySourceUrl":row.get("primarySourceUrl") if verdict!="N" else None,
        "primaryPublishedAt":row.get("primaryPublishedAt") if verdict!="N" else None,
        "publicTraceOverlap":row.get("publicTraceOverlap") if verdict!="N" else "none",
        "humanEvidenceAssessment":True,
        "mediaFulltextReviewed":True,
        "priorPublicTraceProvenExhaustive":False,
    }


def build(press, reviews=None, *, now=None, max_candidates=400, history=None,
          evidence_priority_ids=None):
    now=now or datetime.now(KST)
    if now.utcoffset() is None:raise ValueError("need_timezone")
    if not isinstance(press,dict) or press.get("status")!="observed_domestic_press_index_not_complete_coverage":
        raise ValueError("press_index_missing_or_malformed")
    if not isinstance(press.get("items"),list) or len(press["items"])>MAX_ARTICLES:
        raise ValueError("press_index_records_invalid")
    if press.get("itemCount")!=len(press["items"]):
        raise ValueError("press_index_count_mismatch")
    if not 1<=max_candidates<=600:raise ValueError("sample_cap")
    if reviews is not None and (not isinstance(reviews,list) or len(reviews)>MAX_ARTICLES):
        raise ValueError("invalid_review_sheet")
    if evidence_priority_ids is not None and (
        not isinstance(evidence_priority_ids,(list,tuple,set))
        or len(evidence_priority_ids)>600
        or any(not isinstance(x,str) or
               not re.fullmatch("[0-9a-f]{24}",x)
               for x in evidence_priority_ids)):
        raise ValueError("invalid_evidence_priority_ids")
    history_rows=[]
    if history is not None:
        if (not isinstance(history,dict)
            or history.get("status")!="historical_industry_exclusive_rss_partial_index"
            or not isinstance(history.get("items"),list)
            or not isinstance(history.get("itemCount"),int)
            or history["itemCount"]!=len(history["items"])
            or history["itemCount"]>8_000
            or history.get("allDomesticIndustryExclusivesCovered") is not False
            or history.get("confirmedScoops")!=0
            or not isinstance(history.get("windowHealth"),dict)):
            raise ValueError("historical_exclusive_index_invalid_preserve_previous")
        history_rows=history["items"]
        if any(not isinstance(x,dict) or x.get("fulltextReviewed") is not False
               or x.get("rssIndexedHeadlineOnly") is not True
               or x.get("publisherOriginalUrlVerified") is not False
               or not isinstance(x.get("id"),str)
               or not re.fullmatch("[0-9a-f]{24}",x["id"])
               or aware(x.get("published")) is None
               for x in history_rows):
            raise ValueError("invalid_historical_rss_index_row")
    labelled={}
    for row in reviews or []:
        if not isinstance(row,dict) or not isinstance(row.get("articleId"),str):
            raise ValueError("malformed_review_id")
        aid=row["articleId"]
        if aid in labelled:raise ValueError("duplicate_human_verdict")
        labelled[aid]=row
    # Never equate a 72-hour article index with a one-year press census.
    # Historical Google RSS observations are a second, incomplete source.
    # Prefer the independently collected press record when the same URL is
    # present in both, preserving stable article IDs for human review sheets.
    all_candidates={row["id"]:row for row in history_rows if candidate(row)}
    for row in press["items"]:
        if candidate(row):
            all_candidates[row["id"]]=row
    observed_by_date=sorted(all_candidates.values(),
                  key=lambda r:(r["published"],r["id"]),reverse=True)
    # A rolling top-400 newsroom digest must not permanently hide manually
    # investigated historical records as more recent headlines accumulate.
    # Only pin IDs still present in verified ingested press history; no
    # synthetic articles or undocumented source links are introduced.
    priority=set(evidence_priority_ids or ())
    priority.update(labelled)
    selected_ids={row["id"] for row in observed_by_date if row["id"] in priority}
    if len(selected_ids)>max_candidates:
        raise ValueError("reviewed_or_curated_rows_exceed_display_capacity")
    priority_rows=[row for row in observed_by_date if row["id"] in selected_ids]
    other_rows=[row for row in observed_by_date if row["id"] not in selected_ids]
    sample=(priority_rows+other_rows[:max_candidates-len(priority_rows)])
    sample=sorted(sample,key=lambda r:(r["published"],r["id"]),reverse=True)
    items=[]
    for row in sample:
        proof=validate_review(labelled[row["id"]],row) if row["id"] in labelled else None
        items.append({
            "articleId":row["id"],"title":row["title"],
            "published":row["published"],
            "sourceName":row["sourceName"],
            "articleUrl":row["url"],
            "companies":list(row.get("companies") or [])[:8],
            "kind":kind_for(row["title"]),
            "publicTraceClass":proof["verdict"] if proof else "U",
            "humanReviewStatus":"verified_comparison" if proof else "not_reviewed_or_invalid_evidence",
            "primaryEvidence":proof,
            "historicalSearchHeadlineOnly":row.get("rssIndexedHeadlineOnly") is True,
            "publisherOriginalUrlVerifiedByCollector":False,
            "confirmedExclusive":False,
            "scoopAcquiredBeforeStory":False,
            "warning":"언론의 단독 표기는 원자료의 독점성 증명 아님; Y/P/N은 기사 전문 및 선행 원자료를 비교한 경우에만 인정",
        })
    valid=[x for x in items if x["primaryEvidence"] is not None]
    by_type={}
    for typ in sorted({x["kind"] for x in items}):
        group=[x for x in items if x["kind"]==typ]
        reviewed=[x for x in group if x["primaryEvidence"] is not None]
        counts=Counter(x["publicTraceClass"] for x in reviewed)
        by_type[typ]={
            "articlesObserved":len(group),"reviewed":len(reviewed),
            "Y":counts["Y"],"P":counts["P"],"N":counts["N"],
            "unreviewed":len(group)-len(reviewed),
            "measuredSourceReach": (
                {"anyPublicTraceNumerator":counts["Y"]+counts["P"],
                 "exactFactNumerator":counts["Y"],
                 "reviewedDenominator":len(reviewed),
                 "sampleUnrepresentativeCaution":True}
                if len(reviewed)>=20 else None),
        }
    sources=Counter(x["primaryEvidence"]["primarySourceType"] for x in valid
                    if x["publicTraceClass"] in ("Y","P"))
    return {
        "status":STATUS,"generatedAt":now.astimezone(KST).isoformat(timespec="seconds"),
        "pressIndexGeneratedAt":press.get("generatedAt"),
        "pressIndexSeedOnly":press.get("seedOnly") is True,
        "historicalSearchIndexAt":(history.get("generatedAt") if history else None),
        "historicalSearchIndexStatus":(history.get("status") if history else "not_connected"),
        "historicalSearchObservedRows":len(history_rows),
        "historicalSearchAllSourcesChecked":False,
        "historicalSearchFailuresInLastRun":(history.get("failedWindowsThisRun") if history else None),

        "pressIndexObservationIncomplete":True,
        "targetHistoricalExclusiveArticles":400,
        "totalObservedExclusiveHeadlines":len(sample),
        "availableObservedExclusiveHeadlinesBeforeCap":len(observed_by_date),
        "candidateDisplayLimit":max_candidates,
        "evidencePriorityObservedItemsRetained":len(selected_ids),
        "evidencePriorityIdsNotObserved":len(priority-set(all_candidates)),
        "sampleIncompleteBecauseOfCap":len(observed_by_date)>max_candidates,
        "humanReviewedYPN":len(valid),
        "unreviewedU":len(sample)-len(valid),
        "couldMeasureReach":len(valid)>=30,
        "reliablePopulationReachEstimated":False,
        "Y":sum(x["publicTraceClass"]=="Y" for x in valid),
        "P":sum(x["publicTraceClass"]=="P" for x in valid),
        "N":sum(x["publicTraceClass"]=="N" for x in valid),
        "byType":by_type,
        "verifiedPublicSourceCategories":dict(sorted(sources.items())),
        "confirmedScoops":0,
        "approvedArticles":0,
        "warning":"국내 산업 [단독] 전체 표본 아님. 자동 발견은 U 기준선일 뿐; 소스별 도달률 및 향후 수집기 우선순위는 수백 편의 Y/P/N 사람 검증 전 확정 불가.",
        "items":items,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--press",default="digests/press_coverage_index_latest.json")
    p.add_argument("--history",default="digests/historical_exclusive_press_index_latest.json")
    p.add_argument("--reviews",default="data/reverse_trace_verified_labels.json")
    p.add_argument("--original-leads",default="data/reverse_trace_primary_original_leads.json")
    p.add_argument("--output",default="digests/reverse_trace_latest.json")
    args=p.parse_args()
    press=json.loads(Path(args.press).read_text(encoding="utf-8"))
    sheet=json.loads(Path(args.reviews).read_text(encoding="utf-8"))
    if sheet.get("status")!="reviewer_approved_reverse_trace_labels" or not isinstance(sheet.get("items"),list):
        raise ValueError("invalid_human_review_sheet")
    history_path=Path(args.history)
    history=(json.loads(history_path.read_text(encoding="utf-8"))
             if history_path.exists() else None)
    # Invoked as 'python scripts/exclusive_reverse_trace.py' by Auto Desk.
    # A sibling import works regardless of project-root PYTHONPATH.
    from reverse_trace_source_leads import attach_primary_original_leads
    leads=json.loads(Path(args.original_leads).read_text(encoding="utf-8"))
    # Validation belongs before priority selection: a forged curation file
    # must never force arbitrary article IDs into the prominent sample.
    from reverse_trace_source_leads import verify_curated_lead
    if (not isinstance(leads,dict) or
        not isinstance(leads.get("items"),list) or
        any(not verify_curated_lead(row) for row in leads["items"])):
        raise ValueError("invalid_curated_source_priorities")
    pinned=[row["articleId"] for row in leads["items"]]
    result=attach_primary_original_leads(
        build(press,sheet["items"],history=history,
              evidence_priority_ids=pinned),leads)
    dest=Path(args.output)
    dest.parent.mkdir(parents=True,exist_ok=True)
    tmp=dest.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    tmp.replace(dest)
    print("reverse trace: observed",[result["totalObservedExclusiveHeadlines"]],
          "human reviewed",result["humanReviewedYPN"],"confirmed scoops 0")


if __name__=="__main__":
    main()
