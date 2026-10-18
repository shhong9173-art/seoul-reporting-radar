import copy
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from official_beat_triage_merge import merge

KST = timezone(timedelta(hours=9))
NOW = datetime(2026, 10, 18, 16, 30, tzinfo=KST)


def triage():
    return {"status": "official_date_triage",
            "generatedAt": "2026-10-17T17:16:38+09:00",
            "freshOfficialReview": [], "backgroundReference": [],
            "seen": {}, "feedHealth": [], "confirmedScoops": 0,
            "approvedArticles": 0, "firstRunBaseline": False}


def record(receipt="20261016800823", company="KG스틸", correction=False):
    return {"company": company, "corpCode": "00115676", "receiptNo": receipt,
            "published": receipt[:8],
            "report": "기업가치제고계획(자율공시) (PBR 개선 계획 제출 기업)",
            "category": "정기·주요공시", "isCorrection": correction,
            "sourceUrl": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=" + receipt,
            "status": "official_valueup_document_review",
            "firstObservedAt": "2026-10-17T20:49:36+09:00"}


def beat():
    checks = [{"company": "KG스틸", "status": "checked"}]
    checks += [{"company": "가상기업" + str(i), "status": "checked"} for i in range(44)]
    checks += [{"company": "미등록" + str(i), "status": "corp_code_unavailable"}
               for i in range(3)]
    return {"status": "industry_beat_official_receipt_review",
            "generatedAt": "2026-10-18T09:24:53+09:00",
            "scopeCompanyCount": 48, "companiesCodeVerified": 45,
            "companiesUnresolved": 3, "companiesWithSourceErrors": 0,
            "sourceChecks": checks, "records": [record()]}


class BeatQueueIntegration(unittest.TestCase):
    def test_kg_valueup_is_public_review_not_exclusive(self):
        out = merge(triage(), beat(), now=NOW)
        self.assertEqual(out["beatWideDartAdded"], 1)
        self.assertEqual(out["freshOfficialReviewCount"], 1)
        item = out["freshOfficialReview"][0]
        self.assertEqual(item["officialReceiptNo"], "20261016800823")
        self.assertEqual(item["officialDate"], "2026-10-16")
        self.assertEqual(item["sourceSnapshotAt"], "2026-10-18T09:24:53+09:00")
        self.assertEqual(out["beatWideDartSourceAt"], item["sourceSnapshotAt"])
        self.assertEqual(item["firstObservedAt"], "2026-10-17")
        self.assertFalse(item["exclusiveConfirmed"])
        self.assertFalse(item["priorMediaCoverageVerified"])
        self.assertFalse(item["approvedForPitch"])
        self.assertFalse(item["originalDocumentFieldsVerified"])
        self.assertEqual(out["confirmedScoops"], 0)
        self.assertEqual(out["feedHealth"][-1]["status"], "partial_issuer_coverage")
        self.assertFalse(out["sourceCompletenessVerified"])
        self.assertNotIn("20%p", item["officialFact"])

    def test_rerun_is_idempotent(self):
        first = merge(triage(), beat(), now=NOW)
        second = merge(first, beat(), now=NOW)
        self.assertEqual(second["beatWideDartAdded"], 0)
        self.assertEqual(second["freshOfficialReviewCount"], 1)
        self.assertEqual(second["baseTriageGeneratedAt"],
                         "2026-10-17T17:16:38+09:00")

    def test_regenerated_triage_with_seen_history_keeps_old_receipts(self):
        b = beat()
        b["records"] = [record(), record(receipt="20261015000414")]
        first = merge(triage(), b, now=NOW)
        self.assertEqual(first["beatWideDartAdded"], 2)
        regenerated = triage()
        regenerated["seen"] = first["seen"].copy()
        # Main triage builder intentionally carries seen state, but rebuilds
        # the display arrays from its own narrower source feeds.
        second = merge(regenerated, b, now=NOW)
        self.assertEqual(second["beatWideDartAdded"], 2)
        self.assertEqual(second["freshOfficialReviewCount"], 1)
        self.assertEqual(second["backgroundReferenceCount"], 1)
        self.assertEqual(second["backgroundReference"][0]["id"],
                         "DART_FILING:20261015000414")
        self.assertEqual(merge(second, b, now=NOW)["beatWideDartAdded"], 0)

    def test_same_filing_from_contract_feed_is_not_repeated(self):
        q = triage()
        q["freshOfficialReview"] = [
            {"id": "DART_FILING:20261016800823", "officialDate": "2026-10-16"}]
        self.assertEqual(merge(q, beat(), now=NOW)["beatWideDartAdded"], 0)

    def test_old_first_discovery_is_background(self):
        b = beat()
        b["records"] = [record(receipt="20260930000001")]
        out = merge(triage(), b, now=NOW)
        self.assertEqual(out["freshOfficialReviewCount"], 0)
        self.assertEqual(out["backgroundReferenceCount"], 1)
        self.assertFalse(out["backgroundReference"][0]["officialDateInRecentWindow"])

    def test_correction_unknown_company_and_spoofed_url_fail_closed(self):
        b = beat()
        b["records"] = [record(correction=True), record(company="가짜회사")]
        fake = record(receipt="20261016800824")
        fake["sourceUrl"] = "https://dart.fss.or.kr.attacker.test/?rcpNo=20261016800824"
        b["records"].append(fake)
        out = merge(triage(), b, now=NOW)
        self.assertEqual(out["beatWideDartExcluded"], 3)
        self.assertEqual(out["beatWideDartAdded"], 0)

    def test_stale_and_source_error_not_clean_zero(self):
        b = beat()
        b["generatedAt"] = "2026-10-16T09:00:00+09:00"
        out = merge(triage(), b, now=NOW)
        self.assertEqual(out["feedHealth"][-1]["status"], "snapshot_older_than_24h")
        b = beat()
        b["sourceChecks"][1]["status"] = "source_error"
        b["companiesCodeVerified"] = 44
        b["companiesWithSourceErrors"] = 1
        out = merge(triage(), b, now=NOW)
        self.assertEqual(out["feedHealth"][-1]["status"], "partial_collection")
        self.assertFalse(out["sourceCompletenessVerified"])

    def test_original_document_stage_preserves_kg_attachment_gap(self):
        b = beat()
        b["records"][0]["valueupPrimarySource"] = {
            "officialXmlOrHtmlBodyRetrieved": True,
            "officialAttachmentPdfReviewed": False,
            "priorPressCoverageFulltextReviewed": False}
        out = merge(triage(), b, now=NOW)
        item = out["freshOfficialReview"][0]
        self.assertEqual(item["originalEvidenceStage"],
                         "official_valueup_text_only_attachment_unverified")
        self.assertFalse(item["priorMediaCoverageVerified"])
        self.assertFalse(item["exclusiveConfirmed"])
        self.assertFalse(item["approvedForPitch"])

    def test_oci_parent_and_subsidiary_filing_not_two_verified_closures(self):
        b=beat()
        b["sourceChecks"][0]["company"]="OCI"
        b["sourceChecks"][1]["company"]="OCI홀딩스"
        direct=record(receipt="20260929000097",company="OCI")
        direct.update(corpCode="00111111",
            report="주요사항보고서(영업정지)",
            status="official_business_cessation_document_review",
            businessCessationFilingRelation="issuer_business_cessation")
        parent=record(receipt="20260929800197",company="OCI홀딩스")
        parent.update(corpCode="00122222",
            report="주요사항보고서(영업정지)(자회사의 주요경영사항)",
            status="official_business_cessation_document_review",
            businessCessationFilingRelation="parent_disclosure_of_subsidiary")
        evidence={
            "officialXmlOrHtmlBodyRetrieved":True,
            "observedTerms":{
                "issuerReportedRevenueRatioPct":{
                    "value":"5.87","basis":"same_official_table_row",
                    "operationalShutdownVerified":False,
                    "independentBusinessEffectVerified":False},
                "issuerStatedCessationDate":{
                    "value":"2026-12-18","basis":"same_official_table_row",
                    "operationalShutdownVerified":False,
                    "independentBusinessEffectVerified":False}}}
        direct["businessCessationPrimarySource"]=evidence
        parent["businessCessationPrimarySource"]=evidence
        direct["possibleSameUnderlyingCessationEvent"]=True
        direct["possibleOverlappingCessationReceipt"]=parent["receiptNo"]
        direct["underlyingCessationEventIndependentlyVerified"]=False
        parent["possibleSameUnderlyingCessationEvent"]=True
        parent["possibleOverlappingCessationReceipt"]=direct["receiptNo"]
        parent["underlyingCessationEventIndependentlyVerified"]=False
        b["records"]=[direct,parent]
        out=merge(triage(),b,now=NOW)
        self.assertEqual(out["beatWideDartAdded"],2)
        self.assertEqual(out["freshOfficialReviewCount"],0)
        self.assertEqual(out["backgroundReferenceCount"],2)
        self.assertEqual(out["confirmedScoops"],0)
        records={x["company"]:x for x in out["backgroundReference"]}
        self.assertEqual(records["OCI"]["originalEvidenceStage"],
                         "official_business_cessation_fields_checked")
        self.assertEqual(records["OCI"]["issuerFiledBusinessCessationTerms"],
                         {"issuerReportedRevenueRatioPct":"5.87",
                          "issuerStatedCessationDate":"2026-12-18"})
        self.assertEqual(records["OCI홀딩스"]["businessCessationFilingRelation"],
                         "parent_disclosure_of_subsidiary")
        self.assertFalse(records["OCI홀딩스"]["uniqueUnderlyingCessationEventVerified"])
        self.assertTrue(records["OCI홀딩스"]["possibleSameUnderlyingCessationEvent"])
        self.assertEqual(records["OCI홀딩스"]["possibleOverlappingCessationReceipt"],"20260929000097")
        self.assertFalse(records["OCI홀딩스"]["underlyingCessationEventIndependentlyVerified"])
        self.assertFalse(records["OCI홀딩스"]["uniqueUnderlyingCessationEventVerified"])
        self.assertFalse(records["OCI홀딩스"]["companyImpactVerified"])
        self.assertFalse(records["OCI홀딩스"]["approvedForPitch"])
        self.assertFalse(records["OCI"]["exclusiveConfirmed"])

    def test_unsupported_cessation_source_does_not_invent_figures(self):
        b=beat()
        b["records"][0].update(
            status="business_cessation_document_unavailable",
            report="주요사항보고서(영업정지)",
            businessCessationPrimarySource={
                "officialXmlOrHtmlBodyRetrieved":False})
        out=merge(triage(),b,now=NOW)
        item=out["freshOfficialReview"][0]
        self.assertNotIn("issuerFiledBusinessCessationTerms",item)
        self.assertEqual(item["originalEvidenceStage"],
                         "official_receipt_only_original_not_checked")
        self.assertFalse(item["exclusiveConfirmed"])

    def test_share_cancellation_official_terms_are_not_actual_execution(self):
        b = beat()
        row = record(receipt="20261015800723")
        row["report"] = "주식소각결정"
        row["status"] = "official_share_cancellation_document_review"
        row["shareCancellationPrimarySource"] = {
            "officialXmlOrHtmlBodyRetrieved": True,
            "observedTerms": {
                "preferredSharesToCancel": {
                    "value": "678", "basis": "same_official_table_row",
                    "completedCancellationVerified": False},
                "scheduledCancellationDate": {
                    "value": "2026-10-22", "basis": "same_official_table_row",
                    "completedCancellationVerified": False}}}
        b["records"] = [row]
        out = merge(triage(), b, now=NOW)
        self.assertEqual(out["beatWideDartAdded"], 1)
        item = out["backgroundReference"][0]
        self.assertEqual(item["originalEvidenceStage"],
                         "official_share_cancellation_fields_checked")
        self.assertEqual(item["issuerFiledCancellationTerms"],
                         {"preferredSharesToCancel": "678",
                          "scheduledCancellationDate": "2026-10-22"})
        self.assertFalse(item["exclusiveConfirmed"])
        self.assertFalse(item["approvedForPitch"])
        self.assertFalse(item["companyImpactVerified"])
        self.assertIn("완료",item["officialFact"])

    def test_share_cancellation_unverified_cells_not_exported(self):
        b = beat()
        row = record(receipt="20261015800723")
        row["report"] = "주식소각결정"
        row["status"] = "official_share_cancellation_document_review"
        row["shareCancellationPrimarySource"] = {
            "officialXmlOrHtmlBodyRetrieved": True,
            "observedTerms": {
                "preferredSharesToCancel": {
                    "value": "678", "basis": "press_story",
                    "completedCancellationVerified": False}}}
        b["records"] = [row]
        out = merge(triage(), b, now=NOW)
        item = out["backgroundReference"][0]
        self.assertNotIn("issuerFiledCancellationTerms", item)
        self.assertFalse(item["exclusiveConfirmed"])

    def test_official_table_fields_are_not_verified_shipments(self):
        b = beat()
        b["records"][0]["status"] = "official_document_read"
        b["records"][0]["observedFields"] = {"contract_amount": "116,810,902,865"}
        out = merge(triage(), b, now=NOW)
        item = out["freshOfficialReview"][0]
        self.assertEqual(item["originalEvidenceStage"],
                         "official_table_filing_fields_checked")
        self.assertTrue(item["originalDocumentFieldsVerified"])
        self.assertFalse(item["companyImpactVerified"])
        self.assertFalse(item["contractTermsVerified"])

    def test_malformed_snapshot_not_zero_results(self):
        b = beat()
        b["companiesCodeVerified"] = 44
        out = merge(triage(), b, now=NOW)
        self.assertEqual(out["beatWideDartAdded"], 0)
        self.assertEqual(out["feedHealth"][-1]["status"], "source_missing_or_malformed")
        self.assertIsNone(out["feedHealth"][-1]["records"])


if __name__ == "__main__":
    unittest.main()
