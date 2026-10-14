"""Fail-closed validation of manually reviewed NTIS rpatent keyword discovery.

Never infer patent/project identity from matching titles, technology words,
agency names or corporate applicants. Exact RegistType=출원 / RegistNumber
against KIPRIS APPLICATION plus ProjectID within the *same NTIS HIT* is
necessary for a limited review candidate, still not a confirmed outcome.

The 2024 NTIS official patent-outcome XML fields and a registered-PC live
schema probe were established in the reporting project on 2026-10-14.
"""
import argparse
import json
import re
from datetime import datetime
from pathlib import Path

PROFILE="ntis_rpatent_2024_manual_keyword_discovery_v1"
KIPRIS_RE=re.compile(r"^10\d{11}$")
PROJECT_RE=re.compile(r"^\d{10}$")
OUTCOME_ID_RE=re.compile(r"^[A-Za-z0-9_-]{5,100}$")
CREDENTIALS=re.compile(r"(?i)apprvKey|authorization|bearer\s|api[_-]?key|password|secret")
ROOT={
    "generatedAt","dossierGeneratedAt","kiprisDeepGeneratedAt",
    "ntisProjectsGeneratedAt","ntisProjectDossierGeneratedAt","status",
    "mappingProfile","collectionMethod","targetCount","plannedQueries",
    "completedQueries","failedQueries","pagesPerQueryMax",
    "totalSearchHitsAcrossQueries","scannedOutcomeRows",
    "exactPatentAndPriorProjectNumberPairs",
    "verifiedDirectPatentProjectLinks","commercializationConfirmed",
    "exclusiveConfirmed","records","checks","warning",
}
CHECK={
    "publicationNumber","applicationNumber","mode","query","status",
    "totalHits","pagesChecked","rowsExamined","exactApplicationRows",
    "exactApplicationRowsWithProjectOutsidePriorSample",
    "registrationTypeRowsExcluded","unrelatedApplicationRowsExcluded",
    "truncated","errorClass",
}
ROW={
    "publicationNumber","patentApplicationNumber","patentPublicationNumber",
    "projectNumber","sourceOfficialRecordId","sourceFieldMappingVerified",
    "registType","registTypeCode","registNumberRaw","resultTitle",
    "projectTitle","performAgency","resultYear","matchType","sourceQueryMode",
}
MODES={"technology","title","applicant"}

def normalize(value):
    value=re.sub(r"[\s-]","",str(value or ""))
    return value if KIPRIS_RE.fullmatch(value) else None

def mappings(dossier,deep):
    index={}
    for item in deep.get("investigations",[]):
        pub=normalize(item.get("publicationNumber"))
        app=normalize(item.get("applicationNumber"))
        if pub and app:
            index.setdefault(pub,set()).add(app)
    output={}
    for item in dossier.get("dossiers",[]):
        pub=normalize(item.get("publicationNumber"))
        if pub and len(index.get(pub,set()))==1:
            output[pub]=(next(iter(index[pub])),item)
    return output

def project_numbers(projects):
    return {str(p["projectNumber"])
            for ch in projects.get("checks",[]) if ch.get("status")=="checked"
            for p in ch.get("records",[]) if PROJECT_RE.fullmatch(str(p.get("projectNumber") or ""))}

def valid_query(mode,query,title,deep_partners):
    if not isinstance(query,str) or len(query)<3 or len(query)>70 or "<" in query or ">" in query:
        return False
    title=str(title or "")
    if mode=="title":
        # Title may be truncated by the PC collector to first 42 chars.
        # Require substring length sufficient to avoid generic single words.
        return len(query)>=4 and query in title and len(query)<=42
    if mode=="technology":
        # Terms must be present in the KIPRIS title rather than invented.
        known=("부분방전","상변태","침투탐상","메타렌즈","복합패널",
               "방열 조성물","RTCM","고정자 냉각","배터리 열폭주",
               "해중합","자율주행","전력설비")
        return ((query in known and query in title) or
                (len(query)>=3 and len(query)<=40 and
                 all(part in title for part in query.split())))
    if mode=="applicant":
        # Require a CORPORATE party in official KIPRIS applicants, not a person.
        for raw in deep_partners:
            raw=str(raw)
            if not any(s in raw for s in ("주식회사","(주)","㈜","산학협력단")):
                continue
            cleaned=re.sub(r"주식회사|\(주\)|㈜","",raw).strip()
            if cleaned==query and 3<=len(cleaned)<=45:
                return True
    return False

def validate(export,dossier,deep,projects):
    if not isinstance(export,dict) or set(export)!=ROOT:
        raise ValueError("discovery_unexpected_schema")
    if export["mappingProfile"]!=PROFILE or export["collectionMethod"]!="approved_pc_rpatent_keyword_discovery":
        raise ValueError("unverified_collection_profile")
    if (export["dossierGeneratedAt"]!=dossier.get("generatedAt") or
        export["kiprisDeepGeneratedAt"]!=deep.get("generatedAt") or
        export["ntisProjectsGeneratedAt"]!=projects.get("generatedAt") or
        export["ntisProjectDossierGeneratedAt"]!=projects.get("dossierGeneratedAt")):
        raise ValueError("source_snapshot_mismatch")
    try:
        if datetime.fromisoformat(export["generatedAt"]).utcoffset() is None:
            raise ValueError()
    except (ValueError,TypeError):
        raise ValueError("invalid_generated_timestamp") from None
    if export["status"] not in {"ready","partial_errors","incomplete"}:
        raise ValueError("invalid_collector_status")
    if (export["verifiedDirectPatentProjectLinks"]!=0 or
        export["commercializationConfirmed"]!=0 or export["exclusiveConfirmed"]!=0):
        raise ValueError("illegal_reporting_certainty")
    if (not isinstance(export["records"],list) or len(export["records"])>50 or
        not isinstance(export["checks"],list) or len(export["checks"])>21):
        raise ValueError("too_many_or_invalid_discovery_results")
    maxpages=export["pagesPerQueryMax"]
    if type(maxpages) is not int or not 1<=maxpages<=3:
        raise ValueError("invalid_page_limit")
    pubs=mappings(dossier,deep)
    deep_by_pub={item.get("publicationNumber"):item for item in deep.get("investigations",[])
                 if isinstance(item,dict)}
    prior_projects=project_numbers(projects)
    completed=failed=observed=totalhits=0
    ids=set()
    seen_queries=set()
    for ch in export["checks"]:
        if not isinstance(ch,dict) or not set(ch)<=CHECK:
            raise ValueError("unexpected_discovery_check_fields")
        pub=ch.get("publicationNumber")
        if pub not in pubs or normalize(ch.get("applicationNumber"))!=pubs[pub][0]:
            raise ValueError("unmatched_official_patent_identifier")
        mode,query=ch.get("mode"),ch.get("query")
        if mode not in MODES or not valid_query(mode,query,pubs[pub][1].get("title"),
                                                deep_by_pub.get(pub,{}).get("applicants",[])):
            raise ValueError("query_not_grounded_in_kipris")
        key=(pub,mode,query)
        if key in seen_queries:
            raise ValueError("duplicate_discovery_query")
        seen_queries.add(key)
        if ch.get("status")=="checked":
            completed+=1
            for k in ("totalHits","pagesChecked","rowsExamined",
                      "exactApplicationRows","exactApplicationRowsWithProjectOutsidePriorSample",
                      "registrationTypeRowsExcluded","unrelatedApplicationRowsExcluded"):
                if type(ch.get(k)) is not int or ch[k]<0:
                    raise ValueError("invalid_result_counts")
            if not 1<=ch["pagesChecked"]<=maxpages:
                raise ValueError("invalid_pages_scanned")
            if ch["rowsExamined"]>ch["pagesChecked"]*10 or ch["rowsExamined"]>ch["totalHits"]:
                raise ValueError("scan_count_impossible")
            if (ch["exactApplicationRows"]+
                ch["registrationTypeRowsExcluded"]+
                ch["unrelatedApplicationRowsExcluded"])>ch["rowsExamined"]:
                raise ValueError("impossible_typed_match_counts")
            if ch["exactApplicationRowsWithProjectOutsidePriorSample"]>ch["exactApplicationRows"]:
                raise ValueError("project_outside_subset_greater_than_exact_apps")
            if ch.get("truncated") is not (ch["totalHits"]>ch["rowsExamined"]):
                raise ValueError("false_pagination_claim")
            observed+=ch["rowsExamined"]
            totalhits+=ch["totalHits"]
        elif ch.get("status")=="source_error":
            failed+=1
            if not isinstance(ch.get("errorClass"),str) or not ch["errorClass"].startswith(("NTIS_","INVALID_","UNKNOWN_","OUTCOME_")):
                raise ValueError("invalid_source_error_label")
        else:
            raise ValueError("unknown_query_status")
    for row in export["records"]:
        if not isinstance(row,dict) or set(row)!=ROW:
            raise ValueError("unexpected_match_record_fields")
        pub=row.get("publicationNumber")
        if pub not in pubs or row.get("patentApplicationNumber")!=pubs[pub][0]:
            raise ValueError("not_exact_kipris_application")
        if row.get("patentPublicationNumber") is not None:
            raise ValueError("publication_number_not_in_outcome")
        if row.get("registType")!="출원" or str(row.get("registTypeCode"))!="01":
            raise ValueError("registration_number_is_not_application")
        if normalize(row.get("registNumberRaw"))!=pubs[pub][0]:
            raise ValueError("regist_number_does_not_match_application")
        pid=str(row.get("projectNumber") or "")
        if pid not in prior_projects or not PROJECT_RE.fullmatch(pid):
            raise ValueError("project_not_in_prior_official_sample")
        if not OUTCOME_ID_RE.fullmatch(str(row.get("sourceOfficialRecordId") or "")):
            raise ValueError("no_official_outcome_identifier")
        if row.get("sourceFieldMappingVerified") is not True or row.get("matchType")!="official_application_and_project_id_in_same_hit":
            raise ValueError("non_official_match_promoted")
        if row.get("sourceQueryMode") not in MODES or not any(
            c["publicationNumber"]==pub and c["mode"]==row["sourceQueryMode"] and c["status"]=="checked"
            for c in export["checks"]
        ):
            raise ValueError("no_supporting_query")
        for k in ("resultTitle","projectTitle","performAgency","resultYear"):
            if not isinstance(row.get(k),str) or len(row[k])>200 or "<" in row[k] or ">" in row[k]:
                raise ValueError("unsafe_public_outcome_text")
        k=(pub,pid,row["sourceOfficialRecordId"])
        if k in ids:
            raise ValueError("duplicate_exact_outcome")
        ids.add(k)
    if (export["exactPatentAndPriorProjectNumberPairs"]!=len(ids) or
        export["plannedQueries"]<len(export["checks"]) or
        export["completedQueries"]!=completed or
        export["failedQueries"]!=failed or
        export["scannedOutcomeRows"]!=observed or
        export["totalSearchHitsAcrossQueries"]!=totalhits):
        raise ValueError("inconsistent_collection_totals")
    if (export["status"]=="ready" and
        (failed>0 or completed!=export["plannedQueries"])):
        raise ValueError("false_success_claim")
    if (type(export["targetCount"]) is not int or not 1<=export["targetCount"]<=7 or
        type(export["plannedQueries"]) is not int or not 1<=export["plannedQueries"]<=21):
        raise ValueError("invalid_plan_size")
    text=json.dumps(export,ensure_ascii=False)
    if CREDENTIALS.search(text):
        raise ValueError("potential_api_key_or_secret")
    return {"status":export["status"],"queries":completed,
            "scannedRows":observed,"exactAppProjectPairs":len(ids),
            "priorProjectSubsetSize":len(prior_projects),
            "snapshotAligned":export["dossierGeneratedAt"]==projects.get("dossierGeneratedAt")}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("input",type=Path)
    parser.add_argument("--dossier",default="digests/patent_rnd_dossiers_latest.json")
    parser.add_argument("--deep",default="digests/patent_deep_latest.json")
    parser.add_argument("--projects",default="digests/ntis_project_leads_latest.json")
    p=parser.parse_args()
    read=lambda f:json.loads(Path(f).read_text(encoding="utf-8-sig"))
    print("NTIS discovery structure valid:",validate(read(p.input),read(Path(p.dossier)),
                                                     read(Path(p.deep)),read(Path(p.projects))))
if __name__=="__main__":main()
