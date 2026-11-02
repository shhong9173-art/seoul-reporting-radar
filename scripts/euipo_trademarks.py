"""유럽 상표 출원(EUIPO Trademark Search API) — 출입처 영문 출원인 이름으로 최근 출원을 본다. trademark_watch.py가 주 1회 부른다.

- 토큰: OAuth client_credentials(scope uid) — 운영 주소는 CAS(euipo.europa.eu/cas-server-webapp/oidc/accessToken). 공개 꾸러미 기본값
  auth.euipo.europa.eu는 운영에서 502다(11-02). docs/euipo-api.md.
- 검색: applicants.name 와일드카드(RSQL), 출원일 내림차순. 응답의 출원인 이름을 회사 규칙으로 다시 거른다(이름 일부만 같은 다른 회사).
- 403(access-forbidden)은 앱의 상품 구독이 운영 승인 전일 때 — 실패가 아니라 '승인 대기'로 남기고 다음 회사는 묻지 않는다.
- 회사마다 첫 성공 읽기는 기준선. 처음 보는 출원번호만 새 출원. 키·토큰은 저장·출력하지 않는다.
"""
from __future__ import annotations

import datetime as dt
import re

TOKEN_URL = "https://euipo.europa.eu/cas-server-webapp/oidc/accessToken"
SEARCH_URL = "https://api.euipo.europa.eu/trademark-search/trademarks"
SOURCE = "EUIPO Trademark Search(유럽연합 상표 출원)"
KEEP = 300


def _date(v):
    m = re.match(r"(20\d\d-\d\d-\d\d)", str(v or ""))
    return m.group(1) if m else ""


def _classes(v):
    out = []
    for c in v or []:
        try:
            n = int(c)
        except (TypeError, ValueError):
            continue
        if 1 <= n <= 45:
            out.append(f"{n:02d}")
    return sorted(set(out))


def _mark(it):
    w = it.get("wordMarkSpecification")
    if isinstance(w, dict) and w.get("verbalElement"):
        return str(w["verbalElement"]).strip()[:120]
    return f"({it.get('markFeature') or '표장'})"


def _applicants(it):
    return [str(a.get("name") or "").strip() for a in it.get("applicants") or [] if isinstance(a, dict) and a.get("name")]


def token(client_id, secret, post):
    r = post(TOKEN_URL, data={"grant_type": "client_credentials", "client_id": client_id, "client_secret": secret, "scope": "uid"},
             headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}, timeout=40)
    if r.status_code != 200:
        raise RuntimeError(f"토큰 HTTP {r.status_code}")
    tok = (r.json() or {}).get("access_token")
    if not tok:
        raise RuntimeError("토큰 응답에 access_token 없음")
    return tok


def run(cfg, previous, now, *, client_id, secret, post, get, only_unsettled=False):
    """cfg = trademark_watch.json의 euipo 칸. previous = 직전 문서의 eu 칸. only_unsettled면(평일 재시도) 직전이 정상인 회사는 그대로 둔다."""
    stamp = now.isoformat(timespec="seconds")
    prev = previous if isinstance(previous, dict) else {}
    prev_checks = {c.get("company"): c for c in prev.get("checks") or [] if isinstance(c, dict)}
    seen = {k: dict(v) for k, v in (prev.get("seen") or {}).items() if isinstance(v, dict)}
    titles = {k: dict(v) for k, v in (prev.get("titles") or {}).items() if isinstance(v, dict)}
    old = {f["id"]: f for f in prev.get("filings") or [] if isinstance(f, dict) and f.get("id")}
    since = (now.date() - dt.timedelta(days=int(cfg.get("windowDays", 120)))).isoformat()
    industries = cfg.get("industries") or {}
    checks, fresh = [], []
    try:
        tok = token(client_id, secret, post) if client_id and secret else None
        tok_err = None if tok else "EUIPO_CLIENT_ID·SECRET 없음"
    except Exception as e:  # noqa: BLE001
        tok, tok_err = None, str(e)[:60] or type(e).__name__
    blocked = None
    for c in cfg.get("applicants") or []:
        name = c["company"]
        pc = prev_checks.get(name)
        if only_unsettled and pc and pc.get("status") == "ok":
            checks.append(pc)
            continue
        if not tok:
            checks.append({"company": name, "status": "unset" if "없음" in (tok_err or "") else "failed", "error": tok_err})
            continue
        if blocked:
            checks.append({"company": name, "status": "waiting", "reason": blocked})
            continue
        try:
            r = get(SEARCH_URL, params={"query": f'applicants.name=="{c["query"]}"', "size": int(cfg.get("size", 30)), "sort": "applicationDate:desc"},
                    headers={"Authorization": f"Bearer {tok}", "X-IBM-Client-Id": client_id, "Accept": "application/json"}, timeout=40)
            if r.status_code == 403:
                blocked = "상품 구독 운영 승인 대기(403 access-forbidden)"
                checks.append({"company": name, "status": "waiting", "reason": blocked})
                continue
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")
            body = r.json() or {}
        except Exception as e:  # noqa: BLE001
            checks.append({"company": name, "status": "failed", "error": str(e)[:60] or type(e).__name__})
            continue
        accept = re.compile(c.get("accept") or re.escape(c["query"].strip("*")), re.I)
        exclude = re.compile(c["exclude"], re.I) if c.get("exclude") else None
        rows = body.get("trademarks") or []
        first_read = not (pc and pc.get("status") == "ok") and name not in seen
        core = set((industries.get(c.get("industry")) or {}).get("core") or [])
        kept = other = 0
        for it in rows:
            if not isinstance(it, dict):
                continue
            apps = _applicants(it)
            if not any(accept.search(a) and not (exclude and exclude.search(a)) for a in apps):
                other += 1
                continue
            day = _date(it.get("applicationDate"))
            no = str(it.get("applicationNumber") or "").strip()
            if not no or (day and day < since):
                continue
            kept += 1
            fid = f"euipo:{no}"
            mark = _mark(it)
            nt = re.sub(r"[\W_]+", "", mark.casefold())
            new = no not in seen.get(name, {})
            seen.setdefault(name, {})[no] = seen.get(name, {}).get(no) or now.date().isoformat()
            classes = _classes(it.get("niceClasses"))
            title_new = bool(nt) and nt not in titles.get(name, {})
            if nt:
                titles.setdefault(name, {}).setdefault(nt, now.date().isoformat())
            if fid in old:
                f = old[fid]
                f.update(status=it.get("status") or f.get("status"), classes=classes or f.get("classes"))
                continue
            is_new = new and not first_read
            f = {"id": fid, "company": name, "applicationNumber": no, "title": mark, "applicationDate": day, "classes": classes,
                 "coreClasses": sorted(core & set(classes)), "status": it.get("status"), "markFeature": it.get("markFeature"),
                 "applicants": apps[:3], "firstSeen": stamp, "isNew": is_new, "baseline": first_read,
                 "titleNew": is_new and title_new,
                 "tier": ("B" if title_new and core & set(classes) else "C") if is_new else None,
                 "url": f"https://euipo.europa.eu/eSearch/#details/trademarks/{no}"}
            old[fid] = f
            if is_new:
                fresh.append(fid)
        checks.append({"company": name, "status": "ok", "query": c["query"], "rawTotal": body.get("totalElements"), "read": len(rows),
                       "kept": kept, **({"otherApplicants": other} if other else {}), **({"baseline": True} if first_read else {})})
    keep_from = (now.date() - dt.timedelta(days=int(cfg.get("keepDays", 180)))).isoformat()
    filings = sorted((f for f in old.values() if f.get("firstSeen", "")[:10] >= keep_from or (f.get("applicationDate") or "") >= keep_from),
                     key=lambda f: (f.get("firstSeen", ""), f.get("applicationDate", "")), reverse=True)[:KEEP]
    ok = sum(1 for c in checks if c["status"] == "ok")
    waiting = sum(1 for c in checks if c["status"] == "waiting")
    status = ("unset" if checks and all(c["status"] == "unset" for c in checks) else "complete" if ok == len(checks) and ok
              else "waiting" if waiting and not ok else "failed" if not ok else "partial")
    return {"source": SOURCE, "generatedAt": stamp, "status": status, "window": {"from": since, "to": now.date().isoformat()},
            "baselineSince": prev.get("baselineSince") or (stamp if ok else None), "checks": checks, "filings": filings,
            "fresh": fresh, "seen": seen, "titles": {k: dict(list(v.items())[-2000:]) for k, v in titles.items()},
            **({"blocked": blocked} if blocked else {})}
