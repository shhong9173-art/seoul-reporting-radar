"""Link *located* first-party originals to historical '[단독]' research items.

A manually located original web URL and calendar date are NOT a verified
publication timestamp, exact fact overlap, original publisher story fulltext,
prior press coverage or an automatic Y/P/N verdict.
"""
from __future__ import annotations
import re
from datetime import date, datetime
from urllib.parse import parse_qs, urlsplit

STATUS="curated_official_original_candidates_chronology_unverified"
ALLOWED_HOST_PATH={
    ("news.samsungsdi.com","/ko/articleView"),
    ("www.sec.gov","/Archives/edgar/data/1844862/000110465925104388/0001104659-25-104388-index.html"),
}
ARTICLE_ID=re.compile(r"[0-9a-f]{24}\Z")
MAX_ITEMS=2000
MAX_LINKED=400


def official_candidate_url(value):
    if not isinstance(value,str) or len(value)>1200:
        return False
    try:
        u=urlsplit(value)
        if (u.scheme!="https" or not u.hostname or u.username or u.password
            or u.port is not None or u.fragment
            or (u.hostname,u.path) not in ALLOWED_HOST_PATH):
            return False
        if (u.hostname,u.path)==("news.samsungsdi.com","/ko/articleView"):
            return parse_qs(u.query)=={"seq":["371"]}
        if u.hostname=="www.sec.gov":
            return not u.query
    except ValueError:
        return False
    return False


def _date(value):
    if not isinstance(value,str) or not re.fullmatch(r"20\d{2}-\d{2}-\d{2}",value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _published_day(value):
    if not isinstance(value,str):
        return None
    try:
        dt=datetime.fromisoformat(value.replace("Z","+00:00"))
        if dt.utcoffset() is None:
            return None
        return dt.date()
    except (ValueError,TypeError,OverflowError):
        return None


def verify_supporting_sec_original(row):
    if not isinstance(row,dict):
        return False
    accepted=row.get("officialAcceptanceAt")
    try:
        clock=datetime.fromisoformat(accepted)
        verified_time=(clock.utcoffset() is not None
                       and clock.date()==_date(row.get("officialDocumentDate"))
                       and clock.isoformat()=="2025-10-30T16:15:52-04:00")
    except (ValueError,TypeError,OverflowError,AttributeError):
        verified_time=False
    return (
        row.get("issuer")=="Solid Power, Inc."
        and isinstance(row.get("officialDocumentTitle"),str)
        and 15<=len(row["officialDocumentTitle"])<=200
        and row.get("sourceType")=="regulatory_filing"
        and row.get("officialUrl")==
          "https://www.sec.gov/Archives/edgar/data/1844862/000110465925104388/0001104659-25-104388-index.html"
        and official_candidate_url(row.get("officialUrl"))
        and verified_time
        and all(row.get(key) is False for key in (
            "publicFirstAvailabilityTimeVerified",
            "publisherStoryFulltextCompared",
            "sourceFactsMatchedToMediaBody",
            "releasedBeforeStoryVerified",
            "humanYPNAssigned"))
    )


def verify_curated_lead(row):
    if not isinstance(row,dict):
        return False
    article=row.get("articleId")
    issuer=row.get("issuer")
    title=row.get("officialDocumentTitle")
    terms=row.get("articleMustContain")
    dt=_date(row.get("officialDocumentDate"))
    if (not isinstance(article,str) or not ARTICLE_ID.fullmatch(article)
        or not isinstance(issuer,str) or not 2<=len(issuer)<=55
        or not isinstance(title,str) or not 12<=len(title)<=200
        or not isinstance(terms,list) or not 2<=len(terms)<=7
        or any(not isinstance(x,str) or not 2<=len(x)<=30 for x in terms)
        or len(terms)!=len(set(terms)) or dt is None
        or row.get("sourceType")!="company_notice"
        or not official_candidate_url(row.get("officialUrl"))
        or row.get("sourceLocatedOnOfficialDomain") is not True
        or any(row.get(key) is not False for key in (
            "officialPublicationClockVerified",
            "publisherArticleFirstPublishedClockVerified",
            "articleFulltextCompared",
            "officialFactOverlapIndependentlyVerified",
            "primaryReleasedBeforeStoryVerified",
            "humanYPNAssigned"))):
        return False
    supporting=row.get("supportingOfficialOriginals",[])
    if (not isinstance(supporting,list) or len(supporting)>4 or
        any(not verify_supporting_sec_original(x) for x in supporting) or
        len({x["officialUrl"] for x in supporting})!=len(supporting) or
        any(x["officialUrl"]==row["officialUrl"] for x in supporting)):
        return False
    return True


def _subject_platforms(kind):
    # These are search *starting points*, not discovered original documents.
    return {
        "리콜·안전":["자동차리콜센터","국토교통부 리콜 공표","미국 NHTSA 보고서"],
        "공장·생산·투자":["DART 공시","지방자치단체 산업단지·인허가 공고","회사 공시자료"],
        "정책·규제·입법":["국회 의안정보·회의록","관보·행정예고","정부 공개 보도자료"],
        "수주·입찰":["DART 계약공시","나라장터 입찰·낙찰 자료","발주처 공개 계약자료"],
        "노사·인사":["고용노동부 공표","노동위원회 판정 공개자료","공식 회사 공시"],
        "자본·지배구조":["DART 공시","해외법인 등기·상업등기 원본","주주총회 공고"],
        "회생·소송":["법원 공개 사건·판결문","DART 소송 관련 공시"],
        "특허·상표":["KIPRIS 공개공보","WIPO 공개특허","KIPO 공개공보"],
        "통상·관세":["산업통상자원부 무역구제 공고","미국 상무부·ITC 공고","EU 공식 관보"],
        "신차·인증·허가":["국토교통부·환경부 형식승인 자료","자동차리콜센터","제조사 공개 제원"],
    }.get(kind,["회사 공식 공개자료","관계부처 공고","DART 공시"])


def source_research_checklist():
    return [
        "기사를 보도한 언론사의 실제 본문과 최초 게재 시각 확인",
        "공식 원문의 접수·게시·공개 시각과 이후 정정 이력 확인",
        "기사의 핵심 숫자·사실이 공식 원문에 실제 있었는지 문장별 대조",
        "보도 전 다른 국내 언론과 공개자료의 선행 언급 여부 확인",
        "사람이 Y/P/N 판정 근거와 원자료 링크를 리뷰 시트에 작성",
    ]


def attach_primary_original_leads(trace,leads):
    """Pure attachment; rejects bad curation; retains unknown article verdicts."""
    if (not isinstance(trace,dict)
        or trace.get("status")!="automotive_industry_exclusive_reverse_trace_unverified_candidates"
        or not isinstance(trace.get("items"),list)
        or trace.get("totalObservedExclusiveHeadlines")!=len(trace["items"])
        or trace.get("reliablePopulationReachEstimated") is not False
        or not isinstance(leads,dict) or leads.get("status")!=STATUS
        or leads.get("confirmedScoops")!=0
        or leads.get("humanYPNFromLeads")!=0
        or not isinstance(leads.get("lastCuratedAt"),str)
        or not isinstance(leads.get("items"),list)
        or len(leads["items"])>MAX_ITEMS):
        raise ValueError("invalid_official_candidate_source_or_trace")
    lead_by_id={}
    for row in leads["items"]:
        if not verify_curated_lead(row):
            raise ValueError("unsafe_curated_official_original_candidate")
        article=row["articleId"]
        if article in lead_by_id:
            raise ValueError("duplicate_official_original_candidate_article")
        lead_by_id[article]=row
    attached=0
    actual_docs=set()
    updated_items=[]
    mismatched=[]
    for item in trace["items"]:
        if not isinstance(item,dict) or not isinstance(item.get("articleId"),str):
            raise ValueError("invalid_trace_article")
        record={**item}
        record["researchSourcePlatformsSuggested"]=_subject_platforms(item.get("kind"))
        record["sourcePlatformSuggestionsOnly"]=True
        lead=lead_by_id.get(item["articleId"])
        if lead:
            title=item.get("title")
            companies=item.get("companies")
            story_day=_published_day(item.get("published"))
            source_day=_date(lead["officialDocumentDate"])
            # Candidate linkage is allowed only on exact article id, the
            # full issuer identity and multiple words actually on the title.
            if (not isinstance(title,str) or not isinstance(companies,list)
                or lead["issuer"] not in companies
                or any(t.casefold() not in title.casefold()
                       for t in lead["articleMustContain"])
                or story_day is None or source_day is None
                or source_day>story_day):
                mismatched.append(item["articleId"])
            else:
                record["locatedOfficialOriginalCandidate"]={
                    "status":"dated_company_original_candidate_not_chronology_verified",
                    "issuer":lead["issuer"],
                    "documentTitle":lead["officialDocumentTitle"],
                    "documentDay":lead["officialDocumentDate"],
                    "documentUrl":lead["officialUrl"],
                    "sourceType":lead["sourceType"],
                    "publicationClockVerified":False,
                    "storyPublisherClockVerified":False,
                    "articleFulltextCompared":False,
                    "documentAndStoryFactsCompared":False,
                    "releasedBeforeStoryVerified":False,
                    "sameDayDoesNotProveEarlierRelease":source_day==story_day,
                    "priorDomesticMediaFulltextCompared":False,
                    "automaticYPNDecision":False,
                    "warning":"공식 링크와 문서 날짜 확인만. 첫 게시 시각·기사 원문·이전 보도와 정확한 사실관계 미검증. Y/P/N을 자동 확정하지 않음",
                }
                extra=[]
                for other in lead.get("supportingOfficialOriginals",[]):
                    foreign_date=_date(other["officialDocumentDate"])
                    if foreign_date is None or foreign_date>story_day:
                        # Retain a valid curated earlier source even if a
                        # mismatched RSS date is observed: do not claim a link.
                        continue
                    extra.append({
                        "status":"official_us_sec_filing_original_candidate_not_article_verified",
                        "issuer":other["issuer"],
                        "documentTitle":other["officialDocumentTitle"],
                        "documentDay":other["officialDocumentDate"],
                        "documentUrl":other["officialUrl"],
                        "sourceType":other["sourceType"],
                        "secAcceptedAtOfficialEastern":other["officialAcceptanceAt"],
                        "secAcceptedAtIsNotPressFirstPublishedAt":True,
                        "documentCalendarDayEarlierThanIndexedRssDay":
                            foreign_date<story_day,
                        "firstPublicAvailabilityClockVerified":False,
                        "publisherStoryFirstPublicationClockVerified":False,
                        "articleFulltextCompared":False,
                        "sourceAndStoryFactsDirectlyMatched":False,
                        "releasedBeforeStoryVerified":False,
                        "automaticYPNDecision":False,
                        "warning":"미국 SEC 공식 접수 날짜·수리시각 확인. 언론사 기사의 최초 출고시각 및 핵심 사실 일치·국내 선행보도 미검증. Y/P/N 확정 아님",
                    })
                    actual_docs.add(other["officialUrl"])
                if extra:
                    record["locatedSupportingOfficialOriginals"]=extra
                actual_docs.add(lead["officialUrl"])
                attached+=1
        updated_items.append(record)
    return {
        **trace,
        "items":updated_items,
        "locatedOriginalCandidateArticleCount":attached,
        "distinctLocatedOfficialOriginalDocuments":len(actual_docs),
        "locatedSupplementaryForeignOriginalReferences":sum(
            len(row.get("locatedSupportingOfficialOriginals",[]))
            for row in updated_items),
        "secOfficialAcceptanceTimestampChecked":bool(
            any(row.get("locatedSupportingOfficialOriginals") for row in updated_items)),
        "curatedOfficialLeadRows":len(lead_by_id),
        "staleOrUnmatchedCuratedLeadRows":len(lead_by_id)-attached,
        "staleLinkageCandidateIds":sorted(mismatched),
        "primaryDocumentPublishedBeforeMediaVerifiedCount":0,
        "pressFulltextMatchedToOfficialOriginalCount":0,
        "curatedLeadSourceAt":leads["lastCuratedAt"],
        "curatedLeadStatus":STATUS,
        "sourceResearchChecklist":source_research_checklist(),
        "sourcePrioritizationEvidenceSufficient":False,
        "warning":trace["warning"]+
            " 공식 원문 후보는 검색 지원용으로만 표시하고, 기사 이전 공개나 Y/P/N의 증명으로 사용하지 않음.",
    }
