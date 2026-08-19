import os,re,json,subprocess,tempfile,datetime,html
from urllib.request import Request,urlopen
from urllib.parse import urlparse
from urllib.error import HTTPError,URLError

NUM=re.compile(r'(?P<value>\d+(?:,\d{3})*(?:\.\d+)?)\s*(?P<unit>조원|억원|만원|원|%|명|가구|세대|건|곳|개)')
FILE=re.compile(r'\.(pdf|hwp|hwpx|xlsx?|csv|docx?|pptx?)(?:[?#]|$)',re.I)
LINK=re.compile(r'''(?:href|src)=["']([^"']+)["']''',re.I)

UA='Seoul-Reporting-Radar/2.0'

def fetch(u,timeout=45):
    try:
        r=urlopen(Request(u,headers={'User-Agent':UA,'Accept':'text/html,application/pdf,*/*'}),timeout=timeout)
        return r.read(),r.headers.get('Content-Type','')
    except Exception:
        return b'',''

def absurl(base,u):
    from urllib.parse import urljoin
    return urljoin(base,u)

def clean_url(u):
    return html.unescape(u).replace('&amp;','&').strip()

def discover_links(page_url):
    b,ct=fetch(page_url)
    if not b:return [],''
    enc='utf-8'
    text=b.decode(enc,'ignore')
    urls=[]
    for x in LINK.findall(text):
        x=clean_url(absurl(page_url,x))
        if x not in urls: urls.append(x)
    return urls,text

def discover_documents(page_url,depth=0,max_links=40):
    """Follow detail pages and discover real attachment/document URLs.
    The collector may give us a listing/detail URL rather than attachment URLs.
    We therefore inspect the page HTML, normalize relative links, and follow a
    small number of same-domain candidate links for one extra level."""
    found=[]; seen=set()
    def add(u,source,kind='attachment'):
        u=clean_url(u)
        if not u or u in seen:return
        seen.add(u);found.append({'url':u,'source':source,'kind':kind})
    direct,txt=discover_links(page_url)
    for u in direct:
        if FILE.search(urlparse(u).path): add(u,page_url,'attachment')
    if depth==0 and len(found)<max_links:
        basehost=urlparse(page_url).netloc
        candidates=[]
        for u in direct:
            p=urlparse(u)
            if p.netloc!=basehost:continue
            low=u.lower()
            if any(k in low for k in ('detail','view','download','attach','file','notice','board','view.do','article')):
                candidates.append(u)
        for u in candidates[:8]:
            sub,_=discover_documents(u,depth=1,max_links=max_links-len(found))
            for d in sub:
                if d['url'] not in seen:
                    seen.add(d['url']);found.append(d)
    return found[:max_links],txt

def text_from(u):
    b,ct=fetch(u,60)
    if not b:return '', 'download_failed'
    ext=os.path.splitext(urlparse(u).path)[1].lower()
    if not ext:
        c=(ct or '').lower()
        ext='.pdf' if 'pdf' in c else ('.xlsx' if 'spreadsheet' in c or 'excel' in c else '')
    d=tempfile.mkdtemp();p=os.path.join(d,'f'+ext);open(p,'wb').write(b)
    try:
        if ext=='.pdf':
            r=subprocess.run(['pdftotext','-layout',p,'-'],capture_output=True,text=True,timeout=60)
            return r.stdout,'' if r.returncode==0 else 'pdf_extract_failed'
        if ext in ('.xlsx','.xls'):
            code='import pandas as pd,sys; x=pd.ExcelFile(sys.argv[1]); print("\\n".join(["SHEET: "+s+"\\n"+pd.read_excel(sys.argv[1],sheet_name=s).fillna("").to_string(index=False) for s in x.sheet_names]))'
            r=subprocess.run(['python','-c',code,p],capture_output=True,text=True,timeout=90)
            return r.stdout,'' if r.returncode==0 else 'excel_extract_failed'
        if ext=='.csv':return b.decode('utf-8-sig','ignore'),''
        if ext=='.docx':
            code='import zipfile,re,sys; z=zipfile.ZipFile(sys.argv[1]); s=z.read("word/document.xml").decode("utf-8","ignore"); print(" ".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>",s)))'
            r=subprocess.run(['python','-c',code,p],capture_output=True,text=True,timeout=45)
            return r.stdout,'' if r.returncode==0 else 'docx_extract_failed'
        if ext=='.pptx':
            code='import zipfile,re,sys; z=zipfile.ZipFile(sys.argv[1]); out=[]; [out.extend(re.findall(r"<a:t>(.*?)</a:t>",z.read(n).decode("utf-8","ignore"))) for n in z.namelist() if n.startswith("ppt/slides/slide") and n.endswith(".xml")]; print(" ".join(out))'
            r=subprocess.run(['python','-c',code,p],capture_output=True,text=True,timeout=45)
            return r.stdout,'' if r.returncode==0 else 'pptx_extract_failed'
        if ext in ('.hwp','.hwpx'):
            for cmd in (['hwp5txt',p],['pandoc',p,'-t','plain']):
                try:
                    r=subprocess.run(cmd,capture_output=True,text=True,timeout=90)
                    if r.stdout.strip():return r.stdout,''
                except:pass
            return '','hwp_extractor_unavailable'
    except Exception as e:return '',str(e)
    return '','unsupported_format'

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

def analyze(item):
    links=item.get('attachments',[]) or []
    discovered=[]
    for u in links:
        if u: discovered.extend(discover_documents(u)[0] if not FILE.search(u) else [{'url':u,'source':u,'kind':'attachment'}])
    # Also treat the item's main URL/detail URL as a source for attachment discovery.
    for key in ('url','sourceUrl','link','detailUrl'):
        u=item.get(key)
        if u and isinstance(u,str) and u.startswith('http'):
            ds,_=discover_documents(u)
            for d in ds:
                if d['url'] not in {x['url'] for x in discovered}:discovered.append(d)
    docs=[]
    for d in discovered[:40]:
        u=d['url']
        if not FILE.search(u) and d.get('kind')!='attachment':continue
        t,e=text_from(u)
        docs.append({'url':u,'source':d.get('source'),'text':re.sub(r'\s+',' ',t)[:30000],'error':e,'numbers':numbers(t)[:500]})
    body=item.get('summary','')+' '+item.get('title','')
    allnums=numbers(body)+[n for d in docs for n in d['numbers']]
    findings=[]
    verified=bool(docs and any(d['text'] for d in docs))
    if verified: findings.append('상세 페이지에서 첨부파일을 찾아 문서 본문을 실제 추출했습니다.')
    if docs: findings.append(f'첨부/문서 후보 {len(docs)}개를 분석했습니다.')
    for d in docs:
        if d['error']: findings.append('첨부파일 분석 실패: '+d['error'])
    score=item.get('score',35)
    if verified:score=min(100,score+10)
    item['documentText']='\n\n'.join(d['text'] for d in docs if d['text'])[:30000]
    item['documentFiles']=docs
    item['numbers']=allnums[:300]
    item['findings']=findings
    if verified:item['summary']=docs[0]['text'][:1500]
    item['documentVerified']=verified
    item['attachmentCount']=len(docs)
    # A document-backed item can be a lead, but never declare it a scoop merely
    # because a government document exists.
    item['standaloneEligible']=False
    item['level']='A' if verified else 'B'
    item['score']=score
    return item

s=open('data.js',encoding='utf-8').read()
payload=s.split('=',1)[1].strip().rstrip(';')
items=json.loads(payload)
for i,x in enumerate(items):items[i]=analyze(x)
open('data.js','w',encoding='utf-8').write('const ITEMS = '+json.dumps(items,ensure_ascii=False,separators=(',',':'))+';\n')
print('analyzed',len(items))
