"""Strict NTIS patent-outcome / KIPRIS identifier reconciliation.

A keyword match in NTIS public_project is never a patent-to-project link.
Only an *explicitly field-mapped* patent outcome containing both an exact
project number and exact corresponding patent number can create a review
candidate. Even that candidate needs NTIS detail and newsroom confirmation.

The user supplied the NTIS 2024 outcome-search official PDF and a 2026-10-14
approved-PC probe verifying ProjectID/RegistNumber/RegistType/ResultID XML.
A registration number never implies a KIPRIS application or publication.
Matching identifiers remain reporter-review evidence, not commercial results.
"""
import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST=timezone(timedelta(hours=9))
PAT=re.compile(r"^10\d{11}$")
PROJ=re.compile(r"^[A-Za-z0-9-]{4,80}$")
OUTCOME_PROFILE="ntis_patent_outcome_fields_manual_confirmed_v1"


def number(raw):
    """Korean patent publication/application, not registration; preserve namespace."""
    value=re.sub(r"[\s-]","",str(raw or ""))
    return value if PAT.fullmatch(value) else None


def source_project_numbers(projects):
    """Index only successfully captured official project *keyword leads*."""
    good={}
    for row in projects.get("checks",[]):
        if row.get("status")!="checked":
            continue
        for p in (row.get("records") or []):
            pid=str(p.get("projectNumber") or "")
            if not PROJ.fullmatch(pid) or not p.get("projectTitle"):
                continue
            good.setdefault(pid,{"projectNumber":pid,
                                 "projectTitle":p["projectTitle"],
                                 "agency":p.get("performingAgency"),
                                 "years":set()})
            if p.get("projectYear"):
                good[pid]["years"].add(str(p["projectYear"]))
    return good


def lookups(dossier,deep):
    """Return exact cross-source identifiers, with ambiguous refs excluded."""
    deep_by_pub={}
    for investigation in deep.get("investigations",[]):
        if not isinstance(investigation,dict):
            continue
        pub=number(investigation.get("publicationNumber"))
        app=number(investigation.get("applicationNumber"))
        if pub and app:
            deep_by_pub.setdefault(pub,set()).add(app)
    by_pub={}
    for patent in dossier.get("dossiers",[]):
        pub=number(patent.get("publicationNumber"))
        if not pub:
            continue
        app_set=deep_by_pub.get(pub,set())
        by_pub[pub]={
            "publicationNumber":pub,
            "applicationNumber":next(iter(app_set)) if len(app_set)==1 else None,
            "applicationSource":"KIPRIS deep snapshot" if len(app_set)==1 else "missing_or_ambiguous",
            "title":patent.get("title"),
            "publicationDate":patent.get("publicationDate"),
        }
    return by_pub


def build(dossier, deep, projects, outcomes=None, now=None):
    now=now or datetime.now(KST)
    if dossier.get("status")!="research_only" or not isinstance(dossier.get("dossiers"),list):
        raise ValueError("invalid_dossier_snapshot")
    if not isinstance(deep.get("investigations"),list):
        raise ValueError("invalid_kipris_deep_snapshot")
    if not isinstance(projects.get("checks"),list) or projects.get("projectPatentLinksConfirmed")!=0:
        raise ValueError("invalid_ntis_project_snapshot")
    aligned=(projects.get("dossierGeneratedAt")==dossier.get("generatedAt"))
    project_rows=source_project_numbers(projects)
    patents=lookups(dossier,deep)
    links=[]
    blocked=[]
    eligible_outcomes=[]
    outcome_status="ntis_patent_outcome_records_not_yet_collected"
    if outcomes is not None:
        if (outcomes.get("status")!="verified_official_patent_outcomes" or
            outcomes.get("mappingProfile")!=OUTCOME_PROFILE or
            not isinstance(outcomes.get("records"),list)):
            outcome_status="outcome_schema_or_authorization_unverified"
        elif outcomes.get("projectSourceGeneratedAt")!=projects.get("generatedAt"):
            outcome_status="project_source_timestamp_mismatch"
        else:
            outcome_status=("outcome_records_ready_for_manual_link_review" if aligned else
                            "outcome_records_ready_but_historical_project_dossier")
            # Historical project-search snapshots remain usable only as
            # explicit old context when the same official ProjectID and exact
            # KIPRIS application are found in the *same* NTIS rpatent HIT.
            # They do not turn an older research project into recent news.
            eligible_outcomes=outcomes["records"]
    if eligible_outcomes:
        # Only exact, type-preserving matches for the *same record* count as
        # number-identity evidence. Related titles, applicants and keywords
        # must NEVER upgrade the status.
        for record in eligible_outcomes[:500]:
            if not isinstance(record,dict):
                continue
            pid=str(record.get("projectNumber") or "")
            app=number(record.get("patentApplicationNumber"))
            # NTIS manual: RegistNumber = 출원(등록)번호. No publication field.
            # Registration ("등록", code 02) must not be compared with KIPRIS
            # *application* or *publication* identifiers.
            if (record.get("registType")!="출원" or
                str(record.get("registTypeCode"))!="01" or
                number(record.get("registNumberRaw"))!=app or
                record.get("patentPublicationNumber") is not None):
                blocked.append("not_official_application_number")
                continue
            if pid not in project_rows:
                blocked.append("project_not_in_approved_pc_snapshot")
                continue
            if not record.get("sourceOfficialRecordId") or not record.get("sourceFieldMappingVerified"):
                blocked.append("missing_official_outcome_record_provenance")
                continue
            for patent in patents.values():
                match=[]
                if app and patent["applicationNumber"] and app==patent["applicationNumber"]:
                    match.append("application_number_exact")
                # NTIS rpatent API has RegistNumber (not 공개번호),
                # so publication-number matches are never inferred here.
                if not match:
                    continue
                links.append({
                    "publicationNumber":patent["publicationNumber"],
                    "applicationNumber":patent["applicationNumber"],
                    "projectNumber":pid,
                    "projectTitle":project_rows[pid]["projectTitle"],
                    "ntisOutcomeRecordId":str(record["sourceOfficialRecordId"])[:100],
                    "identityEvidence":match,
                    "sourceRecordHasBothIdentifiers":True,
                    "samePatentAndProjectConfirmedForPublication":False,
                    "outcomeManuallyVerified":False,
                    "productOrCommercializationVerified":False,
                    "exclusiveVerified":False,
                    "deskStatus":"number_match_needs_official_outcome_detail_and_legal_entity_check",
                })
    dedup={(x["publicationNumber"],x["projectNumber"],x["ntisOutcomeRecordId"]):x for x in links}
    return {
        "generatedAt":now.isoformat(timespec="seconds"),
        "dossierGeneratedAt":dossier["generatedAt"],
        "kiprisDeepGeneratedAt":deep.get("generatedAt"),
        "ntisProjectsGeneratedAt":projects.get("generatedAt"),
        "ntisOutcomeGeneratedAt":outcomes.get("generatedAt") if outcomes else None,
        "status":outcome_status,
        "projectSnapshotMatchesCurrentDossier":aligned,
        "patentsConsidered":len(patents),
        "patentsWithOfficialKiprisApplicationNumbers":sum(bool(p["applicationNumber"]) for p in patents.values()),
        "ntisProjectNumbersIndexed":len(project_rows),
        "potentialExactNumberPairsNeedingHumanReview":len(dedup),
        "confirmedPatentProjectLinks":0,
        "commercializationConfirmed":0,
        "exclusiveConfirmed":0,
        "reviewOnlyMatches":list(dedup.values())[:30],
        "outcomeNumberTypeChecks":"Only RegistType=출원(code 01) and exact RegistNumber vs KIPRIS application accepted; NTIS registration is not a publication",
        "reviewQuestions":[
            "NTIS 성과검색 전체용 승인과 실측 XML의 필드 뜻을 공식 매뉴얼로 확인했는가?",
            "성과 원문에 과제번호 및 출원번호 또는 공개번호가 각각 명시돼 있는가?",
            "NTIS 특허 성과의 출원번호와 KIPRIS 출원번호, 공개번호와 공개번호를 유형별로 일치시켰는가?",
            "동일 과제의 연차별 번호와 주관·공동연구기관을 원문으로 구분했는가?",
            "해당 특허와 특정 차량·설비 제품 적용, 사업화 및 기보도를 별도 취재했는가?",
        ],
        "warning":"성과검색 API 공식 필드는 확인됨. 단, 같은 성과 HIT의 과제번호/출원번호 일치도 취재 검증 대상으로만 분류하며 특허 사업화·최근 이벤트·미보도 단독은 별도 확인. 공개번호와 출원번호를 혼용하지 않음.",
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--dossier",default="digests/patent_rnd_dossiers_latest.json")
    p.add_argument("--deep",default="digests/patent_deep_latest.json")
    p.add_argument("--projects",default="digests/ntis_project_leads_latest.json")
    p.add_argument("--outcomes",default=None)
    p.add_argument("--out",default="digests/ntis_patent_outcome_links_latest.json")
    args=p.parse_args()
    read=lambda f:json.loads(Path(f).read_text(encoding="utf-8-sig"))
    result=build(read(args.dossier),read(args.deep),read(args.projects),
                 read(args.outcomes) if args.outcomes else None)
    dest=Path(args.out);dest.parent.mkdir(parents=True,exist_ok=True)
    tmp=dest.with_suffix(".tmp")
    tmp.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    tmp.replace(dest)
    print("NTIS outcome audit",result["status"],
          "KIPRIS application IDs",result["patentsWithOfficialKiprisApplicationNumbers"],
          "project records",result["ntisProjectNumbersIndexed"],
          "official links confirmed",result["confirmedPatentProjectLinks"])


if __name__=="__main__":
    main()
