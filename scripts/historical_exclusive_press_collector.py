"""Rolling, bounded historical Korean industry '[단독]' headline *search index*.

The 72-hour newsroom news feed is not a one-year historical press sample.
This collector rotates monthly × beat searches, remembers every observed
candidate for up to 365 days, and retains source failures separately from
valid empty RSS responses. Google News RSS is neither the publisher article
fulltext nor an exhaustive census; Y/P/N and source reach are NEVER inferred.
"""
from __future__ import annotations
import argparse
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
    INDUSTRY_COMPANIES, SCOOP_MARKER, SPORTS
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
    "parts_battery":"현대모비스 OR HL만도 OR LG에너지솔루션 OR 삼성SDI OR SK온 OR 천보",
    "steel_nonferrous":"포스코 OR 현대제철 OR KG스틸 OR 세아제강 OR 고려아연",
    "power_equipment":"HD현대일렉트릭 OR LS일렉트릭 OR 대한전선 OR LS전선 OR 두산에너빌리티",
    "energy_chemicals":"OCI홀딩스 OR 한화솔루션 OR 씨에스윈드 OR 롯데케미칼 OR GS칼텍스",
    # 11-01 기자 명시: 석유화학·정유 — 새 묶음의 13개월 창은 다음 실행부터 5개씩 처음 훑는다
    "petchem_refining":"LG화학 OR 롯데케미칼 OR 금호석유화학 OR 에쓰오일 OR SK이노베이션 OR HD현대오일뱅크",
}
RSS_URL="https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko"
MONTHS=13
QUERIES_PER_RUN=6   # 한 실행에 한 달치 출입 묶음 전부(11-01 석유화학·정유 묶음 추가로 5→6)
RECENT_WINDOW_DAYS=4
INDUSTRY_TERMS=re.compile(
    r"철강|제철|후판|냉연|열연|배터리|리튬|수소|전기차|"
    r"양극재|음극재|니켈|제련|제철소|HVDC|변압기|광산|석유화학|정유|나프타|NCC",re.I)
CONSTRUCTION_POSCO=re.compile(
    r"포스코(?:이앤씨|E&C|건설)|"
    r"재건축|재개발|시공사|정비사업|도시정비|아파트",re.I)
SPORTS_GOLF=re.compile(
    r"KPGA|KLPGA|LPGA|프로골프|골프|선수권|"
    r"제네시스.{0,8}챔피언십|피버스|타이거즈",re.I)
HUNGER_KIA=re.compile(
    r"기아\s*(?:호적|아동|문제|상태|극복|퇴치|빈곤|지수|위기|사태)|"
    r"기아호적|기아퇴치",re.I)


def tracked_industry_companies(title):
    """Only classify explicit tracked industrial companies, not homonyms.

    Corporate group names in construction reporting and non-automotive '기아'
    must not inflate automotive/steel historical exclusive story counts.
    Ambiguous names are excluded, not turned into verified company facts.
    """
    if not isinstance(title,str):
        return []
    if SPORTS.search(title) or SPORTS_GOLF.search(title):
        return []
    names=[name for name in sorted(INDUSTRY_COMPANIES,key=len,reverse=True)
           if name.casefold() in title.casefold()]
    if HUNGER_KIA.search(title):
        names=[x for x in names if x!="기아"]
    if CONSTRUCTION_POSCO.search(title) and not INDUSTRY_TERMS.search(title):
        names=[x for x in names if x!="포스코"]
    # Never silently map an explicit POSCO E&C-only mention to the
    # separately covered steel producer POSCO.
    if re.search(r"포스코(?:이앤씨|E&C|건설)",title,re.I) and not INDUSTRY_TERMS.search(title):
        names=[x for x in names if x!="포스코"]
    return names



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


def _all_month_beat_windows(now):
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("planning_requires_timezone")
    output=[]
    for back in range(MONTHS):
        for beat in BEATS:
            begin,end=month_bounds(now,back)
            expression=('[단독] ('+BEATS[beat]+') after:'+begin.isoformat()
                        +' before:'+end.isoformat())
            output.append({
                "windowId":beat+":"+begin.isoformat(),
                "beat":beat,"start":begin.isoformat(),
                "endExclusive":end.isoformat(),"query":expression,
                "url":RSS_URL.format(q=urllib.parse.quote(expression)),
            })
    return output


def recent_searches(now):
    """Run ALL five short-window beat queries on each normal newsroom run.

    This deliberately does not participate in the 13-month × beat historical rotation (78 slots since 11-01).
    Search results are observed headlines, not an exhaustive list of reporting.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("timezone_required")
    begin=(now-timedelta(days=RECENT_WINDOW_DAYS-1)).date().isoformat()
    end=(now.date()+timedelta(days=1)).isoformat()
    rows=[]
    for beat,companies in BEATS.items():
        q="[단독] ("+companies+") after:"+begin+" before:"+end
        rows.append({
            "windowId":"recent:"+beat,"beat":beat,
            "start":begin,"endExclusive":end,"query":q,
            "url":RSS_URL.format(q=urllib.parse.quote(q))
        })
    return rows


def planned_searches(now,*,batch=None,limit=QUERIES_PER_RUN,previous=None):
    """Never re-check a completed window while other windows remain untried.

    Explicit --batch is a deterministic diagnostic replay override. Normal
    production uses last-seen window health; a failed query is NOT a checked
    source, and a 0-row success is NOT proof of no historical news.
    """
    if not isinstance(limit,int) or not 1<=limit<=10:
        raise ValueError("queries_per_run_out_of_bounds")
    _previous_valid(previous)
    windows=_all_month_beat_windows(now)
    if batch is not None:
        slots=math.ceil(len(windows)/limit)
        if not isinstance(batch,int) or not 0<=batch<slots:
            raise ValueError("invalid_search_batch")
        return windows[batch*limit:(batch+1)*limit]
    health=(previous or {}).get("windowHealth",{})
    unchecked=[r for r in windows if r["windowId"] not in health]
    if unchecked:
        return unchecked[:limit]

    def when(v):
        if not isinstance(v,str):
            return None
        try:
            dt=datetime.fromisoformat(v)
            return dt if dt.tzinfo is not None and dt.utcoffset() is not None else None
        except (ValueError,OverflowError):
            return None

    # After the initial sweep, retry explicitly failed source windows if the
    # last attempt is older than 30 minutes. Never treat 0 results as failure.
    due_failures=[]
    checked=[]
    for row in windows:
        prior=health.get(row["windowId"])
        if not isinstance(prior,dict):
            raise ValueError("invalid_history_window_state")
        last_ok=when(prior.get("lastOk"))
        last_fail=when(prior.get("lastFail"))
        if prior.get("lastOk") is not None and last_ok is None:
            raise ValueError("invalid_window_last_ok")
        if prior.get("lastFail") is not None and last_fail is None:
            raise ValueError("invalid_window_last_fail")
        if (prior.get("lastAttemptStatus")=="failed"
            and (last_fail is None or now-last_fail>=timedelta(minutes=30))):
            due_failures.append(row)
        if last_ok is not None:
            checked.append((last_ok,row))
    if due_failures:
        return due_failures[:limit]
    # All slots already attempted: refresh the oldest successful observations
    # rather than tie selection to a wall-clock modulo (which can skip slots
    # when scheduled runs are cancelled or delayed).
    checked.sort(key=lambda x:(x[0],x[1]["windowId"]))
    return [row for _,row in checked[:limit]]


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
            when=parsedate_to_datetime(pub)
            if when.tzinfo is None or when.utcoffset() is None:
                raise ValueError("naive_pubdate")
            when=when.astimezone(KST)
        except (ValueError,TypeError,OverflowError,IndexError):
            stats["undated"]+=1
            continue
        if not(begin<=when.date()<end and cutoff<=when<=now+timedelta(hours=3)):
            stats["outsideWindow"]+=1
            continue
        if not SCOOP_MARKER.search(title):
            stats["nonExclusive"]+=1
            continue
        # Only the original title can establish an industrial entity.
        # Avoid KIA hunger records, POSCO E&C construction and sports.
        companies=tracked_industry_companies(title)
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
            or not re.fullmatch("[0-9a-f]{24}",row["id"])
            or not isinstance(row.get("title"),str)
            or _aware(row.get("published")) is None
            or row.get("rssIndexedHeadlineOnly") is not True
            or row.get("fulltextReviewed") is not False):
            raise ValueError("unsafe_history_row")


def merge_history(prior,observed,checks,*,now,recent_checks=None):
    _previous_valid(prior)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("timezone_required")
    if not isinstance(observed,list) or len(observed)>1_000:
        raise ValueError("too_many_observed_rows")
    if not isinstance(checks,list) or len(checks)>10 or not checks:
        raise ValueError("missing_query_health")
    recent_checks=[] if recent_checks is None else recent_checks
    if (not isinstance(recent_checks,list) or len(recent_checks)>len(BEATS)
        or any(not isinstance(c,dict)
               or c.get("windowId") not in {"recent:"+b for b in BEATS}
               or c.get("status") not in ("checked","failed")
               for c in recent_checks)
        or len({c["windowId"] for c in recent_checks})!=len(recent_checks)):
        raise ValueError("invalid_recent_query_health")
    cutoff=now-timedelta(days=HORIZON_DAYS)
    seen={}
    discarded_legacy_offbeat=0
    for row in (prior or {}).get("items",[]):
        when=_aware(row.get("published"))
        current_beat=set(tracked_industry_companies(row.get("title")))
        recorded_beat=set(row.get("companies") or [])
        if not current_beat.intersection(recorded_beat):
            discarded_legacy_offbeat+=1
            continue
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
    # Keep only the rolling 13 months; old month windows otherwise pile up
    # indefinitely and can make a legitimate archive hit the 130-item limit.
    live_window_ids={r["windowId"] for r in _all_month_beat_windows(now)}
    window_health={key:value for key,value in
                   (prior or {}).get("windowHealth",{}).items()
                   if key in live_window_ids}
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
    recent_ok=[r for r in recent_checks if r["status"]=="checked"]
    recent_failed=[r for r in recent_checks if r["status"]=="failed"]
    recent_new=[r for r in observed
                if isinstance(r,dict)
                and str(r.get("historicalBackfillWindow","")).startswith("recent:")]
    recent_window_start=(now-timedelta(days=RECENT_WINDOW_DAYS-1)).date()
    recent_observed=[r for r in items
                     if _aware(r["published"]) and
                     _aware(r["published"]).astimezone(KST).date()>=recent_window_start]
    return {
        "status":STATUS,
        "generatedAt":now.astimezone(KST).isoformat(timespec="seconds"),
        "lastSuccessfulSearchAt":(now.isoformat(timespec="seconds") if count_ok
            else (prior or {}).get("lastSuccessfulSearchAt")),
        "firstRunBaseline":prior is None,
        "lookbackDays":HORIZON_DAYS,
        "itemCount":len(items),
        "newObservedHeadlineCount":max(0,len(seen)-before),
        "discardedLegacyOffBeatHeadlinesThisRun":discarded_legacy_offbeat,
        "searchedWindowCountThisRun":len(checks),
        "recentBeatQueriesExpected":len(BEATS),
        "recentBeatQueriesAttempted":len(recent_checks),
        "recentBeatQueriesSucceeded":len(recent_ok),
        "recentBeatQueriesFailed":len(recent_failed),
        "recentBeatQueriesAllChecked":len(recent_ok)==len(BEATS),
        "recentWindowDays":RECENT_WINDOW_DAYS,
        "recentCandidateRowsFromThisRun":len(recent_new),
        "recentObservedHeadlinesRetained":len(recent_observed),
        "recentLatestPublishedAt":max(
            (r["published"] for r in recent_observed),default=None),
        "recentLastSuccessfulAt":(now.isoformat(timespec="seconds") if recent_ok
                                  else (prior or {}).get("recentLastSuccessfulAt")),
        "recentSearchErrors":[{"windowId":r["windowId"],
                              "errorType":r.get("errorType","unknown")}
                              for r in recent_failed],
        "recentSearchCoverageExhaustive":False,
        "successfulWindowsThisRun":count_ok,
        "failedWindowsThisRun":len(errors),
        "checkedNoCandidatesThisRun":sum(r["status"]=="checked"
            and r.get("matched")==0 for r in checks),
        "searchedWindowsWithPriorSuccess":sum(bool(r.get("lastOk"))
            for r in window_health.values()),
        "unvisitedBeatMonthWindows":len(live_window_ids)-sum(
            bool(row.get("lastOk")) for row in window_health.values()),
        "selectedBeatMonthWindows":[row["windowId"] for row in checks],
        "sourceCompletenessNotEstablished":True,
        "totalPlannedBeatMonthWindows":len(BEATS)*MONTHS,
        "searchErrors":errors,
        "windowHealth":window_health,
        "items":items,
        "allDomesticIndustryExclusivesCovered":False,
        "pressArticleFulltextsReviewed":False,
        "humanReviewedYPN":0,
        "confirmedScoops":0,
        "warning":"Google 뉴스 RSS에서 관측된 불완전한 365일 기사 제목 색인. 기아호적·포스코이앤씨 건설·스포츠 등 동명이의어 오분류는 제외. 빈 검색은 미보도 증명 아님. 기사 전문·정확한 발행일·원자료·단독성은 별도 검증",
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
    recent_checks=[]
    observed=[]
    # A diagnostic historical --batch does not claim current-window freshness.
    # Normal production searches every beat's current headlines BEFORE
    # resuming the long historical rotation.
    windows=(recent_searches(now) if args.batch is None else [])
    windows+=planned_searches(now,batch=args.batch,limit=args.max_queries,
                              previous=previous)
    for window in windows:
        try:
            result,stats=parse_observed_headlines(fetch_rss(window["url"]),window,now=now)
            observed.extend(result)
            target=recent_checks if window["windowId"].startswith("recent:") else checks
            target.append({"windowId":window["windowId"],
                           "status":"checked",**stats})
        except (OSError,ValueError,ET.ParseError,TimeoutError) as exc:
            target=recent_checks if window["windowId"].startswith("recent:") else checks
            target.append({"windowId":window["windowId"],"status":"failed",
                           "matched":None,"errorType":type(exc).__name__})
    result=merge_history(previous,observed,checks,now=now,
                         recent_checks=recent_checks)
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(result,ensure_ascii=False,separators=(",",":"))
                   +"\n",encoding="utf-8")
    tmp.replace(path)
    print("Historical industry exclusive RSS observation:",result["itemCount"],
          "observed; newly indexed",result["newObservedHeadlineCount"],
          "checked",result["successfulWindowsThisRun"],
          "failed",result["failedWindowsThisRun"],
          "recent",result["recentBeatQueriesSucceeded"],"/",result["recentBeatQueriesExpected"],
          "recent observed",result["recentObservedHeadlinesRetained"],
          "(no Y/P/N, no exclusivity claims)")


if __name__=="__main__":
    main()
