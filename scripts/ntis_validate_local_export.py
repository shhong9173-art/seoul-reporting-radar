"""Validate an NTIS PC-generated public research leads JSON BEFORE publishing.

A local export is researcher-supplied evidence, not an independently verified
NTIS record. Refuse keys, unexpected schemas, unknown patent IDs and mismatched
source snapshots. This does not certify patent-project relevance or exclusivity.
"""
import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

PUB = re.compile(r"^10\d{11}$")
PROJ = re.compile(r"^[A-Za-z0-9-]{4,80}$")
RECORD_KEYS = {
    "projectNumber", "projectTitle", "performingAgency", "projectYear",
    "periodStart", "periodEnd", "researchSummary", "keyword",
    "sourceSearchUrl", "researchLinkConfirmed", "patentOutcomeConfirmed",
    "companyProjectParticipationConfirmed", "commercializationConfirmed",
}
CHECK_KEYS = {
    "publicationNumber", "publicationDate", "patentTitle", "query",
    "checkedAt", "status", "errorClass", "totalHits", "firstPageOnly",
    "records", "sourceEndpointPath",
}
ROOT_KEYS = {
    "generatedAt", "dossierGeneratedAt", "status", "source",
    "requestProfile", "collectionMethod", "scope", "totalResearchQueries",
    "completedQueries", "failedQueries", "remainingQueries",
    "newQueriesThisRun", "sourceRecords", "projectPatentLinksConfirmed",
    "actualApplicationConfirmed", "checks", "warning",
}
SENSITIVE_KEYS = re.compile(r"(?i)apprvKey|authorization|password|secret|api[_-]?key|token")


def validate(export, dossier):
    if not isinstance(export, dict) or set(export) != ROOT_KEYS:
        raise ValueError("unexpected_export_schema")
    if export["collectionMethod"] != "approved_pc_local_manual_review":
        raise ValueError("untrusted_collection_method")
    if export["requestProfile"] != "ntis_2025_pdf_page11_rest_example":
        raise ValueError("unknown_ntis_request_profile")
    if export["dossierGeneratedAt"] != dossier.get("generatedAt") or dossier.get("status") != "research_only":
        raise ValueError("patent_dossier_source_timestamp_mismatch")
    if export["projectPatentLinksConfirmed"] != 0 or export["actualApplicationConfirmed"] != 0:
        raise ValueError("unsupported_project_patent_or_commercialization_claim")
    if export["status"] not in ("ready", "partial_errors", "partial_not_yet_checked", "no_queries"):
        raise ValueError("unaccepted_source_status")
    for key in ("generatedAt",):
        try:
            if datetime.fromisoformat(export[key]).utcoffset() is None:
                raise ValueError()
        except (TypeError, ValueError):
            raise ValueError("missing_timezone") from None
    if not isinstance(export["checks"], list) or len(export["checks"]) > 12:
        raise ValueError("too_many_or_invalid_checks")
    indexed = {
        p["publicationNumber"]: p for p in dossier.get("dossiers", [])
        if isinstance(p, dict) and PUB.fullmatch(str(p.get("publicationNumber") or ""))
    }
    completed = failed = records = 0
    seen = set()
    for row in export["checks"]:
        if not isinstance(row, dict) or not set(row) <= CHECK_KEYS:
            raise ValueError("unknown_check_fields")
        pub, query = row.get("publicationNumber"), row.get("query")
        if pub not in indexed or not isinstance(query, str):
            raise ValueError("unknown_patent_or_query")
        if query not in {
            q.get("query") for q in (indexed[pub].get("ntisResearchQueries") or [])[:2] if isinstance(q, dict)
        } or row.get("publicationDate") != indexed[pub].get("publicationDate"):
            raise ValueError("query_does_not_match_official_dossier")
        if (pub, query) in seen:
            raise ValueError("duplicate_query")
        seen.add((pub, query))
        if row.get("status") == "checked":
            completed += 1
            payload = row.get("records")
            total = row.get("totalHits")
            if (not isinstance(payload, list) or len(payload) > 10 or
                type(total) is not int or total < len(payload) or total > 1000000000):
                raise ValueError("invalid_ntis_results")
            for p in payload:
                if not isinstance(p, dict) or set(p) != RECORD_KEYS:
                    raise ValueError("unexpected_public_project_fields")
                if not PROJ.fullmatch(str(p["projectNumber"])):
                    raise ValueError("invalid_project_identifier")
                if not isinstance(p["projectTitle"], str) or not (1 <= len(p["projectTitle"]) <= 200):
                    raise ValueError("invalid_project_title")
                for key in ("researchLinkConfirmed", "patentOutcomeConfirmed",
                            "companyProjectParticipationConfirmed", "commercializationConfirmed"):
                    if p[key] is not False:
                        raise ValueError("unsupported_confirmation_flag")
                uri = urlsplit(p["sourceSearchUrl"])
                if (uri.scheme != "https" or uri.hostname != "www.ntis.go.kr" or
                    uri.path != "/ThSearchProjectList.do" or
                    parse_qs(uri.query).get("searchWord") != [p["projectNumber"]]):
                    raise ValueError("non_ntis_public_link")
            records += len(payload)
        elif row.get("status") == "source_error":
            failed += 1
            if "records" in row or not isinstance(row.get("errorClass"), str):
                raise ValueError("error_row_has_fake_results")
        else:
            raise ValueError("unknown_ntis_check_status")
    for key, expected in [
        ("completedQueries", completed), ("failedQueries", failed),
        ("newQueriesThisRun", len(export["checks"])), ("sourceRecords", records)
    ]:
        if export[key] != expected:
            raise ValueError("inconsistent_counts_" + key)
    if type(export["totalResearchQueries"]) is not int or export["totalResearchQueries"] != (
        export["newQueriesThisRun"] + export["remainingQueries"]
    ):
        raise ValueError("inconsistent_plan_count")
    if (export["status"] == "ready" and
        (failed > 0 or export["remainingQueries"] > 0)):
        raise ValueError("falsely_claimed_ready")
    if SENSITIVE_KEYS.search(json.dumps(export, ensure_ascii=False)):
        raise ValueError("possible_credential_in_export")
    return {"status": export["status"], "checks": len(export["checks"]),
            "projects": records, "dossierGeneratedAt": export["dossierGeneratedAt"]}


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("file", type=Path)
    cli.add_argument("--dossiers", type=Path,
                     default=Path("digests/patent_rnd_dossiers_latest.json"))
    args = cli.parse_args()
    source = json.loads(args.dossiers.read_text(encoding="utf-8-sig"))
    export = json.loads(args.file.read_text(encoding="utf-8-sig"))
    result = validate(export, source)
    print("NTIS local export structurally valid:", result,
          "; patent/outcome relevance still unverified")


if __name__ == "__main__":
    main()
