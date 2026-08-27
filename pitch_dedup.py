from __future__ import annotations
import json,re
from pathlib import Path

PITCH=Path('pitch.json')
OUT=Path('pitch.json')
pitches=json.loads(PITCH.read_text(encoding='utf-8')) if PITCH.exists() else []

NOISE_WORDS={'주가','주식','증권','목표주가','급등','급락','추천','관련주','테마주','특징주'}
ALLOWED={'strategy-change','industry-issue','dart-led','cross-source'}

def body(p):
    return ' '.join(str(p.get(k) or '') for k in ('headline','angle','newFact','differentiator','whyNow')).lower()

def valid(p):
    return p.get('type') in ALLOWED and p.get('pitchScore',0)>=90 and bool(p.get('companies')) and bool(p.get('numbers')) and not any(w in body(p) for w in NOISE_WORDS)

def sig(p):
    c=tuple(sorted(p.get('companies') or []))
    n=tuple(sorted(str(x) for x in (p.get('numbers') or [])[:4]))
    h=set(re.findall(r'[가-힣A-Za-z0-9]{2,}',str(p.get('headline') or '').lower()))
    return c,n,h

clean=[p for p in pitches if valid(p)]
clean.sort(key=lambda x:(x.get('grade')=='A',x.get('pitchScore',0),len(x.get('numbers') or [])),reverse=True)
final=[]
for p in clean:
    c,n,h=sig(p); dup=False
    for q in final:
        qc,qn,qh=sig(q)
        if c==qc and ((n and qn and set(n)&set(qn)) or (len(h&qh)/max(1,len(h|qh))>=.5)):
            dup=True; break
    if not dup:
        final.append(p)
    if len(final)>=3: break

OUT.write_text(json.dumps(final,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
print(f'pitch dedup: {len(pitches)} -> {len(final)}; strategy/industry only; events excluded')
