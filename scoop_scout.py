from __future__ import annotations

import hashlib
import html
import json
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
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
 "두산에너빌리티":("두산에너빌리티",),"포스코":("포스코","POSCO"),"현대제철":("현대제철","Hyundai Steel")
}
OFFICIAL_DOMAINS={
 "motie.go.kr":"산업부","molit.go.kr":"국토부","ftc.go.kr":"공정위","kostat.go.kr":"통계청",
 "korea.kr":"정부","moef.go.kr":"기재부","customs.go.kr":"관세청","me.go.kr":"환경부","kma.go.kr":"기상청",
 "k-startup.go.kr":"중기부","mss.go.kr":"중기부","g2b.go.kr":"조달청","kipris.or.kr":"특허청·KIPRIS",
 "kipo.go.kr":"특허청","fss.or.kr":"금감원·DART","dart.fss.or.kr":"DART",
 "nhtsa.gov":"NHTSA","ustr.gov":"USTR","trade.gov":"미 상무부","ec.europa.eu":"EU 집행위","europa.eu":"EU",
 "sec.gov":"SEC","epa.gov":"EPA","energy.gov":"미 에너지부","bis.gov":"BIS"
}
COMPANY_DOMAINS={
 "현대차":"hyundai.com","기아":"kia.com","현대모비스":"mobis.com","포스코":"posco.com","포스코홀딩스":"posco-inc.com",
 "현대제철":"hyundai-steel.com","고려아연":"koreazinc.co.kr","LS ELECTRIC":"ls-electric.com","HD현대일렉트릭":"hdelectric.com",
 "효성중공업":"hyosungheavyindustries.com","LS전선":"lscns.com","대한전선":"taekyung.com","두산에너빌리티":"doosanenerbility.com",
 "GS칼텍스":"gscaltex.com","한화솔루션":"hanwhasolutions.com","LG화학":"lgchem.com","롯데케미칼":"lottechem.com"
}
NOISE_RE=re.compile(r"주가|증권|목표주가|급등|급락|관련주|테마주|특징주|장중|종목|추천주|리포트",re.I)
WEAK_RE=re.compile(r"사회공헌|기부|봉사|채용|수상|캠페인|축제|전시|세미나|포럼|강연|홍보대사",re.I)
ACTION_RE=re.compile(r"정책|규제|시행|법안|고시|입법|관세|반덤핑|특허|출원|등록|대표이사|임원|사내이사|사외이사|선임|퇴임|조직개편|신설|투자|출자|증설|공장|법인|합병|분할|인수|매각|철수|수주|계약|공급|발주|입찰|생산|가동|감산|가격|원가|마진|배터리|ESS|HVDC|변압기|해저케이블|해상풍력|자율주행|리콜",re.I)
NUM_RE=re.compile(r"(?<!\d)(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?:조원|억원|만원|달러|만대|천대|대|명|%|GWh|MWh|kWh|톤|km|MW|GW)(?!\w)",re.I)
PRIMARY_QUERY_SETS=[
 ("정책·규제","site:motie.go.kr (자동차 OR 철강 OR 전력 OR 배터리 OR ESS OR 관세 OR 통상)"),
 ("정책·규제","site:molit.go.kr (자동차 OR 자율주행 OR 전기차 OR 리콜)"),
 ("정책·규제","site:ftc.go.kr (기업결합 OR 부당지원 OR 담합 OR 인수 OR 분할 OR 합병)"),
 ("정책·규제","site:customs.go.kr (철강 OR 자동차 OR 배터리 OR 관세 OR 반덤핑 OR 통관)"),
 ("정책·규제","site:moef.go.kr (세제 OR 투자 OR 산업 OR 자동차 OR 에너지)"),
 ("정책·규제","site:me.go.kr (탄소 OR 배출권 OR 재생에너지 OR 산업)"),
 ("조달·발주","site:g2b.go.kr (변압기 OR HVDC OR ESS OR 전력망 OR 철강 OR 자동차)"),
 ("특허·기술","site:kipris.or.kr (현대차 OR 기아 OR 현대모비스 OR 포스코 OR LS ELECTRIC) (특허 OR 출원 OR 등록)"),
 ("통상·해외","site:ustr.gov (automotive OR steel OR battery OR tariff OR Korea)"),
 ("통상·해외","site:trade.gov (steel OR automotive OR battery OR Korea OR tariff)"),
 ("통상·해외","site:ec.europa.eu (steel OR automotive OR battery OR Korean)"),
]
for company,domain in COMPANY_DOMAINS.items():
    PRIMARY_QUERY_SETS.append(("기업 원자료",f"site:{domain} ({company} OR investment OR contract OR plant OR patent OR executive OR appointment)"))

def get(url,timeout=15):
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 NewsroomScoopScout/2.0","Accept":"application/rss+xml,application/xml,text/xml,*/*"})
    with urllib.request.urlopen(req,timeout=timeout) as r:return r.read()

def clean(s):
    s=html.unescape(s or "")
    s=re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>"," ",s,flags=re.I|re.S)
    return re.sub(r"\s+"," ",s).strip()

def parse_dt(raw):
    try:
        d=parsedate_to_datetime(str(raw))
        return d.astimezone(KST) if d.tzinfo else d.replace(tzinfo=KST)
    except Exception:
        try:
            d=datetime.fromisoformat(str(raw).replace("Z","+00:00"))
            return d if d.tzinfo else d.replace(tzinfo=KST)
        except Exception:
            return datetime.min.replace(tzinfo=KST)

def tokens(s):
    return {w for w in re.findall(r"[가-힣A-Za-z0-9]{2,}",(s or "").lower()) if w not in {"기사","관련","시장","업계","기업","최근","오늘","국내","사업","계획"}}

def similarity(a,b):
    aa,bb=tokens(a),tokens(b)
    return len(aa&bb)/max(1,len(aa|bb))

def target_hits(s):
    t=(s or "").lower(); out=[]
    for name,_ in TARGETS:
        if any(alias.lower() in t for alias in ALIASES.get(name,(name,))):
            out.append(name)
    return list(dict.fromkeys(out))

def beat_for(s):
    for name,beat in TARGETS:
        if any(alias.lower() in (s or "").lower() for alias in ALIASES.get(name,(name,))):
            return beat
    return "정책·통상"

def domain_for(url):
    host=urllib.parse.urlparse(url or "").netloc.lower().split(":")[0]
    for domain,label in OFFICIAL_DOMAINS.items():
        if host==domain or host.endswith("."+domain):
            return label,True
    return "",False

def google_rss(category,query,max_items=8):
    url="https://news.google.com/rss/search?q="+urllib.parse.quote(query)+"&hl=ko&gl=KR&ceid=KR:ko"
    try:root=ET.fromstring(get(url))
    except Exception:return []
    cutoff=datetime.now(KST)-timedelta(days=7);out=[]
    for item in root.findall("./channel/item"):
        title=(item.findtext("title") or "").strip();link=(item.findtext("link") or "").strip();pub=item.findtext("pubDate") or ""
        desc=clean(item.findtext("description") or ""); src=item.find("source"); source=(src.text or "").strip() if src is not None else ""
        if not title or not link:continue
        dt=parse_dt(pub)
        if dt<cutoff:continue
        official_label,official=domain_for(link)
        out.append({
            "category":category,"title":title,"url":link,"published":dt.isoformat(),"sourceName":source or official_label or "Google News",
            "summary":desc[:1200],"official":official or bool(official_label),"officialLabel":official_label
        })
        if len(out)>=max_items:break
    return out

def bad_secondary(x):
    t=(x.get("title") or "")+" "+(x.get("summary") or "")
    return bool(NOISE_RE.search(t) or WEAK_RE.search(t) or x.get("sourceName") in {"Google News"})

def newsroom_matches(title,data):
    matches=[]
    for row in data:
        if row.get("global"):continue
        sim=similarity(title,row.get("title","")+" "+row.get("summary",""))
        if sim>=0.38:
            matches.append((sim,row))
    matches.sort(key=lambda z:z[0],reverse=True)
    return [r for _,r in matches[:8]]

def candidate_kind(title,category):
    t=(title or "").lower()
    if any(w in t for w in ("대표이사","임원","이사","선임","퇴임","인사","조직개편","경영진")):return "인사"
    if any(w in t for w in ("특허","출원","등록","patent")):return "특허·기술"
    if any(w in t for w in ("관세","반덤핑","덤핑","통상","tariff","customs")):return "통상·관세"
    if any(w in t for w in ("법안","고시","시행","규제","정책","세제","입법")):return "정책·규제"
    if any(w in t for w in ("발주","입찰","조달")):return "조달·발주"
    if any(w in t for w in ("매각","철수","분할","합병","인수","출자","법인")):return "사업재편"
    if any(w in t for w in ("투자","증설","공장","생산","가동")):return "신사업·투자"
    if any(w in t for w in ("수주","계약","공급","납품")):return "계약·수주"
    return category

def quality(title,summary,official,news_matches,kind):
    t=(title+" "+summary)
    score=48
    if official:score+=25
    if target_hits(t):score+=12
    if NUM_RE.search(t):score+=10
    if ACTION_RE.search(t):score+=8
    if len(news_matches)==0:score+=18
    elif len(news_matches)<=1:score+=8
    if kind=="인사":score+=6
    if kind in {"특허·기술","정책·규제","사업재편","신사업·투자"}:score+=5
    return min(99,score)

def build_pitch(x,kind,companies,numbers):
    base=re.sub(r"\s*[-|｜].*$","",x["title"]).strip()
    c=companies[0] if companies else "업계"
    if kind=="인사":
        pitch=f"{base}…새 직책·사업 역할에 변화"
        angle="원문 인사 공지에서 직책·담당사업·전임자와의 차이를 확인하고 최근 투자·조직 변화와 연결"
    elif kind=="특허·기술":
        pitch=f"{base}…실제 적용 제품·양산 시점이 관건"
        angle="특허 원문에서 청구항·적용 제품·출원 시점과 기존 기술을 확인해 사업화 여부를 취재"
    elif kind=="정책·규제":
        pitch=f"{base}…기업 현장에 미칠 변화는"
        angle="고시·법안 원문에서 시행 시점·대상·예외를 확인하고 출입처별 대응을 교차 확인"
    elif kind=="통상·관세":
        pitch=f"{base}…국내 기업 수출전략 변수"
        angle="최종 판정·시행 조건을 실제 출하·계약에 대입해 국내 기업별 영향과 대응을 확인"
    elif kind=="조달·발주":
        pitch=f"{base}…실제 발주 물량과 참여사는"
        angle="입찰·계약 원문에서 예산·물량·납기·참여업체를 확인해 시장에 새로 생기는 수요를 취재"
    elif kind=="사업재편":
        pitch=f"{base}…줄이는 사업·키우는 사업은"
        angle="공시 원문에서 자산·법인·사업 목적 변화를 확인하고 기존 사업계획과 달라진 점을 취재"
    elif kind=="신사업·투자":
        pitch=f"{base}…기존 계획과 달라진 투자 규모는"
        angle="공시·기업 원문에서 투자액·생산능력·가동 시점을 확인하고 기존 계획 대비 증감 여부를 취재"
    elif kind=="계약·수주":
        pitch=f"{base}…계약 규모와 실제 물량은"
        angle="계약 원문에서 고객사·물량·기간·단가·생산능력을 확인해 후속 수주 가능성을 취재"
    else:
        pitch=f"{base}…추가 확인이 필요한 변화"
        angle="원문에서 숫자·시행일·담당조직을 확인하고 출입처에서 실제 변화를 교차 확인"
    return pitch,angle

def main():
    data=json.loads(DATA.read_text(encoding="utf-8")) if DATA.exists() else []
    archive=json.loads(ARCHIVE.read_text(encoding="utf-8")) if ARCHIVE.exists() else []
    dart=json.loads(DART.read_text(encoding="utf-8")).get("items",[]) if DART.exists() else []
    numeric=json.loads(NUM.read_text(encoding="utf-8")).get("items",[]) if NUM.exists() else []
    now=datetime.now(KST)
    primary=[]

    # 1) Primary web sources: government, regulators, public procurement, KIPRIS and company original sites.
    for category,query in PRIMARY_QUERY_SETS:
        for x in google_rss(category,query,max_items=6):
            if x.get("official"):primary.append(x)

    # 2) DART: primary disclosure layer. DART items are not secondary news and are
    # scored independently of media coverage.
    for d in dart:
        report=str(d.get("reportName") or "")
        if not report or d.get("date","")< (now-timedelta(days=14)).strftime("%Y%m%d"):
            continue
        if not ACTION_RE.search(report):
            continue
        primary.append({
            "category":"공시",
            "title":f"{d.get('corpName','')} {report}",
            "url":d.get("url",""),
            "published":parse_dt(d.get("date","")).isoformat(),
            "sourceName":"DART",
            "summary":d.get("signalText",""),
            "official":True,
            "officialLabel":"DART",
            "receiptNo":d.get("receiptNo")
        })

    # A primary fact is useful only when the same fact is absent from the newsroom DB.
    candidates=[]; seen=set()
    for x in sorted(primary,key=lambda z:z.get("published",""),reverse=True):
        title=x.get("title","").strip()
        if not title:continue
        key=re.sub(r"[^가-힣A-Za-z0-9]","",title.lower())[:180]
        if key in seen:continue
        seen.add(key)
        if bad_secondary(x):continue

        own= news = newsroom_matches(title,data)
        # DART/company/government wording can differ materially from article wording,
        # so a lower semantic threshold is used; two or more matching articles means
        # the fact is already publicly covered and is not a scoop candidate.
        if len(news)>=2:
            continue

        joined=title+" "+x.get("summary","")
        companies=target_hits(joined)
        numbers=list(dict.fromkeys(NUM_RE.findall(joined)))[:8]
        if not companies and not numbers and not ACTION_RE.search(joined):
            continue

        kind=candidate_kind(title,x.get("category",""))
        score=quality(title,x.get("summary",""),bool(x.get("official")),news,kind)
        if len(news)==1:score-=18
        if not x.get("official"):score-=30
        if kind=="인사" and not re.search(r"선임|취임|퇴임|대표이사|임원|이사|조직",title,re.I):
            continue
        if score<65:continue

        pitch,angle=build_pitch(x,kind,companies,numbers)
        questions=[
            "원문에 적힌 시행일·금액·직책·계약조건을 확인했는가?",
            "아이뉴스24와 타 매체에서 같은 사실을 이미 보도했는가?",
            "출입처에서 실제 생산·투자·수주·조직 변화로 확인되는가?"
        ]
        if kind=="인사":
            questions=[
                "선임·퇴임의 정확한 발령일과 새 직책은 무엇인가?",
                "최근 해당 사업의 투자·수주·조직 변화와 맞물리는가?",
                "회사에 인선 배경과 담당 범위를 확인할 수 있는가?"
            ]
        elif kind=="특허·기술":
            questions=[
                "특허 출원일·출원번호·핵심 청구항은 무엇인가?",
                "기존 기술과 무엇이 달라졌으며 실제 적용 제품은 무엇인가?",
                "양산·상용화 계획이 회사 내부에서 잡혀 있는가?"
            ]
        elif kind=="정책·규제":
            questions=[
                "최종 고시·법안 원문과 시행일은 무엇인가?",
                "기존 제도와 달라진 조항은 정확히 무엇인가?",
                "포스코·현대차·LS 등 출입처의 실제 대응은 무엇인가?"
            ]
        evidence=[{
            "source":x.get("sourceName","원자료"),
            "label":x.get("officialLabel") or x.get("sourceName"),
            "title":x.get("title",""),
            "url":x.get("url"),
            "published":x.get("published")
        }]
        for row in news[:3]:
            evidence.append({"source":row.get("sourceName"),"label":"기존 기사","title":row.get("title"),"url":row.get("url"),"published":row.get("published")})
        history=[]
        for row in archive:
            if similarity(title,row.get("title",""))>=0.42:
                history.append({"title":row.get("title"),"source":row.get("sourceName"),"published":row.get("published")})
                if len(history)>=3:break
        candidates.append({
            "id":hashlib.sha1((x.get("url","")+"|"+title).encode()).hexdigest()[:12],
            "kind":kind,
            "beat":beat_for(joined),
            "title":re.sub(r"\s*[-|｜].*$","",title).strip(),
            "score":score,
            "status":"미보도 확인중",
            "originalSource":x.get("officialLabel") or x.get("sourceName"),
            "originalSourceUrl":x.get("url"),
            "original":True,
            "coverageCount":len(news),
            "coverageSources":list(dict.fromkeys(r.get("sourceName") for r in news if r.get("sourceName"))),
            "why":f"{x.get('officialLabel') or x.get('sourceName')} 원자료에서 잡힌 신호입니다. 현재 기사 DB에서 동일 사실의 보도 {len(news)}건이 확인돼, 추가 취재 전 선점 여부를 확인할 가치가 있습니다.",
            "whatConfirmed":x.get("title"),
            "pitch":pitch,
            "angle":angle,
            "numbers":numbers,
            "companies":companies,
            "sources":evidence,
            "history":history,
            "questions":questions,
            "firstSeenAt":x.get("published"),
            "firstSeenSource":x.get("officialLabel") or x.get("sourceName"),
            "verification":"원문 확인 전 단독 확정 금지"
        })

    # Diverse, high-value queue. We deliberately do not fill with ordinary media stories.
    candidates.sort(key=lambda z:(z["score"],z["coverageCount"]==0,bool(z["numbers"]),z["kind"]=="인사"),reverse=True)
    final=[];seen_company_kind=set()
    for x in candidates:
        group=(x["companies"][0] if x["companies"] else x["beat"],x["kind"])
        if group in seen_company_kind and len(final)<10:continue
        seen_company_kind.add(group)
        final.append(x)
        if len(final)>=40:break

    old={}
    if OUT.exists():
        try:old={x.get("id"):x for x in json.loads(OUT.read_text(encoding="utf-8")).get("items",[])}
        except Exception:old={}
    for x in final:
        if x["id"] in old:
            x["status"]=old[x["id"]].get("status",x["status"])
            x["note"]=old[x["id"]].get("note","")
            x["checkedCount"]=int(old[x["id"]].get("checkedCount",0))+1
        else:x["checkedCount"]=1

    payload={
        "generatedAt":now.isoformat(),
        "windowDays":14,
        "mode":"primary-source-first",
        "counts":{
            "primaryHits":len(primary),
            "candidates":len(final),
            "uncovered":sum(1 for x in final if x["coverageCount"]==0),
            "alreadyCoveredOne":sum(1 for x in final if x["coverageCount"]==1),
            "beats":len(set(x["beat"] for x in final))
        },
        "items":final,
        "note":"언론 기사 자체를 단독감으로 올리지 않고 DART·정부·조달·특허·기업 원자료를 먼저 찾아, 동일 사실의 언론 보도 여부를 대조합니다."
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    print(f"primary-source scoop scout: {len(primary)} primary hits -> {len(final)} candidates / uncovered {payload['counts']['uncovered']}")

if __name__=="__main__":
    main()
