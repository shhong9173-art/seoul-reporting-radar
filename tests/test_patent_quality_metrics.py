import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import patent_quality_metrics as metrics
import patent_record_review as record

NOW=datetime(2026,10,13,9,tzinfo=timezone(timedelta(hours=9)))
PUB="1020260147319"
SECOND="1020260147965"

def fixture():
    source={"generatedAt":"2026-10-13T08:55:00+09:00",
            "items":[{"publicationNumber":PUB,"title":"플라스틱 효소 재생 기술","publicationDate":"20261008"},
                     {"publicationNumber":SECOND,"title":"도어 및 이를 갖춘 차량","publicationDate":"20261012"}]}
    story={"generatedAt":"2026-10-13T08:56:00+09:00",
           "officialSourceGeneratedAt":source["generatedAt"],"sourceWindowComplete":True,
           "investigations":[{"publicationNumber":PUB,"rank":70},
                             {"publicationNumber":SECOND,"rank":80}]}
    benchmark={"cases":[{"publicationNumber":PUB,"caseName":"CJ 협업 효소 특허"}]}
    ledger={"schemaVersion":1,"reviews":[]}
    return source,story,benchmark,ledger


class QualityTests(unittest.TestCase):
    def test_no_editorial_sample_means_null_not_fake_zero(self):
        source,story,b,ledger=fixture()
        out=metrics.summarize(story,source,ledger,b,now=NOW)
        self.assertIsNone(out["observedEditorialHitRate"])
        self.assertIsNone(out["observedFalsePositiveRate"])
        self.assertEqual(out["finalizedHumanReviewSample"],0)
        self.assertEqual(out["status"],"unmeasured_no_human_sample")
        self.assertFalse(out["exclusiveScoopsVerified"])
        self.assertEqual(out["knownCaseReplay"]["captureRate"],1.0)
        self.assertIsNone(out["knownCaseReplay"]["cases"][0]["priorToKnownArticle"])

    def test_human_outcomes_are_counted_only_for_current_candidates(self):
        source,story,b,ledger=fixture()
        ledger["reviews"]=[
            {"publicationNumber":PUB,"decision":"already_reported"},
            {"publicationNumber":SECOND,"decision":"worth_reporting"},
            {"publicationNumber":"1020260999999","decision":"published"}
        ]
        out=metrics.summarize(story,source,ledger,b,now=NOW)
        self.assertEqual(out["finalizedHumanReviewSample"],2)
        self.assertEqual(out["observedEditorialHitRate"],0.5)
        self.assertEqual(out["observedFalsePositiveRate"],0.5)
        self.assertEqual(out["humanReviewedCurrentCandidates"],2)
        self.assertEqual(out["uniqueHumanReviewedAllTime"],3)
        self.assertEqual(out["priorityScoreBuckets"]["high_70_plus"]["finalizedSample"],2)

    def test_newer_human_review_supersedes_prior_decision(self):
        source,story,b,ledger=fixture()
        ledger["reviews"]=[{"publicationNumber":PUB,"decision":"needs_reporting"},
                           {"publicationNumber":PUB,"decision":"already_reported"}]
        out=metrics.summarize(story,source,ledger,b,now=NOW)
        self.assertEqual(out["humanReviewEvents"],2)
        self.assertEqual(out["humanReviewedCurrentCandidates"],1)
        self.assertEqual(out["knownPriorCoverageCount"],1)

    def test_pending_review_excluded_from_precision_denominator(self):
        source,story,b,ledger=fixture()
        ledger["reviews"]=[{"publicationNumber":PUB,"decision":"needs_reporting"},
                           {"publicationNumber":SECOND,"decision":"published"}]
        out=metrics.summarize(story,source,ledger,b,now=NOW)
        self.assertEqual(out["finalizedHumanReviewSample"],1)
        self.assertEqual(out["observedEditorialHitRate"],1.0)
        self.assertEqual(out["pendingInvestigationCount"],1)

    def test_source_mismatch_refuses_metrics(self):
        source,story,b,ledger=fixture()
        story["officialSourceGeneratedAt"]="2026-01-01"
        with self.assertRaisesRegex(ValueError,"mismatched"):
            metrics.summarize(story,source,ledger,b)

    def test_cannot_claim_coverage_without_benchmark_sample(self):
        source,story,b,ledger=fixture()
        b={"cases":[]}
        r=metrics.summarize(story,source,ledger,b)
        self.assertIsNone(r["knownCaseReplay"]["captureRate"])

    def test_record_requires_valid_official_number_and_editor(self):
        source,story,b,ledger=fixture()
        with self.assertRaises(ValueError):
            record.record(ledger,source,"1020250000000","worth_reporting",reviewer="reporter")
        with self.assertRaises(ValueError):
            record.record(ledger,source,PUB,"worth_reporting",reviewer="not@valid")

    def test_article_based_decisions_require_public_evidence(self):
        source,story,b,ledger=fixture()
        with self.assertRaisesRegex(ValueError,"article URL"):
            record.record(ledger,source,PUB,"already_reported",reviewer="reporter")
        with self.assertRaises(ValueError):
            record.record(ledger,source,PUB,"published",evidence_url="http://example.com",reviewer="reporter")

    def test_records_valid_human_review_without_automatic_scoop_claim(self):
        source,story,b,ledger=fixture()
        out,entry=record.record(ledger,source,PUB,"already_reported",
                                evidence_url="https://example.com/news/2026",
                                reviewer="reporter",public_note="확인된 동일 기술",now=NOW)
        self.assertEqual(len(out["reviews"]),1)
        self.assertEqual(entry["publicationNumber"],PUB)
        self.assertEqual(entry["reviewer"],"reporter")
        self.assertIn("단독",entry["statusNote"])
        r=metrics.summarize(story,source,out,b,now=NOW)
        self.assertEqual(r["knownPriorCoverageCount"],1)
        self.assertFalse(r["exclusiveScoopsVerified"])


if __name__=="__main__":
    unittest.main()
