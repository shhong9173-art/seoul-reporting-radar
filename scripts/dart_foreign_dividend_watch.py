"""Find named foreign subsidiary dividend *evidence* in real DART note tables.

This catches material overlooked by the consolidated-only peer comparison.
The same table must name the foreign entity and refer to dividends. Numbers
are excerpted UNINTERPRETED: cash received, income recognized, entitlement,
and year of earnings must be verified separately. Foreign registries are NOT
connected here; do not auto-claim 2.6 trillion won of completed remittances.
"""
from __future__ import annotations
import io
import json
import re
import os
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

from business_content import api_bytes, plain
from dart_numeric_extractor import decode_web_bytes

KST = timezone(timedelta(hours=9))
TABLE = re.compile(r"<table\b[^>]*>[\s\S]*?</table>", re.I)
KEYWORDS = {
    "현대자동차":("HYUNDAI MOTOR MANUFACTURING CZECH","HYUNDAI MOTOR MANUFACTURING CZECH S.R.O.","HMMC","체코생산법인"),
    "기아":("KIA SLOVAKIA","KIA MOTORS SLOVAKIA","KASK","슬로바키아생산법인")
}
DIVIDEND = re.compile(r"배당금|배당수익|배당액|dividend", re.I)
VALID_RECEIPT = re.compile(r"^20\d{12}$")
MAX_DOC = 55_000_000


def matches_foreign_entity(text, company):
    normalized = re.sub(r"\s+"," ",text).upper()
    return any(term in normalized for term in KEYWORDS[company])


def extract_tables(markup,company,receipt):
    out=[]
    for match in TABLE.finditer(markup):
        table=plain(match.group(0))
        # Do not join unrelated document-wide keywords to a financial table.
        if not matches_foreign_entity(table, company):
            continue
        heading=plain(markup[max(0,match.start()-450):match.start()])
        if not DIVIDEND.search(table) and not DIVIDEND.search(heading[-150:]):
            continue
        # Prevent a company name only in note header from implying amount.
        out.append({
            "company":company,
            "receiptNo":receipt,
            "filingUrl":"https://dart.fss.or.kr/dsaf001/main.do?rcpNo="+receipt,
            "tableExcerpt":table[:1400],
            "context":heading[-220:],
            "sourceScope":"same named subsidiary in dividend-related DART note table",
            "amountParsed":False,
            "cashReceiptVerified":False,
            "historicalNetIncomeCompared":False,
            "foreignRegistryVerified":False,
            "mediaCoverageVerified":False,
            "scoopConfirmed":False,
            "verify":[
                "Identify separate versus consolidated basis, period and KRW/EUR units",
                "Match column/row for exact subsidiary; check dividend income vs dividend receivable vs actual cash",
                "Compare 2025/2026 payout against audited Czech/Slovak legal-entity reports",
                "Identify profit year, accumulated retained earnings and board resolution date",
                "Check Korean press and local corporate-register articles for prior coverage"
            ]})
        if len(out)>=8:
            break
    return out



# Explicit issuer accounting wording is materially stronger than a near-by
# dividend word. Do NOT translate it into a cash remittance.
RECOGNIZED_FROM_ENTITY = re.compile(
    r"(?P<entity>Kia\s+Slovakia\s+s\.?\s*r\.?\s*o\.?(?:\s*\(KaSK\))?"
    r"|Hyundai\s+Motor\s+Manufacturing\s+Czech(?:\s+s\.?\s*r\.?\s*o\.?)?)"
    r"\s*로부터\s*인식한\s*"
    r"(?P<amount>\d{1,3}(?:,\d{3})+|\d{1,14})\s*백만원",
    re.I
)


def exact_dividend_income_recognition(visible, company, receipt):
    """DART issuer's explicit individual entity dividend income recognition.

    Require 'dividend income' and correct period in the immediate sentence
    BEFORE the named foreign entity; do not join other headings or total rows.
    """
    if company not in KEYWORDS or not isinstance(visible,str):
        return []
    matches=[]
    for m in RECOGNIZED_FROM_ENTITY.finditer(visible):
        entity=m.group("entity").strip()
        if not matches_foreign_entity(entity,company):
            continue
        amount=m.group("amount")
        if not amount.replace(",","").isdigit():
            continue
        # Korean notes: '당반기 배당금수익은 Kia Slovakia ...로부터 인식한'
        # A different unrelated table-heading's income label is not enough.
        prefix=visible[max(0,m.start()-190):m.start()]
        marker=list(re.finditer(r"(?:당반기|전반기|당기|전기)\s*배당금수익(?:은|에는|으로)?",prefix))
        if not marker:
            continue
        near=prefix[marker[-1].start():]
        if len(near)>145:
            continue
        scope=marker[-1].group(0)
        period=("current" if scope.startswith(("당반기","당기"))
                else "previous")
        # Require one recognized entity + amount expression without an
        # intervening sentence boundary; only official exact phrase captured.
        statement=visible[max(0,m.start()-min(85,len(prefix))):m.end()+28]
        matches.append({
          "company":company,"receiptNo":receipt,
          "filingUrl":"https://dart.fss.or.kr/dsaf001/main.do?rcpNo="+receipt,
          "namedEntity":entity,
          "accountingLine":"배당금수익",
          "issuerNamedRecognitionAmount":amount,
          "issuerUnit":"백만원",
          "issuerRecognizedPeriod":period,
          "recognitionPhrase":visible[m.start():m.end()],
          "context":statement[:280],
          "sourceScope":"issuer_explicit_named_entity_recognized_dividend_income",
          "evidenceTier":"exact_issuer_recognized_dividend_income",
          "amountParsed":True,
          "cashReceiptVerified":False,
          "separateFinancialStatementsVerified":False,
          "foreignRegistryVerified":False,
          "historicalNetIncomeCompared":False,
          "mediaCoverageVerified":False,
          "scoopConfirmed":False,
          "verify":[
            "Confirm issuer's note uses separate vs consolidated basis and exact accounting period",
            "Verify dividend recognition rather than actual cash receipt using issuer filings and public cash-flow materials",
            "Read Czech/Slovak legal-entity annual accounts or resolutions for distribution period and retained earnings",
            "Compare first publication date and prior Korean/local-media articles about this precise dividend",
            "Ask issuer PR only published figures, accounting line, and confirmation of public documents; not private transfer strategy"
          ]
        })
        if len(matches)>=8:break
    if not matches:return []
    by_amount={}
    for row in matches:
        k=(row["issuerRecognizedPeriod"],re.sub(r"\s+","",row["namedEntity"]).lower())
        by_amount.setdefault(k,set()).add(row["issuerNamedRecognitionAmount"])
    conflicting={k for k,v in by_amount.items() if len(v)>1}
    clean=[];seen=set()
    for row in matches:
        k=(row["issuerRecognizedPeriod"],re.sub(r"\s+","",row["namedEntity"]).lower())
        if k in conflicting or (k,row["issuerNamedRecognitionAmount"]) in seen:
            continue
        seen.add((k,row["issuerNamedRecognitionAmount"]))
        clean.append(row)
    return clean[:8]


def document_tables(key,receipt,company,fetch=api_bytes,diagnostic=None):
    if not key or company not in KEYWORDS or not VALID_RECEIPT.fullmatch(str(receipt)):
        raise ValueError("missing valid corporate filing")
    url="https://opendart.fss.or.kr/api/document.xml?"+urlencode({"crtfc_key":key,"rcept_no":receipt})
    payload=fetch(url)
    if len(payload)>35_000_000 or not zipfile.is_zipfile(io.BytesIO(payload)):
        raise ValueError("unverified or oversized OpenDART document ZIP")
    hits=[]
    diagnostic = diagnostic if isinstance(diagnostic,dict) else {}
    diagnostic["documentsChecked"]=0
    diagnostic["entityMentions"]=0
    diagnostic["dividendMentions"]=0
    diagnostic["nearestEntityContext"]=""
    diagnostic["entityPatternsSearched"]=list(KEYWORDS[company])
    with zipfile.ZipFile(io.BytesIO(payload)) as arc:
        info=arc.infolist()
        if len(info)>80 or sum(x.file_size for x in info)>85_000_000:
            raise ValueError("oversized DART document")
        for entry in info:
            if entry.is_dir() or not entry.filename.lower().endswith((".xml",".htm",".html")):
                continue
            if entry.file_size>MAX_DOC:
                raise ValueError("oversized DART part")
            decoded=decode_web_bytes(arc.read(entry))
            diagnostic["documentsChecked"]+=1
            hits.extend(extract_tables(decoded,company,receipt))
            # An issuer's report may place the entity in the narrative preceding
            # a different financial table. Track this explicitly as weaker
            # proximity evidence; never parse an amount from it.
            visible=plain(decoded)
            # Look for a legal entity and issuer-recognized dividend income in
            # ONE explicit sentence. Retain only stronger evidence when found.
            exact=exact_dividend_income_recognition(visible,company,receipt)
            if exact:
                hits=[x for x in hits if x.get("evidenceTier")!="low_confidence_proximity"]
                hits.extend(exact)
            normalized=re.sub(r"\\s+"," ",visible).upper()
            aliases=KEYWORDS[company]
            positions=sorted(set(p for alias in aliases for p in
                                 [m.start() for m in re.finditer(re.escape(alias),normalized)]))
            diagnostic["entityMentions"]+=len(positions)
            diagnostic["dividendMentions"]+=len(DIVIDEND.findall(visible))
            for pos in positions[:25]:
                segment=visible[max(0,pos-500):min(len(visible),pos+900)]
                if not diagnostic["nearestEntityContext"]:
                    diagnostic["nearestEntityContext"]=segment[:360]
                if hits or not DIVIDEND.search(segment):
                    continue
                hits.append({
                    "company":company,"receiptNo":receipt,
                    "filingUrl":"https://dart.fss.or.kr/dsaf001/main.do?rcpNo="+receipt,
                    "tableExcerpt":segment[:1000],"context":"표 행 미대조 · 같은 주석 주변의 배당 키워드",
                    "sourceScope":"text_proximity_only_not_same_verified_table",
                    "evidenceTier":"low_confidence_proximity",
                    "amountParsed":False,"cashReceiptVerified":False,
                    "historicalNetIncomeCompared":False,"foreignRegistryVerified":False,
                    "mediaCoverageVerified":False,"scoopConfirmed":False,
                    "verify":["Confirm exact table row/column and subsidiary name in DART source",
                              "Distinguish dividend income, board resolution, and cash receipt",
                              "Compare with foreign legal-entity registry and prior press"]})
                break
    return hits[:8]


def build(snapshot,key,fetch=api_bytes,now=None):
    now=now or datetime.now(KST)
    companies=snapshot.get("companies",[]) if isinstance(snapshot,dict) else []
    relevant={r.get("company"):r for r in companies if isinstance(r,dict) and r.get("company") in KEYWORDS}
    states=[];leads=[]
    for company in KEYWORDS:
        record=relevant.get(company,{})
        curr=record.get("current") or {}
        previous=record.get("priorSamePeriod") or {}
        for label,row in (("current",curr),("previous_same_period",previous)):
            receipt=row.get("receiptNo")
            if not VALID_RECEIPT.fullmatch(str(receipt or "")):
                states.append({"company":company,"period":label,"status":"no_verified_receipt"})
                continue
            if not key:
                states.append({"company":company,"period":label,"status":"dart_api_key_unset","receiptNo":receipt})
                continue
            try:
                diagnostic={}
                notes=document_tables(key,receipt,company,fetch=fetch,diagnostic=diagnostic)
                states.append({"company":company,"period":label,"status":"checked",
                               "receiptNo":receipt,"candidateTables":len(notes),
                               "diagnostics":diagnostic})
                for n in notes:
                    n["period"]=label
                    leads.append(n)
            except (OSError,RuntimeError,ValueError,zipfile.BadZipFile) as exc:
                states.append({"company":company,"period":label,"status":"source_error",
                               "receiptNo":receipt,"errorType":type(exc).__name__})
    return {"generatedAt":now.astimezone(KST).isoformat(),
            "source":"OpenDART official original filing note tables",
            "status":"evidence_excerpts_not_verified_dividend_receipts",
            "foreignRegistryStatus":"not_connected",
            "confirmedScoops":0,"sourceChecks":states,"leads":leads}


def main():
    src=Path("digests/recent_business_latest.json")
    if not src.exists():
        raise ValueError("no verified filing metadata")
    record=json.loads(src.read_text(encoding="utf-8"))
    result=build(record,os.environ.get("DART_API_KEY",""))
    if not any(s["status"]=="checked" for s in result["sourceChecks"]):
        raise ValueError("DART dividend notes not successfully checked: preserve old output")
    path=Path("digests/overseas_dividend_evidence_latest.json")
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    temp.replace(path)


if __name__=="__main__":
    main()
