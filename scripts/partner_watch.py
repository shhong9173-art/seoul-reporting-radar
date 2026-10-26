"""해외 파트너 공시 감시: 출입처와 계약한 해외 상장사(ASX)와 미국 공시 전반(SEC EDGAR 전문 검색).

- ASX: data/overseas_partners.json의 관계 근거가 있는 회사만. 최근 공시 제목을 읽고 공급·계약·조건·가격·
  출입처 이름 같은 낱말이 있으면 표시한다.
- EDGAR: 출입처 영문명을 큰따옴표로 묶어 최근 공시(8-K·6-K·10-Q·10-K·20-F·S-1·F-1 등)를 찾는다.
  출입처 자신이 낸 공시(포스코홀딩스 6-K 등)는 뺀다. 새로 잡힌 문서는 이름 주변 문장을 덧붙인다(예산 안에서).
- 결과는 기자 전용 저장소(partner-filings)로만. 공개 로그는 건수만. 조회 실패는 0건이 아니다.
"""
from __future__ import annotations

import argparse
import datetime as dt
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
SCHEMA = "partner_filings/v1"
PARTNERS = ROOT / "data" / "overseas_partners.json"
WINDOW_DAYS = 30
KEEP_DAYS = 120
NEW_DAYS = 7
BROWSER = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
SEC_UA = os.environ.get("SEC_USER_AGENT", "").strip() or "seoul-reporting-radar research (github.com/shhong9173-art/seoul-reporting-radar)"
FORMS = "8-K,6-K,10-Q,10-K,20-F,40-F,S-1,F-1,424B4,DEF 14A"
FLAG = re.compile(r"offtake|supply|agreement|contract|binding|conditions? precedent|amend|variation|terminat|price|pricing|"
                  r"hyundai|kia|posco|seah|korea|korean|mou|memorandum|strategic|investment|placement|financ|partner", re.I)


def get_json(url, *, params=None, headers=None, get=None):
    if get is None:
        import requests
        get = requests.get
    try:
        r = get(url, params=params or {}, headers=headers or {"User-Agent": BROWSER, "Accept": "application/json"}, timeout=30)
    except Exception as e:
        return "failed", type(e).__name__
    if r.status_code != 200:
        return "failed", f"HTTP {r.status_code}"
    try:
        return "ok", r.json()
    except ValueError:
        return "failed", "JSON 아님"


# ---------- ASX ----------

def asx_items(body):
    """Normalise the two public ASX JSON shapes (markitdigital research API, legacy asx.com.au API)."""
    rows = []
    data = body.get("data") if isinstance(body, dict) else None
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        for x in data["items"]:
            key = x.get("documentKey")
            rows.append({"date": str(x.get("date") or "")[:10], "headline": x.get("headline") or "",
                         "url": x.get("url") or (f"https://cdn-api.markitdigital.com/apiman-gateway/ASX/asx-research/1.0/file/{key}" if key else None),
                         "priceSensitive": bool(x.get("isPriceSensitive"))})
    elif isinstance(data, list):
        for x in data:
            rows.append({"date": str(x.get("document_release_date") or x.get("document_date") or "")[:10],
                         "headline": x.get("header") or "", "url": x.get("url"),
                         "priceSensitive": bool(x.get("market_sensitive"))})
    return rows


def asx(partner, *, get=None):
    code = partner["code"]
    tried = []
    for url, params in ((f"https://asx.api.markitdigital.com/asx-research/1.0/companies/{code.lower()}/announcements", {"count": 30}),
                        (f"https://www.asx.com.au/asx/1/company/{code}/announcements", {"count": 30, "market_sensitive": "false"})):
        status, body = get_json(url, params=params, get=get)
        if status == "ok":
            rows = asx_items(body)
            if rows:
                return {"status": "ok", "via": url.split("/")[2], "items": rows}
            tried.append(f"{url.split('/')[2]} 형식 불일치")
        else:
            tried.append(f"{url.split('/')[2]} {body}")
    return {"status": "failed", "error": "; ".join(tried), "items": []}


# ---------- EDGAR ----------

def edgar_search(phrase, start, end, *, get=None):
    return get_json("https://efts.sec.gov/LATEST/search-index",
                    params={"q": f'"{phrase}"', "dateRange": "custom", "startdt": start, "enddt": end, "forms": FORMS},
                    headers={"User-Agent": SEC_UA, "Accept": "application/json"}, get=get)


def edgar_hits(body, phrase):
    rows = []
    for h in ((body or {}).get("hits") or {}).get("hits") or []:
        src = h.get("_source") or {}
        adsh = src.get("adsh") or ""
        doc_id = str(h.get("_id") or "")
        filename = doc_id.split(":", 1)[1] if ":" in doc_id else ""
        ciks = src.get("ciks") or []
        names = src.get("display_names") or []
        filer = re.sub(r"\s*\(CIK \d+\)\s*$", "", names[0]).strip() if names else ""
        url = None
        if ciks and adsh and filename:
            url = f"https://www.sec.gov/Archives/edgar/data/{int(ciks[0])}/{adsh.replace('-', '')}/{filename}"
        rows.append({"id": f"edgar:{adsh}:{filename}", "filer": filer, "form": src.get("form") or src.get("file_type"),
                     "date": src.get("file_date"), "description": src.get("file_description") or "", "url": url,
                     "phrase": phrase})
    return rows


def snippet(text, phrase, width=280):
    i = text.lower().find(phrase.lower())
    if i < 0:
        return None
    return text[max(0, i - width): i + len(phrase) + width].strip()


def doc_text(url, *, get=None):
    if get is None:
        import requests
        get = requests.get
    try:
        r = get(url, headers={"User-Agent": SEC_UA, "Accept": "text/html,*/*"}, timeout=40)
    except Exception as e:
        return None, type(e).__name__
    if r.status_code != 200:
        return None, f"HTTP {r.status_code}"
    raw = r.text if hasattr(r, "text") else r.content.decode("utf-8", "replace")
    raw = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"(?s)<[^>]+>", " ", raw))), None


# ---------- run ----------

def run(cfg, *, now, previous=None, get=None, sleep=time.sleep, snippet_budget=12):
    prev = {x["id"]: x for x in (previous or {}).get("items", []) if isinstance(x, dict) and x.get("id")}
    keep_from = (now - dt.timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    items = {k: v for k, v in prev.items() if (v.get("date") or "") >= keep_from}
    checks = []
    stamp = now.isoformat(timespec="seconds")
    start = (now - dt.timedelta(days=WINDOW_DAYS)).strftime("%Y-%m-%d")
    for p in cfg.get("asx", []):
        res = asx(p, get=get)
        sleep(1.0)
        checks.append({"source": "ASX", "target": f"{p['name']}({p['code']})", "status": res["status"],
                       **({"via": res["via"], "returned": len(res["items"])} if res["status"] == "ok" else {"error": res["error"]})})
        for a in res["items"]:
            if not a["date"] or a["date"] < start:
                continue
            iid = f"asx:{p['code']}:{a['date']}:{a['headline'][:60]}"
            flags = sorted({m.group(0).lower() for m in FLAG.finditer(a["headline"])})
            items[iid] = {**items.get(iid, {}), "id": iid, "source": "ASX", "filer": f"{p['name']} ({p['code']})",
                          "beat": p["beat"], "relation": p["relation"], "relationEvidence": p["evidence"],
                          "date": a["date"], "title": a["headline"], "url": a["url"], "priceSensitive": a["priceSensitive"],
                          "flags": flags, "firstSeen": items.get(iid, {}).get("firstSeen") or stamp}
    end = now.strftime("%Y-%m-%d")
    for beat, phrase in cfg.get("edgarPhrases", []):
        status, body = edgar_search(phrase, start, end, get=get)
        sleep(0.4)
        if status != "ok":
            checks.append({"source": "EDGAR", "target": phrase, "status": "failed", "error": body})
            continue
        hits = edgar_hits(body, phrase)
        kept = 0
        for h in hits:
            if re.search(rf"\b{re.escape(phrase)}\b", h["filer"], re.I):
                continue  # the beat company's own filing (e.g. POSCO Holdings 6-K); whole-phrase match only
            kept += 1
            old = items.get(h["id"], {})
            beats = sorted(set(old.get("beat", [])) | {beat})
            phrases = sorted(set(old.get("phrases", [])) | {phrase})
            items[h["id"]] = {**old, **h, "source": "EDGAR", "beat": beats, "phrases": phrases,
                              "title": f"{h['form']} {h['description']}".strip(), "firstSeen": old.get("firstSeen") or stamp}
        checks.append({"source": "EDGAR", "target": phrase, "status": "ok", "returned": len(hits), "kept": kept})
    # Context sentences for new EDGAR documents (budgeted).
    for it in sorted(items.values(), key=lambda x: x.get("date") or "", reverse=True):
        if snippet_budget <= 0:
            break
        if it["source"] != "EDGAR" or it.get("snippet") or it.get("snippetError") or not it.get("url"):
            continue
        snippet_budget -= 1
        text, err = doc_text(it["url"], get=get)
        sleep(0.4)
        if err:
            it["snippetError"] = err
            continue
        for ph in it.get("phrases", []):
            sn = snippet(text, ph)
            if sn:
                it["snippet"] = sn[:700]
                break
    new_from = (now - dt.timedelta(days=NEW_DAYS)).strftime("%Y-%m-%d")
    out = sorted(items.values(), key=lambda x: (x.get("date") or "", x["id"]), reverse=True)
    for x in out:
        x["isNew"] = x["id"] not in prev or (x.get("date") or "") >= new_from
    failed = [c for c in checks if c["status"] != "ok"]
    return {"schema": SCHEMA, "generatedAt": stamp, "windowDays": WINDOW_DAYS, "status": "partial" if failed else "complete",
            "checks": checks, "items": out[:400],
            "rules": ["파트너 공시는 그 회사의 발표다. 출입처와의 계약 변경인지는 문구로만 판단하지 않고 출입처 확인이 필요하다.",
                      "ASX는 관계 근거가 확인된 회사만 본다. EDGAR는 출입처 이름이 들어간 공시 전반(출입처 자신의 공시 제외).",
                      "조회 실패는 0건이 아니라 미확인."],
            "confirmedScoops": 0}


def main():
    argparse.ArgumentParser(description="해외 파트너 공시 감시(기자 전용 저장소로)").parse_args()
    now = dt.datetime.now(KST)
    cfg = json.loads(PARTNERS.read_text(encoding="utf-8"))
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    import private_store
    previous = None
    if token:
        try:
            previous = private_store.get("partner-filings", token)
        except private_store.StoreError as e:
            print(f"::warning title=partner-state::이전 상태 조회 실패({e}) — 신규 표시는 이번 실행 기준")
    doc = run(cfg, now=now, previous=previous)
    by = {}
    for c in doc["checks"]:
        key = f"{c['source']} {'ok' if c['status'] == 'ok' else 'fail'}"
        by[key] = by.get(key, 0) + 1
    errors = sorted({c.get("error", "") for c in doc["checks"] if c["status"] != "ok"})[:4]
    new = sum(1 for x in doc["items"] if x["isNew"])
    print(f"::notice title=partner-filings::질의 {json.dumps(by, ensure_ascii=False)} · 항목 {len(doc['items'])}(신규 {new})"
          + (f" · 오류 유형 {errors}" if errors else ""))
    if not token:
        print("::warning title=partner-push::MCP_ACCESS_TOKEN 미설정 — 결과를 저장하지 않음(공개 저장소에도 쓰지 않음)")
        return
    if not any(c["status"] == "ok" for c in doc["checks"]):
        sys.exit("모든 질의 실패 — 이전 결과 유지(0건 아님)")
    status = private_store.put("partner-filings", doc, token)
    print(f"::notice title=partner-push::기자 전용 저장소 전송 HTTP {status}")
    if status != 200:
        sys.exit(1)


if __name__ == "__main__":
    main()
