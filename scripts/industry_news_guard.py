"""Fail-closed industrial RSS publication dates and source health.

RSS request failure is not an empty underlying news source. A malformed or
undated article cannot receive the collector's current timestamp.
"""
from __future__ import annotations
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime


def inspect_rss_date(value, *, now, hours=72):
    """Return (usable datetime, reason), not a made-up publication timestamp.

    Old timestamped records are valid observations outside the rolling window.
    Malformed/missing/naive/future-dated records are source-health anomalies.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("collector_time_requires_timezone")
    if not isinstance(value,str) or not value.strip():
        return None,"invalid"
    try:
        dt=parsedate_to_datetime(value.strip())
        if dt.tzinfo is None or dt.utcoffset() is None:
            return None,"invalid"
        local=dt.astimezone(now.tzinfo)
    except (TypeError,ValueError,OverflowError,IndexError,AttributeError):
        return None,"invalid"
    if local>now+timedelta(minutes=5):
        return None,"future"
    if local<now-timedelta(hours=hours):
        return None,"outside_window"
    return local,"valid"


def verified_rss_date(value, *, now, hours=72):
    return inspect_rss_date(value,now=now,hours=hours)[0]


def summarize_queries(checks,expected):
    if (not isinstance(checks,list) or not isinstance(expected,int)
        or len(checks)!=expected or expected<1):
        raise ValueError("invalid_industry_feed_diagnostics")
    states=[x.get("status") for x in checks if isinstance(x,dict)]
    if len(states)!=expected or any(x not in
       ("checked_recent_rows","checked_no_relevant_recent",
        "checked_partial_dates","failed") for x in states):
        raise ValueError("unverifiable_industry_feed_status")
    errors=sum(x=="failed" for x in states)
    partial=sum(x=="checked_partial_dates" for x in states)
    bad=0;future=0
    if any(type(c.get("dedicatedExclusiveQuery",False)) is not bool
           for c in checks):
        raise ValueError("bad_industry_exclusive_query_health")
    for row in checks:
        invalid=row.get("rejectedUndated",0)
        later=row.get("rejectedFuture",0)
        if invalid is None and row.get("status")=="failed":
            continue
        if (type(invalid) is not int or type(later) is not int
            or not 0<=later<=invalid<=1000
            or row["status"]=="checked_partial_dates" and invalid==0):
            raise ValueError("invalid_industry_date_health")
        bad+=invalid
        future+=later
    return {
        "status":"failed_sources_preserve_previous_dataset" if errors
                  else "partial_dated_rss_not_complete_coverage" if partial
                  else "all_feed_requests_checked_not_full_news_coverage",
        "feedsExpected":expected,
        "feedsChecked":expected-errors,
        "feedsFailed":errors,
        "feedsPartiallyDated":partial,
        "exclusiveQueriesAttempted":sum(bool(c.get("dedicatedExclusiveQuery"))
                                        for c in checks),
        "exclusiveQueriesWithRows":sum(bool(c.get("dedicatedExclusiveQuery"))
                and c["status"] in ("checked_recent_rows","checked_partial_dates")
                and (c.get("recentRows") or 0)>0 for c in checks),
        "exclusiveQueriesFailedOrPartial":sum(bool(c.get("dedicatedExclusiveQuery"))
                and c["status"] in ("failed","checked_partial_dates") for c in checks),
        "exclusiveQueryObservedRows":sum((c.get("recentRows") or 0)
                                        for c in checks if c.get("dedicatedExclusiveQuery")),
        "rejectedInvalidDates":bad,
        "rejectedFutureDates":future,
        "feedsWithRelevantRows":sum(x in ("checked_recent_rows","checked_partial_dates")
                                    for x in states),
        "feedsCheckedNoRelevantRows":sum(x=="checked_no_relevant_recent" for x in states),
        "allFeedsHealthy":errors==0,
        "officialBulletinCoverageComplete":False,
        "proofOfNoIndustryNews":False,
        "domesticUnreportedProved":False,
        "warning":"부분 RSS 검색 결과는 정부·기업 전체 원문 모집단이 아님. 날짜 오류로 제외된 항목은 확인 실패이지 0건이 아니며 국내 미보도를 입증하지 않음",
    }
