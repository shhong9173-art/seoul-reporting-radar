"""영국 정부 무역구제 고시(gov.uk) 감시 — 11-19 탐침 18의 실제 제목·주소 모양으로."""
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import uk_trade_notices_watch as w  # noqa: E402

KST = w.KST
HR = "/government/publications/trade-remedies-notice-hot-rolled-steel-plates-originating-from-south-korea-anti-dumping"
PVC = "/government/publications/trade-remedies-notices-s-pvc-from-china-mexico-and-south-korea"
MOW = "/government/publications/trade-remedies-notices-robot-lawn-mowers-from-china-anti-dumping"
A32 = HR + "/trade-remedies-notice-202632-definitive-anti-dumping-measure-on-hot-rolled-steel-plate-originating-from-south-korea"
A17 = HR + "/trade-remedies-notice-202617-rejection-of-the-tras-recommendation-to-apply-a-provisional-anti-dumping-measure"
A16 = HR + "/trade-remedies-notice-202514-registration-of-imports-of-hot-rolled-steel-plates-originating-from-south-korea"
APVC = PVC + "/trade-remedies-notice-202630-s-pvc"
# 탐침 18에서 읽은 2026/32 본문 표 글자(세율 줄은 실제), 앞뒤 문장은 모양만 맞춘 글
BODY32 = ("<p>This notice sets out the definitive anti-dumping measure. The measure applies for 5 years from 19 November 2026.</p>"
          "<h2>Anti-dumping duty rates for overseas exporters</h2><table><tr><th>Overseas exporter/producer</th><th>Dumping margin</th><th>Additional code</th></tr>"
          "<tr><td>Hyundai Steel</td><td>7.04%</td><td>8A78</td></tr><tr><td>POSCO</td><td>12.19%</td><td>8A79</td></tr>"
          "<tr><td>All other overseas exporters/producers</td><td>23.07%</td><td>8A80</td></tr>"
          "<tr><td>Hot-rolled steel plates with a width exceeding 2100mm</td><td>0%</td><td>8A81</td></tr></table>"
          "<p>The Secretary of State has decided not to accept the TRA recommendation in full for products with a width over 2100mm.</p>")


class R:
    def __init__(self, status=200, data=None):
        self.status_code, self._d = status, data

    def json(self):
        return self._d


def collection(updated_hr="2026-07-01T10:00:00Z"):
    return {"links": {"documents": [
        {"title": "Trade remedies notices: robot lawn mowers from China (anti-dumping)", "base_path": MOW, "public_updated_at": "2026-11-18T15:30:03Z"},
        {"title": "Trade remedies notice: hot-rolled steel plates originating from South Korea (anti-dumping)", "base_path": HR, "public_updated_at": updated_hr},
        {"title": "Trade remedies notices: S-PVC from China, Mexico and South Korea", "base_path": PVC, "public_updated_at": "2026-10-21T10:45:58Z"}]}}


def fake(with32=False, fail=(), updated_hr=None):
    calls = []
    atts = [{"title": "Trade remedies notice 2026/17: rejection of the TRA’s recommendation to apply a provisional anti-dumping measure on hot-rolled steel plate originating from South Korea", "url": A17, "content_type": "text/html"},
            {"title": "Trade remedies notice 2025/16: registration of imports of hot-rolled steel plates originating from South Korea", "url": A16, "content_type": "text/html"}]
    if with32:
        atts.insert(0, {"title": "Trade remedies notice 2026/32: definitive anti-dumping measure on hot-rolled steel plate originating from South Korea", "url": A32, "content_type": "text/html"})
    pages = {
        w.COLLECTION: collection(updated_hr or ("2026-11-18T13:00:04Z" if with32 else "2026-07-01T10:00:00Z")),
        w.API + HR: {"title": "Trade remedies notice: hot-rolled steel plates originating from South Korea (anti-dumping)", "details": {"attachments": atts}},
        w.API + PVC: {"title": "Trade remedies notices: S-PVC from China, Mexico and South Korea", "details": {"attachments": [
            {"title": "Trade remedies notice 2026/30: registration of imports of S-PVC", "url": APVC, "content_type": "text/html"}]}},
        w.API + A32: {"first_published_at": "2026-11-18T13:00:04+00:00", "details": {"body": BODY32}},
        w.API + A17: {"first_published_at": "2026-04-02T11:00:00+01:00", "details": {"body": "<p>The Secretary of State has decided to reject the TRA recommendation to apply a provisional measure.</p>"}},
        w.API + A16: {"first_published_at": "2025-07-23T00:00:00+01:00", "details": {"body": "<p>Imports of the goods are subject to registration.</p>"}},
        w.API + APVC: {"first_published_at": "2026-10-21T10:45:58+01:00", "details": {"body": "<p>Registration of imports of S-PVC.</p>"}},
    }

    def get(url, headers=None, timeout=None):
        calls.append(url)
        if any(f in url for f in fail):
            return R(503)
        return R(200, pages[url]) if url in pages else R(404)
    return get, calls


NOW = dt.datetime(2026, 11, 18, 18, 20, tzinfo=KST)


class Notices(unittest.TestCase):
    def test_first_run_is_baseline_korea_only(self):
        get, calls = fake()
        doc = w.run(NOW, None, get=get, sleep=lambda s: None)
        self.assertEqual(doc["status"], "ok")
        self.assertEqual(doc["events"], [])
        self.assertNotIn(w.API + MOW, calls)                                  # 한국 아닌 게시물은 안 연다
        ids = {n["id"]: n for n in doc["notices"]}
        self.assertEqual(len(ids), 3)
        self.assertTrue(all(n["baseline"] for n in ids.values()))
        n17 = next(n for n in ids.values() if n["number"] == "2026/17")
        self.assertEqual((n17["kind"], n17["tier"]), ("TRA 권고 거부", "A"))
        self.assertEqual(next(n for n in ids.values() if n["number"] == "2025/16")["kind"], "수입 등록")
        self.assertEqual(n17["product"], "hot-rolled steel plates")
        self.assertEqual(doc["checks"][0]["korea"], 2)

    def test_new_attachment_on_updated_publication_is_event_with_rates(self):
        get, _ = fake()
        doc = w.run(NOW, None, get=get, sleep=lambda s: None)
        get2, calls2 = fake(with32=True)
        later = NOW + dt.timedelta(hours=4)
        doc2 = w.run(later, doc, get=get2, sleep=lambda s: None)
        self.assertNotIn(w.API + PVC, calls2)                                  # 갱신 시각이 그대로인 게시물은 다시 안 읽음
        self.assertEqual([c for c in calls2 if c.startswith(w.API + HR + "/")], [w.API + A32])   # 처음 보는 첨부만
        self.assertEqual(len(doc2["events"]), 1)
        e = doc2["events"][0]
        self.assertEqual((e["tier"], e["kind"], e["number"], e["date"]), ("A", "영국 정부 무역구제 고시(확정 조치)", "2026/32", "2026-11-18"))
        self.assertEqual(e["companies"], ["포스코", "현대제철"] if e["companies"][0] == "포스코" else ["현대제철", "포스코"])
        self.assertIn("영국 정부 무역구제 고시 2026/32 — 확정 조치: 「Trade remedies notice 2026/32: definitive anti-dumping measure on hot-rolled steel plate", e["text"])
        self.assertIn("업체별 세율 Hyundai Steel 7.04%(8A78) · POSCO 12.19%(8A79) · 그 밖 수출자·생산자 23.07%(8A80) · Hot-rolled steel plates with a width exceeding 2100mm 0.00%(8A81)", e["text"])
        self.assertIn("권고 대목 「The Secretary of State has decided not to accept the TRA recommendation", e["text"])
        self.assertIn("기간 대목 「The measure applies for 5 years from 19 November 2026.」", e["text"])
        self.assertEqual(e["url"], w.SITE + A32)
        self.assertEqual(e["product"], "hot-rolled steel plates")
        # 다음 실행: 바뀐 것 없음 → 모음만 읽음, 이벤트 그대로
        get3, calls3 = fake(with32=True)
        doc3 = w.run(later + dt.timedelta(hours=2), doc2, get=get3, sleep=lambda s: None)
        self.assertEqual(calls3, [w.COLLECTION])
        self.assertEqual(len(doc3["events"]), 1)
        self.assertFalse(next(n for n in doc3["notices"] if n["number"] == "2026/32")["isNew"])

    def test_attachment_budget_carries_over(self):
        get, _ = fake()
        doc = w.run(NOW, None, get=get, sleep=lambda s: None)
        old = w.ATT_BUDGET
        try:
            w.ATT_BUDGET = 0
            get2, _ = fake(with32=True)
            doc2 = w.run(NOW + dt.timedelta(hours=2), doc, get=get2, sleep=lambda s: None)
            self.assertEqual(doc2["events"], [])
            self.assertNotEqual(doc2["pubs"][HR], "2026-11-18T13:00:04Z")       # 다 못 읽은 게시물은 갱신 시각을 저장하지 않는다
        finally:
            w.ATT_BUDGET = old
        get3, _ = fake(with32=True)
        doc3 = w.run(NOW + dt.timedelta(hours=4), doc2, get=get3, sleep=lambda s: None)
        self.assertEqual([e["number"] for e in doc3["events"]], ["2026/32"])

    def test_collection_failure_keeps_previous_and_is_unconfirmed(self):
        get, _ = fake()
        doc = w.run(NOW, None, get=get, sleep=lambda s: None)
        get2, _ = fake(fail=("collections",))
        doc2 = w.run(NOW + dt.timedelta(hours=2), doc, get=get2, sleep=lambda s: None)
        self.assertEqual((doc2["status"], doc2["checks"][0]["status"]), ("failed", "failed"))
        self.assertEqual(len(doc2["notices"]), 3)
        self.assertTrue(doc2["stale"])
        doc3 = w.run(NOW, None, get=get2, sleep=lambda s: None)
        self.assertEqual((doc3["status"], doc3["notices"]), ("failed", []))

    def test_notice_body_failure_is_partial_and_retried(self):
        get, _ = fake()
        doc = w.run(NOW, None, get=get, sleep=lambda s: None)
        get2, _ = fake(with32=True, fail=("202632",))
        doc2 = w.run(NOW + dt.timedelta(hours=2), doc, get=get2, sleep=lambda s: None)
        self.assertEqual(doc2["status"], "partial")
        self.assertEqual(doc2["events"], [])
        get3, _ = fake(with32=True)
        self.assertEqual([e["number"] for e in w.run(NOW + dt.timedelta(hours=4), doc2, get=get3, sleep=lambda s: None)["events"]], ["2026/32"])

    def test_kind_and_product_parsing(self):
        self.assertEqual(w.kind_of("Trade remedies notice 2025/16: registration of imports of hot-rolled steel plates"), ("수입 등록", "B"))
        self.assertEqual(w.kind_of("Trade remedies notice 2024/30: anti-dumping duty on steel ropes and cables"), ("고시", "B"))
        self.assertEqual(w.product_of("Trade remedies notices: anti-dumping duty on steel ropes and cables from China, Morocco and the Republic of South Korea"),
                         "steel ropes and cables")
        self.assertEqual(w.product_of("Trade remedies notices: S-PVC from China, Mexico and South Korea"), "S-PVC")


if __name__ == "__main__":
    unittest.main()
