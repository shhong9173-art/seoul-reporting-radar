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
    if has(r"notice of initiation|initiation of an?\b"):
        return ("재심·우회 조사 개시", "B") if has(r"review|circumvention") else ("조사 개시", "A")
    if has(r"\bcorrecting\b|\bamending\b|corrigendum"):
        return "변경·정정", "B"
    if has(r"subject to registration"):
        return "수입 등록", "B"
    if has(r"\brepealing\b|\bterminating\b|termination of"):
        return "조사 종료·조치 폐지", "A"
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
    m = re.search(r"imports? of (?:certain )?(.+?) originating in", title or "", re.I)
    return (m.group(1) if m else "")[:100]


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


def list_docs(get, since):
    r = get(SPARQL, params={"query": query(since), "format": "application/sparql-results+json"}, headers=UA, timeout=120)
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
    if names and tier == "A":
        rec["tier"] = "A"
    elif korea and beat_product and kind in ("확정 관세", "잠정 관세", "조사 개시", "확정 관세 연장(종료재심 결과)", "조사 종료·조치 폐지"):
        rec["tier"] = "A"
    else:
        rec["tier"] = "B"
    return rec


def event_of(rec, stamp):
    rates = " · ".join(f"{r['exporter']} {r['rate']}" + (f"({r['code']})" if r.get("code") else "") for r in rec.get("rates") or [])
    text = (f"EU 관보 무역구제 — {rec['kind']}: {rec['number']} 「{rec['title'][:240]}」({rec['date']})"
            + (f" · 본문에 출입처 {'·'.join(rec['companies'])}" if rec.get("companies") else " · 본문에 출입처 이름 없음(한국산 품목)")
            + (f" · 제1조 세율 {rates}" if rates else "")
            + (f" · 본문 대목 「{rec['snippets'][0]}」" if rec.get("snippets") else "")
            + (f" · {rec['note']}" if rec.get("note") else "")
            + " (EU 집행위원회 시행규정·공고 — 세율·대상 업체는 본문 제1조 표로. 출입처 해외 법인이 수출자로 나온 것은 그 나라산 조치)")
    return {"id": rec["id"], "kind": f"EU 관보 무역구제({rec['kind']})", "tier": rec["tier"], "company": "·".join(rec.get("companies") or []),
            "companies": rec.get("companies") or [], "product": rec.get("product"), "number": rec.get("number"), "date": rec.get("date"),
            "korea": rec.get("korea"), "url": rec["url"], "text": text, "detectedAt": stamp}


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
        docs = list_docs(get, since)
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
        want = (korea and beat_product) or (beat_product and kind in ("확정 관세", "잠정 관세", "확정 관세 연장(종료재심 결과)")) or kind == "만료 예정 공고"
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
        if not rec["korea"] and not rec["companies"] and not (kind == "만료 예정 공고" and rec.get("koreaMentions")):
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
    keep_from = (now.date() - dt.timedelta(days=KEEP_DAYS)).isoformat()
    kept = sorted((r for r in recs.values() if (r.get("date") or "") >= keep_from), key=lambda r: (r.get("date") or "", r.get("celex")), reverse=True)[:MAX_RECORDS]
    for r in kept:
        if r.get("firstSeen") != stamp:
            r["isNew"] = False
    return {"schema": SCHEMA, "generatedAt": stamp, "status": check["status"], "checks": [check], "baselineAt": prev.get("baselineAt") or stamp,
            "seen": seen[-800:], "records": kept, "events": events[-60:], "fresh": fresh, "skipped": skipped,
            "rules": ["EU 관보의 무역구제 규정·공고(유럽연합 출판청 목록, 최근 21일). 제목에 Korea가 든 출입 업종 품목과, 본문에 출입처 이름이 나온 확정·잠정 관세 규정만.",
                      "출입처 해외 법인(포스코 베트남 등)이 수출자로 나온 규정은 그 나라산 조치다 — 한국산 조치가 아니다.",
                      "세율은 본문 제1조에서 출입처 이름 뒤 첫 % 값을 자동으로 읽은 것 — 기사 전 원문 표 대조. 첫 실행은 기준선."]}


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
          f"이번 새 항목 {doc.get('fresh', 0)} · 업종 밖·무관 {doc.get('skipped', 0)}" + (f" · {c['error']}" if c.get("error") else ""))
    if a.dry_run or not token:
        if not token and not a.dry_run:
            print("::warning title=eu-trade-defence-push::MCP_ACCESS_TOKEN 미설정 — 결과를 저장하지 않음")
        return 0
    status = private_store.put("eu-trade-defence", doc, token)
    print(f"::notice title=eu-trade-defence-push::기자 전용 저장소 전송 HTTP {status}")
    return 0 if status == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
