"""Fail-closed industrial RSS publication dates and source health.

RSS request failure is not an empty underlying news source. A malformed or
undated article cannot receive the collector's current timestamp.
"""
from __future__ import annotations
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime


def verified_rss_date(value, *, now, hours=72):
    if not isinstance(value,str) or not value.strip():
        return None
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("collector_time_requires_timezone")
    try:
        dt=parsedate_to_datetime(value.strip())
        if dt.tzinfo is None or dt.utcoffset() is None:
            return None
        local=dt.astimezone(now.tzinfo)
        if now-timedelta(hours=hours) <= local <= now+timedelta(hours=6):
            return local
    except (TypeError,ValueError,OverflowError):
        pass
    return None


def summarize_queries(checks,expected):
    if (not isinstance(checks,list) or not isinstance(expected,int)
        or len(checks)!=expected or expected<1):
        raise ValueError("invalid_industry_feed_diagnostics")
    states=[x.get("status") for x in checks if isinstance(x,dict)]
    if len(states)!=expected or any(x not in
       ("checked_recent_rows","checked_no_relevant_recent","failed") for x in states):
        raise ValueError("unverifiable_industry_feed_status")
    errors=sum(x=="failed" for x in states)
    return {
        "status":"failed_sources_preserve_previous_dataset" if errors
                  else "all_feed_requests_checked_not_full_news_coverage",
        "feedsExpected":expected,
        "feedsChecked":expected-errors,
        "feedsFailed":errors,
        "feedsWithRelevantRows":sum(x=="checked_recent_rows" for x in states),
        "feedsCheckedNoRelevantRows":sum(x=="checked_no_relevant_recent" for x in states),
        "allFeedsHealthy":errors==0,
        "officialBulletinCoverageComplete":False,
        "proofOfNoIndustryNews":False,
        "domesticUnreportedProved":False,
        "warning":"부분 RSS 검색 결과는 정부·기업 전체 원문 모집단이 아님. 수집 실패는 빈 기사 목록이나 국내 미보도를 입증하지 않음",
    }
