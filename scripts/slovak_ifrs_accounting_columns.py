"""Conservative year-column extraction from Kia Slovakia official IFRS PDFs.

Only parse exact, recognizable Slovak financial-statement rows, in the
expected PDF page/statement and the specified column year. Never infer
payments from dividend rights, accounting income, equity balances, the
previous year's comparative column or a different reporting period.
"""
from __future__ import annotations
import re

METRICS={
 "dividend_cash_outflow":"현지법인 현금흐름표의 배당 지급",
 "annual_profit_cf_reconciliation":"현지법인 현금흐름표에 표시된 당기순이익",
 "retained_earnings_balance":"현지법인 재무상태표의 전기이월이익잉여금"
}
# Source PDF pages are 1-indexed for reporters and 0-indexed in Python:
# 7 = balance sheet, 8 = change in equity, 9 = cash flow.
PAGES={"retained_earnings_balance":7,
       "annual_profit_cf_reconciliation":9,
       "dividend_cash_outflow":9}
NUMBER=r"-?(?:\d{1,3}(?:[ \u00a0]\d{3})+|\d+)"
LINE_CASH=re.compile(
    r"^\s*Splatenie\s+dividend\s+(?:4\s+)?(?P<now>"+NUMBER+
    r")\s+(?P<prior>"+NUMBER+r")\s*$",re.I)
LINE_PROFIT=re.compile(r"^\s*Zisk\s+za\s+účtovné\s+obdobie\s+"
     r"(?P<now>"+NUMBER+r")\s+(?P<prior>"+NUMBER+r")\s*$",re.I)
LINE_RETAINED=re.compile(r"^\s*Nerozdelený\s+zisk\s+minulých\s+období\s+"
    r"(?P<now>"+NUMBER+r")\s+(?P<prior>"+NUMBER+r")\s*$",re.I)
LABELS={
    "dividend_cash_outflow":LINE_CASH,
    "annual_profit_cf_reconciliation":LINE_PROFIT,
    "retained_earnings_balance":LINE_RETAINED
}
PAGE_HEADING={
    "dividend_cash_outflow":"Výkaz peňažných tokov",
    "annual_profit_cf_reconciliation":"Výkaz peňažných tokov",
    "retained_earnings_balance":"Výkaz o finančnej situácii"
}
MAX_EXCERPT=220

def clean_number(text):
    if not isinstance(text,str):return None
    number=re.sub(r"[ \u00a0]","",text)
    if not re.fullmatch(r"-?\d{1,12}",number):return None
    return int(number)

def columns(page_text,report_year,metric):
    """Return two explicitly labelled calendar-year values or no usable row."""
    if type(report_year) is not int or report_year not in (2024,2025):
        return {"status":"wrong_year"}
    if not isinstance(page_text,str) or PAGE_HEADING[metric].lower() not in page_text.lower():
        return {"status":"statement_page_heading_not_found"}
    if not re.search(r"\bV\s+tisícoch\s+EUR\b",page_text,re.I):
        return {"status":"eur_thousands_unit_not_verified"}
    # The audited statement must name the reporting period. We do not parse a
    # same-looking row from an accounting note or subsidiary comparison table.
    if (str(report_year) not in page_text or
        str(report_year-1) not in page_text):
        return {"status":"both_column_years_not_verified"}
    matches=[]
    for raw in page_text.splitlines():
        # normalize internal whitespace only after identifying one full row
        txt=re.sub(r"[ \t\u00a0]+"," ",raw).strip()
        m=LABELS[metric].fullmatch(txt)
        if not m:continue
        curr=clean_number(m.group("now"))
        prev=clean_number(m.group("prior"))
        if curr is None or prev is None:continue
        if metric=="dividend_cash_outflow" and (curr>0 or prev>0):
            # Payments in the issuer statement are represented as negative
            # financing cash outflows or exact 0, not positive receipts.
            continue
        matches.append((curr,prev,txt))
    if len(matches)!=1:
        return {"status":"row_missing_or_ambiguous","matchingRows":len(matches)}
    curr,prev,source_line=matches[0]
    return {
      "status":"two_period_official_statement_row_extracted",
      "unit":"EUR_thousands",
      "reportYear":report_year,
      "columnYears":[report_year,report_year-1],
      "sourceLine":source_line[:MAX_EXCERPT],
      "values":[curr,prev],
      "manualSourceTableReviewConfirmed":False,
      "parentRecipientVerified":False,
      "cashReceivedInKoreaVerified":False,
      "currentYearWasNotConfusedWithComparative":True
    }

def audited_rows(pages,report_year):
    if not isinstance(pages,list):raise ValueError("no_pdf_pages")
    out={}
    for metric,page in PAGES.items():
        if len(pages)<page or not isinstance(pages[page-1],str):
            out[metric]={"status":"required_pdf_page_missing"}
            continue
        parsed=columns(pages[page-1],report_year,metric)
        parsed["sourcePdfPage"]=page
        parsed["statementRowType"]=metric
        parsed["rowScope"]=METRICS[metric]
        out[metric]=parsed
    return out

def reconcile(reports):
    """Never double count an annual amount shown again in comparative column."""
    if not isinstance(reports,list):raise ValueError("no_verified_reports")
    entries={}
    for report in reports:
        if not isinstance(report,dict):continue
        if report.get("pdfReadAndOfficialHashVerified") is not True:
            continue
        year=report.get("year")
        if year not in (2024,2025):continue
        rows=report.get("auditedStatementRows")
        if not isinstance(rows,dict):continue
        for metric in METRICS:
            row=rows.get(metric)
            if not isinstance(row,dict) or row.get("status")!="two_period_official_statement_row_extracted":
                continue
            if (row.get("reportYear")!=year or
                row.get("columnYears")!=[year,year-1] or
                row.get("unit")!="EUR_thousands" or
                row.get("manualSourceTableReviewConfirmed") is not False):
                continue
            for y,value in zip(row["columnYears"],row["values"]):
                if y not in (2023,2024,2025) or type(value) is not int:continue
                entries.setdefault((metric,y),[]).append({
                    "reportYear":year,"sourcePdfPage":row.get("sourcePdfPage"),
                    "reportedAs":"reporting_year" if y==year else "comparative_previous_year",
                    "value":value,"pdfUrl":report.get("attachmentUrl"),
                    "documentSha256":report.get("sha256")
                })
    result=[]
    for metric,year in sorted(entries,key=lambda k:(k[0],-k[1])):
        proofs=entries[(metric,year)]
        # Collapse the same calendar year seen in two audited annual reports.
        differing=len({p["value"] for p in proofs})>1
        selected=None if differing else proofs[0]["value"]
        result.append({
           "metric":metric,"metricLabelKo":METRICS[metric],
           "calendarYear":year,"unit":"EUR_thousands",
           "value":selected,
           "sourceDocuments":proofs,
           "sourceDocumentCount":len(proofs),
           "comparisonAcrossAnnualReportsConsistent":not differing,
           "annualValueWithheldBecauseContradiction":differing,
           "annualReportDisclosureObserved":True,
           "manualSourceTableReviewConfirmed":False,
           "koreanParentCashReceiptVerified":False,
           "samePeriodAs2026KiaDartDividendIncome":False,
           "notNew2026Distribution":True
        })
    return result
