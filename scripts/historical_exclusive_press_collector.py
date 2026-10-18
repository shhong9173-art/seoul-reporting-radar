"""Rolling, bounded historical Korean industry '[단독]' headline *search index*.

The 72-hour newsroom news feed is not a one-year historical press sample.
This collector rotates monthly × beat searches, remembers every observed
candidate for up to 365 days, and retains source failures separately from
valid empty RSS responses. Google News RSS is neither the publisher article
fulltext nor an exhaustive census; Y/P/N and source reach are NEVER inferred.
"""
from __future__ import annotations
import argparse
import calendar
import json
import math
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, date, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

from scripts.exclusive_reverse_trace import (
    INDUSTRY_COMPANIES, SCOOP_MARKER, SPORTS, STATUS as REVERSE_TRACE_STATUS
)
from scripts.press_coverage_index import article_id

KST=timezone(timedelta(hours=9))
STATUS="historical_industry_exclusive_rss_partial_index"
OUTPUT="digests/historical_exclusive_press_index_latest.json"
HORIZON_DAYS=365
MAX_ENTRIES=8_000
MAX_QUERY_ROWS=100
BEATS={
    "auto":"현대차 OR 기아 OR 제네시스 OR KG모빌리티 OR 한국GM",
    "parts_battery":"현대모비스 OR HL만도 OR LG에너지솔루션 OR 삼성SDI OR SK온",
    "steel_nonferrous":"포스코 OR 현대제철 OR KG스틸 OR 세아제강 OR 고려아연",
    "power_equipment":"HD현대일렉트릭 OR LS일렉트릭 OR 대한전선 OR LS전선 OR 두산에너빌리티",
    "energy_chemicals":"OCI홀딩스 OR 한화솔루션 OR 씨에스윈드 OR 롯데케미칼 OR GS칼텍스",
}
RSS_URL="https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko"
MONTHS=13
QUERIES_PER_RUN=5


def _aware(value):
    if not isinstance(value,str) or len(value)>55:
        return None
    try:
        dt=datetime.fromisoformat(value.replace("Z","+00:00"))
        return dt if dt.tzinfo is not None and dt.utcoffset() is not None else None
    except (ValueError,OverflowError,TypeError):
        return None


def month_bounds(now,months_back):
    if now.tzinfo is None or not 0<=months_back<MONTHS:
        raise ValueError("invalid_month_window")
    year=now.year
    month=now.month-months_back
    while month<=0:
        year-=1
        month+=12
    start=date(year,month,1)
    after=date(year+1,1,1) if month==12 else date(year,month+1,1)
    end=min(after,now.date()+timedelta(days=1))
    return start,end


def planned_searches(now,*,batch=None,limit=QUERIES_PER_RUN):
    if not 1<=limit<=10:
        raise ValueError("queries_per_run_out_of_bounds")
    slots=[(back,beat) for back in range(MONTHS) for beat in BEATS]
    slot_count=math.ceil(len(slots)/limit)
    if batch is None:
        batch=int(now.timestamp()//900)%slot_count
    if not isinstance(batch,int) or not 0<=batch<slot_count:
        raise ValueError("invalid_search_batch")
    selected=slots[batch*limit:(batch+1)*limit]
    output=[]
    for back,beat in selected:
        begin,end=month_bounds(now,back)
        expression='[단독] ('+BEATS[beat]+') after:'+begin.isoformat()+' before:'+end.isoformat()
        output.append({"windowId":beat+":"+begin.isoformat(),
                       "beat":beat,"start":begin.isoformat(),
                       "endExclusive":end.isoformat(),
                       "query":expression,
                       "url":RSS_URL.format(q=urllib.parse.quote(expression))})
    return output


def fetch_rss(url,timeout=12):
    req=urllib.request.Request(url,headers={
        "User-Agent":"ReporterOriginalSourceRadar/1.0",
        "Accept":"application/rss+xml,application/xml,text/xml,*/*"})
    with urllib.request.urlopen(req,timeout=timeout) as response:
        raw=response.read(2_500_001)
        if len(raw)>2_500_000:
            raise ValueError("rss_response_oversize")
        return raw


def parse_observed_headlines(raw,window,*,now):
    if not isinstance(raw,(bytes,str)):
        raise ValueError("invalid_rss_bytes")
    root=ET.fromstring(raw)
    if root.tag!="rss" or root.find("channel") is None:
        raise ValueError("rss_channel_missing")
    begin=date.fromisoformat(window["start"])
    end=date.fromisoformat(window["endExclusive"])
    cutoff=now-timedelta(days=HORIZON_DAYS)
    observed=[]
    stats={"rssRows":0,"outsideWindow":0,"nonExclusive":0,
           "offBeatOrSport":0,"undated":0,"matched":0}
    for item in root.findall("./channel/item")[:MAX_QUERY_ROWS]:
        stats["rssRows"]+=1
        title=(item.findtext("title") or "").strip()
        link=(item.findtext("link") or "").strip()
        pub=(item.findtext("pubDate") or "").strip()
        src=item.find("source")
        source=(src.text or "").strip() if src is not None else ""
        try:
            when=parsedate_to_datetime(pub).astimezone(KST)
            if when.tzinfo is None or when.utcoffset() is None:
                raise ValueError("naive_pubdate")
        except (ValueError,TypeError,OverflowError,IndexError):
            stats["undated"]+=1
            continue
        if not(begin<=when.date()<end and cutoff<=when<=now+timedelta(hours=3)):
            stats["outsideWindow"]+=1
            continue
        if not SCOOP_MARKER.search(title):
            stats["nonExclusive"]+=1
            continue
        if SPORTS.search(title):
            stats["offBeatOrSport"]+=1
            continue
        # Only title-identified industry companies. Generic topical query
        # hits and RSS summaries cannot conjure corporate identities.
        companies=[name for name in sorted(INDUSTRY_COMPANIES,key=len,reverse=True)
                   if name.lower() in title.lower()]
        if not companies:
            stats["offBeatOrSport"]+=1
            continue
        url=urllib.parse.urlsplit(link)
        if (url.scheme!="https" or url.hostname!="news.google.com"
            or not source or len(source)>120 or len(title)>300
            or len(link)>1200):
            stats["offBeatOrSport"]+=1
            continue
        result={"title":title,"sourceName":source,"url":link,
                "published":when.isoformat(timespec="seconds"),
                "companies":companies[:8],"global":False,
                "fulltextReviewed":False,"coverageIndexOnly":True,
                "publisherOriginalUrlVerified":False,
                "publisherPublicationTimeVerified":False,
                "rssIndexedHeadlineOnly":True,
                "historicalBackfillWindow":window["windowId"],
                "historicalBeatGroup":window["beat"]}
        result["id"]=article_id(result)
        observed.append(result)
        stats["matched"]+=1
    return observed,stats


def _previous_valid(prior):
    if prior is None:
        return
    if (not isinstance(prior,dict) or prior.get("status")!=STATUS
        or not isinstance(prior.get("items"),list)
        or len(prior["items"])>MAX_ENTRIES
        or prior.get("itemCount")!=len(prior["items"])
        or not isinstance(prior.get("windowHealth"),dict)
        or len(prior["windowHealth"])>130):
        raise ValueError("invalid_historical_corpus_preserve_previous")
    for row in prior["items"]:
        if (not isinstance(row,dict) or not isinstance(row.get("id"),str)
            or not isinstance(row.get("title"),str)
            or _aware(row.get("published")) is None
            or row.get("rssIndexedHeadlineOnly") is not True
            or row.get("fulltextReviewed") is not False):
            raise ValueError("unsafe_history_row")


def merge_history(prior,observed,checks,*,now):
    _previous_valid(prior)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("timezone_required")
    if not isinstance(observed,list) or len(observed)>1_000:
        raise ValueError("too_many_observed_rows")
    if not isinstance(checks,list) or len(checks)>10 or not checks:
        raise ValueError("missing_query_health")
    cutoff=now-timedelta(days=HORIZON_DAYS)
    seen={}
    for row in (prior or {}).get("items",[]):
        when=_aware(row.get("published"))
        if when is not None and cutoff<=when<=now+timedelta(hours=3):
            seen[row["id"]]=row
    before=len(seen)
    for row in observed:
        if (not isinstance(row,dict) or row.get("rssIndexedHeadlineOnly") is not True
            or row.get("fulltextReviewed") is not False
            or row.get("publisherOriginalUrlVerified") is not False
            or not isinstance(row.get("id"),str)
            or not re.fullmatch("[0-9a-f]{24}",row["id"])
            or _aware(row.get("published")) is None):
            raise ValueError("invalid_observed_historical_candidate")
        when=_aware(row["published"])
        if cutoff<=when<=now+timedelta(hours=3):
            seen[row["id"]]=row
    if len(seen)>MAX_ENTRIES:
        raise ValueError("history_max_entries_preserve_previous")
    statuses={"checked","failed"}
    if any(not isinstance(c,dict)
           or not isinstance(c.get("windowId"),str)
           or c.get("status") not in statuses for c in checks):
        raise ValueError("invalid_search_health_record")
    window_health=dict((prior or {}).get("windowHealth",{}))
    for row in checks:
        key=row["windowId"]
        previous=window_health.get(key,{})
        if not isinstance(previous,dict):
            raise ValueError("invalid_window_health")
        success=row["status"]=="checked"
        window_health[key]={
            "lastOk":now.isoformat(timespec="seconds") if success
                     else previous.get("lastOk"),
            "lastFail":now.isoformat(timespec="seconds") if not success
                       else previous.get("lastFail"),
            "lastAttemptStatus":row["status"],
            "failStreak":0 if success else int(previous.get("failStreak",0))+1,
            "returnedCandidateRows":row.get("matched") if success else None,
            "errorType":row.get("errorType") if not success else None,
        }
    if len(window_health)>130:
        raise ValueError("excessive_window_health")
    items=sorted(seen.values(),key=lambda row:(row["published"],row["id"]),reverse=True)
    errors=[{"windowId":r["windowId"],"errorType":r.get("errorType","unknown")}
            for r in checks if r["status"]=="failed"]
    count_ok=len(checks)-len(errors)
    return {
        "status":STATUS,
        "generatedAt":now.astimezone(KST).isoformat(timespec="seconds"),
        "lastSuccessfulSearchAt":(now.isoformat(timespec="seconds") if count_ok
            else (prior or {}).get("lastSuccessfulSearchAt")),
        "firstRunBaseline":prior is None,
        "lookbackDays":HORIZON_DAYS,
        "itemCount":len(items),
        "newObservedHeadlineCount":max(0,len(seen)-before),
        "searchedWindowCountThisRun":len(checks),
        "successfulWindowsThisRun":count_ok,
        "failedWindowsThisRun":len(errors),
        "checkedNoCandidatesThisRun":sum(r["status"]=="checked"
            and r.get("matched")==0 for r in checks),
        "searchedWindowsWithPriorSuccess":sum(bool(r.get("lastOk"))
            for r in window_health.values()),
        "totalPlannedBeatMonthWindows":len(BEATS)*MONTHS,
        "searchErrors":errors,
        "windowHealth":window_health,
        "items":items,
        "allDomesticIndustryExclusivesCovered":False,
        "pressArticleFulltextsReviewed":False,
        "humanReviewedYPN":0,
        "confirmedScoops":0,
        "warning":"Google 뉴스 RSS 월별 검색에서 관측된 [단독] 제목 후보의 불완전한 365일 색인. 빈 검색은 0건의 실제 기사가 아님. 기사 전문·실제 최초 발행일·원자료·독점성은 전부 별도 검증",
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",default=OUTPUT)
    parser.add_argument("--batch",type=int)
    parser.add_argument("--max-queries",type=int,default=QUERIES_PER_RUN)
    args=parser.parse_args()
    now=datetime.now(KST)
    path=Path(args.output)
    previous=json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    _previous_valid(previous)
    checks=[]
    observed=[]
    for window in planned_searches(now,batch=args.batch,limit=args.max_queries):
        try:
            result,stats=parse_observed_headlines(fetch_rss(window["url"]),window,now=now)
            observed.extend(result)
            checks.append({"windowId":window["windowId"],
                           "status":"checked",**stats})
        except (OSError,ValueError,ET.ParseError,TimeoutError) as exc:
            checks.append({"windowId":window["windowId"],"status":"failed",
                           "matched":None,"errorType":type(exc).__name__})
    result=merge_history(previous,observed,checks,now=now)
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(result,ensure_ascii=False,separators=(",",":"))
                   +"\n",encoding="utf-8")
    tmp.replace(path)
    print("Historical industry exclusive RSS observation:",result["itemCount"],
          "observed; newly indexed",result["newObservedHeadlineCount"],
          "checked",result["successfulWindowsThisRun"],
          "failed",result["failedWindowsThisRun"],
          "(no Y/P/N, no exclusivity claims)")


if __name__=="__main__":
    main()
