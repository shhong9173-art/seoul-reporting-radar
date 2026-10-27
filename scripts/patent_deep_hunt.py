"""Second-stage patent investigation: unique publication, precise technology and history.

A news desk's triage, not an AI declaration of novelty:
  1. same publication co-filed by Hyundai/Kia -> ONE publication card;
  2. narrow automotive/grid themes using actual title evidence;
  3. prior 3-year KIPRIS official invention-title search (bounded);
  4. show related recent inventions and coverage verification questions.
Claim-scope novelty, foreign family, product release and first-to-file remain
UNVERIFIED until corresponding primary source has been read.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from patent_hunt import BASE,parse_response,request_xml,normalize,applicant_matches,APPLICANTS
from kipris_account_ledger import KiprisAccountLedger

KST=timezone(timedelta(hours=9))
AUTO={"현대자동차","기아","현대모비스","현대위아","HL만도",
      "한국타이어앤테크놀로지","넥센타이어","금호타이어"}
PLAIN={"차량","장치","방법","시스템","구조","제어","이를","포함하는",
       "및","그","것","용","모듈","제조","기술","동작","자동차"}
GRID=("변압기","차단기","hvdc","고압직류","초고압직류","직류송전",
      "몰드변압기","배전","송전","가스절연","축발전기")
AUTO_SPECIFIC=("자율주행","자율 주행","라이다","원격주차","센서융합","경로계획","자율차")
RECORD=re.compile(r"[\d-]{10,22}\Z")
TODAY=datetime.now(KST)


def keywords(title):
    text=re.sub(r"[\[\](){}·ㆍ,:/\\-]"," ",str(title or "")).lower()
    words=re.findall(r"[가-힣]{2,}|[a-z]{2,}\d*|\d+[a-z]+",text)
    return [s for s in words if s not in PLAIN]


def similarity(left,right):
    a,b=set(keywords(left)),set(keywords(right))
    if not a or not b:
        return 0
    return round(len(a&b)/len(a|b),3)


def accurate_topics(row):
    """Use literal title evidence to avoid cars mislabeled as HVDC/SDV."""
    company=row.get("company")
    title=str(row.get("title") or "")
    norm=normalize(title)
    old={x.get("theme") for x in row.get("themes",[])}
    topics=[]
    if any(normalize(w) in norm for w in AUTO_SPECIFIC):
        topics.append("자율주행·SDV")
    elif company in AUTO and ("자율주행·SDV" in old or "차량" in title or "하이브리드" in title):
        topics.append("차량 제어·파워트레인(자율주행 미확정)")
    if "전기차·배터리" in old and ("배터리" in title or "충전" in title or "전지" in title):
        topics.append("전기차·배터리")
    if any(normalize(w) in norm for w in GRID):
        topics.append("전력망·전력기기(용도 검증 필요)")
    elif company not in AUTO and "전력망·HVDC" in old:
        topics.append("전력변환 기술(계통 HVDC 여부 미확인)")
    if "수소·연료전지" in old and any(w in title for w in ("수소","연료전지","수전해")):
        topics.append("수소·연료전지")
    for theme in ("저탄소 제철","공장·제조 자동화","순환소재·폐차재활용"):
        if theme in old:
            topics.append(theme)
    return topics or ["관련 출입처 기술·세부 활용처 확인"]


def outside_beat_applicants(applicants):
    """Keep ALL named official co-applicants, but classify exact beat legal
    entities separately. No inference of supply contracts or joint ventures.
    """
    if not isinstance(applicants,list):
        return []
    found=[]
    seen=set()
    for name in applicants:
        name=str(name or "").strip()
        identity=normalize(name)
        if not identity or identity in seen:
            continue
        seen.add(identity)
        if not any(applicant_matches(name,aliases) for aliases in APPLICANTS.values()):
            found.append(name)
    return found


def merge_publications(source):
    if not isinstance(source,dict) or not isinstance(source.get("items"),list):
        raise ValueError("KIPRIS 기존 데이터 형식 오류")
    merged={}
    invalid=[]
    for row in source["items"]:
        if not isinstance(row,dict) or not RECORD.fullmatch(str(row.get("publicationNumber") or "")):
            continue
        n=row["publicationNumber"]
        company=row.get("company")
        if company not in APPLICANTS:
            continue
        if n not in merged:
            cur={**row,"coveredCompanies":[company],"sourceRecordCount":1}
            merged[n]=cur
        else:
            cur=merged[n]
            if (normalize(cur.get("title"))!=normalize(row.get("title"))
                or cur.get("publicationDate")!=row.get("publicationDate")):
                invalid.append(n)
                continue
            if company not in cur["coveredCompanies"]:
                cur["coveredCompanies"].append(company)
            cur["sourceRecordCount"]+=1
            # A multi-applicant public record may be returned for two beat
            # companies. Preserve any genuinely named outside participants.
            known={normalize(a) for a in cur.get("applicants",[])}
            for applicant in row.get("applicants",[]):
                if normalize(applicant) not in known:
                    cur.setdefault("applicants",[]).append(applicant)
                    known.add(normalize(applicant))
            cur["previouslyObserved"]=bool(cur.get("previouslyObserved") and row.get("previouslyObserved"))
    for number in set(invalid):
        merged.pop(number,None)
    items=list(merged.values())
    for x in items:
        x["coveredCompanies"].sort()
        x["investigativeThemes"]=accurate_topics(x)
        # Corporate-group filings (Hyundai + Kia) and cross-organization
        # filings are different editorial signals.
        x["outsideBeatCoApplicants"]=outside_beat_applicants(x.get("applicants",[]))
        x["officialApplicantCount"]=len({normalize(n) for n in x.get("applicants",[]) if normalize(n)})
        x["jointApplicantGroup"]=x["officialApplicantCount"]>1
        x["crossOrganizationLead"]=bool(x["outsideBeatCoApplicants"])
        x["partnerStatus"]="공동출원 명의만 확인 · 역할/사업화/협업 계약 미확인"
        x["partnerQuestions"]=[
            "출입처 외 공동출원인 각각이 담당한 효소·소재·공정·차량 적용 기술은 무엇인가?",
            "특허의 청구항이 폐차 재료의 실제 재생·신차 적용을 설명하는가, 연구 단계인가?",
            "양산 적용 시점·공급 계약 및 기존 유사 기술과의 차이·선행 보도는 확인됐는가?"
        ] if x["crossOrganizationLead"] else []
        x["newsroomScore"]=score(x)
        x["techNoveltyStatus"]="특허 청구항·기존 기술과의 실질 차이 미확인"
        x["commercialStatus"]="기업 직접 확인 전 제품화·양산·수주 미확인"
        x["priorFullTitleCheck"]={"status":"미검색","matches":[]}
        x["relatedRecent"]=[]
    return items,sorted(set(invalid))


def score(row):
    title=row.get("title","")
    topics=accurate_topics(row)
    # This is only desk priority to investigate, not novelty/exclusive chance.
    signal=0
    if any(normalize(w) in normalize(title) for w in AUTO_SPECIFIC+GRID):
        signal+=15
    if any(x in title for x in ("양방향","고전압","전고체","실시간","최적화","전력밀도","방열","냉각","열관리","철심","수전해","제어")):
        signal+=9
    if len(keywords(title))>=5:
        signal+=5
    if len(row.get("abstract") or "")>=110:
        signal+=8
    if row.get("jointApplicantGroup"):
        signal+=3
    if row.get("crossOrganizationLead"):
        signal+=17
    if any(t.get("theme")=="순환소재·폐차재활용" for t in row.get("themes",[])):
        signal+=10
    return min(85,28+signal)


def relate(items,threshold=0.42):
    """Within already collected 35-day data; NOT worldwide prior art."""
    for i,patent in enumerate(items):
        matches=[]
        for j,other in enumerate(items):
            if i==j:
                continue
            s=similarity(patent.get("title"),other.get("title"))
            if s<threshold:
                continue
            matches.append({"publicationNumber":other["publicationNumber"],
                            "title":other["title"],"companies":other["coveredCompanies"],
                            "publicationDate":other.get("publicationDate"),"titleSimilarity":s})
        matches.sort(key=lambda r:(-r["titleSimilarity"],-int(r["publicationDate"] or "0")))
        patent["relatedRecent"]=matches[:3]
    return items


def historical_title_search(key,title,cutoff,fetch=request_xml):
    """Title index hit search; cannot establish same claims or all prior art."""
    if not key or not title or not re.fullmatch(r"\d{8}",cutoff):
        raise ValueError("KIPRIS 과거 제목 검색 입력 오류")
    params={"inventionTitle":title[:170],
            "openDate":"20230101~"+cutoff,
            "patent":"true","utility":"false",
            "sortSpec":"OPD","descSort":"true",
            "pageNo":"1","numOfRows":"100","ServiceKey":key}
    # Keep ServiceKey last for KIPRISPlus gateway compatibility.
    result=parse_response(fetch(BASE+"?"+urlencode(params)))
    return {"total":result["total"],"rows":result["items"],
            "complete":result["total"]<=100,
            "queryFields":{"title":title[:170],"period":"20230101~"+cutoff}}


def historical_summary(patent,response):
    if not isinstance(response,dict) or not isinstance(response.get("rows"),list):
        raise ValueError("과거 특허 검색 원문 누락")
    past=[]
    target=normalize(patent.get("title"))
    current=patent["publicationNumber"]
    for row in response["rows"]:
        number=str(row.get("openNumber") or "")
        pub=re.sub(r"\D","",str(row.get("openDate") or ""))
        title=str(row.get("inventionTitle") or "")
        if (number==current or not RECORD.fullmatch(number)
            or not re.fullmatch(r"20\d{6}",pub)):
            continue
        if normalize(title)!=target:
            continue
        owner=str(row.get("applicantName") or "")
        known=any(applicant_matches(owner,APPLICANTS[c]) for c in patent["coveredCompanies"])
        past.append({"publicationNumber":number,"title":title,
                     "published":pub,"applicationNumber":str(row.get("applicationNumber") or ""),
                     "applicants":owner[:220],
                     "overlappingApplicant":known})
    return {"status":("과거 동일 제목 공보 발견(청구항/패밀리 동일성 미검증)" if past
                      else "동일 제목 공보 미확인(다른 명칭의 선행기술은 검증 전)"),
            "queryFields":response.get("queryFields"),
            "rawTotal":response.get("total"),
            "complete":bool(response.get("complete")),
            "checkedItems":len(response["rows"]),
            "matches":past[:6],
            "claimComparison":"미조회: 청구항 원문 데이터는 이 검색 API 결과에 포함되지 않음",
            "foreignFamilyComparison":"미조회: KIPRISPlus 별도 패밀리·우선권 또는 해외 공식 API 필요"}



def balance_issuers(items):
    """Round-robin across distinct applicant groups, then by source priority.

    If Hyundai/Kia co-file most patents, their one group must not consume
    the entire research budget while power/steel/parts filings are skipped.
    This does not imply that less common filings are more newsworthy.
    """
    groups={}
    for row in items:
        key="+".join(sorted(row.get("coveredCompanies") or [row.get("company","")]))
        groups.setdefault(key,[]).append(row)
    order=sorted(groups,key=lambda k:(-groups[k][0]["newsroomScore"],k))
    result=[]
    while any(groups.values()):
        for key in order:
            if groups[key]:
                result.append(groups[key].pop(0))
    return result


def build(source,key="",historical=historical_title_search,search_limit=10,now=None):
    now=now or datetime.now(KST)
    if not 0<=search_limit<=20:
        raise ValueError("과거 특허 비교 검색 상한 0~20")
    items,rejected=merge_publications(source)
    relate(items)
    items.sort(key=lambda x:(-x["newsroomScore"],-int(x.get("publicationDate") or 0),x["publicationNumber"]))
    items=balance_issuers(items)
    count=0
    for row in items:
        if count>=search_limit or not key:
            continue
        date=row.get("publicationDate") or ""
        if not re.fullmatch(r"20\d{6}",date):
            continue
        target=(datetime.strptime(date,"%Y%m%d").date()-timedelta(days=1)).strftime("%Y%m%d")
        count+=1
        try:
            r=historical(key,row["title"],target)
            row["priorFullTitleCheck"]=historical_summary(row,r)
        except Exception as e:
            row["priorFullTitleCheck"]={
                "status":"과거 특허 원문 검색 오류: "+type(e).__name__,
                "matches":[],"claimComparison":"미검증",
                "foreignFamilyComparison":"미검증"}
    for i,x in enumerate(items):
        x["priority"]=i+1
    return {
        "generatedAt":now.isoformat(timespec="seconds"),
        "patentDatasetGeneratedAt":source.get("generatedAt"),
        "inputPatents":len(source["items"]),
        "sourceCandidateCount":source.get("candidateCount"),
        "uniquePublicationCount":len(items),
        "jointApplications":sum(x["jointApplicantGroup"] for x in items),
        "outsideBeatJointPublications":sum(x["crossOrganizationLead"] for x in items),
        "partnerInvestigations":sorted(
            (x for x in items if x["crossOrganizationLead"]),
            key=lambda x:(-x["newsroomScore"],-int(x.get("publicationDate") or 0))
        ),
        "invalidDuplicateNumbers":rejected,
        "sourceCoverageComplete":source.get("sourceWindowComplete",False),
        "historicalQueriesAttempted":count,
        "rankingMethod":"공식 기술 근거 우선점수×공동출원 법인군 라운드로빈(출입처 편중 방지, 단독 확률 아님)",
        "historicalScope":"동일 발명명칭 공식 KIPRIS 공개공보 2023년 이후 목록 부분검색; 청구범위/해외패밀리 전체 선행기술 비교 아님",
        "warning":"출원/공개/등록·실제 기술 적용·세계최초·선행보도·단독은 각각 독립 검증해야 한다. 공동출원 하나는 1건.",
        "confirmedScoops":0,
        "investigations":items[:60],
        "unshown":max(0,len(items)-60)
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",default="digests/patent_hunt_latest.json")
    p.add_argument("--output",default="digests/patent_deep_latest.json")
    p.add_argument("--max-history",type=int,default=10)
    args=p.parse_args()
    source=json.loads(Path(args.input).read_text(encoding="utf-8"))
    if (source.get("status")!="official_search_completed" or
        source.get("sourceWindowComplete") is not True):
        print("KIPRIS 공식 출원인 전체 검색 미검증: 과거 심층 분석 출판 중지")
        raise SystemExit(2)
    key=os.environ.get("KIPRIS_SERVICE_KEY","").strip()
    limit=args.max_history if key else 0
    historical=historical_title_search
    if key:
        ledger=KiprisAccountLedger()
        if not ledger.should_probe("patent_deep"):
            limit=0
        limit=min(limit,ledger.remaining("patent_deep"))
        fetch=ledger.fetcher("patent_deep",request_xml)
        historical=lambda k,t,c:historical_title_search(k,t,c,fetch=fetch)
        if limit<args.max_history:
            print("KIPRIS 공용 장부: 과거 제목 검색",args.max_history,"→",limit,"건으로 제한")
    result=build(source,key=key,historical=historical,search_limit=limit)
    if key:
        ledger.persist()
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    temp=out.with_suffix(".json.tmp")
    temp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    temp.replace(out)
    print("특허 조사단서",result["uniquePublicationCount"],"공개번호 · 공동출원",
          result["jointApplications"],"건 · 과거 제목 검색",result["historicalQueriesAttempted"],
          "건 · 단독 확정 0건")


if __name__=="__main__":
    main()
