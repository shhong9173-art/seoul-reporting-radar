import copy
import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from ntis_project_page_followup_validate import validate

def read(file):
    return json.loads((ROOT/file).read_text(encoding="utf-8-sig"))

PLAN=read("digests/ntis_project_reverse_plan_latest.json")
SOURCE=read("digests/ntis_project_reverse_remaining_23_pc_latest.json")
PINNED=read("digests/ntis_project_reverse_kipris_source.json")
def fixture():
    return dict(profile="ntis_rpatent_single_project_page_followup_v1",
        generatedAt="2026-10-15T12:01:00+09:00",
        sourceReverseGeneratedAt=SOURCE["generatedAt"],
        planGeneratedAt=PLAN["generatedAt"],
        projectNumber="1415180715",status="ready",
        collectionMethod="approved_pc_ntis_rpatent_targeted_page_followup",
        offlineSynthetic=False,queryMode="primary",pageSize=10,
        currentQueryTotalHits=11,firstPageRows=10,secondPageRows=1,
        rowsInspected=11,actualHttpRequests=2,maxHttpRequests=2,
        distinctResultIDs=11,paginationConfirmedByDisjointIds=True,
        currentQueryFullyInspected=True,
        matchedOfficialProjectApplicationRows=0,records=[],
        verifiedPatentProjectOutcomes=0,confirmedCommercialization=0,
        confirmedExclusives=0,
        warning="Historical results were not retained; no assertion of equivalence.")
def pair():
    return dict(projectNumber="1415180715",publicationNumber="1020260145290",
        applicationNumber="1020250039383",officialResultID="MOCKPAGE11B",
        sourceProjectID="1415180715",sourceRegistType="출원",sourceRegistTypeCode="01",
        sourceRegistNumber="10-2025-0039383",resultTitle="Test only",
        sameOfficialHitIdentifiers=True,officialPatentProjectOutcomeVerified=False,
        commercializationConfirmed=False,exclusiveConfirmed=False)
def call(x,**kw):return validate(x,PLAN,SOURCE,PINNED,**kw)
class FollowupTest(unittest.TestCase):
    def test_empty_current_11_is_only_an_observed_zero(self):
        self.assertEqual(call(fixture())["reviewOnlyNumberPairs"],0)
    def test_exact_pair_is_human_review_only(self):
        x=fixture();x["matchedOfficialProjectApplicationRows"]=1;x["records"]=[pair()]
        self.assertEqual(call(x)["reviewOnlyNumberPairs"],1)
    def test_wrong_official_project(self):
        x=fixture();x["matchedOfficialProjectApplicationRows"]=1;x["records"]=[pair()]
        x["records"][0]["sourceProjectID"]="1415146190"
        with self.assertRaisesRegex(ValueError,"wrong_official_project"):call(x)
    def test_wrong_application(self):
        x=fixture();x["matchedOfficialProjectApplicationRows"]=1;x["records"]=[pair()]
        x["records"][0]["sourceRegistNumber"]="10-2026-0145290"
        with self.assertRaisesRegex(ValueError,"wrong_official_project"):call(x)
    def test_registered_cannot_masquerade_as_application(self):
        x=fixture();x["matchedOfficialProjectApplicationRows"]=1;x["records"]=[pair()]
        x["records"][0]["sourceRegistType"]="등록"
        with self.assertRaisesRegex(ValueError,"registered_not_application"):call(x)
    def test_duplicated_page_or_failed_second_page_rejected(self):
        x=fixture();x["distinctResultIDs"]=10
        with self.assertRaisesRegex(ValueError,"wrong_current_11"):call(x)
        x=fixture();x["paginationConfirmedByDisjointIds"]=False
        with self.assertRaisesRegex(ValueError,"pagination_not_verified"):call(x)
    def test_source_mutation_rejected(self):
        x=fixture();x["sourceReverseGeneratedAt"]="2026-10-16T10:00:00+09:00"
        with self.assertRaisesRegex(ValueError,"followup_provenance"):call(x)
    def test_false_exclusive_rejected(self):
        x=fixture();x["confirmedExclusives"]=1
        with self.assertRaisesRegex(ValueError,"wrong_current_11"):call(x)
    def test_synthetic_cannot_be_imported_as_real(self):
        x=fixture();x["offlineSynthetic"]=True
        x["collectionMethod"]="offline_synthetic_test_not_real"
        with self.assertRaisesRegex(ValueError,"synthetic_result_is_not_real"):call(x)
        self.assertTrue(call(x,allow_offline=True)["offlineSynthetic"])
    def test_no_credentials_or_raw_unrelated_rows(self):
        x=fixture();x["warning"]="apprvKey=EXAMPLE"
        with self.assertRaisesRegex(ValueError,"credential_leak"):call(x)
if __name__=="__main__":unittest.main()
