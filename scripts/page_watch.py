"""출입처 해외 공식 페이지 변경 감시: 출시 시점·가격·판매 상태·차종 목록 문구의 변화.

- data/official_page_watch.json의 페이지를 열어 '신호 문구'를 뽑는다.
  출시 시점(Coming Spring 2027 등), 한정 물량, 가격(Starting MSRP $..), 판매 상태(sold out·reserve 등), 연식+차명.
- 직전 상태(기자 전용 저장소)와 비교해 추가·삭제된 문구를 '변경'으로 남긴다.
  처음 보는 페이지는 웹 아카이브(Wayback)의 약 45일 전 사본을 기준으로 비교한다.
- 설정한 주소가 다른 주소로 넘어가면(리디렉트) 그 페이지는 '넘어감'으로 두고 문구를 비교하지 않는다. 알던 페이지가 넘어가기 시작하면
  '페이지 넘어감'(판매 중단·단종·개편 가능성), 넘어가던 주소가 제 페이지로 열리면 '페이지 열림'(출시 준비 신호)을 남긴다.
  (10-31 확인: kia.com/us/en/ev4는 기아 미국 홈페이지로 301 — 그동안 'EV4' 이름으로 홈페이지의 K4 가격 문구를 비교했다.)
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
# 가격 줄 앞(160자 안)의 가장 가까운 차명 — 차종 목록 페이지의 가격만 바뀌면 어느 차인지 모른다(10-31 운영: 현대차 미국 차종 목록
# '$26,900 / $27,450 / $29,200 → $27,600 / $29,450 Starting MSRP'). 페이지 배치에 따른 추정이라 '근처 차명'으로만 적는다.
MODEL_NAME = re.compile(r"\b(?:IONIQ|Ioniq)\s*\d(?:\s+N)?\b|\b(?:EV\d|GV\d{2}|G\d{2}|K4|K5)\b(?:\s+GT)?|"
                        r"\b(?:Palisade|Santa\s+Fe|Santa\s+Cruz|Tucson|Elantra|Sonata|Kona|Venue|Telluride|Sorento|Sportage|Seltos|Carnival|Niro|Soul)\b"
                        r"(?:\s+(?:Plug-in\s+Hybrid|Hybrid|Electric|N\s+Line|N|XRT|X-Pro))?", re.I)


def price_models(text):
    out = {}
    for m in PATTERNS["price"].finditer(text):
        line = re.sub(r"\s+", " ", m.group(0)).strip().lower()
        names = list(MODEL_NAME.finditer(text[max(0, m.start() - 160):m.start()]))
        if names and line not in out:
            out[line] = re.sub(r"\s+", " ", names[-1].group(0)).strip()
    return out


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
    final = getattr(r, "url", None)
    return {"status": "ok", "html": body, "final": final if isinstance(final, str) and final else url}


def page_key(u):
    """주소 비교용: 호스트(www 뺌)·경로(끝 / 뺌), scheme·쿼리·조각은 무시."""
    m = re.match(r"^https?://(?:www\.)?([^/?#]+)([^?#]*)", str(u or ""), re.I)
    return (m.group(1).lower(), m.group(2).rstrip("/").lower()) if m else (str(u or "").lower(), "")


def same_page(want, got):
    return page_key(want) == page_key(got)


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


def domain_of(url):
    return re.sub(r"^https?://(?:www\.)?([^/]+).*$", r"\1", url)


def common_signals(sig_list):
    """Lines present on most pages of one site = navigation/banners, not the page's own content."""
    sig_list = [x for x in sig_list if x]
    if len(sig_list) < 2:
        return {}
    need = max(2, -(-len(sig_list) * 6 // 10))
    out = {}
    for cat in PATTERNS:
        counts = {}
        for sig in sig_list:
            for line in {v.lower(): v for v in sig.get(cat, [])}.values():
                counts.setdefault(line.lower(), [0, line])[0] += 1
        keep = sorted((v[1] for v in counts.values() if v[0] >= need), key=str.lower)
        if keep:
            out[cat] = keep
    return out


def subtract(sig, common):
    if not sig:
        return {}
    out = {}
    for cat in PATTERNS:
        drop = {x.lower() for x in (common or {}).get(cat, [])}
        out[cat] = [x for x in sig.get(cat, []) if x.lower() not in drop]
    return out


def run(pages, *, now, previous=None, get=None, sleep=time.sleep):
    prev_pages = {p["id"]: p for p in (previous or {}).get("pages", []) if isinstance(p, dict)}
    prev_sites = (previous or {}).get("sites") or {}
    keep_from = (now - dt.timedelta(days=KEEP_EVENTS_DAYS)).isoformat()
    events = [e for e in (previous or {}).get("events", []) if isinstance(e, dict) and e.get("detectedAt", "") >= keep_from]
    stamp = now.isoformat(timespec="seconds")
    raw, wb = {}, {}
    out_pages = []
    for p in pages:  # pass 1: fetch
        res = fetch(p["url"], get=get)
        sleep(1.5)
        rec = {k: p[k] for k in ("id", "company", "label", "url", "kind")}
        rec["checkedAt"] = stamp
        old = prev_pages.get(p["id"])
        if res["status"] != "ok":
            rec.update(status="failed", error=res["error"])
            if old and old.get("signals"):
                rec.update(signals=old["signals"], specific=old.get("specific", False), lastOk=old.get("lastOk"))
            out_pages.append(rec)
            continue
        final = res.get("final") or p["url"]
        if not same_page(p["url"], final):
            rec.update(status="redirected", finalUrl=final, lastOk=stamp, signals={})
            if old and "finalUrl" in old and old.get("status") != "redirected":
                # 알던 페이지가 이번에 다른 주소로 넘어감
                events.append({"pageId": p["id"], "scope": "page", "kind": "moved", "company": p["company"], "label": p["label"], "url": p["url"],
                               "detectedAt": stamp, "baselineSource": "직전 확인", "baselineDate": (old.get("lastOk") or "")[:10],
                               "movedTo": final, "added": {}, "removed": old.get("signals") or {}})
            elif old and "finalUrl" not in old:
                # 예전 기록(넘어간 줄 모르던 때): 이 주소의 지난 '변경'은 넘어간 곳의 문구였다고 적는다
                for e in events:
                    if e.get("pageId") == p["id"] and not e.get("redirectNote"):
                        e["redirectNote"] = f"이 주소는 {final}(으)로 넘어가 있어 이 문구는 그 페이지 것이다 — {p['label']} 문구 아님({stamp[:10]} 확인)"
            out_pages.append(rec)
            continue
        text = visible_text(res["html"])
        raw[p["id"]] = signals(text)
        rec["priceModels"] = price_models(text)
        rec.update(status="ok", finalUrl=final, hash=hashlib.sha256(text.encode()).hexdigest()[:16], lastOk=stamp, textLength=len(text))
        if old and old.get("status") == "redirected":
            rec["openedFrom"] = old.get("finalUrl") or "다른 주소"
        elif not (old and old.get("signals")):
            day = (now - dt.timedelta(days=BASELINE_DAYS)).strftime("%Y%m%d")
            wb_day, wb_html = wayback(p["url"], day, get=get)
            sleep(1.5)
            wb[p["id"]] = (wb_day, signals(visible_text(wb_html)) if wb_html else None)
        out_pages.append(rec)
    # pass 2: separate site-wide lines (menus, banners) from each page's own lines
    by_domain = {}
    for rec in out_pages:
        by_domain.setdefault(domain_of(rec["url"]), []).append(rec)
    sites = {}
    for dom, recs in by_domain.items():
        ok = [r for r in recs if r["status"] == "ok"]
        common = common_signals([raw[r["id"]] for r in ok])
        wb_common = common_signals([wb[r["id"]][1] for r in ok if r["id"] in wb and wb[r["id"]][1]])
        company = recs[0]["company"]
        sites[dom] = {"company": company, "signals": common, "pages": len(ok), "checkedAt": stamp}
        # Before site-wide separation existed, rebuild the previous site lines from the previous page records.
        prev_recs = [prev_pages[r["id"]] for r in recs if r["id"] in prev_pages and prev_pages[r["id"]].get("signals")]
        legacy_common = common_signals([x["signals"] for x in prev_recs if not x.get("specific")])
        prev_common = (prev_sites.get(dom) or {}).get("signals")
        if prev_common is None and legacy_common:
            prev_common = legacy_common
        if prev_common is not None and ok:
            added, removed = diff(prev_common, common)
            if added or removed:
                events.append({"pageId": f"site:{dom}", "scope": "site", "company": company,
                               "label": f"{company} {dom} 사이트 공통 문구(메뉴·배너)", "url": f"https://{dom}",
                               "detectedAt": stamp, "baselineSource": "직전 확인",
                               "baselineDate": ((prev_sites.get(dom) or {}).get("checkedAt") or "")[:10],
                               "added": added, "removed": removed})
        for rec in ok:
            pid = rec["id"]
            own = subtract(raw[pid], common)
            rec.update(signals=own, specific=True)
            old = prev_pages.get(pid)
            base, src, day = None, None, None
            if rec.get("openedFrom"):
                # 다른 주소로 넘어가던 주소가 제 페이지로 열림 — 지금 문구 전체를 새로 보인 것으로
                events.append({"pageId": pid, "scope": "page", "kind": "opened", "company": rec["company"], "label": rec["label"], "url": rec["url"],
                               "detectedAt": stamp, "baselineSource": f"{rec['openedFrom']}(으)로 넘어가던 주소", "baselineDate": (old.get("lastOk") or "")[:10],
                               "openedFrom": rec["openedFrom"], "added": {k: v for k, v in own.items() if v}, "removed": {}})
                continue
            if old and old.get("signals"):
                # Records saved before site-wide separation still contain menu lines: strip today's common lines.
                base = old["signals"] if old.get("specific") else subtract(subtract(old["signals"], legacy_common), common)
                src, day = "직전 확인", (old.get("lastOk") or old.get("checkedAt") or "")[:10]
            elif pid in wb:
                wb_day, wb_sig = wb[pid]
                if wb_sig:
                    base, src, day = subtract(subtract(wb_sig, wb_common), common), "웹 아카이브 사본", wb_day
                rec["baseline"] = {"source": src or "없음(첫 확인)", "date": day}
            if base is not None:
                added, removed = diff(base, own)
                if added or removed:
                    ev = {"pageId": pid, "scope": "page", "company": rec["company"], "label": rec["label"],
                          "url": rec["url"], "detectedAt": stamp, "baselineSource": src, "baselineDate": day,
                          "added": added, "removed": removed}
                    near = {**((old or {}).get("priceModels") or {}), **(rec.get("priceModels") or {})}
                    pm = {x.lower(): near[x.lower()] for x in added.get("price", []) + removed.get("price", []) if x.lower() in near}
                    if pm:
                        ev["priceModels"] = pm
                    events.append(ev)
    events.sort(key=lambda e: e["detectedAt"], reverse=True)
    failed = [p for p in out_pages if p["status"] == "failed"]
    return {"schema": SCHEMA, "generatedAt": stamp,
            "status": "partial" if failed else "complete", "pages": out_pages, "sites": sites, "events": events[:200],
            "rules": ["페이지 문구 변화는 공식 발표가 아니다. 언제·왜 바뀌었는지는 회사 확인이 필요하다.",
                      "같은 사이트 여러 페이지에 공통으로 붙은 문구(메뉴·배너)는 사이트 공통으로 따로 본다.",
                      "첫 비교 기준이 웹 아카이브 사본이면 그 사이 언제 바뀌었는지는 모른다.",
                      "열리지 않은 페이지(차단·오류)는 변화 없음이 아니라 미확인.",
                      "다른 주소로 넘어가는 페이지는 문구를 비교하지 않는다. 넘어가기 시작하면 '페이지 넘어감', 다시 제 페이지로 열리면 '페이지 열림'."],
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
    if private_store.late_scheduled_duplicate(previous, now):
        return
    doc = run(pages, now=now, previous=previous)
    new_events = [e for e in doc["events"] if e["detectedAt"] == doc["generatedAt"]]
    # Public log: response codes and counts only — never the signal text or the changes.
    # GitHub shows at most 10 notices per step: one line for all pages.
    lines = []
    for p in doc["pages"]:
        counts = "/".join(str(len(v)) for v in (p.get("signals") or {}).values()) if p["status"] == "ok" else (p.get("error") or p["status"])
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
    if status == 404:
        print(f"::warning title=page-watch-push-token::토큰 거부 가능성 — {private_store.token_shape(private_store.normalize_token(token))}. GitHub Secret MCP_ACCESS_TOKEN이 Cloudflare 값과 같아야 함")
    if status != 200:
        sys.exit(1)


if __name__ == "__main__":
    main()
