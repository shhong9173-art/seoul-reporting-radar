"""Build the small views that the Claude connector tools read (tools/*.json).

This is the data layer behind the 매의눈-style tools (단서·통계·단독 흐름·
상태·큰 그림). It only restates what the radar's published JSON already says:

* it never upgrades a lead (공개 원자료 추적 → 취재 단서 → 단독 후보 stays as
  the source labelled it, and nothing here can make a 단독 후보);
* a news-index search with no hit is "색인 0건 — 미보도 증거 아님", never
  "미보도";
* collection date is kept apart from the official publication date;
* source failures stay visible in health.json instead of becoming 0건.

Private reporter state (packages, kill/keep feedback) is NOT written here: this
repository and GitHub Pages are public. That state lives behind the connector's
access token.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scoop_scout  # noqa: E402  (exact-name company boundaries)

KST = timezone(timedelta(hours=9))
SCHEMA = 1
TEAM_ORDER = ["자동차", "철강·비철", "전력·에너지", "화학·소재", "해외", "조달", "특허", "그 외"]

# Reporter-confirmed direct beats (2026-10-26, 41 companies) grouped the way
# the reporter lists them. Only these names can put a clue on a beat team.
BEAT_TEAMS = {
    "자동차": ("현대차", "기아", "현대모비스", "현대위아", "HL만도", "한국GM", "KG모빌리티",
             "르노코리아", "메르세데스벤츠코리아", "BMW코리아", "폭스바겐코리아", "아우디코리아",
             "혼다코리아", "한국타이어", "넥센타이어", "금호타이어"),
    "철강·비철": ("포스코홀딩스", "포스코", "현대제철", "KG스틸", "세아홀딩스", "세아제강",
              "동국제강", "동국씨엠", "고려아연", "영풍"),
    "전력·에너지": ("HD현대일렉트릭", "LS일렉트릭", "대한전선", "LS전선", "LS MnM", "LS지주",
               "두산에너빌리티", "GS", "GS칼텍스"),
    "화학·소재": ("한화솔루션", "OCI", "OCI홀딩스", "태광", "동성케미칼", "DL케미칼"),
}
BEAT_TO_TEAM = {name: team for team, names in BEAT_TEAMS.items() for name in names}
# Exact legal/registry spellings seen in DART company fields (whole-field match only).
REGISTRY_NAMES = {
    "현대자동차": "현대차", "기아자동차": "기아", "한국타이어앤테크놀로지": "한국타이어",
    "엘에스일렉트릭": "LS일렉트릭", "LS ELECTRIC": "LS일렉트릭", "엘에스전선": "LS전선",
    "엘에스엠앤엠": "LS MnM", "LS M&M": "LS MnM", "케이지스틸": "KG스틸", "케이지모빌리티": "KG모빌리티",
    "한국지엠": "한국GM", "오씨아이": "OCI", "에이치디현대일렉트릭": "HD현대일렉트릭",
    "디엘케미칼": "DL케미칼", "LS": "LS지주", "엘에스": "LS지주", "에이치엘만도": "HL만도",
    "만도": "HL만도", "메르세데스-벤츠 코리아": "메르세데스벤츠코리아",
}

STOP = set("""
공시 결정 공고 보고서 주식회사 관련 대한 위한 따른 통해 및 등 의 에 를 을 이 가 는 은 와 과 로 으로 에서
기업 회사 업계 국내 해외 올해 지난해 전년 최근 계획 추진 사업 단일판매 공급계약체결 공급계약 기재정정
첨부정정 자율공시 정기 주요공시 주요사항보고서 보고 안내 알림 공지 게시 입찰 공고일 접수기간 처분신청
국내 미국 동일 대조 필요 확인 미확인 여부 공식 숫자 단위 동일기간 장치 방법 시스템 이를 갖춘 포함하는
이용한 차량 제어 공정공시 잠정 연결재무제표기준영업 단독 기자 뉴스
the and for with from of to in on
""".split())
TOKEN = re.compile(r"[가-힣A-Za-z0-9][가-힣A-Za-z0-9&.\-]+")


def now_kst():
    return datetime.now(KST)


def load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def stamp(data):
    if isinstance(data, dict):
        value = data.get("generatedAt") or data.get("generated_at")
        return value if isinstance(value, str) else None
    return None


def parse_dt(value):
    """Return an aware datetime for ISO strings or YYYYMMDD, else None."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    try:
        if re.fullmatch(r"\d{8}", text):
            return datetime(int(text[:4]), int(text[4:6]), int(text[6:]), tzinfo=KST)
        if re.fullmatch(r"\d{2}/\d{2}/\d{4}", text):  # NHTSA dd/mm/yyyy
            d, m, y = text.split("/")
            return datetime(int(y), int(m), int(d), tzinfo=KST)
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=KST)
    except ValueError:
        return None


def day(value):
    parsed = parse_dt(value)
    return parsed.astimezone(KST).strftime("%Y-%m-%d") if parsed else None


def https_url(value):
    if isinstance(value, str) and re.match(r"https://[^\s/]+\.[^\s]+", value):
        return value
    return None


def beat_name(raw):
    name = str(raw or "").strip()
    if not name:
        return None
    name = REGISTRY_NAMES.get(name, name)
    name = scoop_scout.DIRECT_BEAT_CANONICAL.get(name, name)
    return name if name in BEAT_TO_TEAM else None


def beats_in(text, *explicit):
    found = []
    for raw in explicit:
        for value in (raw if isinstance(raw, (list, tuple)) else [raw]):
            name = beat_name(value)
            if name and name not in found:
                found.append(name)
    for hit in scoop_scout.strict_company_hits(text or ""):
        name = beat_name(hit)
        if name and name not in found:
            found.append(name)
    return found


def team_for(companies, kind=None):
    if kind in ("해외", "조달", "특허"):
        return kind
    for name in companies:
        team = BEAT_TO_TEAM.get(name)
        if team:
            return team
    return "그 외"


def clue_id(*parts):
    raw = "|".join(str(p or "") for p in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def clue(*, kind, source, title, url, published, companies, tier, signal="", note="",
         receipt=None, key=None, team=None):
    title = re.sub(r"\s+", " ", str(title or "")).strip()[:240]
    return {
        "id": clue_id(source, receipt or key or url or title),
        "team": team or team_for(companies, kind),
        "published": day(published),
        "source": source,
        "kind": kind,
        "title": title,
        "url": https_url(url),
        "receiptNo": receipt,
        "companies": companies,
        "signal": signal,
        "tier": tier,
        "routine": bool(ROUTINE_RE.search(title)),
        "note": str(note or "")[:300],
    }


# Procedural filings: kept for completeness but sorted last and hidden by default.
ROUTINE_RE = re.compile(r"기업설명회|IR\)?개최|주주명부폐쇄|주주총회소집|매매거래정지|결산실적공시예고|"
                        r"증권발행실적보고서|투자설명서|일괄신고추가서류|기업지배구조보고서|"
                        r"주식등의대량보유상황보고서\(약식\)|자기주식취득결과보고서")

TIER_PUBLIC = "공개 원자료 추적"
TIER_LEAD = "취재 단서·단독 미확정"
TIER_CANDIDATE = "단독 후보"


# ---------------------------------------------------------------- adapters
def from_pre_scoop(data):
    out = []
    for x in (data or {}).get("items", []) or []:
        if not isinstance(x, dict):
            continue
        text = " ".join(str(x.get(k) or "") for k in ("title", "summary"))
        companies = beats_in(text, x.get("companies") or [])
        group = str(x.get("sourceGroup") or "")
        kind = "조달" if "조달" in group else None
        url = x.get("url")
        note = x.get("dateSource") or ""
        if not https_url(url):
            note = (note + " · 원문 링크 없음(목록 화면에서 확인)").strip(" ·")
        out.append(clue(kind=kind, source=x.get("officialLabel") or x.get("sourceName") or "공식 원자료",
                        title=x.get("title"), url=url, published=x.get("published"),
                        companies=companies, tier=TIER_PUBLIC,
                        signal=x.get("signalType") or x.get("category") or group, note=note))
    return out


def from_triage(data):
    out = []
    for bucket in ("freshOfficialReview", "backgroundReference"):
        for x in (data or {}).get(bucket, []) or []:
            if not isinstance(x, dict):
                continue
            receipt = x.get("officialReceiptNo")
            companies = beats_in(x.get("headline"), x.get("company"))
            out.append(clue(kind=None, source=str(x.get("source") or "공식").replace("_FILING", ""),
                            title=x.get("headline"), url=x.get("sourceUrl"),
                            published=x.get("officialDate"), companies=companies,
                            tier=TIER_PUBLIC, signal=x.get("evidenceClass") or bucket,
                            note=x.get("officialFact"), receipt=receipt))
    return out


def from_dart_beat(data):
    out = []
    for x in (data or {}).get("records", []) or []:
        if not isinstance(x, dict) or not x.get("receiptNo"):
            continue
        report = re.sub(r"\s+", " ", str(x.get("report") or "")).strip()
        companies = beats_in(report, x.get("company"))
        out.append(clue(kind=None, source="DART", title=f"{x.get('company')} · {report}",
                        url=x.get("sourceUrl"), published=x.get("published"), companies=companies,
                        tier=TIER_PUBLIC, signal=x.get("category") or "", receipt=x.get("receiptNo"),
                        note="정정공시" if x.get("isCorrection") else ""))
    return out


def from_morning(data):
    out = []
    for x in (data or {}).get("items", []) or []:
        if not isinstance(x, dict) or not x.get("receiptNo"):
            continue
        report = re.sub(r"\s+", " ", str(x.get("report") or "")).strip()
        companies = beats_in(report, x.get("company"))
        out.append(clue(kind=None, source="DART", title=f"{x.get('company')} · {report}",
                        url=x.get("url"), published=x.get("published"), companies=companies,
                        tier=TIER_PUBLIC, signal=x.get("tag") or "", receipt=x.get("receiptNo")))
    return out


def from_industry_hunt(data):
    out = []
    for x in (data or {}).get("leads", []) or []:
        if not isinstance(x, dict):
            continue
        source = str(x.get("source") or "")
        kind = "해외" if source in ("NHTSA", "OVERSEAS") else None
        companies = beats_in(" ".join(str(x.get(k) or "") for k in ("headline", "fact")))
        receipt = None
        match = re.search(r"rcpNo=(\d{14})", str(x.get("url") or ""))
        if match:
            receipt = match.group(1)
        out.append(clue(kind=kind, source=source or "공식", title=f"{x.get('headline')} — {x.get('fact')}",
                        url=x.get("url"), published=None, companies=companies, tier=TIER_LEAD,
                        signal="industry_official_hunt", note=x.get("verification"),
                        receipt=receipt, key=f"{source}|{x.get('headline')}|{x.get('fact')}"))
    return out


def from_nhtsa(data):
    out = []
    for x in (data or {}).get("records", []) or []:
        if not isinstance(x, dict) or not x.get("id"):
            continue
        make = str(x.get("make") or "")
        companies = beats_in(make, "기아" if make.lower() == "kia" else "현대차" if make.lower() in ("hyundai", "genesis") else None)
        out.append(clue(kind="해외", source="NHTSA", title=f"미국 {x.get('kind')} {x.get('id')} · {make} {x.get('model')} {x.get('year')}",
                        url=x.get("officialApi"), published=x.get("reportDate"), companies=companies,
                        tier=TIER_PUBLIC, signal=str(x.get("kind") or ""), key=x.get("id"),
                        note="미국 공개 자료(국내 동일 결함 증거 아님)"))
    return out


def from_crossborder(data):
    out = []
    for x in (data or {}).get("items", []) or []:
        if not isinstance(x, dict):
            continue
        group = str(x.get("companyGroup") or "")
        companies = beats_in(group + " " + str(x.get("headline") or ""))
        url = None
        for ev in x.get("sourceEvidence") or []:
            if isinstance(ev, dict) and https_url(ev.get("url")):
                url = ev["url"]
                break
        title = str(x.get("headline") or "")
        models = []
        for m in (x.get("officialFact") or {}).get("usModelYears") or []:
            name = re.sub(r"\s+", " ", str((m or {}).get("model") or "")).strip().upper() if isinstance(m, dict) else ""
            if name and name not in models:
                models.append(name)
        if models:
            # 미국 리콜 단서 제목에 차종을 붙인다 — 캠페인 번호만으로는 보도 대조가 '{회사} 미국 리콜'이 된다(10-31 운영:
            # 26V692000 아반떼·투싼 하이브리드 스트럿 ↔ 투싼 에어백 남아공 기사)
            title = re.sub(r"^(미국 리콜 \S+)", lambda mm: f"{mm.group(1)} · {'·'.join(models[:3])}{' 외' if len(models) > 3 else ''}", title, count=1)
        out.append(clue(kind="해외", source="해외 원자료", title=title, url=url,
                        published=x.get("officialPublicationDate"), companies=companies,
                        tier=TIER_LEAD, signal=x.get("type") or "", key=x.get("id"),
                        note=x.get("reporterPriority") or ""))
    return out


def from_patents(data):
    out = []
    for x in (data or {}).get("shortlist", []) or []:
        if not isinstance(x, dict) or not x.get("publicationNumber"):
            continue
        companies = beats_in(x.get("title"), x.get("coveredCompanies") or [])
        number = str(x["publicationNumber"])
        out.append(clue(kind="특허", source="KIPRIS 공개특허", title=f"{x.get('title')} ({', '.join(x.get('coveredCompanies') or [])})",
                        url=f"https://doi.org/10.8080/{number}" if re.fullmatch(r"\d{13}", number) else None,
                        published=x.get("publicationDate"), companies=companies, tier=TIER_LEAD,
                        signal=x.get("topic") or "", key=number,
                        note="특허 공개만으로 사업화·단독 판단 금지"))
    return out


def from_g2b(data):
    out = []
    for x in (data or {}).get("notices", []) or []:
        if not isinstance(x, dict) or not x.get("noticeId"):
            continue
        companies = beats_in(x.get("title"))
        out.append(clue(kind="조달", source="나라장터", title=f"{x.get('title')} ({x.get('demandAgency') or x.get('issuingAgency') or ''})",
                        url=x.get("sourceUrl"), published=x.get("issueDate"), companies=companies,
                        tier=TIER_PUBLIC, signal=",".join(x.get("technologyTopics") or []),
                        key=f"{x.get('noticeId')}-{x.get('revision')}",
                        note="입찰 공고(낙찰·계약 아님)"))
    return out


def from_scoop(data):
    out = []
    data = data or {}
    for bucket, tier in (("items", TIER_CANDIDATE), ("leadSignals", TIER_LEAD), ("publicSignals", TIER_PUBLIC)):
        for x in data.get(bucket, []) or []:
            if not isinstance(x, dict):
                continue
            companies = beats_in(x.get("title"), x.get("companies") or [])
            receipt = None
            match = re.search(r"rcpNo=(\d{14})", str(x.get("url") or ""))
            if match:
                receipt = match.group(1)
            title = x.get("title")
            details = [re.sub(r"\s+", " ", str(d)).strip() for d in x.get("details") or [] if str(d).strip()]
            if details and x.get("kind") == "공개 리콜 공지":
                # 묶음 제목('기아, 10월 30일 리콜 공지 1건')만으로는 차종·부품을 모른다 — 첫 공지 줄을 붙인다
                # (10-31 운영: 쏘렌토 저압연료라인 리콜이 '기아 리콜'로 찾아져 ICCU 리콜 기사가 근거로 붙었다)
                title = f"{title} — {details[0]}" + (f" 외 {len(details) - 1}건" if len(details) > 1 else "")
            out.append(clue(kind=None, source=x.get("sourceName") or "레이더", title=title,
                            url=x.get("url"), published=x.get("published"), companies=companies,
                            tier=tier, signal=x.get("signalGroup") or x.get("kind") or bucket,
                            note=x.get("verification") or x.get("coverageStatus") or "", receipt=receipt,
                            key=x.get("id")))
    for x in data.get("heldDartResearch", []) or []:
        if not isinstance(x, dict):
            continue
        companies = beats_in(x.get("reportName"), x.get("company"))
        out.append(clue(kind=None, source="DART", title=f"{x.get('company')} · {x.get('reportName')}",
                        url=x.get("sourceUrl"), published=x.get("published"), companies=companies,
                        tier=TIER_PUBLIC, signal="held_dart_research",
                        note=f"보류: {x.get('officialFact') or x.get('holdReason')}", receipt=x.get("receiptNo")))
    return out


def from_contracts(data):
    out = []
    for x in (data or {}).get("items", []) or []:
        if not isinstance(x, dict) or not x.get("receiptNo"):
            continue
        report = re.sub(r"\s+", " ", str(x.get("report") or "")).strip()
        companies = beats_in(report, x.get("company"))
        changes = (x.get("issuerCorrectionTable") or {}).get("changes") or []
        note = ""
        if changes:
            first = changes[0]
            note = f"정정표: {first.get('fieldLabel')} {first.get('before')} → {first.get('after')} (발행인 기재, 원공시 독립 대조 전)"
        out.append(clue(kind=None, source="DART", title=f"{x.get('company')} · {report}", url=x.get("sourceUrl"),
                        published=x.get("published"), companies=companies, tier=TIER_PUBLIC,
                        signal=x.get("category") or "", receipt=x.get("receiptNo"), note=note))
    return out


def from_federal_register(data):
    out = []
    for x in (data or {}).get("items", []) or []:
        if not isinstance(x, dict) or not x.get("title"):
            continue
        companies = beats_in("", x.get("companiesMentioned") or [])
        out.append(clue(kind="해외", source="미 연방관보", title=x.get("title"), url=x.get("sourceUrl"),
                        published=x.get("published"), companies=companies, tier=TIER_PUBLIC,
                        signal=x.get("status") or "", key=x.get("sourceId"),
                        note="본문에 기업명 확인" if companies else ""))
    return out


def from_overseas(data):
    out = []
    for x in (data or {}).get("documents", []) or []:
        if not isinstance(x, dict) or not x.get("title"):
            continue
        companies = beats_in("", x.get("companiesMentioned") or [])
        out.append(clue(kind="해외", source=x.get("source") or "해외 공고", title=x.get("title"),
                        url=x.get("sourceUrl"), published=x.get("published"), companies=companies,
                        tier=TIER_LEAD if companies else TIER_PUBLIC, signal=x.get("sourceType") or "",
                        key=x.get("sourceId"), note=x.get("notProven") or ""))
    return out


def from_governance(data):
    out = []
    for x in (data or {}).get("items", []) or []:
        if not isinstance(x, dict) or not (x.get("receiptNo") or x.get("groupKey")):
            continue
        companies = beats_in("", x.get("company"))
        change = x.get("ratioChange")
        delta = f" {change:+.2f}%p" if isinstance(change, (int, float)) else ""
        who = x.get("reporter") or ""
        role = f"({x['role']})" if x.get("role") else ""
        row = clue(kind=None, source="DART 지분공시", title=f"{x.get('company')} · {x.get('kind')} · {who}{role}{delta}",
                   url=x.get("url"), published=x.get("date"), companies=companies, tier=TIER_PUBLIC,
                   signal="governance", receipt=x.get("receiptNo"), key=x.get("groupKey"),
                   note=" ".join(x.get("tags") or []) + (f" 사유: {x['reason']}" if x.get("reason") else ""))
        row["routine"] = row["routine"] or bool(x.get("routine"))
        out.append(row)
    return out


def from_earnings(data):
    """Only filed companies whose same-period ratios moved past the flag lines become clues."""
    out = []
    period = ((data or {}).get("period") or {}).get("label") or ""
    for x in (data or {}).get("companies", []) or []:
        if not isinstance(x, dict) or x.get("status") != "filed" or not x.get("tags") or not x.get("url"):
            continue
        q = x.get("quarter") or x.get("annual") or {}
        r = q.get("ratios") or {}
        parts = [f"{label} {r[k]:.1f}%" for k, label in (("costRatio", "원가율"), ("sgaRatio", "판관비율"),
                                                       ("opMargin", "영업이익률")) if isinstance(r.get(k), (int, float))]
        row = clue(kind=None, source="DART 정기보고서", title=f"{x.get('company')} · {period} · " + " · ".join(parts),
                   url=x.get("url"), published=x.get("filedOn"), companies=beats_in("", x.get("company")),
                   tier=TIER_PUBLIC, signal="earnings", receipt=(x.get("receipts") or [None])[0],
                   note=" ".join(x.get("tags") or []) + f" ({x.get('basis', '')}, 전년 동기 대비)")
        out.append(row)
    return out


ADAPTERS = (
    ("scoop.json", from_scoop),
    ("pre_scoop.json", from_pre_scoop),
    ("digests/official_event_triage_latest.json", from_triage),
    ("digests/dart_beat_monitor_latest.json", from_dart_beat),
    ("digests/latest.json", from_morning),
    ("digests/recent_contracts_latest.json", from_contracts),
    ("digests/industry_official_hunt_latest.json", from_industry_hunt),
    ("digests/nhtsa_official_latest.json", from_nhtsa),
    ("digests/crossborder_source_gap_latest.json", from_crossborder),
    ("digests/patent_reporting_triage_latest.json", from_patents),
    ("digests/g2b_tender_latest.json", from_g2b),
    ("digests/federal_register_evidence_latest.json", from_federal_register),
    ("digests/overseas_official_latest.json", from_overseas),
    ("digests/governance_latest.json", from_governance),
    ("digests/earnings_compare_latest.json", from_earnings),
)
TIER_RANK = {TIER_CANDIDATE: 3, TIER_LEAD: 2, TIER_PUBLIC: 1}


def merge_clues(rows):
    """One line per receipt/URL/title; keep the strongest source label and notes."""
    merged = {}
    for row in rows:
        key = row["receiptNo"] or row["url"] or row["title"]
        if not key:
            continue
        old = merged.get(key)
        if old is None:
            merged[key] = dict(row)
            continue
        if TIER_RANK[row["tier"]] > TIER_RANK[old["tier"]]:
            old["tier"] = row["tier"]
        for field in ("published", "url"):
            if not old.get(field) and row.get(field):
                old[field] = row[field]
        for name in row["companies"]:
            if name not in old["companies"]:
                old["companies"].append(name)
        if row["note"] and row["note"] not in old["note"]:
            old["note"] = (old["note"] + " · " + row["note"]).strip(" ·")[:300]
        if old["team"] == "그 외" and row["team"] != "그 외":
            old["team"] = row["team"]
    return list(merged.values())


# ---------------------------------------------------------- press coverage
def tokens(text, drop=()):
    out = set()
    for tok in TOKEN.findall(str(text or "")):
        low = tok.lower()
        if low in STOP or len(low) < 2 or low in drop:
            continue
        out.add(low)
    return out


# Filing/event families: a headline about the same company and the same kind of
# event within a week of the official date is a candidate prior report.
EVENT_FAMILIES = (
    (re.compile(r"공급계약|단일판매|수주"), re.compile(r"공급계약|수주|계약|공급")),
    (re.compile(r"신규시설투자|시설투자|공장등록|증설"), re.compile(r"투자|증설|공장|설비|신설")),
    (re.compile(r"타법인주식|출자|지분"), re.compile(r"지분|인수|취득|출자|매입")),
    (re.compile(r"영업양도|영업양수|자산양도|분할|합병"), re.compile(r"양도|양수|매각|이관|분할|합병|넘긴")),
    (re.compile(r"유상증자|무상증자"), re.compile(r"증자")),
    (re.compile(r"자기주식|주식소각"), re.compile(r"자사주|자기주식|소각")),
    (re.compile(r"리콜|recall", re.I), re.compile(r"리콜|결함|시정조치")),
    (re.compile(r"영업\(잠정\)실적|영업실적"), re.compile(r"실적|영업이익|매출|판매")),
    (re.compile(r"기업가치제고"), re.compile(r"밸류업|기업가치")),
    (re.compile(r"소송|가처분|판결"), re.compile(r"소송|가처분|판결|패소|승소")),
)


def event_family(text):
    for trigger, headline in EVENT_FAMILIES:
        if trigger.search(text or ""):
            return headline
    return None


class CoverageIndex:
    """Headline-only news index (Google News RSS). Similar ≠ same story."""

    def __init__(self, coverage, exclusive):
        self.rows = []
        self.ok = False
        self.generatedAt = stamp(coverage)
        for data in (coverage, exclusive):
            if not isinstance(data, dict):
                continue
            self.ok = True
            for x in data.get("items", []) or []:
                if not isinstance(x, dict) or not x.get("title"):
                    continue
                companies = [beat_name(c) for c in x.get("companies") or []]
                self.rows.append({
                    "title": str(x["title"])[:200], "source": x.get("sourceName"),
                    "published": day(x.get("published")), "url": x.get("url"),
                    "companies": {c for c in companies if c},
                    "tokens": tokens(x["title"]),
                })

    def check(self, item):
        if not self.ok:
            return {"status": "index_unavailable", "label": "대조 불가(뉴스 색인 없음)", "matches": []}
        companies = set(item["companies"])
        if not companies:
            return {"status": "not_compared", "label": "대조 안 함(출입처 기업 미식별)", "matches": []}
        drop = {c.lower() for c in companies} | {a.lower() for c in companies for a in scoop_scout.ALIASES.get(c, ())}
        mine = tokens(item["title"], drop)  # notes are boilerplate; titles only
        family = event_family(item["title"])
        official = parse_dt(item.get("published"))
        scored = []
        for row in self.rows:
            if not (companies & row["companies"]):
                continue
            overlap = len(mine & (row["tokens"] - drop))
            near = False
            if family and official and row["published"]:
                gap = (parse_dt(row["published"]) - official).days
                near = -1 <= gap <= 7 and bool(family.search(row["title"]))
            if overlap >= 2 or near:
                scored.append((overlap + (2 if near else 0), row["published"] or "", row))
        scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
        matches = [{"title": r["title"], "source": r["source"], "published": r["published"], "url": r["url"]}
                   for _, _, r in scored[:3]]
        if matches:
            return {"status": "similar_headlines",
                    "label": f"색인 유사 제목 {len(scored)}건(같은 기업·유사 낱말 또는 공시일 전후 7일 같은 유형) — 같은 사건인지 원문 확인 필요",
                    "matches": matches}
        return {"status": "none_in_index", "label": "색인 0건 — 미보도 증거 아님(제목 색인·365일)", "matches": []}


# -------------------------------------------------------------------- views
def build_clues(root: Path, now: datetime, previous=None, horizon_days=45):
    rows, sources = [], []
    for rel, adapter in ADAPTERS:
        data = load(root / rel)
        got = adapter(data) if data is not None else []
        sources.append({"file": rel, "generatedAt": stamp(data), "rows": len(got),
                        "status": "missing" if data is None else "read"})
        rows.extend(got)
    rows = merge_clues(rows)
    cutoff = (now - timedelta(days=horizon_days)).strftime("%Y-%m-%d")
    rows = [r for r in rows if not r["published"] or r["published"] >= cutoff]
    index = CoverageIndex(load(root / "digests/press_coverage_index_latest.json"),
                          load(root / "digests/historical_exclusive_press_index_latest.json"))
    seen_before = {}
    for old in (previous or {}).get("items", []) or []:
        if isinstance(old, dict) and old.get("id") and old.get("firstSeen"):
            seen_before[old["id"]] = old["firstSeen"]
    stamp_now = now.isoformat(timespec="seconds")
    for row in rows:
        row["coverage"] = index.check(row)
        row["firstSeen"] = seen_before.get(row["id"], stamp_now)
    # newest first inside each team/tier; procedural filings last
    rows.sort(key=lambda r: r["published"] or "0000", reverse=True)
    rows.sort(key=lambda r: (TEAM_ORDER.index(r["team"]), r["routine"], -TIER_RANK[r["tier"]]))
    return {
        "schema": SCHEMA, "generatedAt": stamp_now, "horizonDays": horizon_days,
        "coverageIndexGeneratedAt": index.generatedAt,
        "rules": [
            "출처가 붙인 단계(공개 원자료 추적/취재 단서·단독 미확정/단독 후보)를 올리지 않는다.",
            "published는 공식 게시일, firstSeen은 이 뷰가 처음 본 시각이다. 섞지 않는다.",
            "색인 0건은 미보도 증거가 아니다. 유사 제목은 같은 사건이라는 증거가 아니다.",
        ],
        "sources": sources, "count": len(rows), "items": rows,
    }


TOPIC_LABEL = {"productionCapacity": "생산능력", "productionActual": "생산실적", "segmentSales": "부문 매출",
               "utilization": "가동률", "orderBacklog": "수주잔고"}
BEAT_HS2 = {"27", "28", "29", "38", "39", "40", "72", "73", "74", "75", "76", "79", "84", "85", "87"}


def pct(value):
    try:
        return round(float(value), 1)
    except (TypeError, ValueError):
        return None


def stat_tags(change, extra=()):
    tags = list(extra)
    if change is None:
        return tags
    if abs(change) >= 30:
        tags.append("[급변]")
    if change >= 100:
        tags.append(f"[{change / 100 + 1:.1f}배]")
    return tags


def stat(*, kind, label, team, period, current, prior, unit, change, source, urls, generated,
         company=None, caveat="", tags=(), key=None):
    strength = min(100, abs(change or 0)) + (20 if company else 0) + 10 * len([t for t in tags if t])
    return {
        "id": clue_id(kind, key or label, period), "kind": kind, "team": team, "company": company,
        "label": label, "period": period, "current": current, "prior": prior, "unit": unit,
        "changePercent": change, "tags": stat_tags(change, tags), "strength": round(strength, 1),
        "source": source, "sourceUrls": [u for u in urls if https_url(u)], "sourceGeneratedAt": generated,
        "caveat": caveat,
    }


def from_tenday(data):
    out = []
    data = data or {}
    observed = [o for o in data.get("observed", []) or [] if isinstance(o, dict)]
    for x in data.get("focus", []) or []:
        if not isinstance(x, dict):
            continue
        change = pct(x.get("yoyPercent"))
        same = []
        for o in observed:
            if o.get("cutoff") != x.get("cutoff") or o.get("series") != x.get("series"):
                continue
            for it in o.get("items") or []:
                if isinstance(it, dict) and it.get("name") == x.get("item"):
                    try:
                        same.append((o.get("month"), float(it.get("amountKUsd"))))
                    except (TypeError, ValueError):
                        pass
        extra = []
        try:
            current = float(x.get("amountKUsd"))
            if len(same) >= 6 and current >= max(v for _, v in same):
                first = min(m for m, _ in same)
                extra.append(f"[관측 구간 최대: {first[:4]}.{first[4:]}~]")
        except (TypeError, ValueError):
            pass
        item = str(x.get("item") or "")
        team = ("철강·비철" if "철강" in item else "자동차" if ("승용차" in item or "자동차" in item) else
                "전력·에너지" if any(k in item for k in ("가스", "석유", "전기", "전력")) else
                "화학·소재" if any(k in item for k in ("화학", "플라스틱", "합성수지")) else "그 외")
        out.append(stat(kind="customs_tenday", label=f"{item} 수출 {x.get('month', '')[:4]}.{x.get('month', '')[4:]} {x.get('periodLabel')}일 (관세청 10일 잠정치)",
                        team=team, period=f"{x.get('month')}-{x.get('cutoff')}", current=x.get("amountKUsd"),
                        prior=x.get("priorYearAmountKUsd"), unit="천달러", change=change,
                        source="관세청 수출입 10일 잠정치", urls=[x.get("sourceUrl")], generated=stamp(data),
                        caveat="잠정치·품목군 합계(개별 기업 실적 아님)", tags=extra, key=item))
    return out


def from_customs_five(data):
    out = []
    for svc in (data or {}).get("services", []) or []:
        if not isinstance(svc, dict):
            continue
        for row in svc.get("rows", []) or []:
            if not isinstance(row, dict):
                continue
            code = str(row.get("code") or "")
            change = pct(row.get("changePercent"))
            if code[:2] not in BEAT_HS2 or change is None or abs(change) < 30:
                continue
            try:
                if float(row.get("current") or 0) < 10000:  # < 1천만 달러: too small for a stat line
                    continue
            except (TypeError, ValueError):
                continue
            name = str(row.get("name") or "")
            team = ("철강·비철" if code[:2] in {"72", "73", "74", "75", "76", "79"} or
                    any(k in name for k in ("철강", "비철", "구리", "아연", "알루미늄", "니켈")) else
                    "자동차" if code[:2] in {"87", "40"} else
                    "전력·에너지" if code[:2] in {"85", "84", "27"} else "화학·소재")
            label = f"{row.get('market') or ''} {row.get('name')}(HS{code}) {row.get('flow')} {row.get('month')}"
            out.append(stat(kind="customs_regional", label=label.strip(), team=team, period=row.get("month"),
                            current=row.get("current"), prior=row.get("previous"), unit=svc.get("unit") or "",
                            change=change, source=f"관세청 {svc.get('name')}", urls=[row.get("sourceUrl")],
                            generated=stamp(data), caveat="지역·HS2 품목군(기업 귀속 미확인)",
                            key=f"{svc.get('id')}|{row.get('market')}|{code}|{row.get('flow')}"))
    return out


def from_hs_trends(data):
    out = []
    for x in (data or {}).get("items", []) or []:
        if not isinstance(x, dict):
            continue
        totals = ((x.get("comparison") or {}).get("totals") or {})
        change = pct(totals.get("exportValueYoYPercent"))
        months = (x.get("comparison") or {}).get("comparableMonths") or []
        year = (x.get("comparison") or {}).get("year")
        label = f"HS{x.get('hs4')} {x.get('label')} 수출 {year}년 {months[0] if months else ''}~{months[-1] if months else ''}월 누적"
        hs = str(x.get("hs4") or "")
        team = "철강·비철" if hs.startswith("72") else "자동차" if hs.startswith("87") else "전력·에너지"
        unit_change = pct(totals.get("unitValueYoYPercent") or totals.get("exportUnitValueYoYPercent"))
        extra = [f"[단가 {unit_change:+.1f}%]"] if unit_change is not None and abs(unit_change) >= 10 else []
        out.append(stat(kind="hs_trend", label=label, team=team, period=f"{year}", current=totals.get("currentExportUsd"),
                        prior=totals.get("previousExportUsd"), unit="달러", change=change, source="관세청 HS 품목별",
                        urls=[x.get("sourceUrl")], generated=stamp(data), caveat=x.get("scopeWarning") or "",
                        tags=extra, key=hs))
    return out


def from_metric_changes(data, kind, source, items_key):
    out = []
    for x in (data or {}).get(items_key, []) or []:
        if not isinstance(x, dict):
            continue
        company = beat_name(x.get("company"))
        change = pct(x.get("percentChange") if "percentChange" in x else x.get("changePercent"))
        if change is None or abs(change) < 10:
            continue
        row = " / ".join(str(v) for v in (x.get("rowIdentity") or []))
        entity = str(x.get("reportingEntity") or "")
        if entity:
            row = entity + " / " + row
        topic = TOPIC_LABEL.get(x.get("topic"), x.get("topic"))
        period = (f"{x.get('fromYear')}→{x.get('toYear')}" + (f" {x.get('period')}월 누적" if x.get("period") else ""))
        out.append(stat(kind=kind, label=f"{company or x.get('company')} {topic} ({row})", team=team_for([company] if company else []),
                        period=period, current=x.get("currentValue") or x.get("to"), prior=x.get("priorValue") or x.get("from"),
                        unit=x.get("unit") or "", change=change, source=source, urls=x.get("sourceUrls") or [],
                        generated=stamp(data), company=company,
                        caveat="공시 원문 표 숫자 변동만 확인(물량·사업 영향·기보도 미확인)",
                        key=f"{x.get('company')}|{x.get('topic')}|{row}"))
    return out


def from_peer(data):
    out = []
    for x in (data or {}).get("findings", []) or []:
        if not isinstance(x, dict):
            continue
        company = beat_name(x.get("company"))
        urls = [s.get("url") for s in x.get("sources") or [] if isinstance(s, dict)]
        out.append(stat(kind="peer_gap", label=f"{company or x.get('company')} {x.get('metric')} ({x.get('group')})",
                        team=team_for([company] if company else []), period=f"{x.get('year')} {x.get('period')}",
                        current=x.get("latestYoYPercent"), prior=x.get("comparisonMedianPercent"), unit="%",
                        change=pct(x.get("gapPp")), source="OpenDART 재무 비교", urls=urls, generated=stamp(data),
                        company=company, caveat="비교기업 중앙값과의 격차(%p). 원인 미확인",
                        key=f"{x.get('company')}|{x.get('metric')}|{x.get('year')}"))
    return out


def build_stats(root: Path, now: datetime):
    rows = []
    rows += from_tenday(load(root / "digests/customs_tenday_latest.json"))
    rows += from_customs_five(load(root / "digests/customs_five_latest.json"))
    rows += from_hs_trends(load(root / "digests/hs_trends_latest.json"))
    rows += from_metric_changes(load(root / "digests/recent_metric_changes_latest.json"),
                                "dart_business_recent", "DART 분기·반기 사업의 내용", "items")
    rows += from_metric_changes(load(root / "digests/business_metrics_latest.json"),
                                "dart_business_annual", "DART 사업보고서 사업의 내용", "findings")
    rows += from_peer(load(root / "digests/peer_financial_latest.json"))
    seen, unique = set(), []
    for row in sorted(rows, key=lambda r: r["strength"], reverse=True):
        if row["id"] in seen:
            continue
        seen.add(row["id"])
        unique.append(row)
    return {"schema": SCHEMA, "generatedAt": now.isoformat(timespec="seconds"),
            "rules": ["관세청 HS 기준 숫자와 기업 공시 숫자를 한 문장에 섞지 않는다.",
                      "[관측 구간 최대]는 이 레이더가 가진 기간 안에서의 최대이지 '역대'가 아니다.",
                      "통계 줄은 기사 재료이지 단독 판정이 아니다. 같은 통계를 다른 매체가 이미 썼는지 news_check로 본다."],
            "count": len(unique), "items": unique}


def build_dandok(root: Path, now: datetime, keep_days=120):
    rows, seen = [], set()
    data = load(root / "digests/historical_exclusive_press_index_latest.json") or {}
    cutoff = (now - timedelta(days=keep_days)).strftime("%Y-%m-%d")
    for x in data.get("items", []) or []:
        if not isinstance(x, dict) or not x.get("title"):
            continue
        published = day(x.get("published"))
        if not published or published < cutoff:
            continue
        title = re.sub(r"\s+-\s+[^-]{1,40}$", "", str(x["title"])).strip()
        key = (title, x.get("sourceName"))
        if key in seen:
            continue
        seen.add(key)
        companies = [c for c in (beat_name(c) for c in x.get("companies") or []) if c]
        rows.append({"published": published, "source": x.get("sourceName"), "title": title[:200],
                     "url": x.get("url"), "companies": companies, "team": team_for(companies)})
    rows.sort(key=lambda r: r["published"], reverse=True)
    return {"schema": SCHEMA, "generatedAt": now.isoformat(timespec="seconds"),
            "sourceGeneratedAt": stamp(data), "status": data.get("status"),
            "note": "구글 뉴스 RSS 제목 색인의 [단독] 기사. 전문·원 게시시각 미검증. 목록에 없다고 단독이 아닌 건 아니다.",
            "count": len(rows), "items": rows}


def age_hours(value, now):
    parsed = parse_dt(value)
    return round((now - parsed).total_seconds() / 3600, 1) if parsed else None


HEALTH_FILES = (
    ("레이더 단독 판정(scoop.json)", "scoop.json", 12),
    ("공식 원자료 직접 수집(pre_scoop.json)", "pre_scoop.json", 12),
    ("자동차 뉴스 수집", "digests/auto_news_feed_health_latest.json", 12),
    ("DART 출입처 공시", "digests/dart_beat_run_health_latest.json", 30),
    ("공식 사건 분류", "digests/official_event_triage_latest.json", 30),
    ("기보도 뉴스 색인", "digests/press_coverage_index_latest.json", 30),
    ("[단독] 기사 색인", "digests/historical_exclusive_press_index_latest.json", 30),
    ("계약 공시 원장", "digests/recent_contracts_latest.json", 48),
    ("관세청 10일 잠정치", "digests/customs_tenday_latest.json", 24 * 12),
    ("특허 파이프라인", "digests/patent_run_health_latest.json", 72),
    ("지분공시(대량보유·임원 소유)", "digests/governance_latest.json", 96),
    ("공시 시즌 비교표(원가율·판관비율·직원 수)", "digests/earnings_compare_latest.json", 96),
)


def build_health(root: Path, now: datetime):
    rows = []
    for label, rel, max_age in HEALTH_FILES:
        data = load(root / rel)
        generated = stamp(data)
        age = age_hours(generated, now)
        status = str((data or {}).get("status") or ("missing" if data is None else "ok"))
        problem = data is None or age is None or age > max_age or status in ("degraded", "source_error", "not_connected")
        rows.append({"source": label, "file": rel, "status": status, "generatedAt": generated,
                     "ageHours": age, "expectedMaxAgeHours": max_age, "problem": bool(problem)})
    g2b = load(root / "digests/g2b_source_status_latest.json") or {}
    rows.append({"source": "나라장터 입찰공고", "file": "digests/g2b_source_status_latest.json",
                 "status": g2b.get("status", "missing"), "generatedAt": g2b.get("generatedAt"),
                 "ageHours": age_hours(g2b.get("generatedAt"), now), "expectedMaxAgeHours": 30,
                 "problem": g2b.get("status") != "checked", "note": g2b.get("note")})
    kipris = load(root / "digests/kipris_source_request_budget_latest.json") or {}
    if kipris:
        rows.append({"source": "KIPRIS 특허", "file": "digests/kipris_source_request_budget_latest.json",
                     "status": f"provider_code_{kipris.get('lastProviderResultCode')}" if kipris.get("lastProviderResultCode") else "ok",
                     "generatedAt": kipris.get("lastProviderResponseAt"), "ageHours": age_hours(kipris.get("lastProviderResponseAt"), now),
                     "expectedMaxAgeHours": 72, "problem": bool(kipris.get("lastProviderResultCode")),
                     "note": f"다음 1회 확인 {kipris.get('nextProviderProbeAt')}. 계정 사용량 미검증"})
    pre = load(root / "pre_scoop.json") or {}
    for name, obs in sorted(((pre.get("sourceObservations") or {}).get("sources") or {}).items()):
        if not isinstance(obs, dict) or not name.startswith("direct:"):
            continue
        if obs.get("failStreak", 0) or obs.get("status") not in ("checked_list_not_exhaustive", "index_responded", "ok"):
            rows.append({"source": f"직접 원천 {name[7:]}", "file": "pre_scoop.json", "status": obs.get("status"),
                         "generatedAt": obs.get("lastOk"), "ageHours": age_hours(obs.get("lastOk"), now),
                         "expectedMaxAgeHours": 12, "problem": True,
                         "note": f"연속 실패·부분 {obs.get('failStreak')}회, 마지막 실패 {obs.get('lastFail')}"})
    return {"schema": SCHEMA, "generatedAt": now.isoformat(timespec="seconds"),
            "rule": "수집 실패·미연결·부분 수집은 0건이 아니다. 이 목록의 문제 원천에서 나온 '없음'은 미확인으로 적는다.",
            "problemCount": sum(1 for r in rows if r["problem"]), "items": rows}


def build_big_picture(clues, stats, dandok, health, now: datetime):
    recent = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    by_team = {}
    for row in clues["items"]:
        if (row["published"] or "") >= recent:
            by_team.setdefault(row["team"], {"count": 0, "lead": 0, "indexZero": 0, "routine": 0})
            entry = by_team[row["team"]]
            entry["count"] += 1
            entry["lead"] += row["tier"] != TIER_PUBLIC
            entry["indexZero"] += row["coverage"]["status"] == "none_in_index"
            entry["routine"] += row["routine"]
    week = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    flow = {}
    for row in dandok["items"]:
        if row["published"] >= week:
            for name in row["companies"] or ["(출입처 외)"]:
                flow[name] = flow.get(name, 0) + 1
    return {
        "schema": SCHEMA, "generatedAt": now.isoformat(timespec="seconds"),
        "cluesLast7DaysByTeam": [{"team": t, **by_team[t]} for t in TEAM_ORDER if t in by_team],
        "topStats": [{k: s[k] for k in ("label", "changePercent", "tags", "period", "caveat", "company")}
                     for s in stats["items"][:8]],
        "dandokLast7DaysByCompany": sorted(({"company": k, "count": v} for k, v in flow.items()),
                                           key=lambda r: r["count"], reverse=True)[:12],
        "latestDandok": dandok["items"][:5],
        "healthProblems": [{k: h.get(k) for k in ("source", "status", "ageHours", "note")}
                           for h in health["items"] if h["problem"]],
        "howToRead": [
            "통계 신호(topStats)는 '정기 통계 한 줄 + 출입처 3~4곳 사례'형 기획의 출발점이다.",
            "단독 흐름은 남이 이미 쓴 걸 새것처럼 내지 않기 위해 본다.",
            "healthProblems의 원천에서 나온 '0건'은 미확인이다.",
        ],
    }


def write(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    tmp.replace(path)


def build_all(root: Path, out: Path, now=None):
    now = now or now_kst()
    clues = build_clues(root, now, previous=load(out / "clues.json"))
    stats = build_stats(root, now)
    dandok = build_dandok(root, now)
    health = build_health(root, now)
    big = build_big_picture(clues, stats, dandok, health, now)
    for name, data in (("clues", clues), ("stats", stats), ("dandok", dandok), ("health", health), ("big_picture", big)):
        write(out / f"{name}.json", data)
    return {"clues": clues["count"], "stats": stats["count"], "dandok": dandok["count"],
            "healthProblems": health["problemCount"]}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--out", default=str(ROOT / "tools"))
    args = ap.parse_args()
    summary = build_all(Path(args.root), Path(args.out))
    print("tool views:", json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
