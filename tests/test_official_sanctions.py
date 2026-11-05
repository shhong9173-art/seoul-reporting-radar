import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import kr_exec_market as km  # noqa: E402
import official_sanctions as osn  # noqa: E402

NOW = dt.datetime(2026, 11, 5, 5, 50)


def fss_page(rows):
    trs = "".join(f'<tr><td>{n}</td><td>{org}</td><td>{d}</td><td><a href="/fss/job/openInfo/view.do?menuNo=200476&amp;pageIndex=1&amp;examMgmtNo={k}&amp;emOpenSeq=1">내용보기</a></td>'
                  f'<td>보험검사3국</td><td>10</td></tr>' for n, org, d, k in rows)
    return "<table><tr><th>번호</th><th>제재대상기관</th></tr>" + trs + "</table>"


class R:
    def __init__(self, text="", content=b"", status=200):
        self.text, self.content, self.status_code = text, content, status


# 탐침 180 공개안 PDF 글자(가상 회사로 바꿈)
PDF = ("제재내용 공개안\n1. 금융기관명 : 한빛카드㈜\n2. 제재조치일 : 2021. 10. 26.\n3. 제재조치내용\n대상 내용\n기 관 기관경고, 과태료 53억 1,110만원 부과\n"
       "임 원 주의적 경고 : 2명\n직 원 등\n감봉 : 2명\n4. 제재대상사실\n가. 문책사항\n(1) 신용정보 관리 소홀 한빛카드㈜ 前 대표이사 등은")
PDF_NONE = ("제재내용 공개안\n1. 금융기관명 : 오성보험대리점㈜\n2. 제재조치일 : 2026. 10. 26.\n3. 제재조치내용\n대상 내용\n기 관 해당사항 없음\n임 원 해당사항 없음\n"
            "직 원 등 (보험설계사) 업무정지 90일 : 1명\n4. 제재대상사실\n가. 문책사항")
# 탐침 181 결과의 공표 PDF 글자(가상 회사)
PIPC = ("개인정보보호법 위반 행정처분 결과 공표 … 순번 위반행위를 한 자 위반행위의 내용 행정처분의 내용 및 결과 명칭 위반조항 위반내용 처분일자 처분내용 "
        "1 ㈜한빛카드 舊 보호법*제29조 안전조치의무 2024. 3. 18. 과징금 7,088만원과태료 360만원 2 ㈜서울오성티브이 舊 보호법* 제29조 안전조치의무 2024. 3. 18. "
        "과징금 2,225만원과태료 420만원 舊 보호법* 제39조의4 제1항 개인정보 유출등의 통지·신고에 대한 특례 2024. 3. 18. 과태료 부과 360만원 "
        "* 舊 보호법 : 2020. 8. 5. 시행, 법률 제16930호 2024년 3월 18일 개 인 정 보 보 호 위 원 회")


class Parse(unittest.TestCase):
    def test_fss_rows_and_summary(self):
        rows = osn.fss_rows(fss_page([(310, "인카금융서비스㈜", "20261104", "202400672"), (309, "한빛카드주식회사", "20211026", "202100001")]))
        self.assertEqual(rows[0], {"id": "fss:202400672-1", "org": "인카금융서비스㈜", "date": "2026-11-04"})
        self.assertIn("examMgmtNo=202100001&emOpenSeq=1", osn.fss_url(rows[1]["id"]))
        s = osn.fss_summary(PDF)
        self.assertEqual(s["inst"], "기관경고, 과태료 53억 1,110만원 부과")
        self.assertEqual(s["exec"], "주의적 경고 : 2명")
        self.assertTrue(s["execSanctioned"] and s["ceoMentioned"])
        self.assertEqual(s["ceoWord"], "前대표이사")
        self.assertIn("한빛카드㈜ 前 대표이사 등은", s["ceoText"])             # 제재대상사실 속 앞뒤 원문
        n = osn.fss_summary(PDF_NONE)
        self.assertFalse(n["execSanctioned"])
        self.assertFalse(n["ceoMentioned"])
        # 제재대상사실 밖(머리·주소 칸)의 '대표이사'는 언급으로 치지 않는다
        head = osn.fss_summary("제재내용 공개안 1. 금융기관명 : 한빛카드㈜(대표이사 갑) 3. 제재조치내용 기 관 과태료 1,800만원 4. 제재대상사실 가. 직원 甲은 2019.1.2.∼2019.3.4. 기간중")
        self.assertFalse(head["ceoMentioned"])
        self.assertNotIn("ceoText", head)
        glued = osn.fss_summary("3.제재조치내용제재대상제재내용기관기관경고임원문책경고1명4.제재대상사실 ◦한빛은행은행장甲은2019.1.2.∼2019.8.7.기간중 사모펀드 내부통제기준을 마련하지 않음" + "가" * 200)
        self.assertEqual(glued["ceoWord"], "은행장")
        self.assertTrue(glued["ceoText"].startswith("◦한빛은행은행장甲은") and glued["ceoText"].endswith("…"))

    def test_fss_summary_old_formats_probe185(self):
        old = ("- 1 - 제재내용공개안1.금융회사명:㈜한빛은행2.제재조치일:2022.11.9.3.제재조치내용제재대상제재내용기관업무의일부[신규업무]정지3월과태료76.6억원"
               "임원퇴직자위법․부당사항(문책경고상당)1명직원감봉(3월)3명4.제재대상사실가.문책(1)사모펀드불완전판매 ◦한빛은행은2019.1.2.∼2019.8.7.기간중")
        d = osn.fss_summary(old)
        self.assertEqual((d["inst"], d["exec"], d["execSanctioned"], d["violation"]),
                         ("업무의일부[신규업무]정지3월과태료76.6억원", "퇴직자위법․부당사항(문책경고상당)1명", True, "2019-01~2019-08"))
        none = osn.fss_summary("제재내용공개안1.금융회사명:㈜한빛은행2.제재조치일:2021.2.5.3.제재조치내용제재대상제재내용기관과태료1,800만원직원자율처리필요사항1건4.제재대상사실가.")
        self.assertEqual((none["inst"], none["exec"], none["execSanctioned"]), ("과태료1,800만원", None, False))
        re_ = osn.fss_summary("직권재심 공개안Ⅰ.재심취지 … 1.제재개요□제재일자:2020.3.4.□제재대상자및제재종류 ◦회사:기관경고 ◦임직원甲甲등11명:정직3월~주의2.제재대상사실")
        self.assertEqual((re_["inst"], re_["exec"]), ("기관경고", "정직3월~주의"))

    def test_pipc_rows(self):
        rows = osn.pipc_rows(PIPC)
        self.assertEqual([(r["org"], r["date"], r["major"]) for r in rows], [("한빛카드", "2024-03-18", True), ("서울오성티브이", "2024-03-18", True)])
        self.assertEqual(rows[0]["inst"], "과징금 7,088만원, 과태료 360만원")
        self.assertEqual(rows[0]["what"], "안전조치의무")

    def test_pipc_rows_without_spaces_pypdf5(self):
        # 탐침 182: 운영 pypdf 5.9 글자(띄어쓰기 없이 칸이 붙음) — 회사는 가상으로 바꿈
        t = ("개인정보보호법 위반 행정처분 결과 공표 … 공표합니다.순번위반행위를 한 자위반행위의 내용행정처분의 내용 및 결과명칭위반조항위반내용처분일자처분내용"
             "1㈜한빛크린텍舊 보호법*제29조안전조치의무 2026. 9. 18.과징금 7,088만원과태료 360만원2㈜서울오성티브이舊 보호법*제29조안전조치의무2026. 9. 18."
             "과징금 2,225만원과태료 420만원舊 보호법*제39조의4제1항개인정보 유출등의 통지·신고에 대한 특례2026. 9. 18.과태료 부과 360만원 * 舊 보호법 : 2020. 8. 5. 시행,"
             " 법률 제16930호2026년 9월 18일개 인 정 보 보 호 위 원 회")
        rows = osn.pipc_rows(t)
        self.assertEqual([(r["no"], r["org"], r["date"], r["major"]) for r in rows], [("1", "한빛크린텍", "2026-09-18", True), ("2", "서울오성티브이", "2026-09-18", True)])
        self.assertEqual(rows[0]["inst"], "과징금 7,088만원, 과태료 360만원")
        t2 = ("처분내용1(주)한빛텔레콤보호법제29조안전조치의무 위반2026. 7. 29.과징금 539억 7,900만원, 시정조치 명령, 공표명령, 개선권고2(주)한빛텔레콤舊 보호법"
              "제39조의4제1항개인정보 유출등의 통지·신고에 대한 특례2026. 8. 26.과태료 360만원 * 舊 보호법 : 2020. 8. 5. 시행")
        rows = osn.pipc_rows(t2)
        self.assertEqual(rows[0]["inst"], "과징금 539억 7,900만원, 시정조치 명령, 공표명령, 개선권고")
        self.assertEqual((rows[1]["org"], rows[1]["date"], rows[1]["major"]), ("한빛텔레콤", "2026-08-26", False))
        t3 = "처분내용1양평군청舊 보호법제28조제1항취급자 관리‧감독 소홀2026.8.26.시정조치 권고2경성대학교보호법제29조,제35조제3항안전조치의무 위반,개인정보 열람 요구 부당 거부2026.8.26.과태료 1,350만원, 시정조치 명령, 공표명령2026년  9월  8일개 인 정 보"
        self.assertEqual([(r["org"], r["what"][:6]) for r in osn.pipc_rows(t3)], [("양평군청", "취급자 관리"), ("경성대학교", "안전조치의무")])

    def test_ftc_respondents_from_title(self):
        self.assertEqual(osn.ftc_respondents("(주) 해성산업개발의 부당한 광고행위에 대한 건"), ["해성산업개발"])
        self.assertEqual(osn.ftc_respondents("한빛자동차(주) 및 오성(주)의 부당한 하도급대금 결정 행위에 대한 건"), ["한빛자동차", "오성"])
        self.assertEqual(osn.ftc_respondents("4개 시중은행의 부당한 공동행위에 대한 건"), [])
        self.assertEqual(osn.ftc_respondents("6개 건설사들의 입찰담합 행위에 대한 건"), [])
        # 탐침 190(실제 사건명, 회사는 가상): 사업부문 꼬리·기업집단 머리를 떼야 회사 표와 이어진다
        self.assertEqual(osn.ftc_respondents("(주) 한빛리테일(슈퍼부문)의 대규모유통업법 위반행위에 대한 건"), ["한빛리테일"])
        self.assertEqual(osn.ftc_respondents("오성마트 (주) [슈퍼부문]의 대규모유통업법 위반행위에 대한 건"), ["오성마트"])
        self.assertEqual(osn.ftc_respondents("상호출자제한기업집단 한빛 소속 (주) 한빛리테일의 주식소유현황 등 신고 규정 위반행위에 대한 건"), ["한빛리테일"])
        st = {"rows": {"ftc:2018유통1950": {"id": "ftc:2018유통1950", "o": ["한빛리테일(슈퍼부문)"], "d": "2021-05-06", "a": "과징금"}}}
        self.assertEqual(osn.ftc_records(st)[0]["org"], "한빛리테일")                                  # 저장된 옛 줄도 읽을 때 떼기

    def test_ftc_refresh_and_records(self):
        pages = {1: [{"csno": "2026서경0001", "name": "한빛카드(주)의 부당한 고객유인행위에 대한 건", "decidedOn": "2026-10-07", "action": "과징금"}],
                 2: [{"csno": "2020서경0009", "name": "4개 시중은행의 부당한 공동행위에 대한 건", "decidedOn": "2020-03-01", "action": "과징금"}], 3: []}

        def get(url, params=None, **kw):
            return R(text=str(params["pageIndex"]))
        parse = lambda text: (pages[int(text)], 3)
        st, c = osn.refresh_ftc(None, get=get, now=NOW, parse=parse, new_pages=1)
        self.assertEqual((c["status"], c["rows"], st["done"]), ("ok", 2, True))
        recs = osn.ftc_records(st)
        self.assertEqual([(r["org"], r["date"], r["inst"]) for r in recs], [("한빛카드", "2026-10-07", "과징금")])
        self.assertIn("caseNo=2026서경0001", recs[0]["url"])

    def test_ftc_year_window_audit_fills_gaps_probe189(self):
        # 뒤 채우기가 끝난 뒤 해마다 창을 한 번씩 끝까지 다시 훑는다. 같은 사건번호 '의결'·'결정(고발)' 두 줄은 한 건(의결 줄을 남김)
        win = {"2024": {1: [{"csno": "2023서경0001", "blno": "결정2024-001", "name": "한빛카드(주)의 부당한 고객유인행위에 대한 건", "decidedOn": "2024-03-02", "action": "고발"},
                            {"csno": "2023서경0001", "blno": "의결2024-010", "name": "한빛카드(주)의 부당한 고객유인행위에 대한 건", "decidedOn": "2024-03-20", "action": "과징금, 고발"}] +
                           [{"csno": f"2023서경01{i:02d}", "blno": f"의결2024-1{i:02d}", "name": f"오성{i}(주)의 하도급법 위반행위에 대한 건", "decidedOn": "2024-05-01", "action": "경고"}
                            for i in range(8)],
                        2: [{"csno": "2023서경0099", "blno": "의결2024-199", "name": "누리상사(주)의 표시광고법 위반행위에 대한 건", "decidedOn": "2024-12-01", "action": "과징금"}]},
               "2025": {1: []}, "2026": {1: [{"csno": "2026서경0001", "blno": "의결2026-001", "name": "한빛화학(주)의 하도급법 위반행위에 대한 건", "decidedOn": "2026-10-07", "action": "과징금"}]}}
        calls = []

        def get(url, params=None, **kw):
            calls.append((params["startRceptDt"], params["pageIndex"]))
            return R(text=f"{params['startRceptDt']}|{params['endRceptDt']}|{params['pageIndex']}")

        def parse(text):
            a, b, n = text.split("|")
            if a == "2024-01-01" and b == NOW.date().isoformat():      # 전체 목록 앞쪽(새 의결)
                return win["2026"][1], 1
            y = win[a[:4]]
            return y.get(int(n), []), max(y)
        prev = {"since": "2024-01-01", "done": True,
                "rows": {"ftc:2023서경0001": {"id": "ftc:2023서경0001", "o": ["한빛카드"], "d": "2024-03-02", "a": "고발", "k": "결정"},
                         "ftc:2026서경0001": {"id": "ftc:2026서경0001", "o": ["한빛화학"], "d": "2026-10-07", "a": "과징금"}}}
        st, c = osn.refresh_ftc(prev, get=get, now=NOW, parse=parse)
        self.assertEqual(c["audit"], {"year": "2024", "rows": 11, "cases": 10, "added": 9, "complete": True})
        self.assertEqual((c["rows"], c["auditedYears"], c["auditAdded"]), (11, 1, 9))
        self.assertEqual((st["rows"]["ftc:2023서경0001"]["d"], st["rows"]["ftc:2023서경0001"]["a"]), ("2024-03-20", "과징금, 고발"))   # 의결 줄로 바꿈
        self.assertNotIn("k", st["rows"]["ftc:2023서경0001"])
        old_row = {**prev, "rows": {"ftc:2023서경0001": {"id": "ftc:2023서경0001", "o": ["한빛카드"], "d": "2024-03-02", "a": "고발"}}}   # 표시 없는 옛 줄
        self.assertEqual(osn.refresh_ftc(old_row, get=get, now=NOW, parse=parse)[0]["rows"]["ftc:2023서경0001"]["d"], "2024-03-20")
        st, c = osn.refresh_ftc(st, get=get, now=NOW, parse=parse)
        st, c = osn.refresh_ftc(st, get=get, now=NOW, parse=parse)
        self.assertEqual(sorted(st["audit"]), ["2024", "2025", "2026"])
        calls.clear()
        st, c = osn.refresh_ftc(st, get=get, now=NOW + dt.timedelta(days=3), parse=parse)
        self.assertNotIn("audit", c)                                     # 다 봤으면 쉰다
        self.assertEqual(calls, [("2024-01-01", 1)])
        st, c = osn.refresh_ftc(st, get=get, now=NOW + dt.timedelta(days=31), parse=parse)
        self.assertEqual(c["audit"]["year"], "2026")                     # 올해 창은 한 달마다
        bad = lambda url, params=None, **k: R(status=500) if params["endRceptDt"] == "2024-12-31" else get(url, params=params)
        failing, c = osn.refresh_ftc(prev, get=bad, now=NOW, parse=parse)
        self.assertEqual((c["status"], failing.get("audit")), ("partial", None))   # 실패한 창은 점검으로 치지 않는다(다음 실행에 다시)

    def test_pipc_probe184_variants(self):
        t = ("처분내용1한빛연구재단법 제29조안전조치의무위반2026.1.28과징금, 시정명령,공표명령, 징계권고, 개선권고법 제34조제1항유출통지의무 위반2026.1.28과태료, 시정명령"
             "2026년 3월 6일개 인 정 보 보 호 위 원 회")
        rows = osn.pipc_rows(t)
        self.assertEqual([(r["org"], r["date"]) for r in rows], [("한빛연구재단", "2026-01-28")])
        t2 = ("처분내용1오성공단 보호법 제29조 안전조치의무 위반 2026. 5. 1. 과징금 4억 7,800만원, 공표명령 2한빛구청 보호법 제26조제1항위탁업무와 수탁자 공개 미흡 2026. 5. 1. 과태료 300만원"
              " 2026년 5월 9일 개인정보 보호위원회")
        self.assertEqual([r["org"] for r in osn.pipc_rows(t2)], ["오성공단", "한빛구청"])
        self.assertEqual(osn.pipc_rows("처분내용1경북한빛병원 汤捯 보호법 제34조 유출통지 지연 2026. 1. 28. 과태료 360만 원")[0]["org"], "경북한빛병원")

    def test_ftc_titles_probe184(self):
        self.assertEqual(osn.ftc_respondents("한빛조선해양 주식회사 및 오성중공업 주식회사 의 불공정하도급거래행위에 대한 건"), ["한빛조선해양", "오성중공업"])
        self.assertEqual(osn.ftc_respondents("(합)한빛종합건설의 불공정하도급거래행위에 대한 건"), ["한빛종합건설"])
        self.assertEqual(osn.ftc_respondents("용인시 오성중학교 발주 교복 입찰 관련 4개 사업자의 부당한 공동행위에 대한 건"), [])

    def test_ftc_case_detail_and_won(self):
        self.assertEqual(osn.won_text("1,582,000,000"), "15억8200만원")
        self.assertEqual(osn.won_text("44,000,000"), "4400만원")
        self.assertEqual(osn.won_text("120", "백만원"), "1억2000만원")

        class KS:
            FTC_TEXT = "doc"

            @staticmethod
            def parse_ftc_list(text):
                rows = [{"csno": "2020서경0001" if text == "p2" else "x", "name": "(주) 한빛리테일의 대규모유통업법 위반행위에 대한 건",
                         "doc": {"docId": "D", "docCnvrMnNo": "N"}}]
                return rows, 3

            doc_text = staticmethod(lambda raw: raw)

            @staticmethod
            def sections(text):
                return ("주식회사 한빛리테일 서울 대표이사 허○○, 김○○ 대리인 변호사 전○○",
                        "1. 피심인은 … 하여서는 아니 된다. 2. 피심인은 과징금을 국고에 납부하여야 한다. 가. 과징금액 : 1,582,000,000원 나. 납부기한")
        pages = []

        def get(url, params=None, **kw):
            if url == "doc":
                return R(text="원문")
            pages.append(params["pageIndex"])
            return R(text="p2" if params["pageIndex"] == 2 else "p1")
        d = osn.ftc_case_detail({"id": "ftc:2020서경0001:0", "org": "한빛리테일"}, get=get, now=NOW, ks=KS)
        self.assertEqual((d["status"], d["amount"], d["ceos"], pages), ("ok", "15억8200만원", ["허○○", "김○○"], [1, 2]))
        self.assertIn("대규모유통업법", d["title"])
        seen = []

        def get2(url, params=None, **kw):
            if url == "doc":
                return R(text="원문")
            seen.append(params["searchKrwd"])
            return R(text="p2" if params["searchKrwd"] == "케이비리테일" else "p1")
        d2 = osn.ftc_case_detail({"id": "ftc:2020서경0001:0", "org": "KB리테일"}, get=get2, now=NOW, ks=KS, pages=1)
        self.assertEqual((d2["status"], seen), ("ok", ["KB리테일", "케이비리테일"]))          # 영문 약자로 못 찾으면 한글 읽기로
        miss = osn.ftc_case_detail({"id": "ftc:2099서경0009:0", "org": "한빛리테일"}, get=get, now=NOW, ks=KS, pages=1)
        self.assertEqual(miss["status"], "not_found")                                   # 목록은 읽었는데 사건번호가 없음

        class Empty(KS):
            parse_ftc_list = staticmethod(lambda text: ([], None))
        blank = osn.ftc_case_detail({"id": "ftc:2020서경0001:0", "org": "한빛리테일"}, get=get, now=NOW, ks=Empty)
        self.assertEqual(blank, {"status": "failed", "error": "empty_list"})           # 빈 목록(오류 쪽)은 못 찾음으로 저장하지 않는다

    def test_org_keys_read_latin(self):
        self.assertTrue(osn.org_keys("KB증권") & osn.org_keys("케이비증권 주식회사"))
        self.assertTrue(osn.org_keys("DB손해보험") & osn.org_keys("DB손해보험주식회사"))
        self.assertFalse(osn.org_keys("한빛카드") & osn.org_keys("한빛카드캐피탈"))

    def test_top_roles(self):
        got = osn.top_roles("(2015~2018) 한빛증권 대표이사 사장 / 前) 현대자동차 사장 / KB자산 대표이사 사장 오성증권 대표이사 / 現) 디비손보 대표이사(2024~현재)",
                            km.segments, now=NOW)
        self.assertEqual([(r["org"], r["start"], r["end"]) for r in got],
                         [("한빛증권", 2015, 2018), ("현대자동차", None, None), ("KB자산", None, None), ("오성증권", None, None), ("디비손보", 2024, 2026)])
        self.assertEqual(osn.top_roles("現) 한국경영학회 회장 / 現) 법무법인 율촌 대표", km.segments, now=NOW), [])

    def test_match_timing(self):
        roles = [{"org": "한빛카드", "role": "대표이사", "start": 2019, "end": 2021, "current": False, "seg": ""},
                 {"org": "오성증권", "role": "사장", "start": None, "end": None, "current": False, "seg": ""}]
        recs = [{"id": "a", "agency": "금감원", "org": "한빛카드주식회사", "date": "2023-05-01"},     # 끝+2년 안
                {"id": "b", "agency": "금감원", "org": "한빛카드㈜", "date": "2024-05-01"},          # 끝+3년 — 뺀다
                {"id": "c", "agency": "금감원", "org": "한빛카드", "date": "2018-12-01"},            # 시작 전 — 뺀다
                {"id": "d", "agency": "금감원", "org": "오성증권㈜", "date": "2020-01-01"}]
        got = {(m["record"]["id"], m["timing"]) for m in osn.match(roles, recs)}
        self.assertEqual(got, {("a", "overlap"), ("d", "timing_unknown")})


class Refresh(unittest.TestCase):
    def test_fss_new_then_backfill_and_failure_keeps_state(self):
        pages = {1: [(3, "새회사", "20261104", "3")], 2: [(2, "중간", "20201010", "2")], 3: [(1, "옛회사", "20160105", "1")], 4: []}
        calls = []

        def get(url, **kw):
            n = int(url.rsplit("pageIndex=", 1)[1])
            calls.append(n)
            return R(fss_page(pages[n]))
        st, c = osn.refresh_fss(None, get=get, now=NOW, backfill_pages=10, new_pages=2)
        self.assertEqual((c["status"], c["rows"], st["done"]), ("ok", 3, True))
        pages[1] = [(4, "더새회사", "20261105", "4")] + pages[1]
        calls.clear()
        st2, c2 = osn.refresh_fss(st, get=get, now=NOW, new_pages=3)
        self.assertEqual((c2["new"], c2["rows"], calls), (1, 4, [1]))          # 아는 줄이 나오면 멈추고, 채우기 끝났으면 뒤쪽 안 봄

        def boom(url, **kw):
            raise TimeoutError()
        st3, c3 = osn.refresh_fss(st2, get=boom, now=NOW)
        self.assertEqual((c3["status"], c3["rows"]), ("partial", 4))           # 실패는 앞 상태 유지(0건 아님)

    def test_pipc_reads_only_new_posts(self):
        listing = '<a href="/np/cop/bbs/selectBoardArticle.do?bbsId=BS258&amp;mCode=C010040000&amp;nttId=12608">공표</a>'
        view = "<a href=\"javascript:fn_egov_downFileCnv('FILE_1','0','pdf')\">다운로드</a>"
        calls = []

        def get(url, **kw):
            calls.append(url)
            if "selectBoardList" in url:
                return R(listing if url.endswith("pageIndex=1") else "")
            if "selectBoardArticle" in url:
                return R(view)
            return R(content=b"%PDF-1.4 fake")
        st, c = osn.refresh_pipc(None, get=get, now=NOW, read_pdf=lambda raw, pages: PIPC)
        self.assertEqual((c["posts"], c["rows"]), (1, 2))
        self.assertEqual(osn.pipc_records(st)[0]["id"], "pipc:12608:1")
        calls.clear()
        osn.refresh_pipc(st, get=get, now=NOW, read_pdf=lambda raw, pages: PIPC)
        self.assertFalse(any("FileDown" in u for u in calls))                   # 이미 읽은 글은 다시 안 읽는다


    def test_pipc_unread_posts_are_retried(self):
        listing = '<a href="/np/cop/bbs/selectBoardArticle.do?bbsId=BS258&amp;mCode=C010040000&amp;nttId=12608">공표</a>'
        view = "<a href=\"javascript:fn_egov_downFileCnv('FILE_1','0','pdf')\">다운로드</a>"
        state = {"posts": {"12608": []}}                                         # 예전 실행: 첨부를 못 읽어 빈 글로 저장
        html_err = lambda url, **kw: R(listing if "pageIndex=1" in url else "") if "selectBoardList" in url else R(view) if "selectBoardArticle" in url else R(text="<html>", content=b"<html>")
        st, c = osn.refresh_pipc(state, get=html_err, now=NOW, read_pdf=lambda raw, pages: PIPC)
        self.assertEqual((c["status"], c["posts"], st["posts"]), ("partial", 0, {}))
        self.assertIn("unread:200:", next(iter(c["outcomes"])))
        ok = lambda url, **kw: R(listing if "pageIndex=1" in url else "") if "selectBoardList" in url else R(view) if "selectBoardArticle" in url else R(content=b"%PDF-1.4")
        st2, c2 = osn.refresh_pipc(st, get=ok, now=NOW, read_pdf=lambda raw, pages: PIPC)
        self.assertEqual((c2["status"], c2["rows"]), ("ok", 2))

if __name__ == "__main__":
    unittest.main()
