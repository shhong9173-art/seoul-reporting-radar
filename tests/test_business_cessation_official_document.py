import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from business_cessation_official_document import (
    business_cessation_filing, business_cessation_document_evidence,
    literal_business_cessation_terms)

DIRECT = {
    "company": "OCI", "corpCode": "00111111",
    "receiptNo": "20260929000097", "published": "20260929",
    "report": "주요사항보고서(영업정지)", "isCorrection": False,
    "sourceType": "official_list_receipt",
    "sourceUrl": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260929000097",
    "scoopConfirmed": False,
}
PARENT = {
    **DIRECT, "company": "OCI홀딩스", "corpCode": "00122222",
    "receiptNo": "20260929800197",
    "report": "주요사항보고서(영업정지)(자회사의 주요경영사항)",
    "sourceUrl": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260929800197",
}
DOC = """
<html><table>
<tr><td>1. 영업정지 분야</td><td>TDI 제조 및 판매 사업</td></tr>
<tr><td rowspan="3">2. 영업정지 내역</td>
<td>영업정지금액(원)</td><td>117,947,181,460</td></tr>
<tr><td>최근매출총액(원)</td><td>2,009,429,144,163</td></tr>
<tr><td>매출액대비(%)</td><td>5.87</td></tr>
<tr><td>7. 영업정지일자</td><td>2026년 12월 18일</td></tr>
</table></html>
"""


class CessationProof(unittest.TestCase):
    def test_exact_oci_issuer_source_fields_only(self):
        self.assertTrue(business_cessation_filing(DIRECT))
        requested = []
        def documents(key, receipt):
            requested.append(receipt)
            return [DOC]
        output = business_cessation_document_evidence(
            DIRECT, "key", documents=documents)
        self.assertEqual(requested, ["20260929000097"])
        self.assertEqual(output["status"],
                         "official_business_cessation_document_review")
        evidence = output["businessCessationPrimarySource"]
        fields = evidence["observedTerms"]
        self.assertEqual(fields["reportedBusinessScope"]["value"],
                         "TDI 제조 및 판매 사업")
        self.assertEqual(fields["reportedAffectedSalesWon"]["value"],
                         "117947181460")
        self.assertEqual(fields["reportedRecentSalesWon"]["value"],
                         "2009429144163")
        self.assertEqual(fields["issuerReportedRevenueRatioPct"]["value"],
                         "5.87")
        self.assertEqual(fields["issuerStatedCessationDate"]["value"],
                         "2026-12-18")
        self.assertTrue(evidence["officialXmlOrHtmlBodyRetrieved"])
        self.assertFalse(evidence["operationalShutdownVerified"])
        self.assertFalse(evidence["independentFinancialImpactVerified"])
        self.assertFalse(evidence["priorMediaFulltextCompared"])
        self.assertFalse(output["companyImpactVerified"])
        self.assertFalse(output["approvedForPitch"])

    def test_parent_and_subsidiary_are_two_receipts_not_two_events(self):
        self.assertTrue(business_cessation_filing(PARENT))
        self.assertEqual(business_cessation_document_evidence(
            PARENT, "key", documents=lambda *_: [DOC])[
            "businessCessationFilingRelation"],
            "parent_disclosure_of_subsidiary")
        self.assertEqual(business_cessation_document_evidence(
            DIRECT, "key", documents=lambda *_: [DOC])[
            "businessCessationFilingRelation"],
            "issuer_business_cessation")
        evidence = literal_business_cessation_terms([DOC])
        self.assertFalse(evidence["subsidiaryIdentityIndependentlyLinked"])
        self.assertFalse(evidence["duplicateUnderlyingEventExcludedFromUniqueCount"])

    def test_wrong_issuer_and_forged_host_fails(self):
        variants = [
            {"corpCode": "invalid"},
            {"published": "20260928"},
            {"sourceUrl": "https://dart.fss.or.kr.attacker.example/dsaf001/main.do?rcpNo=20260929000097"},
            {"sourceUrl": "http://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260929000097"},
            {"report": "[기재정정]주요사항보고서(영업정지)"},
            {"report": "매매거래정지및정지해제(중요내용공시) (영업정지)"},
            {"isCorrection": True},
            {"sourceType": "press_summary"},
        ]
        for v in variants:
            self.assertFalse(business_cessation_filing({**DIRECT, **v}), msg=str(v))
        with self.assertRaises(ValueError):
            business_cessation_document_evidence(
                {**DIRECT, "sourceType": "news"}, "key")

    def test_adjacent_cells_not_scraped_across_rows(self):
        doc = """<table>
        <tr><td>최근매출총액(원)</td><td>해당 없음</td></tr>
        <tr><td>다른 사업 금액</td><td>2,009,429,144,163</td></tr>
        <tr><td>영업정지금액</td><td>117,947,181,460</td></tr>
        </table>"""
        fields = literal_business_cessation_terms([doc])["observedTerms"]
        self.assertEqual(fields, {})

    def test_conflicting_values_discarded_not_averaged(self):
        doc = """<table>
        <tr><td>매출액대비(%)</td><td>5.87</td></tr>
        <tr><td>매출액대비(%)</td><td>6.25</td></tr>
        <tr><td>7. 영업정지일자</td><td>2026.12.18</td></tr>
        </table>"""
        out = literal_business_cessation_terms([doc])
        self.assertEqual(out["conflictingFields"], ["issuerReportedRevenueRatioPct"])
        self.assertNotIn("issuerReportedRevenueRatioPct", out["observedTerms"])
        self.assertEqual(out["observedTerms"]["issuerStatedCessationDate"]["value"],
                         "2026-12-18")

    def test_invalid_date_not_an_actual_operational_shutdown(self):
        invalid = """<tr><td>영업정지예정일</td><td>2026년 2월 31일</td></tr>"""
        out = literal_business_cessation_terms([invalid])
        self.assertNotIn("issuerStatedCessationDate", out["observedTerms"])
        self.assertFalse(out["operationalShutdownVerified"])

    def test_source_failure_explicit_not_zero_affected_sales(self):
        def broken(*args):
            raise RuntimeError("provider_offline")
        r = business_cessation_document_evidence(DIRECT, "key", documents=broken)
        self.assertEqual(r["status"], "business_cessation_document_unavailable")
        self.assertTrue(r["sourceError"])
        self.assertNotIn("observedTerms", r["businessCessationPrimarySource"])
        self.assertFalse(r["scoopConfirmed"])

    def test_outsize_and_missing_documents_fail_closed(self):
        with self.assertRaises(ValueError):
            literal_business_cessation_terms([])
        with self.assertRaises(ValueError):
            literal_business_cessation_terms(["x" * 2_000_001])


if __name__ == "__main__":
    unittest.main()
