import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import dart_collector as d

class Tests(unittest.TestCase):
 def test_narrow_refresh_retains_extended_beat_and_evidence(self):
  with tempfile.TemporaryDirectory() as td,patch.object(d,'CORP_CACHE',str(Path(td)/'codes.json')):
   p=Path(d.CORP_CACHE)
   old={'한국GM':{'corp_code':'00426873','identityEvidence':{'verifiedAt':'2026-10-16'}},'기아':{'corp_code':'00106641','stock_code':'000270'}}
   p.write_text(json.dumps({'companies':old,'source':'official'}))
   d._write_corp_cache({'기아':{'corp_code':'00106641','stock_code':''}})
   saved=json.loads(p.read_text())
   self.assertEqual(saved['companies'],old)
   self.assertEqual(saved['source'],'official')
 def test_conflicting_mapping_not_silently_overwritten(self):
  with tempfile.TemporaryDirectory() as td,patch.object(d,'CORP_CACHE',str(Path(td)/'codes.json')),patch.object(d,'CORP_CODE_ERRORS',[]):
   p=Path(d.CORP_CACHE);p.write_text(json.dumps({'companies':{'기아':{'corp_code':'00106641'}}}))
   result=d._write_corp_cache({'기아':{'corp_code':'99999999'}})
   self.assertEqual(result['기아']['corp_code'],'00106641')
   self.assertTrue(d.CORP_CODE_ERRORS)
 def test_corrupt_registry_preserved_not_reset(self):
  with tempfile.TemporaryDirectory() as td,patch.object(d,'CORP_CACHE',str(Path(td)/'codes.json')):
   p=Path(d.CORP_CACHE);p.write_text('invalid prior')
   with self.assertRaises(ValueError):d._write_corp_cache({'기아':{'corp_code':'00106641'}})
   self.assertEqual(p.read_text(),'invalid prior')
 def test_replace_failure_preserves_previous_json(self):
  with tempfile.TemporaryDirectory() as td,patch.object(d,'CORP_CACHE',str(Path(td)/'codes.json')):
   p=Path(d.CORP_CACHE);p.write_text('{"companies":{}}')
   with patch.object(Path,'replace',side_effect=OSError()):
    with self.assertRaises(ValueError):d._write_corp_cache({'기아':{'corp_code':'00106641'}})
   self.assertEqual(p.read_text(),'{"companies":{}}')
 def test_production_coverage_ids_survive_limited_collector_refresh(self):
  coverage_path=Path('digests/dart_corp_code_coverage_latest.json')
  if not coverage_path.exists():self.skipTest('production snapshot checked in CI')
  coverage=json.loads(coverage_path.read_text())
  data=json.loads(Path('dart_corp_codes.json').read_text())
  verified=[r for r in coverage['companies'] if r['status']=='resolved_unique_official_legal_name' or (r['status']=='existing_code_verified_in_official_registry' and r['company'] not in d.TARGET_NAMES)]
  self.assertTrue(verified)
  for row in verified:
   data['companies'].setdefault(row['company'],{'corp_code':row['corpCode'],'stock_code':''})
   self.assertEqual(data['companies'][row['company']]['corp_code'],row['corpCode'])
  with tempfile.TemporaryDirectory() as td,patch.object(d,'CORP_CACHE',str(Path(td)/'codes.json')):
   Path(d.CORP_CACHE).write_text(json.dumps(data))
   narrow={k:v for k,v in data['companies'].items() if k in d.TARGET_NAMES}
   result=d._write_corp_cache(narrow)
   self.assertEqual(result,data['companies'])
   print('Operational identity replay:',len(data['companies']),'preserved;',len(verified),'restored verified IDs')
if __name__=='__main__':unittest.main()
