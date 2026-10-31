"""단독 후보 자동 심사: 레이더 단서·수치 변화의 기보도 여부를 네이버·빙·구글로 대조한다.

결과는 공개 저장소에 쓰지 않는다. 기자 전용 커넥터 저장소(Cloudflare Durable Object)로만 보낸다.
로그(공개)에는 건수만 남긴다.

판정(후보별)
- 같은 수치 선행: 기업·사건 낱말·수치 단위·기간이 함께 일치한 기사다(동일 사건 최종 확인 필요).
- 관련 보도 있음: 회사명과 핵심 낱말이 함께 나온 기사가 있다(같은 사건인지는 열어 봐야 한다).
- 미보도 후보: 네이버와 웹 색인(빙 또는 구글)이 모두 정상 응답했고 관련 기사가 없다.
  검색 범위 안에서 못 찾았다는 뜻이지 미보도 증거나 단독 판정이 아니다.
- 미확인: 채널 조회 실패·미설정. 0건이 아니다.
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
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote, parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

KST = dt.timezone(dt.timedelta(hours=9))
WORKER = "https://seoul-reporting-radar.shhong9173.workers.dev"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
SCHEMA = "scoop_screen/v1"
MAX_CANDIDATES = 45
WINDOW_DAYS = 365

# Display/common names → aliases used in articles.
ALIASES = {
    "현대차": ["현대차", "현대자동차"], "기아": ["기아"], "현대모비스": ["현대모비스"], "현대위아": ["현대위아"],
    "HL만도": ["HL만도", "만도"], "KG모빌리티": ["KG모빌리티", "KGM"], "한국타이어": ["한국타이어", "한국타이어앤테크놀로지"],
    "넥센타이어": ["넥센타이어"], "금호타이어": ["금호타이어"], "포스코홀딩스": ["포스코홀딩스"], "포스코": ["포스코"],
    "현대제철": ["현대제철"], "KG스틸": ["KG스틸"], "세아홀딩스": ["세아홀딩스"], "세아제강": ["세아제강"],
    "동국제강": ["동국제강"], "동국씨엠": ["동국씨엠"], "고려아연": ["고려아연"], "영풍": ["영풍"],
    "HD현대일렉트릭": ["HD현대일렉트릭", "현대일렉트릭"], "LS일렉트릭": ["LS일렉트릭", "LS ELECTRIC", "엘에스일렉트릭"],
    "대한전선": ["대한전선"], "LS전선": ["LS전선"], "LS지주": ["LS지주", "(주)LS", "㈜LS", "LS"], "LS MnM": ["LS MnM", "LS엠앤엠"],
    "두산에너빌리티": ["두산에너빌리티"], "GS": ["(주)GS", "㈜GS", "GS"], "GS칼텍스": ["GS칼텍스"],
    "한화솔루션": ["한화솔루션"], "OCI": ["OCI"], "OCI홀딩스": ["OCI홀딩스"], "태광": ["태광"],
    "동성케미칼": ["동성케미칼", "동성케미컬"], "DL케미칼": ["DL케미칼"], "효성중공업": ["효성중공업"], "일진전기": ["일진전기"],
}
LEGAL = {"현대자동차": "현대차", "엘에스일렉트릭": "LS일렉트릭", "한국타이어앤테크놀로지": "한국타이어", "LS": "LS지주"}
BOILER = re.compile(
    r"정기·주요공시|주요사항보고서|공정공시|안내공시|자율공시|자회사의\s*주요경영사항|종속회사의\s*주요경영사항|"
    r"기재정정|첨부정정|발행조건확정|연결재무제표기준|공식|동일기간|단위|숫자|공시상|원문|보고서|결정|체결|변경|관련|"
    r"사업의\s*내용|분기|반기|누적|전년|대비|기준|현황|정보|제출|기업|계획|PBR\s*개선|주요|단일판매ㆍ공급계약|"
    r"단일판매·공급계약|특수관계인(?:에대한|으로부터)?|대량보유\(5%\)|임원·주요주주")
STOP = {"공급계약", "공시", "회사", "국내", "해외", "기타", "합계", "제품", "사업", "부문", "대한", "관한", "통해",
        "에서", "으로", "그리고", "보고", "건", "등", "및", "의", "수", "약", "총", "이를", "위한", "통한", "있는", "하는",
        "따른", "대해", "관련된", "포함", "이상", "이하", "경우", "방법", "장치", "시스템"}
# Procedural or always-covered filings are not scoop candidates (first real run, 10/26: 특수관계인 거래·
# 공정거래 자율준수·밸류업 계획·대표 변경이 '미보도 후보'로 올라왔다).
ADMIN = re.compile(r"특수관계인|공정거래자율준수|기업설명회|IR\)?개최|주주총회|최대주주등소유주식|자기주식취득결과|"
                   r"증권발행실적|투자설명서|기업지배구조보고서|감사보고서|결산실적공시예고|조회공시|풍문|매매거래정지|"
                   r"발행조건확정|증권신고서|영업\(잠정\)실적|잠정\)?실적|기업가치제고|대표이사|대표집행임원|사외이사|"
                   r"주식소각|자기주식처분|자기주식취득|배당|정관변경|명의개서|전환가액|신주인수권|"
                   # 10-30 radar_today A에 매일 올라온 형식 공시: 공정거래법 계열사 상품·용역거래 이사회 의결, 주총 의결권 권유,
                   # 실적 발표와 함께 나오는 실적 전망 공정공시(정정 포함), 기업집단 현황
                   r"동일인등출자계열회사|상품ㆍ?용역거래|의결권대리행사권유|영업실적등에대한전망|기업집단현황|"
                   # 금융 계열사와의 약관 거래 상대방 공시(공정거래법 정기 형식, 10-29 현대차·현대모비스)
                   r"약관에의한금융거래")
# Disclosure vocabulary → words news headlines actually use (queries use the first, matching accepts all).
NEWS_TERMS = {
    "중대재해발생": ["중대재해", "사망", "사고"], "중대재해": ["중대재해", "사망", "사고"],
    "영업양도": ["영업양도", "양도", "매각"], "생산중단": ["생산 중단", "가동 중단", "생산중단"],
    "회사분할": ["분할"], "회사합병": ["합병"], "타법인주식및출자증권취득": ["지분 인수", "인수", "취득"],
    "유형자산취득": ["투자", "취득", "증설"], "유형자산처분": ["매각", "처분"], "신규시설투자": ["투자", "증설"],
    "단일판매ㆍ공급계약체결": ["수주", "공급계약"], "공급계약": ["수주", "공급계약"],
}
PATENT_SOURCES = re.compile(r"KIPRIS|특허", re.I)
PARTICLE = re.compile(r"(으로|에서|에게|까지|부터|의|을|를)$")  # only unambiguous endings (양도·원가·회로 stay intact)
ACRONYM = re.compile(r"[A-Z][A-Z0-9&]{1,5}")


def now_kst():
    return dt.datetime.now(KST)


def canon(name):
    name = str(name or "").strip()
    return LEGAL.get(name, name)


def aliases(company):
    return ALIASES.get(company, [company])


# ---------- numbers ----------

def num_forms(value, unit=""):
    """Ways an article might print the same number (exact-ish; no rounding to round thousands)."""
    try:
        n = float(str(value).replace(",", ""))
    except ValueError:
        return set()
    forms = set()
    if n != int(n):
        forms.add(f"{n:g}")
        return forms
    n = int(abs(n))
    if n < 100:
        return forms  # too common to be evidence
    if unit in ("백만원", "백만 원"):
        eok = n / 100  # 억원
        for v in {int(eok), int(round(eok))}:
            if v >= 10000:
                jo, rest = divmod(v, 10000)
                forms |= {f"{jo}조{rest}억", f"{jo}조 {rest}억", f"{jo}조{rest:,}억", f"{jo}조 {rest:,}억"} if rest else {f"{jo}조"}
                forms.add(f"{v / 10000:.1f}조")
            elif v >= 1:
                forms |= {f"{v}억", f"{v:,}억"}
        return {f for f in forms if f}
    forms |= {f"{n:,}", str(n)}
    if n >= 10000:
        man, rest = divmod(n, 10000)
        forms |= {f"{man}만{rest}", f"{man}만 {rest}"} if rest else {f"{man}만"}
        if rest and rest % 1000 == 0:
            forms.add(f"{man}만{rest // 1000}천")
    return forms


def ratio_forms(prior, current):
    try:
        a, b = float(prior), float(current)
    except (TypeError, ValueError):
        return set()
    if a <= 0 or b <= 0:
        return set()
    pct = (b - a) / a * 100
    forms = {f"{abs(pct):.1f}%"}
    if b / a >= 1.5:
        forms |= {f"{b / a:.1f}배"}
        if 1.95 <= b / a <= 2.05:
            forms |= {"두 배", "2배"}
    return forms


# ---------- candidates ----------

def terms_from(text, company):
    t = html.unescape(str(text or ""))
    for a in aliases(company) + [company] + list(LEGAL):
        t = t.replace(a, " ")
    t = BOILER.sub(" ", t)
    t = re.sub(r"[\[\](){}<>·ㆍ—\-–/,:;|~→+%=\"'“”‘’…]", " ", t)
    words = []
    for w in t.split():
        w = w.strip(".")
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9&.]*", w) and not ACRONYM.fullmatch(w):
            continue  # English prose words never match Korean headlines; acronyms (HMTR, HVDC, ESS) do
        if re.search(r"[가-힣]", w) and len(w) >= 3:
            w = PARTICLE.sub("", w)
        if len(w) < 2 or w in STOP or re.fullmatch(r"[\d.,]+[a-zA-Z가-힣]{0,2}", w) or re.fullmatch(r"\d{4}", w):
            continue
        if w not in words:
            words.append(w)
    # Korean words first: Korean headlines rarely use plant codes (HMTR) or acronyms alone.
    words.sort(key=lambda w: 0 if re.search(r"[가-힣]", w) else 1)
    return words[:4]


def news_terms(terms):
    """Replace disclosure jargon with headline words; keep alternatives for matching."""
    out, alts = [], {}
    for t in terms:
        key = next((k for k in NEWS_TERMS if k in t), None)
        if key:
            words = NEWS_TERMS[key]
            out.append(words[0])
            alts[words[0]] = words
        else:
            out.append(t)
    return list(dict.fromkeys(out)), alts


def from_clue(x):
    companies = [canon(c) for c in x.get("companies") or [] if c]
    if not companies:
        return None
    if ADMIN.search(str(x.get("title") or "")):
        return None
    company = companies[0]
    title = str(x.get("title") or "")
    nums, unit = set(), ""
    m = re.search(r"숫자\s*([\d,]+)\s*→\s*([\d,]+)\s*\(([^)]*)\)", title)
    if m:
        unit = m.group(3).strip()
        nums |= num_forms(m.group(1), unit) | num_forms(m.group(2), unit)
        ratios = ratio_forms(m.group(1).replace(",", ""), m.group(2).replace(",", ""))
        body = title[:m.start()]
    else:
        body, ratios = title, set()
    terms, alts = news_terms(terms_from(body, company))
    patent = bool(PATENT_SOURCES.search(str(x.get("source") or "")))
    return {"id": f"clue:{x.get('id')}", "kind": "특허" if patent else "단서", "team": x.get("team"), "company": company,
            "title": title, "url": x.get("url"), "published": x.get("published"), "source": x.get("source"),
            "tier": x.get("tier"), "terms": terms, "alts": alts, "unit": unit, "numbers": sorted(nums), "ratios": sorted(ratios),
            "note": "특허 공개는 그 자체로 단독이 아니다 — 사업화·생산·수주 연결 확인 필요" if patent else None,
            "strength": 0.5 if patent else (3 if x.get("tier") == "취재 단서·단독 미확정" else 1)}


def from_stat(x):
    company = canon(x.get("company"))
    if not company:
        return None
    unit = str(x.get("unit") or "")
    nums = num_forms(x.get("current"), unit) | num_forms(x.get("prior"), unit)
    label = str(x.get("label") or "")
    urls = x.get("sourceUrls") or []
    return {"id": f"stat:{x.get('id')}", "kind": "수치", "team": x.get("team"), "company": company,
            "title": f"{label} · {x.get('period', '')} {x.get('prior')}→{x.get('current')} {unit} ({x.get('changePercent')}%)",
            "url": urls[-1] if urls else None, "published": None, "source": x.get("source"), "tier": "수치 변화",
            "terms": terms_from(label, company), "unit": unit, "period": str(x.get("period") or ""), "numbers": sorted(nums),
            "ratios": sorted(ratio_forms(x.get("prior"), x.get("current"))),
            "strength": min(4, float(x.get("strength") or 0) / 40)}


STALE_DAYS = 45


def filed_on(url):
    m = re.search(r"rcpNo=(\d{4})(\d{2})(\d{2})\d{6}", str(url or ""))
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def age_mark(c, now):
    """Half-year/annual table numbers lose their news hook with time: halve the weight and label the age."""
    day = c.get("published") or filed_on(c.get("url"))
    c["filedOn"] = filed_on(c.get("url"))
    if not day:
        return c
    age = (now.date() - dt.date.fromisoformat(day)).days
    if age > STALE_DAYS:
        c["staleDays"] = age
        c["strength"] = c["strength"] / 2
    return c


def select(clues, stats, *, now, limit=MAX_CANDIDATES):
    recent = (now - dt.timedelta(days=10)).strftime("%Y-%m-%d")
    rows = []
    for x in clues.get("items", []) if isinstance(clues, dict) else []:
        if not isinstance(x, dict) or x.get("routine"):
            continue
        strong = x.get("tier") == "취재 단서·단독 미확정"
        fresh = (x.get("published") or "") >= recent
        if not (strong or fresh):
            continue
        c = from_clue(x)
        if c and c["terms"]:
            c["strength"] += 1 if fresh else 0
            rows.append(c)
    for x in stats.get("items", []) if isinstance(stats, dict) else []:
        if not isinstance(x, dict) or float(x.get("strength") or 0) < 60:
            continue
        c = from_stat(x)
        if c and c["terms"]:
            rows.append(c)
    rows = [age_mark(c, now) for c in rows]
    seen, out = set(), []
    for c in sorted(rows, key=lambda r: -r["strength"]):
        key = (c["company"], tuple(c["numbers"])) if c["numbers"] else (c["company"], tuple(c["terms"][:2]))
        if is_lawsuit(c):
            key=(c["company"],c.get("url") or c["id"])
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out[:limit]


def lead(terms):
    """The more specific of the first two terms (longer Korean word wins)."""
    korean = [t for t in terms[:2] if re.search(r"[가-힣]", t)]
    pool = korean or terms[:1]
    return max(pool, key=len) if pool else None


# Lawsuit filings name the case and the outcome; headlines use those words, not the filing type
# (운영 10-28: '고려아연 소송등의판결'로 찾아 '미보도 후보' — 같은 날 '주주대표소송 1심 기각' 속보가 여러 건 있었다).
OUTCOME_WORDS = ["기각", "각하", "인용", "승소", "패소", "판결", "선고"]

CASE_NUMBER = re.compile(r"(?<!\d)(20\d{2})\s*(가합|가단|가소|카합|카단|구합|구단|나|다|누|두|허|마)\s*(\d{2,9})(?!\d)")


def case_numbers(text):
    return {"".join(m.groups()) for m in CASE_NUMBER.finditer(str(text or ""))}


def is_lawsuit(c):
    return ((c.get("filing") or {}).get("type") in ("소송판결", "소송제기")
            or bool(re.search(r"소송\s*등의\s*(?:판결|제기)", c.get("title", ""))))


def case_identity(c):
    f=c.get("filing") or {}
    got=dict(f.get("facts") or [])
    numbers=case_numbers(got.get("사건번호")) if not f.get("error") else set()
    plaintiff=re.split(r"원고공동|공동소송|피고|신청인",got.get("원고ㆍ신청인", ""))[0]
    plaintiff=re.sub(r"^(?:원고\s*[:：]?\s*)?(?:주식회사\s*|\(주\)\s*)?", "", plaintiff).strip()
    if not re.fullmatch(r"[A-Za-z가-힣][A-Za-z가-힣0-9 ]{1,60}",plaintiff):
        plaintiff=""
    return numbers,plaintiff


def lawsuit_terms(c):
    """(terms, alts) from the filing's own case name and outcome, or None when this is not a lawsuit filing."""
    f = c.get("filing") or {}
    if f.get("type") not in ("소송판결", "소송제기"):
        return None
    got = {k: v for k, v in (f.get("facts") or []) if isinstance(k, str)}
    name = str(got.get("사건의명칭") or "")
    main = re.sub(r"\s*의\s*소$", "", re.sub(r"\(.*?\)", "", name)).strip()
    inner = [w.strip() for w in re.findall(r"\((.*?)\)", name) if len(w.strip()) >= 2]
    if len(main) < 2:
        return None
    alts = {main: [main] + inner}
    if f["type"] == "소송판결":
        text = str(got.get("판결ㆍ결정내용") or "")
        outcome = next((w for w in ("기각", "각하", "인용") if w in text), "판결")
        if outcome == "판결" and re.search(r"지급하라|이행하라", text):
            outcome = "인용"
        alts[outcome] = [outcome] + [w for w in OUTCOME_WORDS if w != outcome]
        return [main, outcome], alts
    alts["소송"] = ["소송", "소 제기", "제기", "청구"]
    return [main, "소송"], alts


def recheck_lawsuits(rows, *, now, get=None, sleep=time.sleep):
    """Screen lawsuit filings again with the case words read from the original filing."""
    redo = []
    for r in rows:
        better = lawsuit_terms(r)
        if better and better[0] != r.get("terms"):
            redo.append({**r, "terms": better[0], "alts": {**(r.get("alts") or {}), **better[1]},
                         "firstQueries": r.get("queries"), "firstVerdict": r.get("verdict")})
    if not redo:
        return rows, 0
    again = {x["id"]: x for x in screen(redo, now=now, get=get, sleep=sleep)}
    out = [again.get(r["id"], r) for r in rows]
    order = {"미보도 후보": 0, "관련 보도 있음": 1, "미확인": 2, "같은 수치 선행": 3}
    out.sort(key=lambda r: (order[r["verdict"]], -r["strength"]))
    return out, len(redo)


def queries(c):
    a, t = c["company"], c["terms"]
    if is_lawsuit(c):
        numbers,plaintiff=case_identity(c)
        if numbers:
            better=lawsuit_terms(c)
            name=better[0][0] if better else "소송"
            return [f"{a} {sorted(numbers)[0]}", f"{a} {plaintiff} {name}".replace("  "," ")]
    qs = [f"{a} {t[0]}"]
    if len(t) > 1:
        qs.append(f"{a} {t[0]} {t[1]}")
    return qs


# ---------- channels ----------

def strip(s):
    return html.unescape(re.sub(r"<[^>]+>", "", str(s or ""))).strip()


def kst_day(s):
    try:
        return parsedate_to_datetime(s).astimezone(KST).strftime("%Y-%m-%d")
    except (TypeError, ValueError, IndexError):
        return None


def naver(q, *, get=None):
    cid, sec = os.environ.get("NAVER_CLIENT_ID", "").strip(), os.environ.get("NAVER_CLIENT_SECRET", "").strip()
    if not cid or not sec:
        return {"status": "not_configured", "items": []}
    import naver_api
    try:
        via, items = naver_api.news_search(cid, sec, {"query": q, "display": 50, "sort": "sim"}, timeout=15, get=get)
    except naver_api.NaverKeyRefused as e:
        return {"status": "failed", "error": str(e)[:100], "items": []}
    except Exception as e:  # network/HTTP: failure, not zero
        return {"status": "failed", "error": type(e).__name__, "items": []}
    return {"status": "ok", "via": via, "items": [
        {"title": strip(x.get("title")), "text": strip(x.get("description")), "url": x.get("originallink") or x.get("link"),
         "date": kst_day(x.get("pubDate"))} for x in items]}


def rss(url, *, get=None, unwrap=False):
    if get is None:
        import requests
        get = requests.get
    try:
        r = get(url, headers={"User-Agent": UA, "Accept": "application/rss+xml,application/xml;q=0.9,*/*;q=0.8",
                              "Accept-Language": "ko-KR,ko;q=0.9"}, timeout=15)
        if getattr(r, "status_code", 200) != 200:
            return {"status": "failed", "error": f"HTTP {r.status_code}", "items": []}
        root = ET.fromstring(r.content)
        if root.tag != "rss":
            return {"status": "failed", "error": "RSS 아님", "items": []}
    except Exception as e:
        return {"status": "failed", "error": type(e).__name__, "items": []}
    items = []
    for it in root.iter("item"):
        link = it.findtext("link") or ""
        if unwrap:
            link = (parse_qs(urlparse(link).query).get("url") or [link])[0]
        items.append({"title": strip(it.findtext("title")), "text": strip(it.findtext("description")), "url": link,
                      "date": kst_day(it.findtext("pubDate"))})
    return {"status": "ok", "items": items}


def bing(q, *, get=None):
    return rss(f"https://www.bing.com/news/search?q={quote(q)}&format=rss&setlang=ko-KR&cc=KR", get=get, unwrap=True)


def google(q, *, get=None):
    return rss(f"https://news.google.com/rss/search?q={quote(q + ' when:365d')}&hl=ko&gl=KR&ceid=KR:ko", get=get)


# ---------- judging ----------

def company_in_text(company, text):
    # Legal entity boundaries: 포스코 != 포스코인터내셔널; LS != LS전선.
    # Permit Korean particles only at a token end, not arbitrary suffixes.
    for name in aliases(company):
        pattern = r"(?<![A-Za-z0-9가-힣])" + re.escape(name) + r"(?:(?:에서는|으로|에서|에게|까지|부터|은|는|이|가|의|을|를|와|과|도))?(?![A-Za-z0-9가-힣])"
        if re.search(pattern, text, re.I):
            return True
    return False


def article_day(value):
    try:
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return None
        return dt.date.fromisoformat(value)
    except ValueError:
        return None


def judge(c, channels, *, now):
    since = (now - dt.timedelta(days=WINDOW_DAYS)).date()
    if article_day(c.get("since")):
        # A dated event (radar item): articles from before it cannot be reports of it.
        since = max(since, article_day(c.get("since")))
    terms = c["terms"]
    alts = c.get("alts") or {}
    key_term = lead(terms)
    evidence = {}
    invalid_dates = False
    ambiguous_case = False
    lawsuit=is_lawsuit(c)
    expected,plaintiff=case_identity(c)
    if lawsuit and not expected:
        return "미확인", []
    for ch, res in channels.items():
        if res.get("status") != "ok":
            continue  # partial/failed channel items cannot certify absence or precedence
        for a in res.get("items", []):
            day = article_day(a.get("date"))
            if not day or day > now.date():
                invalid_dates = True
                continue
            if day < since:
                continue
            text = f"{a.get('title', '')} {a.get('text', '')}"
            if not company_in_text(c["company"], text):
                continue
            if c.get("strict"):
                # Radar items (radar_press_check): the company and an event word must be in the headline. Body-only
                # matches are kept as weak evidence and do not make an item 'covered' (운영 10-28: 현대제철 국제무역법원
                # 소송이 포스코 판결 기사 본문에 이름이 나와 '관련 보도 있음'으로 내려갔다).
                generic = set(c.get("generic") or [])
                title = a.get("title", "")
                words = [t for t in terms if t not in generic]
                t_hits = [t for t in words if any(w in title for w in alts.get(t, [t]))]
                x_hits = [t for t in words if any(w in text for w in alts.get(t, [t]))]
                must = [m for m in c.get("must") or [] if m]
                if company_in_text(c["company"], title) and (t_hits or len(x_hits) >= 2) and must and not any(m in text for m in must):
                    # 사업장이 여럿인 회사: 그 사업장 지명이 없는 기사는 다른 사업장 이야기일 수 있다(10-31 포스코 광양 ↔ 포항 기사)
                    why, rank = f"제목에 회사·낱말({', '.join((t_hits or x_hits)[:3])})이 있으나 사업장 지명({'·'.join(must)}) 없음 — 다른 사업장 기사일 수 있음", 0
                elif company_in_text(c["company"], title) and (t_hits or len(x_hits) >= 2):
                    why, rank = f"제목에 회사·낱말({', '.join((t_hits or x_hits)[:3])}) — 동일 사건 미확정", 1
                elif len(x_hits) >= 2:
                    why, rank = f"본문에만 회사·낱말({', '.join(x_hits[:3])}) — 제목 불일치, 같은 사건 가능성 낮음", 0
                else:
                    continue
                key = a.get("url") or a.get("title")
                if key not in evidence or evidence[key]["rank"] < rank:
                    evidence[key] = {"title": a.get("title", "")[:160], "url": a.get("url"), "date": a.get("date"),
                                     "channel": ch, "why": why, "rank": rank}
                continue
            if lawsuit:
                observed=case_numbers(text)
                # Same issuer, date and generic case name cannot identify a
                # lawsuit. An article can cover multiple cases; require this
                # case's number or named plaintiff in its actual snippet.
                exact=bool(expected & observed)
                party_match=bool(plaintiff and company_in_text(plaintiff,text))
                if observed and not exact:
                    continue
                if not exact and not party_match:
                    if any(w in text for w in ("소송","판결","기각","승소")):
                        ambiguous_case=True
                    continue
            def has(t, where):
                return any(w in where for w in alts.get(t, [t]))
            # Numbers alone are never evidence of the same event. Preserve
            # related coverage for human review even without period/unit proof.
            term_hits = [t for t in terms if has(t, text)]
            related = (lawsuit and (exact or party_match)) or len(term_hits) >= 2 or (key_term and has(key_term, a.get("title", "")))
            if not related:
                continue
            unit = re.sub(r"\s+", "", c.get("unit") or "")
            period = c.get("period") or ""
            num_hits = [f for f in c["numbers"] if re.search(
                r"(?<![\d,.])" + re.escape(f) + r"\s*" + re.escape(unit) + r"(?![A-Za-z0-9])", text)] if unit else []
            # Require an explicit reporting period and multiple event terms.
            # Approximate money conversions in num_forms are search hints only.
            specific = [t for t in term_hits if t not in {"투자", "공장", "생산", "수주", "계약", "매출", "수출", "판매", "증설", "변압기"}]
            same_context = (len(term_hits) >= 2 and specific and period and period in text
                            and unit not in ("백만원", "백만 원"))
            if lawsuit:
                why,rank=("사건번호 일치 — 기사 원문 최종 확인 필요" if exact else "원고 일치 — 사건번호·거래 대상 추가 확인 필요"),1
            elif num_hits and same_context:
                why, rank = f"같은 수치·단위·기간 및 사건 낱말({', '.join(num_hits[:2])}; {period}) — 동일 사건 최종 확인 필요", 2
            else:
                why, rank = f"낱말({', '.join(term_hits[:3])}) — 동일 사건 미확정", 1
            key = a.get("url") or a.get("title")
            if key not in evidence or evidence[key]["rank"] < rank:
                evidence[key] = {"title": a.get("title", "")[:160], "url": a.get("url"), "date": a.get("date"),
                                 "channel": ch, "why": why, "rank": rank}
    ev = sorted(evidence.values(), key=lambda e: (-e["rank"], e.get("date") or ""))
    web_ok = any(channels.get(k, {}).get("status") == "ok" for k in ("bing", "google"))
    naver_ok = channels.get("naver", {}).get("status") == "ok"
    if any(e["rank"] == 2 for e in ev):
        verdict = "같은 수치 선행"
    elif any(e["rank"] >= 1 for e in ev):
        verdict = "관련 보도 있음"
    elif naver_ok and web_ok and not invalid_dates and not ambiguous_case:
        verdict = "미보도 후보"
    else:
        verdict = "미확인"
    return verdict, [{k: v for k, v in e.items() if k != "rank"} for e in ev[:5]]


def screen(cands, *, now, get=None, sleep=time.sleep):
    out = []
    for c in cands:
        qs = queries(c)
        channels = {"naver": {"status": "ok", "items": []}, "bing": {}, "google": {}}
        n_status, via = [], None
        for q in qs:
            r = naver(q, get=get)
            n_status.append(r["status"])
            via = r.get("via") or via
            channels["naver"]["items"] += r["items"]
            sleep(0.12)
        channels["naver"]["status"] = ("ok" if all(s == "ok" for s in n_status)
                                       else "not_configured" if "not_configured" in n_status else "failed")
        if via:
            channels["naver"]["via"] = via
        channels["bing"] = bing(qs[-1], get=get)
        sleep(0.3)
        channels["google"] = google(qs[-1], get=get)
        sleep(0.3)
        verdict, evidence = judge(c, channels, now=now)
        out.append({**c, "queries": qs, "verdict": verdict, "evidence": evidence,
                    "channels": {k: {"status": v.get("status"), "returned": len(v.get("items", [])),
                                     "invalidDates": sum(article_day(a.get("date")) is None or article_day(a.get("date")) > now.date() for a in v.get("items", [])),
                                     **({"via": v["via"]} if v.get("via") else {}),
                                     **({"error": v["error"]} if v.get("error") else {})} for k, v in channels.items()}})
    order = {"미보도 후보": 0, "관련 보도 있음": 1, "미확인": 2, "같은 수치 선행": 3}
    out.sort(key=lambda r: (order[r["verdict"]], -r["strength"]))
    return out


def carry_first_seen(rows, previous, now):
    """후보마다 처음 심사한 시각을 남긴다 — radar_today는 이 시각이 최근인 후보만 '새 항목'으로 센다(10-30: 10-07·10-12 특허 후보가
    판정 전까지 매일 A에 다시 올라옴). 이전 결과에 시각이 없으면 이전 실행 시각을 쓴다."""
    prev = previous if isinstance(previous, dict) else {}
    seen = {c.get("id"): c.get("firstSeen") or prev.get("generatedAt") for c in prev.get("candidates") or [] if isinstance(c, dict)}
    stamp = now.isoformat(timespec="seconds")
    for r in rows:
        r["firstSeen"] = seen.get(r.get("id")) or stamp
    return rows


def report(rows, *, now, inputs):
    counts = {v: sum(1 for r in rows if r["verdict"] == v) for v in ("미보도 후보", "관련 보도 있음", "같은 수치 선행", "미확인")}
    return {"schema": SCHEMA, "generatedAt": now.isoformat(timespec="seconds"), "inputs": inputs,
            "counts": counts, "windowDays": WINDOW_DAYS, "candidates": rows,
            "rules": ["미보도 후보는 검색 범위(네이버 뉴스 API·빙·구글 최근 365일, 질의 2개) 안에서 못 찾았다는 뜻이다. 단독 판정이 아니다.",
                      "관련 보도 있음은 회사명+낱말이 겹친 기사. 같은 사건·같은 각도인지는 열어 봐야 한다.",
                      "같은 수치 선행은 기업·사건 낱말·수치 단위·기간이 함께 일치한 기사. 동일 사건인지는 원문 확인 전 미확정이다.",
                      "미확인은 채널 실패·미설정 또는 기사 날짜 오류. 0건이 아니다. 최종 단독 판단은 기자가 한다."],
            "confirmedScoops": 0}


def push(doc, token, *, post=None):
    import private_store
    return private_store.put("scoop-screen", doc, token, post=post)


def load(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser(description="단독 후보 자동 심사(결과는 기자 전용 저장소로만)")
    ap.add_argument("--limit", type=int, default=MAX_CANDIDATES)
    ap.add_argument("--out", help="로컬 확인용 파일(공개 저장소에 커밋하지 않는다)")
    ap.add_argument("--dry-run", action="store_true", help="검색 없이 후보·질의만 만든다")
    a = ap.parse_args()
    now = now_kst()
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    previous = None
    if token and not a.dry_run:
        import private_store
        try:
            previous = private_store.get("scoop-screen", token)
        except private_store.StoreError:
            previous = None  # cannot tell — run; first-seen times start now
        if os.environ.get("GITHUB_EVENT_NAME") == "schedule" and private_store.late_scheduled_duplicate(previous, now):
            return
    clues, stats = load(ROOT / "tools/clues.json") or {}, load(ROOT / "tools/stats.json") or {}
    cands = select(clues, stats, now=now, limit=a.limit)
    inputs = {"cluesGeneratedAt": clues.get("generatedAt"), "statsGeneratedAt": stats.get("generatedAt"),
              "selected": len(cands)}
    if a.dry_run:
        for c in cands:
            print(c["company"], "|", queries(c), "|", c["numbers"][:4])
        return
    dart_key = os.environ.get("DART_API_KEY", "").strip()
    if dart_key:
        # Original filing facts and same-company prior comparison for DART leads that could reach the reporter.
        import requests
        import dart_filing_facts
        from dart_lineage import zip_documents
        # Fetch identity before any news query. A generic lawsuit title is
        # never enough to certify either prior reporting or its absence.
        targets = sorted(cands,key=lambda r:not is_lawsuit(r))
        dart_filing_facts.enrich(targets, dart_key, dart_filing_facts.load_corp_codes(), fetch_documents=zip_documents, get=requests.get)
        for c in cands:
            better=lawsuit_terms(c)
            if better:
                c["terms"],c["alts"]=better
        inputs["lawsuitIdentityRead"] = sum(bool(case_identity(c)[0]) for c in cands if is_lawsuit(c))
        got = [r["filing"] for r in cands if r.get("filing")]
        inputs["filingFacts"] = {"read": sum(1 for x in got if x.get("facts") is not None and not x.get("error")),
                                 "routine": sum(1 for x in got if x.get("routine")), "failed": sum(1 for x in got if x.get("error"))}
        print(f"::notice title=scoop-screen-filings::DART 원문 요점 {inputs['filingFacts']['read']}건 · 일상 {inputs['filingFacts']['routine']}건 · 실패 {inputs['filingFacts']['failed']}건")
    else:
        print("::warning title=scoop-screen-filings::DART_API_KEY 미설정 — 원문 요점·직전 비교 생략")
    rows = carry_first_seen(screen(cands, now=now), previous, now)
    doc = report(rows, now=now, inputs=inputs)
    if a.out:
        Path(a.out).write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    ch = {k: sum(1 for r in rows if r["channels"][k]["status"] == "ok") for k in ("naver", "bing", "google")}
    # Public log: counts only — never titles, companies or queries.
    print(f"::notice title=scoop-screen::후보 {len(rows)} · " + " · ".join(f"{k} {v}" for k, v in doc["counts"].items())
          + f" · 채널 정상 naver {ch['naver']}/{len(rows)} bing {ch['bing']}/{len(rows)} google {ch['google']}/{len(rows)}")
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    if not token:
        print("::warning title=scoop-screen-push::MCP_ACCESS_TOKEN 미설정 — 결과를 기자 전용 저장소로 보내지 않음(공개 저장소에도 쓰지 않음)")
        return
    import private_store
    status = push(doc, token)
    print(f"::notice title=scoop-screen-push::기자 전용 저장소 전송 HTTP {status}")
    if status == 404:
        print(f"::warning title=scoop-screen-push-token::토큰 거부 가능성 — {private_store.token_shape(private_store.normalize_token(token))}. GitHub Secret MCP_ACCESS_TOKEN이 Cloudflare 값과 같아야 함")
    if status != 200:
        sys.exit(1)


if __name__ == "__main__":
    main()
