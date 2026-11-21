"""EU 관보(Official Journal) 무역구제 시행규정·공고 — 한국산 조치와, 다른 나라 조치에 출입처(해외 법인 포함)가 수출자로 이름 오른 것.

근거(11-19 기자 "다음발전해" — 영국 정부 고시를 놓친 뒤 다른 나라 '최종 결정 문서'가 비어 있는지 점검): 레이더는 EU 철강 쿼터(TARIC)만 보고
EU 반덤핑·상계관세 규정 자체는 보지 않았다. 탐침 19(11-19): 11-13자 「Commission Implementing Regulation (EU) 2026/2547 … imposing a definitive
anti-dumping duty on imports of certain cold-rolled flat steel products originating in India, Japan, Taiwan, …」 본문에 'POSCO VIETNAM Co., Ltd'가
수출자로 나왔고, 파이낸셜뉴스가 11-17 'EU, 베트남산 냉연강판에 16% 반덤핑 관세 부과…포스코도 포함'으로 썼다. 같은 기간 한국산 PVC 수입 등록
(2026/2345)·한국산 아크릴산 에스테르 잠정 관세(2026/2512) 규정도 있었다.

원천(로그인 없음, 공식 기계 접근 경로):
- 목록: 유럽연합 출판청 Cellar SPARQL(publications.europa.eu/webapi/rdf/sparql) — 영어 제목에 anti-dumping·countervailing·anti-subsidy·
  safeguard가 든 최근 문서(CELEX 3…=시행규정, 5…=C 시리즈 공고). 탐침: 0.8초, 21일 32건
- 본문: publications.europa.eu/resource/celex/<CELEX> (영어 XHTML, 1~2MB) — 출입처 이름·제1조 세율 대목

판정 일정(11-19 기자 "단독을 위해서 더 노력해봐"): 하루 한 번 최근 HISTORY_DAYS일 목록을 한 번 더 받아(탐침 22: 470일 268건, 21초)
제목에 Korea가 든 개시 공고와 출입 업종 품목 세이프가드 개시 공고를 '진행 사건'으로 묶고, 그 뒤 같은 품목 규정(수입 등록·잠정·확정·종료)으로
단계를 매긴다. 기한은 규정에 적힌 것만 계산한다(반덤핑 기본규정 2016/1036 — 2018/825·2020/1173 개정 반영):
  반덤핑 조사: 잠정 관세 개시 60일 뒤부터, 보통 7개월·늦어도 8개월(제7조 1항), 잠정 관세 4주 전 당사자 사전 공개(제19a조), 끝 14개월(제6조 9항)
  반덤핑 재심(종료·중간): 보통 12개월·늦어도 15개월(제11조 5항) / 상계관세 조사: 끝 13개월(2016/1037 제11조 9항)
  세이프가드 조사: 공고 8항 '개시일부터 9개월, 예외 때 최대 2개월 연장' / 우회 조사·세이프가드 재심: 계산하지 않음(공고 원문)
개시 공고 본문의 일정 문장(Schedule of the investigation)도 원문 그대로 붙인다. 날짜는 '규정상 시한'이지 발표 예정일이 아니다.

잡는 것: 제목에 Korea가 든 출입 업종 품목의 규정·공고, 그리고 제목에 Korea가 없어도 본문에 출입처 이름이 나온 확정·잠정 관세 규정
(포스코 베트남처럼 출입처 해외 법인이 수출자). 등급 A = 출입처 이름 + 확정·잠정·개시·종료, 또는 한국산 출입 업종 품목의 확정·잠정·개시.
B = 수입 등록·재심 개시·변경·정정 등. 첫 실행은 기준선. 결과는 기자 전용 저장소(eu-trade-defence)로만 — 공개 로그에는 건수만.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

SCHEMA = "eu_trade_defence/v1"
KST = dt.timezone(dt.timedelta(hours=9))
SPARQL = "https://publications.europa.eu/webapi/rdf/sparql"
CELLAR = "https://publications.europa.eu/resource/celex/"
EURLEX = "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:"
UA = {"User-Agent": "Mozilla/5.0 seoul-reporting-radar (reporter research)"}
LOOKBACK_DAYS = 21
BODY_BUDGET = 5          # 한 실행에 받는 본문 수(1~2MB씩)
PAUSE = 2.0
KEEP_DAYS = 400
EVENT_DAYS = 60
MAX_RECORDS = 80
HISTORY_DAYS = 470       # 재심 15개월 + 여유
HISTORY_EVERY_H = 20     # 긴 목록은 하루 한 번
SCHEDULE_BUDGET = 2      # 한 실행에 일정 문장을 읽을 개시 공고 수
DONE_KEEP_DAYS = 60
SAFEGUARD = re.compile(r"\bsafeguard", re.I)
KOREA = re.compile(r"\bKorea\b", re.I)
# 출입 업종 품목(철강·비철·전선·전력기기·타이어·자동차·석유화학·정유) — 제목만 보고 본문을 받을지 정한다
BEAT_PRODUCT = re.compile(
    r"steel|iron|stainless|plate|coil|tube|pipe|wire rod|rebar|tinplate|tin mill|ferro|electrical steel|grain-oriented|zinc|lead|copper|alumin|"
    r"cable|wire|transformer|tyre|tire|vehicle|car\b|battery|lithium|polyvinyl|PVC|polyethylene|polypropylene|polyethylene terephthalate|PET\b|"
    r"acryl|epoxy|styrene|ABS|rubber|glycol|ethylene|propylene|butadiene|phenol|acetone|caprolactam|polycarbonate|polyamide|methyl|alcohol|"
    r"fuel|biodiesel|gasoline|naphtha|solar|silicon|polysilicon", re.I)


def now_kst():
    return dt.datetime.now(KST)


def plain(raw):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw or ""))).strip()


def kind_of(title):
    """제목 → (종류, 기본 등급). 순서가 중요하다: 확정 규정 제목에도 'provisional duty'(잠정 관세 확정 징수)·'expiry review'(종료재심 결과)가 들어간다."""
    t = title or ""
    has = lambda rx: re.search(rx, t, re.I) is not None
    if has(r"impending expiry"):
        return "만료 예정 공고", "B"
    # 세이프가드는 원산지 구분 없이 모든 수입(한국산 포함)에 걸린다 — 제목에 Korea가 없어도 출입 업종 품목이면 본다(11-19: 하이브리드차 조사 개시를 못 잡음)
    if SAFEGUARD.search(t) and has(r"notice of initiation|initiation of an?\b"):
        return ("세이프가드 재심 개시", "B") if has(r"review") else ("세이프가드 조사 개시", "A")
    if has(r"notice of initiation|initiation of an?\b"):
        return ("재심·우회 조사 개시", "B") if has(r"review|circumvention") else ("조사 개시", "A")
    if has(r"\bcorrecting\b|\bamending\b|corrigendum"):
        return "변경·정정", "B"
    if has(r"subject to registration"):
        return "수입 등록", "B"
    if has(r"\brepealing\b|\bterminating\b|termination of"):
        return "조사 종료·조치 폐지", "A"
    if SAFEGUARD.search(t) and has(r"\bprovisional"):
        return "세이프가드 잠정 조치", "A"
    if SAFEGUARD.search(t) and has(r"\bimposing|\bextending|\bdefinitive"):
        return "세이프가드 조치", "A"
    if has(r"\bdefinitive"):
        return ("확정 관세 연장(종료재심 결과)", "A") if has(r"following an expiry review") else ("확정 관세", "A")
    if has(r"\bprovisional"):
        return "잠정 관세", "A"
    if has(r"review|circumvention"):
        return "재심·우회 조사", "B"
    return "고시", "B"


def number_of(title, celex):
    m = re.search(r"\((?:EU|Euratom)\)\s*(?:No\s*)?(\d{4}/\d{1,5})", title or "")
    return m.group(1) if m else celex


def product_of(title):
    m = re.search(r"imports? of (?:certain )?(.+?)(?:,?\s+originating in|$)", title or "", re.I)
    return (m.group(1) if m else "").strip(" ,")[:100]


def companies_in(text):
    from tra_file_watch import companies_in as ci
    return ci(text)


def query(since):
    return f"""PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
SELECT DISTINCT ?celex ?date ?title WHERE {{
 ?work cdm:resource_legal_id_celex ?celex ; cdm:work_date_document ?date .
 ?expr cdm:expression_belongs_to_work ?work ; cdm:expression_title ?title ;
       cdm:expression_uses_language <http://publications.europa.eu/resource/authority/language/ENG> .
 FILTER(?date >= "{since}"^^<http://www.w3.org/2001/XMLSchema#date>)
 FILTER(REGEX(?title, "anti-dumping|countervailing|anti-subsidy|safeguard", "i"))
}} ORDER BY DESC(?date) LIMIT 200"""


def list_docs(get, since, limit=200):
    r = get(SPARQL, params={"query": query(since).replace("LIMIT 200", f"LIMIT {limit}"), "format": "application/sparql-results+json"}, headers=UA, timeout=180)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}")
    out = {}
    for b in r.json()["results"]["bindings"]:
        celex = b["celex"]["value"]
        # 3…=규정·결정(L), 5…=C 시리즈 공고. 0…(통합본)·6…(법원 판결)은 뺀다
        if not re.match(r"^[35]\d{4}", celex):
            continue
        out.setdefault(celex, {"celex": celex, "date": b["date"]["value"][:10], "title": plain(b["title"]["value"])[:400]})
    return list(out.values())


def article1(text):
    """제1조(관세 표) — 본문 결정부('HAS ADOPTED THIS REGULATION:') 뒤 'Article 1'부터 'Article 2' 전까지. 없으면 ''.
    (전문(前文)에도 'Article 1(4) of the basic Regulation' 같은 인용이 많아 결정부부터 찾는다 — 탐침 20)"""
    m = re.search(r"HAS ADOPTED TH(?:IS|E PRESENT) (?:REGULATION|DECISION)\s*:?(.*)", text, re.S)
    part = m.group(1) if m else ""
    m = re.search(r"\bArticle 1\b(.{0,30000}?)\bArticle 2\b", part, re.S)
    return m.group(1) if m else part[:30000]


def rates_for(text, names):
    """제1조 표에서 출입처 이름 뒤 첫 세율 — [{company, exporter, rate, code}]. EU 영어 본문 표는 '%' 없이 쉼표 소수와 TARIC 추가 코드
    ('Vietnam POSCO VIETNAM CO., LTD 16,0 88GO' — 탐침 20). 본문 문장에는 '16,0 %'처럼 쓴다."""
    from trade_remedy_watch import BEAT_NAMES
    art = article1(text)
    out = []
    for name, rx in BEAT_NAMES:
        if name not in names:
            continue
        for m in re.finditer(rx, art, re.I):
            tail = art[m.end(): m.end() + 160]
            r = re.search(r"(\d{1,3}(?:[.,]\d{1,2})?)\s+([0-9A-Z]{4})\b(?!\s*(?:mm|kg|tonnes))", tail) or re.search(r"(\d{1,3}(?:[.,]\d{1,2})?)\s?%()", tail)
            if r:
                exporter = (art[m.start(): m.end()] + tail[:r.start()]).strip(" ,;:")[:70]
                out.append({"company": name, "exporter": exporter, "rate": r.group(1).replace(",", ".") + "%", "code": r.group(2) or None})
                break
    return out[:6]


def snippets(text, names, limit=2, cap=260):
    from trade_remedy_watch import BEAT_NAMES
    want = [rx for n, rx in BEAT_NAMES if n in names]
    out = []
    for s in re.split(r"(?<=[.;])\s+(?=[A-Z(])", text):
        if 40 <= len(s) <= 1200 and any(re.search(rx, s, re.I) for rx in want):
            out.append(s[:cap] + (" …" if len(s) > cap else ""))
        if len(out) >= limit:
            break
    return out


def read_body(get, celex):
    r = get(CELLAR + celex, headers={**UA, "Accept": "application/xhtml+xml, text/html", "Accept-Language": "eng"}, timeout=120)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}")
    return plain(r.text)


def record_of(d, body, stamp):
    kind, tier = kind_of(d["title"])
    korea = bool(KOREA.search(d["title"]))
    names = companies_in(body) if body is not None else []
    rec = {"id": f"euoj:{d['celex']}", "celex": d["celex"], "number": number_of(d["title"], d["celex"]), "date": d["date"], "title": d["title"],
           "product": product_of(d["title"]), "kind": kind, "korea": korea, "companies": names, "url": EURLEX + d["celex"], "firstSeen": stamp}
    if body is not None:
        rec["chars"] = len(body)
        rec["koreaMentions"] = len(KOREA.findall(body))
        rec["rates"] = rates_for(body, names) if names else []
        rec["snippets"] = snippets(body, names) if names else []
    else:
        rec["note"] = "본문 미읽음(실행 한도) — 원문 열기"
    beat_product = bool(BEAT_PRODUCT.search(d["title"]))
    if SAFEGUARD.search(d["title"]) and beat_product:
        rec["safeguard"] = True
    if names and tier == "A":
        rec["tier"] = "A"
    elif rec.get("safeguard") and kind in ("세이프가드 조사 개시", "세이프가드 잠정 조치", "세이프가드 조치"):
        rec["tier"] = "A"
    elif korea and beat_product and kind in ("확정 관세", "잠정 관세", "조사 개시", "확정 관세 연장(종료재심 결과)", "조사 종료·조치 폐지"):
        rec["tier"] = "A"
    else:
        rec["tier"] = "B"
    return rec


def event_of(rec, stamp):
    rates = " · ".join(f"{r['exporter']} {r['rate']}" + (f"({r['code']})" if r.get("code") else "") for r in rec.get("rates") or [])
    text = (f"EU 관보 무역구제 — {rec['kind']}: {rec['number']} 「{rec['title'][:240]}」({rec['date']})"
            + (f" · 본문에 출입처 {'·'.join(rec['companies'])}" if rec.get("companies")
               else " · 세이프가드 — 원산지 구분 없이 모든 수입(한국산 포함) 대상, 나라별 예외·쿼터는 원문" if rec.get("safeguard") and not rec.get("korea")
               else " · 본문에 출입처 이름 없음(한국산 품목)")
            + (f" · 제1조 세율 {rates}" if rates else "")
            + (f" · 본문 대목 「{rec['snippets'][0]}」" if rec.get("snippets") else "")
            + (f" · {rec['note']}" if rec.get("note") else "")
            + " (EU 집행위원회 시행규정·공고 — 세율·대상 업체는 본문 제1조 표로. 출입처 해외 법인이 수출자로 나온 것은 그 나라산 조치)")
    return {"id": rec["id"], "kind": f"EU 관보 무역구제({rec['kind']})", "tier": rec["tier"], "company": "·".join(rec.get("companies") or []),
            "companies": rec.get("companies") or [], "product": rec.get("product"), "number": rec.get("number"), "date": rec.get("date"),
            "korea": rec.get("korea"), **({"safeguard": True} if rec.get("safeguard") else {}), "url": rec["url"], "text": text, "detectedAt": stamp}


# ── 판정 일정(진행 사건) ──────────────────────────────────────────────
def add_months(day, n):
    y, m = divmod(day.month - 1 + n, 12)
    y, m = day.year + y, m + 1
    last = (dt.date(y + (m == 12), m % 12 + 1, 1) - dt.timedelta(days=1)).day
    return dt.date(y, m, min(day.day, last))


def norm_product(p):
    return re.sub(r"[^a-z0-9]+", " ", re.sub(r"\(.*?\)", " ", (p or "").lower())).replace("certain ", "").strip()


def proc_type(title):
    """개시 공고 제목 → (갈래, 한국어). 개시 공고가 아니면 None."""
    t = title or ""
    if not re.search(r"^notice of initiation", t, re.I):
        return None                      # 'Notice amending the notice of initiation …' 등은 사건이 아니다
    if SAFEGUARD.search(t):
        return ("sgr", "세이프가드 재심") if re.search(r"review", t, re.I) else ("sg", "세이프가드 조사")
    if re.search(r"circumvention", t, re.I):
        return "circ", "우회 조사"
    if re.search(r"expiry review", t, re.I):
        return "er", "종료재심"
    if re.search(r"review", t, re.I):
        return "ir", "재심"
    if re.search(r"anti-subsidy|countervailing", t, re.I):
        return "as", "상계관세 조사"
    return "ad", "반덤핑 조사"


def deadlines(kind, start):
    d = dt.date.fromisoformat(start)
    iso = lambda x: x.isoformat()
    if kind == "ad":
        p7, p8 = add_months(d, 7), add_months(d, 8)
        return [{"key": "pre", "label": "잠정 관세 사전 공개(보통 시점 — 잠정 관세 4주 전 당사자에게)", "date": iso(p7 - dt.timedelta(days=28)), "basis": "기본규정 제19a조(4주)·제7조 1항(보통 7개월)"},
                {"key": "prov", "label": "잠정 관세 보통 시한(7개월)", "date": iso(p7), "basis": "기본규정 제7조 1항"},
                {"key": "provMax", "label": "잠정 관세 최종 시한(8개월)", "date": iso(p8), "basis": "기본규정 제7조 1항"},
                {"key": "final", "label": "조사 종료 시한(14개월)", "date": iso(add_months(d, 14)), "basis": "기본규정 제6조 9항"}]
    if kind in ("er", "ir"):
        return [{"key": "final", "label": "재심 보통 종료(12개월)", "date": iso(add_months(d, 12)), "basis": "기본규정 제11조 5항"},
                {"key": "finalMax", "label": "재심 종료 시한(15개월)", "date": iso(add_months(d, 15)), "basis": "기본규정 제11조 5항"}]
    if kind == "as":
        return [{"key": "final", "label": "조사 종료 시한(13개월)", "date": iso(add_months(d, 13)), "basis": "상계관세 기본규정 2016/1037 제11조 9항"}]
    if kind == "sg":
        return [{"key": "final", "label": "조치 결정 시한(9개월)", "date": iso(add_months(d, 9)), "basis": "개시 공고 8항(예외 때 최대 2개월 연장 — 연장하면 관보 공고)"},
                {"key": "finalMax", "label": "연장 때 최대(11개월)", "date": iso(add_months(d, 11)), "basis": "개시 공고 8항"}]
    return []


def step_kind(title):
    k, _ = kind_of(title)
    if k in ("수입 등록",):
        return "registration", k
    if k in ("잠정 관세", "세이프가드 잠정 조치"):
        return "provisional", k
    if k in ("확정 관세", "확정 관세 연장(종료재심 결과)", "조사 종료·조치 폐지", "세이프가드 조치"):
        return "done", k
    return None, k


def proceedings(rows, prev_procs, now):
    """개시 공고(제목에 Korea, 또는 출입 업종 품목 세이프가드) → 진행 사건. rows: [{celex, date, title}]"""
    old = {p["celex"]: p for p in prev_procs or [] if isinstance(p, dict) and p.get("celex")}
    out = []
    for d in sorted(rows, key=lambda r: r["date"]):
        pt = proc_type(d["title"])
        if not pt:
            continue
        korea = bool(KOREA.search(d["title"]))
        beat = bool(BEAT_PRODUCT.search(d["title"]))
        if not (korea or (pt[0] in ("sg", "sgr") and beat)):
            continue
        prod = product_of(d["title"])
        key = norm_product(prod)
        steps = []
        for r in rows:
            if r["date"] < d["date"] or r["celex"] == d["celex"] or r["title"].lower().startswith("notice"):
                continue
            rk = norm_product(product_of(r["title"]))
            if not key or not rk or not (key in rk or rk in key):
                continue
            if korea and not KOREA.search(r["title"]):
                continue
            if pt[0] in ("sg", "sgr") and not SAFEGUARD.search(r["title"]):
                continue
            if pt[0] not in ("sg", "sgr") and SAFEGUARD.search(r["title"]):
                continue
            if pt[0] == "er" and kind_of(r["title"])[0] == "확정 관세":
                continue                  # 종료재심은 '종료재심 결과' 확정·폐지만
            if pt[0] in ("ad", "as") and kind_of(r["title"])[0] == "확정 관세 연장(종료재심 결과)":
                continue
            sk, ko = step_kind(r["title"])
            if sk:
                steps.append({"date": r["date"], "celex": r["celex"], "number": number_of(r["title"], r["celex"]), "kind": ko, "step": sk, "url": EURLEX + r["celex"]})
        steps.sort(key=lambda x: x["date"])
        stage = "done" if any(x["step"] == "done" for x in steps) else "provisional" if any(x["step"] == "provisional" for x in steps) else "open"
        last = steps[-1]["date"] if steps else d["date"]
        if stage == "done" and last < (now.date() - dt.timedelta(days=DONE_KEEP_DAYS)).isoformat():
            continue
        dl = deadlines(pt[0], d["date"])
        if stage == "provisional":
            dl = [x for x in dl if x["key"] not in ("pre", "prov", "provMax")]
        prev = old.get(d["celex"]) or {}
        out.append({"id": f"euproc:{d['celex']}", "celex": d["celex"], "date": d["date"], "title": d["title"][:400], "product": prod, "type": pt[0], "typeKo": pt[1],
                    "korea": korea, "beat": beat, "stage": stage, "steps": steps[-4:], "deadlines": [] if stage == "done" else dl,
                    "schedule": prev.get("schedule"), **({"scheduleError": prev["scheduleError"]} if prev.get("scheduleError") else {}),
                    "url": EURLEX + d["celex"]})
    return out


def schedule_quote(text):
    """개시 공고 본문의 일정 문장(원문 그대로, 최대 3개). 'Schedule of the investigation' 절, 없으면 'months'가 든 기한 문장."""
    m = re.search(r"schedule of the (?:investigation|review|proceeding)(.{0,2500})", text, re.I | re.S)
    part = m.group(1) if m else text
    out = []
    for sent in re.split(r"(?<=[.;])\s+(?=[A-Z(])", part):
        if re.search(r"\b(?:\d+|nine|seven|eight|twelve|thirteen|fourteen|fifteen) months?\b|\b(?:4|four|3|three) weeks\b|\b200 days", sent, re.I) and 30 <= len(sent) <= 900:
            sent = sent.strip()
            out.append(sent[:420] + (" …" if len(sent) > 420 else ""))
        if len(out) >= 3:
            break
    return out


# ── EU 기업결합(11-21) ─────────────────────────────────────────────
# 경쟁지 11-14 [단독] '포스코·JSW 인도 합작제철소, EU 기업결합 승인'은 EU 관보 공고였다 — 사전 신고(10-30, 52026M12449)와
# 승인 결정(11-12, 32026M12449)이 같은 출판청 목록에 있었다. 탐침(11-21): 5월 뒤 'concentration' 제목 592건(사전 신고 212·이의 없음 177·결정·철회).
# 제목의 당사자('Case M.12449 – POSCO / JSW / SAFFRON / PMH')에 출입처 영문 이름이 있을 때만. 계열사는 뺀다(POSCO FLOW·POSCO International 등,
# 'TMUS / KIA / I3 BROADBAND'의 KIA는 기아가 아니다 — 기아는 KIA CORPORATION·KIA MOTORS만).
MERGER_DAYS = 30
MERGER_NAMES = [
    ("포스코", r"\bPOSCO\b(?!\s*(?:INTERNATIONAL|FUTURE|E&C|DX|FLOW|HOLDINGS|A&C|M-TECH|WIDE|ICT|ENERGY|STEELEON|MOBILITY))"),
    ("포스코홀딩스", r"POSCO HOLDINGS"), ("현대차", r"HYUNDAI MOTOR"), ("기아", r"\bKIA (?:CORPORATION|MOTORS|CORP)\b"), ("현대모비스", r"HYUNDAI MOBIS"),
    ("현대위아", r"HYUNDAI WIA"), ("HL만도", r"\bHL MANDO\b|\bMANDO CORP"), ("현대제철", r"HYUNDAI STEEL"), ("동국제강", r"DONGKUK STEEL"),
    ("동국씨엠", r"DONGKUK (?:CM|COATED)"), ("세아제강", r"SEAH STEEL(?! HOLDINGS)"), ("세아홀딩스", r"SEAH (?:STEEL )?HOLDINGS"), ("KG스틸", r"\bKG STEEL"),
    ("고려아연", r"KOREA ZINC"), ("영풍", r"YOUNG ?POONG"), ("한국타이어", r"HANKOOK TIRE|HANKOOK & COMPANY"), ("넥센타이어", r"NEXEN TIRE"),
    ("금호타이어", r"KUMHO TIRE"), ("HD현대일렉트릭", r"HD HYUNDAI ELECTRIC"), ("LS일렉트릭", r"LS ELECTRIC"), ("LS전선", r"LS CABLE"),
    ("대한전선", r"TAIHAN"), ("LS MnM", r"LS MNM"), ("두산에너빌리티", r"DOOSAN ENERBILITY"), ("GS칼텍스", r"GS CALTEX"),
    ("한화솔루션", r"HANWHA SOLUTIONS|HANWHA Q ?CELLS|\bQCELLS\b"), ("OCI", r"\bOCI (?:HOLDINGS|COMPANY|CO)\b"), ("LG화학", r"\bLG CHEM"),
    ("롯데케미칼", r"LOTTE CHEMICAL(?!\s*TITAN)"), ("금호석유화학", r"KUMHO PETROCHEMICAL"), ("S-OIL", r"\bS-OIL\b"), ("SK이노베이션", r"SK INNOVATION"),
    ("HD현대오일뱅크", r"HYUNDAI OILBANK"), ("태광", r"TAEKWANG"), ("DL케미칼", r"DL CHEMICAL"), ("동성케미칼", r"DONGSUNG CHEMICAL"),
]


def merger_query(since):
    return query(since).replace('"anti-dumping|countervailing|anti-subsidy|safeguard"', '"concentration"').replace("LIMIT 200", "LIMIT 400")


def merger_kind(title):
    t = title or ""
    if re.search(r"Prior notification", t, re.I):
        return "사전 신고", "notified"
    if re.search(r"Withdrawal of notification", t, re.I):
        return "신고 철회", "withdrawn"
    if re.search(r"incompatible|prohibit", t, re.I):
        return "불허", "prohibited"
    if re.search(r"initiation of proceedings|open(?:ing)? proceedings|Article 6\(1\)\(c\)", t, re.I):
        return "2단계 심사 개시", "phase2"
    if re.search(r"Non-opposition|declaring a concentration to be compatible", t, re.I):
        return "승인(이의 없음)", "cleared"
    return None, None


def merger_parts(title):
    """'(Case M.12449 – POSCO / JSW / SAFFRON / PMH)' → ('M.12449', 'POSCO / JSW / SAFFRON / PMH'). 못 읽으면 (None, '')."""
    m = re.search(r"Case (?:No\s*)?(?:COMP/)?(M\.\d{4,6})\s*[–—-]\s*([^)]{2,200})\)", title or "")
    return (m.group(1), re.sub(r"\s+", " ", m.group(2)).strip()) if m else (None, "")


def merger_names(parties):
    return [ko for ko, rx in MERGER_NAMES if re.search(rx, parties or "", re.I)]


# 사전 신고 공고 본문(11-21 탐침: publications.europa.eu/resource/celex/52026M12609, 영어 XHTML 10KB) — '1. On 10 November 2026, the Commission received
# notification …'·당사자 줄('— Certares Management LLC (‘Certares Management’, US),')·거래 문장(… will acquire within the meaning of Article 3(1)(b) …)·
# '2. The business activities …'·'Observations must reach the Commission not later than 10 days following the date of this publication'.
# 포스코 건(M.12449)은 10-19 접수 → 10-30 관보 → 11-12 승인 → 11-14 경쟁지 단독. 제목만으로는 거래가 무엇인지 몰라 기사 판단을 못 한다.
# 'TMUS / KIA …'처럼 이름만 같은 회사를 거르려고 본문에 Korea가 있는지도 본다(탐침: 기아로 잡힌 M.12477 본문에 Korea 없음).
MERGER_BODY_BUDGET = 3
MONTHS_EN = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
                                         "November", "December"], 1)}


def merger_facts(text, published=""):
    """사전 신고 본문 → {notifiedOn, deadline, undertakings[], transaction, activities, korea}. 못 읽은 칸은 비운다(만들지 않는다)."""
    t = re.sub(r"\s+", " ", text or "")
    out = {"korea": bool(re.search(r"\bKorea\b", t))}
    m = re.search(r"On (\d{1,2}) ([A-Z][a-z]+) (20\d\d),? the Commission received (?:a )?notification", t)
    if m and m.group(2) in MONTHS_EN:
        out["notifiedOn"] = f"{m.group(3)}-{MONTHS_EN[m.group(2)]:02d}-{int(m.group(1)):02d}"
    m = re.search(r"not later than (\d{1,2}) days following the date of this publication", t)
    if m and re.match(r"\d{4}-\d\d-\d\d$", published or ""):
        out["deadline"] = (dt.date.fromisoformat(published) + dt.timedelta(days=int(m.group(1)))).isoformat()
    head = t.split("2. The business activities", 1)[0]
    parties = list(re.finditer(r"[—–]\s*([A-Z0-9][^—–(]{1,120}?)\s*\(\s*[‘'\"“]([^’'\"”]{1,60})[’'\"”]\s*,\s*([A-Za-z][A-Za-z .&-]{1,40}?)\s*\)", head))
    out["undertakings"] = [f"{p.group(1).strip()} ({p.group(3).strip()})" for p in parties][:6]
    if parties:
        tail = head[parties[-1].end():].lstrip(" ,.;")
        key = re.search(r"within the meaning of Article 3|\bwill (?:acquire|merge)|\bacquires?\b", tail)
        if key:
            # 문장 처음: 소문자·닫는 괄호 뒤 '. 대문자'(S.p.A.·N.V. 같은 약칭 점은 문장 끝으로 보지 않는다)
            starts = [m.end() for m in re.finditer(r"(?<=[a-z)])\.\s+(?=[A-Z])", tail[:key.start()])]
            end = re.search(r"(?<=[a-z)\d])\.(?=\s+[A-Z]|\s*$)", tail[key.end():])
            sent = tail[starts[-1] if starts else 0: key.end() + (end.end() if end else 300)].strip()
            more = re.match(r"\s*(The concentration is accomplished[^.]*\.)", tail[key.end() + (end.end() if end else 300):])
            out["transaction"] = (sent + (" " + more.group(1) if more else ""))[:500]
    m = re.search(r"2\. The business activities of the undertakings? concerned (?:are|is) the following:\s*(.*?)(?:\s4\. On preliminary examination|\s4\. The Commission|$)", t)
    if m:
        out["activities"] = m.group(1).strip()[:700]
    return out


def merger_fact_text(f):
    if not f:
        return ""
    bits = []
    if f.get("notifiedOn"):
        bits.append(f"신고 접수 {f['notifiedOn']}")
    if f.get("deadline"):
        bits.append(f"제3자 의견 마감 {f['deadline']}")
    if f.get("undertakings"):
        bits.append("당사자: " + " / ".join(f["undertakings"][:4]))
    if f.get("transaction"):
        bits.append(f"거래(원문): 「{f['transaction'][:300]}」")
    if f.get("activities"):
        bits.append(f"사업 내용(원문): 「{f['activities'][:400]}」")
    if not f.get("korea"):
        bits.append("본문에 한국(Korea) 없음 — 이름만 같은 다른 회사일 수 있음")
    return " · ".join(bits)


def mergers_run(get, now, prev, stamp, sleep):
    """EU 기업결합 공고(사전 신고·승인·철회·2단계·불허) 중 당사자에 출입처가 든 것 → (mergers, events, error). 첫 실행은 기준선."""
    first = "mergers" not in (prev or {})
    cases = {m["case"]: m for m in (prev or {}).get("mergers") or [] if isinstance(m, dict) and m.get("case")}
    since = (now.date() - dt.timedelta(days=MERGER_DAYS)).isoformat()
    try:
        r = get(SPARQL, params={"query": merger_query(since), "format": "application/sparql-results+json"}, headers=UA, timeout=180)
        if r.status_code >= 500:
            sleep(RETRY_WAIT)
            r = get(SPARQL, params={"query": merger_query(since), "format": "application/sparql-results+json"}, headers=UA, timeout=180)
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}")
        rows = r.json()["results"]["bindings"]
    except Exception as e:  # noqa: BLE001
        return list(cases.values()), [], f"기업결합 목록 {str(e)[:40] or type(e).__name__}"
    events = []
    budget, tried = [MERGER_BODY_BUDGET], set()

    def read_facts(rec):
        st = rec["stages"]["notified"]
        if budget[0] <= 0 or rec.get("facts") or rec["case"] in tried or rec.get("factsError", {}).get("tries", 0) >= 3:
            return
        budget[0] -= 1
        tried.add(rec["case"])
        sleep(PAUSE)
        try:
            rec["facts"] = merger_facts(read_body(get, st["celex"]), st["date"])
            rec.pop("factsError", None)
        except Exception as e:  # noqa: BLE001 — 본문 실패는 제목 줄만 남기고 다음 실행에 다시(3번까지)
            rec["factsError"] = {"error": str(e)[:40] or type(e).__name__, "tries": rec.get("factsError", {}).get("tries", 0) + 1}

    for b in sorted(rows, key=lambda b: b["date"]["value"]):
        celex, title, date = b["celex"]["value"], plain(b["title"]["value"]), b["date"]["value"][:10]
        if not re.match(r"^[35]\d{4}M", celex):
            continue
        kind, stage = merger_kind(title)
        case, parties = merger_parts(title)
        if not kind or not case:
            continue
        names = merger_names(parties)
        if not names:
            continue
        rec = cases.setdefault(case, {"case": case, "parties": parties, "companies": names, "stages": {}, "firstSeen": stamp})
        if stage in rec["stages"]:
            continue
        url = f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"
        rec["stages"][stage] = {"date": date, "celex": celex, "url": url, "kind": kind, "simplified": bool(re.search(r"simplified procedure", title, re.I))}
        rec["latest"] = stage
        if first:
            continue
        if stage == "notified":
            read_facts(rec)
        facts = rec.get("facts") or {}
        ft = merger_fact_text(facts)
        text = (f"EU 기업결합 — {kind}: {case} 「{parties}」({date}) · 출입처 {'·'.join(names)}"
                + (" · 간이 절차 대상(통상 신고 뒤 25영업일 안 결정)" if rec["stages"][stage]["simplified"] else "")
                + (f" · 사전 신고 {rec['stages']['notified']['date']}" if stage != "notified" and rec["stages"].get("notified") else "")
                + (f" · {ft}" if ft else "")
                + " (EU 집행위원회 경쟁총국 공고 — 사전 신고는 심사 시작, 승인은 '이의 없음' 결정. 거래 구조·지분·금액은 회사 확인)")
        tier = "C" if facts and not facts.get("korea") else "A"
        events.append({"id": f"eumerger:{case}:{stage}", "kind": f"EU 기업결합({kind})", "tier": tier, "company": "·".join(names), "companies": names,
                       "product": "", "number": case, "date": date, "korea": False, "merger": True, "url": url, "text": text, "detectedAt": stamp})
    # 예전에 잡힌(본문 읽기 전) 사전 신고도 남은 예산으로 채운다
    for rec in sorted(cases.values(), key=lambda m: m["stages"].get("notified", {}).get("date", ""), reverse=True):
        if rec["stages"].get("notified") and not rec.get("facts"):
            read_facts(rec)
    keep_from = (now.date() - dt.timedelta(days=KEEP_DAYS)).isoformat()
    kept = [m for m in cases.values() if max((s["date"] for s in m["stages"].values()), default="") >= keep_from]
    return sorted(kept, key=lambda m: max(s["date"] for s in m["stages"].values()), reverse=True)[:40], events, None


# 출판청 SPARQL은 가끔 504·503을 낸다(11-21 07:00 실행 HTTP 504 — 다음 17:50 실행까지 EU 관보가 비었다).
# 서버 오류(5xx)·시간 초과·연결 끊김이면 RETRY_WAIT초 뒤 한 번만 다시 묻는다(4xx·형식 오류는 다시 묻지 않는다).
RETRY_WAIT = 20


def list_docs_retry(get, since, sleep, limit=200):
    try:
        return list_docs(get, since, limit)
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        if not (msg.startswith("HTTP 5") or type(e).__name__ in ("ReadTimeout", "ConnectTimeout", "ConnectionError", "Timeout")):
            raise
        sleep(RETRY_WAIT)
        return list_docs(get, since, limit)


def run(now, previous=None, *, get=None, sleep=time.sleep):
    if get is None:
        import requests
        get = requests.get
    stamp = now.isoformat(timespec="seconds")
    prev = previous or {}
    first = not prev.get("seen")
    seen = list(prev.get("seen") or [])
    recs = {r["id"]: r for r in prev.get("records") or [] if isinstance(r, dict) and r.get("id")}
    events = [e for e in prev.get("events") or [] if isinstance(e, dict)
              and str(e.get("detectedAt", "")) >= (now - dt.timedelta(days=EVENT_DAYS)).isoformat()]
    check = {"source": "EU 관보(Cellar SPARQL)", "status": "ok", "returned": 0}
    since = (now.date() - dt.timedelta(days=LOOKBACK_DAYS)).isoformat()
    try:
        docs = list_docs_retry(get, since, sleep)
    except Exception as e:  # noqa: BLE001
        check.update(status="failed", error=f"목록 {str(e)[:60] or type(e).__name__}")
        return {**prev, "schema": SCHEMA, "generatedAt": stamp, "status": "failed", "checks": [check], "stale": True} if prev else \
            {"schema": SCHEMA, "generatedAt": stamp, "status": "failed", "checks": [check], "records": [], "events": []}
    check["returned"] = len(docs)
    have = set(seen)
    new = sorted([d for d in docs if d["celex"] not in have], key=lambda d: d["date"], reverse=True)
    errors, budget, fresh, skipped = [], BODY_BUDGET, 0, 0
    for d in new:
        korea = bool(KOREA.search(d["title"]))
        kind, _ = kind_of(d["title"])
        beat_product = bool(BEAT_PRODUCT.search(d["title"]))
        # 본문을 볼 것: 한국산 출입 업종 품목, 또는 출입 업종 품목의 확정·잠정 관세(출입처 해외 법인이 수출자일 수 있다)·만료 예정 공고
        sg_beat = bool(SAFEGUARD.search(d["title"])) and beat_product
        want = (korea and beat_product) or (beat_product and kind in ("확정 관세", "잠정 관세", "확정 관세 연장(종료재심 결과)")) or kind == "만료 예정 공고" or sg_beat
        if not want:
            skipped += 1
            seen.append(d["celex"])
            continue
        if budget <= 0:
            continue                      # 다음 실행에(본 것으로 두지 않음)
        budget -= 1
        sleep(PAUSE)
        try:
            body = read_body(get, d["celex"])
        except Exception as e:  # noqa: BLE001
            errors.append(f"{d['celex']} {str(e)[:30] or type(e).__name__}")
            continue
        seen.append(d["celex"])
        rec = record_of(d, body, stamp)
        # 만료 예정 공고는 본문에 한국이 나올 때만, 제목에 한국이 없는 규정은 출입처 이름이 나올 때만 남긴다
        if not rec["korea"] and not rec["companies"] and not rec.get("safeguard") and not (kind == "만료 예정 공고" and rec.get("koreaMentions")):
            skipped += 1
            continue
        rec["baseline"], rec["isNew"] = first, not first
        recs[rec["id"]] = rec
        if not first:
            events.append(event_of(rec, stamp))
            fresh += 1
    pending = sum(1 for d in new if d["celex"] not in set(seen))
    if pending:
        errors.append(f"본문 {pending}건은 다음 실행(한도)")
    if errors:
        check.update(status="partial", error="; ".join(errors[:3]))
    # 판정 일정 — 긴 목록은 하루 한 번(실패하면 직전 목록), 진행 사건은 매번 다시 묶는다(새 21일 목록의 잠정·확정 규정을 바로 반영)
    history, history_at, history_err = list(prev.get("history") or []), prev.get("historyAt"), None
    if not history_at or (now - dt.datetime.fromisoformat(history_at)).total_seconds() >= HISTORY_EVERY_H * 3600:
        try:
            got = list_docs(get, (now.date() - dt.timedelta(days=HISTORY_DAYS)).isoformat(), limit=2000)
            history = [d for d in got if KOREA.search(d["title"]) or SAFEGUARD.search(d["title"])]
            history_at = stamp
        except Exception as e:  # noqa: BLE001
            history_err = f"판정 일정 목록 {str(e)[:40] or type(e).__name__} — 직전 목록"
    rows = {d["celex"]: d for d in history}
    for d in docs:
        if KOREA.search(d["title"]) or SAFEGUARD.search(d["title"]):
            rows.setdefault(d["celex"], d)
    procs = proceedings(list(rows.values()), prev.get("proceedings"), now)
    budget = SCHEDULE_BUDGET
    for pr in procs:
        if budget <= 0 or pr["stage"] == "done" or pr.get("schedule") is not None or pr.get("scheduleError", {}).get("tries", 0) >= 3:
            continue
        budget -= 1
        sleep(PAUSE)
        try:
            pr["schedule"] = schedule_quote(read_body(get, pr["celex"]))
            pr.pop("scheduleError", None)
        except Exception as e:  # noqa: BLE001
            pr["scheduleError"] = {"error": str(e)[:40] or type(e).__name__, "tries": pr.get("scheduleError", {}).get("tries", 0) + 1}
    if history_err:
        errors.append(history_err)
        check.update(status="partial", error="; ".join(errors[:3]))
    mergers, mevents, merr = mergers_run(get, now, prev, stamp, sleep)
    known = {e["id"] for e in events}
    for e in mevents:
        if e["id"] not in known:
            events.append(e)
            fresh += 1
    if merr:
        errors.append(merr)
        check.update(status="partial", error="; ".join(errors[:3]))
    keep_from = (now.date() - dt.timedelta(days=KEEP_DAYS)).isoformat()
    kept = sorted((r for r in recs.values() if (r.get("date") or "") >= keep_from), key=lambda r: (r.get("date") or "", r.get("celex")), reverse=True)[:MAX_RECORDS]
    for r in kept:
        if r.get("firstSeen") != stamp:
            r["isNew"] = False
    return {"schema": SCHEMA, "generatedAt": stamp, "status": check["status"], "checks": [check], "baselineAt": prev.get("baselineAt") or stamp,
            "seen": seen[-800:], "records": kept, "events": events[-60:], "fresh": fresh, "skipped": skipped,
            "history": history[-300:], "historyAt": history_at, "proceedings": procs, "mergers": mergers,
            "rules": ["EU 관보의 무역구제 규정·공고(유럽연합 출판청 목록, 최근 21일). 제목에 Korea가 든 출입 업종 품목과, 본문에 출입처 이름이 나온 확정·잠정 관세 규정만.",
                      "출입처 해외 법인(포스코 베트남 등)이 수출자로 나온 규정은 그 나라산 조치다 — 한국산 조치가 아니다.",
                      "세율은 본문 제1조에서 출입처 이름 뒤 첫 % 값을 자동으로 읽은 것 — 기사 전 원문 표 대조. 첫 실행은 기준선.",
                      "판정 일정의 날짜는 규정상 시한(개시일부터 계산)이지 발표 예정일이 아니다 — 실제 발표는 더 이르거나(보통) 연장 공고로 늦어질 수 있다.",
                      "EU 기업결합: 관보 공고 제목의 당사자에 출입처 영문 이름이 든 사전 신고·승인·철회·2단계·불허만(최근 30일). 계열사(POSCO FLOW·POSCO International 등)는 뺀다."]}


def main():
    ap = argparse.ArgumentParser(description="EU 관보 무역구제(기자 전용 저장소로)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    import private_store
    now = now_kst()
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    previous = None
    if token and not a.dry_run:
        try:
            previous = private_store.get("eu-trade-defence", token)
        except private_store.StoreError as e:
            print(f"::warning title=eu-trade-defence-state::이전 상태 조회 실패({e}) — 이번에는 저장하지 않는다(기준선을 다시 잡지 않으려고)")
            return 0
    doc = run(now, previous)
    c = doc["checks"][0]
    # 공개 로그에는 건수만(규정 제목·업체·세율은 찍지 않는다)
    print(f"::notice title=eu-trade-defence::상태 {doc['status']} · 목록 {c.get('returned', 0)}건 · 저장 {len(doc.get('records') or [])} · "
          f"이번 새 항목 {doc.get('fresh', 0)} · 업종 밖·무관 {doc.get('skipped', 0)} · 진행 사건 {len(doc.get('proceedings') or [])}"
          + (f" · {c['error']}" if c.get("error") else ""))
    if a.dry_run or not token:
        if not token and not a.dry_run:
            print("::warning title=eu-trade-defence-push::MCP_ACCESS_TOKEN 미설정 — 결과를 저장하지 않음")
        return 0
    status = private_store.put("eu-trade-defence", doc, token)
    print(f"::notice title=eu-trade-defence-push::기자 전용 저장소 전송 HTTP {status}")
    return 0 if status == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
