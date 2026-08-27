from __future__ import annotations
import json, re
from pathlib import Path

PITCH=Path('pitch.json')
DIG=Path('dig_today.json')
OUT=Path('quality_report.json')

BAD_TITLE = (
    '공시에 새', '사업전략 얼마나', '사업 신호 겹쳤다', '변화 짚어볼 만',
    '실제 전략은', '전략 변화 본격화하나', '사업전략은'
)
GENERIC = (
    '최근 30일', '대조해 실제 변화인지 확인', '기존 공개 계획보다 얼마나',
    '실제 생산능력·수주·원가 변화와 연결되는가', '경쟁사도 같은 방향으로 움직이는가'
)
EVENT_WORDS = ('인베스터데이','주주총회','설명회','세미나','포럼','엑스포','컨퍼런스','부스투어','기조연설','발표회')
MONEY_RE = re.compile(r'\b(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?:조원|억원|만원|억달러|달러|USD|EUR)\b')


def load(path, default):
    try: return json.loads(path.read_text(encoding='utf-8'))
    except Exception: return default


def norm(s):
    return re.sub(r'\s+', ' ', str(s or '')).strip().lower()


def company_mentions(c, s):
    t=norm(s); return bool(c and norm(c) in t)


def evaluate(x):
    headline=str(x.get('headline') or '').strip()
    lines=[str(v) for v in (x.get('lines') or []) if v]
    questions=[str(v) for v in (x.get('questions') or []) if v]
    sources=[str(v) for v in (x.get('sources') or []) if v]
    company=str(x.get('company') or '').strip()
    numbers=[str(v) for v in (x.get('numbers') or []) if v]
    reasons=[]; score=0
    if headline and not any(b in headline for b in BAD_TITLE): score+=25
    else: reasons.append('기계적/범용 제목')
    if len(lines)>=4: score+=15
    else: reasons.append('기사 구성 부족')
    concrete=sum(bool(MONEY_RE.search(v)) for v in lines)
    if concrete>=1 or numbers: score+=15
    else: reasons.append('구체적 숫자 부족')
    if len(set(sources))>=2: score+=10
    else: reasons.append('복수 근거 부족')
    blob=' '.join(lines)
    if company and any(k in blob for k in ('수주','투자','생산','원가','사업','공장','증설','가격','수익성','상용화')): score+=15
    else: reasons.append('기업 변화와 기사 쟁점 연결 약함')
    if any(q.endswith('?') or '?' in q for q in questions) and len(questions)>=2: score+=10
    else: reasons.append('취재 질문 부족')
    if any(e in (headline+' '+blob) for e in EVENT_WORDS): reasons.append('행사성 소재')
    if sum(1 for g in GENERIC if g in norm(blob))>=2: score-=10; reasons.append('범용 문구 과다')
    if len(set(lines))<len(lines): score-=10; reasons.append('기사 구성 중복')
    return max(0, min(100, score)), reasons


def rewrite_headline(x):
    h=str(x.get('headline') or '')
    c=str(x.get('company') or '')
    sig=' '.join(x.get('lines') or [])
    if any(b in h for b in BAD_TITLE):
        if '수주' in sig and '투자' in sig:
            return f'{c}, 수주 늘자 투자 확대…생산능력 확충이 관건'
        if '원가' in sig or '가격' in sig:
            return f'{c}, 원가 부담 속 투자 확대…수익성 방어 시험대'
        if '사업재편' in sig or '철수' in sig or '매각' in sig:
            return f'{c}, 사업재편 본격화…줄이는 사업·키우는 사업은'
        if '생산' in sig or '증설' in sig:
            return f'{c}, 생산능력 키운다…증설이 수익성으로 이어질까'
        return h.replace('사업전략 얼마나 달라졌나','실제 사업 변화는').replace('…사업전략은','…실제 사업 변화는')
    return h


def clean_digest(x):
    y=dict(x)
    y['headline']=rewrite_headline(y)
    y['qualityScore'], reasons=evaluate(y)
    y['qualityReason']='통과' if not reasons else ' / '.join(reasons[:3])
    # Global linkage must be specific enough to keep; otherwise remove it.
    gl=[]
    c=str(y.get('company') or '')
    for g in y.get('global') or []:
        t=norm((g.get('title') or '')+' '+(g.get('summary') or '')+' '+(g.get('koTitle') or '')+' '+(g.get('koSummary') or ''))
        if any(k in t for k in ('tariff','transformer','grid','hvdc','cable','steel','battery','ev','automotive','wind','renewable','data center','supplier')) or company_mentions(c,t):
            gl.append(g)
    y['global']=gl[:2]
    # Never claim "uncovered" solely from absence of exact number if evidence is weak.
    if y.get('kind')=='공시 미보도 숫자' and len(y.get('sources') or [])<2:
        y['qualityScore']=min(y['qualityScore'],49); y['qualityReason']='복수 근거 부족'
    y['qualityGate']='pass' if y['qualityScore']>=70 else 'hold'
    return y

pitches=load(PITCH,[])
dig=load(DIG,{'items':[]})
if isinstance(pitches,list):
    kept=[]
    seen=set()
    for p in pitches:
        q=clean_digest(p)
        if q['qualityScore']<70: continue
        key=norm(re.sub(r'[^가-힣a-z0-9 ]',' ',q.get('headline','')))
        if key in seen: continue
        seen.add(key); kept.append(q)
    kept=sorted(kept,key=lambda z:z.get('qualityScore',0),reverse=True)[:3]
    PITCH.write_text(json.dumps(kept,ensure_ascii=False,indent=2),encoding='utf-8')
else:
    kept=[]

if isinstance(dig,dict):
    ds=[]
    for x in dig.get('items') or []:
        q=clean_digest(x)
        if q['qualityScore']<72: continue
        ds.append(q)
    # Strong de-duplication by company + core headline words.
    uniq=[]; seen=set()
    for q in sorted(ds,key=lambda z:z.get('qualityScore',0),reverse=True):
        key=(q.get('company'), re.sub(r'[^가-힣a-z0-9]','',q.get('headline',''))[:45])
        if key in seen: continue
        seen.add(key); uniq.append(q)
    dig['items']=uniq[:5]
    DIG.write_text(json.dumps(dig,ensure_ascii=False,indent=2),encoding='utf-8')
else:
    dig={'items':[]}

report={
  'pitches': len(kept),
  'investigations': len(dig.get('items') or []),
  'pitchThreshold':70,
  'investigationThreshold':72,
  'headlineRule':'쟁점형 제목 우선, 범용 템플릿 보류',
  'generatedBy':'pitch_quality_gate.py'
}
OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(f'quality gate: {len(kept)} pitches / {len(dig.get("items") or [])} investigations retained')
