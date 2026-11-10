import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import epo_ops_watch as w  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 11, 14, 6, 40, tzinfo=KST)
GREEN = "idle (images=green:200, inpadoc=green:60, other=green:1000, retrieval=green:200, search=green:30)"
BLACK = "overloaded (images=green:50, inpadoc=green:30, other=green:1000, retrieval=green:50, search=black:0)"


def ex(cc, no, kind, date, applicants, title="Battery module", lang="en", family="123"):
    return {"@country": cc, "@doc-number": no, "@kind": kind, "@family-id": family, "bibliographic-data": {
        "publication-reference": {"document-id": [
            {"@document-id-type": "docdb", "country": {"$": cc}, "doc-number": {"$": no}, "kind": {"$": kind}, "date": {"$": date}},
            {"@document-id-type": "epodoc", "doc-number": {"$": f"{cc}{no}"}, "date": {"$": date}}]},
        "invention-title": [{"@lang": "de", "$": "Batteriemodul"}, {"@lang": lang, "$": title}],
        "parties": {"applicants": {"applicant": [
            {"@data-format": "epodoc", "applicant-name": {"name": {"$": f"{n.upper()} [KR]"}}} for n in applicants] + [
            {"@data-format": "original", "applicant-name": {"name": {"$": n}}} for n in applicants]}},
        "classifications-ipcr": {"classification-ipcr": [{"text": {"$": "H01M  50/204       A I"}}, {"text": {"$": "B60L  53/80 A I"}}]},
        "application-reference": {"document-id": {"@document-id-type": "epodoc", "doc-number": {"$": "EP24123456"}, "date": {"$": "20240305"}}},
        "priority-claims": {"priority-claim": {"document-id": {"@document-id-type": "epodoc", "doc-number": {"$": "KR20230045678"}, "date": {"$": "20230410"}}}},
    }}


def body(docs, total=None):
    return {"ops:world-patent-data": {"ops:biblio-search": {
        "@total-result-count": str(len(docs) if total is None else total),
        "ops:search-result": {"exchange-documents": [{"exchange-document": d} for d in docs] if len(docs) != 1 else {"exchange-document": docs[0]}}}}}


class Resp:
    def __init__(self, status, payload=None, text="", headers=None):
        self.status_code, self._p, self.text, self.headers = status, payload, text, headers or {"X-Throttling-Control": GREEN}

    def json(self):
        return self._p


NOT_FOUND = Resp(404, text='<fault xmlns="http://ops.epo.org"><code>SERVER.EntityNotFound</code><message>No results found</message></fault>')
ROBOT = Resp(403, text='<fault><code>CLIENT.RobotDetected</code><message>Recent behaviour implies you are a robot.</message></fault>',
             headers={"X-Throttling-Control": BLACK})


class Fake:
    def __init__(self, answers, token_status=200):
        self.answers, self.calls, self.posts, self.sleeps, self.token_status = answers, [], 0, [], token_status

    def post(self, url, **kw):
        self.posts += 1
        assert kw["auth"] == ("k", "s")
        return Resp(self.token_status, {"access_token": "tok", "expires_in": "1199"} if self.token_status == 200 else None)

    def get(self, url, params=None, headers=None, timeout=None):
        assert headers["Authorization"] == "Bearer tok"
        self.calls.append((params["q"], headers["X-OPS-Range"]))
        for name, resp in self.answers:
            if f'pa="{name}"' in params["q"]:
                return resp(headers["X-OPS-Range"]) if callable(resp) else resp
        return NOT_FOUND

    def sleep(self, s):
        self.sleeps.append(s)


CFG = {"companies": [
    {"company": "현대자동차", "query": "Hyundai Motor", "accept": "HYUNDAI MOTOR|현대자동차"},
    {"company": "포스코", "query": "POSCO", "accept": "^POSCO(?: HOLDINGS)?(?: INC| CO)?\\b|^(?:주식회사\\s*)?포스코(?:홀딩스)?(?:\\s*주식회사)?$",
     "exclude": "FUTURE\\s*M|INTERNATIONAL|퓨처엠"},
    {"company": "LG화학", "query": "LG Chem", "accept": "LG CHEM|엘지화학"},
]}


def go(fake, previous=None, now=NOW, only=None, key="k"):
    return w.run(CFG, previous, now, key=key, secret="s", post=fake.post, get=fake.get, sleep=fake.sleep, only=only)


class ThrottleTests(unittest.TestCase):
    def test_parse_header(self):
        self.assertEqual(w.throttle(BLACK), ("overloaded", "black", 0))
        self.assertEqual(w.throttle(GREEN), ("idle", "green", 30))
        self.assertEqual(w.throttle(None), (None, None, None))

    def test_gap(self):
        self.assertIsNone(w.gap("overloaded", "black", 0))
        self.assertIsNone(w.gap("busy", "red", 5))
        self.assertGreaterEqual(w.gap("idle", "green", 30), 3.0)
        self.assertGreaterEqual(w.gap("overloaded", "green", 30), 10.0)
        self.assertGreaterEqual(w.gap("busy", "yellow", 10), 12.0)


class ParseTests(unittest.TestCase):
    def test_single_and_list(self):
        total, rows = w.parse(body([ex("EP", "4567890", "A1", "20261104", ["Hyundai Motor Company", "Kia Corporation"])]))
        self.assertEqual(total, 1)
        r = rows[0]
        self.assertEqual(r["id"], "EP4567890A1")
        self.assertEqual(r["date"], "2026-11-04")
        self.assertEqual(r["title"], "Battery module")
        self.assertEqual(r["titleLang"], "en")
        self.assertIn("Hyundai Motor Company", r["applicants"])
        self.assertIn("HYUNDAI MOTOR COMPANY", r["applicants"])  # [KR] 꼬리 제거
        self.assertEqual(r["ipc"], ["H01M 50/204", "B60L 53/80"])
        self.assertEqual(r["priority"], {"number": "KR20230045678", "date": "2023-04-10", "country": "KR"})
        self.assertEqual(r["priorities"], [r["priority"]])
        self.assertEqual(r["applicationDate"], "2024-03-05")
        self.assertTrue(r["url"].endswith("pn%3DEP4567890A1"))
        total, rows = w.parse(body([ex("WO", "2026123456", "A1", "20261105", ["LG CHEM, LTD."]),
                                    ex("EP", "4567891", "A1", "20261104", ["LG Chem Ltd"])]))
        self.assertEqual([r["id"] for r in rows], ["WO2026123456A1", "EP4567891A1"])

    def test_title_fallback_when_no_english(self):
        _, rows = w.parse(body([ex("WO", "2026000001", "A1", "20261105", ["엘지화학"], title="전지", lang="ko")]))
        self.assertEqual(rows[0]["title"], "Batteriemodul")


class RunTests(unittest.TestCase):
    def test_first_run_is_baseline_then_new(self):
        hy = [ex("EP", "4567890", "A1", "20261104", ["Hyundai Motor Company"])]
        fake = Fake([("Hyundai Motor", Resp(200, body(hy)))])
        doc = go(fake)
        self.assertEqual(doc["status"], "complete")
        self.assertEqual(doc["fresh"], [])
        self.assertFalse(doc["filings"][0]["isNew"])
        self.assertIn('pd within "20260717 20261114"', fake.calls[0][0])   # 첫 실행 120일
        self.assertIn("(pn=EP or pn=WO)", fake.calls[0][0])
        self.assertEqual(doc["baselinedCompanies"], ["현대자동차", "포스코", "LG화학"])
        hy2 = hy + [ex("WO", "2026200000", "A1", "20261119", ["현대자동차주식회사", "기아 주식회사"])]
        fake2 = Fake([("Hyundai Motor", Resp(200, body(hy2)))])
        doc2 = go(fake2, previous=doc, now=NOW + dt.timedelta(days=7))
        self.assertEqual(doc2["fresh"], ["WO2026200000A1"])
        self.assertIn('pd within "20261017 20261121"', fake2.calls[0][0])  # 이후 35일
        new = next(f for f in doc2["filings"] if f["id"] == "WO2026200000A1")
        self.assertTrue(new["isNew"])
        self.assertEqual(new["companies"], ["현대자동차"])
        old = next(f for f in doc2["filings"] if f["id"] == "EP4567890A1")
        self.assertFalse(old["isNew"])

    def test_posco_affiliate_excluded_and_others_noted(self):
        po = [ex("EP", "1000001", "A1", "20261104", ["POSCO FUTURE M CO., LTD."]),
              ex("WO", "2026000002", "A1", "20261105", ["POSCO Co., Ltd", "Research Institute of Industrial Science & Technology"])]
        doc = go(Fake([("POSCO", Resp(200, body(po)))]))
        c = next(c for c in doc["checks"] if c["company"] == "포스코")
        self.assertEqual((c["total"], c["matched"]), (2, 1))
        self.assertIn("POSCO FUTURE M CO., LTD.", c["otherApplicants"])
        self.assertEqual([f["id"] for f in doc["filings"]], ["WO2026000002A1"])

    def test_zero_results_is_ok_not_failure(self):
        doc = go(Fake([]))
        self.assertEqual(doc["status"], "complete")
        self.assertTrue(all(c["status"] == "ok" and c["total"] == 0 for c in doc["checks"]))

    def test_black_signal_stops_remaining(self):
        black = Resp(200, body([ex("EP", "4567890", "A1", "20261104", ["Hyundai Motor Company"])]), headers={"X-Throttling-Control": BLACK})
        fake = Fake([("Hyundai Motor", black)])
        doc = go(fake)
        self.assertEqual(len(fake.calls), 1)                  # 멈춘 뒤 더 묻지 않음
        self.assertEqual([c["status"] for c in doc["checks"]], ["ok", "waiting", "waiting"])
        self.assertIn("black", doc["checks"][1]["reason"])
        self.assertEqual(doc["status"], "partial")
        self.assertEqual(doc["throttle"]["search"], "black")
        self.assertEqual(fake.sleeps, [])
        self.assertEqual(doc["baselinedCompanies"], ["현대자동차"])

    def test_robot_403_stops_and_is_waiting(self):
        fake = Fake([("Hyundai Motor", ROBOT)])
        doc = go(fake)
        self.assertEqual(len(fake.calls), 1)
        self.assertEqual(doc["status"], "waiting")
        self.assertTrue(all(c["status"] == "waiting" for c in doc["checks"]))
        self.assertIn("CLIENT.RobotDetected", doc["checks"][0]["reason"])

    def test_retry_asks_only_unsettled_and_keeps_baseline_rule(self):
        black = Resp(200, body([ex("EP", "4567890", "A1", "20261104", ["Hyundai Motor Company"])]), headers={"X-Throttling-Control": BLACK})
        first = go(Fake([("Hyundai Motor", black)]))
        self.assertEqual(w.plan(first, NOW + dt.timedelta(hours=8)), {"포스코", "LG화학"})
        lg = [ex("WO", "2026111111", "A1", "20261105", ["LG CHEM, LTD."])]
        fake = Fake([("LG Chem", Resp(200, body(lg)))])
        doc = go(fake, previous=first, now=NOW + dt.timedelta(hours=8), only={"포스코", "LG화학"})
        self.assertEqual(len(fake.calls), 2)
        self.assertEqual(doc["status"], "complete")
        self.assertEqual(doc["fresh"], [])                    # LG화학은 이번이 기준선
        self.assertIn('pd within "20260717', fake.calls[1][0])
        self.assertEqual(doc["retry"]["companies"], ["포스코", "LG화학"])
        self.assertEqual(len(doc["filings"]), 2)
        self.assertEqual(w.plan(doc, NOW + dt.timedelta(days=1)), set())

    def test_plan(self):
        self.assertIsNone(w.plan(None, NOW))
        wed = NOW + dt.timedelta(days=4)   # 11-18(수) — 직전이 나흘 전이어도 평일엔 EPO를 부르지 않는다
        self.assertEqual(w.plan({"schema": w.SCHEMA, "generatedAt": NOW.isoformat(), "status": "complete"}, wed), set())
        self.assertEqual(w.plan({"schema": w.SCHEMA, "generatedAt": NOW.isoformat(), "status": "partial", "checks": []}, wed), set())
        self.assertIsNone(w.plan({"schema": w.SCHEMA, "generatedAt": NOW.isoformat(), "status": "complete"}, wed, force=True))
        self.assertIsNone(w.plan({"schema": w.SCHEMA, "generatedAt": (NOW - dt.timedelta(days=7)).isoformat(), "status": "partial"}, NOW))
        self.assertIsNone(w.plan({"schema": w.SCHEMA, "generatedAt": NOW.isoformat(), "status": "complete"}, NOW, force=True))

    def test_pagination(self):
        page1 = [ex("EP", str(4000000 + i), "A1", "20261104", ["Hyundai Motor Company"]) for i in range(100)]
        page2 = [ex("WO", str(2026000000 + i), "A1", "20261105", ["Hyundai Motor Company"]) for i in range(12)]
        fake = Fake([("Hyundai Motor", lambda rng: Resp(200, body(page1 if rng == "1-100" else page2, total=112)))])
        doc = go(fake)
        self.assertEqual([r for q, r in fake.calls if "Hyundai" in q], ["1-100", "101-200"])
        self.assertEqual(next(c for c in doc["checks"] if c["company"] == "현대자동차")["matched"], 112)

    def test_truncated_baseline_catches_up_once(self):
        page = [ex("EP", str(5000000 + i), "A1", "20261104", ["POSCO Co., Ltd"]) for i in range(100)]
        first = go(Fake([("POSCO", lambda rng: Resp(200, body(page, total=331)))]))
        po = next(c for c in first["checks"] if c["company"] == "포스코")
        self.assertTrue(po["truncated"] and po["baseline"])
        later = NOW + dt.timedelta(days=7)
        unread = ex("WO", "2026999001", "A1", "20261103", ["POSCO Co., Ltd"])      # 기준선 때 잘려 못 읽은 공개(기준선 창 안)
        newer = ex("WO", "2026999002", "A1", "20261119", ["POSCO Co., Ltd"])       # 기준선 창 뒤 공개 — 진짜 새 공개
        doc = go(Fake([("POSCO", Resp(200, body(page[:3] + [unread, newer])))]), previous=first, now=later)
        self.assertEqual(doc["fresh"], ["WO2026999002A1"])
        po2 = next(c for c in doc["checks"] if c["company"] == "포스코")
        self.assertEqual(po2["catchup"], {"to": "2026-11-14", "asBaseline": 4})
        doc3 = go(Fake([("POSCO", Resp(200, body([ex("WO", "2026999003", "A1", "20261110", ["POSCO Co., Ltd"])])))]), previous=doc, now=later + dt.timedelta(days=7))
        self.assertEqual(doc3["fresh"], ["WO2026999003A1"])                         # 한 번만 — 다음부터는 평소대로
        self.assertNotIn("catchup", next(c for c in doc3["checks"] if c["company"] == "포스코"))

    def test_missing_key_fails_without_requests(self):
        fake = Fake([])
        doc = go(fake, key="")
        self.assertEqual(doc["status"], "failed")
        self.assertEqual(fake.posts, 0)
        self.assertEqual(fake.calls, [])
        self.assertIn("EPO_OPS_KEY", doc["checks"][0]["error"])

    def test_token_error_has_no_secret(self):
        doc = go(Fake([], token_status=401))
        self.assertEqual(doc["checks"][0]["error"], "토큰 HTTP 401")

    def test_old_filings_pruned(self):
        prev = {"schema": w.SCHEMA, "generatedAt": (NOW - dt.timedelta(days=7)).isoformat(), "status": "complete",
                "baselinedCompanies": ["현대자동차", "포스코", "LG화학"], "seen": ["EP1A1"],
                "filings": [{"id": "EP1A1", "date": "2026-01-01", "companies": ["현대자동차"], "isNew": False}]}
        doc = go(Fake([]), previous=prev)
        self.assertEqual(doc["filings"], [])
        self.assertIn("EP1A1", doc["seen"])


class KrLinkTests(unittest.TestCase):
    def test_kr_application_forms(self):
        self.assertEqual(w.kr_application({"number": "KR20250055682"}), "1020250055682")
        self.assertEqual(w.kr_application({"number": "20250055682", "country": "KR"}), "1020250055682")
        self.assertEqual(w.kr_application({"number": "10-2025-0055682", "country": "KR"}), "1020250055682")
        self.assertEqual(w.kr_application({"number": "KR20200012345"}), "1020200012345")
        self.assertEqual(w.kr_application({"number": "KR20250001234U"}), "2020250001234")
        self.assertIsNone(w.kr_application({"number": "US202563123456", "country": "US"}))
        self.assertIsNone(w.kr_application({"number": "KR2025005568"}))   # 자릿수 틀림
        self.assertIsNone(w.kr_application(None))

    def test_priorities_all_claims_and_formats(self):
        bd = {"priority-claims": {"priority-claim": [
            {"document-id": [{"@document-id-type": "docdb", "country": {"$": "KR"}, "doc-number": {"$": "20250055682"}, "date": {"$": "20250428"}},
                             {"@document-id-type": "epodoc", "doc-number": {"$": "KR20250055682"}, "date": {"$": "20250428"}}]},
            {"document-id": {"@document-id-type": "docdb", "country": {"$": "US"}, "doc-number": {"$": "202563123456"}, "date": {"$": "20250301"}}},
            {"document-id": {"@document-id-type": "original", "doc-number": {"$": "1020250077777"}}}]}}
        pr = w.priorities(bd)
        self.assertEqual(pr[0], {"number": "KR20250055682", "date": "2025-04-28", "country": "KR"})
        self.assertEqual(pr[1], {"number": "US202563123456", "date": "2025-03-01", "country": "US"})
        self.assertEqual(pr[2]["number"], "1020250077777")

    def kipris_file(self, items):
        import json, tempfile
        f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        json.dump({"items": items}, f, ensure_ascii=False)
        f.close()
        return f.name

    def test_index_and_link(self):
        path = self.kipris_file([
            {"company": "기아", "applicationNumber": "1020250055682", "publicationNumber": "1020260159700", "publicationDate": "20261105",
             "title": "연료전지 스택의 셀 전압 제어 장치", "ipc": "H01M 8/04858|B60L 58/40", "registerStatus": "공개"},
            {"company": "한국타이어앤테크놀로지", "applicationNumber": "1020250011111", "publicationDate": "20261020", "title": "타이어", "ipc": "B60C 11/03"}])
        idx = w.kipris_index([path, "/nonexistent.json"])
        self.assertEqual(idx["1020250055682"]["ipc"], ["H01M", "B60L"])
        self.assertEqual(idx["1020250011111"]["company"], "한국타이어")
        fs = [{"id": "EP1A1", "priorities": [{"number": "KR20250055682", "country": "KR"}]},
              {"id": "WO2A1", "priority": {"number": "KR20249999999"}},                       # 예전 저장 꼴(priority 하나)
              {"id": "EP3A1", "priorities": [{"number": "US202563123456", "country": "US"}]},
              {"id": "EP4A1", "kr": {"stale": 1}},
              {"id": "WO5A1", "priority": {"number": "WO2025KR012345"}},                     # 한국 특허청 PCT
              {"id": "WO6A1", "priority": {"number": "WO2025IB054321"}},                     # 국제사무국 PCT
              {"id": "EP7A1", "priorities": [{"number": "EP25123456", "country": "EP"}, {"number": "WO2025IB000001"}]}]
        t = w.link_kr(fs, idx)
        self.assertEqual(t, {"linked": 1, "krOutside": 1, "krPct": 1, "pct": 2, "abroad": 1, "none": 1})
        self.assertEqual(fs[4]["krPct"], "WO2025KR012345")
        self.assertEqual(fs[5]["pctPriority"], ["WO2025IB054321"])
        self.assertEqual(fs[6]["pctPriority"], ["WO2025IB000001"])     # PCT가 있으면 외국 출원보다 PCT 갈래
        self.assertEqual(fs[0]["kr"]["title"], "연료전지 스택의 셀 전압 제어 장치")
        self.assertEqual(fs[0]["kr"]["publicationDate"], "2026-11-05")
        self.assertNotIn("ipc", fs[0]["kr"])
        self.assertEqual(fs[1]["krPriority"], "1020249999999")
        self.assertEqual(fs[2]["priorityAbroad"], ["US"])
        self.assertNotIn("kr", fs[3])                       # 지난 연결은 지우고 다시

    def test_new_field_waits_for_history_then_flags(self):
        idx = {"1020250055682": {"applicationNumber": "1020250055682", "company": "포스코", "ipc": ["C25B"], "title": "수전해"}}
        base = {"id": "EP0A1", "companies": ["포스코"], "ipc": ["C21D 8/02"], "date": "2026-09-01"}
        fresh = {"id": "WO9A1", "companies": ["포스코"], "ipc": ["C25B 1/04", "C21D 9/46"], "date": "2026-11-12",
                 "priorities": [{"number": "KR20250055682", "country": "KR"}]}
        doc = {"filings": [dict(base), dict(fresh)]}
        w.annotate(doc, None, idx, NOW, fresh=["WO9A1"])
        self.assertEqual(doc["ipcHistorySince"], "2026-07-17")
        self.assertEqual(doc["newFieldFrom"], "2027-01-13")
        self.assertNotIn("newField", doc["filings"][1])        # 이력 180일 전 — 판정 안 함
        self.assertEqual(doc["ipcHistory"]["포스코"], ["C21D", "C25B"])
        later = NOW + dt.timedelta(days=70)
        doc2 = {"filings": [dict(base), dict(fresh, id="EP8A1", ipc=["C25B 1/04", "H01M 8/18"])]}
        prev = {"ipcHistorySince": "2026-07-01", "ipcHistory": {"포스코": ["C21D"]}}
        w.annotate(doc2, prev, idx, later, fresh=["EP8A1"])
        # 국내 짝(C25B)은 판정 뒤에 더해 '처음'을 가리지 않는다
        self.assertEqual(doc2["filings"][1]["newField"], {"포스코": ["C25B", "H01M"]})
        self.assertEqual(doc2["krLinks"]["newField"], 1)
        self.assertEqual(doc2["filings"][1]["kr"]["title"], "수전해")

    def test_run_links_with_kipris_index(self):
        idx = {"1020230045678": {"applicationNumber": "1020230045678", "company": "현대자동차", "ipc": ["H01M"], "title": "배터리 모듈",
                                  "publicationNumber": "1020240000001", "publicationDate": "2024-10-01"}}
        hy = [ex("EP", "4567890", "A1", "20261104", ["Hyundai Motor Company"])]
        doc = w.run(CFG, None, NOW, key="k", secret="s", post=Fake([]).post, get=Fake([("Hyundai Motor", Resp(200, body(hy)))]).get,
                    sleep=lambda s: None, kipris=idx)
        f = doc["filings"][0]
        self.assertEqual(f["kr"]["title"], "배터리 모듈")
        self.assertEqual(doc["krLinks"]["linked"], 1)
        self.assertIn("현대자동차", doc["ipcHistory"])

    def test_shapes_hide_numbers(self):
        shapes = w.prio_shapes([{"priorities": [{"number": "KR20250055682", "country": "KR"}, {"number": "US63/123,456", "country": "US"}]}])
        self.assertEqual(dict(shapes), {"KR:KR99999999999": 1, "US:US99999999": 1})
        self.assertEqual(w.prio_kind({"number": "WO2025KR012345"}), "WO-KR")
        self.assertEqual(w.prio_kind({"number": "WO2025IB054321"}), "WO")
        self.assertEqual(w.prio_kind({"number": "EP25123456"}), "EP")

    def test_fit_trims_oldest_existing_first(self):
        doc = {"filings": [{"id": f"EP{i}A1", "date": f"2026-0{1 + i % 9}-01", "title": "x" * 300, "isNew": i == 0} for i in range(40)]}
        w.fit(doc, limit=6000)
        self.assertLess(len(__import__("json").dumps(doc, ensure_ascii=False).encode()), 6000)
        self.assertTrue(any(f["id"] == "EP0A1" for f in doc["filings"]))      # 새 공개는 남김
        self.assertGreater(doc["trimmed"], 0)


if __name__ == "__main__":
    unittest.main()
