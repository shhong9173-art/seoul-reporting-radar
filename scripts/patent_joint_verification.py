"""Conservative KIPRIS newsroom evidence queue for recent cross-sector cofilings.

A verified official co-applicant list is NOT an announced collaboration,
business agreement, applied product, technical novelty, or scoop.
Press-index zero is NOT absence of prior reporting.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST=timezone(timedelta(hours=9))
PUB=re.compile(r"^10\d{11}$")
DAY=re.compile(r"^20\d{6}$")
UTC_THRESHOLD=timedelta(hours=24)

def as_date(value):
    if not isinstance(value,str) or not DAY.fullmatch(value):
        raise ValueError("missing_official_publication_date")
    try:return datetime.strptime(value,"%Y%m%d").date()
    except ValueError as e:raise ValueError("invalid_publication_date") from e

def timestamp(value):
    try:
        t=datetime.fromisoformat(str(value))
        if t.utcoffset() is None:raise ValueError()
        return t
    except (ValueError,TypeError) as e:
        raise ValueError("invalid_source_timestamp") from e

def snapshot_gate(official,deep,story,claims):
    if not all(isinstance(x,dict) for x in (official,deep,story,claims)):
        raise ValueError("source_missing")
    if (official.get("status")!="official_search_completed"
        or official.get("sourceWindowComplete") is not True
        or deep.get("sourceCoverageComplete") is not True
        or deep.get("patentDatasetGeneratedAt")!=official.get("generatedAt")
        or story.get("officialSourceGeneratedAt")!=official.get("generatedAt")
        or story.get("deepSourceGeneratedAt")!=deep.get("generatedAt")
        or claims.get("patentDatasetGeneratedAt")!=official.get("generatedAt")
        or claims.get("deepDatasetGeneratedAt")!=deep.get("generatedAt")
        or not isinstance(deep.get("partnerInvestigations"),list)
        or not isinstance(story.get("investigations"),list)
        or not isinstance(claims.get("reviews"),list)
        or deep.get("confirmedScoops")!=0
        or claims.get("confirmedScoops")!=0):
        raise ValueError("official_patent_snapshot_inconsistent")
    count=deep.get("outsideBeatJointPublications")
    if type(count) is not int or count<0 or count<len(deep["partnerInvestigations"]):
        raise ValueError("invalid_joint_population")
    for data in (official,deep,story,claims):
        timestamp(data.get("generatedAt"))

def identify(row):
    pub=row.get("publicationNumber")
    date=as_date(row.get("publicationDate"))
    partners=row.get("outsideBeatCoApplicants")
    covered=row.get("coveredCompanies")
    applicants=row.get("applicants")
    if (not isinstance(pub,str) or not PUB.fullmatch(pub)
        or not isinstance(partners,list) or not partners
        or not isinstance(covered,list) or not covered
        or not isinstance(applicants,list) or len(applicants)<2
        or row.get("crossOrganizationLead") is not True
        or row.get("jointApplicantGroup") is not True):
        raise ValueError("not_official_outside_beat_cofiled")
    for names in (partners,covered,applicants):
        if any(not isinstance(v,str) or not v.strip() or len(v)>160 for v in names):
            raise ValueError("invalid_patent_applicant")
    if (not set(partners).issubset(set(applicants))
        or any(p in covered for p in partners)):
        raise ValueError("unproven_partner_identity")
    return pub,date

def checked_press(story, now):
    if not isinstance(story,dict):
        return "not_searched_no_zero_claim", None,0,False
    press=story.get("pressCoverage") or {}
    checked_at=story.get("pressCheckedAt")
    queries=press.get("queries")
    if (not isinstance(queries,list) or not queries
        or press.get("completeSearch") is not True
        or not checked_at):
        return "not_searched_no_zero_claim",checked_at,0,False
    when=timestamp(checked_at)
    if when>now+timedelta(minutes=10) or now-when>UTC_THRESHOLD:
        return "index_checked_but_stale_recheck",checked_at,len(queries),bool(press.get("possibleEarlierCoverage"))
    if any(q.get("status") not in ("no_hits","found","results_found","success","searched_with_hits") for q in queries):
        # Some valid search schemas use 'searched' and other explicit statuses.
        # Unknown result enums cannot justify declaring coverage checked.
        return "press_index_status_requires_review",checked_at,len(queries),bool(press.get("possibleEarlierCoverage"))
    if press.get("possibleEarlierCoverage") or any(q.get("articles") for q in queries):
        return "indexed_articles_need_fulltext_review",checked_at,len(queries),True
    return "index_no_hits_not_proof_unreported",checked_at,len(queries),False

def build(official, deep, story, claims, *, now=None, days=3, max_items=30):
    now=now or datetime.now(KST)
    if now.tzinfo is None or not 1<=days<=7 or not 1<=max_items<=100:
        raise ValueError("invalid_review_window")
    snapshot_gate(official,deep,story,claims)
    asof=now.astimezone(KST).date()
    earliest=asof-timedelta(days=days-1)
    story_by={}
    for r in story["investigations"]:
        pub=r.get("publicationNumber")
        if pub and pub not in story_by:story_by[pub]=r
    claim_by={}
    for r in claims["reviews"]:
        pub=r.get("publicationNumber")
        if pub and pub not in claim_by:claim_by[pub]=r
    source_generated=timestamp(official["generatedAt"])
    source_stale=now-source_generated>UTC_THRESHOLD or source_generated>now+timedelta(minutes=10)
    rows=[]
    seen=set()
    for row in deep["partnerInvestigations"]:
        pub,publication_date=identify(row)
        if pub in seen:raise ValueError("duplicate_cofiled_publication")
        seen.add(pub)
        if publication_date>asof:raise ValueError("future_official_publication")
        article=story_by.get(pub)
        claim=claim_by.get(pub)
        if (article and (article.get("publicationDate")!=row["publicationDate"]
             or article.get("title")!=row.get("title"))):
            raise ValueError("mismatched_story_identity")
        application=str(row.get("applicationNumber") or "").replace("-","")
        claim_verified=bool(
            claim and claim.get("claimVerified") is True
            and claim.get("claimSourceVerified") is True
            and claim.get("currentApplication")==application
            and claim.get("publicationNumber")==pub
        )
        if claim and claim.get("publicationNumber")==pub and claim.get("currentApplication")!=application:
            raise ValueError("claim_of_different_application")
        press_status,press_at,press_queries,possible_coverage=checked_press(article,now)
        older=row.get("priorFullTitleCheck") or {}
        if older.get("complete") is True and isinstance(older.get("matches"),list):
            older_status="same_title_patent_found_review" if older["matches"] else "bounded_same_title_not_found_other_prior_unchecked"
        elif "오류" in str(older.get("status") or ""):
            older_status="prior_title_lookup_failed"
        else:
            older_status="not_searched_or_incomplete"
        if possible_coverage or older_status=="same_title_patent_found_review":
            next_check="기존 언론 원문·과거 공개공보와 이 출원의 차이를 먼저 확인"
        elif not claim_verified:
            next_check="공식 출원번호의 독립 청구항을 확인하고 종전 기술과 직접 비교"
        elif press_status!="index_no_hits_not_proof_unreported":
            next_check="기보도·기업 발표 검색을 다시 수행하고 기사 원문 확인"
        else:
            next_check="출입처·외부 공동출원인에 개발 역할, 실제 적용 품목·수치, 사업 계획 직접 확인"
        rows.append({
            "publicationNumber":pub,
            "applicationNumber":application or None,
            "publicationDate":row["publicationDate"],
            "title":str(row.get("title") or "")[:250],
            "coveredCompanies":list(row["coveredCompanies"]),
            "outsideBeatCoApplicants":list(row["outsideBeatCoApplicants"]),
            "officialCoApplicants":list(row["applicants"]),
            "isRecentPublication":earliest<=publication_date<=asof,
            "observedInCurrentSource":row.get("previouslyObserved") is True,
            "sourceTitle":str(row.get("title") or "")[:250],
            "sourcePublicationDate":row["publicationDate"],
            "claim1Status":"official_claim1_verified_text_only_no_novelty_certification" if claim_verified else "claim1_not_verified_for_this_application",
            "claim1Excerpt":str(claim.get("claim1Excerpt") or "")[:260] if claim_verified else None,
            "claim1PriorComparisons":len(claim.get("priorComparisons") or []) if claim_verified else None,
            "priorSameTitleStatus":older_status,
            "pressIndexStatus":press_status,
            "pressCheckedAt":press_at,
            "pressQueriesCount":press_queries,
            "possiblePriorCoverage":possible_coverage,
            "companyApplicationVerified":False,
            "industrialImpactVerified":False,
            "partnershipContractVerified":False,
            "scoopConfirmed":False,
            "approvedForPitch":False,
            "nextReportingQuestion":next_check,
            "verificationClass":"published_joint_patent_research_only"
        })
    rows.sort(key=lambda x:(not x["isRecentPublication"],-int(x["publicationDate"]),not x["possiblePriorCoverage"],x["publicationNumber"]))
    recent=[r for r in rows if r["isRecentPublication"]]
    older=[r for r in rows if not r["isRecentPublication"]]
    total=deep["outsideBeatJointPublications"]
    result={
        "generatedAt":now.isoformat(timespec="seconds"),
        "officialSourceGeneratedAt":official["generatedAt"],
        "deepSourceGeneratedAt":deep["generatedAt"],
        "storySourceGeneratedAt":story["generatedAt"],
        "claimSourceGeneratedAt":claims["generatedAt"],
        "status":"historical_source_stale_recollect_before_current_pitch" if source_stale else "official_source_window_verified_not_scoop",
        "windowDays":days,
        "windowStart":earliest.strftime("%Y%m%d"),
        "windowEnd":asof.strftime("%Y%m%d"),
        "sourceAgeHours":round((now-source_generated).total_seconds()/3600,1),
        "officialSourceStale":source_stale,
        "officialOutsideBeatJointCount":total,
        "jointRecordsRepresented":len(rows),
        "unrepresentedOfficialJointRecords":total-len(rows),
        "recentJointInRepresentedSample":len(recent),
        "recentCoverageComplete":total==len(rows) and not source_stale,
        "confirmedScoops":0,
        "approvedArticles":0,
        "warning":"Only named official coapplicants are proven; claim novelty, fulltext prior reporting, role/contract, actual vehicle/plant application and commercial impact are NOT verified. Source-age or unrepresented records must never be counted as zero discoveries.",
        "recentResearchQueue":recent[:max_items],
        "olderReferenceQueue":older[:min(12,max_items)]
    }
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--official",default="digests/patent_hunt_latest.json")
    p.add_argument("--deep",default="digests/patent_deep_latest.json")
    p.add_argument("--story",default="digests/patent_story_latest.json")
    p.add_argument("--claims",default="digests/patent_claim_review_latest.json")
    p.add_argument("--output",default="digests/patent_joint_verification_latest.json")
    args=p.parse_args()
    read=lambda path:json.loads(Path(path).read_text(encoding="utf-8"))
    result=build(read(args.official),read(args.deep),read(args.story),read(args.claims))
    path=Path(args.output)
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(".tmp")
    tmp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    tmp.replace(path)
    print("Joint-patent evidence:",result["status"],"represented",result["jointRecordsRepresented"],
          "of",result["officialOutsideBeatJointCount"],"recent",result["recentJointInRepresentedSample"],
          "unrepresented",result["unrepresentedOfficialJointRecords"],"confirmed scoops 0")

if __name__=="__main__":main()
