"""Fail-closed validation for registered-PC NTIS follow-up output.

Report may only contain number-matched official rpatent outcome rows. An
application number from KIPRIS and ProjectID from the SAME rpatent HIT are
necessary for a lead, but do not prove commercialization or exclusive news.
The earlier 26 sampled project IDs are an incomplete subset.
"""
import argparse
import json
import re
from pathlib import Path
from datetime import datetime
from ntis_followup_plan import validate_plan

APP=re.compile(r"^10\d{11}$")
PROJ=re.compile(r"^\d{10}$")
RESULT=re.compile(r"^[A-Za-z0-9_-]{5,100}$")
SECRET=re.compile(r"(?i)apprvKey|authorization|bearer\s|api[_-]?key|password|secret")
ROOT={
    "generatedAt","planGeneratedAt","sourceDiscoveryGeneratedAt",
    "sourceDossierGeneratedAt","status","collectionMethod","planVersion",
    "plannedQueries","completedQueries","failedQueries","maxHttpRequests",
    "actualHttpRequests","additionalScannedRows",
    "applicationMatchRowsOutsideOldProjectSubset",
    "exactApplicationProjectNumberReviewCandidates",
    "officialPatentProjectLinksConfirmed","commercializationConfirmed",
    "exclusiveConfirmed","checks","records","warning",
}
CHECK={
    "query","strategy","sourceTotalHits","pagesRequested","pagesCompleted",
    "targets","status","errorClass","newQueryTotalHits","newlyScannedRows",
    "exactApplicationRows","exactApplicationWithProjectOutsideOlderSubset",
    "registrationTypeExcluded","unrelatedApplicationExcluded","truncated",
}
RECORD={
    "publicationNumber","patentApplicationNumber","projectNumber",
    "projectInOlder26ProjectSubset","officialOutcomeId","registType",
    "registTypeCode","registNumberRaw","outcomeTitle","projectTitle",
    "performingAgency","query","strategy","page","officialFieldsInSameHit",
    "patentProjectLinkConfirmed","commercializationConfirmed",
    "exclusiveConfirmed",
}

def normalize(value):
    value=re.sub(r"[\s-]","",str(value or ""))
    return value if APP.fullmatch(value) else None

def project_set(projects):
    return {str(row.get("projectNumber")) for c in projects.get("checks",[])
            if c.get("status")=="checked" for row in c.get("records",[])
            if PROJ.fullmatch(str(row.get("projectNumber") or ""))}

def validate(export,plan,previous,projects):
    if not isinstance(export,dict) or set(export)!=ROOT:
        raise ValueError("unexpected_followup_export_schema")
    validate_plan(plan,previous)
    if (export["planVersion"]!=plan["planVersion"] or
        export["planGeneratedAt"]!=plan["generatedAt"] or
        export["sourceDiscoveryGeneratedAt"]!=plan["sourceDiscoveryGeneratedAt"] or
        export["sourceDossierGeneratedAt"]!=plan["sourceDossierGeneratedAt"] or
        projects.get("generatedAt")!=plan["sourceNtisProjectsGeneratedAt"] or
        projects.get("dossierGeneratedAt")!=plan["sourceNtisProjectDossierGeneratedAt"]):
        raise ValueError("not_pinned_to_provenance")
    if export["collectionMethod"]!="approved_pc_ntis_rpatent_targeted_followup":
        raise ValueError("unknown_collection_method")
    if export["status"] not in ("ready","partial_errors","incomplete"):
        raise ValueError("unknown_import_status")
    try:
        if datetime.fromisoformat(export["generatedAt"]).utcoffset() is None:
            raise ValueError()
    except (TypeError,ValueError):
        raise ValueError("invalid_followup_datetime") from None
    if (export["officialPatentProjectLinksConfirmed"]!=0 or
        export["commercializationConfirmed"]!=0 or export["exclusiveConfirmed"]!=0):
        raise ValueError("unsupported_reporting_certainty")
    if (not isinstance(export["checks"],list) or not isinstance(export["records"],list) or
        len(export["checks"])>plan["uniqueQueries"] or len(export["records"])>120):
        raise ValueError("invalid_or_unbounded_result_data")
    if (export["plannedQueries"]!=plan["uniqueQueries"] or
        export["maxHttpRequests"]!=plan["maximumHttpRequests"] or
        type(export["actualHttpRequests"]) is not int or
        not 0<=export["actualHttpRequests"]<=plan["maximumHttpRequests"]):
        raise ValueError("bad_http_request_budget")
    previous_projects=project_set(projects)
    done=failed=rows=outside=pages_checked=0
    queryChecks={}
    for item,expected in zip(export["checks"],plan["tasks"]):
        if not isinstance(item,dict) or set(item)!=CHECK:
            raise ValueError("unexpected_check_fields")
        for prop in ("query","strategy","sourceTotalHits","pagesRequested","targets"):
            if item.get(prop)!=expected[prop]:
                raise ValueError("query_not_in_approved_followup_plan")
        pages=item.get("pagesCompleted")
        if not isinstance(pages,list) or pages!=expected["pages"][:len(pages)]:
            raise ValueError("unapproved_page_sequence")
        pages_checked+=len(pages)
        if item.get("status")=="checked":
            done+=1
            if pages!=expected["pages"] or item.get("errorClass") is not None:
                raise ValueError("false_complete_search")
        elif item.get("status")=="source_error":
            failed+=1
            if not isinstance(item.get("errorClass"),str) or not item["errorClass"]:
                raise ValueError("missing_source_error_reason")
        else:
            raise ValueError("invalid_individual_search_status")
        for key in ("newlyScannedRows","exactApplicationRows",
                    "exactApplicationWithProjectOutsideOlderSubset",
                    "registrationTypeExcluded","unrelatedApplicationExcluded"):
            if type(item.get(key)) is not int or item[key]<0:
                raise ValueError("invalid_scanned_row_count")
        if (item["newlyScannedRows"]>10*len(pages) or
            item["exactApplicationRows"]+
            item["registrationTypeExcluded"]+
            item["unrelatedApplicationExcluded"]>item["newlyScannedRows"] or
            item["exactApplicationWithProjectOutsideOlderSubset"]>item["exactApplicationRows"]):
            raise ValueError("impossible_outcome_classification")
        if expected["strategy"]=="technology_next_pages":
            if item["newQueryTotalHits"] is not None:
                raise ValueError("technological_pagination_not_new_query_total")
        else:
            if pages and (type(item["newQueryTotalHits"]) is not int or
                          item["newQueryTotalHits"]<item["newlyScannedRows"]):
                raise ValueError("incorrect_new_combined_query_count")
        if item["truncated"] is not True and item["truncated"] is not False:
            raise ValueError("missing_pagination_limit_label")
        rows+=item["newlyScannedRows"]
        outside+=item["exactApplicationWithProjectOutsideOlderSubset"]
        queryChecks[(item["strategy"],item["query"])]=item
    if (export["completedQueries"]!=done or export["failedQueries"]!=failed or
        export["additionalScannedRows"]!=rows or
        export["applicationMatchRowsOutsideOldProjectSubset"]!=outside or
        export["actualHttpRequests"]<pages_checked or
        export["actualHttpRequests"]>pages_checked+failed):
        raise ValueError("inconsistent_followup_totals")
    if export["status"]=="ready" and (failed or done!=plan["uniqueQueries"]):
        raise ValueError("false_followup_success")
    if export["status"]=="partial_errors" and not failed:
        raise ValueError("false_error_status")
    keys=set()
    for result in export["records"]:
        if not isinstance(result,dict) or set(result)!=RECORD:
            raise ValueError("unexpected_number_match_record")
        if result["registType"]!="출원" or str(result["registTypeCode"])!="01":
            raise ValueError("registered_number_is_not_application")
        if (normalize(result.get("registNumberRaw"))!=result.get("patentApplicationNumber")
            or result["officialFieldsInSameHit"] is not True or
            result["patentProjectLinkConfirmed"] is not False or
            result["commercializationConfirmed"] is not False or
            result["exclusiveConfirmed"] is not False):
            raise ValueError("non_official_match_or_false_certainty")
        pub,app,pid=result["publicationNumber"],result["patentApplicationNumber"],result["projectNumber"]
        if not APP.fullmatch(str(pub)) or not APP.fullmatch(str(app)) or not PROJ.fullmatch(str(pid)):
            raise ValueError("bad_application_or_project_number")
        if result["projectInOlder26ProjectSubset"] is not (pid in previous_projects):
            raise ValueError("incorrect_old_sample_membership")
        if not RESULT.fullmatch(str(result.get("officialOutcomeId") or "")):
            raise ValueError("unrecognized_official_result_id")
        q=queryChecks.get((result["strategy"],result["query"]))
        if not q or q["status"] not in ("checked","source_error") or result["page"] not in q["pagesCompleted"]:
            raise ValueError("result_not_backed_by_scanned_page")
        if not any(t["publicationNumber"]==pub and t["applicationNumber"]==app
                   for t in q["targets"]):
            raise ValueError("result_not_target_application")
        for name in ("outcomeTitle","projectTitle","performingAgency"):
            value=result.get(name)
            if not isinstance(value,str) or len(value)>200 or "<" in value or ">" in value:
                raise ValueError("unsafe_html_in_official_record")
        key=(pub,pid,result["officialOutcomeId"])
        if key in keys:raise ValueError("duplicated_official_evidence")
        keys.add(key)
    if export["exactApplicationProjectNumberReviewCandidates"]!=len(keys):
        raise ValueError("false_number_match_count")
    payload=json.dumps(export,ensure_ascii=False)
    if SECRET.search(payload):raise ValueError("possible_api_key_exposure")
    return {"status":export["status"],"newRequests":export["actualHttpRequests"],
            "additionalRows":rows,"reviewPairs":len(keys),
            "olderSource":export["sourceDossierGeneratedAt"]}

def main():
    cli=argparse.ArgumentParser()
    cli.add_argument("file")
    cli.add_argument("--plan",default="digests/ntis_patent_followup_plan_latest.json")
    cli.add_argument("--source",default="digests/ntis_patent_discovery_pc_latest.json")
    cli.add_argument("--projects",default="digests/ntis_project_leads_latest.json")
    args=cli.parse_args()
    read=lambda path:json.loads(Path(path).read_text(encoding="utf-8-sig"))
    print("NTIS approved-PC follow-up validated:",
          validate(read(args.file),read(args.plan),read(args.source),read(args.projects)))

if __name__=="__main__":main()
