"""미국 주 환경청 허가·공고: 11-03 탐침 124~126 실제 응답 글자로 조지아 주간 공고 PDF 항목 나누기(시설·신청 번호·주소·공고 종류·작업·이유·
의견 마감·군), 출입처 이름 규칙(현대트랜시스는 계열사라 뺌), 앨라배마 ADEM·루이지애나 LDEQ 목록, 첫 실행 기준선, 새 PDF 이벤트(신설 낱말 A),
조회 실패는 0이 아니라 미확인."""
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import us_state_env_watch as w  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 11, 3, 7, 0, tzinfo=KST)

# 11-03 탐침 126: pa1026-1 PDF 글자(줄바꿈은 공백으로)
GA_1026_1 = ("Georgia Environmental Protection Division Air Protection Branch EPD Public Advisory Week of October 5, 2026 "
             "Any comments should be received by November 6, 2026. SIP PUBLIC ADVISORIES BARTOW COUNTY "
             "Facility Name: Hanwha Q Cells Georgia, Inc. Application No: 30376 Facility Address: 100 Qcells Pkwy, White, 30184 "
             "EPD Notice Type: Permit Application Description of Operation: Semiconductors and Related Devices "
             "Reason for Application: The addition of a rotary concentrator, a regenerative thermal oxidizer and new coating lines. "
             "TROUP COUNTY Facility Name: Hyundai Transys Georgia Seating System LLC Application No: 30365 "
             "Facility Address: 3735 Kia Parkway, West Point, 31833 EPD Notice Type: Permit Application "
             "Description of Operation: Motor Vehicle Seating and Interior Trim Mfg. Reason for Application: Continued operation of an automobile seating plant.")
GA_0126_1 = ("EPD Public Advisory Week of January 5, 2026 MAJOR SOURCE SIP PERMITS BRYAN COUNTY Facility Name: Hyundai Motor Group Metaplant America LLC "
             "Application No: 29866 Facility Address: 9728 Hwy 280 E., Ellabell, 31308 EPD Notice Type: Proposed Permit "
             "Description of Operation: Electrical Vehicle Assembly Plant Reason for Application: Construction of a second paint shop to expand production. "
             "Comments on the proposed permit must be received by February 4, 2026.")
ADEM_HTML = """<ul><li><a href="/sites/default/files/2026-10/10-26scotch.html">Scotch Plywood Company</a></li>
<li><a href="/sites/default/files/2026-10/10-26hikae.html">Hikae Aluminum Processing, L.L.C.</a></li>
<li><a href="/sites/default/files/2026-11/11-26hpt.html">Hyundai Power Transformers USA, Inc.</a></li></ul>"""
ADEM_DETAIL = "<html><body><h1>Public Notice</h1><p>Proposed Consent Order ... Hyundai Power Transformers USA ... civil penalty of $12,000</p></body></html>"
LDEQ_HTML = ('<a href="https://internet.deq.louisiana.gov/portal/DIVISIONS/PPPSD/PUBLIC-COMMENTS?AIName=Valero Refining - New Orleans, LLC - St. Charles Refinery&amp;Subject=DRAFT AIR PERMIT&amp;AI=1406">Comment URL</a>'
             '<a href="https://internet.deq.louisiana.gov/portal/DIVISIONS/PPPSD/PUBLIC-COMMENTS?AIName=Hyundai Steel Louisiana, LLC - Donaldsonville Steel Mill&amp;Subject=PROPOSED PART 70 AIR PERMIT&amp;AI=245566">Comment URL</a>')


# 11-03 탐침 138b: 조지아 허가 검색 결과 줄(실제 HTML 모양)
def gap_row(fid, name, permit, op, date, ptype, narrative=True):
    docs = f'<a target="_blank" href="/Permits/View/ON-{op}">Narrative</a>' if narrative else ""
    return (f'<tr> <th scope="row" class="text-nowrap fw-normal" data-label="Facility ID">{fid}</th> <td data-label="Facility Name">{name}</td> '
            f'<td data-label="Permit" class="text-nowrap"> <a target="_blank" href="/Permits/View/OP-{op}">{permit}</a> </td> '
            f'<td data-label="Issuance Date">{date}</td> <td data-label="Other Documents"> {docs} </td> <td data-label="Permit Type">{ptype}</td> </tr>')


GAP_HEAD = ('<table><tr> <th scope="col" class="text-nowrap">Facility ID</th> <th scope="col" class="text-nowrap">Facility Name</th> '
            '<th scope="col" class="text-nowrap">Permit</th> <th scope="col">Issuance Date</th> <th scope="col">Other Documents</th> <th scope="col">Permit Type</th> </tr>')
GAP_HYUNDAI = (GAP_HEAD + gap_row("029-00015", "Hyundai Motor Group Metaplant America LLC", "3711-029-0015-P-01-0", "21001", "22&#x2011;Dec&#x2011;2022", "PSD/NSR")
               + gap_row("029-00015", "Hyundai Motor Group Metaplant America LLC", "3711-029-0015-P-01-4", "29001", "12&#x2011;Feb&#x2011;2026", "SIP")
               + gap_row("285-00087", "Hyundai-Transys Georgia Powertrain Inc.", "3714-285-0087-B-02-0", "29500", "16&#x2011;Jun&#x2011;2026", "SIP")
               + gap_row("029-00022", "SRM Hyundai Plant 4", "3273-029-0022-R-01-0", "25000", "10&#x2011;Oct&#x2011;2023", "SIP", False) + "</table>")
GAP_HANWHA = (GAP_HEAD + gap_row("313-00165", "Hanwha Q Cells USA, Inc.", "3674-313-0165-E-02-0", "29300", "1&#x2011;Jun&#x2011;2026", "SIP") + "</table>")
# 11-03 탐침 137·138b: 루이지애나 상공위원회 04-22 안건 글자(줄 모양)
LACI_TEXT = ("LOUISIANA BOARD OF COMMERCE AND INDUSTRY April 22, 2026 9:30 a.m. AGENDA 7. Industrial Tax Exemption Program NEW 2018 Rules Application "
             "20240073-ITE Valero Refining-New Orleans, LLC St. Charles $41,850,000 Renewal Applications 20240515-A-ITE Lotte Chemical Louisiana LLC "
             "Calcasieu $3,902,899 $95,000 12 20220056-C-ITE ASH Industries, Inc. Lafayette $1,130,237")
LACI_PAGE_HTML = ('<a href="https://admin.opportunitylouisiana.gov/wp-content/uploads/2026/10/CI-Agenda-PUBVer-OCT-29-2026-compressed.pdf">Agenda</a>'
                  '<a href="https://admin.opportunitylouisiana.gov/wp-content/uploads/2026/09/CI-Agenda-PUBVer-SEPT-23-2026_reduced.pdf">Agenda</a>'
                  '<a href="https://admin.opportunitylouisiana.gov/wp-content/uploads/2024/05/CI-RULES-AGENDA-MAY-3-2024.pdf">Rules</a>'
                  '<a href="https://admin.opportunitylouisiana.gov/wp-content/uploads/2026/04/CI-Board-Agenda-PUBVer-Apr-22-2026.pdf">Agenda</a>')


class R:
    def __init__(self, status=200, text="", content=b"", ctype="text/html"):
        self.status_code, self.text, self.content, self.headers = status, text, content, {"content-type": ctype}


def fake(pdfs, adem=ADEM_HTML, ldeq=LDEQ_HTML, fail=(), gap=None, laci_page=LACI_PAGE_HTML):
    calls = []
    gap = gap or {"Hyundai": GAP_HYUNDAI, "Hanwha": GAP_HANWHA}

    def get(url, headers=None, timeout=None, params=None):
        calls.append(url + (f"?Name={params['Name']}" if params else ""))
        if any(f in url for f in fail):
            raise type("ConnectTimeout", (Exception,), {})("x")
        if url == w.GAP_SEARCH:
            return R(200, gap.get(params["Name"], GAP_HEAD + "</table>"))
        if url == w.LACI_PAGE:
            return R(200, laci_page)
        if "admin.opportunitylouisiana.gov" in url:
            return R(200, content=("laci:" + url).encode(), ctype="application/pdf")
        if "epd.georgia.gov" in url:
            code = url.split("/document/document/")[1].split("/")[0]
            return R(200, content=code.encode(), ctype="application/pdf") if code in pdfs else R(404, "missing")
        if url.endswith("/public-notices") and "adem" in url:
            return R(200, adem)
        if "adem.alabama.gov/sites" in url:
            return R(200, ADEM_DETAIL)
        if "deq.louisiana.gov" in url:
            return R(200, ldeq)
        return R(404)
    return get, calls


class Parse(unittest.TestCase):
    def test_georgia_entries_fields_county_deadline_and_beat_rule(self):
        rows = w.ga_entries(GA_1026_1, "pa1026-1")
        self.assertEqual([(x["facility"], x["appNo"], x["county"], x["noticeType"], x["deadline"], x["week"]) for x in rows],
                         [("Hanwha Q Cells Georgia, Inc.", "30376", "Bartow", "Permit Application", "2026-11-06", "2026-10-05"),
                          ("Hyundai Transys Georgia Seating System LLC", "30365", "Troup", "Permit Application", "2026-11-06", "2026-10-05")])
        self.assertIn("rotary concentrator", rows[0]["reason"])
        self.assertNotIn("TROUP", rows[0]["reason"])   # 다음 군 머리에서 자름
        self.assertEqual(w.beat_of(rows[0]["facility"]), "한화솔루션")
        self.assertIsNone(w.beat_of(rows[1]["facility"]))   # 현대트랜시스는 계열사 — 출입처 아님
        self.assertEqual(w.beat_of("Hyundai Motor Group Metaplant America LLC"), "현대차")
        meta = w.ga_entries(GA_0126_1, "pa0126-1")[0]
        self.assertEqual((meta["deadline"], meta["county"]), ("2026-02-04", "Bryan"))   # 뒤에 오는 마감도 잡음

    def test_codes_are_this_and_last_month(self):
        self.assertEqual(w.ga_codes(NOW)[:2] + w.ga_codes(NOW)[-1:], ["pa1026-1", "pa1026-2", "pa1126-5"])
        self.assertEqual(w.ga_codes(dt.datetime(2026, 1, 9, tzinfo=KST))[0], "pa1225-1")


class Run(unittest.TestCase):
    def setUp(self):
        self.texts = {"pa1026-1": GA_1026_1, "pa0126-1": GA_0126_1, "pa1126-1": GA_0126_1.replace("Week of January 5, 2026", "Week of November 2, 2026")}
        self.orig = w.pdf_text
        w.pdf_text = lambda content: LACI_TEXT if content.startswith(b"laci:") else self.texts[content.decode()]

    def tearDown(self):
        w.pdf_text = self.orig

    def test_first_run_is_baseline_then_new_pdf_and_notice_are_events(self):
        get, calls = fake({"pa1026-1"}, adem=ADEM_HTML.replace('<li><a href="/sites/default/files/2026-11/11-26hpt.html">Hyundai Power Transformers USA, Inc.</a></li>', ""))
        doc = w.run(NOW, None, get=get, sleep=lambda s: None)
        self.assertEqual(doc["events"], [])
        self.assertEqual(sorted((x["company"], x["source"], x.get("baseline")) for x in doc["notices"] if x["source"] in ("ga", "ldeq")),
                         [("한화솔루션", "ga", True), ("현대제철", "ldeq", True)])
        self.assertEqual(doc["seen"]["ga"], ["pa1026-1"])
        self.assertTrue(doc["seen"]["adem"] and doc["seen"]["ldeq"])
        # 다음 실행: 새 주간 공고(메타플랜트 2차 도장 공장 — 신설 낱말 A), ADEM 새 공고(동의명령 → B), 본 PDF는 다시 안 받음
        get2, calls2 = fake({"pa1026-1", "pa1126-1"})
        doc2 = w.run(NOW + dt.timedelta(days=1), doc, get=get2, sleep=lambda s: None)
        self.assertNotIn(w.GA_PDF.format(code="pa1026-1"), calls2)
        ev = {e["company"]: e for e in doc2["events"]}
        self.assertEqual((ev["현대차"]["tier"], ev["현대차"]["kind"]), ("A", "주 환경청 허가·공고"))
        self.assertIn("조지아 주간 공고 pa1126-1 · Hyundai Motor Group Metaplant America LLC(Bryan County · 9728 Hwy 280 E., Ellabell, 31308) · Proposed Permit · 신청 29866", ev["현대차"]["text"])
        self.assertIn("의견 마감 2026-02-04", ev["현대차"]["text"])
        self.assertIn("허가 신청≠착공·투자 확정", ev["현대차"]["text"])
        self.assertEqual((ev["HD현대일렉트릭"]["tier"], ev["HD현대일렉트릭"]["kind"]), ("B", "주 환경청 제재 공고"))
        self.assertEqual(len([e for e in doc2["events"] if e["id"].startswith(("ga:", "adem:"))]), 2)

    def test_failures_are_unconfirmed_and_do_not_set_a_baseline(self):
        get, _ = fake({"pa1026-1"}, fail=("adem.alabama.gov", "deq.louisiana.gov"))
        doc = w.run(NOW, None, get=get, sleep=lambda s: None)
        self.assertEqual([c["status"] for c in doc["checks"]], ["ok", "failed", "failed", "ok", "ok"])
        self.assertEqual(doc["status"], "partial")
        self.assertNotIn("adem", doc["seen"])   # 실패한 실행은 기준선이 아니다 — 다음 성공 실행이 기준선
        get2, _ = fake({"pa1026-1"})
        doc2 = w.run(NOW + dt.timedelta(hours=1), doc, get=get2, sleep=lambda s: None)
        self.assertFalse([e for e in doc2["events"] if e["id"].startswith(("adem:", "ldeq:"))])
        get3, _ = fake(set(), fail=("epd.georgia.gov", "adem.alabama.gov", "deq.louisiana.gov", "air.gaepd.org", "opportunitylouisiana.gov"))
        self.assertEqual(w.run(NOW, None, get=get3, sleep=lambda s: None)["status"], "failed")



class PermitsAndIncentives(unittest.TestCase):
    def setUp(self):
        self.orig = w.pdf_text
        w.pdf_text = lambda content: (LACI_TEXT.replace("April 22, 2026", "December 10, 2026") if b"DEC-10" in content else LACI_TEXT) \
            if content.startswith(b"laci:") else ""

    def tearDown(self):
        w.pdf_text = self.orig

    def test_gap_rows_parse_real_layout_and_beat_rule(self):
        rows = w.gap_rows(GAP_HYUNDAI)
        self.assertEqual([(r["fid"], r["permit"], r["issued"], r["type"]) for r in rows][:2],
                         [("029-00015", "3711-029-0015-P-01-0", "2022-12-22", "PSD/NSR"), ("029-00015", "3711-029-0015-P-01-4", "2026-02-12", "SIP")])
        self.assertEqual(rows[1]["permitUrl"], "https://air.gaepd.org/Permits/View/OP-29001")
        self.assertEqual(rows[1]["docs"], [{"label": "Narrative", "url": "https://air.gaepd.org/Permits/View/ON-29001"}])
        self.assertEqual([w.beat_of(r["facility"]) for r in rows], ["현대차", "현대차", None, None])   # 현대트랜시스·레미콘 'SRM Hyundai' 제외
        self.assertEqual(w.beat_of("HYUNDAI-POSCO Louisiana Steel LLC"), "현대제철")   # 합작 법인은 포스코가 아니라 현대제철(최대주주)

    def test_laci_rows_find_beat_lines_only(self):
        rows = w.laci_rows(LACI_TEXT, "u")
        self.assertEqual([(r["appNo"], r["company"], r["meeting"], r["amount"]) for r in rows],
                         [("20240515-A-ITE", "롯데케미칼", "2026-04-22", "$3,902,899")])
        self.assertTrue(rows[0]["row"].startswith("20240515-A-ITE Lotte Chemical Louisiana LLC Calcasieu"))
        self.assertNotIn("ASH Industries", rows[0]["row"])   # 다음 신청 번호 앞에서 자름

    def test_baseline_then_new_permit_and_new_agenda_events(self):
        waits = []
        get, calls = fake({"pa1026-1"})
        doc = w.run(NOW, None, get=get, sleep=waits.append)
        self.assertFalse([e for e in doc["events"] if e["id"].startswith(("gap:", "laci:"))])   # 첫 실행은 기준선
        gap = [x for x in doc["notices"] if x["source"] == "gap"]
        self.assertEqual(sorted(x["permit"] for x in gap), ["3674-313-0165-E-02-0", "3711-029-0015-P-01-0", "3711-029-0015-P-01-4"])
        self.assertTrue(all(x.get("baseline") for x in gap))
        # 최근 120일 안 안건만(04월 안건·위원회 규칙 안건은 안 받음), PDF 사이 10초
        self.assertEqual([c for c in calls if "admin.opportunitylouisiana" in c],
                         ["https://admin.opportunitylouisiana.gov/wp-content/uploads/2026/09/CI-Agenda-PUBVer-SEPT-23-2026_reduced.pdf",
                          "https://admin.opportunitylouisiana.gov/wp-content/uploads/2026/10/CI-Agenda-PUBVer-OCT-29-2026-compressed.pdf"])
        self.assertEqual(waits.count(10.0), 2)
        self.assertEqual(len(doc["seen"]["laci"]), 2)
        # 다음 실행: 메타플랜트 새 PSD 허가(발급 60일 안) → A, 오래된 새 번호는 목록에만, 새 안건의 롯데케미칼 줄 → B
        new_hyundai = GAP_HYUNDAI.replace("</table>", gap_row("029-00015", "Hyundai Motor Group Metaplant America LLC", "3711-029-0015-P-02-0", "31000",
                                                              "20&#x2011;Oct&#x2011;2026", "PSD/NSR")
                                          + gap_row("199-00028", "HL Mando America Corporation", "3714-199-0028-S-01-0", "18000", "2&#x2011;Mar&#x2011;2019", "SIP")
                                          + "</table>")
        page2 = LACI_PAGE_HTML + '<a href="https://admin.opportunitylouisiana.gov/wp-content/uploads/2026/11/CI-Agenda-PUBVer-DEC-10-2026.pdf">Agenda</a>'
        get2, calls2 = fake({"pa1026-1"}, gap={"Hyundai": new_hyundai, "Hanwha": GAP_HANWHA}, laci_page=page2)
        doc2 = w.run(NOW + dt.timedelta(days=1), doc, get=get2, sleep=lambda s: None)
        ev = {e["id"]: e for e in doc2["events"] if e["id"].startswith(("gap:", "laci:"))}
        self.assertEqual(sorted(ev), ["gap:3711-029-0015-P-02-0", "laci:20240515-A-ITE:2026-12-10"])
        g = ev["gap:3711-029-0015-P-02-0"]
        self.assertEqual((g["tier"], g["kind"], g["company"]), ("A", "주 대기 허가 발급", "현대차"))
        self.assertIn("조지아 대기 허가 발급 · Hyundai Motor Group Metaplant America LLC(시설 029-00015) · 허가 3711-029-0015-P-02-0 · 발급 2026-10-20 · 종류 PSD/NSR", g["text"])
        self.assertIn("발급≠착공·가동", g["text"])
        self.assertEqual(g["url"], "https://air.gaepd.org/Permits/View/OP-31000")
        self.assertIn("gap:3714-199-0028-S-01-0", {x["id"] for x in doc2["notices"]})   # 2019년 발급 — 목록에만
        lc = ev["laci:20240515-A-ITE:2026-12-10"]
        self.assertEqual((lc["tier"], lc["kind"], lc["company"]), ("B", "주 상공위원회 안건", "롯데케미칼"))
        self.assertIn("심의 대상 — 승인·투자 확정 아님", lc["text"])
        self.assertEqual([c for c in calls2 if "admin.opportunitylouisiana" in c],
                         ["https://admin.opportunitylouisiana.gov/wp-content/uploads/2026/11/CI-Agenda-PUBVer-DEC-10-2026.pdf"])   # 본 안건은 다시 안 받음

if __name__ == "__main__":
    unittest.main()
