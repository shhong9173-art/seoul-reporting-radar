"""An unpopular, widely reported or low-score article MUST be kept for scoops."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.press_coverage_index import (
    STATUS, merge_index, update_from_news)

KST=timezone(timedelta(hours=9))
NOW=datetime(2026,10,18,22,0,tzinfo=KST)


def article(title="현대차 이미 보도된 신차", *,
            at="2026-10-18T09:00:00+09:00",
            source="경제신문", score=12,
            url="https://example.com/article/1",
            global_feed=False):
    return {
        "title":title,"published":at,"sourceName":source,
        "url":url, "global":global_feed,"companies":["현대차"],
        "summary":"기보도 현대차 계획 관련 100억원",
        "pitchScore":score,"clusterCount":18,"exclusive":False
    }


class UnfilteredPriorCoverage(unittest.TestCase):
    def test_widely_reported_low_score_is_retained(self):
        press=[
            article(),
            article("현대차 기보도 반복",url="https://example.com/article/2",score=0),
            article("국내 단독 보도",url="https://example.com/article/3",score=25),
            article("Overseas item",url="https://example.com/article/4",
                    global_feed=True)]
        result=merge_index(None,press,now=NOW)
        self.assertEqual(result["itemCount"],3)
        self.assertEqual(result["newlyIndexedArticleCount"],3)
        self.assertFalse(result["proofOfNoPriorCoverage"])
        self.assertTrue(result["firstRunBaseline"])
        self.assertEqual(result["retentionDays"],365)
        self.assertNotIn("pitchScore",result["items"][0])
        self.assertTrue(all(x["fulltextReviewed"] is False for x in result["items"]))

    def test_new_score_change_does_not_erase_same_article(self):
        first=merge_index(None,[article()],now=NOW)
        second=merge_index(first,[article(score=95)],now=NOW)
        self.assertEqual(second["itemCount"],1)
        self.assertEqual(second["newlyIndexedArticleCount"],0)
        self.assertFalse(second["firstRunBaseline"])

    def test_stores_365_days_not_only_90(self):
        old=(NOW-timedelta(days=180)).isoformat()
        stale=(NOW-timedelta(days=367)).isoformat()
        today=article(at=old)
        result=merge_index(None,[today],now=NOW)
        self.assertEqual(result["itemCount"],1)
        rerun=merge_index(result,[article("stale",at=stale,url="https://example.com/old")],
                          now=NOW+timedelta(days=1))
        self.assertEqual(rerun["itemCount"],1)

    def test_undated_and_bad_published_must_not_become_now(self):
        bad=article(at="unknown")
        missing=article(at="")
        out=merge_index(None,[bad,missing,article()],now=NOW)
        self.assertEqual(out["malformedOrUndatedInputCount"],2)
        self.assertEqual(out["itemCount"],1)

    def test_corrupt_history_is_not_silently_zeroed(self):
        with self.assertRaises(ValueError):
            merge_index({"status":"bad","items":[article()]},[],now=NOW)
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/"index.json"
            target.write_text('{"status": "unexpected"}',encoding="utf-8")
            before=target.read_text()
            with self.assertRaises(ValueError):
                update_from_news([article()],path=target,now=NOW)
            self.assertEqual(target.read_text(),before)

    def test_persisted_compact_index_is_reloaded_and_unique(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/"coverage.json"
            first=update_from_news([article()],path=target,now=NOW)
            second=update_from_news([article()],path=target,now=NOW)
            read=json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(first["itemCount"],second["itemCount"])
            self.assertEqual(read["status"],STATUS)
            self.assertEqual(read["itemCount"],1)
            self.assertIn("numbers",read["items"][0])
            self.assertNotIn("summary",read["items"][0])
            self.assertIn("sourceName",read["items"][0])
            self.assertEqual(read["items"][0]["companies"],["현대차"])

    def test_empty_feed_not_negative_proof(self):
        out=merge_index(None,[],now=NOW)
        self.assertEqual(out["itemCount"],0)
        self.assertFalse(out["proofOfNoPriorCoverage"])
        self.assertTrue(out["firstRunBaseline"])


if __name__=="__main__":
    unittest.main()
