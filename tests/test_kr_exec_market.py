import datetime as dt
import io
import sys
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import kr_exec_market as km  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 11, 5, 14, 30, tzinfo=KST)
WATCH = [{"name": "롯데카드", "aliases": ["롯데카드"], "reason": "2025년 해킹 사고"}]


def td(*cells):
    return "<TR>" + "".join(f"<TD>{c}</TD>" for c in cells) + "</TR>"


def table(*rows):
    return "<TABLE>" + "".join(rows) + "</TABLE>"


def zipped(text):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("doc.xml", text)
    return buf.getvalue()


DIRECTOR_IN = ("<P>독립이사의 선임ㆍ해임 또는 중도퇴임에 관한 신고</P>"
               + table(td("1. 독립이사 변경 발생일", "2026년 11월 04일"), td("2. 독립이사 변경 인원수", "선임ㆍ재선임(명)", "1"))
               + "<P>【독립이사 신규선임ㆍ재선임】</P>"
               + table(td("성명", "출생년월", "성별", "선임구분", "임기시작일", "임기", "독립이사총 재직기간(현 임기포함)", "주요경력 및 현직"),
                       td("김전무", "1962.03", "남", "신규", "2026.11.04", "3년", "0년", "- 2015~2022 현대자동차 구매본부장(전무) - 2023~현재 ○○대 교수"),
                       td("박교수", "1970.01", "여", "신규", "2026.11.04", "3년", "0년", "- ○○대 경영학과 교수")))
DIRECTOR_OUT = ("<P>독립이사의 선임ㆍ해임 또는 중도퇴임에 관한 신고</P>"
                + table(td("1. 독립이사 변경 발생일", "2026.11.03"))
                + "<P>【독립이사 해임ㆍ중도퇴임】</P>"
                + table(td("성명", "출생년월", "성별", "임기시작일", "임기만료 예정일", "해임ㆍ중도퇴임 사유"),
                        td("이사퇴", "1958.05", "남", "2025.03.20", "2028.03.19", "일신상의 사유로 중도퇴임")))
CEO = (table(td("1. 변경 전ㆍ후 대표이사(대표집행임원)", "변경전", "이동열, 최현수"), td("변경후", "최현수"),
             td("2. 변경사유", "- 이동열 대표이사 사임에 따른 변경"), td("3. 변경일자", "2026-11-04"))
       + table(td("성명", "최대주주와의 관계", "주요경력", "비고"), td("최현수", "-", "- 前 포스코 철강부문 부사장 - 現 ○○ 대표이사", "-")))
AGM = (table(td("의안", "후보자성명", "생년월일", "사외이사후보자여부", "감사위원회 위원인 이사 분리선출 여부", "최대주주와의 관계", "추천인"),
             td("3-1호", "최윤희", "1964-04-29", "사외이사", "미해당", "없음", "사외이사후보추천위원회"))
       + table(td("의안", "후보자성명", "생년월일", "사외이사후보자여부", "감사위원회 위원인 이사 분리선출 여부", "최대주주와의 관계", "추천인"),
               td("3-2-1호", "무뇨스 바르셀로 호세 안토니오(Munoz)", "1965-06-15", "사내이사", "미해당", "계열사 임원", "이사회"),
               td("3-2-2호", "이승조", "1969-11-24"), td("3-2-3호", "최현기", "1965-01-09"))
       + table(td("후보자성명", "주된직업", "세부경력", "해당법인과의최근3년간 거래내역"), td("기간", "내용"),
               td("최윤희", "건국대 교수", "2005년 ~ 현재", "- 건국대 교수", "없음"), td("2020년 ~ 현재", "- 롯데카드 사외이사"),
               td("무뇨스 바르셀로호세 안토니오", "현대자동차사장", "2018년 ~ 2019년", "- 닛산 전사성과총괄", "보통주 13,333주"))
       + table(td("후보자성명", "체납사실 여부", "부실기업 경영진 여부", "법령상 결격 사유 유무"),
               td("최윤희", "없음", "없음", "없음"), td("이승조", "해당사항 없음", "○○건설(2019 회생절차) 사내이사 재직", "해당사항 없음")))


class R:
    def __init__(self, body=None, content=None, status=200):
        self.status_code, self._body, self.content = status, body, content

    def json(self):
        return self._body

    def raise_for_status(self):
        pass


class Fake:
    def __init__(self, filings=(), docs=None, rosters=None, industry=None):
        self.filings, self.docs, self.rosters, self.ind, self.calls = list(filings), docs or {}, rosters or {}, industry or {}, []

    def __call__(self, url, params=None, **kw):
        ep = url.rsplit("/", 1)[-1]
        self.calls.append((ep, params.get("corp_code") or params.get("rcept_no") or params.get("pblntf_ty"), params.get("reprt_code")))
        if ep == "list.json":
            rows = [f for f in self.filings if f["ty"] == params["pblntf_ty"]]
            return R({"status": "000" if rows else "013", "total_page": 1, "list": rows})
        if ep == "document.xml":
            return R(content=zipped(self.docs[params["rcept_no"]]))
        if ep == "company.json":
            return R({"status": "000", "induty_code": self.ind.get(params["corp_code"], "")})
        if ep == "exctvSttus.json":
            got = self.rosters.get((params["corp_code"], int(params["bsns_year"]), params["reprt_code"]))
            return R(got or {"status": "013"})
        raise AssertionError(url)


def filing(ty, rc, nm, corp, code):
    return {"ty": ty, "rcept_no": rc, "report_nm": nm, "corp_name": corp, "corp_code": code, "rcept_dt": rc[:8]}


REGISTRY = {"companies": {"현대자동차": {"corp_code": "00164742"}}}


def run(g, previous=None, **kw):
    return km.run("k", now=NOW, previous=previous, get=g, sleep=lambda s: None, registry=REGISTRY, table=kw.pop("table", {}), watch=WATCH, **kw)


class CareerRules(unittest.TestCase):
    def test_beat_origin_needs_exec_title_in_same_segment(self):
        o = km.beat_origin("ㆍ조지워싱턴대 졸업 ㆍSK이노베이션 전략기획 과장 (2010~2018) ㆍ케이엠제약㈜ 대표 (2018~現)")
        self.assertEqual(o, [])                                         # 과장은 임원 직함이 아니다(뒤 마디의 '대표'와 섞지 않음)
        o = km.beat_origin("- 2015~2022 현대자동차 구매본부장(전무) - 2023~현재 ○○대 교수")
        self.assertEqual([(x["beat"], x["senior"]) for x in o], [("현대차", True)])
        self.assertEqual(km.beat_origin("현대자동차 협력사 대표"), [])      # 협력사 대표는 그 회사 출신이 아니다
        self.assertEqual(km.beat_origin("현대중공업 부사장"), [])            # 그룹 회사일 뿐 출입처 아님
        self.assertEqual([x["beat"] for x in km.beat_origin("前 두산중공업 부사장")], ["두산에너빌리티"])   # 옛 이름
        # 11-05 실제 자료(시알홀딩스 사외이사): '- 前' 이어 쓴 경력 — 포스코 직함은 '구매센터장'(고위 아님), 포스메이트 대표는 별개
        o = km.beat_origin("- 前 포스코건설 구매계약 임원- 前 포스코 동반성장 사무국장, 구매센터장- 前 포스메이트 대표이사- 前 포항공대법인 본부장")
        self.assertEqual([(x["beat"], x["senior"]) for x in o], [("포스코", False)])
        self.assertEqual([(x["beat"], x["senior"]) for x in km.beat_origin("포스코사장, 포스코차이나 대표법인장")], [("포스코", True)])

    def test_same_group_moves_are_not_flagged(self):
        flags, origins = km.person_flags("현대글로비스", "현대자동차 재경사업부장(상무)", WATCH)
        self.assertEqual((flags, origins), ([], []))
        flags, origins = km.person_flags("신화프리텍", "현대위아(주) 공작기계사업본부 상무", WATCH, industry="29")
        self.assertEqual([f["kind"] for f in flags], ["출입처 출신"])
        flags, _ = km.person_flags("부품사", "현대위아(주) 상무", WATCH, industry="30310")
        self.assertIn("같은 업종 회사", flags[0]["text"])
        self.assertEqual(km.area_of("2211"), "자동차")


class Parsers(unittest.TestCase):
    def test_director_filing(self):
        d = km.parse_director_filing(DIRECTOR_IN)
        self.assertEqual(d["date"], "2026-11-04")
        self.assertEqual([p["name"] for p in d["appointed"]], ["김전무", "박교수"])
        self.assertIn("현대자동차 구매본부장", d["appointed"][0]["career"])
        out = km.parse_director_filing(DIRECTOR_OUT)
        self.assertEqual((out["left"][0]["name"], out["left"][0]["reason"]), ("이사퇴", "일신상의 사유로 중도퇴임"))

    def test_ceo_change(self):
        c = km.parse_ceo_change(CEO)
        self.assertEqual((c["before"], c["after"], c["date"]), ("이동열, 최현수", "최현수", "2026-11-04"))
        self.assertIn("사임", c["reason"])
        self.assertIn("포스코 철강부문 부사장", c["people"][0]["career"])

    def test_ceo_change_second_form(self):
        doc = (table(td("1. 변경내용", "변경전 대표이사", "이다현, 최용인 (공동대표)"), td("변경후 대표이사", "최용인 (단독대표)"),
                     td("2. 변경사유", "일신상의 사유로 공동대표 이다현 사임"), td("3. 변경일", "2026-11-04"))
               + table(td("성명", "생년월일", "최대주주와의 관계", "주식수", "지분율", "비고"), td("최용인", "1980-07-11", "특수관계인", "-", "-", "-"))
               + table(td("성명", "회사명", "상호", "상장여부", "직위", "입사일", "퇴사일", "비고"),
                       td("최용인", "(주)포스코", "포스코", "비상장", "전무", "2010-01-01", "2022-02-15", "-")))
        c = km.parse_ceo_change(doc)
        self.assertEqual((c["before"], c["after"], c["date"]), ("이다현, 최용인 (공동대표)", "최용인 (단독대표)", "2026-11-04"))
        self.assertEqual(c["people"][0]["rel"], "특수관계인")
        self.assertIn("(주)포스코 전무", c["people"][0]["career"])
        self.assertEqual([x["beat"] for x in km.beat_origin(c["people"][0]["career"])], ["포스코"])

    def test_agm_candidates_with_merged_cells(self):
        c = {x["name"]: x for x in km.parse_agm_candidates(AGM)}
        self.assertEqual(set(c), {"최윤희", "무뇨스 바르셀로 호세 안토니오(Munoz)", "이승조", "최현기"})
        self.assertEqual((c["이승조"]["kind"], c["이승조"]["rec"]), ("사내이사", "이사회"))     # 합친 칸을 위 줄에서
        self.assertIn("롯데카드 사외이사", c["최윤희"]["career"])
        self.assertIn("닛산", c["무뇨스 바르셀로 호세 안토니오(Munoz)"]["career"])
        self.assertIn("회생", c["이승조"]["insolvent"])
        self.assertTrue(km.NONE.match(c["최윤희"]["insolvent"]))

    def test_agm_career_glued_cells_paired_probe192(self):
        # 탐침 192(출입처 소집공고 39건): 기간·내용 칸 안 여러 줄이 줄바꿈 없이 붙은 꼴(이름은 가상, 경력 글자는 실제 꼴)
        glued = table(td("후보자성명", "주된직업", "세부경력", "해당법인과의최근3년간 거래내역"), td("기간", "내용"),
                      td("황가상", "변호사", "24~현22~현15~2317~2212~17",
                         "고려아연㈜ 사외이사롯데웰푸드㈜ 사외이사서울고등법원 및 서울중앙지방법원 조정위원하나은행 사외이사한국법학원 상임이사", "해당사항 없음"),
                      td("최가상", "회장", "22~현21~2219~2114~1912~19",
                         "<P>고려아연㈜ 회장</P><P>고려아연㈜ 대표이사 부회장고려아연㈜ 대표이사 사장호주 SMC 대표이사 사장고려아연㈜ 부사장</P>", "해당사항 없음"),
                      td("김가상", "고문", "2012 ~ 20132013 ~ 20152022 ~ 20242024 ~ 현재",
                         "- KDB산업은행 본부장- 나무코프㈜ 대표이사- 법무법인(유) 현 고문- 성신양회(주) 고문", "-"),
                      td("박가상", "교수", "2019-현재2025-현재2014-2019",
                         "서울대학교 경영대학 교수생명보험사회공헌위원회 위원 교보생명 사외이사, 리스크관리위원회 위원 KPMG ACI 자문교수", "해당없음"))
        c = {x["name"]: x["career"] for x in km.parse_agm_candidates(glued)}
        self.assertEqual(c["황가상"], "'24~현재 고려아연㈜ 사외이사 / '22~현재 롯데웰푸드㈜ 사외이사 / '15~'23 서울고등법원 및 서울중앙지방법원 조정위원"
                                    " / '17~'22 하나은행 사외이사 / '12~'17 한국법학원 상임이사 해당사항 없음")
        self.assertTrue(c["최가상"].startswith("'22~현재 고려아연㈜ 회장 / '21~'22 고려아연㈜ 대표이사 부회장 / '19~'21 고려아연㈜ 대표이사 사장 / '14~'19 호주 SMC"))
        self.assertTrue(c["김가상"].startswith("2012~2013 KDB산업은행 본부장 / 2013~2015 나무코프㈜ 대표이사 / 2022~2024 법무법인(유) 현 고문 / 2024~현재 성신양회(주) 고문"))
        self.assertTrue(c["박가상"].startswith("기간(내용과 짝 안 맞음) 2019~현재 , 2025~현재 , 2014~2019 / 서울대학교 경영대학 교수"))   # 수가 안 맞으면 짝짓지 않는다
        # 따로 줄로 나오는 꼴(현대차)은 예전 그대로
        self.assertIn("2005년 ~ 현재 - 건국대 교수", {x["name"]: x for x in km.parse_agm_candidates(AGM)}["최윤희"]["career"])
        self.assertEqual(km.split_periods("2015년~현재 2019년~현재 1997년"), ["2015년~현재", "2019년~현재", "1997년"])
        self.assertEqual(km.split_periods("'14.12~'15.12 '16.07~현재"), ["'14.12~'15.12", "'16.07~현재"])
        self.assertIsNone(km.split_periods("2019년 3월 선임"))
        # 11-06 운영 재읽기에서 본 실제 꼴(고려아연 2026-08-11): 예전 경계로는 '교수부산항만공사'를 못 자르고 '회계감사본부'를 잘못 잘라 수만 맞았다
        self.assertEqual(km.pair_career("25~현07~현26~현26~현19~2319~23",
                                        "NH투자증권㈜ 독립이사상명대 경영경제대학 경제금융학부 교수부산항만공사 해외사업 리스크관리위원회 위원국방부 군인복지ㆍ연금기금 운용심의회 위원"
                                        "한국투자공사 운영위원신용보증기금 자산운용위원회 위원").split(" / ")[:3],
                         ["'25~현재 NH투자증권㈜ 독립이사", "'07~현재 상명대 경영경제대학 경제금융학부 교수", "'26~현재 부산항만공사 해외사업 리스크관리위원회 위원"])
        self.assertEqual(km.pair_career("22~현07~현20~2118~19", "조세심판원 비상임심판관성균관대 법학전문대학원 교수국제조세협회 이사장한국세법학회 회장"),
                         "'22~현재 조세심판원 비상임심판관 / '07~현재 성균관대 법학전문대학원 교수 / '20~'21 국제조세협회 이사장 / '18~'19 한국세법학회 회장")
        wrong = km.pair_career("26~현25~현21~2620-2496-20", "세진회계법인 회계ㆍ재무 자문단국대 데이터지식서비스공학과 산학협력교수한국 딜로이트 그룹 ESG센터장"
                                                         "한국 딜로이트 그룹 이사회 의장한국 딜로이트 그룹 회계감사본부, M&A 재무자문본부")
        self.assertTrue(wrong.startswith("기간(내용과 짝 안 맞음)"))           # 애매하면('자문단국대') 짝짓지 않는다 — 수만 맞춘 오짝 금지
        self.assertNotIn("/ 본부", wrong)


class Runs(unittest.TestCase):
    def fake(self):
        files = [filing("E", "20261104000229", "독립이사의선임ㆍ해임또는중도퇴임에관한신고", "부품사", "00999001"),
                 filing("E", "20261103000258", "독립이사의선임ㆍ해임또는중도퇴임에관한신고", "현대자동차", "00164742"),
                 filing("I", "20261104800578", "대표이사(대표집행임원)변경(안내공시)", "강판가공", "00999002"),
                 filing("E", "20260225005348", "주주총회소집공고", "현대자동차", "00164742"),
                 filing("E", "20260225009999", "주주총회소집공고", "남의회사", "00999003")]
        docs = {"20261104000229": DIRECTOR_IN, "20261103000258": DIRECTOR_OUT, "20261104800578": CEO, "20260225005348": AGM}
        return Fake(files, docs, industry={"00999001": "30310", "00999002": "24112"})

    def test_filings_flags_and_tiers(self):
        g = self.fake()
        doc = run(g, skip_roster=True)
        ev = {(e["source"], e["company"], e["person"].get("name")): e for e in doc["events"]}
        hire = ev[("독립이사 신고", "부품사", "김전무")]
        self.assertEqual(hire["tier"], "A")                   # 출입처 고위 임원(전무) 출신이 다른 회사 독립이사로(11-05 기자: 출입처 출신이 목적)
        self.assertEqual(hire["beat"], "현대차")
        self.assertNotIn(("독립이사 신고", "부품사", "박교수"), ev)   # 다른 회사는 표시 있는 사람만
        quit_ = ev[("독립이사 신고", "현대차", "이사퇴")]
        self.assertEqual(quit_["tier"], "A")                  # 출입처 독립이사 중도퇴임
        ceo = ev[("대표이사 변경", "강판가공", "최현수")]
        self.assertEqual(ceo["tier"], "A")                    # 포스코 부사장 출신이 다른 회사 대표로
        self.assertIn("변경 전 「이동열, 최현수」 → 변경 후 「최현수」", ceo["text"])
        bad = ev[("주총 소집공고", "현대차", "이승조")]
        self.assertEqual(bad["tier"], "A")
        self.assertIn("부실기업 경영진 여부 칸", bad["flags"][0]["text"])
        card = ev[("주총 소집공고", "현대차", "최윤희")]
        self.assertEqual(card["tier"], "A")                   # 주의 회사(롯데카드) 경력
        self.assertFalse([c for c in g.calls if c == ("document.xml", "20260225009999", None)])   # 출입처 아닌 회사 소집공고는 안 연다
        self.assertEqual(doc["counts"]["opened"], 4)
        again = run(self.fake(), previous=doc, skip_roster=True)
        self.assertEqual(again["counts"]["newEvents"], 0)
        self.assertEqual(again["counts"]["opened"], 0)        # 본 접수번호는 다시 열지 않는다

    def test_agm_backfill_reads_older_beat_notices_as_baseline(self):
        class Dated(Fake):   # 목록이 기간·회사로 거른다(실제 OpenDART처럼)
            def __call__(self, url, params=None, **kw):
                if url.endswith("list.json"):
                    self.calls.append(("list.json", params.get("corp_code") or params.get("pblntf_ty"), None))
                    rows = [f for f in self.filings if f["ty"] == params["pblntf_ty"] and params["bgn_de"] <= f["rcept_dt"] <= params["end_de"]
                            and (not params.get("corp_code") or f["corp_code"] == params["corp_code"])]
                    return R({"status": "000" if rows else "013", "total_page": 1, "list": rows})
                return super().__call__(url, params, **kw)
        files = [filing("E", "20260910000111", "임시주주총회소집공고", "현대자동차", "00164742"),
                 filing("E", "20260601000222", "주주총회소집공고", "현대자동차", "00164742"),     # 120일 밖
                 filing("E", "20260911000333", "임시주주총회소집공고", "남의회사", "00999003")]
        g = Dated(files, {"20260910000111": AGM})
        old = km.AGM_DAYS
        try:
            km.AGM_DAYS = 0
            off = run(g, skip_roster=True)
            self.assertEqual([e for e in off["events"] if e["source"] == "주총 소집공고"], [])   # 끄면 3일 목록만
            km.AGM_DAYS = 120
            doc = run(Dated(files, {"20260910000111": AGM}), skip_roster=True)
        finally:
            km.AGM_DAYS = old
        agm = [e for e in doc["events"] if e["source"] == "주총 소집공고"]
        self.assertTrue(agm)
        self.assertTrue(all(e.get("baseline") and e.get("filed") == "2026-09-10" for e in agm))   # 지난 공고 후보는 기준선(오늘의 레이더 X)
        self.assertEqual({e["url"][-14:] for e in agm}, {"20260910000111"})                       # 120일 밖·출입처 아닌 회사 공고는 안 읽음
        back = next(c for c in doc["checks"] if c["source"].startswith("출입처 소집공고 되짚기"))
        self.assertEqual((back["status"], back["returned"]), ("ok", 1))
        self.assertEqual(doc["agmParse"], km.AGM_PARSE_VERSION)
        # 경력 칸 읽는 법이 바뀌면(판 올림) 저장된 후보 공고를 한 번 다시 읽어 경력만 고쳐 쓴다 — 처음 잡힌 때·기준선은 그대로
        old_doc = dict(doc, agmParse=1, events=[dict(e, person=dict(e["person"], career="붙은 옛 경력"), detectedAt="2026-11-05T23:53:00+09:00")
                                                 if e["source"] == "주총 소집공고" else e for e in doc["events"]])
        try:
            km.AGM_DAYS = 120
            g2 = Dated(files, {"20260910000111": AGM})
            again = run(g2, previous=old_doc, skip_roster=True)
            same = run(Dated(files, {"20260910000111": AGM}), previous=again, skip_roster=True)
        finally:
            km.AGM_DAYS = old
        agm2 = [e for e in again["events"] if e["source"] == "주총 소집공고"]
        self.assertTrue(all(e["person"]["career"] != "붙은 옛 경력" and e.get("reparsed") and e.get("baseline")
                            and e["detectedAt"] == "2026-11-05T23:53:00+09:00" for e in agm2))
        self.assertEqual(again["counts"]["newEvents"], 0)
        self.assertEqual(next(c for c in again["checks"] if c["source"] == "이사 후보 경력 다시 읽기")["returned"], len(agm2))
        self.assertFalse(any(c["source"] == "이사 후보 경력 다시 읽기" for c in same["checks"]))     # 같은 판이면 다시 안 읽음

    def test_disqualification_column_none_words_real_1105(self):
        # 11-05 실제(고려아연 2026-08-11 소집공고): 「결격사유 없음」을 '없음 아님'으로 읽어 후보 6명이 A가 됐다
        for v in ("결격사유 없음", "결격 사유 없음.", "체납사실 없음", "해당사항 없음", "부실기업 경영진 아님", "-", "無"):
            self.assertTrue(km.none_value(v), v)
        for v in ("결격사유 있음", "2019년 ○○건설 회생절차 사내이사", "있음", "해당"):
            self.assertFalse(km.none_value(v), v)
        old = {"kind": "이사 후보", "tier": "A", "flags": [{"kind": "결격·부실 칸", "text": "법령상 결격 사유 칸 「결격사유 없음」(회사 기재 그대로)"},
                                                       {"kind": "전관", "text": "경력에 '판사'"}]}
        self.assertTrue(km.refresh_agm_flags(old))
        self.assertEqual((old["tier"], [f["kind"] for f in old["flags"]]), ("B", ["전관"]))
        real = {"kind": "이사 후보", "tier": "A", "flags": [{"kind": "결격·부실 칸", "text": "부실기업 경영진 여부 칸 「○○건설(2019 회생절차) 사내이사 재직」(회사 기재 그대로)"}]}
        self.assertFalse(km.refresh_agm_flags(real))
        self.assertEqual(real["tier"], "A")

    def test_roster_baseline_then_new_flagged_director(self):
        def roster(rc, people):
            return {"status": "000", "list": [{"rcept_no": rc, "nm": n, "birth_ym": b, "ofcps": o, "rgist_exctv_at": "사내이사", "fte_at": "상근",
                                               "chrg_job": "-", "main_career": c, "mxmm_shrholdr_relate": "-", "hffc_pd": "-", "tenure_end_on": "-"}
                                              for n, b, o, c in people]}
        table = {"부품사": [["00999001", "123456"]], "현대글로비스": [["00999004", "086280"]], "현대자동차": [["00164742", "005380"]]}
        rosters = {("00999001", 2026, "11012"): roster("r0", [("기존", "1960년 01월", "대표이사", "현대위아 상무")]),
                   ("00999004", 2026, "11012"): roster("g0", [("내부", "1965년 01월", "사장", "현대자동차 부사장")])}
        g = Fake(rosters=rosters, industry={"00999001": "30310"})
        first = run(g, table=table, roster_budget=10)
        self.assertEqual([e for e in first["events"] if e["source"] == "임원 현황"], [])        # 기준선
        self.assertEqual(first["companies"]["00999001"]["p"], "202611012")
        self.assertNotIn("00164742", first["companies"])                                    # 출입처는 임원 명단 감시가 본다
        rosters[("00999001", 2026, "11014")] = roster("r1", [("기존", "1960년 01월", "대표이사", "현대위아 상무"),
                                                             ("신임", "1966년 02월", "부사장", "前 기아 구매본부장(전무) / 롯데카드 사외이사")])
        rosters[("00999004", 2026, "11014")] = roster("g1", [("내부", "1965년 01월", "사장", "현대자동차 부사장"), ("새내부", "1970년 01월", "부사장", "기아 전무")])
        second = run(Fake(rosters=rosters, industry={"00999001": "30310"}), previous=first, table=table, roster_budget=10)
        ev = [e for e in second["events"] if e["source"] == "임원 현황"]
        self.assertEqual([(e["company"], e["person"]["name"], e["tier"]) for e in ev], [("부품사", "신임", "A")])   # 주의 회사 + 같은 업종 고위 출신
        self.assertIn("앞 조사(2026년 반기(6-30 기준))에는 없음", ev[0]["text"])
        alumni = second["alumni"]["00999001"]
        self.assertEqual([(a["name"], a["beats"], a["senior"]) for a in alumni], [("기존", ["현대위아"], False), ("신임", ["기아"], True)])
        self.assertIn("00999001", first["alumni"])                                          # 기준선 실행에도 현황은 남는다
        self.assertNotIn("00999004", second["alumni"])                                      # 같은 그룹(현대글로비스)은 현황에도 없음

    def test_list_failure_is_unconfirmed(self):
        class Down(Fake):
            def __call__(self, url, params=None, **kw):
                if url.endswith("list.json"):
                    return R({"status": "800", "message": "시스템 점검"})
                return super().__call__(url, params, **kw)
        doc = run(Down(), skip_roster=True)
        self.assertTrue(all(c["status"] == "failed" for c in doc["checks"] if c["source"].startswith("공시 목록")))
        self.assertEqual(doc["events"], [])


if __name__ == "__main__":
    unittest.main()
