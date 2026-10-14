import copy
import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from ntis_followup_plan import build,validate_plan

SOURCE=json.loads((ROOT/"digests/ntis_patent_discovery_pc_latest.json").read_text(encoding="utf-8"))
PLAN=json.loads((ROOT/"digests/ntis_patent_followup_plan_latest.json").read_text(encoding="utf-8"))

class PlanTests(unittest.TestCase):
    def test_committed_plan_exactly_recomputed_from_official_pc_snapshot(self):
        self.assertEqual(build(SOURCE,PLAN["generatedAt"]),PLAN)
        self.assertEqual(validate_plan(PLAN,SOURCE)["boundedRequests"],15)

    def test_only_four_bounded_technology_queries_are_paginated(self):
        technical=[t for t in PLAN["tasks"] if t["strategy"]=="technology_next_pages"]
        self.assertEqual({t["query"] for t in technical},
                         {"부분방전","메타렌즈","복합패널","방열 조성물"})
        self.assertTrue(all(t["pages"]==[2,3] for t in technical))

    def test_seven_corporate_tech_queries_replace_bare_company(self):
        narrowed=[t for t in PLAN["tasks"] if t["strategy"]=="corporate_technology_narrowing"]
        self.assertEqual(len(narrowed),7)
        self.assertNotIn("현대자동차",[t["query"] for t in narrowed])
        self.assertEqual(
            len([t for t in narrowed if t["query"].startswith("현대자동차 ")]),2
        )

    def test_no_broad_applicant_pages_pulled(self):
        self.assertEqual(PLAN["applicantQueriesNotRepeated"],7)
        self.assertEqual(PLAN["duplicateBareApplicantSearchesAvoided"],1)
        for t in PLAN["tasks"]:
            self.assertNotIn(t["query"],{"현대자동차","포스코","엘에스전선"})

    def test_tampering_with_applicant_query_rejected(self):
        bad=copy.deepcopy(PLAN)
        bad["tasks"][-1]["query"]="개인정보 명단 검색"
        with self.assertRaisesRegex(ValueError,"plan_does_not_match"):
            validate_plan(bad,SOURCE)

    def test_technical_page_outside_grounded_source_rejected(self):
        bad=copy.deepcopy(PLAN)
        bad["tasks"][0]["pages"].append(4)
        with self.assertRaisesRegex(ValueError,"plan_does_not_match"):
            validate_plan(bad,SOURCE)

    def test_pagination_not_safe_when_source_is_not_current_audit(self):
        bad=copy.deepcopy(SOURCE)
        bad["checks"][0]["totalHits"]=1
        with self.assertRaisesRegex(ValueError,"plan_does_not_match"):
            validate_plan(PLAN,bad)

    def test_query_budget_cannot_be_inflated(self):
        bad=copy.deepcopy(PLAN)
        bad["maximumHttpRequests"]=100
        with self.assertRaisesRegex(ValueError,"plan_does_not_match"):
            validate_plan(bad,SOURCE)

    def test_all_targets_are_official_kipris_application_pairs(self):
        bypub={(ch["publicationNumber"],ch["applicationNumber"])
               for ch in SOURCE["checks"]}
        for task in PLAN["tasks"]:
            for pair in task["targets"]:
                self.assertIn((pair["publicationNumber"],pair["applicationNumber"]),bypub)

if __name__=="__main__":unittest.main()
