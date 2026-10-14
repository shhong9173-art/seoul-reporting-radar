"""Build and check NTIS rpatent reverse-lookup plan from *actual* approved-PC project results.

Use official 2024 NTIS rpatent manual: searchFd TI covers patent title and
과제고유번호; detailed addQuery TI03 is 과제고유번호. The successful prior
Windows PC REST requests used query/searchField/displayCount aliases.

This file creates the historically pinned input list, NOT a claim that
an NTIS project has patent outcomes. A search returning zero isn't evidence
of absence, and keywords returned by public_project weren't patent proof.
"""
from __future__ import annotations
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

PROFILE="ntis_rpatent_reverse_projectid_v1"
PROJ=re.compile(r"^\d{10}$")
APP=re.compile(r"^10\d{11}$")
MAX_PROJECTS=26

def project_ids(source):
    """Unique verified IDs from checks, retaining a bounded provenance trail."""
    if source.get("status")!="ready" or source.get("collectionMethod")!="approved_pc_local_manual_review":
        raise ValueError("not_approved_pc_project_snapshot")
    result={}
    for check in source.get("checks",[]):
        if check.get("status")!="checked":
            continue
        for item in check.get("records",[]):
            pid=str(item.get("projectNumber",""))
            if not PROJ.fullmatch(pid):
                continue
            title=item.get("projectTitle")
            year=str(item.get("projectYear") or "")
            if not isinstance(title,str) or not title.strip() or len(title)>280:
                raise ValueError("invalid_official_project_title")
            if not re.fullmatch(r"20\d{2}",year):
                raise ValueError("invalid_official_project_year")
            year_num=int(year)
            entry=result.setdefault(pid,{
                "projectNumber":pid,
                "projectTitle":title,
                "projectYear":year,
                "performingAgency":str(item.get("performingAgency") or "")[:120],
                "earlierKeywordMatchedPatentPublications":[],
                "earlierKeywordMatchedQueries":[],
                "sourceRecordOccurrences":0,
            })
            if entry["projectTitle"]!=title or entry["projectYear"]!=year:
                raise ValueError("conflicting_official_project_metadata")
            entry["sourceRecordOccurrences"]+=1
            pub=str(check.get("publicationNumber") or "")
            if pub and pub not in entry["earlierKeywordMatchedPatentPublications"]:
                entry["earlierKeywordMatchedPatentPublications"].append(pub)
            term=str(check.get("query") or "")
            if term and term not in entry["earlierKeywordMatchedQueries"]:
                entry["earlierKeywordMatchedQueries"].append(term)
    return result

def verified_target_applications(dossier,deep):
    seen={}
    for item in deep.get("investigations",[]):
        pub=item.get("publicationNumber")
        app=item.get("applicationNumber")
        if isinstance(pub,str) and isinstance(app,str) and APP.fullmatch(app):
            seen.setdefault(pub,set()).add(app)
    candidates=[]
    for item in dossier.get("dossiers",[]):
        pub=item.get("publicationNumber")
        matches=seen.get(pub,set())
        if len(matches)==1:
            candidates.append({"publicationNumber":pub,
                               "applicationNumber":next(iter(matches))})
    if len(candidates)!=len({x["publicationNumber"] for x in candidates}):
        raise ValueError("duplicate_kipris_target")
    return candidates

def build(source,dossier,deep,now=None):
    if now is None:
        now=datetime.now(timezone.utc).isoformat(timespec="seconds")
    if datetime.fromisoformat(now).utcoffset() is None:
        raise ValueError("plan_time_has_no_timezone")
    projects=project_ids(source)
    if len(projects)!=MAX_PROJECTS:
        raise ValueError(f"project_count_changed:{len(projects)}")
    targets=verified_target_applications(dossier,deep)
    if not targets:
        raise ValueError("no_official_kipris_target_application_numbers")
    # Year priority is only an operational search order, NOT newsworthiness.
    tasks=sorted(projects.values(),key=lambda x:(-int(x["projectYear"]),x["projectNumber"]))
    return {
        "planVersion":PROFILE,
        "generatedAt":now,
        "projectSourceGeneratedAt":source["generatedAt"],
        "projectSourceDossierGeneratedAt":source["dossierGeneratedAt"],
        "kiprisDossierGeneratedAt":dossier["generatedAt"],
        "kiprisDeepGeneratedAt":deep["generatedAt"],
        "projectCount":len(tasks),
        "maxPrimaryQueries":len(tasks),
        "maxFallbackQueries":len(tasks),
        "absoluteMaxHttpRequests":2*len(tasks),
        "searchProfilePrimary":"query=ProjectID;searchField=TI;addQuery=DBT=PAT",
        "searchProfileFallback":"query=ProjectID;searchField=TI;addQuery=TI03=ProjectID&DBT=PAT",
        "fallbackStatus":"manual_field_documented_but_live_indexing_not_yet_verified",
        "maxRowsPerQuery":10,
        "projects":tasks,
        "targetKiprisApplications":targets,
        "warnings":[
            "Earlier project matches were broad keyword matches, not proven patent outputs.",
            "NTIS TI field includes project ID per official manual; TI03 detailed field is documented but actual index behavior requires registered-PC testing.",
            "Every returned patent outcome MUST have ProjectID matching requested project and RegistType=출원(code 01) plus RegistNumber matching same KIPRIS APPLICATION, not publication or registration.",
            "Only first 10 results per query will be scanned; 0 results or 0 matched applications never proves no R&D patent outcome.",
            "Matching identifier pairs are reporting leads; no patent commercialization, company participation or exclusive reporting is automatically confirmed."
        ],
    }

def validate_plan(plan,source,dossier,deep):
    if not isinstance(plan,dict) or plan.get("planVersion")!=PROFILE:
        raise ValueError("not_ntis_project_reverse_plan")
    canonical=build(source,dossier,deep,plan.get("generatedAt"))
    if plan!=canonical:
        raise ValueError("reverse_plan_or_source_mismatch")
    return {"projects":plan["projectCount"],
            "maximumCalls":plan["absoluteMaxHttpRequests"],
            "targetApplications":len(plan["targetKiprisApplications"]),
            "sourceAt":plan["projectSourceGeneratedAt"]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",default="digests/ntis_project_leads_latest.json")
    p.add_argument("--dossier",default="digests/patent_rnd_dossiers_latest.json")
    p.add_argument("--deep",default="digests/patent_deep_latest.json")
    p.add_argument("--out",default="digests/ntis_project_reverse_plan_latest.json")
    p.add_argument("--write",action="store_true")
    a=p.parse_args()
    read=lambda s:json.loads(Path(s).read_text(encoding="utf-8-sig"))
    source,dossier,deep=read(a.source),read(a.dossier),read(a.deep)
    f=Path(a.out)
    if a.write:
        plan=build(source,dossier,deep)
        f.write_text(json.dumps(plan,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    else:
        plan=read(f)
    print("NTIS project reverse plan:",validate_plan(plan,source,dossier,deep))

if __name__=="__main__":
    main()
