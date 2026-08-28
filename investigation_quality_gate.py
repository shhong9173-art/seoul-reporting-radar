from __future__ import annotations
import json,re
from pathlib import Path

IN=Path('dig_today.json')
data=json.loads(IN.read_text(encoding='utf-8')) if IN.exists() else {'generatedAt':None,'items':[]}
items=data.get('items',[])

EVENT_WORDS=('인베스터데이','주주총회','설명회','세미나','포럼','엑스포','컨퍼런스','부스투어','기조연설','발표회')
BAD_TITLE_PATTERNS=('공시에 새','사업전략 얼마나 달라졌나','전략 변화 본격화하나','짚어볼 만','실제 전략은','사업 신호 겹쳤다')
GENERIC_LINES=('최근 30일','관련 보도가 동시에 확인됨','구체적 수치 확인','실제 변화인지 확인','경쟁사와 투자·생산·수주 속도를 비교','공시 숫자를 기존')
ISSUE_WORDS=('관건','시험대','따라가나','바뀌나','달라지나','커지나','줄이는','키우는','전략','원가','수익성','생산능력','공급망','상용화','현지 생산','증설','감산')
NUM_RE=re.compile(r'(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?:조원|억원|만원|억달러|달러|USD|EUR|만대|천대|대|명|%|GWh|MWh|MW|GW|톤|km)')

CAUSAL_CLAIMS={
    '수주 늘자 투자 확대':(('수주','계약'),('투자','출자','증설','CAPEX')),
    '수주 늘자':(('수주','계약'),('투자','출자','증설','CAPEX')),
    '투자 확대':(('투자','출자','증설','CAPEX')),
    '생산능력 확충':(('생산능력','증설','라인','공장','가동')),
    '원가 부담':(('원가','가격','원료','전력','관세')),
    '사업재편':(('사업재편','철수','매각','구조조정','합병','분할','거점축소')),
}

def compact(s): return re.sub(r'\s+',' ',str(s or '')).strip()
def norm(s): return compact(s).lower()
def nums(it):
    out=[str(x) for x in (it.get('numbers') or []) if NUM_RE.search(str(x))]
    for line in it.get('lines') or []: out.extend(NUM_RE.findall(str(line)))
    return list(dict.fromkeys(out))

def lines(it): return [compact(x) for x in (it.get('lines') or []) if compact(x)]
def sources(it): return list(dict.fromkeys(str(x) for x in (it.get('sources') or []) if x))
def blob(it): return norm(' '.join(lines(it)))

def phrase_supported(headline, evidence):
    h=norm(headline); b=norm(evidence)
    if '수주 늘자' in h or '수주 증가' in h or '수주 확대' in h:
        return any(k in b for k in ('수주','계약')) and any(k in b for k in ('투자','출자','증설','capex'))
    if '원가' in h:
        return any(k in b for k in ('원가','가격','원료','전력','관세'))
    if '생산능력' in h or '증설' in h:
        return any(k in b for k in ('생산능력','증설','라인','공장','가동'))
    if '사업재편' in h or '철수' in h or '매각' in h:
        return any(k in b for k in ('재편','철수','매각','구조조정','합병','분할','거점축소'))
    return any(w in h for w in ISSUE_WORDS)

def title_upgrade(it):
    h=compact(it.get('headline')); c=compact(it.get('company')); b=blob(it); ns=nums(it); n=ns[0] if ns else ''
    # Causal headline is allowed only when the evidence supports both sides.
    if ('수주 늘자' in norm(h) or '수주 증가' in norm(h)) and not (('수주' in b or '계약' in b) and any(k in b for k in ('투자','출자','증설','capex'))):
        return f'{c}, {n} 투자…어디에 얼마나 쓰나' if n else f'{c}, 투자 확대…어디에 얼마나 쓰나'
    if any(p in h for p in BAD_TITLE_PATTERNS):
        if ('수주' in b or '계약' in b) and any(k in b for k in ('투자','증설','출자','capex')):
            return f'{c}, 수주 늘자 {n} 투자…생산능력 확충이 관건' if n else f'{c}, 수주 늘자 투자 확대…생산능력 확충이 관건'
        if any(k in b for k in ('원가','가격','원료','전력','관세')) and any(k in b for k in ('투자','증설')):
            return f'{c}, 원가 부담 속 투자 확대…수익성 방어가 관건'
        if any(k in b for k in ('재편','철수','매각','구조조정','합병','분할','거점축소')):
            return f'{c}, 사업재편 본격화…줄이는 사업·키우는 사업은'
        if any(k in b for k in ('생산능력','증설','라인','공장','가동')):
            return f'{c}, 생산능력 키운다…증설이 수익성으로 이어질까'
        if n: return f'{c}, {n} 투자 확대…실제 사업 변화는'
        return f'{c}, 사업 변화 포착…무엇이 달라졌나'
    return h

def evidence_ok(it):
    ls=lines(it); src=sources(it); ns=nums(it)
    specific=sum(1 for x in ls if len(x)>=28 and not any(g in x for g in GENERIC_LINES))
    return len(src)>=2 and specific>=2 and bool(ns)

def dedup_key(it):
    return (compact(it.get('company')), re.sub(r'[^가-힣a-z0-9]','',compact(it.get('headline')))[:55])

kept=[]
for raw in items:
    it=dict(raw)
    if any(e in (compact(it.get('headline'))+' '+' '.join(lines(it))) for e in EVENT_WORDS):
        continue
    it['headline']=title_upgrade(it)
    if not evidence_ok(it):
        continue
    if not phrase_supported(it['headline'], blob(it)):
        continue
    # A causal claim must be supported by both components in the evidence.
    h=norm(it['headline']); b=blob(it)
    if '수주 늘자' in h or '수주 증가' in h:
        if not (('수주' in b or '계약' in b) and any(k in b for k in ('투자','출자','증설','capex'))):
            continue
    it['qualityGate']='pass'
    it['qualityReason']='숫자·복수 근거·사업 변화·제목의 주장까지 모두 근거로 확인된 후보'
    kept.append(it)

final=[]; seen=set()
for it in sorted(kept,key=lambda x:(x.get('score',0),len(nums(x)),len(sources(x))),reverse=True):
    k=dedup_key(it)
    if k in seen: continue
    company=compact(it.get('company'))
    if company and any(company==compact(x.get('company')) for x in final):
        continue
    seen.add(k); final.append(it)
    if len(final)>=5: break

data['items']=final
data['qualityGate']={
    'input':len(items),
    'output':len(final),
    'rule':'구체적 숫자+복수 근거+사업 변화+제목 주장과 근거의 일치성+인과관계 검증'
}
IN.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
print(f'investigation quality gate: {len(items)} -> {len(final)}')
