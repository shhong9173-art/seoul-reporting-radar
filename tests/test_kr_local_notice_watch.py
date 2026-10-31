"""지자체 고시·공고 감시: 새올 목록 두 형식, 출입처 이름·사업 낱말 등급, 생활 공고 제외, 시·군별 기준선·신규, 실패는 미확인."""
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import kr_local_notice_watch as w  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 10, 30, 7, 40, tzinfo=KST)

# 당진·여수 형식: onclick on each <td> (10-30 탐침 원본에서 줄임)
TD_ROW = ('<tr > <td width="40" onclick="javaScript:searchDetail(\'{m}\')" >42605</td> <td align="left" onclick="javaScript:searchDetail(\'{m}\')">'
          '<p align=left >당진시 고시 제2026-{n}호</p></td> <td onclick="javaScript:searchDetail(\'{m}\')" ><p align=left>{t}</p></td> '
          '<td onclick="javaScript:searchDetail(\'{m}\')">환경정책과</td> <td onclick="javaScript:searchDetail(\'{m}\')" >{d}</td> </tr>')
# 울주·아산 형식: <a onclick> inside each <td>
A_ROW = ('<tr bgColor="#FFFFFF"> <td><a href="#" onclick="javaScript:searchDetail(\'{m}\')">52187</a></td> <td><p><a href="#" onclick="javaScript:searchDetail(\'{m}\')">'
         '울산광역시 울주군 공고 제2026-{n}호</a></p></td> <td><p><a href="#" onclick="javaScript:searchDetail(\'{m}\')">{t}</a></p></td> '
         '<td><a href="#" onclick="javaScript:searchDetail(\'{m}\')">건축과</a></td> <td><a href="#" onclick="javaScript:searchDetail(\'{m}\')">{d}</a></td> '
         '<td>{d} ~ 2026-11-19</td></tr>')
HEAD = '<tr height=23><td width="40">번호</td><td>고시공고번호</td><td width="300">제목</td><td>담당부서</td><td>등록일</td></tr>'


def page(rows, fmt):
    return "<table>" + HEAD + "".join(fmt.format(m=m, n=n, t=t, d=d) for m, n, t, d in rows) + "</table><script>function searchDetail(not_ancmt_mgt_no) {}</script>"


class Resp:
    def __init__(self, text, status=200):
        self.text, self.status_code = text, status


# 상세 페이지(10-31 탐침 원본 구조에서 줄임): 울주는 <dd>·<div> 본문 + 첨부 링크, 완주는 표 칸
ULJU_DETAIL = ('<html><head><title>고시공고</title><script>function goDownLoad(){ var a = "<td>제목</td>"; }</script></head><body>'
               '<dl><dt>공고번호</dt><dd>울산광역시 울주군 공고 제2026-2760호</dd><dt>담당부서</dt><dd>건축허가과</dd><dt>제목</dt>'
               '<dd>건설공사 안전점검 수행기관 지정 공고[온산 고려아연(주), #2ASU O2 COMPRESSOR ROOM 토건공사]</dd></dl>'
               '<div>우리 군 온산읍 원산리 892번지 일원 상 공장 용도의 건축공사에 대하여『건설기술 진흥법』제62조에 따라 건설공사 안전점검 '
               '수행기관을 지정하고자 다음과 같이 모집 공고합니다.<br>붙임 1. 안전점검 수행기관 지정 공고문 1부. 끝.</div>'
               '<table><tr><th>첨부파일 :</th><td><a href="#">예정공정표.pdf</a> <a href="#">안전점검 수행기관 지정 공고문[온산 고려아연(주) 2ASU '
               'O2 COMPRESSOR ROOM 토건공사].hwpx</a></td></tr></table><a href="#">목록보기</a></body></html>')
WANJU_DETAIL = ('<table><tr><th>고시공고번호</th><td>완주군 공고 제2026-1851호</td></tr><tr><th>제목</th>'
                '<td>전기사업법 위반에 따른 행정처분 사전통지 공시송달 공고</td></tr></table>'
                '<div>「전기사업법」 제9조(전기설비의 설치 및 사업의 개시의무) 규정을 위반하여 다음과 같이 공시송달합니다.</div>')

CITIES = [("당진시", "https://eminwon.dangjin.go.kr", "현대제철"), ("울주군", "http://eminwon.ulju.ulsan.kr", "고려아연")]


def fake(pages, down=()):
    calls = []

    def post(url, data=None, headers=None, timeout=None):
        calls.append((url, data["pageIndex"]))
        for base, text in pages.items():
            if url.startswith(base):
                if base in down:
                    raise type("ReadTimeout", (Exception,), {})("HTTPConnectionPool(host='x') read timed out")
                return Resp(text if data["pageIndex"] == "1" else "<table>" + HEAD + "</table>")
        raise AssertionError(url)
    post.calls = calls
    return post


DJ1 = [("57845", "303", "당진 도시관리계획(도시계획시설: 도로)결정(변경) 및 지형도면 고시", "2026-10-30"),
       ("57840", "301", "담배소매업 폐업에 따른 신규 소매인 지정 신청 공고(이마트24 당진현대제철점)", "2026-10-29")]
UJ1 = [("68118", "2727", "건설공사 안전점검 수행기관 지정 공고[온산 고려아연(주), Ga' 2차 ...", "2026-10-29")]


class Local(unittest.TestCase):
    def test_both_layouts_and_grades(self):
        rows = w.parse_rows(page([("57845", "303", "현대제철㈜ LNG 자가용전기설비 설치사업 환경영향평가(초안) 공람", "2026-10-30")], TD_ROW))
        self.assertEqual(rows, [{"mgt": "57845", "no": "당진시 고시 제2026-303호", "title": "현대제철㈜ LNG 자가용전기설비 설치사업 환경영향평가(초안) 공람",
                                 "dept": "환경정책과", "date": "2026-10-30"}])
        rows = w.parse_rows(page(UJ1, A_ROW))
        self.assertEqual((rows[0]["mgt"], rows[0]["no"], rows[0]["dept"], rows[0]["date"]), ("68118", "울산광역시 울주군 공고 제2026-2727호", "건축과", "2026-10-29"))
        self.assertEqual(w.classify(rows[0]["title"]), ("A", ["고려아연"]))
        self.assertEqual(w.classify("현대제철 견학 안내"), ("B", ["현대제철"]))
        self.assertEqual(w.classify("여수국가산업단지 계획 변경 승인 고시"), ("C", []))
        self.assertEqual(w.classify(DJ1[1][2]), (None, []))  # 담배 소매인 지정은 버림
        self.assertEqual(w.classify("포스코퓨처엠 광양 양극재 공장 증설"), ("C", []))  # 포스코퓨처엠은 포스코가 아님(공장 증설만 C)
        self.assertEqual(w.classify("(주)동성케미컬 신평공장 증설 관련 건축허가 공고"), ("A", ["동성케미칼"]))  # 법인 이름은 '케미컬'
        self.assertTrue(any(c == "울산 북구" for c, _, _ in w.CITIES))

    def test_namgu_layout_without_notice_number(self):
        row = ('<tr> <td >40994</td> <td class="left"> <div class="list_subject"> <div class="link"> <a href="emwp/gov/mogaha/ntis/web/ofr/action/'
               'OfrAction.do?not_ancmt_mgt_no=54887&amp;subCheck=Y" onclick="searchDetail(\'54887\');return false;" onkeypress="">'
               '현대모비스(주) 울산공장 증설 관련 도시관리계획 결정 고시</a> </div> </div> </td> <td>도시과</td> <td>2026-10-30</td> <td>3</td> </tr>')
        self.assertEqual(w.parse_rows("<table>" + row + "</table>"),
                         [{"mgt": "54887", "no": None, "title": "현대모비스(주) 울산공장 증설 관련 도시관리계획 결정 고시", "dept": "도시과", "date": "2026-10-30"}])

    def test_gwangsan_layout_management_number_in_link(self):
        # 10-30 광주 광산구 실제 목록 모양: 번호, 제목(<img> + <a href="…not_ancmt_mgt_no=…">), 담당부서, 등록일
        row = ('<tr class="row-data"> <td scope="row">43769</td> <td class="title"><img src="x.gif" alt="일반글" /> '
               '<a href="/emwp/gov/mogaha/ntis/web/ofr/action/OfrAction.do?pageIndex=1&amp;method=selectOfrNotAncmt&amp;not_ancmt_mgt_no=56345&amp;list_gubun=A" '
               'title="이동합니다">금호타이어㈜ 광주공장 이전부지 도시관리계획(용도지역) 결정(변경) 열람 공고</a></td> <td>도시계획과</td> <td>2026-10-30</td> </tr>')
        rows = w.parse_rows("<table><tbody>" + row + "</tbody></table>")
        self.assertEqual(rows, [{"mgt": "56345", "no": None, "title": "금호타이어㈜ 광주공장 이전부지 도시관리계획(용도지역) 결정(변경) 열람 공고",
                                 "dept": "도시계획과", "date": "2026-10-30"}])
        self.assertEqual(w.classify(rows[0]["title"])[0], "A")
        self.assertIn(("광주 광산구", "https://eminwon.gwangsan.go.kr", "금호타이어(광주공장)"), w.CITIES)

    def test_seogu_list_layout(self):
        # 10-30 광주 서구 실제 모양: 표가 아니라 <div class="dbody"><ul><li>…</li></ul>
        ul = ('<ul> <li class="col01"> <a href="#" onclick="javaScript:searchDetail(\'56380\')">44849</a> </li> '
              '<li class="col02 blind"> <a href="#" onclick="javaScript:searchDetail(\'56380\')">서구 공고 제2026-2094호</a> </li> '
              '<li class="title"> <a href="#" onclick="javaScript:searchDetail(\'56380\')">기아 오토랜드 광주 2공장 증설 건축 허가 사항 공고</a> </li> '
              '<li class="col03"> <a href="#" onclick="javaScript:searchDetail(\'56380\')">건축과</a> </li> '
              '<li class="col04"> <a href="#" onclick="javaScript:searchDetail(\'56380\')">2026-10-30</a> </li> '
              '<li class="col05"> <a href="#" onclick="javaScript:searchDetail(\'56380\')">11</a> </li> </ul>')
        head = '<div class="dhead"> <ul> <li class="col01">번호</li> <li class="title">제목</li> </ul> </div>'
        page_html = f'<table><tr><td>1</td></tr></table><div class="tstyle_list">{head}<div class="dbody">{ul}</div></div>'
        rows = w.parse_rows(page_html)
        self.assertEqual(rows, [{"mgt": "56380", "no": "서구 공고 제2026-2094호", "title": "기아 오토랜드 광주 2공장 증설 건축 허가 사항 공고",
                                 "dept": "건축과", "date": "2026-10-30"}])
        self.assertEqual(w.classify(rows[0]["title"]), ("A", ["기아"]))

    def test_gwangmyeong_layout_with_spacer_cells(self):
        # 10-30 광명시 실제 모양: 칸 사이마다 빈 <td>, 번호 칸 없이 공고번호부터
        row = ('<tr> <td></td> <td align="center" class="num">광명시 공고 제2026-2301호</td> <td></td> <td class="bbs_list_title">'
               '<a href="javaScript:searchDetail(\'68617\')">기아 오토랜드 광명 EVO플랜트 증축 건축허가 사항 공고</a></td> <td></td> '
               '<td align="center">건축과</td> <td></td> <td align="center" class="num">2026-10-30</td> <td></td> <td align="center" class="num">1</td> <td></td> </tr>')
        spacer = '<tr> <td height="1" colspan="13"></td> </tr>'
        rows = w.parse_rows("<table>" + spacer + row + spacer + "</table>")
        self.assertEqual(rows, [{"mgt": "68617", "no": "광명시 공고 제2026-2301호", "title": "기아 오토랜드 광명 EVO플랜트 증축 건축허가 사항 공고",
                                 "dept": "건축과", "date": "2026-10-30"}])

    def test_baseline_then_new_and_failures(self):
        first = w.run(now=NOW, previous=None, post=fake({"https://eminwon.dangjin.go.kr": page(DJ1, TD_ROW), "http://eminwon.ulju.ulsan.kr": page(UJ1, A_ROW)}),
                      sleep=lambda s: None, cities=CITIES, browser_cities=())
        self.assertEqual(first["status"], "complete")
        self.assertEqual([(x["city"], x["tier"], x["isNew"]) for x in first["items"]], [("울주군", "A", False)])  # 기준선
        self.assertEqual(sorted(first["seen"]), ["당진시", "울주군"])
        dj2 = [("57850", "306", "현대제철(주) 당진제철소 전기로 신설 관련 공유수면 점용 허가 고시", "2026-10-31")] + DJ1
        second = w.run(now=NOW + dt.timedelta(days=1), previous=first,
                       post=fake({"https://eminwon.dangjin.go.kr": page(dj2, TD_ROW), "http://eminwon.ulju.ulsan.kr": page(UJ1, A_ROW)},
                                 down=("http://eminwon.ulju.ulsan.kr",)), sleep=lambda s: None, cities=CITIES, browser_cities=())
        new = [x for x in second["items"] if x["isNew"]]
        self.assertEqual([(x["city"], x["company"], x["tier"], x["date"]) for x in new], [("당진시", "현대제철", "A", "2026-10-31")])
        self.assertIn("not_ancmt_mgt_no=57850", new[0]["url"])
        self.assertEqual(second["status"], "partial")
        self.assertEqual(next(c for c in second["checks"] if c["source"] == "울주군")["error"], "ReadTimeout")
        self.assertIn("울주군", second["seen"])  # 실패한 시·군의 기억은 유지
        self.assertTrue(any(x["id"].startswith("local:울주군") for x in second["items"]))

    def test_page_two_failure_keeps_page_one(self):
        calls = {"n": 0}

        def post(url, data=None, headers=None, timeout=None):
            if data["pageIndex"] == "2":
                return Resp("", 400)
            return Resp(page(DJ1, TD_ROW))
        doc = w.run(now=NOW, previous=None, post=post, sleep=lambda s: None, cities=CITIES[:1], browser_cities=())
        self.assertEqual(doc["checks"][0]["status"], "partial")
        self.assertIn("2쪽 HTTP 400", doc["checks"][0]["error"])
        self.assertEqual(doc["checks"][0]["returned"], 2)
        self.assertEqual(doc["status"], "partial")

    def test_gap_is_reported(self):
        first = w.run(now=NOW, previous=None, post=fake({"https://eminwon.dangjin.go.kr": page(DJ1, TD_ROW)}), sleep=lambda s: None, cities=CITIES[:1], browser_cities=())
        later = [(str(60000 + i), str(400 + i), f"공고 {i}", "2026-11-05") for i in range(3)]
        doc = w.run(now=NOW + dt.timedelta(days=6), previous=first, post=fake({"https://eminwon.dangjin.go.kr": page(later, TD_ROW)}),
                    sleep=lambda s: None, cities=CITIES[:1], browser_cities=())
        self.assertIn("지난 실행 공고가 없음", doc["checks"][0]["error"])
        self.assertEqual((doc["checks"][0]["status"], doc["status"]), ("partial", "partial"))

    def test_all_down_is_failed(self):
        doc = w.run(now=NOW, previous=None, post=fake({"https://eminwon.dangjin.go.kr": "", "http://eminwon.ulju.ulsan.kr": ""},
                                                      down=("https://eminwon.dangjin.go.kr", "http://eminwon.ulju.ulsan.kr")),
                    sleep=lambda s: None, cities=CITIES, browser_cities=())
        self.assertEqual(doc["status"], "failed")

    def test_browser_cities(self):
        # 기자 컴퓨터 브라우저 수집(local_notice_submit): 칸 글자만 오고, 같은 규칙으로 읽는다
        bp = [("인천 부평구", "https://eminwon.icbp.go.kr", "한국GM(부평공장)"), ("구미시", "https://eminwon.gumi.go.kr", "LS전선(구미)"),
              ("청주시", "https://www.cheongju.go.kr", "LS일렉트릭(청주)")]
        fresh = (NOW - dt.timedelta(hours=2)).isoformat()
        browser = {"cities": [
            {"city": "인천 부평구", "fetchedAt": fresh, "rows": [
                {"mgt": "91001", "cells": ["120", "부평구 공고 제2026-1500호", "한국지엠 부평공장 도장공장 증축 건축허가 사항 공고", "건축과", "2026-10-29", "7"]},
                {"mgt": "91000", "cells": ["119", "부평구 공고 제2026-1499호", "도로점용 허가 공고", "건설과", "2026-10-29", "3"]},
                {"mgt": "x y", "cells": ["주입", "제목"]}]},
            {"city": "구미시", "fetchedAt": (NOW - dt.timedelta(hours=40)).isoformat(), "rows": []},
            {"city": "모르는 곳", "fetchedAt": fresh, "rows": []}]}
        doc = w.run(now=NOW, previous=None, post=fake({"https://eminwon.dangjin.go.kr": page(DJ1, TD_ROW)}), sleep=lambda s: None,
                    cities=CITIES[:1], browser=browser, browser_cities=bp)
        by = {c["source"]: c for c in doc["checks"]}
        self.assertEqual((by["인천 부평구"]["status"], by["인천 부평구"]["returned"]), ("ok", 2))  # 관리번호가 이상한 줄은 버림
        self.assertIn("기자 컴퓨터 브라우저 수집", by["인천 부평구"]["via"])
        self.assertEqual(by["구미시"]["status"], "failed")
        self.assertIn("40시간 전", by["구미시"]["error"])
        self.assertIn("브라우저 수집 없음", by["청주시"]["error"])
        self.assertEqual(doc["status"], "partial")
        self.assertEqual(doc["cities"], 4)
        self.assertEqual(sorted(doc["seen"]), ["당진시", "인천 부평구"])  # 실패한 곳은 기준선을 만들지 않음
        gm = [x for x in doc["items"] if x["city"] == "인천 부평구"]
        self.assertEqual([(x["company"], x["isNew"], x["url"].startswith("https://eminwon.icbp.go.kr")) for x in gm], [("한국GM", False, True)])
        # 다음 날 새 공고 → 새 항목
        browser["cities"][0]["fetchedAt"] = (NOW + dt.timedelta(hours=22)).isoformat()
        browser["cities"][0]["rows"].insert(0, {"mgt": "91010", "cells": ["121", "부평구 고시 제2026-300호", "한국GM 부평공장 부지 지구단위계획 결정 고시", "도시계획과", "2026-10-30", "1"]})
        doc2 = w.run(now=NOW + dt.timedelta(days=1), previous=doc, post=fake({"https://eminwon.dangjin.go.kr": page(DJ1, TD_ROW)}),
                     sleep=lambda s: None, cities=CITIES[:1], browser=browser, browser_cities=bp)
        self.assertEqual([x["id"] for x in doc2["items"] if x["isNew"]], ["local:인천 부평구:91010"])

    def test_browser_backup_and_monday(self):
        cities = [("양산시", "https://eminwon.yangsan.go.kr", "넥센타이어(양산)")]
        browser = {"cities": [{"city": "양산시", "fetchedAt": "2026-10-30T08:45:00+09:00",
                               "rows": [{"mgt": "5001", "cells": ["양산시 공고 제2026-10호", "넥센타이어 양산공장 증축 공고", "건축과", "2026-10-30"]}]}]}
        doc = w.run(now=NOW + dt.timedelta(hours=8), previous=None, post=fake({"https://eminwon.yangsan.go.kr": ""}, down=("https://eminwon.yangsan.go.kr",)),
                    sleep=lambda s: None, cities=cities, browser=browser, browser_cities=())
        c = doc["checks"][0]
        self.assertEqual((c["status"], c["returned"]), ("ok", 1))
        self.assertIn("직접 조회 실패(ReadTimeout)", c["via"])
        # 월요일 오전은 금요일 수집까지 받는다, 화요일은 아니다
        monday, tuesday = dt.datetime(2026, 11, 2, 6, 30, tzinfo=KST), dt.datetime(2026, 11, 3, 6, 30, tzinfo=KST)
        self.assertIsNotNone(w.browser_rows(browser, "양산시", monday)[0])
        self.assertIsNone(w.browser_rows(browser, "양산시", tuesday)[0])
        browser["cities"][0]["error"] = "TypeError: Failed to fetch"
        self.assertIn("브라우저 수집 실패", w.browser_rows(browser, "양산시", NOW + dt.timedelta(hours=8))[1])
        del browser["cities"][0]["error"]
        browser["cities"][0]["rows"] = [{"mgt": "bad id", "cells": ["제목"]}]
        self.assertEqual(w.browser_rows(browser, "양산시", NOW + dt.timedelta(hours=8)), (None, "브라우저 수집 0줄(형식 변경 가능)"))

    def test_cheongju_homepage_board(self):
        # 10-30 청주 홈페이지 고시공고 게시판 실제 모양(번호·공고번호·제목·부서·등록일)
        bp = [("청주시", "https://www.cheongju.go.kr", "LS일렉트릭(청주)")]
        browser = {"cities": [{"city": "청주시", "fetchedAt": NOW.isoformat(), "rows": [
            {"mgt": "161030", "cells": ["14781", "청주시 공고 제2026-3000호", "LS일렉트릭 청주사업장 증축 건축허가 사항 공고", "건축디자인과", "2026-10-30"]},
            {"mgt": "161028", "cells": ["14780", "청주시 흥덕구 공고 제2026-1005호", "덕촌3지구 경계결정통지 공시송달 공고", "민원지적과", "2026-10-30"]}]}]}
        doc = w.run(now=NOW, previous=None, post=fake({}), sleep=lambda s: None, cities=[], browser=browser, browser_cities=bp)
        x = doc["items"][0]
        self.assertEqual((x["company"], x["tier"]), ("LS일렉트릭", "A"))
        self.assertEqual(x["url"], "https://www.cheongju.go.kr/www/selectEminwonNoticeView.do?key=281&notAncmtMgtNo=161030")
        self.assertEqual(x["listUrl"], "https://www.cheongju.go.kr/www/selectEminwonNoticeList.do?key=281&pageUnit=60")

    def test_detail_page_gives_full_title_body_and_files(self):
        # 10-31 탐침(울주 68156): 목록 제목은 '…#2ASU O...'로 잘리고 상세에 전체 제목·본문·첨부 파일 이름이 있다
        got = w.parse_detail(ULJU_DETAIL, "건설공사 안전점검 수행기관 지정 공고[온산 고려아연(주), #2ASU O...")
        self.assertEqual(got["title"], "건설공사 안전점검 수행기관 지정 공고[온산 고려아연(주), #2ASU O2 COMPRESSOR ROOM 토건공사]")
        self.assertTrue(got["body"].startswith("우리 군 온산읍 원산리 892번지 일원 상 공장 용도의 건축공사"))
        self.assertNotIn("목록보기", got["body"])
        self.assertEqual(got["files"], ["예정공정표.pdf", "안전점검 수행기관 지정 공고문[온산 고려아연(주) 2ASU O2 COMPRESSOR ROOM 토건공사].hwpx"])
        # 완주 44869 형식(표 칸): 제목 칸 다음 본문
        got = w.parse_detail(WANJU_DETAIL, "전기사업법 위반에 따른 행정처분 사전통지 공시송달 공고")
        self.assertEqual(got["title"], "전기사업법 위반에 따른 행정처분 사전통지 공시송달 공고")
        self.assertTrue(got["body"].startswith("「전기사업법」 제9조"))
        self.assertIsNone(w.parse_detail("<html><body>없는 공고</body></html>", "건설공사 안전점검 수행기관 지정 공고"))

    def test_new_a_b_notices_read_their_detail_once(self):
        first = w.run(now=NOW, previous=None, post=fake({"http://eminwon.ulju.ulsan.kr": page(UJ1, A_ROW)}), sleep=lambda s: None,
                      cities=CITIES[1:], browser_cities=())
        uj2 = [("68156", "2760", "건설공사 안전점검 수행기관 지정 공고[온산 고려아연(주), #2ASU O...", "2026-10-30"),
               ("68157", "2761", "고려아연(주) 온산제련소 직원 표창", "2026-10-30")] + UJ1
        asked = []

        def get(url, headers=None, timeout=None):
            asked.append(url)
            if "68156" in url:
                return Resp(ULJU_DETAIL)
            raise type("ReadTimeout", (Exception,), {})("read timed out")
        doc = w.run(now=NOW + dt.timedelta(days=1), previous=first, post=fake({"http://eminwon.ulju.ulsan.kr": page(uj2, A_ROW)}),
                    sleep=lambda s: None, cities=CITIES[1:], browser_cities=(), get=get)
        by = {x["id"]: x for x in doc["items"]}
        asu = by["local:울주군:68156"]
        self.assertEqual(asu["detail"]["title"], "건설공사 안전점검 수행기관 지정 공고[온산 고려아연(주), #2ASU O2 COMPRESSOR ROOM 토건공사]")
        self.assertEqual(asu["tier"], "A")
        self.assertEqual(by["local:울주군:68157"]["tier"], "B")
        self.assertEqual(by["local:울주군:68157"]["detailError"], "ReadTimeout")  # 실패는 제목만 확인한 상태 그대로
        self.assertNotIn("detail", by["local:울주군:68118"])  # 기준선 항목은 읽지 않는다
        self.assertEqual(len(asked), 2)
        self.assertEqual(doc["details"], {"read": 1, "failed": 1, "skipped": 0})
        # get이 없으면(테스트·다른 호출) 상세를 읽지 않는다
        again = w.run(now=NOW + dt.timedelta(days=1), previous=first, post=fake({"http://eminwon.ulju.ulsan.kr": page(uj2, A_ROW)}),
                      sleep=lambda s: None, cities=CITIES[1:], browser_cities=())
        self.assertNotIn("details", again)

    def test_full_title_regrades(self):
        # 목록 제목이 잘려 사업 낱말이 빠졌던 B가 전체 제목으로 A가 된다
        items = [{"url": "http://x/1", "title": "고려아연(주) 온산제련소 ...", "tier": "B", "companies": ["고려아연"], "company": "고려아연"}]
        page_ = "<dd>고려아연(주) 온산제련소 제2공장 증설 건축허가 공고</dd><div>본문</div>"
        stats = w.read_details(items, lambda url, headers=None, timeout=None: Resp(page_), lambda s: None)
        self.assertEqual((items[0]["tier"], items[0]["listTier"], stats["read"]), ("A", "B", 1))

    def test_parse_cells(self):
        self.assertEqual(w.parse_cells("1", ["", " 10 ", "울산 남구 공고", "건축과", "2026-10-30", "3"])["title"], "울산 남구 공고")
        self.assertIsNone(w.parse_cells("1", ["", "  "]))
        self.assertIsNone(w.parse_cells("<script>", ["제목"]))


if __name__ == "__main__":
    unittest.main()
