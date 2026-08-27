from __future__ import annotations
import json,re
from pathlib import Path

PITCH=Path('pitch.json')
OUT=PITCH
pitches=json.loads(PITCH.read_text(encoding='utf-8')) if PITCH.exists() else []

NOISE_WORDS={'주가','주식','증권','목표주가','급등','급락','추천','관련주','테마주','특징주'}
BAD_HEAD=('기존 계획과 달라졌나','공시에 새 숫자','공시에 새','사업전략 얼마나','전략 변화 본격화하나','변화 짚어볼 만','실제 전략은','사업 신호 겹쳤다')
GENERIC={'최근 30일','대조해 실제 변화인지 확인','기존 공개 계획보다 얼마나','실제 생산능력·수주·원가 변화와 연결되는가','경쟁사도 같은 방향으로 움직이는가'}
ALLOWED={'strategy-change','industry-issue'}


def body(p):
    return ' '.join(str(p.get(k) or '') for k in ('headline','angle','newFact','differentiator','whyNow','whatToWrite')).lower()

def concrete(p):
    nums=[str(x) for x in (p.get('numbers') or [])]
    ev=' '.join(str(x) for x in (p.get('evidence') or []))
    return bool(nums) and bool(re.search(r'(조원|억원|만원|달러|%|만대|톤|MW|GW|GWh)',nums[0]+' '+ev))

def valid(p):
    if p.get('type') not in ALLOWED: return False
    if p.get('pitchScore',0) < 90: return False
    if not p.get('companies') or not p.get('numbers'): return False
    if any(w in body(p) for w in NOISE_WORDS): return False
    if len(p.get('evidence') or []) < 2 or len(p.get('questions') or []) < 3 or len(p.get('articlePlan') or []) < 3: return False
    if any(b in str(p.get('headline') or '') for b in BAD_HEAD): return False
    if not concrete(p): return False
    blob=body(p)
    # A real reporter pitch must contain a fact, a change, and a point of comparison.
    fact_terms=('투자','출자','수주','계약','생산','증설','가격','원가','매각','철수','합병','상용화')
    if not any(k in blob for k in fact_terms): return False
    if not p.get('newFact') or not p.get('differentiator'): return False
    return True

def tokens(s):
    return set(re.findall(r'[가-힣A-Za-z0-9]{2,}',str(s or '').lower()))

def sig(p):
    c=tuple(sorted(p.get('companies') or [])); n=tuple(sorted(str(x) for x in (p.get('numbers') or [])[:8])); h=tokens(p.get('headline'))
    return c,n,h

def rewrite(p):
    p=dict(p)
    # Turn generic 'angle' into the sentence the reporter is actually proposing to write.
    h=str(p.get('headline') or '').strip()
    c=(p.get('companies') or [''])[0]
    blob=body(p)
    n=str((p.get('numbers') or [''])[0])
    if '수주' in blob and '투자' in blob and ('생산' in blob or '증설' in blob):
        p['headline']=f'{c}, 수주 늘자 투자 확대…생산능력 확충이 관건'
    elif '가격' in blob or '원가' in blob:
        if '투자' in blob: p['headline']=f'{c}, 원가 부담 속 투자 확대…수익성 방어가 관건'
    elif '사업재편' in blob or '철수' in blob or '매각' in blob:
        p['headline']=f'{c}, 사업재편 본격화…줄이는 사업·키우는 사업은'
    elif '생산' in blob and ('투자' in blob or '증설' in blob):
        p['headline']=f'{c}, 생산능력 키운다…증설이 수익성으로 이어질까'
    p['reporterSummary']=p.get('newFact') or p.get('differentiator') or p.get('angle') or ''
    return p

clean=[]
for p in pitches:
    if valid(p): clean.append(rewrite(p))
clean.sort(key=lambda x:(x.get('grade')=='A',x.get('pitchScore',0),len(x.get('evidence') or []),len(x.get('numbers') or [])), reverse=True)

final=[]
for p in clean:
    c,n,h=sig(p); dup=False
    for q in final:
        qc,qn,qh=sig(q)
        if c and qc and set(c)&set(qc):
            if n and qn and set(n)&set(qn): dup=True; break
            if len(h&qh)/max(1,len(h|qh)) >= 0.45: dup=True; break
    if not dup:
        final.append(p)
    if len(final)>=3: break

OUT.write_text(json.dumps(final,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
print(f'pitch quality dedup: {len(pitches)} -> {len(final)}; hard reporter-quality gate; max 3')
