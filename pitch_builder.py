from __future__ import annotations
import json,re
from collections import defaultdict
from pathlib import Path

ITEMS=Path('data.json')
OUT=Path('pitch.json')
items=json.loads(ITEMS.read_text(encoding='utf-8'))

THEMES={
    'investment':['투자','증자','자금','억원','조원','investment','funding','capex'],
    'capacity':['증설','공장','생산','라인','가동','capacity','plant','production','factory'],
    'restructuring':['감원','축소','철수','조직','CEO','대표','거점','재편','restructuring','layoff','cut','shutdown'],
    'tariff':['관세','통상','공급망','tariff','trade','supply chain'],
    'ev_to_ess':['ESS','에너지저장','전환','EV battery','storage'],
    'order':['수주','계약','납품','고객사','order','contract'],
    'mobility':['AAM','로보택시','자율주행','모셔널','슈퍼널','모빌리티','robotaxi','autonomous'],
    'sales':['판매','출하','인도량','점유율','sales','deliveries','share'],
    'labor':['임금','임협','노조','파업','노사','wage','union','strike'],
    'product':['신차','출시','양산','모델','차종','product','launch','model'],
}
GENERIC=set('자동차 현대차 기아 배터리 전기차 관련 업계 시장 최근 오늘 미국 한국 중국 차량 자동 회사 산업 기업 뉴스 기사 전망'.split())
NOISE=set('주가 주식 증권 목표주가 투자자 고액자산가 네카오 급등 급락 추천 리서치센터 인사 임원 승진 대표이사 사장 부회장'.split())

def display_title(x):
    return x.get('koTitle') if x.get('global') and x.get('koTitle') else x.get('title','')

def text(x):
    return ' '.join(str(v or '') for v in [display_title(x),x.get('summary',''),x.get('koSummary',''),x.get('whyNow','')])

def toks(s):
    return set(re.findall(r'[가-힣A-Za-z0-9]{2,}',s.lower()))

def nums(s):
    return list(dict.fromkeys(re.findall(r'\d+(?:\.\d+)?\s*(?:조원|억원|만원|억|조|만대|천대|%|명|개|곳|년|개월|GWh|kWh|km)',s,re.I)))

def theme_set(s):
    low=s.lower()
    return {k for k,words in THEMES.items() if any(w.lower() in low for w in words)}

def clean_tokens(s):
    return toks(s)-GENERIC-NOISE

def meaningful_overlap(a,b):
    ta=clean_tokens(display_title(a)); tb=clean_tokens(display_title(b))
    return ta & tb

def company_overlap(a,b):
    return set(a.get('companies') or []) & set(b.get('companies') or [])

# Group by business entity, not merely category or a common generic word.
buckets=defaultdict(list)
for x in items:
    if x.get('exclusive'): continue
    for c in [c for c in (x.get('companies') or []) if c and c not in NOISE]:
        buckets[c].append(x)

candidates=[]
for company, arr in buckets.items():
    arr=sorted(arr,key=lambda x:x.get('published',''),reverse=True)[:40]
    if len({x.get('sourceName') for x in arr if x.get('sourceName')})<2: continue

    # Build connected components only when articles share a meaningful topic token or theme.
    graph=defaultdict(set)
    for i,a in enumerate(arr):
        for j in range(i+1,len(arr)):
            b=arr[j]
            if not company_overlap(a,b): continue
            if meaningful_overlap(a,b) or (theme_set(text(a)) & theme_set(text(b))):
                graph[i].add(j); graph[j].add(i)
    seen=set(); comps=[]
    for i in range(len(arr)):
        if i in seen: continue
        stack=[i]; seen.add(i); comp=[]
        while stack:
            k=stack.pop(); comp.append(k)
            for n in graph[k]:
                if n not in seen:
                    seen.add(n); stack.append(n)
        if len(comp)>=2: comps.append(comp)

    for idxs in comps:
        selected=sorted([arr[i] for i in idxs],key=lambda x:x.get('published',''),reverse=True)[:10]
        srcs=[]
        for x in selected:
            s=x.get('sourceName')
            if s and s not in srcs: srcs.append(s)
        domestic=[x for x in selected if not x.get('global')]
        global_items=[x for x in selected if x.get('global')]
        alltext=' '.join(text(x) for x in selected)
        active=theme_set(alltext)
        numbers=list(dict.fromkeys(sum((nums(text(x)) for x in selected),[])))[:12]

        pairs=[
            ('investment','restructuring','투자는 이어가는데 조직·거점은 재편'),
            ('investment','capacity','투자 확대와 생산능력 재편이 동시에 진행'),
            ('capacity','tariff','관세 대응으로 생산·공급망 재편'),
            ('order','capacity','수주 확대에 맞춰 생산능력도 움직인다'),
            ('order','investment','수주가 늘면서 추가 투자로 이어진다'),
            ('ev_to_ess','capacity','EV 수요 변화에 생산라인을 ESS로 전환'),
            ('mobility','investment','미래 모빌리티 투자는 늘리면서 사업은 재편'),
            ('sales','restructuring','판매 흐름 변화와 조직 재편이 동시에 나타난다'),
            ('sales','investment','판매 흐름과 투자 방향이 엇갈린다'),
            ('labor','capacity','노사 변화가 생산·가동 계획에 영향을 준다'),
            ('labor','investment','노사 비용 변화와 투자 계획이 동시에 움직인다'),
            ('product','capacity','신차 확대와 생산능력 재편이 맞물린다'),
        ]
        matching=[p for p in pairs if p[0] in active and p[1] in active]
        if not matching: continue
        frame=matching[0][2]

        # High-confidence only: 3+ sources OR a domestic+global combination.
        if len(srcs)<3 and not (domestic and global_items): continue
        if len(numbers)<1 or len(active)<2 or len(selected)<2: continue
        if not any(k in alltext for k in sum(THEMES.values(),[])): continue
        if sum(any(n in display_title(x) for n in NOISE) for x in selected)>=len(selected)-1: continue

        score=68
        score += min(15,(len(srcs)-2)*5)
        score += 10 if domestic and global_items else 0
        score += 10 if len(numbers)>=2 else 0
        score += 8 if len(selected)>=3 else 0
        score += 8 if len(active)>=3 else 0
        score=min(98,score)
        if score<80: continue

        evidence=[{'source':x.get('sourceName'),'title':display_title(x),'url':x.get('url'),'published':x.get('published')} for x in selected[:6]]
        if matching[0][0]=='investment' and matching[0][1]=='restructuring':
            angle=f'{company}가 투자는 이어가면서 조직·거점을 재편하는 배경과 실제 전략 전환 폭을 확인'
        elif matching[0][0]=='ev_to_ess':
            angle=f'{company}의 EV 중심 투자와 ESS 전환이 어느 생산거점까지 번졌는지 수치로 확인'
        elif matching[0][0]=='capacity' and matching[0][1]=='tariff':
            angle=f'관세 변화가 {company}의 생산·조달 구조를 얼마나 바꾸는지 국내 투자와 연결해 확인'
        elif matching[0][0]=='order':
            angle=f'{company}의 수주가 단순 계약 증가인지 생산능력·설비 투자 확대까지 이어지는지 확인'
        else:
            angle=f'{company}에서 동시에 나타난 {frame}의 규모와 배경을 추가 취재'

        questions=[
            f'{company}의 {matching[0][0]}·{matching[0][1]} 변화가 실제로 동시에 진행되고 있는지 확인',
            '전년 또는 직전 계획 대비 달라진 금액·물량·인력·시점을 사업보고서·실적자료로 확인',
            '회사·정부가 공식적으로 확인하지 않은 핵심 숫자와 후속 계획을 추가 확인',
            '경쟁사나 공급망에도 같은 변화가 나타나는지 비교',
        ]

        candidates.append({
            'id':f'P{len(candidates)+1:03d}','pitchScore':score,'grade':'A' if score>=88 else 'B',
            'headline':f'{company}, {frame}','frame':frame,'angle':angle,
            'category':selected[0].get('category') or '완성차','companies':[company],
            'sourceCount':len(srcs),'sources':srcs[:8],'globalSignals':len(global_items),'domesticSignals':len(domestic),
            'numbers':numbers,'themes':sorted(active),'evidence':evidence,
            'whyNow':f'{len(srcs)}개 매체와 {len(selected)}개 관련 기사에서 {len(active)}개 변화축과 {len(numbers)}개 수치 신호가 연결됩니다.',
            'questions':questions,'rawSignals':[display_title(x) for x in selected[:6]],
        })

candidates.sort(key=lambda x:(x['pitchScore'],x['sourceCount'],x['globalSignals'],len(x['numbers'])),reverse=True)
final=[]; seen=set()
for p in candidates:
    sig=(tuple(p['companies']),p['frame'])
    if sig in seen: continue
    seen.add(sig); final.append(p)
    if len(final)>=8: break

OUT.write_text(json.dumps(final,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
print(f'pitch builder: {len(final)} high-confidence synthesized items')
