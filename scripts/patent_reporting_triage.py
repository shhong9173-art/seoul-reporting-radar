"""Reporter-feedback-aware patent TRIAGE, not automatic exclusivity or approval.

Inputs are current, provenance-matched KIPRIS desk + DART reference scan,
append-only PUBLIC fact-checks and separate editorial outcome decisions.
Only human-labelled outcomes can move a candidate into editorial-review stage.
Quality percentages are NULL when the current eligible final sample is empty.
These are sample outcomes, not predictions or trained model scores.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

KST=timezone(timedelta(hours=9))
PATENT=re.compile(r"^10\d{11}$")
CHECK_KINDS=("prior_coverage","company_response","actual_application",
             "industry_impact","reporting_angle")
FINAL_POS={"worth_reporting","published"}
FINAL_NEG={"already_reported","wrong_beat","unsupported_angle","low_value"}
PENDING={"needs_reporting"}
EXCLUDED=FINAL_NEG|{"published"}
VALID=FINAL_POS|FINAL_NEG|PENDING


def public_url(url):
    try:
        p=urlsplit(str(url or ""))
        return p.scheme=="https" and bool(p.hostname) and not p.username and not p.password
    except ValueError:
        return False


def latest_editorial(events):
    out={}
    for e in events:
        if (isinstance(e,dict) and PATENT.fullmatch(str(e.get("publicationNumber") or ""))
            and e.get("decision") in VALID):
            # Only the latest *accepted* append-only decision for each
            # official number counts; never sum superseded decisions.
            out[e["publicationNumber"]]=e
    return out


def latest_checks(events):
    out={}
    for e in events:
        if (not isinstance(e,dict)
            or not PATENT.fullmatch(str(e.get("publicationNumber") or ""))
            or e.get("checkType") not in CHECK_KINDS
            or e.get("result") not in ("verified_public","contradicted_public","needs_check")):
            continue
        if e["result"]!="needs_check" and not public_url(e.get("evidenceUrl")):
            continue  # No confirmed PUBLIC-document review without cited URL.
        out[(e["publicationNumber"],e["checkType"])]=e
    return out


def rate(n,total):
    return round(n/total,4) if total else None


def classify(lead,cross,verdict,checks):
    blocking=list(lead.get("cautionFlags") or [])
    if lead.get("retrospectiveKnownCase") and "known_article_replay" not in blocking:
        blocking.append("known_article_replay")
    if verdict in EXCLUDED:
        blocking.append("human_negative_or_already_published")
    if any(check.get("result")=="contradicted_public" for key,check in checks.items()
           if key in ("actual_application","industry_impact","reporting_angle")):
        blocking.append("public_record_conflicts_with_claim")
    if blocking:
        return "hold_for_review",blocking
    if not lead.get("mediaReview",{}).get("checked"):
        return "media_check_first",blocking
    if verdict=="worth_reporting" and all(
       checks.get(k,{}).get("result")=="verified_public" for k in CHECK_KINDS):
        return "reporter_editorial_review",blocking
    if verdict=="worth_reporting":
        return "reporter_follow_up",blocking
    if cross.get("independentDartTechnicalOverlap"):
        return "official_context_check_company",blocking
    return "source_review_company_call",blocking


def build(desk,cross,editorial,checks,quality=None,now=None,max_selected=5):
    now=now or datetime.now(KST)
    if not 1<=max_selected<=5:raise ValueError("Top-N must be 1..5")
    if (desk.get("status")!="research_priorities_only"
        or not desk.get("generatedAt") or not isinstance(desk.get("reviewQueue"),list)
        or not isinstance(cross.get("reviews"),list)
        or cross.get("deskSourceGeneratedAt")!=desk.get("generatedAt")):
        raise ValueError("KIPRIS desk and DART cross-check snapshots mismatched")
    if not isinstance(editorial.get("reviews"),list) or not isinstance(checks.get("checks"),list):
        raise ValueError("Missing user-generated evidence ledgers")
    review_by=latest_editorial(editorial["reviews"])
    check_by=latest_checks(checks["checks"])
    cross_by={r.get("publicationNumber"):r for r in cross["reviews"] if isinstance(r,dict)}
    rows=[]
    current_ids=set()
    for lead in desk["reviewQueue"]:
        pub=str(lead.get("publicationNumber") or "")
        if not PATENT.fullmatch(pub):continue
        if pub not in cross_by:
            raise ValueError("Missing cross-check record for current patent "+pub)
        current_ids.add(pub)
        crossrow=cross_by[pub]
        assigned={k:check_by[(pub,k)] for k in CHECK_KINDS if (pub,k) in check_by}
        reviewed=sum(x.get("result")=="verified_public" for x in assigned.values())
        contradicted=sum(x.get("result")=="contradicted_public" for x in assigned.values())
        incomplete=[k for k in CHECK_KINDS if assigned.get(k,{}).get("result")!="verified_public"]
        event=review_by.get(pub,{})
        verdict=event.get("decision","not_reviewed")
        stage,flags=classify(lead,crossrow,verdict,assigned)

        # Process priority; based on documented desk rank and voluntary
        # public reporter actions. NEVER construed as probability of exclusivity.
        score=int(lead.get("evidencePriorityScore") or 0)
        score+=min(10,2*reviewed)
        score+=8 if verdict=="worth_reporting" else 0
        score+=4 if crossrow.get("independentDartTechnicalOverlap") else 0
        score-=10*contradicted
        score-=18 if stage=="media_check_first" else 0
        score-=200 if flags else 0
        reporter_checks={k:{
            "result":assigned.get(k,{}).get("result","not_reviewed"),
            "publicEvidenceUrl":assigned.get(k,{}).get("evidenceUrl") if
                public_url(assigned.get(k,{}).get("evidenceUrl")) else None,
        } for k in CHECK_KINDS}
        if stage=="media_check_first":
            next_step="선행보도·회사 발표 원문을 먼저 확인"
        elif stage=="hold_for_review":
            next_step="기보도·반증·부정 판정 근거를 다시 확인하고 발제 보류"
        elif stage=="reporter_editorial_review":
            next_step="공개 근거 다섯 항목과 기사 야마를 편집자가 최종 검토(출고 승인 아님)"
        elif "company_response" in incomplete:
            next_step="업체 직접 답변과 기술 적용 여부 확인"
        elif "actual_application" in incomplete:
            next_step="해당 특허의 실제 차종·공정 적용 확인"
        elif "industry_impact" in incomplete:
            next_step="효과 수치·산업 영향 공식 근거 확인"
        else:
            next_step="기사 야마·기보도·반론 확인 후 최종 발제 검토"
        rows.append({
            "publicationNumber":pub,
            "title":lead.get("title"),"publicationDate":lead.get("publicationDate"),
            "coveredCompanies":lead.get("coveredCompanies") or [],
            "topic":lead.get("topic"),
            "evidencePriorityScore":score,
            "baselineScore":lead.get("evidencePriorityScore"),
            "stage":stage,"blockingReasons":flags,
            "editorialOutcome":verdict,
            "publicCheckCount":reviewed,
            "publicContradictionCount":contradicted,
            "publicCheckStatuses":reporter_checks,
            "missingChecks":incomplete,
            "technicalOverlapCount":len(crossrow.get("independentDartTechnicalOverlap") or []),
            "sameCompanyBackgroundCount":len(crossrow.get("sameIssuerBackgroundSources") or []),
            "companyReplyIndependentVerification":False,
            "patentBusinessIdentityProven":False,
            "exclusiveProven":False,
            "approvedForPublication":False,
            "nextStep":next_step
        })
    # Relative preference only in a screened, nonblocked review queue.
    order=sorted(rows,key=lambda r:(-r["evidencePriorityScore"],
                  -int(r.get("publicationDate") or 0),r["publicationNumber"]))
    chosen=[r for r in order if r["stage"]!="hold_for_review"
           and r["stage"]!="media_check_first"][:max_selected]
    current_labeled=[review_by[x] for x in current_ids if x in review_by]
    finalized=[x for x in current_labeled if x["decision"] in FINAL_POS|FINAL_NEG]
    positives=sum(x["decision"] in FINAL_POS for x in finalized)
    negatives=len(finalized)-positives
    # Cross-check precomputed quality provenance; if absent or stale, the
    # derived sample remains valid but is explicitly shown as locally recomputed.
    metrics_coherent=bool(
        quality and quality.get("officialSourceGeneratedAt")==desk.get("officialSourceGeneratedAt")
        and quality.get("storySourceGeneratedAt")==desk.get("storySourceGeneratedAt")
        and quality.get("humanReviewEvents")==len(editorial["reviews"]))
    status=("unmeasured_no_final_human_reviews" if not finalized else
            "small_convenience_sample" if len(finalized)<20 else
            "editorial_selection_sample_only")
    return {
        "generatedAt":now.isoformat(timespec="seconds"),
        "deskSourceGeneratedAt":desk["generatedAt"],
        "crossSourceGeneratedAt":cross.get("generatedAt"),
        "editorialMetricsMatched":metrics_coherent,
        "totalCandidates":len(rows),
        "screenedCandidates":sum(r["stage"] not in ("hold_for_review","media_check_first") for r in rows),
        "holdCandidates":sum(r["stage"]=="hold_for_review" for r in rows),
        "unsearchedMediaCandidates":sum(r["stage"]=="media_check_first" for r in rows),
        "humanEditorialReviewsCurrent":len(current_labeled),
        "finalHumanSample":len(finalized),
        "humanPositiveFinal":positives,"humanNegativeFinal":negatives,
        "observedEditorialHitRate":rate(positives,len(finalized)),
        "observedFalsePositiveRate":rate(negatives,len(finalized)),
        "metricsStatus":status,
        "rankingPolicy":"근거 점수+공개 URL 첨부한 기자 확인 진행+수동 기사 가치 판정. 자동학습/단독 확률 아님",
        "selectionCaveat":"자발적으로 검토한 기사 후보에 대한 편의표본. 표본 0건=측정 불가; 일반화 정확도/단독 검출률 아님",
        "shortlist":chosen,
        "reviewQueue":order,
        "approvedArticles":0,"confirmedExclusives":0,
        "notes":"브라우저 로컬 체크 상태는 서버로 전송되지 않아 본 점수에 반영되지 않음. 공개 URL 사실의 내용·업체 실제 적용은 독립 검증 미완료.",
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--desk",default="digests/patent_desk_latest.json")
    p.add_argument("--cross",default="digests/patent_cross_evidence_latest.json")
    p.add_argument("--editorial",default="data/patent_editorial_reviews.json")
    p.add_argument("--checks",default="data/patent_reporting_checks.json")
    p.add_argument("--quality",default="digests/patent_quality_latest.json")
    p.add_argument("--out",default="digests/patent_reporting_triage_latest.json")
    a=p.parse_args()
    def load(f):return json.loads(Path(f).read_text(encoding="utf-8"))
    try:quality=load(a.quality)
    except (OSError,ValueError):quality={}
    report=build(load(a.desk),load(a.cross),load(a.editorial),load(a.checks),quality)
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    tmp=out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    tmp.replace(out)
    print("KIPRIS reporting triage",report["totalCandidates"],"shortlist",
          len(report["shortlist"]),"human-final",report["finalHumanSample"],
          "observed hit rate",report["observedEditorialHitRate"])


if __name__=="__main__":main()
