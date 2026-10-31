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
    def lead(self, responder):
        row={**event(),"title":"현대자동차 울산 공장 신규 생산중단",
             "url":"https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261018000001",
             "official":True,"officialLabel":"DART","sourceName":"DART"}
        with patch.object(scout,"get",side_effect=responder):
            leads,diag=scout.build_lead_signals([row],[],NOW)
        self.assertEqual(len(leads),1,diag)
        return leads[0],diag

    def test_lead_failed_search_cannot_claim_no_matching_press(self):
        lead,diag=self.lead(TimeoutError("down"))
        self.assertFalse(lead["coverageChecked"])
        self.assertEqual(lead["coverageSearchStatus"],"failed")
        self.assertEqual(lead["leadStrength"],"보도 확인 대기")
        self.assertNotIn("매칭 없음",lead["coverageStatus"])
        self.assertEqual(diag["coverage_unknown"],1)

    def test_lead_partial_search_is_not_complete(self):
        lead,_=self.lead([b"<rss><channel /></rss>",TimeoutError("down")])
        self.assertEqual(lead["coverageSearchStatus"],"partial")
        self.assertEqual(lead["coverageSuccessfulQueries"],1)
        self.assertFalse(lead["coverageChecked"])

    def test_lead_valid_empty_search_retains_limited_no_match_wording(self):
        lead,_=self.lead(lambda *args:b"<rss><channel /></rss>")
        self.assertTrue(lead["coverageChecked"])
        self.assertEqual(lead["coverageSearchStatus"],"complete")
        self.assertFalse(lead["notReportedProved"])
        self.assertFalse(lead["fulltextReviewed"])

    def test_unsearchable_title_is_not_completed_empty_search(self):
        report=scout.coverage_search_report({"title":"짧음"})
        self.assertEqual(report["status"],"not_run")

    def test_lead_uses_year_index_before_rss_even_when_dashboard_empty(self):
        row={**event(),"title":"현대자동차 울산 공장 신규 생산중단",
             "url":"https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261018000001",
             "official":True,"officialLabel":"DART","sourceName":"DART"}
        older=press("2026-09-18T17:00:00+09:00",row["title"])
        index=merge_index(None,[older],now=NOW)
        with patch.object(scout,"load_press_index",return_value=index), \
             patch.object(scout,"get",side_effect=AssertionError("unneeded RSS")) as get:
            leads,diag=scout.build_lead_signals([row],[],NOW)
        self.assertEqual(leads,[])
        self.assertEqual(diag["prior_index_coverage"],1)
        get.assert_not_called()

    def test_missing_index_is_unknown_and_never_proves_no_press(self):
        with patch.object(scout,"load_press_index",return_value={"status":"missing_or_invalid_index"}):
            lead,_=self.lead(lambda *args:b"<rss><channel /></rss>")
        self.assertEqual(lead["coverageIndexStatus"],"index_unavailable_not_no_news")
        self.assertFalse(lead["notReportedProved"])

    def test_unexpected_search_exception_is_unknown(self):
        with patch.object(scout,"coverage_search",side_effect=ValueError("bad")):
            report=scout.coverage_search_report(event())
        self.assertEqual(report["status"],"failed")
        self.assertTrue(report["unexpectedError"])

    def test_previous_failure_does_not_contaminate_next_search(self):
        with patch.object(scout,"get",side_effect=TimeoutError("down")):
            scout.coverage_search_report(event())
        with patch.object(scout,"get",return_value=b"<rss><channel /></rss>"):
            report=scout.coverage_search_report(event())
        self.assertEqual(report["status"],"complete")
        self.assertEqual(report["failedQueries"],0)

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


    def test_malformed_rss_article_dates_fail_closed_not_empty_news(self):
        before=dict(scout.RSS_QUERY_DIAGNOSTICS)
        xml=(b"<rss><channel><item><title>sample</title>"
             b"<link>https://news.example/item</link>"
             b"<pubDate>not a date</pubDate></item></channel></rss>")
        with patch.object(scout,"get",return_value=xml):
            report=scout.coverage_search_report(event())
        self.assertEqual(report["status"],"failed")
        self.assertEqual(report["successfulQueries"],0)
        self.assertFalse(report["notReportedProved"])
        self.assertEqual(scout.RSS_QUERY_DIAGNOSTICS["empty"],before["empty"])
        self.assertGreater(scout.RSS_QUERY_DIAGNOSTICS["invalidDateRows"],
                           before["invalidDateRows"])

    def test_future_rss_article_is_provider_date_error_not_new_story(self):
        from email.utils import format_datetime
        future=format_datetime(datetime.now(KST)+timedelta(days=9))
        xml=("<rss><channel><item><title>산업 리콜</title>"
             "<link>https://news.example/future</link>"
             "<pubDate>"+future+"</pubDate></item></channel></rss>").encode()
        before=dict(scout.RSS_QUERY_DIAGNOSTICS)
        with patch.object(scout,"get",return_value=xml):
            rows=scout.google_rss("coverage","현대차 리콜")
        self.assertEqual(rows,[])
        self.assertEqual(scout.RSS_QUERY_DIAGNOSTICS["empty"],before["empty"])
        self.assertGreater(scout.RSS_QUERY_DIAGNOSTICS["futureDateRows"],
                           before["futureDateRows"])

    def test_mixed_rss_good_and_bad_dates_are_partial_not_complete(self):
        from email.utils import format_datetime
        current=format_datetime(datetime.now(KST)-timedelta(minutes=8))
        xml=("<rss><channel>"
             "<item><title>bad</title><link>https://news.example/bad</link>"
             "<pubDate>???</pubDate></item>"
             "<item><title>현대차 리콜</title><link>https://news.example/good</link>"
             "<pubDate>"+current+"</pubDate><source>매체</source></item>"
             "</channel></rss>").encode()
        with patch.object(scout,"get",return_value=xml):
            report=scout.coverage_search_report(event())
        self.assertEqual(report["status"],"partial")
        self.assertGreater(report["successfulQueries"],0)
        self.assertGreater(report["failedQueries"],0)
        self.assertFalse(report["notReportedProved"])

    def test_all_old_but_dated_rss_is_clean_empty_not_failure(self):
        from email.utils import format_datetime
        old=format_datetime(datetime.now(KST)-timedelta(days=300))
        xml=("<rss><channel><item><title>old article</title>"
             "<link>https://news.example/old</link>"
             "<pubDate>"+old+"</pubDate></item></channel></rss>").encode()
        with patch.object(scout,"get",return_value=xml):
            report=scout.coverage_search_report(event())
        self.assertEqual(report["status"],"complete")
        self.assertEqual(report["failedQueries"],0)
        self.assertEqual(report["matches"],[])
        self.assertFalse(report["notReportedProved"])

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


class SameAmountMatch(unittest.TestCase):
    # 10-31 운영: 레이더 제목(공시 이름+…)과 10-27 기사 제목의 글자 유사도가 0.1 안팎이라 '기보도 검증 미완료'
    ITEM={"title":"HD현대일렉트릭, 배전반/배전변압기 생산 공장 및 자동화 설비 등 생산 인프라 1,980억원 증설 투자…투자 대상·가동 시점은",
          "summary":"HD현대일렉트릭 신규시설투자"}

    def score(self,headline):
        return scout.event_match_score(self.ITEM,{"title":headline,"summary":""})

    def test_same_company_event_word_and_amount_is_the_same_event(self):
        self.assertGreaterEqual(self.score("HD현대일렉트릭, 청주 배전캠퍼스 배전기 시설 증설에 1980억 투자"),0.8)
        self.assertGreaterEqual(self.score("청주공장 1,980억원 증설 나선 HD현대일렉트릭"),0.8)

    def test_other_amount_or_company_or_no_event_word_is_not(self):
        self.assertEqual(self.score("HD현대일렉트릭, 미국 공장 증설에 2,500억 투자"),0.0)
        self.assertEqual(self.score("LS일렉트릭, 배전반 공장 증설에 1980억 투자"),0.0)
        self.assertEqual(self.score("HD현대일렉트릭 3분기 영업익 1980억"),0.0)

    def test_money_amounts_normalise_commas_and_won(self):
        self.assertEqual(scout.money_amounts("1,980억원"),scout.money_amounts("1980억"))
        self.assertEqual(scout.money_amounts("1조 2,000억원 · 5,000만원"),{1000000,200000})  # 1억 미만은 뺌


if __name__=="__main__":
    unittest.main()
