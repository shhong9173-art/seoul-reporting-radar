import json,sys,unittest
def json_dump(x):return json.dumps(x,ensure_ascii=False)
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
 def test_key_resolution_prefers_dedicated_and_never_returns_value_as_source(self):
  self.assertEqual(p.resolve_key({"G2B_API_KEY":" a ","DATA_GO_KR_SHARED_KEY":"b"}),("a","G2B_API_KEY"))
  key,source=p.resolve_key({"G2B_API_KEY":"","DATA_GO_KR_SHARED_KEY":"shared-secret"})
  self.assertEqual(key,"shared-secret")
  self.assertNotIn("shared-secret",source)
  self.assertEqual(p.resolve_key({}),("",None))
 def test_encoding_key_is_decoded_once(self):
  self.assertEqual(p.normalize_key("abc%2Bdef%3D%3D"),("abc+def==","url_encoded_input_decoded"))
  self.assertEqual(p.normalize_key("abc+def=="),("abc+def==","decoded"))
 def test_gateway_xml_refusal_keeps_code_not_zero(self):
  xml=("<OpenAPI_ServiceResponse><cmmMsgHeader><errMsg>SERVICE ERROR</errMsg>"
       "<returnAuthMsg>SERVICE_KEY_IS_NOT_REGISTERED_ERROR</returnAuthMsg>"
       "<returnReasonCode>30</returnReasonCode></cmmMsgHeader></OpenAPI_ServiceResponse>")
  self.assertEqual(p.provider_message(xml),"30 SERVICE_KEY_IS_NOT_REGISTERED_ERROR")
  def refused(url):raise p.ProviderError("gateway 30 SERVICE_KEY_IS_NOT_REGISTERED_ERROR")
  with self.assertRaises(p.ProviderCallsFailed) as ctx:
   p.build("k",get=refused,now=datetime(2026,10,26,9,tzinfo=timezone(timedelta(hours=9))))
  self.assertTrue(all(c["status"]=="source_error" for c in ctx.exception.checks))
  self.assertIn("SERVICE_KEY_IS_NOT_REGISTERED_ERROR",ctx.exception.checks[0]["providerMessage"])
  self.assertNotIn("serviceKey",json_dump(ctx.exception.checks))
 def test_json_gateway_refusal_keeps_code(self):
  body=json.dumps({"OpenAPI_ServiceResponse":{"cmmMsgHeader":{"errMsg":"SERVICE ERROR",
        "returnAuthMsg":"SERVICE_KEY_IS_NOT_REGISTERED_ERROR","returnReasonCode":"30"}}})
  self.assertEqual(p.provider_message(body),"30 SERVICE_KEY_IS_NOT_REGISTERED_ERROR")
 def test_provider_result_code_is_reported(self):
  with self.assertRaises(p.ProviderError) as ctx:
   p.parse_result({"response":{"header":{"resultCode":"12","resultMsg":"NO_OPENAPI_SERVICE_ERROR"}}})
  self.assertIn("12 NO_OPENAPI_SERVICE_ERROR",str(ctx.exception))
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
