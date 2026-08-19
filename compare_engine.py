import json,re
from collections import defaultdict
NUM_RE=re.compile(r'(?P<n>\d+(?:\.\d+)?)\s*(?P<u>조원|억원|천만원|만원|%|명|가구|세대|건|곳|개)')
UNIT={'조원':1_0000_0000,'억원':1_0000,'천만원':1000,'만원':1,'%':1,'명':1,'가구':1,'세대':1,'건':1,'곳':1,'개':1}
STOP=set('서울시 서울특별시 구청 사업 추진 계획 관련 개최 위한 따른 통해 올해 지난해 올해의 자료 안내 보도 공고'.split())
def norm(s): return re.sub(r'[^0-9가-힣 ]',' ',(s or '').lower())
def tokens(s): return [x for x in norm(s).split() if len(x)>=2 and x not in STOP]
def vals(x):
 text=' '.join([x.get('documentText',''),x.get('title',''),x.get('summary','')]);out=[]
 for m in NUM_RE.finditer(text): out.append((m.group(0),float(m.group('n'))*UNIT[m.group('u')],m.group('u')))
 return out
def fingerprint(x): return set(tokens(' '.join([x.get('title',''),x.get('summary',''),x.get('documentText','')[:4000]])))
def similarity(a,b):
 A=fingerprint(a);B=fingerprint(b)
 return len(A&B)/max(1,len(A|B)) if A and B else 0
def group_candidates(items):
 groups=[]
 for x in items:
  candidates=[(similarity(x,g[0]),g) for g in groups if x.get('org')==g[0].get('org') and x.get('category')==g[0].get('category')]
  candidates=[c for c in candidates if c[0]>=0.20]
  if candidates:max(candidates,key=lambda z:z[0])[1].append(x)
  else:groups.append([x])
 return groups
def compare(items):
 for x in items:x['comparisons']=[];x['level']='B';x['standaloneEligible']=False;x['comparisonConfidence']=0
 for g in group_candidates(items):
  g.sort(key=lambda x:x.get('date',''))
  for i,x in enumerate(g):
   best=[]
   for p in g[max(0,i-3):i]:
    sim=similarity(x,p);a=vals(p);b=vals(x)
    for old in a:
     for new in b:
      if old[2]==new[2] and old[1]!=0:
       pct=(new[1]-old[1])/abs(old[1])*100
       if abs(pct)>=20:best.append((abs(pct),sim,p,old,new,pct))
   if not best:continue
   best.sort(reverse=True,key=lambda z:z[0]);maxpct,sim,p,old,new,pct=best[0]
   x['comparisonConfidence']=round(sim*100,1)
   x['comparisons']=[f"{q.get('date')} {o[0]} → {n[0]} ({pc:+.1f}%)" for _,_,q,o,n,pc in best[:5]]
   if sim>=0.32 and maxpct>=50:x['level']='S';x['score']=min(99,80+int(min(maxpct/2,19)));x['standaloneEligible']=True
   elif sim>=0.20 and maxpct>=20:x['level']='A';x['score']=min(79,60+int(min(maxpct/2,19)))
   x['why']=f"과거 자료와 내용 유사도 {sim*100:.0f}%로 매칭됐고 동일 단위 수치 변화가 확인됐습니다: "+'; '.join(x['comparisons'])
   x['questions']=['변경된 수치의 공식 사유와 최초 결정 시점은?','증감분의 세부 항목별 금액·인원은?','예산서·계약자료·의회자료에서도 같은 변화가 확인되는가?','담당 부서와 최종 승인자는 누구인가?']
 return items
raw=open('data.js',encoding='utf-8').read();items=json.loads(raw.split('=',1)[1].rstrip(' ;\n'));items=compare(items);open('data.js','w',encoding='utf-8').write('const ITEMS = '+json.dumps(items,ensure_ascii=False,separators=(',',':'))+';\n');print('compared',len(items))
