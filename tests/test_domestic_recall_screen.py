import sys,unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import domestic_recall_screen as s
NOW=datetime(2026,10,16,10,0,tzinfo=timezone(timedelta(hours=9)))
def source():
    return {"status":"official_us_recalls_to_review","generatedAt":"2026-10-16T09:00:00+09:00",
            "confirmedScoops":0,"leads":[{"id":x,"usRecallExists":True,
              "koreanRecallChecked":False,"exclusiveConfirmed":False}
              for x in ("26V664000","26V588000")]}
def web(title):
    return ("<h1>리콜현황</h1><p>국토교통부</p>"
       "<a href='/ri/stat/view.do?x=123'>"+title+"</a>").encode()
class SafeIndex(unittest.TestCase):
    def test_title_not_exact_component(self):
        self.assertEqual(len(s.parse_official(web("[현대] G80 시트 관련 리콜"),"G80")),1)
        self.assertEqual(s.parse_official(web("[현대] G80 시트 관련 리콜"),"아이오닉9"),[])
    def test_untrusted_page_and_link_rejected(self):
        with self.assertRaises(ValueError):s.parse_official(b"unknown","G80")
        html=("<h1>리콜현황 국토교통부</h1>"
              "<a href='https://evil.example/ri/stat/view.do'>G80 관련 리콜</a>")
        self.assertEqual(s.parse_official(html.encode(),"G80"),[])
    def test_empty_index_not_no_recall_or_no_news(self):
        d=s.scan(source(),now=NOW,fetch=lambda url:(
          web("[다른회사] BMW 관련 리콜") if "car.go.kr" in url
          else b"<rss><channel></channel></rss>"))
        self.assertEqual(d["requestsAttempted"],5)
        self.assertEqual(d["confirmedScoops"],0)
        for x in d["items"]:
            self.assertFalse(x["domesticRecallAbsenceVerified"])
            self.assertFalse(x["sameAnglePressFulltextVerified"])
            self.assertFalse(x["press"]["pressAbsenceVerified"])
            for q in x["officialQueries"]:
                self.assertFalse(q["recallAbsenceVerified"])
                self.assertFalse(q["searchFilterVerified"])
                self.assertFalse(q["exactPartVerified"])
    def test_network_failure_not_empty_official_evidence(self):
        def fail(url):raise TimeoutError()
        d=s.scan(source(),now=NOW,fetch=fail)
        self.assertEqual(d["items"][0]["officialQueries"][0]["status"],
                         "public_page_unavailable_or_unparsed")
        self.assertFalse(d["items"][0]["domesticRecallAbsenceVerified"])
    def test_news_headline_only(self):
        xml=("<rss><channel><item><title>G80 recall - publisher</title>"
             "<link>https://news.google.com/rss/articles/123</link>"
             "<pubDate>Thu, 15 Oct 2026 00:00:00 GMT</pubDate>"
             "</item></channel></rss>").encode()
        r=s.parse_news(xml,NOW,"26V664000")
        self.assertEqual(len(r),1)
        self.assertFalse(r[0]["fulltextRead"])
        self.assertFalse(r[0]["sameIssueVerified"])
    def test_g80_news_excludes_ioniq_and_gv80_unrelated_article(self):
        self.assertFalse(s.relevant_news_title("아이오닉 9 시트 리콜","26V664000"))
        self.assertFalse(s.relevant_news_title("제네시스 GV80 CEO 의전차","26V664000"))
        self.assertFalse(s.relevant_news_title("2020년식 제네시스 GV80 고압연료펌프 리콜","26V664000"))
        self.assertTrue(s.relevant_news_title("현대 제네시스 시트 스위치 과열 신고","26V664000"))
        self.assertTrue(s.relevant_news_title("제네시스 G80 시트 스위치 리콜","26V664000"))
        self.assertFalse(s.relevant_news_title("제네시스 G80 시트 리콜","26V588000"))
        self.assertTrue(s.relevant_news_title("아이오닉 9 전동시트 국내 리콜","26V588000"))
        unrelated=("<rss><channel><item><title>아이오닉 9 시트 리콜</title>"
            "<link>https://news.google.com/rss/articles/123</link>"
            "<pubDate>Thu, 15 Oct 2026 00:00:00 GMT</pubDate>"
            "</item></channel></rss>").encode()
        self.assertEqual(s.parse_news(unrelated,NOW,"26V664000"),[])
        self.assertEqual(len(s.parse_news(unrelated,NOW,"26V588000")),1)

    def test_foreign_campaign_not_automatically_extended(self):
        c=source();c["leads"]=[{"id":"26V999000","usRecallExists":True,
           "koreanRecallChecked":False,"exclusiveConfirmed":False}]
        self.assertEqual(s.scan(c,now=NOW,fetch=lambda u:b"")["requestsAttempted"],0)
        c["confirmedScoops"]=1
        with self.assertRaises(ValueError):s.scan(c,now=NOW,fetch=lambda u:b"")
if __name__=="__main__":unittest.main()
