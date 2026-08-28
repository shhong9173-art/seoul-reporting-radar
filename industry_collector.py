from __future__ import annotations
import html, json, re, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

KST=ZoneInfo('Asia/Seoul')
OUT=Path('industry.json')

FEEDS=[
 ('철강','철강 OR 포스코 OR 포스코홀딩스 OR 현대제철 OR 동국제강 OR 세아제강 OR 열연 OR 냉연 OR 후판 OR 철근'),
 ('비철금속','고려아연 OR 영풍 OR LS MnM OR 풍산 OR 구리 OR 아연 OR 니켈 OR 알루미늄 OR 희소금속 OR 비철금속'),
 ('전력기기','두산에너빌리티 OR HD현대일렉트릭 OR LS ELECTRIC OR 효성중공업 OR 일진전기 OR 변압기 OR 차단기 OR HVDC OR 전력망'),
 ('전선·전력','LS전선 OR 대한전선 OR 가온전선 OR 대원전선 OR 해저케이블 OR 초고압케이블 OR HVDC 케이블 OR 전력케이블'),
 ('에너지','두산에너빌리티 OR GS OR GS칼텍스 OR 풍력 OR 해상풍력 OR 풍력터빈 OR 풍력발전'),
 ('재생에너지','한화솔루션 OR OCI홀딩스 OR 씨에스윈드 OR 해상풍력 OR 육상풍력 OR 태양광 OR 재생에너지'),
 ('화학·소재','LG화학 OR 롯데케미칼 OR 금호석유화학 OR 효성첨단소재 OR 코오롱인더 OR 석유화학 OR 화학소재 OR 스페셜티소재 OR 합성고무'),
]

COMPANIES=[
 '포스코홀딩스','포스코','현대제철','동국제강','세아제강','고려아연','영풍','LS MnM','풍산',
 '두산에너빌리티','HD현대일렉트릭','LS ELECTRIC','효성중공업','일진전기','LS전선','대한전선','가온전선','대원전선',
 'GS','GS칼텍스','한화솔루션','OCI홀딩스','씨에스윈드','LG화학','롯데케미칼','금호석유화학','효성첨단소재','코오롱인더'
]

KEY=[
 '수주','계약','공급','증설','투자','공장','생산중단','가동','감산','철수','매각','인수','합작','관세','반덤핑','통상',
 '가격','원가','마진','LME','구리','아연','니켈','전력망','변압기','HVDC','해저케이블','전력기기','해상풍력','풍력','태양광',
 'ESS','석유화학','구조조정','스페셜티','배터리소재','미국','중국','유럽','북미'
]

EXCLUSIVE_WORDS=('단독','단독취재','단독 확인','단독으로','취재결과','취재를 종합하면','본지 취재','확인됐다','확인한 결과')
STRATEGY_WORDS=('증설','투자','신규공장','공장','생산능력','생산중단','가동','감산','철수','매각','인수','합작','구조조정','수주','계약','공급','가격','원가','마진','관세','반덤핑','통상','해상풍력','HVDC','변압기','전력망','석유화학','스페셜티','배터리소재')
EVENT_WORDS=('인베스터데이','주주총회','설명회','세미나','포럼','엑스포','컨퍼런스','부스투어','기조연설','발표회')

def get(url,timeout=18):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 AutoIndustryDesk/6.0','Accept':'application/rss+xml,application/xml,text/xml,*/*'})
    with urllib.request.urlopen(req,timeout=timeout) as r:return r.read()

def clean(s):
    s=html.unescape(s or '')
    s=re.sub(r'<script.*?</script>|<style.*?</style>|<[^>]+>',' ',s,flags=re.I|re.S)
    return re.sub(r'\s+',' ',s).strip()

def company_list(text):return [c for c in COMPANIES if c in text]

def classify(title,desc):
    blob=(title+' '+desc).lower()
    exclusive=any(w.lower() in blob for w in EXCLUSIVE_WORDS) or '단독' in title
    event=any(w in title for w in EVENT_WORDS)
    signal=sum(1 for k in KEY if k.lower() in blob)
    strategy=sum(1 for k in STRATEGY_WORDS if k.lower() in blob)
    concrete=bool(re.search(r'(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?:조원|억원|만원|달러|만대|천대|대|명|%|톤|MW|GW|GWh|MWh)',blob))
    priority=0
    if exclusive: priority+=60
    if concrete: priority+=15
    priority+=min(15,signal*2)
    priority+=min(10,strategy)
    if event: priority-=20
    return exclusive,event,signal,strategy,concrete,max(0,priority)

def parse_feed(category,query):
    u='https://news.google.com/rss/search?q='+urllib.parse.quote(query)+'&hl=ko&gl=KR&ceid=KR:ko'
    try:root=ET.fromstring(get(u))
    except Exception:return []
    cutoff=datetime.now(KST)-timedelta(hours=72);out=[]
    for item in root.findall('./channel/item'):
        title=(item.findtext('title') or '').strip();link=(item.findtext('link') or '').strip();pub=(item.findtext('pubDate') or '').strip();desc=clean(item.findtext('description') or '')
        src=item.find('source');source=(src.text or '').strip() if src is not None else ''
        if not title or not link:continue
        try:dt=parsedate_to_datetime(pub).astimezone(KST)
        except Exception:dt=datetime.now(KST)
        if dt<cutoff:continue
        text=(title+' '+desc).lower(); keyhits=sum(1 for k in KEY if k.lower() in text)
        if keyhits==0:continue
        exclusive,event,signal,strategy,concrete,priority=classify(title,desc)
        if event and not exclusive and signal<3:continue
        companies=company_list(title+' '+desc)
        out.append({'category':category,'title':title,'url':link,'published':dt.isoformat(),'sourceName':source or 'Google News','summary':desc[:900],'global':False,'companies':companies,'industrySource':True,'signalCount':keyhits,'exclusive':exclusive,'event':event,'strategySignalCount':strategy,'concreteNumber':concrete,'industryPriorityScore':priority})
    return out

all_items=[]
for category,query in FEEDS:all_items.extend(parse_feed(category,query))

seen=set();items=[]
for x in sorted(all_items,key=lambda z:(z['exclusive'],z['industryPriorityScore'],z['published']),reverse=True):
    sig=(x['sourceName'],x['title'].split(' - ')[0].strip().lower())
    if sig in seen:continue
    seen.add(sig);items.append(x)

OUT.write_text(json.dumps({'generatedAt':datetime.now(KST).isoformat(),'count':len(items),'items':items},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
print(f'industry radar: {len(items)} items / exclusive {sum(1 for x in items if x["exclusive"])} / event-only filtered')
