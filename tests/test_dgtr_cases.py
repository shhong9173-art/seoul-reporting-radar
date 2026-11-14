"""인도 DGTR 사건 페이지 일정표: 파서(탐침 231에서 본 꼴), 새 조사·절차 공지 가르기, 다시 읽기, 실패, 이해관계자 명단."""
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import dgtr_cases as d  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 11, 14, 7, 40, tzinfo=KST)
PHENOL = "https://www.dgtr.gov.in/en/anti-dumping-cases/anti-dumping-investigation-concerning-imports-phenol-saudi-arabia-singapore"
NEWCASE = "https://www.dgtr.gov.in/en/anti-dumping-cases/anti-dumping-investigation-concerning-imports-new-product"
LIST = "https://www.dgtr.gov.in/en/anti-dumping-investigation-in-india"


def row(n, title, date, pdf="x.pdf"):
    return (f'<tr> <td>{n}</td> <td id="87{n}">{title}</td> <td><a href="https://dgtr.gov.in/sites/default/files/2026-03/{pdf}" target="_blank">'
            f'<img src="/themes/custom/dgtr/images/pdf.png"> Download (2.87 MB)</a></td> <td>{date}</td> </tr>')


def page(rows):
    return ('<label for="edit-caseno">File No.</label><table summary="Main Grid"><thead><tr><th scope="col">S.no</th>'
            '<th scope="col">Timeline for completion of investigation</th><th scope="col">Details</th><th scope="col">Publish Date</th></tr></thead><tbody>'
            + "".join(rows) + "</tbody></table>")


# 탐침 231: 페놀 사건 페이지 일정표 그대로(제목·날짜)
PHENOL_PAGE = page([row(1, "Initiation Notification", "19/03/2026", "Initiation%20%20Phenol%20english001.pdf"), row(2, "PUC/PCN methodology", "17/04/2026"),
                    row(3, "First Extension for filing Questionnaire responses", "24/04/2026"), row(4, "Second Extension for filing Questionnaire responses", "11/05/2026"),
                    row(5, "Interested parties list", "09/07/2026", "parties1.pdf"), row(6, "Updated Interested parties list", "23/07/2026", "parties2.pdf"),
                    row(7, "Updation of E-mail ID", "13/11/2026")])
NEW_PAGE = page([row(1, "Initiation Notification", "02/11/2026")])


class Resp:
    def __init__(self, text="", status=200, content=b""):
        self.text, self.status_code, self.content = text, status, content


class Site:
    def __init__(self, pages, down=()):
        self.pages, self.down, self.calls = pages, set(down), []

    def get(self, url, headers=None, timeout=None):
        self.calls.append(url)
        if url in self.down:
            return Resp(status=503)
        if url.endswith(".pdf"):
            return Resp(content=b"%PDF")
        return Resp(self.pages.get(url, "<html>none</html>"))


def ev(eid, url, page="in-dgtr", detected="2026-11-14T01:51:00+09:00"):
    return {"id": eid, "pageId": page, "label": "인도 DGTR 반덤핑 조사", "text": "x", "url": url, "country": "인도", "detectedAt": detected}


class Parse(unittest.TestCase):
    def test_timeline_rows_and_kinds(self):
        rows = d.parse_case(PHENOL_PAGE)
        self.assertEqual(len(rows), 7)
        self.assertEqual(rows[0], {"title": "Initiation Notification", "date": "2026-03-19", "url": "https://dgtr.gov.in/sites/default/files/2026-03/Initiation%20%20Phenol%20english001.pdf"})
        s = d.summarize(rows, NOW.date())
        self.assertEqual((s["initiated"], s["latest"], s["steps"], s["kind"]),
                         ("2026-03-19", {"title": "Updation of E-mail ID", "date": "2026-11-13"}, 7, "procedural"))
        self.assertTrue(s["partiesUrl"].endswith("parties2.pdf"))                                   # 가장 최근 명단
        self.assertEqual(d.summarize(d.parse_case(NEW_PAGE), NOW.date())["kind"], "new")            # 개시 30일 안
        final = d.parse_case(page([row(1, "Initiation Notification", "19/03/2026"), row(2, "Final Findings", "10/11/2026")]))
        self.assertEqual(d.summarize(final, NOW.date())["kind"], "progress")
        corr = d.parse_case(page([row(1, "Initiation Notification", "19/03/2026"), row(2, "Corrigendum to Final Findings", "10/11/2026")]))
        self.assertEqual(d.summarize(corr, NOW.date())["kind"], "progress")                         # 절차 낱말이 있어도 판정 문서면 진행 문서
        noinit = d.parse_case(page([row(1, "Extension of time", "10/11/2026")]))
        self.assertEqual((d.summarize(noinit, NOW.date())["initiated"], d.summarize(noinit, NOW.date())["kind"]), (None, "progress"))   # 개시일을 모르면 절차 공지라 단정하지 않는다
        self.assertIsNone(d.summarize(d.parse_case("<html>점검 중</html>"), NOW.date()))
        self.assertIsNone(d.iso("31/02/2026"))

    def test_korea_lines_keep_the_original_text(self):
        text = "S.No Name of the interested party\n1 M/s ABC Chemicals Ltd., Korea RP Producer/Exporter\n2 M/s XYZ Pte Ltd Singapore\n3 M/s Long Name Petrochemical\nKorea RP\nEmbassy of the Republic of Korea"
        self.assertEqual(d.korea_lines(text), ["1 M/s ABC Chemicals Ltd., Korea RP Producer/Exporter", "3 M/s Long Name Petrochemical Korea RP", "Embassy of the Republic of Korea"])
        self.assertEqual(d.korea_lines("no match here"), [])


class Attach(unittest.TestCase):
    def setUp(self):
        self._orig = d.read_parties
        self.pdf_calls = []

        def fake(url, *, get):
            self.pdf_calls.append(url)
            return {"pages": 3, "chars": 900, "koreaLines": ["1 M/s ABC Chemicals Ltd., Korea RP Producer/Exporter"], "beat": []}
        d.read_parties = fake

    def tearDown(self):
        d.read_parties = self._orig

    def test_reads_case_pages_once_and_again_only_when_relisted(self):
        events = [ev("a", PHENOL), ev("b", PHENOL), ev("c", LIST), ev("n", NEWCASE, detected="2026-11-13T07:40:00+09:00"),
                  ev("k", PHENOL.replace("phenol", "other"), page="ca-cbsa"), ev("old", PHENOL.replace("phenol", "old"), detected="2026-08-01T07:40:00+09:00")]
        site = Site({PHENOL: PHENOL_PAGE, NEWCASE: NEW_PAGE})
        doc = {"events": events}
        n = d.attach(doc, None, NOW, get=site.get, sleep=lambda s: None)
        self.assertEqual(site.calls, [PHENOL, NEWCASE])                                             # 목록 주소·다른 나라·45일 넘은 줄은 열지 않는다
        self.assertEqual((n["cases"], n["read"], n["failed"], n["kinds"], n["pdfs"], n["korea"]), (2, 2, 0, {"procedural": 1, "new": 1}, 1, 1))
        c = doc["dgtrCases"][PHENOL]
        self.assertEqual((c["status"], c["initiated"], c["latest"]["title"], c["kind"]), ("ok", "2026-03-19", "Updation of E-mail ID", "procedural"))
        self.assertEqual((c["parties"]["status"], c["parties"]["koreaLines"], c["parties"]["date"]), ("ok", ["1 M/s ABC Chemicals Ltd., Korea RP Producer/Exporter"], "2026-07-23"))
        self.assertNotIn("parties", doc["dgtrCases"][NEWCASE])                                      # 명단이 아직 없는 새 조사
        # 다음 실행: 달라진 게 없으면 다시 열지 않는다
        site2 = Site({PHENOL: PHENOL_PAGE, NEWCASE: NEW_PAGE})
        doc2 = {"events": events}
        n2 = d.attach(doc2, doc, NOW + dt.timedelta(days=1), get=site2.get, sleep=lambda s: None)
        self.assertEqual((site2.calls, n2["read"], n2["pdfs"], len(self.pdf_calls)), ([], 0, 0, 1))
        self.assertEqual(doc2["dgtrCases"][PHENOL]["parties"]["status"], "ok")
        # 같은 사건이 목록에 다시 뜨면(새 문서가 붙음) 다시 읽는다 — 명단 주소가 같으면 PDF는 다시 안 받는다
        relisted = events + [ev("a2", PHENOL, detected="2026-11-20T07:40:00+09:00")]
        site3 = Site({PHENOL: PHENOL_PAGE.replace("</tbody>", row(8, "Disclosure Statement", "19/11/2026") + "</tbody>"), NEWCASE: NEW_PAGE})
        doc3 = {"events": relisted}
        d.attach(doc3, doc2, NOW + dt.timedelta(days=6), get=site3.get, sleep=lambda s: None)
        self.assertEqual((site3.calls, doc3["dgtrCases"][PHENOL]["kind"], doc3["dgtrCases"][PHENOL]["latest"]["date"], len(self.pdf_calls)), ([PHENOL], "progress", "2026-11-19", 1))

    def test_failure_is_unconfirmed_and_retried(self):
        events = [ev("a", PHENOL)]
        doc = {"events": events}
        n = d.attach(doc, None, NOW, get=Site({}, down=[PHENOL]).get, sleep=lambda s: None)
        self.assertEqual((n["failed"], n["kinds"], doc["dgtrCases"][PHENOL]["status"], doc["dgtrCases"][PHENOL]["error"]), (1, {"미확인": 1}, "failed", "HTTP 503"))
        doc2 = {"events": events}
        d.attach(doc2, doc, NOW + dt.timedelta(days=1), get=Site({PHENOL: PHENOL_PAGE}).get, sleep=lambda s: None)
        self.assertEqual(doc2["dgtrCases"][PHENOL]["status"], "ok")
        # 읽었던 사건이 다시 떴는데 이번엔 못 읽으면 직전 값은 남기고 실패 표시
        relisted = events + [ev("a2", PHENOL, detected="2026-11-20T07:40:00+09:00")]
        doc3 = {"events": relisted}
        d.attach(doc3, doc2, NOW + dt.timedelta(days=6), get=Site({}, down=[PHENOL]).get, sleep=lambda s: None)
        self.assertEqual((doc3["dgtrCases"][PHENOL]["status"], doc3["dgtrCases"][PHENOL]["initiated"]), ("failed", "2026-03-19"))
        # 형식이 바뀌어 표가 안 보이면 실패(0줄을 '문서 없음'으로 넘기지 않는다)
        doc4 = {"events": events}
        d.attach(doc4, None, NOW, get=Site({PHENOL: "<html>maintenance</html>"}).get, sleep=lambda s: None)
        self.assertIn("형식 변경 의심", doc4["dgtrCases"][PHENOL]["error"])

    def test_page_budget_defers_the_rest(self):
        urls = [PHENOL.replace("phenol", f"p{i}") for i in range(8)]
        events = [ev(f"e{i}", u, detected=f"2026-11-{10 + i % 4:02d}T07:40:00+09:00") for i, u in enumerate(urls)]
        site = Site({u: NEW_PAGE for u in urls})
        doc = {"events": events}
        n = d.attach(doc, None, NOW, get=site.get, sleep=lambda s: None)
        self.assertEqual((n["read"], n["waiting"], len(site.calls)), (d.PAGE_BUDGET, 2, d.PAGE_BUDGET))
        doc2 = {"events": events}
        self.assertEqual(d.attach(doc2, doc, NOW + dt.timedelta(days=1), get=site.get, sleep=lambda s: None)["read"], 2)


if __name__ == "__main__":
    unittest.main()
