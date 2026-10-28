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
        self.assertEqual((posco["verdict"], posco["best"]["id"]), ("먼저 잡은 후보", "cl:74869986"))  # the ruling was seen after the article
        baic = by["a3"]
        self.assertEqual((baic["verdict"], baic["best"]["label"]), ("먼저 잡은 후보", "해외 파트너 공시"))
        self.assertIn("지분·합작·거래", baic["best"]["why"])
        robot = by["a4"]
        self.assertEqual(robot["verdict"], "같은 회사 항목만")  # 현대차 items exist but nothing about a hire
        self.assertEqual(robot["best"]["why"], [])
        self.assertEqual(by["a5"]["verdict"], "없음")
        self.assertEqual(doc["counts"], {"먼저 잡은 후보": 3, "같은 회사 항목만": 1, "없음": 1, "회사 미상": 0})
        self.assertEqual(doc["bySource"]["미국 소송·판결"]["caught"], 2)
        self.assertEqual(doc["bySource"]["해외 파트너 공시"]["leadHours"] if "leadHours" in doc["bySource"]["해외 파트너 공시"] else
                         doc["bySource"]["해외 파트너 공시"]["leadHoursMedian"], 11.3)

    def test_one_feed_with_an_unexpected_shape_does_not_stop_the_others(self):
        bad = {**DOCS, "kr-signals": {"decisions": [{"id": "d1", "mentions": ["포스코"], "name": "x", "fileDate": "2026-10-01"}]},
               "page-watch": {"events": [{"pageId": "p", "company": ["not", "a", "string"], "added": ["Coming 2027"], "detectedAt": "2026-10-20T06:30:00+09:00"}]}}
        doc = r.run(TRACE, bad, CLUES, now=NOW)
        self.assertEqual(doc["adapterErrors"], {"kr-signals": "AttributeError"})
        self.assertEqual(doc["counts"]["먼저 잡은 후보"], 3)  # litigation and partner filings still read

    def test_group_names_and_missing_times(self):
        self.assertEqual(r.canon("포스코홀딩스"), "포스코")
        self.assertEqual(r.canon("효성중공업(관련)"), "효성중공업")
        self.assertIsNone(r.mem("x", "1", ["현대차"], "t", None))
        self.assertIsNone(r.mem("x", "1", [], "t", "2026-10-01"))
        self.assertEqual(r.parse_time("20261021").isoformat(), "2026-10-21T00:00:00+09:00")


if __name__ == "__main__":
    unittest.main()
