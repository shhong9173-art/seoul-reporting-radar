"""Industry comparative research based on official OpenDART financial statements.

This discovers *reporting questions*, NOT scoops. Never imply that consolidated
revenue equals physical output, export sales, order book, or market share.
Compare only matching fiscal years, statements, currency, and account IDs.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import median
from urllib.error import URLError
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

KST = timezone(timedelta(hours=9))
ENDPOINT = "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"
GUIDE = "https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS003&apiId=2019020"
ACCOUNT_IDS = {
    "revenue": {"ifrs-full_Revenue", "ifrs_Revenue", "ifrs-full_RevenueFromContractsWithCustomers"},
    "operatingIncome": {"dart_OperatingIncomeLoss", "ifrs-full_ProfitLossFromOperatingActivities",
                        "ifrs_ProfitLossFromOperatingActivities"},
}
# Curated reporting beats only. The three business models in a comparison group
# can still differ; never describe the peer median as the market-wide average.
GROUPS = {
    "자동차 완성차": ("현대자동차", "기아"),
    "자동차 부품": ("현대모비스", "현대위아", "HL만도"),
    "전력기기": ("HD현대일렉트릭", "엘에스일렉트릭", "효성중공업"),
    "철강": ("현대제철", "동국제강", "세아제강"),
    "비철": ("고려아연", "영풍"),
}
ACCOUNT_LABELS = {"revenue":"매출액", "operatingIncome":"영업이익"}
SLOTS = (("thstrm_amount",0),("frmtrm_amount",1),("bfefrmtrm_amount",2))
INTERIM_SLOTS = (("thstrm_add_amount",0),("frmtrm_add_amount",1))
PERIODS = (
    {"key":"annual","name":"연간 사업보고서","report":"11011","yearOffset":-1,"slots":SLOTS},
    {"key":"halfyear","name":"반기 누적","report":"11012","yearOffset":0,"slots":INTERIM_SLOTS},
)


def valid_corp(code):
    return isinstance(code,str) and bool(re.fullmatch(r"\d{8}",code))


def amount(value):
    if not isinstance(value,str) or not re.fullmatch(r"-?(?:\d{1,3}(?:,\d{3})+|\d+)",value.strip()):
        return None
    try:
        number=Decimal(value.replace(",","").strip())
        return number if number.is_finite() else None
    except InvalidOperation:
        return None


def receipt_link(receipt):
    return ("https://dart.fss.or.kr/dsaf001/main.do?rcpNo="+receipt
            if isinstance(receipt,str) and re.fullmatch(r"\d{14}",receipt) else None)


def get_json(url):
    request=Request(url,headers={"User-Agent":"industry-reporter-research/1.0",
                                 "Accept":"application/json"})
    with urlopen(request,timeout=18) as response:
        raw=response.read(4*1024*1024+1)
    if len(raw)>4*1024*1024:
        raise ValueError("DART API 4MB 응답 상한 초과")
    return json.loads(raw.decode("utf-8-sig"))


def fetch_statement(key,corp_code,year,report,get=get_json):
    if not key:
        raise ValueError("DART_API_KEY 미설정: 공식 수치 수집 불가")
    if not valid_corp(corp_code) or not 2015<=int(year)<=datetime.now(KST).year:
        raise ValueError("DART 회사·연도 입력 오류")
    url=ENDPOINT+"?"+urlencode({"crtfc_key":key,"corp_code":corp_code,
                              "bsns_year":str(year),"reprt_code":report,"fs_div":"CFS"})
    result=get(url)
    if not isinstance(result,dict):
        raise ValueError("DART 전체 재무제표 응답 형식 오류")
    if result.get("status")=="013":
        return {"status":"no_report", "list":[]}
    if result.get("status")!="000":
        # Never publish a '0 findings' report when provider access failed.
        raise RuntimeError("DART 전체 재무제표 API 오류: "+str(result.get("status")))
    if not isinstance(result.get("list"),list):
        raise ValueError("DART 응답에 재무제표 목록 누락")
    return result


def identify_account(row):
    if row.get("sj_div") not in ("IS","CIS"):
        return None
    if row.get("account_detail") not in ("", "-", None):
        return None
    account_id=row.get("account_id","")
    for name,codes in ACCOUNT_IDS.items():
        if account_id in codes:
            return name
    return None


def extract_period(resp, name, corp_code, base_year, report, period):
    """Use amounts in the SAME CFS filing, with source URLs for every year."""
    if resp.get("status")=="no_report":
        return {"name":name,"corpCode":corp_code,"reportYear":base_year,
                "period":period["key"],"status":"no_report","metrics":{},"sources":[]}
    if resp.get("status")!="000":
        raise ValueError("DART 전체 재무제표 상태 미확인")
    rows=resp["list"]
    matched=[]
    for row in rows:
        if not isinstance(row,dict):
            continue
        if (row.get("corp_code")!=corp_code or str(row.get("bsns_year"))!=str(base_year)
            or row.get("reprt_code")!=report):
            continue
        metric=identify_account(row)
        if metric and row.get("currency") in ("KRW","원"):
            matched.append((metric,row))
    data={}
    receipts=set()
    for metric in ACCOUNT_IDS:
        selected=[r for m,r in matched if m==metric]
        if selected:
            # Prefer income statement over comprehensive income statement.
            is_rows=[r for r in selected if r["sj_div"]=="IS"]
            if is_rows:
                selected=is_rows
        for slot,offset in period["slots"]:
            figures=set()
            slot_receipts=set()
            for row in selected:
                value=amount(row.get(slot))
                if value is not None:
                    figures.add(value)
                    if receipt_link(row.get("rcept_no")):
                        slot_receipts.add(row["rcept_no"])
            # Ambiguous values and conflicting original URLs are UNKNOWN.
            if len(figures)!=1 or len(slot_receipts)!=1:
                continue
            year=str(base_year-offset)
            data.setdefault(metric,{})[year]=str(next(iter(figures)))
            receipts.update(slot_receipts)
    return {
        "name":name,"corpCode":corp_code,"period":period["key"],
        "periodName":period["name"],"reportYear":base_year,
        "scope":"CFS", "currency":"KRW",
        "reportCode":report, "status":"extracted" if data else "no_comparable_accounts",
        "metrics":data,
        "sources":[{"receiptNo":r,"url":receipt_link(r)} for r in sorted(receipts)],
        "warning":"동일 사업보고서 기준 공시 수치. 과거 수치가 재작성됐을 수 있고 그룹사 간 사업구조·내부거래가 다름",
    }


def ratio(new,old):
    # A negative or zero denominator is not an interpretable growth rate.
    if new is None or old is None or old<=0:
        return None
    return float((new-old)/old*100)


def margin(profit,sales):
    return float(profit/sales*100) if profit is not None and sales is not None and sales>0 else None


def series_of(company,metric):
    return {int(y):Decimal(value) for y,value in company.get("metrics",{}).get(metric,{}).items()}


def evaluate_group(group,records,period,year):
    """Outliers only when at least 3 companies have identical-period figures."""
    peers=[r for r in records if r.get("status")=="extracted"]
    metrics={}
    observations=[]
    for r in peers:
        revenue=series_of(r,"revenue")
        income=series_of(r,"operatingIncome")
        yoy=ratio(revenue.get(year),revenue.get(year-1))
        prior_yoy=ratio(revenue.get(year-1),revenue.get(year-2))
        profit_margin=margin(income.get(year),revenue.get(year))
        old_margin=margin(income.get(year-1),revenue.get(year-1))
        if yoy is None:
            continue
        entry={"company":r["name"],"revenueYoY":yoy,
               "priorRevenueYoY":prior_yoy,
               "marginNow":profit_margin,"marginPrior":old_margin,
               "marginShiftPp":(profit_margin-old_margin if
                                profit_margin is not None and old_margin is not None else None),
               "sources":r["sources"],"period":period,"year":year}
        observations.append(entry)
    if len(observations)<3:
        return []
    findings=[]
    for entry in observations:
        others=[e["revenueYoY"] for e in observations if e["company"]!=entry["company"]]
        peer_median=median(others)
        gap=entry["revenueYoY"]-peer_median
        # Keep direction and comparables clear, no causal assignment.
        if abs(gap)>=15 and abs(entry["revenueYoY"])>=10:
            findings.append({
                "group":group,"company":entry["company"],"period":period,"year":year,
                "metric":"매출액 증가율의 비교기업 격차",
                "gapPp":round(gap,2),
                "latestYoYPercent":round(entry["revenueYoY"],2),
                "comparisonMedianPercent":round(peer_median,2),
                "otherPeerCount":len(others),
                "priorYoYPercent":round(entry["priorRevenueYoY"],2) if entry["priorRevenueYoY"] is not None else None,
                "sources":entry["sources"],
                "status":"취재 단서·단독 미확정",
                "coverage":"미검증: 회사 IR·기존 언론 보도·해당 원자료를 추가 확인",
                "questions":["사업부·제품별 매출 구성이 비교기업과 다른지?",
                             "해당 기간 환율·인수합병·연결범위 변화가 수치에 반영됐는지?",
                             "증감 원인과 수주·생산/출하 변화가 실제로 연결되는지?"],
            })
    findings.sort(key=lambda r:-abs(r["gapPp"]))
    return findings


def analyze(records,generated_at=None):
    groups={}
    findings=[]
    for period in PERIODS:
        key=period["key"]
        by_group={}
        for group,companies in GROUPS.items():
            year=max(r.get("reportYear",0) for r in records if r.get("period")==key) if any(
                r.get("period")==key for r in records) else None
            subset=[r for r in records if r["period"]==key and r["name"] in companies]
            by_group[group]=subset
            if year:
                findings.extend(evaluate_group(group,subset,key,year))
        groups[key]=by_group
    return {
        "generatedAt":generated_at or datetime.now(KST).isoformat(timespec="seconds"),
        "source":"OpenDART fnlttSinglAcntAll.json · CFS · 각 보고서의 표준 계정ID",
        "sourceGuide":GUIDE,
        "method":"같은 기준의 매출액 1년 증가율이 비교회사 중앙값에서 15%p 이상 벌어지고 절대 변화가 10% 이상일 때 취재 단서",
        "limitations":"기업별 제품 구성이 달라 원인·산업 전체 추세·단독 여부는 미확인. 3개년은 '사상 처음'을 입증하지 못함",
        "groupNames":{g:list(companies) for g,companies in GROUPS.items()},
        "periods":{p["key"]:{"label":p["name"],"year":next(
            (r["reportYear"] for r in records if r["period"]==p["key"]),None)}
            for p in PERIODS},
        "companies":records,
        "findings":findings[:30],
        "findingCount":len(findings),
        "status":"research_only_not_exclusives",
    }


def collect(codes,key,annual_year,interim_year,get=get_json):
    records=[]
    for period in PERIODS:
        year=annual_year if period["key"]=="annual" else interim_year
        for group,companies in GROUPS.items():
            for company in companies:
                data=codes.get(company)
                code=data.get("corp_code") if isinstance(data,dict) else None
                if not valid_corp(code):
                    records.append({"name":company,"period":period["key"],"reportYear":year,
                                    "status":"corp_code_unavailable","metrics":{},"sources":[]})
                    continue
                try:
                    response=fetch_statement(key,code,year,period["report"],get=get)
                    record=extract_period(response,company,code,year,period["report"],period)
                    record["group"]=group
                    records.append(record)
                except (RuntimeError,URLError,TimeoutError,ValueError) as exc:
                    # Explicit error and partial run, not fabricated zero.
                    records.append({"name":company,"group":group,"corpCode":code,
                                    "reportYear":year,"period":period["key"],
                                    "status":"error","error":type(exc).__name__,
                                    "metrics":{},"sources":[]})
    return records


def prior_news_candidates(company,period,year,fetch= None):
    """Related coverage leads from Google News; never same-event proof.

    One bounded search per candidate with a wide lookback: annual/interim
    disclosures may have been reported months before the current scan.
    """
    if fetch is None:
        def fetch(url):
            req=Request(url,headers={"User-Agent":"industry-reporter-research/1.0",
                                     "Accept":"application/rss+xml"})
            with urlopen(req,timeout=12) as response:
                raw=response.read(800001)
            if len(raw)>800000:
                raise ValueError("Google News RSS 크기 상한 초과")
            return raw
    season="상반기 실적 매출" if period=="halfyear" else "연간 실적 매출"
    query=f"{company} {year} {season} when:365d"
    url="https://news.google.com/rss/search?q="+quote(query)+"&hl=ko&gl=KR&ceid=KR:ko"
    try:
        root=ET.fromstring(fetch(url))
        if root.tag!="rss" or root.find("channel") is None:
            raise ValueError("Google RSS 응답 형식 불일치")
        articles=[]
        for item in root.findall("./channel/item")[:12]:
            headline=html.unescape(re.sub(r"<[^>]+>","",item.findtext("title") or "")).strip()
            link=(item.findtext("link") or "").strip()
            if not headline or not link.startswith("https://news.google.com/"):
                continue
            articles.append({"title":headline[:220],"url":link,
                             "published":str(item.findtext("pubDate") or "")[:90]})
            if len(articles)>=4:
                break
        return {
            "query":query,"checkedVia":"Google News RSS", "items":articles,
            "status":("관련 보도 검색 결과 있음: 같은 사건 여부 직접 확인 필요" if articles else
                      "검색 범위 내 보도 미발견: 단독 판단 불가"),
        }
    except (ET.ParseError,ValueError,URLError,TimeoutError,OSError) as exc:
        return {"query":query,"checkedVia":"Google News RSS","items":[],
                "status":"검색 오류: "+type(exc).__name__+"; 미보도 주장 불가"}


def attach_prior_coverage(report,lookup=prior_news_candidates):
    """Append evidence of search attempts. Retain all anomalous source signals."""
    for item in report.get("findings",[])[:12]:
        try:
            item["priorCoverage"]=lookup(item["company"],item["period"],item["year"])
        except Exception as exc:
            item["priorCoverage"]={"status":"보도 조회 예외: "+type(exc).__name__,
                                   "items":[]}
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--codes",default="dart_corp_codes.json")
    p.add_argument("--out",default="digests/peer_financial_latest.json")
    p.add_argument("--annual-year",type=int,default=datetime.now(KST).year-1)
    p.add_argument("--interim-year",type=int,default=datetime.now(KST).year)
    args=p.parse_args()
    if not 2020<=args.annual_year<=datetime.now(KST).year or not 2020<=args.interim_year<=datetime.now(KST).year:
        p.error("사업연도 범위 오류")
    key=os.getenv("DART_API_KEY","").strip()
    if not key:
        raise SystemExit("DART_API_KEY 미설정: 기존 보고서를 덮어쓰지 않음")
    codes_path=Path(args.codes)
    codes=json.loads(codes_path.read_text(encoding="utf-8")).get("companies",{})
    records=collect(codes,key,args.annual_year,args.interim_year)
    usable=sum(r.get("status")=="extracted" for r in records)
    errors=[r for r in records if r.get("status")=="error"]
    if errors or usable<3:
        raise SystemExit(f"공식 데이터 불완전: 조회 오류={len(errors)}, 지표 성공={usable}; 기존 파일 보존")
    output=attach_prior_coverage(analyze(records))
    output["coverage"]={"requested":len(records),"extracted":usable,
                        "unavailable":sum(r.get("status")!="extracted" for r in records),
                        "errors":len(errors)}
    path=Path(args.out)
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    temp.replace(path)
    print("공식 비교 지표:",usable,"/",len(records),"기업·기간별 수집 | 취재 단서",
          output["findingCount"],"건 | 단독 확정 0건(자동화 설계상 금지)")


if __name__=="__main__":
    main()
