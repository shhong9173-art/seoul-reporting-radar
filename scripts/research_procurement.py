"""MSIT open research CALLS + G2B public procurement NOTICE monitor.

No statement that a company won a government R&D grant or procurement award
unless an *award record with that company* is explicitly returned and verified.
Separate data.go.kr approvals may be required per provider and operation.
"""
from __future__ import annotations
import argparse
import json
import os
import re
from datetime import datetime,timedelta,timezone
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.request import Request,urlopen

KST=timezone(timedelta(hours=9))
RESEARCH="https://apis.data.go.kr/1721000/msitannouncementinfo/businessAnnouncMentList"
BIDS="https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoCnstwk"
DIRECT=["현대자동차","기아","현대모비스","현대제철","포스코","LS일렉트릭","HD현대일렉트릭",
        "대한전선","고려아연","두산에너빌리티","한화솔루션"]
TERMS=["변압기","전력망","HVDC","전기차","배터리","수소","풍력","원전","철강","ESS","초고압","전선","데이터센터"]

def fetch_json(url):
    # Never emit a full authenticated URL or response text on failure.
    try:
        with urlopen(Request(url,headers={"User-Agent":"newsroom-government-spotter/1.0"}),timeout=30) as r:
            raw=r.read(1_500_001)
    except Exception:
        raise ValueError("Official data.go.kr provider request failed (key and URL redacted)") from None
    if len(raw)>1_500_000:raise ValueError("Official response too large")
    try:data=json.loads(raw.decode("utf-8-sig"))
    except (ValueError,UnicodeError):
        raise ValueError("Official provider returned non-JSON data; schema/authorization unverified") from None
    if not isinstance(data,dict):raise ValueError("API object missing")
    return data

def normalized_api(data):
    response=data.get("response")
    if isinstance(response,dict):
        header=response.get("header") or {}
        code=str(header.get("resultCode") or header.get("resultcode") or "")
        if code and code not in ("00","0"):
            raise ValueError("Public-data gateway resultCode "+code[:8])
        body=response.get("body") or {}
        items=body.get("items") or []
        if isinstance(items,dict):items=items.get("item") or []
        if isinstance(items,dict):items=[items]
        total=body.get("totalCount") or 0
    else:
        code=str(data.get("resultCode") or data.get("resultcode") or "")
        if code and code not in ("00","0"):
            raise ValueError("Public-data gateway resultCode "+code[:8])
        items=data.get("items") or data.get("item") or []
        total=data.get("totalCount") or 0
    if not isinstance(items,list):raise ValueError("Unexpected public-data item shape")
    try:count=int(total)
    except (TypeError,ValueError):raise ValueError("Total count not validated") from None
    if count>0 and not items:raise ValueError("Provider reported items but none parsed")
    return items,count

def matching_terms(title):
    v=str(title or "").lower()
    return [x for x in TERMS if x.lower() in v]

def normalized_research(payload,now):
    items,total=normalized_api(payload)
    since=(now-timedelta(days=40)).date().isoformat()
    results=[]
    for item in items:
        if not isinstance(item,dict):continue
        title=str(item.get("subject") or "").strip()
        date=str(item.get("pressDt") or "")[:10]
        url=str(item.get("viewUrl") or "")
        if not date or date<since or date>now.date().isoformat() or not title:continue
        p=urlsplit(url)
        if p.scheme!="https" or p.hostname not in ("www.msit.go.kr","msit.go.kr"):continue
        hits=matching_terms(title)
        if not hits:continue
        results.append({"title":title[:250],"published":date,"url":url,
            "topics":hits,"sourceType":"msit_research_call",
            "status":"official_open_call_not_project_award",
            "reporterQuestion":"관련 기업이 실제 선정되거나 자금 지원을 받았는지 별도 과제·선정 공고 대조"})
    return {"source":"MSIT public announcement API","status":"checked",
            "returned":len(items),"total":total,"truncated":total>len(items),
            "items":results}

def normalized_bids(payload,now):
    items,total=normalized_api(payload)
    results=[]
    for item in items:
        if not isinstance(item,dict):continue
        title=str(item.get("bidNtceNm") or "").strip()
        no=str(item.get("bidNtceNo") or "").strip()
        date=str(item.get("bidNtceDt") or item.get("rgstDt") or "")[:10]
        hits=matching_terms(title)
        if not no or not title or not hits:continue
        if not re.fullmatch(r"[A-Z0-9-]{7,35}",no,re.I):continue
        results.append({"title":title[:200],"noticeNumber":no,
                        "buyer":str(item.get("dminsttNm") or item.get("ntceInsttNm") or "")[:110],
                        "registered":date,"topics":hits,
                        "sourceType":"g2b_construction_bid_notice",
                        "sourceUrl":"https://www.g2b.go.kr/",
                        "status":"bid_notice_not_awarded_or_signed"})
    return {"source":"PPS G2B BidPublicInfoService construction notice","status":"checked",
            "returned":len(items),"total":total,"truncated":total>len(items),
            "items":results}

def build(msit_key="",g2b_key="",now=None,fetch=fetch_json):
    now=now or datetime.now(KST)
    checks={}
    items=[]
    if not msit_key:
        checks["research"]={"status":"key_not_configured","portal":"https://www.data.go.kr/data/15074634/openapi.do"}
    else:
        url=RESEARCH+"?"+urlencode({"ServiceKey":msit_key,"pageNo":1,"numOfRows":50,"returnType":"json"})
        try:
            x=normalized_research(fetch(url),now)
            checks["research"]={k:v for k,v in x.items() if k!="items"}
            items.extend(x["items"])
        except (ValueError,TimeoutError,OSError) as err:
            checks["research"]={"status":"source_error","reason":type(err).__name__,
              "portal":"https://www.data.go.kr/data/15074634/openapi.do"}
    if not g2b_key:
        checks["procurement"]={"status":"key_not_configured",
                               "portal":"https://www.data.go.kr/data/15129394/openapi.do"}
    else:
        bgn=(now-timedelta(days=7)).strftime("%Y%m%d")+"0000"
        end=now.strftime("%Y%m%d")+"2359"
        url=BIDS+"?"+urlencode({"serviceKey":g2b_key,"pageNo":1,"numOfRows":100,
                                  "inqryDiv":1,"inqryBgnDt":bgn,"inqryEndDt":end,"type":"json"})
        try:
            x=normalized_bids(fetch(url),now)
            checks["procurement"]={k:v for k,v in x.items() if k!="items"}
            items.extend(x["items"])
        except (ValueError,TimeoutError,OSError) as err:
            checks["procurement"]={"status":"source_error","reason":type(err).__name__,
              "portal":"https://www.data.go.kr/data/15129394/openapi.do"}
    return {"generatedAt":now.isoformat(timespec="seconds"),
            "checks":checks,"items":items,
            "matchedItems":len(items),
            "sourceComplete":all(x.get("status")=="checked" and not x.get("truncated") for x in checks.values()),
            "scope":"MSIT 연구지원 *공모* + PPS/G2B 공사 부문 *입찰공고* 일부. NTIS 선정과제/수주/낙찰/계약 아님",
            "grantsAwardedVerified":0,"contractsAwardedVerified":0,
            "scoopConfirmed":0}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",default="digests/research_procurement_latest.json")
    args=p.parse_args()
    report=build(os.getenv("MSIT_API_KEY","").strip(),os.getenv("G2B_API_KEY","").strip())
    path=Path(args.out)
    # Do not overwrite last REAL records if either access fails.
    if not any(c.get("status")=="checked" for c in report["checks"].values()):
        print("Research/procurement official provider not available; old verified data retained")
        return
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    tmp.replace(path)
    print("Government research calls/bid notices",report["matchedItems"],
          "verified grants",report["grantsAwardedVerified"],
          "verified awards",report["contractsAwardedVerified"])
if __name__=="__main__":main()
