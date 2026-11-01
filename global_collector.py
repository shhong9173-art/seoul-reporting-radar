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
from scripts.global_news_pipeline import shortlist, summarize_selected, translate_selected
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
    # 11-01 기자 요청("내 출입처 관련 외신"): 자동차·배터리만 보던 검색에 철강·비철·전력기기·전선·에너지·화학·타이어·부품 출입처를 더한다.
    # 매체 제한 없이 출입처 영문 이름으로 찾고, 국내 매체의 영문판(코리아헤럴드·연합 등)은 아래 DOMESTIC_EN으로 뺀다(외신만).
    ("출입처·철강비철", '"POSCO" OR "Hyundai Steel" OR "Dongkuk Steel" OR "SeAH Steel" OR "KG Steel" OR "Korea Zinc" OR "Young Poong" OR "LS MnM"'),
    ("출입처·전력기기전선", '"HD Hyundai Electric" OR "LS Electric" OR "Hyosung Heavy Industries" OR "LS Cable" OR "Taihan Cable" OR "Doosan Enerbility"'),
    ("출입처·에너지화학", '"Hanwha Qcells" OR "Hanwha Solutions" OR "OCI Holdings" OR "GS Caltex" OR "Korean refiner" OR "Korean steelmakers"'),
    ("출입처·타이어부품", '"Hankook Tire" OR "Kumho Tire" OR "Nexen Tire" OR "Hyundai Mobis" OR "HL Mando" OR "Hyundai Wia" OR "KG Mobility" OR "GM Korea"'),
]

# 출입처 검색(매체 제한 없음)은 이 외신 매체만 받는다 — 11-01 탐침 63: 매체 제한 없이 찾으니 48건 중 국내 한글 기사(헤럴드경제·매일경제·조선일보 등)와
# 주가 모음 사이트(BigGo Finance·TradingView·Yahoo Finance)가 대부분이었다.
FOREIGN_OK = re.compile(r"reuters|bloomberg|nikkei|financial times|\bft\b|wall street journal|\bwsj\b|cnbc|associated press|\bap news\b|economist|fortune|barron|"
                        r"s&p global|platts|fastmarkets|argus|mining\.com|kallanish|metal bulletin|utility dive|power engineering|t&d world|recharge|pv magazine|pv tech|"
                        r"electrek|insideevs|automotive news|automotive world|just auto|just-auto|wardsauto|tire business|tyrepress|rubber|tire technology|"
                        r"energy-storage|energy storage news|chemical & engineering|icis|hydrogen insight|financial post|politico|axios|the information|"
                        r"south china morning post|scmp|caixin|nikkei asia|the japan times|asahi|digitimes|electrive|autocar|carscoops|motor1|the verge|techcrunch", re.I)

# 국내 매체 영문판·국내 통신 — 외신 화면에서 뺀다(이미 국내 보도).
DOMESTIC_EN = re.compile(r"korea herald|korea times|joongang|yonhap|korea economic daily|ked global|businesskorea|business korea|pulse by maeil|maeil|"
                         r"chosun|donga|hankyoreh|aju|seoul economic|the investor|korea bizwire|korea\.net|arirang|kbs|mbc|sbs|kpop|asiae|"
                         r"etnews|thelec|the elec|biz\.chosun|koreatechtoday|koreaittimes|newsis|news1|edaily|businesspost|mk\.co\.kr|hankyung", re.I)

KOREA_SIGNALS = [
    "hyundai", "kia", "genesis", "hyundai mobis", "lg energy solution", "lg energy", "samsung sdi", "sk on",
    "sk innovation", "posco", "hanwha", "hl mando", "hyundai transys", "hyundai wia", "kg mobility",
    "gm korea", "renault korea", "korea", "south korea", "korean", "seoul",
    # 철강·비철·전력기기·전선·에너지·화학·타이어 출입처
    "hyundai steel", "dongkuk", "seah", "kg steel", "korea zinc", "young poong", "ls mnm", "ls electric", "ls cable", "taihan",
    "hd hyundai electric", "hyosung heavy", "doosan enerbility", "qcells", "oci holdings", "gs caltex", "hankook tire", "kumho tire", "nexen tire",
]
INDUSTRY = [
    "ev", "electric vehicle", "battery", "ess", "autonomous", "self-driving", "tariff", "trade", "recall",
    "plant", "factory", "production", "investment", "contract", "supply", "order", "sales", "price",
    "lithium", "lfp", "solid-state", "charging", "software", "robotaxi", "export",
    "steel", "steelmaker", "zinc", "copper", "smelter", "transformer", "transformers", "cable", "cables", "grid", "power equipment",
    "solar", "polysilicon", "refinery", "refiner", "petrochemical", "chemical", "tire", "tires", "nuclear", "turbine", "antidumping", "anti-dumping",
    "reactor", "reactors", "smr", "wind", "offshore wind", "subsea", "hvdc", "substation", "module", "modules", "wafer", "cell", "cells", "lng",
]
HIGH_IMPACT = [
    "tariff", "investment", "contract", "order", "supply", "factory", "plant", "production", "recall",
    "fire", "battery", "ess", "autonomous", "export", "sales", "price", "shutdown", "strike", "union"
]


def _word_re(words):
    # 낱말 경계로만 센다 — 예전 부분 문자열 비교는 'ev'가 every·seven, 'ess'가 business·less, 'oci'가 social에도 걸렸다(11-01 점검).
    return [re.compile(r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])") for w in words]


INDUSTRY_RE, KOREA_RE, IMPACT_RE = _word_re(INDUSTRY), _word_re(KOREA_SIGNALS), _word_re(HIGH_IMPACT)


def hits(patterns, text: str) -> int:
    return sum(1 for p in patterns if p.search(text))


def title_only(summary: str, title: str) -> bool:
    """구글 뉴스 RSS 설명 칸은 '제목 + 매체 이름'뿐이다 — 이걸 '요약'으로 번역하지 않는다(11-01: 요약 칸이 제목 번역 되풀이)."""
    norm = lambda t: re.sub(r"[^a-z0-9]+", "", (t or "").lower())
    s, t = norm(summary), norm(re.sub(r"\s+-\s+[^-]+$", "", title or ""))
    return not s or (bool(t) and s.startswith(t) and len(s) - len(t) <= 60)


FEED_UA = "seoul-reporting-radar RSS reader (+https://github.com/shhong9173-art/seoul-reporting-radar)"


def get(url: str, timeout: int = 15, ua: str = "Mozilla/5.0 AutoIndustryGlobalRadar/1.1") -> bytes:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": ua, "Accept": "application/rss+xml,application/xml,text/xml,*/*"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def clean(text: str) -> str:
    text = re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>", " ", text or "", flags=re.I | re.S)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def looks_korean(text: str) -> bool:
    return bool(re.search(r"[가-힣]", text or ""))


WORKER_TRANSLATE = "https://seoul-reporting-radar.shhong9173.workers.dev/ingest/translate"


def worker_translate(text: str) -> str:
    """워커(Cloudflare Workers AI)에 번역을 맡긴다 — MCP_ACCESS_TOKEN이 있을 때만. 실패하면 빈 문자열(다음 번역기로)."""
    import os
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    if not token:
        return ""
    req = urllib.request.Request(WORKER_TRANSLATE, data=json.dumps({"texts": [text]}).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                                          "User-Agent": "seoul-reporting-radar global_collector"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            res = (json.loads(r.read()).get("results") or [{}])[0]
    except Exception:
        return ""
    ko = str(res.get("ko") or "").strip()
    return ko if res.get("status", "").startswith("translated_ai") and looks_korean(ko) else ""


def translate(text: str) -> tuple[str, str]:
    text = clean(text)[:1000]
    if not text:
        return "", "empty"
    if looks_korean(text) and not re.search(r"\b(the|and|of|to|for|with|after|before|reportedly|starts|launches|says)\b", text, re.I):
        return text, "already_ko"
    # 11-01: 구글 비공식 번역 주소가 Actions에서 막혀 거의 전부 보조 번역기로 넘어갔다 — 워커(Workers AI)를 먼저 쓴다.
    # 제목 끝 매체 이름(" - Automotive News")은 떼고 보낸다(11-01 운영: '- 오토모티브 뉴스'·'- 인사이드EV스'가 번역문에 남았다).
    if len(text) < 300:
        text = re.sub(r"\s+[-–—|]\s+[^-–—|]{2,60}$", "", text).strip() or text
    ko = worker_translate(text)
    if ko:
        return ko, "translated_ai"

    url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=ko&dt=t&q=" + urllib.parse.quote(text)
    # 11-01 운영: 32건 중 16건이 보조 번역기(MyMemory)로 넘어가 품질이 낮았다('jailbreaking FSD' → '탈옥 금감원').
    # 주 번역기를 세 번까지, 간격을 늘려(1·2·4초) 다시 묻는다.
    for attempt in range(3):
        try:
            raw = json.loads(get(url, 10))
            translated = "".join(part[0] for part in raw[0] if part and part[0]).strip()
            if translated and (looks_korean(translated) or not re.search(r"[A-Za-z]", text)):
                return translated, "translated"
        except Exception:
            pass
        time.sleep(2 ** attempt)

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


# 매체 자체 RSS — 본문 앞부분(설명)이나 전문(content:encoded)이 있어 한국어 요약을 만들 수 있다(11-01 탐침 65: GitHub 서버에서 열림).
# 구글 뉴스 검색 결과와 같은 기사면 본문을 붙이고 주소를 매체 직접 주소로 바꾼다. 영어 본문은 요약에만 쓰고 저장하지 않는다(공개 저장소).
PUBLISHER_FEEDS = [
    ("Electrek", "https://electrek.co/feed/"), ("InsideEVs", "https://insideevs.com/rss/articles/all/"),
    ("CnEVPost", "https://cnevpost.com/feed/"), ("CarNewsChina", "https://carnewschina.com/feed/"),
    ("Automotive World", "https://www.automotiveworld.com/feed/"), ("Automotive News", "https://www.autonews.com/arc/outboundfeeds/rss/"),
    ("Just Auto", "https://www.just-auto.com/feed/"), ("electrive", "https://www.electrive.com/feed/"),
    ("Utility Dive", "https://www.utilitydive.com/feeds/news/"), ("pv magazine", "https://www.pv-magazine.com/feed/"),
    ("Energy-Storage.news", "https://www.energy-storage.news/feed/"),
    # 11-01 출입처 외신 넓히기(탐침 68: GitHub 서버에서 열리는 것만) — 철강·비철·전력기기·전선·원전·태양광·타이어
    ("GMK Center", "https://gmk.center/en/feed/"), ("MetalMiner", "https://agmetalminer.com/feed/"),
    ("Northern Miner", "https://www.northernminer.com/feed/"), ("Transformers Magazine", "https://transformers-magazine.com/feed/"),
    ("offshoreWIND.biz", "https://www.offshorewind.biz/feed/"), ("Offshore Energy", "https://www.offshore-energy.biz/feed/"),
    ("Canary Media", "https://www.canarymedia.com/rss"), ("World Nuclear News", "https://www.world-nuclear-news.org/rss"),
    ("PV Tech", "https://www.pv-tech.org/feed/"), ("Tire Business", "https://www.tirebusiness.com/arc/outboundfeeds/rss/"),
    ("Tyrepress", "https://www.tyrepress.com/feed/"), ("Automotive News Europe", "https://europe.autonews.com/arc/outboundfeeds/rss/"),
]
# 전력·태양광·에너지저장 전문지는 한국 회사 이름이 나올 때만(미국 전력망 일반 기사로 넘치지 않게)
STRICT_KOREA = {"Utility Dive", "pv magazine", "Energy-Storage.news", "GMK Center", "MetalMiner", "Northern Miner", "Transformers Magazine",
                "offshoreWIND.biz", "Offshore Energy", "Canary Media", "World Nuclear News", "PV Tech", "Tire Business", "Tyrepress"}
CONTENT = "{http://purl.org/rss/1.0/modules/content/}encoded"


def title_key(title: str) -> str:
    """구글 뉴스 제목 끝 ' - 매체'를 떼고 글자·숫자만 — 매체 RSS 제목과 맞춰 본다."""
    t = re.sub(r"\s+[-–—|]\s+[^-–—|]{2,60}$", "", title or "")
    return re.sub(r"[^a-z0-9]+", "", t.lower())


def score_text(text: str):
    """(점수, 출입처 신호 수) 또는 None(업종 낱말 없음·한국 신호 없이 업종 낱말 1개)."""
    industry_score = hits(INDUSTRY_RE, text)
    korea_score = hits(KOREA_RE, text)
    if industry_score == 0 or (korea_score == 0 and industry_score < 2):
        return None
    impact = hits(IMPACT_RE, text)
    return min(99, 45 + korea_score * 9 + min(industry_score, 5) * 4 + min(impact, 5) * 4), korea_score


def parse_publisher(source: str, url: str) -> list[dict]:
    started = time.monotonic()
    try:
        # 매체 RSS는 레이더 이름을 밝힌 요청으로 읽는다(11-01 탐침 65·66: Automotive News RSS가 브라우저 흉내 이름 요청은 거절, 이 이름은 200)
        root = ET.fromstring(get(url, 20, ua=FEED_UA))
    except Exception as exc:
        GLOBAL_FEED_CHECKS.append({"category": source[:40], "globalFeed": True, "status": "transport_or_xml_error", "recentRows": 0,
                                   "errorType": type(exc).__name__, "durationMs": min(600000, int((time.monotonic() - started) * 1000))})
        return []
    cutoff = datetime.now(KST) - timedelta(hours=96)
    rows = []
    for item in root.iter("item"):
        title = clean(item.findtext("title") or "")
        link = (item.findtext("link") or "").strip()
        if not title or not link.startswith("https://") or looks_korean(title):
            continue
        try:
            dt = parsedate_to_datetime((item.findtext("pubDate") or "").strip()).astimezone(KST)
        except Exception:
            continue   # 날짜 없는 항목을 오늘 기사로 만들지 않는다
        if dt < cutoff:
            continue
        body = clean(item.findtext(CONTENT) or "") or clean(item.findtext("description") or "")
        scored = score_text((title + " " + body[:800]).lower())
        if not scored or (source in STRICT_KOREA and scored[1] == 0):   # 전문지는 한국·출입처 이름이 나올 때만
            continue
        rows.append({"title": title, "url": link, "published": dt.isoformat(), "sourceName": source, "category": "글로벌", "global": True,
                     "globalSource": source, "summary": "", "globalScore": scored[0], "koTitle": "", "koSummary": "",
                     "translationStatus": "not_attempted_until_deduplication", "articleText": body[:2000], "summarySource": f"{source} RSS",
                     "globalWhy": "한국 자동차·부품·배터리·전력·에너지 산업과 연결되거나 글로벌 공급망·통상·생산 변화가 큰 해외 신호입니다.",
                     "globalBeat": scored[1] > 0 and source in STRICT_KOREA, "globalPitch": scored[0] >= 70})
    GLOBAL_FEED_CHECKS.append({"category": source[:40], "globalFeed": True, "status": "checked_recent_rows" if rows else "checked_no_recent_rows",
                               "recentRows": min(100, len(rows)), "errorType": None, "durationMs": min(600000, int((time.monotonic() - started) * 1000))})
    return rows


def attach_publisher_text(google_rows: list[dict], publisher_rows: list[dict]) -> list[dict]:
    """같은 기사(제목이 같으면)는 매체 RSS 본문·직접 주소를 구글 뉴스 항목에 붙이고, 남은 매체 RSS 기사는 그대로 후보에 더한다."""
    by_key = {}
    for p in publisher_rows:
        by_key.setdefault(title_key(p["title"]), p)
    used = set()
    out = []
    for g in google_rows:
        k = title_key(g.get("title", ""))
        p = by_key.get(k)
        if p and k:
            g = {**g, "url": p["url"], "articleText": p["articleText"], "summarySource": p["summarySource"]}
            used.add(k)
        out.append(g)
    out += [p for k, p in by_key.items() if k not in used]
    return out


def worker_summarize(title: str, text: str) -> str:
    """워커(Workers AI)로 매체 RSS 본문 발췌를 한국어 2~3문장 요약. 실패하면 빈 문자열."""
    import os
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    if not token or not text.strip():
        return ""
    req = urllib.request.Request(WORKER_TRANSLATE, data=json.dumps({"kind": "summary", "texts": [f"{title}\n\n{text}"]}).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                                          "User-Agent": "seoul-reporting-radar global_collector"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            res = (json.loads(r.read()).get("results") or [{}])[0]
    except Exception:
        return ""
    ko = str(res.get("ko") or "").strip()
    return ko if res.get("status") == "summarized_ai" and looks_korean(ko) else ""


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
    # 출입처(철강·전력기기 등) 외신은 드물다(11-01 탐침 64: 96시간에 1건) — 출입처 검색은 7일까지 본다
    cutoff = datetime.now(KST) - timedelta(hours=168 if source.startswith("출입처") else 96)
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
        if DOMESTIC_EN.search(actual_source or "") or looks_korean(title) or looks_korean(actual_source or ""):
            continue   # 외신만: 국내 매체 영문판·한글 기사는 뺀다
        if source.startswith("출입처") and not FOREIGN_OK.search(actual_source or ""):
            continue   # 매체 제한 없는 출입처 검색은 믿을 만한 외신만
        try:
            dt = parsedate_to_datetime(pub).astimezone(KST)
        except Exception:
            dt = datetime.now(KST)
        if dt < cutoff:
            continue
        scored = score_text((title + " " + desc).lower())
        if not scored:
            continue
        score = scored[0]

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
            "summary": "" if title_only(desc, title) else desc[:1000],
            "globalScore": score,
            "koTitle": "",
            "koSummary": "",
            "translationStatus": "not_attempted_until_deduplication",
            "globalWhy": ("출입처 관련 해외 보도" if source.startswith("출입처") else
                          "한국 자동차·부품·배터리 산업과 연결되거나 글로벌 공급망·통상·생산 변화가 큰 해외 신호입니다."),
            "globalBeat": source.startswith("출입처"),
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
    publisher_rows=[]
    for name,feed_url in PUBLISHER_FEEDS:   # 매체 RSS를 차례로(한 곳당 한 번)
        publisher_rows+=parse_publisher(name,feed_url)
    raw_globals=attach_publisher_text(raw_globals,publisher_rows)
    candidates=shortlist(raw_globals,limit=60)
    unique=translate_selected(candidates,translate,
        previous=previous_global,workers=2)
    unique=summarize_selected(unique,worker_summarize,previous=previous_global,workers=2)
    unique=[x for x in unique if x.get("koTitle") and
            x.get("translationStatus")!="translation_failed"]
    diagnostic=build_feed_health(GLOBAL_FEED_CHECKS,expected=len(QUERIES)+len(PUBLISHER_FEEDS),
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
    statuses={}
    for x in unique:
        statuses[x.get("translationStatus")]=statuses.get(x.get("translationStatus"),0)+1
    print(f"global translation status counts: {statuses}")
    print(f"global summaries: {sum(1 for x in unique if x.get('summaryTranslationStatus')=='summarized_ai')} AI 요약 / "
          f"publisher RSS rows {len(publisher_rows)}")
    print(f"global radar: {len(unique)} source-filtered translated records; "
          f"{reused} exact-title/URL/summary translations reused; "
          f"RSS query errors {diagnostic['errorQueries']}/{len(QUERIES)}; "
          f"total feed {len(merged)}")


if __name__ == "__main__":
    main()
