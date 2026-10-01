from __future__ import annotations
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

DATA=Path('data.json'); DART=Path('dart.json'); NUM=Path('dart_numeric.json'); OUT=Path('pitch.json')

items=json.loads(DATA.read_text(encoding='utf-8')) if DATA.exists() else []
try:
    dart=json.loads(DART.read_text(encoding='utf-8')).get('items',[]) if DART.exists() else []
except Exception:
    dart=[]
try:
    numeric=json.loads(NUM.read_text(encoding='utf-8')).get('items',[]) if NUM.exists() else []
except Exception:
    numeric=[]

AUTO={'완성차','부품','배터리','정책·관세','중국차','노조·생산','수주·투자','리콜·안전','단독','미국·글로벌'}
IND={'철강','비철금속','전력기기','전선·전력','에너지','재생에너지','화학·소재'}
TARGETS={
    '현대차','기아','제네시스','현대모비스','현대위아','현대트랜시스','HL만도','LG에너지솔루션','삼성SDI','SK온',
    '포스코','포스코홀딩스','현대제철','동국제강','세아제강','고려아연','영풍','LS MnM','풍산',
    '두산에너빌리티','HD현대일렉트릭','LS ELECTRIC','효성중공업','일진전기','LS전선','대한전선','가온전선','대원전선',
    'GS','GS칼텍스','한화솔루션','OCI홀딩스','씨에스윈드','LG화학','롯데케미칼','금호석유화학','효성첨단소재','코오롱인더'
}
NOISE_RE=re.compile(r'주가|주식|증권|목표주가|급등|급락|추천|관련주|테마주|특징주|종목|증시|장중|오전장',re.I)
PRESS_RE=re.compile(r'뉴스와이어|Newswire|PRNewswire|Business Wire|GlobeNewswire|EIN Presswire|PRWeb|Accesswire|Press Release|보도자료|자료제공|자료배포|뉴스룸|미디어센터|프레스센터',re.I)
EVENT_RE=re.compile(r'인베스터데이|주주총회|설명회|세미나|포럼|엑스포|컨퍼런스|부스투어|기조연설|발표회')
NUM_RE=re.compile(r'(?<!\\d)(?:\\d{1,3}(?:,\\d{3})+|\\d+(?:\\.\\d+)?)(?:조원|억원|만원|달러|만대|천대|대|명|%|GWh|MWh|kWh|톤|km|MW|GW)(?!\\w)',re.I)

THEMES={
    '가격·수요':['가격','가격 조정','가격 인상','가격 인하','유통가격','수요','재고','원가','마진','스프레드'],
    '통상·관세':['관세','반덤핑','덤핑마진','통상','수입규제','원산지','조강국','melt and pour','OCTG'],
    '수주·공급':['수주','계약','공급','납품','수주잔고'],
    '투자·생산':['투자','증설','생산능력','공장','가동','생산중단'],
    '사업재편':['매각','분할','철수','사업재편','구조조정','합병','인수','합작','지분 전량'],
    '전력·재생':['ESS','에너지저장장치','전력망','배전','송전','변압기','HVDC','해저케이블','재생에너지','태양광','풍력'],
    '자동차 기술':['자율주행','레벨4','로보택시','AI','배터리','충전기'],
}

now=datetime.now(timezone.utc)

def dt(x):
    raw=str(x.get('published') or x.get('date') or '').strip()
    try:
        v=datetime.fromisoformat(raw.replace('Z','+00:00'))
        if v.tzinfo is None: v=v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)

def text(x):
    return ' '.join(str(x.get(k) or '') for k in ('title','summary','koTitle','koSummary')).strip()

def clean_title(x):
    t=str(x.get('title') or x.get('koTitle') or '').strip()
    t=re.sub(r'^\\s*(?:\\[[^]]+\\]|【[^】]+】)\\s*','',t)
    t=re.sub(r'\\s+[-|｜]\\s*[^-|｜]{1,40}$','',t).strip()
    return t

def nums(x):
    return list(dict.fromkeys(NUM_RE.findall(text(x))))

def companies(x):
    found=[c for c in x.get('companies') or [] if c in TARGETS]
    blob=text(x)
    for c in TARGETS:
        if c in blob and c not in found: found.append(c)
    return found

def is_eligible(x):
    if not x or x.get('global') or x.get('category') not in AUTO|IND: return False
    t=text(x)
    if NOISE_RE.search(t) or PRESS_RE.search(t): return False
    if EVENT_RE.search(clean_title(x)) and not any(k in t for k in ('수주','계약','투자','증설','매각','관세','가격','공급','생산','리콜','자율주행')): return False
    return bool(clean_title(x))

recent=[x for x in items if is_eligible(x) and now-dt(x)<=timedelta(days=7)]
recent.sort(key=dt,reverse=True)

def unique_articles(arr,limit=4):
    out=[]; seen=set()
    for x in sorted(arr,key=dt,reverse=True):
        key=(x.get('sourceName') or '',clean_title(x))
        if key in seen: continue
        seen.add(key); out.append(x)
        if len(out)>=limit: break
    return out

def contains_any(x, words):
    low=text(x).lower()
    return any(w.lower() in low for w in words)

def latest_with(arr, words):
    return sorted([x for x in arr if contains_any(x,words)],key=dt,reverse=True)

def sources(arr):
    return list(dict.fromkeys([x.get('sourceName') for x in arr if x.get('sourceName')]))

def evidence(arr):
    return [{'source':x.get('sourceName') or '-', 'title':clean_title(x), 'url':x.get('url'),'published':x.get('published'),'numbers':nums(x)[:6]} for x in unique_articles(arr,4)]

def pitch(headline, category, co, bullets, arr, questions, score=94, angle=''):
    ev=evidence(arr)
    ns=list(dict.fromkeys([n for x in arr for n in nums(x)]))[:8]
    return {
        'type':'strategy-change',
        'grade':'A',
        'pitchScore':score,
        'headline':headline,
        'category':category,
        'companies':list(dict.fromkeys(co))[:4],
        'reporter':'홍성효',
        'generatedAt':datetime.now(timezone.utc).isoformat(),
        'briefBullets':bullets[:4],
        'newFact':bullets[0] if bullets else '',
        'angle':angle or (bullets[-1] if bullets else ''),
        'differentiator':'최근 보도에서 확인된 구체적 사실을 중심으로 기업·시장 변수와 후속 취재 포인트를 연결한 발제.',
        'whyNow':'최근 7일 안에 관련 사실과 숫자가 새로 확인된 이슈.',
        'numbers':ns,
        'sourceCount':len(sources(arr)),
        'globalSignals':0,
        'domesticSignals':len(ev),
        'sources':sources(arr),
        'evidence':ev,
        'dartSignals':[],
        'dartNumericSignals':[],
        'dartNumericCount':0,
        'questions':questions,
        'articlePlan':bullets[:]
    }

candidates=[]

# 1) 정부 정책 -> ESS/재생에너지 -> 국내 전력기기 수요
policy=[x for x in recent if contains_any(x,['정부','산업부','정부,','정책','확대','대책']) and contains_any(x,['ESS','에너지저장장치','재생에너지','전력망','배전'])]
power=[x for x in recent if contains_any(x,['LS ELECTRIC','LS일렉트릭','HD현대일렉트릭','효성중공업','전력기기','변압기']) and contains_any(x,['ESS','전력망','배전','송전','변압기','재생에너지'])]
if len(policy)>=1 and len(power)>=2:
    co=list(dict.fromkeys(c for x in power for c in companies(x)))
    pa=policy[0]; pp=unique_articles(power,3)
    bullets=[
        f'정부가 {clean_title(pa)} 등 재생에너지 수용능력 확대와 전력망 보강에 속도를 내면서 ESS 활용 확대가 본격화될 전망.',
        f'{"·".join(co[:2]) if co else "국내 전력기기업계"}도 {clean_title(pp[0])} 등 ESS·전력망 관련 사업 확대 가능성을 내놓고 있어 관련 설비 수요 변화가 관건.',
        'ESS 보급이 단순 저장장치 확대에 그치지 않고 배전·송전망 투자로 이어질 경우 ESS와 전력기기를 함께 공급하는 국내 업체들의 중장기 사업 기회가 커질 수 있음.'
    ]
    candidates.append(pitch('정부 ESS 확대…K전력기기, 배전까지 수요 확대 기대','전력기기',co,bullets,[pa]+pp,
        ['정부의 ESS 확대 목표와 실제 발주 물량은 무엇인가?','LS일렉트릭·HD현대일렉트릭의 국내 ESS·배전 사업 계획은 어디까지인가?','ESS 확대가 변압기·배전반·송배전망 투자로 연결되는 규모는 얼마인가?'],96))

# 2) 철강 가격: only when demand/inventory is actually present in the observed articles
steel=[x for x in recent if x.get('category')=='철강']
steel_price=[x for x in steel if contains_any(x,['10월','유통가격','가격 인상','가격 조정','가격']) and contains_any(x,['현대제철','동국제강','포스코','세아제강','철강'])]
steel_demand=[x for x in steel if contains_any(x,['수요','재고','성수기','유통업계','판매 부진'])]
if len(steel_price)>=2 and (len(steel_demand)>=1 or any(contains_any(x,['재고','수요','성수기']) for x in steel_price)):
    pp=unique_articles(steel_price+steel_demand,4)
    names=list(dict.fromkeys(c for x in pp for c in companies(x)))
    bullets=[
        '철강사들이 10월 유통가격 조정에 나섰지만 실제 가격 상승으로 이어질지는 수요와 유통 재고 상황에 달려 있음.',
        f'{"·".join(names[:2]) if names else "현대제철·동국제강"}의 10월 가격 조정 움직임과 함께 유통 현장의 재고·주문 흐름을 확인할 필요가 있음.',
        '성수기 수요가 살아나지 않거나 재고 부담이 이어질 경우 가격 인상 폭이 제한될 수 있어 실제 유통가격 반영 여부가 변수.'
    ]
    candidates.append(pitch('철강사 10월 가격 조정…성수기 수요 기대에도 재고 부담','철강',names,bullets,pp,
        ['10월 인상분이 실제 유통가격에 반영됐는가?','현대제철·동국제강의 출하·재고와 유통 주문은 어떻게 달라졌는가?','중국산 저가재와 원료가격이 국내 가격 결정에 미치는 영향은?'],95))

# 3) EU melt-and-pour / origin proof -> Korean steel exporters
eu=[x for x in recent if contains_any(x,['EU','유럽연합','조강국','melt and pour','원산지 증빙','원산지']) and contains_any(x,['철강','강판','강관'])]
eu_comp=[x for x in recent if any(c in text(x) for c in ['현대제철','동국제강','KG스틸','포스코','세아제강']) and contains_any(x,['EU','유럽','통관','원산지','증빙'])]
if eu and eu_comp:
    arr=unique_articles(eu+eu_comp,5); names=list(dict.fromkeys(c for x in arr for c in companies(x)))
    lead=clean_title(eu[0])
    bullets=[
        f'EU가 철강 수입 과정에서 실제 용해·주조가 이뤄진 국가를 확인하는 원산지 증빙을 강화하면서 국내 철강사의 통관 절차가 달라질 수 있음.',
        f'{"·".join(names[:3]) if names else "국내 철강사"}는 현재 {clean_title(eu_comp[0])} 등으로 대응하고 있어 기업별 서류·원산지 관리 방식에 차이가 있는지 확인 필요.',
        '관세 수준뿐 아니라 조강 단계부터 최종 제품까지 원산지를 추적·입증하는 공급망 관리 역량이 유럽 수출의 새로운 변수가 될 전망.'
    ]
    candidates.append(pitch("EU 철강 '조강국 증빙' 시행…K-철강 통관 부담 갈린다",'철강',names,bullets,arr,
        ['EU가 요구하는 원산지·조강 증빙 서류는 무엇인가?','현대제철·동국제강·KG스틸의 대응 절차와 추가 비용은 다른가?','원소재 변경이나 공급처 다변화가 필요한 제품군이 있는가?'],96))

# 4) US OCTG anti-dumping final margin -> Seah
seah=[x for x in recent if contains_any(x,['세아제강']) and contains_any(x,['반덤핑','덤핑마진','OCTG','강관']) and any('%' in n for n in nums(x))]
if seah:
    arr=unique_articles(seah,4); top=arr[0]; ns=nums(top); margin=next((n for n in ns if '%' in n),'')
    bullets=[
        f'미국 통상당국의 한국산 강관 반덤핑 판정에서 세아제강 관련 최종 덤핑마진 {margin or "수치"}가 확인됨.',
        '최종 마진 확정에 따라 세아제강의 미국향 OCTG 출하·수주와 물량 조정 여부, 현지 가격 전략 변화가 주요 변수.',
    ]
    candidates.append(pitch(f'美 한국산 OCTG 최종 덤핑마진 확정…세아제강 수출전략 변수','철강',['세아제강'],bullets,arr,
        ['최종 마진 확정이 미국향 OCTG 계약 단가와 출하량에 미치는 영향은?','기존 수주분과 신규 수주에 적용되는 관세 부담은 각각 얼마인가?','미국 외 지역으로 물량을 전환할 가능성이 있는가?'],95))

# 5) POSCO non-core asset sale -> capital allocation
posco=[x for x in recent if contains_any(x,['포스코']) and contains_any(x,['우리금융','지분 전량','6765억원','6765억']) and not NOISE_RE.search(text(x))]
if len(posco)>=2:
    arr=unique_articles(posco,4)
    bullets=[
        '포스코가 우리금융지주 보유 지분을 전량 매각해 약 6765억원을 현금화하면서 비핵심자산 정리에 속도를 내고 있음.',
        '최근 보도에서는 확보한 자금을 국내외 성장 투자 재원으로 활용한다는 설명이 나오면서 실제 투자처와 집행 시점이 다음 확인 포인트.',
        '철강 투자와 신사업·해외 사업 가운데 어디에 자금이 배분되는지 확인하면 포스코의 사업 포트폴리오 재편 방향을 구체적으로 짚을 수 있음.'
    ]
    candidates.append(pitch('포스코, 우리금융 지분 6765억원 현금화…비핵심자산 정리 속도','철강',['포스코'],bullets,arr,
        ['6765억원의 구체적인 투자처와 집행 일정은?','기존 비핵심자산 매각 계획 중 추가로 정리할 대상이 있는가?','철강·신사업·해외투자별 자금 배분 비중은?'],94))

# 6) Doosan Vietnam repeated orders
doosan=[x for x in recent if contains_any(x,['두산에너빌리티']) and contains_any(x,['베트남','오몬3','가스복합']) and contains_any(x,['수주','계약'])]
if len(doosan)>=3:
    arr=unique_articles(doosan,5)
    bullets=[
        '두산에너빌리티가 베트남 오몬3 가스복합발전소 건설공사를 8400억원 규모로 추가 수주하면서 올해 베트남 수주가 5건, 3조8700억원 규모로 확대.',
        '오몬3를 포함해 가스복합발전 수주가 잇따르면서 베트남에서 발전 EPC·핵심설비 공급을 함께 확대하는 흐름이 이어지고 있음.',
        '추가 수주가 실제 생산·설계 물량으로 얼마나 이어지는지와 후속 발주 파이프라인이 남아 있는지가 중장기 실적 변수.'
    ]
    candidates.append(pitch('두산에너빌리티, 베트남서 3.87조 수주…가스복합 잇단 계약','에너지',['두산에너빌리티'],bullets,arr,
        ['올해 베트남 5건 수주 중 두산에너빌리티 몫의 누적 매출 인식 일정은?','오몬3 이후 추가 발주가 예상되는 프로젝트와 규모는?','국내 생산·설계 인력과 설비 투입은 얼마나 늘어나는가?'],94))

# 7) LS Electric AI data center transformer order
ls=[x for x in recent if contains_any(x,['LS일렉트릭','LS ELECTRIC']) and contains_any(x,['1812억원','1800억원','변압기']) and contains_any(x,['AI 데이터센터','데이터센터'])]
if len(ls)>=4:
    arr=unique_articles(ls,6)
    bullets=[
        'LS일렉트릭이 북미 AI 데이터센터 9개 변전소에 345kV 초고압 변압기를 공급하는 1812억원 규모 계약을 확보.',
        '2030년까지 순차 납품하는 장기 공급으로 단발성 수주보다 북미 AI 데이터센터 전력 인프라 시장과의 연결이 커지는 흐름.',
        '북미 데이터센터 투자 확대에 맞춰 추가 수주와 국내·현지 생산능력 확충이 얼마나 이어지는지가 다음 사업 변수.'
    ]
    candidates.append(pitch('AI 데이터센터 전력수요…LS일렉트릭, 1812억원 변압기 수주','전력기기',['LS ELECTRIC'],bullets,arr,
        ['1812억원 계약의 매출 인식 시점과 수익성은?','2030년까지 추가 공급 물량과 후속 수주 파이프라인은?','북미 현지 생산·증설 계획과 국내 공장 가동률은?'],93))

# 8) Hyundai-Kia Level 4 bus commercialization
bus=[x for x in recent if contains_any(x,['현대차','기아']) and contains_any(x,['레벨4','자율주행 시내버스']) and contains_any(x,['2030','500대','서울'])]
if len(bus)>=2:
    arr=unique_articles(bus,5)
    bullets=[
        '현대차·기아가 서울에서 레벨4 자율주행 시내버스 실증에 나서고 2030년 정규 노선에 500대 투입 계획을 제시.',
        '전용 차량과 관제 플랫폼 개발까지 포함돼 차량 판매를 넘어 자율주행 서비스 운영 생태계 구축으로 사업 범위가 넓어지는 흐름.',
        '실증에서 상용 노선으로 넘어가기 위해 필요한 안전 기준·인프라·운영 주체와 실제 차량 투입 일정이 사업화의 핵심 변수.'
    ]
    candidates.append(pitch('현대차·기아, 레벨4 시내버스 2030년 500대…상용화 시험대','완성차',['현대차','기아'],bullets,arr,
        ['2030년 500대 투입을 위한 실증 단계와 연차별 계획은?','관제 플랫폼·차량·인프라 중 누가 어떤 역할과 비용을 부담하는가?','현행 법·안전기준에서 상용화를 위해 추가로 필요한 제도는?'],92))

# 9) Samsung SDI EV plant -> ESS
sdi=[x for x in recent if contains_any(x,['삼성SDI']) and contains_any(x,['ESS','전기차 공장']) and contains_any(x,['4.4조','4조','실탄','전환'])]
if len(sdi)>=1:
    arr=unique_articles(sdi,4)
    bullets=[
        '삼성SDI가 전기차 공장 일부를 ESS 생산에 활용하는 방안과 함께 4.4조원 규모의 재원을 확보했다는 보도가 나옴.',
        '전기차 배터리 수요 회복을 기다리는 대신 ESS로 생산 포트폴리오를 전환하는 움직임이어서 배터리 업계의 생산능력 활용 방식에도 변화.',
        'ESS 수주가 실제 가동률·수익성 개선으로 이어지는지, 추가 생산 전환과 투자 계획이 있는지가 관건.'
    ]
    candidates.append(pitch('삼성SDI, 전기차 공장 ESS로 돌린다…4.4조 실탄 확보','배터리',['삼성SDI'],bullets,arr,
        ['ESS 전환 대상 공장과 생산능력은 어느 정도인가?','4.4조원 재원 중 ESS 생산·투자에 배분되는 금액은?','ESS 수주잔고와 향후 가동률·수익성 개선 효과는?'],91))

# Rank by editorial usefulness rather than a generic AI score.
# Prefer specific conflict/variable headlines and multiple concrete facts.
def quality(p):
    t=p['headline']; b=' '.join(p['briefBullets'])
    q=0
    q+=min(25,len(p.get('evidence') or [])*6)
    q+=min(22,len(p.get('numbers') or [])*4)
    q+=18 if re.search(r'변수|부담|관건|갈린다|시험대|기대',t) else 10
    q+=12 if len(p.get('companies') or [])>=2 else 6
    q+=10 if re.search(r'정부|EU|美|미국|중국|북미|유럽',t) else 5
    q+=8 if len(p.get('briefBullets') or [])>=3 else 0
    return q

candidates.sort(key=lambda p:(quality(p),p.get('pitchScore',0),max([dt(x) for x in recent if x.get('sourceName') in (p.get('sources') or [])] or [datetime.min.replace(tzinfo=timezone.utc)])),reverse=True)

final=[]
seen=set()
for p in candidates:
    key='|'.join(sorted(p.get('companies') or []))+'|'+re.sub(r'[^가-힣A-Za-z0-9]','',p['headline'])[:28]
    if key in seen: continue
    if any(set(p.get('companies') or []) & set(q.get('companies') or []) and p['category']==q['category'] for q in final):
        # Avoid returning three pitches about the same company/beat in one batch.
        continue
    seen.add(key)
    final.append(p)
    if len(final)>=3: break

# Require an actual reporter-style bullet package; never pad the list.
final=[p for p in final if len(p.get('briefBullets') or [])>=2 and len(p.get('evidence') or [])>=1 and len(p.get('questions') or [])>=3]

OUT.write_text(json.dumps(final,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
print(f'editorial pitch builder: {len(final)} reporter-style candidates / max 3 / no generic template')
