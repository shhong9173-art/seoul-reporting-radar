"""Patent-to-reporting-angle review with *evidence*, never automatic scoops.

Inputs: official KIPRIS applicant-publication snapshot and deduplicated
patent deep investigation. This layer creates a journalist's QUESTIONS, not
claims of product launches, research assignments or exclusive reporting.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

KST=timezone(timedelta(hours=9))
TOPIC_RULES=(
    ("순환소재·폐차재활용",
     ("재활용","폐플라스틱","폐차","해중합","효소","플라스틱","폴리에스테르","폴리우레탄","재생원료","수지","분해"),
     "회수 소재의 재생 공정과 자동차 부품 재사용 가능성",
     "해당 회수 소재를 자동차 부품에 다시 적용했는가? 회수율·품질·원가·양산 일정은?"),
    ("배터리·전동화",
     ("배터리","전고체","리튬","전지","충전","음극","양극","열폭주","셀"),
     "배터리 안전성·원가·충전성능 또는 전동화 부품 적용",
     "기존 기술 대비 효과 수치와 실제 적용 차종·일정은?"),
    ("자율주행·차량제어",
     ("자율주행","센서","라이다","레이더","차로","경로","차량 제어","모빌리티","시뮬레이션"),
     "차량 인식·제어 기술의 적용 가능 범위",
     "기존 자율주행·안전 시스템 대비 청구항의 실제 차이는?"),
    ("전력망·전력기기",
     ("변압기","차단기","절연","직류","송전","배전","hvdc","전력 변환","전력변환"),
     "전력설비 생산성·효율·수명 관련 기술 적용",
     "실제 제조·출하 품목인지? 고객·시험 규격·제품화 단계는?"),
    ("철강·비철 소재",
     ("제철","강판","수소환원","합금","아연","동","전기로","압연","도금"),
     "소재 제조공정·품질·원가 관련 기술 적용",
     "실제 생산공정·판매제품에 반영됐는지, 기술 효과는 검증됐는가?"),
    ("제조공정·자동화",
     ("공정","로봇","금형","용접","검사","자동화","냉각","제조","성형"),
     "제조 현장 적용·생산성 변화 가능성",
     "실제 어느 공장/공정에 적용됐으며 수율·설비투자 변화가 있는가?"),
)


def compact(s):
    return re.sub(r"\s+"," ",str(s or "")).strip()


def topic_for(title,abstract):
    title=compact(title).lower()
    abstract=compact(abstract).lower()
    for name,terms,angle,question in TOPIC_RULES:
        matches=[word for word in terms if word in title]
        if matches:
            return {"topic":name,"matchedSource":"발명명칭",
                    "matchedTerms":matches[:4],"impactToVerify":angle,
                    "question":question}
    for name,terms,angle,question in TOPIC_RULES:
        matches=[word for word in terms if word in abstract]
        if matches:
            return {"topic":name,"matchedSource":"공식 초록",
                    "matchedTerms":matches[:4],"impactToVerify":angle,
                    "question":question}
    return {"topic":"미분류·이종산업 탐색","matchedSource":"키워드 매칭 없음",
            "matchedTerms":[],"impactToVerify":"차량·산업 공정과의 실질 연관성 미확인",
            "question":"공동출원인의 기술분야와 실제 산업 적용 방향은 무엇인가?"}


def official_excerpt(text,length=185):
    """Reproduce only the officially retrieved abstract, no synthetic claims."""
    s=compact(text)
    return s[:length]+("…" if len(s)>length else "")


def _brand_for_press(name):
    """Broader newsroom names; never presented as legal-entity evidence."""
    value=compact(name)
    if "씨제이제일제당" in value or "CJ제일제당" in value:
        return "CJ제일제당"
    if "현대자동차" in value:
        return "현대차"
    return re.sub(r"(주식회사|산학협력단|\(주\))","",value).strip()[:24]


def _distinctive_terms(row):
    source=(compact(row.get("title"))+" "+compact(row.get("sourceAbstractExcerpt") or row.get("abstract"))).lower()
    tokens=("효소","플라스틱","재활용","해중합","폴리에스테르","폐차","폴리우레탄",
            "전고체","배터리","충전","음극","양극","수소","연료전지",
            "라이다","레이더","자율주행","변압기","송전","도금","전기로","냉각")
    return [x for x in tokens if x in source][:3]


def news_queries(row):
    """Different article wording must be searched, not just patent title."""
    number=re.sub(r"[^0-9]","",row.get("publicationNumber") or "")
    title=compact(row.get("title"))
    issuers=(row.get("coveredCompanies") or [])
    outsiders=(row.get("outsideBeatCoApplicants") or [])
    main=("현대차" if any("현대자동차" in n for n in issuers)
          else _brand_for_press(issuers[0]) if issuers else "")
    partner=_brand_for_press(outsiders[0]) if outsiders else ""
    terms=_distinctive_terms(row)
    queries=[]
    if re.fullmatch(r"10\d{11}",number):
        queries.append('"'+number+'"')
    if title:
        queries.append('"'+title[:48]+'" '+(partner or main))
    if partner and main:
        # This catches headlines such as 'CJ·현대차, 플라스틱 먹는 효소'
        # where neither the formal patent title nor publication number appears.
        queries.append(" ".join([main,partner]+terms[:2]+["특허"]))
    elif main and terms:
        queries.append(" ".join([main]+terms[:2]+["특허"]))
    return list(dict.fromkeys(queries))[:3]


def rss_fetch(url):
    request=Request(url,headers={"User-Agent":"newsroom-patent-story-coverage/1.0"})
    with urlopen(request,timeout=8) as result:
        return result.read(450001)


def search_press(row,fetch=rss_fetch):
    queries=news_queries(row)
    searches=[]
    for query in queries:
        url="https://news.google.com/rss/search?q="+quote(query)+"&hl=ko&gl=KR&ceid=KR:ko"
        try:
            raw=fetch(url)
            if len(raw)>450000 or b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
                raise ValueError("RSS invalid or oversized")
            tree=ET.fromstring(raw)
            if tree.tag!="rss" or tree.find("channel") is None:
                raise ValueError("RSS format invalid")
            hits=[]
            for story in tree.findall("./channel/item")[:10]:
                headline=html.unescape(compact(story.findtext("title")))[:180]
                uri=compact(story.findtext("link"))
                if headline and uri.startswith("https://news.google.com/"):
                    hits.append({"title":headline,"url":uri,
                                 "publishedAt":compact(story.findtext("pubDate"))[:55]})
                if len(hits)>=3:
                    break
            searches.append({"query":query,"status":"hits" if hits else "no_hits",
                             "articles":hits})
        except (ET.ParseError,OSError,TimeoutError,ValueError) as exc:
            searches.append({"query":query,"status":"error","error":type(exc).__name__,
                             "articles":[]})
    has_hits=any(x["status"]=="hits" for x in searches)
    failed=any(x["status"]=="error" for x in searches)
    return {"status":("관련 검색 기사 발견 · 동일 기술/기보도 여부 확인" if has_hits
                      else "검색 오류 포함 · 기보도 여부 미확인" if failed
                      else "검색 미발견 · 미보도 증명 아님"),
            "queries":searches,"possibleEarlierCoverage":has_hits,
            "completeSearch":not failed,"scoopConfirmed":False}


def article_hypothesis(row,topic):
    covered=[compact(x) for x in (row.get("coveredCompanies") or []) if compact(x)]
    outsiders=[compact(x) for x in (row.get("outsideBeatCoApplicants") or []) if compact(x)]
    company="·".join(covered[:2]) if covered else compact(row.get("company"))
    if outsiders:
        company+="·"+compact(outsiders[0]).replace(" 주식회사","")[:25]
    verb="공동출원" if row.get("jointApplicantGroup") else "특허 공개"
    title=compact(row.get("title"))[:73]
    # A literal evidence-based draft title, not an unverified conclusion.
    return company+", '"+title+"' "+verb


def prioritize(row,topic,now):
    try:
        age=(now.date()-datetime.strptime(row["publicationDate"],"%Y%m%d").date()).days
    except (ValueError,KeyError):
        age=999
    fresh=0<=age<=3
    outside=bool(row.get("outsideBeatCoApplicants"))
    # Raw-document research priority, not likelihood of exclusivity.
    score=(20+30*outside+8*bool(row.get("jointApplicantGroup"))+
           (14 if fresh else 0)+
           (10 if topic["matchedSource"]=="발명명칭" else 5 if topic["matchedSource"]=="공식 초록" else 0)+
           (7 if row.get("freshObservation") else 0))
    if age>14:
        score-=12
    if row.get("historicalBackfill"):
        score-=15
    return max(1,min(90,score)),fresh,age


def build(official,deep,now=None,max_news=8,press=search_press):
    now=now or datetime.now(KST)
    if not isinstance(official.get("items"),list) or not isinstance(deep.get("investigations"),list):
        raise ValueError("KIPRIS source data incomplete")
    if official.get("generatedAt")!=deep.get("patentDatasetGeneratedAt"):
        raise ValueError("Official and deep snapshots have different dates")
    # The deep ranking view is intentionally limited to 60, so reconstruct
    # ALL verified publications here from the official complete list.
    from patent_deep_hunt import merge_publications
    all_rows,rejected=merge_publications(official)
    stories=[]
    for row in all_rows:
        topic=topic_for(row.get("title"),row.get("abstract"))
        priority,fresh,age=prioritize(row,topic,now)
        outsiders=row.get("outsideBeatCoApplicants") or []
        if not outsiders and not fresh and not row.get("freshObservation"):
            continue  # retain full source; surface selective *investigations*
        stories.append({
            "publicationNumber":row["publicationNumber"],
            "applicationNumber":row.get("applicationNumber"),
            "publicationDate":row.get("publicationDate"),
            "applicationDate":row.get("applicationDate"),
            "coveredCompanies":row.get("coveredCompanies"),
            "outsideBeatCoApplicants":outsiders,
            "applicants":row.get("applicants"),
            "title":row.get("title"),
            "sourceAbstractExcerpt":official_excerpt(row.get("abstract")),
            "technologyEvidenceStatus":("공식 초록 근거 · 청구항 차이 미검증"
                                        if row.get("abstract") else "초록 원문 없음 · 청구항 검증 필요"),
            "topic":topic["topic"],"topicDetectionSource":topic["matchedSource"],
            "topicEvidenceTerms":topic["matchedTerms"],
            "reportingTitleDraft":article_hypothesis(row,topic),
            "industryImpactToVerify":topic["impactToVerify"],
            "questions":[
                "공동출원인별 기술 기여·개발 단계·권리관계를 회사에 확인했는가?" if outsiders
                    else "기술 담당 조직·실제 목적을 회사에 확인했는가?",
                topic["question"],
                "청구항·유사 특허/특허패밀리와 과거 공개 시점·기보도 원문을 확인했는가?"
            ],
            "rank":priority,"daysSincePublic":age,
            "recentPublication":fresh,
            "freshObservation":bool(row.get("freshObservation")),
            "historicalBackfill":bool(row.get("historicalBackfill")),
            "publicationSource":"KIPRISPlus 공식 특허 공개공보 API",
            "pressCoverage":{"status":"미조회 · 미보도 확정 불가"},
            "scoopConfirmed":False,
            "status":"기사 가설 · 실제 성과/출시/단독 미확인"
        })
    stories.sort(key=lambda x:(-x["rank"],-int(x.get("publicationDate") or 0),x["publicationNumber"]))
    if not 0<=max_news<=20:
        raise ValueError("Max news lookups outside 0-20")
    for item in stories[:max_news]:
        item["pressCoverage"]=press(item)
        # A media hit flags editorial checking, never a definitive duplicate.
        if item["pressCoverage"].get("possibleEarlierCoverage"):
            item["status"]="기보도 가능성 · 원문 기사 대조 먼저"
    return {
        "generatedAt":now.isoformat(timespec="seconds"),
        "officialSourceGeneratedAt":official.get("generatedAt"),
        "deepSourceGeneratedAt":deep.get("generatedAt"),
        "sourceWindow":official.get("reportingWindow"),
        "sourceWindowComplete":bool(official.get("sourceWindowComplete")),
        "allVerifiedPublications":len(all_rows),
        "unclassifiedVerifiedRecords":official.get("unclassifiedCount"),
        "possibleResearchLeads":len(stories),
        "outsidePartnerLeads":sum(bool(x["outsideBeatCoApplicants"]) for x in stories),
        "mediaQueriesCompleted":sum(len((x.get("pressCoverage") or {}).get("queries",[])) for x in stories),
        "rejectedConflictPublications":rejected,
        "investigations":stories[:80],
        "unshownInvestigations":max(0,len(stories)-80),
        "sourceScope":"담당 24개 법인의 최근 35일 공개공보; 출입처 외 기업 단독출원은 미포함",
        "mediaCaveat":"Google 뉴스 RSS 번호·제목·이종 산업 키워드 최대 3개 검색식/상위 후보 일부; 검색 무결성·전 매체 선행 보도 확인 불가",
        "confirmedScoops":0,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",default="digests/patent_hunt_latest.json")
    p.add_argument("--deep",default="digests/patent_deep_latest.json")
    p.add_argument("--out",default="digests/patent_story_latest.json")
    p.add_argument("--max-news",type=int,default=8)
    args=p.parse_args()
    official=json.loads(Path(args.source).read_text(encoding="utf-8"))
    deep=json.loads(Path(args.deep).read_text(encoding="utf-8"))
    report=build(official,deep,max_news=args.max_news)
    out=Path(args.out)
    out.parent.mkdir(parents=True,exist_ok=True)
    tmp=out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    tmp.replace(out)
    print("verified",report["allVerifiedPublications"],
          "outside-leads",report["outsidePartnerLeads"],
          "media-searches",report["mediaQueriesCompleted"],
          "confirmed-scoops",report["confirmedScoops"])


if __name__=="__main__":
    main()
