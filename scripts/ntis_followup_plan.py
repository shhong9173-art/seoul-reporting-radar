"""Bounded NTIS rpatent follow-up plan grounded in the approved-PC 21-query audit.

The 2026-10-14 source contains 21 queries / 136 inspected rows; 12 searches
are truncated. Do NOT enumerate huge applicant-name queries. Restrict
pagination to four technical phrases <= 300 total hits, with page 2 and 3
(max 10 records each). Replace broad corporate-only re-runs by narrower
corporate + technical phrases (documented query field, not a guaranteed AND).

A plan is historical: tied to the exact discovery source timestamp, NOT to
whatever today's KIPRIS dossier happens to say.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from datetime import datetime, timezone

PROFILE="ntis_rpatent_followup_v1"
SOURCE_PROFILE="ntis_rpatent_2024_manual_keyword_discovery_v1"
MODES={"technology","title","applicant"}

def build(source,generated_at):
    if (source.get("status")!="ready" or
        source.get("mappingProfile")!=SOURCE_PROFILE or
        source.get("completedQueries")!=21 or source.get("failedQueries")!=0 or
        len(source.get("checks",[]))!=21):
        raise ValueError("untrusted_previous_discovery_snapshot")
    if not generated_at or datetime.fromisoformat(generated_at).utcoffset() is None:
        raise ValueError("generated_at_must_include_timezone")
    by_pub={}
    seen_modes=set()
    for q in source["checks"]:
        if not isinstance(q,dict) or q.get("status")!="checked":
            raise ValueError("unverified_query")
        pub=q.get("publicationNumber")
        app=q.get("applicationNumber")
        if not isinstance(pub,str) or not pub.startswith("10") or len(pub)!=13:
            raise ValueError("invalid_publication")
        if not isinstance(app,str) or not app.startswith("10") or len(app)!=13:
            raise ValueError("invalid_application")
        mode,term=q.get("mode"),q.get("query")
        if mode not in MODES or not isinstance(term,str) or len(term)<2:
            raise ValueError("invalid_source_search")
        if (pub,mode) in seen_modes:
            raise ValueError("duplicated_mode_in_source")
        seen_modes.add((pub,mode))
        patent=by_pub.setdefault(pub,{"publicationNumber":pub,"applicationNumber":app})
        if patent["applicationNumber"]!=app:
            raise ValueError("inconsistent_kipris_application")
        patent[mode]=q
    tasks=[]
    queries={}
    def add(query, strategy, pages, target, source_hits):
        if not pages:
            return
        key=(query,tuple(pages))
        if key in queries:
            item=queries[key]
            if (item["strategy"]!=strategy or item["sourceTotalHits"]!=source_hits):
                raise ValueError("conflicting_duplicate_query")
            if target not in item["targets"]:
                item["targets"].append(target)
            return
        entry={
            "query":query,
            "strategy":strategy,
            "pages":pages,
            "sourceTotalHits":source_hits,
            "targets":[target],
        }
        queries[key]=entry
        tasks.append(entry)
    for pub,row in by_pub.items():
        tech=row.get("technology")
        if not tech:
            continue
        total=tech.get("totalHits")
        if (tech.get("truncated") is True and tech.get("pagesChecked")==1 and
            type(total) is int and 20<total<=300 and
            tech.get("rowsExamined")==10):
            pages=[page for page in (2,3) if 1+(page-1)*10<=total]
            add(tech["query"],"technology_next_pages",pages,{
                "publicationNumber":pub,
                "applicationNumber":row["applicationNumber"],
            },total)
    # No bare applicant-name query: some source queries were 3154 total hits.
    for pub,row in by_pub.items():
        tech=row.get("technology")
        applicant=row.get("applicant")
        if not tech or not applicant:
            continue
        # The NTIS broad field might interpret multiple tokens differently:
        # a successful response alone never proves logical AND semantics.
        query=f'{applicant["query"]} {tech["query"]}'
        if len(query)>70:
            continue
        add(query,"corporate_technology_narrowing",[1],{
            "publicationNumber":pub,
            "applicationNumber":row["applicationNumber"],
        },None)
    unique_applicants=len({x["applicant"]["query"] for x in by_pub.values() if "applicant" in x})
    plan={
        "planVersion":PROFILE,
        "generatedAt":generated_at,
        "sourceDiscoveryGeneratedAt":source["generatedAt"],
        "sourceDossierGeneratedAt":source["dossierGeneratedAt"],
        "sourceKiprisDeepGeneratedAt":source["kiprisDeepGeneratedAt"],
        "sourceNtisProjectsGeneratedAt":source["ntisProjectsGeneratedAt"],
        "sourceNtisProjectDossierGeneratedAt":source["ntisProjectDossierGeneratedAt"],
        "sourceQueryCount":len(source["checks"]),
        "sourceTruncatedQueries":sum(q["status"]=="checked" and q["truncated"] for q in source["checks"]),
        "sourceRowsScanned":source["scannedOutcomeRows"],
        "applicantQueriesNotRepeated":sum(q["mode"]=="applicant" for q in source["checks"]),
        "duplicateBareApplicantSearchesAvoided":sum(q["mode"]=="applicant" for q in source["checks"])-unique_applicants,
        "uniqueQueries":len(tasks),
        "maximumHttpRequests":sum(len(t["pages"]) for t in tasks),
        "tasks":tasks,
        "warning":"This is targeted follow-up of a historical 2026-10-14 snapshot. Company+technology is an exploratory NTIS query, not a verified Boolean AND. Results are page-limited; only exact RegistType=출원 and KIPRIS application plus official ProjectID in the SAME HIT can be reviewed. No exclusive/product claim.",
    }
    return plan

def validate_plan(plan, source):
    if not isinstance(plan,dict) or plan.get("planVersion")!=PROFILE:
        raise ValueError("unrecognized_followup_plan")
    expected=build(source,plan.get("generatedAt"))
    if plan!=expected:
        raise ValueError("plan_does_not_match_approved_source")
    if plan["maximumHttpRequests"]>25 or plan["uniqueQueries"]>14:
        raise ValueError("excessive_followup_budget")
    return {
        "queries":plan["uniqueQueries"],
        "boundedRequests":plan["maximumHttpRequests"],
        "repeatCompanyQueriesAvoided":plan["duplicateBareApplicantSearchesAvoided"],
        "sourceTruncatedQueries":plan["sourceTruncatedQueries"],
    }

def main():
    cli=argparse.ArgumentParser()
    cli.add_argument("--source",default="digests/ntis_patent_discovery_pc_latest.json")
    cli.add_argument("--plan",default="digests/ntis_patent_followup_plan_latest.json")
    cli.add_argument("--write",action="store_true")
    args=cli.parse_args()
    source=json.loads(Path(args.source).read_text(encoding="utf-8-sig"))
    dest=Path(args.plan)
    if args.write:
        now=datetime.now(timezone.utc).isoformat(timespec="seconds")
        plan=build(source,now)
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(plan,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    else:
        plan=json.loads(dest.read_text(encoding="utf-8-sig"))
    print("NTIS follow-up validated:",validate_plan(plan,source))

if __name__=="__main__":
    main()
