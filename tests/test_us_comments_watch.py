"""regulations.gov: only comments whose submitter is a beat company; failures are not zero; budget respected."""
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import us_comments_watch as w  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 10, 27, 8, 20, tzinfo=KST)


class R:
    def __init__(self, code, body=None):
        self.status_code, self.body = code, body

    def json(self):
        return self.body


def comment(cid, title, posted):
    return {"id": cid, "attributes": {"title": title, "postedDate": posted + "T04:00:00Z", "agencyId": cid.split("-")[0]}}


HYUNDAI = {"data": [
    comment("NHTSA-2026-1585-0008", "Comment from Hyundai Motor Group", "2026-10-20"),
    comment("EPA-HQ-OAR-2025-3297-0160", "Comment submitted by Hyundai Motor America", "2026-07-07"),
    comment("NHTSA-2025-0491-5248", "Comment from International Council on Clean Transportation", "2026-02-04"),
    comment("ICEB-2026-0100-3761", "Comment Submitted by Anonymous", "2026-10-26"),
]}


def fake(routes, calls):
    def get(url, params, headers, timeout):
        calls.append((url, dict(params)))
        for key, resp in routes.items():
            if key in url or key == params.get("filter[searchTerm]"):
                return resp
        return R(200, {"data": []})
    return get


class Comments(unittest.TestCase):
    def test_submitter_filter_enrichment_and_new_flags(self):
        calls = []
        routes = {
            '"Hyundai Motor"': R(200, HYUNDAI),
            '"POSCO"': R(429),
            "/dockets/NHTSA-2026-1585": R(200, {"data": {"attributes": {"title": "Part 555 exemptions"}}}),
            "/comments/NHTSA-2026-1585-0008": R(200, {"data": {"attributes": {"comment": "<p>Please see attached comments from Hyundai Motor Group.</p>"}},
                                                     "included": [{"attributes": {"fileFormats": [{"fileUrl": "https://downloads.regulations.gov/x.pdf"}]}}]}),
        }
        prev = {"items": [{"id": "EPA-HQ-OAR-2025-3297-0160", "firstSeen": "2026-07-08T09:00:00+09:00", "attachments": [], "excerpt": "old"}]}
        doc = w.collect("KEY", now=NOW, previous=prev, get=fake(routes, calls), sleep=lambda s: None)
        ids = [x["id"] for x in doc["items"]]
        self.assertEqual(ids, ["NHTSA-2026-1585-0008", "EPA-HQ-OAR-2025-3297-0160"])  # ICCT and anonymous dropped
        top = doc["items"][0]
        self.assertEqual(top["submitter"], "Hyundai Motor Group")
        self.assertEqual(top["docketTitle"], "Part 555 exemptions")
        self.assertEqual(top["attachments"], ["https://downloads.regulations.gov/x.pdf"])
        self.assertTrue(top["isNew"])
        old = doc["items"][1]
        self.assertFalse(old["isNew"])
        self.assertEqual(old["firstSeen"], "2026-07-08T09:00:00+09:00")
        posco = next(c for c in doc["checks"] if c["phrase"] == "POSCO")
        self.assertEqual(posco["status"], "failed")
        self.assertIn("429", posco["error"])
        self.assertEqual(doc["status"], "partial")
        q = next(p for u, p in calls if p.get("filter[searchTerm]") == '"Hyundai Motor"')
        self.assertEqual(q["api_key"], "KEY")
        self.assertEqual(q["filter[postedDate][ge]"], "2026-04-30")

    def test_phrase_added_later_reads_old_comments_as_baseline(self):
        # 11-01: 석유화학 6곳을 더한 첫 실행에 롯데케미칼 6월 의견서가 오늘 B로 떴다
        later = dt.datetime(2026, 11, 2, 8, 20, tzinfo=KST)
        lotte = {"data": [comment("USTR-2026-0232-0137", "Comment from Lotte Chemical California, Inc.", "2026-06-11"),
                          comment("EPA-HQ-2026-0001-0009", "Comment from Lotte Chemical Corporation", "2026-10-30")]}
        prev = {"items": [], "checks": [{"company": c, "phrase": ph, "status": "ok"} for c, ph, _ in w.COMPANIES
                                          if ph != "Lotte Chemical"]}
        doc = w.collect("KEY", now=later, previous=prev, get=fake({'"Lotte Chemical"': R(200, lotte)}, []), sleep=lambda s: None)
        by = {x["id"]: x for x in doc["items"]}
        self.assertEqual((by["USTR-2026-0232-0137"]["baseline"], by["USTR-2026-0232-0137"]["isNew"]), (True, False))
        self.assertEqual((by["EPA-HQ-2026-0001-0009"]["baseline"], by["EPA-HQ-2026-0001-0009"]["isNew"]), (False, True))
        # 다음 실행에도 기준선 표시는 이어진다
        again = w.collect("KEY", now=later + dt.timedelta(days=1), previous=doc, get=fake({'"Lotte Chemical"': R(200, lotte)}, []),
                          sleep=lambda s: None)
        self.assertTrue(next(x for x in again["items"] if x["id"] == "USTR-2026-0232-0137")["baseline"])

    def test_items_stored_new_on_1101_for_added_companies_are_repaired(self):
        later = dt.datetime(2026, 11, 2, 8, 20, tzinfo=KST)
        lotte = {"data": [comment("USTR-2026-0232-0106", "Comment from Lotte Chemical California, Inc.", "2026-06-03")]}
        prev = {"items": [{"id": "USTR-2026-0232-0106", "company": "롯데케미칼", "firstSeen": "2026-11-01T16:40:12+09:00",
                           "postedDate": "2026-06-03", "attachments": [], "excerpt": "x"}],
                "checks": [{"company": c, "phrase": ph, "status": "ok"} for c, ph, _ in w.COMPANIES]}
        doc = w.collect("KEY", now=later, previous=prev, get=fake({'"Lotte Chemical"': R(200, lotte)}, []), sleep=lambda s: None)
        self.assertTrue(doc["items"][0]["baseline"])
        self.assertFalse(doc["items"][0]["isNew"])

    def test_budget_marks_the_rest_as_skipped_not_zero(self):
        calls = []
        doc = w.collect("DEMO_KEY", now=NOW, get=fake({}, calls), sleep=lambda s: None, budget=w.Budget(3))
        self.assertEqual(len(calls), 3)
        skipped = [c for c in doc["checks"] if c["status"] == "skipped"]
        self.assertEqual(len(skipped), len(w.COMPANIES) - 3)
        self.assertEqual(doc["keyType"], "DEMO_KEY")

    def test_submitter_parsing(self):
        self.assertEqual(w.submitter_of("Comment from Kia America, Inc."), "Kia America, Inc.")
        self.assertEqual(w.submitter_of("Comment submitted by Hyundai Motor America"), "Hyundai Motor America")
        self.assertIsNone(w.submitter_of("Hyundai Motor Group comments"))


if __name__ == "__main__":
    unittest.main()
