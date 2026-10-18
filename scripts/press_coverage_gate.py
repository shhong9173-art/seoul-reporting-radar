"""Fail-closed use of the observed (non-exhaustive) domestic media history.

A matching indexed article is NEGATIVE exclusivity evidence, but absence of a
matching indexed article is NEVER proof of non-coverage. Index title comparisons
do not substitute for reviewing the full Korean story.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

STATUS="observed_domestic_press_index_not_complete_coverage"
KST=timezone(timedelta(hours=9))


def load_index(path):
    try:
        obj=json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {"status":"missing_or_invalid_index","items":[]}
    if (not isinstance(obj,dict) or obj.get("status")!=STATUS
        or not isinstance(obj.get("items"),list)
        or obj.get("itemCount")!=len(obj["items"])
        or len(obj["items"])>100_000):
        return {"status":"missing_or_invalid_index","items":[]}
    if obj.get("seedOnly") is True:
        return {"status":"initial_baseline_without_articles","items":[]}
    return obj


def _date(value):
    if not isinstance(value,str):
        return None
    try:
        dt=datetime.fromisoformat(value.replace("Z","+00:00"))
        return dt.astimezone(KST) if dt.utcoffset() is not None else None
    except (ValueError,TypeError):
        return None


def prior_coverage_candidates(event,index,*,event_match_score,companies=None,
                              now=None,limit=12):
    """Evaluate headline candidates; do not assert fulltext, 0-news or novelty."""
    now=now or datetime.now(KST)
    if now.utcoffset() is None:
        raise ValueError("now must include timezone")
    if (not isinstance(index,dict) or index.get("status")!=STATUS
        or index.get("seedOnly") is True):
        return {"status":"index_unavailable_not_no_news",
                "matches":[],"fulltextReviewed":False,
                "notReportedProved":False,"sourceAt":None}
    generated=_date(index.get("generatedAt"))
    if generated is None:
        return {"status":"index_unavailable_not_no_news",
                "matches":[],"fulltextReviewed":False,
                "notReportedProved":False,"sourceAt":None}
    rows=index.get("items")
    if (not isinstance(rows,list) or len(rows)>100_000
        or index.get("itemCount")!=len(rows)):
        return {"status":"index_unavailable_not_no_news",
                "matches":[],"fulltextReviewed":False,
                "notReportedProved":False,"sourceAt":index.get("generatedAt")}
    first=_date(event.get("published")) if isinstance(event,dict) else None
    if first is None:
        return {"status":"event_date_unverified",
                "matches":[],"fulltextReviewed":False,
                "notReportedProved":False,"sourceAt":index.get("generatedAt")}
    matched=[]
    companies=set(x for x in (companies or []) if isinstance(x,str))
    if not companies:
        return {"status":"company_identity_missing",
                "matches":[],"fulltextReviewed":False,
                "notReportedProved":False,"sourceAt":index.get("generatedAt")}
    for article in rows:
        if not isinstance(article,dict) or article.get("global") is True:
            continue
        if not companies.intersection(article.get("companies") or []):
            continue
        recorded=_date(article.get("published"))
        if recorded is None:
            continue
        # Corporate announcements often have date-only midnight timestamps.
        if recorded > first and not (
            first.hour==0 and first.minute==0
            and recorded.date()==first.date()):
            continue
        if (not isinstance(article.get("title"),str)
            or not isinstance(article.get("sourceName"),str)):
            continue
        quality=event_match_score(event,article)
        if quality>=0.76:
            matched.append({
                "title":article["title"],"sourceName":article["sourceName"],
                "published":article["published"],"url":article.get("url",""),
                "eventMatchScore":round(quality,3),
                "indexedHeadlineOnly":True,"fulltextReviewed":False})
    matched.sort(key=lambda x:(x["eventMatchScore"],x["published"]),reverse=True)
    stale=(now-generated)>timedelta(hours=48) or generated>now+timedelta(hours=1)
    return {
        "status":("indexed_prior_headline_candidate" if matched else
                  "index_stale_no_negative_inference" if stale else
                  "no_strong_index_match_not_no_news"),
        "matches":matched[:limit],
        "indexedCorpusStale":stale,
        "sourceAt":index.get("generatedAt"),
        "fulltextReviewed":False,
        "notReportedProved":False,
        "warning":"Index hits are candidate earlier articles, not verified fulltext; zero hits never prove unreported status."
    }
