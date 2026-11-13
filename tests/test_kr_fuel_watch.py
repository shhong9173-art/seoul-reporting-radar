"""국내 표시연비 신고 감시: 기준선, 새 모델명·주행거리 변화·사양 추가, 활용신청 전 미설정, 일괄 갱신, 쪽 넘김."""
import datetime as dt
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import kr_fuel_watch as k  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 10, 29, 6, 10, tzinfo=KST)


def row(comp, model, year="2026", fuel="휘발유", eff="12.5", rng="", reg="20261020", **kw):
    r = {f: "" for f in k.FIELDS}
    r.update({"COMP_NM": comp, "MODEL_NM": model, "YEAR": year, "FUEL_NM": fuel, "DISPLAY_EFF": eff,
              "RANGE_PER_CHARGE": rng, "DATA_REG_DT": reg, **kw})
    return r


class Resp:
    def __init__(self, text, status=200):
        self.text, self.status_code = text, status


def api(rows, per=None):
    """Fake CAREFF_LIST: pages of `per` rows (default all) in the swagger JSON shape (no 'response' wrapper)."""
    calls = []

    def get(url, params=None, headers=None, timeout=None):
        calls.append(params)
        n = per or len(rows) or 1
        p = int(params["pageNo"])
        chunk = rows[(p - 1) * n: p * n]
        return Resp(json.dumps({"header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE"},
                                "body": {"items": {"item": chunk}, "pageNo": p, "totalCount": len(rows), "numOfRows": n}}, ensure_ascii=False))
    get.calls = calls
    return get


BASE = [row("현대자동차(주)", "아반떼 1.6 가솔린", eff="15.0"),
        row("기아(주)", "EV3 롱레인지", fuel="전기", eff="5.5", rng="501"),
        row("폭스바겐그룹코리아(주)", "A6 45 TFSI quattro"),
        row("폭스바겐그룹코리아(주)", "ID.4 Pro", fuel="전기", rng="430"),
        row("(주)테슬라코리아", "Model Y")]


class Watch(unittest.TestCase):
    def test_company_mapping(self):
        self.assertEqual(k.company_of(BASE[0]), "현대차")
        self.assertEqual(k.company_of(BASE[1]), "기아")
        self.assertEqual(k.company_of(BASE[2]), "아우디코리아")
        self.assertEqual(k.company_of(BASE[3]), "폭스바겐코리아")
        self.assertIsNone(k.company_of(BASE[4]))  # 출입처 아님
        self.assertEqual(k.company_of(row("현대자동차(주)", "제네시스 GV80 3.5T")), "현대차")
        self.assertEqual(k.company_of(row("케이지모빌리티(주)", "토레스 EVX")), "KG모빌리티")
        self.assertEqual(k.company_of(row("한국지엠(주)", "트랙스 크로스오버")), "한국GM")

    def test_first_run_is_baseline_then_new_rows_are_classified(self):
        first = k.run("key", now=NOW, previous=None, get=api(BASE), sleep=lambda s: None)
        self.assertEqual(first["status"], "complete")
        self.assertEqual(first["vehicles"], [])
        self.assertEqual(first["checks"][0]["beatRows"], 4)
        later = BASE + [row("현대자동차(주)", "아반떼 N 2.0 터보", year="2027", eff="10.6", reg="20261028"),
                        row("기아(주)", "EV3 롱레인지", year="2027", fuel="전기", eff="5.6", rng="525", reg="20261028"),
                        row("현대자동차(주)", "아반떼 1.6 가솔린", year="2027", eff="15.0", reg="20261028")]
        second = k.run("key", now=NOW + dt.timedelta(days=1), previous=first, get=api(later), sleep=lambda s: None)
        kinds = {(v["model"], v["year"]): v["kind"] for v in second["vehicles"]}
        self.assertEqual(kinds[("아반떼 N 2.0 터보", "2027")], "새 모델명")
        self.assertEqual(kinds[("EV3 롱레인지", "2027")], "주행거리 변화")
        self.assertEqual(kinds[("아반떼 1.6 가솔린", "2027")], "사양·연식 추가")
        ev = [v for v in second["vehicles"] if v["model"] == "EV3 롱레인지"][0]
        self.assertEqual(ev["compare"], {"previousRanges": [501]})
        self.assertEqual(ev["registered"], "2026-10-28")
        self.assertTrue(all(v["isNew"] for v in second["vehicles"]))
        third = k.run("key", now=NOW + dt.timedelta(days=2), previous=second, get=api(later), sleep=lambda s: None)
        self.assertFalse(any(v["isNew"] for v in third["vehicles"]))

    def test_key_not_registered_is_unset_not_zero(self):
        xml = ("<OpenAPI_ServiceResponse><cmmMsgHeader><errMsg>SERVICE ERROR</errMsg><returnAuthMsg>SERVICE_KEY_IS_NOT_REGISTERED_ERROR"
               "</returnAuthMsg><returnReasonCode>30</returnReasonCode></cmmMsgHeader></OpenAPI_ServiceResponse>")
        doc = k.run("key", now=NOW, previous=None, get=lambda *a, **kw: Resp(xml), sleep=lambda s: None)
        self.assertEqual(doc["status"], "unset")
        self.assertIn("활용신청 필요", doc["checks"][0]["error"])
        self.assertEqual(k.run("", now=NOW)["checks"][0]["status"], "unset")

    def test_failure_keeps_previous(self):
        first = k.run("key", now=NOW, previous=None, get=api(BASE), sleep=lambda s: None)
        first["vehicles"] = [{"id": "kf:x", "firstSeen": "2026-10-29T06:10:00+09:00", "registered": "2026-10-28", "model": "m", "company": "현대차"}]

        def boom(*a, **kw):
            raise ConnectionError("x")
        doc = k.run("key", now=NOW, previous=first, get=boom, sleep=lambda s: None)
        self.assertEqual(doc["status"], "failed")
        self.assertEqual(doc["vehicles"][0]["id"], "kf:x")
        self.assertEqual(doc["seenKeys"], first["seenKeys"])

    def test_paging_and_bulk_reload(self):
        many = [row("현대자동차(주)", f"모델 {i}") for i in range(2500)]
        get = api(many, per=1000)
        first = k.run("key", now=NOW, previous=None, get=get, sleep=lambda s: None)
        self.assertEqual(len(get.calls), 3)
        self.assertEqual(first["checks"][0]["rows"], 2500)
        reloaded = [row("현대자동차(주)", f"모델 {i}", eff="9.9") for i in range(300)] + many
        second = k.run("key", now=NOW + dt.timedelta(days=1), previous=first, get=api(reloaded, per=1000), sleep=lambda s: None)
        self.assertTrue(second["bulk"])
        self.assertTrue(all(v["bulk"] for v in second["vehicles"]))

    def test_truncated_list_fails_closed(self):
        def short(url, params=None, headers=None, timeout=None):
            return Resp(json.dumps({"header": {"resultCode": "00"}, "body": {"items": {"item": []}, "totalCount": 50}}))
        doc = k.run("key", now=NOW, previous=None, get=short, sleep=lambda s: None)
        self.assertEqual(doc["status"], "failed")


    def test_second_account_key_is_tried_when_first_is_refused(self):
        xml = "<OpenAPI_ServiceResponse><cmmMsgHeader><returnAuthMsg>SERVICE_KEY_IS_NOT_REGISTERED_ERROR</returnAuthMsg><returnReasonCode>30</returnReasonCode></cmmMsgHeader></OpenAPI_ServiceResponse>"
        ok = api(BASE)

        def get(url, params=None, headers=None, timeout=None):
            return Resp(xml) if params["serviceKey"] == "a" else ok(url, params=params, headers=headers, timeout=timeout)
        self.assertEqual(k.resolve_keys({"KR_FUEL_API_KEY": "z", "CUSTOMS_API_KEY": "a"})[0], ("z", "KR_FUEL_API_KEY"))
        keys = k.resolve_keys({"CUSTOMS_API_KEY": "a", "G2B_API_KEY": "b%2B"})
        self.assertEqual(keys, [("a", "CUSTOMS_API_KEY"), ("b+", "G2B_API_KEY")])
        doc, name, refused = k.run_any(keys, now=NOW, previous=None, get=get, sleep=lambda s: None)
        self.assertEqual((doc["status"], name, refused), ("complete", "G2B_API_KEY", ["CUSTOMS_API_KEY"]))
        doc2, name2, refused2 = k.run_any([("a", "CUSTOMS_API_KEY")], now=NOW, previous=None, get=get, sleep=lambda s: None)
        self.assertEqual((doc2["status"], name2, refused2), ("unset", None, ["CUSTOMS_API_KEY"]))


    def test_json_403_refusal_keeps_the_gateway_code(self):
        body = json.dumps({"OpenAPI_ServiceResponse": {"cmmMsgHeader": {"errMsg": "SERVICE_KEY_IS_NOT_REGISTERED_ERROR",
                                                                        "returnAuthMsg": "등록되지 않은 서비스키", "returnReasonCode": "30"}}}, ensure_ascii=False)
        doc = k.run("key", now=NOW, previous=None, get=lambda *a, **kw: Resp(body, 403), sleep=lambda s: None)
        self.assertEqual(doc["status"], "unset")
        self.assertIn("HTTP 403 30 SERVICE_KEY_IS_NOT_REGISTERED_ERROR", doc["checks"][0]["error"])
        html = k.run("key", now=NOW, previous=None, get=lambda *a, **kw: Resp("<html>blocked</html>", 403), sleep=lambda s: None)
        self.assertIn("본문 형식 미상(20자)", html["checks"][0]["error"])


class Board:
    """가짜 무상점검·수리 게시판(목록 한 쪽, 상세 없음). down=True면 목록이 HTTP 500."""

    def __init__(self, titles, down=False):
        self.titles, self.down, self.calls = titles, down, 0

    def get(self, url, headers=None, timeout=None):
        if url.endswith("robots.txt"):
            return Resp("<html>404</html>", 404)
        return self.post(url, data={"currentPageNo": "1"})

    def post(self, url, data=None, headers=None, timeout=None):
        self.calls += 1
        if self.down:
            return Resp("", 500)
        if "detail.do" in url:
            return Resp("<table><tr><th>제작(수입)사</th><td>기아(주)</td><th>대수</th><td>77,043 대</td></tr></table>")
        rows = "".join(f"<li><a onclick=\"$main.event.detailView('{no}','O');\"><strong>{t}</strong></a><ol><li>국토교통부</li><li>{d}</li></ol></li>"
                       for no, t, d in self.titles) if data["currentPageNo"] == "1" else ""
        return Resp(f"<p>전체 4,177건</p><ul>{rows}</ul>")


class Build(unittest.TestCase):
    """연비 목록과 무상점검·수리 게시판은 한 저장소에 싣되 따로 읽는다(11-14)."""
    KEYS = [("key", "KR_FUEL_API_KEY")]
    OLD_POST = ("4870", "[포르쉐] 카이엔 - 무상수리", "2026-10-01")
    K8 = ("4874", "[기아] K8 HEV - HPCU 관련 무상수리", "2026-10-29")

    def test_daytime_run_skips_the_fuel_api_and_still_reads_the_board(self):
        get = api(BASE)
        morning, info = k.build(None, NOW, self.KEYS, get=get, session=Board([self.OLD_POST]), sleep=lambda s: None)
        self.assertEqual((morning["status"], morning["fuelAt"], len(get.calls)), ("complete", NOW.isoformat(timespec="seconds"), 1))
        self.assertEqual([c["status"] for c in morning["checks"]], ["ok", "ok"])
        self.assertTrue(k.fuel_is_fresh(morning, NOW + dt.timedelta(hours=5)))
        self.assertFalse(k.fuel_is_fresh(morning, NOW + dt.timedelta(hours=24)))       # 다음 날 아침에는 다시 받는다
        self.assertFalse(k.fuel_is_fresh({**morning, "fuelAt": None}, NOW))             # 예전 저장본(fuelAt 없음)

        def boom(*a, **kw):
            raise AssertionError("낮 실행은 연비 API를 부르지 않는다")
        noon, info = k.build(morning, NOW + dt.timedelta(hours=5, minutes=30), self.KEYS, get=boom, session=Board([self.K8, self.OLD_POST]), sleep=lambda s: None)
        self.assertEqual((noon["status"], noon["fuelAt"], info["keyName"]), ("complete", morning["fuelAt"], "건너뜀(연비 목록은 오늘 받음)"))
        self.assertEqual(noon["seenKeys"], morning["seenKeys"])
        new = [x for x in noon["freeRepair"]["items"] if x["isNew"]]
        self.assertEqual([(x["no"], x["company"], x["tier"], x["units"]) for x in new], [("4874", "기아", "A", 77043)])
        self.assertEqual(noon["checks"][1]["newBeat"], 1)

    def test_one_side_failing_keeps_the_other(self):
        morning, _ = k.build(None, NOW, self.KEYS, get=api(BASE), session=Board([self.OLD_POST]), sleep=lambda s: None)
        morning["vehicles"] = [{"id": "kf:x", "firstSeen": "2026-10-29T06:10:00+09:00", "registered": "2026-10-28", "model": "m", "company": "현대차", "kind": "새 모델명"}]

        def boom(*a, **kw):
            raise ConnectionError("x")
        nxt = NOW + dt.timedelta(days=1)
        # 연비 API만 실패: 연비 결과는 그대로, 게시판 새 글은 저장, 상태는 일부
        doc, info = k.build(morning, nxt, self.KEYS, get=boom, session=Board([self.K8, self.OLD_POST]), sleep=lambda s: None)
        self.assertEqual((doc["status"], info["fuelFailed"]), ("partial", True))
        self.assertEqual(doc["vehicles"][0]["id"], "kf:x")
        self.assertEqual([c["status"] for c in doc["checks"]], ["failed", "ok"])
        self.assertEqual(doc["fuelAt"], morning["fuelAt"])
        self.assertTrue(any(x["no"] == "4874" for x in doc["freeRepair"]["items"]))
        # 게시판만 실패: 연비는 새로 받고, 게시판은 직전 구역 그대로(미확인 표시), 상태는 일부
        doc2, info2 = k.build(morning, nxt, self.KEYS, get=api(BASE), session=Board([], down=True), sleep=lambda s: None)
        self.assertEqual((doc2["status"], info2["fuelFailed"]), ("partial", False))
        self.assertEqual([c["status"] for c in doc2["checks"]], ["ok", "failed"])
        self.assertTrue(doc2["freeRepair"]["stale"])
        self.assertEqual(len(doc2["freeRepair"]["items"]), 1)


if __name__ == "__main__":
    unittest.main()
