"""Recent quarterly / half-year DART business-content evidence scout.

Pulls the latest AVAILABLE current-year interim report for directly covered
companies and the previous year's EXACT MATCHING reporting period. This
produces source-grounded reporting leads, not numeric changes or scoops.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlencode

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from business_content import (api_json,fetch_report,evidence_tables,CORPS,EXTRACTION_VERSION)
from business_coverage import check_one

KST=timezone(timedelta(hours=9))
RECEIPT_RE=re.compile(r"\d{14}\Z")
CORP_RE=re.compile(r"\d{8}\Z")
REPORT_RE=re.compile(r"^(?:\[(?:기재정정|첨부정정)\])?(반기보고서|분기보고서)\((20\d{2})\.(03|06|09)\)$")
KIND={"03":"1분기","06":"반기","09":"3분기"}
TOPIC_LABEL={"investment":"설비투자","orderBacklog":"수주잔고",
             "productionCapacity":"생산능력","productionActual":"생산실적",
             "segmentSales":"제품·사업별 매출","utilization":"가동률"}
GENERIC={"합계","합 계","총계","소계","구분","합 계액","사업부문","공장","내수","수출","기타"}
SCOUT_COMPANIES=CORPS


def reports_for_year(key,corp_code,year,fetch=api_json,now=None):
    now=now or datetime.now(KST)
    if not key or not CORP_RE.fullmatch(str(corp_code)) or not 2018<=int(year)<=now.year:
        raise ValueError("공시 검색 회사 코드 또는 연도 오류")
    begin=f"{year}0101"
    end=(now.strftime("%Y%m%d") if year==now.year else f"{year}1231")
    url="https://opendart.fss.or.kr/api/list.json?"+urlencode({
        "crtfc_key":key,"corp_code":corp_code,"bgn_de":begin,"end_de":end,
        "last_reprt_at":"N","pblntf_ty":"A","page_count":100,"page_no":1})
    result=fetch(url)
    if not isinstance(result,dict):
        raise ValueError("공시 검색 응답 형식 오류")
    if result.get("status")=="013":
        return []
    if result.get("status")!="000":
        raise RuntimeError("DART 공시검색 API 응답 오류 "+str(result.get("status")))
    if int(result.get("total_page",1))>1:
        raise ValueError("공시 페이지 누락 위험: 100건 초과 결과는 확인하지 않음")
    rows=[]
    for r in result.get("list",[]):
        if not isinstance(r,dict) or r.get("corp_code")!=corp_code:
            continue
        receipt=str(r.get("rcept_no") or "")
        title=re.sub(r"\s+","",r.get("report_nm") or "")
        m=REPORT_RE.fullmatch(title)
        if not m or not RECEIPT_RE.fullmatch(receipt):
            continue
        report_type,fy,month=m.groups()
        if int(fy)!=year or (month=="06")!=(report_type=="반기보고서"):
            continue
        if report_type=="분기보고서" and month not in ("03","09"):
            continue
        # Future-dated receipt is not trusted.
        filed=str(r.get("rcept_dt") or "")
        if not re.fullmatch(r"20\d{6}",filed) or filed>now.strftime("%Y%m%d"):
            continue
        rows.append({"period":month,"periodLabel":KIND[month],
                     "year":year,"receiptNo":receipt,"published":filed,
                     "reportName":r.get("report_nm"),
                     "url":"https://dart.fss.or.kr/dsaf001/main.do?rcpNo="+receipt})
    return rows


def select_period(reports):
    if not reports:
        return None
    # Latest financial PERIOD, not most recently corrected historical quarter.
    return max(reports,key=lambda r:(r["period"],r["published"],r["receiptNo"]))


def matching_prior(reports,period):
    same=[r for r in reports if r["period"]==period]
    return max(same,key=lambda r:(r["published"],r["receiptNo"])) if same else None


def extracted_sections(key,filing,doc_fetch=fetch_report):
    doc=doc_fetch(key,filing["receiptNo"])
    if doc.get("status")!="found":
        return {"status":doc.get("status","unknown"),"tables":[]}
    tables=evidence_tables(doc["section"],filing["receiptNo"])
    return {"status":"evidence_found" if tables else "no_supported_tables",
            "documentName":doc.get("document"),"tables":tables}


def normalized_name(raw):
    return re.sub(r"[\s()_,·ㆍ.'\[\]-]","",str(raw or "")).lower()


def project_rows(evidence):
    """These are EXCERPTS, not a complete investment ledger."""
    projects=[]
    for table in evidence:
        if table.get("topic")!="investment":
            continue
        for row in table.get("rows",[]):
            if not isinstance(row,list) or len(row)<2:
                continue
            name=str(row[0]).strip()
            compact=normalized_name(name)
            if not 4<=len(compact)<=42 or name in GENERIC:
                continue
            if re.fullmatch(r"[\d,.%()'-]+",name):
                continue
            # Dates, legal-entity category totals and vague strategic
            # descriptions are not an identified factory/project.
            if (re.search(r"20\d{2}\s*년.*(?:~|부터|까지|20\d{2})",name)
                or re.search(r"(?:^해외법인|^국내법인|^기타법인|^미래\s*성장동력)",name)
                or re.fullmatch(r"(?:미국|멕시코|슬로박|중국|인도|체코|유럽)공장",name)):
                continue
            if not re.search(r"(?:공장|캠퍼스|설비|라인|신축|증설|증축|건립|부지|프로젝트|공정|발전소|데이터센터)",name):
                continue
            # Evidence rows need an actual schedule or number; narrative-only
            # fragments are retained in context, not promoted as projects.
            if not any(re.search(r"\d",str(v)) for v in row[1:]):
                continue
            projects.append({"name":name[:90],"unit":table.get("unit"),
                             "row":row[:7],"context":table.get("context","")[-170:],
                             "receiptNo":table.get("receiptNo")})
    unique={}
    for row in projects:
        unique.setdefault(normalized_name(row["name"]),row)
    return list(unique.values())[:10]


def source_questions(topic):
    questions={
        "investment":[
            "해당 투자·사업장의 최초 발표 시점과 2025년 말 사업보고서·IR 기재 여부는?",
            "확정된 투자금액·실제 집행액·가동 개시 시점이 구분되는가?",
            "신설 설비가 추가 생산량·신규 수주에 기여하는 규모는 실제 얼마인가?"
        ],
        "orderBacklog":[
            "대상 계약·사업부·기준 통화·연결범위가 전년 동일 기간과 같은가?",
            "신규 수주액과 잔고, 취소·환율 변화가 구분되는가?"
        ],
    }
    return questions.get(topic,[
        "해당 표의 비교 기간·단위·제품·사업장·연결범위가 동일한가?",
        "과거 발표·언론 기사와 비교했을 때 신규 사실이 무엇인가?",
        "기업이 확인한 실제 생산·판매·수주 영향은 무엇인가?"
    ])


def signals_from_company(company,old,current,period):
    current_tables=current.get("tables",[])
    prior_tables=old.get("tables",[])
    signals=[]
    current_projects=project_rows(current_tables)
    old_projects={normalized_name(x["name"]) for x in project_rows(prior_tables)}
    for p in current_projects[:6]:
        was_seen=normalized_name(p["name"]) in old_projects
        signals.append({
            "company":company,"topic":"investment","topicName":"설비투자",
            "project":p["name"],"currentRow":p["row"],
            "currentUnit":p["unit"],"period":period,
            "priorExcerptContainsName":was_seen,
            "observation":("동일 이름이 전년 동기 발췌 행에서도 발견됨" if was_seen else
                           "전년 동기 발췌 행에는 동일 이름이 없음(표 일부만 분석·신규 투자 확정 아님)"),
            "currentReceipt":current["receiptNo"],"priorReceipt":old["receiptNo"],
            "sourceUrls":[current["url"],old["url"]],
            "coverage":{"status":"언론 선행 보도 미검색"},
            "questions":source_questions("investment"),
            "status":"공식 공개 원문 취재 단서 · 단독 미확정",
        })
    # General topics are shown as table-evidence counts only, because one
    # reporting period's cumulative financial columns can be structured
    # differently from the previous year's report.
    return signals


def scan_company(company,corp_code,key,year,list_fetch=reports_for_year,
                 doc_fetch=fetch_report,cache_record=None):
    item={"company":company,"corpCode":corp_code,"status":"not_checked","extractionVersion":EXTRACTION_VERSION,
          "current":None,"priorSamePeriod":None,"signals":[],"topicCounts":{}}
    try:
        current_reports=list_fetch(key,corp_code,year)
        latest=select_period(current_reports)
        if latest is None:
            item["status"]="current_interim_not_found"
            return item
        past_reports=list_fetch(key,corp_code,year-1)
        past=matching_prior(past_reports,latest["period"])
        if past is None:
            item.update({"status":"prior_matching_interim_not_found",
                         "current":{**latest,"status":"not_fetched"}})
            return item
        # A checked, unchanged pair can reuse its original verified excerpts.
        # Revisit the API list every weekday so new reports/corrections are
        # noticed immediately, while avoiding redundant large ZIP downloads.
        if (isinstance(cache_record,dict)
            and cache_record.get("extractionVersion")==EXTRACTION_VERSION
            and cache_record.get("corpCode")==corp_code
            and cache_record.get("status")=="official_sections_retrieved"
            and (cache_record.get("current") or {}).get("receiptNo")==latest["receiptNo"]
            and (cache_record.get("priorSamePeriod") or {}).get("receiptNo")==past["receiptNo"]
            and (cache_record.get("current") or {}).get("status")=="evidence_found"
            and (cache_record.get("priorSamePeriod") or {}).get("status")=="evidence_found"):
            return {**cache_record,"cacheHit":True,
                    "listCheckedAt":datetime.now(KST).isoformat(timespec="seconds")}
        item["current"]={**latest,**extracted_sections(key,latest,doc_fetch)}
        item["priorSamePeriod"]={**past,**extracted_sections(key,past,doc_fetch)}
        recent=item["current"]
        old=item["priorSamePeriod"]
        item["topicCounts"]={t:sum(r["topic"]==t for r in recent.get("tables",[]))
                             for t in TOPIC_LABEL}
        if recent.get("status")!="evidence_found" or old.get("status")!="evidence_found":
            item["status"]="incomplete_original_sections"
            return item
        item["signals"]=signals_from_company(company,old,recent,latest["period"])
        item["status"]="official_sections_retrieved"
    except (ValueError,RuntimeError,URLError,TimeoutError,OSError,zipfile.BadZipFile) as error:
        item["status"]="source_error"
        item["errorType"]=type(error).__name__
    return item


def source_report(codes,key,year,names=SCOUT_COMPANIES,scan=scan_company,previous=None):
    records=[]
    for name in names:
        code=(codes.get(name) or {}).get("corp_code")
        if not isinstance(code,str) or not CORP_RE.fullmatch(code):
            records.append({"company":name,"status":"corp_code_unavailable",
                            "signals":[],"current":None,"priorSamePeriod":None})
        else:
            cached=next((r for r in (previous or {}).get("companies",[])
                         if r.get("company")==name),None)
            if cached:
                records.append(scan(name,code,key,year,cache_record=cached))
            else:
                records.append(scan(name,code,key,year))
    return {
        "generatedAt":datetime.now(KST).isoformat(timespec="seconds"),
        "unchangedCachedCount":sum(bool(x.get("cacheHit")) for x in records),
        "businessYear":year,
        "source":"OpenDART 정기공시 검색 list.json + document.xml 원문",
        "scope":"직접 출입처 분기·반기 최신 공시 대 전년 같은 보고기간",
        "method":"공시 시점·법인·보고기간 일치 검증 후 II. 사업의 내용 관련 표 일부 발췌, 투자 사업명 확인",
        "warning":"표 일부만 분석하며 원문에 없다는 증거가 아니다. 신규 투자·실제 사업 영향·기보도 여부·단독 여부 자동 확정 금지.",
        "companies":records,
        "retrievedCount":sum(x["status"]=="official_sections_retrieved" for x in records),
        "leadCount":sum(len(x.get("signals",[])) for x in records),
        "scoopCountConfirmed":0,
    }


def enrich_coverage(report,lookup=check_one,limit=6):
    """Bounded research searches; one lead per issuer first."""
    targets=[]
    by_company={}
    for record in report.get("companies",[]):
        if record.get("status")!="official_sections_retrieved":
            continue
        signal=next((s for s in record.get("signals",[]) if s["topic"]=="investment"),None)
        if signal:
            by_company[record["company"]]=signal
    targets=list(by_company.values())[:limit]
    for signal in targets:
        q={"company":signal["company"],"topic":signal["topic"],
           "toYear":report["businessYear"],"rowIdentity":[signal["project"]]}
        try:
            result=lookup(q)
        except (ValueError,URLError,TimeoutError,OSError) as ex:
            result={"status":"관련 기사 검색 오류: "+type(ex).__name__,"articles":[]}
        signal["coverage"]={"status":result["status"],"articles":result.get("articles",[])[:4],
                            "decision":"검색 결과가 없어도 단독·미보도 확정 금지"}
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--codes",default="dart_corp_codes.json")
    parser.add_argument("--out",default="digests/recent_business_latest.json")
    parser.add_argument("--year",type=int,default=datetime.now(KST).year)
    parser.add_argument("--max-news",type=int,default=6)
    args=parser.parse_args()
    now=datetime.now(KST)
    if not 2020<=args.year<=now.year or not 0<=args.max_news<=7:
        parser.error("연도/기보도 검색 최대 개수 오류")
    key=os.getenv("DART_API_KEY","").strip()
    if not key:
        raise SystemExit("DART_API_KEY 미설정: 기존 공식 탐지 파일 보존")
    codes=json.loads(Path(args.codes).read_text(encoding="utf-8")).get("companies",{})
    previous=None
    old_file=Path(args.out)
    if old_file.is_file():
        try:
            candidate=json.loads(old_file.read_text(encoding="utf-8"))
            if candidate.get("businessYear")==args.year and isinstance(candidate.get("companies"),list):
                previous=candidate
        except (ValueError,OSError,TypeError):
            pass
    report=source_report(codes,key,args.year,previous=previous)
    if report["retrievedCount"]<1:
        raise SystemExit("공식 당해·전년 분기/반기 원문 대조 성공 0개사: 기존 파일 보존")
    if args.max_news:
        enrich_coverage(report,limit=args.max_news)
    path=Path(args.out)
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    temp.replace(path)
    print(f"최신 분기·반기 공식 원문 {report['retrievedCount']}/{len(report['companies'])}개사, "
          f"투자 프로젝트 검증 대기 {report['leadCount']}건, 단독 확정 0건")


if __name__=="__main__":
    main()
