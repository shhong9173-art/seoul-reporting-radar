import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import patent_run_health as p

KST=timezone(timedelta(hours=9))


def snap(root,name,payload):
    d=root/"digests"
    d.mkdir(parents=True,exist_ok=True)
    (d/name).write_text(json.dumps(payload,ensure_ascii=False),encoding="utf-8")


class HealthTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        snap(self.root,"patent_hunt_latest.json",{
            "generatedAt":"2026-10-13T09:00:00+09:00",
            "sourceWindowComplete":True,"applicantCount":24,
            "completelyCheckedCompanies":24,"companyChecks":[]})
        snap(self.root,"patent_deep_latest.json",{
            "generatedAt":"2026-10-13T09:01:00+09:00",
            "patentDatasetGeneratedAt":"2026-10-13T09:00:00+09:00"})
        snap(self.root,"patent_story_latest.json",{
            "generatedAt":"2026-10-13T09:02:00+09:00",
            "officialSourceGeneratedAt":"2026-10-13T09:00:00+09:00",
            "deepSourceGeneratedAt":"2026-10-13T09:01:00+09:00",
            "possibleResearchLeads":19,"mediaQueriesCompleted":14})
        snap(self.root,"patent_quality_latest.json",{
            "generatedAt":"2026-10-13T09:02:15+09:00",
            "officialSourceGeneratedAt":"2026-10-13T09:00:00+09:00",
            "storySourceGeneratedAt":"2026-10-13T09:02:00+09:00",
            "humanReviewedCurrentCandidates":0})
        snap(self.root,"patent_desk_latest.json",{
            "generatedAt":"2026-10-13T09:02:45+09:00",
            "officialSourceGeneratedAt":"2026-10-13T09:00:00+09:00",
            "deepSourceGeneratedAt":"2026-10-13T09:01:00+09:00",
            "storySourceGeneratedAt":"2026-10-13T09:02:00+09:00",
            "candidateCount":12,"shortlistCount":4,"publicationReady":0})
        snap(self.root,"patent_claim_review_latest.json",{
            "generatedAt":"2026-10-13T09:02:30+09:00",
            "patentDatasetGeneratedAt":"2026-10-13T09:00:00+09:00",
            "deepDatasetGeneratedAt":"2026-10-13T09:01:00+09:00"})
    def tearDown(self):
        self.temp.cleanup()
    def test_consistent_success_is_ready(self):
        x=p.audit(dict.fromkeys(p.STEPS,"success"),root=self.root)
        self.assertEqual(x["status"],"ready")
        self.assertTrue(x["datasets"]["story"]["consistent"])
        self.assertFalse(x["scoopConfirmed"])
        self.assertEqual(x["datasets"]["story"]["coverageQueries"],14)
    def test_api_failure_with_old_successful_files_is_degraded(self):
        steps=dict.fromkeys(p.STEPS,"success")
        steps["source"]="failure"
        x=p.audit(steps,root=self.root)
        self.assertEqual(x["status"],"degraded")
        self.assertFalse(x["datasets"]["source"]["consistent"])
    def test_missing_story_artifact_is_not_zero_leads(self):
        (self.root/"digests/patent_story_latest.json").unlink()
        x=p.audit(dict.fromkeys(p.STEPS,"success"),root=self.root)
        self.assertEqual(x["status"],"degraded")
        self.assertFalse(x["datasets"]["story"]["exists"])
        self.assertIsNone(x["datasets"]["story"]["generatedAt"])
    def test_missing_desk_shortlist_makes_pipeline_degraded(self):
        (self.root/"digests/patent_desk_latest.json").unlink()
        x=p.audit(dict.fromkeys(p.STEPS,"success"),root=self.root)
        self.assertEqual(x["status"],"degraded")
        self.assertEqual(x["editorialDeskStatus"],"partial_or_missing")

    def test_desk_provenance_mismatch_stays_degraded(self):
        snap(self.root,"patent_desk_latest.json",{
            "generatedAt":"2026-10-13T09:02:45+09:00",
            "officialSourceGeneratedAt":"2026-10-12T09:00:00+09:00",
            "deepSourceGeneratedAt":"2026-10-13T09:01:00+09:00",
            "storySourceGeneratedAt":"2026-10-13T09:02:00+09:00",
            "candidateCount":12})
        x=p.audit(dict.fromkeys(p.STEPS,"success"),root=self.root)
        self.assertFalse(x["datasets"]["desk"]["consistent"])
        self.assertEqual(x["status"],"degraded")

    def test_missing_quality_digest_makes_pipeline_degraded(self):
        (self.root/"digests/patent_quality_latest.json").unlink()
        x=p.audit(dict.fromkeys(p.STEPS,"success"),root=self.root)
        self.assertEqual(x["status"],"degraded")
        self.assertEqual(x["editorialQualityStatus"],"partial_or_missing")

    def test_cross_dataset_mismatch_degraded(self):
        snap(self.root,"patent_story_latest.json",{
            "generatedAt":"2026-10-13T09:02:00+09:00",
            "officialSourceGeneratedAt":"2026-10-12T09:00:00+09:00",
            "deepSourceGeneratedAt":"2026-10-13T09:01:00+09:00"})
        x=p.audit(dict.fromkeys(p.STEPS,"success"),root=self.root)
        self.assertEqual(x["status"],"degraded")
        self.assertFalse(x["datasets"]["story"]["consistent"])


if __name__=="__main__":
    unittest.main()
