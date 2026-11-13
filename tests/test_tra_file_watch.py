"""영국 TRA 공개기록 수집(scripts/tra_file_watch.py) — 11-13 탐침에서 본 실제 꼴로."""
import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import tra_file_watch as t  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 11, 13, 7, 40, tzinfo=KST)
H = '<span class="govuk-visually-hidden--mobile">{}</span>'


def td(label, value):
    return f'<td class="govuk-table__cell" style="width: 175px;"> {H.format(label)} {value} </td>'


def case_row(cid, case, commodity, country, initiated, updated=None, closed=None):
    last = td("Updated ", f"<span>{updated}</span> 12 Nov 2026") + td("Action ", f'<a href="{t.BASE}//case/{cid.lower()}/registration-of-interest">Register interest</a>') if updated else td("Closed ", closed)
    return ("<tr>" + td("No. ", f'<a href="{t.BASE}/case/{cid.lower()}">{cid}</a>') + td("Case ", case) + td("Commodity ", commodity) + td("Country ", country)
            + td("Type ", "Dumping Investigation") + td("Initiated ", f"<span>{initiated}</span> 04 Aug 2026") + last + "</tr>")


LIST = "<table>" + case_row("AD0092", "Suspension Polyvinyl Chloride from China, Mexico, and South Korea", "Suspension polyvinylchloride (S-PVC)", "China / Korea (the Republic of) / Mexico", "2026-08-04", "2026-11-12") \
    + case_row("AD0071", "Hot-rolled steel plate from South Korea", "Hot-rolled steel plate", "Korea (the Republic of)", "2025-06-06", "2026-08-12") \
    + case_row("NE0095", "Certain Excavators from China", "Excavators", "China", "2026-01-10", "2026-10-01") \
    + case_row("TD0034", "Steel Ropes and Cables", "Steel Ropes and Cables", "China / Morocco / Korea (the Republic of)", "2023-03-30", closed="28 Mar 2025") + "</table>"


def sub_row(cid, sid, title, party, ptype, published, files=1):
    return ("<tr>" + td("Submission: ", f'<a class="govuk-link" href = "{t.BASE}/case/{cid.lower()}/submission/{sid}">{title}</a>') + td("Party: ", party)
            + td("Type: ", ptype) + td("Published: ", published) + td("No. of files: ", str(files)) + "</tr>")


ROWS92 = [
    sub_row("AD0092", "s-0000012417-j7d0", "General", "LG Chem, Ltd.", "Exporter", "<span>2026-09-10</span> 10 Sep 2026", 8),
    sub_row("AD0092", "s-0000012360-j7s6", "Pre-Sampling Questionnaire", "LG Chem, Ltd.", "Exporter", "<span>2026-09-10</span> 10 Sep 2026"),
    sub_row("AD0092", "s-0000012235-r0t7", "Pre-Sampling Questionnaire", "Government of Korea, MOTIR(Ministry of Trade, Industry and Resources)", "Foreign government", "<span>2026-09-10</span> 10 Sep 2026"),
    sub_row("AD0092", "s-0000012374-j8y2", "Pre-Sampling Questionnaire", "Tianjin Bohua Chemical Development Co.,Ltd", "Exporter", "<span>2026-09-10</span> 10 Sep 2026"),
    sub_row("AD0092", "1172", "Questionnaire extensions", "Trade Remedies Authority", "TRA", "<span>2026-10-26</span> 26 Oct 2026"),
    sub_row("AD0092", "1239", "Supplementary submission (S/K PMS)", "Trade Remedies Authority", "TRA", "09 Nov 2026"),
    sub_row("AD0092", "1244", "Note to the public file &#8211; proposed representative third country", "Trade Remedies Authority", "TRA", "12 Nov 2026"),
]
CASE92 = "<h1>AD0092</h1><table><tr><th>Submission</th><th>Party</th></tr>" + "".join(ROWS92) + "</table>"
CASE71 = "<table>" + sub_row("AD0071", "s-0000001704-m2y9", "General", "STEMCOR DISTRIBUTION LIMITED", "Importer", "<span>2025-07-01</span> 01 Jul 2025") \
    + sub_row("AD0071", "s-0000001800-a1b2", "General", "POSCO", "Exporter", "<span>2025-07-03</span> 03 Jul 2025") + "</table>"
SUB1244 = f'<a href="{t.BASE}/case/ad0092">AD0092</a> <a href="https://afd-x.a02.azurefd.net/content/CD-01890_Note_third_country.pdf">CD-01890_Note_third_country.pdf</a> (120 KB)'
PDF_TEXT = ("NOTE TO THE PUBLIC FILE. " * 3 + "The TRA is considering whether a particular market situation exists in South Korea. "
            "If so, the normal value for LG Chem, Ltd. and Hanwha Solutions Corporation may be constructed using costs from a representative third country. "
            "The TRA proposes Mexico as the representative third country and invites comments by 22 November 2026. " + "Filler sentence about procedure and timetable for the case team. " * 6)


class Resp:
    def __init__(self, text="", status=200, content=b""):
        self.text, self.status_code, self.content, self.encoding = text, status, content, None


def getter(pages, log=None):
    def get(url, headers=None, timeout=None):
        if log is not None:
            log.append(url)
        v = pages.get(url)
        if v is None:
            return Resp("nf", 404)
        return Resp(content=v) if isinstance(v, bytes) else Resp(v)
    return get


class TraFile(unittest.TestCase):
    def setUp(self):
        self._pdf = t.pdf_text
        t.pdf_text = lambda data, limit=t.PDF_PAGES: (3, PDF_TEXT)

    def tearDown(self):
        t.pdf_text = self._pdf

    def pages(self, case92=CASE92):
        return {t.BASE + "/": LIST, t.BASE + "/case/ad0092": case92, t.BASE + "/case/ad0071": CASE71,
                t.BASE + "/case/ad0092/submission/1244": SUB1244, "https://afd-x.a02.azurefd.net/content/CD-01890_Note_third_country.pdf": b"%PDF-1.7 fake"}

    def test_parsers_read_the_real_shapes(self):
        cases = t.parse_cases(LIST)
        self.assertEqual([(c["id"], c["active"], c["initiated"], c["updated"]) for c in cases],
                         [("AD0092", True, "2026-08-04", "2026-11-12"), ("AD0071", True, "2025-06-06", "2026-08-12"), ("NE0095", True, "2026-01-10", "2026-10-01"), ("TD0034", False, "2023-03-30", "")])
        self.assertEqual(cases[0]["url"], t.BASE + "/case/ad0092")       # 'Register interest'의 겹슬래시 주소가 아니라 사건 주소
        rows = t.parse_case_page(CASE92, "AD0092")
        self.assertEqual(len(rows), 7)
        self.assertEqual((rows[0]["sid"], rows[0]["title"], rows[0]["party"], rows[0]["ptype"], rows[0]["published"], rows[0]["files"]),
                         ("s-0000012417-j7d0", "General", "LG Chem, Ltd.", "Exporter", "2026-09-10", 8))
        self.assertEqual((rows[5]["published"], rows[6]["published"]), ("2026-11-09", "2026-11-12"))   # '09 Nov 2026' 꼴
        self.assertEqual(rows[6]["title"], "Note to the public file – proposed representative third country")
        self.assertEqual(t.parse_submission(SUB1244), [{"name": "CD-01890_Note_third_country.pdf", "url": "https://afd-x.a02.azurefd.net/content/CD-01890_Note_third_country.pdf"}])

    def test_tiers_from_party_and_title(self):
        got = {r["sid"]: t.classify(r)[:2] for r in t.parse_case_page(CASE92, "AD0092")}
        self.assertEqual(got["s-0000012417-j7d0"], ("A", "출입처가 낸 문서"))                       # LG화학이 낸 일반 제출(즉시 종결 요청 등)
        self.assertEqual(got["s-0000012360-j7s6"], ("B", "출입처가 낸 절차 문서(질문서 답변·등록)"))
        self.assertEqual(got["s-0000012235-r0t7"], ("B", "한국 정부가 낸 절차 문서(질문서 답변·등록)"))
        self.assertEqual(got["s-0000012374-j8y2"], ("C", "다른 당사자 문서"))                        # 중국 수출자
        self.assertEqual(got["1172"], ("C", "조사기관의 일상 문서"))                                 # 기한 연장
        self.assertEqual(got["1239"], ("A", "조사기관의 판단·쟁점 문서"))                             # 11-10 기자 단독의 근거 문서
        self.assertEqual(got["1244"], ("A", "조사기관의 판단·쟁점 문서"))                             # 대표 제3국 메모
        self.assertEqual(t.classify({"party": "Korea Iron and Steel Association(KOSA)", "title": "General"})[:2], ("A", "한국 업계 단체가 낸 문서"))
        self.assertEqual(t.classify({"party": "Trade Remedies Authority", "title": "Final sampling notice"})[0], "B")   # '최종 표본'은 판정이 아니다

    def test_first_run_is_baseline_and_only_recent_docs_are_announced(self):
        log = []
        sec, events, check = t.collect(None, NOW, get=getter(self.pages(), log), sleep=lambda s: None)
        self.assertEqual(check["status"], "ok")
        self.assertEqual([c["id"] for c in sec["cases"]], ["AD0092", "AD0071"])               # 한국이 든 진행 조사만(종료·다른 나라 제외)
        self.assertEqual(sec["cases"][0]["beatParties"], ["LG화학"])
        self.assertTrue(sec["cases"][0]["govParty"])
        self.assertEqual(sec["cases"][1]["beatParties"], ["포스코"])
        self.assertEqual(len(sec["docs"]), 7)                                                  # 200일 넘은 문서(AD0071의 2025년 줄)는 화면에 안 남긴다 — 본 적은 기억한다
        self.assertEqual(len(sec["seen"]["AD0071"]), 2)
        # 최근 사흘(11-10 이후)에 올라온 것만 새 문서: 11-12 대표 제3국 메모 하나. 11-09 PMS 제출은 기준선
        self.assertEqual([e["id"] for e in events], ["trafile:AD0092:1244"])
        e = events[0]
        self.assertEqual((e["tier"], e["companies"], e["pageId"], e["country"]), ("A", ["한화솔루션", "LG화학"], "trafile", "영국"))
        self.assertIn("Trade Remedies Authority 제출 「Note to the public file – proposed representative third country」(게시 2026-11-12) · 파일 1개: CD-01890_Note_third_country.pdf", e["text"])
        self.assertIn("본문 대목 「The TRA is considering whether a particular market situation exists in South Korea.」 / 「If so, the normal value for LG Chem, Ltd. and Hanwha Solutions Corporation may be constructed", e["text"])
        self.assertEqual(sum(1 for u in log if "/submission/" in u), 1)                       # 기준선 문서의 제출 페이지는 열지 않는다
        self.assertEqual(check["pdfsRead"], 1)

    def test_next_run_announces_new_rows_and_upgrades_on_beat_mentions(self):
        sec, _, _ = t.collect(None, NOW, get=getter(self.pages()), sleep=lambda s: None)
        new_rows = sub_row("AD0092", "s-0000013000-z9z9", "General", "INOVYN ChlorVinyls Limited", "Applicant", "<span>2026-11-13</span> 13 Nov 2026") \
            + sub_row("AD0092", "s-0000013001-q1q1", "General", "Hanwha Solutions Corporation", "Exporter", "<span>2026-11-13</span> 13 Nov 2026") \
            + sub_row("AD0092", "s-0000013002-c3c3", "Questionnaire", "Wanhua Chemical (Fujian) Co., Ltd.", "Exporter", "<span>2026-11-13</span> 13 Nov 2026")
        pages = self.pages(CASE92.replace("</table>", new_rows + "</table>"))
        pages[t.BASE + "/case/ad0092/submission/s-0000013000-z9z9"] = '<a href="https://afd-x.a02.azurefd.net/content/INOVYN_comments.pdf">f</a>'
        pages["https://afd-x.a02.azurefd.net/content/INOVYN_comments.pdf"] = b"%PDF-1.7 fake"
        pages[t.BASE + "/case/ad0092/submission/s-0000013001-q1q1"] = '<a href="https://afd-x.a02.azurefd.net/content/HSC%20response.pdf">f</a>'
        pages["https://afd-x.a02.azurefd.net/content/HSC%20response.pdf"] = b"not a pdf"
        later = NOW + dt.timedelta(days=1)
        sec2, events, check = t.collect(sec, later, get=getter(pages), sleep=lambda s: None)
        by = {e["id"].rsplit(":", 1)[-1]: e for e in events}
        self.assertEqual(sorted(by), ["s-0000013000-z9z9", "s-0000013001-q1q1"])              # 중국 수출자 질문서(C)는 화면에만
        self.assertEqual((by["s-0000013000-z9z9"]["tier"], by["s-0000013000-z9z9"]["why"]), ("B", "다른 당사자 문서에 출입처 이름"))
        self.assertEqual((by["s-0000013001-q1q1"]["tier"], by["s-0000013001-q1q1"]["why"]), ("A", "출입처가 낸 문서"))
        self.assertIn("본문 못 읽음(HSC response.pdf: HTTP 200)", by["s-0000013001-q1q1"]["text"])   # PDF가 아니면 못 읽었다고 적는다
        self.assertEqual(check["newDocs"], 3)
        self.assertEqual(len(sec2["docs"]), 10)
        # 같은 문서를 다시 알리지 않는다
        _, again, _ = t.collect(sec2, later + dt.timedelta(days=1), get=getter(pages), sleep=lambda s: None)
        self.assertEqual(again, [])

    def test_list_failure_keeps_last_state_and_is_not_zero(self):
        sec, _, _ = t.collect(None, NOW, get=getter(self.pages()), sleep=lambda s: None)
        kept, events, check = t.collect(sec, NOW + dt.timedelta(days=1), get=getter({}), sleep=lambda s: None)
        self.assertEqual((check["status"], events), ("failed", []))
        self.assertTrue(kept["stale"])
        self.assertEqual(len(kept["docs"]), 7)
        # 사건 하나만 안 열리면 그 사건은 지난 상태 그대로, 나머지는 읽는다
        pages = self.pages()
        del pages[t.BASE + "/case/ad0071"]
        sec3, _, check3 = t.collect(sec, NOW + dt.timedelta(days=1), get=getter(pages), sleep=lambda s: None)
        self.assertEqual(check3["status"], "partial")
        self.assertTrue(next(c for c in sec3["cases"] if c["id"] == "AD0071")["stale"])

    def test_budget_leaves_pending_for_the_next_run(self):
        sec, _, _ = t.collect(None, NOW, get=getter(self.pages()), sleep=lambda s: None)
        many = "".join(sub_row("AD0092", f"s-00000140{i:02d}-aaaa", "General", "POSCO", "Exporter", "<span>2026-11-13</span> 13 Nov 2026") for i in range(t.PAGE_BUDGET + 3))
        pages = self.pages(CASE92.replace("</table>", many + "</table>"))
        sec2, events, check = t.collect(sec, NOW + dt.timedelta(days=1), get=getter(pages), sleep=lambda s: None)
        self.assertEqual(check["pagesRead"], t.PAGE_BUDGET)
        self.assertEqual(sum(1 for d in sec2["docs"] if d.get("detail") == "pending"), 3)
        self.assertEqual(len(events), t.PAGE_BUDGET + 3)                                       # 알림은 한다(파일 목록은 다음 실행)


if __name__ == "__main__":
    unittest.main()
