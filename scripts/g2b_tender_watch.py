"""Conservative public KONEPS bid notices; NO award/contract assertions.

PPS official API (data.go.kr dataset 15129394) requires explicit permission.
A response error, incomplete pagination, or missing key is NOT "zero tenders".
"""
from __future__ import annotations
import argparse,json,os,re
from datetime import datetime,timedelta,timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import unquote,urlencode,urlsplit
from urllib.request import Request,urlopen

KST=timezone(timedelta(hours=9))
BASE="https://apis.data.go.kr/1230000/ad/BidPublicInfoService"
OPERATIONS={"goods":"getBidPblancListInfoThng",
            "construction":"getBidPblancListInfoCnstwk"}
TECH={
 "transformer":("변압기","변전소","배전반"),
 "grid":("초고압","송전선","HVDC","GIS","전력망","전력케이블","전선"),
 "storage":("ESS","에너지저장장치"),
 "energy":("원자력발전","원전","수소연료전지","풍력발전"),
 "mobility":("전기버스","전기차충전","전기차 충전"),
}
NOTICE=re.compile(r"^[A-Za-z0-9-]{7,35}$")
class ProviderError(ValueError):
 """A provider/gateway refusal with its own code. Never carries the key or URL."""
GATEWAY=re.compile(r"<(returnReasonCode|returnAuthMsg|errMsg|resultCode|resultMsg)>\s*([^<]{1,120})<")
def provider_message(text):
 found={}
 for tag,value in GATEWAY.findall(text or ""):
  found.setdefault(tag,value.strip())
 if not found:
  # With type=json the gateway refusal is JSON: {"OpenAPI_ServiceResponse":{"cmmMsgHeader":{...}}}
  try:
   header=((json.loads(text) or {}).get("OpenAPI_ServiceResponse") or {}).get("cmmMsgHeader") or {}
  except (ValueError,AttributeError,TypeError):
   header={}
  for tag in ("returnReasonCode","returnAuthMsg","errMsg"):
   if isinstance(header,dict) and header.get(tag):found[tag]=str(header[tag]).strip()[:120]
 if not found:return None
 code=found.get("returnReasonCode") or found.get("resultCode") or "?"
 msg=found.get("returnAuthMsg") or found.get("resultMsg") or found.get("errMsg") or ""
 return f"{code} {msg}".strip()
def fetch(url):
 try:
  with urlopen(Request(url,headers={"Accept":"application/json","User-Agent":"official-industry-reporter/1.0"}),
               timeout=18) as r:
   raw=r.read(1_500_001)
 except HTTPError as e:
  body=e.read(4000).decode("utf-8","replace") if e.fp else ""
  raise ProviderError(f"HTTP {e.code} {provider_message(body) or ''}".strip()) from None
 if len(raw)>1_500_000:raise ValueError("Official response truncated")
 text=raw.decode("utf-8-sig","replace")
 try:
  payload=json.loads(text)
 except ValueError:
  # data.go.kr gateway refusals come back as XML even when type=json.
  raise ProviderError("gateway "+(provider_message(text) or "non-JSON response")) from None
 if isinstance(payload,dict) and "OpenAPI_ServiceResponse" in payload:
  raise ProviderError("gateway "+(provider_message(text) or "refusal"))
 return payload
def unpack(body):
 if not isinstance(body,dict):raise ValueError("Missing provider body")
 rows=body.get("items")
 if isinstance(rows,dict):rows=rows.get("item")
 if isinstance(rows,dict):rows=[rows]
 if rows in (None,""):rows=[]
 if not isinstance(rows,list):raise ValueError("Unexpected provider items structure")
 try:total=int(body.get("totalCount",0))
 except (ValueError,TypeError):raise ValueError("Provider totalCount invalid")
 if total<0:raise ValueError("Provider totalCount negative")
 return rows,total
def parse_result(payload):
 if not isinstance(payload,dict):raise ValueError("Invalid provider response")
 resp=payload.get("response")
 if not isinstance(resp,dict):raise ValueError("Missing response")
 header=resp.get("header") or {}
 if str(header.get("resultCode")) not in ("00","000"):
  raise ProviderError(f"provider {header.get('resultCode')} {str(header.get('resultMsg') or '')[:120]}".strip())
 return unpack(resp.get("body"))
def tags(title):
 val=str(title or "").lower()
 return [name for name,terms in TECH.items() if any(t.lower() in val for t in terms)]
def official_link(value):
 if not isinstance(value,str):return None
 p=urlsplit(value)
 if p.scheme!="https" or not p.hostname:return None
 if p.hostname.lower() not in ("www.g2b.go.kr","g2b.go.kr","www.g2b.nara.go.kr","g2b.nara.go.kr"):
  return None
 return value[:450]

# 일일 공고가 많은 날은 이틀 창이 1,000건을 넘는다(10-27 물품 921건). 상한 20쪽(2,000건), 하루 1회 실행.
def query(kind,key,start,end,get=fetch,max_pages=20,per_page=100):
 if kind not in OPERATIONS or not key:raise ValueError("Provider kind/key missing")
 if not re.fullmatch(r"20\d{10}",start) or not re.fullmatch(r"20\d{10}",end) or end<start:
  raise ValueError("Invalid 12-digit period")
 if not 1<=max_pages<=20:raise ValueError("Excessive provider pagination")
 collected=[];pages=0;count=None
 for page in range(1,max_pages+1):
  params={"serviceKey":key,"pageNo":page,"numOfRows":per_page,
          "type":"json","inqryDiv":"1","inqryBgnDt":start,"inqryEndDt":end}
  url=BASE+"/"+OPERATIONS[kind]+"?"+urlencode(params)
  rows,total=parse_result(get(url))
  if count is not None and total!=count:
   raise ValueError("Official totalCount changed mid-pagination")
  count=total;pages=page
  collected.extend(rows)
  if len(collected)>=total:break
  if not rows:raise ValueError("Provider pagination ended prematurely")
 if len(collected)<count:raise ValueError("Official result truncated by pagination cap")
 data=[]
 for row in collected:
  if not isinstance(row,dict):continue
  number=str(row.get("bidNtceNo") or "")
  title=str(row.get("bidNtceNm") or "").strip()
  if not NOTICE.fullmatch(number) or not title:continue
  sectors=tags(title)
  if not sectors:continue
  data.append({"noticeId":number,"revision":str(row.get("bidNtceOrd") or ""),
   "title":title[:230],"issueDate":str(row.get("bidNtceDt") or "")[:32],
   "issuingAgency":str(row.get("ntceInsttNm") or "")[:100],
   "demandAgency":str(row.get("dminsttNm") or "")[:100],
   "technologyTopics":sectors,"workType":kind,
   "sourceUrl":official_link(row.get("bidNtceDtlUrl") or row.get("bidNtceUrl")),
   "status":"public_tender_notice_not_award_or_contract",
   "namedSupplierVerified":False,"scoopConfirmed":False})
 return data,{"workType":kind,"status":"checked","total":count,
              "pages":pages,"matched":len(data)}

# Fixed messages raised by this module (no key, no URL): safe to keep in the public status file.
SAFE_MESSAGES={"Official response truncated","Missing provider body","Unexpected provider items structure",
               "Provider totalCount invalid","Provider totalCount negative","Invalid provider response",
               "Missing response","Official totalCount changed mid-pagination","Provider pagination ended prematurely",
               "Official result truncated by pagination cap","Provider kind/key missing","Invalid 12-digit period",
               "Excessive provider pagination"}
class ProviderCallsFailed(ValueError):
 def __init__(self,checks):
  super().__init__("Provider calls failed; old complete snapshot must be preserved")
  self.checks=checks
def build(key,get=fetch,now=None,previous=None):
 now=now or datetime.now(KST)
 # 창 끝을 '오늘 23:59'가 아니라 실행 5분 전으로: 넘기는 사이 새 공고가 붙어 totalCount가 바뀌는 일을 줄인다.
 end=(now-timedelta(minutes=5)).strftime("%Y%m%d%H%M")
 start=(now-timedelta(days=1)).strftime("%Y%m%d")+"0000"
 checks=[];leads=[];errors=0
 for kind in OPERATIONS:
  try:
   try:
    rows,check=query(kind,key,start,end,get=get)
   except ValueError as e:
    if str(e)!="Official totalCount changed mid-pagination":raise
    rows,check=query(kind,key,start,end,get=get)  # 한 번만 처음부터 다시
    check["restarted"]=True
   checks.append(check);leads.extend(rows)
  except (OSError,TimeoutError,ValueError,TypeError) as e:
   errors+=1
   check={"workType":kind,"status":"source_error","errorType":type(e).__name__}
   if isinstance(e,ProviderError):check["providerMessage"]=str(e)[:160]
   elif str(e) in SAFE_MESSAGES:check["errorMessage"]=str(e)
   checks.append(check)
 if errors:raise ProviderCallsFailed(checks)
 seen=set();unique=[]
 for row in leads:
  k=(row["noticeId"],row["revision"],row["workType"])
  if k in seen:continue
  seen.add(k)
  unique.append(row)
 old={(x.get("noticeId"),x.get("revision"),x.get("workType")) for x in
      (previous or {}).get("notices",[]) if isinstance(x,dict)}
 for row in unique:
  row["firstSeenInMonitor"]=(
      False if previous is None else
      (row["noticeId"],row["revision"],row["workType"]) not in old)
 return {"generatedAt":now.isoformat(timespec="seconds"),
         "from":start,"to":end,"source":"PPS official KONEPS tender notices",
         "checks":checks,"notices":unique[:180],
         "totalRelevant":len(unique),
         "newnessComparable":previous is not None,
         "confirmedAwards":0,"confirmedContracts":0,"confirmedScoops":0,
         "warning":"공고 공개/품명 일치만 확인. 낙찰·계약·국내 출입기업 공급·독점성 모두 미확인."}

def normalize_key(key):
 """data.go.kr shows an Encoding and a Decoding key. urlencode() encodes once,
 so an Encoding key (with %2B, %3D...) would be double-encoded: decode it first."""
 key=str(key or "").strip()
 if re.search(r"%[0-9A-Fa-f]{2}",key):return unquote(key),"url_encoded_input_decoded"
 return key,"decoded"
def resolve_key(env):
 """Return (key, secret name). Never the value in any output."""
 dedicated=str(env.get("G2B_API_KEY") or "").strip()
 if dedicated:return dedicated,"G2B_API_KEY"
 shared=str(env.get("DATA_GO_KR_SHARED_KEY") or "").strip()
 if shared:return shared,"CUSTOMS_API_KEY (shared data.go.kr account key)"
 return "",None
def failure_note(source):
 """Say what the failure actually was; a key-permission note only when the provider said so."""
 texts=[str(c.get("providerMessage") or "") for c in source.get("providerChecks") or []]+[str(source.get("providerMessage") or "")]
 if any(re.search(r"(^|\D)30(\D|$)|등록되지 않은|SERVICE_KEY|SERVICE ACCESS DENIED",t) for t in texts):
  return "Provider refused the key for this dataset (permission not active or key not registered). No 0-count claim."
 return "Provider call failed (see providerChecks errorType/errorMessage); not a key-permission signal by itself. No 0-count claim."
def main():
 p=argparse.ArgumentParser()
 p.add_argument("--out",default="digests/g2b_tender_latest.json")
 p.add_argument("--status",default="digests/g2b_source_status_latest.json")
 args=p.parse_args()
 key,key_source=resolve_key(os.environ)
 key,key_form=normalize_key(key)
 prev=None
 out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
 try:
  if out.exists():prev=json.loads(out.read_text(encoding="utf-8"))
 except (ValueError,OSError):pass
 source={"generatedAt":datetime.now(KST).isoformat(timespec="seconds"),
         "status":"not_connected" if not key else "unverified",
         "source":"PPS KONEPS dataset 15129394",
         "keySource":key_source,
         "keyForm":key_form if key else None,
         "note":("No G2B_API_KEY or shared data.go.kr key in this run. No 0-count claim."
                 if not key else
                 "Key present; a provider error means the dataset permission is not active for this key yet. No 0-count claim.")}
 if key:
  try:
   report=build(key,previous=prev)
   temp=out.with_suffix(".json.tmp")
   temp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
   temp.replace(out)
   source["status"]="checked";source["checkedKinds"]=len(report["checks"])
   source["note"]="Provider answered for every work type in the window; notices are not awards or contracts."
  except (ValueError,OSError,TimeoutError,TypeError) as e:
   source["status"]="source_error";source["errorType"]=type(e).__name__
   if isinstance(e,ProviderCallsFailed):source["providerChecks"]=e.checks
   elif isinstance(e,ProviderError):source["providerMessage"]=str(e)[:160]
   source["note"]=failure_note(source)
 path=Path(args.status);path.parent.mkdir(parents=True,exist_ok=True)
 temp=path.with_suffix(".json.tmp")
 temp.write_text(json.dumps(source,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 temp.replace(path)
 print("KONEPS source",source["status"],"contract/award claims: none")
 if source["status"]=="source_error":raise SystemExit(1)
if __name__=="__main__":main()
