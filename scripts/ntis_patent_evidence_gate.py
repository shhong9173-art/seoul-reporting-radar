"""Source-bounded NTIS/KIPRIS evidence overlay for patent editorial triage.

A keyword-related national project is not a patent outcome, company
participation, business application or scoop. Unscanned rows are unknown.
This module never changes editorial approval or the exclusive flag.
"""
from __future__ import annotations
from collections import defaultdict
from pathlib import Path
import json
import re

PROJECT=re.compile(r"^\d{10}$")
PUB=re.compile(r"^10\d{11}$")
APP=re.compile(r"^10\d{11}$")
STATUS="bounded_ntis_rpatent_reverse_not_a_business_link"

def build_evidence(plan,pilot,remaining,followup=None):
    if (plan.get("planVersion")!="ntis_rpatent_reverse_projectid_v1"
        or len(plan.get("projects",[]))!=26
        or len(plan.get("targetKiprisApplications",[]))!=7):
        raise ValueError("ntis_plan_invalid")
    if (pilot.get("planGeneratedAt")!=plan.get("generatedAt")
        or remaining.get("planGeneratedAt")!=plan.get("generatedAt")
        or pilot.get("plannedUniqueProjects")!=3
        or remaining.get("plannedUniqueProjects")!=23
        or pilot.get("status")!="ready" or remaining.get("status")!="ready"):
        raise ValueError("ntis_source_mismatch")
    checks=[*pilot.get("checks",[]),*remaining.get("checks",[])]
    if ([p.get("projectNumber") for p in plan["projects"]]!=
        [p.get("projectNumber") for p in checks] or
        any(c.get("status")!="checked" for c in checks)):
        raise ValueError("ntis_projects_or_checks_changed")
    apps={p["publicationNumber"]:p["applicationNumber"] for p in
          plan["targetKiprisApplications"]}
    if (len(apps)!=7 or
        any(not PUB.fullmatch(pub) or not APP.fullmatch(app) for pub,app in apps.items())):
        raise ValueError("ntis_frozen_patents_changed")
    projects_by_pub=defaultdict(set)
    for p in plan["projects"]:
        if not PROJECT.fullmatch(str(p.get("projectNumber") or "")):
            raise ValueError("invalid_ntis_project")
        for pub in p.get("earlierKeywordMatchedPatentPublications",[]):
            if PUB.fullmatch(str(pub)):
                projects_by_pub[pub].add(p["projectNumber"])
    found=defaultdict(set)
    def take_rows(rows):
        for r in rows:
            pub=r.get("publicationNumber")
            app=r.get("applicationNumber")
            pid=r.get("projectNumber")
            if (pub not in apps or app!=apps[pub]
                or pid not in {c["projectNumber"] for c in checks}
                or r.get("sourceProjectID")!=pid
                or r.get("sourceRegistType")!="출원"
                or str(r.get("sourceRegistTypeCode"))!="01"
                or re.sub(r"[\s-]","",str(r.get("sourceRegistNumber","")))!=app
                or r.get("sameOfficialHitIdentifiers") is not True
                or r.get("officialPatentProjectOutcomeVerified") is not False
                or r.get("commercializationConfirmed") is not False
                or r.get("exclusiveConfirmed") is not False):
                raise ValueError("invalid_ntis_pair_cannot_be_ranked")
            found[pub].add((pid,r.get("officialResultID")))
    for s in (pilot,remaining):
        if (s.get("verifiedPatentProjectOutcomes")!=0 or
            s.get("confirmedExclusives")!=0 or
            s.get("confirmedCommercialization")!=0 or
            s.get("reviewedNumberPairs")!=len(s.get("records",[]))):
            raise ValueError("unverified_ntis_source")
        take_rows(s["records"])
    closed=set()
    if followup is not None:
        # Called only after separate actual JSON validator has succeeded.
        if (followup.get("collectionMethod")!="approved_pc_ntis_rpatent_targeted_page_followup"
            or followup.get("offlineSynthetic") is not False
            or followup.get("sourceReverseGeneratedAt")!=remaining.get("generatedAt")
            or followup.get("planGeneratedAt")!=plan["generatedAt"]
            or followup.get("projectNumber")!="1415180715"
            or followup.get("currentQueryFullyInspected") is not True
            or followup.get("paginationConfirmedByDisjointIds") is not True
            or followup.get("rowsInspected")!=11 or followup.get("distinctResultIDs")!=11
            or followup.get("verifiedPatentProjectOutcomes")!=0
            or followup.get("confirmedCommercialization")!=0
            or followup.get("confirmedExclusives")!=0):
            raise ValueError("unverified_ntis_followup")
        take_rows(followup["records"])
        closed.add("1415180715")
    missing={c["projectNumber"] for c in checks
             if c.get("uninspectedPagesRemain") is True and c["projectNumber"] not in closed}
    out={}
    for pub in projects_by_pub.keys()|apps.keys():
        related=projects_by_pub.get(pub,set())
        review_pairs=len(found[pub])
        uninspected=len(missing & related)
        if pub not in apps:
            stage="keyword_only_no_frozen_kipris_application"
            pairs=None # number-pair comparison wasn't authorized for this patent
        elif review_pairs:
            stage="same_official_hit_number_pair_for_human_review"
            pairs=review_pairs
        elif uninspected:
            stage="partially_inspected_no_official_pair_observed"
            pairs=0
        else:
            stage="bounded_inspected_no_official_pair_observed"
            pairs=0
        out[pub]={
            "status":stage,
            "frozenKiprisApplicationAvailable":pub in apps,
            "keywordRelatedProjectCount":len(related),
            "officialNumberPairsForHumanReview":pairs,
            "uninspectedRelatedProjectCount":uninspected,
            "sourceStatus":STATUS,
            "projectParticipationVerified":False,
            "businessApplicationVerified":False,
            "exclusiveProven":False
        }
    return out

def load_evidence(root:Path=Path(".")):
    read=lambda p:json.loads((root/p).read_text(encoding="utf-8-sig"))
    paths=("digests/ntis_project_reverse_plan_latest.json",
           "digests/ntis_project_reverse_pc_latest.json",
           "digests/ntis_project_reverse_remaining_23_pc_latest.json")
    if not all((root/p).is_file() for p in paths):
        return None
    plan,pilot,remaining=(read(p) for p in paths)
    follow_path=root/"digests/ntis_project_page_followup_pc_latest.json"
    follow=None
    if follow_path.is_file():
        follow=read(str(follow_path.relative_to(root)))
        # Same validation used by import CI, never accept a synthetic fixture.
        from ntis_project_page_followup_validate import validate
        pinned=read("digests/ntis_project_reverse_kipris_source.json")
        validate(follow,plan,remaining,pinned)
    return build_evidence(plan,pilot,remaining,follow)
