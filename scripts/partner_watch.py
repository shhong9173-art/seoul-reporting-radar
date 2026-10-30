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
# Name used in an unrelated sense (first real run, 10/26: 'POSCO Center' building address in a Beijing proxy statement).
UNRELATED = {"POSCO": re.compile(r"POSCO\s+(?:Center|Centre|Tower|Plaza|E&C\s+Tower)", re.I),
             # EDGAR 전문 검색은 대소문자를 가리지 않아 말레이시아·싱가포르 성씨 'Seah'도 걸린다(10-29 Global Engine Group 20-F → '세아' A).
             # 세아는 'SeAH'로만 쓴다 — 다른 대소문자 'Seah·SEAH'는 무관한 뜻으로 센다.
             "SeAH": re.compile(r"\b(?!SeAH\b)[Ss][Ee][Aa][Hh]\b")}
# EDGAR hits that name a beat company without any dealing with it (첫 실운영 10/27: 미국 보험사 투자 보유 표의
# 'Top Ten Exposures by Issuer … Hyundai Motor Company', KT 분기 재무제표 주석의 기존 지분 약정 문구).
HOLDINGS = re.compile(r"top\s+(?:ten|10)\s+(?:exposures|holdings|issuers)|exposures?\s+by\s+issuer|fixed\s+maturit|schedule\s+of\s+investments|"
                      r"portfolio\s+holdings|corporate\s+(?:bonds|debt\s+securities)|%\s+of\s+(?:total|net\s+assets|invested)|amortized\s+cost|"
                      r"unrealized\s+(?:gains?|loss)|principal\s+amount\s+held", re.I)
FIN_NOTE = re.compile(r"\(\d{1,2}\)\s+the\s+(?:company|group)\s+(?:has|had|have|is|entered)|commitments\s+and\s+contingenc|"
                      r"\bnote\s+\d{1,2}\b|review\s+report|separate\s+financial\s+statements|consolidated\s+financial\s+statements", re.I)
FIN_DOC = re.compile(r"(?:review|financ|consolidat|separate|interim|10-?q|annual|20-?f)", re.I)


def classify(it):
    """routine: no dealing with the beat company (holdings tables) → C. finNote: periodic financial-statement
    notes, often restating an existing arrangement → never A. Text only; the original decides."""
    sn = it.get("snippet") or ""
    it.pop("routine", None)
    it.pop("finNote", None)
    digits = sum(ch.isdigit() for ch in sn)
    if HOLDINGS.search(sn) or (len(sn) > 200 and digits / len(sn) > 0.18):
        it["routine"] = "투자 보유 목록(채권·주식 보유 표) — 출입처와의 거래 아님"
    elif FIN_NOTE.search(sn) or (FIN_DOC.search(str(it.get("url") or "")) and str(it.get("form") or "").upper() in ("6-K", "6-K/A", "10-Q", "10-K", "20-F")
                                 and re.search(r"\bthe\s+(?:company|group)\s+has\b", sn, re.I)):
        it["finNote"] = "재무제표 주석 — 이미 있던 약정을 다시 적은 것일 수 있음(이전 분기 보고서와 대조)"


def fingerprint(it):
    """Same sentence in another filing of the same filer (amounts and dates ignored)."""
    sn = re.sub(r"[\d,.%$₩]+", " ", (it.get("snippet") or "").lower())
    sn = re.sub(r"\s+", " ", sn).strip()
    if len(sn) < 80:
        return None
    import hashlib
    return hashlib.sha1(f"{(it.get('filer') or '').lower()}|{sn}".encode()).hexdigest()[:16]


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


# ---------- HKEX ----------
# Hong Kong-listed partners (운영 10-22 경쟁지 [단독] 'BAIC, 현대차 합작 금융사 지분 정리' — BAIC Motor(01958)가 전날
# 10-21 18:33 HKEX에 'MAJOR TRANSACTION - EXIT OF BAIC INVESTMENT FROM ITS INVESTMENT IN BHAF'를 냈다).
HKEX_SEARCH = "https://www1.hkexnews.hk/search/titleSearchServlet.do"
HKEX_SITE = "https://www1.hkexnews.hk"
HKEX_DEAL = re.compile(r"major transaction|very substantial|discloseable|connected transaction|disposal|acquisition|exit|transfer|"
                       r"joint venture|equity interest|capital (?:increase|injection)|subscription|framework agreement|termination|"
                       r"hyundai|kia|posco", re.I)
HKEX_ROUTINE = re.compile(r"monthly return|next day disclosure|notice of board meeting|interim report|annual report|"
                          r"proxy form|form of proxy|date of board meeting|list of directors|poll results|"
                          r"change of company secretary|corporate governance|esg report|environmental, social", re.I)


def hkex_rows(body):
    """titleSearchServlet answers {'result': '<JSON string of rows>', ...}. Rows: DATE_TIME 'dd/mm/yyyy HH:MM' (HKT), TITLE, FILE_LINK."""
    import json as _json
    try:
        rows = _json.loads(body.get("result") or "[]") if isinstance(body, dict) else []
    except ValueError:
        return None
    out = []
    for x in rows if isinstance(rows, list) else []:
        m = re.match(r"(\d{2})/(\d{2})/(\d{4})(?:\s+(\d{2}:\d{2}))?", str(x.get("DATE_TIME") or ""))
        out.append({"date": f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else "", "time": (m.group(4) if m else None),
                    "title": re.sub(r"\s+", " ", str(x.get("TITLE") or "")).strip(), "category": re.sub(r"<[^>]+>", " ", str(x.get("LONG_TEXT") or "")).strip()[:200],
                    "url": HKEX_SITE + x["FILE_LINK"] if str(x.get("FILE_LINK") or "").startswith("/") else x.get("FILE_LINK"),
                    "newsId": str(x.get("NEWS_ID") or "")})
    return out


def hkex(partner, start, end, *, get=None):
    params = {"sortDir": 0, "sortByOptions": "DateTime", "category": 0, "market": "SEHK", "stockId": partner["stockId"], "documentType": -1,
              "fromDate": start.replace("-", ""), "toDate": end.replace("-", ""), "title": "", "searchType": 0, "t1code": -2, "t2Gcode": -2,
              "t2code": -2, "rowRange": 100, "lang": "E"}
    status, body = get_json(HKEX_SEARCH, params=params, get=get)
    if status != "ok":
        return {"status": "failed", "error": body, "items": []}
    rows = hkex_rows(body)
    if rows is None:
        return {"status": "failed", "error": "결과 형식 불일치", "items": []}
    return {"status": "ok", "items": rows}


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

def run(cfg, *, now, previous=None, get=None, sleep=time.sleep, snippet_budget=25):
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
    for p in cfg.get("hkex", []):
        res = hkex(p, start, end, get=get)
        sleep(1.0)
        checks.append({"source": "HKEX", "target": f"{p['name']}({p['code']})", "status": res["status"],
                       **({"returned": len(res["items"])} if res["status"] == "ok" else {"error": res["error"]})})
        for a in res["items"]:
            if not a["date"] or a["date"] < start or not a["title"]:
                continue
            iid = f"hkex:{p['code']}:{a['newsId'] or a['date'] + ':' + a['title'][:60]}"
            old = items.get(iid, {})
            routine = "정기·형식 공시(월간 증권 변동·이사회 일정·정기보고서 등)" if HKEX_ROUTINE.search(a["title"]) else None
            flags = [] if routine else sorted({m.group(0).lower() for m in HKEX_DEAL.finditer(a["title"])})
            items[iid] = {**old, "id": iid, "source": "HKEX", "filer": f"{p['name']} ({p['code']})", "beat": p["beat"],
                          "relation": p["relation"], "relationEvidence": p["evidence"], "date": a["date"], "time": a["time"],
                          "title": a["title"], "category": a["category"], "url": a["url"], "flags": flags,
                          **({"routine": routine} if routine else {}), "firstSeen": old.get("firstSeen") or stamp}
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
        related = []
        for ph in it.get("phrases", []):
            total = len(re.findall(re.escape(ph), text, re.I))
            unrelated = len(UNRELATED[ph].findall(text)) if ph in UNRELATED else 0
            if total and total > unrelated:
                related.append(ph)
        if it.get("phrases") and not related:
            it["noise"] = "출입처 이름이 무관한 뜻(건물 주소 등)으로만 쓰임"
            continue
        for ph in related:
            sn = snippet(UNRELATED[ph].sub(" ", text) if ph in UNRELATED else text, ph)
            if sn:
                it["snippet"] = sn[:700]
                break
    # Saved snippets from earlier runs get the same unrelated-sense check.
    for it in items.values():
        sn = it.get("snippet") or ""
        if it.get("source") == "EDGAR" and sn and not it.get("noise"):
            unrelated = sum(len(UNRELATED[ph].findall(sn)) for ph in it.get("phrases", []) if ph in UNRELATED)
            total = sum(len(re.findall(re.escape(ph), sn, re.I)) for ph in it.get("phrases", []))
            if unrelated and total == unrelated:  # only when the unrelated sense is actually visible
                it["noise"] = "출입처 이름이 무관한 뜻(건물 주소 등)으로만 쓰임"
    # Classify every EDGAR item with a snippet, then mark repeats of the same sentence by the same filer.
    text_seen = {k: v for k, v in ((previous or {}).get("textSeen") or {}).items()
                 if isinstance(v, dict) and (v.get("date") or "") >= (now - dt.timedelta(days=400)).strftime("%Y-%m-%d")}
    for it in sorted(items.values(), key=lambda x: (x.get("date") or "", x["id"])):
        if it.get("source") != "EDGAR" or not it.get("snippet") or it.get("noise"):
            continue
        classify(it)
        fp = fingerprint(it)
        if not fp:
            continue
        first = text_seen.get(fp)
        if first and first.get("id") != it["id"]:
            same_filing = first["id"].split(":")[1:2] == it["id"].split(":")[1:2]
            it["routine"] = it.get("routine") or ("같은 제출의 다른 문서와 같은 문구" if same_filing else
                                                 f"같은 회사 이전 공시({first.get('date')})와 같은 문구 — 반복 기재")
            it["repeatOf"] = first["id"]
        else:
            text_seen.setdefault(fp, {"id": it["id"], "date": it.get("date")})
    new_from = (now - dt.timedelta(days=NEW_DAYS)).strftime("%Y-%m-%d")
    out = sorted((x for x in items.values() if not x.get("noise")), key=lambda x: (x.get("date") or "", x["id"]), reverse=True)
    for x in out:
        x["isNew"] = x["id"] not in prev or (x.get("date") or "") >= new_from
    failed = [c for c in checks if c["status"] != "ok"]
    return {"schema": SCHEMA, "generatedAt": stamp, "windowDays": WINDOW_DAYS, "status": "partial" if failed else "complete",
            "checks": checks, "items": out[:400], "textSeen": dict(list(text_seen.items())[-3000:]),
            "rules": ["파트너 공시는 그 회사의 발표다. 출입처와의 계약 변경인지는 문구로만 판단하지 않고 출입처 확인이 필요하다.",
                      "ASX·HKEX는 관계 근거가 확인된 회사만 본다. EDGAR는 출입처 이름이 들어간 공시 전반(출입처 자신의 공시 제외).",
                      "HKEX 제목의 거래 낱말(주요 거래·처분·합작 등)은 제목 분류일 뿐이다. 거래 상대·지분·금액은 공시 PDF에서 확인한다.",
                      "EDGAR 투자 보유 표·같은 회사의 반복 문구는 일상으로 접고, 재무제표 주석은 기존 약정일 수 있어 A로 올리지 않는다(문구 분류일 뿐 원문이 기준).",
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
    if private_store.late_scheduled_duplicate(previous, now):
        return
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
    if status == 404:
        print(f"::warning title=partner-push-token::토큰 거부 가능성 — {private_store.token_shape(private_store.normalize_token(token))}. GitHub Secret MCP_ACCESS_TOKEN이 Cloudflare 값과 같아야 함")
    if status != 200:
        sys.exit(1)


if __name__ == "__main__":
    main()
