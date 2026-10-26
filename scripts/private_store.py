"""Bearer-token client for the radar Worker's private feeds (never the public repo).

GET returns the collector's own previous document (for diffs); PUT replaces it.
Logs must stay counts-only: this module never prints document contents.
"""
from __future__ import annotations

import json

WORKER = "https://seoul-reporting-radar.shhong9173.workers.dev"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
FEEDS = {"scoop-screen", "us-comments", "page-watch", "partner-filings"}


class StoreError(RuntimeError):
    pass


def _headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "User-Agent": UA}


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
        raise StoreError(f"private store GET HTTP {r.status_code}")
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
