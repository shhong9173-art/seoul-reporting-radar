import unittest,sys
from datetime import datetime,timezone,timedelta
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import epa_echo_facilities as e
NOW=datetime(2026,10,13,tzinfo=timezone(timedelta(hours=9)))
class Tests(unittest.TestCase):
 def test_registered_facility_not_new_permit_or_proven_owner(self):
  d={"features":[{"attributes":{"REGISTRY_ID":"110045611798","FAC_NAME":"HYUNDAI MOTOR ALABAMA",
     "FAC_STATE":"AL","FAC_CITY":"Montgomery","CAA_PERMIT_TYPES":"TITLE V",
     "FAC_ACTIVE_FLAG":"Y","FAC_CURR_COMPLIANCE_STATUS":"UNKNOWN"}}]}
  a=e.parse(d,"현대자동차")
  self.assertEqual(a["status"],"checked")
  self.assertEqual(len(a["items"]),1)
  self.assertFalse(a["items"][0]["permitIssuedVerified"])
  self.assertFalse(a["items"][0]["companyLegalOwnershipVerified"])
  self.assertFalse(a["items"][0]["newConstructionVerified"])
 def test_provider_limit_is_not_exhaustive_zero(self):
  d={"features":[{"attributes":{"REGISTRY_ID":"110045611798","FAC_NAME":"KIA FOO"}}],
      "exceededTransferLimit":True}
  r=e.parse(d,"기아")
  self.assertEqual(r["status"],"truncated_not_exhaustive")
  self.assertEqual(r["items"],[])
 def test_false_short_alias_not_matched(self):
  d={"features":[{"attributes":{"REGISTRY_ID":"110045611798","FAC_NAME":"NOKIAN TIRES"}}]}
  self.assertEqual(e.parse(d,"기아")["items"],[])
 def test_reject_missing_features_and_unsupported_name(self):
  with self.assertRaises(ValueError):e.parse({"count":0},"기아")
  with self.assertRaises(ValueError):e.query_url("COMPANY NOT VALID")
 def test_same_registry_deduplicated_not_same_owner_certified(self):
  def fetch(url):return {"features":[{"attributes":{
   "REGISTRY_ID":"110045611798","FAC_NAME":"HYUNDAI MOTOR"}}]}
  a=e.evaluate(fetch,NOW)
  self.assertEqual(a["sourceComplete"],True)
  self.assertEqual(a["candidateCount"],1)
  self.assertEqual(a["verifiedNewPermits"],0)
 def test_failed_provider_not_no_facilities(self):
  def fetch(url):raise ValueError("provider unavailable")
  a=e.evaluate(fetch,NOW)
  self.assertEqual(a["sourceComplete"],False)
  self.assertEqual(a["candidateCount"],0)
  self.assertEqual(a["checks"][0]["status"],"source_error")
if __name__=="__main__":unittest.main()
