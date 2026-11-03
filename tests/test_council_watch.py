"""지방의회 회의록: 국회도서관 지방의정포털 Open API 안내(11-03 확인)의 응답 모양(RESULT_CODE·LIST 안 ROW, DOCID·RASMBLY_NM·MTGNM·MTG_DE,
상세 MTR_SJ·MINTS_HTML·ORGINL_FILE_URL)으로 목록·대목·등급, 키 미설정은 '미설정'(0건 아님), 첫 실행 기준선, 상한 넘은 회의록·상세 실패는
다음 실행에, 키 오류는 더 묻지 않음. 실제 응답 확인은 키를 넣은 첫 실행에서."""
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import council_watch as w  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 11, 4, 7, 15, tzinfo=KST)


def lst(*rows):
    return {"SERVICE": "minutes", "RESULT_CODE": "SUCCESS", "RESULT_MESSAGE": "정상", "TOTAL_COUNT": len(rows), "LIST_COUNT": len(rows),
            "LIST": [{"ROW": r} for r in rows]}


def row(did, council, date, name="제300회 본회의"):
    return {"DOCID": did, "RASMBLY_ID": "041001", "RASMBLY_NM": council, "RASMBLY_NUMPR": "9", "RASMBLY_SESN": "300", "MINTS_ODR": "2", "MTGNM": name, "MTG_DE": date}


DETAIL = {
    "CLIKC1": {"MTR_SJ": "1. 시정에 관한 질문", "ORGINL_FILE_URL": "https://example.go.kr/minutes/1.hwp",
               "MINTS_HTML": "<p>○ 김의원: 화성시 우정읍 기아 오토랜드 화성 인근 부지에 신차 2000대가 공장 시설로 허가받은 땅에 야적되고 있습니다. 불법 아닙니까?</p>"},
    "CLIKC2": {"MTR_SJ": "2. 예산안", "MINTS_HTML": "<p>○ 이의원: 현대제철 당진제철소 직원 봉사활동에 감사드립니다.</p>"},
    "CLIKC3": {"MTR_SJ": "3. 행정사무감사", "MINTS_HTML": "<p>포스코퓨처엠 광양 공장 견학</p>"},
}


class R:
    def __init__(self, body):
        self.body = body

    def json(self):
        return self.body


def fake(lists, fail_detail=(), code=None):
    calls = []

    def get(url, params=None, headers=None, timeout=None):
        calls.append(dict(params))
        if params["displayType"] == "list":
            if code:
                return R({"RESULT_CODE": code, "RESULT_MESSAGE": "인증키 오류"})
            return R(lists.get(params["searchKeyword"], lst()))
        if params["docid"] in fail_detail:
            raise type("ReadTimeout", (Exception,), {})("x")
        return R({"RESULT_CODE": "SUCCESS", "LIST": [{"ROW": {**DETAIL[params["docid"]], "DOCID": params["docid"]}}]})
    return get, calls


class Run(unittest.TestCase):
    def test_not_configured_is_not_zero(self):
        doc = w.run(NOW, None, key="", get=lambda *a, **k: None, sleep=lambda s: None)
        self.assertEqual((doc["status"], doc["checks"][0]["status"]), ("not_configured", "unset"))   # 레이더 수집 상태에 '미설정'으로
        self.assertIn("CLIK_API_KEY 미설정", doc["checks"][0]["error"])

    def test_baseline_then_new_minutes(self):
        get, calls = fake({"기아자동차": lst(row("CLIKC0", "화성시의회", "20261001"))})
        doc = w.run(NOW, None, key="k", get=get, sleep=lambda s: None)
        self.assertFalse([c for c in calls if c["displayType"] == "detail"])   # 기준선은 상세를 열지 않는다
        self.assertIn("CLIKC0", doc["seen"])
        lists = {"기아자동차": lst(row("CLIKC1", "화성시의회", "20261020"), row("CLIKC0", "화성시의회", "20261001")),
                 "현대제철": lst(row("CLIKC2", "당진시의회", "20261015")), "포스코": lst(row("CLIKC3", "광양시의회", "20261012"))}
        get2, calls2 = fake(lists)
        doc2 = w.run(NOW + dt.timedelta(days=1), doc, key="k", get=get2, sleep=lambda s: None)
        self.assertEqual(sorted(c["docid"] for c in calls2 if c["displayType"] == "detail"), ["CLIKC1", "CLIKC2", "CLIKC3"])
        by = {x["id"]: x for x in doc2["items"]}
        self.assertEqual((by["clik:CLIKC1"]["tier"], by["clik:CLIKC1"]["company"]), ("A", "기아"))
        self.assertEqual(by["clik:CLIKC2"]["tier"], "C")          # 사건 낱말 없음 — 참고
        self.assertNotIn("clik:CLIKC3", by)                        # 포스코퓨처엠만 — 대목 없음
        ev = doc2["events"]
        self.assertEqual(len(ev), 1)
        self.assertIn("화성시의회 제300회 본회의(20261020) 회의록 · 기아 대목 「", ev[0]["text"])
        self.assertIn("신차 2000대가 공장 시설로 허가받은 땅에 야적", ev[0]["text"])
        self.assertIn("회의록 번호 CLIKC1(국회도서관 지방의정포털)", ev[0]["text"])
        self.assertEqual(ev[0]["url"], "https://example.go.kr/minutes/1.hwp")

    def test_failures(self):
        get, _ = fake({})
        doc = w.run(NOW, None, key="k", get=get, sleep=lambda s: None)
        get2, _ = fake({"기아자동차": lst(row("CLIKC1", "화성시의회", "20261020"))}, fail_detail=("CLIKC1",))
        doc2 = w.run(NOW, doc, key="k", get=get2, sleep=lambda s: None)
        self.assertNotIn("CLIKC1", doc2["seen"])                   # 상세 실패 — 다음 실행에 다시
        self.assertEqual(doc2["status"], "partial")
        get3, calls3 = fake({}, code="ERROR01")
        bad = w.run(NOW, doc, key="k", get=get3, sleep=lambda s: None)
        self.assertEqual(len(calls3), 1)                            # 키 오류면 더 묻지 않는다
        self.assertEqual((bad["status"], bad["checks"][0]["status"]), ("failed", "failed"))
        self.assertIn("ERROR01", bad["checks"][0]["error"])


if __name__ == "__main__":
    unittest.main()
