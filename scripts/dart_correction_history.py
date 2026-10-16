"""Bounded historic DART amendment candidate + previously indexed news audit.

This is a REPORTER RESEARCH queue, not a contract-lineage conclusion.
Candidates are prior documents found by same issuer, event type and first-
submission date in issuer's official list. That does not prove the same deal.
Matching text likewise cannot prove identity or exclusivity.

This module never retrieves article full text, guesses receipt numbers,
calculates changed money, or upgrades an issuer-only statement into a verified
original-to-current comparison.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from dart_lineage import (event_type, has_correction, issuer_table_evidence,
                          explicit_origin_id, source_link, tabular_fields,
                          valid_receipt, zip_documents)
from official_event_triage import dart_receipt_link

KST=timezone(timedelta(hours=9))
CANDIDATE_MAX=2
RUN_DOCUMENT_MAX=8
TRUSTED_CANDIDATE_STATUS="같은 날짜의 후보일 뿐 동일 사건 미검증"
PLACEHOLDERS=frozenset({"", "-", "미정", "미기재", "해당없음", "비공개"})

def textkey(value):
    return re.sub(r"\s+", "", str(value or "")).replace(",", "").replace("ㆍ","·")

def current_field(change):
    label=textkey(change.get("fieldLabel"))
    if not isinstance(label,str):
        return None
    if "계약금액" in label:return "contract_amount"
    if "투자금액" in label:return "investment_amount"
    if "계약기간" in label and "종료일" in label:return "contract_end"
    if "계약기간" in label and "시작일" in label:return "contract_start"
    if "생산재개" in label and "예정" in label:return "production_restart"
    if "계약상대" in label:return "counterparty"
    return None

def trustworthy_candidate(row, candidate):
    if not isinstance(candidate,dict) or not isinstance(row,dict):return False
    receipt=candidate.get("receiptNo")
    day=candidate.get("date")
    if (not valid_receipt(receipt) or not isinstance(day,str)
        or not re.fullmatch(r"20\d{6}",day)
        or day!=receipt[:8] or day>=row.get("published","")
        or candidate.get("status")!=TRUSTED_CANDIDATE_STATUS
        or not dart_receipt_link(receipt,candidate.get("url"))
        or event_type(candidate.get("report",""))!=row.get("category")
        or receipt==row.get("receiptNo")):
        return False
    return True

def candidate_issuer_proof(row,candidate,documents):
    """Compare the *literal* prior candidate's values with current before.

    The dated candidate is NOT linked to the present amended contract.
    """
    if not isinstance(documents,list) or not documents:
        raise ValueError("prior_document_missing")
    current=row.get("issuerCorrectionTable") or {}
    current_changes=current.get("changes") or []
    if has_correction(candidate.get("report","")):
        previous=issuer_table_evidence(documents,candidate["url"])
        prior_kind="prior_amendment_issuer_table"
        prior_after=[]
        for a in previous["changes"]:
            prior_after.append((current_field(a),a.get("after"),a.get("fieldLabel"),
                                a.get("before")))
    else:
        # Standalone, explicit source table terms in an independently fetched
        # prior filing; not an assertion of a related contract.
        previous={"status":"historical_full_document_terms"}
        terms=tabular_fields(documents)
        prior_kind="prior_filing_official_terms"
        prior_after=[(key,value,key,None) for key,value in terms.items()]
    observations=[]
    for nowrow in current_changes[:8]:
        if (nowrow.get("basis")!="issuer_reported_amendment_table_only"
            or nowrow.get("commercialEffectVerified") is not False
            or not dart_receipt_link(row["receiptNo"],nowrow.get("amendedSourceUrl"))):
            continue
        key=current_field(nowrow)
        before=str(nowrow.get("before") or "")
        if not key or textkey(before) in PLACEHOLDERS:continue
        for other_key,prior_value,other_label,prior_before in prior_after:
            if other_key!=key or not isinstance(prior_value,str):continue
            if textkey(prior_value) in PLACEHOLDERS:continue
            matches=textkey(prior_value)==textkey(before)
            observations.append({
                "field":key,"currentAmendmentField":nowrow.get("fieldLabel"),
                "currentIssuerSaidBefore":before,
                "priorCandidatePublishedValue":prior_value,
                "priorCandidateSaidBefore":prior_before,
                "currentIssuerSaidAfter":str(nowrow.get("after") or "")[:220],
                "priorCandidateField":other_label,
                "literalValuesMatch":matches,
                "sameContractVerified":False,
                "previouslyReportedInMediaVerified":False,
                "contractEffectVerified":False,
                "basis":"unlinked_same_issuer_event_type_date_candidate_only"
            })
    prior_reference=(explicit_origin_id(documents,candidate["receiptNo"])
                     if has_correction(candidate.get("report",""))
                     else {"status":"not_an_amendment","receiptNo":None})
    candidate_origin=prior_reference.get("receiptNo")
    if candidate_origin is not None and (
            not valid_receipt(candidate_origin)
            or candidate_origin==candidate["receiptNo"]
            or candidate_origin[:8]>=candidate["receiptNo"][:8]):
        candidate_origin=None
    return {"priorCandidateKind":prior_kind,
            "priorCandidateTableStatus":previous.get("status"),
            "priorCandidateExplicitOriginReferenceStatus":(
                "prior_candidate_mentions_earlier_receipt_not_current_linkage"
                if candidate_origin else prior_reference.get("status")),
            "priorCandidateExplicitOriginReceipt":candidate_origin,
            "priorCandidateExplicitOriginVerifiedInIssuerList":False,
            "currentAmendmentLinkedToThisOrigin":False,
            "priorIssuerDeclaredRevisions":([
                {"fieldLabel":v["fieldLabel"],"before":v["before"],
                 "after":v["after"],"basis":"issuer_reported_amendment_table_only",
                 "independentCurrentLinkageVerified":False}
                for v in previous.get("changes",[])[:6]]
                if prior_kind=="prior_amendment_issuer_table" else []),
            "priorDocumentRetrieved":True,
            "unlinkedComparisons":observations[:12],
            "matchingTextRows":sum(x["literalValuesMatch"] for x in observations),
            "conflictingTextRows":sum(not x["literalValuesMatch"] for x in observations)}

def press_index_clues(item,news):
    if not isinstance(news,dict) or news.get("receiptNo")!=item.get("receiptNo"):
        return {"status":"missing_or_mismatched_prior_press_snapshot",
                "olderIndexedArticles":[],"coverageOfSameRevisionVerified":False,
                "articleFulltextRead":False}
    if news.get("pressSearchCompleted") is not True:
        state="partial_or_unsearched_index"
    else:
        state="index_checked_not_fulltext"
    correction_day=item["published"]
    seen=set()
    out=[]
    for group in news.get("pressSearchQueries",[]) or []:
        if not isinstance(group,dict) or group.get("status")!="hits":continue
        for a in group.get("articles",[]) or []:
            if not isinstance(a,dict):continue
            uri=a.get("url")
            published=a.get("publishedAt")
            if not isinstance(uri,str) or not uri.startswith("https://news.google.com/"):
                continue
            try:
                t=datetime.fromisoformat(str(published))
                if t.utcoffset() is None or t.astimezone(KST).strftime("%Y%m%d")>=correction_day:
                    continue
            except (ValueError,TypeError):
                continue
            if uri in seen:continue
            seen.add(uri)
            out.append({"title":str(a.get("title") or "")[:200],
                        "url":uri,"indexedPublishedAt":published,
                        "sameRevisionVerified":False,
                        "sameContractVerified":False,
                        "originalArticleFulltextRead":False})
    return {"status":state,"olderIndexedArticles":out[:5],
            "coverageOfSameRevisionVerified":False,
            "articleFulltextRead":False}

def examine(row, news, *,key,fetch_documents=zip_documents, remaining_calls=2):
    if not isinstance(row,dict) or row.get("isCorrection") is not True:
        raise ValueError("only_corrections")
    receipt=row.get("receiptNo")
    if (not valid_receipt(receipt)
        or not dart_receipt_link(receipt,row.get("sourceUrl"))
        or row.get("published")!=receipt[:8]):
        raise ValueError("unverified_current_dart_identity")
    candidates=row.get("unverifiedSameDateCandidates")
    candidates=candidates if isinstance(candidates,list) else []
    ordered=[]
    invalid=0
    for c in candidates[:10]:
        if trustworthy_candidate(row,c):
            if c["receiptNo"] not in {x["receiptNo"] for x in ordered}:
                ordered.append(c)
        else:
            invalid+=1
    ordered=ordered[:CANDIDATE_MAX]
    histories=[]
    used=0
    for candidate in ordered:
        result={
            "receiptNo":candidate["receiptNo"],
            "officialDate":candidate["date"],
            "reportTitle":str(candidate.get("report") or "")[:140],
            "sourceUrl":candidate["url"],
            "relationshipStatus":"UNLINKED_same_company_category_reference_date",
            "sameContractVerified":False,
            "priorDocumentRetrieved":False,
            "matchingTextRows":0,"conflictingTextRows":0,
            "unlinkedComparisons":[]
        }
        if not key:
            result["status"]="not_checked_without_DART_key"
        elif used>=remaining_calls:
            result["status"]="not_checked_bounded_limit"
        else:
            used+=1
            try:
                docs=fetch_documents(key,candidate["receiptNo"])
                comparison=candidate_issuer_proof(row,candidate,docs)
                result.update(comparison)
                result["status"]="previous_candidate_official_document_inspected"
            except (RuntimeError,ValueError,OSError,TimeoutError,TypeError) as exc:
                result["status"]="prior_candidate_document_unavailable"
                result["errorType"]=type(exc).__name__
        histories.append(result)
    article_clues=press_index_clues(row,news)
    editorial=("previous_candidate_values_review_only" if
               any(h["matchingTextRows"] or h["conflictingTextRows"] for h in histories)
               else "candidate_filings_no_comparable_values" if histories
               else "no_verified_prior_event_candidate")
    return {
        "id":"DART:"+receipt,
        "receiptNo":receipt,"company":row.get("company"),
        "officialDate":row["published"],
        "category":row.get("category"),
        "sourceUrl":row["sourceUrl"],
        "referenceDateFromCorrection":row.get("unverifiedSameDateCandidates",[{}])[0].get("date")
              if row.get("unverifiedSameDateCandidates") else None,
        "historyScope":"official_same_issuer_event_type_on_filing_reference_date_ONLY",
        "linkageVerified":False,
        "olderOfficialCandidateCount":len(histories),
        "candidateCountInvalidOrRejected":invalid,
        "retrievalsAttempted":used,
        "priorOfficialCandidateDocuments":histories,
        "pressEvidence":article_clues,
        "editorialStatus":editorial,
        "revisionFirstReportedAfterPreviousCoverageVerified":False,
        "realCommercialImpactVerified":False,
        "confirmedExclusive":False,
        "approvedForPitch":False,
        "nextVerification":[
            "해당 회사·공시 유형의 다른 문서는 동일 계약이 아닐 수 있으므로 원공시 접수번호·동일 계약명·정정 근거를 먼저 확인",
            "정정문이 밝힌 전후 금액·기간이 과거 어느 정정 시점의 기재인지 공시 이력 원문으로 검증",
            "색인 기사 후보의 전문을 읽어 이번 변경 내용까지 기보도됐는지 확인",
            "실제 발생한 계약조건·납품 실적·기업 영향에 대해 홍보팀이 확인 가능한 공개 사실만 질문"
        ]
    }

def build(ledger,review,*,now=None,key="",fetch_documents=zip_documents):
    now=now or datetime.now(KST)
    if now.utcoffset() is None:raise ValueError("timezone_required")
    if (not isinstance(ledger,dict) or not isinstance(review,dict)
        or not isinstance(ledger.get("items"),list)
        or not isinstance(review.get("items"),list)
        or review.get("dartSourceGeneratedAt")!=ledger.get("generatedAt")
        or review.get("confirmedScoops")!=0
        or review.get("approvedArticles")!=0):
        raise ValueError("source_provenance_mismatch")
    refs={}
    for x in review["items"]:
        if isinstance(x,dict) and valid_receipt(x.get("receiptNo")):
            refs[x["receiptNo"]]=x
    remaining=RUN_DOCUMENT_MAX
    records=[]
    for row in ledger["items"]:
        if not isinstance(row,dict) or not row.get("isCorrection"):continue
        if row.get("receiptNo") not in refs:
            raise ValueError("missing_news_review_for_correction")
        x=examine(row,refs[row["receiptNo"]],key=key,fetch_documents=fetch_documents,
                  remaining_calls=min(CANDIDATE_MAX,remaining))
        remaining-=x["retrievalsAttempted"]
        records.append(x)
    return {
        "generatedAt":now.astimezone(KST).isoformat(timespec="seconds"),
        "dartSourceGeneratedAt":ledger["generatedAt"],
        "newsIndexSourceGeneratedAt":review["generatedAt"],
        "status":"bounded_unlinked_correction_history_for_reporter_review",
        "corrections":len(records),
        "totalHistoricalCandidateDocs":sum(r["olderOfficialCandidateCount"] for r in records),
        "historicalDocumentsRetrieved":sum(
            int(p["priorDocumentRetrieved"]) for r in records
            for p in r["priorOfficialCandidateDocuments"]),
        "requestBound":RUN_DOCUMENT_MAX,
        "requestsAttempted":RUN_DOCUMENT_MAX-remaining,
        "verifiedSameContractHistory":0,
        "confirmedScoops":0,
        "approvedArticles":0,
        "limitations":"Past same-company/type/date filings are UNLINKED candidates, not contract continuity. Matching amounts are not legal identity. Google News indexes do not constitute article fulltext/same-revision prior reporting proof. All past corrections remain published, not current scoops.",
        "items":records
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--ledger",default="digests/recent_contracts_latest.json")
    p.add_argument("--news",default="digests/dart_contract_followup_latest.json")
    p.add_argument("--output",default="digests/dart_correction_history_latest.json")
    p.add_argument("--offline",action="store_true")
    a=p.parse_args()
    read=lambda path:json.loads(Path(path).read_text(encoding="utf-8"))
    secret="" if a.offline else os.getenv("DART_API_KEY","").strip()
    result=build(read(a.ledger),read(a.news),key=secret)
    file=Path(a.output);file.parent.mkdir(parents=True,exist_ok=True)
    temp=file.with_suffix(".json.tmp")
    temp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    temp.replace(file)
    print("Prior DART correction candidates",result["totalHistoricalCandidateDocs"],
          "official documents read",result["historicalDocumentsRetrieved"],
          "within",result["requestsAttempted"],"/",result["requestBound"],
          "confirmed same contracts 0, scoops 0")

if __name__=="__main__":main()
