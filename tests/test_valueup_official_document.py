"""Official ZIP DART corporate value-up raw text with no inferred target amounts."""
import json
import sys
import unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import valueup_official_document as m
import dart_beat_monitor as beat

def official():
    d=json.loads((ROOT/"digests/dart_beat_monitor_latest.json").read_text(encoding="utf-8"))
    return next(x for x in d["records"] if x["receiptNo"]=="20261016800823")

class OfficialValueUpDocuments(unittest.TestCase):
    def test_current_kgsteel_doc_original_issuer_scope_verified(self):
        row=official()
        self.assertTrue(m.is_current_valueup_filing(row))
        self.assertEqual(row["corpCode"],"00115676")

    def test_literal_only_detects_official_text_not_actual_outcome(self):
        row=official()
        content="<html><table><tr><td>목표설정</td><td>2029년 PBR 0.5배 이상 목표</td></tr><tr><td>주주 환원</td><td>5개년 목표 주주환원율 50% 환원</td></tr></table></html>"
        result=m.valueup_document_evidence(row,"test",documents=lambda key,r:[content])
        self.assertEqual(result["status"],"official_valueup_document_review")
        self.assertFalse(result["sourceError"])
        proof=result["valueupPrimarySource"]
        self.assertEqual(proof["status"],"official_original_text_checked_no_inference")
        self.assertEqual(len(proof["documentTextSha256"]),1)
        self.assertEqual(set(proof["targetExcerpts"]),{
            "pbr_2029_at_least_0_5","five_year_shareholder_return_50_percent"})
        self.assertFalse(proof["officialAttachmentPdfReviewed"])
        self.assertFalse(proof["targetAchievementVerified"])
        self.assertFalse(proof["crossYearPlanPeriodMatched"])
        self.assertFalse(proof["exclusiveConfirmed"])

    def test_old_percent_and_non_target_text_not_2026_goal(self):
        sample="<html>2025년 ROE 13%와 주주환원율 30% 목표 참조. 2029년 PBR 0.4배. 5개년 주주환원율 30%.</html>"
        result=m.literal_target_excerpts([sample])
        self.assertEqual(result["targetExcerpts"],{})
        self.assertTrue(result["notMatchedDoesNotMeanIssuerHasNoTarget"])

    def test_official_source_failure_is_not_zero_goals_and_is_retryable(self):
        row=official()
        def deny(key,receipt):
            raise ValueError("DART document zip returned invalid XML")
        result=m.valueup_document_evidence(row,"test",documents=deny)
        self.assertEqual(result["status"],"valueup_document_unavailable")
        self.assertTrue(result["sourceError"])
        self.assertEqual(result["errorType"],"ValueError")
        self.assertFalse(result["valueupPrimarySource"]["officialXmlOrHtmlBodyRetrieved"])
        self.assertEqual(result["valueupPrimarySource"]["status"],
                         "source_unavailable_not_zero_target_facts")

    def test_fake_corp_or_correction_never_fetches_original(self):
        row=official()
        for change in [
             {"corpCode":"not-a-code"}, {"company":""},
             {"receiptNo":"20261016800824"},
             {"published":"20261015"},
             {"sourceType":"google-news-rss"},
             {"sourceUrl":"https://evil.test?rcpNo=20261016800823"},
             {"report":"[첨부정정]기업가치제고계획(자율공시)"},
             {"isCorrection":True},
        ]:
            bad={**row,**change}
            called=[]
            def forbid(key,rcp):
                called.append(True)
                return []
            with self.assertRaises(ValueError):
                m.valueup_document_evidence(bad,"test",documents=forbid)
            self.assertEqual(called,[])

    def test_real_collector_bounded_new_valueup_read_and_retry_after_error(self):
        template=official()
        def fake_query(key,name,code,start,end):
            return {"records":[dict(template)] if name=="KG스틸" else [],
                    "pagesRead":1,"complete":True,"totalOfficialFilings":1,
                    "status":"checked"}
        def success(row,key):
            return m.valueup_document_evidence(row,key,documents=lambda k,r:[
              "<p>2029년 PBR 0.5배 이상. 5개년 목표 주주환원율 50% 환원.</p>"])
        kwargs=dict(codes={"KG스틸":{"corp_code":"00115676"}},key="key",
                    now=datetime(2026,10,17,21,30,tzinfo=timezone(timedelta(hours=9))),
                    query=fake_query,valueup_detail=success)
        run=beat.collect(**kwargs)
        self.assertEqual(run["detailsAttempted"],1)
        self.assertEqual(run["valueupOfficialDocumentAttempts"],1)
        self.assertEqual(run["valueupOfficialDocumentReads"],1)
        self.assertEqual(run["valueupOfficialDocumentUnavailable"],0)
        self.assertEqual(run["uninspectedRelevantDetails"],0)
        # Same official receipt can reuse strictly the same previously read
        # source, never promote it to a new public business activity.
        next_run=beat.collect(**{**kwargs,"previous":run})
        self.assertEqual(next_run["detailsAttempted"],0)
        self.assertFalse(next_run["records"][0]["scoopConfirmed"])
        self.assertFalse(next_run["records"][0]["approvedForPitch"])
        def outage(row,key):
            return m.valueup_document_evidence(row,key,
                documents=lambda k,r: (_ for _ in ()).throw(ValueError("code999")))
        first=beat.collect(**{**kwargs,"valueup_detail":outage})
        self.assertEqual(first["uninspectedRelevantDetails"],1)
        self.assertEqual(first["valueupOfficialDocumentUnavailable"],1)
        recovered=beat.collect(**{**kwargs,"previous":first})
        self.assertEqual(recovered["detailsAttempted"],1)
        self.assertEqual(recovered["valueupOfficialDocumentReads"],1)

if __name__=="__main__":
    unittest.main()
