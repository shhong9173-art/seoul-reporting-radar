"""DART producer failure must not present an old/failed snapshot as new zero filings."""
import json
import sys
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import dart_beat_run_health as health

KST=timezone(timedelta(hours=9))
NOW=datetime(2026,10,16,3,20,tzinfo=KST)
PREVIOUS={"status":"industry_beat_official_receipt_review",
          "generatedAt":"2026-10-15T18:09:23+09:00",
          "companiesCodeVerified":43,
          "companiesUnresolved":5,
          "companiesWithSourceErrors":0,
          "uninspectedRelevantDetails":4}

class HealthReport(unittest.TestCase):
    def test_failing_official_job_keeps_previous_timestamp_and_avoids_zero_claim(self):
        out=health.build(tests="success",registry="failure",
            collector="failure",publisher="skipped",published=PREVIOUS,now=NOW)
        self.assertEqual(out["executionResult"],"failed_or_skipped_last_execution_old_data_preserved")
        self.assertFalse(out["newCollectionVerified"])
        self.assertTrue(out["sourceClaimsNotVerifiedIfFailed"])
        self.assertTrue(out["latestDatasetPublished"])
        self.assertEqual(out["latestDatasetGeneratedAt"],PREVIOUS["generatedAt"])
        self.assertEqual(out["lastPublishedCoveredCompanies"],43)
        self.assertEqual(out["lastPublishedDetailBacklog"],4)
        self.assertFalse(out["publishedDataStale24h"])
        self.assertFalse(out["noNewFilingsClaimPermitted"])
        self.assertFalse(out["scoopConfirmed"])

    def test_successful_collect_but_registry_failure_is_partial(self):
        out=health.build(tests="success",registry="failure",
            collector="success",publisher="success",published=PREVIOUS,now=NOW)
        self.assertTrue(out["newCollectionVerified"])
        self.assertFalse(out["registryRefreshVerified"])
        self.assertEqual(out["executionResult"],
                         "official_list_published_registry_refresh_incomplete")

    def test_all_success_and_current_fresh_dataset(self):
        out=health.build(tests="success",registry="success",
            collector="success",publisher="success",published=PREVIOUS,now=NOW)
        self.assertTrue(out["newCollectionVerified"])
        self.assertFalse(out["publishedDataStale24h"])
        self.assertEqual(out["executionResult"],"official_list_published")

    def test_missing_output_is_unknown_not_zero(self):
        out=health.build(tests="failure",registry="skipped",
            collector="skipped",publisher="skipped",published=None,now=NOW)
        self.assertFalse(out["latestDatasetPublished"])
        self.assertIsNone(out["lastPublishedCoveredCompanies"])
        self.assertTrue(out["publishedDataStale24h"])
        self.assertFalse(out["newCollectionVerified"])

    def test_old_published_dataset_stale_even_when_success_is_claimed(self):
        old={**PREVIOUS,"generatedAt":"2026-10-13T08:00:00+09:00"}
        result=health.build(tests="success",registry="success",
            collector="success",publisher="success",published=old,now=NOW)
        self.assertTrue(result["publishedDataStale24h"])

    def test_invalid_outcome_is_normalized_not_exposed(self):
        out=health.build(tests="secret-key-123",registry="success",
            collector="success",publisher="failure",published=PREVIOUS,now=NOW)
        self.assertEqual(out["stages"]["regressionTests"],"unknown")
        self.assertNotIn("secret-key-123",json.dumps(out))

    def test_read_dataset_does_not_accept_stale_wrong_schema(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"data.json"
            path.write_text(json.dumps({"status":"source_error","generatedAt":"2026-10-15T18:00:00+09:00"}))
            self.assertIsNone(health.read_published(path))
            path.write_text(json.dumps(PREVIOUS))
            self.assertEqual(health.read_published(path)["companiesCodeVerified"],43)

    def test_workflow_always_emits_health_from_last_published_main(self):
        wf=(ROOT/".github/workflows/dart-beat-monitor.yml").read_text(encoding="utf-8")
        for literal in ("if: always()","git reset --hard origin/main",
                        "DART_COLLECT_OUTCOME:","DART_PUBLISH_OUTCOME:",
                        "dart_beat_run_health_latest.json"):
            self.assertIn(literal,wf)
        self.assertNotIn("git add -A",wf)

if __name__=="__main__":unittest.main()
