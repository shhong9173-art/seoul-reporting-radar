"""Protect against equating pre-2026 Slovak cash flow and Kia 2026 dividend income."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from dividend_period_gap import build_gap

def fixture():
    return {"companyGroup":"기아","officialFact":{
        "recognizedFromEntity":"Kia Slovakia s.r.o.(KaSK)",
        "recognizedAmountInMillionKrw":1610458,"recognizedPeriodLabel":"current"
      },"slovakPdfPrimaryReview":{"auditedCalendarYearRows":[
        {"metric":"dividend_cash_outflow","year":y,"amountThousandEur":0,
         "annualReportComparativeConflict":False,"parentRecipientVerified":False,
         "koreanCashReceiptVerified":False,"amountFromKiaParentDart2026":False,
         "year2026LocalPaymentNotYetVerified":True,
         "humanAuditOfParsedRowCompleted":False} for y in (2024,2025)]}}

class TimingGate(unittest.TestCase):
    def test_original_periods_are_distinct_and_zero_is_not_2026_absence(self):
        result=build_gap(fixture())
        self.assertEqual(result["koreanIssuerIncomePeriod"],"2026_first_half")
        self.assertEqual(result["koreanIssuerRecognizedIncomeMillionKrw"],1610458)
        self.assertEqual([x["year"] for x in result["slovakAuditedPaymentCalendarYears"]],[2024,2025])
        self.assertFalse(result["canCalculateParentCashTransferFromTheseRows"])
        self.assertFalse(result["canClaimNoDividendIn2026"])
        self.assertFalse(result["koreanCashReceivedVerified"])
    def test_conflicting_or_nonofficial_amount_removed(self):
        x=fixture()
        x["slovakPdfPrimaryReview"]["auditedCalendarYearRows"][0]["annualReportComparativeConflict"]=True
        x["slovakPdfPrimaryReview"]["auditedCalendarYearRows"][1]["humanAuditOfParsedRowCompleted"]=True
        self.assertEqual(build_gap(x)["slovakAuditedPaymentCalendarYears"],[])
    def test_real_kia_slovakia_government_pdf_same_year_comparatives(self):
        import json
        doc=json.loads((Path(__file__).resolve().parents[1]/
            "digests/crossborder_source_gap_latest.json").read_text(encoding="utf-8"))
        ds=[x for x in doc.get("items",[])
            if x.get("type")=="foreign_subsidiary_dividend_accounting"
            and x.get("companyGroup")=="기아"]
        self.assertEqual(len(ds),1)
        result=build_gap(ds[0])
        profit=result["slovakLocalProfitYearOnYear"]
        self.assertIsNotNone(profit)
        self.assertEqual(profit["priorCalendarYear"],2024)
        self.assertEqual(profit["currentCalendarYear"],2025)
        self.assertEqual(profit["priorValueThousandEur"],682581)
        self.assertEqual(profit["currentValueThousandEur"],451021)
        self.assertEqual(profit["changeThousandEur"],-231560)
        self.assertEqual(profit["changePercent"],-33.9)
        self.assertEqual(profit["sourcePdfPage"],9)
        self.assertFalse(profit["sourceLineManuallyReviewed"])
        self.assertFalse(profit["exclusiveConfirmed"])
        self.assertFalse(profit["samePeriodAsKorean2026HalfYearDividendIncome"])
        self.assertFalse(profit["koreanParentCashReceiptVerified"])
        self.assertTrue(profit["sameOfficialGovernmentPdfUrl"].startswith(
            "https://www.registeruz.sk/cruz-public/domain/financialreport/attachment/"))

    def test_wrong_or_missing_government_document_cannot_forge_profit_delta(self):
        import copy, json
        doc=json.loads((Path(__file__).resolve().parents[1]/
            "digests/crossborder_source_gap_latest.json").read_text(encoding="utf-8"))
        base=next(x for x in doc["items"] if
             x.get("type")=="foreign_subsidiary_dividend_accounting")
        source=copy.deepcopy(base)
        profit_rows=source["slovakPdfPrimaryReview"]["auditedCalendarYearRows"]
        changed=next(r for r in profit_rows
                     if r["metric"]=="annual_profit_cf_reconciliation" and r["year"]==2025)
        changed["sourceDocuments"][0]["pdfUrl"]="https://evil.example/pdf.pdf"
        self.assertIsNone(build_gap(source)["slovakLocalProfitYearOnYear"])
        changed["sourceDocuments"][0]["pdfUrl"]=(
            "https://www.registeruz.sk/cruz-public/domain/financialreport/attachment/12784290")
        changed["sourceDocuments"][0]["documentSha256"]="not-verified"
        self.assertIsNone(build_gap(source)["slovakLocalProfitYearOnYear"])
        source=copy.deepcopy(base)
        changed=next(r for r in source["slovakPdfPrimaryReview"]["auditedCalendarYearRows"]
                     if r["metric"]=="annual_profit_cf_reconciliation" and r["year"]==2025)
        changed["annualReportComparativeConflict"]=True
        self.assertIsNone(build_gap(source)["slovakLocalProfitYearOnYear"])
        source=copy.deepcopy(base)
        source["officialFact"]["recognizedFromEntity"]="Kia Sales Slovakia"
        self.assertIsNone(build_gap(source)["slovakLocalProfitYearOnYear"])

    def test_public_financial_service_already_printed_same_profits(self):
        import copy,json
        root=Path(__file__).resolve().parents[1]
        source=json.loads((root/"digests/crossborder_source_gap_latest.json").read_text(encoding="utf-8"))
        prior=json.loads((root/"data/public_financial_metric_prior_checks.json").read_text(encoding="utf-8"))
        d=next(x for x in source["items"] if x.get("type")=="foreign_subsidiary_dividend_accounting")
        gap=build_gap(d,prior)
        info=gap["slovakProfitFinancialDataPriorPublic"]
        self.assertEqual(info["status"],"exact_2025_financial_metric_visible_on_public_service")
        self.assertEqual(info["localProfitEuro"],451021000)
        self.assertEqual(info["roundedAnnualChangePercent"],34)
        self.assertTrue(info["metricIsPublicNotExclusive"])
        self.assertFalse(info["sourceOriginalPublishingDateVerified"])
        self.assertFalse(info["koreanPressSameAngleFulltextChecked"])
        self.assertFalse(info["actual2026DividendDecisionOrRemittanceVerified"])
        self.assertFalse(gap["canCalculateParentCashTransferFromTheseRows"])

        cases=[
          {"url":"https://finstat.sk.evil.example/35876832"},
          {"publishedProfitEuro":450000000},
          {"ico":"35942894"},
          {"originalPagePublicationDateVerified":True},
          {"newExclusiveReportingFactConfirmed":True},
          {"publishedProfitDecreaseApproxPercent":33},
          {"observerCheckedDate":"not-a-date"},
        ]
        for change in cases:
            fake=copy.deepcopy(prior)
            fake["items"][0].update(change)
            self.assertIsNone(build_gap(d,fake)["slovakProfitFinancialDataPriorPublic"],change)

    def test_finstat_number_does_not_establish_2026_dividend_disbursement(self):
        import json
        root=Path(__file__).resolve().parents[1]
        source=json.loads((root/"digests/crossborder_source_gap_latest.json").read_text(encoding="utf-8"))
        prior=json.loads((root/"data/public_financial_metric_prior_checks.json").read_text(encoding="utf-8"))
        d=next(x for x in source["items"] if x.get("type")=="foreign_subsidiary_dividend_accounting")
        gap=build_gap(d,prior)
        self.assertEqual(gap["koreanIssuerIncomePeriod"],"2026_first_half")
        self.assertFalse(gap["koreanCashReceivedVerified"])
        self.assertFalse(gap["canClaimOverseasDividendIsExclusive"])
        self.assertTrue(gap["slovakProfitFinancialDataPriorPublic"]["metricIsPublicNotExclusive"])

    def test_wrong_named_entity_is_not_attached(self):
        x=fixture();x["officialFact"]["recognizedFromEntity"]="Kia Sales Slovakia"
        self.assertEqual(build_gap(x)["status"],"not_applicable_or_parent_income_not_verified")
if __name__=="__main__":unittest.main()
