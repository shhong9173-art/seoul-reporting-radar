import copy
import sys
import json
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from ntis_patent_evidence_gate import build_evidence,load_evidence
read=lambda path:json.loads((ROOT/path).read_text(encoding="utf-8-sig"))
PLAN=read("digests/ntis_project_reverse_plan_latest.json")
PILOT=read("digests/ntis_project_reverse_pc_latest.json")
REMAINING=read("digests/ntis_project_reverse_remaining_23_pc_latest.json")

class EvidenceGateTests(unittest.TestCase):
    def test_page_gap_and_zero_pairs_are_not_missing_patent_outcomes(self):
        data=build_evidence(PLAN,PILOT,REMAINING)
        ls=data["1020260145290"]
        self.assertEqual(ls["status"],"partially_inspected_no_official_pair_observed")
        self.assertEqual(ls["officialNumberPairsForHumanReview"],0)
        self.assertEqual(ls["uninspectedRelatedProjectCount"],1)
        self.assertFalse(ls["exclusiveProven"])
    def test_keyword_only_patent_has_no_false_observed_zero(self):
        data=build_evidence(PLAN,PILOT,REMAINING)
        other=data["1020260148086"]
        self.assertEqual(other["status"],"keyword_only_no_frozen_kipris_application")
        self.assertIsNone(other["officialNumberPairsForHumanReview"])
    def test_bad_plan_or_snapshot_rejected(self):
        x=copy.deepcopy(REMAINING);x["planGeneratedAt"]="changed"
        with self.assertRaisesRegex(ValueError,"ntis_source_mismatch"):
            build_evidence(PLAN,PILOT,x)
    def test_false_same_hit_rejected(self):
        x=copy.deepcopy(REMAINING)
        x["reviewedNumberPairs"]=1
        x["records"]=[dict(projectNumber="1415180715",
            publicationNumber="1020260145290",applicationNumber="1020250039383",
            sourceProjectID="1415180715",sourceRegistType="등록",
            sourceRegistTypeCode="02",sourceRegistNumber="10-2025-0039383",
            sameOfficialHitIdentifiers=True,officialPatentProjectOutcomeVerified=False,
            commercializationConfirmed=False,exclusiveConfirmed=False,officialResultID="MOCK1234")]
        with self.assertRaisesRegex(ValueError,"invalid_ntis_pair"):
            build_evidence(PLAN,PILOT,x)
    def test_bound_scan_is_not_exclusive(self):
        data=load_evidence(ROOT)
        self.assertIsNotNone(data)
        self.assertFalse(any(x["exclusiveProven"] for x in data.values()))
    def test_synthetic_followup_rejected(self):
        x={"collectionMethod":"offline_synthetic_test_not_real",
           "offlineSynthetic":True}
        with self.assertRaisesRegex(ValueError,"unverified_ntis_followup"):
            build_evidence(PLAN,PILOT,REMAINING,x)
if __name__=="__main__":unittest.main()
