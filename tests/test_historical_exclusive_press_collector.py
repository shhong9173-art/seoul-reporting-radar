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
    merge_history, month_bounds
)

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
    def test_real_month_windows_rotate_65_beat_month_slots(self):
        batches=[planned_searches(NOW,batch=i) for i in range(13)]
        urls=[r for part in batches for r in part]
        self.assertEqual(len(urls),MONTHS*len(BEATS))
        self.assertEqual(len({r["windowId"] for r in urls}),65)
        self.assertEqual(month_bounds(NOW,12)[0].isoformat(),"2025-10-01")
        self.assertTrue(all("after%3A" in u["url"]
                            and "before%3A" in u["url"] for u in urls))

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
