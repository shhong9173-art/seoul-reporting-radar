"""굴뚝 측정(가동 신호): 10-30 실제 응답 칸 모양의 가짜 API로 출입처 사업장 이름 규칙(계열사·동명 회사 제외), 첫 실행 기준선,
관측이 쌓이기 전 판단 안 함, 사업장 대부분 멈춤 A·일부 멈춤 B·작은 배출구 하나는 이벤트 없음, 측정 시각 멈춤, 새 배출구 A, 빠진 배출구 B,
재가동 B, 조회 실패는 미확인."""
import datetime as dt
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import kr_stack_watch as w  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
T0 = dt.datetime(2026, 10, 30, 12, 0, tzinfo=KST)
CFG = json.loads(w.CONFIG.read_text(encoding="utf-8"))
CFG_SMALL = {"companies": [c for c in CFG["companies"] if c["company"] in ("현대제철", "포스코", "영풍")]}


def row(site, area, code, when, val):
    # rltmMesureResult item 칸(10-30 실제 응답과 같은 이름)
    return {"area_nm": area, "fact_manage_nm": site, "stack_code": code, "mesure_dt": when.strftime("%Y-%m-%d %H:%M"),
            "tsp_mesure_value": None if val is None else f"{val * 0.2:.2f}", "sox_mesure_value": None if val is None else f"{val:.2f}",
            "nox_mesure_value": None if val is None else f"{val * 0.5:.2f}", "hcl_mesure_value": None, "hf_mesure_value": None,
            "nh3_mesure_value": None, "co_mesure_value": None, "sox_exhst_perm_stdr_value": "140"}


class Api:
    def __init__(self, world, down=(), key_error=False):
        self.world, self.down, self.key_error, self.calls = world, set(down), key_error, []

    def __call__(self, url, params=None, timeout=None):
        self.calls.append(params["factManageNm"])
        term = params["factManageNm"]
        if self.key_error:
            return R(403, '{"OpenAPI_ServiceResponse":{"cmmMsgHeader":{"returnReasonCode":"30"}}}')
        if term in self.down:
            raise type("ReadTimeout", (Exception,), {})("x")
        items = [x for x in self.world if term in x["fact_manage_nm"]]
        return R(200, json.dumps({"response": {"header": {"resultCode": "0", "resultMsg": "NORMAL_CODE"}, "body": {"items": items}}}, ensure_ascii=False))


class R:
    def __init__(self, status, text):
        self.status_code, self.text = status, text


def world(t, pohang2=(20.0, 15.0), dangjin=(30.0, 8.0, 0.1), new_stack=False, extra=()):
    rows = [row("현대제철㈜포항2공장", "경상북도", str(i + 1), t, v) for i, v in enumerate(pohang2)]
    rows += [row("현대제철㈜", "충청남도", str(i + 1), t, v) for i, v in enumerate(dangjin)]
    rows += [row("㈜포스코 광양제철소", "전라남도", "1", t, 50.0), row("㈜포스코퓨처엠 광양화학사업부", "전라남도", "1", t, 9.0),
             row("㈜영풍석포제련소", "경상북도", "3", t, 12.0), row("영풍제지㈜", "경기도", "1", t, 4.0),
             row("아세아제지㈜ 세종공장", "세종특별자치시", "1", t, 4.0)]
    if new_stack:
        rows.append(row("현대제철㈜", "충청남도", "99", t, 6.0))
    return rows + list(extra)


def series(n, start=T0, **kw):
    """n번 실행(3시간 간격)한 결과 문서. kw는 실행 번호 → world() 인자 함수."""
    doc = None
    for i in range(n):
        t = start + dt.timedelta(hours=3 * i)
        args = kw.get("at", lambda i: {})(i)
        doc = w.run(CFG_SMALL, now=t + dt.timedelta(minutes=20), previous=doc, key="k", get=Api(world(t, **args)), sleep=lambda s: None)
    return doc


class StackTest(unittest.TestCase):
    def test_names_and_baseline(self):
        doc = w.run(CFG_SMALL, now=T0, key="k", get=Api(world(T0)), sleep=lambda s: None)
        self.assertEqual(sorted(s["name"] for s in doc["sites"]), ["㈜영풍석포제련소", "㈜포스코 광양제철소", "현대제철㈜", "현대제철㈜포항2공장"])
        self.assertEqual(doc["events"], [])
        self.assertEqual(doc["status"], "complete")
        self.assertEqual(w.peak(row("x", "y", "1", T0, 10.0)), 10.0)

    def test_no_judgement_before_enough_observations(self):
        doc = series(5, at=lambda i: {"pohang2": (0.0, 0.0)} if i >= 2 else {})
        self.assertEqual([e for e in doc["events"] if "멈춤" in e["kind"] or "중단" in e["kind"]], [])

    def test_site_down_is_A_and_restart_is_B(self):
        # 6번 정상 뒤 포항2공장 두 배출구가 3번 연속 0 근처 → 사업장 가동 중단 신호 A(한 번만)
        doc = series(11, at=lambda i: {"pohang2": (0.1, 0.0)} if i >= 6 else {})
        down = [e for e in doc["events"] if e["kind"] == "사업장 가동 중단 신호"]
        self.assertEqual([(e["tier"], e["site"]) for e in down], [("A", "현대제철㈜포항2공장")])
        self.assertIn("평소 움직이던 배출구 2개 중 2개가 3번 연속 평소의 10% 아래", down[0]["text"])
        # 다시 움직이면 재가동 신호 B
        doc2 = w.run(CFG_SMALL, now=T0 + dt.timedelta(hours=34), previous=doc, key="k",
                     get=Api(world(T0 + dt.timedelta(hours=34))), sleep=lambda s: None)
        up = [e for e in doc2["events"] if e["kind"] == "사업장 재가동 신호"]
        self.assertEqual([(e["tier"], e["site"]) for e in up], [("B", "현대제철㈜포항2공장")])

    def test_one_big_stack_is_B_small_or_near_zero_stack_is_nothing(self):
        # 당진: 큰 배출구(30) 하나가 멈춤 → B(큰 배출구), 0.1인 배출구는 원래 거의 0이라 판단 안 함
        doc = series(10, at=lambda i: {"dangjin": (0.0, 8.0, 0.0)} if i >= 6 else {})
        ev = [e for e in doc["events"] if e["site"] == "현대제철㈜"]
        self.assertEqual([(e["kind"], e["tier"]) for e in ev], [("배출구 멈춤 신호", "B")])
        self.assertIn("1번(평소 30.0", ev[0]["text"])

    def test_stale_measurement_counts_as_stopped(self):
        doc = series(8)
        # 영풍 석포 배출구의 측정 시각이 13시간째 그대로 → 멈춤(사업장 전체 1개라 A는 아님: 배출구 2개 이상일 때만)
        t = T0 + dt.timedelta(hours=3 * 8 + 13)
        frozen = [x for x in world(t) if x["fact_manage_nm"] != "㈜영풍석포제련소"] + [row("㈜영풍석포제련소", "경상북도", "3", T0 + dt.timedelta(hours=21), 12.0)]
        doc = w.run(CFG_SMALL, now=t, previous=doc, key="k", get=Api(frozen), sleep=lambda s: None)
        site = next(s for s in doc["sites"] if s["name"] == "㈜영풍석포제련소")
        self.assertEqual(site["stopped"], ["3"])
        ev = [e for e in doc["events"] if e["site"] == "㈜영풍석포제련소"]
        self.assertEqual([(e["kind"], e["tier"]) for e in ev], [("배출구 멈춤 신호", "B")])  # 사업장에서 가장 큰 배출구

    def test_new_stack_and_missing_stack(self):
        doc = series(2)
        t = T0 + dt.timedelta(hours=6)
        doc = w.run(CFG_SMALL, now=t, previous=doc, key="k", get=Api(world(t, new_stack=True)), sleep=lambda s: None)
        new = [e for e in doc["events"] if e["kind"] == "새 배출구"]
        self.assertEqual([(e["tier"], e["site"]) for e in new], [("A", "현대제철㈜")])
        self.assertIn("새 배출구 99번", new[0]["text"])
        for k in range(2):  # 포항2공장 2번 배출구가 두 번 연속 빠짐 → B 한 번
            t = T0 + dt.timedelta(hours=9 + 3 * k)
            rows = [x for x in world(t, new_stack=True) if not (x["fact_manage_nm"] == "현대제철㈜포항2공장" and x["stack_code"] == "2")]
            doc = w.run(CFG_SMALL, now=t, previous=doc, key="k", get=Api(rows), sleep=lambda s: None)
        gone = [e for e in doc["events"] if e["kind"] == "배출구 목록에서 빠짐"]
        self.assertEqual(len(gone), 1)
        self.assertIn("포항2공장 배출구 2번", gone[0]["text"])

    def test_emission_standard_exceedance_B_then_sustained_A_and_new_episode(self):
        # 같은 줄의 sox_exhst_perm_stdr_value(140)를 넘는 측정값: 처음 B, 다음 실행도 넘으면 A, 내려왔다 다시 넘으면 새 B
        self.assertEqual(w.exceedances(row("x", "y", "1", T0, 150.0)), [("sox", 150.0, 140.0)])
        self.assertEqual(w.exceedances({"sox_mesure_value": "9", "sox_exhst_perm_stdr_value": None, "nox_mesure_value": "-", "nox_exhst_perm_stdr_value": "0"}), [])
        doc = series(2)
        seq = [150.0, 160.0, 155.0, 30.0, 151.0]
        kinds = []
        for i, v in enumerate(seq):
            t = T0 + dt.timedelta(hours=6 + 3 * i)
            doc = w.run(CFG_SMALL, now=t + dt.timedelta(minutes=20), previous=doc, key="k", get=Api(world(t, dangjin=(v, 8.0, 0.1))), sleep=lambda s: None)
            kinds.append([(e["kind"], e["tier"]) for e in doc["events"] if "배출허용기준" in e["kind"] and e["detectedAt"] == doc["generatedAt"]])
        self.assertEqual(kinds, [[("배출허용기준 초과(측정값)", "B")], [("배출허용기준 초과 지속", "A")], [], [], [("배출허용기준 초과(측정값)", "B")]])
        a = next(e for e in doc["events"] if e["kind"] == "배출허용기준 초과 지속")
        self.assertIn("현대제철㈜ 배출구 1번 황산화물 측정값 160이 배출허용기준 140을 넘음(기준의 1.1배, 측정 2026-10-30 21:00)", a["text"])
        self.assertIn("2026-10-30 18:00 측정부터 이 감시의 실행 2번 연속 초과(처음 150)", a["text"])
        self.assertIn("초과 판정·행정처분은 한국환경공단·관할 지자체 확인", a["text"])
        site = next(s for s in doc["sites"] if s["name"] == "현대제철㈜")
        self.assertEqual([x["value"] for x in site["exceedLog"]], [150.0, 160.0, 155.0, 151.0])

    def test_failures_are_unconfirmed(self):
        doc = w.run(CFG_SMALL, now=T0, key="k", get=Api(world(T0), key_error=True), sleep=lambda s: None)
        self.assertEqual(doc["status"], "failed")
        self.assertIn("코드 30", doc["checks"][0]["error"])
        first = series(2)
        doc = w.run(CFG_SMALL, now=T0 + dt.timedelta(hours=6), previous=first, key="k", get=Api(world(T0 + dt.timedelta(hours=6)), down={"영풍"}),
                    sleep=lambda s: None)
        self.assertEqual(doc["status"], "partial")
        self.assertEqual(next(s for s in doc["sites"] if s["name"] == "㈜영풍석포제련소").get("missingRuns", 0), 0)  # 검색 실패는 빠짐이 아님


if __name__ == "__main__":
    unittest.main()
