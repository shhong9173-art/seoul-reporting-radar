"""공식 DART digest 증거 검토. 자동 단독 판정 금지.

DART 공시 목록, 같은 접수번호의 원문 수치/발행인 정정표, 선택적인
네이버 뉴스 검색 결과를 함께 보여준다. 서로 다른 계약을 같은
회사·보고서명만으로 연결해 변경분이라고 주장하지 않는다.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse
from typing import Callable

KST = timezone(timedelta(hours=9))
RECEIPT = re.compile(r"\d{14}\Z")
ROUTINE_PHRASES = (
    "임원ㆍ주요주주특정증권등소유상황보고서",
    "임원·주요주주특정증권등소유상황보고서",
    "주식등의대량보유상황보고서",
    "자기주식취득",
    "자기주식처분",
    "분기보고서",
    "반기보고서",
    "사업보고서",
)
EVENT_TERMS = (
    ("생산중단", "생산중단"),
    ("생산재개", "생산재개"),
    ("단일판매", "공급계약"),
    ("공급계약", "공급계약"),
    ("신규시설투자", "신규시설투자"),
    ("타법인주식", "지분 인수"),
    ("회사합병", "합병"),
    ("회사분할", "분할"),
    ("영업양수", "영업양수"),
    ("영업양도", "영업양도"),
    ("유상증자", "유상증자"),
    ("최대주주변경", "최대주주변경"),
    ("소송", "소송"),
)


def event_term(report: str) -> str:
    normalized = re.sub(r"\s+", "", report)
    for token, term in EVENT_TERMS:
        if token in normalized:
            return term
    return ""


def is_routine(report: str) -> bool:
    normalized = re.sub(r"\s+", "", report)
    return any(re.sub(r"\s+", "", term) in normalized for term in ROUTINE_PHRASES)


def valid_receipt(value) -> bool:
    return isinstance(value, str) and RECEIPT.fullmatch(value) is not None


def normalize_news(items):
    """Search results are leads, never proof of the same event."""
    clean = []
    if not isinstance(items, list):
        raise ValueError("뉴스 검색 응답은 목록이어야 합니다")
    for raw in items[:12]:
        if not isinstance(raw, dict):
            continue
        link = raw.get("originallink") or raw.get("link") or raw.get("url") or ""
        parsed = urlparse(str(link))
        if parsed.scheme not in ("https", "http") or not parsed.netloc:
            continue
        title = re.sub(r"<[^>]+>", "", str(raw.get("title", "")))
        title = html.unescape(title).strip()
        if title:
            clean.append({"title": title[:250], "url": str(link), "published": str(raw.get("pubDate", ""))[:90]})
        if len(clean) >= 3:
            break
    return clean


def naver_search(company: str, term: str):
    """Read-only verification candidates. Missing key means 'not checked'."""
    import requests
    cid = os.environ.get("NAVER_CLIENT_ID", "").strip()
    secret = os.environ.get("NAVER_CLIENT_SECRET", "").strip()
    if not cid or not secret:
        return {"status": "미실행: 네이버 API 키 없음", "results": []}
    try:
        resp = requests.get(
            "https://openapi.naver.com/v1/search/news.json",
            params={"query": f"{company} {term}", "display": 20, "sort": "date"},
            headers={"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": secret},
            timeout=12,
        )
        resp.raise_for_status()
        matches = normalize_news(resp.json().get("items", []))
        return {
            "status": ("관련 기사 검색 결과 있음: 동일 사건 여부 미검증" if matches
                       else "검색 결과 없음: 미보도 확정 불가"),
            "results": matches,
        }
    except (ValueError, requests.RequestException) as exc:
        return {"status": f"조회 오류: {type(exc).__name__}", "results": []}


def google_news_search(company: str, term: str):
    """Fallback when NAVER credentials are absent; not an exhaustive search."""
    import urllib.error
    import urllib.parse
    import urllib.request
    import xml.etree.ElementTree as ET
    query = urllib.parse.quote(f"{company} {term} when:30d")
    url = ("https://news.google.com/rss/search?q=" + query +
           "&hl=ko&gl=KR&ceid=KR:ko")
    request = urllib.request.Request(url, headers={"User-Agent": "reporter-radar/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            payload = response.read(1024 * 1024)
        root = ET.fromstring(payload)
        if root.tag != "rss" or root.find("channel") is None:
            raise ValueError("Google News RSS 형식 불일치")
        matches = normalize_news([
            {"title": (item.findtext("title") or ""),
             "link": (item.findtext("link") or ""),
             "pubDate": (item.findtext("pubDate") or "")}
            for item in root.findall("./channel/item")[:12]
        ])
        return {"status": ("Google News 최근 30일 관련 기사 후보: 동일 사건 미검증" if matches
                           else "Google News 최근 30일 검색상 미발견: 미보도 확정 불가"),
                "results": matches}
    except (ValueError, urllib.error.URLError, TimeoutError, ET.ParseError) as exc:
        return {"status": f"Google News 검색 실패: {type(exc).__name__}", "results": []}


def _correction_evidence(matching_numeric):
    changes = []
    for group in matching_numeric.get("correctionComparisons", []):
        if not isinstance(group, dict) or group.get("basis") != "issuer_correction_table":
            continue
        source = group.get("sourceUrl")
        verified_original = bool(group.get("originalDocumentVerified"))
        for change in group.get("changes", [])[:15]:
            if not isinstance(change, dict):
                continue
            field, before, after = (change.get("field"), change.get("before"), change.get("after"))
            if all(isinstance(v, str) and v.strip() for v in (field, before, after)):
                changes.append({
                    "field": field.strip()[:160],
                    "before": before.strip()[:1200],
                    "after": after.strip()[:1200],
                    "category": change.get("category", ""),
                    "sourceUrl": source,
                    "basis": "발행인 정정표 기재",
                    "originalDocumentVerified": verified_original,
                })
    return changes[:15]


def review_item(row, numeric_by_receipt, search=None):
    if not isinstance(row, dict):
        raise ValueError("잘못된 digest 항목")
    receipt = row.get("receiptNo")
    if not valid_receipt(receipt):
        raise ValueError("공시 접수번호 형식 오류")
    company, report = row.get("company"), row.get("report")
    if not (isinstance(company, str) and company.strip() and isinstance(report, str) and report.strip()):
        raise ValueError("기업명·보고서명이 없는 공시")
    source_url = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt}"
    raw_doc = numeric_by_receipt.get(receipt, {})
    # A receipt-number match alone is not enough if issuer names disagree.
    doc = raw_doc if raw_doc.get("corpName") == company else {}
    changes = _correction_evidence(doc)
    facts = []
    for fact in doc.get("numericFacts", [])[:6]:
        if not isinstance(fact, dict):
            continue
        if fact.get("label") and fact.get("formatted"):
            facts.append({
                "label": str(fact["label"])[:200], "value": str(fact["formatted"])[:120],
                "context": str(fact.get("context", ""))[:400],
                "interpretation": str(fact.get("interpretation", ""))[:280],
            })
    routine = is_routine(report)
    relevant_term = event_term(report)
    if routine:
        lane = "정례 공개·후순위"
        reason = "보고서 유형만으로 실제 지분 변화·경영 영향이 확인되지 않음"
    elif changes:
        lane = "정정표 변경 검토"
        reason = "발행인 정정표의 전후 문구가 확인됨. 최초 원공시와 독립 대조한 사실은 아님"
    elif row.get("tag") and relevant_term:
        lane = "원문·변경 사실 확인"
        reason = "공시 유형을 포착했지만 실제 사업 변화·대상 물량은 확인 전"
    else:
        lane = "공개자료 추적"
        reason = "변경 전후의 직접 근거 또는 실질적인 기사 야마가 아직 없음"
    if routine:
        questions = ["신고 대상·보유 전후 수량·비율을 원문에서 비교", "경영권 등 실질적 영향 존재 여부 확인"]
    elif changes:
        questions = ["정정 공시 표의 변경사항을 최초 공시 원문과 독립 대조", "수정된 일정·계약 조건이 실제 사업에 미치는 영향 회사에 확인"]
    else:
        questions = ["원공시 전문에서 대상 사업·금액·기간·상대방 확인", "기존 발표 대비 새 변화와 기업의 실제 대응 확인"]
    # Search return values never make an 'already covered' or 'exclusive' decision.
    coverage = {"status": "미실행: 보도 검색 전", "results": []}
    if not routine and relevant_term and search:
        response = search(company, relevant_term)
        if isinstance(response, dict):
            coverage = {"status": str(response.get("status", "조회 상태 불명"))[:200],
                        "results": normalize_news(response.get("results", []))}
    return {
        "receiptNo": receipt, "company": company, "group": row.get("group", ""),
        "report": report, "published": row.get("published", ""),
        "url": source_url, "isNew": bool(row.get("isNew")), "tag": row.get("tag", ""),
        "lane": lane, "reason": reason,
        "evidenceStatus": ("발행인 정정표 확인(원공시 대조 미완료)" if changes else
                           "동일 접수번호 원문 수치 일부 확인" if facts else
                           "공시 목록 확인, 상세 근거 미검증"),
        "changeStatus": ("발행인 정정표 문구 변화 확인" if changes else "동일 사건 전후 변화 미확인"),
        "changes": changes, "numericFacts": facts,
        "coverage": coverage,
        "companyResponse": "미확인",
        "exclusiveStatus": "판정 보류: 자동 단독 확정 금지",
        "questions": questions,
        "originalDocumentVerified": bool(changes) and all(v["originalDocumentVerified"] for v in changes),
    }


def build_review(digest, numeric, *, search: Callable | None = None):
    if not isinstance(digest, dict) or not isinstance(digest.get("items"), list):
        raise ValueError("원본 공시 digest 데이터가 유효하지 않음")
    if not isinstance(numeric, dict) or not isinstance(numeric.get("items"), list):
        raise ValueError("원문 수치 분석 결과가 유효하지 않음")
    doc_index = {}
    for doc in numeric["items"]:
        if isinstance(doc, dict) and valid_receipt(doc.get("receiptNo")):
            doc_index[doc["receiptNo"]] = doc
    seen = set()
    results = []
    for row in digest["items"]:
        if not isinstance(row, dict) or not valid_receipt(row.get("receiptNo")):
            raise ValueError("공시 목록에 잘못된 접수번호가 있음")
        if row["receiptNo"] in seen:
            continue
        seen.add(row["receiptNo"])
        results.append(review_item(row, doc_index, search=search))
    rank = {"정정표 변경 검토": 0, "원문·변경 사실 확인": 1,
            "공개자료 추적": 2, "정례 공개·후순위": 3}
    results.sort(key=lambda r: (rank[r["lane"]], not r["isNew"], r["receiptNo"]), reverse=False)
    lanes = {name: sum(x["lane"] == name for x in results) for name in rank}
    return {
        "generatedAt": datetime.now(KST).isoformat(timespec="seconds"),
        "digestGeneratedAt": digest.get("generatedAt"),
        "numericGeneratedAt": numeric.get("generatedAt"),
        "assessment": "공개 원자료·수치·정정표·관련 기사 검색, 자동 단독 확정 불가",
        "counts": lanes, "total": len(results),
        "missingCompanies": digest.get("missingCompanies", []),
        "items": results,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--digest", default="digests/latest.json")
    parser.add_argument("--numeric", default="dart_numeric.json")
    parser.add_argument("--output", default="digests/review_latest.json")
    parser.add_argument("--no-news", action="store_true", help="외부 보도 검색 없이 로컬 원자료만 분석")
    args = parser.parse_args()
    digest = json.loads(Path(args.digest).read_text(encoding="utf-8"))
    numeric = json.loads(Path(args.numeric).read_text(encoding="utf-8"))
    has_keys = bool(os.environ.get("NAVER_CLIENT_ID") and os.environ.get("NAVER_CLIENT_SECRET"))
    search = (naver_search if has_keys else google_news_search) if not args.no_news else None
    if not search:
        print("기존 기사 실검색 미실행: --no-news")
    review = build_review(digest, numeric, search=search)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("원자료 검토:", review["total"], "건 |", review["counts"],
          "| 자동 단독 확정 0건(설계상 금지)")


if __name__ == "__main__":
    main()
