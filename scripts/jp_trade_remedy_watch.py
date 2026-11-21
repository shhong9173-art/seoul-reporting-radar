"""일본 무역구제(재무성 관세제도 누리집 — 반덤핑·상계관세·긴급관세 결정 목록) — 한국산 사건의 새 공고.

근거(11-21 기자 "다음 업데이트 계속 진행해"): 일본은 재무성·경제산업성 합동 조사로 한국산 철강을 잇달아 조사한다 —
용융아연도금강판(2025-08-13 개시, 2026-07-24 가결정, 08-08~12-07 잠정 관세 29.2~55.3%, 조사 기간 12-12까지 연장),
열연·냉연강판(2026-06-01 개시), 비스페놀A(2025-08-20 개시, 기간 연장). 무역협회 수입규제DB는 한 달에 한 번 몰아서 고친다(10-29 뒤 갱신 없음).
탐침(11-21): 일본어 목록 https://www.mof.go.jp/policy/customs_tariff/trade/plan/futou/index.html — 'li > a(제목)' 뒤에 '（令和8年10月27日）',
최신순, 22건 중 한국 11건. 상세 쪽은 보도자료 본문(신청 업체·조사 경과·잠정 관세율 범위·기간). robots.txt 없음(404). UTF-8.
영어 쪽(english/policy/customs_tariff/traderemedy)은 '가번역'이라 늦게 올라온다 — 일본어 쪽을 본다.

하는 일: 반덤핑(futou)·상계관세(sousai) 목록에서 제목에 '大韓民国'이 든 공고, 긴급관세(kinkyu, 세이프가드)는 출입 업종 품목이면 원산지 없이.
처음 보는 공고를 이벤트로 — 상세 쪽은 한 실행 DETAIL_BUDGET건(PAUSE초 간격), 못 읽은 것은 다음 실행에 읽어 이벤트를 채운다. 첫 실행은 기준선.
등급: A = 한국산(세이프가드는 모든 수입) 출입 업종 품목의 개시·가결정·잠정·확정·종료·일몰 재심 개시·연장 결정.
B = 출입 업종 품목의 조사 기간 연장·변경, 또는 업종 밖 품목의 굵은 결정. C = 그 밖. 결과는 기자 전용 저장소(jp-trade-remedy)로만 — 공개 로그에는 건수만.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import os
import re
import sys
import time
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

SCHEMA = "jp_trade_remedy/v1"
KST = dt.timezone(dt.timedelta(hours=9))
SITE = "https://www.mof.go.jp"
BASE = SITE + "/policy/customs_tariff/trade/plan/"
INDEXES = (("AD", "반덤핑(不当廉売関税)", BASE + "futou/index.html"),
           ("CVD", "상계관세(相殺関税)", BASE + "sousai/index.html"),
           ("SG", "세이프가드(緊急関税)", BASE + "kinkyu/index.html"))
UA = {"User-Agent": "Mozilla/5.0 seoul-reporting-radar (reporter research)"}
# 관세·외국환등심의회 관세분과회 특수관세부회 배포자료(11-21 2판): 확정·잠정 관세와 과세 기간 연장은 각의 결정 전에 이 부회가 '적당' 답신을 낸다.
# 11-20 회의 자료에 한국산 도금강판(포스코 29.2% 등 5년)·비스페놀A(LG화학 제외)·수산화칼륨 연장이 올랐는데 국내 보도는 없었다(11-21 18시 대조).
# 목록은 'li > p > a(令和8年11月20日開催)'(탐침: li 하나에 여러 회의), 회의 쪽은 PDF 링크 제목에 품목('（資料２－２）大韓民国産及び…の課税(PDF:729KB)').
COUNCIL_INDEX = SITE + "/about_mof/councils/customs_foreign_exchange/sub-of_customs/proceedings_tokusyu/material/index.html"
COUNCIL_RECENT_DAYS = 7     # 첫 실행이라도 최근 이만큼 안의 회의는 이벤트로(자료가 회의 뒤 며칠 동안 기사 거리다)
MEETING_BUDGET = 2
PDF_BUDGET = 3
PDF_MAX = 6_000_000
KEEP_MEETINGS = 20
DETAIL_BUDGET = 4
PAUSE = 2.0
EVENT_DAYS = 90
KEEP_ENTRIES = 80
KOREA = re.compile(r"大韓民国|韓国")
# 일본어 품목 → (한국어, 보도 대조 낱말, 출입 업종 여부). 위에서부터 첫 일치.
JP_PRODUCT = [
    (r"ステンレス", "스테인리스강", ["스테인리스"], True),
    (r"亜鉛めっき|めっき鋼", "용융아연도금강판", ["도금강판", "아연도금"], True),
    (r"熱延", "열연강판", ["열연"], True),
    (r"冷延", "냉연강판", ["냉연"], True),
    (r"電磁鋼", "전기강판", ["전기강판"], True),
    (r"鋼管|鋼製の管", "강관", ["강관"], True),
    (r"線材|棒鋼", "선재·봉강", ["선재", "봉강"], True),
    (r"鋼|鉄", "철강재", ["철강"], True),
    (r"アルミニウム", "알루미늄", ["알루미늄"], True),
    (r"ビスフェノール", "비스페놀A", ["비스페놀", "BPA"], True),
    (r"ポリエチレン|ポリプロピレン|ポリスチレン|ポリ塩化ビニル|塩化ビニル|テレフタル|樹脂|合成ゴム", "화학 수지·고무", ["수지"], True),
    (r"タイヤ", "타이어", ["타이어"], True),
    (r"電線|ケーブル|変圧器", "전선·전력기기", ["전선", "변압기"], True),
    (r"黒鉛電極", "흑연전극", ["흑연전극"], False),
    (r"水酸化カリウム", "수산화칼륨", ["수산화칼륨"], False),
    (r"炭酸二?カリウム", "탄산칼륨", ["탄산칼륨"], False),
    (r"二酸化チタン", "이산화티타늄", ["이산화티타늄"], False),
]
STRONG = ("조사 개시", "예비 판정(가결정)", "잠정 관세 결정", "확정 관세 결정", "조사 종료(관세 안 매김)",
          "일몰 재심(과세 기간 연장 조사) 개시", "과세 기간 연장 결정(일몰 재심 결과)", "과세 기간 연장 안 함(조치 끝)")
# 일본어 상세 쪽에 나올 수 있는 출입처 이름(전각은 NFKC로 반각이 된 뒤 맞춘다). 영문 이름은 미국 감시의 목록을 같이 쓴다.
JP_NAMES = [("포스코", r"ポスコ"), ("현대제철", r"現代製鉄|ヒュンダイスチール"), ("동국제강", r"東国製鋼"), ("동국씨엠", r"東国(?:CM|シーエム)"),
            ("KG스틸", r"KGスチール"), ("세아제강", r"世亜製鋼|セア製鋼"), ("LG화학", r"LG化学"), ("롯데케미칼", r"ロッテケミカル"),
            ("한화솔루션", r"ハンファソリューション"), ("금호석유화학", r"錦湖石油化学")]
ERA = re.compile(r"令和\s*(元|\d{1,2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日")


def now_kst():
    return dt.datetime.now(KST)


def norm(s):
    return unicodedata.normalize("NFKC", s or "")


def latin_spaced(text):
    """영문 이름 앞뒤에 빈칸 — 한자·가나도 \\w라 '供給者LG Chem'에서 \\bLG가 안 맞는다(11-21 비스페놀A 자료)."""
    return re.sub(r"([A-Za-z][A-Za-z0-9&.,'\- ]*[A-Za-z0-9.])", r" \1 ", text or "")


def plain(raw):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw or ""))).strip()


def era_date(s):
    """'令和8年10月27日'·'令和８年１２月１２日'(전각) → '2026-10-27'. 못 읽으면 ''."""
    m = ERA.search(norm(s))
    if not m:
        return ""
    y = 1 if m.group(1) == "元" else int(m.group(1))
    try:
        return dt.date(2018 + y, int(m.group(2)), int(m.group(3))).isoformat()
    except ValueError:
        return ""


def product_ko(title):
    t = norm(title)
    for rx, ko, words, beat in JP_PRODUCT:
        if re.search(rx, t):
            return ko, words, beat
    return None, [], False


def kind_of(title):
    """공고 제목(일본어) → 한국어 종류. 순서가 중요하다: 일몰 재심 개시 제목에도 '調査を開始'가, 가결정 제목에도 '不当廉売関税の課税'가 들어간다."""
    t = norm(title)
    if re.search(r"課税期間の延長に関する調査を開始", t):
        return "일몰 재심(과세 기간 연장 조사) 개시"
    if re.search(r"課税期間の延長を決定", t):
        return "과세 기간 연장 결정(일몰 재심 결과)"
    if re.search(r"課税期間を延長しない|延長しないこと", t):
        return "과세 기간 연장 안 함(조치 끝)"
    if re.search(r"調査の期間を延長", t):
        return "조사 기간 연장"
    if re.search(r"仮の決定", t):
        return "예비 판정(가결정)"
    if re.search(r"暫定的な.{0,40}課税を決定|暫定措置", t):
        return "잠정 관세 결정"
    if re.search(r"課さないこと|課税しないこと|調査を終了|調査の終了", t):
        return "조사 종료(관세 안 매김)"
    if re.search(r"課税を決定|課することを決定", t):
        return "확정 관세 결정"
    if re.search(r"調査を開始", t):
        return "조사 개시"
    if re.search(r"変更|改正|見直し", t):
        return "조치 변경"
    return "공고"


def case_key(title):
    """같은 사건의 공고를 묶는 열쇠 — '…に対する' 앞(원산지+품목). 없으면 제목 앞 60자."""
    t = norm(title).strip()
    m = re.match(r"(.{6,120}?)に対する", t)
    return (m.group(1) if m else t[:60]).strip()


LI = re.compile(r"(?is)<li[^>]*>(.*?)</li>")
A = re.compile(r"""(?is)<a[^>]+href=["']([^"']+)["'][^>]*>(.*?)</a>(.*)""")


def parse_index(raw, kind, page_url):
    """목록 쪽 → [{url, title, date, index}] (날짜가 붙은 줄만 — 메뉴·국회도서관 보관 링크는 날짜가 없다)."""
    out, seen = [], set()
    for li in LI.findall(raw or ""):
        m = A.search(li)
        if not m:
            continue
        rest = plain(m.group(3))
        date = era_date(rest[:40])
        title = plain(m.group(2))
        if not date or len(title) < 10:
            continue
        url = m.group(1).strip()
        if url.startswith("/"):
            url = SITE + url
        elif not url.startswith("http"):
            url = page_url.rsplit("/", 1)[0] + "/" + url
        if url in seen:
            continue
        seen.add(url)
        out.append({"url": url, "title": title[:400], "date": date, "index": kind})
    return out


def wanted(e):
    if KOREA.search(e["title"]):
        return True
    return e["index"] == "SG" and product_ko(e["title"])[2]


def tier_of(kind, beat):
    if beat and kind in STRONG:
        return "A"
    return "B" if beat or kind in STRONG else "C"


def _year_for(month, day, base):
    """연도 없는 'M月D日' — 공고일 base 뒤 가장 가까운 날(잠정 관세 끝은 공고일 뒤다)."""
    for y in (base.year, base.year + 1):
        try:
            d = dt.date(y, month, day)
        except ValueError:
            return None
        if d >= base - dt.timedelta(days=31):
            return d
    return None


def parse_detail(raw, published):
    """상세 쪽(보도자료) → 사실 문장·세율 범위·조사 끝·관세 끝·신청 업체·출입처 이름·첨부 PDF."""
    body = re.sub(r"(?is)<(script|style|nav|header|footer|noscript)[^>]*>.*?</\1>", " ", raw or "")
    m = re.search(r"(?is)<main[^>]*>(.*?)</main>", body)
    main = m.group(1) if m else body
    pdfs = []
    for href, inner in re.findall(r"""(?is)<a[^>]+href=["']([^"']+\.pdf)["'][^>]*>(.*?)</a>""", main):
        url = href if href.startswith("http") else SITE + href if href.startswith("/") else href
        t = plain(inner)
        if t and len(pdfs) < 8 and url not in [p["url"] for p in pdfs]:
            pdfs.append({"title": t[:160], "url": url})
    text = norm(plain(main))
    sents = [s.strip() + "。" for s in re.split(r"。", text) if len(s.strip()) >= 12]
    keys = re.compile(r"[%％]|まで|株式会社|本日|告示第|答申|延長|仮の決定|暫定|課税|調査を開始")
    facts = []
    for s in sents:
        if keys.search(s) and s not in facts:
            facts.append(s[:260])
        if len(facts) >= 5:
            break
    rates = None
    r = re.search(r"(\d+(?:\.\d+)?)\s*[～〜~\-－]\s*(\d+(?:\.\d+)?)\s*[%％]", text)
    if r:
        rates = f"{r.group(1)}~{r.group(2)}%"
    else:
        r = re.search(r"税率は?\s*(\d+(?:\.\d+)?)\s*[%％]", text)
        rates = f"{r.group(1)}%" if r else None
    until = ""
    u = re.search(r"(令和\s*(?:元|\d{1,2})\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)\s*までと(?:する|し)", text)
    if u:
        until = era_date(u.group(1))
    duty_to = ""
    base = dt.date.fromisoformat(published) if published else None
    d = re.search(r"から\s*(?:(同年|翌年|令和\s*(?:元|\d{1,2})\s*年)\s*)?(\d{1,2})\s*月\s*(\d{1,2})\s*日\s*までの間", text)
    if d and base:
        if d.group(1) and d.group(1).startswith("令和"):
            duty_to = era_date(f"{d.group(1)}{d.group(2)}月{d.group(3)}日")
        else:
            got = _year_for(int(d.group(2)), int(d.group(3)), base)
            if got and d.group(1) == "翌年":
                got = got.replace(year=base.year + 1)
            duty_to = got.isoformat() if got else ""
    applicants = ""
    a = re.search(r"日に(.{4,160}?)から「", text)   # NFKC 뒤라 괄호는 반각
    if a and "株式会社" in a.group(1):
        applicants = re.sub(r"[(（]申請書掲載順[)）]", "", a.group(1)).strip()[:160]
    names = [ko for ko, rx in JP_NAMES if re.search(rx, text)]
    try:
        from trade_remedy_watch import BEAT_NAMES
        spaced = latin_spaced(text)
        names += [ko for ko, rx in BEAT_NAMES if ko not in names and re.search(rx, spaced, re.I)]
    except Exception:  # noqa: BLE001
        pass
    return {"facts": facts, "rates": rates, "until": until, "dutyTo": duty_to, "applicants": applicants, "companies": names, "pdfs": pdfs}


COUNCIL_A = re.compile(r"""(?is)<a[^>]+href=["']([^"']*kanb\d{8}\.html?)["'][^>]*>(.*?)</a>""")
PDF_A = re.compile(r"""(?is)<a[^>]+href=["']([^"']+\.pdf)["'][^>]*>(.*?)</a>""")


def parse_council_index(raw, page_url=COUNCIL_INDEX):
    """부회 배포자료 목록 → [{url, date}] ('令和8年11月20日開催' 링크만)."""
    from urllib.parse import urljoin
    out, seen = [], set()
    for href, inner in COUNCIL_A.findall(raw or ""):
        text = plain(inner)
        date = era_date(text)
        url = urljoin(page_url, href.strip())
        if "開催" not in text or not date or url in seen:
            continue
        seen.add(url)
        out.append({"url": url, "date": date})
    return out


def council_kind(title):
    t = norm(title)
    if re.search(r"課税期間の延長", t):
        return "과세 기간 연장(일몰)"
    if re.search(r"暫定", t):
        return "잠정 관세"
    if re.search(r"課税|課する", t):
        return "관세 부과(확정)"
    return "안건"


def parse_meeting(raw, page_url):
    """회의 배포자료 쪽 → PDF [{title, url}] (제목 끝 '(PDF:729KB)'는 뗀다)."""
    from urllib.parse import urljoin
    out = []
    for href, inner in PDF_A.findall(raw or ""):
        title = re.sub(r"\s*[(（]PDF[:：][^)）]*[)）]\s*$", "", plain(inner)).strip()
        url = urljoin(page_url, href.strip())
        if title and url not in [m["url"] for m in out]:
            out.append({"title": title[:300], "url": url})
    return out


def council_items(materials):
    """한국산 안건(자료 제목에 '大韓民国') 또는 출입 업종 품목 세이프가드 자료."""
    items = []
    for m in materials:
        korea = bool(KOREA.search(m["title"]))
        ko, words, beat = product_ko(m["title"])
        if not korea and not (beat and re.search(r"緊急関税", norm(m["title"]))):
            continue
        items.append({**m, "korea": korea, "productKo": ko, "productWords": words, "beat": beat, "kind": council_kind(m["title"])})
    return items


def pdf_text(content):
    import io
    from pypdf import PdfReader
    return norm("\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(content)).pages))


def council_facts(text):
    """부회 자료 PDF 글 → '適当'(부과 권고)·기간·본문 출입처·'…を除く'(제외 업체). 세율은 표 배치 때문에 자동으로 뽑지 않는다(원문 표 확인)."""
    names = [ko for ko, rx in JP_NAMES if re.search(rx, text)]
    try:
        from trade_remedy_watch import BEAT_NAMES
        names += [ko for ko, rx in BEAT_NAMES if ko not in names and re.search(rx, latin_spaced(text), re.I)]
    except Exception:  # noqa: BLE001
        BEAT_NAMES = []
    excl_raw = [x.strip() for x in re.findall(r"[(（]([^()（）]{2,80}?)を除く[)）]", text)][:3]
    excluded = []
    for x in excl_raw:
        excluded += [ko for ko, rx in JP_NAMES if re.search(rx, x) and ko not in excluded]
        excluded += [ko for ko, rx in BEAT_NAMES if re.search(rx, latin_spaced(x), re.I) and ko not in excluded]
    y = re.search(r"(\d{1,2})\s*年間", text)
    return {"recommends": "適当" in text, "years": int(y.group(1)) if y else None, "companies": names, "excluded": excluded, "excludedRaw": excl_raw[:2]}


def council_item_text(it):
    p = it.get("pdf") or {}
    bits = [f"{it.get('productKo') or '업종 밖 품목'} {it['kind']}"]
    if p.get("read"):
        if p.get("recommends"):
            bits.append("자료에 '適当'(부과가 적당)")
        if p.get("years"):
            bits.append(f"기간 {p['years']}년")
        named = [n for n in p.get("companies") or [] if n not in (p.get("excluded") or [])]
        if named:
            bits.append(f"본문 출입처 {'·'.join(named)}")
        if p.get("excluded"):
            bits.append(f"부과 대상에서 제외 {'·'.join(p['excluded'])}(자료 '…を除く')")
    elif p.get("error"):
        bits.append(f"PDF 못 읽음({p['error']})")
    return " · ".join(bits)


def council_event(m, stamp):
    items = m.get("items") or []
    beat = [i for i in items if i.get("beat")]
    names = []
    for i in items:
        names += [n for n in (i.get("pdf") or {}).get("companies") or [] if n not in names]
    marks = "①②③④⑤⑥⑦⑧"
    text = (f"일본 재무성 특수관세부회 회의 자료({m['date']} 개최) — 한국산 안건 {len(items)}건: "
            + " / ".join(f"{marks[k] if k < len(marks) else '-'} {council_item_text(i)}" for k, i in enumerate(items))
            + f" · 자료 목록 {m['url']} (부회가 부과를 '적당'이라 답하면 각의 결정·정령 공포로 이어진다 — 세율·대상 업체는 자료 PDF 원문 표)")
    words = []
    for i in beat or items:
        words += [w for w in i.get("productWords") or [] if w not in words]
    return {"id": f"jpcouncil:{m['date'].replace('-', '')}", "kind": "일본 무역구제(특수관세부회 자료)", "tier": "A" if beat else "B", "index": "AD",
            "product": (beat or items)[0].get("productKo") or "", "productWords": words, "korea": any(i.get("korea") for i in items),
            "company": "·".join(names), "companies": names, "case": "", "date": m["date"], "url": m["url"], "text": text, "detectedAt": stamp}


def council_run(prev_council, now, get, sleep, stamp):
    """부회 배포자료: 새 회의 쪽 → 한국산 안건 → 그 자료 PDF('適当'·기간·출입처·제외). → (council, check, errors)."""
    council = dict(prev_council or {})
    meetings = {m["url"]: m for m in council.get("meetings") or [] if isinstance(m, dict) and m.get("url")}
    first = not meetings and not council.get("seen")
    check = {"source": "일본 재무성 특수관세부회 배포자료", "url": COUNCIL_INDEX, "status": "ok", "returned": 0}
    errors = []
    try:
        r = get(COUNCIL_INDEX, headers=UA, timeout=60)
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}")
        r.encoding = "utf-8"
        listed = parse_council_index(r.text)
        if not listed:
            raise RuntimeError("목록 0줄(형식 변경 의심)")
    except Exception as ex:  # noqa: BLE001
        check.update(status="failed", error=str(ex)[:60] or type(ex).__name__)
        return council, check, errors
    check["returned"] = len(listed)
    recent = (now.date() - dt.timedelta(days=COUNCIL_RECENT_DAYS)).isoformat()
    for x in listed:
        if x["url"] not in meetings:
            meetings[x["url"]] = {**x, "read": False, "baseline": first and x["date"] < recent}
    budget, pdfs = MEETING_BUDGET, PDF_BUDGET
    for m in sorted(meetings.values(), key=lambda m: m["date"], reverse=True):
        if m.get("read") or m.get("baseline"):
            continue
        if budget <= 0:
            break
        budget -= 1
        sleep(PAUSE)
        try:
            r = get(m["url"], headers=UA, timeout=60)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")
            r.encoding = "utf-8"
            mats = parse_meeting(r.text, m["url"])
            m.update(read=True, readAt=stamp, materials=len(mats), items=council_items(mats))
            m.pop("error", None)
        except Exception as ex:  # noqa: BLE001
            m["error"] = str(ex)[:40] or type(ex).__name__
            errors.append(f"부회 {m['date']} {m['error']}")
    # 안건 자료 PDF: 아직 못 읽은 것(최근 회의부터)
    for m in sorted(meetings.values(), key=lambda m: m["date"], reverse=True):
        for it in m.get("items") or []:
            if (it.get("pdf") or {}).get("read") or pdfs <= 0:
                continue
            pdfs -= 1
            sleep(PAUSE)
            try:
                r = get(it["url"], headers=UA, timeout=90)
                if r.status_code != 200:
                    raise RuntimeError(f"HTTP {r.status_code}")
                if len(r.content or b"") > PDF_MAX:
                    raise RuntimeError("PDF 너무 큼")
                it["pdf"] = {**council_facts(pdf_text(r.content)), "read": True}
            except Exception as ex:  # noqa: BLE001
                it["pdf"] = {"read": False, "error": str(ex)[:40] or type(ex).__name__}
                errors.append(f"부회 PDF {it['url'].rsplit('/', 1)[-1]} {it['pdf']['error']}")
    kept = sorted(meetings.values(), key=lambda m: m["date"], reverse=True)[:KEEP_MEETINGS]
    check["korea"] = sum(1 for m in kept if m.get("items"))
    council.update(meetings=kept, checkedAt=stamp, seen=True)
    return council, check, errors


def event_text(e):
    det = e.get("detail") or {}
    bits = [f"일본 재무성 무역구제 공고({e['indexLabel']}) — {e['kind']}: 「{e['title'][:200]}」",
            f"품목 {e['productKo']}" if e.get("productKo") else "품목(출입 업종 밖)", f"공표 {e['date']}"]
    if e["index"] == "SG" and not e.get("korea"):
        bits.append("세이프가드 — 원산지 구분 없이 모든 수입(한국산 포함)")
    if det.get("rates"):
        bits.append(f"세율 {det['rates']}(보도자료 본문 — 업체별 세율은 정령·보고서 원문)")
    if det.get("until"):
        bits.append(f"조사 기간 {det['until']}까지")
    if det.get("dutyTo"):
        bits.append(f"관세 부과 {det['dutyTo']}까지")
    if det.get("applicants"):
        bits.append(f"신청 {det['applicants']}")
    if det.get("companies"):
        bits.append(f"본문에 출입처 {'·'.join(det['companies'])}")
    if not det.get("read"):
        bits.append(f"상세 쪽 못 읽음({det.get('error') or '다음 실행에 읽음'})")
    return " · ".join(bits) + " (일본 재무성·경제산업성 공표 — 세율·대상 업체는 원문 확인)"


def event_id(e):
    return f"jptr:{e['url'].rsplit('/', 1)[-1].rsplit('.', 1)[0][:60]}"


def event_of(e, stamp):
    return {"id": event_id(e), "kind": f"일본 무역구제({e['kind']})", "tier": e["tier"],
            "index": e["index"], "product": e.get("productKo") or "", "productWords": e.get("productWords") or [], "korea": e["korea"],
            "company": "·".join((e.get("detail") or {}).get("companies") or []), "companies": (e.get("detail") or {}).get("companies") or [], "case": e["case"], "date": e["date"], "url": e["url"],
            "text": event_text(e), "detectedAt": stamp}


def run(now, previous=None, *, get=None, sleep=time.sleep):
    if get is None:
        import requests
        get = requests.get
    stamp = now.isoformat(timespec="seconds")
    prev = previous or {}
    first = not prev.get("entries")
    entries = {x["url"]: x for x in prev.get("entries") or [] if isinstance(x, dict) and x.get("url")}
    seen = set(prev.get("seen") or []) | set(entries)
    events = [e for e in prev.get("events") or [] if isinstance(e, dict) and str(e.get("detectedAt", "")) >= (now - dt.timedelta(days=EVENT_DAYS)).isoformat()]
    checks, listed, fresh = [], [], 0
    for kind, label, url in INDEXES:
        check = {"source": f"일본 재무성 {label}", "url": url, "status": "ok", "returned": 0}
        try:
            r = get(url, headers=UA, timeout=60)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")
            r.encoding = "utf-8"
            got = parse_index(r.text, kind, url)
            if kind == "AD" and not got:
                raise RuntimeError("목록 0줄(형식 변경 의심)")
        except Exception as ex:  # noqa: BLE001
            check.update(status="failed", error=str(ex)[:60] or type(ex).__name__)
            checks.append(check)
            sleep(PAUSE)
            continue
        want = [x for x in got if wanted(x)]
        check.update(returned=len(got), korea=len(want))
        checks.append(check)
        listed += want
        sleep(PAUSE)
    ok = [c for c in checks if c["status"] == "ok"]
    if not ok:
        return {**prev, "schema": SCHEMA, "generatedAt": stamp, "status": "failed", "checks": checks, "stale": True} if prev else \
            {"schema": SCHEMA, "generatedAt": stamp, "status": "failed", "checks": checks, "entries": [], "events": [], "seen": []}
    for x in listed:
        old = entries.get(x["url"])
        ko, words, beat = product_ko(x["title"])
        kind = kind_of(x["title"])
        rec = {**(old or {}), **x, "kind": kind, "korea": bool(KOREA.search(x["title"])), "productKo": ko, "productWords": words, "beat": beat,
               "tier": tier_of(kind, beat), "case": case_key(x["title"]), "indexLabel": next(lb for k, lb, _ in INDEXES if k == x["index"])}
        if old is None:
            rec["baseline"] = first or x["url"] in seen
            rec["detail"] = {"read": False}
            if not rec["baseline"]:
                rec["eventPending"] = True
        entries[x["url"]] = rec
        seen.add(x["url"])
    # 상세 쪽: 새 공고(이벤트 대기) 먼저, 그다음 아직 안 읽은 한국 공고(최신순) — 기준선 공고도 조사 기간·관세 끝 날짜를 일정에 쓰려고 읽는다
    todo = sorted((e for e in entries.values() if not (e.get("detail") or {}).get("read")),
                  key=lambda e: (0 if e.get("eventPending") else 1, -int((e.get("date") or "0000-00-00").replace("-", ""))))
    budget, errors = DETAIL_BUDGET, []
    for e in todo:
        if budget <= 0:
            break
        budget -= 1
        sleep(PAUSE)
        try:
            r = get(e["url"], headers=UA, timeout=60)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")
            r.encoding = "utf-8"
            e["detail"] = {**parse_detail(r.text, e["date"]), "read": True, "readAt": stamp}
        except Exception as ex:  # noqa: BLE001
            err = str(ex)[:40] or type(ex).__name__
            e["detail"] = {**(e.get("detail") or {}), "read": False, "error": err}
            errors.append(f"{e['url'].rsplit('/', 1)[-1]} {err}")
    council, ccheck, cerrors = council_run(prev.get("council"), now, get, sleep, stamp)
    checks.append(ccheck)
    errors += cerrors
    by_id = {ev["id"]: i for i, ev in enumerate(events)}
    for m in council.get("meetings") or []:
        if m.get("baseline") or not m.get("items"):
            continue
        ev = council_event(m, stamp)
        if ev["id"] in by_id:
            old_ev = events[by_id[ev["id"]]]
            if old_ev.get("text") != ev["text"]:
                events[by_id[ev["id"]]] = {**ev, "detectedAt": old_ev.get("detectedAt", stamp), "updatedAt": stamp}
        else:
            events.append(ev)
            by_id[ev["id"]] = len(events) - 1
            fresh += 1
    for e in entries.values():
        if e.pop("eventPending", None) or (not e.get("baseline") and event_id(e) in by_id):
            ev = event_of(e, stamp)
            if ev["id"] in by_id:
                old_ev = events[by_id[ev["id"]]]
                if old_ev.get("text") != ev["text"]:
                    events[by_id[ev["id"]]] = {**ev, "detectedAt": old_ev.get("detectedAt", stamp), "updatedAt": stamp}
            else:
                events.append(ev)
                by_id[ev["id"]] = len(events) - 1
                fresh += 1
    status = "ok" if all(c["status"] == "ok" for c in checks) and not errors else "partial"
    if errors:
        checks[0]["detailErrors"] = errors[:3]
    pending = sum(1 for e in entries.values() if not (e.get("detail") or {}).get("read"))
    kept = sorted(entries.values(), key=lambda x: x.get("date") or "", reverse=True)[:KEEP_ENTRIES]
    return {"schema": SCHEMA, "generatedAt": stamp, "status": status, "checks": checks, "baselineAt": prev.get("baselineAt") or stamp,
            "entries": kept, "events": events[-80:], "seen": sorted(seen)[-400:], "fresh": fresh, "detailPending": pending, "council": council,
            "rules": ["일본 재무성 관세제도 누리집(공식, 일본어 목록). 반덤핑·상계관세는 제목에 '大韓民国'이 든 공고, 세이프가드는 출입 업종 품목만.",
                      "보도자료 본문의 세율은 범위(업체별 세율은 관보 정령·조사 보고서 원문). 일본 조사는 원칙 1년, 연장하면 최대 18개월.",
                      "첫 실행은 기준선 — 그 뒤 목록에 새로 오른 공고만 이벤트.",
                      "특수관세부회 배포자료: 한국산 안건 자료 PDF에서 '適当'(부과가 적당)·기간·출입처 이름·'…を除く'(제외 업체)만 자동으로 본다 — 세율은 원문 표."]}


def main():
    ap = argparse.ArgumentParser(description="일본 무역구제 공고(기자 전용 저장소로)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    import private_store
    now = now_kst()
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    previous = None
    if token and not a.dry_run:
        try:
            previous = private_store.get("jp-trade-remedy", token)
        except private_store.StoreError as e:
            print(f"::warning title=jp-trade-remedy-state::이전 상태 조회 실패({e}) — 이번에는 저장하지 않는다(기준선을 다시 잡지 않으려고)")
            return 0
    doc = run(now, previous)
    counts = " · ".join(f"{c['source'].split()[-1]} {c.get('returned', 0)}건(한국 {c.get('korea', 0)})" if c["status"] == "ok" else
                        f"{c['source'].split()[-1]} 실패({c.get('error', '')})" for c in doc["checks"])
    # 공개 로그에는 건수만(품목·업체·세율은 찍지 않는다)
    print(f"::notice title=jp-trade-remedy::상태 {doc['status']} · {counts} · 저장 {len(doc.get('entries') or [])} · "
          f"이번 새 공고 {doc.get('fresh', 0)} · 상세 못 읽음 {doc.get('detailPending', 0)}")
    if a.dry_run or not token:
        if not token and not a.dry_run:
            print("::warning title=jp-trade-remedy-push::MCP_ACCESS_TOKEN 미설정 — 결과를 저장하지 않음")
        return 0
    if doc["status"] == "failed" and previous:
        print("::warning title=jp-trade-remedy::목록 조회 실패 — 이전 결과 유지(0건 아님)")
    status = private_store.put("jp-trade-remedy", doc, token)
    print(f"::notice title=jp-trade-remedy-push::기자 전용 저장소 전송 HTTP {status}")
    return 0 if status == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
