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


if __name__ == "__main__":
    unittest.main()
