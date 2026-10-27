"""Per-source retrieval health and first-seen baseline for domestic official leads.

State is observation metadata, not a claim that every agency notice was
collected. Google search RSS is an index, NOT an official board listing.
Outages never become 'zero publications', and a recovered query never proves
a newly published item merely because its URL was not seen before.
"""
from __future__ import annotations
import hashlib
from datetime import datetime
from urllib.parse import urlsplit

MAX_SEEN=1000
DIRECT_DOMAINS={
    "scourt-case-releases":"scourt.go.kr",
    "iris-rnd-announcements":"iris.go.kr",
    "ntis-announcements":"ntis.go.kr",
    "nlrc-case-summaries":"nlrc.go.kr",
    "ieps-permits":"ieps.nier.go.kr",
    "factoryon-industrial-sites":"factoryon.go.kr",
    "kepco-enc":"kepco-enc.com",
    "car-recalls":"car.go.kr",
}


def _when(value):
    try:
        d=datetime.fromisoformat(value)
        return d if d.tzinfo is not None and d.utcoffset() is not None else None
    except (TypeError,ValueError):
        return None


def _source_id(item):
    if not isinstance(item,dict):
        return None
    domain=item.get("querySite")
    if not isinstance(domain,str) or not domain or len(domain)>150:
        return None
    signal=item.get("signalType")
    if isinstance(signal,str) and signal:
        direct=next((name for name,host in DIRECT_DOMAINS.items()
                     if domain==host),None)
        if direct:
            return "direct:"+direct
        return None
    return "rss:"+domain


def _fingerprint(item):
    url=item.get("url")
    title=item.get("title")
    date=item.get("published")
    if not all(isinstance(v,str) and v for v in (url,title,date)):
        return None
    if _when(date) is None:
        return None
    # Accept official in-site JavaScript view IDs as stable opaque keys.
    if len(url)>1800 or len(title)>300:
        return None
    return hashlib.sha256((url+"|"+title+"|"+date[:10]).encode("utf-8")).hexdigest()[:24]


def _health_rss(d):
    if not isinstance(d,dict):
        return "unknown"
    q=d.get("rssQueries")
    if type(q) is not int or q<1:
        return "unknown"
    errors=d.get("errors")
    if not isinstance(errors,list):
        return "unknown"
    # RSS channel responses may succeed yet yield no relevant matching
    # official publications: this is NOT an empty underlying bulletin board.
    return "index_partial" if errors else "index_responded"


# Exclusions that mean a page could not be read or did not look like the official page.
BROKEN_EXCLUSIONS={"detail_fetch_failed","detail_deferred_after_timeouts","detail_structure_or_title_missing",
                   "list_detail_title_mismatch","list_detail_date_mismatch","announcement_date_missing_or_invalid"}


def _health_direct(d):
    if not isinstance(d,dict):
        return "unknown"
    attempted=d.get("pagesAttempted",d.get("listPagesAttempted",
               d.get("queriesAttempted",1 if d.get("listFetched") is True else None)))
    fetched=d.get("pagesFetched",d.get("listPagesFetched",
            d.get("searchPagesFetched",d.get("queriesSucceeded",
                  1 if d.get("listFetched") is True else None))))
    # Provider-specific detail fetches can fail with a usable list.
    if type(attempted) is not int or attempted<=0 or type(fetched) is not int:
        return "unknown"
    if fetched<0 or fetched>attempted:
        return "unknown"
    errors=d.get("errors")
    if not isinstance(errors,list):
        errors=[]
    if fetched==0:
        return "failed"
    # A retried request that then succeeded is not a failure; its first attempt
    # is logged with retry=True. Everything else (final attempts, plain strings) is.
    final_errors=[e for e in errors if not (isinstance(e,dict) and e.get("retry") is True)]
    exclusions=d.get("exclusions") if isinstance(d.get("exclusions"),dict) else {}
    broken=sum(int(v) for k,v in exclusions.items() if k in BROKEN_EXCLUSIONS and type(v) is int)
    invalid=sum(int(d.get(k) or 0) for k in ("invalidLinks","invalidIds") if type(d.get(k) or 0) is int)
    if fetched<attempted or final_errors or broken or invalid or d.get("detailCircuitOpen") is True:
        return "partial"
    # Coverage limits by design (first search page, page/detail caps) are recorded in the
    # diagnostics and named here as "not exhaustive" — not a failure that repeats every run.
    if d.get("collectionComplete") is False and d.get("coverageLimited") is not True:
        return "partial"
    return "checked_list_not_exhaustive"


def update_source_states(previous,rss_diagnostics,direct_diagnostics,fresh_items,*,now):
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("timezone_required")
    if not isinstance(rss_diagnostics,dict) or not isinstance(direct_diagnostics,dict):
        raise ValueError("source_diagnostics_missing")
    if not isinstance(fresh_items,list):
        raise ValueError("fresh_collected_items_required")
    if previous is not None and (not isinstance(previous,dict)
        or previous.get("status")!="official_source_observation_not_exclusive"
        or not isinstance(previous.get("sources"),dict)):
        raise ValueError("prior_observation_corrupt_preserve_history")
    old=previous.get("sources",{}) if previous else {}
    source_keys={"rss:"+key:_health_rss(value)
                 for key,value in rss_diagnostics.items() if isinstance(key,str)}
    source_keys.update({"direct:"+key:_health_direct(value)
                        for key,value in direct_diagnostics.items() if isinstance(key,str)})
    source_rows={}
    for item in fresh_items:
        key=_source_id(item)
        digest=_fingerprint(item)
        if key and digest and key in source_keys:
            source_rows.setdefault(key,set()).add(digest)
    updated={}
    for key,status in sorted(source_keys.items()):
        prior=old.get(key,{})
        if not isinstance(prior,dict):
            raise ValueError("bad_source_state_entry")
        prev_seen=prior.get("seenKeys",[])
        if not isinstance(prev_seen,list) or len(prev_seen)>MAX_SEEN:
            raise ValueError("bad_seen_history")
        if any(not isinstance(x,str) or len(x)!=24 for x in prev_seen):
            raise ValueError("bad_seen_key")
        if prior.get("lastOk") is not None and not _when(prior["lastOk"]):
            raise ValueError("bad_last_ok")
        if prior.get("lastFail") is not None and not _when(prior["lastFail"]):
            raise ValueError("bad_last_fail")
        ok=status in ("index_responded","index_partial","partial","checked_list_not_exhaustive")
        failed=status in ("failed","index_partial","partial")
        now_iso=now.isoformat(timespec="seconds")
        seen=list(dict.fromkeys(prev_seen))
        discovered=sorted(source_rows.get(key,set())-set(seen)) if ok else []
        # If a source was unavailable in the previous run, newly observed
        # rows may have been published DURING the gap. They are evidence to
        # investigate, not 'just published' or previously unreported news.
        first_run=prior.get("lastOk") is None
        newly_observed=0 if first_run else len(discovered)
        recovered_after_gap=(prior.get("failStreak",0)>0)
        if ok:
            seen=list(dict.fromkeys((seen+discovered)[-MAX_SEEN:]))
        updated[key]={
            "status":status,
            "lastOk":now_iso if ok else prior.get("lastOk"),
            "lastFail":now_iso if failed else prior.get("lastFail"),
            "failStreak":(int(prior.get("failStreak",0))+1 if failed
                          else 0 if ok else int(prior.get("failStreak",0))),
            "seenKeys":seen,
            "baselineOnly":first_run,
            "newlyObservedSincePreviousOk":newly_observed,
            "observedAfterPriorGap":bool(recovered_after_gap and discovered),
            "rawNewlySeenAfterGap":len(discovered) if recovered_after_gap else 0,
            "actualPublicationNoveltyProved":False,
            "domesticUnreportedProved":False,
        }
    # Preserve health of sources not attempted; they must not be silently
    # marked current just because this batch skipped them.
    for key,row in old.items():
        if key not in updated:
            updated[key]={**row,"status":"not_checked_this_run",
                          "newlyObservedSincePreviousOk":0,
                          "actualPublicationNoveltyProved":False,
                          "domesticUnreportedProved":False}
    return {
        "status":"official_source_observation_not_exclusive",
        "generatedAt":now.isoformat(timespec="seconds"),
        "sourceCount":len(updated),
        "unknownOrFailedSources":[key for key,row in updated.items()
            if row["status"] in ("unknown","failed","not_checked_this_run")],
        "partiallyCollectedSources":[key for key,row in updated.items()
            if row["status"] in ("index_partial","partial")],
        "currentObservedSources":sum(row["status"] not in
            ("unknown","failed","not_checked_this_run") for row in updated.values()),
        "confirmedScoops":0,
        "warning":"원천별 최초 조회는 기준선. RSS 응답/0건은 정부 게시판 전체 공고 없음이 아님. 장애 후 처음 본 문서는 새 발행/국내 미보도 증거가 아님",
        "sources":updated,
    }
