"""Official Customs HS-category monthly trends, NOT issuer-specific figures."""
from __future__ import annotations
import argparse
import json
import os
import re
from collections import defaultdict
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from pathlib import Path

import customs
from trade_trends import compare_years

KST=timezone(timedelta(hours=9))
# Broad HS4 categories: useful for sector context, NEVER a named company's exports.
CATEGORIES={
    "8504":"변압기·정류기·정지형 변환기 등 (광범위 HS4)",
    "8544":"절연전선·케이블 (광범위 HS4)",
    "8703":"승용자동차 (광범위 HS4)",
    "7208":"철강 평판압연제품 중 열연 관련 (광범위 HS4)",
}
FIELDS=("expDlr","expWgt","impDlr","impWgt")
METRICS=("수출금액(달러)","수출중량(kg)","수입금액(달러)","수입중량(kg)")


def last_complete_month(now):
    year,month=now.year,now.month-1
    if month==0:
        year-=1;month=12
    return f"{year:04d}{month:02d}"


def verify_month(value,start,end):
    if not re.fullmatch(r"(?:19|20)\d{2}(?:0[1-9]|1[0-2])",str(value)):
        raise ValueError(f"무역통계 연월 형식 미확인: {value!r}")
    if not start<=value<=end:
        raise ValueError(f"API 응답이 요청한 기간 밖: {value}")


def aggregate(items,start,end):
    result=defaultdict(lambda:{key:Decimal(0) for key in METRICS})
    if not isinstance(items,list) or not items:
        raise ValueError("관세청 데이터 미수신: 유효한 통계 0건이라고 볼 수 없음")
    for record in items:
        month=record.get("year","")
        if "총" in month:
            continue
        verify_month(month,start,end)
        for field,label in zip(FIELDS,METRICS):
            if field not in record:
                raise ValueError(f"관세청 응답 필드 누락: {field}")
            result[month][label]+=customs.num(record[field])
    if not result:
        raise ValueError("월별 유효 통계가 없는 응답: 비교 자료 미확인")
    return dict(result)


def fetch_category(key,hs,start,end,fetch=customs.fetch):
    items=[]
    for begin,finish in customs.chunks(start,end):
        chunk=fetch(key,hs,begin,finish,"")
        if not isinstance(chunk,list):
            raise ValueError("관세청 XML item 파싱 결과가 목록 아님")
        items.extend(chunk)
    return aggregate(items,start,end)


def build(key,start,end,year,codes=tuple(CATEGORIES),fetch=customs.fetch):
    if not key:
        raise ValueError("CUSTOMS_API_KEY 환경변수 없음")
    if not (re.fullmatch(r"\d{6}",start) and re.fullmatch(r"\d{6}",end) and start<=end):
        raise ValueError("조회기간 지정 오류")
    records=[]
    for hs in codes:
        if hs not in CATEGORIES:
            raise ValueError("출입 산업과 관련성 검토되지 않은 HS 코드")
        months=fetch_category(key,hs,start,end,fetch=fetch)
        report=compare_years(months,target_year=year)
        if not report.get("totals"):
            raise ValueError(f"HS{hs} 동일 월 전년 비교가 불가능해 전체 최신값 게시를 중단")
        records.append({
            "hs4":hs,"label":CATEGORIES[hs],"country":"ALL","rowCount":len(months),
            "observedMonths":sorted(months),"comparison":report,
            "source":"관세청 품목별 국가별 수출입실적 API",
            "sourceUrl":"https://apis.data.go.kr/1220000/nitemtrade/getNitemtradeList",
            "scopeWarning":"HS4 전체 품목군의 무역 실적. 특정 기업·전력기기 단일품목·생산량·개별 계약 결과가 아님",
        })
    return {"generatedAt":datetime.now(KST).isoformat(timespec="seconds"),
            "periodStart":start,"periodEnd":end,"comparisonYear":year,
            "source":"관세청 품목별 국가별 수출입실적 API / 전체 국가",
            "status":"official_hs_trade_context_not_company_performance",
            "items":records,
            "notes":"공식 HS4로 묶인 국가 전체 수출입 현황. 기자가 HS 최신 분류와 통계 수정·잠정치 여부를 확인하고 기업 직접 수출과 연결하지 말 것"}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--start",default=str(datetime.now(KST).year-2)+"01")
    p.add_argument("--end",default=last_complete_month(datetime.now(KST)))
    p.add_argument("--year",type=int,default=datetime.now(KST).year)
    p.add_argument("--output",default="digests/hs_trends_latest.json")
    args=p.parse_args()
    key=os.getenv("CUSTOMS_API_KEY","").strip()
    if not key:
        print("CUSTOMS_API_KEY 미연결: 관세청 지표 수집 미실행, 기존 결과 보존")
        return
    result=build(key,args.start,args.end,args.year)
    path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    temp.replace(path)
    print("관세청 HS4 공식 동일 월 비교",len(result["items"]),"개 품목군, 개별 회사 귀속 없음")


if __name__=="__main__":
    main()
