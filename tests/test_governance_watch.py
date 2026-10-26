"""Stake/insider filings: window, routine flag, failures never become 0건."""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import governance_watch as g  # noqa: E402

KST = timezone(timedelta(hours=9))
NOW = datetime(2026, 10, 26, 9, 0, tzinfo=KST)
REGISTRY = {"companies": {"고려아연": {"corp_code": "00102858"}, "영풍": {"corp_code": "00141307"},
                          "현대제철": {"corp_code": "00145880"}}}


class R:
    def __init__(self, body, code=200):
        self.body, self.status_code = body, code

    def raise_for_status(self):
        pass

    def json(self):
        return self.body


def fake(responses):
    calls = []

    def get(url, params, timeout):
        calls.append((url.rsplit("/", 1)[1], params["corp_code"]))
        value = responses.get((url.rsplit("/", 1)[1], params["corp_code"]), {"status": "013", "message": "없음"})
        if isinstance(value, Exception):
            raise value
        return value if isinstance(value, R) else R(value)
    get.calls = calls
    return get


ZINC_MAJOR = {"status": "000", "list": [
    {"rcept_no": "20261020000111", "rcept_dt": "2026-10-20", "repror": "영풍", "report_tp": "일반",
     "stkqy": "5,000,000", "stkqy_irds": "-300,000", "stkrt": "24.10", "stkrt_irds": "-1.45", "report_resn": "보유주식 처분"},
    {"rcept_no": "20261015000222", "rcept_dt": "2026-10-15", "repror": "국민연금공단", "report_tp": "약식",
     "stkqy": "1,000,000", "stkqy_irds": "10,000", "stkrt": "6.10", "stkrt_irds": "0.05", "report_resn": "단순투자"},
    {"rcept_no": "20260801000333", "rcept_dt": "2026-08-01", "repror": "오래된 보고", "report_tp": "일반",
     "stkrt": "5.0", "stkrt_irds": "5.0", "report_resn": "신규"},
]}
ZINC_INSIDER = {"status": "000", "list": [
    {"rcept_no": "20261022000444", "rcept_dt": "20261022", "repror": "홍길동", "isu_exctv_rgist_at": "등기임원",
     "isu_exctv_ofcps": "부회장", "isu_main_shrholdr": "-", "sp_stock_lmp_cnt": "120,000",
     "sp_stock_lmp_irds_cnt": "20,000", "sp_stock_lmp_rate": "0.58", "sp_stock_lmp_irds_rate": "0.10"},
]}


class Governance(unittest.TestCase):
    def build(self, responses, **kw):
        g.BEATS[:] = [("철강·비철", ["고려아연", "영풍", "현대제철"]), ("화학·소재", ["태광"])]
        return g.build("SECRETKEY", now=NOW, days=30, get=fake(responses), sleep=lambda s: None,
                       registry=REGISTRY, **kw)

    def tearDown(self):
        import importlib
        importlib.reload(g)

    def test_window_tags_and_routine_order(self):
        r = self.build({("majorstock.json", "00102858"): ZINC_MAJOR, ("elestock.json", "00102858"): ZINC_INSIDER})
        receipts = [x["receiptNo"] for x in r["items"]]
        self.assertNotIn("20260801000333", receipts)  # outside 30-day window
        first = r["items"][0]
        self.assertFalse(first["routine"])
        pension = next(x for x in r["items"] if x["reporter"] == "국민연금공단")
        self.assertTrue(pension["routine"])
        self.assertEqual(r["items"][-1]["reporter"], "국민연금공단")
        young = next(x for x in r["items"] if x["reporter"] == "영풍")
        self.assertIn("[지분율 -1.45%p]", young["tags"])
        self.assertEqual(young["sharesChange"], -300000)
        insider = next(x for x in r["items"] if x["kind"] == "임원·주요주주")
        self.assertEqual(insider["date"], "2026-10-22")
        self.assertIn("부회장", insider["role"])
        self.assertEqual(r["confirmedScoops"], 0)

    def test_failures_and_unresolved_are_not_zero(self):
        r = self.build({("majorstock.json", "00141307"): R({}, 503), ("elestock.json", "00141307"): R({}, 503)})
        failed = [c for c in r["checks"] if c["status"] == "failed"]
        self.assertEqual({c["company"] for c in failed}, {"영풍"})
        self.assertEqual(r["status"], "partial")
        self.assertIn("태광", r["unresolvedCompanies"])
        self.assertTrue(all("SECRETKEY" not in c.get("error", "") for c in failed))
        no_data = [c for c in r["checks"] if c["status"] == "no_data"]
        self.assertTrue(no_data)

    def test_corp_code_table_resolves_exact_unique_names_only(self):
        codes, missing = g.resolve_codes(["태광", "동성케미칼"], {"companies": {}},
                                         {"태광": [["00123456", "023160"]], "동성케미칼": [["1", ""], ["2", ""]]})
        self.assertEqual(codes, {"태광": "00123456"})
        self.assertEqual(missing, ["동성케미칼"])

    def test_numbers_and_dates_parse_safely(self):
        self.assertEqual(g.num("1,234"), 1234)
        self.assertEqual(g.num("－0.50"), -0.5)
        self.assertIsNone(g.num("-"))
        self.assertEqual(g.day("20261022"), "2026-10-22")
        self.assertEqual(g.day("2026.10.22"), "2026-10-22")
        self.assertIsNone(g.day("미상"))


if __name__ == "__main__":
    unittest.main()
