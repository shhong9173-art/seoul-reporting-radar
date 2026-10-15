"""Only issuer-stated material correction rows, never independent original proof."""
import sys
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import dart_lineage as lineage
import recent_contracts as capture
import dart_contract_followup as review

KST=timezone(timedelta(hours=9))
NOW=datetime(2026,10,15,17,16,tzinfo=KST)
CORP="00159616"
RECEIPT="20261014800697"
OLD_RECEIPT="20261001800690"
COMPANY="두산에너빌리티"

def fixture():
    return dict(company=COMPANY,corpCode=CORP,
        receiptNo=RECEIPT,published=RECEIPT[:8],
        category="공급계약",report="[기재정정]단일판매ㆍ공급계약체결",
        isCorrection=True,
        sourceUrl=lineage.source_link(RECEIPT))

def correction_document(include_formal=True,similar=False):
    suffix=('<TR><TD>증빙서류</TD><TD>구비</TD><TD>추가</TD></TR>'
            if include_formal else "")
    amount=("100,000,000" if not similar else "120,000,000")
    return """
      <HTML><BODY><TABLE>
      <TR><TH>정정항목</TH><TH>정정 전</TH><TH>정정 후</TH></TR>
      <TR><TD>2. 계약내역 - 계약금액(원)</TD>
          <TD>"""+amount+"""</TD><TD>120,000,000</TD></TR>
      <TR><TD>5. 계약기간</TD><TD>2027-01-31</TD>
          <TD>2028-03-31</TD></TR>
      """+suffix+"""
      </TABLE><TABLE>
      <TR><TD>정정대상 공시서류의 최초제출일</TD><TD>2026-10-01</TD></TR>
      </TABLE></BODY></HTML>"""

def fake_list(api_key,code,day):
    assert code==CORP and day=="20261001"
    return [{"rcept_no":OLD_RECEIPT,"corp_code":CORP,
             "report_nm":"[기재정정]단일판매ㆍ공급계약체결"}]

class IssuerOnlyCorrectionEvidence(unittest.TestCase):
    def test_amendment_table_can_be_read_without_original_receipt(self):
        reported=lineage.issuer_table_evidence(
            [correction_document()],lineage.source_link(RECEIPT))
        self.assertEqual(reported["status"],"issuer_table_material_changes_for_review")
        self.assertEqual(reported["totalMaterialRows"],2)
        self.assertEqual([x["category"] for x in reported["changes"]],
                         ["amount","contract_period"])
        self.assertFalse(reported["independentOriginalDocumentCompared"])
        self.assertTrue(all(x["commercialEffectVerified"] is False for x in reported["changes"]))

    def test_independently_unlinked_correction_still_preserves_issuer_only_rows(self):
        def docs(key,no):
            if no!=RECEIPT:raise AssertionError("Original must NOT be opened without ID")
            return [correction_document()]
        info=lineage.review_lineage(
            fixture(),{COMPANY:{"corp_code":CORP}},api_key="TEST",
            fetch_documents=docs,fetch_list=fake_list)
        self.assertFalse(info["originalDocumentVerified"])
        self.assertIsNone(info["originReceiptNo"])
        self.assertEqual(info["changes"],[])
        self.assertEqual(len(info["issuerCorrectionTable"]["changes"]),2)
        self.assertEqual(info["candidateOrigins"][0]["receiptNo"],OLD_RECEIPT)
        recorded=capture.document_evidence(fixture(),"TEST",
            lineage=lambda *args,**kwargs:info)
        self.assertEqual(recorded["status"],"original_not_verified")
        self.assertEqual(recorded["changes"],[])
        self.assertIsNone(recorded["originalReceiptNo"])
        reporter=review.review_one(recorded,now=NOW,search=False)
        self.assertEqual(reporter["comparisonStatus"],"original_unverified_no_comparison")
        self.assertEqual(reporter["materialFieldChanges"],[])
        self.assertEqual(len(reporter["issuerDeclaredMaterialChanges"]),2)
        self.assertEqual(reporter["revisionEditorialClass"],
                         "issuer_stated_change_recent_needs_original_and_press")
        self.assertFalse(reporter["priorCoverageOfSameContractVerified"])
        self.assertFalse(reporter["exclusiveConfirmed"])
        self.assertIn("원공시",reporter["nextChecks"][0])

    def test_formal_or_same_value_is_not_a_material_change(self):
        out=lineage.issuer_table_evidence(
            [correction_document(similar=True)],lineage.source_link(RECEIPT))
        self.assertEqual(len(out["changes"]),1)
        self.assertEqual(out["changes"][0]["category"],"contract_period")
        only_formal="<TABLE><TR><TD>정정항목</TD><TD>정정전</TD><TD>정정후</TD></TR><TR><TD>증빙서류</TD><TD>해당없음</TD><TD>추가</TD></TR></TABLE>"
        out=lineage.issuer_table_evidence([only_formal],lineage.source_link(RECEIPT))
        self.assertEqual(out["changes"],[])

    def test_conflicting_issuer_tables_discard_entire_field(self):
        doc=correction_document()
        second=doc.replace("100,000,000","200,000,000")
        out=lineage.issuer_table_evidence([doc,second],lineage.source_link(RECEIPT))
        self.assertEqual(out["conflictingFieldCount"],1)
        self.assertEqual(len(out["changes"]),1)
        self.assertEqual(out["changes"][0]["category"],"contract_period")

    def test_weak_provenance_cannot_be_smuggled_into_original_comparison(self):
        x=fixture()
        x.update(status="original_not_verified",changes=[
            {"field":"contract_amount","before":"100","after":"200",
             "basis":"issuer_reported_amendment_table_only"}
        ])
        r=review.review_one(x,now=NOW,search=False)
        self.assertEqual(r["materialFieldChanges"],[])
        self.assertIsNone(r["originalReceiptNo"])

    def test_fake_unofficial_url_or_unverified_source_flag_rejected(self):
        raw=lineage.issuer_table_evidence([correction_document()],
            lineage.source_link(RECEIPT))
        x=fixture()
        x.update(status="original_not_verified",issuerCorrectionTable=raw)
        raw["changes"][0]["amendedSourceUrl"]="https://example.test/evil"
        result=review.review_one(x,now=NOW,search=False)
        self.assertEqual(result["issuerDeclaredMaterialChanges"],[])
        self.assertEqual(result["issuerCorrectionTableStatus"],"issuer_table_invalid_evidence")

    def test_old_correction_never_becomes_recent_scoop(self):
        x=fixture()
        x["receiptNo"]="20261002800300"
        x["published"]="20261002"
        x["sourceUrl"]=lineage.source_link(x["receiptNo"])
        x["issuerCorrectionTable"]=lineage.issuer_table_evidence(
             [correction_document()],x["sourceUrl"])
        x["status"]="original_not_verified"
        r=review.review_one(x,now=NOW,search=False)
        self.assertEqual(r["revisionEditorialClass"],
                         "issuer_stated_change_historical_reference")
        self.assertFalse(r["officialPublishedWithinLast3Days"])
        self.assertFalse(r["exclusiveConfirmed"])

    def test_legacy_snapshot_without_data_means_unexamined_not_zero(self):
        row=fixture()
        row["status"]="original_not_verified"
        result=review.review_one(row,now=NOW,search=False)
        self.assertEqual(result["issuerCorrectionTableStatus"],"issuer_table_not_examined")
        self.assertEqual(result["issuerDeclaredMaterialChanges"],[])
        self.assertEqual(result["revisionEditorialClass"],
                         "no_supported_material_revision_observed")

if __name__=="__main__":unittest.main()
