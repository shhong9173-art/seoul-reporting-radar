"""Automatic prior-capture check of competitor exclusives: same group company first seen before publication + event overlap."""
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import reverse_prior_capture as r  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 10, 28, 19, 20, tzinfo=KST)
# Real titles from digests/reverse_trace_latest.json (10-28).
TRACE = {"generatedAt": "2026-10-28T15:23:05+09:00", "items": [
    {"articleId": "a1", "title": "[단독] LS일렉트릭, 미국 전기차 충전 특허 거절에 불복…연방항소법원 항소 - 뉴스저널리즘", "published": "2026-10-26T08:00:00+09:00",
     "sourceName": "뉴스저널리즘", "companies": ["LS일렉트릭"], "kind": "회생·소송"},
    {"articleId": "a2", "title": "[단독] 포스코, 미국 상계관세 소송서 패소…탄소배출권 무상할당 보조금 인정 - 뉴스저널리즘", "published": "2026-10-28T10:50:00+09:00",
     "sourceName": "뉴스저널리즘", "companies": ["포스코"], "kind": "통상·관세"},
    {"articleId": "a3", "title": "[단독] '中 홀로서기' 속도 내는 현대차…BAIC, 합작 금융사 지분 전량 정리 '대수술'", "published": "2026-10-22T07:00:00+09:00",
     "sourceName": "X", "companies": ["현대차"], "kind": "자본·지배구조"},
    {"articleId": "a4", "title": "[단독] LG그룹, 현대차 로봇사업 수장 품었다", "published": "2026-10-23T09:00:00+09:00", "sourceName": "Y", "companies": ["현대차"], "kind": "노사·인사"},
    {"articleId": "a5", "title": "[단독] 천보 \"美·中에 차세대 배터리 전해액 수출\"", "published": "2026-10-19T09:00:00+09:00", "sourceName": "Z", "companies": ["천보"]},
    {"articleId": "old", "title": "[단독] 오래된 기사", "published": "2026-08-01T09:00:00+09:00", "companies": ["현대차"]},
]}
DOCS = {
    "us-litigation": {"cases": [
        {"id": "cl:75019340", "beat": ["LS일렉트릭"], "caseName": "In re: LS Electric Co., Ltd.", "category": "연방순회항소법원",
         "summary": "LS일렉트릭, 미국 특허청 특허심판원(PTAB) 결정에 불복해 연방순회항소법원에 항소", "firstSeen": "2026-10-24T07:50:00+09:00", "url": "https://cl/1"},
        {"id": "cl:74869986", "beat": ["포스코"], "caseName": "POSCO v. United States", "category": "국제무역법원(무역구제 소송)",
         "summary": "포스코, 미국 정부를 상대로 국제무역법원에 소송 제기", "firstSeen": "2026-10-01T07:50:00+09:00"}],
        "opinions": [{"id": "op:1", "beat": ["포스코"], "caseName": "POSCO v. United States", "holding": "Sustaining the Department of Commerce's ...",
                      "firstSeen": "2026-10-28T14:55:00+09:00"}]},  # after the article: does not count
    "partner-filings": {"items": [{"id": "hkex:01958:1", "beat": ["현대차"], "filer": "BAIC Motor (01958)",
                                   "title": "MAJOR TRANSACTION - EXIT OF BAIC INVESTMENT FROM ITS INVESTMENT IN BHAF", "date": "2026-10-21", "firstSeen": "2026-10-21T19:40:00+09:00"}]},
    "page-watch": {"events": [{"pageId": "hyundai-us", "company": "현대차", "label": "현대차 미국 차종", "added": {"timing": ["Coming 2027"]}, "detectedAt": "2026-10-20T06:30:00+09:00"}]},
}
CLUES = {"items": [{"id": "c1", "companies": ["현대자동차"], "title": "현대자동차 · 주주총회소집공고", "published": "2026-10-15"}]}


class Capture(unittest.TestCase):
    def test_verdicts_and_lead_time(self):
        doc = r.run(TRACE, DOCS, CLUES, now=NOW)
        by = {x["articleId"]: x for x in doc["articles"]}
        self.assertNotIn("old", by)  # outside the 30-day window
        ls = by["a1"]
        self.assertEqual((ls["verdict"], ls["best"]["source"], ls["best"]["leadHours"]), ("먼저 잡은 후보", "us-litigation", 48.2))
        self.assertIn("소송·판결", ls["best"]["why"])
        self.assertIn("특허·상표", ls["best"]["why"])
        posco = by["a2"]
        # 패소(판결) 기사: 기사 뒤에 본 판결은 빼고, 먼저 본 것은 다른 사건번호일 수 있는 소송 접수뿐 → 같은 회사 항목만
        self.assertEqual((posco["verdict"], posco["best"]["id"]), ("같은 회사 항목만", "cl:74869986"))
        baic = by["a3"]
        self.assertEqual((baic["verdict"], baic["best"]["label"]), ("먼저 잡은 후보", "해외 파트너 공시"))
        self.assertIn("지분·합작·거래", baic["best"]["why"])
        robot = by["a4"]
        self.assertEqual(robot["verdict"], "같은 회사 항목만")  # 현대차 items exist but nothing about a hire
        self.assertEqual(robot["best"]["why"], [])
        self.assertEqual(by["a5"]["verdict"], "없음")
        self.assertEqual(doc["counts"], {"먼저 잡은 후보": 2, "같은 회사 항목만": 2, "없음": 1, "회사 미상": 0})
        self.assertEqual(doc["bySource"]["미국 소송·판결"]["caught"], 1)
        self.assertEqual(doc["bySource"]["해외 파트너 공시"]["leadHours"] if "leadHours" in doc["bySource"]["해외 파트너 공시"] else
                         doc["bySource"]["해외 파트너 공시"]["leadHoursMedian"], 11.3)

    def test_one_feed_with_an_unexpected_shape_does_not_stop_the_others(self):
        bad = {**DOCS, "kr-signals": {"decisions": [{"id": "d1", "mentions": ["포스코"], "name": "x", "fileDate": "2026-10-01"}]},
               "page-watch": {"events": [{"pageId": "p", "company": ["not", "a", "string"], "added": ["Coming 2027"], "detectedAt": "2026-10-20T06:30:00+09:00"}]}}
        doc = r.run(TRACE, bad, CLUES, now=NOW)
        self.assertEqual(doc["adapterErrors"], {"kr-signals": "AttributeError"})
        self.assertEqual(doc["counts"]["먼저 잡은 후보"], 2)  # litigation and partner filings still read

    def test_group_names_and_missing_times(self):
        self.assertEqual(r.canon("포스코홀딩스"), "포스코")
        self.assertEqual(r.canon("효성중공업(관련)"), "효성중공업")
        self.assertIsNone(r.mem("x", "1", ["현대차"], "t", None))
        self.assertIsNone(r.mem("x", "1", [], "t", "2026-10-01"))
        self.assertEqual(r.parse_time("20261021").isoformat(), "2026-10-21T00:00:00+09:00")


    def test_feed_with_no_stored_result_is_named_separately_from_failures(self):
        import io
        import os
        from contextlib import redirect_stdout
        from unittest.mock import patch
        import private_store
        sent = {}

        def fake_get(name, token, **_):
            if name == "trademarks":
                return None  # 204: 아직 저장된 결과 없음
            if name == "kr-signals":
                raise private_store.StoreError("private store GET HTTP 500")
            return {}

        def fake_put(name, doc, token, **_):
            sent["doc"] = doc
            return 200
        buf = io.StringIO()
        with patch.object(private_store, "get", fake_get), patch.object(private_store, "put", fake_put), \
                patch.dict(os.environ, {"MCP_ACCESS_TOKEN": "x" * 20}), redirect_stdout(buf):
            r.main()
        self.assertEqual(sent["doc"]["feedsEmpty"], ["trademarks"])
        self.assertEqual(sent["doc"]["feedsFailed"], ["kr-signals:StoreError"])
        self.assertIn("저장 결과 없음 ['trademarks']", buf.getvalue())
        self.assertIn("감시 읽음 19/21", buf.getvalue())


    def test_plant_permit_before_the_article(self):
        trace = {"generatedAt": "2026-11-20T15:00:00+09:00", "items": [
            {"articleId": "b1", "title": "[단독] LS전선, 구미에 희토류 영구자석 공장 증설", "published": "2026-11-18T08:00:00+09:00",
             "sourceName": "X", "companies": ["LS전선"]}]}
        docs = {"kr-building": {"permits": [
            {"id": "bld:1", "company": "LS전선", "companies": ["LS전선"], "archGbCdNm": "신축", "mainPurpsCdNm": "공장", "plot": "경상북도 구미시 공단동 1",
             "tier": "A", "firstSeen": "2026-11-02T07:45:00+09:00", "permitted": "2026-10-20"},
            {"id": "bld:2", "company": "LS전선", "companies": ["LS전선"], "archGbCdNm": "증축", "tier": "C", "firstSeen": "2026-11-02T07:45:00+09:00"}]}}
        doc = r.run(trace, docs, {"items": []}, now=dt.datetime(2026, 11, 20, 19, 20, tzinfo=r.KST))
        a = doc["articles"][0]
        self.assertEqual(a["verdict"], "먼저 잡은 후보")
        self.assertEqual((a["best"]["label"], a["best"]["id"]), ("공장 부지 건축허가", "bld:1"))

    def test_new_car_filing_before_the_article(self):
        trace = {"generatedAt": "2026-10-28T15:00:00+09:00", "items": [
            {"articleId": "n1", "title": "[단독] 현대차, 아반떼 N 2027년형 투입…연비 인증 마쳐", "published": "2026-10-23T08:00:00+09:00",
             "sourceName": "X", "companies": ["현대차"]}]}
        docs = {"kr-fuel": {"vehicles": [{"id": "kf:1", "company": "현대차", "maker": "현대자동차(주)", "model": "아반떼 N 2.0 터보", "year": "2027",
                                           "fuel": "휘발유", "kind": "새 모델명", "firstSeen": "2026-10-21T06:10:00+09:00"}]}}
        doc = r.run(trace, docs, {"items": []}, now=NOW)
        a = doc["articles"][0]
        self.assertEqual(a["verdict"], "먼저 잡은 후보")
        self.assertEqual(a["best"]["label"], "국내 연비 신고")


    def test_epa_rule_docket_is_not_a_new_car_capture(self):
        # 10-30 운영: 신차 낱말 하나로 EPA 규제 의견서와 묶인 오탐(실제 제목·의견서 이름)
        trace = {"generatedAt": "2026-10-30T12:55:00+09:00", "items": [
            {"articleId": "c4", "title": "[단독]현대차 미래항공·새만금 사업 가속..신차로 본업 경쟁력↑ - 머니투데이", "published": "2026-10-29T18:10:00+09:00",
             "sourceName": "머니투데이", "companies": ["현대차"]}]}
        docs = {"us-comments": {"items": [{"id": "EPA-HQ-OAR-2025-3297-0160", "company": "현대차", "agency": "EPA",
                                           "docketTitle": "Revision of Tier 4 Phase-in Schedule for Light-Duty and Medium-Duty Vehicles",
                                           "firstSeen": "2026-10-26T21:04:00+09:00"}]},
                "us-epa": {"vehicles": [{"id": "epa:1", "company": "현대차", "kind": "새 모델", "year": "2027", "make": "Hyundai", "model": "IONIQ 6 N",
                                         "range": 250, "firstSeen": "2026-10-20T06:20:00+09:00"}]}}
        doc = r.run(trace, docs, {"items": []}, now=dt.datetime(2026, 10, 30, 13, 0, tzinfo=r.KST))
        a = doc["articles"][0]
        self.assertEqual(a["verdict"], "같은 회사 항목만")
        # 차량 항목은 여전히 신차 낱말로 묶인다(EPA 연비 인증 새 모델)
        trace["items"][0]["title"] = "[단독] 현대차, 아이오닉 6 N 美 출시 임박…EPA 인증 마쳐"
        trace["items"][0]["articleId"] = "c5"
        b = r.run(trace, docs, {"items": []}, now=dt.datetime(2026, 10, 30, 13, 0, tzinfo=r.KST))["articles"][0]
        self.assertEqual((b["verdict"], b["best"]["id"]), ("먼저 잡은 후보", "epa:1"))

    def test_one_generic_word_is_not_enough_and_duplicates_count_once(self):
        # 10-28 첫 운영 실행의 오탐 2건(실제 제목): '배터리'·'공장'만 겹침
        trace = {"generatedAt": "2026-10-28T15:00:00+09:00", "items": [
            {"articleId": "m1", "title": "[단독] 폭스바겐 멈춘 배터리 불량…현대모비스 스페인 수장 교체", "published": "2026-10-28T11:24:00+09:00", "companies": ["현대모비스"]},
            {"articleId": "h1", "title": "[단독] '회장 4년차' 이재용, 사장단과 현대차 美공장 방문", "published": "2026-10-27T09:00:00+09:00", "companies": ["현대차"]},
            {"articleId": "h2", "title": "[단독] '회장 4년차' 이재용, 사장단과 현대차 美공장 방문", "published": "2026-10-27T09:00:00+09:00", "companies": ["현대차"]}]}
        docs = {"kr-official": {"factories": [
            {"id": "fac:312002020516159", "company": "현대모비스", "registeredOn": "2026-10-20", "cmpnyNm": "(주)현대모비스", "mainProductCn": "배터리 모듈/팩", "firstSeen": "2026-10-26T22:18:00+09:00"},
            {"id": "fac:442002005098935", "company": "현대차", "registeredOn": "2026-10-20", "cmpnyNm": "(주)현대자동차 충청써비스", "mainProductCn": "건설장비 수리", "firstSeen": "2026-10-26T22:18:00+09:00"}]}}
        doc = r.run(trace, docs, {"items": []}, now=NOW)
        self.assertEqual(len(doc["articles"]), 2)
        self.assertEqual({a["articleId"]: a["verdict"] for a in doc["articles"]}, {"m1": "같은 회사 항목만", "h1": "같은 회사 항목만"})


    def test_quotation_subsidiary_and_schedule_a_trademark_suits_are_not_captures(self):
        # 10-31 운영 오탐 2건(실제 제목·항목 이름)
        trace = {"generatedAt": "2026-10-31T01:43:00+09:00", "items": [
            {"articleId": "t1", "title": "[단독] 현대차, 인도서 부품 관세 분쟁 대법원행…세관, 판정 불복 - 뉴스저널리즘", "published": "2026-10-30T16:31:00+09:00",
             "sourceName": "뉴스저널리즘", "companies": ["현대차"]},
            {"articleId": "t2", "title": "[단독] 현대차·기아 ‘E-pit’ 상표권 현대엔지니어링에 넘긴다…12월1일 충전사업 운영 일원화 - 쿠키뉴스", "published": "2026-10-30T17:28:00+09:00",
             "sourceName": "쿠키뉴스", "companies": ["현대차"]}]}
        docs = {"partner-filings": {"items": [
            {"id": "asx:ARU:2026-10-27:Application for quotation of securities - ARU", "beat": ["현대차", "기아"], "filer": "Arafura Rare Earths (ARU)",
             "title": "Application for quotation of securities - ARU", "date": "2026-10-27", "firstSeen": "2026-10-28T02:00:00+09:00"},
            {"id": "edgar:x", "beat": ["현대차"], "filer": "X", "title": "Hyundai Motor America, a subsidiary of Hyundai Motor Company", "date": "2026-10-27",
             "firstSeen": "2026-10-28T02:00:00+09:00"}]},
            "us-litigation": {"cases": [{"id": "cl:75032648", "beat": ["현대차"], "category": "지식재산(상표)",
                                         "caseName": "Hyundai Motor Company v. The Partnerships and Unincorporated Associations Identified on Schedule A",
                                         "summary": "trademark counterfeiting", "firstSeen": "2026-10-29T07:51:00+09:00"}]}}
        doc = r.run(trace, docs, {"items": []}, now=dt.datetime(2026, 10, 31, 1, 43, tzinfo=r.KST))
        self.assertEqual({a["articleId"]: a["verdict"] for a in doc["articles"]}, {"t1": "같은 회사 항목만", "t2": "같은 회사 항목만"})
        # 진짜 쿼터·보조금·상표명 낱말은 여전히 잡는다
        rx = dict((n, x) for n, _, x in r.CONCEPTS)["관세·무역구제"]
        import re as _re
        self.assertTrue(all(_re.search(rx, t, _re.I) for t in ["steel safeguard quotas", "countervailable subsidy", "duties on imports"]))
        self.assertFalse(any(_re.search(rx, t, _re.I) for t in ["Application for quotation of securities", "a subsidiary of Hyundai"]))

    def test_ruling_article_counts_a_ruling_seen_before_it(self):
        docs = {"us-litigation": {"cases": [], "opinions": [{"id": "op:1", "beat": ["포스코"], "caseName": "POSCO v. United States",
                "holding": "Sustaining the Department of Commerce's second remand redetermination", "firstSeen": "2026-10-28T07:50:00+09:00"}]}}
        trace = {"items": [TRACE["items"][1]]}
        a = r.run(trace, docs, {"items": []}, now=NOW)["articles"][0]
        self.assertEqual((a["verdict"], a["best"]["id"]), ("먼저 잡은 후보", "op:1"))


if __name__ == "__main__":
    unittest.main()


class GroupsAndSuppliers(unittest.TestCase):
    def test_audi_recall_with_sk_battery_counts_for_a_vw_sk_on_article(self):
        # 10-26 '[단독] 아우디, 미국서 Q4 e-트론 9048대 리콜…SK온 배터리 화재 우려'(회사 분류: SK온·폭스바겐)와 NHTSA 26V698000(접수 10-21).
        # 가정: 레이더가 기사 전에 이 리콜을 봤다면(firstSeen은 가상 — 실제 감시는 10-28에 생겨 운영 판정 '없음'이 맞다) 회사가 이어져야 한다.
        trace = {"items": [{"articleId": "audi", "title": "[단독] 아우디, 미국서 Q4 e-트론 9048대 리콜…SK온 배터리 화재 우려 - 한국신용신문",
                            "published": "2026-10-26T10:17:00+09:00", "sourceName": "한국신용신문", "companies": ["SK온", "폭스바겐"]}]}
        docs = {"us-recalls": {"recalls": [{"id": "26V698000", "why": [{"name": "AUDI", "beat": "아우디"}], "models": "Q4 E-TRON",
                                            "component": "ELECTRICAL SYSTEM:PROPULSION SYSTEM:TRACTION BATTERY",
                                            "defect": "The high voltage battery may fail and cause a fire.", "supplierBox": "SK Battery Manufacturing Kft. (Hungary)",
                                            "firstSeen": "2026-10-21T17:10:00+09:00", "url": "https://www.nhtsa.gov/recalls?nhtsaId=26V698"}]}}
        doc = r.run(trace, docs, {}, now=NOW)
        row = doc["articles"][0]
        self.assertEqual(row["verdict"], "먼저 잡은 후보")
        self.assertEqual(row["best"]["id"], "26V698000")
        self.assertGreater(row["best"]["leadHours"], 100)
        self.assertEqual(r.suppliers_in("SK On Co., Ltd.", "LG Energy Solution Michigan"), ["SK온", "LG에너지솔루션"])
        self.assertEqual(r.canon("아우디코리아"), "폭스바겐")
