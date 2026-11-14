"""호주 ATRC 사건 공개기록(EPR): 기자 컴퓨터 브라우저 수집 줄(11-14 실제 수집에서 옮긴 줄) → 기준선, 새 문서·새 사건·일정 바뀜·목록에서 빠짐."""
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import au_epr_cases as a  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 11, 16, 7, 40, tzinfo=KST)   # 월요일 아침 실행(금요일 16:00 수집을 읽는다)
EPR = "/australian-trade-remedies-commission/current-cases-and-electronic-public-record-epr"
PDF = "/sites/default/files/atrc/public-record"


def row(*cells, link=None):
    return {"cells": list(cells), **({"links": [link]} if link else {})}


# 11-14 기자 컴퓨터 브라우저로 읽은 줄(칸 글자 그대로, 문서 줄은 일부만)
ROWS = [
    row("list", "28", "3"),
    row("case", "698", "Aluminium zinc coated steel (≥600mm)", "698", "Continuation", "Korea, Vietnam", "Final Report", "15/10/2026", "-", link=f"{EPR}/698"),
    row("case", "710", "Hollow structural sections", "710", "Continuation", "China, Korea, Malaysia, Taiwan", "SEF", "06/11/2026", "-", link=f"{EPR}/710"),
    row("case", "706", "Zinc coated (galvanised) steel", "706", "Investigation", "Korea, Vietnam", "SEF", "02/10/2026", "-", link=f"{EPR}/706"),
    row("title", "698", "698 - Aluminium zinc coated steel (≥600mm) from Korea, Vietnam", "17"),
    row("info", "698", "Applicant", "Bluescope Steel Limited (BSL)"),
    row("info", "698", "Inquiry Period", "1 January 2025 – 31 December 2025"),
    row("date", "698", "Initiation Date", "10 February 2026"),
    row("date", "698", "SEF* no later than", "24 September 2026"),
    row("date", "698", "SEF submissions due", "20 days after publication of SEF"),
    row("date", "698", "Final recommendation due no later than", "16 November 2026"),
    row("doc", "698", "17", "Submission", "Exporter - Hoa Sen Group - Response to SEF 698 [pdf 85 KB]", "15/10/2026", link=f"{PDF}/2026-10/698-17-submission-exporter-hoa-sen-group-response-to-sef-698.pdf"),
    row("doc", "698", "16", "Submission", "Exporter - KG Dongbu Steel Co Ltd - Response to SEF 698 [pdf 169 KB]", "15/10/2026", link=f"{PDF}/2026-10/698-16-submission-exporter-kg-dongbu-steel-co-ltd-response-to-sef-698.pdf"),
    row("doc", "698", "14", "Report", "Statement of Essential Facts (SEF 698) [pdf 734 KB]", "24/09/2026", link="/sites/default/files/adc/public-record/2026-09/698-14-statement-of-essential-facts-sef-698.pdf"),
    row("doc", "698", "13", "Submission", "Australian Industry - BlueScope Steel Limited - Submission on PMS in the Korean HRC market and response to KG Dongbu submission [pdf 310 KB]", "15/09/2026"),
    row("doc", "698", "2", "Notice - ADN", "ADN 2026/027 - Initiation of Continuation inquiry 698 [pdf 324 KB]", "10/02/2026"),
    row("title", "710", "710 - Hollow structural sections from China, Korea, Malaysia, Taiwan", "13"),
    row("date", "710", "Initiation Date", "03 August 2026"),
    row("date", "710", "PAD* earliest date", "NA"),
    row("date", "710", "SEF* no later than", "31 March 2027"),
    row("doc", "710", "13", "Questionnaire", "Exporter - Hengshui Jinghua Steel Pipe Co., Ltd - Response to Exporter Questionnaire [pdf 923 KB]", "06/11/2026"),
    row("doc", "710", "9", "Notice - TRN", "TRN 2026/143 - Extension of time to publish Statement of Essential Facts and Final Report [pdf 42 KB]", "07/10/2026"),
    row("title", "706", "706 - Zinc coated (galvanised) steel from Korea, Vietnam", "22"),
    row("date", "706", "Initiation Date", "19 June 2026"),
    row("date", "706", "SEF* no later than", "5 March 2027"),
    row("date", "706", "Final recommendation due no later than", "19 April 2027"),
    row("doc", "706", "22", "Notice - TRN", "TRN 2026/141 - Extension of Time to Publish SEF and Final Report [pdf 270 KB]", "02/10/2026", link=f"{PDF}/2026-10/706-22-notice-trn-atrc-extension-oftime-to-publish-sef-and-final-report.pdf"),
    row("doc", "706", "21", "Submission", "Exporter - Dongkuk Coated Metal Co., Ltd - Submission responding to BlueScope PMS [pdf 226 KB]", "30/09/2026"),
    row("doc", "706", "20", "File Note", "Meeting with POSCO [pdf 117 KB]", "28/09/2026", link="/sites/default/files/adc/public-record/2026-09/706-20-file-note-meeting-with-posco.pdf"),
    row("doc", "706", "18", "Report", "Termination report - Dongkuk Steel Mill Co. Ltd [pdf 230 KB]", "18/09/2026"),
    row("doc", "706", "17", "Notice - ADN", "ADN 2026/126 - Termination of part of an Investigation [pdf 78 KB]", "18/09/2026"),
]


def upload(rows, at):
    return {"pages": [{"id": "au-trn", "fetchedAt": at.isoformat(), "rows": []}, {"id": "au-epr", "fetchedAt": at.isoformat(), "rows": rows}]}


FRI = dt.datetime(2026, 11, 13, 16, 3, tzinfo=KST)


class AuEpr(unittest.TestCase):
    def test_parse_real_rows(self):
        total, cases = a.parse_rows(ROWS)
        self.assertEqual(total, 28)
        self.assertEqual(sorted(cases), ["698", "706", "710"])
        c = cases["698"]
        self.assertEqual((c["commodity"], c["kind"], c["countries"], c["milestone"], c["updated"], c["state"]),
                         ("Aluminium zinc coated steel (≥600mm)", "Continuation", "Korea, Vietnam", "Final Report", "2026-10-15", ""))
        self.assertEqual(c["url"], a.HOST + EPR + "/698")
        self.assertEqual((c["title"], c["n"]), ("698 - Aluminium zinc coated steel (≥600mm) from Korea, Vietnam", 17))
        self.assertEqual(c["dates"]["Final recommendation due no later than"], "16 November 2026")
        d = {x["no"]: x for x in c["docs"]}
        self.assertEqual(d["16"], {"no": "16", "type": "Submission", "title": "Exporter - KG Dongbu Steel Co Ltd - Response to SEF 698", "date": "2026-10-15",
                                   "url": a.HOST + PDF + "/2026-10/698-16-submission-exporter-kg-dongbu-steel-co-ltd-response-to-sef-698.pdf", "companies": ["KG스틸"]})
        self.assertNotIn("companies", d["17"])                       # 베트남 업체
        # 제목은 첫 문서 제목만 — 뒤에 이어 붙은 첨부 이름은 떼지만, 출입처 이름은 첨부 이름에서도 찾는다
        _, more = a.parse_rows([row("list", "28", "1"), row("case", "706", "x", "706", "Investigation", "Korea", "SEF", "01/11/2026", "-"),
                                row("doc", "706", "15", "Submission", "Australian Industry - BlueScope Steel Limited - Response to SEF 698 [pdf 288 KB] Non-Confidential Attachment - Appendix A [pdf 224 KB]", "15/10/2026"),
                                row("doc", "706", "12", "Questionnaire", "Importer - Acme Pty Ltd - Importer Questionnaire [pdf 1 MB] Exhibit 3 - POSCO price list [pdf 2 MB]", "31/08/2026")])
        self.assertEqual([(x["title"], x.get("companies")) for x in more["706"]["docs"]],
                         [("Australian Industry - BlueScope Steel Limited - Response to SEF 698", None), ("Importer - Acme Pty Ltd - Importer Questionnaire", ["포스코"])])
        self.assertEqual(d["13"]["companies"], ["KG스틸"])            # 호주 업체 의견서 제목에 든 이름
        self.assertIsNone(d["13"]["url"])
        d6 = {x["no"]: x.get("companies") for x in cases["706"]["docs"]}
        # 동국제강(Dongkuk Steel Mill)과 동국씨엠(Dongkuk Coated Metal)은 별개 법인
        self.assertEqual((d6["21"], d6["20"], d6["18"], d6["17"]), (["동국씨엠"], ["포스코"], ["동국제강"], None))

    def test_dates_and_tier(self):
        self.assertEqual(a.iso_date("15/10/2026"), "2026-10-15")
        self.assertEqual(a.iso_date("03 August 2026"), "2026-08-03")
        self.assertEqual(a.iso_date("5 March 2027"), "2027-03-05")
        self.assertEqual(a.iso_date("20 days after publication of SEF"), "")
        self.assertEqual(a.iso_date("31/02/2026"), "")
        # 기자 11-15: 직접 출입처 이름이 든 문서는 A(캐나다 CBSA와 같은 규칙), 절차 문서는 이름이 있어도 B
        self.assertEqual(a.tier_of("Submission", "Exporter - KG Dongbu Steel Co Ltd - Response to SEF 698", ["KG스틸"]), "A")
        self.assertEqual(a.tier_of("File Note", "Meeting with POSCO", ["포스코"]), "A")
        self.assertEqual(a.tier_of("Notice - TRN", "TRN 2026/150 - Extension of time for POSCO verification", ["포스코"]), "B")
        self.assertEqual(a.tier_of("Report", "Statement of Essential Facts (SEF 698)", []), "B")
        self.assertEqual(a.tier_of("Report", "Day 60 Status Report", []), "C")                 # 현황 보고는 절차 문서
        self.assertEqual(a.tier_of("Verification Report", "Exporter - Hoa Sen Group - Exporter verification report", []), "C")
        self.assertEqual(a.tier_of("Notice - TRN", "TRN 2026/143 - Extension of time to publish SEF", []), "C")   # 공지는 TRN 목록 감시가 따로 알린다
        self.assertEqual(a.tier_of("Submission", "Hyosung Heavy Industries submission", ["효성중공업(관련)"]), "C")  # 직접 출입처가 아닌 관련 회사 이름만
        self.assertEqual((a.named_tier(["포스코"]), a.named_tier(["효성중공업(관련)"]), a.named_tier(None)), ("A", "B", "B"))
        self.assertEqual(a.kind_ko("Continuation"), "종료재심")
        self.assertEqual(a.kind_ko("Something new"), "Something new")

    def test_first_read_is_baseline(self):
        sec, ev, chk = a.collect(upload(ROWS, FRI), None, NOW)
        self.assertEqual(ev, [])                                        # 지금 보이는 문서는 새 문서가 아니다
        self.assertEqual((chk["status"], chk["cases"], chk["returned"], chk["baseline"], chk["listTotal"]), ("ok", 3, 12, True, 28))
        self.assertEqual(sec["baselineAt"], NOW.isoformat(timespec="seconds"))
        self.assertEqual(sec["cases"]["706"]["companies"], ["동국씨엠", "동국제강", "포스코"])
        self.assertEqual([d["no"] for d in sec["cases"]["706"]["docs"]], ["22", "21", "20", "18", "17"])
        # 같은 수집을 다시 읽는 실행(21:30 등)은 아무것도 내지 않는다
        sec2, ev2, _ = a.collect(upload(ROWS, FRI), sec, NOW + dt.timedelta(hours=2))
        self.assertEqual(ev2, [])
        self.assertEqual(sec2["baselineAt"], sec["baselineAt"])

    def test_new_documents(self):
        sec, _, _ = a.collect(upload(ROWS, FRI), None, NOW)
        mon = dt.datetime(2026, 11, 16, 16, 2, tzinfo=KST)
        more = ROWS + [
            row("doc", "698", "18", "Report", "Final Report 698 [pdf 1.2 MB]", "16/11/2026", link=f"{PDF}/2026-11/698-18-report-final-report-698.pdf"),
            row("doc", "706", "23", "Submission", "Exporter - POSCO - Submission on PMS [pdf 90 KB]", "13/11/2026", link=f"{PDF}/2026-11/706-23.pdf"),
            row("doc", "706", "24", "Submission", "Importer - MantaMesh Pty Ltd - Further submission [pdf 50 KB]", "13/11/2026"),
            row("doc", "710", "14", "Notice - TRN", "TRN 2026/150 - Something [pdf 50 KB]", "12/11/2026"),
            row("doc", "710", "8", "Submission", "Importer - GP Marking International Pty. Ltd. - Response to ATM [pdf 251 KB]", "18/09/2026"),  # 전에 못 본 옛 줄
            row("doc", "710", "15", "Submission", "Exporter - Hyundai Steel Pipe Co., Ltd - Submission [pdf 50 KB]", "-"),  # 날짜 없음
        ]
        sec2, ev, chk = a.collect(upload(more, mon), sec, mon + dt.timedelta(minutes=10))
        got = {e["id"]: e for e in ev}
        self.assertEqual(sorted(got), ["au-epr:698:doc:18", "au-epr:706:doc:23", "au-epr:706:doc:24", "au-epr:710:doc:14"])
        e = got["au-epr:706:doc:23"]
        self.assertEqual((e["tier"], e["companies"], e["country"], e["pageId"]), ("A", ["포스코"], "호주", "au-epr"))
        self.assertEqual(e["label"], "호주 ATRC 사건 706 Zinc coated (galvanised) steel(조사)")
        self.assertEqual(e["text"], "새 문서 EPR 23번 Submission 「Exporter - POSCO - Submission on PMS」(2026-11-13)")
        self.assertEqual(e["url"], a.HOST + PDF + "/2026-11/706-23.pdf")
        self.assertEqual(got["au-epr:698:doc:18"]["tier"], "B")          # Report
        self.assertEqual(got["au-epr:706:doc:24"]["tier"], "C")          # 출입처 이름 없는 의견서
        self.assertEqual(got["au-epr:706:doc:24"]["url"], a.HOST + EPR + "/706")   # PDF 링크가 없으면 사건 페이지
        self.assertEqual(got["au-epr:710:doc:14"]["tier"], "C")          # 공지
        self.assertEqual((chk["newDocs"], chk["events"], chk["baseline"]), (4, 4, False))
        # 옛 날짜 줄·날짜 없는 줄은 저장만 한다(현대스틸파이프는 현대제철이 아니다)
        d10 = {d["no"]: d for d in sec2["cases"]["710"]["docs"]}
        self.assertIn("8", d10)
        self.assertEqual((d10["15"]["date"], d10["15"].get("companies")), ("", None))
        # 다음 수집에서 같은 문서를 다시 내지 않는다
        _, ev3, _ = a.collect(upload(more, mon + dt.timedelta(days=1)), sec2, mon + dt.timedelta(days=1, minutes=10))
        self.assertEqual(ev3, [])

    def test_burst_is_one_line(self):
        sec, _, _ = a.collect(upload(ROWS, FRI), None, NOW)
        mon = dt.datetime(2026, 11, 16, 16, 2, tzinfo=KST)
        many = ROWS + [row("doc", "706", str(n), "Questionnaire", f"Exporter - Company {n} - Response [pdf 1 KB]", "13/11/2026") for n in range(23, 31)]
        many.append(row("doc", "706", "31", "Submission", "Exporter - Dongkuk Coated Metal Co., Ltd - Further submission [pdf 1 KB]", "14/11/2026"))
        _, ev, chk = a.collect(upload(many, mon), sec, mon + dt.timedelta(minutes=10))
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0]["id"], "au-epr:706:docs:2026-11-16")
        self.assertIn("새 문서 9건(EPR 23~31번)", ev[0]["text"])
        self.assertEqual((ev[0]["tier"], ev[0]["companies"], ev[0]["url"]), ("A", ["동국씨엠"], a.HOST + EPR + "/706"))
        self.assertEqual(chk["newDocs"], 9)

    def test_stage_dates_new_case_and_gone(self):
        sec, _, _ = a.collect(upload(ROWS, FRI), None, NOW)
        mon = dt.datetime(2026, 11, 16, 16, 2, tzinfo=KST)
        rows = [r for r in ROWS if r["cells"][1] != "698" or r["cells"][0] == "list"]           # 698이 목록에서 빠짐
        rows = [row("case", "706", "Zinc coated (galvanised) steel", "706", "Investigation", "Korea, Vietnam", "Final Report", "16/11/2026", "-", link=f"{EPR}/706")
                if r["cells"][:2] == ["case", "706"] else r for r in rows]
        rows = [row("date", "706", "SEF* no later than", "30 April 2027") if r["cells"][:3] == ["date", "706", "SEF* no later than"] else r for r in rows]
        rows += [row("case", "731", "Steel reinforcing bar", "731", "Investigation", "Korea", "PAD", "12/11/2026", "-", link=f"{EPR}/731"),
                 row("title", "731", "731 - Steel reinforcing bar from Korea", "2"),
                 row("date", "731", "Initiation Date", "12 November 2026"),
                 row("doc", "731", "2", "Notice - TRN", "TRN 2026/160 - Initiation of Investigation 731 [pdf 1 KB]", "12/11/2026"),
                 row("doc", "731", "1", "Application", "Australian Industry - InfraBuild - Application [pdf 1 KB]", "12/11/2026"),
                 # 오래전에 개시된 사건이 한국 줄로 새로 잡힘: 알리지 않는다
                 row("case", "640", "Wind towers", "640", "Review", "China, Korea", "Final Report", "01/11/2026", "-", link=f"{EPR}/640"),
                 row("title", "640", "640 - Wind towers from China, Korea", "40"),
                 row("date", "640", "Initiation Date", "10 March 2025")]
        sec2, ev, chk = a.collect(upload(rows, mon), sec, mon + dt.timedelta(minutes=10))
        got = {e["id"]: e for e in ev}
        self.assertEqual(sorted(k.split(":")[1] + ":" + k.split(":")[2] for k in got), ["706:dates", "706:milestone", "731:new"])
        self.assertIn("다음 단계 바뀜: SEF → Final Report", next(e["text"] for k, e in got.items() if ":milestone:" in k))
        self.assertIn("SEF* no later than 5 March 2027 → 30 April 2027", next(e["text"] for k, e in got.items() if ":dates:" in k))
        self.assertTrue(all(e["tier"] == "C" for k, e in got.items() if ":706:" in k))
        new = got["au-epr:731:new"]
        self.assertEqual(new["tier"], "B")
        self.assertIn("개시 2026-11-12", new["text"])
        self.assertEqual(sec2["cases"]["698"]["missing"], 1)             # 한 번 빠진 것은 아직 알리지 않는다
        self.assertEqual((chk["cases"], chk["newCases"], chk["gone"]), (4, 1, 0))
        tue = mon + dt.timedelta(hours=17)
        sec3, ev3, chk3 = a.collect(upload(rows, tue), sec2, tue + dt.timedelta(minutes=10))
        self.assertEqual([e["id"] for e in ev3], ["au-epr:698:gone"])
        self.assertEqual((ev3[0]["tier"], ev3[0]["companies"]), ("A", ["KG스틸"]))   # 문서에 직접 출입처 이름이 있던 사건
        self.assertIn("진행 사건 목록에서 빠짐", ev3[0]["text"])
        _, ev4, _ = a.collect(upload(rows, tue + dt.timedelta(days=1)), sec3, tue + dt.timedelta(days=1, minutes=10))
        self.assertEqual(ev4, [])                                        # 다시 알리지 않는다

    def test_failures_keep_previous(self):
        sec, _, _ = a.collect(upload(ROWS, FRI), None, NOW)
        # 수집이 없거나 오래됨·실패: 직전 구역 그대로, 실패로 표시(0건 아님)
        for browser, why in [(None, "브라우저 수집 없음"), ({"pages": [{"id": "au-trn", "fetchedAt": FRI.isoformat(), "rows": []}]}, "브라우저 수집 없음"),
                             ({"pages": [{"id": "au-epr", "fetchedAt": FRI.isoformat(), "error": "EPR 목록 시간 초과 36초", "rows": []}]}, "브라우저 수집 실패(EPR 목록 시간 초과"),
                             ({"pages": [{"id": "au-epr", "fetchedAt": FRI.isoformat(), "rows": [row("doc", "706", "1", "x", "y", "z")]}]}, "목록 줄(list)이 없음")]:
            sec2, ev, chk = a.collect(browser, sec, NOW)
            self.assertEqual((ev, chk["status"], sec2["status"], len(sec2["cases"])), ([], "failed", "failed", 3))
            self.assertIn(why, chk["error"])
        late = dt.datetime(2026, 11, 18, 7, 40, tzinfo=KST)            # 수요일 아침에 금요일 수집뿐
        _, _, chk = a.collect(upload(ROWS, FRI), sec, late)
        self.assertIn("시간 전", chk["error"])
        self.assertEqual(a.collect(None, None, NOW)[0], None)             # 직전도 없으면 구역 없음
        # 사건 페이지 하나를 못 읽음: 그 사건은 직전 문서 줄 그대로, 새 문서로 알리지 않는다. 다음에 읽히면 그사이 문서는 알린다
        mon = dt.datetime(2026, 11, 16, 16, 2, tzinfo=KST)
        broken = [r for r in ROWS if r["cells"][1] != "706" or r["cells"][0] in ("list", "case")] + [row("error", "706", "사건 706 시간 초과 4초")]
        sec3, ev, chk = a.collect(upload(broken, mon), sec, mon + dt.timedelta(minutes=10))
        self.assertEqual((ev, chk["status"], chk["unread"]), ([], "partial", 1))
        self.assertEqual(len(sec3["cases"]["706"]["docs"]), 5)
        self.assertEqual(sec3["cases"]["706"]["error"], "사건 706 시간 초과 4초")
        back = ROWS + [row("doc", "706", "23", "File Note", "Meeting with Dongkuk Coated Metal [pdf 1 KB]", "16/11/2026")]
        _, ev5, _ = a.collect(upload(back, mon + dt.timedelta(days=1)), sec3, mon + dt.timedelta(days=1, minutes=10))
        self.assertEqual([e["id"] for e in ev5], ["au-epr:706:doc:23"])

    def test_archived_cases(self):
        # 보관(종결) 사건: 수집 코드가 TRN 목록에서 최근 공지가 있는 보관 사건의 사건 페이지도 읽어 acase 줄로 올린다(11-15)
        ARC = "/australian-trade-remedies-commission/archive-cases-and-electronic-public-record-epr"
        arc = [row("acase", "688", "Certain flat rolled steel products", "Findings of subsidy investigation", "China, Korea", "24/09/2026", link=f"{ARC}/688"),
               row("title", "688", "688 - Certain flat rolled steel products from China, Korea", "41"),
               row("date", "688", "Initiation Date", "20 October 2025"),
               row("doc", "688", "41", "Notice - TRN", "TRN 2026/104 - Findings of subsidy investigation [pdf 1 KB]", "24/09/2026"),
               row("doc", "688", "40", "Report", "Final Report 688 [pdf 2 MB]", "24/09/2026", link=f"{PDF}/2026-09/688-40-final-report.pdf"),
               row("doc", "688", "33", "Submission", "Exporter - Hyundai Steel Company - Response to SEF 688 [pdf 1 KB]", "10/08/2026", link=f"{PDF}/2026-08/688-33.pdf")]
        _, cases = a.parse_rows(ROWS + arc)
        c = cases["688"]
        self.assertEqual((c["archived"], c["commodity"], c["subject"], c["countries"], c["updated"], c["url"]),
                         (True, "Certain flat rolled steel products", "Findings of subsidy investigation", "China, Korea", "2026-09-24", a.HOST + ARC + "/688"))
        self.assertNotIn("archived", cases["706"])
        # 처음 보는 보관 사건은 기준선(기준선이 이미 있어도), 진행 사건 수에는 넣지 않는다
        sec, _, _ = a.collect(upload(ROWS, FRI), None, NOW)
        mon = dt.datetime(2026, 11, 16, 16, 2, tzinfo=KST)
        sec2, ev, chk = a.collect(upload(ROWS + arc, mon), sec, mon + dt.timedelta(minutes=10))
        self.assertEqual((ev, chk["cases"], chk["archived"], sec2["cases"]["688"]["archived"]), ([], 3, 1, True))
        self.assertEqual(a.label_of("688", sec2["cases"]["688"]), "호주 ATRC 사건 688 Certain flat rolled steel products(종결·보관)")
        # 보관 사건에 새로 붙는 문서도 같은 규칙으로 알린다
        tue = mon + dt.timedelta(hours=17)
        more = arc + [row("doc", "688", "42", "Notice - ADN", "ADN 2026/150 - Minister's decision - POSCO exempted [pdf 1 KB]", "16/11/2026")]
        sec3, ev3, _ = a.collect(upload(ROWS + more, tue), sec2, tue + dt.timedelta(minutes=10))
        self.assertEqual([(e["id"], e["tier"], e["companies"]) for e in ev3], [("au-epr:688:doc:42", "A", ["포스코"])])
        self.assertEqual(ev3[0]["label"], "호주 ATRC 사건 688 Certain flat rolled steel products(종결·보관)")
        # 진행 목록에 있던 698이 보관 사건으로 올라옴: 두 번 기다리지 않고 바로 알리고, '목록에서 빠짐'은 따로 내지 않는다
        rows = [r for r in ROWS if r["cells"][1] != "698" or r["cells"][0] == "list"]
        moved = [row("acase", "698", "Aluminium zinc coated steel (≥600mm)", "Findings of continuation inquiry", "Korea, Vietnam", "17/11/2026", link=f"{ARC}/698"),
                 row("title", "698", "698 - Aluminium zinc coated steel (≥600mm) from Korea, Vietnam", "19"),
                 row("doc", "698", "19", "Notice - TRN", "TRN 2026/170 - Findings of continuation inquiry [pdf 1 KB]", "17/11/2026"),
                 row("doc", "698", "18", "Report", "Final Report 698 [pdf 1 MB]", "17/11/2026"),
                 row("doc", "698", "17", "Submission", "Exporter - Hoa Sen Group - Response to SEF 698 [pdf 85 KB]", "15/10/2026"),
                 row("doc", "698", "16", "Submission", "Exporter - KG Dongbu Steel Co Ltd - Response to SEF 698 [pdf 169 KB]", "15/10/2026"),
                 row("doc", "698", "14", "Report", "Statement of Essential Facts (SEF 698) [pdf 734 KB]", "24/09/2026"),
                 row("doc", "698", "13", "Submission", "Australian Industry - BlueScope Steel Limited - Submission on PMS in the Korean HRC market and response to KG Dongbu submission [pdf 310 KB]", "15/09/2026"),
                 row("doc", "698", "2", "Notice - ADN", "ADN 2026/027 - Initiation of Continuation inquiry 698 [pdf 324 KB]", "10/02/2026")]
        wed = tue + dt.timedelta(days=1)
        sec4, ev4, chk4 = a.collect(upload(rows + more + moved, wed), sec3, wed + dt.timedelta(minutes=10))
        got = {e["id"]: e for e in ev4}
        self.assertEqual(sorted(got), ["au-epr:698:archived", "au-epr:698:doc:18", "au-epr:698:doc:19"])
        arch = got["au-epr:698:archived"]
        self.assertEqual((arch["tier"], arch["companies"]), ("A", ["KG스틸"]))       # 문서 제목에 직접 출입처 이름이 있던 사건
        self.assertIn("보관(종결) 목록으로 옮겨짐: 「698 - Aluminium zinc coated steel (≥600mm) from Korea, Vietnam」 · 가장 최근 공지 「Findings of continuation inquiry」(2026-11-17)", arch["text"])
        self.assertEqual((got["au-epr:698:doc:18"]["tier"], got["au-epr:698:doc:19"]["tier"]), ("B", "C"))
        self.assertEqual((chk4["cases"], chk4["archived"], sec4["cases"]["698"].get("missing")), (2, 2, None))
        _, ev5, _ = a.collect(upload(rows + more + moved, wed + dt.timedelta(hours=7)), sec4, wed + dt.timedelta(hours=7, minutes=10))
        self.assertEqual(ev5, [])
        # 보관 사건이 수집에서 빠지면(공지일이 150일을 넘김) 조용히 내려놓는다
        sec6, ev6, _ = a.collect(upload(rows, wed + dt.timedelta(days=1)), sec4, wed + dt.timedelta(days=1, minutes=10))
        self.assertEqual((ev6, sorted(sec6["cases"])), ([], ["706", "710"]))

    def test_want_list_asks_for_unread_beat_documents(self):
        sec, _, _ = a.collect(upload(ROWS, FRI), None, NOW)
        # 직접 출입처 이름이 들고 같은 사이트 PDF 링크가 있는 문서만: 의견서·보고서·공지 먼저, 그다음 최근 순, 4건까지
        self.assertEqual(sec["want"], [{"key": "698-16", "url": PDF + "/2026-10/698-16-submission-exporter-kg-dongbu-steel-co-ltd-response-to-sef-698.pdf"},
                                       {"key": "706-20", "url": "/sites/default/files/adc/public-record/2026-09/706-20-file-note-meeting-with-posco.pdf"}])
        self.assertEqual(sec["pdf"], {})
        self.assertEqual((a.pdf_path(a.HOST + "/sites/default/files/x/y.pdf"), a.pdf_path("https://evil.example/sites/default/files/x.pdf"), a.pdf_path("/sites/default/files/../x.pdf"),
                          a.pdf_path("/sites/default/files/x.docx"), a.pdf_path(None)), ("/sites/default/files/x/y.pdf", "", "", "", ""))
        # 읽은 것·세 번 실패한 것은 다시 달라고 하지 않고, 본문 기록은 다음 수집에도 이어진다
        sec["pdf"] = {"698-16": {"v": a.PDF_VERSION, "date": "2026-10-15", "excerpts": ["x"]}, "706-20": {"v": a.PDF_VERSION, "tries": 3, "error": "PDF 아님"},
                      "999-1": {"v": a.PDF_VERSION, "excerpts": []}}
        mon = dt.datetime(2026, 11, 16, 16, 2, tzinfo=KST)
        sec2, _, _ = a.collect(upload(ROWS, mon), sec, mon + dt.timedelta(minutes=10))
        self.assertEqual((sec2["want"], sorted(sec2["pdf"])), ([], ["698-16", "706-20"]))      # 문서 줄에 없는 999-1 기록은 버린다
        sec["pdf"]["706-20"]["tries"] = 2
        self.assertEqual([w["key"] for w in a.want_list(sec["cases"], sec["pdf"], NOW)], ["706-20"])
        old = dict(sec["cases"]["698"], docs=[dict(d, date="2025-01-01") for d in sec["cases"]["698"]["docs"]])
        self.assertEqual(a.want_list({"698": old}, {}, NOW), [])                               # 400일 넘은 문서는 받지 않는다

    def test_rows_outside_listed_cases_are_ignored(self):
        _, cases = a.parse_rows([row("list", "28", "1"), row("case", "698", "x", "698", "Continuation", "Korea", "SEF", "01/11/2026", "-"),
                                 row("doc", "999", "1", "Report", "Not listed", "01/11/2026"), row("doc", "../x", "1", "Report", "Bad", "01/11/2026"),
                                 row("doc", "698", "1", "Report", "Listed", "01/11/2026", link="https://evil.example/x.pdf"), row("weird", "698", "x")])
        self.assertEqual(list(cases), ["698"])
        self.assertEqual(cases["698"]["docs"], [{"no": "1", "type": "Report", "title": "Listed", "date": "2026-11-01", "url": None}])
        self.assertEqual(cases["698"]["url"], a.INDEX + "/698")


if __name__ == "__main__":
    unittest.main()
