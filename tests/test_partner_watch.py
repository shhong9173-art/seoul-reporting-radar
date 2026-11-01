"""Partner filings: ASX (two JSON shapes) and EDGAR hits, own filings dropped, failures recorded, snippets budgeted."""
import datetime as dt
import json
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

    def test_phrase_added_later_reads_old_filings_as_baseline(self):
        # 11-01: 석유화학 6곳 문구를 더한 첫 실행에 지난 30일 공시가 '새 공시'로 뜨지 않게(미국 의견서와 같은 문제)
        prev = {"items": [], "checks": [{"source": "EDGAR", "target": "POSCO", "status": "ok"}]}
        later = NOW + dt.timedelta(days=3)   # 10-30: 10-21 공시는 7일 전
        doc = w.run(CFG, now=later, previous=prev, get=fake([]), sleep=lambda s: None)
        steel = next(x for x in doc["items"] if x["source"] == "EDGAR")
        self.assertEqual((steel["baseline"], steel["isNew"]), (True, False))   # 'Hyundai Steel'은 새 문구
        again = w.run(CFG, now=later + dt.timedelta(days=1), previous=doc, get=fake([]), sleep=lambda s: None)
        self.assertTrue(next(x for x in again["items"] if x["source"] == "EDGAR")["baseline"])
        known = {"items": [], "checks": [{"source": "EDGAR", "target": t, "status": "ok"} for t in ("POSCO", "Hyundai Steel")]}
        doc2 = w.run(CFG, now=later, previous=known, get=fake([]), sleep=lambda s: None)
        self.assertNotIn("baseline", next(x for x in doc2["items"] if x["source"] == "EDGAR"))   # 아는 문구로 잡힌 새 공시는 그대로

    def test_officer_biography_mention_is_routine(self):
        # 11-01 운영: Beyond Air DEF 14A 이사 경력 소개
        it = {"phrases": ["LG Chem"], "form": "DEF 14A", "snippet": (
            "He was the Chief Financial Officer of AVEO Oncology (Nasdaq: AVEO), a biopharmaceutical company focused on targeted "
            "medicines for oncology and other unmet medical needs, from 2020 to 2023, when it was acquired by LG Chem, and was the "
            "Chief Financial Officer of Valeritas Holdings, Inc.")}
        w.classify(it)
        self.assertIn("경력", it.get("routine", ""))
        # 'Inc.'·'Ltd.' 뒤에서 문장이 잘려도(11-01 Verastem 8-K) 경력 소개로 본다
        cut = {"phrases": ["LG Chem"], "form": "8-K", "snippet": (
            "Mr. Bailey served as president and chief executive officer of AVEO Pharmaceuticals, Inc. (\u201cAVEO\u201d), an LG Chem Ltd. "
            "company from January 2015 to June 2026, and has served as a member of its board of directors since January 2015.")}
        w.classify(cut)
        self.assertIn("경력", cut.get("routine", ""))
        deal = {"phrases": ["LG Chem"], "form": "8-K", "snippet": "The Company entered into a supply agreement with LG Chem, Ltd. for cathode materials."}
        w.classify(deal)
        self.assertNotIn("routine", deal)
        self.assertTrue(deal["dealNear"])

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

    def test_edgar_transient_error_retried_once(self):
        # 10-30 'OCI Holdings' 한 질의만 HTTP 500(앞뒤 실행 정상) — 5xx·연결 오류만 한 번 다시, 4xx는 그대로 실패
        body = {"hits": {"hits": []}}
        seen = {}

        def get(url, params=None, headers=None, timeout=None):
            q = (params or {}).get("q", "")
            seen[q] = seen.get(q, 0) + 1
            if q == '"Hyundai Steel"' and seen[q] == 1:
                return R(500)
            if q == '"POSCO"':
                return R(429)
            return R(200, body)
        waits = []
        doc = w.run({"asx": [], "edgarPhrases": CFG["edgarPhrases"]}, now=NOW, get=get, sleep=waits.append)
        st = {c["target"]: c["status"] for c in doc["checks"] if c["source"] == "EDGAR"}
        self.assertEqual(st, {"Hyundai Steel": "ok", "POSCO": "failed"})
        self.assertEqual((seen['"Hyundai Steel"'], seen['"POSCO"']), (2, 1))
        self.assertIn(5.0, waits)
        self.assertTrue(w.transient("HTTP 502") and w.transient("ConnectionError") and not w.transient("HTTP 404") and not w.transient("JSON 아님"))

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

    def test_seah_surname_is_not_seah_steel(self):
        # 10-29 Global Engine Group 20-F: 'Seah'(사람 성씨)만 있어 세아로 잡혔다 — 'SeAH'만 세아
        body = {"hits": {"hits": [{"_id": "g-1:ex4.htm", "_source": {"ciks": ["1908705"], "display_names": ["Global Engine Group Holding Ltd  (GLE)  (CIK 0001908705)"],
                                                                    "form": "20-F", "file_date": "2026-10-29", "adsh": "g-1"}}]}}
        def get(url, params=None, headers=None, timeout=None):
            if "efts" in url:
                return R(200, body)
            return R(200, text="<p>Signed by Mr. Seah Kok Wah, Director, and SEAH Holdings Sdn Bhd.</p>")
        doc = w.run({"asx": [], "edgarPhrases": [["세아", "SeAH"]]}, now=NOW, get=get, sleep=lambda s: None)
        self.assertEqual(doc["items"], [])
        def get2(url, params=None, headers=None, timeout=None):
            if "efts" in url:
                return R(200, body)
            return R(200, text="<p>Mr. Seah Kok Wah signed a supply agreement with SeAH Steel Corporation for API pipes.</p>")
        doc = w.run({"asx": [], "edgarPhrases": [["세아", "SeAH"]]}, now=NOW, get=get2, sleep=lambda s: None)
        self.assertIn("SeAH Steel Corporation", doc["items"][0]["snippet"])
        prev = {"items": [{"id": "edgar:g-1:ex4.htm", "source": "EDGAR", "date": "2026-10-29", "firstSeen": "2026-10-29T07:00:00+09:00",
                           "phrases": ["SeAH"], "beat": ["세아"], "snippet": "agreement signed by Seah Kok Wah, director"}]}
        doc = w.run({"asx": [], "edgarPhrases": []}, now=NOW, previous=prev, get=lambda *a, **k: R(404), sleep=lambda s: None)
        self.assertEqual(doc["items"], [])  # 저장된 발췌도 같은 기준

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


class EdgarNoise(unittest.TestCase):
    HARTFORD = ("Basic industry 1,198 1,151 1.8 % Transportation 907 844 1.3 % Other 617 610 0.9 % Total $ 25,618 $ 24,052 37.2 % "
                "Top Ten Exposures by Issuer [1] TPG Partners X $ 309 $ 308 0.5 % Goldman Sachs Group Inc. 196 178 0.3 % "
                "Hyundai Motor Company 182 178 0.3 % Duke Energy Corporation 183 175 0.3 %")
    KT = ("to provide financial support as an operating investor during the operating period with respect to K Defense Co., Ltd. "
          "(12) The Company has an agreement related to a stock sale contract with HYUNDAI MOBIS Co., Ltd. and HYUNDAI MOTOR COMPANY. "
          "If the Company intends to dispose of the acquired stocks to a third party")
    DEAL = "On October 20, 2026 the Company entered into a binding supply agreement with Hyundai Motor Company for battery cells."

    def item(self, iid, date, snippet, filer="Filer", form="8-K", url="https://www.sec.gov/Archives/edgar/data/1/x/d.htm"):
        return {"id": iid, "source": "EDGAR", "date": date, "firstSeen": date + "T07:00:00+09:00", "filer": filer, "form": form,
                "url": url, "phrases": ["Hyundai Motor Company"], "beat": ["현대차"], "snippet": snippet}

    def run_with(self, items, previous_extra=None):
        prev = {"items": items, **(previous_extra or {})}
        return w.run({"asx": [], "edgarPhrases": []}, now=NOW, previous=prev, get=lambda *a, **k: R(404), sleep=lambda s: None)

    def test_holdings_table_is_routine_and_deal_text_is_not(self):
        doc = self.run_with([self.item("edgar:a-1:ex992.htm", "2026-10-26", self.HARTFORD, filer="HARTFORD INSURANCE GROUP"),
                             self.item("edgar:b-1:d8k.htm", "2026-10-21", self.DEAL, filer="Cell Maker Inc")])
        by = {x["id"]: x for x in doc["items"]}
        self.assertIn("투자 보유", by["edgar:a-1:ex992.htm"]["routine"])
        self.assertNotIn("routine", by["edgar:b-1:d8k.htm"])
        self.assertNotIn("finNote", by["edgar:b-1:d8k.htm"])

    def test_deal_word_must_share_a_sentence_with_the_beat_name(self):
        # 운영 10-29 Nexa Resources 3분기 6-K: 계약 낱말은 제3자 공급사 일반 서술, 고려아연은 업계 기준가 보도 인용 문장에만
        nexa = ("For internal transfers between mining and smelting segments, we apply our internal benchmark treatment charge (TC). "
                "For third-party suppliers, TCs are based on the annual benchmark TC, spot TCs, or annually negotiated contracts. "
                "The 2026 benchmark TC, reportedly agreed between Korea Zinc and Teck Resources in March 2026, was set at US$85/t of "
                "concentrate, up 6% from US$80/t in 2025.")
        it = self.item("edgar:n-1:ex99-1.htm", "2026-10-29", nexa, filer="Nexa Resources S.A. (NEXA)", form="6-K")
        it["phrases"], it["beat"] = ["Korea Zinc"], ["고려아연"]
        doc = self.run_with([it, self.item("edgar:b-1:d8k.htm", "2026-10-21", self.DEAL, filer="Cell Maker Inc")])
        by = {x["id"]: x for x in doc["items"]}
        self.assertIs(by["edgar:n-1:ex99-1.htm"]["dealNear"], False)
        self.assertIn("보도 인용", by["edgar:n-1:ex99-1.htm"]["hearsay"])
        self.assertIs(by["edgar:b-1:d8k.htm"]["dealNear"], True)
        self.assertNotIn("hearsay", by["edgar:b-1:d8k.htm"])
        # 전망·위험 고지 문구 속 언급(10-31 운영 Cleveland-Cliffs 8-K EX-99.1 발췌 그대로)
        clf = ("…ign currency rates and tax laws; risks and uncertainties related to our ability to realize the anticipated synergies or other "
               "expected benefits of any acquisitions, including the acquisition of Stelco, any potential transaction arising out of our "
               "Memorandum of Understanding with POSCO and completing any proposed asset divestiture transactions; challenges to successfully "
               "implementing our business s…")
        c = self.item("edgar:clf-1:ex991.htm", "2026-10-19", clf, filer="CLEVELAND-CLIFFS INC. (CLF)", form="8-K")
        c["phrases"], c["beat"] = ["POSCO"], ["포스코"]
        got = {x["id"]: x for x in self.run_with([c, self.item("edgar:b-1:d8k.htm", "2026-10-21", self.DEAL, filer="Cell Maker Inc")])["items"]}
        self.assertIn("전망·위험 고지", got["edgar:clf-1:ex991.htm"]["boilerplate"])
        self.assertNotIn("boilerplate", got["edgar:b-1:d8k.htm"])
        # 정기 보고서 앞머리 용어·약어 풀이(10-31 운영 Cleveland-Cliffs 10-Q 발췌 그대로)
        gl = ("…steel IAM International Association of Machinists and Aerospace Workers Long ton (lt) 2,240 pounds Metric ton (mt) 2,205 pounds "
              "MMBtu Million British Thermal Units Net ton (nt) 2,000 pounds NOES Non-oriented electrical steel N/M Not meaningful OPEB Other "
              "postretirement benefits POSCO POSCO Holdings Inc., a publicly traded South Korean steel manufacturer headquartered in Pohang, "
              "South Korea RCRA Re…")
        g = self.item("edgar:clf-2:10q.htm", "2026-10-20", gl, filer="CLEVELAND-CLIFFS INC. (CLF)", form="10-Q")
        g["phrases"], g["beat"] = ["POSCO"], ["포스코"]
        got = {x["id"]: x for x in self.run_with([g, self.item("edgar:b-1:d8k.htm", "2026-10-21", self.DEAL, filer="Cell Maker Inc")])["items"]}
        self.assertIn("용어·약어 풀이나 이름 나열", got["edgar:clf-2:10q.htm"]["routine"])
        # 공급사 이름 나열 표(10-13 VME Companies S-1 EXHIBIT 10.5)도 문장 없는 나열
        vme = ("…g and Fittings Type of Supply Supplier SDSS Piping & Fittings Europe, Singapore GRE Piping & Fittings NOV Amerstrand Malaysia, "
               "Future Pipe Indonesia/Dubai HDPE, PVC, PVDF George Fisher FRP Piping & Fittings Yunku FRP Alloy/CS Pipe Benteler, Kobe Steel, "
               "Kobelco, NSSMC, Outokumpu, Posco, Seah, Schoeller Bleckmann, Tubacex, Tubos Reuni dos, Vallourec_Brazil/Europe, Zhejiang Jiuli, AMSA, Anhui, APC, A…")
        v = self.item("edgar:vme-1:ex10-5.htm", "2026-10-13", vme, filer="VME Companies, Inc.", form="S-1/A")
        v["phrases"], v["beat"] = ["Posco", "Seah"], ["포스코", "세아"]
        self.assertIn("이름 나열", self.run_with([v])["items"][0]["routine"])
        self.assertNotIn("routine", got["edgar:b-1:d8k.htm"])
        # 발췌에 이름이 안 보이면(잘림) 판단하지 않는다
        cut = self.item("edgar:c-1:x.htm", "2026-10-21", "The Company entered into a supply agreement for cells with a customer in Asia.")
        self.assertNotIn("dealNear", self.run_with([cut])["items"][0])

    def test_financial_statement_note_is_flagged_not_hidden(self):
        doc = self.run_with([self.item("edgar:k-1:a2q26_seperatexreviewrep.htm", "2026-10-23", self.KT, filer="KT CORP", form="6-K/A")])
        it = doc["items"][0]
        self.assertIn("재무제표 주석", it["finNote"])
        self.assertNotIn("routine", it)

    def test_same_sentence_repeats_within_filing_and_across_filings(self):
        q1 = self.item("edgar:k-0:q1.htm", "2026-08-14", self.KT.replace("(12)", "(11)"), filer="KT CORP", form="6-K")
        ex1 = self.item("edgar:k-1:ex991.htm", "2026-10-23", self.KT, filer="KT CORP", form="6-K/A")
        ex2 = self.item("edgar:k-1:ex992.htm", "2026-10-23", self.KT, filer="KT CORP", form="6-K/A")
        doc = self.run_with([q1, ex1, ex2])
        by = {x["id"]: x for x in doc["items"]}
        self.assertNotIn("routine", by["edgar:k-0:q1.htm"])
        self.assertIn("이전 공시(2026-08-14)와 같은 문구", by["edgar:k-1:ex991.htm"]["routine"])
        self.assertEqual(by["edgar:k-1:ex991.htm"]["repeatOf"], "edgar:k-0:q1.htm")
        # Remembered after the earlier filing leaves the 120-day item store.
        later = self.run_with([ex1], previous_extra={"textSeen": doc["textSeen"]})
        self.assertIn("반복 기재", later["items"][0]["routine"])
        # Same sentence by a different filer is not a repeat.
        other = self.run_with([q1, self.item("edgar:z-1:x.htm", "2026-10-23", self.KT, filer="OTHER CORP")])
        self.assertNotIn("routine", {x["id"]: x for x in other["items"]}["edgar:z-1:x.htm"])

    def test_same_exhibits_in_one_filing(self):
        ex1 = self.item("edgar:k-1:ex991.htm", "2026-10-23", self.DEAL, filer="KT CORP")
        ex2 = self.item("edgar:k-1:ex992.htm", "2026-10-23", self.DEAL, filer="KT CORP")
        by = {x["id"]: x for x in self.run_with([ex1, ex2])["items"]}
        self.assertEqual(by["edgar:k-1:ex992.htm"]["routine"], "같은 제출의 다른 문서와 같은 문구")
        self.assertNotIn("routine", by["edgar:k-1:ex991.htm"])


if __name__ == "__main__":
    unittest.main()


# Row shape of HKEX titleSearchServlet on 2026-10-28 (probe): result is a JSON string.
HKEX_BODY = {"hasNextRow": False, "recordCnt": 3, "result": json.dumps([
    {"DATE_TIME": "21/10/2026 18:33", "TITLE": "MAJOR TRANSACTION - EXIT OF BAIC INVESTMENT FROM ITS INVESTMENT IN BHAF",
     "FILE_LINK": "/listedco/listconews/sehk/2026/1021/2026102100777.pdf", "NEWS_ID": "11906001", "LONG_TEXT": "Announcements and Notices - [Major Transaction]",
     "STOCK_CODE": "01958", "STOCK_NAME": "BAIC MOTOR"},
    {"DATE_TIME": "16/10/2026 16:44", "TITLE": "NOTICE OF BOARD MEETING", "FILE_LINK": "/listedco/listconews/sehk/2026/1016/2026101600428.pdf",
     "NEWS_ID": "11900002", "LONG_TEXT": "Announcements and Notices - [Date of Board Meeting]"},
    {"DATE_TIME": "02/09/2026 16:45", "TITLE": "Monthly Return of Equity Issuer", "FILE_LINK": "/x.pdf", "NEWS_ID": "1"}])}
HKEX_CFG = {"asx": [], "edgarPhrases": [], "hkex": [{"code": "01958", "stockId": 116122, "name": "BAIC Motor", "beat": ["현대차"],
                                                    "relation": "베이징현대 합작 상대", "evidence": "https://example/baic"}]}


class Hkex(unittest.TestCase):
    def test_partner_titles_with_deal_words_and_routine_folding(self):
        seen = []

        def get(url, params=None, headers=None, timeout=None):
            seen.append(params)
            return R(200, HKEX_BODY) if "hkexnews" in url else R(404)
        doc = w.run(HKEX_CFG, now=NOW, get=get, sleep=lambda s: None)
        self.assertEqual((seen[0]["stockId"], seen[0]["fromDate"], seen[0]["toDate"]), (116122, "20260927", "20261027"))
        items = {x["id"]: x for x in doc["items"] if x["source"] == "HKEX"}
        self.assertEqual(sorted(items), ["hkex:01958:11900002", "hkex:01958:11906001"])  # 09-02 is outside the 30-day window
        exit_ = items["hkex:01958:11906001"]
        self.assertEqual((exit_["date"], exit_["time"], exit_["beat"]), ("2026-10-21", "18:33", ["현대차"]))
        self.assertEqual(exit_["url"], "https://www1.hkexnews.hk/listedco/listconews/sehk/2026/1021/2026102100777.pdf")
        self.assertIn("major transaction", exit_["flags"])
        self.assertIn("exit", exit_["flags"])
        board = items["hkex:01958:11900002"]
        self.assertEqual(board["flags"], [])
        self.assertIn("정기·형식", board["routine"])
        self.assertEqual(next(c for c in doc["checks"] if c["source"] == "HKEX")["status"], "ok")

    def test_failure_and_bad_shape_are_not_zero(self):
        doc = w.run(HKEX_CFG, now=NOW, get=lambda *a, **k: R(503), sleep=lambda s: None)
        c = next(c for c in doc["checks"] if c["source"] == "HKEX")
        self.assertEqual((c["status"], c["error"]), ("failed", "HTTP 503"))
        doc = w.run(HKEX_CFG, now=NOW, get=lambda *a, **k: R(200, {"result": "not json"}), sleep=lambda s: None)
        self.assertEqual(next(c for c in doc["checks"] if c["source"] == "HKEX")["error"], "결과 형식 불일치")

    def test_config_partner_has_relation_evidence(self):
        cfg = json.loads(w.PARTNERS.read_text(encoding="utf-8"))
        for p in cfg["hkex"]:
            self.assertTrue(p["relation"] and p["evidence"].startswith("https://") and isinstance(p["stockId"], int))
