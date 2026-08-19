import json,re,urllib.parse,urllib.request,datetime
from collections import Counter,defaultdict

MAX_MEDIA_CHECKS=100

def txt(x): return ' '.join([x.get('title',''),x.get('summary',''),x.get('documentText','')])
def nums(x):
 out=[]
 for m in re.finditer(r'(\d+(?:\.\d+)?)\s*(조원|억원|만원|천만원|%)',txt(x)): out.append((float(m.group(1)),m.group(2),m.group(0)))
 return out
def words(x): return set(re.findall(r'[가-힣A-Za-z0-9]{2,}',txt(x)))
def news(q):
 try:
  u='https://www.google.com/search?'+urllib.parse.urlencode({'q':q+' 뉴스','num':10,'tbm':'nws'})
  r=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0 Seoul-Reporting-Radar/2.1'}),timeout=10).read().decode('utf-8','ignore')
  hs=re.findall(r'<h3[^>]*>(.*?)</h3>',r,re.S);return [re.sub('<[^>]+>','',h).strip() for h in hs[:10]]
 except:return []
def run(items):
 ranked=sorted(range(len(items)),key=lambda i:int(items[i].get('score') or 0),reverse=True)
 media_ids=set(ranked[:MAX_MEDIA_CHECKS])
 by_topic=defaultdict(list)
 for x in items:
  sig=tuple(sorted(words(x),key=lambda w:(-len(w),w))[:8])
  if sig:by_topic[sig].append(x)
 for i,x in enumerate(items):
  # 1) attachment-vs-release hidden facts
  body=set(nums(x)); summary=' '.join([x.get('title',''),x.get('summary','')])
  shown=set((m.group(0) for m in re.finditer(r'(\d+(?:\.\d+)?)\s*(조원|억원|만원|천만원|%)',summary)))
  x['hiddenNumbers']=[a[2] for a in nums(x) if a[2] not in shown]
  # 2) near-duplicate documents / changed numbers
  peers=[]
  for y in items:
   if y is x or not x.get('org')==y.get('org'): continue
   inter=len(words(x)&words(y)); union=len(words(x)|words(y)) or 1
   sim=inter/union
   if sim>=0.35: peers.append((sim,y))
  peers.sort(reverse=True,key=lambda z:z[0])
  x['documentChangeSignals']=[]
  if peers:
   sim,y=peers[0]; old={(n[1],n[0]) for n in nums(y)};new={(n[1],n[0]) for n in nums(x)}
   changed=[n[2] for n in nums(x) if (n[1],n[0]) not in old]
   if changed:x['documentChangeSignals']=[f'유사문서 {sim*100:.0f}% / 변경·추가 숫자: '+', '.join(changed[:10])]
  # 3) media novelty — only top candidates to avoid hundreds of external requests
  if i in media_ids:
   q=' '.join(re.findall(r'[가-힣A-Za-z0-9]+',x.get('title',''))[:10]);hits=news(q) if q else []
   x['mediaCheck']={'status':'reported' if hits else 'not_found','hits':hits,'note':'검색 결과는 참고용이며 최종 보도 여부는 원문 확인 필요'}
   x['standaloneStatus']='기존 보도 가능성 있음' if hits else '검색상 동일 제목 기사 미확인'
  else:
   x['mediaCheck']={'status':'deferred','hits':[],'note':'상위 취재 후보 선별 후 웹 중복검색'}
   x['standaloneStatus']='웹 중복검색 보류'
  # 4) target-vs-result / execution indicators
  a=nums(x); x['computedMetrics']=[]
  if len(a)>=2:
   vals=[v for v,u,_ in a if u in ('억원','만원','천만원','조원')]
   if len(vals)>=2 and vals[0]:x['computedMetrics'].append(f'자료 내 금액 비교: {vals[0]:g} → {vals[1]:g} ({(vals[1]-vals[0])/vals[0]*100:+.1f}%)')
  # 5) recurring vendors / institutions
  vendors=re.findall(r'(?:업체|회사|법인)\s*[:：]?\s*([가-힣A-Za-z0-9㈜주식회사]{3,30})',txt(x))
  x['vendorSignals']=vendors[:10]
  # 6) composite anomaly summary
  inv=x.get('investigation',{});flags=[]
  if '변경계약' in inv.get('pipelineFound',[]):flags.append('변경계약')
  if '감사' in inv.get('pipelineFound',[]):flags.append('감사')
  if '회의' in inv.get('pipelineFound',[]):flags.append('회의')
  if x.get('hiddenNumbers'):flags.append('첨부문서 숨은 수치')
  if x.get('documentChangeSignals'):flags.append('전년·유사문서 수치 변경')
  x['anomalySummary']=flags
  # 7) why-now
  d=x.get('date',''); reasons=[]
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
p=open('data.js',encoding='utf-8').read();items=json.loads(p.split('=',1)[1].rstrip(' ;\n'));items=run(items);open('data.js','w',encoding='utf-8').write('const ITEMS = '+json.dumps(items,ensure_ascii=False,separators=(',',':'))+';\n');print('advanced radar',len(items),'media checks',len(media_ids))
