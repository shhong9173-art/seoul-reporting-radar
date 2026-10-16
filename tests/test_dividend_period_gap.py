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
    def test_wrong_named_entity_is_not_attached(self):
        x=fixture();x["officialFact"]["recognizedFromEntity"]="Kia Sales Slovakia"
        self.assertEqual(build_gap(x)["status"],"not_applicable_or_parent_income_not_verified")
if __name__=="__main__":unittest.main()
