"""Source-delta investigation engine: changed facts in two REAL DART filings.

This is /hunt -> /check -> /desk, not a single-publication keyword filter.
A source-supported change earns a reporter verification card; no programmatic
exclusive certification. Physical construction/operation dates cannot be
inferred from investment plan date ranges.
"""
from __future__ import annotations

import argparse
import json
import html
import re
import xml.etree.ElementTree as ET
from urllib.parse import quote
from urllib.request import Request, urlopen
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from business_content import CORPS

KST=timezone(timedelta(hours=9))
RECEIPT=re.compile(r"\d{14}\Z")
NUMERIC=re.compile(r"\d{1,3}(?:,\d{3})*(?:\.\d+)?\Z|\d+(?:\.\d+)?\Z")
PERIOD=re.compile(r"^'?(?P<sy>\d{2}|\d{4})\.(?P<sm>0[1-9]|1[0-2])\s*~\s*'?(?P<ey>\d{2}|\d{4})\.(?P<em>0[1-9]|1[0-2])$")
GENERIC={"신규","확장","경상","합계","소계","자산형태","기타","해외법인외","미국공장",
         "슬로박공장","멕시코공장","인도공장"}
TOPIC="investment"


def normalize(s):
    return re.sub(r"[\s*()'·ㆍ,./_-]","",str(s or "")).lower()


def year(number):
    n=int(number)
    return 2000+n if n<100 else n


def months(date):
    return date[0]*12+date[1]


def investment_period(raw):
    m=PERIOD.fullmatch(str(raw or "").strip())
    if not m:
        return None
    start=(year(m["sy"]),int(m["sm"]))
    end=(year(m["ey"]),int(m["em"]))
    if end<start or not 2010<=start[0]<=2035 or not 2010<=end[0]<=2040:
        return None
    return {"start":start,"end":end,
            "startLabel":f"{start[0]}.{start[1]:02d}",
            "endLabel":f"{end[0]}.{end[1]:02d}"}


def amount(value):
    raw=str(value or "").strip()
    if not NUMERIC.fullmatch(raw):
        return None
    try:
        n=Decimal(raw.replace(",",""))
        return n if n.is_finite() and n>=0 else None
    except InvalidOperation:
        return None


def qualify(table,row):
    """Only named, full-width, same-schema 'ongoing investment' rows."""
    if table.get("topic")!=TOPIC or table.get("unit")!="백만원":
        return None
    context=normalize(table.get("context"))
    if "진행중인투자" not in context:
        return None
    if not isinstance(row,list) or len(row)!=7:
        return None
    name=str(row[0]).strip()
    key=normalize(name)
    if (not 4<=len(key)<=52 or key in GENERIC
        or re.search(r"(?:법인外|법인외|성장동력확보)",name)
        or re.fullmatch(r"\d.*",name)):
        return None
    # A factory or identifiable production investment, not generic plans.
    if not any(word in key for word in ("공장","캠퍼스","자동화설비","증설","신축","라인")):
        return None
    timing=investment_period(row[1])
    total=amount(row[4])
    descriptor=(normalize(row[2]),normalize(row[3]))
    if not timing or total is None or not all(descriptor):
        return None
    return {"project":name,"key":key,"schedule":timing,"totalMillionWon":total,
            "descriptor":descriptor,"sourceRow":row,"receiptNo":table.get("receiptNo"),
            "unit":table["unit"]}


def by_project(tables):
    groups={}
    for t in tables or []:
        for row in t.get("rows",[]):
            parsed=qualify(t,row)
            if parsed is None:
                continue
            groups.setdefault(parsed["key"],[]).append(parsed)
    # A repeated name in different business-unit tables is ambiguous.
    return {key:items[0] for key,items in groups.items() if len(items)==1}


def verified_receipt(source):
    receipt=source.get("receiptNo") if isinstance(source,dict) else None
    return isinstance(receipt,str) and RECEIPT.fullmatch(receipt) is not None


def check_company(name,annual_company,recent_company):
    out={"company":name,"status":"not_comparable","updates":[],"checkedProjects":0,
         "rejectionReasons":[]}
    annuals=annual_company.get("periods",{}) if isinstance(annual_company,dict) else {}
    annual=annuals.get("2025",{})
    older=annuals.get("2024",{})
    current=recent_company.get("current") or {}
    if (annual.get("status")!="evidence_found" or current.get("status")!="evidence_found"
        or not verified_receipt(annual) or not verified_receipt(current)
        or annual.get("year") not in (None,2025) or current.get("year")!=2026
        or current.get("period") not in ("03","06","09")
        or annual["receiptNo"]==current["receiptNo"]):
        out["rejectionReasons"].append("2025 사업보고서/2026 최신 분기 원문·기준기간 일치 미확인")
        return out
    earlier=by_project(older.get("tables")) if older.get("status")=="evidence_found" else {}
    old=by_project(annual.get("tables"))
    new=by_project(current.get("tables"))
    out["checkedProjects"]=len(set(old)&set(new))
    for key in sorted(set(old)&set(new)):
        before=old[key];after=new[key]
        if before["descriptor"]!=after["descriptor"] or before["schedule"]["start"]!=after["schedule"]["start"]:
            out["rejectionReasons"].append("동일 투자명이나 제품/목적 또는 시작시점 차이: "+before["project"])
            continue
        prev_end=before["schedule"]["end"]
        curr_end=after["schedule"]["end"]
        shift=months(curr_end)-months(prev_end)
        change=after["totalMillionWon"]-before["totalMillionWon"]
        if not shift and not change:
            continue
        # One normalized project name, same products/purpose, same unit.
        # Public source row fields are retained intact for independent audit.
        prior_history=None
        if key in earlier:
            first=earlier[key]
            if (first["descriptor"]==before["descriptor"]
                and first["schedule"]["start"]==before["schedule"]["start"]):
                prior_history={
                    "receiptNo":older.get("receiptNo"),
                    "plannedEnd":first["schedule"]["endLabel"],
                    "plannedBudgetMillionWon":str(first["totalMillionWon"]),
                    "firstToAnnualMonths":months(prev_end)-months(first["schedule"]["end"]),
                }
        row={
            "company":name,"project":after["project"],"comparisonType":"투자계획의 공시 기재 변경",
            "fromPeriod":"2025년 연간 사업보고서",
            "toPeriod":"2026년 "+current.get("periodLabel","분기/반기보고서"),
            "fromPublished":annual.get("published"),
            "toPublished":current.get("published"),
            "oldPlannedEnd":before["schedule"]["endLabel"],
            "newPlannedEnd":after["schedule"]["endLabel"],
            "endMonthShift":shift,
            "oldBudgetMillionWon":str(before["totalMillionWon"]),
            "newBudgetMillionWon":str(after["totalMillionWon"]),
            "budgetChangeMillionWon":str(change),
            "unit":"백만원",
            "annualReceipt":annual["receiptNo"],"currentReceipt":current["receiptNo"],
            "originalUrls":[
                "https://dart.fss.or.kr/dsaf001/main.do?rcpNo="+annual["receiptNo"],
                "https://dart.fss.or.kr/dsaf001/main.do?rcpNo="+current["receiptNo"]],
            "sourceRows":[before["sourceRow"],after["sourceRow"]],
            "history2024":prior_history,
            "factVerified":"동일 투자명·기간 시작·사업 목적·원화 단위 표의 공시 기재값을 대조",
            "notProven":"투자 종료 예정월은 착공·준공·가동일과 같지 않음. 실제 지연·이익 영향·새로운 단독·원인은 회사 취재 전 미확인",
            "alreadyPublic":True,
            "coverage":{"status":"기존 기사 검색 미실행","articles":[]},
            "exclusiveStatus":"공개 원자료 변화 확인 · 미보도/단독 확인 전",
        }
        out["updates"].append(row)
    out["status"]="changed_in_official_reports" if out["updates"] else "no_supported_changes"
    return out


def desk_packet(group,as_of):
    changed=group["updates"]
    delayed=[r for r in changed if r["endMonthShift"]>0]
    advanced=[r for r in changed if r["endMonthShift"]<0]
    if not changed:
        return None
    score=min(95,40+12*len(delayed)+8*len(advanced)+
              8*sum(bool(r["history2024"]) and r["history2024"]["firstToAnnualMonths"]>0 for r in changed))
    company=group["company"]
    if delayed:
        headline=f"{company}, {len(delayed)}개 설비투자 항목의 공시상 종료 예정월 변경"
        angle=f"{company}의 {len(delayed)}개 생산·설비 투자는 2025년 사업보고서 대비 2026년 최신 보고서에서 종료 예정월이 늦춰져 기재됐다. 실제 준공·가동 지연인지는 확인되지 않았다."
    else:
        headline=f"{company}, 공식 투자계획 기재 변경 {len(changed)}건"
        angle=f"{company}의 최신 보고서에서 기존 투자계획 금액·예정 기간 수정이 확인됐다. 조정 배경과 사업 영향은 미확인이다."
    return {
        "company":company,"headline":headline,"angleConditional":angle,
        "priorityScore":score,
        "reporterStatus":"P1 원자료 변화 취재 착수" if score>=60 else "P2 공식 변화 재확인",
        "projects":changed,
        "coverageStatus":"선행 기사 동일 사건 여부 직접 확인 필요",
        "deskChecks":[
            "원문: 전기·당기 두 자료에서 동일 사업장·품목·투자 범위/단위인가?",
            "이미 나온 보도: 사업명·이전/변경 일정·금액이 전문지나 기존 IR에 공개됐는가?",
            "회사 확인: 투자 종료 예정월 수정과 실제 준공/가동·생산 일정 변경은 같은가?",
            "규모·영향: 달라진 기간이 수주 소화·생산량·출하/고객사에 영향을 주는가?",
            "반론: 일정이 아니라 회계 집행기간·인허가·신설사업 분류만 수정됐을 가능성은?",
        ],
        "deskVerdict":"발제 미확정: 회사 답변·기보도 사실 확인 후 보고",
    }


def targeted_press_search(query,fetch=None):
    """Target PROJECT name, not just generic company financial results."""
    company=str(query["company"])
    project=str(query["rowIdentity"][0])
    project=re.sub(r"\(\*\)|[＊*()]","",project).strip()[:55]
    search=f'{company} "{project}" when:365d'
    url="https://news.google.com/rss/search?q="+quote(search)+"&hl=ko&gl=KR&ceid=KR:ko"
    if fetch is None:
        def fetch(uri):
            req=Request(uri,headers={"User-Agent":"reporter-document-delta-hunt/1.0",
                                     "Accept":"application/rss+xml"})
            with urlopen(req,timeout=12) as result:
                data=result.read(600001)
            if len(data)>600000:
                raise ValueError("뉴스 RSS 크기 제한 초과")
            return data
    try:
        root=ET.fromstring(fetch(url))
        if root.tag!="rss" or root.find("channel") is None:
            raise ValueError("뉴스 RSS 응답 형식 오류")
        articles=[]
        for item in root.findall("./channel/item")[:15]:
            title=html.unescape(re.sub(r"<[^>]+>","",item.findtext("title") or "")).strip()[:220]
            link=str(item.findtext("link") or "")
            if title and link.startswith("https://news.google.com/"):
                articles.append({"title":title,"url":link,
                                "published":str(item.findtext("pubDate") or "")[:85]})
            if len(articles)>=4:
                break
        return {"query":search,"status":("관련 기사 검색됨: 사건·숫자·보도시점 동일성 재검증" if articles
                                           else "해당 검색어 결과 미발견: 미보도 여부 판단 불가"),
                "articles":articles}
    except (ValueError,TimeoutError,OSError,ET.ParseError) as exc:
        return {"query":search,"status":"보도 검색 실패: "+type(exc).__name__,
                "articles":[]}


def news_lookup(row,check=targeted_press_search):
    # Existing official-news helper applies strict direct-beat company
    # identity and bounded Google RSS with a one-year lookback.
    query={
        "company":row["company"],"topic":"investment","toYear":2026,
        "rowIdentity":[row["project"]]
    }
    try:
        found=check(query)
        return {"status":found.get("status","검색결과 불분명"),
                "articles":found.get("articles",[])[:4],
                "query":found.get("query"),
                "decision":"기사 내용/동일 사건을 직접 확인하기 전 미보도 또는 이미 보도로 확정 금지"}
    except (ValueError,TimeoutError,OSError,TypeError) as exc:
        return {"status":"언론 검색 오류: "+type(exc).__name__,
                "articles":[],"decision":"선행보도 미확인: 단독 아님"}


def build(annual,recent,now=None,fetch_news=None,news_limit=4):
    now=now or datetime.now(KST)
    if not isinstance(annual,dict) or not isinstance(recent,dict):
        raise ValueError("원자료 입력 형식 오류")
    if not isinstance(annual.get("companies"),list) or not isinstance(recent.get("companies"),list):
        raise ValueError("원자료 기업 목록 누락")
    if annual.get("reportYear")!=2025 or recent.get("businessYear")!=2026:
        raise ValueError("2025 사업보고서와 2026 최신 자료가 아님")
    index={c.get("company"):c for c in annual["companies"] if isinstance(c,dict)}
    investigations=[]
    diagnostics=[]
    for company in CORPS:
        old=index.get(company)
        curr=next((c for c in recent["companies"] if c.get("company")==company),None)
        if old is None or curr is None:
            diagnostics.append({"company":company,"status":"official_source_missing"})
            continue
        group=check_company(company,old,curr)
        diagnostics.append({"company":company,"status":group["status"],
                            "checkedProjects":group["checkedProjects"],
                            "changedRows":len(group["updates"]),
                            "rejections":group["rejectionReasons"][:5]})
        card=desk_packet(group,now)
        if card:
            investigations.append(card)
    investigations.sort(key=lambda x:(-x["priorityScore"],x["company"]))
    quota=news_limit
    for card in investigations:
        for r in card["projects"]:
            if quota<=0 or fetch_news is None:
                continue
            r["coverage"]=news_lookup(r,fetch_news)
            quota-=1
    return {
        "generatedAt":now.isoformat(timespec="seconds"),
        "annualDataAt":annual.get("generatedAt"),
        "interimDataAt":recent.get("generatedAt"),
        "status":"source_changes_detected_not_exclusive",
        "method":"같은 회사·투자명·사업목적·기간시작·백만원 단위 원문 행의 2025 사업보고서/2026 최신 분기보고서 직접 비교",
        "warning":"원문 변경 시점과 실제 사건 발생 시점은 다름. 종료 예정월 변경=준공 지연 아님. 기사 선행 보도, 반론, 회사답변 전 단독 판정 금지",
        "investigationCount":len(investigations),
        "verifiedChangeCount":sum(len(x["projects"]) for x in investigations),
        "scoopConfirmed":0,
        "diagnostics":diagnostics,
        "investigations":investigations,
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--annual",default="digests/business_content_latest.json")
    ap.add_argument("--recent",default="digests/recent_business_latest.json")
    ap.add_argument("--output",default="digests/investigation_hunt_latest.json")
    ap.add_argument("--max-news",type=int,default=4)
    args=ap.parse_args()
    if not 0<=args.max_news<=8:
        ap.error("보도검색 상한 0~8")
    annual=json.loads(Path(args.annual).read_text(encoding="utf-8"))
    recent=json.loads(Path(args.recent).read_text(encoding="utf-8"))
    result=build(annual,recent,fetch_news=(targeted_press_search if args.max_news else None),
                 news_limit=args.max_news)
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
    tmp=output.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    tmp.replace(output)
    print(f"독립 원문 비교 {result['verifiedChangeCount']}개 수정 사실, "
          f"취재 묶음 {result['investigationCount']}건, 단독 확정 0건")


if __name__=="__main__":
    main()
