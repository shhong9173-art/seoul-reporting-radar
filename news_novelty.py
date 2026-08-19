import json,re,urllib.parse,urllib.request
from html import unescape

MAX_WEB_CHECKS=100

def search(q):
 u='https://www.google.com/search?'+urllib.parse.urlencode({'q':q+' 뉴스','num':10})
 try:
  r=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0 Seoul-Reporting-Radar/2.1'}),timeout=10).read().decode('utf-8','ignore')
  titles=re.findall(r'<h3[^>]*>(.*?)</h3>',r,re.S)
  return [re.sub('<[^>]+>','',unescape(t)).strip() for t in titles[:10]]
 except:return []
def run(items):
 ranked=sorted(range(len(items)),key=lambda i:int(items[i].get('score') or 0),reverse=True)
 check_ids=set(ranked[:MAX_WEB_CHECKS])
 for i,x in enumerate(items):
  if i not in check_ids:
   x['mediaCheck']={'status':'deferred','hits':[],'note':'저우선순위 자료는 상위 취재 후보 선별 후 웹 중복검색합니다.'}
   x['standaloneStatus']='웹 중복검색 보류'
   continue
  q=re.sub(r'[^가-힣A-Za-z0-9 ]',' ',x.get('title',''));q=' '.join(q.split()[:10])
  hits=search(q) if q else []
  x['mediaCheck']={'status':'reported' if hits else 'not_found','hits':hits[:10],'note':'자동 웹 검색 결과이며 최종 보도 여부는 기자가 원문을 확인해야 합니다.'}
  if hits:
   x['standaloneStatus']='이미 보도된 가능성';x['level']='A' if x.get('level')=='S' else x.get('level')
   x['questions']=list(dict.fromkeys((x.get('questions') or [])+['기존 보도와 비교해 새롭게 확인된 사실은 무엇인가?']))
  else:x['standaloneStatus']='검색상 동일 내용 기사 미확인(단독 가능성 후보)'
 return items
p=open('data.js',encoding='utf-8').read();items=json.loads(p.split('=',1)[1].rstrip(' ;\n'));items=run(items);open('data.js','w',encoding='utf-8').write('const ITEMS = '+json.dumps(items,ensure_ascii=False,separators=(',',':'))+';\n');print('media checked',len(check_ids),'of',len(items))
