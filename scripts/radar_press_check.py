"""오늘의 레이더 A·B 항목 자동 보도 대조.

- Worker /ingest/radar-items(Bearer)에서 대조 낱말이 붙은 A·B 항목을 받는다(낱말은 digest.mjs가 항목 종류별로 만든다).
- scoop_screen의 채널(네이버 뉴스 API·빙·구글)과 판정을 그대로 쓰되, 항목 날짜 3일 전 이후 기사만 센다.
- 결과는 기자 전용 저장소(radar-check)로만. 공개 로그는 건수만. 채널 실패는 0건이 아니라 미확인.
- 처음 판정과 시각을 남겨, '미보도 후보'였다가 기사가 나온 항목을 알 수 있게 한다.
"""
from __future__ import annotations

import datetime as dt
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import scoop_screen as ss  # noqa: E402

SCHEMA = "radar_check/v1"
HOURS = 72
MAX_ITEMS = 40
LEAD_DAYS = 3
KEEP_DAYS = 14


def subject(who):
    name = re.sub(r"\(.*?\)", "", str(who or "").split("·")[0]).strip()
    return ss.canon(name)


def item_day(x):
    m = re.match(r"(\d{4}-\d{2}-\d{2})", str(x.get("date") or ""))
    if m:
        return dt.date.fromisoformat(m.group(1))
    m = re.match(r"(\d{4})(\d{2})(\d{2})$", str(x.get("date") or ""))
    return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def candidates(items, *, now, limit=MAX_ITEMS):
    """Radar items → scoop_screen candidates (A first, newest first). Items without a subject or words are skipped."""
    rows = []
    for x in items:
        hint = x.get("check") or {}
        who, terms = subject(hint.get("who")), [str(t) for t in hint.get("terms") or [] if str(t).strip()]
        day = item_day(x) or now.date()
        if not who or not terms:
            continue
        rows.append({"id": str(x["id"]), "tier": x.get("tier"), "watch": x.get("watch"), "company": who, "terms": terms,
                     "alts": {k: list(v) for k, v in (hint.get("alts") or {}).items() if k in terms},
                     "numbers": [], "unit": "", "period": "", "strength": 1 if x.get("tier") == "A" else 0,
                     "title": x.get("fact") or "", "date": str(x.get("date") or ""),
                     "since": (day - dt.timedelta(days=LEAD_DAYS)).isoformat()})
    a = sorted([r for r in rows if r["tier"] == "A"], key=lambda r: r["date"], reverse=True)
    b = sorted([r for r in rows if r["tier"] != "A"], key=lambda r: r["date"], reverse=True)
    return (a + b)[:limit]


def run(items, *, now, previous=None, get=None, sleep=time.sleep):
    cands = candidates(items, now=now)
    rows = ss.screen(cands, now=now, get=get, sleep=sleep)
    stamp = now.isoformat(timespec="seconds")
    prev = {str(r.get("id")): r for r in (previous or {}).get("items", []) if isinstance(r, dict)}
    out = []
    for r in rows:
        old = prev.get(r["id"]) or {}
        out.append({"id": r["id"], "tier": r["tier"], "watch": r["watch"], "who": r["company"], "terms": r["terms"],
                    "since": r["since"], "queries": r["queries"], "verdict": r["verdict"], "evidence": r["evidence"],
                    "channels": r["channels"], "checkedAt": stamp,
                    "firstVerdict": old.get("firstVerdict") or r["verdict"], "firstCheckedAt": old.get("firstCheckedAt") or stamp})
    have = {r["id"] for r in out}
    keep_from = (now - dt.timedelta(days=KEEP_DAYS)).isoformat(timespec="seconds")
    out += [r for i, r in prev.items() if i not in have and str(r.get("checkedAt") or "") >= keep_from]
    counts = {v: sum(1 for r in out if r.get("checkedAt") == stamp and r["verdict"] == v)
              for v in ("미보도 후보", "관련 보도 있음", "같은 수치 선행", "미확인")}
    return {"schema": SCHEMA, "generatedAt": stamp, "hours": HOURS, "leadDays": LEAD_DAYS, "received": len(items),
            "screened": len(rows), "counts": counts, "items": out,
            "rules": ["오늘의 레이더 A·B 항목 중 대조 낱말이 있는 것만(회사·법안 이름 + 사건 낱말). 낱말은 검색어일 뿐 사실이 아니다.",
                      f"항목 날짜 {LEAD_DAYS}일 전 이후 기사만 센다. 미보도 후보는 검색 범위 안에서 못 찾았다는 뜻이고 단독 판정이 아니다.",
                      "관련 보도 있음은 회사명+낱말이 겹친 기사. 같은 사건인지는 열어 봐야 한다. 채널 실패·미설정은 미확인(0건 아님)."]}


def fetch_items(token, *, hours=HOURS, get=None):
    if get is None:
        import requests
        get = requests.get
    r = get(f"{ss.WORKER}/ingest/radar-items", params={"hours": hours}, headers={"Authorization": f"Bearer {token}",
            "User-Agent": "seoul-reporting-radar press-check"}, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}")
    body = r.json()
    if not isinstance(body.get("items"), list):
        raise RuntimeError("형식 오류")
    return body["items"]


def main():
    import private_store
    now = ss.now_kst()
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    if not token:
        sys.exit("MCP_ACCESS_TOKEN 미설정 — 레이더 항목을 받을 수 없음(미확인)")
    previous = None
    try:
        previous = private_store.get("radar-check", token)
    except private_store.StoreError as e:
        print(f"::warning title=radar-check-state::이전 결과 조회 실패({e}) — 처음 판정은 이번 실행 기준")
    if private_store.late_scheduled_duplicate(previous, now):
        return
    try:
        items = fetch_items(token)
    except Exception as e:  # network/HTTP/format: nothing was checked — keep the previous result
        print(f"::error title=radar-check-items::레이더 항목 조회 실패({type(e).__name__}: {str(e)[:60]}) — 이전 결과 유지")
        sys.exit(1)
    doc = run(items, now=now, previous=previous)
    ch = {k: sum(1 for r in doc["items"] if r.get("checkedAt") == doc["generatedAt"] and r["channels"].get(k, {}).get("status") == "ok")
          for k in ("naver", "bing", "google")}
    # Public log: counts only — never companies, titles or queries.
    print(f"::notice title=radar-check::항목 {doc['received']} · 대조 {doc['screened']} · "
          + " · ".join(f"{k} {v}" for k, v in doc["counts"].items())
          + f" · 채널 정상 naver {ch['naver']} bing {ch['bing']} google {ch['google']}")
    if doc["screened"] and not any(ch.values()):
        print("::warning title=radar-check-channels::모든 채널 실패 — 판정은 모두 미확인")
    status = private_store.put("radar-check", doc, token)
    print(f"::notice title=radar-check-push::기자 전용 저장소 전송 HTTP {status}")
    if status != 200:
        sys.exit(1)


if __name__ == "__main__":
    main()
