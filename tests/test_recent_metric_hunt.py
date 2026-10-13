import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import recent_metric_hunt as m
def dataset():
 def table(value,unit="백만원",row="부산"):
  return {"topic":"productionCapacity","unit":unit,
          "rows":[["사업장","제품","2026/2025","전년","전전년"],
                  [row,"초고압변압기","{:,.0f}".format(value),"100,000","90,000"]]}
 def report(year,n,data,period="06"):
  return {"status":"evidence_found","period":period,"year":year,"receiptNo":n,"tables":[table(data)]}
 return {"generatedAt":"2026-10-13T14:00:00+09:00","businessYear":2026,
   "companies":[{"company":"LS일렉트릭","status":"official_sections_retrieved",
       "priorSamePeriod":report(2025,"20250814003228",228651),
       "current":report(2026,"20260814003228",484052)}]}
class Tests(unittest.TestCase):
 def test_exact_same_row_period_and_unit_delta(self):
  v=m.evaluate(dataset())
  self.assertEqual(v["checkedCompanies"],1)
  self.assertEqual(v["officialChanges"],1)
  self.assertEqual(v["items"][0]["diff"],"255401")
  self.assertFalse(v["scoopConfirmed"])
  self.assertIn("미확인",v["items"][0]["reportingStatus"])
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
 def test_non_numeric_or_currency_hidden_rejected(self):
  d=dataset();d["companies"][0]["current"]["tables"][0]["rows"][1][2]="1식"
  self.assertEqual(m.evaluate(d)["officialChanges"],0)
 def test_source_mismatch_rejected(self):
  d=dataset();d["companies"][0]["priorSamePeriod"]["receiptNo"]="bad"
  self.assertEqual(m.evaluate(d)["checkedCompanies"],0)
if __name__=="__main__":unittest.main()
