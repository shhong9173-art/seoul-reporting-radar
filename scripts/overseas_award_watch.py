"""해외 발주처 낙찰 공고 감시: 출입처(전력기기·전선·철강·에너지·자동차)가 해외 공공 발주처 입찰에서 낙찰자로 적힌 공고.

- EU TED(유럽 공공·유틸리티 조달): 낙찰 공고(can-*)의 낙찰자 이름·국가 필드. 한국 국적 낙찰자 전체 질의 1번 +
  출입처 영문명 질의(유럽 현지 법인 낙찰까지). 공고 전문 검색이 아니라 낙찰자 필드에 이름이 있어야 잡는다.
- 영국 Find a Tender(OCDS): 낙찰 단계 릴리스의 공급사 이름·주소 국가.
- 세계은행 조달 공고(Contract Award): 'Awarded Bidder(s)' 칸에 적힌 회사만. 탈락·평가 명단에 있는 이름은 버린다.
  (이라크·요르단·이집트·모로코 등 중동·북아프리카와 중앙아시아·남아시아 전력망 사업)
- 바레인 입찰위원회 월간 낙찰 보고서(PDF): 새 달 보고서에서 출입처 영문명이 나온 줄만.
- 바레인 입찰위원회 개찰 결과(Opened Tenders): 개찰 당일 공개되는 응찰 회사·응찰가·상태. 새 개찰마다 상세를 한 번 읽어
  출입처 응찰을 잡고 응찰가 순위를 붙인다(낙찰 아님). 10-30 탐침: 바레인 전력수도청(EWA) 4669/2025/5100 '400kV·220kV
  Feeder Cable Works(새 시트라 400kV 변전소)' 2026-04-13 개찰 — ILJIN ELECTRIC BHD 35,004,118.330, LS CABLE AND SYSTEM
  BHD 46,659,985.550, TAIHAN ELECTRIC WIRE 옵션1 BHD 45,648,300.000. 더구루는 개찰 나흘 뒤(04-17) '1500억 규모 3각 경쟁',
  10-20 '일진전기 최종 낙찰'([단독])을 냈다 — 레이더는 월간 보고서만 봐서 둘 다 못 잡았다.
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
import shutil
import subprocess
import sys
import tempfile
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


def _top_alternatives(rx):
    out, depth, cur = [], 0, ""
    for ch in rx:
        depth += ch == "("
        depth -= ch == ")"
        if ch == "|" and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    return out + [cur]


# 스캔 PDF 글자 인식(OCR)은 낱말 사이 띄어쓰기를 자주 잃는다(11-02 바레인 8월 보고서: 'ILJINELECTRIC COLTD'). 영문자만 남긴 줄에
# 두 낱말 이상 이름 규칙을 붙여 쓴 형태로 맞춘다. 짧은 약어(POSCO·KEPCO·LSIS·KHNP)는 붙여 쓴 글자 속 우연 일치가 많아 빼고 원래 규칙으로만 본다.
COMPACT_RX = [(ko, re.compile("|".join(a for a in (re.sub(r"\\s[+*]|\\b", "", x) for x in _top_alternatives(rx)) if len(re.sub(r"\W", "", a)) >= 8)))
              for ko, rx, _, _ in COMPANIES]
COMPACT_RX = [(ko, c) for ko, c in COMPACT_RX if c.pattern]


def beat_of_ocr(line):
    """글자 인식 줄: 원래 이름 규칙, 안 되면 띄어쓰기를 지운 형태로."""
    hit = beat_of(line)
    if hit:
        return hit
    flat = re.sub(r"[^a-z0-9&]", "", str(line or "").lower())
    for ko, rx in COMPACT_RX:
        if rx.search(flat):
            return ko
    return None
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
    "바레인 개찰 결과는 응찰가 공개일 뿐 낙찰이 아니다. 최저가 응찰도 기술 평가·협상으로 뒤집힐 수 있다 — '최저가 응찰'까지만 쓰고 낙찰은 입찰위원회 결정·월간 보고서·회사로 확인. 옵션 응찰은 가장 낮은 옵션 값으로 순위를 매긴다.",
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


# 바레인 월간 낙찰 보고서는 8·9월분이 스캔 이미지 PDF(글자 0자)다. 11-02 탐침: tesseract 5(영문)로 200dpi 14쪽 17~25초,
# 8월 보고서에서 'ILJINELECTRIC COLTD … SOUTH KOREA … 400KV and 220KV Feeder Cable Works for Establishment of New Sitra 400KV Grid
# Substations · 34,968,319.628'을 읽었다(아랍어 칸은 깨진 글자). 도구가 없으면(로컬 등) 예전처럼 '스캔 — 미확인'으로 남긴다.
OCR_DPI = 200
OCR_MAX_PAGES = 40
OCR_BUDGET = 300  # 초(실행당)


def ocr_pdf(raw, *, run=subprocess.run, which=shutil.which, budget=OCR_BUDGET, clock=time.monotonic):
    """(글자, 오류). pdftoppm으로 쪽 그림을 만들고 tesseract로 읽는다."""
    if not (which("pdftoppm") and which("tesseract")):
        return None, "글자 인식 도구 없음"
    started = clock()
    with tempfile.TemporaryDirectory() as d:
        pdf = os.path.join(d, "r.pdf")
        with open(pdf, "wb") as f:
            f.write(raw)
        r = run(["pdftoppm", "-r", str(OCR_DPI), "-gray", "-png", "-l", str(OCR_MAX_PAGES), pdf, os.path.join(d, "pg")],
                capture_output=True, timeout=budget)
        if r.returncode != 0:
            return None, "쪽 그림 변환 실패"
        pages, texts = sorted(f for f in os.listdir(d) if f.startswith("pg")), []
        for f in pages:
            left = budget - (clock() - started)
            if left <= 5:
                return ("\n".join(texts) or None), f"글자 인식 시간 상한({len(texts)}/{len(pages)}쪽)"
            out = run(["tesseract", os.path.join(d, f), "-", "--psm", "6"], capture_output=True, text=True, timeout=left)
            texts.append(out.stdout or "")
        return "\n".join(texts), None


MONTHS = {m: i for i, m in enumerate(("january", "february", "march", "april", "may", "june", "july", "august", "september",
                                       "october", "november", "december"), 1)}


def report_month(report):
    """'Awarded Tenders Report - August 2026 8.7 MB' → '2026-08'(보고서 달 — 낙찰 결정 달, 공고일 아님)."""
    m = re.search(r"\b(" + "|".join(MONTHS) + r")\s+(20\d\d)\b", str(report or ""), re.I)
    return f"{m.group(2)}-{MONTHS[m.group(1).lower()]:02d}" if m else None


# 바레인 디나르 금액은 소수 셋째 자리(필스)까지 적힌다: '34,968,319.628'. 글자 인식 줄에서 이 꼴(천 단위 쉼표 + 점 + 세 자리)만 금액으로 본다
# ('47.115.868'처럼 점으로 읽힌 것·쉼표만 있는 '9,564,000'은 옆 줄 다른 낙찰일 수 있어 쓰지 않는다).
BHD_AMOUNT = re.compile(r"(?<![\d.,])(\d{1,3}(?:,\d{3})+\.\d{3})(?![\d,])")


def ocr_amount(lines):
    """이름 줄과 바로 다음 줄에서 첫 BHD 금액."""
    for line in lines[:2]:
        m = BHD_AMOUNT.search(line)
        if m:
            return float(m.group(1).replace(",", ""))
    return None


def tidy_ocr_item(x):
    """예전 저장본(11-02 첫 OCR): 이름 줄 앞 두 줄(앞 낙찰의 끝)을 떼고, 발주처 문구·보고서 달을 지금 규칙으로."""
    if x.get("source") != "바레인 입찰위원회":
        return
    if x.get("buyer") == "바레인 정부 발주처(보고서 줄 참조)":
        x["buyer"] = "정부 발주처(보고서 줄 참조)"
    if not x.get("reportMonth") and report_month(x.get("report")):
        x["reportMonth"] = report_month(x.get("report"))
    if x.get("ocr") and x.get("company"):
        parts = str(x.get("title") or "").split(" / ")
        k = next((n for n, part in enumerate(parts) if beat_of_ocr(part)), 0)
        if k:
            x["title"] = " / ".join(parts[k:])
            parts = parts[k:]
        if x.get("value") is None:
            v = ocr_amount(parts)
            if v:
                x["value"], x["currency"], x["valueOcr"] = v, "BHD", True


def bh_items(text, report, href, *, ocr=False):
    out, seen = [], set()
    lines = [norm_space(x) for x in text.splitlines() if norm_space(x)]
    find = beat_of_ocr if ocr else beat_of
    beats = {i: b for i, b in ((i, find(line)) for i, line in enumerate(lines)) if b}
    hits = sorted(set(beats) | {i for i, line in enumerate(lines) if re.search(r"\bkorea\b", line, re.I)
                                and not any(abs(i - j) <= 2 for j in beats)})  # 이름 줄 옆 'SOUTH KOREA'(국적 칸)는 같은 낙찰
    month = report_month(report)
    for i in hits:
        beat = beats.get(i)
        # 글자 인식 줄은 앞줄이 대개 앞 낙찰(다른 회사)의 끝이라 이름 줄부터 뒤로 4줄(국적·금액·사업명이 이어짐)
        snippet = " / ".join(lines[i: i + 5] if ocr and beat else lines[max(0, i - 2): i + (4 if ocr else 2)])[:500 if ocr else 400]
        key = (beat, snippet[:120])
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "id": f"bh:{href.rsplit('/', 1)[-1]}:{len(out)}", "source": "바레인 입찰위원회", "published": None, "kind": "낙찰(월간 보고서)",
            "buyer": "정부 발주처(보고서 줄 참조)", "buyerCountry": "BHR", "winners": [], "winnerCountry": [], "winnerIds": [],
            "company": beat, "companies": [beat] if beat else [], "title": snippet, "report": report, "value": None, "currency": None,
            "concluded": None, "noticeType": "awarded-report", "url": BH_SITE + href.replace(" ", "%20"),
            **({"reportMonth": month} if month else {}), **({"ocr": True} if ocr else {}),
        })
        if ocr and beat:
            v = ocr_amount(lines[i: i + 2])
            if v:
                out[-1].update(value=v, currency="BHD", valueOcr=True)
    return out[:20]


def bahrain(previous_seen, *, get=None, ocr_done=None, ocr=None):
    try:
        r = _get(get, BH_LIST, headers={**UA, "Accept": "text/html"})
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}")
        reports = bh_reports(r.text)
        if not reports:
            raise RuntimeError("보고서 목록 형식 미상")
    except Exception as e:  # noqa: BLE001
        return [], [{"source": "바레인 입찰위원회", "query": "월간 낙찰 보고서", "status": "failed", "error": str(e)[:80] or type(e).__name__}], previous_seen, ocr_done
    # First run: older reports are remembered unread; only the newest one is read.
    seen = list(previous_seen) if previous_seen else [x["href"] for x in reports[1:]]
    # 글자 인식을 붙이기 전(ocr_done 없음)에 '스캔 — 미확인'으로 넘긴 최근 두 보고서는 한 번 다시 받아 읽는다(8·9월분).
    recheck = set() if ocr_done is not None else {x["href"] for x in reports[:2]}
    done = list(ocr_done or [])
    ocr = ocr_pdf if ocr is None else ocr
    items, checks = [], []
    for rep in reports[:2]:
        if rep["href"] in seen and rep["href"] not in recheck:
            continue
        try:
            pr = _get(get, BH_SITE + rep["href"].replace(" ", "%20"), headers={**UA, "Accept": "application/pdf"}, timeout=120)
            if pr.status_code != 200:
                raise RuntimeError(f"HTTP {pr.status_code}")
            if len(pr.content) > BH_MAX_BYTES:
                raise RuntimeError("파일이 너무 큼")
            text = pdf_text(pr.content)
            if rep["href"] not in seen:
                seen.append(rep["href"])
            scanned = len(text.strip()) < 500
            if scanned:
                # 10-29: August 2026 report (8.7MB) is a scanned image — 9 characters. 11-02부터 글자 인식(OCR)으로 읽는다.
                text, err = ocr(pr.content)
                if not text or len(text.strip()) < 500:
                    checks.append({"source": "바레인 입찰위원회", "query": rep["subject"], "status": "ok", "returned": 1, "matched": None,
                                   "note": f"스캔 이미지 PDF — 글자 인식 실패({err or '글자 적음'}), 이 보고서는 미확인(원문 직접 확인)",
                                   "url": BH_SITE + rep["href"].replace(" ", "%20")})
                    continue
                if rep["href"] not in done:
                    done.append(rep["href"])
            got = bh_items(text, rep["subject"], rep["href"], ocr=scanned)
            items += got
            checks.append({"source": "바레인 입찰위원회", "query": rep["subject"], "status": "ok", "returned": 1, "matched": len(got),
                           **({"note": f"스캔 이미지 PDF — 글자 인식(OCR)으로 읽음{' · ' + err if err else ''}. 이름·금액 오독 가능, 원문 확인"} if scanned else {})})
        except Exception as e:  # noqa: BLE001
            checks.append({"source": "바레인 입찰위원회", "query": rep["subject"], "status": "failed", "error": str(e)[:80] or type(e).__name__})
    if not checks:
        checks.append({"source": "바레인 입찰위원회", "query": "월간 낙찰 보고서", "status": "ok", "returned": len(reports), "matched": 0, "note": "새 보고서 없음"})
    return items, checks, seen[-60:], done[-24:]


# ---------------------------------------------------------------- Bahrain Tender Board opened bids (개찰 결과)
# 월간 낙찰 보고서는 두세 달 늦고(10-29 최신이 8월, 스캔 이미지) 일진전기 바레인 송전망(더구루 10-20 '최종 낙찰')도 없었다.
# 입찰위원회 누리집의 '개찰 결과'(Opened Tenders)는 개찰 당일 응찰 회사 이름·응찰가·상태를 공개한다(10-30 탐침, robots.txt 없음).
# 개찰은 낙찰이 아니다: 최저가 응찰까지만 잡고 낙찰 여부는 입찰위원회 결정·월간 보고서·회사로 확인한다.
BH_OPEN_API = BH_SITE + "/Templates/TenderBoardWebService.aspx/GetOpenedTenderF"
BH_OPEN_SOURCE = "바레인 입찰위원회 개찰"
BH_OPEN_PAGES = 4         # 실행당 목록 쪽수(쪽당 10건, 최신순)
BH_OPEN_FIRST_PAGES = 12  # 첫 실행
BH_OPEN_DETAIL_MAX = 40   # 실행당 새 개찰 상세 읽기 상한(남은 것은 다음 실행에)
BH_OPEN_GAP = 1.0
BH_OPEN_ROW = re.compile(r"""<div data-ref=['"](\d+)['"] class=['"]rows['"]>(.*?)(?=<div data-ref=|$)""", re.S)
BH_OPEN_COL = re.compile(r"""<div class=['"]column['"][^>]*>(.*?)</div>""", re.S)
BH_ROWS_SPLIT = re.compile(r"""<div class=['"]rows['"]>""")
BH_CELL = r"""data-label=['"]{}['"]>(.*?)</div>"""
BH_AMOUNT = re.compile(r"\b([A-Z]{3})\s*([\d,]+(?:\.\d+)?)")
BH_OPEN_A_BHD = 1_000_000  # 약 265만 달러
BH_TO_BHD = {"BHD": 1, "USD": 0.376, "EUR": 0.41, "GBP": 0.48, "SAR": 0.1, "AED": 0.102}
BH_OUT = re.compile(r"reject|withdr|disqual|exclud|not\s+accept|cancel", re.I)


def _bh_payload(page):
    # 빈 문자열을 category·tendertype·sortingType에 넣으면 서버가 SQL 오류를 낸다(10-30 탐침) — '0'이 기본값.
    return {"tenderNumber": "", "ministry": "", "category": "0", "tendertype": "0", "openedDate_filter": "", "endDate_filter": "",
            "sortingType": "0", "pageIndex": str(page), "sectionName": ""}


def bh_open_rows(d):
    """GetOpenedTenderF 응답의 d(XML 안에 HTML이 엔터티로 들어 있음) → 개찰 목록 줄."""
    c = re.search(r"<Content>(.*?)</Content>", d or "", re.S)
    content = htmlmod.unescape(c.group(1)) if c else ""
    rows = []
    for ref, block in BH_OPEN_ROW.findall(content):
        cols = [norm_space(htmlmod.unescape(re.sub(r"<[^>]+>", " ", x))) for x in BH_OPEN_COL.findall(block)]
        no = re.search(r"<span>(.*?)</span>", block, re.S)
        href = re.search(r"""href=['"]([^'"]+)['"]""", block)
        if len(cols) < 5 or not href:
            continue
        tender_no = norm_space(htmlmod.unescape(re.sub(r"<[^>]+>", " ", no.group(1)))) if no else ""
        subject = cols[1]
        if tender_no and subject.startswith(tender_no):
            subject = subject[len(tender_no):].strip()
        try:
            opened = dt.datetime.strptime(cols[3].replace(" ", ""), "%d%b,%Y").date().isoformat()
        except ValueError:
            opened = None
        bids = re.sub(r"\D", "", cols[5]) if len(cols) > 5 else ""
        rows.append({"ref": ref, "tenderNo": tender_no, "subject": subject, "tenderType": cols[2], "opened": opened,
                     "authority": cols[4], "bids": int(bids) if bids else None, "href": htmlmod.unescape(href.group(1))})
    return rows


def _bh_text(s):
    return norm_space(htmlmod.unescape(re.sub(r"<[^>]+>", " ", s or "")))


def bh_bidders(html):
    """개찰 상세의 응찰 표: 회사 이름·응찰가(옵션이 여럿이면 모두)·상태. 10-30 탐침 형식:
    <div class='rows'>…data-label='Bidder Name'>회사</div><div class='column bidvalue' data-label='Bidder Value'><span>BHD 1.000</span>
    (옵션 응찰은 <div>(Opt. 1) <span>BHD …</span></div><div>(Opt. 2) …)… data-label='Status'>Accepted</div></div>"""
    out = []
    for block in BH_ROWS_SPLIT.split(html or "")[1:]:
        name = re.search(BH_CELL.format("Bidder Name"), block, re.S)
        if not name:
            continue
        status = re.search(BH_CELL.format("Status"), block, re.S)
        start = block.find("Bidder Value")
        stop = min([i for i in (block.find("Remarks", start), block.find("Status", start)) if i > 0] or [len(block)])
        amounts = []
        for cur, num in BH_AMOUNT.findall(_bh_text(block[start:stop])) if start >= 0 else []:
            try:
                amounts.append((float(num.replace(",", "")), cur))
            except ValueError:
                pass
        curs = {c for _, c in amounts}
        low = min(amounts) if amounts and len(curs) == 1 else (amounts[0] if amounts else (None, None))
        out.append({"name": _bh_text(name.group(1)), "value": low[0], "currency": low[1], "options": len(amounts),
                    "status": _bh_text(status.group(1)) if status else ""})
    return out


def bh_open_items(row, bidders):
    """출입처(또는 이름에 Korea가 든 회사) 응찰마다 한 줄. 응찰가 순위는 같은 통화·탈락 아닌 응찰 안에서만(옵션 응찰은 가장 낮은 값)."""
    priced = [b for b in bidders if b["value"] is not None and not BH_OUT.search(b["status"] or "")]
    one_cur = len({b["currency"] for b in priced}) == 1
    order = sorted(priced, key=lambda b: b["value"]) if one_cur else []
    env = re.search(r"envelope=([A-Za-z]+)", row["href"])
    out = []
    for b in bidders:
        beat = beat_of(b["name"])
        if not beat and not KOREA_RX.search(b["name"]):
            continue
        ranked = one_cur and any(o is b for o in priced)
        rank = 1 + sum(1 for o in priced if o["value"] < b["value"]) if ranked else None
        low = order[0] if order and order[0] is not b and rank != 1 else None
        out.append({
            "id": f"bhopen:{row['ref']}:{beat or b['name'][:30]}", "source": BH_OPEN_SOURCE, "published": row["opened"], "kind": "개찰(응찰)",
            "buyer": row["authority"] or "바레인 정부 발주처", "buyerCountry": "BHR", "winners": [], "winnerCountry": [], "winnerIds": [],
            "company": beat, "companies": [beat] if beat else [], "title": f"{row['tenderNo']} {row['subject']}".strip()[:300],
            "bidder": b["name"], "bidStatus": b["status"], "value": b["value"], "currency": b["currency"], "options": b.get("options") or 0,
            "rank": rank, "priced": len(priced) if ranked else None, "bidCount": len(bidders) or row.get("bids"), "lowest": rank == 1,
            "others": [{"name": o["name"], "value": o["value"]} for o in order if o is not b][:3],
            "lowestBid": {"name": low["name"], "value": low["value"]} if low else None,
            "tenderType": row["tenderType"], "envelope": env.group(1).upper() if env else None, "concluded": None,
            "noticeType": "opened-bids", "url": BH_SITE + row["href"].replace(" ", "%20"),
        })
    return out


def bahrain_opened(previous_seen, *, get=None, post=None, sleep=time.sleep):
    first = previous_seen is None
    seen = list(previous_seen or [])
    rows, checks = [], []
    pages = BH_OPEN_FIRST_PAGES if first else BH_OPEN_PAGES
    for page in range(1, pages + 1):
        try:
            if post is None:
                import requests
                post = requests.post
            r = post(BH_OPEN_API, data=json.dumps(_bh_payload(page)), timeout=60,
                     headers={**UA, "Content-Type": "application/json; charset=utf-8", "X-Requested-With": "XMLHttpRequest"})
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")
            got = bh_open_rows(r.json().get("d"))
            if not got and page == 1:
                raise RuntimeError("목록 형식 미상(0줄)")
        except Exception as e:  # noqa: BLE001
            checks.append({"source": BH_OPEN_SOURCE, "query": f"개찰 목록 {page}쪽", "status": "failed", "error": str(e)[:80] or type(e).__name__})
            break
        if not got:  # 목록 끝
            break
        have = {x["ref"] for x in rows}
        rows += [x for x in got if x["ref"] not in have]  # 쪽을 넘기는 사이 새 개찰이 붙으면 같은 줄이 다음 쪽에 또 나온다
        if page < pages:
            sleep(BH_OPEN_GAP)
    if not rows:
        return [], checks, previous_seen
    fresh = [x for x in rows if x["ref"] not in seen]
    items, read, errors = [], 0, []
    for row in fresh[:BH_OPEN_DETAIL_MAX]:
        try:
            r = _get(get, BH_SITE + row["href"].replace(" ", "%20"), headers={**UA, "Accept": "text/html"})
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")
            bidders = bh_bidders(r.text)
            if not bidders and "Bidder Name" not in r.text and (row.get("bids") or 0) > 0:
                raise RuntimeError("응찰 표 형식 미상")
            items += bh_open_items(row, bidders)
            seen.append(row["ref"])
            read += 1
        except Exception as e:  # noqa: BLE001
            errors.append(f"{row['tenderNo'] or row['ref']}({str(e)[:40] or type(e).__name__})")
        sleep(BH_OPEN_GAP)
    left = len(fresh) - read - len(errors)
    if first:  # 첫 실행: 상한 밖 예전 개찰은 읽지 않고 기억만 한다(다음 실행에 새 소식으로 나오지 않게)
        seen += [x["ref"] for x in fresh if x["ref"] not in seen]
    status = "partial" if errors or checks else "ok"
    note = [f"목록 {len(rows)}건(개찰 {rows[-1]['opened'] or '?'}~{rows[0]['opened'] or '?'}) · 새 개찰 {len(fresh)} · 상세 {read}"]
    if left > 0:
        note.append(f"첫 실행 기준선 — 예전 개찰 {left}건은 읽지 않음" if first else f"남은 {left}건은 다음 실행에")
    if errors:
        note.append(f"상세 미확인 {len(errors)}: {', '.join(errors[:3])}")
    checks.append({"source": BH_OPEN_SOURCE, "query": "개찰 결과(응찰 회사·응찰가)", "status": status, "returned": len(rows),
                   "matched": len(items), "note": " · ".join(note)})
    return items, checks, seen[-600:]


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
PCC_GAP = 2.0        # 호출 사이 대기(10-30 탐침: 대기 없이 11번 부르자 HTTP 429)
PCC_EVERY_HOURS = 20  # 하루 한 번(아침 실행). 오후 실행은 건너뛴다


class RateLimited(RuntimeError):
    pass


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
        if re.search(r"契約變更", str(b.get("title") or "")):
            kind = "계약 변경"  # 결정 공고라도 제목이 'N차 계약 변경'이면 새 수주가 아니다(10-30 탐침: 臺鐵 SJ01 號誌 第1次契約變更)
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
    if r.status_code == 429:
        raise RateLimited("HTTP 429")
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
        if item_name and item_name == norm_space(item.get("title")):
            item_name = ""  # 품목이 하나면 품목명이 공고 제목과 같다(10-30 실제 공고)
        total += amt or 0
        lines.append(f"{m.group(1)}번 품목{f' {item_name}' if item_name else ''} {v} NT${amt:,}" if amt else f"{m.group(1)}번 품목 {v} 금액 미기재")
        if origin:
            lines[-1] += f"(원산지 {origin})"
    return {"lines": lines, "beatTotal": total or None, "concluded": roc_date(det.get("決標資料:決標日期")),
            "category": norm_space(det.get("採購資料:標的分類"))[:80] or None}


def pcc(since, previous_ids, *, get=None, sleep=time.sleep):
    """미러 호출 제한(429)이 오면 이번 실행의 나머지 검색·상세는 하지 않는다(다시 부르지 않음, 남은 검색은 미확인)."""
    items, checks, since_day = {}, [], since.date().isoformat()
    limited = False
    for i, (ko, term) in enumerate(PCC_TERMS):
        if limited:
            checks.append({"source": PCC_SOURCE, "query": f"{ko}({term})", "status": "failed", "error": "HTTP 429 뒤 이번 실행 중단"})
            continue
        if i:
            sleep(PCC_GAP)
        try:
            r = _get(get, PCC_SEARCH, params={"query": term})
            if r.status_code == 429:
                limited = True
                raise RuntimeError("HTTP 429")
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
    read = 0
    for it in sorted(items.values(), key=lambda x: x["published"], reverse=True):
        if it["id"] in previous_ids:
            continue
        if limited or read >= PCC_DETAIL_MAX:
            it["detailError"] = "HTTP 429(상세 다음에)" if limited else "상세 상한(다음에)"
            continue
        read += 1
        sleep(PCC_GAP)
        try:
            d = pcc_detail(it, get=get)
            if d["lines"]:
                it["title"] = f"{it['title']} — {' · '.join(d['lines'])}"[:400]
            if d["beatTotal"]:
                it["value"], it["priceKind"] = d["beatTotal"], "출입처 낙찰 품목 결정 금액 합"
            it["concluded"], it["category"] = d["concluded"], d["category"]
        except RateLimited:
            limited = True
            it["detailError"] = "HTTP 429(상세 다음에)"
        except Exception as e:  # noqa: BLE001 — 상세 실패는 목록 값만 남긴다
            it["detailError"] = str(e)[:60] or type(e).__name__
    return list(items.values()), checks


# ---------------------------------------------------------------- run
def tier_of(it):
    if not it.get("company"):
        return "C"
    if it.get("kind") == "계약 변경" or it.get("source") == "바레인 입찰위원회":
        return "B"
    if it.get("source") == BH_OPEN_SOURCE:
        # 개찰은 낙찰이 아니다. 출입처가 최저가로 응찰한 큰 입찰(약 100만 BHD 이상)만 A, 그 밖의 출입처 응찰은 B.
        bhd = (it.get("value") or 0) * BH_TO_BHD.get(it.get("currency") or "", 0)
        return "A" if it.get("lowest") and bhd >= BH_OPEN_A_BHD else "B"
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


BH_REF = re.compile(r"\b\d{2,6}/\d{4}/\d{2,6}\b")


def link_bahrain_reports(reports, pool):
    """월간 낙찰 보고서 줄의 입찰 번호가 앞서 잡은 개찰(응찰가 공개)과 같으면 그 개찰을 붙인다. 보고서는 번호 순서가 거꾸로다
    (8월 보고서 '5100/2025/4669' = 개찰 '4669/2025/5100' 일진전기 최저가 BHD 35,004,118 → 보고서 34,968,319.628)."""
    opened = {}
    for x in pool:
        if isinstance(x, dict) and x.get("source") == BH_OPEN_SOURCE and x.get("company"):
            for ref in BH_REF.findall(str(x.get("title") or "")[:40]):
                opened.setdefault(tuple(sorted(ref.split("/"))), []).append(x)
    for it in reports:
        if not it.get("company"):
            continue
        for ref in BH_REF.findall(it.get("title") or ""):
            same = [x for x in opened.get(tuple(sorted(ref.split("/"))), []) if x.get("company") == it["company"]]
            if same:
                o = same[0]
                money = f"{o['currency']} {o['value']:,.0f}" if o.get("value") and o.get("currency") else "응찰가 미공개"
                it["openedBid"] = {"id": o.get("id"), "published": o.get("published"), "rank": o.get("rank"), "priced": o.get("priced"),
                                   "value": o.get("value"), "currency": o.get("currency")}
                rank = f" · 응찰가 {o['rank']}위/{o.get('priced') or '?'}곳" if o.get("rank") else ""
                it["title"] = (f"{it['title']} ‖ 같은 입찰의 개찰 기록: {o.get('published') or '?'} {o.get('bidder') or it['company']} {money}{rank}"
                               " — 월간 낙찰 보고서에 실림")
                break


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
    bh_got, bh_checks, bh_seen, bh_ocr = bahrain((previous or {}).get("bahrainSeen"), get=get,
                                                 ocr_done=(previous or {}).get("bahrainOcr") if previous else [])
    found += bh_got
    checks += bh_checks
    open_prev = (previous or {}).get("bahrainOpenSeen")
    bo_got, bo_checks, bo_seen = bahrain_opened(open_prev, get=get, post=post, sleep=sleep)
    open_first = open_prev is None  # 이 원천의 첫 실행: 이미 개찰된 것은 기준선(새 소식 아님)
    for it in bo_got:
        it["_first"] = open_first
    found += bo_got
    checks += bo_checks
    known = {x.get("id") for x in (previous or {}).get("items") or []
             if isinstance(x, dict) and not re.search(r"다음에", str(x.get("detailError") or ""))}  # 429·상한으로 못 읽은 상세는 다음 실행에
    pcc_last = (previous or {}).get("pccLastRun")
    try:
        pcc_due = not pcc_last or (now - dt.datetime.fromisoformat(pcc_last)).total_seconds() >= PCC_EVERY_HOURS * 3600
    except (TypeError, ValueError):
        pcc_due = True
    if pcc_due:
        pcc_got, pcc_checks = pcc(since if pcc_last else max(since, now - dt.timedelta(days=BASELINE_DAYS)), known, get=get, sleep=sleep)
        pcc_last = stamp
    else:
        pcc_got, pcc_checks = [], [{"source": PCC_SOURCE, "query": "출입처 이름 검색", "status": "ok", "returned": 0, "matched": 0,
                                    "note": f"하루 한 번(마지막 {str(pcc_last)[:16]}) — 이번 실행은 건너뜀"}]
    old_by = {x.get("id"): x for x in (previous or {}).get("items") or [] if isinstance(x, dict)}
    for it in pcc_got:  # 상세는 처음 볼 때만 읽으니, 다시 잡힌 공고는 저장된 상세(금액·결정일)를 그대로 쓴다(이번에 다시 읽은 것은 제외)
        o = old_by.get(it["id"]) if it["id"] in known else None
        if o:
            for k in ("title", "value", "priceKind", "concluded", "category", "detailError"):
                if k in o:
                    it[k] = o[k]
    found += pcc_got
    checks += pcc_checks
    old = {x["id"]: x for x in (previous or {}).get("items") or []}
    for x in old.values():
        tidy_ocr_item(x)
    link_bahrain_reports(bh_got, list(old.values()) + bo_got)
    items = dict(old)
    for it in found:
        prev = old.get(it["id"])
        first = baseline or it.pop("_first", False)
        it["firstSeen"] = prev["firstSeen"] if prev else stamp
        it["baseline"] = bool(prev.get("baseline")) if prev else first
        it["isNew"] = not prev and not first
        it["tier"] = tier_of(it)
        items[it["id"]] = it
    found_ids = {i["id"] for i in found}
    for k, x in list(items.items()):
        if k not in found_ids:
            x["isNew"] = False
            # stored items follow the current name and tier rules (e.g. a company dropped from the beat list)
            if x.get("source") == BH_OPEN_SOURCE:
                beat = beat_of(x.get("bidder"))
                x["company"], x["companies"] = beat, [beat] if beat else []
            elif x.get("source") != "바레인 입찰위원회":
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
        "checks": checks, "items": kept[:KEEP_MAX], "bahrainSeen": bh_seen, "bahrainOcr": bh_ocr, "bahrainOpenSeen": bo_seen, "pccLastRun": pcc_last, "rules": RULES,
        "coverage": "EU TED(유럽 공공·유틸리티) · 영국 Find a Tender · 세계은행 낙찰 공고 · 바레인 입찰위원회 월간 낙찰 보고서·개찰 결과 · 대만 정부조달(PCC)",
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
