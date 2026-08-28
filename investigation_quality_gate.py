from __future__ import annotations
import json,re
from pathlib import Path

IN=Path('dig_today.json')
data=json.loads(IN.read_text(encoding='utf-8')) if IN.exists() else {'generatedAt':None,'items':[]}
items=data.get('items',[])

BAD_TITLE_PATTERNS=('공시에 새','공시에 새 숫자','사업전략 얼마나 달라졌나','전략 변화 본격화하나','짚어볼 만','실제 전략은','사업 신호 겹쳤다')
GENERIC_LINES=('최근 30일','관련 보도가 동시에 확인됨','구체적 수치 확인','실제 변화인지 확인','경쟁사와 투자·생산·수주 속도를 비교')
EVENT_WORDS=('인베스터데이','주주총회','설명회','세미나','포럼','엑스포','컨퍼런스','부스투어','기조연설','발표회')
ISSUE_WORDS=('관건','시험대','따라가나','바뀌나','달라지나','커지나','줄이는','키우는','전략','원가','수익성','생산능력','공급망','상용화','현지 생산','증설','감산')
NUM_RE=re.compile(r'(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?:조원|억원|만원|만대|천대|대|명|%|GWh|MWh|MW|GW|톤|km)')


def compact(s): return re.sub(r'\s+',' ',str(s or '')).strip()
def norm(s): return compact(s).lower()

def concrete_numbers(it):
    ns=[]
    for x in (it.get('numbers') or []):
        sx=str(x)
        if NUM_RE.search(sx): ns.append(sx)
    for line in (it.get('lines') or []): ns.extend(NUM_RE.findall(line))
    return list(dict.fromkeys(ns))

def evidence_ok(it):
    lines=[compact(x) for x in (it.get('lines') or []) if compact(x)]
    specific=[x for x in lines if len(x)>=28 and not any(g in x for g in GENERIC_LINES)]
    sources=list(dict.fromkeys(str(x) for x in (it.get('sources') or []) if x))
    return len(specific)>=2 and len(sources)>=2

def claim_supported(it):
    h=norm(it.get('headline'))
    blob=norm(' '.join(it.get('lines') or [])+' '+' '.join(it.get('questions') or []))
    if '수주 늘자' in h or '수주 증가와 투자' in h:
        return ('수주' in blob or '계약' in blob) and any(k in blob for k in ('투자','출자','증설','capex'))
    if '생산능력 확충' in h or '증설' in h:
        return any(k in blob for k in ('생산능력','증설','라인','공장','가동'))
    if '원가' in h or '수익성' in h:
        return any(k in blob for k in ('원가','가격','원료','전력','관세','마진'))
    if '사업재편' in h or '줄이는 사업' in h or '키우는 사업' in h:
        return any(k in blob for k in ('재편','철수','매각','구조조정','합병','분할','거점축소'))
    return any(w in h for w in ISSUE_WORDS) and any(w in blob for w in ISSUE_WORDS)

def rewrite_headline(it):
    h=compact(it.get('headline')); c=compact(it.get('company')); blob=norm(' '.join(it.get('lines') or [])); nums=concrete_numbers(it); n=nums[0] if nums else ''
    if '수주 늘자' in h and not (('수주' in blob or '계약' in blob) and any(k in blob for k in ('투자','증설','출자','capex'))):
        return f'{c}, {n} 투자 확대…무엇을 늘리나' if n else f'{c}, 투자 확대…생산·사업에 어떻게 쓰나'
    if any(p in h for p in BAD_TITLE_PATTERNS):
        if ('수주' in blob or '계약' in blob) and any(k in blob for k in ('투자','증설','출자','capex')):
            return f'{c}, 수주 늘자 {n+" 투자" if n else "투자"} 확대…생산능력 확충이 관건'
        if any(k in blob for k in ('원가','가격','원료','전력','관세')) and any(k in blob for k in ('투자','증설')):
            return f'{c}, 원가 부담 속 투자 확대…수익성 방어가 관건'
        if any(k in blob for k in ('재편','철수','매각','구조조정','합병','분할')):
            return f'{c}, 사업재편 본격화…줄이는 사업·키우는 사업은'
        if any(k in blob for k in ('생산능력','증설','라인','공장','가동')):
            return f'{c}, 생산능력 키운다…증설이 수익성으로 이어질까'
        if n: return f'{c}, {n} 투자 확대…실제 사업 변화는'
        return f'{c}, 사업 변화 포착…무엇이 달라졌나'
    return h

kept=[]
for raw in items:
    it=dict(raw)
    it['headline']=rewrite_headline(it)
    if any(e in (it['headline']+' '+' '.join(it.get('lines') or [])) for e in EVENT_WORDS): continue
    if not evidence_ok(it): continue
    if not concrete_numbers(it): continue
    if not claim_supported(it): continue
    h=norm(it['headline'])
    # Generic rewrites are allowed only with >=3 distinct sources.
    if h.endswith('실제 사업 변화는') or h.endswith('무엇이 달라졌나'):
        if len(set(it.get('sources') or []))<3: continue
    it['qualityGate']='pass'
    it['qualityReason']='숫자·복수 근거·기사 쟁점이 확인되고 제목의 주장도 근거로 뒷받침됨'
    kept.append(it)

# One company, one story in the investigation top list.
final=[]; seen_company=set()
for it in sorted(kept,key=lambda x:(x.get('score',0),len(concrete_numbers(x)),len(set(x.get('sources') or []))),reverse=True):
    c=compact(it.get('company'))
    if c and c in seen_company: continue
    if c: seen_company.add(c)
    final.append(it)
    if len(final)>=5: break

data['items']=final
data['qualityGate']={'input':len(items),'output':len(final),'rule':'구체적 숫자+복수 근거+쟁점형 제목+제목 주장과 근거의 일치성 요구'}
IN.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
print(f'investigation quality gate: {len(items)} -> {len(final)}')
