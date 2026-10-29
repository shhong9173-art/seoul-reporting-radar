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


if __name__ == "__main__":
    unittest.main()
