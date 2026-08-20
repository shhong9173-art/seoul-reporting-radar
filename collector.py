import re,json,hashlib,datetime,html as htmlmod
from urllib.parse import urljoin,urlparse
from urllib.request import Request,urlopen
from concurrent.futures import ThreadPoolExecutor,as_completed

SOURCES=[('서울시','https://www.seoul.go.kr/news/news_report.do?tr_code=rsite'),('서울 열린데이터','https://data.seoul.go.kr/')]
DISTRICTS=[('강남구','https://www.gangnam.go.kr/'),('강동구','https://www.gangdong.go.kr/'),('강북구','https://www.gangbuk.go.kr/'),('강서구','https://www.gangseo.seoul.kr/'),('관악구','https://www.gwanak.go.kr/'),('광진구','https://www.gwangjin.go.kr/'),('구로구','https://www.guro.go.kr/'),('금천구','https://www.geumcheon.go.kr/'),('노원구','https://www.nowon.kr/'),('도봉구','https://www.dobong.go.kr/'),('동대문구','https://www.ddm.go.kr/'),('동작구','https://www.dongjak.go.kr/'),('마포구','https://www.mapo.go.kr/'),('서대문구','https://www.sdm.go.kr/'),('서초구','https://www.seocho.go.kr/'),('성동구','https://www.sd.go.kr/'),('성북구','https://www.sb.go.kr/'),('송파구','https://www.songpa.go.kr/'),('양천구','https://www.yangcheon.go.kr/'),('영등포구','https://www.ydp.go.kr/'),('용산구','https://www.yongsan.go.kr/'),('은평구','https://www.ep.go.kr/'),('종로구','https://www.jongno.go.kr/'),('중구','https://www.junggu.seoul.kr/'),('중랑구','https://www.jungnang.go.kr/')]
KEY=re.compile(r'(통계|데이터|현황|실적|지표|분석|예산|결산|재정|계약|입찰|보조금|지원금|사업비|고시|공고|행정예고|입법예고|감사|위원회|회의|인허가|사업계획|공모|주택|건축|도시계획|교통|복지|안전)')
FILE=re.compile(r'\.(pdf|hwp|hwpx|xlsx?|csv|docx?|pptx?|zip)(?:[?#]|$)',re.I)
PROMO=re.compile(r'(보도자료|보도설명자료|행사|축제|캠페인|수상|업무협약|협약식|개최|참여|기념|홍보)')
NUM=re.compile(r'\d+(?:\.\d+)?\s*(?:억|억원|조원|만원|%|명|가구|세대|건|곳|개)')
DATE=re.compile(r'(20\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})')
LINK=re.compile(r'''<a[^>]+href=["']([^"']+)["'][^>]*>([\s\S]*?)</a>''',re.I)
PAGE_TIMEOUT=6;MAX_PAGE_BYTES=2_000_000;MAX_CANDIDATES_PER_ORG=10;MAX_DETAILS_PER_ORG=4;MAX_ITEMS=400

def fetch(url,timeout=PAGE_TIMEOUT):
    try:
        req=Request(url,headers={'User-Agent':'Mozilla/5.0 Seoul-Reporting-Radar/4.1','Accept':'text/html,*/*'})
        with urlopen(req,timeout=timeout) as r:return r.read(MAX_PAGE_BYTES).decode('utf-8','ignore')
    except Exception:return ''

def clean(s):
    s=re.sub(r'<script[\s\S]*?</script>|<style[\s\S]*?</style>|<noscript[\s\S]*?</noscript>',' ',s,flags=re.I)
    s=re.sub(r'<[^>]+>',' ',s);s=htmlmod.unescape(s);return re.sub(r'\s+',' ',s).strip()

def content_text(body):
    patterns=[
        r"<article\b[\s\S]*?</article>",
        r"<main\b[\s\S]*?</main>",
        r"<div[^>]+(?:id|class)=[\"'][^\"']*(?:view|content|article|bbs|board)[^\"']*[\"'][^>]*>[\s\S]*?</div>"
    ]
    for pat in patterns:
        m=re.search(pat,body,re.I)
        if m:
            t=clean(m.group(0))
            if len(t)>=120:return t
    return clean(body)

def links(page,base):
    out=[];seen=set()
    for href,title in LINK.findall(page):
        u=urljoin(base,htmlmod.unescape(href).replace('&amp;','&').strip())
        if u not in seen:seen.add(u);out.append((u,clean(title)))
    return out

def detail(url):
    body=fetch(url);atts=[]
    if not body:return '',[],''
    for href,title in links(body,url):
        if FILE.search(urlparse(href).path) or re.search(r'(첨부|다운로드|download|attach|file)',title,re.I):atts.append(href)
    text=content_text(body)
    dm=DATE.search(text[:4000]);pubdate=f'{dm.group(1)}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}' if dm else ''
    return text[:12000],list(dict.fromkeys(atts))[:6],pubdate

def cat(t):
    if re.search(r'통계|데이터|현황|실적|지표|분석',t):return '데이터·통계'
    if re.search(r'예산|결산|재정|계약|입찰|보조금|지원금|사업비',t):return '예산·재정'
    if re.search(r'주택|건축|부동산|도시계획|재개발|재건축|용적률',t):return '부동산'
    if re.search(r'교통|지하철|버스|도로',t):return '교통'
    if re.search(r'복지|출생|청년|어르신|장애|돌봄',t):return '복지'
    if re.search(r'안전|재난|화재|사고|단속|적발',t):return '안전'
    return '행정·공고'

def collect(org,url):
    page=fetch(url)
    if not page:return []
    candidates=[];seen=set()
    for href,title in links(page,url):
        if len(title)<8 or href in seen:continue
        if any(x in title for x in ('로그인','검색','메뉴','바로가기','사이트맵','개인정보')):continue
        if KEY.search(title) or FILE.search(href) or PROMO.search(title):seen.add(href);candidates.append((href,title))
    candidates.sort(key=lambda x:(10 if KEY.search(x[1]) else 0)+(5 if NUM.search(x[1]) else 0)+(5 if FILE.search(x[0]) else 0),reverse=True)
    candidates=candidates[:MAX_CANDIDATES_PER_ORG]
    details={}
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs={ex.submit(detail,u):u for u,t in candidates[:MAX_DETAILS_PER_ORG] if not FILE.search(urlparse(u).path)}
        for f in as_completed(futs):
            try:details[futs[f]]=f.result()
            except Exception:details[futs[f]]=('',[],'')
    out=[]
    for href,title in candidates:
        isfile=bool(FILE.search(urlparse(href).path));bodytext,atts,pubdate=details.get(href,('',[],''))
        allatts=[href] if isfile else [x for x in atts if FILE.search(urlparse(x).path)]
        nums=NUM.findall(title);date=pubdate or datetime.date.today().isoformat();score=35+(8 if KEY.search(title) else 0)+(5 if nums else 0)+(5 if allatts else 0)
        out.append({'id':hashlib.sha1(href.encode()).hexdigest()[:12],'level':'B','category':cat(title),'org':org,'date':date,'score':min(score,69),'title':title,'summary':bodytext[:1800] if bodytext else f'{org} 공개정보에서 자동 발견된 자료. 공식 발표 자체를 단독 근거로 판정하지 않습니다.','why':'원문·첨부파일을 먼저 확인한 뒤 과거자료·예산·계약·통계와 교차검증합니다.','keyNumber':nums[0] if nums else '','tags':['자동수집',org,cat(title)]+(['첨부파일'] if allatts else []),'questions':['원문과 첨부파일의 핵심 수치는 무엇인가?','전년·전월 또는 기존 계획과 무엇이 달라졌는가?','예산·계약·통계 자료와 숫자가 일치하는가?','25개 자치구 전체 추세와 비교했을 때 이상치인가?'],'source':href,'detailUrl':href,'attachments':allatts,'standaloneEligible':False,'rawDetail':bodytext[:12000]})
    return out

items=[]
with ThreadPoolExecutor(max_workers=8) as ex:
    futs={ex.submit(collect,org,url):org for org,url in SOURCES+DISTRICTS}
    for f in as_completed(futs):
        try:items.extend(f.result())
        except Exception as e:print('collect failed',futs[f],type(e).__name__)
seen=set();unique=[]
for x in sorted(items,key=lambda y:(y.get('score',0),y.get('date','')),reverse=True):
    k=(x.get('source',''),x.get('org',''),x.get('title',''))
    if k in seen:continue
    seen.add(k);unique.append(x)
items=unique[:MAX_ITEMS]
with open('data.js','w',encoding='utf-8') as f:f.write('const ITEMS = '+json.dumps(items,ensure_ascii=False,separators=(',',':'))+';\n')
print('collected',len(items),'unique items from',len(SOURCES)+len(DISTRICTS),'portals')
