"""대한(對韓) 수입규제 — 한국무역협회 수입규제DB(kita.net) 감시. trade_remedy_watch가 부른다.

- 무역협회가 세계 각국의 한국산 반덤핑·상계관세·세이프가드·우회수출 조사를 한 곳에 모아 갱신한다(10-30 기준 750건).
  지금까지 국가별 공고 목록(호주·캐나다·인도·영국·인도네시아·베트남)과 미국 관보만 봤는데, EU·중국·EAEU·튀르키예·브라질 등은 비어 있었다.
- 목록(POST importRegulationCardList.do, 최근 갱신순 50건)을 실행마다 한 번 읽어 새 사건과 갱신일이 바뀐 사건을 찾고,
  그것만 상세(POST importRegulationCardDetail.do)를 읽어 최신 진행 단계(예: '재심 · 예비판정(2026.10.08)')와 업체별 마진을 붙인다.
- 등급: 최신 단계에 출입처 업체(영문 이름)가 마진과 함께 나오면 A(새 사건)·B(진행), 품목 분류가 출입 업종(철강/금속·화학·플라스틱/고무·
  전기전자·기계)이면 B(새 사건)·C(진행), 나머지 새 사건은 C, 나머지 진행 갱신은 이벤트 없음. 미국 사건은 관보 감시가 먼저 잡으니 한 단계 낮춘다.
- 무역협회가 정리한 2차 자료다. 세율·판정은 단계마다 붙은 원문 링크(관보 등)로 확인한다. 첫 실행은 기준선. 조회 실패는 0건이 아니다.
- robots.txt 허용(10-30 확인). 실행당 목록 1번 + 상세 최대 8번, 1초 간격.
"""
from __future__ import annotations

import datetime as dt
import html as htmllib
import re
import time

SITE = "https://www.kita.net"
LIST = SITE + "/importRegulation/importRegulation/importRegulationCardList.do"
DETAIL = SITE + "/importRegulation/importRegulation/importRegulationCardDetail.do"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "ko-KR,ko;q=0.9", "Referer": LIST}
PAGE_UNIT = 50
DETAIL_MAX = 8
RECENT_DAYS = 60   # 갱신된 사건의 최신 단계가 이보다 오래면 '진행' 이벤트로 보지 않는다(무역협회가 옛 글을 손본 것)
CASES_MAX = 1500
BEAT_CATS = {"철강/금속", "화학", "플라스틱/고무", "전기전자", "기계"}
# (출입처, 업체명 규칙) — 무역협회 상세의 업체명 칸은 영문(조사 당국 표기) 그대로다.
FIRMS = [
    ("포스코", r"\bPOSCO\b(?!\s*(?:Future\s*M|Chemical|E&C|Engineering|DX|Plant))"), ("현대제철", r"Hyundai\s+Steel"),
    ("KG스틸", r"KG\s*(?:Dongbu|Steel)|Dongbu\s+(?:Steel|Incheon)"), ("동국제강", r"Dongkuk\s+(?:Steel|International)"),
    ("동국씨엠", r"Dongkuk\s+(?:Coated\s+Metal|CM)"), ("세아제강", r"SeAH\s+(?:Steel|Coated)"), ("세아", r"SeAH\s+(?:Besteel|Changwon|Holdings)"),
    ("고려아연", r"Korea\s+Zinc"), ("영풍", r"Young\s*Poong"), ("LS전선", r"LS\s+Cable"), ("대한전선", r"Taihan\s+(?:Cable|Electric)"),
    ("효성중공업", r"Hyosung\s+Heavy"), ("HD현대일렉트릭", r"Hyundai\s+Electric"), ("LS일렉트릭", r"LS\s+(?:Electric|Industrial)"),
    ("한화솔루션", r"Hanwha\s+(?:Solutions|Q\s*CELLS|Chemical)"), ("OCI", r"\bOCI\b"), ("태광", r"Taekwang"), ("DL케미칼", r"DL\s+Chemical"),
    ("동성케미칼", r"Dongsung\s+Chemical"), ("GS칼텍스", r"GS\s+Caltex"), ("두산에너빌리티", r"Doosan\s+(?:Enerbility|Heavy)"),
    ("한국타이어", r"Hankook\s+Tire"), ("금호타이어", r"Kumho\s+Tire"), ("넥센타이어", r"Nexen\s+Tire"), ("현대차", r"Hyundai\s+Motor"),
    ("기아", r"\bKia\s+(?:Corporation|Motors)"), ("현대모비스", r"Hyundai\s+Mobis"),
    # 11-01 기자 명시: 석유화학·정유(자회사 Kumho P&B·SK Energy·SK Geo Centric은 아님)
    ("LG화학", r"\bLG\s+Chem(?:ical)?\b"), ("롯데케미칼", r"Lotte\s+Chemical(?!\s*Titan)"), ("금호석유화학", r"Kumho\s+Petrochemical"),
    ("S-OIL", r"\bS-Oil\b"), ("HD현대오일뱅크", r"Hyundai\s+Oil\s*bank"), ("SK이노베이션", r"\bSK\s+Innovation"),
]
FIRM_RX = [(ko, re.compile(rx, re.I)) for ko, rx in FIRMS]
STAGE_RX = re.compile(r"^(.+?)\s*\((\d{4})\.(\d{2})\.(\d{2})\)\s*$")


def plain(s):
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", str(s or "")))).strip()


def day(s):
    m = re.search(r"(\d{4})\.(\d{2})\.(\d{2})", str(s or ""))
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def beat_firms(text):
    return sorted({ko for ko, rx in FIRM_RX if rx.search(str(text or ""))})


def parse_cards(page):
    """목록 카드: 관리번호(tirId)·규제국·품목·조사개시일·최근갱신일·유형·상태(10-30 실제 모양)."""
    out = []
    for li in re.findall(r"(?is)<li>\s*<div class=\"cate[^\"]*\">(.*?)</li>\s*(?=<li>\s*<div class=\"cate|</ul>)", page or ""):
        m = re.search(r"goDetailPage\('([A-Za-z0-9]+)'\)", li)
        if not m:
            continue
        country = plain((re.search(r"(?is)<span class=\"caption[^\"]*\">(.*?)</span>", li) or [None, ""])[1])
        item = plain((re.search(r"(?is)goDetailPage\('[A-Za-z0-9]+'\)\"[^>]*>(.*?)</a>", li) or [None, ""])[1])
        inve = day((re.search(r"조사개시일\s*:\s*<span[^>]*>([^<]+)", li) or [None, ""])[1])
        reg = day((re.search(r"최근갱신일\s*:\s*<span[^>]*>([^<]+)", li) or [None, ""])[1])
        kind = plain((re.search(r"규제유형\s*:\s*([^<]+)", li) or [None, ""])[1])
        status = plain((re.search(r"규제상태\s*:\s*([^<]+)", li) or [None, ""])[1])
        if item:
            out.append({"tirId": m.group(1), "country": country, "item": item[:160], "investigated": inve, "updated": reg, "type": kind, "status": status})
    return out


def parse_detail(page):
    """상세: 머리 표(케이스 번호·규제국·유형·품목 분류·상태·HS)와 진행 단계(최신이 먼저), 단계별 업체·마진·비고·메모·원문 링크."""
    head = {}
    for th, td in re.findall(r"(?is)<th[^>]*>\s*(?:<p>)?(.*?)(?:</p>)?\s*</th>\s*<td[^>]*>(.*?)</td>", page or ""):
        k, v = plain(th), plain(re.sub(r"(?is)<a\b.*?</a>", " ", td))
        if k and k not in head:
            head[k] = v
    stages = []
    parts = re.split(r"(?is)<div class=\"subject subject-flex[^\"]*\"[^>]*>", page or "")
    for part in parts[1:]:
        label = plain(part.split("</div>", 1)[0])
        m = STAGE_RX.match(label)
        if not m:
            continue  # '특이사항' 같은 머리
        body = part.split("</div>", 1)[1] if "</div>" in part else ""
        body = re.split(r"(?is)<div class=\"subject subject-flex", body)[0]
        firms = []
        for li in re.findall(r"(?is)<li>\s*<dl>(.*?)</li>", body):
            dd = {plain(k): plain(v) for k, v in re.findall(r"(?is)<dt>(.*?)</dt>\s*<dd>(.*?)</dd>", li)}
            if dd.get("업체명"):
                firms.append({"firm": dd["업체명"][:120], "margin": dd.get("마진") or None, "note": dd.get("비고") or None})
        note = plain((re.search(r"(?is)<ul class=\"list-bull\">(.*?)</ul>", body) or [None, ""])[1])[:400]
        link = (re.search(r"(?is)<a href=\"(https?://[^\"]+)\"[^>]*class=\"open-link\"", body)
                or re.search(r"(?is)<a href=\"(https?://[^\"]+)\"[^>]*>\s*관련 링크", body))
        stages.append({"label": m.group(1).strip(), "date": f"{m.group(2)}-{m.group(3)}-{m.group(4)}", "firms": firms[:20], "note": note,
                       "link": htmllib.unescape(link.group(1)) if link else None})  # 10-30 실제 링크에 '&amp;'가 그대로
    return {"caseNo": head.get("케이스 번호"), "country": head.get("규제국"), "type": head.get("유형"), "category": head.get("품목 분류"),
            "status": head.get("규제 상태"), "hs": re.findall(r"\d{4}\.\d{2}(?:\.\d{2,4})?", head.get("HS코드", ""))[:6], "stages": stages}


class Http:
    def __init__(self, session=None, sleep=time.sleep):
        if session is None:
            import requests
            session = requests.Session()
        self.s, self.sleep = session, sleep

    def post(self, url, data):
        last = None
        for attempt in range(2):
            try:
                r = self.s.post(url, data=data, headers=UA, timeout=40)
                if r.status_code == 200:
                    return r.text
                last = RuntimeError(f"HTTP {r.status_code}")
                if r.status_code < 500:
                    break
            except Exception as e:  # noqa: BLE001
                last = e
            self.sleep(5.0)
        raise last


def stage_text(st, limit=5):
    firms = "; ".join(f"{f['firm']} {f['margin']}%" + (f"({f['note']})" if f.get("note") else "") for f in st["firms"][:limit] if f.get("margin"))
    more = f" 외 {len(st['firms']) - limit}곳" if len(st["firms"]) > limit else ""
    return f"{st['label']}({st['date']})" + (f": {firms}{more}" if firms else "")


def collect(prev, now, http, *, sleep=time.sleep):
    """(상태, 새 이벤트, 점검). prev는 이전 trade-remedy 문서의 kita 블록."""
    prev = prev if isinstance(prev, dict) else {}
    stamp = now.isoformat(timespec="seconds")
    known = dict(prev.get("cases") or {})
    baseline = not known
    try:
        cards = parse_cards(http.post(LIST, {"pageIndex": "1", "pageUnit": str(PAGE_UNIT), "searchOrder": "2"}))
        if not cards:
            raise RuntimeError("목록 형식 미상")
    except Exception as e:  # noqa: BLE001
        err = str(e)[:60] if isinstance(e, RuntimeError) and str(e) else type(e).__name__
        return (dict(prev, stale=True) if prev else None), [], {"source": "무역협회 수입규제DB", "status": "failed", "returned": 0, "error": err}
    todo = [c for c in cards if c["tirId"] not in known or known[c["tirId"]].get("updated") != c["updated"]]
    events, read, errors = [], 0, []
    for c in cards:
        old = known.get(c["tirId"]) or {}
        rec = {**old, **{k: c[k] for k in ("country", "item", "investigated", "updated", "type", "status")}}
        if c in todo and not baseline and read < DETAIL_MAX:
            read += 1
            sleep(1.0)
            try:
                d = parse_detail(http.post(DETAIL, {"tirId": c["tirId"]}))
            except Exception as e:  # noqa: BLE001
                errors.append(f"{c['tirId']} {str(e)[:30] if isinstance(e, RuntimeError) and str(e) else type(e).__name__}")
                rec["updated"] = old.get("updated")  # 다음 실행에 다시 읽게
                known[c["tirId"]] = rec
                continue
            rec.update(caseNo=d["caseNo"], category=d["category"])
            st = d["stages"][0] if d["stages"] else None
            key = f"{st['label']}|{st['date']}" if st else None
            firms = beat_firms(" ".join([f["firm"] for f in (st or {}).get("firms", [])] + [(st or {}).get("note") or ""])) if st else []
            beat_cat = (d["category"] or "") in BEAT_CATS
            us = c["country"] == "미국"
            down = {"A": "B", "B": "C", "C": "C"}
            if not old:
                tier = "A" if firms else "B" if beat_cat else "C"
                kind = "새 대한 수입규제"
            elif key and key != old.get("latestStage") and st["date"] >= (now - dt.timedelta(days=RECENT_DAYS)).date().isoformat():
                tier = "B" if firms else "C" if beat_cat else None
                kind = "대한 수입규제 진행"
            else:
                tier = kind = None
            rec["latestStage"] = key or old.get("latestStage")
            if tier:
                tier = down[tier] if us else tier
                text = (f"{c['country']} {c['type']} · {c['item']} — 조사개시 {c['investigated'] or '?'} · 상태 {c['status']}"
                        f"{' · 품목 분류 ' + d['category'] if d['category'] else ''}{' · 케이스 ' + d['caseNo'] if d['caseNo'] else ''}"
                        + (f" · 최신 단계 {stage_text(st)}" if st else " · 진행 단계 미기재")
                        + (f" · 출입처: {'·'.join(firms)}" if firms else "")
                        + (f" · 메모: {st['note'][:160]}" if st and st.get("note") else ""))
                events.append({"id": f"kita:{c['tirId']}:{key or 'new'}", "pageId": "kita", "country": c["country"], "tier": tier, "kitaKind": kind,
                               "label": f"{c['country']} {c['type']} {c['item'][:40]}", "text": text[:700], "companies": firms,
                               "url": (st or {}).get("link") or LIST, "kitaId": c["tirId"], "detectedAt": stamp})
        elif baseline:
            rec["latestStage"] = rec.get("latestStage")
        known[c["tirId"]] = rec
    if len(known) > CASES_MAX:
        known = dict(sorted(known.items(), key=lambda kv: str(kv[1].get("updated") or ""), reverse=True)[:CASES_MAX])
    state = {"checkedAt": stamp, "cases": known, "recent": [c["tirId"] for c in cards], "baselineSince": prev.get("baselineSince") or stamp}
    check = {"source": "무역협회 수입규제DB", "status": "partial" if errors else "ok", "returned": len(cards), "detailsRead": read,
             **({"error": "; ".join(errors[:3])} if errors else {})}
    return state, events, check
