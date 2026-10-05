from __future__ import annotations

import hashlib
import html
import io
import json
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

KST=timezone(timedelta(hours=9))
DATA=Path("data.json"); DART=Path("dart.json"); NUM=Path("dart_numeric.json")
ARCHIVE=Path("archive.json"); OUT=Path("scoop.json")

TARGETS=[
 ("현대차","자동차"),("기아","자동차"),("제네시스","자동차"),("현대모비스","자동차"),("현대위아","자동차"),
 ("현대트랜시스","자동차"),("HL만도","자동차"),("현대글로비스","자동차"),("LG에너지솔루션","배터리"),
 ("삼성SDI","배터리"),("SK온","배터리"),("포스코","철강"),("포스코홀딩스","철강"),("현대제철","철강"),
 ("동국제강","철강"),("세아제강","철강"),("고려아연","비철금속"),("영풍","비철금속"),("LS MnM","비철금속"),
 ("풍산","비철금속"),("LS ELECTRIC","전력기기"),("HD현대일렉트릭","전력기기"),("효성중공업","전력기기"),
 ("일진전기","전력기기"),("LS전선","전선·전력"),("대한전선","전선·전력"),("두산에너빌리티","에너지"),
 ("GS","에너지"),("GS칼텍스","에너지"),("한화솔루션","재생에너지"),("OCI홀딩스","재생에너지"),
 ("씨에스윈드","재생에너지"),("LG화학","화학·소재"),("롯데케미칼","화학·소재"),("금호석유화학","화학·소재"),
 ("효성첨단소재","화학·소재"),("코오롱인더","화학·소재")
]
ALIASES={
 "현대차":("현대차","현대자동차"),"기아":("기아","기아자동차"),"LG에너지솔루션":("LG에너지솔루션","LG엔솔"),
 "LS ELECTRIC":("LS ELECTRIC","LS일렉트릭"),"HD현대일렉트릭":("HD현대일렉트릭",),
 "두산에너빌리티":("두산에너빌리티",),"포스코":("포스코","POSCO"),"현대제철":("현대제철","Hyundai Steel"),
 "고려아연":("고려아연",),"롯데케미칼":("롯데케미칼",),"한화솔루션":("한화솔루션",)
}
OFFICIAL_DOMAINS={
 "motie.go.kr":"산업부","molit.go.kr":"국토부","ftc.go.kr":"공정위","kostat.go.kr":"통계청",
 "korea.kr":"정부","moef.go.kr":"기재부","customs.go.kr":"관세청","me.go.kr":"환경부","kma.go.kr":"기상청",
 "g2b.go.kr":"조달청","kipris.or.kr":"특허청·KIPRIS","kipo.go.kr":"특허청","fss.or.kr":"금감원·DART",
 "dart.fss.or.kr":"DART","nhtsa.gov":"NHTSA","ustr.gov":"USTR","trade.gov":"미 상무부",
 "ec.europa.eu":"EU 집행위","europa.eu":"EU","sec.gov":"SEC","epa.gov":"EPA","energy.gov":"미 에너지부","bis.gov":"BIS"
}
COMPANY_DOMAINS={
 "현대차":"hyundai.com","기아":"kia.com","현대모비스":"mobis.com","포스코":"posco.com",
 "현대제철":"hyundai-steel.com","고려아연":"koreazinc.co.kr","LS ELECTRIC":"ls-electric.com",
 "두산에너빌리티":"doosanenerbility.com","GS칼텍스":"gscaltex.com","한화솔루션":"hanwhasolutions.com",
 "LG화학":"lgchem.com","롯데케미칼":"lottechem.com"
}
NOISE_RE=re.compile(r"주가|증권|목표주가|급등|급락|관련주|테마주|특징주|장중|종목|추천주|리포트",re.I)
WEAK_RE=re.compile(r"사회공헌|기부|봉사|채용|수상|캠페인|축제|전시|세미나|포럼|강연|홍보대사|혜택|이벤트|모먼트|스토리",re.I)
HARD_SIGNAL_RE=re.compile(r"정책|규제|시행|고시|법안|입법|관세|반덤핑|특허|출원|등록|대표이사|임원|사내이사|사외이사|선임|취임|퇴임|조직개편|신설|투자|출자|증설|공장|법인|합병|분할|인수|매각|철수|수주|계약|공급|발주|입찰|생산|가동|감산|가격|원가|마진|배터리|ESS|HVDC|변압기|해저케이블|해상풍력|자율주행|리콜|조업정지",re.I)
TOPIC_RE=re.compile(r"자동차|전기차|배터리|철강|비철|구리|아연|니켈|전력|변압기|HVDC|케이블|풍력|태양광|ESS|에너지|석유화학|화학|소재|공장|수출|관세|산업단지|자율주행|데이터센터|원전",re.I)
NUM_RE=re.compile(r"(?<!\d)(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?:조원|억원|만원|달러|만대|천대|대|명|%|GWh|MWh|kWh|톤|km|MW|GW)(?!\w)",re.I)

PRIMARY_QUERY_SETS=[
 ("정책·규제","site:motie.go.kr (정책 OR 고시 OR 시행 OR 법안 OR 제도 OR 관세 OR 통상) (자동차 OR 철강 OR 전력 OR 배터리 OR ESS OR 에너지)"),
 ("정책·규제","site:molit.go.kr (정책 OR 고시 OR 시행 OR 법안 OR 제도) (자동차 OR 자율주행 OR 전기차 OR 리콜)"),
 ("정책·규제","site:ftc.go.kr (기업결합 OR 부당지원 OR 담합 OR 인수 OR 분할 OR 합병)"),
 ("정책·규제","site:customs.go.kr (철강 OR 자동차 OR 배터리) (관세 OR 반덤핑 OR 통관)"),
 ("정책·규제","site:moef.go.kr (세제 OR 투자 OR 산업) (자동차 OR 에너지 OR 제조)"),
 ("정책·규제","site:me.go.kr (탄소 OR 배출권 OR 재생에너지 OR 산업)"),
 ("조달·발주","site:g2b.go.kr (변압기 OR HVDC OR ESS OR 전력망 OR 철강 OR 자동차) (입찰 OR 계약 OR 발주)"),
 ("특허·기술","site:kipris.or.kr (현대차 OR 기아 OR 현대모비스 OR 포스코 OR LS일렉트릭) (특허 OR 출원 OR 등록)"),
 ("특허·기술","site:kipo.go.kr (현대차 OR 기아 OR 포스코 OR 현대제철 OR LS일렉트릭 OR 두산에너빌리티) (특허 OR 출원 OR 등록)"),
 ("통상·해외","site:ustr.gov (automotive OR steel OR battery OR tariff OR Korea)"),
 ("통상·해외","site:trade.gov (steel OR automotive OR battery OR Korea OR tariff)"),
 ("통상·해외","site:ec.europa.eu (steel OR automotive OR battery OR Korean)"),
]
for company,domain in COMPANY_DOMAINS.items():
    PRIMARY_QUERY_SETS.append(("기업 원자료",f"site:{domain} ({company} OR 투자 OR 증설 OR 공장 OR 수주 OR 계약 OR 특허 OR 임원 OR 대표이사 OR 조직개편)"))

def get(url,timeout=15):
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 NewsroomScoopScout/3.0","Accept":"application/rss+xml,application/xml,text/xml,*/*"})
    with urllib.request.urlopen(req,timeout=timeout) as r:return r.read()

def clean(s):
    s=html.unescape(s or "")
    s=re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>"," ",s,flags=re.I|re.S)
    return re.sub(r"\s+"," ",s).strip()

def parse_dt(raw):
    v=str(raw or "").strip()
    if re.fullmatch(r"\d{8}",v):
        try:return datetime.strptime(v,"%Y%m%d").replace(tzinfo=KST)
        except ValueError:pass
    try:
        d=parsedate_to_datetime(v)
        return d.astimezone(KST) if d.tzinfo else d.replace(tzinfo=KST)
    except Exception:
        try:
            d=datetime.fromisoformat(v.replace("Z","+00:00"))
            return d if d.tzinfo else d.replace(tzinfo=KST)
        except Exception:return datetime.min.replace(tzinfo=KST)

def tokens(s):
    return {w for w in re.findall(r"[가-힣A-Za-z0-9]{2,}",(s or "").lower()) if w not in {"기사","관련","시장","업계","기업","최근","오늘","국내","사업","계획"}}

def similarity(a,b):
    aa,bb=tokens(a),tokens(b)
    return len(aa&bb)/max(1,len(aa|bb))

def target_hits(s):
    t=(s or "").lower();out=[]
    for name,_ in TARGETS:
        if any(a.lower() in t for a in ALIASES.get(name,(name,))):
            out.append(name)
    return list(dict.fromkeys(out))

def beat_for(s):
    for name,beat in TARGETS:
        if any(a.lower() in (s or "").lower() for a in ALIASES.get(name,(name,))):
            return beat
    return "정책·통상"

def domain_for(url):
    host=urllib.parse.urlparse(url or "").netloc.lower().split(":")[0]
    for domain,label in OFFICIAL_DOMAINS.items():
        if host==domain or host.endswith("."+domain):return label,True
    return "",False

def google_rss(category,query,max_items=8):
    url="https://news.google.com/rss/search?q="+urllib.parse.quote(query)+"&hl=ko&gl=KR&ceid=KR:ko"
    try:root=ET.fromstring(get(url))
    except Exception:return []
    cutoff=datetime.now(KST)-timedelta(days=14);out=[]
    site_match=re.search(r"site:([A-Za-z0-9.-]+)",query,re.I)
    site=site_match.group(1).lower() if site_match else ""
    for item in root.findall("./channel/item"):
        title=(item.findtext("title") or "").strip();link=(item.findtext("link") or "").strip();pub=item.findtext("pubDate") or ""
        desc=clean(item.findtext("description") or "");src=item.find("source");source=(src.text or "").strip() if src is not None else ""
        if not title or not link:continue
        dt=parse_dt(pub)
        if dt<cutoff:continue
        label,domain_official=domain_for(link)
        out.append({
            "category":category,"title":title,"url":link,"published":dt.isoformat(),
            "sourceName":source or label or "Google News","summary":desc[:2000],
            "official":bool(site or domain_official),"officialLabel":label or (OFFICIAL_DOMAINS.get(site) if site else ""),
            "querySite":site
        })
        if len(out)>=max_items:break
    return out

def newsroom_matches(title,data):
    out=[]
    for row in data:
        if row.get("global"):continue
        sim=similarity(title,(row.get("title") or "")+" "+(row.get("summary") or ""))
        if sim>=0.36:out.append((sim,row))
    out.sort(key=lambda z:z[0],reverse=True)
    return [r for _,r in out[:8]]

def coverage_search(x):
    q=(x.get("title") or "").strip()
    if len(q)<8:return []
    q=re.sub(r"\s*[-|｜].*$","",q)
    companies=target_hits(q)
    nums=NUM_RE.findall(q+" "+x.get("summary",""))
    words=[w for w in re.findall(r"[가-힣A-Za-z0-9]{2,}",q) if w not in {"정책","사업","결정","주요","사항","관련","전체"}]
    phrase=" ".join(words[:10])
    if companies:phrase=companies[0]+" "+phrase
    if nums:phrase+=" "+" ".join(nums[:2])
    return [h for h in google_rss("coverage",f'"{phrase}"',max_items=8) if not h.get("official") and h.get("sourceName") not in {"Google News"}]

def fetch_dart_document(receipt):
    key=os.environ.get("DART_API_KEY","").strip()
    if not key or not receipt:return ""
    try:
        u="https://opendart.fss.or.kr/api/document.xml?"+urllib.parse.urlencode({"crtfc_key":key,"rcept_no":receipt})
        raw=get(u,30)
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            chunks=[]
            for name in z.namelist()[:10]:
                if not name.lower().endswith((".xml",".html",".htm",".txt")):continue
                txt=clean(z.read(name).decode("utf-8",errors="ignore"))
                if txt:chunks.append(txt)
            return " ".join(chunks)[:16000]
    except Exception:return ""

def dart_fact(d,numeric_rows):
    nr=next((r for r in numeric_rows if r.get("receiptNo")==d.get("receiptNo")),None)
    context="";nums=[]
    if nr:
        nums=list(dict.fromkeys(nr.get("numbers") or []))
        context=" ".join(s.get("context","") for s in nr.get("snippets",[])[:2])
    document=fetch_dart_document(d.get("receiptNo"))
    return (context+" "+document).strip(),nums

def dart_title(corp,report,blob,nums):
    amounts=[str(n) for n in nums if re.search(r"(조원|억원|만원|달러|USD|EUR)$",str(n))]
    if "회사분할" in report:
        if "자동차용 램프" in blob:return f"{corp}, 자동차용 램프 사업부문 물적분할"
        return f"{corp}, 사업부문 물적분할 결정"
    if "생산중단" in report or "영업정지" in report:
        if "10일의 조업정지 처분을 취소" in blob:return f"{corp}, 석포제련소 10일 조업정지 처분 취소"
        return f"{corp}, 생산중단 관련 새 결정"
    if "신규시설투자" in report or "시설투자" in report:
        target=re.search(r"투자대상\s+([^0-9]{2,100}?)(?:\s+2\.|\s+투자내역)",blob)
        what=target.group(1).strip() if target else "생산시설"
        return f"{corp}, {what} {amounts[0]+' ' if amounts else ''}증설 투자".strip()
    if "타법인주식및출자증권취득결정" in report:
        target=re.search(r"발행회사\s+회사명\s+([^0-9]{2,100}?)(?:\s+국적|\s+대표자)",blob)
        what=target.group(1).strip() if target else "타법인"
        return f"{corp}, {what} 지분 취득" + (f"…{amounts[0]}" if amounts else "")
    if "단일판매" in report or "공급계약" in report:
        return f"{corp}, 신규 공급계약 공시" + (f"…{amounts[0]}" if amounts else "")
    if any(k in report for k in ("대표이사","임원","이사선임")):
        if "대표이사" in blob:return f"{corp}, 대표이사 인사 변경"
        return f"{corp}, 임원 인사 변경"
    return f"{corp}, {report}"

def candidate_kind(title,category):
    t=(title or "").lower()
    if any(w in t for w in ("대표이사","임원","이사","선임","취임","퇴임","인사","조직개편","경영진")):return "인사"
    if any(w in t for w in ("특허","출원","등록","patent")):return "특허·기술"
    if any(w in t for w in ("관세","반덤핑","덤핑","통상","tariff","customs")):return "통상·관세"
    if any(w in t for w in ("법안","고시","시행","규제","정책","세제","입법")):return "정책·규제"
    if any(w in t for w in ("발주","입찰","조달")):return "조달·발주"
    if any(w in t for w in ("매각","철수","分할","분할","합병","인수","출자","법인")):return "사업재편"
    if any(w in t for w in ("투자","증설","공장","생산","가동")):return "신사업·투자"
    if any(w in t for w in ("수주","계약","공급","납품")):return "계약·수주"
    return category or "기업 원자료"

def build_pitch(x,kind,companies,numbers):
    base=re.sub(r"\s*[-|｜].*$","",(x.get("title") or "")).strip()
    if kind=="인사":
        return f"{base}…인선 배경과 담당 사업이 변수","인사 원문에서 직책·담당 사업·전임자와의 차이를 확인하고 최근 조직·투자 변화와 연결"
    if kind=="특허·기술":
        return f"{base}…실제 적용·양산 시점이 관건","특허 원문에서 출원번호·청구항·적용 제품을 확인해 단순 특허 소개를 넘어 사업화 여부를 취재"
    if kind=="정책·규제":
        return f"{base}…현장에 달라지는 규정은","최종 고시·법안에서 시행일·대상·예외 조항을 확인하고 출입처별 실제 대응을 교차 확인"
    if kind=="통상·관세":
        return f"{base}…국내 기업 수출전략 변수","최종 판정·시행 조건을 실제 출하·계약에 대입해 국내 기업별 영향과 대응을 확인"
    if kind=="조달·발주":
        return f"{base}…새로 생기는 발주 물량은","입찰·발주 원문에서 예산·물량·납기·참여사를 확인해 실제 수요를 취재"
    if kind=="사업재편":
        return f"{base}…줄이는 사업·키우는 사업은","공시 원문에서 사업 목적·자산·법인 변화를 확인하고 기존 계획과 달라진 점을 취재"
    if kind=="신사업·투자":
        return f"{base}…기존 계획과 다른 점은","투자액·대상·가동 시점·생산능력을 확인하고 기존 계획 대비 변화 여부를 취재"
    if kind=="계약·수주":
        return f"{base}…고객사·물량·기간은","계약 원문에서 고객사·물량·기간·단가·생산능력을 확인해 후속 수주 가능성을 취재"
    return f"{base}…새로 확인된 변화","원문 숫자와 담당 조직을 확인하고 출입처에서 실제 변화를 교차 확인"

def main():
    data=json.loads(DATA.read_text(encoding="utf-8")) if DATA.exists() else []
    dart=json.loads(DART.read_text(encoding="utf-8")).get("items",[]) if DART.exists() else []
    numeric=json.loads(NUM.read_text(encoding="utf-8")).get("items",[]) if NUM.exists() else []
    archive=json.loads(ARCHIVE.read_text(encoding="utf-8")) if ARCHIVE.exists() else []
    now=datetime.now(KST)
    primary=[]

    for category,query in PRIMARY_QUERY_SETS:
        for x in google_rss(category,query,max_items=8):
            if x.get("official"):primary.append(x)

    for d in dart:
        report=str(d.get("reportName") or "")
        if not report:continue
        ddt=parse_dt(d.get("date",""))
        if ddt<now-timedelta(days=14):continue
        material=any(k in report for k in ("회사분할","영업정지","생산중단","신규시설투자","타법인주식및출자증권취득결정","단일판매ㆍ공급계약체결","유상증자","영업양수도","합병","대표이사","임원","이사선임"))
        if ("기재정정" in report or "첨부정정" in report) and not material:continue
        if not HARD_SIGNAL_RE.search(report):continue
        blob,nums=dart_fact(d,numeric)
        primary.append({
            "category":"공시","title":dart_title(d.get("corpName",""),report,blob,nums),
            "url":d.get("url",""),"published":ddt.isoformat(),"sourceName":"DART","summary":(d.get("signalText","")+" "+blob)[:7000],
            "official":True,"officialLabel":"DART","receiptNo":d.get("receiptNo"),"dartNumbers":nums,"rawReport":report
        })

    candidates=[];seen=set()
    for x in sorted(primary,key=lambda z:z.get("published",""),reverse=True):
        title=(x.get("title") or "").strip();joined=title+" "+x.get("summary","")
        if not title or NOISE_RE.search(title) or WEAK_RE.search(title):continue
        if not HARD_SIGNAL_RE.search(joined):continue
        if not TOPIC_RE.search(joined) and x.get("category") not in {"공시"}:continue
        companies=target_hits(joined)
        numbers=list(dict.fromkeys((x.get("dartNumbers") or [])+NUM_RE.findall(joined)))[:8]
        if not companies and not numbers and x.get("category") not in {"정책·규제","특허·기술","통상·해외"}:continue

        newsroom=newsroom_matches(title,data)
        coverage=coverage_search(x)
        if coverage:continue
        # An exact newsroom match means we already have the item.
        if any(similarity(title,r.get("title",""))>=0.62 for r in newsroom):continue

        kind=candidate_kind(title,x.get("category",""))
        # Generic KIPRIS/DART document headings without a business fact are not leads.
        meaningful=len(target_hits(joined))>0 or bool(numbers) or bool(re.search(r"자동차용 램프|패키지기판|석포제련소|생산시설|데이터센터|전력망|해상풍력|ESS|자율주행",joined,re.I))
        if not meaningful:continue

        score=52
        score+=22 if x.get("official") else 0
        score+=16 if not coverage else 0
        score+=12 if companies else 0
        score+=10 if numbers else 0
        score+=8 if kind=="인사" else 0
        score+=6 if kind in {"특허·기술","정책·규제","사업재편","신사업·투자"} else 0
        score=min(99,score)

        key=re.sub(r"[^가-힣A-Za-z0-9]","",title.lower())[:180]
        if key in seen:continue
        seen.add(key)
        pitch,angle=build_pitch(x,kind,companies,numbers)

        questions={
            "인사":["선임·퇴임의 정확한 발령일과 새 직책은 무엇인가?","최근 해당 사업의 투자·수주·조직 변화와 맞물리는가?","회사에 인선 배경과 담당 범위를 확인할 수 있는가?"],
            "특허·기술":["특허 출원일·출원번호·핵심 청구항은 무엇인가?","기존 기술과 무엇이 달라졌으며 실제 적용 제품은 무엇인가?","양산·상용화 계획이 회사 내부에서 잡혀 있는가?"],
            "정책·규제":["최종 고시·법안 원문과 시행일은 무엇인가?","기존 제도와 달라진 조항은 정확히 무엇인가?","출입처 기업들의 실제 대응은 무엇인가?"],
            "사업재편":["기존 사업계획과 비교해 실제로 무엇이 달라졌는가?","분할·매각·투자 대상 사업의 자산과 인력은 어떻게 바뀌는가?","회사에서 밝히지 않은 후속 일정은 무엇인가?"]
        }.get(kind,["원문에 적힌 금액·직책·계약조건을 다시 확인했는가?","동일 사실을 다룬 언론 기사가 정말 없는가?","출입처에서 실제 물량·생산·투자·조직 변화로 확인되는가?"])

        evidence=[{"source":x.get("sourceName"),"label":x.get("officialLabel") or x.get("sourceName"),"title":x.get("title"),"url":x.get("url"),"published":x.get("published")}]
        history=[]
        for r in archive:
            if similarity(title,r.get("title",""))>=0.42:
                history.append({"title":r.get("title"),"source":r.get("sourceName"),"published":r.get("published")})
                if len(history)>=3:break

        candidates.append({
            "id":hashlib.sha1((x.get("url","")+"|"+title).encode()).hexdigest()[:12],
            "kind":kind,"beat":beat_for(joined),"title":title,"score":score,"status":"미보도 확인중",
            "originalSource":x.get("officialLabel") or x.get("sourceName"),"originalSourceUrl":x.get("url"),"original":True,
            "coverageCount":0,"coverageSources":[],"newsroomMatches":[{"source":r.get("sourceName"),"title":r.get("title"),"published":r.get("published")} for r in newsroom[:4]],
            "why":f"{x.get('officialLabel') or x.get('sourceName')} 원자료에서 확인된 신호입니다. 현재 검색권에서 동일 내용을 보도한 매체가 확인되지 않아 선점 취재 가치가 있습니다.",
            "whatConfirmed":x.get("title"),"pitch":pitch,"angle":angle,"numbers":numbers,"companies":companies,
            "sources":evidence,"history":history,"questions":questions,
            "firstSeenAt":x.get("published"),"firstSeenSource":x.get("officialLabel") or x.get("sourceName"),
            "verification":"원문·회사 확인 후 단독 확정"
        })

    candidates.sort(key=lambda z:(z["score"],z["kind"]=="인사",bool(z["numbers"]),len(z["companies"])),reverse=True)
    old={}
    if OUT.exists():
        try:old={x.get("id"):x for x in json.loads(OUT.read_text(encoding="utf-8")).get("items",[])}
        except Exception:old={}
    for c in candidates:
        if c["id"] in old:
            c["status"]=old[c["id"]].get("status",c["status"]);c["note"]=old[c["id"]].get("note","");c["checkedCount"]=int(old[c["id"]].get("checkedCount",0))+1
        else:c["checkedCount"]=1
    final=candidates[:40]
    payload={
        "generatedAt":now.isoformat(),"windowDays":14,"mode":"primary-source-first",
        "counts":{"primaryHits":len(primary),"candidates":len(final),"uncovered":len(final),"alreadyCoveredOne":0,"beats":len(set(x["beat"] for x in final))},
        "items":final,
        "note":"단독 후보는 언론 기사를 재수집하지 않습니다. DART·정부·조달·특허·기업 원자료를 먼저 찾아 같은 사실의 언론 보도 여부를 다시 검색한 뒤 미보도 후보만 남깁니다."
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    print(f"primary-source scoop scout: {len(primary)} primary hits -> {len(final)} unreported candidates")

if __name__=="__main__":main()
