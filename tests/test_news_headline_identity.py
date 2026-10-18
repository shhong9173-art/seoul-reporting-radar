import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from news_headline_identity import normalize_title, obvious_sports_homonym


class HeadlineIdentity(unittest.TestCase):
    def test_internal_dash_is_not_discarded(self):
        a="현대차 - 인도 생산라인 증설 - 한국경제"
        b="현대차 - 인도 생산라인 축소 - 한국경제"
        self.assertEqual(normalize_title(a,"한국경제"),"현대차 - 인도 생산라인 증설")
        self.assertNotEqual(normalize_title(a,"한국경제"),
                            normalize_title(b,"한국경제"))

    def test_pipe_in_story_remains(self):
        self.assertEqual(normalize_title("포스코 | 현대제철 공급망 변화"),
                         "포스코 | 현대제철 공급망 변화")
        self.assertEqual(normalize_title("현대차 | 기아 - 매일경제","매일경제"),
                         "현대차 | 기아")

    def test_only_matching_final_publisher_removed(self):
        self.assertEqual(normalize_title("전기차 리콜 - 고유 매체","다른 매체"),
                         "전기차 리콜 - 고유 매체")
        self.assertEqual(normalize_title("배터리 - 모델 A - Reuters","Reuters"),
                         "배터리 - 모델 a")
        self.assertEqual(normalize_title("기업 A-B 공급계약 - 뉴스1","뉴스1"),
                         "기업 a-b 공급계약")

    def test_explicit_sports_homonyms_blocked(self):
        for title in (
            "기아 타이거즈, 준플레이오프 2연승",
            "프로농구 현대모비스 15연패 탈출",
            "울산 현대모비스 피버스 리바운드 우위",
        ):
            self.assertTrue(obvious_sports_homonym(title),title)

    def test_real_operating_mobis_phoebus_event_not_automotive(self):
        headline="‘별까루 마킹’ 유니폼 소장 욕구UP!…현대모비스, 25일까지 ‘도전! 피버스 키즈 모델’ 참가자 모집 - 스포츠서울"
        self.assertTrue(obvious_sports_homonym(headline))
        self.assertFalse(obvious_sports_homonym(
            "울산 현대모비스 공장 배터리 부품 증설"))
        self.assertFalse(obvious_sports_homonym(
            "울산 현대모비스 연간 120만대 생산능력 확대"))

    def test_company_automotive_industry_preserved(self):
        for title in (
            "기아 전기차 생산라인 확대",
            "현대모비스 전동화 부품 신규 공장",
            "현대차 노조 임금교섭 잠정합의",
            "기아 차종별 배터리 리콜",
        ):
            self.assertFalse(obvious_sports_homonym(title),title)

    def test_no_company_sports_not_misclassified_as_company_news(self):
        self.assertFalse(obvious_sports_homonym("프로야구 롯데 3연승"))

if __name__=="__main__":
    unittest.main()
