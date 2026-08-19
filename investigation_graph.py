import json,re,datetime
from collections import defaultdict
STAGES={'예산':['예산','사업비','본예산','추경','결산','재정'],'계약':['계약','입찰','낙찰','협상','발주','용역','공사'],'집행':['집행','지출','집행률','지급','실적'],'변경계약':['변경계약','증액','감액','계약변경','설계변경'],'감사':['감사','감사결과','주의','시정','징계','지적'],'회의':['회의록','위원회','의회','질의','답변','보고']}
def txt(x):return ' '.join([x.get('title',''),x.get('summary',''),x.get('documentText','')])
def words(x):return set(re.findall(r'[가-힣]{2,}',txt(x)))
def amounts(x):
 out=[]
 for m in re.finditer(r'(\d+(?:\.\d+)?)\s*(조원|억원|만원|천만원|%)',txt(x)):
  out.append((float(m.group(1)),m.group(2),m.group(0)))
 return out
def stage(x):
 t=txt(x)
 hit=[]
 for s,ks in STAGES.items():
  if any(k in t for k in ks):hit.append(s)
 return hit
def run(items):
 for x in items:
  x['investigation']=x.get('investigation',{})
  x['investigation']['stages']=stage(x)
  x['investigation']['related']=[]
 groups=defaultdict(list)
 for x in items:
  ws=words(x); signature=tuple(sorted(ws,key=lambda w:(-len(w),w))[:10])
  if signature:groups[signature].append(x)
 for g in groups.values():
  if len(g)<2:continue
  for x in g:
   rel=[]
   for y in g:
    if y is x:continue
    shared=len(words(x)&words(y));
    if shared>=3: rel.append({'org':y.get('org'),'title':y.get('title'),'date':y.get('date'),'stages':stage(y),'numbers':[a[2] for a in amounts(y)[:10]],'source':y.get('source')})
   x['investigation']['related']=rel[:20]
   allst=set(x['investigation']['stages']);
   for r in rel:allst.update(r['stages'])
   x['investigation']['pipeline']=list(dict.fromkeys(['예산','계약','집행','변경계약','감사','회의']))
   x['investigation']['pipelineFound']=sorted(allst,key=lambda s:list(STAGES).index(s))
   missing=[s for s in STAGES if s not in allst]
   x['investigation']['missingStages']=missing
   if '변경계약' in allst and ('예산' in allst or '계약' in allst):
    x['level']='A' if x.get('level')=='B' else x.get('level');x['score']=max(x.get('score',0),76)
    x['why']='예산·계약·집행·변경계약 등 사업 흐름에서 연결 근거가 발견됐습니다. 변경 사유와 금액을 확인해야 합니다.'
   if '감사' in allst:
    x['score']=max(x.get('score',0),82);x['questions']=list(dict.fromkeys((x.get('questions') or [])+['감사·위원회 자료에서 지적된 문제의 후속조치는 완료됐는가?']))
 return items
p=open('data.js',encoding='utf-8').read();items=json.loads(p.split('=',1)[1].rstrip(' ;\n'));items=run(items);open('data.js','w',encoding='utf-8').write('const ITEMS = '+json.dumps(items,ensure_ascii=False,separators=(',',':'))+';\n');print('investigation graph built',len(items))
