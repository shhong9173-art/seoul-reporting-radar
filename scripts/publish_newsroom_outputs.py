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
from pathlib import Path

# Only these fixed paths may be published by this script. One file, one owner.
OUTPUTS = {
    "news": (
        "dart_refresh_status.json", "data.js", "data.json", "global.json",
        "archive.json", "changes.json", "strategic_shifts.json", "dart.json",
        "pitch.json", "industry.json", "dig_today.json", "dart_corp_codes.json",
    ),
    "scoop": ("pre_scoop.json", "scoop.json", "dart_numeric.json"),
    "health": (
        "digests/auto_news_feed_health_latest.json",
        "digests/global_news_feed_health_latest.json",
    ),
}
OPTIONAL = {"dart_corp_codes.json"}
MAX_BYTES = 12 * 1024 * 1024


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
        if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_BYTES:
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
    if mode == "scoop":
        for name in ("pre_scoop.json", "scoop.json", "dart_numeric.json"):
            obj = json.loads((root / name).read_text(encoding="utf-8"))
            if not isinstance(obj, dict) or not isinstance(obj.get("items"), list):
                raise ValueError("invalid_scoop_output: " + name)
    if mode == "health":
        for name in files:
            obj = json.loads((root / name).read_text(encoding="utf-8"))
            if (not isinstance(obj, dict) or
                obj.get("newsDatasetApprovedForPublish") not in (True, False) or
                obj.get("zeroFetchedMeansZeroPublishedStories") is not False or
                not isinstance(obj.get("checks"), list)):
                raise ValueError("invalid_source_health_output: " + name)
    return files


def publish(root: Path, mode: str, *, attempts: int = 4, before_push=None):
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
