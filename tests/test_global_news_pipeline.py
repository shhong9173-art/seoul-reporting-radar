"""Offline checks for global RSS source-first duplicate and translator reuse."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from global_news_pipeline import AI_TRANSLATION_VERSION,shortlist,summarize_selected,translate_selected


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

    def test_one_fixed_request_name_no_retry_with_another(self):
        import inspect
        src=inspect.getsource(gc)
        self.assertNotIn("FEED_UA",src)
        self.assertEqual(list(inspect.signature(gc.get).parameters),["url","timeout"])   # 요청 이름을 바꿀 수 있는 인자 없음

    def test_beat_trade_press_feeds_require_korean_mention(self):
        names={n for n,_ in gc.PUBLISHER_FEEDS}
        for n in ("GMK Center","World Nuclear News","offshoreWIND.biz","PV Tech","Tire Business","Transformers Magazine"):
            self.assertIn(n,names); self.assertIn(n,gc.STRICT_KOREA)
        self.assertNotIn("Automotive News Europe",gc.STRICT_KOREA)   # 자동차 매체는 자동차 기준 그대로
        self.assertGreaterEqual(gc.hits(gc.INDUSTRY_RE,"ls cable wins hvdc subsea cable order for offshore wind"),3)

    def test_beat_companies_direct_list_only(self):
        f=gc.beat_companies
        self.assertEqual(f("Doosan to manufacture upper reactor vessel for NuScale SMR"),["두산에너빌리티"])
        self.assertEqual(f("Doosan Bobcat posts record sales"),[])
        self.assertEqual(f("POSCO Future M signs cathode deal"),[])                       # 포스코퓨처엠은 포스코 아님
        self.assertEqual(f("POSCO Holdings and Hyundai Steel weigh US mill"),["포스코홀딩스","현대제철"])
        self.assertEqual(f("HD Hyundai Heavy wins LNG carrier order"),[])                 # HD현대중공업 아님
        self.assertEqual(f("Hyundai Engineering agrees to cooperate with US SMR developers"),[])
        self.assertEqual(f("Hyundai to invest US$450m in Alabama plant; Kia recalls EV9"),["현대차","기아"])
        self.assertEqual(f("HD Hyundai Electric wins transformer order"),["HD현대일렉트릭"])
        self.assertEqual(f("LS Cable and Taihan bid for HVDC link; Q Cells expands Georgia"),["LS전선","대한전선","한화솔루션"])
        self.assertEqual(f("Social impact of associated costs"),[])                        # oci 부분 일치 아님

    def test_check_terms_from_korean_title(self):
        self.assertEqual(gc.check_terms("두산, 뉴스케일 소형모듈원전 상부 원자로 용기 제작",["두산에너빌리티"]),["원자로"])
        self.assertEqual(gc.check_terms("현대차, 4억5천만달러 앨라배마 공장 투자해 신형 투싼 생산",["현대차"]),["공장","투자"])
        self.assertEqual(gc.check_terms("넥센타이어, 에코바디스 골드 3년 연속",["넥센타이어"]),[])          # 회사 이름에 든 '타이어'는 안 씀
        self.assertEqual(gc.check_terms("현대차, 영국서 신형 아이오닉 6 가격 공개",["현대차"]),[])

    def test_push_beat_sends_only_beat_items(self):
        import os, types, sys as _sys
        sent=[]
        fake=types.SimpleNamespace(put=lambda name,doc,token,post=None,get=None: sent.append((name,doc,token,post)) or 200)
        os.environ["MCP_ACCESS_TOKEN"]="t"*20
        _sys.modules["scripts.private_store"]=fake
        import scripts
        orig=getattr(scripts,"private_store",None)
        scripts.private_store=fake
        try:
            rows=[{**item("Doosan wins SMR vessel order","https://w/a"),"beatCompanies":["두산에너빌리티"],"checkTerms":["원자로"],"koTitle":"두산, SMR 용기 수주","firstSeen":"2026-11-01T09:00:00+09:00"},
                  {**item("CATL opens plant","https://w/b"),"beatCompanies":[]}]
            gc.push_beat(rows,"2026-11-01T09:00:00+09:00")
        finally:
            os.environ.pop("MCP_ACCESS_TOKEN",None)
            if orig is not None: scripts.private_store=orig
            _sys.modules.pop("scripts.private_store",None)
        self.assertEqual(len(sent),1)
        name,doc,_,post=sent[0]
        self.assertTrue(callable(post))   # requests 없이 표준 라이브러리로 보낸다
        self.assertEqual((name,doc["schema"],[x["url"] for x in doc["items"]]),("global-beat","global_beat/v1",["https://w/a"]))
        self.assertTrue(doc["items"][0]["id"].startswith("gl:"))
        self.assertEqual(doc["items"][0]["checkTerms"],["원자로"])

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
        sent = []
        orig_post = gc.worker_translate
        try:
            gc.worker_translate = lambda t: (sent.append(t) or "번역")
            gc.translate("Three in a row – Nexen Tire receives EcoVadis Gold medal")
        finally:
            gc.worker_translate = orig_post
        # 번역기에는 제목을 자르지 않고 보낸다(11-01 운영: ' – 뒤 글'을 떼서 '3연패'만 번역됐다). 매체 이름은 수집 때 뗀다.
        self.assertEqual(sent, ["Three in a row – Nexen Tire receives EcoVadis Gold medal"])
        os.environ.pop("MCP_ACCESS_TOKEN", None)
        self.assertEqual(gc.worker_translate("x"), "")   # 토큰 없으면 워커를 부르지 않는다

    def test_ai_translation_is_reused_from_cache(self):
        old=item("Korean EV signal","https://news.example/a",summary="")
        old.update({"koTitle":"한국 전기차 신호","koSummary":"","translationStatus":"translated_ai","translationVersion":AI_TRANSLATION_VERSION})
        out=translate_selected([item("Korean EV signal","https://news.example/a",summary="")],lambda t:("다시","translated_ai"),previous=[old],workers=1)
        self.assertEqual((out[0]["koTitle"],out[0]["translationCacheUsed"]),("한국 전기차 신호",True))
        old.pop("translationVersion")   # 예전 규칙(v1) AI 번역은 다시 번역
        out=translate_selected([item("Korean EV signal","https://news.example/a",summary="")],lambda t:("다시","translated_ai"),previous=[old],workers=1)
        self.assertEqual((out[0]["koTitle"],out[0]["translationCacheUsed"],out[0]["translationVersion"]),("다시",False,AI_TRANSLATION_VERSION))

    def test_source_suffix_removed_only_when_it_is_the_outlet_name(self):
        s=gc.strip_source_suffix
        self.assertEqual(s("Hyundai to invest US$450m in Alabama plant for new Tucson - Automotive World","Automotive World"),
                         "Hyundai to invest US$450m in Alabama plant for new Tucson")
        self.assertEqual(s("Three in a row – Nexen Tire receives EcoVadis Gold medal - Tyrepress","Tyrepress"),
                         "Three in a row – Nexen Tire receives EcoVadis Gold medal")
        self.assertEqual(s("Three in a row – Nexen Tire receives EcoVadis Gold medal","Tyrepress"),
                         "Three in a row – Nexen Tire receives EcoVadis Gold medal")   # 매체 RSS 제목은 그대로
        self.assertEqual(s("Korea Zinc – the smelter bet | Reuters","Reuters"),"Korea Zinc – the smelter bet")
        self.assertEqual(s("‘Cannot Give Up’: Hyundai’s R&D Boss On The Solid-State Battery Bet - InsideEVs","InsideEVs"),
                         "‘Cannot Give Up’: Hyundai’s R&D Boss On The Solid-State Battery Bet")
        self.assertEqual(s("Doosan wins order - Korea's big week","Reuters"),"Doosan wins order - Korea's big week")   # 매체 이름이 아니면 안 뗀다
        self.assertEqual(s("Doosan wins order - Reuters",""),"Doosan wins order - Reuters")

    def test_google_rows_drop_outlet_suffix_and_match_publisher_rss(self):
        import datetime as _dt
        now=_dt.datetime.now(gc.KST).strftime("%a, %d %b %Y %H:%M:%S +0900")
        xml=("<rss><channel>"
             f"<item><title>Three in a row – Nexen Tire receives EcoVadis Gold medal - Tyrepress</title><link>https://news.google.com/rss/articles/n</link>"
             f"<pubDate>{now}</pubDate><description>Nexen Tire tyre sustainability rating</description><source url=\"https://www.tyrepress.com\">Tyrepress</source></item>"
             "</channel></rss>").encode()
        orig=gc.get
        try:
            gc.get=lambda url,timeout=15: xml
            g=gc.parse("타이어","Nexen Tire")
        finally:
            gc.get=orig
        self.assertEqual([r["title"] for r in g],["Three in a row – Nexen Tire receives EcoVadis Gold medal"])
        p=[{**item("Three in a row – Nexen Tire receives EcoVadis Gold medal","https://www.tyrepress.com/2026/10/three-in-a-row/",summary=""),
            "articleText":"Nexen Tire has been awarded …","summarySource":"Tyrepress RSS"}]
        out=gc.attach_publisher_text(g,p)
        self.assertEqual([x["url"] for x in out],["https://www.tyrepress.com/2026/10/three-in-a-row/"])   # 같은 기사를 두 번 올리지 않는다

    def test_publisher_rss_text_attaches_to_google_rows_and_direct_url(self):
        g=[item("Hyundai to invest US$450m in Alabama plant for new Tucson","https://news.google.com/rss/articles/x",summary="")]
        p=[{**item("Hyundai to invest US$450m in Alabama plant for new Tucson","https://www.automotiveworld.com/news/hyundai-tucson/",summary=""),
            "articleText":"Hyundai Motor Manufacturing Alabama will invest US$450m ...","summarySource":"Automotive World RSS"},
           {**item("CATL opens Hungary plant","https://cnevpost.com/catl-hungary/",summary=""),"articleText":"CATL said ...","summarySource":"CnEVPost RSS"}]
        out=gc.attach_publisher_text(g,p)
        self.assertEqual(len(out),2)
        self.assertEqual((out[0]["url"],out[0]["summarySource"]),("https://www.automotiveworld.com/news/hyundai-tucson/","Automotive World RSS"))
        self.assertIn("invest US$450m",out[0]["articleText"])
        self.assertEqual(out[1]["url"],"https://cnevpost.com/catl-hungary/")   # 구글 뉴스에 없던 매체 기사도 후보로

    def test_summaries_only_from_article_text_cached_and_english_text_dropped(self):
        rows=[{**item("A","https://e/a",summary=""),"articleText":"Body A text."},{**item("B","https://e/b",summary=""),"articleText":""}]
        calls=[]
        def summarizer(title,text):
            calls.append((title,text))
            return "현대차가 앨라배마 공장에 4억5000만달러를 투자한다."
        out=summarize_selected(rows,summarizer,previous=[],workers=1)
        self.assertEqual(calls,[("A","Body A text.")])                          # 본문 없는 항목은 요약하지 않는다
        self.assertEqual((out[0]["summaryTranslationStatus"],out[0]["summaryVersion"]),("summarized_ai",1))
        self.assertNotIn("articleText",out[0]); self.assertNotIn("articleText",out[1])   # 영어 본문은 저장하지 않는다
        self.assertFalse(out[1].get("koSummary"))
        again=summarize_selected([{**item("A","https://e/a",summary=""),"articleText":"Body A text."}],summarizer,previous=out,workers=1)
        self.assertEqual((len(calls),again[0]["koSummary"]),(1,"현대차가 앨라배마 공장에 4억5000만달러를 투자한다."))   # 같은 주소·제목이면 다시 쓴다
        failed=summarize_selected([{**item("C","https://e/c",summary=""),"articleText":"x"}],lambda t,x:"",previous=[],workers=1)
        self.assertNotIn("summaryTranslationStatus",failed[0])

    def test_publisher_feed_parsing_scoring_and_strict_korea(self):
        import datetime as _dt
        now=_dt.datetime.now(gc.KST).strftime("%a, %d %b %Y %H:%M:%S +0900")
        xml=("<rss><channel>"
             f"<item><title>Hyundai Mobis wins battery system order from European OEM</title><link>https://example.com/a</link><pubDate>{now}</pubDate>"
             "<description>Hyundai Mobis said it won an order for battery systems worth $1 billion.</description></item>"
             f"<item><title>Utility rate case in Ohio</title><link>https://example.com/b</link><pubDate>{now}</pubDate><description>grid transformer price</description></item>"
             "<item><title>No date battery plant</title><link>https://example.com/c</link><description>battery plant</description></item>"
             "</channel></rss>").encode()
        orig=gc.get
        try:
            gc.get=lambda url,timeout=15: xml
            rows=gc.parse_publisher("Electrek","https://electrek.co/feed/")
            strict=gc.parse_publisher("Utility Dive","https://www.utilitydive.com/feeds/news/")
        finally:
            gc.get=orig
        self.assertEqual([r["url"] for r in rows],["https://example.com/a","https://example.com/b"])   # 날짜 없는 항목은 뺀다
        self.assertIn("battery systems",rows[0]["articleText"])
        self.assertEqual([r["url"] for r in strict],["https://example.com/a"])   # 전력 전문지는 한국 회사 이름이 있을 때만

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
