"""Separate proven historical Slovak IFRS figures from unproven 2026 cash transfers."""
from __future__ import annotations
import re
from urllib.parse import urlsplit

METRICS={"dividend_cash_outflow","annual_profit_cf_reconciliation","retained_earnings_balance"}

def _official_pdf_document(doc):
    """Validate public Slovak government PDF document identity, not an inference."""
    if not isinstance(doc,dict):return False
    url=doc.get("pdfUrl")
    sha=doc.get("documentSha256")
    if not isinstance(url,str) or not isinstance(sha,str):return False
    u=urlsplit(url)
    return (u.scheme=="https" and u.netloc=="www.registeruz.sk"
            and re.fullmatch(r"/cruz-public/domain/financialreport/attachment/[1-9]\d{3,11}",
                             u.path) is not None
            and not u.query and not u.fragment
            and re.fullmatch(r"[a-f0-9]{64}",sha) is not None
            and doc.get("sourcePdfPage")==9 and
            doc.get("reportedAs") in ("reporting_year","comparative_previous_year")
            and doc.get("reportYear") in (2024,2025))


def _profit_year_delta(rows):
    """Two years from SAME government 2025 PDF, no currency/period mixing."""
    by={}
    for row in rows:
        if (not isinstance(row,dict) or
            row.get("metric")!="annual_profit_cf_reconciliation" or
            row.get("year") not in (2024,2025) or
            type(row.get("amountThousandEur")) is not int or
            not 0<=row["amountThousandEur"]<1_000_000_000 or
            row.get("annualReportComparativeConflict") is not False or
            row.get("parentRecipientVerified") is not False or
            row.get("koreanCashReceiptVerified") is not False or
            row.get("humanAuditOfParsedRowCompleted") is not False or
            row.get("amountFromKiaParentDart2026") is not False or
            row.get("year2026LocalPaymentNotYetVerified") is not True):
            continue
        docs=row.get("sourceDocuments")
        if not isinstance(docs,list) or not docs or len(docs)>3 or not all(
            _official_pdf_document(doc) for doc in docs):
            continue
        year=row["year"]
        # Explicit 2025 accounting report must contain the current year and
        # its 2024 comparative in identical EUR-thousands columns.
        expected_as="reporting_year" if year==2025 else "comparative_previous_year"
        proof=next((doc for doc in docs if doc.get("reportYear")==2025
                    and doc.get("reportedAs")==expected_as),None)
        if proof is None:continue
        if year in by: return None  # Ambiguous/duplicated accounting rows.
        by[year]=(row["amountThousandEur"],proof)
    if set(by)!={2024,2025}:return None
    before,before_doc=by[2024]
    current,current_doc=by[2025]
    if (before==0 or
        before_doc["pdfUrl"]!=current_doc["pdfUrl"] or
        before_doc["documentSha256"]!=current_doc["documentSha256"]):
        return None
    change=current-before
    return {
      "status":"same_official_2025_pdf_comparative_columns_machine_extracted",
      "company":"Kia Slovakia s. r. o.",
      "basis":"local_cash_flow_statement_profit_reconciliation_start_line",
      "currency":"EUR","unit":"EUR_thousands",
      "priorCalendarYear":2024,"priorValueThousandEur":before,
      "currentCalendarYear":2025,"currentValueThousandEur":current,
      "changeThousandEur":change,
      "changePercent":round(change*100/before,1),
      "sameOfficialGovernmentPdfUrl":current_doc["pdfUrl"],
      "sourcePdfPage":9,
      "sourcePdfSha256":current_doc["documentSha256"],
      "sourceLineManuallyReviewed":False,
      "sameCurrencyAndPeriodBasisWithinLocalProfitComparison":True,
      "samePeriodAsKorean2026HalfYearDividendIncome":False,
      "distributionApprovedByLocalResolutionVerified":False,
      "koreanParentCashReceiptVerified":False,
      "sameAnglePriorPressFulltextChecked":False,
      "exclusiveConfirmed":False,
      "warning":"슬로바키아 정부 등록 IFRS 2025년 PDF의 당기/전기 비교열 기계 추출. 원본 9쪽 수동 검산 전. 2026년 한국 모회사 배당금수익과 동일 회계기간·거래가 아니며 배당결의·현금수취 입증 불가."
    }


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
    # A same-PDF, same-unit local year-on-year comparison is permissible.
    # It is NOT a ratio to Kia's separate-period 2026 dividend income.
    local_profit=_profit_year_delta(rows)
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
        "slovakLocalProfitYearOnYear":local_profit if is_kia else None,
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
