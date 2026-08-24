from __future__ import annotations
import hashlib, html, json, re, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

KST=ZoneInfo('Asia/Seoul'); OUT=Path('data.js'); JSON_OUT=Path('data.json')
FEEDS=[
 ('완성차','현대차 OR 기아 OR 제네시스 OR 현대자동차 OR 기아자동차'),
 ('부품','자동차부품 OR 현대모비스 OR 현대위아 OR 현대트랜시스 OR HL만도 OR 전장부품'),
 ('배터리','전기차 배터리 OR LG에너지솔루션 OR 삼성SDI OR SK온 OR CATL OR 배터리소재'),
 ('정책·관세','자동차 관세 OR 자동차 정책 OR 미국 관세 자동차 OR 전기차 정책 OR IRA 자동차 OR 산업부 자동차 OR 국토부 자동차'),
 ('중국차','BYD OR 중국 전기차 OR 중국 자동차 OR 샤오미 자동차 OR 샤오펑 OR 지커 OR 니오'),
 ('노조·생산','현대차 노조 OR 기아 노조 OR 자동차 파업 OR 자동차 임단협 OR 자동차 생산중단 OR 공장 휴업'),
 ('수주·투자','자동차 수주 OR 배터리 수주 OR 자동차 공급계약 OR 배터리 공급계약 OR 자동차 공장 증설 OR 배터리 공장 투자'),
 ('리콜·안전','자동차 리콜 OR 전기차 화재 OR 자동차 결함 OR 전기차 안전 OR 국토부 리콜'),
 ('단독','단독 자동차 OR 단독 현대차 OR 단독 기아 OR 단독 자동차부품 OR 단독 배터리 OR 단독 전기차'),
 ('미국·글로벌','미국 자동차 시장 OR 미국 자동차 공장 OR 유럽 자동차 규제 OR 글로벌 자동차 공급망')]
GLOBAL_FEEDS=[
 ('Reuters','site:reuters.com (automotive OR car OR EV OR battery OR tariff)'),
 ('Automotive News','site:autonews.com (automotive OR EV OR battery OR supplier)'),
 ('Automotive World','site:automotiveworld.com (EV OR battery OR OEM OR supplier)'),
 ('InsideEVs','site:insideevs.com (EV OR battery OR Tesla OR BYD)'),
 ('Electrek','site:electrek.co (EV OR Tesla OR battery)'),
 ('Nikkei Asia','site:asia.nikkei.com (automotive OR EV OR battery)'),
 ('The Verge','site:theverge.com (EV OR Tesla OR autonomous)'),
 ('Bloomberg','site:bloomberg.com (automotive OR EV OR battery OR tariff)')]
COMPANIES=['현대차','기아','제네시스','현대모비스','현대위아','현대트랜시스','HL만도','LG에너지솔루션','삼성SDI','SK온','CATL','BYD','테슬라','폭스바겐','GM','포드','토요타','BMW','벤츠','르노코리아','한국GM','KG모빌리티','볼보','파나소닉','노스볼트']
SOURCE_TIERS={'연합뉴스':5,'한국경제':5,'매일경제':5,'서울경제':5,'이데일리':5,'머니투데이':5,'전자신문':5,'조선비즈':5,'뉴스1':4,'뉴시스':4,'더팩트':4,'오토타임즈':5,'오토뷰':4,'카가이':4,'모터그래프':4}
GLOBAL_TIERS={'Reuters':8,'Bloomberg':8,'Nikkei Asia':7,'Automotive News':7,'Automotive World':6,'The Verge':5,'InsideEVs':5,'Electrek':4}
HIGH=['수주','계약','공급','증설','투자','공장','생산중단','생산 중단','파업','임단협','관세','보조금','리콜','인증','화재','배터리','소송','매각','철수','출시','판매','실적','가격','노조','자율주행','tariff','battery','recall','fire','autonomous','investment','contract']
FOLLOW=['수주','공급','계약','증설','투자','공장','노조','파업','임단협','관세','리콜','판매','실적','배터리','화재','가격','자율주행','tariff','battery','autonomous']
STOP=set('자동차 자동차산업 산업 업계 관련 시장 올해 오늘 최근 전망 기자 보도 밝혔다 따르면 대한 통해 위한 국내 글로벌 전기차 차량 기업 사업 계획 등 및 의 과 에서 으로 위한 the and for with from this that auto automotive'.split())

def get(url,timeout=18):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 AutoIndustryDesk/4.0','Accept':'application/rss+xml,application/xml,text/xml,*/*'})
    with urllib.request.urlopen(req,timeout=timeout) as r:return r.read()

def clean(s):
    s=re.sub(r'<script.*?</script>|<style.*?</style>|<[^>]+>',' ',s or '',flags=re.I|re.S)
    return re.sub(r'\s+',' ',html.unescape(s)).strip()

def norm_title(t):
    return re.sub(r'\s*[-|｜].*$','',t).lower()

def company_list(text):return [c for c in COMPANIES if c in text]

def tokens(t):return {w for w in re.findall(r'[가-힣A-Za-z0-9]{2,}',t.lower()) if w not in STOP and not w.isdigit()}

def exclusive(t):
    return any(re.search(p,t,re.I) for p in [r'^\s*\[단독(?:취재|보도)?\]',r'^\s*\(단독(?:취재|보도)?\)',r'\b단독(?:취재|보도|입수)\s*:',r'\b단독보도\b'])

def parse_feed(category,query,global_feed=False,source_hint=''):
    lang,gl=('en-US','US') if global_feed else ('ko','KR')
    u='https://news.google.com/rss/search?q='+urllib.parse.quote(query)+'&hl='+lang+'&gl='+gl+'&ceid='+gl+':'+('en' if global_feed else 'ko')
    try:root=ET.fromstring(get(u))
    except Exception:return []
    cutoff=datetime.now(KST)-timedelta(hours=72);out=[]
    for item in root.findall('./channel/item'):
        title=(item.findtext('title') or '').strip();link=(item.findtext('link') or '').strip();pub=(item.findtext('pubDate') or '').strip();desc=clean(item.findtext('description') or '')
        src=item.find('source');source=(src.text or '').strip() if src is not None else source_hint
        if not title or not link:continue
        try:dt=parsedate_to_datetime(pub).astimezone(KST)
        except Exception:dt=datetime.now(KST)
        if dt<cutoff:continue
        out.append({'category':category,'title':title,'url':link,'published':dt.isoformat(),'sourceName':source or source_hint,'summary':desc[:900],'global':global_feed})
    return out

def translate(text):
    text=clean(text)[:900]
    if not text:return ''
    try:
        u='https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=ko&dt=t&q='+urllib.parse.quote(text)
        raw=json.loads(get(u,10));return ''.join(p[0] for p in raw[0] if p and p[0]).strip()
    except Exception:return text

def same_issue(a,b):
    at=tokens(a['title']);bt=tokens(b['title']);sim=len(at&bt)/max(1,len(at|bt))
    ac=set(company_list(a['title']+' '+a.get('summary','')));bc=set(company_list(b['title']+' '+b.get('summary','')))
    ai=any(w.lower() in (a['title']+' '+a.get('summary','')).lower() for w in HIGH);bi=any(w.lower() in (b['title']+' '+b.get('summary','')).lower() for w in HIGH)
    return (bool(ac&bc) and sim>=0.28) or (sim>=0.45 and ai and bi)

def dedupe(items):
    seen=set();out=[]
    for x in sorted(items,key=lambda z:z['published'],reverse=True):
        k=norm_title(x['title'])
        if k in seen:continue
        seen.add(k);out.append(x)
    return out

def clusters(items):
    cs=[]
    for x in sorted(items,key=lambda z:z['published']):
        hit=next((c for c in cs[-100:] if same_issue(x,c['head'])),None)
        if hit:hit['items'].append(x)
        else:cs.append({'head':x,'items':[x]})
    return cs

def enrich(items):
    for ci,c in enumerate(clusters(items),1):
        members=sorted(c['items'],key=lambda z:z['published']); earliest=members[0]; sources=list(dict.fromkeys(m['sourceName'] for m in members if m.get('sourceName')))
        companies=sorted(set(sum((company_list(m['title']+' '+m.get('summary','')) for m in members),[])))
        for x in members:
            text=(x['title']+' '+x.get('summary','')).lower(); ex=exclusive(x['title']); hc=sum(w.lower() in text for w in HIGH); fc=sum(w.lower() in text for w in FOLLOW); tier=GLOBAL_TIERS.get(x.get('sourceName',''),4) if x.get('global') else SOURCE_TIERS.get(x.get('sourceName',''),3)
            age=max(0,(datetime.now(KST)-datetime.fromisoformat(x['published'])).total_seconds()/3600); fresh=max(0,8-int(age//12)); coverage=min(18,max(0,(len(members)-1)*4)); competition=12 if len(sources)>=3 else (8 if len(sources)==2 else 0)
            score=max(38,min(99,44+min(28,hc*4)+min(15,len(companies)*3)+(16 if ex else 0)+tier+competition+fresh-coverage))
            follow=fc>=1 and (bool(companies) or any(w in x['title'] for w in ['관세','리콜','파업','수주','공장','tariff','battery','autonomous']))
            priority='must' if ex or score>=78 else ('follow' if follow else 'normal')
            if x.get('global'):
                x['koTitle']=translate(x['title']);x['koSummary']=translate(x.get('summary',''))[:700];x['translationStatus']='translated';why='해외 주요 매체의 자동차·배터리 이슈입니다. 국내 업체·공급망 파급효과를 먼저 확인하세요.'
            elif ex:why='제목 형식상 단독·속보 후보입니다. 최초 보도 여부와 취재원·회사 공식 확인을 먼저 점검하세요.'
            elif len(sources)>=2:why=f'같은 이슈가 {len(sources)}개 매체에서 확인됐습니다. 최초 관측 매체와 후속 확인 포인트를 비교할 가치가 있습니다.'
            elif any(w in x['title'] for w in ['수주','계약','공장','관세','리콜','파업','화재']):why='산업 파급력이 큰 핵심 키워드가 포함돼 있어 후속 확인 가치가 높습니다.'
            else:why='자동차 업계의 주요 동향으로 관련 기업·정책 변화 여부를 확인할 가치가 있습니다.'
            points=[]
            if ex:points.append('최초 보도 근거와 취재원 층위를 확인')
            if any(w in text for w in ['수주','계약','공급','deal','contract']):points.append('수주 규모·계약 기간·공급 차종·고객사를 확인')
            if any(w in text for w in ['공장','증설','투자','plant','investment']):points.append('투자액·생산능력·가동 시점·고용 효과를 확인')
            if '배터리' in text or 'battery' in text:points.append('셀·소재·장비 중 어느 단계의 이슈인지 확인')
            if '관세' in text or 'tariff' in text:points.append('적용 시점·대상 차종·현지 생산 비중·가격 전가 여부를 확인')
            if '리콜' in text or '화재' in text or 'recall' in text or 'fire' in text:points.append('대상 대수·결함 원인·조치 방법·국내 동일 차종 여부를 확인')
            if not points:points=['회사 공식자료와 업계 취재를 교차 확인']
            x.update({'id':hashlib.sha1((x['url']+'|'+x['title']).encode()).hexdigest()[:12],'companies':companies,'tags':[x['category']]+(['글로벌'] if x.get('global') else [])+(['단독'] if ex else []),'exclusive':ex,'exclusiveScore':95 if ex else max(10,min(70,score-18)),'followUp':follow,'followScore':max(10,min(95,38+fc*9+len(companies)*5)),'priority':priority,'score':score,'whyNow':why,'points':points,'questions':['회사 또는 정부의 공식 확인은 나왔는가?','전날·전주 대비 새롭게 달라진 숫자는 무엇인가?','경쟁사 또는 공급망에 미치는 영향은 무엇인가?']+([f"관련 기업 {', '.join(companies[:3])}의 입장은 무엇인가?"] if companies else []),'publishedLabel':x['published'][:16].replace('T',' '),'clusterId':f'A{ci:03d}','clusterCount':len(members),'earliestObservedAt':earliest['published'],'earliestObservedSource':earliest.get('sourceName',''),'coveredBy':sources[:10],'coverageGap':len(sources)==1,'sourceTier':tier})
    return items

raw=[]
for cat,q in FEEDS:raw.extend(parse_feed(cat,q))
global_items=[]
for hint,q in GLOBAL_FEEDS:global_items.extend(parse_feed('글로벌',q,True,hint))
global_items=dedupe(global_items)[:30]
items=enrich(dedupe(raw)+global_items);items.sort(key=lambda x:(x.get('global',False),x['priority']!='must',-x['score'],x['published']));items=items[:220]
if len(items)<10:raise SystemExit(f'collection returned only {len(items)} items')
payload=json.dumps(items,ensure_ascii=False,separators=(',',':'))
JSON_OUT.write_text(payload,encoding='utf-8');OUT.write_text('window.ITEMS = '+payload+';\n',encoding='utf-8')
print(f'wrote {len(items)} items including {len(global_items)} global items')
