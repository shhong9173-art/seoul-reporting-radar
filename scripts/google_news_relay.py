"""구글 뉴스 GitHub 경유 조회(11-12): 구글은 Cloudflare Worker 접속에 HTTP 503을 주지만 GitHub Actions에는 정상이다.

Worker의 즉석 보도 대조(news_check)가 구글에 막히면 낱말을 기자 전용 저장소(google-relay-pending)에 맡기고 이 작업을 부른다.
여기서는 맡겨진 낱말을 구글 뉴스 RSS로 조회해 결과를 기자 전용 저장소(google-relay)에 둔다 — 1~2분 뒤 news_check가 그 결과를 쓴다.

지킬 것
- 낱말·기사 제목은 로그에 찍지 않는다(공개 저장소 — 기자가 무엇을 확인 중인지 드러나면 안 된다). 로그엔 건수만.
- 한 실행에 MAX_QUERIES개, 요청 사이 PAUSE초. 구글이 여기서도 막으면(503·429) 그 자리에서 멈추고 남은 낱말은 다음 요청에.
- 결과는 RESULT_KEEP개까지 최근 것만, KEEP_HOURS 지난 것은 지운다.
"""
from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))

import private_store  # noqa: E402
import scoop_screen  # noqa: E402

KST = timezone(timedelta(hours=9))
MAX_QUERIES = 10
PAUSE = 1.5
ASK_WINDOW_MIN = 30
RESULT_KEEP = 200
KEEP_HOURS = 24
ITEM_KEEP = 40


def google_url(q, days):
    return f"https://news.google.com/rss/search?q={quote(q + f' when:{int(days)}d')}&hl=ko&gl=KR&ceid=KR:ko"


def item_of(x):
    """구글 RSS 제목은 '기사 제목 - 매체'. Worker news_check 꼴 {title, url, date, source}."""
    title = x.get("title") or ""
    head, sep, src = title.rpartition(" - ")
    return {"title": head if sep else title, "url": x.get("url"), "date": x.get("date"), "source": src if sep else ""}


def run(pending_doc, results_doc, now, *, fetch=None, sleep=time.sleep):
    """(새 결과 문서, 조회 수, 정상 수, 멈춘 이유|None)."""
    fetch = fetch or (lambda url: scoop_screen.rss(url))
    old = {r["qid"]: r for r in (results_doc or {}).get("results") or [] if r.get("qid")}
    since = now - timedelta(minutes=ASK_WINDOW_MIN)
    todo = []
    for p in (pending_doc or {}).get("pending") or []:
        try:
            asked = datetime.fromisoformat(str(p.get("askedAt")).replace("Z", "+00:00"))
        except ValueError:
            continue
        got = old.get(p.get("qid"))
        if asked < since or not p.get("q") or (got and got.get("fetchedAt", "") >= p["askedAt"]):
            continue
        todo.append(p)
    asked_n, ok_n, stopped = 0, 0, None
    for p in todo[:MAX_QUERIES]:
        if asked_n:
            sleep(PAUSE)
        asked_n += 1
        res = fetch(google_url(str(p["q"]), int(p.get("days") or 365)))
        at = datetime.now(timezone.utc).isoformat(timespec="seconds") if now is None else now.astimezone(timezone.utc).isoformat(timespec="seconds")
        rec = {"qid": p["qid"], "q": p["q"], "days": p.get("days"), "fetchedAt": at, "status": res.get("status"),
               "error": res.get("error") or "", "returned": len(res.get("items") or []),
               "items": [item_of(x) for x in (res.get("items") or [])[:ITEM_KEEP]]}
        old[p["qid"]] = rec
        if res.get("status") == "ok":
            ok_n += 1
        elif any(code in (res.get("error") or "") for code in ("HTTP 503", "HTTP 429")):
            stopped = res.get("error")
            break
    cut = (now - timedelta(hours=KEEP_HOURS)).astimezone(timezone.utc).isoformat(timespec="seconds")
    keep = sorted((r for r in old.values() if str(r.get("fetchedAt")) >= cut), key=lambda r: r["fetchedAt"], reverse=True)[:RESULT_KEEP]
    doc = {"schema": "google_relay/v1", "generatedAt": now.astimezone(timezone.utc).isoformat(timespec="seconds"), "results": keep}
    return doc, asked_n, ok_n, stopped


def main():
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    if not token:
        print("::error title=google-relay::MCP_ACCESS_TOKEN 없음 — 조회 안 함")
        sys.exit(1)
    now = datetime.now(timezone.utc)
    pending = private_store.get("google-relay-pending", token)
    results = private_store.get("google-relay", token)
    doc, asked, ok, stopped = run(pending, results, now)
    # 공개 로그: 건수만(낱말·제목 없음)
    print(f"::notice title=google-relay::구글 조회 {asked}건 · 정상 {ok} · 저장 결과 {len(doc['results'])}"
          + (f" · 구글이 여기서도 막음({stopped}) — 남은 낱말은 다음 요청에" if stopped else ""))
    if not asked:
        return
    status = private_store.put("google-relay", doc, token)
    print(f"::notice title=google-relay-push::기자 전용 저장소 전송 HTTP {status}")
    if status != 200:
        sys.exit(1)


if __name__ == "__main__":
    main()
