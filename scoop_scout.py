from __future__ import annotations

import hashlib
import html
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

KST = timezone(timedelta(hours=9))
DATA = Path("data.json")
ARCHIVE = Path("archive.json")
OUT = Path("scoop.json")

AUTO = {
    "완성차","부품","배터리","정책·관세","중국차","노조·생산","수주·투자","리콜·안전","단독","미국·글로벌"
}
IND = {
    "철강","비철금속","전력기기","전선·전력","에너지","재생에너지","화학·소재"
}
TARGETS = [
    ("현대차","자동차"),("기아","자동차"),("제네시스","자동차"),("현대모비스","자동차"),
    ("현대위아","자동차"),("HL만도","자동차"),("LG에너지솔루션","자동차"),("삼성SDI","자동차"),
    ("SK온","자동차"),("BYD","자동차"),("테슬라","자동차"),
    ("포스코","철강"),("포스코홀딩스","철강"),("현대제철","철강"),("동국제강","철강"),("세아제강","철강"),
    ("고려아연","비철금속"),("영풍","비철금속"),("LS MnM","비철금속"),("풍산","비철금속"),
    ("LS ELECTRIC","전력기기"),("HD현대일렉트릭","전력기기"),("효성중공업","전력기기"),("일진전기","전력기기"),
    ("LS전선","전선·전력"),("대한전선","전선·전력"),
    ("두산에너빌리티","에너지"),("GS","에너지"),("GS칼텍스","에너지"),
    ("한화솔루션","재생에너지"),("OCI홀딩스","재생에너지"),("씨에스윈드","재생에너지"),
    ("LG화학","화학·소재"),("롯데케미칼","화학·소재"),("금호석유화학","화학·소재"),
    ("효성첨단소재","화학·소재"),("코오롱인더","화학·소재")
]

NOISE_RE = re.compile(
    r"주가|증권|목표주가|급등|급락|추천|관련주|테마주|특징주|장중|오전장|종목|주목할 종목|리포트",
    re.I
)
PRESS_RE = re.compile(
    r"뉴스와이어|Newswire|PRNewswire|Business Wire|GlobeNewswire|EIN Presswire|PRWeb|Accesswire|Press Release|보도자료|자료제공|자료배포|뉴스룸|미디어센터|프레스센터",
    re.I
)
EVENT_RE = re.compile(
    r"인베스터데이|주주총회|설명회|세미나|포럼|엑스포|컨퍼런스|부스투어|기조연설|발표회"
)
ACTION_WORDS = (
    "수주","계약","공급","납품","증설","투자","공장","생산","가동","감산","철수","매각","인수","합병",
    "분할","합작","관세","반덤핑","덤핑마진","원산지","통관","가격","원가","마진","수요","재고",
    "특허","리콜","결함","화재","자율주행","레벨4","ESS","전력망","배전","송전","변압기","HVDC",
    "해저케이블","해상풍력","풍력","태양광","배터리","배터리소재"
)
NUM_RE = re.compile(
    r"(?<!\d)(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?:조원|억원|만원|달러|만대|천대|대|명|%|GWh|MWh|kWh|톤|km|MW|GW)(?!\w)",
    re.I
)

QUERY_SETS = [
    ("자동차","현대차 기아 제네시스 특허 자율주행 레벨4 리콜 생산 투자 가격 관세"),
    ("자동차","현대모비스 현대위아 HL만도 수주 공급 생산 증설 투자 특허"),
    ("자동차","LG에너지솔루션 삼성SDI SK온 ESS 배터리 공장 전환 수주 투자"),
    ("자동차","BYD 테슬라 중국 전기차 한국 인증 가격 관세 판매"),
    ("철강","포스코 현대제철 동국제강 세아제강 10월 가격 유통가격 수요 재고"),
    ("철강","포스코 현대제철 세아제강 미국 철강 관세 반덤핑 OCTG 투자 공장"),
    ("비철금속","고려아연 영풍 LS MnM 풍산 아연 구리 제련 투자 가격 공급"),
    ("전력기기","LS ELECTRIC HD현대일렉트릭 효성중공업 일진전기 변압기 HVDC 데이터센터 수주"),
    ("전선·전력","LS전선 대한전선 해저케이블 초고압 HVDC 수주 미국 투자"),
    ("에너지","두산에너빌리티 GS GS칼텍스 수주 투자 발전소 원전 가스 가격"),
    ("재생에너지","한화솔루션 OCI홀딩스 씨에스윈드 태양광 풍력 ESS 전력망 투자"),
    ("화학·소재","LG화학 롯데케미칼 금호석유화학 효성첨단소재 코오롱인더 투자 증설 구조조정 가격"),
    ("정책·조달","산업부 국토부 공정위 환경부 철강 자동차 전력기기 조달 계약 관세 정책"),
    ("특허·기술","site:kipris.or.kr 현대차 기아 현대모비스 특허 자율주행 배터리"),
    ("특허·기술","site:kipris.or.kr 포스코 현대제철 LS ELECTRIC 두산에너빌리티 특허"),
    ("공시·조달","site:dart.fss.or.kr 현대차 기아 포스코 현대제철 수주 투자 매각 분할"),
    ("공시·조달","site:dart.fss.or.kr LS ELECTRIC HD현대일렉트릭 두산에너빌리티 수주 투자"),
    ("공시·조달","site:dart.fss.or.kr 고려아연 영풍 LS MnM LG화학 롯데케미칼 투자"),
    ("정책·조달","site:g2b.go.kr 전력망 변압기 ESS 철강 자동차 조달 계약"),
]

def get(url: str, timeout: int = 15) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 NewsroomScoopScout/1.0",
            "Accept": "application/rss+xml,application/xml,text/xml,text/html,*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def clean(s: str) -> str:
    s = re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>", " ", s or "", flags=re.I | re.S)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()

def parse_dt(raw: str) -> datetime:
    value=str(raw or '').strip()
    try:
        d=parsedate_to_datetime(value)
        if d.tzinfo is None: d=d.replace(tzinfo=KST)
        return d.astimezone(KST)
    except Exception:
        pass
    try:
        d=datetime.fromisoformat(value.replace("Z","+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=KST)
    except Exception:
        return datetime.min.replace(tzinfo=KST)

def tokens(s: str) -> set[str]:
    return {
        w for w in re.findall(r"[가-힣A-Za-z0-9]{2,}", (s or "").lower())
        if w not in {"기사","관련","시장","업계","기업","최근","오늘","한국","국내","사업","계획"}
    }

def similarity(a: str, b: str) -> float:
    aa, bb = tokens(a), tokens(b)
    return len(aa & bb) / max(1, len(aa | bb))

def source_of(item) -> str:
    node = item.find("source")
    return (node.text or "").strip() if node is not None else ""

def parse_google(category: str, query: str, max_items: int = 12) -> list[dict]:
    url = "https://news.google.com/rss/search?q=" + urllib.parse.quote(query) + "&hl=ko&gl=KR&ceid=KR:ko"
    try:
        root = ET.fromstring(get(url))
    except Exception:
        return []
    cutoff = datetime.now(KST) - timedelta(days=7)
    out = []
    for item in root.findall("./channel/item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        desc = clean(item.findtext("description") or "")
        if not title or not link:
            continue
        dt = parse_dt(pub)
        if dt < cutoff:
            continue
        out.append({
            "category": category,
            "title": title,
            "url": link,
            "published": dt.isoformat(),
            "sourceName": source_of(item) or "Google News",
            "summary": desc[:1000],
        })
        if len(out) >= max_items:
            break
    return out

def parse_bing(category: str, query: str, max_items: int = 8) -> list[dict]:
    url = "https://www.bing.com/news/search?q=" + urllib.parse.quote(query) + "&format=rss"
    try:
        root = ET.fromstring(get(url))
    except Exception:
        return []
    cutoff = datetime.now(KST) - timedelta(days=7)
    out = []
    for item in root.findall("./channel/item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        desc = clean(item.findtext("description") or "")
        if not title or not link:
            continue
        dt = parse_dt(pub)
        if dt < cutoff:
            continue
        out.append({
            "category": category,
            "title": title,
            "url": link,
            "published": dt.isoformat(),
            "sourceName": source_of(item) or "Bing News",
            "summary": desc[:1000],
        })
        if len(out) >= max_items:
            break
    return out

def title_key(t: str) -> str:
    return re.sub(r"[^가-힣A-Za-z0-9]", "", (t or "").lower())[:160]

def company_hits(s: str) -> list[str]:
    return [name for name, _ in TARGETS if name.lower() in (s or "").lower()]

def beat_for(s: str) -> str:
    hits = [beat for name, beat in TARGETS if name.lower() in (s or "").lower()]
    if hits:
        return hits[0]
    return "산업부"

def is_bad(x: dict) -> bool:
    t = (x.get("title") or "") + " " + (x.get("summary") or "")
    if NOISE_RE.search(t) or PRESS_RE.search(t):
        return True
    if EVENT_RE.search(x.get("title") or "") and not any(k in t for k in ACTION_WORDS):
        return True
    return False

def canonical_issue(title: str) -> str:
    t = re.sub(r"\[[^\]]*\]|【[^】]*】|\([^\)]*\)", " ", title or "")
    t = re.sub(r"(단독|속보|긴급|종목|리포트|분석|전망|특종)", " ", t, flags=re.I)
    return " ".join(t.lower().split())[:220]

def in_archive(title: str, archive: list[dict], limit: int = 3) -> list[dict]:
    scored = []
    for row in archive:
        if row.get("global"):
            continue
        old = row.get("title") or ""
        sim = similarity(title, old)
        if sim >= 0.42:
            scored.append((sim, row))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored[:limit]]

def search_hits():
    all_hits = []
    for category, query in QUERY_SETS:
        all_hits.extend(parse_google(category, query))
        all_hits.extend(parse_bing(category, query))
    seen = set()
    out = []
    for x in sorted(all_hits, key=lambda z: z["published"], reverse=True):
        k = (x["sourceName"], title_key(x["title"]))
        if k in seen:
            continue
        seen.add(k)
        if not is_bad(x):
            out.append(x)
    return out

def candidate_kind(x: dict) -> str:
    t = (x.get("title","") + " " + x.get("summary","")).lower()
    if any(k in t for k in ("특허","kipris")):
        return "특허·기술"
    if any(k in t for k in ("조달","입찰","공급계약","계약")):
        return "정책·조달"
    if any(k in t for k in ("관세","반덤핑","덤핑마진","원산지","통관")):
        return "통상"
    if any(k in t for k in ("가격","유통가격","수요","재고","마진","원가")):
        return "가격·수요"
    if any(k in t for k in ("공시","투자","증설","공장","매각","분할","철수")):
        return "공시·사업"
    return "단독감"

def score_candidate(x: dict, same_source: int, same_issue_sources: int, history: list[dict]) -> int:
    t = (x.get("title","") + " " + x.get("summary","")).lower()
    score = 42
    score += min(18, len(company_hits(t)) * 6)
    score += min(18, sum(1 for w in ACTION_WORDS if w.lower() in t) * 2)
    score += 14 if NUM_RE.search(t) else 0
    score += 10 if any(w in t for w in ("단독","특허","공시","확정","최종판정","전량","신규","처음")) else 0
    score += 10 if same_source == 1 else 0
    score += 8 if same_issue_sources == 1 else 0
    score -= min(24, max(0, len(history) - 1) * 8)
    return max(0, min(99, score))

def make_candidate(x: dict, all_hits: list[dict], archive: list[dict]) -> dict:
    title = x.get("title") or ""
    issue = canonical_issue(title)
    issue_hits = [
        h for h in all_hits
        if similarity(issue, canonical_issue(h.get("title") or "")) >= 0.55
    ]
    distinct_sources = list(dict.fromkeys(h.get("sourceName") for h in issue_hits if h.get("sourceName")))
    history = in_archive(title, archive, 4)
    companies = company_hits((title + " " + x.get("summary","")))
    if not companies:
        companies = company_hits(issue)
    same_source = len(distinct_sources)
    same_issue_sources = len(issue_hits)
    score = score_candidate(x, same_source, same_issue_sources, history)
    beat = beat_for(title + " " + x.get("summary",""))
    numbers = list(dict.fromkeys(NUM_RE.findall(title + " " + x.get("summary",""))))[:8]
    kind = candidate_kind(x)

    why = (
        f"{x.get('sourceName','한 매체')}에서 먼저 포착된 이슈입니다. "
        f"현재 검색권에서 같은 내용이 {same_issue_sources}건 확인돼 확산 전 선점 여부를 볼 수 있습니다."
    )
    if history:
        why += f" 과거 유사 이슈 {len(history)}건과 비교해 새로 붙은 사실을 확인해야 합니다."
    if kind == "특허·기술":
        angle = "특허 원문에서 실제 적용 제품·양산 시점·출원 범위를 확인해 단순 특허 소개를 넘어 사업화 가능성을 취재"
    elif kind == "정책·조달":
        angle = "정책·조달 원문과 실제 기업 수주·참여 여부를 맞춰 시장에 새로 생기는 물량을 확인"
    elif kind == "통상":
        angle = "최종 판정·시행 시점과 실제 출하·계약 조건을 붙여 국내 기업의 수출전략 변화를 확인"
    elif kind == "가격·수요":
        angle = "발표 가격과 실제 유통가격·주문·재고를 대조해 시장 반영 여부를 확인"
    elif kind == "공시·사업":
        angle = "공시 원문과 기존 사업계획을 대조해 실제 자금·생산·사업 포트폴리오 변화인지 확인"
    else:
        angle = "최초 보도에 없는 추가 숫자·계약·현장 상황을 붙여 아이뉴스24만의 후속 기사로 확장"

    pitch = (
        f"{companies[0] if companies else beat} {title.split(' - ')[0].strip()}…"
        f"실제 사업 영향과 다음 변수를 확인"
    )
    questions = [
        "이 내용의 원자료는 무엇이며 회사·정부의 공식 확인은 나왔는가?",
        "기존 공개 계획이나 지난해 같은 시점과 비교해 새롭게 달라진 숫자는 무엇인가?",
        "출입처에서 확인할 실제 물량·계약·가격·투자·생산 변화는 무엇인가?"
    ]
    if numbers:
        questions[1] = f"확인된 {', '.join(numbers[:3])}이 기존 수치와 어떻게 달라졌는가?"
    source_rows = []
    for h in issue_hits[:5]:
        source_rows.append({
            "source": h.get("sourceName") or "-",
            "title": h.get("title") or "",
            "url": h.get("url"),
            "published": h.get("published"),
        })
    return {
        "id": hashlib.sha1((x.get("url","")+"|"+title).encode()).hexdigest()[:12],
        "kind": kind,
        "beat": beat,
        "title": title,
        "score": score,
        "status": "확인중",
        "why": why,
        "whatConfirmed": f"{x.get('sourceName','매체')}에서 {title}",
        "angle": angle,
        "pitch": pitch,
        "numbers": numbers,
        "companies": companies[:5],
        "sources": source_rows,
        "history": [
            {"title": h.get("title"), "source": h.get("sourceName"), "published": h.get("published")}
            for h in history
        ],
        "questions": questions,
        "firstSeenAt": x.get("published"),
        "firstSeenSource": x.get("sourceName"),
        "coverageSources": distinct_sources[:8],
    }

def main():
    try:
        data = json.loads(DATA.read_text(encoding="utf-8")) if DATA.exists() else []
    except Exception:
        data = []
    try:
        archive = json.loads(ARCHIVE.read_text(encoding="utf-8")) if ARCHIVE.exists() else []
    except Exception:
        archive = []

    existing_titles = [x.get("title","") for x in data if x.get("title")]
    hits = search_hits()
    candidates = []
    seen_issue = set()

    for x in hits:
        title = x.get("title") or ""
        if not title:
            continue
        # Keep genuinely new findings. Items already present in the newsroom feed
        # are useful as context, but do not become "scoop candidates".
        if max([similarity(title, old) for old in existing_titles] or [0]) >= 0.82:
            continue
        issue = canonical_issue(title)
        if issue in seen_issue:
            continue
        seen_issue.add(issue)
        c = make_candidate(x, hits, archive)
        # A scoop candidate needs at least one concrete reporting signal.
        if not c["numbers"] and not c["companies"] and c["kind"] == "단독감":
            continue
        if c["score"] < 60:
            continue
        candidates.append(c)

    candidates.sort(key=lambda x: (x["score"], bool(x["numbers"]), len(x["questions"])), reverse=True)

    old = {}
    if OUT.exists():
        try:
            old = {x.get("id"): x for x in json.loads(OUT.read_text(encoding="utf-8")).get("items", [])}
        except Exception:
            old = {}
    for c in candidates:
        prev = old.get(c["id"])
        if prev:
            c["status"] = prev.get("status","확인중")
            c["note"] = prev.get("note","")
    out = candidates[:30]
    payload = {
        "generatedAt": datetime.now(KST).isoformat(),
        "windowDays": 7,
        "searchEngines": ["Google News RSS","Bing News RSS"],
        "counts": {
            "hits": len(hits),
            "candidates": len(out),
            "beats": len({x["beat"] for x in out}),
            "singleSource": sum(1 for x in out if len(x["coverageSources"]) <= 1),
        },
        "items": out,
        "note": "뉴스·공시·특허·정책·조달 검색 결과를 기존 기사 DB와 대조해 확산 전 기사거리를 추립니다."
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",",":")), encoding="utf-8")
    print(
        f"scoop scout: {len(hits)} web hits -> {len(out)} candidates / "
        f"single-source {payload['counts']['singleSource']}"
    )

if __name__ == "__main__":
    main()
