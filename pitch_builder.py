from __future__ import annotations
import json,re
from pathlib import Path

ITEMS=Path('data.json')
OUT=Path('pitch.json')
items=json.loads(ITEMS.read_text(encoding='utf-8'))

THEMES={
    'investment':['투자','증자','자금','억원','조원','investment','funding','capex','시설투자'],
    'capacity':['증설','공장','생산','라인','가동','capacity','plant','production','factory','생산능력'],
    'restructuring':['감원','인력감축','축소','철수','조직개편','거점축소','거점 재편','재편','layoff','shutdown','restructure','ceo 교체'],
    'tariff':['관세','통상','공급망','tariff','trade','supply chain'],
    'ev_to_ess':['ESS','에너지저장','전환','EV battery','storage','ESS 라인'],
    'order':['수주','계약','납품','고객사','order','contract'],
    'mobility':['AAM','로보택시','자율주행','모셔널','슈퍼널','모빌리티','robotaxi','autonomous'],
    'sales':['판매','출하','인도량','점유율','sales','deliveries','share'],
    'labor':['임금','임협','노조','파업','노사','wage','union','strike'],
    'product':['신차','출시','양산','모델','차종','product','launch','model'],
}
GENERIC=set('자동차 현대차 기아 배터리 전기차 관련 업계 시장 최근 오늘 미국 한국 중국 차량 자동 회사 산업 기업 뉴스 기사 전망'.split())
NOISE=set('주가 주식 증권 목표주가 투자자 고액자산가 네카오 급등 급락 추천 리서치센터'.split())

PAIR_FRAMES={
    ('investment','restructuring'):('투자 확대와 조직·거점 재편이 동시에','투자는 이어가는데 조직·거점은 재편되는 배경과 실제 전략 전환 폭을 확인'),
    ('investment','capacity'):('투자 확대와 생산능력 재편이 동시에','투자액이 실제 공장·라인 증설과 가동률 변화로 이어지는지 확인'),
    ('capacity','tariff'):('관세 대응이 생산·공급망 재편으로','관세 변화가 생산거점·조달선·국내 투자에 미친 실제 변화를 수치로 확인'),
    ('order','capacity'):('수주 확대와 생산능력 증설이 맞물려','수주 규모가 설비투자·생산능력 확대까지 이어지는지 확인'),
    ('order','investment'):('수주 확대가 추가 투자로 번지는지','신규 수주가 단순 계약인지 실제 자본지출·고용 확대로 이어지는지 확인'),
    ('ev_to_ess','capacity'):('EV에서 ESS로 생산축이 이동','EV 수요 변화가 어느 공장·라인의 ESS 전환으로 이어졌는지 확인'),
    ('mobility','investment'):('미래 모빌리티 투자와 사업 재편이 동시에','투자액·상용화 일정과 조직·거점 변화가 어떤 전략 전환을 의미하는지 확인'),
    ('sales','restructuring'):('판매 변화와 조직 재편이 동시에','판매·가동률 변화가 인력·거점 재편으로 이어졌는지 확인'),
    ('sales','investment'):('판매 흐름과 투자 방향이 엇갈려','수요 변화와 실제 투자 방향 사이의 간극과 이유를 확인'),
    ('labor','capacity'):('노사 변화가 생산계획에 직결돼','임단협 결과가 채용·가동일수·생산량에 미치는 실제 영향을 확인'),
    ('labor','investment'):('노사 비용 변화와 투자계획이 동시에','임금·채용 변화가 투자규모와 생산전략에 미치는 영향을 확인'),
    ('product','capacity'):('신차 확대와 생산능력 재편이 맞물려','신차 계획이 공장·라인·가동률 변화로 어떻게 연결되는지 확인'),
}


def display_title(x):
    return x.get('koTitle') if x.get('global') and x.get('koTitle') else x.get('title','')

def text(x):
    return ' '.join(str(v or '') for v in [display_title(x),x.get('summary',''),x.get('koSummary',''),x.get('whyNow','')])

def toks(s):
    return set(re.findall(r'[가-힣A-Za-z0-9]{2,}',s.lower()))

def nums(s):
    pat=r'\d+(?:\.\d+)?\s*(?:조원|억원|만원|억|조|만대|천대|%|명|개|곳|년|개월|GWh|kWh|km)'
    return list(dict.fromkeys(re.findall(pat,s,re.I)))

def theme_set(s):
    low=s.lower()
    return {k for k,words in THEMES.items() if any(w.lower() in low for w in words)}

def clean_tokens(s):
    return toks(s)-GENERIC-NOISE

def company_names(x):
    return [c for c in (x.get('companies') or []) if c and c not in NOISE]

# Build a candidate only from a REAL cross-theme pair. The two source articles must
# carry different business signals; same-company duplicate coverage is not enough.
buckets={}
for x in items:
    if x.get('exclusive'): continue
    for c in company_names(x):
        buckets.setdefault(c,[]).append(x)

candidates=[]
for company, arr in buckets.items():
    arr=sorted(arr,key=lambda x:x.get('published',''),reverse=True)[:50]
    # Dedup same-source near-identical headlines.
    uniq=[]; seen=set()
    for x in arr:
        sig=(x.get('sourceName'),re.sub(r'\W','',display_title(x)).lower()[:90])
        if sig in seen: continue
        seen.add(sig); uniq.append(x)
    arr=uniq

    # Compare every meaningful cross-theme pair.
    for i,a in enumerate(arr):
        ta=theme_set(text(a)); na=nums(text(a))
        if not ta: continue
        for b in arr[i+1:]:
            tb=theme_set(text(b)); nb=nums(text(b))
            common=ta & tb
            # Need two distinct themes spread across the two articles.
            pair=None
            for p in PAIR_FRAMES:
                if p[0] in ta and p[1] in tb: pair=p; break
                if p[1] in ta and p[0] in tb: pair=(p[1],p[0]); break
            if not pair: continue

            sources={a.get('sourceName'),b.get('sourceName')}-{None,''}
            domestic=[x for x in (a,b) if not x.get('global')]
            global_items=[x for x in (a,b) if x.get('global')]
            # Same source is insufficient unless three+ distinct corroborating items are available later.
            if len(sources)<2 and not (domestic and global_items):
                continue

            all_numbers=list(dict.fromkeys(na+nb))[:8]
            # At least one concrete numerical or quantitative signal is required.
            if not all_numbers:
                continue

            # For strongest quality, require topical token overlap beyond company name
            # OR a theme pair that is intrinsically consequential.
            overlap=clean_tokens(display_title(a)) & clean_tokens(display_title(b))
            if not overlap and pair not in {('investment','restructuring'),('ev_to_ess','capacity'),('capacity','tariff'),('mobility','investment')}:
                continue

            frame,angle=PAIR_FRAMES[pair]
            # Pull the most concrete facts from each side separately.
            fact_a=na[:4]
            fact_b=nb[:4]
            score=72
            score += 10 if len(sources)>=3 else 0
            score += 10 if domestic and global_items else 0
            score += 10 if len(all_numbers)>=2 else 0
            score += 8 if len(overlap)>=2 else 0
            score += 6 if pair in {('investment','restructuring'),('ev_to_ess','capacity'),('capacity','tariff'),('mobility','investment')} else 0
            score=min(98,score)
            if score<80: continue

            evidence=[
                {'source':a.get('sourceName'),'title':display_title(a),'url':a.get('url'),'published':a.get('published'),'themes':sorted(ta),'numbers':fact_a},
                {'source':b.get('sourceName'),'title':display_title(b),'url':b.get('url'),'published':b.get('published'),'themes':sorted(tb),'numbers':fact_b},
            ]

            # Make the headline express the INFORMATION RELATION, not a generic company summary.
            if pair==('investment','restructuring'):
                headline=f'{company}, 투자 확대하는데 조직·거점은 재편…사업 전략 바뀌나'
            elif pair==('ev_to_ess','capacity'):
                headline=f'{company}, EV 수요 변화에 ESS로 생산축 이동…어디까지 전환했나'
            elif pair==('capacity','tariff'):
                headline=f'{company}, 관세 대응에 생산·공급망 재편…국내 투자도 바뀌나'
            elif pair==('order','capacity'):
                headline=f'{company}, 수주 늘자 생산능력도 키운다…설비투자 본격화하나'
            elif pair==('order','investment'):
                headline=f'{company}, 수주 확대에 추가 투자…실제 증설 규모는'
            elif pair==('mobility','investment'):
                headline=f'{company}, 미래 모빌리티 투자는 계속…사업 전열은 재편'
            elif pair==('sales','restructuring'):
                headline=f'{company}, 판매 변화에 조직 재편…인력·거점 얼마나 줄이나'
            elif pair==('sales','investment'):
                headline=f'{company}, 판매 흐름과 투자 방향 엇갈려…전략 변화 주목'
            elif pair==('labor','capacity'):
                headline=f'{company}, 노사 합의가 생산계획 바꾼다…채용·가동일수 주목'
            elif pair==('labor','investment'):
                headline=f'{company}, 임금·채용 변화와 투자계획 맞물려…생산전략은'
            elif pair==('product','capacity'):
                headline=f'{company}, 신차 확대 맞춰 생산능력 재편…공장별 변화는'
            else:
                headline=f'{company}, {frame}'

            questions=[
                f'{company}의 {pair[0]}와 {pair[1]} 변화가 실제로 동시에 진행되는지 양측에 확인',
                '각 출처의 숫자를 사업보고서·실적자료·공시의 원수치와 대조',
                '전년 또는 직전 계획 대비 달라진 투자·생산·인력·일정이 무엇인지 확인',
                '경쟁사에도 동일한 변화가 나타나는지 비교해 산업적 의미를 확인',
            ]

            candidates.append({
                'id':f'P{len(candidates)+1:03d}',
                'pitchScore':score,
                'grade':'A' if score>=88 else 'B',
                'headline':headline,
                'frame':frame,
                'angle':angle,
                'category':a.get('category') or b.get('category') or '완성차',
                'companies':[company],
                'sourceCount':len(sources),
                'sources':sorted(sources),
                'globalSignals':len(global_items),
                'domesticSignals':len(domestic),
                'numbers':all_numbers,
                'themes':sorted(ta|tb),
                'evidence':evidence,
                'whyNow':f'{len(sources)}개 출처에서 {pair[0]}와 {pair[1]}이라는 서로 다른 사업 변화가 연결되고, 수치 {len(all_numbers)}개가 확인됩니다.',
                'questions':questions,
                'rawSignals':[display_title(a),display_title(b)],
            })

# Rank and suppress same-company/same-frame duplicates. Never pad the list.
candidates.sort(key=lambda x:(x['pitchScore'],x['sourceCount'],x['globalSignals'],len(x['numbers'])),reverse=True)
final=[]; seen=set()
for p in candidates:
    sig=(tuple(p['companies']),p['frame'])
    if sig in seen: continue
    seen.add(sig); final.append(p)
    if len(final)>=8: break

OUT.write_text(json.dumps(final,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
print(f'pitch builder: {len(final)} high-confidence pitch items')
