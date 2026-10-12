import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import business_coverage as bc


def row(company="HD현대일렉트릭",topic="segmentSales"):
    return {"company":company,"topic":topic,"toYear":2025,"rowIdentity":["전력기기"],
            "carryForwardMatched":True,"status":"양쪽 공식 원문 대조",
            "originalReceipts":["20250320001309","20260316000940"]}


class CoverageTests(unittest.TestCase):
    def test_search_query_preserves_company_year_and_topic(self):
        q=bc.query_for(row())
        self.assertIn("HD현대일렉트릭",q)
        self.assertIn("2025",q)
        self.assertIn("제품별 매출",q)

    def test_results_do_not_prove_same_event(self):
        feed=b'<rss><channel><item><title>HD Hyundai revenue growth</title><link>https://news.google.com/rss/articles/aaa</link><pubDate>Mon, 12 Oct 2026 05:00:00 GMT</pubDate></item></channel></rss>'
        found=bc.check_one(row(),fetch=lambda _:feed)
        self.assertEqual(len(found["articles"]),1)
        self.assertIn("사건 동일성",found["status"])
        self.assertIn("미검증",found["coverageDecision"])

    def test_no_hits_not_exclusive(self):
        found=bc.check_one(row(),fetch=lambda _:b'<rss><channel /></rss>')
        self.assertIn("단독 여부 판단 불가",found["status"])

    def test_source_error_is_not_no_coverage(self):
        found=bc.check_one(row(),fetch=lambda _:b'<html>error</html>')
        self.assertIn("검색 실패",found["status"])

    def test_nonbeat_company_cannot_be_tracked(self):
        with self.assertRaises(ValueError):
            bc.query_for(row(company="삼성전기"))

    def test_verified_findings_required(self):
        d=bc.build({"generatedAt":"x","sourceGeneratedAt":"s",
                    "findings":[{**row(),"carryForwardMatched":False}]},search=lambda _:self.fail("network"))
        self.assertEqual(d["checked"],0)
        self.assertIn("보류",d["items"][0]["exclusiveStatus"])

    def test_limited_search_and_source_timestamp(self):
        source={"generatedAt":"2026-10-13T01:30:00+09:00",
                "sourceGeneratedAt":"2026-10-13T01:28:00+09:00",
                "findings":[row(),row()]}
        checks=[]
        def search(f):
            checks.append(f)
            return {"status":"관련 보도 후보 발견: 사건 동일성 미확인","articles":[]}
        d=bc.build(source,search=search,limit=1)
        self.assertEqual(len(checks),1)
        self.assertEqual(d["metricsGeneratedAt"],source["generatedAt"])
        self.assertIn("미검색",d["items"][1]["coverage"]["status"])

if __name__=="__main__":
    unittest.main()
