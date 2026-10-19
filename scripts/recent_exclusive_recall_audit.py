"""Compare observed recent [단독] headlines across two INCOMPLETE RSS indexes.

This is a missing-observation diagnostic, not a claim that a publisher's
story did not exist, that any source beat was exhaustively searched, or that
the story is an original unreported scoop.
"""
from __future__ import annotations
import json
from datetime import datetime,timedelta,timezone
from pathlib import Path
from urllib.parse import urlsplit

from scripts.exclusive_reverse_trace import SCOOP_MARKER

KST=timezone(timedelta(hours=9))
STATUS="recent_exclusive_rss_cross_index_gap_not_exhaustive"
OUTPUT=Path("digests/recent_exclusive_recall_audit_latest.json")


def _when(v):
    try:
        d=datetime.fromisoformat(v.replace("Z","+00:00"))
        return d if d.tzinfo is not None and d.utcoffset() is not None else None
    except (ValueError,TypeError,AttributeError,OverflowError):
        return None


def _observed(row,now,hours):
    if not isinstance(row,dict) or row.get("global") is True:
        return None
    title=row.get("title","")
    when=_when(row.get("published"))
    link=row.get("url")
    if not isinstance(title,str) or not SCOOP_MARKER.search(title) or not when:
        return None
    if not (now-timedelta(hours=hours)<=when<=now+timedelta(minutes=5)):
        return None
    if not isinstance(link,str) or len(link)>1200:
        return None
    url=urlsplit(link)
    if url.scheme!="https" or url.hostname!="news.google.com":
        return None
    name=str(row.get("sourceName") or "").strip()
    if not name or len(name)>120:
        return None
    return {"title":title[:300],"url":link,"sourceName":name,
            "published":when.isoformat(timespec="seconds")}


def audit(news,history,*,now,hours=72,limit=25):
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("aware_now_required")
    if not 12<=hours<=168 or not 1<=limit<=50:
        raise ValueError("unbounded_recent_audit")
    if not isinstance(news,list) or len(news)>35000:
        raise ValueError("news_index_missing")
    if (not isinstance(history,dict)
        or history.get("status")!="historical_industry_exclusive_rss_partial_index"
        or not isinstance(history.get("items"),list)
        or history.get("itemCount")!=len(history["items"])
        or not _when(history.get("generatedAt"))
        or history.get("allDomesticIndustryExclusivesCovered") is not False):
        raise ValueError("history_not_verifiably_current")
    def selected(rows):
        out={}
        for raw in rows:
            a=_observed(raw,now,hours)
            if a:
                out[a["url"]]=a
        return out
    from_news=selected(news)
    from_history=selected(history["items"])
    news_only=sorted((a for k,a in from_news.items() if k not in from_history),
                      key=lambda a:a["published"],reverse=True)
    historical_only=sorted((a for k,a in from_history.items() if k not in from_news),
                           key=lambda a:a["published"],reverse=True)
    joint=set(from_news)&set(from_history)
    return {
       "status":STATUS,"generatedAt":now.astimezone(KST).isoformat(timespec="seconds"),
       "historySourceAt":history["generatedAt"],
       "lookbackHours":hours,
       "newsIndexObservedExclusive":len(from_news),
       "historyIndexObservedExclusive":len(from_history),
       "observedInBoth":len(joint),
       "newsOnlyObserved":len(news_only),
       "historyOnlyObserved":len(historical_only),
       "newsOnlyExamples":news_only[:limit],
       "historyOnlyExamples":historical_only[:limit],
       "fullArticleTextsReviewed":False,
       "rssCoverageExhaustive":False,
       "domesticUnreportedProved":False,
       "confirmedScoops":0,
       "warning":"메인 뉴스/과거 [단독] RSS 색인 사이의 관측 차이. 한쪽 미관측은 실제 미보도·단독의 증거가 아니며 언론사 원문과 발행일은 별도 확인",
    }


def main():
    news=json.loads(Path("data.json").read_text(encoding="utf-8"))
    history=json.loads(Path("digests/historical_exclusive_press_index_latest.json")
                       .read_text(encoding="utf-8"))
    result=audit(news,history,now=datetime.now(KST))
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    tmp=OUTPUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(result,ensure_ascii=False,separators=(",",":"))+"\n",
                   encoding="utf-8")
    tmp.replace(OUTPUT)
    print("Recent scoop RSS cross-index comparison:",
          result["newsIndexObservedExclusive"],"news observed,",
          result["historyIndexObservedExclusive"],"history observed,",
          result["observedInBoth"],"same Google URL,",
          result["newsOnlyObserved"],"news only,",
          result["historyOnlyObserved"],"history only (not proof of no story)")


if __name__=="__main__":
    main()
