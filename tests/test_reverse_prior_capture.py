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

    def test_clue_label_names_its_real_origin(self):
        # 11-03 역추적: 미국 관보 상계관세 문서가 '공개 원자료 단서(DART 등)'로 보였다
        m = r.mem("clues", "x", ["현대제철"], "Certain Hot-Rolled Steel ... Final Results", "2026-11-01T00:43:00+09:00", origin="미 연방관보")
        self.assertEqual(r.label_of(m), "공개 원자료 단서(미 연방관보)")
        self.assertEqual(r.label_of(r.mem("clues", "y", ["현대제철"], "t", "2026-11-01")), "공개 원자료 단서(DART 등)")
        self.assertEqual(r.label_of(r.mem("kr-stacks", "z", ["포스코"], "t", "2026-11-01")), "굴뚝 측정(가동 신호)")
        self.assertEqual(r.label_of(r.mem("clues", "o", ["현대제철"], "t", "2026-11-01", origin="OVERSEAS")), "공개 원자료 단서(해외 원자료)")

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
        self.assertIn("감시 읽음 27/29", buf.getvalue())   # 11-03: 새 감시 7개, 11-04: 지분·자사주 변동


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

    def test_stack_emission_value_is_not_a_plant_expansion_but_matches_an_emission_story(self):
        # 11-02: '[단독] 포스코 포항 2열연, 가열로 한 기 더'가 포항제철소 질소산화물 초과 측정값과 '공장·생산·포항'으로 묶였다
        stacks = {"kr-stacks": {"events": [
            {"id": "stk:exceed2:포스코:x:228:nox", "kind": "배출허용기준 초과 지속", "company": "포스코", "detectedAt": "2026-11-01T17:18:00+09:00",
             "tier": "A", "text": "㈜포스코 포항제철소 배출구 228번 질소산화물 측정값 152.71이 배출허용기준 140을 넘음"},
            {"id": "stk:exceed:롯데케미칼:y:916:nox", "kind": "배출허용기준 초과(측정값)", "company": "롯데케미칼", "detectedAt": "2026-11-01T16:00:00+09:00",
             "tier": "B", "text": "롯데케미칼㈜ 여수1공장 배출구 916번 질소산화물 측정값 69.95이 배출허용기준 63.8을 넘음"},
            # 같은 날 C '배출구 목록에서 빠짐 — 이후 다시 나타남'(일시적 누락)은 사건으로 세지 않는다
            {"id": "stk:gone:포스코:x:135:2026-11-01", "kind": "배출구 목록에서 빠짐", "company": "포스코", "detectedAt": "2026-11-01T04:22:00+09:00", "tier": "C",
             "text": "㈜포스코 포항제철소 배출구 135번이 굴뚝 자동측정 목록에서 2번 연속 빠짐 — 이후 다시 나타남(측정 2026-11-01 08:00, 일시적 누락)"},
            {"id": "stk:stop:포스코:x:2026-10-31", "kind": "배출구 멈춤 신호", "company": "포스코", "detectedAt": "2026-10-31T09:17:00+09:00", "tier": "B",
             "text": "㈜포스코 포항제철소: 배출구 3개가 3번 연속 평소의 10% 아래 — 다시 측정 중", "_note": "다시 나타남 없음"}]}}
        trace = {"generatedAt": "2026-11-02T10:46:00+09:00", "items": [
            {"articleId": "s1", "title": "[단독] 포스코 포항 2열연, 가열로 한 기 더…연산 500만 톤 생산체계 다진다", "published": "2026-11-02T05:00:00+09:00",
             "sourceName": "철강금속신문", "companies": ["포스코"]},
            {"articleId": "s2", "title": "[단독] 롯데케미칼 여수1공장 질소산화물 배출 기준 넘겨", "published": "2026-11-02T06:00:00+09:00",
             "sourceName": "X", "companies": ["롯데케미칼"]},
            {"articleId": "s3", "title": "[단독] 롯데케미칼 여수1공장 증설 착수", "published": "2026-11-02T07:00:00+09:00",
             "sourceName": "Y", "companies": ["롯데케미칼"]}]}
        doc = r.run(trace, stacks, {"items": []}, now=dt.datetime(2026, 11, 2, 11, 0, tzinfo=r.KST))
        by = {a["articleId"]: a for a in doc["articles"]}
        # 11-08: 약한 개념('생산')과 지명('포항')만 겹친 멈춤 신호는 가열로 증설 기사와 같은 사건 근거가 못 된다 → 같은 회사 항목만
        self.assertEqual(by["s1"]["verdict"], "같은 회사 항목만")
        stacks["kr-stacks"]["events"] = [e for e in stacks["kr-stacks"]["events"] if e["id"] != "stk:stop:포스코:x:2026-10-31"]
        doc = r.run(trace, stacks, {"items": []}, now=dt.datetime(2026, 11, 2, 11, 0, tzinfo=r.KST))
        by = {a["articleId"]: a for a in doc["articles"]}
        self.assertEqual(by["s1"]["verdict"], "같은 회사 항목만")   # C 일시적 누락·배출 초과만 남으면 묶지 않는다
        self.assertEqual(by["s2"]["verdict"], "먼저 잡은 후보")
        self.assertIn("대기 배출", by["s2"]["best"]["why"])
        self.assertEqual(by["s3"]["verdict"], "같은 회사 항목만")   # 사업장 이름의 '공장'은 증설 기사와 묶지 않는다

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
            "us-comments": {"items": [{"id": "EPA-HQ-OAR-2025-3297-0160", "company": "현대차", "agency": "EPA",
                                       "docketTitle": "Revision of Tier 4 Phase-in Schedule for Light-Duty and Medium-Duty Vehicles",
                                       "firstSeen": "2026-10-26T21:04:00+09:00"}]},
            "us-litigation": {"cases": [{"id": "cl:75032648", "beat": ["현대차"], "category": "지식재산(상표)",
                                         "caseName": "Hyundai Motor Company v. The Partnerships and Unincorporated Associations Identified on Schedule A",
                                         "summary": "trademark counterfeiting", "firstSeen": "2026-10-29T07:51:00+09:00"}]}}
        doc = r.run(trace, docs, {"items": []}, now=dt.datetime(2026, 10, 31, 1, 43, tzinfo=r.KST))
        self.assertEqual({a["articleId"]: a["verdict"] for a in doc["articles"]}, {"t1": "같은 회사 항목만", "t2": "같은 회사 항목만"})
        # 진짜 쿼터·보조금·상표명 낱말은 여전히 잡는다
        rx = dict((n, x) for n, _, x in r.CONCEPTS)["관세·무역구제"]
        import re as _re
        self.assertTrue(all(_re.search(rx, t, _re.I) for t in ["steel safeguard quotas", "countervailable subsidy", "duties on imports"]))
        self.assertFalse(any(_re.search(rx, t, _re.I) for t in ["Application for quotation of securities", "a subsidiary of Hyundai",
                                                                 "Light-Duty and Medium-Duty Vehicles", "heavy duty trucks", "duty-free shop"]))
        self.assertTrue(_re.search(rx, "Countervailing Duty Administrative Review", _re.I))

    def test_ruling_article_counts_a_ruling_seen_before_it(self):
        docs = {"us-litigation": {"cases": [], "opinions": [{"id": "op:1", "beat": ["포스코"], "caseName": "POSCO v. United States",
                "holding": "Sustaining the Department of Commerce's second remand redetermination", "firstSeen": "2026-10-28T07:50:00+09:00"}]}}
        trace = {"items": [TRACE["items"][1]]}
        a = r.run(trace, docs, {"items": []}, now=NOW)["articles"][0]
        self.assertEqual((a["verdict"], a["best"]["id"]), ("먼저 잡은 후보", "op:1"))


    def test_concept_only_long_filings_are_not_captures_but_bilingual_products_are(self):
        # 11-08: 30일 '먼저' 11건 중 엉뚱한 연결 — 개념 하나만 겹친 긴 영문 공시·다른 소송. 한·영 품목(강관↔pipe)·쟁점(탄소배출권↔KAU)은 센다
        items = [r.mem("partner-filings", "edgar:aptv", ["현대차"], "Aptiv PLC (APTV) 10-Q equity method goodwill investment", "2026-11-04T07:00:00+09:00"),
                 r.mem("partner-filings", "edgar:vrsk", ["현대차"], "Verisk Analytics 10-Q District Courts lawsuit", "2026-11-06T07:00:00+09:00"),
                 r.mem("us-litigation", "cl:posco", ["포스코"], "POSCO v. United States 포스코, 미국 정부를 상대로 국제무역법원에 소송 제기", "2026-11-03T07:50:00+09:00"),
                 r.mem("trade-remedy", "fr:pipe", ["현대제철"], "Circular Welded Non-Alloy Steel Pipe From the Republic of Korea: Final Results of Antidumping Duty duty",
                       "2026-11-05T00:00:00+09:00"),
                 r.mem("trade-remedy", "fr:hr", ["포스코"], "Certain Hot-Rolled Steel Flat Products: Final Results of Countervailing Duty duty Comment 5: Whether the Provision of KAUs Confers a Countervailable Benefit",
                       "2026-10-26T21:32:00+09:00")]
        v = lambda title, comp, when: r.match({"title": title, "companies": [comp], "published": when}, items)[0]  # noqa: E731
        self.assertEqual(v("[단독] 제네시스PE, GS건설 지분 전량 노린다", "제네시스", "2026-11-06T11:04:00+09:00"), "회사 미상")
        self.assertEqual(v("[단독] 교섭 의제 제한 안 둔 중노위…현대차, 다음주 불복 소송 가닥", "현대차", "2026-11-06T09:36:00+09:00"), "같은 회사 항목만")
        self.assertEqual(v("[단독] 포스코인터, 러시아서 '떼인 돈' 받는다…현지 법원 '강제집행 승인'", "포스코", "2026-11-05T10:21:00+09:00"), "같은 회사 항목만")
        self.assertEqual(v("[단독] 美, 현대제철 강관 반덤핑 4.20% 확정…휴스틸은 0%", "현대제철", "2026-11-05T08:35:00+09:00"), "먼저 잡은 후보")
        self.assertEqual(v("[단독] 포스코, 미국 상계관세 소송서 패소…탄소배출권 무상할당 보조금 인정", "포스코", "2026-10-28T10:50:00+09:00"), "먼저 잡은 후보")


    def test_product_words_inside_company_names_are_not_event_words(self):
        # 11-09: 'LS전선'의 전선 ↔ 'LS Cable & System Ltd.'의 cable, 자회사 설립 ↔ Ltd.로 노동위 재심 사건이 '먼저'가 됐다
        items = [r.mem("kr-labor", "labor:00:2026부노46", ["LS전선"], "노동위 심판 회의 중앙노동위원회 사건 2026부노46 「엘에스전선 주식회사(LS Cable & System Ltd.) 부당노동행위 구제 재심신청」",
                       "2026-11-04T10:28:00+09:00"),
                 r.mem("us-litigation", "cl:kumho", ["금호타이어"], "Kumho Tire U.S.A., Inc. employment complaint", "2026-11-02T09:00:00+09:00"),
                 r.mem("overseas-registry", "ch:ls", ["LS전선"], "영국 법인 설립 Companies House LS SUBSEA CABLES UK LIMITED", "2026-11-01T09:00:00+09:00")]
        v = lambda title, comp, when: r.match({"title": title, "companies": [comp], "published": when}, items)  # noqa: E731
        self.assertEqual(v("[단독] LS전선, 장애인 예술단 자회사 ‘누리이음’ 설립…ESG 경쟁력 강화 포석", "LS전선", "2026-11-03T17:00:00+09:00")[0], "같은 회사 항목만")
        self.assertEqual(v("[단독] 금호타이어, 노조 임단협 결렬", "금호타이어", "2026-11-03T09:00:00+09:00")[0], "같은 회사 항목만")
        # 품목 낱말이 회사 이름 밖에 있으면 센다(기사 해저케이블 ↔ 등기 이름 SUBSEA CABLES — 'LS Cable' 회사 이름이 아님)
        verdict, best, _ = v("[단독] LS전선, 영국에 해저케이블 법인 세운다", "LS전선", "2026-11-03T09:00:00+09:00")
        self.assertEqual((verdict, best["id"]), ("먼저 잡은 후보", "ch:ls"))

    def test_article_numbers_are_checked_against_the_radar_text(self):
        # 11-09: '먼저 잡은 후보'에 같은 분야 다른 사실이 섞인다 — 기사 제목 숫자가 레이더 원문(관보 표 세율)에도 있는지 붙인다
        docs = {"trade-remedy": {"federalRegister": [
            {"id": "fr:2026-22630", "named": [{"company": "현대제철"}], "title": "Circular Welded Non-Alloy Steel Pipe From the Republic of Korea: Final Results",
             "rateTable": {"kind": "반덤핑", "rates": {"현대제철": {"rate": 4.2}}, "othersRate": 0.0}, "memoTopics": ["Comment 1"], "firstSeen": "2026-11-05T00:00:00+09:00"},
            {"id": "fr:core", "named": [{"company": "KG스틸"}], "title": "Certain Corrosion-Resistant Steel Products From the Republic of Korea: Preliminary Results of Countervailing Duty",
             "rateTable": {"kind": "상계관세", "rates": {"KG스틸": {"rate": 1.05}}}, "firstSeen": "2026-10-26T21:32:00+09:00"}]}}
        items = r.memory(docs, {})
        self.assertIn("4.20% 0.00%", next(m["text"] for m in items if m["id"] == "fr:2026-22630"))
        # 관보 다음에 본 단서(세율 없음)보다 숫자까지 같은 관보 항목을 고른다
        items.append(r.mem("clues", "clue:pipe", ["현대제철"], "Circular Welded Non-Alloy Steel Pipe From the Republic of Korea: Final Results duty", "2026-11-05T01:00:00+09:00"))
        v, best, _ = r.match({"title": "[단독] 美, 현대제철 강관 반덤핑 4.20% 확정…휴스틸은 0%", "companies": ["현대제철"], "published": "2026-11-05T08:35:00+09:00"}, items)
        self.assertEqual((v, best["id"], best["numbers"]), ("먼저 잡은 후보", "fr:2026-22630", {"article": ["4.20%"], "found": ["4.20%"], "comparable": True}))
        v, best, _ = r.match({"title": "[단독] 美 도금강판 관세 70%대 위협…동국씨엠·KG스틸, 법적 대응 저울질", "companies": ["KG스틸"], "published": "2026-10-30T05:00:00+09:00"}, items)
        self.assertEqual((v, best["numbers"]), ("먼저 잡은 후보", {"article": ["70%대"], "found": [], "comparable": True}))
        # 기사보다 늦게 본 관보 항목은 후보가 못 되지만, 먼저 본 단서가 같은 문서(관보 번호)를 가리키면 그 글의 세율로 숫자를 본다
        late = r.memory({"trade-remedy": {"federalRegister": [dict(docs["trade-remedy"]["federalRegister"][0], firstSeen="2026-11-05T09:00:00+09:00",
                                                                    url="https://www.federalregister.gov/documents/2026/11/05/2026-22630/circular-welded")]}}, {})
        clue = r.mem("clues", "clue:pipe", ["현대제철"], "Circular Welded Non-Alloy Steel Pipe From the Republic of Korea: Final Results duty", "2026-11-05T00:00:00+09:00",
                     "https://www.federalregister.gov/d/2026-22630")
        v, best, _ = r.match({"title": "[단독] 美, 현대제철 강관 반덤핑 4.20% 확정", "companies": ["현대제철"], "published": "2026-11-05T08:35:00+09:00"}, late + [clue])
        self.assertEqual((v, best["id"], best["numbers"]["found"]), ("먼저 잡은 후보", "clue:pipe", ["4.20%"]))
        v, best, _ = r.match({"title": "[단독] 美, 현대제철 강관 반덤핑 4.20% 확정", "companies": ["현대제철"], "published": "2026-11-05T08:35:00+09:00"},
                             [dict(clue, url=None)])
        self.assertEqual(best["numbers"], {"article": ["4.20%"], "found": [], "comparable": False})     # 세율 없는 글 — 비교 못 함
        v, best, _ = r.match({"title": "[단독] 포스코, 美 변압기 관세 정산 보류", "companies": ["현대제철"], "published": "2026-11-05T08:35:00+09:00"}, items)
        self.assertNotIn("numbers", best or {})                                     # 기사 제목에 숫자가 없으면 안 붙임

    def test_numbers_in(self):
        self.assertEqual([x[2] for x in r.numbers_in("1조2000억원 투자·3500억·504MW·휴스틸 0%")], ["1조2000억원", "3500억", "504MW"])
        self.assertEqual(r.same_numbers("3000억대 증설", "투자 3,450억원"), (["3000억대"], ["3000억대"], True))
        self.assertEqual(r.same_numbers("강관 4.2%", "duty 4.20%"), (["4.2%"], ["4.2%"], True))
        self.assertEqual(r.same_numbers("관세 70%대", "duty 80.10%"), (["70%대"], [], True))
        self.assertEqual(r.same_numbers("관세 70%대", "투자 3,450억원"), (["70%대"], [], False))
        self.assertEqual(r.doc_key("https://www.federalregister.gov/documents/2026/11/05/2026-22630/circular"), "fr:2026-22630")
        self.assertEqual(r.doc_key("https://www.federalregister.gov/d/2026-22630"), "fr:2026-22630")

class Places(unittest.TestCase):
    """11-04 기자 기사 대조: 장소 있는 항목은 기사 제목에 같은 지역 이름이 있어야 '먼저 잡은 후보'."""
    ITEMS = [r.mem("kr-building", "bld:947602", ["LS전선"], "공장 건축허가 경상북도 구미시 진평동 643번지 증설 신축 plant factory", "2026-10-29T16:21:00+09:00"),
             r.mem("kr-building", "bld:857775", ["OCI"], "공장 건축허가 증축 공장 전남광주통합특별시 광양시 태인동 1658번지 증설 신축 plant factory", "2026-10-29T17:14:00+09:00")]

    def verdict(self, title, comp, when):
        return r.match({"title": title, "companies": [comp], "published": when}, [m for m in self.ITEMS if m])

    def test_same_city_matches_other_city_or_none_does_not(self):
        v, best, _ = self.verdict("LS전선, 구미에 3500억원 들여 희토류 영구자석 공장 짓는다", "LS전선", "2026-10-30T10:49:00+09:00")
        self.assertEqual((v, best["id"]), ("먼저 잡은 후보", "bld:947602"))
        v, best, n = self.verdict("LS전선·LS마린솔루션, 504MW 태안해상풍력 해저케이블 일정 확보", "LS전선", "2026-11-02T11:27:00+09:00")
        self.assertEqual((v, n), ("같은 회사 항목만", 1))                   # 태안 기사 ↔ 구미 허가: 낱말만 겹침
        v, _, _ = self.verdict("OCI그룹, 반도체소재사업본부·AX조직 신설", "OCI", "2026-11-02T11:26:00+09:00")
        self.assertEqual(v, "같은 회사 항목만")                              # 지역 없는 조직 기사 ↔ 광양 허가

    def test_place_names(self):
        self.assertEqual(r.places_in("Hanwha Q Cells Cartersville, Georgia air permit"), {"조지아"})
        self.assertEqual(r.places_in("㈜포스코 포항제철소 배출구 39번"), {"포항"})
        self.assertEqual(r.places_in("2027년 예산 음성 안내"), set())     # 흔한 낱말과 겹치는 지명은 안 셈

class Governance(unittest.TestCase):
    def test_kg_steel_treasury_article_matches_disposal(self):
        docs = {"governance": {"items": [
            {"company": "KG스틸", "kind": "자사주 처분 결정", "date": "2026-10-15", "receiptNo": "20261015000414", "routine": False,
             "reason": '처분목적 "임직원 지급을 위한 자기주식 처분" · 2,461,991주·136.9억원', "tags": ["[처분목적: 임직원 보상]", "[보유 자사주의 100%]"]},
            {"company": "현대자동차", "kind": "자사주 처분 결정", "date": "2026-03-26", "receiptNo": "x", "routine": True, "reason": "임원 대상"}]}}
        items = r.memory(docs, {})
        self.assertEqual([m["id"] for m in items if m["source"] == "governance"], ["20261015000414"])   # 일상 보상은 기억에 안 넣음
        v, best, _ = r.match({"title": "주주가치 높인다며 산 자사주…KG스틸, 임직원 보상에 쓴다", "companies": ["KG스틸"], "published": "2026-10-24T09:00:00+09:00"}, items)
        self.assertEqual((v, best["label"]), ("먼저 잡은 후보", "지분·자사주 변동"))

    def test_merger_completion_article_matches_completion_report_11_11(self):
        clues = {"items": [{"id": "c-kumho", "companies": ["금호석유화학"], "title": "금호석유화학 · 합병등종료보고서(합병)", "published": "2026-11-10"}]}
        items = r.memory({}, clues)
        v, best, _ = r.match({"title": "금호석유화학, 특수가스 자회사 흡수합병 마무리", "companies": ["금호석유화학"], "published": "2026-11-11T10:00:00+09:00"}, items)
        self.assertEqual((v, best["id"]), ("먼저 잡은 후보", "c-kumho"))
        self.assertIn("합병 종료", best["why"])
        # 합병을 '추진'한다는 기사는 종료 보고서와 같은 사건이 아니다(개념 '합병' 하나만 겹침)
        v2, _, _ = r.match({"title": "금호석유화학, 특수가스 자회사 흡수합병 추진", "companies": ["금호석유화학"], "published": "2026-11-11T10:00:00+09:00"}, items)
        self.assertEqual(v2, "같은 회사 항목만")


class Tally(unittest.TestCase):
    def test_type_and_outlet_tallies(self):
        trace = {"items": [
            {"articleId": "s1", "title": "[단독] 포스코, 미국 상계관세 소송서 패소 - 뉴스저널리즘", "published": "2026-10-28T10:50:00+09:00", "sourceName": "뉴스저널리즘", "companies": ["포스코"]},
            {"articleId": "s2", "title": "[단독] LG그룹, 현대차 로봇사업 수장 영입", "published": "2026-10-23T09:00:00+09:00", "sourceName": "Y", "companies": ["현대차"]},
            {"articleId": "s3", "title": "[단독] 현대차, 앨라배마 공장 증설", "published": "2026-10-23T09:00:00+09:00", "sourceName": "Y", "companies": ["현대차"]}]}
        doc = r.run(trace, {}, {}, now=NOW)
        self.assertEqual({x["articleId"]: x["type"] for x in doc["articles"]}, {"s1": "논란·법적", "s2": "인사·조직", "s3": "투자·공장"})
        self.assertEqual(doc["byOutlet"]["Y"]["total"], 2)
        self.assertEqual(doc["byType"]["인사·조직"]["없음"], 1)

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
