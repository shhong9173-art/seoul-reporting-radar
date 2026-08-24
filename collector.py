from __future__ import annotations
import hashlib, html, json, re, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

KST=ZoneInfo('Asia/Seoul'); OUT=Path('data.js')
FEEDS=[
 ('완성차','현대차 OR 기아 OR 현대자동차 OR 제네시스 자동차'),
 ('부품','자동차부품 OR 현대모비스 OR HL만도 OR 현대위아 OR 현대트랜시스'),
 ('배터리','전기차 배터리 OR LG에너지솔루션 OR 삼성SDI OR SK온 OR CATL'),
 ('정책·관세','자동차 관세 OR 자동차 정책 OR 미국 관세 전기차 OR 국토부 리콜 자동차 OR 산업부 자동차'),
 ('중국차','BYD OR 중국 전기차 OR 중국 자동차 OR 샤오펑 OR 지커 OR 니오'),
 ('노조·생산','현대차 노조 OR 기아 노조 OR 자동차 파업 OR 자동차 생산 중단 OR 자동차 임단협'),
 ('수주·투자','자동차 수주 OR 배터리 수주 OR 자동차 공장 증설 OR 배터리 공장 투자 OR 자동차 투자')]
COMPANIES=['현대차','기아','제네시스','현대모비스','현대위아','현대트랜시스','HL만도','LG에너지솔루션','삼성SDI','SK온','CATL','BYD','폭스바겐','테슬라','GM','포드','토요타','BMW','벤츠','르노코리아','한국GM','KG모빌리티','볼보']
EXCLUSIVE=['단독','단독취재','단독 보도','단독입수','속보']
HIGH=['수주','계약','공급','증설','투자','공장','생산중단','생산 중단','파업','임단협','관세','보조금','리콜','인증','화재','배터리','소송','매각','철수','출시','판매']
FOLLOW=['수주','공급','계약','증설','투자','공장','노조','파업','임단협','관세','리콜','판매','실적','배터리']

def clean(s):
 s=re.sub(r'<script.*?</script>|<style.*?</style>|<[^>]+>',' ',s or '',flags=re.I|re.S)
 return re.sub(r'\s+',' ',html.unescape(s)).strip()

def get(url):
 req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 AutoDesk/1.0'})
 with urllib.request.urlopen(req,timeout=20) as r:return r.read()

def parse(cat,q):
 u='https://news.google.com/rss/search?q='+urllib.parse.quote(q)+'&hl=ko&gl=KR&ceid=KR:ko'
 try: root=ET.fromstring(get(u))
 except Exception:return []
 out=[]; cutoff=datetime.now(KST)-timedelta(hours=72)
 for it in root.findall('./channel/item'):
  title=(it.findtext('title') or '').strip(); link=(it.findtext('link') or '').strip(); pub=(it.findtext('pubDate') or '').strip(); desc=clean(it.findtext('description') or '')
  sn=it.find('source'); source=(sn.text or '').strip() if sn is not None else ''
  if not title or not link: continue
  try: dt=parsedate_to_datetime(pub).astimezone(KST)
  except Exception: dt=datetime.now(KST)
  if dt<cutoff: continue
  out.append({'category':cat,'title':title,'url':link,'published':dt.isoformat(),'sourceName':source,'summary':desc[:700]})
 return out

def companies(text): return [c for c in COMPANIES if c in text]
def norm(t): return re.sub(r'\s+',' ',re.sub(r'[^0-9A-Za-z가-힣 ]',' ',t).lower()).strip()

def enrich(x):
 text=(x['title']+' '+x['summary']).lower(); comps=companies(x['title']+' '+x['summary'])
 excl=any(w in x['title'] for w in EXCLUSIVE); hh=sum(w.lower() in text for w in HIGH); fh=sum(w.lower() in text for w in FOLLOW)
 score=min(99,45+min(25,hh*4)+min(18,len(comps)*3)+(20 if excl else 0)+(8 if any(w in x['title'] for w in ['관세','리콜','파업','화재','생산중단','계약']) else 0))
 follow=fh>=1 and (bool(comps) or any(w in x['title'] for w in ['관세','리콜','파업','수주','공장']))
 priority='must' if score>=78 or excl else ('follow' if follow else 'normal')
 m=re.search(r'(\d[\d,.]*\s*(?:억원|조원|만대|대|GWh|억달러|만톤|톤|%))',x['title']+' '+x['summary'],re.I)
 key=m.group(1) if m else None
 if excl: why='제목에 단독·속보 표기가 있습니다. 최초 보도 근거와 사실관계를 원문에서 확인해야 합니다.'
 elif any(w in x['title'] for w in ['관세','리콜','파업','수주','계약','공장']): why='업계 파급력이 큰 키워드가 포함돼 있어 후속 취재 가치가 높습니다.'
 else: why='자동차 산업 동향상 관련 기업·정책 변화 여부를 확인할 가치가 있습니다.'
 points=[]
 if excl: points.append('최초 보도 근거와 취재원 층위를 확인')
 if any(w in text for w in ['수주','계약','공급']): points.append('수주 규모·계약 기간·공급 차종·고객사를 확인')
 if any(w in text for w in ['공장','증설','투자']): points.append('투자액·생산능력·가동 시점·고용 효과를 확인')
 if '배터리' in text: points.append('셀·소재·장비 중 어느 단계의 이슈인지 확인')
 if '관세' in text: points.append('적용 시점·대상 차종·현지 생산 비중·가격 전가 여부를 확인')
 if '리콜' in text: points.append('대상 대수·결함 원인·조치 방법·국내 동일 차종 여부를 확인')
 if not points: points=['회사 공식자료와 업계 취재를 교차 확인']
 return {**x,'id':hashlib.sha1((x['url']+x['title']).encode()).hexdigest()[:12],'companies':comps,'tags':[x['category']]+(['단독'] if excl else []),'exclusive':excl,'exclusiveScore':95 if excl else max(10,min(70,score-20)),'followUp':follow,'followScore':max(10,min(95,35+fh*10+len(comps)*5)),'priority':priority,'score':score,'whyNow':why,'keyNumber':key,'points':points,'questions':['회사 또는 정부의 공식 확인은 나왔는가?','전날·전주 대비 새롭게 달라진 숫자는 무엇인가?','경쟁사 또는 공급망에 미치는 영향은 무엇인가?']+([f"관련 기업 {', '.join(comps[:3])}의 입장은 무엇인가?"] if comps else []),'publishedLabel':x['published'][:16].replace('T',' ')}

def main():
 raw=[]
 for cat,q in FEEDS: raw += parse(cat,q)
 seen=set(); unique=[]
 for x in sorted(raw,key=lambda z:z['published'],reverse=True):
  k=norm(x['title'])
  if not k or k in seen: continue
  seen.add(k); unique.append(x)
 items=[enrich(x) for x in unique[:180]]
 items.sort(key=lambda x:(x['priority']!='must',-x['score'],x['published']))
 items=items[:120]
 OUT.write_text('const ITEMS = '+json.dumps(items,ensure_ascii=False,separators=(',',':'))+';\n',encoding='utf-8')
 print('wrote',len(items),'items')
if __name__=='__main__': main()
