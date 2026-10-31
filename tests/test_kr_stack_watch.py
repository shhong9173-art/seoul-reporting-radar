"""굴뚝 측정(가동 신호): 10-30 실제 응답 칸 모양의 가짜 API로 출입처 사업장 이름 규칙(계열사·동명 회사 제외), 첫 실행 기준선,
관측이 쌓이기 전 판단 안 함, 사업장 대부분 멈춤 A·일부 멈춤 B·작은 배출구 하나는 이벤트 없음, 측정 시각 멈춤, 새 배출구는 지켜본 기간대로(14일 A·7일 B·그 전 C), 빠진 배출구 B,
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


def aged(doc, days):
    """감시를 days일 전부터 돌린 것처럼(사업장 firstSeen·기준선을 앞당김)."""
    back = dt.timedelta(days=days)
    for site in doc["sites"]:
        site["firstSeen"] = (dt.datetime.fromisoformat(site["firstSeen"]) - back).isoformat(timespec="seconds")
    doc["baselineSince"] = (dt.datetime.fromisoformat(doc["baselineSince"]) - back).isoformat(timespec="seconds")
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

    def test_two_small_stacks_of_a_big_steelworks_are_not_B(self):
        # 10-31 09:17 운영: 포스코 광양 평소 움직이던 137개 중 2개(평소 41.0·18.2) 멈춤이 B — 일상 정비 수준
        big = tuple([60.0, 55.0, 50.0] + [20.0] * 57)  # 60개, 상위 3개는 50 이상

        def at(i):
            return {"pohang2": big if i < 6 else (big[:10] + (0.0, 0.0) + big[12:])}  # 11·12번(평소 20) 두 개 멈춤
        doc = series(10, at=at)
        ev = [e for e in doc["events"] if e["site"] == "현대제철㈜포항2공장"]
        self.assertEqual(ev, [])  # 60개 중 2개(5%=3개 미만), 상위 3 아님, 평소 값 합 40/1305(10% 미만) → 이벤트 없음
        site = next(x for x in doc["sites"] if x["name"] == "현대제철㈜포항2공장")
        self.assertEqual(site["stopped"], ["11", "12"])  # 화면 목록에는 보인다

        def at3(i):
            return {"pohang2": big if i < 6 else ((0.0,) + big[1:])}  # 가장 큰 배출구 하나 → B
        ev = [e for e in series(10, at=at3)["events"] if e["site"] == "현대제철㈜포항2공장"]
        self.assertEqual([(e["kind"], e["tier"]) for e in ev], [("배출구 멈춤 신호", "B")])

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
        doc = aged(series(7), 15)  # 사업장을 14일 넘게(7번 넘게) 지켜본 뒤라야 새 번호를 새 설비 신호(A)로 본다
        t = T0 + dt.timedelta(hours=21)
        doc = w.run(CFG_SMALL, now=t, previous=doc, key="k", get=Api(world(t, new_stack=True)), sleep=lambda s: None)
        new = [e for e in doc["events"] if e["kind"] == "새 배출구"]
        self.assertEqual([(e["tier"], e["site"]) for e in new], [("A", "현대제철㈜")])
        self.assertIn("새 배출구 99번", new[0]["text"])
        self.assertIn("이 사업장을 16일·7번 지켜보는 동안 없던 번호) — 새 설비 가동 또는 오래 쉬던 설비 재가동 가능성", new[0]["text"])
        for k in range(2):  # 포항2공장 2번 배출구가 두 번 연속 빠짐 → B 한 번
            t = T0 + dt.timedelta(hours=24 + 3 * k)
            rows = [x for x in world(t, new_stack=True) if not (x["fact_manage_nm"] == "현대제철㈜포항2공장" and x["stack_code"] == "2")]
            doc = w.run(CFG_SMALL, now=t, previous=doc, key="k", get=Api(rows), sleep=lambda s: None)
        gone = [e for e in doc["events"] if e["kind"] == "배출구 목록에서 빠짐"]
        self.assertEqual(len(gone), 1)
        self.assertIn("포항2공장 배출구 2번", gone[0]["text"])

    def test_new_number_tier_follows_how_long_the_site_was_watched(self):
        # 10-31 운영: 영풍 석포 5·6번이 감시 하루(7번째 실행) 만에 A '새 설비 가동 가능성'으로 떴다 — 쉬던 설비가 다시 측정된 것일 수 있다
        def one(days):
            doc = aged(series(7), days)
            t = T0 + dt.timedelta(hours=21)
            doc = w.run(CFG_SMALL, now=t, previous=doc, key="k", get=Api(world(t, new_stack=True)), sleep=lambda s: None)
            return [(e["kind"], e["tier"], e["text"]) for e in doc["events"] if e["detectedAt"] == doc["generatedAt"]]
        got = one(0)
        self.assertEqual([(k, t) for k, t, _ in got], [("배출구 목록 보강", "C")])
        self.assertIn("이 사업장을 0.9일·7번만 봐서 간헐 가동·측정 자료 지연일 수 있어 새 설비로 보지 않음", got[0][2])
        got = one(8)
        self.assertEqual([(k, t) for k, t, _ in got], [("새 배출구", "B")])
        self.assertIn("간헐 가동 설비가 다시 측정된 것일 수 있음(새 설비 여부 미확인)", got[0][2])

    def test_stored_early_new_stack_A_is_lowered(self):
        doc = series(7)
        at = (T0 + dt.timedelta(hours=18, minutes=20)).isoformat(timespec="seconds")
        doc["events"] = [{"id": "stk:newstack:영풍:㈜영풍석포제련소:5", "kind": "새 배출구", "tier": "A", "company": "영풍", "site": "㈜영풍석포제련소",
                          "detectedAt": at, "text": "㈜영풍석포제련소 굴뚝 자동측정에 새 배출구 5번이 생김"}] + doc["events"]
        t = T0 + dt.timedelta(hours=21)
        out = w.run(CFG_SMALL, now=t, previous=doc, key="k", get=Api(world(t)), sleep=lambda s: None)
        e = next(e for e in out["events"] if e["id"] == "stk:newstack:영풍:㈜영풍석포제련소:5")
        self.assertEqual(e["tier"], "C")
        self.assertIn("이 사업장을 0.8일만 지켜본 때라 간헐 가동·측정 자료 지연일 수 있어 C로 바로잡음", e["text"])
        again = w.run(CFG_SMALL, now=t + dt.timedelta(hours=3), previous=out, key="k", get=Api(world(t)), sleep=lambda s: None)
        e2 = next(x for x in again["events"] if x["id"] == "stk:newstack:영풍:㈜영풍석포제련소:5")
        self.assertEqual(e2["text"].count("바로잡음"), 1)  # 한 번만 붙인다
        site = {"id": "stk:newsite:한화솔루션:x", "kind": "새 사업장(굴뚝 측정)", "tier": "A", "company": "한화솔루션", "site": "x", "detectedAt": at, "text": "x"}
        w.retier_new([site], {}, T0.isoformat())
        self.assertEqual(site["tier"], "C")

    def test_weekday_plant_weekend_is_not_a_stop(self):
        # 10-31(토) 09:09 운영: 현대차 울산 배출구 7개·기아 화성 2개 '멈춤', 기아 광주2공장 '목록에서 빠짐'이 B로 뜸 — 주말 휴무
        cfg = {"companies": [c for c in CFG["companies"] if c["company"] == "기아"]}
        self.assertEqual(cfg["companies"][0].get("schedule"), "weekday")
        start = dt.datetime(2026, 10, 29, 7, 0, tzinfo=KST)  # 목요일

        def kia(t, monday_off=False, gwangju=True):
            on = w.working(t) and not (monday_off and t.date() >= dt.date(2026, 11, 2))
            rows = [row("기아㈜화성공장", "경기도", str(c), t, 20.0 if on else 0.0) for c in (1, 2, 3)]
            if gwangju and (w.working(t) or t.weekday() < 5):
                rows.append(row("기아㈜ 광주2공장", "광주광역시", "1", t, 15.0 if on else 0.0))
            return rows

        def week(monday_off=False):
            doc, events = None, []
            for i in range(0, 36):  # 목 07:00 ~ 월 16:00(3시간 간격)
                t = start + dt.timedelta(hours=3 * i)
                doc = w.run(cfg, now=t + dt.timedelta(minutes=20), previous=doc, key="k", get=Api(kia(t, monday_off)), sleep=lambda s: None)
            return doc
        doc = week()
        bad = [(e["kind"], e["tier"], e["detectedAt"]) for e in doc["events"] if e["kind"] in w.OFFHOUR_KINDS]
        self.assertEqual(bad, [])  # 주말·밤에 멈추고 평일 아침에 돌아오면 신호 없음(광주2공장이 주말에 목록에서 빠져도)
        doc = week(monday_off=True)
        down = [e for e in doc["events"] if e["kind"] in ("사업장 가동 중단 신호", "배출구 멈춤 신호") and "화성" in e["site"]]
        self.assertEqual([(e["kind"], e["tier"]) for e in down], [("사업장 가동 중단 신호", "A")])
        at = dt.datetime.fromisoformat(down[0]["detectedAt"])
        self.assertEqual((at.date().isoformat(), at.hour >= 7), ("2026-11-02", True))  # 월요일 일하는 시간 관측 3번 뒤

    def test_offhour_stored_stops_of_weekday_plants_are_lowered(self):
        sat = "2026-10-31T09:09:00+09:00"
        ev = [{"id": "stk:stop:현대차:x:2026-10-31", "kind": "배출구 멈춤 신호", "tier": "B", "company": "현대차", "site": "현대자동차㈜ 울산공장", "detectedAt": sat, "text": "멈춤"},
              {"id": "stk:sitegone:기아:y", "kind": "사업장 목록에서 빠짐(굴뚝 측정)", "tier": "B", "company": "기아", "site": "기아㈜ 광주2공장", "detectedAt": sat, "text": "빠짐"},
              {"id": "stk:stop:포스코:z:2026-10-31", "kind": "배출구 멈춤 신호", "tier": "B", "company": "포스코", "site": "포항", "detectedAt": sat, "text": "멈춤"},
              {"id": "stk:stop:기아:w:2026-11-02", "kind": "배출구 멈춤 신호", "tier": "B", "company": "기아", "site": "화성", "detectedAt": "2026-11-02T10:20:00+09:00", "text": "멈춤"}]
        w.retier_offhours(ev, {"현대차", "기아"})
        self.assertEqual([e["tier"] for e in ev], ["C", "C", "B", "B"])  # 연속 가동(포스코)·평일 낮은 그대로
        self.assertIn("주말·휴일·밤에 잡힌 것이라 휴무일 수 있어 C로 바로잡음", ev[0]["text"])
        self.assertFalse(w.working(dt.datetime(2026, 12, 25, 10, 0, tzinfo=KST)))  # 공휴일 목록
        self.assertFalse(w.working(dt.datetime(2026, 11, 2, 6, 30, tzinfo=KST)))   # 월요일 새벽
        self.assertTrue(w.working(dt.datetime(2026, 11, 2, 7, 30, tzinfo=KST)))

    def test_new_numbers_early_or_in_bulk_are_list_fill_C_not_new_plant(self):
        # 10-30 13:36 운영: 첫 실행 기준선 때 고려아연 온산 배출구가 7개만 보였다가 다음 실행에 24개가 더 보여 모두 A로 뜸
        doc = series(2)
        t = T0 + dt.timedelta(hours=6)
        extra = [row("현대제철㈜", "충청남도", str(100 + i), t, 5.0) for i in range(5)]
        doc = w.run(CFG_SMALL, now=t, previous=doc, key="k", get=Api(world(t, extra=extra)), sleep=lambda s: None)
        got = [(e["kind"], e["tier"]) for e in doc["events"] if e["detectedAt"] == doc["generatedAt"]]
        self.assertEqual(got, [("배출구 목록 보강", "C")])
        self.assertIn("배출구 5개가 새로 보임(100, 101, 102, 103, 104) — 한꺼번에 여러 개라", doc["events"][0]["text"])
        # 성숙한 사업장이라도 한 번에 3개 이상이면 목록 보강
        doc = series(8)
        t = T0 + dt.timedelta(hours=24)
        extra = [row("현대제철㈜", "충청남도", str(200 + i), t, 5.0) for i in range(3)]
        doc = w.run(CFG_SMALL, now=t, previous=doc, key="k", get=Api(world(t, extra=extra)), sleep=lambda s: None)
        self.assertEqual([(e["kind"], e["tier"]) for e in doc["events"] if e["detectedAt"] == doc["generatedAt"]], [("배출구 목록 보강", "C")])

    def test_site_gone_needs_maturity_and_reappearance_settles_it(self):
        # 10-30 14:36 운영: 첫날 엘에스엠앤엠(주)이 2번 빠져 B — 이른 감시의 일시적 누락일 수 있다
        def drop_yp(t):
            return [x for x in world(t) if x["fact_manage_nm"] != "㈜영풍석포제련소"]
        doc = series(2)
        for k in range(2):
            t = T0 + dt.timedelta(hours=6 + 3 * k)
            doc = w.run(CFG_SMALL, now=t, previous=doc, key="k", get=Api(drop_yp(t)), sleep=lambda s: None)
        gone = [e for e in doc["events"] if e["kind"].startswith("사업장 목록에서 빠짐")]
        self.assertEqual([e["tier"] for e in gone], ["C"])
        self.assertIn("일시적 누락일 수 있음", gone[0]["text"])
        # 예전 규칙으로 저장된 B도 다음 실행에 C로
        gone[0]["tier"] = "B"
        t = T0 + dt.timedelta(hours=12)
        doc = w.run(CFG_SMALL, now=t, previous=doc, key="k", get=Api(drop_yp(t)), sleep=lambda s: None)
        self.assertEqual([e["tier"] for e in doc["events"] if e["kind"].startswith("사업장 목록에서 빠짐")], ["C"])
        doc = series(8)
        for k in range(2):
            t = T0 + dt.timedelta(hours=24 + 3 * k)
            doc = w.run(CFG_SMALL, now=t, previous=doc, key="k", get=Api(drop_yp(t)), sleep=lambda s: None)
        self.assertEqual([e["tier"] for e in doc["events"] if e["kind"].startswith("사업장 목록에서 빠짐")], ["B"])
        t = T0 + dt.timedelta(hours=30)
        doc = w.run(CFG_SMALL, now=t, previous=doc, key="k", get=Api(world(t)), sleep=lambda s: None)
        back = [e for e in doc["events"] if e["kind"].startswith("사업장 목록에서 빠짐")]
        self.assertEqual([e["tier"] for e in back], ["C"])
        self.assertIn("이후 다시 나타남", back[0]["text"])

    def test_stored_burst_of_new_stack_A_is_collapsed(self):
        at = "2026-10-30T13:36:00+09:00"
        burst = [{"id": f"stk:newstack:고려아연:x:{c}", "kind": "새 배출구", "tier": "A", "company": "고려아연", "site": "고려아연㈜온산제련소",
                  "detectedAt": at, "text": f"고려아연㈜온산제련소 굴뚝 자동측정에 새 배출구 {c}번이 생김"} for c in ("1", "16", "2", "20")]
        lone = {"id": "stk:newstack:현대제철:y:9", "kind": "새 배출구", "tier": "A", "company": "현대제철", "site": "현대제철㈜", "detectedAt": at,
                "text": "현대제철㈜ 굴뚝 자동측정에 새 배출구 9번이 생김"}
        out = w.collapse_bursts(burst + [lone])
        self.assertEqual(sorted((e["kind"], e["tier"]) for e in out), [("배출구 목록 보강", "C"), ("새 배출구", "A")])
        c = next(e for e in out if e["tier"] == "C")
        self.assertIn("배출구 4개가 한꺼번에 새로 보임(1, 16, 2, 20)", c["text"])
        self.assertIn("처음엔 A로 띄웠다가 바로잡음", c["text"])
        prev = series(2)
        prev["events"] = burst + prev["events"]
        t = T0 + dt.timedelta(hours=6)
        doc = w.run(CFG_SMALL, now=t, previous=prev, key="k", get=Api(world(t)), sleep=lambda s: None)
        self.assertFalse(any(e["kind"] == "새 배출구" for e in doc["events"]))

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


class GatewayRetry(unittest.TestCase):
    def test_gateway_timeout_retried_once(self):
        timeout = R(200, '{"OpenAPI_ServiceResponse":{"cmmMsgHeader":{"returnReasonCode":"05"}}}')
        ok = R(200, json.dumps({"response": {"header": {"resultCode": "00"}, "body": {"items": []}}}))
        replies = [timeout, ok]
        w.fetch("고려아연", "k", get=lambda *a, **k: replies.pop(0), sleep=lambda s: None)
        self.assertEqual(replies, [])
        with self.assertRaisesRegex(w.ApiError, "코드 30"):
            w.fetch("고려아연", "k", get=lambda *a, **k: R(403, '{"OpenAPI_ServiceResponse":{"cmmMsgHeader":{"returnReasonCode":"30"}}}'), sleep=lambda s: None)


if __name__ == "__main__":
    unittest.main()
