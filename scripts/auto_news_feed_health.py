"""Secret-free Google News RSS audit; records missing feeds, never zero-news facts."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

VALID={"checked_recent_rows","checked_no_recent_rows",
       "checked_partial_dates","transport_or_xml_error","malformed_rss"}

def build(checks,*,expected,news_items,now,threshold=10):
    if now.tzinfo is None:raise ValueError("aware_timestamp_required")
    if (not isinstance(expected,int) or not 1<=expected<=100 or
        not isinstance(news_items,int) or news_items<0):
        raise ValueError("bad_count")
    if not isinstance(checks,list) or len(checks)>expected:raise ValueError("bad_checks")
    safe=[]
    for row in checks:
        if (not isinstance(row,dict) or row.get("status") not in VALID or
            not isinstance(row.get("globalFeed"),bool) or
            not isinstance(row.get("category"),str) or
            not 1<=len(row["category"])<=40 or
            not isinstance(row.get("recentRows"),int) or
            not 0<=row["recentRows"]<=100 or
            row.get("errorType") is not None and
            (not isinstance(row["errorType"],str) or
             not row["errorType"].isidentifier() or len(row["errorType"])>50)):
            raise ValueError("invalid_row")
        bad_dates=row.get("invalidPubDateRows",0)
        future_dates=row.get("futurePubDateRows",0)
        if (type(bad_dates) is not int or type(future_dates) is not int
            or not 0<=future_dates<=bad_dates<=1000
            or row["status"]=="checked_partial_dates" and bad_dates==0):
            raise ValueError("invalid_published_date_diagnostics")
        exclusive_query=row.get("exclusiveQuery",False)
        if type(exclusive_query) is not bool:
            raise ValueError("invalid_exclusive_query_diagnostic")
        duration=row.get("durationMs")
        if duration is not None and (type(duration) is not int or not 0<=duration<=600000):
            raise ValueError("invalid_latency")
        slim={k:row.get(k) for k in
                ("category","globalFeed","status","recentRows","errorType")}
        if duration is not None:slim["durationMs"]=duration
        if "invalidPubDateRows" in row:slim["invalidPubDateRows"]=bad_dates
        if "futurePubDateRows" in row:slim["futurePubDateRows"]=future_dates
        if "exclusiveQuery" in row:slim["exclusiveQuery"]=exclusive_query
        # 외신 검색: 받은 줄 수와 버린 이유별 건수(11-01) — 건수만, 제목·주소는 남기지 않는다
        if "feedItems" in row:
            if type(row["feedItems"]) is not int or not 0<=row["feedItems"]<=1000:raise ValueError("invalid_feed_items")
            slim["feedItems"]=row["feedItems"]
        if "dropped" in row:
            d=row["dropped"]
            if (not isinstance(d,dict) or not set(d)<= {"notNews","domestic","outlet","old","unscored"}
                or any(type(v) is not int or not 0<=v<=1000 for v in d.values())):
                raise ValueError("invalid_drop_counts")
            slim["dropped"]=dict(d)
        safe.append(slim)
    failures=sum(x["status"] in ("transport_or_xml_error","malformed_rss",
                                 "checked_partial_dates") for x in safe)
    zero=sum(x["status"]=="checked_no_recent_rows" for x in safe)
    complete=len(safe)==expected
    status=("incomplete_queries_or_provider_errors" if failures or not complete else
            "checked_but_insufficient_recent_news" if news_items<threshold else
            "source_requests_completed")
    return {
      "generatedAt":now.isoformat(timespec="seconds"),
      "status":status,"expectedQueries":expected,"attemptedQueries":len(safe),
      "errorQueries":failures,"validEmptyQueries":zero,
      "invalidPublishedDatesSkipped":sum(x.get("invalidPubDateRows",0) for x in safe),
      "futurePublishedDatesSkipped":sum(x.get("futurePubDateRows",0) for x in safe),
      "dateIncompleteQueries":sum(x["status"]=="checked_partial_dates" for x in safe),
      "exclusiveQueriesAttempted":sum(x.get("exclusiveQuery",False) for x in safe),
      "exclusiveQueriesFailedOrPartial":sum(x.get("exclusiveQuery",False)
                       and x["status"] in ("checked_partial_dates",
                                          "transport_or_xml_error","malformed_rss")
                       for x in safe),
      "exclusiveQueriesWithRecentRows":sum(x.get("exclusiveQuery",False)
                       and x["recentRows"]>0 for x in safe),
      "exclusiveQueryRecentRowsBeforeDedupe":sum(x["recentRows"] for x in safe
                                                  if x.get("exclusiveQuery",False)),
      "slowestQueries":[{"category":x["category"],"globalFeed":x["globalFeed"],
                         "status":x["status"],"durationMs":x["durationMs"]}
                        for x in sorted((s for s in safe if "durationMs" in s),
                            key=lambda s:s["durationMs"],reverse=True)[:5]],
      "recentArticleItemsAfterDedupe":news_items,
      "minimumPublicationItems":threshold,
      "newsDatasetApprovedForPublish":(news_items>=threshold),
      "allProvidersResponded":bool(complete and not failures),
      "unknownOfficialNewsCoverage":True,
      "zeroFetchedMeansZeroPublishedStories":False,
      "warning":"RSS 검색/형식/기간 장애는 기사 부재를 입증하지 않습니다. 수집 미달 시 기존 data.js/data.json 유지.",
      "checks":safe
    }

def persist(report,path):
    target=Path(path)
    target.parent.mkdir(parents=True,exist_ok=True)
    temp=target.with_suffix(".json.tmp")
    temp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    temp.replace(target)
