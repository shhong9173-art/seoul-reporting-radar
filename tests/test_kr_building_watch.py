"""공장 부지 건축인허가 감시: 도로명→지번→법정동코드, 같은 번지 허가, 신축·증축 등급, 사용승인, 키 거부는 미설정(0건 아님)."""
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
EPOST = {"북부산업로 1228": "충청남도 당진시 송악읍 고대리 1-1", "현대로 1077": "충청남도 아산시 인주면 금성리 196"}
REGION = {"충청남도 당진시 송악읍 고대리": "4427025031", "충청남도 아산시 인주면 금성리": "4420034022"}


class Resp:
    def __init__(self, text, status=200):
        self.text, self.status_code = text, status


def permit(pk, kind="증축", purpose="공장", area="12500.5", day="20261020", use=""):
    return {"mgmPmsrgstPk": pk, "platPlc": "충청남도 당진시 송악읍 고대리 1-1번지", "archGbCdNm": kind, "mainPurpsCdNm": purpose,
            "totArea": area, "archArea": "8000", "archPmsDay": day, "stcnsSchedDay": "20261201", "realStcnsDay": "", "useAprDay": use, "bldNm": "제강공장"}


def fake(permits_by_bun, refuse=()):
    calls = []

    def get(url, params=None, headers=None, timeout=None):
        calls.append((url, params))
        key = params["serviceKey"]
        if url == b.EPOST:
            if "epost" in refuse or key == "bad":
                return Resp("<NewAddressListResponse><cmmMsgHeader><successYN>N</successYN><returnCode>30</returnCode><errMsg>등록되지 않은 서비스키</errMsg></cmmMsgHeader></NewAddressListResponse>")
            road = params["srchwrd"]
            lnm = next((v for k, v in EPOST.items() if k in road), None)
            body = f"<newAddressListAreaCd><lnmAdres>{lnm}</lnmAdres></newAddressListAreaCd>" if lnm else ""
            return Resp(f"<NewAddressListResponse><cmmMsgHeader><successYN>Y</successYN><returnCode>00</returnCode></cmmMsgHeader>{body}</NewAddressListResponse>")
        if url == b.REGION:
            if key == "bad":
                return Resp(json.dumps({"RESULT": {"resultCode": "30"}}), 403)
            name = params["locatadd_nm"]
            return Resp(json.dumps({"StanReginCd": [{"head": [{"totalCount": 1}]}, {"row": [{"region_cd": REGION[name], "locatadd_nm": name}]}]}, ensure_ascii=False))
        if url == b.ARCH:
            if "arch" in refuse or key == "bad":
                return Resp('{"response":{"header":{"resultCode":"30"}}}', 403)
            rows = permits_by_bun.get(params["bun"], [])
            return Resp(json.dumps({"response": {"header": {"resultCode": "00"}, "body": {"items": {"item": rows}, "totalCount": len(rows)}}}, ensure_ascii=False))
        raise AssertionError(url)
    get.calls = calls
    return get


class Building(unittest.TestCase):
    def test_address_helpers(self):
        self.assertEqual(b.road_query("충청남도 아산시 인주면 현대로 1077 (금성리)"), "충청남도 아산시 인주면 현대로 1077")
        self.assertEqual(b.split_jibun("충청남도 당진시 송악읍 고대리 1-1 케이지스틸"), {"dong": "충청남도 당진시 송악읍 고대리", "platGbCd": "0", "bun": "1", "ji": "1"})
        self.assertEqual(b.split_jibun("울산광역시 북구 양정동 산 12")["platGbCd"], "1")
        self.assertEqual(b.resolve_keys({"KR_FUEL_API_KEY": "a%2B", "CUSTOMS_API_KEY": "a+", "G2B_API_KEY": "c"}), [("KR_FUEL_API_KEY", "a+"), ("G2B_API_KEY", "c")])

    def test_baseline_then_new_permit_and_use_approval(self):
        get = fake({"0001": [permit("P1")], "0196": [permit("P9", kind="신축", area="200", day="20260101")]})
        first = b.run([("K", "good")], FACS, now=NOW, previous=None, get=get, sleep=lambda s: None)
        self.assertEqual(first["status"], "complete")
        self.assertEqual(first["parcelsResolved"], 2)
        self.assertEqual(first["parcels"]["fac:1"]["bun"], "0001")
        self.assertTrue(all(x["baseline"] and not x["isNew"] for x in first["permits"]))
        p1 = next(x for x in first["permits"] if x["id"] == "bld:P1")
        self.assertEqual((p1["tier"], p1["company"], p1["totArea"], p1["permitted"]), ("A", "KG스틸", 12500.5, "2026-10-20"))
        self.assertEqual(next(x for x in first["permits"] if x["id"] == "bld:P9")["tier"], "C")  # 300㎡ 미만

        get2 = fake({"0001": [permit("P1", use="20261030"), permit("P2", kind="대수선", area="900", day="20261028")]})
        second = b.run([("K", "good")], FACS, now=NOW + dt.timedelta(days=7), previous=first, get=get2, sleep=lambda s: None)
        new = {x["id"]: x for x in second["permits"] if x["isNew"]}
        self.assertEqual(set(new), {"bld:P1", "bld:P2"})
        self.assertEqual((new["bld:P1"]["kind"], new["bld:P1"]["tier"]), ("사용승인(준공)", "B"))
        self.assertEqual((new["bld:P2"]["kind"], new["bld:P2"]["tier"]), ("새 허가", "B"))
        self.assertFalse(any(u == b.EPOST for u, _ in get2.calls))  # 번지는 저장분 재사용

    def test_refused_key_is_unset_and_next_key_is_tried(self):
        get = fake({"0001": [permit("P1")]})
        doc = b.run([("CUSTOMS_API_KEY", "bad"), ("G2B_API_KEY", "good")], FACS, now=NOW, previous=None, get=get, sleep=lambda s: None)
        self.assertEqual(doc["status"], "complete")
        only_bad = b.run([("CUSTOMS_API_KEY", "bad")], FACS, now=NOW, previous=None, get=fake({}), sleep=lambda s: None)
        self.assertEqual(only_bad["status"], "unset")
        self.assertIn("활용신청 필요(15000124 우체국 도로명주소", only_bad["checks"][0]["error"])
        arch_refused = b.run([("K", "good")], FACS, now=NOW, previous=None, get=fake({}, refuse=("arch",)), sleep=lambda s: None)
        self.assertEqual([c["status"] for c in arch_refused["checks"]], ["ok", "unset"])
        self.assertIn("15136267 건축인허가", arch_refused["checks"][1]["error"])
        self.assertEqual(b.run([], FACS, now=NOW)["status"], "unset")


if __name__ == "__main__":
    unittest.main()
