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
    def __init__(self, code=200, text="", body=None, url=None):
        self.status_code, self.text, self.body = code, text, body
        if url:
            self.url = url

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

    def test_site_wide_menu_lines_are_separated_from_page_lines(self):
        nav_old = "<nav>IONIQ 6 N Coming 2026</nav>"
        nav_new = "<nav>IONIQ 6 N Coming 2027</nav>"
        def page(nav, body):
            return f"<html><body>{nav}<p>{body}</p>{PAD}</body></html>"
        pages = [dict(PAGE, id="a", url="https://www.hyundaiusa.com/us/en/vehicles/ioniq-5-n"),
                 dict(PAGE, id="b", url="https://www.hyundaiusa.com/us/en/vehicles/ioniq-9"),
                 dict(PAGE, id="c", url="https://www.hyundaiusa.com/us/en/vehicles/palisade")]
        first = w.run(pages, now=NOW, previous={"pages": [dict(p, status="ok", signals={"timing": ["Coming 2026"]}, lastOk="2026-10-20") for p in pages]},
                      get=lambda url, **k: R(text=page(nav_new, "Starting at $59,900" if "ioniq-5-n" in url else "")), sleep=lambda s: None)
        # transition from records that still had menu lines: the menu change is one site event, not three page events
        site_ev = [e for e in first["events"] if e["scope"] == "site"]
        page_ev = [e for e in first["events"] if e["scope"] == "page"]
        self.assertEqual(len(site_ev), 1)
        self.assertEqual(site_ev[0]["removed"]["timing"], ["Coming 2026"])
        self.assertEqual([e["pageId"] for e in page_ev], ["a"])  # only the real page change (new price line)
        self.assertEqual(list(page_ev[0]["added"]), ["price"])
        self.assertNotIn("timing", page_ev[0].get("removed", {}))
        site = first["sites"]["hyundaiusa.com"]["signals"]
        self.assertIn("Coming 2027", site["timing"])
        a = next(p for p in first["pages"] if p["id"] == "a")
        self.assertTrue(a["specific"])
        self.assertNotIn("Coming 2027", a["signals"]["timing"])
        self.assertIn("Starting at $59,900", a["signals"]["price"])
        second = w.run(pages, now=NOW + dt.timedelta(days=1), previous=first,
                       get=lambda url, **k: R(text=page("<nav>IONIQ 6 N Coming Spring 2028</nav>", "Starting at $59,900" if "ioniq-5-n" in url else "")),
                       sleep=lambda s: None)
        new = [e for e in second["events"] if e["detectedAt"].startswith("2026-10-28")]
        self.assertEqual([e["scope"] for e in new], ["site"])
        self.assertIn("Coming Spring 2028", new[0]["added"]["timing"])

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


class Redirects(unittest.TestCase):
    """10-31 확인: kia.com/us/en/ev4 → 301 → 기아 미국 홈페이지. 그동안 'EV4' 이름으로 홈페이지 K4 가격을 비교했다."""
    EV4 = {"id": "kia-us-ev4", "company": "기아", "label": "기아 미국 EV4", "url": "https://www.kia.com/us/en/ev4", "kind": "model"}
    HOME = f"<html><head><title>Kia America</title></head><body><p>2027 K4 STARTING AT $22,390</p>{PAD}</body></html>"

    def home(self, url, **k):
        return R(text=self.HOME, url="https://www.kia.com/us/en")

    def test_same_page_ignores_scheme_www_slash_and_query(self):
        self.assertTrue(w.same_page("https://www.kia.com/us/en/ev9", "https://kia.com/us/en/ev9/?cid=x"))
        self.assertFalse(w.same_page("https://www.kia.com/us/en/ev4", "https://www.kia.com/us/en"))

    def test_first_sight_of_a_redirect_is_recorded_without_events_or_wayback(self):
        calls = []
        doc = w.run([self.EV4], now=NOW, get=lambda url, **k: calls.append(url) or self.home(url), sleep=lambda s: None)
        page = doc["pages"][0]
        self.assertEqual((page["status"], page["finalUrl"], page["signals"]), ("redirected", "https://www.kia.com/us/en", {}))
        self.assertEqual((doc["events"], doc["status"], calls), ([], "complete", [self.EV4["url"]]))  # 넘어감은 실패가 아니다

    def test_legacy_record_marks_earlier_changes_as_the_target_pages(self):
        prev = {"pages": [{**self.EV4, "status": "ok", "signals": {"price": ["STARTING AT $ 22,390"]}, "lastOk": "2026-10-28T06:31:00+09:00"}],
                "events": [{"pageId": "kia-us-ev4", "scope": "page", "detectedAt": "2026-10-28T06:31:00+09:00", "added": {"price": ["STARTING AT $ 22,390"]}}]}
        doc = w.run([self.EV4], now=NOW, previous=prev, get=self.home, sleep=lambda s: None)
        self.assertEqual(len(doc["events"]), 1)  # 새 '넘어감' 이벤트는 없다(언제 넘어갔는지 모름)
        self.assertIn("이 주소는 https://www.kia.com/us/en(으)로 넘어가 있어 이 문구는 그 페이지 것이다", doc["events"][0]["redirectNote"])

    def test_known_page_moving_away_and_a_redirect_opening_are_events(self):
        prev = {"pages": [{**PAGE, "status": "ok", "finalUrl": PAGE["url"], "signals": w.signals(w.visible_text(NEW)), "lastOk": "2026-10-26T06:00:00+09:00"}]}
        doc = w.run([PAGE], now=NOW, previous=prev, get=lambda url, **k: R(text=self.HOME, url="https://www.hyundaiusa.com/us/en/vehicles"),
                    sleep=lambda s: None)
        ev = doc["events"][0]
        self.assertEqual((ev["kind"], ev["movedTo"]), ("moved", "https://www.hyundaiusa.com/us/en/vehicles"))
        self.assertIn("Coming Spring 2027", " ".join(ev["removed"]["timing"]))
        # 넘어가던 주소가 제 페이지로 열림 → '열림' 이벤트(지금 문구 전체), 웹 아카이브는 부르지 않는다
        calls = []
        opened = w.run([PAGE], now=NOW + dt.timedelta(days=1), previous=doc,
                       get=lambda url, **k: calls.append(url) or R(text=NEW, url=PAGE["url"]), sleep=lambda s: None)
        e = [x for x in opened["events"] if x.get("kind") == "opened"][0]
        self.assertEqual(e["openedFrom"], "https://www.hyundaiusa.com/us/en/vehicles")
        self.assertIn("Coming Spring 2027", " ".join(e["added"]["timing"]))
        self.assertEqual(calls, [PAGE["url"]])
        self.assertEqual(opened["pages"][0]["status"], "ok")


if __name__ == "__main__":
    unittest.main()
