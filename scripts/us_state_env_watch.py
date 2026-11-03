"""미국 주 환경청 허가·공고 — 출입처 미국 공장의 대기 허가 신청·제재 공고(기자 전용 저장소 us-state-env).

- 조지아 EPD 주간 공고(Public Advisory·Public Notice PDF, epd.georgia.gov/document/document/paMMYY-N/download): 대기 허가 신청·허가안
  (시설 이름·신청 번호·주소·공고 종류·작업 설명·신청 이유·의견 마감). 11-03 탐침 126: 2026년 PDF 40개 중 현대차 메타플랜트(01월 허가안),
  한화큐셀 조지아(10월 신청 — 회전 농축기·축열식 산화기 추가, 의견 11-06까지)가 나왔다.
- 앨라배마 ADEM 공고 목록(adem.alabama.gov/public-notices): 공고 제목이 시설·회사 이름이다(허가·동의명령(제재)). 11-03 탐침 125.
- 루이지애나 LDEQ 공고(deq.louisiana.gov/public-notices): 의견 링크의 AIName(시설 이름)·Subject(공고 종류)·AI 번호. 현대제철 루이지애나
  제철소·롯데케미칼 레이크찰스가 대상. 11-03 탐침 124.
- 출입처 이름 규칙은 미국 OSHA 감시(us_osha_watch.RULES)와 같다 — 현대트랜시스 같은 계열사는 출입처가 아니다.
- 첫 실행은 기준선(이벤트 없음, 목록에는 남김). 공고는 공개 문서라 그 자체로 단독이 아니다 — 허가 신청은 증설·신설 신호일 수 있어 회사 확인.
- 결과는 기자 전용 저장소로만. 공개 로그는 건수만. 조회 실패는 0건이 아니라 미확인.
"""
from __future__ import annotations

import datetime as dt
import html
import io
import os
import re
import sys
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from us_osha_watch import RULES  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
SCHEMA = "us_state_env/v1"
UA = {"User-Agent": "seoul-reporting-radar (newsroom research; state environmental notices)"}
GA_PDF = "https://epd.georgia.gov/document/document/{code}/download"
ADEM_LIST = "https://adem.alabama.gov/public-notices"
ADEM_SITE = "https://adem.alabama.gov"
LDEQ_LIST = "https://deq.louisiana.gov/public-notices"
PAUSE = 2.0
WEEKS = 5            # 조지아 주간 공고는 달마다 -1 ~ -5
KEEP_DAYS = 180
BEAT = [(ko, re.compile(rx, re.I)) for ko, rx in RULES]
# 신청 이유에 신설·증설 낱말이 있으면 A(공장·라인 신설·생산 능력 확대 신호), 나머지 허가 공고는 B, 제재(동의명령)는 B
A_WORDS = re.compile(r"\bconstruct\w*|\bexpan\w*|\bnew (?:facility|plant|line|building|production)|"
                     r"\bincreas\w* (?:in )?(?:capacity|production|throughput)|\bcapacity (?:increase|expansion)|\bgreenfield", re.I)
ENFORCE = re.compile(r"consent order|administrative order|penalt|violation", re.I)
MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"


def beat_of(name):
    for ko, rx in BEAT:
        if rx.search(name or ""):
            return ko
    return None


def tidy(s):
    return re.sub(r"\s+", " ", html.unescape(str(s or ""))).strip()


def us_date(s):
    m = re.search(rf"({MONTHS})\s+(\d{{1,2}}),\s*(\d{{4}})", s or "")
    if not m:
        return None
    return dt.date(int(m.group(3)), MONTHS.split("|").index(m.group(1)) + 1, int(m.group(2))).isoformat()


# ---------- 조지아 EPD 주간 공고 PDF ----------

FIELDS = ("Facility Name", "Application No", "Facility Address", "EPD Notice Type", "Description of Operation", "Reason for Application")
FIELD_RX = re.compile(r"(Facility Name|Application No|Facility Address|EPD Notice Type|Description of Operation|Reason for Application)\s*:")
COUNTY_RX = re.compile(r"\b([A-Z][A-Z.' ]{2,40}) COUNTY\b")
HEAD_WORDS = {"SIP", "PUBLIC", "ADVISORIES", "ADVISORY", "MAJOR", "SOURCE", "PERMITS", "PERMIT", "NOTICE", "OF", "DRAFT", "TITLE", "V",
              "OPERATING", "SYNTHETIC", "MINOR", "AND", "AMENDMENTS", "OTHER"}
DEADLINE_RX = re.compile(rf"(?:received|submitted|requested)[^.]{{0,80}}?\bby\s+((?:{MONTHS})\s+\d{{1,2}},\s*\d{{4}})")


def ga_codes(now):
    """이번 달·지난달 주간 공고 번호(pa1026-1 … pa1026-5)."""
    first = now.date().replace(day=1)
    prev = (first - dt.timedelta(days=1)).replace(day=1)
    return [f"pa{d.month:02d}{d.year % 100:02d}-{n}" for d in (prev, first) for n in range(1, WEEKS + 1)]


def ga_entries(text, code):
    """PDF 글자 → 시설 항목들. 항목 끝은 다음 'Facility Name:' 또는 다음 군(COUNTY) 머리."""
    text = re.sub(r"\s+", " ", text or "")
    week = us_date((re.search(rf"Week of\s+((?:{MONTHS})\s+\d{{1,2}},\s*\d{{4}})", text) or [None, ""])[1])
    starts = [m.start() for m in re.finditer(r"Facility Name\s*:", text)]
    deadlines = [(m.start(), us_date(m.group(1))) for m in DEADLINE_RX.finditer(text)]
    out = []
    for i, st in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(text)
        chunk = text[st:end]
        # 다음 군 머리(대문자 'XXX COUNTY')·절 머리가 끼면 그 앞에서 자른다
        cut = re.search(r"\s(?:[A-Z][A-Z.' ]{2,30} COUNTY|SIP PUBLIC ADVISORIES|MAJOR SOURCE|NOTICE OF DRAFT|TITLE V)\b", chunk[20:])
        if cut:
            chunk = chunk[:20 + cut.start()]
        parts = FIELD_RX.split(chunk)
        f = {}
        for k in range(1, len(parts) - 1, 2):
            f[parts[k]] = tidy(parts[k + 1])
        if not f.get("Facility Name"):
            continue
        county = None
        for m in COUNTY_RX.finditer(text[max(0, st - 300):st]):
            words = m.group(1).split()
            while words and words[0] in HEAD_WORDS:   # 'SIP PUBLIC ADVISORIES BARTOW' → 'BARTOW'
                words.pop(0)
            county = " ".join(words[-2:]).title() or None
        before = [d for p, d in deadlines if p < st and st - p < 4000]
        after = [d for p, d in deadlines if p >= st and p - st < 1500]
        out.append({"code": code, "week": week, "facility": f.get("Facility Name"), "appNo": f.get("Application No"),
                    "address": f.get("Facility Address"), "noticeType": f.get("EPD Notice Type"),
                    "operation": f.get("Description of Operation"),
                    "reason": re.split(r"\s(?:Any comments|Comments (?:on|should|must))", f.get("Reason for Application") or "")[0][:600],
                    "county": county, "deadline": (before[-1] if before else after[0] if after else None)})
    return out


def pdf_text(content):
    from pypdf import PdfReader
    return " ".join((pg.extract_text() or "") for pg in PdfReader(io.BytesIO(content)).pages)


def georgia(now, seen, get, sleep):
    """새 주간 공고 PDF만 받는다(본 번호는 다시 받지 않음). (출입처 항목, 본 번호, 점검)"""
    rows, got, failed, tried = [], [], [], 0
    for code in ga_codes(now):
        if code in seen:
            continue
        tried += 1
        try:
            r = get(GA_PDF.format(code=code), headers=UA, timeout=40)
        except Exception as e:  # noqa: BLE001
            failed.append(f"{code}:{type(e).__name__}")
            sleep(PAUSE)
            continue
        ctype = (r.headers.get("content-type") or "") if hasattr(r, "headers") else ""
        if r.status_code == 404 or (r.status_code == 200 and "pdf" not in ctype.lower()):
            sleep(PAUSE / 2)
            continue  # 아직 안 올라온 주(다음 실행에 다시)
        if r.status_code != 200:
            failed.append(f"{code}:HTTP {r.status_code}")
            sleep(PAUSE)
            continue
        try:
            entries = ga_entries(pdf_text(r.content), code)
        except Exception as e:  # noqa: BLE001
            failed.append(f"{code}:PDF {type(e).__name__}")
            sleep(PAUSE)
            continue
        got.append(code)
        for x in entries:
            company = beat_of(x["facility"])
            if company:
                rows.append({**x, "company": company, "source": "ga", "state": "조지아",
                             "id": f"ga:{x['appNo'] or x['facility']}:{code}", "url": GA_PDF.format(code=code)})
        sleep(PAUSE)
    status = "failed" if failed and not got else "partial" if failed else "ok"
    return rows, got, {"source": "조지아 EPD 주간 공고", "status": status, "returned": len(got), "tried": tried,
                       **({"error": "; ".join(failed[:4])} if failed else {})}


# ---------- 앨라배마 ADEM 공고 목록 ----------

ADEM_ITEM = re.compile(r'<a[^>]+href="((?:https?://(?:www\.)?adem\.alabama\.gov)?/sites/default/files/[^"]+\.(?:html|pdf))"[^>]*>(.*?)</a>', re.S | re.I)


def adem(get, sleep):
    try:
        r = get(ADEM_LIST, headers=UA, timeout=40)
    except Exception as e:  # noqa: BLE001
        return [], {"source": "앨라배마 ADEM 공고", "status": "failed", "returned": 0, "error": type(e).__name__}
    if r.status_code != 200:
        return [], {"source": "앨라배마 ADEM 공고", "status": "failed", "returned": 0, "error": f"HTTP {r.status_code}"}
    items, rows = ADEM_ITEM.findall(r.text), []
    for href, label in items:
        name = tidy(re.sub(r"<[^>]+>", " ", label))
        company = beat_of(name)
        if not company:
            continue
        url = href if href.startswith("http") else ADEM_SITE + href
        detail = ""
        if url.endswith(".html"):
            sleep(PAUSE)
            try:
                d = get(url, headers=UA, timeout=40)
                if d.status_code == 200:
                    body = re.sub(r"<script.*?</script>|<style.*?</style>", " ", d.text, flags=re.S)
                    detail = tidy(re.sub(r"<[^>]+>", " ", body))[:900]
            except Exception:  # noqa: BLE001
                detail = ""
        month = re.search(r"/files/(\d{4}-\d{2})/", url)
        rows.append({"id": f"adem:{url.rsplit('/', 1)[-1]}", "source": "adem", "state": "앨라배마", "company": company, "facility": name,
                     "noticeType": "동의명령(제재)" if ENFORCE.search(detail) else "공고", "operation": "", "reason": detail[:600],
                     "posted": month.group(1) if month else None, "url": url})
    return rows, {"source": "앨라배마 ADEM 공고", "status": "ok" if items else "partial", "returned": len(items),
                  **({} if items else {"error": "목록 0줄 — 형식 바뀜일 수 있음"})}


# ---------- 루이지애나 LDEQ 공고 ----------

LDEQ_ITEM = re.compile(r"AIName=([^&\"]+)&(?:amp;)?Subject=([^&\"]+)&(?:amp;)?AI=(\d+)")


def ldeq(get):
    try:
        r = get(LDEQ_LIST, headers=UA, timeout=40)
    except Exception as e:  # noqa: BLE001
        return [], {"source": "루이지애나 LDEQ 공고", "status": "failed", "returned": 0, "error": type(e).__name__}
    if r.status_code != 200:
        return [], {"source": "루이지애나 LDEQ 공고", "status": "failed", "returned": 0, "error": f"HTTP {r.status_code}"}
    items, rows, seen = LDEQ_ITEM.findall(r.text), [], set()
    for name, subject, ai in items:
        name, subject = tidy(urllib.parse.unquote(name)), tidy(urllib.parse.unquote(subject))
        company = beat_of(name)
        key = f"{ai}:{subject}"
        if not company or key in seen:
            continue
        seen.add(key)
        rows.append({"id": f"ldeq:{key}", "source": "ldeq", "state": "루이지애나", "company": company, "facility": name,
                     "noticeType": subject, "operation": "", "reason": "", "ai": ai, "url": LDEQ_LIST})
    return rows, {"source": "루이지애나 LDEQ 공고", "status": "ok" if items else "partial", "returned": len(items),
                  **({} if items else {"error": "공고 0줄 — 형식 바뀜일 수 있음"})}


# ---------- 합치기 ----------

def tier_of(x):
    if x["source"] == "adem" and x.get("noticeType") == "동의명령(제재)":
        return "B"
    return "A" if A_WORDS.search(f"{x.get('reason') or ''} {x.get('noticeType') or ''}") else "B"


def line(x):
    where = " · ".join(v for v in (x.get("county") and f"{x['county']} County", x.get("address")) if v)
    return (f"{x['state']} {('주간 공고 ' + x['code']) if x['source'] == 'ga' else '공고'} · {x['facility']}"
            + (f"({where})" if where else "") + f" · {x.get('noticeType') or '공고'}"
            + (f" · 신청 {x['appNo']}" if x.get("appNo") else "")
            + (f" · 작업 '{x['operation']}'" if x.get("operation") else "")
            + (f" · 이유 「{x['reason'][:260]}」" if x.get("reason") else "")
            + (f" · 의견 마감 {x['deadline']}" if x.get("deadline") else ""))


def run(now, previous=None, *, get=None, sleep=time.sleep):
    if get is None:
        import requests
        get = requests.get
    prev = previous or {}
    stamp = now.isoformat(timespec="seconds")
    seen = prev.get("seen") or {}
    first = {k: k not in seen for k in ("ga", "adem", "ldeq")}
    ga_rows, ga_got, ga_check = georgia(now, set(seen.get("ga") or []), get, sleep)
    sleep(PAUSE)
    ad_rows, ad_check = adem(get, sleep)
    sleep(PAUSE)
    ld_rows, ld_check = ldeq(get)
    known = {x["id"]: x for x in prev.get("notices") or [] if isinstance(x, dict) and x.get("id")}
    events = [e for e in prev.get("events") or [] if isinstance(e, dict)]
    have = {e["id"] for e in events}
    for src, rows, ok in (("ga", ga_rows, ga_check["status"] != "failed"), ("adem", ad_rows, ad_check["status"] == "ok"),
                          ("ldeq", ld_rows, ld_check["status"] == "ok")):
        for x in rows:
            if x["id"] in known:
                known[x["id"]]["lastSeen"] = stamp
                continue
            base = first[src]
            known[x["id"]] = {**x, "firstSeen": stamp, "lastSeen": stamp, **({"baseline": True} if base else {})}
            if not base and ok and x["id"] not in have:
                tier = tier_of(x)
                events.append({"id": x["id"], "kind": "주 환경청 제재 공고" if x.get("noticeType") == "동의명령(제재)" else "주 환경청 허가·공고",
                               "tier": tier, "company": x["company"], "state": x["state"], "detectedAt": stamp, "url": x["url"],
                               "text": line(x) + (" — 신설·증설 낱말이 있는 신청(회사 확인)" if tier == "A" else "")
                               + " · 주 정부 공개 공고(허가 신청≠착공·투자 확정)"})
                have.add(x["id"])
    # 목록 원천은 처음 정상으로 읽은 실행이 기준선 — 실패한 실행으로 기준선을 잡으면 다음 실행에 기존 공고가 모두 새것으로 뜬다
    new_seen = {"ga": sorted(set(seen.get("ga") or []) | set(ga_got))[-60:]}
    for k, c in (("adem", ad_check), ("ldeq", ld_check)):
        if seen.get(k) or c["status"] == "ok":
            new_seen[k] = True
    if not ga_got and not seen.get("ga") and ga_check["status"] == "failed":
        new_seen.pop("ga", None)
    keep_from = (now - dt.timedelta(days=KEEP_DAYS)).isoformat()
    notices = sorted((x for x in known.values() if str(x.get("lastSeen") or x.get("firstSeen")) >= keep_from),
                     key=lambda x: str(x.get("firstSeen")), reverse=True)[:300]
    events = sorted((e for e in events if str(e.get("detectedAt")) >= keep_from), key=lambda e: e["detectedAt"], reverse=True)[:200]
    checks = [ga_check, ad_check, ld_check]
    status = "failed" if all(c["status"] == "failed" for c in checks) else "partial" if any(c["status"] != "ok" for c in checks) else "complete"
    return {"schema": SCHEMA, "generatedAt": stamp, "status": status, "checks": checks, "seen": new_seen,
            "notices": notices, "events": events,
            "rules": ["주 환경청 공개 공고(조지아 EPD 주간 공고 PDF·앨라배마 ADEM 공고·루이지애나 LDEQ 공고)에서 출입처 미국 공장 이름이 나온 것만(이름 규칙은 미국 OSHA 감시와 같다).",
                      "허가 신청·허가안은 착공·투자 확정이 아니다. 신청 이유에 신설·증설 낱말이 있으면 A, 나머지 허가 공고·제재 공고는 B. 규모·일정은 공고 원문과 회사로 확인.",
                      "첫 실행은 기준선(목록에만 남김). 조회 실패는 0건이 아니라 미확인. 계열사(현대트랜시스 등)는 출입처가 아니다."]}


def main():
    import private_store
    now = dt.datetime.now(KST)
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    previous = None
    if token:
        try:
            previous = private_store.get("us-state-env", token)
        except private_store.StoreError as e:
            print(f"::warning title=us-state-env-state::이전 상태 조회 실패({e}) — 이번 실행은 기준선")
    doc = run(now, previous)
    new = [e for e in doc["events"] if e["detectedAt"] == doc["generatedAt"]]
    print(f"::notice title=us-state-env::상태 {doc['status']} · 출입처 공고 {len(doc['notices'])}건 · 이번 새 이벤트 {len(new)} · "
          + " / ".join(f"{c['source']} {c['status']}({c.get('returned', 0)})" for c in doc["checks"]))
    if not token:
        print("::warning title=us-state-env-push::MCP_ACCESS_TOKEN 미설정 — 결과를 저장하지 않음")
        return
    if doc["status"] == "failed":
        sys.exit("주 환경청 공고 조회 전체 실패 — 이전 결과 유지(0 아님)")
    status = private_store.put("us-state-env", doc, token)
    print(f"::notice title=us-state-env-push::기자 전용 저장소 전송 HTTP {status}")
    if status != 200:
        sys.exit(1)


if __name__ == "__main__":
    main()
