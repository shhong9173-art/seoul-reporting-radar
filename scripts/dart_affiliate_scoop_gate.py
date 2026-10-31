"""Fail closed: affiliated-party filings cannot become external-customer scoops.

A public issuer filing itself is newsworthy context, but a new-contract
headline that omits the subsidiary counterparty misstates its evidence.
This module only identifies explicit issuer metadata, not corporate strategy.
"""
import re
from urllib.parse import urlsplit,parse_qs

RECEIPT=re.compile(r"20\d{12}\Z")
AFFILIATED={"자회사","종속회사","계열회사","관계회사","특수관계인","특수관계회사"}

def exact_dart_source(receipt,url):
    if not isinstance(receipt,str) or not RECEIPT.fullmatch(receipt):
        return False
    if not isinstance(url,str):return False
    try:
        u=urlsplit(url)
        return (u.scheme=="https" and u.netloc=="dart.fss.or.kr"
                and u.path=="/dsaf001/main.do" and
                parse_qs(u.query)=={"rcpNo":[receipt]})
    except ValueError:
        return False

def review_hold(filing,monitor):
    """Return explicit public-filing review status, or None.

    A related-party equity notice may still be material but is never an
    externally confirmed new product/contract scoop from its title alone.
    """
    if not isinstance(filing,dict):return None
    report=str(filing.get("reportName") or "").replace(" ","")
    company=filing.get("corpName")
    receipt=filing.get("receiptNo")
    url=filing.get("url")
    if not company or not exact_dart_source(receipt,url):
        return None
    if "특수관계인에대한출자" in report:
        return {
            "reason":"related_party_equity_not_new_external_business",
            "whatVerified":"특수관계인에 대한 출자 공시 접수",
            "notVerified":"신규 시장 진입·대외 매출·실제 출자금 납입·미보도",
            "sourceUrl":url,
            "counterparty":None
        }
    # The DART *form name* explicitly states this is a goods/services
    # transaction with a company in the same large-business group. A change
    # filing is evidence of the issuer's stated related-party reporting change,
    # not a new third-party customer/order or a new commercial activity.
    # The initial filing of the same form is the same kind of evidence (10-31 운영: GS칼텍스
    # '동일인등출자계열회사와의상품ㆍ용역거래', 매출 대비 0.02~0.03%가 '단독 유력' 87점으로 올랐다).
    if ("동일인등출자계열회사와의상품" in report and
        ("용역거래" in report or "용역" in report)):
        changed="변경" in report or "정정" in report
        return {
            "reason":"related_party_goods_services_change_not_external_customer",
            "whatVerified":"동일인 등 출자계열회사와의 상품·용역거래"+(" 변경" if changed else "")+" 공시 접수",
            "notVerified":"그룹 외부 신규 고객·실제 신규 매출·원거래 대비 금액 증감·미보도",
            "sourceUrl":url,
            "counterparty":None
        }
    if "단일판매ㆍ공급계약체결" not in report:
        return None
    if not isinstance(monitor,dict) or monitor.get("status")!="industry_beat_official_receipt_review":
        return None
    # Cross-check exact document identity; other company's similar name is unsafe.
    for row in (monitor.get("records") or [])[:300]:
        if not isinstance(row,dict):continue
        if (row.get("receiptNo")!=receipt or
            row.get("company")!=company or
            row.get("sourceUrl")!=url or
            row.get("status")!="official_document_read" or
            row.get("detailStatus")!="official_document_read" or
            row.get("isCorrection") is not False or
            row.get("documentFieldExtractionStatus")!="official_table_terms_not_business_effect"):
            continue
        fields=row.get("observedFields") or {}
        evidence=row.get("observedFieldEvidence") or {}
        if not isinstance(fields,dict) or not isinstance(evidence,dict):continue
        relation=str(fields.get("counterparty_relationship") or "").strip()
        counterparty=str(fields.get("counterparty") or "").strip()
        x=evidence.get("counterparty_relationship") or {}
        if not isinstance(x,dict):continue
        if (not relation or not counterparty or
            x.get("basis")!="same_official_table_row" or
            x.get("sourceLabel") not in ("- 회사와의 관계","회사와의 관계") or
            relation not in AFFILIATED):
            continue
        return {
            "reason":"official_contract_counterparty_is_affiliate",
            "whatVerified":"공식 DART 원문 기재 계약상대방 "+counterparty+
                          " / 관계 "+relation,
            "notVerified":"외부 신규 고객 수주·최종 고객 공급·신규 외부 매출 인식",
            "sourceUrl":url,
            "counterparty":counterparty
        }
    return None
