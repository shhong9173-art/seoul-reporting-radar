"""Attach the 48-company official DART monitor to the event-date research queue.

No row is an exclusive lead; failed collection and unknown issuers stay explicit.
Receipt publication date, never discovery time, controls freshness.
"""
import argparse
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

KST = timezone(timedelta(hours=9))
RECEIPT = re.compile(r"20\d{12}\Z")
CORP = re.compile(r"\d{8}\Z")


def _stamp(value):
    try:
        d = datetime.fromisoformat(value)
        return d if d.utcoffset() is not None else None
    except (ValueError, TypeError):
        return None


def _published(value):
    try:
        if isinstance(value, str) and re.fullmatch(r"20\d{6}", value):
            return datetime.strptime(value, "%Y%m%d").date()
    except ValueError:
        pass
    return None


def _receipt_link(receipt, url):
    if not isinstance(receipt, str) or not RECEIPT.fullmatch(receipt):
        return False
    if not isinstance(url, str) or len(url) > 380:
        return False
    try:
        u = urlsplit(url)
        return (u.scheme == "https" and u.hostname == "dart.fss.or.kr"
                and not u.username and not u.password
                and receipt in parse_qs(u.query).get("rcpNo", []))
    except ValueError:
        return False



def evidence_stage(row):
    """What was actually read, not what a newly seen receipt might imply."""
    cessation = row.get("businessCessationPrimarySource")
    if (row.get("status") == "official_business_cessation_document_review"
        and isinstance(cessation, dict)
        and cessation.get("officialXmlOrHtmlBodyRetrieved") is True):
        return ("official_business_cessation_fields_checked"
                if isinstance(cessation.get("observedTerms"), dict)
                and bool(cessation["observedTerms"])
                else "official_business_cessation_text_only_fields_unverified")
    cancellation = row.get("shareCancellationPrimarySource")
    if (row.get("status") == "official_share_cancellation_document_review"
        and isinstance(cancellation, dict)
        and cancellation.get("officialXmlOrHtmlBodyRetrieved") is True):
        return ("official_share_cancellation_fields_checked"
                if isinstance(cancellation.get("observedTerms"), dict)
                and bool(cancellation["observedTerms"])
                else "official_share_cancellation_text_only_fields_unverified")
    valueup = row.get("valueupPrimarySource")
    if isinstance(valueup, dict) and valueup.get("officialXmlOrHtmlBodyRetrieved") is True:
        return ("official_valueup_text_and_attachment_checked"
                if valueup.get("officialAttachmentPdfReviewed") is True
                else "official_valueup_text_only_attachment_unverified")
    if (row.get("status") == "official_document_read"
        and isinstance(row.get("observedFields"), dict)
        and row["observedFields"]):
        return "official_table_filing_fields_checked"
    return "official_receipt_only_original_not_checked"


def merge(queue, beat, *, now=None):
    now = now or datetime.now(KST)
    if now.utcoffset() is None:
        raise ValueError("timezone_required")
    now = now.astimezone(KST)
    if not isinstance(queue, dict) or queue.get("status") != "official_date_triage":
        raise ValueError("unverified_triage")
    required = ("freshOfficialReview", "backgroundReference", "seen", "feedHealth")
    if any(not isinstance(queue.get(x), (dict if x == "seen" else list)) for x in required):
        raise ValueError("malformed_triage")

    out = dict(queue)
    out["freshOfficialReview"] = list(queue["freshOfficialReview"])
    out["backgroundReference"] = list(queue["backgroundReference"])
    out["seen"] = dict(queue["seen"])
    out["feedHealth"] = [dict(x) for x in queue["feedHealth"]
                         if isinstance(x, dict) and x.get("name") != "dart_beat_monitor"]
    checks = beat.get("sourceChecks") if isinstance(beat, dict) else None
    rows = beat.get("records") if isinstance(beat, dict) else None
    scope = beat.get("scopeCompanyCount") if isinstance(beat, dict) else None
    stamp = _stamp(beat.get("generatedAt")) if isinstance(beat, dict) else None
    structurally_valid = (isinstance(checks, list) and isinstance(rows, list)
        and type(scope) is int and scope > 0 and len(checks) == scope
        and isinstance(beat, dict)
        and beat.get("status") == "industry_beat_official_receipt_review"
        and stamp is not None and stamp <= now + timedelta(minutes=10)
        and all(isinstance(x, dict) and isinstance(x.get("company"), str)
                and x["company"].strip() for x in checks)
        and len({x["company"] for x in checks}) == scope
        and all(x.get("status") in
                ("checked", "corp_code_unavailable", "source_error") for x in checks)
    )
    checked = {x["company"] for x in checks if x.get("status") == "checked"} if structurally_valid else set()
    missing = sum(x["status"] == "corp_code_unavailable" for x in checks) if structurally_valid else 0
    failed = sum(x["status"] == "source_error" for x in checks) if structurally_valid else 0
    valid = (structurally_valid
             and beat.get("companiesCodeVerified") == len(checked)
             and beat.get("companiesUnresolved") == missing
             and beat.get("companiesWithSourceErrors") == failed)
    if not valid:
        status = "source_missing_or_malformed"
    elif now - stamp > timedelta(hours=24):
        status = "snapshot_older_than_24h"
    elif failed:
        status = "partial_collection"
    elif missing:
        status = "partial_issuer_coverage"
    else:
        status = "checked_source"
    health = {
        "name": "dart_beat_monitor", "status": status,
        "sourceAt": beat.get("generatedAt") if valid else None,
        "records": len(rows) if valid else None,
        "scopeCompanies": scope if valid else None,
        "checkedCompanies": len(checked) if valid else None,
        "unresolvedCompanies": missing if valid else None,
        "failedCompanies": failed if valid else None,
        "scopeWarning": "Unmapped issuer is not zero filings; first observation is not an exclusive scoop",
    }
    out["feedHealth"].append(health)
    visible = {x.get("id") for x in out["freshOfficialReview"] + out["backgroundReference"]
               if isinstance(x, dict)}
    already_attached = set(queue.get("beatAttachedReceiptIds", [])) if queue.get("beatMergeAlreadyApplied") is True and isinstance(queue.get("beatAttachedReceiptIds"), list) else set()
    attached_this_run = set()
    earliest = now.date() - timedelta(days=2)
    added_recent = added_background = excluded = 0
    if valid:
        for row in rows:
            if not isinstance(row, dict):
                excluded += 1
                continue
            receipt = row.get("receiptNo")
            published = row.get("published")
            dt = _published(published)
            url = row.get("sourceUrl")
            company = row.get("company")
            if (company not in checked or not _receipt_link(receipt, url)
                or not dt or dt > now.date() or receipt[:8] != published
                or not CORP.fullmatch(str(row.get("corpCode") or ""))
                or not isinstance(row.get("report"), str)
                or not row["report"].strip()):
                excluded += 1
                continue
            if row.get("isCorrection") is True:
                # Corrected notices require original comparison; never fresh.
                excluded += 1
                continue
            key = "DART_FILING:" + receipt
            if key in visible or key in already_attached:
                continue
            previous = out["seen"].get(key)
            first_seen = str(previous or row.get("firstObservedAt") or now.isoformat())[:10]
            try:
                date.fromisoformat(first_seen)
            except ValueError:
                first_seen = now.date().isoformat()
            fresh = earliest <= dt <= now.date()
            item = {
                "id": key, "source": "DART_FILING",
                "officialDate": dt.isoformat(), "company": company,
                "headline": company + " · " + str(row.get("category") or "공시")
                            + " · " + row["report"].strip()[:90],
                "officialFact": "공식 DART 공시 접수 확인. 계약 이행·실제 산업 영향 및 단독 여부 미확인",
                "sourceUrl": url, "officialReceiptNo": receipt,
                "verification": "공시 원문·첨부자료·국내 선행보도 전문·회사 공개 사실 답변 대조",
                "classification": "public_official_document_not_a_scoop",
                "evidenceClass": "beat_wide_official_receipt",
                "originalEvidenceStage": evidence_stage(row),
                "sourceSnapshotAt": beat["generatedAt"],
                "originalDocumentFieldsVerified": bool(
                    row.get("status") == "official_document_read"
                    and isinstance(row.get("observedFields"), dict)
                    and row["observedFields"]),
                "companyImpactVerified": False,
                "contractTermsVerified": False,
                "priorMediaCoverageVerified": False,
                "exclusiveConfirmed": False, "approvedForPitch": False,
                "freshArticleConfirmed": False, "correction": False,
                "firstObservedAt": first_seen,
                "firstObservedThisRun": (None if queue.get("firstRunBaseline")
                    else row.get("firstObservedThisRun")
                    if isinstance(row.get("firstObservedThisRun"), bool)
                    else not bool(previous)),
                "publicDocumentAgeDays": (now.date() - dt).days,
                "officialDateInRecentWindow": fresh,
                "editorialBucket": "recent_official_filing_review" if fresh else "published_background",
            }
            shareproof = row.get("shareCancellationPrimarySource")
            if (row.get("status") == "official_share_cancellation_document_review"
                and isinstance(shareproof, dict)
                and shareproof.get("officialXmlOrHtmlBodyRetrieved") is True):
                raw_terms = shareproof.get("observedTerms")
                if isinstance(raw_terms, dict):
                    issuer_terms = {}
                    for name in ("ordinarySharesToCancel", "preferredSharesToCancel",
                                 "scheduledCancellationDate"):
                        term = raw_terms.get(name)
                        if (isinstance(term, dict)
                            and term.get("basis") == "same_official_table_row"
                            and isinstance(term.get("value"), str)
                            and len(term["value"]) <= 20
                            and term.get("completedCancellationVerified") is False):
                            issuer_terms[name] = term["value"]
                    if issuer_terms:
                        item["issuerFiledCancellationTerms"] = issuer_terms
                        item["officialFact"] = (
                            "공식 주식소각결정 원문 표의 예정값 확인; "
                            "실제 소각 완료·배당 및 주주환원 산식·기보도 미검증")
            cessation = row.get("businessCessationPrimarySource")
            if (row.get("status") == "official_business_cessation_document_review"
                and isinstance(cessation, dict)
                and cessation.get("officialXmlOrHtmlBodyRetrieved") is True):
                observed = cessation.get("observedTerms")
                if isinstance(observed, dict):
                    verified = {}
                    fields = ("reportedBusinessScope", "reportedAffectedSalesWon",
                              "reportedRecentSalesWon", "issuerReportedRevenueRatioPct",
                              "issuerStatedCessationDate")
                    for field in fields:
                        proof = observed.get(field)
                        if (isinstance(proof, dict)
                            and proof.get("basis") == "same_official_table_row"
                            and proof.get("operationalShutdownVerified") is False
                            and proof.get("independentBusinessEffectVerified") is False
                            and isinstance(proof.get("value"), str)
                            and 1 <= len(proof["value"]) <= 140):
                            verified[field] = proof["value"]
                    relation = row.get("businessCessationFilingRelation")
                    if relation in ("issuer_business_cessation",
                                    "parent_disclosure_of_subsidiary"):
                        item["businessCessationFilingRelation"] = relation
                    item["uniqueUnderlyingCessationEventVerified"] = False
                    if verified:
                        item["issuerFiledBusinessCessationTerms"] = verified
                        item["officialFact"] = (
                            "공식 영업정지 공시 원문 표의 기재값만 확인; "
                            "실제 중단 실행·사업 영향·선행보도 및 모자회사 중복 여부 미검증")
            if fresh:
                out["freshOfficialReview"].append(item)
                added_recent += 1
            else:
                out["backgroundReference"].append(item)
                added_background += 1
            visible.add(key)
            attached_this_run.add(key)
            out["seen"].setdefault(key, first_seen)
    out["freshOfficialReview"].sort(key=lambda x: (x.get("officialDate", ""), x.get("id", "")), reverse=True)
    out["backgroundReference"].sort(key=lambda x: (x.get("officialDate", ""), x.get("id", "")), reverse=True)
    out["freshOfficialReviewCount"] = max(len(queue["freshOfficialReview"]),
        int(queue.get("freshOfficialReviewCount") or 0)) + added_recent
    out["backgroundReferenceCount"] = max(len(queue["backgroundReference"]),
        int(queue.get("backgroundReferenceCount") or 0)) + added_background
    out["freshOfficialReview"] = out["freshOfficialReview"][:40]
    out["backgroundReference"] = out["backgroundReference"][:25]
    out["truncatedBackgroundReference"] = max(0, out["backgroundReferenceCount"] - 25)
    out["incompleteOrStaleFeeds"] = [x["name"] for x in out["feedHealth"]
                                     if x.get("status") != "checked_source"]
    out["sourceCompletenessVerified"] = not out["incompleteOrStaleFeeds"]
    out["beatWideDartAdded"] = added_recent + added_background
    out["beatMergeAlreadyApplied"] = True
    out["beatAttachedReceiptIds"] = sorted(already_attached | attached_this_run)
    out["beatWideDartExcluded"] = excluded
    out["beatWideDartSourceAt"] = beat.get("generatedAt") if valid else None
    out["confirmedScoops"] = 0
    out["approvedArticles"] = 0
    out["baseTriageGeneratedAt"] = queue.get("baseTriageGeneratedAt", queue.get("generatedAt"))
    out["generatedAt"] = now.isoformat(timespec="seconds")
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--triage", default="digests/official_event_triage_latest.json")
    parser.add_argument("--beat", default="digests/dart_beat_monitor_latest.json")
    args = parser.parse_args()
    path = Path(args.triage)
    queue = json.loads(path.read_text(encoding="utf-8"))
    try:
        beat = json.loads(Path(args.beat).read_text(encoding="utf-8"))
    except (ValueError, OSError):
        beat = {}
    report = merge(queue, beat)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    print("DART beat attached:", report["beatWideDartAdded"],
          "public receipts, 0 confirmed scoops; source health",
          next(x["status"] for x in report["feedHealth"]
               if x["name"] == "dart_beat_monitor"))


if __name__ == "__main__":
    main()
