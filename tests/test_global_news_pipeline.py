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


sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import global_collector as gc  # noqa: E402


class GlobalCollectorBeatTests(unittest.TestCase):
    """11-01 기자 요청: 출입처(철강·전력기기·에너지·화학·타이어) 외신, 국내 매체 영문판 제외, 제목뿐인 설명은 요약으로 번역하지 않음."""

    def test_word_boundaries_not_substrings(self):
        self.assertEqual(gc.hits(gc.INDUSTRY_RE, "every business needs less seven"), 0)       # ev·ess 부분 문자열 아님
        self.assertEqual(gc.hits(gc.KOREA_RE, "social media associated"), 0)                 # oci 아님
        self.assertGreaterEqual(gc.hits(gc.INDUSTRY_RE, "korea zinc smelter expands ev battery"), 3)
        self.assertGreaterEqual(gc.hits(gc.KOREA_RE, "hyosung heavy industries wins transformer order"), 1)

    def test_domestic_english_outlets_are_excluded(self):
        for name in ("The Korea Herald", "Yonhap News Agency", "KED Global", "BusinessKorea", "Korea JoongAng Daily", "The Elec"):
            self.assertTrue(gc.DOMESTIC_EN.search(name), name)
        for name in ("Reuters", "Bloomberg", "Nikkei Asia", "Financial Times", "Utility Dive"):
            self.assertFalse(gc.DOMESTIC_EN.search(name), name)

    def test_beat_search_keeps_only_foreign_outlets(self):
        for name in ("Reuters", "Bloomberg.com", "Nikkei Asia", "Financial Times", "Fastmarkets", "MINING.COM", "Utility Dive", "pv magazine"):
            self.assertTrue(gc.FOREIGN_OK.search(name), name)
        for name in ("BigGo Finance", "TradingView", "Yahoo Finance", "WBRZ", "UA.NEWS", "헤럴드경제"):
            self.assertFalse(gc.FOREIGN_OK.search(name), name)

    def test_title_only_google_news_description(self):
        t = "Korea Zinc starts US smelter study - Reuters"
        self.assertTrue(gc.title_only("Korea Zinc starts US smelter study Reuters", t))
        self.assertTrue(gc.title_only("", t))
        self.assertFalse(gc.title_only("The company said on Monday it would spend $7.4 billion on a smelter in Tennessee, its first outside Korea.", t))

    def test_beat_queries_cover_non_auto_beats(self):
        q = " ".join(x[1] for x in gc.QUERIES)
        for name in ("Hyundai Steel", "Korea Zinc", "LS Electric", "HD Hyundai Electric", "LS Cable", "Hanwha Qcells", "GS Caltex", "Hankook Tire"):
            self.assertIn(name, q)

    def test_worker_ai_translation_first_then_fallbacks(self):
        import os
        calls = []
        orig_post, orig_get = gc.worker_translate, gc.get
        try:
            gc.worker_translate = lambda t: (calls.append(("ai", t)) or "고려아연, 미국 제련소 검토 착수")
            self.assertEqual(gc.translate("Korea Zinc starts US smelter study"), ("고려아연, 미국 제련소 검토 착수", "translated_ai"))
            gc.worker_translate = lambda t: ""   # 워커 실패 → 구글 → 보조
            def fake_get(url, timeout=15):
                if "googleapis" in url:
                    raise OSError("blocked")
                return '{"responseData":{"translatedText":"보조 번역"}}'.encode()
            gc.get = fake_get
            orig_sleep, gc.time.sleep = gc.time.sleep, (lambda s: None)
            try:
                self.assertEqual(gc.translate("Korea Zinc starts US smelter study"), ("보조 번역", "translated_fallback"))
            finally:
                gc.time.sleep = orig_sleep
        finally:
            gc.worker_translate, gc.get = orig_post, orig_get
        self.assertEqual(calls, [("ai", "Korea Zinc starts US smelter study")])
        os.environ.pop("MCP_ACCESS_TOKEN", None)
        self.assertEqual(gc.worker_translate("x"), "")   # 토큰 없으면 워커를 부르지 않는다

    def test_ai_translation_is_reused_from_cache(self):
        old=item("Korean EV signal","https://news.example/a",summary="")
        old.update({"koTitle":"한국 전기차 신호","koSummary":"","translationStatus":"translated_ai"})
        out=translate_selected([item("Korean EV signal","https://news.example/a",summary="")],lambda t:("다시","translated"),previous=[old],workers=1)
        self.assertEqual((out[0]["koTitle"],out[0]["translationCacheUsed"]),("한국 전기차 신호",True))

    def test_fallback_translation_is_not_reused_and_empty_summary_not_translated(self):
        old=item("Korean EV signal","https://news.example/a",summary="")
        old.update({"koTitle":"보조 번역","koSummary":"","translationStatus":"translated_fallback"})
        called=[]
        def translator(t):
            called.append(t)
            return ("한국 전기차 신호","translated")
        out=translate_selected([item("Korean EV signal","https://news.example/a",summary="")],translator,previous=[old],workers=1)
        self.assertEqual((out[0]["koTitle"],out[0]["translationStatus"],out[0]["koSummary"],out[0]["summaryTranslationStatus"]),
                         ("한국 전기차 신호","translated","","no_summary"))
        self.assertEqual(called,["Korean EV signal"])


if __name__=="__main__":
    unittest.main()
