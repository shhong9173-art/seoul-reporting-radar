import copy
import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from ntis_project_reverse_plan import project_ids,verified_target_applications,build,validate_plan

def read(path):
    return json.loads((ROOT/path).read_text(encoding="utf-8-sig"))

PLAN=read("digests/ntis_project_reverse_plan_latest.json")
PROJECTS=read("digests/ntis_project_leads_latest.json")
PINNED=read("digests/ntis_project_reverse_kipris_source.json")
DOSSIER=PINNED["dossier"]
DEEP=PINNED["deep"]

class ReversePlanTests(unittest.TestCase):
    def test_all_unique_26_official_project_numbers(self):
        self.assertEqual(len(project_ids(PROJECTS)),26)
        self.assertEqual(PLAN["projectCount"],26)
        self.assertEqual(PLAN["absoluteMaxHttpRequests"],52)
        self.assertEqual(PLAN["maxRowsPerQuery"],10)

    def test_one_source_project_can_appear_in_two_keyword_searches(self):
        p=project_ids(PROJECTS)
        self.assertGreaterEqual(p["2410019058"]["sourceRecordOccurrences"],2)
        self.assertIn("한빛이디에스 부분방전",p["2410019058"]["earlierKeywordMatchedQueries"])

    def test_all_7_kipris_applications_are_legacy_source_verified(self):
        apps=verified_target_applications(DOSSIER,DEEP)
        self.assertEqual(len(apps),7)
        self.assertEqual(apps,PLAN["targetKiprisApplications"])

    def test_top_priorities_are_2026_as_scheduling_not_scoop(self):
        self.assertTrue(all(p["projectYear"]=="2026" for p in PLAN["projects"][:3]))
        self.assertEqual(PLAN["projects"][0]["projectNumber"],"2410017694")
        self.assertEqual(PLAN["projects"][2]["projectNumber"],"2410019058")

    def test_exact_plan_reconstructed_from_official_snapshots(self):
        self.assertEqual(build(PROJECTS,DOSSIER,DEEP,PLAN["generatedAt"]),PLAN)
        self.assertEqual(validate_plan(PLAN,PROJECTS,DOSSIER,DEEP)["projects"],26)

    def test_old_project_keyword_match_not_patent_outcome(self):
        self.assertTrue(PLAN["projects"][0]["earlierKeywordMatchedPatentPublications"])
        self.assertFalse(any("outcomeConfirmed" in p for p in PLAN["projects"]))

    def test_changed_project_list_refused(self):
        stale=copy.deepcopy(PROJECTS)
        stale["checks"][0]["records"]=[]
        with self.assertRaisesRegex(ValueError,"project_count_changed"):
            validate_plan(PLAN,stale,DOSSIER,DEEP)

    def test_unofficial_app_number_refused(self):
        changed=copy.deepcopy(DEEP)
        changed["investigations"]=[]
        with self.assertRaisesRegex(ValueError,"no_official_kipris_target_application_numbers"):
            validate_plan(PLAN,PROJECTS,DOSSIER,changed)

    def test_tampered_plan_query_budget_refused(self):
        changed=copy.deepcopy(PLAN)
        changed["absoluteMaxHttpRequests"]=1000
        with self.assertRaisesRegex(ValueError,"plan_or_source_mismatch"):
            validate_plan(changed,PROJECTS,DOSSIER,DEEP)

    def test_project_query_modes_use_documented_ti_and_ti03(self):
        self.assertIn("searchField=TI",PLAN["searchProfilePrimary"])
        self.assertIn("TI03=ProjectID",PLAN["searchProfileFallback"])
        self.assertIn("not_yet_verified",PLAN["fallbackStatus"])

if __name__=="__main__":unittest.main()
