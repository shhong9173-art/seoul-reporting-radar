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

KST = ZoneInfo("Asia/Seoul")
DATA = Path("data.json")

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
    for attempt in range(3):
        try:
            raw = json.loads(get(url, 12))
            translated = "".join(part[0] for part in raw[0] if part and part[0]).strip()
            if translated and (looks_korean(translated) or not re.search(r"[A-Za-z]", text)):
                return translated, "translated"
        except Exception:
            pass
        time.sleep(0.7 * (attempt + 1))

    # Second provider fallback. It is intentionally only used when Google translation failed.
    try:
        q = urllib.parse.quote(text[:500])
        mm = f"https://api.mymemory.translated.net/get?q={q}&langpair=en|ko"
        raw = json.loads(get(mm, 12))
        translated = str(raw.get("responseData", {}).get("translatedText", "")).strip()
        if translated and looks_korean(translated):
            return translated, "translated_fallback"
    except Exception:
        pass

    return text, "translation_failed"


def parse(source: str, query: str) -> list[dict]:
    url = "https://news.google.com/rss/search?q=" + urllib.parse.quote(query) + "&hl=en-US&gl=US&ceid=US:en"
    try:
        root = ET.fromstring(get(url))
    except Exception:
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

        ko_title, title_status = translate(title)
        ko_summary, summary_status = translate(desc[:900])
        # Never label an untranslated English string as translated.
        translation_status = "translated" if title_status.startswith("translated") else title_status

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
            "koTitle": ko_title,
            "koSummary": ko_summary,
            "translationStatus": translation_status,
            "globalWhy": "한국 자동차·부품·배터리 산업과 연결되거나 글로벌 공급망·통상·생산 변화가 큰 해외 신호입니다.",
            "globalPitch": score >= 70,
        })
    return rows


def main() -> None:
    try:
        current = json.loads(DATA.read_text(encoding="utf-8"))
    except Exception:
        current = []

    domestic = [x for x in current if not x.get("global")]
    globals_: list[dict] = []
    for source, query in QUERIES:
        globals_.extend(parse(source, query))

    seen = set()
    unique = []
    for item in sorted(globals_, key=lambda x: x["published"], reverse=True):
        key = re.sub(r"\s+", " ", item["title"].lower()).strip()
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    # Drop items whose title could not be translated; they are not useful for the Korean newsroom view.
    unique = [x for x in unique if x.get("translationStatus") != "translation_failed" and x.get("koTitle")]
    unique = sorted(unique, key=lambda x: (x.get("globalScore", 0), x["published"]), reverse=True)[:80]
    merged = domestic + unique
    merged.sort(key=lambda x: x.get("published", ""), reverse=True)

    DATA.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    Path("data.js").write_text("window.ITEMS = " + json.dumps(merged, ensure_ascii=False, indent=2) + ";\n", encoding="utf-8")
    Path("global.json").write_text(json.dumps(unique, ensure_ascii=False, indent=2), encoding="utf-8")
    failed = sum(1 for x in unique if x.get("translationStatus") == "translation_failed")
    print(f"global radar: {len(unique)} translated records retained; {failed} translation failures dropped; total feed: {len(merged)}")


if __name__ == "__main__":
    main()
