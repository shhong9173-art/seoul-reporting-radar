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
