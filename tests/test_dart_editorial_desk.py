import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import dart_editorial_desk as desk
NOW=None
def setup(unit="백만원",topic="productionCapacity"):
 src={"generatedAt":"2026-10-13T15:19:54+09:00"}
 delta={"generatedAt":"2026-10-13T15:25:00+09:00",
 "sourceGeneratedAt":src["generatedAt"],"items":[
 {"company":"엘에스일렉트릭","topic":topic,"unit":unit,"rowIdentity":["부산","변압기"],
  "percentChange":111.7,"priorValue":"228651","currentValue":"484052",
  "sourceUrls":["https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20250814001952",
                "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260814003088"],
  "period":"06","fromYear":2025,"toYear":2026}],"coverage":[],"checkedCompanies":7}
 return src,delta
class Desk(unittest.TestCase):
 def test_money_is_not_production_volume(self):
  output=desk.evaluate(*setup())
  row=output["shortlist"][0]
  self.assertIn("금액",row["pitchBullets"][1])
  self.assertEqual(len(row["pitchBullets"]),3)
  self.assertFalse(row["scoopConfirmed"])
  self.assertFalse(row["publicationApproved"])
  self.assertEqual(output["confirmedScoops"],0)
 def test_quantity_requires_company_explanation(self):
  row=desk.evaluate(*setup("톤","productionActual"))["shortlist"][0]
  self.assertEqual(row["unitInterpretation"],"reported_quantity_unit")
  self.assertIn("원인은 미확인",row["pitchBullets"][1])
 def test_source_mismatch_fails(self):
  a,b=setup();b["sourceGeneratedAt"]="2026-10-12"
  with self.assertRaises(ValueError):desk.evaluate(a,b)
 def test_unverified_document_url_excluded(self):
  a,b=setup();b["items"][0]["sourceUrls"][0]="https://example.com"
  self.assertEqual(len(desk.evaluate(a,b)["shortlist"]),0)
 def test_company_diversity_and_invalid_period(self):
  a,b=setup();second=dict(b["items"][0]);second["rowIdentity"]=["울산","차단기"];second["percentChange"]=40
  b["items"].append(second)
  self.assertEqual(len(desk.evaluate(a,b)["shortlist"]),1)
  second["company"]="기아";second["period"]="02"
  self.assertEqual(len(desk.evaluate(a,b)["shortlist"]),1)
if __name__=="__main__":unittest.main()
