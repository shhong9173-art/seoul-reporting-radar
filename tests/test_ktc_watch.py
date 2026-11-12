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

    def __init__(self, cases, details=None, meetings=(), meeting_pages=None, news=(), down=(), list_status=200, news_pages=None):
        self.cases, self.details = list(cases), dict(DETAILS if details is None else details)
        self.meetings, self.meeting_pages, self.news = list(meetings), dict(meeting_pages or {}), list(news)
        self.news_pages = dict(news_pages or {})
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
            rows = self.news if data.get("pageIndex", "1") == "1" else self.news_pages.get(int(data["pageIndex"]), [])
            return 200, "<table>" + "".join(NEWS_ROW.format(n=300 + j, i=i, t=t) for j, (i, t) in enumerate(rows)) + "</table>"
        raise AssertionError(path)

    def post_binary(self, path, data, referer=None):
        self.calls.append((path, dict(data)))
        assert path == "/boardFileDownload.do"
        bid = data["bbs_id"]
        if bid in NEWS_PDF and data["seq_no"] == "0001":
            return 200, b"%PDF-1.7 news:" + bid.encode()
        return 200, b"PK\x03\x04hwpx"

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


# 보도자료 첨부 PDF 글(11-11 probe 212 운영 원문에서 옮긴 구간)
BUTYL = ("중국산 부틸 아크릴레이트에 대한 덤핑조사 최종판정 1건과 자동차용 배터리팩 등 불공정무역행위 조사 5건, 총 6건을 심의‧의결하였다. 중국산 부틸 아크릴레이트에 "
         "대한 덤핑조사 건은 작년 7월 엘지화학이 조사를 신청한 건으로, 지난 2월 12일 예비판정을 거쳐 … 조사과정에서 당사자간 라이선스 계약이 체결되어 당사자간 합의하에 "
         "신청인이 조사신청 철회를 요청하였다. 무역위 무역조사실은 그간 우리 업계로부터 중국산 봉강에 대한 반덤핑 조사신청을 받아")
NAOH = ("고체 수산화나트륨은 백색의 고체로서 비누‧세제 제조 등에 사용된다. 올해 3월 ㈜영진이 덤핑조사를 신청하였고, 조사대상 공급자는 중국 동루이 등 3 - 3 - "
        "참고1 (예비판정) 중국 및 대만산 고체수산화나트륨 덤핑조사 (원심)□ 조사 개요ㅇ (신청인)주식회사영진 ㅇ (조사대상공급자)중국동루이")
BAR = ("봉강은 자동차, 건설 중장비 등의 부품 제조 등에 활용되는 것으로, 올해 2월 세아베스틸과 세아창원특수강이 덤핑조사를 신청하였으며 조사대상공급자는 중국 다예 "
       "- 4 - 참고2 (예비판정) 중국산 봉강 덤핑조사 (원심)□ 조사 개요ㅇ (신청인)㈜세아베스틸,㈜세아창원특수강ㅇ (조사대상공")
GALV = ("아연도금냉연은 건축자재, 자동차 부품 등에 활용된다. 금번 조사건은 작년 11월 동국씨엠 등 3사의 신청에 따라 조사가 개시되었다. 무역위원회는 중국산 무계목강관에 대한 "
        "덤핑조사 개시를 보고받았다. 동 덤핑조사 건은 일진제강이 조사신청하여 10월 8일 조사가 개시되었으며, - 3 - 참고1 (최종판정) 중국산 아연도금냉연 덤핑조사 "
        "(원심)□ 조사 개요 ㅇ (신청인) 동국씨엠㈜, 케이지스틸㈜, ㈜세아씨엠 ㅇ (조사대상공급자)")
TUBE = "- 2 - 참고[의결] 태국산 이음매 없는 동관 덤핑조사 최종판정□조사개요ㅇ (신청인)능원금속공업주식회사,엘에스메탈주식회사ㅇ (조사대상"
# probe 213 운영 원문: 대리인 괄호, 조사종결 불공정 사건, 글자 사이를 띄운 머리(한화솔루션 PVC 페이스트 수지), 표 다음 품목 모르는 문장
BUTYL_TABLE = ("- 3 - 참고1 (최종판정) 중국산 부틸 아크릴레이트 (원심)□조사개요ㅇ (신청인)㈜엘지화학(대리인: 법무법인 정률, DKC글로벌컨설팅)ㅇ (조사대상공급자)중국타이싱순커 "
               "- 4 - 참고2 (조사종결) 자동차용 배터리팩 특허권 침해 조사□조사개요ㅇ (신청인)튤립이노베이션케이에프티ㅇ (피신청인)외국기업A,Bㅇ")
PSR = ("- 3 - 참고1[의 결] 독·프·노 르 웨 이 및 스 웨 덴 산 폴 리 염 화 비 닐 페 이 스 트 수 지 덤 핑 조 사 □조사개요ㅇ (신청인)한화솔루션주식회사ㅇ (조사대상공급자)독비놀릿")
ROBOT = ("이번 덤핑조사건은 ‘25년 3월에 HD현대로보틱스가 조사 신청한 것으로, 지난해 5월에 조사를 개시하여 - 3 - 참고1 (최종판정) 일본 및 중국산 산업용 로봇 (원심)□조사개요ㅇ "
         "(신청인)에이치디현대로보틱스㈜ ㅇ (조사대상공급자)일본 화낙")
# 판정 예고 테스트용 가상 보도자료(신청인 이름은 테스트 값)
TIN_OPEN = "- 3 - 참고1 (조사개시) 중국산 석도강판 덤핑조사 (원심)□ 조사 개요 ㅇ (신청인) 케이지스틸㈜, ㈜테스트석도 ㅇ (조사대상공급자) 중국 A사"
NEWS_PDF = {"00002297": GALV, "00002147": BUTYL, "00002050": TIN_OPEN}


def fake_pdf(data):
    tail = data.decode(errors="ignore").split()[-1]
    if tail.startswith("news:"):
        return NEWS_PDF.get(tail[5:]), None
    return PDF_TEXT.get(tail), None


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

    def test_applicants_from_press_pdf_11_11(self):
        self.assertEqual(k.applicants_in(BUTYL), [{"product": "중국산 부틸 아크릴레이트", "names": ["엘지화학"], "beat": ["LG화학"], "how": "문장"}])
        self.assertEqual(k.applicants_in(NAOH), [{"product": "중국 및 대만산 고체수산화나트륨", "names": ["영진"], "beat": [], "how": "표"}])
        self.assertEqual(k.applicants_in(BAR), [{"product": "중국산 봉강", "names": ["세아베스틸", "세아창원특수강"], "beat": [], "how": "표"}])   # 세아 계열사는 출입처 아님
        galv = k.applicants_in(GALV)
        self.assertEqual(galv[0], {"product": "중국산 아연도금냉연", "names": ["동국씨엠", "케이지스틸", "세아씨엠"], "beat": ["동국씨엠", "KG스틸"], "how": "표"})
        self.assertEqual((galv[1]["names"], galv[1]["product"], galv[1]["how"]), (["일진제강"], "중국산 무계목강관", "문장"))
        self.assertEqual(k.applicants_in(TUBE), [{"product": "태국산 이음매 없는 동관", "names": ["능원금속공업", "엘에스메탈"], "beat": [], "how": "표"}])
        self.assertEqual(k.applicants_in("무역위원회는 공청회를 개최하였다. 신청인측과 피신청인측 이해관계인 등 20여 명이 참석하였다."), [])
        bt = k.applicants_in(BUTYL_TABLE)
        self.assertEqual(bt[0], {"product": "중국산 부틸 아크릴레이트", "names": ["엘지화학"], "beat": ["LG화학"], "how": "표"})   # 대리인(법무법인·컨설팅) 뺌
        self.assertEqual((bt[1]["product"], bt[1]["names"]), ("자동차용 배터리팩 특허권 침해", ["튤립이노베이션케이에프티"]))
        self.assertEqual(k.applicants_in(PSR), [{"product": "독·프·노르웨이및스웨덴산폴리염화비닐페이스트수지", "names": ["한화솔루션"], "beat": ["한화솔루션"], "how": "표"}])
        self.assertEqual(k.applicants_in(ROBOT), [{"product": "일본 및 중국산 산업용 로봇", "names": ["에이치디현대로보틱스"], "beat": [], "how": "표"}])
        # 운영 PDF 글 조각: 표 칸 이름 안 띄어쓰기(pypdf 판에 따라 '튤립 이노베이션케이에프티'·'한 화 솔 루 션')는 붙인다
        self.assertEqual(k.applicants_in("참고2 (조사종결) 자동차용 배터리팩 특허권 침해 조사□조사개요ㅇ (신청인)튤립 이노베이션케이에프티ㅇ (피신청인)외국기업A")[0]["names"],
                         ["튤립이노베이션케이에프티"])
        self.assertEqual(k.applicants_in("참고1 (의결) 중국산 PVC 페이스트 수지 덤핑조사 □ ㅇ (신청인) 한 화 솔 루 션 주식회사, ㈜ 엘지 화학 ㅇ (조사대상")[0]["beat"],
                         ["한화솔루션", "LG화학"])

    def test_same_product_across_press_case_agenda_11_12(self):
        sp = k.same_product
        self.assertTrue(sp("중국산 아연도금냉연", "중국산 아연 및 아연합금 표면처리 냉간압연 제품의 덤핑사실및국내산업 피해유무(원심) 최종판정"))
        self.assertTrue(sp("중국산 아연도금냉연", "중국산 아연 및 아연합금 표면처리 냉간압연 제품의 덤핑사실 및 국내산업피해 유무 조사"))
        self.assertTrue(sp("독·프·노르웨이및스웨덴산폴리염화비닐페이스트수지", "독일, 프랑스, 노르웨이 및 스웨덴산 폴리염화비닐 페이스트 수지의 덤핑사실 및 국내산업피해 유무"))
        self.assertTrue(sp("중국산 무계목강관", "중국산 무계목강관 에 대한 덤핑사실 및 국내산업피해 유무(원심) 개시결정 보고"))
        self.assertTrue(sp("중국 및 대만산 고체수산화나트륨", "중국 및 대만산 고체 수산화나트륨의 덤핑사실 및 국내산업피해 유무"))
        self.assertTrue(sp("중국산 석도강판", "중국산 석도강판의 덤핑사실및국내산업피해유무 예비판정(원심)"))
        self.assertFalse(sp("중국산 봉강", "중국산 H형강의 덤핑사실 및 국내산업피해 유무"))
        self.assertFalse(sp("태국산 이음매 없는 동관", "중국산 무계목강관의 덤핑사실 및 국내산업피해 유무"))
        self.assertFalse(sp("중국산 폴리에스테르 장섬유 완전연신사", "중국산 폴리염화비닐 서스펜션 수지의 덤핑사실 및 국내산업피해 유무"))
        self.assertFalse(sp("대만산 PET 필름", "중국산 PET 필름의 덤핑사실"))                   # 같은 품목이라도 나라가 다르면 다른 사건
        self.assertFalse(sp("중국산 PET 필름", "중국산 PET 수지의 덤핑사실"))

    def test_preview_from_older_press_page_11_12(self):
        first = k.collect(None, NOW, Site([TINPLATE], meetings=[M478], meeting_pages=PAGES, news=[("00002297", "무역위, 중국산 아연도금냉연 덤핑조사 최종판정")]),
                          sleep=lambda s: None)[0]
        self.assertEqual(first.get("newsDepth"), 1)
        # 다음 실행: 보도자료 2쪽(지난 석도강판 개시 보도자료)을 읽고 첨부 신청인을 채운 뒤, 다가오는 제479차(11-20) 안건 석도강판 예비판정에 붙인다
        site = Site([TINPLATE], meetings=[M479, M478], meeting_pages=PAGES, news=[("00002297", "무역위, 중국산 아연도금냉연 덤핑조사 최종판정")],
                    news_pages={2: [("00002050", "무역위, 중국산 석도강판 덤핑조사 개시")]})
        doc, ev, _ = k.collect(first, NOW + dt.timedelta(days=1), site, sleep=lambda s: None)
        self.assertEqual(doc["newsDepth"], 2)
        old = next(n for n in doc["news"] if n["id"] == "00002050")
        self.assertTrue(old["older"])
        self.assertEqual(old["applicants"][0]["beat"], ["KG스틸"])
        self.assertFalse([e for e in ev if e["id"] == "ktc:news:00002050"])            # 지난 보도자료는 이벤트 없음
        pv = [e for e in ev if e["ktcKind"] == "preview"]
        self.assertEqual(len(pv), 1)
        self.assertEqual((pv[0]["tier"], pv[0]["company"], pv[0]["label"]), ("B", "KG스틸", "무역위 회의 예고(개최 2026-11-20)"))
        self.assertIn("의결: 중국산 석도강판의 덤핑사실및국내산업피해유무 예비판정(원심) — 신청인 케이지스틸, 테스트석도(보도자료 「무역위, 중국산 석도강판 덤핑조사 개시」", pv[0]["text"])
        self.assertIn("결과(판정·세율)는 회의 뒤 보도자료·의결서로 확인", pv[0]["text"])
        tin = next(c for c in doc["cases"] if c["id"] == "00000868")
        self.assertEqual(tin["applicant"]["beat"], ["KG스틸"])                           # 사건에도 신청인
        m479 = next(m for m in doc["meetings"] if m["id"] == "00000312")
        self.assertEqual(m479["agenda"][0]["applicant"]["names"], ["케이지스틸", "테스트석도"])
        # 다시 돌려도 예고는 한 번만
        _, ev2, _ = k.collect(doc, NOW + dt.timedelta(days=1, hours=3), Site([TINPLATE], meetings=[M479, M478], meeting_pages=PAGES,
                                                                              news=[("00002297", "무역위, 중국산 아연도금냉연 덤핑조사 최종판정")]), sleep=lambda s: None)
        self.assertFalse([e for e in ev2 if e["ktcKind"] == "preview"])
        # 지난 회의(제478차 10-23) 안건엔 신청인만 붙고 예고는 없다
        m478 = next(m for m in doc["meetings"] if m["id"] == "00000311")
        self.assertEqual(next(a for a in m478["agenda"] if "아연" in a["text"])["applicant"]["beat"], ["동국씨엠", "KG스틸"])

    def test_press_applicant_makes_beat_item_and_backfills(self):
        site = Site([EV], news=[("00002147", "무역위, 중국산 부틸 아크릴레이트에 덤핑방지관세 부과 건의")])
        first = k.collect(None, NOW, site, sleep=lambda s: None)[0]
        self.assertNotIn("applicants", first["news"][0])   # 기준선은 첨부를 안 읽는다
        site2 = Site([EV], news=[("00002297", "무역위, 중국산 아연도금냉연, 옵셋인쇄판 덤핑조사 최종판정"), ("00002147", "무역위, 중국산 부틸 아크릴레이트에 덤핑방지관세 부과 건의"),
                                 ("00002306", "청년의 시각에서 바라본 무역구제")])
        doc, ev, _ = k.collect(first, NOW + dt.timedelta(days=1), site2, sleep=lambda s: None)
        news_ev = {e["id"]: e for e in ev if e["ktcKind"] == "news"}
        g = news_ev["ktc:news:00002297"]
        self.assertEqual((g["tier"], g["company"], g["beat"]), ("B", "동국씨엠·KG스틸", True))
        self.assertIn("· 첨부 PDF의 신청인 — 중국산 아연도금냉연: 동국씨엠, 케이지스틸, 세아씨엠; 중국산 무계목강관: 일진제강", g["text"])
        self.assertEqual((news_ev["ktc:news:00002306"]["tier"], news_ev["ktc:news:00002306"].get("company")), ("C", None))   # 판정 아닌 글은 첨부 안 읽음
        self.assertNotIn(("/boardFileDownload.do", {"bbs_id": "00002306", "seq_no": "0001"}), site2.calls)
        # 지난 판정 보도자료(기준선 때 본 부틸)는 이벤트 없이 신청인만 채운다
        butyl = next(n for n in doc["news"] if n["id"] == "00002147")
        self.assertEqual(butyl["applicants"][0]["beat"], ["LG화학"])
        self.assertEqual(butyl["applicantsV"], k.APPLICANTS_V)
        self.assertNotIn("ktc:news:00002147", news_ev)
        # 다시 돌려도 첨부를 또 받지 않는다
        site3 = Site([EV], news=site2.news)
        k.collect(doc, NOW + dt.timedelta(days=2), site3, sleep=lambda s: None)
        self.assertFalse([c for c in site3.calls if c[0] == "/boardFileDownload.do"])
        # 규칙 판이 바뀌면(예전 판 결과) 다시 읽는다
        old_v = {**doc, "news": [{**n, "applicantsV": 1} if n["id"] == "00002147" else n for n in doc["news"]]}
        site4 = Site([EV], news=site2.news)
        k.collect(old_v, NOW + dt.timedelta(days=3), site4, sleep=lambda s: None)
        self.assertIn(("/boardFileDownload.do", {"bbs_id": "00002147", "seq_no": "0001"}), site4.calls)

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
