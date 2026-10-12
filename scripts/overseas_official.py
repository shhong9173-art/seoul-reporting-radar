"""Official overseas government evidence leads, not awarded contracts or permits.

Sources: US Federal Register published notices; EU TED published procurement
notices. Official state/county building permits and local environmental permits
are NOT covered. Mentions never imply supplier/beneficiary/project ownership.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

KST=timezone(timedelta(hours=9))
FR_API="https://www.federalregister.gov/api/v1/documents.json"
TED_API="https://api.ted.europa.eu/v3/notices/search"
ALIASES={
    "현대자동차":("Hyundai Motor","Hyundai Motor Company"),
    "기아":("Kia Corporation","Kia Motors"),
    "두산에너빌리티":("Doosan Enerbility",),
    "효성중공업":("Hyosung Heavy Industries",),
    "HD현대일렉트릭":("HD Hyundai Electric",),
    "고려아연":("Korea Zinc",),
}
DAYS=30
TED_FIELDS=["publication-number","notice-title","buyer-name",
            "publication-date","notice-type","buyer-country"]


def read_json(request):
    with urlopen(request,timeout=18) as response:
        content=response.read(2_000_001)
    if len(content)>2_000_000:
        raise ValueError("공식 문서 API 응답 용량 상한 초과")
    parsed=json.loads(content.decode("utf-8-sig"))
    if not isinstance(parsed,dict):
        raise ValueError("공식 문서 API 결과 객체가 아님")
    return parsed


def exact_mention(text,alias):
    """Prevent short Hyundai/Kia/LS substrings from matching unrelated firms."""
    if not isinstance(text,str) or not text:
        return False
    expression=r"(?<![A-Za-z0-9])"+re.escape(alias)+r"(?![A-Za-z0-9])"
    return re.search(expression,text,re.I) is not None


def match_company(text):
    return [company for company,aliases in ALIASES.items()
            if any(exact_mention(text,alias) for alias in aliases)]


def federal_register(term,since,fetch=read_json):
    params={
        "conditions[term]":term,
        "conditions[publication_date][gte]":since,
        "order":"newest","per_page":"25",
    }
    url=FR_API+"?"+urlencode(params)
    data=fetch(Request(url,headers={"User-Agent":"newsroom-official-research/1.0","Accept":"application/json"}))
    if not isinstance(data.get("results"),list):
        raise ValueError("Federal Register results 누락: 검색 완료 아님")
    items=[]
    for r in data["results"]:
        if not isinstance(r,dict):
            continue
        title=str(r.get("title") or "").strip()
        abstract=str(r.get("abstract") or "").strip()
        # Search engine matching inside full text is insufficient proof;
        # require the company name in visible original title/abstract.
        hits=match_company(title+" "+abstract)
        identifier=str(r.get("document_number") or "")
        published=str(r.get("publication_date") or "")
        link=str(r.get("html_url") or "")
        if not (re.fullmatch(r"20\d{2}-\d{4,6}",identifier)
                and re.fullmatch(r"20\d{2}-\d{2}-\d{2}",published)
                and link.startswith("https://www.federalregister.gov/documents/")):
            continue
        items.append({
            "source":"US Federal Register","sourceType":"federal_notice",
            "sourceId":identifier,"published":published,
            "companiesMentioned":hits,"companySearchTerm":term,
            "nameVerified":bool(hits),"title":title[:260],
            "abstract":abstract[:350],"sourceUrl":link,
            "evidence":("공식 연방 고시의 제목·요약에 기업명 등장" if hits
                        else "연방 고시 검색 색인 일치: 기업명·사건 관계를 원문에서 확인하지 못함"),
            "notProven":"지역 공장허가 취득·회사 사업 확정·직접 수주 여부 미확인",
            "exclusiveStatus":"공개 문서 취재 단서·단독 미확정",
        })
    return {"query":term,"returned":len(data["results"]),
            "totalReported":data.get("count"),"items":items,
            "status":"checked"}


def multilingual(data):
    if isinstance(data,str):
        return data
    if isinstance(data,list):
        return " ".join(multilingual(v) for v in data)
    if isinstance(data,dict):
        for preferred in ("eng","kor","deu","fra"):
            if data.get(preferred):
                return multilingual(data[preferred])
        for v in data.values():
            out=multilingual(v)
            if out:
                return out
    return ""


def ted_procurement(term,since,fetch=read_json):
    # TED official v3 expert query (not a general web search).
    q='FT~"'+term.replace('"',"")+'" AND publication-date>='+since.replace("-","")+' SORT BY publication-date DESC'
    payload={"query":q,"fields":TED_FIELDS,"limit":25,"scope":"ALL","paginationMode":"PAGE_NUMBER","page":1}
    request=Request(TED_API,data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type":"application/json","Accept":"application/json",
                             "User-Agent":"newsroom-official-research/1.0"},method="POST")
    result=fetch(request)
    if result.get("timedOut") is True or not isinstance(result.get("notices"),list):
        raise ValueError("EU TED 검색 미완료/응답 스키마 오류")
    items=[]
    for notice in result["notices"]:
        if not isinstance(notice,dict):
            continue
        number=str(notice.get("publication-number") or "")
        if not re.fullmatch(r"\d{1,9}-20\d{2}",number):
            continue
        title=multilingual(notice.get("notice-title")).strip()[:260]
        buyer=multilingual(notice.get("buyer-name")).strip()[:170]
        # A free-text match can be in the full notice body. If the title or
        # buyer lacks an exact legal/company identity, do not assert a link.
        companies=match_company(title+" "+buyer)
        published=str(notice.get("publication-date") or "")[:10]
        if not re.fullmatch(r"20\d{2}-\d{2}-\d{2}",published):
            continue
        items.append({
            "source":"EU TED","sourceType":"eu_procurement_notice",
            "sourceId":number,"published":published,
            "companiesMentioned":companies,"companySearchTerm":term,
            "nameVerified":bool(companies),"title":title,"buyer":buyer,
            "sourceUrl":f"https://ted.europa.eu/en/notice/{number}/html",
            "evidence":("EU 조달 공고 제목·발주자 필드에 회사 실명 확인" if companies
                        else "TED 전문검색 일치: 공식 공고에서 해당 기업의 역할 확인 전"),
            "notProven":"낙찰·공급사 선정·계약금액·해당 회사 사업 귀속 여부 미확인",
            "exclusiveStatus":"공개 조달 공고 취재 단서·단독 미확정",
        })
    return {"query":term,"returned":len(result["notices"]),
            "totalReported":result.get("totalNoticeCount"),"items":items,
            "status":"checked"}


def collect(now=None,fr=federal_register,ted=ted_procurement):
    now=now or datetime.now(KST)
    since=(now-timedelta(days=DAYS)).date().isoformat()
    sources=[]
    documents=[]
    seen=set()
    tasks=[
        (fr,"US Federal Register","Hyundai Motor"),
        (fr,"US Federal Register","Doosan Enerbility"),
        (fr,"US Federal Register","Kia Motors"),
        (fr,"US Federal Register","Korea Zinc"),
        (ted,"EU TED","Hyundai Motor"),
        (ted,"EU TED","Hyosung Heavy Industries"),
        (ted,"EU TED","HD Hyundai Electric"),
        (ted,"EU TED","Doosan Enerbility"),
    ]
    for func,provider,term in tasks:
        try:
            result=func(term,since)
            for d in result.get("items",[]):
                identity=(d["source"],d["sourceId"])
                if identity not in seen:
                    seen.add(identity)
                    documents.append(d)
            sources.append({"provider":provider,"query":term,"status":"checked",
                            "returned":result.get("returned"),
                            "matched":sum(bool(x.get("nameVerified")) for x in result.get("items",[])),
                            "unverified":sum(not x.get("nameVerified") for x in result.get("items",[]))})
        except Exception as err:
            sources.append({"provider":provider,"query":term,"status":"source_error",
                            "errorType":type(err).__name__,
                            "errorDetail":str(err)[:155],"matched":None})
    documents.sort(key=lambda row:(row["published"],row["sourceId"]),reverse=True)
    return {
        "generatedAt":now.isoformat(timespec="seconds"),
        "lookbackDays":DAYS,"windowStart":since,
        "scope":"US Federal Register 연방 고시 및 EU TED 공개 조달 공고",
        "limits":"미국 주·카운티 건축/환경 인허가, EU 각국 소액 조달, 모든 세계 공장 인허가를 망라하지 않음",
        "checks":sources,"documents":documents,
        "matchedCount":sum(bool(x.get("nameVerified")) for x in documents),
        "unverifiedSearchMatches":sum(not x.get("nameVerified") for x in documents),
        "sourceErrors":sum(x["status"]=="source_error" for x in sources),
        "scoopConfirmed":0,
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",default="digests/overseas_official_latest.json")
    args=ap.parse_args()
    data=collect()
    # Do not overwrite a valid snapshot with provider downtime.
    if all(x["status"]=="source_error" for x in data["checks"]):
        raise SystemExit("해외 공식 원천 전체 조회 장애: 기존 자료 보존")
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
    temp=output.with_suffix(".json.tmp")
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    temp.replace(output)
    print(f"해외 공식 원천 8회 질의, 원문 기업언급 {data['matchedCount']}건, "
          f"API 오류 {data['sourceErrors']}건, 단독 확정 0건")


if __name__=="__main__":
    main()
