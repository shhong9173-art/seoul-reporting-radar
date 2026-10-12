import json
import os
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import peer_financial as pf

CORP="00164742"
RECEIPT="20260310000123"


def item(metric,now="150",prev="100",older="70",**kw):
    account={"revenue":"ifrs-full_Revenue","operatingIncome":"dart_OperatingIncomeLoss"}[metric]
    return {"corp_code":CORP,"bsns_year":"2025","reprt_code":"11011",
            "sj_div":"IS","account_detail":"-","account_id":account,
            "currency":"KRW","rcept_no":RECEIPT,
            "thstrm_amount":now,"frmtrm_amount":prev,
            "bfefrmtrm_amount":older,**kw}


class FinancialResearchTests(unittest.TestCase):
    def test_annual_three_years_exact_standard_codes(self):
        got=pf.extract_period({"status":"000","list":[item("revenue"),item("operatingIncome",now="20",prev="10",older="5")]},
                              "현대자동차",CORP,2025,"11011",pf.PERIODS[0])
        self.assertEqual(got["metrics"]["revenue"],{"2025":"150","2024":"100","2023":"70"})
        self.assertEqual(got["metrics"]["operatingIncome"]["2024"],"10")
        self.assertEqual(got["scope"],"CFS")
        self.assertEqual(len(got["sources"]),1)

    def test_no_zero_for_missing_period_or_invalid_number(self):
        rows=[item("revenue",prev="",older="broken")]
        out=pf.extract_period({"status":"000","list":rows},"현대자동차",CORP,2025,"11011",pf.PERIODS[0])
        self.assertNotIn("2024",out["metrics"]["revenue"])
        self.assertNotIn("2023",out["metrics"]["revenue"])

    def test_different_issuer_and_report_never_joined(self):
        row=item("revenue")
        row["corp_code"]="99999999"
        result=pf.extract_period({"status":"000","list":[row]},"현대자동차",CORP,2025,"11011",pf.PERIODS[0])
        self.assertEqual(result["metrics"],{})
        self.assertEqual(result["status"],"no_comparable_accounts")

    def test_non_krw_or_wrong_statement_ignored(self):
        x=item("revenue")
        x["currency"]="USD"
        y=item("operatingIncome")
        y["sj_div"]="CF"
        result=pf.extract_period({"status":"000","list":[x,y]},"현대자동차",CORP,2025,"11011",pf.PERIODS[0])
        self.assertEqual(result["metrics"],{})

    def test_conflicting_account_duplicates_rejected(self):
        result=pf.extract_period({"status":"000","list":[item("revenue"),item("revenue",now="160")]},
                                 "현대자동차",CORP,2025,"11011",pf.PERIODS[0])
        self.assertNotIn("2025",result["metrics"]["revenue"])

    def test_two_company_growth_cannot_imply_sector_average(self):
        companies=[]
        for n in ["현대자동차","기아"]:
            companies.append({"name":n,"status":"extracted","sources":[],
                              "metrics":{"revenue":{"2024":"100","2025":"150"}}})
        self.assertEqual(pf.evaluate_group("자동차 완성차",companies,"annual",2025),[])

    def test_three_company_gap_yields_reporting_question_not_exclusive(self):
        companies=[]
        for n,after in (("현대모비스",170),("현대위아",115),("HL만도",108)):
            companies.append({"name":n,"status":"extracted","sources":[{"url":"https://example.org"}],
                              "metrics":{"revenue":{"2023":"100","2024":"110","2025":str(after)}}})
        found=pf.evaluate_group("자동차 부품",companies,"annual",2025)
        self.assertEqual(len(found),1)
        self.assertEqual(found[0]["company"],"현대모비스")
        self.assertIn("단독 미확정",found[0]["status"])
        self.assertIn("연결범위",found[0]["questions"][1])

    def test_denominator_zero_is_not_growth(self):
        self.assertIsNone(pf.ratio(Decimal("25"),Decimal("0")))
        self.assertIsNone(pf.margin(Decimal("1"),Decimal("0")))

    def test_no_api_key_or_bad_status_do_not_make_zero(self):
        with self.assertRaises(ValueError):
            pf.fetch_statement("",CORP,2025,"11011")
        with self.assertRaises(RuntimeError):
            pf.fetch_statement("test",CORP,2025,"11011",
                               get=lambda u:{"status":"800","message":"system maintenance"})

    def test_interim_uses_cumulative_amount_not_quarterly(self):
        row=item("revenue")
        row["bsns_year"]="2026";row["reprt_code"]="11012"
        row["thstrm_add_amount"]="350";row["frmtrm_add_amount"]="250"
        result=pf.extract_period({"status":"000","list":[row]},"현대자동차",CORP,2026,"11012",pf.PERIODS[1])
        self.assertEqual(result["metrics"]["revenue"],{"2026":"350","2025":"250"})

    def test_unmatched_corp_whitelist_not_silently_expanded(self):
        self.assertNotIn("삼성전기",sum((list(v) for v in pf.GROUPS.values()),[]))
        self.assertNotIn("포스코퓨처엠",sum((list(v) for v in pf.GROUPS.values()),[]))

    def test_no_filing_return_stays_no_report(self):
        result=pf.extract_period({"status":"no_report","list":[]},"기아","00106641",2025,"11011",pf.PERIODS[0])
        self.assertEqual(result["status"],"no_report")
        self.assertEqual(result["sources"],[])

    def test_analyze_does_not_claim_first_or_exclusive(self):
        r=pf.analyze([])
        self.assertEqual(r["status"],"research_only_not_exclusives")
        self.assertNotIn("사상 처음",r["method"])
        self.assertEqual(r["findings"],[])


if __name__=="__main__":
    unittest.main()
