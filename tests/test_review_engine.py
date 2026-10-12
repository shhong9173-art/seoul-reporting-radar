"""Offline tests: evidence precision takes priority over speculative scoops."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import review_engine as engine


class ReviewEngineTests(unittest.TestCase):
    def row(self, receipt="20261012000123", company="현대제철", report="신규시설투자등", tag="★증설"):
        return {"receiptNo": receipt, "company": company, "report": report,
                "published": "20261012", "group": "철강", "tag": tag, "isNew": True}

    def numeric(self, doc):
        return {"generatedAt": "2026-10-12T00:00:00+09:00", "items": [doc]}

    def test_routine_filing_is_not_promoted_just_for_star(self):
        r = engine.review_item(self.row(report="임원ㆍ주요주주특정증권등소유상황보고서", tag="★임원지분"), {})
        self.assertEqual(r["lane"], "정례 공개·후순위")
        self.assertIn("판정 보류", r["exclusiveStatus"])

    def test_changed_correction_is_issuer_table_only_not_original_filing(self):
        row = self.row(report="[기재정정]생산중단", tag="★생산중단")
        num = {"receiptNo": row["receiptNo"], "corpName": "현대제철",
               "correctionComparisons": [
                   {"basis": "issuer_correction_table", "originalDocumentVerified": False,
                    "sourceUrl": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261012000123",
                    "changes": [{"field": "재개 예정일", "before": "-", "after": "2026-10-12",
                                 "category": "production_schedule"}]}
               ]}
        r = engine.review_item(row, {row["receiptNo"]: num})
        self.assertEqual(r["lane"], "정정표 변경 검토")
        self.assertEqual(r["changes"][0]["before"], "-")
        self.assertFalse(r["originalDocumentVerified"])
        self.assertIn("원공시", r["evidenceStatus"])
        self.assertIn("판정 보류", r["exclusiveStatus"])

    def test_no_numeric_cross_company_or_cross_receipt(self):
        a = self.row()
        invalid = {"receiptNo": a["receiptNo"], "corpName": "포스코",
                   "numericFacts": [{"label": "투자금액", "formatted": "1조원"}]}
        r = engine.review_item(a, {a["receiptNo"]: invalid})
        self.assertEqual(r["numericFacts"], [])
        self.assertEqual(r["changeStatus"], "동일 사건 전후 변화 미확인")

    def test_new_deal_title_alone_not_confirmed_as_material_change(self):
        r = engine.review_item(self.row(report="단일판매ㆍ공급계약체결", tag="★수주"), {})
        self.assertEqual(r["lane"], "원문·변경 사실 확인")
        self.assertEqual(r["changeStatus"], "동일 사건 전후 변화 미확인")

    def test_news_search_is_never_same_incident_proof(self):
        def search(company, term):
            return {"status": "관련 기사 검색 결과 있음: 동일 사건 여부 미검증",
                    "results": [{"title": "현대제철 관련 기사",
                                 "originallink": "https://example.com/story",
                                 "pubDate": "Mon, 12 Oct 2026 09:00:00 +0900"}]}
        r = engine.review_item(self.row(), {}, search=search)
        self.assertEqual(len(r["coverage"]["results"]), 1)
        self.assertIn("동일 사건", r["coverage"]["status"])
        self.assertIn("판정 보류", r["exclusiveStatus"])

    def test_unsafe_or_missing_news_links_are_ignored(self):
        found = engine.normalize_news([
            {"title": "<b>단독</b> 관련", "link": "javascript:alert(1)"},
            {"title": "보도", "link": "https://example.com/report"}])
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["title"], "보도")

    def test_invalid_digest_fails_closed(self):
        with self.assertRaises(ValueError):
            engine.build_review({"items": [{"receiptNo": "bad"}]}, {"items": []})

    def test_duplicates_reduced_by_receipt_not_name(self):
        rows = [self.row(), self.row(), self.row("20261012000124")]
        v = engine.build_review({"items": rows}, {"items": []})
        self.assertEqual(v["total"], 2)

    def test_correction_numeric_unknown_does_not_invent_differences(self):
        doc = {"corpName": "현대제철",
               "numericFacts": [{"label": "신규시설투자금액", "formatted": "5억원"}],
               "correctionComparisons": []}
        r = engine.review_item(self.row(), {"20261012000123": doc})
        self.assertEqual(len(r["numericFacts"]), 1)
        self.assertEqual(r["changes"], [])
        self.assertEqual(r["changeStatus"], "동일 사건 전후 변화 미확인")

    def test_priority_order_changed_before_routine(self):
        x = self.row("20261012000123", report="임원ㆍ주요주주특정증권등소유상황보고서")
        y = self.row("20261012000124", report="신규시설투자등")
        v = engine.build_review({"items": [x, y]}, {"items": []})
        self.assertEqual(v["items"][0]["receiptNo"], "20261012000124")


if __name__ == "__main__":
    unittest.main()
