import copy
import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from ntis_project_reverse_validate import validate

def read(path):
    return json.loads((ROOT/path).read_text(encoding="utf-8-sig"))

PLAN=read("digests/ntis_project_reverse_plan_latest.json")
PROJECTS=read("digests/ntis_project_leads_latest.json")
PINNED=read("digests/ntis_project_reverse_kipris_source.json")
DOSSIER=PINNED["dossier"]
DEEP=PINNED["deep"]

def fixture():
    checks=[]
    for project in PLAN["projects"]:
        pid=project["projectNumber"]
        fallback=pid=="2410017896"
        ls=pid=="2410019058"
        checks.append({
            "projectNumber":pid,"projectYear":project["projectYear"],
            "projectTitle":project["projectTitle"],
            "performingAgency":project["performingAgency"],
            "earlierKeywordPatentPublications":
                list(project["earlierKeywordMatchedPatentPublications"]),
            "status":"checked","errorClass":None,
            "searchModesCompleted":["primary","ti03"] if fallback else ["primary"],
            "primaryTotalHits":0 if fallback else 3,
            "fallbackTotalHits":1 if fallback else None,
            "rowsInspected":1 if fallback else 3,
            "exactProjectIdRows":0 if fallback else (3 if ls else 2),
            "differentProjectIdRowsExcluded":1 if fallback else (0 if ls else 1),
            "registrationTypeRowsExcluded":0 if fallback else 1,
            "applicationTypeRows":0 if fallback else (2 if ls else 1),
            "matchingKiprisApplicationRows":1 if ls else 0,
            "uninspectedPagesRemain":False,
        })
    row={
        "projectNumber":"2410019058",
        "publicationNumber":"1020260145290",
        "applicationNumber":"1020250039383",
        "officialResultID":"MOCK2410019058A",
        "sourceRegistNumber":"10-2025-0039383",
        "sourceRegistType":"출원","sourceRegistTypeCode":"01",
        "sourceProjectID":"2410019058",
        "resultTitle":"Fixture sensor",
        "projectTitle":"Fixture project",
        "performingAgency":"",
        "searchMode":"primary",
        "sameOfficialHitIdentifiers":True,
        "officialPatentProjectOutcomeVerified":False,
        "commercializationConfirmed":False,
        "exclusiveConfirmed":False,
    }
    return {
        "generatedAt":"2026-10-14T23:30:00+09:00",
        "planVersion":PLAN["planVersion"],
        "planGeneratedAt":PLAN["generatedAt"],
        "projectSourceGeneratedAt":PLAN["projectSourceGeneratedAt"],
        "projectSourceDossierGeneratedAt":PLAN["projectSourceDossierGeneratedAt"],
        "kiprisDossierGeneratedAt":PLAN["kiprisDossierGeneratedAt"],
        "kiprisDeepGeneratedAt":PLAN["kiprisDeepGeneratedAt"],
        "status":"ready",
        "collectionMethod":"approved_pc_ntis_rpatent_reverse_projectid",
        "plannedUniqueProjects":26,
        "completedProjects":26,
        "failedProjects":0,
        "actualHttpRequests":27,
        "maximumHttpRequests":52,
        "primaryQueriesCompleted":26,
        "fallbackQueriesCompleted":1,
        "rowsInspected":76,
        "matchedOfficialProjectApplicationRows":1,
        "reviewedNumberPairs":1,
        "verifiedPatentProjectOutcomes":0,
        "confirmedCommercialization":0,
        "confirmedExclusives":0,
        "checks":checks,
        "records":[row],
        "warning":"Data is a synthetic reverse lookup test, not verified R&D outcomes.",
    }

class ReverseImportTests(unittest.TestCase):
    def test_official_synthetic_matched_pair_only_review_not_confirmed(self):
        x=fixture()
        y=validate(x,PLAN,PROJECTS,DOSSIER,DEEP)
        self.assertEqual(y["projects"],26)
        self.assertEqual(y["httpRequests"],27)
        self.assertEqual(y["officialPairsForHumanReview"],1)
        self.assertEqual(x["verifiedPatentProjectOutcomes"],0)

    def test_all_zero_matches_are_valid_observation_not_absence_claim(self):
        x=fixture()
        x["records"]=[]
        x["reviewedNumberPairs"]=0
        x["matchedOfficialProjectApplicationRows"]=0
        for ch in x["checks"]:
            ch["matchingKiprisApplicationRows"]=0
        self.assertEqual(validate(x,PLAN,PROJECTS,DOSSIER,DEEP)["officialPairsForHumanReview"],0)

    def test_wrong_project_id_in_same_hit_rejected(self):
        x=fixture()
        x["records"][0]["sourceProjectID"]="2410005211"
        with self.assertRaisesRegex(ValueError,"patent_application_or_project_not_in_verified_sources"):
            validate(x,PLAN,PROJECTS,DOSSIER,DEEP)

    def test_registered_number_cannot_be_used_as_application(self):
        x=fixture()
        x["records"][0]["sourceRegistType"]="등록"
        with self.assertRaisesRegex(ValueError,"registered_patent_misread"):
            validate(x,PLAN,PROJECTS,DOSSIER,DEEP)

    def test_official_publication_number_not_substituted_for_application(self):
        x=fixture()
        x["records"][0]["sourceRegistNumber"]="10-2026-0145290"
        with self.assertRaisesRegex(ValueError,"wrong_application_number"):
            validate(x,PLAN,PROJECTS,DOSSIER,DEEP)

    def test_reported_approved_patent_outcome_is_not_automatic_certification(self):
        x=fixture()
        x["verifiedPatentProjectOutcomes"]=1
        with self.assertRaisesRegex(ValueError,"unjustified"):
            validate(x,PLAN,PROJECTS,DOSSIER,DEEP)

    def test_same_number_pair_cannot_prove_commercialization(self):
        x=fixture()
        x["records"][0]["commercializationConfirmed"]=True
        with self.assertRaisesRegex(ValueError,"unjustified_outcome"):
            validate(x,PLAN,PROJECTS,DOSSIER,DEEP)

    def test_duplicate_outcome_record_rejected(self):
        x=fixture()
        x["records"].append(copy.deepcopy(x["records"][0]))
        x["reviewedNumberPairs"]=2
        x["matchedOfficialProjectApplicationRows"]=2
        x["checks"][2]["matchingKiprisApplicationRows"]=2
        with self.assertRaisesRegex(ValueError,"duplicate_patent_project_pair"):
            validate(x,PLAN,PROJECTS,DOSSIER,DEEP)

    def test_false_fallback_when_primary_has_hits(self):
        x=fixture()
        ch=next(c for c in x["checks"] if c["projectNumber"]=="2410017896")
        ch["primaryTotalHits"]=4
        with self.assertRaisesRegex(ValueError,"fallback_not_conditional"):
            validate(x,PLAN,PROJECTS,DOSSIER,DEEP)

    def test_changed_source_timestamp_rejected(self):
        x=fixture()
        x["kiprisDossierGeneratedAt"]="2026-10-15T00:00:00+09:00"
        with self.assertRaisesRegex(ValueError,"reverse_source_snapshot_mismatch"):
            validate(x,PLAN,PROJECTS,DOSSIER,DEEP)

    def test_secrets_in_export_refused(self):
        x=fixture()
        x["warning"]="apprvKey=TOPSECRET"
        with self.assertRaisesRegex(ValueError,"suspected_ntis_secret"):
            validate(x,PLAN,PROJECTS,DOSSIER,DEEP)

    def test_malformed_project_count_rejected(self):
        x=fixture()
        x["completedProjects"]=25
        with self.assertRaisesRegex(ValueError,"reverse_counts"):
            validate(x,PLAN,PROJECTS,DOSSIER,DEEP)

    def test_unrecognized_result_id_rejected(self):
        x=fixture()
        x["records"][0]["officialResultID"]=""
        with self.assertRaisesRegex(ValueError,"invalid_official_result"):
            validate(x,PLAN,PROJECTS,DOSSIER,DEEP)

if __name__=="__main__":unittest.main()
