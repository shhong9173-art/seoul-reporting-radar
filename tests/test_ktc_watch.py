"""무역위원회 감시: 실제 누리집 형식(10-30 탐침)의 진행 목록·상세 진행일정·회의 안내·개요 PDF 안건·보도자료,
첫 실행 기준선, 새 사건·새 진행·빠짐·회의·보도자료 이벤트, 오래된 사건 상세 생략, 실패와 대량 빠짐은 미확인으로."""
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ktc_watch as k  # noqa: E402
import trade_remedy_watch as w  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 10, 30, 7, 40, tzinfo=KST)
EMPTY_ROW = '<tr> <td colspan="5">등록된 조사건이 없습니다.</td> </tr>'


def case_row(cid, ctype, title, no, product, opened, stage="조사실행"):
    # /proInvestList.do 10-30 원형
    return (f'<tr > <td class="ta-l"> <div class="board-link"> <a href="javascript:viewInvest(\'{cid}\',\'{ctype}\')"> <i>{title}</i> </a> </div> </td> '
            f'<td>{no}</td> <td>{product}</td> <td>{opened}</td> <td>{stage}</td> </tr>')


def list_page(rows):
    return ('<table class="board-list"><caption>목록</caption><thead><tr><th>조사건명</th><th>조사번호</th><th>조사품명</th><th>조사개시일</th>'
            f'<th>진행단계</th></tr></thead><tbody>{"".join(rows)}{EMPTY_ROW if not rows else ""}</tbody></table>'
            '<script>function viewInvest(v, invstg_type_code) { $("#masterId").val(v); }</script>')


def detail(no, title, product, country, kind, review, steps, result=None):
    # /viewInvest.do 10-30 원형(관리정보 th/td 짝, 진행일정 표, 판정결과 요약)
    tl = "".join(f"<tr> <td>{s}</td> <td>{d}</td> </tr>" for s, d in steps)
    res = f"<tr><td>{result[0]}</td><td>{result[1]}</td></tr>" if result else '<tr><td colspan="2">판정결과가 없습니다.</td></tr>'
    return (f'<p class="tit">관리정보</p> <table> <caption>관리정보 테이블로 조사번호, 조사건명, 조사품목, 대상국, 조사유형, 재심종류 정보가 담긴 테이블입니다.</caption> '
            f'<tbody> <tr> <th scope="row">조사번호</th> <td>{no}</td> <th scope="row">조사건명</th> <td id="invstgTitle">{title}</td> </tr> '
            f'<tr> <th>조사품목</th> <td>{product} </td> <th>대상국</th> <td>{country}</td> </tr> <tr> <th>조사유형</th> <td>{kind}</td> '
            f'<th>재심종류</th> <td>{review} </td> </tr> </tbody> </table> <p>진행일정</p> <table> <caption>진행일정 테이블로 진행단계, 진행일 정보가 담긴 '
            f'테이블입니다.</caption> <thead> <tr> <th>진행단계</th> <th>진행일</th> </tr> </thead> <tbody> {tl} </tbody> </table> '
            f'<table><caption>판정결과 요약 테이블로 판정결과, 종결사유 정보가 담긴 테이블입니다.</caption><thead><tr><th>판정결과</th><th>종결사유</th></tr></thead>'
            f'<tbody>{res}</tbody></table>')


def meeting_row(mid, n, title, posted):
    return (f'<tr> <td>{n}</td> <td> <div> <a href="/noticeScheduleView.do?dltnc_id={mid}&menuId=24&pageIndex=1&searchCondition=&searchKeyword=" '
            f'onclick="dltncView(\'{mid}\'); return false;"> <i>{title}</i> </a> </div> </td> <td> <i><img src="/x.png" alt="첨부파일 있음"/></i> </td> '
            f'<td> <i>박만희</i></td> <td>{posted}</td> <td>423</td> </tr>')


def meeting_detail(mid, seq, nth, when, summary):
    return (f'<strong>첨부파일</strong></div> <div class="info-down"> <span> <i> <img class="vtM" src="/pdf.png" alt="pdf" /> </i> '
            f'<a href="#" onclick="fileDownload(\'{mid}\', \'{seq}\'); return false;">제{nth}차 무역위원회 본회의 개요- 261023 - 공개.pdf</a> </span> </div> '
            f'<div class="detail-cont"> <p> &lt; 제{nth}차 10월 무역위원회&gt;<br/><br/> □ 일시 : ‘{when}(금) 14:00~17:00<br/><br/> □ 장소 : 무역센터 51층 중회의실<br/> '
            f'<!-- □ 요약정보 --> 회의 안건: {summary}<br/> ** 자세한 사항은 첨부파일을 참조하시기 바랍니다. </p> </div>'
            '<script>function fileDownload(dltnc_id, seq_no){ var params = {}; }</script>')


# 제478차 본회의 개요 PDF에서 pypdf가 뽑은 글(10-30 탐침, 제목 중복 글자 그대로)
AGENDA_478 = ("- 1 - 제제제제478478478차 차 무역위원회 무역위원회 본회의 본회의 개요개요제478차 무역위원회 본회의 개요 1. 회의 개요 ㅇ (일시/장소) ’26. 10. 23(금) "
              "14:00~17:00 /무역센터 51층(소회의실) ㅇ (참석위원 ) 위원장 포함 8명 2. 회의 안건 □ 정기보고 ㅇ (정기 제2026-11호)제477차무역위원회회의록 □ 일반보고 "
              "ㅇ (일반 제2026-18호) 중국산 무계목강관 에 대한 덤핑사실 및 국내산업피해 유무(원심) 개시결정 보고 ㅇ (일반 제2026-19호) 외장형 모뎀 연결장치 -Ⅱ 원산지 "
              "표시위반 불공정무역행위 조사개시 보고 ㅇ (일반 제2026-20호) 플라스틱 필름 원산지 표시위반 불공정 무역행위 조사개시 보고 □ 의결 ㅇ (의결제2026-24호)중국산 "
              "아연 및 아연합금 표면처리 냉간압연 제품의 덤핑사실및국내산업 피해유무(원심) 최종판정 ㅇ (의결 제2026-25호) 중국산 인쇄제판용 평면모양 사진플레이트에 "
              "대한덤핑방지관세 부과종료재심사(2차) 최종판정 ㅇ (의결 제2026-26호) 화장품 상표권 침해 불공정무역행위 관련 무역위원회처분에 대한이의신청결정")
AGENDA_479 = ("제479차 무역위원회 본회의 개요 2. 회의 안건 □ 정기보고 ㅇ (정기 제2026-12호)제478차무역위원회회의록 □ 의결 ㅇ (의결 제2026-27호)중국산 석도강판의 "
              "덤핑사실및국내산업피해유무 예비판정(원심) ㅇ (의결 제2026-28호) 자동차용 배터리팩 특허권 침해 불공정무역행위 여부 판정")

STEEL = ("00000875", "10100001", "중국산 무계목강관의 덤핑사실 및 국내산업피해 유무 조사", "구제 23-2026-9호", "무계목강관", "2026.10.08")
EV = ("00000845", "10100002", "커넥티드 전기자동차 특허권 침해 불공정무역행위 조사", "구제 4-1-2025-1", "커넥티드 전기자동차 ", "2025.06.30")
OLD = ("00000493", "10100002", "낚싯대케이스 특허권 침해", "구제 4-1-2008-6", "낚싯대케이스", "2008.07.23")
TINPLATE = ("00000868", "10100001", "중국산 석도강판의 덤핑사실 및 국내산업피해 유무", "구제23-2026-5호", "석도강판", "2026.07.10")
EV_STEPS = [("조사개시", "2025-06-30"), ("피신청인 질의서 송부", "2025-07-01"), ("판정시한 2차 연장", "2026-02-25"), ("피신청인 최후 의견서 제출", "2026-04-20")]
DETAILS = {
    "00000875": detail("구제 23-2026-9호", STEEL[2], "무계목강관", "중국", "반덤핑조사", "원심",
                       [("조사개시", "2026-10-08"), ("예비조사", ""), ("공청회", ""), ("최종판정", "")]),
    "00000845": detail("구제 4-1-2025-1", EV[2], "커넥티드 전기자동차", "", "불공정무역행위", "원심", EV_STEPS),
    "00000493": detail("구제 4-1-2008-6", OLD[2], "낚싯대케이스", "", "", "", [("조사개시", "2008-07-23"), ("결정", "2008-09-01")]),
    "00000868": detail("구제23-2026-5호", TINPLATE[2], "석도강판", "중국", "반덤핑조사", "원심", [("조사개시", "2026-07-10"), ("예비조사", "")]),
}
NEWS_ROW = ('<tr > <td class="a"><i>{n}</i></td> <td class="ta-l"> <div class="board-link"> <a href="/boardView.do?bbs_id={i}&menuId=57&pageIndex=1" '
            'onclick="boardView(\'{i}\'); return false;"> <i>{t}</i> </a> </div> </td> <td class="a"> <img src="/f.png" /> </td> '
            '<td class="a"> <i>박만희</i> </td> <td class="a"><i>329</i></td> </tr>')


class Site:
    """가짜 무역위원회 누리집: 경로·인자별 응답, 내려간 경로, 호출 기록."""

    def __init__(self, cases, details=None, meetings=(), meeting_pages=None, news=(), down=(), list_status=200):
        self.cases, self.details = list(cases), dict(DETAILS if details is None else details)
        self.meetings, self.meeting_pages, self.news = list(meetings), dict(meeting_pages or {}), list(news)
        self.down, self.list_status, self.calls = set(down), list_status, []

    def post(self, path, data):
        self.calls.append((path, dict(data)))
        if path in self.down:
            raise type("ConnectTimeout", (Exception,), {})("timed out")
        if path == "/proInvestList.do":
            if self.list_status != 200:
                return self.list_status, ""
            p = int(data.get("pageIndex", "1"))
            return 200, list_page([case_row(*c) for c in self.cases[(p - 1) * 10:p * 10]])
        if path == "/viewInvest.do":
            return 200, self.details.get(data["masterId"], "<html>잘못된 접근</html>")
        if path == "/noticeScheduleList.do":
            return 200, "<table>" + "".join(meeting_row(*m) for m in self.meetings) + "</table>"
        if path == "/reportNewsList.do":
            return 200, "<table>" + "".join(NEWS_ROW.format(n=300 + j, i=i, t=t) for j, (i, t) in enumerate(self.news)) + "</table>"
        raise AssertionError(path)

    def get(self, path, params, referer=None, binary=False):
        self.calls.append((path, dict(params)))
        if path in self.down:
            raise type("ConnectTimeout", (Exception,), {})("timed out")
        if path == "/noticeScheduleView.do":
            return 200, self.meeting_pages[params["dltnc_id"]]
        if path == "/dltncFileDownload.do":
            return 200, b"%PDF-1.7 " + params["dltnc_id"].encode()
        if path == "/boardView.do":
            return 200, f"<div>제목 등록일 2026-10-{int(params['bbs_id']) % 28 + 1:02d} 13:50:12.978 조회수 330</div>"
        raise AssertionError(path)


M478 = ("00000311", 310, "제478차 10월 무역위원회 개최 안내", "2026-10-16")
M479 = ("00000312", 311, "제479차 11월 무역위원회 개최 안내", "2026-11-13")
PAGES = {"00000311": meeting_detail("00000311", "0000", 478, "26.10.23", "7건(정기보고1, 일반보고3, 의결3)"),
         "00000312": meeting_detail("00000312", "0001", 479, "26.11.20", "3건(정기보고1, 의결2)")}
PDF_TEXT = {"00000311": AGENDA_478, "00000312": AGENDA_479}


def fake_pdf(data):
    return PDF_TEXT.get(data.decode().split()[-1]), None


class KtcTest(unittest.TestCase):
    def setUp(self):
        self._pdf, k.pdf_text = k.pdf_text, fake_pdf

    def tearDown(self):
        k.pdf_text = self._pdf

    def test_parsers_on_real_layout(self):
        rows = k.parse_cases(list_page([case_row(*STEEL), case_row("00000297", "10100002", "신발", "", "신발", "1900.01.01")]) + EMPTY_ROW)
        self.assertEqual(rows[0], {"id": "00000875", "type": "10100001", "title": STEEL[2], "no": "구제 23-2026-9호", "product": "무계목강관",
                                   "opened": "2026-10-08", "stage": "조사실행"})
        self.assertIsNone(rows[1]["opened"])  # 1900-01-01은 빈 날짜 자리값
        d = k.parse_detail(DETAILS["00000875"])
        self.assertEqual((d["country"], d["kind"], d["review"], d["timeline"], d["pending"], d["result"]),
                         ("중국", "반덤핑조사", "원심", [["조사개시", "2026-10-08"]], ["예비조사", "공청회", "최종판정"], None))
        self.assertIsNone(k.parse_detail("<html>잘못된 접근</html>"))
        gone = k.parse_detail(detail("x", "t", "p", "", "불공정무역행위", "원심", [("조사개시", "2024-07-16")], result=("철회", "종결")))
        self.assertEqual(gone["result"], "철회 · 종결")
        m = k.parse_meeting_detail(PAGES["00000311"])
        self.assertEqual(m, {"meetingOn": "2026-10-23", "summary": "7건(정기보고1, 일반보고3, 의결3)",
                             "files": [{"seq": "0000", "name": "제478차 무역위원회 본회의 개요- 261023 - 공개.pdf"}]})
        agenda = k.parse_agenda(AGENDA_478)
        self.assertEqual([(a["kind"], a["no"], a["beat"]) for a in agenda],
                         [("보고", "2026-18", True), ("보고", "2026-19", False), ("보고", "2026-20", False),
                          ("의결", "2026-24", True), ("의결", "2026-25", False), ("의결", "2026-26", False)])
        self.assertTrue(agenda[3]["text"].startswith("중국산 아연 및 아연합금 표면처리 냉간압연 제품"))
        self.assertTrue(agenda[3]["text"].endswith("최종판정"))
        news = k.parse_news("<table>" + NEWS_ROW.format(n=1, i="00002113", t="중국산 아연 표면처리 냉연제품에 잠정 덤핑방지관세 부과 건의 의결 <span>새글</span>") + "</table>")
        self.assertEqual(news, [{"id": "00002113", "title": "중국산 아연 표면처리 냉연제품에 잠정 덤핑방지관세 부과 건의 의결"}])

    def test_baseline_then_changes(self):
        site = Site([EV, OLD, TINPLATE], meetings=[M478], meeting_pages=PAGES, news=[("00002297", "무역위, 중국산 아연도금냉연 덤핑조사 최종판정")])
        first, ev, check = k.collect(None, NOW, site, sleep=lambda s: None)
        self.assertEqual(ev, [])  # 기준선
        self.assertEqual((check["status"], check["returned"], first["listComplete"]), ("ok", 3, True))
        self.assertEqual(len(first["meetings"][0]["agenda"]), 6)  # 첫 실행에도 가장 최근 회의 안건은 읽어 둔다
        self.assertTrue(first["cases"][0]["beat"] and not first["cases"][1]["beat"])
        self.assertEqual(first["cases"][0]["url"], "https://www.ktc.go.kr/viewInvest.do?menuId=11&masterId=00000845&invstg_type_code=10100002")

        # 다음 날: 무계목강관 새 조사, 전기차 사건 진행일정 한 줄 추가, 석도강판 사건이 목록에서 빠짐, 새 회의, 새 보도자료
        details = dict(DETAILS)
        details["00000845"] = detail("구제 4-1-2025-1", EV[2], "커넥티드 전기자동차", "", "불공정무역행위", "원심", EV_STEPS + [("판정시한 3차 연장", "2026-10-30")])
        details["00000868"] = detail("구제23-2026-5호", TINPLATE[2], "석도강판", "중국", "반덤핑조사", "원심",
                                     [("조사개시", "2026-07-10"), ("예비판정", "2026-10-29")], result=("부정", "조사종결"))
        site2 = Site([STEEL, EV, OLD], details=details, meetings=[M479, M478], meeting_pages=PAGES,
                     news=[("00002298", "중국산 석도강판 덤핑조사 예비판정"), ("00002297", "무역위, 중국산 아연도금냉연 덤핑조사 최종판정")])
        doc, ev, check = k.collect(first, NOW + dt.timedelta(days=1), site2, sleep=lambda s: None)
        got = {e["ktcKind"]: e for e in ev}
        self.assertEqual(sorted(got), ["case", "left", "meeting", "news", "step"])
        self.assertEqual((got["case"]["tier"], got["case"]["label"]), ("B", "무역위 새 조사 · 구제 23-2026-9호"))
        self.assertIn("개시 2026-10-08, 반덤핑조사/원심, 대상국 중국", got["case"]["text"])
        self.assertIn("새 진행: 판정시한 3차 연장 2026-10-30", got["step"]["text"])
        self.assertEqual(got["step"]["tier"], "B")
        self.assertIn("마지막 진행: 조사개시 2026-07-10; 예비판정 2026-10-29; 판정결과: 부정 · 조사종결", got["left"]["text"])
        self.assertIn("(개최 2026-11-20) 안건 3건(정기보고1, 의결2) — 의결: 중국산 석도강판의 덤핑사실및국내산업피해유무 예비판정(원심) / 자동차용 배터리팩",
                      got["meeting"]["text"])
        self.assertEqual(got["meeting"]["tier"], "B")
        self.assertEqual((got["news"]["tier"], got["news"]["text"]), ("C", "중국산 석도강판 덤핑조사 예비판정 (등록 2026-10-03)"))
        self.assertEqual([x["id"] for x in doc["left"]], ["00000868"])
        self.assertEqual(doc["cases"][1]["firstSeen"], first["cases"][0]["firstSeen"])
        # 2008년 사건은 첫 실행에 한 번 읽은 뒤로 상세를 다시 읽지 않는다
        self.assertNotIn(("/viewInvest.do", {"menuId": "11", "masterId": "00000493", "invstg_type_code": "10100002"}), site2.calls)
        self.assertEqual(check["status"], "ok")

    def test_meeting_without_pdf_then_agenda(self):
        bare = PAGES["00000312"].replace("fileDownload", "noFile")
        first = k.collect(None, NOW, Site([EV], meetings=[M478], meeting_pages=PAGES), sleep=lambda s: None)[0]
        doc, ev, _ = k.collect(first, NOW + dt.timedelta(hours=1), Site([EV], meetings=[M479, M478], meeting_pages={**PAGES, "00000312": bare}),
                               sleep=lambda s: None)
        self.assertEqual([(e["ktcKind"], e["tier"]) for e in ev], [("meeting", "C")])
        self.assertIn("안건 PDF 미확인(PDF 첨부 없음)", ev[0]["text"])
        doc2, ev2, _ = k.collect(doc, NOW + dt.timedelta(hours=2), Site([EV], meetings=[M479, M478], meeting_pages=PAGES), sleep=lambda s: None)
        self.assertEqual([(e["ktcKind"], e["tier"]) for e in ev2], [("agenda", "B")])
        self.assertIn("의결: 중국산 석도강판", ev2[0]["text"])

    def test_failures_are_unconfirmed(self):
        first = k.collect(None, NOW, Site([EV, TINPLATE], meetings=[M478], meeting_pages=PAGES), sleep=lambda s: None)[0]
        # 목록이 안 열리면 지난 사건을 그대로 두고 빠짐으로 보지 않는다
        doc, ev, check = k.collect(first, NOW + dt.timedelta(days=1), Site([], meetings=[M478], meeting_pages=PAGES, list_status=500),
                                   sleep=lambda s: None)
        self.assertEqual(ev, [])
        self.assertEqual(check["status"], "partial")
        self.assertIn("진행 목록 1쪽 HTTP 500", check["error"])
        self.assertTrue(all(c.get("stale") for c in doc["cases"]) and len(doc["cases"]) == 2)
        # 한꺼번에 많이 빠지면 누리집 이상으로 보고 보류
        many = [(f"0000090{i}", "10100001", f"사건 {i}", f"구제 {i}", "철강", "2026.01.0" + str(i + 1)) for i in range(8)]
        base = k.collect(None, NOW, Site(many, details={}, meetings=[M478], meeting_pages=PAGES), sleep=lambda s: None)[0]
        doc, ev, check = k.collect(base, NOW + dt.timedelta(days=1), Site(many[:1], details={}, meetings=[M478], meeting_pages=PAGES),
                                   sleep=lambda s: None)
        self.assertEqual([e for e in ev if e["ktcKind"] == "left"], [])
        self.assertIn("한꺼번에 7건 빠져 판단 보류", check["error"])
        # 모두 내려가면 실패
        down = Site([], down={"/proInvestList.do", "/noticeScheduleList.do", "/reportNewsList.do"})
        self.assertEqual(k.collect(None, NOW, down, sleep=lambda s: None)[2]["status"], "failed")

    def test_trade_remedy_run_carries_ktc(self):
        def get(url, params=None, headers=None, timeout=None):
            raise type("ConnectTimeout", (Exception,), {})("offline")
        cfg = {"pages": [], "taricSeeds": []}
        first = w.run(cfg, now=NOW, get=get, sleep=lambda s: None, ktc_http=Site([EV], meetings=[M478], meeting_pages=PAGES))
        self.assertEqual(next(c for c in first["checks"] if c["source"] == "무역위원회")["status"], "ok")
        self.assertEqual(len(first["ktc"]["cases"]), 1)
        second = w.run(cfg, now=NOW + dt.timedelta(days=1), previous=first, get=get, sleep=lambda s: None,
                       ktc_http=Site([STEEL, EV], meetings=[M478], meeting_pages=PAGES))
        self.assertEqual([e["id"] for e in second["events"] if e["pageId"] == "ktc"], ["ktc:case:00000875"])
        # 누리집이 모두 안 열리면 지난 무역위 구역을 그대로(0건 아님)
        third = w.run(cfg, now=NOW + dt.timedelta(days=2), previous=second, get=get, sleep=lambda s: None,
                      ktc_http=Site([], down={"/proInvestList.do", "/noticeScheduleList.do", "/reportNewsList.do"}))
        self.assertTrue(third["ktc"]["stale"])
        self.assertEqual(len(third["ktc"]["cases"]), 2)
        self.assertIn("ktc:case:00000875", [e["id"] for e in third["events"]])
        # 무역위 감시를 넘기지 않은 실행(시험)은 지난 구역을 그대로 싣는다
        self.assertEqual(w.run(cfg, now=NOW, previous=second, get=get, sleep=lambda s: None)["ktc"], second["ktc"])


if __name__ == "__main__":
    unittest.main()
