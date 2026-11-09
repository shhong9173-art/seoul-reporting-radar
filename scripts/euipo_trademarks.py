"""유럽 상표 출원(EUIPO Trademark Search API) — 출입처 영문 출원인 이름으로 최근 출원을 본다. trademark_watch.py가 주 1회 부른다.

- 토큰: OAuth client_credentials(scope uid) — 운영 주소는 CAS(euipo.europa.eu/cas-server-webapp/oidc/accessToken). 공개 꾸러미 기본값
  auth.euipo.europa.eu는 운영에서 502다(11-02). docs/euipo-api.md.
- 검색: applicants.name 와일드카드(RSQL), 출원일 내림차순. 응답의 출원인 이름을 회사 규칙으로 다시 거른다(이름 일부만 같은 다른 회사).
- 403(access-forbidden)은 앱의 상품 구독이 운영 승인 전일 때 — 실패가 아니라 '승인 대기'로 남기고 다음 회사는 묻지 않는다.
- 회사마다 첫 성공 읽기는 기준선. 처음 보는 출원번호만 새 출원. 키·토큰은 저장·출력하지 않는다.
- 11-09: 운영 검색이 막혀 있는 동안(토큰 실패·403) SIGNA_API_KEY가 있으면 같은 회사를 Signa(2차 원천, signa_trademarks.py)로 읽는다.
  EUIPO는 실행마다 토큰 1·검색 1로 계속 확인해 승인되면 저절로 EUIPO로 돌아간다. 원천은 회사별 checks[].via·filings[].via에 남긴다.
"""
from __future__ import annotations

import datetime as dt
import re

import signa_trademarks as signa

TOKEN_URL = "https://euipo.europa.eu/cas-server-webapp/oidc/accessToken"
SEARCH_URL = "https://api.euipo.europa.eu/trademark-search/trademarks"
SOURCE = "EUIPO Trademark Search(유럽연합 상표 출원)"
# 관청별 표시(11-09: 미국은 Signa만으로 같은 규칙을 쓴다 — USPTO 직접 API는 ID.me 인증 실패)
OFFICES = {"EM": {"source": SOURCE, "prefix": "euipo", "url": "https://euipo.europa.eu/eSearch/#details/trademarks/{no}"},
           "US": {"source": "USPTO 상표 출원(Signa 경유)", "prefix": "uspto",
                  "url": "https://tsdr.uspto.gov/#caseNumber={no}&caseType=SERIAL_NO&searchType=statusSearch"}}
RICH_CREDITS = 3000   # 직전 남은 Signa 크레딧이 이 이상이면 회사별 조회 주기(signaEvery)를 무시하고 매주 다 본다

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


def run(cfg, previous, now, *, client_id, secret, post, get, only_unsettled=False, signa_key=None, office="EM"):
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
        tok = token(client_id, secret, post) if client_id and secret and office == "EM" else None
        tok_err = None if tok else ("EUIPO_CLIENT_ID·SECRET 없음" if office == "EM" else "SIGNA_API_KEY 없음")
    except Exception as e:  # noqa: BLE001
        tok, tok_err = None, str(e)[:60] or type(e).__name__
    blocked = None
    signa_left = None
    meta = OFFICES[office]
    # Signa 크레딧이 넉넉하면(가입 크레딧) 매주 다 보고, 모자라면 회사별 주기(signaEvery 주)대로 — 유럽·미국 출원이 드문 곳은 4주에 한 번
    rich = not isinstance(prev.get("signaCreditsLeft"), int) or prev["signaCreditsLeft"] >= RICH_CREDITS
    for c in cfg.get("applicants") or []:
        name = c["company"]
        pc = prev_checks.get(name)
        if only_unsettled and pc and pc.get("status") == "ok":
            checks.append(pc)
            continue
        every = int(c.get("signaEvery") or 1)
        if not rich and every > 1 and pc and pc.get("status") == "ok" and pc.get("via") == "signa":
            try:
                age = (now - dt.datetime.fromisoformat(str(pc.get("checkedAt")))).days
            except (TypeError, ValueError):
                age = None
            if age is not None and 0 <= age < every * 7 - 1:
                checks.append({**pc, "carried": True})   # 이번 주는 안 묻고 직전 결과를 둔다(크레딧 아낌)
                continue
        body, via, err = None, None, None
        if tok and not blocked and office == "EM":
            try:
                r = get(SEARCH_URL, params={"query": f'applicants.name=="{c["query"]}"', "size": int(cfg.get("size", 30)), "sort": "applicationDate:desc"},
                        headers={"Authorization": f"Bearer {tok}", "X-IBM-Client-Id": client_id, "Accept": "application/json"}, timeout=40)
                if r.status_code == 403:
                    blocked = "상품 구독 운영 승인 대기(403 access-forbidden)"
                elif r.status_code != 200:
                    raise RuntimeError(f"HTTP {r.status_code}")
                else:
                    body, via = r.json() or {}, "euipo"
            except Exception as e:  # noqa: BLE001
                err = str(e)[:60] or type(e).__name__
        if body is None and err is None and signa_key and (blocked or not tok):
            # EUIPO 직접 조회가 막힌 동안만 Signa — 크레딧이 바닥이면 더 묻지 않는다(미확인)
            if signa_left is not None and signa_left < signa.MIN_CREDITS:
                checks.append({"company": name, "status": "waiting", "reason": f"Signa 크레딧 부족(남은 {signa_left}) — 다음 달 초기화 뒤", "via": "signa"})
                continue
            try:
                rows, signa_left, _more = signa.search(c["query"].strip("*"), since, key=signa_key, get=get, office=office)
                body, via = {"trademarks": rows, "totalElements": len(rows)}, "signa"
            except Exception as e:  # noqa: BLE001
                checks.append({"company": name, "status": "failed", "error": str(e)[:60] or type(e).__name__, "via": "signa"})
                continue
        if body is None:
            if err:
                checks.append({"company": name, "status": "failed", "error": err})
            elif blocked:
                checks.append({"company": name, "status": "waiting", "reason": blocked})
            else:
                checks.append({"company": name, "status": "unset" if "없음" in (tok_err or "") else "failed", "error": tok_err})
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
            fid = f"{meta['prefix']}:{no}"
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
                 "url": meta["url"].format(no=no),
                 **({"via": "signa"} if via == "signa" else {}),
                 **({"route": "마드리드 지정"} if str(it.get("filingRoute") or "").startswith("madrid") else {})}
            old[fid] = f
            if is_new:
                fresh.append(fid)
        checks.append({"company": name, "status": "ok", "query": c["query"], "rawTotal": body.get("totalElements"), "read": len(rows),
                       "kept": kept, "via": via, "checkedAt": stamp, **({"otherApplicants": other} if other else {}), **({"baseline": True} if first_read else {})})
    keep_from = (now.date() - dt.timedelta(days=int(cfg.get("keepDays", 180)))).isoformat()
    filings = sorted((f for f in old.values() if f.get("firstSeen", "")[:10] >= keep_from or (f.get("applicationDate") or "") >= keep_from),
                     key=lambda f: (f.get("firstSeen", ""), f.get("applicationDate", "")), reverse=True)[:KEEP]
    ok = sum(1 for c in checks if c["status"] == "ok")
    waiting = sum(1 for c in checks if c["status"] == "waiting")
    status = ("unset" if checks and all(c["status"] == "unset" for c in checks) else "complete" if ok == len(checks) and ok
              else "waiting" if waiting and not ok else "failed" if not ok else "partial")
    via_signa = sum(1 for c in checks if c.get("via") == "signa" and c["status"] == "ok")
    return {"source": meta["source"], "office": office, "generatedAt": stamp, "status": status, "window": {"from": since, "to": now.date().isoformat()},
            "baselineSince": prev.get("baselineSince") or (stamp if ok else None), "checks": checks, "filings": filings,
            "fresh": fresh, "seen": seen, "titles": {k: dict(list(v.items())[-2000:]) for k, v in titles.items()},
            **({"blocked": blocked} if blocked else {}),
            **({"provider": "signa", "providerNote": signa.SOURCES.get(office, signa.SOURCE),
                "signaCreditsLeft": signa_left if signa_left is not None else prev.get("signaCreditsLeft")} if via_signa else {}),
            **({"carried": [c["company"] for c in checks if c.get("carried")]} if any(c.get("carried") for c in checks) else {})}
