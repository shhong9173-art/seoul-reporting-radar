"""Cross-check patent story leads against actual official and indexed evidence.

This is a reporter triage queue, NOT a patent novelty opinion, confirmed
commercial application or a scoop certificate. No language-model guesses.
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST=timezone(timedelta(hours=9))
STOP={"방법","장치","이를","포함하는","포함한","위한","이용한","및","그","기술","관한",
      "시스템","자동차","차량","제조","기반","일","형성","특허","발명","통한","제어"}
NEGATIVE={"already_reported","wrong_beat","unsupported_angle","low_value"}
VALID_PUB=re.compile(r"^10\d{11}$")


def tokens(value):
    terms=re.findall(r"[가-힣A-Za-z0-9]{2,}",str(value or "").lower())
    return {x for x in terms if x not in STOP and len(x)>=2}


def headline_match(story,headline):
    """Indexed headline resemblance is a clue, not proof of same reporting."""
    title=str(story.get("title") or "")
    headline=str(headline or "")
    pub=re.sub(r"\D","",str(story.get("publicationNumber") or ""))
    compact=re.sub(r"\D","",headline)
    if VALID_PUB.fullmatch(pub) and pub in compact:
        return "publication_number_visible",1.0
    norm=lambda v:re.sub(r"[\W_]","",v).lower()
    if len(norm(title))>=12 and norm(title) in norm(headline):
        return "invention_title_visible",0.95
    # Alternative headlines often omit the legal invention title: e.g.
    # "플라스틱 먹는 효소" versus CJ/Hyundai's official long PET claim title.
    # Two explicitly shared technical concepts are an ARTICLE REVIEW FLAG,
    # not proof that the entire patent or business plan was already reported.
    excerpt=str(story.get("sourceAbstractExcerpt") or "").lower()
    signals=("효소","플라스틱","재활용","해중합","폐차","전고체","배터리",
             "열폭주","음극","양극","변압기","송전","수소","연료전지",
             "자율주행","라이다","레이더","도어","휠체어",
             "모터","철심","아연","동박","냉각","충전")
    concept=[word for word in signals
             if word in (title+" "+excerpt).lower() and word in headline.lower()]
    if len(concept)>=2:
        return "abstract_tech_headline_overlap_review",round(min(0.9,0.5+len(concept)*0.1),2)
    a=tokens(title)
    b=tokens(headline)
    if len(a)<2 or not b:
        return "weak_or_generic_index_hit",0.0
    shared=len(a & b)
    overlap=round(shared/len(a),2)
    if shared>=2 and overlap>=0.55:
        return "technical_headline_overlap_review",overlap
    return "weak_or_generic_index_hit",overlap


def press_assessment(lead):
    data=lead.get("pressCoverage") or {}
    queries=data.get("queries")
    if not isinstance(queries,list) or not queries:
        return {"state":"not_searched","checked":False,"hits":0,"articleEvidence":[],
                "warning":"언론 검색 미실시. 단독 또는 미보도 추정 금지"}
    evidence=[]
    errors=0
    for q in queries:
        if q.get("status")=="error":
            errors+=1
        for article in (q.get("articles") or []):
            kind,score=headline_match(lead,article.get("title"))
            url=str(article.get("url") or "")
            if not url.startswith("https://news.google.com/"):
                continue
            if not any(z["url"]==url for z in evidence):
                evidence.append({"headline":str(article.get("title") or "")[:180],
                                 "url":url,"publishedAt":article.get("publishedAt"),
                                 "headlineRelation":kind,"titleOverlap":score,
                                 "samePatentConfirmed":False})
    strong=any(x["headlineRelation"] in ("publication_number_visible","invention_title_visible",
                                        "abstract_tech_headline_overlap_review",
                                        "technical_headline_overlap_review") for x in evidence)
    state=("indexed_potential_same_technology" if strong else
           "indexed_articles_need_review" if evidence else
           "search_errors_not_cleared" if errors else
           "index_no_hits_not_proof")
    return {"state":state,"checked":True,"hits":len(evidence),"articleEvidence":evidence[:5],
            "searchErrors":errors,"warning":"검색 제목 일치만으로 동일 특허 보도 확정 불가; 기사 본문·발행일과 회사 발표 별도 확인"}


def recent_priors(lead,source,limit=3):
    """Within the collected disclosure window only, not a full prior-art search."""
    pub=lead["publicationNumber"]
    date=lead.get("publicationDate") or ""
    name=lead.get("title") or ""
    norm=lambda s:re.sub(r"\s+","",str(s or "")).lower()
    if not name or len(norm(name))<8:
        return []
    current=tokens(name)
    results=[]
    for row in source.get("items",[]):
        other=row.get("publicationNumber")
        if other==pub or not VALID_PUB.fullmatch(str(other or "")):
            continue
        day=row.get("publicationDate") or ""
        if not day or day>=date:
            continue
        old=row.get("title") or ""
        similarity=round(difflib.SequenceMatcher(None,norm(name),norm(old),autojunk=False).ratio(),3)
        common=current & tokens(old)
        if similarity<0.69 or (len(common)<2 and similarity<0.93):
            continue
        results.append({"publicationNumber":other,"publicationDate":day,
                        "title":old[:150],"titleSimilarity":similarity,
                        "comparisonScope":"동일 35일 공보 내 발명명칭 문자열 유사: 청구항·우선권/동일패밀리 미확인"})
    results.sort(key=lambda x:(-x["titleSimilarity"],-int(x["publicationDate"])))
    unique={}
    for r in results:
        unique.setdefault(r["publicationNumber"],r)
    return list(unique.values())[:limit]


def human_final(reviews):
    out={}
    for event in reviews.get("reviews",[]):
        if isinstance(event,dict) and VALID_PUB.fullmatch(str(event.get("publicationNumber") or "")):
            out[event["publicationNumber"]]=event
    return out


def evaluate(official,deep,story,claim,reviews,benchmarks,now=None,top=5):
    now=now or datetime.now(KST)
    if not 1<=top<=5:
        raise ValueError("Desk shortlist must contain 1-5 places")
    if (official.get("sourceWindowComplete") is not True
        or story.get("officialSourceGeneratedAt")!=official.get("generatedAt")
        or deep.get("patentDatasetGeneratedAt")!=official.get("generatedAt")
        or story.get("deepSourceGeneratedAt")!=deep.get("generatedAt")
        or not isinstance(story.get("investigations"),list)):
        raise ValueError("Official, deep and story snapshots do not match")
    if not isinstance(reviews.get("reviews"),list) or not isinstance(benchmarks.get("cases"),list):
        raise ValueError("Human reviews / retrospective known cases missing")
    claims_consistent=bool(
        claim.get("patentDatasetGeneratedAt")==official.get("generatedAt")
        and claim.get("deepDatasetGeneratedAt")==deep.get("generatedAt"))
    claim_by_pub={x.get("publicationNumber"):x for x in claim.get("reviews",[])
                  if claims_consistent and isinstance(x,dict)}
    # Deep output intentionally contains only part of the 35-day candidates.
    deep_by_pub={x.get("publicationNumber"):x for x in deep.get("investigations",[])}
    labels=human_final(reviews)
    known={str(x.get("publicationNumber")) for x in benchmarks["cases"]}
    rows=[]
    for lead in story["investigations"]:
        pub=str(lead.get("publicationNumber") or "")
        if not VALID_PUB.fullmatch(pub):
            continue
        news=press_assessment(lead)
        prev=recent_priors(lead,official)
        deep_row=deep_by_pub.get(pub) or {}
        historical=deep_row.get("priorFullTitleCheck")
        if historical is not None:
            hist={"state":"searched_same_title_only",
                  "queryComplete":bool(historical.get("complete")),
                  "matches":(historical.get("matches") or [])[:3],
                  "status":historical.get("status")}
        else:
            hist={"state":"not_checked","queryComplete":False,
                  "matches":[],"status":"이 특허의 과거 동일 제목 KIPRIS API 대조 미실시"}
        claim_row=claim_by_pub.get(pub)
        claim_evidence={"state":("official_claim1_verified" if claim_row.get("claimVerified")
                                  else "official_claim1_lookup_incomplete")
                                 if claim_row else "not_checked",
                        "verified":bool(claim_row and claim_row.get("claimVerified")),
                        "claim1Excerpt":(claim_row.get("claim1Excerpt") if claim_row else None),
                        "comparisons":(claim_row.get("priorComparisons") or [])[:2] if claim_row else [],
                        "warning":"청구항 문구 차이만으로 신규성·기술적 우월성 확정 불가"}
        verdict=labels.get(pub,{}).get("decision")
        excluded=[]
        if pub in known:
            excluded.append("known_post_publication_benchmark")
        if verdict in NEGATIVE:
            excluded.append("human_editorial_negative")
        if verdict=="published":
            excluded.append("already_published_by_reporter")
        if news["state"]=="indexed_potential_same_technology":
            excluded.append("indexed_similar_article_needs_manual_review")
        if hist["matches"]:
            excluded.append("older_same_title_publication_needs_claim_check")
        # A source-grounded *research queue* score, never scoop likelihood.
        score=int(lead.get("rank") or 0)
        score+=12 if claim_evidence["verified"] else 0
        score+=5 if hist["state"]=="searched_same_title_only" else 0
        score+=4 if news["checked"] and news["state"]=="index_no_hits_not_proof" else 0
        score-=17 if news["state"]=="indexed_potential_same_technology" else 0
        score-=9 if hist["matches"] else 0
        score-=25 if not news["checked"] else 0
        score-=90 if "known_post_publication_benchmark" in excluded else 0
        score-=110 if verdict in NEGATIVE|{"published"} else 0
        if lead.get("historicalBackfill"):
            score-=20
        questions=[
            "공개특허의 제1항 핵심 기술 구성과 기존 유사 특허의 실제 차이는 무엇인가?",
            "같은 기술을 먼저 다룬 언론 기사·해외 기사·회사 발표의 본문은 확인했는가?",
            "공동출원인별 연구 역할, 특허 권리관계와 실제 제품·설비 적용 여부는?",
            "효과 수치·사업 규모·양산 시점은 업체 자료/공식 검증으로 확인됐는가?",
        ]
        outline=[
            "공식 공개공보 "+pub+" / 공개일 "+str(lead.get("publicationDate"))+
              " / 출원인 "+", ".join((lead.get("applicants") or [])[:4]),
            "발명명칭 '"+str(lead.get("title") or "")[:95]+"' 및 공식 초록(청구항 별도 검증)",
            "기보도·과거특허·실제 사업 적용 미확인: 업체 직접 답변 확인 후 기사 야마 확정",
        ]
        rows.append({
            "publicationNumber":pub,"publicationDate":lead.get("publicationDate"),
            "reportingTitleDraft":lead.get("reportingTitleDraft"),
            "title":lead.get("title"),"coveredCompanies":lead.get("coveredCompanies") or [],
            "outsideBeatCoApplicants":lead.get("outsideBeatCoApplicants") or [],
            "topic":lead.get("topic"),"sourceAbstractExcerpt":lead.get("sourceAbstractExcerpt"),
            "sourceRank":lead.get("rank"),"evidencePriorityScore":score,
            "priorWithin35Days":prev,"olderSameTitle":hist,
            "claim1Review":claim_evidence,"mediaReview":news,
            "humanEditorialDecision":verdict or "not_reviewed",
            "retrospectiveKnownCase":pub in known,"cautionFlags":excluded,
            "deskStatus":("known_or_reported_not_scoop" if pub in known or verdict in NEGATIVE|{"published"}
                          else "earlier_coverage_requires_comparison" if news["state"]=="indexed_potential_same_technology"
                          else "research_first_media_not_checked" if not news["checked"]
                          else "research_first_company_reply_missing"),
            "questions":questions,"pitchOutlineDraft":outline,
            "scoopConfirmed":False,"companyResponsesVerified":False,
            "publicationNoveltyConfirmed":False,
            "warning":"공보의 기술 가설만 확인. 언론 전문·청구항 전수·사업화·기업 직접 답변·단독은 별도 취재 필요"
        })
    rows.sort(key=lambda x:(-x["evidencePriorityScore"],
                            -int(x.get("publicationDate") or 0),x["publicationNumber"]))
    eligible=[x for x in rows if not x["cautionFlags"] and
              x["mediaReview"]["checked"]]
    # At least one full RSS attempt (no claim that full press survey is done).
    choices=eligible[:top]
    return {
        "generatedAt":now.isoformat(timespec="seconds"),
        "officialSourceGeneratedAt":official["generatedAt"],
        "deepSourceGeneratedAt":deep["generatedAt"],
        "storySourceGeneratedAt":story["generatedAt"],
        "claimSourceGeneratedAt":claim.get("generatedAt") if claims_consistent else None,
        "claimSnapshotConsistent":claims_consistent,
        "candidateCount":len(rows),"newsSearched":sum(x["mediaReview"]["checked"] for x in rows),
        "claim1Checked":sum(x["claim1Review"]["verified"] for x in rows),
        "historyTitleSearched":sum(x["olderSameTitle"]["state"]=="searched_same_title_only" for x in rows),
        "replayExcluded":sum(x["retrospectiveKnownCase"] for x in rows),
        "shortlistCount":len(choices),"shortlist":choices,
        "reviewQueue":rows,
        "confirmedScoops":0,"publicationReady":0,
        "status":"research_priorities_only",
        "warnings":[
            "후보 순위와 검토 가제는 수동 취재 전 단계. 단독 확인·기사 발제 승인 아님",
            "구글뉴스 검색 0건은 미보도 증명이 아니며, 발견 기사 제목 유사도는 본문 동일성 증명 아님",
            "과거 특허 대조는 35일 수집 윈도 및 일부 동일 제목 조회. 특허패밀리/선행기술 전체 아님",
            "기업 직접 답변·사업화 증거가 아직 없으면 출고용 사실·인과관계를 생성하지 않음",
        ],
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--official",default="digests/patent_hunt_latest.json")
    p.add_argument("--deep",default="digests/patent_deep_latest.json")
    p.add_argument("--story",default="digests/patent_story_latest.json")
    p.add_argument("--claims",default="digests/patent_claim_review_latest.json")
    p.add_argument("--reviews",default="data/patent_editorial_reviews.json")
    p.add_argument("--benchmarks",default="data/patent_benchmark_cases.json")
    p.add_argument("--out",default="digests/patent_desk_latest.json")
    p.add_argument("--top",type=int,default=5)
    args=p.parse_args()
    load=lambda x:json.loads(Path(x).read_text(encoding="utf-8"))
    # Optional claim evidence must never be reused from a different vintage.
    try:
        claims=load(args.claims)
    except (OSError,ValueError):
        claims={}
    report=evaluate(load(args.official),load(args.deep),load(args.story),
                    claims,load(args.reviews),load(args.benchmarks),top=args.top)
    path=Path(args.out)
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    temp.replace(path)
    print("KIPRIS desk: reviewed",report["candidateCount"],
          "shortlist",report["shortlistCount"],"scoops verified",report["confirmedScoops"])


if __name__=="__main__":
    main()
