"""공장 부지 건축인허가 감시: 도로명→법정동코드·지번(도로명주소 API), 같은 번지 허가, 신축·증축 등급, 사용승인, 키 거부는 미설정(0건 아님)."""
import datetime as dt
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import kr_building_watch as b  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 11, 2, 7, 45, tzinfo=KST)
FACS = [{"id": "fac:1", "company": "KG스틸", "cmpnyNm": "케이지스틸 주식회사", "rnAdres": "충청남도 당진시 송악읍 북부산업로 1228"},
        {"id": "fac:2", "company": "현대차", "cmpnyNm": "현대자동차(주) 아산공장", "rnAdres": "충청남도 아산시 인주면 현대로 1077 (금성리)"}]
JUSO_DB = {"충청남도 당진시 송악읍 북부산업로 1228": ("충청남도 당진시 송악읍 고대리 1-1", "4427025031", "0", "1", "1"),
           "충청남도 아산시 인주면 현대로 1077": ("충청남도 아산시 인주면 금성리 196", "4420034022", "0", "196", "0")}


class Resp:
    def __init__(self, text, status=200):
        self.text, self.status_code = text, status


def permit(pk, kind="증축", purpose="공장", area="12500.5", day="20261020", use=""):
    return {"mgmPmsrgstPk": pk, "platPlc": "충청남도 당진시 송악읍 고대리 1-1번지", "archGbCdNm": kind, "mainPurpsCdNm": purpose,
            "totArea": area, "archArea": "8000", "archPmsDay": day, "stcnsSchedDay": "20261201", "realStcnsDay": "", "useAprDay": use, "bldNm": "제강공장"}


def fake(permits_by_bun, refuse=(), down=False):
    calls = []

    def get(url, params=None, headers=None, timeout=None):
        calls.append((url, params))
        if url == b.JUSO:
            if down:
                raise type("ConnectTimeout", (Exception,), {})("HTTPSConnectionPool(host='x'): url: /a?confmKey=SECRET")
            if params["confmKey"] == "bad":
                return Resp(json.dumps({"results": {"common": {"errorCode": "E0001", "errorMessage": "승인되지 않은 KEY 입니다."}, "juso": None}}, ensure_ascii=False))
            hit = JUSO_DB.get(params["keyword"])
            rows = [] if not hit else [{"roadAddrPart1": params["keyword"], "jibunAddr": hit[0], "admCd": hit[1], "mtYn": hit[2], "lnbrMnnm": hit[3], "lnbrSlno": hit[4]}]
            return Resp(json.dumps({"results": {"common": {"errorCode": "0", "totalCount": str(len(rows))}, "juso": rows}}, ensure_ascii=False))
        key = params["serviceKey"]
        if url == b.ARCH:
            if "arch" in refuse or key == "bad":
                return Resp('{"response":{"header":{"resultCode":"30"}}}', 403)
            rows = permits_by_bun.get(params["bun"], [])
            return Resp(json.dumps({"response": {"header": {"resultCode": "00"}, "body": {"items": {"item": rows}, "totalCount": len(rows)}}}, ensure_ascii=False))
        raise AssertionError(url)
    get.calls = calls
    return get


def go(keys, facs, juso="jk", **kw):
    kw.setdefault("sleep", lambda s: None)
    return b.run(keys, facs, juso_key=juso, **kw)


class Building(unittest.TestCase):
    def test_address_helpers(self):
        self.assertEqual(b.road_query("충청남도 아산시 인주면 현대로 1077 (금성리)"), "충청남도 아산시 인주면 현대로 1077")
        many = json.dumps({"results": {"common": {"errorCode": "0"}, "juso": [
            {"roadAddrPart1": "울산광역시 북구 염포로 700", "admCd": "3120010300", "mtYn": "1", "lnbrMnnm": "12", "lnbrSlno": "0"},
            {"roadAddrPart1": "울산광역시 북구 염포로 700-1", "admCd": "3120010300", "mtYn": "0", "lnbrMnnm": "99", "lnbrSlno": "0"}]}})
        self.assertEqual(b.juso_pick(many, "울산광역시 북구 염포로 700")["mtYn"], "1")  # exact road match wins
        with self.assertRaises(RuntimeError):
            b.juso_pick(many, "울산광역시 북구 염포로")  # two different lots, none exact
        with self.assertRaises(b.Refused):
            b.juso_pick(json.dumps({"results": {"common": {"errorCode": "E0014", "errorMessage": "개발승인키 기간이 만료되었습니다."}}}), "x")
        self.assertEqual(b.resolve_keys({"KR_FUEL_API_KEY": "a%2B", "CUSTOMS_API_KEY": "a+", "G2B_API_KEY": "c"}), [("KR_FUEL_API_KEY", "a+"), ("G2B_API_KEY", "c")])

    def test_baseline_then_new_permit_and_use_approval(self):
        get = fake({"0001": [permit("P1")], "0196": [permit("P9", kind="신축", area="200", day="20260101")]})
        first = go([("K", "good")], FACS, now=NOW, previous=None, get=get, sleep=lambda s: None)
        self.assertEqual(first["status"], "complete")
        self.assertEqual(first["parcelsResolved"], 2)
        self.assertEqual(first["parcels"]["fac:1"]["bun"], "0001")
        self.assertTrue(all(x["baseline"] and not x["isNew"] for x in first["permits"]))
        p1 = next(x for x in first["permits"] if x["id"] == "bld:P1")
        self.assertEqual((p1["tier"], p1["company"], p1["totArea"], p1["permitted"]), ("A", "KG스틸", 12500.5, "2026-10-20"))
        self.assertEqual(next(x for x in first["permits"] if x["id"] == "bld:P9")["tier"], "C")  # 300㎡ 미만

        get2 = fake({"0001": [permit("P1", use="20261030"), permit("P2", kind="대수선", area="900", day="20261028")]})
        second = go([("K", "good")], FACS, now=NOW + dt.timedelta(days=7), previous=first, get=get2, sleep=lambda s: None)
        new = {x["id"]: x for x in second["permits"] if x["isNew"]}
        self.assertEqual(set(new), {"bld:P1", "bld:P2"})
        self.assertEqual((new["bld:P1"]["kind"], new["bld:P1"]["tier"]), ("사용승인(준공)", "B"))
        self.assertEqual((new["bld:P2"]["kind"], new["bld:P2"]["tier"]), ("새 허가", "B"))
        self.assertFalse(any(u == b.JUSO for u, _ in get2.calls))  # 번지는 저장분 재사용

    def test_first_real_run_after_unset_is_baseline(self):
        unset = go([("K", "good")], FACS, juso=None, now=NOW, previous=None, get=fake({}), sleep=lambda s: None)
        self.assertEqual(unset["status"], "unset")
        doc = go([("K", "good")], FACS, now=NOW, previous=unset, get=fake({"0001": [permit("P1")]}), sleep=lambda s: None)
        self.assertTrue(all(x["baseline"] and not x["isNew"] for x in doc["permits"]))

    def test_time_budget_saves_progress(self):
        facs = FACS + [dict(FACS[0], id="fac:3")]
        get = fake({"0001": [permit("P1")]})
        doc = go([("K", "good")], facs, now=NOW, previous=None, get=get, sleep=lambda s: None)
        t = iter([0, 0, 0, b.ADDR_BUDGET_S + 1] + [b.ADDR_BUDGET_S + 1] * 20)
        cut = go([("K", "good")], facs, now=NOW, previous=None, get=fake({"0001": [permit("P1")]}), sleep=lambda s: None, clock=lambda: next(t))
        self.assertEqual(cut["status"], "partial")
        self.assertIn("남은 1곳", cut["checks"][0]["error"])
        self.assertEqual(cut["parcelsResolved"], 2)
        later = fake({"0001": [permit("P1")]})
        done = go([("K", "good")], facs, now=NOW + dt.timedelta(days=7), previous=cut, get=later, sleep=lambda s: None)
        self.assertEqual(done["parcelsResolved"], 3)
        self.assertEqual(sum(1 for u, _ in later.calls if u == b.JUSO), 1)  # only the one left over

    def test_parcel_seen_first_after_the_baseline_is_its_own_baseline(self):
        # run 1 resolves only 현대차's parcel (time limit); run 2 adds KG스틸's: its existing permits are not 'new'
        t = iter([0, 0] + [b.ADDR_BUDGET_S + 1] * 30)
        facs = [FACS[1], FACS[0]]
        first = go([("K", "good")], facs, now=NOW, previous=None, get=fake({"0196": [permit("P9")]}), sleep=lambda s: None, clock=lambda: next(t))
        self.assertEqual(first["parcelsResolved"], 1)
        second = go([("K", "good")], facs, now=NOW + dt.timedelta(days=7), previous=first,
                       get=fake({"0196": [permit("P9"), permit("P10", day="20261105")], "0001": [permit("P1")]}), sleep=lambda s: None)
        got = {x["id"]: (x["baseline"], x["isNew"]) for x in second["permits"]}
        self.assertEqual(got["bld:P1"], (True, False))   # first look at KG스틸's parcel
        self.assertEqual(got["bld:P10"], (False, True))  # really new at a parcel already watched
        # TTL re-resolution of the same parcel keeps its first-look stamp
        aged = dict(second, parcels={k: dict(v, checkedAt="2026-01-01T00:00:00+09:00") for k, v in second["parcels"].items()})
        third = go([("K", "good")], facs, now=NOW + dt.timedelta(days=14), previous=aged,
                      get=fake({"0196": [permit("P9"), permit("P10", day="20261105")], "0001": [permit("P1"), permit("P2", day="20261110")]}), sleep=lambda s: None)
        self.assertEqual(next(x for x in third["permits"] if x["id"] == "bld:P2")["isNew"], True)

    def test_state_before_first_look_stamps(self):
        first = go([("K", "good")], FACS, now=NOW, previous=None, get=fake({"0001": [permit("P1")]}), sleep=lambda s: None)
        old = dict(first, archFirstMarked=None, parcels={k: {kk: vv for kk, vv in v.items() if kk != "archFirst"} for k, v in first["parcels"].items()})
        second = go([("K", "good")], FACS, now=NOW + dt.timedelta(days=4), previous=old,
                       get=fake({"0001": [permit("P1"), permit("P2", day="20261101")]}), sleep=lambda s: None)
        self.assertTrue(next(x for x in second["permits"] if x["id"] == "bld:P2")["isNew"])
        t2 = iter([0] * 4 + [b.TOTAL_BUDGET_S + 1] * 20)
        arch_cut = go([("K", "good")], FACS, now=NOW, previous=None, get=fake({}), sleep=lambda s: None, clock=lambda: next(t2))
        self.assertIn("남은", arch_cut["checks"][1]["error"])
        self.assertEqual(arch_cut["status"], "partial")

    def test_refused_key_is_unset_and_next_key_is_tried(self):
        get = fake({"0001": [permit("P1")]})
        doc = go([("CUSTOMS_API_KEY", "bad"), ("G2B_API_KEY", "good")], FACS, now=NOW, previous=None, get=get, sleep=lambda s: None)
        self.assertEqual(doc["status"], "complete")
        no_juso = go([("K", "good")], FACS, juso=None, now=NOW, previous=None, get=fake({}), sleep=lambda s: None)
        self.assertEqual(no_juso["status"], "unset")
        self.assertIn("JUSO_CONFM_KEY 없음", no_juso["checks"][0]["error"])
        bad_juso = go([("K", "good")], FACS, juso="bad", now=NOW, previous=None, get=fake({}), sleep=lambda s: None)
        self.assertEqual(bad_juso["status"], "unset")
        self.assertIn("E0001", bad_juso["checks"][0]["error"])
        arch_refused = go([("K", "good")], FACS, now=NOW, previous=None, get=fake({}, refuse=("arch",)), sleep=lambda s: None)
        self.assertEqual([c["status"] for c in arch_refused["checks"]], ["ok", "unset"])
        self.assertIn("15136267 건축인허가", arch_refused["checks"][1]["error"])
        self.assertEqual(b.run([], FACS, now=NOW)["status"], "unset")

    def test_unreachable_address_service_stops_early_and_keeps_no_url(self):
        facs = [dict(FACS[0], id=f"fac:{i}") for i in range(10)]
        get = fake({}, down=True)
        doc = go([("K", "good")], facs, now=NOW, previous=None, get=get, sleep=lambda s: None)
        self.assertEqual(sum(1 for u, _ in get.calls if u == b.JUSO), b.CONNECT_STREAK)
        self.assertEqual(doc["checks"][0]["status"], "failed")
        self.assertIn("남은 7곳", doc["checks"][0]["error"])
        self.assertEqual(doc["status"], "failed")
        self.assertNotIn("SECRET", json.dumps(doc))


if __name__ == "__main__":
    unittest.main()
