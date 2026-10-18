import copy
import sys
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import official_event_triage as t

KST=timezone(timedelta(hours=9))
NOW=datetime(2026,10,15,12,0,tzinfo=KST)
def samples():
    stamp="2026-10-15T10:30:00+09:00"
    return dict(
      recent_contracts=dict(generatedAt=stamp,sourceChecks=[dict(status="checked")],
        items=[
          dict(company="엘에스일렉트릭",receiptNo="20261013800054",
               published="20261013",sourceUrl="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261013800054",
               status="official_document_read",category="공급계약",isCorrection=False,
               report="단일판매·공급계약체결",observedFields={}),
          dict(company="두산에너빌리티",receiptNo="20261014800012",
               published="20261014",sourceUrl="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261014800012",
               status="original_not_verified",category="공급계약",isCorrection=True,
               originalReceiptNo=None,report="[정정]공급계약"),
          dict(company="현대제철",receiptNo="20260814001234",
               published="20260814",sourceUrl="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260814001234",
               status="official_document_read",category="시설투자",isCorrection=False,
               report="신규시설 투자")]),
      overseas_official=dict(generatedAt=stamp,checks=[dict(status="checked")],
        documents=[
          dict(source="US Federal Register",sourceId="2026-21111",
               published="2026-10-14",nameVerified=False,
               companiesMentioned=[],title="Generic anti-dumping announcement",
               sourceUrl="https://www.federalregister.gov/documents/2026/10/14/2026-21111/item"),
          dict(source="US Federal Register",sourceId="2026-20778",
               published="2026-10-09",nameVerified=True,
               companiesMentioned=["현대제철","포스코"],title="Korean steel final review",
               sourceUrl="https://www.federalregister.gov/documents/2026/10/09/2026-20778/item")]),
      investigation_hunt=dict(generatedAt=stamp,investigations=[
        dict(company="HD현대일렉트릭",projects=[
          dict(project="변압기 철심공장",
               originalUrls=[
                 "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260316000940",
                 "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260814003228"])])]),
      recent_metric_changes=dict(generatedAt=stamp,items=[
        dict(company="일진전기",rowIdentity=["홍성","변압기"],priorValue="100",
             currentValue="200",unit="백만원",originalReceipts=["20250811000431","20260811000431"],
             sourceUrls=[
               "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20250811000431",
               "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260811000431"])]),
      nhtsa_official=dict(generatedAt=stamp,checks=[
          dict(status="checked"),dict(status="source_error")],records=[
          dict(make="Hyundai",model="IONIQ 5",id="26V047000",reportDate="27/01/2026",
            kind="recalls",officialApi="https://api.nhtsa.gov/recalls/recallsByVehicle?make=Hyundai")
        ])
    )
class OfficialEventTriage(unittest.TestCase):
    def test_correct_date_not_collection_date_and_no_stale_scoops(self):
        result=t.build(samples(),now=NOW)
        self.assertEqual(result["freshOfficialReviewCount"],1)
        lead=result["freshOfficialReview"][0]
        self.assertEqual(lead["id"],"DART_FILING:20261013800054")
        self.assertEqual(lead["officialDate"],"2026-10-13")
        self.assertIsNone(lead["firstObservedThisRun"])
        self.assertFalse(lead["exclusiveConfirmed"])
        self.assertFalse(lead["contractTermsVerified"])
        self.assertEqual(result["confirmedScoops"],0)
        self.assertEqual(result["backgroundReferenceCount"],5)
        self.assertEqual(result["excluded"]["correction_without_original"],1)
        self.assertEqual(result["excluded"]["unverified_foreign_search_hit"],1)
    def test_duplicate_same_filing_is_not_multiple_fresh_leads(self):
        a=samples();a["recent_contracts"]["items"].append(copy.deepcopy(a["recent_contracts"]["items"][0]))
        out=t.build(a,now=NOW)
        self.assertEqual(out["freshOfficialReviewCount"],1)
        self.assertEqual(out["excluded"]["duplicate_event_id"],1)
    def test_bad_receipt_or_crosshost_link_cannot_enter_queue(self):
        a=samples()
        a["recent_contracts"]["items"][0]["sourceUrl"]="https://fake-dart.example/dsaf001/main.do?rcpNo=20261013800054"
        out=t.build(a,now=NOW)
        self.assertEqual(out["freshOfficialReviewCount"],0)
        self.assertEqual(out["excluded"]["source_without_official_identity"],1)
    def test_current_public_recalls_cannot_be_exclusive_queue(self):
        a=samples()
        a["nhtsa_official"]["records"][0]["reportDate"]="15/10/2026"
        r=t.build(a,now=NOW)
        self.assertEqual(r["freshOfficialReviewCount"],1)
        record=next(x for x in r["backgroundReference"] if x["source"]=="NHTSA")
        self.assertEqual(record["editorialBucket"],"published_background")
    def test_partial_source_is_not_verified_zero(self):
        a=samples()
        out=t.build(a,now=NOW)
        self.assertIn("nhtsa_official",out["incompleteOrStaleFeeds"])
        self.assertFalse(out["sourceCompletenessVerified"])
        self.assertEqual(next(x for x in out["feedHealth"] if x["name"]=="nhtsa_official")["status"],"partial_collection")
    def test_source_older_than_24h_not_reported_fresh(self):
        a=samples()
        a["recent_contracts"]["generatedAt"]="2026-10-13T09:00:00+09:00"
        out=t.build(a,now=NOW)
        self.assertIn("recent_contracts",out["incompleteOrStaleFeeds"])
        self.assertEqual(out["freshOfficialReview"][0]["officialDate"],"2026-10-13")
        self.assertFalse(out["sourceCompletenessVerified"])
    def test_prior_seen_preserves_first_observation_without_scoop(self):
        old=t.build(samples(),now=NOW)
        newer=t.build(samples(),now=NOW+timedelta(hours=1),previous=old)
        self.assertFalse(newer["firstRunBaseline"])
        item=newer["freshOfficialReview"][0]
        self.assertFalse(item["firstObservedThisRun"])
        self.assertFalse(item["exclusiveConfirmed"])
        fresh=samples()
        fresh["recent_contracts"]["items"][0]["receiptNo"]="20261015800091"
        fresh["recent_contracts"]["items"][0]["published"]="20261015"
        fresh["recent_contracts"]["items"][0]["sourceUrl"]="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261015800091"
        newer=t.build(fresh,now=NOW+timedelta(hours=1),previous=old)
        self.assertTrue(newer["freshOfficialReview"][0]["firstObservedThisRun"])
        self.assertFalse(newer["freshOfficialReview"][0]["exclusiveConfirmed"])
    def test_overseas_proven_mention_still_requires_industry_impact(self):
        a=samples()
        a["overseas_official"]["documents"][1]["published"]="2026-10-14"
        res=t.build(a,now=NOW)
        self.assertEqual(res["freshOfficialReviewCount"],2)
        e=next(x for x in res["freshOfficialReview"] if x["source"]=="FOREIGN_NOTICE")
        self.assertEqual(e["company"],"현대제철·포스코")
        self.assertFalse(e["companyImpactVerified"])
        self.assertFalse(e["approvedForPitch"])
    def test_only_current_quarter_dart_number_change_still_old_filing(self):
        a=samples()
        a["recent_metric_changes"]["generatedAt"]="2026-10-15T11:59:00+09:00"
        out=t.build(a,now=NOW)
        metric=next(x for x in out["backgroundReference"] if x["source"]=="DART_METRIC")
        self.assertEqual(metric["officialDate"],"2026-08-11")
        self.assertFalse(metric["freshArticleConfirmed"])
    def test_verification_questions_only_request_public_facts(self):
        result=t.build(samples(),now=NOW)
        delta=next(x for x in result["backgroundReference"] if x["source"]=="DART_DELTA")
        metric=next(x for x in result["backgroundReference"] if x["source"]=="DART_METRIC")
        self.assertIn("공시",delta["verification"])
        self.assertIn("미공개 생산계획 질의 금지",delta["verification"])
        self.assertNotIn("가동일·생산 물량",delta["verification"])
        self.assertIn("공표 수치만",metric["verification"])
        self.assertFalse(delta["approvedForPitch"])
        self.assertFalse(metric["approvedForPitch"])

    def test_malformed_and_missing_feeds_not_zero(self):
        a=samples();a["overseas_official"]={}
        r=t.build(a,now=NOW)
        self.assertIn("overseas_official",r["incompleteOrStaleFeeds"])
        self.assertIsNone(next(x for x in r["feedHealth"] if x["name"]=="overseas_official")["records"])

if __name__=="__main__":unittest.main()
