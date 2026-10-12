"""KIPRIS official independent-claim audit: technical wording and prior-art questions.

This is a journalist evidence ledger, NOT patent novelty, priority,
infringement or grant analysis. Discloses only short textual excerpts and
hashes rather than republishing entire claim text in a public GitHub repo.
Fail-closed identity checks ensure claims belong to the given application.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import html
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from patent_hunt import APPLICANTS,normalize,request_xml
from patent_deep_hunt import historical_title_search,historical_summary

KST=timezone(timedelta(hours=9))
DETAIL="https://plus.kipris.or.kr/kipo-api/kipi/patUtiModInfoSearchSevice/getBibliographyDetailInfoSearch"
NUMBER=re.compile(r"10-?\d{4}-?\d{6,8}\Z")
PUBLICATION=re.compile(r"[\d-]{10,22}\Z")
CLAIM_PREFIX=re.compile(r"^\s*(?:【\s*청구항\s*1\s*】|청구항\s*1\b|제\s*1\s*항\b|1\s*[.、)])")
DEPENDS=re.compile(r"제\s*\d+\s*항(?:에|의)\s*(?:있어서|기재된|따른)")
TOPICS={
    "자율주행·SDV":"센서/인지/경로계획/제어 구성과 실제 주행자동화 수준을 회사에 질의",
    "전력망·전력기기(용도 검증 필요)":"냉각·절연·보호계전 구조, 제품 사양/인증 및 실물 공급 여부를 확인",
    "차량 제어·파워트레인(자율주행 미확정)":"차량 제어 목적·적용 차종·출시 여부를 별도 취재",
    "전기차·배터리":"셀/모듈/충전 안전 및 완성차 적용 여부를 확인",
    "수소·연료전지":"실증 시설·운송 장비·기술 상용화 진행을 확인",
    "저탄소 제철":"전기로/제조 공정 적용 사업장과 배출·원가 실적을 확인",
}
# Keep query limits small for the KIPRISPlus monthly quota.
PRIORITY_PUBLICATION="1020260138678"


def _clean(value):
    return re.sub(r"\s+"," ",html.unescape(str(value or ""))).strip()


def _stripped(value):
    return re.sub(r"[\s-]","",str(value or ""))


def official_detail(key,application,fetch=request_xml):
    """One KIPRIS+ official API call keyed by application (not publication)."""
    if not key or not NUMBER.fullmatch(str(application or "")):
        raise ValueError("특허 상세 출원번호/인증키 오류")
    url=DETAIL+"?"+urlencode({"applicationNumber":_stripped(application),"ServiceKey":key})
    return parse_bibliography(fetch(url),_stripped(application))


def _text(node):
    return _clean("".join(node.itertext()))


def parse_bibliography(raw,expected_application):
    """Reject unexpected output and prevent comparing claims of another patent."""
    if isinstance(raw,str):
        raw=raw.encode("utf-8")
    if not isinstance(raw,bytes) or not 50<=len(raw)<=2_000_000:
        raise ValueError("공식 서지상세 원문 형식/길이 오류")
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("비신뢰 XML 엔터티 사용 불가")
    root=ET.fromstring(raw)
    if root.tag!="response":
        raise ValueError("공식 KIPRIS 응답 루트가 일치하지 않음")
    header=root.findtext("./header/resultCode")
    if header not in ("00","0"):
        raise RuntimeError("KIPRIS 상세 응답 오류: "+str(header))
    item=root.find("./body/item")
    if item is None:
        raise ValueError("서지 상세 item 없음: 공식 문헌 확인 실패")
    application_numbers=[_stripped(_text(n)) for n in item.iter()
                         if n.tag.lower() in ("applicationnumber","applnumber")]
    if _stripped(expected_application) not in application_numbers:
        raise ValueError("출원번호 불일치 또는 상세 응답에 공식 출원번호 없음")
    nodes=list(item.findall(".//claimInfoArray"))
    if len(nodes)!=1:
        raise ValueError("공식 청구항 응답 배열 없음/중복: 판독 불가")
    arr=nodes[0]
    claims=[]
    # Official responses vary: <claimInfo><claim> or direct <claim>.
    for n in arr.iter():
        if n.tag.lower() not in ("claim","claimtext","claimcontent"):
            continue
        text=_text(n)
        if not text or len(text)<18 or len(text)>80_000:
            continue
        number=None
        parent=None
        for candidate in arr.iter():
            if n in list(candidate):
                parent=candidate
                break
        for wrapper in (parent,n):
            if wrapper is None:
                continue
            for elem in wrapper:
                if elem.tag.lower() in ("claimnumber","claimno","claimnum","number"):
                    m=re.search(r"\d+",_text(elem))
                    if m:
                        number=int(m.group(0))
                        break
            if number is not None:
                break
        if number is None:
            m=re.match(r"^(?:【\s*청구항\s*|청구항\s*|제\s*)(\d+)",text)
            if m:
                number=int(m.group(1))
        claims.append({"number":number,"text":text})
    if not claims:
        raise ValueError("공식 XML에 판독 가능한 청구항 본문 없음")
    first=next((x for x in claims if x["number"]==1),None)
    if first is None and claims[0]["number"] is None:
        # The KIPRIS claimInfoArray list may have no explicit indexes;
        # the first item is claim 1 only when the provider explicitly
        # structures it as the first claimInfo element in the claim array.
        claim_items=list(arr.findall("./claimInfo"))
        if claim_items and len(claim_items)==len(claims):
            first=claims[0]
    if first is None:
        raise ValueError("독립 청구항 제1항의 원문 위치를 신뢰할 수 없음")
    if DEPENDS.search(first["text"][:70]):
        raise ValueError("청구항 제1항을 종속항으로 판독함")
    return {
        "applicationNumber":_stripped(expected_application),
        "claimCountParsed":len(claims),
        "claim1Text":first["text"],
        "claim1Sha256":hashlib.sha256(first["text"].encode("utf-8")).hexdigest(),
        "claim1Length":len(first["text"]),
        "sourceVerified":True,
        "claimStatus":"공식 KIPRIS 서지상세 공보에 기재된 제1항(심사 중 보정/등록후 권리범위는 별도)",
    }


def compare_claims(current,prior):
    """Only text-level similarity; novelty and patent-family comparison excluded."""
    a=current["claim1Text"]
    b=prior["claim1Text"]
    score=round(difflib.SequenceMatcher(None,b,a,autojunk=False).ratio(),3)
    changed=a!=b
    # No full claims in GitHub; retain only short leading snippets and hashes.
    return {
        "comparisonType":"공식 청구항 제1항 문구 대조(기술적 신규성 판정 아님)",
        "currentApplication":current["applicationNumber"],
        "priorApplication":prior["applicationNumber"],
        "sameClaimText":not changed,
        "textSimilarity":score,
        "currentClaimSha256":current["claim1Sha256"],
        "priorClaimSha256":prior["claim1Sha256"],
        "currentClaimLength":current["claim1Length"],
        "priorClaimLength":prior["claim1Length"],
        "currentShortExcerpt":a[:100]+"…" if len(a)>100 else a,
        "priorShortExcerpt":b[:100]+"…" if len(b)>100 else b,
        "finding":("청구항 1의 표기 문구 차이 확인; 법적·기술적 차별성은 해석 전" if changed
                   else "청구항 1의 수집 원문 문구가 동일함; 문헌·권리범위 동일성 판정 아님"),
        "notProven":"신규성/진보성·청구범위 동일성·선행기술 전수 검토·특허패밀리·실제 양산·단독을 확정하지 않음",
    }


def plan_company_questions(row):
    questions=[
        "제1항의 핵심 구성요소 중 기존 기술 대비 다른 부분을 연구개발 부서가 확인할 수 있는가?",
        "해당 출원 기술이 실제 제품·사업장에 적용됐나? 적용 시점·차종/품목·상업적 실적은?",
        "관련 해외 특허패밀리·우선권·심사 인용 및 보정 이력이 어떻게 되나?",
        "이 기술 관련 기보도·IR·제품 발표가 있는가? 없다면 공개 가능한 신규 사업 사실은?",
    ]
    theme=next(iter(row.get("investigativeThemes") or []),None)
    impact=TOPICS.get(theme,"현 사업부 관련성·개발 단계·산업 영향을 검증")
    return {"applicationHypothesis":impact,"companyQuestions":questions,
            "industryEffectStatus":"특허 기술의 실제 사업 적용·효과 미확인",
            "earlierCoverageStatus":"기보도·기업 IR 본문 검증 미완료",
            "candidateAngle":"공보 청구항의 구성 차이 및 제품 적용 여부 확인 후 야마 결정(기사 발제 미확정)"}


def _newspaper_news(query,fetch=None):
    """Search is an index hint, never proof of unique/previous coverage."""
    uri="https://news.google.com/rss/search?q="+quote(query)+"&hl=ko&gl=KR&ceid=KR:ko"
    if fetch is None:
        def fetch(request_url):
            req=Request(request_url,headers={"User-Agent":"reporter-patent-check/1.0"})
            with urlopen(req,timeout=10) as handle:
                result=handle.read(220001)
            if len(result)>220000:
                raise ValueError("뉴스 검색 결과 크기 초과")
            return result
    data=fetch(uri)
    if len(data)>220000 or b"<!DOCTYPE" in data.upper():
        raise ValueError("RSS 응답 형식 오류")
    root=ET.fromstring(data)
    if root.tag!="rss":
        raise ValueError("RSS 응답 루트 오류")
    articles=[]
    for item in root.findall("./channel/item")[:8]:
        title=_clean(item.findtext("title"))[:180]
        link=_clean(item.findtext("link"))
        if title and link.startswith("https://news.google.com/"):
            articles.append({"title":title,"url":link,
                             "status":"RSS 검색 색인 일치: 실제 동일 특허·청구항 기보도 여부 미확인"})
        if len(articles)>=3:
            break
    return {"query":query,"articles":articles,
            "status":("관련 기사 검색됨(내용·동일사건 미검증)" if articles
                      else "검색 미발견: 미보도 확정 불가")}


def related_press(row,fetch=None):
    pub=row.get("publicationNumber","")
    company="/".join((row.get("coveredCompanies") or [])[:2])
    search=(f'"{pub}"' if PUBLICATION.fullmatch(pub or "") else
            f'"{_clean(row.get("title"))[:35]}"')
    search2=f'{company} "{_clean(row.get("title"))[:34]}"'
    research=[]
    for q in (search,search2):
        try:
            research.append(_newspaper_news(q,fetch=fetch))
        except (OSError,TimeoutError,ValueError,ET.ParseError) as e:
            research.append({"query":q,"status":"검색 오류: "+type(e).__name__,
                             "articles":[]})
    return {"status":"자동 검색은 잠정 근거; 전문지·회사 발표 추가 확인 필수",
            "queries":research,
            "claimAlreadyReported":"미확인"}


def inspect(row,key,old_limit=2,detail=official_detail,history=historical_title_search,
            news=related_press):
    result={"publicationNumber":row.get("publicationNumber"),"company":row.get("coveredCompanies",[]),
            "title":row.get("title"),"currentApplication":row.get("applicationNumber"),
            "published":row.get("publicationDate"),
            "sourceDataset":"KIPRISPlus 최근 공식 공개공보 및 2023년 이후 동일 제목 이력",
            "status":"not_checked","priorComparisons":[],"claimVerified":False,
            "scoopConfirmed":False,"desk":plan_company_questions(row),
            "relatedPress":{"status":"미확인"},
            "sourceLink":"https://www.kipris.or.kr/",
            "errorType":None}
    application=row.get("applicationNumber")
    if not NUMBER.fullmatch(str(application or "")):
        result["status"]="invalid_official_application_number"
        return result
    try:
        current=detail(key,application)
    except Exception as error:
        result.update({"status":"current_claim_unavailable",
                       "errorType":type(error).__name__})
        return result
    result.update({"status":"claim1_verified","claimVerified":True,
                   "claim1Length":current["claim1Length"],
                   "claim1Sha256":current["claim1Sha256"],
                   "claim1Excerpt":current["claim1Text"][:115],
                   "claimsParsed":current["claimCountParsed"],
                   "claimSourceVerified":True,
                   "claimContext":current["claimStatus"]})
    existing=row.get("priorFullTitleCheck") or {}
    past=list(existing.get("matches") or [])
    if not past and old_limit>0:
        try:
            window=(datetime.strptime(row["publicationDate"],"%Y%m%d").date()-timedelta(days=1)).strftime("%Y%m%d")
            found=history(key,row["title"],window)
            past=historical_summary(row,found)["matches"]
        except Exception as error:
            result["historyError"]=type(error).__name__
    # Focus comparable SAME applicant, earlier disclosure and distinct app.
    prior=[p for p in past
           if p.get("overlappingApplicant") is True and
              NUMBER.fullmatch(str(p.get("applicationNumber") or ""))
              and p["applicationNumber"]!=application
              and PUBLICATION.fullmatch(str(p.get("publicationNumber") or ""))]
    for old in prior[:old_limit]:
        try:
            parsed=detail(key,old["applicationNumber"])
            comp=compare_claims(current,parsed)
            result["priorComparisons"].append({**comp,
              "priorPublicationNumber":old["publicationNumber"],
              "priorPublished":old.get("published"),
              "priorApplicants":old.get("applicants"),
              "status":"source_claim_text_compared_no_legal_novelty"})
        except Exception as error:
            result["priorComparisons"].append({
               "priorPublicationNumber":old.get("publicationNumber"),
               "priorApplication":old.get("applicationNumber"),
               "status":"previous_claim_unavailable",
               "errorType":type(error).__name__})
    result["priorCandidateCount"]=len(prior)
    result["status"]=("claim1_and_prior_compared"
                      if any(x["status"]=="source_claim_text_compared_no_legal_novelty"
                             for x in result["priorComparisons"])
                      else "current_claim_only_prior_unverified")
    if news is not None:
        result["relatedPress"]=news(row)
    return result


def choose_candidates(deep,limit):
    rows=deep.get("investigations")
    if not isinstance(rows,list):
        raise ValueError("심층 공보 근거 누락")
    # Known match first if present and still in the same current source.
    pinned=[r for r in rows if r.get("publicationNumber")=="1020260138678"]
    prior=[r for r in rows if (r.get("priorFullTitleCheck") or {}).get("matches")]
    chosen=[]
    seen=set()
    for row in pinned+prior+rows:
        pub=row.get("publicationNumber")
        if not PUBLICATION.fullmatch(str(pub or "")) or pub in seen:
            continue
        if len(chosen)>=limit:
            break
        chosen.append(row)
        seen.add(pub)
    return chosen


def build(deep,patents,key,limit=6,max_prior=2,now=None,detail=official_detail,
          history=historical_title_search,news=related_press):
    now=now or datetime.now(KST)
    if not 1<=limit<=8 or not 0<=max_prior<=2:
        raise ValueError("KIPRIS 상세조회 최대예산 범위 초과")
    if (not isinstance(deep,dict) or not isinstance(patents,dict) or
        deep.get("patentDatasetGeneratedAt")!=patents.get("generatedAt")
        or deep.get("uniquePublicationCount") is None):
        raise ValueError("KIPRIS 공식 공보와 심층 분석 데이터 출처 시각이 일치하지 않음")
    candidates=choose_candidates(deep,limit)
    if not key:
        return {"generatedAt":now.isoformat(),"status":"KIPRIS_SERVICE_KEY unavailable",
                "dataAt":patents.get("generatedAt"),"reviewCount":0,
                "reviews":[],"confirmedScoops":0}
    reports=[]
    for row in candidates:
        reports.append(inspect(row,key,old_limit=max_prior,detail=detail,
                               history=history,news=news))
        if detail is official_detail:
            time.sleep(0.12)
    return {
        "generatedAt":now.isoformat(timespec="seconds"),
        "patentDatasetGeneratedAt":patents["generatedAt"],
        "deepDatasetGeneratedAt":deep.get("generatedAt"),
        "source":"KIPRISPlus getBibliographyDetailInfoSearch official claimInfoArray",
        "scope":"기본 후보 6개 출원서 제1항; 2023년 이후 동일 제목·동일 출원인 일부와 제한 대조",
        "reviewCount":len(reports),
        "currentClaimsVerified":sum(bool(r.get("claimVerified")) for r in reports),
        "pairedClaimsCompared":sum(sum(x.get("status")=="source_claim_text_compared_no_legal_novelty"
                     for x in r.get("priorComparisons",[])) for r in reports),
        "confirmedScoops":0,
        "warning":"청구항 문구 차이≠법적 신규성·진보성. 공개 청구항은 보정·등록 후 권리범위 아님. 기업 사업화·기보도 미확인.",
        "status":"source_claim_review_partial_or_complete",
        "reviews":reports,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--patents",default="digests/patent_hunt_latest.json")
    p.add_argument("--deep",default="digests/patent_deep_latest.json")
    p.add_argument("--output",default="digests/patent_claim_review_latest.json")
    p.add_argument("--max-current",type=int,default=6)
    p.add_argument("--max-prior",type=int,default=2)
    p.add_argument("--no-news",action="store_true")
    args=p.parse_args()
    key=os.getenv("KIPRIS_SERVICE_KEY","").strip()
    if not key:
        raise SystemExit("KIPRIS_SERVICE_KEY 누락: 이전 청구항 비교 데이터 보존")
    patents=json.loads(Path(args.patents).read_text(encoding="utf-8"))
    deep=json.loads(Path(args.deep).read_text(encoding="utf-8"))
    report=build(deep,patents,key,limit=args.max_current,max_prior=args.max_prior,
                 news=None if args.no_news else related_press)
    if report["currentClaimsVerified"]==0:
        # Keep the previous good source data for reporter comparison.
        raise SystemExit("공식 제1항 확인 성공 0건: 기존 결과 보존")
    out=Path(args.output)
    out.parent.mkdir(parents=True,exist_ok=True)
    tmp=out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    tmp.replace(out)
    print(f"공식 제1항 확인 {report['currentClaimsVerified']}/{report['reviewCount']}건,"
          f" 동제목 과거 제1항 직접 대조 {report['pairedClaimsCompared']}건; 단독 확정 0건")


if __name__=="__main__":
    main()
