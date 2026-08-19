import json,re,datetime,math
from collections import defaultdict
NUM_RE=re.compile(r'(?P<n>\d+(?:\.\d+)?)\s*(?P<u>조원|억원|만원|천만원|%|명|가구|세대|건|곳|개)')
UNIT={'조원':1_0000_0000,'억원':1_0000,'천만원':1000,'만원':1,'%':1,'명':1,'가구':1,'세대':1,'건':1,'곳':1,'개':1}
def vals(x):
 out=[]
 for m in NUM_RE.finditer((x.get('documentText') or '')+' '+x.get('title','')+' '+x.get('summary','')):
  n=float(m.group('n'))*UNIT[m.group('u')];out.append((m.group(0),n,m.group('u')))
 return out
def key(x):
 t=re.sub(r'[^0-9가-힣 ]',' ',x.get('title','')).lower();return ' '.join(t.split()[:8])
def compare(items):
 groups=defaultdict(list)
 for x in items: groups[(x.get('org'),x.get('category'),key(x))].append(x)
 for g in groups.values():
  g.sort(key=lambda x:x.get('date',''))
  for i,x in enumerate(g):
   x['comparisons']=[];x['level']='B';x['standaloneEligible']=False
   if i==0:continue
   prev=g[i-1];a=vals(prev);b=vals(x)
   if not a or not b:continue
   pairs=[]
   for old in a:
    for new in b:
     if old[2]==new[2] and old[1]!=0:
      pct=(new[1]-old[1])/abs(old[1])*100
      if abs(pct)>=20:pairs.append((old,new,pct))
   if pairs:
    for old,new,pct in pairs[:5]:x['comparisons'].append(f"{old[0]} → {new[0]} ({pct:+.1f}%)")
    maxpct=max(abs(p[2]) for p in pairs)
    x['level']='A' if maxpct<50 else 'S';x['score']=min(100,70+int(min(maxpct,30)));x['standaloneEligible']=x['level']=='S'
    x['why']='과거 공개자료와 비교해 동일 단위의 수치 변화가 확인됐습니다. '+ '; '.join(x['comparisons'])
    x['questions']=['수치가 변한 공식 사유는 무엇인가?','증감분의 세부 항목은 무엇인가?','예산·계약·의회자료에서도 동일한 수치가 확인되는가?','변경 승인일과 담당 부서는 어디인가?']
 return items
try:
 raw=open('data.js',encoding='utf-8').read();items=json.loads(raw.split('=',1)[1].rstrip(' ;\n'));items=compare(items);open('data.js','w',encoding='utf-8').write('const ITEMS = '+json.dumps(items,ensure_ascii=False,separators=(',',':'))+';\n');print('compared',len(items))
except Exception as e:print('comparison error',e)
