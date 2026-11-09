"""경쟁지 [단독] 자동 역추적: 레이더가 기사보다 먼저 같은 회사·같은 사건 낱말을 잡았는지(자동 후보, 미검토).

- 입력: digests/reverse_trace_latest.json(업종 [단독] 제목 색인)과 레이더 기억 — 기자 전용 저장소의 감시 결과(처음 본 시각)와
  tools/clues.json(공개 원자료 단서, 게시일).
- 판정은 사람이 하는 Y/P/N(exclusive_reverse_trace.py, 기사 전문·원자료 비교)과 다르다. 여기서는 '먼저 잡은 후보 있음 /
  같은 회사 항목만 / 없음'만 자동으로 세고, 원천별로 몇 건을 몇 시간 먼저 잡았는지 모은다. 같은 사건인지는 열어 봐야 한다.
- 결과는 기자 전용 저장소(reverse-check)로만(레이더 기억에 비공개 항목이 있다). 공개 로그는 건수만.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import re
import sys
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

KST = dt.timezone(dt.timedelta(hours=9))
SCHEMA = "reverse_check/v1"
WINDOW_DAYS = 30
LOOKBACK_DAYS = 60   # how far before an article a radar item can count
FEEDS = ["us-litigation", "partner-filings", "trade-remedy", "kr-official", "kr-signals", "us-comments", "page-watch",
         "trademarks", "assembly-bills", "us-recalls", "scoop-screen", "us-epa", "kr-fuel", "overseas-awards",
         "kr-insolvency", "kr-energy", "kr-building", "overseas-registry", "kr-local", "kr-workforce", "kr-stacks",
         # 11-03 추가 감시(이벤트 모양이 같다: id·company·kind·text|title·detectedAt·url) — 역추적·기자 기사 대조가 이 감시들도 본다
         "us-osha", "us-state-env", "kr-labor", "india-filings", "dart-counterparty", "union-notices", "council-minutes",
         # 11-04: 지분·자사주 변동(임원 집단 보고·자기주식 처분 결정) — KG스틸 자사주 임직원 보상 기사가 '없음'이었다
         "governance"]
LABEL = {"us-litigation": "미국 소송·판결", "partner-filings": "해외 파트너 공시", "trade-remedy": "무역구제·미국 관보",
         "kr-official": "공장등록·관보", "kr-signals": "공정위·한전·산업부", "us-comments": "미 연방 의견서", "page-watch": "해외 공식 페이지",
         "trademarks": "상표 출원", "assembly-bills": "국회 법안", "us-recalls": "미국 리콜", "scoop-screen": "단독 후보 심사",
         "us-epa": "미국 EPA 인증", "kr-fuel": "국내 연비 신고", "overseas-awards": "해외 발주처 낙찰",
         "kr-insolvency": "협력사 회생·파산", "kr-energy": "전기위·원안위", "kr-building": "공장 부지 건축허가", "overseas-registry": "해외 법인 등기", "kr-local": "지자체 고시·공고",
         "kr-workforce": "사업장 인력(국민연금)", "kr-stacks": "굴뚝 측정(가동 신호)", "clues": "공개 원자료 단서(DART 등)",
         "us-osha": "미국 OSHA 점검·위반", "us-state-env": "미국 주 환경 허가·공고", "kr-labor": "노동위 회의", "india-filings": "인도 법인 공시",
         "dart-counterparty": "타사 공시 속 출입처", "union-notices": "노조 성명·보도자료", "council-minutes": "지방의회 회의록",
         "governance": "지분·자사주 변동"}
# Group-level names: an article about 포스코 and a radar item about 포스코홀딩스 concern the same group.
GROUP = {"한국타이어앤테크놀로지": "한국타이어", "S-Oil": "S-OIL", "현대자동차": "현대차", "제네시스": "현대차", "현대차(제네시스)": "현대차", "포스코홀딩스": "포스코", "엘에스일렉트릭": "LS일렉트릭",
         "아우디코리아": "아우디", "폭스바겐코리아": "폭스바겐", "BMW코리아": "BMW", "메르세데스-벤츠 코리아": "벤츠", "혼다코리아": "혼다",
         "효성중공업(관련)": "효성중공업", "일진전기(관련)": "일진전기", "OCI홀딩스": "OCI", "세아홀딩스": "세아제강", "LS지주": "LS",
         # 아우디는 폭스바겐그룹 브랜드: 10-26 '[단독] 아우디, 미국서 Q4 e-트론 9048대 리콜…SK온 배터리'는 회사가 '폭스바겐·SK온'으로
         # 분류된다. 리콜 항목 회사는 '아우디'라, 기사 전에 잡았더라도 회사가 달라 '없음'이 됐을 것이다. 대조에서는 한 그룹으로 본다.
         # (이 기사 자체는 '없음'이 맞다: 10-21은 NHTSA 접수일이고, 아우디를 보는 미국 리콜 감시는 기사 뒤 10-28에 생겼다.)
         "아우디": "폭스바겐", "아우디코리아": "폭스바겐"}
# 리콜 원보고서 공급사 칸·결함 설명의 한국 부품사 영문 이름 → 대조용 회사 이름(기사 회사 분류는 부품사 이름으로도 붙는다)
SUPPLIERS = [(re.compile(r"SK\s*(?:On|Battery|Innovation)", re.I), "SK온"), (re.compile(r"LG\s*(?:Energy\s*Solution|Chem)", re.I), "LG에너지솔루션"),
             (re.compile(r"Samsung\s*SDI", re.I), "삼성SDI"), (re.compile(r"Hyundai\s*Mobis|\bMobis\b", re.I), "현대모비스"),
             (re.compile(r"\bMando\b", re.I), "HL만도"), (re.compile(r"Hyundai\s*Wia", re.I), "현대위아"), (re.compile(r"Hyundai\s*Transys", re.I), "현대트랜시스"),
             (re.compile(r"Hankook", re.I), "한국타이어"), (re.compile(r"Kumho", re.I), "금호타이어"), (re.compile(r"Nexen", re.I), "넥센타이어"),
             (re.compile(r"LS\s*(?:Cable|Electric)", re.I), "LS"), (re.compile(r"POSCO", re.I), "포스코")]


def suppliers_in(*texts):
    t = " ".join(str(x or "") for x in texts)
    return [name for rx, name in SUPPLIERS if rx.search(t)]
# (concept, Korean headline words, words in radar items — Korean or English)
CONCEPTS = [
    ("소송·판결", r"소송|제소|항소|불복|패소|승소|판결|법원|배상", r"v\. United States|\bIn re\b|lawsuit|complaint|appeal|opinion|court|소송|판결|항소|법원|Sustaining|Remand"),
    # 레이더 쪽 영문 낱말은 단어 경계로: 'quota'가 'quotation'(ASX 'Application for quotation of securities')에, 'subsid'가
    # 'subsidiary'에 걸렸다(10-31: 현대차 인도 관세 분쟁 [단독]이 아라푸라 증권 상장 신청과 묶임). 'Light-Duty·Heavy-Duty' 차량의 duty도
    # 관세가 아니다(같은 날 고친 뒤 그 기사가 EPA 'Tier 4 … Light-Duty and Medium-Duty Vehicles' 의견서와 다시 묶임).
    ("관세·무역구제", r"관세|상계|반덤핑|덤핑|무역구제|세이프가드|보조금", r"countervail|anti-?dumping|"
     r"(?<!light-)(?<!light )(?<!heavy-)(?<!heavy )(?<!medium-)(?<!medium )\bdut(?:y|ies)\b(?!-free)|tariff|subsid(?!iar)|관세|덤핑|쿼터|\bquotas?\b"),
    ("리콜·결함", r"리콜|결함|화재|발화|시정조치", r"recall|defect|fire|리콜|결함"),
    ("특허·상표", r"특허|상표|브랜드|명칭", r"patent|PTAB|trademark|상표|특허"),
    ("지분·합작·거래", r"지분|합작|매각|인수|철수|정리|양도|합병", r"equity|joint venture|disposal|acquisition|exit|transaction|investment in|양도|합병|지분|merger"),
    ("공장·생산", r"공장|증설|감산|생산|가동|라인|투자", r"plant|factory|공장|고용|주생산품|production|capacity"),
    ("수주·입찰", r"수주|낙찰|입찰|공급계약|계약", r"tender|award|bid|입찰|낙찰|supply agreement|contract|offtake"),
    ("건축·증설", r"증설|신설|착공|짓는다|짓기로|신축|증축|새 공장", r"건축허가|신축|증축"),
    ("회생·파산", r"회생|파산|법정관리|부도|워크아웃", r"회생|파산|포괄적 금지명령"),
    ("허가·원전", r"허가|원전|원자력|발전사업|해상풍력|계속운전|원안위", r"허가|원자력|발전사업|해상풍력|계속운전|원안의결|심의"),
    # 11-09: 영문 회사 이름 끝의 Ltd.가 법인 설립으로 잡혔다(LS전선 누리이음 자회사 [단독] ↔ 노동위 'LS Cable & System Ltd.' 재심 사건).
    # 영국 법인 등기 항목은 글에 '법인 설립 Companies House'가 있어 LIMITED·LTD 없이도 맞는다.
    ("법인 설립", r"법인|현지법인|자회사|설립", r"법인 설립|incorporat|Companies House"),
    # 11-04: 「주주가치 높인다며 산 자사주…KG스틸, 임직원 보상에 쓴다」가 자기주식 처분 결정과 '자사주' 한 낱말만 겹쳐 '같은 회사 항목만'이었다
    ("자사주·주주환원", r"자사주|자기주식|주주환원|주식\s*소각|주주가치", r"자기주식|자사주|treasury|share buyback|소각"),
    ("인력·고용", r"인력|감원|희망퇴직|구조조정|채용|고용|직원|인원|감축", r"국민연금 가입자|인력 감소|인력 증가|취득|상실"),
    ("가동·중단", r"가동|중단|셧다운|정지|휴업|멈춰|멈춘|재가동|조업", r"가동 중단|멈춤|재가동|새 배출구|배출구"),
    ("입법·규제", r"법안|입법|개정안|국회|규제|시행령|입법예고", r"법률안|개정안|입법예고|bill|regulation|rule"),
    ("보육·복지", r"어린이집|보육|직장", r"nursery|child ?care|daycare|어린이집"),
    # 굴뚝 배출허용기준 초과(실시간 측정값) ↔ 대기오염·배출 기사
    ("대기 배출", r"배출|대기오염|오염물질|미세먼지|질소산화물|황산화물|굴뚝|TMS", r"배출허용기준|대기 배출|질소산화물|황산화물"),
    ("가격", r"가격|값|인상|인하", r"MSRP|price|\$\s?\d|가격"),
    ("배터리", r"배터리|셀|전지", r"battery|cell|배터리"),
    # 레이더 쪽은 차량 항목(EPA 연비 인증·VIN 새 모델명·국내 연비 신고)의 낱말만: 맨 'EPA'·'range'는 EPA 규제 의견서·영문 공시에도 나온다
    # (10-30: 머니투데이 '[단독]현대차 미래항공·새만금 사업 가속..신차로 본업 경쟁력↑'이 'EPA 의견서 Tier 4 Phase-in'과 묶였다).
    ("신차·인증", r"신차|출시|투입|연식|연비|인증|주행거리|부분변경|신형|트림", r"연비|새 모델|model year|주행거리|1회 충전|연식"),
]
# 판결 기사(패소·승소 등)는 판결 항목만 같은 사건으로 센다. 같은 회사의 다른 소송 접수는 다른 사건번호일 수 있다
# (10-28: 포스코 패소 기사 = 국제무역법원 24-00006 판결(Slip Op. 26-131), 레이더가 먼저 본 것은 1:26-cv-04229 접수).
RULING_TITLE = re.compile(r"패소|승소|판결|기각|인용|선고")
RULING_ITEM = re.compile(r"\bopinion\b|Sustain|Remand|Affirm|Revers|holding|판결|결정 유지|환송", re.I)
# 출입 업종에서 너무 흔한 사건 낱말: 이것 하나만 겹치면 같은 사건 근거로 약하다(10-28 첫 실행: '배터리'·'공장'만 겹친 오탐 2건).
# '신차·인증'도 약하다: 현대차·기아는 새 모델·연식 항목이 늘 있어서, 모델명·EPA 같은 낱말이 함께 겹쳐야 같은 사건으로 본다(10-30).
# '특허·상표'도 약하다: 현대차·기아는 미국 'Schedule A' 상표 위조품 소송이 늘 있어, 상표 기사마다 묶였다
# (10-31: 쿠키뉴스 'E-pit 상표권 현대엔지니어링 이전' [단독] ↔ Hyundai Motor Company v. The Partnerships … Schedule A). 상표명·특허 이름 같은 낱말이 함께 겹쳐야 한다.
WEAK_CONCEPTS = {"공장·생산", "배터리", "가격", "신차·인증", "특허·상표"}
# 11-08 정확도: 30일 '먼저 잡은 후보' 11건을 열어 보니 4~5건이 엉뚱한 연결이었다 — 사건 개념 하나만 겹친 긴 영문 공시
# (Aptiv 10-Q ↔ 제네시스PE GS건설 지분, Verisk 10-Q ↔ 현대차 중노위 소송, EMAT S-1 ↔ 포스코인터 인니 법인)와 다른 소송
# (POSCO v. United States ↔ 포스코인터 러시아 강제집행). 이제 '먼저'는 ① 같은 사건 낱말(지명 빼고)·한·영 대응 품목·쟁점·판결↔판결이
# 하나 이상 겹치거나 ② 사건 개념 점수(강 2·약 1)가 3 이상일 때만이다. 한·영 대응이 있어야 미국 관보(영문)와 한국 기사(강관·후판)가 이어진다.
SPECIFICS = [("강관", r"강관", r"\bpipe|tube|tubular"), ("후판", r"후판", r"\bplate\b|cut-to-length"), ("열연", r"열연", r"hot-rolled"),
             ("냉연", r"냉연", r"cold-rolled"), ("도금강판", r"도금", r"corrosion-resistant|galvaniz"), ("석도강판", r"석도", r"tin mill"),
             ("변압기", r"변압기", r"transformer"), ("철근", r"철근", r"rebar|reinforcing bar"), ("선재", r"선재", r"wire rod"),
             ("스테인리스", r"스테인리스", r"stainless"), ("전선", r"전선|케이블", r"\bcable|\bwire\b"), ("타이어", r"타이어", r"\btires?\b"),
             ("탄소배출권", r"탄소배출권|배출권", r"\bKAUs?\b|K-?ETS|emission (?:permit|allowance)"), ("전기요금", r"전기요금|전력요금", r"electricity"),
             ("특별시장상황", r"특별시장상황|PMS", r"particular market situation")]
SPECIFIC_RX = [(name, re.compile(ko), re.compile(en, re.I)) for name, ko, en in SPECIFICS]
# 회사 이름 속 품목 낱말은 사건 낱말이 아니다(11-09: 기사 'LS전선'의 전선 ↔ 항목 'LS Cable & System'의 cable로 '먼저'가 됨).
# 기사 쪽은 그 기사의 회사 이름을 지운 제목, 항목 쪽은 아래 영문 회사 이름을 지운 글로 품목을 맞춘다.
EN_COMPANY = re.compile(r"LS\s*Cable(?:\s*&\s*System)?|Taihan\s*Cable|(?:Kumho|Hankook|Nexen)\s*Tires?", re.I)
NOT_COMPANY = [("제네시스", re.compile(r"제네시스\s*(?:PE|프라이빗|자산운용|랩)"))]   # 사모펀드 제네시스PE는 제네시스(현대차) 아님
GENERIC_WORDS = {"공장", "배터리", "미국", "생산", "가격", "투자", "계약", "중국", "한국", "글로벌", "사업", "신규"}
# 장소가 있는 항목(건축허가·굴뚝·지자체 공고·국민연금 현장·공장등록·지방의회·미국 주 환경·OSHA)은 기사 제목에 같은 지역 이름이
# 있어야 사건 대조에 넣는다. 11-04 기자 기사 대조: 구미 진평동 공장 건축허가가 'LS전선·LS마린솔루션, 504MW 태안해상풍력 해저케이블
# 일정 확보'와, 광양 태인동 공장 건축허가가 'OCI그룹, 반도체소재사업본부·AX조직 신설'과 '허가·건축·신설' 낱말만으로 묶였다.
# 기사 제목에 지역 이름이 없으면(예: '포스코 2열연') 놓칠 수 있다 — 정확도를 우선한다(같은 회사 항목으로는 남는다).
PLACE_SOURCES = {"kr-building", "kr-stacks", "kr-local", "kr-workforce", "kr-official", "council-minutes", "us-state-env", "us-osha"}
# 흔한 낱말과 겹치는 지명(예산·음성·상주·장성)은 뺐다
KR_PLACES = ["포항", "광양", "당진", "울산", "울주", "온산", "여수", "대산", "서산", "아산", "천안", "화성", "평택", "광명", "광주", "구미",
             "김천", "영천", "경주", "창원", "김해", "양산", "거제", "통영", "사천", "진주", "부산", "인천", "시흥", "안산", "김포", "파주",
             "이천", "여주", "용인", "안성", "오산", "청주", "충주", "제천", "진천", "군산", "익산", "전주", "완주", "순천", "목포", "나주",
             "함평", "영암", "해남", "무안", "곡성", "고흥", "보성", "담양", "봉화", "석포", "태안", "서천", "보령", "대전", "세종", "원주",
             "춘천", "강릉", "동해", "삼척"]
US_PLACES = [("조지아", r"Georgia|조지아"), ("앨라배마", r"Alabama|앨라배마"), ("루이지애나", r"Louisiana|루이지애나"), ("테네시", r"Tennessee|테네시"),
             ("텍사스", r"Texas|텍사스"), ("캘리포니아", r"California|캘리포니아"), ("오하이오", r"Ohio|오하이오"), ("미시간", r"Michigan|미시간"),
             ("인디애나", r"Indiana|인디애나"), ("켄터키", r"Kentucky|켄터키"), ("사우스캐롤라이나", r"South Carolina|사우스캐롤라이나"),
             ("노스캐롤라이나", r"North Carolina|노스캐롤라이나"), ("애리조나", r"Arizona|애리조나"), ("일리노이", r"Illinois|일리노이"),
             ("펜실베이니아", r"Pennsylvania|펜실베이니아"), ("미시시피", r"Mississippi|미시시피"), ("버지니아", r"(?<!West )Virginia|(?<!웨스트)버지니아")]
US_PLACE_RX = [(name, re.compile(rx, re.I)) for name, rx in US_PLACES]
PLACE_WORDS = set(KR_PLACES) | {name for name, _ in US_PLACES}   # 지명만 겹친 것은 같은 사건 낱말로 치지 않는다(11-08)


# 기사 종류(제목 낱말, 첫 일치) — 레이더가 놓친 기사를 어떤 원천으로 메울지 보려고 묶는다. 순서가 판정 순서다
# ('금호타이어, 롯데카드와 제휴카드 출시'는 계약이 아니라 제품·마케팅, '대미 타이어 수출 25% 감소…관세 복병'은 통계·시장).
KINDS = [("실적", r"영업익|영업이익|매출|순이익|순손실|실적|흑자|적자|어닝"), ("인사·조직", r"사장|회장|대표이사|임원|인사|선임|승진|조직|본부|영입|CEO"),
         ("노사·안전", r"노조|파업|임단협|교섭|노사|사망|사고|산재|중대재해"),
         # 11-04 첫 화면: '고려아연 자사주 공개매수 손배소'가 '공개'로, '동국제강, 하나카드와 맞손'이 '카드'로 제품·마케팅에 들어갔다
         ("논란·법적", r"불법|위반|논란|의혹|소송|손배|제소|항소|판결|승소|패소|법원|명령|검찰|과징금|제재|리콜|결함"),
         ("자본·지배구조", r"자사주|배당|지분|유상증자|주주|공개매수|인수|매각|경영권"),
         ("제품·마케팅", r"출시|할인|프로모션|신차|사전예약|시승|세일|캠페인"),
         ("투자·공장", r"공장|투자|증설|착공|준공|라인|짓는다|부지|설비|가동"),
         ("수주·계약", r"수주|계약|공급|MOU|협약|제휴|합작|파트너|낙찰|맞손|협력|턴키"),
         ("통계·시장", r"수출|수입|재고|판매량|판매|점유율|생산량|가격|시황|감소|증가|최저|최고"),
         ("정책·통상", r"관세|규제|법안|보조금|정부|무역|통상|정책")]
KIND_RX = [(k, re.compile(rx)) for k, rx in KINDS]


def kind_of(title):
    return next((k for k, rx in KIND_RX if rx.search(title or "")), "기타")


def places_in(text):
    t = str(text or "")
    return {p for p in KR_PLACES if p in t} | {name for name, rx in US_PLACE_RX if rx.search(t)}
STOP = {"단독", "기자", "업계", "관계자", "국내", "최대", "최초", "올해", "내년", "전략", "본격", "사업", "추진", "확대", "주목", "위해",
        "이유", "속도", "결국", "다시", "직접", "모두", "현대", "그룹"}


def canon(name):
    n = re.sub(r"\(.*?\)", "", str(name or "")).strip()
    return GROUP.get(str(name or "").strip(), GROUP.get(n, n))


def parse_time(v):
    v = str(v or "").strip()
    if not v:
        return None
    try:
        if re.fullmatch(r"\d{8}", v):
            return dt.datetime(int(v[:4]), int(v[4:6]), int(v[6:8]), tzinfo=KST)
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
            return dt.datetime.fromisoformat(v).replace(tzinfo=KST)
        t = dt.datetime.fromisoformat(v.replace("Z", "+00:00"))
        return t if t.tzinfo else t.replace(tzinfo=KST)
    except ValueError:
        return None


def mem(source, iid, companies, text, seen, url=None, origin=None):
    when = parse_time(seen)
    names = sorted({canon(c) for c in companies if isinstance(c, str) and c.strip()})
    if not when or not names:
        return None
    return {"source": source, "id": str(iid), "companies": names, "text": re.sub(r"\s+", " ", str(text or ""))[:500], "seen": when, "url": url,
            **({"origin": str(origin)[:40]} if origin else {})}


# 단서 원천 이름 중 영문 코드(11-03 역추적 화면: '공개 원자료 단서(OVERSEAS)')
ORIGIN_KO = {"OVERSEAS": "해외 원자료", "DART_METRIC": "DART 수치", "CUSTOMS_FIVE": "관세청 수출입"}


def label_of(m):
    """원천 이름. 공개 원자료 단서는 단서마다 실제 원천(DART·미 연방관보·나라장터 등)을 붙인다 — 11-03 역추적: 미국 관보 상계관세 문서가
    '공개 원자료 단서(DART 등)'로 보였다."""
    if m.get("source") == "clues" and m.get("origin"):
        return f"공개 원자료 단서({ORIGIN_KO.get(m['origin'], m['origin'])})"
    return LABEL.get(m["source"], m["source"])


def split_names(v):
    return [x for x in re.split(r"[·,/]", str(v or "")) if x.strip()]


def memory(docs, clues, errors=None):
    """Radar items with the time the radar first had them. Each feed is read by its own adapter; a shape surprise in one feed
    is recorded (feed name and exception type only) and does not stop the others."""
    out = []
    for name, fn in ADAPTERS:
        try:
            got = []
            fn(docs.get(name) or {} if name != "clues" else clues or {}, lambda m: m and got.append(m))
            out += got
        except Exception as e:  # noqa: BLE001 — one feed's shape must not stop the measurement
            if errors is not None:
                errors[name] = type(e).__name__
    return out


def _litigation(d, add):
    for x in d.get("cases") or []:
        add(mem("us-litigation", x.get("id"), x.get("beat") or [], f"{x.get('caseName')} {x.get('summary') or ''} {x.get('category') or ''}", x.get("firstSeen") or x.get("dateFiled"), x.get("url")))
    for x in d.get("opinions") or []:
        add(mem("us-litigation", x.get("id"), x.get("beat") or [], f"{x.get('caseName')} opinion {x.get('holding') or ''}", x.get("firstSeen") or x.get("dateFiled"), x.get("url")))
    for x in d.get("itc") or []:
        add(mem("us-litigation", x.get("id"), [n.get("company") for n in x.get("named") or []], f"ITC 337 patent {x.get('title')}", x.get("firstSeen") or x.get("date"), x.get("url")))


def _partners(d, add):
    for x in d.get("items") or []:
        add(mem("partner-filings", x.get("id"), x.get("beat") or [], f"{x.get('filer')} {x.get('title')} {x.get('snippet') or ''}", x.get("firstSeen") or x.get("date"), x.get("url")))


def _trade(d, add):
    for x in d.get("federalRegister") or []:
        # 관보 표에서 읽은 세율도 글에 넣는다(11-09): 기사 제목의 '4.20%'가 레이더 원문에도 있는지 본다. 500자에서 잘리지 않게 결정문 목차 앞에.
        table = x.get("rateTable") or {}
        rates = [v.get("rate") for v in (table.get("rates") or {}).values() if isinstance(v, dict)] + [table.get("othersRate")]
        rate_text = " ".join(f"{float(v):.2f}%" for v in rates if isinstance(v, (int, float)))
        add(mem("trade-remedy", x.get("id"), [n.get("company") for n in x.get("named") or []],
                f"{x.get('title')} duty {rate_text} {' '.join(x.get('memoTopics') or [])}", x.get("firstSeen") or x.get("date"), x.get("url")))


def _official(d, add):
    for x in d.get("events") or []:
        add(mem("kr-official", x.get("id"), [x.get("company")], f"공장 {x.get('kind')} {x.get('text')}", x.get("detectedAt"), None))
    for x in d.get("factories") or []:
        if x.get("registeredOn"):
            add(mem("kr-official", x.get("id"), [x.get("company")], f"공장 새 등록 {x.get('cmpnyNm')} {x.get('mainProductCn') or ''}", x.get("firstSeen") or x.get("registeredOn"), None))


def _eia(d, add):
    for x in d.get("eia") or []:
        add(mem("kr-official", x.get("id"), [x.get("company")], f"공장 환경영향평가 {x.get('stage')} {x.get('name')} {x.get('category') or ''} 증설 투자",
                x.get("firstSeen"), x.get("url")))


def _signals(d, add):
    for x in d.get("decisions") or []:
        add(mem("kr-signals", x.get("id"), [m.get("company") for m in x.get("mentions") or []], f"공정위 {x.get('name')} {x.get('action') or ''}", x.get("fileDate") or x.get("decidedOn"), x.get("url")))
    for x in d.get("kepco") or []:
        add(mem("kr-signals", x.get("id"), [x.get("company")], f"한전 입찰 {x.get('name')}", x.get("noticeDate"), None))
    for x in d.get("motir") or []:
        add(mem("kr-signals", x.get("id"), x.get("companies") or [], f"산업부 {x.get('title')}", x.get("date"), x.get("url")))
    for x in d.get("ftcPress") or []:
        add(mem("kr-signals", x.get("id"), x.get("companies") or [], f"공정위 {x.get('title')}", x.get("date"), x.get("url")))
    for x in d.get("briefing") or []:
        add(mem("kr-signals", x.get("id"), x.get("companies") or [], f"{x.get('ministry')} {x.get('title')}", x.get("date"), x.get("url")))
    for x in d.get("g2bAwards") or []:
        add(mem("kr-signals", x.get("id"), x.get("companies") or [], f"나라장터 낙찰 {x.get('title')}", x.get("date"), None))
    for x in d.get("province") or []:
        add(mem("kr-signals", x.get("id"), x.get("companies") or [], f"{x.get('site')} {x.get('title')}", x.get("date"), x.get("url")))


def _comments(d, add):
    for x in d.get("items") or []:
        add(mem("us-comments", x.get("id"), [x.get("company")], f"{x.get('agency')} 의견서 {x.get('docketTitle') or ''}", x.get("firstSeen") or x.get("postedDate"), x.get("url")))


def _pages(d, add):
    for x in d.get("events") or []:
        a = x.get("added") or {}
        added = " ".join(str(v) for vs in (a.values() if isinstance(a, dict) else [a]) for v in (vs if isinstance(vs, list) else [vs]))
        add(mem("page-watch", f"{x.get('pageId')}:{x.get('detectedAt')}", [x.get("company")], f"{x.get('label')} {added}", x.get("detectedAt"), x.get("url")))


def _marks(d, add):
    for x in d.get("filings") or []:
        add(mem("trademarks", x.get("id"), [x.get("company")], f"상표 {x.get('title')}", x.get("firstSeen") or x.get("applicationDate"), None))


def _recalls(d, add):
    for x in d.get("recalls") or []:
        add(mem("us-recalls", x.get("id"), [w.get("name") for w in x.get("why") or []] + [w.get("beat") for w in x.get("why") or []]
                + suppliers_in(x.get("supplierBox"), x.get("defect"), x.get("component")),
                f"recall 리콜 {x.get('models')} {x.get('component')} {x.get('defect') or ''} {x.get('supplierBox') or ''}", x.get("firstSeen") or x.get("received"), x.get("url")))


def _epa(d, add):
    for v in d.get("vehicles") or []:
        add(mem("us-epa", v.get("id"), [v.get("company")], f"EPA 연비 인증 {v.get('kind')} {v.get('year')} {v.get('make')} {v.get('model')} {v.get('baseModel') or ''}"
                f"{' 주행거리 range ' + str(v.get('range')) if v.get('range') else ''}", v.get("firstSeen"), v.get("url")))


def _vin(d, add):
    for v in d.get("vpicModels") or []:
        add(mem("us-epa", v.get("id"), [v.get("company")], f"VIN 새 모델명 등록 {v.get('make')} {v.get('model')} {' '.join(str(y) for y in v.get('years') or [])} 연식",
                v.get("firstSeen"), v.get("url")))


def _fuel(d, add):
    for v in d.get("vehicles") or []:
        add(mem("kr-fuel", v.get("id"), [v.get("company")], f"연비 신고 표시연비 {v.get('kind')} {v.get('maker')} {v.get('model')} {v.get('year')}년 {v.get('fuel') or ''}"
                f"{' 1회 충전 주행거리 ' + str(v.get('range')) if v.get('range') else ''}", v.get("firstSeen"), v.get("url")))


def _awards(d, add):
    for x in d.get("items") or []:
        if not x.get("company"):
            continue
        add(mem("overseas-awards", x.get("id"), x.get("companies") or [x.get("company")],
                f"해외 낙찰 award {x.get('source')} {x.get('buyer')} {x.get('buyerCountry') or ''} {x.get('title')} {' '.join(x.get('winners') or [])}",
                x.get("firstSeen"), x.get("url")))


def _investigations(d, add):
    for x in d.get("investigations") or []:
        add(mem("us-recalls", x.get("id"), [w.get("name") for w in x.get("why") or []] + [w.get("beat") for w in x.get("why") or []],
                f"NHTSA 결함조사 defect investigation {x.get('kind')} {x.get('models')} {x.get('component')} {x.get('subject') or ''} 결함 조사",
                x.get("firstSeen") or x.get("opened"), x.get("url")))


def _insolvency(d, add):
    for x in d.get("events") or []:
        if x.get("tier") == "C":
            continue
        add(mem("kr-insolvency", x.get("id"), [x.get("company"), (x.get("watch") or {}).get("beat")],
                f"회생 파산 {x.get('kind')} {x.get('company')} {(x.get('industry') or {}).get('product') or ''}", x.get("firstSeen") or x.get("posted"), x.get("url")))


def _energy(d, add):
    for x in d.get("items") or []:
        add(mem("kr-energy", x.get("id"), [x.get("company")], f"허가 {x.get('source')} {x.get('kind')} {x.get('title')} {x.get('result') or ''}",
                x.get("firstSeen") or x.get("held"), x.get("url")))


def _building(d, add):
    for x in d.get("permits") or []:
        if x.get("orphan") or x.get("tier") == "C":
            continue  # a plant gone from the list, or a small/neighbouring-lot permit
        add(mem("kr-building", x.get("id"), x.get("companies") or [x.get("company")],
                f"공장 건축허가 {x.get('archGbCdNm') or ''} {x.get('mainPurpsCdNm') or ''} {x.get('plot') or ''} 증설 신축 plant factory",
                x.get("firstSeen") or x.get("permitted"), None))


def _registry(d, add):
    for x in d.get("companies") or []:
        if x.get("tier") not in ("A", "B"):
            continue  # name-only companies (dealers, unrelated firms)
        add(mem("overseas-registry", x.get("id"), [x.get("company")], f"영국 법인 설립 Companies House {x.get('name')} LIMITED",
                x.get("firstSeen") or x.get("created"), x.get("url")))


def _local(d, add):
    for x in d.get("items") or []:
        if x.get("tier") == "C" or not x.get("companies"):
            continue
        add(mem("kr-local", x.get("id"), x.get("companies") or [], f"지자체 고시 공고 {x.get('city')} {x.get('title')} 공장 증설 신축",
                x.get("firstSeen") or x.get("date"), x.get("url")))


def _workforce(d, add):
    # 자사 사업장 인력 변화·탈퇴·새 사업장, 새 공사 현장(A는 하나씩, B는 묶음) — 국민연금 월 자료
    for e in d.get("events") or []:
        words = "공사 현장 신설 증설 신축 착공" if "공사" in str(e.get("kind")) else "인력 고용 공장"
        add(mem("kr-workforce", e.get("id"), [e.get("company")], f"{e.get('kind')} {e.get('text')} {words}", e.get("detectedAt"), None))


STACK_OPS = ("가동 중단", "재가동", "멈춤", "새 배출구", "새 사업장", "빠짐", "목록 보강")


def _stacks(d, add):
    # 굴뚝 측정 가동 신호(사업장 가동 중단·배출구 멈춤·새 배출구·재가동)는 '공장 가동' 사건, 배출허용기준 초과는 '대기 배출' 사건.
    # 사업장 이름의 '공장'(여수1공장·포항1공장)은 사건 낱말이 아니다 — 11-02 철강금속신문 '[단독] 포스코 포항 2열연, 가열로 한 기 더'가
    # 포스코 포항제철소 질소산화물 초과 측정값과 '공장·생산·포항'으로 묶였다.
    for e in d.get("events") or []:
        # 참고(C)·일시적 누락(다시 나타남)은 사건이 아니다 — 11-02 '[단독] 포스코 포항 2열연 가열로'가 이번엔 포항제철소 배출구 135번
        # '목록에서 빠짐 — 이후 다시 나타남'(C)과 묶였다
        if e.get("tier") not in ("A", "B") or "다시 나타남" in str(e.get("text") or ""):
            continue
        kind = str(e.get("kind") or "")
        text = str(e.get("text") or "").replace("공장", "사업장")
        tail = " 공장 가동" if any(k in kind for k in STACK_OPS) else " 대기 배출"
        add(mem("kr-stacks", e.get("id"), [e.get("company")], f"{kind} {text}{tail}", e.get("detectedAt"), None))


def _screen(d, add):
    for x in d.get("candidates") or []:
        add(mem("scoop-screen", x.get("id"), split_names(x.get("company")), x.get("title"), x.get("published") or x.get("filedOn"), x.get("url")))


def _events_of(source):
    """11-03 추가 감시들의 이벤트(A·B만 — C는 참고)."""
    def fn(d, add):
        for e in d.get("events") or []:
            if e.get("tier") not in ("A", "B"):
                continue
            comps = e.get("companies") if isinstance(e.get("companies"), list) else [e.get("company")]
            add(mem(source, e.get("id"), [c for c in comps if c], f"{e.get('kind') or ''} {e.get('text') or e.get('title') or ''}",
                    e.get("detectedAt"), e.get("url")))
    return fn


def _governance(d, add):
    """지분·자사주 변동(공개 공시): 일상(routine) 아닌 것만. 자기주식 처분은 '자사주'·'보상' 낱말로도 찾게 붙인다."""
    for x in d.get("items") or []:
        if x.get("routine"):
            continue
        tags = " ".join(x.get("tags") or [])
        extra = (" 자사주 자기주식 처분" if x.get("kind") == "자사주 처분 결정" else " 임원 지분") + (" 임직원 보상" if "임직원 보상" in tags or "보상" in str(x.get("reason")) else "")
        add(mem("governance", x.get("groupKey") or x.get("receiptNo"), [x.get("company")], f"{x.get('kind')} {x.get('reason') or ''} {tags}{extra}",
                x.get("date"), x.get("url")))


def _clues(d, add):
    for x in d.get("items") or []:
        add(mem("clues", x.get("id"), x.get("companies") or [], x.get("title"), x.get("firstSeen") or x.get("published"), x.get("url"),
                origin=x.get("source")))


ADAPTERS = [("us-litigation", _litigation), ("partner-filings", _partners), ("trade-remedy", _trade), ("kr-official", _official), ("kr-official", _eia),
            ("kr-signals", _signals), ("us-comments", _comments), ("page-watch", _pages), ("trademarks", _marks),
            ("us-recalls", _recalls), ("scoop-screen", _screen), ("us-epa", _epa), ("us-epa", _vin), ("kr-fuel", _fuel), ("overseas-awards", _awards),
            ("us-recalls", _investigations), ("kr-insolvency", _insolvency), ("kr-energy", _energy), ("kr-building", _building),
            ("overseas-registry", _registry), ("kr-local", _local), ("kr-workforce", _workforce), ("kr-stacks", _stacks), ("clues", _clues),
            ("governance", _governance), *[(f, _events_of(f)) for f in ("us-osha", "us-state-env", "kr-labor", "india-filings", "dart-counterparty", "union-notices", "council-minutes")]]


# 기사 제목의 핵심 숫자(세율·금액·규모)가 레이더 원문에도 있는지(11-09): 품목·쟁점 낱말만 겹치면 '같은 분야'일 뿐이다 — 숫자까지
# 같으면 같은 사실일 가능성이 높다(강관 '4.20%' ↔ 관보 표 4.20%), 숫자가 원문에 없으면 같은 분야 다른 사실일 수 있다(도금강판 '70%대').
NUM_RX = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(%|％|조\s*원|억\s*원|조|억|MW|GW|kV|만\s*대|만\s*톤|톤)(대)?")
NUM_UNIT = {"％": "%", "조원": "억", "조": "억", "억원": "억", "만대": "만대", "만톤": "만톤"}


def numbers_in(text):
    """[(값, 단위, 원문, '대' 여부)] — 조는 억으로 바꾼다('1조2000억'은 한 값). 0은 흔해서 뺀다(휴스틸 0%)."""
    both = re.compile(r"(\d[\d,]*)\s*조\s*(\d[\d,]*)\s*억\s*원?")
    out = [(int(m.group(1).replace(",", "")) * 10000 + int(m.group(2).replace(",", "")), "억", m.group(0).strip(), False)
           for m in both.finditer(text or "")]
    t = both.sub(" ", text or "")
    for m in NUM_RX.finditer(t):
        try:
            v = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        unit = re.sub(r"\s+", "", m.group(2))
        if unit in ("조", "조원"):
            v *= 10000
        unit = NUM_UNIT.get(unit, unit)
        if v:
            out.append((v, unit, m.group(0).strip(), bool(m.group(3))))
    return out


def same_numbers(title, text):
    """기사 제목 숫자 중 레이더 원문에도 있는 것: (제목 숫자 원문 목록, 원문에도 있는 것 목록, 비교할 숫자가 원문에 있었는지).
    원문 글에 같은 단위 숫자가 하나도 없으면 '다름'이 아니라 비교 못 함이다(11-09: 세율 없는 단서 글 ↔ 강관 4.20%)."""
    art, item = numbers_in(title), numbers_in(text)
    comparable = any(u2 == unit for _, unit, _, _ in art for _, u2, _, _ in item)
    found = []
    for v, unit, raw, band in art:
        for w, u2, _, _ in item:
            if u2 != unit:
                continue
            if (band and v <= w < v + (10 if unit == "%" else 10 ** math.floor(math.log10(v)))) or (not band and (abs(v - w) < 0.005 if unit == "%" else abs(v - w) <= max(v, w) * 0.01)):
                found.append(raw)
                break
    return [raw for _, _, raw, _ in art], found, comparable


def doc_key(url):
    """같은 원문 문서를 가리키는 열쇠: 미국 관보는 문서 번호(관보 항목·단서·심사가 주소 모양이 달라도 같은 문서), 그 밖은 주소."""
    u = str(url or "").strip()
    m = re.search(r"federalregister\.gov/(?:documents|d|api/v1/documents)/(?:\d{4}/\d{2}/\d{2}/)?(\d{4}-\d{4,6})", u)
    return f"fr:{m.group(1)}" if m else re.sub(r"^https?://|/+$", "", u.split("#")[0])


def nouns(title):
    t = re.sub(r"\[[^\]]*\]|\([^)]*\)|\s+-\s+[^-]{1,40}$", " ", title)
    return {w for w in re.findall(r"[가-힣A-Za-z0-9]{2,}", t) if w not in STOP and not re.fullmatch(r"\d+", w)}


def match(article, items):
    """Best radar item for an article: same group company first seen before publication, ranked by event overlap."""
    pub = parse_time(article.get("published"))
    title = article.get("title") or ""
    comps = {canon(c) for c in article.get("companies") or [] if not any(c == n and rx.search(title) for n, rx in NOT_COMPANY)}
    if not pub or not comps:
        return "회사 미상", None, 0
    concepts = {name for name, ko, _ in CONCEPTS if re.search(ko, title)}
    bare = title
    for c in sorted({*(article.get("companies") or []), *comps}, key=len, reverse=True):
        bare = bare.replace(c, " ")
    words = nouns(title) - comps
    same = [m for m in items if comps & set(m["companies"]) and pub - dt.timedelta(days=LOOKBACK_DAYS) <= m["seen"] < pub]
    tplaces = places_in(title)
    best, best_score = None, 0
    concept_words = {w for w in words if any(name in concepts and re.search(ko, w) for name, ko, _ in CONCEPTS)}
    # 숫자 대조는 같은 원문 문서(같은 주소)를 가리키는 항목 글을 모두 본다 — 단서 글엔 세율이 없어도 같은 관보 항목 글(표 세율)엔 있다.
    # 시점과 상관없이 같은 문서라 레이더가 그때 이미 그 문서를 가졌다(숫자를 언제 읽었는지는 따지지 않는다).
    pool = {}
    for m in items:
        if m.get("url"):
            pool.setdefault(doc_key(m["url"]), []).append(m["text"])
    for m in same:
        if m["source"] in PLACE_SOURCES:
            mp = places_in(m["text"])
            if mp and not (mp & tplaces):
                continue   # 다른 지역(또는 기사에 지역 없음) — 같은 회사 항목으로만 센다
        hit_c = sorted(name for name, _, rx in CONCEPTS if name in concepts and re.search(rx, m["text"], re.I))
        if "소송·판결" in hit_c and RULING_TITLE.search(title) and not RULING_ITEM.search(m["text"]):
            hit_c.remove("소송·판결")
        # 사건 낱말로 이미 센 단어·흔한 단어는 따로 세지 않는다
        hit_w = sorted(w for w in words - concept_words - GENERIC_WORDS if w in m["text"])
        hit_s = sorted(name for name, ko, en in SPECIFIC_RX if ko.search(bare) and en.search(EN_COMPANY.sub(" ", m["text"])) and name not in hit_w)
        score = sum(1 if c in WEAK_CONCEPTS else 2 for c in hit_c) + len(hit_w) + len(hit_s)
        art_nums, same_nums, comparable = same_numbers(title, " ".join(pool.get(doc_key(m.get("url")), []) + [m["text"]]) if m.get("url") else m["text"])
        # 판결 기사 ↔ 먼저 본 판결 항목은 같은 사건 근거로 센다(위에서 판결 아닌 소송 접수는 이미 뺐다)
        ruling = "소송·판결" in hit_c and bool(RULING_TITLE.search(title))
        # 한국어 항목 본문에 기사 제목의 세 글자 넘는 낱말이 그대로 있으면(사건 낱말이라도: '임직원') 같은 사건 근거 — 두 글자 개념 낱말
        # ('법원'·'소송'·'관세')은 너무 흔해 뺀다
        literal = [w for w in words - GENERIC_WORDS - PLACE_WORDS if len(w) >= 3 and w in m["text"]]
        specific = sorted({*[w for w in hit_w if w not in PLACE_WORDS], *literal, *hit_s, *(["판결"] if ruling else [])})
        if not specific and sum(1 if c in WEAK_CONCEPTS else 2 for c in hit_c) < 3:
            continue   # 사건 개념 하나(+지명)만 겹침 — 같은 회사 항목으로만 센다
        score += 1 if same_nums else 0   # 사건 낱말이 겹친 항목끼리는 숫자까지 같은 쪽을 고른다
        if score > best_score or (score == best_score and best and m["seen"] > best["seen"]):
            best, best_score = {**m, "why": hit_c + hit_s + hit_w, **({"numbers": {"article": art_nums, "found": same_nums, "comparable": comparable}} if art_nums else {})}, score
    if best and best_score >= 2:
        verdict = "먼저 잡은 후보"
    elif same:
        verdict = "같은 회사 항목만"
        best = max(same, key=lambda m: m["seen"])
        best = {**best, "why": []}
    else:
        verdict = "없음"
    if best:
        best = {"source": best["source"], "label": label_of(best), "id": best["id"], "text": best["text"][:240],
                "seen": best["seen"].isoformat(timespec="minutes"), "url": best.get("url"), "why": best["why"][:6],
                "leadHours": round((pub - best["seen"]).total_seconds() / 3600, 1), **({"numbers": best["numbers"]} if best.get("numbers") else {})}
    return verdict, best, len(same)


def run(trace, docs, clues, *, now):
    since = now - dt.timedelta(days=WINDOW_DAYS)
    adapter_errors = {}
    items = memory(docs, clues, adapter_errors)
    rows = []
    seen_titles = set()
    for a in trace.get("items") or []:
        pub = parse_time(a.get("published"))
        if not pub or pub < since or pub > now:
            continue
        # 같은 기사가 색인에 두 번 들어온 경우(같은 제목·같은 날) 한 번만 센다
        tkey = (re.sub(r"\s+", "", re.sub(r"\s+-\s+[^-]{1,40}$", "", a.get("title") or "")), pub.date().isoformat())
        if tkey in seen_titles:
            continue
        seen_titles.add(tkey)
        verdict, best, n = match(a, items)
        clean_title = re.sub(r"\s+-\s+[^-]{1,40}$", "", a.get("title") or "")
        rows.append({"articleId": a.get("articleId"), "title": clean_title[:200], "published": a.get("published"),
                     "source": a.get("sourceName"), "companies": a.get("companies") or [], "kind": a.get("kind"),
                     "type": kind_of(re.sub(r"^\s*[\[(【][^\])】]*단독[^\])】]*[\])】]\s*", "", clean_title)), "verdict": verdict,
                     "best": best, "sameCompanyItems": n})
    rows.sort(key=lambda r: r["published"] or "", reverse=True)
    by_source = {}
    for r in rows:
        if r["verdict"] == "먼저 잡은 후보":
            s = by_source.setdefault(r["best"]["label"], {"caught": 0, "lead": []})
            s["caught"] += 1
            s["lead"].append(r["best"]["leadHours"])
    summary = {k: {"caught": v["caught"], "leadHoursMedian": median(v["lead"])} for k, v in sorted(by_source.items(), key=lambda t: -t[1]["caught"])}
    counts = {v: sum(1 for r in rows if r["verdict"] == v) for v in ("먼저 잡은 후보", "같은 회사 항목만", "없음", "회사 미상")}
    # 11-04: 어디서 지는지 — 기사 종류(기자 기사 대조와 같은 규칙)·매체별 판정 수
    def tally(key):
        out = {}
        for r in rows:
            t = out.setdefault(r.get(key) or "기타", {"total": 0, **{v: 0 for v in counts}})
            t["total"] += 1
            t[r["verdict"]] += 1
        return dict(sorted(out.items(), key=lambda kv: -kv[1]["total"]))
    by_type, by_outlet = tally("type"), tally("source")
    loaded = {f: f in docs for f in FEEDS}
    return {"schema": SCHEMA, "generatedAt": now.isoformat(timespec="seconds"), "windowDays": WINDOW_DAYS, "articles": rows, "counts": counts, "byType": by_type, "byOutlet": by_outlet,
            "bySource": summary, "memoryItems": len(items), "feedsLoaded": loaded, "adapterErrors": adapter_errors, "traceGeneratedAt": trace.get("generatedAt"),
            "rules": ["자동 후보다. 사람이 기사 전문과 원자료를 비교하는 Y/P/N 판정(역추적 기록)과 다르고, 그 수를 바꾸지 않는다.",
                      "먼저 잡은 후보마다 기사 제목의 숫자(세율·금액·규모)가 레이더 원문(같은 문서를 가리키는 항목 글 포함)에도 있는지 붙인다 — 숫자까지 같으면 같은 사실일 가능성이 높고, 원문 숫자와 다르면 같은 분야 다른 사실일 수 있다. 원문 글에 같은 단위 숫자가 없으면 비교 못 함(0은 흔해서 안 셈).",
                      "'먼저 잡은 후보'는 같은 회사(그룹) 항목을 기사 60일 전~직전에 레이더가 처음 봤고, 사건 낱말(한·영 대응)이 겹친 경우다. 같은 사건인지는 열어 봐야 한다.",
                      "장소가 있는 항목(건축허가·굴뚝·지자체 공고·국민연금 현장·공장등록·지방의회·미국 주 정부·OSHA)은 기사 제목에 같은 지역 이름이 있어야 센다.",
                      "레이더 기억은 지금 저장된 결과뿐이다(보관 기간이 지나 지워진 항목·저장 실패한 감시는 '없음'으로 나올 수 있다 — 0건 아님).",
                      "경쟁지 [단독] 목록은 구글 뉴스 제목 색인(최근 4일은 네이버 뉴스 검색 보강)이라 일부다."],
            "confirmedScoops": 0}


def main():
    import private_store
    now = dt.datetime.now(KST)
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    if not token:
        sys.exit("MCP_ACCESS_TOKEN 미설정 — 레이더 기억을 읽을 수 없음(미확인)")
    trace = json.loads((ROOT / "digests" / "reverse_trace_latest.json").read_text(encoding="utf-8"))
    clues = json.loads((ROOT / "tools" / "clues.json").read_text(encoding="utf-8"))
    docs, failed, empty = {}, [], []
    for f in FEEDS:
        try:
            d = private_store.get(f, token)
            if isinstance(d, dict):
                docs[f] = d
            else:
                empty.append(f)  # 저장된 결과가 아직 없음(첫 실행 전 등) — 조회 실패와 구분
        except Exception as e:  # noqa: BLE001 — network, HTTP or JSON: this feed is 미확인, the rest still count
            failed.append(f"{f}:{type(e).__name__}")
    doc = run(trace, docs, clues, now=now)
    doc["feedsFailed"] = failed
    doc["feedsEmpty"] = empty
    # Public log: counts, feed names and exception types only.
    print(f"::notice title=reverse-check::경쟁지 단독 {len(doc['articles'])}건 · {json.dumps(doc['counts'], ensure_ascii=False)} · "
          f"레이더 기억 {doc['memoryItems']}건 · 감시 읽음 {len(docs)}/{len(FEEDS)}" + (f" · 조회 실패 {failed}" if failed else "")
          + (f" · 저장 결과 없음 {empty}" if empty else "")
          + (f" · 읽기 오류 {doc['adapterErrors']}" if doc["adapterErrors"] else ""))
    try:
        status = private_store.put("reverse-check", doc, token)
    except Exception as e:  # noqa: BLE001
        sys.exit(f"저장 실패: {type(e).__name__}")
    print(f"::notice title=reverse-check-push::기자 전용 저장소 전송 HTTP {status}")
    if status != 200:
        sys.exit(1)


if __name__ == "__main__":
    main()
