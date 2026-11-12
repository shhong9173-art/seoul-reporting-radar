"""Direct SEC submissions feed monitor for public US industrial partner filings.

Reads DATA.SEC.GOV submissions JSON and preserves public filing dates and
accession numbers. A new submission observed is not new news or a scoop.
First successful collection is baseline only. Original exhibit body is not
fetched here, so do not infer substantive contracts or partnership decisions.
"""
from __future__ import annotations
import json
import re
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError

ROOT=Path(__file__).resolve().parents[1]
KST=timezone(timedelta(hours=9))
CONFIG=ROOT/"data/primary_sec_filer_watches.json"
OUTPUT=ROOT/"digests/primary_sec_filing_watch_latest.json"
STATUS="sec_edgar_filing_index_observed_not_fulltext_or_exclusive"
FORMS={"8-K","8-K/A","10-Q","10-Q/A","10-K","10-K/A",
       "6-K","20-F","20-F/A"}
LOOKBACK_DAYS=90
MAX_ROW_PER_COMPANY=25
MAX_OBSERVED=80
ACC=re.compile(r"\d{10}-\d{2}-\d{6}\Z")
FILE=re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,180}\Z")


def registry(spec):
    if (not isinstance(spec,dict) or spec.get("schemaVersion")!=1
        or not isinstance(spec.get("companies"),list)
        or not 1<=len(spec["companies"])<=12):
        raise ValueError("invalid_sec_filer_watch_registry")
    ids=set()
    for item in spec["companies"]:
        if (not isinstance(item,dict) or
            not isinstance(item.get("company"),str) or
            not 2<=len(item["company"])<=70 or
            not isinstance(item.get("cik"),str) or
            not re.fullmatch(r"\d{10}",item["cik"]) or
            item["cik"] in ids):
            raise ValueError("invalid_sec_cik")
        ids.add(item["cik"])
    return spec


def fetch_submission(cik):
    if not isinstance(cik,str) or not re.fullmatch(r"\d{10}",cik):
        raise ValueError("invalid_sec_cik")
    url="https://data.sec.gov/submissions/CIK"+cik+".json"
    request=Request(url,headers={
        "Accept":"application/json",
        "User-Agent":"SeoulReportingRadar public-source research https://github.com/shhong9173-art/seoul-reporting-radar",
    })
    with urlopen(request,timeout=12) as response:
        ctype=response.headers.get("Content-Type","").lower()
        if "json" not in ctype:
            raise ValueError("sec_did_not_return_json")
        body=response.read(2_000_001)
        if len(body)>2_000_000:
            raise ValueError("oversized_sec_submission")
        return json.loads(body.decode("utf-8"))


def parsed_day(value):
    try:
        return date.fromisoformat(value)
    except (ValueError,TypeError):
        return None


def decode_filing_rows(payload,cik,*,now):
    if not isinstance(payload,dict) or str(payload.get("cik"))!=str(int(cik)):
        raise ValueError("sec_cik_does_not_match")
    filings=payload.get("filings",{}).get("recent")
    if not isinstance(filings,dict):
        raise ValueError("missing_sec_recent_index")
    keys=("accessionNumber","form","filingDate","primaryDocument")
    cols=[filings.get(key) for key in keys]
    if not all(isinstance(col,list) for col in cols):
        raise ValueError("sec_schema_missing_required_columns")
    if len({len(col) for col in cols})!=1 or not 1<=len(cols[0])<=2000:
        raise ValueError("sec_recent_index_misaligned")
    today=now.astimezone(KST).date()
    result=[];seen=set()
    for acc,form,when,document in zip(*cols):
        if not (isinstance(acc,str) and ACC.fullmatch(acc) and
                isinstance(form,str) and form in FORMS and
                isinstance(document,str) and FILE.fullmatch(document)
                and ".." not in document and len(document)<=180):
            continue
        day=parsed_day(when)
        if day is None or day>today+timedelta(days=1) or day<today-timedelta(days=LOOKBACK_DAYS):
            continue
        if acc in seen:continue
        seen.add(acc)
        slug=acc.replace("-","")
        link=("https://www.sec.gov/Archives/edgar/data/"+
              str(int(cik))+"/"+slug+"/"+document)
        result.append({
          "accessionNumber":acc,"form":form,"filingDate":day.isoformat(),
          "primaryDocument":document,"filingOriginalUrl":link,
          "secCompanyIndexCik":cik,
          "originalDocumentBodyRead":False,
          "contractOrPartnerMentionVerified":False,
          "actualTransactionDateVerified":False,
        })
        if len(result)>=MAX_ROW_PER_COMPANY:break
    return result


def _time(value):
    try:
        dt=datetime.fromisoformat(value)
        return dt if dt.tzinfo and dt.utcoffset() is not None else None
    except (ValueError,TypeError,AttributeError):
        return None


def checked_previous(previous):
    if previous is None:return {},{}
    if (not isinstance(previous,dict) or previous.get("status")!=STATUS
        or not isinstance(previous.get("sources"),list)
        or not isinstance(previous.get("filings"),list)):
        raise ValueError("corrupt_sec_previous_state")
    state={};existing={}
    for src in previous["sources"]:
        if (not isinstance(src,dict) or
            not isinstance(src.get("cik"),str) or
            not re.fullmatch(r"\d{10}",src["cik"]) or
            not isinstance(src.get("seenAccessionNumbers"),list) or
            len(src["seenAccessionNumbers"])>400 or
            any(not isinstance(a,str) or not ACC.fullmatch(a)
                for a in src["seenAccessionNumbers"])):
            raise ValueError("corrupt_sec_source_history")
        state[src["cik"]]=src
    for rec in previous["filings"]:
        if (not isinstance(rec,dict) or
            not isinstance(rec.get("accessionNumber"),str) or
            not ACC.fullmatch(rec["accessionNumber"])):
            raise ValueError("corrupt_sec_filing_history")
        existing[rec["accessionNumber"]]=rec
    return state,existing


def collect(spec,previous=None,*,now,fetcher=fetch_submission):
    registry(spec)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("aware_now_required")
    state,old_rows=checked_previous(previous)
    stamp=now.astimezone(KST).isoformat(timespec="seconds")
    sources=[];observed={}
    for company in spec["companies"]:
        cik=company["cik"]
        prior=state.get(cik,{})
        prior_seen=prior.get("seenAccessionNumbers",[])
        had_baseline=bool(prior.get("lastOkAt"))
        record={
            "cik":cik,"company":company["company"],
            "submissionIndexUrl":"https://data.sec.gov/submissions/CIK"+cik+".json",
            "checkedAt":stamp,"lastOkAt":prior.get("lastOkAt"),
            "lastFailAt":prior.get("lastFailAt"),
            "failStreak":prior.get("failStreak",0),
            "status":"source_unavailable","baselineOnly":not had_baseline,
            "recentVerifiedFilingRows":None,"newSinceCleanBaseline":None,
            "seenAccessionNumbers":prior_seen,
        }
        try:
            rows=decode_filing_rows(fetcher(cik),cik,now=now)
            new=0
            already=set(prior_seen)
            for row in rows:
                acc=row["accessionNumber"]
                earlier=old_rows.get(acc,{})
                is_new=(had_baseline and prior.get("failStreak",0)==0
                        and acc not in already)
                observed[acc]={
                    **row,"company":company["company"],
                    "firstSeenAt":earlier.get("firstSeenAt",stamp),
                    "lastSeenAt":stamp,
                    "newSinceCleanBaseline":bool(is_new),
                    "observedAfterSourceGap":bool(
                        prior.get("failStreak",0) and acc not in already),
                    "fullTextAndPriorPressCompared":False,
                    "exclusiveConfirmed":False,
                    "reporterNextStep":(
                        "SEC 원문과 첨부문서 Item·계약 상대·정확한 효력일을 확인하고"
                        " 국내 선행보도 대조 및 회사의 공개 설명 확보"),
                }
                if is_new:new+=1
            merged=list(dict.fromkeys((prior_seen+
                         [r["accessionNumber"] for r in rows])[-400:]))
            record.update(
                status="sec_recent_index_checked_not_exhaustive",
                lastOkAt=stamp,failStreak=0,
                recentVerifiedFilingRows=len(rows),
                newSinceCleanBaseline=new,
                seenAccessionNumbers=merged)
        except (ValueError,OSError,HTTPError,URLError,TimeoutError,
                UnicodeError,json.JSONDecodeError) as e:
            record.update(
                lastFailAt=stamp,
                failStreak=int(prior.get("failStreak",0))+1,
                errorType=type(e).__name__,
            )
        sources.append(record)
    # A failed feed must not delete previously validated SEC accessions;
    # retired 90-day old indexes are not newly published releases.
    for acc,earlier in old_rows.items():
        if acc in observed:continue
        if not _time(earlier.get("lastSeenAt")):continue
        if (now-_time(earlier["lastSeenAt"]))>timedelta(days=14):
            continue
        observed[acc]={
            **earlier,"notRecheckedThisRun":True,
            "newSinceCleanBaseline":False,"exclusiveConfirmed":False,
            "fullTextAndPriorPressCompared":False,
        }
    items=sorted(observed.values(),
                 key=lambda x:(not x["newSinceCleanBaseline"],
                               x["filingDate"],x["accessionNumber"]),
                 reverse=False)
    # Within each category, most recent official filing dates first.
    new_rows=sorted((x for x in items if x["newSinceCleanBaseline"]),
                    key=lambda x:x["filingDate"],reverse=True)
    other_rows=sorted((x for x in items if not x["newSinceCleanBaseline"]),
                      key=lambda x:x["filingDate"],reverse=True)
    items=(new_rows+other_rows)[:MAX_OBSERVED]
    return {
        "status":STATUS,"generatedAt":stamp,
        "sources":sources,"filings":items,
        "sourcesAttempted":len(sources),
        "sourcesChecked":sum(s["status"]=="sec_recent_index_checked_not_exhaustive"
                             for s in sources),
        "sourcesUnavailable":sum(s["status"]=="source_unavailable" for s in sources),
        "filingsObserved":len(items),
        "newlyObservedAfterBaseline":sum(x["newSinceCleanBaseline"] for x in items),
        "sourceCoverageExhaustive":False,
        "allDomesticPressChecked":False,
        "allOriginalDocumentBodiesRead":False,
        "confirmedScoops":0,
        "warning":"SEC 공개 접수번호·접수일 관측일 뿐 첨부 본문·현대차 계약 관계·선행보도 확인 전이며 최초 관측을 첫 발표나 미보도 단독으로 간주하지 않는다.",
    }


def main():
    spec=json.loads(CONFIG.read_text(encoding="utf-8"))
    prev=json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else None
    result=collect(spec,prev,now=datetime.now(KST))
    OUTPUT.parent.mkdir(exist_ok=True)
    tmp=OUTPUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    tmp.replace(OUTPUT)
    print("SEC direct filings:",result["sourcesChecked"],"/",
          result["sourcesAttempted"],"registrants;",
          result["filingsObserved"],"indexed filing records;",
          result["newlyObservedAfterBaseline"],"first observed since clean baseline;",
          result["confirmedScoops"],"confirmed scoops")


if __name__=="__main__":
    main()
