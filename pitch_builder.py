from __future__ import annotations
import json,re
from pathlib import Path
from datetime import datetime, timezone, timedelta

DATA=Path('data.json'); DART=Path('dart.json'); NUM=Path('dart_numeric.json'); OUT=Path('pitch.json')
items=json.loads(DATA.read_text(encoding='utf-8')) if DATA.exists() else []
dart=json.loads(DART.read_text(encoding='utf-8')).get('items',[]) if DART.exists() else []
numeric=json.loads(NUM.read_text(encoding='utf-8')).get('items',[]) if NUM.exists() else []
AUTO={'완성차','부품','배터리','정책·관세','중국차','노조·생산','수주·투자','리콜·안전','단독','미국·글로벌'}
IND={'철강','비철금속','전력기기','전선·전력','에너지','재생에너지','화학·소재'}
NOISE={'주가','주식','증권','목표주가','급등','급락','추천','관련주','테마주','특징주'}
EVENT={'인베스터데이','주주총회','설명회','세미나','포럼','엑스포','컨퍼런스','부스투어','기조연설','발표회'}
THEMES={
 '투자·생산':['투자','시설투자','출자','증설','생산능력','공장','가동','라인','감산'],
 '사업재편':['철수','매각','재편','구조조정','거점축소','인수','합병','분할','합작'],
 '수주·공급망':['수주','계약','납품','공급','공급망','조달'],
 '통상·가격':['관세','통상','반덤핑','가격','원가','마진'],
 '전력·에너지':['전력망','변압기','HVDC','해저케이블','풍력','해상풍력','재생에너지','ESS'],
 '제품·기술':['양산','상용화','자율주행','로보택시','신차','배터리','소재']}
NUM_RE=re.compile(r'(?<!\d)(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?:조원|억원|만원|만대|천대|대|명|%|GWh|MWh|kWh|톤|km|MW|GW)(?!\w)',re.I)

def txt(x): return ' '.join(str(x.get(k) or '') for k in ('title','koTitle','summary','koSummary')).strip()
def cs(x): return [c for c in x.get('companies',[]) if c]
def dt(x):
    try:return datetime.fromisoformat(str(x.get('published','')).replace('Z','+00:00'))
    except:return datetime.min.replace(tzinfo=timezone.utc)
def nums(s): return list(dict.fromkeys(NUM_RE.findall(s or '')))
def themes(s):
    low=(s or '').lower(); return {k for k,ws in THEMES.items() if any(w.lower() in low for w in ws)}
def recent(c,days=30):
    cut=datetime.now(timezone.utc)-timedelta(days=days)
    return [x for x in items if c in cs(x) and not x.get('global') and dt(x)>=cut]
def source_count(arr): return len({x.get('sourceName') for x in arr if x.get('sourceName')})
def reported_amount(c,n): return any(n in txt(x) for x in recent(c,45))
def clean_tokens(s): return set(re.findall(r'[가-힣A-Za-z0-9]{2,}',(s or '').lower()))-NOISE

def money_from_numeric(row):
    vals=[]
    for n in row.get('numbers') or []:
        s=str(n)
        if re.search(r'(?:조원|억원|만원|달러|USD|EUR|원)$',s): vals.append(s)
    return list(dict.fromkeys(vals))

def relevant_category(x): return (not x.get('global')) and x.get('category') in AUTO|IND and bool(cs(x))
def event_only(s): return any(w in (s or '').lower() for w in EVENT)

def build_dart():
    out=[]
    for r in numeric:
        corp=r.get('corpName',''); vals=money_from_numeric(r)
        if not corp or not vals: continue
        report=str(r.get('reportName') or '')
        if not any(k in report for k in ('시설투자','출자','유상증자','타법인','지분','생산중단','영업양수도','합병','분할','주요사항','사업보고서','반기보고서','분기보고서')): continue
        news=recent(corp,45)
        fresh=[v for v in vals if not reported_amount(corp,v)]
        if not fresh: continue
        related=[x for x in news if themes(txt(x))]
        if not related: continue
        th=set().union(*(themes(txt(x)) for x in related[:12]))
        if not th: continue
        primary=fresh[0]
        if '시설투자' in report or '생산' in report:
            head=f'{corp}, {primary} 투자…생산능력·사업전략 실제 변화는'
            angle='공시 투자금액이 어느 생산거점·제품에 집행되는지, 기존 계획 대비 확대·축소됐는지 확인'
        elif any(k in report for k in ('타법인','지분','출자')):
            head=f'{corp}, {primary} 규모 지분·출자 변화…자금이 향한 곳은'
            angle='공시상 자금의 실제 사용처와 기존 사업전략 변화 여부를 확인'
        elif any(k in report for k in ('합병','분할','영업양수도')):
            head=f'{corp}, {report}…사업재편 이후 달라지는 생산·투자 지도는'
            angle='재편 전후 사업·생산·인력 구조가 어떻게 달라지는지 확인'
        else:
            head=f'{corp}, 공시에서 드러난 {primary} 변화…기존 계획과 달라졌나'
            angle='새 공시 숫자가 기존 계획·실적과 어떤 차이를 만드는지 확인'
        evidence=[{'source':'DART','title':report,'url':r.get('url'),'published':r.get('date'),'numbers':fresh[:6]}]
        for n in related[:3]: evidence.append({'source':n.get('sourceName') or '-','title':n.get('title') or '','url':n.get('url'),'published':n.get('published'),'numbers':nums(txt(n))[:4]})
        out.append({'type':'dart-led','grade':'A','pitchScore':96,'headline':head,'category':related[0].get('category') or '산업','companies':[corp],
          'newFact':f'DART {report}에서 {", ".join(fresh[:4])}의 신규 수치가 확인됐고, 최근 보도에서는 같은 수치가 확인되지 않음.',
          'angle':angle,'differentiator':'DART 원문 수치와 최근 보도 범위를 대조해 아직 기사화되지 않은 사업 변화만 추린 아이템.',
          'whyNow':'최근 공시와 기존 보도의 숫자·계획이 어긋나는 지점을 확인할 수 있는 시점.',
          'numbers':fresh[:6],'sourceCount':1+source_count(related[:3]),'globalSignals':0,'domesticSignals':len(related[:3]),
          'sources':['DART']+list(dict.fromkeys([n.get('sourceName') for n in related[:3] if n.get('sourceName')])),
          'evidence':evidence,'dartSignals':[d for d in dart if d.get('corpName')==corp][:4],'dartNumericSignals':[r],'dartNumericCount':len(fresh),
          'questions':['이 숫자가 기존 공개 계획보다 얼마나 달라졌는가?','실제 투자·생산·수주·원가에 변화가 나타났는가?','회사 설명과 DART 원문이 정확히 일치하는가?','경쟁사에도 같은 변화가 나타나는가?'],
          'articlePlan':['새로운 숫자·변화 제시','기존 계획·최근 보도와 비교','실제 생산·투자·수주 영향 확인','산업·경쟁사에 미치는 파장 제시']})
    return out

def build_gap():
    out=[]
    for c in sorted({c for x in items for c in cs(x)}):
        arr=[x for x in recent(c,45) if relevant_category(x) and not event_only(txt(x))]
        if source_count(arr)<2: continue
        # one signal with concrete number + another different business theme
        for i,a in enumerate(arr[:20]):
            ta=themes(txt(a)); na=nums(txt(a))
            for b in arr[i+1:20]:
                if a.get('sourceName')==b.get('sourceName'): continue
                tb=themes(txt(b)); nb=nums(txt(b))
                if not na or not nb or ta==tb or not (ta-tb or tb-ta): continue
                shared=clean_tokens(a.get('title','')) & clean_tokens(b.get('title',''))
                if len(shared)<1: continue
                headline=f'{c}, {"·".join(sorted(ta|tb)[:2])} 동시 변화…실제 사업전략 바뀌나'
                out.append({'type':'cross-source','grade':'A','pitchScore':93,'headline':headline,'category':a.get('category') or b.get('category'),'companies':[c],
                  'newFact':f'{a.get("sourceName")}와 {b.get("sourceName")}에서 서로 다른 사업 신호와 구체적 수치가 동시에 확인됨.',
                  'angle':'각각 따로 보도된 숫자·사업 움직임이 실제 하나의 전략 변화로 이어지는지 확인',
                  'differentiator':'같은 기사를 재가공하지 않고 서로 다른 출처의 사실을 연결해 새로운 취재 질문을 만드는 방식.',
                  'whyNow':'최근 45일 보도에서 서로 다른 사업 신호가 겹쳐 실체 확인 가치가 생긴 시점.',
                  'numbers':list(dict.fromkeys(na+nb))[:6],'sourceCount':2,'globalSignals':0,'domesticSignals':2,
                  'sources':[a.get('sourceName') or '-',b.get('sourceName') or '-'],
                  'evidence':[{'source':a.get('sourceName') or '-','title':a.get('title') or '','url':a.get('url'),'published':a.get('published'),'numbers':na[:4]},{'source':b.get('sourceName') or '-','title':b.get('title') or '','url':b.get('url'),'published':b.get('published'),'numbers':nb[:4]}],
                  'dartSignals':[],'dartNumericSignals':[],'dartNumericCount':0,
                  'questions':['두 출처가 가리키는 사업·공장·제품이 실제 같은 흐름인지 확인','공시·IR에서 관련 수치 대조','생산·투자·수주 전략 변화 확인','경쟁사도 같은 방향인지 비교'],
                  'articlePlan':['각 출처의 핵심 사실을 제시','숫자·일정의 차이와 연결고리 확인','회사·공시로 실체 검증','경쟁사와 산업 영향 비교']})
                break
            if out and out[-1].get('companies')==[c]: break
    return out

candidates=build_dart()+build_gap()
candidates.sort(key=lambda p:(p.get('grade')=='A',p.get('pitchScore',0),p.get('dartNumericCount',0),len(p.get('numbers') or [])),reverse=True)
final=[]
for p in candidates:
    dup=False
    pc=set(p.get('companies') or []); pn=set(p.get('numbers') or []); ph=clean_tokens(p.get('headline',''))
    for q in final:
        qc=set(q.get('companies') or []); qn=set(q.get('numbers') or []); qh=clean_tokens(q.get('headline',''))
        if pc==qc and ((pn & qn) or len(ph&qh)/max(1,len(ph|qh))>=.5): dup=True; break
    if not dup: final.append(p)
    if len(final)>=3: break

OUT.write_text(json.dumps(final,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
print(f'pitch rebuild: {len(final)} items / report-derived strategy-change + industry-issue / events excluded / max 3')
