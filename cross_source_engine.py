import json,re,datetime
from collections import defaultdict

def text(x): return ' '.join([x.get('title',''),x.get('summary',''),x.get('documentText','')]).lower()
def nums(x):
 out=[]
 for m in re.finditer(r'(\d+(?:\.\d+)?)\s*(조원|억원|만원|천만원|%)',text(x)):
  out.append((float(m.group(1)),m.group(2)))
 return out

def run(items):
 # Build cross-source clusters by normalized project/topic words.
 groups=defaultdict(list)
 for x in items:
  words=re.findall(r'[가-힣]{2,}',text(x))
  stop={'서울시','서울특별시','구청','자료','사업','관련','추진','계획','공개','통해','대상','위해'}
  sig=tuple(sorted(set(w for w in words if w not in stop),key=lambda w:(-len(w),w))[:8])
  if sig: groups[sig].append(x)
 for g in groups.values():
  if len(g)<2: continue
  for x in g:
   x.setdefault('crossSource',[])
   for y in g:
    if x is y: continue
    if y.get('org')==x.get('org'): continue
    shared=[]
    for a in nums(x):
     for b in nums(y):
      if a[1]==b[1] and a[0]!=b[0]: shared.append(f"{a[0]:g}{a[1]} ↔ {b[0]:g}{b[1]}")
    x['crossSource'].append({'org':y.get('org'),'title':y.get('title'),'numbers':shared[:5],'source':y.get('source')})
   if x['crossSource']:
    x['questions']=list(dict.fromkeys((x.get('questions') or [])+['서울시·25개 구청 자료에서 동일 사업의 예산·실적이 어떻게 다른가?','관련 계약·집행자료와 수치가 일치하는가?']))
    if len(x['crossSource'])>=3 and x.get('level')=='B': x['level']='A';x['score']=max(x.get('score',0),72)
 return items

p=open('data.js',encoding='utf-8').read();items=json.loads(p.split('=',1)[1].rstrip(' ;\n'));items=run(items);open('data.js','w',encoding='utf-8').write('const ITEMS = '+json.dumps(items,ensure_ascii=False,separators=(',',':'))+';\n');print('cross-source links',sum(bool(x.get('crossSource')) for x in items))
