"""Scoop screening: queries from real-looking clues, same-number vs related vs not-found, failures stay 미확인."""
import datetime as dt
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import scoop_screen as s  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 10, 27, 7, 10, tzinfo=KST)

CLUES = {"items": [
    {"id": "a1", "team": "자동차", "published": None, "source": "DART_METRIC", "companies": ["현대차"], "routine": False,
     "tier": "취재 단서·단독 미확정", "url": "https://dart.fss.or.kr/x",
     "title": "현대자동차 · HMTR/튀르키예 — 공식 2025→2026 동일기간·단위 숫자 117600 → 95900 (대)"},
    {"id": "a2", "team": "자동차", "published": "2026-10-19", "source": "DART", "companies": ["현대위아"], "routine": False,
     "tier": "공개 원자료 추적", "url": "https://dart.fss.or.kr/y", "title": "현대위아 · 영업양도결정"},
    {"id": "a3", "team": "자동차", "published": "2026-08-01", "source": "DART", "companies": ["기아"], "routine": False,
     "tier": "공개 원자료 추적", "title": "기아 · 오래된 공시"},
    {"id": "a4", "team": "자동차", "published": "2026-10-25", "source": "DART", "companies": ["기아"], "routine": True,
     "tier": "공개 원자료 추적", "title": "기아 · 기업설명회(IR)개최"},
    {"id": "a5", "team": "철강·비철", "published": "2026-10-22", "source": "미 연방관보", "companies": ["포스코"], "routine": False,
     "tier": "공개 원자료 추적", "title": "Certain Hot-Rolled Steel Flat Products From Korea"},
]}
STATS = {"items": [
    {"id": "s1", "team": "전력·에너지", "company": "LS일렉트릭", "label": "LS일렉트릭 생산능력 (부산 / 초고압변압기, 배전변압기)",
     "period": "2025→2026 06월 누적", "current": "484052", "prior": "228651", "unit": "백만원", "changePercent": 111.7,
     "strength": 120, "source": "DART 분기·반기 사업의 내용", "sourceUrls": ["https://dart.fss.or.kr/z"]},
    {"id": "s2", "team": "전력·에너지", "company": "LS일렉트릭", "label": "약한 변화", "current": "10", "prior": "9", "strength": 10},
]}


class Numbers(unittest.TestCase):
    def test_forms_cover_comma_man_and_eok(self):
        self.assertTrue({"117,600", "11만7600"} <= s.num_forms("117600", "대"))
        self.assertTrue({"4,840억", "4840억"} <= s.num_forms("484052", "백만원"))
        self.assertIn("1조2345억", s.num_forms("1234500", "백만원"))
        self.assertIn("12조3450억", s.num_forms("12345000", "백만원"))
        self.assertEqual(s.num_forms("42", "대"), set())  # too common to be evidence
        self.assertIn("2.1배", s.ratio_forms("228651", "484052"))


class Selection(unittest.TestCase):
    def test_strong_and_fresh_clues_and_strong_stats_only(self):
        rows = s.select(CLUES, STATS, now=NOW)
        ids = [r["id"] for r in rows]
        self.assertIn("clue:a1", ids)
        self.assertIn("clue:a2", ids)
        self.assertNotIn("clue:a3", ids)  # stale and weak
        self.assertNotIn("clue:a4", ids)  # routine
        self.assertNotIn("clue:a5", ids)  # English prose only → no usable Korean query
        self.assertIn("stat:s1", ids)
        self.assertNotIn("stat:s2", ids)
        hmtr = next(r for r in rows if r["id"] == "clue:a1")
        self.assertEqual(s.queries(hmtr), ["현대차 튀르키예", "현대차 튀르키예 HMTR"])
        self.assertIn("95,900", hmtr["numbers"])
        wia = next(r for r in rows if r["id"] == "clue:a2")
        self.assertEqual(wia["terms"], ["영업양도"])  # 양도 keeps its last syllable

    def test_old_table_numbers_are_labelled_and_ranked_down(self):
        rows = s.select(CLUES, STATS, now=NOW)
        stat = next(r for r in rows if r["id"] == "stat:s1")
        self.assertIsNone(stat.get("staleDays"))  # fixture URL has no receipt number
        old = dict(STATS["items"][0], id="s3", sourceUrls=["https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260814003088"])
        rows = s.select(CLUES, {"items": [old]}, now=NOW)
        stale = next(r for r in rows if r["id"] == "stat:s3")
        self.assertEqual(stale["filedOn"], "2026-08-14")
        self.assertEqual(stale["staleDays"], 74)
        self.assertEqual(stale["strength"], 1.5)

    def test_procedural_filings_patents_and_news_vocabulary(self):
        clues = {"items": [
            {"id": "m1", "team": "자동차", "published": "2026-10-22", "source": "DART", "companies": ["현대모비스"], "routine": False,
             "tier": "공개 원자료 추적", "title": "현대모비스 · 특수관계인으로부터기타유가증권매수"},
            {"id": "m2", "team": "철강·비철", "published": "2026-10-21", "source": "DART", "companies": ["동국제강"], "routine": False,
             "tier": "공개 원자료 추적", "title": "동국제강 · 정기·주요공시 · 기업가치제고계획(자율공시)"},
            {"id": "m3", "team": "전력·에너지", "published": "2026-10-21", "source": "DART", "companies": ["대한전선"], "routine": False,
             "tier": "공개 원자료 추적", "title": "대한전선 · 대표이사(대표집행임원)변경(안내공시)"},
            {"id": "m4", "team": "전력·에너지", "published": "2026-10-20", "source": "DART", "companies": ["HD현대일렉트릭"], "routine": False,
             "tier": "공개 원자료 추적", "title": "HD현대일렉트릭 · 중대재해발생(종속회사의주요경영사항)"},
            {"id": "m5", "team": "특허", "published": "2026-10-12", "source": "KIPRIS 공개특허", "companies": ["기아"], "routine": False,
             "tier": "취재 단서·단독 미확정", "title": "고정자 냉각 장치 (기아, 현대자동차)"},
        ]}
        # 10-30 radar_today A에 매일 올라온 형식 공시(계열사 상품·용역거래, 의결권 권유, 실적 전망 정정)
        clues["items"] += [
            {"id": "m6", "team": "화학", "published": "2026-10-29", "source": "DART", "companies": ["한화솔루션"], "routine": False,
             "tier": "취재 단서·단독 미확정", "title": "한화솔루션 · 동일인등출자계열회사와의상품ㆍ용역거래변경"},
            {"id": "m7", "team": "자동차", "published": "2026-10-28", "source": "DART", "companies": ["현대모비스"], "routine": False,
             "tier": "취재 단서·단독 미확정", "title": "현대모비스 · 의결권대리행사권유참고서류"},
            {"id": "m8", "team": "자동차", "published": "2026-10-29", "source": "DART", "companies": ["현대차"], "routine": False,
             "tier": "취재 단서·단독 미확정", "title": "현대자동차 · 정기·주요공시 · [기재정정]영업실적등에대한전망(공정공시)"},
            {"id": "m9", "team": "자동차", "published": "2026-10-29", "source": "DART", "companies": ["현대모비스"], "routine": False,
             "tier": "취재 단서·단독 미확정", "title": "현대모비스 · 약관에의한금융거래시계열금융회사의거래상대방의공시"}]
        rows = {r["id"]: r for r in s.select(clues, {}, now=NOW)}
        self.assertEqual(set(rows), {"clue:m4", "clue:m5"})
        accident = rows["clue:m4"]
        self.assertEqual(s.queries(accident), ["HD현대일렉트릭 중대재해"])
        art = {"title": "HD현대일렉트릭 자회사 공장서 사망 사고", "text": "", "url": "a", "date": "2026-10-20"}
        self.assertEqual(s.judge(accident, channels([art]), now=NOW)[0], "관련 보도 있음")
        patent = rows["clue:m5"]
        self.assertEqual(patent["kind"], "특허")
        self.assertIn("단독이 아니다", patent["note"])
        self.assertEqual(patent["strength"], 0.5)

    def test_disclosure_form_names_become_headline_words(self):
        # 10-31 운영 질의: 'LS전선 교환사채권발행'·'HD현대일렉트릭 타인에대한채무보증'·'영풍 임원'·'현대모비스 분할 항목'·'두산에너빌리티 항목'
        def q(title, company):
            return s.news_terms(s.terms_from(title, company))
        self.assertEqual(q("LS전선 · 정기·주요공시 · [기재정정]주요사항보고서(교환사채권발행결정)", "LS전선"),
                         (["교환사채"], {"교환사채": ["교환사채", "교환사채권"]}))
        self.assertEqual(q("HD현대일렉트릭 · 타인에대한채무보증결정", "HD현대일렉트릭")[0], ["채무보증"])
        self.assertEqual(q("포스코홀딩스 · 주요사항보고서(전환사채권발행결정)", "포스코홀딩스")[0], ["전환사채"])
        self.assertEqual(q("영풍 · 임원ㆍ주요주주특정증권등거래계획보고서", "영풍")[0], ["거래계획"])
        self.assertIn("매도 계획", q("영풍 · 임원ㆍ주요주주특정증권등거래계획보고서", "영풍")[1]["거래계획"])
        self.assertEqual(q("현대모비스 [기재정정]주요사항보고서(회사분할결정) — 변경 항목 대조 필요", "현대모비스")[0], ["분할"])
        self.assertEqual(q("두산에너빌리티 [기재정정]단일판매ㆍ공급계약체결 — 변경 항목 대조 필요", "두산에너빌리티")[0], [])
        # BW 발행 결정은 자금 조달 기사라 심사 대상, 신주인수권 행사는 계속 형식 공시
        self.assertIsNone(s.ADMIN.search("X · 주요사항보고서(신주인수권부사채권발행결정)"))
        self.assertTrue(s.ADMIN.search("X · 신주인수권행사"))
        # 영문 약어는 대조 낱말로 쓰지 않는다(EBITDA 기사에 'EB'가 섞인다)
        self.assertFalse(any(w in ("EB", "CB", "BW") for v in s.NEWS_TERMS.values() for w in v))

    def test_form_only_titles_wait_for_the_filing_subject(self):
        def clue(i, company, title, rcp):
            return {"id": i, "team": "t", "published": "2026-10-29", "source": "DART", "companies": [company], "routine": False,
                    "tier": "공개 원자료 추적", "title": title, "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcp}"}
        clues = {"items": [clue("o1", "OCI홀딩스", "OCI홀딩스 · [기재정정]수시공시의무관련사항(공정공시)", "20261029800315"),
                           clue("h1", "현대차", "현대자동차 · [기재정정]장래사업ㆍ경영계획(공정공시)", "20261029800231"),
                           clue("h2", "현대차", "현대자동차 · 기타경영사항(자율공시)", "20261029800999"),
                           clue("x1", "현대차", "현대자동차 · 투자판단관련주요경영사항", "20261029800998")]}
        rows = {r["id"]: r for r in s.select(clues, {}, now=dt.datetime(2026, 10, 31, 7, 10, tzinfo=KST))}
        self.assertEqual(set(rows), {"clue:o1", "clue:h1", "clue:h2", "clue:x1"})  # same company, different filings: not merged
        self.assertTrue(all(r["bodyTitle"] and r["terms"] == [] for r in rows.values()))
        # 원문 제목(2026-10-31 실제 공시에서 읽은 값)
        rows["clue:o1"]["filing"] = {"type": "공정공시", "facts": [["공시제목", "2024년 ~ 2026년 자기주식 취득 및 소각 계획"]]}
        rows["clue:h1"]["filing"] = {"type": "공정공시", "facts": [["장래계획사항", "2026년 현대자동차 가이던스"]]}
        rows["clue:h2"]["filing"] = {"type": "공정공시", "error": "원문 조회 실패(ValueError) — 미확인"}
        kept, count = s.apply_body_titles(list(rows.values()))
        self.assertEqual(count, {"read": 1, "procedural": 1, "unread": 2})  # x1: no filing read at all (no DART key)
        self.assertEqual([r["id"] for r in kept], ["clue:h1"])
        self.assertEqual((kept[0]["terms"], kept[0]["subject"]), (["가이던스"], "2026년 현대자동차 가이던스"))
        self.assertEqual(s.queries(kept[0]), ["현대차 가이던스"])
        art = {"title": "현대차, 올해 판매 가이던스 400만대로 하향", "text": "", "url": "g", "date": "2026-10-29"}
        self.assertEqual(s.judge(kept[0], channels([art]), now=dt.datetime(2026, 10, 31, 7, 10, tzinfo=KST))[0], "관련 보도 있음")
        # 기존 후보는 그대로
        plain = {"id": "clue:p", "terms": ["분할"]}
        self.assertEqual(s.apply_body_titles([plain]), ([plain], {"read": 0, "procedural": 0, "unread": 0}))

    def test_supply_contracts_are_searched_by_the_contract_name(self):
        # 10-31: 단일판매ㆍ공급계약 공시는 제목 낱말이 모두 상투어라 심사에서 빠졌다(대한전선 10-27·두산 10-26·효성 10-27)
        def clue(i, company, title, source="DART"):
            return {"id": i, "team": "t", "published": "2026-10-27", "source": source, "companies": [company] if company else [],
                    "routine": False, "tier": "공개 원자료 추적", "title": title,
                    "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo=2026102780{i[-4:]}"}
        clues = {"items": [clue("c0001", "대한전선", "대한전선 단일판매ㆍ공급계약체결"),
                           # 회사 칸이 빈 '그 외' 팀 공시: 제목 앞 이름이 심사 대상 회사면 그 회사
                           clue("c0002", None, "일진전기 · 공급계약 · 단일판매ㆍ공급계약체결"),
                           clue("c0003", None, "효성중공업 · 건설/주상복합 — 공식 2025→2026 동일기간·단위 숫자 793315 → 101198", "DART_METRIC"),
                           clue("c0004", None, "효성중공업 · 임원ㆍ주요주주특정증권등소유상황보고서"),
                           clue("c0005", None, "씨에스윈드 · [기재정정]단일판매ㆍ공급계약체결")]}
        rows = {r["id"]: r for r in s.select(clues, {}, now=dt.datetime(2026, 10, 31, 7, 10, tzinfo=KST))}
        self.assertEqual(set(rows), {"clue:c0001", "clue:c0002"})  # 수치 단서·소유상황 형식명·대상 밖 회사는 그대로 뺀다
        self.assertEqual((rows["clue:c0002"]["company"], rows["clue:c0002"]["bodyTitle"]), ("일진전기", True))
        # 원문 체결계약명(엘에스일렉트릭 20261019800108 형식)
        rows["clue:c0001"]["filing"] = {"type": "공급계약", "facts": [["체결계약명", "765kV 초고압 전력케이블 공급"], ["계약상대", "한국전력공사"]]}
        rows["clue:c0002"]["filing"] = {"type": "공급계약", "facts": [["체결계약명", "-"], ["계약상대", "비공개"]]}
        kept, count = s.apply_body_titles(list(rows.values()))
        self.assertEqual(count, {"read": 1, "procedural": 0, "unread": 1})  # 계약명 '-'는 못 읽은 것과 같다
        self.assertEqual(s.queries(kept[0]), ["대한전선 초고압", "대한전선 초고압 전력케이블"])  # 한글 낱말 먼저
        art = {"title": "대한전선, 한전에 765kV 초고압 전력케이블 1200억 공급", "text": "", "url": "k", "date": "2026-10-28"}
        self.assertEqual(s.judge(kept[0], channels([art]), now=dt.datetime(2026, 10, 31, 7, 10, tzinfo=KST))[0], "관련 보도 있음")
        # 긴 회사 이름부터 지운다(한국타이어앤테크놀로지 → '앤테크놀로지'가 낱말로 남던 것)
        self.assertEqual(s.terms_from("한국타이어앤테크놀로지 · 생산설비", "한국타이어"), ["생산설비"])

    def test_first_seen_is_carried_so_old_candidates_are_not_new(self):
        rows = [{"id": "clue:a"}, {"id": "clue:b"}, {"id": "clue:c"}]
        prev = {"generatedAt": "2026-10-29T07:10:00+09:00",
                "candidates": [{"id": "clue:a", "firstSeen": "2026-10-12T07:10:00+09:00"}, {"id": "clue:b"}]}
        out = {r["id"]: r["firstSeen"] for r in s.carry_first_seen(rows, prev, NOW)}
        self.assertEqual(out["clue:a"], "2026-10-12T07:10:00+09:00")
        self.assertEqual(out["clue:b"], "2026-10-29T07:10:00+09:00")  # 이전 결과에 시각이 없으면 이전 실행 시각
        self.assertEqual(out["clue:c"], NOW.isoformat(timespec="seconds"))
        self.assertEqual(s.carry_first_seen([{"id": "x"}], None, NOW)[0]["firstSeen"], NOW.isoformat(timespec="seconds"))

    def test_qcells_headline_names_hanwha_solutions(self):
        self.assertTrue(s.company_in_text("한화솔루션", "퍼스트솔라, 한화큐셀 등 특허침해 ITC 제소"))

    def test_particles_and_stopwords(self):
        self.assertEqual(s.terms_from("두산에너빌리티 압력용기의 내외부를 이를", "두산에너빌리티"), ["압력용기", "내외부"])


def channels(naver_items=(), bing_items=(), google_status="ok", naver_status="ok"):
    return {"naver": {"status": naver_status, "items": list(naver_items)},
            "bing": {"status": "ok", "items": list(bing_items)}, "google": {"status": google_status, "items": []}}


class Judge(unittest.TestCase):
    def setUp(self):
        self.c = s.select(CLUES, STATS, now=NOW)[0] if False else next(
            r for r in s.select(CLUES, STATS, now=NOW) if r["id"] == "clue:a1")

    def test_same_number_without_period_is_only_related(self):
        art = {"title": "현대차 튀르키예 공장 생산 9만5900대로 감소", "text": "", "url": "u1", "date": "2026-09-01"}
        verdict, ev = s.judge(self.c, channels([art]), now=NOW)
        self.assertEqual(verdict, "관련 보도 있음")
        self.assertIn("동일 사건 미확정", ev[0]["why"])

    def test_related_needs_company_and_terms(self):
        rel = {"title": "현대차 HMTR 튀르키예 공장 감산", "text": "", "url": "u2", "date": "2026-09-01"}
        other = {"title": "기아 HMTR 튀르키예", "text": "", "url": "u3", "date": "2026-09-01"}
        old = {"title": "현대차 HMTR 튀르키예 9만5900대", "text": "", "url": "u4", "date": "2025-01-01"}
        verdict, ev = s.judge(self.c, channels([rel, other, old]), now=NOW)
        self.assertEqual(verdict, "관련 보도 있음")
        self.assertEqual([e["url"] for e in ev], ["u2"])

    def test_lead_term_in_a_headline_with_the_company_counts_as_related(self):
        art = {"title": "현대차, 튀르키예산 아이오닉3 9월 판매 6486대", "text": "", "url": "u5", "date": "2026-10-25"}
        body_only = {"title": "현대차 유럽 전략", "text": "튀르키예 공장도 언급", "url": "u6", "date": "2026-10-25"}
        verdict, ev = s.judge(self.c, channels([art, body_only]), now=NOW)
        self.assertEqual(verdict, "관련 보도 있음")
        self.assertEqual([e["url"] for e in ev], ["u5"])

    def test_generic_first_word_alone_is_not_related(self):
        c = {"company": "HD현대일렉트릭", "terms": ["변압기", "철심공장"], "numbers": [], "ratios": []}
        self.assertEqual(s.lead(c["terms"]), "철심공장")
        generic = {"title": "HD현대일렉트릭, 美 변압기 수주", "text": "", "url": "g1", "date": "2026-10-01"}
        specific = {"title": "HD현대일렉트릭 철심공장 준공 연기", "text": "", "url": "g2", "date": "2026-10-01"}
        self.assertEqual(s.judge(c, channels([generic]), now=NOW)[0], "미보도 후보")
        self.assertEqual(s.judge(c, channels([specific]), now=NOW)[0], "관련 보도 있음")

    def test_not_found_only_when_naver_and_a_web_index_answered(self):
        self.assertEqual(s.judge(self.c, channels(), now=NOW)[0], "미보도 후보")
        self.assertEqual(s.judge(self.c, channels(naver_status="failed"), now=NOW)[0], "미확인")
        self.assertEqual(s.judge(self.c, channels(naver_status="not_configured"), now=NOW)[0], "미확인")
        both_web_down = channels()
        both_web_down["bing"]["status"] = "failed"
        both_web_down["google"]["status"] = "failed"
        self.assertEqual(s.judge(self.c, both_web_down, now=NOW)[0], "미확인")

    def test_entity_number_and_date_false_positives(self):
        c = {"company": "포스코", "terms": ["투자", "공장"], "numbers": ["100억원"], "ratios": []}
        for title in ["포스코인터내셔널 공장 투자 100억원", "포스코 기부 100억원", "포스코퓨처엠 투자 100억원"]:
            with self.subTest(title=title):
                art = {"title": title, "date": "2026-10-26", "url": "test"}
                self.assertEqual(s.judge(c, channels([art]), now=NOW), ("미보도 후보", []))
        for date in ["2030-01-01", None, "2026-02-30", "bad"]:
            art = {"title": "포스코 공장 투자 100억원", "date": date, "url": "test"}
            self.assertEqual(s.judge(c, channels([art]), now=NOW), ("미확인", []))

    def test_legal_entities_and_particles(self):
        for company, wrong in [("LS지주", "LS전선"), ("GS", "GS칼텍스"), ("OCI", "OCI홀딩스"),
                               ("세아제강", "세아제강지주"), ("태광", "태광산업"), ("현대차", "현대차그룹")]:
            self.assertFalse(s.company_in_text(company, wrong + " 투자"))
        self.assertTrue(s.company_in_text("포스코", "포스코는 공장에 투자했다"))
        self.assertTrue(s.company_in_text("현대차", "현대자동차, 공장 증설"))
        self.assertFalse(s.company_in_text("기아", "기아차량부품회사"))

    def test_matching_numbers_need_unit_period_and_event_context(self):
        c = {**self.c, "terms": ["튀르키예", "생산"], "period": "2026년 상반기", "unit": "대"}
        art = {"title": "현대차 2026년 상반기 튀르키예 생산 9만5900대", "date": "2026-10-26", "url": "test"}
        self.assertEqual(s.judge(c, channels([art]), now=NOW)[0], "같은 수치 선행")
        for title in [art["title"].replace("대", "억원"), art["title"].replace("2026년", "2025년"),
                      art["title"].replace("9만5900대", "19만5900대")]:
            self.assertNotEqual(s.judge(c, channels([{**art, "title": title}]), now=NOW)[0], "같은 수치 선행")
        self.assertEqual(s.judge(c, channels([art], naver_status="failed"), now=NOW)[0], "미확인")


class R:
    def __init__(self, code=200, body=None, content=b""):
        self.status_code, self.body, self.content = code, body or {}, content

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)

    def json(self):
        return self.body


class Screen(unittest.TestCase):
    def test_end_to_end_with_fake_channels_and_counts_only_log(self):
        rss_empty = b"<rss><channel></channel></rss>"
        def get(url, params=None, headers=None, timeout=None):
            if "naverapihub" in url:
                q = params["query"]
                items = [{"title": "<b>현대위아</b> 영업양도 결정", "description": "", "originallink": "https://n/1",
                          "pubDate": "Mon, 20 Oct 2026 09:00:00 +0900"}] if "현대위아" in q else []
                return R(200, {"items": items})
            return R(200, content=rss_empty)
        cands = s.select(CLUES, STATS, now=NOW)
        with patch.dict(os.environ, {"NAVER_CLIENT_ID": "i", "NAVER_CLIENT_SECRET": "k"}):
            rows = s.screen(cands, now=NOW, get=get, sleep=lambda x: None)
        by = {r["id"]: r for r in rows}
        self.assertEqual(by["clue:a2"]["verdict"], "관련 보도 있음")
        self.assertEqual(by["clue:a1"]["verdict"], "미보도 후보")
        self.assertEqual(by["clue:a1"]["channels"]["naver"]["via"], "API HUB")
        self.assertEqual(rows[0]["verdict"], "미보도 후보")  # unreported first
        doc = s.report(rows, now=NOW, inputs={})
        self.assertEqual(doc["schema"], "scoop_screen/v1")
        self.assertEqual(doc["confirmedScoops"], 0)
        self.assertEqual(sum(doc["counts"].values()), len(rows))

    def test_material_correction_is_checked_for_its_own_coverage(self):
        # 두산에너빌리티 20261026800529(10-31 운영): 원 계약 기사는 있으나 정정(계약기간 종료일 +7개월) 기사는 따로 찾아야 했다
        now = dt.datetime(2026, 10, 31, 7, 10, tzinfo=KST)
        fix = {"reason": "계약기간 종료일 변경", "changes": [["계약기간 - 종료일", "2029-07-01", "2030-01-28"]], "material": ["종료일 +7개월"]}
        row = {"id": "clue:ds", "kind": "단서", "company": "두산에너빌리티", "title": "두산에너빌리티 [기재정정]단일판매ㆍ공급계약체결",
               "url": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261026800529", "published": "2026-10-26",
               "terms": ["영광", "야월", "해상풍력"], "alts": {}, "verdict": "관련 보도 있음", "filing": {"type": "공급계약", "correction": fix}}
        cc = s.correction_check_of(row)
        self.assertEqual((cc["terms"], cc["must"], cc["since"], cc["queries"]),
                         (["연장"], ["영광", "야월"], "2026-10-26", ["두산에너빌리티 영광 야월", "두산에너빌리티 야월 연장"]))
        seen = []

        def get(url, params=None, headers=None, timeout=None):
            if "naverapihub" in url:
                seen.append(params["query"])
                return R(200, {"items": [
                    {"title": "두산에너빌리티, 영광 야월 해상풍력 EPC 5750억 수주", "description": "", "originallink": "https://n/old",
                     "pubDate": "Wed, 31 Dec 2025 09:00:00 +0900"},
                    {"title": "두산에너빌리티 해상풍력 공사기간 연장", "description": "신안 우이 해상풍력", "originallink": "https://n/other",
                     "pubDate": "Tue, 27 Oct 2026 09:00:00 +0900"}]})
            return R(200, content=b"<rss><channel></channel></rss>")
        with patch.dict(os.environ, {"NAVER_CLIENT_ID": "i", "NAVER_CLIENT_SECRET": "k"}):
            rows, n = s.check_corrections([row], now=now, get=get, sleep=lambda x: None)
        got = rows[0]["correctionCheck"]
        self.assertEqual((n, seen, got["word"], got["verdict"]), (1, cc["queries"], "연장", "미보도 후보"))
        # 원 계약 기사(정정 전)는 판정에 안 세고, 다른 해상풍력(신안 우이) 연장 기사는 사업 낱말이 없어 약한 근거
        self.assertEqual([e["url"] for e in got["evidence"]], ["https://n/other"])
        self.assertIn("영광·야월 없음", got["evidence"][0]["why"])

        def hit(url, params=None, headers=None, timeout=None):
            if "naverapihub" in url:
                return R(200, {"items": [{"title": "두산에너빌리티, 영광 야월 해상풍력 계약기간 7개월 연장", "description": "",
                                          "originallink": "https://n/hit", "pubDate": "Thu, 29 Oct 2026 09:00:00 +0900"}]})
            return R(200, content=b"<rss><channel></channel></rss>")
        row.pop("correctionCheck")
        with patch.dict(os.environ, {"NAVER_CLIENT_ID": "i", "NAVER_CLIENT_SECRET": "k"}):
            rows, _ = s.check_corrections([row], now=now, get=hit, sleep=lambda x: None)
        self.assertEqual(rows[0]["correctionCheck"]["verdict"], "관련 보도 있음")
        # 가이던스 정정(공정공시): '하향' 낱말, 실적 기사의 '매출 축소'는 근거가 아니고, 제목에 사업 낱말이 있는 기사가 앞
        guide = {"id": "clue:hm", "kind": "단서", "company": "현대차", "title": "현대자동차 · [기재정정]장래사업ㆍ경영계획(공정공시)",
                 "url": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261029800231", "published": "2026-10-29", "terms": ["가이던스"],
                 "alts": {}, "verdict": "관련 보도 있음",
                 "filing": {"type": "공정공시", "correction": {"reason": "2026년 가이던스 업데이트", "material": ["예상투자금액 -10%"]}}}
        self.assertEqual(s.correction_check_of(guide)["queries"], ["현대차 가이던스", "현대차 가이던스 하향"])

        def news(url, params=None, headers=None, timeout=None):
            if "naverapihub" in url:  # 10-31 운영에서 실제로 잡힌 제목들
                return R(200, {"items": [
                    {"title": "파업 차질 현실화…현대차, 3분기 영업익 늘었지만 매출 축소", "description": "연간 가이던스는 유지",
                     "originallink": "https://n/strike", "pubDate": "Thu, 29 Oct 2026 15:00:00 +0900"},
                    {"title": "현대차, 매출 줄었지만 영업익 증가…연간 목표 판매량은 '하향조정'", "description": "가이던스를 낮췄다",
                     "originallink": "https://n/hk", "pubDate": "Thu, 29 Oct 2026 16:00:00 +0900"},
                    {"title": "현대차, 2026년 연간 영업이익률 가이던스 하향 조정", "description": "",
                     "originallink": "https://n/g", "pubDate": "Fri, 30 Oct 2026 09:00:00 +0900"}]})
            return R(200, content=b"<rss><channel></channel></rss>")
        with patch.dict(os.environ, {"NAVER_CLIENT_ID": "i", "NAVER_CLIENT_SECRET": "k"}):
            rows, _ = s.check_corrections([guide], now=now, get=news, sleep=lambda x: None)
        g = rows[0]["correctionCheck"]
        self.assertEqual((g["word"], g["verdict"], [e["url"] for e in g["evidence"]]), ("하향", "관련 보도 있음", ["https://n/g", "https://n/hk"]))
        # 낱말 고르기: 해지 > 금액 > 기간, 취득완료로 당겨지면 '완료'
        self.assertEqual(s.change_word({"material": ["계약금액 -40%", "사유에 해지·취소"]}), "해지")
        self.assertEqual(s.change_word({"material": ["예상투자금액 -10%"]}), "감액")
        self.assertEqual(s.change_word({"material": ["취득예정일자 -36개월"], "reason": "취득완료(취득가액 및 취득일자 확정)에 따른 정정"}), "완료")
        self.assertIsNone(s.change_word({"changes": [["a", "1", "2"]]}))
        self.assertEqual(s.change_word({"material": ["계약기간 확정"]}), "착공")  # 착공지시서 수령으로 기간이 정해짐
        self.assertIsNone(s.change_word({"material": ["계약상대 공개(현대건설)", "공시유보 해제"]}))  # 기사는 상대 이름을 쓴다
        # 미보도 후보(원 공시도 못 찾음)·큰 변경 없음·사업 낱말 없음은 다시 찾지 않는다
        for other in ({**row, "verdict": "미보도 후보"}, {**row, "filing": {"correction": {"material": []}}}, {**row, "terms": ["수주", "공급계약"]}):
            self.assertEqual(s.check_corrections([dict(other)], now=now, get=get, sleep=lambda x: None)[1], 0)

    def test_without_naver_everything_is_unconfirmed(self):
        def get(url, params=None, headers=None, timeout=None):
            return R(200, content=b"<rss><channel></channel></rss>")
        with patch.dict(os.environ, {"NAVER_CLIENT_ID": "", "NAVER_CLIENT_SECRET": ""}):
            rows = s.screen(s.select(CLUES, STATS, now=NOW), now=NOW, get=get, sleep=lambda x: None)
        self.assertTrue(all(r["verdict"] == "미확인" for r in rows))

    def test_lawsuit_filing_is_rechecked_with_case_name_and_outcome(self):
        facts = [["사건의명칭", "주주대표소송(손해배상)"], ["사건번호", "2025가합10683"],
                 ["판결ㆍ결정내용", "[주문] 1. 원고 공동소송참가인의 공동소송참가신청을 각하한다. 2. 원고의 주위적 및 예비적 청구를 모두 기각한다."]]
        row = {"id": "clue:kz", "kind": "단서", "company": "고려아연", "title": "고려아연 · 소송등의판결ㆍ결정", "terms": ["소송등의판결"],
               "alts": {}, "numbers": [], "ratios": [], "unit": "", "strength": 3, "verdict": "미보도 후보",
               "queries": ["고려아연 소송등의판결"], "filing": {"type": "소송판결", "facts": facts}}
        terms, alts = s.lawsuit_terms(row)
        self.assertEqual(terms, ["주주대표소송", "기각"])  # 기각 is the main ruling here; 각하 was only for the joint-party motion
        self.assertIn("손해배상", alts["주주대표소송"])
        self.assertIn("승소", alts["기각"])

        def get(url, params=None, headers=None, timeout=None):
            if "naverapihub" in url:
                hit = "주주대표소송" in params["query"]
                items = [{"title": "고려아연 8300억 주주대표소송 1심 기각…영풍, 즉각 항소", "description": "", "originallink": "https://n/kz",
                          "pubDate": "Thu, 22 Oct 2026 15:00:00 +0900"}] if hit else []
                return R(200, {"items": items})
            return R(200, content=b"<rss><channel></channel></rss>")
        with patch.dict(os.environ, {"NAVER_CLIENT_ID": "i", "NAVER_CLIENT_SECRET": "k"}):
            out, n = s.recheck_lawsuits([row], now=NOW, get=get, sleep=lambda x: None)
        self.assertEqual(n, 1)
        self.assertEqual(out[0]["verdict"], "미확인")
        self.assertEqual(out[0]["queries"], ["고려아연 2025가합10683", "고려아연 주주대표소송"])
        self.assertEqual((out[0]["firstVerdict"], out[0]["firstQueries"]), ("미보도 후보", ["고려아연 소송등의판결"]))
        self.assertEqual(out[0]["filing"]["type"], "소송판결")

    def test_group_headline_short_names_count_when_the_body_names_the_company(self):
        # 10-28 아이뉴스24 「0%→19.87%로 뛴 美 관세…세아·현대, 국제무역법원 제소」 — 10-31 운영에서 세아제강·현대제철 소송이
        # '본문에만' 약한 근거로 미보도 후보(A)에 남았다
        art = {"title": "0%→19.87%로 뛴 美 관세…세아·현대, 국제무역법원 제소", "url": "https://www.inews24.com/view/2020330", "date": "2026-10-28",
               "text": "세아제강과 현대제철이 미국 국제무역법원(CIT)에 소송을 냈다."}
        now = dt.datetime(2026, 10, 31, 7, 10, tzinfo=KST)
        for who in ("세아제강", "현대제철"):
            c = {"id": f"cl:{who}", "company": who, "terms": ["국제무역법원", "소송"], "alts": {"소송": ["소송", "제소", "판결", "항소"]},
                 "numbers": [], "unit": "", "strict": True, "generic": [], "since": "2026-10-20", "title": "x"}
            verdict, ev = s.judge(c, channels([art]), now=now)
            self.assertEqual((verdict, ev[0]["why"]), ("관련 보도 있음", "제목에 회사·낱말(국제무역법원, 소송) — 동일 사건 미확정"), who)
        # 줄임만 있고 본문에 정식 이름이 없으면 그 회사로 보지 않는다(현대 → 현대차·현대모비스일 수 있음)
        other = {**art, "text": "현대자동차그룹 계열사가 소송을 냈다."}
        c = {"id": "cl:h", "company": "현대제철", "terms": ["국제무역법원", "소송"], "alts": {"소송": ["소송", "제소"]}, "numbers": [], "unit": "",
             "strict": True, "generic": [], "since": "2026-10-20", "title": "x"}
        self.assertEqual(s.judge(c, channels([other]), now=now)[0], "미보도 후보")
        self.assertFalse(s.company_in_title("현대제철", "현대차, 국제무역법원 제소", "현대제철도"))  # '현대차'의 '현대'는 줄임이 아님

    def test_domestic_recall_is_searched_by_model_strictly(self):
        # 10-31 운영 단서(clues.json 384a5fb21a248f1e) + 공지 줄(scoop.json details)
        clue = {"id": "384a5fb21a248f1e", "team": "자동차", "published": "2026-10-30", "source": "자동차리콜센터(국토교통부·자동차안전연구원)",
                "title": "기아, 10월 30일 리콜 공지 1건 — [기아] 쏘렌토 - 저압연료라인 어셈블리 관련 리콜 중대리콜(화재위험)",
                "url": "https://car.go.kr/ri/stat/list.do?ctype=O&currentPageNo=1&searchProductName=%EC%8F%98%EB%A0%8C%ED%86%A0",
                "companies": ["기아"], "tier": "공개 원자료 추적"}
        c = s.from_clue(clue)
        self.assertEqual((c["kind"], c["terms"], c["must"], c["since"]), ("리콜", ["쏘렌토", "리콜", "저압연료라인"], ["쏘렌토"], "2026-10-27"))
        self.assertEqual(s.queries(c), ["기아 쏘렌토", "기아 쏘렌토 리콜"])
        now = dt.datetime(2026, 10, 31, 7, 10, tzinfo=KST)
        iccu = {"title": "전기차 리콜 후에도 결함 재발…현대차·기아 ICCU 부실 대응 도마 위", "text": "", "url": "i", "date": "2026-10-27"}
        launch = {"title": "기아, 쏘렌토 하이브리드 판매 호조", "text": "", "url": "l", "date": "2026-10-28"}
        verdict, ev = s.judge(c, channels([iccu, launch]), now=now)
        self.assertEqual(verdict, "미보도 후보")  # 다른 차종 리콜(ICCU)·리콜 아닌 쏘렌토 기사는 같은 리콜이 아니다
        self.assertEqual([e["url"] for e in ev], ["i"])  # 약한 근거로만
        hit = {"title": "기아 쏘렌토 1만대 리콜…저압연료라인 화재 위험", "text": "", "url": "h", "date": "2026-10-30"}
        self.assertEqual(s.judge(c, channels([iccu, hit]), now=now)[0], "관련 보도 있음")
        # 차종을 못 읽으면 일반 단서, 다른 줄 형식의 부품 낱말
        self.assertIsNone(s.recall_candidate({**clue, "url": "https://car.go.kr/ri/stat/list.do", "title": "기아, 10월 30일 리콜 공지 1건"}, "기아", "기아, 10월 30일 리콜 공지 1건"))
        ion = s.recall_candidate({**clue, "url": "https://car.go.kr/x?searchProductName=%EC%95%84%EC%9D%B4%EC%98%A4%EB%8B%89"}, "현대차",
                                 "현대차, 10월 14일 리콜 공지 1건 — [현대] 아이오닉9 - 2열 및 3열 전동시트 제어기 관련 리콜")
        self.assertEqual(ion["terms"], ["아이오닉", "리콜", "전동시트"])
        # 미국 리콜 단서(해외 원자료, 10-31 운영 26V692000): 차종으로 찾고, 같은 차종이 기사에 있어야
        us = {"id": "e33ee9a7dca58d62", "team": "해외", "published": "2026-10-20", "source": "해외 원자료", "tier": "취재 단서·단독 미확정",
              "title": "미국 리콜 26V692000 · ELANTRA·TUCSON HYBRID · 국내 동일 부품/시정조치 대조 필요", "companies": ["현대차", "기아"],
              "url": "https://api.nhtsa.gov/recalls/campaignNumber?campaignNumber=26V692000"}
        uc = s.from_clue(us)
        self.assertEqual((uc["kind"], uc["terms"], uc["must"]), ("리콜", ["아반떼", "리콜"], ["아반떼", "엘란트라", "투싼"]))
        self.assertEqual(s.queries(uc), ["현대차 아반떼", "현대차 아반떼 리콜"])
        airbag = {"title": "현대차 '측면 에어백 센서' 리콜 남아공 확산…美·호주 이어 투싼 253대", "text": "", "url": "a", "date": "2026-10-21"}
        # 같은 차종(투싼)이 있으면 관련 보도로 남는다 — 차종 수준 대조의 한계(결함 부품은 맞추지 않음)
        self.assertEqual(s.judge(uc, channels([airbag]), now=now)[0], "관련 보도 있음")
        other = {"title": "현대차, 美서 팰리세이드 리콜", "text": "", "url": "o", "date": "2026-10-21"}
        self.assertEqual(s.judge(uc, channels([other]), now=now)[0], "미보도 후보")
        self.assertEqual(s.us_recall_models("G80 · GENESIS"), ["G80"])
        self.assertIsNone(s.recall_candidate({**us, "title": "미국 리콜 26V692000 · 국내 동일 부품/시정조치 대조 필요"}, "현대차",
                                             "미국 리콜 26V692000 · 국내 동일 부품/시정조치 대조 필요"))

    def test_asset_filing_is_searched_by_its_place(self):
        # 금호타이어 20261027800641 [기재정정]유형자산취득결정(자율공시) — 10-31 운영 원문 요점 그대로
        facts = [["취득물건구분", "토지 및 건물"], ["취득물건명", "전라남도 함평군 빛그린국가산업단지 2단계 사업구역 소재 토지"],
                 ["취득가액(원)", "116,081,801,890"], ["거래상대", "한국토지주택공사(LH)"], ["취득목적", "금호타이어 광주공장 이전 신부지 확보"]]
        row = {"id": "clue:kt", "kind": "단서", "company": "금호타이어", "title": "금호타이어 · [기재정정]유형자산취득결정(자율공시)",
               "terms": ["투자"], "alts": {"투자": ["투자", "취득", "증설"]}, "numbers": [], "ratios": [], "unit": "", "strength": 1,
               "published": "2026-10-27", "filing": {"type": "유형자산취득", "facts": facts}}
        terms, alts = s.asset_terms(row)
        self.assertEqual(terms, ["부지", "함평", "투자"])
        row.update(terms=terms, alts=alts)
        self.assertEqual(s.queries(row), ["금호타이어 부지", "금호타이어 부지 함평"])
        hit = {"title": "금호타이어 함평 이전 부지 1160억원에 취득 완료", "text": "", "url": "v", "date": "2026-10-28"}
        report = {"title": "[리포트 브리핑]금호타이어, '마진 방어 상에서 EU 반덤핑 관세 영향이라는 변수' 목표가 8,300원",
                  "text": "투자 의견", "url": "r", "date": "2026-10-30"}
        verdict, ev = s.judge(row, channels([report, hit]), now=dt.datetime(2026, 10, 31, 7, 10, tzinfo=KST))
        self.assertEqual((verdict, [e["url"] for e in ev]), ("관련 보도 있음", ["v"]))  # 리포트 기사는 근거가 아님
        # 시·군을 못 읽으면 그대로, 토지가 아니면 제목 낱말 + 시·군
        self.assertIsNone(s.asset_terms({**row, "filing": {"type": "유형자산취득", "facts": [["취득물건명", "기계장치"]]}}))
        plant = {**row, "terms": ["투자"], "filing": {"type": "신규시설투자", "facts": [["투자구분", "신규시설투자"],
                 ["투자대상", "충청북도 청주시 흥덕구 배전 공장 증설"], ["투자목적", "생산능력 확대"]]}}
        self.assertEqual(s.asset_terms(plant)[0], ["투자", "청주"])
        self.assertEqual(s.asset_terms({**plant, "filing": {"type": "유형자산처분", "facts": [["처분물건구분", "토지"],
                         ["처분물건명", "광주광역시 광산구 소촌동 공장 부지"]]}})[0], ["부지", "광주", "투자"])
        self.assertIsNone(s.asset_terms({**row, "filing": {"type": "공급계약", "facts": facts}}))
        # '투자'는 증권사 이름·투자의견 속에서 맞지 않는다(그 전에는 '금호타이어 투자' 질의의 근거가 이 리포트 기사였다)
        plain_row = {**row, "terms": ["투자"], "alts": {"투자": ["투자", "취득", "증설"]}}
        broker = {"title": "[리포트 브리핑]금호타이어, 목표가 8,300원 - 한화투자증권 - 뉴스핌", "text": "투자의견 매수", "url": "b", "date": "2026-10-30"}
        self.assertEqual(s.judge(plain_row, channels([broker]), now=dt.datetime(2026, 10, 31, 7, 10, tzinfo=KST))[1], [])
        real = {"title": "금호타이어, 함평 신공장에 4천억 투자", "text": "", "url": "i", "date": "2026-10-30"}
        self.assertEqual([e["url"] for e in s.judge(plain_row, channels([broker, real]), now=dt.datetime(2026, 10, 31, 7, 10, tzinfo=KST))[1]], ["i"])
        self.assertEqual(s.event_text("투자자산 투자자 보호"), "투자자산 · 보호")

    def test_trade_plan_is_searched_by_the_reporting_holder(self):
        row = {"id": "clue:yp", "kind": "단서", "company": "영풍", "title": "영풍 · 임원ㆍ주요주주특정증권등거래계획보고서",
               "terms": ["거래계획"], "alts": {}, "numbers": [], "ratios": [], "unit": "", "strength": 1,
               "filing": {"type": "거래계획", "facts": [["보고자", "장세환"], ["거래시작일(결제일)", "2026년 11월 27일"]]}}
        terms, alts = s.holder_terms(row)
        self.assertEqual(terms, ["장세환", "지분"])
        row.update(terms=terms, alts=alts)
        self.assertEqual(s.queries(row), ["영풍 장세환", "영풍 장세환 지분"])
        art = {"title": "영풍 오너일가 장세환, 75억 원 규모 지분 매수 추진", "text": "", "url": "f", "date": "2026-10-29"}
        self.assertEqual(s.judge(row, channels([art]), now=dt.datetime(2026, 10, 31, 7, 10, tzinfo=KST))[0], "관련 보도 있음")
        # 이름을 못 읽은 표지·회사 자신·다른 종류는 None
        for facts in ([["보고자", "(성 명)"]], [["보고자", "영풍"]], []):
            self.assertIsNone(s.holder_terms({**row, "filing": {"type": "거래계획", "facts": facts}}))
        self.assertEqual(s.holder_terms({**row, "filing": {"type": "거래계획", "facts": [["보고자", "주식회사 에이치씨"]]}})[0],
                         ["에이치씨", "지분"])
        # '성명' 칸(연락 담당자일 수 있음)은 보고자로 쓰지 않는다
        self.assertIsNone(s.holder_terms({**row, "filing": {"type": "거래계획", "facts": [["보고자", "(성 명)"], ["성명", "권순광"]]}}))
        self.assertIsNone(s.holder_terms({**row, "filing": {"type": "채무보증", "facts": [["보고자", "장세환"]]}}))
        # 근거 기사 순서: 공시 날짜(10-28) 이후 기사가 앞, 그 전 기사는 최근 순 — 3~4월 지분 기사가 이번 기사를 밀어내지 않게
        row["published"] = "2026-10-28"
        old = [{"title": f"주요주주 장세환, 영풍 주식 보유 증가 {i}", "text": "", "url": f"o{i}", "date": f"2026-0{i}-10"} for i in range(3, 9)]
        verdict, ev = s.judge(row, channels(old + [art]), now=dt.datetime(2026, 10, 31, 7, 10, tzinfo=KST))
        self.assertEqual([e["url"] for e in ev], ["f", "o8", "o7", "o6", "o5"])
        self.assertIsNone(s.holder_terms({**row, "filing": {"type": "거래계획", "error": "원문 조회 실패 — 미확인"}}))

    def test_lawsuit_filing_variants_and_non_lawsuits(self):
        sue = {"filing": {"type": "소송제기", "facts": [["사건의명칭", "손해배상청구의 소"]]}}
        self.assertEqual(s.lawsuit_terms(sue)[0], ["손해배상청구", "소송"])
        paid = {"filing": {"type": "소송판결", "facts": [["사건의명칭", "물품대금"], ["판결ㆍ결정내용", "피고는 원고에게 10억원을 지급하라."]]}}
        self.assertEqual(s.lawsuit_terms(paid)[0], ["물품대금", "인용"])
        self.assertIsNone(s.lawsuit_terms({"filing": {"type": "채무보증", "facts": []}}))
        self.assertIsNone(s.lawsuit_terms({"filing": {"type": "소송판결", "facts": [["사건의명칭", "()"]]}}))
        rows, n = s.recheck_lawsuits([{"id": "x", "terms": ["a"], "verdict": "미보도 후보", "strength": 1}], now=NOW, get=None)
        self.assertEqual(n, 0)

    def test_push_sends_bearer_token_to_private_ingest(self):
        seen = {}
        def post(url, data, headers, timeout):
            seen.update(url=url, auth=headers["Authorization"], body=data)
            return R(200)
        self.assertEqual(s.push({"schema": "scoop_screen/v1"}, "tok", post=post), 200)
        self.assertTrue(seen["url"].endswith("/ingest/scoop-screen"))
        self.assertEqual(seen["auth"], "Bearer tok")


if __name__ == "__main__":
    unittest.main()
