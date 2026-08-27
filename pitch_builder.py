from __future__ import annotations
import json,re
from pathlib import Path
from datetime import datetime, timezone, timedelta

DATA=Path('data.json'); OUT=Path('pitch.json')
items=json.loads(DATA.read_text(encoding='utf-8')) if DATA.exists() else []
AUTO={'완성차','부품','배터리','정책·관세','중국차','노조·생산','수주·투자','리콜·안전','단독','미국·글로벌'}
IND={'철강','비철금속','전력기기','전선·전력','에너지','재생에너지','화학·소재'}
NOISE={'주가','주식','증권','목표주가','급등','급락','추천','관련주','테마주','특징주'}
STRATEGY={'투자','시설투자','출자','유상증자','증설','생산능력','공장','가동','감산','철수','매각','인수','합작','재편','구조조정','수주','계약','납품','공급','관세','통상','공급망','가격','원가','마진','전력망','변압기','HVDC','해저케이블','풍력','태양광','ESS','석유화학','스페셜티','배터리소재','생산','거점','진출','철강','제련'}
MONEY=re.compile(r'(?<!\d)(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?:조원|억원|만원|억|조|만대|천대|대|명|%|GWh|MWh|kWh|톤|km|MW|GW)(?!\w)',re.I)

def text(x): return ' '.join(str(x.get(k) or '') for k in ('title','koTitle','summary','koSummary')).strip()
def companies(x): return [c for c in (x.get('companies') or []) if c]
def dt(x):
    try:return datetime.fromisoformat(str(x.get('published','')).replace('Z','+00:00'))
    except:return datetime.now(timezone.utc)
def nums(s): return list(dict.fromkeys(MONEY.findall(s or '')))
def recent(c,days=30):
    cut=datetime.now(timezone.utc)-timedelta(days=days)
    return [x for x in items if c in companies(x) and dt(x)>=cut and not x.get('global')]
def exact_amount_covered(c,n): return any(n in text(x) for x in recent(c))
def meaningful(x):
    if x.get('global') or x.get('category') not in AUTO|IND or not companies(x):return False
    t=text(x)
    return not any(n in t for n in NOISE) and bool(nums(t)) and bool(STRATEGY & set(k for k in STRATEGY if k.lower() in t.lower()))
def theme(t):
    low=t.lower(); out=[]
    if any(k in low for k in ('투자','출자','증설','공장','생산능력','가동')):out.append('투자·생산전략')
    if any(k in low for k in ('수주','계약','납품','공급')):out.append('수주·공급망')
    if any(k in low for k in ('관세','통상','공급망')):out.append('통상·공급망')
    if any(k in low for k in ('가격','원가','마진')):out.append('가격·원가')
    if any(k in low for k in ('철수','매각','재편','구조조정','거점')):out.append('사업재편')
    return out

def mk_strategy(x):
    c=companies(x)[0]; t=text(x); ns=nums(t); arr=recent(c)
    new=[n for n in ns if not exact_amount_covered(c,n)]
    th=theme(t)
    if not new or not th:return None
    # Require an additional independent signal so the item is more than a single-news rewrite.
    others=[a for a in arr if a.get('url')!=x.get('url') and theme(text(a))]
    if not others:return None
    n=new[0]
    return {'type':'strategy-change','grade':'A','pitchScore':96,'headline':f"{c}, {n} 규모 변화…기존 계획과 달라진 이유는",
      'category':x.get('category'),'companies':[c],
      'newFact':f"{x.get('sourceName') or '-'}에서 {n} 규모의 구체적 수치가 확인됐지만 최근 보도에서 같은 수치가 명확히 확인되지 않음.",
      'angle':f"{th[0]} 변화가 일회성 발표가 아니라 {c}의 실제 사업전략 변화인지 확인.",
      'differentiator':'공시·기사에 흩어진 숫자와 과거 계획을 대조해 아직 기사화되지 않은 변화를 찾는 방식.',
      'whyNow':'최근 자료와 신규 수치가 동시에 포착돼 계획 대비 변화 여부를 확인할 수 있는 시점.',
      'numbers':new[:6],'sourceCount':1+len({a.get('sourceName') for a in others[:5] if a.get('sourceName')}),'globalSignals':0,'domesticSignals':1+len(others[:5]),
      'sources':list(dict.fromkeys([x.get('sourceName') or '-']+[a.get('sourceName') for a in others[:5] if a.get('sourceName')])),
      'evidence':[{'source':x.get('sourceName') or '-','title':x.get('title') or '','url':x.get('url'),'published':x.get('published'),'numbers':ns[:6]}]+[{'source':a.get('sourceName') or '-','title':a.get('title') or '','url':a.get('url'),'published':a.get('published'),'numbers':nums(text(a))[:4]} for a in others[:2]],
      'questions':['이 숫자가 기존 공개 계획보다 얼마나 달라졌는가?','실제 투자·생산·수주·원가에 어떤 변화가 나타났는가?','회사 설명과 공시·사업보고서 수치가 일치하는가?','경쟁사 대비 같은 변화가 나타나고 있는가?']}

def mk_industry(c,arr):
    arr=sorted([a for a in arr if meaningful(a)],key=dt,reverse=True)[:15]
    if len(arr)<2:return None
    # Need two different source-level signals and different themes, not two copies of the same story.
    for i,a in enumerate(arr):
        for b in arr[i+1:]:
            if a.get('sourceName')==b.get('sourceName'):continue
            ta=set(theme(text(a))); tb=set(theme(text(b)))
            na=set(nums(text(a))); nb=set(nums(text(b)))
            if not ta or not tb or ta==tb or not (na|nb):continue
            return {'type':'industry-issue','grade':'A','pitchScore':94,'headline':f"{c}, {('·'.join(sorted(ta|tb)[:2]))} 변화…업계 판도 어디까지 바뀌나",
              'category':a.get('category') or b.get('category'),'companies':[c],
              'newFact':f"서로 다른 출처에서 {', '.join(sorted(ta|tb)[:4])} 관련 수치와 사업 신호가 동시에 확인됨.",
              'angle':'개별 기사를 합치는 데 그치지 않고 여러 숫자와 움직임을 연결해 산업 구조 변화로 확인.',
              'differentiator':'복수 출처에서 서로 다른 사실을 묶어 하나의 산업 변화로 만드는 아이템.',
              'whyNow':'최근 30일 내 서로 다른 사업 신호가 동시에 포착됨.',
              'numbers':list(dict.fromkeys(nums(text(a))+nums(text(b))))[:6],'sourceCount':2,'globalSignals':0,'domesticSignals':2,
              'sources':[a.get('sourceName') or '-',b.get('sourceName') or '-'],
              'evidence':[{'source':a.get('sourceName') or '-','title':a.get('title') or '','url':a.get('url'),'published':a.get('published'),'numbers':nums(text(a))[:4]}, {'source':b.get('sourceName') or '-','title':b.get('title') or '','url':b.get('url'),'published':b.get('published'),'numbers':nums(text(b))[:4]}],
              'questions':['두 기사에서 언급한 사업·제품·공장이 실제 같은 흐름인지 확인','공시·IR에서 관련 수치를 대조','기업의 생산·투자·수주 전략이 실제로 바뀌었는지 확인','경쟁사도 같은 방향으로 움직이는지 확인']}
    return None

candidates=[]
for x in items:
    if meaningful(x):
        p=mk_strategy(x)
        if p:candidates.append(p)
for c in sorted({c for x in items for c in companies(x)}):
    p=mk_industry(c,recent(c))
    if p:candidates.append(p)

candidates.sort(key=lambda p:(p['grade']=='A',p['pitchScore'],len(p.get('numbers') or [])),reverse=True)
final=[]
for p in candidates:
    dup=False
    for q in final:
        if set(p['companies']) & set(q['companies']):
            if set(p.get('numbers') or []) & set(q.get('numbers') or []):dup=True;break
            a=set(re.findall(r'[가-힣A-Za-z0-9]{2,}',p['headline']));b=set(re.findall(r'[가-힣A-Za-z0-9]{2,}',q['headline']))
            if len(a&b)/max(1,len(a|b))>=0.45:dup=True;break
    if not dup: final.append(p)
    if len(final)>=3:break
OUT.write_text(json.dumps(final,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
print(f'pitch rebuild: {len(final)} items / strategy-change + industry-issue only / max 3 / events excluded')
