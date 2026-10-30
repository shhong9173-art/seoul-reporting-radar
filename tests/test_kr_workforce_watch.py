"""출입처 사업장 인력 감시(국민연금): 10-30 실제 응답 칸 모양의 가짜 API로 자사 사업장 이름 규칙, 공사 현장 등급(투자 낱말·보수 제외·
아파트 제외·'경기아트' 같은 부분 일치 제외), 첫 실행 기준선, 지난 12개월 채우기, 지난달 대비 증감 등급, 새 달의 새 현장·탈퇴·빠짐,
실패·일부 실패는 미확인."""
import datetime as dt
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import kr_workforce_watch as w  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 10, 30, 9, 0, tzinfo=KST)
CFG = {"sentinel": "현대제철(주)", "companies": [
    c for c in json.loads((Path(__file__).resolve().parents[1] / "data" / "workforce_watch.json").read_text(encoding="utf-8"))["companies"]
    if c["company"] in ("현대제철", "기아")]}


def rec(seq, ym, name, dg="47", sg="111", stcd="1", addr=""):
    # getBassInfoSearchV2 item 칸(10-30 실제 응답과 같은 이름)
    return {"bzowrRgstNo": "121811****", "dataCrtYm": ym, "ldongAddrMgplDgCd": dg, "ldongAddrMgplSgguCd": sg, "ldongAddrMgplSgguEmdCd": "101",
            "seq": seq, "wkplJnngStcd": stcd, "wkplNm": name, "wkplRoadNmDtlAddr": addr, "wkplStylDvcd": "1"}


class FakeApi:
    """검색은 이름 포함·seq 내림차순·쪽 나눔, 상세·기간별 현황은 seq로. down: 실패할 검색어, key_error: 표지부터 코드 30."""

    def __init__(self, records, details, periods=None, down=(), key_error=False, clock=None, tick=0.0):
        self.records, self.details, self.periods = records, details, periods or {}
        self.down, self.key_error, self.calls, self.log = set(down), key_error, 0, []
        self.clock, self.tick = clock, tick

    def call(self, op, params, *, rows=100, page=1):
        self.calls += 1
        if self.clock:
            self.clock.t += self.tick  # 실제 API는 한 번에 1~10초
        self.log.append((op, params.get("wkplNm") or params.get("seq"), page))
        if self.key_error:
            raise w.ApiError("코드 30")
        if op == "getBassInfoSearchV2":
            if params["wkplNm"] in self.down:
                raise w.ApiError("HTTP 502")
            hit = sorted([r for r in self.records if params["wkplNm"] in r["wkplNm"]], key=lambda r: -r["seq"])
            return len(hit), hit[(page - 1) * rows:page * rows]
        if op == "getDetailInfoSearchV2":
            d = self.details.get(params["seq"])
            return (1, [d]) if d else (0, [])
        if op == "getPdAcctoSttusInfoSearchV2":
            acq, loss = self.periods.get(params["seq"], (0, 0))
            return 1, [{"nwAcqzrCnt": acq, "lssJnngpCnt": loss}]
        raise AssertionError(op)


def det(members, adpt="20000316", industry="제철업", scsn="00010101"):
    return {"jnngpCnt": members, "adptDt": adpt, "vldtVlKrnNm": industry, "scsnDt": scsn, "crrmmNtcAmt": "1"}


def world(oct_data=False):
    """8·9월(필요하면 10월) 자료. seq는 달이 바뀌면 커진다(실제 응답처럼 최신 달이 먼저)."""
    r, d, p = [], {}, {}
    months = ["202608", "202609"] + (["202610"] if oct_data else [])
    pohang = {"202608": 1252, "202609": 1150, "202610": 1140}
    hwaseong = {"202608": 11586, "202609": 11560, "202610": 11300}
    dangjin = {"202608": 5000, "202609": 5001, "202610": 5003}
    for i, ym in enumerate(months):
        base = 1000 * (i + 1)
        r += [rec(base + 1, ym, "현대제철(주)포항1공장"), rec(base + 2, ym, "현대제철주식회사당진공장", "44", "270", addr="충청남도 당진시 송악읍 북부산업로"),
              rec(base + 3, ym, "현대제철당진어린이집", "44", "270"), rec(base + 4, ym, "기아(주)AutoLand화성", "41", "591"),
              rec(base + 5, ym, "경기아트센터/일용/전기공사", "41", "111"), rec(base + 6, ym, "(주)휴먼하우징/일용/현대제철 사택 아파트 보수", "44", "270")]
        d[base + 1], d[base + 2], d[base + 4] = det(pohang[ym]), det(dangjin[ym]), det(hwaseong[ym], "19911220", "자동차 제조업")
        p[base + 1] = (4, 106) if ym == "202609" else (6, 10)
    # 9월부터 있던 공사 현장(기준선)
    r += [rec(1101, "202609", "거명이앤씨(주)/일용/(기계공사)당진 현대제철 1고로 원료 집진설비 개선 PJT", "44", "270"),
          rec(1102, "202609", "경운기술산업(주)/일용/현대제철 당진제철소 LNG 자가발전 사업/비계 공사", "44", "270")]
    if oct_data:
        r += [rec(3101, "202610", "(주)대한건설/일용/현대제철 당진 전기로 신설공사 기계설치", "44", "270"),
              rec(3102, "202610", "영일전설(주)/일용/2026 당진 현대제철 전기공사", "44", "270"),
              rec(3103, "202610", "삼우기전/상용/기아 오토랜드 화성 PBV 2공장 신축공사 전기", "41", "591"),
              rec(3104, "202610", "청소나라/용역/현대제철 당진 사무동 청소", "44", "270"),
              rec(3105, "202610", "현대제철 순천공장", "12", "150"),
              rec(3106, "202610", "거명이앤씨(주)/일용/(기계공사)당진 현대제철 1고로 원료 집진설비 개선 PJT", "44", "270"),
              rec(3107, "202610", "대선이엔씨(주)/일용/현대제철 당진제철소 LNG 자가발전 사업/전기 공사", "44", "270")]
        d[3101], d[3102], d[3103] = det(41, "20261005", "기계장비 설치"), det(12, "20260912", "전기공사업"), det(77, "20261002", "전기공사업")
        d[3105] = det(310, "20260901", "냉간 압연")
        # 당진공장이 10월에 '현대제철주식회사 당진제철소'로 이름이 바뀐 것처럼 10월 줄을 빼 본다
        r = [x for x in r if not (x["dataCrtYm"] == "202610" and x["wkplNm"] == "현대제철주식회사당진공장")]
    return r, d, p


class Clock:
    def __init__(self, step=0.0):
        self.t, self.step = 0.0, step

    def __call__(self):
        self.t += self.step
        return self.t


class WorkforceTest(unittest.TestCase):
    def test_name_rules_and_project_tiers(self):
        own = {c["company"]: __import__("re").compile(c["own"]) for c in json.loads(w.CONFIG.read_text(encoding="utf-8"))["companies"]}
        self.assertTrue(own["현대제철"].search("현대제철(주)포항1공장") and own["현대제철"].search("현대제철 순천공장"))
        self.assertTrue(own["현대제철"].search("현대제철주식회사본사"))
        self.assertFalse(own["현대제철"].search("현대제철당진어린이집") or own["현대제철"].search("현대제철새마을금고"))
        self.assertTrue(own["기아"].search("기아(주) AutoLand광주") and own["기아"].search("기아 주식회사"))
        self.assertFalse(own["기아"].search("기아타이거즈(주)"))
        self.assertTrue(own["포스코"].search("주식회사포스코"))
        self.assertFalse(own["포스코"].search("(주)포스코퓨처엠") or own["포스코"].search("주식회사 포스코지와이알테크"))
        self.assertTrue(own["현대차"].search("현대자동차(주)"))
        self.assertFalse(own["현대차"].search("현대자동차(주)노동조합") or own["현대차"].search("방축점현대자동차(주)"))
        import re
        car, steel = re.compile("(?<![가-힣])현대(?:자동차|차)(?!운전|학원|공업|해체|운수)"), re.compile("현대제철")
        # 10-30 실제 이름: 한 공사에 시공사·공종별 현장이 여럿 — 공사 이름으로 묶는다
        for n in ("(주)디투엔지니어링/일용/현대자동차 0-프로젝트 건설공사 중 일반전기공사(HOOK-UP조립)", "주식회사 디와이시/일용/현대자동차 0-프로젝트 건설공사",
                  "두양건축(주)/상용/현대자동차 0-프로젝트 건설공사 중 인테리어공사(2공구)", "（주）동영산업/일용/현대자동차 0-프로젝트 건설공사 / 철재창호"):
            self.assertEqual(w.project_key(n, car), "현대자동차 0-프로젝트", n)
        kia = re.compile("(?<![가-힣])기아(?!대책|타이거즈|오토큐|현대특장)")
        for n in ("A/일용/AutoLand 화성 기아 LW 프로젝트 부대토목공사 (차체공장)", "B/상용/AutoLand 화성 기아 LW 프로젝트중일반전기공사(프레스선진화)"):
            self.assertEqual(w.project_key(n, kia), "AutoLand 화성 기아 LW 프로젝트", n)
        self.assertEqual(w.project_key("C/일용/현대제철 당진 LNG 자가발전사업, 수처리 기계설치공사", steel), "현대제철 당진 LNG 자가발전사업")
        posco = re.compile(next(c["word"] for c in json.loads(w.CONFIG.read_text(encoding="utf-8"))["companies"] if c["company"] == "포스코"))
        self.assertTrue(posco.search("D/일용/포스코(광양)#1 전기로 신설_400톤 이상 크레인") and posco.search("E/일용/포스코광양제철소 3고로"))
        self.assertFalse(posco.search("광양 포스코중타이에어솔루션 희귀가스공장 건설공사") or posco.search("포스코이앤씨/일용/아파트")
                         or posco.search("포스코서리풀 업무복합시설"))
        self.assertEqual(w.project_key("더원종합건설 주식회사-(일용)현대자동차 인증중고차 군산센터 신축공사", car), "현대자동차 인증중고차 군산센터 신축공사")
        self.assertEqual(w.project_key("디씨티준오 주식회사/일용/23년 현대제철 1,2연주기 ASTC확대적용, 전기설치공사", steel), "현대제철 1,2연주기 ASTC확대적용, 전기설치공사")
        self.assertEqual(w.project_key("거명이앤씨(주)/일용/(기계공사)당진 현대제철 1고로 원료 집진설비 개선 PJT", steel), "당진 현대제철 1고로 원료 집진설비 개선 PJT")
        self.assertEqual(w.project_tier("현대자동차 0-프로젝트"), "A")
        self.assertEqual(w.project_tier("현대제철:순천냉연공장 계근대 사무실 신축공사"), "B")
        self.assertEqual(w.project_tier("포스코(광양)전기로 철도건널목 Smart CCTV 시스템 구축"), "B")
        self.assertEqual(w.project_tier("대한전선(주) 당진해저케이블 2공장 신축공사"), "A")
        self.assertEqual(w.project_tier("현대제철 당진 전기로 신설공사 기계설치"), "A")
        self.assertEqual(w.project_tier("현대자동차 인증중고차 군산센터 신축공사"), "B")  # 서비스·판매 시설 신축은 공장 투자가 아님
        self.assertEqual(w.project_tier("현대자동차 남양연구소 기숙사 신축"), "B")
        self.assertEqual(w.project_tier("당진 현대제철 1고로 원료 집진설비 개선 PJT"), "C")  # 개선(보수 낱말)
        self.assertEqual(w.project_tier("당진 현대제철 전기공사"), "B")
        self.assertEqual(w.project_tier("현대제철 당진 사무동 청소"), "C")
        self.assertEqual(w.month_before("202601"), "202512")

    def test_baseline_backfill_then_delta(self):
        r, d, p = world()
        api = FakeApi(r, d, p)
        first = w.run(CFG, now=NOW, api=api, clock=Clock())
        self.assertEqual((first["status"], first["month"], first["scanStatus"]), ("complete", "202609", "complete"))
        self.assertEqual(first["events"], [])  # 기준선
        names = sorted(s["name"] for s in first["sites"])
        self.assertEqual(names, ["기아(주)AutoLand화성", "현대제철(주)포항1공장", "현대제철주식회사당진공장"])
        pohang = next(s for s in first["sites"] if "포항" in s["name"])
        self.assertEqual(pohang["history"], {"202609": {"members": 1150, "acq": 4, "loss": 106}, "202608": {"members": 1252, "acq": 6, "loss": 10}})
        self.assertEqual(pohang["backfilledMonth"], "202609")
        # 공사 현장: 9월 기준선, 아파트 보수·'경기아트센터'는 빠지고 보수·개선(C)은 보관 안 함
        self.assertEqual([(x["company"], x["title"], x["tier"], x["baseline"]) for x in first["projects"]],
                         [("현대제철", "현대제철 당진제철소 LNG 자가발전 사업", "A", True)])
        self.assertEqual(len(first["projectSeen"]), 2)
        # 같은 달 다음 실행: 검색을 다시 하지 않고 지난달 대비 변화만 낸다(포항 -102명 -8.1% → A, 화성 -26명 → 없음)
        api2 = FakeApi(r, d, p)
        second = w.run(CFG, now=NOW + dt.timedelta(hours=7), previous=first, api=api2, clock=Clock())
        self.assertEqual([x for x in api2.log if x[0] == "getBassInfoSearchV2"], [("getBassInfoSearchV2", "현대제철(주)", 1)])
        self.assertEqual([(e["tier"], e["kind"], e["company"]) for e in second["events"]], [("A", "인력 감소", "현대제철")])
        self.assertIn("현대제철(주)포항1공장(경북 시군구코드 111) 국민연금 가입자 1,252→1,150명(-102명, -8.1%) · 그달 신규 취득 4·상실 106 — 2026-09 자료",
                      second["events"][0]["text"])
        third = w.run(CFG, now=NOW + dt.timedelta(days=1), previous=second, api=FakeApi(r, d, p), clock=Clock())
        self.assertEqual(len(third["events"]), 1)  # 같은 변화는 한 번만

    def test_new_month_events(self):
        r, d, p = world()
        first = w.run(CFG, now=NOW, api=FakeApi(r, d, p), clock=Clock())
        r2, d2, p2 = world(oct_data=True)
        doc = w.run(CFG, now=NOW + dt.timedelta(days=20), previous=first, api=FakeApi(r2, d2, p2), clock=Clock())
        self.assertEqual(doc["month"], "202610")
        got = sorted((e["tier"], e["kind"], e["company"]) for e in doc["events"])
        self.assertEqual(got, sorted([("A", "새 공사 현장", "현대제철"), ("A", "새 공사 현장", "기아"), ("B", "새 공사 현장 묶음", "현대제철"),
                                      ("A", "새 자사 사업장", "현대제철"), ("B", "자사 사업장 목록에서 빠짐", "현대제철"),
                                      ("B", "인력 변동", "기아")]))  # 포항 1,150→1,140(-10)은 기준 미달
        ev = {e["kind"] + e["company"]: e["text"] for e in doc["events"]}
        self.assertIn("「현대제철 당진 전기로 신설공사 기계설치」 · 충남 시군구코드 270 · 첫 현장 적용 2026-10-05 · 가입자 41명 · 현장 이름 예 「(주)대한건설/일용/",
                      ev["새 공사 현장현대제철"])
        self.assertIn("기아 오토랜드 화성 PBV 2공장 신축공사", ev["새 공사 현장기아"])
        self.assertIn("현대제철 이름이 든 새 공사 1건(2026-10 자료): 「당진 현대제철 전기공사」(첫 현장 적용 2026-09-12, 가입자 12명)",
                      ev["새 공사 현장 묶음현대제철"])
        self.assertIn("현대제철 순천공장", ev["새 자사 사업장현대제철"])
        self.assertIn("2026-09에 있던 사업장이 2026-10 검색 결과에 없음", ev["자사 사업장 목록에서 빠짐현대제철"])
        self.assertIn("11,560→11,300명(-260명, -2.2%)", ev["인력 변동기아"])
        self.assertNotIn("청소", json.dumps(doc["events"], ensure_ascii=False))
        # 이미 아는 공사(9월 기준선 'LNG 자가발전 사업')에 시공사 현장이 하나 더 생기면 이벤트 없이 현장 수만 는다
        self.assertNotIn("자가발전", json.dumps(doc["events"], ensure_ascii=False))
        lng = next(x for x in doc["projects"] if "자가발전" in x["title"])
        self.assertEqual((lng["sites"], lng["baseline"]), (2, True))

    def test_failures_are_unconfirmed(self):
        r, d, p = world()
        first = w.run(CFG, now=NOW, api=FakeApi(r, d, p), clock=Clock())
        bad = w.run(CFG, now=NOW + dt.timedelta(days=1), previous=first, api=FakeApi(r, d, p, key_error=True), clock=Clock())
        self.assertEqual(bad["status"], "failed")
        self.assertIn("표지 조회 코드 30", bad["checks"][0]["error"])
        self.assertEqual(len(bad["sites"]), 3)  # 지난 결과 그대로
        # 새 달인데 '기아' 검색이 실패: 일부 실패, 기아 사업장은 빠짐으로 보지 않는다
        r2, d2, p2 = world(oct_data=True)
        doc = w.run(CFG, now=NOW + dt.timedelta(days=20), previous=first, api=FakeApi(r2, d2, p2, down={"기아"}), clock=Clock())
        self.assertEqual((doc["status"], doc["scanStatus"]), ("partial", "partial"))
        self.assertIn("기아(HTTP 502)", doc["checks"][0]["error"])
        self.assertFalse(any(e["company"] == "기아" and e["kind"] in ("자사 사업장 목록에서 빠짐", "새 공사 현장") for e in doc["events"]))
        # 화성 사업장 10월 수치는 사업장 이름 검색(채우기)으로 따로 읽혀 비교된다
        self.assertTrue(any(e["company"] == "기아" and e["kind"] == "인력 변동" for e in doc["events"]))
        # 다음 실행은 같은 달이어도 다시 전체를 읽는다
        again = w.run(CFG, now=NOW + dt.timedelta(days=21), previous=doc, api=FakeApi(r2, d2, p2), clock=Clock())
        self.assertEqual(again["scanStatus"], "complete")
        self.assertTrue(any(e["company"] == "기아" and e["kind"] == "새 공사 현장" for e in again["events"]))

    def test_time_budget_leaves_history_for_later(self):
        r, d, p = world()
        clock = Clock()
        doc = w.run(CFG, now=NOW, api=FakeApi(r, d, p, clock=clock, tick=30.0), clock=clock, budget=400)
        pending = next(c for c in doc["checks"] if "채우기" in c["source"])["pending"]
        self.assertGreater(pending, 0)
        self.assertEqual(doc["scanStatus"], "complete")



class GatewayRetry(unittest.TestCase):
    def test_gateway_timeout_is_retried_once_but_key_errors_are_not(self):
        # 10-30 운영: '지난 달 채우기 코드 05'(SERVICE_TIMEOUT)로 그 실행 검색이 일부 실패
        class Resp:
            def __init__(self, text, status=200):
                self.text, self.status_code = text, status
        timeout = '{"OpenAPI_ServiceResponse":{"cmmMsgHeader":{"returnAuthMsg":"SERVICE_TIMEOUT_ERROR","returnReasonCode":"05"}}}'
        ok = '{"response":{"header":{"resultCode":"00"},"body":{"totalCount":1,"items":{"item":[{"seq":"1"}]}}}}'
        replies, waits = [Resp(timeout), Resp(ok)], []
        api = w.Api("k", get=lambda *a, **k: replies.pop(0), sleep=waits.append)
        self.assertEqual(api.call("getBassInfoSearchV2", {}), (1, [{"seq": "1"}]))
        self.assertEqual((api.calls, waits[0]), (2, 3.0))
        api = w.Api("k", get=lambda *a, **k: Resp(timeout), sleep=lambda s: None)
        with self.assertRaisesRegex(w.ApiError, "코드 05"):
            api.call("getBassInfoSearchV2", {})
        self.assertEqual(api.calls, 2)
        denied = '{"OpenAPI_ServiceResponse":{"cmmMsgHeader":{"returnReasonCode":"30"}}}'
        api = w.Api("k", get=lambda *a, **k: Resp(denied), sleep=lambda s: None)
        with self.assertRaisesRegex(w.ApiError, "코드 30"):
            api.call("getBassInfoSearchV2", {})
        self.assertEqual(api.calls, 1)  # 키 오류는 다시 부르지 않음


if __name__ == "__main__":
    unittest.main()
