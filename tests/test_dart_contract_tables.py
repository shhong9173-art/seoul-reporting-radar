"""DART public XML contract fields: merge cells, explicit label identity, no guessing."""
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import dart_contract_tables as t
from dart_lineage import tabular_fields,comparable_differences

class ContractTableSourceTests(unittest.TestCase):
    def test_official_three_columns_with_decorative_rowspan(self):
        doc="""
        <DOCUMENT><BODY><SECTION-1>
        <TABLE border="1">
          <TR><TD rowspan="4">2. 계약내역</TD>
              <TD><P>계약금액(원)</P></TD><TD><P>125,000,000,000</P></TD></TR>
          <TR><TD>최근매출액(원)</TD><TD>200,000,000,000</TD></TR>
          <TR><TD>매출액대비(%)</TD><TD>62.5</TD></TR>
          <TR><TD>계약상대</TD><TD><P>글로벌 전력망 운영사</P></TD></TR>
        </TABLE>
        </SECTION-1></BODY></DOCUMENT>"""
        r=t.extract_contract_terms([doc])
        self.assertEqual(r["fields"]["contract_amount"],"125,000,000,000")
        self.assertEqual(r["fields"]["counterparty"],"글로벌 전력망 운영사")
        self.assertNotIn("recent_sales",r["fields"])
        self.assertEqual(r["fieldEvidence"]["contract_amount"]["rowPattern"],
                         "three_cell_explicit_label")
        self.assertFalse(r["fieldEvidence"]["contract_amount"]["independentBusinessVerification"])
        self.assertEqual(r["status"],"official_table_terms_not_business_effect")

    def test_korean_real_world_contract_period_rowspan(self):
        html="""
        <TABLE><TR><TD rowspan="2">계약기간</TD><TD>시작일</TD>
          <TD><P>2026-10-01</P></TD></TR>
          <TR><TD>종료일</TD><TD>2027.12.31</TD></TR>
        </TABLE>"""
        result=t.extract_contract_terms([html])
        self.assertEqual(result["fields"]["contract_start"],"2026-10-01")
        self.assertEqual(result["fields"]["contract_end"],"2027.12.31")

    def test_standalone_start_end_without_contract_period_context_rejected(self):
        html="<TABLE><TR><TD>시작일</TD><TD>2026-10-01</TD></TR><TR><TD>종료일</TD><TD>2027-10-01</TD></TR></TABLE>"
        self.assertEqual(t.extract_contract_terms([html])["fields"],{})

    def test_explicit_sibling_pairs_and_numeric_validation(self):
        html="""
        <TABLE><TR><TD>계약금액(원)</TD><TD>12,500,000,000</TD>
        <TD>계약상대방</TD><TD>한국전력공사</TD></TR>
        <TR><TD>계약기간시작일</TD><TD>20261001</TD></TR>
        <TR><TD>계약기간종료일</TD><TD>2028년 3월 31일</TD></TR></TABLE>
        """
        vals=t.tabular_fields([html]) if hasattr(t,"tabular_fields") else t.extract_contract_terms([html])["fields"]
        self.assertEqual(vals["contract_amount"],"12,500,000,000")
        self.assertEqual(vals["counterparty"],"한국전력공사")
        self.assertEqual(vals["contract_start"],"20261001")
        self.assertEqual(vals["contract_end"],"2028년 3월 31일")

    def test_unsupported_or_wrong_unit_and_redaction_never_shown(self):
        html="""
        <TABLE><TR><TD>계약금액(원)</TD><TD>USD 12,500,000</TD></TR>
        <TR><TD>계약상대방</TD><TD>영업비밀로 비공개</TD></TR>
        <TR><TD>계약기간시작일</TD><TD>2026-22-99</TD></TR>
        <TR><TD>최근매출액(원)</TD><TD>19,000,000,000</TD></TR>
        </TABLE>"""
        self.assertEqual(t.extract_contract_terms([html])["fields"],{})

    def test_nested_tables_cannot_fake_parent_fields(self):
        html="""
        <TABLE><TR><TD>계약금액(원)</TD><TD><TABLE><TR>
          <TD>임의 사업명</TD><TD>120,000,000,000</TD>
        </TR></TABLE></TD></TR></TABLE>"""
        self.assertNotIn("contract_amount",t.extract_contract_terms([html])["fields"])

    def test_multiple_distinct_values_are_ambiguous_not_first_match(self):
        html="""
        <TABLE><TR><TD>계약금액(원)</TD><TD>120,000,000</TD></TR>
        <TR><TD>계약금액(원)</TD><TD>130,000,000</TD></TR></TABLE>"""
        r=t.extract_contract_terms([html])
        self.assertNotIn("contract_amount",r["fields"])
        self.assertEqual(r["conflictingFields"],["contract_amount"])

    def test_repeated_identical_value_is_consistent(self):
        doc="<TABLE><TR><TD>계약금액(원)</TD><TD>1,000,000</TD></TR></TABLE>"
        r=t.extract_contract_terms([doc,doc])
        self.assertEqual(r["fields"]["contract_amount"],"1,000,000")
        self.assertEqual(r["fieldEvidence"]["contract_amount"]["distinctDocumentRows"],2)

    def test_correction_before_after_table_does_not_create_current_contract_amount(self):
        html="""
        <TABLE>
          <TR><TH>정정항목</TH><TH>정정전</TH><TH>정정후</TH></TR>
          <TR><TD>계약금액(원)</TD><TD>100,000,000</TD><TD>200,000,000</TD></TR>
        </TABLE>"""
        self.assertEqual(t.extract_contract_terms([html])["fields"],{})

    def test_pairing_of_original_and_amended_documents_keeps_comparison_safe(self):
        old="<TABLE><TR><TD>계약금액(원)</TD><TD>10,000,000</TD><TD>계약상대방</TD><TD>한국전력공사</TD></TR></TABLE>"
        new="<TABLE><TR><TD>계약금액(원)</TD><TD>12,000,000</TD><TD>계약상대방</TD><TD>한국전력공사</TD></TR></TABLE>"
        before=tabular_fields([old]);after=tabular_fields([new])
        changes=comparable_differences(before,after)
        self.assertEqual(changes,[{
            "field":"contract_amount","before":"10,000,000","after":"12,000,000",
            "basis":"independent_primary_documents","numericDelta":None,
            "needsCompanyConfirmation":True}])

    def test_unrecognized_arbitrary_text_not_promoted(self):
        html="<TABLE><TR><TD>금액</TD><TD>9,999,999</TD></TR><TR><TD>공급처</TD><TD>추정 회사</TD></TR></TABLE>"
        self.assertEqual(t.extract_contract_terms([html])["fields"],{})

if __name__=="__main__":unittest.main()
