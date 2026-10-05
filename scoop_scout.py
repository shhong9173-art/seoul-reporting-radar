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
WEAK_RE=re.compile(r"사회공헌|기부|봉사|채용|수상|캠페인|축제|전시|세미나|포럼|강연|홍보대사|혜택|이벤트|모먼트|스토리|재단|장학|펠로|양궁|칵테일|아트워크|우수조",re.I)
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
    title=(x.get("title") or "").strip()
    if len(title)<8:return []
    joined=title+" "+(x.get("summary") or "")
    companies=target_hits(joined)
    nums=list(dict.fromkeys(NUM_RE.findall(joined)))[:3]
    stop={"정책","사업","결정","주요","사항","관련","전체","상세보기","행정규칙","훈령","예규","고시","기업","회사","신규","공급계약","체결","발표","현황","자동차","산업"}
    raw=[w for w in re.findall(r"[가-힣A-Za-z0-9]{2,}",title) if w not in stop]
    hard=[w for w in raw if re.search(r"물적분할|인적분할|분할|합병|매각|인수|철수|신설|조직개편|대표이사|사내이사|특허|출원|등록|자율주행|공장|증설|투자|수주|계약|공급|관세|반덤핑|리콜|생산|가동|ESS|HVDC|변압기",w,re.I)]
    queries=[]
    if companies:
        queries.append((companies[0]+" "+" ".join(hard[:4] or raw[:5])+" "+" ".join(nums[:2])).strip())
    queries.append(" ".join(raw[:8]))
    out=[];seen=set()
    for q in queries[:2]:
        if len(q)<8:continue
        for h in google_rss("coverage",q,max_items=10):
            if h.get("official") or h.get("sourceName")=="Google News":continue
            key=h.get("url") or (h.get("sourceName","")+"|"+h.get("title",""))
            if key not in seen:
                seen.add(key);out.append(h)
    scored=[]
    for h in out:
        ht=h.get("title") or ""; hs=h.get("summary") or ""
        tsim=similarity(title,ht); ssim=similarity((x.get("summary") or "")[:1600],hs[:1600])
        n1=set(nums); n2=set(NUM_RE.findall(ht+" "+hs))
        act1=set(re.findall(r"수주|계약|공급|투자|증설|공장|생산|가동|감산|철수|매각|인수|분할|합병|특허|출원|등록|선임|취임|퇴임|관세|반덤핑|리콜|자율주행|ESS|HVDC|변압기",title))
        act2=set(re.findall(r"수주|계약|공급|투자|증설|공장|생산|가동|감산|철수|매각|인수|분할|합병|특허|출원|등록|선임|취임|퇴임|관세|반덤핑|리콜|자율주행|ESS|HVDC|변압기",ht+" "+hs))
        same_company=bool(companies) and any(c.lower() in (ht+" "+hs).lower() for c in companies)
        shared_nums=len(n1&n2); shared_actions=len(act1&act2)
        if tsim>=0.52 or (tsim>=0.38 and ssim>=0.22) or (same_company and shared_nums>=1 and shared_actions>=1):
            quality=tsim*65+ssim*20+min(10,shared_nums*5)+min(5,shared_actions*2)+(5 if same_company else 0)
            scored.append((quality,h))
    scored.sort(key=lambda z:z[0],reverse=True)
    return [h for _,h in scored[:8]]

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

def won_amount(blob):
    m=re.search(r"(?:계약금액|투자금액|취득금액|출자금액)\s*\(?원\)?\s+([0-9,]+)",blob)
    if not m:return ""
    try:v=int(m.group(1).replace(",",""))
    except Exception:return ""
    if v>=1000000000000:return f"{v/1e12:.2f}".rstrip("0").rstrip(".")+"조원"
    if v>=100000000:return f"{v/1e8:,.0f}억원"
    if v>=10000:return f"{v/1e4:,.0f}만원"
    return f"{v:,}원"

def near_fact(blob,label):
    m=re.search(re.escape(label)+r"\s+([^\n]{2,100})",blob,re.I)
    return re.sub(r"\s+"," ",m.group(1)).strip() if m else ""

def percent_fact(blob):
    m=re.search(r"매출액대비\(?%\)?\s+([0-9]+(?:\.[0-9]+)?)",blob)
    return (m.group(1)+"%") if m else ""

def dart_title(corp,report,blob,nums):
    amount=won_amount(blob)
    pct=percent_fact(blob)
    if "회사분할" in report:
        if "자동차용 램프" in blob:return f"{corp}, 자동차용 램프 사업부문 물적분할"
        return f"{corp}, 사업부문 물적분할 결정"
    if "생산중단" in report or "영업정지" in report:
        if "10일의 조업정지 처분을 취소" in blob:return f"{corp}, 석포제련소 10일 조업정지 처분 취소"+(f"…매출비중 {pct}" if pct else "")
        return f"{corp}, 생산중단 관련 새 결정"
    if "신규시설투자" in report or "시설투자" in report:
        m=re.search(r"투자대상\s+(.{2,100}?)(?:\s+2\.|\s+투자내역)",blob)
        what=re.sub(r"\s+"," ",m.group(1)).strip() if m else "생산시설"
        return f"{corp}, {what} "+(amount+" " if amount else "")+"증설 투자"
    if "타법인주식및출자증권취득결정" in report:
        m=re.search(r"발행회사\s+회사명\s+(.{2,90}?)(?:\s+국적|\s+대표자)",blob)
        what=re.sub(r"\s+"," ",m.group(1)).strip() if m else "타법인"
        return f"{corp}, {what} 지분 취득"+(f"…{amount}" if amount else "")
    if "단일판매" in report or "공급계약" in report:
        party=near_fact(blob,"계약상대방")
        contract=near_fact(blob,"계약명")
        units=[u for u in nums if re.search(r"(GWh|MWh|km|MW|GW|톤|만대|대)$",str(u),re.I)]
        detail=units[0] if units else ""
        if party and len(party)<45:
            return f"{corp}, {party} 공급계약"+(f" {detail}" if detail else "")+(f"…{amount}" if amount else "")
        if contract and len(contract)<70:
            return f"{corp}, {contract}"+(f"…{amount}" if amount else "")
        return f"{corp}, 신규 공급계약"+(f" {detail}" if detail else "")+(f"…{amount}" if amount else "")
    if any(k in report for k in ("대표이사","임원","이사선임")):return f"{corp}, 경영진 인사 변경"
    if "유상증자" in report:return f"{corp}, 자회사 유상증자 결정"+(f"…{amount}" if amount else "")
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

def source_tier(x):
    label=str(x.get("officialLabel") or x.get("sourceName") or "")
    if label in {"DART","특허청·KIPRIS","특허청","조달청"}: return 3
    if label in {"산업부","국토부","공정위","관세청","기재부","환경부","금감원·DART","USTR","미국 상무부","EU 집행위","EU"}: return 3
    if x.get("category")=="기업 원자료": return 2
    return 1

def extract_person(blob,corp):
    pats=[
        r"성명\\s+([가-힣A-Za-z·]{2,12})[^\\n]{0,80}?(?:직책|직위)\\s+([가-힣A-Za-z·\\s]{2,30})",
        r"([가-힣]{2,5})\\s+(?:대표이사|사장|부사장|전무|상무|부문장|본부장|실장|사내이사|사외이사)",
        r"(?:대표이사|사내이사|사외이사|이사|임원)\\s+([가-힣]{2,5})"
    ]
    for p in pats:
        z=re.search(p,blob,re.I)
        if z:
            vals=[v.strip() for v in z.groups() if v and v.strip()]
            if vals:return " ".join(vals[:2])
    return corp

def relevant_primary(x,companies,kind,joined):
    t=joined.lower()
    if kind in {"특허·기술","인사","사업재편","신사업·투자","계약·수주"}: return bool(companies)
    if kind=="정책·규제":
        terms=("전기차","자동차","차량","자율주행","리콜","배터리","충전","수소차","부품","배출가스","연비","안전기준","형식승인","관세","반덤핑","통상")
        return bool(companies) or any(k in t for k in terms)
    if kind=="조달·발주":
        terms=("변압기","hvdc","전력망","ess","자동차","차량","배터리","충전")
        return bool(companies) and any(k in t for k in terms)
    return bool(companies)

def scoop_headline(x,kind,corp,blob,nums):
    base=(x.get("title") or "").strip()
    if kind=="인사":
        person=extract_person(blob,corp)
        role=next((k for k in ("대표이사","사장","부사장","전무","상무","본부장","부문장","사내이사","사외이사","임원") if k in base+" "+blob),"")
        return f"{corp}, {person} {role} 인사…배경은" if person!=corp else f"{corp}, 경영진 인사 확인…담당 사업은"
    if kind=="특허·기술":
        detail=next((k for k in ("자율주행","로보택시","배터리","충전","로봇","램프","차량","변압기","HVDC","전력망") if k in base+" "+blob),"신기술")
        return f"{corp}, {detail} 특허 새로 확인…양산 적용하나"
    if kind=="정책·규제":
        clean_base=re.sub(r"\\s*[-|｜].*$","",base)
        return f"{clean_base}…자동차 업계에 달라지는 규정은"
    if kind=="사업재편":
        if "물적분할" in base:return f"{corp}, 사업부문 물적분할…분할 대상·향후 사업은"
        return f"{base}…실제 사업재편 내용은"
    if kind=="신사업·투자":return f"{base}…투자 대상·가동 시점은"
    if kind=="계약·수주":
        return f"{corp}, 신규 계약 {nums[0]}…고객사·물량은" if nums else f"{base}…고객사·물량·기간은"
    if kind=="조달·발주":return f"{base}…예산·물량·참여사는"
    return base

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
        material=any(k in report for k in ("회사분할","영업정지","생산중단","신규시설투자","타법인주식및출자증권취득결정","단일판매ㆍ공급계약체결","유상증자","영업양수도","합병","대표이사","임원","이사선임","주요사항보고"))
        if ("기재정정" in report or "첨부정정" in report) and not material:continue
        if not HARD_SIGNAL_RE.search(report):continue
        blob,nums=dart_fact(d,numeric)
        primary.append({
            "category":"공시","title":dart_title(d.get("corpName",""),report,blob,nums),
            "url":d.get("url",""),"published":ddt.isoformat(),"sourceName":"DART",
            "summary":(d.get("signalText","")+" "+blob)[:12000],
            "official":True,"officialLabel":"DART","receiptNo":d.get("receiptNo"),
            "dartNumbers":nums,"rawReport":report
        })

    candidates=[];seen=set()
    for x in sorted(primary,key=lambda z:z.get("published",""),reverse=True):
        title=(x.get("title") or "").strip()
        joined=title+" "+x.get("summary","")
        if not title or NOISE_RE.search(title) or WEAK_RE.search(title):continue
        companies=target_hits(joined)
        numbers=list(dict.fromkeys((x.get("dartNumbers") or [])+NUM_RE.findall(joined)))[:8]
        kind=candidate_kind(title,x.get("category",""))
        if not relevant_primary(x,companies,kind,joined):continue

        newsroom=newsroom_matches(title,data)
        archive_matches=[]
        for r in archive:
            sim=similarity(title,(r.get("title","")+" "+r.get("summary",""))[:2500])
            if sim>=0.44:archive_matches.append((sim,r))
        archive_matches.sort(key=lambda z:z[0],reverse=True)
        if archive_matches and archive_matches[0][0]>=0.58:continue

        coverage=[]
        best_news=max([similarity(title,r.get("title","")+" "+(r.get("summary") or "")) for r in newsroom] or [0])
        if best_news<0.52:coverage=coverage_search(x)

        combined=[]
        for r in newsroom:
            combined.append({"source":r.get("sourceName"),"title":r.get("title"),"published":r.get("published"),"url":r.get("url"),"_sim":similarity(title,r.get("title","")+" "+(r.get("summary") or ""))})
        for r in coverage:
            combined.append({"source":r.get("sourceName"),"title":r.get("title"),"published":r.get("published"),"url":r.get("url"),"_sim":similarity(title,r.get("title","")+" "+(r.get("summary") or ""))})
        combined.sort(key=lambda z:z.get("_sim",0),reverse=True)
        strong=[r for r in combined if r.get("_sim",0)>=0.54]
        if strong:continue

        # Routine contracts are not useful scoop candidates unless they carry a new customer/market,
        # unusual project, large amount, or specific physical quantity.
        if kind=="계약·수주":
            large=any(re.search(r"(조원|억원)",str(n)) and float(re.sub(r"[^0-9.]","",str(n).replace(",","")) or 0)>=1000 for n in numbers)
            unusual=any(k in joined for k in ("첫","최초","북미","미국","유럽","중동","사우디","호주","대규모","장기","독점","신규 고객","신규 고객사","프로젝트"))
            detailed=any(k in joined for k in ("GWh","MWh","MW","GW","km","톤","만대","물량","사업장","지역"))
            if not (large or unusual or detailed):continue

        # A true personnel/patent scoop must originate in an authoritative or company source.
        if kind in {"특허·기술","인사"} and source_tier(x)<2:continue

        age_h=max(0,(now-parse_dt(x.get("published"))).total_seconds()/3600)
        tier=source_tier(x)
        concrete=min(18,len(numbers)*3)
        hard=min(12,sum(1 for k in ("분할","합병","매각","인수","철수","신설","조직개편","대표이사","임원","선임","취임","特許","특허","출원","등록","고시","법안","수주","계약","投资","투자","증설","공장","생산") if k in joined))
        score=42 + tier*8 + concrete + hard + 28
        if kind in {"인사","특허·기술","사업재편","정책·규제"}:score+=9
        if age_h<=24:score+=7
        elif age_h<=72:score+=4
        if not archive_matches:score+=4
        score=min(99,score)

        if score<78:continue
        if not (numbers or kind in {"인사","특허·기술","정책·규제","사업재편"} or any(k in joined for k in ("공장","법인","조직개편","대표이사","특허","고시","법안"))):continue

        corp=companies[0] if companies else "정부"
        headline=scoop_headline(x,kind,corp,x.get("summary") or "",numbers)
        dedup=re.sub(r"[^가-힣A-Za-z0-9]","",headline.lower())
        if dedup in seen:continue
        seen.add(dedup)

        if kind=="인사":
            why=f"DART·원자료에서 경영진/이사 변화를 먼저 포착했습니다. 현재 검색된 국내 보도에서 동일 인선의 강한 매칭이 없어, 직책·담당 사업·인선 배경을 확인할 가치가 있습니다."
        elif kind=="특허·기술":
            why=f"특허 원자료에서 새로운 출원·등록 신호를 포착했습니다. 기존 보도에 없는 기술적 세부와 양산·상용화 연결 여부를 확인할 수 있는 후보입니다."
        elif kind=="정책·규제":
            why=f"정부 원자료에서 자동차 산업에 직접 영향을 줄 수 있는 제도 변화를 포착했습니다. 시행일과 실제 적용 범위를 먼저 확인할 수 있는 후보입니다."
        elif kind=="사업재편":
            why=f"공시 원문에서 사업부문·법인·생산거점의 변화를 포착했습니다. 기존 계획과 달라진 구체적 조건을 확인할 필요가 있습니다."
        else:
            why=f"{x.get('officialLabel') or x.get('sourceName')} 원자료에서 구체적 사업 사실을 포착했습니다. 국내 언론에서 동일 사실의 강한 매칭이 없어 선점 취재 후보로 분류했습니다."

        questions={
            "인사":["정확한 발령일·직책·담당 사업은 무엇인가?","기존 보직과 무엇이 달라졌고 왜 지금 바뀌었나?","최근 해당 사업의 투자·수주·조직 변화와 연결되는가?"],
            "특허·기술":["출원일·출원번호·핵심 청구항은 무엇인가?","기존 기술과 무엇이 달라졌고 실제 적용 제품은 무엇인가?","양산·상용화 계획이나 협력사가 정해져 있는가?"],
            "정책·규제":["최종 고시·법안에서 달라진 조항은 무엇인가?","시행일과 적용 대상 기업·차종·부품은 어디까지인가?","자동차 회사와 부품사가 실제로 바꿔야 하는 절차·비용은 무엇인가?"],
            "사업재편":["분할·매각·신설 대상 사업의 자산과 인력은 어떻게 이동하는가?","기존 계획과 비교해 이번 결정으로 달라지는 사업 범위는 무엇인가?","후속 일정과 생산·투자 변화는 언제 발생하는가?"],
            "신사업·투자":["투자 대상·금액·가동 시점은 무엇인가?","기존 생산능력·사업계획에서 얼마나 달라졌는가?","신규 고객·시장 진입 효과가 있는가?"],
            "계약·수주":["계약 상대방과 프로젝트·지역은 어디인가?","물량·기간·단가와 실제 생산능력 투입 규모는 얼마인가?","이번 계약이 신규 고객 또는 신규 시장 진입을 의미하는가?"],
            "조달·발주":["예산·물량·납기·발주기관은 어디인가?","참여 예상 기업과 낙찰 일정은 언제인가?","기존 계획에 없던 신규 수요인지 확인할 수 있는가?"]
        }.get(kind,["원자료의 핵심 조건은 무엇인가?","동일 사실의 언론 보도가 정말 없는가?","출입처에서 어떤 사실을 전화로 교차확인할 수 있는가?"])

        matches=[{k:v for k,v in r.items() if k!="_sim"} for r in combined[:6] if r.get("source")]
        history=[{"title":r.get("title"),"source":r.get("sourceName"),"published":r.get("published")} for _,r in archive_matches[:3]]
        sources=[{"source":x.get("sourceName"),"label":x.get("officialLabel") or x.get("sourceName"),"title":x.get("title"),"url":x.get("url"),"published":x.get("published")}]

        candidates.append({
            "id":hashlib.sha1((x.get("url","")+"|"+headline).encode()).hexdigest()[:12],
            "kind":kind,"beat":beat_for(joined),"title":headline,"score":score,
            "status":"미보도 유력" if not strong and score>=88 else "미보도 후보",
            "originalSource":x.get("officialLabel") or x.get("sourceName"),
            "originalSourceUrl":x.get("url"),"original":True,
            "coverageCount":len(strong),"coverageSources":[r.get("source") for r in strong if r.get("source")],
            "newsroomMatches":matches,"why":why,"whatConfirmed":x.get("title"),
            "pitch":build_pitch(x,kind,companies,numbers)[0],
            "angle":build_pitch(x,kind,companies,numbers)[1],
            "numbers":numbers,"companies":companies,"sources":sources,"history":history,
            "questions":questions,"firstSeenAt":x.get("published"),
            "firstSeenSource":x.get("officialLabel") or x.get("sourceName"),
            "verification":"원문·출입처 확인 후 단독 확정",
            "evidenceTier":tier,"coverageChecked":True
        })

    kind_rank={"인사":7,"특허·기술":7,"사업재편":6,"정책·규제":6,"신사업·투자":5,"조달·발주":3,"계약·수주":2}
    candidates.sort(key=lambda z:(z["score"],kind_rank.get(z["kind"],1),-z["coverageCount"],len(z.get("numbers") or []),z.get("firstSeenAt","")),reverse=True)

    final=[];used_primary=set();used_keys=set()
    for c in candidates:
        key=(tuple(sorted(c.get("companies") or [])),re.sub(r"[^가-힣A-Za-z0-9]","",c.get("title",""))[:45])
        if key in used_keys:continue
        primary_company=(c.get("companies") or [None])[0]
        if primary_company and primary_company in used_primary and c["score"]<94:continue
        used_keys.add(key)
        if primary_company:used_primary.add(primary_company)
        final.append(c)
        if len(final)>=12:break

    old={}
    if OUT.exists():
        try:old={x.get("id"):x for x in json.loads(OUT.read_text(encoding="utf-8")).get("items",[])}
        except Exception:old={}
    for c in final:
        prev=old.get(c["id"],{})
        c["note"]=prev.get("note","")
        c["checkedCount"]=int(prev.get("checkedCount",0))+1 if prev else 1

    payload={
        "generatedAt":now.isoformat(),"windowDays":14,"mode":"primary-source-first",
        "counts":{
            "primaryHits":len(primary),"candidates":len(final),
            "uncovered":sum(1 for x in final if x.get("coverageCount",0)==0),
            "alreadyCoveredOne":sum(1 for x in final if x.get("coverageCount",0)>0),
            "beats":len(set(x["beat"] for x in final))
        },
        "items":final,
        "note":"단독감은 기존 언론 기사의 중요도를 평가하는 기능이 아닙니다. 원자료에서 새 사실을 먼저 포착하고, 현재 언론·아카이브에 동일 사실이 없을 때만 후보로 올립니다. 인사·특허·정책·사업재편을 우선하며 일반적인 공급계약은 추가성이 없으면 제외합니다."
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    print(f"primary-source scoop scout: {len(primary)} primary hits -> {len(final)} selective unreported candidates")

if __name__=="__main__":main()
