from __future__ import annotations

import html
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from scripts.rss_concurrent import collect_feeds
from scripts.global_news_pipeline import shortlist, translate_selected
from scripts.auto_news_feed_health import build as build_feed_health, persist as persist_feed_health

KST = ZoneInfo("Asia/Seoul")
DATA = Path("data.json")
GLOBAL_FEED_CHECKS=[]

QUERIES = [
    ("Reuters", "site:reuters.com automotive OR EV OR electric vehicle OR battery OR auto tariff OR Hyundai OR Kia OR LG Energy Solution OR Samsung SDI OR SK On OR CATL OR BYD"),
    ("Bloomberg", "site:bloomberg.com automotive OR EV OR electric vehicle OR battery OR auto tariff OR Hyundai OR Kia OR LG Energy Solution OR Samsung SDI OR SK On"),
    ("Nikkei Asia", "site:asia.nikkei.com automotive OR EV OR battery OR Hyundai OR Kia OR Toyota OR Panasonic OR CATL OR BYD"),
    ("Automotive News", "site:autonews.com EV OR battery OR supplier OR Hyundai OR Kia OR GM OR Ford OR Toyota OR tariffs"),
    ("Automotive World", "site:automotiveworld.com EV OR battery OR OEM OR supplier OR Hyundai OR Kia OR Toyota OR China"),
    ("WardsAuto", "site:wardsauto.com EV OR battery OR supplier OR production OR tariff"),
    ("InsideEVs", "site:insideevs.com EV OR battery OR Hyundai OR Kia OR BYD OR Tesla OR CATL"),
    ("Electrek", "site:electrek.co EV OR battery OR Tesla OR Hyundai OR Kia OR BYD"),
    ("CnEVPost", "site:cnevpost.com BYD OR CATL OR Xiaomi OR Zeekr OR Geely OR EV OR battery"),
    ("CarNewsChina", "site:carnewschina.com BYD OR Geely OR Zeekr OR Xiaomi OR CATL OR EV"),
    ("EV.com", "site:ev.com EV OR battery OR charging OR automotive"),
    ("The Verge", "site:theverge.com EV OR Tesla OR autonomous OR battery OR car"),
]

KOREA_SIGNALS = [
    "hyundai", "kia", "genesis", "hyundai mobis", "lg energy solution", "lg energy", "samsung sdi", "sk on",
    "sk innovation", "posco", "hanwha", "hl mando", "hyundai transys", "hyundai wia", "kg mobility",
    "gm korea", "renault korea", "korea", "south korea", "korean", "seoul"
]
INDUSTRY = [
    "ev", "electric vehicle", "battery", "ess", "autonomous", "self-driving", "tariff", "trade", "recall",
    "plant", "factory", "production", "investment", "contract", "supply", "order", "sales", "price",
    "lithium", "lfp", "solid-state", "charging", "software", "robotaxi", "export"
]
HIGH_IMPACT = [
    "tariff", "investment", "contract", "order", "supply", "factory", "plant", "production", "recall",
    "fire", "battery", "ess", "autonomous", "export", "sales", "price", "shutdown", "strike", "union"
]


def get(url: str, timeout: int = 15) -> bytes:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 AutoIndustryGlobalRadar/1.1", "Accept": "application/rss+xml,application/xml,text/xml,*/*"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def clean(text: str) -> str:
    text = re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>", " ", text or "", flags=re.I | re.S)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def looks_korean(text: str) -> bool:
    return bool(re.search(r"[가-힣]", text or ""))


def translate(text: str) -> tuple[str, str]:
    text = clean(text)[:1000]
    if not text:
        return "", "empty"
    if looks_korean(text) and not re.search(r"\b(the|and|of|to|for|with|after|before|reportedly|starts|launches|says)\b", text, re.I):
        return text, "already_ko"

    url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=ko&dt=t&q=" + urllib.parse.quote(text)
    for attempt in range(2):
        try:
            raw = json.loads(get(url, 8))
            translated = "".join(part[0] for part in raw[0] if part and part[0]).strip()
            if translated and (looks_korean(translated) or not re.search(r"[A-Za-z]", text)):
                return translated, "translated"
        except Exception:
            pass
        time.sleep(0.35 * (attempt + 1))

    # Second provider fallback. It is intentionally only used when Google translation failed.
    try:
        q = urllib.parse.quote(text[:500])
        mm = f"https://api.mymemory.translated.net/get?q={q}&langpair=en|ko"
        raw = json.loads(get(mm, 8))
        translated = str(raw.get("responseData", {}).get("translatedText", "")).strip()
        if translated and looks_korean(translated):
            return translated, "translated_fallback"
    except Exception:
        pass

    return text, "translation_failed"


def parse(source: str, query: str) -> list[dict]:
    started=time.monotonic()
    url = "https://news.google.com/rss/search?q=" + urllib.parse.quote(query) + "&hl=en-US&gl=US&ceid=US:en"
    try:
        root = ET.fromstring(get(url))
        if root.tag!="rss" or root.find("channel") is None:
            raise ValueError("rss_channel_missing")
    except Exception as exc:
        GLOBAL_FEED_CHECKS.append({
            "category":source[:40],"globalFeed":True,
            "status":"malformed_rss" if isinstance(exc,(ET.ParseError,ValueError))
                    else "transport_or_xml_error",
            "recentRows":0,"errorType":type(exc).__name__,
            "durationMs":min(600000,int((time.monotonic()-started)*1000))})
        return []
    cutoff = datetime.now(KST) - timedelta(hours=96)
    rows = []
    for item in root.findall("./channel/item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        desc = clean(item.findtext("description") or "")
        src = item.find("source")
        actual_source = (src.text or "").strip() if src is not None else source
        if not title or not link:
            continue
        try:
            dt = parsedate_to_datetime(pub).astimezone(KST)
        except Exception:
            dt = datetime.now(KST)
        if dt < cutoff:
            continue
        text = (title + " " + desc).lower()
        industry_score = sum(1 for x in INDUSTRY if x in text)
        korea_score = sum(1 for x in KOREA_SIGNALS if x in text)
        if industry_score == 0:
            continue
        if korea_score == 0 and industry_score < 2:
            continue
        impact = sum(1 for x in HIGH_IMPACT if x in text)
        score = min(99, 45 + korea_score * 9 + min(industry_score, 5) * 4 + min(impact, 5) * 4)

        # Translation happens after cross-feed headline deduplication and priority ranking.
        # Calling external translation here multiplies latency for duplicate RSS hits.
        rows.append({
            "title": title,
            "url": link,
            "published": dt.isoformat(),
            "sourceName": actual_source or source,
            "category": "글로벌",
            "global": True,
            "globalSource": source,
            "summary": desc[:1000],
            "globalScore": score,
            "koTitle": "",
            "koSummary": "",
            "translationStatus": "not_attempted_until_deduplication",
            "globalWhy": "한국 자동차·부품·배터리 산업과 연결되거나 글로벌 공급망·통상·생산 변화가 큰 해외 신호입니다.",
            "globalPitch": score >= 70,
        })
    GLOBAL_FEED_CHECKS.append({
        "category":source[:40],"globalFeed":True,
        "status":"checked_recent_rows" if rows else "checked_no_recent_rows",
        "recentRows":min(100,len(rows)),"errorType":None,
        "durationMs":min(600000,int((time.monotonic()-started)*1000))})
    return rows


def unexpected_feed_error(category,is_global,error_type):
    GLOBAL_FEED_CHECKS.append({
        "category":category[:40],"globalFeed":True,
        "status":"transport_or_xml_error","recentRows":0,"errorType":error_type})


def main() -> None:
    try:
        current = json.loads(DATA.read_text(encoding="utf-8"))
    except Exception:
        current = []

    domestic = [x for x in current if not x.get("global")]
    try:
        previous_global=json.loads(Path("global.json").read_text(encoding="utf-8"))
        if not isinstance(previous_global,list):previous_global=[]
    except (OSError,ValueError):previous_global=[]

    # Twelve independent source-bound queries: max 3 simultaneous RSS fetches.
    _,raw_globals=collect_feeds([],QUERIES,
        lambda cat,q,global_feed=False,source_hint="":parse(source_hint,q),
        on_error=unexpected_feed_error,workers=3)
    candidates=shortlist(raw_globals,limit=32)
    unique=translate_selected(candidates,translate,
        previous=previous_global,workers=3)
    unique=[x for x in unique if x.get("koTitle") and
            x.get("translationStatus")!="translation_failed"]
    diagnostic=build_feed_health(GLOBAL_FEED_CHECKS,expected=len(QUERIES),
        news_items=len(unique),now=datetime.now(KST),threshold=1)
    persist_feed_health(diagnostic,Path("digests/global_news_feed_health_latest.json"))
    # Do not overwrite previously verified worldwide stories with a blackout.
    if not unique:
        raise SystemExit("No translated global stories: previous news dataset preserved")

    merged = domestic + unique
    merged.sort(key=lambda x: x.get("published", ""), reverse=True)

    DATA.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    Path("data.js").write_text("window.ITEMS = " + json.dumps(merged, ensure_ascii=False, indent=2) + ";\n", encoding="utf-8")
    Path("global.json").write_text(json.dumps(unique, ensure_ascii=False, indent=2), encoding="utf-8")
    reused=sum(bool(x.get("translationCacheUsed")) for x in unique)
    print(f"global radar: {len(unique)} source-filtered translated records; "
          f"{reused} exact-title/URL/summary translations reused; "
          f"RSS query errors {diagnostic['errorQueries']}/{len(QUERIES)}; "
          f"total feed {len(merged)}")


if __name__ == "__main__":
    main()
