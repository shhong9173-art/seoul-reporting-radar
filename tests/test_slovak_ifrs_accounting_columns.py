"""Column-aware 2023–25 Kia Slovakia audited IFRS provenance regression."""
import copy,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import slovak_ifrs_accounting_columns as m

def audited_pages(year):
    pages=[""]*41
    curr=year
    prev=year-1
    retained={
      2025:"2 117 131        1 666 110",
      2024:"1 666 110        983 529"}[year]
    profit={
      2025:"451 021        682 581",
      2024:"682 581        390 131"}[year]
    payout={
      2025:"0            0",
      2024:"0            -735 621"}[year]
    pages[6]=("Kia Slovakia s. r. o.\nVýkaz o finančnej situácii\n"
       f"k 31. decembru {curr}\nV tisícoch EUR\n"
       f"Pozn.    31. december {curr}       31. december {prev}\n"
       "Vlastné imanie\n"
       f"Nerozdelený zisk minulých období    {retained}\n")
    pages[7]="Kia Slovakia s.r.o.\nVýkaz zmien vo vlastnom imaní"
    pages[8]=("Kia Slovakia s. r. o.\nVýkaz peňažných tokov\n"
       f"za rok končiaci sa 31. decembrom {curr}\nV tisícoch EUR\n"
       f"Pozn.   31. december {curr}      31. december {prev}\n"
       f"Zisk za účtovné obdobie          {profit}\n"
       "Peňažné toky z finančnej činnosti\n"
       f"Splatenie dividend       4      {payout}\n"
       "Čisté peňažné toky použité vo finančnej činnosti\n")
    return pages

def synthetic_report(year):
    return {"year":year,
      "attachmentUrl":"https://www.registeruz.sk/cruz-public/domain/financialreport/attachment/"+
       str(12784290 if year==2025 else 11846820),
      "sha256":"c"*64 if year==2025 else "0"*64,
      "pdfReadAndOfficialHashVerified":True,
      "auditedStatementRows":m.audited_rows(audited_pages(year),year)}

class ParsedAuditedRows(unittest.TestCase):
    def test_actual_like_government_2024_2025_year_columns(self):
        rows25=m.audited_rows(audited_pages(2025),2025)
        rows24=m.audited_rows(audited_pages(2024),2024)
        self.assertEqual(rows25["dividend_cash_outflow"]["values"],[0,0])
        self.assertEqual(rows24["dividend_cash_outflow"]["values"],[0,-735621])
        self.assertEqual(rows25["retained_earnings_balance"]["values"],[2117131,1666110])
        self.assertEqual(rows24["retained_earnings_balance"]["values"],[1666110,983529])
        self.assertEqual(rows25["annual_profit_cf_reconciliation"]["values"],[451021,682581])
        self.assertEqual(rows24["annual_profit_cf_reconciliation"]["values"],[682581,390131])
        self.assertTrue(all(x["manualSourceTableReviewConfirmed"] is False
                            for x in rows24.values()))

    def test_one_calendar_year_not_double_counted_across_two_audited_reports(self):
        matrix=m.reconcile([synthetic_report(2024),synthetic_report(2025)])
        def find(metric,year):
            return next(x for x in matrix if x["metric"]==metric and x["calendarYear"]==year)
        self.assertEqual(find("dividend_cash_outflow",2023)["value"],-735621)
        self.assertEqual(find("dividend_cash_outflow",2024)["value"],0)
        self.assertEqual(find("dividend_cash_outflow",2025)["value"],0)
        self.assertEqual(find("dividend_cash_outflow",2024)["sourceDocumentCount"],2)
        self.assertEqual(find("retained_earnings_balance",2025)["value"],2117131)
        self.assertEqual(find("annual_profit_cf_reconciliation",2025)["value"],451021)
        self.assertTrue(all(x["samePeriodAs2026KiaDartDividendIncome"] is False for x in matrix))
        self.assertTrue(all(x["koreanParentCashReceiptVerified"] is False for x in matrix))

    def test_conflicting_comparative_2024_numbers_suppress_only_that_calendar_metric(self):
        past=synthetic_report(2024)
        latest=synthetic_report(2025)
        latest["auditedStatementRows"]["retained_earnings_balance"]["values"][1]=1666999
        matrix=m.reconcile([past,latest])
        x=next(q for q in matrix if q["metric"]=="retained_earnings_balance" and q["calendarYear"]==2024)
        self.assertIsNone(x["value"])
        self.assertTrue(x["annualValueWithheldBecauseContradiction"])
        y=next(q for q in matrix if q["metric"]=="dividend_cash_outflow" and q["calendarYear"]==2024)
        self.assertEqual(y["value"],0)

    def test_missing_heading_or_units_yields_no_amount_not_zero_payment(self):
        pages=audited_pages(2024)
        pages[8]=pages[8].replace("V tisícoch EUR","")
        rows=m.audited_rows(pages,2024)
        self.assertEqual(rows["dividend_cash_outflow"]["status"],"eur_thousands_unit_not_verified")
        self.assertFalse(any(x["metric"]=="dividend_cash_outflow" for x in
                             m.reconcile([{"year":2024,
                                           "pdfReadAndOfficialHashVerified":True,
                                           "auditedStatementRows":rows}])))

    def test_single_spaces_make_large_number_year_columns_ambiguous(self):
        pages=audited_pages(2025)
        pages[6]=pages[6].replace("2 117 131        1 666 110","2 117 131 1 666 110")
        rows=m.audited_rows(pages,2025)
        self.assertEqual(rows["retained_earnings_balance"]["status"],"row_missing_or_ambiguous")

    def test_two_matching_rows_are_not_assumed_identical(self):
        pages=audited_pages(2024)
        pages[8]+="\nSplatenie dividend       4      0          -735 621\n"
        rows=m.audited_rows(pages,2024)
        self.assertEqual(rows["dividend_cash_outflow"]["matchingRows"],2)
        self.assertEqual(rows["dividend_cash_outflow"]["status"],"row_missing_or_ambiguous")

    def test_positive_dividend_in_cashflow_is_not_automatically_paid_outflow(self):
        pages=audited_pages(2024)
        pages[8]=pages[8].replace("0            -735 621","0             735 621")
        rows=m.audited_rows(pages,2024)
        self.assertEqual(rows["dividend_cash_outflow"]["status"],"row_missing_or_ambiguous")

    def test_no_verified_pdf_yields_no_yearly_values(self):
        report=synthetic_report(2025)
        report["pdfReadAndOfficialHashVerified"]=False
        self.assertEqual(m.reconcile([report]),[])

if __name__=="__main__":unittest.main()
