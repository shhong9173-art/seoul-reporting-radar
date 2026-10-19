import sys
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from industry_news_guard import verified_rss_date,inspect_rss_date,summarize_queries
from news_headline_identity import normalize_title

KST=timezone(timedelta(hours=9))
NOW=datetime(2026,10,18,23,0,tzinfo=KST)


class IndustrialFeedEvidence(unittest.TestCase):
    def test_invalid_pubdate_never_becomes_current_time(self):
        for pub in ("",None,"missing","Sun, 18 Oct 2026 10:00:00"):
            self.assertIsNone(verified_rss_date(pub,now=NOW))
        self.assertIsNone(verified_rss_date(
            "Sun, 01 Jan 2012 12:00:00 +0900",now=NOW))

    def test_actual_rfc822_date_and_clock_offset(self):
        d=verified_rss_date("Sun, 18 Oct 2026 11:00:00 +0000",now=NOW)
        self.assertEqual(d.isoformat(),"2026-10-18T20:00:00+09:00")
        self.assertIsNone(verified_rss_date(
            "Mon, 19 Oct 2026 10:00:00 +0900",now=NOW))

    def test_source_date_reason_distinguishes_old_from_invalid_and_future(self):
        old,old_reason=inspect_rss_date(
            "Sun, 01 Jan 2012 12:00:00 +0900",now=NOW)
        bad,bad_reason=inspect_rss_date("wrong date",now=NOW)
        later,later_reason=inspect_rss_date(
            "Mon, 19 Oct 2026 05:00:00 +0900",now=NOW)
        self.assertEqual((old,old_reason),(None,"outside_window"))
        self.assertEqual((bad,bad_reason),(None,"invalid"))
        self.assertEqual((later,later_reason),(None,"future"))

    def test_partial_dates_are_not_clean_empty_search(self):
        result=summarize_queries([
            {"status":"checked_partial_dates","rejectedUndated":2,
             "rejectedFuture":1,"recentRows":3},
            {"status":"checked_no_relevant_recent","rejectedUndated":0,
             "rejectedFuture":0}],2)
        self.assertEqual(result["status"],"partial_dated_rss_not_complete_coverage")
        self.assertEqual(result["feedsPartiallyDated"],1)
        self.assertEqual(result["rejectedInvalidDates"],2)
        self.assertEqual(result["rejectedFutureDates"],1)
        self.assertEqual(result["feedsCheckedNoRelevantRows"],1)
        self.assertFalse(result["proofOfNoIndustryNews"])

    def test_focused_scoop_search_outage_does_not_freeze_general_industry_news(self):
        rows=[
            {"status":"checked_recent_rows","recentRows":5,
             "dedicatedExclusiveQuery":False},
            {"status":"failed","recentRows":None,"rejectedUndated":None,
             "dedicatedExclusiveQuery":True,"errorType":"TimeoutError"},
        ]
        result=summarize_queries(rows,2)
        self.assertTrue(result["allCoreFeedsHealthy"])
        self.assertFalse(result["allFeedsHealthy"])
        self.assertEqual(result["exclusiveFeedsFailed"],1)
        self.assertEqual(result["coreFeedsFailed"],0)
        self.assertEqual(result["status"],
                         "focused_exclusive_search_partial_not_complete")
        rows[0]["status"]="failed"
        rows[0]["rejectedUndated"]=None
        self.assertFalse(summarize_queries(rows,2)["allCoreFeedsHealthy"])

    def test_focused_exclusive_query_health_is_separate(self):
        rows=[
            {"status":"checked_recent_rows","recentRows":4,
             "dedicatedExclusiveQuery":True},
            {"status":"checked_partial_dates","recentRows":2,
             "rejectedUndated":1,"rejectedFuture":0,
             "dedicatedExclusiveQuery":True},
            {"status":"checked_no_relevant_recent","recentRows":0,
             "dedicatedExclusiveQuery":False},
        ]
        health=summarize_queries(rows,3)
        self.assertEqual(health["exclusiveQueriesAttempted"],2)
        self.assertEqual(health["exclusiveQueriesWithRows"],2)
        self.assertEqual(health["exclusiveQueriesFailedOrPartial"],1)
        self.assertEqual(health["exclusiveQueryObservedRows"],6)
        self.assertFalse(health["domesticUnreportedProved"])

    def test_industrial_rss_outage_is_not_empty_source(self):
        result=summarize_queries([
            {"status":"checked_recent_rows"},
            {"status":"checked_no_relevant_recent"},
            {"status":"failed","errorType":"TimeoutError"}],3)
        self.assertEqual(result["status"],"failed_sources_preserve_previous_dataset")
        self.assertEqual(result["feedsFailed"],1)
        self.assertFalse(result["allFeedsHealthy"])
        self.assertFalse(result["proofOfNoIndustryNews"])
        self.assertFalse(result["domesticUnreportedProved"])

    def test_zero_relevant_news_is_not_zero_underlying_company_reports(self):
        result=summarize_queries([
            {"status":"checked_no_relevant_recent"}],1)
        self.assertTrue(result["allFeedsHealthy"])
        self.assertFalse(result["officialBulletinCoverageComplete"])
        self.assertFalse(result["proofOfNoIndustryNews"])

    def test_schema_mismatch_rejected_instead_of_reported_zero(self):
        with self.assertRaises(ValueError):
            summarize_queries([],7)
        with self.assertRaises(ValueError):
            summarize_queries([{"status":"unknown"}],1)

    def test_industry_merge_keeps_two_distinct_fact_headlines(self):
        a=normalize_title("포스코 - 신규 계약 300억 - 한국경제","한국경제")
        b=normalize_title("포스코 - 기존 계약 취소 - 한국경제","한국경제")
        self.assertNotEqual(a,b)

if __name__=="__main__":
    unittest.main()
