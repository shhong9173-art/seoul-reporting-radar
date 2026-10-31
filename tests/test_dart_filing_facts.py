"""DART exchange disclosure facts: real table layouts (2026-10 filings), period labels, related-filing pointer,
same-counterparty comparison, routine guarantees, failures kept as 미확인."""
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import dart_filing_facts as f  # noqa: E402


def table(rows):
    def cell(c):
        if isinstance(c, tuple):
            text, rowspan = c
            return f'<TD ROWSPAN="{rowspan}">{text}</TD>'
        return f"<TD>{c}</TD>"
    return "<TABLE>" + "".join("<TR>" + "".join(cell(c) for c in r) + "</TR>" for r in rows) + "</TABLE>"


# Rows as read from HD현대일렉트릭 20261026800468 (타인에대한채무보증결정), 2026-10-27.
HDE = table([["1. 채무자", "유럽법인(HD Hyundai Electric Europe GmbH)"], ["- 회사와의 관계", "자회사"],
             ["2. 채권자", "ING Bank, a branch of ING-DiBa AG, Germany"], ["3. 채무(차입)금액(원)", "44,514,300,000"],
             [("4. 채무보증내역", 6), "채무보증금액(원)", "53,417,160,000"], ["자기자본(원)", "2,032,934,924,019"],
             ["자기자본대비(%)", "2.63"], ["대규모법인여부", "해당"], [("채무보증기간", 2), "시작일", "2026-11-01"], ["종료일", "2027-11-01"],
             ["5. 채무보증 총 잔액(원)", "542,037,341,654"], ["6. 이사회결의일(결정일)", "2026-10-26"], ["※ 관련공시", "-"],
             ["※ 관련 공시법규", "자본시장법"]])
HDE_PREV = table([["1. 채무자", "유럽법인(HD Hyundai Electric Europe GmbH)"], ["- 회사와의 관계", "자회사"],
                  [("4. 채무보증내역", 3), "채무보증금액(원)", "48,000,000,000"], ["자기자본대비(%)", "2.90"]])
OTHER_PREV = table([["1. 채무자", "미국법인(Hyundai Power Transformers USA)"], ["- 회사와의 관계", "자회사"],
                    [("4. 채무보증내역", 3), "채무보증금액(원)", "120,000,000,000"], ["자기자본대비(%)", "6.10"]])
# 고려아연 20261023801005 (소송등의판결ㆍ결정)
KZ = table([["1. 사건의 명칭", "주주대표소송(손해배상)", "사건번호", "2025가합10683"],
            ["2. 원고ㆍ신청인", "원고: 주식회사 한국기업투자홀딩스 원고공동소송참가인: 주식회사 엠제이파트너스 피고: 최**"],
            ["3. 판결ㆍ결정내용", "[주문] 1. 원고 공동소송참가인의 공동소송참가신청을 각하한다. " + "가" * 200],
            ["5. 관할법원", "서울중앙지방법원"], ["6. 판결ㆍ결정일자", "2026-10-22"],
            ["※ 관련공시", "2026-06-10 소송 등의 제기ㆍ신청(경영권 분쟁 소송)"]])
# 엘에스일렉트릭 20261019800108 (단일판매ㆍ공급계약체결)
LSE = table([["1. 판매ㆍ공급계약 구분", "기타 판매ㆍ공급계약"], ["- 체결계약명", "2027년 북미 데이터센터 전력설비 공급 PJT"],
             [("2. 계약내역", 3), "계약금액(원)", "168,871,711,050"], ["최근매출액(원)", "4,965,798,552,980"], ["매출액대비(%)", "3.40"],
             ["3. 계약상대", "LS ELECTRIC AMERICA Inc."], ["- 회사와의 관계", "자회사"], ["4. 판매ㆍ공급지역", "미국"],
             [("5. 계약기간", 2), "시작일", "2026-10-16"], ["종료일", "2027-12-31"], ["※ 관련공시", "2026-04-13 단일판매ㆍ공급계약체결"]])

# OCI홀딩스 20261029800315 ([기재정정]수시공시의무관련사항(공정공시)), 2026-10-31: 정정 표 다음에 본문 표
OCI_FAIR = (table([["정정일자", "2026-10-29"], ["1. 정정관련 공시서류", "수시공시의무관련사항(공정공시)"],
                   ["정정항목", "정정전", "정정후"], ["1. 정보내용 - 관련 수시공시내용", "-", "- 당사는 정정일자 기준으로 본 주주환원 정책의 이행을 완료하였으며"]])
            + table([[("1. 정보내용", 2), "공시제목", "2024년 ~ 2026년 자기주식 취득 및 소각 계획"],
                     ["관련 수시공시내용", "- 당사는 중장기 주주환원 정책을 수립중에 있으며"], ["예정 공시 일시", "2024-03-29"]]))
# 현대자동차 20261029800231 ([기재정정]장래사업ㆍ경영계획(공정공시)), 2026-10-31
HMC_PLAN = (table([["정정일자", "2026-10-29"], ["2.주요내용 및 추진 일정 - 세부내용", "·2026년 판매목표 : 416만대", "·2026년 판매목표 : 400만대"]])
            + table([["1. 장래계획 사항", "2026년 현대자동차 가이던스"], [("2. 주요내용 및 추진일정", 2), "목적", "2026년 경영계획 공개를 통한 투자자 이해 제고"],
                     ["세부내용", "◎ 판매, 수익성, 투자 등 2026년 주요 경영 계획 및 정책 방향성 ·2026년 판매목표 : 400만대"]]))


class R:
    def __init__(self, body, code=200):
        self.body, self.status_code = body, code

    def json(self):
        return self.body


class Facts(unittest.TestCase):
    def test_guarantee_fields_and_period(self):
        x = f.facts("타인에대한채무보증결정", [HDE])
        got = dict(x["facts"])
        self.assertEqual(x["type"], "채무보증")
        self.assertEqual(got["채무자"], "유럽법인(HD Hyundai Electric Europe GmbH)")
        self.assertEqual(got["채무보증금액(원)"], "53,417,160,000원(약 534억원)")
        self.assertEqual(got["자기자본대비(%)"], "2.63")
        self.assertEqual((got["채무보증기간 시작일"], got["채무보증기간 종료일"]), ("2026-11-01", "2027-11-01"))
        self.assertEqual(got["채무보증총잔액(원)"], "542,037,341,654원(약 5,420억원)")
        self.assertIsNone(x["related"])  # '-' is not a related filing, and the statute line is not one either (real run 2026-10-27)

    def test_lawsuit_four_cell_row_related_and_truncation(self):
        x = f.facts("소송등의판결ㆍ결정", [KZ])
        got = dict(x["facts"])
        self.assertEqual((got["사건의명칭"], got["사건번호"]), ("주주대표소송(손해배상)", "2025가합10683"))
        self.assertTrue(got["판결ㆍ결정내용"].endswith("…") and len(got["판결ㆍ결정내용"]) == 158)
        self.assertEqual(x["related"], "2026-06-10 소송 등의 제기ㆍ신청(경영권 분쟁 소송)")

    def test_supply_contract(self):
        got = dict(f.facts("단일판매ㆍ공급계약체결", [LSE])["facts"])
        self.assertEqual(got["계약금액(원)"], "168,871,711,050원(약 1,689억원)")
        self.assertEqual(got["매출액대비(%)"], "3.40")
        self.assertEqual(got["계약상대"], "LS ELECTRIC AMERICA Inc.")
        self.assertEqual(got["계약기간 종료일"], "2027-12-31")

    def test_fair_disclosure_subject_is_read_from_the_body(self):
        x = f.facts("[기재정정]수시공시의무관련사항(공정공시)", [OCI_FAIR])
        got = dict(x["facts"])
        self.assertEqual(x["type"], "공정공시")
        self.assertEqual(got["공시제목"], "2024년 ~ 2026년 자기주식 취득 및 소각 계획")
        self.assertTrue(got["관련수시공시내용"].startswith("- 당사는 중장기"))  # the body table, not the correction table
        got = dict(f.facts("[기재정정]장래사업ㆍ경영계획(공정공시)", [HMC_PLAN])["facts"])
        self.assertEqual(got["장래계획사항"], "2026년 현대자동차 가이던스")
        self.assertIn("400만대", got["세부내용"])
        self.assertEqual(f.filing_type("기타경영사항(자율공시)"), "공정공시")
        self.assertEqual(f.filing_type("투자판단관련주요경영사항"), "공정공시")
        self.assertEqual(f.filing_type("[기재정정]영업실적등에대한전망(공정공시)"), None)  # 실적 전망은 형식 공시(scoop_screen ADMIN)

    def test_types(self):
        self.assertEqual(f.filing_type("[기재정정]타인에대한채무보증결정"), "채무보증")
        self.assertEqual(f.filing_type("타법인주식및출자증권취득결정(자율공시)"), "타법인주식취득")
        self.assertEqual(f.filing_type("임원ㆍ주요주주특정증권등거래계획철회보고서"), "거래계획")
        self.assertIsNone(f.filing_type("영업양도결정"))  # not mapped yet: no facts rather than guessed ones


class LawsuitIdentity(unittest.TestCase):
    def test_same_case_name_different_case_number_is_not_the_same_lawsuit(self):
        other = table([["1. 사건의 명칭", "주주대표소송(손해배상)", "사건번호", "2025가합99999"], ["6. 판결ㆍ결정일자", "2026-10-22"]])
        same = table([["1. 사건의 명칭", "주주대표소송(손해배상)", "사건번호", "2025가합10683"], ["6. 판결ㆍ결정일자", "2026-03-02"]])
        cur = f.facts("소송등의판결ㆍ결정", [KZ])["raw"]
        lines, _ = f.compare("소송판결", cur, [({"date": "20261023", "rcept_no": "20261023800867"}, f.facts("소송등의판결ㆍ결정", [other])["raw"])], 1)
        self.assertFalse(any(l.startswith("같은 사건") for l in lines))
        lines, _ = f.compare("소송판결", cur, [({"date": "20260302", "rcept_no": "20260302800001"}, f.facts("소송등의판결ㆍ결정", [same])["raw"])], 1)
        self.assertTrue(lines[0].startswith("같은 사건(사건번호) 직전 공시 2026-03-02"))


class Enrich(unittest.TestCase):
    def run_enrich(self, docs, listing, cand=None):
        cand = cand or {"id": "clue:1", "kind": "단서", "company": "HD현대일렉트릭", "title": "HD현대일렉트릭 · 타인에대한채무보증결정",
                        "url": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261026800468"}
        def fetch_documents(key, rcept):
            if rcept not in docs:
                raise ValueError("no doc")
            return [docs[rcept]]
        def get(url, params=None, timeout=None):
            self.assertEqual(params["corp_code"], "01205851")
            self.assertEqual(params["pblntf_ty"], "I")
            return R(listing)
        corp = {"companies": {"HD현대일렉트릭": {"corp_code": "01205851"}}}
        f.enrich([cand], "k", corp, fetch_documents=fetch_documents, get=get)
        return cand["filing"]

    def test_same_subsidiary_repeat_small_ratio_is_routine(self):
        listing = {"status": "000", "total_page": 1, "list": [
            {"rcept_no": "20260601800100", "rcept_dt": "20260601", "report_nm": "타인에대한채무보증결정"},
            {"rcept_no": "20251103800200", "rcept_dt": "20251103", "report_nm": "타인에대한채무보증결정"},
            {"rcept_no": "20251001800300", "rcept_dt": "20251001", "report_nm": "단일판매ㆍ공급계약체결"}]}
        fl = self.run_enrich({"20261026800468": HDE, "20260601800100": OTHER_PREV, "20251103800200": HDE_PREV}, listing)
        self.assertEqual(fl["type"], "채무보증")
        self.assertIn("같은 채무자 직전 공시 2025-11-03(접수 20251103800200): 48,000,000,000원(약 480억원) → 53,417,160,000원(약 534억원)(+11%)", fl["compare"])
        self.assertIn("최근 3년 같은 종류 공시 2건(정정 포함, 목록 기준)", fl["compare"])
        self.assertEqual(fl["routine"], "같은 자회사 채무자 반복 보증 · 자기자본 대비 2.63%")

    def test_new_debtor_is_not_routine(self):
        listing = {"status": "000", "total_page": 1, "list": [{"rcept_no": "20260601800100", "rcept_dt": "20260601", "report_nm": "타인에대한채무보증결정"}]}
        fl = self.run_enrich({"20261026800468": HDE, "20260601800100": OTHER_PREV}, listing)
        self.assertIsNone(fl["routine"])
        self.assertEqual(fl["compare"], [
            "최근 3년 같은 종류 공시 1건(정정 포함, 목록 기준) 중 원문 1건 확인 — 같은 채무자 없음(확인한 범위 안)",
            "직전 같은 종류 공시 2026-06-01(접수 20260601800100) · 금액 120,000,000,000원(약 1,200억원)"])  # count said once

    def test_no_previous_and_list_failure_and_doc_failure(self):
        fl = self.run_enrich({"20261026800468": HDE}, {"status": "013", "message": "조회된 데이타가 없습니다."})
        self.assertEqual(fl["compare"], ["최근 3년 같은 종류 거래소 공시 없음(목록 기준)"])
        fl = self.run_enrich({"20261026800468": HDE}, {"status": "020", "message": "요청 제한"})
        self.assertEqual(fl["compare"], ["직전 공시 목록 조회 실패(RuntimeError) — 미확인"])
        self.assertIsNone(fl["routine"])
        fl = self.run_enrich({}, {"status": "013"})
        self.assertEqual(fl["error"], "원문 조회 실패(ValueError) — 미확인")

    def test_trading_plan_is_routine_by_type_and_non_dart_skipped(self):
        cand = {"id": "clue:2", "kind": "단서", "company": "GS", "title": "GS · 임원ㆍ주요주주특정증권등거래계획철회보고서",
                "url": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261023000362"}
        fl = self.run_enrich({"20261023000362": "<TABLE><TR><TD>보 고 자:</TD><TD>(성 명)</TD></TR></TABLE>"}, {"status": "013"}, cand)
        self.assertTrue(fl["routine"].startswith("임원·주요주주 거래계획 보고"))
        patent = {"id": "clue:3", "kind": "특허", "company": "기아", "title": "기아 · 고정자 냉각 장치", "url": "https://doi.org/x"}
        f.enrich([patent], "k", {}, fetch_documents=lambda *a: [], get=lambda *a, **k: None)
        self.assertNotIn("filing", patent)

    def test_fair_disclosure_skips_previous_comparison(self):
        cand = {"id": "clue:o", "kind": "단서", "company": "OCI홀딩스", "title": "OCI홀딩스 · [기재정정]수시공시의무관련사항(공정공시)",
                "url": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261029800315"}
        def get(*a, **k):
            raise AssertionError("no previous-filing list for fair disclosures")
        used = f.enrich([cand], "k", {}, fetch_documents=lambda k, r: [OCI_FAIR], get=get)
        self.assertEqual(used, 1)
        self.assertEqual((cand["filing"]["type"], cand["filing"]["compare"], cand["filing"]["routine"]), ("공정공시", [], None))
        self.assertEqual(dict(cand["filing"]["facts"])["공시제목"], "2024년 ~ 2026년 자기주식 취득 및 소각 계획")

    def test_budget_marks_unread(self):
        cands = [{"id": f"clue:{i}", "kind": "단서", "company": "X", "title": "X · 타인에대한채무보증결정",
                  "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo=2026102680046{i}"} for i in range(3)]
        f.enrich(cands, "k", {}, fetch_documents=lambda k, r: [HDE], get=lambda *a, **k: R({"status": "013"}), budget=1)
        self.assertIn("facts", cands[0]["filing"])
        self.assertEqual(cands[0]["filing"]["compare"], ["회사 고유번호 없음 — 직전 비교 못 함 — 미확인"])
        self.assertEqual(cands[2]["filing"]["error"], "원문 조회 예산 초과 — 미확인")


if __name__ == "__main__":
    unittest.main()
