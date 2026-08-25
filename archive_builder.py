import hashlib,json
from datetime import datetime,timedelta
from pathlib import Path
RAW=Path('data.js').read_text(encoding='utf-8')
items=json.loads(RAW.split('=',1)[1].strip().rstrip(';'))
strong=['수주','계약','공급','증설','투자','공장','관세','리콜','화재','파업','임단협','배터리','자율주행','철수','매각','tariff','battery','recall','fire','investment','contract','autonomous']

def stable_id(x):
    if x.get('id'): return str(x['id'])
    return hashlib.sha1((str(x.get('url',''))+'|'+str(x.get('title',''))).encode('utf-8')).hexdigest()[:12]

for x in items:
    x['id']=stable_id(x)
    text=(x.get('title','')+' '+x.get('summary','')).lower()
    signal=sum(w.lower() in text for w in strong)
    if x.get('global'):
        company=set(x.get('companies') or [])
        domestic=[d for d in items if not d.get('global') and company.intersection(d.get('companies') or [])]
        if not domestic: score=92+min(5,signal)
        elif len(domestic)==1: score=78+min(5,signal)
        else: score=48+min(8,signal)
        reasons=['해외 주요 매체 신호','국내 동일 기업 관련 보도 공백' if not domestic else f'국내 관련 보도 {len(domestic)}건']
    else:
        spread=int(x.get('clusterCount') or 1)
        if x.get('exclusive'): score=25
        elif spread==1 and signal>=1: score=74+min(10,signal*2)
        elif spread==1: score=52
        else: score=max(20,55-spread*7+min(8,signal*2))
        reasons=['국내 단일 매체만 확인' if spread==1 else f'국내 확산 {spread}개 매체']
    x['pitchScore']=min(99,int(score)); x['pitchReasons']=reasons

path=Path('archive.json')
try: archive=json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
except Exception: archive=[]
byid={stable_id(x):x for x in archive}
for x in items:
    if x.get('exclusive') or x.get('pitchScore',0)>=70 or (x.get('global') and x.get('score',0)>=70):
        y=dict(x); y['archivedAt']=y.get('archivedAt') or datetime.now().astimezone().isoformat(); byid[stable_id(y)]=y
cut=datetime.now().astimezone()-timedelta(days=90)
out=[]
for x in byid.values():
    try: dt=datetime.fromisoformat(x.get('published','').replace('Z','+00:00'))
    except Exception: dt=datetime.now().astimezone()
    if dt>=cut: out.append(x)
out.sort(key=lambda x:x.get('published',''),reverse=True)
Path('archive.json').write_text(json.dumps(out,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
Path('data.json').write_text(json.dumps(items,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
Path('data.js').write_text('window.ITEMS = '+json.dumps(items,ensure_ascii=False,separators=(',',':'))+';\n',encoding='utf-8')
print(f'archive: {len(out)} items; pitch candidates: {sum(x.get("pitchScore",0)>=70 and not x.get("exclusive") for x in items)}')
