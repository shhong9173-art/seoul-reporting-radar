"""Offline tests execute the actual industrial RSS parser without a live network."""
import ast
import re
import html
import urllib.parse
import unittest
import xml.etree.ElementTree as ET
from datetime import datetime,timedelta
from email.utils import format_datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from scripts.industry_news_guard import inspect_rss_date,summarize_queries

ROOT=Path(__file__).resolve().parents[1]
TREE=ast.parse((ROOT/"industry_collector.py").read_text(encoding="utf-8"))
PARSER=[x for x in TREE.body if isinstance(x,ast.FunctionDef) and x.name=="parse_feed"]
assert len(PARSER)==1
KST=ZoneInfo("Asia/Seoul")
SCOPE={
    "datetime":datetime,"timedelta":timedelta,"KST":KST,
    "ET":ET,"urllib":urllib,"FEED_CHECKS":[],
    "inspect_rss_date":inspect_rss_date,
    "KEY":("철강","변압기","공장","계약","수주"),
    "company_list":lambda text:["포스코"] if "포스코" in text else [],
    "classify":lambda title,desc:(False,False,1,1,False,45),
    "clean":lambda text:re.sub(r"<[^>]+>"," ",html.unescape(text or "")),
}
exec(compile(ast.Module(body=PARSER,type_ignores=[]),
             str(ROOT/"industry_collector.py"),"exec"),SCOPE)
parse_feed=SCOPE["parse_feed"]


def rss(items):
    body=[]
    for title,when,url in items:
        body.append("<item><title>"+title+"</title><link>"+url+"</link>"
                    "<pubDate>"+when+"</pubDate><source>매체</source></item>")
    return ("<rss><channel>"+"".join(body)+"</channel></rss>").encode()


class IndustrialProductionDates(unittest.TestCase):
    def setUp(self):
        SCOPE["FEED_CHECKS"].clear()

    def run_feed(self,entries):
        SCOPE["get"]=lambda _url:rss(entries)
        return parse_feed("철강","포스코 철강")

    def test_mixed_malformed_and_real_news_marks_partial(self):
        now=format_datetime(datetime.now(KST)-timedelta(minutes=20))
        rows=self.run_feed([
            ("포스코 철강 계약","garbage","https://news.example/0"),
            ("포스코 철강 공장",now,"https://news.example/1")])
        self.assertEqual(len(rows),1)
        self.assertIn("공장",rows[0]["title"])
        check=SCOPE["FEED_CHECKS"][-1]
        self.assertEqual(check["status"],"checked_partial_dates")
        self.assertEqual(check["rejectedUndated"],1)
        self.assertEqual(check["rejectedFuture"],0)
        source=summarize_queries([check],1)
        self.assertEqual(source["feedsPartiallyDated"],1)
        self.assertEqual(source["feedsCheckedNoRelevantRows"],0)
        self.assertFalse(source["proofOfNoIndustryNews"])

    def test_malformed_only_is_failed_and_preserves_prior(self):
        rows=self.run_feed([
            ("포스코 철강 거래","","https://news.example/1")])
        self.assertEqual(rows,[])
        check=SCOPE["FEED_CHECKS"][-1]
        self.assertEqual(check["status"],"failed")
        source=summarize_queries([check],1)
        self.assertEqual(source["feedsFailed"],1)
        self.assertFalse(source["allFeedsHealthy"])
        self.assertEqual(source["status"],"failed_sources_preserve_previous_dataset")

    def test_future_dated_article_not_created_in_today_feed(self):
        future=format_datetime(datetime.now(KST)+timedelta(days=1))
        rows=self.run_feed([
            ("포스코 철강 신공장",future,"https://news.example/future")])
        self.assertEqual(rows,[])
        check=SCOPE["FEED_CHECKS"][-1]
        self.assertEqual(check["status"],"failed")
        self.assertEqual(check["rejectedFuture"],1)

    def test_old_but_valid_date_is_a_clean_outside_window(self):
        old=format_datetime(datetime.now(KST)-timedelta(days=60))
        rows=self.run_feed([
            ("포스코 철강 공장",old,"https://news.example/old")])
        self.assertEqual(rows,[])
        check=SCOPE["FEED_CHECKS"][-1]
        self.assertEqual(check["status"],"checked_no_relevant_recent")
        self.assertEqual(check["rejectedUndated"],0)
        self.assertEqual(check["outsideWindowDatedRows"],1)

    def test_empty_rss_is_clean_empty_search_not_official_zero(self):
        self.assertEqual(self.run_feed([]),[])
        check=SCOPE["FEED_CHECKS"][-1]
        self.assertEqual(check["status"],"checked_no_relevant_recent")
        self.assertFalse(summarize_queries([check],1)["proofOfNoIndustryNews"])


if __name__=="__main__":
    unittest.main()
