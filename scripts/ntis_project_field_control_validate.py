"""Validate a registered-PC NTIS ProjectID index positive-control probe.

No personal names, unrelated project numbers, HIT XML, or secret-bearing
request URLs are allowed. The only finding permitted is whether a reference
outcome from a known positive rpatent query can be retrieved through distinct
officially documented search-field variants. No commercialization/scoop claim.
"""
import argparse
import json
import re
from datetime import datetime
from pathlib import Path

ROOT={
    "generatedAt","profile","collectionMethod","status",
    "controlSeedTerm","controlSeedTotalHits","controlSeedRowsInspected",
    "officialReferenceProjectAndOutcomeSeenInSeed",
    "controlProjectIdExported","controlResultIdExported",
    "plannedAdditionalControlQueries","completedAdditionalControlQueries",
    "failedAdditionalControlQueries","exactReferenceOutcomeRecoveredInAnyMode",
    "searchModes","verifiedPatentProjectOutcomeLinks",
    "commercializationConfirmed","exclusiveConfirmed","warning",
}
CHECK={
    "mode","status","totalHits","rowsInspected",
    "exactReferenceProjectRows","exactReferenceOutcomeRows",
    "additionalPagesNotChecked","errorClass",
}
MODES=["project_ti","project_bi","project_unscoped","ti03_seed","ti03_project"]
CREDENTIAL=re.compile(r"(?i)apprvKey|authorization|bearer\s|api[_-]?key|password|secret")
UNRELATED_ID=re.compile(r"(?<!\d)\d{10}(?!\d)")
BANNED_SOURCE_FIELDS=("ProjectID","ResultID","RegistNumber","PerformAgency","Registrant")

def validate(data):
    if not isinstance(data,dict) or set(data)!=ROOT:
        raise ValueError("unexpected_index_control_output_fields")
    if (data["profile"]!="ntis_rpatent_project_id_index_control_v1" or
        data["collectionMethod"]!="approved_pc_official_rpatent_field_control" or
        data["controlSeedTerm"]!="부분방전"):
        raise ValueError("unexpected_source_or_search_profile")
    try:
        if datetime.fromisoformat(data["generatedAt"]).utcoffset() is None:
            raise ValueError()
    except (ValueError,TypeError):
        raise ValueError("invalid_control_timestamp") from None
    if data["status"] not in (
        "control_unavailable","partial_errors",
        "some_project_search_paths_work","project_id_retrieval_not_verified",
    ):
        raise ValueError("unknown_positive_control_status")
    for name in ("controlSeedTotalHits","controlSeedRowsInspected",
                 "plannedAdditionalControlQueries","completedAdditionalControlQueries",
                 "failedAdditionalControlQueries"):
        if type(data.get(name)) is not int or data[name]<0:
            raise ValueError("invalid_control_counts")
    if (data["controlSeedTotalHits"]<data["controlSeedRowsInspected"] or
        data["controlSeedRowsInspected"]>10 or
        data["plannedAdditionalControlQueries"]!=5 or
        data["completedAdditionalControlQueries"]+
        data["failedAdditionalControlQueries"]>5):
        raise ValueError("impossible_positive_control_count")
    for name in ("officialReferenceProjectAndOutcomeSeenInSeed",
                 "controlProjectIdExported","controlResultIdExported",
                 "exactReferenceOutcomeRecoveredInAnyMode"):
        if type(data.get(name)) is not bool:
            raise ValueError("untyped_control_status")
    if data["controlProjectIdExported"] or data["controlResultIdExported"]:
        raise ValueError("unrelated_control_identifiers_must_not_be_exported")
    if (data["verifiedPatentProjectOutcomeLinks"]!=0 or
        data["commercializationConfirmed"]!=0 or data["exclusiveConfirmed"]!=0):
        raise ValueError("unauthorized_patent_or_news_certainty")
    modes=data["searchModes"]
    if not isinstance(modes,list) or len(modes)>5:
        raise ValueError("unbounded_control_queries")
    if [m.get("mode") for m in modes]!=MODES[:len(modes)]:
        raise ValueError("unexpected_control_mode_sequence")
    completed=failed=refcount=0
    for item in modes:
        if not isinstance(item,dict) or set(item)!=CHECK:
            raise ValueError("control_mode_unexpected_schema")
        if item["status"]=="checked":
            completed+=1
            if item["errorClass"] is not None:
                raise ValueError("control_success_contains_error")
            for key in ("totalHits","rowsInspected","exactReferenceProjectRows",
                        "exactReferenceOutcomeRows"):
                if type(item[key]) is not int or item[key]<0:
                    raise ValueError("invalid_official_result_counts")
            if (item["rowsInspected"]>10 or item["rowsInspected"]>item["totalHits"] or
                item["exactReferenceProjectRows"]>item["rowsInspected"] or
                item["exactReferenceOutcomeRows"]>item["exactReferenceProjectRows"]):
                raise ValueError("impossible_project_and_result_id_matches")
            if item["additionalPagesNotChecked"] is not (item["totalHits"]>item["rowsInspected"]):
                raise ValueError("wrong_pagination_limit_status")
            refcount+=int(item["exactReferenceOutcomeRows"]>0)
        elif item["status"]=="source_error":
            failed+=1
            if item["totalHits"] is not None or item["rowsInspected"]!=0:
                raise ValueError("source_error_fabricated_results")
            if not isinstance(item["errorClass"],str) or not item["errorClass"].startswith(("NTIS_","UNSAFE_","BAD_","UNRECOGNIZED_","INDEX_","UNEXPECTED_")):
                raise ValueError("unrecognized_safe_error_label")
        else:
            raise ValueError("unknown_search_mode_status")
    if (data["completedAdditionalControlQueries"]!=completed or
        data["failedAdditionalControlQueries"]!=failed or
        data["exactReferenceOutcomeRecoveredInAnyMode"] is not (refcount>0)):
        raise ValueError("control_aggregate_inconsistent")
    if not data["officialReferenceProjectAndOutcomeSeenInSeed"]:
        if data["status"]!="control_unavailable" or modes:
            raise ValueError("no_reference_but_queries_or_success_claim")
    elif failed>0:
        if data["status"]!="partial_errors":
            raise ValueError("source_errors_are_not_success")
    elif completed==5 and refcount>0:
        if data["status"]!="some_project_search_paths_work":
            raise ValueError("recoverable_index_not_reported")
    elif completed==5 and refcount==0:
        if data["status"]!="project_id_retrieval_not_verified":
            raise ValueError("missing_index_not_reported")
    elif data["status"]!="partial_errors":
        raise ValueError("incomplete_control_probe_misreported")
    exported=json.dumps(data,ensure_ascii=False)
    if CREDENTIAL.search(exported):
        raise ValueError("possible_ntis_secret_export")
    if any(f'"{name}"' in exported for name in BANNED_SOURCE_FIELDS):
        raise ValueError("raw_unrelated_ntis_data_exported")
    if UNRELATED_ID.search(exported):
        # Does not flag ISO date timestamps (separators), which are not
        # contiguous ten-digit numeric identifiers.
        raise ValueError("unrelated_project_identifier_leaked")
    return {
        "status":data["status"],
        "checked":completed,
        "errors":failed,
        "baselineHits":data["controlSeedTotalHits"],
        "retrievedReferencePaths":refcount,
        "noUnrelatedIdentifiersOrSecret":True,
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("file")
    a=p.parse_args()
    doc=json.loads(Path(a.file).read_text(encoding="utf-8-sig"))
    print("Official NTIS rpatent ProjectID indexing control:",validate(doc))
if __name__=="__main__":
    main()
