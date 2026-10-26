"""Official page watch: signal extraction, diff vs previous, Wayback baseline on first sight, failures not 'unchanged'."""
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import page_watch as w  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 10, 27, 6, 0, tzinfo=KST)
PAD = "<p>" + "filler text " * 300 + "</p>"
OLD = f"<html><head><title>2026 IONIQ 6 N | Hyundai</title></head><body><h1>2026 IONIQ 6 N</h1><p>Coming 2026. Get updates.</p>{PAD}</body></html>"
NEW = (f"<html><head><title>2027 IONIQ 6 N | Hyundai</title><script>var x='Coming Spring 2020';</script></head><body><h1>2027 IONIQ 6 N</h1>"
       f"<p>Coming Spring 2027, extremely limited availability.</p><p>Starting MSRP $65,000</p>{PAD}</body></html>")
PAGE = {"id": "hyundai-us-ioniq-6-n", "company": "현대차", "label": "현대차 미국 아이오닉6 N", "url": "https://www.hyundaiusa.com/us/en/vehicles/ioniq-6-n", "kind": "model"}


class R:
    def __init__(self, code=200, text="", body=None):
        self.status_code, self.text, self.body = code, text, body

    def json(self):
        return self.body


class Signals(unittest.TestCase):
    def test_extracts_timing_limited_price_models_and_ignores_scripts(self):
        s = w.signals(w.visible_text(NEW))
        self.assertIn("Coming Spring 2027", s["timing"])
        self.assertNotIn("Coming Spring 2020", " ".join(s["timing"]))
        self.assertIn("extremely limited availability", s["limited"])
        self.assertIn("Starting MSRP $65,000", s["price"])
        self.assertIn("2027 IONIQ 6 N", s["models"])

    def test_diff(self):
        added, removed = w.diff(w.signals(w.visible_text(OLD)), w.signals(w.visible_text(NEW)))
        self.assertIn("Coming Spring 2027", added["timing"])
        self.assertIn("Coming 2026", removed["timing"])
        self.assertIn("Get updates", removed["status"])


class Run(unittest.TestCase):
    def test_first_sight_uses_wayback_baseline(self):
        def get(url, params=None, headers=None, timeout=None, allow_redirects=True):
            if "archive.org/wayback/available" in url:
                self.assertEqual(params["timestamp"], "20260912")
                return R(body={"archived_snapshots": {"closest": {"available": True, "status": "200", "timestamp": "20260910083000"}}})
            if url.startswith("https://web.archive.org/web/20260910083000id_/"):
                return R(text=OLD)
            return R(text=NEW)
        doc = w.run([PAGE], now=NOW, get=get, sleep=lambda s: None)
        ev = doc["events"][0]
        self.assertEqual(ev["baselineSource"], "웹 아카이브 사본")
        self.assertEqual(ev["baselineDate"], "2026-09-10")
        self.assertIn("Coming Spring 2027", ev["added"]["timing"])
        self.assertEqual(doc["pages"][0]["baseline"]["date"], "2026-09-10")

    def test_previous_state_is_the_baseline_and_no_change_means_no_event(self):
        prev_sig = w.signals(w.visible_text(NEW))
        prev = {"pages": [{**PAGE, "status": "ok", "signals": prev_sig, "lastOk": "2026-10-26T06:00:00+09:00"}],
                "events": [{"pageId": "x", "detectedAt": "2026-10-20T06:00:00+09:00"}, {"pageId": "old", "detectedAt": "2026-06-01T06:00:00+09:00"}]}
        doc = w.run([PAGE], now=NOW, previous=prev, get=lambda url, **k: R(text=NEW), sleep=lambda s: None)
        self.assertEqual([e["pageId"] for e in doc["events"]], ["x"])  # 90-day retention, nothing new
        changed = w.run([PAGE], now=NOW, previous={"pages": [{**PAGE, "status": "ok", "signals": w.signals(w.visible_text(OLD)),
                                                             "lastOk": "2026-10-26T06:00:00+09:00"}]},
                        get=lambda url, **k: R(text=NEW), sleep=lambda s: None)
        self.assertEqual(changed["events"][0]["baselineSource"], "직전 확인")
        self.assertEqual(changed["events"][0]["baselineDate"], "2026-10-26")

    def test_blocked_page_is_failed_and_keeps_old_signals(self):
        prev = {"pages": [{**PAGE, "status": "ok", "signals": {"timing": ["Coming 2026"]}, "lastOk": "2026-10-26T06:00:00+09:00"}]}
        doc = w.run([PAGE], now=NOW, previous=prev, get=lambda url, **k: R(403, text="Access Denied"), sleep=lambda s: None)
        page = doc["pages"][0]
        self.assertEqual(page["status"], "failed")
        self.assertEqual(page["error"], "HTTP 403")
        self.assertEqual(page["signals"], {"timing": ["Coming 2026"]})
        self.assertEqual(doc["events"], [])
        self.assertEqual(doc["status"], "partial")
        short = w.fetch("u", get=lambda url, **k: R(200, text="<html>Access Denied</html>"))
        self.assertEqual(short["status"], "failed")


if __name__ == "__main__":
    unittest.main()
