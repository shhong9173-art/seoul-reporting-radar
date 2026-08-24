from __future__ import annotations
import hashlib, html, json, re, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

KST = ZoneInfo('Asia/Seoul')
OUT = Path('data.js')

FEEDS = [
    ('완성차', '현대차 OR 기아 OR 제네시스 OR 현대자동차 OR 기아자동차'),
    ('부품', '자동차부품 OR 현대모비스 OR 현대위아 OR 현대트랜시스 OR HL만도 OR 전장부품'),
    ('배터리', '전기차 배터리 OR LG에너지솔루션 OR 삼성SDI OR SK온 OR CATL OR 배터리소재'),
    ('정책·관세', '자동차 관세 OR 자동차 정책 OR 미국 관세 자동차 OR 전기차 정책 OR IRA 자동차 OR 산업부 자동차 OR 국토부 자동차'),
    ('중국차', 'BYD OR 중국 전기차 OR 중국 자동차 OR 샤오미 자동차 OR 샤오펑 OR 지커 OR 니오'),
    ('노조·생산', '현대차 노조 OR 기아 노조 OR 자동차 파업 OR 자동차 임단협 OR 자동차 생산중단 OR 공장 휴업'),
    ('수주·투자', '자동차 수주 OR 배터리 수주 OR 자동차 공급계약 OR 배터리 공급계약 OR 자동차 공장 증설 OR 배터리 공장 투자'),
    ('리콜·안전', '자동차 리콜 OR 전기차 화재 OR 자동차 결함 OR 전기차 안전 OR 국토부 리콜'),
    ('단독', '단독 자동차 OR 단독 현대차 OR 단독 기아 OR 단독 자동차부품 OR 단독 배터리 OR 단독 전기차'),
    ('미국·글로벌', '미국 자동차 시장 OR 미국 자동차 공장 OR 유럽 자동차 규제 OR 글로벌 자동차 공급망')
]

COMPANIES = [
    '현대차','기아','제네시스','현대모비스','현대위아','현대트랜시스','HL만도',
    'LG에너지솔루션','삼성SDI','SK온','CATL','BYD','테슬라','폭스바겐','GM','포드',
    '토요타','BMW','벤츠','르노코리아','한국GM','KG모빌리티','볼보','파나소닉','노스볼트'
]

SOURCE_TIERS = {
    '연합뉴스':5,'연합뉴스TV':5,'한국경제':5,'매일경제':5,'서울경제':5,'이데일리':5,
    '머니투데이':5,'전자신문':5,'조선비즈':5,'한국일보':4,'조선일보':4,'중앙일보':4,'동아일보':4,
    '파이낸셜뉴스':4,'아시아경제':4,'뉴스1':4,'뉴시스':4,'더팩트':4,'데일리안':3,
    '오토타임즈':5,'오토뷰':4,'카가이':4,'오토트리뷴':4,'모터그래프':4,'탑라이더':3
}

EXCLUSIVE = ['단독','단독취재','단독 보도','단독입수','속보']
HIGH = ['수주','계약','공급','증설','투자','공장','생산중단','생산 중단','파업','임단협','관세','보조금','리콜','인증','화재','배터리','소송','매각','철수','출시','판매','실적','가격','노조']
FOLLOW = ['수주','공급','계약','증설','투자','공장','노조','파업','임단협','관세','리콜','판매','실적','배터리','화재','가격']
TOPIC_STOP = set('자동차 자동차산업 산업 업계 관련 시장 올해 오늘 최근 전망 기자 보도 밝혔다 따르면 대한 통해 위한 국내 글로벌 전기차 차량 기업 사업 계획 등 및 의 과 에서 으로 위한'.split())


def get(url, timeout=18):
    req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0 AutoIndustryDesk/2.0','Accept':'application/rss+xml,application/xml,text/xml,*/*'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def clean(s: str) -> str:
    s = re.sub(r'<script.*?</script>|<style.*?</style>|<[^>]+>', ' ', s or '', flags=re.I|re.S)
    return re.sub(r'\s+', ' ', html.unescape(s)).strip()


def norm_title(t: str) -> str:
    t = re.sub(r'\s*[-|｜].*$', '', t)
    return re.sub(r'[^0-9A-Za-z가-힣 ]', ' ', t).lower().split()


def tokens(t: str):
    words = re.findall(r'[가-힣A-Za-z0-9]{2,}', t.lower())
    return {w for w in words if w not in TOPIC_STOP and not re.fullmatch(r'\d+', w)}


def company_list(text: str):
    return [c for c in COMPANIES if c in text]


def parse_feed(category, query):
    u = 'https://news.google.com/rss/search?q=' + urllib.parse.quote(query) + '&hl=ko&gl=KR&ceid=KR:ko'
    try:
        root = ET.fromstring(get(u))
    except Exception:
        return []
    cutoff = datetime.now(KST) - timedelta(hours=72)
    out=[]
    for item in root.findall('./channel/item'):
        title=(item.findtext('title') or '').strip(); link=(item.findtext('link') or '').strip(); pub=(item.findtext('pubDate') or '').strip(); desc=clean(item.findtext('description') or '')
        src=item.find('source'); source=(src.text or '').strip() if src is not None else ''
        if not title or not link: continue
        try: dt=parsedate_to_datetime(pub).astimezone(KST)
        except Exception: dt=datetime.now(KST)
        if dt < cutoff: continue
        out.append({'category':category,'title':title,'url':link,'published':dt.isoformat(),'sourceName':source,'summary':desc[:700]})
    return out


def classify_cluster(x):
    text=x['title']+' '+x.get('summary','')
    comps=company_list(text)
    ts=tokens(x['title'])
    impact=[w for w in HIGH if w.lower() in text.lower()]
    return comps, ts, impact


def same_issue(a,b):
    ac,at,ai=classify_cluster(a); bc,bt,bi=classify_cluster(b)
    company_overlap=bool(set(ac)&set(bc))
    sim=len(at&bt)/max(1,len(at|bt))
    impact_overlap=bool(set(ai)&set(bi))
    return (company_overlap and sim>=0.28) or (sim>=0.45 and impact_overlap)


def build_clusters(items):
    clusters=[]
    for x in sorted(items,key=lambda z:z['published']):
        hit=None
        for c in clusters[-80:]:
            if same_issue(x,c['head']):
                hit=c; break
        if hit:
            hit['items'].append(x)
        else:
            clusters.append({'head':x,'items':[x]})
    out=[]
    for i,c in enumerate(clusters,1):
        members=c['items']; members.sort(key=lambda z:z['published'])
        earliest=members[0]; sources=list(dict.fromkeys(m['sourceName'] for m in members if m.get('sourceName')))
        companies=sorted(set(sum((company_list(m['title']+' '+m.get('summary','')) for m in members),[])))
        out.append((i,members,earliest,sources,companies))
    return out


def enrich(items):
    clusters=build_clusters(items)
    for cluster_id,members,earliest,sources,companies in clusters:
        for x in members:
            text=(x['title']+' '+x.get('summary','')).lower()
            excl=any(w in x['title'] for w in EXCLUSIVE)
            high_count=sum(w.lower() in text for w in HIGH)
            follow_count=sum(w.lower() in text for w in FOLLOW)
            tier=SOURCE_TIERS.get(x.get('sourceName',''),3)
            same_issue_count=len(members)
            coverage=min(18,max(0,(same_issue_count-1)*4))
            competition=12 if len(sources)>=3 else (8 if len(sources)==2 else 0)
            score=44+min(28,high_count*4)+min(15,len(companies)*3)+(16 if excl else 0)+tier+competition
            # Heavy coverage lowers novelty, but never below the relevance floor.
            score=max(38,min(99,score-coverage))
            follow=follow_count>=1 and (bool(companies) or any(w in x['title'] for w in ['관세','리콜','파업','수주','공장']))
            priority='must' if excl or score>=78 else ('follow' if follow else 'normal')
            if len(sources)>=3 and not excl and score<78:
                priority='follow' if follow else 'normal'
            if excl:
                why='제목에 단독·속보 표기가 있습니다. 최초 보도 여부와 취재원·회사 공식 확인을 먼저 점검하세요.'
            elif len(sources)>=2:
                why=f'같은 이슈가 {len(sources)}개 매체에서 확인됐습니다. 최초 관측 매체와 후속 확인 포인트를 비교할 가치가 있습니다.'
            elif any(w in x['title'] for w in ['수주','계약','공장','관세','리콜','파업','화재']):
                why='산업 파급력이 큰 핵심 키워드가 포함돼 있어 후속 확인 가치가 높습니다.'
            else:
                why='자동차 업계의 주요 동향으로 관련 기업·정책 변화 여부를 확인할 가치가 있습니다.'
            points=[]
            if excl: points.append('최초 보도 근거와 취재원 층위를 확인')
            if any(w in text for w in ['수주','계약','공급']): points.append('수주 규모·계약 기간·공급 차종·고객사를 확인')
            if any(w in text for w in ['공장','증설','투자']): points.append('투자액·생산능력·가동 시점·고용 효과를 확인')
            if '배터리' in text: points.append('셀·소재·장비 중 어느 단계의 이슈인지 확인')
            if '관세' in text: points.append('적용 시점·대상 차종·현지 생산 비중·가격 전가 여부를 확인')
            if '리콜' in text or '화재' in text: points.append('대상 대수·결함 원인·조치 방법·국내 동일 차종 여부를 확인')
            if not points: points=['회사 공식자료와 업계 취재를 교차 확인']
            x.update({
                'id':hashlib.sha1((x['url']+'|'+x['title']).encode()).hexdigest()[:12],
                'companies':companies,
                'tags':[x['category']]+(['단독'] if excl else []),
                'exclusive':excl,
                'exclusiveScore':95 if excl else max(10,min(70,score-18)),
                'followUp':follow,
                'followScore':max(10,min(95,38+follow_count*9+len(companies)*5)),
                'priority':priority,'score':score,'whyNow':why,'keyNumber':extract_number(x['title']+' '+x.get('summary','')),
                'points':points,
                'questions':['회사 또는 정부의 공식 확인은 나왔는가?','전날·전주 대비 새롭게 달라진 숫자는 무엇인가?','경쟁사 또는 공급망에 미치는 영향은 무엇인가?'] + ([f"관련 기업 {', '.join(companies[:3])}의 입장은 무엇인가?"] if companies else []),
                'publishedLabel':x['published'][:16].replace('T',' '),
                'clusterId':f'A{cluster_id:03d}','clusterCount':len(members),
                'earliestObservedAt':earliest['published'],'earliestObservedSource':earliest.get('sourceName',''),
                'coveredBy':sources[:10],'coverageGap':len(sources)==1,
                'sourceTier':tier
            })
    return items


def extract_number(text):
    m=re.search(r'(\d[\d,.]*\s*(?:조원|억원|만대|대|GWh|억달러|만톤|톤|%))',text,re.I)
    return m.group(1) if m else None


def dedupe(items):
    seen=set(); out=[]
    for x in sorted(items,key=lambda z:z['published'],reverse=True):
        k=' '.join(norm_title(x['title']))
        if k in seen: continue
        seen.add(k); out.append(x)
    return out

raw=[]
for cat,q in FEEDS: raw.extend(parse_feed(cat,q))
items=enrich(dedupe(raw))
items.sort(key=lambda x:(x['priority']!='must', -x['score'], x['published']), reverse=False)
items=items[:180]
OUT.write_text('const ITEMS = '+json.dumps(items,ensure_ascii=False,separators=(',',':'))+';\n',encoding='utf-8')
print(f'wrote {len(items)} items from {len(FEEDS)} RSS queries')