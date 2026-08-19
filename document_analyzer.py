import os,re,json,subprocess,tempfile,datetime,html
from urllib.request import Request,urlopen
from urllib.parse import urlparse,urljoin

NUM=re.compile(r'(?P<value>\d+(?:,\d{3})*(?:\.\d+)?)\s*(?P<unit>조원|억원|만원|원|%|명|가구|세대|건|곳|개)')
FILE=re.compile(r'\.(pdf|hwp|hwpx|xlsx?|csv|docx?|pptx?)(?:[?#]|$)',re.I)
LINK=re.compile(r'''(?:href|src)=["']([^"']+)["']''',re.I)
UA='Seoul-Reporting-Radar/2.0'

def fetch(u,timeout=45):
    try:
        r=urlopen(Request(u,headers={'User-Agent':UA,'Accept':'text/html,application/pdf,*/*'}),timeout=timeout)
        return r.read(),r.headers.get('Content-Type','')
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

def discover_documents(url,depth=0,max_links=40):
    found=[];seen=set()
    def add(u,source):
        u=clean_url(u)
        if u and u not in seen:
            seen.add(u);found.append({'url':u,'source':source})
    links,_=discover_page(url)
    for u in links:
        if FILE.search(urlparse(u).path):add(u,url)
    if depth==0:
        host=urlparse(url).netloc
        candidates=[u for u in links if urlparse(u).netloc==host and any(k in u.lower() for k in ('detail','view','download','attach','file','notice','board','article'))]
        for u in candidates[:8]:
            for d in discover_documents(u,1,max_links-len(found)):
                add(d['url'],d.get('source',u))
    return found[:max_links]

def text_from(u):
    b,ct=fetch(u,60)
    if not b:return '', 'download_failed'
    ext=os.path.splitext(urlparse(u).path)[1].lower()
    if not ext:
        c=(ct or '').lower();ext='.pdf' if 'pdf' in c else ('.xlsx' if 'spreadsheet' in c or 'excel' in c else '')
    d=tempfile.mkdtemp();p=os.path.join(d,'f'+ext);open(p,'wb').write(b)
    try:
        if ext=='.pdf':
            r=subprocess.run(['pdftotext','-layout',p,'-'],capture_output=True,text=True,timeout=60);return r.stdout,('pdf_extract_failed' if r.returncode else '')
        if ext in ('.xlsx','.xls'):
            code='import pandas as pd,sys; x=pd.ExcelFile(sys.argv[1]); print("\\n".join(["SHEET: "+s+"\\n"+pd.read_excel(sys.argv[1],sheet_name=s).fillna("").to_string(index=False) for s in x.sheet_names]))'
            r=subprocess.run(['python','-c',code,p],capture_output=True,text=True,timeout=90);return r.stdout,('excel_extract_failed' if r.returncode else '')
        if ext=='.csv':return b.decode('utf-8-sig','ignore'),''
        if ext=='.docx':
            code='import zipfile,re,sys; z=zipfile.ZipFile(sys.argv[1]); s=z.read("word/document.xml").decode("utf-8","ignore"); print(" ".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>",s)))'
            r=subprocess.run(['python','-c',code,p],capture_output=True,text=True,timeout=45);return r.stdout,('docx_extract_failed' if r.returncode else '')
        if ext=='.pptx':
            code='import zipfile,re,sys; z=zipfile.ZipFile(sys.argv[1]); out=[]; [out.extend(re.findall(r"<a:t>(.*?)</a:t>",z.read(n).decode("utf-8","ignore"))) for n in z.namelist() if n.startswith("ppt/slides/slide") and n.endswith(".xml")]; print(" ".join(out))'
            r=subprocess.run(['python','-c',code,p],capture_output=True,text=True,timeout=45);return r.stdout,('pptx_extract_failed' if r.returncode else '')
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
    discovered=[]
    for u in (item.get('attachments') or []):
        if u:
            if FILE.search(urlparse(u).path):discovered.append({'url':u,'source':u})
            else:discovered.extend(discover_documents(u))
    for key in ('url','sourceUrl','link','detailUrl'):
        u=item.get(key)
        if isinstance(u,str) and u.startswith('http'):
            for d in discover_documents(u):
                if d['url'] not in {x['url'] for x in discovered}:discovered.append(d)
    docs=[]
    for d in discovered[:40]:
        t,e=text_from(d['url'])
        docs.append({'url':d['url'],'source':d['source'],'text':re.sub(r'\s+',' ',t)[:30000],'error':e,'numbers':numbers(t)[:500]})
    body=item.get('summary','')+' '+item.get('title','')
    allnums=numbers(body)+[n for d in docs for n in d['numbers']]
    verified=bool(docs and any(d['text'] for d in docs));findings=[]
    if verified:findings.append('상세 페이지에서 첨부파일을 찾아 문서 본문을 실제 추출했습니다.')
    if docs:findings.append(f'첨부/문서 후보 {len(docs)}개를 분석했습니다.')
    for d in docs:
        if d['error']:findings.append('첨부파일 분석 실패: '+d['error'])
    item['documentText']='\n\n'.join(d['text'] for d in docs if d['text'])[:30000]
    item['documentFiles']=docs;item['numbers']=allnums[:300];item['findings']=findings;item['documentVerified']=verified;item['attachmentCount']=len(docs)
    item['standaloneEligible']=False;item['level']='A' if verified else 'B';item['score']=min(100,item.get('score',35)+(10 if verified else 0))
    if verified:item['summary']=docs[0]['text'][:1500]
    return item

s=open('data.js',encoding='utf-8').read();payload=s.split('=',1)[1].strip().rstrip(';');items=json.loads(payload)
for i,x in enumerate(items):items[i]=analyze(x)
open('data.js','w',encoding='utf-8').write('const ITEMS = '+json.dumps(items,ensure_ascii=False,separators=(',',':'))+';\n')
print('analyzed',len(items))
