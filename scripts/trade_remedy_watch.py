"""무역구제 감시: EU 철강 쿼터(TARIC) 한국 몫 소진, 미국 관보의 한국산 무역구제·ITC 고시, 호주·캐나다·인도 공고 목록,
국내 무역위원회(진행 사건·진행일정·회의 안건·보도자료, scripts/ktc_watch.py), 무역협회 대한 수입규제DB(세계 각국, scripts/kita_watch.py).

- EU TARIC: 이번 분기 한국 관련 관세쿼터(09xxxx) 초기 물량·잔량·소진일·CN 코드. 사용률 80% 이상·소진을 표시하고
  직전 확인 대비 사용률 변화를 남긴다.
- 미국 관보(Federal Register API): 상무부(ITA)·ITC 고시 중 'Republic of Korea'가 들어간 것. 조사 개시·예비·최종 판정을 구분한다.
- 호주·캐나다·인도: 공고 목록 페이지에서 'Korea'가 들어간 줄이 새로 생기면 변경으로 남긴다.
- 무역위원회: 새 조사·진행일정 새 줄·진행 목록에서 빠짐·회의 안건(회의 약 1주 전 개요 PDF)·보도자료. 첫 실행은 기준선.
- 결과는 기자 전용 저장소(trade-remedy)로만. 공개 로그는 건수만. 조회 실패는 0건이 아니다.
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
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

KST = dt.timezone(dt.timedelta(hours=9))
SCHEMA = "trade_remedy/v1"
CONFIG = ROOT / "data" / "trade_remedy_pages.json"
TARIC = "https://ec.europa.eu/taxation_customs/dds2/taric"
FR_API = "https://www.federalregister.gov/api/v1/documents.json"
FR_DAYS = 45
KEEP_DAYS = 120
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
HEADERS = {"User-Agent": UA, "Accept": "text/html,application/json;q=0.9,*/*;q=0.8", "Accept-Language": "en-US,en;q=0.9"}
# CN chapter prefix → product (Korean). Longest prefix wins.
PRODUCTS = [("721070", "컬러강판(유기코팅)"), ("721240", "컬러강판(유기코팅)"), ("720851", "후판"), ("720852", "후판"),
            ("7208", "열연"), ("7211", "열연"), ("7209", "냉연"), ("7210", "도금·기타 표면처리"), ("7212", "도금·기타 표면처리"),
            ("7219", "스테인리스 판재"), ("7220", "스테인리스 판재"), ("7213", "선재"), ("7214", "봉강"), ("7215", "봉강"),
            ("7216", "형강"), ("7217", "강선"), ("7221", "스테인리스 선재"), ("7222", "스테인리스 봉강"), ("7225", "합금강 판재"),
            ("7226", "합금강 판재"), ("7228", "합금강 봉형강"), ("7304", "강관(무계목)"), ("7305", "강관(대구경)"), ("7306", "강관(용접)"),
            ("7301", "시트파일"), ("7302", "철도용 강재")]
BEAT_PRODUCTS = re.compile(r"steel|iron|pipe|tube|wire|rebar|plate|sheet|coil|stainless|transformer|cable|conductor|aluminum|"
                           r"zinc|copper|tire|tyre|polysilicon|solar|silicon|chemical|resin|polyethylene|terephthal|fiber|"
                           r"rod|bar|strip|electrical|vehicle|automotive|battery|graphite|lithium", re.I)
# Beat companies as they appear in US trade notices (respondents, rate tables). 동국제강 and 동국씨엠 are separate companies;
# POSCO International / POSCO Future M are not 포스코.
BEAT_NAMES = [
    ("포스코", r"\bPOSCO\b(?!\s*(?:International|Future|E&C|DX|Holdings))"), ("포스코홀딩스", r"POSCO Holdings"),
    ("현대제철", r"Hyundai Steel"), ("동국제강", r"Dongkuk Steel"), ("동국씨엠", r"Dongkuk (?:CM|Coated)"),
    ("세아제강", r"SeAH Steel(?! Holdings)"), ("세아홀딩스", r"SeAH (?:Steel )?Holdings"), ("KG스틸", r"\bKG (?:Dongbu )?Steel|KG Dongbu"),
    ("고려아연", r"Korea Zinc"), ("영풍", r"Young ?Poong"), ("현대차", r"Hyundai Motor"), ("기아", r"\bKia\b"),
    ("현대모비스", r"Hyundai Mobis"), ("현대위아", r"Hyundai WIA"), ("HL만도", r"\bMando\b"),
    ("한국타이어", r"Hankook Tire"), ("넥센타이어", r"Nexen Tire"), ("금호타이어", r"Kumho Tire"),
    ("HD현대일렉트릭", r"HD Hyundai Electric|Hyundai Electric (?:&|and) Energy|Hyundai Power Transformers"),
    ("LS일렉트릭", r"\bLS Electric|\bLSIS\b"), ("LS전선", r"\bLS Cable"), ("대한전선", r"Taihan"), ("LS MnM", r"\bLS MnM|LS-Nikko"),
    ("두산에너빌리티", r"Doosan Enerbility|Doosan Heavy"), ("효성중공업(관련)", r"Hyosung Heavy"), ("일진전기(관련)", r"Iljin Electric"),
    ("한화솔루션", r"Hanwha Solutions|Hanwha Q ?CELLS|\bQcells\b"), ("OCI", r"\bOCI\b"), ("GS칼텍스", r"GS Caltex"),
    ("태광", r"Taekwang"), ("DL케미칼", r"DL Chemical"), ("동성케미칼", r"Dongsung Chemical"), ("KG모빌리티", r"KG Mobility"),
]
STAGE = [("개시", r"initiation|institution of|commencement"), ("예비 판정", r"preliminary"), ("최종 판정", r"final"),
         ("연례 재심", r"administrative review"), ("일몰 재심", r"sunset|five-year|expiry"), ("범위 판정", r"scope"),
         ("철회·종료", r"revocation|termination|rescission")]


def get_text(url, *, params=None, get=None, headers=HEADERS, timeout=40):
    if get is None:
        import requests
        get = requests.get
    try:
        r = get(url, params=params or {}, headers=headers, timeout=timeout)
    except Exception as e:
        return None, type(e).__name__
    if r.status_code != 200:
        return None, f"HTTP {r.status_code}"
    return (r.text if hasattr(r, "text") else r.content.decode("utf-8", "replace")), None


def plain(raw):
    t = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"(?s)<[^>]+>", " ", t))).strip()


def text_lines(raw):
    """Tags removed but line breaks kept (FR full text comes as <pre> or plain text)."""
    t = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", raw)
    t = re.sub(r"(?i)<br\s*/?>|</(?:p|tr|li|div|h\d)>", "\n", t)
    return html.unescape(re.sub(r"(?s)<[^>]+>", " ", t))


# ---------- EU TARIC ----------

def quarter_start(day):
    return dt.date(day.year, 3 * ((day.month - 1) // 3) + 1, 1)


def previous_quarter(start):
    return quarter_start(start - dt.timedelta(days=1))


def number(s):
    """TARIC prints plain numbers with a dot decimal and no thousands separator ('15126425.659')."""
    try:
        return float(str(s).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def iso(dmy):
    return f"{dmy[6:]}-{dmy[3:5]}-{dmy[:2]}" if dmy else None


def product_of(codes):
    for code in (re.sub(r"\D", "", c) for c in codes):
        for prefix, name in sorted(PRODUCTS, key=lambda x: -len(x[0])):
            if code.startswith(prefix):
                return name
    return None


def parse_quota_detail(raw):
    """quota_tariff_details.jsp → amounts in tonnes (kg/1000), exhaustion date, origin scope, CN codes."""
    t = plain(raw)
    def g(rx):
        m = re.search(rx, t, re.I)
        return m.group(1).strip() if m else None
    initial, balance = number(g(r"Initial amount\s*([\d.,]+)")), number(g(r"\bBalance\s*([\d.,]+)"))
    if initial is None or balance is None:
        return None
    unit = g(r"Initial amount\s*[\d.,]+\s*([A-Za-z]+(?: metre)?)") or ""
    k = 1 / 1000 if unit.lower().startswith("kilogram") else 1
    awaiting = number(g(r"awaiting allocation\s*(?:\(\s*indicative\s*\))?\s*([\d.,]+)"))
    origin = g(r"\bOrigin\s*(.*?)\s*Initial amount") or ""
    others = re.sub(r"European Union|Korea, Republic of \(South Korea\)", "", origin).strip(" ,")
    tail = t.split("Associated TARIC code", 1)[1] if "Associated TARIC code" in t else ""
    codes = re.findall(r"\b(\d{4} \d{2} \d{2}(?: \d{2})?)\b", tail)
    validity = re.search(r"Validity period\s*(\d{2}-\d{2}-\d{4})\s*-\s*(\d{2}-\d{2}-\d{4})", t)
    return {"origin": origin, "scope": "한국 전용" if re.search(r"Korea", origin) and not others else
            ("공동(한국 포함)" if re.search(r"Korea", origin) else "공동"),
            "unit": "t" if k != 1 else unit, "initialT": round(initial * k, 1), "balanceT": round(balance * k, 1),
            "awaitingT": round(awaiting * k, 1) if awaiting is not None else None,
            "usedPct": round((initial - balance) / initial * 100, 1) if initial else None,
            "exhaustedOn": iso(g(r"Exhaustion date\s*(\d{2}-\d{2}-\d{4})")),
            "critical": (g(r"\bCritical\s*(Yes|No)\b") or "").lower() == "yes",
            "periodStart": iso(validity.group(1)) if validity else None, "periodEnd": iso(validity.group(2)) if validity else None,
            "cn": codes[:6], "product": product_of(codes)}


def taric_orders(year, start, *, get=None, sleep=time.sleep):
    """Steel quota order numbers (099xxx) listed for Korea whose period starts on `start` (quota_list.jsp, 20 rows a page)."""
    found, errors, pages = set(), [], 0
    want = start.strftime("%d-%m-%Y")
    for origin in ("KR", "1011"):
        rows_seen = 0
        for offset in range(0, 400, 20):
            raw, err = get_text(f"{TARIC}/quota_list.jsp", params={"Lang": "en", "Year": year, "Origin": origin, "Expand": "true",
                                                                 "Critical": "", "Status": "", "Code": "", "Offset": offset}, get=get)
            sleep(0.5)
            pages += 1
            if err:
                errors.append(f"목록 {origin} {err}")
                break
            n = 0
            for row in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", raw):
                cells = [plain(c) for c in re.findall(r"(?is)<td[^>]*>(.*?)</td>", row)]
                if not cells or not re.fullmatch(r"09\d{4}", cells[0]):
                    continue
                n += 1
                if cells[0].startswith("099") and want in cells:
                    found.add(cells[0])
            rows_seen += n
            if n < 20:
                break
        if rows_seen:
            break  # the ISO code worked; the numeric geo code is only a fallback
    return sorted(found), errors, pages


def quota_tags(d):
    tags = []
    if d.get("exhaustedOn"):
        tags.append(f"[소진 {d['exhaustedOn']} · 분기 {d['daysToExhaust'] + 1}일째]")
    elif d.get("usedPct") is not None and d["usedPct"] >= 80:
        tags.append(f"[사용률 {d['usedPct']}%]")
    if d.get("awaitingT"):
        tags.append(f"[배정 대기 {d['awaitingT']:,}t]")
    if d.get("prevUsedPct") is not None and d.get("usedPct") is not None and d["usedPct"] - d["prevUsedPct"] >= 10:
        tags.append(f"[직전 확인 대비 +{round(d['usedPct'] - d['prevUsedPct'], 1)}%p]")
    last = d.get("lastQuarter") or {}
    if d.get("daysToExhaust") is not None and last.get("daysToExhaust") is not None and d["daysToExhaust"] < last["daysToExhaust"]:
        tags.append(f"[직전 분기보다 {last['daysToExhaust'] - d['daysToExhaust']}일 빨리 소진]")
    return tags


def taric(now, seeds, previous, *, get=None, sleep=time.sleep):
    start = quarter_start(now.date() if isinstance(now, dt.datetime) else now)
    last_start = previous_quarter(start)
    orders, errors, pages = taric_orders(start.year, start, get=get, sleep=sleep)
    orders = sorted(set(orders) | set(seeds))
    prev = {q["order"]: q for q in (previous or {}).get("quotas", []) if isinstance(q, dict) and q.get("status") == "ok"}
    history = {k: dict(v) for k, v in ((previous or {}).get("quotaHistory") or {}).items() if isinstance(v, dict)}
    had_state = bool(prev)
    out = []

    def detail(order, period):
        raw, err = get_text(f"{TARIC}/quota_tariff_details.jsp", params={"Lang": "en", "StartDate": period.isoformat(), "Code": order}, get=get)
        sleep(0.5)
        if err:
            return None, err
        d = parse_quota_detail(raw)
        return (d, None) if d else (None, "형식 불일치")

    for o in orders:
        d, err = detail(o, start)
        if err:
            out.append({"order": o, "status": "failed", "error": err, "periodStart": start.isoformat()})
            continue
        d["daysToExhaust"] = (dt.date.fromisoformat(d["exhaustedOn"]) - start).days if d.get("exhaustedOn") else None
        # the previous quarter is final once it ends, so it is fetched once and kept in history
        last = (history.get(o) or {}).get(last_start.isoformat())
        if last is None and d["scope"] != "공동":
            ld, lerr = detail(o, last_start)
            if ld:
                last = {k: ld.get(k) for k in ("initialT", "balanceT", "usedPct", "exhaustedOn")}
                last["daysToExhaust"] = (dt.date.fromisoformat(ld["exhaustedOn"]) - last_start).days if ld.get("exhaustedOn") else None
                history.setdefault(o, {})[last_start.isoformat()] = last
        p = prev.get(o) or {}
        same = p.get("periodStart") == start.isoformat()
        d.update(order=o, status="ok", periodStart=d.get("periodStart") or start.isoformat(), lastQuarter=last,
                 url=f"{TARIC}/quota_tariff_details.jsp?Lang=en&StartDate={start.isoformat()}&Code={o}",
                 prevUsedPct=p.get("usedPct") if same else None)
        d["tags"] = quota_tags(d)
        d["newlyExhausted"] = had_state and bool(d.get("exhaustedOn")) and not (same and p.get("exhaustedOn"))
        history.setdefault(o, {})[start.isoformat()] = {k: d.get(k) for k in ("initialT", "balanceT", "usedPct", "exhaustedOn", "daysToExhaust")}
        out.append(d)
    keep = {start.isoformat(), last_start.isoformat(), previous_quarter(last_start).isoformat()}
    history = {o: {q: v for q, v in h.items() if q in keep} for o, h in history.items()}
    return out, errors, {"periodStart": start.isoformat(), "listPages": pages, "listed": len(orders)}, history


# ---------- US Federal Register ----------

OMNIBUS = re.compile(r"Initiation of Antidumping and Countervailing Duty Administrative Reviews|Initiation of Five-Year \(Sunset\) Reviews|"
                     r"Notice of Receipt of Complaint|Notice of Institution of Investigation", re.I)
BODY_BUDGET = 40


def stage_of(title):
    for name, rx in STAGE:
        if re.search(rx, title, re.I):
            return name
    return "기타"


def is_337(title):
    """Section 337 (ITC IP) notices: 'Certain X; Notice of …' or complaint receipt. AD/CVD notices also start with
    'Certain … From <country>: … Review; 2023', so anything naming a country of origin or AD/CVD is not 337."""
    if re.search(r"Section 337|Receipt of Complaint", title, re.I):
        return True
    if re.search(r"\bFrom\b|Antidumping|Countervailing|Anti-Dumping|Five-Year|Sunset", title, re.I):
        return False
    return bool(re.match(r"Certain .*;", title))


def named_companies(text):
    """Beat companies named in a notice body, with up to two short lines each (rate tables, respondent lists)."""
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in re.split(r"[\r\n]+", text)]
    out = []
    for name, rx in BEAT_NAMES:
        hits = [ln[:220] for ln in lines if re.search(rx, ln, re.I)]
        if hits:
            out.append({"company": name, "lines": hits[:2], "mentions": len(hits)})
    return out


# Decision memo topics are public in the FR notice itself ('List of Topics Discussed in the … Decision Memorandum' appendix);
# the memo PDFs moved behind a script-rendered ACCESS page (탐침 10-28: 옛 PDF 주소 404). 운영 근거: 10-09 열연 상계관세 최종
# 판정 부록 'Comment 8: Whether the Constructing and Operation of Workplace Nursery Program is Countervailable' → 10-23
# 경쟁지 [단독] '애들 보육비가 철강 보조금?…포스코·현대제철 직장어린이집까지 겨눈 美'.
TOPICS_HEAD = re.compile(r"List of Topics Discussed in the (?:Preliminary |Final )?(?:Issues and )?Decision Memorandum", re.I)
TOPIC_START = re.compile(r"^(?:[IVX]{1,5}\.|[A-Z]\.|\d{1,2}\.|Comment \d+[A-Za-z]?:)\s")
BOILER = re.compile(r"^(?:[IVX]{1,5}\.)\s+(?:Summary|Background|Scope|Period of|Recommendation|Subsidies Valuation|Analysis of Programs|"
                    r"Discussion of the|Currency Conversion|Discussion of the Methodology|Affiliation|Methodology|Use of Facts|"
                    r"Non-Selected|Rate for|Diversification|Changes Since|Margin|Attribution of Subsidies|Final Determination|Preliminary)", re.I)
# Programs and arguments that come up in most Korean steel CVD reviews; a topic with none of these words is shown as unusual.
COMMON = re.compile(r"electricity|K-?ETS|emission|KEXIM|Export-Import|KDB|Korea Development Bank|IBK|KORES|KEPCO|benchmark|interest rate|"
                    r"tax|RSTA|Restriction of Special|loan|cross-own|attribut|LTAR|MTAR|adequate remuneration|uncreditworth|equityworth|"
                    r"debt|grant|R&D|research|port|harbor|land|industrial complex|guarantee|insurance|K-?SURE|currency|exchange rate|"
                    r"sales denominator|de minimis|specificity|financial contribution|facts available|AFA|verification|respondent|"
                    r"rate|scope|ministerial|clerical|sampl|duty absorption|cash deposit|liquidat", re.I)


def memo_topics(text):
    """Substantive topics (programs, comments) of the decision-memo appendix, wrapped lines joined. None when there is no appendix."""
    m = TOPICS_HEAD.search(text or "")
    if not m:
        return None
    seg = re.split(r"\[FR Doc\.|BILLING CODE|\nAppendix I{1,3}\b", text[m.end(): m.end() + 8000])[0]
    items, cur = [], ""
    for ln in (re.sub(r"\s+", " ", x).strip() for x in seg.splitlines()):
        if not ln:
            continue
        if TOPIC_START.match(ln + " "):
            if cur:
                items.append(cur)
            cur = ln
        else:
            cur = f"{cur} {ln}".strip()
    if cur:
        items.append(cur)
    return [t[:300] for t in items if not BOILER.match(t)][:40]


def topic_flags(topics):
    """(beat-named topics, unusual topics) — word tests on the appendix text only."""
    named = [t for t in topics if any(re.search(rx, t, re.I) for _, rx in BEAT_NAMES)]
    unusual = [t for t in topics if re.match(r"(?:Comment \d|\d{1,2}\.|[A-Z]\.)", t) and not COMMON.search(t)]
    return named[:6], unusual[:6]


def federal_register(now, previous=None, *, get=None, sleep=time.sleep):
    """ITA·ITC notices from the last FR_DAYS that name Korea in the title, plus omnibus notices (review initiations,
    337 complaints) — bodies are scanned once for beat company names and the result is cached by document number."""
    since = (now - dt.timedelta(days=FR_DAYS)).strftime("%Y-%m-%d")
    params = [("conditions[term]", "Korea"), ("conditions[publication_date][gte]", since),
              ("conditions[agencies][]", "international-trade-administration"),
              ("conditions[agencies][]", "international-trade-commission"),
              ("order", "newest"), ("per_page", "100")]
    for f in ("title", "publication_date", "html_url", "document_number", "type", "agencies", "raw_text_url"):
        params.append(("fields[]", f))
    if get is None:
        import requests
        get = requests.get
    try:
        r = get(FR_API, params=params, headers={"User-Agent": UA, "Accept": "application/json"}, timeout=40)
        if r.status_code != 200:
            return [], f"HTTP {r.status_code}", 0
        data = r.json()
    except Exception as e:
        return [], type(e).__name__, 0
    prev = {x["id"]: x for x in (previous or {}).get("federalRegister", []) if isinstance(x, dict) and x.get("id")}
    rows, budget = [], BODY_BUDGET
    for x in data.get("results") or []:
        title = x.get("title") or ""
        in_title = bool(re.search(r"korea", title, re.I))
        if not in_title and not OMNIBUS.search(title):
            continue  # Korea only in the body of another country's case
        did = f"fr:{x.get('document_number')}"
        agency = ", ".join(a.get("name", "") for a in x.get("agencies") or [] if isinstance(a, dict))
        row = {"id": did, "date": x.get("publication_date"), "title": title, "agency": agency, "url": x.get("html_url"),
               "stage": stage_of(title), "koreaInTitle": in_title, "omnibus": not in_title,
               "section337": is_337(title),
               "beatProduct": bool(BEAT_PRODUCTS.search(title))}
        old = prev.get(did) or {}
        for k in ("named", "memoTopics", "memoNamed", "memoUnusual"):
            if k in old:
                row[k] = old[k]
        wants_memo = in_title and bool(re.search(r"Results|Determination", title)) and "memoTopics" not in row
        if ("named" not in row or wants_memo) and x.get("raw_text_url") and budget > 0:
            budget -= 1
            body, err = get_text(x["raw_text_url"], get=get, headers={"User-Agent": UA, "Accept": "text/plain,text/html"})
            sleep(0.5)
            if body is not None:
                lines = text_lines(body)
                row["named"] = named_companies(lines)
                topics = memo_topics(lines)
                if topics is not None:
                    row["memoTopics"] = topics
                    row["memoNamed"], row["memoUnusual"] = topic_flags(topics)
                elif wants_memo:
                    row["memoTopics"] = []
            else:
                row["bodyError"] = err
        if row["omnibus"] and "named" in row and not row["named"]:
            continue  # omnibus notice that names no beat company
        rows.append(row)
    return rows, None, BODY_BUDGET - budget


# ---------- Foreign listing pages ----------

LINE_PARSER = 2
KOREA_RX = re.compile(r"korea", re.I)
BLOCK_END = re.compile(r"(?i)<br\s*/?>|</(?:p|tr|li|div|h\d|dt|dd|td|th|summary|section|article)>")


def korea_lines(raw, rx=None):
    """Lines that mention Korea — table rows, list items, headings, paragraphs, link texts — with the first link inside.
    rx: the page's own word for Korea (베트남 'Hàn Quốc' 등); default 'korea'."""
    rx = rx or KOREA_RX
    raw = re.sub(r"(?is)<(script|style|noscript|nav|header|footer)[^>]*>.*?</\1>", " ", raw)
    out = {}
    for href, inner in re.findall(r"""(?is)<a[^>]+href=["']([^"']+)["'][^>]*>(.*?)</a>""", raw):
        t = plain(inner)
        if rx.search(t) and 8 <= len(t) <= 300:
            out.setdefault(t, href)
    # rows first so a table row keeps its link; then any other block-level line
    for row in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", raw):
        t = plain(row)
        if rx.search(t) and 8 <= len(t) <= 400:
            m = re.search(r"""href=["']([^"']+)["']""", row)
            out.setdefault(t, m.group(1) if m else None)
    prev_text = ""
    for chunk in BLOCK_END.split(re.sub(r"(?is)<tr[^>]*>.*?</tr>", "\n", raw)):
        t = plain(chunk)
        if not t:
            continue
        if rx.search(t) and 8 <= len(t) <= 400:
            # a bare country list ("China, South Korea and Vietnam") is keyed with the line before it (the case name)
            key = f"{prev_text[:120]} — {t}" if len(t) < 60 and prev_text else t
            if not any(key in k for k in out):  # already kept as a link or table row
                m = re.search(r"""href=["']([^"']+)["']""", chunk)
                out.setdefault(key, m.group(1) if m else None)
        prev_text = t
    return out


def foreign_pages(pages, previous, now, *, get=None, sleep=time.sleep, relay_token=None):
    prev = {p["id"]: p for p in (previous or {}).get("pages", []) if isinstance(p, dict)}
    out, events = [], []
    for p in pages:
        rec = {k: p[k] for k in ("id", "country", "label", "url")}
        old = prev.get(p["id"]) or {}
        if p.get("disabled"):
            out.append({**rec, "status": "disabled", "error": p["disabled"], "lines": old.get("lines", {})})
            continue
        if p.get("via") == "relay":
            if not relay_token:
                raw, err = None, "중계 토큰 없음"
            else:
                import private_store
                _, raw, err = private_store.relay(p["url"], relay_token, get=get)
        else:
            raw, err = get_text(p["url"], get=get, timeout=60)
            if err in ("ReadTimeout", "ConnectTimeout", "ConnectionError"):
                sleep(5.0)
                raw, err = get_text(p["url"], get=get, timeout=60)
        sleep(1.0)
        if err:
            rec.update(status="failed", error=err, lines=old.get("lines", {}), parser=old.get("parser"))
            out.append(rec)
            continue
        lines = dict(list(korea_lines(raw, re.compile(p["pattern"], re.I) if p.get("pattern") else None).items())[:200])
        rec.update(status="ok", lines=lines, checkedAt=now.isoformat(timespec="seconds"), parser=LINE_PARSER)
        # a baseline taken by another version of the line reader is not compared (its keys differ)
        if old.get("parser") == LINE_PARSER and (old.get("status") == "ok" or old.get("lines")):
            new = [t for t in lines if t not in (old.get("lines") or {})]
            for t in new:
                href = urljoin(p["url"], lines[t]) if lines[t] else None
                events.append({"id": f"{p['id']}:{t[:80]}", "pageId": p["id"], "country": p["country"], "label": p["label"],
                               "text": t, "url": href or p["url"], "detectedAt": now.isoformat(timespec="seconds")})
        out.append(rec)
    return out, events


def run(cfg, *, now, previous=None, get=None, sleep=time.sleep, relay_token=None, ktc_http=None, kita_http=None):
    stamp = now.isoformat(timespec="seconds")
    had_state = bool(previous)
    checks = []
    quotas, terr, tinfo, history = taric(now, cfg.get("taricSeeds", []), previous, get=get, sleep=sleep)
    ok_q = [q for q in quotas if q["status"] == "ok"]
    checks.append({"source": "EU TARIC", "status": ("ok" if len(ok_q) == len(quotas) else "partial") if ok_q else "failed",
                   "returned": len(ok_q), "listed": tinfo["listed"], "listPages": tinfo["listPages"],
                   **({"error": "; ".join(terr[:3]) or "상세 조회 실패"} if terr or not ok_q else {})})
    fr, ferr, bodies = federal_register(now, previous, get=get, sleep=sleep)
    checks.append({"source": "미국 관보", "status": "failed" if ferr else "ok", "returned": len(fr), "bodiesRead": bodies,
                   **({"error": ferr} if ferr else {})})
    pages, page_events = foreign_pages(cfg.get("pages", []), previous, now, get=get, sleep=sleep, relay_token=relay_token)
    for p in pages:
        if p["status"] == "disabled":
            continue
        checks.append({"source": p["label"], "status": p["status"], "returned": len(p.get("lines") or {}),
                       **({"error": p["error"]} if p["status"] != "ok" else {})})
    ktc, ktc_events = (previous or {}).get("ktc"), []
    if ktc_http is not None:
        import ktc_watch
        ktc, ktc_events, kcheck = ktc_watch.collect(ktc, now, ktc_http, sleep=sleep)
        if kcheck["status"] == "failed" and (previous or {}).get("ktc"):
            ktc = dict(previous["ktc"], stale=True)  # 누리집이 안 열리면 지난 목록을 그대로(0건 아님)
        checks.append(kcheck)
    kita, kita_events = (previous or {}).get("kita"), []
    if kita_http is not None:
        import kita_watch
        kita, kita_events, kcheck2 = kita_watch.collect(kita, now, kita_http, sleep=sleep)
        checks.append(kcheck2)
    prev_fr = {x["id"]: x for x in (previous or {}).get("federalRegister", []) if isinstance(x, dict)}
    if ferr:  # keep the last good list rather than showing an empty one
        fr = list(prev_fr.values())
    for x in fr:
        x["firstSeen"] = prev_fr.get(x["id"], {}).get("firstSeen") or stamp
        x["isNew"] = had_state and x["id"] not in prev_fr
    keep_from = (now - dt.timedelta(days=KEEP_DAYS)).isoformat()
    events = [e for e in (previous or {}).get("events", []) if isinstance(e, dict) and e.get("detectedAt", "") >= keep_from]
    seen = {e.get("id") for e in events}
    fresh = page_events + ktc_events + kita_events + [
        {"id": f"taric:{q['order']}:{q['periodStart']}", "pageId": "taric", "country": "EU",
         "label": f"EU 쿼터 {q['order']} {q.get('product') or ''}({q['scope']}) 소진", "text": " ".join(q["tags"]),
         "url": q["url"], "detectedAt": stamp} for q in ok_q if q.get("newlyExhausted")]
    events += [e for e in fresh if e["id"] not in seen]
    events.sort(key=lambda e: e["detectedAt"], reverse=True)
    if terr and not ok_q and previous:  # TARIC down: keep last quotas, marked as stale
        quotas = [dict(q, stale=True) for q in previous.get("quotas", []) if isinstance(q, dict)]
    failed = [c for c in checks if c["status"] != "ok"]
    return {"schema": SCHEMA, "generatedAt": stamp, "status": "partial" if failed else "complete", "checks": checks,
            "baselineSince": (previous or {}).get("baselineSince") or ((previous or {}).get("generatedAt") if previous else None) or stamp,
            "quarter": tinfo["periodStart"], "quotas": quotas, "quotaHistory": history, "federalRegister": fr,
            "pages": pages, "events": events[:300], **({"ktc": ktc} if ktc else {}), **({"kita": kita} if kita else {}),
            "rules": ["쿼터 수치는 EU TARIC 집계(마지막 갱신일 기준)다. 통관 신고 정산·배정 대기 물량 배분으로 바뀔 수 있다.",
                      "'한국 전용'은 원산지가 한국만인 쿼터, '공동'은 인도·튀르키예 등과 나눠 쓰는 쿼터다. 공동 쿼터 소진을 한국 물량 소진으로 쓰지 않는다.",
                      "쿼터 소진이 곧 수출 타격은 아니다(선적 시점 조정·선계약). 업체별 물량·영향은 회사 확인이 필요하다.",
                      "미국 고시에 업체명이 나와도 판정 결과·세율은 원문 표에서 직접 확인한다. 회사명 일치만으로 해당 회사 사건으로 단정하지 않는다.",
                      "무역위원회 누리집에는 신청인(국내 생산자)·피신청인 이름이 대개 없다. 품목이 출입 업종이어도 회사 사건으로 단정하지 않는다.",
                      "무역위 회의 안건은 회의 전 공개 개요다. 판정 결과(긍정·부정·세율)는 회의 뒤 보도자료·의결서로 확인한다.",
                      "무역협회 수입규제DB는 각국 조치를 무역협회가 정리한 2차 자료다. 마진·판정은 단계마다 붙은 원문 링크(관보·WTO 통보 등)로 확인한다.",
                      "조회 실패는 0건이 아니라 미확인."],
            "confirmedScoops": 0}


def main():
    argparse.ArgumentParser(description="무역구제 감시(해외·국내 무역위원회, 기자 전용 저장소로)").parse_args()
    now = dt.datetime.now(KST)
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    import private_store
    previous = None
    if token:
        try:
            previous = private_store.get("trade-remedy", token)
        except private_store.StoreError as e:
            print(f"::warning title=trade-state::이전 상태 조회 실패({e}) — 신규 표시는 이번 실행 기준")
    if private_store.late_scheduled_duplicate(previous, now):
        return
    import kita_watch
    import ktc_watch
    doc = run(cfg, now=now, previous=previous, relay_token=token or None, ktc_http=ktc_watch.Http(), kita_http=kita_watch.Http())
    q = [x for x in doc["quotas"] if x["status"] == "ok"]
    exhausted = sum(1 for x in q if x.get("exhaustedOn"))
    hot = sum(1 for x in q if x.get("tags"))
    new_events = sum(1 for e in doc["events"] if e["detectedAt"] == doc["generatedAt"])
    checks = " ;; ".join(f"{c['source']}={c['status']}({c.get('returned', 0)}{', ' + c['error'] if c.get('error') else ''})" for c in doc["checks"])
    named = sum(1 for x in doc["federalRegister"] if x.get("named"))
    print(f"::notice title=trade-remedy::{doc['quarter']} 분기 쿼터 {len(q)}/{len(doc['quotas'])} 조회 · 소진 {exhausted} · 표시 {hot} · "
          f"미국 관보 {len(doc['federalRegister'])}건(출입처 이름 {named}) · 이번 신규 이벤트 {new_events}")
    print(f"::notice title=trade-remedy-checks::{checks}")
    k = doc.get("ktc") or {}
    kev = [e for e in doc["events"] if e.get("pageId") == "ktc" and e["detectedAt"] == doc["generatedAt"]]
    print(f"::notice title=trade-remedy-ktc::무역위 진행 사건 {len([c for c in k.get('cases', []) if not c.get('stale')])} · "
          f"회의 {len(k.get('meetings', []))}(안건 읽음 {sum(1 for m in k.get('meetings', []) if m.get('agenda'))}) · 보도자료 {len(k.get('news', []))} · 이번 이벤트 {len(kev)}")
    ki = doc.get("kita") or {}
    kiev = [e for e in doc["events"] if e.get("pageId") == "kita" and e["detectedAt"] == doc["generatedAt"]]
    print(f"::notice title=trade-remedy-kita::무역협회 수입규제DB 사건 {len(ki.get('cases', {}))} · 이번 이벤트 {len(kiev)}"
          f"({', '.join(sorted({e['tier'] for e in kiev}))})")
    if not token:
        print("::warning title=trade-remedy-push::MCP_ACCESS_TOKEN 미설정 — 결과를 저장하지 않음")
        return
    if all(c["status"] != "ok" for c in doc["checks"]):
        sys.exit("모든 원천 조회 실패 — 이전 결과 유지(0건 아님)")
    status = private_store.put("trade-remedy", doc, token)
    print(f"::notice title=trade-remedy-push::기자 전용 저장소 전송 HTTP {status}")
    if status == 404:
        print(f"::warning title=trade-remedy-token::토큰 거부 가능성 — {private_store.token_shape(private_store.normalize_token(token))}")
    if status != 200:
        sys.exit(1)


if __name__ == "__main__":
    main()
