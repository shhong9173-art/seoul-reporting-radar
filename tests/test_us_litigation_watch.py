"""US litigation watch: party-only matching, classification, paging, first run vs later runs, ITC 337 body scan."""
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import us_litigation_watch as w  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 10, 27, 8, 0, tzinfo=KST)


def case(did, name, parties, date="2026-10-20", court="vaed", nos="", cause=""):
    # Field names as returned by CourtListener v4 search type=r on 2026-10-26.
    return {"docket_id": did, "caseName": name, "party": parties, "court_id": court, "court": court.upper(), "dateFiled": date,
            "dateTerminated": None, "docketNumber": f"1:26-cv-{did}", "docket_absolute_url": f"/docket/{did}/x/", "suitNature": nos,
            "cause": cause, "recap_documents": []}


RESULTS = {
    "자동차": [
        case(1, "Summers v. Hyundai Motor America Inc", ["Summers", "Hyundai Motor America Inc"], cause="15:2301 Magnuson-Moss Warranty Act"),
        case(2, "Hyundai Motor Company v. The Partnerships and Unincorporated Associations Identified on Schedule A",
             ["Hyundai Motor Company", "The Partnerships and Unincorporated Associations Identified on Schedule A"], court="ilnd", nos="840 Trademark"),
        case(3, "Acme Robotics v. Hyundai Motor Manufacturing Alabama, LLC", ["Acme Robotics", "Hyundai Motor Manufacturing Alabama, LLC"],
             nos="190 Contract: Other"),
    ],
    "철강": [case(4, "POSCO v. United States", ["POSCO", "United States"], date="2026-09-29", court="cit"),
            case(5, "Smith v. POSCO International America", ["Smith", "POSCO International America Corp"])],
}
RESULTS["자동차"].append(case(6, "Qingdao Transamerica Tire Industrial Co., Ltd. v. United States",
                             ["Qingdao Transamerica Tire Industrial Co., Ltd.", "United States"], court="cit"))


RESULTS["전력"] = [case(8, "In re: LS Electric Co., Ltd.", ["LS Electric Co., Ltd."], date="2026-10-22", court="cafc")]
# Field names as returned by CourtListener v4 search type=o on 2026-10-28 (court=cit cafc).
CAPTION = ("Slip Op. 26- UNITED STATES COURT OF INTERNATIONAL TRADE POSCO, Plaintiff, GOVERNMENT OF THE REPUBLIC OF KOREA, "
           "Plaintiff-Intervenor, v. Before: Jane A. Restani, Judge UNITED STATES, Court No. 24-00006 Defendant, and NUCOR CORPORATION, "
           "Defendant-Intervenor. OPINION AND ORDER Dated: October 27, 2026")


def opinion(cluster, op, name, snippet, court="cit", date="2026-10-27", dn="24-00006"):
    return {"cluster_id": cluster, "caseName": name, "caseNameFull": "", "court_id": court, "court": court.upper(), "dateFiled": date,
            "docketNumber": dn, "absolute_url": f"/opinion/{cluster}/x/", "opinions": [{"id": op, "snippet": snippet, "download_url": f"https://pdf/{op}.pdf"}]}


OPINIONS = {"count": 4, "next": None, "results": [
    opinion(11046079, 11513853, "POSCO v. United States", CAPTION),
    # Cites 'POSCO v. United States' in the body only: not POSCO's case.
    opinion(11040617, 11508314, "Baroque Timber Indus. (Zhongshan) Co. v. United States",
            "Slip Op. 26-120 UNITED STATES COURT OF INTERNATIONAL TRADE BAROQUE TIMBER, Plaintiff, v. UNITED STATES, Defendant. "
            "OPINION ... see POSCO v. United States, 296 F. Supp. 3d 1320", date="2026-10-20"),
    opinion(500, 501, "Nucor Corporation v. United States", "NOTE: This disposition is nonprecedential. United States Court of Appeals "
            "for the Federal Circuit NUCOR CORPORATION, Plaintiff-Appellant v. UNITED STATES, Defendant-Appellee HYUNDAI STEEL COMPANY, "
            "Defendant-Appellee 2025-1234 Appeal from the United States Court of International Trade", court="cafc", date="2026-10-21", dn="25-1234"),
    opinion(600, 601, "People v. Kia America", "Kia", court="cal", date="2026-10-22"),
]}
TEXTS = {11513853: "Slip Op. 26-\x14\x16\x14 UNITED STATES COURT OF INTERNATIONAL TRADE POSCO, Plaintiff ... OPINION AND ORDER\n"
                   "[Sustaining the Department of Commerce\u2019s second remand redetermination in its countervailing duty order review of "
                   "certain carbon and alloy steel cut-to-length plate from the Republic of Korea.]\nDated: October 27, 2026",
         501: "... For the foregoing reasons, we affirm.\n\nAFFIRMED\n"}
DOCKETS = {8: {"appeal_from_str": "United States Patent and Trademark Office",
               "appellate_case_type_information": "BCA or PTO, Patent Trial and Appeal Board", "nature_of_suit": ""}}


def group_of(q):
    return "자동차" if '"Hyundai Motor"' in q else ("철강" if '"POSCO"' in q else "전력")
FR = {"results": [
    {"title": "Certain Automotive Headlamps and Components Thereof; Notice of Institution of Investigation", "publication_date": "2026-10-15",
     "html_url": "https://www.federalregister.gov/d/2026-1", "document_number": "2026-1", "raw_text_url": "https://fr/full/2026-1.txt"},
    {"title": "Certain Corrosion-Resistant Steel Products From Korea; Institution of Five-Year Reviews", "publication_date": "2026-10-10",
     "html_url": "https://www.federalregister.gov/d/2026-2", "document_number": "2026-2", "raw_text_url": "https://fr/full/2026-2.txt"},
    {"title": "Certain Wireless Earbuds; Notice of Receipt of Complaint; Solicitation of Comments", "publication_date": "2026-10-12",
     "html_url": "https://www.federalregister.gov/d/2026-3", "document_number": "2026-3", "raw_text_url": "https://fr/full/2026-3.txt"},
]}
BODIES = {"2026-1": "<pre>The respondents are:\nHyundai Mobis Co., Ltd., Seoul, Republic of Korea\nAcme Lighting Inc.\n</pre>",
          "2026-2": "<pre>POSCO\n</pre>", "2026-3": "<pre>Respondent: Earbud Co.\n</pre>"}


class R:
    def __init__(self, code=200, body=None, text="", headers=None):
        self.status_code, self.body, self.text, self.headers = code, body, text, headers or {}

    def json(self):
        return self.body


def fake(cl_code=200, calls=None, pages=None, throttle=None, log=None, opinions=None):
    throttle = list(throttle or [])
    def get(url, params=None, headers=None, timeout=None):
        if calls is not None:
            calls.append(url)
        if log is not None:
            log.append((url, dict(params or {})))
        if url.startswith(w.CL_BASE):
            assert headers["Authorization"] == "Token t"
            if throttle:
                return R(429, {"detail": "Request was throttled."}, headers={"Retry-After": throttle.pop(0)})
            if cl_code != 200:
                return R(cl_code, {"detail": "x"})
            if url.startswith(f"{w.CL_BASE}/opinions/"):
                return R(body={"plain_text": TEXTS.get(int(url.rstrip("/").rsplit("/", 1)[1]), "")})
            if url.startswith(f"{w.CL_BASE}/dockets/"):
                did = int(url.rstrip("/").rsplit("/", 1)[1])
                return R(body=DOCKETS[did]) if did in DOCKETS else R(404, {"detail": "Not found."})
            if (params or {}).get("type") == "o":
                return R(body=opinions if opinions is not None else OPINIONS)
            if pages and url in pages:
                return R(body=pages[url])
            g = group_of(params["q"])
            if pages and g in pages:
                return R(body=pages[g])
            return R(body={"count": len(RESULTS.get(g, [])), "next": None, "results": RESULTS.get(g, [])})
        if url == w.trw.FR_API:
            return R(body=FR)
        if url.startswith("https://fr/full/"):
            doc = url.rsplit("/", 1)[1].replace(".txt", "")
            return R(text=BODIES[doc])
        return R(404)
    return get


def dockets_checks(doc):
    return [c for c in doc["checks"] if c["source"].startswith("CourtListener") and c.get("kind") != "opinions"]


def run(previous=None, **k):
    return w.run("t", now=NOW, previous=previous, get=fake(**k), sleep=lambda s: None)


class Litigation(unittest.TestCase):
    def test_party_matching_and_classification(self):
        doc = run()
        cases = {x["id"]: x for x in doc["cases"]}
        self.assertNotIn("cl:5", cases)  # POSCO International is not 포스코
        self.assertNotIn("cl:6", cases)  # Hankook only mentioned in someone else's case
        self.assertEqual(cases["cl:4"]["category"], "국제무역법원(무역구제 소송)")
        self.assertEqual(cases["cl:4"]["role"], "원고")
        self.assertEqual(cases["cl:3"]["category"], "계약")
        self.assertEqual(cases["cl:3"]["role"], "피고·기타 당사자")
        self.assertEqual(cases["cl:1"]["category"], "소비자·제조물책임")
        self.assertEqual(cases["cl:1"]["priority"], 3)
        self.assertEqual(cases["cl:2"]["category"], "위조품 단속(상표)")
        self.assertEqual([x["id"] for x in doc["cases"]][:3], ["cl:8", "cl:4", "cl:3"])  # Federal Circuit / trade court first, then contract
        self.assertEqual(cases["cl:4"]["url"], "https://www.courtlistener.com/docket/4/x/")
        self.assertFalse(any(x["isNew"] for x in doc["cases"]))  # first run is a baseline

    def test_later_run_marks_new_and_keeps_older_cases(self):
        first = run()
        first["cases"] = [x for x in first["cases"] if x["id"] != "cl:3"]
        first["cases"].append(dict(first["cases"][0], id="cl:99", dateFiled="2026-08-01", caseName="Old v. Hyundai Motor America"))
        doc = run(previous=first)
        cases = {x["id"]: x for x in doc["cases"]}
        self.assertTrue(cases["cl:3"]["isNew"])
        self.assertFalse(cases["cl:4"]["isNew"])
        self.assertIn("cl:99", cases)  # outside the 45-day window, inside 120-day retention

    def test_paging_follows_next(self):
        nxt = "https://www.courtlistener.com/api/rest/v4/search/?page=2"
        pages = {"자동차": {"count": 4, "next": nxt, "results": RESULTS["자동차"]},
                 nxt: {"count": 4, "next": None, "results": [case(7, "Lee v. Hyundai Motor America", ["Lee", "Hyundai Motor America"])]}}
        doc = run(pages=pages)
        self.assertIn("cl:7", {x["id"] for x in doc["cases"]})

    def test_refused_token_stops_and_is_failed(self):
        calls = []
        doc = run(cl_code=401, calls=calls)
        cl = dockets_checks(doc)
        self.assertEqual(len(cl), 3)
        self.assertEqual(cl[0]["error"], "HTTP 401 토큰 거부")
        self.assertTrue(all(c["status"] == "failed" for c in cl))
        op = next(c for c in doc["checks"] if c.get("kind") == "opinions")
        self.assertEqual((op["status"], op["error"]), ("failed", "앞 질의 중단(HTTP 401 토큰 거부)"))
        self.assertEqual(doc["status"], "partial")
        self.assertEqual(sum(1 for u in calls if u.startswith(w.CL_BASE)), 1)  # no opinion search, no details after a refusal
        self.assertIsNone(doc["coveredThrough"])

    def test_three_group_queries_spaced_and_or_joined(self):
        log, sleeps = [], []
        doc = w.run("t", now=NOW, get=fake(log=log), sleep=sleeps.append)
        searches = [p for u, p in log if u.startswith(w.CL_API) and p.get("type") == "r"]
        self.assertEqual(len(searches), 3)
        cl_all = [u for u, _ in log if u.startswith(w.CL_BASE)]
        # 3 docket searches + 1 Federal Circuit docket detail + 1 opinion search + 2 opinion texts, all spaced
        self.assertEqual(len(cl_all), 7)
        self.assertEqual(sleeps.count(w.CALL_GAP), 7)
        self.assertEqual(doc["coveredThrough"], NOW.isoformat(timespec="seconds"))
        self.assertTrue(all(c["since"] == "2026-09-12" for c in dockets_checks(doc)))

    def test_short_retry_after_is_waited_once(self):
        sleeps = []
        doc = w.run("t", now=NOW, get=fake(throttle=["30"]), sleep=sleeps.append)
        self.assertIn(30, sleeps)
        self.assertTrue(all(c["status"] == "ok" for c in doc["checks"] if c["source"].startswith("CourtListener")))

    def test_long_retry_after_stops_remaining_groups(self):
        calls = []
        doc = run(throttle=["85774"], calls=calls)
        cl = [c for c in doc["checks"] if c["source"].startswith("CourtListener")]
        self.assertEqual(cl[0]["error"], "HTTP 429 호출 한도(재시도 85774초 뒤)")
        self.assertTrue(all(c["status"] == "failed" for c in cl))
        self.assertEqual(len(cl), 4)  # three groups + rulings
        self.assertEqual(sum(1 for u in calls if u.startswith(w.CL_BASE)), 1)

    def test_window_narrows_after_a_complete_run(self):
        self.assertEqual(w.window_start(NOW, None), "2026-09-12")
        self.assertEqual(w.window_start(NOW, {"coveredThrough": "2026-10-26T07:50:00+09:00"}), "2026-10-19")
        self.assertEqual(w.window_start(NOW, {"coveredThrough": "2026-01-01T07:50:00+09:00"}), "2026-09-12")


class Rulings(unittest.TestCase):
    def test_trade_court_ruling_with_holding_and_reading(self):
        log = []
        doc = w.run("t", now=NOW, get=fake(log=log), sleep=lambda s: None)
        q = next(p for u, p in log if p.get("type") == "o")
        self.assertEqual((q["court"], q["filed_after"], q["order_by"]), ("cit cafc", "2026-10-06", "dateFiled desc"))
        self.assertIn('"POSCO"', q["q"])
        self.assertIn('"LS Electric"', q["q"])
        ops = {x["id"]: x for x in doc["opinions"]}
        self.assertEqual(sorted(ops), ["op:11046079", "op:500"])  # citing-only CIT case and a state court left out
        posco = ops["op:11046079"]
        self.assertEqual((posco["beat"], posco["role"], posco["courtId"], posco["docketNumber"]), (["포스코"], "원고", "cit", "24-00006"))
        self.assertTrue(posco["holding"].startswith("Sustaining the Department of Commerce\u2019s second remand redetermination"))
        self.assertEqual(posco["holdingKo"], "유지")
        self.assertIn("받아들여지지 않았다는 뜻으로 읽힘(판결문 본문 확인 전)", posco["reading"])
        self.assertIsNone(posco["slipOp"])  # control characters in the slip number are dropped, not guessed
        self.assertEqual(posco["pdf"], "https://pdf/11513853.pdf")
        nucor = ops["op:500"]
        self.assertEqual((nucor["beat"], nucor["role"], nucor["holding"], nucor["holdingKo"]), (["현대제철"], "피고·참가인 등", "AFFIRMED", "원심 확정"))
        self.assertIsNone(nucor["reading"])  # a reading is only offered for a beat plaintiff against the government
        self.assertFalse(any(x["isNew"] for x in doc["opinions"]))  # first run is a baseline
        self.assertTrue(any(c.get("kind") == "opinions" and c["status"] == "ok" and c["own"] == 2 for c in doc["checks"]))

    def test_later_run_marks_new_ruling_and_does_not_reread_texts(self):
        first = w.run("t", now=NOW, get=fake(), sleep=lambda s: None)
        first["opinions"] = [x for x in first["opinions"] if x["id"] != "op:500"]
        log = []
        doc = w.run("t", now=NOW + dt.timedelta(days=1), previous=first, get=fake(log=log), sleep=lambda s: None)
        ops = {x["id"]: x for x in doc["opinions"]}
        self.assertTrue(ops["op:500"]["isNew"])
        self.assertFalse(ops["op:11046079"]["isNew"])
        self.assertEqual(ops["op:11046079"]["holdingKo"], "유지")  # kept from the previous run
        texts = [u for u, _ in log if "/opinions/" in u]
        self.assertEqual(texts, [f"{w.CL_BASE}/opinions/501/"])

    def test_failed_ruling_search_keeps_previous_and_does_not_block_case_window(self):
        first = w.run("t", now=NOW, get=fake(), sleep=lambda s: None)
        bad = fake(opinions=None)

        def get(url, params=None, headers=None, timeout=None):
            if (params or {}).get("type") == "o":
                return R(500, {"detail": "x"})
            return bad(url, params, headers, timeout)
        doc = w.run("t", now=NOW + dt.timedelta(days=1), previous=first, get=get, sleep=lambda s: None)
        op = next(c for c in doc["checks"] if c.get("kind") == "opinions")
        self.assertEqual((op["status"], op["error"]), ("failed", "HTTP 500"))
        self.assertEqual({x["id"] for x in doc["opinions"]}, {x["id"] for x in first["opinions"]})
        self.assertEqual(doc["status"], "partial")
        self.assertIsNotNone(doc["coveredThrough"])  # docket searches were complete

    def test_gloss_reads_only_clause_opening_verbs(self):
        self.assertEqual(w.gloss("Sustaining in part and remanding in part Commerce's final results"), "일부 유지·일부 재검토 환송")
        self.assertEqual(w.gloss("Granting defendant's motion to dismiss"), "신청 인용")
        self.assertEqual(w.gloss("AFFIRMED-IN-PART, VACATED-IN-PART, AND REMANDED"), "일부 원심 확정·일부 취소·재검토 환송")
        self.assertEqual(w.gloss("Sustaining Commerce's remand redetermination, which was remanded twice"), "유지")
        self.assertIsNone(w.gloss("Opinion and order"))


class Explain(unittest.TestCase):
    def test_federal_circuit_appeal_from_patent_board(self):
        doc = run()
        ls = next(x for x in doc["cases"] if x["id"] == "cl:8")
        self.assertEqual(ls["role"], "신청·항소인(In re)")
        self.assertEqual((ls["appealFrom"], ls["caseType"]), ("United States Patent and Trademark Office", "BCA or PTO, Patent Trial and Appeal Board"))
        self.assertEqual(ls["summary"], "LS일렉트릭, 미국 특허청 특허심판원(PTAB) 결정에 불복해 연방순회항소법원에 항소(사건 1:26-cv-8, 2026-10-22 접수)")
        posco = next(x for x in doc["cases"] if x["id"] == "cl:4")
        self.assertEqual(posco["summary"], "포스코, 미국 정부를 상대로 국제무역법원에 소송 제기(2026-09-29 접수, 다툰 판정은 소장에서 확인)")
        self.assertNotIn("appealFrom", posco)  # no detail call for trade-court dockets
        self.assertIsNone(next(x for x in doc["cases"] if x["id"] == "cl:3")["summary"])

    def test_details_are_read_once(self):
        first = run()
        log = []
        doc = w.run("t", now=NOW, previous=first, get=fake(log=log), sleep=lambda s: None)
        self.assertFalse(any("/dockets/" in u for u, _ in log))
        self.assertEqual(next(x for x in doc["cases"] if x["id"] == "cl:8")["appealFrom"], "United States Patent and Trademark Office")


class Itc(unittest.TestCase):
    def test_337_only_and_named_companies(self):
        doc = run()
        itc = {x["id"]: x for x in doc["itc"]}
        self.assertEqual(list(itc), ["fr:2026-1"])  # AD/CVD 'From Korea' notice and unnamed complaint left out
        self.assertEqual(itc["fr:2026-1"]["stage"], "조사 개시")
        self.assertEqual(itc["fr:2026-1"]["named"][0]["company"], "현대모비스")
        self.assertIn("fr:2026-3", doc["itcChecked"])
        self.assertNotIn("fr:2026-2", doc["itcChecked"])

    def test_checked_bodies_are_not_read_again(self):
        first = run()
        calls = []
        w.run("t", now=NOW, previous=first, get=fake(calls=calls), sleep=lambda s: None)
        self.assertFalse(any(u.startswith("https://fr/full/") for u in calls))


if __name__ == "__main__":
    unittest.main()
