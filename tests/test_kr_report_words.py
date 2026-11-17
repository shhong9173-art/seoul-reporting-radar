import datetime as dt
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import kr_report_words as w  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 11, 17, 13, 20, tzinfo=KST)


class Resp:
    def __init__(self, status, data):
        self.status_code, self._data = status, data

    def json(self):
        return self._data


def doc():
    return {"schema": "kr_report_notes/v1", "period": {"year": 2026, "report": "11014", "label": "2026년 3분기"},
            "companies": {
                "LG화학": {"status": "ok", "period": "202611014", "rcept": "20261116000765", "baseRcept": "20260814000765", "filed": "20261116"},
                "롯데케미칼": {"status": "ok", "period": "202611014", "rcept": "20261113001597", "baseRcept": "20260814001597", "filed": "20261113"},
                "현대차": {"status": "ok", "period": "202611014", "rcept": "20261116001437", "baseRcept": "20260814001437", "filed": "20261116"},
                "기아": {"status": "ok", "period": "202611014", "rcept": "20261116001529", "baseRcept": "20260814001529", "filed": "20261116",
                         "wordScan": {"v": w.VERSION, "rcept": "20261116001529"}},
                "옛 방식": {"status": "ok", "period": "202611014", "rcept": "20261116000003", "baseRcept": "20260814000003", "filed": "20261116",
                          "wordScan": {"rcept": "20261116000003"}},   # 1판(줄 단위)으로 비교한 보고서는 다시 본다
                "옛 기간": {"status": "ok", "period": "202611012", "rcept": "20260814000001", "baseRcept": "20260515000001"},
                "앞 보고서 없음": {"status": "ok", "period": "202611014", "rcept": "20261116000002", "baseRcept": None}},
            "events": [{"id": "rptnote:00356361:202611014:after", "kind": "보고기간 후 사건", "company": "LG화학",
                        "lines": ["〔앞 보고서에도 있던 건〕 2026년 10월 여수 NPG 공정을 매각하기로 결정하였습니다"]},
                       {"id": "rptword:20261113001597", "kind": w.KIND, "company": "롯데케미칼", "lines": ["옛 줄"]}]}


class Words(unittest.TestCase):
    def test_scan_new_lines_once_per_report_and_skip_notes_lines(self):
        sent = []

        def post(url, data=None, **kw):
            a = json.loads(data)
            sent.append((url.rsplit("/", 1)[-1], a["rcp"], a["base"]))
            if a["rcp"] == "20261116000765":
                return Resp(200, {"status": "ok", "lines": [
                    {"word": "매각", "line": "2026년 10월 여수 NPG 공정을 매각하기로 결정하였습니다"},          # 정기보고서 감시가 이미 잡은 줄
                    {"word": "매각", "line": "대산 SM 공장 매각 협상을 진행 중입니다"},
                    {"word": "가동중단", "line": "여수 NPG 공정은 2026년 12월 가동중단 예정입니다"},
                    {"word": "과징금", "line": "동 규정을 위반할 경우 매출액의 6%를 넘지 않는 과징금을 부과 받을 수 있습니다."},   # 일반 조항
                    {"word": "매각", "line": "당사는 2025년 7월 14일 공작기계사업부문 매각을 완료하였습니다."},                    # 앞 기간의 일
                    {"word": "과징금", "line": "당분기말 현재 진행 중인 소송의 최종 결과와 이에 따른 과징금 또는 벌금 등이 재무상태에 미칠 영향을 합리적으로 추정할 수 없어 충당부채를 인식하지 아니하였습니다."},
                    {"word": "과징금", "line": "⑧소프트웨어 업데이트 준수사항 미이행 과징금/과태료 제재(시행-2025.8.14) 등이 신설 되었습니다."},
                    {"word": "매각", "line": "2025년 배출권 매각 및 정부제출은 2026년 8월 중으로 확정되었습니다."},
                    {"word": "매각", "line": "8. 매각예정자산당분기말 현재 당사의 매각예정자산 내역은 다음과 같습니다."}]})
            if a["rcp"] == "20261113001597":
                return Resp(200, {"status": "missing", "cur": True, "base": False})
            return Resp(500, None)

        out, c = w.run(doc(), "t" * 43, post=post, now=NOW)
        self.assertEqual(sorted(sent), sorted([("dart-text-scan", "20261116000765", "20260814000765"), ("dart-text-scan", "20261113001597", "20260814001597"),
                                               ("dart-text-scan", "20261116001437", "20260814001437"), ("dart-text-scan", "20261116000003", "20260814000003")]))
        self.assertEqual(c, {"eligible": 5, "already": 1, "scanned": 1, "missing": 1, "failed": 2, "events": 1, "lines": 2})
        ev = [e for e in out["events"] if e["id"] == "rptword:20261116000765"][0]
        self.assertEqual(ev["lines"], ["〔가동중단〕 여수 NPG 공정은 2026년 12월 가동중단 예정입니다", "〔매각〕 대산 SM 공장 매각 협상을 진행 중입니다"])   # 무거운 낱말 먼저
        self.assertEqual((ev["kind"], ev["tier"], ev["company"], ev["url"]), (w.KIND, "B", "LG화학", "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261116000765"))
        self.assertNotIn("late", ev)
        self.assertIn("가동중단·매각 낱말이 든 줄 2개", ev["text"])
        self.assertEqual(out["companies"]["LG화학"]["wordScan"], {"v": w.VERSION, "rcept": "20261116000765", "base": "20260814000765", "at": NOW.isoformat(timespec="seconds"), "lines": 2, "raw": 9})
        self.assertNotIn("wordScan", out["companies"]["롯데케미칼"])        # 원문 미리 넣기 전 — 다음 실행
        self.assertTrue(any(e["id"] == "rptword:20261113001597" for e in out["events"]))   # 옛 이벤트는 그대로
        self.assertEqual(out["wordScan"]["scanned"], 1)

    def test_rescan_replaces_event_and_marks_late_reports(self):
        d = doc()
        d["companies"] = {"현대차": {**d["companies"]["현대차"], "filed": "20261113"}}
        d["events"].append({"id": "rptword:20261116001437", "kind": w.KIND, "company": "현대차", "lines": ["앞서 낸 줄"]})
        out, c = w.run(d, "t" * 43, post=lambda *a, **k: Resp(200, {"status": "ok", "lines": [{"word": "회생", "line": "당분기 중 협력사 A사가 회생절차 개시를 신청하였습니다"}]}), now=NOW)
        evs = [e for e in out["events"] if e["id"] == "rptword:20261116001437"]
        self.assertEqual(len(evs), 1)
        self.assertEqual((evs[0]["lines"], evs[0].get("late")), (["〔회생〕 당분기 중 협력사 A사가 회생절차 개시를 신청하였습니다"], True))   # 접수 나흘 뒤 처음 비교


    def test_rescan_with_no_lines_drops_old_version_event(self):
        d = doc()
        d["companies"] = {"현대차": {**d["companies"]["현대차"], "wordScan": {"v": 1, "rcept": "20261116001437"}}}
        d["events"].append({"id": "rptword:20261116001437", "kind": w.KIND, "company": "현대차", "lines": ["〔매각〕 1판이 낸 일반 조항"]})
        out, c = w.run(d, "t" * 43, post=lambda *a, **k: Resp(200, {"status": "ok", "lines": []}), now=NOW)
        self.assertFalse(any(e["id"] == "rptword:20261116001437" for e in out["events"]))
        self.assertEqual(out["companies"]["현대차"]["wordScan"]["v"], w.VERSION)


    def test_affiliate_lines_marked_and_sorted_last(self):
        d = doc()
        d["companies"] = {"GS": {"status": "ok", "period": "202611014", "rcept": "20261116001026", "baseRcept": "20260814001026", "filed": "20261116"}}
        lines = [{"word": "매각", "line": "연결실체의 종속회사인 (주)지에스이앤알의 경영진은 해남풍력사업 관련 건설중인자산을 매도하기 위한 계획을 수립하였고, 2026년 내 자산매각절차를 완료할 예정입니다."},
                 {"word": "영업정지", "line": "2026년 10월 2일 포스코이앤씨는 영업정지 8개월의 행정처분 사전통지서를 수령하였습니다."},
                 {"word": "청산", "line": "당분기 중 LG Chem Hai Phong Vietnam Co., Ltd.는 청산되었습니다."},
                 {"word": "과징금", "line": "당분기 중 개인정보보호위원회는 과징금 12,836백만원을 부과하였습니다."}]
        out, _ = w.run(d, "t" * 43, post=lambda *a, **k: Resp(200, {"status": "ok", "lines": lines}), now=NOW)
        ev = [e for e in out["events"] if e["id"] == "rptword:20261116001026"][0]
        self.assertEqual(ev["lines"], ["〔과징금〕 당분기 중 개인정보보호위원회는 과징금 12,836백만원을 부과하였습니다.",
                                       "〔청산〕 당분기 중 LG Chem Hai Phong Vietnam Co., Ltd.는 청산되었습니다.",      # 해외 법인은 그 회사 일
                                       "〔출입처 외 포스코이앤씨〕 〔영업정지〕 2026년 10월 2일 포스코이앤씨는 영업정지 8개월의 행정처분 사전통지서를 수령하였습니다.",
                                       "〔출입처 외 지에스이앤알〕 〔매각〕 연결실체의 종속회사인 (주)지에스이앤알의 경영진은 해남풍력사업 관련 건설중인자산을 매도하기 위한 계획을 수립하였고, 2026년 내 자산매각절차를 완료할 예정입니다."])


    def test_outsider_needs_company_mark_and_skips_beats(self):
        # 11-18 4판 실행에서 잘못 붙은 표시
        self.assertIsNone(w.outsider("(*14) 당분기 중 회사는 LG Chem Hai Phong Vietnam Co., Ltd.의 청산이 완료됨에 따라 해당 종속기업투자주식의 장부금액 3,079백만원을 제거하였습니다.", "LG화학"))
        self.assertIsNone(w.outsider("생산운영 효율화 계획에 따라 '26년 하반기 중에 중국 자회사 매각 및 노후화된 증평 공장의 생산 중단 추진 중이며", "SK이노베이션"))
        self.assertIsNone(w.outsider("(15) 오씨아이 주식회사 영업정지와 관련된 우발부채 당분기말 현재 종속회사 오씨아이 주식회사는 TDI 제조 및 판매 사업을 중단하기로 결정하였습니다.", "OCI홀딩스"))
        # 맞게 붙은 표시
        self.assertEqual(w.outsider("롯데에너지머티리얼즈의 종속회사인 롯데에코월(주)는 당분기 중 지분 매각(2026. 9. 3.)에 따라 지배력을 상실하여", "롯데케미칼"), "롯데에코월")
        self.assertEqual(w.outsider("연결실체는 종속기업인 롯데에너지머티리얼즈㈜의 종속기업인 롯데에코월㈜ 지분 매각과 관련하여", "롯데케미칼"), "롯데에너지머티리얼즈")
        self.assertEqual(w.outsider("연결실체의 종속회사인 (주)지에스이앤알의 경영진은", "GS"), "지에스이앤알")
        self.assertEqual(w.outsider("종속회사인 (주)한빛이 보유한", "GS"), "한빛")          # 받침 뒤 '이'는 조사
        self.assertEqual(w.outsider("종속회사인 (주)가나다아이 지분을", "GS"), "가나다아이")  # 받침 없는 '이'는 이름

if __name__ == "__main__":
    unittest.main()
