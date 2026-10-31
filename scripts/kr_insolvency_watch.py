"""협력사 회생·파산 공고 감시: 대법원 회생·파산 공고(법인회생·법인파산)에서 출입 업종 제조사만 고른다.

- 원천: 대법원 '공고 > 회생·파산'(ssgo.scourt.go.kr 공고 목록 JSON) 15개 법원 × 법인회생·법인파산, 게시일 최신순.
  회생법원 M&A 공고 게시판(제조업 3개 업종)의 매각 공고도 본다.
- 업종 판단: 공고의 회사 이름을 공장등록(공공데이터포털 한국산업단지공단 공장등록정보)에서 '같은 이름'으로 찾아
  대표 업종(KSIC)·주생산품을 붙인다. 1차 철강·비철·주조, 자동차·부품, 전기장비(변압기·전지·전선), 화학·고무(타이어),
  석유정제 = 핵심 업종. 금속가공·기계·플라스틱·전자부품 = 관련 업종. 공장등록이 없으면 이름 낱말(스틸·금속·케미칼 등)만 참고(C).
- 출입처 협력사 명단(data/kr_supplier_watchlist.json)에 있는 이름은 업종과 관계없이 A.
- 결과는 기자 전용 저장소(kr-insolvency)로만. 공개 로그는 건수만. 조회 실패는 0건이 아니다.
- 공고는 법원 절차 단계다. 거래 관계·납품 차질·출입처 영향은 회사·출입처 확인 전에는 모른다.
"""
from __future__ import annotations

import base64
import datetime as dt
import html as htmlmod
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from kr_official_watch import FACTORY_API, call, emp, norm, parse_factories  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
SCHEMA = "kr_insolvency/v1"
LIST_API = "https://ssgo.scourt.go.kr/ssgo/ssgo930/selectRhblBnkpPbancLst.on"
LIST_PAGE = "https://www.scourt.go.kr/portal/notice/insolvency/insolvency.jsp"
VIEWER = "https://ecfs.scourt.go.kr/sgvo/websquare/websquare.html?w2xPath=/sgvo/ui/sgvo200/SGVO201M01.xml?paramData="
MA_LIST = "https://www.scourt.go.kr/portal/notice/mainfo/MaNoticeList.work"
MA_VIEW = "https://www.scourt.go.kr/portal/notice/mainfo/MaNoticeView.work"
WATCHLIST = ROOT / "data" / "kr_supplier_watchlist.json"
COURTS = [("000221", "서울회생법원"), ("000214", "의정부지방법원"), ("000240", "인천지방법원"), ("000249", "수원회생법원"),
          ("000260", "춘천지방법원"), ("000261", "춘천지방법원 강릉지원"), ("000291", "대전회생법원"), ("000270", "청주지방법원"),
          ("000321", "대구회생법원"), ("000443", "부산회생법원"), ("000411", "울산지방법원"), ("000420", "창원지방법원"),
          ("000543", "광주회생법원"), ("000520", "전주지방법원"), ("000530", "제주지방법원")]
TASKS = [("4", "법인회생"), ("5", "법인파산")]
MA_BUSINESS = [("01", "제조업(기계,금속,중공업)"), ("02", "제조업(전기전자)"), ("03", "제조업(석유,화학)")]
PAGE_SIZE = 100
MAX_PAGES = 5
BASELINE_DAYS = 14
OVERLAP_DAYS = 2
KEEP_DAYS = 180
LOOKUP_BUDGET = 120
LOOKUP_TTL_DAYS = 90
CACHE_MAX = 2000  # ingest body cap 2MB
DEADLINE_SECONDS = 9 * 60

# (종류, 단계, 제목 규칙). 단계: start = 신청·개시·선고(가장 이른 공개 신호), end = 폐지, late = 인가·종결 등.
KINDS = [
    ("포괄적 금지명령", "start", re.compile(r"포괄적\s*금지명령")),
    ("회생 개시", "start", re.compile(r"개시\s*결정")),
    ("파산 선고", "start", re.compile(r"파산\s*선고")),
    ("회생 폐지", "end", re.compile(r"(?<!이시)(?<!동시)폐지\s*결정\s*공고")),
    ("회생계획 인가", "late", re.compile(r"인가\s*결정")),
    ("이시폐지", "late", re.compile(r"이시\s*폐지|동시\s*폐지")),
    ("종결", "late", re.compile(r"종결")),
]
SKIP_TITLE = re.compile(r"의견\s*제출|제출기간|기일\s*변경|연장")
NON_FIRM = re.compile(r"의료법인|재단법인|사단법인|학교법인|사회복지법인|종교|교회|조합|농업회사법인|영농조합|어업회사법인")
CORE = {"241": "1차 철강", "242": "1차 비철금속", "243": "금속 주조", "301": "자동차", "302": "차체·트레일러", "303": "자동차 부품",
        "281": "전동기·발전기·전기변환·공급제어장치", "282": "일차전지·축전지", "283": "절연선·케이블", "201": "기초 화학물질",
        "202": "합성고무·플라스틱 물질", "204": "기타 화학제품", "221": "고무제품", "192": "석유 정제품"}
RELATED = {"25": "금속가공제품", "29": "기타 기계·장비", "28": "전기장비", "222": "플라스틱 제품", "262": "전자부품", "264": "통신·방송장비"}
PRODUCT = re.compile(r"자동차|차량|브레이크|시트|범퍼|머플러|배터리|이차전지|2차전지|양극재|음극재|전해액|분리막|변압기|차단기|개폐기|"
                     r"전선|케이블|강관|강판|철근|형강|선재|주물|주조|단조|타이어|휠|램프|와이어링|하네스|도금|열처리")
NAME_HINT = re.compile(r"스틸|철강|금속|메탈|강관|모텍|오토모티브|자동차|모빌리티|전기|전선|케이블|케미칼|화학|배터리|에너지|소재|타이어")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept": "application/json", "Content-Type": "application/json; charset=UTF-8",
      "Referer": "https://ssgo.scourt.go.kr/ssgo/ssgo930/rhblBnkp.on"}
RULES = [
    "법원 공고의 회사 이름을 공장등록에서 같은 이름으로 찾아 업종을 붙인다. 이름이 같은 다른 회사일 수 있다(주소·대표자 확인).",
    "포괄적 금지명령 = 회생 신청 직후(개시 전). 개시·파산선고가 가장 이른 확정 단계. 거래 관계·납품 차질은 회사·출입처 확인 전에는 모른다.",
    "공장등록이 없는 회사는 이름 낱말만으로 C(참고). 출입처 협력사 명단(data/kr_supplier_watchlist.json)에 있으면 A.",
    "관련 업종(금속가공·기타 기계·전기장비·플라스틱·전자부품)은 주생산품에 출입 업종 낱말(자동차·배터리·변압기·전선·강관 등)이 있을 때만 B, 없으면 C.",
    "같은 이름 공장이 관할 법원 지역 밖에만 있거나 대표자가 3명 이상이면 다른 회사일 수 있어 한 단계 내린다.",
]


def norm_space(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


def ymd(s):
    d = re.sub(r"\D", "", str(s or ""))
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) >= 8 else None


def kind_of(title):
    if SKIP_TITLE.search(title or ""):
        return None, None
    for name, stage, rx in KINDS:
        if rx.search(title or ""):
            return name, stage
    return None, None


def firm_key(name):
    """'주식회사 단지(632-88-00237)' → '단지'; legal words and spaces removed."""
    n = re.sub(r"\(\s*\d{3}-\d{2}-\d{5}\s*\)", "", str(name or ""))
    n = re.sub(r"\(분할신설회사\)|\(분할존속회사\)", "", n)
    return norm(n)


def viewer_url(enc):
    if not enc:
        return None
    data = json.dumps({"encParam": enc, "pspTkn": "NA", "pspSid": "NA"}, separators=(",", ":"))
    return VIEWER + base64.b64encode(data.encode()).decode()


# ---------------------------------------------------------------- court notice list
def fetch_page(task, cort, page, *, post=None, sleep=time.sleep):
    if post is None:
        import requests
        post = requests.post
    body = json.dumps({"dma_search": {"taskDvs": task, "srchType": "pstgBgng", "cortCd": cort, "pstgDvs": "999", "csYr": "", "csDvsCd": "",
                                      "csSrno": "", "debtrNm": "", "jdbnCd": ""},
                       "dma_pageInfo": {"pageNo": page, "pageSize": PAGE_SIZE, "totalYn": "Y" if page == 1 else "N"}})
    last = None
    for timeout in (20, 45):  # scourt.go.kr drops some runner connections; a second, slower try usually answers
        try:
            r = post(LIST_API, data=body, headers=UA, timeout=timeout)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")
            d = r.json()
            data = d.get("data") or {}
            rows = data.get("dlt_pbancLst")
            if rows is None and d.get("status") == 200 and "완료" in str(d.get("message") or ""):
                rows = []  # a court with no notices answers without the list (10-29: 춘천지법 강릉지원)
            if not isinstance(rows, list):
                raise RuntimeError(f"응답 형식 미상({str(d.get('message') or '')[:40]})")
            return rows, (data.get("dma_pageInfo") or {}).get("totalCnt")
        except Exception as e:  # noqa: BLE001
            last = e
            sleep(5)
    raise last


DOWN_AFTER = 4  # 처음부터 이만큼 연달아 접속이 안 되면 대법원 사이트가 내려간 것으로 보고 나머지를 건너뛴다


def court_notices(since_day, *, post=None, sleep=time.sleep, deadline=None):
    """since_day: 날짜 문자열 하나, 또는 원천 이름(법원 업무)을 받아 그 법원 업무의 조회 시작일을 돌려주는 함수."""
    since_for = since_day if callable(since_day) else (lambda source: since_day)
    notices, checks = [], []
    for cort, cname in COURTS:
        for task, tname in TASKS:
            source = f"{cname} {tname}"
            since_day = since_for(source)
            if deadline and time.monotonic() > deadline:
                checks.append({"source": source, "status": "partial", "error": "실행 시간 상한 — 다음 실행에서 조회"})
                continue
            if len(checks) >= DOWN_AFTER and all(c["status"] == "failed" for c in checks):
                checks.append({"source": source, "status": "failed", "error": f"대법원 사이트 접속 불가(앞 {DOWN_AFTER}곳 연속 실패) — 다음 실행에서 조회"})
                continue
            got, pages, total = 0, 0, None
            try:
                for page in range(1, MAX_PAGES + 1):
                    rows, t = fetch_page(task, cort, page, post=post, sleep=sleep)
                    total = t if page == 1 else total
                    pages += 1
                    for x in rows:
                        day = ymd(x.get("pbancBgngYmd"))
                        if day and day >= since_day:
                            notices.append({**x, "_court": cname, "_task": tname})
                            got += 1
                    oldest = min((ymd(x.get("pbancBgngYmd")) or "9999" for x in rows), default="0000")
                    if len(rows) < PAGE_SIZE or oldest < since_day:
                        break
                    sleep(0.8)
                checks.append({"source": source, "status": "ok", "returned": got, "pages": pages, "total": total, "since": since_day})
            except Exception as e:  # noqa: BLE001
                checks.append({"source": source, "status": "failed", "error": str(e)[:80] or type(e).__name__})
            sleep(0.8)
    return notices, checks


def ma_rows(html):
    """회생회사 M&A 공고 게시판 rows: 번호 · 관할법원 · 업종 · 회사 · 작성일."""
    out = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S | re.I):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S | re.I)
        link = re.search(r'href="([^"]*MaNoticeView\.work[^"]*?seqnum=(\d+)[^"]*)"', row)
        if len(cells) < 5 or not link:
            continue
        text = [norm_space(htmlmod.unescape(re.sub(r"<span[^>]*font-size:0px[^>]*>.*?</span>|<[^>]+>", " ", c, flags=re.S))) for c in cells]
        date = re.search(r"20\d{2}-\d{2}-\d{2}", text[4])
        out.append({"seq": link.group(2), "court": text[1], "business": text[2], "company": text[3],
                    "date": date.group(0) if date else None,
                    "url": MA_VIEW + "?" + htmlmod.unescape(link.group(1)).split("?", 1)[-1]})
    return out


def ma_notices(*, get=None, sleep=time.sleep):
    if get is None:
        import requests
        get = requests.get
    rows, checks = [], []
    for code, label in MA_BUSINESS:
        try:
            r = get(MA_LIST, params={"business": code}, headers={"User-Agent": UA["User-Agent"], "Accept": "text/html"}, timeout=30)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")
            got = ma_rows(r.text)
            if not got and "자료가 없습니다" not in r.text:
                raise RuntimeError("목록 형식 미상")
            rows += [{**x, "businessCode": code} for x in got]
            checks.append({"source": f"회생회사 M&A 공고 {label}", "status": "ok", "returned": len(got)})
        except Exception as e:  # noqa: BLE001
            checks.append({"source": f"회생회사 M&A 공고 {label}", "status": "failed", "error": str(e)[:80] or type(e).__name__})
        sleep(0.8)
    return rows, checks


# ---------------------------------------------------------------- industry lookup
CACHE_VERSION = 2
# 법인 회생·파산 관할(본점 소재지). 회생법원은 고등법원 관할 구역 전체의 법인 사건도 받는다(채무자회생법 제3조 제2항),
# 서울회생법원은 전국 큰 회사도 받으므로 지역을 보지 않는다. 회생법원 이름을 지방법원 도시 이름보다 먼저 본다.
REGION_BY_COURT = [("서울", None), ("수원회생", r"경기"), ("대전회생", r"대전|세종|충청남도|충남|충청북도|충북"),
                   ("대구회생", r"대구|경상북도|경북"), ("부산회생", r"부산|울산|경상남도|경남"),
                   ("광주회생", r"광주|전라남도|전남|전라북도|전북|전북특별자치도|제주"), ("의정부", r"경기"), ("인천", r"인천|경기도\s*(?:부천|김포)"), ("수원", r"경기"), ("춘천", r"강원"),
                   ("강릉", r"강원"), ("대전", r"대전|세종|충청남도|충남"), ("청주", r"충청북도|충북"), ("대구", r"대구|경상북도|경북"),
                   ("부산", r"부산"), ("울산", r"울산|경상남도\s*양산"), ("창원", r"경상남도|경남"), ("광주", r"광주|전라남도|전남"),
                   ("전주", r"전라북도|전북|전북특별자치도"), ("제주", r"제주")]


def region_rx(court):
    for city, rx in REGION_BY_COURT:
        if city in str(court or ""):
            return re.compile(rx) if rx else None
    return None


def factory_match(f):
    code = re.sub(r"\D", "", f.get("rprsntvIndutyCode") or "")
    text = f"{f.get('indutyNm') or ''} {f.get('mainProductCn') or ''}"
    for p, name in CORE.items():
        if code.startswith(p):
            return "core", name
    for p, name in sorted(RELATED.items(), key=lambda kv: -len(kv[0])):
        if code.startswith(p):
            return ("product" if PRODUCT.search(text) else "related"), name
    if PRODUCT.search(text):
        return "product", "주생산품 낱말"
    return None, None


RANK = {"core": 0, "product": 1, "related": 2}


def classify_factories(facs):
    """Same-name factories, beat-relevant ones kept as candidates (best first); the notice's court picks among them."""
    if not facs:
        return {"v": CACHE_VERSION, "match": None, "factories": 0}
    owners = len({norm(f.get("rprsntvNm")) for f in facs if f.get("rprsntvNm")})
    cands = []
    for f in facs:
        m, label = factory_match(f)
        if m:
            cands.append({"m": m, "l": label, "c": re.sub(r"\D", "", f.get("rprsntvIndutyCode") or "") or None,
                          "i": (f.get("indutyNm") or "")[:40] or None, "p": (f.get("mainProductCn") or "")[:60] or None,
                          "e": emp(f.get("allEmplyCo")), "a": (f.get("rnAdres") or "")[:60] or None})
    cands.sort(key=lambda c: (RANK[c["m"]], -(c["e"] or 0)))
    if not cands:
        f = facs[0]
        return {"v": CACHE_VERSION, "match": "factory-other", "code": re.sub(r"\D", "", f.get("rprsntvIndutyCode") or "") or None,
                "industry": (f.get("indutyNm") or "")[:40] or None, "factories": len(facs), "owners": owners}
    return {"v": CACHE_VERSION, "match": cands[0]["m"], "factories": len(facs), "owners": owners, "cands": cands[:5]}


def pick(info, court):
    """Industry for one notice: a same-name factory inside the court's region first. Outside it → regionMismatch."""
    if not info or not info.get("cands"):
        return info
    rx = region_rx(court)
    cands = info["cands"]
    local = [c for c in cands if rx and rx.search(c.get("a") or "")]
    best = local[0] if local else cands[0]
    return {"match": best["m"], "label": best["l"], "code": best["c"], "industry": best["i"], "product": best["p"], "employees": best["e"],
            "address": best["a"], "factories": info.get("factories"), "owners": info.get("owners"),
            "regionMismatch": bool(rx) and not local}


def doubtful(ind):
    """Name may belong to another company: factory outside the court's region, or 3+ owners under the same name."""
    return bool(ind) and (bool(ind.get("regionMismatch")) or (ind.get("owners") or 0) >= 3)


def lookup(name, key, *, get=None, sleep=time.sleep):
    q = firm_key(name)
    if len(q) < 2:
        return {"match": None, "factories": 0}, None
    text, err = call(FACTORY_API, {"serviceKey": key, "pageNo": 1, "numOfRows": 50, "type": "json", "cmpnyNm": q}, get=get, sleep=sleep)
    if err:
        return None, err
    try:
        code, _total, items = parse_factories(text)
    except Exception as e:  # noqa: BLE001
        return None, f"형식 오류 {type(e).__name__}"
    if code not in ("00", "0", "NORMAL_SERVICE"):
        return None, f"결과코드 {code or '?'}"
    same = [it for it in items if norm(it.get("cmpnyNm")) == q]
    return classify_factories(same), None


def load_watchlist(path=WATCHLIST):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {firm_key(x.get("name")): x for x in data.get("suppliers") or [] if x.get("name")}


# ---------------------------------------------------------------- run
def tier_of(stage, match, watch, ind=None):
    if watch:
        return "A"
    t = _tier(stage, match)
    return {"A": "B", "B": "C"}.get(t, t) if t and doubtful(ind) else t


def _tier(stage, match):
    if match == "core":
        return "A" if stage == "start" else "B" if stage == "end" else "C"
    if match == "product":
        return "B" if stage == "start" else "C"
    if match == "related":
        # 관련 업종(금속가공·기타 기계·전기장비·플라스틱 등)인데 주생산품에 출입 업종 낱말이 없으면 참고(C)
        # (10-31 운영: 맨홀·바이오필터·화장품 용기·덕트 제조사가 B로 떠 B 28건 중 상당수를 차지)
        return "C"
    if match == "name":
        return "C"
    return None


def since_of(previous, now):
    floor = now - dt.timedelta(days=BASELINE_DAYS)
    try:
        last = dt.datetime.fromisoformat(str(previous.get("lastSuccess") or previous.get("generatedAt")))
        return max(floor, last - dt.timedelta(days=OVERLAP_DAYS)).date().isoformat()
    except (AttributeError, TypeError, ValueError):
        return floor.date().isoformat()


def court_since(previous, now, source):
    """법원 업무별 조회 시작일: 그 법원 업무를 마지막으로 다 읽은 때 − 겹침(10-30 07:20 대법원 접속 불가 실행이 전체 성공 시각을
    앞당겨 다음 실행 범위가 줄 수 있었다). 기록이 없으면 전체 기준(since_of)."""
    last = ((previous or {}).get("courtLastOk") or {}).get(source)
    if not last:
        return since_of(previous, now)
    floor = now - dt.timedelta(days=BASELINE_DAYS)
    try:
        return max(floor, dt.datetime.fromisoformat(str(last)) - dt.timedelta(days=OVERLAP_DAYS)).date().isoformat()
    except (TypeError, ValueError):
        return since_of(previous, now)


def run(key, *, now, previous=None, post=None, get=None, sleep=time.sleep, watchlist=None, deadline=None):
    stamp = now.isoformat(timespec="seconds")
    baseline = not (isinstance(previous, dict) and previous.get("events") is not None)
    since_day = since_of(None if baseline else previous, now)
    watch = load_watchlist() if watchlist is None else watchlist
    notices, checks = court_notices(lambda source: since_day if baseline else court_since(previous, now, source), post=post, sleep=sleep, deadline=deadline)
    court_last = dict((previous or {}).get("courtLastOk") or {})
    court_last.update({c["source"]: stamp for c in checks if c["status"] == "ok"})
    since_day = min([c["since"] for c in checks if c.get("since")] or [since_day])
    ma, ma_checks = ma_notices(get=get, sleep=sleep)
    checks += ma_checks

    # candidate notices: key kinds only, firms only
    cands = []
    kinds_count = {}
    for x in notices:
        kind, stage = kind_of(x.get("pbancTitlNm"))
        if not kind:
            continue
        kinds_count[kind] = kinds_count.get(kind, 0) + 1
        if NON_FIRM.search(x.get("btprtNm") or ""):
            continue
        cands.append((x, kind, stage))
    seen_ma = set((previous or {}).get("maSeen") or [])
    ma_new = [r for r in ma if baseline or r["seq"] not in seen_ma]

    cache = dict((previous or {}).get("industryCache") or {})
    fresh_cut = (now - dt.timedelta(days=LOOKUP_TTL_DAYS)).isoformat()
    stale = {firm_key(e.get("company")) for e in (previous or {}).get("events") or []
             if (cache.get(firm_key(e.get("company"))) or {}).get("match") in RANK and (cache.get(firm_key(e.get("company"))) or {}).get("v") != CACHE_VERSION}
    order = sorted({firm_key(x.get("btprtNm")) for x, _, st in cands if st != "late"} | {firm_key(r["company"]) for r in ma_new} | stale,
                   key=lambda k: (0 if NAME_HINT.search(k) else 1, k))
    lookups, pending, lookup_errors = 0, 0, []
    if key:
        for k in order:
            c = cache.get(k)
            current = c and str(c.get("checkedAt")) >= fresh_cut and (c.get("v") == CACHE_VERSION or c.get("match") not in RANK)
            if not k or current or k in watch:
                continue
            if lookups >= LOOKUP_BUDGET or (deadline and time.monotonic() > deadline):
                pending += 1
                continue
            res, err = lookup(k, key, get=get, sleep=sleep)
            lookups += 1
            if err:
                lookup_errors.append(err)
                continue
            cache[k] = {**res, "checkedAt": stamp}
    status_lookup = "unset" if not key else "failed" if lookups and len(lookup_errors) == lookups else "partial" if pending else "ok"
    checks.append({"source": "공장등록 업종 조회", "status": status_lookup, "returned": lookups - len(lookup_errors),
                   **({"pending": pending} if pending else {}),
                   **({"error": f"{len(lookup_errors)}건 실패({lookup_errors[0]})"} if lookup_errors else {}),
                   **({"error": "DATA_GO_KR_KEY·CUSTOMS_API_KEY 미설정 — 업종 미확인"} if not key else {})})

    def industry_for(name, court):
        k = firm_key(name)
        info = pick(cache.get(k), court)
        w = watch.get(k)
        match = (info or {}).get("match")
        if match in (None, "factory-other") and NAME_HINT.search(k):
            match = "name"
        return k, info, w, match

    old = {e["id"]: e for e in (previous or {}).get("events") or []}
    events = dict(old)
    found = set()
    for x, kind, stage in cands:
        k, info, w, match = industry_for(x.get("btprtNm"), x.get("_court"))
        tier = tier_of(stage, match, w, info)
        if not tier:
            continue
        eid = f"ins:{x.get('cortCd')}:{x.get('csNo')}:{x.get('inetPbancDvsCd')}:{x.get('inetPbancSeq')}"
        found.add(eid)
        prev = old.get(eid)
        events[eid] = {
            "id": eid, "source": "대법원 회생·파산 공고", "kind": kind, "stage": stage, "title": norm_space(x.get("pbancTitlNm")),
            "company": norm_space(x.get("btprtNm")), "court": x.get("_court"), "task": x.get("_task"), "caseNo": x.get("csNoNm"),
            "division": x.get("jdbnCdNm"), "posted": ymd(x.get("pbancBgngYmd")), "industry": info, "match": match,
            "watch": {k2: w[k2] for k2 in ("beat", "relation", "evidence") if w and w.get(k2)} or None,
            "tier": tier, "url": viewer_url(x.get("encParam")), "listUrl": LIST_PAGE,
            "firstSeen": prev["firstSeen"] if prev else stamp, "baseline": bool(prev.get("baseline")) if prev else baseline,
            "isNew": not prev and not baseline,
        }
    for r in ma:
        k, info, w, match = industry_for(r["company"], r["court"])
        eid = f"ma:{r['seq']}"
        prev = old.get(eid)
        if r["seq"] in seen_ma and not prev:
            continue  # seen earlier and not kept
        tier = "A" if w else ("C" if doubtful(info) or match == "related" else "B") if match in RANK else "C" if match == "name" else None
        if not tier:
            continue
        found.add(eid)
        events[eid] = {
            "id": eid, "source": "회생회사 M&A 공고", "kind": "M&A 매각 공고", "stage": "sale", "title": f"{r['business']} 매각 공고",
            "company": r["company"], "court": r["court"], "task": "M&A", "caseNo": None, "division": None, "posted": r["date"],
            "industry": info, "match": match, "watch": {k2: w[k2] for k2 in ("beat", "relation", "evidence") if w and w.get(k2)} or None,
            "tier": tier, "url": r["url"], "listUrl": MA_LIST,
            "firstSeen": prev["firstSeen"] if prev else stamp, "baseline": bool(prev.get("baseline")) if prev else baseline,
            "isNew": not prev and not baseline,
        }
    for eid, e in events.items():
        if eid not in found:
            e["isNew"] = False
    # an industry looked up after the notice was stored: refresh the stored events' industry and tier
    for e in events.values():
        if e["source"] == "대법원 회생·파산 공고" and e["id"] not in found:
            k, info, w, match = industry_for(e["company"], e.get("court"))
            if info:  # stored notices follow the current cache and region rules
                e["industry"], e["match"] = info, match
                e["tier"] = tier_of(e["stage"], match, w, info) or e["tier"]

    cut = (now - dt.timedelta(days=KEEP_DAYS)).date().isoformat()
    kept = sorted((e for e in events.values() if str(e.get("posted") or e["firstSeen"])[:10] >= cut),
                  key=lambda e: (str(e.get("posted") or ""), e["id"]), reverse=True)
    if len(cache) > CACHE_MAX:
        cache = dict(sorted(cache.items(), key=lambda kv: str(kv[1].get("checkedAt")), reverse=True)[:CACHE_MAX])
    court_checks = [c for c in checks if not c["source"].startswith(("회생회사", "공장등록"))]
    court_failed = [c for c in court_checks if c["status"] == "failed"]
    failed = [c for c in checks if c["status"] == "failed"]
    court_ok = [c for c in court_checks if c["status"] == "ok"]
    status = ("failed" if len(court_failed) == len(court_checks) or not court_ok else
              "partial" if failed or any(c["status"] == "partial" for c in checks) else "complete")
    return {
        "schema": SCHEMA, "generatedAt": stamp, "status": status,
        "lastSuccess": stamp if status != "failed" else (previous or {}).get("lastSuccess"), "courtLastOk": court_last,
        "baselineSince": (previous or {}).get("baselineSince") or stamp, "windowStart": since_day,
        "checks": checks, "events": kept, "industryCache": cache, "maSeen": sorted({r["seq"] for r in ma} | seen_ma)[-500:],
        "counts": {"notices": len(notices), "keyKinds": kinds_count, "firms": len(cands), "lookups": lookups, "pending": pending},
        "watchlistSize": len(watch), "rules": RULES,
    }


def main():
    import private_store
    now = dt.datetime.now(KST)
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    key = (os.environ.get("DATA_GO_KR_KEY") or os.environ.get("CUSTOMS_API_KEY") or "").strip()
    previous = None
    if token:
        try:
            previous = private_store.get("kr-insolvency", token)
        except private_store.StoreError as e:
            print(f"::warning title=kr-insolvency-state::이전 상태 조회 실패({e}) — 이번 실행은 기준선")
    if private_store.late_scheduled_duplicate(previous, now):
        return
    doc = run(key, now=now, previous=previous, deadline=time.monotonic() + DEADLINE_SECONDS)
    ok = sum(1 for c in doc["checks"] if c["status"] == "ok")
    tiers = {}
    for e in doc["events"]:
        if e.get("isNew"):
            tiers[e["tier"]] = tiers.get(e["tier"], 0) + 1
    c = doc["counts"]
    bad = [x for x in doc["checks"] if x["status"] != "ok"]
    # 실패 원인 예(오류 종류만 — 공고 내용·키는 싣지 않음). 10-31(토) 실행이 34곳 중 1곳만 정상이었는데 원인이 로그에 없었다.
    sample, errs = [], set()
    for x in bad:  # 서로 다른 오류만 3가지까지
        err = str(x.get("error") or x["status"])[:40]
        if err not in errs and len(sample) < 3:
            errs.add(err)
            sample.append(f"{x['source']}({err})")
    why = f" · 미확인 {len(bad)}곳 예: {', '.join(sample)}" if bad else ""
    print(f"::notice title=kr-insolvency::상태 {doc['status']} · 원천 {ok}/{len(doc['checks'])} 정상 · 공고 {c['notices']}건(주요 단계 {sum(c['keyKinds'].values())}) · "
          f"업종 조회 {c['lookups']}(대기 {c['pending']}) · 새 항목 {tiers} · 보관 {len(doc['events'])}{why}")
    if not token:
        print("::warning title=kr-insolvency-push::MCP_ACCESS_TOKEN 미설정 — 결과를 저장하지 않음")
        return
    if doc["status"] == "failed":
        sys.exit("대법원 회생·파산 공고 전체 조회 실패 — 이전 결과 유지(0건 아님)")
    status = private_store.put("kr-insolvency", doc, token)
    print(f"::notice title=kr-insolvency-push::기자 전용 저장소 전송 HTTP {status}")
    if status != 200:
        sys.exit(1)


if __name__ == "__main__":
    main()
