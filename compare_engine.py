import json,re,datetime

def txt(x):return ' '.join([x.get('title',''),x.get('summary',''),x.get('documentText','')])
def nums(x):
 out=[]
 for m in re.finditer(r'(\d+(?:\.\d+)?)\s*(조원|억원|천만원|만원|%)',txt(x)):out.append((float(m.group(1)),m.group(2),m.group(0)))
 return out
def words(x):return set(re.findall(r'[가-힣A-Za-z0-9]{2,}',' '.join([x.get('title',''),x.get('summary','')])))
def similarity(a,b):
 A=words(a);B=words(b);return len(A&B)/max(1,len(A|B)) if A and B else 0

def compare(items):
 for x in items:
  x['comparisons']=[];x['comparisonConfidence']=0
  # Never manufacture an S-grade from same-day duplicates or unrelated documents.
  if x.get('level')=='S':x['level']='B';x['standaloneEligible']=False
  x['standaloneEligible']=False
 for i,x in enumerate(items):
  best=None
  for j,y in enumerate(items):
   if i==j or x.get('org')!=y.get('org'):continue
   try:
    dx=datetime.date.fromisoformat(str(x.get('date',''))[:10]);dy=datetime.date.fromisoformat(str(y.get('date',''))[:10])
   except Exception:continue
   if dy>=dx:continue
   sim=similarity(x,y)
   if sim<0.55:continue
   old=nums(y);new=nums(x)
   changes=[]
   for a in old:
    for b in new:
     if a[1]==b[1] and a[0]!=0:
      pct=(b[0]-a[0])/abs(a[0])*100
      if abs(pct)>=20:changes.append((abs(pct),a,b,pct))
   if changes:
    c=max(changes,key=lambda z:z[0]);candidate=(sim,y,c)
    if best is None or candidate[0]>best[0] or (candidate[0]==best[0] and candidate[2][0]>best[2][0]):best=candidate
  if not best:continue
  sim,y,c=best;maxpct,a,b,pct=c
  x['comparisonConfidence']=round(sim*100,1)
  x['comparisons']=[f"{y.get('date')} {a[2]} → {b[2]} ({pct:+.1f}%)"]
  if sim>=0.72 and maxpct>=50:
   x['level']='A';x['score']=max(int(x.get('score') or 0),78);x['standaloneEligible']=False
   x['why']=f"과거 동일 기관 자료({y.get('date')})와 내용 유사도 {sim*100:.0f}%를 확인했고 수치가 {pct:+.1f}% 변했습니다. 단독 여부는 별도 보도·원문 확인이 필요합니다."
  elif sim>=0.55 and maxpct>=20:
   x['level']='A';x['score']=max(int(x.get('score') or 0),68);x['standaloneEligible']=False
   x['why']=f"과거 자료와 내용 유사도 {sim*100:.0f}%로 매칭됐고 수치 변화({pct:+.1f}%)가 확인됐습니다."
  x['questions']=['변경된 수치의 공식 사유와 최초 결정 시점은?','증감분의 세부 항목별 금액·인원은?','예산서·계약자료·의회자료에서도 같은 변화가 확인되는가?','동일 내용이 이미 보도됐는지 확인했는가?']
 return items

raw=open('data.js',encoding='utf-8').read();items=json.loads(raw.split('=',1)[1].rstrip(' ;\n'));items=compare(items);open('data.js','w',encoding='utf-8').write('const ITEMS = '+json.dumps(items,ensure_ascii=False,separators=(',',':'))+';\n');print('historical comparisons',len(items))
