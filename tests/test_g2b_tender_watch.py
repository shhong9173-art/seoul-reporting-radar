import sys,unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import g2b_tender_watch as p
NOW=datetime(2026,10,13,15,tzinfo=timezone(timedelta(hours=9)))
def make(title="초고압 변압기 장비 구매",total=1):
 return {"response":{"header":{"resultCode":"00"},
       "body":{"totalCount":total,"items":[{"bidNtceNo":"R26BK00123456",
          "bidNtceOrd":"000","bidNtceNm":title,"ntceInsttNm":"한국전력",
          "dminsttNm":"전력기관","bidNtceDtlUrl":"https://www.g2b.go.kr/"}]}}}
class Tender(unittest.TestCase):
 def test_official_notice_is_not_award(self):
  out=p.build("fake-key",get=lambda u:make(),now=NOW)
  self.assertEqual(len(out["checks"]),2)
  self.assertEqual(out["confirmedAwards"],0)
  self.assertEqual(out["confirmedContracts"],0)
  self.assertEqual(out["confirmedScoops"],0)
  self.assertEqual(len(out["notices"]),2)
  self.assertTrue(all(not x["namedSupplierVerified"] for x in out["notices"]))
 def test_no_results_are_valid_only_with_provider_zero(self):
  rows,checked=p.query("goods","fake","202610130000","202610132359",get=lambda _:{"response":{"header":{"resultCode":"00"},"body":{"items":[],"totalCount":0}}})
  self.assertEqual(rows,[])
  self.assertEqual(checked["total"],0)
 def test_no_results_when_positive_total_must_fail(self):
  with self.assertRaises(ValueError):
   p.query("goods","fake","202610130000","202610132359",
           get=lambda _:{"response":{"header":{"resultCode":"00"},"body":{"items":[],"totalCount":5}}})
 def test_page_cap_fail_closed(self):
  with self.assertRaisesRegex(ValueError,"truncated"):
   p.query("goods","fake","202610130000","202610132359",get=lambda _:make(total=200),max_pages=1)
 def test_permission_denied_is_not_zero(self):
  with self.assertRaises(ValueError):
   p.parse_result({"response":{"header":{"resultCode":"20"},"body":{"items":[],"totalCount":0}}})
 def test_irrelevant_and_spurious_urls(self):
  self.assertEqual(p.tags("회사 사무용 의자"),[])
  self.assertIn("grid",p.tags("HVDC 송전선 건설"))
  self.assertIsNone(p.official_link("https://example.com/tender"))
 def test_partial_provider_failure_not_publishable(self):
  def fake(uri):
   if "Cnstwk" in uri:raise OSError("provider failure")
   return make()
  with self.assertRaises(ValueError):p.build("fake-key",get=fake,now=NOW)
if __name__=="__main__":unittest.main()
