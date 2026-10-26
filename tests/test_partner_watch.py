"""Partner filings: ASX (two JSON shapes) and EDGAR hits, own filings dropped, failures recorded, snippets budgeted."""
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import partner_watch as w  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 10, 27, 7, 0, tzinfo=KST)
CFG = {"asx": [{"code": "ARU", "name": "Arafura Rare Earths", "beat": ["현대차", "기아"], "relation": "NdPr 공급계약",
                "evidence": "https://example/aru"}],
       "edgarPhrases": [["현대제철", "Hyundai Steel"], ["포스코", "POSCO"]]}


class R:
    def __init__(self, code=200, body=None, text=""):
        self.status_code, self.body, self.text = code, body, text

    def json(self):
        if self.body is None:
            raise ValueError
        return self.body


MARKIT = {"data": {"items": [
    {"date": "2026-10-20T08:00:00", "headline": "Offtake update - amendment to binding agreement", "documentKey": "abc", "isPriceSensitive": True},
    {"date": "2026-10-10T08:00:00", "headline": "Quarterly Activities Report", "documentKey": "def", "isPriceSensitive": False},
    {"date": "2026-08-01T08:00:00", "headline": "Old news", "documentKey": "ghi"}]}}
EFTS_STEEL = {"hits": {"hits": [
    {"_id": "0001193125-26-111111:d111d8k.htm", "_source": {"ciks": ["0001234567"], "display_names": ["Acme Metals Inc  (ACME)  (CIK 0001234567)"],
                                                            "form": "8-K", "file_date": "2026-10-21", "adsh": "0001193125-26-111111", "file_description": "Current report"}}]}}
EFTS_POSCO = {"hits": {"hits": [
    {"_id": "0001104659-26-222222:tm6k.htm", "_source": {"ciks": ["0000889132"], "display_names": ["POSCO Holdings Inc.  (PKX)  (CIK 0000889132)"],
                                                         "form": "6-K", "file_date": "2026-10-22", "adsh": "0001104659-26-222222"}}]}}


def fake(calls):
    def get(url, params=None, headers=None, timeout=None):
        calls.append((url, params, headers))
        if "markitdigital" in url:
            return R(200, MARKIT)
        if "efts.sec.gov" in url:
            return R(200, EFTS_STEEL if params["q"] == '"Hyundai Steel"' else EFTS_POSCO)
        if "sec.gov/Archives" in url:
            return R(200, text="<html><body><p>The Company entered into a supply agreement with Hyundai Steel Company for slab.</p></body></html>")
        return R(404)
    return get


class Partners(unittest.TestCase):
    def test_asx_and_edgar(self):
        calls = []
        doc = w.run(CFG, now=NOW, get=fake(calls), sleep=lambda s: None)
        asx = [x for x in doc["items"] if x["source"] == "ASX"]
        self.assertEqual([x["date"] for x in asx], ["2026-10-20", "2026-10-10"])  # 30-day window
        self.assertIn("offtake", asx[0]["flags"])
        self.assertIn("amend", asx[0]["flags"])
        self.assertEqual(asx[0]["relationEvidence"], "https://example/aru")
        ed = [x for x in doc["items"] if x["source"] == "EDGAR"]
        self.assertEqual(len(ed), 1)  # POSCO's own 6-K dropped
        self.assertEqual(ed[0]["filer"], "Acme Metals Inc  (ACME)")
        self.assertEqual(ed[0]["url"], "https://www.sec.gov/Archives/edgar/data/1234567/000119312526111111/d111d8k.htm")
        self.assertIn("supply agreement with Hyundai Steel", ed[0]["snippet"])
        self.assertTrue(all(x["isNew"] for x in doc["items"]))
        efts = next(c for c in calls if "efts" in c[0])
        self.assertEqual(efts[1]["startdt"], "2026-09-27")
        self.assertIn("seoul-reporting-radar", efts[2]["User-Agent"])

    def test_legacy_asx_shape_and_failures_are_recorded(self):
        legacy = {"data": [{"document_release_date": "2026-10-25T10:00:00+1100", "header": "Binding offtake with Kia", "url": "https://www.asx.com.au/asxpdf/x.pdf",
                            "market_sensitive": True}]}
        def get(url, params=None, headers=None, timeout=None):
            if "markitdigital" in url:
                return R(403)
            if "asx.com.au" in url:
                return R(200, legacy)
            return R(503)
        doc = w.run(CFG, now=NOW, get=get, sleep=lambda s: None)
        asx_check = next(c for c in doc["checks"] if c["source"] == "ASX")
        self.assertEqual(asx_check["via"], "www.asx.com.au")
        self.assertEqual(doc["items"][0]["title"], "Binding offtake with Kia")
        self.assertIn("kia", doc["items"][0]["flags"])
        edgar_fail = [c for c in doc["checks"] if c["source"] == "EDGAR"]
        self.assertTrue(all(c["status"] == "failed" and c["error"] == "HTTP 503" for c in edgar_fail))
        self.assertEqual(doc["status"], "partial")

    def test_own_filing_filter_needs_the_whole_phrase(self):
        body = {"hits": {"hits": [{"_id": "a:b.htm", "_source": {"ciks": ["1"], "display_names": ["Wells Fargo & Co  (WFC)  (CIK 0000072971)"],
                                                                "form": "8-K", "file_date": "2026-10-20", "adsh": "a"}}]}}
        cfg = {"asx": [], "edgarPhrases": [["LS일렉트릭", "LS Electric"]]}
        doc = w.run(cfg, now=NOW, get=lambda url, params=None, headers=None, timeout=None: R(200, body) if "efts" in url else R(404),
                    sleep=lambda s: None)
        self.assertEqual(len(doc["items"]), 1)

    def test_building_name_only_mentions_are_dropped(self):
        body = {"hits": {"hits": [{"_id": "x-1:p.htm", "_source": {"ciks": ["1509646"], "display_names": ["Phoenix New Media Ltd  (FENG)  (CIK 0001509646)"],
                                                                  "form": "6-K", "file_date": "2026-10-20", "adsh": "x-1"}}]}}
        def get(url, params=None, headers=None, timeout=None):
            if "efts" in url:
                return R(200, body)
            return R(200, text="<p>Meeting at Floor 25, Tower B, POSCO Center, Beijing.</p>")
        doc = w.run({"asx": [], "edgarPhrases": [["포스코", "POSCO"]]}, now=NOW, get=get, sleep=lambda s: None)
        self.assertEqual(doc["items"], [])

    def test_saved_snippets_get_the_unrelated_check_too(self):
        prev = {"items": [{"id": "edgar:x-1:p.htm", "source": "EDGAR", "date": "2026-10-20", "firstSeen": "2026-10-20T07:00:00+09:00",
                           "phrases": ["POSCO"], "beat": ["포스코"], "snippet": "held at Floor 25, Tower B, POSCO Center, Beijing"},
                          {"id": "edgar:y-1:q.htm", "source": "EDGAR", "date": "2026-10-19", "firstSeen": "2026-10-19T07:00:00+09:00",
                           "phrases": ["POSCO"], "beat": ["포스코"], "snippet": "our Memorandum of Understanding with POSCO and"}]}
        doc = w.run({"asx": [], "edgarPhrases": []}, now=NOW, previous=prev, get=lambda *a, **k: R(404), sleep=lambda s: None)
        self.assertEqual([x["id"] for x in doc["items"]], ["edgar:y-1:q.htm"])

    def test_previous_items_keep_first_seen_and_expire(self):
        prev = {"items": [{"id": "edgar:0001193125-26-111111:d111d8k.htm", "source": "EDGAR", "date": "2026-10-21", "firstSeen": "2026-10-21T07:00:00+09:00",
                           "snippet": "kept", "beat": ["현대제철"], "phrases": ["Hyundai Steel"]},
                          {"id": "asx:OLD", "source": "ASX", "date": "2026-05-01", "firstSeen": "2026-05-01T07:00:00+09:00"}]}
        doc = w.run(CFG, now=NOW, previous=prev, get=fake([]), sleep=lambda s: None)
        ed = next(x for x in doc["items"] if x["source"] == "EDGAR")
        self.assertEqual(ed["firstSeen"], "2026-10-21T07:00:00+09:00")
        self.assertEqual(ed["snippet"], "kept")
        self.assertNotIn("asx:OLD", [x["id"] for x in doc["items"]])


if __name__ == "__main__":
    unittest.main()
