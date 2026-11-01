"""Trade remedy watch: TARIC quota parsing (real 2026-10 page layout), Korea-only vs shared quotas, first run vs later runs,
Federal Register title/body filtering, foreign listing diffs, failures kept as failures."""
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import trade_remedy_watch as w  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 10, 27, 7, 0, tzinfo=KST)


def detail_html(order, start, end, origins, initial, balance, exhausted="", awaiting="0", codes=("7210 70 80 00", "7212 40 80 00"), critical="Yes"):
    # Same field order and labels as quota_tariff_details.jsp on 2026-10-26.
    origin = "<br>".join(origins)
    rows = [("Order number", order), ("Validity period", f"{start} -  {end}"), ("Origin", origin),
            ("Initial amount", f"{initial}  Kilogram"), ("Amount", f"{initial}  Kilogram"), ("Balance", f"{balance}  Kilogram"),
            ("Transferred Amount", ""), ("Closed for drawing requests", "No"), ("Exhaustion date", exhausted), ("Critical", critical),
            ("Last import date", exhausted), ("Last allocation date", "19-10-2026"),
            ("Total awaiting allocation ( indicative )", awaiting), ("Blocking period", ""), ("Suspension period", ""),
            ("Allocated percentage at the last allocation", "0"), ("Associated TARIC code", "<br>".join(codes))]
    body = "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in rows)
    return (f"<html><body><div>Tariff quota details | Last TARIC update: 23-10-2026</div><table>{body}</table>"
            f"<div>Top Taxation and Custom Union Contact us</div></body></html>")


def list_html(rows):
    head = "<tr><th>Order number</th><th>Origins</th><th>Start date</th><th>End date</th><th>Balance</th></tr>"
    body = "".join(f"<tr><td>{o}</td><td>{origin}</td><td>{s}</td><td>{e}</td><td>{b}<br>Kilogram</td><td><a href='#'>[More info]</a></td></tr>"
                   for o, origin, s, e, b in rows)
    return f"<html><body><table>{head}{body}</table></body></html>"


KR_ONLY = ["European Union", "Korea, Republic of (South Korea)"]
SHARED = ["European Union", "India", "Korea, Republic of (South Korea)", "Türkiye", "United Kingdom"]
DETAILS = {
    ("099843", "2026-10-01"): detail_html("099843", "01-10-2026", "31-12-2026", KR_ONLY, "41828130", "0", "10-10-2026"),
    ("099843", "2026-07-01"): detail_html("099843", "01-07-2026", "30-09-2026", KR_ONLY, "41828130", "0", "25-07-2026"),
    ("099854", "2026-10-01"): detail_html("099854", "01-10-2026", "31-12-2026", KR_ONLY, "136000000", "34153885", codes=("7208 51 20 00",), critical="No"),
    ("099854", "2026-07-01"): detail_html("099854", "01-07-2026", "30-09-2026", KR_ONLY, "136000000", "0", "02-09-2026"),
    ("099507", "2026-10-01"): detail_html("099507", "01-10-2026", "31-12-2026", SHARED, "12575710", "0", "16-10-2026", awaiting="289370", critical="No"),
    ("099507", "2026-07-01"): detail_html("099507", "01-07-2026", "30-09-2026", SHARED, "12575710", "0", "20-07-2026", critical="No"),
}
LIST = list_html([("098827", "Korea, Republic of (South Korea)", "01-04-2026", "30-06-2026", "0"),
                  ("099507", "Multiple origins", "01-10-2026", "31-12-2026", "0"),
                  ("099507", "Multiple origins", "01-07-2026", "30-09-2026", "0"),
                  ("099843", "Multiple origins", "01-10-2026", "31-12-2026", "0"),
                  ("099854", "Multiple origins", "01-10-2026", "31-12-2026", "34153885")])
FR_JSON = {"count": 4, "results": [
    {"title": "Certain Corrosion-Resistant Steel Products From the Republic of Korea: Preliminary Results and Rescission, in Part, of Antidumping Duty Administrative Review; 2024-2025",
     "publication_date": "2026-10-08", "html_url": "https://www.federalregister.gov/d/2026-20698", "document_number": "2026-20698",
     "agencies": [{"name": "International Trade Administration"}], "raw_text_url": "https://www.federalregister.gov/full_text/2026-20698.txt"},
    {"title": "Heavy-Walled Rectangular Welded Carbon Steel Pipes and Tubes From Mexico: Initiation and Expedited Preliminary Results of Changed Circumstances Review",
     "publication_date": "2026-10-26", "html_url": "https://www.federalregister.gov/d/2026-21790", "document_number": "2026-21790",
     "agencies": [{"name": "International Trade Administration"}], "raw_text_url": "https://www.federalregister.gov/full_text/2026-21790.txt"},
    {"title": "Initiation of Antidumping and Countervailing Duty Administrative Reviews", "publication_date": "2026-10-01",
     "html_url": "https://www.federalregister.gov/d/2026-20160", "document_number": "2026-20160",
     "agencies": [{"name": "International Trade Administration"}], "raw_text_url": "https://www.federalregister.gov/full_text/2026-20160.txt"},
    {"title": "Initiation of Five-Year (Sunset) Reviews", "publication_date": "2026-10-01",
     "html_url": "https://www.federalregister.gov/d/2026-20161", "document_number": "2026-20161",
     "agencies": [{"name": "International Trade Administration"}], "raw_text_url": "https://www.federalregister.gov/full_text/2026-20161.txt"},
]}
BODIES = {
    "2026-20698": "<pre>Producer or exporter    Weighted-average\nHyundai Steel Company ........ 1.12\nDongkuk CM Co., Ltd. ........ 0.84\nPOSCO International Corporation ... 2.10\n</pre>",
    "2026-20160": "<pre>Republic of Korea: Certain Hot-Rolled Steel Flat Products, A-580-883\nPOSCO\nHyundai Steel Company\n</pre>",
    "2026-20161": "<pre>Brass Rod From Japan, A-588-..\nno beat company here\n</pre>",
}
AU_OLD = "<html><body><table><tr><td><a href='/adn/2026-090'>ADN 2026/090 Steel rod from Korea - initiation</a></td></tr></table></body></html>"
AU_NEW = ("<html><body><table><tr><td><a href='/adn/2026/101'>ADN 2026/101 Zinc coated steel from China, Korea and Taiwan - initiation</a></td></tr>"
          "<tr><td><a href='/adn/2026-090'>ADN 2026/090 Steel rod from Korea - initiation</a></td></tr></table></body></html>")
PAGES = [{"id": "au-adn", "country": "호주", "label": "호주 반덤핑위원회 공지(ADN)", "url": "https://www.industry.gov.au/anti-dumping-commission/anti-dumping-notices-adns"}]


class R:
    def __init__(self, code=200, text="", body=None):
        self.status_code, self.text, self.body = code, text, body

    def json(self):
        return self.body


def fake(au=AU_NEW, taric_down=False, fr_down=False, calls=None):
    def get(url, params=None, headers=None, timeout=None):
        if calls is not None:
            calls.append((url, dict(params) if isinstance(params, dict) else params))
        if "quota_list.jsp" in url:
            if taric_down:
                return R(503)
            return R(text=LIST if params["Origin"] == "KR" and params["Offset"] == 0 else list_html([]))
        if "quota_tariff_details.jsp" in url:
            if taric_down:
                return R(503)
            key = (params["Code"], params["StartDate"])
            return R(text=DETAILS[key]) if key in DETAILS else R(text="<html>No data</html>")
        if url == w.FR_API:
            return R(500) if fr_down else R(body=FR_JSON)
        if "full_text" in url:
            doc = url.rsplit("/", 1)[1].replace(".txt", "")
            return R(text=BODIES.get(doc, "<pre>nothing</pre>"))
        if "industry.gov.au" in url:
            return R(text=au)
        return R(404)
    return get


def run(previous=None, now=NOW, **k):
    cfg = {"pages": PAGES, "taricSeeds": ["099843", "099854", "099507"]}
    return w.run(cfg, now=now, previous=previous, get=fake(**k), sleep=lambda s: None)


class Taric(unittest.TestCase):
    def test_parses_real_detail_layout(self):
        d = w.parse_quota_detail(DETAILS[("099507", "2026-10-01")])
        self.assertEqual(d["initialT"], 12575.7)
        self.assertEqual(d["balanceT"], 0.0)
        self.assertEqual(d["usedPct"], 100.0)
        self.assertEqual(d["exhaustedOn"], "2026-10-16")
        self.assertEqual(d["awaitingT"], 289.4)
        self.assertEqual(d["scope"], "공동(한국 포함)")
        self.assertEqual(d["product"], "컬러강판(유기코팅)")
        self.assertEqual((d["periodStart"], d["periodEnd"]), ("2026-10-01", "2026-12-31"))
        kr = w.parse_quota_detail(DETAILS[("099843", "2026-10-01")])
        self.assertEqual(kr["scope"], "한국 전용")
        self.assertTrue(kr["critical"])
        plate = w.parse_quota_detail(DETAILS[("099854", "2026-10-01")])
        self.assertEqual(plate["product"], "후판")
        self.assertIsNone(plate["exhaustedOn"])
        self.assertEqual(plate["usedPct"], 74.9)
        self.assertIsNone(w.parse_quota_detail("<html>No data</html>"))

    def test_discovers_current_quarter_orders_only(self):
        orders, errors, pages = w.taric_orders(2026, dt.date(2026, 10, 1), get=fake(), sleep=lambda s: None)
        self.assertEqual(orders, ["099507", "099843", "099854"])  # 098827 (old safeguard, Q2) left out
        self.assertEqual(errors, [])
        self.assertEqual(pages, 1)

    def test_first_run_has_no_new_exhaustion_events_but_shows_quarter_comparison(self):
        doc = run()
        q = {x["order"]: x for x in doc["quotas"]}
        self.assertEqual(doc["quarter"], "2026-10-01")
        self.assertIn("[소진 2026-10-10 · 분기 10일째]", q["099843"]["tags"])
        self.assertEqual(q["099843"]["lastQuarter"]["daysToExhaust"], 24)
        self.assertIn("[직전 분기보다 15일 빨리 소진]", q["099843"]["tags"])
        self.assertIn("[배정 대기 289.4t]", q["099507"]["tags"])
        self.assertEqual(q["099854"]["tags"], [])
        self.assertFalse(any(e["pageId"] == "taric" for e in doc["events"]))  # first sight is not "newly exhausted"
        self.assertEqual(doc["quotaHistory"]["099854"]["2026-07-01"]["exhaustedOn"], "2026-09-02")

    def test_later_run_flags_newly_exhausted_and_reuses_last_quarter(self):
        first = run()
        first["quotas"] = [dict(x, exhaustedOn=None, usedPct=50.0) if x["order"] == "099843" else x for x in first["quotas"]]
        calls = []
        cfg = {"pages": PAGES, "taricSeeds": ["099843", "099854", "099507"]}
        doc = w.run(cfg, now=NOW + dt.timedelta(days=1), previous=first, get=fake(calls=calls), sleep=lambda s: None)
        ev = [e for e in doc["events"] if e["pageId"] == "taric"]
        self.assertEqual([e["id"] for e in ev], ["taric:099843:2026-10-01"])
        self.assertIn("한국 전용", ev[0]["label"])
        q = {x["order"]: x for x in doc["quotas"]}
        self.assertIn("[직전 확인 대비 +50.0%p]", q["099843"]["tags"])
        last_q_calls = [c for c in calls if "quota_tariff_details" in c[0] and c[1]["StartDate"] == "2026-07-01"]
        self.assertEqual(last_q_calls, [])  # last quarter is final and cached

    def test_taric_down_keeps_last_quotas_marked_stale(self):
        first = run()
        doc = run(previous=first, taric_down=True)
        c = doc["checks"][0]
        self.assertEqual(c["status"], "failed")
        self.assertTrue(all(q.get("stale") for q in doc["quotas"]))
        self.assertEqual(doc["status"], "partial")


class FederalRegister(unittest.TestCase):
    def test_title_or_named_omnibus_only_and_company_lines(self):
        doc = run()
        fr = {x["id"]: x for x in doc["federalRegister"]}
        self.assertNotIn("fr:2026-21790", fr)  # Mexico case, Korea only in body
        self.assertNotIn("fr:2026-20161", fr)  # omnibus without a beat company
        crs = fr["fr:2026-20698"]
        self.assertEqual(crs["stage"], "예비 판정")
        names = {n["company"]: n for n in crs["named"]}
        self.assertEqual(set(names), {"현대제철", "동국씨엠"})  # POSCO International is not 포스코
        self.assertIn("Hyundai Steel Company ........ 1.12", names["현대제철"]["lines"])
        self.assertEqual({n["company"] for n in fr["fr:2026-20160"]["named"]}, {"포스코", "현대제철"})
        self.assertFalse(any(x["isNew"] for x in doc["federalRegister"]))  # first run

    def test_failure_keeps_previous_list(self):
        first = run()
        doc = run(previous=first, fr_down=True)
        c = next(c for c in doc["checks"] if c["source"] == "미국 관보")
        self.assertEqual(c["status"], "failed")
        self.assertEqual(len(doc["federalRegister"]), len(first["federalRegister"]))


# Appendix of FR 2026-20778 (10-09, hot-rolled CVD final results) as published — line breaks as in the FR text.
HR_APPENDIX = """<pre>Appendix
List of Topics Discussed in the Issues and Decision Memorandum
I. Summary
II. Background
III. Scope of the Order
IV. Subsidies Valuation Information
V. Analysis of Programs
VI. Discussion of the Issues
Comment 1: Whether the Provision of Electricity Is Subsidized by
the Government of Korea (GOK)
Comment 2: Whether the Provision of Korea Emissions Trading
System (K-ETS) Permits is Countervailable
Comment 3: Whether Commerce Incorrectly Attributed Electricity
for More than Adequate Remuneration (MTAR) Benefits Received by
POSCO International Corporation (POSCO International) to POSCO
Comment 6: Whether to Modify POSCO's KEXIM OICP Loan Benchmark
Comment 8: Whether the Constructing and Operation of Workplace
Nursery Program is Countervailable
VII. Recommendation
[FR Doc. 2026-20778 Filed 10-8-26; 8:45 am]
BILLING CODE 3510-DS-P
</pre>"""


class MemoTopics(unittest.TestCase):
    def test_appendix_topics_named_and_unusual(self):
        topics = w.memo_topics(w.text_lines(HR_APPENDIX))
        self.assertEqual(topics[0], "Comment 1: Whether the Provision of Electricity Is Subsidized by the Government of Korea (GOK)")
        self.assertIn("Comment 8: Whether the Constructing and Operation of Workplace Nursery Program is Countervailable", topics)
        self.assertFalse(any(t.startswith(("I.", "VII.")) for t in topics))  # boilerplate headings dropped
        named, unusual = w.topic_flags(topics)
        self.assertEqual([t[:10] for t in named], ["Comment 3:", "Comment 6:"])
        self.assertEqual(unusual, ["Comment 8: Whether the Constructing and Operation of Workplace Nursery Program is Countervailable"])
        self.assertIsNone(w.memo_topics("no appendix here"))

    def test_results_notice_body_carries_topics_once(self):
        fr = {"results": [{"title": "Certain Hot-Rolled Steel Flat Products From the Republic of Korea: Final Results of Countervailing Duty Administrative Review; 2024",
                           "publication_date": "2026-10-09", "html_url": "https://www.federalregister.gov/d/2026-20778", "document_number": "2026-20778",
                           "agencies": [{"name": "International Trade Administration"}], "raw_text_url": "https://www.federalregister.gov/full_text/2026-20778.txt"}]}
        calls = []

        def get(url, params=None, headers=None, timeout=None):
            calls.append(url)
            if url == w.FR_API:
                return R(body=fr)
            return R(text=HR_APPENDIX) if "full_text" in url else R(404)
        rows, err, read = w.federal_register(NOW, None, get=get, sleep=lambda s: None)
        row = rows[0]
        self.assertEqual((err, read), (None, 1))
        self.assertEqual(len(row["memoUnusual"]), 1)
        self.assertIn("포스코", [n["company"] for n in row["named"]])
        self.assertEqual([t[:10] for t in row["memoNamed"]], ["Comment 3:", "Comment 6:"])
        again, _, read2 = w.federal_register(NOW, {"federalRegister": rows}, get=get, sleep=lambda s: None)
        self.assertEqual((read2, again[0]["memoUnusual"]), (0, row["memoUnusual"]))  # cached, body not read again


class Relay(unittest.TestCase):
    def test_relay_pages_go_through_the_worker(self):
        seen = []
        def get(url, params=None, headers=None, timeout=None):
            if url.endswith("/ingest/relay"):
                seen.append((params["url"], headers["Authorization"]))
                r = R(text=AU_NEW)
                r.headers = {"X-Relay-Status": "200"}
                return r
            if "industry.gov.au" in url:
                raise AssertionError("direct fetch of a relay page")
            return fake()(url, params=params, headers=headers, timeout=timeout)
        cfg = {"pages": [dict(PAGES[0], via="relay")], "taricSeeds": []}
        doc = w.run(cfg, now=NOW, get=get, sleep=lambda s: None, relay_token="tok-0123456789abcdef")
        self.assertEqual(seen, [(PAGES[0]["url"], "Bearer tok-0123456789abcdef")])
        self.assertEqual(doc["pages"][0]["status"], "ok")
        self.assertTrue(doc["pages"][0]["lines"])
        nort = w.run(cfg, now=NOW, get=get, sleep=lambda s: None)
        self.assertEqual((nort["pages"][0]["status"], nort["pages"][0]["error"]), ("failed", "중계 토큰 없음"))

    def test_upstream_error_seen_by_the_relay_is_a_failure(self):
        def get(url, params=None, headers=None, timeout=None):
            if url.endswith("/ingest/relay"):
                r = R(text="Access Denied")
                r.headers = {"X-Relay-Status": "403"}
                return r
            return fake()(url, params=params, headers=headers, timeout=timeout)
        cfg = {"pages": [dict(PAGES[0], via="relay")], "taricSeeds": []}
        doc = w.run(cfg, now=NOW, get=get, sleep=lambda s: None, relay_token="tok-0123456789abcdef")
        self.assertEqual(doc["pages"][0]["error"], "원 사이트 HTTP 403(중계)")


class Section337(unittest.TestCase):
    def test_ad_cvd_reviews_are_not_337(self):
        for title in ["Certain Hot-Rolled Steel Flat Products From the Republic of Korea: Final Results of Countervailing Duty Administrative Review; 2023",
                      "Certain Steel Nails From the Republic of Korea: Preliminary Results and Rescission, in Part of Antidumping Duty Administrative Review; 2024-2025",
                      "Certain Oil Country Tubular Goods From the Republic of Korea: Final Results of Antidumping Duty Administrative Review; 2023-2024"]:
            self.assertFalse(w.is_337(title), title)
        for title in ["Certain Automotive Headlamps and Components Thereof; Notice of Institution of Investigation",
                      "Certain Wireless Earbuds; Notice of Receipt of Complaint; Solicitation of Comments Relating to the Public Interest"]:
            self.assertTrue(w.is_337(title), title)
        doc = run()
        self.assertFalse(next(x for x in doc["federalRegister"] if x["id"] == "fr:2026-20698")["section337"])

    def test_baseline_date_is_kept_across_runs(self):
        first = run()
        later = run(previous=first, now=NOW + dt.timedelta(days=2))
        self.assertEqual(later["baselineSince"], first["generatedAt"])


class ForeignPages(unittest.TestCase):
    def test_new_korea_line_is_an_event_with_absolute_link(self):
        first = run(au=AU_OLD)
        self.assertEqual([e for e in first["events"] if e["pageId"] == "au-adn"], [])
        doc = run(previous=first, au=AU_NEW, now=NOW + dt.timedelta(days=1))
        ev = [e for e in doc["events"] if e["pageId"] == "au-adn"]
        self.assertEqual(len(ev), 1)
        self.assertIn("Zinc coated steel from China, Korea", ev[0]["text"])
        self.assertEqual(ev[0]["url"], "https://www.industry.gov.au/adn/2026/101")
        again = run(previous=doc, au=AU_NEW, now=NOW + dt.timedelta(days=2))
        self.assertEqual(len([e for e in again["events"] if e["pageId"] == "au-adn"]), 1)

    def test_blocked_page_is_failed_and_keeps_lines(self):
        first = run(au=AU_OLD)
        cfg = {"pages": PAGES, "taricSeeds": []}
        def get(url, **k):
            return R(403) if "industry.gov.au" in url else fake()(url, **k)
        doc = w.run(cfg, now=NOW, previous=first, get=get, sleep=lambda s: None)
        page = doc["pages"][0]
        self.assertEqual((page["status"], page["error"]), ("failed", "HTTP 403"))
        self.assertTrue(page["lines"])
        self.assertEqual(doc["status"], "partial")


if __name__ == "__main__":
    unittest.main()


class KoreaLines(unittest.TestCase):
    def test_baseline_from_an_older_line_reader_is_not_diffed(self):
        prev = {"pages": [dict(PAGES[0], status="ok", lines={})]}  # first run, before block lines (no parser mark)
        doc = run(previous=prev, au=AU_NEW)
        self.assertEqual([e for e in doc["events"] if e["pageId"] == "au-adn"], [])
        self.assertEqual(doc["pages"][0]["parser"], w.LINE_PARSER)

    def test_headings_and_country_lines_with_case_context(self):
        raw = ("<html><nav><a href='/x'>Korea trade office</a></nav><main><h2>2025</h2>"
               "<h3>Steel Strapping: Dumping and subsidy</h3><p>China, South Korea, Türkiye and Vietnam</p><p>Concluded on 2025-12-01</p>"
               "<h3>Oil Country Tubular Goods 5: Dumping</h3><p>China, South Korea, Türkiye and Vietnam</p>"
               "<ul><li><a href='/sima/ctl2026.html'>Cold-rolled coil from the Republic of Korea: Notice of initiation</a></li></ul></main></html>")
        lines = w.korea_lines(raw)
        self.assertIn("Steel Strapping: Dumping and subsidy — China, South Korea, Türkiye and Vietnam", lines)
        self.assertIn("Oil Country Tubular Goods 5: Dumping — China, South Korea, Türkiye and Vietnam", lines)
        self.assertEqual(lines["Cold-rolled coil from the Republic of Korea: Notice of initiation"], "/sima/ctl2026.html")
        self.assertFalse(any("trade office" in k for k in lines))  # navigation removed
        self.assertEqual(len(lines), 3)

    def test_browser_page_rows_from_the_reporters_computer(self):
        # 10-30 기자 컴퓨터에서 읽은 호주 TRN 실제 줄 모양(칸 글자 + 같은 사이트 링크)
        page = {"id": "au-trn", "country": "호주", "label": "호주 무역구제위원회 공지(TRN)", "via": "browser",
                "url": "https://www.industry.gov.au/australian-trade-remedies-commission/trade-remedies-notices-trns"}
        row = lambda no, case, prod, kind, ctry, day, pdf: {  # noqa: E731
            "cells": [f"2026/{no} [PDF 42.34 KB]", case, prod, kind, ctry, day],
            "links": [f"/sites/default/files/atrc/public-record/2026-10/{pdf}.pdf", f"/australian-trade-remedies-commission/current-cases-and-electronic-public-record-epr/{case}"]}
        rows = [row("143", "710", "Hollow structural sections", "Extension of time for SEF and Final Report", "China, Korea, Malaysia, Taiwan", "07/10/2026", "710-9"),
                row("141", "706", "Zinc coated (galvanised) steel", "Extension of time for SEF and Final Report", "Korea, Vietnam", "02/10/2026", "706-22")]
        cfg = {"pages": [page], "taricSeeds": []}
        fetched = []
        def get(url, **k):
            fetched.append(url)
            return fake()(url, **k)
        b1 = {"pages": [{"id": "au-trn", "fetchedAt": (NOW - dt.timedelta(hours=15)).isoformat(), "rows": rows[1:]}]}
        first = w.run(cfg, now=NOW, get=get, sleep=lambda s: None, browser=b1)
        self.assertFalse(any("industry.gov.au" in u for u in fetched))  # 직접 접속하지 않음
        p = first["pages"][0]
        self.assertEqual((p["status"], p["parser"], len(p["lines"])), ("ok", w.BROWSER_PARSER, 1))
        self.assertEqual(first["events"], [])  # 첫 수집은 기준선
        b2 = {"pages": [{"id": "au-trn", "fetchedAt": (NOW + dt.timedelta(hours=9)).isoformat(), "rows": rows}]}
        doc = w.run(cfg, now=NOW + dt.timedelta(days=1), previous=first, get=get, sleep=lambda s: None, browser=b2)
        ev = [e for e in doc["events"] if e["pageId"] == "au-trn"]
        self.assertEqual(len(ev), 1)
        self.assertIn("710 Hollow structural sections Extension of time for SEF and Final Report China, Korea", ev[0]["text"])
        self.assertEqual(ev[0]["url"], "https://www.industry.gov.au/sites/default/files/atrc/public-record/2026-10/710-9.pdf")
        # 오래된 수집·수집 없음은 미확인(지난 줄은 유지)
        stale = w.run(cfg, now=NOW + dt.timedelta(days=3), previous=doc, get=get, sleep=lambda s: None, browser=b2)
        self.assertEqual(stale["pages"][0]["status"], "failed")
        self.assertIn("시간 전", stale["pages"][0]["error"])
        self.assertTrue(stale["pages"][0]["lines"])
        none = w.run(cfg, now=NOW, get=get, sleep=lambda s: None, browser=None)
        self.assertIn("브라우저 수집 없음", none["pages"][0]["error"])

    def test_renumbered_table_rows_are_not_new_lines(self):
        # 인도 DGTR 10-28·10-31 실제: 한국 줄 6개 그대로인데 위에 새 사건이 끼어 일련번호만 밀림("3 - …"→"4 - …")
        page = {"id": "in-dgtr", "country": "인도", "label": "인도 DGTR 반덤핑 조사", "url": "https://www.dgtr.gov.in/en/anti-dumping-investigation-in-india"}
        ipa = "Ongoing Investigation Anti-dumping investigation concerning imports of Isopropyl Alcohol from the European Union, South Korea, Taiwan, and the United States of America"
        def page_html(*rows):
            return "<html><table>" + "".join(f"<tr><td>{n} - <a href='/en/case/{n}'>{t}</a></td></tr>" for n, t in rows) + "</table></html>"
        bodies = iter([page_html((3, ipa)), page_html((4, ipa)), page_html((4, ipa), (5, "Ongoing Investigation Anti-dumping investigation concerning imports of Acetone from the Republic of Korea"))])
        cfg = {"pages": [page], "taricSeeds": []}
        def get(url, **k):
            return R(200, next(bodies)) if "dgtr" in url else fake()(url, **k)
        first = w.run(cfg, now=NOW, get=get, sleep=lambda s: None)
        self.assertEqual(list(first["pages"][0]["lines"]), [ipa])  # 번호를 뗀 열쇠
        second = w.run(cfg, now=NOW + dt.timedelta(days=1), previous=first, get=get, sleep=lambda s: None)
        self.assertEqual([e for e in second["events"] if e["pageId"] == "in-dgtr"], [])
        third = w.run(cfg, now=NOW + dt.timedelta(days=2), previous=second, get=get, sleep=lambda s: None)
        ev = [e for e in third["events"] if e["pageId"] == "in-dgtr"]
        self.assertEqual(len(ev), 1)
        self.assertIn("Acetone", ev[0]["text"])
        self.assertFalse(ev[0]["text"][0].isdigit())
        # 번호 붙은 열쇠로 저장된 지난 실행과도 새 줄로 안 본다(배포 직후 첫 실행)
        old = {"pages": [dict(page, status="ok", parser=w.LINE_PARSER, lines={f"3 - {ipa}": "/en/case/3"})], "events": []}
        bodies2 = iter([page_html((4, ipa))])
        def get2(url, **k):
            return R(200, next(bodies2)) if "dgtr" in url else fake()(url, **k)
        doc = w.run(cfg, now=NOW, previous=old, get=get2, sleep=lambda s: None)
        self.assertEqual([e for e in doc["events"] if e["pageId"] == "in-dgtr"], [])

    def test_renumbered_repeats_already_stored_are_marked_not_deleted(self):
        page = {"id": "in-dgtr", "country": "인도", "label": "인도 DGTR 반덤핑 조사", "url": "https://www.dgtr.gov.in/x"}
        ipa = "Ongoing Investigation Anti-dumping investigation concerning imports of Isopropyl Alcohol from the European Union, South Korea"
        ev = lambda n, day: {"id": f"in-dgtr:{n} - {ipa}"[:89], "pageId": "in-dgtr", "country": "인도", "label": page["label"],  # noqa: E731
                             "text": f"{n} - {ipa}", "url": "https://www.dgtr.gov.in/x", "detectedAt": (NOW - dt.timedelta(days=day)).isoformat()}
        prev = {"pages": [dict(page, status="ok", parser=w.LINE_PARSER, lines={f"4 - {ipa}": None})], "events": [ev(3, 3), ev(4, 1)]}
        cfg = {"pages": [page], "taricSeeds": []}
        def get(url, **k):
            return R(200, f"<table><tr><td>4 - {ipa}</td></tr></table>") if "dgtr" in url else fake()(url, **k)
        doc = w.run(cfg, now=NOW, previous=prev, get=get, sleep=lambda s: None)
        got = sorted((e for e in doc["events"] if e["pageId"] == "in-dgtr"), key=lambda e: e["detectedAt"])
        self.assertEqual(len(got), 2)  # 지우지 않는다
        self.assertEqual((got[0].get("renumbered"), got[0].get("repeats")), (None, 1))
        self.assertTrue(got[1]["renumbered"])

    def test_serial_free_keeps_case_numbers_and_years(self):
        self.assertEqual(w.serial_free("12 - Ongoing Investigation X"), "Ongoing Investigation X")
        self.assertEqual(w.serial_free("3. Hot-rolled steel from Korea"), "Hot-rolled steel from Korea")
        self.assertEqual(w.serial_free("2026/143 [PDF 42.34 KB] 710 Hollow"), "2026/143 [PDF 42.34 KB] 710 Hollow")
        self.assertEqual(w.serial_free("2026 - Korea review"), "2026 - Korea review")
        self.assertEqual(w.serial_free("AD0012 Korea"), "AD0012 Korea")

    def test_disabled_page_is_not_fetched_or_counted_as_failure(self):
        cfg = {"pages": [dict(PAGES[0], disabled="주소 확인 전")], "taricSeeds": ["099843"]}
        seen = []
        def get(url, **k):
            seen.append(url)
            return fake()(url, **k)
        doc = w.run(cfg, now=NOW, get=get, sleep=lambda s: None)
        self.assertFalse(any("industry.gov.au" in u for u in seen))
        self.assertEqual(doc["pages"][0]["status"], "disabled")
        self.assertFalse(any(c["source"] == PAGES[0]["label"] for c in doc["checks"]))
        self.assertEqual(doc["status"], "complete")

    def test_timeout_is_retried_once(self):
        n = []
        class ReadTimeout(Exception):
            pass
        def get2(url, **k):
            if "industry.gov.au" in url:
                n.append(k.get("timeout"))
                if len(n) == 1:
                    raise ReadTimeout()
            return fake()(url, **k)
        doc = w.run({"pages": PAGES, "taricSeeds": []}, now=NOW, get=get2, sleep=lambda s: None)
        self.assertEqual(n, [60, 60])
        self.assertEqual(doc["pages"][0]["status"], "ok")


class PagePattern(unittest.TestCase):
    def test_vietnamese_word_for_korea(self):
        import re
        raw = ('<ul><li><a href="/tin/1">Khởi xướng điều tra chống bán phá giá thép mạ từ Trung Quốc và Hàn Quốc</a></li>'
               '<li><a href="/tin/2">Hội thảo về phòng vệ thương mại</a></li></ul>')
        lines = w.korea_lines(raw, re.compile("hàn quốc|korea", re.I))
        self.assertEqual(list(lines), ["Khởi xướng điều tra chống bán phá giá thép mạ từ Trung Quốc và Hàn Quốc"])
        self.assertEqual(w.korea_lines(raw), {})  # 기본 'korea'로는 안 잡힌다
        uk = '<table><tr><td><a href="/public/case/AD0099/">Case Hot-rolled steel plate from South Korea</a></td><td>Initiated</td></tr></table>'
        self.assertTrue(any("Hot-rolled steel plate from South Korea" in k for k in w.korea_lines(uk)))


# 관보 원문(raw text) 표 — 2026-10-08 도금강판 상계관세·반덤핑 예비, 2026-05-14 반덤핑 최종, 2026-08-14 변압기 반덤핑 최종(줄 그대로)
CORE_CVD_PRELIM = """Preliminary Results of Review
------------------------------------------------------------------------
Subsidy rate
Company (percent ad
valorem)
------------------------------------------------------------------------
Hyundai Steel Company \\12\\.............................. 0.58
KG Dongbu Steel Co., Ltd.\\13\\........................... 4.82
Companies Not Selected for Individual Review \\14\\....... 2.22
------------------------------------------------------------------------
Disclosure
Appendix II
Non-Selected Companies Under Review
1. POSCO
2. POSCO International
3. POSCO Coated & Color Steel Co., Ltd.
4. POSCO Steeleon Co., Ltd.
5. SeAH Coated Metal
6. SeAH Steel Corporation
7. TCC Steel Corp.
[FR Doc. 2026-20699 Filed 10-7-26; 8:45 am]
"""
CORE_AD_PRELIM = """Preliminary Results
We preliminarily determine the following weighted-average dumping
margins for the period July 1, 2024, through June 30, 2025:
------------------------------------------------------------------------
Weighted-
average
Exporter/producer dumping
margin
(percent)
------------------------------------------------------------------------
KG Dongbu Steel Co., Ltd.................................... 23.40
Dongkuk Coated Metal Co., Ltd./Aju Steel Co., Ltd........... 19.43
Companies Not Selected for Individual Review \\12\\........... 20.58
------------------------------------------------------------------------
Disclosure
For companies not selected for individual examination, we assign the rate above.
Appendix I
List of Topics Discussed in the Preliminary Decision Memorandum
I. Summary
Appendix II
Review-Specific Rate Applicable to Companies Not Selected for
Individual Review
1. Hyundai Steel Company
2. POSCO
3. POSCO International Corporation
4. SeAH Coated Metal
5. SeAH Steel Corporation
Appendix III
Companies With No Reviewable Entries
1. Dongbu Incheon Steel Co., Ltd.
2. Dongkuk Steel Mill Co., Ltd.
3. POSCO Coated & Color Steel Co., Ltd.
4. TCC Steel Corp.
[FR Doc. 2026-20698 Filed 10-7-26; 8:45 am]
BILLING CODE 3510-DS-P
"""
LINE_PIPE = """Commerce is amending its Amended Final Determination and its antidumping duty Order with
respect to SeAH Steel Corporation (SeAH) and all other producers and exporters. The revised
estimated weighted-average dumping margins are as follows:
------------------------------------------------------------------------
Weighted-
average
Exporter or producer dumping
margin
(percent)
------------------------------------------------------------------------
SeAH........................................................ 4.55
All Others.................................................. 5.39
------------------------------------------------------------------------
"""
CORE_AD_FINAL = """Final Results of Review
------------------------------------------------------------------------
Weighted-
average
Exporter/producer \\6\\ dumping
margin
(percent)
------------------------------------------------------------------------
Dongbu Incheon Steel Co., Ltd............................... 0.00
Dongkuk Coated Metal Co., Ltd............................... 0.00
Dongkuk Steel Mill Co., Ltd................................. 0.00
Hyundai Steel Company....................................... 0.00
KG Steel Corporation; KG Dongbu Steel Co., Ltd.............. 0.00
POSCO....................................................... 0.00
POSCO International Corporation............................. 0.00
POSCO STEELEON Co., Ltd..................................... 0.00
SeAH Coated Metal Corporation............................... 0.00
SeAH Steel Corporation...................................... 0.00
------------------------------------------------------------------------
[[Page 27253]]
Disclosure
"""
LPT = """------------------------------------------------------------------------
Weighted-
average
Producer/exporter dumping
margin
(percent)
------------------------------------------------------------------------
HD Hyundai Electric Co., Ltd............................... 0.00
Iljin Electric Co., Ltd.................................... 0.00
LS Electric Co., Ltd....................................... 4.32
Hyosung Heavy Industries Corporation....................... 4.32
------------------------------------------------------------------------
"""
CORE_AD_TITLE = "Certain Corrosion-Resistant Steel Products From the Republic of Korea: Preliminary Results and Rescission, in Part, of Antidumping Duty Administrative Review; 2024-2025"


class DutyRates(unittest.TestCase):
    def test_rate_rows_from_real_tables(self):
        t = w.rate_table(CORE_CVD_PRELIM, "Certain Corrosion-Resistant Steel Products From the Republic of Korea: Preliminary Results and Recission, In Part, of Countervailing Duty Administrative Review; 2024")
        self.assertEqual(t["kind"], "상계관세")
        self.assertEqual({k: (v["rate"], v["via"]) for k, v in t["rates"].items()},
                         {"현대제철": (0.58, "표"), "KG스틸": (4.82, "표"), "포스코": (2.22, "비선정"), "세아제강": (2.22, "비선정")})
        self.assertEqual(t["othersRate"], 2.22)
        t = w.rate_table(CORE_AD_PRELIM, CORE_AD_TITLE)
        self.assertEqual((t["kind"], t["rates"]["KG스틸"]["rate"], t["rates"]["동국씨엠"]["rate"], t["othersRate"]), ("반덤핑", 23.40, 19.43, 20.58))
        self.assertEqual((t["rates"]["현대제철"]["via"], t["rates"]["포스코"]["rate"], t["rates"]["세아제강"]["rate"]), ("비선정", 20.58, 20.58))
        self.assertNotIn("동국제강", t["rates"])   # 부록 III(재심 취소·대상 거래 없음)는 세율을 받지 않는다
        lp = w.rate_table(LINE_PIPE, "Welded Line Pipe From the Republic of Korea: Notice of Court Decision Not in Harmony With the Less-Than-Fair-Value Amended Final Determination")
        self.assertEqual((lp["rates"]["세아제강"]["rate"], lp["othersRate"]), (4.55, 5.39))   # 본문이 정한 줄임말 'SeAH'
        self.assertEqual(w.aliases("HD Hyundai Electric Co., Ltd. (Hyundai) and Iljin Electric Co., Ltd. (Iljin)"), {"Hyundai": "HD현대일렉트릭", "Iljin": "일진전기(관련)"})
        self.assertEqual(w.aliases("Commerce selected Hyundai Steel and Dongbu Incheon Steel Co., Ltd. (Dongbu Incheon)"), {})   # 괄호 앞이 다른 회사
        f = w.rate_table(CORE_AD_FINAL, "… Final Results and Rescission, in Part, of Antidumping Duty Administrative Review; 2023-2024")
        self.assertEqual(sorted(f["rates"]), sorted(["동국씨엠", "동국제강", "현대제철", "KG스틸", "포스코", "세아제강"]))
        self.assertEqual(f["rates"]["포스코"]["name"], "POSCO")   # POSCO International 줄이 아니라 POSCO 줄
        self.assertEqual(f["rows"], 10)
        lpt = w.rate_table(LPT, "Large Power Transformers From the Republic of Korea: Final Results of Antidumping Duty Administrative Review; 2023-2024")
        self.assertEqual({k: v["rate"] for k, v in lpt["rates"].items()},
                         {"HD현대일렉트릭": 0.0, "LS일렉트릭": 4.32, "효성중공업(관련)": 4.32, "일진전기(관련)": 0.0})
        self.assertIsNone(w.rate_table("no table here\nCommerce ... determines", CORE_AD_TITLE))
        # 두 줄로 나뉜 이름
        rows = w.rate_rows("----------------------------------------\nHyundai Steel Company and Hyundai\nSteel Pipe Co., Ltd. ............ 1.23\n"
                           "[[Page 27253]]\nSeAH Steel Corporation........ 9.80\n----------------------------------------\nDisclosure\nCommerce intends\n")
        self.assertEqual(rows, [("Hyundai Steel Company and Hyundai Steel Pipe Co., Ltd", 1.23), ("SeAH Steel Corporation", 9.8)])

    def fr_get(self, docket_docs, bodies, calls):
        def get(url, params=None, headers=None, timeout=None):
            calls.append((url, dict(params or [])))
            if url == w.FR_API:
                p = dict(params or [])
                if "conditions[docket_id]" in p:
                    return R(body={"results": docket_docs.get(p["conditions[docket_id]"], [])})
                return R(body={"results": [{"title": CORE_AD_TITLE, "publication_date": "2026-10-08", "html_url": "https://www.federalregister.gov/d/2026-20698",
                                            "document_number": "2026-20698", "agencies": [{"name": "International Trade Administration"}],
                                            "raw_text_url": "https://www.federalregister.gov/full_text/2026-20698.txt", "docket_ids": ["A-580-878"]}]})
            if "full_text" in url:
                return R(text=bodies.get(url.rsplit("/", 1)[1].replace(".txt", ""), "<pre>nothing</pre>"))
            return R(404)
        return get

    def test_prelim_compared_with_last_final_of_the_same_docket(self):
        docs = {"A-580-878": [
            {"title": CORE_AD_TITLE, "publication_date": "2026-10-08", "document_number": "2026-20698", "raw_text_url": "https://x/full_text/2026-20698.txt"},
            {"title": "Certain Corrosion-Resistant Steel Products From the Republic of Korea: Final Results and Rescission, in Part, of Antidumping Duty Administrative Review; 2023-2024",
             "publication_date": "2026-05-14", "document_number": "2026-09691", "html_url": "https://www.federalregister.gov/d/2026-09691", "raw_text_url": "https://x/full_text/2026-09691.txt"},
            {"title": "Certain Corrosion-Resistant Steel Products from the Republic of Korea: Initiation of Circumvention Inquiry on the Antidumping and Countervailing Duty Orders",
             "publication_date": "2026-04-02", "document_number": "2026-06449", "raw_text_url": "https://x/full_text/2026-06449.txt"},
            {"title": "Certain Corrosion-Resistant Steel Products From the Republic of Korea: Preliminary Results of Antidumping Duty Administrative Review; 2023-2024",
             "publication_date": "2026-01-08", "document_number": "2026-00191", "raw_text_url": "https://x/full_text/2026-00191.txt"}]}
        bodies = {"2026-20698": CORE_AD_PRELIM, "2026-09691": CORE_AD_FINAL}
        calls = []
        rows, err, read = w.federal_register(NOW, None, get=self.fr_get(docs, bodies, calls), sleep=lambda s: None)
        row = rows[0]
        self.assertEqual((err, row["dockets"]), (None, ["A-580-878"]))
        self.assertEqual(row["prior"]["final"]["id"], "fr:2026-09691")
        self.assertNotIn("prelim", row["prior"])   # 최종을 먼저 찾으면 그 앞 예비는 읽지 않는다
        self.assertEqual(sorted((c["company"], c["rate"], c["before"]) for c in row["rateChange"]),
                         [("KG스틸", 23.4, 0.0), ("동국씨엠", 19.43, 0.0), ("세아제강", 20.58, 0.0), ("포스코", 20.58, 0.0), ("현대제철", 20.58, 0.0)])
        self.assertFalse(any("2026-06449" in u or "2026-00191" in u for u, _ in calls))   # 우회 조사·더 오래된 예비는 읽지 않음
        n = len(calls)
        again, _, read2 = w.federal_register(NOW, {"federalRegister": rows}, get=self.fr_get(docs, bodies, calls), sleep=lambda s: None)
        self.assertEqual((read2, len(calls) - n), (0, 1))   # 목록 조회 한 번뿐 — 본문·직전 판정은 저장본
        self.assertEqual(again[0]["rateChange"], row["rateChange"])
        again[0]["rateTable"].pop("v")   # 예전 규칙으로 저장된 세율은 다시 읽는다(직전 판정도)
        third, _, read3 = w.federal_register(NOW, {"federalRegister": again}, get=self.fr_get(docs, bodies, calls), sleep=lambda s: None)
        self.assertEqual((read3, third[0]["rateTable"]["v"], third[0]["prior"]["final"]["id"]), (1, w.RATE_RULES, "fr:2026-09691"))

    def test_same_rates_as_last_final_is_no_change_and_sunset_is_not_compared(self):
        row = {"id": "fr:2026-22343", "date": "2026-11-02", "title": "Large Power Transformers From the Republic of Korea: Preliminary Results of Antidumping Duty Administrative Review; 2024-2025",
               "rateTable": w.rate_table(LPT, "… Antidumping …"),
               "prior": {"final": {"rates": {"HD현대일렉트릭": 0.0, "일진전기(관련)": 0.0, "LS일렉트릭": 4.32, "효성중공업(관련)": 4.32}, "othersRate": None}}}
        self.assertEqual(w.rate_change(row), [])
        row["prior"]["final"]["rates"]["LS일렉트릭"] = 0.0
        self.assertEqual(w.rate_change(row), [])   # 0→4.32는 5%p도, 5% 이상도 아님
        row["rateTable"]["rates"]["LS일렉트릭"]["rate"] = 6.1
        self.assertEqual(w.rate_change(row), [("LS일렉트릭", 6.1, 0.0)])
        row["title"] = "Passenger Vehicle and Light Truck Tires From the Republic of Korea: Final Results of the Expedited First Sunset Reviews of the Antidumping Duty Orders"
        self.assertEqual(w.rate_change(row), [])
        inv = {"title": "Certain Steel Wire From the Republic of Korea: Affirmative Preliminary Determination of Sales at Less-Than-Fair-Value",
               "rateTable": {"rates": {"고려아연": {"rate": 31.0, "via": "표"}, "포스코": {"rate": 2.0, "via": "표"}}}, "prior": {"none": True}}
        self.assertEqual(w.rate_change(inv), [("고려아연", 31.0, None)])   # 새 조사: 처음 매긴 5% 이상
