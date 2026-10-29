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

    def test_namgu_layout_without_notice_number(self):
        row = ('<tr> <td >40994</td> <td class="left"> <div class="list_subject"> <div class="link"> <a href="emwp/gov/mogaha/ntis/web/ofr/action/'
               'OfrAction.do?not_ancmt_mgt_no=54887&amp;subCheck=Y" onclick="searchDetail(\'54887\');return false;" onkeypress="">'
               '현대모비스(주) 울산공장 증설 관련 도시관리계획 결정 고시</a> </div> </div> </td> <td>도시과</td> <td>2026-10-30</td> <td>3</td> </tr>')
        self.assertEqual(w.parse_rows("<table>" + row + "</table>"),
                         [{"mgt": "54887", "no": None, "title": "현대모비스(주) 울산공장 증설 관련 도시관리계획 결정 고시", "dept": "도시과", "date": "2026-10-30"}])

    def test_baseline_then_new_and_failures(self):
        first = w.run(now=NOW, previous=None, post=fake({"https://eminwon.dangjin.go.kr": page(DJ1, TD_ROW), "http://eminwon.ulju.ulsan.kr": page(UJ1, A_ROW)}),
                      sleep=lambda s: None, cities=CITIES)
        self.assertEqual(first["status"], "complete")
        self.assertEqual([(x["city"], x["tier"], x["isNew"]) for x in first["items"]], [("울주군", "A", False)])  # 기준선
        self.assertEqual(sorted(first["seen"]), ["당진시", "울주군"])
        dj2 = [("57850", "306", "현대제철(주) 당진제철소 전기로 신설 관련 공유수면 점용 허가 고시", "2026-10-31")] + DJ1
        second = w.run(now=NOW + dt.timedelta(days=1), previous=first,
                       post=fake({"https://eminwon.dangjin.go.kr": page(dj2, TD_ROW), "http://eminwon.ulju.ulsan.kr": page(UJ1, A_ROW)},
                                 down=("http://eminwon.ulju.ulsan.kr",)), sleep=lambda s: None, cities=CITIES)
        new = [x for x in second["items"] if x["isNew"]]
        self.assertEqual([(x["city"], x["company"], x["tier"], x["date"]) for x in new], [("당진시", "현대제철", "A", "2026-10-31")])
        self.assertIn("not_ancmt_mgt_no=57850", new[0]["url"])
        self.assertEqual(second["status"], "partial")
        self.assertEqual(next(c for c in second["checks"] if c["source"] == "울주군")["error"], "ReadTimeout")
        self.assertIn("울주군", second["seen"])  # 실패한 시·군의 기억은 유지
        self.assertTrue(any(x["id"].startswith("local:울주군") for x in second["items"]))

    def test_gap_is_reported(self):
        first = w.run(now=NOW, previous=None, post=fake({"https://eminwon.dangjin.go.kr": page(DJ1, TD_ROW)}), sleep=lambda s: None, cities=CITIES[:1])
        later = [(str(60000 + i), str(400 + i), f"공고 {i}", "2026-11-05") for i in range(3)]
        doc = w.run(now=NOW + dt.timedelta(days=6), previous=first, post=fake({"https://eminwon.dangjin.go.kr": page(later, TD_ROW)}),
                    sleep=lambda s: None, cities=CITIES[:1])
        self.assertIn("지난 실행 공고가 없음", doc["checks"][0]["error"])
        self.assertEqual((doc["checks"][0]["status"], doc["status"]), ("partial", "partial"))

    def test_all_down_is_failed(self):
        doc = w.run(now=NOW, previous=None, post=fake({"https://eminwon.dangjin.go.kr": "", "http://eminwon.ulju.ulsan.kr": ""},
                                                      down=("https://eminwon.dangjin.go.kr", "http://eminwon.ulju.ulsan.kr")),
                    sleep=lambda s: None, cities=CITIES)
        self.assertEqual(doc["status"], "failed")


if __name__ == "__main__":
    unittest.main()
