"""인도 DGTR 사건 페이지 일정표: 파서(탐침 231·232에서 본 꼴), 이번 절차 개시(재심·우회조사), 새 조사·절차 공지 가르기, 다시 읽기, 실패, 이해관계자 명단 표 묶기."""
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
# 탐침 232: 한 사건 페이지에 원조사·재심이 쌓인다(제목·날짜 그대로, 일부 줄 생략)
TDI_PAGE = page([row(1, "Initiation", "05/10/2016"), row(2, "Preliminary Findings", "28/03/2017"), row(3, "Final Findings", "14/12/2017"),
                 row(4, "Initiation Notification", "05/08/2020"), row(5, "List of registered interested parties", "10/08/2020", "old1.pdf"), row(6, "Final Findings", "29/10/2020"),
                 row(7, "Initiation Notification- SSR", "27/08/2021"), row(8, "List of Interested Parties", "27/10/2021", "old2.pdf"), row(9, "FINAL FINDING", "24/06/2022"),
                 row(10, "Initiation Notification-2nd SSR", "30/09/2026"), row(11, "Letter regarding clarification on PUC/PCNs and extension of time for Q", "12/11/2026")])
CHISEL_PAGE = page([row(1, "Initiation Notification", "04/10/2022"), row(2, "List of registered interested parties and sharing of non-confidential", "17/07/2023", "old.pdf"),
                    row(3, "Final Findings", "28/03/2024"), row(4, "Anti-Circumvention - Initiation Notification", "28/09/2026"), row(5, "List of registered interested parties", "12/11/2026", "ac.pdf")])
SILICA_PAGE = page([row(1, "Initiation Notification", "22/09/2020"), row(2, "Final Findings dated 20/9/2021", "20/09/2021"), row(3, "Initiation Notification SSR UFS", "20/03/2026"),
                    row(4, "Interested party list", "02/07/2026", "ufs.pdf"), row(5, "Final Findings", "06/11/2026")])
# 탐침 232: 명단 PDF에서 뽑은 글 — 표 칸이 줄마다 끊긴다(이름·번호는 원문 꼴, 이메일은 지어낸 것)
PARTIES_TEXT = """F. No. 6/11/2026 -DGTR
Case No. AD(OI) – 10/2026
Date: 9th July, 2026
Subject: Interested parties list in the case of anti-dumping investigation concerning
imports of Acetone from the Republic of Singapore, the Republic of Korea, Taiwan and
the Kingdom of Thailand.
1. With Reference to the above -mentioned investigation, it is informed that a list of the
interested parties who have requested to be registered
2. All interested parties are advised to forward the non-confidential version
concerning imports of “Acetone” from the Republic of Singapore, the Republic of
Korea, Taiwan and the Kingdom of Thailand., F. No. 06/11/2026-DGTR, Case No. AD(OI)
– 10/2026.
S.No
Name of the
Interested Party
Category
1. Deepak Phenolics Ltd Domestic
Industry
TPM a@example.in
2.
Kumho P and B
Chemicals Inc
Exporter/
Producer
3. Kempar Energy Pte Ltd Exporter WTC k@example.in
4. LG Chem Ltd
Exporter/
Producer b@example.com
5.
Lotte GS Chemical
Corporation
Exporter/
6.
Korea Chemical Industry
Association Association c@example.kr
7. Akin Chemicals Importer TLC d@example.in 8. Glued Row Trading Importer
e@example.in
9. Embassy of South Korea. Embassy
Self f@example.kr
• Interested parties are further directed to regularly visit the official website
Korea should not be read from this footer
"""
BEAT = [("LG화학", r"\bLG Chem"), ("롯데케미칼", r"\bLotte Chemical")]


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

    def test_current_proceeding_is_the_latest_initiation(self):
        # 탐침 232: 처음 구현은 TDI를 '개시 2016-10-05'로 적었다 — 이번 절차는 2차 일몰재심(2026-09-30)
        tdi = d.summarize(d.parse_case(TDI_PAGE), NOW.date())
        self.assertEqual((tdi["initiated"], tdi["initTitle"], tdi["firstInitiated"], tdi["kind"]), ("2026-09-30", "Initiation Notification-2nd SSR", "2016-10-05", "procedural"))
        self.assertNotIn("partiesUrl", tdi)                                                         # 지난 재심(2020·2021)의 명단은 읽지 않는다
        chisel = d.summarize(d.parse_case(CHISEL_PAGE), NOW.date())
        self.assertEqual((chisel["initiated"], chisel["firstInitiated"], chisel["kind"]), ("2026-09-28", "2022-10-04", "procedural"))
        self.assertTrue(chisel["partiesUrl"].endswith("ac.pdf"))                                    # 우회조사 개시 뒤 명단만
        silica = d.summarize(d.parse_case(SILICA_PAGE), NOW.date())
        self.assertEqual((silica["initiated"], silica["latest"]["title"], silica["kind"]), ("2026-03-20", "Final Findings", "progress"))
        self.assertNotIn("firstInitiated", d.summarize(d.parse_case(PHENOL_PAGE), NOW.date()))      # 재심이 없으면 첫 조사 날짜를 따로 두지 않는다
        # 새로 개시된 재심(오래된 사건 페이지): 개시 30일 안이면 new
        fresh = d.parse_case(page([row(1, "Initiation Notification", "22/09/2020"), row(2, "Final Findings", "20/09/2021"), row(3, "Initiation Notification - SSR", "03/11/2026")]))
        self.assertEqual((d.summarize(fresh, NOW.date())["kind"], d.summarize(fresh, NOW.date())["initiated"]), ("new", "2026-11-03"))
        # 개시 고시를 고친 문서는 개시가 아니다
        corr = d.parse_case(page([row(1, "Initiation Notification", "19/03/2026"), row(2, "Corrigendum to Initiation Notification", "10/11/2026")]))
        self.assertEqual((d.summarize(corr, NOW.date())["initiated"], d.summarize(corr, NOW.date())["kind"]), ("2026-03-19", "procedural"))

    def test_party_table_is_regrouped_by_number(self):
        entries, last_no = d.party_entries(PARTIES_TEXT)
        self.assertEqual(last_no, 9)
        self.assertEqual(entries, ["1. Deepak Phenolics Ltd Domestic Industry TPM", "2. Kumho P and B Chemicals Inc Exporter/ Producer", "3. Kempar Energy Pte Ltd Exporter WTC",
                                   "4. LG Chem Ltd Exporter/ Producer", "5. Lotte GS Chemical Corporation Exporter/", "6. Korea Chemical Industry Association Association",
                                   "7. Akin Chemicals Importer TLC", "8. Glued Row Trading Importer", "9. Embassy of South Korea. Embassy Self"])
        got = d.parties_from_text(PARTIES_TEXT, 3, BEAT)
        self.assertEqual((got["shape"], got["entries"], got["lastNo"], got["koreaTotal"], got["beat"]), ("table", 9, 9, 5, ["LG화학"]))     # 'Lotte GS Chemical'은 롯데케미칼이 아니다
        self.assertEqual(got["koreaLines"], ["4. LG Chem Ltd Exporter/ Producer", "2. Kumho P and B Chemicals Inc Exporter/ Producer", "5. Lotte GS Chemical Corporation Exporter/",
                                             "6. Korea Chemical Industry Association Association", "9. Embassy of South Korea. Embassy Self"])   # 출입처 줄 먼저, 사건 제목·꼬리말 줄은 없음
        self.assertNotIn("@", " ".join(got["koreaLines"]))
        # 번호 줄 몇 개가 안 잡혀도(3·4번이 점 없이 나옴) 뒤 번호에서 다시 묶는다 — 못 가른 줄 수는 lastNo와 entries 차이로 남는다
        broken = d.parties_from_text(PARTIES_TEXT.replace("3. Kempar", "3 Kempar").replace("4. LG Chem", "4 LG Chem"), 3, BEAT)
        self.assertEqual((broken["entries"], broken["lastNo"], broken["beat"]), (7, 9, ["LG화학"]))
        self.assertIn("9. Embassy of South Korea. Embassy Self", broken["koreaLines"])
        # 표 머리나 번호 줄이 없으면 줄 단위로(사건 제목 줄은 뺀다)
        loose = d.parties_from_text("Subject: imports of X from the Republic of Korea, Taiwan and\nthe Kingdom of Thailand.\nM/s ABC Chemicals, Korea RP\nEmbassy of the Republic of Korea", 1, BEAT)
        self.assertEqual((loose["shape"], loose["koreaLines"]), ("lines", ["M/s ABC Chemicals, Korea RP", "Embassy of the Republic of Korea"]))

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
            return {"v": d.PARTIES_VERSION, "pages": 3, "chars": 900, "shape": "table", "entries": 4, "koreaLines": ["1. ABC Chemicals Ltd Korea Exporter"], "koreaTotal": 1, "beat": []}
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
        self.assertEqual((c["parties"]["status"], c["parties"]["koreaLines"], c["parties"]["date"]), ("ok", ["1. ABC Chemicals Ltd Korea Exporter"], "2026-07-23"))
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

    def test_old_rule_records_are_read_again(self):
        # 읽는 규칙이 바뀌면(VERSION) 저장된 사건·명단을 다시 읽는다 — 처음 구현이 남긴 '개시 2016'·제목 줄 명단을 그대로 두지 않는다
        events = [ev("a", PHENOL)]
        old = {"dgtrCases": {PHENOL: {"status": "ok", "checkedAt": "2026-11-14T09:56:00+09:00", "initiated": "2026-03-19", "latest": {"title": "Updation of E-mail ID", "date": "2026-11-13"},
                                      "steps": 7, "kind": "procedural", "partiesUrl": "https://dgtr.gov.in/sites/default/files/2026-03/parties2.pdf", "partiesDate": "2026-07-23",
                                      "parties": {"url": "https://dgtr.gov.in/sites/default/files/2026-03/parties2.pdf", "date": "2026-07-23", "status": "ok", "koreaLines": ["imports of Phenol from South Korea"], "beat": ["LG화학"]}}}}
        site = Site({PHENOL: PHENOL_PAGE})
        doc = {"events": events}
        n = d.attach(doc, old, NOW + dt.timedelta(hours=3), get=site.get, sleep=lambda s: None)
        c = doc["dgtrCases"][PHENOL]
        self.assertEqual((site.calls, n["read"], n["pdfs"], c["v"], c["parties"]["v"], c["parties"]["koreaLines"]), ([PHENOL], 1, 1, d.VERSION, d.PARTIES_VERSION, ["1. ABC Chemicals Ltd Korea Exporter"]))

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
        urls = [PHENOL.replace("phenol", f"p{i}") for i in range(d.PAGE_BUDGET + 2)]
        events = [ev(f"e{i}", u, detected=f"2026-11-{10 + i % 4:02d}T07:40:00+09:00") for i, u in enumerate(urls)]
        site = Site({u: NEW_PAGE for u in urls})
        doc = {"events": events}
        n = d.attach(doc, None, NOW, get=site.get, sleep=lambda s: None)
        self.assertEqual((n["read"], n["waiting"], len(site.calls)), (d.PAGE_BUDGET, 2, d.PAGE_BUDGET))
        doc2 = {"events": events}
        self.assertEqual(d.attach(doc2, doc, NOW + dt.timedelta(days=1), get=site.get, sleep=lambda s: None)["read"], 2)


if __name__ == "__main__":
    unittest.main()
