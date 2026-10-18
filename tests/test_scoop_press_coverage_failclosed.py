"""No Google RSS response or annual index gap may be 'domestic unreported'."""
import sys
import tempfile
import unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import scoop_scout as scout
from scripts.press_coverage_index import merge_index
from scripts.press_coverage_gate import load_index, prior_coverage_candidates

KST=timezone(timedelta(hours=9))
NOW=datetime(2026,10,18,22,0,tzinfo=KST)


def event():
    return {
        "title":"현대자동차 자율주행 리콜 94622대",
        "summary":"현대자동차 자율주행 리콜 94622대 차량",
        "published":"2026-10-18T18:00:00+09:00",
        "companies":["현대차"]}


def press(at="2026-10-18T17:00:00+09:00",title=None):
    return {
        "title":title or event()["title"],"sourceName":"경제신문",
        "published":at,"url":"https://publisher.example/old-story",
        "companies":["현대차"],"global":False,
        "pitchScore":0,"clusterCount":19,"exclusive":False}


class DomesticNewsFailureGate(unittest.TestCase):
    def test_google_rss_timeout_is_failed_not_empty_news(self):
        before=dict(scout.RSS_QUERY_DIAGNOSTICS)
        errors=scout.COVERAGE_SEARCH_DIAGNOSTICS["failedQueries"]
        with patch.object(scout,"get",side_effect=TimeoutError("remote index down")):
            rows=scout.google_rss("coverage","현대자동차 리콜 94622")
        self.assertEqual(rows,[])
        self.assertEqual(scout.RSS_QUERY_DIAGNOSTICS["coverageFailed"],
                         before["coverageFailed"]+1)
        self.assertEqual(scout.COVERAGE_SEARCH_DIAGNOSTICS["failedQueries"],
                         errors+1)

    def test_non_rss_provider_payload_is_failed_not_zero(self):
        before=scout.RSS_QUERY_DIAGNOSTICS["coverageFailed"]
        with patch.object(scout,"get",return_value=b"<html><p>maintenance</p></html>"):
            self.assertEqual(scout.google_rss("coverage","현대차 리콜"),[])
        self.assertEqual(scout.RSS_QUERY_DIAGNOSTICS["coverageFailed"],before+1)

    def test_valid_empty_rss_is_empty_not_provider_failure(self):
        before=dict(scout.RSS_QUERY_DIAGNOSTICS)
        with patch.object(scout,"get",return_value=b"<rss><channel /></rss>"):
            rows=scout.google_rss("coverage","현대자동차 리콜")
        self.assertEqual(rows,[])
        self.assertEqual(scout.RSS_QUERY_DIAGNOSTICS["failed"],before["failed"])
        self.assertEqual(scout.RSS_QUERY_DIAGNOSTICS["empty"],before["empty"]+1)

    def test_coverage_query_failure_is_reliably_recorded(self):
        before=scout.COVERAGE_SEARCH_DIAGNOSTICS["failedQueries"]
        with patch.object(scout,"get",side_effect=TimeoutError("down")):
            result=scout.coverage_search(event())
        self.assertEqual(result,[])
        self.assertGreater(scout.COVERAGE_SEARCH_DIAGNOSTICS["failedQueries"],before)

    def test_popular_low_score_prior_article_is_negative_exclusivity_evidence(self):
        archive=merge_index(None,[press()],now=NOW)
        report=prior_coverage_candidates(event(),archive,
            event_match_score=scout.event_match_score,
            companies=["현대차"],now=NOW)
        self.assertEqual(report["status"],"indexed_prior_headline_candidate")
        self.assertEqual(len(report["matches"]),1)
        self.assertTrue(report["matches"][0]["indexedHeadlineOnly"])
        self.assertFalse(report["fulltextReviewed"])
        self.assertFalse(report["notReportedProved"])
        self.assertEqual(report["matches"][0]["eventMatchScore"],0.8)

    def test_no_index_results_cannot_prove_domestic_exclusive(self):
        valid=merge_index(None,[],now=NOW)
        report=prior_coverage_candidates(event(),valid,
            event_match_score=scout.event_match_score,
            companies=["현대차"],now=NOW)
        self.assertEqual(report["status"],"no_strong_index_match_not_no_news")
        self.assertFalse(report["notReportedProved"])
        self.assertEqual(report["matches"],[])

    def test_seed_initial_index_must_not_certify_no_press(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"index.json"
            p.write_text('{"status":"observed_domestic_press_index_not_complete_coverage",'
                         '"seedOnly":true,"itemCount":0,"items":[]}',encoding="utf-8")
            loaded=load_index(p)
            self.assertEqual(loaded["status"],"initial_baseline_without_articles")
            report=prior_coverage_candidates(event(),loaded,
                event_match_score=scout.event_match_score,
                companies=["현대차"],now=NOW)
            self.assertEqual(report["status"],"index_unavailable_not_no_news")
            self.assertFalse(report["notReportedProved"])

    def test_article_after_original_date_is_not_prior(self):
        after=press("2026-10-18T19:30:00+09:00")
        archive=merge_index(None,[after],now=NOW)
        report=prior_coverage_candidates(event(),archive,
            event_match_score=scout.event_match_score,
            companies=["현대차"],now=NOW)
        self.assertEqual(report["matches"],[])
        self.assertFalse(report["notReportedProved"])


if __name__=="__main__":
    unittest.main()
