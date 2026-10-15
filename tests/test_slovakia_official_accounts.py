"""RUZ state registry API coverage, entity identity, year provenance and cash safeguards."""
import sys
import unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from urllib.parse import urlparse,parse_qs
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import slovakia_official_accounts as a

NOW=datetime(2026,10,16,4,15,tzinfo=timezone(timedelta(hours=9)))
def api_data(url):
    parsed=urlparse(url)
    q=parse_qs(parsed.query)
    if parsed.path.endswith("/uctovne-jednotky"):
        assert q["ico"]==["35876832"]
        return {"id":[244945],"existujeDalsieId":False}
    if parsed.path.endswith("/uctovna-jednotka"):
        return {"id":244945,"ico":"35876832",
                "nazovUJ":"Kia Slovakia s. r. o.",
                "datumPoslednejUpravy":"2026-08-31",
                "idUctovnychZavierok":[1001,1002]}
    if parsed.path.endswith("/uctovna-zavierka"):
        number=int(q["id"][0])
        year=2024 if number==1001 else 2025
        return {"id":number,"idUJ":244945,
                "obdobieOd":f"{year}-01","obdobieDo":f"{year}-12",
                "konsolidovana":False,"typ":"Riadna",
                "datumPodania":f"{year+1}-06-29",
                "datumSchvalenia":f"{year+1}-05-18",
                "idUctovnychVykazov":[number+10000]}
    raise AssertionError("unexpected official URL "+url)

class SlovakOfficial(unittest.TestCase):
    def test_exact_kia_manufacturer_both_annual_filings_no_cash_or_profit(self):
        v=a.registry_evidence(api_data,now=NOW)
        self.assertTrue(v["companyIdentityVerified"])
        self.assertEqual(v["officialEntityId"],244945)
        self.assertEqual(v["ico"],"35876832")
        self.assertEqual(v["statementAvailabilityStatus"],
                         "registered_annual_filing_metadata_for_both_years")
        self.assertEqual([x["financialYear"] for x in v["statements"]],[2025,2024])
        self.assertTrue(all(x["profitOrDividendAmountsParsed"] is False
                            for x in v["statements"]))
        for flag in ("actualNetProfitVerified","approvedDistributionAmountVerified",
                     "dividendPaymentToKoreanParentVerified","parentCashReceiptVerified",
                     "auditedLocalStatementsReadInFull","exclusiveConfirmed"):
            self.assertIs(v[flag],False,flag)

    def test_missing_optional_consolidation_property_is_metadata_not_verified_standalone(self):
        def omitted(url):
            d=api_data(url)
            if "/uctovna-zavierka?" in url:
                d.pop("konsolidovana",None)
            return d
        report=a.registry_evidence(omitted,now=NOW)
        self.assertEqual(report["statementAvailabilityStatus"],
                         "registered_annual_filing_metadata_for_both_years")
        self.assertEqual([x["financialYear"] for x in report["statements"]],[2025,2024])
        self.assertEqual({x["consolidationFlag"] for x in report["statements"]},
                         {"not_specified_by_api"})
        self.assertFalse(report["auditedLocalStatementsReadInFull"])

    def test_kia_sales_slovakia_same_brand_wrong_ico_refused(self):
        def wrong(url):
            d=api_data(url)
            if "uctovna-jednotka?" in url:
                d={**d,"ico":"35942894","nazovUJ":"Kia Sales Slovakia s. r. o."}
            return d
        report=a.registry_evidence(wrong,now=NOW)
        self.assertFalse(report["companyIdentityVerified"])
        self.assertEqual(report["statements"],[])
        self.assertNotEqual(report["sourceQueriesFailed"],0)

    def test_ambiguous_registry_id_list_does_not_choose_company(self):
        def ambiguous(url):
            if "uctovne-jednotky?" in url:
                return {"id":[244945,12345],"existujeDalsieId":True}
            return api_data(url)
        report=a.registry_evidence(ambiguous,now=NOW)
        self.assertFalse(report["companyIdentityVerified"])
        self.assertEqual(report["statements"],[])

    def test_wrong_entity_statement_is_not_counted_as_2025_approved(self):
        def contaminated(url):
            o=api_data(url)
            if "/uctovna-zavierka?" in url:
                o={**o,"idUJ":102335}
            return o
        report=a.registry_evidence(contaminated,now=NOW)
        self.assertTrue(report["companyIdentityVerified"])
        self.assertEqual(report["statements"],[])
        self.assertEqual(report["statementAvailabilityStatus"],
                         "partial_official_statement_lookup_failed")

    def test_registry_failure_is_error_not_no_distributable_profit(self):
        def fail(url):
            raise TimeoutError("unavailable")
        report=a.registry_evidence(fail,now=NOW)
        self.assertFalse(report["companyIdentityVerified"])
        self.assertEqual(report["companyIdentityStatus"],
                         "official_source_error_or_exact_identity_unverified")
        self.assertIs(report["actualNetProfitVerified"],False)
        self.assertEqual(report["statements"],[])
        self.assertGreater(report["sourceQueriesFailed"],0)

    def test_2025_report_only_does_not_mean_2024_report_absent(self):
        def single(url):
            d=api_data(url)
            if "/uctovna-jednotka?" in url:
                d={**d,"idUctovnychZavierok":[1002]}
            return d
        result=a.registry_evidence(single,now=NOW)
        self.assertEqual(result["statementAvailabilityStatus"],
                         "one_or_more_years_not_identified_in_api")
        self.assertEqual([x["financialYear"] for x in result["statements"]],[2025])
        self.assertFalse(result["dividendPaymentToKoreanParentVerified"])

if __name__=="__main__":unittest.main()
