"""Candidate DART receipt ↔ observed '[단독]' title research links.

Only suggests reading a specific first-party filing. Same issuer + explicit
event vocabulary + plausible calendar order does NOT establish shared facts,
that the source preceded the actual publisher story, Y/P/N, or exclusivity.
No external network and no new legal interpretations.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, date
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

STATUS = "reverse_trace_dart_receipt_reading_queue_unverified"
RECEIPT = re.compile(r"20\d{12}\Z")
DATE = re.compile(r"20\d{2}-\d{2}-\d{2}\Z")
ID = re.compile(r"[0-9a-f]{24}\Z")
EVENTS = (
    ("company_split", re.compile(r"회사분할결정"), re.compile(r"분할")),
    ("share_cancellation", re.compile(r"주식소각결정"), re.compile(r"주식\s*소각|자사주\s*소각|자기주식\s*소각|소각\s*결정")),
    ("business_cessation", re.compile(r"영업정지"), re.compile(r"영업정지|영업\s*중단|사업\s*중단|사업\s*철수")),
    ("contract", re.compile(r"단일판매.{0,8}공급계약체결"), re.compile(r"수주|공급\s*계약|판매\s*계약|발주처")),
)
STAGES = {
    "official_receipt_only_original_not_checked",
    "official_table_filing_fields_checked",
    "official_share_cancellation_fields_checked",
    "official_business_cessation_fields_checked",
    "official_business_cessation_text_only_fields_unverified",
    "official_share_cancellation_text_only_fields_unverified",
}
MAX_ARTICLES = 1500
MAX_SOURCE_ROWS = 400
MAX_MATCHES = 250


def _aware(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.utcoffset() is not None else None
    except (TypeError, ValueError, OverflowError):
        return None


def _day(value):
    if not isinstance(value, str) or not DATE.fullmatch(value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def official_dart_url(value, receipt):
    if not isinstance(value, str) or not isinstance(receipt, str) or not RECEIPT.fullmatch(receipt):
        return False
    try:
        u = urlsplit(value)
        return (u.scheme == "https" and u.hostname == "dart.fss.or.kr"
                and u.port is None and u.username is None and u.password is None
                and u.path == "/dsaf001/main.do"
                and parse_qs(u.query) == {"rcpNo": [receipt]}
                and not u.fragment)
    except ValueError:
        return False


def _issuer_present(article, issuer):
    companies = article.get("companies")
    return isinstance(companies, list) and issuer in companies


def build_queue(trace, official, beat, *, max_results=MAX_MATCHES):
    if (not isinstance(trace, dict)
        or trace.get("status") != "automotive_industry_exclusive_reverse_trace_unverified_candidates"
        or not isinstance(trace.get("items"), list)
        or trace.get("totalObservedExclusiveHeadlines") != len(trace["items"])
        or _aware(trace.get("generatedAt")) is None
        or len(trace["items"]) > MAX_ARTICLES
        or trace.get("confirmedScoops") != 0
        or not isinstance(official, dict)
        or official.get("status") != "official_date_triage"
        or official.get("confirmedScoops") != 0
        or not isinstance(official.get("backgroundReference"), list)
        or not isinstance(official.get("freshOfficialReview"), list)
        or not isinstance(beat, dict)
        or beat.get("status") != "industry_beat_official_receipt_review"
        or not isinstance(max_results, int) or not 1 <= max_results <= MAX_MATCHES):
        raise ValueError("reverse_trace_or_dart_source_not_verified")
    stamp = beat.get("generatedAt")
    if (_aware(stamp) is None or official.get("beatWideDartSourceAt") != stamp
        or _aware(official.get("generatedAt")) is None):
        raise ValueError("official_dart_snapshot_identity_mismatch")
    source_rows = official["backgroundReference"] + official["freshOfficialReview"]
    if len(source_rows) > MAX_SOURCE_ROWS:
        raise ValueError("official_dart_source_row_limit_exceeded")
    filings = {}
    for row in source_rows:
        if not isinstance(row, dict):
            raise ValueError("invalid_official_source_row")
        if row.get("source") != "DART_FILING":
            continue
        no = row.get("officialReceiptNo")
        day = _day(row.get("officialDate"))
        if (not isinstance(no, str) or not RECEIPT.fullmatch(no)
            or day is None or no[:8] != day.strftime("%Y%m%d")
            or not official_dart_url(row.get("sourceUrl"), no)
            or not isinstance(row.get("company"), str)
            or not isinstance(row.get("headline"), str)
            or row.get("sourceSnapshotAt") != stamp
            or row.get("originalEvidenceStage") not in STAGES
            or row.get("exclusiveConfirmed") is not False
            or row.get("approvedForPitch") is not False
            or row.get("priorMediaCoverageVerified") is not False):
            # An older/stale or malformed source must not be reused as proof.
            continue
        if no in filings:
            if filings[no] != row:
                raise ValueError("contradictory_same_receipt_official_rows")
        filings[no] = row
    matches = []
    for item in trace["items"]:
        if (not isinstance(item, dict)
            or not isinstance(item.get("articleId"), str)
            or not ID.fullmatch(item["articleId"])
            or item.get("publicTraceClass") != "U"
            or not isinstance(item.get("title"), str)):
            continue
        article_at = _aware(item.get("published"))
        if article_at is None:
            continue
        for row in filings.values():
            if not _issuer_present(item, row["company"]):
                continue
            gap = (article_at.date() - _day(row["officialDate"])).days
            if not 0 <= gap <= 45:
                continue
            kind = next((label for label, filing_term, story_term in EVENTS
                         if filing_term.search(row["headline"])
                         and story_term.search(item["title"])), None)
            if kind is None:
                continue
            stage = row["originalEvidenceStage"]
            matches.append({
                "articleId": item["articleId"],
                "observedArticleTitle": item["title"],
                "issuer": row["company"],
                "eventType": kind,
                "officialReceiptNo": row["officialReceiptNo"],
                "officialFilingDay": row["officialDate"],
                "newsRssObservedAt": item["published"],
                "calendarDaysBetweenDates": gap,
                "officialUrl": row["sourceUrl"],
                "originalEvidenceStage": stage,
                "officialOriginalBodyVerifiedForMatchedFact": False,
                "articlePublisherOriginalFulltextRead": False,
                "publisherFirstPublishedAtVerified": False,
                "publicSourceAvailableBeforePublisherVerified": False,
                "publicFactOverlapVerified": False,
                "domesticPriorCoverageVerified": False,
                "identicalUnderlyingCorporateEventVerified": False,
                "automaticYPNDecision": False,
                "exclusiveConfirmed": False,
                "approvedForPitch": False,
                "researchAction": (
                    "공시 원문 접수번호를 열어 분할·주식소각·영업정지·계약의 사실범위와 "
                    "기사 본문을 대조하고 각각의 최초 공개시각·국내 선행보도를 확인"
                ),
            })
    matches.sort(key=lambda x:(x["newsRssObservedAt"],x["articleId"],x["officialReceiptNo"]), reverse=True)
    if len(matches) > max_results:
        # Explicit truncation is not treated as no other evidence.
        dropped = len(matches) - max_results
        matches = matches[:max_results]
    else:
        dropped = 0
    return {
        "status": STATUS,
        "generatedAt": trace.get("generatedAt"),
        "reverseTraceSourceAt": trace.get("generatedAt"),
        "officialQueueSourceAt": official["generatedAt"],
        "dartOfficialSourceAt": stamp,
        "candidatePairCount": len(matches),
        "distinctObservedArticles": len({m["articleId"] for m in matches}),
        "distinctOfficialReceipts": len({m["officialReceiptNo"] for m in matches}),
        "truncatedCandidatePairs": dropped,
        "incompleteOfficialFeeds": official.get("incompleteOrStaleFeeds", []),
        "sourceCompletenessVerified": False,
        "humanValidatedYPN": 0,
        "sameFactEstablished": False,
        "confirmedScoops": 0,
        "approvedArticles": 0,
        "warning": ("같은 법인명·공시 유형 단어·날짜가 연결된 원문 검토 후보일 뿐. "
                    "기사 핵심 사실이 공시에서 사전 공개됐다고 확인한 것이 아니며 "
                    "미보도 증거·단독·Y/P/N 판정이 아님. 원문 미확인과 실제 0건을 구분"),
        "items": matches,
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--trace",default="digests/reverse_trace_latest.json")
    parser.add_argument("--official",default="digests/official_event_triage_latest.json")
    parser.add_argument("--dart",default="digests/dart_beat_monitor_latest.json")
    parser.add_argument("--output",default="digests/reverse_trace_dart_followups_latest.json")
    args=parser.parse_args()
    source=lambda path:json.loads(Path(path).read_text(encoding="utf-8"))
    doc=build_queue(source(args.trace),source(args.official),source(args.dart))
    out=Path(args.output)
    out.parent.mkdir(parents=True,exist_ok=True)
    tmp=out.with_suffix(out.suffix+".tmp")
    tmp.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    tmp.replace(out)
    print("DART receipt comparison candidates:",doc["candidatePairCount"],
          "human verified",doc["humanValidatedYPN"],"scoops",doc["confirmedScoops"])


if __name__=="__main__":
    main()
