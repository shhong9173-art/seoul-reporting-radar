"""해외 발주처 낙찰 감시: TED 낙찰자 필드, 영국 FTS 공급사, 세계은행 'Awarded Bidder' 칸만, 바레인 월간 보고서, 기준선·새 항목·실패 보존."""
import datetime as dt
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import overseas_award_watch as w  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 10, 29, 17, 30, tzinfo=KST)


class Resp:
    def __init__(self, body=None, status=200, text=None, content=None):
        self._body, self.status_code = body, status
        self.text = text if text is not None else json.dumps(body or {})
        self.content = content if content is not None else self.text.encode()

    def json(self):
        return self._body


TED_HYOSUNG = {"publication-number": "545946-2026", "publication-date": "2026-08-06+02:00", "notice-type": "can-standard",
               "buyer-name": {"eng": ["Energinet Eltransmission A/S"]}, "buyer-country": ["DNK"],
               "winner-name": {"eng": ["Hyosung Heavy Industires Corporation"]}, "winner-country": ["KOR"], "winner-identifier": ["578-87-00896"],
               "title-lot": {"eng": ["400/220 kV Autotransformers for SLF02"]}, "result-value-notice": "15923696", "result-value-cur-notice": "EUR",
               "contract-conclusion-date": ["2026-06-19Z"]}
TED_FRAMEWORK = {"publication-number": "558812-2026", "publication-date": "2026-08-12+02:00", "notice-type": "can-standard",
                 "buyer-name": {"eng": ["Ellevio AB"]}, "buyer-country": ["SWE"], "winner-name": {"eng": ["HD Hyundai Electric Co., Ltd."]},
                 "winner-country": ["KOR"], "total-value": 1, "total-value-cur": ["SEK"]}
TED_SUBSIDIARY = {"publication-number": "546637-2026", "publication-date": "2026-08-06+02:00", "notice-type": "can-modif",
                  "buyer-name": {"eng": ["Energinet Eltransmission A/S"]}, "buyer-country": ["DNK"],
                  "winner-name": {"eng": ["HD Hyundai Electric Europe GmbH"]}, "winner-country": ["DEU"], "total-value": 31169665, "total-value-cur": ["EUR"]}
TED_OTHER_KR = {"publication-number": "721359-2026", "publication-date": "2026-10-20+02:00", "notice-type": "can-standard",
                "buyer-name": {"pol": ["Enea Elektrownia Połaniec sp. z o.o."]}, "buyer-country": ["POL"],
                "winner-name": {"pol": ["Nano Co., Ltd."]}, "winner-country": ["KOR"]}
TED_NOT_KR = {"publication-number": "65790-2026", "publication-date": "2026-01-29+01:00", "notice-type": "can-standard",
              "buyer-name": {"spa": ["REE"]}, "winner-name": {"spa": ["EFACEC Energia"]}, "winner-country": ["PRT"]}

WB_AWARD = {"id": "OP00477000", "noticedate": "20-Oct-2026", "notice_type": "Contract Award", "project_ctry_name": "Iraq",
            "project_name": "Electricity Sector Reconnection", "bid_description": "Supply of 400 kV power transformers",
            "notice_text": ("<p>Duration of Contract: 12 Month(s)</p><p>Awarded Bidder(s): HYOSUNG HEAVY INDUSTRIES CORPORATION (496851) 119, Mapo-daero, "
                            "Mapo-gu, Seoul, Korea Country: Korea, Republic of Bid Price at Opening USD 38,500,000.00 Evaluated Bid Price USD 38,410,000.00</p>"
                            "<p>Evaluated Bidder(s): SIEMENS ENERGY (12345) Country: Germany</p>")}
WB_REJECTED = {"id": "OP00305046", "noticedate": "18-Oct-2026", "notice_type": "Contract Award", "project_ctry_name": "Ukraine",
               "project_name": "Winterization", "bid_description": "Autotransformers 330 kV",
               "notice_text": ("<p>Awarded Bidder(s): KYIV ENERGY CONSTRUCTION COMPANY (776840) Country: Ukraine Bid Price at Opening UAH 1,000,000.00</p>"
                               "<p>Rejected Bidder(s): Reason for Rejection Non Responsive HYOSUNG HEAVY INDUSTRIES CORPORATION (496851) Country: Korea, Republic of</p>")}
WB_OLD = dict(WB_AWARD, id="OP00100000", noticedate="03-Nov-2022")

FTS_REL = {"id": "102400-2026", "ocid": "ocds-h6vhtk-0aaaaa", "date": "2026-10-28T10:00:00Z", "tag": ["award", "contract"],
           "buyer": {"id": "GB-NG", "name": "National Grid Electricity Transmission plc"},
           "tender": {"title": "HVDC cable supply - Eastern Green Link 3"},
           "parties": [{"id": "GB-NG", "name": "National Grid Electricity Transmission plc", "roles": ["buyer"], "address": {"countryName": "United Kingdom"}},
                       {"id": "S1", "name": "LS CABLE & SYSTEM UK LIMITED", "roles": ["supplier"], "address": {"countryName": "United Kingdom"}},
                       {"id": "S2", "name": "Some Korean Engineering Co", "roles": ["supplier"], "address": {"countryName": "Korea, Republic of"}}],
           "awards": [{"id": "102400-2026-1", "suppliers": [{"id": "S1", "name": "LS CABLE & SYSTEM UK LIMITED"}], "value": {"amount": 250000000, "currency": "GBP"}}]}
FTS_UK_ONLY = {"id": "102401-2026", "date": "2026-10-28T11:00:00Z", "tender": {"title": "Software"}, "parties": [
    {"id": "X", "name": "Acme Ltd", "roles": ["supplier"], "address": {"countryName": "United Kingdom"}}], "awards": []}

BH_HTML = ('<table><tr><th>No</th><th>Subject</th></tr>'
           '<tr><td>1</td><td>Awarded Tenders Report - September 2026</td><td><a href="/MediaHandler/GenericHandler/Pdf/Awarded/Awarded Tenders 2026-09.pdf">PDF</a></td></tr>'
           '<tr><td>2</td><td>Awarded Tenders Report - August 2026</td><td><a href="/MediaHandler/GenericHandler/Pdf/Awarded/Awarded Tenders 2026-08.pdf">PDF</a></td></tr></table>')


def fakes(ted_rows=(TED_HYOSUNG, TED_FRAMEWORK, TED_SUBSIDIARY, TED_OTHER_KR, TED_NOT_KR), wb_rows=(WB_AWARD, WB_REJECTED, WB_OLD),
          fts_rels=(FTS_REL, FTS_UK_ONLY), bh_text="Tender 12/2026 EWA 400kV transformers HYOSUNG HEAVY INDUSTRIES BHD 4,200,000"):
    calls = {"ted": 0, "wb": 0, "fts": 0, "bh_pdf": 0}

    def post(url, json=None, headers=None, timeout=None):
        calls["ted"] += 1
        return Resp({"notices": list(ted_rows), "totalNoticeCount": len(ted_rows)})

    def get(url, params=None, headers=None, timeout=None):
        if url.startswith(w.WB_API):
            calls["wb"] += 1
            return Resp({"procnotices": list(wb_rows), "total": len(wb_rows)})
        if url.startswith(w.FTS_API):
            calls["fts"] += 1
            return Resp({"releases": list(fts_rels), "links": {}})
        if url == w.BH_LIST:
            return Resp(text=BH_HTML)
        if url.endswith(".pdf"):
            calls["bh_pdf"] += 1
            return Resp(text="", content=b"%PDF")
        raise AssertionError(url)
    return get, post, calls


class Award(unittest.TestCase):
    def setUp(self):
        self._pdf = w.pdf_text
        w.pdf_text = lambda raw: ("Awarded Tenders\nTender 12/2026 EWA 400kV transformers\nHYOSUNG HEAVY INDUSTRIES BHD 4,200,000\n"
                                  + "\n".join(f"Tender {i}/2026 Ministry of Works road maintenance ALMOAYYED W.L.L. BHD {i}00" for i in range(30)))

    def tearDown(self):
        w.pdf_text = self._pdf

    def test_ted_winner_fields_only(self):
        items = {x["id"]: x for x in w.ted_items([TED_HYOSUNG, TED_FRAMEWORK, TED_SUBSIDIARY, TED_OTHER_KR, TED_NOT_KR])}
        self.assertEqual(set(items), {"ted:545946-2026", "ted:558812-2026", "ted:546637-2026", "ted:721359-2026"})
        h = items["ted:545946-2026"]
        self.assertEqual((h["company"], h["value"], h["currency"], h["concluded"], h["buyerCountry"]), ("효성중공업", 15923696.0, "EUR", "2026-06-19", "DNK"))
        self.assertEqual(h["winnerIds"], ["578-87-00896"])
        self.assertIsNone(items["ted:558812-2026"]["value"])  # framework placeholder 1
        self.assertEqual(items["ted:546637-2026"]["kind"], "계약 변경")
        self.assertEqual(items["ted:546637-2026"]["company"], "HD현대일렉트릭")
        self.assertIsNone(items["ted:721359-2026"]["company"])  # Korean but not a beat company

    def test_names_tiers_and_scanned_pdf(self):
        self.assertEqual(w.beat_of("DE_POONGSAN CORPORATION"), "풍산")
        self.assertIsNone(w.beat_of("Hanwha Aerospace Co., Ltd."))  # 방산은 출입처 밖
        local = dict(TED_HYOSUNG, **{"publication-number": "700001-2026", "winner-name": {"ces": ["Hyundai Motor Czech s.r.o."]}, "winner-country": ["CZE"]})
        hq = dict(TED_HYOSUNG, **{"publication-number": "700002-2026", "winner-name": {"eng": ["Hyundai Motor Company"]}, "winner-country": ["KOR"]})
        got = {x["id"]: w.tier_of(x) for x in w.ted_items([local, hq])}
        self.assertEqual(got, {"ted:700001-2026": "B", "ted:700002-2026": "A"})
        w.pdf_text = lambda raw: "   "
        get, post, _ = fakes()
        doc = w.run(now=NOW, previous=None, get=get, post=post, sleep=lambda s: None)
        bh = [c for c in doc["checks"] if c["source"] == "바레인 입찰위원회"]
        self.assertEqual((bh[0]["status"], bh[0]["matched"]), ("ok", None))
        self.assertIn("스캔 이미지", bh[0]["note"])
        self.assertIn("/MediaHandler/GenericHandler/Pdf/Awarded/Awarded Tenders 2026-09.pdf", doc["bahrainSeen"])  # not retried

    def test_world_bank_older_layout_without_vendor_number(self):
        old = dict(WB_AWARD, id="OP00999", notice_text="Awarded Bidder(s): LS CABLE & SYSTEM LTD Country: Korea, Republic of Signed Contract Price USD 12,000,000.00")
        x = w.wb_items([old], "2026-07-01")[0]
        self.assertEqual((x["company"], x["winners"], x["value"]), ("LS전선", ["LS CABLE & SYSTEM LTD"], 12000000.0))

    def test_world_bank_awarded_block_only(self):
        got = {x["id"]: x for x in w.wb_items([WB_AWARD, WB_REJECTED, WB_OLD], "2026-07-01")}
        self.assertEqual(set(got), {"wb:OP00477000"})  # rejected Hyosung and the 2022 notice are dropped
        x = got["wb:OP00477000"]
        self.assertEqual((x["company"], x["buyerCountry"], x["currency"], x["value"]), ("효성중공업", "Iraq", "USD", 38410000.0))
        self.assertEqual(x["winners"], ["HYOSUNG HEAVY INDUSTRIES CORPORATION"])

    def test_fts_supplier_names_and_korean_address(self):
        got = w.fts_items([FTS_REL, FTS_UK_ONLY])
        self.assertEqual(len(got), 1)
        x = got[0]
        self.assertEqual(x["company"], "LS전선")
        self.assertIn("Some Korean Engineering Co", x["winners"])
        self.assertEqual((x["value"], x["currency"], x["url"]), (250000000.0, "GBP", "https://www.find-tender.service.gov.uk/Notice/102400-2026"))

    def test_baseline_then_new(self):
        get, post, calls = fakes()
        first = w.run(now=NOW, previous=None, get=get, post=post, sleep=lambda s: None)
        self.assertEqual(first["status"], "complete")
        self.assertTrue(all(x["baseline"] and not x["isNew"] for x in first["items"]))
        self.assertEqual(first["windowStart"], (NOW - dt.timedelta(days=w.BASELINE_DAYS)).date().isoformat())
        self.assertEqual(calls["bh_pdf"], 1)  # first run reads only the newest monthly report
        bh = [x for x in first["items"] if x["source"] == "바레인 입찰위원회"]
        self.assertEqual((len(bh), bh[0]["company"], bh[0]["tier"]), (1, "효성중공업", "B"))
        tiers = {x["id"]: x["tier"] for x in first["items"]}
        self.assertEqual((tiers["ted:545946-2026"], tiers["ted:546637-2026"], tiers["ted:721359-2026"]), ("A", "B", "C"))

        new_ted = dict(TED_HYOSUNG, **{"publication-number": "800001-2026", "publication-date": "2026-10-29+01:00"})
        get2, post2, calls2 = fakes(ted_rows=(TED_HYOSUNG, new_ted))
        second = w.run(now=NOW + dt.timedelta(days=1), previous=first, get=get2, post=post2, sleep=lambda s: None)
        new = [x for x in second["items"] if x["isNew"]]
        self.assertEqual([x["id"] for x in new], ["ted:800001-2026"])
        self.assertEqual(second["windowStart"], (NOW - dt.timedelta(days=w.OVERLAP_DAYS)).date().isoformat())
        self.assertEqual(calls2["bh_pdf"], 0)  # both monthly reports already read or remembered
        old = next(x for x in second["items"] if x["id"] == "ted:545946-2026")
        self.assertEqual(old["firstSeen"], NOW.isoformat(timespec="seconds"))

    def test_failures_are_not_zero_and_keep_items(self):
        get, post, _ = fakes()
        first = w.run(now=NOW, previous=None, get=get, post=post, sleep=lambda s: None)

        def bad(*a, **kw):
            return Resp({}, status=503)
        doc = w.run(now=NOW + dt.timedelta(days=1), previous=first, get=bad, post=bad, sleep=lambda s: None)
        self.assertEqual(doc["status"], "failed")
        self.assertEqual(len(doc["items"]), len(first["items"]))
        self.assertTrue(all(c["status"] == "failed" for c in doc["checks"]))
        self.assertEqual(doc["lastSuccess"], first["lastSuccess"])

    def test_ted_429_waits_once(self):
        state = {"n": 0}
        waits = []

        def post(url, json=None, headers=None, timeout=None):
            state["n"] += 1
            return Resp({}, status=429) if state["n"] == 1 else Resp({"notices": [TED_HYOSUNG], "totalNoticeCount": 1})
        rows, total = w.ted_search("q", post=post, sleep=waits.append)
        self.assertEqual((len(rows), total, waits), (1, 1, [15]))


if __name__ == "__main__":
    unittest.main()
