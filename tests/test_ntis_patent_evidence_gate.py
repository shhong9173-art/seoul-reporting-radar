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
    def test_actual_approved_pc_last_page_closes_only_its_gap(self):
        path=ROOT/"digests/ntis_project_page_followup_pc_latest.json"
        self.assertTrue(path.is_file(),"Reviewed official result must be committed")
        data=read("digests/ntis_project_page_followup_pc_latest.json")
        from ntis_project_page_followup_validate import validate
        pinned=read("digests/ntis_project_reverse_kipris_source.json")
        result=validate(data,PLAN,REMAINING,pinned)
        self.assertEqual(result["currentPageRows"],11)
        self.assertEqual(result["reviewOnlyNumberPairs"],0)
        self.assertFalse(result["offlineSynthetic"])
        evidence=load_evidence(ROOT)
        record=evidence["1020260145290"]
        self.assertEqual(record["status"],"bounded_inspected_no_official_pair_observed")
        self.assertEqual(record["uninspectedRelatedProjectCount"],0)
        self.assertEqual(record["officialNumberPairsForHumanReview"],0)
        self.assertFalse(record["projectParticipationVerified"])
        self.assertFalse(record["exclusiveProven"])

    def test_published_triage_snapshot_agrees_with_official_page_result(self):
        # 11-23: 공개 특허는 검토 대기열에서 날짜가 지나면 빠진다(11-21 판 176줄에 1020260145290 없음) — 운영 자료가 바뀔 때마다
        # 이 테스트가 실패해 무관한 NTIS PR이 막히지 않게, 그 공개번호가 대기열에 있을 때만 근거 상태를 맞춰 보고 단독 확정 0은 늘 본다
        raw=read("digests/patent_reporting_triage_latest.json")
        matches=[r for r in raw["reviewQueue"] if r["publicationNumber"]=="1020260145290"]
        self.assertLessEqual(len(matches),1)
        for m in matches:
            self.assertEqual(m["ntisResearchEvidence"]["status"],"bounded_inspected_no_official_pair_observed")
            self.assertEqual(m["ntisResearchEvidence"]["uninspectedRelatedProjectCount"],0)
        self.assertFalse(any(r.get("exclusiveProven") for r in raw["reviewQueue"]))
        self.assertEqual(raw["confirmedExclusives"],0)

if __name__=="__main__":unittest.main()
