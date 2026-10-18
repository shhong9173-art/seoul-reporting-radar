import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from share_cancellation_official_document import (
    cancellation_filing, cancellation_document_evidence, literal_cancellation_terms)


def kg():
    return {
        "company": "KG스틸", "corpCode": "00115676",
        "receiptNo": "20261015800723", "published": "20261015",
        "report": "주식소각결정", "isCorrection": False,
        "sourceType": "official_list_receipt",
        "sourceUrl": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261015800723",
        "scoopConfirmed": False,
    }


DOC = """
<html><table>
<tr><td>1. 소각할 주식의 종류와 수</td><td>보통주식</td><td>-</td>
<td>우선주식</td><td>678주</td></tr>
<tr><td>4. 소각예정일</td><td>2026-10-22</td></tr>
<tr><td>5. 발행주식총수</td><td>보통주식</td><td>100,000,000</td></tr>
</table></html>
"""


class ShareCancellationOriginalEvidence(unittest.TestCase):
    def test_exact_dart_receipt_and_original_table_proof(self):
        self.assertTrue(cancellation_filing(kg()))
        calls=[]
        def documented(key, receipt):
            calls.append((key,receipt))
            return [DOC]
        result=cancellation_document_evidence(kg(), "api-key", documents=documented)
        self.assertEqual(calls, [("api-key", "20261015800723")])
        self.assertEqual(result["status"], "official_share_cancellation_document_review")
        proof=result["shareCancellationPrimarySource"]
        self.assertEqual(proof["observedTerms"]["preferredSharesToCancel"]["value"], "678")
        self.assertEqual(proof["observedTerms"]["scheduledCancellationDate"]["value"], "2026-10-22")
        self.assertNotIn("ordinarySharesToCancel", proof["observedTerms"])
        self.assertTrue(proof["officialXmlOrHtmlBodyRetrieved"])
        self.assertFalse(proof["actualCancellationExecutedVerified"])
        self.assertFalse(proof["shareholderReturnNumeratorVerified"])
        self.assertFalse(result["companyImpactVerified"])
        self.assertFalse(result["scoopConfirmed"])

    def test_nonadjacent_stock_numbers_are_not_cancellation_quantities(self):
        doc="""<table><tr><td>발행주식총수</td><td>우선주식</td><td>678</td>
        </tr><tr><td>소각할 주식</td><td>보통주식</td><td>-</td></tr></table>"""
        found=literal_cancellation_terms([doc])
        self.assertNotIn("preferredSharesToCancel",found["observedTerms"])
        self.assertEqual(found["status"], "official_text_opened_fields_not_unambiguous")

    def test_conflicting_official_table_values_fail_closed(self):
        doc="""<table><tr><td>소각할 주식수</td><td>우선주식</td><td>678</td></tr>
        <tr><td>소각할 주식수</td><td>우선주식</td><td>987</td></tr></table>"""
        found=literal_cancellation_terms([doc])
        self.assertEqual(found["conflictingFields"],["preferredSharesToCancel"])
        self.assertNotIn("preferredSharesToCancel",found["observedTerms"])
        self.assertFalse(found["exclusiveConfirmed"])

    def test_invalid_date_does_not_create_planned_execution(self):
        found=literal_cancellation_terms(["<table><tr><td>소각예정일</td>"
            "<td>2026-02-31</td></tr></table>"])
        self.assertNotIn("scheduledCancellationDate",found["observedTerms"])
        self.assertFalse(found["actualCancellationExecutedVerified"])

    def test_issuer_receipt_and_url_fail_closed(self):
        for invalid in [
            {"corpCode": "00115675", "sourceType": "other"},
            {"sourceUrl": "https://dart.fss.or.kr.evil.example/?rcpNo=20261015800723"},
            {"sourceUrl": "http://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261015800723"},
            {"receiptNo": "20261015800724"},
            {"isCorrection": True},
            {"report": "[기재정정]주식소각결정"},
        ]:
            row={**kg(),**invalid}
            self.assertFalse(cancellation_filing(row),msg=str(invalid))
        with self.assertRaises(ValueError):
            cancellation_document_evidence({**kg(), "report":"다른공시"}, "api-key")

    def test_api_outage_is_not_equivalent_to_zero_share_count(self):
        def unavailable(key,receipt):
            raise ValueError("provider_returned_error")
        row=cancellation_document_evidence(kg(),"api-key",documents=unavailable)
        self.assertTrue(row["sourceError"])
        self.assertEqual(row["status"], "share_cancellation_document_unavailable")
        self.assertNotIn("observedTerms",row["shareCancellationPrimarySource"])
        self.assertFalse(row["scoopConfirmed"])

    def test_malformed_and_oversized_document_rejected(self):
        with self.assertRaises(ValueError):
            literal_cancellation_terms([])
        with self.assertRaises(ValueError):
            literal_cancellation_terms(["x" * 2_000_001])


if __name__ == "__main__":
    unittest.main()
