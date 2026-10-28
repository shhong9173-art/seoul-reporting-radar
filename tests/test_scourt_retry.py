"""Supreme Court releases: a dropped connection is retried once before the page counts as failed."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pre_scoop_radar as psr  # noqa: E402

PAGE = """<table><tr><td><a href="/supreme/news/NewsViewAction.work?seqnum=1">현대제철 하도급 손해배상 사건 판결 선고</a></td>
<td>{day}</td></tr></table>"""


DETAIL_PAGE = """<table><tr><td><a href="/portal/news/NewsViewAction.work?seqnum=2">경매 임차인 통지서 전면 개선 안내</a></td>
<td>{day}</td></tr></table>"""


class Retry(unittest.TestCase):
    def run_with(self, outcomes, page=PAGE):
        calls = []
        day = psr.datetime.now(psr.KST).strftime("%Y-%m-%d")

        def fake_get(url, timeout=8):
            calls.append((url, timeout))
            o = outcomes.pop(0) if outcomes else "ok"
            if o == "fail":
                raise TimeoutError("timed out")
            return page.format(day=day).encode()
        with patch.object(psr, "get", fake_get), patch.object(psr.time, "sleep", lambda s: None):
            psr.fetch_direct_court(max_items=1)
        return psr.DIRECT_DIAGNOSTICS["scourt-case-releases"], calls

    def test_one_failure_is_retried_with_a_longer_timeout(self):
        diag, calls = self.run_with(["fail", "ok"])
        self.assertEqual(diag["pagesFetched"], 1)
        self.assertEqual(diag["retriedOk"], 1)
        self.assertEqual(diag["errors"], [])
        self.assertEqual([t for _, t in calls[:2]], [10, 20])

    def test_two_failures_are_reported(self):
        diag, _ = self.run_with(["fail", "fail", "fail", "fail"])
        self.assertEqual(diag["pagesFetched"], 0)
        self.assertEqual(len(diag["errors"]), 2)
        self.assertIn("TimeoutError", diag["errors"][0])

    def test_detail_page_reset_is_retried(self):
        # 목록(성공) → 본문 1차 끊김 → 본문 2차 성공. 목록 두 번째 쪽은 그다음.
        diag, calls = self.run_with(["ok", "fail", "ok"], page=DETAIL_PAGE)
        self.assertEqual(diag["detailPagesAttempted"], 1)
        self.assertEqual(diag["detailPagesFetched"], 1)
        self.assertEqual(diag["retriedOk"], 1)
        self.assertEqual(diag["errors"], [])
        self.assertEqual([t for _, t in calls[1:3]], [8, 15])

    def test_detail_page_two_failures_are_reported(self):
        diag, _ = self.run_with(["ok", "fail", "fail"], page=DETAIL_PAGE)
        self.assertEqual(diag["detailPagesFetched"], 0)
        self.assertEqual(len(diag["errors"]), 1)
        self.assertTrue(diag["errors"][0].startswith("detail "))


if __name__ == "__main__":
    unittest.main()
