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
  for name in ('KIAH COMPANY','XKIA','NOKIAN'):
   d['features'][0]['attributes']['FAC_NAME']=name
   self.assertEqual(e.parse(d,'기아')['items'],[])
  d['features'][0]['attributes']['FAC_NAME']='KIA GEORGIA, INC.'
  self.assertEqual(len(e.parse(d,'기아')['items']),1)
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
  self.assertIsNone(a["candidateCount"])
  self.assertEqual(a['observedCandidateCount'],0)
  self.assertEqual(a["checks"][0]["status"],"source_error")
 def test_failed_main_keeps_prior_evidence_and_writes_health(self):
  import tempfile,json
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as td:
   dest=Path(td)/'evidence.json';health=Path(td)/'health.json'
   dest.write_text('{"prior":true}')
   failed=e.evaluate(lambda u:(_ for _ in ()).throw(ValueError('offline')),NOW)
   with patch.object(e,'evaluate',return_value=failed),patch.object(sys,'argv',['epa','--out',str(dest),'--health',str(health)]):
    with self.assertRaises(SystemExit):e.main()
   self.assertEqual(json.loads(dest.read_text()),{'prior':True})
   self.assertIsNone(json.loads(health.read_text())['candidateCount'])
class PaginationTests(unittest.TestCase):
 def fetcher(self,mode='ok'):
  from urllib.parse import urlparse,parse_qs
  calls=[]
  def fetch(url):
   q=parse_qs(urlparse(url).query);calls.append(q)
   if 'returnIdsOnly' in q:
    return {'objectIdFieldName':'OBJECTID','objectIds':list(range(1,102)) if mode!='budget' else list(range(1001))}
   if 'objectIds' not in q:return {'features':[], 'exceededTransferLimit':True}
   ids=list(map(int,q['objectIds'][0].split(',')))
   if mode=='missing':ids=ids[:-1]
   if mode=='duplicate':ids[-1]=ids[0]
   if mode=='unexpected':ids[-1]=9999
   if mode=='fail':raise ValueError('offline')
   return {'features':[{'attributes':{'OBJECTID':i,'REGISTRY_ID':str(110000000000+i),
                        'FAC_NAME':'KIA GEORGIA' if i==101 else 'NOKIAN TIRES'}} for i in ids]}
  return fetch,calls
 def test_recovers_match_after_first_fifty_and_excludes_nokian(self):
  fetch,calls=self.fetcher()
  payload=e.collect('KIA',fetch)
  result=e.parse(payload,'기아')
  self.assertEqual(payload['matchedIds'],101)
  self.assertEqual(payload['unqueriedIds'],0)
  self.assertEqual(len(calls),5)
  self.assertEqual(result['count'],101)
  self.assertEqual(len(result['items']),1)
 def test_incomplete_duplicate_unexpected_and_failed_batches_fail_closed(self):
  for mode in ('missing','duplicate','unexpected','fail'):
   with self.subTest(mode=mode):
    fetch,_=self.fetcher(mode)
    with self.assertRaises(ValueError):e.collect('KIA',fetch)
 def test_request_budget_stops_before_batches_and_reports_scope(self):
  fetch,calls=self.fetcher('budget')
  payload=e.collect('KIA',fetch)
  self.assertEqual(len(calls),2)
  self.assertEqual(payload['unqueriedIds'],1001)
  self.assertEqual(e.parse(payload,'기아')['status'],'truncated_not_exhaustive')
 def test_invalid_manifest_not_zero(self):
  for ids in (None,[True],[1,1],['1']):
   with self.subTest(ids=ids):
    def fetch(url):
     if 'returnIdsOnly' in url:return {'objectIds':ids,'objectIdFieldName':'OBJECTID'}
     return {'exceededTransferLimit':True}
    with self.assertRaises(ValueError):e.collect('KIA',fetch)
if __name__=="__main__":unittest.main()
