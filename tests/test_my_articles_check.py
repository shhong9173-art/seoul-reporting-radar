"""기자 기사 자동 대조: 아이뉴스24 사이트맵(11-03 탐침 159 실제 모양)·작성자 메타로 홍성효 기사만, 구글 색인은 첫 실행만(작성자 미확인),
레이더 항목과 대조(11-03 추가 감시 이벤트 포함), 안 쓴 항목은 세지 않음."""
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import my_articles_check as w  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 11, 4, 19, 40, tzinfo=KST)
SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">
  <url>
   <loc>https://www.inews24.com/view/2019957</loc>
   <news:news>
\t<news:publication>
\t\t<news:name>아이뉴스24</news:name>
\t\t<news:language>ko</news:language>
\t</news:publication>
   \t<news:publication_date>2026-11-03T23:00:00+09:00</news:publication_date>
     <news:title>&quot;업무 맥락 이해하는 AI 에이전트&quot;⋯스노우플레이크, 기업용 에이전트 기능 고도화</news:title>
    </news:news>
\t</url>
  <url><loc>https://www.inews24.com/view/3000001</loc><news:news><news:publication_date>2026-11-04T10:00:00+09:00</news:publication_date>
     <news:title>기아, 화성 신차 불법 야적 논란⋯시의회 "공장 부지 허가 위반"</news:title></news:news></url>
  <url><loc>https://www.inews24.com/view/3000002</loc><news:news><news:publication_date>2026-11-04T11:00:00+09:00</news:publication_date>
     <news:title>포스코퓨처엠, 양극재 증설</news:title></news:news></url>
  <url><loc>https://www.inews24.com/view/3000003</loc><news:news><news:publication_date>2026-11-04T12:00:00+09:00</news:publication_date>
     <news:title>현대제철, 3분기 영업익 871억원</news:title></news:news></url>
</urlset>"""
PAGES = {"https://www.inews24.com/view/3000001": '<meta property="og:article:author"\tcontent="홍성효"/><meta property="article:author" content="홍성효">',
         "https://www.inews24.com/view/3000003": '<meta property="article:author" content="최효경">'}
RSS = """<rss><channel>
<item><title>금호타이어, 롯데카드와 제휴카드 출시…최대 80만원 선할인 - 아이뉴스24</title><pubDate>Tue, 03 Nov 2026 01:26:18 GMT</pubDate></item>
<item><title>트럼프 "바이낸스 해킹 北 소행이면 北과 대화" - 아이뉴스24</title><pubDate>Sun, 01 Nov 2026 05:14:01 GMT</pubDate></item>
</channel></rss>"""
DOCS = {"council-minutes": {"events": [
    {"id": "clik:CLIKC1", "tier": "A", "kind": "지방의회 회의록", "company": "기아", "detectedAt": "2026-10-21T09:10:00+09:00",
     "text": "화성시의회 제300회 본회의(20261020) 회의록 · 기아 대목 「신차 2000대가 공장 시설로 허가받은 땅에 야적되고 있습니다. 불법 아닙니까?」"},
    {"id": "clik:C", "tier": "C", "kind": "지방의회 회의록", "company": "현대제철", "detectedAt": "2026-10-21T09:10:00+09:00", "text": "봉사"}]}}


class R:
    def __init__(self, text="", code=200):
        self.text, self.status_code, self.content = text, code, text.encode()


def fake(fail=()):
    calls = []

    def get(url, headers=None, timeout=None, params=None):
        calls.append(url)
        if url == w.SITEMAP:
            return R(SITEMAP)
        if url.startswith(w.GOOGLE):
            return R(RSS)
        if url in fail:
            raise type("ReadTimeout", (Exception,), {})("x")
        return R(PAGES.get(url, '<meta property="article:author" content="다른기자">'))
    return get, calls


class MyArticles(unittest.TestCase):
    def test_sitemap_author_and_beat_titles(self):
        rows = w.parse_sitemap(SITEMAP)
        self.assertEqual(rows[0], {"url": "https://www.inews24.com/view/2019957", "published": "2026-11-03T23:00:00+09:00",
                                   "title": '"업무 맥락 이해하는 AI 에이전트"⋯스노우플레이크, 기업용 에이전트 기능 고도화'})
        self.assertEqual(w.author_of(PAGES["https://www.inews24.com/view/3000001"]), "홍성효")
        self.assertEqual(w.companies_in("포스코퓨처엠, 양극재 증설"), [])                 # 계열사는 출입처 아님
        self.assertEqual(w.companies_in("현대차·기아, 'K-세일페스타' 할인 공세"), ["현대차", "기아"])
        self.assertEqual(w.companies_in("LS전선·LS마린솔루션, 504MW 태안해상풍력 해저케이블"), ["LS전선"])
        self.assertEqual(w.companies_in("영풍 석포제련소 앞 낙동강, 사계절 내내 수달 포착"), ["영풍"])
        # 기사 종류(11-04: 기자 기사 7일 제목 실제 예)
        self.assertEqual([w.kind_of(t) for t in ["KG스틸, 3분기 영업익 248억원⋯전년比 53.9% 감소", "SK이노베이션, 총괄사장에 정승일⋯\"전력사업자 전환 총괄\"",
                                                "금호타이어, 롯데카드와 제휴카드 출시…최대 80만원 선할인", "LS전선, 구미에 3500억원 들여 희토류 영구자석 공장 짓는다",
                                                "두산에너빌리티, 美 뉴스케일파워 SMR 상부 원자로 제작 계약", "대미 타이어 수출 25% 감소…유럽이 메웠지만 관세 '복병'",
                                                "효성중공업, 사무노조 전면파업 예고에 \"깊은 유감\"", "LS전선·LS마린솔루션, 504MW 태안해상풍력 해저케이블 일정 확보"]],
                         ["실적", "인사·조직", "제품·마케팅", "투자·공장", "수주·계약", "통계·시장", "노사·안전", "기타"])
        # 11-04 첫 화면에서 잘못 묶인 제목
        self.assertEqual([w.kind_of(t) for t in ["법원, 고려아연 자사주 공개매수 손배소서 영풍 패소 판결⋯최윤범 등 책임 불인정",
                                                "동국제강, 하나은행·하나카드와 맞손…철강 구매기업 금융 지원 확대",
                                                "주주가치 높인다며 산 자사주…KG스틸, 임직원 보상에 쓴다", "BMW코리아, '더 뉴 7시리즈' 사전예약 돌입",
                                                "HD현대일렉트릭, LG CNS와 데이터센터·스마트 제조 협력 확대"]],
                         ["논란·법적", "수주·계약", "자본·지배구조", "제품·마케팅", "수주·계약"])

    def test_run_matches_own_articles_with_radar(self):
        get, calls = fake()
        doc = w.run(NOW, None, DOCS, {}, get=get, sleep=lambda s: None)
        opened = [u for u in calls if "/view/" in u]
        self.assertEqual(opened, ["https://www.inews24.com/view/3000001", "https://www.inews24.com/view/3000003"])   # 출입처 제목만, 계열사 제목은 안 엶
        self.assertEqual(doc["checks"][0]["mineNew"], 1)
        by = {a["title"][:6]: a for a in doc["articles"]}
        self.assertEqual(by["기아, 화성"]["verdict"], "먼저 잡은 후보")
        self.assertEqual((by["기아, 화성"]["kind"], by["금호타이어,"]["kind"]), ("논란·법적", "제품·마케팅"))
        self.assertEqual(by["기아, 화성"]["best"]["label"], "지방의회 회의록")              # 11-03 추가 감시도 레이더 기억에 든다
        self.assertTrue(by["기아, 화성"]["verified"])
        self.assertEqual(doc["itemHits"]["clik:CLIKC1"]["title"][:8], "기아, 화성 신")
        self.assertFalse(by["금호타이어,"]["verified"])                                   # 첫 실행 구글 색인 — 작성자 미확인
        self.assertEqual(by["금호타이어,"]["verdict"], "없음")
        self.assertEqual(by["트럼프 \"바"]["verdict"], "회사 미상")                       # 당직 기사 — 출입처 아님
        self.assertNotIn("현대제철, 3", by)                                             # 다른 기자 기사
        self.assertEqual(doc["checked"]["https://www.inews24.com/view/3000003"], "최효경")
        # 다음 실행: 본 주소는 다시 열지 않고, 구글 색인도 다시 부르지 않는다
        get2, calls2 = fake()
        doc2 = w.run(NOW + dt.timedelta(hours=6), doc, DOCS, {}, get=get2, sleep=lambda s: None)
        self.assertEqual([u for u in calls2 if "/view/" in u or u.startswith(w.GOOGLE)], [])
        self.assertEqual(len(doc2["articles"]), len(doc["articles"]))

    def test_failed_article_is_retried_and_sitemap_failure_is_not_zero(self):
        get, _ = fake(fail=("https://www.inews24.com/view/3000001",))
        doc = w.run(NOW, {"schema": w.SCHEMA, "backfilledAt": "x"}, DOCS, {}, get=get, sleep=lambda s: None)
        self.assertNotIn("https://www.inews24.com/view/3000001", doc["checked"])   # 다음 실행에 다시
        self.assertEqual(doc["status"], "partial")

        def down(url, **k):
            raise type("ConnectionError", (Exception,), {})("x")
        bad = w.run(NOW, {"schema": w.SCHEMA, "backfilledAt": "x"}, DOCS, {}, get=down, sleep=lambda s: None)
        self.assertEqual((bad["status"], bad["checks"][0]["status"]), ("failed", "failed"))
        self.assertIn("사이트맵:ConnectionError", bad["checks"][0]["error"])

    def test_press_release_split_11_04(self):
        # 11-04 기자: "내 기사 대부분이 보도자료". 같은 때 다른 매체 비슷한 제목이 먼저 2곳 이상 → 보도자료·공시, 모두 뒤면 선행
        a = {"title": "KG스틸, 3분기 영업익 248억원⋯전년比 53.9% 감소", "published": "2026-11-03T15:51:02+09:00"}
        items = [{"title": "<b>KG스틸</b>, 3분기 영업익 248억원…전년比 53.9% 감소(종합)", "originallink": "https://www.news1.kr/x", "pubDate": "Tue, 03 Nov 2026 15:20:00 +0900"},
                 {"title": "KG스틸 3분기 영업이익 248억원, 전년 대비 53.9% 감소", "originallink": "https://www.newsis.com/x", "pubDate": "Tue, 03 Nov 2026 15:31:00 +0900"},
                 {"title": "KG스틸, 3분기 영업익 248억원⋯전년比 53.9% 감소", "originallink": "https://www.inews24.com/view/1", "pubDate": "Tue, 03 Nov 2026 15:51:02 +0900"},
                 {"title": "철강업계 3분기 실적 희비", "originallink": "https://x.com/y", "pubDate": "Tue, 03 Nov 2026 16:00:00 +0900"}]
        self.assertEqual(w.press_label(a, items), ("보도자료·공시", 2))
        b = {"title": "대미 타이어 수출 25% 감소…유럽이 메웠지만 관세 '복병'", "published": "2026-11-03T14:00:00+09:00"}
        self.assertEqual(w.press_label(b, [{"title": "대미 타이어 수출 25% 감소…관세 복병", "originallink": "https://a.kr/1", "pubDate": "Tue, 03 Nov 2026 18:00:00 +0900"}]),
                         ("선행", 1))                                                  # 기자 기사 4시간 뒤 다른 매체
        self.assertEqual(w.press_label(b, items), ("자체", 0))
        # 11-04 보정: 같은 출입처 + 다른 낱말 2개(자사주·공개매수) 겹침도 비슷한 제목
        c = {"title": "고려아연, 자사주 공개매수 손배소 승소에 \"정당한 경영판단 인정\"", "published": "2026-10-22T16:00:00+09:00"}
        others = [{"title": "법원, 고려아연 자사주 공개매수 손배소서 영풍 패소 판결", "originallink": "https://a.kr/1", "pubDate": "Thu, 22 Oct 2026 14:30:00 +0900"},
                  {"title": "영풍·MBK, 고려아연 <b>자사주</b> 공개매수 손배소 패소에 \"즉각 항소\"", "originallink": "https://b.kr/1", "pubDate": "Thu, 22 Oct 2026 15:10:00 +0900"},
                  {"title": "고려아연, 3분기 영업익 발표", "originallink": "https://c.kr/1", "pubDate": "Thu, 22 Oct 2026 15:00:00 +0900"}]
        self.assertEqual(w.press_label(c, others), ("보도자료·공시", 2))
        self.assertFalse(w.press_similar("고려아연, 3분기 영업익 발표", "고려아연, 자사주 공개매수 손배소 승소"))   # 회사만 같음

    def test_run_marks_press_once_and_counts_own_articles(self):
        calls = []

        def search(params):
            calls.append(params["query"])
            if "금호타이어" in params["query"]:
                return [{"title": "금호타이어, 롯데카드와 제휴카드 출시", "originallink": f"https://o{i}.kr", "pubDate": "Mon, 02 Nov 2026 10:00:00 +0900"} for i in range(3)]
            return []
        get, _ = fake()
        doc = w.run(NOW, None, DOCS, {}, get=get, sleep=lambda s: None, search=search)
        by = {a["title"][:6]: a for a in doc["articles"]}
        self.assertEqual(by["금호타이어,"]["press"], "보도자료·공시")
        self.assertEqual(by["기아, 화성"]["press"], "자체")
        self.assertEqual(doc["pressCounts"]["보도자료·공시"], 1)
        self.assertEqual(doc["ownCounts"]["먼저 잡은 후보"], 1)
        n = len(calls)
        doc2 = w.run(NOW + dt.timedelta(hours=6), doc, DOCS, {}, get=fake()[0], sleep=lambda s: None, search=search)
        self.assertEqual(len(calls), n)                                              # 한 번 정한 기사는 다시 묻지 않음
        self.assertEqual(doc2["pressCounts"], doc["pressCounts"])

        def refused(params):
            raise RuntimeError("키 거부")
        doc3 = w.run(NOW, None, DOCS, {}, get=fake()[0], sleep=lambda s: None, search=refused)
        self.assertEqual(doc3["pressCounts"]["미확인"], len(doc3["articles"]))         # 검색 실패는 판정 안 함
        self.assertIn("뉴스 검색:RuntimeError", doc3["checks"][0]["error"])

    def test_earnings_articles_count_as_filings_11_11(self):
        self.assertEqual(w.press_of({"title": "KG스틸, 3분기 영업익 248억원⋯전년比 53.9% 감소", "press": "자체"}, "실적"), ("보도자료·공시", w.EARNINGS_NOTE))
        self.assertEqual(w.press_of({"title": "[단독] 현대제철, 4분기 적자 전환 유력", "press": "자체"}, "실적"), ("자체", None))   # 단독은 그대로
        self.assertEqual(w.press_of({"title": "금호석유화학, 특수가스 자회사 흡수합병 마무리", "press": "자체"}, "기타"), ("자체", None))
        self.assertEqual(w.press_of({"title": "KG스틸, 3분기 영업익", "press": None}, "실적"), (None, None))          # 판정 전은 판정 전
        self.assertEqual(w.press_of({"title": "KG스틸, 3분기 영업익", "press": "선행"}, "실적"), ("선행", None))        # 기자가 먼저 쓴 기사는 그대로

        def search(params):
            return []   # 비슷한 제목 없음 → 저장 판정은 '자체'
        get, _ = fake()
        doc = w.run(NOW, None, DOCS, {}, get=get, sleep=lambda s: None, search=search)
        art = next(a for a in doc["mine"] if a["title"].startswith("기아, 화성"))
        self.assertEqual(art["press"], "자체")
        earn = {"url": "https://www.inews24.com/view/3000009", "title": "현대제철, 3분기 영업익 871억원", "published": "2026-11-04T16:00:00+09:00",
                "companies": ["현대제철"], "verified": True, "press": "자체", "pressN": 0, "pressAt": "2026-11-04T19:40:00+09:00", "pressV": w.PRESS_V}
        doc2 = w.run(NOW + dt.timedelta(hours=1), {**doc, "mine": doc["mine"] + [earn]}, DOCS, {}, get=fake()[0], sleep=lambda s: None, search=search)
        row = next(a for a in doc2["articles"] if a["title"].startswith("현대제철, 3분기"))
        self.assertEqual((row["press"], row["pressNote"], row["kind"]), ("보도자료·공시", w.EARNINGS_NOTE, "실적"))
        self.assertEqual(next(a for a in doc2["mine"] if a["title"].startswith("현대제철, 3분기"))["press"], "자체")   # 저장값은 그대로
        self.assertEqual(doc2["pressCounts"]["자체"], doc["pressCounts"]["자체"])                       # 실적 기사는 '자체'에 안 더해짐
        self.assertEqual(doc2["pressCounts"]["보도자료·공시"], doc["pressCounts"]["보도자료·공시"] + 1)


    def test_lead_is_read_from_meta_and_backfilled_once_11_11(self):
        self.assertEqual(w.lead_of('<meta property="og:description" content="무역위원회가 착수한 &#39;아크릴산 2-에틸헥실&#39; 반덤핑 조사">'),
                         "무역위원회가 착수한 '아크릴산 2-에틸헥실' 반덤핑 조사")
        self.assertEqual(w.lead_of('<meta content="첫 문단" name="description">'), "첫 문단")
        self.assertIsNone(w.lead_of('<meta property="article:author" content="홍성효">'))
        get, calls = fake()
        doc = w.run(NOW, None, DOCS, {}, get=get, sleep=lambda s: None)
        kia = next(a for a in doc["mine"] if a["title"].startswith("기아, 화성"))
        self.assertEqual(kia["lead"], "")                                                   # 새로 연 기사: 메타 없으면 빈 값(다시 안 엶)
        old = {"url": "https://www.inews24.com/view/2023473", "title": "[단독] LG화학, 수입산 점착제 원료 반덤핑 조사 신청", "published": "2026-11-04T14:42:00+09:00",
               "companies": ["LG화학"], "verified": True}
        PAGES[old["url"]] = '<meta property="og:description" content="무역위원회가 착수한 중국·미국·말레이시아산 \'아크릴산 2-에틸헥실\'(2-EHA) 반덤핑 조사">'
        try:
            n = len(calls)
            doc2 = w.run(NOW + dt.timedelta(hours=1), {**doc, "mine": doc["mine"] + [old]}, DOCS, {}, get=get, sleep=lambda s: None)
            got = next(a for a in doc2["mine"] if a["url"] == old["url"])
            self.assertIn("아크릴산 2-에틸헥실", got["lead"])
            self.assertEqual(doc2["checks"][0]["leadOpened"], 1)                             # 첫 문단 없는 지난 기사만 다시 엶
            self.assertEqual(calls[n:].count(old["url"]), 1)
            doc3 = w.run(NOW + dt.timedelta(hours=2), doc2, DOCS, {}, get=get, sleep=lambda s: None)
            self.assertEqual(doc3["checks"][0]["leadOpened"], 0)                             # 한 번 채우면 다시 안 엶
        finally:
            PAGES.pop(old["url"], None)


if __name__ == "__main__":
    unittest.main()
