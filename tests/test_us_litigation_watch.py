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


def fake(cl_code=200, calls=None, pages=None, throttle=None):
    throttle = list(throttle or [])
    def get(url, params=None, headers=None, timeout=None):
        if calls is not None:
            calls.append(url)
        if url.startswith(w.CL_API) or url.startswith("https://www.courtlistener.com/api/rest/v4/search/?page"):
            assert headers["Authorization"] == "Token t"
            if throttle:
                return R(429, {"detail": "Request was throttled."}, headers={"Retry-After": throttle.pop(0)})
            if cl_code != 200:
                return R(cl_code, {"detail": "x"})
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
        self.assertEqual([x["id"] for x in doc["cases"]][:2], ["cl:4", "cl:3"])  # trade court first, then contract
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
        cl = [c for c in doc["checks"] if c["source"].startswith("CourtListener")]
        self.assertEqual(len(cl), 3)
        self.assertEqual(cl[0]["error"], "HTTP 401 토큰 거부")
        self.assertTrue(all(c["status"] == "failed" for c in cl))
        self.assertEqual(doc["status"], "partial")
        self.assertEqual(sum(1 for u in calls if u.startswith(w.CL_API)), 1)
        self.assertIsNone(doc["coveredThrough"])

    def test_three_group_queries_spaced_and_or_joined(self):
        calls, sleeps = [], []
        doc = w.run("t", now=NOW, get=fake(calls=calls), sleep=sleeps.append)
        cl_calls = [u for u in calls if u.startswith(w.CL_API)]
        self.assertEqual(len(cl_calls), 3)
        self.assertEqual(sleeps.count(w.CALL_GAP), 3)
        self.assertEqual(doc["coveredThrough"], NOW.isoformat(timespec="seconds"))
        self.assertTrue(all(c["since"] == "2026-09-12" for c in doc["checks"] if c["source"].startswith("CourtListener")))

    def test_short_retry_after_is_waited_once(self):
        sleeps = []
        doc = w.run("t", now=NOW, get=fake(throttle=["30"]), sleep=sleeps.append)
        self.assertIn(30, sleeps)
        self.assertTrue(all(c["status"] == "ok" for c in doc["checks"] if c["source"].startswith("CourtListener")))

    def test_long_retry_after_stops_remaining_groups(self):
        doc = run(throttle=["85774"])
        cl = [c for c in doc["checks"] if c["source"].startswith("CourtListener")]
        self.assertEqual(cl[0]["error"], "HTTP 429 호출 한도(재시도 85774초 뒤)")
        self.assertTrue(all(c["status"] == "failed" for c in cl))

    def test_window_narrows_after_a_complete_run(self):
        self.assertEqual(w.window_start(NOW, None), "2026-09-12")
        self.assertEqual(w.window_start(NOW, {"coveredThrough": "2026-10-26T07:50:00+09:00"}), "2026-10-19")
        self.assertEqual(w.window_start(NOW, {"coveredThrough": "2026-01-01T07:50:00+09:00"}), "2026-09-12")


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
