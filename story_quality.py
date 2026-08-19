import json,re
from collections import defaultdict

def words(x): return set(re.findall(r'[가-힣A-Za-z0-9]{2,}', ' '.join([x.get('title',''),x.get('summary',''),x.get('documentText','')])))
def quality(items):
 for x in items:
  score=int(x.get('score') or 0); reasons=[]
  # Public-source novelty gate: no source alone can become a standalone scoop.
  if x.get('standaloneEligible') is True and x.get('level')=='S': reasons.append('과거·교차자료에서 수치 변화 근거 확인')
  else: x['standaloneEligible']=False
  if x.get('crossSource'): score+=min(10,len(x['crossSource'])*2); reasons.append('서울시·타 자치구 교차자료 존재')
  inv=x.get('investigation',{}); found=set(inv.get('pipelineFound',[]))
  if '계약' in found and '변경계약' in found: score+=8;reasons.append('계약→변경계약 흐름 확인')
  if '감사' in found: score+=10;reasons.append('감사자료 연결')
  if '회의' in found: score+=5;reasons.append('회의자료 연결')
  if x.get('documentText'): score+=4;reasons.append('첨부문서 본문 분석 완료')
  x['score']=min(100,score);x['qualityReasons']=reasons
  if x['score']>=85 and x.get('standaloneEligible'): x['level']='S'
  elif x['score']>=70 and x.get('level') not in ('S',): x['level']='A'
  elif x.get('level') not in ('S','A'): x['level']='B'
  x['why']=(' / '.join(reasons)+'. ' if reasons else '')+x.get('why','')
 return items
p=open('data.js',encoding='utf-8').read();items=json.loads(p.split('=',1)[1].rstrip(' ;\n'));items=quality(items);open('data.js','w',encoding='utf-8').write('const ITEMS = '+json.dumps(items,ensure_ascii=False,separators=(',',':'))+';\n')
