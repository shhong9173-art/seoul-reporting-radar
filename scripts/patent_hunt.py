"""KIPRISPlus official patent-publication reporting hunt.

Requires separately authorized KIPRISPlus 'Patent/Utility Publication' Open API
ServiceKey. No invented discoveries if access unavailable. Patent publication is
NOT a product launch, registration, approval, or proof of a scoop.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen

KST=timezone(timedelta(hours=9))
# Public KIPRISPlus REST documentation: getAdvancedSearch / applicant / openDate.
BASE="https://plus.kipris.or.kr/kipo-api/kipi/patUtiModInfoSearchSevice/getAdvancedSearch"
LANDING="https://plus.kipris.or.kr/eng/data/service/DBII_000000000000001/view.do?menuNo=300100&subTab=SC001"
LIMIT=100
MAX_PAGES=4
# Explicit Korean corporate names, not labels shortened to "현대", "LS", "포스코".
APPLICANTS={
 "현대자동차":("현대자동차주식회사","현대자동차 주식회사"),
 "기아":("기아주식회사","기아 주식회사"),
 "현대모비스":("현대모비스주식회사","현대모비스 주식회사"),
 "현대위아":("현대위아주식회사","현대위아 주식회사"),
 "HL만도":("주식회사에이치엘만도","주식회사 에이치엘만도"),
 "한국타이어앤테크놀로지":("한국타이어앤테크놀로지주식회사","한국타이어앤테크놀로지 주식회사"),
 "넥센타이어":("넥센타이어주식회사","넥센타이어 주식회사"),
 "금호타이어":("금호타이어주식회사","금호타이어 주식회사"),
 "현대제철":("현대제철주식회사","현대제철 주식회사"),
 "포스코":("주식회사포스코","주식회사 포스코"),
 "포스코홀딩스":("주식회사포스코홀딩스","주식회사 포스코홀딩스"),
 "동국제강":("동국제강주식회사","동국제강 주식회사"),
 "세아제강":("주식회사세아제강","주식회사 세아제강"),
 "고려아연":("고려아연주식회사","고려아연 주식회사"),
 "영풍":("주식회사영풍","주식회사 영풍"),
 "HD현대일렉트릭":("에이치디현대일렉트릭주식회사","에이치디현대일렉트릭 주식회사"),
 "LS일렉트릭":("엘에스일렉트릭주식회사","엘에스일렉트릭 주식회사"),
 "효성중공업":("효성중공업주식회사","효성중공업 주식회사"),
 "일진전기":("일진전기주식회사","일진전기 주식회사"),
 "대한전선":("대한전선주식회사","대한전선 주식회사"),
 "LS전선":("엘에스전선주식회사","엘에스전선 주식회사"),
 "두산에너빌리티":("두산에너빌리티주식회사","두산에너빌리티 주식회사"),
 "한화솔루션":("한화솔루션주식회사","한화솔루션 주식회사"),
 "OCI":("오씨아이주식회사","오씨아이 주식회사"),
}
# Short, cross-company names are intentionally not queried unguarded.
# Unlisted corporate aliases/renames require manual checking before addition.
TERMS={
 "자율주행·SDV":("자율주행","자율 주행","소프트웨어 정의","차량제어","차량 제어","원격주차","원격 주차","라이다","센서융합","경로계획","모빌리티 서비스"),
 "전기차·배터리":("배터리","전고체","급속충전","초급속","충전제어","열폭주","배터리 관리","셀밸런싱","v2g","양방향 충전","bms"),
 "수소·연료전지":("수소 저장","수소생산","수전해","연료전지","수소 연소","액화수소"),
 "전력망·HVDC":("hvdc","직류송전","직류 송전","변압기","변압","고압직류","초고압직류","차단기","전력변환","전력 변환","dc-dc","dc/dc"),
 "저탄소 제철":("전기로","직접환원","환원철","수소환원","탄소포집","탄소 포집","저탄소","열연강판","냉연강판","용융아연","도금강판"),
 "순환소재·폐차재활용":("효소","효소적","생분해","해중합","화학적 재활용","재활용","플라스틱","폐플라스틱","폐차","폐자동차","폴리에스테르","폴리에틸렌테레프탈레이트","페트","pet","재생원료","재생 원료","단량체","열분해","자동차 내장재"),
 "공장·제조 자동화":("무인운반","무인이송","협동로봇","공정제어","제조공정","자동화설비","생산라인"),
}
DATE8=re.compile(r"20\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\Z")
PATENT_NUMBER=re.compile(r"[\d-]{10,22}\Z")


def normalize(name):
    return re.sub(r"[\s()（）·ㆍ.,_-]","",str(name or "")).lower()


def applicant_matches(raw,expected):
    if not raw or not expected:
        return False
    # Multiple legal applicants are separated by '|' in the official API;
    # each co-applicant must match a complete allowed legal name.
    actual=[normalize(x) for x in re.split(r"[|;]",raw)]
    return any(normalize(variant) in actual for variant in expected)


def parse_response(xml_bytes):
    if isinstance(xml_bytes,str):
        xml_bytes=xml_bytes.encode("utf-8")
    if len(xml_bytes)>2_000_000:
        raise ValueError("KIPRIS 응답 상한 초과")
    if b"<!DOCTYPE" in xml_bytes.upper() or b"<!ENTITY" in xml_bytes.upper():
        raise ValueError("외부 XML 엔터티 허용 안 함")
    root=ET.fromstring(xml_bytes)
    if root.tag!="response":
        raise ValueError("KIPRIS 공식 API XML response 루트 불일치")
    code=root.findtext("./header/resultCode")
    if code not in (None,"00","0"):
        raise RuntimeError("KIPRISPlus 응답 오류 코드 "+str(code))
    n=root.findtext(".//count/totalCount")
    if n is None:
        n=root.findtext(".//totalCount")
    if n is None or not n.strip().isdigit():
        raise ValueError("KIPRIS 특허 결과 totalCount 누락(검색 0건으로 판단 금지)")
    items=[]
    for node in root.findall(".//items/item"):
        row={child.tag:(child.text or "").strip() for child in node}
        items.append(row)
    return {"total":int(n),"items":items}


def request_xml(url):
    # Never log or persist the key embedded in this request URL.
    req=Request(url,headers={"User-Agent":"newsroom-kipris-evidence/1.0",
                             "Accept":"application/xml"})
    with urlopen(req,timeout=20) as answer:
        response=answer.read(2_000_001)
    return response


def search_applicant(key,term,from_date,to_date,fetch=request_xml,max_pages=MAX_PAGES):
    """Complete a date range using recursive nonoverlapping windows.

    KIPRISPlus pages are capped at 100 rows. When the four-page budget
    cannot cover a company, split by disclosure date instead of silently
    dropping later records. A single over-capacity day remains explicitly
    INCOMPLETE and must not replace a previously verified snapshot.
    """
    if not key or not term or not DATE8.fullmatch(from_date) or not DATE8.fullmatch(to_date):
        raise ValueError("KIPRIS 검색 인증키/공개일/출원인 값 이상")
    if from_date>to_date or not 1<=max_pages<=4:
        raise ValueError("KIPRIS 기간·페이지 범위 오류")
    first=datetime.strptime(from_date,"%Y%m%d").date()
    last=datetime.strptime(to_date,"%Y%m%d").date()
    total_requests=0
    windows=[]

    def query_day_range(left,right):
        nonlocal total_requests
        begin=left.strftime("%Y%m%d")
        finish=right.strftime("%Y%m%d")
        def page_request(page):
            nonlocal total_requests
            if fetch is request_xml and total_requests:
                time.sleep(0.18)
            params={
                "applicant":term,"openDate":begin+"~"+finish,
                "patent":"true","utility":"false",
                "sortSpec":"OPD","descSort":"true",
                "pageNo":str(page),"numOfRows":str(LIMIT),
                "ServiceKey":key,
            }
            total_requests+=1
            return parse_response(fetch(BASE+"?"+urlencode(params)))
        head=page_request(1)
        raw_total=head["total"]
        # The windows must be disjoint, not paged separately after splitting.
        if raw_total>max_pages*LIMIT and left<right:
            pivot=left+timedelta(days=(right-left).days//2)
            a=query_day_range(left,pivot)
            b=query_day_range(pivot+timedelta(days=1),right)
            return {
                "rows":a["rows"]+b["rows"],
                "total":a["total"]+b["total"],
                "complete":a["complete"] and b["complete"],
            }
        rows=list(head["items"])
        for page in range(2,max_pages+1):
            if len(rows)>=raw_total:
                break
            reply=page_request(page)
            if reply["total"]!=raw_total:
                raise ValueError("페이지 간 공보 건수 변경: 완전 탐색 확인 불가")
            if not reply["items"]:
                raise ValueError("빈 페이지가 있는데 전체 공보 건수는 남아 있음")
            rows.extend(reply["items"])
        # Repeating the same page is not evidence of complete retrieval.
        ids=[(x.get("openNumber") or "",x.get("applicationNumber") or "")
             for x in rows]
        if len(ids)!=len(set(ids)):
            raise ValueError("특허 페이지 간 동일 공개번호 반복: 완전 탐색 실패")
        complete=len(rows)==raw_total
        windows.append({"start":begin,"end":finish,"total":raw_total,
                        "retrieved":len(rows),"complete":complete})
        return {"rows":rows,"total":raw_total,"complete":complete}

    report=query_day_range(first,last)
    return {
        **report,"query":term,"window":from_date+"~"+to_date,
        "requestCount":total_requests,"windows":windows,
        "splitWindowCount":len(windows),
    }


def tech_tags(title,abstract):
    title_norm=normalize(title)
    abstract_norm=normalize(abstract)
    found=[]
    for group,words in TERMS.items():
        title_hits=[word for word in words if normalize(word) in title_norm]
        abstract_hits=[word for word in words if normalize(word) in abstract_norm]
        if title_hits or abstract_hits:
            found.append({
                "theme":group,"titleHits":title_hits[:5],
                "abstractHits":abstract_hits[:5]
            })
    return found


def verified_patent(raw,company,aliases,start,end):
    applicant=raw.get("applicantName","")
    if not applicant_matches(applicant,aliases):
        return None
    published=re.sub(r"[^\d]","",raw.get("openDate",""))
    applied=re.sub(r"[^\d]","",raw.get("applicationDate",""))
    pub_no=str(raw.get("openNumber","")).strip()
    app_no=str(raw.get("applicationNumber","")).strip()
    title=html.unescape(raw.get("inventionTitle","")).strip()
    if (not DATE8.fullmatch(published) or not start<=published<=end
        or not PATENT_NUMBER.fullmatch(pub_no) or not PATENT_NUMBER.fullmatch(app_no)
        or not 2<=len(title)<=250):
        return None
    try:
        real_date=datetime.strptime(published,"%Y%m%d").date()
    except ValueError:
        return None
    if applied:
        if not DATE8.fullmatch(applied):
            return None
        try:
            if datetime.strptime(applied,"%Y%m%d").date()>real_date:
                return None
        except ValueError:
            return None
    tags=tech_tags(title,raw.get("astrtCont",""))
    # Preserve verified publications even without known sector terms:
    # cross-industry technology must not be excluded by a keyword gate.
    title_tags=[t for t in tags if t["titleHits"]]
    score=(min(85,35+14*len(title_tags)+5*len(tags)+(6 if raw.get("astrtCont") else 0))
           if tags else 20)
    return {
        "company":company,"applicants":applicant.split("|"),
        "applicationNumber":app_no,"publicationNumber":pub_no,
        "applicationDate":applied or None,"publicationDate":published,
        "registrationDate":re.sub(r"[^\d]","",raw.get("registerDate","")) or None,
        "registerStatus":raw.get("registerStatus") or "미확인",
        "title":title,"abstract":html.unescape(raw.get("astrtCont","")).strip()[:850],
        "ipc":raw.get("ipcNumber","")[:160],
        "themes":tags,"priorityScore":score,
        "themeMatched":bool(tags),
        "classificationStatus":("기술 키워드 일치 · 별도 원문 검증 필요" if tags
                                 else "기존 기술사전에 없음 · 공동출원인/초록 검토"),
        "source":"KIPRISPlus 특허·실용 공개·등록공보 API",
        "sourceLookup":LANDING,
        "lookupNumber":pub_no,
        "status":"공개된 특허 문헌: 기술 방향 취재 후보",
        "notProven":"실제 제품화·양산·인허가·특허등록/독점권·미보도·단독 여부 미확인",
        "questions":[
            "이 공개특허의 독립 청구항 핵심 구성과 종전 기술의 차이는 무엇인가?",
            "기존 동일 출원인 특허·우선권·특허패밀리/해외공개와 중복되지 않는가?",
            "해당 기술이 연구 단계인지, 현재 양산차·제품/설비에 적용되는가?",
            "업계 경쟁제품 및 특허 관련 기보도/기업 발표와 다른 사실은 무엇인가?"
        ],
        "scoopConfirmed":False
    }


def press_lookup(item,fetch=None):
    # Query an exact publication number; a single broad-company hit is not evidence.
    query=f'"{item["publicationNumber"]}" "{item["company"]}"'
    url="https://news.google.com/rss/search?q="+quote(query)+"&hl=ko&gl=KR&ceid=KR:ko"
    def public_fetch(uri):
        req=Request(uri,headers={"User-Agent":"newsroom-patent-precoverage/1.0"})
        with urlopen(req,timeout=10) as handle:
            return handle.read(500_001)
    try:
        payload=(fetch or public_fetch)(url)
        if len(payload)>500_000:
            raise ValueError("뉴스 RSS 크기 상한 초과")
        root=ET.fromstring(payload)
        if root.tag!="rss" or root.find("channel") is None:
            raise ValueError("뉴스 RSS 형식 오류")
        stories=[]
        for node in root.findall("./channel/item")[:12]:
            title=html.unescape(node.findtext("title") or "").strip()[:240]
            link=(node.findtext("link") or "").strip()
            if title and link.startswith("https://news.google.com/"):
                stories.append({"title":title,"url":link})
            if len(stories)==4:
                break
        return {"status":("검색된 기사 있음: 동일 기술·선행 보도 원문 확인 필요" if stories else
                          "번호 직접 검색 결과 미발견: 미보도 의미 아님"),
                "query":query,"articles":stories}
    except (ValueError,ET.ParseError,OSError,TimeoutError) as error:
        return {"status":"보도 확인 실패: "+type(error).__name__,
                "articles":[],"query":query}


def build(key,previous=None,now=None,search=search_applicant,coverage=None,
          names=None,news_limit=5):
    now=now or datetime.now(KST)
    if not key:
        return {"generatedAt":now.isoformat(),"status":"KIPRIS_SERVICE_KEY 미설정",
                "complete":False,"items":[],"companyChecks":[],"confirmedScoops":0}
    since=(now-timedelta(days=35)).strftime("%Y%m%d")
    until=now.strftime("%Y%m%d")
    previous=previous if isinstance(previous,dict) else {}
    old_seen=previous.get("seen",{})
    if not isinstance(old_seen,dict):
        old_seen={}
    baseline=previous.get("status") not in ("official_search_partial","official_search_completed")
    previous_day=re.sub(r"[^0-9]","",str(previous.get("generatedAt") or "")[:10])
    # Publications older than the previous successful snapshot are backfills
    # (including a previously truncated applicant query), not fresh disclosure.
    companies=names if names is not None else list(APPLICANTS)
    seen=dict(old_seen)
    checks=[]
    candidates={}
    for company in companies:
        aliases=APPLICANTS.get(company)
        if not aliases:
            checks.append({"company":company,"status":"unlisted_issuer"})
            continue
        try:
            # Search by distinctive legal stem; verify EXACT official legal
            # applicant name in the response (no false '현대' subsidiaries).
            stem=re.sub(r"(?:주식회사|\s)","",aliases[0])
            result=search(key,stem,since,until)
            count=0
            for row in result["rows"]:
                candidate=verified_patent(row,company,aliases,since,until)
                if candidate is None:
                    continue
                number=candidate["publicationNumber"]
                identity=company+"|"+number
                if identity in candidates:
                    continue
                candidate["previouslyObserved"]=identity in old_seen
                candidate["firstObservedAt"]=old_seen.get(identity,now.date().isoformat())
                candidate["initialBaseline"]=baseline
                candidate["historicalBackfill"]=bool(not baseline
                    and identity not in old_seen and len(previous_day)==8
                    and candidate["publicationDate"]<=previous_day)
                candidate["freshObservation"]=bool(not baseline
                    and identity not in old_seen and not candidate["historicalBackfill"])
                candidate["observationNote"]=(
                    "직전 스냅샷 이전 공개 공보를 뒤늦게 수집(신규 공개 아님)"
                    if candidate["historicalBackfill"] else
                    "수집 기준선의 과거 공보" if baseline else
                    "이미 관측된 공개공보" if candidate["previouslyObserved"] else
                    "새로 관측한 공개공보(최초 출원·단독 아님)")
                candidates[identity]=candidate
                seen.setdefault(identity,now.date().isoformat())
                count+=1
            checks.append({"company":company,"status":("checked" if result["complete"] else "truncated"),
                           "matched":count,"rawTotal":result["total"],
                           "rawRetrieved":len(result["rows"]),
                           "requests":result.get("requestCount"),
                           "windows":result.get("splitWindowCount")})
        except Exception as ex:
            checks.append({"company":company,"status":"source_error",
                           "errorType":type(ex).__name__,
                           "errorDetail":str(ex)[:110] if isinstance(ex,ValueError) else ""})
    leads=sorted(candidates.values(),key=lambda r:(-r["priorityScore"],-int(r["publicationDate"]),r["company"]))
    for row in leads[:news_limit]:
        row["pressCoverage"]=(coverage or press_lookup)(row)
    # Retain only last 180 days of first-seen history, but never use the
    # first successful run to allege that the patent was just filed or new.
    cutoff=(now.date()-timedelta(days=180)).isoformat()
    seen={k:v for k,v in seen.items() if isinstance(v,str) and v>=cutoff}
    successes=sum(c["status"]=="checked" for c in checks)
    return {
        "generatedAt":now.isoformat(timespec="seconds"),"source":"KIPRISPlus Patent/Utility Publication official Open API",
        "status":("official_search_completed" if successes==len(companies)
                  else "official_search_partial"),
        "reportingWindow":since+"~"+until,
        "applicantCount":len(companies),
        "companyChecks":checks,"candidateCount":len(leads),
        "topicMatchedCount":sum(bool(r["themeMatched"]) for r in leads),
        "unclassifiedCount":sum(not r["themeMatched"] for r in leads),
        "capturePolicy":"35일 공개공보에서 공식 출입처 법인명·공개번호·공개일 검증; 기술 키워드 제외 없음",
        "completelyCheckedCompanies":successes,
        "baselineInitialized":baseline,
        "alertCount":sum(bool(r["freshObservation"]) for r in leads),
        "historicalBackfillCount":sum(bool(r["historicalBackfill"]) for r in leads),
        # No top-500 truncation: keep complete validated records for downstream discovery.
        "items":leads,"seen":seen,"confirmedScoops":0,
        "displayedCount":len(leads),
        "unshownCount":0,
        "sourceWindowComplete":successes==len(companies) and all(c["status"]=="checked" for c in checks),
        "coverageWarning":"첫 조회는 과거 35일 공개공보의 기준선. 출원일과 공개일이 다르고 특허 공개는 출시/양산·단독 확정이 아님. API 미지원/절단/장애는 회사 0건 아님",
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",default="digests/patent_hunt_latest.json")
    parser.add_argument("--max-news",type=int,default=5)
    args=parser.parse_args()
    if not 0<=args.max_news<=10:
        parser.error("검색 건수는 0~10")
    output=Path(args.out)
    previous=None
    if output.is_file():
        try:
            previous=json.loads(output.read_text(encoding="utf-8"))
        except (OSError,ValueError):
            pass
    key=os.environ.get("KIPRIS_SERVICE_KEY","").strip()
    report=build(key,previous=previous,news_limit=args.max_news)
    if key and not report.get("sourceWindowComplete"):
        print("KIPRISPlus 24개 출입처 공식 검색에 오류·누락·페이지 절단 발생: 이전 검증 데이터 보존")
        raise SystemExit(2)
    output.parent.mkdir(parents=True,exist_ok=True)
    tmp=output.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    tmp.replace(output)
    print("KIPRISPlus official",report["status"],
          "issuer checks",len(report["companyChecks"]),"patent evidence",len(report["items"]),
          "exclusive confirmed",report["confirmedScoops"])


if __name__=="__main__":
    main()
