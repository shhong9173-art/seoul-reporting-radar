import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import patent_story_hunt as h

KST=timezone(timedelta(hours=9))
NOW=datetime(2026,10,13,9,0,tzinfo=KST)


def example(pub="1020260147319", title="효소 재활용 기술 연구",
            outsiders=True,date="20261008", abstract="플라스틱 부품을 효소로 분해한다."):
    owners=["현대자동차주식회사","기아 주식회사"]
    if outsiders:
        owners+=["씨제이제일제당 (주)","경북대학교 산학협력단"]
    return {
        "company":"현대자동차","publicationNumber":pub,
        "applicationNumber":"1020250041823","publicationDate":date,
        "applicationDate":"20250331","title":title,
        "abstract":abstract,"applicants":owners,
        "themes":[],"freshObservation":False,"historicalBackfill":False,
    }


def sources(rows):
    official={"generatedAt":"2026-10-13T08:30:00+09:00",
              "reportingWindow":"20260908~20261013",
              "sourceWindowComplete":True,
              "unclassifiedCount":len(rows),"items":rows}
    deep={"generatedAt":"2026-10-13T08:33:00+09:00",
          "patentDatasetGeneratedAt":official["generatedAt"],"investigations":[]}
    return official,deep


class PatentStoryTests(unittest.TestCase):
    def test_realistic_cj_style_partner_is_found_without_old_topic_tags(self):
        a,b=sources([example()])
        result=h.build(a,b,now=NOW,max_news=0)
        self.assertEqual(result["allVerifiedPublications"],1)
        self.assertEqual(result["outsidePartnerLeads"],1)
        lead=result["investigations"][0]
        self.assertEqual(lead["topic"],"순환소재·폐차재활용")
        self.assertIn("씨제이제일제당",lead["reportingTitleDraft"])
        self.assertEqual(lead["sourceAbstractExcerpt"],"플라스틱 부품을 효소로 분해한다.")
        self.assertFalse(lead["scoopConfirmed"])

    def test_unknown_patent_kept_and_cross_sector_analysis_still_happens(self):
        a,b=sources([example(title="형상 기억 탄성 구조체",abstract="극저온에서 구동력을 전달하는 구조체")])
        result=h.build(a,b,now=NOW,max_news=0)
        lead=result["investigations"][0]
        self.assertEqual(lead["topic"],"미분류·이종산업 탐색")
        self.assertEqual(lead["topicDetectionSource"],"키워드 매칭 없음")
        self.assertIn("미확인",lead["status"])

    def test_date_and_backfill_not_mistaken_for_new_disclosure(self):
        row=example(date="20260914")
        row["historicalBackfill"]=True
        a,b=sources([row])
        lead=h.build(a,b,now=NOW,max_news=0)["investigations"][0]
        self.assertFalse(lead["recentPublication"])
        self.assertTrue(lead["historicalBackfill"])
        self.assertGreater(lead["daysSincePublic"],14)

    def test_recent_non_partner_patent_can_be_selected(self):
        row=example(outsiders=False,date="20261012",title="차량 제어 장치 및 방법")
        a,b=sources([row])
        result=h.build(a,b,now=NOW,max_news=0)
        self.assertEqual(result["outsidePartnerLeads"],0)
        self.assertEqual(len(result["investigations"]),1)

    def test_same_publication_two_beat_names_yields_one_story(self):
        row=example()
        a,b=sources([row,{**row,"company":"기아"}])
        result=h.build(a,b,now=NOW,max_news=0)
        self.assertEqual(result["allVerifiedPublications"],1)
        self.assertEqual(len(result["investigations"]),1)
        self.assertEqual(result["outsidePartnerLeads"],1)

    def test_news_rss_search_has_explicit_unknown_when_zero(self):
        urls=[]
        def empty(url):
            urls.append(url)
            return b"<rss><channel/></rss>"
        result=h.search_press(example(),fetch=empty)
        self.assertFalse(result["possibleEarlierCoverage"])
        self.assertTrue(result["completeSearch"])
        self.assertIn("미보도 증명 아님",result["status"])
        self.assertGreaterEqual(len(urls),1)
        self.assertIn("1020260147319",parse_qs(urlparse(urls[0]).query)["q"][0])

    def test_relevant_media_hit_raises_review_flag_not_confirmed_duplicate(self):
        result=h.search_press(example(),fetch=lambda url:
            b'<rss><channel><item><title>Company coverage</title><link>https://news.google.com/rss/articles/123</link></item></channel></rss>')
        self.assertTrue(result["possibleEarlierCoverage"])
        self.assertFalse(result["scoopConfirmed"])
        self.assertIn("대조",result["status"])

    def test_malformed_rss_is_error_not_zero_coverage(self):
        r=h.search_press(example(),fetch=lambda _:b"<html></html>")
        self.assertFalse(r["completeSearch"])
        self.assertIn("미확인",r["status"])

    def test_source_timestamp_mismatch_is_hard_error(self):
        a,b=sources([example()])
        b["patentDatasetGeneratedAt"]="2025-01-01"
        with self.assertRaises(ValueError):
            h.build(a,b,now=NOW,max_news=0)

    def test_news_queries_limited_to_high_priority(self):
        rows=[example(pub=f"102026014{i:04d}",date="20261012")
              for i in range(12)]
        a,b=sources(rows)
        called=[]
        def fake(row):
            called.append(row["publicationNumber"])
            return {"status":"미확인","queries":[],"possibleEarlierCoverage":False}
        result=h.build(a,b,now=NOW,max_news=3,press=fake)
        self.assertEqual(len(called),3)
        self.assertEqual(len(result["investigations"]),12)


if __name__=="__main__":
    unittest.main()
