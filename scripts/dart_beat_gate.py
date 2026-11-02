"""DART 출입처 공시 감시 실행 여부(GitHub Actions 출력 run=true/false).

Cloudflare 워커가 07:45·17:45에 정시 요청하고, 10:45·20:45는 재시도 칸이다. 마지막으로 게시된 결과
(digests/dart_beat_monitor_latest.json)가 FRESH_HOURS 안이면 건너뛴다 — 정시 칸이 성공했으면 재시도 칸과
몇 시간 늦게 도착한 GitHub 예약이 같은 목록을 다시 읽지 않는다. push·강제 실행은 늘 돈다.
11-02: GitHub 예약(07:45)이 10:50에 돌았고 그 실행은 OpenDART 시간 초과로 실패 — 다음 성공은 저녁 예약을 기다려야 했다.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))
SNAPSHOT = Path(__file__).resolve().parent.parent / "digests" / "dart_beat_monitor_latest.json"
FRESH_HOURS = 4.0


def should_run(snapshot, now, *, event="", force=False, fresh_hours=FRESH_HOURS):
    """(run, 이유)."""
    if force or event == "push":
        return True, "push·강제 실행"
    try:
        doc = json.loads(Path(snapshot).read_text(encoding="utf-8"))
        last = datetime.fromisoformat(str(doc.get("generatedAt")))
    except (OSError, ValueError, TypeError):
        return True, "직전 결과를 읽지 못함"
    if last.tzinfo is None:
        last = last.replace(tzinfo=KST)
    age = (now - last).total_seconds() / 3600
    if 0 <= age < fresh_hours:
        return False, f"직전 결과 {age:.1f}시간 전 — 건너뜀(재시도 칸·늦은 예약)"
    return True, f"직전 결과 {age:.1f}시간 전"


def main():
    run, why = should_run(SNAPSHOT, datetime.now(KST), event=os.environ.get("GITHUB_EVENT_NAME", ""),
                          force=os.environ.get("FORCE_RUN", "").lower() in ("1", "true", "yes"))
    print(f"::notice title=dart-beat-gate::{'실행' if run else '건너뜀'} — {why}", file=sys.stderr)
    print(f"run={'true' if run else 'false'}")


if __name__ == "__main__":
    main()
