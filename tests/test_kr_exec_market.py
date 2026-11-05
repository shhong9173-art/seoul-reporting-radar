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
        self.assertEqual(hire["tier"], "B")                   # 출입처 고위 임원 출신이 다른 회사 독립이사로
        self.assertEqual(hire["beat"], "현대차")
        self.assertNotIn(("독립이사 신고", "부품사", "박교수"), ev)   # 다른 회사는 표시 있는 사람만
        quit_ = ev[("독립이사 신고", "현대차", "이사퇴")]
        self.assertEqual(quit_["tier"], "A")                  # 출입처 독립이사 중도퇴임
        ceo = ev[("대표이사 변경", "강판가공", "최현수")]
        self.assertEqual(ceo["tier"], "B")
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
