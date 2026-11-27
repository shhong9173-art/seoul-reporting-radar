"""국내 무상수리 공지 ↔ 미국 NHTSA 리콜 대조(free_repair_us.py, 11-22): 차종·연식·부품 낱말, 날짜 꼴, 한도, 실패, 등급."""
import datetime as dt
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import free_repair_us as u  # noqa: E402
import kr_free_repair as f  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 11, 22, 6, 10, tzinfo=KST)


class Resp:
    def __init__(self, data, status=200):
        self.status_code, self._data = status, data
        self.text = json.dumps(data)

    def json(self):
        return self._data


def item(no, title, model, produced, reason, date="2026-11-20", company="현대차"):
    return {"id": f"grts:{no}", "no": no, "title": title, "model": model, "produced": produced, "reason": reason, "date": date,
            "company": company, "detail": "ok"}


# 11-04 기사 꼴: 팰리세이드 ABS — 미국 리콜이 먼저(값은 시험용)
PALISADE = item("4800", "[현대] 팰리세이드 - ABS 모듈 관련 무상수리", "팰리세이드(LX2)", "2019-03-01 ~ 2022-05-31",
                "ABS 모듈 내부 회로 단락으로 화재 발생 가능성이 확인됨에 따른 무상수리", date="2026-11-04")
ROW = {"NHTSACampaignNumber": "25V900000", "ReportReceivedDate": "05/12/2025", "Component": "SERVICE BRAKES, HYDRAULIC:ANTILOCK/TRACTION CONTROL/ELECTRONIC LIMITED SLIP:CONTROL UNIT/MODULE",
       "Summary": "Hyundai Motor America (Hyundai) is recalling certain 2020-2022 Palisade vehicles. The Anti-lock Brake System (ABS) module may short circuit, which can result in an engine compartment fire.",
       "ModelYear": "2020", "Make": "HYUNDAI", "Model": "PALISADE"}
OTHER = {"NHTSACampaignNumber": "24V100000", "ReportReceivedDate": "10/02/2024", "Component": "AIR BAGS", "Summary": "The passenger air bag may not deploy.",
         "ModelYear": "2020", "Make": "HYUNDAI", "Model": "PALISADE"}


class Api:
    def __init__(self, by=None, fail=(), unknown=()):
        self.by, self.fail, self.unknown, self.calls = by or {}, set(fail), set(unknown), []

    def __call__(self, url, headers=None, timeout=None):
        self.calls.append(url)
        assert url.startswith(u.API) and "Mozilla/5.0 seoul-reporting-radar" in headers["User-Agent"]
        key = next((k for k in self.by if k in url), None)
        if any(k in url for k in self.fail):
            return Resp({}, 503)
        if any(k in url for k in self.unknown):
            return Resp({"Message": "Invalid"}, 400)
        return Resp({"Count": 1, "results": self.by.get(key, [])})


class Parts(unittest.TestCase):
    def test_models_years_parts_and_dates(self):
        self.assertEqual(u.us_models({"model": "싼타페 (MX5), 싼타페 하이브리드 (MX5 HEV)", "title": "[현대] 싼타페 등 2차종 - 도어"}), ("HYUNDAI", ["SANTA FE", "SANTA FE HYBRID"]))
        self.assertEqual(u.us_models({"model": "쏘나타 (DT23)"}), ("HYUNDAI", ["SONATA"]))
        self.assertEqual(u.us_models({"model": "G90(RS4)"}), ("GENESIS", ["G90"]))
        self.assertEqual(u.us_models({"model": "코나 일렉트릭(SX2 EV)"}), ("HYUNDAI", ["KONA ELECTRIC", "KONA"]))
        # 11-22 수입·한국GM 차종: 혼다 미국 생산 차종·한국GM 수출 차종·폭스바겐·아우디 일부
        self.assertEqual(u.us_models({"model": "ACCORD Hybrid (어코드 하이브리드)", "title": "[혼다] 어코드 - 에어백 관련 무상수리"}), ("HONDA", ["ACCORD", "ACCORD HYBRID"]))
        self.assertEqual(u.us_models({"model": "CR-V"}), ("HONDA", ["CR-V"]))
        self.assertEqual(u.us_models({"model": "트레일블레이저"}), ("CHEVROLET", ["TRAILBLAZER"]))
        self.assertEqual(u.us_models({"model": "Q4 40 e-tron, Q4 Sportback 40 e-tron"}), ("AUDI", ["Q4 E-TRON"]))
        self.assertEqual(u.us_models({"model": "ID.4 Pro"}), ("VOLKSWAGEN", ["ID.4"]))
        self.assertIsNone(u.us_models({"model": "SCR-VALVE"}))           # CR-V 낱말 경계
        # 다른 브랜드 공지의 낱말로 엉뚱한 차종을 조회하지 않는다(현대차 공지의 '아틀라스' 배터리 → 폭스바겐 ATLAS 아님)
        self.assertIsNone(u.us_models({"model": "그랜저", "title": "[현대] 그랜저 - 아틀라스 배터리 관련 무상수리", "company": "현대차"}))
        self.assertEqual(u.us_models({"model": "ATLAS", "company": "폭스바겐코리아"}), ("VOLKSWAGEN", ["ATLAS"]))
        for domestic in ("K8(GL3) HEV", "타스만(TK)", "스타리아 (US4 PE)", "레이 (TAM)", "쏠라티", "BMW 740 xDrive", "E 300 4MATIC", "KOLEOS (콜레오스)"):   # 미국 판매 이름 없음·차명 다름
            self.assertIsNone(u.us_models({"model": domestic}), domestic)
        self.assertEqual(u.model_years("2026-01-21 ~ 2026-09-04"), [2026, 2027])
        self.assertEqual(u.model_years("2019-03-01 ~ 2022-05-31"), [2019, 2021, 2023])
        self.assertEqual(u.model_years(""), [])
        self.assertEqual([p[0] for p in u.domestic_parts(PALISADE)], ["ABS"])
        # 제목의 부품 이름 + 원인 문장(조치 칸은 안 본다)
        radar = item("4885", "[현대] 쏘나타 - 후측방 레이더 관련 무상수리", "쏘나타 (DT23)", "2026-05-22 ~ 2026-07-29", "후측방레이더 내부 수분유입 가능성")
        radar["action"] = "와이어링 점검"
        self.assertEqual([p[0] for p in u.domestic_parts(radar)], ["레이더"])
        self.assertEqual(u.recall_date("05/12/2025"), "2025-12-05")    # 일/월/연
        self.assertEqual(u.recall_date("2025-12-05T00:00:00"), "2025-12-05")
        self.assertIsNone(u.recall_date("31/31/2025"))
        self.assertEqual(u.recall_url("25V900000"), "https://www.nhtsa.gov/recalls?nhtsaId=25V900")

    def test_only_recalls_with_a_strong_part_word_match(self):
        m = u.match_rows([ROW, OTHER, {**ROW, "ModelYear": "2021"}], u.domestic_parts(PALISADE), "2026-11-04")
        self.assertEqual([(x["campaign"], x["received"], x["years"], x["parts"], x["leadDays"]) for x in m], [("25V900000", "2025-12-05", ["2020", "2021"], ["ABS"], 334)])
        door_only = item("4886", "[현대] 싼타페 등 2차종 - 도어 사이드 관련 무상수리", "싼타페", "2026-01-21 ~ 2026-09-04", "도어 오픈 시 소음")
        self.assertEqual(u.match_rows([{**OTHER, "Component": "LATCHES/LOCKS/LINKAGES:DOORS", "Summary": "The rear door may open."}], u.domestic_parts(door_only)), [])   # 약한 낱말(도어)만


class Link(unittest.TestCase):
    def test_link_fills_us_and_classify_raises_to_a_when_us_recall_came_two_months_earlier(self):
        x = dict(PALISADE)
        api = Api({"model=PALISADE": [ROW, OTHER]})
        check = u.link([x], api, NOW, sleep=lambda s: None)
        self.assertEqual((check["calls"], check["checked"], check["linked"]), (3, 1, 1))
        self.assertEqual(x["us"]["status"], "ok")
        self.assertEqual(x["us"]["matches"][0]["campaign"], "25V900000")
        x["units"] = 900
        x["reason"] = "ABS 모듈 내부 회로 단락 가능성이 확인됨에 따른 무상수리"     # 안전 낱말 없음
        self.assertEqual(f.classify(x), ("A", "미국 같은 차종·부품 낱말 리콜 25V900000이 국내 공지보다 334일 앞(같은 결함인지 미확인)"))
        x["units"] = 92000
        self.assertEqual(f.classify(x)[1], "대상 92,000대(1만 대 이상) · 미국 같은 차종·부품 낱말 리콜 25V900000이 국내 공지보다 334일 앞(같은 결함인지 미확인)")
        # 넓은 낱말(브레이크)만 맞은 대조는 화면에만 — A로 올리지 않는다
        broad = {**x, "units": 900, "us": {"matches": [{**x["us"]["matches"][0], "parts": ["브레이크"]}]}}
        self.assertEqual(f.classify(broad)[0], "B")
        # 다음 실행은 다시 조회하지 않는다
        self.assertEqual(u.link([x], api, NOW, sleep=lambda s: None)["calls"], 0)

    def test_no_model_budget_and_failures(self):
        k8 = item("4874", "[기아] K8 HEV - HPCU 관련 무상수리", "K8(GL3) HEV", "2021-04-23 ~ 2024-08-12", "HPCU 소프트웨어 설계 오류", company="기아")
        other = {**item("4870", "[포르쉐] 카이엔 - 무상수리", "Cayenne", "2024-01-01 ~ 2024-12-31", "x"), "company": None}
        api = Api()
        u.link([k8, other], api, NOW, sleep=lambda s: None)
        self.assertEqual((k8["us"]["status"], "us" in other, api.calls), ("no-model", False, []))   # 국내 전용 차종은 조회 안 함·다른 브랜드는 안 봄
        # 차종 목록 판이 바뀌기 전(판 없음)에 '조회 안 함'으로 적은 공지는 다시 본다 — 11-22 혼다 추가
        accord = {**item("4870", "[혼다] 어코드 - 에어백 관련 무상수리", "ACCORD (어코드)", "2025-03-01 ~ 2025-06-30", "에어백 인플레이터", company="혼다코리아"),
                  "us": {"status": "no-model"}}
        api2 = Api()
        u.link([accord, k8], api2, NOW, sleep=lambda s: None)
        self.assertEqual((accord["us"]["status"], accord["us"]["models"], len(api2.calls)), ("ok", ["ACCORD"], 2))   # 2025·2026년형(끝 해 +1)
        self.assertEqual(u.link([accord, k8], Api(), NOW, sleep=lambda s: None)["calls"], 0)       # 같은 판이면 다시 안 봄
        # 한도: 한 공지(3연식 × 2차종 = 6번)씩, 한도 12면 두 건, 셋째는 다음 실행
        many = [item(str(4900 + i), "[현대] 싼타페 하이브리드 - EGR 관련 무상수리", "싼타페, 싼타페 하이브리드", "2020-01-01 ~ 2023-12-31", "EGR 쿨러 결빙", date=f"2026-11-{10 + i}") for i in range(3)]
        sleeps = []
        check = u.link(many, Api(), NOW, sleep=sleeps.append)
        self.assertEqual((check["calls"], check["checked"], check["waiting"]), (12, 2, 1))
        self.assertEqual(len(sleeps), 11)
        self.assertNotIn("us", many[0])      # 날짜가 가장 이른 글이 남음(새 글부터)
        self.assertEqual(many[2]["us"]["matches"], [])
        # 전부 실패: failed·tries — TRIES번까지 다음 실행이 다시
        y = item("4801", "[현대] 쏘나타 - 레이더 관련 무상수리", "쏘나타", "2026-05-22 ~ 2026-07-29", "레이더 수분")
        for n in range(1, u.TRIES + 1):
            u.link([y], Api(fail=["SONATA"]), NOW, sleep=lambda s: None)
            self.assertEqual((y["us"]["status"], y["us"]["tries"]), ("failed", n))
        self.assertEqual(u.link([y], Api(fail=["SONATA"]), NOW, sleep=lambda s: None)["calls"], 0)
        self.assertEqual(f.classify({**y, "company": "현대차"})[0], "B")   # 실패는 등급에 안 씀


class NewPartWords(unittest.TestCase):
    """11-27: GV60 '운전자 주행·주차 보조 제어기'(4891·4890)·니로 '리어 스프링'(4894)이 부품 낱말 없음으로 대조를 건너뛰었다."""
    ASSIST = item("4891", "[제네시스] GV60 - 운전자 주행 보조 제어기 관련 무상수리", "GV60 (JW PE)", "2025-02-20 ~ 2026-04-03",
                  "운전자 주행 보조 제어기 소프트웨어 오류로 간헐적 원격 시동 시 경고등 점등 가능성이 확인됨에 따른 무상수리", date="2026-11-25")
    PARK = item("4890", "[제네시스] GV60 - 운전자 주차 보조 제어기 관련 무상수리", "GV60 (JW PE)", "2025-02-20 ~ 2026-02-26",
                "운전자 주차 보조 제어기 소프트웨어 오류로 인해 간헐적 주차거리 경고 시스템 점검문구 출력 가능성이 확인됨에 따른 무상수리", date="2026-11-25")
    SPRING = item("4894", "[기아] 니로 - 리어 스프링 관련 무상수리", "니로 (SG2 PE)", "2026-01-16 ~ 2026-07-06",
                  "리어 스프링 형상 불량으로 인해 주행 중 요철 통과 시 차량 뒤쪽 하부 간헐적 이음 발생 가능성이 확인됨에 따른 무상수리", date="2026-11-26", company="기아")

    def test_new_part_words_and_us_side(self):
        self.assertEqual([p[0] for p in u.domestic_parts(self.ASSIST)], ["주행 보조"])
        self.assertEqual([p[0] for p in u.domestic_parts(self.PARK)], ["주차 보조"])
        self.assertEqual([p[0] for p in u.domestic_parts(self.SPRING)], ["스프링"])
        self.assertEqual([p[0] for p in u.domestic_parts(item("1", "[현대] 아반떼 - ADAS제어기 관련 무상수리", "아반떼", "", "x"))], ["주행 보조"])
        self.assertEqual(u.domestic_parts(item("2", "[현대] 아반떼 - 보조 배터리 관련 무상수리", "아반떼", "", "주행 중 경고등"))[0][0], "12V 배터리")   # '주행 … 보조'가 떨어져 있으면 아님
        fca = {**ROW, "NHTSACampaignNumber": "25V500000", "Component": "FORWARD COLLISION AVOIDANCE:AUTOMATIC EMERGENCY BRAKING", "Summary": "The forward collision-avoidance assist may activate unexpectedly."}
        park = {**ROW, "NHTSACampaignNumber": "25V600000", "Component": "ELECTRICAL SYSTEM", "Summary": "The Parking Distance Warning system may fail to warn."}
        brake = {**ROW, "NHTSACampaignNumber": "25V700000", "Component": "PARKING BRAKE", "Summary": "The parking brake may not hold."}
        spring = {**ROW, "NHTSACampaignNumber": "25V800000", "Component": "SUSPENSION:REAR:SPRINGS", "Summary": "The rear coil spring may fracture."}
        belt = {**ROW, "NHTSACampaignNumber": "25V810000", "Component": "SEAT BELTS", "Summary": "The retractor spring may break."}
        self.assertEqual([m["campaign"] for m in u.match_rows([fca, park, brake], u.domestic_parts(self.ASSIST))], ["25V500000"])
        self.assertEqual([m["campaign"] for m in u.match_rows([fca, park, brake], u.domestic_parts(self.PARK))], ["25V600000"])   # 주차 브레이크는 아님
        self.assertEqual([m["campaign"] for m in u.match_rows([spring, belt], u.domestic_parts(self.SPRING))], ["25V800000"])     # 안전벨트 되감기 스프링은 아님
        # '주행 보조'만 맞은 대조는 넓다 — 화면엔 보이되 A로 올리지 않는다
        x = {**self.ASSIST, "units": 425, "us": {"matches": [{"campaign": "25V500000", "leadDays": 200, "parts": ["주행 보조"]}]}}
        self.assertEqual(f.classify(x)[0], "B")
        x["us"]["matches"][0]["parts"] = ["주차 보조"]
        self.assertEqual(f.classify(x)[0], "A")

    def test_notices_skipped_for_no_part_word_are_linked_again_once(self):
        old = {"at": "2026-11-25T16:30:00+09:00", "status": "ok", "make": "GENESIS", "models": ["GV60"], "years": [2025, 2026, 2027], "parts": [], "campaigns": 5, "matches": []}
        a = {**self.PARK, "us": dict(old)}
        still = {**item("4880", "[제네시스] GV60 - 소프트웨어 관련 무상수리", "GV60 (JW PE)", "2025-02-20 ~ 2026-02-26", "경고 문구 출력"), "us": dict(old)}
        park = {**ROW, "NHTSACampaignNumber": "25V600000", "ReportReceivedDate": "01/03/2026", "Component": "ELECTRICAL SYSTEM", "Summary": "The Parking Distance Warning may fail."}
        api = Api({"model=GV60": [park]})
        check = u.link([a, still], api, NOW, sleep=lambda s: None)
        self.assertEqual((check["calls"], check["checked"], check["linked"]), (3, 1, 1))     # 새 판에서도 낱말이 없는 공지는 다시 안 본다
        self.assertEqual((a["us"]["parts"], a["us"]["pv"], [m["campaign"] for m in a["us"]["matches"]]), (["주차 보조"], u.PARTS_VERSION, ["25V600000"]))
        self.assertEqual(still["us"], old)
        self.assertEqual(u.link([a, still], api, NOW, sleep=lambda s: None)["calls"], 0)     # 한 번만


class UnknownYear(unittest.TestCase):
    def test_http_400_is_an_unknown_model_year_not_a_failure(self):
        # 11-22 첫 운영: SANTA FE·SANTA FE HYBRID·SONATA 2027년형이 HTTP 400 — 아직 NHTSA에 없는 연식
        x = item("4886", "[현대] 싼타페 등 2차종 - 도어 사이드 웨더 스트립 관련 무상수리", "싼타페 (MX5), 싼타페 하이브리드 (MX5 HEV)",
                 "2026-01-21 ~ 2026-09-04", "도어 웨더스트립과 차체간 점착 소음 발생 가능성")
        check = u.link([x], Api(unknown=["modelYear=2027"]), NOW, sleep=lambda s: None)
        self.assertEqual((check["calls"], check["failed"]), (4, 0))
        self.assertEqual((x["us"]["status"], x["us"]["unknown"], "error" in x["us"]), ("ok", ["SANTA FE 2027", "SANTA FE HYBRID 2027"], False))
        # 첫 운영 저장분(400을 실패로 적은 것)은 한 번 고쳐 두고 다시 조회하지 않는다
        old = {**x, "us": {"status": "partial", "error": "SANTA FE 2027 HTTP 400; SANTA FE HYBRID 2027 HTTP 400", "tries": 1, "matches": []}}
        api = Api()
        u.link([old], api, NOW, sleep=lambda s: None)
        self.assertEqual((old["us"]["status"], old["us"]["unknown"], "tries" in old["us"], api.calls), ("ok", ["SANTA FE 2027", "SANTA FE HYBRID 2027"], False, []))
        # 다른 오류가 섞이면 그대로 둔다
        mixed = {**x, "us": {"status": "partial", "error": "SANTA FE 2026 HTTP 503; SANTA FE 2027 HTTP 400", "tries": 1}}
        u.link([mixed], Api(), NOW, sleep=lambda s: None)
        self.assertEqual(mixed["us"]["status"], "partial")


class Tsbs(unittest.TestCase):
    def test_service_campaigns_with_same_model_year_and_part_are_kept(self):
        # us-recalls 저장소의 제조사 통신 꼴(nhtsa_tsbs.py): models [{model, years}], components, summary, mfrDate
        x = item("4885", "[현대] 쏘나타 - 후측방 레이더 관련 무상수리", "쏘나타 (DT23)", "2026-05-22 ~ 2026-07-29", "후측방레이더 내부 수분유입 가능성")
        camp = {"id": "LB01", "campaign": "LB01", "doc": "26-01-070H TSB", "kindName": "보증 프로그램·캠페인", "mfrDate": "2026-08-10", "added": "2026-08-20",
                "models": [{"model": "SONATA", "years": ["2026"]}, {"model": "ELANTRA", "years": ["2026"]}], "components": ["BACK OVER PREVENTION"],
                "summary": "Certain 2026MY Sonata vehicles may exhibit a blind spot radar warning due to water intrusion into the rear corner radar.", "url": "https://static.nhtsa.gov/odi/tsbs/2026/MC-1.pdf"}
        other_year = {**camp, "campaign": "LB02", "models": [{"model": "SONATA", "years": ["2020"]}]}
        other_part = {**camp, "campaign": "LB03", "summary": "Fuel filler door may be difficult to open."}
        other_model = {**camp, "campaign": "LB04", "models": [{"model": "TUCSON", "years": ["2026"]}]}
        self.assertEqual(u.link_tsbs([x], [camp, other_year, other_part, other_model]), 1)
        self.assertEqual([(m["key"], m["models"], m["years"], m["parts"], m["leadDays"], m["date"]) for m in x["usTsb"]], [("LB01", ["SONATA"], ["2026"], ["레이더"], 102, "2026-08-10")])
        # 통신이 보관 기간(120일)을 넘겨 저장소에서 빠져도 맞은 기록은 남는다
        self.assertEqual(u.link_tsbs([x], []), 1)
        self.assertEqual(x["usTsb"][0]["key"], "LB01")
        # 미국 판매 이름 없는 차종·다른 브랜드는 안 본다
        k8 = item("4874", "[기아] K8 HEV - HPCU 관련 무상수리", "K8(GL3) HEV", "2021-04-23 ~ 2024-08-12", "HPCU 소프트웨어 설계 오류", company="기아")
        self.assertEqual(u.link_tsbs([k8, {**x, "company": None, "usTsb": None}], [camp]), 0)
        self.assertNotIn("usTsb", k8)
        self.assertEqual(f.classify({**x, "units": 886})[0], "B")     # 제조사 통신은 등급을 올리지 않는다(11-09 기자: 美 캠페인 유형 약함)


if __name__ == "__main__":
    unittest.main()
