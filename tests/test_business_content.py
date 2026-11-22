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

    def test_embedded_sub_heading_after_footnote(self):
        # 11-23: 엘에스일렉트릭 3분기보고서(20261116002011) — '주) 작성기준 … 라. 생산실적 및 가동률(1) 생산실적'이 한 줄로 붙어
        # 생산실적 표(청주2 1,475,594)가 앞 생산능력 제목 그대로 '생산능력'으로 읽혔다(radar_stats에 청주2 생산능력이 두 줄)
        def tbl(v):
            return f'<TABLE><TR><TH>사업장</TH><TH>주요제품</TH><TH>제53기 3분기</TH></TR><TR><TD>청주2</TD><TD>배전반</TD><TD>{v}</TD></TR></TABLE>'
        def run(between, tail='<P>[LS ELECTRIC] (단위 : 백만원)</P>'):
            body = ('<SECTION-1><TITLE>II. 사업의 내용</TITLE><P>다. 생산능력</P><P>[LS ELECTRIC] (단위 : 백만원)</P>' + tbl('1,635,398')
                    + between + tail + tbl('1,475,594') + '</SECTION-1>')
            return [(e["topic"], e["rows"][-1][-1]) for e in bc.evidence_tables(bc.business_section(body), A)]
        want = [("productionCapacity", "1,635,398"), ("productionActual", "1,475,594")]
        self.assertEqual(run('<P>주) 작성기준 : 월제작 가능 생산시설 라. 생산실적 및 가동률(1) 생산실적</P>'), want)
        self.assertEqual(run('<P>라. 생산실적 및 가동률(1) 생산실적</P>'), want)          # 큰 제목·작은 제목이 한 줄(예전엔 표를 버림)
        self.assertEqual(run('<P>라. 생산실적 및 가동률</P><P>(1) 생산실적</P>'), want)    # 줄이 나뉜 예전 꼴 그대로
        # 주석 글 속 낱말(산출 근거의 '생산실적/회수율')·긴 글 뒤 표지는 제목이 아니다 — 다음 회사 생산능력 표는 그대로
        prose = run('<P>주2) 각 사업장별 생산능력의 산출 근거는 하기와 같습니다. - 양산(청주 1, 천안) : 생산실적/회수율 [LS메탈] (단위 : 백만원)</P>', tail='')
        self.assertEqual([t for t, _ in prose], ["productionCapacity", "productionCapacity"])
        long_ = run('<P>주) (1) 생산실적은 투입공수 기준으로 단순 계산한 금액이며 회수율을 반영하였습니다</P>')
        self.assertEqual([t for t, _ in long_], ["productionCapacity", "productionCapacity"])
        self.assertEqual(bc.EXTRACTION_VERSION, "heading-scope-v3")   # 판을 올려 저장된 발췌를 다시 받는다

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

    def test_new_direct_beats_are_in_scope(self):
        self.assertTrue({"현대자동차","기아","현대제철","세아제강"}.issubset(set(bc.CORPS)))
        self.assertNotIn("포스코퓨처엠",bc.CORPS)

    def test_unrelated_company_never_filled_in(self):
        r=bc.build_report({"삼성전기":{"corp_code":"00126371"}},"key",2025,names=("HD현대일렉트릭",))
        self.assertEqual(r["companies"][0]["status"],"corp_code_unavailable")


if __name__=="__main__":
    unittest.main()
