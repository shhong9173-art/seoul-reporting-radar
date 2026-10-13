"""Detailed official HS6 exports context, separate from broad HS4 dashboard.

Each code is a six-digit internationally defined product GROUP, not a company,
contract, a specific transformer specification or a confirmed price rise.
"""
from __future__ import annotations
import argparse,json,os
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from pathlib import Path
import customs
from customs_watch import fetch_category,last_complete_month
from trade_trends import compare_years
KST=timezone(timedelta(hours=9))
CODES={
 "850421":"액체절연 변압기(650kVA 이하)",
 "850422":"액체절연 변압기(650~1만kVA)",
 "850423":"액체절연 변압기(1만kVA 초과)",
 "850434":"기타 변압기(500kVA 초과)",
 "854460":"1,000V 초과 전기 도체(HS6)",
 "870380":"전기 구동 승용자동차(HS6)",
}
COUNTRIES={"":"전체국가","US":"미국","CN":"중국"}
SOURCE="https://apis.data.go.kr/1220000/nitemtrade/getNitemtradeList"

def verify_dataset(key,start,end,year,fetch=customs.fetch):
    if not key:raise ValueError("CUSTOMS_API_KEY missing")
    data=[]
    for code,label in CODES.items():
        # Split into 12-month windows. The official API's 6-digit code may
        # itself represent several finer national subheadings.
        months=fetch_category(key,code,start,end,fetch=fetch)
        comparison=compare_years(months,target_year=year)
        if not comparison.get("totals"):raise ValueError("Missing comparable period HS6 "+code)
        data.append({"hs6":code,"label":label,"country":"ALL",
          "observedMonths":sorted(months),"comparison":comparison,
          "sourceUrl":SOURCE,
          "claimScope":"공식 국가 전체 HS6 수출입. 기업별 수출·해당 사업 납품/기술별 가격이 아님"})
    return {"generatedAt":datetime.now(KST).isoformat(timespec="seconds"),
       "periodStart":start,"periodEnd":end,"year":year,
       "status":"verified_hs6_country_trade_only",
       "items":data,"confirmedScoops":0,
       "notes":"관세청 현행 코드/세분 HSK 10단위 분류표 대조 필요. 중량(kg) 기반 단가는 품목 믹스에 따라 달라짐"}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",default="digests/customs_hs6_latest.json")
    a=p.parse_args()
    key=os.getenv("CUSTOMS_API_KEY","")
    if not key:
        print("CUSTOMS_API_KEY missing, HS6 not fetched; previous evidence retained")
        return
    now=datetime.now(KST)
    year=now.year
    start=f"{year-2}01"
    end=last_complete_month(now)
    report=verify_dataset(key,start,end,year)
    path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    tmp.replace(path)
    print("HS6 official category groups",len(report["items"]),"no firm-specific verification")
if __name__=="__main__":main()
