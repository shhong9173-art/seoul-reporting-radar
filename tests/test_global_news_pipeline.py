"""Offline checks for global RSS source-first duplicate and translator reuse."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from global_news_pipeline import shortlist,translate_selected


def item(title,url,score=70,published="2026-10-16T09:00:00+09:00",summary="Original context"):
    return {"title":title,"url":url,"globalScore":score,"published":published,"summary":summary}


class GlobalNewsPipelineTests(unittest.TestCase):
    def test_headline_deduplication_before_translation_and_score_cap(self):
        raw=[
          item(" EV   tariff news ","https://news.example/a",score=90,published="2026-10-16T06:00:00+09:00"),
          item("ev tariff news","https://news.example/a",score=90,published="2026-10-16T08:00:00+09:00"),
          item("Hyundai US plant","https://news.example/b",score=70),
          item("Battery deal","https://news.example/c",score=85)
        ]
        ordered=shortlist(raw,limit=2)
        self.assertEqual([x["title"] for x in ordered],["ev tariff news","Battery deal"])
        self.assertEqual(len(ordered),2)

    def test_reuse_requires_full_article_text_url_identity(self):
        old=item("Korean EV signal","https://news.example/a")
        old.update({"koTitle":"한국 전기차 신호","koSummary":"기존 요약",
                    "translationStatus":"translated","summaryTranslationStatus":"translated"})
        fresh=item("Korean EV signal","https://news.example/a")
        called=[]
        def translator(t):
            called.append(t)
            return ("번역한 "+t,"translated")
        reuse=translate_selected([fresh],translator,previous=[old],workers=2)
        self.assertEqual(reuse[0]["koTitle"],"한국 전기차 신호")
        self.assertTrue(reuse[0]["translationCacheUsed"])
        self.assertEqual(called,[])
        changed=item("Korean EV signal","https://news.example/a",summary="Changed context")
        result=translate_selected([changed],translator,previous=[old],workers=2)
        self.assertFalse(result[0]["translationCacheUsed"])
        self.assertEqual(len(called),2)

    def test_translate_only_shortlisted_rows_and_no_fake_translation(self):
        rows=[item("Title "+str(i),"https://news.example/"+str(i),score=i) for i in range(14)]
        selected=shortlist(rows,limit=3)
        called=[]
        def translator(t):
            called.append(t)
            return ("한국어 제목","translated")
        translated=translate_selected(selected,translator,previous=[],workers=2)
        self.assertEqual(len(translated),3)
        self.assertEqual(len(called),6)
        self.assertEqual([x["title"] for x in translated],[x["title"] for x in selected])

    def test_failed_title_skipped_and_summary_failure_explicit(self):
        rows=[item("Untranslatable","https://news.example/0"),
              item("Valid title","https://news.example/1")]
        def translator(t):
            if t=="Untranslatable":return ("Untranslatable","translation_failed")
            if t=="Original context":return ("Original context","translation_failed")
            return ("유효한 제목","translated")
        result=translate_selected(rows,translator,workers=1)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]["koSummary"],"")
        self.assertEqual(result[0]["summaryTranslationStatus"],"translation_failed")
        self.assertEqual(result[0]["translationStatus"],"translated")

    def test_bad_budget_rejected(self):
        with self.assertRaises(ValueError):shortlist([],limit=100)
        with self.assertRaises(ValueError):
            translate_selected([],lambda s:(s,"already_ko"),workers=15)


if __name__=="__main__":
    unittest.main()
