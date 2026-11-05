import datetime as dt
import io
import json
import sys
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import kr_exec_watch as kx  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 11, 16, 21, 50, tzinfo=KST)


def td(*cells):
    return "<TR>" + "".join(f"<TD>{c}</TD>" for c in cells) + "</TR>"


REG_HEAD = td("성명", "성별", "출생년월", "직위", "등기임원여부", "상근여부", "담당업무", "주요경력", "소유주식수", "최대주주와의관계", "재직기간", "임기만료일") \
    + td("의결권 있는 주식", "의결권 없는 주식")
UNREG_HEAD = td("이름", "성별", "출생년월", "직위명", "상근여부", "주요담당업무", "주요경력", "재직기간 (개월)", "소유주식수") \
    + td("의결권 있는주식", "의결권 없는주식")


def reg_row(name, birth, ofcps, reg, career, rel="계열회사임원", end="2028.03.19"):
    return td(name, "남", birth, ofcps, reg, "상근" if reg == "사내이사" else "비상근", "업무", career, "100", "-", rel, "2025.3.20~", end)


def unreg_row(name, birth, ofcps, career, job="팀장"):
    return td(name, "남", birth, ofcps, "상근", job, career, "12", "0", "0")


def document(reg_rows, unreg_rows, changes=None, note=""):
    parts = ["<P>VIII. 임원 및 직원 등에 관한 사항</P><P>1. 임원 및 직원 등의 현황</P><P>가. 임원 현황 (1) 등기임원</P>",
             "<TABLE>" + td("(기준일 :", "2026년 09월 30일", ")", "(단위 : 주)") + "</TABLE>",
             "<TABLE>" + REG_HEAD + "".join(reg_rows) + "</TABLE>", "<P>(2) 미등기임원</P>",
             "<TABLE>" + UNREG_HEAD + "".join(unreg_rows) + "</TABLE>",
             f"<P>※ 별정직 임원은 제외함. ※ 보고서 제출일 현재 변동사항 {note}</P>"]
    if changes:
        parts.append("<TABLE>" + td("구분", "성명", "직위", "담당업무", "비고") + "".join(changes) + "</TABLE>")
    parts.append("<P>나. 직원 등 현황</P><TABLE>" + td("사업부문", "성별", "직원수", "평균 근속연수") + td("자동차", "남", "100", "15") + "</TABLE>")
    return "".join(parts)


def zipped(text):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("doc.xml", text)
    return buf.getvalue()


class R:
    def __init__(self, body=None, content=None, status=200):
        self.status_code, self._body, self.content = status, body, content

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise OSError(self.status_code)


def api_list(rcept, rows):
    return {"status": "000", "list": [{"rcept_no": rcept, "nm": n, "birth_ym": b, "ofcps": o, "rgist_exctv_at": r, "fte_at": "상근",
                                       "chrg_job": "-", "main_career": c, "mxmm_shrholdr_relate": rel, "hffc_pd": "-", "tenure_end_on": e}
                                      for n, b, o, r, c, rel, e in rows]}


class Fake:
    """corp → {(year, report): (api body, document text)}"""

    def __init__(self, data):
        self.data, self.calls = data, []

    def __call__(self, url, params=None, **kw):
        params = params or {}
        self.calls.append((url.rsplit("/", 1)[-1], params.get("corp_code") or params.get("rcept_no"), params.get("reprt_code")))
        if url.endswith("exctvSttus.json"):
            got = self.data.get(params["corp_code"], {}).get((int(params["bsns_year"]), params["reprt_code"]))
            return R(got[0] if got else {"status": "013", "message": "조회된 데이타가 없습니다."})
        if url.endswith("document.xml"):
            for per in self.data.values():
                for body, text in per.values():
                    if body["list"] and body["list"][0]["rcept_no"] == params["rcept_no"]:
                        return R(content=zipped(text))
            return R(content=b'{"status":"014"}')
        raise AssertionError(url)


REGISTRY = {"companies": {"현대자동차": {"corp_code": "00164742"}, "KG모빌리티": {"corp_code": "00138242"}, "고려아연": {"corp_code": "00102858"}}}
WATCH = [{"name": "롯데카드", "aliases": ["롯데카드"], "reason": "2025년 해킹 사고"}]


def hyundai(base=False):
    reg = [reg_row("정의선", "1970.10", "회장", "사내이사", "기아자동차 사장('05~'08)", rel="임원"),
           reg_row("도원식", "1961.05", "이사", "독립이사" if not base else "사외이사", "퀄컴 수석부사장")]
    if base:
        reg.append(reg_row("김중도", "1960.01", "이사", "사외이사", "법무법인 대표", end="2028.03.19"))
    unreg = [unreg_row("박상무", "1972.03", "상무", "현대자동차 생산팀장"), unreg_row("최전무", "1968.07", "전무", "현대자동차 재경")]
    if base:
        unreg.append(unreg_row("이퇴임", "1966.02", "상무", "현대자동차 품질검사팀장"))
    else:
        unreg.append(unreg_row("한영입", "1975.04", "상무", "테슬라 시니어 디렉터 / 한국GM 부장"))
        unreg.append(unreg_row("오카드", "1964.09", "부사장", "롯데카드 대표이사 / 대구고검 검사장"))
    changes = None if base else [td("임원추가", "권신규", "부사장", "자율주행개발센터장", "-"), td("이승애", "상무", "Feature전략실장", "-"),
                                 td("퇴임", "최전무", "전무", "재경", "11월 1일 사임")]
    return document(reg, unreg, changes)


def api_rows(base=False):
    rows = [("정의선", "1970년 10월", "회장", "사내이사", "기아자동차 사장", "임원", "2028년 03월 19일"),
            ("도원식", "1961년 05월", "이사", "사외이사", "퀄컴", "계열회사임원", "2028년 03월 19일")]
    if base:
        rows.append(("김중도", "1960년 01월", "이사", "사외이사", "법무법인", "-", "2028년 03월 19일"))
    return rows


def kgm(base=False):
    reg = [reg_row("곽재선", "1959.01", "회장", "사내이사", "KG그룹 회장", rel="본인")]
    unreg = [unreg_row("김기존", "1970.01", "상무", "쌍용자동차 기획")]
    if not base:
        unreg.append(unreg_row("유경쟁", "1974.05", "상무", "현대자동차 글로벌KD사업실장/기획실장"))
        unreg.append(unreg_row("곽자녀", "1990.02", "상무보", "KG그룹 전략"))
    return document(reg, unreg)


def kgm_doc_with_rel(base=False):
    # 오너 일가 표시는 '최대주주와의 관계' 칸이 있는 등기 표에서
    reg = [reg_row("곽재선", "1959.01", "회장", "사내이사", "KG그룹 회장", rel="본인")]
    if not base:
        reg.append(reg_row("곽상속", "1988.06", "부사장", "사내이사", "KG스틸 전략", rel="친인척"))
    return document(reg, [unreg_row("김기존", "1970.01", "상무", "쌍용자동차 기획")])


def fake(kgm_fn=kgm, include_kgm=True):
    data = {"00164742": {(2026, "11014"): (api_list("20261116000001", api_rows()), hyundai()),
                         (2026, "11012"): (api_list("20260814003521", api_rows(True)), hyundai(True))}}
    if include_kgm:
        data["00138242"] = {(2026, "11014"): (api_list("20261114000002", [("곽재선", "1959년 01월", "회장", "사내이사", "KG", "본인", "-")]), kgm_fn()),
                            (2026, "11012"): (api_list("20260814000002", [("곽재선", "1959년 01월", "회장", "사내이사", "KG", "본인", "-")]), kgm_fn(True))}
    return Fake(data)


def run(get, previous=None, **kw):
    return kx.run("k", now=NOW, previous=previous, get=get, sleep=lambda s: None, registry=REGISTRY, table={}, watch=WATCH, **kw)


class TextRules(unittest.TestCase):
    def test_word_match_keeps_affiliates_apart(self):
        self.assertTrue(kx.mentions("前 포스코 상무", "포스코"))
        self.assertTrue(kx.mentions("(주)포스코 부사장", "포스코"))
        self.assertFalse(kx.mentions("포스코퓨처엠 상무", "포스코"))
        self.assertFalse(kx.mentions("LS전선 기획", "LS"))
        self.assertTrue(kx.mentions("LS전선 기획", "LS전선"))
        self.assertFalse(kx.mentions("다우기술 대표", "다우"))

    def test_career_flags(self):
        own = kx.career_flags("현대자동차", "기아자동차 사장 / 현대모비스 부사장", WATCH)
        self.assertEqual(own, [])                                   # 같은 그룹 계열은 경쟁사가 아니다
        rival = kx.career_flags("KG모빌리티", "현대자동차 글로벌KD사업실장", WATCH)
        self.assertEqual([f["kind"] for f in rival], ["경쟁사 출신"])
        mixed = kx.career_flags("현대자동차", "롯데카드 대표이사 / 대구고검 검사장 / 테슬라 디렉터", WATCH)
        self.assertEqual([f["kind"] for f in mixed], ["주의 회사 출신", "해외 경쟁사 출신", "전관"])
        self.assertIn("2025년 해킹 사고", mixed[0]["text"])
        self.assertEqual(kx.career_flags("현대자동차", "현대자동차 품질검사팀장", WATCH), [])   # 품질검사 ≠ 검사
        self.assertEqual(kx.career_flags("S-Oil", "Saudi Aramco 부사장", WATCH), [])          # 대주주 출신은 해외 경쟁사가 아니다
        other = kx.career_flags("현대모비스", "S-Oil 재무팀장", WATCH)
        self.assertEqual([f["kind"] for f in other], ["다른 출입처 출신"])                   # 업종이 다르면 경쟁사가 아니다
        gm = kx.career_flags("현대자동차", "한국GM 부장", WATCH)
        self.assertEqual([f["kind"] for f in gm], ["경쟁사 출신"])                           # 한국GM은 출입처 — 'GM' 해외 표시와 겹치지 않음

    def test_owner_relation_is_read_not_guessed(self):
        self.assertEqual(kx.owner_flag({"rel": "특수관계인\n(친인척)"})["kind"], "오너 일가")
        self.assertIsNone(kx.owner_flag({"rel": "계열회사 임원"}))
        self.assertIsNone(kx.owner_flag({"rel": "-"}))

    def test_keys(self):
        self.assertEqual(kx.birth_key("1970년 10월"), "197010")
        self.assertEqual(kx.birth_key("1970.10"), "197010")
        self.assertEqual(kx.person_key({"name": "무뇨스 (Jose Munoz)", "birth": "1965.06"}), "무뇨스|196506")
        self.assertEqual(kx.norm_reg("독립이사"), "사외이사")
        self.assertEqual(kx.norm_reg("미등기임원"), "미등기")


class DocumentParsing(unittest.TestCase):
    def test_tables_and_change_rows(self):
        ppl, changes, notes = kx.parse_document(hyundai())
        self.assertEqual(sum(1 for p in ppl if p["reg"] != "미등기"), 2)
        self.assertEqual(sum(1 for p in ppl if p["reg"] == "미등기"), 4)
        p = next(x for x in ppl if x["name"] == "한영입")
        self.assertEqual((p["ofcps"], p["career"], p["period"]), ("상무", "테슬라 시니어 디렉터 / 한국GM 부장", "12"))  # 소유주식수 두 칸 뒤 칸 맞춤
        r = next(x for x in ppl if x["name"] == "도원식")
        self.assertEqual((r["reg"], r["end"]), ("사외이사", "2028.03.19"))
        self.assertEqual([(c["kind"], c["name"]) for c in changes], [("임원추가", "권신규"), ("임원추가", "이승애"), ("퇴임", "최전무")])
        self.assertEqual(notes, [])

    def test_header_after_date_row_in_same_table(self):
        doc = ("<P>가. 임원 현황</P><TABLE>" + td("(기준일 : 2026.06.30)", "(단위 : 주)") + REG_HEAD
               + reg_row("장인화", "1955.08", "회장", "사내이사", "포스코홀딩스 대표이사 회장") + "</TABLE>")
        ppl, _, _ = kx.parse_document(doc)
        self.assertEqual([(p["name"], p["reg"]) for p in ppl], [("장인화", "사내이사")])

    def test_board_chapter_table_before_exec_section_is_skipped(self):
        board = ("<P>VI. 이사회 등 회사의 기관에 관한 사항</P><TABLE>" + td("성 명", "성별", "출생년월", "직위", "담당업무", "주요경력", "선임일(임기)")
                 + td("감사위원", "남", "1960.01", "이사", "감사위원", "회계법인", "2025.3") + "</TABLE><P>직원 등 현황 참고</P>")
        ppl, _, _ = kx.parse_document(board + hyundai())
        self.assertNotIn("감사위원", [p["name"] for p in ppl])
        self.assertEqual(len(ppl), 6)
        board2 = ("<TABLE>" + td("성명", "성별", "출생년월", "직위", "등기임원여부", "상근여부", "담당업무", "주요경력", "선임일", "임기")
                  + td("이사회위원", "남", "1960.01", "이사", "사외이사", "비상근", "감사", "회계법인", "2025.3", "3년") + "</TABLE><P>직원 등 현황</P>")
        ppl, _, _ = kx.parse_document(board2 + hyundai())       # 두산에너빌리티: 이사회 장 표에도 등기임원여부 칸
        self.assertNotIn("이사회위원", [p["name"] for p in ppl])
        self.assertEqual(len(ppl), 6)

    def test_stops_before_employee_table(self):
        ppl, _, _ = kx.parse_document(hyundai() + "<TABLE>" + UNREG_HEAD + unreg_row("엉뚱", "1980.01", "상무", "x") + "</TABLE>")
        self.assertNotIn("엉뚱", [p["name"] for p in ppl])

    def test_text_change_note(self):
        doc = document([reg_row("장인화", "1955.08", "회장", "사내이사", "포스코홀딩스 대표")], [],
                       note="※공시기준일 이후 보고서 제출일 현재까지 변동된 미등기임원 현황은 다음과 같습니다. ○ 임원 신규선임 - 임치현 그룹DX전략실장")
        _, changes, notes = kx.parse_document(doc)
        self.assertEqual(changes, [])
        self.assertTrue(notes and "임치현" in notes[0])


class Runs(unittest.TestCase):
    def test_first_run_flags_and_tiers(self):
        doc = run(fake())
        self.assertEqual(doc["period"]["label"], "2026년 3분기(9-30 기준)")
        self.assertEqual(doc["period"]["base"]["label"], "2026년 반기(6-30 기준)")
        ev = {(e["company"], e["kind"], (e.get("person") or {}).get("name")): e for e in doc["events"]}
        hire = ev[("현대차", "새 임원", "한영입")]
        self.assertEqual(hire["tier"], "A")       # 수시 인사 철(3분기) 경쟁 출입처(한국GM) 출신
        self.assertEqual([f["kind"] for f in hire["flags"]], ["경쟁사 출신", "해외 경쟁사 출신"])
        card = ev[("현대차", "새 임원", "오카드")]
        self.assertEqual(card["tier"], "A")
        self.assertIn("주의 회사 출신", [f["kind"] for f in card["flags"]])
        self.assertIn("전관", [f["kind"] for f in card["flags"]])
        mid = ev[("현대차", "명단에서 빠짐", "김중도")]
        self.assertEqual(mid["tier"], "A")        # 등기임원 임기 2028년인데 빠짐
        self.assertIn("임기 중 빠짐", [f["kind"] for f in mid["flags"]])
        self.assertEqual(ev[("현대차", "명단에서 빠짐", "이퇴임")]["tier"], "C")
        self.assertNotIn(("현대차", "직위 변경", "도원식"), ev)     # 사외이사→독립이사 이름 바뀜은 변경이 아니다
        rival = ev[("KG모빌리티", "새 임원", "유경쟁")]
        self.assertEqual(rival["tier"], "A")
        self.assertEqual(ev[("KG모빌리티", "새 임원", "곽자녀")]["tier"], "C")   # 관계 칸이 없는 미등기 표 — 성으로 추정하지 않는다
        changes = [e for e in doc["events"] if e["kind"] == "제출일까지 변동"]
        self.assertEqual(len(changes), 3)
        self.assertTrue(all("기준일 뒤 제출일까지" in e["text"] for e in changes))
        self.assertTrue(all(e["id"].startswith("exec:") and e["detectedAt"] == NOW.isoformat(timespec="seconds") for e in doc["events"]))
        c = {x["source"]: x for x in doc["checks"]}
        self.assertEqual(c["현대차"]["coverage"], "원문 표(등기 2·미등기 4)")
        self.assertEqual((c["현대차"]["new"], c["현대차"]["gone"]), (2, 2))

    def test_same_report_is_not_read_twice(self):
        g = fake()
        first = run(g)
        g2 = fake()
        second = run(g2, previous=first)
        self.assertEqual(second["counts"]["newEvents"], 0)
        self.assertEqual(len(second["events"]), len(first["events"]))
        self.assertFalse([c for c in g2.calls if c[0] == "document.xml"])       # 같은 접수번호면 원문을 다시 받지 않는다
        self.assertTrue(all(x["status"] == "ok" for x in second["checks"] if x["source"] in ("현대차", "KG모빌리티")))

    def test_next_quarter_reuses_last_roster_as_base(self):
        first = run(fake(include_kgm=False))
        g = fake(include_kgm=False)
        annual = hyundai().replace("한영입", "신연말")
        g.data["00164742"][(2026, "11011")] = (api_list("20270310000001", api_rows()), annual)
        doc = kx.run("k", now=dt.datetime(2027, 3, 10, 21, 50, tzinfo=KST), year=2026, report="11011", previous=first, get=g,
                     sleep=lambda s: None, registry=REGISTRY, table={}, watch=WATCH)
        docs = [c for c in g.calls if c[0] == "document.xml"]
        self.assertEqual(docs, [("document.xml", "20270310000001", None)])      # 앞 보고서(3분기)는 지난 실행에 읽은 명단
        c = next(x for x in doc["checks"] if x["source"] == "현대차")
        self.assertIn("지난 실행에 읽은 명단", c["baseCoverage"])
        names = {(e["kind"], (e.get("person") or {}).get("name")) for e in doc["events"] if e["detectedAt"] == doc["generatedAt"]}
        self.assertEqual(names & {("새 임원", "신연말"), ("명단에서 빠짐", "한영입")}, {("새 임원", "신연말"), ("명단에서 빠짐", "한영입")})
        self.assertEqual(doc["season"], "annual")

    def test_board_seat_left_midterm_but_stays(self):
        g = fake(include_kgm=False)
        cur = hyundai().replace(reg_row("도원식", "1961.05", "이사", "독립이사", "퀄컴 수석부사장"), "") \
            .replace(unreg_row("박상무", "1972.03", "상무", "현대자동차 생산팀장"), unreg_row("박상무", "1972.03", "상무", "현대자동차 생산팀장")
                     + unreg_row("도원식", "1961.05", "고문", "퀄컴 수석부사장"))
        g.data["00164742"][(2026, "11014")] = (g.data["00164742"][(2026, "11014")][0], cur)
        doc = run(g)
        e = next(x for x in doc["events"] if (x.get("person") or {}).get("name") == "도원식")
        self.assertEqual((e["kind"], e["tier"]), ("등기임원에서 내려옴", "A"))
        self.assertIn("2028-03-19", e["flags"][0]["text"])

    def test_baseline_stores_roster_without_items(self):
        g = fake()
        base = run(g, year=2026, report="11012", baseline=True)
        self.assertEqual(base["events"], [])
        self.assertTrue(base["baseline"])
        self.assertEqual(base["rosters"]["현대자동차"]["period"], "202611012")
        self.assertEqual(len([c for c in g.calls if c[0] == "document.xml"]), 2)      # 회사당 이번 보고서 하나만
        g2 = fake()
        doc = run(g2, previous=base)                                                     # 3분기: 앞 보고서는 저장한 반기 명단
        self.assertEqual([c[1] for c in g2.calls if c[0] == "document.xml"], ["20261116000001", "20261114000002"])
        self.assertIn(("새 임원", "한영입"), {(e["kind"], (e.get("person") or {}).get("name")) for e in doc["events"]})

    def test_not_filed_is_unconfirmed_not_zero(self):
        doc = run(fake(include_kgm=False))
        c = {x["source"]: x for x in doc["checks"]}
        self.assertEqual(c["KG모빌리티"]["status"], "no_data")
        self.assertEqual(c["고려아연"]["status"], "no_data")
        self.assertEqual(c["기아"]["status"], "failed")              # 고유번호 못 찾음 — 미확인
        self.assertEqual(doc["status"], "partial")

    def test_owner_relation_new_director_is_a(self):
        doc = run(fake(kgm_fn=kgm_doc_with_rel))
        e = next(x for x in doc["events"] if (x.get("person") or {}).get("name") == "곽상속")
        self.assertEqual((e["kind"], e["tier"]), ("새 임원", "A"))
        self.assertIn("친인척", e["flags"][0]["text"])

    def test_api_only_side_compares_registered_only(self):
        g = fake(include_kgm=False)
        g.data["00164742"][(2026, "11012")] = (api_list("20260814003521", api_rows(True)), "<P>원문에 표 없음</P>")
        doc = run(g)
        c = next(x for x in doc["checks"] if x["source"] == "현대차")
        self.assertTrue(c["baseCoverage"].startswith("API 줄만"))
        kinds = {(e["kind"], (e.get("person") or {}).get("name")) for e in doc["events"]}
        self.assertNotIn(("새 임원", "한영입"), kinds)          # 앞 보고서에 미등기 줄이 없으면 미등기는 비교하지 않는다
        self.assertIn(("명단에서 빠짐", "김중도"), kinds)

    def test_format_shift_suppresses_items(self):
        g = fake(include_kgm=False)
        renamed = document([reg_row(f"새사람{i}", f"19{60 + i}.01", "이사", "사외이사", "x") for i in range(14)], [])
        old = document([reg_row(f"옛사람{i}", f"19{70 + i}.01", "이사", "사외이사", "x") for i in range(14)], [])
        g.data["00164742"] = {(2026, "11014"): (api_list("r1", []), renamed), (2026, "11012"): (api_list("r0", []), old)}
        g.data["00164742"][(2026, "11014")][0]["list"] = [{"rcept_no": "r1", "nm": "새사람0", "birth_ym": "1960.01", "rgist_exctv_at": "사외이사"}]
        g.data["00164742"][(2026, "11012")][0]["list"] = [{"rcept_no": "r0", "nm": "옛사람0", "birth_ym": "1970.01", "rgist_exctv_at": "사외이사"}]
        doc = run(g)
        self.assertEqual([e["kind"] for e in doc["events"]], ["명단 형식 변화"])

    def test_doc_budget_leaves_waiting(self):
        old = kx.DOC_BUDGET
        try:
            kx.DOC_BUDGET = 2
            doc = run(fake())
        finally:
            kx.DOC_BUDGET = old
        c = {x["source"]: x for x in doc["checks"]}
        self.assertEqual(c["현대차"]["status"], "ok")
        self.assertEqual(c["KG모빌리티"]["status"], "waiting")      # 다음 실행에서 — 0건이 아니다
        self.assertNotIn("KG모빌리티", doc["seen"])


class Annotate(unittest.TestCase):
    def test_public_log_masks_names(self):
        doc = run(fake())
        out = io.StringIO()
        old = sys.stdout
        sys.stdout = out
        try:
            kx.annotate(doc)
        finally:
            sys.stdout = old
        text = out.getvalue()
        self.assertNotIn("한영입", text)
        self.assertIn("한**", text)


if __name__ == "__main__":
    unittest.main()
