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
# 11-24: 하루 약 620건이 쌓여 1년이면 약 23만 건 — 예전 상한 10만 건은 3월 말에 찼다.
MAX_ENTRIES = 400_000
MAX_SOURCE_ITEMS = 30_000
STATUS = "observed_domestic_press_index_not_complete_coverage"
# 11-24 월별 분할: 한 파일(1년이면 약 120MB)은 발행 상한·GitHub 파일 한도(100MB)를 넘는다.
# latest 파일에는 이번 달·지난달만 두고, 그 전 달은 press_coverage_index/YYYY-MM.json에 달마다 나눈다.
# latest의 coldShards 목록(달·파일·건수·sha256)이 유일한 기준이다 — 목록에 없는 파일은 읽지 않는다.
SHARD_STATUS = "observed_domestic_press_index_month_shard"
SHARD_DIR = "press_coverage_index"
HOT_MONTHS = 2
MAX_SHARDS = 30
SHARD_FILE = re.compile(r"press_coverage_index/(\d{4}-(?:0[1-9]|1[0-2]))\.json")
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
    values = NUMBERS.findall(combined)
    # 11-24: 저장된 줄에는 요약이 없어 다시 합칠 때마다 요약 속 숫자가 사라졌다(운영 23,195줄 모두 제목 숫자만).
    # 색인 줄이면 저장된 숫자를 먼저 그대로 둔다 — 지난 달 파일이 실행마다 바뀌지 않게.
    kept = raw.get("numbers") if raw.get("coverageIndexOnly") is True else None
    if isinstance(kept, list):
        values = [x for x in kept if isinstance(x, str) and 0 < len(x) <= 40] + values
    values = list(dict.fromkeys(values))[:12]
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


def month_of(published):
    when = parse_published(published)
    if when is None:
        raise ValueError("press_index_undated_row")
    return when.astimezone(KST).strftime("%Y-%m")


def hot_from_month(now):
    """latest 파일에 남기는 첫 달(이번 달과 지난달 — HOT_MONTHS=2)."""
    local = now.astimezone(KST)
    year, month = local.year, local.month - (HOT_MONTHS - 1)
    while month < 1:
        year, month = year - 1, month + 12
    return f"{year:04d}-{month:02d}"


def expand_index(hot, base):
    """latest(이번 달·지난달)에 coldShards 목록의 달 파일을 붙여 1년 색인 전체를 돌려준다.

    목록의 파일이 없거나 sha256·건수·달이 다르면 ValueError — 일부만 읽은 색인을 전체처럼 쓰지 않는다.
    coldShards가 없는 예전 형식은 그대로 돌려준다."""
    if not isinstance(hot, dict) or "coldShards" not in hot:
        return hot
    shards = hot.get("coldShards")
    items = hot.get("items")
    if (not isinstance(shards, list) or len(shards) > MAX_SHARDS
            or not isinstance(items, list) or hot.get("itemCount") != len(items)):
        raise ValueError("press_index_shard_manifest_invalid")
    rows = list(items)
    seen = set()
    for entry in shards:
        if not isinstance(entry, dict):
            raise ValueError("press_index_shard_manifest_invalid")
        name, month, count, digest = (entry.get("file"), entry.get("month"),
                                      entry.get("itemCount"), entry.get("sha256"))
        match = SHARD_FILE.fullmatch(name) if isinstance(name, str) else None
        if (match is None or match.group(1) != month or month in seen
                or type(count) is not int or count < 0
                or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
            raise ValueError("press_index_shard_manifest_invalid")
        seen.add(month)
        try:
            raw = (Path(base) / name).read_bytes()
        except OSError:
            raise ValueError("press_index_shard_missing") from None
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError("press_index_shard_hash_mismatch")
        try:
            doc = json.loads(raw.decode("utf-8"))
        except (UnicodeError, ValueError):
            raise ValueError("press_index_shard_invalid_json") from None
        if (not isinstance(doc, dict) or doc.get("status") != SHARD_STATUS
                or doc.get("month") != month or not isinstance(doc.get("items"), list)
                or doc.get("itemCount") != len(doc["items"]) or len(doc["items"]) != count):
            raise ValueError("press_index_shard_invalid")
        rows.extend(doc["items"])
    if hot.get("totalItemCount") != len(rows) or len(rows) > MAX_ENTRIES:
        raise ValueError("press_index_shard_total_mismatch")
    full = dict(hot)
    full["items"] = sorted(rows, key=lambda x: (str(x.get("published")), str(x.get("id"))), reverse=True)
    full["itemCount"] = len(rows)
    full["hotItemCount"] = len(items)
    return full


def shard_names(hot):
    """latest의 coldShards가 가리키는 달 파일(latest와 같은 폴더 기준 상대 경로)."""
    if not isinstance(hot, dict) or not isinstance(hot.get("coldShards"), list):
        return []
    return [x["file"] for x in hot["coldShards"]
            if isinstance(x, dict) and isinstance(x.get("file"), str) and SHARD_FILE.fullmatch(x["file"])]


def load_index(path):
    p = Path(path)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def load_full_index(path):
    """1년 색인 전체(latest + 달 파일). 파일이 없으면 None, 달 파일이 어긋나면 ValueError."""
    hot = load_index(path)
    return None if hot is None else expand_index(hot, Path(path).parent)


def _atomic_write_bytes(dest, data):
    dest.parent.mkdir(parents=True, exist_ok=True)
    temp = dest.with_suffix(dest.suffix + ".tmp")
    temp.write_bytes(data)
    temp.replace(dest)


def write_index(path, index):
    dest = Path(path)
    _atomic_write_bytes(dest, (json.dumps(index, ensure_ascii=False,
        separators=(",", ":"))+"\n").encode("utf-8"))


def write_split_index(path, full, now):
    """전체 색인을 latest(이번 달·지난달) + 달 파일로 나눠 쓴다. 달 파일 먼저, latest는 마지막.

    달 파일에는 생성 시각을 넣지 않는다 — 내용이 같으면 같은 바이트라 다시 쓰지 않는다(지난 달은 거의 그대로)."""
    base = Path(path).parent
    start = hot_from_month(now)
    hot_rows, months = [], {}
    for row in full["items"]:
        month = month_of(row["published"])
        if month >= start:
            hot_rows.append(row)
        else:
            months.setdefault(month, []).append(row)
    if len(months) > MAX_SHARDS:
        raise ValueError("press_index_too_many_month_shards")
    manifest = []
    for month in sorted(months, reverse=True):
        rows = months[month]
        doc = {"status": SHARD_STATUS, "month": month, "retentionDays": full["retentionDays"],
               "itemCount": len(rows), "proofOfNoPriorCoverage": False,
               "pressFulltextReviewed": False, "items": rows}
        data = (json.dumps(doc, ensure_ascii=False, separators=(",", ":"))+"\n").encode("utf-8")
        name = f"{SHARD_DIR}/{month}.json"
        dest = base / name
        if not dest.is_file() or dest.read_bytes() != data:
            _atomic_write_bytes(dest, data)
        manifest.append({"month": month, "file": name, "itemCount": len(rows),
                         "sha256": hashlib.sha256(data).hexdigest()})
    hot = {k: v for k, v in full.items() if k not in ("items", "hotItemCount")}
    hot.update({"hotFromMonth": start, "itemCount": len(hot_rows),
                "totalItemCount": len(full["items"]), "coldShards": manifest, "items": hot_rows})
    write_index(path, hot)
    return hot


def update_from_news(new_items, *, path="digests/press_coverage_index_latest.json",
                     now=None):
    now = now or datetime.now(KST)
    previous = load_full_index(path)   # 달 파일이 어긋나면 여기서 멈춘다(기록을 0으로 덮지 않음)
    result = merge_index(previous, new_items, now=now)
    write_split_index(path, result, now)
    return result
