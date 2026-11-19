"""영국 정부 무역구제 고시(gov.uk 'Trade remedies notices') — 한국산 조치의 국무장관 결정·수입 등록 고시를 올라온 그날 밤에 잡는다.

근거(11-19 기자 "이거 고쳐"): 11-18 13:00 UTC(한국 22:00) 영국 기업통상부가 「Trade remedies notice 2026/32: definitive anti-dumping
measure on hot-rolled steel plate originating from South Korea」를 올렸고(현대제철 7.04%·포스코 12.19%·그 밖 23.07%, TRA 권고와 다르게 결정),
글로벌이코노믹이 11-19 06:58에 '영국 정부, 한국산 열연강판 반덤핑 관세 확정'으로 썼다. 레이더는 TRA 공개기록의 'Final Recommendation'
(조사기관 권고)만 잡았고, 국무장관의 최종 결정 고시는 감시 밖이었다.

원천(탐침 18, 11-19 — 로그인 없음, robots 허용):
- 모음 https://www.gov.uk/api/content/government/collections/trade-remedies-notices — links.documents(제목·base_path·public_updated_at) 60건
- 게시물 /api/content/<base_path> — details.attachments(고시 하나하나가 HTML 첨부: 'Trade remedies notice 2026/32: …')
  같은 게시물에 새 고시가 첨부로 붙는다(한국산 열연 후판 게시물은 2025-07-23 처음 올라와 2025/16 수입 등록 → 2026/17 잠정 조치 권고 거부 →
  2026/32 확정 조치가 차례로 붙음). 그래서 게시물 갱신 시각이 바뀌면 첨부 목록을 다시 읽고, 처음 보는 첨부만 새 고시로 본다.
- HTML 첨부 /api/content/<첨부 url> — details.body(업체별 세율 표: 'Hyundai Steel 7.04% 8A78 POSCO 12.19% 8A79 …'), first_published_at

잡는 것: 제목에 Korea가 든 게시물·첨부의 새 고시. 등급 A = 확정·잠정 조치, 권고 거부, 조치 종료·변경·연장(국무장관 결정),
B = 수입 등록·그 밖 고시. 첫 실행은 기준선(목록에만). 결과는 기자 전용 저장소(uk-trade-notices)로만 — 공개 로그에는 건수만.
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

SCHEMA = "uk_trade_notices/v1"
KST = dt.timezone(dt.timedelta(hours=9))
API = "https://www.gov.uk/api/content"
COLLECTION = API + "/government/collections/trade-remedies-notices"
SITE = "https://www.gov.uk"
UA = {"User-Agent": "Mozilla/5.0 seoul-reporting-radar (reporter research)", "Accept": "application/json"}
KOREA = re.compile(r"\bKorea\b", re.I)
PUB_BUDGET = 6          # 한 실행에 다시 읽는 게시물 수
ATT_BUDGET = 10         # 한 실행에 읽는 HTML 첨부(고시 본문) 수
PAUSE = 1.0
PARSER = 2              # 11-19 2판: 권고 세율 범위 ↔ 국무장관 결정(거부·수용)·확정 세율 범위. 옛 판으로 읽은 고시는 다시 읽는다(이벤트 없음)
REPARSE_BUDGET = 4
KEEP_DAYS = 550        # 한 사건의 수입 등록 → 잠정 → 확정이 1년 넘게 걸린다(한국산 열연 후판 2025-07 등록 → 2026-11 확정)
EVENT_DAYS = 60
MAX_NOTICES = 80
# 첨부 제목 → 고시 종류(국무장관 결정이면 A)
KINDS = [
    (r"reject|not to accept|declin", "TRA 권고 거부", "A"),
    (r"\bdefinitive\b|imposition|impose", "확정 조치", "A"),
    (r"\bprovisional\b", "잠정 조치", "A"),
    (r"terminat|revok|revocation|\bend(?:ing)?\b", "조치 종료", "A"),
    (r"variation|\bvary\b|amend", "조치 변경", "A"),
    (r"extension|extend|expiry review|transition review|interim review", "연장·재심 결과", "A"),
    (r"registration", "수입 등록", "B"),
]


def now_kst():
    return dt.datetime.now(KST)


def plain(raw):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw or ""))).strip()


def kind_of(title):
    for rx, label, tier in KINDS:
        if re.search(rx, title or "", re.I):
            return label, tier
    return "고시", "B"


def number_of(title):
    m = re.search(r"notice (\d{4}/\d{1,3})", title or "", re.I)
    return m.group(1) if m else None


def product_of(pub_title):
    """'Trade remedies notice: hot-rolled steel plates originating from South Korea (anti-dumping)' → 'hot-rolled steel plates'"""
    t = re.sub(r"(?i)^trade remedies notices?:\s*", "", pub_title or "")
    t = re.sub(r"\s*\([^)]*\)\s*$", "", t)
    t = re.split(r"(?i)\s+(?:originating\s+)?from\s+", t)[0]
    t = re.sub(r"(?i)^(?:registration of imports of|anti-dumping duty on|countervailing duty on|definitive [\w-]+ (?:duty|measure) on)\s+", "", t)
    return t.strip()[:80]


def companies_in(text):
    from tra_file_watch import companies_in as ci
    return ci(text)


def rates_in(body):
    """본문 세율 표 → [{name, rate, code}] ('Hyundai Steel 7.04% 8A78 POSCO 12.19% 8A79 All other … 23.07% 8A80')."""
    out, last = [], 0
    for m in re.finditer(r"(\d{1,3}(?:\.\d{1,2})?)\s?%\s+(8[A-Z0-9]{3})\b", body):
        window = re.split(r"(?i)additional code|dumping margin|subsidy (?:amount|margin)|duty rate", body[last:m.start()])[-1].strip()
        last = m.end()
        name = window[-70:].strip(" :;,-")
        if re.search(r"(?i)all other", name):
            name = "그 밖 수출자·생산자"
        out.append({"name": name, "rate": float(m.group(1)), "code": m.group(2)})
    return out[:8]


def blocks(raw):
    """본문 HTML → 문단·표 칸 단위 줄(문장 고르기용 — 표 글자가 문장에 붙지 않게)."""
    t = re.sub(r"(?i)<br\s*/?>|</(?:p|li|td|th|tr|h\d|div|caption)>", "\n", raw or "")
    return [plain(x) for x in t.split("\n") if plain(x)]


def sentences(lines, rx, n=2, cap=240):
    out = []
    for s in (x for line in lines for x in re.split(r"(?<=[.;])\s+(?=[A-Z(])", line)):
        if re.search(rx, s, re.I) and 30 <= len(s) <= 600:
            out.append(s[:cap] + (" …" if len(s) > cap else ""))
        if len(out) >= n:
            break
    return out


def get_json(get, url):
    r = get(url, headers=UA, timeout=40)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}")
    return r.json()


def read_notice(get, att, pub, stamp):
    """HTML 첨부(고시 본문) 한 건 → 기록. 파일 첨부(PDF)는 제목만."""
    title = plain(att.get("title"))
    kind, tier = kind_of(title)
    rec = {"id": f"ukn:{att['url'].rstrip('/').rsplit('/', 1)[-1][:90]}", "url": SITE + att["url"] if att["url"].startswith("/") else att["url"],
           "title": title[:240], "pubTitle": plain(pub.get("title"))[:200], "pubUrl": SITE + pub["base_path"], "product": product_of(pub.get("title")),
           "number": number_of(title), "kind": kind, "tier": tier, "firstSeen": stamp}
    is_html = att["url"].startswith("/") and "html" in str(att.get("content_type") or att.get("attachment_type") or "html").lower()
    if not is_html:
        rec["note"] = "파일 첨부 — 본문 미읽음(원문 열기)"
        rec["published"] = (pub.get("public_updated_at") or "")[:10]
        return rec
    j = get_json(get, API + att["url"])
    raw = (j.get("details") or {}).get("body") or ""
    body, lines = plain(raw), blocks(raw)
    rec["published"] = (j.get("first_published_at") or j.get("public_updated_at") or pub.get("public_updated_at") or "")[:10]
    rec["chars"] = len(body)
    rec["companies"] = companies_in(body + " " + title)
    rec["rates"] = rates_in(body)
    # 권고 대목: 세율이 적힌 권고 문장 먼저('The TRA recommended imposing … with duties of 5.98% to 25.71%'), 없으면 권고 문장
    rec["recommendation"] = sentences(lines, r"recommend[^.]*\d+(?:\.\d+)?\s?%", 1) or sentences(lines, r"recommend", 1)
    rec["decision"] = sentences(lines, r"Secretary of State has decided|decided[^.]{0,80}\b(?:reject|accept)", 1)
    rec["term"] = sentences(lines, r"\b\d+\s+years?\b|come into force|comes into force|expire|until \d", 2)
    rec["parser"] = PARSER
    m = re.search(r"(\d+(?:\.\d+)?)\s?%\s*(?:to|-|–)\s*(\d+(?:\.\d+)?)\s?%", rec["recommendation"][0] if rec["recommendation"] else "")
    if m:
        rec["recRange"] = [float(m.group(1)), float(m.group(2))]
    named = [r["rate"] for r in rec["rates"] if r["rate"] > 0]
    if named:
        rec["finalRange"] = [min(named), max(named)]
    dec = " ".join(rec["decision"])
    rec["verdict"] = "권고 거부·다르게 결정" if re.search(r"\breject", dec, re.I) else "권고 수용" if re.search(r"\baccept", dec, re.I) else None
    return rec


def compare_text(rec):
    """'TRA 권고 5.98~25.71% → 국무장관 7.04~23.07%(권고 거부·다르게 결정)' — 범위를 못 읽으면 ''"""
    rr, fr = rec.get("recRange"), rec.get("finalRange")
    if not rr and not rec.get("verdict"):
        return ""
    rng = lambda r: f"{r[0]:.2f}~{r[1]:.2f}%" if r and r[0] != r[1] else f"{r[0]:.2f}%" if r else "?"
    return f"TRA 권고 {rng(rr)} → 국무장관 확정 {rng(fr)}" + (f"({rec['verdict']})" if rec.get("verdict") else "")


def event_of(rec, stamp):
    def rate_text(r):
        return f"{r['name']} {r['rate']:.2f}%" + (f"({r['code']})" if r.get("code") else "")
    num = f" {rec['number']}" if rec.get("number") else ""
    text = (f"영국 정부 무역구제 고시{num} — {rec['kind']}: 「{rec['title']}」(게시 {rec.get('published') or '날짜 없음'})"
            + (f" · 업체별 세율 {' · '.join(rate_text(r) for r in rec['rates'][:5])}" if rec.get("rates") else "")
            + (f" · {compare_text(rec)}" if compare_text(rec) else "")
            + (f" · 권고 대목 「{rec['recommendation'][0]}」" if rec.get("recommendation") else "")
            + (f" · 결정 대목 「{rec['decision'][0]}」" if rec.get("decision") else "")
            + (f" · 기간 대목 「{rec['term'][0]}」" if rec.get("term") else "")
            + (f" · {rec['note']}" if rec.get("note") else "")
            + " (영국 기업통상부 국무장관 고시 — TRA 권고를 받아 정한 조치. 세율·기간은 원문 표로)")
    return {"id": rec["id"], "kind": f"영국 정부 무역구제 고시({rec['kind']})", "tier": rec["tier"], "company": "·".join(rec.get("companies") or []),
            "companies": rec.get("companies") or [], "product": rec.get("product"), "number": rec.get("number"), "date": rec.get("published"),
            "url": rec["url"], "text": text, "detectedAt": stamp}


def run(now, previous=None, *, get=None, sleep=time.sleep):
    if get is None:
        import requests
        get = requests.get
    stamp = now.isoformat(timespec="seconds")
    prev = previous or {}
    first = not prev.get("pubs")
    pubs_seen = dict(prev.get("pubs") or {})
    atts_seen = set(prev.get("atts") or [])
    notices = {n["id"]: n for n in prev.get("notices") or [] if isinstance(n, dict) and n.get("id")}
    events = [e for e in prev.get("events") or [] if isinstance(e, dict)
              and str(e.get("detectedAt", "")) >= (now - dt.timedelta(days=EVENT_DAYS)).isoformat()]
    check = {"source": "gov.uk 무역구제 고시 모음", "status": "ok", "returned": 0}
    try:
        col = get_json(get, COLLECTION)
        docs = [d for d in (col.get("links") or {}).get("documents") or [] if isinstance(d, dict) and d.get("base_path")]
        if not docs:
            raise RuntimeError("모음에 문서 없음(형식 변경 의심)")
    except Exception as e:  # noqa: BLE001
        check.update(status="failed", error=f"모음 {str(e)[:60] or type(e).__name__}")
        return {**prev, "schema": SCHEMA, "generatedAt": stamp, "status": "failed", "checks": [check], "stale": True} if prev else \
            {"schema": SCHEMA, "generatedAt": stamp, "status": "failed", "checks": [check], "notices": [], "events": []}
    korea = [d for d in docs if KOREA.search(d.get("title") or "")]
    check["returned"] = len(docs)
    check["korea"] = len(korea)
    todo = [d for d in korea if pubs_seen.get(d["base_path"]) != d.get("public_updated_at")]
    todo.sort(key=lambda d: d.get("public_updated_at") or "", reverse=True)
    errors, att_budget, fresh = [], ATT_BUDGET, 0
    for d in todo[:PUB_BUDGET]:
        sleep(PAUSE)
        try:
            pub = get_json(get, API + d["base_path"])
        except Exception as e:  # noqa: BLE001
            errors.append(f"게시물 {str(e)[:30] or type(e).__name__}")
            continue
        pub.setdefault("base_path", d["base_path"])
        atts = [a for a in (pub.get("details") or {}).get("attachments") or [] if isinstance(a, dict) and a.get("url")]
        done = True
        for a in atts:
            if a["url"] in atts_seen:
                continue
            if att_budget <= 0:
                done = False      # 다음 실행에 이어 읽는다(게시물 갱신 시각을 아직 저장하지 않음)
                break
            att_budget -= 1
            sleep(PAUSE)
            try:
                rec = read_notice(get, a, pub, stamp)
            except Exception as e:  # noqa: BLE001
                errors.append(f"고시 본문 {str(e)[:30] or type(e).__name__}")
                done = False
                continue
            atts_seen.add(a["url"])
            rec["baseline"] = first
            rec["isNew"] = not first
            notices[rec["id"]] = rec
            if not first:
                events.append(event_of(rec, stamp))
                fresh += 1
        if done:
            pubs_seen[d["base_path"]] = d.get("public_updated_at")
    if len(todo) > PUB_BUDGET:
        errors.append(f"게시물 {len(todo) - PUB_BUDGET}개는 다음 실행(한도)")
    # 읽는 규칙이 바뀌면(PARSER) 저장된 고시를 다시 읽어 칸을 채운다 — 새 고시가 아니므로 이벤트는 내지 않는다
    stale = [n for n in notices.values() if (n.get("parser") or 1) < PARSER and n.get("url", "").startswith(SITE) and not n.get("note")]
    for n in sorted(stale, key=lambda n: n.get("published") or "", reverse=True)[:REPARSE_BUDGET]:
        sleep(PAUSE)
        try:
            again = read_notice(get, {"url": n["url"][len(SITE):], "title": n["title"]}, {"title": n.get("pubTitle"), "base_path": n.get("pubUrl", SITE)[len(SITE):]}, n.get("firstSeen") or stamp)
        except Exception as e:  # noqa: BLE001
            errors.append(f"다시 읽기 {str(e)[:30] or type(e).__name__}")
            continue
        notices[n["id"]] = {**n, **{k: v for k, v in again.items() if k not in ("firstSeen", "id")}}
    if errors:
        check.update(status="partial", error="; ".join(errors[:3]))
    keep_from = (now - dt.timedelta(days=KEEP_DAYS)).date().isoformat()
    kept = sorted((n for n in notices.values() if (n.get("published") or n.get("firstSeen", "")[:10]) >= keep_from),
                  key=lambda n: (n.get("published") or "", n.get("firstSeen") or ""), reverse=True)[:MAX_NOTICES]
    for n in kept:
        if n.get("firstSeen") != stamp:
            n["isNew"] = False
    return {"schema": SCHEMA, "generatedAt": stamp, "status": check["status"], "checks": [check],
            "baselineAt": prev.get("baselineAt") or stamp, "pubs": pubs_seen, "atts": sorted(atts_seen)[-400:],
            "notices": kept, "events": events[-60:], "fresh": fresh,
            "rules": ["영국 기업통상부(국무장관)가 gov.uk에 올리는 무역구제 고시 — TRA(조사기관) 권고를 받아 정한 최종 조치·수입 등록. 제목에 Korea가 든 것만.",
                      "고시 하나는 게시물의 HTML 첨부다 — 같은 게시물에 새 고시가 붙는다. 첫 실행은 기준선(목록에만).",
                      "세율은 본문 표에서 자동으로 읽은 값('업체 세율(추가 코드)') — 기사 전 원문 표 대조. 권고와 다르게 정했는지는 '권고 대목'과 TRA 권고 문서로."]}


def main():
    ap = argparse.ArgumentParser(description="영국 정부 무역구제 고시(기자 전용 저장소로)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    import private_store
    now = now_kst()
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    previous = None
    if token and not a.dry_run:
        try:
            previous = private_store.get("uk-trade-notices", token)
        except private_store.StoreError as e:
            print(f"::warning title=uk-trade-notices-state::이전 상태 조회 실패({e}) — 이번에는 저장하지 않는다(기준선을 다시 잡지 않으려고)")
            return 0
    doc = run(now, previous)
    c = doc["checks"][0]
    # 공개 로그에는 건수만(고시 제목·업체·세율은 찍지 않는다)
    print(f"::notice title=uk-trade-notices::상태 {doc['status']} · 모음 {c.get('returned', 0)}건 · 한국 게시물 {c.get('korea', 0)} · "
          f"저장 고시 {len(doc.get('notices') or [])} · 이번 새 고시 {doc.get('fresh', 0)}" + (f" · {c['error']}" if c.get("error") else ""))
    if a.dry_run or not token:
        if not token and not a.dry_run:
            print("::warning title=uk-trade-notices-push::MCP_ACCESS_TOKEN 미설정 — 결과를 저장하지 않음")
        return 0
    if doc["status"] == "failed" and previous:
        print("::warning title=uk-trade-notices::모음 조회 실패 — 이전 결과 유지(0건 아님)")
    status = private_store.put("uk-trade-notices", doc, token)
    print(f"::notice title=uk-trade-notices-push::기자 전용 저장소 전송 HTTP {status}")
    return 0 if status == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
