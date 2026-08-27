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
LEGAL_RE=re.compile(r'(?:^|\s)제?\d+조(?:의\d+)?(?:$|\s)')

def txt(x): return ' '.join(str(x.get(k) or '') for k in ('title','koTitle','summary','koSummary')).strip()
def cs(x): return [c for c in x.get('companies',[]) if c]
def dt(x):
    try:return datetime.fromisoformat(str(x.get('published','')).replace('Z','+00:00'))
    except:return datetime.min.replace(tzinfo=timezone.utc)
def nums(s): return list(dict.fromkeys(NUM_RE.findall(s or '')))
def themes(s):
    low=(s or '').lower(); return {k for k,ws in THEMES.items() if any(w.lower() in low for w in ws)}
def event_only(s): return any(w in (s or '').lower() for w in EVENT)
def recent(c,days=45):
    cut=datetime.now(timezone.utc)-timedelta(days=days)
    return [x for x in items if c in cs(x) and not x.get('global') and dt(x)>=cut and not event_only(txt(x))]
def source_count(arr): return len({x.get('sourceName') for x in arr if x.get('sourceName')})
def clean_tokens(s): return set(re.findall(r'[가-힣A-Za-z0-9]{2,}',(s or '').lower()))-NOISE

def money_from_numeric(row):
    vals=[]
    for n in row.get('numbers') or []:
        s=str(n).strip()
        if LEGAL_RE.search(s): continue
        if re.search(r'(?:조원|억원|만원|원|조|억|달러|USD|EUR)$',s): vals.append(s)
    return list(dict.fromkeys(vals))

def relevant(x): return (not x.get('global')) and x.get('category') in AUTO|IND and bool(cs(x))
def meaningful(x):
    if not relevant(x): return False
    t=txt(x)
    return not any(n in t for n in NOISE) and bool(nums(t)) and bool(themes(t)) and not event_only(t)

def best_topic(s):
    low=(s or '').lower()
    for keys,label in [
        (('수소환원','hyrex'),'수소환원제철'),
        (('전기차','ev','배터리'),'전기차·배터리'),
        (('로보택시','자율주행'),'자율주행'),
        (('해저케이블','hvdc','전력망','변압기'),'전력망·전력기기'),
        (('풍력','해상풍력'),'풍력'),
        (('석유화학','스페셜티'),'석유화학'),
        (('철강','고로','제철'),'철강'),
        (('구리','아연','니켈','제련'),'비철금속')]:
        if any(k in low for k in keys): return label
    return None

def evidence_title(x):
    title=txt(x)
    return title[:110] + ('…' if len(title)>110 else '')

def strategy_headline(c, topic, th, n):
    if topic=='수소환원제철': return f'{n} 투입하는 {c} 수소환원제철…탄소보다 원가가 관건'
    if topic=='전력망·전력기기': return f'{n} 투자하는 {c}…전력망 호황, 증설 따라잡나'
    if topic=='풍력': return f'{n} 투자하는 {c}…풍력 확대, 수익성까지 잡나'
    if '사업재편' in th: return f'{c}, 사업재편 속 {n} 규모 변화…생산·투자 전략 어디로'
    if '수주·공급망' in th and '투자·생산' in th: return f'{c}, 수주 늘자 {n} 투자…생산능력 확충이 관건'
    if '통상·가격' in th and '투자·생산' in th: return f'{c}, 관세·원가 부담 속 {n} 투자…가격 경쟁력 시험대'
    return f'{c}, {n} 규모 변화…기존 사업전략 어디까지 달라졌나'

def build_dart():
    out=[]
    for r in numeric:
        corp=r.get('corpName',''); report=str(r.get('reportName') or ''); vals=money_from_numeric(r)
        if not corp or not vals: continue
        if not any(k in report for k in ('시설투자','출자','유상증자','타법인','지분','생산중단','영업양수도','합병','분할','주요사항','사업보고서','반기보고서','분기보고서')): continue
        news=recent(corp,45)
        mentioned={n for x in news for n in nums(txt(x))}
        fresh=[v for v in vals if v not in mentioned]
        related=[x for x in news if meaningful(x) and corp in cs(x)]
        if not fresh or len(related)<1: continue
        combined=' '.join(txt(x) for x in related[:8]); top=best_topic(combined) or (related[0].get('category') or '사업')
        th=set().union(*(themes(txt(x)) for x in related[:8]))
        primary=fresh[0]
        headline=strategy_headline(corp,top,th,primary)
        evidence=[{'source':'DART','title':report,'url':r.get('url'),'published':r.get('date'),'numbers':fresh[:6]}]
        for x in related[:3]: evidence.append({'source':x.get('sourceName') or '-', 'title':evidence_title(x), 'url':x.get('url'),'published':x.get('published'),'numbers':nums(txt(x))[:4]})
        plan=[]
        for x in related[:2]:
            plan.append(f'{x.get("sourceName") or "매체"}: {evidence_title(x)}')
        plan.append(f'DART {report}의 {primary}와 기존 공개 투자·생산 계획을 대조')
        if '통상·가격' in th: plan.append('철광석·원료탄·전력 등 투입비용 변화를 붙여 원가·마진 영향 확인')
        elif '수주·공급망' in th: plan.append('수주잔고·가동률·증설 규모를 연결해 생산능력 부족 여부 확인')
        elif '사업재편' in th: plan.append('재편 전후 공장·인력·자산 변화를 비교해 전략 전환 실체 확인')
        else: plan.append('실제 매출·생산·수익성 변화와 경쟁사 움직임 확인')
        out.append({'type':'strategy-change','grade':'A','pitchScore':98,'headline':headline,'category':related[0].get('category') or '산업','companies':[corp],
          'newFact':f'DART {report}에서 {", ".join(fresh[:4])}의 구체적 수치가 확인됨. 최근 기사와 대조했을 때 이 수치가 의미하는 사업 변화가 충분히 다뤄지지 않음.',
          'angle':f'{corp}의 {primary} 변화가 단순 숫자 변화인지, 실제 생산·투자·수주·원가 전략 전환으로 이어지는지 확인',
          'differentiator':'공시 원문·최근 보도·과거 계획을 함께 대조해 이미 보도된 사실이 아니라 아직 설명되지 않은 변화를 찾음.',
          'whyNow':'최근 공시에서 새 숫자가 확인돼 기존 계획과 현재 사업 흐름을 다시 대조할 수 있는 시점.',
          'numbers':fresh[:6],'sourceCount':1+source_count(related[:3]),'globalSignals':0,'domesticSignals':len(related[:3]),
          'sources':['DART']+list(dict.fromkeys([x.get('sourceName') for x in related[:3] if x.get('sourceName')])),
          'evidence':evidence,'dartSignals':[d for d in dart if d.get('corpName')==corp][:4],'dartNumericSignals':[r],'dartNumericCount':len(fresh),
          'questions':['기존 공개 계획·사업보고서 수치와 실제 집행액이 얼마나 다른가?','이 숫자가 생산능력·가동률·수주·원가에 어떤 변화로 이어지는가?','회사 설명과 DART 원문 수치가 정확히 일치하는가?','경쟁사에도 같은 변화가 나타나는가?'],
          'articlePlan':plan})
    return out

def build_industry():
    out=[]
    for cat in sorted({x.get('category') for x in items if x.get('category') in AUTO|IND}):
        arr=sorted([x for x in items if x.get('category')==cat and meaningful(x)],key=dt,reverse=True)
        for i,a in enumerate(arr[:80]):
            ca=(cs(a) or [None])[0]; na=nums(txt(a)); ta=themes(txt(a))
            if not ca or not na: continue
            for b in arr[i+1:80]:
                cb=(cs(b) or [None])[0]; nb=nums(txt(b)); tb=themes(txt(b))
                if not cb or not nb or ca==cb or a.get('sourceName')==b.get('sourceName') or ta==tb: continue
                if not (ta&tb) and len(ta|tb)<2: continue
                top=best_topic(txt(a)+' '+txt(b)) or cat; th=ta|tb
                headline=f'{top} 업계, {"·".join(sorted(th)[:2])} 동시 확대…공급능력이 관건'
                plan=[f'{ca}: {evidence_title(a)}',f'{cb}: {evidence_title(b)}','두 기업의 투자·생산·수주 숫자와 일정을 비교해 공통 변화 확인','공시·IR로 실제 공급능력·원가·수익성 변화와 경쟁사 흐름 확인']
                out.append({'type':'industry-issue','grade':'A','pitchScore':95,'headline':headline,'category':cat,'companies':[ca,cb],
                  'newFact':f'{a.get("sourceName")}와 {b.get("sourceName")}에서 서로 다른 기업의 사업 움직임과 구체적 수치가 확인됨.',
                  'angle':f'{ca}와 {cb}의 움직임을 연결해 {cat} 업계의 구조 변화가 실제로 진행되는지 확인',
                  'differentiator':'같은 기사 반복이 아니라 서로 다른 기업의 숫자와 움직임을 연결해 산업 단위의 새로운 취재 질문을 만듦.',
                  'whyNow':'최근 서로 다른 기업에서 같은 산업 방향을 가리키는 움직임이 동시에 포착됨.',
                  'numbers':list(dict.fromkeys(na+nb))[:8],'sourceCount':2,'globalSignals':0,'domesticSignals':2,'sources':[a.get('sourceName') or '-',b.get('sourceName') or '-'],
                  'evidence':[{'source':a.get('sourceName') or '-','title':evidence_title(a),'url':a.get('url'),'published':a.get('published'),'numbers':na[:4]},{'source':b.get('sourceName') or '-','title':evidence_title(b),'url':b.get('url'),'published':b.get('published'),'numbers':nb[:4]}],
                  'dartSignals':[],'dartNumericSignals':[],'dartNumericCount':0,
                  'questions':['두 기업의 움직임이 같은 산업 구조 변화인지 확인','공시·IR에서 투자·생산·수주 수치 대조','원가·가격·가동률에 실제 변화가 있는지 확인','다른 경쟁사도 같은 방향인지 비교'],
                  'articlePlan':plan})
                break
            if out and out[-1].get('category')==cat: break
    return out

candidates=build_dart()+build_industry()
candidates.sort(key=lambda p:(p.get('grade')=='A',p.get('pitchScore',0),p.get('dartNumericCount',0),len(p.get('numbers') or [])),reverse=True)
final=[]
for p in candidates:
    dup=False; pc=set(p.get('companies') or []); pn=set(p.get('numbers') or []); ph=clean_tokens(p.get('headline',''))
    for q in final:
        qc=set(q.get('companies') or []); qn=set(q.get('numbers') or []); qh=clean_tokens(q.get('headline',''))
        if pc and qc and ((pc==qc and (pn&qn or len(ph&qh)/max(1,len(ph|qh))>=.5)) or (pc&qc and len(ph&qh)/max(1,len(ph|qh))>=.6)):
            dup=True; break
    if not dup: final.append(p)
    if len(final)>=3: break
OUT.write_text(json.dumps(final,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
print(f'pitch rebuild: {len(final)} items / reporter-ready strategy-change + industry-issue / events excluded / max 3')
