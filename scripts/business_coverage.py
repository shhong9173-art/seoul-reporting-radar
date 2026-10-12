"""Prior press cross-check for source-verified business changes.

Searches a few public Google News RSS results per evidence-backed candidate.
This is a coverage lead list, NOT proof of either unreported or already-covered
same-event news. Failure or zero hits must never increase exclusivity.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime,timedelta,timezone
from pathlib import Path
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import Request,urlopen

KST=timezone(timedelta(hours=9))
TOPIC_QUERY={
    "orderBacklog":"수주잔고",
    "productionCapacity":"생산능력",
    "productionActual":"생산실적",
    "utilization":"가동률",
    "segmentSales":"제품별 매출",
    "investment":"설비투자",
}


def query_for(f):
    company=str(f.get("company","")).strip()
    if not company or company not in ("HD현대일렉트릭","엘에스일렉트릭","효성중공업",
                                       "현대자동차","기아","현대제철","세아제강"):
        raise ValueError("출입처 확인되지 않은 검색 대상")
    year=int(f["toYear"])
    if not 2019<=year<=datetime.now(KST).year:
        raise ValueError("비정상 비교 연도")
    unit=TOPIC_QUERY.get(f.get("topic"))
    if not unit:
        raise ValueError("지원하지 않는 자료 종류")
    # Long legal-entity lists from consolidated tables make RSS queries
    # nearly impossible to match. Use at most one short distinct product/plant.
    generic={"전력","중공업","제품","기타","공통","건설","사업부문"}
    identifiers=[str(x).strip() for x in f.get("rowIdentity",[])
                 if isinstance(x,str) and 2<=len(x.strip())<=8
                 and x.strip() not in generic]
    label=identifiers[0] if identifiers else ""
    return f"{company} {year} {unit} {label} when:365d".strip()


def fetch_google(url):
    request=Request(url,headers={"User-Agent":"reporter-source-audit/1.0",
                                 "Accept":"application/rss+xml"})
    with urlopen(request,timeout=12) as response:
        payload=response.read(800_001)
    if len(payload)>800_000:
        raise ValueError("검색 응답 크기 상한 초과")
    return payload


def check_one(f,fetch=fetch_google):
    q=query_for(f)
    url="https://news.google.com/rss/search?q="+quote(q)+"&hl=ko&gl=KR&ceid=KR:ko"
    output={"query":q,"searchedAt":datetime.now(KST).isoformat(timespec="seconds"),
            "provider":"Google News RSS",
            "coverageDecision":"미검증: 검색은 같은 사건의 선행 보도를 확정하지 않음",
            "articles":[],"status":"unchecked"}
    try:
        root=ET.fromstring(fetch(url))
        if root.tag!="rss" or root.find("channel") is None:
            raise ValueError("Google RSS 응답 형식 불일치")
        for item in root.findall("./channel/item")[:15]:
            raw=(item.findtext("title") or "")
            name=html.unescape(re.sub(r"<[^>]*>","",raw)).strip()[:240]
            link=(item.findtext("link") or "").strip()
            if not name or not link.startswith("https://news.google.com/"):
                continue
            output["articles"].append({"title":name,"url":link,
                                       "published":str(item.findtext("pubDate") or "")[:90]})
            if len(output["articles"])>=4:
                break
        output["status"]=("관련 보도 후보 발견: 사건 동일성·원문 내용 확인 필요"
                          if output["articles"] else
                          "검색상 미발견: 단독 여부 판단 불가")
    except (ValueError,URLError,TimeoutError,OSError,ET.ParseError) as err:
        output["status"]="검색 실패("+type(err).__name__+"): 선행 보도 여부 미검증"
    return output


def build(metrics,search=check_one,limit=8):
    if not isinstance(metrics,dict) or not isinstance(metrics.get("findings"),list):
        raise ValueError("공식 수치 검증 JSON 형식 오류")
    if not 1<=limit<=20:
        raise ValueError("뉴스 검색 최대 건수 1~20")
    # Search is quota-limited; order by substantive change and diversify
    # across direct-beat issuers rather than spending all queries on one company.
    topic_rank={"orderBacklog":0,"productionCapacity":1,"utilization":2,
                "investment":3,"segmentSales":4,"productionActual":5}
    buckets={}
    for i,f in enumerate(metrics["findings"]):
        if not isinstance(f,dict) or f.get("carryForwardMatched") is not True:
            continue
        buckets.setdefault(f.get("company",""),[]).append((i,f))
    for group in buckets.values():
        group.sort(key=lambda pair:(
            topic_rank.get(pair[1].get("topic"),9),
            -abs(float(pair[1].get("changePercent") or 0)),
            pair[0]))
    companies=sorted(buckets,
                     key=lambda c:(topic_rank.get(buckets[c][0][1].get("topic"),9),c))
    selected=[]
    while len(selected)<limit and any(buckets.values()):
        for c in companies:
            if buckets[c] and len(selected)<limit:
                selected.append(buckets[c].pop(0)[0])
    selected=set(selected)
    rows=[]
    for i,f in enumerate(metrics["findings"]):
        if not isinstance(f,dict):
            continue
        candidate={
            "company":f.get("company"),"topic":f.get("topic"),
            "rowIdentity":f.get("rowIdentity",[]),"sourceReceipts":f.get("originalReceipts",[]),
            "sourceStatus":f.get("status"),
            "exclusiveStatus":"보류: 단독 기사 자동 판정 금지",
        }
        if i in selected and f.get("carryForwardMatched") is True:
            try:
                candidate["coverage"]=search(f)
            except (ValueError,TypeError) as err:
                candidate["coverage"]={"status":"검색 입력 오류: "+type(err).__name__,
                                        "articles":[],"coverageDecision":"미검증"}
        else:
            candidate["coverage"]={"status":"미검색: 조회 상한 또는 공식 증거 부족",
                                    "articles":[],"coverageDecision":"미검증"}
        rows.append(candidate)
    return {"generatedAt":datetime.now(KST).isoformat(timespec="seconds"),
            "metricsGeneratedAt":metrics.get("generatedAt"),
            "sourceGeneratedAt":metrics.get("sourceGeneratedAt"),
            "scope":"공식 사업보고서 비교 수치 관련 언론 검색 후보",
            "status":"prior_coverage_leads_not_exclusives",
            "checked":sum(r["coverage"]["status"].startswith(("관련","검색상","검색 실패")) for r in rows),
            "items":rows}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--metrics",default="digests/business_metrics_latest.json")
    p.add_argument("--output",default="digests/business_coverage_latest.json")
    p.add_argument("--max-searches",type=int,default=8)
    args=p.parse_args()
    data=json.loads(Path(args.metrics).read_text(encoding="utf-8"))
    result=build(data,limit=args.max_searches)
    dest=Path(args.output)
    dest.parent.mkdir(parents=True,exist_ok=True)
    temp=dest.with_suffix(".json.tmp")
    temp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    temp.replace(dest)
    print("보도검색 검토",result["checked"],"건, 관련 보도 건수와 무관하게 단독판정 0건")


if __name__=="__main__":
    main()
