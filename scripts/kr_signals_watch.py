"""국내 신호 감시: 공정위 의결서, 한전 전자입찰 공고, 원자재 가격(KOMIS).

- 공정위 의결서(case.ftc.go.kr, 열쇠 없음): 의결일 최근 120일 목록 → 처음 보는 의결서는 개방문서 전문을 읽어
  출입처·관련 기업 법인명이 피심인/발주처/본문 언급 중 어디에 나오는지와 주문 발췌를 남긴다. 이름 없는 의결서는 버린다.
- 한전 전자입찰(전력데이터개방포털 electContract, KEPCO_API_KEY): 최근 14일 공고 중 전력기기·전선 품목만. 열쇠 없으면 '미설정'.
- 산업통상부 보도·참고자료(motir.go.kr, 열쇠 없음): 최근 두 쪽에서 출입처 업종 낱말·출입처 이름이 제목에 있는 것. '○년 ○월 수출입 동향'은
  본문의 주요 품목 표에서 출입처 품목(자동차·부품·철강·비철·석유화학·이차전지·전기기기 등) 수출액·증감률을 적힌 그대로 남긴다.
- 공정위 보도·참고자료(두 쪽)와 설명자료(한 쪽)(ftc.go.kr 게시판, 열쇠 없음): 제목에 출입처 이름이나 출입 업종 낱말이 있는 것.
  정책브리핑 RSS·API가 끊겨 부처 게시판을 직접 읽는다. 이 구역 첫 실행은 기준선(신규 표시 없음).
- 기후에너지환경부·국토교통부·관세청·조달청 보도자료(정책브리핑 목록을 부처 코드로 거름, 두 쪽씩): 제목에 출입처 이름이나 부처별 업종 낱말이 있는 것.
  제목·날짜·부처·주소만 남긴다(정책브리핑이 7-1 RSS를 권리 보호로 끊음 — 요약·본문은 남기지 않음).
- 시·도 보도자료(울산광역시 세 쪽·충청남도 두 쪽): 제목에 출입처 이름, 또는 투자협약·증설·산업위기 낱말과 출입 업종 낱말이 함께 있는 것.
  러너에 따라 접속이 막히는 날이 있어 실패는 미확인(이전 줄 유지).
- 원자재 가격(KOMIS 광물자원가격, 열쇠 없음): 설정한 광종·가격 기준(LME CASH 등)의 일별 가격·LME 재고.
  같은 기준·같은 단위로만 비교하고, 설정한 since 이전 값과는 비교하지 않는다. 'N개월 만에 최고'는 조회 범위 안의 사실만.
- 결과는 기자 전용 저장소(kr-signals)로만. 공개 로그는 건수만. 조회 실패는 0건이 아니다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html as htmllib
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
SCHEMA = "kr_signals/v1"
CONFIG = ROOT / "data" / "kr_signals.json"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

FTC_LIST = "https://case.ftc.go.kr/ocp/co/ltfr.do"
FTC_TEXT = "https://case.ftc.go.kr/com/dscv/dscvHtmlView.do"
FTC_VIEW = "https://case.ftc.go.kr/ocp/co/openDocView.do"
FTC_DAYS = 120
FTC_MAX_PAGES = 30
FTC_DOC_BUDGET = 40
FTC_SEEN_KEEP = 1500

KEPCO_API = "https://bigdata.kepco.co.kr/openapi/v1/electContract.do"
KEPCO_COMPANIES = {"COM01": "한국전력공사", "COM02": "한국서부발전", "COM04": "한국남부발전", "COM05": "한국중부발전", "COM06": "한국남동발전",
                   "COM08": "한국동서발전", "COM09": "한국전력기술", "COM10": "한전KPS", "COM11": "한국전력거래소", "COM12": "한국원자력연료",
                   "COM16": "한국해상풍력", "COM19": "KAPES"}
KEPCO_STATES = {"PreAttendProgress": "공고진행", "AttendProgress": "입찰진행", "Close": "마감", "Fail": "유찰", "OpenTimed": "개찰", "Final": "공고종료"}

KOMIS = "https://www.komis.or.kr"
KOMIS_PAGE = KOMIS + "/Komis/RsrcPrice/BaseMetals"
KOMIS_CRTR = KOMIS + "/Komis/RsrcPrice/ajax/getMnrlPriceCrtr"
KOMIS_PRICE = KOMIS + "/Komis/RsrcPrice/ajax/getMnrlPrcByMnrkndUnqCd"
KEEP_ROWS = 70
EVENT_KEEP_DAYS = 120


def now_kst():
    return dt.datetime.now(KST)


class Http:
    """requests wrapper: spacing between calls, one slower retry on timeouts, failures returned as text."""

    def __init__(self, session=None, sleep=time.sleep, gap=0.6):
        if session is None:
            import requests
            session = requests.Session()
        self.s, self.sleep, self.gap = session, sleep, gap

    def call(self, method, url, *, timeout=40, **kw):
        kw.setdefault("headers", UA)
        for attempt in (1, 2):
            try:
                r = self.s.request(method, url, timeout=timeout if attempt == 1 else 70, **kw)
            except Exception as e:  # noqa: BLE001 — reported as 미확인
                self.sleep(self.gap)
                if attempt == 1 and type(e).__name__ in ("ReadTimeout", "ConnectTimeout", "ConnectionError"):
                    self.sleep(5.0)
                    continue
                return None, type(e).__name__
            self.sleep(self.gap)
            if r.status_code != 200:
                return None, f"HTTP {r.status_code}"
            return r, None
        return None, "error"


# ---------- 공정위 의결서 ----------

def _norm(text):
    t = htmllib.unescape(str(text or ""))
    t = t.replace("㈜", " (주) ").replace("(주)", " (주) ").replace("（주）", " (주) ").replace("주식회사", " 주식회사 ")
    return re.sub(r"\s+", " ", t).strip()


PARTICLE = r"(?:의|가|이|은|는|을|를|에|에게|에서|와|과|로|으로|도|만|등|및)?"
EDGE = r"(?![가-힣A-Za-z0-9])"


def name_rx(names):
    """Whole-name match: no letter/digit before, an optional particle, then no letter/digit after
    ('포스코' does not match 포스코퓨처엠·포스코이앤씨; '현대제철이' matches)."""
    alts = sorted({_norm(n) for n in names}, key=len, reverse=True)
    body = "|".join(re.escape(a).replace(r"\ ", r"\s?") for a in alts)
    return re.compile(rf"(?<![가-힣A-Za-z0-9])(?:{body}){PARTICLE}{EDGE}")


def company_patterns(cfg):
    f = cfg["ftc"]
    out = [(c, name_rx(n), False) for c, n in f["companies"].items()]
    out += [(c, name_rx(n), False) for c, n in f.get("legalOnly", {}).items()]  # LS·GS: legal forms only
    out += [(c, name_rx(n), True) for c, n in f.get("related", {}).items()]
    return out


def _input(row, name):
    m = re.search(rf'name="{name}"\s+value="([^"]*)"', row)
    return htmllib.unescape(m.group(1)).strip() if m else ""


def parse_ftc_list(text):
    body = text.split("<tbody", 1)[-1].split("</tbody>", 1)[0]
    rows = []
    for row in re.split(r"<tr[\s>]", body)[1:]:
        csno = _input(row, "csno")
        if not csno:
            continue
        view = re.search(r'fn_htmlView\(this\);"[^>]*>\s*</a>\s*<input type="hidden" value="([^"]*)">\s*<input type="hidden" value="([^"]*)">\s*'
                         r'<input type="hidden" value="([^"]*)">', row)
        rows.append({"csno": csno, "blno": _input(row, "blno"), "name": _norm(_input(row, "csname")), "action": _input(row, "ttcnts"),
                     "decidedOn": _input(row, "apdate"), "fileId": _input(row, "fileId"), "fileNm": _input(row, "fileNm"),
                     "doc": {"docId": view.group(1), "docCnvrMnNo": view.group(2), "id": view.group(3)} if view else None})
    last = re.search(r"fn_goPage\((\d+)\);\s*return false;\"[^>]*>\s*마지막", text)
    return rows, int(last.group(1)) if last else None


def file_date(file_id):
    m = re.match(r"(20\d{2})(\d{2})(\d{2})(\d{2})(\d{2})", file_id or "")
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)} {m.group(4)}:{m.group(5)}" if m else None


LABELS = re.compile(r"(사\s?건\s?명|피\s?심\s?인|사\s?건\s?번\s?호|의\s?결\s?번\s?호|신\s?청\s?인|대\s?리\s?인)(?=[가-힣A-Za-z(])(?!(?:은|는|의|이|을|를|에|들|과|와|으로|로)[\s,.])")


def doc_text(raw):
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw or "")
    # headings are glued to the next word in the open document ('사건명금호타이어(주)의…', '피 심 인금호타이어 주식회사')
    return _norm(LABELS.sub(r"\1 ", _norm(re.sub(r"(?s)<[^>]+>", " ", t))))


RESP = re.compile(r"사\s?건\s?명.{0,800}?피\s?심\s?인(.{0,6000}?)(?=심\s?의\s?종\s?결\s?일|주\s?문\s)")
ORDER = re.compile(r"주\s?문\s(.{0,4000}?)\s이\s?유\s?1\.")


def sections(text):
    """Respondent block and order block of a decision. Anchored after '사건명' so the table of contents
    ('주문 이유 1. 기초사실 … 피심인의 …') is skipped; headings may be spaced ('피 심 인', '심 의 종 결 일')."""
    resp = RESP.search(text)
    order = ORDER.search(text, resp.end() if resp else 0)
    return (resp.group(1).strip() if resp else ""), (order.group(1).strip() if order else "")


def mentions(name, text, patterns):
    resp, order = sections(text)
    out = []
    for company, rx, related in patterns:
        in_name, in_resp, in_text = rx.search(name), rx.search(resp), rx.search(text)
        if not (in_name or in_resp or in_text):
            continue
        if in_resp:
            role = "피심인"
        elif in_name and re.search(rx.pattern + r".{0,25}?발주", name):
            role = "발주처"
        elif in_name:
            role = "사건명 언급"
        else:
            role = "본문 언급"
        where = (order if rx.search(order) else resp) if role == "피심인" else text
        m = rx.search(where)
        snip = where[max(0, m.start() - 60): m.end() + 160] if m else ""
        money = []
        if role == "피심인":
            for mm in rx.finditer(order):
                tail = order[mm.end(): mm.end() + 90]
                hit = re.search(r"([\d,]{4,})\s*(백만원|천원|원)", tail)
                if hit and f"{hit.group(1)}{hit.group(2)}" not in money:
                    money.append(f"{hit.group(1)}{hit.group(2)}")
        out.append({"company": company, "role": role, "related": related, "snippet": snip.strip()[:300], "orderAmounts": money[:3]})
    return out


def flags_of(name, action):
    f = []
    if re.search(r"납부기한\s?연장|분할\s?납부", name):
        f.append("과징금 납부기한 연장·분할납부")
    if re.search(r"이의신청", name) or action in ("인용", "일부인용", "재결기각", "재결각하"):
        f.append("이의신청 재결")
    if "동의의결" in name or "동의의결" in action:
        f.append("동의의결")
    if action == "고발":
        f.append("고발")
    if re.search(r"기업결합", name):
        f.append("기업결합")
    return f


def ftc(cfg, now, previous, http):
    prev = {d["id"]: d for d in (previous or {}).get("decisions", []) if isinstance(d, dict) and d.get("id")}
    seen = set((previous or {}).get("ftcSeen", []))
    baseline = previous is None or "ftcSeen" not in (previous or {})
    stamp = now.isoformat(timespec="seconds")
    params = {"startRceptDt": (now.date() - dt.timedelta(days=FTC_DAYS)).isoformat(), "endRceptDt": now.date().isoformat()}
    rows, err, page, last = [], None, 1, None
    while page <= FTC_MAX_PAGES:
        r, err = http.call("GET", FTC_LIST, params={**params, "pageIndex": page})
        if err:
            break
        got, last_page = parse_ftc_list(r.text)
        last = last_page or last
        have = {x["csno"] for x in rows}
        if not got or all(x["csno"] in have for x in got):  # past the end (some boards repeat the last page)
            break
        rows += got
        if last and page >= last:
            break
        page += 1
    groups = {}
    for x in rows:
        did = f"ftc:{x['blno'] or x['csno']}"
        g = groups.setdefault(did, {**x, "id": did, "caseNos": []})
        g["caseNos"].append(x["csno"])
        if not g.get("doc") and x.get("doc"):
            g["doc"] = x["doc"]
    patterns = company_patterns(cfg)
    kept, budget, read, pending, doc_err = dict(prev), FTC_DOC_BUDGET, 0, 0, 0
    for did, g in groups.items():
        if did in seen or did in prev:
            if did in kept:
                kept[did] = {**kept[did], "caseNos": sorted(set(kept[did].get("caseNos", [])) | set(g["caseNos"]))}
            continue
        text, note = "", None
        if g.get("doc"):
            if budget <= 0:
                pending += 1
                continue
            budget -= 1
            r, e = http.call("GET", FTC_TEXT, params={"docId": g["doc"]["docId"], "docCnvrMnNo": g["doc"]["docCnvrMnNo"]}, timeout=60)
            if e:
                doc_err += 1
                pending += 1
                continue
            text, read = doc_text(r.text), read + 1
        else:
            note = "개방문서 없음(PDF만) — 사건명만 대조"
        found = mentions(g["name"], text, patterns)
        seen.add(did)
        if not found:
            continue
        resp, order = sections(text)
        kept[did] = {"id": did, "decisionNo": g["blno"], "caseNos": sorted(set(g["caseNos"])), "name": g["name"], "action": g["action"],
                     "decidedOn": g["decidedOn"], "fileDate": file_date(g["fileId"]), "fileNm": g["fileNm"],
                     "mentions": found, "flags": flags_of(g["name"], g["action"]), "orderExcerpt": order[:500],
                     "respondentsExcerpt": resp[:400], **({"note": note} if note else {}),
                     "url": (f"{FTC_VIEW}?docTy=LTFR&docId={g['doc']['docId']}&docCnvrMnNo={g['doc']['docCnvrMnNo']}&id={g['doc']['id']}"
                             if g.get("doc") else f"{FTC_LIST}?caseNo={g['csno']}"),
                     "firstSeen": stamp,
                     # new = posted lately (file date), not merely read late: the first runs read older decisions under the budget
                     "isNew": not baseline and (file_date(g["fileId"]) or "") >= (now.date() - dt.timedelta(days=14)).isoformat()}
    keep_from = (now.date() - dt.timedelta(days=365)).isoformat()
    decisions = sorted((d for d in kept.values() if str(d.get("decidedOn") or "") >= keep_from),
                       key=lambda d: (d.get("decidedOn") or "", d["id"]), reverse=True)
    status = "failed" if err and not rows else ("partial" if err or pending else "ok")
    check = {"source": "공정위 의결서", "status": status, "listed": len(rows), "decisions": len(groups), "read": read,
             "pending": pending, "kept": len(decisions), **({"error": err} if err else {}),
             **({"docErrors": doc_err} if doc_err else {})}
    return decisions, sorted(seen)[-FTC_SEEN_KEEP:], check


# ---------- 한전 전자입찰 ----------

def won(v):
    digits = re.sub(r"[^\d]", "", str(v or ""))
    return int(digits) if digits else None


def kepco(cfg, key, now, previous, http):
    prev = {x["id"]: x for x in (previous or {}).get("kepco", []) if isinstance(x, dict) and x.get("id")}
    if not key:
        return list(prev.values()), [], {"source": "한전 전자입찰", "status": "unset", "error": "KEPCO_API_KEY 미설정"}
    kc = cfg["kepco"]
    rx = re.compile(kc["keywords"], re.I)
    project = re.compile(kc.get("projectKeywords") or r"(?!)", re.I)
    skip = re.compile(kc.get("exclude") or r"(?!)")

    def wanted(d):
        """Equipment purchases (자재구매) for power-equipment and cable makers; construction only for HVDC/765kV-class projects."""
        name = str(d.get("name") or "")
        if skip.search(name):
            return False
        if str(d.get("purchaseType")) == "Product":
            return bool(rx.search(name))
        return bool(project.search(name))
    stamp = now.isoformat(timespec="seconds")
    fr = (now.date() - dt.timedelta(days=kc.get("windowDays", 14))).strftime("%Y%m%d")
    r, err = http.call("GET", KEPCO_API, params={"noticeBeginDate": fr, "noticeEndDate": now.date().strftime("%Y%m%d"), "apiKey": key,
                                                 "returnType": "json"}, timeout=90)
    events, kept = [], dict(prev)
    if err:
        return sorted(prev.values(), key=lambda x: x.get("noticeDate") or "", reverse=True), [], {"source": "한전 전자입찰", "status": "failed", "error": err}
    try:
        body = r.json()
        data = body.get("data") if isinstance(body, dict) else None
    except ValueError:
        data = None
    if not isinstance(data, list):
        return list(prev.values()), [], {"source": "한전 전자입찰", "status": "failed", "error": "응답 형식(data 목록 없음)"}
    for d in data:
        name = re.sub(r"\s+", " ", str(d.get("name") or "")).strip()
        if not wanted(d):
            continue
        iid = f"kepco:{d.get('companyId')}:{d.get('no')}"
        price = won(d.get("presumedPrice")) or won(d.get("presumedAmount"))
        state = KEPCO_STATES.get(str(d.get("progressState") or ""), str(d.get("progressState") or ""))
        old = prev.get(iid)
        row = {"id": iid, "no": d.get("no"), "company": KEPCO_COMPANIES.get(str(d.get("companyId")), str(d.get("companyId") or "")),
               "name": name, "price": price, "big": bool(price and price >= kc.get("bigWon", 10_000_000_000)),
               "noticeDate": str(d.get("noticeDate") or "")[:8], "closeAt": str(d.get("bidAttendReqCloseDatetime") or "")[:12],
               "state": state, "purchaseType": d.get("purchaseType"), "competition": d.get("competitionType"), "bidType": d.get("bidType"),
               "place": d.get("placeName"), "delivery": str(d.get("deliveryLocation") or "")[:80],
               "files": [str(d.get(f"filename{i}")) for i in range(1, 6) if d.get(f"filename{i}")][:5],
               "firstSeen": (old or {}).get("firstSeen") or stamp, "isNew": bool(previous) and old is None}
        if old and old.get("state") != state:
            events.append({"id": f"{iid}:{state}", "kind": "한전 입찰 상태 변화", "company": row["company"], "detectedAt": stamp,
                           "text": f"{name} · {old.get('state')} → {state}" + (f" · 추정가격 {price:,}원" if price else "")})
        kept[iid] = row
    keep_from = (now.date() - dt.timedelta(days=EVENT_KEEP_DAYS)).strftime("%Y%m%d")
    rows = sorted((x for x in kept.values() if (x.get("noticeDate") or "") >= keep_from), key=lambda x: x.get("noticeDate") or "", reverse=True)
    return rows, events, {"source": "한전 전자입찰", "status": "ok", "returned": len(data), "kept": sum(1 for d in data if wanted(d))}


# ---------- 원자재 가격(KOMIS) ----------

def _f(v):
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def komis_rows(body, since):
    rows = []
    for x in ((body or {}).get("data") or {}).get("defaultMnrl") or []:
        d = str(x.get("crtrYmd") or "")
        p = _f(x.get("cmercPrc"))
        if len(d) != 8 or p is None or p <= 0:
            continue
        day = f"{d[:4]}-{d[4:6]}-{d[6:]}"
        if day < since:
            continue
        rows.append({"date": day, "price": p, "stock": _f(x.get("invt")) or None})
    return sorted(rows, key=lambda r: r["date"], reverse=True)


def pct(a, b):
    return round((a - b) / b * 100, 2) if a is not None and b else None


def record(rows, key, *, high=True):
    """Latest value vs history: the last earlier date at or beyond it (for '그 날 이후 최고'), or None if it is a range record."""
    cur = rows[0][key]
    for r in rows[1:]:
        v = r[key]
        if v is not None and ((v >= cur) if high else (v <= cur)):
            return r
    return None


def price_signals(c, rows, rules):
    """Explicit, checkable statements only: 'since D (that day's value) the highest/lowest', one-month moves, LME stock moves."""
    if len(rows) < 2:
        return {}, []
    out = []
    latest = rows[0]
    gap = rules.get("recordGapDays", 90)
    span_days = (dt.date.fromisoformat(latest["date"]) - dt.date.fromisoformat(rows[-1]["date"])).days
    for high in (True, False):
        prior = record(rows, "price", high=high)
        word = "최고" if high else "최저"
        if prior is None and span_days >= gap:
            out.append({"kind": f"조회 범위 {word}", "text": f"{c['since']} 이후 {word}(조회 범위 안)"})
        elif prior is not None:
            days = (dt.date.fromisoformat(latest["date"]) - dt.date.fromisoformat(prior["date"])).days
            if days >= gap and prior is not rows[1]:
                out.append({"kind": f"{word}(기간)", "text": f"{prior['date']}({prior['price']:,.2f}) 이후 {word} — {days}일 만"})
    n = rules.get("monthRows", 21)
    month = rows[n] if len(rows) > n else None
    mchg = pct(latest["price"], month["price"]) if month else None
    if mchg is not None and abs(mchg) >= rules.get("monthMovePct", 10):
        out.append({"kind": "한 달 큰 변동", "text": f"{month['date']} 대비 {mchg:+.1f}%"})
    schg = None
    if c.get("lme") and month and latest.get("stock") and month.get("stock"):
        schg = pct(latest["stock"], month["stock"])
        if schg is not None and abs(schg) >= rules.get("stockMovePct", 25):
            out.append({"kind": "LME 재고 큰 변동", "text": f"재고 {month['stock']:,.0f} → {latest['stock']:,.0f}({schg:+.1f}%, {month['date']} 대비)"})
    week = rows[5] if len(rows) > 5 else None
    year_start = next((r for r in reversed(rows) if r["date"][:4] == latest["date"][:4]), None)
    summary = {"date": latest["date"], "price": latest["price"], "stock": latest.get("stock"),
               "day": pct(latest["price"], rows[1]["price"]), "week": pct(latest["price"], week["price"]) if week else None,
               "month": mchg, "monthFrom": month["date"] if month else None, "ytd": pct(latest["price"], year_start["price"]) if year_start else None,
               "ytdFrom": year_start["date"] if year_start else None, "stockMonth": schg,
               "high": max(rows, key=lambda r: r["price"]), "low": min(rows, key=lambda r: r["price"]), "span": [rows[-1]["date"], latest["date"]]}
    return summary, out


def komis(cfg, now, previous, http):
    prev = {x["id"]: x for x in (previous or {}).get("prices", []) if isinstance(x, dict) and x.get("id")}
    prev_events = [e for e in (previous or {}).get("events", []) if isinstance(e, dict)]
    stamp = now.isoformat(timespec="seconds")
    rules = cfg.get("priceSignals", {})
    r, err = http.call("GET", KOMIS_PAGE)  # session cookie
    hdr = {**UA, "X-Requested-With": "XMLHttpRequest", "Referer": KOMIS_PAGE}
    prices, events, checks = [], [], []
    for c in cfg["commodities"]:
        old = prev.get(c["id"])
        try:
            if err:
                raise RuntimeError(err)
            cr, e = http.call("POST", KOMIS_CRTR, data={"HP000": c["group"], "mnrkndUnqCd": c["code"]}, headers=hdr)
            if e:
                raise RuntimeError(e)
            crtr = next((x for x in (cr.json().get("data") or []) if str(x.get("cdVal", "")).startswith(c["basis"])), None)
            if not crtr:
                raise RuntimeError(f"가격 기준 '{c['basis']}' 없음")
            y0 = c["since"][:4]
            pr, e = http.call("POST", KOMIS_PRICE, headers=hdr, timeout=60, data={
                "mnrkndUnqRadioCd": c["code"], "srchMnrkndUnqCd": c["code"], "srchPrcCrtr": crtr["cdKey"], "srchAvgOpt": "DAY",
                "srchField": "year", "srchStartDate": y0, "srchEndDate": str(now.year), "srchCompareMnrkndUnqCd": "",
                "lmeInvt": "Y" if c.get("lme") else "N"})
            if e:
                raise RuntimeError(e)
            body = pr.json()
            info = ((body.get("dataAvg") or {}).get("INFO") or ((body.get("dataAvg") or {}).get("stdMap") or {}).get("INFO") or {})
            rows = komis_rows(body, c["since"])
            if not rows:
                raise RuntimeError("가격 행 없음")
        except Exception as ex:  # noqa: BLE001 — 미확인
            checks.append({"source": f"KOMIS {c['name']}", "status": "failed", "error": str(ex)[:120]})
            if old:
                prices.append({**old, "stale": True})
            continue
        summary, sig = price_signals(c, rows, rules)
        unit = f"{info.get('prcUnitCdNm') or ''}/{info.get('weigUnitCd') or ''}".strip("/")
        prices.append({"id": c["id"], "name": c["name"], "basis": crtr["cdVal"], "basisDetail": info.get("prcCrtr"), "source": info.get("archNm"),
                       "unit": unit, "beats": c.get("beats", []), "since": c["since"], "sinceNote": c.get("sinceNote"),
                       "summary": summary, "signals": sig, "rows": rows[:KEEP_ROWS]})
        checks.append({"source": f"KOMIS {c['name']}", "status": "ok", "rows": len(rows), "latest": rows[0]["date"]})
        repeat = dt.timedelta(days=rules.get("repeatDays", 14))
        for s in sig:
            recent = any(e.get("commodity") == c["id"] and e.get("signal") == s["kind"] and
                         now - dt.datetime.fromisoformat(e["detectedAt"]) < repeat for e in prev_events + events)
            if recent:
                continue
            events.append({"id": f"px:{c['id']}:{s['kind']}:{rows[0]['date']}", "kind": "원자재 가격", "signal": s["kind"], "commodity": c["id"],
                           "company": "·".join(c.get("beats", [])), "detectedAt": stamp, "priceDate": rows[0]["date"],
                           "text": f"{c['name']}({crtr['cdVal']}, {unit}) {rows[0]['price']:,.2f} · {s['text']}"})
    return prices, events, checks


# ---------- 산업통상부 보도·참고자료 ----------

MOTIR = "https://www.motir.go.kr"
MOTIR_LIST = MOTIR + "/kor/article/ATCL3f49a5a8c"
MOTIR_PAGES = 2
MOTIR_KEEP_DAYS = 60
TOPIC = re.compile(r"자동차|완성차|부품|모빌리티|미래차|전기차|수소차|철강|강판|강관|철근|아연|비철|구리|알루미늄|광물|희토류|전력|변압기|전선|케이블|송전|"
                   r"전력망|원전|원자력|수소|석유화학|화학|석유|정유|나프타|에틸렌|원유|국제유가|정제마진|배터리|이차전지|무역위|덤핑|상계|세이프가드|관세|통상|수출입|공급망|타이어|소재")
TRADE_TITLE = re.compile(r"^(\d{4})년\s*(\d{1,2})월\s*수출입\s*동향$")
# 출입 업종 낱말이 있어도 업종 밖인 보도자료(10-31 운영: 「통상교섭본부장, K-콘텐츠 기업과…」·「글로벌 화학 기업 독일 머크, 대전 바이오
# 원부자재…」·「자동차·가전부터 한우·수산물까지…최대 50% 할인」이 출입 업종으로 잡혔다). 출입처 이름이 나오면 그대로 둔다.
OFF_BEAT = re.compile(r"콘텐츠|바이오|제약|의약|한우|수산물|농식품|관광|게임|뷰티|페스티벌|할인\s*행사|사회공헌")
NOT_TOPIC = re.compile(r"통상교섭본부장|통상차관보")  # 직함 속 '통상'은 업종 낱말이 아니다


def motir_topic(title):
    return bool(TOPIC.search(NOT_TOPIC.sub(" ", title))) and not OFF_BEAT.search(title)
TRADE_ITEMS = ("자동차", "자동차부품", "철강", "비철금속", "석유화학", "석유제품", "이차전지", "전기기기", "일반기계", "선박")


def parse_motir_list(text):
    """Server HTML of the board (the data-cell-header labels are added later by the page script, so cells are read by position:
    번호, 분류, 제목, 담당부서, 등록일, 조회수, 첨부파일)."""
    body = text.split("<tbody", 1)[-1].split("</tbody>", 1)[0]
    rows = []
    for row in re.split(r"<tr[\s>]", body)[1:]:
        link = re.search(r'<a href="(/kor/article/ATCL3f49a5a8c/(\d+)/view)[^"]*"[^>]*>(.*?)</a>', row, re.S)
        if not link:
            continue
        cells = [_norm(re.sub(r"(?s)<[^>]+>", " ", c)) for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        di = next((i for i, c in enumerate(cells) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", c)), None)
        kind = re.search(r'class="badge-category"[^>]*>\s*<i>([^<]+)</i>', row)
        attach = re.search(r'<a href="/attach/down/[^"]+" title="([^"]+)"', row)
        att = htmllib.unescape(attach.group(1)) if attach else ""
        embargo = re.search(r"\(([^()]{0,60}(?:조간|석간|엠바고)[^()]{0,60}(?:\([^()]*\)[^()]{0,40})*)\)", att)
        rows.append({"id": f"motir:{link.group(2)}", "title": _norm(re.sub(r"(?s)<[^>]+>", " ", link.group(3))),
                     "kind": kind.group(1).strip() if kind else "", "dept": cells[di - 1] if di else "", "date": cells[di] if di is not None else "",
                     "url": MOTIR + link.group(1), "embargo": embargo.group(1)[:120] if embargo else None})
    return rows


def _tight(t):
    """11-01 '10월 수출입 동향'부터 본문이 낱말마다 태그로 쪼개져 '10 월 수출 1,153 억 달러 (+93.7%) ,'·'( △ 44)'처럼 띄어 나온다.
    9월까지의 붙은 형식('9월 수출 1,209.4억 달러(+83.5%),')으로 되돌린다."""
    t = re.sub(r"(\d)\s+월", r"\1월", t)
    t = re.sub(r"\s*억\s*달러", "억 달러", t)
    t = re.sub(r"\(\s+", "(", t)
    t = re.sub(r"\s+\)", ")", t)
    t = re.sub(r"달러\s+\(", "달러(", t)
    t = re.sub(r"\s+([,%])", r"\1", t)
    return re.sub(r"△\s+", "△", t)


def parse_trade(text):
    """'○년 ○월 수출입 동향' body: totals and the main-items table (names then '값 (증감)' cells, in the same order)."""
    t = _tight(_norm(text))
    out = {}
    tot = re.search(r"\*\s*\d{1,2}월\s*수출\s*([\d,.]+)억\s*달러\(([+△\-]?[\d.]+)%\),\s*수입\s*([\d,.]+)억\s*달러\(([+△\-]?[\d.]+)%\)", t)
    if tot:
        out["exports"] = {"value": tot.group(1), "yoy": tot.group(2).replace("△", "-")}
        out["imports"] = {"value": tot.group(3), "yoy": tot.group(4).replace("△", "-")}
    seg = re.search(r"【\s*\d{1,2}월\s*\d+\s*대\s*주요\s*품목별\s*수출액[^】]*】(.*?)(?:\(IT\)|【)", t)
    items = {}
    if seg:
        chunk = seg.group(1).replace("총 수출액", "총수출액")
        chunk = re.sub(r"([\d,.]+)\s+([+△\-][\d.]+)\s*$", r"\1 (\2)", chunk.strip())  # 10월: 끝의 총 수출액이 '1,153 +94'(괄호 없음)
        names = re.findall(r"[가-힣]+", re.sub(r"[\d,.]+\s*\([+△\-]?[\d.]+\)", " ", chunk))
        vals = re.findall(r"([\d,.]+)\s*\(([+△\-]?[\d.]+)\)", chunk)
        if names and len(names) == len(vals):
            for n, (v, y) in zip(names, vals):
                if n in TRADE_ITEMS:
                    items[n] = {"value": v, "yoy": y.replace("△", "-")}
        else:
            out["tableError"] = f"표 해석 실패(이름 {len(names)}·값 {len(vals)})"
    for n in TRADE_ITEMS:  # prose fallback: '자동차(60.5억 달러, △5.5%)'
        if n in items:
            continue
        m = re.search(rf"(?<![가-힣]){n}(?:\s*수출)?\s*\(([\d,.]+)억\s*달러,\s*([+△\-]?[\d.]+)%\)", t)
        if m:
            items[n] = {"value": m.group(1), "yoy": m.group(2).replace("△", "-"), "from": "본문"}
    out["items"] = items
    return out


def motir(cfg, now, previous, http):
    prev = {x["id"]: x for x in (previous or {}).get("motir", []) if isinstance(x, dict) and x.get("id")}
    stamp = now.isoformat(timespec="seconds")
    patterns = company_patterns(cfg)
    rows, err = [], None
    for page in range(1, MOTIR_PAGES + 1):
        r, err = http.call("GET", MOTIR_LIST, params={"pageIndex": page})
        if err:
            break
        got = parse_motir_list(r.text)
        if not got:
            if page == 1:
                err = "목록 형식(행 없음)"  # the first page always has rows; later pages may simply end
            break
        rows += got
    kept = dict(prev)
    for x in rows:
        trade = TRADE_TITLE.match(x["title"])
        names = sorted({c for c, rx, _ in patterns if rx.search(x["title"])})
        if not (trade or names or motir_topic(x["title"])):
            continue
        old = prev.get(x["id"])
        row = {**x, "companies": names, "trade": (old or {}).get("trade"), "firstSeen": (old or {}).get("firstSeen") or stamp,
               "isNew": bool(previous) and old is None}
        stale = row["trade"] and (row["trade"].get("error") or row["trade"].get("tableError") or not row["trade"].get("exports"))
        if trade and (not row["trade"] or stale):  # 해석 실패·조회 실패분은 다음 실행에서 다시 읽는다
            d, e = http.call("GET", x["url"])
            row["trade"] = {"period": f"{trade.group(1)}-{int(trade.group(2)):02d}", **(parse_trade(re.sub(r"(?s)<[^>]+>", " ", d.text)) if not e else {"error": e})}
        kept[x["id"]] = row
    keep_from = (now.date() - dt.timedelta(days=MOTIR_KEEP_DAYS)).isoformat()
    # 예전 실행이 남긴 업종 밖 줄도 같은 기준으로 다시 거른다
    items = sorted((x for x in kept.values() if str(x.get("date") or "") >= keep_from
                    and (TRADE_TITLE.match(str(x.get("title") or "")) or x.get("companies") or motir_topic(str(x.get("title") or "")))),
                   key=lambda x: (x.get("date") or "", x["id"]), reverse=True)
    status = "failed" if err and not rows else ("partial" if err else "ok")
    return items, {"source": "산업통상부 보도자료", "status": status, "listed": len(rows), "kept": sum(1 for x in items if x["id"] in {r["id"] for r in rows}),
                   **({"error": err} if err else {})}


# ---------- 공정위 보도·참고·설명자료 ----------
# 정책브리핑(korea.kr) RSS는 2026-07-01 중단, 공공데이터포털 정책브리핑 API(policyNewsService2)는 '서비스 없거나 폐기됨'(코드 12, 11-01 확인)이라
# 공정위 누리집 게시판 목록 첫 쪽들을 직접 읽는다(robots.txt는 /www/search.do만 막음). 보도자료는 보통 의결서 공개보다 몇 달 먼저 나온다.

FTC_HOME = "https://www.ftc.go.kr/www/"
FTC_PRESS = FTC_HOME + "selectBbsNttList.do"
FTC_PRESS_VIEW = FTC_HOME + "selectBbsNttView.do"
FTC_BOARDS = (("12", "01,02", 2, "보도·참고자료"), ("13", "03", 1, "설명자료"))  # key, searchCtgry, 읽을 쪽 수, 이름
FTC_PRESS_KEEP_DAYS = 60
FTC_TOPIC = re.compile(r"자동차|완성차|차량|부품|철강|강판|강관|철근|고철|비철|아연|구리|전력|변압기|전선|케이블|"
                       r"석유화학|화학|석유|정유|타이어|배터리|이차전지|수소|원전")
_COMMENT = re.compile(r"(?s)<!--.*?-->")


def _cell(html):
    return _norm(re.sub(r"(?s)<[^>]+>", " ", _COMMENT.sub(" ", html)))


def parse_ftc_press(text, key, ctg):
    """공정위 게시판 목록(서버 HTML): 번호, 분류(보도·참고·설명), 제목, 담당부서, 등록일, 첨부."""
    body = text.split("<tbody", 1)[-1].split("</tbody>", 1)[0]
    rows = []
    for row in re.split(r"<tr[\s>]", body)[1:]:
        link = re.search(r'<a href="\./selectBbsNttView\.do\?[^"]*?nttSn=(\d+)[^"]*"[^>]*>(.*?)</a>', row, re.S)
        if not link:
            continue
        cells = [_cell(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        di = next((i for i, c in enumerate(cells) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", c)), None)
        title = re.sub(r"^\d{6,8}\s+", "", _cell(link.group(2)))  # 설명자료 앞의 '20261029 ' 같은 날짜
        rows.append({"id": f"ftcpress:{link.group(1)}", "title": title, "kind": cells[1] if len(cells) > 1 else "",
                     "dept": cells[di - 1] if di else "", "date": cells[di] if di is not None else "",
                     "url": f"{FTC_PRESS_VIEW}?bordCd=3&key={key}&searchCtgry={ctg}&nttSn={link.group(1)}"})
    return rows


def ftc_press(cfg, now, previous, http):
    had = isinstance((previous or {}).get("ftcPress"), list)  # 이 구역 첫 실행은 모두 기준선(신규 표시 없음)
    prev = {x["id"]: x for x in (previous or {}).get("ftcPress", []) if isinstance(x, dict) and x.get("id")}
    stamp = now.isoformat(timespec="seconds")
    patterns = company_patterns(cfg)
    rows, errs, seen = [], [], set()
    for key, ctg, pages, label in FTC_BOARDS:
        for page in range(1, pages + 1):
            r, err = http.call("GET", FTC_PRESS, params={"bordCd": "3", "key": key, "searchCtgry": ctg, "pageIndex": page})
            if err:
                errs.append(f"{label} {err}")
                break
            got = [x for x in parse_ftc_press(r.text, key, ctg) if x["id"] not in seen]
            if not got:
                if page == 1:
                    errs.append(f"{label} 목록 형식(행 없음)")  # 첫 쪽에는 늘 글이 있다
                break
            seen.update(x["id"] for x in got)
            rows += got
    kept = dict(prev)
    for x in rows:
        names = sorted({c for c, rx, rel in patterns if not rel and rx.search(x["title"])})
        related = sorted({c for c, rx, rel in patterns if rel and rx.search(x["title"])} - set(names))
        if not (names or related or FTC_TOPIC.search(x["title"])):
            continue
        old = prev.get(x["id"])
        kept[x["id"]] = {**x, "companies": names, "related": related, "firstSeen": (old or {}).get("firstSeen") or stamp,
                         "isNew": had and old is None}
    keep_from = (now.date() - dt.timedelta(days=FTC_PRESS_KEEP_DAYS)).isoformat()
    items = sorted((x for x in kept.values() if str(x.get("date") or "") >= keep_from),
                   key=lambda x: (x.get("date") or "", x["id"]), reverse=True)
    status = "failed" if errs and not rows else ("partial" if errs else "ok")
    listed = {x["id"] for x in rows}
    return items, {"source": "공정위 보도자료", "status": status, "listed": len(rows), "kept": sum(1 for x in items if x["id"] in listed),
                   **({"error": "; ".join(errs)} if errs else {})}


# ---------- 정책브리핑 부처별 보도자료(기후에너지환경부·국토교통부·관세청·조달청 — data/kr_signals.json briefing) ----------
# 부처 누리집이 GitHub 러너에서 막힌 곳(me.go.kr 접속 실패)은 정책브리핑 목록 쪽을 부처 코드로 걸러 읽는다(robots.txt 전부 허용).
# 정책브리핑은 2026-07-01 RSS를 '저작권 등 권리 보호'로 끊었다 — 제목·날짜·부처·주소만 남기고 본문·요약은 남기지 않는다.

BRIEFING = "https://www.korea.kr"
BRIEFING_LIST = BRIEFING + "/briefing/pressReleaseList.do"
BRIEFING_KEEP_DAYS = 60
_BRIEF_ROW = re.compile(r'<a href="/briefing/pressReleaseView\.do\?newsId=(\d+)[^"]*"[^>]*>(.*?)</a>', re.S)


def parse_briefing(text):
    rows = []
    for m in _BRIEF_ROW.finditer(text):
        inner = m.group(2)
        title = re.search(r"<strong[^>]*>(.*?)</strong>", inner, re.S)
        src = re.search(r'<span class="source">\s*<span>\s*([\d.\-]+)\s*</span>\s*<span>\s*([^<]+?)\s*</span>', inner, re.S)
        if not (title and src):
            continue
        rows.append({"id": f"briefing:{m.group(1)}", "title": _cell(title.group(1)), "date": src.group(1).replace(".", "-"),
                     "ministry": _norm(src.group(2)), "url": f"{BRIEFING}/briefing/pressReleaseView.do?newsId={m.group(1)}"})
    return rows


def briefing(cfg, now, previous, http):
    bc = cfg.get("briefing") or {}
    prev = {x["id"]: x for x in (previous or {}).get("briefing", []) if isinstance(x, dict) and x.get("id")}
    # 부처마다 처음 읽은 실행은 기준선(신규 표시 없음) — 11-01 관세청·조달청을 더하자 첫 실행 줄이 [신규]로 떴다.
    # briefingRead가 없던 예전 결과는 저장된 줄의 부처를 이미 읽은 부처로 본다.
    seen_before = set((previous or {}).get("briefingRead") or []) | {x.get("ministry") for x in prev.values()}
    read_ok = set()
    stamp = now.isoformat(timespec="seconds")
    patterns = company_patterns(cfg)
    rows, errs = [], []
    topics = {}
    for mi in bc.get("ministries", []):
        topics[mi["name"]] = re.compile(mi["topic"])
        for page in range(1, int(bc.get("pages", 2)) + 1):
            r, err = http.call("GET", BRIEFING_LIST, params={"repCodeType": mi["code"][0], "repCode": mi["code"], "pageIndex": page})
            if err:
                errs.append(f"{mi['name']} {err}")
                break
            got = parse_briefing(r.text)
            wrong = [x for x in got if x["ministry"] != mi["name"]]
            if page == 1 and (not got or wrong):  # 거르기가 풀리면 다른 부처가 섞여 나온다 — 그 쪽은 버리고 미확인
                errs.append(f"{mi['name']} 목록 형식({'행 없음' if not got else '다른 부처 섞임'})")
                break
            rows += [x for x in got if x["ministry"] == mi["name"]]
            read_ok.add(mi["name"])
            if not got:
                break
    def on_topic(x):  # 업종 낱말이 있어도 할인 행사·한우 같은 업종 밖 공동 보도자료는 뺀다(산업부 구역과 같은 기준)
        t = topics.get(x.get("ministry"))
        title = str(x.get("title") or "")
        return bool(t and t.search(title)) and not OFF_BEAT.search(title)

    kept = dict(prev)
    for x in rows:
        names = sorted({c for c, rx, rel in patterns if not rel and rx.search(x["title"])})
        if not (names or on_topic(x)):
            continue
        old = prev.get(x["id"])
        kept[x["id"]] = {**x, "companies": names, "firstSeen": (old or {}).get("firstSeen") or stamp,
                         "isNew": x["ministry"] in seen_before and old is None}
    keep_from = (now.date() - dt.timedelta(days=BRIEFING_KEEP_DAYS)).isoformat()

    # 설정 낱말을 좁히면 예전 실행이 남긴 줄도 같은 기준으로 다시 거른다
    items = sorted((x for x in kept.values() if str(x.get("date") or "") >= keep_from and (x.get("companies") or on_topic(x))),
                   key=lambda x: (x.get("date") or "", x["id"]), reverse=True)
    listed = {x["id"] for x in rows}
    status = "unset" if not bc.get("ministries") else ("failed" if errs and not rows else ("partial" if errs else "ok"))
    return items, {"source": "정책브리핑 부처 보도자료", "status": status, "listed": len(rows), "kept": sum(1 for x in items if x["id"] in listed),
                   "read": sorted(n for n in seen_before | read_ok if n), **({"error": "; ".join(errs)} if errs else {})}


# ---------- 시·도 보도자료(울산·충남 — data/kr_signals.json provinces) ----------
# 출입처 공장이 있는 시·도는 투자협약·증설·산업위기 대응을 회사 공시·중앙 보도보다 먼저 발표하기도 한다. 제목·날짜·부서·주소만 남긴다.
# 러너에 따라 접속이 막히는 날이 있다(11-01 probe 87·88) — 실패한 시·도는 미확인, 이전 줄 유지.


def parse_province(text, site):
    body = text.split("<tbody", 1)[-1].split("</tbody>", 1)[0]
    rows = []
    for row in re.split(r"<tr[\s>]", body)[1:]:
        link = re.search(rf'<a[^>]+href="([^"]*[?&](?:amp;)?{re.escape(site["idParam"])}=(\d+)[^"]*)"[^>]*>(.*?)</a>', row, re.S)
        if not link:
            continue
        cells = [_cell(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        di = next((i for i, c in enumerate(cells) if re.fullmatch(r"\d{4}[.\-]\d{2}[.\-]\d{2}", c)), None)
        rows.append({"id": f"province:{site['name']}:{link.group(2)}", "site": site["name"], "title": _cell(link.group(3)),
                     "dept": cells[di - 1] if di else "", "date": cells[di].replace(".", "-") if di is not None else "",
                     "url": urljoin(site["list"], htmllib.unescape(link.group(1)))})
    return rows


def province(cfg, now, previous, http):
    pc = cfg.get("provinces") or {}
    prev = {x["id"]: x for x in (previous or {}).get("province", []) if isinstance(x, dict) and x.get("id")}
    seen_before = set((previous or {}).get("provinceRead") or []) | {x.get("site") for x in prev.values()}
    invest, industry = re.compile(pc.get("invest") or r"(?!)"), re.compile(pc.get("industry") or r"(?!)")
    stamp = now.isoformat(timespec="seconds")
    patterns = company_patterns(cfg)
    rows, errs, read_ok = [], [], set()
    for site in pc.get("sites", []):
        got_ids = set()
        for page in range(1, int(site.get("pages", 1)) + 1):
            r, err = http.call("GET", site["list"], params={"pageIndex": page} if page > 1 else None, timeout=30)
            if err:
                errs.append(f"{site['name']} {err}")
                break
            got = [x for x in parse_province(r.text, site) if x["id"] not in got_ids]
            if not got:
                if page == 1:
                    errs.append(f"{site['name']} 목록 형식(행 없음)")
                break  # 쪽 번호가 무시되면 같은 줄만 다시 온다
            got_ids.update(x["id"] for x in got)
            rows += got
            read_ok.add(site["name"])

    def on_topic(x):
        t = str(x.get("title") or "")
        return bool(invest.search(t) and industry.search(t)) and not OFF_BEAT.search(t)

    kept = dict(prev)
    for x in rows:
        names = sorted({c for c, rx, rel in patterns if not rel and rx.search(x["title"])})
        if not (names or on_topic(x)):
            continue
        old = prev.get(x["id"])
        kept[x["id"]] = {**x, "companies": names, "firstSeen": (old or {}).get("firstSeen") or stamp,
                         "isNew": x["site"] in seen_before and old is None}
    keep_from = (now.date() - dt.timedelta(days=BRIEFING_KEEP_DAYS)).isoformat()
    items = sorted((x for x in kept.values() if str(x.get("date") or "") >= keep_from and (x.get("companies") or on_topic(x))),
                   key=lambda x: (x.get("date") or "", x["id"]), reverse=True)
    listed = {x["id"] for x in rows}
    status = "unset" if not pc.get("sites") else ("failed" if errs and not rows else ("partial" if errs else "ok"))
    return items, {"source": "시·도 보도자료", "status": status, "listed": len(rows), "kept": sum(1 for x in items if x["id"] in listed),
                   "read": sorted(n for n in seen_before | read_ok if n), **({"error": "; ".join(errs)} if errs else {})}


# ---------- run ----------

def run(cfg, *, now, previous=None, http=None, kepco_key=""):
    http = http or Http()
    stamp = now.isoformat(timespec="seconds")
    decisions, seen, fcheck = ftc(cfg, now, previous, http)
    bids, bid_events, kcheck = kepco(cfg, kepco_key, now, previous, http)
    prices, px_events, pchecks = komis(cfg, now, previous, http)
    releases, mcheck = motir(cfg, now, previous, http)
    press, pcheck = ftc_press(cfg, now, previous, http)
    briefs, bcheck = briefing(cfg, now, previous, http)
    provs, rcheck = province(cfg, now, previous, http)
    checks = [fcheck, kcheck, mcheck, pcheck, bcheck, rcheck, *pchecks]
    keep_from = (now - dt.timedelta(days=EVENT_KEEP_DAYS)).isoformat()
    events = [e for e in (previous or {}).get("events", []) if isinstance(e, dict) and e.get("detectedAt", "") >= keep_from]
    have = {e.get("id") for e in events}
    events += [e for e in bid_events + px_events if e["id"] not in have]
    events.sort(key=lambda e: e["detectedAt"], reverse=True)
    failed = [c for c in checks if c["status"] not in ("ok", "unset")]
    return {"schema": SCHEMA, "generatedAt": stamp, "status": "partial" if failed else "complete", "checks": checks,
            "baselineSince": (previous or {}).get("baselineSince") or stamp,
            "decisions": decisions, "ftcSeen": seen, "kepco": bids, "motir": releases, "ftcPress": press, "briefing": briefs, "briefingRead": bcheck.get("read", []),
            "province": provs, "provinceRead": rcheck.get("read", []), "prices": prices, "events": events[:400],
            "rules": ["공정위 의결서는 의결일과 파일 등록(파일번호 앞자리)이 다르다. 보도자료는 보통 의결 전후에 먼저 나오니 news_check로 선행 보도를 본다.",
                      "'발주처'는 출입처가 입찰을 낸 쪽(피해·구매자)이라는 뜻이다. 제재 대상(피심인)과 섞어 쓰지 않는다.",
                      "주문 발췌의 금액은 의결서에 적힌 그대로다. 합계·감경 전후는 원문에서 확인한다.",
                      "한전 공고의 추정가격은 발주 예정 금액이다. 낙찰 금액·낙찰사가 아니다.",
                      "공정위 보도·참고자료는 공개 발표다(의결서보다 먼저 나온다). 설명자료는 기사에 대한 공정위 해명이다. 단독 근거가 아니다.",
                      "정책브리핑 부처 보도자료(기후에너지환경부·국토교통부·관세청·조달청)도 공개 발표다. 제목만 남긴다 — 내용·수치는 원문에서 확인한다.",
                      "시·도 보도자료(울산·충남)는 지자체 발표다. 투자 규모·일정은 회사 확인 전 지자체 주장으로 쓴다.",
                      "산업통상부 보도자료는 공개 발표다. 단독 근거가 아니라 확인할 공식 변화이며, 첨부 파일명의 엠바고(조간·석간)를 지킨다.",
                      "원자재 가격은 KOMIS 게시값(같은 가격 기준·단위)이다. '이후 최고'는 조회 범위 안의 사실이고, 역대 최고가 아니다.",
                      "조회 실패는 0건이 아니라 미확인."],
            "confirmedScoops": 0}


def main():
    argparse.ArgumentParser(description="공정위 의결서·보도자료·한전 입찰·산업부 보도자료·원자재 가격 감시(기자 전용 저장소로)").parse_args()
    now = now_kst()
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    import private_store
    previous = None
    if token:
        try:
            previous = private_store.get("kr-signals", token)
        except private_store.StoreError as e:
            print(f"::warning title=kr-signals-state::이전 상태 조회 실패({e}) — 새 의결서 판단은 다음 실행부터")
    if private_store.late_scheduled_duplicate(previous, now):
        return
    doc = run(cfg, now=now, previous=previous, kepco_key=os.environ.get("KEPCO_API_KEY", "").strip())
    f = next(c for c in doc["checks"] if c["source"] == "공정위 의결서")
    k = next(c for c in doc["checks"] if c["source"] == "한전 전자입찰")
    p = [c for c in doc["checks"] if c["source"].startswith("KOMIS ")]
    m = next(c for c in doc["checks"] if c["source"] == "산업통상부 보도자료")
    fp = next(c for c in doc["checks"] if c["source"] == "공정위 보도자료")
    bp = next(c for c in doc["checks"] if c["source"] == "정책브리핑 부처 보도자료")
    rp = next(c for c in doc["checks"] if c["source"] == "시·도 보도자료")
    new_ev = sum(1 for e in doc["events"] if e["detectedAt"] == doc["generatedAt"])
    print(f"::notice title=kr-signals::공정위 의결서 {f['status']} 목록 {f.get('listed', 0)}건·의결 {f.get('decisions', 0)}건·전문 {f.get('read', 0)}건 읽음·"
          f"대기 {f.get('pending', 0)}·출입처 관련 {f.get('kept', 0)}건 · 한전 {k['status']} {k.get('kept', 0)}/{k.get('returned', 0)} · "
          f"산업부 {m['status']} {m.get('kept', 0)}/{m.get('listed', 0)} · 공정위 보도 {fp['status']} {fp.get('kept', 0)}/{fp.get('listed', 0)} · 부처 보도 {bp['status']} {bp.get('kept', 0)}/{bp.get('listed', 0)} · 시·도 보도 {rp['status']} {rp.get('kept', 0)}/{rp.get('listed', 0)} · 원자재 {sum(1 for c in p if c['status'] == 'ok')}/{len(p)} · 새 이벤트 {new_ev}")
    errors = sorted({c.get("error") for c in doc["checks"] if c.get("error")})
    if errors:
        print(f"::notice title=kr-signals-errors::{', '.join(errors)[:400]}")
    if not token:
        print("::warning title=kr-signals-push::MCP_ACCESS_TOKEN 미설정 — 결과를 저장하지 않음")
        return
    if f["status"] == "failed" and not any(c["status"] == "ok" for c in p):
        sys.exit("모든 질의 실패 — 이전 결과 유지(0건 아님)")
    status = private_store.put("kr-signals", doc, token)
    print(f"::notice title=kr-signals-push::기자 전용 저장소 전송 HTTP {status}")
    if status == 404:
        print(f"::warning title=kr-signals-token::토큰 거부 또는 배포 전 — {private_store.token_shape(private_store.normalize_token(token))}")
    if status != 200:
        sys.exit(1)


if __name__ == "__main__":
    main()
