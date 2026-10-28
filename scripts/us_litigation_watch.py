"""미국 소송·ITC 337조 감시: 출입처가 당사자인 미국 연방법원 사건(CourtListener)과 출입처 이름이 나오는 ITC 337조 고시.

- CourtListener v4 검색(RECAP 사건 목록): 회사 영문명으로 최근 사건을 찾고, 당사자(party) 목록에 출입처가 있을 때만 남긴다.
  본문에 이름만 나오는 다른 회사 사건은 버린다.
- 분류: 국제무역법원(CIT)·연방순회항소법원(CAFC) 사건, 특허·계약·반독점·증권·노동 등은 먼저 보여 주고,
  소비자 제조물책임·개인 고용 소송·위조품 단속(Schedule A)은 '일상'으로 접는다.
- 판결(10-28 추가): 국제무역법원·연방순회항소법원 판결 검색(type=o, court=cit cafc, 최근 21일)에서 사건명·판결문 첫머리
  당사자 줄(OPINION 앞)에 출입처가 있을 때만 남긴다(판례로 인용만 한 판결은 버림). 새 판결은 판결문을 한 번 읽어
  국제무역법원은 첫머리 괄호 요지, 연방순회항소법원은 끝의 대문자 주문(AFFIRMED 등)을 원문 그대로 붙이고 낱말 풀이를 단다.
- 새 연방순회항소법원 사건은 사건 상세(원심·사건 유형)를 한 번 읽어 사실만으로 한 줄 설명을 만든다.
- ITC 337조: 미국 관보에서 ITC 고시 중 'Certain …' 337조 사건(제소 접수·조사 개시·판정)을 찾아 본문을 한 번 읽고
  출입처 영문명이 나오면 남긴다(문서번호로 캐시).
- 결과는 기자 전용 저장소(us-litigation)로만. 공개 로그는 건수만. 조회 실패는 0건이 아니다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import trade_remedy_watch as trw  # noqa: E402  (BEAT_NAMES, named_companies, text_lines, get_text)

KST = dt.timezone(dt.timedelta(hours=9))
SCHEMA = "us_litigation/v1"
CL_API = "https://www.courtlistener.com/api/rest/v4/search/"
CL_SITE = "https://www.courtlistener.com"
CL_BASE = "https://www.courtlistener.com/api/rest/v4"
# Rulings: a new filing is a claim, a ruling is the news (운영 10-28: CIT 'POSCO v. United States' 판결 10-27 →
# 경쟁지 [단독] 10-28 오전). Trade court and Federal Circuit opinions naming a beat party are read every run.
OPINION_COURTS = ("cit", "cafc")
OPINION_DAYS = 21
OPINION_SOURCE = "CourtListener 판결(국제무역법원·연방순회항소법원)"
DETAIL_BUDGET = 3   # docket details (원심·사건 유형) of new Federal Circuit cases per run
TEXT_BUDGET = 3     # opinion texts (판결 요지 한 줄) per run
HOLDING = re.compile(r"\[\s*((?:Sustain|Remand|Grant|Den(?:y|ie)|Affirm|Revers|Vacat|Dismiss)[^\]]{0,600})\]", re.I)
# Federal Circuit opinions end with the disposition in capitals ("AFFIRMED", "REVERSED AND REMANDED").
_D = r"(?:AFFIRMED|REVERSED|VACATED|DISMISSED|REMANDED)(?:-IN-PART| IN PART)?"
DISPOSITION = re.compile(rf"^[ \t]*({_D}(?:(?:,[ \t]*|[ \t]+)(?:AND[ \t]+)?{_D})*)[ \t]*\.?[ \t]*$", re.M)
VERB = re.compile(r"(Sustain|Remand|Grant|Den(?:y|ie)|Affirm|Revers|Vacat|Dismiss)\w*(\s*-?\s*in\s*-?\s*part)?", re.I)
VERB_KO = {"sustain": "유지", "remand": "재검토 환송", "grant": "신청 인용", "deny": "신청 기각", "denie": "신청 기각",
           "affirm": "원심 확정", "revers": "원심 파기", "vacat": "취소", "dismiss": "기각·각하"}
# The court's own list is same-day (POSCO 26-131: PDF 10-27 14:57 GMT, 경쟁지 [단독] 10-28 10:50 KST). One GET a run.
CIT_LIST = "https://www.cit.uscourts.gov/content/slip-opinions-{year}"
CIT_SITE = "https://www.cit.uscourts.gov"
CIT_SOURCE = "국제무역법원 누리집 판결 목록"
CIT_ROW = re.compile(r"<tr>\s*<td[^>]*>\s*<a href=\"([^\"]+\.pdf)\">\s*(\d{2}-\d{1,3})\s*</a>\s*</td>\s*<td[^>]*>(.*?)</td>\s*"
                     r"<td[^>]*>\s*(\d{1,2}/\d{1,2}/\d{4})\s*</td>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>", re.S | re.I)
WINDOW_DAYS = 45
KEEP_DAYS = 120
MAX_PAGES = 5
ITC_BODY_BUDGET = 40

# CourtListener allows an authenticated account 5 requests a minute, 50 an hour and 125 a day (v4 overview, 2026-10).
# So the company phrases are OR-ed into a few group queries, calls are spaced, and parties decide which company a case is about.
GROUPS = [
    ("자동차", ["Hyundai Motor", "Genesis Motor America", "Kia America", "Kia Corporation", "Kia Georgia", "Hyundai Mobis",
              "Mobis Alabama", "Hyundai WIA", "HL Mando", "Hankook Tire", "Nexen Tire", "Kumho Tire", "KG Mobility"]),
    ("철강·비철", ["POSCO", "Hyundai Steel", "SeAH Steel", "Dongkuk", "Korea Zinc", "KG Dongbu Steel", "KG Steel"]),
    ("전력·에너지·화학", ["Hyundai Power Transformers", "HD Hyundai Electric", "LS Electric", "LS Cable", "LS GreenLink", "Taihan",
                    "Doosan Enerbility", "Hanwha Q Cells", "Qcells", "Mission Solar", "GS Caltex", "Hyosung HICO", "Iljin Electric"]),
]
# (출입처, 당사자 판정 정규식). 계열사·약어 오인을 막기 위해 당사자 이름으로 확인한다.
PARTIES = [
    ("현대차", r"Hyundai Motor|Genesis Motor"), ("기아", r"\bKia\b"), ("현대모비스", r"Hyundai Mobis|\bMobis\b"),
    ("현대위아", r"Hyundai WIA"), ("HL만도", r"\bMando\b"), ("한국타이어", r"Hankook"), ("넥센타이어", r"Nexen Tire"),
    ("금호타이어", r"Kumho"), ("KG모빌리티", r"KG Mobility|SsangYong"),
    ("포스코", r"\bPOSCO\b(?!\s*(?:International|Future|E&C|DX))"), ("현대제철", r"Hyundai Steel"), ("세아제강", r"SeAH"),
    ("동국제강·동국씨엠", r"Dongkuk"), ("고려아연", r"Korea Zinc"),
    # KG스틸(옛 동부제철): CIT 사건명은 'KG Dongbu Steel Co. v. United States'(Slip Op. 26-130, 10-20) — 10-29까지 빠져 있었다.
    ("KG스틸", r"\bKG (?:Dongbu )?Steel\b|\bKG Dongbu\b|\bDongbu Steel\b"),
    ("HD현대일렉트릭", r"Hyundai Power Transformers|HD Hyundai Electric|Hyundai Electric"), ("LS일렉트릭", r"\bLS Electric"),
    ("LS전선", r"\bLS Cable|LS GreenLink"), ("대한전선", r"Taihan"), ("두산에너빌리티", r"Doosan"), ("한화솔루션", r"Hanwha|Q ?Cells"),
    ("OCI", r"Mission Solar|\bOCI\b"), ("GS칼텍스", r"GS Caltex"), ("효성중공업(관련)", r"Hyosung"), ("일진전기(관련)", r"Iljin"),
]
CALL_GAP = 13.0      # seconds between CourtListener calls (5 a minute)
MAX_CALLS = 24       # per run (daily cap 125, hourly 50)
MAX_RETRY_AFTER = 90


# Nature-of-suit code → (분류, 우선순위). Lower is shown first; 3 = 일상(접힘).
NOS = [
    (r"^83[05]", "특허", 1), (r"^840", "상표", 2), (r"^410", "반독점", 1), (r"^85[0-9]", "증권", 1),
    (r"^89[03]", "환경·기타 법령", 1), (r"^470", "부패·RICO", 1), (r"^19[0-6]|^11[0-9]", "계약", 1),
    (r"^7[0-9]{2}", "노동", 2), (r"^89[0-9]", "기타 법령", 2), (r"^3[0-9]{2}", "제조물책임·상해", 3),
    (r"^44[0-9]", "고용 차별(개인)", 3), (r"^4[0-9]{2}", "기타 민사", 2),
]
CONSUMER_CAUSE = re.compile(r"Magnuson|Warranty|Product Liabil|Personal Inj|Motor Vehicle|Lemon", re.I)


def classify(x):
    court = (x.get("court_id") or "").lower()
    case = x.get("caseName") or ""
    nos = (x.get("suitNature") or "").strip()
    cause = x.get("cause") or ""
    if court == "cit":
        return "국제무역법원(무역구제 소송)", 0
    if court == "cafc":
        return "연방순회항소법원", 0
    if re.search(r"^In re\b|Multidistrict|MDL", case, re.I):
        return "병합·집단 소송", 1
    if re.search(r"Schedule A|Unincorporated Associations", case, re.I):
        return "위조품 단속(상표)", 3
    for rx, name, pri in NOS:
        if re.match(rx, nos):
            return name, pri
    if CONSUMER_CAUSE.search(cause):
        return "소비자·제조물책임", 3
    return "분류 없음", 2


class Budget:
    def __init__(self, n):
        self.left = n
        self.stop = None   # set when a refused token / long throttle should end every later CourtListener call

    def take(self):
        if self.left <= 0:
            return False
        self.left -= 1
        return True


def cl_search(query, since, token, budget, *, get=None, sleep=time.sleep):
    """One group query, following `next` up to MAX_PAGES. Returns (rows, error, complete)."""
    if get is None:
        import requests
        get = requests.get
    headers = {"User-Agent": "seoul-reporting-radar (github.com/shhong9173-art)", "Accept": "application/json",
               "Authorization": f"Token {token}"}
    rows, url, params = [], CL_API, {"q": query, "type": "r", "order_by": "dateFiled desc", "filed_after": since}
    for _ in range(MAX_PAGES):
        retried = False
        while True:
            if not budget.take():
                return rows, "호출 예산 소진", False
            try:
                r = get(url, params=params, headers=headers, timeout=40)
            except Exception as e:
                sleep(CALL_GAP)
                return rows, type(e).__name__, False
            sleep(CALL_GAP)
            if r.status_code == 429 and not retried:
                wait = int(re.sub(r"\D", "", str((getattr(r, "headers", None) or {}).get("Retry-After", ""))) or 0)
                if 0 < wait <= MAX_RETRY_AFTER:
                    sleep(wait)
                    retried = True
                    continue
                return rows, f"HTTP 429 호출 한도(재시도 {wait or '?'}초 뒤)", False
            break
        if r.status_code == 401:
            return rows, "HTTP 401 토큰 거부", False
        if r.status_code == 429:
            return rows, "HTTP 429 호출 한도", False
        if r.status_code != 200:
            return rows, f"HTTP {r.status_code}", False
        try:
            body = r.json()
        except ValueError:
            return rows, "JSON 아님", False
        rows += body.get("results") or []
        url, params = body.get("next"), None
        if not url:
            return rows, None, True
    return rows, None, False  # more pages than MAX_PAGES


def cl_call(url, token, budget, *, params=None, get=None, sleep=time.sleep):
    """One CourtListener API call with the same spacing and 429 handling as the searches. Returns (body, error)."""
    if get is None:
        import requests
        get = requests.get
    headers = {"User-Agent": "seoul-reporting-radar (github.com/shhong9173-art)", "Accept": "application/json",
               "Authorization": f"Token {token}"}
    for attempt in (1, 2):
        if not budget.take():
            return None, "호출 예산 소진"
        try:
            r = get(url, params=params, headers=headers, timeout=40)
        except Exception as e:
            sleep(CALL_GAP)
            return None, type(e).__name__
        sleep(CALL_GAP)
        if r.status_code == 429 and attempt == 1:
            wait = int(re.sub(r"\D", "", str((getattr(r, "headers", None) or {}).get("Retry-After", ""))) or 0)
            if 0 < wait <= MAX_RETRY_AFTER:
                sleep(wait)
                continue
        if r.status_code != 200:
            return None, f"HTTP {r.status_code}" + (" 토큰 거부" if r.status_code == 401 else "")
        try:
            return r.json(), None
        except ValueError:
            return None, "JSON 아님"
    return None, "HTTP 429 호출 한도"


def clean_text(v, n=400):
    return re.sub(r"\s+", " ", re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", str(v or ""))).strip()[:n]


def beat_in(text):
    return sorted({c for c, rx in PARTIES if re.search(rx, text or "", re.I)})


def explain(x):
    """One factual line from docket fields (원심·사건 유형·역할). None when the fields say nothing more than the title."""
    court, src, kind = x.get("courtId"), x.get("appealFrom") or "", x.get("caseType") or ""
    who = "·".join(x.get("beat") or [])
    if court == "cafc":
        if re.search(r"Patent and Trademark", src, re.I):
            board = "특허심판원(PTAB) " if re.search(r"Patent Trial", kind, re.I) else ""
            return f"{who}, 미국 특허청 {board}결정에 불복해 연방순회항소법원에 항소(사건 {x.get('docketNumber')}, {x.get('dateFiled')} 접수)"
        if re.search(r"International Trade Commission", src, re.I):
            return f"{who}, 미국 ITC 결정 관련 연방순회항소법원 항소(사건 {x.get('docketNumber')}, {x.get('dateFiled')} 접수)"
        if re.search(r"Court of International Trade", src, re.I):
            return f"{who}, 국제무역법원 판결 관련 연방순회항소법원 항소(사건 {x.get('docketNumber')}, {x.get('dateFiled')} 접수)"
        if src:
            return f"{who}, 연방순회항소법원 항소(원심: {src[:60]}, {x.get('dateFiled')} 접수)"
        return None
    if court == "cit" and x.get("role") == "원고" and re.search(r"\bv\.?\s+United States", x.get("caseName") or "", re.I):
        return f"{who}, 미국 정부를 상대로 국제무역법원에 소송 제기({x.get('dateFiled')} 접수, 다툰 판정은 소장에서 확인)"
    return None


def gloss(holding):
    """Word-for-word gloss of the ruling verbs that open a clause ('Sustaining in part and remanding in part …' →
    '일부 유지·일부 재검토 환송'). A verb inside the object ('… motion to dismiss') is not read."""
    text, out = holding or "", []
    for m in VERB.finditer(text):
        before = text[:m.start()].rstrip()
        word = re.match(r"[A-Za-z]+", m.group(0)).group(0)
        if before and not re.search(r"(?:\band|[,;])$", before, re.I):
            continue
        if not (word.isupper() or re.search(r"(?:ing|ed)$", word, re.I)):
            continue
        ko = ("일부 " if m.group(2) else "") + VERB_KO[m.group(1).lower()]
        if ko not in out:
            out.append(ko)
    return "·".join(out) or None


def reading(row):
    """What the gloss implies for a beat plaintiff against the government — labelled as a reading, never as the result."""
    ko, h = row.get("holdingKo") or "", row.get("holding") or ""
    if row.get("courtId") != "cit" or row.get("role") != "원고" or not ko:
        return None
    agency = re.search(r"Commerce|Commission|\bITC\b|Customs|agency", h, re.I)
    if ko == "유지" and agency:
        return "원고 쪽 청구가 받아들여지지 않았다는 뜻으로 읽힘(판결문 본문 확인 전)"
    if "재검토 환송" in ko and agency:
        return "원고 주장 일부 이상을 받아들여 기관에 재검토를 돌려보냈다는 뜻으로 읽힘(판결문 본문 확인 전)"
    return None


def opinions(token, now, previous, budget, *, get=None, sleep=time.sleep):
    """Trade court / Federal Circuit opinions of the last OPINION_DAYS naming a beat party (case name or caption)."""
    since = (now - dt.timedelta(days=OPINION_DAYS)).strftime("%Y-%m-%d")
    query = " OR ".join(f'"{p}"' for _, phrases in GROUPS for p in phrases)
    prev = {x["id"]: x for x in (previous or {}).get("opinions", []) if isinstance(x, dict) and x.get("id")}
    if budget.stop:
        return list(prev.values()), {"source": OPINION_SOURCE, "kind": "opinions", "status": "failed", "error": f"앞 질의 중단({budget.stop})"}
    body, err = cl_call(CL_API, token, budget, params={"q": query, "type": "o", "order_by": "dateFiled desc", "filed_after": since,
                                                     "court": " ".join(OPINION_COURTS)}, get=get, sleep=sleep)
    if err:
        return list(prev.values()), {"source": OPINION_SOURCE, "kind": "opinions", "status": "failed", "error": err}
    rows, texts = [], TEXT_BUDGET
    for x in body.get("results") or []:
        if (x.get("court_id") or "").lower() not in OPINION_COURTS:
            continue
        op = (x.get("opinions") or [{}])[0] or {}
        # Parties come from the caption only: a slip opinion that merely cites 'POSCO v. United States' is not POSCO's case.
        caption = re.split(r"\bOPINION\b|\bDated:|\bBefore:", clean_text(op.get("snippet"), 600))[0]
        beat = beat_in(f"{x.get('caseName') or ''} {x.get('caseNameFull') or ''} {caption}")
        if not beat:
            continue
        oid = f"op:{x.get('cluster_id')}"
        old = prev.get(oid, {})
        plaintiff = any(re.match(rf"^\s*(?:{rx})", x.get("caseName") or "", re.I) for c, rx in PARTIES if c in beat)
        slip = re.search(r"Slip Op\.?\s*(\d{2}-\d{1,3})", caption)
        row = {"id": oid, "beat": beat, "court": x.get("court"), "courtId": (x.get("court_id") or "").lower(),
               "caseName": x.get("caseName") or "", "docketNumber": x.get("docketNumber"), "dateFiled": x.get("dateFiled"),
               "slipOp": slip.group(1) if slip else old.get("slipOp"), "role": "원고" if plaintiff else "피고·참가인 등",
               "url": CL_SITE + (x.get("absolute_url") or ""), "pdf": op.get("download_url"),
               "holding": old.get("holding"), "holdingKo": old.get("holdingKo"), "reading": old.get("reading"),
               "firstSeen": old.get("firstSeen") or now.isoformat(timespec="seconds")}
        if not old and texts > 0 and op.get("id") and not budget.stop:
            texts -= 1
            got, terr = cl_call(f"{CL_BASE}/opinions/{op['id']}/", token, budget, params={"fields": "plain_text"}, get=get, sleep=sleep)
            raw = str((got or {}).get("plain_text") or "")
            m = HOLDING.search(clean_text(raw[:8000], 8000)) if row["courtId"] == "cit" else None
            d = DISPOSITION.findall(raw[-6000:]) if row["courtId"] == "cafc" else []
            if m or d:
                row["holding"] = clean_text(m.group(1) if m else d[-1], 300)
                row["holdingKo"] = gloss(row["holding"])
                row["reading"] = reading(row)
            elif terr:
                row["holdingError"] = terr
        rows.append(row)
    keep_from = (now - dt.timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    have = {r["id"] for r in rows}
    rows += [x for x in prev.values() if x["id"] not in have and str(x.get("dateFiled") or "") >= keep_from]
    rows.sort(key=lambda r: str(r.get("dateFiled") or ""), reverse=True)
    return rows, {"source": OPINION_SOURCE, "kind": "opinions", "status": "ok", "returned": len(body.get("results") or []),
                  "own": len(have), "since": since}


def cit_direct(now, previous, *, get=None):
    """Beat-party rulings from the trade court's own slip-opinion list (same day; CourtListener can lag)."""
    if get is None:
        import requests
        get = requests.get
    since = (now - dt.timedelta(days=OPINION_DAYS)).date()
    prev = {x.get("slipOp"): x for x in (previous or {}).get("opinions", []) if isinstance(x, dict) and x.get("slipOp")}
    years = [now.year - 1, now.year] if now.month == 1 else [now.year]
    rows = []
    for y in years:
        try:
            r = get(CIT_LIST.format(year=y), headers={"User-Agent": "Mozilla/5.0 seoul-reporting-radar"}, timeout=40)
        except Exception as e:  # noqa: BLE001
            return rows, {"source": CIT_SOURCE, "kind": "opinions-direct", "status": "failed", "error": type(e).__name__}
        if r.status_code != 200:
            return rows, {"source": CIT_SOURCE, "kind": "opinions-direct", "status": "failed", "error": f"HTTP {r.status_code}"}
        for pdf, slip, caption, date, court_no, judge in CIT_ROW.findall(r.text):
            caption = clean_text(re.sub(r"<[^>]+>", " ", caption), 300)
            try:
                filed = dt.datetime.strptime(date, "%m/%d/%Y").date()
            except ValueError:
                continue
            if filed < since:
                continue
            beat = beat_in(caption)
            if not beat:
                continue
            old = prev.get(slip, {})
            plaintiff = any(re.match(rf"^\s*(?:{rx})", caption, re.I) for c, rx in PARTIES if c in beat)
            rows.append({"id": f"cit:{slip}", "beat": beat, "court": "Court of International Trade", "courtId": "cit", "caseName": caption,
                         "docketNumber": clean_text(re.sub(r"<[^>]+>", " ", court_no), 40), "dateFiled": filed.isoformat(), "slipOp": slip,
                         "judge": clean_text(re.sub(r"<[^>]+>", " ", judge), 40), "role": "원고" if plaintiff else "피고·참가인 등",
                         "url": CIT_SITE + pdf if pdf.startswith("/") else pdf, "pdf": CIT_SITE + pdf if pdf.startswith("/") else pdf,
                         "holding": old.get("holding"), "holdingKo": old.get("holdingKo"), "reading": old.get("reading"),
                         "firstSeen": old.get("firstSeen") or now.isoformat(timespec="seconds"), "via": "cit"})
    return rows, {"source": CIT_SOURCE, "kind": "opinions-direct", "status": "ok", "own": len(rows)}


def merge_opinions(cl_rows, cit_rows):
    """One row per slip opinion: the CourtListener row (holding text) wins, but keeps the earliest firstSeen."""
    by_slip = {r["slipOp"]: r for r in cit_rows if r.get("slipOp")}
    out = []
    for r in cl_rows:
        c = by_slip.pop(r.get("slipOp"), None) if r.get("slipOp") else None
        if c:
            r = {**r, "firstSeen": min(str(r.get("firstSeen") or "9"), str(c.get("firstSeen") or "9")), "citPdf": c.get("pdf"), "judge": c.get("judge")}
        out.append(r)
    out += list(by_slip.values())
    # a CIT-list row seen earlier and now matched by CourtListener under another id must not appear twice
    seen, uniq = set(), []
    for r in sorted(out, key=lambda r: (str(r.get("dateFiled") or ""), r["id"].startswith("op:")), reverse=True):
        k = r.get("slipOp") or r["id"]
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)
    return uniq


def window_start(now, previous):
    """45 days on a first or failed run; afterwards a week before the last complete run (fewer pages, same coverage)."""
    floor = now - dt.timedelta(days=WINDOW_DAYS)
    try:
        last = dt.datetime.fromisoformat(str((previous or {}).get("coveredThrough") or ""))
    except ValueError:
        last = None
    if last and last.tzinfo:
        return max(floor, last - dt.timedelta(days=7)).strftime("%Y-%m-%d")
    return floor.strftime("%Y-%m-%d")


def litigation(token, now, previous, *, get=None, sleep=time.sleep, budget=None):
    since = window_start(now, previous)
    prev = {x["id"]: x for x in (previous or {}).get("cases", []) if isinstance(x, dict) and x.get("id")}
    found, checks = {}, []
    budget = budget or Budget(MAX_CALLS)
    for group, phrases in GROUPS:
        query = " OR ".join(f'"{p}"' for p in phrases)
        rows, err, complete = cl_search(query, since, token, budget, get=get, sleep=sleep)
        own = 0
        for x in rows:
            parties = [p for p in (x.get("party") or []) if isinstance(p, str)]
            hits = [(company, [p for p in parties if re.search(rx, p, re.I)]) for company, rx in PARTIES]
            hits = [(c, m) for c, m in hits if m]
            if not hits:
                continue  # the company is only mentioned in a filing of someone else's case
            did = f"cl:{x.get('docket_id')}"
            own += 1
            beat = sorted({c for c, _ in hits})
            matched = sorted({p for _, m in hits for p in m})[:6]
            if did in found:
                found[did]["beat"] = sorted(set(found[did]["beat"]) | set(beat))
                continue
            category, pri = classify(x)
            case = x.get("caseName") or ""
            plaintiff = any(re.match(rf"^\s*(?:{rx})", case, re.I) for c, rx in PARTIES if c in beat)
            # 'In re: LS Electric Co., Ltd.' at the Federal Circuit is the company's own appeal (e.g. from the patent board).
            in_re = any(re.match(rf"^\s*In re:?\s*(?:{rx})", case, re.I) for c, rx in PARTIES if c in beat)
            found[did] = {
                "id": did, "beat": beat, "group": group, "caseName": case, "court": x.get("court"), "courtId": x.get("court_id"),
                "docketNumber": x.get("docketNumber"), "dateFiled": x.get("dateFiled"), "dateTerminated": x.get("dateTerminated"),
                "suitNature": x.get("suitNature") or "", "cause": x.get("cause") or "", "category": category, "priority": pri,
                "role": "원고" if plaintiff else "신청·항소인(In re)" if in_re else "피고·기타 당사자", "matchedParties": matched, "partyCount": len(parties),
                "url": CL_SITE + (x.get("docket_absolute_url") or ""),
                "firstSeen": prev.get(did, {}).get("firstSeen") or now.isoformat(timespec="seconds"),
            }
        status = "failed" if err and not rows else ("partial" if err or not complete else "ok")
        checks.append({"source": f"CourtListener {group}", "status": status, "returned": len(rows), "own": own, "since": since,
                       **({"error": err} if err else {}), **({} if complete or err else {"error": f"{MAX_PAGES}쪽 초과 — 이후 미조회"})})
        if err and ("401" in err or "429" in err or "예산" in err):
            for g2, _ in GROUPS[GROUPS.index((group, phrases)) + 1:]:
                checks.append({"source": f"CourtListener {g2}", "status": "failed", "error": f"앞 질의 중단({err})", "returned": 0})
            budget.stop = err
            break
    return found, checks


def enrich(cases, prev_cases, token, budget, *, get=None, sleep=time.sleep):
    """Origin and case type of Federal Circuit dockets (one call each, DETAIL_BUDGET per run), and the one-line summary
    for every kept case — including ones carried over from earlier runs (운영 10-28: 기존 사건은 설명 없이 남았다)."""
    details = DETAIL_BUDGET
    for x in cases:
        old = prev_cases.get(x["id"]) or {}
        for k in ("appealFrom", "caseType", "detailTried"):
            if old.get(k) and not x.get(k):
                x[k] = old[k]
        if x.get("courtId") == "cafc" and not x.get("detailTried") and details > 0 and not budget.stop:
            details -= 1
            got, err = cl_call(f"{CL_BASE}/dockets/{x['id'].split(':', 1)[1]}/", token, budget,
                               params={"fields": "appeal_from_str,appellate_case_type_information,nature_of_suit"}, get=get, sleep=sleep)
            if got:
                x["appealFrom"] = clean_text(got.get("appeal_from_str"), 120) or None
                x["caseType"] = clean_text(got.get("appellate_case_type_information"), 120) or None
            if got or (err or "").startswith("HTTP 404"):
                x["detailTried"] = True  # timeouts and throttling are tried again next run
        x["summary"] = explain(x)


def is_337(title):
    return trw.is_337(title)


def itc_337(now, previous, *, get=None, sleep=time.sleep):
    """ITC notices of the last WINDOW_DAYS that are Section 337 matters, kept when the body names a beat company."""
    since = (now - dt.timedelta(days=WINDOW_DAYS)).strftime("%Y-%m-%d")
    params = [("conditions[agencies][]", "international-trade-commission"), ("conditions[publication_date][gte]", since),
              ("order", "newest"), ("per_page", "200")]
    for f in ("title", "publication_date", "html_url", "document_number", "raw_text_url", "type"):
        params.append(("fields[]", f))
    if get is None:
        import requests
        get = requests.get
    try:
        r = get(trw.FR_API, params=params, headers={"User-Agent": trw.UA, "Accept": "application/json"}, timeout=40)
        if r.status_code != 200:
            return [], f"HTTP {r.status_code}", 0
        data = r.json()
    except Exception as e:
        return [], type(e).__name__, 0
    prev = {x["id"]: x for x in (previous or {}).get("itc", []) if isinstance(x, dict) and x.get("id")}
    seen = set((previous or {}).get("itcChecked") or [])
    rows, budget, checked = [], ITC_BODY_BUDGET, []
    for x in data.get("results") or []:
        title = x.get("title") or ""
        if not is_337(title):
            continue
        did = f"fr:{x.get('document_number')}"
        checked.append(did)
        if did in prev:
            rows.append(prev[did])
            continue
        if did in seen or budget <= 0 or not x.get("raw_text_url"):
            continue
        budget -= 1
        body, err = trw.get_text(x["raw_text_url"], get=get, headers={"User-Agent": trw.UA, "Accept": "text/plain,text/html"})
        sleep(0.5)
        if body is None:
            checked.pop()  # retry next time
            continue
        named = trw.named_companies(trw.text_lines(body))
        if named:
            rows.append({"id": did, "date": x.get("publication_date"), "title": title, "url": x.get("html_url"),
                         "stage": "제소 접수" if re.search(r"Receipt of Complaint", title, re.I) else
                                  ("조사 개시" if re.search(r"Institution", title, re.I) else
                                   ("최종 판정" if re.search(r"Final", title, re.I) else
                                    ("예비 판정" if re.search(r"Initial Determination", title, re.I) else "절차 고시"))),
                         "named": named, "firstSeen": now.isoformat(timespec="seconds")})
    return rows, None, sorted(set(checked) | seen)[-600:]


def run(token, *, now, previous=None, get=None, sleep=time.sleep):
    stamp = now.isoformat(timespec="seconds")
    had_state = bool(previous)
    budget = Budget(MAX_CALLS)
    found, checks = litigation(token, now, previous, get=get, sleep=sleep, budget=budget)
    rulings, ocheck = opinions(token, now, previous, budget, get=get, sleep=sleep)
    checks.append(ocheck)
    cit_rows, ccheck = cit_direct(now, previous, get=get)
    checks.append(ccheck)
    rulings = merge_opinions(rulings, cit_rows)
    prev_ops = {x["id"] for x in (previous or {}).get("opinions", []) if isinstance(x, dict)}
    prev_slips = {x.get("slipOp") for x in (previous or {}).get("opinions", []) if isinstance(x, dict) and x.get("slipOp")}
    for x in rulings:
        x["isNew"] = bool((previous or {}).get("opinions") is not None and had_state and x["id"] not in prev_ops
                          and not (x.get("slipOp") and x["slipOp"] in prev_slips))
    itc, ierr, checked = itc_337(now, previous, get=get, sleep=sleep)
    checks.append({"source": "미국 관보 ITC 337조", "status": "failed" if ierr else "ok", "returned": len(itc), **({"error": ierr} if ierr else {})})
    keep_from = (now - dt.timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    prev_cases = {x["id"]: x for x in (previous or {}).get("cases", []) if isinstance(x, dict) and x.get("id")}
    # cases outside this run's window (or from failed queries) stay until KEEP_DAYS
    for did, x in prev_cases.items():
        if did not in found and str(x.get("dateFiled") or "") >= keep_from:
            found[did] = x
    cases = sorted(found.values(), key=lambda x: (x["priority"], -int(re.sub(r"\D", "", x.get("dateFiled") or "0") or 0)))
    for x in cases:
        x["isNew"] = had_state and x["id"] not in prev_cases
    enrich(cases, prev_cases, token, budget, get=get, sleep=sleep)
    prev_itc = {x["id"] for x in (previous or {}).get("itc", []) if isinstance(x, dict)}
    if ierr:
        itc = list((previous or {}).get("itc") or [])
    for x in itc:
        x["isNew"] = had_state and x["id"] not in prev_itc
    failed = [c for c in checks if c["status"] != "ok"]
    cl_ok = all(c["status"] == "ok" for c in checks if c["source"].startswith("CourtListener") and c.get("kind") != "opinions")
    covered = stamp if cl_ok else (previous or {}).get("coveredThrough")
    return {"schema": SCHEMA, "generatedAt": stamp, "windowDays": WINDOW_DAYS, "status": "partial" if failed else "complete",
            "coveredThrough": covered, "checks": checks, "cases": cases, "opinions": rulings, "itc": itc, "itcChecked": checked,
            "rules": ["당사자 목록에 출입처(미국 법인 포함)가 있는 사건만. 서류에 이름만 나온 남의 사건은 제외.",
                      "소장 접수는 주장일 뿐 사실 확정이 아니다. 청구 내용·금액은 소장 원문(PACER)으로 확인하고 회사 입장을 듣는다.",
                      "CourtListener에 아직 안 올라온 사건이 있을 수 있다. 0건은 소송 없음이 아니다.",
                      "ITC 337조 고시의 회사명은 제소인·피제소인·제3자일 수 있다. 원문에서 역할을 확인한다.",
                      "판결 요지는 판결문 첫머리 괄호 줄(원문)이다. '결정 유지'·'환송' 같은 풀이는 그 낱말의 뜻일 뿐, 승패와 세율은 판결문 본문에서 확인한다.",
                      "조회 실패는 0건이 아니라 미확인."],
            "confirmedScoops": 0}


def main():
    argparse.ArgumentParser(description="미국 소송·ITC 337조 감시(기자 전용 저장소로)").parse_args()
    now = dt.datetime.now(KST)
    cl_token = os.environ.get("COURTLISTENER_TOKEN", "").strip()
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    if not cl_token:
        sys.exit("COURTLISTENER_TOKEN 미설정 — 실행하지 않음(0건 아님)")
    import private_store
    previous = None
    if token:
        try:
            previous = private_store.get("us-litigation", token)
        except private_store.StoreError as e:
            print(f"::warning title=us-litigation-state::이전 상태 조회 실패({e}) — 신규 표시는 이번 실행 기준")
    if private_store.late_scheduled_duplicate(previous, now):
        return
    doc = run(cl_token, now=now, previous=previous)
    ok = sum(1 for c in doc["checks"] if c["status"] == "ok")
    shown = sum(1 for x in doc["cases"] if x["priority"] < 3)
    errors = sorted({c.get("error") for c in doc["checks"] if c.get("error")})
    print(f"::notice title=us-litigation::질의 정상 {ok}/{len(doc['checks'])} · 출입처 당사자 사건 {len(doc['cases'])}건(우선 {shown}, "
          f"신규 {sum(1 for x in doc['cases'] if x['isNew'])}, 한 줄 설명 {sum(1 for x in doc['cases'] if x.get('summary'))}) · "
          f"판결 {len(doc['opinions'])}건(신규 {sum(1 for x in doc['opinions'] if x['isNew'])}, 요지 {sum(1 for x in doc['opinions'] if x.get('holding'))}) · "
          f"ITC 337조 출입처 이름 {len(doc['itc'])}건"
          f"{' · 오류 ' + ', '.join(errors) if errors else ''}")
    if not token:
        print("::warning title=us-litigation-push::MCP_ACCESS_TOKEN 미설정 — 결과를 저장하지 않음")
        return
    if ok == 0:
        sys.exit("모든 질의 실패 — 이전 결과 유지(0건 아님)")
    status = private_store.put("us-litigation", doc, token)
    print(f"::notice title=us-litigation-push::기자 전용 저장소 전송 HTTP {status}")
    if status == 404:
        print(f"::warning title=us-litigation-token::토큰 거부 또는 배포 전 — {private_store.token_shape(private_store.normalize_token(token))}")
    if status != 200:
        sys.exit(1)


if __name__ == "__main__":
    main()
