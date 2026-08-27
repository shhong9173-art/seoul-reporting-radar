from __future__ import annotations
import json,re
from pathlib import Path

IN=Path('dig_today.json')
data=json.loads(IN.read_text(encoding='utf-8')) if IN.exists() else {'generatedAt':None,'items':[]}
items=data.get('items',[])

BAD_TITLE_PATTERNS=('공시에 새','공시에 새 숫자','사업전략 얼마나 달라졌나','전략 변화 본격화되나','짚어볼 만','실제 전략은')
GENERIC_LINES=('최근 30일','관련 보도가 동시에 확인됨','구체적 수치 확인','실제 변화인지 확인','경쟁사와 투자·생산·수주 속도를 비교')
INDUSTRY_HINTS={
 '철강':('철강','고로','수소환원','후판','중국산','감산','원료','탄소'),
 '비철금속':('구리','알루미늄','아연','니켈','제련','TC/RC'),
 '전력기기':('변압기','HVDC','전력망','데이터센터','증설','북미'),
 '전선·전력':('해저케이블','HVDC','전선','구리','북미'),
 '에너지':('두산에너빌리티','GS','GS칼텍스','가스터빈','원전','에너지'),
 '재생에너지':('풍력','해상풍력','터빈','REC','계통'),
 '화학·소재':('석유화학','스페셜티','원료','중국','화학','소재'),
}
ISSUE_WORDS=('관건','시험대','따라가나','바뀌나','달라지나','커지나','줄이는','키우는','전략','원가','수익성','생산능력','공급망','상용화','현지 생산','수출전략')

def compact(s): return re.sub(r'\s+',' ',str(s or '')).strip()
def concrete_numbers(it):
    ns=[str(x) for x in (it.get('numbers') or []) if re.search(r'(조원|억원|만원|달러|USD|EUR|만대|천대|대|명|%|GWh|MWh|MW|GW|톤|km)',str(x))]
    return list(dict.fromkeys(ns))
def evidence_ok(it):
    lines=[compact(x) for x in (it.get('lines') or [])]
    specific=sum(1 for x in lines if len(x)>=28 and not any(g in x for g in GENERIC_LINES))
    nums=concrete_numbers(it)
    return specific>=2 and bool(nums)
def title_score(t):
    t=compact(t)
    return sum(1 for w in ISSUE_WORDS if w in t)
def make_headline(it):
    c=it.get('company') or ''
    cat=it.get('category') or ''
    ns=concrete_numbers(it)
    n=ns[0] if ns else ''
    lines=' '.join(it.get('lines') or [])
    blob=(compact(it.get('headline'))+' '+compact(it.get('why'))+' '+compact(lines)).lower()
    if '수소환원' in blob or 'hyrex' in blob: return f'{n} 투입하는 {c} 수소환원제철…탄소보다 원가가 관건'.replace(' 투입하는',' 투입하는',1) if n else f'{c} 수소환원제철 투자 확대…탄소보다 원가가 관건'
    if cat=='전력기기' and n and any(k in blob for k in ('투자','증설','변압기','전력망')): return f'{n} 투자하는 {c}…전력망 호황, 증설이 관건'
    if '사업재편' in blob or any(k in blob for k in ('철수','매각','구조조정')): return f'{c}, 사업재편 본격화…줄이는 사업·키우는 사업은'
    if '수주' in blob and '투자' in blob: return f'{c}, 수주 늘자 {n} 투자…생산능력 확충이 관건' if n else f'{c}, 수주 늘자 투자 확대…생산능력 확충이 관건'
    if '가격·원가' in blob and '투자' in blob: return f'{c}, 원가 부담 속 투자 확대…수익성 방어가 관건'
    if '생산' in blob and '투자' in blob: return f'{c}, 생산능력 키운다…증설이 수익성으로 이어질까'
    if cat in INDUSTRY_HINTS and any(k in blob for k in INDUSTRY_HINTS[cat]):
        return f'{c}, 산업 변화 본격화…공급능력·수익성이 관건'
    return None

kept=[]
for it in items:
    t=compact(it.get('headline'))
    if any(p in t for p in BAD_TITLE_PATTERNS):
        nh=make_headline(it)
        if nh: it['headline']=nh
        else: continue
    if not evidence_ok(it): continue
    if title_score(it.get('headline'))<1: continue
    if len(concrete_numbers(it))==0: continue
    it['qualityGate']='pass'
    it['qualityReason']='구체적 숫자와 복수 근거가 있고, 기사 쟁점이 제목에서 드러나는 후보'
    kept.append(it)

# Keep the strongest candidates, with automotive preferred but preserve industry coverage when qualified.
kept.sort(key=lambda x:(x.get('score',0), len(concrete_numbers(x)), len(x.get('sources') or [])), reverse=True)
final=[]
seen=set()
for it in kept:
    key=(it.get('company'),it.get('category'))
    if key in seen: continue
    seen.add(key); final.append(it)
final=final[:5]

data['items']=final
data['qualityGate']={'input':len(items),'output':len(final),'rule':'구체적 숫자+복수 근거+쟁점형 제목을 모두 요구'}
IN.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
print(f'investigation quality gate: {len(items)} -> {len(final)}')
