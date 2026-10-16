import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import reporting_evidence_queue as q

KST=timezone(timedelta(hours=9))
NOW=datetime(2026,10,16,11,0,tzinfo=KST)
def url(r):
    return "https://dart.fss.or.kr/dsaf001/main.do?rcpNo="+r

def fixtures():
    stamp="2026-10-16T10:00:00+09:00"
    return {
      "officialEvents":{"generatedAt":stamp,"status":"official_date_triage",
         "sourceCompletenessVerified":False,"incompleteOrStaleFeeds":["nhtsa_official"],
         "freshOfficialReview":[{
           "source":"DART_FILING","id":"DART_FILING:20261015800054",
           "officialDate":"2026-10-15","officialReceiptNo":"20261015800054",
           "company":"대한전선","headline":"대한전선 신규 계약 공시",
           "officialFact":"공식 접수제목만 검증","sourceUrl":url("20261015800054"),
           "classification":"public_official_document_not_a_scoop",
           "companyImpactVerified":False,"exclusiveConfirmed":False,
           "approvedForPitch":False
         }]},
      "investment":{"generatedAt":stamp,
         "status":"source_changes_detected_not_exclusive",
         "investigations":[{
           "company":"HD현대일렉트릭","projects":[{
             "company":"HD현대일렉트릭","project":"변압기 철심공장",
             "factVerified":"두 시점 공시상 같은 투자 표를 원문 비교","alreadyPublic":True,
             "oldPlannedEnd":"2026.01","newPlannedEnd":"2026.11",
             "endMonthShift":10,"annualReceipt":"20260316000940",
             "currentReceipt":"20260814003228",
             "originalUrls":[url("20260316000940"),url("20260814003228")]
           }]}]},
      "metrics":{"generatedAt":stamp,"status":"evidence_comparison",
         "items":[{"company":"엘에스일렉트릭",
                   "topic":"productionCapacity","rowIdentity":["부산","HVDC"],
                   "evidenceStatus":"동일 회사·기간·단위·행명 일치 검증",
                   "fromYear":2025,"toYear":2026,"priorValue":"100",
                   "currentValue":"300","unit":"백만원",
                   "originalReceipts":["20250814001952","20260814003088"],
                   "sourceUrls":[url("20250814001952"),url("20260814003088")]}]},
      "contracts":{"generatedAt":stamp,"status":"reporter_review_not_exclusive",
         "items":[{
           "company":"두산에너빌리티","receiptNo":"20261006800697",
           "officialSourceUrl":url("20261006800697"),"isCorrection":True,
           "headline":"두산 계약 정정","officialSourceStatus":"original_not_verified",
           "comparisonStatus":"original_unverified_no_comparison",
           "originalReceiptNo":None,"approvedForPitch":False,
           "exclusiveConfirmed":False,
           "issuerDeclaredMaterialChanges":[{
               "fieldLabel":"계약내역 금액",
               "basis":"issuer_reported_amendment_table_only",
               "originalDocumentCompared":False
           }]},{
           "company":"대한전선","receiptNo":"20261015800054",
           "officialSourceUrl":url("20261015800054"),
           "headline":"대한전선 계약 공시","isCorrection":False,
           "comparisonStatus":"not_a_correction",
           "approvedForPitch":False,"exclusiveConfirmed":False
         }]}
    }


class EvidenceQueue(unittest.TestCase):
    def test_real_date_tiers_cannot_be_freshened_by_snapshot_time(self):
        x=q.build(fixtures(),now=NOW)
        self.assertEqual(x["status"],"reporter_evidence_queue_not_exclusive")
        self.assertEqual(x["checkedOfficialRecentCandidates"],1)
        self.assertEqual(x["countsByEvidenceTier"]["verified_historical_investment_delta"],1)
        self.assertEqual(x["countsByEvidenceTier"]["verified_historical_numeric_delta"],1)
        self.assertEqual(x["countsByEvidenceTier"]["issuer_only_correction_unverified_original"],1)
        self.assertEqual(x["countsByEvidenceTier"]["older_public_contract_reference"],0)
        self.assertEqual(x["excluded"]["same_receipt_merged"],1)
        self.assertEqual(x["confirmedScoops"],0)
        self.assertEqual(x["approvedArticles"],0)
        for item in x["items"]:
            self.assertFalse(item["exclusiveConfirmed"])
            self.assertFalse(item["approvedForPitch"])
            self.assertFalse(item["companyImpactVerified"])
            self.assertFalse(item["pressFulltextReviewed"])
        august=next(v for v in x["items"] if v["tier"]=="verified_historical_investment_delta")
        self.assertEqual(august["officialDocumentDate"],"2026-08-14")
        self.assertIn("실제 준공",august["evidenceSummary"])
        corrected=next(v for v in x["items"] if v["tier"]=="issuer_only_correction_unverified_original")
        self.assertIn("최초 원공시 미대조",corrected["evidenceSummary"])

    def test_empty_fresh_is_not_zero_news_coverage(self):
        s=fixtures()
        s["officialEvents"]["freshOfficialReview"]=[]
        s["contracts"]=None
        r=q.build(s,now=NOW)
        self.assertEqual(r["checkedOfficialRecentCandidates"],0)
        self.assertEqual(r["sourceCoverage"],"partial_source_coverage_not_zero_news")
        self.assertEqual(r["sourceHealth"]["contracts"]["status"],"unavailable_or_schema_mismatch")

    def test_bad_urls_and_future_dated_items_are_not_in_queue(self):
        s=fixtures()
        s["officialEvents"]["freshOfficialReview"][0]["officialDate"]="2026-10-19"
        s["investment"]["investigations"][0]["projects"][0]["originalUrls"][1]="https://evil.example/file"
        s["metrics"]["items"][0]["originalReceipts"][1]="20269999000000"
        r=q.build(s,now=NOW)
        self.assertEqual(r["countsByEvidenceTier"]["new_official_receipt_review"],0)
        self.assertEqual(r["countsByEvidenceTier"]["verified_historical_investment_delta"],0)
        self.assertEqual(r["countsByEvidenceTier"]["verified_historical_numeric_delta"],0)

    def test_prior_press_or_verified_scoop_forgery_is_not_promoted(self):
        s=fixtures()
        s["officialEvents"]["freshOfficialReview"][0]["exclusiveConfirmed"]=True
        s["contracts"]["items"][0]["exclusiveConfirmed"]=True
        out=q.build(s,now=NOW)
        self.assertEqual(out["checkedOfficialRecentCandidates"],0)
        self.assertEqual(out["countsByEvidenceTier"]["issuer_only_correction_unverified_original"],0)

    def test_invalid_correction_with_claimed_original_skipped(self):
        s=fixtures()
        s["contracts"]["items"][0]["originalReceiptNo"]="20261001800011"
        out=q.build(s,now=NOW)
        self.assertEqual(out["countsByEvidenceTier"]["issuer_only_correction_unverified_original"],0)
        self.assertEqual(out["excluded"]["unverified_correction"],1)

    def test_unverified_dates_and_domains(self):
        self.assertFalse(q.dart_url("20261015800054","https://evil.example/dsaf001/main.do?rcpNo=20261015800054"))
        self.assertFalse(q.dart_url("20261015800054","https://dart.fss.or.kr.evil.example/dsaf001/main.do?rcpNo=20261015800054"))
        self.assertFalse(q.dart_url("20261015800054","https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261015800054&x=y"))
        self.assertTrue(q.dart_url("20261015800054",url("20261015800054")))
        self.assertIsNone(q.date_value("20260230"))
        self.assertIsNone(q.date_value("20261022-no"))

    def test_future_source_snapshot_cannot_make_new_scoops(self):
        s=fixtures()
        s["officialEvents"]["generatedAt"]="2026-10-20T00:00:00+09:00"
        out=q.build(s,now=NOW)
        self.assertEqual(out["sourceHealth"]["officialEvents"]["status"],"future_timestamp_invalid")
        self.assertEqual(out["checkedOfficialRecentCandidates"],0)
        self.assertEqual(out["confirmedScoops"],0)


if __name__=="__main__":
    unittest.main()
