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
 # 자동차
 ("현대차","자동차"),("기아","자동차"),("제네시스","자동차"),("현대모비스","자동차"),("현대위아","자동차"),
 ("HL만도","자동차"),("만도","자동차"),("한국GM","자동차"),("KG모빌리티","자동차"),("메르세데스벤츠코리아","자동차"),
 ("폭스바겐코리아","자동차"),("폭스바겐","자동차"),("BMW코리아","자동차"),("BMW","자동차"),("르노코리아","자동차"),
 ("아우디코리아","자동차"),("아우디","자동차"),("혼다코리아","자동차"),("한국타이어","자동차"),("넥센타이어","자동차"),
 ("금호타이어","자동차"),("현대트랜시스","자동차"),("현대글로비스","자동차"),
 # 철강
 ("포스코홀딩스","철강"),("포스코","철강"),("현대제철","철강"),("KG스틸","철강"),("세아홀딩스","철강"),("세아제강","철강"),
 # 비철
 ("고려아연","비철금속"),("영풍","비철금속"),("LS MnM","비철금속"),
 # 전력기기
 ("HD현대일렉트릭","전력기기"),("LS일렉트릭","전력기기"),("대한전선","전력기기"),("효성중공업","전력기기"),("일진전기","전력기기"),
 # 전선·전력
 ("LS전선","전선·전력"),("LS M&M","전선·전력"),("LS지주","전선·전력"),
 # 에너지
 ("두산에너빌리티","에너지"),("GS","에너지"),("GS칼텍스","에너지"),
 # 풍력·재생에너지
 ("한화솔루션","재생에너지"),("OCI","재생에너지"),("OCI홀딩스","재생에너지"),("씨에스윈드","재생에너지"),
 # 화학·소재
 ("태광","화학·소재"),("동성케미칼","화학·소재"),("DL케미칼","화학·소재"),
 ("LG화학","화학·소재"),("롯데케미칼","화학·소재"),("금호석유화학","화학·소재"),("효성첨단소재","화학·소재"),("코오롱인더","화학·소재"),
 # 협회
 ("한국철강협회","협회·산업단체"),("한국풍력산업협회","협회·산업단체"),("민간LNG산업협회","협회·산업단체"),
 ("대한전기협회","협회·산업단체"),("한국전기산업진흥회","협회·산업단체"),("한국원자력산업협회","협회·산업단체"),
]
ALIASES={
 "현대차":("현대차","현대자동차","Hyundai Motor"),"기아":("기아","기아자동차","Kia"),
 "제네시스":("제네시스","Genesis"),"현대모비스":("현대모비스","Hyundai Mobis"),"현대위아":("현대위아","Hyundai Wia"),
 "HL만도":("HL만도","HL Mando","만도"),"만도":("만도","Mando","HL만도"),"한국GM":("한국GM","GM Korea","쉐보레","Chevrolet"),
 "KG모빌리티":("KG모빌리티","KGM","쌍용자동차"),"메르세데스벤츠코리아":("메르세데스벤츠코리아","메르세데스-벤츠 코리아","Mercedes-Benz Korea"),
 "폭스바겐코리아":("폭스바겐코리아","Volkswagen Korea"),"폭스바겐":("폭스바겐","Volkswagen"),
 "BMW코리아":("BMW코리아","BMW 코리아","BMW Korea"),"BMW":("BMW",),
 "르노코리아":("르노코리아","Renault Korea"),"아우디코리아":("아우디코리아","Audi Korea"),"아우디":("아우디","Audi"),
 "혼다코리아":("혼다코리아","Honda Korea"),"한국타이어":("한국타이어","Hankook Tire","Hankook"),"넥센타이어":("넥센타이어","Nexen Tire"),
 "금호타이어":("금호타이어","Kumho Tire"),"현대트랜시스":("현대트랜시스","Hyundai Transys"),"현대글로비스":("현대글로비스","Hyundai Glovis"),
 "포스코":("포스코","POSCO"),"포스코홀딩스":("포스코홀딩스","POSCO Holdings"),"현대제철":("현대제철","Hyundai Steel"),
 "KG스틸":("KG스틸","KG Steel"),"세아홀딩스":("세아홀딩스","SeAH Holdings"),"세아제강":("세아제강","SeAH Steel"),
 "고려아연":("고려아연","Korea Zinc"),"영풍":("영풍","Young Poong"),"LS MnM":("LS MnM","LS MnM Inc."),
 "HD현대일렉트릭":("HD현대일렉트릭","HD Hyundai Electric"),"LS일렉트릭":("LS일렉트릭","LS ELECTRIC"),
 "대한전선":("대한전선","Taihan Cable"),"효성중공업":("효성중공업","Hyosung Heavy Industries"),"일진전기":("일진전기","Iljin Electric"),
 "LS전선":("LS전선","LS Cable & System"),"LS M&M":("LS M&M","LS MnM"),"LS지주":("LS지주","LS Corp"),
 "두산에너빌리티":("두산에너빌리티","Doosan Enerbility"),"GS":("GS",),"GS칼텍스":("GS칼텍스","GS Caltex"),
 "한화솔루션":("한화솔루션","Hanwha Solutions"),"OCI":("OCI",),"OCI홀딩스":("OCI홀딩스","OCI Holdings"),
 "씨에스윈드":("씨에스윈드","CS Wind"),"태광":("태광","Taekwang"),"동성케미칼":("동성케미칼","Dongsung Chemical"),
 "DL케미칼":("DL케미칼","DL Chemical"),"LG화학":("LG화학","LG Chem"),"롯데케미칼":("롯데케미칼","Lotte Chemical"),
 "금호석유화학":("금호석유화학","Kumho Petrochemical"),"효성첨단소재":("효성첨단소재","Hyosung Advanced Materials"),
 "코오롱인더":("코오롱인더","Kolon Industries"),
 "한국철강협회":("한국철강협회","Korea Iron & Steel Association"),"한국풍력산업협회":("한국풍력산업협회","Korea Wind Energy Association"),
 "민간LNG산업협회":("민간LNG산업협회","Korea Private LNG Industry Association"),"대한전기협회":("대한전기협회","Korea Electric Association"),
 "한국전기산업진흥회":("한국전기산업진흥회","Korea Electrical Manufacturers Association"),"한국원자력산업협회":("한국원자력산업협회","Korea Nuclear Association"),
}
OFFICIAL_DOMAINS={
 "motie.go.kr":"산업부","molit.go.kr":"국토부","ftc.go.kr":"공정위","kostat.go.kr":"통계청","korea.kr":"정부","moef.go.kr":"기재부",
 "customs.go.kr":"관세청","me.go.kr":"환경부","kma.go.kr":"기상청","g2b.go.kr":"조달청","pps.go.kr":"조달청",
 "kipris.or.kr":"특허청·KIPRIS","kipo.go.kr":"특허청","fss.or.kr":"금감원·DART","dart.fss.or.kr":"DART","kind.krx.co.kr":"KIND",
 "car.go.kr":"자동차리콜센터","eiass.go.kr":"환경영향평가","law.go.kr":"법령·입법","lawmaking.go.kr":"입법예고",
 "nhtsa.gov":"NHTSA","epa.gov":"EPA","sec.gov":"SEC","ustr.gov":"USTR","trade.gov":"미 상무부","ec.europa.eu":"EU 집행위","eur-lex.europa.eu":"EU",
 "ids.usitc.gov":"USITC","usitc.gov":"USITC","rulings.cbp.gov":"CBP CROSS","cbp.gov":"CBP","unece.org":"UNECE WP.29",
 "samr.gov.cn":"중국 SAMR","cnca.gov.cn":"중국 인증","j-platpat.inpit.go.jp":"J-PlatPat","safetygate.ec.europa.eu":"EU Safety Gate",
 "seoul.go.kr":"서울시","gg.go.kr":"경기도","investkorea.org":"Invest Korea",
 "hyundai.com":"현대차","kia.com":"기아","mobis.com":"현대모비스","hyundai-wia.com":"현대위아","hlmando.com":"HL만도",
 "gm-korea.co.kr":"한국GM","kg-mobility.com":"KG모빌리티","mercedes-benz.co.kr":"메르세데스벤츠코리아","volkswagen.co.kr":"폭스바겐코리아",
 "bmw.co.kr":"BMW코리아","renault.co.kr":"르노코리아","audi.co.kr":"아우디코리아","honda.co.kr":"혼다코리아",
 "hankooktire.com":"한국타이어","nexentire.com":"넥센타이어","kumhotire.com":"금호타이어",
 "posco.com":"포스코","hyundai-steel.com":"현대제철","seah.co.kr":"세아","koreazinc.co.kr":"고려아연","youngpoong.co.kr":"영풍",
 "ls-electric.com":"LS일렉트릭","taihan.com":"대한전선","hyosung.com":"효성","iljinelectric.co.kr":"일진전기","lscns.co.kr":"LS전선",
 "lscorp.co.kr":"LS지주","doosanenerbility.com":"두산에너빌리티","gscaltex.com":"GS칼텍스","hanwhasolutions.com":"한화솔루션",
 "oci.co.kr":"OCI","oci-holdings.co.kr":"OCI홀딩스","cswind.com":"씨에스윈드","taekwang.com":"태광",
 "dongsungchemical.com":"동성케미칼","dlchem.com":"DL케미칼"
}
COMPANY_DOMAINS={
 "현대차":"hyundai.com","기아":"kia.com","현대모비스":"mobis.com","현대위아":"hyundai-wia.com","HL만도":"hlmando.com",
 "한국GM":"gm-korea.co.kr","KG모빌리티":"kg-mobility.com","메르세데스벤츠코리아":"mercedes-benz.co.kr","폭스바겐코리아":"volkswagen.co.kr",
 "BMW코리아":"bmw.co.kr","르노코리아":"renault.co.kr","아우디코리아":"audi.co.kr","혼다코리아":"honda.co.kr",
 "한국타이어":"hankooktire.com","넥센타이어":"nexentire.com","금호타이어":"kumhotire.com","포스코":"posco.com","현대제철":"hyundai-steel.com",
 "세아홀딩스":"seah.co.kr","고려아연":"koreazinc.co.kr","영풍":"youngpoong.co.kr","LS일렉트릭":"ls-electric.com",
 "대한전선":"taihan.com","두산에너빌리티":"doosanenerbility.com","GS칼텍스":"gscaltex.com","한화솔루션":"hanwhasolutions.com",
 "OCI":"oci.co.kr","OCI홀딩스":"oci-holdings.co.kr","태광":"taekwang.com","동성케미칼":"dongsungchemical.com","DL케미칼":"dlchem.com"
}
NOISE_RE=re.compile(r"주가|증권|목표주가|급등|급락|관련주|테마주|특징주|장중|종목|추천주|리포트",re.I)
WEAK_RE=re.compile(r"사회공헌|기부|봉사|채용|수상|캠페인|축제|전시|세미나|포럼|강연|홍보대사|혜택|이벤트|모먼트|스토리|재단|장학|펠로|양궁|칵테일|아트워크|우수조",re.I)
HARD_SIGNAL_RE=re.compile(r"정책|규제|시행|고시|법안|입법|예고|결정고시|행정처분|관세|반덤핑|상계관세|특허|출원|등록|특허심판|심판|상표|디자인|대표이사|임원|사내이사|사외이사|선임|취임|퇴임|조직개편|신설|투자|출자|증설|공장|법인|합병|분할|인수|매각|철수|수주|계약|공급|발주|입찰|낙찰|생산|가동|감산|가격|원가|마진|배터리|ESS|HVDC|변압기|해저케이블|해상풍력|자율주행|리콜|결함|제작결함|무상수리|조사개시|인증|형식승인|환경영향|환경성평가|건축허가|사업계획승인|산업단지|소송|제소|가처분|판결|행정심판",re.I)
TOPIC_RE=re.compile(r"자동차|전기차|하이브리드|PBV|자율주행|ADAS|타이어|배터리|철강|열연|냉연|후판|강관|비철|구리|아연|니켈|전력|변압기|HVDC|케이블|해저케이블|풍력|태양광|ESS|에너지|LNG|원전|수소|석유화학|화학|소재|공장|수출|관세|산업단지|데이터센터|재생에너지",re.I)
NUM_RE=re.compile(r"(?<!\d)(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?:조원|억원|만원|달러|만대|천대|대|명|%|GWh|MWh|kWh|톤|km|MW|GW)(?!\w)",re.I)

PRIMARY_QUERY_SETS=[
 ("정책·규제","site:motie.go.kr (정책 OR 고시 OR 시행 OR 법안 OR 제도 OR 관세 OR 통상 OR 공급망) (자동차 OR 철강 OR 비철 OR 전력기기 OR 전선 OR LNG OR 원전 OR 수소 OR 풍력 OR 태양광 OR 화학 OR 소재)"),
 ("정책·규제","site:molit.go.kr (고시 OR 시행 OR 입법예고 OR 정책 OR 제도 OR 안전기준 OR 리콜 OR 자동차관리 OR 자율주행) (자동차 OR 차량 OR 타이어 OR 전기차)"),
 ("정책·규제","site:ftc.go.kr (기업결합 OR 인수 OR 합병 OR 분할 OR 담합 OR 부당지원 OR 하도급) (자동차 OR 철강 OR 전력 OR 에너지 OR 화학 OR 소재)"),
 ("정책·규제","site:customs.go.kr (자동차 OR 철강 OR 배터리 OR 부품 OR 구리 OR 알루미늄 OR 전력기기) (관세 OR 반덤핑 OR 통관 OR 원산지 OR 품목분류)"),
 ("정책·규제","site:me.go.kr (배출가스 OR 탄소 OR 배출권 OR 환경영향 OR 화학물질 OR 대기오염 OR 폐기물) (자동차 OR 철강 OR 공장 OR 화학 OR 풍력 OR 태양광 OR LNG OR 수소)"),
 ("정책·규제","site:keco.or.kr (자동차 OR 배터리 OR 폐배터리 OR 탄소 OR 배출권) (기준 OR 인증 OR 규제 OR 회수)"),
 ("정책·규제","site:law.go.kr (자동차 OR 전기차 OR 자율주행 OR 철강 OR 전력 OR HVDC OR LNG OR 원전 OR 풍력 OR 화학) (법령 OR 시행령 OR 시행규칙 OR 고시 OR 입법예고)"),
 ("정책·규제","site:lawmaking.go.kr (자동차 OR 철강 OR 전력 OR 에너지 OR 화학 OR 소재) (입법예고 OR 법령안 OR 일부개정령안)"),
 ("자동차 결함","site:car.go.kr (현대 OR 기아 OR 제네시스 OR 현대모비스 OR 한국GM OR KGM OR 벤츠 OR 폭스바겐 OR BMW OR 르노 OR 아우디 OR 혼다 OR 한국타이어 OR 넥센 OR 금호타이어) (리콜 OR 결함 OR 무상수리 OR 제작결함 OR 신고 OR 조사)"),
 ("자동차 결함","site:car.go.kr (자동차 OR 타이어 OR 전기차) (리콜 OR 결함 OR 무상수리 OR 제작결함 OR 신고)"),
 ("자동차 인증","site:epa.gov (Hyundai OR Kia OR Genesis OR Mercedes OR Volkswagen OR BMW OR Renault OR Audi OR Honda OR automotive) (certificate OR certification OR emissions OR family)"),
 ("자동차 규제","site:nhtsa.gov (Hyundai OR Kia OR Genesis OR Mercedes OR Volkswagen OR BMW OR Renault OR Audi OR Honda) (recall OR investigation OR defect OR petition OR complaint OR manufacturer communication)"),
 ("환경·인허가","site:eiass.go.kr (현대차 OR 기아 OR 포스코 OR 현대제철 OR KG스틸 OR 세아 OR 고려아연 OR 영풍 OR LS OR 두산 OR 한화 OR OCI OR 공장 OR 산업단지) (환경영향평가 OR 환경성평가 OR 사업조회)"),
 ("환경·인허가","site:seoul.go.kr (현대차 OR 기아 OR 포스코 OR LS OR 자동차 OR 철강 OR 전력 OR 에너지 OR 공장) (인허가 OR 건축허가 OR 심의 OR 도시계획 OR 산업 OR 착공 OR 사업계획)"),
 ("환경·인허가","site:gg.go.kr (현대차 OR 기아 OR 포스코 OR 현대제철 OR KG스틸 OR 세아 OR 공장 OR 배터리 OR 전력) (인허가 OR 투자 OR 착공 OR 산업단지 OR 환경영향 OR 심의)"),
 ("환경·인허가","site:investkorea.org (현대차 OR 기아 OR 자동차 OR 철강 OR 전력 OR 에너지 OR 화학 OR 소재 OR 공장) (투자 OR 착공 OR 유치 OR 외투 OR 산업단지)"),
 ("거래소·공시","site:kind.krx.co.kr (현대차 OR 기아 OR 현대모비스 OR 현대위아 OR 만도 OR 한국GM OR KG모빌리티 OR 포스코 OR 현대제철 OR KG스틸 OR 세아 OR 고려아연 OR 영풍 OR LS OR 두산에너빌리티 OR GS OR 한화솔루션 OR OCI OR 태광 OR 동성케미칼 OR DL케미칼) (공시 OR 조회공시 OR 임원 OR 최대주주 OR 자사주 OR 분할 OR 합병 OR 투자 OR 인수 OR 매각)"),
 ("조달·발주","site:g2b.go.kr (자동차 OR 전기차 OR 충전 OR 타이어 OR 철강 OR 변압기 OR HVDC OR ESS OR 전력망 OR 케이블 OR LNG OR 원전 OR 풍력 OR 태양광) (입찰 OR 발주 OR 낙찰 OR 계약 OR 구매 OR 적격심사)"),
 ("조달·발주","site:pps.go.kr (자동차 OR 전기차 OR 철강 OR 변압기 OR HVDC OR 전력기기 OR ESS OR 케이블 OR 원전) (조달 OR 입찰 OR 계약 OR 낙찰)"),
 ("특허·기술","site:kipris.or.kr (현대차 OR 기아 OR 현대모비스 OR 현대위아 OR 만도 OR 한국GM OR KG모빌리티 OR 포스코 OR 현대제철 OR KG스틸 OR 세아 OR 고려아연 OR 영풍 OR LS OR 두산에너빌리티 OR GS칼텍스 OR 한화솔루션 OR OCI OR 태광 OR 동성케미칼 OR DL케미칼) (특허 OR 출원 OR 등록 OR 심판 OR 상표 OR 디자인)"),
 ("특허·기술","site:kipo.go.kr (현대차 OR 기아 OR 현대모비스 OR 포스코 OR 현대제철 OR LS일렉트릭 OR 두산에너빌리티 OR 한화솔루션 OR OCI) (특허 OR 출원 OR 등록 OR 심판 OR 상표 OR 디자인)"),
 ("특허·기술","site:patents.google.com (Hyundai OR Kia OR "Hyundai Mobis" OR "Hyundai Wia" OR "HL Mando" OR POSCO OR "Hyundai Steel" OR "Korea Zinc" OR "LS Electric" OR Doosan OR "Hanwha Solutions") (autonomous OR battery OR vehicle OR tire OR transformer OR HVDC OR wind OR hydrogen OR nuclear OR steel)"),
 ("특허·기술","site:j-platpat.inpit.go.jp (Toyota OR Honda OR Nissan OR Hyundai OR Kia OR Denso OR Aisin) (patent OR trademark OR design)"),
 ("분쟁·조사","site:usitc.gov (Hyundai OR Kia OR steel OR cable OR transformer OR battery OR tire OR Korea) (investigation OR petition OR complaint OR antidumping OR countervailing OR Section 337)"),
 ("분쟁·조사","site:ids.usitc.gov (Hyundai OR Kia OR steel OR cable OR transformer OR battery OR tire OR Korea) (investigation OR petition OR instituted OR complaint)"),
 ("분쟁·조사","site:rulings.cbp.gov (Hyundai OR Kia OR steel OR cable OR transformer OR battery OR tire OR Korea) (origin OR classification OR tariff)"),
 ("해외 규제","site:unece.org (vehicle OR autonomous OR ADAS OR EV OR battery OR tire OR hydrogen) (regulation OR WP.29 OR GRVA OR GRSP OR GRPE OR proposal)"),
 ("해외 규제","site:samr.gov.cn (Hyundai OR Kia OR Mercedes OR Volkswagen OR BMW OR Renault OR Audi OR Honda OR tire) (recall OR defect OR vehicle)"),
 ("해외 규제","site:safetygate.ec.europa.eu (vehicle OR tire OR battery OR charger OR automotive) (alert OR recall OR safety)"),
 ("해외 규제","site:sec.gov (Hyundai OR Kia OR automotive OR POSCO OR steel OR cable OR energy) (8-K OR acquisition OR investment OR executive OR agreement)"),
 ("통상·해외","site:ustr.gov (automotive OR steel OR battery OR cable OR Korea) (tariff OR antidumping OR investigation OR agreement)"),
 ("통상·해외","site:trade.gov (steel OR automotive OR cable OR battery OR Korea) (tariff OR antidumping OR investigation)"),
 ("통상·해외","site:ec.europa.eu (automotive OR steel OR battery OR cable OR Korean) (tariff OR antidumping OR safeguard OR regulation)"),
 ("통상·해외","site:eur-lex.europa.eu (automotive OR battery OR steel OR vehicle OR cable) (regulation OR implementing OR tariff OR antidumping)"),
]
for company,domain in COMPANY_DOMAINS.items():
    PRIMARY_QUERY_SETS.append(("기업 원자료",f"site:{domain} ({company} OR investment OR 투자 OR 증설 OR 공장 OR 수주 OR 계약 OR 특허 OR 임원 OR 대표이사 OR 조직개편 OR board)"))

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
    if any(w in t for w in ("리콜","결함","제작결함","무상수리","investigation","complaint","recall","defect")):return "결함·리콜"
    if any(w in t for w in ("인증","형식승인","certificate","certification","type approval")):return "인증·형식승인"
    if any(w in t for w in ("환경영향","환경성평가","환경입지","건축허가","인허가","개발행위","사업계획승인","산업단지","착공","심의")):return "인허가·환경"
    if any(w in t for w in ("소송","제소","가처분","판결","행정심판","특허심판","분쟁","petition","complaint")):return "소송·분쟁"
    if any(w in t for w in ("상표","디자인","trademark","design patent")):return "상표·디자인"
    if any(w in t for w in ("대표이사","임원","이사","선임","취임","퇴임","인사","조직개편","경영진")):return "인사"
    if any(w in t for w in ("특허","출원","등록","patent")):return "특허·기술"
    if any(w in t for w in ("관세","반덤핑","덤핑","통상","tariff","customs","countervailing","원산지","품목분류")):return "통상·관세"
    if any(w in t for w in ("법안","고시","시행","규제","정책","세제","입법","입법예고")):return "정책·규제"
    if any(w in t for w in ("발주","입찰","조달","낙찰")):return "조달·발주"
    if any(w in t for w in ("물적분할","인적분할","분할","합병","인수","매각","철수","신설법인","사업재편")):return "사업재편"
    if any(w in t for w in ("투자","증설","공장","생산라인","생산","가동","신규법인")):return "신사업·투자"
    if any(w in t for w in ("수주","계약","공급","납품")):return "계약·수주"
    return category or "기업 원자료"

def build_pitch(x,kind,companies,numbers):
    base=re.sub(r"\s*[-|｜].*$","",(x.get("title") or "")).strip()
    if kind=="결함·리콜":
        return f"{base}…국내 판매차량 영향은","결함 부위·생산기간·대상을 확인하고 국내 리콜·무상수리 여부와 회사 대응을 교차 확인"
    if kind=="인증·형식승인":
        return f"{base}…신차·사양 변경 선행 신호인가","인증 원문에서 차종·파워트레인·배출가스·형식 정보를 확인해 출시·양산 계획과 연결"
    if kind=="인허가·환경":
        return f"{base}…공장·증설 실제 움직임은","환경영향평가·인허가 원문에서 사업지·면적·용량·사업자·예상 착공 시점을 확인"
    if kind=="소송·분쟁":
        return f"{base}…기업 간 실제 쟁점은","소장·결정문·심판 기록에서 청구내용·금액·기술·계약 쟁점을 확인하고 상대방 입장을 교차 확인"
    if kind=="상표·디자인":
        return f"{base}…신차·신제품 출시 신호인가","출원인·출원일·지정상품·디자인 대상을 확인하고 실제 출시계획과 연결되는지 취재"
    if kind=="인사":
        return f"{base}…인선 배경과 담당 사업이 변수","인사 원문에서 직책·담당 사업·전임자와의 차이를 확인하고 최근 조직·투자 변화와 연결"
    if kind=="특허·기술":
        return f"{base}…실제 적용·양산 시점이 관건","특허 원문에서 출원번호·청구항·적용 제품을 확인해 단순 등록 사실을 넘어 사업화 여부를 취재"
    if kind=="정책·규제":
        return f"{base}…현장에 달라지는 규정은","최종 고시·법안에서 시행일·대상·예외 조항을 확인하고 출입처별 실제 대응을 교차 확인"
    if kind=="통상·관세":
        return f"{base}…국내 출입처 수출·원가 변수는","판정 원문에서 품목·국가·세율·적용기간을 확인하고 국내 기업별 수출·원가 영향을 취재"
    if kind=="조달·발주":
        return f"{base}…새로 생기는 발주 물량은","입찰·발주 원문에서 예산·물량·납기·참여사를 확인해 실제 수요를 취재"
    if kind=="사업재편":
        return f"{base}…줄이는 사업·키우는 사업은","공시 원문에서 사업 목적·자산·법인 변화를 확인하고 기존 계획과 달라진 점을 취재"
    if kind=="신사업·투자":
        return f"{base}…기존 계획과 다른 점은","투자액·대상·가동 시점·생산능력을 확인하고 기존 계획 대비 변화 여부를 취재"
    if kind=="계약·수주":
        return f"{base}…고객사·물량·기간은","계약 원문에서 고객사·물량·기간·단가·생산능력을 확인해 신규 시장·고객 여부를 취재"
    return f"{base}…새로 확인된 변화","원문 숫자와 담당 조직을 확인하고 출입처에서 실제 변화를 교차 확인"
def source_tier(x):
    label=str(x.get("officialLabel") or x.get("sourceName") or "")
    group=source_group(x)
    if group in {"DART","KIND","특허","조달","자동차·결함","환경·인허가","법령·입법","통상·분쟁","해외기관","지역·투자"}:return 3
    if label in {"산업부","국토부","공정위","관세청","기재부","환경부","USTR","미국 상무부","EU 집행위","EU","NHTSA","EPA","USITC","CBP CROSS","UNECE WP.29","중국 SAMR"}:return 3
    if x.get("category")=="기업 원자료":return 2
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
    general_terms=("자동차","차량","타이어","철강","열연","냉연","후판","강관","비철","구리","아연","전력","변압기","hvdc","케이블","풍력","태양광","ess","에너지","lng","원전","수소","화학","소재","공장","산업단지")
    auto_terms=("자동차","차량","전기차","하이브리드","pbv","자율주행","adas","타이어","리콜","결함","형식승인","배출가스")
    if companies:return True
    if kind in {"정책·규제","통상·관세","인허가·환경","소송·분쟁"}:return any(k in t for k in general_terms)
    if kind in {"결함·리콜","인증·형식승인"}:return any(k in t for k in auto_terms)
    return any(k in t for k in general_terms)

def scoop_headline(x,kind,corp,blob,nums):
    base=(x.get("title") or "").strip()
    if kind=="결함·리콜":return f"{corp}, {base}…대상 차종·대수는"
    if kind=="인증·형식승인":return f"{corp}, 새 인증 포착…국내 출시·사양 변경하나"
    if kind=="인허가·환경":return f"{corp}, 공장·사업 인허가 움직임…착공 시점은"
    if kind=="소송·분쟁":return f"{corp}, 새 소송·분쟁 확인…쟁점과 규모는"
    if kind=="상표·디자인":return f"{corp}, 새 상표·디자인 출원…신차·신제품 신호인가"
    if kind=="인사":
        person=extract_person(blob,corp)
        role=next((k for k in ("대표이사","사장","부사장","전무","상무","본부장","부문장","사내이사","사외이사","임원") if k in base+" "+blob),"")
        return f"{corp}, {person} {role} 인사…배경은" if person!=corp else f"{corp}, 경영진 인사 확인…담당 사업은"
    if kind=="특허·기술":
        detail=next((k for k in ("자율주행","로보택시","배터리","충전","로봇","램프","차량","변압기","HVDC","전력망","풍력","원전") if k in base+" "+blob),"신기술")
        return f"{corp}, {detail} 특허 새로 확인…양산 적용하나"
    if kind=="정책·규제":
        clean_base=re.sub(r"\s*[-|｜].*$","",base)
        return f"{clean_base}…업계에 달라지는 규정은"
    if kind=="통상·관세":return f"{base}…국내 출입처 수출·원가 영향은"
    if kind=="사업재편":
        if "물적분할" in base:return f"{corp}, 사업부문 물적분할…분할 대상·향후 사업은"
        return f"{base}…실제 사업재편 내용은"
    if kind=="신사업·투자":return f"{base}…투자 대상·가동 시점은"
    if kind=="계약·수주":return f"{corp}, 신규 계약 {nums[0]}…고객사·물량은" if nums else f"{base}…고객사·물량·기간은"
    if kind=="조달·발주":return f"{base}…예산·물량·참여사는"
    return base

def source_group(x):
    label=str(x.get("officialLabel") or x.get("sourceName") or "")
    dom=str(x.get("url") or "").lower()
    if label=="DART" or "dart.fss.or.kr" in dom:return "DART"
    if "kind.krx.co.kr" in dom:return "KIND"
    if any(d in dom for d in ("kipris.or.kr","kipo.go.kr","patents.google.com","j-platpat.inpit.go.jp")):return "특허"
    if any(d in dom for d in ("g2b.go.kr","pps.go.kr")):return "조달"
    if "car.go.kr" in dom:return "자동차·결함"
    if "eiass.go.kr" in dom:return "환경·인허가"
    if any(d in dom for d in ("law.go.kr","lawmaking.go.kr")):return "법령·입법"
    if any(d in dom for d in ("usitc.gov","ids.usitc.gov","rulings.cbp.gov","cbp.gov","ustr.gov","trade.gov","ec.europa.eu","eur-lex.europa.eu")):return "통상·분쟁"
    if any(d in dom for d in ("nhtsa.gov","epa.gov","sec.gov","unece.org","samr.gov.cn","cnca.gov.cn","safetygate.ec.europa.eu")):return "해외기관"
    if any(d in dom for d in ("motie.go.kr","molit.go.kr","ftc.go.kr","customs.go.kr","me.go.kr","keco.or.kr","kostat.go.kr","moef.go.kr")):return "정부"
    if any(d in dom for d in ("hyundai.com","kia.com","mobis.com","hyundai-wia.com","hlmando.com","gm-korea.co.kr","kg-mobility.com","mercedes-benz.co.kr","volkswagen.co.kr","bmw.co.kr","renault.co.kr","audi.co.kr","honda.co.kr","hankooktire.com","nexentire.com","kumhotire.com","posco.com","hyundai-steel.com","seah.co.kr","koreazinc.co.kr","youngpoong.co.kr","ls-electric.com","taihan.com","doosanenerbility.com","gscaltex.com","hanwhasolutions.com","oci.co.kr","oci-holdings.co.kr","taekwang.com","dongsungchemical.com","dlchem.com")):return "기업"
    if any(d in dom for d in ("seoul.go.kr","gg.go.kr","investkorea.org")):return "지역·투자"
    return "기타"

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
        if kind in {"특허·기술","상표·디자인","인사","결함·리콜","인증·형식승인","인허가·환경","소송·분쟁"} and source_tier(x)<2:continue

        age_h=max(0,(now-parse_dt(x.get("published"))).total_seconds()/3600)
        tier=source_tier(x)
        concrete=min(18,len(numbers)*3)
        hard=min(12,sum(1 for k in ("분할","합병","매각","인수","철수","신설","조직개편","대표이사","임원","선임","취임","特許","특허","출원","등록","고시","법안","수주","계약","投资","투자","증설","공장","생산") if k in joined))
        score=42 + tier*8 + concrete + hard + 28
        if kind in {"결함·리콜","인증·형식승인","인허가·환경","소송·분쟁","인사","특허·기술","상표·디자인","사업재편","정책·규제","통상·관세"}:score+=9
        if age_h<=24:score+=7
        elif age_h<=72:score+=4
        if not archive_matches:score+=4
        score=min(99,score)

        if score<78:continue
        if not (numbers or kind in {"결함·리콜","인증·형식승인","인허가·환경","소송·분쟁","인사","특허·기술","상표·디자인","정책·규제","사업재편","통상·관세"} or any(k in joined for k in ("공장","법인","조직개편","대표이사","특허","고시","법안","리콜","결함","인증","인허가","소송","판결","관세"))):continue

        corp=companies[0] if companies else "정부"
        headline=scoop_headline(x,kind,corp,x.get("summary") or "",numbers)
        dedup=re.sub(r"[^가-힣A-Za-z0-9]","",headline.lower())
        if dedup in seen:continue
        seen.add(dedup)

        if kind=="결함·리콜":
            why=f"{x.get('officialLabel') or x.get('sourceName')}에서 결함·리콜 원자료를 먼저 포착했습니다. 기존 언론 보도에서 동일 사실의 강한 매칭이 없어 대상 차종·생산기간·국내 영향부터 확인할 가치가 있습니다."
        elif kind=="인증·형식승인":
            why=f"인증 원자료에서 새 차량·파워트레인 인증 신호를 포착했습니다. 공개 기사보다 선행된 자료라면 신차·사양변경의 취재 단서가 될 수 있습니다."
        elif kind=="인허가·환경":
            why=f"환경영향평가·지역 인허가 자료에서 사업 진행 단계를 먼저 포착했습니다. 공식 투자 발표 전 공장·증설·생산거점 변화를 확인할 수 있는 후보입니다."
        elif kind=="소송·분쟁":
            why=f"규제기관·분쟁 원자료에서 새 조사·소송·심판 신호를 포착했습니다. 공개 기사보다 먼저 청구내용·금액·상대방 대응을 확인할 수 있는 후보입니다."
        elif kind=="상표·디자인":
            why=f"특허·상표 원자료에서 새 브랜드·디자인 출원 신호를 포착했습니다. 실제 차종·제품        questions={
            "결함·리콜":["결함 부위·발생 조건과 생산기간은 무엇인가?","국내 판매 차종·대수와 한국GM·벤츠·BMW 등 국내 사업자 영향은?","국내 리콜·무상수리 또는 자진시정 계획이 있는가?"],
            "인증·형식승인":["인증 차종·파워트레인·사양은 무엇인가?","국내 판매·출시 또는 생산 계획과 연결되는가?","기존 모델 대비 변경된 인증 항목과 출시 일정은 무엇인가?"],
            "인허가·환경":["사업지·면적·생산능력·사업자는 누구인가?","환경영향평가 단계와 실제 착공·가동 예상 시점은 언제인가?","기존 투자계획과 비교해 새로 확인되는 규모·공정·생산품은 무엇인가?"],
            "소송·분쟁":["소송·심판·조사의 당사자와 청구내용은 무엇인가?","금액·특허·공급계약 등 핵심 쟁점은 무엇인가?","상대방 또는 감독기관은 어떤 입장인가?"],
            "상표·디자인":["출원인·출원일·지정상품 또는 디자인 대상은 무엇인가?","새 차종·제품·브랜드 출시와 연결되는가?","국내외 동시 출원 또는 기존 브랜드와의 연관성이 있는가?"],
            "인사":["정확한 발령일·직책·담당 사업은 무엇인가?","기존 보직과 무엇이 달라졌고 왜 지금 바뀌었나?","최근 해당 사업의 투자·수주·조직 변화와 연결되는가?"],
            "특허·기술":["출원일·출원번호·핵심 청구항은 무엇인가?","기존 기술과 무엇이 달라졌고 실제 적용 제품은 무엇인가?","양산·상용화 계획이나 협력사가 정해져 있는가?"],
            "정책·규제":["최종 고시·법안에서 달라진 조항은 무엇인가?","시행일과 적용 대상 기업·제품은 어디까지인가?","기업이 실제로 바꿔야 하는 절차·비용은 무엇인가?"],
            "통상·관세":["적용 품목·국가·세율·기간은 무엇인가?","한국 기업의 수출·원가·조달에 미치는 영향은 어느 정도인가?","기업들은 가격전가·생산지 변경 등 어떤 대응을 준비하나?"],
            "사업재편":["분할·매각·신설 대상 사업의 자산과 인력은 어떻게 이동하는가?","기존 계획과 비교해 이번 결정으로 달라지는 사업 범위는 무엇인가?","후속 일정과 생산·투자 변화는 언제 발생하는가?"],
            "신사업·투자":["투자 대상·금액·가동 시점은 무엇인가?","기존 생산능력·사업계획에서 얼마나 달라졌는가?","신규 고객·시장 진입 효과가 있는가?"],
            "계약·수주":["계약 상대방과 프로젝트·지역은 어디인가?","물량·기간·단가와 실제 생산능력 투입 규모는 얼마인가?","이번 계약이 신규 고객 또는 신규 시장 진입을 의미하는가?"],
            "조달·발주":["예산·물량·납기·발주기관은 어디인가?","참여 예상 기업과 낙찰 일정은 언제인가?","기존 계획에 없던 신규 수요인지 확인할 수 있는가?"]        }.get(kind,["원자료의 핵심 조건은 무엇인가?","동일 사실의 언론 보도가 정말 없는가?","출입처에서 어떤 사실을 전화로 교차확인할 수 있는가?"])

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
            "evidenceTier":tier,"coverageChecked":True,
            "sourceGroup":source_group(x)
        })

    kind_rank={"결함·리콜":10,"인증·형식승인":10,"인허가·환경":9,"소송·분쟁":9,"인사":8,"특허·기술":8,"상표·디자인":7,"사업재편":7,"정책·규제":7,"통상·관세":6,"신사업·투자":6,"조달·발주":5,"계약·수주":3}
    candidates.sort(key=lambda z:(z["score"],kind_rank.get(z["kind"],1),-z["coverageCount"],len(z.get("numbers") or []),z.get("firstSeenAt","")),reverse=True)

    final=[];used_primary=set();used_keys=set();used_groups=set()
    for c in sorted(candidates,key=lambda z:(z["score"],{"결함·리콜":10,"인증·형식승인":10,"인허가·환경":9,"소송·분쟁":9,"인사":8,"특허·기술":8,"상표·디자인":7,"사업재편":7,"정책·규제":7,"통상·관세":6,"신사업·투자":6,"조달·발주":5,"계약·수주":3}.get(z["kind"],1)),reverse=True):
        key=(tuple(sorted(c.get("companies") or [])),re.sub(r"[^가-힣A-Za-z0-9]","",c.get("title",""))[:45])
        if key in used_keys:continue
        sg=c.get("sourceGroup","기타")
        if sg=="DART" and sum(1 for x in final if x.get("sourceGroup")=="DART")>=4:continue
        if sg in used_groups and len(used_groups)<5 and sg in {"특허","KIND","조달","해외기관","정부","기업","지역·투자"}:continue
        primary_company=(c.get("companies") or [None])[0]
        if primary_company and primary_company in used_primary and c["score"]<94:continue
        used_keys.add(key)
        if primary_company:used_primary.add(primary_company)
        used_groups.add(sg)
        final.append(c)
        if len(final)>=12:break
    if len(final)<12:
        for c in candidates:
            key=(tuple(sorted(c.get("companies") or [])),re.sub(r"[^가-힣A-Za-z0-9]","",c.get("title",""))[:45])
            if key in used_keys:continue
            if c.get("sourceGroup")=="DART" and sum(1 for x in final if x.get("sourceGroup")=="DART")>=4:continue
            used_keys.add(key);final.append(c)
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
        "sourceGroups":{g:sum(1 for x in final if x.get("sourceGroup")==g) for g in sorted({x.get("sourceGroup","기타") for x in final})},
        "note":"단독감은 기존 언론 기사의 중요도를 평가하는 기능이 아닙니다. DART뿐 아니라 특허·KIND·정부·조달·기업 원자료·해외 규제기관·지역 인허가 자료에서 새 사실을 먼저 포착하고, 현재 언론·아카이브에 동일 사실이 없을 때만 후보로 올립니다. 인사·특허·정책·사업재편을 우선하며 일반적인 공급계약은 추가성이 없으면 제외합니다."
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    print(f"primary-source scoop scout: {len(primary)} primary hits -> {len(final)} selective unreported candidates")

if __name__=="__main__":main()
