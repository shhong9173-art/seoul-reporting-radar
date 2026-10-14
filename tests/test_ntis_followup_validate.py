import copy
import json
import sys
import unittest
from pathlib import Path
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from ntis_followup_validate import validate

def read(path):
    return json.loads((ROOT/path).read_text(encoding="utf-8-sig"))

SOURCE=read("digests/ntis_patent_discovery_pc_latest.json")
PLAN=read("digests/ntis_patent_followup_plan_latest.json")
PROJECTS=read("digests/ntis_project_leads_latest.json")

def fixture():
    checks=[]
    for t in PLAN["tasks"]:
        tech=t["strategy"]=="technology_next_pages"
        checked=len(t["pages"])*10 if tech else 3
        checks.append({
            "query":t["query"],"strategy":t["strategy"],
            "sourceTotalHits":t["sourceTotalHits"],
            "pagesRequested":list(t["pages"]),
            "pagesCompleted":list(t["pages"]),
            "targets":copy.deepcopy(t["targets"]),
            "status":"checked","errorClass":None,
            "newQueryTotalHits":None if tech else 3,
            "newlyScannedRows":checked,
            "exactApplicationRows":1 if t==PLAN["tasks"][0] else 0,
            "exactApplicationWithProjectOutsideOlderSubset":0,
            "registrationTypeExcluded":1,
            "unrelatedApplicationExcluded":checked-(2 if t==PLAN["tasks"][0] else 1),
            "truncated":tech,
        })
    first=PLAN["tasks"][0]
    rec={
        "publicationNumber":first["targets"][0]["publicationNumber"],
        "patentApplicationNumber":first["targets"][0]["applicationNumber"],
        "projectNumber":"2410019058",
        "projectInOlder26ProjectSubset":True,
        "officialOutcomeId":"MOCK2X0",
        "registType":"출원","registTypeCode":"01",
        "registNumberRaw":"10-2025-0039383",
        "outcomeTitle":"Test result","projectTitle":"Test project",
        "performingAgency":"",
        "query":first["query"],"strategy":first["strategy"],
        "page":2,
        "officialFieldsInSameHit":True,
        "patentProjectLinkConfirmed":False,
        "commercializationConfirmed":False,
        "exclusiveConfirmed":False,
    }
    return {
        "generatedAt":datetime.now(timezone.utc).isoformat(),
        "planGeneratedAt":PLAN["generatedAt"],
        "sourceDiscoveryGeneratedAt":PLAN["sourceDiscoveryGeneratedAt"],
        "sourceDossierGeneratedAt":PLAN["sourceDossierGeneratedAt"],
        "status":"ready",
        "collectionMethod":"approved_pc_ntis_rpatent_targeted_followup",
        "planVersion":PLAN["planVersion"],
        "plannedQueries":len(checks),
        "completedQueries":len(checks),
        "failedQueries":0,
        "maxHttpRequests":PLAN["maximumHttpRequests"],
        "actualHttpRequests":PLAN["maximumHttpRequests"],
        "additionalScannedRows":sum(c["newlyScannedRows"] for c in checks),
        "applicationMatchRowsOutsideOldProjectSubset":0,
        "exactApplicationProjectNumberReviewCandidates":1,
        "officialPatentProjectLinksConfirmed":0,
        "commercializationConfirmed":0,
        "exclusiveConfirmed":0,
        "checks":checks,
        "records":[rec],
        "warning":"Historically sourced; not an exclusive news confirmation.",
    }

class FollowupValidatorTests(unittest.TestCase):
    def test_synthetic_exact_outcome_is_a_review_not_confirmed(self):
        x=fixture()
        info=validate(x,PLAN,SOURCE,PROJECTS)
        self.assertEqual(info["newRequests"],15)
        self.assertEqual(info["reviewPairs"],1)
        self.assertEqual(x["officialPatentProjectLinksConfirmed"],0)

    def test_false_registration_rejected(self):
        x=fixture()
        x["records"][0]["registType"]="등록"
        with self.assertRaisesRegex(ValueError,"registered_number"):
            validate(x,PLAN,SOURCE,PROJECTS)

    def test_wrong_kipris_app_rejected(self):
        x=fixture()
        x["records"][0]["registNumberRaw"]="10-2026-0145290"
        with self.assertRaisesRegex(ValueError,"non_official_match"):
            validate(x,PLAN,SOURCE,PROJECTS)

    def test_project_outside_old_sample_is_allowed_but_unverified(self):
        x=fixture()
        x["records"][0]["projectNumber"]="1234567890"
        x["records"][0]["projectInOlder26ProjectSubset"]=False
        self.assertEqual(validate(x,PLAN,SOURCE,PROJECTS)["reviewPairs"],1)
        self.assertFalse(x["records"][0]["patentProjectLinkConfirmed"])

    def test_wrong_sample_membership_rejected(self):
        x=fixture()
        x["records"][0]["projectInOlder26ProjectSubset"]=False
        with self.assertRaisesRegex(ValueError,"incorrect_old_sample"):
            validate(x,PLAN,SOURCE,PROJECTS)

    def test_fabricated_technology_and_company_query_rejected(self):
        x=fixture()
        x["checks"][-1]["query"]="현대자동차 포스코 신약"
        with self.assertRaisesRegex(ValueError,"query_not_in_approved"):
            validate(x,PLAN,SOURCE,PROJECTS)

    def test_unapproved_fourth_page_rejected(self):
        x=fixture()
        x["checks"][0]["pagesCompleted"].append(4)
        with self.assertRaisesRegex(ValueError,"unapproved_page_sequence"):
            validate(x,PLAN,SOURCE,PROJECTS)

    def test_no_more_than_fifteen_calls(self):
        x=fixture()
        x["actualHttpRequests"]=16
        with self.assertRaisesRegex(ValueError,"bad_http_request_budget"):
            validate(x,PLAN,SOURCE,PROJECTS)

    def test_missing_source_record_id_rejected(self):
        x=fixture()
        x["records"][0]["officialOutcomeId"]=""
        with self.assertRaisesRegex(ValueError,"unrecognized_official"):
            validate(x,PLAN,SOURCE,PROJECTS)

    def test_credential_leak_rejected(self):
        x=fixture()
        x["warning"]="apprvKey=AAA"
        with self.assertRaisesRegex(ValueError,"possible_api_key"):
            validate(x,PLAN,SOURCE,PROJECTS)

    def test_business_claim_must_remain_false(self):
        x=fixture()
        x["records"][0]["exclusiveConfirmed"]=True
        with self.assertRaisesRegex(ValueError,"non_official_match"):
            validate(x,PLAN,SOURCE,PROJECTS)

    def test_duplicate_matched_official_outcome_rejected(self):
        x=fixture()
        x["records"].append(copy.deepcopy(x["records"][0]))
        x["exactApplicationProjectNumberReviewCandidates"]=2
        with self.assertRaisesRegex(ValueError,"duplicated_official"):
            validate(x,PLAN,SOURCE,PROJECTS)

    def test_stale_plan_update_is_rejected_not_retargeted(self):
        x=fixture()
        x["sourceDiscoveryGeneratedAt"]="2026-10-15T00:00:00+09:00"
        with self.assertRaisesRegex(ValueError,"not_pinned"):
            validate(x,PLAN,SOURCE,PROJECTS)

if __name__=="__main__":
    unittest.main()
