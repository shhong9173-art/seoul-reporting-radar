import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import industry_official_hunt as h
import nhtsa_public_watch as n
class Sources(unittest.TestCase):
 def test_official_dart_deltas_and_missing_provider_are_distinct(self):
  out=h.build([("DART",{"generatedAt":"2026-10-13","investigations":[{"company":"현대제철","projects":[{"project":"신규 철강설비","originalUrls":["https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260316000000","https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260814000000"]}]}]},"investigations"),("CUSTOMS",{},"items")])
  self.assertEqual(out["feeds"][0]["status"],"ready")
  self.assertEqual(out["feeds"][1]["status"],"missing")
  self.assertIsNone(out["feeds"][1]["rows"])
  self.assertEqual(len(out["leads"]),1)
  self.assertEqual(out["confirmedScoops"],0)
 def test_nhtsa_public_us_recalls_not_scoops(self):
  def fake(url):
   return {"results":[{"NHTSACampaignNumber":"26V100000"}]} if "/recalls/" in url else {"results":[{"odiNumber":"12345678"}]}
  a=n.collect(fetch=fake)
  self.assertEqual(len(a["checks"]),8)
  self.assertFalse(a["scoopConfirmed"])
  self.assertTrue(all(x["alreadyPublic"] for x in a["records"]))
 def test_nhtsa_source_partial_errors(self):
  def fake(uri):
   if "complaints" in uri:raise OSError("offline")
   return {"results":[]}
  a=n.collect(fetch=fake)
  self.assertEqual(sum(x["status"]=="source_error" for x in a["checks"]),4)
 def test_nhtsa_all_failure_does_not_overwrite(self):
  with self.assertRaises(ValueError):n.collect(fetch=lambda uri:(_ for _ in ()).throw(OSError("offline")))
if __name__=="__main__":unittest.main()
