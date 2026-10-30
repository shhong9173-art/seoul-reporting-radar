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
  with self.assertRaises(ValueError):p.build("fake-key",get=fake,now=NOW,sleep=lambda s:None)
 def test_connection_error_is_retried_once_but_a_refusal_is_not(self):
  # 10-30 운영: 공사 목록이 URLError로 한 번 실패해 그날 상태 source_error
  from urllib.error import URLError
  calls=[];waits=[]
  def flaky(uri):
   calls.append(uri)
   if "Cnstwk" in uri and sum("Cnstwk" in c for c in calls)==1:raise URLError("timed out")
   return make()
  out=p.build("fake-key",get=flaky,now=NOW,sleep=waits.append)
  self.assertEqual([c["status"] for c in out["checks"]],["checked","checked"])
  self.assertEqual(waits,[p.RETRY_WAIT])
  def down(uri):
   if "Cnstwk" in uri:raise URLError("timed out")
   return make()
  with self.assertRaises(p.ProviderCallsFailed) as ctx:p.build("fake-key",get=down,now=NOW,sleep=lambda s:None)
  self.assertEqual(ctx.exception.checks[-1]["errorType"],"URLError")
  refusals=[]
  def refused(uri):
   refusals.append(uri);raise p.ProviderError("HTTP 403")
  with self.assertRaises(p.ProviderCallsFailed):p.build("fake-key",get=refused,now=NOW,sleep=lambda s:None)
  self.assertEqual(len(refusals),2)  # 물품·공사 한 번씩만(거절은 다시 부르지 않음)
 def test_window_ends_before_run_time_not_midnight(self):
  seen=[]
  def fake(uri):
   seen.append(uri);return make()
  out=p.build("fake-key",get=fake,now=NOW)
  self.assertEqual(out["to"],"202610131455")
  self.assertIn("inqryEndDt=202610131455",seen[0])
 def test_total_changing_mid_pagination_restarts_once(self):
  calls={"n":0}
  def fake(uri):
   calls["n"]+=1
   if "Cnstwk" in uri:return make()
   # 1차: 1쪽 total 150 → 2쪽 total 151(새 공고) → 처음부터 다시: 150, 150
   totals=[150,151,150,150]
   total=totals[min(calls["n"]-1,3)]
   return make(total=total) if calls["n"] in (1,3) else {"response":{"header":{"resultCode":"00"},"body":{"totalCount":total,"items":[
     {"bidNtceNo":f"R26BK00{i:06d}","bidNtceOrd":"000","bidNtceNm":"사무용품","bidNtceDtlUrl":"https://www.g2b.go.kr/"} for i in range(149)]}}}
  out=p.build("fake-key",get=fake,now=NOW)
  goods=[c for c in out["checks"] if c["workType"]=="goods"][0]
  self.assertTrue(goods["restarted"])
  self.assertEqual(goods["total"],150)
 def test_more_than_1000_rows_fit_in_20_pages(self):
  page={"response":{"header":{"resultCode":"00"},"body":{"totalCount":1500,"items":[
    {"bidNtceNo":f"R26BK00{i:06d}","bidNtceOrd":"000","bidNtceNm":"사무용품"} for i in range(100)]}}}
  rows,check=p.query("goods","fake","202610130000","202610131455",get=lambda _:page)
  self.assertEqual(check["pages"],15)
 def test_failure_records_fixed_message_and_honest_note(self):
  def fake(uri):
   return {"response":{"header":{"resultCode":"00"},"body":{"totalCount":5000,"items":[
     {"bidNtceNo":f"R26BK00{i:06d}","bidNtceOrd":"000","bidNtceNm":"사무용품"} for i in range(100)]}}}
  with self.assertRaises(p.ProviderCallsFailed) as ctx:p.build("fake-key",get=fake,now=NOW)
  checks=ctx.exception.checks
  self.assertEqual(checks[0]["errorMessage"],"Official result truncated by pagination cap")
  note=p.failure_note({"providerChecks":checks})
  self.assertIn("not a key-permission signal",note)
  self.assertIn("refused the key",p.failure_note({"providerChecks":[{"providerMessage":"HTTP 403 30 등록되지 않은 서비스키"}]}))
 def test_success_status_does_not_carry_failure_note(self):
  import os,tempfile
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as d:
   out=os.path.join(d,"t.json");st=os.path.join(d,"s.json")
   with patch.dict(os.environ,{"G2B_API_KEY":"fake-key"}),patch.object(p,"build",lambda key,previous=None:{"checks":[{},{}]}),\
        patch.object(sys,"argv",["x","--out",out,"--status",st]):
    p.main()
   status=json.loads(Path(st).read_text(encoding="utf-8"))
  self.assertEqual(status["status"],"checked")
  self.assertNotIn("permission",status["note"])
if __name__=="__main__":unittest.main()
