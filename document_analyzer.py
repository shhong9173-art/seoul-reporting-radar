import os,re,json,subprocess,tempfile,html
from urllib.request import Request,urlopen
from urllib.parse import urlparse,urljoin

NUM=re.compile(r'(?P<value>\d+(?:,\d{3})*(?:\.\d+)?)\s*(?P<unit>조원|억원|만원|원|%|명|가구|세대|건|곳|개)')
FILE=re.compile(r'\.(pdf|hwp|hwpx|xlsx?|csv|docx?|pptx?)(?:[?#]|$)',re.I)
LINK=re.compile(r'''(?:href|src)=["']([^"']+)["']''',re.I)
UA='Seoul-Reporting-Radar/3.0'
MAX_ITEMS=12
MAX_DOCS_PER_ITEM=1
PAGE_TIMEOUT=5
DOC_TIMEOUT=12
MAX_BYTES=1_500_000

def fetch(u,timeout=PAGE_TIMEOUT):
    try:
        r=urlopen(Request(u,headers={'User-Agent':UA,'Accept':'text/html,application/pdf,*/*'}),timeout=timeout)
        return r.read(MAX_BYTES),r.headers.get('Content-Type','')
    except Exception:return b'',''

def clean_url(u):return html.unescape(u).replace('&amp;','&').strip()

def discover_page(url):
    b,ct=fetch(url)
    if not b:return [],''
    text=b.decode('utf-8','ignore'); urls=[]
    for x in LINK.findall(text):
        x=clean_url(urljoin(url,x))
        if x not in urls:urls.append(x)
    return urls,text

def discover_documents(url,max_links=3):
    found=[];seen=set()
    def add(u,source):
        u=clean_url(u)
        if u and u not in seen:seen.add(u);found.append({'url':u,'source':source})
    links,_=discover_page(url)
    for u in links:
        if FILE.search(urlparse(u).path):add(u,url)
    host=urlparse(url).netloc
    candidates=[u for u in links if urlparse(u).netloc==host and any(k in u.lower() for k in ('detail','view','download','attach','file','notice','board','article'))]
    for u in candidates[:1]:
        for x in discover_documents(u,max(0,max_links-len(found))):add(x['url'],x.get('source',u))
        if len(found)>=max_links:break
    return found[:max_links]

def text_from(u):
    b,ct=fetch(u,DOC_TIMEOUT)
    if not b:return '', 'download_failed'
    ext=os.path.splitext(urlparse(u).path)[1].lower()
    if not ext:
        c=(ct or '').lower();ext='.pdf' if 'pdf' in c else ''
    d=tempfile.mkdtemp();p=os.path.join(d,'f'+ext);open(p,'wb').write(b)
    try:
        if ext=='.pdf':
            r=subprocess.run(['pdftotext','-layout',p,'-'],capture_output=True,text=True,timeout=DOC_TIMEOUT);return r.stdout,('pdf_extract_failed' if r.returncode else '')
        if ext in ('.xlsx','.xls'):
            code='import pandas as pd,sys; print(pd.read_excel(sys.argv[1]).fillna("").to_string(index=False))'
            r=subprocess.run(['python','-c',code,p],capture_output=True,text=True,timeout=DOC_TIMEOUT);return r.stdout,('excel_extract_failed' if r.returncode else '')
        if ext=='.csv':return b.decode('utf-8-sig','ignore'),''
        if ext=='.docx':
            code='import zipfile,re,sys; z=zipfile.ZipFile(sys.argv[1]); s=z.read("word/document.xml").decode("utf-8","ignore"); print(" ".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>",s)))'
            r=subprocess.run(['python','-c',code,p],capture_output=True,text=True,timeout=DOC_TIMEOUT);return r.stdout,('docx_extract_failed' if r.returncode else '')
        if ext=='.pptx':
            code='import zipfile,re,sys; z=zipfile.ZipFile(sys.argv[1]); out=[]; [out.extend(re.findall(r"<a:t>(.*?)</a:t>",z.read(n).decode("utf-8","ignore"))) for n in z.namelist() if n.startswith("ppt/slides/slide") and n.endswith(".xml")]; print(" ".join(out))'
            r=subprocess.run(['python','-c',code,p],capture_output=True,text=True,timeout=DOC_TIMEOUT);return r.stdout,('pptx_extract_failed' if r.returncode else '')
        return '','unsupported_format'
    except Exception as e:return '',type(e).__name__

def numbers(t):
    out=[]
    for m in NUM.finditer(t):
        raw=m.group('value').replace(',','');unit=m.group('unit');v=float(raw)
        if unit=='조원':v*=10000;norm='억원'
        elif unit=='만원':v/=10000;norm='억원'
        elif unit=='원':v/=100000000;norm='억원'
        else:norm=unit
        out.append({'raw':m.group(0),'value':v,'unit':norm})
    return out

def should_analyze(item):
    return bool(item.get('attachments')) or int(item.get('score') or 0)>=55 or (item.get('category') in ('데이터·통계','예산·재정') and int(item.get('score') or 0)>=48)

def analyze(item):
    discovered=[]
    for u in (item.get('attachments') or []):
        if u and FILE.search(urlparse(u).path):discovered.append({'url':u,'source':u})
    if should_analyze(item) and not discovered:
        u=item.get('detailUrl') or item.get('source')
        if isinstance(u,str) and u.startswith('http'):discovered.extend(discover_documents(u))
    docs=[];seen=set()
    for d in discovered:
        if d['url'] in seen:continue
        seen.add(d['url']);t,e=text_from(d['url']);docs.append({'url':d['url'],'source':d['source'],'text':re.sub(r'\s+',' ',t)[:20000],'error':e,'numbers':numbers(t)[:150]})
        if len(docs)>=MAX_DOCS_PER_ITEM:break
    body=item.get('summary','')+' '+item.get('title','');allnums=numbers(body)+[n for d in docs for n in d['numbers']]
    verified=bool(docs and any(d['text'] for d in docs));findings=[]
    if verified:findings.append('첨부파일 본문을 실제 추출했습니다.')
    if docs:findings.append(f'첨부/문서 {len(docs)}개를 분석했습니다.')
    for d in docs:
        if d['error']:findings.append('첨부파일 분석 실패: '+d['error'])
    item['documentText']='\n\n'.join(d['text'] for d in docs if d['text'])[:20000];item['documentFiles']=docs;item['numbers']=allnums[:200];item['findings']=findings;item['documentVerified']=verified;item['attachmentCount']=len(docs);item['standaloneEligible']=False;item['level']='A' if verified else item.get('level','B');item['score']=min(100,int(item.get('score',35))+(10 if verified else 0))
    if verified:item['summary']=docs[0]['text'][:1200]
    return item

s=open('data.js',encoding='utf-8').read();payload=s.split('=',1)[1].strip().rstrip(';');items=json.loads(payload)
with_docs=[x for x in items if x.get('attachments')];ranked=sorted([x for x in items if x not in with_docs],key=lambda x:int(x.get('score') or 0),reverse=True);priority=(with_docs+ranked)[:MAX_ITEMS];priority_ids={x.get('id') for x in priority}
for i,x in enumerate(items):
    if x.get('id') in priority_ids:items[i]=analyze(x)
    else:
        x['documentText']=x.get('documentText','');x['documentFiles']=x.get('documentFiles',[]);x['numbers']=x.get('numbers',[]);x['findings']=[];x['documentVerified']=False;x['attachmentCount']=len(x.get('attachments') or []);items[i]=x
open('data.js','w',encoding='utf-8').write('const ITEMS = '+json.dumps(items,ensure_ascii=False,separators=(',',':'))+';\n')
print('analyzed priority items',len(priority),'of',len(items))
