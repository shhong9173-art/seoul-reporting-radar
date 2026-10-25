"""Five-case, extensible first-party document -> reporter dossier collector.

All journalist claims must be backed by actually retrieved original page text.
Prior-coverage search is *not* implied; HTTP errors mean unknown, not zero.
This registry is a monitored starting set, not autonomous new-source discovery.
"""
from __future__ import annotations
import argparse
import hashlib
import html
from html.parser import HTMLParser
import json
import re
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import URLError, HTTPError
try:
    from scripts.candidate_press_preview import recheck, fetch_rss
except ModuleNotFoundError as exc:
    if exc.name != "scripts":
        raise
    from candidate_press_preview import recheck, fetch_rss

ROOT=Path(__file__).resolve().parents[1]
KST=timezone(timedelta(hours=9))
REGISTRY=ROOT/"data/primary_research_targets.json"
OUTPUT=ROOT/"digests/primary_research_dossiers_latest.json"
STATUS="primary_original_reporter_dossiers_not_exclusive"
ALLOWED_HOSTS={
    "svdisposition.com","www.svdisposition.com","www.ipgate.ch","ipgate.ch",
    "www.supremecourt.gov","supremecourt.gov","www.sec.gov","sec.gov",
    "find-and-update.company-information.service.gov.uk",
}
MAX_BYTES=850_000
MAX_TARGETS=30


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts=[]
        self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in ("script","style","noscript","svg"):
            self.skip+=1
    def handle_endtag(self,tag):
        if tag in ("script","style","noscript","svg") and self.skip:
            self.skip-=1
    def handle_data(self,data):
        if not self.skip:
            self.parts.append(data)


def normalized(raw):
    parser=_Text()
    parser.feed(raw)
    return re.sub(r"\s+"," ",html.unescape(" ".join(parser.parts))).strip()


def _time(value):
    try:
        d=datetime.fromisoformat(value)
        return d if d.tzinfo and d.utcoffset() is not None else None
    except (TypeError,ValueError,OverflowError,AttributeError):
        return None


def safe_url(value):
    if not isinstance(value,str) or len(value)>1800:
        return False
    try:
        parsed=urlsplit(value)
        return (parsed.scheme=="https" and parsed.hostname in ALLOWED_HOSTS
                and parsed.port in (None,443)
                and not parsed.username and not parsed.password
                and "#" not in value)
    except (ValueError,AttributeError):
        return False


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Fail closed; do not fetch arbitrary redirect destinations.
        raise ValueError("redirect_requires_manual_source_review")


def fetch_page(url):
    if not safe_url(url):
        raise ValueError("untrusted_original_source_url")
    req=Request(url,headers={
        "User-Agent":"IndustrialReporterSourceChecker/1.0 (+public-original-verification)",
        "Accept":"text/html,application/xhtml+xml;q=0.9,text/plain;q=0.8",
    })
    opener=build_opener(_NoRedirect)
    with opener.open(req,timeout=13) as resp:
        content_type=resp.headers.get("Content-Type","").lower()
        if "html" not in content_type and "text/plain" not in content_type:
            raise ValueError("non_text_original_requires_separate_parser")
        raw=resp.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES:
            raise ValueError("oversized_original_requires_review")
        encoding="utf-8"
        if "charset=" in content_type:
            enc=content_type.split("charset=",1)[1].split(";",1)[0].strip()
            if enc in ("utf-8","iso-8859-1","windows-1252"):
                encoding=enc
        return normalized(raw.decode(encoding,errors="replace"))


def checked_registry(spec):
    if (not isinstance(spec,dict) or spec.get("schemaVersion")!=1
        or not isinstance(spec.get("cases"),list)
        or not 1<=len(spec["cases"])<=MAX_TARGETS):
        raise ValueError("invalid_case_registry")
    seen=set()
    for case in spec["cases"]:
        if (not isinstance(case,dict) or
            not isinstance(case.get("id"),str) or
            not re.fullmatch(r"[a-z0-9-]{5,80}",case["id"]) or
            case["id"] in seen or
            type(case.get("priority")) is not int or
            not 1<=case["priority"]<=MAX_TARGETS or
            not isinstance(case.get("questions"),list) or
            not 1<=len(case["questions"])<=5 or
            not isinstance(case.get("documents"),list) or
            not 1<=len(case["documents"])<=5 or
            not isinstance(case.get("boundaries"),list) or
            not 1<=len(case["boundaries"])<=4):
            raise ValueError("invalid_case_record")
        seen.add(case["id"])
        for q in case["questions"]:
            if (not isinstance(q,dict) or
                not all(isinstance(q.get(k),str) and q[k].strip()
                        for k in ("recipient","text")) or
                not q["text"].endswith("?") or len(q["text"])>280):
                raise ValueError("nonpublic_or_unanswerable_question_shape")
        ids=set()
        for doc in case["documents"]:
            if (not isinstance(doc,dict) or
                not isinstance(doc.get("id"),str) or
                not re.fullmatch(r"[a-z0-9-]{3,85}",doc["id"]) or
                doc["id"] in ids or not safe_url(doc.get("url")) or
                not isinstance(doc.get("evidence"),list) or
                not 1<=len(doc["evidence"])<=7):
                raise ValueError("unverified_original_reference")
            ids.add(doc["id"])
            for fact in doc["evidence"]:
                if (not isinstance(fact,dict) or
                    not isinstance(fact.get("contains"),list) or
                    not 2<=len(fact["contains"])<=8 or
                    not all(isinstance(w,str) and 2<=len(w)<=100
                            for w in fact["contains"]) or
                    not isinstance(fact.get("fact"),str) or
                    not isinstance(fact.get("attribution"),str) or
                    not 8<=len(fact["fact"])<=260):
                    raise ValueError("unbounded_evidence_phrase")
    return spec


def validated_prior(previous):
    if previous is None:
        return {}
    if (not isinstance(previous,dict) or
        previous.get("status")!=STATUS or
        not isinstance(previous.get("cases"),list) or
        not _time(previous.get("generatedAt"))):
        raise ValueError("prior_dossiers_corrupt_preserve")
    old={}
    for case in previous["cases"]:
        if not isinstance(case,dict) or not isinstance(case.get("id"),str):
            raise ValueError("corrupt_previous_cases")
        for doc in case.get("originalDocuments",[]):
            if isinstance(doc,dict) and isinstance(doc.get("id"),str):
                old[(case["id"],doc["id"])]=doc
    return old


def comparison_baseline(older, url, now):
    """Retain hashes across outages, never across URLs or invalid chronology."""
    if older.get("url") != url:
        return None
    baseline = older.get("lastSuccessfulSnapshot")
    if baseline is None and older.get("status") == "matched_original_text":
        baseline = {"url": url, "checkedAt": older.get("checkedAt"),
                    "contentSha256": older.get("contentSha256"),
                    "firstObservedAt": older.get("firstObservedAt")}
    if not isinstance(baseline, dict) or baseline.get("url") != url:
        return None
    at = _time(baseline.get("checkedAt"))
    if not at or at >= now or not re.fullmatch(r"[a-f0-9]{64}", str(baseline.get("contentSha256", ""))):
        return None
    return baseline


def dossier(spec,previous=None,*,now=None,fetcher=fetch_page,prior_press=None,press_fetcher=None):
    checked_registry(spec)
    now=now or datetime.now(KST)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("timezone_required")
    now_s=now.astimezone(KST).isoformat(timespec="seconds")
    old=validated_prior(previous)
    run_id = str(uuid.uuid4())
    if prior_press is not None and not isinstance(prior_press,list):
        raise ValueError("malformed_prior_press_data")
    results=[]
    doc_count=0;verified_count=0;failed_count=0
    for case in sorted(spec["cases"],key=lambda v:(v["priority"],v["id"])):
        docs=[];facts=[]
        for doc in case["documents"]:
            doc_count+=1
            record={"id":doc["id"],"url":doc["url"],"status":"source_unavailable",
                    "checkedAt":now_s,"verifiedFactCount":0,
                    "firstObservedAt":None,"contentChangedSincePriorCheck":None,
                    "baselineOnly":True}
            older=old.get((case["id"],doc["id"]),{})
            baseline = comparison_baseline(older, doc["url"], now)
            record.update(comparisonStatus="current_fetch_failed", previousSuccessfulCheckAt=
                          baseline["checkedAt"] if baseline else None,
                          lastSuccessfulSnapshot=baseline)
            try:
                content=fetcher(doc["url"])
                if not isinstance(content,str) or len(content)<45:
                    raise ValueError("empty_or_nontext_original")
                lowered=re.sub(r"\s+"," ",content).casefold()
                page_hash=hashlib.sha256(lowered.encode()).hexdigest()
                matched=[]
                for assertion in doc["evidence"]:
                    if all(word.casefold() in lowered for word in assertion["contains"]):
                        matched.append({"text":assertion["fact"],
                                        "attribution":assertion["attribution"],
                                        "sourceUrl":doc["url"],
                                        "evidencePhrasesFound":assertion["contains"]})
                record["status"]="matched_original_text" if matched else "text_retrieved_no_expected_evidence"
                record["verifiedFactCount"]=len(matched)
                record["contentSha256"]=page_hash
                was_verified=baseline is not None
                record["firstObservedAt"]=(baseline.get("firstObservedAt") or baseline["checkedAt"]) if baseline else now_s
                record["contentChangedSincePriorCheck"]=(
                    baseline["contentSha256"]!=page_hash if was_verified
                    else None)
                record["baselineOnly"]=not was_verified
                record["comparisonStatus"]=("text_changed_requires_review" if record["contentChangedSincePriorCheck"]
                    else "text_unchanged" if baseline else "first_comparable_observation")
                record["lastSuccessfulSnapshot"]={"url":doc["url"], "checkedAt":now_s,
                    "contentSha256":page_hash,"firstObservedAt":record["firstObservedAt"]}
                facts.extend(matched)
                if matched:
                    verified_count+=1
                else:
                    failed_count+=1
            except (OSError,HTTPError,URLError,ValueError,UnicodeError,TimeoutError) as exc:
                record["errorType"]=type(exc).__name__
                # Prior successfully fetched facts are NOT carried forward as
                # current verification when the source is inaccessible.
                record["lastSuccessfulObservationAt"]=baseline["checkedAt"] if baseline else None
                failed_count+=1
            docs.append(record)
        matched_documents=sum(x["status"]=="matched_original_text" for x in docs)
        press_candidates=[]
        if prior_press is not None:
            terms=[t.casefold() for t in case.get("pressTerms",[]) if isinstance(t,str)]
            for entry in prior_press:
                if not isinstance(entry,dict):continue
                title=entry.get("title","")
                if not isinstance(title,str):continue
                if terms and all(t in title.casefold() for t in terms):
                    press_candidates.append({"title":title[:250],"url":entry.get("url")})
                    if len(press_candidates)==4:break
        results.append({
            "id":case["id"],"company":case["company"],
            "title":case["title"],"category":case["domain"],
            "editorialPriority":case["priority"],
            "sourceDate":case["sourceDate"],
            "sourceDateFromRegistryNotMachineVerified":True,
            "angle":case["angle"],
            "originalDocuments":docs,"factsFromMatchedPrimaryPages":facts,
            "originalDocumentsVerified":matched_documents,
            "originalDocumentsExpected":len(docs),
            "reporterReadyForVerification":bool(facts),
            "status":("all_registered_originals_matched" if matched_documents==len(docs)
                      else "partial_original_evidence" if matched_documents
                      else "originals_not_currently_verified"),
            "priorPressIndexStatus":("not_provided" if prior_press is None
                                     else "partial_index_not_fulltext_checked"),
            "possiblePriorPressTitles":press_candidates,
            "pressRecheck":recheck(case.get("pressTerms"), now=now, fetcher=press_fetcher)
                if press_fetcher is not None else {"status":"not_queried", "items":[],
                    "noPriorPressProved":False,"publisherFulltextCompared":False},
            "noPriorPressProved":False,
            "questionsForPublicConfirmation":case["questions"],
            "unresolved":case["boundaries"],
            "exclusiveConfirmed":False,
            "publisherFulltextCompared":False,
        })
    return {
        "status":STATUS,"generatedAt":now_s,"verificationRunId":run_id,
        "workflowRunUrl":("https://github.com/shhong9173-art/seoul-reporting-radar/actions/runs/"+
            os.environ["GITHUB_RUN_ID"] if os.environ.get("GITHUB_RUN_ID","").isdigit() else None),
        "registryBaselineDate":spec.get("baselineDate"),
        "registryIsManuallyCuratedNotAutomatedDiscovery":True,
        "cases":results,"caseCount":len(results),
        "documentRequestsAttempted":doc_count,
        "documentPagesMatched":verified_count,
        "documentPagesFailedOrUnmatched":failed_count,
        "confirmedScoops":0,"approvedArticles":0,
        "allDomesticPressChecked":False,
        "warning":"원문 페이지 확인은 1차 취재 출발점이며 선행보도 없음, 사내 계약·계획, 소송 승패, 격납고 폐쇄 또는 새 단독 증거가 아님",
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--registry",type=Path,default=REGISTRY)
    ap.add_argument("--output",type=Path,default=OUTPUT)
    ap.add_argument("--previous",type=Path,default=OUTPUT)
    args=ap.parse_args()
    spec=json.loads(args.registry.read_text(encoding="utf-8"))
    previous=json.loads(args.previous.read_text(encoding="utf-8")) if args.previous.exists() else None
    # A known news index can provide POSITIVE possible prior reports only.
    # Missing/failed news index NEVER becomes proof of no prior publication.
    press=None
    try:
        index=json.loads((ROOT/"digests/press_coverage_index_latest.json")
                         .read_text(encoding="utf-8"))
        if (index.get("status")=="observed_domestic_press_index_not_complete_coverage"
            and isinstance(index.get("items"),list)
            and index.get("itemCount")==len(index["items"])
            and _time(index.get("generatedAt"))):
            press=index["items"]
    except (OSError,ValueError,UnicodeError,AttributeError):
        pass
    result=dossier(spec,previous=previous,prior_press=press,press_fetcher=fetch_rss)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    tmp=args.output.with_suffix(args.output.suffix+".tmp")
    tmp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    tmp.replace(args.output)
    print("Primary reporter dossiers:",result["caseCount"],
          "cases,",result["documentPagesMatched"],"/",
          result["documentRequestsAttempted"],"original pages matched; 0 confirmed scoops")


if __name__=="__main__":
    main()
