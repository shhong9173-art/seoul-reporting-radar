"""Bounded, hash-checked Slovak Ministry of Finance RUZ IFRS PDF evidence.

Reads an independently verified accounting entity IČO and 2024/2025
statement/report IDs from the existing official registry JSON. For each
official IFRS report: download its *metadata*, obtain a PDF attachment ID,
verify the government-supplied SHA-256 and original PDF bytes, then index
the pages around dividend/profit words as review clues, never as automated
cash paid, distributable profit, comparable profit or Korean remittance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime,timedelta,timezone
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError

KST=timezone(timedelta(hours=9))
API="https://registeruz.sk/cruz-public/api/uctovny-vykaz?id="
ATTACHMENTS="https://www.registeruz.sk/cruz-public/domain/financialreport/attachment/"
IFRS={2024:(6499422,9718744),2025:(6995571,10298519)}
MAX_PDF=14*1024*1024
MAX_METADATA=350_000
MAX_PAGES=90
MAX_CITATIONS=10
KEYWORDS=re.compile(r"\bdividend(?:s)?\b|\bdividenda\b|\bdividendy\b|\bdividendov\b|"
    r"\bdividendami\b|\bprofit\s+for\s+the\s+year\b|"
    r"\bretained\s+earnings\b|\bnerozdelen[ýy]\s+zisk\b|"
    r"\brozdelenie\s+zisku\b|\bvyplateni[ea]\s+dividend\b",re.I)
HEX=re.compile(r"^[a-f0-9]{64}$")
PDF_ID=re.compile(r"^[1-9]\d{3,11}$")
STATUS="official_slovak_ifrs_pdf_review_clues_not_validated_dividend_transfer"

def get_data(url,max_bytes):
    if url.startswith(API):
        is_json=True
        tail=url[len(API):]
    elif url.startswith(ATTACHMENTS):
        is_json=False
        tail=url[len(ATTACHMENTS):]
    else:
        raise ValueError("only_ruzu_approved_api_or_attachment_url")
    if not PDF_ID.fullmatch(tail):
        raise ValueError("unverified_government_document_identifier")
    req=Request(url,headers={"Accept":"application/json" if is_json else "application/pdf",
                             "User-Agent":"newsroom-primary-document-review/1.0"})
    with urlopen(req,timeout=22) as response:
        b=response.read(max_bytes+1)
        if len(b)>max_bytes:raise ValueError("official_source_over_size_limit")
        return b

def checked_metadata(raw,statement_id,report_id):
    if not isinstance(raw,(bytes,bytearray)) or len(raw)>MAX_METADATA:
        raise ValueError("metadata_invalid")
    obj=json.loads(raw)
    if not isinstance(obj,dict) or obj.get("id")!=report_id or obj.get("idUctovnejZavierky")!=statement_id:
        raise ValueError("not_exact_2024_2025_registered_ifrs_report")
    if obj.get("pristupnostDat") not in ("Verejné","Verejné prílohy"):
        return {"public":False,"attachments":[]}
    files=[]
    for a in obj.get("prilohy",[]) if isinstance(obj.get("prilohy"),list) else []:
        if not isinstance(a,dict):continue
        docid=a.get("id")
        sha=str(a.get("digest") or "").lower()
        claimed=a.get("velkostPrilohy")
        if (not isinstance(docid,int) or not PDF_ID.fullmatch(str(docid))
            or str(a.get("mimeType") or "").lower()!="application/pdf"
            or not HEX.fullmatch(sha)
            or type(claimed) is not int or not 300<=claimed<=MAX_PDF):
            continue
        files.append({
            "attachmentId":docid,"sha256":sha,"byteSize":claimed,
            "mimeType":"application/pdf",
            "pageCountDeclared":a.get("pocetStran"),
            "officialAttachmentUrl":ATTACHMENTS+str(docid),
            "label":str(a.get("meno") or "")[:100]
        })
    return {"public":True,"attachments":files[:3]}

def extract_pages(pdf_bytes):
    if not pdf_bytes.startswith(b"%PDF-"):raise ValueError("not_pdf_payload")
    with tempfile.TemporaryDirectory() as folder:
        name=Path(folder)/"official.pdf"
        name.write_bytes(pdf_bytes)
        # The pdf is untrusted input to a bounded external parser. PDFs are
        # never committed or served by our repository.
        r=subprocess.run(["pdftotext","-f","1","-l",str(MAX_PAGES),
            "-layout","-enc","UTF-8",str(name),"-"],
            capture_output=True,timeout=35,check=False)
    if r.returncode!=0:raise ValueError("pdf_text_not_extractable")
    if len(r.stdout)>4_000_000:raise ValueError("pdf_extracted_text_over_limit")
    return r.stdout.decode("utf-8","replace").split("\f")[:MAX_PAGES]

def page_clues(pages):
    if not isinstance(pages,list):raise ValueError("pdf_pages_missing")
    out=[]
    for page_num,page in enumerate(pages,1):
        if not isinstance(page,str) or not page.strip():continue
        normalized=re.sub(r"\s+"," ",page).strip()
        for m in KEYWORDS.finditer(normalized):
            snippet=normalized[max(0,m.start()-120):m.end()+155].strip()
            if len(snippet)>310:snippet=snippet[:310]
            out.append({
                "page":page_num,"keyword":m.group(0)[:40],
                "sourceTextExcerpt":snippet,
                "containsFinancialAmountValidated":False,
                "cashPaidOrRetainedProfitValidated":False,
                "interpretation":"literal_pdf_keyword_passage_only_requires_manual_note_and_period_review"
            })
            if len(out)>=MAX_CITATIONS:return out
    return out

def source_snapshot_valid(src):
    if not isinstance(src,dict) or src.get("status")!="official_slovak_registry_identity_and_filing_metadata":
        return False
    if src.get("ico")!="35876832" or src.get("companyIdentityVerified") is not True or src.get("officialEntityId")!=244945:
        return False
    if not isinstance(src.get("statements"),list):return False
    return True

def analyze(source,*,now=None,fetch=get_data,pdf_text=extract_pages):
    now=now or datetime.now(KST)
    if now.utcoffset() is None or not source_snapshot_valid(source):
        raise ValueError("unverified_production_issuer_identity")
    r={
        "generatedAt":now.astimezone(KST).isoformat(timespec="seconds"),
        "status":STATUS,"sourceRegistryGeneratedAt":source.get("generatedAt"),
        "company":"Kia Slovakia s. r. o.","ico":"35876832",
        "governmentApi":"https://registeruz.sk/cruz-public/home/api",
        "reports":[],"reportCount":0,"verifiedPdfCount":0,
        "verifiedPageExcerpts":0,"sourceQueriesFailed":0,
        "errors":[],
        "financialFiguresInterpreted":False,
        "dividendDistributionResolutionVerified":False,
        "koreanParentCashReceiptVerified":False,
        "dividendPaymentToParentVerified":False,
        "sameAnglePriorNewsChecked":False,
        "exclusiveConfirmed":False,
        "warning":"Only original publicly filed PDF text passages with official hash verified are indexed. OCR/scanned content may be absent. Even a PDF dividend keyword or amount does not establish distribution resolution, which year earnings financed it, parent cash receipts, or any unreported scoop."
    }
    seen_years=set()
    for item in source["statements"]:
        year=item.get("financialYear") if isinstance(item,dict) else None
        if year not in IFRS or year in seen_years:continue
        stmt,report=IFRS[year]
        if (item.get("statementId")!=stmt or
            report not in item.get("reportIds",[]) or
            item.get("officialIfrsReportDetailUrl")!=
            "https://www.registeruz.sk/cruz-public/domain/financialreport/show/"+str(report) or
            item.get("sameIcoAndLegalNameConfirmed") is not True or
            item.get("profitOrDividendAmountsParsed") is not False):
            continue
        seen_years.add(year)
        row={
            "year":year,"statementId":stmt,"reportId":report,
            "reportDetailUrl":item["officialIfrsReportDetailUrl"],
            "status":"not_requested",
            "pdfReadAndOfficialHashVerified":False,
            "attachmentUrl":None,"sha256":None,"pageClues":[],
            "financialFiguresInterpreted":False,
            "dividendCashRemittanceVerified":False
        }
        try:
            meta=checked_metadata(fetch(API+str(report),MAX_METADATA),stmt,report)
            if not meta["public"]:
                row["status"]="report_not_publicly_accessible_in_api"
            elif not meta["attachments"]:
                row["status"]="official_pdf_attachment_missing_or_hash_unavailable"
            else:
                # Do not select another unrelated or ambiguously multiple PDF.
                if len(meta["attachments"])!=1:
                    row["status"]="multiple_pdf_attachments_require_manual_selection"
                else:
                    info=meta["attachments"][0]
                    pdf=fetch(info["officialAttachmentUrl"],MAX_PDF)
                    if (len(pdf)!=info["byteSize"] or
                        hashlib.sha256(pdf).hexdigest()!=info["sha256"]):
                        raise ValueError("official_pdf_sha256_or_size_mismatch")
                    row["pdfReadAndOfficialHashVerified"]=True
                    row["sha256"]=info["sha256"]
                    row["attachmentUrl"]=info["officialAttachmentUrl"]
                    r["verifiedPdfCount"]+=1
                    try:
                        pages=pdf_text(pdf)
                        row["pageClues"]=page_clues(pages)
                        r["verifiedPageExcerpts"]+=len(row["pageClues"])
                        row["status"]=(
                            "official_pdf_text_passages_for_manual_review"
                            if row["pageClues"] else
                            "verified_pdf_no_indexed_words_not_proof_of_no_dividend")
                    except (OSError,ValueError,TimeoutError,subprocess.TimeoutExpired) as err:
                        row["status"]="verified_pdf_text_not_extractable"
                        row["textErrorType"]=type(err).__name__
        except (ValueError,URLError,HTTPError,OSError,TimeoutError,json.JSONDecodeError) as err:
            row["status"]="official_metadata_or_attachment_error"
            row["errorType"]=type(err).__name__
            r["sourceQueriesFailed"]+=1
            r["errors"].append(type(err).__name__)
        r["reports"].append(row)
    r["reportCount"]=len(r["reports"])
    return r

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--source",default="digests/slovakia_official_accounts_latest.json")
    ap.add_argument("--out",default="digests/slovak_ifrs_primary_pages_latest.json")
    args=ap.parse_args()
    source=json.loads(Path(args.source).read_text(encoding="utf-8"))
    result=analyze(source)
    dest=Path(args.out);dest.parent.mkdir(parents=True,exist_ok=True)
    tmp=dest.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    tmp.replace(dest)
    print("RUZ original IFRS PDFs",result["reportCount"],
          "verified bytes",result["verifiedPdfCount"],
          "manual page clues",result["verifiedPageExcerpts"],
          "cash remittance verified 0")
if __name__=="__main__":main()
