from __future__ import annotations
import json,re
from pathlib import Path

PITCH=Path('pitch.json')
NUM=Path('dart_numeric.json')

pitches=json.loads(PITCH.read_text(encoding='utf-8')) if PITCH.exists() else []
numeric=json.loads(NUM.read_text(encoding='utf-8')).get('items',[]) if NUM.exists() else []

LAW_ARTICLE_RE=re.compile(r'^(?:\d{1,3})조$')
MONEY_WON_RE=re.compile(r'(?:양도금액|거래금액|투자금액|취득금액|처분금액)[^0-9]{0,30}(\d{1,3}(?:,\d{3})+|\d+)원')


def fmt_won(raw: str) -> str:
    n=int(raw.replace(',',''))
    if n >= 10**12:
        v=n/10**12
        return f'{v:.2f}'.rstrip('0').rstrip('.')+'조'
    if n >= 10**8:
        v=n/10**8
        return f'{v:.0f}억원' if abs(v-round(v))<1e-9 else f'{v:.2f}'.rstrip('0').rstrip('.')+'억원'
    if n >= 10**4:
        v=n/10**4
        return f'{v:.0f}만원' if abs(v-round(v))<1e-9 else f'{v:.2f}'.rstrip('0').rstrip('.')+'만원'
    return f'{n:,}원'


def sanitize_numbers(p):
    vals=[]
    for v in p.get('numbers') or []:
        s=str(v).strip()
        if LAW_ARTICLE_RE.fullmatch(s):
            continue
        vals.append(s)
    # For DART-led pitches, replace legal-article false positives with the actual money amount.
    for r in p.get('dartNumericSignals') or []:
        for sn in r.get('snippets') or []:
            ctx=str(sn.get('context') or '')
            m=MONEY_WON_RE.search(ctx)
            if m:
                money=fmt_won(m.group(1))
                if money not in vals:
                    vals.insert(0,money)
                break
    p['numbers']=list(dict.fromkeys(vals))[:8]
    # Keep evidence numbers consistent.
    for e in p.get('evidence') or []:
        e['numbers']=[x for x in (e.get('numbers') or []) if not LAW_ARTICLE_RE.fullmatch(str(x))]
    return p


def key(p):
    companies=tuple(sorted(p.get('companies') or []))
    dtype=p.get('type','')
    dart_keys=tuple(sorted((r.get('receiptNo') or r.get('corpName') or '') for r in (p.get('dartNumericSignals') or [])))
    headline=re.sub(r'\s+',' ',str(p.get('headline') or '')).strip()
    # Same company + same DART disclosure + same headline is one pitch.
    if dart_keys:
        return (dtype,companies,dart_keys[0],headline[:70])
    return (dtype,companies,headline[:70])

clean=[]
seen=set()
for p in pitches:
    p=sanitize_numbers(p)
    k=key(p)
    if k in seen:
        continue
    seen.add(k)
    clean.append(p)

# Collapse same underlying fact even when the generated headline differs slightly.
collapsed=[]
seen_fact=set()
for p in sorted(clean,key=lambda x:(x.get('grade')=='A',x.get('pitchScore',0),x.get('sourceCount',0)),reverse=True):
    companies=tuple(sorted(p.get('companies') or []))
    dart_keys=tuple(sorted((r.get('receiptNo') or '') for r in (p.get('dartNumericSignals') or [])))
    nums=tuple(sorted(p.get('numbers') or []))
    fact=(companies,dart_keys,nums)
    if dart_keys and fact in seen_fact:
        continue
    seen_fact.add(fact)
    collapsed.append(p)

PITCH.write_text(json.dumps(collapsed[:6],ensure_ascii=False,separators=(',',':')),encoding='utf-8')
print(f'pitch dedup: {len(pitches)} -> {len(collapsed[:6])}; removed {max(0,len(pitches)-len(collapsed[:6]))} duplicates')
