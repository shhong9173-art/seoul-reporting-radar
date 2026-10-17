"""DART contract-specific news-index search; index hits are NOT a fulltext audit.

Uses exact issuer/receipt/official-table identity to construct targeted searches.
The contract amount and distinctive official project words must match together
before a syndicated headline is treated as a likely already-covered event.
"""
from __future__ import annotations
import re
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit,parse_qs

NUMBER=re.compile(r"(?<!\d)(\d{1,3}(?:,\d{3})+|\d{1,13})(?:\.(\d{1,3}))?\s*억")
STOP={"공급","납품","계약","체결","관련","사업","프로젝트","건","경우","위한","시설","기자","의","전력","판매"}

def exact_contract_evidence(filing, monitor):
    if not isinstance(filing,dict) or not isinstance(monitor,dict):
        return None
    if monitor.get("status")!="industry_beat_official_receipt_review":
        return None
    receipt=filing.get("receiptNo")
    company=filing.get("corpName")
    url=filing.get("url")
    if not (isinstance(receipt,str) and re.fullmatch(r"20\d{12}",receipt)
            and isinstance(url,str) and isinstance(company,str)):
        return None
    parsed=urlsplit(url)
    if not (parsed.scheme=="https" and parsed.netloc=="dart.fss.or.kr" and
        parsed.path=="/dsaf001/main.do" and
        parse_qs(parsed.query)=={"rcpNo":[receipt]}):
        return None
    for doc in monitor.get("records",[])[:300]:
        if not isinstance(doc,dict):continue
        if (doc.get("receiptNo")!=receipt or doc.get("company")!=company or
            doc.get("sourceUrl")!=url or doc.get("isCorrection") is not False or
            doc.get("status")!="official_document_read" or
            doc.get("documentFieldExtractionStatus")!="official_table_terms_not_business_effect"):
            continue
        f=doc.get("observedFields") or {}
        e=doc.get("observedFieldEvidence") or {}
        if not isinstance(f,dict) or not isinstance(e,dict):continue
        if not all(isinstance(e.get(key),dict) and
                   e[key].get("basis")=="same_official_table_row"
                   for key in ("contract_subject","contract_amount")):
            continue
        subject=str(f.get("contract_subject") or "")[:110]
        amount=str(f.get("contract_amount") or "").replace(",","")
        if not subject or not amount.isdigit() or not 100_000_000<=int(amount)<=100_000_000_000_000:
            continue
        return {"company":company,"receiptNo":receipt,"contractSubject":subject,
                "amountWon":int(amount),"officialUrl":url,
                "sameContractMediaFulltextVerified":False}
    return None

def project_words(subject):
    words=re.findall(r"[가-힣A-Za-z]{2,}|[0-9]{3,}[a-zA-Z]+",subject or "")
    return [w for w in words if w.lower() not in STOP and len(w)>=2][:7]

def precise_press_queries(evidence):
    if not isinstance(evidence,dict):return []
    company=str(evidence.get("company") or "")
    terms=project_words(evidence.get("contractSubject") or "")
    amount=evidence.get("amountWon")
    if not company or not isinstance(amount,int) or len(terms)<2:return []
    rounded=round(amount/100_000_000)
    words=" ".join(terms[:3])
    return [f'"{company}" "{words}"',f'"{company}" "{rounded:,}억"']

def similar_amount_in_headline(text,official_won):
    if not isinstance(official_won,int) or not isinstance(text,str):
        return False
    target=Decimal(official_won)/Decimal(100_000_000)
    for m in NUMBER.finditer(text):
        try:
            value=Decimal((m.group(1) or "").replace(",","")+
                    ("."+(m.group(2)) if m.group(2) else ""))
        except InvalidOperation:
            continue
        if abs(value-target)<=Decimal("1.0"):
            return True
    return False

def likely_same_contract_indexed(evidence, headline):
    """Only possible coverage, never proof that article body reports same deal."""
    if not isinstance(evidence,dict) or not isinstance(headline,str):return False
    company=evidence.get("company") or ""
    terms=project_words(evidence.get("contractSubject") or "")
    lowered=headline.lower()
    matched=sum(w.lower() in lowered for w in terms)
    return bool(company and company.lower() in lowered and len(terms)>=2 and
                matched>=2 and similar_amount_in_headline(
                    headline,evidence.get("amountWon")))
