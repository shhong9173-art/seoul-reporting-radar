import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from dart_beat_monitor import mark_possible_parent_subsidiary_cessation_overlap

VALUES = {
    "reportedBusinessScope":"TDI 제조 및 판매 사업",
    "reportedAffectedSalesWon":"117947181460",
    "reportedRecentSalesWon":"2009429144163",
    "issuerReportedRevenueRatioPct":"5.87",
    "issuerStatedCessationDate":"2026-12-18",
}


def filing(parent=False, ratio="5.87", receipt=None):
    no=receipt or ("20260929800197" if parent else "20260929000097")
    terms={name:{
        "value":ratio if name=="issuerReportedRevenueRatioPct" else value,
        "basis":"same_official_table_row",
        "operationalShutdownVerified":False,
        "independentBusinessEffectVerified":False}
        for name,value in VALUES.items()}
    return {
        "company":"OCI홀딩스" if parent else "OCI",
        "corpCode":"00122222" if parent else "00111111",
        "receiptNo":no,"published":no[:8],
        "report":("주요사항보고서(영업정지)(자회사의 주요경영사항)"
                  if parent else "주요사항보고서(영업정지)"),
        "category":"정기·주요공시",
        "isCorrection":False,"sourceType":"official_list_receipt",
        "sourceUrl":"https://dart.fss.or.kr/dsaf001/main.do?rcpNo="+no,
        "status":"official_business_cessation_document_review",
        "sourceError":False,
        "businessCessationFilingRelation":(
            "parent_disclosure_of_subsidiary"
            if parent else "issuer_business_cessation"),
        "businessCessationPrimarySource":{
            "officialXmlOrHtmlBodyRetrieved":True,
            "observedTerms":terms,
            "operationalShutdownVerified":False},
        "scoopConfirmed":False, "approvedForPitch":False,
    }


class SuspectedOfficialCessationOverlap(unittest.TestCase):
    def test_exact_original_terms_are_review_pair_not_unique_event_proof(self):
        parent, direct=filing(True),filing()
        pairs=mark_possible_parent_subsidiary_cessation_overlap([parent,direct])
        self.assertEqual(len(pairs),1)
        p=pairs[0]
        self.assertEqual(p["parentReceiptNo"],"20260929800197")
        self.assertEqual(p["issuerReceiptNo"],"20260929000097")
        self.assertEqual(p["filingDate"],"20260929")
        self.assertEqual(len(p["identicalOfficialFields"]),5)
        self.assertFalse(p["parentSubsidiaryLegalIdentityIndependentlyVerified"])
        self.assertFalse(p["actualBusinessClosureIndependentlyVerified"])
        self.assertFalse(p["twoSeparateBusinessEventsVerified"])
        self.assertFalse(p["scoopConfirmed"])
        self.assertEqual(parent["possibleOverlappingCessationReceipt"],
                         direct["receiptNo"])
        self.assertTrue(parent["possibleSameUnderlyingCessationEvent"])
        self.assertFalse(parent["underlyingCessationEventIndependentlyVerified"])
        self.assertFalse(direct["underlyingCessationEventIndependentlyVerified"])

    def test_conflicting_official_percentage_prevents_false_link(self):
        parent,direct=filing(True,ratio="5.87"),filing(False,ratio="6.25")
        self.assertEqual(mark_possible_parent_subsidiary_cessation_overlap(
            [parent,direct]),[])
        self.assertNotIn("possibleOverlappingCessationReceipt",parent)

    def test_ambiguous_multiple_matching_issuers_are_withheld(self):
        parent,direct=filing(True),filing()
        third=filing(False,receipt="20260929000098")
        third.update(company="미확인 별도 상장사",corpCode="00333333")
        group=[parent,direct,third]
        self.assertEqual(mark_possible_parent_subsidiary_cessation_overlap(group),[])
        self.assertTrue(all("possibleOverlappingCessationReceipt" not in x for x in group))

    def test_previously_seen_pair_cleared_after_corrected_source_or_outage(self):
        parent,direct=filing(True),filing()
        self.assertEqual(len(mark_possible_parent_subsidiary_cessation_overlap(
            [parent,direct])),1)
        parent["businessCessationPrimarySource"]["observedTerms"][
            "reportedAffectedSalesWon"]["value"]="changed"
        self.assertEqual(mark_possible_parent_subsidiary_cessation_overlap(
            [parent,direct]),[])
        self.assertFalse("possibleOverlappingCessationReceipt" in direct)
        self.assertFalse("possibleSameUnderlyingCessationEvent" in parent)

    def test_incomplete_primary_source_never_matches_news_text(self):
        parent,direct=filing(True),filing()
        parent["businessCessationPrimarySource"]["observedTerms"].pop(
            "issuerStatedCessationDate")
        self.assertEqual(mark_possible_parent_subsidiary_cessation_overlap(
            [parent,direct]),[])
        parent=filing(True)
        parent["sourceError"]=True
        self.assertEqual(mark_possible_parent_subsidiary_cessation_overlap(
            [parent,direct]),[])

    def test_no_pair_for_two_direct_issuer_disclosures(self):
        a,b=filing(),filing(receipt="20260929000098")
        b.update(company="제삼 법인",corpCode="00555555")
        self.assertEqual(mark_possible_parent_subsidiary_cessation_overlap(
            [a,b]),[])


if __name__=="__main__":
    unittest.main()
