"""Validate a single NTIS 1415180715 paginated official rpatent scan.

This does NOT establish company R&D participation or patent commercialization.
Two current API pages are checked against the frozen source; the historic
ten ResultIDs were not retained and cannot be claimed as identical.
"""
from __future__ import annotations
import argparse
import json
import re
from datetime import datetime
from pathlib import Path

PROJECT="1415180715"
SOURCE_TIME="2026-10-15T10:52:32+09:00"
PROFILE="ntis_rpatent_single_project_page_followup_v1"
ID=re.compile(r"^10\d{11}$")
RESULT_ID=re.compile(r"^[A-Za-z0-9_-]{5,100}$")
SECRETS=re.compile(r"(?i)apprvKey|authorization|bearer\s|api[_-]?key|password|secret")
FIELDS={
  "profile","generatedAt","sourceReverseGeneratedAt","planGeneratedAt",
  "projectNumber","status","collectionMethod","offlineSynthetic",
  "queryMode","pageSize","currentQueryTotalHits","firstPageRows","secondPageRows",
  "rowsInspected","actualHttpRequests","maxHttpRequests","distinctResultIDs",
  "paginationConfirmedByDisjointIds","currentQueryFullyInspected",
  "matchedOfficialProjectApplicationRows","records",
  "verifiedPatentProjectOutcomes","confirmedCommercialization","confirmedExclusives",
  "warning"
}
RECORD_FIELDS={
  "projectNumber","publicationNumber","applicationNumber","officialResultID",
  "sourceProjectID","sourceRegistType","sourceRegistTypeCode","sourceRegistNumber",
  "resultTitle","sameOfficialHitIdentifiers","officialPatentProjectOutcomeVerified",
  "commercializationConfirmed","exclusiveConfirmed"
}

def validate(result, plan, source, pinned, *, allow_offline=False):
    if not isinstance(result, dict) or set(result)!=FIELDS:
        raise ValueError("unexpected_followup_schema")
    if not isinstance(plan, dict) or not isinstance(source, dict) or not isinstance(pinned,dict):
        raise ValueError("source_missing")
    if (plan.get("planVersion")!="ntis_rpatent_reverse_projectid_v1"
        or plan.get("projectCount")!=26 or source.get("generatedAt")!=SOURCE_TIME
        or source.get("planGeneratedAt")!=plan.get("generatedAt")
        or source.get("status")!="ready" or source.get("completedProjects")!=23
        or source.get("failedProjects")!=0
        or pinned.get("schema")!="ntis_rpatent_kipris_7_identifiers_frozen_v1"
        or pinned.get("confirmedProjectOutcomeLinks")!=0):
        raise ValueError("source_snapshot_changed")
    checks=source.get("checks",[])
    if (not isinstance(checks,list) or len(checks)!=23
        or [x.get("projectNumber") for x in checks]!=
           [x.get("projectNumber") for x in plan.get("projects",[])[3:]]):
        raise ValueError("source_project_sequence_changed")
    remaining=[x for x in checks if x.get("uninspectedPagesRemain") is True]
    if (len(remaining)!=1 or remaining[0].get("projectNumber")!=PROJECT
        or remaining[0].get("primaryTotalHits")!=11
        or remaining[0].get("rowsInspected")!=10
        or remaining[0].get("matchingKiprisApplicationRows")!=0
        or remaining[0].get("searchModesCompleted")!=["primary"]
        or source.get("reviewedNumberPairs")!=0):
        raise ValueError("gap_source_not_verified")
    if (result["profile"]!=PROFILE or result["sourceReverseGeneratedAt"]!=SOURCE_TIME
        or result["planGeneratedAt"]!=plan["generatedAt"]
        or result["projectNumber"]!=PROJECT):
        raise ValueError("followup_provenance_mismatch")
    try:
        if datetime.fromisoformat(result["generatedAt"]).utcoffset() is None:
            raise ValueError()
    except (TypeError, ValueError):
        raise ValueError("invalid_collection_time") from None
    offline=result["offlineSynthetic"]
    if type(offline) is not bool or (offline and not allow_offline):
        raise ValueError("synthetic_result_is_not_real")
    method=("offline_synthetic_test_not_real" if offline else
            "approved_pc_ntis_rpatent_targeted_page_followup")
    if result["collectionMethod"]!=method or result["status"]!="ready":
        raise ValueError("unverified_collection_method")
    expected={
        "pageSize":10,"currentQueryTotalHits":11,"firstPageRows":10,
        "secondPageRows":1,"rowsInspected":11,"actualHttpRequests":2,
        "maxHttpRequests":2,"distinctResultIDs":11,
        "verifiedPatentProjectOutcomes":0,
        "confirmedCommercialization":0,"confirmedExclusives":0
    }
    for k,v in expected.items():
        if type(result.get(k)) is not int or result[k]!=v:
            raise ValueError("wrong_current_11_row_coverage_"+k)
    for k in ("paginationConfirmedByDisjointIds","currentQueryFullyInspected"):
        if result.get(k) is not True:
            raise ValueError("pagination_not_verified")
    if result["queryMode"]!="primary" or not isinstance(result["warning"],str) or not result["warning"]:
        raise ValueError("unapproved_query_mode")
    targets={(p["publicationNumber"],p["applicationNumber"]) for p in plan["targetKiprisApplications"]}
    frozen={(x["publicationNumber"],x["applicationNumber"]) for x in pinned["deep"]["investigations"]}
    if len(targets)!=7 or targets!=frozen:
        raise ValueError("changed_kipris_application_population")
    rows=result["records"]
    if not isinstance(rows,list) or len(rows)>11 or len(rows)!=result["matchedOfficialProjectApplicationRows"]:
        raise ValueError("invalid_pair_count")
    seen=set()
    for row in rows:
        if not isinstance(row,dict) or set(row)!=RECORD_FIELDS:
            raise ValueError("unexpected_record_fields")
        pub,app=row["publicationNumber"],row["applicationNumber"]
        normalized=re.sub(r"[\s-]","",str(row.get("sourceRegistNumber","")))
        if ((pub,app) not in targets or not ID.fullmatch(app)
            or normalized!=app or row["projectNumber"]!=PROJECT
            or row["sourceProjectID"]!=PROJECT):
            raise ValueError("wrong_official_project_or_kipris_application")
        if row["sourceRegistType"]!="출원" or row["sourceRegistTypeCode"]!="01":
            raise ValueError("registered_not_application")
        if (row["sameOfficialHitIdentifiers"] is not True
            or row["officialPatentProjectOutcomeVerified"] is not False
            or row["commercializationConfirmed"] is not False
            or row["exclusiveConfirmed"] is not False):
            raise ValueError("false_business_or_exclusive_claim")
        if not RESULT_ID.fullmatch(str(row.get("officialResultID") or "")):
            raise ValueError("bad_result_id")
        if (not isinstance(row["resultTitle"],str) or len(row["resultTitle"])>180
            or "<" in row["resultTitle"] or ">" in row["resultTitle"]):
            raise ValueError("html_or_untrusted_text")
        pair=(pub,app,row["officialResultID"])
        if pair in seen:raise ValueError("duplicate_row")
        seen.add(pair)
    if SECRETS.search(json.dumps(result,ensure_ascii=False)):
        raise ValueError("possible_credential_leak")
    return {"status":result["status"],"offlineSynthetic":offline,
            "currentPageRows":result["rowsInspected"],
            "verifiedPagination":True,"reviewOnlyNumberPairs":len(rows)}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("file")
    p.add_argument("--allow-offline-test",action="store_true")
    p.add_argument("--plan",default="digests/ntis_project_reverse_plan_latest.json")
    p.add_argument("--source",default="digests/ntis_project_reverse_remaining_23_pc_latest.json")
    p.add_argument("--pinned",default="digests/ntis_project_reverse_kipris_source.json")
    a=p.parse_args()
    def load(path):return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    print("NTIS targeted page follow-up:",validate(load(a.file),load(a.plan),load(a.source),
                                                     load(a.pinned),allow_offline=a.allow_offline_test))
if __name__=="__main__":main()
