"""Private feed client: 204 means nothing stored, other errors are never read as empty."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import private_store as ps  # noqa: E402


class R:
    def __init__(self, code, body=None):
        self.status_code, self.body = code, body

    def json(self):
        return self.body


class PrivateStore(unittest.TestCase):
    def test_get_put_and_errors(self):
        seen = {}
        def get(url, headers, timeout):
            seen["url"], seen["auth"] = url, headers["Authorization"]
            return R(204)
        self.assertIsNone(ps.get("page-watch", "tok", get=get))
        self.assertTrue(seen["url"].endswith("/ingest/page-watch"))
        self.assertEqual(seen["auth"], "Bearer tok")
        self.assertEqual(ps.get("us-comments", "t", get=lambda u, headers, timeout: R(200, {"a": 1})), {"a": 1})
        with self.assertRaises(ps.StoreError):
            ps.get("us-comments", "t", get=lambda u, headers, timeout: R(404))
        with self.assertRaises(ValueError):
            ps.get("anything", "t", get=get)
        self.assertEqual(ps.put("partner-filings", {"x": "한글"}, "t", post=lambda u, data, headers, timeout: R(200)), 200)

    def test_whole_connector_url_in_the_secret_still_works(self):
        tok = "FAKEtoken_0123456789abcdefghij-XYZ"  # not a real credential
        self.assertEqual(ps.normalize_token(f"https://example.workers.dev/mcp/{tok}"), tok)
        self.assertEqual(ps.normalize_token(f" {tok}\n"), tok)
        self.assertEqual(ps.normalize_token(f'"{tok}"'), tok)
        seen = {}
        ps.get("page-watch", f"https://example.workers.dev/mcp/{tok}/", get=lambda u, headers, timeout: seen.update(h=headers) or R(204))
        self.assertEqual(seen["h"]["Authorization"], f"Bearer {tok}")



class DeployLag(unittest.TestCase):
    """10-30 kr-stacks: the first push run after merge hit the old Worker (404), a re-run a few minutes later saved."""

    def setUp(self):
        import contextlib
        import io
        self.out = io.StringIO()
        self._ctx = contextlib.redirect_stdout(self.out)
        self._ctx.__enter__()
        self.addCleanup(self._ctx.__exit__, None, None, None)

    def test_put_waits_while_the_token_still_reads_an_old_feed(self):
        posts, waits = [], []
        def post(url, data, headers, timeout):
            posts.append(url)
            return R(404 if len(posts) < 3 else 200)
        def get(url, headers, timeout):
            self.assertTrue(url.endswith("/ingest/page-watch"))
            return R(200, {})
        self.assertEqual(ps.put("kr-stacks", {"a": 1}, "t", post=post, get=get, sleep=waits.append), 200)
        self.assertEqual(len(posts), 3)
        self.assertEqual(waits, [45, 90])
        self.assertIn("store-wait-deploy::kr-stacks", self.out.getvalue())

    def test_wrong_token_fails_at_once(self):
        waits = []
        self.assertEqual(ps.put("kr-stacks", {}, "t", post=lambda u, data, headers, timeout: R(404),
                                get=lambda u, headers, timeout: R(404), sleep=waits.append), 404)
        with self.assertRaises(ps.StoreError) as e:
            ps.get("kr-stacks", "t", get=lambda u, headers, timeout: R(404), sleep=waits.append)
        self.assertIn("토큰 거부 가능성", str(e.exception))
        self.assertEqual(waits, [])

    def test_gives_up_after_the_waits_and_says_why(self):
        waits = []
        def get(url, headers, timeout):
            return R(204) if url.endswith("/page-watch") else R(404)
        with self.assertRaises(ps.StoreError) as e:
            ps.get("kr-stacks", "t", get=get, sleep=waits.append)
        self.assertEqual(waits, list(ps.DEPLOY_WAITS))
        self.assertIn("토큰은 맞음", str(e.exception))
        waits.clear()
        self.assertEqual(ps.put("kr-stacks", {}, "t", post=lambda u, data, headers, timeout: R(404), get=get, sleep=waits.append), 404)
        self.assertEqual(waits, list(ps.DEPLOY_WAITS))

    def test_get_recovers_and_other_errors_do_not_wait(self):
        calls, waits = [], []
        def get(url, headers, timeout):
            calls.append(url)
            if url.endswith("/page-watch"):
                return R(204)
            return R(404) if len([c for c in calls if c.endswith("/kr-stacks")]) == 1 else R(200, {"ok": 1})
        self.assertEqual(ps.get("kr-stacks", "t", get=get, sleep=waits.append), {"ok": 1})
        self.assertEqual(waits, [45])
        waits.clear()
        self.assertEqual(ps.put("kr-stacks", {}, "t", post=lambda u, data, headers, timeout: R(500), sleep=waits.append), 500)
        with self.assertRaises(ps.StoreError):
            ps.get("kr-stacks", "t", get=lambda u, headers, timeout: R(503), sleep=waits.append)
        self.assertEqual(waits, [])



class RelayClient(unittest.TestCase):
    def test_only_allow_listed_hosts(self):
        with self.assertRaises(ValueError):
            ps.relay("https://example.com/", "tok-0123456789abcdef", get=lambda *a, **k: None)

    def test_worker_or_upstream_errors_are_errors(self):
        class R:
            def __init__(self, code, upstream="200", text="ok"):
                self.status_code, self.headers, self.text = code, {"X-Relay-Status": upstream}, text
        self.assertEqual(ps.relay("https://www.dgtr.gov.in/en/x", "t" * 20, get=lambda *a, **k: R(404))[2], "중계 HTTP 404")
        self.assertEqual(ps.relay("https://www.dgtr.gov.in/en/x", "t" * 20, get=lambda *a, **k: R(200, "503"))[2], "원 사이트 HTTP 503(중계)")
        self.assertEqual(ps.relay("https://www.dgtr.gov.in/en/x", "t" * 20, get=lambda *a, **k: R(200))[1], "ok")



class LateSchedule(unittest.TestCase):
    def test_only_late_cron_copies_skip(self):
        import datetime as dt
        kst = dt.timezone(dt.timedelta(hours=9))
        now = dt.datetime(2026, 10, 28, 10, 40, tzinfo=kst)
        prev = {"generatedAt": "2026-10-28T07:42:10+09:00"}  # the on-time Cloudflare-requested run
        # The skip notice is captured: printed in a real run's test step it showed up as a false
        # 'skip-late-schedule' annotation on every collector run (10-29 점검에서 헷갈림).
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertTrue(ps.late_scheduled_duplicate(prev, now, env={"GITHUB_EVENT_NAME": "schedule"}))
        self.assertIn("title=skip-late-schedule::직전 결과가 3.0시간 전", buf.getvalue())
        self.assertFalse(ps.late_scheduled_duplicate(prev, now, env={"GITHUB_EVENT_NAME": "workflow_dispatch"}))
        self.assertFalse(ps.late_scheduled_duplicate(prev, now, env={"GITHUB_EVENT_NAME": "push"}))
        old = {"generatedAt": "2026-10-27T07:42:10+09:00"}  # Cloudflare request failed: yesterday's result
        self.assertFalse(ps.late_scheduled_duplicate(old, now, env={"GITHUB_EVENT_NAME": "schedule"}))
        self.assertFalse(ps.late_scheduled_duplicate(None, now, env={"GITHUB_EVENT_NAME": "schedule"}))
        self.assertFalse(ps.late_scheduled_duplicate({"generatedAt": "bad"}, now, env={"GITHUB_EVENT_NAME": "schedule"}))

    def test_quota_watch_skips_a_second_run_the_same_morning_unless_forced(self):
        import contextlib
        import datetime as dt
        import io
        kst = dt.timezone(dt.timedelta(hours=9))
        now = dt.datetime(2026, 11, 2, 7, 40, tzinfo=kst)
        prev = {"generatedAt": "2026-11-02T07:12:00+09:00"}   # 월 07:10 Cloudflare 요청 실행 — 뒤이어 온 GitHub 예약·요청은 건너뜀
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(ps.recent_duplicate(prev, now, env={"GITHUB_EVENT_NAME": "workflow_dispatch"}))
        self.assertFalse(ps.recent_duplicate(prev, now, env={"GITHUB_EVENT_NAME": "workflow_dispatch", "FORCE_RUN": "true"}))
        self.assertFalse(ps.recent_duplicate({"generatedAt": "2026-10-26T07:12:00+09:00"}, now, env={}))   # 지난주 결과
        self.assertFalse(ps.recent_duplicate(None, now, env={}))


if __name__ == "__main__":
    unittest.main()
