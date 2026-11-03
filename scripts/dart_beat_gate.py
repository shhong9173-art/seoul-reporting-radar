"""DART 출입처 공시 감시 실행 여부(GitHub Actions 출력 run=true/false).

Cloudflare 워커가 07:40·17:40에 정시 요청하고, 10:40·20:40은 재시도 칸이다. 마지막으로 게시된 결과
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
# Cloudflare 칸: 정시(07:40·17:40)와 재시도(10:40·20:40). 정시 칸은 직전 결과가 MAIN_FRESH_HOURS 안일 때만 건너뛰고,
# 재시도 칸은 그날 정시 칸(정시 30분 전부터) 결과가 있으면 건너뛴다.
# 11-03: 전날 저녁(11:45 UTC) GitHub 예약이 7시간 늦게 03:49에 돌았고, 07:40 정시 칸이 '직전 결과 3.8시간 전'으로 건너뛰어졌다
# — 아침 출근 전 확인이 새벽 결과로 남았다.
MAIN_SLOTS = {7: 7, 17: 17}      # 칸 시각(시) → 정시 칸 시각
RETRY_SLOTS = {10: 7, 20: 17}    # 재시도 칸 → 그 칸이 기다리는 정시 칸
MAIN_FRESH_HOURS = 1.0


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
    now_k = now.astimezone(KST)
    age = (now - last).total_seconds() / 3600
    if event == "workflow_dispatch" and now_k.hour in RETRY_SLOTS:
        main_from = now_k.replace(hour=RETRY_SLOTS[now_k.hour], minute=10, second=0, microsecond=0)
        if last >= main_from:
            return False, f"오늘 {RETRY_SLOTS[now_k.hour]:02d}:40 칸 결과({last.astimezone(KST):%H:%M}) 있음 — 재시도 칸 건너뜀"
        return True, f"오늘 {RETRY_SLOTS[now_k.hour]:02d}:40 칸 결과 없음(직전 {age:.1f}시간 전) — 재시도"
    if event == "workflow_dispatch" and now_k.hour in MAIN_SLOTS:
        if 0 <= age < MAIN_FRESH_HOURS:
            return False, f"직전 결과 {age:.1f}시간 전 — 정시 칸이지만 방금 돈 결과가 있음"
        return True, f"정시 칸(직전 결과 {age:.1f}시간 전)"
    if 0 <= age < fresh_hours:
        return False, f"직전 결과 {age:.1f}시간 전 — 건너뜀(늦은 예약)"
    return True, f"직전 결과 {age:.1f}시간 전"


def main():
    run, why = should_run(SNAPSHOT, datetime.now(KST), event=os.environ.get("GITHUB_EVENT_NAME", ""),
                          force=os.environ.get("FORCE_RUN", "").lower() in ("1", "true", "yes"))
    print(f"::notice title=dart-beat-gate::{'실행' if run else '건너뜀'} — {why}", file=sys.stderr)
    print(f"run={'true' if run else 'false'}")


if __name__ == "__main__":
    main()
