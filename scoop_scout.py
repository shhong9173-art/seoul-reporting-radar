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
    ("현대위아","자동차"),("HL만도","자동차"),("현대트랜시스","자동차"),("현대글로비스","자동차"),("LG에너지솔루션","자동차"),("삼성SDI","자동차"),
    ("SK온","자동차"),("BYD","자동차"),("테슬라","자동차"),
    ("포스코","철강"),("포스코홀딩스","철강"),("현대제철","철강"),("동국제강","철강"),("세아제강","철강"),
    ("고려아연","비철금속"),("영풍","비철금속"),("LS MnM","비철금속"),("풍산","비철금속"),
    ("LS ELECTRIC","전력기기"),("HD현대일렉트릭","전력기기"),("HD현대중공업","전력기기"),("LS마린솔루션","전선·전력"),("효성중공업","전력기기"),("일진전기","전력기기"),
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
OWN_RE = re.compile(r"아이뉴스24|iNews24|inews24", re.I)
PRESS_RE = re.compile(
    r"뉴스와이어|Newswire|PRNewswire|Business Wire|GlobeNewswire|EIN Presswire|PRWeb|Accesswire|Press Release|보도자료|자료제공|자료배포|뉴스룸|미디어센터|프레스센터",
    re.I
)
WEAK_RE = re.compile(r"사회공헌|기부|봉사|교육|인재|채용|수상|선정|캠페인|축제|전시|세미나|포럼|특집|칼럼|오피니언|강연", re.I)\nEVENT_RE = re.compile(
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
    ("자동차","(현대차 OR 기아 OR 제네시스) (특허 OR 자율주행 OR 레벨4 OR 리콜 OR 생산 OR 투자 OR 가격 OR 관세)"),
    ("자동차","(현대모비스 OR 현대위아 OR HL만도) (수주 OR 공급 OR 생산 OR 증설 OR 투자 OR 특허)"),
    ("자동차","(LG에너지솔루션 OR 삼성SDI OR SK온) (ESS OR 배터리 OR 공장 OR 전환 OR 수주 OR 투자)"),
    ("자동차","(BYD OR 테슬라 OR 중국 전기차) (한국 OR 인증 OR 가격 OR 관세 OR 판매)"),
    ("철강","(포스코 OR 현대제철 OR 동국제강 OR 세아제강) (10월 OR 가격 OR 유통가격 OR 수요 OR 재고)"),
    ("철강","(포스코 OR 현대제철 OR 세아제강) (미국 OR 관세 OR 반덤핑 OR OCTG OR 투자 OR 공장)"),
    ("비철금속","(고려아연 OR 영풍 OR LS MnM OR 풍산) (아연 OR 구리 OR 제련 OR 투자 OR 가격 OR 공급)"),
    ("전력기기","(LS ELECTRIC OR HD현대일렉트릭 OR 효성중공업 OR 일진전기) (변압기 OR HVDC OR 데이터센터 OR 수주)"),
    ("전선·전력","(LS전선 OR 대한전선) (해저케이블 OR 초고압 OR HVDC OR 수주 OR 미국 OR 투자)"),
    ("에너지","(두산에너빌리티 OR GS OR GS칼텍스) (수주 OR 투자 OR 발전소 OR 원전 OR 가스 OR 가격)"),
    ("재생에너지","(한화솔루션 OR OCI홀딩스 OR 씨에스윈드) (태양광 OR 풍력 OR ESS OR 전력망 OR 투자)"),
    ("화학·소재","(LG화학 OR 롯데케미칼 OR 금호석유화학 OR 효성첨단소재 OR 코오롱인더) (투자 OR 증설 OR 구조조정 OR 가격)"),
    ("정책·조달","(산업부 OR 국토부 OR 공정위 OR 환경부) (철강 OR 자동차 OR 전력기기) (조달 OR 계약 OR 관세 OR 정책)"),
    ("특허·기술","site:kipris.or.kr (현대차 OR 기아 OR 현대모비스) (특허 OR 자율주행 OR 배터리)"),
    ("특허·기술","site:kipris.or.kr (포스코 OR 현대제철 OR LS ELECTRIC OR 두산에너빌리티) 특허"),
    ("공시·조달","site:dart.fss.or.kr (현대차 OR 기아 OR 포스코 OR 현대제철) (수주 OR 투자 OR 매각 OR 분할)"),
    ("공시·조달","site:dart.fss.or.kr (LS ELECTRIC OR HD현대일렉트릭 OR 두산에너빌리티) (수주 OR 투자)"),
    ("공시·조달","site:dart.fss.or.kr (고려아연 OR 영풍 OR LS MnM OR LG화학 OR 롯데케미칼) 투자"),
    ("정책·조달","site:g2b.go.kr (전력망 OR 변압기 OR ESS OR 철강 OR 자동차) (조달 OR 입찰 OR 계약)"),
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
    if NOISE_RE.search(t) or PRESS_RE.search(t) or OWN_RE.search(str(x.get("sourceName") or "")):
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
    t=(x.get("title","")+" "+x.get("summary","")).lower()
    score=40
    companies=len(company_hits(t))
    actions=sum(1 for w in ACTION_WORDS if w.lower() in t)
    score+=min(24,companies*8)
    score+=min(20,actions*2)
    score+=16 if NUM_RE.search(t) else 0
    score+=14 if any(w in t for w in ("단독","특허","공시","최종판정","덤핑마진","원산지","전량","신규","확정")) else 0
    score+=14 if same_issue_sources<=1 else (8 if same_issue_sources==2 else 0)
    score-=12 if same_issue_sources>=5 else 0
    spread=int(x.get("clusterCount") or 0)
    if spread==1: score+=10
    elif spread==2: score+=5
    elif spread>=5: score-=18
    if history: score-=min(24,max(0,len(history)-1)*8)
    return max(0,min(99,score))

def make_candidate(x: dict, all_hits: list[dict], archive: list[dict]) -> dict:
    title=x.get("title") or ""
    issue=canonical_issue(title)
    issue_hits=[h for h in all_hits if similarity(issue,canonical_issue(h.get("title") or ""))>=0.55]
    base_sources=x.get("coveredBy") or ([x.get("sourceName")] if x.get("sourceName") else [])
    distinct_sources=list(dict.fromkeys([*base_sources,*[h.get("sourceName") for h in issue_hits if h.get("sourceName")]]))
    history=in_archive(title,archive,4)
    companies=company_hits((title+" "+x.get("summary","")))
    beat=beat_for(title+" "+x.get("summary",""))
    numbers=list(dict.fromkeys(NUM_RE.findall(title+" "+x.get("summary",""))))[:8]
    kind=candidate_kind(x)
    same_issue_sources=len(distinct_sources)

    why=f"{x.get('sourceName','한 매체')}에서 먼저 포착된 이슈입니다. 현재 아이뉴스24 보도 여부와 확산 정도를 대조해 선점 가능성을 확인합니다."
    if same_issue_sources>1:
        why+=f" 같은 이슈가 현재 {same_issue_sources}개 매체에서 확인돼 추가로 붙을 수 있는 사실이 있는지 봅니다."
    else:
        why+=" 현재 확인 매체가 1곳이라 회사·정부 원자료를 바로 대조할 가치가 있습니다."
    if history:
        why+=f" 과거 유사 기사 {len(history)}건과 비교해 무엇이 새로 달라졌는지도 확인합니다."

    if kind=="특허·기술":
        angle="특허 원문에서 적용 제품·출원 범위·양산 시점을 확인해 기술 소개가 아닌 사업화 기사로 확장"
        pitch_text=f"{title.split(' - ')[0].strip()}…특허 실제 적용·양산 시점이 변수"
    elif kind=="정책·조달":
        angle="정책·조달 원문과 실제 발주·예산·참여 기업을 맞춰 새로 생기는 물량과 수혜처를 확인"
        pitch_text=f"{title.split(' - ')[0].strip()}…실제 발주·예산 규모가 관건"
    elif kind=="통상":
        angle="시행·최종 판정 조건을 실제 출하·계약에 대입해 국내 기업의 물량·가격·수출전략 변화를 확인"
        pitch_text=f"{title.split(' - ')[0].strip()}…출하·계약 영향까지 확인할 필요"
    elif kind=="가격·수요":
        angle="발표 가격과 실제 유통가격·주문·재고를 대조해 시장에서 실제로 가격이 움직였는지 확인"
        pitch_text=f"{title.split(' - ')[0].strip()}…발표 가격과 실제 유통가격이 변수"
    elif kind=="공시·사업":
        angle="공시 원문과 기존 투자·생산 계획을 대조해 숫자 변화가 실제 사업재편으로 이어지는지 확인"
        pitch_text=f"{title.split(' - ')[0].strip()}…기존 계획과 실제 집행의 차이가 핵심"
    else:
        angle="최초 기사에 없는 추가 숫자·계약·회사 입장을 붙여 아이뉴스24만의 후속 기사로 확장"
        pitch_text=f"{title.split(' - ')[0].strip()}…회사 대응과 추가 숫자 확인이 핵심"

    questions=[
        "원자료는 무엇이며 회사·정부의 공식 확인은 나왔는가?",
        "기존 공개 계획이나 지난해 같은 시점과 비교해 새롭게 달라진 숫자는 무엇인가?",
        "출입처에서 확인할 실제 물량·계약·가격·투자·생산 변화는 무엇인가?"
    ]
    if numbers:
        questions[1]=f"확인된 {', '.join(numbers[:3])}이 기존 수치와 어떻게 달라졌는가?"

    source_rows=[]
    for h in issue_hits[:5]:
        source_rows.append({"source":h.get("sourceName") or "-", "title":h.get("title") or "", "url":h.get("url"), "published":h.get("published")})

    return {
        "id":hashlib.sha1((x.get("url","")+"|"+title).encode()).hexdigest()[:12],
        "kind":kind,
        "beat":beat,
        "title":title,
        "score":score_candidate(x,len(distinct_sources),same_issue_sources,history),
        "status":"확인중",
        "why":why,
        "whatConfirmed":f"{x.get('sourceName','매체')}에서 {title}",
        "angle":angle,
        "pitch":pitch_text,
        "numbers":numbers,
        "companies":companies[:5],
        "sources":source_rows,
        "history":[{"title":h.get("title"),"source":h.get("sourceName"),"published":h.get("published")} for h in history],
        "questions":questions,
        "firstSeenAt":x.get("published"),
        "firstSeenSource":x.get("sourceName"),
        "coverageSources":distinct_sources[:8],
    }

def main():
    try:
        data=json.loads(DATA.read_text(encoding="utf-8")) if DATA.exists() else []
    except Exception:
        data=[]
    try:
        archive=json.loads(ARCHIVE.read_text(encoding="utf-8")) if ARCHIVE.exists() else []
    except Exception:
        archive=[]

    # Start with the current newsroom DB, then add an independent web search layer.
    # The goal is not "already covered nowhere"; it is "not yet covered by iNews24
    # and still actionable enough to pursue".
    feed_seeds=[]
    for x in data:
        if not x.get("global") and not is_bad(x):
            t=(x.get("title") or "")+" "+(x.get("summary") or "")
            signal=sum(1 for w in ACTION_WORDS if w.lower() in t.lower())
            spread=int(x.get("clusterCount") or 1)
            if x.get("exclusive") or NUM_RE.search(t) or signal>=2 or spread<=2:
                feed_seeds.append(x)

    web_hits=search_hits()
    pool=[]
    seen=set()
    for x in sorted(feed_seeds+web_hits,key=lambda z:z.get("published",""),reverse=True):
        k=(x.get("sourceName",""),title_key(x.get("title","")))
        if k in seen or is_bad(x):
            continue
        seen.add(k)
        pool.append(x)

    candidates=[]
    seen_issue=set()
    for x in pool:
        title=x.get("title") or ""
        source=str(x.get("sourceName") or "")
        if not title or OWN_RE.search(source):
            continue

        # Do not call a broadly covered item a scoop candidate unless it carries
        # a genuinely new exclusive/number/policy/contract fact.
        spread=int(x.get("clusterCount") or 0)
        new_fact=bool(x.get("exclusive") or NUM_RE.search(title+" "+x.get("summary","")))
        if x in data and spread>4 and not new_fact:
            continue

        c=make_candidate(x,pool,archive)
        if c["score"]<55:
            continue
        joined=(title+" "+x.get("summary","")).lower()
        if not (c["numbers"] or c["companies"] or x.get("exclusive")):
            continue
        if not any(w.lower() in joined for w in ACTION_WORDS):
            continue

        issue=canonical_issue(title)
        if issue in seen_issue:
            continue
        seen_issue.add(issue)
        candidates.append(c)

    candidates.sort(
        key=lambda x:(
            x["score"],
            len(x["coverageSources"])<=1,
            bool(x["numbers"]),
            len(x["history"])==0,
        ),
        reverse=True
    )

    old={}
    if OUT.exists():
        try:
            old={x.get("id"):x for x in json.loads(OUT.read_text(encoding="utf-8")).get("items",[])}
        except Exception:
            old={}

    for c in candidates:
        prev=old.get(c["id"])
        if prev:
            c["status"]=prev.get("status","확인중")
            c["note"]=prev.get("note","")
            c["checkedCount"]=int(prev.get("checkedCount",0))+1
        else:
            c["checkedCount"]=1

    out=candidates[:60]
    payload={
        "generatedAt":datetime.now(KST).isoformat(),
        "windowDays":7,
        "searchEngines":["Google News RSS","Bing News RSS"],
        "counts":{
            "hits":len(pool),
            "candidates":len(out),
            "beats":len({x["beat"] for x in out}),
            "singleSource":sum(1 for x in out if len(x["coverageSources"])<=1),
        },
        "items":out,
        "note":"현재 기사 DB와 웹 탐색 결과를 비교해 아이뉴스24 미보도·단일매체·정책·공시·수치·특허·통상 등 실제 확인 가능한 기사거리를 지속 축적합니다."
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    print(
        f"scoop scout: pool {len(pool)} -> {len(out)} candidates / "
        f"single-source {payload['counts']['singleSource']}"
    )

if __name__ == "__main__":
    main()
