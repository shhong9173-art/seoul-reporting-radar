import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import recent_metric_hunt as m
def dataset():
 # 당기·전기(연간)·전전기(연간) — 두 보고서가 함께 적은 해(2024)의 숫자는 같다
 def table(value,prior,third,unit="백만원",row="부산"):
  return {"topic":"productionCapacity","unit":unit,
          "rows":[["사업장","제품","2026/2025","전년","전전년"],
                  [row,"초고압변압기","{:,.0f}".format(value),prior,third]]}
 def report(year,n,data,prior,third,period="06"):
  return {"status":"evidence_found","period":period,"year":year,"receiptNo":n,"tables":[table(data,prior,third)]}
 return {"generatedAt":"2026-10-13T14:00:00+09:00","businessYear":2026,
   "companies":[{"company":"LS일렉트릭","status":"official_sections_retrieved",
       "priorSamePeriod":report(2025,"20250814003228",228651,"100,000","90,000"),
       "current":report(2026,"20260814003228",484052,"300,000","100,000")}]}
class Tests(unittest.TestCase):
 def test_exact_same_row_period_and_unit_delta(self):
  v=m.evaluate(dataset())
  self.assertEqual(v["checkedCompanies"],1)
  self.assertEqual(v["officialChanges"],1)
  self.assertEqual(v["items"][0]["diff"],"255401")
  self.assertFalse(v["scoopConfirmed"])
  self.assertIn("미확인",v["items"][0]["reportingStatus"])
 def test_row_redefined_between_filings_is_not_a_change(self):
  # 11-23 금호타이어 '아시아' 587,796→46,639(-92.1%): 중국 줄이 아시아에서 떨어져 나간 것뿐 — 두 보고서의 같은 2024년 숫자가
  # 784,278과 45,886으로 달랐다(2025 보고서: 당기·2024·2023, 2026 보고서: 당기·2025·2024)
  d=dataset()
  row=lambda v,p,t:{"topic":"segmentSales","unit":"백만원","rows":[["구분","지역","당기","전기","전전기"],["타이어","아시아",v,p,t]]}
  d["companies"][0]["priorSamePeriod"]["tables"]=[row("587,796","784,278","672,595")]
  d["companies"][0]["current"]["tables"]=[row("46,639","60,876","45,886")]
  v=m.evaluate(d)
  self.assertEqual(v["officialChanges"],0)
  self.assertEqual([(x["company"],x["rowIdentity"]) for x in v["basisChanged"]],[("LS일렉트릭",["타이어","아시아"])])
  self.assertEqual(v["coverage"][0]["basisChanged"],1)
  # 같은 기간 1년 전 숫자를 둘째 칸에 적는 표(당기·전년 동기·전기)도 맞으면 그대로 센다
  d["companies"][0]["priorSamePeriod"]["tables"]=[row("587,796","500,000","784,278")]
  d["companies"][0]["current"]["tables"]=[row("646,390","587,796","800,000")]
  self.assertEqual(m.evaluate(d)["officialChanges"],1)
 def test_mismatch_period_is_not_comparable(self):
  d=dataset();d["companies"][0]["priorSamePeriod"]["period"]="03"
  self.assertEqual(m.evaluate(d)["officialChanges"],0)
 def test_mismatch_unit_no_false_change(self):
  d=dataset();d["companies"][0]["current"]["tables"][0]["unit"]="대"
  self.assertEqual(m.evaluate(d)["officialChanges"],0)
 def test_same_row_generic_with_duplicate_discarded(self):
  d=dataset();row=d["companies"][0]["current"]["tables"][0]["rows"][1]
  d["companies"][0]["current"]["tables"][0]["rows"].append(row)
  self.assertEqual(m.evaluate(d)["officialChanges"],0)
 def test_generic_subtotal_without_company_product_identity_rejected(self):
  d=dataset()
  for era in ("current","priorSamePeriod"):
   d["companies"][0][era]["tables"][0]["rows"][1]=["소계","228,651","100,000","90,000"]
  self.assertEqual(m.evaluate(d)["officialChanges"],0)

 def test_non_numeric_or_currency_hidden_rejected(self):
  d=dataset();d["companies"][0]["current"]["tables"][0]["rows"][1][2]="1식"
  self.assertEqual(m.evaluate(d)["officialChanges"],0)
 def test_source_mismatch_rejected(self):
  d=dataset();d["companies"][0]["priorSamePeriod"]["receiptNo"]="bad"
  self.assertEqual(m.evaluate(d)["checkedCompanies"],0)
if __name__=="__main__":unittest.main()
