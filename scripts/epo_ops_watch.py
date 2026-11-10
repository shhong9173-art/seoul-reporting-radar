"""출입처 유럽(EP)·국제(WO) 특허 공개 감시 — EPO OPS 3.2(Open Patent Services), 주 1회(토 06:40 KST).

- EP 공개는 보통 수요일, WO(PCT) 공개는 목요일이라 금요일 밤(유럽 시간) 뒤에 읽는다.
- 검색: GET /rest-services/published-data/search/biblio?q=pa="…" and pd within "시작 끝" and (pn=EP or pn=WO)
  — 한 쪽 100건(X-OPS-Range), 회사당 최대 3쪽. 0건은 HTTP 404(SERVER.EntityNotFound)로 온다.
- 공정 이용(Fair use charter): 응답마다 X-Throttling-Control('idle|busy|overloaded (… search=green:30)')을 읽어
  검색이 red·black이거나 403(CLIENT.RobotDetected 등)이면 그 자리에서 멈춘다. 남은 회사는 대기(0건 아님 — 미확인)로 두고
  같은 주말 재시도 칸(토 14:40·일 06:40)에 그 회사들만 다시 묻는다. 회피·반복 호출은 하지 않는다(11-10 탐침: 1.2초 간격에서 robot 판정).
- OPS 약관 3.2: 자료 그 자체를 공개하지 않는다 — 결과는 기자 전용 저장소(epo-patents)에만, Actions 로그엔 건수만.
- 키·토큰은 저장·출력하지 않는다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "data" / "epo_ops_watch.json"
TOKEN_URL = "https://ops.epo.org/3.2/auth/accesstoken"
SEARCH_URL = "https://ops.epo.org/3.2/rest-services/published-data/search/biblio"
UA = "seoul-reporting-radar/1.0 (+https://github.com/shhong9173-art/seoul-reporting-radar)"
KST = dt.timezone(dt.timedelta(hours=9))
SCHEMA = "epo_patents/v1"
FEED = "epo-patents"
PAGE = 100
MAX_PAGES = 3
FIRST_DAYS = 120     # 회사 기준선(처음 성공한 실행)
WINDOW_DAYS = 35     # 이후 주간 창 — 색인이 늦게 붙는 공개까지 5주 겹쳐 읽는다
KEEP_DAYS = 200
MAX_FILINGS = 4000
SEEN_KEEP = 8000
RETRY_DAYS = 3       # 직전 결과가 3일 안이고 완료가 아니면 실패·대기한 회사만 다시
MIN_GAP = 3.0

RULES = [
    "특허 공개는 출원 뒤 약 18개월(또는 조기 공개)에 나오는 공보다. 개발 완료·양산·사업 진출이 아니다.",
    "EP는 유럽특허청 공개, WO는 PCT 국제출원 공개다. 같은 패밀리의 국내(KR) 출원이 KIPRIS에 먼저 공개됐을 수 있다 — 우선권 번호로 확인.",
    "'새 공개'는 이 감시가 처음 본 공개번호다. 회사마다 처음 성공한 조회(최근 120일)는 기준선이라 새 공개로 치지 않는다.",
    "출원인 검색(pa=)은 낱말로 넓게 맞아 회사 규칙으로 다시 거른다. 공동 출원(현대차·기아, 대학·연구소)은 해당 회사 모두에 붙는다.",
    "조회 실패·EPO 서버 과부하로 멈춘 회사는 0건이 아니라 미확인.",
    "EPO OPS 약관 3.2: 자료 그 자체를 공개하지 않는다 — 기자 전용 저장소에만 둔다(공개 저장소·Pages·공개 도구에 싣지 않음).",
]


class TokenError(RuntimeError):
    pass


def now_kst():
    return dt.datetime.now(KST)


def as_list(x):
    return x if isinstance(x, list) else ([x] if x else [])


def _t(v):
    if isinstance(v, dict):
        v = v.get("$")
    return str(v).strip() if isinstance(v, (str, int)) and str(v).strip() else None


def iso(d):
    d = str(d or "")
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}" if re.fullmatch(r"\d{8}", d) else (d or None)


THROTTLE_STATE = re.compile(r"^\s*([A-Za-z]+)")
THROTTLE_SERVICE = re.compile(r"(\w+)=(\w+):(\d+)")


def throttle(header):
    """'overloaded (images=green:50, …, search=black:0)' → (서버 상태, 검색 신호, 분당 허용)."""
    h = str(header or "")
    m = THROTTLE_STATE.match(h)
    svc = {k.lower(): (c.lower(), int(n)) for k, c, n in THROTTLE_SERVICE.findall(h)}
    color, per_min = svc.get("search", (None, None))
    return (m.group(1).lower() if m else None), color, per_min


def gap(state, color, per_min):
    """다음 검색까지 쉴 초. None이면 멈춤(검색 red·black — 공정 이용 규칙)."""
    if color in ("red", "black"):
        return None
    base = 60.0 / per_min if per_min else MIN_GAP
    if color == "yellow" or state == "overloaded":
        return max(10.0, base * 2)
    if state == "busy":
        return max(5.0, base * 1.5)
    return max(MIN_GAP, base * 1.2)


def fault(text):
    m = re.search(r"<code>([^<]+)</code>", str(text or ""))
    return m.group(1).strip() if m else None


def get_token(key, secret, post):
    r = post(TOKEN_URL, auth=(key, secret), data={"grant_type": "client_credentials"},
             headers={"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded"}, timeout=60)
    if r.status_code != 200:
        raise TokenError(f"토큰 HTTP {r.status_code}")
    tok = (r.json() or {}).get("access_token")
    if not tok:
        raise TokenError("토큰 응답에 access_token 없음")
    return tok


def _doc(e):
    bd = e.get("bibliographic-data") or {}
    ids = as_list((bd.get("publication-reference") or {}).get("document-id"))
    pub = next((d for d in ids if isinstance(d, dict) and d.get("@document-id-type") == "docdb"), None) or {}
    cc, no, kind = _t(pub.get("country")) or e.get("@country"), _t(pub.get("doc-number")) or e.get("@doc-number"), _t(pub.get("kind")) or e.get("@kind")
    if not (cc and no and kind):
        return None
    titles = [t for t in as_list(bd.get("invention-title")) if _t(t)]
    en = next((t for t in titles if isinstance(t, dict) and t.get("@lang") == "en"), None)
    pick = en or (titles[0] if titles else None)
    names = []
    for a in as_list(((bd.get("parties") or {}).get("applicants") or {}).get("applicant")):
        n = _t(((a or {}).get("applicant-name") or {}).get("name"))
        if n:
            n = re.sub(r"\s*\[[A-Z]{2}\]\s*$", "", n).strip().rstrip(",").strip()
            if n and n not in names:
                names.append(n)
    ipc = []
    for c in as_list((bd.get("classifications-ipcr") or {}).get("classification-ipcr")):
        m = re.match(r"\s*([A-H]\d{2}[A-Z])\s*(\d+)\s*/\s*(\d+)", _t((c or {}).get("text")) or "")
        code = f"{m.group(1)} {m.group(2)}/{m.group(3)}" if m else None
        if code and code not in ipc:
            ipc.append(code)
    app = next((_t(d.get("date")) for d in as_list((bd.get("application-reference") or {}).get("document-id"))
                if isinstance(d, dict) and _t(d.get("date"))), None)
    prio = None
    for p in as_list((bd.get("priority-claims") or {}).get("priority-claim")):
        for d in as_list((p or {}).get("document-id")):
            if isinstance(d, dict) and d.get("@document-id-type") in ("epodoc", "original") and _t(d.get("doc-number")):
                prio = prio or {"number": _t(d.get("doc-number")), "date": iso(_t(d.get("date")))}
    pid = f"{cc}{no}{kind}"
    return {"id": pid, "country": cc, "number": no, "kind": kind, "date": iso(_t(pub.get("date"))),
            "title": _t(pick), "titleLang": (pick or {}).get("@lang") if isinstance(pick, dict) else None,
            "applicants": names, "ipc": ipc[:4], "applicationDate": iso(app), "priority": prio,
            "family": e.get("@family-id"), "url": f"https://worldwide.espacenet.com/patent/search?q=pn%3D{pid}"}


def parse(body):
    bs = ((body or {}).get("ops:world-patent-data") or {}).get("ops:biblio-search") or {}
    try:
        total = int(bs.get("@total-result-count") or 0)
    except (TypeError, ValueError):
        total = 0
    rows = []
    for ed in as_list((bs.get("ops:search-result") or {}).get("exchange-documents")):
        for e in as_list((ed or {}).get("exchange-document")):
            row = _doc(e) if isinstance(e, dict) else None
            if row:
                rows.append(row)
    return total, rows


def accepted(names, c):
    acc = re.compile(c["accept"], re.I)
    exc = re.compile(c["exclude"], re.I) if c.get("exclude") else None
    return [n for n in names if acc.search(n) and not (exc and exc.search(n))]


def query(c, start, end):
    return f'pa="{c["query"]}" and pd within "{start:%Y%m%d} {end:%Y%m%d}" and (pn=EP or pn=WO)'


def plan(previous, now, *, force=False):
    """None = 전체, set() = 건너뜀, {회사} = 그 회사만(직전 실행이 3일 안이고 완료가 아닐 때)."""
    if force or not isinstance(previous, dict) or previous.get("schema") != SCHEMA:
        return None
    try:
        age = (now - dt.datetime.fromisoformat(str(previous.get("generatedAt")))).total_seconds() / 86400
    except (TypeError, ValueError):
        return None
    if not 0 <= age < RETRY_DAYS:
        return None
    if previous.get("status") == "complete":
        return set()
    return {c["company"] for c in previous.get("checks") or [] if c.get("status") != "ok"}


def run(cfg, previous, now, *, key, secret, post, get, sleep=time.sleep, only=None):
    prev = previous if isinstance(previous, dict) and previous.get("schema") == SCHEMA else {}
    baselined = set(prev.get("baselinedCompanies") or [])
    stamp = now.isoformat(timespec="seconds")
    end = now.date()
    companies = [c for c in cfg["companies"] if only is None or c["company"] in only]
    prev_checks = {c.get("company"): c for c in prev.get("checks") or []}
    token, tok_err = None, None
    if not key or not secret:
        tok_err = "EPO_OPS_KEY·EPO_OPS_SECRET 없음"
    else:
        try:
            token = get_token(key, secret, post)
        except Exception as e:  # noqa: BLE001 — 키 값이 섞이지 않게 종류만
            tok_err = str(e)[:120] if isinstance(e, TokenError) else f"토큰 요청 실패({type(e).__name__})"
    refreshed = False
    stopped = None
    last = {}
    found = {}
    checks = []
    for i, c in enumerate(companies):
        if token is None:
            checks.append({"company": c["company"], "query": c["query"], "status": "failed", "error": tok_err, "checkedAt": stamp})
            continue
        if stopped:
            checks.append({"company": c["company"], "query": c["query"], "status": "waiting", "reason": stopped, "checkedAt": stamp})
            continue
        first = c["company"] not in baselined
        start = end - dt.timedelta(days=FIRST_DAYS if first else WINDOW_DAYS)
        q = query(c, start, end)
        rows, total, err, pos, wait = [], 0, None, 1, MIN_GAP
        while True:
            r = get(SEARCH_URL, params={"q": q}, timeout=90,
                    headers={"Authorization": f"Bearer {token}", "Accept": "application/json", "User-Agent": UA,
                             "X-OPS-Range": f"{pos}-{pos + PAGE - 1}"})
            st, col, pm = throttle((getattr(r, "headers", None) or {}).get("X-Throttling-Control"))
            if st or col:
                last = {"state": st, "search": col, "perMinute": pm, "at": stamp}
            code = fault(getattr(r, "text", ""))
            if r.status_code in (400, 401) and code and "token" in code.lower() and not refreshed:
                refreshed = True
                try:
                    token = get_token(key, secret, post)
                    continue
                except Exception:  # noqa: BLE001
                    err = "토큰 재발급 실패"
                    break
            if r.status_code == 200:
                t, rs = parse(r.json())
                total = t
                rows += rs
            elif r.status_code == 404 and code == "SERVER.EntityNotFound":
                total = 0
            elif r.status_code == 403:
                stopped = f"EPO {code or 'HTTP 403'} — 공정 이용 규칙상 이번 실행 멈춤"
                err = stopped
                break
            else:
                err = f"HTTP {r.status_code}{f' {code}' if code else ''}"
                break
            wait = gap(st, col, pm)
            if wait is None:
                stopped = f"EPO 검색 {col}(서버 {st}) — 공정 이용 규칙상 이번 실행 멈춤"
            if wait is None or pos + PAGE > total or pos + PAGE > PAGE * MAX_PAGES:
                break
            sleep(wait)
            pos += PAGE
        if err:
            checks.append({"company": c["company"], "query": c["query"], "status": "waiting" if err == stopped else "failed",
                           **({"reason": err} if err == stopped else {"error": err}), "checkedAt": stamp})
            continue
        mine, others = 0, {}
        for row in rows:
            ok = accepted(row["applicants"], c)
            if ok:
                mine += 1
                f = found.setdefault(row["id"], {**row, "companies": []})
                if c["company"] not in f["companies"]:
                    f["companies"].append(c["company"])
                f.setdefault("baselineFor", set())
                if first:
                    f["baselineFor"].add(c["company"])
            else:
                for n in row["applicants"][:2]:
                    others[n] = others.get(n, 0) + 1
        checks.append({"company": c["company"], "query": c["query"], "status": "ok", "total": total, "got": len(rows), "matched": mine,
                       "window": {"from": start.isoformat(), "to": end.isoformat()}, "baseline": first,
                       **({"truncated": True} if total > PAGE * MAX_PAGES else {}),
                       **({"otherApplicants": sorted(others, key=lambda n: -others[n])[:3]} if others else {}), "checkedAt": stamp})
        if first:
            baselined.add(c["company"])
        if i < len(companies) - 1 and not stopped:
            sleep(wait if wait else MIN_GAP)

    # 이번에 묻지 않은 회사(재시도 실행)는 직전 결과를 그대로 둔다
    asked = {c["company"] for c in checks}
    checks += [pc for name, pc in prev_checks.items() if name not in asked and any(x["company"] == name for x in cfg["companies"])]
    order = {c["company"]: i for i, c in enumerate(cfg["companies"])}
    checks.sort(key=lambda c: order.get(c.get("company"), 999))

    seen = list(prev.get("seen") or [])
    seen_set = set(seen)
    filings = {f["id"]: f for f in prev.get("filings") or [] if isinstance(f, dict) and f.get("id")}
    fresh = []
    for pid, row in found.items():
        base_for = row.pop("baselineFor", set())
        old = filings.get(pid)
        if old:
            merged = {**old, **{k: v for k, v in row.items() if v not in (None, [], "")}}
            merged["companies"] = sorted(set(old.get("companies") or []) | set(row["companies"]), key=lambda n: order.get(n, 999))
            merged["firstSeen"], merged["isNew"] = old.get("firstSeen"), old.get("isNew", False)
            filings[pid] = merged
        else:
            is_new = pid not in seen_set and not set(row["companies"]) <= base_for
            filings[pid] = {**row, "firstSeen": stamp, "isNew": is_new}
            if is_new:
                fresh.append(pid)
        if pid not in seen_set:
            seen.append(pid)
            seen_set.add(pid)
    cut = (end - dt.timedelta(days=KEEP_DAYS)).isoformat()
    kept = sorted((f for f in filings.values() if str(f.get("date") or f.get("firstSeen") or "")[:10] >= cut),
                  key=lambda f: (str(f.get("date") or ""), f["id"]), reverse=True)[:MAX_FILINGS]

    oks = [c for c in checks if c.get("status") == "ok"]
    waits = [c for c in checks if c.get("status") == "waiting"]
    status = ("complete" if len(oks) == len(checks) and checks else
              "failed" if not oks and not waits else
              "waiting" if not oks else "partial")
    return {
        "schema": SCHEMA, "generatedAt": stamp, "status": status,
        "source": "EPO OPS 3.2(Open Patent Services) — 유럽특허(EP)·국제특허(WO·PCT) 공개 서지",
        "terms": RULES[-1],
        "window": {"to": end.isoformat(), "field": "공개일", "firstDays": FIRST_DAYS, "weeklyDays": WINDOW_DAYS},
        "baselineSince": prev.get("baselineSince") or (stamp if oks else None),
        "baselinedCompanies": sorted(baselined, key=lambda n: order.get(n, 999)),
        "throttle": {**last, **({"stopped": stopped} if stopped else {})},
        **({"retry": {"at": stamp, "companies": sorted(only, key=lambda n: order.get(n, 999))}} if only is not None else {}),
        "checks": checks, "filings": kept, "fresh": fresh, "seen": seen[-SEEN_KEEP:],
        "rules": RULES, "confirmedScoops": 0,
    }


def main():
    argparse.ArgumentParser(description="출입처 유럽·국제 특허 공개 감시(EPO OPS, 기자 전용 저장소로)").parse_args()
    now = now_kst()
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    key = os.environ.get("EPO_OPS_KEY", "").strip()
    secret = os.environ.get("EPO_OPS_SECRET", "").strip()
    force = str(os.environ.get("FORCE_RUN", "")).lower() in ("1", "true", "yes")
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    import private_store
    previous = None
    if token:
        try:
            previous = private_store.get(FEED, token)
        except private_store.StoreError as e:
            print(f"::warning title=epo-patents-state::이전 상태 조회 실패({e}) — 저장하지 않고 끝냄(기준선 재설정 방지)")
            sys.exit(1)
    if private_store.late_scheduled_duplicate(previous, now):
        return
    only = plan(previous, now, force=force)
    if only is not None and not only:
        print("::notice title=epo-patents::직전 결과(3일 안)가 정상 — EPO를 부르지 않고 끝냄")
        return
    if only:
        print(f"::notice title=epo-patents-retry::직전에 실패·대기한 회사만 다시: {len(only)}곳")
    import requests
    doc = run(cfg, previous, now, key=key, secret=secret, post=requests.post, get=requests.get, only=only)
    counts = {}
    for c in doc["checks"]:
        counts[c["status"]] = counts.get(c["status"], 0) + 1
    th = doc.get("throttle") or {}
    print(f"::notice title=epo-patents::상태 {doc['status']} · 회사 {' · '.join(f'{k} {v}' for k, v in sorted(counts.items()))}"
          f" · 저장 공개 {len(doc['filings'])} · 새 공개 {len(doc['fresh'])} · 기준선 회사 {len(doc['baselinedCompanies'])}"
          f" · EPO 서버 {th.get('state') or '?'}/검색 {th.get('search') or '?'}{' · ' + th['stopped'] if th.get('stopped') else ''}")
    errors = sorted({c.get("error") for c in doc["checks"] if c.get("error")})
    if errors:
        print(f"::notice title=epo-patents-errors::{', '.join(errors)[:300]}")
    if not token:
        print("::warning title=epo-patents-push::MCP_ACCESS_TOKEN 미설정 — 결과를 저장하지 않음")
        return
    status = private_store.put(FEED, doc, token)
    print(f"::notice title=epo-patents-push::기자 전용 저장소 전송 HTTP {status}")
    if status != 200:
        sys.exit(1)
    if any(c["status"] == "failed" for c in doc["checks"]):
        sys.exit("일부 회사 조회 실패 — 해당 회사는 미확인(0건 아님)")


if __name__ == "__main__":
    main()
