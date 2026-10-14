"""NTIS public_project API collection for patent R&D reporting leads.

The NTIS key is read ONLY from the NTIS_API_KEY environment variable. The key
must never enter a repository file, a GitHub Actions log or a browser response.
The public_project service returns searchable project metadata; keyword hits
do NOT show patent outcome, project participation, product adoption or a scoop.

Public NTIS API path and parameters follow the NTIS OpenAPI guide; the first
authorized live response should be inspected for schema changes before making
journalistic assertions. An unrecognized response fails closed, never '0 hits'.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

KST = timezone(timedelta(hours=9))
API_URL = "https://www.ntis.go.kr/rndopen/openApi/public_project"
SEARCH_URL = "https://www.ntis.go.kr/ThSearchProjectList.do"
PATENT = re.compile(r"^10\d{11}$")
MAX_XML = 1_500_000
MAX_QUERIES = 12
CACHE_HOURS = 20


def txt(node, path, limit=220):
    value = node.findtext(path) if node is not None else None
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def parse_project_xml(payload):
    """Parse documented RESULT/TOTALHITS/RESULTSET/HIT. Never accept HTML."""
    if not isinstance(payload, bytes) or not payload or len(payload) > MAX_XML:
        raise ValueError("invalid_or_oversized_xml")
    upper = payload.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise ValueError("xml_entity_declaration_blocked")
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise ValueError("malformed_xml") from None
    if root.tag != "RESULT":
        raise ValueError("unexpected_ntis_xml_wrapper")
    total = txt(root, "TOTALHITS", 16)
    resultset = root.find("RESULTSET")
    if not total.isdigit() or resultset is None:
        # May represent invalid key, IP restriction, permission, or API change.
        raise ValueError("ntis_status_or_schema_unrecognized")
    if int(total) > 1_000_000_000:
        raise ValueError("implausible_hit_count")
    parsed = []
    hits = resultset.findall("HIT")
    for hit in hits[:25]:
        number = txt(hit, "ProjectNumber", 100)
        title = txt(hit, "ProjectTitle/Korean", 200) or txt(hit, "ProjectTitle/English", 200)
        if not number or not title:
            continue
        parsed.append({
            "projectNumber":number,
            "projectTitle":title,
            "performingAgency":txt(hit, "ResearchAgency/Name", 90) or None,
            "projectYear":txt(hit, "ProjectYear", 6) or None,
            "periodStart":txt(hit, "ProjectPeriod/Start", 20) or None,
            "periodEnd":txt(hit, "ProjectPeriod/End", 20) or None,
            "researchSummary":txt(hit, "Abstract/Teaser", 240) or
                              txt(hit, "Goal/Teaser", 240) or None,
            "keyword":txt(hit, "Keyword/Korean", 140) or None,
            "sourceSearchUrl":SEARCH_URL + "?" + urlencode({"dbt":"project","searchWord":number}),
            "researchLinkConfirmed":False,
            "patentOutcomeConfirmed":False,
            "companyProjectParticipationConfirmed":False,
            "commercializationConfirmed":False,
        })
    if hits and not parsed:
        raise ValueError("project_hits_unrecognized_fields")
    return {"totalHits":int(total),"records":parsed,
            "firstPageOnly":int(total)>len(hits)}


def request_xml(query, key, count=10, fetch=None):
    if not key or not isinstance(key,str):
        raise ValueError("missing_api_key")
    if not isinstance(query,str) or not 2<=len(query)<=110:
        raise ValueError("invalid_search_query")
    if not 1<=count<=25:
        raise ValueError("invalid_display_count")
    params = {
        "apprvKey":key, "userId":"", "collection":"project",
        "SRWR":query, "searchFd":"", "addQuery":"", "searchRnkn":"",
        "startPosition":1, "displayCnt":count,
    }
    url = API_URL + "?" + urlencode(params)
    if fetch:
        # Test hooks accept the URL; NEVER print that URL in production.
        return parse_project_xml(fetch(url))
    request = Request(url,headers={"User-Agent":"industry-reporting-radar/ntis-1.0",
                                   "Accept":"application/xml,text/xml"})
    with urlopen(request,timeout=20) as response:
        actual=urlsplit(response.geturl())
        if actual.scheme!="https" or actual.hostname!="www.ntis.go.kr":
            raise ValueError("unexpected_api_redirect")
        payload=response.read(MAX_XML+1)
    return parse_project_xml(payload)


def plan_queries(dossiers):
    if dossiers.get("status")!="research_only" or not dossiers.get("generatedAt") or not isinstance(dossiers.get("dossiers"),list):
        raise ValueError("invalid_dossier_snapshot")
    ordered=sorted(dossiers["dossiers"],key=lambda r:(not r.get("recentPatentWithin3Days"),
                       not r.get("pressLookupCompleted"),r.get("publicationNumber") or ""))
    plans=[]
    seen=set()
    for row in ordered:
        pub=str(row.get("publicationNumber") or "")
        if not PATENT.fullmatch(pub):continue
        for entry in (row.get("ntisResearchQueries") or [])[:2]:
            query=str(entry.get("query") or "").strip() if isinstance(entry,dict) else ""
            if not 2<=len(query)<=110:continue
            key=(pub,query)
            if key in seen:continue
            seen.add(key)
            plans.append({"publicationNumber":pub,
                          "publicationDate":row.get("publicationDate"),
                          "patentTitle":str(row.get("title") or "")[:180],
                          "query":query})
    return plans


def recent_success(previous, p, now):
    if not isinstance(previous,dict):return None
    for old in previous.get("checks",[]):
        if (old.get("publicationNumber")==p["publicationNumber"] and
            old.get("publicationDate")==p["publicationDate"] and
            old.get("query")==p["query"] and old.get("status")=="checked"):
            try:
                checked=datetime.fromisoformat(old["checkedAt"])
                hours=(now-checked).total_seconds()/3600
            except (ValueError, TypeError, KeyError):
                continue
            if 0<=hours<=CACHE_HOURS:return old
    return None


def collect(dossiers, key, previous=None, now=None, max_queries=MAX_QUERIES, search=request_xml):
    now=now or datetime.now(KST)
    if not 0<=max_queries<=MAX_QUERIES:raise ValueError("max_queries exceeds bound")
    plans=plan_queries(dossiers)
    cached={}
    for p in plans:
        old=recent_success(previous,p,now)
        if old:cached[(p["publicationNumber"],p["query"])]=old
    pending=[p for p in plans if (p["publicationNumber"],p["query"]) not in cached]
    checks=[]
    for p in plans:
        row=cached.get((p["publicationNumber"],p["query"]))
        if row:checks.append(row)
    attempted=0
    if key:
        for p in pending[:max_queries]:
            attempted+=1
            info={**p,"checkedAt":now.isoformat(timespec="seconds")}
            try:
                result=search(p["query"],key)
                if not isinstance(result,dict) or "records" not in result or "totalHits" not in result:
                    raise ValueError("search_response_invalid")
                info.update({"status":"checked","totalHits":result["totalHits"],
                             "firstPageOnly":result["firstPageOnly"],
                             "records":result["records"]})
            except HTTPError as exc:
                info.update({"status":"source_error","errorClass":"HTTP_"+str(exc.code)})
            except (URLError,TimeoutError,OSError):
                info.update({"status":"source_error","errorClass":"network_or_ip_allowlist"})
            except (ValueError,ET.ParseError,KeyError,TypeError) as exc:
                # Only internal controlled reason strings, never raw HTTP body/URL.
                allowed={"invalid_or_oversized_xml","xml_entity_declaration_blocked",
                         "malformed_xml","unexpected_ntis_xml_wrapper",
                         "ntis_status_or_schema_unrecognized","implausible_hit_count",
                         "project_hits_unrecognized_fields","unexpected_api_redirect",
                         "search_response_invalid"}
                code=str(exc)
                info.update({"status":"source_error",
                             "errorClass":code if code in allowed else "api_schema_unknown"})
            checks.append(info)
    remaining=len(plans)-len(cached)-attempted
    errors=sum(x["status"]=="source_error" for x in checks)
    completed=sum(x["status"]=="checked" for x in checks)
    state=("missing_key" if not key else "no_queries" if not plans else
           "partial_errors" if errors else
           "partial_not_yet_checked" if remaining else "ready")
    return {
        "generatedAt":now.isoformat(timespec="seconds"),
        "dossierGeneratedAt":dossiers["generatedAt"],
        "status":state,
        "source":"NTIS public_project OpenAPI - public project metadata",
        "scope":"bounded selected patent query strings, first result page, not NTIS exhaustive coverage",
        "totalResearchQueries":len(plans),
        "completedQueries":completed,"failedQueries":errors,
        "remainingQueries":remaining,"newQueriesThisRun":attempted,
        "sourceRecords":sum(len(x.get("records",[])) for x in checks),
        "projectPatentLinksConfirmed":0,
        "actualApplicationConfirmed":0,
        "checks":checks,
        "warning":"NTIS 검색결과는 관련성 후보일 뿐 해당 특허의 국가과제 성과·기업 참여·사업화 증명이 아닙니다. 부분/권한 오류는 0건 아님. 키와 원본 URL은 게시·기록하지 않습니다."
    }


def main():
    cli=argparse.ArgumentParser()
    cli.add_argument("--dossiers",default="digests/patent_rnd_dossiers_latest.json")
    cli.add_argument("--out",default="digests/ntis_project_leads_latest.json")
    cli.add_argument("--max-queries",type=int,default=MAX_QUERIES)
    args=cli.parse_args()
    source=json.loads(Path(args.dossiers).read_text(encoding="utf-8"))
    destination=Path(args.out)
    try:previous=json.loads(destination.read_text(encoding="utf-8"))
    except (OSError,ValueError):previous=None
    output=collect(source,os.environ.get("NTIS_API_KEY"),previous,max_queries=args.max_queries)
    destination.parent.mkdir(parents=True,exist_ok=True)
    temp=destination.with_suffix(".json.tmp")
    temp.write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    temp.replace(destination)
    print("NTIS public_project status",output["status"],"attempted",output["newQueriesThisRun"],
          "checked",output["completedQueries"],"errors",output["failedQueries"],
          "remaining",output["remainingQueries"])
    # A missing key or API failure must NOT imply successful new research data.
    # Pipeline still publishes the explicit source status, never fake zero hits.


if __name__=="__main__":
    main()
