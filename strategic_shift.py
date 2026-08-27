from __future__ import annotations
import json,re
from pathlib import Path
from datetime import datetime,timezone,timedelta

DATA=Path('data.json'); CHANGES=Path('changes.json'); DART=Path('dart_numeric.json'); OUT=Path('strategic_shifts.json')
items=json.loads(DATA.read_text(encoding='utf-8')) if DATA.exists() else []
try: changes=json.loads(CHANGES.read_text(encoding='utf-8')) if CHANGES.exists() else {'changes':[],'snapshots':[]}
except: changes={'changes':[],'snapshots':[]}
try: numeric=json.loads(DART.read_text(encoding='utf-8')).get('items',[]) if DART.exists() else []
except: numeric=[]
now=datetime.now(timezone.utc)
AUTO={'완성차','부품','배터리','정책·관세','중국차','노조·생산','리콜·안전','수주·투자'}
IND={'철강','비철금속','전력기기','전선·전력','에너지','재생에너지','화학·소재'}
CATS=AUTO|IND
NOISE={'주가','주식','증권','목표주가','급등','급락','추천','관련주','테마주','특징주'}

def txt(x): return ' '.join(str(x.get(k) or '') for k in ('title','koTitle','summary','koSummary'))
def company(x): return (x.get('companies') or [None])[0]
def dt(x):
    try:return datetime.fromisoformat(str(x.get('published','')).replace('Z','+00:00'))
    except:return datetime.min.replace(tzinfo=timezone.utc)
def nums(s): return list(dict.fromkeys(re.findall(r'(?<!\d)(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?:조원|억원|만원|만대|천대|대|명|%|GWh|MWh|kWh|톤|km|MW|GW)(?!\w)',s or '',re.I)))
def meaningful(x): return (not x.get('global')) and x.get('category') in CATS and company(x) and not any(w in txt(x).lower() for w in NOISE)

def join_terms(c):
    rel=[x for x in items if meaningful(x) and company(x)==c and now-dt(x)<=timedelta(days=30)]
    titles=' '.join(txt(x) for x in rel[:40]).lower(); sig=[]
    for k,ws in {
        '투자 확대':['투자','시설투자','출자','증설','capex'],
        '생산 확대':['생산능력','증산','공장','라인','가동'],
        '수주 확대':['수주','계약','공급계약','수주잔고'],
        '사업재편':['철수','매각','구조조정','합병','분할','거점축소'],
        '가격·원가 변화':['원가','가격','마진','관세','반덤핑'],
        '신사업 전환':['상용화','신사업','로봇','자율주행','배터리','소재']}.items():
        if any(w in titles for w in ws): sig.append(k)
    return rel,sig

out=[]
for ch in changes.get('changes',[]):
    c=ch.get('company'); cat=ch.get('category')
    if not c or cat not in CATS: continue
    rel,sig=join_terms(c)
    signals=list(dict.fromkeys((ch.get('signals') or [])+sig))
    if len(signals)<2 and not ch.get('newNumbers'): continue
    # DART evidence by company; require a recent report when available
    de=[r for r in numeric if r.get('corpName')==c]
    recent_d=[r for r in de if str(r.get('date','')).isdigit() and (now-datetime.strptime(str(r['date']),'%Y%m%d').replace(tzinfo=timezone.utc)).days<=90]
    numbers=list(dict.fromkeys((ch.get('newNumbers') or [])+[n for r in recent_d[:3] for n in (r.get('numbers') or [])[:8]]))[:8]
    # suppress purely repetitive changes
    if not rel or not numbers: continue
    latest=max(rel,key=dt)
    if set(signals)>={'투자·생산'} or ('투자' in signals and '생산' in signals) or ('투자 확대' in signals and '생산 확대' in signals):
        headline=f"{c}, {numbers[0]} 투자에 수주·생산도 움직였다…증설 전략 본격화"
        angle=f"{c}의 투자 확대가 실제 수주 증가와 생산능력 확충으로 이어지는지 확인하고, 증설 이후 가동률과 수익성이 따라오는지 점검"
    elif '사업재편' in signals and ('투자 확대' in signals or '생산 확대' in signals):
        headline=f"{c}, 사업재편 속 {numbers[0]} 추가 투자…돈줄은 성장사업으로"
        angle=f"사업재편과 동시에 늘어난 투자가 철수 비용인지 성장사업 재배치인지, 자산·생산·수익구조 변화를 통해 확인"
    elif '수주 확대' in signals and ('가격·원가 변화' in signals or '생산 확대' in signals):
        headline=f"{c}, 수주 늘었는데 {numbers[0]}…물량보다 원가가 관건"
        angle=f"수주 증가가 외형 확대에 그치는지, 생산능력·원가·마진까지 개선하는지 확인"
    elif '신사업 전환' in signals:
        headline=f"{c}, 기존 사업서 신사업으로 무게중심 이동…투자 숫자에 흔적"
        angle=f"최근 공시·보도에서 확인된 투자와 신사업 신호를 연결해 실제 사업 포트폴리오 전환인지 점검"
    else:
        headline=f"{c}, 최근 사업 신호가 달라졌다…{cat} 전략 변화 시작됐나"
        angle=f"최근 30일간 달라진 {cat} 관련 투자·생산·수주 신호가 일시적 변화인지 구조적인 전략 전환인지 확인"
    evidence=[{'source':x.get('sourceName') or '-', 'title':x.get('title') or x.get('koTitle') or '', 'url':x.get('url'), 'published':x.get('published'), 'numbers':nums(txt(x))[:4]} for x in rel[:3]]
    evidence += [{'source':'DART','title':r.get('reportName') or '공시','url':r.get('url'),'published':r.get('date'),'numbers':(r.get('numbers') or [])[:6]} for r in recent_d[:2]]
    sources=list(dict.fromkeys(e['source'] for e in evidence if e['source'] and e['source']!='-'))
    out.append({'type':'strategic-shift','grade':'A','score':96+min(4,len(signals)),'headline':headline,'company':c,'category':cat,'angle':angle,
      'brief':[f"최근 30일 {c} 관련 {cat} 신호 변화: {', '.join(signals)}",f"새로 잡힌 숫자: {', '.join(numbers[:5])}",f"기존 기사와 공시를 대조해 투자→생산→수주로 이어지는 실제 전략 변화 확인",f"변화가 일시적 이벤트인지 지속 가능한 사업 전환인지 점검"],
      'signals':signals,'numbers':numbers,'evidence':evidence[:5],'sources':sources[:6],'whyNow':'최근 30일 보도·공시에서 사업 신호가 동시에 변한 시점','questions':['최근 투자·수주·생산 숫자가 서로 연결되는가?','기존 회사 계획과 비교하면 무엇이 달라졌는가?','경쟁사도 같은 방향으로 움직이는가?','실제 매출·가동률·원가에 영향을 줄 변화인가?'],
      'articlePlan':['최근 달라진 숫자와 사업 신호 제시','기존 계획·과거 수치와 비교','수주·생산·원가 연결해 실제 변화 검증','경쟁사와 비교해 산업적 의미 제시']})
out.sort(key=lambda x:(x['score'],len(x['numbers']),len(x['evidence'])),reverse=True)
# one shift per company/category cluster
final=[]; seen=set()
for x in out:
    k=(x['company'],x['category'])
    if k in seen: continue
    seen.add(k); final.append(x)
    if len(final)>=12: break
OUT.write_text(json.dumps({'generatedAt':now.isoformat(),'items':final},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
print(f'strategic shifts: {len(final)}')
