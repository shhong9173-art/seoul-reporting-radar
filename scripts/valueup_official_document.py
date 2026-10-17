"""Bounded first-party OpenDART value-up document inspection.

An OpenDART title receipt is never evidence that the attached PDF was read.
This inspection uses official document.xml ZIP only. Literal target excerpts
prove what the retrieved text says, not goal achievement, novelty or
comparability to an older plan.
"""
from __future__ import annotations

import hashlib
import re
from urllib.parse import urlsplit,parse_qs

from dart_lineage import zip_documents
from dart_numeric_extractor import html_to_text

DART_RECEIPT=re.compile(r"20\d{12}\Z")
CODE=re.compile(r"\d{8}\Z")
MAX_TEXT=2_000_000
MAX_DOCS=12
TARGETS={
    "pbr_2029_at_least_0_5":re.compile(
        r"2029\s*년.{0,65}?\bPBR\b\s*(?:0[.,]5)\s*배\s*이상",re.I),
    "five_year_shareholder_return_50_percent":re.compile(
        r"5\s*개년.{0,90}?주주\s*환원\s*율\s*50\s*%",re.I),
}

def is_current_valueup_filing(row):
    if not isinstance(row,dict):return False
    receipt=row.get("receiptNo")
    company=row.get("company")
    code=row.get("corpCode")
    published=row.get("published")
    report=row.get("report")
    url=row.get("sourceUrl")
    if (not isinstance(receipt,str) or not DART_RECEIPT.fullmatch(receipt)
        or not isinstance(code,str) or not CODE.fullmatch(code)
        or not isinstance(company,str) or not company.strip()
        or not isinstance(published,str) or published!=receipt[:8]
        or not isinstance(report,str) or
        not "".join(report.split()).startswith("기업가치제고계획")
        or row.get("isCorrection") is not False
        or "정정" in report
        or row.get("sourceType")!="official_list_receipt"
        or not isinstance(url,str)):
        return False
    try:
        parsed=urlsplit(url)
        return (parsed.scheme=="https" and parsed.hostname=="dart.fss.or.kr"
            and parsed.port is None and parsed.username is None
            and parsed.password is None and parsed.path=="/dsaf001/main.do"
            and parse_qs(parsed.query)=={"rcpNo":[receipt]}
            and not parsed.fragment)
    except ValueError:return False

def literal_target_excerpts(documents):
    """Extract only unambiguous, literally present text from official ZIP.

    No semantic inference from similar percentages, no PDF claims.
    Conflicting appearances of exact targets and a contradictory
    2029-PBR/5-year-return phrase block confident target assertions.
    """
    if (not isinstance(documents,list) or not 1<=len(documents)<=MAX_DOCS
        or any(not isinstance(d,str) or len(d)>MAX_TEXT for d in documents)):
        raise ValueError("official_document_text_invalid_or_oversize")
    matches={name:[] for name in TARGETS}
    signatures=[]
    for doc in documents:
        signatures.append(hashlib.sha256(doc.encode("utf-8")).hexdigest())
        plain=html_to_text(doc.encode("utf-8"))
        for name,pattern in TARGETS.items():
            for result in list(pattern.finditer(plain))[:3]:
                literal=plain[max(0,result.start()-25):min(len(plain),result.end()+25)]
                matches[name].append(" ".join(literal.split())[:180])
    out={}
    for name,examples in matches.items():
        if len(examples)>0:
            out[name]={
                "literalExcerpts":examples[:3],
                "matchesInRetrievedOriginalText":len(examples),
                "sourceBasis":"official_opendart_document_xml_text_only",
                "issuerPdfAttachmentRead":False,
                "sameMetricDenominatorAndTimeWindowVerified":False,
            }
    return {
       "status":"official_original_text_checked_no_inference",
       "targetExcerpts":out,
       "documentTextSha256":signatures[:MAX_DOCS],
       "documentsExamined":len(documents),
       "officialXmlOrHtmlBodyRetrieved":True,
       "officialAttachmentPdfReviewed":False,
       "targetAchievementVerified":False,
       "crossYearPlanPeriodMatched":False,
       "priorPressCoverageFulltextReviewed":False,
       "exclusiveConfirmed":False,
       "approvedForPitch":False,
       "notMatchedDoesNotMeanIssuerHasNoTarget":True,
    }

def valueup_document_evidence(row,key,*,documents=zip_documents):
    if not is_current_valueup_filing(row) or not isinstance(key,str) or not key:
        raise ValueError("valueup_requires_verified_current_official_issuer_and_key")
    try:
        texts=documents(key,row["receiptNo"])
        proof=literal_target_excerpts(texts)
        return {**row,"status":"official_valueup_document_review",
                "sourceError":False,"valueupPrimarySource":proof}
    except (ValueError,OSError,RuntimeError,TimeoutError,ConnectionError,
            TypeError) as exc:
        # No secrets or raw request URLs in the public published diagnostics.
        return {**row,"status":"valueup_document_unavailable",
                "sourceError":True,"errorType":type(exc).__name__,
                "valueupPrimarySource":{
                    "status":"source_unavailable_not_zero_target_facts",
                    "officialXmlOrHtmlBodyRetrieved":False,
                    "officialAttachmentPdfReviewed":False,
                    "exclusiveConfirmed":False,
                    "approvedForPitch":False}}
