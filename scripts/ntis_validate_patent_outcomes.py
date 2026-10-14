"""Validate field-mapped NTIS rpatent PC export against official KIPRIS & NTIS snapshots.

2024 NTIS '성과검색 전체용' manual pp.15-23: in one HIT, ProjectID
(과제고유번호), RegistNumber (출원/등록번호), RegistType (출원/등록구분),
ResultID. Only RegistType=출원 / code 01 may match a KIPRIS application
number. A registration number must NEVER be matched to application/publication.

The user-provided 2026-10-14 probe confirmed these exact XML element names.
A matched number is a REVIEW lead, never proven product use/exclusivity.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

PROFILE = "ntis_rpatent_2024_manual_registtype_application_v1"
PUBLICATION = re.compile(r"^10\d{11}$")
PROJECT = re.compile(r"^\d{10}$")
RESULT = re.compile(r"^[A-Za-z0-9_-]{5,100}$")
ALLOWED_RECORD_KEYS = {
    "publicationNumber","patentApplicationNumber","patentPublicationNumber",
    "projectNumber","sourceOfficialRecordId","sourceFieldMappingVerified",
    "registType","registTypeCode","registNumberRaw","resultTitle",
    "projectTitle","performAgency","resultYear",
}
ALLOWED_ROOT_KEYS = {
    "generatedAt","dossierGeneratedAt","projectSourceGeneratedAt",
    "projectDossierGeneratedAt","kiprisDeepGeneratedAt",
    "status","mappingProfile","collectionMethod","targetCount",
    "completedTargets","errorTargets","matchingOutcomeRows",
    "sampleOutcomeRowsObserved","projectNumbersInKeywordSnapshot",
    "records","checks","confirmedPatentProjectLinks","commercializationConfirmed",
    "exclusiveConfirmed","warning"
}
ALLOWED_CHECK_KEYS={"publicationNumber","applicationNumber","status","totalHits",
                    "rowsObserved","exactApplicationRows","numberProjectMatches",
                    "errorClass"}

def normalize(value):
    val=re.sub(r"[\s-]","",str(value or ""))
    return val if PUBLICATION.fullmatch(val) else None

def kipris_lookup(dossier,deep):
    index={}
    for d in deep.get("investigations",[]):
        pub=normalize(d.get("publicationNumber"))
        app=normalize(d.get("applicationNumber"))
        if pub and app:
            index.setdefault(pub,set()).add(app)
    return {p["publicationNumber"]:next(iter(index[p["publicationNumber"]]))
            for p in dossier.get("dossiers",[])
            if p.get("publicationNumber") in index and len(index[p["publicationNumber"]])==1}

def approved_projects(projects):
    return {str(p["projectNumber"]) for r in projects.get("checks",[])
            if r.get("status")=="checked" for p in (r.get("records") or [])
            if PROJECT.fullmatch(str(p.get("projectNumber") or ""))}

def validate(data,dossier,deep,projects):
    if not isinstance(data,dict) or set(data)!=ALLOWED_ROOT_KEYS:
        raise ValueError("schema_mismatch")
    if data["mappingProfile"]!=PROFILE or data["collectionMethod"]!="approved_pc_rpatent_official_manual":
        raise ValueError("unverified_source_profile")
    if data["status"] not in ("verified_official_patent_outcomes","partial_official_patent_outcomes","source_error"):
        raise ValueError("invalid_outcome_status")
    if (data["projectSourceGeneratedAt"]!=projects.get("generatedAt") or
        data["projectDossierGeneratedAt"]!=projects.get("dossierGeneratedAt") or
        data["dossierGeneratedAt"]!=dossier.get("generatedAt") or
        data["kiprisDeepGeneratedAt"]!=deep.get("generatedAt")):
        raise ValueError("source_timestamps_changed")
    if data["confirmedPatentProjectLinks"]!=0 or data["commercializationConfirmed"]!=0 or data["exclusiveConfirmed"]!=0:
        raise ValueError("unsupported_reporting_claim")
    from datetime import datetime
    if datetime.fromisoformat(data["generatedAt"]).utcoffset() is None:
        raise ValueError("missing_generated_timezone")
    targets=kipris_lookup(dossier,deep)
    project_ids=approved_projects(projects)
    if not isinstance(data["records"],list) or not isinstance(data["checks"],list) or len(data["records"])>100 or len(data["checks"])>30:
        raise ValueError("unbounded_data")
    seen=set()
    for record in data["records"]:
        if not isinstance(record,dict) or set(record)!=ALLOWED_RECORD_KEYS:
            raise ValueError("outcome_record_schema")
        pub=record["publicationNumber"]
        app=normalize(record["patentApplicationNumber"])
        pid=str(record["projectNumber"])
        if pub not in targets or targets[pub]!=app:
            raise ValueError("not_an_exact_kipris_application_match")
        if record["patentPublicationNumber"] is not None:
            raise ValueError("ntis_registnumber_is_not_publication_number")
        if not PROJECT.fullmatch(pid) or pid not in project_ids:
            raise ValueError("not_an_official_project_in_snapshot")
        if not RESULT.fullmatch(str(record["sourceOfficialRecordId"])):
            raise ValueError("unverified_ntis_outcome_id")
        if record["registType"]!="출원" or str(record["registTypeCode"])!="01":
            raise ValueError("registered_patent_cannot_match_application")
        if normalize(record["registNumberRaw"])!=app or record["sourceFieldMappingVerified"] is not True:
            raise ValueError("ntis_number_not_verified")
        for key in ("resultTitle","projectTitle","performAgency"):
            if not isinstance(record[key],str) or len(record[key])>250 or "<" in record[key] or ">" in record[key]:
                raise ValueError("unsafe_outcome_text")
        tup=(pub,pid,record["sourceOfficialRecordId"])
        if tup in seen:raise ValueError("duplicate_outcome")
        seen.add(tup)
    checked=errors=0;seen_targets=set()
    for ch in data["checks"]:
        if not isinstance(ch,dict) or not set(ch)<=ALLOWED_CHECK_KEYS:
            raise ValueError("invalid_query_audit")
        pub=ch.get("publicationNumber")
        if pub not in targets or normalize(ch.get("applicationNumber"))!=targets[pub] or pub in seen_targets:
            raise ValueError("invalid_query_target")
        seen_targets.add(pub)
        if ch.get("status")=="checked":
            checked+=1
            if type(ch.get("totalHits")) is not int or ch["totalHits"]<0:
                raise ValueError("invalid_hit_count")
        elif ch.get("status")=="source_error":
            errors+=1
            if not isinstance(ch.get("errorClass"),str):raise ValueError("no_source_error_type")
        else:raise ValueError("invalid_check_status")
    if (data["targetCount"]<len(data["checks"]) or
        data["completedTargets"]!=checked or data["errorTargets"]!=errors or
        data["matchingOutcomeRows"]!=len(data["records"])):
        raise ValueError("incorrect_counts")
    if data["status"]=="verified_official_patent_outcomes" and (errors or checked!=data["targetCount"]):
        raise ValueError("false_full_success")
    serialized=json.dumps(data,ensure_ascii=False)
    if re.search(r"(?i)apprvKey|authorization|bearer\s|api[_-]?key|password|secret",serialized):
        raise ValueError("possible_credentials")
    return {"status":data["status"],"official_searches":checked,
            "verified_number_pairs_for_manual_review":len(data["records"]),
            "project_snapshot_age_mismatch":projects.get("dossierGeneratedAt")!=dossier.get("generatedAt")}

def main():
    cli=argparse.ArgumentParser()
    cli.add_argument("input")
    cli.add_argument("--dossier",default="digests/patent_rnd_dossiers_latest.json")
    cli.add_argument("--deep",default="digests/patent_deep_latest.json")
    cli.add_argument("--projects",default="digests/ntis_project_leads_latest.json")
    args=cli.parse_args()
    read=lambda p:json.loads(Path(p).read_text(encoding="utf-8-sig"))
    print("Validated NTIS rpatent outcome:",validate(read(args.input),read(args.dossier),
                                                  read(args.deep),read(args.projects)))

if __name__=="__main__": main()
