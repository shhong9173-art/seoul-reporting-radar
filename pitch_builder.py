from __future__ import annotations
import json, re
from collections import defaultdict
from pathlib import Path

items = json.loads(Path('data.json').read_text(encoding='utf-8'))
OUT = Path('pitch.json')

THEMES = {
    'investment': ['투자','증자','자금','억원','조원','investment','funding'],
    'capacity': ['증설','공장','생산','라인','가동','capacity','plant','production'],
    'restructuring': ['감원','축소','철수','조직','CEO','대표','거점','재편','restructuring','layoff','cut'],
    'tariff': ['관세','통상','공급망','tariff','trade','supply chain'],
    'ev_to_ess': ['ESS','에너지저장','전환','EV battery','storage'],
    'order': ['수주','계약','납품','고객사','order','contract'],
    'mobility': ['AAM','로보택시','자율주행','모빌리티','robotaxi','autonomous'],
    'sales': ['판매','출하','인도량','점유율','sales','deliveries','share'],
}
GENERIC = {'자동차','현대차','기아','배터리','전기차','관련','업계','시장','최근','오늘','미국','한국','중국','차량','자동','회사','산업'}

def text(x):
    return (x.get('title','') + ' ' + x.get('summary','') + ' ' + (x.get('koSummary') or '')).strip()

def toks(s):
    return set(re.findall(r'[가-힣A-Za-z0-9]{2,}', s.lower()))

def nums(s):
    return list(dict.fromkeys(re.findall(r'\d+(?:\.\d+)?\s*(?:조원|억원|만원|조|억|만대|천대|%|명|개|곳|년|개월|GWh|kWh|km)', s, re.I)))

def themes(s):
    s = s.lower()
    return {k for k, words in THEMES.items() if any(w.lower() in s for w in words)}

def display_title(x):
    return x.get('koTitle') if x.get('global') and x.get('koTitle') else x.get('title','')

# Build evidence groups by company, then merge related stories within the latest 7 days.
buckets = defaultdict(list)
for x in items:
    if x.get('exclusive'):
        continue
    for company in (x.get('companies') or []):
        buckets[company].append(x)

candidates = []
for company, arr in buckets.items():
    arr = sorted(arr, key=lambda x: x.get('published',''), reverse=True)
    uniq = []
    seen = set()
    for x in arr:
        sig = (x.get('sourceName'), re.sub(r'\W','',display_title(x))[:90])
        if sig in seen:
            continue
        seen.add(sig)
        uniq.append(x)
    sources = list(dict.fromkeys(x.get('sourceName') for x in uniq if x.get('sourceName')))
    if len(sources) < 2:
        continue

    selected = uniq[:8]
    alltext = ' '.join(text(x) for x in selected)
    th = themes(alltext)
    numbers = list(dict.fromkeys(sum((nums(text(x)) for x in selected), [])))[:10]
    domestic = [x for x in selected if not x.get('global')]
    global_items = [x for x in selected if x.get('global')]

    # Reject simple duplicate-news clusters unless there is a second substantive signal.
    signal_pairs = [
        ('investment','restructuring'), ('investment','capacity'), ('investment','order'),
        ('tariff','capacity'), ('tariff','investment'), ('ev_to_ess','investment'),
        ('mobility','investment'), ('sales','investment'), ('sales','restructuring'),
    ]
    pair = next((p for p in signal_pairs if set(p) <= th), None)
    if not pair and len(th) < 2 and not numbers:
        continue

    if pair == ('investment','restructuring'):
        frame = '투자는 이어가는데 조직·거점은 줄인다'
        angle = f'{company}의 투자 확대와 조직·거점 재편이 동시에 진행되는 배경과 실제 전략 변화를 확인'
    elif pair == ('ev_to_ess','investment'):
        frame = 'EV에서 ESS로 무게중심 이동'
        angle = f'{company}의 EV 투자와 ESS 전환 흐름을 묶어 생산·제품 포트폴리오 변화 확인'
    elif pair and pair[0] == 'tariff':
        frame = '관세 대응 위해 생산·공급망 재편'
        angle = f'관세 변화가 {company}의 생산·조달·투자 결정에 실제로 미친 영향 확인'
    elif pair == ('mobility','investment'):
        frame = '미래 모빌리티 투자와 사업 재편 병행'
        angle = f'{company}의 미래 모빌리티 투자 규모와 사업 재편이 같은 전략 아래 움직이는지 확인'
    elif pair == ('sales','restructuring'):
        frame = '판매 흐름 악화에 조직 재편'
        angle = f'{company}의 판매·수요 변화와 조직 축소가 연결되는지 확인'
    else:
        frame = '투자·생산·수주 변화가 동시에 포착된다'
        angle = f'{company} 관련 최근 자료를 교차해 단순 동향을 넘어선 전략 변화 여부 확인'

    score = 60
    score += min(18, max(0, (len(sources)-2) * 6))
    score += 12 if numbers else 0
    score += 12 if len(numbers) >= 2 else 0
    score += 10 if global_items and domestic else 0
    score += 8 if pair else 0
    score += 6 if len(th) >= 3 else 0
    score = max(65, min(97, score))

    questions = [
        f'{company}의 추가 투자·생산·조직 변화 규모와 시점은?',
        '최근 자료에서 전년 또는 직전 계획과 달라진 숫자는?',
        '회사·정부가 공식 확인하지 않은 핵심 사실은?',
        '경쟁사·공급망에도 같은 변화가 나타나는가?',
    ]

    candidates.append({
        'id': f'P{len(candidates)+1:03d}',
        'pitchScore': score,
        'grade': 'A' if score >= 85 else 'B',
        'headline': f'{company}, {frame}',
        'frame': frame,
        'angle': angle,
        'category': selected[0].get('category') or '완성차',
        'companies': [company],
        'sourceCount': len(sources),
        'sources': sources[:8],
        'globalSignals': len(global_items),
        'domesticSignals': len(domestic),
        'numbers': numbers,
        'evidence': [
            {'source': x.get('sourceName'), 'title': display_title(x), 'url': x.get('url'), 'published': x.get('published')}
            for x in selected[:6]
        ],
        'whyNow': f'{len(sources)}개 매체에서 {company} 관련 신호가 확인됐고, {len(numbers)}개의 수치 정보와 {len(th)}개 변화 축을 교차했습니다.',
        'questions': questions,
        'rawSignals': [display_title(x) for x in selected[:4]],
    })

candidates.sort(key=lambda x: (x['pitchScore'], x['sourceCount'], x['globalSignals'], len(x['numbers'])), reverse=True)
final = []
seen = set()
for p in candidates:
    sig = (tuple(p['companies']), p['frame'])
    if sig in seen:
        continue
    seen.add(sig)
    final.append(p)
    if len(final) >= 10:
        break

OUT.write_text(json.dumps(final, ensure_ascii=False, separators=(',',':')), encoding='utf-8')
print(f'pitch builder: {len(final)} synthesized items')
