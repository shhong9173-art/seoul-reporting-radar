"""Publish *validated* newsroom outputs from an isolated Git worktree.

Two independent workflows own non-overlapping files. Never rebase or reset the
collector's dirty working tree, and never combine health and story outputs
accidentally. On an unrelated concurrent remote commit, regenerate one atomic
output commit from the current remote main and retry the push.

The caller MUST finish its existing evidence/JSON validation before 'news' or
'scoop' mode. RSS diagnosis can be persisted via 'health' even on a failed run.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from datetime import datetime, timezone

# Only these fixed paths may be published by this script. One file, one owner.
OUTPUTS = {
    "news": (
        "dart_refresh_status.json", "data.js", "data.json", "global.json",
        "archive.json", "digests/press_coverage_index_latest.json",
        "digests/historical_exclusive_press_index_latest.json",
        "digests/recent_exclusive_recall_audit_latest.json",
        "digests/reverse_trace_latest.json",
        "digests/reverse_trace_dart_followups_latest.json",
        "changes.json", "strategic_shifts.json", "dart.json",
        "pitch.json", "industry.json", "dig_today.json",
    ),
    "dart_beat": (
        "dart_corp_codes.json",
        "digests/dart_corp_code_coverage_latest.json",
        "digests/dart_beat_monitor_latest.json",
        "digests/dart_beat_changes_latest.json",
    ),
    "scoop": ("pre_scoop.json", "scoop.json", "dart_numeric.json"),
    "queue": ("digests/reporting_evidence_queue_latest.json",),
    "crossborder": (
        "digests/crossborder_source_gap_latest.json",
        "digests/slovakia_official_accounts_latest.json",
        "digests/czech_factory_official_identity_latest.json",
        "digests/slovak_ifrs_primary_pages_latest.json",
        "digests/nhtsa_part573_primary_latest.json",
        "digests/domestic_recall_screen_latest.json",
    ),
    "health": (
        "digests/auto_news_feed_health_latest.json",
        "digests/global_news_feed_health_latest.json",
    ),
    "primary_dossiers": ("digests/primary_research_dossiers_latest.json",),
    "primary_discovery": ("digests/primary_original_discovery_latest.json",),
    "sec_filings": ("digests/primary_sec_filing_watch_latest.json",),
}
OPTIONAL = set()  # A shared corporate registry has exactly one official writer.
# Existing verified archive.json is ~16.2MB (2026-10-17). A blanket 12MiB
# cap blocked already-validated news from publication. Give ONLY the long-lived
# 90-day news archive a bounded 32MiB allowance, never all output files.
DEFAULT_MAX_BYTES = 12 * 1024 * 1024
ARCHIVE_MAX_BYTES = 32 * 1024 * 1024

def output_size_limit(name: str) -> int:
    return ARCHIVE_MAX_BYTES if name == "archive.json" else DEFAULT_MAX_BYTES


def run(cwd: Path, *args: str, check: bool = True):
    result = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True,
        timeout=80, check=False,
    )
    if check and result.returncode:
        # Never reproduce credential-bearing remote URLs or subprocess stderr.
        raise RuntimeError("git_" + args[0] + "_failed")
    return result


def selected(root: Path, mode: str):
    if mode not in OUTPUTS:
        raise ValueError("unknown_output_owner")
    files = []
    for name in OUTPUTS[mode]:
        path = root / name
        if not path.exists():
            if mode == "health" or name in OPTIONAL:
                continue
            raise ValueError("required_generated_output_missing: " + name)
        if not path.is_file() or path.is_symlink() or path.stat().st_size > output_size_limit(name):
            raise ValueError("invalid_generated_output: " + name)
        if name.endswith(".json"):
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except (UnicodeError, ValueError):
                raise ValueError("invalid_json_output: " + name) from None
        files.append(name)
    if mode == "sec_filings":
        report=json.loads((root / "digests/primary_sec_filing_watch_latest.json")
                          .read_text(encoding="utf-8"))
        sources=report.get("sources",[])
        filings=report.get("filings",[])
        if (report.get("status")!="sec_edgar_filing_index_observed_not_fulltext_or_exclusive"
            or report.get("sourceCoverageExhaustive") is not False
            or report.get("allDomesticPressChecked") is not False
            or report.get("allOriginalDocumentBodiesRead") is not False
            or report.get("confirmedScoops")!=0
            or not isinstance(sources,list) or not 1<=len(sources)<=12
            or report.get("sourcesAttempted")!=len(sources)
            or not isinstance(filings,list) or len(filings)>80
            or report.get("filingsObserved")!=len(filings)
            or report.get("newlyObservedAfterBaseline")!=sum(
                f.get("newSinceCleanBaseline") is True for f in filings)):
            raise ValueError("unsafe_sec_primary_original_index")
        if any(not isinstance(f,dict) or
               f.get("exclusiveConfirmed") is not False or
               f.get("originalDocumentBodyRead") is not False or
               f.get("contractOrPartnerMentionVerified") is not False or
               f.get("actualTransactionDateVerified") is not False or
               f.get("fullTextAndPriorPressCompared") is not False or
               not isinstance(f.get("filingOriginalUrl"),str) or
               not f["filingOriginalUrl"].startswith(
                   "https://www.sec.gov/Archives/edgar/data/")
               for f in filings):
            raise ValueError("sec_filing_unverified_evidence_cannot_publish")
    if mode == "primary_discovery":
        report=json.loads((root / "digests/primary_original_discovery_latest.json")
                          .read_text(encoding="utf-8"))
        sources=report.get("sources",[])
        candidates=report.get("candidates",[])
        if (report.get("status")!="official_listing_links_observed_not_verified_scoops"
            or report.get("sourceCoverageExhaustive") is not False
            or report.get("domesticNoPriorCoverageProved") is not False
            or report.get("confirmedScoops")!=0
            or not isinstance(sources,list) or not 1<=len(sources)<=8
            or report.get("sourcesAttempted")!=len(sources)
            or not isinstance(candidates,list) or len(candidates)>50
            or report.get("candidateCount")!=len(candidates)
            or report.get("newlyObservedAfterBaseline")!=sum(
                x.get("newlyObservedAfterCleanBaseline") is True
                for x in candidates)
            or any(x.get("confirmedExclusive") is not False or
                   x.get("publishedAtVerified") is not False or
                   x.get("factsComparedToPublisherArticle") is not False or
                   x.get("domesticPriorCoverageChecked") is not False or
                   x.get("originalPageRead") is not True or
                   x.get("companyActivityOrLegalOutcomeIndependentlyConfirmed",False)
                       is not False or
                   not isinstance(x.get("eventFieldsQuotedFromOriginal",[]),list) or
                   len(x.get("eventFieldsQuotedFromOriginal",[]))>6 or
                   any(not isinstance(f,dict) or
                       f.get("notIndependentlyVerified") is not True or
                       not isinstance(f.get("originalQuote"),str) or
                       not 3<=len(f["originalQuote"])<=230 or
                       not isinstance(f.get("verbatimValue"),str) or
                       not 3<=len(f["verbatimValue"])<=145
                       for f in x.get("eventFieldsQuotedFromOriginal",[])) or
                   not isinstance(x.get("publicConfirmationQuestions",[]),list) or
                   len(x.get("publicConfirmationQuestions",[]))>4 or
                   any(not isinstance(q,str) or not q.endswith("?")
                       or any(term in q for term in (
                           "비공개 내부","내부 대응계획","생산 라인 전환 전략",
                           "공급사 변경 계획","미확정 영향 검토"))
                       for q in x.get("publicConfirmationQuestions",[]))
                   for x in candidates)):
            raise ValueError("unsafe_or_unverified_first_party_discovery")
        try:
            from scripts.primary_document_dossiers import safe_url
        except ModuleNotFoundError:
            # Invoking this file as a script sets sys.path[0] to /scripts.
            # The importable package path is then absent by default.
            from primary_document_dossiers import safe_url
        if any(not safe_url(x.get("url")) for x in candidates):
            raise ValueError("untrusted_discovered_original_url")
    if mode == "primary_dossiers":
        report=json.loads((root / "digests/primary_research_dossiers_latest.json")
                          .read_text(encoding="utf-8"))
        cases=report.get("cases",[])
        if (report.get("status")!="primary_original_reporter_dossiers_not_exclusive"
            or report.get("registryIsManuallyCuratedNotAutomatedDiscovery") is not True
            or report.get("allDomesticPressChecked") is not False
            or report.get("confirmedScoops")!=0 or report.get("approvedArticles")!=0
            or not isinstance(cases,list) or not 1<=len(cases)<=30
            or report.get("caseCount")!=len(cases)
            or type(report.get("documentRequestsAttempted")) is not int
            or type(report.get("documentPagesMatched")) is not int
            or type(report.get("documentPagesFailedOrUnmatched")) is not int
            or report["documentPagesMatched"]+report["documentPagesFailedOrUnmatched"]
               !=report["documentRequestsAttempted"]
            or report["documentRequestsAttempted"]<len(cases)
            or report["documentRequestsAttempted"]>150):
            raise ValueError("unsafe_or_unverified_primary_source_dossiers")
        if any(not isinstance(c,dict) or c.get("exclusiveConfirmed") is not False
               or c.get("publisherFulltextCompared") is not False
               or c.get("noPriorPressProved") is not False
               or not isinstance(c.get("originalDocuments"),list)
               or not isinstance(c.get("factsFromMatchedPrimaryPages"),list)
               or c.get("originalDocumentsExpected")!=len(c["originalDocuments"])
               or c.get("originalDocumentsVerified")!=sum(
                   d.get("status")=="matched_original_text" for d in c["originalDocuments"])
               for c in cases):
            raise ValueError("primary_dossier_case_verification_failed")
    if mode == "news":
        articles = json.loads((root / "data.json").read_text(encoding="utf-8"))
        raw = (root / "data.js").read_text(encoding="utf-8").strip()
        if not isinstance(articles, list) or len(articles) < 10:
            raise ValueError("invalid_news_feed_or_too_few_articles")
        if not raw.startswith("window.ITEMS = ") or not raw.endswith(";"):
            raise ValueError("invalid_news_js")
        try:
            embedded = json.loads(raw[len("window.ITEMS = "):-1])
        except ValueError:
            raise ValueError("invalid_news_js_json") from None
        if embedded != articles:
            raise ValueError("news_js_json_mismatch")
        history=json.loads((root/"digests/press_coverage_index_latest.json").read_text(encoding="utf-8"))
        trace=json.loads((root/"digests/reverse_trace_latest.json").read_text(encoding="utf-8"))
        historical=json.loads((root/"digests/historical_exclusive_press_index_latest.json").read_text(encoding="utf-8"))
        if (not isinstance(historical,dict)
            or historical.get("status")!="historical_industry_exclusive_rss_partial_index"
            or not isinstance(historical.get("items"),list)
            or historical.get("itemCount")!=len(historical["items"])
            or not isinstance(historical.get("windowHealth"),dict)
            or historical.get("confirmedScoops")!=0
            or historical.get("allDomesticIndustryExclusivesCovered") is not False
            or any(not isinstance(x,dict) or
                   x.get("rssIndexedHeadlineOnly") is not True or
                   x.get("fulltextReviewed") is not False or
                   x.get("publisherOriginalUrlVerified") is not False
                   for x in historical["items"])
            or trace.get("historicalSearchIndexAt")!=historical.get("generatedAt")
            or trace.get("historicalSearchObservedRows")!=historical.get("itemCount")
            or trace.get("historicalSearchAllSourcesChecked") is not False):
            raise ValueError("unverified_historical_press_index_or_stale_reverse_trace")
        scoop_audit=json.loads(
            (root/"digests/recent_exclusive_recall_audit_latest.json")
            .read_text(encoding="utf-8"))
        if (scoop_audit.get("status")!="recent_exclusive_rss_cross_index_gap_not_exhaustive"
            or scoop_audit.get("historySourceAt")!=historical.get("generatedAt")
            or scoop_audit.get("rssCoverageExhaustive") is not False
            or scoop_audit.get("domesticUnreportedProved") is not False
            or scoop_audit.get("fullArticleTextsReviewed") is not False
            or scoop_audit.get("confirmedScoops")!=0
            or any(type(scoop_audit.get(key)) is not int
                   or not 0<=scoop_audit[key]<=35000 for key in (
                       "newsIndexObservedExclusive","historyIndexObservedExclusive",
                       "observedInBoth","newsOnlyObserved","historyOnlyObserved"))
            or scoop_audit["observedInBoth"]+scoop_audit["newsOnlyObserved"]
               !=scoop_audit["newsIndexObservedExclusive"]
            or scoop_audit["observedInBoth"]+scoop_audit["historyOnlyObserved"]
               !=scoop_audit["historyIndexObservedExclusive"]
            or any(not isinstance(scoop_audit.get(key),list)
                   or len(scoop_audit[key])>50 for key in (
                       "newsOnlyExamples","historyOnlyExamples"))):
            raise ValueError("stale_or_unsafe_recent_scoop_cross_index_audit")
        official_links=[x.get("locatedOfficialOriginalCandidate")
                        for x in trace.get("items",[])
                        if isinstance(x,dict) and
                        isinstance(x.get("locatedOfficialOriginalCandidate"),dict)]
        foreign_links=[]
        for item in trace.get("items",[]):
            if not isinstance(item,dict):
                continue
            linked=item.get("locatedSupportingOfficialOriginals",[])
            if not isinstance(linked,list) or len(linked)>4:
                raise ValueError("unsafe_supporting_primary_source_shape")
            foreign_links.extend(linked)
        if (trace.get("curatedLeadStatus")!="curated_official_original_candidates_chronology_unverified"
            or not isinstance(trace.get("curatedLeadSourceAt"),str)
            or not trace["curatedLeadSourceAt"]
            or trace.get("locatedOriginalCandidateArticleCount")!=len(official_links)
            or trace.get("distinctLocatedOfficialOriginalDocuments")!=
               len({x.get("documentUrl") for x in official_links+foreign_links})
            or trace.get("locatedSupplementaryForeignOriginalReferences")!=len(foreign_links)
            or trace.get("secOfficialAcceptanceTimestampChecked") is not bool(foreign_links)
            or any(not isinstance(x,dict) or
                   x.get("status")!="official_us_sec_filing_original_candidate_not_article_verified"
                   or x.get("sourceType")!="regulatory_filing"
                   or x.get("secAcceptedAtOfficialEastern")!="2025-10-30T16:15:52-04:00"
                   or x.get("secAcceptedAtIsNotPressFirstPublishedAt") is not True
                   or x.get("firstPublicAvailabilityClockVerified") is not False
                   or x.get("publisherStoryFirstPublicationClockVerified") is not False
                   or x.get("articleFulltextCompared") is not False
                   or x.get("sourceAndStoryFactsDirectlyMatched") is not False
                   or x.get("releasedBeforeStoryVerified") is not False
                   or x.get("automaticYPNDecision") is not False
                   for x in foreign_links)
            or trace.get("primaryDocumentPublishedBeforeMediaVerifiedCount")!=0
            or trace.get("pressFulltextMatchedToOfficialOriginalCount")!=0
            or trace.get("sourcePrioritizationEvidenceSufficient") is not False
            or any(not isinstance(x,dict) or
                   x.get("status")!="dated_company_original_candidate_not_chronology_verified" or
                   x.get("publicationClockVerified") is not False or
                   x.get("storyPublisherClockVerified") is not False or
                   x.get("articleFulltextCompared") is not False or
                   x.get("documentAndStoryFactsCompared") is not False or
                   x.get("releasedBeforeStoryVerified") is not False or
                   x.get("automaticYPNDecision") is not False
                   for x in official_links)):
            raise ValueError("unverified_original_candidate_claim_in_news_publish")
        try:
            # Imported from repository root in CI.
            from scripts.reverse_trace_dart_followups import STATUS as DART_FOLLOWUP_STATUS, official_dart_url
        except ModuleNotFoundError:
            # Invoked as python scripts/publish_newsroom_outputs.py in production.
            from reverse_trace_dart_followups import STATUS as DART_FOLLOWUP_STATUS, official_dart_url
        matched=json.loads((root/"digests/reverse_trace_dart_followups_latest.json")
                          .read_text(encoding="utf-8"))
        beat_doc=json.loads((root/"digests/dart_beat_monitor_latest.json")
                           .read_text(encoding="utf-8"))
        official_doc=json.loads((root/"digests/official_event_triage_latest.json")
                               .read_text(encoding="utf-8"))
        if (not isinstance(matched,dict)
            or matched.get("status")!=DART_FOLLOWUP_STATUS
            or not isinstance(matched.get("items"),list)
            or matched.get("candidatePairCount")!=len(matched["items"])
            or matched.get("reverseTraceSourceAt")!=trace.get("generatedAt")
            or matched.get("dartOfficialSourceAt")!=beat_doc.get("generatedAt")
            or matched.get("dartOfficialSourceAt")!=official_doc.get("beatWideDartSourceAt")
            or matched.get("officialQueueSourceAt")!=official_doc.get("generatedAt")
            or matched.get("confirmedScoops")!=0
            or matched.get("approvedArticles")!=0
            or matched.get("humanValidatedYPN")!=0
            or matched.get("sameFactEstablished") is not False
            or matched.get("sourceCompletenessVerified") is not False
            or matched.get("distinctOfficialReceipts")!=len(
                {x.get("officialReceiptNo") for x in matched["items"] if isinstance(x,dict)})
            or matched.get("distinctObservedArticles")!=len(
                {x.get("articleId") for x in matched["items"] if isinstance(x,dict)})
            or any(not isinstance(x,dict)
                   or x.get("exclusiveConfirmed") is not False
                   or x.get("approvedForPitch") is not False
                   or x.get("automaticYPNDecision") is not False
                   or x.get("publicFactOverlapVerified") is not False
                   or x.get("publicSourceAvailableBeforePublisherVerified") is not False
                   or x.get("publisherFirstPublishedAtVerified") is not False
                   or x.get("officialOriginalBodyVerifiedForMatchedFact") is not False
                   or x.get("originalEvidenceStage") not in (
                       "official_receipt_only_original_not_checked",
                       "official_table_filing_fields_checked",
                       "official_share_cancellation_fields_checked",
                       "official_business_cessation_fields_checked",
                       "official_business_cessation_text_only_fields_unverified",
                       "official_share_cancellation_text_only_fields_unverified")
                   or not official_dart_url(
                       x.get("officialUrl"),x.get("officialReceiptNo"))
                   for x in matched["items"])):
            raise ValueError("unverified_dart_receipt_reverse_trace_in_news_publish")
        if (not isinstance(history,dict)
            or history.get("status")!="observed_domestic_press_index_not_complete_coverage"
            or history.get("itemCount")!=len(history.get("items",[]))
            or not isinstance(trace,dict)
            or trace.get("status")!="automotive_industry_exclusive_reverse_trace_unverified_candidates"
            or trace.get("pressIndexGeneratedAt")!=history.get("generatedAt")
            or trace.get("confirmedScoops")!=0 or trace.get("approvedArticles")!=0
            or trace.get("reliablePopulationReachEstimated") is not False
            or trace.get("humanReviewedYPN")!=trace.get("Y",0)+trace.get("P",0)+trace.get("N",0)
            or trace.get("totalObservedExclusiveHeadlines")!=len(trace.get("items",[]))
            or any(not isinstance(x,dict) or x.get("confirmedExclusive") is not False
                   or x.get("publicTraceClass") not in ("Y","P","N","U")
                   for x in trace.get("items",[]))):
            raise ValueError("unverified_reverse_trace_claim_in_news_publish")
    if mode == "scoop":
        for name in ("pre_scoop.json", "scoop.json", "dart_numeric.json"):
            obj = json.loads((root / name).read_text(encoding="utf-8"))
            if not isinstance(obj, dict) or not isinstance(obj.get("items"), list):
                raise ValueError("invalid_scoop_output: " + name)
    if mode == "dart_beat":
        def read_dart(name):
            doc=json.loads((root/name).read_text(encoding="utf-8"))
            if not isinstance(doc,dict):raise ValueError("invalid_dart_beat_"+name)
            return doc
        codes=read_dart("dart_corp_codes.json").get("companies")
        coverage=read_dart("digests/dart_corp_code_coverage_latest.json")
        monitor=read_dart("digests/dart_beat_monitor_latest.json")
        changes=read_dart("digests/dart_beat_changes_latest.json")
        if (not isinstance(codes,dict) or
            coverage.get("status")!="official_corp_code_registry_checked" or
            monitor.get("status")!="industry_beat_official_receipt_review" or
            changes.get("status")!="official_receipt_change_review_not_exclusive" or
            monitor.get("confirmedScoops")!=0 or monitor.get("approvedArticles")!=0 or
            changes.get("confirmedScoops")!=0 or changes.get("approvedArticles")!=0 or
            not isinstance(coverage.get("companies"),list) or
            coverage.get("scope")!=monitor.get("scopeCompanyCount") or
            coverage.get("knownWithCode")!=sum(
                row.get("corpCode") is not None for row in coverage["companies"]
                if isinstance(row,dict)) or
            monitor.get("companiesCodeVerified")+
            monitor.get("companiesUnresolved")+
            monitor.get("companiesWithSourceErrors")!=monitor.get("scopeCompanyCount") or
            coverage.get("generatedAt")!=monitor.get("generatedAt") or
            changes.get("sourceGeneratedAt")!=monitor.get("generatedAt")):
            raise ValueError("invalid_shared_dart_official_snapshot")
        # An issuer marked verified in a new official registry run must
        # retain the same corporation ID in the file used by the next run.
        for row in coverage["companies"]:
            if not isinstance(row,dict):raise ValueError("invalid_shared_dart_registry_row")
            co=row.get("company");number=row.get("corpCode")
            if number is None:continue
            actual=codes.get(co)
            if (not isinstance(actual,dict) or actual.get("corp_code")!=number):
                raise ValueError("official_issuer_id_missing_in_published_registry")
            if row.get("status")=="resolved_unique_official_stock_and_legal_name":
                if (row.get("officialListedStockCodeProof") is None or
                    actual.get("stock_code")!=row["officialListedStockCodeProof"]):
                    raise ValueError("listed_issuer_stock_identity_unverified")
        # Different source emitters are NOT authorized to overwrite these
        # files; only the official-issuer production job owns the whole set.
    if mode == "queue":
        doc=json.loads((root / "digests/reporting_evidence_queue_latest.json").read_text(encoding="utf-8"))
        if (not isinstance(doc,dict) or
            doc.get("status")!="reporter_evidence_queue_not_exclusive" or
            doc.get("confirmedScoops")!=0 or doc.get("approvedArticles")!=0 or
            not isinstance(doc.get("items"),list) or
            doc.get("totalRows")!=len(doc["items"]) or
            any(not isinstance(x,dict) or x.get("exclusiveConfirmed") is not False or
                x.get("approvedForPitch") is not False or
                x.get("pressFulltextReviewed") is not False
                for x in doc["items"])):
            raise ValueError("invalid_reporting_queue_evidence")
    if mode == "crossborder":
        doc=json.loads((root/"digests/crossborder_source_gap_latest.json").read_text(encoding="utf-8"))
        if (not isinstance(doc,dict) or
            doc.get("status")!="crossborder_reporter_evidence_gap_not_exclusive" or
            doc.get("confirmedScoops")!=0 or doc.get("approvedArticles")!=0 or
            doc.get("domesticRecallAbsenceVerified") is not False or
            doc.get("foreignParentCashTransferVerified") is not False or
            not isinstance(doc.get("items"),list) or
            any(not isinstance(item,dict) or
                item.get("pitchGate",{}).get("exclusiveConfirmed") is not False or
                item.get("pitchGate",{}).get("approvedForPitch") is not False
                for item in doc["items"])):
            raise ValueError("invalid_crossborder_source_evidence")
        for item in doc["items"]:
            profit=(item.get("dividendCrossPeriodGap") or {}).get("slovakLocalProfitYearOnYear")
            if profit is not None and (not isinstance(profit,dict)
                or profit.get("exclusiveConfirmed") is not False
                or profit.get("koreanParentCashReceiptVerified") is not False
                or profit.get("sourceLineManuallyReviewed") is not False
                or profit.get("samePeriodAsKorean2026HalfYearDividendIncome") is not False):
                raise ValueError("invalid_crossborder_profit_comparison")
    if mode == "health":
        for name in files:
            obj = json.loads((root / name).read_text(encoding="utf-8"))
            if (not isinstance(obj, dict) or
                obj.get("newsDatasetApprovedForPublish") not in (True, False) or
                obj.get("zeroFetchedMeansZeroPublishedStories") is not False or
                not isinstance(obj.get("checks"), list)):
                raise ValueError("invalid_source_health_output: " + name)
    return files


def verified_queue_dart_source_at(source):
    """Source collection time orders queue versions, not official event novelty."""
    try:
        if isinstance(source,Path):
            source=json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(source,dict):return None
        h=source.get("sourceHealth")
        if not isinstance(h,dict):return None
        d=h.get("dartBeat")
        if not isinstance(d,dict) or d.get("status") not in (
            "source_snapshot_checked","source_partial_coverage"):return None
        stamp=datetime.fromisoformat(d.get("generatedAt"))
        return stamp.astimezone(timezone.utc) if stamp.utcoffset() is not None else None
    except (OSError,ValueError,TypeError,OverflowError):
        return None



def rebuild_dart_followups_from_current_remote(worktree: Path):
    """Bind current news trace to the latest *independently published* DART.

    This runs ONLY inside the disposable worktree after fetching origin/main,
    never against the collector's dirty checkout. If independent official
    DART and event triage snapshots disagree, fail closed instead of
    publishing stale candidate evidence or pretending zero matches.
    """
    try:
        from scripts.reverse_trace_dart_followups import build_queue
    except ModuleNotFoundError:
        from reverse_trace_dart_followups import build_queue
    def read(name):
        return json.loads((worktree / name).read_text(encoding="utf-8"))
    result=build_queue(
        read("digests/reverse_trace_latest.json"),
        read("digests/official_event_triage_latest.json"),
        read("digests/dart_beat_monitor_latest.json"),
    )
    path=worktree / "digests/reverse_trace_dart_followups_latest.json"
    target=path.with_suffix(".json.tmp")
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",
                      encoding="utf-8")
    target.replace(path)
    return result


def publish(root: Path, mode: str, *, attempts: int = 6, before_push=None, retry_sleep=time.sleep):
    root = root.resolve()
    if attempts < 1 or attempts > 6:
        raise ValueError("invalid_retry_count")
    names = selected(root, mode)
    if not names:
        return "no_source_health_created"
    # Do not write to, rebase, stash, add or reset the collector workspace.
    # All cherry-pick-style retries happen only in this disposable worktree.
    with tempfile.TemporaryDirectory(prefix="newsroom-git-publish-") as tmp:
        output = Path(tmp) / "worktree"
        attached = False
        try:
            for attempt in range(attempts):
                run(root, "fetch", "--no-tags", "origin",
                    "+refs/heads/main:refs/remotes/origin/main")
                if not attached:
                    run(root, "worktree", "add", "--detach",
                        str(output), "refs/remotes/origin/main")
                    attached = True
                else:
                    run(output, "reset", "--hard", "refs/remotes/origin/main")
                    run(output, "clean", "-fd")
                if mode == "queue":
                    incoming=verified_queue_dart_source_at(
                        root/"digests/reporting_evidence_queue_latest.json")
                    existing=verified_queue_dart_source_at(
                        output/"digests/reporting_evidence_queue_latest.json")
                    if existing is not None and (
                        incoming is None or incoming<existing):
                        return "skipped_stale_dart_source"
                for name in names:
                    destination = output / name
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(root / name, destination)
                if mode == "news":
                    # DART may update while Auto Desk is collecting news.
                    # A news branch checkout must never silently publish a
                    # research queue tied to the *older* DART snapshot.
                    rebuild_dart_followups_from_current_remote(output)
                run(output, "add", "--", *names)
                changed = run(output, "diff", "--cached", "--quiet", check=False)
                if changed.returncode == 0:
                    return "no_changes"
                if changed.returncode != 1:
                    raise RuntimeError("staged_diff_failed")
                # Freshly create the commit atop the *current* remote main.
                run(output, "-c", "user.name=github-actions[bot]",
                    "-c", "user.email=41898282+github-actions[bot]@users.noreply.github.com",
                    "commit", "-m",
                    "data: validated newsroom " + mode + " outputs [skip ci]")
                if before_push is not None:
                    before_push(attempt)
                pushed = run(output, "push", "origin",
                             "HEAD:refs/heads/main", check=False)
                if pushed.returncode == 0:
                    return "published"
                # Other independently scheduled producers may publish their
                # own unrelated changes after our fetch. Never force push or
                # preserve the failed commit as evidence of publication.
                # Rebuild from *fresh* main with bounded backoff.
                if attempt+1 < attempts:
                    retry_sleep(min(2**attempt, 8))
            raise RuntimeError("remote_changed_or_push_denied_after_retries")
        finally:
            if attached:
                run(root, "worktree", "remove", "--force", str(output), check=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=tuple(OUTPUTS), required=True)
    ap.add_argument("--root", default=".")
    ap.add_argument("--check-only", action="store_true",
                    help="Validate source output exactly as CLI would, but never git push")
    args = ap.parse_args()
    if args.check_only:
        files=selected(Path(args.root).resolve(),args.mode)
        print("validated",args.mode,"outputs:",", ".join(files),
              "(read-only; no git push)")
        return
    outcome = publish(Path(args.root), args.mode)
    print("validated", args.mode, "publish:", outcome)


if __name__ == "__main__":
    main()
