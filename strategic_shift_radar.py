from __future__ import annotations
import json,re
from pathlib import Path
from datetime import datetime,timezone,timedelta

DATA=Path('data.json'); CH=Path('changes.json'); DART=Path('dart.json'); OUT=Path('strategic_shifts.json')
items=json.loads(DATA.read_text(encoding='utf-8')) if DATA.exists() else []
try: changes=json.loads(CH.read_text(encoding='utf-8')) if CH.exists() else {}
except: changes={}
try: dart=json.loads(DART.read_text(encoding='utf-8')) if DART.exists() else {'items':[]}
except: dart={'items':[]}
now=datetime.now(timezone.utc)
AUTO={'완성차','부품','배터리','정책·관세','중국차','노조·생산','리콜·안전','수주·투자'}
IND={'철강','비철금속','전력기기','전선·전력','에너지','재생에너지','화학·소재'}
SIGNALS={'투자':['투자','출자','증설','CAPEX','신규법인'],'생산':['생산능력','가동','라인','공장','증산','감산'],'수주':['수주','계약','공급계약','수주잔고'],'가격·원가':['가격','원가','마진','스프레드','관세','반덤핑'],'사업재편':['철수','매각','재편','구조조정','합병','분할','거점축소'],'기술·상용화':['양산','상용화','개발','자율주행','로봇','배터리','소재']}
NOISE=['주가','증권','목표주가','급등','급락','관련주','테마주','특징주']
NUM_RE=re.compile(r'(?<!\d)(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?:조원|억원|만원|만대|천대|대|명|%|GWh|MWh|kWh|톤|MW|GW)(?!\w)',re.I)

def txt(x): return ' '.join(str(x.get(k) or '') for k in ('title','summary','koTitle','koSummary'))
def dt(x):
    try:return datetime.fromisoformat(str(x.get('published') or x.get('date') or '').replace('Z','+00:00'))
    except:return datetime.min.replace(tzinfo=timezone.utc)
def comp(x): return (x.get('companies') or [None])[0]
def sigs(x):
    t=txt(x).lower(); return [k for k,ws in SIGNALS.items() if any(w.lower() in t for w in ws)]
def nums(x): return list(dict.fromkeys(NUM_RE.findall(txt(x))))
def relevant(x): return (not x.get('global')) and (x.get('category') in AUTO|IND) and comp(x) and not any(n in txt(x).lower() for n in NOISE)
def norm(s): return re.sub(r'[^0-9가-힣A-Za-z]','',str(s).lower())

def similarity(a,b):
    A=set(norm(a).split()); B=set(norm(b).split()); return len(A&B)/max(1,len(A|B))

# Recent company/category signals from collected news
recent=[x for x in items if relevant(x) and now-dt(x)<=timedelta(days=30)]
by={}
for x in recent:
    k=(comp(x),x.get('category'),tuple(sorted(sigs(x))))
    z=by.setdefault(k,{'company':comp(x),'category':x.get('category'),'signals':list(k[2]),'count':0,'numbers':set(),'titles':[],'sources':set(),'latest':x.get('published')})
    z['count']+=1; z['numbers'].update(nums(x)); z['sources'].add(x.get('sourceName'))
    if len(z['titles'])<8:z['titles'].append(x.get('title') or '')

# DART evidence keyed by company name fragments
 dart_items=dart.get('items',[]) if isinstance(dart,dict) else []
