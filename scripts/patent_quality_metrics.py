"""Editorial quality metrics for human-graded KIPRIS patent leads.

No manual labels => no hit-rate number. Google News empty results must never
be called exclusive. Known-case replay is NOT scoop recall or early detection.
"""
import argparse
import json
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST=timezone(timedelta(hours=9))
NUMBER=re.compile(r"^10\d{11}$")
FINAL_POSITIVE={"worth_reporting","published"}
FINAL_NEGATIVE={"already_reported","wrong_beat","unsupported_angle","low_value"}
PENDING={"needs_reporting"}
DECISIONS=FINAL_POSITIVE|FINAL_NEGATIVE|PENDING


def latest_by_publication(events):
    latest={}
    for event in events:
        if (not isinstance(event,dict) or
            not NUMBER.fullmatch(str(event.get("publicationNumber") or "")) or
            event.get("decision") not in DECISIONS):
            continue
        # Append-only actions are ordered by accepted review timestamp, not
        # lexicographically by reporter notes or the patent's date.
        key=event["publicationNumber"]
        latest[key]=event
    return latest


def ratio(a,b):
    return round(a/b,4) if b else None


def summarize(story,source,reviews,benchmarks,now=None):
    now=now or datetime.now(KST)
    if (not story.get("generatedAt") or
        story.get("officialSourceGeneratedAt")!=source.get("generatedAt") or
        story.get("sourceWindowComplete") is not True or
        not isinstance(story.get("investigations"),list) or
        not isinstance(source.get("items"),list)):
        raise ValueError("KIPRIS official and story snapshots incomplete or mismatched")
    if not isinstance(reviews.get("reviews"),list):
        raise ValueError("Editorial review ledger must contain a reviews list")
    if not isinstance(benchmarks.get("cases"),list):
        raise ValueError("Historical benchmark requires a cases list")
    rows=story["investigations"]
    active={str(x.get("publicationNumber")):x for x in rows}
    latest=latest_by_publication(reviews["reviews"])
    labeled=[e for e in latest.values() if e["publicationNumber"] in active]
    final=[e for e in labeled if e["decision"] in FINAL_POSITIVE|FINAL_NEGATIVE]
    positive=sum(e["decision"] in FINAL_POSITIVE for e in final)
    negative=len(final)-positive
    breakdown=Counter(e["decision"] for e in labeled)
    by_score={}
    for name,low,high in [("high_70_plus",70,1000),("medium_50_69",50,69),("lower_under_50",0,49)]:
        in_bucket=[x for x in rows if low<=int(x.get("rank") or 0)<=high]
        done=[latest[x["publicationNumber"]] for x in in_bucket
              if x["publicationNumber"] in latest and latest[x["publicationNumber"]]["decision"] in FINAL_POSITIVE|FINAL_NEGATIVE]
        by_score[name]={"candidateCount":len(in_bucket),
                        "finalizedSample":len(done),
                        "positive":sum(e["decision"] in FINAL_POSITIVE for e in done),
                        "observedHitRate":ratio(sum(e["decision"] in FINAL_POSITIVE for e in done),len(done))}
    benchmark_results=[]
    source_pub={str(r.get("publicationNumber")) for r in source["items"]}
    story_pub=set(active)
    seen=set()
    for case in benchmarks["cases"]:
        number=str(case.get("publicationNumber") or "")
        if not NUMBER.fullmatch(number) or number in seen:
            continue
        seen.add(number)
        benchmark_results.append({
            "publicationNumber":number,
            "caseName":str(case.get("caseName") or "")[:130],
            "inOfficialSnapshot":number in source_pub,
            "inReportingLeads":number in story_pub,
            "leadRank":next((i+1 for i,x in enumerate(rows)
                             if x.get("publicationNumber")==number),None),
            "priorToKnownArticle":None,
            "caveat":"기사 보도 전 발견 여부 미검증, 사후 재현 테스트만 해당",
        })
    captured=sum(x["inReportingLeads"] for x in benchmark_results)
    return {
        "generatedAt":now.isoformat(timespec="seconds"),
        "officialSourceGeneratedAt":source["generatedAt"],
        "storySourceGeneratedAt":story["generatedAt"],
        "candidateCount":len(rows),
        "humanReviewEvents":len(reviews["reviews"]),
        "uniqueHumanReviewedAllTime":len(latest),
        "humanReviewedCurrentCandidates":len(labeled),
        "humanReviewCoverage":ratio(len(labeled),len(rows)),
        "finalizedHumanReviewSample":len(final),
        "positiveEditorialJudgments":positive,
        "negativeEditorialJudgments":negative,
        "observedEditorialHitRate":ratio(positive,len(final)),
        "observedFalsePositiveRate":ratio(negative,len(final)),
        "unsupportedAngleCount":breakdown["unsupported_angle"],
        "knownPriorCoverageCount":breakdown["already_reported"],
        "publishedEditorialCount":breakdown["published"],
        "pendingInvestigationCount":breakdown["needs_reporting"],
        "reviewBreakdown":{key:breakdown[key] for key in sorted(DECISIONS)},
        "priorityScoreBuckets":by_score,
        "knownCaseReplay":{
            "matched":captured,"total":len(benchmark_results),
            "captureRate":ratio(captured,len(benchmark_results)),
            "cases":benchmark_results,
            "explanation":"이미 알려진 보도 사례의 사후 재현률이며, 새 단독기사의 재현율·선행 발견율이 아님",
        },
        "status":("unmeasured_no_human_sample" if not final else
                  "small_review_sample" if len(final)<20 else "review_sample_measured"),
        "samplingCaveat":"검토자가 선택한 표본에 한정한 품질률. 무작위 표본이 아니면 전체 133건의 정확도 추정 불가",
        "exclusiveScoopsVerified":False,
        "metricsCaveat":"공식 출원/공개, 기사화, 단독 확인은 별도 사실. RSS 미발견은 미보도 입증이 아님",
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",default="digests/patent_hunt_latest.json")
    p.add_argument("--story",default="digests/patent_story_latest.json")
    p.add_argument("--reviews",default="data/patent_editorial_reviews.json")
    p.add_argument("--benchmarks",default="data/patent_benchmark_cases.json")
    p.add_argument("--out",default="digests/patent_quality_latest.json")
    args=p.parse_args()
    read=lambda f:json.loads(Path(f).read_text(encoding="utf-8"))
    report=summarize(read(args.story),read(args.source),read(args.reviews),read(args.benchmarks))
    dst=Path(args.out)
    dst.parent.mkdir(parents=True,exist_ok=True)
    temp=dst.with_suffix(".json.tmp")
    temp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    temp.replace(dst)
    print("Patent quality finalized sample",report["finalizedHumanReviewSample"],
          "out of candidates",report["candidateCount"],
          "observed editorial hit rate",report["observedEditorialHitRate"],
          "known-case replay",report["knownCaseReplay"]["captureRate"])


if __name__=="__main__":
    main()
