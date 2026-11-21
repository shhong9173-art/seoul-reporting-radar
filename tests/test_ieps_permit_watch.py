"""통합환경허가 정보공개(11-21 탐침 실제 제목·목록 꼴): 제목 나누기, 출입처 이름 규칙, 변경허가 B·통합허가 C·연간보고서 버림,
첫 실행 기준선, 결과서 앞쪽 이력·변경 줄, 조회 실패는 0이 아니라 미확인."""
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ieps_permit_watch as w  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 11, 23, 17, 20, tzinfo=KST)


class R:
    def __init__(self, status=200, text="", content=b""):
        self.status_code, self.text, self.content = status, text, content


def row(seq, title, date):
    return (f'<tr><td>{seq}</td><td><a href="/web/board/7/{seq}/?pMENUMST_ID=176&amp;searchType=ALL&amp;searchWord=">{title}</a></td>'
            f'<td></td><td>과학원</td><td>{date}</td><td>10</td></tr>')


PAGE1 = ("<table><tr><th>#</th><th>제목</th><th>첨부</th><th>작성자</th><th>등록일</th><th>조회수</th></tr>"
         + row(3643, "[통합허가, 발전](주)보광에너지 정보공개(제0891-01호)", "2026-10-26")
         + row(3640, "[통합허가, 무기화학]금호석유화학(주) 율촌CNT공장 정보공개(제0733-01호)", "2026-10-26")
         + row(3498, "[변경허가, 철강]현대제철(주)포항1공장 정보공개(제0526-02호)", "2025-09-08")
         + row(3486, "[연간보고서]현대제철(주)당진제철소_2023(2022년 기준)", "2025-09-08")
         + row(3446, "[통합허가, 철강]현대스틸파이프(주) 정보공개(제326-01호)", "2025-08-25")
         + "</table>")
VIEW = ("<div>환경오염시설의 통합관리에 관한 법률」 제27조제5항에 따라 다음 사항을 통합환경허가시스템에 공개합니다.</div>"
        '<a href="/jfile/readDownloadFile.do?fileId=1a175f2c9d793&amp;fileSeq=1&amp;useSecurity=&amp;uploadMode=db">526-02 배출시설등 설치·운영허가 검토결과서_현대제철(주)포항1공장(비공개).pdf</a>')
# 11-21 탐침: 결과서 앞 8쪽의 이력·변경 줄 꼴
PDF = ("2021.12.28. 통 합 허 가\n2023.4.25.\n2023.12.00. < 변경신고 > 김 지 혜\n1. 배출시설 및 방지시설 , 배출구 변경\n2. 신규 오염물질 추가\n"
       "1. 배출시설 및 방지시설 추가\n2. 폐수처리공정 변경\n「환경오염시설의 통합관리에 관한 법률」 제6조 배출시설 변경")


def site(pages, fail=()):
    calls = []

    def get(url, timeout=None, headers=None):
        calls.append(url)
        if any(f in url for f in fail):
            raise type("ReadTimeout", (Exception,), {})("x")
        if "/web/board/7?" in url:
            n = int(url.rsplit("page=", 1)[1])
            return R(text=pages.get(n, "<table></table>"))
        if "/web/board/7/" in url:
            return R(text=VIEW)
        if "readDownloadFile" in url:
            return R(content=b"%PDF-1.4 fake")
        return R(404)
    return get, calls


class Parse(unittest.TestCase):
    def test_titles(self):
        self.assertEqual(w.parse_title("[변경허가, 철강]현대제철(주)포항1공장 정보공개(제0526-02호)"),
                         {"kind": "변경허가", "industry": "철강", "site": "현대제철(주)포항1공장", "no": "제0526-02호"})
        self.assertEqual(w.parse_title("[통합허가, 무기화학]금호석유화학(주) 율촌CNT공장 정보공개(제0733-01호)")["site"], "금호석유화학(주) 율촌CNT공장")
        self.assertEqual(w.parse_title("[연간보고서]현대제철(주)당진제철소_2023(2022년 기준)")["kind"], "연간보고서")
        self.assertEqual(w.parse_title("(주)지에스이앤알 반원발전처 정보공개(1)"), None)
        self.assertEqual(len(w.list_rows(PAGE1)), 5)

    def test_beat_rules(self):
        self.assertEqual(w.beat_of("현대제철(주)포항1공장"), ("현대제철", False))
        self.assertEqual(w.beat_of("금호석유화학(주) 율촌CNT공장"), ("금호석유화학", False))
        self.assertEqual(w.beat_of("현대스틸파이프(주)"), (None, False))          # 계열사는 출입처 아님
        self.assertEqual(w.beat_of("포스코퓨처엠(주) 광양공장"), (None, False))
        self.assertEqual(w.beat_of("(주)포스코 광양제철소"), ("포스코", False))
        # 11-21 첫 운영 실행: '포스코강판(주) 도금공장'(별도 상장사)이 포스코로 잡혔다 — 회사 부분만 규칙에 맞춘다
        self.assertEqual(w.beat_of("포스코강판(주) 도금공장"), (None, False))
        self.assertEqual(w.company_token("OCI(주)군산공장"), "OCI")
        self.assertEqual(w.beat_of("OCI(주)군산공장"), ("OCI", False))
        self.assertEqual(w.beat_of("에쓰-오일(주) 온산공장"), ("S-OIL", False))
        self.assertEqual(w.beat_of("현대제철포항공장"), ("현대제철", False))
        self.assertEqual(w.beat_of("한국타이어앤테크놀로지(주) 대전공장"), ("한국타이어", False))
        self.assertEqual(w.beat_of("OCI(주) 군산공장")[0], "OCI")
        self.assertEqual(w.beat_of("효성중공업(주) 창원공장"), ("효성중공업", True))
        self.assertEqual(w.tier_of("변경허가", False), "B")
        self.assertEqual(w.tier_of("통합허가", False), "C")
        self.assertEqual(w.tier_of("변경허가", True), "C")

    def test_changes_from_review_document(self):
        hist, lines = w.changes_of(PDF)
        self.assertEqual(hist, [("2021-12-28", "통합허가"), ("2023-12", "변경신고")])
        self.assertEqual(lines, ["배출시설 및 방지시설 , 배출구 변경", "신규 오염물질 추가", "배출시설 및 방지시설 추가", "폐수처리공정 변경"])


class Run(unittest.TestCase):
    def test_first_run_is_baseline_then_new_change_permit_is_b_with_document_lines(self):
        get, calls = site({1: PAGE1})
        doc = w.run(NOW, None, get=get, sleep=lambda s: None)
        self.assertEqual((doc["status"], doc["events"]), ("ok", []))
        # 연간보고서·계열사·비출입처 빼고, 게시 1년 넘은 글(2025-09 현대제철 변경허가)은 보관하지 않는다
        self.assertEqual({x["company"] for x in doc["items"]}, {"금호석유화학"})
        self.assertTrue(all(x["baseline"] for x in doc["items"]))
        self.assertFalse(any("readDownloadFile" in u for u in calls))                          # 기준선은 결과서를 안 읽는다
        new = PAGE1.replace("<table><tr><th>", "<table>" + row(3700, "[변경허가, 석유정제]에쓰-오일(주) 온산공장 정보공개(제0400-02호)", "2026-11-23")
                            + row(3699, "[통합허가, 철강]동국제강(주) 인천공장 정보공개(제0410-01호)", "2026-11-23") + "<tr><th>")
        get2, calls2 = site({1: new})
        doc2 = w.run(NOW, doc, get=get2, sleep=lambda s: None, read_pdf=lambda raw: (PDF, 227))
        ev = {e["id"]: e for e in doc2["events"]}
        self.assertEqual(set(ev), {"ieps:3700", "ieps:3699"})
        self.assertEqual((ev["ieps:3700"]["tier"], ev["ieps:3700"]["company"]), ("B", "S-OIL"))
        self.assertEqual(ev["ieps:3699"]["tier"], "C")
        self.assertIn("허가 이력(검토 결과서): 2021-12-28 통합허가, 2023-12 변경신고", ev["ieps:3700"]["text"])
        self.assertIn("변경 항목(검토 결과서 앞쪽): 배출시설 및 방지시설 , 배출구 변경", ev["ieps:3700"]["text"])
        self.assertEqual(sum(1 for u in calls2 if "readDownloadFile" in u), 2)                   # 출입처 글이면 C도 결과서를 읽는다(실행당 2건)
        self.assertEqual(doc2["counts"]["pdf"], 2)
        self.assertIn("허가 이력(검토 결과서)", ev["ieps:3699"]["text"])
        doc3 = w.run(NOW + dt.timedelta(days=1), doc2, get=get2, sleep=lambda s: None)
        self.assertEqual(len(doc3["events"]), 2)                                                 # 본 글은 다시 안 올린다

    def test_stored_items_are_rechecked_against_name_rules(self):
        prev = {"schema": w.SCHEMA, "baselineAt": "2026-11-21T22:56:00+09:00", "seen": ["3601"], "events": [],
                "items": [{"id": "ieps:3601", "company": "포스코", "site": "포스코강판(주) 도금공장", "kind": "통합허가", "date": "2026-08-31", "tier": "C"},
                          {"id": "ieps:3640", "company": "금호석유화학", "site": "금호석유화학(주) 율촌CNT공장", "kind": "통합허가", "date": "2026-10-26", "tier": "C"}]}
        get, _ = site({1: PAGE1})
        doc = w.run(NOW, prev, get=get, sleep=lambda s: None, read_pdf=lambda raw: (PDF, 3))
        self.assertEqual({x["id"] for x in doc["items"]} - {"ieps:3640"}, set())

    def test_failures_are_unconfirmed(self):
        get, _ = site({1: PAGE1}, fail=("page=1",))
        doc = w.run(NOW, None, get=get, sleep=lambda s: None)
        self.assertEqual(doc["status"], "failed")
        self.assertIn("ReadTimeout", doc["checks"][0]["error"])
        get, _ = site({1: "<html>바뀐 화면</html>"})
        self.assertEqual(w.run(NOW, None, get=get, sleep=lambda s: None)["checks"][0]["error"], "목록 0줄(형식 변경 의심)")


if __name__ == "__main__":
    unittest.main()
