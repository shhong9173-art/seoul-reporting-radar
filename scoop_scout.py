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
PRIMARY_LOOKBACK_DAYS=10
COVERAGE_LOOKBACK_DAYS=180

TARGETS=[
 # 자동차
 ("현대차","자동차"),("기아","자동차"),("제네시스","자동차"),("현대모비스","자동차"),("현대위아","자동차"),
 ("HL만도","자동차"),("만도","자동차"),("한국GM","자동차"),("KG모빌리티","자동차"),("메르세데스벤츠코리아","자동차"),
 ("폭스바겐코리아","자동차"),("폭스바겐","자동차"),("BMW코리아","자동차"),("BMW","자동차"),("르노코리아","자동차"),
 ("아우디코리아","자동차"),("아우디","자동차"),("혼다코리아","자동차"),("한국타이어","자동차"),("넥센타이어","자동차"),
 ("금호타이어","자동차"),("현대트랜시스","자동차"),("현대글로비스","자동차"),
 ("현대오토에버","자동차"),("삼성전기","자동차부품"),
 ("LG에너지솔루션","배터리"),("삼성SDI","배터리"),("SK온","배터리"),("SK이노베이션","에너지"),
 ("포스코퓨처엠","배터리·소재"),("엘앤에프","배터리·소재"),("포스코인터내셔널","철강·에너지"),
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
 "현대오토에버":("현대오토에버","Hyundai AutoEver"),"삼성전기":("삼성전기","Samsung Electro-Mechanics"),
 "LG에너지솔루션":("LG에너지솔루션","LG Energy Solution","LGES"),"삼성SDI":("삼성SDI","Samsung SDI"),
 "SK온":("SK온","SK On"),"SK이노베이션":("SK이노베이션","SK Innovation"),
 "포스코퓨처엠":("포스코퓨처엠","POSCO Future M"),"엘앤에프":("엘앤에프","L&F","LNF"),
 "포스코인터내셔널":("포스코인터내셔널","POSCO International"),
 "포스코":("포스코","POSCO"),"포스코홀딩스":("포스코홀딩스","POSCO Holdings"),"현대제철":("현대제철","Hyundai Steel"),
 "KG스틸":("KG스틸","KG Steel"),"세아홀딩스":("세아홀딩스","SeAH Holdings"),"세아제강":("세아제강","SeAH Steel"),
 "고려아연":("고려아연","Korea Zinc"),"영풍":("영풍","Young Poong"),"LS MnM":("LS MnM","LS MnM Inc."),
 "HD현대일렉트릭":("HD현대일렉트릭","HD Hyundai Electric"),"LS일렉트릭":("LS일렉트릭","엘에스일렉트릭","LS ELECTRIC"),
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
 "assembly.go.kr":"국회","bai.go.kr":"감사원","kpx.or.kr":"전력거래소","kepco.co.kr":"한국전력","kogas.or.kr":"한국가스공사","khnp.co.kr":"한수원","knrec.or.kr":"에너지공단",
 "kisrating.com":"한국신용평가","korearatings.com":"한국기업평가","crefia.or.kr":"신용평가·금융",
 "kosa.or.kr":"한국철강협회","kweia.or.kr":"한국풍력산업협회","lngkorea.org":"민간LNG산업협회","metall.or.kr":"금속노련",
 "hyundai-transys.com":"현대트랜시스","glovis.net":"현대글로비스","kg-steel.co.kr":"KG스틸","seahsteel.co.kr":"세아제강",
 "lsmnm.com":"LS MnM","hd-hyundaielectric.com":"HD현대일렉트릭","hyosungheavyindustries.com":"효성중공업",
 "lscns.co.kr":"LS전선","lsholdings.com":"LS지주","gs.co.kr":"GS",
 "kkpc.com":"금호석유화학","hshyosungadvancedmaterials.com":"효성첨단소재","kolonindustries.com":"코오롱인더",
 "lgchem.com":"LG화학","lottechem.com":"롯데케미칼","lgensol.com":"LG에너지솔루션","samsungsem.com":"삼성전기","poscofuturem.com":"포스코퓨처엠",
 "kepic.or.kr":"대한전기협회","koema.or.kr":"한국전기산업진흥회","kaif.or.kr":"한국원자력산업협회",
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
 "현대차":"hyundai.com","기아":"kia.com","제네시스":"genesis.com","현대모비스":"mobis.com","현대위아":"hyundai-wia.com","HL만도":"hlmando.com","만도":"hlmando.com",
 "한국GM":"gm-korea.co.kr","KG모빌리티":"kg-mobility.com","메르세데스벤츠코리아":"mercedes-benz.co.kr","폭스바겐코리아":"volkswagen.co.kr",
 "BMW코리아":"bmw.co.kr","BMW":"bmw.co.kr","르노코리아":"renault.co.kr","아우디코리아":"audi.co.kr","아우디":"audi.co.kr","혼다코리아":"honda.co.kr","폭스바겐":"volkswagen.co.kr",
 "한국타이어":"hankooktire.com","넥센타이어":"nexentire.com","금호타이어":"kumhotire.com",
 "현대트랜시스":"hyundai-transys.com","현대글로비스":"glovis.net",
 "LG에너지솔루션":"lgensol.com","삼성전기":"samsungsem.com","포스코퓨처엠":"poscofuturem.com",
 "포스코":"posco.com","포스코홀딩스":"posco-inc.com","현대제철":"hyundai-steel.com","KG스틸":"kg-steel.co.kr","세아홀딩스":"seah.co.kr","세아제강":"seahsteel.co.kr",
 "고려아연":"koreazinc.co.kr","영풍":"youngpoong.co.kr","LS MnM":"lsmnm.com","LS M&M":"lsmnm.com",
 "HD현대일렉트릭":"hd-hyundaielectric.com","LS일렉트릭":"ls-electric.com","대한전선":"taihan.com","효성중공업":"hyosungheavyindustries.com","일진전기":"iljinelectric.co.kr",
 "LS전선":"lscns.co.kr","LS지주":"lsholdings.com",
 "두산에너빌리티":"doosanenerbility.com","GS":"gs.co.kr","GS칼텍스":"gscaltex.com",
 "한화솔루션":"hanwhasolutions.com","OCI":"oci.co.kr","OCI홀딩스":"oci-holdings.co.kr","씨에스윈드":"cswind.com",
 "태광":"taekwang.com","동성케미칼":"dongsungchemical.com","DL케미칼":"dlchem.com",
 "LG화학":"lgchem.com","롯데케미칼":"lottechem.com","금호석유화학":"kkpc.com","효성첨단소재":"hshyosungadvancedmaterials.com","코오롱인더":"kolonindustries.com"
}
COMPANY_BY_DOMAIN={domain:company for company,domain in COMPANY_DOMAINS.items()}
NOISE_RE=re.compile(r"주가|증권|목표주가|급등|급락|관련주|테마주|특징주|장중|종목|추천주|리포트|기재정정|첨부정정",re.I)
WEAK_RE=re.compile(r"사회공헌|기부|봉사|채용|수상|캠페인|축제|전시|세미나|포럼|강연|홍보대사|혜택|이벤트|모먼트|스토리|재단|장학|펠로|양궁|칵테일|아트워크|우수조",re.I)
HARD_SIGNAL_RE=re.compile(r"정책|규제|시행|고시|법안|입법|예고|결정고시|행정처분|관세|반덤핑|상계관세|특허|출원|등록|특허심판|심판|상표|디자인|대표이사|임원|사내이사|사외이사|선임|취임|퇴임|조직개편|신설|투자|출자|증설|공장|법인|합병|분할|인수|매각|철수|수주|계약|공급|발주|입찰|낙찰|생산|가동|감산|가격|원가|마진|배터리|ESS|HVDC|변압기|해저케이블|해상풍력|자율주행|리콜|결함|제작결함|무상수리|조사개시|인증|형식승인|환경영향|환경성평가|건축허가|사업계획승인|산업단지|소송|제소|가처분|판결|행정심판|자기주식|자사주|주식처분|주식소각|전환사채|교환사채|신주인수권부사채|금전대여|채무인수|담보제공|보증제공|영업정지|영업양수도",re.I)
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
 ("특허·기술",'site:patents.google.com (Hyundai OR Kia OR "Hyundai Mobis" OR "Hyundai Wia" OR "HL Mando" OR POSCO OR "Hyundai Steel" OR "Korea Zinc" OR "LS Electric" OR Doosan OR "Hanwha Solutions") (autonomous OR battery OR vehicle OR tire OR transformer OR HVDC OR wind OR hydrogen OR nuclear OR steel)'),
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
 ("협회·산업단체","site:kosa.or.kr (정책 OR 건의 OR 조사 OR 통계 OR 수급 OR 가격 OR 통상 OR 반덤핑 OR 수입 OR 수출 OR 회원사 OR 공동대응 OR 연구) (철강 OR 열연 OR 냉연 OR 후판 OR 강관 OR 철광석)"),
 ("협회·산업단체","site:kweia.or.kr (정책 OR 제도 OR 입찰 OR 조사 OR 프로젝트 OR 공급망 OR 인허가 OR 특별법 OR 회원사 OR 공동대응) (풍력 OR 해상풍력 OR 전력 OR 항만 OR 선박)"),
 ("협회·산업단체","site:lngkorea.org (정책 OR 제도 OR 통상 OR 직수입 OR 배관 OR 공동이용 OR 수급 OR 요금 OR 연구 OR 회원사) (LNG OR 천연가스)"),
 ("협회·산업단체","site:kepic.or.kr (기술기준 OR 개정 OR 인증 OR 표준 OR 입찰 OR 원전 OR 전력 OR 전기설비 OR 안전)"),
 ("협회·산업단체","site:koema.or.kr (정책 OR 수출 OR 조사 OR 인증 OR 시험 OR 전력망 OR 변압기 OR HVDC OR 기술 OR 회원사)"),
 ("협회·산업단체","site:kaif.or.kr (원전 OR SMR OR 입찰 OR 회원사 OR 정책 OR 수출 OR 수주 OR 프로젝트 OR 산업실태조사 OR 기술) (공지 OR 입찰정보 OR 보도자료 OR 투데이뉴스)"),
 ("정책·의원실","site:assembly.go.kr (현대차 OR 기아 OR 현대모비스 OR 포스코 OR 현대제철 OR 고려아연 OR 영풍 OR LS OR 두산에너빌리티 OR GS OR 한화솔루션 OR OCI OR 태광 OR 동성케미칼 OR DL케미칼) (요구자료 OR 국정감사 OR 의원실 OR 자료제출 OR 질의 OR 현안)"),
 ("감사·감독","site:bai.go.kr (현대차 OR 기아 OR 포스코 OR 현대제철 OR 고려아연 OR LS OR 두산에너빌리티 OR GS OR 한화솔루션 OR OCI) (감사 OR 처분 OR 지적 OR 조사)"),
 ("전력시장","site:kpx.or.kr (전력망 OR 전력수급 OR SMP OR REC OR HVDC OR ESS OR 발전 OR 송전 OR 예비력) (계획 OR 통계 OR 공고 OR 회의 OR 용량)"),
 ("공기업·에너지","site:kepco.co.kr (HVDC OR 변압기 OR 전력망 OR 송전 OR 배전 OR 입찰 OR 발주 OR 구매 OR 계약 OR 공사)"),
 ("공기업·에너지","site:kogas.or.kr (LNG OR 천연가스 OR 터미널 OR 배관 OR 수급 OR 직수입 OR 투자 OR 공사 OR 입찰)"),
 ("공기업·원전","site:khnp.co.kr (원전 OR SMR OR 원자로 OR 건설 OR 입찰 OR 기자재 OR 공급 OR 구매)"),
 ("재생에너지","site:knrec.or.kr (풍력 OR 태양광 OR ESS OR 재생에너지 OR 보급 OR 입찰 OR 공급망 OR 인증 OR 지원금)"),
 ("재무·신용","site:kisrating.com (현대자동차 OR 기아 OR 현대모비스 OR 포스코 OR 현대제철 OR 고려아연 OR 영풍 OR LS OR 두산에너빌리티 OR GS OR 한화솔루션 OR OCI OR 태광 OR 동성케미칼 OR DL케미칼) (수시평가 OR Issuer Comment OR 그룹분석 OR 신용등급 OR 전망 OR 차입 OR 투자 OR 인수 OR 매각 OR 자금조달 OR 재무구조)"),
 ("재무·신용","site:korearatings.com (현대자동차 OR 기아 OR 현대모비스 OR 포스코 OR 현대제철 OR 고려아연 OR 영풍 OR LS OR 두산에너빌리티 OR GS OR 한화솔루션 OR OCI OR 태광 OR 동성케미칼 OR DL케미칼) (수시평가 OR 신용등급 OR 전망 OR 투자 OR 인수 OR 매각 OR 자금조달 OR 재무구조)"),
 ("노사·현장","site:metall.or.kr (현대차 OR 기아 OR 포스코 OR 현대제철 OR LS전선 OR HD현대일렉트릭 OR 일진전기 OR 세아 OR 금호타이어 OR 한국타이어 OR 넥센타이어) (임단협 OR 단체교섭 OR 잠정합의 OR 파업 OR 쟁의 OR 투표 OR 노조 OR 생산 OR 조업)"),
]
for company,domain in {
    "한국철강협회":"kosa.or.kr","한국풍력산업협회":"kweia.or.kr","민간LNG산업협회":"lngkorea.org",
    "대한전기협회":"kepic.or.kr","한국전기산업진흥회":"koema.or.kr","한국원자력산업협회":"kaif.or.kr"
}.items():
    PRIMARY_QUERY_SETS.append(("협회·산업단체",f"site:{domain} ({company} OR 정책 OR 건의 OR 조사 OR 통계 OR 수급 OR 회원사 OR 공동대응 OR 입찰 OR 프로젝트)"))

SCOOP_FINGERPRINT_TERMS="이사회 OR 임원 OR 대표이사 OR 인사 OR 퇴사 OR 조직개편 OR 생산계획 OR 생산조정 OR 생산라인 OR 공급사 OR 공급중단 OR 대체투입 OR 재고 OR 납기 OR 노사 OR 임단협 OR 잠정합의 OR 파업 OR 쟁의 OR 매각 OR 인수 OR 거래종결 OR 지분 OR 자금조달 OR 유상증자 OR 회사채 OR RSU OR 양산 OR 시제품 OR 품질 OR 리콜 OR 인증 OR 인허가 OR 환경영향 OR 특허"
for company,domain in COMPANY_DOMAINS.items():
    PRIMARY_QUERY_SETS.append(("기업 원자료",f"site:{domain} ({company}) ({SCOOP_FINGERPRINT_TERMS})"))

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
    t=(s or "").lower();hits=[]
    for order,(name,_) in enumerate(TARGETS):
        matched_len=0
        for alias in ALIASES.get(name,(name,)):
            a=alias.lower()
            if re.fullmatch(r"[a-z0-9 &.-]{2,}",a):
                matched=bool(re.search(r"(?<![a-z0-9])"+re.escape(a)+r"(?![a-z0-9])",t))
            else:
                matched=a in t
            if matched:matched_len=max(matched_len,len(a))
        if matched_len:hits.append((matched_len,-order,name))
    # Prefer the most specific tracked company first (e.g. POSCO Future M before POSCO).
    hits.sort(reverse=True)
    return list(dict.fromkeys(name for _,_,name in hits))
BEAT_KEYWORDS=[
    (("자동차","차량","전기차","하이브리드","PBV","자율주행","ADAS","타이어","리콜","결함","형식승인"),"자동차"),
    (("철강","열연","냉연","후판","강관","철광석","제철","제강","도금"),"철강"),
    (("고려아연","영풍","구리","아연","니켈","제련","희소금속"),"비철금속"),
    (("HVDC","변압기","전력기기","전력망","배전","송전"),"전력기기"),
    (("해저케이블","전선","케이블","초고압"),"전선·전력"),
    (("LNG","원전","원자로","SMR","가스터빈","수소","발전"),"에너지"),
    (("풍력","해상풍력","태양광","재생에너지","ESS"),"재생에너지"),
    (("석유화학","화학","소재","수지","고분자","탄소섬유"),"화학·소재"),
]
def beat_for(s):
    hits=target_hits(s)
    for name in hits:
        for target,beat in TARGETS:
            if target==name:return beat
    t=(s or "")
    for keys,beat in BEAT_KEYWORDS:
        if any(k.lower() in t.lower() for k in keys):return beat
    return "정책·통상"

def domain_for(url):
    host=urllib.parse.urlparse(url or "").netloc.lower().split(":")[0]
    for domain,label in OFFICIAL_DOMAINS.items():
        if host==domain or host.endswith("."+domain):return label,True
    return "",False

def google_rss(category,query,max_items=8,lookback_days=PRIMARY_LOOKBACK_DAYS):
    now=datetime.now(KST)
    # Primary-source queries stay tight; coverage queries intentionally look much further back.
    after=(now-timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    q=query+" after:"+after
    url="https://news.google.com/rss/search?q="+urllib.parse.quote(q)+"&hl=ko&gl=KR&ceid=KR:ko"
    try:root=ET.fromstring(get(url))
    except Exception:return []
    cutoff=now-timedelta(days=lookback_days);out=[]
    site_match=re.search(r"site:([A-Za-z0-9.-]+)",query,re.I)
    site=site_match.group(1).lower() if site_match else ""
    for item in root.findall("./channel/item"):
        title=(item.findtext("title") or "").strip();link=(item.findtext("link") or "").strip();pub=item.findtext("pubDate") or ""
        desc=clean(item.findtext("description") or "");src=item.find("source");source=(src.text or "").strip() if src is not None else ""
        if not title or not link:continue
        dt=parse_dt(pub)
        if dt<cutoff:continue
        # Drop clearly stale source documents that Google can re-surface with a new feed timestamp.
        stale_marker=re.search(r"(?:^|[\s\[\(])20(?:0\d|1\d|2[0-4])(?:년|년도)",title)
        if stale_marker:continue
        label,domain_official=domain_for(link)
        out.append({
            "category":category,"title":title,"url":link,"published":dt.isoformat(),
            "sourceName":source or label or "Google News","summary":desc[:2000],
            "official":bool(site or domain_official),"officialLabel":label or (OFFICIAL_DOMAINS.get(site) if site else ""),
            "querySite":site,
            "retrievalQuery":q
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

def event_signal_terms(text):
    return set(re.findall(
        r"영업정지|조업정지|생산중단|가동중단|생산조정|생산계획|공급중단|공급차질|대체투입|생산라인|공급사|재고|납기|가격인상|가격인하|매각|인수|우선협상|거래종결|분할|합병|철수|신설법인|조직개편|대표이사|사장|임원|선임|퇴임|인허가|환경영향|건축허가|사업계획승인|착공|증설|공장|리콜|결함|조사개시|행정처분|소송|제소|판결|특허심판|특허|출원|등록|상표|디자인|인증|형식승인|관세|반덤핑|상계관세|수주|계약|발주|입찰|낙찰|자금조달|유상증자|회사채|PRS|보조금|지원금|신용등급|수시평가|재무구조",
        str(text or ""),re.I))

def event_match_score(x,h):
    title=(x.get("title") or "").strip()
    htitle=(h.get("title") or "").strip()
    if not title or not htitle:return 0.0
    xtext=title+" "+(x.get("summary") or "")
    htext=htitle+" "+(h.get("summary") or "")
    companies=target_hits(xtext)
    same_company=bool(companies) and any(c.lower() in htext.lower() for c in companies)
    tsim=similarity(title,htitle)
    ssim=similarity((x.get("summary") or "")[:1800],(h.get("summary") or "")[:1800])
    shared_terms=len(event_signal_terms(title)&event_signal_terms(htitle))
    nums_x=set(NUM_RE.findall(xtext)); nums_h=set(NUM_RE.findall(htext))
    shared_nums=len(nums_x&nums_h)
    # Similar company/topic is not enough to call it the same event.
    # Prior-coverage suppression requires a materially stronger match.
    # A distinctive event can match prior coverage even when the filing has no amount.
    specific_pattern=re.compile(r"물적분할|인적분할|회사분할|영업정지|생산중단|조업정지|가동중단|영업양수도|합병|인수|매각|철수|우선협상|거래종결|가처분|소송제기|특허심판|반덤핑|상계관세",re.I)
    shared_specific=set(specific_pattern.findall(title)) & set(specific_pattern.findall(htitle))
    if same_company and shared_specific and tsim>=0.28:
        return 0.80
    if same_company and shared_terms>=2 and tsim>=0.42:
        return 0.82+min(0.10,shared_nums*0.03)
    if same_company and shared_terms>=1 and shared_nums>=1 and tsim>=0.34:
        return 0.76+min(0.10,shared_nums*0.04)
    if same_company and tsim>=0.66:
        return 0.80
    if tsim>=0.72 or (tsim>=0.55 and ssim>=0.32):
        return 0.70
    return 0.0

COVERAGE_SEARCH_DIAGNOSTICS={"calls":0,"queries":0,"results":0}

def coverage_search(x,max_queries=2):
    COVERAGE_SEARCH_DIAGNOSTICS["calls"]+=1
    title=(x.get("title") or "").strip()
    if len(title)<8:return []
    joined=title+" "+(x.get("summary") or "")
    companies=target_hits(joined)
    stop={"정책","사업","결정","주요","사항","관련","전체","상세보기","행정규칙","훈령","예규","고시","기업","회사","신규","공급계약","체결","발표","현황","자동차","산업","원자료","확인"}
    raw=[w for w in re.findall(r"[가-힣A-Za-z0-9]{2,}",title) if w not in stop]
    signal_words=[w for w in raw if re.search(r"조업정지|생산중단|가동중단|공급중단|대체투입|생산라인|공급사|재고|납기|매각|인수|우선협상|거래종결|분할|합병|철수|신설|조직개편|대표이사|임원|선임|퇴임|인허가|환경영향|건축허가|착공|증설|공장|리콜|결함|조사|행정처분|소송|판결|특허|출원|등록|상표|디자인|인증|형식승인|관세|반덤핑|수주|계약|발주|입찰|낙찰|자금조달|유상증자|회사채|PRS|보조금|지원금",w,re.I)]
    queries=[]
    company=companies[0] if companies else ""
    core=signal_words[:4] or raw[:6]
    if company and core:
        queries.append((company+" "+" ".join(core[:4])).strip())
        queries.append((company+" "+" ".join(core[:2])).strip())
    elif core:
        queries.append(" ".join(core[:6]))
    if len(core)>=2:queries.append(f'"{core[0]}" "{core[1]}"')
    if company and len(core)>=1:queries.append(f'"{company}" "{core[0]}"')
    if company and len(raw)>=3:queries.append(f'"{company}" "{" ".join(raw[1:4])}"')
    out=[];seen=set()
    for q in queries[:max_queries]:
        COVERAGE_SEARCH_DIAGNOSTICS['queries']+=1
        if len(q)<8:continue
        for h in google_rss("coverage",q,max_items=6,lookback_days=COVERAGE_LOOKBACK_DAYS):
            if h.get("official") or h.get("sourceName")=="Google News":continue
            key=h.get("url") or (h.get("sourceName","")+"|"+h.get("title",""))
            if key not in seen:
                seen.add(key);out.append(h)
    scored=[]
    for h in out:
        quality=event_match_score(x,h)
        if quality>0:scored.append((quality,h))
    scored.sort(key=lambda z:z[0],reverse=True)
    COVERAGE_SEARCH_DIAGNOSTICS['results']+=len(scored)
    return [h for _,h in scored[:8]]
DART_DOC_CACHE={}

def fetch_dart_document(receipt):
    key=os.environ.get("DART_API_KEY","").strip()
    if not key or not receipt:return ""
    receipt=str(receipt)
    if receipt in DART_DOC_CACHE:
        return DART_DOC_CACHE[receipt]
    try:
        u="https://opendart.fss.or.kr/api/document.xml?"+urllib.parse.urlencode({"crtfc_key":key,"rcept_no":receipt})
        raw=get(u,8)
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            chunks=[]
            for name in z.namelist()[:10]:
                if not name.lower().endswith((".xml",".html",".htm",".txt")):continue
                txt=clean(z.read(name).decode("utf-8",errors="ignore"))
                if txt:chunks.append(txt)
            result=" ".join(chunks)[:16000]
            DART_DOC_CACHE[receipt]=result
            return result
    except Exception:
        DART_DOC_CACHE[receipt]=""
        return ""

def dart_fact(d,numeric_rows,force_document=False):
    nr=next((r for r in numeric_rows if r.get("receiptNo")==d.get("receiptNo")),None)
    context="";nums=[]
    if nr:
        nums=list(dict.fromkeys(nr.get("numbers") or []))
        context=" ".join(sn.get("context","") for sn in nr.get("snippets",[])[:2])
        # Reuse snippets for ordinary filings. Material single-sale/supply contracts
        # are the exception: customer, tonnage, duration and destination often live
        # in the original filing body rather than the numeric extractor's snippets.
        if (context or nums or nr.get("error")) and not force_document:
            return context.strip(),nums
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
    if any(w in t for w in ("영업정지","생산중단","조업정지","가동중단","생산조정")):return "사업재편"
    if any(w in t for w in ("산업안전","근로감독","특별감독","중대재해","행정처분","시정명령","임금체불")):return "정책·규제"
    if any(w in t for w in ("리콜","결함","제작결함","무상수리","recall","defect")) or category=="자동차 결함":return "결함·리콜"
    if any(w in t for w in ("인증","형식승인","certificate","certification","type approval","emissions family")):return "인증·형식승인"
    if any(w in t for w in ("환경영향","환경성평가","환경입지","건축허가","인허가","개발행위","사업계획승인","산업단지","착공","심의")):return "인허가·환경"
    if any(w in t for w in ("소송","제소","가처분","판결","행정심판","특허심판","분쟁","petition","complaint","investigation")):return "소송·분쟁"
    if any(w in t for w in ("상표","디자인","trademark","design patent")):return "상표·디자인"
    if any(w in t for w in ("대표이사","임원","이사","선임","취임","퇴임","인사","조직개편","경영진")):return "인사"
    if any(w in t for w in ("특허","출원","등록","patent")):return "특허·기술"
    if any(w in t for w in ("관세","반덤핑","덤핑","통상","tariff","customs","countervailing","원산지","품목분류")):return "통상·관세"
    if any(w in t for w in ("요구자료","국정감사","의원실","감사","감사처분","지적","정책","법안","고시","시행","규제","정책","세제","입법","입법예고")):return "정책·규제"
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
    if group in {"DART","KIND","특허","조달","자동차·결함","환경·인허가","법령·입법","통상·분쟁","해외기관","지역·투자","협회","노사·현장","정책·감독","공기업·시장","공기업·조달","법원·분쟁","공장·산업단지","인증·안전","R&D·기술","중앙노동위","고용노동","재무·신용"}:return 3
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
    specific=("생산라인","생산계획","생산량","공급사","대체투입","재고","조업","가동중단","종풍","증설","공장","투자","매각","인수","합병","분할","이사회","임원","대표이사","선임","퇴임","특허","상표","디자인","리콜","결함","조사","인증","형식승인","환경영향","건축허가","사업계획","입찰","낙찰","수주","계약","관세","반덤핑","소송","판결","심판","자금조달","유상증자","채권","RSU","신용등급","전망","수시평가","Issuer Comment","그룹분석","차입","노사","임단협","잠정합의","파업","쟁의","생산계획","생산조정","공급중단","대체투입","재고","납기","거래종결","지분")
    # Company-specific source signals are highest value.
    if companies:return True
    if COMPANY_BY_DOMAIN.get(str(x.get("querySite") or "").lower()):return True
    if kind in {"결함·리콜","인증·형식승인"}:return any(k in t for k in auto_terms)
    if kind in {"정책·규제","통상·관세","인허가·환경","소송·분쟁"}:
        return any(k in t for k in general_terms) and any(k in t for k in specific)
    return any(k in t for k in general_terms) and any(k in t for k in specific)

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
    if x.get("sourceGroup") and x.get("preScoop"):return str(x.get("sourceGroup"))
    label=str(x.get("officialLabel") or x.get("sourceName") or "")
    dom=str(x.get("url") or "").lower()
    query_site=str(x.get("querySite") or "").lower()
    if label=="DART" or "dart.fss.or.kr" in dom:return "DART"
    if "kind.krx.co.kr" in dom or query_site=="kind.krx.co.kr":return "KIND"
    if any(d in (dom+" "+query_site) for d in ("kipris.or.kr","kipo.go.kr","patents.google.com","j-platpat.inpit.go.jp")):return "특허"
    if any(d in (dom+" "+query_site) for d in ("g2b.go.kr","pps.go.kr")):return "조달"
    if "car.go.kr" in (dom+" "+query_site):return "자동차·결함"
    if "eiass.go.kr" in (dom+" "+query_site):return "환경·인허가"
    if any(d in (dom+" "+query_site) for d in ("law.go.kr","lawmaking.go.kr")):return "법령·입법"
    if any(d in (dom+" "+query_site) for d in ("usitc.gov","ids.usitc.gov","rulings.cbp.gov","cbp.gov","ustr.gov","trade.gov","ec.europa.eu","eur-lex.europa.eu")):return "통상·분쟁"
    if any(d in (dom+" "+query_site) for d in ("nhtsa.gov","epa.gov","sec.gov","unece.org","samr.gov.cn","cnca.gov.cn","safetygate.ec.europa.eu")):return "해외기관"
    if any(d in (dom+" "+query_site) for d in ("motie.go.kr","molit.go.kr","ftc.go.kr","customs.go.kr","me.go.kr","keco.or.kr","kostat.go.kr","moef.go.kr")):return "정부"
    if any(domain in (dom+" "+query_site) for domain in COMPANY_DOMAINS.values()):return "기업"
    if any(d in (dom+" "+query_site) for d in ("seoul.go.kr","gg.go.kr","investkorea.org")):return "지역·투자"
    if any(d in (dom+" "+query_site) for d in ("assembly.go.kr","bai.go.kr")):return "정책·감독"
    if any(d in (dom+" "+query_site) for d in ("kisrating.com","korearatings.com","crefia.or.kr")):return "재무·신용"
    if any(d in (dom+" "+query_site) for d in ("kpx.or.kr","kepco.co.kr","kogas.or.kr","khnp.co.kr","knrec.or.kr")):return "공기업·시장"
    if any(d in (dom+" "+query_site) for d in ("kosa.or.kr","kweia.or.kr","lngkorea.org","kepic.or.kr","koema.or.kr","kaif.or.kr")):return "협회"
    if "metall.or.kr" in (dom+" "+query_site):return "노사·현장"
    return "기타"

EXCLUSIVE_PATTERN_MAP={
    "노사·생산":("노사","임단협","잠정합의","생산조정","생산계획","파업","쟁의","공급차질"),
    "내부인사":("내정","인선","퇴임","조직개편","이사회","사장","대표이사","임원"),
    "사업재편":("매각 협상","우선협상","인수","분할","철수","신설법인","거래종결"),
    "공급망":("공급사","공급중단","대체투입","납품","재고","생산차질","가격인상"),
    "프로젝트":("착공","인허가","환경영향","보조금","지원금","공장","증설","발주"),
    "자금조달":("PRS","유증","회사채","사모","브리지","리파이낸싱","자금조달"),
    "규제·조사":("조사개시","시정명령","행정처분","리콜","결함","소송","심판","반덤핑"),
    "기술·제품":("특허","출원","상표","디자인","인증","형식승인","시제품","양산"),
}

def exclusive_pattern_hits(text):
    t=(text or "").lower()
    hits=[]
    for label,terms in EXCLUSIVE_PATTERN_MAP.items():
        n=sum(1 for k in terms if k.lower() in t)
        if n>=2:hits.append((label,n))
    return hits

def group_is_procurement(x):
    group=str(x.get("sourceGroup") or "")
    return group in {"공기업·조달","조달"} and bool(re.search(r"원전|원자력|원자로|SMR|변압기|HVDC|케이블|송전|배전|터빈|발전기|배관|플랜트|전력망|풍력|태양광|ESS|배터리|철강|강관|수소|암모니아|압축기|제어시스템|계측제어|전기설비|계속운전", str(x.get("title") or ""), re.I))

def build_lead_signals(primary, data, now, limit=12):
    """Surface only company-specific material changes after a recent-news cross-check."""
    signal_patterns = [
        ("결함·안전", ("리콜","제작결함","결함조사","안전기준","배터리 화재")),
        ("노사·생산", ("잠정합의","임단협","단체교섭","파업","쟁의","생산계획","생산조정","생산라인","감산","조업중단","생산중단")),
        ("공급망", ("공급중단","공급차질","공급사 변경","대체투입","납기","재고","생산차질","원료수급")),
        ("사업재편", ("매각 협상","우선협상","인수","매각","분할","합병","철수","거래종결","신설법인","지분취득")),
        ("투자·공장", ("투자","신규시설투자","증설","신설","공장","생산능력","양산","가동중단","생산중단")),
        ("신제품·시장", ("출시","수출","납품","사업화","기술개발","개발 완료","고객사","생산 개시","양산 돌입")),
        ("인허가·규제", ("변경허가","환경영향","사업계획승인","인허가","시정명령","행정처분","조사개시","반덤핑","상계관세")),
        ("기술·제품", ("특허 출원","특허심판","상표 출원","디자인 출원","형식승인","리콜","제작결함","결함조사","시제품","실증","양산 적용")),
        ("자금·거래", ("PRS","유상증자","회사채","자금조달","리파이낸싱","보조금","지원금","신용등급 하향","신용등급 상향")),
        ("수주·발주", ("신규 계약","신규 수주","단일판매","낙찰","입찰공고","공급계약","계약 체결","계약 해지","고객사 변경","물량","수주")),
        ("소송·분쟁", ("소송 제기","제소","가처분","판결","특허심판","분쟁 개시")),
        ("인사·조직", ("내정","조직개편","대표이사 선임","임원 선임","사장 교체","퇴임")),
    ]
    hard_change_re = re.compile(
        r"최초|첫\s|신규|증설|신설|변경|중단|철수|매각|인수|협상|우선협상|분할|합병|조직개편|내정|잠정합의|임단협|파업|쟁의|"
        r"생산계획|생산조정|생산라인|대체투입|공급차질|공급중단|변경허가|사업계획승인|환경영향|시정명령|조사개시|"
        r"반덤핑|상계관세|특허심판|특허 출원|상표 출원|디자인 출원|형식승인|리콜|제작결함|결함조사|PRS|유상증자|"
        r"회사채|자금조달|리파이낸싱|신규 수주|낙찰|입찰공고|계약 해지|고객사 변경|소송 제기|가처분|판결|"
        r"대표이사 선임|임원 선임|사장 교체|퇴임|투자|공급|계약|납품|출시|수출|사업화|개발|고객사|생산 개시|양산 돌입|준공", re.I)
    noise_re = re.compile(
        r"검색|바로가기|안내|설명회|개최 알림|주간 동향|주간 입찰|자료실|상세보기|정기보고|실적발표|월간동향|"
        r"행사|캠페인|수상|채용|교육생 모집|사회공헌|기부|봉사|홍보대사|체험|진로탐색|청소년|희망드림|"
        r"세이브더칠드런|수수료 지원|달력 제작|회계감사 용역|국제민간항공기구|유가보조금 관리 규정|보증제도|명품보증|보증대상|프로모션|브랜드 캠페인|고객 혜택|기재정정|첨부정정", re.I)
    diag={k:0 for k in ("input","invalid","noise","outside_window","no_hard_change","no_signal_pattern","no_company","untrusted_source","duplicate","rows","coverage_checked","prior_coverage","diversity_skip","surfaced")}
    diag["sample_no_hard_change"]=[]
    diag["sample_no_signal_pattern"]=[]
    # Convert multiple public recall notices for one tracked company into one
    # verification lead. Individual public notices are never labelled as scoops.
    recall_groups={}
    for item in primary:
        if item.get("signalType")!="official_recall_notice":
            continue
        dt=parse_dt(item.get("published"))
        if dt.year<2000 or dt<now-timedelta(days=30) or dt>now+timedelta(hours=6):
            continue
        for company in (item.get("companies") or target_hits(item.get("title",""))):
            recall_groups.setdefault(company,[]).append(item)
    recall_clusters=[]
    for company,records in recall_groups.items():
        unique={}
        for rec in sorted(records,key=lambda r:parse_dt(r.get("published"))):
            unique[(rec.get("title") or "").strip()]=rec
        records=list(unique.values())
        if len(records)<2:
            continue
        dates=[parse_dt(r.get("published")) for r in records]
        defects="; ".join(f"{parse_dt(r.get('published')).strftime('%m/%d')} {r.get('title','')}" for r in records)
        newest=max(dates)
        recall_clusters.append({
            "title":f"{company}, 최근 30일간 리콜 공지 {len(records)}건…대상 차종·결함 부위는",
            "url":records[-1].get("url") or "https://car.go.kr/ri/stat/list.do",
            "published":newest.isoformat(),
            "sourceName":"자동차리콜센터(국토교통부·자동차안전연구원)",
            "officialLabel":"자동차리콜센터","querySite":"car.go.kr",
            "sourceGroup":"자동차·결함","official":True,"preScoop":True,"directSource":True,
            "companies":[company],"signalType":"recall_cluster",
            "summary":"공식 리콜현황 목록에서 확인한 최근 공지: "+defects,
            "recallItems":[{"title":r.get("title"),"published":r.get("published"),"url":r.get("url")} for r in records]
        })
    lead_input=[x for x in primary if x.get("signalType")!="official_recall_notice"]+recall_clusters
    rows=[]; seen=set()
    for x in lead_input:
        diag["input"]+=1
        title=str(x.get("title") or "").strip()
        url=str(x.get("url") or "").strip()
        if not title or not url:
            diag["invalid"]+=1; continue
        # A public recall notice is useful for follow-up reporting, but the published
        # notice itself must not be surfaced as a scoop lead.
        if x.get("signalType")=="official_recall_notice":
            diag["noise"]+=1; continue
        # Company newsroom releases announce public facts; they are not pre-publication
        # signals. Keep them out of the lead queue and use them only as source material.
        source_name=str(x.get("sourceName") or "")
        group_hint=source_group(x)
        public_company_source=(group_hint=="기업" and bool(x.get("official")))
        public_release_url=bool(re.search(r"newsroom\\.|/newsroom/|/pr/|/press/|/press-release",url,re.I))
        if re.search(r"뉴스룸|보도자료|press release|newsroom",source_name,re.I) or public_company_source or public_release_url:
            diag["noise"]+=1; continue
        if noise_re.search(title):
            diag["noise"]+=1; continue
        dt=parse_dt(x.get("published"))
        age_h=(now-dt).total_seconds()/3600
        if dt.year < 2000 or age_h < -6 or age_h > PRIMARY_LOOKBACK_DAYS*24:
            diag["outside_window"]+=1; continue
        body=title+" "+str(x.get("summary") or "")
        direct_procurement=bool(x.get("procurementSignal") and x.get("directSource") and group_is_procurement(x))
        if not hard_change_re.search(title) and not direct_procurement:
            diag["no_hard_change"]+=1
            if len(diag["sample_no_hard_change"])<12:
                diag["sample_no_hard_change"].append({"title":title,"source":x.get("sourceName") or x.get("officialLabel") or "","group":source_group(x)})
            continue
        if re.search(r"\d+\s*년\s*만에|지난해|전년|누적\s*생산|정기\s*준공|준공식", title) and not re.search(r"신규|증설|변경|중단|매각|협상|분할|합병|생산계획|공급차질|리콜|결함|소송|내정|조직개편|투자|신제품|출시|고객사|양산|생산 개시", title):
            diag["no_hard_change"]+=1; continue
        hits=[(label,terms) for label,terms in signal_patterns if any(term.lower() in body.lower() for term in terms)]
        if not hits:
            diag["no_signal_pattern"]+=1
            if len(diag["sample_no_signal_pattern"])<12:
                diag["sample_no_signal_pattern"].append({"title":title,"source":x.get("sourceName") or x.get("officialLabel") or "","group":source_group(x)})
            continue
        companies=target_hits(body)
        if x.get("corpName"):
            companies=list(dict.fromkeys(target_hits(x.get("corpName"))+companies))
        qcompany=COMPANY_BY_DOMAIN.get(str(x.get("querySite") or "").lower())
        if qcompany:
            companies=list(dict.fromkeys([qcompany]+companies))
        direct_procurement=bool(x.get("procurementSignal") and x.get("directSource") and group_is_procurement(x))
        if not companies and not direct_procurement:
            diag["no_company"]+=1; continue
        group=source_group(x)
        if group=="기타" and not x.get("officialLabel"):
            diag["untrusted_source"]+=1; continue
        if group=="조달" and re.search(r"청소년|진로|체험|기부|후원|사회공헌|달력|홍보|주간 입찰",title,re.I):
            diag["noise"]+=1; continue
        matched=hits[0][0] if hits else ("수주·발주" if direct_procurement else "산업 신호")
        signal_terms=[term for label,terms in hits for term in terms if term.lower() in body.lower()]
        if direct_procurement and not signal_terms:
            signal_terms=["구매규격 사전공개"]
        concrete_numbers=list(dict.fromkeys(NUM_RE.findall(body)))[:4]
        score=min(24,len(signal_terms)*4)+min(8,len(concrete_numbers)*2)+(8 if companies else 2)+4
        key=(url,re.sub(r"[^가-힣A-Za-z0-9]","",title).lower())
        if key in seen:
            diag["duplicate"]+=1; continue
        seen.add(key)
        rows.append({"raw":x,"title":title,"url":url,"date":dt,"sourceGroup":group,"kind":matched,
            "companies":companies,"signalTerms":signal_terms,"numbers":concrete_numbers,"score":score})
    rows.sort(key=lambda r:(r["score"],r["date"].isoformat()),reverse=True)
    diag["rows"]=len(rows)
    out=[];used_companies=set();used_groups=set()
    for row in rows[:max(limit,12)]:
        diag["coverage_checked"]+=1
        x=row["raw"]
        try:
            prior=coverage_search(x)
        except Exception:
            prior=[]
        source_dt=row["date"]
        # Any strong same-event media match means this is already a public story,
        # even when the article followed the original public announcement.
        if any(event_match_score(x,h)>=0.76 for h in prior):
            diag["prior_coverage"]+=1
            continue
        co=(row["companies"][0] if row["companies"] else "공기업 조달")
        if co in used_companies or row["sourceGroup"] in used_groups:
            diag["diversity_skip"]+=1
            continue
        questions={
            "노사·생산":["합의·생산조정이 확정됐나. 적용 시점과 대상 사업장은 어디인가?","생산량·근무형태·협력사 물량에 실제 변화가 있나?"],
            "공급망":["변경 대상 부품·소재와 적용 시점은 언제인가?","기존 공급사·납기·재고 또는 생산계획에 어떤 변화가 생기나?"],
            "사업재편":["협상·이사회·계약 단계가 어디까지 진행됐나?","대상 자산·지분·금액·종결 조건은 무엇인가?"],
            "투자·공장":["계획이 검토·승인·착공 중 어느 단계인가?","투자액·생산능력·가동 시점이 기존 계획과 어떻게 다른가?"],
            "인허가·규제":["원문상 대상 사업장·품목·적용 시점은 무엇인가?","해당 회사의 실제 비용·생산·수출 영향은 어느 정도인가?"],
            "기술·제품":["출원·인증·실증이 새로 확인된 것인가. 출원일·공개일은 언제인가?","실제 제품 적용·양산·고객사 검증 단계까지 진행됐나?"],
            "자금·거래":["조달·거래의 확정 여부와 사용 목적은 무엇인가?","금액·상대방·만기·담보 등 조건에서 기존과 달라진 점이 있나?"],
            "수주·발주":["입찰·계약의 수요자·물량·기간·추정금액은 무엇인가?","해당 회사가 참여·수주했는지 별도 확인 가능한가?"],
            "소송·분쟁":["당사자·청구취지·쟁점·절차 단계는 무엇인가?","생산·판매·기술 적용·손익에 직접 영향을 주는가?"],
            "인사·조직":["인선·조직 변경이 확정됐나. 적용 시점과 담당 사업은 무엇인가?","전임자·조직 개편과 최근 투자·사업 변경이 연결되는가?"],
            "결함·안전":["두 리콜의 대상 차종·생산기간·대수가 겹치는가?","각 공지의 결함 부품·시정개시일·조치 방법은 무엇인가?","같은 날 공지된 배경이나 공통 부품·공급망 이슈가 있는지 회사와 국토부에 확인할 수 있나?"],
        }.get(row["kind"],["원문상 확정된 변경 사항과 적용 시점은 무엇인가?","기존 계획·생산·고객사·손익에 어떤 차이가 생기나?"])
        out.append({
            "id":hashlib.sha1((row["url"]+"|lead").encode()).hexdigest()[:12],
            "title":row["title"],"url":row["url"],"published":row["date"].isoformat(),
            "sourceName":x.get("sourceName") or x.get("officialLabel") or "공식자료",
            "originalSource":x.get("officialLabel") or x.get("sourceName") or "원자료 검색",
            "sourceGroup":row["sourceGroup"],"kind":row["kind"],"companies":row["companies"][:5],
            "summary":str(x.get("summary") or "")[:500],"signalTerms":row["signalTerms"][:6],"numbers":row["numbers"],
            "leadScore":row["score"],"leadStrength":"강" if row["score"]>=24 else "보통",
            "verification":"취재 단서 — 단독 확정 아님",
            "coverageStatus":"최근 180일 언론 검색에서 강한 동일 사건 매칭 없음. 전체 미보도 확정은 아니므로 추가 확인 필요.",
            "whyLead":("공식 리콜현황에서 같은 제조사의 리콜 공지가 최근 30일 내 복수 확인됐다. 공지 자체는 공개 정보이며 단독으로 볼 수 없다. 차종·생산기간·대수·결함 부품의 공통점이 실제로 있는지 확인할 때만 후속 기사 가치가 생긴다." if x.get("signalType")=="recall_cluster" else "구체적인 기업 변화 신호를 원자료 검색에서 포착했다. 발표 사실 자체를 단독으로 보지 말고, 기존 계획 대비 달라진 부분을 확인해야 한다."),
            "questions":questions,"recallItems":x.get("recallItems",[]),"directSource":bool(x.get("directSource") or x.get("receiptNo")),"preScoop":bool(x.get("preScoop"))
        })
        used_companies.add(co);used_groups.add(row["sourceGroup"])
        diag["surfaced"]+=1
        if len(out)>=limit:
            break
    return out,diag


def build_public_signals(primary, dart_rows, now, limit=10):
    """Expose public-source follow-ups in a separate lane; never imply exclusivity."""
    out=[];seen=set()
    cutoff=now-timedelta(days=PRIMARY_LOOKBACK_DAYS)

    # Public recall notices are useful for follow-up reporting, but the notice itself
    # is already public. Group by make and date to avoid duplicate cards.
    recall_groups={}
    for x in primary:
        if x.get("signalType")!="official_recall_notice":
            continue
        title=str(x.get("title") or "").strip()
        dt=parse_dt(x.get("published"))
        if not title or dt.year<2000 or dt<cutoff or dt>now+timedelta(hours=6):
            continue
        companies=x.get("companies") or target_hits(title)
        if not companies:
            continue
        company=companies[0]
        key=(company,dt.date().isoformat())
        g=recall_groups.setdefault(key,{"company":company,"date":dt,"items":[],"url":x.get("url",""),"source":x.get("sourceName") or "자동차리콜센터"})
        clean_title=re.sub(r"\s*(?:\.\.\.|…)\s*-->?$","",title).strip()
        if clean_title not in g["items"]:
            g["items"].append(clean_title)
    for g in recall_groups.values():
        titles=g["items"][:8]
        out.append({
            "id":hashlib.sha1(("public-recall|"+g["company"]+"|"+g["date"].date().isoformat()).encode()).hexdigest()[:12],
            "signalGroup":"자동차·결함","kind":"공개 리콜 공지","companies":[g["company"]],
            "title":f'{g["company"]}, {g["date"].strftime("%-m월 %-d일")} 리콜 공지 {len(g["items"])}건',
            "published":g["date"].isoformat(),"sourceName":g["source"],"url":g["url"],
            "details":titles,
            "verification":"공개 원자료 · 단독 아님",
            "coverageStatus":"공식 리콜 목록에 공개된 사실입니다. 공지 자체를 단독으로 취급하지 않습니다.",
            "whyFollowup":"동일 제조사의 리콜 공지를 묶어 대상 대수·생산기간·국내 판매 차종·반복 결함 여부를 추가 확인할 수 있습니다.",
            "questions":["대상 대수와 생산기간, 국내 판매 차량은 몇 대인가?","최근 12개월 동일 제조사의 유사 부품·결함 리콜이 반복됐나?","시정 조치율과 부품 공급·수리 대기 기간은 어느 정도인가?"]
        })

    # Material DART filings appear here as public facts to investigate, not as scoops.
    dart_terms={
        "회사분할결정":"사업재편","합병":"사업재편","영업양수도":"사업재편","영업정지":"생산·사업 중단",
        "생산중단":"생산·사업 중단","신규시설투자":"투자·공장","유상증자":"자금·거래",
        "전환사채":"자금·거래","교환사채":"자금·거래","신주인수권부사채":"자금·거래",
        "타법인주식및출자증권취득결정":"지분·투자","대표이사":"인사·조직","임원":"인사·조직",
        "이사선임":"인사·조직","주요사항보고서(소송)":"소송·분쟁","소송":"소송·분쟁",
        "단일판매ㆍ공급계약체결":"공급계약 추적","자기주식처분결정":"지분·자금"
    }
    for d in dart_rows:
        corp=str(d.get("corpName") or "").strip()
        report=str(d.get("reportName") or "").strip()
        if not corp or not report or not target_hits(corp):
            continue
        dt=parse_dt(d.get("date") or d.get("published") or "")
        if dt.year<2000 or dt<cutoff or dt>now+timedelta(hours=6):
            continue
        if any(k in report for k in ("투자설명서","증권신고서","사업보고서","반기보고서","분기보고서","기타시장안내")):
            continue
        # Treasury-share disposition filings are often routine employee/management
        # compensation. Do not fill the public monitoring lane with them by default.
        if re.search(r"자기주식|자사주",report):
            continue
        group=next((label for term,label in dart_terms.items() if term in report),None)
        if not group:
            continue
        key=(corp,report,dt.date().isoformat())
        if key in seen:
            continue
        seen.add(key)
        correction=("기재정정" in report or "첨부정정" in report)
        url=str(d.get("url") or "")
        out.append({
            "id":hashlib.sha1(("public-dart|"+"|".join(key)).encode()).hexdigest()[:12],
            "signalGroup":group,"kind":report,"companies":[corp],
            "title":f"{corp} {report}"+(" — 변경 항목 대조 필요" if correction else ""),
            "published":dt.isoformat(),"sourceName":"DART","url":url,"details":[],
            "verification":"공개 공시 · 단독 아님",
            "coverageStatus":"공개 공시입니다. 미보도·단독으로 표시하지 않습니다." if not correction else "정정 공시입니다. 최초 공시 대비 변경된 항목을 확인해야 합니다.",
            "whyFollowup":"공시 원문에서 실제로 바뀐 숫자·일정·사업 범위를 확인한 뒤, 기존 보도와 회사 설명을 교차 확인해야 합니다.",
            "questions":["최초 공시와 비교해 실제 변경된 항목은 무엇인가?","생산·투자·계약·재무에 미치는 정량적 영향은 얼마인가?","이 변경으로 추가 확인해야 할 고객사·사업장·적용 일정이 있는가?"]
        })
    out.sort(key=lambda x:(x["published"],x["signalGroup"]),reverse=True)
    # Prefer distinct companies so one issuer does not flood the monitoring lane.
    final=[];used=set()
    for x in out:
        company=(x.get("companies") or [""])[0]
        if company in used:
            continue
        final.append(x);used.add(company)
        if len(final)>=limit:
            break
    return final

def main():
    data=json.loads(DATA.read_text(encoding="utf-8")) if DATA.exists() else []
    dart=json.loads(DART.read_text(encoding="utf-8")).get("items",[]) if DART.exists() else []
    numeric=json.loads(NUM.read_text(encoding="utf-8")).get("items",[]) if NUM.exists() else []
    archive=json.loads(ARCHIVE.read_text(encoding="utf-8")) if ARCHIVE.exists() else []
    pre_scoop=json.loads(Path("pre_scoop.json").read_text(encoding="utf-8")).get("items",[]) if Path("pre_scoop.json").exists() else []
    now=datetime.now(KST)
    primary=[]
    pattern_frequency={}
    dart_suppression={"correction":0,"outside_lookback_window":0,"contract_reports_seen":0,"contract_reports_routine":0,"contract_reports_eligible":0,"routine_equity_compensation":0}
    for row in data:
        if row.get("global"):continue
        title=str(row.get("title") or "")
        body=title+" "+str(row.get("summary") or "")
        if any(k in title.lower() for k in ("단독","본지","단독취재","단독 확인")):
            for label,n in exclusive_pattern_hits(body):
                pattern_frequency[label]=pattern_frequency.get(label,0)+n


    for category,query in PRIMARY_QUERY_SETS:
        for x in google_rss(category,query,max_items=8):
            if x.get("official"):primary.append(x)

    for d in dart:
        corp_name=str(d.get("corpName") or "").strip()
        report=str(d.get("reportName") or "")
        if not report or not corp_name:continue
        if any(k in report for k in ("투자설명서","증권신고서","사업보고서","반기보고서","분기보고서","기타시장안내")):continue
        # Corrective filings are not new events by themselves. The changed fields
        # must be compared with the original filing before they can support a scoop.
        if "기재정정" in report or "첨부정정" in report:
            dart_suppression["correction"]+=1
            continue
        ddt=parse_dt(d.get("date",""))
        if ddt<now-timedelta(days=PRIMARY_LOOKBACK_DAYS):
            dart_suppression["outside_lookback_window"]+=1
            continue
        material=any(k in report for k in ("회사분할","영업정지","생산중단","신규시설투자","타법인주식및출자증권취득결정","유상증자","영업양수도","합병","대표이사","임원","이사선임","소송","주요사항보고","자기주식처분결정","자기주식취득","주식소각","금전대여","채무인수","전환사채","교환사채"))
        contract_report=("단일판매ㆍ공급계약체결" in report)
        if contract_report:dart_suppression["contract_reports_seen"]+=1
        if ("기재정정" in report or "첨부정정" in report) and not material:continue
        if not HARD_SIGNAL_RE.search(report):continue
        if not target_hits(corp_name):continue
        blob,nums=dart_fact(d,numeric,force_document=contract_report)
        joined_dart=str(d.get("signalText",""))+" "+blob
        if contract_report:
            party=near_fact(blob,"계약상대방")
            party_specific=bool(party and not re.search(r"해당없음|미정|비공개|불특정|기타|없음|-",party,re.I) and len(party.strip())>=2)
            contract_units=bool(re.search(r"\b(?:GWh|MWh|MW|GW|kV|km|톤|만대|천대)\b|물량|생산능력|연간 공급|공급 기간|납기",joined_dart,re.I))
            unusual_contract=any(k in joined_dart for k in ("첫","최초","신규 고객","신규 고객사","신규 시장","북미","미국","유럽","중동","사우디","호주","독점","장기 공급","신규 프로젝트"))
            amount=won_amount(blob)
            material_amount=amount>=100_000_000_000 if amount else False
            if not (unusual_contract or contract_units or (material_amount and party_specific)):
                dart_suppression["contract_reports_routine"]+=1
                continue
            dart_suppression["contract_reports_eligible"]+=1
        # Small treasury-share transfers used for routine executive bonuses are governance notices,
        # not industrial scoops. Keep material ownership/control changes for later verification.
        if re.search(r"자기주식|자사주",report) and re.search(r"임원.*상여|상여금|임직원.*보상",joined_dart) and won_amount(blob)<10_000_000_000:
            dart_suppression["routine_equity_compensation"]+=1
            continue
        primary.append({
            "category":"공시","title":dart_title(corp_name,report,blob,nums),
            "url":d.get("url",""),"published":ddt.isoformat(),"sourceName":"DART",
            "summary":(d.get("signalText","")+" "+blob)[:12000],
            "official":True,"officialLabel":"DART","receiptNo":d.get("receiptNo"),
            "dartNumbers":nums,"rawReport":report,"corpName":corp_name
        })

    for p in pre_scoop:
        if p.get("title") and p.get("url") and p.get("preScoop"):
            primary.append(p)

    lead_signals,lead_diagnostics=build_lead_signals(primary,data,now,limit=12)
    public_signals=build_public_signals(primary,dart,now,limit=10)
    candidates=[];seen=set();drop_stats={"noise":0,"stale_pre_scoop":0,"routine_regulatory":0,"relevance":0,"generic":0,"specificity":0,"prior_coverage":0,"procurement":0,"routine_contract":0,"low_score":0,"low_score_rescued":0,"other":0,"accepted":0}
    for x in sorted(primary,key=lambda z:z.get("published",""),reverse=True):
        title=(x.get("title") or "").strip()
        joined=title+" "+x.get("summary","")
        # Public recall-list entries are already published notices, not scoop candidates.
        if x.get("signalType")=="official_recall_notice":
            drop_stats.setdefault("routine_public_notice",0)
            drop_stats["routine_public_notice"]+=1
            continue
        # Company newsroom announcements are public releases, not unpublished scoops.
        public_company_release=(source_group(x)=="기업" and bool(x.get("official")))
        public_release_url=bool(re.search(r"newsroom\\.|/newsroom/|/pr/|/press/|/press-release",str(x.get("url") or ""),re.I))
        if public_company_release or public_release_url or (re.search(r"뉴스룸|press release|newsroom",str(x.get("sourceName") or ""),re.I) and source_group(x)=="기업"):
            drop_stats.setdefault("public_company_release",0)
            drop_stats["public_company_release"]+=1
            continue
        # Pre-scoop search intentionally looks 21 days back for raw signals, but only
        # the recent 10-day window is eligible to enter the actual scoop-candidate queue.
        # Otherwise an old official press release can reappear as a "new" scoop.
        if x.get("preScoop"):
            source_dt=parse_dt(x.get("published"))
            if source_dt.year < 2000 or (now-source_dt).total_seconds() > PRIMARY_LOOKBACK_DAYS*86400:
                drop_stats["stale_pre_scoop"]+=1
                continue
        # Completed inspection-result press releases are ordinary published news,
        # not an unpublished scoop lead. Keep "inspection begins" signals, but never
        # elevate a generic "results announced" headline into a scoop.
        if x.get("preScoop") and re.search(r"(?:산업안전|근로|특별)?\s*(?:안전)?(?:감독|점검|단속).{0,18}(?:결과|발표)", title):
            drop_stats["routine_regulatory"]+=1
            continue
        if not title or NOISE_RE.search(title) or WEAK_RE.search(title):
            drop_stats["noise"]+=1;continue
        companies=target_hits(joined)
        if x.get("corpName"):
            direct=target_hits(x.get("corpName"))
            companies=list(dict.fromkeys(direct+companies))
        query_company=COMPANY_BY_DOMAIN.get(str(x.get("querySite") or "").lower())
        if query_company:
            companies=list(dict.fromkeys([query_company]+companies))
        numbers=list(dict.fromkeys((x.get("dartNumbers") or [])+NUM_RE.findall(joined)))[:8]
        kind=candidate_kind(title,x.get("category",""))
        if not relevant_primary(x,companies,kind,joined):
            drop_stats["relevance"]+=1;continue

        source_group_now=source_group(x)
        # Reject generic administrative pages and evergreen notices masquerading as new scoops.
        generic_doc=("상세보기" in title or "행정규칙" in title) and not companies
        evergreen=any(k in title for k in ("교육생 모집","세미나","포럼","행사","캠페인","신년인사회","채용","모집공고","참가신청"))
        if generic_doc or evergreen:
            drop_stats["generic"]+=1;continue
        # A scoop needs a concrete reporting handle, not just an industry keyword.
        source_text=(title+" "+x.get("summary",""))
        if source_group_now=="협회" and not any(k in source_text for k in ("정책","제도","건의","조사","통계","수급","가격","통상","반덤핑","공동대응","회원사","입찰","낙찰","프로젝트","수주","공급망","인증","기술기준","표준","안전","수출","수입")):
            continue
        concrete_hooks=0
        concrete_hooks+=min(2,len(NUM_RE.findall(source_text)))
        concrete_hooks+=sum(1 for k in ("이사회","임원","대표이사","선임","퇴임","생산계획","생산라인","공급사","대체투입","매각","인수","분할","합병","공장","증설","인증","형식승인","리콜","결함","환경영향","인허가","특허","상표","디자인","수주","입찰","낙찰","관세","반덤핑","소송","판결","심판","자금조달","유상증자","채권","RSU") if k in source_text)
        if not companies and concrete_hooks<2:
            drop_stats["specificity"]+=1;continue
        if source_group_now!="DART" and source_group_now!="기타" and concrete_hooks<1:
            drop_stats["specificity"]+=1;continue
        newsroom=newsroom_matches(title,data)
        archive_matches=[]
        for r in archive:
            ev=event_match_score(x,{"title":r.get("title",""),"summary":r.get("summary") or "","sourceName":r.get("sourceName"),"published":r.get("published")})
            if ev>=0.72:archive_matches.append((ev,r))
        archive_matches.sort(key=lambda z:z[0],reverse=True)

        coverage=[]
        best_news=max([event_match_score(x,r) for r in newsroom] or [0])
        if best_news<0.78:coverage=coverage_search(x)

        combined=[]
        for r in newsroom:
            combined.append({"source":r.get("sourceName"),"title":r.get("title"),"published":r.get("published"),"url":r.get("url"),"_sim":similarity(title,r.get("title","")+" "+(r.get("summary") or ""))})
        for r in coverage:
            combined.append({"source":r.get("sourceName"),"title":r.get("title"),"published":r.get("published"),"url":r.get("url"),"_sim":similarity(title,r.get("title","")+" "+(r.get("summary") or ""))})
        for _,r in archive_matches[:12]:
            combined.append({"source":r.get("sourceName") or "archive","title":r.get("title"),"published":r.get("published"),"url":r.get("url"),"_sim":similarity(title,r.get("title","")+" "+(r.get("summary") or ""))})
        combined.sort(key=lambda z:z.get("_sim",0),reverse=True)
        strong=[]
        for r in combined:
            ev=event_match_score(x,{"title":r.get("title",""),"summary":r.get("summary") or "","published":r.get("published"),"sourceName":r.get("source")})
            r["_event"]=ev
            if ev>=0.76:strong.append(r)
        # A newly posted disclosure is not a new scoop when the same event was already
        # reported before the disclosure date. This is the decisive novelty gate.
        primary_dt=parse_dt(x.get("published"))
        def is_prior_coverage(r):
            if not r.get("published"):return False
            rdt=parse_dt(r.get("published"))
            if rdt<=primary_dt:return True
            # DART/KIND-style records often carry only a calendar date and are parsed
            # at midnight. A same-day news report is therefore still prior coverage.
            if primary_dt.hour==0 and primary_dt.minute==0 and rdt.date()==primary_dt.date():
                return True
            return False
        prior_strong=[r for r in strong if is_prior_coverage(r)]
        if prior_strong:
            drop_stats["prior_coverage"]+=1;continue

        # Procurement feeds contain many welfare, education, PR, event and routine service
        # tenders. Those are not industry scoop signals even when a tracked company is named.
        procurement_text=(title+" "+x.get("summary","")).lower()
        procurement_noise=(
            "세이브더칠드런","청소년","진로","교육","봉사","사회공헌","기부","복지","캠프",
            "체험","축제","행사","캠페인","홍보","전시","포럼","세미나","멘토링","장학",
            "희망드림","아동","학교","유치원","어린이","지역사회","문화","체육"
        )
        procurement_material=(
            "공장","생산","설비","기자재","변압기","hvdc","케이블","송전","배전","ess",
            "충전기","충전소","원전","발전","터빈","풍력","태양광","배터리","철강","강관",
            "차량","자동차","타이어","산업단지","건설","토목","건축","플랜트","배관","터미널",
            "선박","항만","물류센터","데이터센터","시스템","소프트웨어","인증시험","시험장"
        )
        if source_group_now=="조달":
            if any(k in procurement_text for k in procurement_noise):
                continue
            if not any(k in procurement_text for k in procurement_material):
                continue
            # A company name alone is never enough; the tender must expose an
            # industrial asset, physical demand, infrastructure or material service.
            procurement_specific=sum(1 for k in procurement_material if k in procurement_text)
            if procurement_specific<1:
                drop_stats["procurement"]+=1;continue

        # Routine contracts are not useful scoop candidates unless they carry a new customer/market,
        # unusual project, large amount, or specific physical quantity.
        if kind=="계약·수주":
            large=any(re.search(r"(조원|억원)",str(n)) and float(re.sub(r"[^0-9.]","",str(n).replace(",","")) or 0)>=1000 for n in numbers)
            unusual=any(k in joined for k in ("첫","최초","북미","미국","유럽","중동","사우디","호주","대규모","장기","독점","신규 고객","신규 고객사","신규 시장","프로젝트"))
            detailed=any(k in joined for k in ("GWh","MWh","MW","GW","kV","km","톤","만대","물량","생산능력","연간 공급","공급 기간","납기"))
            party=near_fact(x.get("summary",""),"계약상대방")
            party_specific=bool(party and not re.search(r"해당없음|미정|비공개|불특정|기타|없음|-",party,re.I) and len(party.strip())>=2)
            if not (unusual or detailed or (large and party_specific)):
                drop_stats["routine_contract"]+=1;continue

        # A true personnel/patent scoop must originate in an authoritative or company source.
        if kind in {"특허·기술","상표·디자인","인사","결함·리콜","인증·형식승인","인허가·환경","소송·분쟁"} and source_tier(x)<2:
            drop_stats["other"]+=1;continue

        age_h=max(0,(now-parse_dt(x.get("published"))).total_seconds()/3600)
        tier=source_tier(x)
        concrete=min(18,len(numbers)*3)
        hard=min(12,sum(1 for k in ("분할","합병","매각","인수","철수","신설","조직개편","대표이사","임원","선임","취임","特許","특허","출원","등록","고시","법안","수주","계약","投资","투자","증설","공장","생산") if k in joined))
        freshness=12 if age_h<=24 else 8 if age_h<=72 else 3
        specificity=min(20,concrete*3)
        change=min(16,hard*2)
        source_weight=12 if tier>=3 else 6
        novelty=8 if not archive_matches else 0
        kind_weight=8 if kind in {"결함·리콜","인증·형식승인","인허가·환경","소송·분쟁","인사","특허·기술","상표·디자인","사업재편","정책·규제","통상·관세"} else 4
        source_boost={
            "자동차·결함":14,"환경·인허가":14,"법령·입법":12,"특허":12,"KIND":10,"조달":10,
            "통상·분쟁":12,"해외기관":10,"정부":9,"협회":8,"노사·현장":12,"정책·감독":11,"공기업·시장":11,"공기업·조달":13,"법원·분쟁":14,"중앙노동위":14,"고용노동":13,"공장·산업단지":15,"인증·안전":13,"R&D·기술":13,"재무·신용":12,"기업":8,"지역·투자":10,"DART":3,"기타":0
        }.get(source_group_now,0)
        exclusive_signal=sum(2 for k in ("내정","잠정합의","생산조정","생산계획","생산중단","공급중단","대체투입","공급사 변경","공급망","이사회","임원","퇴임","매각 협상","우선협상","거래종결","자금조달","보조금","지원금","인허가","환경영향","조사개시","소송 제기","특허심판","리콜","제작결함") if k in source_text)
        learned_signal=sum(min(3,pattern_frequency.get(label,0)//3) for label,_ in exclusive_pattern_hits(source_text))
        score=min(98,30+freshness+specificity+change+source_weight+novelty+kind_weight+source_boost+min(12,exclusive_signal)+min(6,learned_signal))

        score_floor_applied=False
        if score<66:
            material_kinds={"결함·리콜","인증·형식승인","인허가·환경","소송·분쟁","인사","특허·기술","상표·디자인","사업재편","정책·규제","통상·관세","신사업·투자"}
            authoritative_groups={"DART","KIND","특허","조달","자동차·결함","환경·인허가","법령·입법","통상·분쟁","해외기관","지역·투자","협회","노사·현장","정책·감독","공기업·시장","공기업·조달","법원·분쟁","공장·산업단지","인증·안전","R&D·기술","중앙노동위","고용노동","재무·신용"}
            # Rescue only a concrete material event from an authoritative source,
            # after the prior-coverage gate. Routine equity disposals/contracts do not qualify.
            material_primary=(tier>=3 and bool(companies) and kind in material_kinds
                and source_group_now in authoritative_groups
                and bool(re.search(r"물적분할|인적분할|회사분할|영업정지|생산중단|조업정지|가동중단|신규시설투자|증설|사업부문|영업양수도|합병|매각|인수|철수|대표이사.{0,12}(?:선임|취임)|특허(?:출원|등록|심판)|환경영향평가|사업계획승인|행정처분|반덤핑|상계관세|형식승인|제작결함",source_text,re.I)))
            if material_primary:
                score=66
                score_floor_applied=True
                drop_stats["low_score_rescued"]+=1
            else:
                drop_stats["low_score"]+=1
                continue
        if not (numbers or kind in {"결함·리콜","인증·형식승인","인허가·환경","소송·분쟁","인사","특허·기술","상표·디자인","정책·규제","사업재편","통상·관세"} or any(k in joined for k in ("공장","법인","조직개편","대표이사","특허","고시","법안","리콜","결함","인증","인허가","소송","판결","관세"))):continue
        # Public-source freshness and specificity are mandatory for a real scoop candidate.
        if source_group_now=="기타" and not x.get("officialLabel"):continue
        if not companies and kind in {"특허·기술","상표·디자인","인사","결함·리콜","인증·형식승인"}:continue

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
            why=f"특허·상표 원자료에서 새 브랜드·디자인 출원 신호를 포착했습니다. 실제 차종·제품·신사업 출시와 연결되는지 먼저 확인할 가치가 있습니다."
        elif kind=="인사":
            why=f"원자료에서 경영진·이사회 변화를 먼저 포착했습니다. 동일 인선의 강한 언론 매칭이 없어 직책·담당 사업·인선 배경을 확인할 가치가 있습니다."
        elif kind=="특허·기술":
            why=f"특허 원자료에서 새로운 출원·등록 신호를 포착했습니다. 기존 보도에 없는 기술적 세부와 양산·상용화 연결 여부를 확인할 수 있는 후보입니다."
        elif kind=="정책·규제":
            why=f"정부·입법 원자료에서 제도 변화를 먼저 포착했습니다. 시행일·적용 범위·업계 대응을 공개 기사보다 먼저 확인할 수 있는 후보입니다."
        elif kind=="통상·관세":
            why=f"통상·관세 원자료에서 판정·조사·품목분류 변화를 먼저 포착했습니다. 국내 출입처의 수출·원가 영향과 대응을 확인할 가치가 있습니다."
        elif kind=="사업재편":
            why=f"공시 원문에서 사업부문·법인·생산거점의 변화를 포착했습니다. 기존 계획과 달라진 구체적 조건을 확인할 필요가 있습니다."
        else:
            why=f"{x.get('officialLabel') or x.get('sourceName')} 원자료에서 구체적 사업 사실을 포착했습니다. 국내 언론에서 동일 사실의 강한 매칭이 없어 선점 취재 후보로 분류했습니다."

        questions={
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
            "조달·발주":["예산·물량·납기·발주기관은 어디인가?","참여 예상 기업과 낙찰 일정은 언제인가?","기존 계획에 없던 신규 수요인지 확인할 수 있는가?"]
        }.get(kind,["원자료의 핵심 조건은 무엇인가?","동일 사실의 언론 보도가 정말 없는가?","출입처에서 어떤 사실을 전화로 교차확인할 수 있는가?"])
        matches=[{k:v for k,v in r.items() if k!="_sim" and k!="_event"} for r in combined[:6] if r.get("source")]
        history=[{"title":r.get("title"),"source":r.get("sourceName"),"published":r.get("published")} for _,r in archive_matches[:3]]
        sources=[{"source":x.get("sourceName"),"label":x.get("officialLabel") or x.get("sourceName"),"title":x.get("title"),"url":x.get("url"),"published":x.get("published")}]

        drop_stats["accepted"]+=1
        candidates.append({
            "id":hashlib.sha1((x.get("url","")+"|"+headline).encode()).hexdigest()[:12],
            "kind":kind,"beat":beat_for(joined),"title":headline,"score":score,
            "scoreFloorApplied":score_floor_applied,
            "scoreNote":"공식 원자료의 중대 사건이나 수치 누락으로 원문 재확인이 필요함" if score_floor_applied else "일반 점수 기준 충족",
            "status":"단독 유력" if not strong and score>=86 and tier>=3 and concrete_hooks>=2 else "단독 후보",
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
            "sourceGroup":source_group(x),
            "exclusivePatternHits":exclusive_pattern_hits(source_text),
            "reportingPath":questions[:3]
        })

    kind_rank={"결함·리콜":10,"인증·형식승인":10,"인허가·환경":9,"소송·분쟁":9,"인사":8,"특허·기술":8,"상표·디자인":7,"사업재편":7,"정책·규제":7,"통상·관세":6,"신사업·투자":6,"조달·발주":5,"계약·수주":3}
    candidates.sort(key=lambda z:(z["score"],kind_rank.get(z["kind"],1),-z["coverageCount"],len(z.get("numbers") or []),z.get("firstSeenAt","")),reverse=True)

    final=[];used_primary=set();used_keys=set();used_groups=set()
    for c in sorted(candidates,key=lambda z:(z["score"],{"결함·리콜":10,"인증·형식승인":10,"인허가·환경":9,"소송·분쟁":9,"인사":8,"특허·기술":8,"상표·디자인":7,"사업재편":7,"정책·규제":7,"통상·관세":6,"신사업·투자":6,"조달·발주":5,"계약·수주":3}.get(z["kind"],1)),reverse=True):
        key=(tuple(sorted(c.get("companies") or [])),re.sub(r"[^가-힣A-Za-z0-9]","",c.get("title",""))[:45])
        if key in used_keys:continue
        sg=c.get("sourceGroup","기타")
        if sg=="DART" and sum(1 for x in final if x.get("sourceGroup")=="DART")>=2:continue
        if sg in used_groups and len(used_groups)<8 and sg in {"특허","KIND","조달","자동차·결함","환경·인허가","해외기관","정부","기업","지역·투자","협회","노사·현장","통상·분쟁","법령·입법"}:continue
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
            if c.get("sourceGroup")=="DART" and sum(1 for x in final if x.get("sourceGroup")=="DART")>=2:continue
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
        "generatedAt":now.isoformat(),"windowDays":PRIMARY_LOOKBACK_DAYS,"mode":"primary-source-first",
        "counts":{
            "primaryHits":len(primary),"candidates":len(final),
            "uncovered":sum(1 for x in final if x.get("coverageCount",0)==0),
            "alreadyCoveredOne":sum(1 for x in final if x.get("coverageCount",0)>0),
            "coverageLookbackDays":COVERAGE_LOOKBACK_DAYS,
            "beats":len(set(x["beat"] for x in final)),
            "strongCandidates":sum(1 for x in final if x.get("status")=="단독 유력")
        },
        "items":final,
        "leadSignals":lead_signals,
        "leadSignalCount":len(lead_signals),
        "publicSignals":public_signals,
        "publicSignalCount":len(public_signals),
        "leadDiagnostics":lead_diagnostics,
        "sourceHealth":{
            "dart":{"count":len(dart),"status":"ok" if dart else ("error" if (json.loads(DART.read_text(encoding="utf-8")).get("errors") if DART.exists() else []) else "empty"),"errors":(json.loads(DART.read_text(encoding="utf-8")).get("errors",[]) if DART.exists() else [])[:3]},
            "dartNumeric":{
                "count":len(numeric),
                "withNumbers":sum(1 for row in numeric if row.get("numbers")),
                "errorCount":sum(1 for row in numeric if row.get("error")),
                "cacheFallbackCount":sum(1 for row in numeric if row.get("cacheFallback")),
                "maintenanceCount":sum(1 for row in numeric if "status 800" in str(row.get("error","")).lower() or "시스템 점검" in str(row.get("error",""))),
                "errors":[{"company":row.get("corpName"),"report":row.get("reportName"),"error":row.get("error")} for row in numeric if row.get("error")][:3]
            },
            "preScoop":{
                "count":len(pre_scoop),
                "groups":(json.loads(Path("pre_scoop.json").read_text(encoding="utf-8")).get("sourceGroups",{}) if Path("pre_scoop.json").exists() else {}),
                "sourceDiagnostics":(json.loads(Path("pre_scoop.json").read_text(encoding="utf-8")).get("sourceDiagnostics",{}) if Path("pre_scoop.json").exists() else {}),
                "directSourceDiagnostics":(json.loads(Path("pre_scoop.json").read_text(encoding="utf-8")).get("directSourceDiagnostics",{}) if Path("pre_scoop.json").exists() else {})
            }
        },
        "sourceSuppressionStats":{"dart":dart_suppression},
        "coverageSearchDiagnostics":COVERAGE_SEARCH_DIAGNOSTICS,
        "dropStats":drop_stats,
        "sourceGroups":{g:sum(1 for x in final if x.get("sourceGroup")==g) for g in sorted({x.get("sourceGroup","기타") for x in final})},
        "note":"단독감은 중요 뉴스 랭킹이 아닙니다. 실제 단독 기사에서 반복되는 내부 의사결정·생산계획·공급변경·이사회·인사·거래구조·자금조달·규제/인허가 선행 신호를 찾고, 구체적 사실·최근성·원자료성·미보도 여부·실제 전화 확인 가능성을 함께 평가합니다. 일반 공지·행정규칙·행사·채용·단순 계약 규모만으로는 올리지 않습니다."
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    print(f"primary-source scoop scout: {len(primary)} primary hits -> {len(final)} selective unreported candidates")

if __name__=="__main__":main()
