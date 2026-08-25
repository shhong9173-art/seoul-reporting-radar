import json
from datetime import datetime,timedelta
from pathlib import Path
RAW=Path('data.js').read_text(encoding='utf-8')
items=json.loads(RAW.split('=',1)[1].strip().rstrip(';'))
path=Path('archive.json')
try: archive=json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
except Exception: archive=[]
byid={str(x.get('id')):x for x in archive if x.get('id')}
for x in items:
    if x.get('exclusive') or x.get('pitchScore',0)>=70 or (x.get('global') and x.get('score',0)>=70):
        y=dict(x); y['archivedAt']=y.get('archivedAt') or datetime.now().astimezone().isoformat(); byid[str(y['id'])]=y
cut=datetime.now().astimezone()-timedelta(days=90)
out=[]
for x in byid.values():
    try: dt=datetime.fromisoformat(x.get('published','').replace('Z','+00:00'))
    except Exception: dt=datetime.now().astimezone()
    if dt>=cut: out.append(x)
out.sort(key=lambda x:x.get('published',''),reverse=True)
Path('archive.json').write_text(json.dumps(out,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
print(f'archive: {len(out)} items')
