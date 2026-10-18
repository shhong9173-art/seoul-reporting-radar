import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timedelta, timezone

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.official_publication_date_guard import resurfaced_historical_original
from pre_scoop_radar import parse_feed

KST=timezone(timedelta(hours=9))
NOW=datetime(2026,10,18,22,0,tzinfo=KST)


class DateAuthority(unittest.TestCase):
    def test_2015_original_is_not_2026_new_notice(self):
        title="2015년도 한국전력기술(주) 녹색제품 구매계획 공지 | 경영공시"
        self.assertTrue(resurfaced_historical_original(title,NOW))
        self.assertTrue(resurfaced_historical_original(title,
            datetime(2026,10,13,8,57,tzinfo=KST)))

    def test_recent_true_annual_report_not_dropped(self):
        self.assertFalse(resurfaced_historical_original(
            "2026년도 한국전력기술 녹색제품 구매계획 공고",NOW))
        self.assertFalse(resurfaced_historical_original(
            "2025년도 한국전력기술 녹색제품 구매계획 공고",NOW))

    def test_retrospective_current_reporting_is_preserved(self):
        self.assertFalse(resurfaced_historical_original(
            "현대차 2015년 신차 전략, 2026년과 다른 점",NOW))
        self.assertFalse(resurfaced_historical_original(
            "현대차, 2015년도 사업계획과 달라진 정책 비교 분석",NOW))

    def test_failed_or_naive_dates_do_not_create_false_date_claim(self):
        self.assertFalse(resurfaced_historical_original(
            "2015년도 한국전력기술 녹색제품 구매계획",None))
        self.assertFalse(resurfaced_historical_original(
            "2015년도 한국전력기술 녹색제품 구매계획",
            datetime(2026,10,18)))

    def test_actual_rss_parser_excludes_historical_document_and_keeps_new(self):
        root=ET.Element("rss"); channel=ET.SubElement(root,"channel")
        def item(title):
            x=ET.SubElement(channel,"item")
            ET.SubElement(x,"title").text=title
            ET.SubElement(x,"link").text="https://www.kepco-enc.com/example"
            ET.SubElement(x,"pubDate").text="Sun, 18 Oct 2026 08:00:00 +0900"
            ET.SubElement(x,"description").text="한국전력기술 녹색제품 구매계획"
        item("2015년도 한국전력기술 녹색제품 구매계획 공지")
        item("2026년도 한국전력기술 녹색제품 구매계획 공지")
        diag={}
        found=parse_feed(root,"kepco-enc.com","공기업·조달",NOW,diag)
        self.assertEqual(diag.get("rssRejectHistoricalOriginalResurfaced"),1)
        self.assertEqual(len(found),1)
        self.assertIn("2026년도",found[0]["title"])
        self.assertEqual(found[0]["published"][:10],"2026-10-18")

if __name__=="__main__":
    unittest.main()
