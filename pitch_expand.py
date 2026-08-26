from __future__ import annotations
import json,re
from pathlib import Path
from datetime import datetime, timezone, timedelta

DATA=Path('data.json'); OUT=Path('pitch.json')
items=json.loads(DATA.read_text(encoding='utf-8')) if DATA.exists() else []
pitches=json.loads(OUT.read_text(encoding='utf-8')) if OUT.exists() else []

EVENT_WORDS=[
    '인베스터데이','Investor Day','설명회','주주총회','간담회','세미나','포럼','컨퍼런스','엑스포',
    '발표회','발표 예정','공개 예정','공개한다','공개 계획','기조연설','부스 투어','데모데이','전시회',
    'IR','strategy day','capital markets day','summit','conference','expo','showcase','demo'
]
ACTION_WORDS=['공개','발표','추진','투자','수주','계약','증설','가동','양산','상용화','IPO','상장','감축','합병','재편','계획']
STOP={'관련','업계','시장','최근','오늘','올해','지난해','국내','글로벌','사업','기업','회사','계획','전망','대한','통해','위한','기자','보도'}

def title(x): return (x.get('koTitle') if x.get('global') and x.get('koTitle') else x.get('title','')).strip()
def text(x): return ' '.join(str(v or '') for v in (title(x),x.get('summary',''),x.get('koSummary','')))
def nums(s):
    return list(dict.fromkeys(re.findall(r'(?<!\d)(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?:조원|억원|만원|억|조|만대|천대|대|명|%|GWh|MWh|kWh|톤|km|MW|GW|일|시간)(?!\w)',s or '',re.I)))
def companies(x): return [c for c in (x.get('companies') or []) if c]
def sentences(s):
    s=re.sub(r'\s+',' ',s or '').strip()
    parts=[p.strip(' -•·') for p in re.split(r'(?<=[.!?。])\s+|\s+-\s+|\s+·\s+',s) if p.strip()]
    return parts

def event_candidate(x):
    t=text(x)
    if x.get('global') or x.get('industrySource') and x.get('score',0)<70: return False
    if x.get('score',0)<72: return False
    hits=sum(1 for w in EVENT_WORDS if w.lower() in t.lower())
    actions=sum(1 for w in ACTION_WORDS if w.lower() in t.lower())
    return hits>=1 and actions>=1

def build_plan(x):
    t=text(x); ts=t.lower(); c=companies(x); ns=nums(t); ss=sentences(x.get('summary',''))
    plan=[]
    if any(w.lower() in ts for w in ['인베스터데이','investor day','strategy day','capital markets day','ir']):
        plan.append('행사에서 제시하는 연간 실적 가이던스·핵심 목표와 기존 계획 대비 달라진 부분을 먼저 확인')
    elif any(w.lower() in ts for w in ['설명회','주주총회']):
        plan.append('설명회·주총에서 제시되는 합병·투자·재무 계획과 경영진의 구체적 숫자를 확인')
    elif any(w.lower() in ts for w in ['세미나','포럼','간담회','컨퍼런스','엑스포','conference','expo']):
        plan.append('행사에서 새로 공개되는 정책·기술·시장 전망과 실제 기업 투자·사업 계획의 연결고리를 확인')
    else:
        plan.append('발표·공개 일정에서 새롭게 확인되는 숫자·계획·일정을 취재')
    if any(w.lower() in ts for w in ['ipo','상장']):
        plan.append('IPO 추진 단계, 상장 주체·시점·지분구조와 기존 투자·가치평가 변화를 확인')
    elif any(w.lower() in ts for w in ['수주','계약']):
        plan.append('수주 규모·계약 기간·고객사·공급 대상과 실제 매출 반영 시점을 확인')
    elif any(w.lower() in ts for w in ['투자','증설','공장','가동','양산']):
        plan.append('투자액·생산능력·가동 시점·고용 효과 등 실행 계획을 수치로 확인')
    elif any(w.lower() in ts for w in ['합병','재편']):
        plan.append('합병·재편의 배경과 사업 시너지, 중복 조직·비용 절감, 향후 재무 부담을 확인')
    else:
        plan.append('발표 내용이 실제 제품·생산·수주·투자 등 사업 변화로 이어지는지 확인')
    if ns:
        plan.append('기사에 등장하는 '+', '.join(ns[:4])+' 등의 숫자가 기존 공시·계획과 어떻게 달라졌는지 대조')
    elif ss:
        plan.append('현재 기사에서 언급한 핵심 주장 2~3개를 회사·정부·업계 자료로 교차 확인')
    return plan[:3]

def make_candidate(x):
    c=companies(x); ns=nums(text(x)); ts=text(x); src=x.get('sourceName') or '-'
    original=title(x)
    # Turn generic headline into a reportable angle while preserving the underlying fact.
    if '인베스터데이' in ts or 'Investor Day' in ts:
        headline=original.replace('…','…')
    elif '설명회' in ts and c:
        headline=f"{c[0]} 설명회서 확인할 핵심…사업·재무 계획 어디까지 바뀌나"
    elif ('엑스포' in ts or '부스 투어' in ts) and c:
        headline=original
    else:
        headline=original
    plan=build_plan(x)
    evidence=[{'source':src,'title':original,'url':x.get('url'),'published':x.get('published'),'numbers':ns[:6]}]
    return {
        'type':'event-led','grade':'A' if (x.get('score',0)>=84 and len(plan)>=3) else 'B',
        'pitchScore':min(96,max(82,(x.get('score',0) or 72)+8)),
        'headline':headline,'category':x.get('category') or '산업','companies':c,
        'angle':plan[0],
        'newFact':f"{src}의 {original}에서 행사·발표와 관련된 구체적 사업 신호가 확인됨.",
        'differentiator':'이미 나온 기사 제목을 반복하는 대신, 행사에서 실제로 확인할 숫자·일정·사업 실행 여부를 기사 구조로 전환.',
        'whyNow':f"{src}가 포착한 일정·발표를 기준으로 후속 확인 포인트가 발생한 시점.",
        'numbers':ns[:8],'sourceCount':1,'globalSignals':1 if x.get('global') else 0,'domesticSignals':0 if x.get('global') else 1,
        'sources':[src],'evidence':evidence,
        'dartSignals':[],'dartNumericSignals':[],'dartNumericCount':0,
        'articlePlan':plan,
        'reportingBrief':[f"{src} · {original}"]+[s for s in sentences(x.get('summary',''))[:3]],
        'questions':[
            '행사·발표에서 실제로 새로 제시되는 숫자와 일정은 무엇인가?',
            '기존에 알려진 계획과 달라진 내용이 있는가?',
            '발표 내용이 실제 투자·생산·수주·제품 출시로 언제 이어지는가?',
            '경쟁사와 비교했을 때 이번 발표에서 차별화되는 포인트는 무엇인가?'
        ],
        'rawSignals':[original]+sentences(x.get('summary',''))[:3]
    }

# Keep only strong event-driven items and one item per obvious event cluster.
new=[]
for x in items:
    if event_candidate(x): new.append(make_candidate(x))

# Avoid flooding the pitch list with several articles about the same event.
merged=[]
def sig(p):
    raw=(p['headline']+' '+' '.join(p.get('companies') or [])).lower()
    toks=re.findall(r'[가-힣A-Za-z0-9]{2,}',raw)
    return set(t for t in toks if t not in STOP)
for p in sorted(new,key=lambda z:(z['grade']=='A',z['pitchScore']),reverse=True):
    ps=sig(p); dup=False
    for q in merged:
        qs=sig(q); sim=len(ps&qs)/max(1,len(ps|qs))
        if (set(p.get('companies',[])) & set(q.get('companies',[]))) and sim>=0.42:
            dup=True; break
    if not dup: merged.append(p)

# Existing DART/cross-source candidates stay, but event-led candidates compete on the same score.
allp=pitches+merged
allp.sort(key=lambda x:(x.get('grade')=='A',x.get('pitchScore',0),x.get('dartNumericCount',0),x.get('globalSignals',0)),reverse=True)
final=[];seen=set()
for p in allp:
    k=(p.get('type'),tuple(p.get('companies') or []),p.get('headline','')[:45])
    if k in seen: continue
    seen.add(k); final.append(p)
    if len(final)>=8: break

OUT.write_text(json.dumps(final,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
print(f'pitch expand: base={len(pitches)} event_added={len(merged)} final={len(final)} A={sum(1 for x in final if x.get("grade")=="A")}')
