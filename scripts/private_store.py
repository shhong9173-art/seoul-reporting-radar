"""Bearer-token client for the radar Worker's private feeds (never the public repo).

GET returns the collector's own previous document (for diffs); PUT replaces it.
Logs must stay counts-only: this module never prints document contents.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re

WORKER = "https://seoul-reporting-radar.shhong9173.workers.dev"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
FEEDS = {"scoop-screen", "us-comments", "page-watch", "partner-filings", "trade-remedy", "us-litigation", "kr-official", "kr-signals", "kr-stats", "trademarks", "assembly-bills", "radar-check", "us-recalls"}


class StoreError(RuntimeError):
    pass


def token_shape(token):
    """Describe the secret's format without revealing it (length and shape only)."""
    t = token or ""
    # 8 hex chars of SHA-256: enough to tell two values apart, useless for recovering a random 43-char token.
    fp = hashlib.sha256(t.encode()).hexdigest()[:8] if t else "-"
    return (f"길이 {len(t)}, 지문 {fp}, 형식 {'정상' if re.fullmatch(r'[A-Za-z0-9_-]{16,128}', t) else '비정상'}"
            f"{', 주소 포함' if '/' in t or 'http' in t.lower() else ''}{', 공백·줄바꿈 포함' if re.search(r'\s', t) else ''}"
            f"{', 따옴표 포함' if re.search(r'[\"\']', t) else ''}")


def normalize_token(token):
    """Accept either the bare token or the whole connector URL (…/mcp/<token>) pasted into the secret."""
    t = (token or "").strip().strip('"\'')
    m = re.search(r"/mcp/([A-Za-z0-9_-]{16,128})/?$", t)
    return m.group(1) if m else t


def _headers(token):
    return {"Authorization": f"Bearer {normalize_token(token)}", "Content-Type": "application/json", "User-Agent": UA}


def get(name, token, *, get=None):
    """Previous private document, or None when nothing is stored yet. Errors raise (never treated as empty)."""
    if name not in FEEDS:
        raise ValueError(name)
    if get is None:
        import requests
        get = requests.get
    r = get(f"{WORKER}/ingest/{name}", headers=_headers(token), timeout=30)
    if r.status_code == 204:
        return None
    if r.status_code != 200:
        hint = f" — 토큰 거부 가능성({token_shape(normalize_token(token))}; Cloudflare MCP_ACCESS_TOKEN과 같아야 함)" if r.status_code == 404 else ""
        raise StoreError(f"private store GET HTTP {r.status_code}{hint}")
    return r.json()


def put(name, doc, token, *, post=None):
    if name not in FEEDS:
        raise ValueError(name)
    if post is None:
        import requests
        post = requests.post
    r = post(f"{WORKER}/ingest/{name}", data=json.dumps(doc, ensure_ascii=False).encode("utf-8"),
             headers=_headers(token), timeout=30)
    return getattr(r, "status_code", 0)


RELAY_HOSTS = {"www.industry.gov.au", "www.dgtr.gov.in"}


def relay(url, token, *, get=None, timeout=40):
    """Fetch an allow-listed official page through the Worker (for hosts that time out from GitHub runners).
    Returns (status, text, error); status is the upstream HTTP status the Worker saw."""
    from urllib.parse import urlparse
    if urlparse(url).hostname not in RELAY_HOSTS:
        raise ValueError(url)
    if get is None:
        import requests
        get = requests.get
    try:
        r = get(f"{WORKER}/ingest/relay", params={"url": url}, headers=_headers(token), timeout=timeout)
    except Exception as e:
        return 0, None, f"중계 {type(e).__name__}"
    if r.status_code != 200:
        return r.status_code, None, f"중계 HTTP {r.status_code}"
    upstream = int((getattr(r, "headers", None) or {}).get("X-Relay-Status", "0") or 0)
    if upstream != 200:
        return upstream, None, f"원 사이트 HTTP {upstream}(중계)"
    return upstream, r.text, None


LATE_HOURS = 6


def late_scheduled_duplicate(previous, now, *, hours=LATE_HOURS, env=None):
    """True when this is a GitHub cron run arriving after the same watch already ran (normally the on-time
    Cloudflare request). GitHub's cron is often hours late; the late copy is skipped. Manual, push and
    Cloudflare-requested runs (workflow_dispatch) never skip, and a missing or old result never skips —
    so GitHub's cron still covers a failed Cloudflare request."""
    env = os.environ if env is None else env
    if env.get("GITHUB_EVENT_NAME") != "schedule" or not isinstance(previous, dict):
        return False
    try:
        last = dt.datetime.fromisoformat(str(previous.get("generatedAt")))
        age = (now - last).total_seconds() / 3600
    except (TypeError, ValueError):
        return False
    if 0 <= age < hours:
        print(f"::notice title=skip-late-schedule::직전 결과가 {age:.1f}시간 전 — 늦게 도착한 GitHub 예약 실행이라 건너뜀(결과 유지)")
        return True
    return False
