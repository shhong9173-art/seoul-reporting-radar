import datetime as dt
import io
import sys
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import kr_report_notes as n  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 11, 15, 19, 20, tzinfo=KST)


def report(sanctions, suits, consol):
    rows = "".join(f"<TR>{''.join(f'<TD>{c}</TD>' for c in r)}</TR>" for r in sanctions)
    # 실제 보고서 표는 두 칸(신규 연결·연결 제외)이 늘 함께 있고, 없으면 '-'다
    consol = list(consol) + [(k, "-", "-") for k in ("신규 연결", "연결 제외") if k not in [c[0] for c in consol]]
    cons = "".join(f"<TR><TD>{k}</TD><TD>{name}</TD><TD>{why}</TD></TR>" for k, name, why in consol)
    return ('<SECTION-1><TITLE ATOC="Y">1. 회사의 개요</TITLE><P>가. 연결대상 종속회사 개황</P>'
            f'<TABLE><TR><TH>구분</TH><TH>자회사</TH><TH>사유</TH></TR>{cons}</TABLE></SECTION-1>'
            '<TITLE ATOC="Y">2. 우발부채 등에 관한 사항</TITLE><P>가. 중요한 소송사건</P>'
            + "".join(f"<P>{s}</P>" for s in suits) +
            '<P>나. 견질 또는 담보용 어음ㆍ수표 현황</P><TABLE><TR><TD>은행</TD><TD>1매</TD><TD>백지어음 보관 중</TD></TR></TABLE>'
            '<P>다. 채무보증 현황</P><TABLE><TR><TD>Doosan Enerbility America</TD><TD>지급보증 3,500억원으로 증가</TD></TR></TABLE>'
            '<TITLE ATOC="Y">3. 제재 등과 관련된 사항</TITLE><P>가. 제재현황</P>'
            f'<TABLE><TR><TH>일자</TH><TH>제재기관</TH><TH>대상자</TH><TH>처벌 또는 조치 내용</TH><TH>사유</TH></TR>{rows}</TABLE>'
            '<TITLE ATOC="Y">4. 작성기준일 이후 발생한 주요사항</TITLE><P>해당사항 없음</P>')


H1 = report([["2025.03.10", "공정거래위원회", "당사", "과징금 3억원", "하도급법 위반"]],
            ["(1) 당사는 2025년 4월 서울중앙지방법원에 제기된 손해배상청구(소가 80억원)의 피고로 계류 중입니다."],
            [("신규 연결", "Doosan GridTech LLC", "신규 설립")])
Q3 = report([["2025.03.10", "공정거래위원회", "당사", "과징금 3.0억원", "하도급법 위반"],
             ["2026.09.03", "고용노동부 창원지청", "당사", "과태료 1,500만원", "퇴직연금 최소적립금 미달"]],
            ["(1) 당사는 2025년 4월 서울중앙지방법원에 제기된 손해배상청구(소가 85억원)의 피고로 계류 중입니다.",
             "(2) 당사는 2026년 8월 미국 텍사스 남부 연방지방법원에 제기된 계약위반 소송(청구액 USD 40,000천)의 피고입니다."],
            [("신규 연결", "Doosan GridTech LLC", "신규 설립"), ("연결 제외", "두산메카텍㈜", "지분 매각")])


def zipped(text):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("main.xml", text)
    return b.getvalue()


class R:
    def __init__(self, body=None, content=b"", status=200):
        self._body, self.content, self.status_code = body, content, status

    def json(self):
        return self._body

    def raise_for_status(self):
        pass


class Notes(unittest.TestCase):
    def test_sections_read_sanctions_suits_and_consolidation_only(self):
        s = n.sections(Q3)
        self.assertEqual(len(s["sanction"]), 2)
        self.assertIn("2026.09.03 | 고용노동부 창원지청 | 당사 | 과태료 1,500만원 | 퇴직연금 최소적립금 미달", s["sanction"])
        self.assertEqual(len(s["suit"]), 2)                                  # 견질어음·채무보증 표는 읽지 않는다
        self.assertFalse(any("지급보증" in x or "백지어음" in x for x in s["suit"]))
        self.assertEqual(s["consol"], ["신규 연결: Doosan GridTech LLC | 신규 설립", "연결 제외: 두산메카텍㈜ | 지분 매각"])
        self.assertEqual(n.sections("<TITLE>1. 사업의 개요</TITLE><P>본문</P>"), {})   # 못 찾은 대목은 키가 없다
        self.assertEqual(n.key_of("과징금 3억원 (2025.03.10)"), n.key_of("과징금 3.0억원 2025-03-10"))

    def run_once(self, previous=None, lists=None, docs=None, calls=None, year=2026, report="11014", now=NOW):
        lists = lists or {"00159616": [{"report_nm": "분기보고서 (2026.09)", "rcept_no": "20261113000111", "rcept_dt": "20261113"},
                                        {"report_nm": "반기보고서 (2026.06)", "rcept_no": "20260814000222", "rcept_dt": "20260814"}]}
        docs = docs or {"20261113000111": Q3, "20260814000222": H1}

        def get(url, params=None, headers=None, timeout=None):
            if calls is not None:
                calls.append((url.rsplit("/", 1)[1], (params or {}).get("rcept_no")))
            if url.endswith("/list.json"):
                rows = lists.get(params["corp_code"])
                return R(body={"status": "000", "list": rows} if rows else {"status": "013"})
            if url.endswith("/document.xml"):
                return R(content=zipped(docs[params["rcept_no"]]))
            raise AssertionError(url)

        return n.run("k", now=now, year=year, report=report, previous=previous, get=get, sleep=lambda s: None,
                     registry={"companies": {"두산에너빌리티": {"corp_code": "00159616"}}}, table={}, only=["두산에너빌리티"])

    def test_new_lines_against_the_previous_report_and_no_second_download(self):
        calls = []
        doc = self.run_once(calls=calls)
        c = doc["companies"]["두산에너빌리티"]
        self.assertEqual((c["status"], c["rcept"], c["baseRcept"], c["missing"]), ("ok", "20261113000111", "20260814000222", []))
        self.assertEqual(c["new"]["sanction"], ["2026.09.03 | 고용노동부 창원지청 | 당사 | 과태료 1,500만원 | 퇴직연금 최소적립금 미달"])   # 숫자 표기만 바뀐 과징금 줄은 아니다
        self.assertEqual(len(c["new"]["suit"]), 1)                                # 소가만 바뀐 (1)은 아니고 새 소송 (2)만
        self.assertIn("텍사스 남부 연방지방법원", c["new"]["suit"][0])
        self.assertEqual(c["new"]["consol"], ["연결 제외: 두산메카텍㈜ | 지분 매각"])
        ev = {e["kind"]: e for e in doc["events"]}
        self.assertEqual(sorted(ev), ["소송", "연결 범위", "제재"])
        self.assertEqual((ev["제재"]["id"], ev["제재"]["tier"], ev["제재"]["late"], ev["제재"]["url"]),
                         ("rptnote:00159616:202611014:sanction", "B", True, "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261113000111"))
        self.assertEqual(doc["summary"]["newLines"], {"after": 0, "held": 0, "sanction": 1, "suit": 1, "consol": 1})
        self.assertEqual([c for c in calls if c[0] == "document.xml"], [("document.xml", "20260814000222"), ("document.xml", "20261113000111")])
        calls.clear()
        again = self.run_once(previous=doc, calls=calls)                           # 같은 접수번호면 다시 받지 않는다
        self.assertEqual([c for c in calls if c[0] == "document.xml"], [])
        self.assertEqual(len(again["events"]), 3)
        # 다음 분기: 저장해 둔 줄 열쇠가 앞 보고서 노릇을 한다(앞 보고서를 또 받지 않는다) — 사업보고서(11011)
        calls.clear()
        fy = report([["2026.09.03", "고용노동부 창원지청", "당사", "과태료 1,500만원", "퇴직연금 최소적립금 미달"],
                     ["2026.12.01", "공정거래위원회", "당사", "시정명령 및 과징금 20억원", "부당한 공동행위"]], [], [])
        lists = {"00159616": [{"report_nm": "사업보고서 (2026.12)", "rcept_no": "20270318000333", "rcept_dt": "20270318"}]}

        def get(url, params=None, headers=None, timeout=None):
            calls.append((url.rsplit("/", 1)[1], (params or {}).get("rcept_no")))
            if url.endswith("/list.json"):
                return R(body={"status": "000", "list": lists[params["corp_code"]]})
            return R(content=zipped(fy))

        nxt = n.run("k", now=dt.datetime(2027, 3, 19, 6, 20, tzinfo=KST), year=2026, report="11011", previous=again, get=get, sleep=lambda s: None,
                    registry={"companies": {"두산에너빌리티": {"corp_code": "00159616"}}}, table={}, only=["두산에너빌리티"])
        self.assertEqual([c for c in calls if c[0] == "document.xml"], [("document.xml", "20270318000333")])
        self.assertEqual(nxt["companies"]["두산에너빌리티"]["new"]["sanction"], ["2026.12.01 | 공정거래위원회 | 당사 | 시정명령 및 과징금 20억원 | 부당한 공동행위"])
        fresh = [e for e in nxt["events"] if e["id"].startswith("rptnote:00159616:202611011")]
        self.assertEqual((len(fresh), "late" in fresh[0]), (1, False))              # 접수 다음 날 읽었고 첫 실행이 아니다 — 늦게 읽은 표시가 없다(알림 대상)

    def test_two_column_case_tables_tell_a_new_case_from_a_changed_line(self):
        def case(parties, progress, amount="1,200"):
            return ("<TABLE><TR><TD>구분</TD><TD>내용</TD></TR><TR><TD>소제기일</TD><TD>2024.03.05</TD></TR>"
                    f"<TR><TD>소송 당사자</TD><TD>{parties}</TD></TR><TR><TD>소송의 내용</TD><TD>공사대금 청구</TD></TR>"
                    f"<TR><TD>소송가액(백만원)</TD><TD>{amount}</TD></TR><TR><TD>진행상황</TD><TD>{progress}</TD></TR></TABLE>")
        head = '<TITLE ATOC="Y">2. 우발부채 등에 관한 사항</TITLE><P>가. 중요한 소송사건</P>'
        tail = '<P>나. 견질 또는 담보용 어음ㆍ수표 현황</P><TITLE ATOC="Y">3. 제재 등과 관련된 사항</TITLE>'
        old = n.sections(head + case("원고: 갑건설 / 피고: 당사", "1심 진행 중") + tail)
        new = n.sections(head + case("원고: 갑건설 / 피고: 당사", "1심 원고 일부 승소(2026.09.18), 당사 항소", "1,350")
                         + case("원고: 을에너지 / 피고: 당사", "1심 진행 중", "48,000") + tail)
        self.assertEqual(len(old["suit"]), 1)                                # 표 하나가 한 줄
        self.assertTrue(old["suit"][0].startswith("소제기일: 2024.03.05 ▸ 소송 당사자: 원고: 갑건설 / 피고: 당사 ▸ 소송의 내용: 공사대금 청구"))
        fresh = n.fresh_lines(new["suit"], set(n.keys_of(old["suit"])))
        self.assertEqual(len(fresh), 2)
        self.assertEqual(fresh[0], "〔앞 보고서에도 있던 건 · 바뀐 줄〕 소송 당사자: 원고: 갑건설 / 피고: 당사 — 진행상황: 1심 원고 일부 승소(2026.09.18), 당사 항소")   # 금액만 바뀐 줄은 아니다
        self.assertTrue(fresh[1].startswith("〔처음 보는 건〕 소제기일: 2024.03.05 ▸ 소송 당사자: 원고: 을에너지 / 피고: 당사"))
        self.assertEqual(n.fresh_lines(old["suit"], set(n.keys_of(old["suit"]))), [])
        self.assertTrue(all(len(k) == 10 for k in n.keys_of(old["suit"])))   # 저장하는 것은 글자가 아니라 해시

    def test_an_omitted_quarterly_section_is_not_a_new_line_and_keeps_the_old_keys(self):
        thin = Q3.replace(Q3[Q3.index("<P>가. 제재현황</P>"):Q3.index('<TITLE ATOC="Y">4.')],
                          "<P>기업공시서식 작성기준에 따라 분기보고서에는 기재를 생략합니다. 반기보고서를 참고하시기 바랍니다.</P>")
        self.assertIsNone(n.sections(thin)["sanction"])                      # 0줄(해당사항 없음)과 다르다
        none = Q3.replace(Q3[Q3.index("<P>가. 제재현황</P>"):Q3.index('<TITLE ATOC="Y">4.')], "<P>가. 제재현황</P><P>해당사항 없음</P>")
        self.assertEqual(n.sections(none)["sanction"], [])
        base = report([["2025.03.10", "공정거래위원회", "당사", "과징금 3억원", "하도급법 위반"], ["2025.05.02", "관세청", "당사", "과태료 200만원", "신고 오류"],
                       ["2025.06.11", "환경부", "당사", "경고", "자가측정 미이행"]], [], [])
        doc = self.run_once(docs={"20261113000111": thin, "20260814000222": base})
        c = doc["companies"]["두산에너빌리티"]
        self.assertEqual((c["omitted"], c["new"].get("sanction"), "sanction" in c["lines"], "sanction" in c["found"]), (["sanction"], None, False, False))
        self.assertEqual(doc["checks"][0]["omitted"], ["sanction"])
        self.assertTrue(set(n.keys_of(n.sections(base)["sanction"])) <= set(c["keys"]["sanction"]))   # 앞 보고서 열쇠를 이어 둔다
        # 다음 사업보고서가 같은 세 줄을 다시 적어도 새 줄이 아니다
        fy = report([["2025.03.10", "공정거래위원회", "당사", "과징금 3억원", "하도급법 위반"], ["2025.05.02", "관세청", "당사", "과태료 200만원", "신고 오류"],
                     ["2025.06.11", "환경부", "당사", "경고", "자가측정 미이행"], ["2026.11.20", "고용노동부", "당사", "과태료 1,500만원", "퇴직연금 최소적립금 미달"]], [], [])
        nxt = self.run_once(previous=doc, lists={"00159616": [{"report_nm": "사업보고서 (2026.12)", "rcept_no": "20270318000333", "rcept_dt": "20270318"}]},
                            docs={"20270318000333": fy}, year=2026, report="11011", now=dt.datetime(2027, 3, 18, 19, 40, tzinfo=KST))
        self.assertEqual(nxt["companies"]["두산에너빌리티"]["new"]["sanction"], ["2026.11.20 | 고용노동부 | 당사 | 과태료 1,500만원 | 퇴직연금 최소적립금 미달"])
        # 앞 보고서(1분기)가 대목을 생략했으면 비교하지 않는다 — 반기보고서의 제재 줄 전부가 새 줄로 쏟아지지 않는다(probe 250: 포스코홀딩스 126줄)
        lists = {"00159616": [{"report_nm": "반기보고서 (2026.06)", "rcept_no": "20260814000222", "rcept_dt": "20260814"},
                              {"report_nm": "분기보고서 (2026.03)", "rcept_no": "20260515000444", "rcept_dt": "20260515"}]}
        half = self.run_once(lists=lists, docs={"20260814000222": base, "20260515000444": thin}, year=2026, report="11012", now=dt.datetime(2026, 8, 14, 19, 40, tzinfo=KST))
        h = half["companies"]["두산에너빌리티"]
        self.assertEqual((h["nobase"], h["new"].get("sanction"), len(h["keys"]["sanction"])), (["sanction"], None, 3))

    def test_headers_unit_lines_and_period_words_are_not_new_lines(self):
        head = '<TITLE ATOC="Y">3. 제재 등과 관련된 사항</TITLE><P>가. 지배회사① 수사ㆍ사법기관의 제재현황1) 회사 제재현황</P>'
        table = ("<TABLE><TR><TD>일자</TD><TD>제재기관</TD><TD>대상자</TD><TD>처벌 또는 조치내용</TD><TD>금전적 제재금액</TD><TD>사유 및 근거법령</TD></TR>"
                 "<TR><TD>2025. 3. 6.</TD><TD>울산지방법원</TD><TD>회사</TD><TD>벌금 부과</TD><TD>100만원</TD><TD>산업안전보건법 제173조</TD></TR></TABLE>"
                 "<P>[기준일 : 2026.09.30] (원화단위 : 백만원)</P><P>[Lotte Chemical California, Inc.]</P>")
        self.assertEqual(n.sections(head + table)["sanction"], ["2025. 3. 6. | 울산지방법원 | 회사 | 벌금 부과 | 100만원 | 산업안전보건법 제173조"])
        self.assertEqual(n.key_of("당반기말 현재 연결실체가 피소되어 계류중인 소송사건은 451건(소송가액 1조 2,649억원)입니다."),
                         n.key_of("당분기말 현재 연결실체가 피소되어 계류중인 소송사건은 448건(소송가액 1조 2,310억원)입니다."))
        long = "진행상황: " + " ".join(f"2024. {m}. 1. 제{m}회 변론기일" for m in range(1, 13)) * 3 + " 2026. 9. 18. 1심 판결 선고(원고 일부 승소)"
        self.assertTrue(n.tail(long).startswith("진행상황: … "))
        self.assertTrue(n.tail(long).endswith("2026. 9. 18. 1심 판결 선고(원고 일부 승소)"))
        self.assertEqual(n.tail("진행상황: 1심 진행 중"), "진행상황: 1심 진행 중")

    def test_events_after_the_period_need_no_baseline_and_held_for_sale_keeps_prose_only(self):
        notes = ('<TITLE ATOC="N">15. 매각예정자산 및 중단영업 (연결)</TITLE><TABLE><TR><TD>유형자산</TD><TD>12,323</TD><TD>7,357</TD></TR>'
                 '<TR><TE>연결실체는 상기 자산에 대하여 고압탱크 사업부 라인 가동 중단 및 사업장 매각 결정, 미국 오펠라이카 공장의 운영 중단 결정에 따라 매각예정자산 처리하였습니다.</TE></TR></TABLE>'
                 '<TITLE ATOC="N">31. 보고기간후사건 (연결)</TITLE><TABLE><TR><TE>연결실체는 보고기간 종료일 이후인 2026년 10월 30일자로 종속기업인 Hanwha Cimarron LLC (지분율 100%)의 '
                 '지분 전부를 HANWHA DEFENSE USA,INC.에 매각하였습니다(매각대금 58,962백만원).</TE></TR></TABLE>'
                 '<TITLE ATOC="N">30. 보고기간후사건</TITLE><P>당사는 2026년 10월 20일 제45회 무보증사채 2,000억원을 발행하였습니다.</P>')
        s = n.sections(Q3 + notes)
        self.assertEqual(len(s["after"]), 2)                                   # 연결·별도 주석을 합친다
        self.assertIn("Hanwha Cimarron LLC (지분율 100%)의 지분 전부를 HANWHA DEFENSE USA,INC.에 매각하였습니다(매각대금 58,962백만원).", s["after"][0])
        self.assertEqual(len(s["held"]), 1)                                    # 숫자 표 줄은 빼고 글로 적은 줄만
        doc = self.run_once(docs={"20261113000111": Q3 + notes, "20260814000222": H1})   # 앞 보고서(H1)에는 두 주석이 없다
        c = doc["companies"]["두산에너빌리티"]
        self.assertEqual((len(c["new"]["after"]), c["new"].get("held"), c["nobase"], c["v"]), (2, None, ["held"], n.VERSION))
        ev = {e["kind"]: e for e in doc["events"]}
        self.assertEqual(ev["보고기간 후 사건"]["id"], "rptnote:00159616:202611014:after")
        # 앞서 읽은 접수번호라도 읽는 대목이 늘기 전(v 없음)에 읽은 것은 한 번 다시 읽는다
        old = {**doc, "companies": {"두산에너빌리티": {k: v for k, v in c.items() if k != "v"}}}
        calls = []
        again = self.run_once(previous=old, docs={"20261113000111": Q3 + notes, "20260814000222": H1}, calls=calls)
        self.assertEqual(len([x for x in calls if x[0] == "document.xml"]), 2)
        self.assertEqual({e["detectedAt"] for e in again["events"]}, {doc["events"][0]["detectedAt"]})
        # 실제 꼴(probe 252): 사건이 열로 나뉜 표 — 칸 이름 줄, 사건을 글로 적은 세 칸 줄, 숫자뿐인 두 칸 줄
        real = ('<TITLE ATOC="N">31. 보고기간후사건 (연결)</TITLE><P>수정을 요하지 않는 보고기간후사건에 대한 공시</P><TABLE>'
                '<TR><TD></TD><TD>타인을 위하여 제공한 담보</TD><TD>주요 종속기업의 처분</TD></TR>'
                '<TR><TD>수정을 요하지 않는 보고기간후사건의 성격에 대한 기술</TD><TE>회사는 잠실마이스㈜의 PF대출 대주단으로부터의 차입에 대하여 회사가 보유하는 주식을 담보로 제공하기로 2026년 10월 13일 이사회에서 결의하였습니다.</TE>'
                '<TE>연결실체는 보고기간 종료일 이후인 2026년 10월 30일자로 종속기업인 Hanwha Cimarron LLC (지분율 100%)의 지분 전부를 HANWHA DEFENSE USA,INC.에 매각하였습니다(매각대금 58,962백만원).</TE></TR>'
                '<TR><TD>담보설정금액</TD><TD>68,271</TD></TR><TR><TD>처분일자</TD><TD>2026-10-30</TD></TR><TR><TD>매각대가</TD><TD>58,962</TD></TR></TABLE>'
                '<TITLE ATOC="N">15. 매각예정자산 및 중단영업 (연결)</TITLE><TABLE><TR><TD>자산의 분류</TD><TD>매각예정으로 분류된 비유동 자산이나 처분자산집단</TD><TD>재고자산</TD><TD>0</TD></TR>'
                '<TR><TD>자산의 분류 합계</TD><TD>79,500</TD><TE>연결실체는 상기 자산에 대하여 미국 시마론 오펠라이카 공장의 운영 중단 결정에 따라 매각예정자산 처리하였습니다.</TE></TR></TABLE>')
        r = n.sections(Q3 + real)
        self.assertEqual(r["after"], ["회사는 잠실마이스㈜의 PF대출 대주단으로부터의 차입에 대하여 회사가 보유하는 주식을 담보로 제공하기로 2026년 10월 13일 이사회에서 결의하였습니다.",
                                      "연결실체는 보고기간 종료일 이후인 2026년 10월 30일자로 종속기업인 Hanwha Cimarron LLC (지분율 100%)의 지분 전부를 HANWHA DEFENSE USA,INC.에 매각하였습니다(매각대금 58,962백만원)."])
        self.assertEqual(r["held"], ["연결실체는 상기 자산에 대하여 미국 시마론 오펠라이카 공장의 운영 중단 결정에 따라 매각예정자산 처리하였습니다."])
        # 주석마다 제목 표시가 없는 보고서: 소제목으로 찾는다
        plain = Q3 + '<P>31. 보고기간후사건</P><P>당사는 2026년 11월 3일 이사회에서 인도네시아 법인 청산을 결의하였습니다.</P><TITLE ATOC="Y">4. 재무제표</TITLE><P>다른 대목</P>'
        self.assertEqual(n.sections(plain)["after"], ["당사는 2026년 11월 3일 이사회에서 인도네시아 법인 청산을 결의하였습니다."])

    def test_late_reads_are_marked_and_a_reread_keeps_the_first_seen_time(self):
        first = self.run_once()                                               # 감시 첫 실행 — 늦게 읽은 것으로 표시(알림 없음)
        self.assertTrue(all(e.get("late") for e in first["events"]))
        lists = {"00159616": [{"report_nm": "[기재정정]분기보고서 (2026.09)", "rcept_no": "20261117000999", "rcept_dt": "20261117"},
                              {"report_nm": "분기보고서 (2026.09)", "rcept_no": "20261113000111", "rcept_dt": "20261113"},
                              {"report_nm": "반기보고서 (2026.06)", "rcept_no": "20260814000222", "rcept_dt": "20260814"}]}
        again = self.run_once(previous=first, lists=lists, docs={"20261117000999": Q3, "20260814000222": H1}, now=dt.datetime(2026, 11, 17, 19, 40, tzinfo=KST))
        self.assertEqual(again["companies"]["두산에너빌리티"]["rcept"], "20261117000999")
        self.assertEqual({e["detectedAt"] for e in again["events"]}, {first["events"][0]["detectedAt"]})   # 줄이 그대로면 처음 본 때를 지킨다

    def test_missing_report_and_unreadable_document_are_not_zero(self):
        doc = self.run_once(lists={"00159616": [{"report_nm": "반기보고서 (2026.06)", "rcept_no": "20260814000222", "rcept_dt": "20260814"}]})
        self.assertEqual((doc["checks"][0]["note"], doc["events"]), ("이 기간 보고서 미제출(또는 제출 대상 아님)", []))
        doc = self.run_once(docs={"20261113000111": "<TITLE>1. 사업</TITLE><P>제재 낱말만 있음</P>", "20260814000222": H1})
        self.assertEqual((doc["status"], doc["checks"][0]["status"], doc["events"]), ("partial", "failed", []))
        self.assertEqual(doc["companies"]["두산에너빌리티"]["status"], "pending")      # 앞 보고서 열쇠는 남긴다


if __name__ == "__main__":
    unittest.main()
