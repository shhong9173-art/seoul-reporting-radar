"""Offline tests for production collector without executing its network main."""
import ast
import html
import re
import sys
import time
import unittest
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime,timedelta
from email.utils import format_datetime,parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT=Path(__file__).resolve().parents[1]
TREE=ast.parse((ROOT/"collector.py").read_text(encoding="utf-8"))
FUNS={"norm_title","dedupe","parse_feed"}
SCRIPTS=[n for n in TREE.body if isinstance(n,ast.FunctionDef) and n.name in FUNS]
assert len(SCRIPTS)==3
# The module's batch collector performs live HTTP calls at import; compile ONLY
# the exact unchanged production parser/dedupe functions for deterministic CI.
NAMESPACE={
 "re":re,"html":html,"time":time,"urllib":urllib,"ET":ET,
 "datetime":datetime,"timedelta":timedelta,"ZoneInfo":ZoneInfo,
 "parsedate_to_datetime":parsedate_to_datetime,"KST":ZoneInfo("Asia/Seoul"),
 "FEED_CHECKS":[],
 "AUTO_SCOOP_RE":re.compile("현대모비스|현대차|기아|자동차"),
 "SPORTS_NOISE_RE":re.compile(
   r"KIA\s*타이거즈|기아\s*타이거즈|현대모비스\s*(?:피버스|농구단|농구)\b|"
   r"프로야구|프로농구|KBO\b|KBL\b|배구단|야구단",re.I),
 "clean":lambda x:re.sub(r"<[^>]*>"," ",x),
}
exec(compile(ast.Module(body=SCRIPTS,type_ignores=[]),
             str(ROOT/"collector.py"),"exec"),NAMESPACE)
norm_title=NAMESPACE["norm_title"]
dedupe=NAMESPACE["dedupe"]
parse_feed=NAMESPACE["parse_feed"]


class DomesticArticleIdentity(unittest.TestCase):
    def test_meaningful_hyphen_and_pipe_are_not_cut(self):
        self.assertEqual(norm_title("포스코-현대제철 수급 달라졌다"),
                         "포스코-현대제철 수급 달라졌다")
        self.assertEqual(norm_title("기아 | 현대모비스 전동화 협업"),
                         "기아 | 현대모비스 전동화 협업")
        self.assertNotEqual(norm_title("현대차-기아 공동 투자"),
                            norm_title("현대차-포스코 공동 투자"))

    def test_only_same_publisher_suffix_is_removed(self):
        self.assertEqual(norm_title("현대차-기아 첫 공동 계약 - 한국경제","한국경제"),
                         "현대차-기아 첫 공동 계약")
        self.assertEqual(norm_title("현대차-기아 첫 공동 계약 - 다른경제지","한국경제"),
                         "현대차-기아 첫 공동 계약 - 다른경제지")

    def test_distinct_publishers_are_retained_for_prior_coverage(self):
        data=[
          {"title":"현대제철-포스코 계약 - 한국경제",
           "sourceName":"한국경제","published":"2026-10-18T08:00:00+09:00"},
          {"title":"현대제철-포스코 계약 - 매일경제",
           "sourceName":"매일경제","published":"2026-10-18T08:01:00+09:00"},
          {"title":"현대제철-포스코 계약 - 한국경제",
           "sourceName":"한국경제","published":"2026-10-18T08:02:00+09:00"},
          {"title":"현대제철-현대차 계약 - 한국경제",
           "sourceName":"한국경제","published":"2026-10-18T08:03:00+09:00"},
        ]
        self.assertEqual(len(dedupe(data)),3)

    def test_undated_google_rss_not_rewritten_as_published_today(self):
        time_now=datetime.now(ZoneInfo("Asia/Seoul"))-timedelta(hours=1)
        good=format_datetime(time_now)
        rss=("<rss><channel>"+
           "<item><title>현대자동차 공장 투자</title><link>https://example.com/1</link>"+
           "<pubDate>broken date</pubDate></item>"+
           "<item><title>현대자동차 공장 증설</title><link>https://example.com/2</link>"+
           "<pubDate>"+good+"</pubDate></item>"+
           "</channel></rss>").encode("utf-8")
        NAMESPACE["get"]=lambda u:rss
        out=parse_feed("완성차","현대차")
        self.assertEqual(len(out),1)
        self.assertIn("증설",out[0]["title"])
        self.assertEqual(NAMESPACE["FEED_CHECKS"][-1]["invalidPubDateRows"],1)

    def test_sport_team_headlines_not_labeled_vehicle_scoops(self):
        good=format_datetime(datetime.now(ZoneInfo("Asia/Seoul"))-timedelta(hours=1))
        rss=("<rss><channel>"+
           "<item><title>[단독] 현대모비스 농구단 감독 선임</title>"+
           "<link>https://example.com/1</link><pubDate>"+good+"</pubDate></item>"+
           "<item><title>[단독] 현대모비스 공장 생산 설비 투자</title>"+
           "<link>https://example.com/2</link><pubDate>"+good+"</pubDate></item>"+
           "</channel></rss>").encode("utf-8")
        NAMESPACE["get"]=lambda _:rss
        out=parse_feed("단독","현대모비스 단독")
        self.assertEqual(len(out),1)
        self.assertIn("공장",out[0]["title"])


if __name__=="__main__":
    unittest.main()
