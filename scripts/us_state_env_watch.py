"""미국 주 환경청 허가·공고 — 출입처 미국 공장의 대기 허가 신청·제재 공고(기자 전용 저장소 us-state-env).

- 조지아 EPD 주간 공고(Public Advisory·Public Notice PDF, epd.georgia.gov/document/document/paMMYY-N/download): 대기 허가 신청·허가안
  (시설 이름·신청 번호·주소·공고 종류·작업 설명·신청 이유·의견 마감). 11-03 탐침 126: 2026년 PDF 40개 중 현대차 메타플랜트(01월 허가안),
  한화큐셀 조지아(10월 신청 — 회전 농축기·축열식 산화기 추가, 의견 11-06까지)가 나왔다.
- 앨라배마 ADEM 공고 목록(adem.alabama.gov/public-notices): 공고 제목이 시설·회사 이름이다(허가·동의명령(제재)). 11-03 탐침 125.
- 루이지애나 LDEQ 공고(deq.louisiana.gov/public-notices): 의견 링크의 AIName(시설 이름)·Subject(공고 종류)·AI 번호. 현대제철 루이지애나
  제철소·롯데케미칼 레이크찰스가 대상. 11-03 탐침 124.
- 조지아 대기 허가 발급(air.gaepd.org/Permits/Search?Name=…): 시설 ID·허가 번호·발급일·허가 종류(SIP·PSD/NSR·Title V)·설명서(Narrative).
  11-03 탐침 137~138: 메타플랜트 3711-029-0015-P-01-4(2026-02-12), 한화큐셀 USA(달튼) 3674-313-0165-E-02-0(2026-06-01). 신청(주간 공고)
  다음 단계인 '발급'을 본다 — 10-29 경쟁지 [단독]은 루이지애나 제철소 대기 허가 '승인'이었다(루이지애나 발급 문서함 EDMS는 robots 전체 금지라 못 봄).
- 루이지애나 상공위원회(Board of Commerce and Industry) 안건 PDF(opportunitylouisiana.gov 위원회 쪽 링크): 산업 재산세 감면(ITEP)·
  Quality Jobs 등 신청 번호·회사·패리시·투자액 줄. 11-03 탐침 137: 04-22 안건에 Lotte Chemical Louisiana LLC(20240515-A-ITE). 안건 파일 서버는
  robots Crawl-delay 10초라 PDF 사이 10초를 둔다. 안건 = 심의 대상(승인·투자 확정 아님).
- 루이지애나 채권위원회(State Bond Commission) 안건 PDF(11-18 기자 '추천대로' — 해외 현지 공공문서): 행정청 게시판(DOA 위원회 422번
  회의 공고 'MM-DD-YYYY SBC Meeting Posted Agenda')과 재무부 채권위 화면(회의마다 Preliminary·Posted 안건)에서 새 안건만 받아, 'L26-302 -
  Port of South Louisiana (Hyundai Steel Project/FastSites Program) - Not exceeding $400,000,000 …'처럼 번호 붙은 안건 줄에 출입처 미국 법인
  이름이 나온 것. 11-18 탐침 15: 09-17 회의 안건에 현대제철 루이지애나 제철소 채권 두 건(항만 리스 수익채권 상한 4억 달러, LPFA 면세 시설채권
  상한 9억 달러) — WWNO 09-18 '13억 달러 채권' 기사보다 안건 게시가 먼저였다. 안건 = 심의 대상(승인·발행 확정 아님), 금액은 상한.
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
GAP_SEARCH = "https://air.gaepd.org/Permits/Search"
GAP_SITE = "https://air.gaepd.org"
# 조지아 출입처 시설 이름 낱말(11-03 탐침 137 시설 목록: 한화큐셀 조지아·USA, 한화 첨단소재 조지아, 금호타이어 조지아, 메타플랜트, HL-GA,
# HL만도 아메리카, 기아 조지아). 검색은 부분 일치 — 결과는 RULES로 다시 거른다(현대트랜시스·'SRM Hyundai Plant'(레미콘) 제외).
GAP_NAMES = ["Hanwha", "Hyundai", "KIA", "Kumho", "Mando", "HL-GA", "Mobis"]
GAP_RECENT_DAYS = 60
LACI_PAGE = "https://www.opportunitylouisiana.gov/boards-reports-and-rules/louisiana-board-of-commerce-and-industry"
LACI_PDF = re.compile(r'href="(https://admin\.opportunitylouisiana\.gov/wp-content/uploads/(\d{4})/(\d{2})/[^"]*?Agenda[^"]*?\.pdf)"', re.I)
LACI_DELAY = 10.0    # admin.opportunitylouisiana.gov robots.txt: Crawl-delay: 10
LACI_MAX = 2         # 한 실행에 받는 새 안건 PDF 수
LACI_RECENT_DAYS = 120
# 루이지애나 채권위원회(11-18): 행정청 게시판 회의 공고 목록(파일 이름에 회의일)과 재무부 채권위 화면(Wix — 회의마다 Preliminary·Posted 링크, 위가 오래된 회의)
LASBC_DOA = "https://wwwcfprd.doa.louisiana.gov/boardsandcommissions/viewMeetingNotices.cfm?board=422"
LASBC_DOA_PDF = re.compile(r'href=["\']([^"\']*MeetingNotices/422_(\d{2})-(\d{2})-(\d{4})[^"\']*?\.pdf)["\']', re.I)
LASBC_TREASURY = "https://www.treasury.la.gov/state-bond-commission"
LASBC_TR_LINK = re.compile(r'<a\b[^>]*href=["\']([^"\']+\.pdf)["\'][^>]*>(.*?)</a>', re.S | re.I)
LASBC_TR_LAST = 4      # 재무부 화면 맨 아래(최근 회의) Preliminary·Posted 링크 몇 개를 보나
LASBC_MAX = 2          # 한 실행에 받는 새 안건 PDF 수(안건 PDF는 1~2MB, 자본 지출 표가 붙으면 수십만 자)
LASBC_RECENT_DAYS = 45
LASBC_ITEM = re.compile(r"(?<![\d.])(\d{1,3})\.\s+([A-Z]\d{2}-\d{3})\s*-\s*")
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


# ---------- 조지아 대기 허가 발급 ----------

GAP_ROW = re.compile(r'<tr>\s*<th[^>]*data-label="Facility ID"[^>]*>(?P<fid>.*?)</th>\s*<td[^>]*>(?P<name>.*?)</td>\s*<td[^>]*>(?P<permit>.*?)</td>'
                     r'\s*<td[^>]*>(?P<date>.*?)</td>\s*<td[^>]*>(?P<docs>.*?)</td>\s*<td[^>]*>(?P<type>.*?)</td>\s*</tr>', re.S)
HREF = re.compile(r'href="([^"]+)"[^>]*>(.*?)</a>', re.S)


def gap_date(s):
    s = tidy(s).replace("\u2011", "-")
    try:
        return dt.datetime.strptime(s, "%d-%b-%Y").date().isoformat()
    except ValueError:
        return None


def gap_rows(page):
    out = []
    for m in GAP_ROW.finditer(page or ""):
        name = tidy(re.sub(r"<[^>]+>", " ", m.group("name")))
        link = HREF.search(m.group("permit"))
        permit = tidy(re.sub(r"<[^>]+>", " ", link.group(2) if link else m.group("permit")))
        docs = [(tidy(re.sub(r"<[^>]+>", " ", lab)), (GAP_SITE + h) if h.startswith("/") else h) for h, lab in HREF.findall(m.group("docs"))]
        out.append({"fid": tidy(m.group("fid")), "facility": name, "permit": permit, "issued": gap_date(m.group("date")),
                    "type": tidy(re.sub(r"<[^>]+>", " ", m.group("type"))),
                    "permitUrl": ((GAP_SITE + link.group(1)) if link and link.group(1).startswith("/") else link.group(1) if link else None),
                    "docs": [{"label": lab, "url": u} for lab, u in docs]})
    return out


def ga_permits(get, sleep):
    rows, got, failed, seen = [], 0, [], set()
    for i, name in enumerate(GAP_NAMES):
        if i:
            sleep(PAUSE)
        try:
            r = get(GAP_SEARCH, params={"Name": name}, headers=UA, timeout=40)
        except Exception as e:  # noqa: BLE001
            failed.append(f"{name}:{type(e).__name__}")
            continue
        if r.status_code != 200:
            failed.append(f"{name}:HTTP {r.status_code}")
            continue
        got += 1
        for x in gap_rows(r.text):
            company = beat_of(x["facility"])
            if not company or not x["permit"] or x["permit"] in seen:
                continue
            seen.add(x["permit"])
            narrative = next((d["url"] for d in x["docs"] if d["label"].lower().startswith("narrative")), None)
            rows.append({"id": f"gap:{x['permit']}", "source": "gap", "state": "조지아", "company": company, "facility": x["facility"],
                         "fid": x["fid"], "permit": x["permit"], "issued": x["issued"], "permitType": x["type"],
                         "noticeType": f"대기 허가 발급({x['type'] or '종류 미기재'})", "operation": "", "reason": "",
                         "docs": x["docs"], "url": x["permitUrl"] or narrative or GAP_SEARCH})
    status = "failed" if failed and not got else "partial" if failed else "ok"
    return rows, {"source": "조지아 대기 허가 발급", "status": status, "returned": len(rows), **({"error": "; ".join(failed[:4])} if failed else {})}


# ---------- 루이지애나 상공위원회 안건 ----------

LACI_APP = re.compile(r"\b(\d{8}-(?:[A-Z]-)?[A-Z]{2,4})\b")


def laci_rows(text, url):
    text = re.sub(r"\s+", " ", text or "")
    meeting = us_date(text[:600]) or us_date(text)
    marks = list(LACI_APP.finditer(text))
    out = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else min(len(text), m.end() + 260)
        row = text[m.start(): min(end, m.start() + 260)].strip()
        company = beat_of(row)
        if not company:
            continue
        amount = re.search(r"\$[\d,]{4,}", row)
        out.append({"appNo": m.group(1), "row": row[:220], "company": company, "meeting": meeting, "amount": amount.group(0) if amount else None,
                    "url": url})
    return out


def louisiana_ci(now, seen, get, sleep):
    """위원회 쪽에서 최근(올린 달 기준 120일) 안건 PDF 중 아직 안 본 것을 한 실행에 2개까지. (출입처 줄, 받은 주소, 점검)"""
    try:
        r = get(LACI_PAGE, headers=UA, timeout=40)
    except Exception as e:  # noqa: BLE001
        return [], [], {"source": "루이지애나 상공위원회 안건", "status": "failed", "returned": 0, "error": type(e).__name__}
    if r.status_code != 200:
        return [], [], {"source": "루이지애나 상공위원회 안건", "status": "failed", "returned": 0, "error": f"HTTP {r.status_code}"}
    cutoff = (now.date() - dt.timedelta(days=LACI_RECENT_DAYS)).strftime("%Y%m")
    links = []
    for u, y, mo in LACI_PDF.findall(r.text):
        if "rules" in u.lower() or f"{y}{mo}" < cutoff or u in seen or u in links:
            continue
        links.append(u)
    rows, got, failed = [], [], []
    for u in sorted(links)[:LACI_MAX]:
        sleep(LACI_DELAY)
        try:
            d = get(u, headers=UA, timeout=60)
            if d.status_code != 200:
                raise RuntimeError(f"HTTP {d.status_code}")
            for x in laci_rows(pdf_text(d.content), u):
                rows.append({"id": f"laci:{x['appNo']}:{x['meeting'] or u.rsplit('/', 1)[-1]}", "source": "laci", "state": "루이지애나",
                             "company": x["company"], "facility": re.sub(r"^\S+\s+", "", x["row"].split("$")[0]).strip()[:100],
                             "appNo": x["appNo"], "meeting": x["meeting"],
                             "amount": x["amount"], "noticeType": "상공위원회 안건(세제 감면·고용 인센티브)", "operation": "",
                             "reason": x["row"], "url": u})
            got.append(u)
        except Exception as e:  # noqa: BLE001
            failed.append(f"{u.rsplit('/', 1)[-1][:40]}:{type(e).__name__}")
    status = "partial" if failed else "ok"
    return rows, got, {"source": "루이지애나 상공위원회 안건", "status": status, "returned": len(got), "pending": max(0, len(links) - LACI_MAX),
                       **({"error": "; ".join(failed[:3])} if failed else {})}


# ---------- 루이지애나 채권위원회 안건(11-18) ----------

def sbc_rows(text, url, meeting=None):
    """번호 붙은 안건 줄('61. L26-302 - Port of South Louisiana (Hyundai Steel Project/FastSites Program) - Not exceeding $400,000,000 …')
    가운데 출입처 미국 법인 이름이 나온 줄. 회의일은 안건 머리(앞 1,500자)의 날짜, 없으면 주어진 날짜(행정청 파일 이름)."""
    text = re.sub(r"\s+", " ", text or "")
    meeting = us_date(text[:1500]) or meeting
    marks = list(LASBC_ITEM.finditer(text))
    out = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else min(len(text), m.end() + 500)
        row = text[m.start(): min(end, m.start() + 500)].strip()
        company = beat_of(row)
        if not company:
            continue
        cap = re.search(r"Not exceeding \$[\d,]{4,}", row, re.I)
        out.append({"itemNo": m.group(2), "row": row[:420], "company": company, "meeting": meeting,
                    "amount": re.sub(r"(?i)^not exceeding ", "상한 ", cap.group(0)) if cap else None, "url": url})
    return out


def sbc_links(get):
    """(새로 볼 수 있는 안건 링크 [(주소, 종류, 파일 이름 회의일)], 점검 실패 목록)"""
    links, failed = [], []
    try:
        r = get(LASBC_DOA, headers=UA, timeout=40)
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}")
        for href, mo, d, y in LASBC_DOA_PDF.findall(r.text):
            u = urllib.parse.quote(urllib.parse.urljoin(LASBC_DOA, html.unescape(href)), safe="/:%?=&")
            kind = "게시 안건" if re.search(r"posted agenda", href, re.I) else "특별·소위 회의 공고"
            if "cancel" in href.lower():
                continue
            links.append((u, kind, f"{y}-{mo}-{d}"))
    except Exception as e:  # noqa: BLE001
        failed.append(f"행정청 게시판:{type(e).__name__ if not isinstance(e, RuntimeError) else e}")
    try:
        r = get(LASBC_TREASURY, headers=UA, timeout=40)
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}")
        tr = [(m.group(1), re.sub(r"<[^>]+>|\s+", " ", m.group(2)).strip()) for m in LASBC_TR_LINK.finditer(r.text)]
        tr = [(u, label) for u, label in tr if label in ("Preliminary", "Posted")]
        for u, label in tr[-LASBC_TR_LAST:]:
            links.append((u, "예비 안건" if label == "Preliminary" else "게시 안건", None))
    except Exception as e:  # noqa: BLE001
        failed.append(f"재무부 화면:{type(e).__name__ if not isinstance(e, RuntimeError) else e}")
    return links, failed


def louisiana_sbc(now, seen, get, sleep, first):
    """새 안건 PDF를 한 실행에 2개까지. 첫 실행은 지금 보이는 링크를 모두 본 것으로 두고(기준선) 최근 2개만 목록용으로 읽는다.
    (출입처 줄, 본 것으로 둘 주소, 점검)"""
    src = "루이지애나 채권위원회 안건"
    links, failed = sbc_links(get)
    if len(failed) == 2:
        return [], [], {"source": src, "status": "failed", "returned": 0, "error": "; ".join(failed)}
    cutoff = (now.date() - dt.timedelta(days=LASBC_RECENT_DAYS)).isoformat()
    todo, old = [], []
    for u, kind, day in links:
        if u in seen or u in old or u in [t[0] for t in todo]:
            continue
        if day and day < cutoff:
            old.append(u)         # 오래된 회의 공고는 받지 않고 본 것으로
        else:
            todo.append((u, kind, day))
    # 행정청 파일 이름 회의일이 늦은 것부터, 재무부(날짜 모름)는 화면 아래(최근)부터
    todo = sorted([t for t in todo if t[2]], key=lambda t: t[2], reverse=True) + [t for t in reversed(todo) if not t[2]]
    pick = todo[:LASBC_MAX]
    # 첫 실행: 지금 보이는 링크 전부를 본 것으로(기준선). 그 뒤: 오래된 것 + 이번에 읽은 것만(못 읽은 것·한도 넘은 것은 다음 실행에)
    got = old + [t[0] for t in todo] if first else old + [t[0] for t in pick]
    rows = []
    for u, kind, day in pick:
        sleep(PAUSE)
        try:
            d = get(u, headers=UA, timeout=90)
            if d.status_code != 200 or not d.content[:5].startswith(b"%PDF"):
                raise RuntimeError(f"HTTP {d.status_code}")
            for x in sbc_rows(pdf_text(d.content), u, day):
                rows.append({"id": f"lasbc:{x['itemNo']}:{x['meeting'] or 'date?'}", "source": "lasbc", "state": "루이지애나",
                             "company": x["company"], "facility": x["row"].split(" - ")[1][:120] if " - " in x["row"] else x["row"][:120],
                             "appNo": x["itemNo"], "meeting": x["meeting"], "amount": x["amount"], "agenda": kind,
                             "noticeType": "채권위원회 안건(채권 발행 심의)", "operation": "", "reason": x["row"], "url": u})
        except Exception as e:  # noqa: BLE001
            failed.append(f"{u.rsplit('/', 1)[-1][:40]}:{type(e).__name__ if not isinstance(e, RuntimeError) else e}")
            if not first:
                got = [g for g in got if g != u]     # 못 읽은 안건은 다음 실행에 다시
    status = "partial" if failed else "ok"
    return rows, got, {"source": src, "status": status, "returned": len(pick), "pending": 0 if first else max(0, len(todo) - LASBC_MAX),
                       **({"error": "; ".join(failed[:3])} if failed else {})}


# ---------- 합치기 ----------

def tier_of(x):
    if x["source"] == "adem" and x.get("noticeType") == "동의명령(제재)":
        return "B"
    if x["source"] == "gap":   # 대형 신·증설 허가(PSD/NSR)는 A, 그 밖의 발급·변경은 B
        return "A" if re.search(r"PSD|NSR", x.get("permitType") or "") else "B"
    if x["source"] in ("laci", "lasbc"):
        return "B"
    return "A" if A_WORDS.search(f"{x.get('reason') or ''} {x.get('noticeType') or ''}") else "B"


def line(x):
    if x["source"] == "gap":
        return (f"조지아 대기 허가 발급 · {x['facility']}(시설 {x['fid']}) · 허가 {x['permit']} · 발급 {x.get('issued') or '날짜 미기재'}"
                f" · 종류 {x.get('permitType') or '미기재'}")
    if x["source"] == "lasbc":
        return (f"루이지애나 채권위원회 {x.get('agenda') or '안건'}({x.get('meeting') or '회의일 미확인'} 회의) · {x['appNo']}"
                + (f" · 금액 {x['amount']}" if x.get("amount") else "") + f" · 안건 줄 「{x['reason'][:300]}」")
    if x["source"] == "laci":
        return (f"루이지애나 상공위원회 안건({x.get('meeting') or '회의일 미확인'}) · 신청 {x['appNo']}"
                + (f" · 금액 칸 첫 값 {x['amount']}" if x.get("amount") else "") + f" · 줄 「{x['reason'][:200]}」")
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
    first = {k: k not in seen for k in ("ga", "adem", "ldeq", "gap", "laci", "lasbc")}
    ga_rows, ga_got, ga_check = georgia(now, set(seen.get("ga") or []), get, sleep)
    sleep(PAUSE)
    ad_rows, ad_check = adem(get, sleep)
    sleep(PAUSE)
    ld_rows, ld_check = ldeq(get)
    sleep(PAUSE)
    gp_rows, gp_check = ga_permits(get, sleep)
    sleep(PAUSE)
    lc_rows, lc_got, lc_check = louisiana_ci(now, set(seen.get("laci") or []), get, sleep)
    sleep(PAUSE)
    sb_rows, sb_got, sb_check = louisiana_sbc(now, set(seen.get("lasbc") or []), get, sleep, first["lasbc"])
    known = {x["id"]: x for x in prev.get("notices") or [] if isinstance(x, dict) and x.get("id")}
    events = [e for e in prev.get("events") or [] if isinstance(e, dict)]
    have = {e["id"] for e in events}
    recent_from = (now.date() - dt.timedelta(days=GAP_RECENT_DAYS)).isoformat()
    for src, rows, ok in (("ga", ga_rows, ga_check["status"] != "failed"), ("adem", ad_rows, ad_check["status"] == "ok"),
                          ("ldeq", ld_rows, ld_check["status"] == "ok"), ("gap", gp_rows, gp_check["status"] == "ok"),
                          ("laci", lc_rows, lc_check["status"] != "failed"), ("lasbc", sb_rows, sb_check["status"] != "failed")):
        for x in rows:
            if x["id"] in known:
                known[x["id"]]["lastSeen"] = stamp
                continue
            base = first[src]
            known[x["id"]] = {**x, "firstSeen": stamp, "lastSeen": stamp, **({"baseline": True} if base else {})}
            # 발급 허가는 기준선 뒤 처음 보인 번호라도 발급일이 오래됐으면(목록 정리·검색 낱말 변경) 목록에만 남긴다
            stale = src == "gap" and not (x.get("issued") and x["issued"] >= recent_from)
            # 채권위 안건은 회의일이 30일 넘게 지난 것(늦게 올라온 옛 안건)은 목록에만
            stale = stale or (src == "lasbc" and bool(x.get("meeting")) and x["meeting"] < (now.date() - dt.timedelta(days=30)).isoformat())
            if not base and ok and not stale and x["id"] not in have:
                tier = tier_of(x)
                kind = ("주 환경청 제재 공고" if x.get("noticeType") == "동의명령(제재)" else "주 대기 허가 발급" if src == "gap"
                        else "주 상공위원회 안건" if src == "laci" else "주 채권위원회 안건" if src == "lasbc" else "주 환경청 허가·공고")
                events.append({"id": x["id"], "kind": kind,
                               "tier": tier, "company": x["company"], "state": x["state"], "detectedAt": stamp, "url": x["url"],
                               "text": line(x) + (" — 대형 신·증설 허가(PSD/NSR)" if src == "gap" and tier == "A"
                                                  else " — 신설·증설 낱말이 있는 신청(회사 확인)" if tier == "A" else "")
                               + (" · 주 정부 허가 발급 목록(발급≠착공·가동, 허가 내용은 설명서 원문)" if src == "gap"
                                  else " · 주 상공위원회 공개 안건(심의 대상 — 승인·투자 확정 아님, 금액 칸 뜻은 원문 표 머리로 확인)" if src == "laci"
                                  else " · 주 채권위원회 공개 안건(심의 대상 — 채권 승인·발행 확정 아님, 금액은 상한, 발행 주체는 주·항만 등 공공기관)" if src == "lasbc"
                                  else " · 주 정부 공개 공고(허가 신청≠착공·투자 확정)")})
                have.add(x["id"])
    # 목록 원천은 처음 정상으로 읽은 실행이 기준선 — 실패한 실행으로 기준선을 잡으면 다음 실행에 기존 공고가 모두 새것으로 뜬다
    new_seen = {"ga": sorted(set(seen.get("ga") or []) | set(ga_got))[-60:]}
    for k, c in (("adem", ad_check), ("ldeq", ld_check), ("gap", gp_check)):
        if seen.get(k) or c["status"] == "ok":
            new_seen[k] = True
    if seen.get("laci") or lc_got:
        new_seen["laci"] = sorted(set(seen.get("laci") or []) | set(lc_got))[-40:]
    if seen.get("lasbc") or sb_got:
        new_seen["lasbc"] = list(dict.fromkeys(list(seen.get("lasbc") or []) + sb_got))[-80:]
    if not ga_got and not seen.get("ga") and ga_check["status"] == "failed":
        new_seen.pop("ga", None)
    keep_from = (now - dt.timedelta(days=KEEP_DAYS)).isoformat()
    notices = sorted((x for x in known.values() if str(x.get("lastSeen") or x.get("firstSeen")) >= keep_from),
                     key=lambda x: str(x.get("firstSeen")), reverse=True)[:300]
    events = sorted((e for e in events if str(e.get("detectedAt")) >= keep_from), key=lambda e: e["detectedAt"], reverse=True)[:200]
    checks = [ga_check, ad_check, ld_check, gp_check, lc_check, sb_check]
    status = "failed" if all(c["status"] == "failed" for c in checks) else "partial" if any(c["status"] != "ok" for c in checks) else "complete"
    return {"schema": SCHEMA, "generatedAt": stamp, "status": status, "checks": checks, "seen": new_seen,
            "notices": notices, "events": events,
            "rules": ["주 환경청 공개 공고(조지아 EPD 주간 공고 PDF·앨라배마 ADEM 공고·루이지애나 LDEQ 공고)에서 출입처 미국 공장 이름이 나온 것만(이름 규칙은 미국 OSHA 감시와 같다).",
                      "조지아 대기 허가 발급 목록: 기준선 뒤 새 허가 번호이고 발급일이 60일 안인 것만 알린다. PSD/NSR(대형 신·증설)은 A, 그 밖의 발급·변경은 B. 발급≠착공·가동 — 무엇을 허가했는지는 설명서(Narrative) 원문.",
                      "루이지애나 상공위원회 안건: 세제 감면(ITEP)·고용 인센티브 신청·변경 줄에 출입처 미국 법인 이름이 나온 것. 안건은 심의 대상이지 승인·투자 확정이 아니다. 금액 칸의 뜻(투자액·감면액)은 원문 표 머리로 확인.",
                      "루이지애나 채권위원회 안건(11-18): 번호 붙은 안건 줄에 출입처 미국 법인 이름(현대제철 루이지애나 등)이 나온 것. 안건은 심의 대상이고 금액은 상한(Not exceeding) — 승인·발행 여부는 회의 뒤 결과·회의록, 발행 주체는 주·항만 등 공공기관.",
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
