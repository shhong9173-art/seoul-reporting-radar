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
    def test_kg_steel_recent_title_only_public_filing_is_never_pitched(self):
        src=fixtures()
        at=datetime(2026,10,17,20,45,tzinfo=KST)
        company="KG스틸"
        def row(receipt,title):
            return {"company":company,"corpCode":"00115676",
                "receiptNo":receipt,"published":receipt[:8],
                "sourceUrl":url(receipt),
                "sourceType":"official_list_receipt",
                "isCorrection":False,"report":title,
                "status":"not_inspected_bounded_detail_budget",
                "detailStatus":"not_inspected_bounded_detail_budget",
                "firstObservedThisRun":False}
        valueup=row("20261016800823","기업가치제고계획(자율공시)")
        cancelled=row("20261015800723","주식소각결정")
        old=row("20260930800523","기업가치제고계획(자율공시)")
        wrong_company=row("20261016800523","기업가치제고계획(자율공시)")
        wrong_company["corpCode"]="no-code"
        corrected=row("20261016800524","[기재정정]기업가치제고계획(자율공시)")
        src["dartBeat"]={
            "generatedAt":"2026-10-17T20:39:32+09:00",
            "status":"industry_beat_official_receipt_review",
            "sourceComplete":False,
            "uninspectedRelevantDetails":0,
            "records":[valueup,cancelled,old,wrong_company,corrected],
        }
        data=q.build(src,now=at)
        self.assertEqual(data["recentOfficialTitleOnlyCount"],2)
        self.assertEqual(data["checkedOfficialRecentCandidates"],2)
        self.assertEqual(data["sourceHealth"]["dartBeat"]["status"],
                         "source_partial_coverage")
        cards=[x for x in data["items"]
               if x["tier"]=="new_official_list_heading_review"]
        self.assertEqual({x["officialDocumentDate"] for x in cards},
                         {"2026-10-15","2026-10-16"})
        self.assertEqual({x["filingTypeFromOfficialTitle"] for x in cards},
                         {"기업가치제고계획","주식소각결정"})
        for card in cards:
            self.assertTrue(card["officialListTitleOnly"])
            self.assertFalse(card["officialDocumentBodyReviewed"])
            self.assertFalse(card["companyImpactVerified"])
            self.assertFalse(card["disclosedFinancialImpactVerified"])
            self.assertFalse(card["pressFulltextReviewed"])
            self.assertFalse(card["exclusiveConfirmed"])
            self.assertFalse(card["approvedForPitch"])
            self.assertTrue(card["firstObservedHereNotFirstReported"])

        # Same DART receipt from broader government triage must not double count.
        another=q.build(src,now=at)
        self.assertEqual(another["recentOfficialTitleOnlyCount"],2)
        src["officialEvents"]["freshOfficialReview"][0].update({
            "officialDate":"2026-10-16",
            "officialReceiptNo":"20261016800823",
            "id":"DART_FILING:20261016800823",
            "company":"KG스틸",
            "headline":"KG스틸 가치제고계획 공식 공시",
            "sourceUrl":url("20261016800823")})
        dedup=q.build(src,now=at)
        self.assertEqual(dedup["checkedOfficialRecentCandidates"],2)
        self.assertEqual(dedup["recentOfficialTitleOnlyCount"],1)
        self.assertEqual(dedup["excluded"]["same_receipt_merged"],1)

    def test_tampered_issuer_and_recycled_official_title_is_not_novelty(self):
        src=fixtures()
        at=datetime(2026,10,17,20,45,tzinfo=KST)
        src["dartBeat"]={
            "generatedAt":"2026-10-17T20:39:32+09:00",
            "status":"industry_beat_official_receipt_review",
            "sourceComplete":True,"records":[{
                "company":"KG스틸","corpCode":"00115676",
                "receiptNo":"20261016800823","published":"20261016",
                "sourceUrl":"https://evil.example/disclose?rcpNo=20261016800823",
                "sourceType":"official_list_receipt",
                "isCorrection":False,"report":"기업가치제고계획(자율공시)"}]}
        r=q.build(src,now=at)
        self.assertEqual(r["recentOfficialTitleOnlyCount"],0)
        src["dartBeat"]["records"][0]["sourceUrl"]=url("20261016800823")
        src["dartBeat"]["records"][0]["published"]="20261015"
        self.assertEqual(q.build(src,now=at)["recentOfficialTitleOnlyCount"],0)
        src["dartBeat"]["records"][0]["published"]="20261016"
        src["dartBeat"]["records"][0]["sourceType"]="rss_aggregated_not_official"
        self.assertEqual(q.build(src,now=at)["recentOfficialTitleOnlyCount"],0)

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

    def test_three_source_unlinked_correction_is_review_not_recent_or_scoop(self):
        s=fixtures()
        stamp="2026-10-16T10:00:00+09:00"
        s["officialEvents"]["freshOfficialReview"]=[]
        amendment="20260930800924"
        prior="20260226801263"
        s["recentLedger"]={"generatedAt":stamp,"items":[{
            "company":"효성중공업","receiptNo":amendment,"published":"20260930",
            "sourceUrl":url(amendment),"isCorrection":True,
            "status":"original_not_verified","originalReceiptNo":None
        }]}
        s["contracts"]={"generatedAt":stamp,"dartSourceGeneratedAt":stamp,
            "status":"reporter_review_not_exclusive","items":[{
                "company":"효성중공업","receiptNo":amendment,"officialSourceUrl":url(amendment),
                "isCorrection":True,"comparisonStatus":"original_unverified_no_comparison",
                "officialSourceStatus":"original_not_verified","originalReceiptNo":None,
                "exclusiveConfirmed":False,"approvedForPitch":False
            }]}
        match={
            "field":"contract_amount",
            "priorCandidatePublishedValue":"372,324,339,860",
            "currentIssuerSaidBefore":"372,324,339,860",
            "currentIssuerSaidAfter":"383,338,819,710",
            "literalValuesMatch":True,"sameContractVerified":False,
            "contractEffectVerified":False,"previouslyReportedInMediaVerified":False,
            "basis":"unlinked_same_issuer_event_type_date_candidate_only"
        }
        s["correctionHistory"]={"generatedAt":stamp,"status":
            "bounded_unlinked_correction_history_for_reporter_review",
            "dartSourceGeneratedAt":stamp,"newsIndexSourceGeneratedAt":stamp,
            "verifiedSameContractHistory":0,"confirmedScoops":0,"approvedArticles":0,
            "items":[{
                "company":"효성중공업","receiptNo":amendment,"officialDate":"20260930",
                "sourceUrl":url(amendment),"linkageVerified":False,
                "confirmedExclusive":False,"approvedForPitch":False,
                "priorOfficialCandidateDocuments":[{
                    "receiptNo":prior,"officialDate":"20260226","sourceUrl":url(prior),
                    "relationshipStatus":"UNLINKED_same_company_category_reference_date",
                    "priorDocumentRetrieved":True,"sameContractVerified":False,
                    "currentAmendmentLinkedToThisOrigin":False,
                    "priorCandidateExplicitOriginVerifiedInIssuerList":False,
                    "unlinkedComparisons":[match]
                }]
            }]}
        d=q.build(s,now=NOW)
        self.assertEqual(d["unlinkedHistoryTextMatchCount"],1)
        self.assertEqual(d["todayOnlyCount"],0)
        self.assertEqual(d["correctionHistorySourceGate"],"reviewed_unlinked_candidates_only")
        item=next(r for r in d["items"] if r["tier"]=="unlinked_correction_text_followup")
        self.assertEqual(item["officialDocumentDate"],"2026-09-30")
        self.assertEqual(item["officialUrls"],[url(amendment),url(prior)])
        self.assertTrue(item["textMatchIsNotContractContinuity"])
        self.assertFalse(item["contractLinkVerified"])
        self.assertFalse(item["exclusiveConfirmed"])
        self.assertFalse(item["approvedForPitch"])
        self.assertFalse(item["newsArticleFulltextVerified"])
        self.assertIn("동일 계약 및 실제 계약 변경은 증명되지 않음",item["evidenceSummary"])

        # A previous candidate belongs to a different issuer/event if the
        # unrelated snapshots drift or issuer-given values do not match.
        s["correctionHistory"]["newsIndexSourceGeneratedAt"]="2026-10-16T09:00:00+09:00"
        mismatched=q.build(s,now=NOW)
        self.assertEqual(mismatched["unlinkedHistoryTextMatchCount"],0)
        self.assertEqual(mismatched["correctionHistorySourceGate"],
                         "original_document_snapshot_provenance_mismatch")
        s["correctionHistory"]["newsIndexSourceGeneratedAt"]=stamp
        s["correctionHistory"]["items"][0]["priorOfficialCandidateDocuments"][0][
            "unlinkedComparisons"][0]["currentIssuerSaidBefore"]="111,111,111,111"
        self.assertEqual(q.build(s,now=NOW)["unlinkedHistoryTextMatchCount"],0)

    def test_missing_history_stays_unavailable_not_zero_old_contracts(self):
        r=q.build(fixtures(),now=NOW)
        self.assertEqual(r["unlinkedHistoryTextMatchCount"],0)
        self.assertEqual(r["correctionHistorySourceGate"],"missing_or_stale_related_snapshots")
        self.assertNotEqual(r["sourceCoverage"],"verified_inputs_only")

    def test_live_dart_original_is_recent_without_broad_triage_completeness(self):
        s=fixtures()
        stamp="2026-10-16T10:00:00+09:00"
        receipt="20261015800054"
        fields={
            "contract_subject":"북미 초고압 케이블 납품의 건",
            "contract_amount":"116,810,902,865",
            "counterparty":"TAIHAN ELECTRIC USA LTD.",
            "counterparty_relationship":"자회사",
            "supply_region":"미국"
        }
        row={"company":"대한전선","receiptNo":receipt,
             "published":"20261015","sourceUrl":url(receipt),
             "status":"official_document_read","detailStatus":"official_document_read",
             "isCorrection":False,
             "documentFieldExtractionStatus":"official_table_terms_not_business_effect",
             "observedFields":fields,
             "observedFieldEvidence":{k:{"basis":"same_official_table_row"}
                                    for k in fields}}
        s["dartBeat"]={"generatedAt":stamp,
                       "status":"industry_beat_official_receipt_review",
                       "sourceComplete":False,"uninspectedRelevantDetails":0,
                       "records":[row]}
        result=q.build(s,now=NOW)
        self.assertEqual(result["checkedOfficialRecentCandidates"],1)
        self.assertEqual(result["sourceHealth"]["dartBeat"]["status"],"source_partial_coverage")
        self.assertGreaterEqual(result["excluded"]["same_receipt_merged"],2)
        item=next(x for x in result["items"]
                  if x["tier"]=="new_official_receipt_review")
        self.assertEqual(item["officialDocumentDate"],"2026-10-15")
        self.assertTrue(item["officialTableTermsRetrieved"])
        self.assertTrue(item["inGroupCounterpartyPerIssuerFiling"])
        self.assertFalse(item["externalNewCustomerVerified"])
        self.assertFalse(item["pressFulltextReviewed"])
        self.assertFalse(item["exclusiveConfirmed"])
        self.assertIn("TAIHAN ELECTRIC USA LTD.",item["evidenceSummary"])
        self.assertEqual(item["officialUrls"],[url(receipt)])
        self.assertEqual(item["editorialPriority"],"related_party_reference_only")
        # A mismatched URL, different company, or unverified field means no
        # evidence-based promotion; generic official item is still distinct.
        s["dartBeat"]["records"][0]["sourceUrl"]=url("20261015800055")
        other=q.build(s,now=NOW)
        self.assertFalse(any(x.get("officialTableTermsRetrieved") for x in other["items"]))
        s["dartBeat"]["records"][0]["sourceUrl"]=url(receipt)
        s["dartBeat"]["records"][0]["observedFieldEvidence"]["contract_amount"]["basis"]="inferred_from_title"
        other=q.build(s,now=NOW)
        self.assertFalse(any(x.get("officialTableTermsRetrieved") for x in other["items"]))
        s["dartBeat"]["records"][0]["observedFieldEvidence"]["contract_amount"]["basis"]="same_official_table_row"
        s["dartBeat"]["records"][0]["published"]="20261005"
        other=q.build(s,now=NOW)
        self.assertFalse(any(x.get("officialTableTermsRetrieved") for x in other["items"]))

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
