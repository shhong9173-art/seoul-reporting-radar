"""미국 OSHA 감시: 10-31 탐침의 실제 응답 모양({"data": [...]}, 204는 0건, 필드 이름 그대로)으로
회사별 이름 규칙(딜러·이름 겹침 버림, 버린 이름은 남김), like 5개씩 나눠 묻기와 호출 간격, 429 한 번 다시,
첫 실행 기준선, 새 점검 등급(사망·중대사고 A·민원 B·정기 C), 새 위반 통지 등급(반복·고의·10만 달러 A, 중대 B), 삭제 표시 위반 제외,
사망 사고 요약 A, 오래된 개시·통지는 이벤트 아님, 점검 조회 전부 실패는 미확인·지난 목록 유지, 일부 실패는 지난 점검을 지우지 않음."""
import datetime as dt
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import us_osha_watch as w  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 11, 2, 6, 40, tzinfo=KST)


def insp(nr, name, opened, typ="B", city="WEST POINT", state="GA", closed=None):
    return {"activity_nr": nr, "estab_name": name, "site_city": city, "site_state": state, "open_date": f"{opened}T00:00:00",
            "insp_type": typ, "insp_scope": "B", "close_case_date": f"{closed}T00:00:00" if closed else None, "naics_code": "336111", "nr_in_estab": 2700}


def viol(nr, cit, typ, issued, penalty, deleted=None):
    return {"activity_nr": nr, "citation_id": cit, "viol_type": typ, "issuance_date": f"{issued}T00:00:00", "initial_penalty": penalty,
            "current_penalty": penalty, "standard": "19100147 C04 I", "delete_flag": deleted}


class R:
    def __init__(self, code=200, body=None):
        self.status_code, self.body = code, body

    def json(self):
        return self.body


def fake(inspections, violations=(), injuries=(), accidents=(), calls=None, fail=None):
    """inspections: 모든 점검 행. like 묶음 질의에는 이름이 그 묶음의 like에 걸리는 행만 돌려준다."""
    fail = list(fail or [])

    def like(name, pat):
        return pat.strip("%") in (name or "").upper()

    def get(url, params=None, headers=None, timeout=None):
        ep = url.split("/OSHA/")[1].split("/")[0]
        if calls is not None:
            calls.append(ep)
        if fail:
            code = fail.pop(0)
            if code:
                return R(code)
        f = json.loads(params["filter_object"])
        if ep == "inspection":
            pats = [c["value"] for c in f["and"][1]["or"]]
            rows = [x for x in inspections if any(like(x["estab_name"], p) for p in pats) and x["open_date"][:10] > f["and"][0]["value"]]
        elif ep == "violation":
            rows = [v for v in violations if v["activity_nr"] in f["value"]]
        elif ep == "accident_injury":
            rows = [i for i in injuries if i["rel_insp_nr"] in f["value"]]
        else:
            rows = [a for a in accidents if a["summary_nr"] in f["value"]]
        return R(200, {"data": rows}) if rows else R(204)
    return get


SLEEPS = []


def run(prev=None, now=NOW, **k):
    return w.run(now=now, key="K", previous=prev, get=fake(**k), sleep=SLEEPS.append)


BASE = [insp(1001, "KIA GEORGIA INC", "2026-09-01", "M"), insp(1002, "HYUNDAI MOTOR MANUFACTURING ALABAMA, LLC", "2026-10-08", "B", "MONTGOMERY", "AL"),
        insp(1003, "PAT PECK KIA OF GULFPORT", "2026-10-01", "B"), insp(1004, "ARMANDO'S MANDO GRILL", "2026-10-02", "C"),
        insp(1005, "HANKOOK TIRE MANUFACTURING TENNESSEE LP", "2026-03-03", "H", "CLARKSVILLE", "TN", closed="2026-09-01")]


class Run(unittest.TestCase):
    def test_baseline_rules_and_dropped_names(self):
        SLEEPS.clear()
        calls = []
        doc = run(inspections=BASE, violations=[viol(1005, "01001", "S", "2026-06-01", 16550)], calls=calls)
        self.assertEqual(doc["checks"][0]["status"], "ok")
        self.assertEqual({x["id"]: x["company"] for x in doc["inspections"]}, {"1001": "기아", "1002": "현대차", "1005": "한국타이어"})
        self.assertEqual(dict(doc["dropped"]), {"PAT PECK KIA OF GULFPORT": 1, "ARMANDO'S MANDO GRILL": 1})
        self.assertEqual(doc["events"], [])
        self.assertEqual(calls.count("inspection"), 7)               # like 31개를 5개씩
        self.assertTrue(all(s == w.GAP for s in SLEEPS))
        h = next(x for x in doc["inspections"] if x["id"] == "1005")
        self.assertEqual((h["penaltyInitial"], h["violations"][0]["typeName"]), (16550, "중대"))
        self.assertEqual(next(x for x in doc["inspections"] if x["id"] == "1001")["typeName"], "사망·중대사고")
        self.assertEqual(h["url"], "https://www.osha.gov/ords/imis/establishment.inspection_detail?id=1005")

    def test_next_run_events_and_tiers(self):
        first = run(inspections=BASE)
        more = BASE + [insp(1006, "HANWHA QCELLS GEORGIA INC", "2026-10-28", "M", "DALTON"),
                       insp(1007, "MOBIS ALABAMA LLC", "2026-10-29", "H", "MONTGOMERY", "AL"),
                       insp(1008, "SUPERIOR ESSEX INC", "2025-02-01", "B", "FORT WAYNE", "IN")]  # 옛 점검이 처음 잡힘 — 이벤트 아님
        vs = [viol(1002, "01001", "R", "2026-10-30", 48000), viol(1002, "01002", "S", "2026-10-30", 16550),
              viol(1001, "01001", "S", "2026-10-30", 16550), viol(1001, "01002", "O", "2026-10-30", 0, deleted="X"),
              viol(1005, "01002", "S", "2026-10-30", 9000)]
        inj = [{"summary_nr": 777, "rel_insp_nr": 1001, "degree_of_inj": "1"}]
        acc = [{"summary_nr": 777, "event_date": "2026-08-28T00:00:00", "event_desc": "Worker struck by press", "fatality": "X", "abstract_text": "At 10 a.m. ..."}]
        doc = run(first, now=NOW + dt.timedelta(days=1), inspections=more, violations=vs, injuries=inj, accidents=acc)
        ev = {e["id"]: e for e in doc["events"]}
        self.assertEqual(ev["osha:insp:1006"]["tier"], "A")
        self.assertEqual(ev["osha:insp:1007"]["tier"], "C")
        self.assertNotIn("osha:insp:1008", ev)
        self.assertEqual(ev["osha:viol:1002:2026-10-30"]["tier"], "A")          # 반복
        self.assertIn("2건(반복·중대) · 최초 벌금 합 $64,550", ev["osha:viol:1002:2026-10-30"]["text"])
        self.assertEqual(ev["osha:viol:1001:2026-10-30"]["tier"], "B")          # 중대, 삭제 표시는 빠짐
        self.assertIn("1건(중대)", ev["osha:viol:1001:2026-10-30"]["text"])
        self.assertEqual(ev["osha:viol:1005:2026-10-30"]["tier"], "B")
        self.assertEqual(ev["osha:acc:777"]["tier"], "A")
        self.assertIn("사망", ev["osha:acc:777"]["text"])
        self.assertTrue(next(x for x in doc["inspections"] if x["id"] == "1006")["isNew"])

    def test_big_penalty_is_a(self):
        self.assertEqual(w.viol_tier([{"type": "S", "initialPenalty": 60000}, {"type": "S", "initialPenalty": 45000}]), "A")
        self.assertEqual(w.viol_tier([{"type": "O", "initialPenalty": 0}]), "C")

    def test_429_is_retried_once_after_30s(self):
        SLEEPS.clear()
        doc = run(inspections=BASE, fail=[429])
        self.assertEqual(doc["checks"][0]["status"], "ok")
        self.assertIn(30, SLEEPS)

    def test_all_inspection_queries_failing_is_unconfirmed_and_keeps_previous(self):
        first = run(inspections=BASE)
        doc = run(first, now=NOW + dt.timedelta(days=1), inspections=BASE, fail=[503] * 7)
        self.assertEqual(doc["checks"][0]["status"], "failed")
        self.assertEqual(len(doc["inspections"]), 3)
        self.assertTrue(all(x["stale"] for x in doc["inspections"]))
        self.assertEqual(doc["events"], [])

    def test_partial_failure_keeps_previous_inspections_unmarked_as_new(self):
        first = run(inspections=BASE)
        doc = run(first, now=NOW + dt.timedelta(days=1), inspections=BASE, fail=[503, 0, 0, 0, 0, 0, 0])
        self.assertEqual(doc["checks"][0]["status"], "partial")
        ids = {x["id"] for x in doc["inspections"]}
        self.assertTrue({"1001", "1002", "1005"} <= ids)
        self.assertEqual(doc["events"], [])

    def test_company_rules(self):
        self.assertEqual(w.company_of("Hyundai Motor Group Metaplant America LLC"), "현대차")
        self.assertEqual(w.company_of("HL-GA BATTERY COMPANY LLC"), "현대차(관련 합작)")
        self.assertIsNone(w.company_of("HYUNDAI OF WESLEY CHAPEL"))
        self.assertIsNone(w.company_of("POSCO INTERNATIONAL AMERICA"))
        self.assertEqual(w.company_of("LS GREENLINK USA INC"), "LS전선")


if __name__ == "__main__":
    unittest.main()
