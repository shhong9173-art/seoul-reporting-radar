"""유럽 상표 출원(EUIPO): 토큰·403 승인 대기·기준선·새 출원 등급·이름 거르기·평일 재시도."""
import datetime as dt
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import euipo_trademarks as eu  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 11, 9, 7, 10, tzinfo=KST)
CFG = {"windowDays": 120, "size": 30, "industries": {"auto": {"core": ["12", "09"]}, "steel": {"core": ["06"]}},
       "applicants": [{"company": "현대자동차", "industry": "auto", "query": "*Hyundai Motor Company*"},
                      {"company": "포스코", "industry": "steel", "query": "*POSCO*", "accept": "^POSCO(?: Holdings)?$", "exclude": "Future\\s*M"}]}


class R:
    def __init__(self, status, body=None):
        self.status_code, self.body = status, body or {}

    def json(self):
        return self.body


def tm(no, mark, day, classes, who="Hyundai Motor Company"):
    return {"applicationNumber": no, "applicationDate": day, "niceClasses": classes, "status": "RECEIVED", "markFeature": "WORD",
            "wordMarkSpecification": {"verbalElement": mark}, "applicants": [{"name": who, "office": "EM"}]}


class Fake:
    def __init__(self, by_query=None, token_status=200, search_status=200):
        self.by_query, self.token_status, self.search_status, self.searches, self.headers = by_query or {}, token_status, search_status, [], []

    def post(self, url, data=None, headers=None, timeout=None):
        assert url == eu.TOKEN_URL and data["grant_type"] == "client_credentials" and data["scope"] == "uid"
        return R(self.token_status, {"access_token": "TOK", "expires_in": 7200})

    def get(self, url, params=None, headers=None, timeout=None):
        self.searches.append(params["query"])
        self.headers.append(headers)
        if self.search_status != 200:
            return R(self.search_status, {"title": "Forbidden", "type": "https://dev.euipo.europa.eu/problems-registry/access-forbidden"})
        rows = next((v for k, v in self.by_query.items() if k in params["query"]), [])
        return R(200, {"trademarks": rows, "totalElements": len(rows), "page": 0, "size": params["size"]})


class Euipo(unittest.TestCase):
    def test_403_is_waiting_and_stops_asking(self):
        f = Fake(search_status=403)
        doc = eu.run(CFG, None, NOW, client_id="CID", secret="SEC", post=f.post, get=f.get)
        self.assertEqual(len(f.searches), 1)
        self.assertEqual([c["status"] for c in doc["checks"]], ["waiting", "waiting"])
        self.assertEqual(doc["status"], "waiting")
        self.assertIn("승인 대기", doc["blocked"])
        self.assertEqual(f.headers[0]["X-IBM-Client-Id"], "CID")
        self.assertNotIn("TOK", json.dumps(doc, ensure_ascii=False))
        self.assertNotIn("SEC", json.dumps(doc, ensure_ascii=False))

    def test_token_failure_and_missing_keys(self):
        f = Fake(token_status=502)
        doc = eu.run(CFG, None, NOW, client_id="CID", secret="SEC", post=f.post, get=f.get)
        self.assertEqual({c["status"] for c in doc["checks"]}, {"failed"})
        self.assertIn("토큰 HTTP 502", doc["checks"][0]["error"])
        self.assertEqual(f.searches, [])
        doc = eu.run(CFG, None, NOW, client_id="", secret="", post=f.post, get=f.get)
        self.assertEqual(doc["status"], "unset")

    def test_baseline_then_new_filings_graded_and_names_filtered(self):
        first = Fake({"Hyundai Motor Company": [tm("019000001", "PLEOS", "2026-09-10", [9, 12])],
                      "POSCO": [tm("019000010", "GREENATE", "2026-08-01", [6], who="POSCO Holdings"),
                                tm("019000011", "FUTURE CATHODE", "2026-08-02", [1], who="POSCO Future M Co., Ltd.")]})
        d1 = eu.run(CFG, None, NOW, client_id="C", secret="S", post=first.post, get=first.get)
        self.assertEqual(d1["status"], "complete")
        self.assertFalse(any(f["isNew"] for f in d1["filings"]))
        self.assertEqual(sorted(f["applicationNumber"] for f in d1["filings"]), ["019000001", "019000010"])  # 포스코퓨처엠은 거름
        self.assertEqual(next(c for c in d1["checks"] if c["company"] == "포스코")["otherApplicants"], 1)
        self.assertTrue(all(c.get("baseline") for c in d1["checks"]))
        later = NOW + dt.timedelta(days=7)
        second = Fake({"Hyundai Motor Company": [tm("019000002", "AERO DRIVE", "2026-11-01", [12, 35]),
                                                 tm("019000003", "PLEOS", "2026-11-02", [9]),
                                                 tm("018000999", "OLD", "2026-03-01", [12]),
                                                 tm("019000001", "PLEOS", "2026-09-10", [9, 12])]})
        d2 = eu.run(CFG, d1, later, client_id="C", secret="S", post=second.post, get=second.get)
        by = {f["applicationNumber"]: f for f in d2["filings"]}
        self.assertEqual((by["019000002"]["isNew"], by["019000002"]["tier"], by["019000002"]["coreClasses"]), (True, "B", ["12"]))
        self.assertEqual((by["019000003"]["isNew"], by["019000003"]["tier"]), (True, "C"))   # 이미 본 이름
        self.assertNotIn("018000999", by)                                                     # 조회 창(120일) 밖
        self.assertFalse(by["019000001"]["isNew"])
        self.assertEqual(sorted(d2["fresh"]), ["euipo:019000002", "euipo:019000003"])
        self.assertTrue(by["019000002"]["url"].endswith("/019000002"))

    def test_weekday_retry_only_unsettled_companies(self):
        blocked = eu.run(CFG, None, NOW, client_id="C", secret="S", post=Fake(search_status=403).post, get=Fake(search_status=403).get)
        prev = dict(blocked)
        prev["checks"] = [{"company": "현대자동차", "status": "ok", "query": "*Hyundai Motor Company*"}, {"company": "포스코", "status": "waiting"}]
        f = Fake({"POSCO": [tm("019000010", "GREENATE", "2026-08-01", [6], who="POSCO")]})
        d = eu.run(CFG, prev, NOW + dt.timedelta(days=1), client_id="C", secret="S", post=f.post, get=f.get, only_unsettled=True)
        self.assertEqual(f.searches, ['applicants.name=="*POSCO*"'])
        self.assertEqual([c["status"] for c in d["checks"]], ["ok", "ok"])
        self.assertTrue(next(c for c in d["checks"] if c["company"] == "포스코").get("baseline"))

    def test_config_has_unique_companies_and_queries(self):
        cfg = json.loads((Path(__file__).resolve().parents[1] / "data" / "trademark_watch.json").read_text(encoding="utf-8"))["euipo"]
        names = [a["company"] for a in cfg["applicants"]]
        self.assertEqual(len(names), len(set(names)))
        self.assertTrue(all(a["query"].startswith("*") and a["query"].endswith("*") for a in cfg["applicants"]))


if __name__ == "__main__":
    unittest.main()
