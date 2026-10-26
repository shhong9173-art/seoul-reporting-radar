"""Disclosure-season comparison: same-period prior year only, no ratios without the account, failures are not zero."""
import datetime as dt
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import earnings_compare as ec  # noqa: E402
import governance_watch as gw  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))


def row(aid, name, now, now_add, prior_q, prior_add, sj="IS", detail="-"):
    return {"rcept_no": "20261113000555", "sj_div": sj, "account_id": aid, "account_nm": name, "account_detail": detail,
            "currency": "KRW", "thstrm_amount": now, "thstrm_add_amount": now_add,
            "frmtrm_q_amount": prior_q, "frmtrm_add_amount": prior_add}


STEEL_Q3 = {"status": "000", "list": [
    row("ifrs-full_Revenue", "매출액", "5,000", "15,500", "5,200", "16,000"),
    row("ifrs-full_CostOfSales", "매출원가", "4,600", "14,000", "4,600", "14,500"),
    row("dart_TotalSellingGeneralAdministrativeExpenses", "판매비와관리비", "300", "900", "250", "800"),
    row("dart_OperatingIncomeLoss", "영업이익", "100", "600", "350", "700"),
    row("ifrs-full_Revenue", "매출액", "5,000", "15,500", "5,200", "16,000", sj="CIS"),
    row("ifrs-full_CostOfSales", "매출원가", "999", "999", "999", "999", detail="철강부문"),  # segment detail ignored
]}
HOLDING_Q3 = {"status": "000", "list": [
    row("ifrs-full_Revenue", "영업수익", "800", "2,400", "700", "2,100"),
    row("", "영업비용", "500", "1,500", "450", "1,350"),
    row("dart_OperatingIncomeLoss", "영업이익", "300", "900", "250", "750"),
]}
EMP = {"status": "000", "list": [
    {"fo_bbm": "철강", "sexdstn": "남", "sm": "9,000", "stlm_dt": "2026.09.30"},
    {"fo_bbm": "철강", "sexdstn": "여", "sm": "500", "stlm_dt": "2026.09.30"},
    {"fo_bbm": "합계", "sexdstn": "남", "sm": "9,000", "stlm_dt": "2026.09.30"},
    {"fo_bbm": "합계", "sexdstn": "여", "sm": "500", "stlm_dt": "2026.09.30"},
]}
EMP_PRIOR = {"status": "000", "list": [
    {"fo_bbm": "철강", "sexdstn": "남", "sm": "8,600"}, {"fo_bbm": "철강", "sexdstn": "여", "sm": "400"}]}


class R:
    def __init__(self, body, code=200):
        self.body, self.status_code = body, code

    def raise_for_status(self):
        pass

    def json(self):
        return self.body


def fake(routes):
    calls = []

    def get(url, params, headers, timeout):
        endpoint = url.rsplit("/", 1)[1]
        calls.append((endpoint, dict(params)))
        key = (endpoint, params["corp_code"], params.get("fs_div"), params.get("bsns_year"))
        for k in (key, key[:3] + (None,), key[:2] + (None, None)):
            if k in routes:
                v = routes[k]
                return v if isinstance(v, R) else R(v)
        return R({"status": "013", "message": "없음"})
    get.calls = calls
    return get


class Earnings(unittest.TestCase):
    def test_target_period_follows_the_filing_season(self):
        self.assertEqual(ec.target_period(dt.datetime(2026, 10, 26, tzinfo=KST)), (2026, "11014"))
        self.assertEqual(ec.target_period(dt.datetime(2027, 3, 2, tzinfo=KST)), (2026, "11011"))
        self.assertEqual(ec.target_period(dt.datetime(2027, 5, 20, tzinfo=KST)), (2027, "11013"))
        self.assertEqual(ec.target_period(dt.datetime(2027, 8, 20, tzinfo=KST)), (2027, "11012"))

    def test_quarter_and_cumulative_ratios_against_the_same_period_last_year(self):
        fin, receipts = ec.financials(STEEL_Q3, "11014")
        q = fin["quarter"]
        self.assertEqual(q["ratios"], {"costRatio": 92.0, "sgaRatio": 6.0, "opMargin": 2.0})
        self.assertEqual(q["priorRatios"]["costRatio"], 88.46)
        self.assertEqual(q["deltaPp"]["costRatio"], 3.54)
        self.assertEqual(q["deltaPp"]["opMargin"], -4.73)
        self.assertEqual(fin["cumulative"]["values"]["revenue"], 15500)
        self.assertEqual(receipts, ["20261113000555"])
        self.assertNotIn("warning", fin)

    def test_no_cost_of_sales_means_no_cost_ratio(self):
        fin, _ = ec.financials(HOLDING_Q3, "11014")
        self.assertNotIn("costRatio", fin["quarter"]["ratios"])
        self.assertEqual(fin["quarter"]["ratios"]["opMargin"], 37.5)

    def test_conflicting_values_make_the_metric_unknown(self):
        body = {"status": "000", "list": STEEL_Q3["list"] + [row("ifrs-full_CostOfSales", "매출원가", "4,700", "1", "1", "1")]}
        fin, _ = ec.financials(body, "11014")
        self.assertNotIn("costRatio", fin["quarter"]["ratios"])

    def test_headcount_uses_total_rows_without_double_counting(self):
        self.assertEqual(ec.headcount(EMP), (9500, "2026.09.30"))
        self.assertEqual(ec.headcount(EMP_PRIOR), (9000, None))
        self.assertEqual(ec.headcount({"list": [{"fo_bbm": "합계", "sexdstn": "합계", "sm": "100"},
                                                {"fo_bbm": "합계", "sexdstn": "남", "sm": "60"}]}), (100, None))
        self.assertEqual(ec.headcount({"list": [{"fo_bbm": "A", "sexdstn": "남", "sm": "-"}]}), (None, None))

    def test_subtotal_rows_are_never_added_to_details(self):
        body = {"list": [{"fo_bbm": "철강", "sexdstn": "남", "sm": "600"}, {"fo_bbm": "철강", "sexdstn": "여", "sm": "100"},
                         {"fo_bbm": "철강 소계", "sexdstn": "", "sm": "700"}, {"fo_bbm": "기타", "sexdstn": "남", "sm": "50"}]}
        total, _, how = ec.headcount(body, explain=True)
        self.assertEqual(total, 750)
        self.assertEqual(how["method"], "세부 행 합산")
        body = {"list": [{"fo_bbm": "철강", "sexdstn": "합계", "sm": "700"}, {"fo_bbm": "기타", "sexdstn": "합계", "sm": "50"},
                         {"fo_bbm": "철강", "sexdstn": "남", "sm": "600"}]}
        self.assertEqual(ec.headcount(body), (750, None))

    def test_third_quarter_without_headcount_falls_back_to_half_year(self):
        gw_beats = gw.BEATS[:]
        gw.BEATS[:] = [("철강·비철", ["현대제철"])]
        try:
            get = fake({("fnlttSinglAcntAll.json", "00145880", "CFS", None): STEEL_Q3,
                        ("empSttus.json", "00145880", None, "2026"): R({"status": "013"}),
                        })
            calls = []
            def routed(url, params, headers, timeout):
                calls.append((params.get("bsns_year"), params.get("reprt_code")))
                if url.endswith("empSttus.json") and params.get("reprt_code") == "11012":
                    return R(EMP if params["bsns_year"] == "2026" else EMP_PRIOR)
                return get(url, params, headers, timeout)
            r = ec.build("K", year=2026, report="11014", get=routed, sleep=lambda s: None,
                         registry={"companies": {"현대제철": {"corp_code": "00145880"}}})
        finally:
            gw.BEATS[:] = gw_beats
        e = r["companies"][0]["employees"]
        self.assertEqual((e["count"], e["priorCount"], e["changePct"]), (9500, 9000, 5.6))
        self.assertEqual(e["report"], "2026년 반기")
        self.assertIn("3분기 보고서에 직원 현황이 없어", e["note"])
        self.assertIn(("2026", "11014"), calls)

    def test_split_selling_and_admin_lines_add_up_and_a_lone_line_stays_unknown(self):
        body = {"status": "000", "list": [r for r in STEEL_Q3["list"] if r["account_nm"] != "판매비와관리비"] + [
            row("", "판매비", "100", "300", "90", "270"), row("", "관리비", "200", "600", "160", "530")]}
        fin, _ = ec.financials(body, "11014")
        self.assertEqual(fin["quarter"]["values"]["sga"], 300)
        self.assertEqual(fin["quarter"]["prior"]["sga"], 250)
        self.assertEqual(fin["cumulative"]["values"]["sga"], 900)
        self.assertIn("판매비+관리비", fin["derived"]["sga"])
        self.assertNotIn("unmatched", fin)
        only_sell = {"status": "000", "list": [r for r in body["list"] if r["account_nm"] != "관리비"]}
        fin, _ = ec.financials(only_sell, "11014")
        self.assertNotIn("sgaRatio", fin["quarter"]["ratios"])
        self.assertEqual(fin["unmatched"]["metrics"], ["sga"])
        self.assertIn("판매비", fin["unmatched"]["accountNames"])

    def test_build_marks_filed_not_filed_failed_and_flags(self):
        gw_beats = gw.BEATS[:]
        gw.BEATS[:] = [("철강·비철", ["현대제철", "고려아연", "영풍"]), ("전력·에너지", ["LS"])]
        try:
            registry = {"companies": {"현대제철": {"corp_code": "00145880"}, "고려아연": {"corp_code": "00102858"},
                                      "영풍": {"corp_code": "00141307"}, "LS": {"corp_code": "00105952"}}}
            get = fake({
                ("fnlttSinglAcntAll.json", "00145880", "CFS", None): STEEL_Q3,
                ("empSttus.json", "00145880", None, "2026"): EMP,
                ("empSttus.json", "00145880", None, "2025"): EMP_PRIOR,
                ("fnlttSinglAcntAll.json", "00141307", "CFS", None): R({}, 503),
                ("fnlttSinglAcntAll.json", "00105952", "OFS", None): HOLDING_Q3,
            })
            r = ec.build("SECRET", year=2026, report="11014", now=dt.datetime(2026, 11, 14, 18, 40, tzinfo=KST),
                         get=get, sleep=lambda s: None, registry=registry)
        finally:
            gw.BEATS[:] = gw_beats
        by = {c["company"]: c for c in r["companies"]}
        steel = by["현대제철"]
        self.assertEqual(steel["status"], "filed")
        self.assertEqual(steel["basis"], "연결")
        self.assertEqual(steel["filedOn"], "2026-11-13")
        self.assertEqual(steel["employees"]["count"], 9500)
        self.assertEqual(steel["employees"]["changePct"], 5.6)
        self.assertEqual(steel["tags"], ["[원가율 +3.5%p]", "[영업이익률 -4.7%p]", "[직원 +5.6%]"])
        self.assertEqual(by["고려아연"]["status"], "not_filed")
        self.assertEqual(by["영풍"]["status"], "failed")
        self.assertEqual(by["LS"]["basis"], "별도")
        self.assertEqual(r["counts"], {"filed": 2, "not_filed": 1, "failed": 1, "no_comparable_accounts": 0})
        self.assertEqual(r["status"], "partial")
        self.assertEqual(r["period"], {"year": 2026, "report": "11014", "label": "2026년 3분기", "deadline": "2026-11-14"})
        self.assertTrue(all(p.get("crtfc_key") == "SECRET" for _, p in get.calls))
        self.assertNotIn("SECRET", str(r))

    def test_annual_report_compares_with_the_prior_year(self):
        body = {"status": "000", "list": [
            {"rcept_no": "20270310000111", "sj_div": "IS", "account_id": "ifrs-full_Revenue", "account_nm": "매출액",
             "account_detail": "-", "currency": "KRW", "thstrm_amount": "100", "frmtrm_amount": "80"},
            {"rcept_no": "20270310000111", "sj_div": "IS", "account_id": "ifrs-full_CostOfSales", "account_nm": "매출원가",
             "account_detail": "-", "currency": "KRW", "thstrm_amount": "90", "frmtrm_amount": "60"}]}
        fin, _ = ec.financials(body, "11011")
        self.assertEqual(fin["annual"]["deltaPp"]["costRatio"], 15.0)
        self.assertNotIn("quarter", fin)


if __name__ == "__main__":
    unittest.main()
