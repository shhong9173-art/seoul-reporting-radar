"""Offline production collector RSS chronology and source-identity regressions.

Only compile selected actual functions; importing collector.py invokes live RSS
collection and must never be done in an isolated test.
"""
import ast
import re
import html
import time
import urllib.parse
import unittest
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime, format_datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from scripts.news_headline_identity import normalize_title, obvious_sports_homonym

ROOT=Path(__file__).resolve().parents[1]
TREE=ast.parse((ROOT/"collector.py").read_text(encoding="utf-8"))
NAMES={"norm_title","parse_feed","dedupe","exclusive","error_label","failure_summary"}
FUNS=[n for n in TREE.body if isinstance(n,ast.FunctionDef) and n.name in NAMES]
assert len(FUNS)==len(NAMES)
KST=ZoneInfo("Asia/Seoul")
NAMESPACE={
    "re":re,"html":html,"time":time,"urllib":urllib,"ET":ET,
    "datetime":datetime,"timedelta":timedelta,
    "parsedate_to_datetime":parsedate_to_datetime,
    "KST":KST,"FEED_CHECKS":[],
    "normalize_title":normalize_title,
    "obvious_sports_homonym":obvious_sports_homonym,
    "AUTO_SCOOP_RE":re.compile("현대모비스|현대차|기아|자동차",re.I),
    "clean":lambda x:re.sub(r"<[^>]*>"," ",x or ""),
}
exec(compile(ast.Module(body=FUNS,type_ignores=[]),
             str(ROOT/"collector.py"),"exec"),NAMESPACE)
parse_feed=NAMESPACE["parse_feed"]
dedupe=NAMESPACE["dedupe"]


def rss(rows):
    entries=[]
    for title,pub,link,source in rows:
        entries.append(
            "<item><title>"+title+"</title><link>"+link+"</link>"
            "<pubDate>"+pub+"</pubDate><source>"+source+"</source></item>")
    return ("<rss><channel>"+"".join(entries)+"</channel></rss>").encode()


class ProductionRssDateAndIdentity(unittest.TestCase):
    def setUp(self):
        NAMESPACE["FEED_CHECKS"].clear()

    def test_stopped_run_says_why_in_counts_only(self):
        # 11-01 11:30·12:10 KST: 'collection returned only N items'로 멈췄지만 Actions 화면에 이유가 없었다
        import urllib.error
        def fail(_url):
            raise urllib.error.HTTPError("https://news.google.com/rss/search?q=x", 503, "Service Unavailable", {}, None)
        NAMESPACE["get"]=fail
        self.assertEqual(parse_feed("완성차","현대차"),[])
        self.assertEqual(NAMESPACE["FEED_CHECKS"][-1]["errorType"],"HTTPError 503")
        checks=NAMESPACE["FEED_CHECKS"]+[{"status":"transport_or_xml_error","errorType":"URLError"},{"status":"checked_no_recent_rows"},{"status":"checked_recent_rows"}]
        line=NAMESPACE["failure_summary"](checks,4)
        self.assertEqual(line,"국내 뉴스 수집 4건(문턱 10) — 검색 4개 중 실패 2(HTTPError 503 ×1, URLError ×1) · 최근 기사 없음 1")
        self.assertNotIn("news.google",line)

    def run_feed(self,rows):
        NAMESPACE["get"]=lambda _url:rss(rows)
        return parse_feed("완성차","현대차")

    def test_focused_scoop_query_requires_actual_article_headline_marker(self):
        pub=format_datetime(datetime.now(KST)-timedelta(minutes=30))
        NAMESPACE["get"]=lambda _url:rss([
            ("현대차 단독 콘서트 안내",pub,"https://news.example/no","매체"),
            ("[단독] 현대차 신규 계약 확인",pub,"https://news.example/yes","산업매체"),
        ])
        result=parse_feed("단독","[단독] 현대차")
        self.assertEqual(len(result),1)
        self.assertTrue(NAMESPACE["exclusive"](result[0]["title"]))
        self.assertTrue(NAMESPACE["FEED_CHECKS"][-1]["exclusiveQuery"])

    def test_invalid_date_never_rewritten_as_now(self):
        dt=format_datetime(datetime.now(KST)-timedelta(minutes=20))
        items=self.run_feed([
            ("현대차 옛날 기사","broken date","https://news.example/bad","매체"),
            ("현대차 실제 기사",dt,"https://news.example/good","매체")])
        self.assertEqual(len(items),1)
        self.assertEqual(items[0]["title"],"현대차 실제 기사")
        h=NAMESPACE["FEED_CHECKS"][-1]
        self.assertEqual(h["status"],"checked_partial_dates")
        self.assertEqual(h["invalidPubDateRows"],1)
        self.assertEqual(h["recentRows"],1)

    def test_invalid_only_is_not_a_successful_empty_feed(self):
        self.assertEqual(self.run_feed([
            ("현대차 과거 기록","","https://news.example/missing","매체")]),[])
        h=NAMESPACE["FEED_CHECKS"][-1]
        self.assertEqual(h["status"],"malformed_rss")
        self.assertEqual(h["invalidPubDateRows"],1)
        self.assertEqual(h["errorType"],"InvalidPublishedDate")

    def test_future_date_is_rejected_as_bad_timestamp(self):
        future=format_datetime(datetime.now(KST)+timedelta(hours=2))
        items=self.run_feed([("기아 내일 뉴스",future,
                             "https://news.example/future","매체")])
        self.assertEqual(items,[])
        h=NAMESPACE["FEED_CHECKS"][-1]
        self.assertEqual(h["status"],"malformed_rss")
        self.assertEqual(h["futurePubDateRows"],1)

    def test_valid_but_old_article_and_empty_rss_are_not_failures(self):
        old=format_datetime(datetime.now(KST)-timedelta(days=30))
        self.assertEqual(self.run_feed([
            ("현대차 지난달",old,"https://news.example/old","매체")]),[])
        self.assertEqual(NAMESPACE["FEED_CHECKS"][-1]["status"],
                         "checked_no_recent_rows")
        self.assertEqual(self.run_feed([]),[])
        self.assertEqual(NAMESPACE["FEED_CHECKS"][-1]["status"],
                         "checked_no_recent_rows")

    def test_sports_homonym_still_filtered(self):
        dt=format_datetime(datetime.now(KST)-timedelta(minutes=20))
        rows=self.run_feed([
            ("현대모비스 피버스 승리",dt,"https://news.example/basketball","스포츠매체"),
            ("현대모비스 전동화 공장 증설",dt,"https://news.example/factory","산업매체")])
        self.assertEqual(len(rows),1)
        self.assertIn("공장",rows[0]["title"])

    def test_keep_distinct_publishers_and_different_hyphen_content(self):
        t="현대차-기아 새 계약"
        data=[
            {"title":t+" - 한국경제","sourceName":"한국경제","published":"2026-10-19T20:04:00+09:00"},
            {"title":t+" - 매일경제","sourceName":"매일경제","published":"2026-10-19T20:03:00+09:00"},
            {"title":t+" - 한국경제","sourceName":"한국경제","published":"2026-10-19T20:02:00+09:00"},
            {"title":"현대차-포스코 새 계약 - 한국경제","sourceName":"한국경제",
             "published":"2026-10-19T20:01:00+09:00"}]
        out=dedupe(data)
        self.assertEqual(len(out),3)
        self.assertEqual({x["sourceName"] for x in out},{"한국경제","매일경제"})
        self.assertNotEqual(normalize_title(t),normalize_title("현대차-포스코 새 계약"))


if __name__=="__main__":
    unittest.main()
