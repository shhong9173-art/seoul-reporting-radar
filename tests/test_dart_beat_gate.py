import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import dart_beat_gate as g  # noqa: E402

KST = timezone(timedelta(hours=9))


class Gate(unittest.TestCase):
    def snap(self, folder, at):
        p = Path(folder) / "s.json"
        p.write_text(json.dumps({"generatedAt": at}), encoding="utf-8")
        return p

    def test_retry_slot_after_good_run_and_late_cron_are_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.snap(d, "2026-11-02T07:46:10+09:00")
            self.assertFalse(g.should_run(p, datetime(2026, 11, 2, 10, 45, tzinfo=KST), event="workflow_dispatch")[0])
            self.assertFalse(g.should_run(p, datetime(2026, 11, 2, 10, 50, tzinfo=KST), event="schedule")[0])
            self.assertTrue(g.should_run(p, datetime(2026, 11, 2, 17, 45, tzinfo=KST), event="workflow_dispatch")[0])

    def test_failed_morning_is_retried_and_push_force_always_run(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.snap(d, "2026-11-02T00:31:03+09:00")   # 11-02 아침 실패 뒤 남은 마지막 결과
            run, why = g.should_run(p, datetime(2026, 11, 2, 10, 45, tzinfo=KST), event="workflow_dispatch")
            self.assertTrue(run)
            self.assertIn("10.2시간", why)
            fresh = self.snap(d, "2026-11-02T10:00:00+09:00")
            self.assertTrue(g.should_run(fresh, datetime(2026, 11, 2, 10, 5, tzinfo=KST), event="push")[0])
            self.assertTrue(g.should_run(fresh, datetime(2026, 11, 2, 10, 5, tzinfo=KST), force=True)[0])
            self.assertTrue(g.should_run(Path(d) / "none.json", datetime(2026, 11, 2, 10, 5, tzinfo=KST))[0])

    def test_late_night_cron_does_not_take_the_morning_slot(self):
        # 11-03: 전날 저녁 예약이 03:49에 늦게 돌아, 07:40 정시 칸이 '3.8시간 전'으로 건너뛰어졌다
        with tempfile.TemporaryDirectory() as d:
            p = self.snap(d, "2026-11-03T03:49:40+09:00")
            run, why = g.should_run(p, datetime(2026, 11, 3, 7, 40, tzinfo=KST), event="workflow_dispatch")
            self.assertTrue(run)
            self.assertIn("정시 칸", why)
            # 그 아침 칸이 성공하면 10:40 재시도 칸은 건너뜀, 아침 칸이 실패했으면(새벽 결과만 남음) 재시도
            ok = self.snap(d, "2026-11-03T07:41:20+09:00")
            self.assertFalse(g.should_run(ok, datetime(2026, 11, 3, 10, 40, tzinfo=KST), event="workflow_dispatch")[0])
            night = self.snap(d, "2026-11-03T03:49:40+09:00")
            self.assertTrue(g.should_run(night, datetime(2026, 11, 3, 10, 40, tzinfo=KST), event="workflow_dispatch")[0])
            # 정시 칸이라도 방금(1시간 안) 돈 결과가 있으면 건너뜀(수동 실행 직후 등)
            just = self.snap(d, "2026-11-03T07:10:00+09:00")
            self.assertFalse(g.should_run(just, datetime(2026, 11, 3, 7, 40, tzinfo=KST), event="workflow_dispatch")[0])
            # 늦은 GitHub 예약은 4시간 안이면 건너뜀(그대로)
            self.assertFalse(g.should_run(ok, datetime(2026, 11, 3, 10, 50, tzinfo=KST), event="schedule")[0])


if __name__ == "__main__":
    unittest.main()
