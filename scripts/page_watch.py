"""출입처 해외 공식 페이지 변경 감시: 출시 시점·가격·판매 상태·차종 목록 문구의 변화.

- data/official_page_watch.json의 페이지를 열어 '신호 문구'를 뽑는다.
  출시 시점(Coming Spring 2027 등), 한정 물량, 가격(Starting MSRP $..), 판매 상태(sold out·reserve 등), 연식+차명.
- 직전 상태(기자 전용 저장소)와 비교해 추가·삭제된 문구를 '변경'으로 남긴다.
  처음 보는 페이지는 웹 아카이브(Wayback)의 약 45일 전 사본을 기준으로 비교한다.
- 페이지 문구 변화는 공식 발표가 아니다. 변경 시점·사유는 회사 확인이 필요하다.
- 결과는 기자 전용 저장소(page-watch)로만. 공개 로그에는 건수와 페이지별 응답 코드만.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

KST = dt.timezone(dt.timedelta(hours=9))
SCHEMA = "page_watch/v1"
WATCH = ROOT / "data" / "official_page_watch.json"
BASELINE_DAYS = 45
KEEP_EVENTS_DAYS = 90
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
SEASON = r"(?:(?:early|late|mid[- ]?)\s*)?(?:spring|summer|fall|autumn|winter|q[1-4])"
PATTERNS = {
    "timing": re.compile(
        r"\b(?:coming|arriving|available|on sale|launch(?:es|ing)?|expected|due|in dealerships)\b[^.!?\n]{0,40}?"
        rf"\b(?:{SEASON}\s*,?\s*20[2-3]\d|20[2-3]\d|soon)\b", re.I),
    "limited": re.compile(r"\b(?:extremely\s+|very\s+)?limited\s+(?:availability|production|quantities|run|edition)\b", re.I),
    "price": re.compile(r"(?:starting\s+(?:msrp|at|from|price)|msrp(?:\s+from)?|from)\s*:?\s*\$\s?\d{2,3},\d{3}"
                        r"|\$\s?\d{2,3},\d{3}\s*(?:\*\s*)?(?:starting\s+)?msrp", re.I),
    "status": re.compile(r"\b(?:sold\s+out|discontinued|no\s+longer\s+available|reservations?\s+(?:are\s+)?(?:now\s+)?open"
                         r"|pre-?order|reserve\s+(?:yours|now|one)|order\s+now|notify\s+me|get\s+updates|sign\s+up\s+for\s+updates)\b", re.I),
    "models": re.compile(r"\b20[2-3]\d\s+(?:Hyundai\s+|Kia\s+|Genesis\s+)?(?:IONIQ|Ioniq|EV\d|GV\d{2}|G\d{2}|Palisade|Santa\s+Fe|Santa\s+Cruz|"
                         r"Tucson|Elantra|Sonata|Kona|Venue|Telluride|Sorento|Sportage|Seltos|Carnival|Niro|K4|K5|Soul|Electrified\s+G\w+)"
                         r"(?:\s+(?:\d|N|Hybrid|Plug-in Hybrid|Electric|XRT|X-Pro|Line|GT)){0,2}\b"),
}
CATEGORY_KO = {"timing": "출시 시점", "limited": "한정 물량", "price": "가격", "status": "판매 상태", "models": "연식·차명"}


def visible_text(raw):
    t = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", raw)
    metas = " ".join(re.findall(r'(?is)<meta[^>]+(?:name|property)="(?:description|og:description|og:title)"[^>]+content="([^"]*)"', raw))
    title = " ".join(re.findall(r"(?is)<title[^>]*>(.*?)</title>", raw))
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", html.unescape(f"{title} {metas} {t}")).strip()


def signals(text):
    out = {}
    for cat, rx in PATTERNS.items():
        found = []
        for m in rx.finditer(text):
            s = re.sub(r"\s+", " ", m.group(0)).strip()
            if s.lower() not in (f.lower() for f in found):
                found.append(s)
        out[cat] = sorted(found, key=str.lower)[:40]
    return out


def diff(old, new):
    added, removed = {}, {}
    for cat in PATTERNS:
        o = {s.lower(): s for s in (old or {}).get(cat, [])}
        n = {s.lower(): s for s in (new or {}).get(cat, [])}
        a = [n[k] for k in n.keys() - o.keys()]
        r = [o[k] for k in o.keys() - n.keys()]
        if a:
            added[cat] = sorted(a, key=str.lower)
        if r:
            removed[cat] = sorted(r, key=str.lower)
    return added, removed


def fetch(url, *, get=None):
    if get is None:
        import requests
        get = requests.get
    try:
        r = get(url, headers=HEADERS, timeout=30, allow_redirects=True)
    except Exception as e:
        return {"status": "failed", "error": type(e).__name__}
    if r.status_code != 200:
        return {"status": "failed", "error": f"HTTP {r.status_code}"}
    body = r.text if hasattr(r, "text") else r.content.decode("utf-8", "replace")
    if len(body) < 2000 or re.search(r"(?i)access denied|captcha|are you a robot|request unsuccessful", body[:5000]):
        return {"status": "failed", "error": "차단·확인 페이지 의심"}
    return {"status": "ok", "html": body}


def wayback(url, day, *, get=None):
    """Closest archived copy at or before `day` (YYYYMMDD) → (date, html) or (None, None)."""
    if get is None:
        import requests
        get = requests.get
    try:
        r = get("https://archive.org/wayback/available", params={"url": url, "timestamp": day}, headers=HEADERS, timeout=30)
        snap = (r.json().get("archived_snapshots") or {}).get("closest") or {}
        ts = snap.get("timestamp")
        if not snap.get("available") or not ts or str(snap.get("status")) != "200":
            return None, None
        raw = get(f"https://web.archive.org/web/{ts}id_/{url}", headers=HEADERS, timeout=40)
        if raw.status_code != 200:
            return None, None
        return f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}", (raw.text if hasattr(raw, "text") else raw.content.decode("utf-8", "replace"))
    except Exception:
        return None, None


def run(pages, *, now, previous=None, get=None, sleep=time.sleep):
    prev_pages = {p["id"]: p for p in (previous or {}).get("pages", []) if isinstance(p, dict)}
    keep_from = (now - dt.timedelta(days=KEEP_EVENTS_DAYS)).isoformat()
    events = [e for e in (previous or {}).get("events", []) if isinstance(e, dict) and e.get("detectedAt", "") >= keep_from]
    out_pages = []
    for p in pages:
        res = fetch(p["url"], get=get)
        sleep(1.5)
        rec = {k: p[k] for k in ("id", "company", "label", "url", "kind")}
        rec["checkedAt"] = now.isoformat(timespec="seconds")
        old = prev_pages.get(p["id"])
        if res["status"] != "ok":
            rec.update(status="failed", error=res["error"])
            if old and old.get("signals"):
                rec.update(signals=old["signals"], since=old.get("since"), lastOk=old.get("lastOk"))
            out_pages.append(rec)
            continue
        text = visible_text(res["html"])
        sig = signals(text)
        rec.update(status="ok", signals=sig, hash=hashlib.sha256(text.encode()).hexdigest()[:16],
                   lastOk=now.isoformat(timespec="seconds"), textLength=len(text))
        base, base_src, base_day = None, None, None
        if old and old.get("signals"):
            base, base_src, base_day = old["signals"], "직전 확인", (old.get("lastOk") or old.get("checkedAt") or "")[:10]
        else:
            day = (now - dt.timedelta(days=BASELINE_DAYS)).strftime("%Y%m%d")
            wb_day, wb_html = wayback(p["url"], day, get=get)
            sleep(1.5)
            if wb_html:
                base, base_src, base_day = signals(visible_text(wb_html)), "웹 아카이브 사본", wb_day
            rec["baseline"] = {"source": base_src or "없음(첫 확인)", "date": base_day}
        if base is not None:
            added, removed = diff(base, sig)
            if added or removed:
                events.append({"pageId": p["id"], "company": p["company"], "label": p["label"], "url": p["url"],
                               "detectedAt": now.isoformat(timespec="seconds"), "baselineSource": base_src,
                               "baselineDate": base_day, "added": added, "removed": removed})
        out_pages.append(rec)
    events.sort(key=lambda e: e["detectedAt"], reverse=True)
    failed = [p for p in out_pages if p["status"] != "ok"]
    return {"schema": SCHEMA, "generatedAt": now.isoformat(timespec="seconds"),
            "status": "partial" if failed else "complete", "pages": out_pages, "events": events[:200],
            "rules": ["페이지 문구 변화는 공식 발표가 아니다. 언제·왜 바뀌었는지는 회사 확인이 필요하다.",
                      "첫 비교 기준이 웹 아카이브 사본이면 그 사이 언제 바뀌었는지는 모른다.",
                      "열리지 않은 페이지(차단·오류)는 변화 없음이 아니라 미확인."],
            "confirmedScoops": 0}


def main():
    ap = argparse.ArgumentParser(description="출입처 해외 공식 페이지 변경 감시(기자 전용 저장소로)")
    ap.add_argument("--only", help="페이지 id 하나만(격리 확인용)")
    a = ap.parse_args()
    now = dt.datetime.now(KST)
    pages = json.loads(WATCH.read_text(encoding="utf-8"))["pages"]
    if a.only:
        pages = [p for p in pages if p["id"] == a.only]
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    import private_store
    previous = None
    if token:
        try:
            previous = private_store.get("page-watch", token)
        except private_store.StoreError as e:
            sys.exit(f"이전 상태 조회 실패({e}) — 비교 기준이 없어 중단(변경 없음으로 처리하지 않음)")
    doc = run(pages, now=now, previous=previous)
    new_events = [e for e in doc["events"] if e["detectedAt"] == doc["generatedAt"]]
    # Public log: response codes and counts only — never the signal text or the changes.
    # GitHub shows at most 10 notices per step: one line for all pages.
    lines = []
    for p in doc["pages"]:
        counts = "/".join(str(len(v)) for v in (p.get("signals") or {}).values()) if p["status"] == "ok" else p.get("error")
        lines.append(f"{p['id']}={p['status']}({counts};{(p.get('baseline') or {}).get('source', '직전')})")
    print("::notice title=page-watch-pages::신호 수 순서 timing/limited/price/status/models ;; " + " ;; ".join(lines))
    ok = sum(1 for p in doc["pages"] if p["status"] == "ok")
    print(f"::notice title=page-watch::열림 {ok}/{len(doc['pages'])} · 이번 변경 {len(new_events)}건 · 보관 변경 {len(doc['events'])}건")
    if not token:
        print("::warning title=page-watch-push::MCP_ACCESS_TOKEN 미설정 — 결과를 저장하지 않음(공개 저장소에도 쓰지 않음)")
        return
    if ok == 0:
        sys.exit("모든 페이지 열기 실패 — 이전 상태 유지")
    status = private_store.put("page-watch", doc, token)
    print(f"::notice title=page-watch-push::기자 전용 저장소 전송 HTTP {status}")
    if status != 200:
        sys.exit(1)


if __name__ == "__main__":
    main()
