"""Broader industry-beat OpenDART monitoring and evidence-gated changes.

Separate *new official receipts*, issuer-stated amendments, independently
verified original-to-amended values, and differences caused by re-parsing a
same-receipt file. NONE means unreported/exclusive business impact.

Companies without a verified DART corporation code remain visible as
unresolved coverage, not "0 filings".
"""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime,timedelta,timezone
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request,urlopen

from business_content import api_json
from dart_lineage import event_type,has_correction,valid_receipt,source_link
from recent_contracts import document_evidence
from valueup_official_document import is_current_valueup_filing, valueup_document_evidence
from share_cancellation_official_document import cancellation_filing, cancellation_document_evidence
from business_cessation_official_document import business_cessation_filing, business_cessation_document_evidence
from official_event_triage import dart_receipt_link

KST=timezone(timedelta(hours=9))
BEATS={
 "자동차·부품·타이어":(
  "현대자동차","기아","현대모비스","현대위아","HL만도","한국GM",
  "KG모빌리티","르노코리아","한국타이어앤테크놀로지","넥센타이어",
  "금호타이어","한온시스템","에스엘","현대오토에버",
  "메르세데스벤츠코리아","BMW코리아","아우디코리아","폭스바겐코리아","혼다코리아"),
 "철강":("포스코홀딩스","포스코","현대제철","KG스틸","세아홀딩스",
        "세아제강","동국제강","동국씨엠","포스코인터내셔널"),
 "비철":("고려아연","영풍","LS MnM"),
 "전력기기·전선":("HD현대일렉트릭","엘에스일렉트릭","일진전기",
       "효성중공업","대한전선","LS전선","가온전선","LS"),
 "에너지·화학":("두산에너빌리티","한화솔루션","OCI","OCI홀딩스",
       "GS","GS칼텍스","한국전력공사","SK이노베이션","씨에스윈드",
       # 11-01 기자 명시: 석유화학 3·정유(S-Oil·HD현대오일뱅크; SK이노베이션은 이미 있음)
       "LG화학","롯데케미칼","금호석유화학","S-Oil","HD현대오일뱅크")
}
TARGETS={name:group for group,names in BEATS.items() for name in names}
if sum(map(len,BEATS.values()))!=len(TARGETS):
    raise ValueError("DART whitelist has duplicate company name")
CODE=re.compile(r"^\d{8}$")
DAY=re.compile(r"^20\d{6}$")
IMPORTANT=(
 "사업보고서","반기보고서","분기보고서","주요사항보고서",
 "유상증자결정","무상증자결정","영업(잠정)실적",
 "영업실적","타법인주식및출자증권","회사분할결정","합병결정",
 # These are filed primary-document heads, not validated performance facts.
 "기업가치제고계획","주식소각결정",
)
PRIORITY_FIELDS=frozenset(("contract_amount","contract_start","contract_end",
        "investment_amount","production_restart"))
WINDOW_DAYS=30
MAX_PAGES=3
PAGE_SIZE=100
MAX_DETAILS=12


def interesting(title):
    t="".join(str(title or "").split()).replace("[기재정정]","").replace("[첨부정정]","")
    cat=event_type(t)
    if cat:return cat
    for label in IMPORTANT:
        if label in t:return "정기·주요공시"
    return None


def fetch_official_list(key,company,code,start,end,*,get=api_json,max_pages=MAX_PAGES):
    if (not key or company not in TARGETS or not isinstance(code,str)
        or not CODE.fullmatch(code) or not DAY.fullmatch(start)
        or not DAY.fullmatch(end) or start>end):
        raise ValueError("missing_verifiable_issuer_and_period")
    found={}
    total_pages=1
    for page in range(1,max_pages+1):
        address="https://opendart.fss.or.kr/api/list.json?"+urlencode({
            "crtfc_key":key,"corp_code":code,"bgn_de":start,"end_de":end,
            "page_no":page,"page_count":PAGE_SIZE,"last_reprt_at":"N"})
        obj=get(address)
        if not isinstance(obj,dict):raise ValueError("malformed_list_response")
        if obj.get("status")=="013":
            if page!=1:raise ValueError("unexpected_empty_page_after_results")
            return {"records":[],"pagesRead":1,"complete":True,
                    "totalOfficialFilings":0,"status":"checked_no_filings"}
        if obj.get("status")!="000":
            raise RuntimeError("OpenDART list error "+str(obj.get("status","invalid"))[:8])
        if not isinstance(obj.get("list"),list):
            raise ValueError("missing_list_array")
        try:
            total_pages=int(obj.get("total_page",1))
            total_count=int(obj.get("total_count",len(obj["list"])))
        except (ValueError,TypeError) as exc:
            raise ValueError("malformed_count") from exc
        if total_pages<1 or total_count<0 or total_pages>100:
            raise ValueError("unsafe_pagination")
        if total_pages>max_pages:
            # Never claim to have covered the official population.
            return {"records":[],"pagesRead":page,"complete":False,
                    "totalOfficialFilings":total_count,
                    "status":"pagination_over_bound"}
        for entry in obj["list"]:
            if not isinstance(entry,dict) or entry.get("corp_code")!=code:continue
            receipt=str(entry.get("rcept_no") or "")
            dt=str(entry.get("rcept_dt") or "")
            title=str(entry.get("report_nm") or "")
            if not (valid_receipt(receipt) and DAY.fullmatch(dt)
                    and dt==receipt[:8] and start<=dt<=end and title.strip()):
                continue
            kind=interesting(title)
            if not kind:continue
            row={
                "company":company,"beat":TARGETS[company],"corpCode":code,
                "receiptNo":receipt,"published":dt,
                "report":title[:230],"category":kind,
                "isCorrection":has_correction(title) and event_type(title) is not None,
                "sourceUrl":source_link(receipt),"sourceType":"official_list_receipt",
                "originalDocumentVerified":False,
                "companyImpactVerified":False,"scoopConfirmed":False
            }
            if receipt in found and found[receipt]!=row:
                raise ValueError("conflicting_duplicate_official_receipt")
            found[receipt]=row
        if page>=total_pages:
            return {"records":sorted(found.values(),key=lambda x:x["receiptNo"],reverse=True),
                    "pagesRead":page,"complete":True,
                    "totalOfficialFilings":total_count,"status":"checked"}
    raise ValueError("pagination_bounded")


def valid_prior_snapshot(previous):
    return (isinstance(previous,dict)
            and previous.get("status")=="industry_beat_official_receipt_review"
            and isinstance(previous.get("records"),list)
            and isinstance(previous.get("firstSeen"),dict))



_CESSATION_PAIR_TERMS = (
    "reportedBusinessScope", "reportedAffectedSalesWon",
    "reportedRecentSalesWon", "issuerReportedRevenueRatioPct",
    "issuerStatedCessationDate",
)


def _cessation_original_signature(row):
    """Same filed values can indicate overlap, never prove corporate identity."""
    if (not business_cessation_filing(row)
        or row.get("status")!="official_business_cessation_document_review"
        or row.get("sourceError") is True
        or row.get("businessCessationFilingRelation") not in (
            "issuer_business_cessation", "parent_disclosure_of_subsidiary")):
        return None
    proof=row.get("businessCessationPrimarySource")
    if (not isinstance(proof,dict)
        or proof.get("officialXmlOrHtmlBodyRetrieved") is not True
        or not isinstance(proof.get("observedTerms"),dict)):
        return None
    values=[]
    for name in _CESSATION_PAIR_TERMS:
        item=proof["observedTerms"].get(name)
        if (not isinstance(item,dict)
            or item.get("basis")!="same_official_table_row"
            or item.get("operationalShutdownVerified") is not False
            or item.get("independentBusinessEffectVerified") is not False
            or not isinstance(item.get("value"),str)
            or not item["value"]):
            return None
        values.append(item["value"])
    return (row["published"], *values)


def mark_possible_parent_subsidiary_cessation_overlap(records):
    """Attach *candidate* matching receipts, not verified one-event merges.

    All five original-cell fields and the filing date must agree. Ambiguous
    matches are excluded. Existing annotations are discarded on every scan,
    preventing old matches from surviving after source corrections or losses.
    """
    matches={}
    for row in records:
        row.pop("possibleOverlappingCessationReceipt",None)
        row.pop("possibleSameUnderlyingCessationEvent",None)
        row.pop("underlyingCessationEventIndependentlyVerified",None)
        signature=_cessation_original_signature(row)
        if signature is not None:
            matches.setdefault(signature,[]).append(row)
    pairs=[]
    for signature,group in matches.items():
        parents=[r for r in group if
            r["businessCessationFilingRelation"]=="parent_disclosure_of_subsidiary"]
        issuers=[r for r in group if
            r["businessCessationFilingRelation"]=="issuer_business_cessation"]
        if len(group)!=2 or len(parents)!=1 or len(issuers)!=1:
            continue
        parent,issuer=parents[0],issuers[0]
        if (parent["company"]==issuer["company"] or
            parent["corpCode"]==issuer["corpCode"] or
            parent["receiptNo"]==issuer["receiptNo"]):
            continue
        for source,other in ((parent,issuer),(issuer,parent)):
            source["possibleOverlappingCessationReceipt"]=other["receiptNo"]
            source["possibleSameUnderlyingCessationEvent"]=True
            source["underlyingCessationEventIndependentlyVerified"]=False
        pairs.append({
            "status":"candidate_parent_subsidiary_same_event_not_verified",
            "parentCompany":parent["company"],
            "parentReceiptNo":parent["receiptNo"],
            "issuerCompany":issuer["company"],
            "issuerReceiptNo":issuer["receiptNo"],
            "filingDate":signature[0],
            "identicalOfficialFields":list(_CESSATION_PAIR_TERMS),
            "parentSubsidiaryLegalIdentityIndependentlyVerified":False,
            "actualBusinessClosureIndependentlyVerified":False,
            "twoSeparateBusinessEventsVerified":False,
            "priorNewsFulltextReviewed":False,
            "scoopConfirmed":False,
            "approvedForPitch":False,
            "warning":"두 DART 공시의 원문 기재값과 날짜가 동일함. 별도 독립 영업중단 2건 아님을 증명하지도, 동일 사건을 법적으로 확정하지도 않음"
        })
    return sorted(pairs,key=lambda x:(x["filingDate"],x["parentReceiptNo"]),reverse=True)


def collect(codes,key,*,now=None,previous=None,query=fetch_official_list,
            detail=document_evidence,valueup_detail=valueup_document_evidence,
            cancellation_detail=cancellation_document_evidence,
            cessation_detail=business_cessation_document_evidence,
            limit=MAX_DETAILS,window_days=WINDOW_DAYS):
    now=now or datetime.now(KST)
    if now.utcoffset() is None or not 1<=limit<=15 or not 3<=window_days<=45:
        raise ValueError("invalid_window_or_detail_limit")
    if not isinstance(codes,dict) or not key:raise ValueError("codes_and_key_required")
    now=now.astimezone(KST)
    start=(now-timedelta(days=window_days-1)).strftime("%Y%m%d")
    end=now.strftime("%Y%m%d")
    prior_ok=valid_prior_snapshot(previous)
    old_records={x["receiptNo"]:x for x in previous.get("records",[])
                 if isinstance(x,dict) and valid_receipt(x.get("receiptNo"))} if prior_ok else {}
    first_seen=dict(previous.get("firstSeen",{})) if prior_ok else {}
    checks=[]
    rows=[]
    for name in TARGETS:
        obj=codes.get(name)
        number=obj.get("corp_code") if isinstance(obj,dict) else None
        if not isinstance(number,str) or not CODE.fullmatch(number):
            checks.append({"company":name,"beat":TARGETS[name],
                           "status":"corp_code_unavailable",
                           "officialRows":None,"relevantRows":None})
            continue
        try:
            got=query(key,name,number,start,end)
            if not isinstance(got,dict) or not isinstance(got.get("records"),list):
                raise ValueError("malformed_official_result")
            if got.get("complete") is not True:
                checks.append({"company":name,"beat":TARGETS[name],
                    "status":"pagination_uninspected","officialRows":got.get("totalOfficialFilings"),
                    "relevantRows":None})
                continue
            validated=[]
            for x in got["records"]:
                if (not isinstance(x,dict) or x.get("corpCode")!=number
                    or x.get("company")!=name or x.get("published")!=x.get("receiptNo","")[:8]
                    or not dart_receipt_link(x.get("receiptNo"),x.get("sourceUrl"))
                    or not start<=x["published"]<=end):
                    raise ValueError("unverifiable_official_list_row")
                validated.append(x)
            rows.extend(validated)
            checks.append({"company":name,"beat":TARGETS[name],"status":"checked",
                           "officialRows":got.get("totalOfficialFilings"),
                           "relevantRows":len(validated),"pagesRead":got.get("pagesRead")})
        except (ValueError,RuntimeError,URLError,TimeoutError,OSError) as exc:
            checks.append({"company":name,"beat":TARGETS[name],"status":"source_error",
                           "errorType":type(exc).__name__,
                           "officialRows":None,"relevantRows":None})
    official_count=len(rows)
    dedup={}
    for row in rows:
        receipt=row["receiptNo"]
        if receipt in dedup and dedup[receipt]!=row:
            raise ValueError("duplicate_receipt_conflict")
        dedup[receipt]=row
    rows=sorted(dedup.values(),key=lambda x:(x["published"],x["receiptNo"]),reverse=True)
    first_run=not prior_ok
    detailed=[]
    by_number={}
    # If full source already parsed in last run, reuse only the SAME receipt
    # source evidence. This is not new corporate activity.
    for row in rows:
        old=old_records.get(row["receiptNo"])
        if (old and old.get("status") in
                ("official_document_read","original_verified","original_not_verified",
                 "official_valueup_document_review",
                 "official_share_cancellation_document_review",
                 "official_business_cessation_document_review")
            and old.get("sourceError") is not True
            and old.get("company")==row["company"]
            and old.get("corpCode")==row["corpCode"]
            and old.get("sourceUrl")==row["sourceUrl"]):
            # Never perpetually cache a failed source read or a now-mismatched
            # issuer/receipt identity. Previously unread rows will be
            # processed on the next scheduled run until the backlog drains.
            by_number[row["receiptNo"]]=old
    # DART contract/correction or issuer-submitted value-up official bodies.
    # An unavailable origin remains retryable and never becomes zero targets.
    def detail_supported(row):
        return (event_type(row["report"]) is not None
                or is_current_valueup_filing(row)
                or cancellation_filing(row)
                or business_cessation_filing(row))

    candidates=[r for r in rows if detail_supported(r)
                and r["receiptNo"] not in by_number]
    selected=candidates[:limit]
    for row in selected:
        try:
            fn=(valueup_detail if is_current_valueup_filing(row) else
                cancellation_detail if cancellation_filing(row) else
                cessation_detail if business_cessation_filing(row) else detail)
            result=fn(dict(row),key)
            if (result.get("receiptNo")!=row["receiptNo"] or
                result.get("company")!=row["company"] or
                result.get("corpCode")!=row["corpCode"]):
                raise ValueError("detail_receipt_or_issuer_mismatch")
            by_number[row["receiptNo"]]=result
        except (ValueError,RuntimeError,URLError,TimeoutError,OSError) as exc:
            by_number[row["receiptNo"]]={**row,"status":"detail_source_error",
                                         "errorType":type(exc).__name__}
    for row in rows:
        receipt=row["receiptNo"]
        item={**row,**by_number.get(receipt,{})}
        item["firstObservedAt"]=first_seen.get(receipt,now.isoformat(timespec="seconds"))
        item["firstObservedThisRun"]=(None if first_run else receipt not in first_seen)
        item["detailTypeSupported"]=detail_supported(row)
        item["detailStatus"]=item.get("status",
            "not_inspected_bounded_detail_budget" if item["detailTypeSupported"]
            else "original_detail_type_unsupported")
        item["independentContractComparisonVerified"]=bool(
            item.get("status")=="original_verified" and
            isinstance(item.get("originalReceiptNo"),str) and
            valid_receipt(item["originalReceiptNo"]) and
            isinstance(item.get("changes"),list))
        item["companyImpactVerified"]=False
        item["scoopConfirmed"]=False
        item["approvedForPitch"]=False
        detailed.append(item)
        first_seen.setdefault(receipt,item["firstObservedAt"])
    candidate_pairs=mark_possible_parent_subsidiary_cessation_overlap(detailed)
    return {
        "generatedAt":now.isoformat(timespec="seconds"),
        "status":"industry_beat_official_receipt_review",
        "windowStart":start,"windowEnd":end,
        "scopeCompanyCount":len(TARGETS),
        "companiesCodeVerified":sum(c["status"]=="checked" for c in checks),
        "companiesUnresolved":sum(c["status"]=="corp_code_unavailable" for c in checks),
        "companiesWithSourceErrors":sum(c["status"] in ("source_error","pagination_uninspected")
                                       for c in checks),
        "sourceComplete":all(c["status"]=="checked" for c in checks),
        "relevantFilings":official_count,
        "detailBound":limit,"detailsAttempted":len(selected),
        "valueupOfficialDocumentAttempts":sum(is_current_valueup_filing(r) for r in selected),
        "shareCancellationDocumentAttempts":sum(cancellation_filing(r) for r in selected),
        "businessCessationDocumentAttempts":sum(business_cessation_filing(r) for r in selected),
        "businessCessationDocumentReads":sum(r.get("status")=="official_business_cessation_document_review" for r in detailed),
        "businessCessationDocumentUnavailable":sum(r.get("status")=="business_cessation_document_unavailable" for r in detailed),
        "possibleParentSubsidiaryCessationOverlapCount":len(candidate_pairs),
        "possibleParentSubsidiaryCessationOverlapReviews":candidate_pairs[:15],
        "shareCancellationDocumentReads":sum(r.get("status")=="official_share_cancellation_document_review" for r in detailed),
        "shareCancellationDocumentUnavailable":sum(r.get("status")=="share_cancellation_document_unavailable" for r in detailed),
        "valueupOfficialDocumentReads":sum(
            r.get("status")=="official_valueup_document_review" for r in detailed),
        "valueupOfficialDocumentUnavailable":sum(
            r.get("status")=="valueup_document_unavailable" for r in detailed),
        "detailBacklogQueued":len(candidates),
        "detailNotAttemptedThisRun":max(0,len(candidates)-len(selected)),
        "unsupportedOriginalDetailTypes":sum(not detail_supported(r) for r in rows),
        "uninspectedListedDetails":sum(
            r["detailStatus"] in ("original_detail_type_unsupported",
                "not_inspected_bounded_detail_budget","detail_source_error",
                "document_unavailable","valueup_document_unavailable",
                "share_cancellation_document_unavailable",
                "business_cessation_document_unavailable")
            for r in detailed),
        "uninspectedRelevantDetails":sum(
            detail_supported(r)
            and (r["receiptNo"] not in by_number or
                 by_number[r["receiptNo"]].get("sourceError") is True)
            for r in rows),
        "firstRunBaseline":first_run,
        "sourceChecks":checks,"records":detailed,"firstSeen":first_seen,
        "confirmedScoops":0,"approvedArticles":0,
        "warning":"Official list coverage excludes unresolved DART corporation IDs and unavailable/non-DART entities. Uninspected original-document categories are out of parser scope, not a clean zero-source result. Newly OBSERVED official receipts do not prove unreported or novel business events. Filing value changes never prove actual shipments or contract impact."
    }



REPORTABLE_TERMS=(
    "contract_subject","contract_amount","recent_sales","sales_ratio",
    "counterparty","counterparty_relationship","supply_region",
    "contract_start","contract_end","investment_amount","production_restart"
)
AFFILIATE_RELATIONS=frozenset({"자회사","종속회사","계열회사","관계회사"})


CESSATION_FIELDS=frozenset((
    "reportedBusinessScope", "reportedAffectedSalesWon",
    "reportedRecentSalesWon", "issuerReportedRevenueRatioPct",
    "issuerStatedCessationDate"
))


def verified_official_cessation_terms(row):
    """Validated issuer descriptions, not independently verified shutdowns."""
    src=row.get("businessCessationPrimarySource")
    if (row.get("status")!="official_business_cessation_document_review"
        or row.get("sourceError") is True
        or not isinstance(src,dict)
        or src.get("officialXmlOrHtmlBodyRetrieved") is not True
        or not isinstance(src.get("observedTerms"),dict)):
        return {}
    out={}
    for name in CESSATION_FIELDS:
        proof=src["observedTerms"].get(name)
        if (not isinstance(proof,dict)
            or proof.get("basis")!="same_official_table_row"
            or proof.get("operationalShutdownVerified") is not False
            or proof.get("independentBusinessEffectVerified") is not False
            or not isinstance(proof.get("value"),str)
            or not 1<=len(proof["value"])<=140
            or not isinstance(proof.get("officialTableLabel"),str)):
            continue
        out[name]={"value":proof["value"],
                   "officialTableLabel":proof["officialTableLabel"][:100],
                   "basis":"same_official_table_row",
                   "businessEffectVerified":False,
                   "operationalShutdownVerified":False}
    return out


def verified_official_table_terms(row):
    """Exact issuer-filed cell values only, never commercial/business impact."""
    if (row.get("status")!="official_document_read"
        or row.get("sourceError") is True
        or not isinstance(row.get("observedFields"),dict)
        or not isinstance(row.get("observedFieldEvidence"),dict)):
        return {}
    confirmed={}
    for key in REPORTABLE_TERMS:
        value=row["observedFields"].get(key)
        proof=row["observedFieldEvidence"].get(key)
        if (isinstance(value,str) and 0<len(value)<=220
            and isinstance(proof,dict)
            and proof.get("basis")=="same_official_table_row"
            and proof.get("independentBusinessVerification") is False
            and isinstance(proof.get("sourceLabel"),str)
            and proof.get("sourceLabel")
            and proof.get("rowPattern") in (
                "two_cell_explicit_label","three_cell_explicit_label",
                "four_cell_independent_pair","contract_period_rowspan")
            and key not in (row.get("conflictingDocumentFields") or [])):
            confirmed[key]={"value":value,
                            "officialTableLabel":proof["sourceLabel"][:100],
                            "basis":"same_official_table_row",
                            "businessEffectVerified":False}
    return confirmed


def change_review(current,previous=None,*,now=None):
    """Compare exact receipts and verified original references only.

    Different receipt numbers from the same issuer do NOT imply same contract.
    Any identical-receipt extracted-value difference is parsing/source
    consistency investigation, not a new contract.
    """
    now=now or datetime.now(KST)
    if now.utcoffset() is None or not valid_prior_snapshot(current):
        raise ValueError("invalid_current_snapshot")
    previous=previous if valid_prior_snapshot(previous) else None
    old={x["receiptNo"]:x for x in previous["records"]} if previous else {}
    previously_checked={x.get("company"):x.get("status")
        for x in previous.get("sourceChecks",[]) if isinstance(x,dict)} if previous else {}
    currently_checked={x.get("company"):x.get("status")
        for x in current.get("sourceChecks",[]) if isinstance(x,dict)}
    now_day=now.astimezone(KST).date()
    signals=[]
    for row in current["records"]:
        receipt=row["receiptNo"]
        prior=old.get(receipt)
        kind="previously_seen_public_filing"
        cited=[]
        changed_fields=[]
        new_receipt=prior is None
        coverage_new=(new_receipt and
            previously_checked.get(row["company"]) in (
                "corp_code_unavailable","source_error","pagination_uninspected")
            and currently_checked.get(row["company"])=="checked")
        if prior is not None and row.get("observedFields")!=prior.get("observedFields"):
            if row.get("observedFields") or prior.get("observedFields"):
                changed_fields=sorted(set((row.get("observedFields") or {}).keys())
                                      |set((prior.get("observedFields") or {}).keys()))
                # On scheduled backlog catch-up the old snapshot may only
                # contain official list metadata. Extracting a table for the
                # SAME receipt is not a company changing its contract.
                if (not prior.get("observedFields")
                    and row.get("observedFields")
                    and prior.get("detailStatus") in (
                        "not_inspected_bounded_detail_budget",
                        "detail_source_error","document_unavailable",
                        "original_not_verified",None)):
                    kind="same_receipt_first_document_field_recovery"
                else:
                    kind="same_receipt_data_reparse_discrepancy"
        elif (prior is not None
              and prior.get("detailStatus") in (
                  "original_detail_type_unsupported",
                  "not_inspected_bounded_detail_budget",
                  "document_unavailable", "detail_source_error",
                  "business_cessation_document_unavailable")
              and row.get("status")=="official_business_cessation_document_review"
              and verified_official_cessation_terms(row)):
            # Same receipt, newly extracted first-party fields. This is a
            # collector recovery, not a fresh corporate decision or scoop.
            kind="same_receipt_first_cessation_original_recovery"
        elif new_receipt and row.get("isCorrection"):
            source_changes=row.get("changes",[])
            original=row.get("originalReceiptNo")
            if (row.get("independentContractComparisonVerified") is True
                and valid_receipt(original) and dart_receipt_link(original,row.get("originalSourceUrl"))
                and source_changes
                and all(x.get("basis")=="independent_primary_documents" and
                        x.get("needsCompanyConfirmation") is True for x in source_changes)):
                kind="two_official_documents_changed_terms"
                cited=source_changes[:12]
            else:
                issuer=row.get("issuerCorrectionTable") or {}
                values=issuer.get("changes",[])
                if issuer.get("status")=="issuer_table_material_changes_for_review" and isinstance(values,list) and values:
                    kind="issuer_stated_correction_only"
                    cited=[v for v in values if
                        isinstance(v,dict) and
                        v.get("basis")=="issuer_reported_amendment_table_only"
                        and v.get("commercialEffectVerified") is False][:8]
                else:
                    kind="new_observed_correction_unconfirmed_change"
        elif new_receipt:
            kind=("existing_public_filing_from_newly_resolved_issuer"
                  if coverage_new else "newly_observed_public_filing")
        try:
            official_day=datetime.strptime(row["published"],"%Y%m%d").date()
        except (ValueError,TypeError):continue
        recent=0<=(now_day-official_day).days<=2
        if not new_receipt and kind=="previously_seen_public_filing":continue
        terms=verified_official_table_terms(row)
        affiliate=terms.get("counterparty_relationship",{}).get("value") in AFFILIATE_RELATIONS
        cessation_terms=verified_official_cessation_terms(row)
        # Every non-duplicate candidate has exact DART URL from upstream.
        signals.append({
            "company":row["company"],"beat":row["beat"],"receiptNo":receipt,
            "officialDate":row["published"],"sourceUrl":row["sourceUrl"],
            "title":row["report"],"status":kind,
            "recentOfficialDocument":recent,
            "newObservation":(None if current["firstRunBaseline"] else new_receipt),
            "firstObservedBecauseIssuerBecameCollectable":coverage_new,
            "companyInOfficialScope":True,
            "priorReceiptIndependentCompared":kind=="two_official_documents_changed_terms",
            "originalReceiptNo":(row.get("originalReceiptNo")
                        if kind=="two_official_documents_changed_terms" else None),
            "changedTermsForReview":cited,"sourceReparseFieldKeys":changed_fields,
            "reportedOfficialTableTerms":terms,
            "reportedOfficialCessationTerms":cessation_terms,
            "possibleOverlappingCessationReceipt":row.get("possibleOverlappingCessationReceipt"),
            "possibleSameUnderlyingCessationEvent":row.get("possibleSameUnderlyingCessationEvent") is True,
            "underlyingCessationEventIndependentlyVerified":False,
            "businessCessationFilingRelation":(
                row.get("businessCessationFilingRelation")
                if row.get("status")=="official_business_cessation_document_review"
                else None),
            "uniqueUnderlyingBusinessCessationEventsVerified":False,
            "reportedCounterpartyIsAffiliate":affiliate,
            "ultimateExternalCustomerVerified":False,
            "actualShipmentVerified":False,
            "businessImpactVerified":False,
            "priorNewsFulltextChecked":False,
            "scoopConfirmed":False,"approvedForPitch":False,
            "nextCheck":(
             "기존에는 법인 코드/공식 자료 오류로 이 기업을 조회하지 못했으나 이번에 기존 공개자료를 처음 수집함. 공시 자체는 이미 공개됨. 공시일·기보도·실제 산업 영향 별도 확인"
             if coverage_new else
             "이전에 목록만 확인한 같은 공시번호의 표 항목을 처음 추출함: 신규 기업 변화가 아님. 원문 확인 필요"
             if kind=="same_receipt_first_document_field_recovery" else
             "같은 공시 접수번호의 영업정지 원문 기재값을 처음 추출함. 기보도 전문·실제 중단 실행·모자회사 중복 공시 관계 확인(새 사건 아님)"
             if kind=="same_receipt_first_cessation_original_recovery" else
             "두 DART 원문이 동일 사업·금액·비율·일자로 확인된 모자회사 공시 후보. 동일 법인/사건 여부를 공식 원문으로 확인하기 전 2건의 별도 사업 중단으로 집계 금지"
             if row.get("possibleSameUnderlyingCessationEvent") is True else
             "같은 공시번호의 데이터 추출 차이: 공식 원문과 수집기 코드 확인 (기업 변화로 해석 금지)"
             if kind=="same_receipt_data_reparse_discrepancy" else
             "공시 상대방이 관계회사: 외부 최종 고객/납품과 연결 매출 계상·기보도 여부 별도 검증"
             if affiliate else
             "명시된 원공시 및 전후 공시 원문·기보도 기사 전문·실제 기업 영향 확인"
             if row.get("isCorrection") else
             "공식 접수내용/동일 사건 기보도/출입처 실제 변화를 확인")
        })
    signals.sort(key=lambda r:(not r["recentOfficialDocument"],r["officialDate"],
                               r["receiptNo"]),reverse=False)
    # Sort recent first, then newest within group.
    signals.sort(key=lambda r:(not r["recentOfficialDocument"],-int(r["officialDate"]),
                               r["company"],r["receiptNo"]))
    return {
      "generatedAt":now.astimezone(KST).isoformat(timespec="seconds"),
      "sourceGeneratedAt":current["generatedAt"],
      "previousSourceGeneratedAt":previous["generatedAt"] if previous else None,
      "status":"official_receipt_change_review_not_exclusive",
      "baselineOnly":current["firstRunBaseline"] or previous is None,
      "scopedSourcesComplete":current["sourceComplete"],
      "monitoredCompanies":current["scopeCompanyCount"],
      "companiesMissingCode":current["companiesUnresolved"],
      "companiesWithFailures":current["companiesWithSourceErrors"],
      "observedSignals":len(signals),
      "recentOfficialReviewCount":sum(x["recentOfficialDocument"] for x in signals),
      "confirmedScoops":0,"approvedArticles":0,
      "warning":"A new or changed DART receipt is public. Issuer correction statements are NOT independently verified original-to-current contract effects; same-receipt parser changes are not new business developments. All prior-media/operational impact conclusions require separate reporting.",
      "signals":signals[:140]
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--codes",default="dart_corp_codes.json")
    p.add_argument("--source",default="digests/dart_beat_monitor_latest.json")
    p.add_argument("--changes",default="digests/dart_beat_changes_latest.json")
    p.add_argument("--detail-limit",type=int,default=MAX_DETAILS)
    a=p.parse_args()
    key=os.environ.get("DART_API_KEY","").strip()
    if not key:raise SystemExit("DART_API_KEY missing: keep last verified outputs")
    read=lambda x:json.loads(Path(x).read_text(encoding="utf-8"))
    companies=read(a.codes).get("companies",{})
    try:previous=read(a.source)
    except (OSError,ValueError):previous=None
    result=collect(companies,key,previous=previous,limit=a.detail_limit)
    if result["companiesCodeVerified"]==0:
        raise SystemExit("OpenDART no successful company sources: preserve previous snapshots")
    signals=change_review(result,previous=previous)
    for path,data in ((a.source,result),(a.changes,signals)):
        dest=Path(path);dest.parent.mkdir(parents=True,exist_ok=True)
        temp=dest.with_suffix(".tmp")
        temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        temp.replace(dest)
    print("DART beat monitor",result["scopeCompanyCount"],"targets",
          result["companiesCodeVerified"],"checked",
          result["companiesUnresolved"],"missing code",
          result["companiesWithSourceErrors"],"errors",
          result["relevantFilings"],"public receipts",
          signals["recentOfficialReviewCount"],"recent dated reviews, exclusives 0")

if __name__=="__main__":main()
