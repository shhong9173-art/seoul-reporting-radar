"""Only same issuer/table/year/row/unit with carry-forward audit yields amounts."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import business_metric_compare as m
import business_content as source


def block(topic,header,rows,unit="백만원",context="(1) 주요 제품군별 매출실적 (단위 : 백만원)"):
    return {"topic":topic,"unit":unit,"rows":[header]+rows,"context":context}


def record(company,old,new,oldreceipt="20250320001309",newreceipt="20260316000940"):
    return {"company":company,"periods":{
        "2024":{"status":"evidence_found","receiptNo":oldreceipt,"tables":old},
        "2025":{"status":"evidence_found","receiptNo":newreceipt,"tables":new}}}


class VerifiedBusinessMetricTests(unittest.TestCase):
    def hd(self):
        old=block("segmentSales",["구분","제8기","제7기","제6기"],
                  [["전력기기","2,035,525","1,571,748","1,096,837"],
                   ["회전기기","537,227","486,814","404,798"]])
        new=block("segmentSales",["구분","제9기","제8기","제7기"],
                  [["전력기기","2,835,195","2,035,525","1,571,748"],
                   ["회전기기","588,664","537,227","486,814"]])
        return record("HD현대일렉트릭",[old],[new])

    def test_verified_hd_product_group_2024_vs_2025(self):
        found=m.compare_company(self.hd(),2024,2025)
        row=[x for x in found if x["rowIdentity"]==["전력기기"]][0]
        self.assertEqual(row["from"],"2035525")
        self.assertEqual(row["to"],"2835195")
        self.assertEqual(row["change"],"799670")
        self.assertTrue(row["carryForwardMatched"])
        self.assertIn("단독 아님",row["journalismStatus"])
        self.assertEqual(len(found),2)

    def test_restatement_rejected_even_when_delta_large(self):
        data=self.hd()
        data["periods"]["2025"]["tables"][0]["rows"][1][2]="2,040,000"
        remaining=m.compare_company(data,2024,2025)
        self.assertEqual([x["rowIdentity"] for x in remaining],[["회전기기"]])

    def test_mixed_units_rejected(self):
        data=self.hd()
        data["periods"]["2024"]["tables"][0]["context"]="단위: 백만원, 천RMB, 천USD"
        self.assertEqual(m.compare_company(data,2024,2025),[])

    def test_different_scope_blocks_pairing(self):
        data=self.hd()
        data["periods"]["2025"]["tables"][0]["context"]="(2) 매출유형별 매출실적 (단위: 백만원)"
        self.assertEqual(m.compare_company(data,2024,2025),[])

    def test_mismatched_company_business_row_blocked(self):
        data=self.hd()
        data["periods"]["2025"]["tables"][0]["rows"][1][0]="배전기기"
        found=m.compare_company(data,2024,2025)
        self.assertEqual(len(found),1)
        self.assertEqual(found[0]["rowIdentity"],["회전기기"])

    def test_colspan_shift_mismatch_rejected(self):
        data=self.hd()
        data["periods"]["2025"]["tables"][0]["rows"][1].insert(1,"사업장")
        found=m.compare_company(data,2024,2025)
        self.assertEqual(len(found),1)

    def test_generic_total_not_automatically_joined(self):
        data=self.hd()
        data["periods"]["2024"]["tables"][0]["rows"][1][0]="합 계"
        data["periods"]["2025"]["tables"][0]["rows"][1][0]="합 계"
        self.assertEqual(len(m.compare_company(data,2024,2025)),1)

    def test_no_scoop_claim_or_causal_inference(self):
        report=m.build({"reportYear":2025,"priorYear":2024,"generatedAt":"2026-10-13",
                        "companies":[self.hd()]})
        self.assertEqual(report["status"],"validated_filing_values_not_exclusives")
        self.assertEqual(report["findingCount"],2)
        self.assertEqual(report["findings"][0]["journalismStatus"].endswith("단독 아님"),True)

    def test_hyosung_explicit_annual_header_and_year_carry(self):
        old=block("productionCapacity",
                  ["사업부문","지배회사","주요제품","사업장",
                   "제7기(당기)(2024년 1~12월)","제6기(전기)(2023년 1~12월)","제5기(전전기)(2022년 1~12월)"],
                  [["중공업","효성중공업(주) 외","변압기·차단기","창원 등","2,540,371","2,179,863","1,939,318"]],
                  context="(4) 주요 제품 생산능력 (단위 : 백만원)")
        new=block("productionCapacity",
                  ["사업부문","지배회사","주요제품","사업장",
                   "제8기(당기)(2025년 1~12월)","제7기(전기)(2024년 1~12월)","제6기(전전기)(2023년 1~12월)"],
                  [["중공업","효성중공업(주) 외","변압기·차단기","창원 등","3,128,398","2,540,371","2,179,863"]],
                  context="(4) 주요 제품 생산능력 (단위 : 백만원)")
        found=m.compare_company(record("효성중공업",[old],[new]),2024,2025)
        self.assertEqual(len(found),1)
        self.assertEqual(found[0]["change"],"588027")

    def test_production_actual_mislabeled_as_capacity_is_not_compared(self):
        data=self.hd()
        for side in ("2024","2025"):
            t=data["periods"][side]["tables"][0]
            t["topic"]="productionCapacity"
            t["context"]="마. 생산실적 (단위 : 백만원)"
        self.assertEqual(m.compare_company(data,2024,2025),[])

    def test_wrong_period_header_no_numeric_claim(self):
        data=self.hd()
        data["periods"]["2025"]["tables"][0]["rows"][0]=["구분","제7기","제6기","제5기"]
        self.assertEqual(m.compare_company(data,2024,2025),[])

    def test_missing_filing_source_rejected(self):
        data=self.hd();data["periods"]["2024"]["receiptNo"]="bad"
        self.assertEqual(m.compare_company(data,2024,2025),[])

    def test_ambiguous_table_duplicate_rejected(self):
        data=self.hd()
        data["periods"]["2025"]["tables"].append(data["periods"]["2025"]["tables"][0])
        self.assertEqual(m.compare_company(data,2024,2025),[])

    def test_pure_table_unit_rejects_mixed_currency(self):
        self.assertIsNone(source.explicit_table_unit("다. 수주상황 (단위: 백만원, 천RMB, 천INR)", ""))
        self.assertIsNone(source.explicit_table_unit("다. 수주상황 (단위: 톤, 억원)", ""))
        self.assertEqual(source.explicit_table_unit("다. 수주상황 (단위: 백만원)", ""),"백만원")

    def test_nearest_section_title_prevents_wrong_topic(self):
        context="라. 생산능력의 산출근거 마. 생산실적 (단위: 백만원)"
        self.assertEqual(source.classify_table("<table></table>",context),"productionActual")
        self.assertEqual(source.classify_table("<table></table>","(4) 주요 제품 생산능력 (단위: 백만원)"),"productionCapacity")


if __name__=="__main__":
    unittest.main()
