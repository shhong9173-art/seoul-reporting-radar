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


if __name__ == "__main__":
    unittest.main()
