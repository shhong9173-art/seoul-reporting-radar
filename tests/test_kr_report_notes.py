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
        self.assertIn("〔일자〕2026.09.03 | 〔제재기관〕고용노동부 창원지청 | 〔대상자〕당사 | 〔처벌 또는 조치 내용〕과태료 1,500만원 | 〔사유〕퇴직연금 최소적립금 미달", s["sanction"])   # 표 줄에는 칸 이름을 붙인다(11-17)
        self.assertEqual(n.key_of("〔일자〕2026.09.03 | 〔제재기관〕고용노동부 창원지청 | 〔대상자〕당사 | 〔처벌 또는 조치 내용〕과태료 1,500만원 | 〔사유〕퇴직연금 최소적립금 미달"), n.key_of("2026.09.03 | 고용노동부 창원지청 | 당사 | 과태료 1,500만원 | 퇴직연금 최소적립금 미달"))   # 칸 이름은 열쇠에서 빠진다
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
                body = docs[params["rcept_no"]]
                return R(content=body if isinstance(body, bytes) else zipped(body))
            raise AssertionError(url)

        return n.run("k", now=now, year=year, report=report, previous=previous, get=get, sleep=lambda s: None,
                     registry={"companies": {"두산에너빌리티": {"corp_code": "00159616"}}}, table={}, only=["두산에너빌리티"])

    def test_new_lines_against_the_previous_report_and_no_second_download(self):
        calls = []
        doc = self.run_once(calls=calls)
        c = doc["companies"]["두산에너빌리티"]
        self.assertEqual((c["status"], c["rcept"], c["baseRcept"], c["missing"]), ("ok", "20261113000111", "20260814000222", []))
        self.assertEqual(c["new"]["sanction"], ["〔일자〕2026.09.03 | 〔제재기관〕고용노동부 창원지청 | 〔대상자〕당사 | 〔처벌 또는 조치 내용〕과태료 1,500만원 | 〔사유〕퇴직연금 최소적립금 미달"])   # 숫자 표기만 바뀐 과징금 줄은 아니다
        self.assertEqual(len(c["new"]["suit"]), 1)                                # 소가만 바뀐 (1)은 아니고 새 소송 (2)만
        self.assertIn("텍사스 남부 연방지방법원", c["new"]["suit"][0])
        self.assertEqual(c["new"]["consol"], ["연결 제외: 두산메카텍㈜ | 지분 매각"])
        ev = {e["kind"]: e for e in doc["events"]}
        self.assertEqual(sorted(ev), ["소송", "연결 범위", "제재"])
        self.assertEqual((ev["제재"]["id"], ev["제재"]["tier"], ev["제재"]["late"], ev["제재"]["url"]),
                         ("rptnote:00159616:202611014:sanction", "B", True, "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261113000111"))
        self.assertEqual(doc["summary"]["newLines"], {"after": 0, "dated": 0, "held": 0, "sanction": 1, "suit": 1, "consol": 1, "guarantee": 0, "deal": 0, "order": 0})
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
        self.assertEqual(nxt["companies"]["두산에너빌리티"]["new"]["sanction"], ["〔일자〕2026.12.01 | 〔제재기관〕공정거래위원회 | 〔대상자〕당사 | 〔처벌 또는 조치 내용〕시정명령 및 과징금 20억원 | 〔사유〕부당한 공동행위"])
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
        self.assertEqual(nxt["companies"]["두산에너빌리티"]["new"]["sanction"], ["〔일자〕2026.11.20 | 〔제재기관〕고용노동부 | 〔대상자〕당사 | 〔처벌 또는 조치 내용〕과태료 1,500만원 | 〔사유〕퇴직연금 최소적립금 미달"])
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
        self.assertEqual(n.sections(head + table)["sanction"], ["〔일자〕2025. 3. 6. | 〔제재기관〕울산지방법원 | 〔대상자〕회사 | 〔처벌 또는 조치내용〕벌금 부과 | 〔금전적 제재금액〕100만원 | 〔사유 및 근거법령〕산업안전보건법 제173조"])
        self.assertEqual(n.key_of("당반기말 현재 연결실체가 피소되어 계류중인 소송사건은 451건(소송가액 1조 2,649억원)입니다."),
                         n.key_of("당분기말 현재 연결실체가 피소되어 계류중인 소송사건은 448건(소송가액 1조 2,310억원)입니다."))
        self.assertEqual(n.key_of("2025. 3. 6. | 울산지방법원 | 벌금 부과 | 각 100만원"), n.key_of("2025. 3. 6. | 울산지방법원 | 벌금 부과 | 각 1,000,000 원"))
        self.assertEqual(n.key_of("과태료 부과 | 192만원"), n.key_of("과태료 부과 | 1,920,000원"))
        self.assertNotEqual(n.key_of("과태료 부과 | 192만원"), n.key_of("과징금 부과 | 192만원"))
        self.assertEqual(n.key_of("지배기업은 2026년 11월 9일 LOTTE Chemical Louisiana LLC의 지분 40%를 기초자산으로 하는 주가수익스왑 계약의 계약조건을 재협의하였으며"),
                         n.key_of("당사는 2026년 11월 9일 LOTTE Chemical Louisiana LLC의 지분 40%를 기초자산으로 하는 주가수익스왑 계약의 계약조건을 재협의하였으며"))
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

    def test_table_sections_guarantee_deal_order_and_after_the_reporting_date(self):
        # 11-17 3분기보고서 전수 비교에서 다섯 대목 밖에 있던 줄들(실제 표 꼴을 줄인 것)
        def guar(rows):
            body = "".join(f"<TR><TD>{a}</TD><TD>{b}</TD><TD>종속기업</TD><TD>{c}</TD><TD>{d}</TD></TR>" for a, b, c, d in rows)
            return ("<P>다. 이행보증, 자금보충 약정 등</P><P>당사는 해외 현지법인의 계약에 대해 이행보증 및 자금보충 약정을 제공하고 있습니다.</P>"
                    f"<TABLE><TR><TH>구분</TH><TH>회사명</TH><TH>관 계</TH><TH>금액</TH><TH>이사회승인</TH></TR>{body}</TABLE>")
        marubeni = ("Hanwha Japan CO.,LTD.와 Marubeni Corporation 간의 Sale and Purchase Contract 상의 의무를 보증(2013.02.19. 체결)",
                    "Hanwha Japan CO.,LTD./Marubeni Corporation", "USD 131,000", "2012.12.12")
        rwe = ("Hanwha Q CELLS America Inc.의 모듈 매각 거래 관련 이행보증 납품 일정 및 품질 보증 등 납품 이행 관련 의무 전반에 대한 이행보증 (2026.08.04 체결)",
               "Hanwha Q CELLS America Inc./RWE Solar Development, LLC", "USD 157,200", "2026.07.21")

        def deal(rows):
            body = "".join("<TR>" + "".join(f"<TD>{c}</TD>" for c in r) + "</TR>" for r in rows)
            return ("<P>2. 대주주와의 자산양수도 등</P><P>(1) 당분기 중 지배회사의 이해관계자와의 자산양수도 거래 (단위: 천원)</P>"
                    "<TABLE><TR><TH>거래 상대방</TH><TH>거래유형</TH><TH>지배회사과의관계</TH><TH>거래일자</TH><TH>거래 대상물</TH><TH>거래 목적</TH>"
                    f"<TH>금 액</TH><TH>금액 산정 기준</TH><TH>관련 손익 (주1)</TH><TH>비 고</TH></TR>{body}</TABLE>")
        fund = ["Clean H2 Infra Fund S.L.P", "출자", "관계기업", "2026-05-13", "Clean H2 Infra Fund S.L.P 의 보통주", "10차 투자금 납입", "8,991,248", "지분비율에 따른 출자금액 산정", "-", "이사회 승인 완료"]
        koruz = ["Kor-UZ Gas Chemical Investment Ltd.", "처분", "공동기업", "2026-07-15", "Kor-UZ Gas Chemical Investment Ltd. 의 보통주",
                 "UZ-KOR로부터 수취한 대여금 원금 재분배", "56,538,631", "주주들의 지분비율에 따른 감자금액 산정", "18,480,232", "이사회 승인 완료"]

        def order(rows):
            body = "".join("<TR>" + "".join(f"<TD>{c}</TD>" for c in r) + "</TR>" for r in rows)
            return ('<P>■ 포스코퓨처엠 당분기말 현재 수주잔고 총액은 약 43,418백만원입니다. (단위 : 백만원)</P><TABLE>'
                    '<TR><TH ROWSPAN="2">품목</TH><TH ROWSPAN="2">수주일자</TH><TH ROWSPAN="2">납기</TH><TH COLSPAN="2">수주총액</TH><TH COLSPAN="2">기납품액</TH><TH COLSPAN="2">수주잔고</TH></TR>'
                    f'<TR><TH>수량</TH><TH>금액</TH><TH>수량</TH><TH>금액</TH><TH>수량</TH><TH>금액</TH></TR>{body}</TABLE>')
        gwangyang = ["광양 2고로 2차개수", "2025-03-04", "2027-05-31", "-", "21,000", "-", "2,553", "-", "18,447"]
        hyrex = ["포항 HyREX Demo Plant ESF 전기로 본체 내화물 공사", "2026-09-01", "2028-06-30", "-", "10,800", "-", "4", "-", "10,796"]
        dated = ('<TITLE ATOC="Y">4. 작성기준일 이후 발생한 주요사항 등 기타사항</TITLE><P>가. 작성기준일 이후 발생한 주요사항</P>'
                 '<P>(3) 미국 현지시간 2026년 11월 12일 종속회사인 OCI Alabama LLC가 매각됨에 따라, 연결대상 종속회사에서 제외되었습니다.</P>'
                 '<P>나. 합병 등의 사후정보</P><P>당사는 2024년 3월 흡수합병을 완료하였으며 합병 전후 재무사항은 다음과 같이 비교하여 기재하였습니다.</P>')
        h1 = H1.replace('<TITLE ATOC="Y">4. 작성기준일 이후 발생한 주요사항</TITLE><P>해당사항 없음</P>', "") + guar([marubeni]) + deal([fund]) + order([gwangyang])
        q3 = Q3.replace('<TITLE ATOC="Y">4. 작성기준일 이후 발생한 주요사항</TITLE><P>해당사항 없음</P>', "") + guar([marubeni, rwe]) + deal([fund, koruz]) + order([gwangyang, hyrex]) + dated
        s = n.sections(q3)
        self.assertEqual(s["dated"], ["(3) 미국 현지시간 2026년 11월 12일 종속회사인 OCI Alabama LLC가 매각됨에 따라, 연결대상 종속회사에서 제외되었습니다."])   # '나.' 앞까지
        self.assertTrue(any("〔회사명〕Hanwha Q CELLS America Inc./RWE Solar Development, LLC | 〔관 계〕종속기업 | 〔금액〕USD 157,200 | 〔이사회승인〕2026.07.21" in x
                            for x in s["guarantee"]))
        self.assertTrue(any("〔거래유형〕처분" in x and "〔관련 손익 (주1)〕18,480,232" in x for x in s["deal"]))
        self.assertTrue(s["order"][0].startswith("〔출입처 외 포스코퓨처엠〕 〔품목〕포항 HyREX Demo Plant ESF 전기로 본체 내화물 공사 | 〔수주일자〕2026-09-01 | 〔납기〕2028-06-30 | 〔수주총액·수량〕- | 〔수주총액·금액〕10,800"))   # 두 줄 머리(COLSPAN), 표 앞 '■ 포스코퓨처엠'은 출입처 외
        # 자회사 차입 지급보증('다. 채무보증 현황')은 보지 않고(이행보증·자금보충만), 그 뒤 제재 표를 앞 표 안 '지급보증' 낱말로 잘못 고르지 않는다
        self.assertEqual(n.sections(Q3)["guarantee"], [])
        self.assertEqual(len(n.sections(Q3)["sanction"]), 2)
        # 문단과 표 사이에 '[기준일 : …] (단위 : …)' 짧은 표가 끼어도 앞 글로 고른다(한화솔루션 실제 꼴)
        unit = "<TABLE><TR><TD>[기준일 : 2026. 09. 30]</TD><TD>(단위 : 백만원, 천미불)</TD></TR></TABLE>"
        g = n.sections(guar([rwe]).replace("<TABLE><TR><TH>구분", unit + "<TABLE><TR><TH>구분"))["guarantee"]
        self.assertEqual(len(g), 1)
        # 받은 보증·PF 신용보강·주석 전치표(같은 칸 이름이 한 줄에 셋 이상)는 뺀다
        recv = '<P>제공받은 지급보증 현황</P><TABLE><TR><TH>제공자</TH><TH>보증금액</TH><TH>보증내용</TH></TR><TR><TD>서울보증보험</TD><TD>6,991,487</TD><TD>계약이행보증 등</TD></TR></TABLE>'
        wide = ('<P>특수관계자 지급보증</P><TABLE><TR><TH></TH><TH COLSPAN="3">지급보증의 구분</TH></TR><TR><TH></TH><TH>제공한 이행보증 1</TH><TH>제공한 이행보증 2</TH><TH>제공한 이행보증 3</TH></TR>'
                '<TR><TD>피보증인</TD><TD>REC Silicon Inc</TD><TD>Hanwha Futureproof Corp</TD><TD>Garnet Solar Power Generation Station 1, LLC</TD></TR></TABLE>')
        self.assertIsNone(n.sections(recv).get("guarantee"))
        # 주석 표 제목 칸만 있는 줄은 뺀다(11-17 운영: OCI홀딩스 '제공한 지급보증에 대한 공시의 기술')
        title = ('<P>특수관계자 보증 및 담보제공</P><TABLE><TR><TD>특수관계자 보증 및 담보제공에 대한 공시의 기술</TD></TR>'
                 '<TR><TD>(주1) 당사는 OCI TerraSus Sdn. Bhd.가 현지의 전기공급회사와 체결한 전기공급계약에 대해서, 계약이행보증을 하고 있습니다.</TD></TR></TABLE>')
        self.assertEqual(n.sections(title)["guarantee"], ["(주1) 당사는 OCI TerraSus Sdn. Bhd.가 현지의 전기공급회사와 체결한 전기공급계약에 대해서, 계약이행보증을 하고 있습니다."])
        # 표 앞 글에 자금보충이 있어도 특수관계자 거래 표 전체를 보증으로 받지 않는다(그 낱말이 든 줄만)
        trade = ('<P>당사는 공동기업 차입금에 대해 자금보충 약정을 제공하고 있습니다.</P><TABLE><TR><TH>회사명</TH><TH>관계</TH><TH>거래종류</TH><TH>거래금액</TH></TR>'
                 '<TR><TD>오씨아이드림(주)</TD><TD>종속기업</TD><TD>용역매출, 임대수익 등</TD><TD>3,798,769</TD></TR></TABLE>')
        self.assertEqual(n.sections(trade)["guarantee"], [])
        # 표 앞 글에 자금보충이 있어도 자회사 차입 지급보증 표는 표 전체로 받지 않는다(탐침 3: LS 하나은행 지급보증 줄)
        loan = ('<P>엘에스엠트론㈜는 공동기업 차입금에 대해 자금보충약정을 체결하였습니다.</P><TABLE><TR><TH>구분</TH><TH>회사명</TH><TH>차입은행</TH><TH>지급보증액</TH><TH>보증기간</TH></TR>'
                '<TR><TD>종속기업</TD><TD>PT.LSAG Cable Indonesia</TD><TD>하나은행</TD><TD>USD 5</TD><TD>2026-07-07 ~ 2027-07-07</TD></TR>'
                '<TR><TD>공동기업</TD><TD>에이치앤엘어드밴스드(주)</TD><TD>한국산업은행 외</TD><TD>USD 76,068</TD><TD>자금보충약정 2026-09-10 ~ 2029-03-20</TD></TR></TABLE>')
        got = n.sections(loan)["guarantee"]
        self.assertEqual(len(got), 1)
        self.assertIn("자금보충약정", got[0])
        # '거래목적'만 있는 파생상품 거래 표는 이해관계자 거래가 아니다
        deriv = ('<TABLE><TR><TH>거래목적</TH><TH>상품종류</TH><TH>계약물량(USD)</TH><TH>계약내용</TH><TH>거래처</TH><TH>계약일자</TH><TH>손익</TH></TR>'
                 '<TR><TD>매매목적</TD><TD>Gold</TD><TD>1,608</TD><TD>Sell</TD><TD>하나증권</TD><TD>2026-08-31</TD><TD>388,336</TD></TR></TABLE>')
        self.assertNotIn("deal", n.sections(deriv))
        self.assertEqual(n.sections(wide)["guarantee"], [])
        doc = self.run_once(docs={"20261113000111": q3, "20260814000222": h1})
        new = doc["companies"]["두산에너빌리티"]["new"]
        self.assertEqual([len(new[k]) for k in ("dated", "guarantee", "deal", "order")], [1, 1, 1, 1])   # 앞 보고서에 있던 줄은 빠진다
        self.assertIn("RWE Solar Development", new["guarantee"][0])
        self.assertIn("UZ-KOR로부터 수취한 대여금 원금 재분배", new["deal"][0])
        self.assertIn("HyREX", new["order"][0])
        kinds = {e["kind"] for e in doc["events"]}
        self.assertTrue({"작성기준일 이후 주요사항", "이행보증·자금보충", "이해관계자 거래(출자·처분)", "수주"} <= kinds)
        # 앞 보고서에 그 표가 없으면 비교하지 않는다(작성기준일 이후 주요사항은 보고기간 후 사건처럼 늘 비교)
        bare = self.run_once(docs={"20261113000111": q3, "20260814000222": H1.replace('<TITLE ATOC="Y">4. 작성기준일 이후 발생한 주요사항</TITLE><P>해당사항 없음</P>', "")})
        c = bare["companies"]["두산에너빌리티"]
        self.assertEqual((sorted(c["nobase"]), len(c["new"]["dated"])), (["deal", "order"], 1))
        self.assertEqual(len(c["new"]["guarantee"]), 2)                       # 보증 대목은 앞 보고서(채무보증 현황 표)에 있어 비교한다 — 앞 보고서에 없던 이행보증 표 두 줄은 새 줄

    def test_rowspan_cells_are_filled_in_every_row_so_keys_do_not_depend_on_where_a_merge_starts(self):
        table = ('<TITLE ATOC="Y">2. 우발부채 등에 관한 사항</TITLE><P>가. 중요한 소송사건</P><TABLE>'
                 '<TR><TD COLSPAN="2">소송 당사자</TD><TD COLSPAN="2">최종소송가액</TD><TD ROWSPAN="2">소송내용</TD><TD ROWSPAN="2">진행경과</TD><TD ROWSPAN="2">비고</TD></TR>'
                 '<TR><TD>원고</TD><TD>피고</TD><TD>외화</TD><TD>원화</TD></TR>'
                 '<TR><TD ROWSPAN="2">포스코이앤씨</TD><TD>(주)다원시스</TD><TD></TD><TD>485,856</TD><TD>신안산선 7공구 다원시스 회생채권조사확정재판 신청</TD><TD>1심 중</TD><TD>소 제기일: 26. 08. 21</TD></TR>'
                 '<TR><TD>엔지니어링공제조합</TD><TD></TD><TD>19,222</TD><TD>신안산선 7공구 다원시스 계약이행보증금 청구소송</TD><TD>1심 중</TD><TD>소 제기일: 26. 07. 07</TD></TR>'
                 '<TR><TD>Campelo Costa</TD><TD>포스코홀딩스</TD><TD></TD><TD>1,680</TD><TD>브라질법인 중재 집행 소송</TD><TD>1심중</TD><TD>소 제기일 : \'25. 9. 25.</TD></TR>'
                 '</TABLE><P>나. 견질 또는 담보용 어음ㆍ수표 현황</P>')
        suit = n.sections(table)["suit"]
        self.assertEqual(suit[0], "〔소송 당사자·원고〕포스코이앤씨 | 〔소송 당사자·피고〕(주)다원시스 | 〔최종소송가액·원화〕485,856 | 〔소송내용〕신안산선 7공구 다원시스 회생채권조사확정재판 신청 | 〔진행경과〕1심 중 | 〔비고〕소 제기일: 26. 08. 21")
        self.assertEqual(suit[1], "〔소송 당사자·원고〕포스코이앤씨 | 〔소송 당사자·피고〕엔지니어링공제조합 | 〔최종소송가액·원화〕19,222 | 〔소송내용〕신안산선 7공구 다원시스 계약이행보증금 청구소송 | 〔진행경과〕1심 중 | 〔비고〕소 제기일: 26. 07. 07")
        # 칸 이름은 열쇠에서 빠진다. 합쳐 내려온 칸 값은 열쇠에 든다 — 줄이 끼어들어 합친 칸의 첫 줄이 바뀌어도 같은 줄이 같은 열쇠
        self.assertEqual(n.key_of(suit[1]), n.key_of("포스코이앤씨 | 엔지니어링공제조합 | 19,222 | 신안산선 7공구 다원시스 계약이행보증금 청구소송 | 1심 중 | 소 제기일: 26. 07. 07"))
        moved = table.replace('<TR><TD ROWSPAN="2">포스코이앤씨</TD><TD>(주)다원시스</TD>', '<TR><TD ROWSPAN="3">포스코이앤씨</TD><TD>(주)새피고</TD><TD></TD><TD>1</TD><TD>새 소송</TD><TD>1심 중</TD><TD>-</TD></TR><TR><TD>(주)다원시스</TD>')
        self.assertTrue(set(n.keys_of(suit)) <= set(n.keys_of(n.sections(moved)["suit"])))
        self.assertEqual(n.latest_date(suit[0]), (2026, 8))
        self.assertEqual(n.latest_date("소 제기일 : '25. 9. 25. | 소가 12.5억원"), (2025, 9))
        self.assertEqual(n.latest_date("2026년 7월 30일 소 취하"), (2026, 7))
        self.assertIsNone(n.latest_date("청구금액 7,974억원 · 지분율 26.5%"))
        # 이번 기간 날짜만 '새 날짜'로 — 계약 종료일·만기 같은 앞날 날짜는 세지 않는다
        self.assertFalse(n.in_period("〔계약시작일〕2025년 07월 | 〔계약종료일〕2030년 02월", (2026, 6), (2026, 11)))
        self.assertTrue(n.in_period("〔계약시작일〕2026년 08월 | 〔계약종료일〕2031년 12월", (2026, 6), (2026, 11)))

    def test_same_text_rows_are_counted_and_amounts_summed(self):
        # 11-17: 롯데케미칼 Kor-UZ 감자 5건이 숫자만 달라 화면에 1줄로만 보였다
        head = ("<TR><TH>거래 상대방</TH><TH>거래유형</TH><TH>거래일자</TH><TH>거래 대상물</TH><TH>거래 목적</TH><TH>금 액</TH>"
                "<TH>금액 산정 기준</TH><TH>관련 손익 (주1)</TH></TR>")
        rows = [("2026-07-15", "56,538,631", "18,480,232"), ("2026-07-27", "37,692,421", "11,452,090"), ("2026-08-03", "42,431,526", "11,658,202"),
                ("2026-08-04", "36,369,880", "9,873,086"), ("2026-08-05", "16,531,763", "4,462,777")]
        body = "".join(f"<TR><TD>Kor-UZ Gas Chemical Investment Ltd.</TD><TD>처분</TD><TD>{d}</TD><TD>Kor-UZ 보통주</TD>"
                       f"<TD>UZ-KOR로부터 수취한 대여금 원금 재분배</TD><TD>{a}</TD><TD>감자금액 산정</TD><TD>{b}</TD></TR>" for d, a, b in rows)
        got = n.sections(f"<TABLE>{head}{body}</TABLE>")["deal"]
        self.assertEqual(len(got), 1)
        self.assertTrue(got[0].endswith("〔같은 글자 줄 5건 · 금액 합계 189,564,221〕"))
        self.assertEqual(n.key_of(got[0]), n.key_of(got[0].rsplit(" 〔같은 글자", 1)[0]))   # 꼬리는 열쇠에서 빠진다

    def test_non_beat_affiliate_order_lines_are_marked_and_go_last(self):
        # 11-17: 포스코홀딩스 수주 새 줄 50줄 대부분이 포스코이앤씨(출입처 외) 건설 계약이었다
        def order(who, rows):
            body = "".join(f"<TR><TD>{a}</TD><TD>{b}</TD><TD>{c}</TD><TD>{d}</TD></TR>" for a, b, c, d in rows)
            return (f"<P>■ {who} (단위: 백만원)</P><TABLE><TR><TH>품목</TH><TH>수주일자</TH><TH>납기</TH><TH>수주총액</TH></TR>{body}</TABLE>")
        base = order("포스코", [("광양 3고로 개수 공사 설비", "2025-03-04", "2027-05-31", "21,000")]) + order("포스코이앤씨", [("서울 업무시설 신축공사 본공사", "2025-07-01", "2030-02-28", "300,000")])
        cur = order("포스코", [("광양 3고로 개수 공사 설비", "2025-03-04", "2027-05-31", "21,000"), ("포항 전기로 본체 내화물 공사", "2026-09-01", "2028-06-30", "10,800")]) \
            + order("포스코이앤씨", [("서울 업무시설 신축공사 본공사", "2025-07-01", "2030-02-28", "300,000"), ("동탄 주상복합 신축공사 본공사", "2026-08-01", "2031-12-31", "694,250")])
        s = n.sections(cur)["order"]
        self.assertTrue(any(x.startswith("〔출입처 외 포스코이앤씨〕 〔품목〕동탄") for x in s))
        new = self.run_once(docs={"20261113000111": Q3 + cur, "20260814000222": H1 + base})["companies"]["두산에너빌리티"]["new"]["order"]
        self.assertEqual(len(new), 2)
        self.assertIn("전기로 본체 내화물", new[0])                               # 출입처 줄이 먼저
        self.assertTrue(new[1].startswith("〔출입처 외 포스코이앤씨〕"))            # 계열사 줄은 뒤로

    def test_lines_dated_in_this_period_come_first(self):
        def doc(rows):
            body = "".join("<TR>" + "".join(f"<TD>{c}</TD>" for c in r) + "</TR>" for r in rows)
            return ('<TITLE ATOC="Y">2. 우발부채 등에 관한 사항</TITLE><P>가. 중요한 소송사건</P><TABLE><TR><TH>원고</TH><TH>피고</TH><TH>소송내용</TH><TH>비고</TH></TR>'
                    f'{body}</TABLE><P>나. 견질 또는 담보용 어음ㆍ수표 현황</P><TITLE ATOC="Y">3. 제재 등과 관련된 사항</TITLE><P>해당사항 없음</P>')
        old = [f"{k}건설" for k in "가나다라마바사아자차"]
        base = doc([["기존 원고", "당사", "공사대금 청구", "소 제기일 2024.05.01"]])
        rows = [[o, "당사", "서식만 바뀐 옛 소송", "소 제기일 2025.03.01"] for o in old] + [["포스코이앤씨", "(주)다원시스", "회생채권조사확정재판", "소 제기일: 26. 08. 21"]]
        got = self.run_once(docs={"20261113000111": doc(rows), "20260814000222": base})["companies"]["두산에너빌리티"]["new"]["suit"]
        self.assertIn("다원시스", got[0])                                      # 이번 기간 날짜 줄이 맨 앞(8줄 자르기에 묻히지 않는다)
        self.assertEqual(got[-1], "… 그 밖 3줄")

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

    def test_a_document_file_that_is_not_ready_yet_waits_for_the_next_run(self):
        # 11-16 마감일 저녁: 접수 직후 OpenDART가 원문 대신 014(파일이 존재하지 않습니다)를 돌려줬다 — 실패가 아니라 대기
        not_ready = b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><result><status>014</status><message>x</message></result>'
        doc = self.run_once(docs={"20261113000111": not_ready, "20260814000222": H1})
        self.assertEqual((doc["checks"][0]["status"], doc["events"]), ("waiting", []))
        self.assertIn("014", doc["checks"][0]["error"])
        self.assertEqual((doc["summary"]["waiting"], doc["summary"]["failed"]), (1, 0))
        again = self.run_once(previous=doc)                                   # 다음 실행에서 파일이 올라오면 그대로 읽는다
        self.assertEqual(again["companies"]["두산에너빌리티"]["status"], "ok")
        self.assertTrue(again["events"])


if __name__ == "__main__":
    unittest.main()
