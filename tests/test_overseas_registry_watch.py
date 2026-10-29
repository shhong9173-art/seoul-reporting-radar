"""영국 법인 등기 감시: 회사명 규칙, 지배 주주(PSC)로 A/C, 기준선·새 법인, 키 없음·거부는 미설정."""
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import overseas_registry_watch as w  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 10, 30, 6, 0, tzinfo=KST)


class Resp:
    def __init__(self, body=None, status=200):
        self._b, self.status_code = body or {}, status

    def json(self):
        return self._b


def co(num, name, created="2026-10-20"):
    return {"company_number": num, "company_name": name, "company_status": "active", "company_type": "ltd", "date_of_creation": created,
            "sic_codes": ["27110"], "registered_office_address": {"address_line_1": "1 Grid Way", "locality": "London"}}


def fake(results, psc, status=200):
    calls = []

    def get(url, params=None, auth=None, headers=None, timeout=None):
        calls.append(url)
        if status != 200:
            return Resp(status=status)
        if url.endswith("/advanced-search/companies"):
            return Resp({"items": results.get(params["company_name_includes"], [])})
        num = url.split("/company/")[1].split("/")[0]
        return Resp({"items": [{"name": n} for n in psc.get(num, [])]})
    get.calls = calls
    return get


class Registry(unittest.TestCase):
    def test_psc_decides_tier_and_baseline(self):
        res = {"hyosung": [co("1001", "HYOSUNG HEAVY INDUSTRIES UK LTD")], "hyundai": [co("2001", "HYUNDAI OF BRISTOL LIMITED"), co("2002", "XHYUNDAIX LTD")]}
        psc = {"1001": ["Hyosung Heavy Industries Corporation"], "2001": ["John Smith"]}
        first = w.run("k", now=NOW, previous=None, get=fake(res, psc), sleep=lambda s: None)
        got = {x["number"]: x for x in first["companies"]}
        self.assertEqual(set(got), {"1001", "2001"})  # 'XHYUNDAIX' is not the word hyundai
        self.assertEqual((got["1001"]["tier"], got["1001"]["company"]), ("A", "효성중공업(관련)"))
        self.assertEqual(got["2001"]["tier"], "C")
        self.assertTrue(all(x["baseline"] and not x["isNew"] for x in first["companies"]))
        self.assertEqual(first["windowStart"], (NOW - dt.timedelta(days=w.BASELINE_DAYS)).date().isoformat())

        res2 = dict(res, **{"ls cable": [co("3001", "LS CABLE & SYSTEM UK OFFSHORE LIMITED", "2026-10-29")]})
        get2 = fake(res2, {"3001": ["Ls Cable & System Ltd."]})
        second = w.run("k", now=NOW + dt.timedelta(days=1), previous=first, get=get2, sleep=lambda s: None)
        new = [x for x in second["companies"] if x["isNew"]]
        self.assertEqual([(x["number"], x["tier"]) for x in new], [("3001", "A")])
        self.assertFalse(any("/company/1001/" in u for u in get2.calls))  # PSC는 처음 볼 때만 읽는다
        self.assertEqual(second["windowStart"], (NOW - dt.timedelta(days=w.OVERLAP_DAYS)).date().isoformat())  # 직전 성공 7일 전부터

    def test_first_real_run_after_unset_is_baseline(self):
        unset = w.run("", now=NOW)
        res = {"hyundai": [co("2001", "HYUNDAI OF BRISTOL LIMITED")]}
        doc = w.run("k", now=NOW, previous=unset, get=fake(res, {}), sleep=lambda s: None)
        self.assertTrue(all(x["baseline"] and not x["isNew"] for x in doc["companies"]))
        # repair of the 10-29 state: one batch stored as new right after '미설정'
        bad = dict(doc, baselineMarked=None, companies=[dict(x, baseline=False, isNew=True) for x in doc["companies"]])
        again = w.run("k", now=NOW + dt.timedelta(days=1), previous=bad, get=fake(res, {}), sleep=lambda s: None)
        self.assertTrue(all(x["baseline"] and not x["isNew"] for x in again["companies"]))

    def test_parent_name_without_psc_is_b(self):
        res = {"nexen": [co("16848629", "NEXEN TYRE U.K. LIMITED"), co("16967581", "NEXEN STRATEGY LIMITED")]}
        doc = w.run("k", now=NOW, previous=None, get=fake(res, {"16967581": ["Mr Nauman Safdar"]}), sleep=lambda s: None)
        got = {x["number"]: x["tier"] for x in doc["companies"]}
        self.assertEqual(got, {"16848629": "B", "16967581": "C"})
        # a stored row graded before this rule, now outside the search window, is re-graded
        old = dict(doc, companies=[dict(x, tier="C") for x in doc["companies"]])
        again = w.run("k", now=NOW + dt.timedelta(days=30), previous=old, get=fake({}, {}), sleep=lambda s: None)
        self.assertEqual({x["number"]: x["tier"] for x in again["companies"]}, {"16848629": "B", "16967581": "C"})

    def test_missing_or_refused_key_is_unset(self):
        self.assertEqual(w.run("", now=NOW)["status"], "unset")
        doc = w.run("k", now=NOW, previous=None, get=fake({}, {}, status=401), sleep=lambda s: None)
        self.assertEqual(doc["status"], "unset")
        self.assertIn("키 거부", doc["checks"][0]["error"])


if __name__ == "__main__":
    unittest.main()
