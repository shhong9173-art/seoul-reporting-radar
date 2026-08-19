import json,re,datetime
from collections import defaultdict

def txt(x): return ' '.join([x.get('title',''),x.get('summary',''),x.get('documentText','')])
def nums(x):
 out=[]
 for m in re.finditer(r'(\d+(?:\.\d+)?)\s*(조원|억원|만원|천만원|%)',txt(x)): out.append((float(m.group(1)),m.group(2),m.group(0)))
 return out
def words(x):
 # Similarity is intentionally based on title/summary only; full document text can be very large.
 return set(re.findall(r'[가-힣A-Za-z0-9]{2,}',' '.join([x.get('title',''),x.get('summary','')])))
def run(items):
 # Group by organization and compare only against the same organization's compact title/summary index.
 by_org=defaultdict(list)
 wordsets={id(x):words(x) for x in items}
 for x in items: by_org[x.get('org','')].append(x)
 for i,x in enumerate(items):
  # 1) attachment-vs-release hidden facts
  summary=' '.join([x.get('title',''),x.get('summary','')])
  shown=set(m.group(0) for m in re.finditer(r'(\d+(?:\.\d+)?)\s*(조원|억원|만원|천만원|%)',summary))
  x['hiddenNumbers']=[a[2] for a in nums(x) if a[2] not in shown]
  # 2) near-duplicate documents / changed numbers, without O(n^2) full-text tokenization
  wx=wordsets[id(x)];best=None
  for y in by_org.get(x.get('org',''),[]):
   if y is x: continue
   wy=wordsets[id(y)]; union=len(wx|wy) or 1; inter=len(wx&wy); sim=inter/union
   if sim>=0.35 and (best is None or sim>best[0]):best=(sim,y)
  x['documentChangeSignals']=[]
  if best:
   sim,y=best; old={(n[1],n[0]) for n in nums(y)}
   changed=[n[2] for n in nums(x) if (n[1],n[0]) not in old]
   if changed:x['documentChangeSignals']=[f'유사문서 {sim*100:.0f}% / 변경·추가 숫자: '+', '.join(changed[:10])]
  # Media novelty is handled once by news_novelty.py. Do not perform another 100 Google requests here.
  x['advancedMediaCheck']='handled_by_news_novelty'
  # 3) target-vs-result / execution indicators
  a=nums(x);x['computedMetrics']=[]
  if len(a)>=2:
   vals=[v for v,u,_ in a if u in ('억원','만원','천만원','조원')]
   if len(vals)>=2 and vals[0]:x['computedMetrics'].append(f'자료 내 금액 비교: {vals[0]:g} → {vals[1]:g} ({(vals[1]-vals[0])/vals[0]*100:+.1f}%)')
  # 4) recurring vendors / institutions
  vendors=re.findall(r'(?:업체|회사|법인)\s*[:：]?\s*([가-힣A-Za-z0-9㈜주식회사]{3,30})',txt(x))
  x['vendorSignals']=vendors[:10]
  # 5) composite anomaly summary
  inv=x.get('investigation',{});flags=[]
  if '변경계약' in inv.get('pipelineFound',[]):flags.append('변경계약')
  if '감사' in inv.get('pipelineFound',[]):flags.append('감사')
  if '회의' in inv.get('pipelineFound',[]):flags.append('회의')
  if x.get('hiddenNumbers'):flags.append('첨부문서 숨은 수치')
  if x.get('documentChangeSignals'):flags.append('전년·유사문서 수치 변경')
  x['anomalySummary']=flags
  # 6) why-now
  d=x.get('date','');reasons=[]
  if d:
   try:
    days=(datetime.date.today()-datetime.date.fromisoformat(d[:10])).days
    if days<=2:reasons.append('최근 공개된 자료')
   except:pass
  if '예산' in inv.get('pipelineFound',[]):reasons.append('예산·집행 단계 확인 가능')
  if '변경계약' in inv.get('pipelineFound',[]):reasons.append('변경계약 직후 확인 가치')
  if x.get('hiddenNumbers'):reasons.append('보도자료 밖의 첨부 수치 발견')
  if x.get('documentChangeSignals'):reasons.append('기존 자료와 숫자 변화 확인')
  x['whyNow']=' / '.join(reasons) if reasons else '공개자료 변화 여부 추가 확인 필요'
  x['qualityReasons']=list(dict.fromkeys((x.get('qualityReasons') or [])+flags+reasons))
 return items
p=open('data.js',encoding='utf-8').read();items=json.loads(p.split('=',1)[1].rstrip(' ;\n'));items=run(items);open('data.js','w',encoding='utf-8').write('const ITEMS = '+json.dumps(items,ensure_ascii=False,separators=(',',':'))+';\n');print('advanced radar',len(items),'without duplicate web search')
