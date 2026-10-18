"""A score-independent, lightweight prior-coverage memory for Korean press.

This stores observed index metadata, NOT article fulltexts, exhaustive coverage
or proof of exclusivity. Unlike pitch archives, every collected domestic article
with a verifiable publication timestamp is retained regardless of popularity,
headline score, source count or 'exclusive' label.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

KST = timezone(timedelta(hours=9))
RETENTION_DAYS = 365
MAX_ENTRIES = 100_000
MAX_SOURCE_ITEMS = 30_000
STATUS = "observed_domestic_press_index_not_complete_coverage"
NUMBERS = re.compile(r"(?<![가-힣A-Za-z0-9])\d{1,3}(?:,\d{3})+(?:\.\d+)?|\b\d+(?:\.\d+)?(?:억|조|만원|%)")
FIELDS = ("title", "sourceName", "url", "published")


def parse_published(value):
    if not isinstance(value, str) or not value or len(value) > 45:
        return None
    try:
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        return None
    return date if date.tzinfo is not None and date.utcoffset() is not None else None


def article_id(row):
    # Same Google RSS URL must not be duplicated every fifteen minutes.
    url = row.get("url") or ""
    if url:
        return hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
    return hashlib.sha256(
        (row["sourceName"]+"|"+row["title"]+"|"+row["published"][:10])
        .encode("utf-8")).hexdigest()[:24]


def small_record(raw):
    if not isinstance(raw, dict) or raw.get("global") is True:
        return None
    if any(not isinstance(raw.get(k), str) or not raw.get(k).strip()
           for k in FIELDS):
        return None
    when = parse_published(raw["published"])
    if when is None:
        return None
    link = raw["url"]
    if not 1 <= len(link) <= 1200:
        return None
    try:
        uri = urlsplit(link)
        if uri.scheme not in ("https", "http") or not uri.hostname:
            return None
    except ValueError:
        return None
    title = " ".join(raw["title"].split())[:240]
    source = " ".join(raw["sourceName"].split())[:110]
    if not title or not source:
        return None
    companies = raw.get("companies")
    if not isinstance(companies, list):
        companies = []
    companies = list(dict.fromkeys(
        x[:65] for x in companies if isinstance(x, str) and x.strip()))[:8]
    combined = title+" "+str(raw.get("summary") or "")[:650]
    values = list(dict.fromkeys(NUMBERS.findall(combined)))[:12]
    info = {"title": title, "sourceName": source, "url": link,
            "published": when.isoformat(timespec="seconds"),
            "companies": companies, "numbers": values,
            "global": False, "fulltextReviewed": False,
            "coverageIndexOnly": True}
    info["id"] = article_id(info)
    return info


def merge_index(prior, new_items, *, now=None, horizon_days=RETENTION_DAYS):
    now = now or datetime.now(KST)
    if now.utcoffset() is None:
        raise ValueError("need_aware_now")
    if not 365 <= horizon_days <= 730:
        raise ValueError("press_index_365_day_minimum")
    if not isinstance(new_items, list) or len(new_items) > MAX_SOURCE_ITEMS:
        raise ValueError("invalid_collected_press_items")
    if prior is not None and (
        not isinstance(prior, dict) or prior.get("status") != STATUS
        or not isinstance(prior.get("items"), list)
        or len(prior["items"]) > MAX_ENTRIES
    ):
        raise ValueError("bad_existing_press_index_preserve_instead_of_zero")
    cutoff = now - timedelta(days=horizon_days)
    indexed = {}
    prior_count = 0
    invalid = 0
    for raw in (prior or {}).get("items", []):
        row = small_record(raw)
        if row is None:
            invalid += 1
            continue
        dt = parse_published(row["published"])
        if cutoff <= dt <= now + timedelta(hours=1):
            indexed[row["id"]] = row
            prior_count += 1
    accepted = 0
    for raw in new_items:
        row = small_record(raw)
        if row is None:
            invalid += 1
            continue
        when = parse_published(row["published"])
        if not cutoff <= when <= now + timedelta(hours=1):
            continue
        if row["id"] not in indexed:
            accepted += 1
        indexed[row["id"]] = row
    records = sorted(indexed.values(),
                     key=lambda x: (x["published"], x["id"]), reverse=True)
    if len(records) > MAX_ENTRIES:
        # Do not silently truncate historical evidence. A known capacity
        # failure should preserve the last valid snapshot on disk.
        raise ValueError("press_history_capacity_exceeded")
    return {
        "status": STATUS, "generatedAt": now.astimezone(KST).isoformat(timespec="seconds"),
        "retentionDays": horizon_days,
        "itemCount": len(records),
        "newlyIndexedArticleCount": accepted,
        "priorRetainedCount": prior_count,
        "malformedOrUndatedInputCount": invalid,
        "firstRunBaseline": prior is None or (prior.get("seedOnly") is True if isinstance(prior, dict) else False),
        "proofOfNoPriorCoverage": False,
        "pressFulltextReviewed": False,
        "warning": ("일부 수집된 국내 기사 제목·매체·일자 색인임. 누락·수집 실패가 존재할 수 있으므로 "
                    "검색 결과 0건만으로 국내 미보도 또는 단독으로 확정하지 말 것"),
        "items": records
    }


def load_index(path):
    p = Path(path)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def write_index(path, index):
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    temp = dest.with_suffix(dest.suffix + ".tmp")
    temp.write_text(json.dumps(index, ensure_ascii=False,
        separators=(",", ":"))+"\n", encoding="utf-8")
    temp.replace(dest)


def update_from_news(new_items, *, path="digests/press_coverage_index_latest.json",
                     now=None):
    previous = load_index(path)
    result = merge_index(previous, new_items, now=now)
    write_index(path, result)
    return result
