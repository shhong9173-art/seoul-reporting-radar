"""인도 상장 법인 공시: 11-03 탐침 142~143 실제 NSE 공시 RSS 항목 모양(회사·PDF 주소·'… |SUBJECT: …'·IST 게시 시각)으로
현대차 인도법인만 고르기, 등급(A 설비·인수 / B 이사회 결과 / C 녹취록), 첫 실행 기준선, 새 공시 이벤트와 PDF 첫머리, RSS 밀려남 표시, 조회 실패."""
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import india_filings_watch as w  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 11, 3, 22, 10, tzinfo=KST)


def item(company, fname, desc, subject, when):
    return (f"<item><title>{company}</title><link>https://nsearchives.nseindia.com/corporate/{fname}</link>"
            f"<description>{desc} |SUBJECT: {subject}</description><pubDate>{when}</pubDate></item>")


def rss(*items):
    return ('<rss xmlns:atom="http://www.w3.org/2005/Atom" version="2.0"><channel><title>NSE News - Latest Announcements</title>'
            + "".join(items) + "</channel></rss>").encode()


AMANTA = item("Amanta Healthcare Limited", "AMANTA_03112026172706_Outcome_of_Board_Meeting.pdf",
              "Amanta Healthcare Limited has submitted to the Exchange, the financial results for the period ended September 30, 2026.",
              "Outcome of Board Meeting", "03-Nov-2026 17:30:45")
HMIL_TRANSCRIPT = item("Hyundai Motor India Limited", "HMILNSE_03112026164225_Transcript28102026.pdf",
                       "Hyundai Motor India Limited has informed the Exchange about Transcript",
                       "Analysts/Institutional Investor Meet/Con. Call Updates", "03-Nov-2026 16:43:09")
HMIL_BOARD = item("Hyundai Motor India Limited", "HMILNSE_04112026150000_Outcome.pdf",
                  "Hyundai Motor India Limited has informed the Exchange regarding Board meeting held on November 04, 2026.",
                  "Outcome of Board Meeting", "04-Nov-2026 15:00:10")
HMIL_CAPEX = item("Hyundai Motor India Limited", "HMILNSE_04112026160000_Capacity.pdf",
                  "Hyundai Motor India Limited has informed the Exchange regarding capacity expansion at Talegaon plant.",
                  "Updates", "04-Nov-2026 16:00:00")


class R:
    def __init__(self, status=200, content=b"", ctype="application/xml"):
        self.status_code, self.content, self.headers = status, content, {"content-type": ctype}


def fake(feed, fail_first=False, fail=False):
    calls = []

    def get(url, headers=None, timeout=None):
        calls.append(url)
        if fail or (fail_first and len([c for c in calls if c == w.RSS]) == 1 and url == w.RSS):
            raise type("ConnectionError", (Exception,), {})("x")
        if url == w.RSS:
            return R(200, feed)
        return R(200, b"%PDF " + url.encode(), "application/pdf")
    return get, calls


class Parse(unittest.TestCase):
    def test_items_tiers_and_beat_rule(self):
        rows = w.items_of(rss(AMANTA, HMIL_TRANSCRIPT))
        self.assertEqual([(r["company"], r["subject"], r["published"]) for r in rows],
                         [("Amanta Healthcare Limited", "Outcome of Board Meeting", "2026-11-03T21:00:45+09:00"),
                          ("Hyundai Motor India Limited", "Analysts/Institutional Investor Meet/Con. Call Updates", "2026-11-03T20:13:09+09:00")])
        self.assertEqual(rows[1]["desc"], "Hyundai Motor India Limited has informed the Exchange about Transcript")
        self.assertEqual([w.beat_of(r["company"]) for r in rows], [None, "현대차(인도 법인)"])
        self.assertEqual(w.tier_of(rows[1]), "C")
        self.assertEqual(w.tier_of(w.items_of(rss(HMIL_BOARD))[0]), "B")
        self.assertEqual(w.tier_of(w.items_of(rss(HMIL_CAPEX))[0]), "A")


class Letterhead(unittest.TestCase):
    def test_company_letterhead_is_skipped(self):
        # 11-27 운영: 첨부 첫머리 400자가 등록 주소·CIN·전화·누리집뿐이었다(가격 인상 안내)
        head = ("Hyundai Motor India Ltd. Regd. Office: Plot No. H-1, SIPCOT Industrial Park, Irrungattukottai, Sriperumbudur Taluk, Kancheepuram District, "
                "Tamil Nadu-602117, India. CIN (Corporate Identity Number): L29309TN1996PLC035377, T +91(44) 47100000 Corporate Office: Plot No. C11& C11A, "
                "City Centre, Urban Estate Gurgaon II, Sector 29 Gurugram, Haryana – 122001, India T+91(124) 6962000 www.hyundai.com/in/en ")
        self.assertEqual(w.strip_letterhead(head + "Sub: Advance intimation regarding price increase of vehicles w.e.f. December 01, 2026."),
                         "Sub: Advance intimation regarding price increase of vehicles w.e.f. December 01, 2026.")
        self.assertEqual(w.strip_letterhead("Talegaon plant capacity will be increased"), "Talegaon plant capacity will be increased")   # 머리글 없으면 그대로


class Run(unittest.TestCase):
    def setUp(self):
        self.orig = w.pdf_head
        w.pdf_head = lambda content, n=600: "Talegaon plant capacity will be increased " + content.decode()[-20:]

    def tearDown(self):
        w.pdf_head = self.orig

    def test_baseline_then_new_filings_with_pdf_head(self):
        get, calls = fake(rss(AMANTA, HMIL_TRANSCRIPT))
        doc = w.run(NOW, None, get=get, sleep=lambda s: None)
        self.assertEqual((doc["status"], doc["events"]), ("complete", []))
        self.assertEqual([(f["tier"], f.get("baseline")) for f in doc["filings"]], [("C", True)])
        self.assertEqual(calls, [w.RSS])   # 기준선은 PDF를 받지 않는다
        get2, calls2 = fake(rss(HMIL_CAPEX, HMIL_BOARD, AMANTA, HMIL_TRANSCRIPT))
        doc2 = w.run(NOW + dt.timedelta(hours=18), doc, get=get2, sleep=lambda s: None)
        ev = {e["id"]: e for e in doc2["events"]}
        self.assertEqual(sorted((e["tier"], e["subject"]) for e in ev.values()), [("A", "Updates"), ("B", "Outcome of Board Meeting")])
        cap = ev["nse:HMILNSE_04112026160000_Capacity.pdf"]
        self.assertEqual(cap["company"], "현대차(인도 법인)")
        self.assertIn("Hyundai Motor India Limited NSE 공시(2026-11-04 19:30 KST) · Updates · 「Hyundai Motor India Limited has informed the Exchange regarding capacity expansion", cap["text"])
        self.assertIn("첨부 첫머리 「Talegaon plant capacity will be increased", cap["text"])
        self.assertIn("현대차 자회사(별도 상장사)", cap["text"])
        self.assertEqual(len([c for c in calls2 if c.endswith(".pdf")]), 2)
        # 다음 실행에 같은 공시는 다시 안 알린다
        get3, calls3 = fake(rss(HMIL_CAPEX, HMIL_BOARD))
        doc3 = w.run(NOW + dt.timedelta(hours=21), doc2, get=get3, sleep=lambda s: None)
        self.assertEqual(len(doc3["events"]), 2)
        self.assertEqual(calls3, [w.RSS])

    def test_gap_retry_and_failure(self):
        get, _ = fake(rss(HMIL_TRANSCRIPT))
        doc = w.run(NOW, None, get=get, sleep=lambda s: None)
        # 다음 RSS의 가장 오래된 공시가 직전 가장 새 공시보다 늦으면 그 사이를 못 봤을 수 있다
        get2, _ = fake(rss(HMIL_BOARD))
        doc2 = w.run(NOW + dt.timedelta(days=1), doc, get=get2, sleep=lambda s: None)
        self.assertEqual((doc2["status"], doc2["checks"][0]["status"]), ("partial", "partial"))
        # 첫 요청 실패는 10초 뒤 한 번 다시
        waits = []
        get3, calls3 = fake(rss(HMIL_TRANSCRIPT), fail_first=True)
        self.assertEqual(w.run(NOW, None, get=get3, sleep=waits.append)["status"], "complete")
        self.assertEqual(waits, [10])
        get4, _ = fake(b"", fail=True)
        bad = w.run(NOW, doc, get=get4, sleep=lambda s: None)
        self.assertEqual((bad["status"], bad["checks"][0]["status"]), ("failed", "failed"))
        self.assertEqual(bad["filings"], doc["filings"])   # 실패해도 보관한 목록은 그대로

    def test_daily_reset_after_late_run_is_not_a_gap(self):
        # 11-04: RSS는 인도 자정(03:30 KST)에 새로 시작한다. 03:10 칸(인도 23:40) 실행 뒤면 20분만 못 본 것 — '일부'가 아니라 메모
        late = item("Hyundai Motor India Limited", "HMILNSE_03112026233500_Press.pdf", "Hyundai Motor India Limited has informed the Exchange about Press Release",
                    "Press Release", "03-Nov-2026 23:35:00")
        first = item("Amanta Healthcare Limited", "AMANTA_04112026000400_X.pdf", "Amanta Healthcare Limited has informed the Exchange", "Updates", "04-Nov-2026 00:04:00")
        get, _ = fake(rss(HMIL_TRANSCRIPT, late))
        at = dt.datetime(2026, 11, 4, 3, 10, tzinfo=KST)
        doc = w.run(at, None, get=get, sleep=lambda s: None)
        get2, _ = fake(rss(first, HMIL_BOARD))
        doc2 = w.run(at + dt.timedelta(hours=10), doc, get=get2, sleep=lambda s: None)
        self.assertEqual((doc2["status"], doc2["checks"][0]["status"]), ("complete", "ok"))
        self.assertEqual(doc2["checks"][0]["reset"], "RSS가 인도 자정(03:30 KST)에 새로 시작 — 직전 실행(03:10) 뒤 20분은 못 봄")


    def test_gap_only_over_the_indian_weekend_is_a_note_11_23(self):
        # 11-22(일) 18:40: 토 22:10 실행 뒤 일 03:30(인도 자정)에 RSS가 새로 시작 — 못 본 건 인도 토요일 저녁뿐이라 '일부'가 아니라 메모
        sat = item("Amanta Healthcare Limited", "AMANTA_21112026180000_X.pdf", "Amanta Healthcare Limited has informed the Exchange", "Updates", "21-Nov-2026 18:00:00")
        sun = item("Amanta Healthcare Limited", "AMANTA_22112026000800_X.pdf", "Amanta Healthcare Limited has informed the Exchange", "Updates", "22-Nov-2026 00:08:00")
        get, _ = fake(rss(sat))
        doc = w.run(dt.datetime(2026, 11, 21, 22, 10, tzinfo=KST), None, get=get, sleep=lambda s: None)
        get2, _ = fake(rss(sun))
        doc2 = w.run(dt.datetime(2026, 11, 22, 18, 40, tzinfo=KST), doc, get=get2, sleep=lambda s: None)
        self.assertEqual((doc2["status"], doc2["checks"][0]["status"]), ("complete", "ok"))
        self.assertIn("인도 토·일 구간만 못 봄", doc2["checks"][0]["reset"])
        # 월요일 첫 실행(일 22:10 뒤)도 같다
        mon = item("Amanta Healthcare Limited", "AMANTA_23112026000500_X.pdf", "Amanta Healthcare Limited has informed the Exchange", "Updates", "23-Nov-2026 00:05:00")
        get3, _ = fake(rss(mon))
        doc3 = w.run(dt.datetime(2026, 11, 23, 13, 10, tzinfo=KST), dict(doc2, generatedAt="2026-11-22T22:10:00+09:00"), get=get3, sleep=lambda s: None)
        self.assertEqual(doc3["status"], "complete")
        # 평일(인도 금요일 저녁)을 못 봤으면 그대로 '일부'
        fri = item("Amanta Healthcare Limited", "AMANTA_20112026180000_X.pdf", "Amanta Healthcare Limited has informed the Exchange", "Updates", "20-Nov-2026 18:00:00")
        get4, _ = fake(rss(fri))
        doc4 = w.run(dt.datetime(2026, 11, 20, 22, 10, tzinfo=KST), None, get=get4, sleep=lambda s: None)
        get5, _ = fake(rss(item("Amanta Healthcare Limited", "AMANTA_21112026000800_X.pdf", "Amanta Healthcare Limited has informed the Exchange", "Updates", "21-Nov-2026 00:08:00")))
        doc5 = w.run(dt.datetime(2026, 11, 21, 13, 10, tzinfo=KST), doc4, get=get5, sleep=lambda s: None)
        self.assertEqual(doc5["status"], "partial")


class RoutineNotices(unittest.TestCase):
    def test_rta_and_investor_service_notices_are_routine_11_21(self):
        # 11-20 실제 공시: 명의개서 대리인(RTA) 주소 변경이 B로 떴다
        t = lambda desc, subject="Updates": w.tier_of({"subject": subject, "desc": desc})  # noqa: E731
        self.assertEqual(t("Hyundai Motor India Limited has informed the Exchange regarding 'Intimation Regarding The Change In the address of the Corporate Office of the RTA"), "C")
        self.assertEqual(t("Compliance Certificate under Regulation 7(3) of SEBI (LODR)"), "C")
        self.assertEqual(t("Statement of Investor Complaints for the quarter"), "C")
        self.assertEqual(t("Hyundai Motor India Limited has informed the Exchange regarding capacity expansion at Talegaon plant."), "A")
        self.assertEqual(t("Outcome of Board Meeting held on November 04, 2026", "Outcome of Board Meeting"), "B")
        # 규칙 전에 B로 저장된 공시(11-20)는 다음 실행에서 C로 다시 매긴다(이벤트 등급도)
        fid = "nse:HMILNSE_20112026100624_ChangeRTAOFFICE.pdf"
        desc = "Hyundai Motor India Limited has informed the Exchange regarding 'Intimation Regarding The Change In the address of the Corporate Office of the RTA"
        prev = {"schema": w.SCHEMA, "baselineAt": "2026-11-01T00:00:00+09:00", "generatedAt": "2026-11-20T22:10:00+09:00",
                "filings": [{"id": fid, "company": "현대차(인도 법인)", "subject": "Updates", "desc": desc, "tier": "B", "firstSeen": "2026-11-20T16:10:00+09:00"}],
                "events": [{"id": fid, "tier": "B", "kind": "인도 법인 공시", "company": "현대차(인도 법인)", "detectedAt": "2026-11-20T16:10:00+09:00", "text": "x"}]}
        get, _ = fake(rss(AMANTA))
        doc = w.run(NOW + dt.timedelta(days=18), prev, get=get, sleep=lambda s: None)
        self.assertEqual([(f["id"], f["tier"]) for f in doc["filings"] if f["id"] == fid], [(fid, "C")])
        self.assertEqual([e["tier"] for e in doc["events"] if e["id"] == fid], ["C"])


if __name__ == "__main__":
    unittest.main()
