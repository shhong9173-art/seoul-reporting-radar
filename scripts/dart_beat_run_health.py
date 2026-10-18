"""Safe, public DART beat producer run-health summary.

Executed after GitHub Actions steps with status/outcome passed as fixed string
environment variables. No credential, URL query string or raw provider body is
ever serialized. Source JSON is read only after resetting to origin/main so
failed/unpublished partial run data cannot be mistaken for last published data.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime,timedelta,timezone
from pathlib import Path

KST=timezone(timedelta(hours=9))
OUTCOMES=frozenset(("success","failure","cancelled","skipped","unknown"))

def normalized(value):
    return value if value in OUTCOMES else "unknown"

def read_published(path):
    try:
        data=json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError,ValueError,TypeError):
        return None
    if not isinstance(data,dict) or data.get("status")!="industry_beat_official_receipt_review":
        return None
    stamp=data.get("generatedAt")
    try:
        dt=datetime.fromisoformat(stamp)
        if dt.utcoffset() is None: return None
    except (ValueError,TypeError):
        return None
    return data


def read_published_event_queue(path):
    try:
        data=json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError,ValueError,TypeError):
        return None
    if not isinstance(data,dict) or data.get("status")!="official_date_triage":
        return None
    try:
        dt=datetime.fromisoformat(data.get("generatedAt"))
        if dt.utcoffset() is None:return None
    except (ValueError,TypeError):
        return None
    return data


def build(*,tests,registry,collector,publisher,published=None,now=None,
          official_queue="unknown",official_queue_published=None):
    now=now or datetime.now(KST)
    if now.utcoffset() is None:raise ValueError("naive_run_time")
    statuses={name:normalized(state) for name,state in (
        ("regressionTests",tests),("corporationIdRegistry",registry),
        ("officialDartCollection",collector),("datasetPublication",publisher),
        ("officialEventQueue",official_queue))}
    complete=(statuses["regressionTests"]=="success" and
              statuses["officialDartCollection"]=="success" and
              statuses["datasetPublication"]=="success")
    partial=complete and statuses["corporationIdRegistry"]!="success"
    sync_ok=bool(complete and statuses["officialEventQueue"]=="success"
        and published is not None and isinstance(official_queue_published,dict)
        and official_queue_published.get("beatWideDartSourceAt")==published.get("generatedAt")
        and any(isinstance(x,dict) and x.get("name")=="dart_beat_monitor"
            and x.get("sourceAt")==published.get("generatedAt")
            for x in official_queue_published.get("feedHealth",[])))
    if not complete:
        tag="failed_or_skipped_last_execution_old_data_preserved"
    elif statuses["officialEventQueue"] in ("failure","cancelled","skipped") or (statuses["officialEventQueue"]=="success" and not sync_ok):
        tag="official_list_published_event_queue_unsynchronized"
    elif partial:
        tag="official_list_published_registry_refresh_incomplete"
    else:
        tag="official_list_published"
    result={
      "generatedAt":now.astimezone(KST).isoformat(timespec="seconds"),
      "status":"dart_official_source_execution_health",
      "executionResult":tag,
      "stages":statuses,
      "latestDatasetPublished":published is not None,
      "latestDatasetGeneratedAt":published.get("generatedAt") if published else None,
      "lastPublishedCoveredCompanies":published.get("companiesCodeVerified") if published else None,
      "lastPublishedUnresolvedCompanies":published.get("companiesUnresolved") if published else None,
      "lastPublishedSourceFailures":published.get("companiesWithSourceErrors") if published else None,
      "lastPublishedDetailBacklog":published.get("uninspectedRelevantDetails") if published else None,
      "newCollectionVerified":complete,
      "officialEventQueueSourceSynchronized":sync_ok,
      "latestOfficialEventQueueSourceAt":(official_queue_published.get("beatWideDartSourceAt")
          if isinstance(official_queue_published,dict) else None),
      "registryRefreshVerified":statuses["corporationIdRegistry"]=="success",
      "sourceClaimsNotVerifiedIfFailed":not complete,
      "noNewFilingsClaimPermitted":False,
      "scoopConfirmed":False,
      "warning":"This reflects GitHub Actions step status, not exclusive reporting. Failed workflow means last published official data were preserved, NOT that no new DART filings existed. Missing DART company codes are not zero filings. Do not disclose API keys or source error responses."
    }
    try:
        ts=datetime.fromisoformat(result["latestDatasetGeneratedAt"])
        age=(now-ts.astimezone(KST)).total_seconds()/3600
        result["publishedDataStale24h"]=age>24 or age < -0.3
    except (ValueError,TypeError):
        result["publishedDataStale24h"]=True
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--dataset",default="digests/dart_beat_monitor_latest.json")
    p.add_argument("--output",default="digests/dart_beat_run_health_latest.json")
    p.add_argument("--event-queue",default="digests/official_event_triage_latest.json")
    a=p.parse_args()
    r=build(tests=os.getenv("DART_TESTS_OUTCOME","unknown"),
            registry=os.getenv("DART_REGISTRY_OUTCOME","unknown"),
            collector=os.getenv("DART_COLLECT_OUTCOME","unknown"),
            publisher=os.getenv("DART_PUBLISH_OUTCOME","unknown"),
            official_queue=os.getenv("DART_OFFICIAL_QUEUE_OUTCOME","unknown"),
            published=read_published(a.dataset),
            official_queue_published=read_published_event_queue(a.event_queue))
    dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True)
    tmp=dest.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    tmp.replace(dest)
    print("DART official producer:",r["executionResult"],
          "dataset",r["latestDatasetGeneratedAt"],"stale",r["publishedDataStale24h"])

if __name__=="__main__":main()
