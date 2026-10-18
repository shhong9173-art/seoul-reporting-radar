import copy
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from official_beat_triage_merge import merge

KST = timezone(timedelta(hours=9))
NOW = datetime(2026, 10, 18, 16, 30, tzinfo=KST)


def triage():
    return {"status": "official_date_triage",
            "generatedAt": "2026-10-17T17:16:38+09:00",
            "freshOfficialReview": [], "backgroundReference": [],
            "seen": {}, "feedHealth": [], "confirmedScoops": 0,
            "approvedArticles": 0, "firstRunBaseline": False}


def record(receipt="20261016800823", company="KG스틸", correction=False):
    return {"company": company, "corpCode": "00115676", "receiptNo": receipt,
            "published": receipt[:8],
            "report": "기업가치제고계획(자율공시) (PBR 개선 계획 제출 기업)",
            "category": "정기·주요공시", "isCorrection": correction,
            "sourceUrl": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=" + receipt,
            "status": "official_valueup_document_review",
            "firstObservedAt": "2026-10-17T20:49:36+09:00"}


def beat():
    checks = [{"company": "KG스틸", "status": "checked"}]
    checks += [{"company": "가상기업" + str(i), "status": "checked"} for i in range(44)]
    checks += [{"company": "미등록" + str(i), "status": "corp_code_unavailable"}
               for i in range(3)]
    return {"status": "industry_beat_official_receipt_review",
            "generatedAt": "2026-10-18T09:24:53+09:00",
            "scopeCompanyCount": 48, "companiesCodeVerified": 45,
            "companiesUnresolved": 3, "companiesWithSourceErrors": 0,
            "sourceChecks": checks, "records": [record()]}


class BeatQueueIntegration(unittest.TestCase):
    def test_kg_valueup_is_public_review_not_exclusive(self):
        out = merge(triage(), beat(), now=NOW)
        self.assertEqual(out["beatWideDartAdded"], 1)
        self.assertEqual(out["freshOfficialReviewCount"], 1)
        item = out["freshOfficialReview"][0]
        self.assertEqual(item["officialReceiptNo"], "20261016800823")
        self.assertEqual(item["officialDate"], "2026-10-16")
        self.assertEqual(item["sourceSnapshotAt"], "2026-10-18T09:24:53+09:00")
        self.assertEqual(out["beatWideDartSourceAt"], item["sourceSnapshotAt"])
        self.assertEqual(item["firstObservedAt"], "2026-10-17")
        self.assertFalse(item["exclusiveConfirmed"])
        self.assertFalse(item["priorMediaCoverageVerified"])
        self.assertFalse(item["approvedForPitch"])
        self.assertFalse(item["originalDocumentFieldsVerified"])
        self.assertEqual(out["confirmedScoops"], 0)
        self.assertEqual(out["feedHealth"][-1]["status"], "partial_issuer_coverage")
        self.assertFalse(out["sourceCompletenessVerified"])
        self.assertNotIn("20%p", item["officialFact"])

    def test_rerun_is_idempotent(self):
        first = merge(triage(), beat(), now=NOW)
        second = merge(first, beat(), now=NOW)
        self.assertEqual(second["beatWideDartAdded"], 0)
        self.assertEqual(second["freshOfficialReviewCount"], 1)
        self.assertEqual(second["baseTriageGeneratedAt"],
                         "2026-10-17T17:16:38+09:00")

    def test_same_filing_from_contract_feed_is_not_repeated(self):
        q = triage()
        q["freshOfficialReview"] = [
            {"id": "DART_FILING:20261016800823", "officialDate": "2026-10-16"}]
        self.assertEqual(merge(q, beat(), now=NOW)["beatWideDartAdded"], 0)

    def test_old_first_discovery_is_background(self):
        b = beat()
        b["records"] = [record(receipt="20260930000001")]
        out = merge(triage(), b, now=NOW)
        self.assertEqual(out["freshOfficialReviewCount"], 0)
        self.assertEqual(out["backgroundReferenceCount"], 1)
        self.assertFalse(out["backgroundReference"][0]["officialDateInRecentWindow"])

    def test_correction_unknown_company_and_spoofed_url_fail_closed(self):
        b = beat()
        b["records"] = [record(correction=True), record(company="가짜회사")]
        fake = record(receipt="20261016800824")
        fake["sourceUrl"] = "https://dart.fss.or.kr.attacker.test/?rcpNo=20261016800824"
        b["records"].append(fake)
        out = merge(triage(), b, now=NOW)
        self.assertEqual(out["beatWideDartExcluded"], 3)
        self.assertEqual(out["beatWideDartAdded"], 0)

    def test_stale_and_source_error_not_clean_zero(self):
        b = beat()
        b["generatedAt"] = "2026-10-16T09:00:00+09:00"
        out = merge(triage(), b, now=NOW)
        self.assertEqual(out["feedHealth"][-1]["status"], "snapshot_older_than_24h")
        b = beat()
        b["sourceChecks"][1]["status"] = "source_error"
        b["companiesCodeVerified"] = 44
        b["companiesWithSourceErrors"] = 1
        out = merge(triage(), b, now=NOW)
        self.assertEqual(out["feedHealth"][-1]["status"], "partial_collection")
        self.assertFalse(out["sourceCompletenessVerified"])

    def test_malformed_snapshot_not_zero_results(self):
        b = beat()
        b["companiesCodeVerified"] = 44
        out = merge(triage(), b, now=NOW)
        self.assertEqual(out["beatWideDartAdded"], 0)
        self.assertEqual(out["feedHealth"][-1]["status"], "source_missing_or_malformed")
        self.assertIsNone(out["feedHealth"][-1]["records"])


if __name__ == "__main__":
    unittest.main()
