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
        self.assertEqual(eu.signa._status({"stage": "examining"}, {"code": "630"}), "examining(USPTO 코드 630)")   # 숫자 코드만 보이지 않게
        self.assertEqual(eu.signa._status({"stage": "examining"}, {"code": "APPLICATION_PUBLISHED"}), "APPLICATION_PUBLISHED")
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


def us(no, mark, day, classes, oid, who, bases=(), updated=None):
    """Signa 미국 줄(11-14 탐침 229 모양): owners[].id·filing_bases[].basis_type·updated_at."""
    return {"id": f"tm_{no}", "object": "trademark", "mark_text": mark, "mark_feature_type": "word",
            "status": {"primary": "pending", "stage": "examining", "raw": {"code": "630"}}, "office_code": "US", "filing_route": "direct_national",
            "application_number": no, "filing_date": day, "nice_classes": classes, "updated_at": f"{updated or day}T10:00:00.000Z",
            "owners": [{"id": oid, "name": who, "country_code": "KR", "entity_id": "ent_1"}],
            "filing_bases": [{"basis_type": b, "nice_class": classes[0]} for b in bases]}


class ListFake(SignaFake):
    """owner_id 목록 조회(쪽마다 10크레딧)와 /v1/offices(크레딧 0)까지 흉내 낸다."""
    def __init__(self, by_owner, by_id, list_status=200, **kw):
        super().__init__(by_owner, **kw)
        self.by_id, self.list_status, self.id_calls, self.office_calls = by_id, list_status, [], 0

    def get(self, url, params=None, headers=None, timeout=None):
        if url == eu.signa.OFFICES_URL:
            self.office_calls += 1
            return SR(200, {"object": "list", "data": [{"code": "EM", "last_synced_at": "2026-11-13T07:06:04.087Z"}, {"code": "US", "last_synced_at": "2026-11-13T13:14:40.468Z"}]})
        if url == eu.signa.SEARCH_URL and "owner_id" in (params or {}):
            self.id_calls.append(dict(params))
            if self.list_status != 200:
                return SR(self.list_status, {"type": "error"})
            self.left -= 10
            rows = [r for i in params["owner_id"].split(",") for r in self.by_id.get(i, [])]
            if params.get("updated_at_gte"):
                rows = [r for r in rows if r["updated_at"][:10] >= params["updated_at_gte"]]
            return SR(200, {"object": "list", "data": rows, "has_more": False, "pagination": {"cursor": None}}, {"X-Credits-Remaining": str(self.left)})
        return super().get(url, params=params, headers=headers, timeout=timeout)


class SignaOwnerList(unittest.TestCase):
    """11-14 Signa 답장: 회사 이름 조회에서 얻은 출원인 id를 모아 두고, 다음부터는 id 목록 한 번으로 전 회사를 본다(평일 매일)."""
    CFG_US = {**CFG_SIGNA, "applicants": CFG_SIGNA["applicants"] + [{"company": "KG모빌리티", "industry": "auto", "query": "*KG Mobility*", "phrase": True}]}
    H_OLD = us("99000001", "IONIQ", "2026-09-01", [12], "own_h1", "Hyundai Motor Company", ["use_in_commerce"])
    P_OLD = us("99000002", "PosZET", "2026-08-20", [6], "own_p1", "POSCO Co.")
    JUNK = us("99000003", "E-BIKE", "2026-10-01", [12], "own_junk", "Zweirad Union e-mobility GmbH & Co. KG")

    def monday(self):
        f = ListFake({"Hyundai Motor Company": [self.H_OLD], "POSCO": [self.P_OLD, self.JUNK], "KG Mobility": []}, {})
        doc = eu.run(self.CFG_US, None, NOW, client_id="", secret="", post=f.post, get=f.get, signa_key="K", office="US")
        return f, doc

    def test_ids_are_harvested_from_accepted_rows_and_phrase_is_per_company(self):
        f, doc = self.monday()
        self.assertEqual(f.signa, ["Hyundai Motor Company", "POSCO", "KG Mobility"])
        self.assertEqual([p.get("owner_name_match") for p in f.signa_params], [None, None, "phrase"])     # KG모빌리티만 phrase(낱말 맞춤이 'Co. KG'를 데려옴)
        self.assertEqual(doc["ownerIds"], {"현대자동차": {"own_h1": "Hyundai Motor Company"}, "포스코": {"own_p1": "POSCO Co."}})   # 회사 규칙에 안 맞는 출원인 id는 안 모은다
        self.assertEqual(sorted(doc["discoveredAt"]), ["KG모빌리티", "포스코", "현대자동차"])
        self.assertEqual((f.id_calls, doc.get("listCheckedAt"), doc["providerSyncedAt"]), ([], None, "2026-11-13T13:14:40.468Z"))
        self.assertEqual(next(x for x in doc["filings"] if x["applicationNumber"] == "99000001")["basis"], ["use_in_commerce"])
        self.assertFalse(any(x["isNew"] for x in doc["filings"]))                                          # 첫 읽기는 기준선

    def test_weekday_list_query_covers_every_company_in_one_request(self):
        _, mon = self.monday()
        new = us("99000010", "NEXO ZERO", "2026-11-09", [12], "own_h1", "Hyundai Motor Company", ["intent_to_use"], updated="2026-11-10")
        late = us("98000001", "OLD NAME", "2026-08-01", [12], "own_h1", "Hyundai Motor Company")        # 이름 조회(100줄 한도)가 못 본 예전 출원
        f = ListFake({}, {"own_h1": [new, self.H_OLD, late], "own_p1": [self.P_OLD]})
        tue = eu.run(self.CFG_US, mon, NOW + dt.timedelta(days=1), client_id="", secret="", post=f.post, get=f.get, signa_key="K", office="US",
                     only_unsettled=True, daily_list=True)
        self.assertEqual((f.signa, len(f.id_calls)), ([], 1))                                               # 이름 조회 0번, 목록 조회 1번(10크레딧)
        q = f.id_calls[0]
        self.assertEqual((q["owner_id"], q["office"], q["filing_date_gte"], "updated_at_gte" in q),
                         ("own_h1,own_p1", "US", (NOW.date() + dt.timedelta(days=1) - dt.timedelta(days=120)).isoformat(), False))   # 첫 목록 조회는 출원일 창 전체
        by = {x["applicationNumber"]: x for x in tue["filings"]}
        self.assertEqual((by["99000010"]["isNew"], by["99000010"]["basis"], by["99000010"]["tier"]), (True, ["intent_to_use"], "B"))
        self.assertEqual((by["98000001"]["isNew"], by["98000001"]["baseline"]), (False, True))            # 첫 목록 조회에 딸려 온 3주 넘은 출원은 기준선
        self.assertEqual(tue["fresh"], ["uspto:99000010"])
        self.assertEqual([(c["company"], c["status"], c.get("mode")) for c in tue["checks"]],
                         [("현대자동차", "ok", "list"), ("포스코", "ok", "list"), ("KG모빌리티", "ok", None)])   # id 없는 회사는 평일엔 직전 결과 그대로
        self.assertEqual((tue["list"]["pages"], tue["list"]["rows"], tue["list"]["companies"], tue["signaCreditsLeft"]), (1, 4, 2, 9990))
        self.assertEqual(tue["status"], "complete")
        # 다음 평일: 직전 목록 조회 3일 전부터 Signa가 새로 넣거나 고친 줄만
        f2 = ListFake({}, {"own_h1": [new, self.H_OLD, late], "own_p1": [self.P_OLD]})
        wed = eu.run(self.CFG_US, tue, NOW + dt.timedelta(days=2), client_id="", secret="", post=f2.post, get=f2.get, signa_key="K", office="US",
                     only_unsettled=True, daily_list=True)
        self.assertEqual(f2.id_calls[0]["updated_at_gte"], (NOW.date() + dt.timedelta(days=1) - dt.timedelta(days=3)).isoformat())
        self.assertEqual((wed["fresh"], wed["list"]["rows"], wed["list"]["updatedSince"]), ([], 1, f2.id_calls[0]["updated_at_gte"]))
        self.assertEqual(len(wed["filings"]), len(tue["filings"]))                                          # 안 딸려 온 줄을 지우지 않는다
        # daily_list가 아니면(예전 평일 재시도) 정상인 회사는 그대로 둔다 — 목록 조회도 안 한다
        f3 = ListFake({}, {"own_h1": [new]})
        eu.run(self.CFG_US, tue, NOW + dt.timedelta(days=2), client_id="", secret="", post=f3.post, get=f3.get, signa_key="K", office="US", only_unsettled=True)
        self.assertEqual((f3.signa, f3.id_calls), ([], []))

    def test_list_failure_is_unconfirmed_and_names_are_rechecked_every_four_weeks(self):
        _, mon = self.monday()
        bad = ListFake({}, {}, list_status=500)
        doc = eu.run(self.CFG_US, mon, NOW + dt.timedelta(days=1), client_id="", secret="", post=bad.post, get=bad.get, signa_key="K", office="US",
                     only_unsettled=True, daily_list=True)
        self.assertEqual([(c["status"], c.get("error")) for c in doc["checks"][:2]], [("failed", "Signa HTTP 500"), ("failed", "Signa HTTP 500")])
        self.assertEqual((bad.signa, doc["list"]["error"], doc.get("listCheckedAt")), ([], "Signa HTTP 500", None))   # 이름 조회로 돌아가 크레딧을 쓰지 않는다
        self.assertEqual(len(doc["filings"]), len(mon["filings"]))
        # 월요일 정기 실행: 28일이 안 지났으면 id 있는 회사는 목록으로, 지났으면 회사 이름으로 다시 찾는다(새 출원인 기록)
        wk = ListFake({"KG Mobility": []}, {"own_h1": [self.H_OLD], "own_p1": [self.P_OLD]})
        eu.run(self.CFG_US, mon, NOW + dt.timedelta(days=7), client_id="", secret="", post=wk.post, get=wk.get, signa_key="K", office="US")
        self.assertEqual((wk.signa, len(wk.id_calls)), (["KG Mobility"], 1))
        late = ListFake({"Hyundai Motor Company": [self.H_OLD], "POSCO": [self.P_OLD], "KG Mobility": []}, {})
        doc5 = eu.run(self.CFG_US, mon, NOW + dt.timedelta(days=35), client_id="", secret="", post=late.post, get=late.get, signa_key="K", office="US")
        self.assertEqual((late.signa, late.id_calls), (["Hyundai Motor Company", "POSCO", "KG Mobility"], []))
        self.assertEqual(doc5["discoveredAt"]["현대자동차"][:10], (NOW + dt.timedelta(days=35)).date().isoformat())

    def test_one_prefetched_request_serves_both_offices_and_madrid_rows_carry_the_ir_date(self):
        # trademark_watch.main이 offices=EM,US 한 요청으로 받아 온 줄을 관청별 run()에 넘긴다 — run()은 Signa를 다시 부르지 않는다
        _, mon = self.monday()
        new = us("99000010", "NEXO ZERO", "2026-11-09", [12], "own_h1", "Hyundai Motor Company", ["intent_to_use"])
        em = dict(us("019500001", "EU ONLY", "2026-11-09", [12], "own_h1", "Hyundai Motor Company"), office_code="EM")
        # 탐침 230에서 본 꼴: 미국 지정일 2026-07-22인 마드리드 줄의 registration_date(국제등록일)가 2019-06-24
        ir = dict(us("79400001", "PosZET", "2026-11-08", [6], "own_p1", "POSCO Co."), filing_route="madrid_designation", ir_number="1481965", registration_date="2019-06-24")
        pre = {"rows": [eu.signa._row(x) for x in (new, em, ir)], "left": 9000, "pages": 1, "truncated": False, "error": None, "updatedSince": "2026-11-07"}
        f = ListFake({}, {})
        tue = eu.run(self.CFG_US, mon, NOW + dt.timedelta(days=1), client_id="", secret="", post=f.post, get=f.get, signa_key="K", office="US",
                     only_unsettled=True, daily_list=True, prefetched=pre)
        self.assertEqual((f.signa, f.id_calls), ([], []))
        self.assertEqual(sorted(tue["fresh"]), ["uspto:79400001", "uspto:99000010"])                      # 유럽 줄은 미국 실행에 안 섞인다
        self.assertEqual((tue["list"]["combined"], tue["list"]["rows"], tue["list"]["updatedSince"], tue["signaCreditsLeft"]), (True, 2, "2026-11-07", 9000))
        pz = next(x for x in tue["filings"] if x["applicationNumber"] == "79400001")
        self.assertEqual((pz["route"], pz["ir"]), ("마드리드 지정", {"number": "1481965", "registered": "2019-06-24"}))
        self.assertNotIn("ir", next(x for x in tue["filings"] if x["applicationNumber"] == "99000010"))
        # 한 요청이 실패하면 그 회사들은 미확인 — 관청별로 다시 묻지 않는다
        bad = eu.run(self.CFG_US, mon, NOW + dt.timedelta(days=1), client_id="", secret="", post=f.post, get=f.get, signa_key="K", office="US",
                     only_unsettled=True, daily_list=True, prefetched={"rows": [], "error": "Signa HTTP 500", "updatedSince": None})
        self.assertEqual(([c["status"] for c in bad["checks"][:2]], f.id_calls), (["failed", "failed"], []))
        # 여러 관청이면 offices, 하나면 office
        seen = []

        def get(url, params=None, headers=None, timeout=None):
            seen.append(dict(params))
            return SR(200, {"data": [], "has_more": False})
        eu.signa.search_ids(["own_1"], "2026-07-01", key="K", get=get, office="EM,US")
        eu.signa.search_ids(["own_1"], "2026-07-01", key="K", get=get, office="US")
        self.assertEqual([(p.get("offices"), p.get("office")) for p in seen], [("EM,US", None), (None, "US")])
        plan = eu.list_plan(tue, NOW + dt.timedelta(days=2), only_unsettled=True, daily_list=True, signa_key="K")
        self.assertEqual((sorted(plan["list_ids"]), plan["updated_since"]), (["포스코", "현대자동차"], (NOW.date() + dt.timedelta(days=1) - dt.timedelta(days=3)).isoformat()))

    def test_id_list_is_chunked_and_paged_with_a_page_limit(self):
        calls = []

        def get(url, params=None, headers=None, timeout=None):
            calls.append(dict(params))
            more = len(calls) < 9
            return SR(200, {"data": [us(f"9{len(calls):07d}", "M", "2026-11-01", [12], "own_1", "X")], "has_more": more, "pagination": {"cursor": f"c{len(calls)}" if more else None}},
                      {"X-Credits-Remaining": str(1000 - 10 * len(calls))})
        rows, left, pages, trunc = eu.signa.search_ids([f"own_{i}" for i in range(50)], "2026-07-01", key="K", get=get, office="US")
        self.assertEqual((len(rows), pages, trunc, left), (eu.signa.MAX_PAGES, eu.signa.MAX_PAGES, True, 1000 - 10 * eu.signa.MAX_PAGES))   # 쪽 한도에서 멈추고 '덜 읽음'
        self.assertEqual((len(calls[0]["owner_id"].split(",")), calls[1].get("cursor")), (eu.signa.ID_CHUNK, "c1"))
        self.assertEqual(eu.signa.BASIS_KO["intent_to_use"], "사용 의사(1B)")


if __name__ == "__main__":
    unittest.main()
