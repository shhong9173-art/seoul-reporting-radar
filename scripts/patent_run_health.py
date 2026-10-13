"""Safe public health audit of the KIPRIS Actions pipeline.

Generated even when API collection or tests fail. Never include credentials,
raw URLs with query ServiceKey, private environment values, or stack traces.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST=timezone(timedelta(hours=9))
STEPS=("checks","source","deep","story","quality","claims")
ARTIFACTS={
    "source":"digests/patent_hunt_latest.json",
    "deep":"digests/patent_deep_latest.json",
    "story":"digests/patent_story_latest.json",
    "quality":"digests/patent_quality_latest.json",
    "claims":"digests/patent_claim_review_latest.json",
}


def audit(outcomes,root=Path("."),now=None):
    now=now or datetime.now(KST)
    statuses={name:(outcomes.get(name) if outcomes.get(name) in
                     ("success","failure","skipped","cancelled") else "unknown")
              for name in STEPS}
    data={}
    for step,path in ARTIFACTS.items():
        entry={"path":path,"exists":False,"generatedAt":None,"consistent":False}
        try:
            raw=json.loads((root/path).read_text(encoding="utf-8"))
            if isinstance(raw,dict) and isinstance(raw.get("generatedAt"),str):
                entry["exists"]=True
                entry["generatedAt"]=raw["generatedAt"]
                if step=="source":
                    entry["complete"]=raw.get("sourceWindowComplete") is True
                    entry["validCompanies"]=raw.get("completelyCheckedCompanies")
                    entry["checkedCompanies"]=raw.get("applicantCount")
                    entry["missingCompanies"]=[x.get("company") for x in raw.get("companyChecks",[])
                                               if x.get("status")!="checked"][:30]
                if step=="story":
                    entry["leads"]=raw.get("possibleResearchLeads")
                    entry["coverageQueries"]=raw.get("mediaQueriesCompleted")
                data[step]=entry
            else:
                data[step]=entry
        except (OSError,ValueError,TypeError):
            data[step]=entry
    # Only outputs produced by the SAME successful run count as consistent.
    source=data["source"]["generatedAt"]
    deep=data["deep"]["generatedAt"]
    if statuses["source"]=="success" and data["source"]["complete"]:
        data["source"]["consistent"]=True
    if statuses["deep"]=="success" and source:
        try:
            d=json.loads((root/ARTIFACTS["deep"]).read_text(encoding="utf-8"))
            data["deep"]["consistent"]=d.get("patentDatasetGeneratedAt")==source
        except (OSError,ValueError):
            pass
    if statuses["story"]=="success" and source and deep:
        try:
            s=json.loads((root/ARTIFACTS["story"]).read_text(encoding="utf-8"))
            data["story"]["consistent"]=(s.get("officialSourceGeneratedAt")==source and
                                         s.get("deepSourceGeneratedAt")==deep)
        except (OSError,ValueError):
            pass
    if statuses["quality"]=="success" and source and data["story"]["generatedAt"]:
        try:
            q=json.loads((root/ARTIFACTS["quality"]).read_text(encoding="utf-8"))
            data["quality"]["consistent"]=(
                q.get("officialSourceGeneratedAt")==source and
                q.get("storySourceGeneratedAt")==data["story"]["generatedAt"])
            data["quality"]["humanReviewedCurrentCandidates"]=q.get("humanReviewedCurrentCandidates")
        except (OSError,ValueError):
            pass
    if statuses["claims"]=="success" and source and deep:
        try:
            c=json.loads((root/ARTIFACTS["claims"]).read_text(encoding="utf-8"))
            data["claims"]["consistent"]=(c.get("patentDatasetGeneratedAt")==source and
                                          c.get("deepDatasetGeneratedAt")==deep)
        except (OSError,ValueError):
            pass
    ready=(statuses["checks"]=="success" and
           all(data[k]["consistent"] for k in ("source","deep","story","quality")))
    return {
        "generatedAt":now.isoformat(timespec="seconds"),
        "workflowRunId":os.environ.get("GITHUB_RUN_ID","")[:32],
        "workflowAttempt":os.environ.get("GITHUB_RUN_ATTEMPT","")[:6],
        "workflowEvent":os.environ.get("GITHUB_EVENT_NAME","")[:25],
        "steps":statuses,
        "datasets":data,
        "status":"ready" if ready else "degraded",
        "claimComparisonStatus":"ok" if data["claims"]["consistent"] else "partial_or_missing",
        "editorialQualityStatus":"ok" if data["quality"]["consistent"] else "partial_or_missing",
        "warning":("검증 완료된 같은 실행의 공식 수집·심층·기사 가설 파일" if ready else
                   "중간 오류·누락 또는 파일 갱신 미확인. 기존 데이터 유지·신규 단독 판단 금지"),
        "scoopConfirmed":False,
    }


def main():
    outcomes={x:os.environ.get("PIPELINE_"+x.upper(),"unknown") for x in STEPS}
    report=audit(outcomes)
    path=Path("digests/patent_run_health_latest.json")
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    temp.replace(path)
    print("KIPRIS run status",report["status"],"steps",report["steps"])


if __name__=="__main__":
    main()
