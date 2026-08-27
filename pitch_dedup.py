from __future__ import annotations
import json,re
from pathlib import Path

PITCH=Path('pitch.json')
NUM=Path('dart_numeric.json')

pitches=json.loads(PITCH.read_text(encoding='utf-8')) if PITCH.exists() else []
numeric=json.loads(NUM.read_text(encoding='utf-8')).get('items',[]) if NUM.exists() else []

LAW_ARTICLE_RE=re.compile(r'^(?:\d{1,3})조$')
MONEY_WON_RE=re.compile(r'(?:양도금액|거래금액|투자금액|취득금액|처분금액)[^0-9]{0,30}(\d{1,3}(?:,\d{3})+|\d+)원')
STRATEGY_KW={'투자','시설투자','출자','유상증자','증설','생산','생산능력','공장','가동','감산','철수','매각','인수','합작','재편','구조조정','수주','계약','납품','공급','관세','통상','공급망','가격','원가','마진','LME','전력망','변압기','HVDC','해저케이블','해상풍력','풍력','태양광','ESS','석유화학','스페셜티','배터리소재','중국','미국','유럽','북미'}
INDUSTRY_CATS={'철강','비철금속','전력기기','전선·전력','에너지','재생에너지','화학·소재'}
AUTO_CATS={'완성차','부품','배터리','정책·관세','중국차','노조·생산','리콜·안전','수주·투자','단독','미국·글로벌'}
NOISE_WORDS={'주가','주식','증권','목표주가','급등','급락','추천','관련주','테마주','특징주'}

def fmt_won(raw:str)->str:
    n=int(raw.replace(',',''))
    if n>=10**12:
        v=n/10**12; return f'{v:.2f}'.rstrip('0').rstrip('.')+'조'
    if n>=10**8:
        v=n/10**8; return f'{v:.0f}억원' if abs(v-round(v))<1e-9 else f'{v:.2f}'.rstrip('0').rstrip('.')+'억원'
    if n>=10**4:
        v=n/10**4; return f'{v:.0f}만원' if abs(v-round(v))<1e-9 else f'{v:.2f}'.rstrip('0').rstrip('.')+'만원'
    return f'{n:,}원'

def sanitize_numbers(p):
    vals=[]
    for v in p.get('numbers') or []:
        s=str(v).strip()
        if LAW_ARTICLE_RE.fullmatch(s): continue
        vals.append(s)
    for r in p.get('dartNumericSignals') or []:
        for sn in r.get('snippets') or []:
            m=MONEY_WON_RE.search(str(sn.get('context') or ''))
            if m:
                money=fmt_won(m.group(1))
                if money not in vals: vals.insert(0,money)
                break
    p['numbers']=list(dict.fromkeys(vals))[:8]
    return p

def body(p): return ' '.join(str(p.get(k) or '') for k in ('headline','angle','newFact','differentiator','whyNow')).lower()

def valid(p):
    if p.get('type') not in {'dart-led','cross-source'}: return False
    if (p.get('pitchScore') or 0)<90 and p.get('grade')!='A': return False
    cat=p.get('category'); cats={cat}
    companies=[c for c in (p.get('companies') or []) if c]
    t=body(p)
    if any(w in t for w in NOISE_WORDS): return False
    if len(companies)<1: return False
    if not any(k.lower() in t for k in STRATEGY_KW): return False
    if not (p.get('numbers') or p.get('dartNumericSignals')): return False
    return bool(cats & (INDUSTRY_CATS|AUTO_CATS))

def fact_key(p):
    companies=tuple(sorted(p.get('companies') or []))
    dart_keys=tuple(sorted((r.get('receiptNo') or r.get('corpName') or '') for r in (p.get('dartNumericSignals') or [])))
    nums=tuple(sorted(str(x) for x in (p.get('numbers') or [])[:3]))
    themes=tuple(sorted(k for k in STRATEGY_KW if k.lower() in body(p)))
    return companies,dart_keys[:1],nums,themes[:2]

clean=[]
for p in pitches:
    p=sanitize_numbers(p)
    if valid(p): clean.append(p)
clean.sort(key=lambda x:(x.get('grade')=='A',x.get('pitchScore',0),x.get('dartNumericCount',0),x.get('sourceCount',0)),reverse=True)

final=[];seen=set()
for p in clean:
    k=fact_key(p)
    if k in seen: continue
    # Also suppress near-identical headlines within the same company.
    sig=' '.join(re.findall(r'[가-힣A-Za-z0-9]{2,}',str(p.get('headline') or '').lower()))
    dup=False
    for q in final:
        if set(p.get('companies') or []) & set(q.get('companies') or []):
            qs=' '.join(re.findall(r'[가-힣A-Za-z0-9]{2,}',str(q.get('headline') or '').lower()))
            a,b=set(sig.split()),set(qs.split())
            if len(a&b)/max(1,len(a|b))>=0.55: dup=True; break
    if dup: continue
    seen.add(k); final.append(p)
    if len(final)>=3: break

OUT.write_text(json.dumps(final,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
print(f'pitch dedup: {len(pitches)} -> {len(final)}; strategy/industry only; max 3')
