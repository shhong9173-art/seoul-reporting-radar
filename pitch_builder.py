from __future__ import annotations
import json,re
from pathlib import Path
from itertools import combinations

ITEMS=Path('data.json')
OUT=Path('pitch.json')
items=json.loads(ITEMS.read_text(encoding='utf-8'))

def toks(s):
    return set(re.findall(r'[가-힣A-Za-z0-9]{2,}',(s or '').lower()))

def nums(s):
    return re.findall(r'\d+(?:\.\d+)?\s*(?:조원|억원|만원|억|조|만대|천대|%|명|만|개|곳|년|개월|GWh|kWh|km)',s or '',re.I)

def norm(x):
    return (x.get('title','')+' '+x.get('summary','')).strip()

# Build cross-source evidence groups. A pitch must derive from at least two distinct sources.
groups=[]
used=set()
for a,b in combinations([x for x in items if not x.get('exclusive')],2):
    if a.get('sourceName')==b.get('sourceName'): continue
    ac=set(a.get('companies') or []); bc=set(b.get('companies') or [])
    shared_company=ac & bc
    shared=toks(norm(a)) & toks(norm(b))
    if not shared_company and len(shared)<3: continue
    if not shared_company and not any(k in shared for k in {'투자','공장','생산','수주','계약','관세','배터리','ESS','AAM','로보택시','자율주행','증설','감원'}): continue
    key='|'.join(sorted(shared_company))+'|'+'|'.join(sorted(list(shared)[:8]))
    if key in used: continue
    used.add(key)
    members=[a,b]
    companies=sorted(shared_company or set(a.get('companies') or []) or set(b.get('companies') or []))
    alltext=' '.join(norm(x) for x in members)
    numbers=[]
    for m in members:
        numbers.extend(nums(norm(m)))
    numbers=list(dict.fromkeys(numbers))[:8]
    sources=list(dict.fromkeys(x.get('sourceName','') for x in members if x.get('sourceName')))
    globals_count=sum(1 for x in members if x.get('global'))
    # Reward actual information combinations, not raw news volume.
    signals=0
    if len(sources)>=2: signals+=20
    if numbers: signals+=18
    if companies: signals+=15
    if globals_count: signals+=12
    if any(k in alltext for k in ['투자','증설','공장','수주','계약','생산','감원','관세','배터리','ESS','AAM','로보택시','자율주행']): signals+=20
    if len(numbers)>=2: signals+=8
    # Penalize generic/duplicate-looking pairs.
    if len(shared)>=8: signals-=8
    score=max(55,min(96,50+signals))
    # Prefer one domestic + one global/professional source when possible.
    if globals_count and len(sources)>=2: score=min(99,score+5)
    title_a=a.get('koTitle') if a.get('global') and a.get('koTitle') else a.get('title','')
    title_b=b.get('koTitle') if b.get('global') and b.get('koTitle') else b.get('title','')
    base=companies[0] if companies else (a.get('category') or '업계')
    if any(k in alltext for k in ['투자','증설','공장']): angle=f'{base}, 투자·사업 확대 속 전략 변화 주목'
    elif any(k in alltext for k in ['AAM','로보택시','자율주행']): angle=f'{base}, 미래 모빌리티 투자와 사업 재편 동시 진행'
    elif any(k in alltext for k in ['배터리','ESS']): angle=f'{base}, 배터리 사업 방향 전환 신호…생산전략 달라지나'
    elif '관세' in alltext or 'tariff' in alltext.lower(): angle=f'{base}, 관세·공급망 변화에 대응 전략 변화'
    elif any(k in alltext for k in ['수주','계약']): angle=f'{base}, 수주 확대 배경과 공급망 변화 주목'
    else: angle=f'{base}, 최근 자료를 종합하면 새로운 후속 취재 포인트'
    questions=[]
    if numbers: questions.append('확인된 숫자의 기준 시점·대상·전년 대비 증감폭을 확인')
    questions.append('회사 또는 관계기관에 추가 투자·생산·조직 변화 계획이 있는지 확인')
    questions.append('기존 보도에 없는 새로운 사실이나 후속 조치가 무엇인지 확인')
    if globals_count: questions.append('해외 보도의 핵심 수치·관계자 발언이 국내 사업에도 적용되는지 확인')
    pitch={
        'id':f'P{len(groups)+1:03d}', 'pitchScore':score, 'grade':'A' if score>=85 else 'B',
        'headline':angle, 'category':a.get('category') or b.get('category'), 'companies':companies,
        'sources':sources, 'sourceCount':len(sources), 'globalSignals':globals_count,
        'evidence':[{'source':x.get('sourceName'),'title':x.get('koTitle') if x.get('global') and x.get('koTitle') else x.get('title'),'url':x.get('url'),'published':x.get('published')} for x in members],
        'numbers':numbers, 'whyNow':'서로 다른 매체·자료에서 확인되는 사실을 묶었을 때 추가 취재 가치가 생기는 조합입니다.',
        'angle':'단일 기사 요약이 아니라 서로 다른 출처의 사실을 교차해 새로운 기사 각도를 제시하는 후보입니다.',
        'questions':questions, 'rawSignals':[title_a,title_b]
    }
    groups.append(pitch)

groups.sort(key=lambda x:x['pitchScore'],reverse=True)
# Keep the shortlist deliberately small.
OUT.write_text(json.dumps(groups[:12],ensure_ascii=False,separators=(',',':')),encoding='utf-8')
print(f'pitch builder: {len(groups[:12])} candidates')
