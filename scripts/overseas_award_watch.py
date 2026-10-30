"""해외 발주처 낙찰 공고 감시: 출입처(전력기기·전선·철강·에너지·자동차)가 해외 공공 발주처 입찰에서 낙찰자로 적힌 공고.

- EU TED(유럽 공공·유틸리티 조달): 낙찰 공고(can-*)의 낙찰자 이름·국가 필드. 한국 국적 낙찰자 전체 질의 1번 +
  출입처 영문명 질의(유럽 현지 법인 낙찰까지). 공고 전문 검색이 아니라 낙찰자 필드에 이름이 있어야 잡는다.
- 영국 Find a Tender(OCDS): 낙찰 단계 릴리스의 공급사 이름·주소 국가.
- 세계은행 조달 공고(Contract Award): 'Awarded Bidder(s)' 칸에 적힌 회사만. 탈락·평가 명단에 있는 이름은 버린다.
  (이라크·요르단·이집트·모로코 등 중동·북아프리카와 중앙아시아·남아시아 전력망 사업)
- 바레인 입찰위원회 월간 낙찰 보고서(PDF): 새 달 보고서에서 출입처 영문명이 나온 줄만.
- 대만 정부전자조달망(PCC) 결정 공고: g0v 공개 미러 API(pcc-api.openfun.app, 매일 갱신)에서 출입처 이름(영문·중문)으로 찾고,
  공고의 득표·탈락 구분 칸(name_key)에서 '得標廠商'(낙찰자)으로 적힌 것만. 대만전력(台灣電力) 전선·광섬유지선 등
  (10-30 탐침: LS Cable & System 2026-02 복합광섬유지선 NT$131,601,032, 2025-09 ZTACIR 품목 NT$276,084,986 등).
  새로 본 공고는 상세(tender API)를 한 번 읽어 출입처 품목의 결정 금액·원산지·결정일을 붙인다. 링크는 g0v 열람기(공고 이력·원문 링크)와
  대만 정부전자조달망 원문 주소(10-30 한국에서 열리지 않은 적 있음).
- 결과는 기자 전용 저장소(overseas-awards)로만. 공개 로그는 건수만. 조회 실패는 0건이 아니다.

다루지 않는 것: 사우디전력(SEC)·두바이수전력청(DEWA)·카타르 카라마·쿠웨이트 전력부 자체 조달(공개 낙찰 목록 없음 또는
봇 차단). 쿠웨이트 중앙입찰청(CAPT)은 봇 확인 화면이 떠 조회하지 않는다(우회하지 않음).
"""
from __future__ import annotations

import datetime as dt
import html as htmlmod
import io
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

KST = dt.timezone(dt.timedelta(hours=9))
SCHEMA = "overseas_awards/v1"
UA = {"User-Agent": "newsroom-official-research/1.0 (github.com/shhong9173-art/seoul-reporting-radar)", "Accept": "application/json"}
BASELINE_DAYS = 120
OVERLAP_DAYS = 3
KEEP_DAYS = 200
KEEP_MAX = 400

TED_API = "https://api.ted.europa.eu/v3/notices/search"
TED_CAN = "notice-type IN (can-standard can-social can-modif can-desg can-tran)"
TED_FIELDS = ["publication-number", "publication-date", "notice-type", "buyer-name", "buyer-country", "winner-name", "winner-country",
              "winner-identifier", "title-lot", "notice-title", "result-value-notice", "result-value-cur-notice", "total-value",
              "total-value-cur", "contract-conclusion-date"]
TED_PAUSE = 2.0
TED_PAGES = 3
FTS_API = "https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages"
FTS_PAGES = 40
WB_API = "https://search.worldbank.org/api/v2/procnotices"
BH_LIST = "https://www.tenderboard.gov.bh/Tenders/AwardedTenders/"
BH_SITE = "https://www.tenderboard.gov.bh"
BH_MAX_BYTES = 20_000_000

# (출입처, 낙찰자 이름 규칙, TED 질의 낱말, 세계은행 질의 낱말)
COMPANIES = [
    ("효성중공업", r"hyosung\s+(?:heavy\s+indust\w*|hico|t\s*&\s*d|power\s*&\s*industrial)", "Hyosung", "Hyosung"),
    ("HD현대일렉트릭", r"hd\s+hyundai\s+electric|hyundai\s+electric\s*(?:&|and)\s*energy|hyundai\s+power\s+transformers", "Hyundai Electric", "Hyundai Electric"),
    ("LS전선", r"\bls\s+cable(?:\s*(?:&|and)\s*system)?", "LS Cable", "LS Cable"),
    ("대한전선", r"\btaihan\s+(?:cable|electric)", "Taihan", "Taihan"),
    ("LS일렉트릭", r"\bls\s+electric\b|\bls\s+industrial\s+systems|\blsis\b", "LS Electric", "LS Electric"),
    ("일진전기", r"\biljin\s+electric", "Iljin", "Iljin Electric"),
    ("두산에너빌리티", r"\bdoosan\s+(?:enerbility|heavy\s+industries)", "Doosan", "Doosan"),
    ("현대제철", r"\bhyundai\s+steel", "Hyundai Steel", "Hyundai Steel"),
    ("포스코", r"\bposco\b", "POSCO", "POSCO"),
    ("세아제강", r"\bseah\s+steel", "SeAH", "SeAH"),
    ("한국수력원자력", r"korea\s+hydro\s*(?:&|and)\s*nuclear|\bkhnp\b", "Korea Hydro", "Korea Hydro"),
    ("한국전력", r"korea\s+electric\s+power|\bkepco\b", "KEPCO", "KEPCO"),
    ("한화솔루션", r"\bhanwha\s+(?:q\s*cells|solutions|energy)", "Hanwha", "Hanwha"),  # 방산·조선(에어로스페이스·오션)은 출입처 밖
    ("현대차", r"\bhyundai\s+motor", "Hyundai Motor", None),
    ("기아", r"\bkia\s+(?:corporation|motors?|europe|slovakia|deutschland|uk|ireland|sweden|austria|belgique|belgium|nederland|"
            r"czech|polska|iberia|italia|france|portugal|hungary|slovenija)", None, None),  # 'Kia' 전문 검색은 잡음(10-29 탐침 851건 중 0건)
    ("현대모비스", r"\bhyundai\s+mobis", "Hyundai Mobis", None),
    ("현대로템", r"\bhyundai\s+rotem", "Hyundai Rotem", "Hyundai Rotem"),
    ("고려아연", r"\bkorea\s+zinc", "Korea Zinc", None),
]
COMPANY_RX = [(ko, re.compile(rx, re.I)) for ko, rx, _, _ in COMPANIES]
KOREA_RX = re.compile(r"\bkorea\b(?!\s*,?\s*(?:democratic|dprk|north))|\bkor\b|republic\s+of\s+korea", re.I)
COUNTRY_KO = {"DNK": "덴마크", "SWE": "스웨덴", "FIN": "핀란드", "NOR": "노르웨이", "ESP": "스페인", "PRT": "포르투갈", "GBR": "영국",
              "DEU": "독일", "NLD": "네덜란드", "BEL": "벨기에", "FRA": "프랑스", "ITA": "이탈리아", "IRL": "아일랜드", "AUT": "오스트리아",
              "POL": "폴란드", "CZE": "체코", "SVK": "슬로바키아", "HUN": "헝가리", "ROU": "루마니아", "BGR": "불가리아", "GRC": "그리스",
              "HRV": "크로아티아", "SVN": "슬로베니아", "EST": "에스토니아", "LVA": "라트비아", "LTU": "리투아니아", "LUX": "룩셈부르크",
              "CHE": "스위스", "ISL": "아이슬란드", "CYP": "키프로스", "MLT": "몰타"}
RULES = [
    "낙찰자 칸에 이름이 있을 때만 잡는다(공고 본문에 이름만 나온 것·탈락 명단은 버림). 금액은 공고에 적힌 값 그대로(형식값 1·2·-1은 미기재).",
    "유럽 TED 공고는 계약 체결 뒤 몇 주~몇 달 늦게 올라온다 — '공고일'이 새것이어도 계약은 예전일 수 있다(계약일 칸 확인).",
    "현지 판매법인(예: 현대차 체코·기아 유럽) 낙찰은 본사 수주와 다르다. 이름 그대로 보고 판단.",
    "중동 걸프 전력회사(SEC·DEWA·카라마·쿠웨이트 전력부) 자체 조달은 공개 낙찰 목록이 없어 다루지 않는다.",
    "대만 PCC는 g0v 공개 미러로 찾고 원문 링크는 대만 정부전자조달망이다. 금액은 대만달러(NT$). 공고 전체 금액은 다른 낙찰자 품목을 포함할 수 있어, 상세를 읽으면 출입처 품목 금액으로 바꾼다.",
]


def norm_space(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


def beat_of(name):
    name = str(name or "").replace("_", " ")  # TED joins a country prefix: 'DE_POONGSAN CORPORATION'
    for ko, rx in COMPANY_RX:
        if rx.search(name):
            return ko
    return None


AUTOMAKERS = {"현대차", "기아"}


def ted_text(v):
    """TED multilingual field → English when present, else the first language."""
    if isinstance(v, dict):
        for lang in ("eng", "ENG"):
            if v.get(lang):
                return v[lang]
        for val in v.values():
            return val
        return None
    return v


def as_list(v):
    v = ted_text(v)
    if v is None:
        return []
    return [str(x) for x in (v if isinstance(v, list) else [v])]


def all_names(v):
    """Winner names across every language key: TED lists some lots' winners only under the buyer's language."""
    if isinstance(v, dict):
        out = []
        for val in v.values():
            out += val if isinstance(val, list) else [val]
        return [str(x) for x in out if x]
    return as_list(v)


# Rough EUR rates for the automaker-subsidiary threshold only (never shown).
TO_EUR = {"EUR": 1, "CZK": 0.04, "PLN": 0.23, "HUF": 0.0025, "RON": 0.2, "BGN": 0.51, "SEK": 0.088, "DKK": 0.134, "NOK": 0.085,
          "CHF": 1.05, "GBP": 1.17, "USD": 0.92, "ISK": 0.0066}
LOCAL_FLEET_EUR = 10_000_000


def money(value, cur):
    try:
        n = float(str(value).split(",")[0] if isinstance(value, str) else value)
    except (TypeError, ValueError):
        return None, None
    if n < 100:  # TED framework placeholders (1, 2, -1)
        return None, None
    return n, (cur or None)


def _get(get, url, **kw):
    if get is None:
        import requests
        get = requests.get
    return get(url, headers=kw.pop("headers", UA), timeout=kw.pop("timeout", 60), **kw)


def _post(post, url, payload):
    if post is None:
        import requests
        post = requests.post
    return post(url, json=payload, headers=UA, timeout=60)


# ---------------------------------------------------------------- EU TED
def ted_search(query, *, post=None, sleep=time.sleep):
    rows, total = [], None
    for page in range(1, TED_PAGES + 1):
        body = {"query": f"{query} SORT BY publication-date DESC", "fields": TED_FIELDS, "limit": 50, "scope": "ALL",
                "paginationMode": "PAGE_NUMBER", "page": page}
        r = _post(post, TED_API, body)
        if r.status_code == 429:
            sleep(15)
            r = _post(post, TED_API, body)
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}")
        d = r.json()
        if not isinstance(d.get("notices"), list):
            raise RuntimeError("응답 형식 미상")
        total = d.get("totalNoticeCount")
        rows += d["notices"]
        if len(rows) >= int(total or 0) or not d["notices"]:
            break
        sleep(TED_PAUSE)
    return rows, total


def ted_items(rows):
    out = []
    for n in rows:
        num = str(n.get("publication-number") or "")
        if not re.fullmatch(r"\d{1,9}-20\d{2}", num):
            continue
        names = {}
        for w in all_names(n.get("winner-name")):
            names.setdefault(norm_space(w).lower(), norm_space(w))
        uniq = sorted(names.values(), key=lambda w: (beat_of(w) is None, w))  # beat companies first
        countries = as_list(n.get("winner-country"))
        ids = as_list(n.get("winner-identifier"))
        beat = [b for b in (beat_of(w) for w in uniq) if b]
        korean = beat or "KOR" in countries
        if not korean:
            continue
        typ = str(n.get("notice-type") or "")
        value, cur = money(n.get("result-value-notice"), n.get("result-value-cur-notice"))
        if value is None:
            tv = n.get("total-value")
            value, cur = money(tv, (as_list(n.get("total-value-cur")) or [None])[0])
        titles = as_list(n.get("title-lot")) or as_list(n.get("notice-title"))
        concluded = sorted({str(x)[:10] for x in as_list(n.get("contract-conclusion-date"))})
        bc = as_list(n.get("buyer-country"))
        out.append({
            "id": f"ted:{num}", "source": "EU TED", "published": str(n.get("publication-date") or "")[:10],
            "kind": "계약 변경" if typ == "can-modif" else "낙찰",
            "buyer": norm_space(" / ".join(dict.fromkeys(as_list(n.get("buyer-name")))))[:160],
            "buyerCountry": bc[0] if bc else None, "winners": uniq[:6], "winnerCount": len(uniq),
            "winnerCountry": sorted(set(countries))[:4], "winnerIds": sorted(set(ids))[:2] if len(uniq) == 1 else [],
            "company": beat[0] if beat else None, "companies": sorted(set(beat)),
            "title": norm_space(" / ".join(dict.fromkeys(titles)))[:240], "value": value, "currency": cur,
            "concluded": concluded[-1] if concluded else None, "noticeType": typ,
            "url": f"https://ted.europa.eu/en/notice/-/detail/{num}",
        })
    return out


def ted(since, *, post=None, sleep=time.sleep):
    day = since.strftime("%Y%m%d")
    queries = [("한국 국적 낙찰자", f"{TED_CAN} AND winner-country=KOR AND publication-date>={day}")]
    queries += [(f"{ko}({term})", f'{TED_CAN} AND FT~"{term}" AND publication-date>={day}') for ko, _, term, _ in COMPANIES if term]
    items, checks = {}, []
    for label, q in queries:
        try:
            rows, total = ted_search(q, post=post, sleep=sleep)
            got = ted_items(rows)
            for it in got:
                items.setdefault(it["id"], it)
            checks.append({"source": "EU TED", "query": label, "status": "ok", "returned": len(rows), "total": total, "matched": len(got)})
        except Exception as e:  # noqa: BLE001
            checks.append({"source": "EU TED", "query": label, "status": "failed", "error": str(e)[:80] or type(e).__name__})
        sleep(TED_PAUSE)
    return list(items.values()), checks


# ---------------------------------------------------------------- UK Find a Tender
def fts_items(releases):
    out = []
    for x in releases:
        rid = str(x.get("id") or "")
        parties = x.get("parties") or []
        by_id = {p.get("id"): p for p in parties}
        suppliers = []
        for a in x.get("awards") or []:
            for s in a.get("suppliers") or []:
                p = by_id.get(s.get("id")) or {}
                country = ((p.get("address") or {}).get("countryName") or "")
                suppliers.append((norm_space(s.get("name") or p.get("name")), country))
        for p in parties:
            if "supplier" in (p.get("roles") or []) and p.get("name"):
                suppliers.append((norm_space(p["name"]), (p.get("address") or {}).get("countryName") or ""))
        hit = [(n, c) for n, c in dict.fromkeys(suppliers) if beat_of(n) or KOREA_RX.search(c or "")]
        if not hit:
            continue
        buyer = (x.get("buyer") or {}).get("name") or next((p.get("name") for p in parties if "buyer" in (p.get("roles") or [])), "")
        value = cur = None
        for c in (x.get("contracts") or []) + (x.get("awards") or []):
            v = c.get("value") or {}
            if v.get("amount"):
                value, cur = money(v.get("amount"), v.get("currency"))
                if value:
                    break
        tender = x.get("tender") or {}
        beat = sorted({b for b in (beat_of(n) for n, _ in hit) if b})
        num = rid if re.fullmatch(r"\d{6}-20\d{2}", rid) else None
        out.append({
            "id": f"fts:{rid or x.get('ocid')}", "source": "영국 Find a Tender", "published": str(x.get("date") or "")[:10], "kind": "낙찰",
            "buyer": norm_space(buyer)[:160], "buyerCountry": "GBR", "winners": [n for n, _ in hit][:6],
            "winnerCountry": sorted({c for _, c in hit if c})[:3], "winnerIds": [], "company": beat[0] if beat else None, "companies": beat,
            "title": norm_space(tender.get("title"))[:240], "value": value, "currency": cur, "concluded": None, "noticeType": ",".join(x.get("tag") or []),
            "url": f"https://www.find-tender.service.gov.uk/Notice/{num}" if num else "https://www.find-tender.service.gov.uk/Search",
        })
    return out


def fts(since, *, get=None, sleep=time.sleep):
    params = {"stages": "award", "updatedFrom": since.strftime("%Y-%m-%dT%H:%M:%S"), "limit": 100}
    url, releases, pages = FTS_API, [], 0
    try:
        while pages < FTS_PAGES:
            r = _get(get, url, params=params if pages == 0 else None)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")
            d = r.json()
            pages += 1
            rel = d.get("releases") or []
            releases += rel
            nxt = (d.get("links") or {}).get("next")
            if not nxt or not rel:
                break
            url = nxt
            sleep(0.5)
        else:
            items = fts_items(releases)
            return items, [{"source": "영국 Find a Tender", "query": "낙찰 단계 릴리스", "status": "partial", "returned": len(releases),
                            "matched": len(items), "error": f"{FTS_PAGES}쪽 상한 — 남은 쪽 다음 실행"}]
    except Exception as e:  # noqa: BLE001
        return [], [{"source": "영국 Find a Tender", "query": "낙찰 단계 릴리스", "status": "failed", "error": str(e)[:80] or type(e).__name__}]
    items = fts_items(releases)
    return items, [{"source": "영국 Find a Tender", "query": "낙찰 단계 릴리스", "status": "ok", "returned": len(releases), "pages": pages, "matched": len(items)}]


# ---------------------------------------------------------------- World Bank
WB_STOP = re.compile(r"evaluated\s+bidder|rejected\s+bidder|bidder\(s\)\s+rejected|reason\s+for\s+rejection|non[\s-]*responsive|"
                     r"evaluation\s+scores|bidders?\s+not\s+(?:awarded|selected)|unsuccessful", re.I)
WB_NAME = re.compile(r"([A-Z0-9][A-Za-z0-9&.,'’()/\- ]{2,140}?)\s*\((\d{3,8})\)")
WB_PRICE = re.compile(r"(signed\s+contract\s+price|evaluated\s+bid\s+price|bid\s+price\s+at\s+opening)\s*:?\s*([A-Z]{3})\s*([\d.,]{3,})", re.I)


def strip_html(s):
    return norm_space(htmlmod.unescape(re.sub(r"<[^>]+>", " ", str(s or ""))))


def wb_awarded(text):
    """Bidders named in the 'Awarded Bidder(s)' block only, with country and the block's price."""
    t = strip_html(text)
    out = []
    for m in re.finditer(r"awarded\s+bidder\(?s?\)?\s*:?", t, re.I):
        seg = t[m.end(): m.end() + 900]
        stop = WB_STOP.search(seg)
        if stop:
            seg = seg[: stop.start()]
        found = [(norm_space(nm.group(1)).strip(" ,.-"), seg[nm.end(): nm.end() + 300]) for nm in WB_NAME.finditer(seg)]
        if not found:  # older notices: 'Awarded Bidder(s): NAME Country: X' without the vendor number
            for chunk in re.finditer(r"\s*(.{3,160}?)\s+(country\s*:.{0,60})", seg, re.I):
                found.append((norm_space(chunk.group(1)).strip(" ,.-"), chunk.group(2)))
                break
        for name, rest in found:
            c = re.search(r"country\s*:?\s*([A-Za-z ,.'()-]{3,40}?)(?=\s+(?:bid|evaluated|signed|duration|$)|$)", rest, re.I)
            out.append({"name": name, "country": norm_space(c.group(1)) if c else ""})
        prices = list(WB_PRICE.finditer(seg)) or list(WB_PRICE.finditer(t))
        rank = {"signed contract price": 0, "evaluated bid price": 1, "bid price at opening": 2}
        prices.sort(key=lambda p: rank.get(norm_space(p.group(1)).lower(), 3))
        if out and prices:
            out[-1]["price"] = (norm_space(prices[0].group(1)).lower(), prices[0].group(2), prices[0].group(3))
    return out


def wb_date(s):
    try:
        return dt.datetime.strptime(str(s), "%d-%b-%Y").date().isoformat()
    except ValueError:
        return str(s or "")[:10]


def wb_items(notices, since_day):
    out = []
    for n in notices:
        day = wb_date(n.get("noticedate"))
        if day and day < since_day:
            continue
        winners = wb_awarded(n.get("notice_text"))
        hit = [w for w in winners if beat_of(w["name"]) or KOREA_RX.search(w.get("country") or "")]
        if not hit:
            continue
        beat = sorted({b for b in (beat_of(w["name"]) for w in hit) if b})
        price = next((w["price"] for w in winners if w.get("price")), None)
        value = cur = None
        if price:
            value, cur = money(price[2].replace(",", ""), price[1])
        nid = str(n.get("id") or "")
        out.append({
            "id": f"wb:{nid}", "source": "세계은행 조달", "published": day, "kind": "낙찰",
            "buyer": norm_space(f"{n.get('project_ctry_name') or ''} · {n.get('project_name') or ''}")[:160],
            "buyerCountry": n.get("project_ctry_name"), "winners": [w["name"] for w in hit][:6],
            "winnerCountry": sorted({w.get("country") for w in hit if w.get("country")})[:3], "winnerIds": [],
            "company": beat[0] if beat else None, "companies": beat, "title": norm_space(n.get("bid_description"))[:240],
            "value": value, "currency": cur, "priceKind": price[0] if price else None, "concluded": None, "noticeType": n.get("notice_type"),
            "url": f"https://projects.worldbank.org/en/projects-operations/procurement-detail/{nid}",
        })
    return out


def wb(since, *, get=None, sleep=time.sleep):
    terms = [("한국 국적 낙찰자", "Korea, Republic of")] + [(f"{ko}({t})", t) for ko, _, _, t in COMPANIES if t]
    items, checks, since_day = {}, [], since.date().isoformat()
    for label, term in terms:
        try:
            r = _get(get, WB_API, params={"format": "json", "rows": 50, "notice_type": "Contract Award", "qterm": term,
                                          "srt": "noticedate", "order": "desc"})
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")
            ns = r.json().get("procnotices")
            if not isinstance(ns, list):
                raise RuntimeError("응답 형식 미상")
            got = wb_items(ns, since_day)
            for it in got:
                items.setdefault(it["id"], it)
            checks.append({"source": "세계은행 조달", "query": label, "status": "ok", "returned": len(ns), "matched": len(got)})
        except Exception as e:  # noqa: BLE001
            checks.append({"source": "세계은행 조달", "query": label, "status": "failed", "error": str(e)[:80] or type(e).__name__})
        sleep(1)
    return list(items.values()), checks


# ---------------------------------------------------------------- Bahrain Tender Board monthly awards (PDF)
def bh_reports(html):
    rows = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S | re.I):
        href = re.search(r'href="([^"]+\.pdf)"', row, re.I)
        subject = strip_html(row)
        if href and re.search(r"award", subject + href.group(1), re.I):
            rows.append({"href": href.group(1), "subject": subject[:90]})
    return rows


def pdf_text(raw):
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(raw))
    return "\n".join((p.extract_text() or "") for p in reader.pages)


def bh_items(text, report, href):
    out, seen = [], set()
    lines = [norm_space(x) for x in text.splitlines() if norm_space(x)]
    for i, line in enumerate(lines):
        beat = beat_of(line)
        if not beat and not re.search(r"\bkorea\b", line, re.I):
            continue
        snippet = " / ".join(lines[max(0, i - 2): i + 2])[:400]
        key = (beat, snippet[:120])
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "id": f"bh:{href.rsplit('/', 1)[-1]}:{len(out)}", "source": "바레인 입찰위원회", "published": None, "kind": "낙찰(월간 보고서)",
            "buyer": "바레인 정부 발주처(보고서 줄 참조)", "buyerCountry": "BHR", "winners": [], "winnerCountry": [], "winnerIds": [],
            "company": beat, "companies": [beat] if beat else [], "title": snippet, "report": report, "value": None, "currency": None,
            "concluded": None, "noticeType": "awarded-report", "url": BH_SITE + href.replace(" ", "%20"),
        })
    return out[:20]


def bahrain(previous_seen, *, get=None):
    try:
        r = _get(get, BH_LIST, headers={**UA, "Accept": "text/html"})
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}")
        reports = bh_reports(r.text)
        if not reports:
            raise RuntimeError("보고서 목록 형식 미상")
    except Exception as e:  # noqa: BLE001
        return [], [{"source": "바레인 입찰위원회", "query": "월간 낙찰 보고서", "status": "failed", "error": str(e)[:80] or type(e).__name__}], previous_seen
    # First run: older reports are remembered unread; only the newest one is read.
    seen = list(previous_seen) if previous_seen else [x["href"] for x in reports[1:]]
    items, checks = [], []
    for rep in reports[:2]:
        if rep["href"] in seen:
            continue
        try:
            pr = _get(get, BH_SITE + rep["href"].replace(" ", "%20"), headers={**UA, "Accept": "application/pdf"}, timeout=120)
            if pr.status_code != 200:
                raise RuntimeError(f"HTTP {pr.status_code}")
            if len(pr.content) > BH_MAX_BYTES:
                raise RuntimeError("파일이 너무 큼")
            text = pdf_text(pr.content)
            seen.append(rep["href"])
            if len(text.strip()) < 500:
                # 10-29: August 2026 report (8.7MB) is a scanned image — 9 characters. Not retried; the report stays unread.
                checks.append({"source": "바레인 입찰위원회", "query": rep["subject"], "status": "ok", "returned": 1, "matched": None,
                               "note": "스캔 이미지 PDF — 자동 판독 불가, 이 보고서는 미확인(원문 직접 확인)", "url": BH_SITE + rep["href"].replace(" ", "%20")})
                continue
            got = bh_items(text, rep["subject"], rep["href"])
            items += got
            checks.append({"source": "바레인 입찰위원회", "query": rep["subject"], "status": "ok", "returned": 1, "matched": len(got)})
        except Exception as e:  # noqa: BLE001
            checks.append({"source": "바레인 입찰위원회", "query": rep["subject"], "status": "failed", "error": str(e)[:80] or type(e).__name__})
    if not checks:
        checks.append({"source": "바레인 입찰위원회", "query": "월간 낙찰 보고서", "status": "ok", "returned": len(reports), "matched": 0, "note": "새 보고서 없음"})
    return items, checks, seen[-60:]


# ---------------------------------------------------------------- Taiwan PCC (g0v mirror of web.pcc.gov.tw)
PCC_SEARCH = "https://pcc-api.openfun.app/api/searchbycompanyname"
PCC_TENDER = "https://pcc-api.openfun.app/api/tender"
PCC_OFFICIAL = "https://web.pcc.gov.tw/prkms/tender/common/noticeDate/redirectPublic?ds={date}&fn={fn}.xml"
PCC_VIEWER = "https://openfunltd.github.io/pcc-viewer/tender.html?unit_id={unit}&job_number={job}"  # 10-30 브라우저로 열림 확인(공고 이력·원문 링크)
PCC_SOURCE = "대만 정부조달(PCC)"
# (출입처, 검색어) — 영문은 COMPANIES 규칙으로, 중문은 PCC_ZH로 출입처를 정한다. 'LS Electric'은 대만 지사가 중문 이름(韓商樂星電氣)으로 나온다.
PCC_TERMS = [("LS전선", "LS Cable"), ("대한전선", "Taihan"), ("대한전선", "大韓電線"), ("LS일렉트릭", "樂星電氣"), ("LS일렉트릭", "LS Electric"),
             ("LS일렉트릭", "LS Industrial"), ("HD현대일렉트릭", "Hyundai Electric"), ("효성중공업", "Hyosung"), ("효성중공업", "曉星"),
             ("두산에너빌리티", "Doosan"), ("일진전기", "Iljin"), ("현대제철", "Hyundai Steel"), ("포스코", "POSCO"), ("한화솔루션", "Hanwha"),
             ("세아제강", "SeAH"), ("한국전력", "KEPCO"), ("한국수력원자력", "Korea Hydro")]
PCC_ZH = [("LS일렉트릭", re.compile(r"樂星電氣|樂星產電")), ("LS전선", re.compile(r"樂星電纜")), ("대한전선", re.compile(r"大韓電線")),
          ("효성중공업", re.compile(r"韓商曉星|曉星重工")), ("HD현대일렉트릭", re.compile(r"現代電氣|現代電機能源")), ("현대로템", re.compile(r"現代樂鐵"))]
PCC_TYPES = {"決標公告": "낙찰", "更正決標公告": "계약 변경"}  # 更正決標公告(낙찰 정정·변경)는 B
WIN_KEY = re.compile(r"^決標品項:第(\d+)品項:得標廠商(\d+):得標廠商$")
PCC_DETAIL_MAX = 12  # 실행당 새 공고 상세 읽기 상한


def pcc_beat(name):
    return beat_of(name) or next((ko for ko, rx in PCC_ZH if rx.search(str(name or ""))), None)


def pcc_winners(rec):
    """공고 회사 칸 가운데 낙찰자(得標廠商)로 적힌 이름. '未得標廠商'(탈락)은 뺀다."""
    keys = (((rec.get("brief") or {}).get("companies") or {}).get("name_key")) or {}
    return [n for n, ks in keys.items() if any(re.search(r"(?<!未)得標廠商\d*:得標廠商$", k) for k in (ks or []))]


def roc_date(s):
    m = re.match(r"^\s*(\d{2,3})/(\d{1,2})/(\d{1,2})", str(s or ""))
    return f"{int(m.group(1)) + 1911:04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else None


def twd(s):
    t = re.sub(r"[^\d]", "", str(s or ""))
    return int(t) if t else None


def pcc_items(records, since_day):
    out = []
    for rec in records:
        b = rec.get("brief") or {}
        kind = PCC_TYPES.get(b.get("type"))
        d = str(rec.get("date") or "")
        if not kind or len(d) != 8:
            continue
        day = f"{d[:4]}-{d[4:6]}-{d[6:]}"
        if day < since_day:
            continue
        winners = pcc_winners(rec)
        beat_w = [w for w in winners if pcc_beat(w)]
        if not beat_w:
            continue  # 탈락 명단·이름만 나온 공고는 버림
        beat = sorted({pcc_beat(w) for w in beat_w})
        fn = str(rec.get("filename") or "")
        out.append({
            "id": f"pcc:{rec.get('unit_id')}:{rec.get('job_number')}:{fn}", "source": PCC_SOURCE, "published": day, "kind": kind,
            "buyer": norm_space(rec.get("unit_name"))[:160], "buyerCountry": "TWN", "winners": beat_w[:6], "winnerCount": len(winners),
            "winnerCountry": [], "winnerIds": [], "company": beat[0], "companies": beat, "title": norm_space(b.get("title"))[:240],
            "value": rec.get("award_amount") or None, "currency": "TWD", "priceKind": "공고 전체 결정 금액(품목이 여럿이면 합계)" if rec.get("award_amount") else None,
            "concluded": None, "noticeType": b.get("type"),
            "url": PCC_VIEWER.format(unit=rec.get("unit_id"), job=rec.get("job_number")),
            "official": PCC_OFFICIAL.format(date=d, fn=fn) if fn else None,
            "tenderApi": rec.get("tender_api_url"), "unitId": rec.get("unit_id"), "jobNumber": rec.get("job_number"), "filename": fn,
        })
    return out


def pcc_detail(item, *, get=None):
    """새 공고 한 번: 출입처가 낙찰한 품목의 결정 금액·원산지, 결정일, 표적 분류."""
    r = _get(get, PCC_TENDER, params={"unit_id": item.get("unitId"), "job_number": item.get("jobNumber")})
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}")
    rec = next((x for x in (r.json().get("records") or []) if str(x.get("filename")) == item.get("filename")), None)
    if not rec:
        raise RuntimeError("상세 없음")
    det = rec.get("detail") or {}
    lines, total = [], 0
    for k, v in det.items():
        m = WIN_KEY.match(k)
        if not m or not pcc_beat(v):
            continue
        pre = k.rsplit(":", 1)[0]
        amt = twd(det.get(pre + ":決標金額"))
        origin = norm_space(det.get(pre + ":原產地國別:原產地國別"))
        item_name = norm_space(det.get(f"決標品項:第{m.group(1)}品項:品項名稱"))
        total += amt or 0
        lines.append(f"{m.group(1)}번 품목{f' {item_name}' if item_name else ''} {v} NT${amt:,}" if amt else f"{m.group(1)}번 품목 {v} 금액 미기재")
        if origin:
            lines[-1] += f"(원산지 {origin})"
    return {"lines": lines, "beatTotal": total or None, "concluded": roc_date(det.get("決標資料:決標日期")),
            "category": norm_space(det.get("採購資料:標的分類"))[:80] or None}


def pcc(since, previous_ids, *, get=None, sleep=time.sleep):
    items, checks, since_day = {}, [], since.date().isoformat()
    for ko, term in PCC_TERMS:
        try:
            r = _get(get, PCC_SEARCH, params={"query": term})
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")
            recs = r.json().get("records")
            if not isinstance(recs, list):
                raise RuntimeError("응답 형식 미상")
            got = pcc_items(recs, since_day)
            for it in got:
                items.setdefault(it["id"], it)
            checks.append({"source": PCC_SOURCE, "query": f"{ko}({term})", "status": "ok", "returned": len(recs), "matched": len(got)})
        except Exception as e:  # noqa: BLE001
            checks.append({"source": PCC_SOURCE, "query": f"{ko}({term})", "status": "failed", "error": str(e)[:80] or type(e).__name__})
        sleep(1)
    read = 0
    for it in sorted(items.values(), key=lambda x: x["published"], reverse=True):
        if it["id"] in previous_ids or read >= PCC_DETAIL_MAX:
            continue
        read += 1
        try:
            d = pcc_detail(it, get=get)
            if d["lines"]:
                it["title"] = f"{it['title']} — {' · '.join(d['lines'])}"[:400]
            if d["beatTotal"]:
                it["value"], it["priceKind"] = d["beatTotal"], "출입처 낙찰 품목 결정 금액 합"
            it["concluded"], it["category"] = d["concluded"], d["category"]
        except Exception as e:  # noqa: BLE001 — 상세 실패는 목록 값만 남긴다
            it["detailError"] = str(e)[:60] or type(e).__name__
        sleep(1)
    return list(items.values()), checks


# ---------------------------------------------------------------- run
def tier_of(it):
    if not it.get("company"):
        return "C"
    if it.get("kind") == "계약 변경" or it.get("source") == "바레인 입찰위원회":
        return "B"
    # 완성차 현지 판매법인(예: Hyundai Motor Czech)의 관용차 납품은 본사 수주가 아니다. 큰 물량(약 1천만 유로 이상)만 B.
    if it["company"] in AUTOMAKERS and "KOR" not in (it.get("winnerCountry") or []) and not KOREA_RX.search(" ".join(it.get("winnerCountry") or [])):
        eur = (it.get("value") or 0) * TO_EUR.get(it.get("currency") or "", 0)
        return "B" if eur >= LOCAL_FLEET_EUR else "C"
    return "A"


def since_of(previous, now):
    floor = now - dt.timedelta(days=BASELINE_DAYS)
    try:
        last = dt.datetime.fromisoformat(str(previous.get("lastSuccess") or previous.get("generatedAt")))
        return max(floor, last - dt.timedelta(days=OVERLAP_DAYS))
    except (AttributeError, TypeError, ValueError):
        return floor


def run(*, now, previous=None, get=None, post=None, sleep=time.sleep):
    stamp = now.isoformat(timespec="seconds")
    baseline = not (isinstance(previous, dict) and previous.get("items") is not None)
    since = since_of(previous if not baseline else None, now)
    fts_since = since if not baseline else now - dt.timedelta(days=7)
    found, checks = [], []
    for fn in (lambda: ted(since, post=post, sleep=sleep), lambda: fts(fts_since, get=get, sleep=sleep), lambda: wb(since, get=get, sleep=sleep)):
        got, ch = fn()
        found += got
        checks += ch
    bh_got, bh_checks, bh_seen = bahrain((previous or {}).get("bahrainSeen"), get=get)
    found += bh_got
    checks += bh_checks
    known = {x.get("id") for x in (previous or {}).get("items") or [] if isinstance(x, dict)}
    pcc_got, pcc_checks = pcc(since, known, get=get, sleep=sleep)
    old_by = {x.get("id"): x for x in (previous or {}).get("items") or [] if isinstance(x, dict)}
    for it in pcc_got:  # 상세는 처음 볼 때만 읽으니, 다시 잡힌 공고는 저장된 상세(금액·결정일)를 그대로 쓴다
        o = old_by.get(it["id"])
        if o:
            for k in ("title", "value", "priceKind", "concluded", "category", "detailError"):
                if k in o:
                    it[k] = o[k]
    found += pcc_got
    checks += pcc_checks
    old = {x["id"]: x for x in (previous or {}).get("items") or []}
    items = dict(old)
    for it in found:
        prev = old.get(it["id"])
        it["firstSeen"] = prev["firstSeen"] if prev else stamp
        it["baseline"] = bool(prev.get("baseline")) if prev else baseline
        it["isNew"] = not prev and not baseline
        it["tier"] = tier_of(it)
        items[it["id"]] = it
    found_ids = {i["id"] for i in found}
    for k, x in list(items.items()):
        if k not in found_ids:
            x["isNew"] = False
            # stored items follow the current name and tier rules (e.g. a company dropped from the beat list)
            if x.get("source") != "바레인 입찰위원회":
                beat = sorted({b for b in ((pcc_beat if x.get("source") == PCC_SOURCE else beat_of)(w) for w in x.get("winners") or []) if b})
                x["company"], x["companies"] = (beat[0] if beat else None), beat
            x["tier"] = tier_of(x)
    cut = (now - dt.timedelta(days=KEEP_DAYS)).date().isoformat()
    kept = [x for x in items.values() if str(x.get("published") or x.get("firstSeen"))[:10] >= cut]
    kept.sort(key=lambda x: (str(x.get("published") or x["firstSeen"][:10]), x["id"]), reverse=True)
    failed = [c for c in checks if c["status"] == "failed"]
    status = "failed" if len(failed) == len(checks) else "partial" if failed or any(c["status"] == "partial" for c in checks) else "complete"
    return {
        "schema": SCHEMA, "generatedAt": stamp, "status": status,
        "lastSuccess": stamp if status != "failed" else (previous or {}).get("lastSuccess"),
        "baselineSince": (previous or {}).get("baselineSince") or stamp, "windowStart": since.date().isoformat(),
        "checks": checks, "items": kept[:KEEP_MAX], "bahrainSeen": bh_seen, "rules": RULES,
        "coverage": "EU TED(유럽 공공·유틸리티) · 영국 Find a Tender · 세계은행 낙찰 공고 · 바레인 입찰위원회 월간 낙찰 보고서 · 대만 정부조달(PCC)",
    }


def main():
    import private_store
    now = dt.datetime.now(KST)
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    previous = None
    if token:
        try:
            previous = private_store.get("overseas-awards", token)
        except private_store.StoreError as e:
            print(f"::warning title=overseas-awards-state::이전 상태 조회 실패({e}) — 이번 실행은 기준선")
    if private_store.late_scheduled_duplicate(previous, now):
        return
    doc = run(now=now, previous=previous)
    by = {}
    for c in doc["checks"]:
        s = by.setdefault(c["source"], [0, 0, 0])
        s[0] += c["status"] != "failed"
        s[1] += 1
        s[2] += c.get("matched") or 0
    new = [x for x in doc["items"] if x.get("isNew")]
    print(f"::notice title=overseas-awards::상태 {doc['status']} · " + " · ".join(f"{k} {a}/{b} 정상(일치 {m})" for k, (a, b, m) in by.items())
          + f" · 새 낙찰 {len(new)}(출입처 {sum(1 for x in new if x.get('company'))}) · 보관 {len(doc['items'])}")
    if not token:
        print("::warning title=overseas-awards-push::MCP_ACCESS_TOKEN 미설정 — 결과를 저장하지 않음")
        return
    if doc["status"] == "failed":
        sys.exit("해외 낙찰 원천 전체 조회 실패 — 이전 결과 유지(0건 아님)")
    status = private_store.put("overseas-awards", doc, token)
    print(f"::notice title=overseas-awards-push::기자 전용 저장소 전송 HTTP {status}")
    if status != 200:
        sys.exit(1)


if __name__ == "__main__":
    main()
