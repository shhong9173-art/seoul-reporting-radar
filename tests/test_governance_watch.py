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
        self.assertIn("[사유: 처분]", young["tags"])
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

    def test_same_day_insider_reports_become_one_group_and_small_moves_are_routine(self):
        rows = [{"rcept_no": f"2026102300{i:04d}", "rcept_dt": "20261023", "repror": f"임원{i}",
                 "isu_exctv_rgist_at": "비등기임원", "isu_exctv_ofcps": "상무보", "isu_main_shrholdr": "-",
                 "sp_stock_lmp_cnt": "5,450", "sp_stock_lmp_irds_cnt": "5,000", "sp_stock_lmp_rate": "0.01",
                 "sp_stock_lmp_irds_rate": "0.01"} for i in range(6)]
        rows.append({"rcept_no": "20261023009999", "rcept_dt": "20261023", "repror": "회장님", "isu_exctv_rgist_at": "비등기임원",
                     "isu_exctv_ofcps": "회장", "isu_main_shrholdr": "-", "sp_stock_lmp_cnt": "250,450",
                     "sp_stock_lmp_irds_cnt": "50,000", "sp_stock_lmp_rate": "0.25", "sp_stock_lmp_irds_rate": "0.05"})
        rows.append({"rcept_no": "20261006000001", "rcept_dt": "20261006", "repror": "국민연금공단", "isu_exctv_rgist_at": "-",
                     "isu_exctv_ofcps": "-", "isu_main_shrholdr": "10%이상주주", "sp_stock_lmp_cnt": "4,195,210",
                     "sp_stock_lmp_irds_cnt": "271,655", "sp_stock_lmp_rate": "13.0", "sp_stock_lmp_irds_rate": "0.87"})
        rows.append({"rcept_no": "20261002000002", "rcept_dt": "20261002", "repror": "모회사", "isu_exctv_rgist_at": "-",
                     "isu_exctv_ofcps": "-", "isu_main_shrholdr": "10%이상주주", "sp_stock_lmp_cnt": "12,756,533",
                     "sp_stock_lmp_irds_cnt": "-1,623", "sp_stock_lmp_rate": "35.4", "sp_stock_lmp_irds_rate": "-0.00"})
        r = self.build({("elestock.json", "00145880"): {"status": "000", "list": rows}})
        group = [x for x in r["items"] if x["kind"] == "임원 집단 보고"]
        self.assertEqual(len(group), 1)
        self.assertEqual(group[0]["reporter"], "임원·주요주주 7명")
        self.assertEqual(group[0]["sharesChange"], 80000)
        self.assertFalse(group[0]["routine"])
        self.assertEqual(len(group[0]["members"]), 7)
        by = {x["reporter"]: x for x in r["items"]}
        self.assertTrue(by["임원0"]["routine"])  # kept, behind the group line
        self.assertIn("[최고경영진]", by["회장님"]["tags"])
        self.assertTrue(by["국민연금공단"]["routine"])  # institution below 1%p
        self.assertTrue(by["모회사"]["routine"])  # rounds to 0.00%p
        flagged = [x["reporter"] for x in r["items"] if not x["routine"]]
        self.assertEqual(set(flagged), {"임원·주요주주 7명", "회장님"})

    def test_institution_stake_reports_flag_only_control_reasons(self):
        rows = [
            {"rcept_no": "20261002000010", "rcept_dt": "2026-10-02", "repror": "국민연금공단", "report_tp": "일반",
             "stkrt": "8.1", "stkrt_irds": "1.05", "report_resn": "단순추가취득/처분"},
            {"rcept_no": "20261002000011", "rcept_dt": "2026-10-02", "repror": "국민연금공단", "report_tp": "일반",
             "stkrt": "9.1", "stkrt_irds": "0.10", "report_resn": "보유목적 변경(단순투자→일반투자)"},
            {"rcept_no": "20261001000012", "rcept_dt": "2026-10-01", "repror": "두산", "report_tp": "일반",
             "stkrt": "30.4", "stkrt_irds": "0.00", "report_resn": "- 보유주식수 변동\n- 계약 내용의 변경"},
            {"rcept_no": "20261002000013", "rcept_dt": "2026-10-02", "repror": "기아", "report_tp": "일반",
             "stkrt": "19.4", "stkrt_irds": "0.00", "report_resn": "장내매수"},
        ]
        r = self.build({("majorstock.json", "00145880"): {"status": "000", "list": rows}})
        by = {x["receiptNo"]: x for x in r["items"]}
        self.assertTrue(by["20261002000010"]["routine"])
        self.assertEqual(by["20261002000010"]["tags"], [])
        self.assertFalse(by["20261002000011"]["routine"])
        self.assertIn("[사유: 계약]", by["20261001000012"]["tags"])
        self.assertNotIn("\n", by["20261001000012"]["reason"])
        self.assertIn("[사유: 보유목적]", by["20261002000011"]["tags"])
        self.assertEqual(by["20261002000013"]["tags"], [])
        self.assertFalse(by["20261002000013"]["routine"])  # controlling-group move stays visible

    def test_beat_name_tries_exact_dart_spelling_only(self):
        codes, missing = g.resolve_codes(["동성케미칼"], {"companies": {}}, {"동성케미컬": [["00999999", "102260"]]})
        self.assertEqual(codes["동성케미칼"], "00999999")
        self.assertEqual(codes["_spellings"], {"동성케미칼": "동성케미컬"})
        codes, missing = g.resolve_codes(["동성케미칼"], {"companies": {}}, {"동성케미칼홀딩스": [["1", "2"]]})
        self.assertEqual(missing, ["동성케미칼"])

    def test_numbers_and_dates_parse_safely(self):
        self.assertEqual(g.num("1,234"), 1234)
        self.assertEqual(g.num("－0.50"), -0.5)
        self.assertIsNone(g.num("-"))
        self.assertEqual(g.day("20261022"), "2026-10-22")
        self.assertEqual(g.day("2026.10.22"), "2026-10-22")
        self.assertIsNone(g.day("미상"))


# 11-04 탐침 162 실제 응답(OpenDART tsstkDpDecsn)
KG_TREASURY = {"status": "000", "list": [{"rcept_no": "20261015000414", "corp_cls": "Y", "corp_code": "00115676", "corp_name": "KG스틸",
    "aq_wtn_div_ostk": "2,456,184", "eaq_ostk": "5,807", "eaq_estk": "678", "dppln_stk_ostk": "2,461,991", "dppln_stk_estk": "-",
    "dppln_prc_ostk": "13,688,669,960", "dppln_prc_estk": "-", "dpprpd_bgd": "2026년 10월 16일", "dpprpd_edd": "2027년 01월 15일",
    "dp_pp": "임직원 지급을 위한\n자기주식 처분", "dp_m_mkt": "-", "dp_m_ovtm": "-", "dp_m_otc": "-", "dp_m_etc": "2,461,991", "dp_dd": "2026년 10월 15일"}]}
HMC_TREASURY_ROW = {"rcept_no": "20260326001343", "corp_code": "00164742", "corp_name": "현대자동차", "aq_wtn_div_ostk": "2,006,508",
    "eaq_ostk": "-", "dppln_stk_ostk": "50,458", "dppln_prc_ostk": "25,279,458,000", "dpprpd_bgd": "2026년 04월 01일",
    "dpprpd_edd": "2026년 04월 01일", "dp_pp": "임원 대상 자기주식 지급", "dp_m_otc": "50,458", "dp_dd": "2026년 03월 26일"}


class Treasury(unittest.TestCase):
    def test_kg_steel_disposal_is_flagged_hyundai_annual_grant_is_routine(self):
        kg = g.treasury_item("KG스틸", "철강·비철", KG_TREASURY["list"][0], "2026-10-01")
        self.assertEqual((kg["date"], kg["routine"], kg["shares"], kg["amount"]), ("2026-10-15", False, 2461991, 13688669960))
        self.assertEqual(kg["tags"], ["[처분목적: 임직원 보상]", "[보유 자사주의 100%]"])
        self.assertIn('처분목적 "임직원 지급을 위한 자기주식 처분" · 2,461,991주·136.9억원 · 처분 전 보유 2,461,991주의 100% · 방법 기타', kg["reason"])
        hmc = g.treasury_item("현대자동차", "자동차", HMC_TREASURY_ROW, "2026-03-01")
        self.assertEqual((hmc["routine"], hmc["tags"]), (True, ["[처분목적: 임직원 보상]"]))   # 보유분의 2.5% — 해마다 하는 임원 지급
        # 11-04 첫 화면: 임단협 주식 지급(기아 보유분 100%)은 해마다 임단협 결과와 함께 보도 — 일상
        kia = g.treasury_item("기아", "자동차", {"rcept_no": "20261030000550", "dp_pp": "2026년 임금협상 결과에 따른 회사주식 지급",
                                               "aq_wtn_div_ostk": "1,756,955", "dppln_stk_ostk": "1,754,496", "dppln_prc_ostk": "190,010,000,000"}, "2026-10-01")
        self.assertEqual((kia["routine"], kia["tags"]), (True, ["[처분목적: 임단협 주식 지급]", "[보유 자사주의 100%]"]))

    def test_insider_group_after_disposal_is_linked(self):
        g.BEATS[:] = [("철강·비철", ["KG스틸"])]
        rows = [{"rcept_no": f"202610230003{i:02d}", "rcept_dt": "20261023", "repror": f"임원{i}", "isu_exctv_rgist_at": "비등기임원",
                 "isu_exctv_ofcps": "상무보", "sp_stock_lmp_cnt": "5,450", "sp_stock_lmp_irds_cnt": "5,000",
                 "sp_stock_lmp_rate": "0.01", "sp_stock_lmp_irds_rate": "0.01"} for i in range(15)]
        try:
            r = g.build("K", now=datetime(2026, 10, 26, 9, 0, tzinfo=KST), days=30, sleep=lambda s: None,
                        registry={"companies": {"KG스틸": {"corp_code": "00115676"}}},
                        get=fake({("elestock.json", "00115676"): {"status": "000", "list": rows}, ("tsstkDpDecsn.json", "00115676"): KG_TREASURY}))
        finally:
            import importlib
            importlib.reload(g)
        grp = next(x for x in r["items"] if x["kind"] == "임원 집단 보고")
        self.assertIn("[자사주 처분 연결]", grp["tags"])
        self.assertIn('10-15 자기주식 처분 결정(처분목적 "임직원 지급을 위한 자기주식 처분", 2,461,991주) 뒤 — 주식 보상 지급으로 보임', grp["reason"])
        self.assertEqual(r["schema"], "governance/v1")
        self.assertTrue(any(x["kind"] == "자사주 처분 결정" and not x["routine"] for x in r["items"]))
        self.assertIn({"company": "KG스틸", "endpoint": "tsstkDpDecsn.json", "status": "checked", "rowsReturned": 1, "rowsInWindow": 1}, r["checks"])

if __name__ == "__main__":
    unittest.main()
