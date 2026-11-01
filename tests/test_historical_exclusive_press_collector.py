"""A year of exclusive headline searches must be observable, never inferred."""
import copy
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.historical_exclusive_press_collector import (
    STATUS, BEATS, MONTHS, planned_searches, parse_observed_headlines,
    merge_history, month_bounds, tracked_industry_companies, recent_searches, QUERIES_PER_RUN
)
N=len(BEATS)            # 출입 묶음 수(11-01 석유화학·정유 추가로 6)
ALL=MONTHS*N           # 13개월 × 묶음

KST=timezone(timedelta(hours=9))
NOW=datetime(2026,10,18,22,0,tzinfo=KST)
WIN={"windowId":"auto:2026-09-01","beat":"auto",
     "start":"2026-09-01","endExclusive":"2026-10-01"}


def rss(*articles):
    rows=[]
    for title,source,published,link in articles:
        rows.append(
            "<item><title>"+escape(title)+"</title><link>"+escape(link)+"</link>"
            "<pubDate>"+escape(published)+"</pubDate>"
            '<source url="https://www.example.com">'+escape(source)+"</source></item>"
        )
    return ('<rss><channel>'+''.join(rows)+'</channel></rss>').encode("utf-8")


def article(title="[단독] 현대차 공장 신설 검토",
            source="경제신문",
            pub="Tue, 15 Sep 2026 09:00:00 +0900",
            link="https://news.google.com/rss/articles/abc?oc=5"):
    return (title,source,pub,link)


def check(status="checked",matched=1):
    return {"windowId":WIN["windowId"],"status":status,
            "matched":matched if status=="checked" else None,
            **({"errorType":"TimeoutError"} if status=="failed" else {})}


class HistoricalExclusiveIndexTests(unittest.TestCase):

    def test_recent_five_beat_windows_always_run_independent_of_old_rotation(self):
        recent=recent_searches(NOW)
        self.assertEqual(len(recent),len(BEATS))
        self.assertEqual({r["windowId"] for r in recent},
                         {"recent:"+beat for beat in BEATS})
        self.assertEqual({r["start"] for r in recent},{"2026-10-15"})
        self.assertEqual({r["endExclusive"] for r in recent},{"2026-10-19"})
        self.assertTrue(all("after%3A" in r["url"]
                            and "before%3A" in r["url"] for r in recent))
        old=merge_history(None,[],[check(matched=0)],now=NOW)
        self.assertEqual({r["windowId"] for r in recent_searches(NOW)},
                         {r["windowId"] for r in recent_searches(
                             NOW+timedelta(minutes=15))})
        self.assertIn("2026-10-15",recent_searches(NOW)[0]["start"])
        self.assertEqual(old["recentBeatQueriesAttempted"],0)
        self.assertFalse(old["recentBeatQueriesAllChecked"])

    def test_recent_observed_corpus_and_partial_health_never_imply_zero_news(self):
        recent=recent_searches(NOW)
        headline=article(
            "[단독] 현대차 오늘 전력기기 계약 검토",
            pub="Sun, 18 Oct 2026 13:15:00 +0900",
            link="https://news.google.com/rss/articles/recent-2026")
        data,meta=parse_observed_headlines(rss(headline),recent[0],now=NOW)
        self.assertEqual(len(data),1)
        self.assertEqual(data[0]["historicalBackfillWindow"],"recent:auto")
        checks=[{"windowId":recent[0]["windowId"],"status":"checked",**meta}]
        checks.extend({"windowId":w["windowId"],"status":"failed",
                       "errorType":"TimeoutError"} for w in recent[1:])
        snapshot=merge_history(None,data,[check(matched=0)],now=NOW,
                               recent_checks=checks)
        self.assertEqual(snapshot["recentBeatQueriesAttempted"],N)
        self.assertEqual(snapshot["recentBeatQueriesSucceeded"],1)
        self.assertEqual(snapshot["recentBeatQueriesFailed"],N-1)
        self.assertFalse(snapshot["recentBeatQueriesAllChecked"])
        self.assertEqual(snapshot["recentObservedHeadlinesRetained"],1)
        self.assertFalse(snapshot["recentSearchCoverageExhaustive"])
        self.assertEqual(snapshot["confirmedScoops"],0)
        self.assertEqual(snapshot["humanReviewedYPN"],0)
        outage=merge_history(snapshot,[],[check(matched=0)],
                             now=NOW+timedelta(minutes=15),
                             recent_checks=[
                                 {"windowId":w["windowId"],"status":"failed",
                                  "errorType":"TimeoutError"} for w in recent])
        self.assertEqual(outage["itemCount"],1)
        self.assertEqual(outage["recentBeatQueriesFailed"],N)
        self.assertEqual(outage["recentObservedHeadlinesRetained"],1)
        self.assertEqual(outage["recentLastSuccessfulAt"],
                         snapshot["recentLastSuccessfulAt"])

    def test_recent_bad_inputs_do_not_modify_historical_search_health(self):
        for broken in [
            [{"windowId":"recent:auto","status":"checked"}]*2,
            [{"windowId":"recent:unknown","status":"checked"}],
            [{"windowId":"recent:auto","status":"empty"}],
        ]:
            with self.assertRaises(ValueError):
                merge_history(None,[],[check(matched=0)],now=NOW,
                              recent_checks=broken)

    def test_unchecked_windows_are_first_even_after_clock_jump(self):
        first=planned_searches(NOW,previous=None)
        self.assertEqual(len(first),QUERIES_PER_RUN)
        self.assertEqual({x["start"] for x in first},{"2026-10-01"})
        checked=[{"windowId":w["windowId"],"status":"checked","matched":0}
                 for w in first]
        history=merge_history(None,[],checked,now=NOW)
        next_run=planned_searches(NOW+timedelta(minutes=45),
                                   previous=history)
        self.assertEqual(len(next_run),QUERIES_PER_RUN)
        self.assertEqual({x["start"] for x in next_run},{"2026-09-01"})
        self.assertFalse({x["windowId"] for x in first}
                         .intersection(x["windowId"] for x in next_run))

    def test_all_month_beat_windows_covered_before_rechecking(self):
        history=None
        executed=set()
        for i in range(13):
            now=NOW+timedelta(minutes=i*15)
            windows=planned_searches(now,previous=history)
            self.assertEqual(len(windows),QUERIES_PER_RUN)
            self.assertFalse(set(x["windowId"] for x in windows)&executed)
            executed.update(x["windowId"] for x in windows)
            checks=[{"windowId":x["windowId"],"status":"checked","matched":0}
                    for x in windows]
            history=merge_history(history,[],checks,now=now)
        self.assertEqual(len(executed),ALL)
        self.assertEqual(history["searchedWindowsWithPriorSuccess"],ALL)
        self.assertEqual(history["unvisitedBeatMonthWindows"],0)
        self.assertEqual(history["selectedBeatMonthWindows"],[
            x["windowId"] for x in windows])
        self.assertTrue(history["sourceCompletenessNotEstablished"])
        self.assertFalse(history["allDomesticIndustryExclusivesCovered"])
        refresh=planned_searches(NOW+timedelta(hours=4),
                                 previous=history)
        self.assertEqual(len(refresh),QUERIES_PER_RUN)
        self.assertEqual({x["windowId"] for x in refresh},
                         {x["windowId"] for x in planned_searches(NOW)})

    def test_gap_failure_kept_unknown_then_retried_when_due(self):
        history=None
        for i in range(13):
            now=NOW+timedelta(minutes=i*15)
            windows=planned_searches(now,previous=history)
            checks=[{"windowId":x["windowId"],
                     "status":"failed" if i==0 else "checked",
                     "matched":None if i==0 else 0,
                     **({"errorType":"TimeoutError"} if i==0 else {})}
                    for x in windows]
            history=merge_history(history,[],checks,now=now)
        self.assertEqual(history["unvisitedBeatMonthWindows"],QUERIES_PER_RUN)
        review=planned_searches(NOW+timedelta(hours=4),previous=history)
        self.assertEqual({w["windowId"] for w in review},
                         {w["windowId"] for w in planned_searches(NOW)})
        self.assertEqual(history["windowHealth"][review[0]["windowId"]]["failStreak"],1)
        self.assertFalse(history["allDomesticIndustryExclusivesCovered"])

    def test_next_month_prunes_expired_window_health_not_articles(self):
        prior=merge_history(None,[],[
            {"windowId":"auto:2025-10-01","status":"checked","matched":0}],
            now=NOW)
        after=merge_history(prior,[],[
            {"windowId":"auto:2026-11-01","status":"checked","matched":0}],
            now=datetime(2026,11,3,12,0,tzinfo=KST))
        self.assertNotIn("auto:2025-10-01",after["windowHealth"])
        self.assertIn("auto:2026-11-01",after["windowHealth"])
        self.assertLessEqual(len(after["windowHealth"]),ALL)

    def test_explicit_batch_is_still_bounded_and_replayable(self):
        baseline=merge_history(None,[],[check(matched=0)],now=NOW)
        expected=planned_searches(NOW,batch=12)
        same=planned_searches(NOW+timedelta(minutes=5),
                              previous=baseline,batch=12)
        self.assertEqual([w["windowId"] for w in expected],
                         [w["windowId"] for w in same])
        with self.assertRaises(ValueError):
            planned_searches(NOW,previous=baseline,batch=13)

    def test_real_month_windows_rotate_all_beat_month_slots(self):
        batches=[planned_searches(NOW,batch=i) for i in range(13)]
        urls=[r for part in batches for r in part]
        self.assertEqual(len(urls),MONTHS*len(BEATS))
        self.assertEqual(len({r["windowId"] for r in urls}),ALL)
        self.assertEqual(month_bounds(NOW,12)[0].isoformat(),"2025-10-01")
        self.assertTrue(all("after%3A" in u["url"]
                            and "before%3A" in u["url"] for u in urls))

    def test_latest_battery_materials_company_can_be_observed_as_press_not_scoop(self):
        title="[단독] 천보 미중 차세대 배터리 전해액 수출"
        self.assertEqual(tracked_industry_companies(title),["천보"])
        recent=recent_searches(NOW)
        battery=next(x for x in recent if x["beat"]=="parts_battery")
        self.assertIn("천보",battery["query"])
        self.assertEqual(len(recent),len(BEATS))

    def test_actual_2025_homonyms_are_not_auto_steel_exclusives(self):
        misleading=[
            "[단독]친부모 정보 없는 ‘기아호적’ 공식 확인된 것만 3만8000여건",
            "[단독] 금호제21구역, 롯데건설·포스코이앤씨 맞대결…포스코 적극 검토 중",
            "[단독] 제네시스 챔피언십 KPGA 출전 명단 확정",
        ]
        for title in misleading:
            self.assertEqual(tracked_industry_companies(title),[],title)
        valid=[
            "[단독] 기아 EV6 충전 결함 원인 조사",
            "[단독] 포스코 미국 제철소 후판 신규 공장",
            "[단독] 포스코필바라리튬솔루션 생산 계획",
        ]
        for title in valid:
            self.assertTrue(tracked_industry_companies(title),title)

    def test_live_2025_false_kia_and_posco_are_removed_from_rolling_history(self):
        a=parse_observed_headlines(rss(article()),WIN,now=NOW)[0][0]
        prior=merge_history(None,[a],[check()],now=NOW)
        bad=copy.deepcopy(a)
        bad.update(id="b"*24,
                   title="[단독] 기아호적 공식 확인 3만8000여건",
                   companies=["기아"])
        construction=copy.deepcopy(a)
        construction.update(id="c"*24,
                            title="[단독] 포스코이앤씨 건설 시공사 결정…포스코 검토",
                            companies=["포스코"])
        prior["items"].extend([bad,construction])
        prior["itemCount"]=3
        updated=merge_history(prior,[],[check(matched=0)],
            now=NOW+timedelta(hours=1))
        self.assertEqual(updated["discardedLegacyOffBeatHeadlinesThisRun"],2)
        self.assertEqual(updated["itemCount"],1)
        self.assertEqual(updated["items"][0]["id"],a["id"])
        self.assertEqual(updated["confirmedScoops"],0)

    def test_historical_article_is_observed_not_claimed_unreported(self):
        result,stats=parse_observed_headlines(rss(article()),WIN,now=NOW)
        self.assertEqual(stats["matched"],1)
        self.assertEqual(len(result),1)
        row=result[0]
        self.assertEqual(row["companies"],["현대차"])
        self.assertFalse(row["publisherOriginalUrlVerified"])
        self.assertFalse(row["publisherPublicationTimeVerified"])
        self.assertFalse(row["fulltextReviewed"])
        self.assertTrue(row["rssIndexedHeadlineOnly"])

    def test_rss_failure_is_not_valid_empty_result(self):
        with self.assertRaises(ValueError):
            parse_observed_headlines(b"<html>site down</html>",WIN,now=NOW)
        baseline=merge_history(None,[],[check("failed")],now=NOW)
        self.assertEqual(baseline["itemCount"],0)
        self.assertEqual(baseline["failedWindowsThisRun"],1)
        self.assertIsNone(baseline["lastSuccessfulSearchAt"])
        self.assertFalse(baseline["allDomesticIndustryExclusivesCovered"])
        self.assertFalse(baseline["pressArticleFulltextsReviewed"])

    def test_source_outage_retains_last_good_titles(self):
        item=parse_observed_headlines(rss(article()),WIN,now=NOW)[0][0]
        first=merge_history(None,[item],[check()],now=NOW)
        second=merge_history(first,[],[check("failed")],
                             now=NOW+timedelta(hours=1))
        self.assertEqual(second["itemCount"],1)
        self.assertEqual(second["items"][0]["id"],item["id"])
        self.assertEqual(second["windowHealth"][WIN["windowId"]]["failStreak"],1)
        self.assertEqual(second["lastSuccessfulSearchAt"],
                         first["lastSuccessfulSearchAt"])
        third=merge_history(second,[item],[check()],
                            now=NOW+timedelta(hours=2))
        self.assertEqual(third["windowHealth"][WIN["windowId"]]["failStreak"],0)
        self.assertEqual(third["itemCount"],1)
        self.assertEqual(third["newObservedHeadlineCount"],0)

    def test_all_duplicate_RSS_urls_have_stable_article_ids(self):
        a=article(title="[단독] 현대차 공장 신설 계약")
        result,_=parse_observed_headlines(rss(a,a),WIN,now=NOW)
        first=merge_history(None,result,[check(matched=2)],now=NOW)
        self.assertEqual(first["itemCount"],1)
        self.assertTrue(first["firstRunBaseline"])
        next_pass=merge_history(first,result,[check(matched=2)],
                                now=NOW+timedelta(minutes=15))
        self.assertEqual(next_pass["newObservedHeadlineCount"],0)
        self.assertFalse(next_pass["firstRunBaseline"])

    def test_pubdate_missing_future_undated_and_outside_month_rejected(self):
        rows=[
            article(pub=""),
            article(pub="Tue, 15 Sep 2026 09:00:00"),
            article(pub="Wed, 15 Oct 2025 09:00:00 +0900"),
            article(pub="Tue, 20 Oct 2026 09:00:00 +0900"),
        ]
        result,stats=parse_observed_headlines(rss(*rows),WIN,now=NOW)
        self.assertEqual(result,[])
        self.assertEqual(stats["undated"],2)
        self.assertEqual(stats["outsideWindow"],2)

    def test_companyless_and_sports_are_not_false_industry_exclusives(self):
        articles=[
            article(title="[단독] 프로야구 기아 타이거즈 새 계약"),
            article(title="[단독] 국내 시장 신기술 도입"),
            article(title="[단독] 포스코 원자재 공급계약"),
        ]
        result,stats=parse_observed_headlines(rss(*articles),WIN,now=NOW)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]["companies"],["포스코"])
        self.assertEqual(stats["offBeatOrSport"],2)

    def test_corrupt_or_malicious_prior_history_never_overwritten_as_zero(self):
        a=parse_observed_headlines(rss(article()),WIN,now=NOW)[0][0]
        first=merge_history(None,[a],[check()],now=NOW)
        wrong=copy.deepcopy(first)
        wrong["status"]="unexpected"
        with self.assertRaises(ValueError):
            merge_history(wrong,[],[check()],now=NOW)
        wrong=copy.deepcopy(first)
        wrong["items"][0]["fulltextReviewed"]=True
        with self.assertRaises(ValueError):
            merge_history(wrong,[],[check()],now=NOW)

    def test_truncation_guard_preserves_previous(self):
        start=merge_history(None,[],[check(matched=0)],now=NOW)
        with self.assertRaises(ValueError):
            merge_history(start,[{"title":"forged"}],[check()],now=NOW)

    def test_google_articles_url_and_tracked_company_required(self):
        forged=article(link="https://attacker.example/rss/articles/abc")
        rows,stats=parse_observed_headlines(rss(forged),WIN,now=NOW)
        self.assertFalse(rows)
        self.assertEqual(stats["offBeatOrSport"],1)

if __name__=="__main__":
    unittest.main()
