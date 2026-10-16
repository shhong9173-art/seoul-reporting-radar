"""Separate proven historical Slovak IFRS figures from unproven 2026 cash transfers."""
from __future__ import annotations

METRICS={"dividend_cash_outflow","annual_profit_cf_reconciliation","retained_earnings_balance"}

def build_gap(dossier):
    """Strict gating. Never compare 2025 annual payment with 2026 DART income as like-for-like."""
    data=dossier.get("slovakPdfPrimaryReview") or {}
    facts=dossier.get("officialFact") or {}
    expected=facts.get("recognizedAmountInMillionKrw")
    rows=data.get("auditedCalendarYearRows") or []
    verified=[]
    for row in rows:
        if (not isinstance(row,dict) or row.get("metric") not in METRICS
            or row.get("year") not in (2023,2024,2025)
            or row.get("annualReportComparativeConflict") is not False
            or type(row.get("amountThousandEur")) is not int
            or row.get("parentRecipientVerified") is not False
            or row.get("koreanCashReceiptVerified") is not False
            or row.get("amountFromKiaParentDart2026") is not False
            or row.get("year2026LocalPaymentNotYetVerified") is not True
            or row.get("humanAuditOfParsedRowCompleted") is not False):
            continue
        verified.append((row["metric"],row["year"],row["amountThousandEur"]))
    by={(m,y):v for m,y,v in verified}
    y2025=by.get(("dividend_cash_outflow",2025))
    y2024=by.get(("dividend_cash_outflow",2024))
    is_kia=(dossier.get("companyGroup")=="기아"
        and "kiaslovakia" in str(facts.get("recognizedFromEntity") or "").lower().replace(" ","")
        and type(expected) is int and expected>0
        and facts.get("recognizedPeriodLabel")=="current")
    return {
        "status":"cross_period_and_accounting_basis_requires_independent_primary_docs"
                 if is_kia else "not_applicable_or_parent_income_not_verified",
        "koreanIssuerIncomePeriod":"2026_first_half" if is_kia else None,
        "koreanIssuerRecognizedIncomeMillionKrw":expected if is_kia else None,
        "slovakAuditedPaymentCalendarYears":[{"year":year,"outflowThousandEur":value}
          for year,value in ((2024,y2024),(2025,y2025)) if value is not None],
        "differentAccountingLine":True,
        "differentAccountingPeriod":True,
        "differentCurrencyAndUnit":True,
        "local2026InterimStatementChecked":False,
        "parent2026CashStatementMatched":False,
        "slovak2026DistributionResolutionChecked":False,
        "parentRecipientIdentifiedInLocalDisclosure":False,
        "koreanCashReceivedVerified":False,
        "canCalculateParentCashTransferFromTheseRows":False,
        "canClaimNoDividendIn2026":False,
        "canClaimOverseasDividendIsExclusive":False,
        "specificNextDocuments":[
            "Kia 2026 first-half separate financial-statement dividend-income note and cash-flow statement with bank/payment timing",
            "Kia Slovakia 2026 interim distribution decision and 2026 cash-flow/payment evidence, if published",
            "Official legal-entity shareholder and distribution resolution identifying actual recipient",
            "Prior Korean and Slovak press full text on the exact 2026 dividend recognition amount"
        ],
        "editorialWarning":"2024/2025 Slovak audited payment 0 is historical; cannot be subtracted from a 2026 Korean issuer dividend-income recognition to infer unpaid, missing, or hidden cash."
    }
