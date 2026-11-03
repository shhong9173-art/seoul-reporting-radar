"""지방의회 회의록: 국회도서관 지방의정포털 Open API 실제 응답 모양(11-03 탐침 150: 맨 바깥 목록 `[{SERVICE, RESULT_CODE, LIST: [{ROW}]}]`,
상세는 칸이 맨 바깥 사전에 바로 — DOCID·MTR_SJ·MINTS_HTML·ORGINL_FILE_URL 빈 값, MTGNM에 줄바꿈 '[임시]')으로 목록·대목·등급, 키 미설정은
'미설정'(0건 아님), 첫 실행 기준선, 상한 넘은 회의록·상세 실패는 다음 실행에, 없는 회의록 번호(SUCCESS에 칸만 빔)는 세 번 뒤 넘김,
키 오류는 더 묻지 않음."""
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import council_watch as w  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 11, 4, 7, 15, tzinfo=KST)


def lst(*rows):
    return [{"SERVICE": "minutes", "RESULT_CODE": "SUCCESS", "RESULT_MESSAGE": "정상 처리되었습니다.", "TOTAL_COUNT": len(rows), "LIST_COUNT": len(rows),
             "LIST": [{"ROW": r} for r in rows]}]


def row(did, council, date, name="제300회 본회의"):
    return {"DOCID": did, "RASMBLY_ID": "041001", "RASMBLY_NM": council, "RASMBLY_NUMPR": "9", "RASMBLY_SESN": "300", "MINTS_ODR": "2", "MTGNM": name, "MTG_DE": date}


DETAIL = {
    "CLIKC1": {"MTR_SJ": "1. 시정에 관한 질문", "ORGINL_FILE_URL": "",
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
                return R([{"SERVICE": "minutes", "RESULT_CODE": code, "RESULT_MESSAGE": "인증키 오류"}])
            body = lists.get(params["searchKeyword"], lst())
            return R([{**body[0], "LIST": body[0]["LIST"][:params["listCount"]]}])   # 실제 API처럼 listCount건까지만
        if params["docid"] in fail_detail:
            raise type("ReadTimeout", (Exception,), {})("x")
        if params["docid"] not in DETAIL:   # 없는 번호: SUCCESS에 칸만 빔(11-03 탐침 150)
            return R([{"SERVICE": "minutes", "RESULT_CODE": "SUCCESS", "RESULT_MESSAGE": "정상 처리되었습니다."}])
        return R([{"SERVICE": "minutes", "RESULT_CODE": "SUCCESS", "RESULT_MESSAGE": "정상 처리되었습니다.", "DOCID": params["docid"],
                   "RASMBLY_SESN": "300", "MINTS_ODR": "2", **DETAIL[params["docid"]]}])
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
        self.assertEqual(ev[0]["url"], "https://clik.nanet.go.kr/potal/search/searchView.do?collection=minutes&DOCID=CLIKC1")   # 원본 파일 주소가 비면 포털 회의록 화면(탐침 154)

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

    def test_meeting_name_newline_and_empty_detail(self):
        get, _ = fake({})
        doc = w.run(NOW, None, key="k", get=get, sleep=lambda s: None)
        lists = {"현대제철": lst(row("CLIKC2", "충청남도 당진시의회", "20261021", "행정복지위원회\n[임시]"), row("NOPE", "충청남도 당진시의회", "20261021"))}
        for n in (1, 2, 3):
            get2, _ = fake(lists)
            doc = w.run(NOW + dt.timedelta(days=n), doc, key="k", get=get2, sleep=lambda s: None)
            if n < 3:                                               # 본문 빈 회의록 — 다음 실행에 다시
                self.assertNotIn("NOPE", doc["seen"])
                self.assertEqual(doc["tries"]["NOPE"], n)
        self.assertIn("NOPE", doc["seen"])                          # 세 번째에 넘김(오류 칸에 남김)
        self.assertNotIn("tries", doc)
        self.assertIn("상세 NOPE:ValueError(3번째, 넘김)", doc["checks"][0]["error"])
        self.assertEqual(doc["items"][0]["meeting"], "행정복지위원회 [임시]")


    def test_real_minutes_cases_probe_151(self):
        # 부평구의회 10-23: '이전'은 폴리텍대학 본부 이야기 — 한국지엠 앞뒤 60자 밖이면 C
        gm = ("등과 함께 초당적인 협력체계를 마련해야 합니다. 이를 통해 정부의 이전 동향을 면밀히 파악하고 법인본부의 부평 존치를 위한 공동대응에 "
              "나서야 할 것입니다. 둘째, 한국폴리텍대학 법인본부가 부평에 존치해야 하는 당위성을 객관적인 근거로 입증하십시오. 부평국가산업단지와 "
              "한국지엠 부평사업장, 폴리텍대학 인천캠퍼스 등 지역산업과의 연계성을 면밀히 분석하고")
        sn, near = w.hits(gm, dict((c, rx) for _t, c, rx in w.PATTERNS)["한국GM"])
        self.assertEqual((len(sn), near), (1, False))
        # 평택시의회 09-30: 'HL만 도'(띄어 쓴 회의록)와 '만도까지' — 사망사고 바로 곁이라 A
        hl = "얼마 전에 좀 안타까운 소식들이 좀 있었죠? HL만 도에서 끼임 사고로 인해서 노동자가 사망한 사고가 있었고. 최근에 만도까지 포함하면 7건"
        self.assertTrue(w.hits(hl, dict((c, rx) for _t, c, rx in w.PATTERNS)["HL만도"])[1])
        rx_mando = dict((c, rx) for _t, c, rx in w.PATTERNS)["HL만도"]
        self.assertFalse(rx_mando.search("그것만도 아니고 만도시 지원"))      # 조사 '~만도'·지명은 아님
        rx_posco = dict((c, rx) for _t, c, rx in w.PATTERNS)["포스코"]
        self.assertFalse(rx_posco.search("앵커기업은 포스코리튬솔루션, 그다음에 HY케미칼"))   # 계열사는 출입처 아님
        self.assertTrue(rx_posco.search("포스코 광양제철소 3고로"))
        self.assertTrue(w.A_WORDS.search("본사 이전 계획을") and not w.A_WORDS.search("이전에 말씀드린"))

    def test_other_beats_in_same_minutes_and_round_robin(self):
        get, _ = fake({})
        doc = w.run(NOW, None, key="k", get=get, sleep=lambda s: None)
        DETAIL["CLIKM"] = {"MTR_SJ": "시정질문", "MINTS_HTML": "<p>현대자동차 울산공장 견학을 다녀온 학생들의 소감문 발표회가 지난주 시청 대강당에서 성황리에 열렸습니다. 다음으로 넘어가서 질문드리겠습니다. 현대제철 당진제철소 슬래그 불법 야적 문제를 묻겠습니다.</p>"}
        many = {f"CLIKP{i}": {"MTR_SJ": "", "MINTS_HTML": "<p>포스코 봉사</p>"} for i in range(70)}
        DETAIL.update(many)
        try:
            lists = {"현대자동차": lst(row("CLIKM", "울산광역시의회", "20261020")),
                     "포스코": lst(*[row(f"CLIKP{i}", "포항시의회", "20261010") for i in range(70)]),
                     "현대제철": lst(row("CLIKM", "울산광역시의회", "20261020"))}
            get2, calls2 = fake(lists)
            doc2 = w.run(NOW + dt.timedelta(days=1), doc, key="k", get=get2, sleep=lambda s: None)
        finally:
            for k in ["CLIKM", *many]:
                DETAIL.pop(k, None)
        opened = [c["docid"] for c in calls2 if c["displayType"] == "detail"]
        self.assertEqual(len(opened), w.DETAIL_BUDGET)
        self.assertEqual(opened[:2], ["CLIKM", "CLIKP0"])          # 검색어마다 돌아가며 — 포스코 70건이 앞을 다 차지하지 않음
        self.assertEqual(doc2["checks"][0]["pending"], 1 + w.LIST_COUNT - w.DETAIL_BUDGET)   # 목록은 검색어마다 LIST_COUNT건까지
        by = {x["id"]: x for x in doc2["items"]}
        self.assertEqual((by["clik:CLIKM"]["company"], by["clik:CLIKM"]["tier"]), ("현대차", "C"))
        self.assertEqual((by["clik:CLIKM:현대제철"]["company"], by["clik:CLIKM:현대제철"]["tier"]), ("현대제철", "A"))   # 같은 회의록의 다른 출입처
        self.assertEqual([e["id"] for e in doc2["events"]], ["clik:CLIKM:현대제철"])

    def test_probe_153_false_positives_duplicates_and_old_meetings(self):
        rx = dict((c, r) for _t, c, r in w.PATTERNS)
        nexen = "다음은 305페이지, 소토지구 우수유출 저감 사업 설치 건입니다. 유산동과 상북면 소토리의 일원인 넥센타이어 주변 저지대 침수 예방을 위하여"
        self.assertFalse(w.hits(nexen, rx["넥센타이어"])[1])                   # 빗물 '우수유출'은 사건 아님
        hd = "인천세무서에무인민원발급기설치하신것은잘하신것같아요. ○민원지적과장 조항관 맞습니다. 저는여전히현대제철이나유통센터나직원들의편의"
        self.assertFalse(w.hits(hd, rx["현대제철"])[1])                        # 부서 이름·발급기
        dk = "보시면법인동○○○감면된취득세가152억원이잖아요. ○세무과장 김복섭 예,동국제강입니다."
        self.assertTrue(w.hits(dk, rx["동국제강"])[1])
        self.assertTrue(w.hits("현대제철 당진제철소 주민 민원이 계속 들어옵니다", rx["현대제철"])[1])
        get, _ = fake({})
        doc = w.run(NOW, None, key="k", get=get, sleep=lambda s: None)
        body = "<p>세아제강을 저희가 2023년도에 시설보조금을 줬거든요. 그때는 MOU가 안 됐었습니까?</p>"
        DETAIL.update({"CLIKS1": {"MTR_SJ": "", "MINTS_HTML": body}, "CLIKS2": {"MTR_SJ": "", "MINTS_HTML": body},
                       "CLIKOLD": {"MTR_SJ": "", "MINTS_HTML": "<p>동국씨엠 공장 증설 허가 문제</p>"}})
        try:
            lists = {"세아제강": lst(row("CLIKS1", "순천시의회", "20261002"), row("CLIKS2", "순천시의회", "20261002")),
                     "동국씨엠": lst(row("CLIKOLD", "인천광역시 동구의회", "20231123"))}
            doc2 = w.run(NOW + dt.timedelta(days=1), doc, key="k", get=fake(lists)[0], sleep=lambda s: None)
        finally:
            for k in ("CLIKS1", "CLIKS2", "CLIKOLD"):
                DETAIL.pop(k, None)
        by = {x["id"]: x for x in doc2["items"]}
        self.assertEqual(sorted(by), ["clik:CLIKOLD", "clik:CLIKS1"])         # 같은 회의 두 번호는 한 번만
        self.assertEqual(by["clik:CLIKS1"]["tier"], "A")
        self.assertEqual((by["clik:CLIKOLD"]["tier"], by["clik:CLIKOLD"]["old"]), ("C", True))   # 3년 전 회의 — 늦게 공개된 옛 이야기
        self.assertEqual([e["id"] for e in doc2["events"]], ["clik:CLIKS1"])
    def test_widening_the_list_baselines_the_newly_visible_tail(self):
        # 11-04: 목록을 30→60건으로 넓힌다. 이전 실행(listCount 없음 = 30)이 못 보던 31~60번째는 열지 않고 기준선으로만
        prev = {"schema": w.SCHEMA, "baselineAt": "2026-11-03T23:12:00+09:00", "seen": {}, "items": [], "events": []}
        rows = [row(f"CLIKD{i}", "당진시의회", "20261020") for i in range(45)]
        DETAIL.update({f"CLIKD{i}": {"MTR_SJ": "", "MINTS_HTML": "<p>봉사</p>"} for i in range(45)})
        try:
            doc = w.run(NOW, prev, key="k", get=fake({"현대제철": lst(*rows)})[0], sleep=lambda s: None)
        finally:
            for i in range(45):
                DETAIL.pop(f"CLIKD{i}", None)
        self.assertEqual(doc["checks"][0]["returned"], 30)                    # 앞 30건만 새 회의록 후보
        self.assertIn("CLIKD44", doc["seen"])                                # 뒤쪽 15건은 기준선
        self.assertEqual(doc["listCount"], 60)
    def test_plant_region_rule_11_04(self):
        facs = [{"company": "포스코", "rnAdres": "경상북도 포항시 남구 동해안로 6261"}, {"company": "포스코", "rnAdres": "전남광주통합특별시 광양시 폭포사랑길 20-26"},
                {"company": "현대차", "rnAdres": "울산광역시 북구 염포로 700"}, {"company": "현대제철", "rnAdres": "충청남도 당진시 송악읍 북부산업로 1480"}]
        reg = w.regions_from_factories(facs)
        self.assertEqual(w.council_region("경상남도 밀양시의회"), ("c", "밀양"))
        self.assertEqual(w.council_region("경상북도의회"), ("p", "경상북"))
        self.assertEqual(w.council_region("울산광역시 북구의회"), ("c", "울산"))
        self.assertEqual(w.council_region("전남광주통합특별시 순천시의회"), ("c", "순천"))
        self.assertIs(w.in_region(reg, "포스코", "경상남도 밀양시의회"), False)     # 밀양: 포스코 공장 없음
        self.assertIs(w.in_region(reg, "포스코", "경상북도의회"), True)
        self.assertIs(w.in_region(reg, "포스코", "전남광주통합특별시 광양시의회"), True)
        self.assertIs(w.in_region(reg, "현대차", "울산광역시의회"), True)
        self.assertIs(w.in_region(reg, "현대제철", "충청남도 당진시의회"), True)
        self.assertIsNone(w.in_region(reg, "기아", "화성시의회"))                  # 공장 주소 모름 — 규칙 안 씀
        # 실제 대목(밀양시의회 총무위원회 2026-09-14) — 사건 낱말('사고')이 있어도 공장 없는 지역이라 C, 앞서 낸 A 이벤트도 C로
        get, _ = fake({})
        doc = w.run(NOW, None, key="k", get=get, sleep=lambda s: None)
        doc["events"] = [{"id": "clik:OLDA", "tier": "A", "company": "포스코", "council": "경상남도 밀양시의회", "detectedAt": "2026-11-04T08:05:00+09:00"}]
        DETAIL["CLIKMY"] = {"MTR_SJ": "결산", "MINTS_HTML": "<p>그래서 우리가 포스코나 이런 건설 현장에서 여러 가지 일들이 생기면서 포스코 같은 경우 대기업에서는 한 곳에 안전사고가 나면 전체가 다 스톱됩니다.</p>"}
        try:
            doc2 = w.run(NOW + dt.timedelta(days=1), doc, key="k", get=fake({"포스코": lst(row("CLIKMY", "경상남도 밀양시의회", "20261014"))})[0],
                         sleep=lambda s: None, regions=reg)
        finally:
            DETAIL.pop("CLIKMY", None)
        it = {x["id"]: x for x in doc2["items"]}["clik:CLIKMY"]
        self.assertEqual((it["tier"], it["outside"]), ("C", True))
        self.assertEqual([(e["id"], e["tier"]) for e in doc2["events"]], [("clik:OLDA", "C")])

if __name__ == "__main__":
    unittest.main()
