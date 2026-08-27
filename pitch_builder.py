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
def relevant_category(x): return (not x.get('global')) and x.get('category') in AUTO|IND and bool(cs(x))
def meaningful(x):
    if not relevant_category(x): return False
    t=txt(x)
    return not any(n in t for n in NOISE) and bool(nums(t)) and bool(themes(t))
def topic(s):
    low=s.lower()
    for keys,label in [
        (('수소환원','hyrex','수소환원제철'),'수소환원제철'),
        (('전기차','ev','배터리'),'전기차·배터리'),
        (('로보택시','자율주행'),'자율주행'),
        (('해저케이블','hvdc','전력망','변압기'),'전력망·전력기기'),
        (('풍력','해상풍력'),'풍력'),
        (('석유화학','스페셜티'),'석유화학'),
        (('철강','고로','제철'),'철강'),
        (('구리','아연','니켈','제련'),'비철금속')]:
        if any(k in low for k in keys): return label
    return None

def build_dart():
    out=[]
    for r in numeric:
        corp=r.get('corpName',''); report=str(r.get('reportName') or '')
        vals=money_from_numeric(r)
        if not corp or not vals: continue
        if not any(k in report for k in ('시설투자','출자','유상증자','타법인','지분','생산중단','영업양수도','합병','분할','주요사항','사업보고서','반기보고서','분기보고서')): continue
        news=recent(corp,45)
        mentioned=set(n for x in news for n in nums(txt(x)))
        fresh=[v for v in vals if v not in mentioned]
        related=[x for x in news if themes(txt(x)) and not any(n in txt(x) for n in NOISE)]
        if not fresh or not related: continue
        top=topic(' '.join(txt(x) for x in related[:10])) or related[0].get('category') or '사업'
        primary=fresh[0]
        if any(k in report for k in ('시설투자','생산')):
            headline=f'{primary} 투입한 {top}…{corp}, 돈 쓴 만큼 수익성 나올까'
            angle=f'{corp}의 {primary} 투자가 어느 생산거점·제품으로 연결되는지, 기존 계획보다 투자 강도가 달라졌는지 확인'
            plan=['신규 투자 규모 제시','기존 생산능력·투자계획과 비교','원가·가동률·수주 등 실제 수익성 연결고리 확인','경쟁사 투자와 비교']
        elif any(k in report for k in ('타법인','지분','출자')):
            headline=f'{corp}, {primary} 자금 투입…이번 돈은 어디로 흘러가나'
            angle=f'공시상 {primary} 자금의 실제 사용처와 기존 사업전략·자회사 구조 변화 여부 확인'
            plan=['자금 투입 내역 제시','과거 투자·지분 구조와 비교','실제 사업·생산·매출 영향 확인','향후 추가 투자 필요성 점검']
        elif any(k in report for k in ('합병','분할','영업양수도')):
            headline=f'{corp}, 사업재편 뒤 숫자가 달라졌다…생산·투자 지도 어디로'
            angle='재편 전후 자산·생산·인력·투자 구조를 비교해 사업전략 변화의 실체 확인'
            plan=['재편 전후 숫자 비교','사업부·자회사 구조 확인','생산·투자 영향 확인','산업 경쟁구도 변화 제시']
        else:
            headline=f'{corp}, 공시에서 드러난 {primary} 변화…기존 계획과 달라졌나'
            angle='최근 공시의 숫자와 기존 계획·실적을 대조해 기사화되지 않은 변화 확인'
            plan=['새 숫자 제시','기존 계획과 비교','실제 사업 영향 확인','추가 취재 포인트 제시']
        evidence=[{'source':'DART','title':report,'url':r.get('url'),'published':r.get('date'),'numbers':fresh[:6]}]
        for n in related[:3]: evidence.append({'source':n.get('sourceName') or '-','title':n.get('title') or '','url':n.get('url'),'published':n.get('published'),'numbers':nums(txt(n))[:4]})
        out.append({'type':'strategy-change','grade':'A','pitchScore':98,'headline':headline,'category':related[0].get('category') or '산업','companies':[corp],
          'newFact':f'DART {report}에서 {", ".join(fresh[:4])}의 신규 수치가 확인됐고 최근 기사에서는 같은 수치가 확인되지 않음.',
          'angle':angle,'differentiator':'공시 원문 숫자와 최근 기사·기존 계획을 교차해 아직 기사화되지 않은 사업 변화를 찾음.','whyNow':'최근 공시 숫자와 기존 보도를 비교할 수 있는 시점.',
          'numbers':fresh[:6],'sourceCount':1+source_count(related[:3]),'globalSignals':0,'domesticSignals':len(related[:3]),'sources':['DART']+list(dict.fromkeys([n.get('sourceName') for n in related[:3] if n.get('sourceName')])),
          'evidence':evidence,'dartSignals':[d for d in dart if d.get('corpName')==corp][:4],'dartNumericSignals':[r],'dartNumericCount':len(fresh),
          'questions':['이 숫자가 기존 공개 계획보다 얼마나 달라졌는가?','실제 투자·생산·수주·원가에 어떤 변화가 나타났는가?','회사 설명과 DART 원문 수치가 정확히 일치하는가?','경쟁사에도 같은 변화가 나타나는가?'],'articlePlan':plan})
    return out

def build_industry():
    out=[]
    for cat in sorted({x.get('category') for x in items if x.get('category') in AUTO|IND}):
        arr=sorted([x for x in items if x.get('category')==cat and meaningful(x) and not event_only(txt(x))],key=dt,reverse=True)
        for i,a in enumerate(arr[:60]):
            ca=(cs(a) or [None])[0]; na=nums(txt(a)); ta=themes(txt(a))
            if not ca or not na: continue
            for b in arr[i+1:60]:
                cb=(cs(b) or [None])[0]; nb=nums(txt(b)); tb=themes(txt(b))
                if not cb or ca==cb or a.get('sourceName')==b.get('sourceName') or not nb or ta==tb: continue
                headline=f'{topic(txt(a)+" "+txt(b)) or cat} 업계, {"·".join(sorted(ta|tb)[:2])} 동시에 움직인다…기업 전략 바뀌나'
                out.append({'type':'industry-issue','grade':'A','pitchScore':95,'headline':headline,'category':cat,'companies':[ca,cb],
                  'newFact':f'{a.get("sourceName")}와 {b.get("sourceName")}에서 서로 다른 사업 신호와 구체적 수치가 확인됨.','angle':f'{ca}와 {cb}의 움직임을 연결해 {cat} 업계의 투자·생산·수주 구조 변화가 실제로 나타나는지 확인',
                  'differentiator':'동일 기사 반복이 아니라 서로 다른 기업의 숫자와 움직임을 연결해 산업 단위의 새로운 질문을 만듦.','whyNow':'최근 보도에서 서로 다른 기업의 사업 신호가 동시에 포착됨.',
                  'numbers':list(dict.fromkeys(na+nb))[:8],'sourceCount':2,'globalSignals':0,'domesticSignals':2,'sources':[a.get('sourceName') or '-',b.get('sourceName') or '-'],
                  'evidence':[{'source':a.get('sourceName') or '-','title':a.get('title') or '','url':a.get('url'),'published':a.get('published'),'numbers':na[:4]},{'source':b.get('sourceName') or '-','title':b.get('title') or '','url':b.get('url'),'published':b.get('published'),'numbers':nb[:4]}],
                  'dartSignals':[],'dartNumericSignals':[],'dartNumericCount':0,'questions':['두 기업의 움직임이 같은 산업 구조 변화인지 확인','공시·IR에서 관련 수치 대조','생산·투자·수주 전략이 실제로 바뀌었는지 확인','경쟁사까지 같은 방향인지 비교'],
                  'articlePlan':['두 기업의 서로 다른 움직임 제시','숫자와 일정 비교','공시·IR로 실제 변화 검증','업계 전체 파장과 경쟁사 비교']})
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
        if pc and qc and ((pc==qc and (pn&qn or len(ph&qh)/max(1,len(ph|qh))>=.5)) or (pc&qc and len(ph&qh)/max(1,len(ph|qh))>=.65)):
            dup=True; break
    if not dup: final.append(p)
    if len(final)>=3: break
OUT.write_text(json.dumps(final,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
print(f'pitch rebuild: {len(final)} items / reporter-ready strategy-change + industry-issue / events excluded / max 3')
