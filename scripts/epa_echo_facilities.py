"""Official EPA ECHO facility registry, NOT new building or environmental permits.

ArcGIS ECHO/Facilities MapServer layer 0 public FAC_NAME registry query.
A matching facility is only a SOURCE to ask about projects; a company may own
facilities with similar names, and permit-type presence is NOT permit issuance.
"""
from __future__ import annotations
import argparse,json,re
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from datetime import datetime,timedelta,timezone
from pathlib import Path

KST=timezone(timedelta(hours=9))
API="https://echogeo.epa.gov/arcgis/rest/services/ECHO/Facilities/MapServer/0/query"
FIELDS=["REGISTRY_ID","FAC_NAME","FAC_STATE","FAC_CITY",
        "CAA_PERMIT_TYPES","FAC_ACTIVE_FLAG","FAC_CURR_COMPLIANCE_STATUS"]
ALIASES={
    "현대자동차":"HYUNDAI MOTOR",
    "현대모비스":"HYUNDAI MOBIS",
    "기아":"KIA",
    "포스코":"POSCO",
    "두산에너빌리티":"DOOSAN",
    "효성중공업":"HYOSUNG",
    "고려아연":"KOREA ZINC",
}
REGISTRY=re.compile(r"^[A-Z0-9-]{3,30}$",re.I)
MAX_IDS=1000
BATCH_SIZE=50

def query_url(alias):
    if alias not in ALIASES.values():raise ValueError("Unsupported legal brand query")
    return API+"?"+urlencode({
        "where":"FAC_NAME LIKE '%"+alias+"%'",
        "outFields":",".join(FIELDS),
        "returnGeometry":"false","resultRecordCount":"50","f":"json"})

def request_json(uri):
    try:
        with urlopen(Request(uri,headers={"User-Agent":"industry-investigative-epa-echo/1.0"}),
                     timeout=23) as r:
            content=r.read(1_500_001)
    except HTTPError as error:
        raise ValueError('EPA HTTP '+str(error.code)) from None
    except Exception:
        raise ValueError("EPA ArcGIS official query unavailable") from None
    if len(content)>1_500_000:raise ValueError("EPA facilities query response truncated")
    try:obj=json.loads(content.decode("utf-8-sig"))
    except (ValueError,UnicodeError):
        raise ValueError("EPA official query returned non-JSON") from None
    if not isinstance(obj,dict) or obj.get("error"):
        raise ValueError("EPA ECHO ArcGIS provider error") from None
    return obj

def collect(alias,fetch):
    """Resolve a truncated query through the provider's complete ID manifest.

    ArcGIS returnIdsOnly is not subject to the feature response row limit.
    Verify every requested ID, rather than trusting offsets on a changing layer.
    """
    first=fetch(query_url(alias))
    if first.get('exceededTransferLimit') is not True:return first
    manifest=fetch(API+'?'+urlencode({'where':"FAC_NAME LIKE '%"+alias+"%'",
                                    'returnIdsOnly':'true','f':'json'}))
    ids=manifest.get('objectIds');field=manifest.get('objectIdFieldName')
    if (not isinstance(ids,list) or not isinstance(field,str)
        or not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*',field)
        or any(type(x) is not int or x<0 for x in ids)
        or len(set(ids))!=len(ids) or manifest.get('exceededTransferLimit') is True):
        raise ValueError('EPA invalid ID manifest')
    if len(ids)>MAX_IDS:
        return {'features':[], 'exceededTransferLimit':True,
                'matchedIds':len(ids),'unqueriedIds':len(ids)}
    rows=[]
    for start in range(0,len(ids),BATCH_SIZE):
        batch=sorted(ids)[start:start+BATCH_SIZE]
        page=fetch(API+'?'+urlencode({'objectIds':','.join(map(str,batch)),
                    'outFields':','.join([field]+FIELDS),'returnGeometry':'false',
                    'resultRecordCount':BATCH_SIZE,'f':'json'}))
        features=page.get('features')
        if not isinstance(features,list) or page.get('exceededTransferLimit') is True:
            raise ValueError('EPA incomplete ID batch')
        returned=[r.get('attributes',{}).get(field) if isinstance(r,dict) else None for r in features]
        if any(type(x) is not int for x in returned) or sorted(returned)!=batch:
            raise ValueError('EPA missing duplicate or unexpected ID')
        rows.extend(features)
    return {'features':rows,'matchedIds':len(ids),'unqueriedIds':0}

def parse(payload,issuer):
    if not isinstance(payload,dict) or not isinstance(payload.get("features"),list):
        raise ValueError("EPA ECHO original features list missing")
    features=payload["features"]
    if payload.get("exceededTransferLimit") is True:
        return {"status":"truncated_not_exhaustive","count":len(features),"items":[]}
    result=[]
    for value in features:
        a=value.get("attributes") if isinstance(value,dict) else None
        if not isinstance(a,dict):continue
        name=str(a.get("FAC_NAME") or "").strip()
        alias=ALIASES[issuer]
        if not re.search(r'(?<![A-Z0-9])'+re.escape(alias)+r'(?![A-Z0-9])',name.upper()):continue
        rid=str(a.get("REGISTRY_ID") or "").strip()
        if not REGISTRY.fullmatch(rid):continue
        result.append({
            "registryId":rid,"facilityName":name[:200],"issuerSearch":issuer,
            "state":str(a.get("FAC_STATE") or "")[:2],
            "city":str(a.get("FAC_CITY") or "")[:100],
            "airPermitTypeLabels":str(a.get("CAA_PERMIT_TYPES") or "")[:150],
            "activeFlag":str(a.get("FAC_ACTIVE_FLAG") or "")[:5],
            "complianceStatusLabel":str(a.get("FAC_CURR_COMPLIANCE_STATUS") or "")[:80],
            "sourceUrl":"https://echo.epa.gov/",
            "sourceType":"existing_epa_registered_facility",
            "permitIssuedVerified":False,
            "companyLegalOwnershipVerified":False,
            "newConstructionVerified":False,
            "claimScope":"공식 ECHO 시설·규제 관심 기록. 신규 공장 허가/인허가 발급일/한국 모기업 소유 확인 전"})
    return {"status":"checked","count":len(features),"items":result}

def evaluate(fetch=request_json,now=None):
    now=now or datetime.now(KST)
    checks=[]
    allitems=[]
    for issuer,alias in ALIASES.items():
        try:
            payload=collect(alias,fetch)
            obj=parse(payload,issuer)
            checks.append({"issuer":issuer,"status":obj["status"],
                           "scanned":obj["count"],"matchedIds":payload.get('matchedIds'),
                           "unqueriedIds":payload.get('unqueriedIds'),
                           "facilityCandidates":len(obj["items"]) if obj['status']=='checked' else None})
            allitems.extend(obj["items"])
        except (ValueError,OSError,TimeoutError) as e:
            reason=str(e) if re.fullmatch(r'EPA HTTP \d{3}',str(e)) else 'network_or_provider_response_error'
            checks.append({"issuer":issuer,"status":"source_error","errorType":type(e).__name__,"reason":reason})
    unique={}
    for row in allitems:
        unique.setdefault(row["registryId"],row)
    return {"generatedAt":now.isoformat(timespec="seconds"),
        "source":"US EPA ECHO All Facilities MapServer ArcGIS layer 0",
        "sourceUrl":API,
        "queries":len(checks),
        "checks":checks,
        "facilityCandidates":list(unique.values()),
        "candidateCount":len(unique) if all(x['status']=='checked' for x in checks) else None,
        "observedCandidateCount":len(unique),
        "sourceComplete":all(x["status"]=="checked" for x in checks),
        "verifiedNewPermits":0,"confirmedScoops":0,
        "limitations":"특정 기업과 유사 시설 이름의 원문만 검색. 실제 회사소유/신규 건축허가/환경허가의 발급일 및 공장 확대는 확인되지 않음"}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--out",default="digests/epa_facilities_latest.json")
    ap.add_argument("--health",default="digests/epa_source_status_latest.json")
    a=ap.parse_args()
    result=evaluate()
    health={'generatedAt':result['generatedAt'],
            'status':'checked' if result['sourceComplete'] else 'incomplete',
            'checks':result['checks'],'candidateCount':result['candidateCount'],
            'observedCandidateCount':result['observedCandidateCount'],
            'warning':'전체 조회 실패·일부 누락은 시설 0곳이 아님. 기존 정상 자료와 현재 원천 상태를 구분'}
    hp=Path(a.health);hp.parent.mkdir(parents=True,exist_ok=True)
    ht=hp.with_suffix('.json.tmp');ht.write_text(json.dumps(health,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');ht.replace(hp)
    if not any(x["status"]=="checked" for x in result["checks"]):
        raise SystemExit("EPA no fully checked original query; previous data preserved, health recorded")
    target=Path(a.out);target.parent.mkdir(parents=True,exist_ok=True)
    if not result['sourceComplete']:
        try:prior=json.loads(target.read_text(encoding='utf-8'))
        except (OSError,ValueError):prior={}
        failed={x['issuer'] for x in result['checks'] if x['status']!='checked'}
        older=prior.get('facilityCandidates',[])+prior.get('retainedPriorEvidence',[])
        retained={x['registryId']:x for x in older if x.get('issuerSearch') in failed}
        result['retainedPriorEvidence']=list(retained.values())
        result['retainedEvidenceIsCurrent']=False
    temp=target.with_suffix(".json.tmp")
    temp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    temp.replace(target)
    print("EPA ECHO facility names",result["candidateCount"],
          "queries",result["queries"],"new permits verified",result["verifiedNewPermits"])
if __name__=="__main__":main()
