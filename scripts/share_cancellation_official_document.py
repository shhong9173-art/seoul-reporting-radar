"""Inspect issuer-submitted share-cancellation filings, without inferring execution.

Only a precise DART issuer/receipt is accepted. Values are reported only when
their share class or scheduled-date label is adjacent in an official document
row. A planned cancellation is not an executed cancellation, a dividend,
a verified shareholder-return numerator, or an exclusive story.
"""
from __future__ import annotations

import hashlib
import re
from datetime import date
from urllib.parse import parse_qs, urlsplit
from urllib.error import URLError

from dart_lineage import zip_documents
from dart_numeric_extractor import html_to_text

RECEIPT = re.compile(r"20\d{12}\Z")
CODE = re.compile(r"\d{8}\Z")
TR = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.I | re.S)
CELL = re.compile(r"<(?:td|th|te|tu)\b[^>]*>(.*?)</(?:td|th|te|tu)>", re.I | re.S)
SHARES = re.compile(r"(?:\d{1,3}(?:,\d{3})+|\d{1,12})(?:주)?\Z")
DATE = re.compile(r"20\d{2}[-./]\d{1,2}[-./]\d{1,2}\Z")
MAX_DOCS = 12
MAX_CHARS = 2_000_000


def cancellation_filing(row):
    if not isinstance(row, dict):
        return False
    no = row.get("receiptNo")
    published = row.get("published")
    title = row.get("report")
    url = row.get("sourceUrl")
    if (not isinstance(no, str) or not RECEIPT.fullmatch(no)
        or not isinstance(row.get("corpCode"), str)
        or not CODE.fullmatch(row["corpCode"])
        or not isinstance(row.get("company"), str)
        or not row["company"].strip()
        or not isinstance(published, str) or published != no[:8]
        or not isinstance(title, str)
        or "".join(title.split()) != "주식소각결정"
        or row.get("isCorrection") is not False
        or row.get("sourceType") != "official_list_receipt"
        or not isinstance(url, str)):
        return False
    try:
        u = urlsplit(url)
        return (u.scheme == "https" and u.hostname == "dart.fss.or.kr"
                and u.port is None and not u.username and not u.password
                and u.path == "/dsaf001/main.do"
                and parse_qs(u.query) == {"rcpNo": [no]}
                and not u.fragment)
    except ValueError:
        return False


def _compact(text):
    return re.sub(r"\s+", "", text).replace("：", ":")


def _quantity(cell):
    raw = _compact(cell)
    if not SHARES.fullmatch(raw):
        return None
    number = raw.removesuffix("주").replace(",", "")
    value = int(number)
    return str(value) if 0 <= value <= 10**12 else None


def _date(cell):
    raw = _compact(cell)
    if not DATE.fullmatch(raw):
        return None
    try:
        return date.fromisoformat(re.sub(r"[-./]", "-", raw)).isoformat()
    except ValueError:
        return None


def literal_cancellation_terms(documents):
    if (not isinstance(documents, list) or not 1 <= len(documents) <= MAX_DOCS
        or any(not isinstance(x, str) or len(x) > MAX_CHARS for x in documents)):
        raise ValueError("invalid_official_share_cancellation_documents")
    values = {}
    conflicts = set()
    signatures = []
    table_rows = 0
    def remember(name, value, label):
        if value is None:
            return
        if name in values and values[name]["value"] != value:
            conflicts.add(name)
        else:
            values[name] = {"value": value, "sourceLabel": label,
                            "basis": "same_official_table_row",
                            "completedCancellationVerified": False,
                            "denominatorOrShareholderReturnVerified": False}

    for doc in documents:
        signatures.append(hashlib.sha256(doc.encode("utf-8")).hexdigest())
        for tr in TR.finditer(doc):
            raw = tr.group(1)
            if re.search(r"<tr\b", raw, re.I):
                continue
            cells = [html_to_text(x.encode("utf-8")).strip()
                     for x in CELL.findall(raw)]
            if not 2 <= len(cells) <= 20:
                continue
            table_rows += 1
            keys = [_compact(c) for c in cells]
            # A share-class pair must occur in a row explicitly headed as
            # shares to cancel. Avoid borrowing quantities from unrelated
            # table rows such as outstanding shares or treasury shares.
            in_cancelled_shares = any("소각할주식" in k or "소각대상주식" in k
                                      for k in keys)
            for i in range(len(keys) - 1):
                label = keys[i]
                next_value = cells[i + 1]
                if in_cancelled_shares:
                    if label in ("보통주", "보통주식"):
                        remember("ordinarySharesToCancel", _quantity(next_value), cells[i])
                    if label in ("우선주", "우선주식", "종류주식", "기타주식"):
                        remember("preferredSharesToCancel", _quantity(next_value), cells[i])
                if label in ("소각예정일", "소각예정일자", "소각할주식의소각예정일",
                             "소각예정일자(예정)"):
                    remember("scheduledCancellationDate", _date(next_value), cells[i])
    for key in conflicts:
        values.pop(key, None)
    return {
        "status": ("official_original_share_cancellation_table_fields"
                   if values else "official_text_opened_fields_not_unambiguous"),
        "observedTerms": values,
        "conflictingFields": sorted(conflicts),
        "officialXmlOrHtmlBodyRetrieved": True,
        "officialPdfAttachmentReviewed": False,
        "documentsExamined": len(documents),
        "tablesExamined": table_rows,
        "documentTextSha256": signatures,
        "actualCancellationExecutedVerified": False,
        "shareholderReturnNumeratorVerified": False,
        "historicalPressFulltextChecked": False,
        "exclusiveConfirmed": False,
        "approvedForPitch": False,
        "caution": "주식소각결정 공시의 기재값일 뿐 실제 소각 완료·주주환원 산식·기보도 여부는 미확인",
    }


def cancellation_document_evidence(row, key, *, documents=zip_documents):
    if not cancellation_filing(row) or not isinstance(key, str) or not key.strip():
        raise ValueError("cancellation_requires_valid_official_receipt")
    try:
        docs = documents(key, row["receiptNo"])
        evidence = literal_cancellation_terms(docs)
        return {**row, "status": "official_share_cancellation_document_review",
                "sourceError": False, "shareCancellationPrimarySource": evidence,
                "companyImpactVerified": False, "scoopConfirmed": False,
                "approvedForPitch": False}
    except (ValueError, RuntimeError, URLError, TimeoutError, OSError,
            ConnectionError, TypeError) as exc:
        return {**row, "status": "share_cancellation_document_unavailable",
                "sourceError": True, "errorType": type(exc).__name__,
                "shareCancellationPrimarySource": {
                    "status": "source_unavailable_not_zero",
                    "officialXmlOrHtmlBodyRetrieved": False,
                    "actualCancellationExecutedVerified": False,
                    "exclusiveConfirmed": False,
                    "approvedForPitch": False},
                "scoopConfirmed": False, "approvedForPitch": False}
