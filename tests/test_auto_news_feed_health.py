import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.auto_news_feed_health import build,persist

NOW=datetime(2026,10,16,17,10,tzinfo=timezone(timedelta(hours=9)))

def row(status,category="완성차",global_feed=False,error=None,count=0):
    return {"category":category,"globalFeed":global_feed,"status":status,
            "recentRows":count,"errorType":error}

class FeedHealth(unittest.TestCase):
    def test_all_rss_failed_does_not_claim_zero_news(self):
        rows=[row("transport_or_xml_error",error="TimeoutError") for _ in range(19)]
        result=build(rows,expected=19,news_items=0,now=NOW)
        self.assertEqual(result["errorQueries"],19)
        self.assertEqual(result["status"],"incomplete_queries_or_provider_errors")
        self.assertFalse(result["newsDatasetApprovedForPublish"])
        self.assertFalse(result["zeroFetchedMeansZeroPublishedStories"])
        self.assertTrue(result["unknownOfficialNewsCoverage"])

    def test_no_recent_articles_is_not_transport_failure(self):
        rows=[row("checked_no_recent_rows") for _ in range(19)]
        report=build(rows,expected=19,news_items=0,now=NOW)
        self.assertEqual(report["status"],"checked_but_insufficient_recent_news")
        self.assertEqual(report["errorQueries"],0)
        self.assertFalse(report["newsDatasetApprovedForPublish"])
        self.assertFalse(report["zeroFetchedMeansZeroPublishedStories"])

    def test_successful_diagnostics_and_atomic_saved_json(self):
        rows=[row("checked_recent_rows",count=5) for _ in range(11)]+[
             row("checked_no_recent_rows",category="글로벌",global_feed=True) for _ in range(8)]
        report=build(rows,expected=19,news_items=24,now=NOW)
        self.assertEqual(report["status"],"source_requests_completed")
        self.assertTrue(report["newsDatasetApprovedForPublish"])
        with tempfile.TemporaryDirectory() as root:
            file=Path(root)/"digests"/"feed_latest.json"
            persist(report,file)
            parsed=json.loads(file.read_text(encoding="utf-8"))
            self.assertEqual(parsed["checks"],rows)
            self.assertEqual(parsed["attemptedQueries"],19)

    def test_drop_counts_are_kept_and_checked(self):
        # 11-01: 외신 출입처 검색 0줄이 '검색 결과 없음'인지 '걸러짐'인지 건수로 구분
        r=row("checked_no_recent_rows",category="출입처·석유화학정유",global_feed=True)
        r.update(feedItems=42,dropped={"notNews":0,"domestic":3,"outlet":30,"old":9,"unscored":0})
        out=build([r],expected=1,news_items=1,now=NOW,threshold=1)
        self.assertEqual((out["checks"][0]["feedItems"],out["checks"][0]["dropped"]["outlet"]),(42,30))
        bad=dict(r,dropped={"title":1})
        with self.assertRaises(ValueError):build([bad],expected=1,news_items=1,now=NOW,threshold=1)

    def test_missing_query_coverage_is_incomplete(self):
        report=build([row("checked_recent_rows",count=3)],expected=19,
                     news_items=11,now=NOW)
        self.assertFalse(report["allProvidersResponded"])
        self.assertEqual(report["status"],"incomplete_queries_or_provider_errors")

    def test_error_field_cannot_leak_urls_or_credentials(self):
        bad=row("transport_or_xml_error",error="https://example.test/?ServiceKey=abc")
        with self.assertRaises(ValueError):
            build([bad],expected=1,news_items=0,now=NOW)

    def test_latency_rank_does_not_expose_feed_urls_or_secrets(self):
        rows=[
            {**row("checked_recent_rows",count=4),"durationMs":1200},
            {**row("transport_or_xml_error",error="TimeoutError"),"durationMs":18000},
            {**row("checked_no_recent_rows"),"durationMs":300}
        ]
        result=build(rows,expected=3,news_items=12,now=NOW)
        self.assertEqual([x["durationMs"] for x in result["slowestQueries"]],
                         [18000,1200,300])
        self.assertEqual(result["slowestQueries"][0]["status"],"transport_or_xml_error")
        self.assertNotIn("https://",str(result["slowestQueries"]))
        with self.assertRaises(ValueError):
            build([{**rows[0],"durationMs":"18000"}],expected=1,
                  news_items=0,now=NOW)

    def test_bad_rss_dates_are_not_verified_empty_news(self):
        partial={**row("checked_partial_dates",count=2,error="InvalidPublishedDate"),
                 "invalidPubDateRows":3,"futurePubDateRows":1}
        valid=row("checked_recent_rows",count=12)
        report=build([partial,valid],expected=2,news_items=14,now=NOW)
        self.assertEqual(report["errorQueries"],1)
        self.assertEqual(report["validEmptyQueries"],0)
        self.assertEqual(report["dateIncompleteQueries"],1)
        self.assertEqual(report["invalidPublishedDatesSkipped"],3)
        self.assertEqual(report["futurePublishedDatesSkipped"],1)
        self.assertFalse(report["allProvidersResponded"])
        self.assertEqual(report["status"],"incomplete_queries_or_provider_errors")

    def test_date_error_counters_are_bounded_and_consistent(self):
        for broken in (
            {"invalidPubDateRows":-1},
            {"invalidPubDateRows":"2"},
            {"invalidPubDateRows":0,"futurePubDateRows":1},
            {"invalidPubDateRows":1,"futurePubDateRows":2},
            {"invalidPubDateRows":1001},
        ):
            with self.assertRaises(ValueError):
                build([{**row("checked_partial_dates",error="InvalidPublishedDate"),
                        **broken}],expected=1,news_items=12,now=NOW)
        with self.assertRaises(ValueError):
            build([row("checked_partial_dates",error="InvalidPublishedDate")],
                  expected=1,news_items=12,now=NOW)

    def test_focused_exclusive_queries_have_dedicated_source_health(self):
        rows=[{**row("checked_recent_rows",category="단독",count=3),
               "exclusiveQuery":True},
              {**row("checked_no_recent_rows",category="단독"),
               "exclusiveQuery":True},
              {**row("transport_or_xml_error",category="단독",error="TimeoutError"),
               "exclusiveQuery":True},
              row("checked_recent_rows",count=7)]
        report=build(rows,expected=4,news_items=11,now=NOW)
        self.assertEqual(report["exclusiveQueriesAttempted"],3)
        self.assertEqual(report["exclusiveQueriesFailedOrPartial"],1)
        self.assertEqual(report["exclusiveQueriesWithRecentRows"],1)
        self.assertEqual(report["exclusiveQueryRecentRowsBeforeDedupe"],3)
        self.assertFalse(report["allProvidersResponded"])
        with self.assertRaises(ValueError):
            build([{**rows[0],"exclusiveQuery":"true"}],
                  expected=1,news_items=11,now=NOW)

    def test_naive_clock_rejected(self):
        with self.assertRaises(ValueError):
            build([row("checked_recent_rows",count=2)],expected=1,
                news_items=2,now=datetime(2026,10,16))

if __name__=="__main__":
    unittest.main()
