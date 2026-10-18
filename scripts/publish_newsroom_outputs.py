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
        "digests/reverse_trace_latest.json",
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
    args = ap.parse_args()
    outcome = publish(Path(args.root), args.mode)
    print("validated", args.mode, "publish:", outcome)


if __name__ == "__main__":
    main()
