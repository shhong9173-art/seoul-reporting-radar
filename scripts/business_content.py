"""DART II. 사업의 내용 evidence discovery (conservative two-year pilot).

Only verified annual filings for directly covered companies. Tables/rows are
research evidence, not a normalized metric series or an exclusive scoop.
Never compare magnitudes across reports without identical unit, row definition,
period and filing scope. No guessed backlog/capacity deltas.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import zipfile
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dart_corrections import Tables
from dart_numeric_extractor import decode_web_bytes, html_to_text

KST=timezone(timedelta(hours=9))
EXTRACTION_VERSION="heading-scope-v2"
# Direct beat companies with verified legal corp codes in dart_corp_codes.json.
# Missing company codes and source failures remain explicit non-results.
CORPS=("HD현대일렉트릭","엘에스일렉트릭","효성중공업",
       "현대자동차","기아","현대모비스","현대위아","HL만도",
       "금호타이어","한국타이어앤테크놀로지",
       "현대제철","세아제강","포스코","동국제강","고려아연","영풍",
       "두산에너빌리티","대한전선","일진전기",
       "한화솔루션","OCI홀딩스",
       # 11-01 기자 명시: 석유화학·정유(분기보고서의 생산능력·가동률)
       "LG화학","롯데케미칼","금호석유화학","S-Oil","SK이노베이션","HD현대오일뱅크")
TOPICS={
    "orderBacklog":("수주잔고","수주상황"),
    "productionCapacity":("생산능력",),
    "utilization":("가동률","평균가동률"),
    "segmentSales":("매출실적","제품별매출","사업부문별매출"),
    "productionActual":("생산실적",),
    "investment":("진행중인투자","향후투자계획","설비의신설"),
}
LABELS={"orderBacklog":"수주잔고","productionCapacity":"생산능력",
        "utilization":"가동률","segmentSales":"제품·사업부별 매출",
        "productionActual":"생산실적","investment":"진행·계획 투자"}
DATE_RE=re.compile(r"\d{8}\Z")
RECEIPT_RE=re.compile(r"\d{14}\Z")
UNIT_RE=re.compile(r"(?:단위\s*[:：]\s*|\(\s*단위\s*[:：]\s*)(백만원|천원|억원|원|천달러|백만달러|USD|MVA|MW|GW|대|톤|%|시간|천대|만대)\b",re.I)
TAG_RE=re.compile(r"<[^>]+>")
TABLE_RE=re.compile(r"<table\b[^>]*>[\s\S]*?</table>",re.I)
SECTION_RE=re.compile(r"<section-1\b[^>]*>",re.I)
TITLE_RE=re.compile(r"<title\b[^>]*>(.*?)</title>",re.I|re.S)
ANNUAL_RE=re.compile(r"(?:^\[기재정정\])?사업보고서\s*\(\s*(\d{4})\s*\.\s*12\s*\)",re.I)


def api_json(url):
    with urlopen(Request(url,headers={"User-Agent":"newsroom-business-disclosures/1.0"}),timeout=15) as res:
        raw=res.read(2_000_001)
    if len(raw)>2_000_000:
        raise ValueError("OpenDART 목록 응답 크기 초과")
    return json.loads(raw.decode("utf-8-sig"))


def api_bytes(url):
    with urlopen(Request(url,headers={"User-Agent":"newsroom-business-disclosures/1.0",
                                     "Accept":"application/zip,*/*"}),timeout=25) as res:
        raw=res.read(35_000_001)
    if len(raw)>35_000_000:
        raise ValueError("OpenDART 원문 압축파일 크기 초과")
    return raw


def annual_receipt(key,corp_code,year,fetch=api_json):
    """Require issuer, 12-month FY and official category, then latest correction."""
    if not key or not re.fullmatch(r"\d{8}",str(corp_code)) or not 2015<=int(year)<=2035:
        raise ValueError("DART 키·고유번호·연도 없음")
    filing_year=year+1
    if filing_year>datetime.now(KST).year:
        return {"status":"not_due","receiptNo":None}
    url="https://opendart.fss.or.kr/api/list.json?"+urlencode({
        "crtfc_key":key,"corp_code":corp_code,
        "bgn_de":f"{filing_year}0101",
        "end_de":datetime.now(KST).strftime("%Y%m%d") if filing_year==datetime.now(KST).year else f"{filing_year}1231",
        "pblntf_ty":"A","page_count":100,"page_no":1})
    data=fetch(url)
    if data.get("status")=="013":
        return {"status":"no_annual_report","receiptNo":None}
    if data.get("status")!="000":
        raise RuntimeError("공시 목록 API 오류 "+str(data.get("status")))
    if int(data.get("total_page",1))!=1:
        raise ValueError("공시 목록 100개 초과: 페이지 처리되지 않은 결과 사용 금지")
    matches=[]
    for row in data.get("list",[]):
        if row.get("corp_code")!=corp_code:
            continue
        number=row.get("rcept_no")
        title=re.sub(r"\s+","",row.get("report_nm",""))
        match=ANNUAL_RE.fullmatch(title)
        if match and int(match[1])==year and RECEIPT_RE.fullmatch(str(number or "")):
            matches.append(row)
    if not matches:
        return {"status":"no_matching_report","receiptNo":None}
    chosen=max(matches,key=lambda r:(r.get("rcept_dt",""),r["rcept_no"]))
    return {"status":"found","receiptNo":chosen["rcept_no"],
            "reportName":chosen.get("report_nm"),"published":chosen.get("rcept_dt"),
            "url":f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={chosen['rcept_no']}"}


def fetch_report(key,receipt,fetch=api_bytes):
    if not key or not RECEIPT_RE.fullmatch(str(receipt)):
        raise ValueError("DART 원문 조회 키·접수번호 없음")
    url="https://opendart.fss.or.kr/api/document.xml?"+urlencode({"crtfc_key":key,"rcept_no":receipt})
    payload=fetch(url)
    if not zipfile.is_zipfile(io.BytesIO(payload)):
        raise RuntimeError("공시 원문 응답 ZIP 아님 (API 오류 가능)")
    docs=[]
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        infos=archive.infolist()
        if len(infos)>80 or sum(info.file_size for info in infos)>80_000_000:
            raise ValueError("ZIP 문서 수·비압축 크기 한도 초과")
        for info in infos:
            if info.is_dir() or not info.filename.lower().endswith((".xml",".html",".htm")):
                continue
            if info.file_size>50_000_000:
                raise ValueError("개별 원문 비압축 크기 한도 초과")
            text=decode_web_bytes(archive.read(info))
            docs.append((info.filename,text))
    if not docs:
        raise ValueError("ZIP 내부에서 분석 가능한 원문 없음")
    # Trust only explicit II section, not a company-wide keyword scan.
    candidates=[(name,section) for name,markup in docs
                if (section:=business_section(markup)) is not None]
    if not candidates:
        return {"status":"section_not_found","document":None,"section":None}
    name,section=max(candidates,key=lambda x:len(x[1]))
    return {"status":"found","document":name,"section":section}


def plain(raw):
    return re.sub(r"\s+"," ",html_to_text(str(raw).encode("utf-8"))).strip()


def business_section(markup):
    """A top-level SECTION-1 title precisely identifying II. 사업의 내용."""
    starts=list(SECTION_RE.finditer(markup))
    for i,match in enumerate(starts):
        segment=markup[match.end():(starts[i+1].start() if i+1<len(starts) else len(markup))]
        title=TITLE_RE.search(segment[:2500])
        if not title:
            continue
        norm=re.sub(r"[\s·.]","",plain(title[1]))
        if re.fullmatch(r"(?:II|Ⅱ|2)사업의내용",norm,re.I):
            return segment[:20_000_000]
    return None


def classify_table(markup,context):
    """Nearest explicit topic in the heading, rather than historical
    keywords earlier in the document, determines the table type."""
    words=re.sub(r"\s+","",context[-320:])
    # '생산능력' in a footnote before '생산실적' must NOT turn
    # production results into physical capacity.
    anchors={
        "orderBacklog":("수주상황","수주잔고"),
        "productionCapacity":("생산능력",),
        "utilization":("가동률",),
        "segmentSales":("매출실적","매출현황"),
        "productionActual":("생산실적",),
        "investment":("진행중인투자","향후투자계획","설비의신설","신설ㆍ매입계획"),
    }
    hits=[(words.rfind(x),topic) for topic,keys in anchors.items()
          for x in keys if x in words]
    if not hits:
        return None
    hits.sort(reverse=True)
    if len(hits)>1 and hits[0][0]==hits[1][0]:
        return None
    return hits[0][1]


def explicit_table_unit(context,table):
    """Reject mixed currency/physical-unit tables and ambiguous headings."""
    preceding=re.sub(r"<[^>]+>"," ",context[-380:])
    matches=list(re.finditer(r"단위\s*[:：]\s*([^)<>。]{1,75})",preceding,re.I))
    if not matches:
        return None
    clause=matches[-1].group(1).strip()
    # An authoritative heading must include exactly one known unit.
    # Some tables show thousands of RMB/USD and KRW simultaneously.
    if any(t in clause for t in (",","，","및","/","천RMB","천INR","천USD")):
        return None
    unit_match=re.match(r"^(백만원|천원|억원|원|MVA|MW|GW|대|톤|%|시간|천대|만대)(?![가-힣A-Za-z0-9])",clause,re.I)
    return unit_match.group(1) if unit_match else None

def table_rows(table):
    parser=Tables()
    parser.feed(table)
    valid=[]
    for t in parser.tables:
        if t["ambiguous"]:
            continue
        for row in t["rows"][:45]:
            if any(spanned for _,spanned in row) or len(row)<2:
                continue
            cells=[c.strip() for c,_ in row]
            if any(len(c)>200 for c in cells):
                continue
            if any(re.search(r"\d[\d,.]*",c) for c in cells[1:]):
                valid.append(cells[:7])
    return valid[:7]


def evidence_tables(section,receipt):
    evidence=[]
    counts=defaultdict(int)
    position=0
    heading=""
    topic=None
    owner=""
    for match in TABLE_RE.finditer(section):
        # Read structural headings outside tables. Footnotes belong to the
        # preceding table and cannot rename the next subsidiary's metric.
        gap=section[position:match.start()]
        position=match.end()
        lines=re.split(r"</?(?:p|title|br)\b[^>]*>",gap,flags=re.I)
        for line in lines:
            text=plain(line)
            owners=re.findall(r"\[([^\[\]]{2,70})\]",text)
            if owners:
                owner=re.sub(r"\s+","",owners[-1])
            title=re.sub(r"^(?:[가-힣A-Za-z0-9]+[.)]|\([가-힣A-Za-z0-9]+\))\s*","",text).strip()
            title=re.sub(r"\s*\[.*?\]\s*$","",title)
            title=re.sub(r"\s*\(?단위\s*[:：].*$","",title).strip()
            if not title or len(title)>65 or re.match(r"(?:주\d*\)|※|작성기준|산출근거)",text):
                continue
            compact=re.sub(r"\s+","",title)
            topics=[t for t,words in TOPICS.items() if any(w in compact for w in words)]
            if topics and (re.match(r"^(?:생산능력|생산실적|당.*가동률|평균가동률|가동률|매출|수주|진행|향후|설비)",compact)):
                topic=topics[0] if len(topics)==1 else None
                heading=title
            elif re.match(r"^(?:[가-힣A-Za-z0-9]+[.)]|\([가-힣A-Za-z0-9]+\))\s",text):
                topic=None
                heading=""
        chunk=match.group(0)
        if len(chunk)>160_000 or re.search(r"<table\b",chunk[6:],re.I):
            continue
        context=plain(section[max(0,match.start()-500):match.start()])
        if not topic or counts[(topic,owner)]>=4:
            continue
        rows=table_rows(chunk)
        if not rows:
            continue
        # Only accept a unit if it is explicitly present and unambiguous.
        unit=explicit_table_unit(context,chunk)
        count_key=(topic,owner)
        counts[count_key]+=1
        evidence.append({"topic":topic,"topicName":LABELS[topic],
                         "receiptNo":receipt,"unit":unit,
                         "context":heading+" "+("["+owner+"] " if owner else "")+("(단위: "+unit+")" if unit else ""),
                         "reportingEntity":owner,"classificationHeading":heading,
                         "extractionVersion":EXTRACTION_VERSION,
                         "rows":rows,
                         "comparisonStatus":"표 발췌 · 표 항목/기간/단위 재확인 필요"})
    return evidence


def cross_year_pairs(older,newer):
    """Show paired source tables only if both sides expose the same unit.

    This is NOT an automatic numerical comparison; table columns or report
    scopes can change despite matching topic/unit.
    """
    pairs=[]
    for topic in TOPICS:
        previous=[x for x in older if x["topic"]==topic]
        current=[x for x in newer if x["topic"]==topic]
        if len(previous)==1 and len(current)==1 and previous[0].get("unit") and previous[0]["unit"]==current[0].get("unit"):
            pairs.append({
                "topic":topic,"topicName":LABELS[topic],"unit":previous[0]["unit"],
                "before":previous[0],"after":current[0],
                "status":"동일 주제·표시 단위 후보, 비교 열·사업범위 확인 전",
                "numericChange":None,
                "needsManualVerification":True})
    return pairs


def scan_company(name,code,year,key,list_fetch=annual_receipt,doc_fetch=fetch_report):
    result={"company":name,"corpCode":code,"periods":{},"pairs":[],
            "status":"review_required","questions":[
                "표에 제시된 기준 기간·수량 단위·연결/별도 범위가 같은가?",
                "제품군·사업장·고객사 변경이 수주잔고 또는 생산능력에 미치는 실제 영향은?",
                "같은 사실이 기업 IR과 기존 산업전문지에 이미 공개됐는가?"
            ]}
    for y in (year-1,year):
        record={"year":y,"status":"not_checked","receiptNo":None,"tables":[]}
        result["periods"][str(y)]=record
        try:
            listing=list_fetch(key,code,y)
            record.update(listing)
            if listing["status"]!="found":
                continue
            doc=doc_fetch(key,listing["receiptNo"])
            if doc["status"]!="found":
                record["status"]=doc["status"]
                continue
            record["documentName"]=doc["document"]
            record["tables"]=evidence_tables(doc["section"],listing["receiptNo"])
            record["status"]="evidence_found" if record["tables"] else "no_supported_tables"
        except (ValueError,RuntimeError,URLError,TimeoutError,zipfile.BadZipFile) as error:
            record["status"]="source_error"
            record["errorType"]=type(error).__name__
    old,new=result["periods"][str(year-1)],result["periods"][str(year)]
    result["pairs"]=cross_year_pairs(old["tables"],new["tables"])
    result["status"]="source_pairs_to_review" if result["pairs"] else "insufficient_comparable_evidence"
    return result


def build_report(codes,key,year=2025,names=CORPS,scan=scan_company):
    records=[]
    for name in names:
        obj=codes.get(name)
        corp=obj.get("corp_code") if isinstance(obj,dict) else None
        if not isinstance(corp,str) or not re.fullmatch(r"\d{8}",corp):
            records.append({"company":name,"status":"corp_code_unavailable","periods":{},"pairs":[]})
        else:
            records.append(scan(name,corp,year,key))
    statuses={s:sum(x["status"]==s for x in records)
              for s in sorted({x["status"] for x in records})}
    return {
        "generatedAt":datetime.now(KST).isoformat(timespec="seconds"),
        "reportYear":year,"priorYear":year-1,
        "source":"OpenDART list.json + 사업보고서 document.xml 원문",
        "scope":"직접 출입처 완성차·부품·타이어·철강·비철·전력기기·에너지 21개사 · II. 사업의 내용",
        "basis":"공식 원문 사업의 내용에서 수주·생산·가동·매출 표를 발췌. 표 간 원시 숫자 자동 비교 금지",
        "statuses":statuses,"companies":records,
        "candidatePairs":sum(len(x.get("pairs",[])) for x in records),
        "verifiedNumericChanges":0,
        "scoopStatus":"단독 판단 불가: 사업범위·보도·회사 확인 전",
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--codes",default="dart_corp_codes.json")
    p.add_argument("--output",default="digests/business_content_latest.json")
    p.add_argument("--year",type=int,default=datetime.now(KST).year-1)
    args=p.parse_args()
    if not 2020<=args.year<datetime.now(KST).year:
        p.error("공시가 완료된 과거 연도만 비교")
    key=os.environ.get("DART_API_KEY","").strip()
    if not key:
        raise SystemExit("DART_API_KEY 미설정: 기존 증거 파일 보존")
    codes=json.loads(Path(args.codes).read_text(encoding="utf-8")).get("companies",{})
    report=build_report(codes,key,args.year)
    checks=[record for record in report["companies"] if record["status"]!="corp_code_unavailable"]
    successes=sum(any(r.get("status")=="evidence_found" for r in rec["periods"].values()) for rec in checks)
    if not successes:
        raise SystemExit("원문 사업내용 추출 성공 0개사: 이전 JSON 보존, 원문 형식 확인 필요")
    path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    temp.replace(path)
    print(f"사업내용 추출 성공 회사 {successes}/{len(checks)}, 수동 대조 후보표 {report['candidatePairs']}개. 자동 단독 확정 없음.")


if __name__=="__main__":
    main()
