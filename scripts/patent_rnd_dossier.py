"""Cross-source investigative dossiers for KIPRIS patents, with strict provenance.

Combines only snapshots already collected by separate verified pipelines.
NTIS research-project search links are investigator *queries*, NEVER ingested
project awards. IRIS public calls are not project selection.
Same-company DART documents, even with matching technical terms, do not
establish common R&D programs, licensing, commercialization or scoops.
"""
from __future__ import annotations
import argparse
import json
import re
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

KST = timezone(timedelta(hours=9))
PUB = re.compile(r"^10\d{11}$")
DART = re.compile(r"^https://dart\.fss\.or\.kr/dsaf001/main\.do\?rcpNo=(\d{14})$")
NTIS_SEARCH = "https://www.ntis.go.kr/ThSearchProjectList.do?searchWord="
NTIS_API_INFO = "https://www.data.go.kr/data/15077315/openapi.do"
IRIS_CALLS = "https://www.iris.go.kr/main.do"
BLOCKED_STAGES = {"hold_for_review", "media_check_first"}
# These are *search terms*, not proof of technical identity or a project.
TECH_TERMS = (
    "부분방전", "상변태", "비파괴검사", "전고체", "고정자냉각",
    "고정자", "액체냉각", "해중합", "폐플라스틱", "재활용",
    "휠체어", "전력변환", "수소환원", "철심적층", "양극재",
    "음극재", "전력케이블", "전기로", "침투탐상"
)


def parse_date(value):
    try:
        return datetime.strptime(str(value), "%Y%m%d").date()
    except (ValueError, TypeError):
        return None


def dossier_sources(row, now):
    """Keep only verified-shape DART links, preserve original filing dates."""
    out = []
    for event in (row.get("independentDartTechnicalOverlap") or []):
        url = event.get("url")
        match = DART.fullmatch(str(url))
        if not match:
            continue
        filing = parse_date(event.get("published")) or parse_date(match.group(1)[:8])
        out.append({
            "relation": "same_issuer_technical_words_only",
            "type": event.get("sourceType"),
            "sourceUrl": url,
            "filingDate": filing.isoformat() if filing else None,
            "filedWithin3Days": bool(filing and 0 <= (now.date() - filing).days <= 3),
            "technicalTerms": (event.get("technicalTermsShared") or [])[:3],
            "patentBusinessRelationshipProven": False,
        })
    for event in (row.get("sameIssuerBackgroundSources") or []):
        url = event.get("sourceUrl")
        match = DART.fullmatch(str(url))
        if not match:
            continue
        filing = parse_date(event.get("published")) or parse_date(match.group(1)[:8])
        out.append({
            "relation": "same_issuer_only_no_patent_relation",
            "type": event.get("sourceType"),
            "sourceUrl": url,
            "filingDate": filing.isoformat() if filing else None,
            "filedWithin3Days": bool(filing and 0 <= (now.date() - filing).days <= 3),
            "technicalTerms": [],
            "patentBusinessRelationshipProven": False,
        })
    distinct = {}
    for x in out:
        distinct.setdefault((x["sourceUrl"], x["type"], x["relation"]), x)
    return list(distinct.values())[:5]


def search_term(lead):
    title = str(lead.get("title") or "")
    abstract = str(lead.get("sourceAbstractExcerpt") or "")
    for term in TECH_TERMS:
        if term in title:
            return term
    for term in TECH_TERMS:
        if term in abstract:
            return term
    # A generic invention name is intentionally not a valid precise search.
    return None


def ntis_queries(lead):
    term = search_term(lead)
    owners = [x for x in (lead.get("coveredCompanies") or []) if isinstance(x, str) and x.strip()]
    partners = [x for x in (lead.get("outsideBeatCoApplicants") or [])
                if isinstance(x, str) and x.strip()]
    if not term:
        return []
    # Only a few queries to avoid presenting dozens of generic keyword hits.
    queries = []
    for name in (owners[:1] + partners[:1]):
        cleaned = re.sub(r"(주식회사|\(주\)|산학협력단)", "", name).strip()[:30]
        if len(cleaned) < 2:
            continue
        value = cleaned + " " + term
        queries.append({"query": value,
                        "url": NTIS_SEARCH + quote(value, safe=""),
                        "resultStatus": "not_queried_api_unconnected",
                        "participationConfirmed": False})
    return queries


def build(desk, cross, triage, now=None, limit=15):
    now = now or datetime.now(KST)
    if not 1 <= limit <= 30:
        raise ValueError("Dossier limit 1..30")
    if (desk.get("status") != "research_priorities_only"
        or not isinstance(desk.get("reviewQueue"), list)
        or not isinstance(cross.get("reviews"), list)
        or not isinstance(triage.get("reviewQueue"), list)
        or cross.get("deskSourceGeneratedAt") != desk.get("generatedAt")
        or triage.get("deskSourceGeneratedAt") != desk.get("generatedAt")
        or triage.get("crossSourceGeneratedAt") != cross.get("generatedAt")):
        raise ValueError("Official patent/cross/triage snapshot mismatch")

    leads = {x.get("publicationNumber"):x for x in desk["reviewQueue"]
             if isinstance(x, dict) and PUB.fullmatch(str(x.get("publicationNumber") or ""))}
    cross_rows = {x.get("publicationNumber"):x for x in cross["reviews"]
                  if isinstance(x, dict) and PUB.fullmatch(str(x.get("publicationNumber") or ""))}
    triage_rows = {x.get("publicationNumber"):x for x in triage["reviewQueue"]
                   if isinstance(x, dict) and PUB.fullmatch(str(x.get("publicationNumber") or ""))}
    if set(leads) != set(cross_rows) or set(leads) != set(triage_rows):
        raise ValueError("Current patent identities are missing from an evidence layer")

    dossiers = []
    for ranked in triage["reviewQueue"]:
        pub = str(ranked.get("publicationNumber") or "")
        if pub not in leads:
            continue
        lead, x, t = leads[pub], cross_rows[pub], triage_rows[pub]
        original = parse_date(lead.get("publicationDate"))
        days = (now.date() - original).days if original else None
        recent = bool(days is not None and 0 <= days <= 3)
        media_complete = bool(lead.get("mediaReview", {}).get("checked"))
        eligible = bool(media_complete and t.get("stage") not in BLOCKED_STAGES)
        dart_rows = dossier_sources(x, now)
        live_documents = [r for r in dart_rows if r["filedWithin3Days"]]
        safety = []
        if not recent: safety.append("old_patent_publication_not_new_event")
        if not media_complete: safety.append("media_lookup_incomplete")
        if t.get("stage") == "hold_for_review": safety.append("existing_coverage_or_editorial_hold")
        if not live_documents and dart_rows: safety.append("dart_evidence_is_historical_context")
        if not dart_rows: safety.append("no_dart_related_source_coverage")
        ntis = ntis_queries(lead)
        questions = [
            "동일 공개번호·청구항과 이전 특허의 우선권·패밀리/기술 차이를 확인했는가?",
            "국가과제 과제번호와 수행기관 법인명이 이 특허의 출원인과 일치하는가?",
            "공식 NTIS 수행과제 결과가 이 특허의 연구성과로 명시됐는가?",
            "DART에 실제 차종·공장·생산공정 적용 근거가 있으며 기업이 확인했는가?",
            "기보도, 회사 보도자료, 공개일과 관측일을 구분했는가?",
        ]
        dossiers.append({
            "publicationNumber":pub,
            "title":lead.get("title"),
            "companies":lead.get("coveredCompanies") or [],
            "outsideCoApplicants":lead.get("outsideBeatCoApplicants") or [],
            "publicationDate":original.isoformat() if original else None,
            "daysSincePublication":days,
            "recentPatentWithin3Days":recent,
            "claim1OfficiallyRetrieved":bool(lead.get("claim1Review", {}).get("verified")),
            "claim1Excerpt":(lead.get("claim1Review", {}).get("claim1Excerpt") or "")[:180],
            "olderSameTitleSearchState":(lead.get("olderSameTitle") or {}).get("state", "not_checked"),
            "patentNoveltyOrTechnicalSuperiorityProven":False,
            "pressLookupCompleted":media_complete,
            "pressRisk":(lead.get("mediaReview") or {}).get("state"),
            "candidateStage":t.get("stage"),
            "eligibleForResearchQueue":eligible,
            "dartDocuments":dart_rows,
            "dartRecentDocuments":len(live_documents),
            "ntisResearchQueries":ntis,
            "ntisProjectApiStatus":"not_connected",
            "ntisProjectConfirmed":False,
            "irisProjectResultStatus":"not_connected",
            "officialResearchProjectAwardConfirmed":False,
            "patentToProjectIdentityVerified":False,
            "commercialApplicationVerified":False,
            "industryImpactVerified":False,
            "exclusiveVerified":False,
            "publicationApproved":False,
            "cautions":safety,
            "questions":questions,
        })
        if len(dossiers) >= limit:
            break
    return {
        "generatedAt":now.isoformat(timespec="seconds"),
        "deskGeneratedAt":desk["generatedAt"],
        "crossGeneratedAt":cross["generatedAt"],
        "triageGeneratedAt":triage["generatedAt"],
        "status":"research_only",
        "totalCurrentCandidates":len(leads),
        "dossiersDisplayed":len(dossiers),
        "mediaCompleteInDisplayed":sum(x["pressLookupCompleted"] for x in dossiers),
        "freshPublicationsInDisplayed":sum(x["recentPatentWithin3Days"] for x in dossiers),
        "sourceStatus":{
            "kipris":"validated_existing_snapshot",
            "dart":"partial_official_reference_snapshot",
            "ntisProjectApi":"not_connected",
            "irisProjectAwardApi":"not_connected",
        },
        "sourceDirectories":{
            "ntisProjectApiApplication":NTIS_API_INFO,
            "irisPublicCalls":IRIS_CALLS,
            "ntisPublicProjectSearch":"https://www.ntis.go.kr/ThSearchProjectList.do",
        },
        "dossiers":dossiers,
        "confirmedExclusives":0,
        "verifiedPatentProjectMappings":0,
        "warning":"NTIS 조회 링크는 검색 실행/과제 선정 확인이 아님. IRIS 공고는 과제 선정 아님. 동일 법인 DART 및 기술어휘는 같은 프로젝트·사업화·단독 증거가 아님.",
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--desk", default="digests/patent_desk_latest.json")
    p.add_argument("--cross", default="digests/patent_cross_evidence_latest.json")
    p.add_argument("--triage", default="digests/patent_reporting_triage_latest.json")
    p.add_argument("--out", default="digests/patent_rnd_dossiers_latest.json")
    args = p.parse_args()
    def read(file):
        return json.loads(Path(file).read_text(encoding="utf-8"))
    result = build(read(args.desk), read(args.cross), read(args.triage))
    target=Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp=target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    tmp.replace(target)
    print("Patent R&D dossiers", result["dossiersDisplayed"],
          "confirmed project links", result["verifiedPatentProjectMappings"],
          "NTIS", result["sourceStatus"]["ntisProjectApi"])


if __name__ == "__main__":
    main()
