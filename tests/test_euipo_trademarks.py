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


CFG_SIGNA = {**CFG, "applicants": [CFG["applicants"][0],
                                    {"company": "포스코", "industry": "steel", "query": "*POSCO*",
                                     "accept": "^POSCO(?: Holdings)?(?: Inc\\.?| Co\\.?(?:,? Ltd\\.?)?)?$|^POSCO$", "exclude": "Future\\s*M|International"}]}


def sg(no, mark, day, classes, who="Hyundai Motor Company", route="direct_regional"):
    """Signa /v1/trademarks 응답 한 줄(11-09 탐침 모양)."""
    return {"id": f"tm_{no}", "object": "trademark", "mark_text": mark, "mark_feature_type": "figurative" if mark.startswith("[") else "word",
            "status": {"primary": "pending", "stage": "examining", "raw": {"code": "UNDER_EXAMINATION" if route.startswith("madrid") else "APPLICATION_PUBLISHED"}},
            "office_code": "EM", "filing_route": route, "application_number": no, "filing_date": day, "nice_classes": classes,
            "owners": [{"id": "own_x", "name": who}], "office_url": f"https://euipo.europa.eu/eSearch/#details/trademarks/{no}"}


class SR(R):
    def __init__(self, status, body=None, headers=None):
        super().__init__(status, body)
        self.headers = headers or {}


class SignaFake(Fake):
    """EUIPO는 403(승인 대기, euipo_rows가 있으면 정상), Signa는 owner_name별 응답·남은 크레딧(한 번에 10씩 줄어듦)."""
    def __init__(self, by_owner, left=10000, status=200, euipo_rows=None):
        super().__init__(euipo_rows or {}, search_status=200 if euipo_rows else 403)
        self.by_owner, self.left, self.status, self.signa, self.signa_params, self.euipo = by_owner, left, status, [], [], []

    def get(self, url, params=None, headers=None, timeout=None):
        if url == eu.signa.SEARCH_URL:
            assert headers["Authorization"].startswith("Bearer ")
            self.signa.append(params["owner_name"])
            self.signa_params.append(params)
            if self.status != 200:
                return SR(self.status, {"type": "insufficient_credits"})
            self.left -= 10
            rows = self.by_owner.get(params["owner_name"], [])
            return SR(200, {"object": "list", "data": rows, "has_more": False}, {"X-Credits-Remaining": str(self.left)})
        self.euipo.append(params["query"])
        return super().get(url, params=params, headers=headers, timeout=timeout)


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

    def test_signa_reads_while_euipo_is_blocked(self):
        # 11-09: EUIPO 운영 검색 403(구독 승인 대기) 동안 SIGNA_API_KEY로 같은 회사를 읽는다(11-09 탐침 응답 모양)
        f = SignaFake({"Hyundai Motor Company": [sg("019422142", "Genesis Box Buggy", "2026-09-14", [28]),
                                                 sg("019403488", "[Design Mark]", "2026-07-31", [12])],
                       "POSCO": [sg("W11481965", "PosZET", "2026-07-22", [6, 12, 40, 42], who="POSCO Co.", route="madrid_designation"),
                                 sg("019390922", "DAEWOO", "2026-07-06", [6], who="Posco International Corporation")]}, left=10390)
        doc = eu.run(CFG_SIGNA, None, NOW, client_id="CID", secret="SEC", post=f.post, get=f.get, signa_key="SIGNA-KEY")
        self.assertEqual(len(f.euipo), 1)                                   # EUIPO는 한 번 확인(403)하고 그 뒤로 묻지 않음
        self.assertEqual(f.signa, ["Hyundai Motor Company", "POSCO"])      # 별표 뺀 이름으로
        self.assertEqual([(c["status"], c["via"]) for c in doc["checks"]], [("ok", "signa"), ("ok", "signa")])
        self.assertEqual((doc["status"], doc["provider"], doc["signaCreditsLeft"]), ("complete", "signa", 10370))
        self.assertIn("승인 대기", doc["blocked"])                          # EUIPO 직접 조회는 여전히 대기로 남김
        by = {x["applicationNumber"]: x for x in doc["filings"]}
        self.assertEqual(sorted(by), ["019403488", "019422142", "W11481965"])  # 포스코인터내셔널은 거름
        self.assertEqual((by["019403488"]["title"], by["019422142"]["via"]), ("(FIGURATIVE)", "signa"))   # '[Design Mark]'는 이름이 아님
        self.assertEqual((by["W11481965"]["route"], by["W11481965"]["status"]), ("마드리드 지정", "UNDER_EXAMINATION"))
        self.assertTrue(by["W11481965"]["url"].endswith("/W11481965"))   # EUIPO eSearch 원문 링크
        dump = json.dumps(doc, ensure_ascii=False)
        self.assertNotIn("SIGNA-KEY", dump)
        self.assertNotIn("TOK", dump)
        self.assertEqual(f.signa_params[0]["office"], "EM")
        self.assertEqual(f.signa_params[0]["filing_date_gte"], (NOW.date() - dt.timedelta(days=120)).isoformat())

    def test_signa_credit_floor_and_errors_are_unconfirmed(self):
        low = SignaFake({}, left=25)
        doc = eu.run(CFG_SIGNA, None, NOW, client_id="", secret="", post=low.post, get=low.get, signa_key="K")
        self.assertEqual(low.signa, ["Hyundai Motor Company"])               # 남은 25 < 30 — 둘째 회사부터 안 물음
        self.assertEqual([c["status"] for c in doc["checks"]], ["ok", "waiting"])
        self.assertIn("크레딧 부족", doc["checks"][1]["reason"])
        bad = SignaFake({}, status=402)
        doc = eu.run(CFG_SIGNA, None, NOW, client_id="", secret="", post=bad.post, get=bad.get, signa_key="K")
        self.assertEqual({(c["status"], c["via"]) for c in doc["checks"]}, {("failed", "signa")})
        self.assertIn("402", doc["checks"][0]["error"])
        self.assertNotIn("provider", doc)
        # 키가 없으면 예전처럼 미설정
        doc = eu.run(CFG_SIGNA, None, NOW, client_id="", secret="", post=bad.post, get=bad.get)
        self.assertEqual(doc["status"], "unset")

    def test_us_office_reads_signa_only(self):
        # 11-09: 미국(USPTO)은 직접 API가 막혀(ID.me) Signa로만 — EUIPO 토큰·검색은 부르지 않는다
        f = SignaFake({"Hyundai Motor Company": [sg("50141613", "GENESIS BOX BUGGY", "2026-10-02", [28], who="HYUNDAI MOTOR COMPANY")],
                       "POSCO": [sg("79455640", "POSCLESS", "2026-09-26", [6], who="POSCO Co., Ltd", route="madrid_extension"),
                                 sg("99742964", "AGENTEE", "2026-08-03", [9], who="POSCO DX COMPANY LTD.")]})
        doc = eu.run({**CFG_SIGNA, "applicants": [CFG_SIGNA["applicants"][0], {**CFG_SIGNA["applicants"][1], "exclude": "Future\\s*M|International|DX"}]},
                     None, NOW, client_id="", secret="", post=f.post, get=f.get, signa_key="K", office="US")
        self.assertEqual(f.euipo, [])
        self.assertEqual({p["office"] for p in f.signa_params}, {"US"})
        self.assertEqual((doc["office"], doc["source"], doc["provider"]), ("US", "USPTO 상표 출원(Signa 경유)", "signa"))
        self.assertIn("USPTO", doc["providerNote"])
        by = {x["applicationNumber"]: x for x in doc["filings"]}
        self.assertEqual(sorted(by), ["50141613", "79455640"])                          # 포스코DX는 거름
        self.assertEqual(by["50141613"]["id"], "uspto:50141613")
        self.assertIn("tsdr.uspto.gov/#caseNumber=50141613", by["50141613"]["url"])
        self.assertEqual(by["79455640"]["route"], "마드리드 지정")
        self.assertNotIn("blocked", doc)
        doc = eu.run(CFG_SIGNA, None, NOW, client_id="", secret="", post=f.post, get=f.get, office="US")
        self.assertEqual((doc["status"], doc["checks"][0]["error"]), ("unset", "SIGNA_API_KEY 없음"))

    def test_cadence_only_when_credits_run_low(self):
        cfg = {**CFG_SIGNA, "applicants": [{**CFG_SIGNA["applicants"][0], "signaEvery": 1}, {**CFG_SIGNA["applicants"][1], "signaEvery": 4}]}
        week_ago = (NOW - dt.timedelta(days=7)).isoformat(timespec="seconds")
        prev = {"signaCreditsLeft": 900, "checks": [{"company": "현대자동차", "status": "ok", "via": "signa", "checkedAt": week_ago},
                                                    {"company": "포스코", "status": "ok", "via": "signa", "checkedAt": week_ago, "kept": 1}]}
        f = SignaFake({})
        doc = eu.run(cfg, prev, NOW, client_id="", secret="", post=f.post, get=f.get, signa_key="K", office="US")
        self.assertEqual(f.signa, ["Hyundai Motor Company"])                          # 포스코는 4주 주기 — 이번 주 안 물음
        self.assertEqual(doc["carried"], ["포스코"])
        self.assertEqual(next(c for c in doc["checks"] if c["company"] == "포스코")["checkedAt"], week_ago)   # 직전 확인 시각 그대로
        rich = SignaFake({})
        eu.run(cfg, {**prev, "signaCreditsLeft": 5000}, NOW, client_id="", secret="", post=rich.post, get=rich.get, signa_key="K", office="US")
        self.assertEqual(rich.signa, ["Hyundai Motor Company", "POSCO"])              # 크레딧이 넉넉하면 매주 다
        old = SignaFake({})
        month_ago = (NOW - dt.timedelta(days=28)).isoformat(timespec="seconds")
        eu.run(cfg, {**prev, "checks": [dict(c, checkedAt=month_ago) for c in prev["checks"]]}, NOW, client_id="", secret="", post=old.post, get=old.get,
               signa_key="K", office="US")
        self.assertEqual(old.signa, ["Hyundai Motor Company", "POSCO"])               # 4주 지나면 다시

    def test_euipo_wins_when_approved(self):
        f = SignaFake({}, euipo_rows={"Hyundai Motor Company": [tm("019000001", "PLEOS", "2026-09-10", [9, 12])]})
        doc = eu.run(CFG_SIGNA, None, NOW, client_id="C", secret="S", post=f.post, get=f.get, signa_key="K")
        self.assertEqual(f.signa, [])
        self.assertEqual({c["via"] for c in doc["checks"]}, {"euipo"})
        self.assertNotIn("provider", doc)

    def test_config_has_unique_companies_and_queries(self):
        cfg = json.loads((Path(__file__).resolve().parents[1] / "data" / "trademark_watch.json").read_text(encoding="utf-8"))["euipo"]
        names = [a["company"] for a in cfg["applicants"]]
        self.assertEqual(len(names), len(set(names)))
        self.assertTrue(all(a["query"].startswith("*") and a["query"].endswith("*") for a in cfg["applicants"]))


if __name__ == "__main__":
    unittest.main()
