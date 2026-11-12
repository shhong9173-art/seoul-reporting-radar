import datetime as dt
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import google_news_relay as g  # noqa: E402

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 11, 12, 6, 10, tzinfo=UTC)


def ask(qid, q, minutes_ago, days=30):
    return {"qid": qid, "q": q, "days": days, "askedAt": (NOW - dt.timedelta(minutes=minutes_ago)).isoformat()}


class Relay(unittest.TestCase):
    def test_runs_fresh_queries_and_keeps_worker_shape(self):
        urls = []

        def fetch(url):
            urls.append(url)
            return {"status": "ok", "items": [{"title": "LG화학, 2-EHA 반덤핑 - 아이뉴스24", "url": "https://n/1", "date": "2026-11-06"},
                                              {"title": "제목에 매체 없음", "url": "https://n/2", "date": "2026-11-05"}]}

        pending = {"pending": [ask("a", "LG화학 2-EHA", 1), ask("b", "오래된 낱말", 45), ask("c", "", 1)]}
        doc, asked, ok, stopped = g.run(pending, None, NOW, fetch=fetch, sleep=lambda s: None)
        self.assertEqual((asked, ok, stopped), (1, 1, None))                     # 30분 넘은 요청·빈 낱말은 안 함
        self.assertIn("when%3A30d", urls[0])
        r = doc["results"][0]
        self.assertEqual((r["qid"], r["status"], r["returned"]), ("a", "ok", 2))
        self.assertEqual(r["items"][0], {"title": "LG화학, 2-EHA 반덤핑", "url": "https://n/1", "date": "2026-11-06", "source": "아이뉴스24"})
        self.assertEqual(r["items"][1]["source"], "")
        # 이미 받은 요청(결과가 요청보다 나중)은 다시 안 함
        doc2, asked2, _, _ = g.run(pending, doc, NOW + dt.timedelta(minutes=1), fetch=fetch, sleep=lambda s: None)
        self.assertEqual(asked2, 0)
        self.assertEqual(len(doc2["results"]), 1)

    def test_stops_when_google_blocks_here_too(self):
        calls = []

        def fetch(url):
            calls.append(url)
            return {"status": "failed", "error": "HTTP 503", "items": []}

        pending = {"pending": [ask("a", "낱말 하나", 1), ask("b", "낱말 둘", 1)]}
        doc, asked, ok, stopped = g.run(pending, None, NOW, fetch=fetch, sleep=lambda s: None)
        self.assertEqual((asked, ok, stopped, len(calls)), (1, 0, "HTTP 503", 1))
        self.assertEqual(doc["results"][0]["status"], "failed")

    def test_old_results_are_dropped(self):
        old = {"results": [{"qid": "z", "fetchedAt": (NOW - dt.timedelta(hours=30)).isoformat(), "status": "ok", "items": []},
                           {"qid": "y", "fetchedAt": (NOW - dt.timedelta(hours=2)).isoformat(), "status": "ok", "items": []}]}
        doc, *_ = g.run({"pending": []}, old, NOW, fetch=lambda u: {"status": "ok", "items": []}, sleep=lambda s: None)
        self.assertEqual([r["qid"] for r in doc["results"]], ["y"])


if __name__ == "__main__":
    unittest.main()
