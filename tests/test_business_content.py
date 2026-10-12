import io
import sys
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import business_content as bc

CORP="01205851"
A="20260318000001"
B="20250318000002"


def markup(value="125,000",unit="억원",section="II. 사업의 내용",name="수주잔고"):
    return (f'<SECTION-1><TITLE>{section}</TITLE><P>4. 매출 및 수주상황</P>'
            f'<P>나. {name} (단위: {unit})</P>'
            f'<TABLE><TR><TH>구분</TH><TH>{name}</TH></TR>'
            f'<TR><TD>변압기</TD><TD>{value}</TD></TR></TABLE></SECTION-1>'
            '<SECTION-1><TITLE>III. 재무에 관한 사항</TITLE>'
            '<TABLE><TR><TD>수주잔고</TD><TD>9999999</TD></TR></TABLE></SECTION-1>')


class ContentTests(unittest.TestCase):
    def test_business_scope_is_explicit_only(self):
        s=bc.business_section(markup())
        self.assertIn("125,000",s)
        self.assertNotIn("9999999",s)
        self.assertIsNone(bc.business_section(markup(section="I. 회사의 개요")))

    def test_table_units_and_source_rows(self):
        rows=bc.evidence_tables(bc.business_section(markup()),A)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["topic"],"orderBacklog")
        self.assertEqual(rows[0]["unit"],"억원")
        self.assertEqual(rows[0]["rows"][0][1],"125,000")

    def test_compare_only_same_topic_single_table_unit(self):
        old=bc.evidence_tables(bc.business_section(markup(value="100,000")),B)
        new=bc.evidence_tables(bc.business_section(markup(value="125,000")),A)
        pairs=bc.cross_year_pairs(old,new)
        self.assertEqual(len(pairs),1)
        self.assertIsNone(pairs[0]["numericChange"])
        self.assertTrue(pairs[0]["needsManualVerification"])
        self.assertNotEqual(pairs[0]["before"]["receiptNo"],pairs[0]["after"]["receiptNo"])

    def test_changed_unit_never_pairs(self):
        old=bc.evidence_tables(bc.business_section(markup(unit="백만원")),B)
        new=bc.evidence_tables(bc.business_section(markup(unit="억원")),A)
        self.assertEqual(bc.cross_year_pairs(old,new),[])

    def test_no_explicit_unit_never_pairs(self):
        old=bc.evidence_tables(bc.business_section(markup(unit="회")),B)
        new=bc.evidence_tables(bc.business_section(markup(unit="회")),A)
        self.assertEqual(bc.cross_year_pairs(old,new),[])

    def test_annual_report_issuer_year_exact(self):
        def official(_):
            return {"status":"000","total_page":1,"list":[
                {"corp_code":CORP,"report_nm":"사업보고서 (2025.12)","rcept_no":A,"rcept_dt":"20260318"},
                {"corp_code":"00164742","report_nm":"사업보고서 (2025.12)","rcept_no":"20260318000456","rcept_dt":"20260318"},
                {"corp_code":CORP,"report_nm":"반기보고서 (2025.06)","rcept_no":"20260814000001","rcept_dt":"20260814"}]}
        found=bc.annual_receipt("fake",CORP,2025,fetch=official)
        self.assertEqual(found["receiptNo"],A)

    def test_no_annual_does_not_fall_back_to_quarter(self):
        outcome=bc.annual_receipt("fake",CORP,2025,fetch=lambda _:{
            "status":"000","total_page":1,"list":[
                {"corp_code":CORP,"report_nm":"반기보고서 (2025.06)","rcept_no":A}]})
        self.assertEqual(outcome["status"],"no_matching_report")

    def test_multi_page_list_does_not_select_incomplete(self):
        with self.assertRaises(ValueError):
            bc.annual_receipt("fake",CORP,2025,fetch=lambda _:{"status":"000","total_page":2,"list":[]})

    def test_api_error_not_silently_zero(self):
        with self.assertRaises(RuntimeError):
            bc.annual_receipt("fake",CORP,2025,fetch=lambda _:{"status":"800"})

    def test_bad_document_zip_rejected(self):
        with self.assertRaises(RuntimeError):
            bc.fetch_report("fake",A,fetch=lambda _:b'{"status":"800"}')

    def test_zip_document_extracts_scope(self):
        memory=io.BytesIO()
        with zipfile.ZipFile(memory,"w",zipfile.ZIP_DEFLATED) as out:
            out.writestr("20260318000001.xml",markup())
        response=bc.fetch_report("fake",A,fetch=lambda _:memory.getvalue())
        self.assertEqual(response["status"],"found")
        self.assertIn("사업의 내용",response["section"])

    def test_scan_status_keeps_missing_source(self):
        def files(key,code,year):
            return {"status":"no_matching_report"} if year==2024 else {
                "status":"found","receiptNo":A,"url":"https://dart.fss.or.kr/dsaf001/main.do?rcpNo="+A}
        got=bc.scan_company("HD현대일렉트릭",CORP,2025,"fake",list_fetch=files,
                            doc_fetch=lambda key,receipt:{"status":"found","document":"x.xml",
                                                         "section":bc.business_section(markup())})
        self.assertEqual(got["periods"]["2024"]["status"],"no_matching_report")
        self.assertEqual(got["pairs"],[])
        self.assertEqual(got["status"],"insufficient_comparable_evidence")

    def test_successful_company_but_no_automatic_scoop(self):
        def scan(name,corp,year,key):
            return {"company":name,"status":"source_pairs_to_review","periods":{},
                    "pairs":[{"topic":"orderBacklog","numericChange":None}]}
        r=bc.build_report({"HD현대일렉트릭":{"corp_code":CORP}},
                          "key",2025,names=("HD현대일렉트릭",),scan=scan)
        self.assertEqual(r["candidatePairs"],1)
        self.assertEqual(r["verifiedNumericChanges"],0)
        self.assertIn("단독 판단 불가",r["scoopStatus"])

    def test_unrelated_company_never_filled_in(self):
        r=bc.build_report({"삼성전기":{"corp_code":"00126371"}},"key",2025,names=("HD현대일렉트릭",))
        self.assertEqual(r["companies"][0]["status"],"corp_code_unavailable")


if __name__=="__main__":
    unittest.main()
