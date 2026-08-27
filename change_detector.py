from __future__ import annotations
import json,re
from pathlib import Path
from datetime import datetime, timezone, timedelta

DATA=Path('data.json'); OUT=Path('changes.json')
items=json.loads(DATA.read_text(encoding='utf-8')) if DATA.exists() else []
now=datetime.now(timezone.utc)

AUTO={'완성차','부품','배터리','정책·관세','중국차','노조·생산','리콜·안전','수주·투자'}
IND={'철강','비철금속','전력기기','전선·전력','에너지','재생에너지','화학·소재'}
CATS=AUTO|IND
NOISE={'주가','주식','증권','목표주가','급등','급락','추천','관련주','테마주','특징주'}
SIGNALS={
 '투자':['투자','시설투자','출자','증설','CAPEX'],
 '생산':['생산','생산능력','가동','라인','공장','증산','감산'],
 '수주':['수주','계약','납품','공급계약','수주잔고'],
 '가격·원가':['가격','원가','마진','스프레드','반덤핑','관세'],
 '사업재편':['철수','매각','재편','구조조정','합병','분할','거점축소'],
 '기술·상용화':['양산','상용화','개발','자율주행','로봇','배터리','소재']}
NUM_RE=re.compile(r'(?<!\d)(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?:조원|억원|만원|만대|천대|대|명|%|GWh|MWh|kWh|톤|km|MW|GW)(?!\w)',re.I)

def text(x): return ' '.join(str(x.get(k) or '') for k in ('title','koTitle','summary','koSummary'))
def dt(x):
    try: return datetime.fromisoformat(str(x.get('published','')).replace('Z','+00:00'))
    except: return datetime.min.replace(tzinfo=timezone.utc)
def company(x): return (x.get('companies') or [None])[0]
def signal_set(x):
    t=text(x).lower(); out=[]
    for k,ws in SIGNALS.items():
        if any(w.lower() in t for w in ws): out.append(k)
    return out
def key(x): return (company(x) or '', x.get('category') or '', tuple(signal_set(x)))
def nums(x): return list(dict.fromkeys(NUM_RE.findall(text(x))))
def keep(x):
    return (not x.get('global')) and x.get('category') in CATS and company(x) and not any(w in text(x).lower() for w in NOISE)

def summarize(batch):
    m={}
    for x in batch:
        if not keep(x): continue
        k=key(x); m.setdefault(k,{'count':0,'numbers':set(),'titles':[],'companies':[], 'latest':x.get('published'),'category':x.get('category')})
        z=m[k]; z['count']+=1; z['numbers'].update(nums(x));
        if len(z['titles'])<3: z['titles'].append(x.get('title') or x.get('koTitle') or '')
    for z in m.values():
        z['numbers']=sorted(z['numbers']); z['titles']=list(dict.fromkeys(z['titles']))
    return m

try: hist=json.loads(OUT.read_text(encoding='utf-8')) if OUT.exists() else {'snapshots':[]}
except: hist={'snapshots':[]}
if not isinstance(hist,dict): hist={'snapshots':[]}
old=hist.get('snapshots') or []
recent_items=[x for x in items if now-dt(x)<=timedelta(hours=24)]
cur=summarize(items)
prev_snap=old[-1].get('metrics',{}) if old else {}
changes=[]
for k,z in cur.items():
    prev=prev_snap.get('|'.join([k[0],k[1],','.join(k[2])]),{})
    old_count=int(prev.get('count',0) or 0)
    delta=z['count']-old_count
    new_numbers=[n for n in z['numbers'] if n not in set(prev.get('numbers',[]))]
    if delta>=2 or new_numbers:
        changes.append({
          'company':k[0], 'category':k[1], 'signals':list(k[2]),
          'count24h':sum(1 for x in recent_items if keep(x) and key(x)==k),
          'countAll':z['count'],'delta':delta,'newNumbers':new_numbers[:8],
          'headline':z['titles'][0] if z['titles'] else '',
          'titles':z['titles'],'detectedAt':now.isoformat()})
changes.sort(key=lambda x:(bool(x['newNumbers']),x['delta'],x['count24h']),reverse=True)
metrics={}
for k,z in cur.items(): metrics['|'.join([k[0],k[1],','.join(k[2])])]={'count':z['count'],'numbers':z['numbers'][:20]}
old.append({'at':now.isoformat(),'metrics':metrics,'itemCount':len(items)})
cut=now-timedelta(days=31)
kept=[]
for s in old:
    try: d=datetime.fromisoformat(s.get('at','').replace('Z','+00:00'))
    except: continue
    if d>=cut: kept.append(s)
old=kept[-62:]
OUT.write_text(json.dumps({'generatedAt':now.isoformat(),'changes':changes[:30],'snapshots':old},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
print(f'change detector: {len(changes)} changes; snapshots={len(old)}')
