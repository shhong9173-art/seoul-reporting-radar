"""Evidence-gated inspection of an issuer's DART business-cessation filing.

An issuer's intended cessation date, reported affected sales and business
description do not establish that a facility actually stopped production,
contract supply was cancelled, employees were redeployed, or revenue declined.
Parent/subsidiary filings are source receipts, NOT automatically two events.
"""
from __future__ import annotations

import hashlib
import re
from datetime import date
from urllib.error import URLError
from urllib.parse import urlsplit, parse_qs

from dart_lineage import zip_documents
from dart_numeric_extractor import html_to_text

RECEIPT = re.compile(r"20\d{12}\Z")
CORP = re.compile(r"\d{8}\Z")
TR = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.I | re.S)
CELL = re.compile(r"<(?:td|th|te|tu)\b[^>]*>(.*?)</(?:td|th|te|tu)>", re.I | re.S)
MONEY = re.compile(r"(?:\d{1,3}(?:,\d{3})+|\d{1,16})\Z")
PERCENT = re.compile(r"\d{1,3}(?:\.\d{1,5})?\Z")
DATE_ISO = re.compile(r"20\d{2}[-./]\d{1,2}[-./]\d{1,2}\Z")
DATE_KOREAN = re.compile(r"(20\d{2})년(\d{1,2})월(\d{1,2})일\Z")
ALLOWED_TITLES = {
    "주요사항보고서(영업정지)": "issuer_business_cessation",
    "주요사항보고서(영업정지)(자회사의주요경영사항)":
        "parent_disclosure_of_subsidiary",
}
MAX_DOCS = 12
MAX_CHARS = 2_000_000


def _clean(value):
    return re.sub(r"\s+", "", value).replace("：", ":")


def business_cessation_filing(row):
    """Only original filings with the exact verified issuer and DART receipt."""
    if not isinstance(row, dict):
        return False
    receipt = row.get("receiptNo")
    published = row.get("published")
    report = row.get("report")
    url = row.get("sourceUrl")
    if (not isinstance(receipt, str) or not RECEIPT.fullmatch(receipt)
        or not isinstance(row.get("corpCode"), str)
        or not CORP.fullmatch(row["corpCode"])
        or not isinstance(row.get("company"), str) or not row["company"].strip()
        or not isinstance(published, str) or published != receipt[:8]
        or not isinstance(report, str)
        or _clean(report) not in ALLOWED_TITLES
        or row.get("isCorrection") is not False
        or row.get("sourceType") != "official_list_receipt"
        or not isinstance(url, str)):
        return False
    try:
        loc = urlsplit(url)
        return (loc.scheme == "https" and loc.hostname == "dart.fss.or.kr"
            and loc.port is None and loc.username is None
            and loc.password is None and loc.path == "/dsaf001/main.do"
            and parse_qs(loc.query) == {"rcpNo": [receipt]}
            and not loc.fragment)
    except ValueError:
        return False


def _money(value):
    value = _clean(value)
    if not MONEY.fullmatch(value):
        return None
    number = int(value.replace(",", ""))
    return str(number) if 0 <= number <= 10**16 else None


def _percent(value):
    value = _clean(value).removesuffix("%")
    if not PERCENT.fullmatch(value):
        return None
    number = float(value)
    if number < 0 or number > 100:
        return None
    return value


def _planned_date(value):
    value = _clean(value)
    match = DATE_KOREAN.fullmatch(value)
    if match:
        iso = "-".join(match.groups())
    elif DATE_ISO.fullmatch(value):
        iso = re.sub(r"[-./]", "-", value)
    else:
        return None
    try:
        return date.fromisoformat(
            "-".join([iso.split("-")[0],
                      iso.split("-")[1].zfill(2),
                      iso.split("-")[2].zfill(2)])).isoformat()
    except ValueError:
        return None


def _scope(value):
    scope = " ".join(str(value).split()).strip()
    if not (2 <= len(scope) <= 140):
        return None
    if any(x in scope for x in ("\n", "<", ">", "http://", "https://")):
        return None
    return scope


def literal_business_cessation_terms(documents):
    """Extract only same-row explicit labels; reject contradictory duplicates."""
    if (not isinstance(documents, list) or not 1 <= len(documents) <= MAX_DOCS
        or any(not isinstance(x, str) or len(x) > MAX_CHARS for x in documents)):
        raise ValueError("invalid_business_cessation_original_documents")
    values = {}
    conflicts = set()
    sha = []
    examined = 0
    def remember(name, value, label):
        if value is None:
            return
        if name in values and values[name]["value"] != value:
            conflicts.add(name)
        else:
            values[name] = {
                "value": value, "officialTableLabel": label[:95],
                "basis": "same_official_table_row",
                "operationalShutdownVerified": False,
                "independentBusinessEffectVerified": False,
                "priorPressCoverageVerified": False,
            }

    for doc in documents:
        sha.append(hashlib.sha256(doc.encode("utf-8")).hexdigest())
        for match in TR.finditer(doc):
            inner = match.group(1)
            if re.search(r"<tr\b", inner, re.I):
                continue
            cells = [html_to_text(value.encode("utf-8")).strip()
                     for value in CELL.findall(inner)]
            if not 2 <= len(cells) <= 18:
                continue
            examined += 1
            for i in range(len(cells)-1):
                raw_label = cells[i]
                label = re.sub(r"^\d{1,2}[.]\s*", "", _clean(raw_label))
                value = cells[i+1]
                if label in ("영업정지분야", "영업정지대상사업", "영업정지대상"):
                    remember("reportedBusinessScope", _scope(value), raw_label)
                elif label in ("영업정지금액(원)", "영업정지금액"):
                    # Unit must be in this label; no assumption on naked cell.
                    if "(원)" in label:
                        remember("reportedAffectedSalesWon", _money(value), raw_label)
                elif label in ("최근매출총액(원)", "최근매출액(원)"):
                    remember("reportedRecentSalesWon", _money(value), raw_label)
                elif label in ("매출액대비(%)", "최근매출액대비(%)"):
                    remember("issuerReportedRevenueRatioPct", _percent(value), raw_label)
                elif label in ("영업정지일자", "영업정지예정일", "영업정지예정일자"):
                    remember("issuerStatedCessationDate", _planned_date(value), raw_label)

    for name in conflicts:
        values.pop(name, None)
    return {
        "status": ("official_original_cessation_table_fields"
                   if values else "official_text_opened_fields_not_unambiguous"),
        "observedTerms": values,
        "conflictingFields": sorted(conflicts),
        "documentsExamined": len(documents), "tableRowsExamined": examined,
        "documentTextSha256": sha, "officialXmlOrHtmlBodyRetrieved": True,
        "officialAttachmentPdfReviewed": False,
        "operationalShutdownVerified": False,
        "independentFinancialImpactVerified": False,
        "subsidiaryIdentityIndependentlyLinked": False,
        "duplicateUnderlyingEventExcludedFromUniqueCount": False,
        "priorMediaFulltextCompared": False,
        "exclusiveConfirmed": False, "approvedForPitch": False,
        "warning": ("공시 본문 기재 사실만 확인. 실제 영업중단 실행 여부와 매출 영향, "
                    "모·자회사 중복 사건 여부, 선행보도 전문 모두 별도 검증"),
    }


def business_cessation_document_evidence(row, key, *, documents=zip_documents):
    if (not business_cessation_filing(row)
        or not isinstance(key, str) or not key.strip()):
        raise ValueError("business_cessation_requires_verified_official_receipt")
    relation = ALLOWED_TITLES[_clean(row["report"])]
    try:
        proof = literal_business_cessation_terms(
            documents(key, row["receiptNo"]))
        return {**row, "status": "official_business_cessation_document_review",
                "sourceError": False, "businessCessationFilingRelation": relation,
                "businessCessationPrimarySource": proof,
                "companyImpactVerified": False, "scoopConfirmed": False,
                "approvedForPitch": False}
    except (ValueError, RuntimeError, URLError, TimeoutError, OSError,
            ConnectionError, TypeError) as exc:
        return {**row, "status": "business_cessation_document_unavailable",
                "sourceError": True, "errorType": type(exc).__name__,
                "businessCessationFilingRelation": relation,
                "businessCessationPrimarySource": {
                    "status": "source_unavailable_not_zero",
                    "officialXmlOrHtmlBodyRetrieved": False,
                    "operationalShutdownVerified": False,
                    "exclusiveConfirmed": False,
                    "approvedForPitch": False},
                "companyImpactVerified": False,
                "scoopConfirmed": False, "approvedForPitch": False}
