"""노동위원회 회의 일정 — 출입처가 사건명에 나온 조정·심판 회의.

- 중앙노동위원회와 지방노동위원회 13곳 첫 화면의 '오늘 회의' 칸(공개)에서 회의를 읽고, 회의 상세(공개, GET)의 '담당 사건정보'
  (사건번호·사건명·시각)에서 사건명 앞 당사자가 출입처인 것만 남긴다. 11-03 탐침 130~135로 확인 — 경북지노위 「2026조정87
  에스케이실트론 주식회사 노동쟁의 조정신청사건」, 중노위 「2026부해846 주식회사 케이티엠앤에스 부당희망퇴직거부 구제 재심신청」.
- 한계: 첫 화면 칸은 위원회마다 5건까지만 보인다(11-03 서울·경기·충남 5건). 5건이면 뒤 회의가 빠졌을 수 있어 '일부만'으로 적는다.
  일정 달력(selectMeetingSche.do)은 GitHub에서 화면과 같은 값을 보내도 오류 쪽만 온다(탐침 133·134·168).
- 달력(11-04): 기자 컴퓨터 브라우저의 달력 화면에서는 그달 회의 전체가 온다. 예약 작업이 회의마다 mtgId·mtgSn·mtgYmd·cmitCd·회의명만
  sdds `local_notice_submit`(labor)으로 올리면(kr-labor-browser) 오늘부터 AHEAD_DAYS일 안 회의의 상세(GET, 공개)를 여기서 읽는다 —
  5건 상한이 풀리고 미리 잡힌 회의(다음 주 조정회의 등)를 회의 전에 본다. 미리 읽은 회의는 회의 당일 한 번 더 읽는다(사건이 더 붙을 수 있음).
- 출입처 이름 규칙은 공장등록 감시(data/factory_watch.json의 accept)와 같다. 당사자 이름에서 '주식회사·(주)·외 n' 같은 꼴만 떼고 맞춘다.
  '(관련)' 회사(효성중공업·일진전기)는 출입처가 아니라 뺀다.
- 노동쟁의 조정·교섭(요구·단위·공정대표)·부당노동행위는 A, 그 밖의 구제신청(해고·징계·차별 등)은 B.
- 사건명은 신청인·피신청인 주장일 뿐이다. 신청 내용·결정(조정 중지·성립, 인정·기각)은 위원회 결정문·당사자 확인 전 미확인.
- 결과는 기자 전용 저장소(kr-labor)로만. 공개 로그는 건수만(사건명·회사 이름은 찍지 않는다). 위원 이름은 저장하지 않는다.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import os
import re
import sys
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KST = dt.timezone(dt.timedelta(hours=9))
SCHEMA = "kr_labor/v1"
BASE = "https://www.nlrc.go.kr"
UA = "seoul-reporting-radar (newsroom research; labor commission public schedule)"
PAUSE = 2.0
KEEP_DAYS = 120
SEEN_DAYS = 14
WIDGET_CAP = 5
AHEAD_DAYS = 14          # 달력에서 오늘부터 이만큼 앞 회의까지 상세를 읽는다
DETAIL_BUDGET = 120      # 한 실행에 읽는 회의 상세 상한(2초 간격 — 4분 남짓). 남은 회의는 다음 실행에
BROWSER_FRESH_HOURS = 30  # 이보다 오래된 달력 수집은 '오래됨'(그래도 회의 번호는 쓴다 — 72시간까지)
BROWSER_USE_HOURS = 72

# (주소 조각, 이름) — 첫 화면 주소는 /nlrc/{slug}/main.do, 중앙은 첫 화면
COMMISSIONS = [("", "중앙노동위원회"), ("seoul", "서울지방노동위원회"), ("busan", "부산지방노동위원회"), ("gyeonggi", "경기지방노동위원회"),
               ("incheon", "인천지방노동위원회"), ("gangwon", "강원지방노동위원회"), ("chungbuk", "충북지방노동위원회"),
               ("chungnam", "충남지방노동위원회"), ("jeonbuk", "전북지방노동위원회"), ("jeonnam", "전남지방노동위원회"),
               ("gyeongbuk", "경북지방노동위원회"), ("gyeongnam", "경남지방노동위원회"), ("ulsan", "울산지방노동위원회"),
               ("jeju", "제주지방노동위원회")]

MEETING_RX = re.compile(r'data-action="(/nlrc/(?:[a-z]+/)?meetingSche/detail\.do)"(?P<attrs>[^>]*)>(?P<label>.*?)</', re.S)
ATTR_RX = re.compile(r'data-(mtg-id|mtg-sn|mtg-ymd|cmit-cd)="([^"]*)"')
CASE_NO = r"\d{4}[가-힣]{1,6}\d{1,6}"
CASE_RX = re.compile(rf"({CASE_NO})\s+(.+?)\s+(\d{{1,2}}:\d{{2}})(?=\s+{CASE_NO}\s|\s+목록|\s*$)")
HEAD_RX = re.compile(r"관할위원회\s+(?P<cmit>\S+)\s+회의명\s+(?P<name>.+?)\s+회의장소\s+(?P<place>.+?)\s+회의일자\s+(?P<day>\d{4}-\d{2}-\d{2})"
                     r"\s+회의시간\s+(?P<start>\d{1,2}:\d{2})")
# 사건명에서 당사자 뒤에 오는 사건 종류의 첫 낱말
KIND_START = re.compile(r"\s(?=(?:노동쟁의|부당|차별|교섭|공정대표|조정|중재|단체협약|구제|휴업|해고|징계|직장\s*내|복수노조|이행|해석|"
                        r"쟁의|임금|단위|사실\s*공고)\S*)")
A_KIND = re.compile(r"노동쟁의|조정신청|중재|교섭요구|교섭단위|공정대표|부당노동행위|단체협약")
STRIP = [re.compile(p) for p in (r"\([^)]*\)", r"（[^）]*）", r"주식회사", r"㈜", r"\(주\)", r"유한회사", r"사단법인", r"재단법인",
                                  r"\s외\s*\d+\s*(?:인|명|곳|개사|개\s*회사)?\s*$", r"\s+")]


def now_kst():
    return dt.datetime.now(KST).replace(microsecond=0)


def text_of(h):
    h = re.sub(r"<script.*?</script>|<style.*?</style>", " ", h or "", flags=re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h))).strip()


def load_rules(path=ROOT / "data" / "factory_watch.json"):
    rules = []
    for c in json.loads(Path(path).read_text(encoding="utf-8")).get("companies", []):
        name = str(c.get("company") or "")
        if not name or "관련" in name or not c.get("accept"):
            continue
        rules.append((name, re.compile(c["accept"])))
    return rules


RULES = load_rules()


def party_of(case_name):
    """사건명 앞 당사자: '현대자동차 주식회사 노동쟁의 조정신청사건' → '현대자동차 주식회사'."""
    m = KIND_START.search(" " + case_name)
    return (case_name[: m.start() - 1] if m and m.start() > 0 else case_name).strip()


def norm_party(party):
    s = party
    for rx in STRIP:
        s = rx.sub("", s)
    return s.strip()


def beat_of(case_name, rules=None):
    name = norm_party(party_of(case_name))
    if not name:
        return None
    for comp, rx in rules or RULES:
        if rx.search(name):
            return comp
    return None


def tier_of(case_name, meeting_name=""):
    return "A" if A_KIND.search(case_name) or "조정" in meeting_name and "화해" not in meeting_name else "B"


def word_of(case_name, case_no=""):
    """보도 대조 낱말(digest.mjs ALT에 같은 이름의 묶음): 노동쟁의·부당노동행위·교섭·부당해고, 나머지는 노동위."""
    s = case_no + " " + case_name
    for rx, word in ((r"노동쟁의|조정|중재", "노동쟁의"), (r"부당노동행위|부노", "부당노동행위"), (r"교섭|공정대표", "교섭"), (r"해고|부해", "부당해고")):
        if re.search(rx, s):
            return word
    return "노동위"


def meetings_of(page_html):
    out = []
    for m in MEETING_RX.finditer(page_html or ""):
        a = dict(ATTR_RX.findall(m.group("attrs")))
        if not a.get("mtg-id"):
            continue
        out.append({"action": m.group(1), "mtgId": a["mtg-id"], "mtgSn": a.get("mtg-sn", "1"), "mtgYmd": a.get("mtg-ymd", ""),
                    "cmitCd": a.get("cmit-cd", ""), "label": text_of(m.group("label"))[:30]})
    seen, uniq = set(), []
    for x in out:
        k = (x["mtgId"], x["mtgSn"])
        if k not in seen:
            seen.add(k)
            uniq.append(x)
    return uniq


def browser_meetings(browser, now):
    """기자 컴퓨터 브라우저 달력 수집(kr-labor-browser) → 위원회 이름별 회의 목록(오늘~AHEAD_DAYS일) · 위원회별 상태."""
    today = now.strftime("%Y%m%d")
    until = (now + dt.timedelta(days=AHEAD_DAYS)).strftime("%Y%m%d")
    slug = {name: s for s, name in COMMISSIONS}
    out, state = {}, {}
    for c in (browser or {}).get("commissions") or []:
        name = c.get("commission")
        if name not in slug:
            continue
        try:
            age = (now - dt.datetime.fromisoformat(str(c.get("fetchedAt")).replace("Z", "+00:00"))).total_seconds() / 3600
        except ValueError:
            continue
        if c.get("error") or age > BROWSER_USE_HOURS:
            state[name] = {"status": "failed", "error": (c.get("error") or f"{age:.0f}시간 지난 수집")[:80], "fetchedAt": c.get("fetchedAt")}
            continue
        action = f"/nlrc/{slug[name]}/meetingSche/detail.do" if slug[name] else "/nlrc/meetingSche/detail.do"
        rows = [{"action": action, "mtgId": r["mtgId"], "mtgSn": str(r["mtgSn"]), "mtgYmd": r["mtgYmd"], "cmitCd": r["cmitCd"],
                 "label": str(r.get("title") or "")[:30], "via": "browser"}
                for r in c.get("rows") or [] if today <= str(r.get("mtgYmd")) <= until
                and re.fullmatch(r"\d{10,22}", str(r.get("mtgId"))) and re.fullmatch(r"\d{1,3}", str(r.get("mtgSn")))
                and re.fullmatch(r"\d{2}", str(r.get("cmitCd")))]
        out[name] = rows
        state[name] = {"status": "ok" if age <= BROWSER_FRESH_HOURS else "stale", "fetchedAt": c.get("fetchedAt"), "meetings": len(rows)}
    return out, state


def detail_url(m):
    q = urllib.parse.urlencode({"mtgId": m["mtgId"], "mtgSn": m["mtgSn"], "mtgYmd": m["mtgYmd"], "cmitCd": m["cmitCd"]})
    return f"{BASE}{m['action']}?{q}"


def parse_detail(page_html):
    t = text_of(page_html)
    h = HEAD_RX.search(t)
    if not h:
        return None
    i = t.find("사건번호 사건명 회의시간")
    cases = [{"no": no, "name": name.strip(), "time": tm} for no, name, tm in CASE_RX.findall(t[i:] if i >= 0 else "")]
    return {"commission": h.group("cmit"), "meeting": h.group("name").strip(), "place": h.group("place").strip()[:80],
            "day": h.group("day"), "start": h.group("start"), "cases": cases}


def line(n):
    return (f"{n['commissionName']} {n['meeting']} {n['day']} {n['time']} · 사건 {n['caseNo']} 「{n['caseName']}」"
            " · 노동위 회의 일정(공개) — 사건명은 신청 주장, 내용·결정은 위원회·당사자 확인")


def run(now, previous=None, get=None, sleep=time.sleep, rules=None, browser=None):
    if get is None:
        import requests
        session = requests.Session()
        session.headers.update({"User-Agent": UA})
        get = session.get
    prev = previous if isinstance(previous, dict) and previous.get("schema") == SCHEMA else {}
    stamp = now.isoformat(timespec="seconds")
    seen_from = (now - dt.timedelta(days=SEEN_DAYS)).strftime("%Y%m%d")
    seen = {k: v for k, v in (prev.get("seen") or {}).items() if str(v) >= seen_from}
    notices = {n["id"]: n for n in prev.get("notices") or [] if isinstance(n, dict) and n.get("id")}
    events = list(prev.get("events") or [])
    checks, counts = [], {"meetings": 0, "details": 0, "cases": 0, "조정 사건": 0}
    cal, cal_state = browser_meetings(browser, now)
    today = now.strftime("%Y%m%d")
    keyof = lambda m: f"{m['cmitCd']}:{m['mtgId']}:{m['mtgSn']}"  # noqa: E731
    # 오늘 회의는 다 읽는다. 앞으로 회의는 위원회를 가리지 않고 조정·중재 회의 → 가까운 날 순으로 한 실행 DETAIL_BUDGET건까지
    pending = sorted((m for rows in cal.values() for m in rows if m["mtgYmd"] > today and keyof(m) not in seen),
                     key=lambda m: ("조정" not in m["label"] and "중재" not in m["label"], m["mtgYmd"]))
    allowed = {keyof(m) for m in pending[:DETAIL_BUDGET]}
    left = max(0, len(pending) - DETAIL_BUDGET)
    # 상세는 처음 볼 때만 읽으므로 사건 수는 그날 실행을 이어 센다(11-03: 두 번째 실행 화면이 '사건 10'으로 줄어 보였다)
    if str(prev.get("generatedAt") or "")[:10] == stamp[:10]:
        for k in ("details", "cases", "조정 사건"):
            counts[k] = int((prev.get("counts") or {}).get(k) or 0)
    first = True
    for slug, cname in COMMISSIONS:
        if not first:
            sleep(PAUSE)
        first = False
        url = f"{BASE}/nlrc/{slug}/main.do" if slug else f"{BASE}/"
        try:
            r = get(url, timeout=30)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")
            ms = meetings_of(r.text)
        except Exception as e:  # network/HTTP: unconfirmed, not zero
            checks.append({"source": cname, "status": "failed", "error": f"{type(e).__name__}: {str(e)[:60]}"})
            continue
        counts["meetings"] += len(ms)
        widget = len(ms)
        # 달력(브라우저 수집)의 회의를 더한다: 오늘 → 조정·교섭 회의 → 가까운 날 순. 첫 화면 칸과 겹치는 회의는 한 번만.
        have = {(m["mtgId"], m["mtgSn"]) for m in ms}
        extra = [m for m in cal.get(cname, []) if (m["mtgId"], m["mtgSn"]) not in have]
        extra.sort(key=lambda m: m["mtgYmd"])
        ms = ms + extra
        bad = 0
        for m in ms:
            key = keyof(m)
            ymd = m["mtgYmd"] or today
            # 미리 읽은 회의(값 '회의일@읽은 날')는 회의 당일 한 번 더 읽는다 — 사건이 더 붙을 수 있다
            if key in seen and not (ymd == today and "@" in str(seen[key]) and str(seen[key]).split("@")[1] < today):
                continue
            if ymd > today and key not in allowed:
                continue
            info = None
            # 11-03 첫 운영 실행: 상세 43건 중 2건 읽기 실패 — 오늘 회의만 보이므로 다음 날 다시 읽을 수 없다. 한 번만 더(5초 뒤) 묻는다.
            for wait in (PAUSE, 5.0):
                sleep(wait)
                try:
                    d = get(detail_url(m), timeout=30)
                    info = parse_detail(d.text) if d.status_code == 200 else None
                except Exception:
                    info = None
                if info:
                    break
            if not info:
                bad += 1
                continue
            seen[key] = ymd if ymd <= today else f"{ymd}@{today}"
            counts["details"] += 1
            if ymd > today:
                counts["ahead"] = counts.get("ahead", 0) + 1
            for c in info["cases"]:
                counts["cases"] += 1
                if "조정" in c["no"]:
                    counts["조정 사건"] += 1
                comp = beat_of(c["name"], rules)
                if not comp:
                    continue
                nid = f"labor:{m['cmitCd']}:{c['no']}:{info['day']}"
                if nid in notices:
                    continue
                n = {"id": nid, "company": comp, "commission": info["commission"], "commissionName": cname, "meeting": info["meeting"],
                     "day": info["day"], "time": c["time"], "caseNo": c["no"], "caseName": c["name"][:160],
                     "party": party_of(c["name"])[:80], "tier": tier_of(c["name"], info["meeting"]), "url": detail_url(m),
                     "firstSeen": stamp}
                # 같은 사건(위원회·사건번호)의 앞선 회의(11-04): 조정은 회의가 두세 번 열리고 마지막 회의에서 조정 중지·성립이 난다
                prior = sorted({x["day"] for x in notices.values() if x.get("caseNo") == c["no"] and x.get("commission") == info["commission"] and x["day"] < info["day"]})
                if prior:
                    n["prior"] = prior[-5:]
                notices[nid] = n
                ahead = (dt.date.fromisoformat(info["day"]) - now.date()).days
                if ahead > 0:
                    n["ahead"] = ahead
                events.append({"id": nid, "tier": n["tier"], "kind": ("노동위 조정 회의" if n["tier"] == "A" and "조정" in (c["no"] + info["meeting"]) else
                               "노동위 심판 회의") + (" (미리 잡힌 회의)" if ahead > 0 else "") + (" (같은 사건 다시)" if prior else ""),
                               "company": comp, "commission": cname, "caseNo": c["no"], "word": word_of(c["name"], c["no"]),
                               "text": line(n) + (f" · 미리 잡힌 회의({ahead}일 뒤, 달력)" if ahead > 0 else "")
                               + (f" · 같은 사건 앞선 회의 {', '.join(d[5:] for d in prior[-3:])}" if prior else ""),
                               "url": n["url"], "detectedAt": stamp, **({"prior": prior[-5:]} if prior else {}), **({"ahead": ahead} if ahead > 0 else {})})
        covered = cal_state.get(cname, {}).get("status") in ("ok", "stale")
        capped = widget >= WIDGET_CAP and not covered
        checks.append({"source": cname, "status": "ok" if not bad else "partial", "returned": widget,
                       **({"calendar": len(cal.get(cname, []))} if covered else {}),
                       **({"note": f"첫 화면 {WIDGET_CAP}건 상한 — 뒤 회의가 빠졌을 수 있음"} if capped else {}),
                       **({"error": f"회의 상세 {bad}건 읽기 실패"} if bad else {})})
    keep = (now - dt.timedelta(days=KEEP_DAYS)).isoformat(timespec="seconds")
    ok = sum(1 for c in checks if c["status"] == "ok")
    status = "complete" if ok == len(checks) else "failed" if not any(c["status"] in ("ok", "partial") for c in checks) else "partial"
    names = [name for _, name in COMMISSIONS]
    calendar = {"status": "unset" if not cal_state else "ok" if all(cal_state.get(x, {}).get("status") == "ok" for x in names) else "partial",
                "ahead": AHEAD_DAYS, "meetings": sum(len(v) for v in cal.values()), "left": left,
                "fetchedAt": max((v.get("fetchedAt") or "" for v in cal_state.values()), default=None),
                "missing": [x for x in names if cal_state.get(x, {}).get("status") not in ("ok", "stale")],
                "stale": [x for x in names if cal_state.get(x, {}).get("status") == "stale"]}
    return {"schema": SCHEMA, "generatedAt": stamp, "status": status, "checks": checks, "counts": counts, "calendar": calendar,
            "seen": seen,
            "notices": sorted([n for n in notices.values() if str(n.get("firstSeen")) >= keep], key=lambda n: (n["day"], n["time"]), reverse=True),
            "events": [e for e in events if str(e.get("detectedAt")) >= keep],
            "rules": ["중앙·지방노동위원회 첫 화면 '오늘 회의' 칸과 회의 상세(공개)의 사건명에서 당사자가 출입처인 것만. 계열사·하청업체 이름은 출입처가 아니다.",
                      f"첫 화면 칸은 위원회마다 {WIDGET_CAP}건까지만 보인다 — 달력(기자 컴퓨터 브라우저 수집)이 있는 위원회는 오늘부터 {AHEAD_DAYS}일 안 회의를 모두 읽고, 없는 위원회에서 {WIDGET_CAP}건이면 뒤 회의가 빠졌을 수 있다(미확인).",
                      "미리 잡힌 회의는 회의일 전에 알린다. 회의는 미뤄지거나 취소될 수 있다 — 회의 당일 상세를 한 번 더 읽는다.",
                      "사건명은 신청인 주장이다. 노동쟁의 조정은 조정 중지·성립, 구제신청은 인정·기각 결정이 따로 난다 — 결정·내용은 위원회 결정문·노사 확인 전 미확인.",
                      "노동쟁의 조정·교섭(요구·단위·공정대표)·부당노동행위는 A, 그 밖의 구제신청(해고·징계·차별 등)은 B. 사건 하나에 회의가 여러 번 열릴 수 있다(회의일마다 따로).",
                      "조회 실패 위원회는 0건이 아니라 미확인."]}


def main():
    import private_store
    now = now_kst()
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    previous = None
    if token:
        try:
            previous = private_store.get("kr-labor", token)
        except private_store.StoreError as e:
            print(f"::warning title=kr-labor-state::이전 상태 조회 실패({e}) — 본 회의도 다시 읽음")
    if private_store.late_scheduled_duplicate(previous, now):
        return
    browser = None
    if token:
        try:
            browser = private_store.get("kr-labor-browser", token)
        except private_store.StoreError as e:
            print(f"::warning title=kr-labor-browser::달력 수집 문서 조회 실패({e}) — 첫 화면 칸만 읽음")
    doc = run(now, previous, browser=browser)
    new = [e for e in doc["events"] if e["detectedAt"] == doc["generatedAt"]]
    c = doc["counts"]
    print(f"::notice title=kr-labor::상태 {doc['status']} · 오늘 회의 {c['meetings']} · 새로 읽은 상세 {c['details']} · 사건 {c['cases']}"
          f"(조정 {c['조정 사건']}) · 출입처 새 이벤트 {len(new)} · 위원회 정상 {sum(1 for x in doc['checks'] if x['status'] == 'ok')}/{len(doc['checks'])}"
          f" · 5건 상한 {sum(1 for x in doc['checks'] if x.get('note'))}곳 · 달력 {doc['calendar']['status']}(회의 {doc['calendar']['meetings']}"
          f", 미리 읽음 {c.get('ahead', 0)}, 남김 {doc['calendar']['left']})")
    if not token:
        print("::warning title=kr-labor-push::MCP_ACCESS_TOKEN 미설정 — 결과를 저장하지 않음")
        return
    if doc["status"] == "failed":
        sys.exit("노동위 첫 화면 조회 전체 실패 — 이전 결과 유지(0 아님)")
    status = private_store.put("kr-labor", doc, token)
    print(f"::notice title=kr-labor-push::기자 전용 저장소 전송 HTTP {status}")
    if status != 200:
        sys.exit(1)


if __name__ == "__main__":
    main()
