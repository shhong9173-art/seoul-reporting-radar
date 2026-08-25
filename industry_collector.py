from __future__ import annotations
import html, json, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

KST=ZoneInfo('Asia/Seoul')
OUT=Path('industry.json')

# Industrial desk coverage, with automotive kept separate and highest priority.
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

STOP={'산업','업계','시장','기업','관련','최근','오늘','전망','기자','보도','밝혔다','따르면','국내','글로벌','사업','계획','올해','지난해'}

def get(url,timeout=18):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 AutoIndustryDesk/5.0','Accept':'application/rss+xml,application/xml,text/xml,*/*'})
    with urllib.request.urlopen(req,timeout=timeout) as r:return r.read()

def clean(s):
    s=html.unescape(s or '')
    s=__import__('re').sub(r'<script.*?</script>|<style.*?</style>|<[^>]+>',' ',s,flags=__import__('re').I|__import__('re').S)
    return __import__('re').sub(r'\s+',' ',s).strip()

def company_list(text):return [c for c in COMPANIES if c in text]

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
        out.append({'category':category,'title':title,'url':link,'published':dt.isoformat(),'sourceName':source or 'Google News','summary':desc[:900],'global':False,'companies':company_list(title+' '+desc),'industrySource':True,'signalCount':keyhits})
    return out

all_items=[]
for category,query in FEEDS:
    all_items.extend(parse_feed(category,query))

seen=set();items=[]
for x in sorted(all_items,key=lambda z:z['published'],reverse=True):
    sig=(x['sourceName'],x['title'].split(' - ')[0].strip().lower())
    if sig in seen:continue
    seen.add(sig);items.append(x)

OUT.write_text(json.dumps({'generatedAt':datetime.now(KST).isoformat(),'count':len(items),'items':items},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
print(f'industry radar: {len(items)} items')
