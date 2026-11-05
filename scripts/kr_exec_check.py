"""문제 임원 점검 — 출입처 임원 한 사람씩 법정 결격·한도와 과거 논란 기사를 본다(11-05 기자: "임원에 대한 단독 — 문제 있는 임원").

선배 매의눈의 롯데카드 사례는 '그 사람의 과거 논란(해킹 사고 책임)'과 '지금 보고서의 이사 등재'를 이어 붙인 기사다. 같은 일을 출입처 임원에 한다.

대상: 출입처 39곳 최근 정기보고서의 등기임원(임원 현황 API — 경력·재직기간·최대주주 관계)과, 임원 명단 감시(kr-exec)가 원문에서 읽은
미등기 사장급(회장·부회장·사장·대표·C레벨).

점검(표시는 판정이 아니라 확인할 단서 — 기자가 판단)
1. 독립(사외)이사 법정 결격 가능 — 상법 시행령 제34조 제5항(2026-07 개정)
   - 7호: 같은 회사에서 사외·독립이사로 6년 초과(계열사 합산 9년) → '재직기간' 칸이 기간(n년 n개월·n개월)이거나 6년 넘은 시작일일 때만
   - 3호: 해당 회사 외 2곳 이상 다른 회사 이사·집행임원·감사 재임 → 다른 상장사(명단 순환)·출입처 정기보고서 등기임원 명단에 같은 이름·출생년월이
     2곳 넘게 있으면 A. 경력 칸 '현(現)' 마디만으로는 B '겸직 확인'(11-05 실제: 기간 표기 '(\'17 ~ \'19)'를 잘못 끊어 끝난 대표이사를 현직으로 셌다)
   - 1호: 계열회사 상무 종사자이거나 최근 3년 안 종사 → 경력 칸에 같은 그룹 이름 + 직원·임원 직함 + 최근 3년 연도(또는 현재)
2. 과거 논란 기사 — 네이버 뉴스에서 '이름 + 회사'(사외이사는 '이름 + 경력의 주된 기관'도) 제목에 비위·사고·제재 낱말이 있는 기사.
   기사 제목에 그 사람 이름이 있는 것만. 강한 낱말(횡령·배임·기소·구속·압수수색·고발·해킹·유출·갑질·성비위·음주운전·뇌물·담합·분식·중대재해·징계·경질)이면 A,
   그 밖(본문에만 이름, 소송·논란·사퇴 등) B. 같은 이름의 다른 사람일 수 있다 — 기사 원문 확인.

원칙
- 공개 공시·공개 기사만. 혐의·비위를 단정하지 않는다(기사 제목을 그대로 옮기고 확인할 것으로 둔다).
- 법정 결격은 '가능'까지만. 재직기간 계산 기준·겸직 회사 수는 회사 공시·회사 확인으로.
- 조회 실패는 0건이 아니라 미확인.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import earnings_compare as ec  # noqa: E402
import governance_watch as gw  # noqa: E402
import kr_exec_watch as kx  # noqa: E402

SCHEMA = "kr_exec_check/v1"
KST = ec.KST
NEWS_BUDGET = 250        # 네이버 뉴스 검색 한 실행 한도
RECHECK_DAYS = 14        # 같은 사람 기사 점검 간격
KEEP_DAYS = 180
PAUSE = 0.3
OUTSIDE = re.compile(r"사외이사|독립이사")
TOP = re.compile(r"(?<!부)사장|회장|대표|\bC[EFOTS]O\b")
STRONG = re.compile(r"횡령|배임|기소|구속|압수\s*수색|고발|해킹|유출|갑질|성희롱|성추행|성비위|성범죄|음주\s*운전|뇌물|비리|담합|분식|"
                    r"중대\s*재해|사망\s*사고|징계|경질|실형|집행유예|유죄|송치|입건|불법")
WEAK = re.compile(r"소송|피소|논란|사퇴|책임\s*지고|물러나|제재|과징금|벌금|수사|검찰\s*조사|의혹|파문|구설|고소")
NONCOMPANY = re.compile(r"학회|협회|재단|위원회|연구원|연구소|대학|학교|병원|조합|포럼|센터|연합회|진흥원|공단|공사|정부|부처|청$|법원|"
                        r"검찰|국회|자문|평가|심사|운영|후원|봉사|교회|사단|사회|클럽|로터리|라이온스|NGO|Foundation|Society|Association|University",
                        re.I)
CURRENT = re.compile(r"^\s*[\(\[]?\s*(現|현\)|현\s*\)|현재|現\))|~\s*(현재|現)|\(\s*현\s*\)|현재\)?\s*$|~\s*$")
# '감사위원회 지원센터 자문교수'(11-05 실제: 세아제강 사외이사)는 감사가 아니다 — 직함으로 쓰인 감사·감사위원만
ROLE_DIRECTOR = re.compile(r"사외이사|독립이사|기타\s*비상무\s*이사|비상임\s*이사|감사위원(?!회)|감사(?!원|팀|실|부|위원회|인|법인|기관|센터|지원)|이사(?!회|장|대우)")
EMPLOYEE = re.compile(r"부장|팀장|실장|상무|전무|부사장|사장|본부장|센터장|연구원|직원|임원|대표|그룹장|담당|매니저|과장|차장")


# ---------- tenure ----------

def tenure_months(period, as_of):
    """'6년 3개월'·'75개월'·'2019.03~'·'2013년4월1일 ~'·'21.4'(→2021.4) → 개월 수. 모르면 None."""
    t = re.sub(r"\s+", "", str(period or ""))
    if not t or t in ("-", "–"):
        return None
    m = re.fullmatch(r"(\d{1,2})년(?:(\d{1,2})개?월)?", t)
    if m:
        return int(m.group(1)) * 12 + int(m.group(2) or 0)
    m = re.fullmatch(r"(\d{1,3})개?월", t)
    if m:
        return int(m.group(1))
    m = re.match(r"(\d{4})[.년-](\d{1,2})", t) or re.fullmatch(r"(\d{2})\.(\d{1,2})", t)
    if m:
        y = int(m.group(1))
        y = y + 2000 if y < 100 else y
        mo = int(m.group(2))
        if 1990 <= y <= as_of.year and 1 <= mo <= 12:
            return (as_of.year - y) * 12 + as_of.month - mo
    return None


# ---------- career rules ----------

def segs(career):
    import kr_exec_market as km
    return km.segments(career)


def current_directorships(career, own_aliases):
    """경력 '현(現)' 마디 중 다른 회사의 이사·감사 직함 → [마디]"""
    out = []
    for s in segs(career):
        if not CURRENT.search(s) and not re.search(r"現|현\)|현재|\(현\)", s):
            continue
        role = ROLE_DIRECTOR.search(s)
        if not role:
            continue
        org = s[:role.start()]
        org = re.sub(r"^[\s\-·ㆍ•\(\)\[\]現현재~\d.년월']+|[\s,\-·]+$", "", org)
        if not org or NONCOMPANY.search(org) or any(kx.mentions(s, a) for a in own_aliases):
            continue
        if re.search(r"법무법인|회계법인|세무법인|로펌|LLC|LLP", org) and not re.search(r"사외이사|감사|이사", s[role.start():role.end()]):
            continue
        out.append(s[:100])
    return list(dict.fromkeys(out))


def affiliate_recent(career, own_aliases, as_of):
    """같은 그룹 이름 + 직원·임원 직함 + 최근 3년 연도(또는 현재) 마디"""
    out = []
    for s in segs(career):
        if not any(kx.mentions(s, a) for a in own_aliases):
            continue
        if OUTSIDE.search(s) or not EMPLOYEE.search(s):
            continue
        years = [int(y) for y in re.findall(r"(?<!\d)(20\d{2}|19\d{2})(?!\d)", s)] + \
                [2000 + int(y) for y in re.findall(r"['’](\d{2})(?!\d)", s)]
        recent = (max(years) >= as_of.year - 3) if years else False
        if recent or re.search(r"現|현\)|현재|\(현\)", s):
            out.append(s[:100])
    return out


def main_org(career, company_aliases):
    """사외이사 경력의 주된 기관(첫 마디의 직함 앞 이름) — 기사 검색용"""
    for s in segs(career):
        m = re.search(r"([가-힣A-Za-z&·]{2,20}?)(?:㈜|\(주\))?\s*(?:대표|사장|부사장|전무|상무|부회장|회장|원장|청장|차관|장관|위원장|검사장|"
                      r"부장검사|판사|국장|실장|본부장|교수|변호사|회계사)", s)
        if m:
            org = m.group(1)
            if not any(a in org for a in company_aliases) and len(org) >= 2 and not re.fullmatch(r"전|현|前|現", org):
                return org
    return None


def news_hits(items, name, anchors, *, skip_in_title=()):
    """기사 중 이름과 기준어(회사·기관)가 있고 제목에 비위·사고·제재 낱말이 있는 것.
    skip_in_title: 제목에 이 낱말(지금 회사 이름)이 있으면 뺀다 — 사내 임원의 자기 회사 사고·담합 기사는 회사 기사(이미 보도)라서(11-05 실제 실행:
    표시 100명 중 사장·회장의 자기 회사 사망사고·담합 기사가 많았다)."""
    out = []
    for a in items:
        title, text = a.get("title", ""), a.get("text", "")
        both = f"{title} {text}"
        if name not in both or not any(x in both for x in anchors if x):
            continue
        if any(x and x in title for x in skip_in_title):
            continue
        if name not in title:      # 11-05 실제: 본문에만 이름이 있는 기사는 거의 다른 사람·다른 일(LS 사외이사 ↔ '명노현 LS 부회장 … 논란')
            continue
        strong, weak = STRONG.search(title), WEAK.search(title)
        if not strong and not weak:
            continue
        out.append({"title": title[:120], "date": a.get("date"), "url": a.get("url"), "word": (strong or weak).group(0),
                    "strong": bool(strong) and name in title})
    out.sort(key=lambda x: (not x["strong"], str(x.get("date") or "")), reverse=False)
    return out[:3]


# ---------- run ----------

def person_id(company, p):
    return f"{company}|{kx.person_key(p)}"


def market_index(market_doc):
    """kr-exec-market 명단 순환의 등기임원 키 해시 → [(회사, 기간)]"""
    idx = {}
    for code, c in ((market_doc or {}).get("companies") or {}).items():
        for h in c.get("dk") or []:
            idx.setdefault(h, []).append((c.get("n") or code, c.get("p")))
    return idx


def run(key, *, now=None, previous=None, exec_doc=None, market_doc=None, get=None, news=None, sleep=time.sleep, registry=None, table=None,
        news_budget=None):
    if get is None:
        import requests
        get = requests.get
    if news is None:
        import scoop_screen
        news = scoop_screen.naver
    now = now or dt.datetime.now(KST)
    stamp = now.isoformat(timespec="seconds")
    prev = previous if isinstance(previous, dict) and previous.get("schema") == SCHEMA else {}
    old_people = {p["id"]: p for p in prev.get("people") or [] if isinstance(p, dict) and p.get("id")}
    old_events = {e["id"]: e for e in prev.get("events") or [] if isinstance(e, dict) and e.get("id")}
    year, report = ec.target_period(now)
    dy, base_report = kx.BASE[report]
    names = [n for n, _, _ in kx.BEATS]
    codes, missing = gw.resolve_codes(names, registry, table)
    codes.pop("_spellings", None)
    rosters = (exec_doc or {}).get("rosters") or {}
    midx = market_index(market_doc)
    covered = sum(1 for c in ((market_doc or {}).get("companies") or {}).values() if c.get("p"))
    beat_keys = {n: {kx.person_key(p) for p in kx.unpack(v.get("people") or []) if p.get("reg") != "미등기"} for n, v in rosters.items()}
    checks, people = [], []
    budget = [news_budget if news_budget is not None else NEWS_BUDGET]
    news_fail = queried = 0
    for name in names:
        code = codes.get(name)
        short = kx.SHORT.get(name, name)
        if not code:
            checks.append({"source": short, "status": "failed", "error": "DART 고유번호 못 찾음"})
            continue
        try:
            st, api, rcept = kx.api_roster(key, code, year, report, get=get, sleep=sleep)
            y, r = year, report
            if st != "ok":
                st, api, rcept = kx.api_roster(key, code, year + dy, base_report, get=get, sleep=sleep)
                y, r = year + dy, base_report
            if st != "ok":
                checks.append({"source": short, "status": "no_data", "note": "최근 보고서 없음"})
                continue
        except (ec.TransientError, RuntimeError) as e:
            checks.append({"source": short, "status": "failed", "error": str(e)[:80]})
            continue
        as_of = dt.date(y, int(kx.AS_OF[r][:2]), int(kx.AS_OF[r][3:]))
        group = kx.GROUP.get(name)
        own = [a for a in kx.RIVALS.get(group, []) if len(a) >= 2] or [short]
        # 미등기 사장급(임원 명단 감시가 원문에서 읽은 것) — 기사 점검만
        tops = [p for p in kx.unpack((rosters.get(name) or {}).get("people") or [])
                if p.get("reg") == "미등기" and TOP.search(kx.norm_ofcps(p.get("ofcps")))]
        url = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept}"
        for p in [x for x in api if x["reg"] != "미등기"] + tops:
            pid = person_id(name, p)
            rec = {"id": pid, "company": short, "dartName": name, "name": p["name"], "birth": kx.birth_key(p["birth"])[:4],
                   "ofcps": kx.norm_ofcps(p["ofcps"]), "reg": p["reg"], "period": p.get("period", ""), "career": (p.get("career") or "")[:300],
                   "report": kx.period_label(y, r), "url": url, "flags": []}
            outside = bool(OUTSIDE.search(p["reg"] + p["ofcps"]))
            if outside:
                months = tenure_months(p.get("period"), as_of)
                if months and months > 72:
                    rec["flags"].append({"kind": "법정 한도: 재직 6년 초과 가능", "tier": "A",
                                         "text": f"재직기간 칸 「{p.get('period')}」 → {months // 12}년 {months % 12}개월({kx.period_label(y, r)} 기준) — 상법 시행령 제34조⑤7호(같은 회사 6년 초과 결격). 연임 경위·계산 기준은 회사 확인"})
                cur = current_directorships(p.get("career"), own)
                others = sorted(kx.SHORT.get(o, o) for o, ks in beat_keys.items() if o != name and kx.person_key(p) in ks)
                h = hashlib.sha256(kx.person_key(p).encode()).hexdigest()[:8]
                listed = sorted({n_ for n_, _ in midx.get(h, [])} - {short, name} - set(others))
                filed = others + listed                     # 공시 명단으로 확인된 다른 회사 등기임원 자리
                if len(filed) >= 2:
                    rec["flags"].append({"kind": "법정 한도: 다른 회사 이사·감사 2곳 이상 가능", "tier": "A",
                                         "text": f"같은 이름·출생년월이 다른 상장사 등기임원 명단에도 있음: {'·'.join(filed[:5])}(각 회사 최근 정기보고서)"
                                                 f"{' · 경력 현직 「' + ' / '.join(cur[:3]) + '」' if cur else ''}"
                                                 " — 상법 시행령 제34조⑤3호(해당 회사 외 2곳 이상 다른 회사 이사·감사 재임 결격). 겸직 시점·동명이인은 각 회사 공시로 확인"})
                elif len(cur) + len(filed) >= 2 and cur:
                    rec["flags"].append({"kind": "겸직 확인: 경력 칸 현직 이사·감사", "tier": "B",
                                         "text": f"경력 '현' 마디 「{' / '.join(cur[:3])}」{' · 다른 상장사 명단: ' + '·'.join(filed) if filed else ''}"
                                                 f" — 공시 명단으로 2곳 확인은 안 됨(명단 순환 {covered}곳 기준·비상장 못 봄). 상법 시행령 제34조⑤3호 기준 확인"})
                aff = affiliate_recent(p.get("career"), own, as_of)
                if aff:
                    rec["flags"].append({"kind": "독립성: 같은 그룹 최근 근무 가능", "tier": "B",
                                         "text": f"경력 「{' / '.join(aff[:2])}」 — 상법 시행령 제34조⑤1호(계열회사 상무 종사자·최근 3년 내 종사자 결격). 근무 기간·직무는 확인"})
            # 과거 논란 기사
            old = old_people.get(pid) or {}
            due = not old.get("newsAt") or old["newsAt"] < (now - dt.timedelta(days=RECHECK_DAYS)).isoformat()
            if due and budget[0] > 0:
                anchors_ = [short, name] + own[:3]
                internal = not (outside or re.search(r"기타\s*비상무", p["reg"] + p["ofcps"]))
                skip = ([short, name] + own) if internal else ()
                queries = [(f"{p['name']} {short}", anchors_, skip)]
                org = main_org(p.get("career"), own) if not internal else None
                if org:
                    queries.append((f"{p['name']} {org}", [org], ()))
                hits, failed = [], False
                queried += 1
                for q, anchors, skip_t in queries:
                    if budget[0] <= 0:
                        break
                    budget[0] -= 1
                    res = news(q)
                    sleep(PAUSE)
                    if res.get("status") != "ok":
                        failed = True
                        continue
                    hits += news_hits(res.get("items") or [], p["name"], anchors, skip_in_title=skip_t)
                if failed and not hits:
                    news_fail += 1
                    rec["news"], rec["newsAt"] = old.get("news") or [], old.get("newsAt")
                else:
                    seen = set()
                    rec["news"] = [h for h in hits if not (h["url"] in seen or seen.add(h["url"]))][:3]
                    rec["newsAt"] = stamp
            else:
                rec["news"], rec["newsAt"] = old.get("news") or [], old.get("newsAt")
            rec["news"] = [h for h in rec.get("news") or [] if p["name"] in h.get("title", "")]
            if rec.get("news"):
                strong = any(h["strong"] for h in rec["news"])
                rec["flags"].append({"kind": "과거 논란 기사", "tier": "A" if strong else "B",
                                     "text": " / ".join(f"「{h['title']}」({h.get('date') or '날짜 미상'}, '{h['word']}')" for h in rec["news"][:2])
                                             + " — 같은 이름의 다른 사람일 수 있음, 기사 원문 확인"})
            people.append(rec)
        checks.append({"source": short, "status": "ok", "returned": len([x for x in api if x["reg"] != "미등기"]), "tops": len(tops), "report": kx.period_label(y, r)})
    if news_fail:
        checks.append({"source": "네이버 뉴스", "status": "partial", "error": f"검색 실패 {news_fail}명(다음 실행 다시)"})
    if budget[0] <= 0:
        checks.append({"source": "네이버 뉴스", "status": "partial", "pending": sum(1 for p in people if not p.get("newsAt")),
                       "error": "한 실행 검색 한도 — 남은 사람은 다음 실행"})
    events = dict(old_events)
    fresh = 0
    first = not prev      # 첫 실행은 지금 표시 전부가 '새로' 생긴다 — 오늘의 레이더엔 올리지 않고(기준선) kr_signals 목록으로 본다
    for p in people:
        for f in p["flags"]:
            eid = "execc:" + hashlib.sha256(f"{p['id']}|{f['kind']}|{f['text'][:60]}".encode()).hexdigest()[:16]
            if eid in events:
                continue
            fresh += 1
            events[eid] = {"id": eid, "tier": f["tier"], "kind": f["kind"], "company": p["company"], "detectedAt": stamp, "url": p["url"],
                           **({"baseline": True} if first else {}),
                           "person": {"name": p["name"], "birth": p["birth"], "ofcps": p["ofcps"], "reg": p["reg"]}, "flags": [f],
                           "text": f"{p['company']} {p['ofcps']}({p['reg']}) {p['name']}{' ' + p['birth'] + '년생' if p['birth'] else ''} — {f['kind']}: {f['text']}"}
    keep = (now - dt.timedelta(days=KEEP_DAYS)).isoformat(timespec="seconds")
    ev = sorted((e for e in events.values() if str(e.get("detectedAt", "")) >= keep),
                key=lambda e: (e.get("detectedAt", ""), {"A": 0, "B": 1}.get(e.get("tier"), 2)), reverse=True)
    ok = sum(1 for c in checks if c["status"] in ("ok", "no_data"))
    status = "complete" if ok == len(checks) else "failed" if not any(c["status"] in ("ok", "no_data") for c in checks) else "partial"
    flagged = [p for p in people if p["flags"]]
    return {
        "schema": SCHEMA, "generatedAt": stamp, "status": status, "checks": checks, "people": people, "events": ev,
        "counts": {"people": len(people), "outside": sum(1 for p in people if OUTSIDE.search(p["reg"] + p["ofcps"])), "flagged": len(flagged),
                   "A": sum(1 for p in flagged if any(f["tier"] == "A" for f in p["flags"])), "newEvents": fresh,
                   "newsChecked": queried},
        "unresolvedCompanies": missing,
        "rules": [
            "출입처 최근 정기보고서 등기임원(임원 현황)과 미등기 사장급을 한 사람씩 본다. 표시는 확인할 단서지 판정이 아니다.",
            "독립(사외)이사 법정 결격 가능 — 상법 시행령 제34조⑤: 7호 같은 회사 6년 초과(재직기간 칸이 기간이거나 6년 넘은 시작일일 때만), 3호 해당 회사 외 2곳 이상 다른 회사 이사·감사(다른 상장사·출입처 공시 명단에 같은 이름·출생년월이 2곳 넘게 있을 때 A, 경력 칸 현직만이면 B '겸직 확인'), 1호 계열회사 최근 3년 내 상무 종사(경력 칸 같은 그룹 + 직함 + 연도).",
            "과거 논란 기사: 네이버 뉴스 '이름 + 회사'(사외·기타비상무이사는 '이름 + 경력의 주된 기관'도)에서 제목에 비위·사고·제재 낱말이 있는 기사. 사내 임원(사내이사·미등기 사장급)은 제목에 지금 회사 이름이 있는 기사(회사 사고·담합 등 — 이미 보도된 회사 기사)를 뺀다. 첫 실행 표시는 기준선(오늘의 레이더엔 안 올림). 기사 제목에 그 사람 이름이 있는 것만. 강한 낱말(횡령·배임·기소·구속·고발·해킹·유출·갑질·성비위·음주운전·뇌물·담합·분식·중대재해·징계·경질 등)이면 A. 같은 이름의 다른 사람일 수 있다.",
            "혐의·비위를 단정하지 않는다. 기사 제목은 그대로 옮기고, 결격 여부·사실관계는 회사·당사자 확인. 조회 실패는 0건이 아니라 미확인.",
        ],
    }


def annotate(doc):
    def mask(s):
        s = str(s or "")
        return s[:1] + "*" * max(0, len(s) - 1)
    print(f"::notice title=kr-exec-check-summary::{json.dumps(doc['counts'], ensure_ascii=False)} · 실패 "
          + ", ".join(f"{c['source']}({c.get('error', c['status'])})" for c in doc["checks"] if c["status"] not in ("ok", "no_data")))
    rows = []
    for p in doc["people"]:
        for f in p["flags"]:
            t = f["text"]
            for h in p.get("news") or []:
                t = t.replace(h["title"], "(기사 제목)")
            rows.append(f"{f['tier']} {p['company']} {p['ofcps']}({p['reg']}) {mask(p['name'])} · {f['kind']} · {t.replace(p['name'], mask(p['name']))[:200]}")
    for i, line in enumerate(sorted(rows)[:40]):
        print(f"::notice title=kr-exec-check-{i + 1}::{line}")


def main():
    global NEWS_BUDGET
    ap = argparse.ArgumentParser(description="문제 임원 점검")
    ap.add_argument("--annotate-only", action="store_true")
    ap.add_argument("--news-budget", type=int)
    a = ap.parse_args()
    NEWS_BUDGET = a.news_budget if a.news_budget is not None else NEWS_BUDGET
    key = os.environ.get("DART_API_KEY", "").strip()
    if not key:
        sys.exit("DART_API_KEY 없음 — 이전 결과 유지")
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    import private_store
    previous = exec_doc = market_doc = None
    if token:
        for feed in ("kr-exec-check", "kr-exec", "kr-exec-market"):
            try:
                got = private_store.get(feed, token)
            except private_store.StoreError as e:
                print(f"::warning title=kr-exec-check-state::{feed} 조회 실패({e})")
                got = None
            if feed == "kr-exec-check":
                previous = got
            elif feed == "kr-exec":
                exec_doc = got
            else:
                market_doc = got
    registry = json.loads((ROOT / "dart_corp_codes.json").read_text(encoding="utf-8"))
    try:
        import dart_watch
        table = dart_watch.load_corp_codes(key)
    except SystemExit:
        table = None
    doc = run(key, previous=None if a.annotate_only else previous, exec_doc=exec_doc, market_doc=market_doc, registry=registry, table=table,
              news_budget=NEWS_BUDGET)
    if a.annotate_only:
        annotate(doc)
        return
    c = doc["counts"]
    print(f"::notice title=kr-exec-check::점검 {c['people']}명(사외·독립 {c['outside']}) · 표시 {c['flagged']}명(A {c['A']}) · 새 항목 {c['newEvents']} · 기사 점검 {c['newsChecked']}명")
    if not token:
        print("::warning title=kr-exec-check-push::MCP_ACCESS_TOKEN 미설정 — 결과를 저장하지 않음")
        return
    if doc["status"] == "failed":
        sys.exit("임원 현황 조회 전체 실패 — 이전 결과 유지(0건 아님)")
    print(f"::notice title=kr-exec-check-push::기자 전용 저장소 전송 HTTP {private_store.put('kr-exec-check', doc, token)}")


if __name__ == "__main__":
    main()
