"""Fail-closed import check for NTIS reverse project-ID patent outcome searches.

The 2024 official rpatent API includes ProjectID, RegistNumber and RegistType
in the SAME HIT. TI is a documented patent-name/project-ID field, and TI03
is a detailed project-ID filter. Their live indexing semantics are unproven
until this approved-PC JSON has been collected.

Exact ProjectID + RegistType=출원(code 01) + KIPRIS APPLICATION number is
strictly an investigative number-pair lead, not publication, commercialization
or an exclusive scoop.
"""
from __future__ import annotations
import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from ntis_project_reverse_plan import validate_plan

ID=re.compile(r"^\d{10}$")
APP=re.compile(r"^10\d{11}$")
RESULT=re.compile(r"^[A-Za-z0-9_-]{5,100}$")
SECRETS=re.compile(r"(?i)apprvKey|authorization|bearer\s|api[_-]?key|password|secret")
ROOT={
    "generatedAt","planVersion","planGeneratedAt","projectSourceGeneratedAt",
    "projectSourceDossierGeneratedAt","kiprisDossierGeneratedAt",
    "kiprisDeepGeneratedAt","status","collectionMethod",
    "plannedUniqueProjects","completedProjects","failedProjects",
    "actualHttpRequests","maximumHttpRequests","primaryQueriesCompleted",
    "fallbackQueriesCompleted","rowsInspected","matchedOfficialProjectApplicationRows",
    "reviewedNumberPairs","verifiedPatentProjectOutcomes",
    "confirmedCommercialization","confirmedExclusives","checks","records","warning",
}
CHECK={
    "projectNumber","projectYear","projectTitle","performingAgency",
    "earlierKeywordPatentPublications","status","errorClass",
    "searchModesCompleted","primaryTotalHits","fallbackTotalHits",
    "rowsInspected","exactProjectIdRows","differentProjectIdRowsExcluded",
    "registrationTypeRowsExcluded","applicationTypeRows",
    "matchingKiprisApplicationRows","uninspectedPagesRemain",
}
RECORD={
    "projectNumber","publicationNumber","applicationNumber",
    "officialResultID","sourceRegistNumber","sourceRegistType",
    "sourceRegistTypeCode","sourceProjectID","resultTitle","projectTitle",
    "performingAgency","searchMode","sameOfficialHitIdentifiers",
    "officialPatentProjectOutcomeVerified","commercializationConfirmed",
    "exclusiveConfirmed",
}

def normal_patent(value):
    value=re.sub(r"[\s-]","",str(value or ""))
    return value if APP.fullmatch(value) else None

def validate(result,plan,projects,dossier,deep):
    if not isinstance(result,dict) or set(result)!=ROOT:
        raise ValueError("unexpected_reverse_output_schema")
    validate_plan(plan,projects,dossier,deep)
    if (result["planVersion"]!=plan["planVersion"] or
        result["planGeneratedAt"]!=plan["generatedAt"] or
        result["projectSourceGeneratedAt"]!=plan["projectSourceGeneratedAt"] or
        result["projectSourceDossierGeneratedAt"]!=plan["projectSourceDossierGeneratedAt"] or
        result["kiprisDossierGeneratedAt"]!=plan["kiprisDossierGeneratedAt"] or
        result["kiprisDeepGeneratedAt"]!=plan["kiprisDeepGeneratedAt"]):
        raise ValueError("reverse_source_snapshot_mismatch")
    if result["collectionMethod"]!="approved_pc_ntis_rpatent_reverse_projectid":
        raise ValueError("unknown_collection_method")
    if result["status"] not in ("ready","partial_errors","incomplete"):
        raise ValueError("unknown_pc_collection_status")
    try:
        if datetime.fromisoformat(result["generatedAt"]).utcoffset() is None:
            raise ValueError()
    except (TypeError,ValueError):
        raise ValueError("generated_timestamp_without_timezone") from None
    if (result["verifiedPatentProjectOutcomes"]!=0 or
        result["confirmedCommercialization"]!=0 or
        result["confirmedExclusives"]!=0):
        raise ValueError("unjustified_published_rnd_or_scoop_claim")
    for k in ("plannedUniqueProjects","completedProjects","failedProjects",
              "actualHttpRequests","maximumHttpRequests","primaryQueriesCompleted",
              "fallbackQueriesCompleted","rowsInspected",
              "matchedOfficialProjectApplicationRows","reviewedNumberPairs"):
        if type(result.get(k)) is not int or result[k]<0:
            raise ValueError("invalid_statistical_field")
    planned=result["plannedUniqueProjects"]
    # 2026-10-15 first pilot was collected with the original absolute 52-call
    # plan ceiling. All NEW registered-PC exports must use the strict runtime
    # ceiling of 2 requests per selected project.
    historical_pilot=(planned==3 and
        result["generatedAt"]=="2026-10-15T09:57:05+09:00" and
        result["maximumHttpRequests"]==52)
    max_matches=(result["maximumHttpRequests"]==2*planned) or historical_pilot
    if (not 1<=planned<=26 or
        not max_matches or
        result["actualHttpRequests"]>result["maximumHttpRequests"] or
        not isinstance(result["checks"],list) or
        not isinstance(result["records"],list) or
        len(result["checks"])>26 or len(result["records"])>70):
        raise ValueError("excessive_unbounded_reverse_data")
    if len(result["checks"])>result["plannedUniqueProjects"]:
        raise ValueError("too_many_checked_projects")
    projects_in_plan={p["projectNumber"]:p for p in plan["projects"]}
    # Follow-up run must skip ONLY the three projects actually collected in
    # the 2026-10-15 pilot. Old 3-project output stays separately archived.
    expected_set=(plan["projects"][3:] if planned==23 else
                  plan["projects"][:planned])
    expected_order=[x["projectNumber"] for x in expected_set]
    actual_order=[x.get("projectNumber") for x in result["checks"]]
    if actual_order!=expected_order[:len(actual_order)]:
        raise ValueError("reverse_project_subset_or_order_mismatch")
    targets={(a["publicationNumber"],a["applicationNumber"])
             for a in plan["targetKiprisApplications"]}
    completed=failed=primary=fallback=scanned=matched=0
    prior={}
    for row in result["checks"]:
        if not isinstance(row,dict) or set(row)!=CHECK:
            raise ValueError("reverse_check_has_unknown_fields")
        pid=row.get("projectNumber")
        if pid not in projects_in_plan or pid in prior:
            raise ValueError("unknown_or_duplicate_project_number")
        official=projects_in_plan[pid]
        for k in ("projectYear","projectTitle","performingAgency"):
            if row.get(k)!=official.get(k):
                raise ValueError("project_metadata_not_official")
        if row.get("earlierKeywordPatentPublications")!=official.get("earlierKeywordMatchedPatentPublications"):
            raise ValueError("keyword_source_provenance_changed")
        prior[pid]=row
        modes=row.get("searchModesCompleted")
        if not isinstance(modes,list) or modes not in ([],["primary"],["primary","ti03"]):
            raise ValueError("unapproved_reverse_query_mode")
        if row["status"]=="checked":
            completed+=1
            if not modes or row["errorClass"] is not None:
                raise ValueError("false_success_without_official_response")
            if row["primaryTotalHits"] is None:
                raise ValueError("missing_primary_search_hits")
            if "ti03" in modes and row["primaryTotalHits"]!=0:
                raise ValueError("fallback_not_conditional_on_zero_primary")
            if "ti03" not in modes and row["fallbackTotalHits"] is not None:
                raise ValueError("fallback_count_without_search")
        elif row["status"]=="source_error":
            failed+=1
            if not isinstance(row["errorClass"],str) or not row["errorClass"]:
                raise ValueError("source_error_not_labeled")
        else:
            raise ValueError("invalid_check_status")
        for field in ("rowsInspected","exactProjectIdRows","differentProjectIdRowsExcluded",
                      "registrationTypeRowsExcluded","applicationTypeRows",
                      "matchingKiprisApplicationRows"):
            if type(row.get(field)) is not int or row[field]<0:
                raise ValueError("negative_or_untyped_observation")
        for k in ("primaryTotalHits","fallbackTotalHits"):
            if row[k] is not None and (type(row[k]) is not int or row[k]<0):
                raise ValueError("invalid_search_index_total")
        if (row["rowsInspected"]>20 or
            row["exactProjectIdRows"]+row["differentProjectIdRowsExcluded"]>row["rowsInspected"] or
            row["applicationTypeRows"]+row["registrationTypeRowsExcluded"]>row["exactProjectIdRows"] or
            row["matchingKiprisApplicationRows"]>row["applicationTypeRows"]):
            raise ValueError("impossible_typed_result_counts")
        if row["uninspectedPagesRemain"] is not True and row["uninspectedPagesRemain"] is not False:
            raise ValueError("missing_pagination_warning")
        scanned+=row["rowsInspected"]
        matched+=row["matchingKiprisApplicationRows"]
        primary+=int("primary" in modes)
        fallback+=int("ti03" in modes)
    if (result["completedProjects"]!=completed or
        result["failedProjects"]!=failed or
        result["primaryQueriesCompleted"]!=primary or
        result["fallbackQueriesCompleted"]!=fallback or
        result["rowsInspected"]!=scanned or
        result["actualHttpRequests"]<primary+fallback or
        result["actualHttpRequests"]>primary+fallback+failed):
        raise ValueError("reverse_counts_do_not_match_records")
    if result["status"]=="ready" and (failed!=0 or completed!=result["plannedUniqueProjects"]):
        raise ValueError("false_reverse_ready_status")
    if result["status"]=="partial_errors" and failed==0:
        raise ValueError("false_reverse_partial_errors")
    seen=set()
    for row in result["records"]:
        if not isinstance(row,dict) or set(row)!=RECORD:
            raise ValueError("unexpected_patent_project_link_fields")
        pid=row.get("projectNumber")
        pair=(row.get("publicationNumber"),row.get("applicationNumber"))
        if (pid not in prior or prior[pid]["status"]!="checked" or
            pair not in targets or
            row.get("sourceProjectID")!=pid):
            raise ValueError("patent_application_or_project_not_in_verified_sources")
        if row.get("sourceRegistType")!="출원" or str(row.get("sourceRegistTypeCode"))!="01":
            raise ValueError("registered_patent_misread_as_application")
        if normal_patent(row.get("sourceRegistNumber"))!=pair[1]:
            raise ValueError("wrong_application_number_for_ntis_result")
        if row.get("searchMode") not in prior[pid]["searchModesCompleted"]:
            raise ValueError("no_supporting_checked_reverse_query")
        if (row.get("sameOfficialHitIdentifiers") is not True or
            row.get("officialPatentProjectOutcomeVerified") is not False or
            row.get("commercializationConfirmed") is not False or
            row.get("exclusiveConfirmed") is not False):
            raise ValueError("unjustified_outcome_or_commercialization_certainty")
        if not RESULT.fullmatch(str(row.get("officialResultID") or "")):
            raise ValueError("invalid_official_result_id")
        for key in ("resultTitle","projectTitle","performingAgency"):
            value=row.get(key)
            if not isinstance(value,str) or len(value)>200 or "<" in value or ">" in value:
                raise ValueError("untrusted_ntis_result_html")
        unique=(pid,pair[0],row["officialResultID"])
        if unique in seen:
            raise ValueError("duplicate_patent_project_pair")
        seen.add(unique)
    if (result["reviewedNumberPairs"]!=len(seen) or
        result["matchedOfficialProjectApplicationRows"]!=len(seen) or
        result["reviewedNumberPairs"]>matched):
        raise ValueError("falsified_patent_number_pair_total")
    if SECRETS.search(json.dumps(result,ensure_ascii=False)):
        raise ValueError("suspected_ntis_secret_in_public_json")
    return {
        "status":result["status"],"projects":completed,
        "httpRequests":result["actualHttpRequests"],
        "scannedRows":scanned,"officialPairsForHumanReview":len(seen),
        "uninspectedPages":sum(x["uninspectedPagesRemain"] for x in result["checks"])
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("file")
    p.add_argument("--plan",default="digests/ntis_project_reverse_plan_latest.json")
    p.add_argument("--projects",default="digests/ntis_project_leads_latest.json")
    p.add_argument("--kipris-source",default="digests/ntis_project_reverse_kipris_source.json")
    a=p.parse_args()
    read=lambda filename:json.loads(Path(filename).read_text(encoding="utf-8-sig"))
    pinned=read(a.kipris_source)
    if pinned.get("schema")!="ntis_rpatent_kipris_7_identifiers_frozen_v1" or pinned.get("confirmedProjectOutcomeLinks")!=0:
        raise ValueError("not_verified_pinned_kipris_identity_subset")
    result=read(a.file)
    if result.get("plannedUniqueProjects")==23:
        from ntis_project_field_control_validate import validate as validate_control
        control=read("digests/ntis_project_field_probe_pc_latest.json")
        summary=validate_control(control)
        if (summary["status"]!="some_project_search_paths_work" or
            summary["retrievedReferencePaths"]<3 or summary["errors"]):
            raise ValueError("positive_control_not_verified_before_remaining23")
    print("NTIS project reverse lookup:",validate(result,read(a.plan),
                                                  read(a.projects),pinned["dossier"],
                                                  pinned["deep"]))
if __name__=="__main__":
    main()
