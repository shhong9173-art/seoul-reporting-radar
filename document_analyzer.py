import os,re,json,subprocess,tempfile,datetime
from urllib.request import Request,urlopen
from urllib.parse import urlparse
NUM=re.compile(r'(?P<value>\d+(?:,\d{3})*(?:\.\d+)?)\s*(?P<unit>조원|억원|만원|원|%|명|가구|세대|건|곳|개)')
FILE=re.compile(r'\.(pdf|hwp|hwpx|xlsx?|csv|docx?|pptx?)(?:[?#]|$)',re.I)
def fetch(u):
 try:
  r=urlopen(Request(u,headers={'User-Agent':'Seoul-Reporting-Radar/1.0'}),timeout=30);return r.read()
 except:return b''
def text_from(u):
 b=fetch(u)
 if not b:return '', 'download_failed'
 ext=os.path.splitext(urlparse(u).path)[1].lower();d=tempfile.mkdtemp();p=os.path.join(d,'f'+ext);open(p,'wb').write(b)
 try:
  if ext=='.pdf':return subprocess.run(['pdftotext','-layout',p,'-'],capture_output=True,text=True,timeout=45).stdout,''
  if ext in ('.xlsx','.xls'):
   code='import pandas as pd,sys; x=pd.ExcelFile(sys.argv[1]); print("\\n".join(["SHEET: "+s+"\\n"+pd.read_excel(sys.argv[1],sheet_name=s).fillna("").to_string(index=False) for s in x.sheet_names]))'
   return subprocess.run(['python','-c',code,p],capture_output=True,text=True,timeout=60).stdout,''
  if ext=='.csv':return b.decode('utf-8-sig','ignore'),''
  if ext=='.docx':
   code='import zipfile,re,sys; z=zipfile.ZipFile(sys.argv[1]); s=z.read("word/document.xml").decode("utf-8","ignore"); print(" ".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>",s)))'
   return subprocess.run(['python','-c',code,p],capture_output=True,text=True,timeout=30).stdout,''
  if ext=='.pptx':
   code='import zipfile,re,sys; z=zipfile.ZipFile(sys.argv[1]); out=[]; [out.extend(re.findall(r"<a:t>(.*?)</a:t>",z.read(n).decode("utf-8","ignore"))) for n in z.namelist() if n.startswith("ppt/slides/slide") and n.endswith(".xml")]; print(" ".join(out))'
   return subprocess.run(['python','-c',code,p],capture_output=True,text=True,timeout=30).stdout,''
  if ext in ('.hwp','.hwpx'):
   for cmd in (['hwp5txt',p],['pandoc',p,'-t','plain']):
    try:
     r=subprocess.run(cmd,capture_output=True,text=True,timeout=60)
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
 links=item.get('attachments',[]);docs=[]
 for u in links:
  if FILE.search(u):
   t,e=text_from(u);docs.append({'url':u,'text':re.sub(r'\s+',' ',t)[:20000],'error':e,'numbers':numbers(t)[:200]})
 body=item.get('summary','')+' '+item.get('title','')
 allnums=numbers(body)+[n for d in docs for n in d['numbers']]
 findings=[]
 for d in docs:
  if d['text']: findings.append('첨부파일 본문을 실제 추출했습니다. 핵심 내용과 수치를 검증 대상으로 표시합니다.')
  if d['error']: findings.append('첨부파일 형식 분석 실패: '+d['error'])
 score=item.get('score',35);verified=bool(docs and any(d['text'] for d in docs));
 if verified:score=min(69,score+10)
 item['documentText']='\n\n'.join(d['text'] for d in docs if d['text'])[:16000];item['documentFiles']=docs;item['numbers']=allnums[:100];item['findings']=findings;item['summary']=docs[0]['text'][:1000] if verified else item.get('summary','');item['standaloneEligible']=False;item['level']='B';item['score']=score
 return item
try:
 s=open('data.js',encoding='utf-8').read();payload=s.split('=',1)[1].strip().rstrip(';');items=json.loads(payload)
 for i,x in enumerate(items):items[i]=analyze(x)
 open('data.js','w',encoding='utf-8').write('const ITEMS = '+json.dumps(items,ensure_ascii=False,separators=(',',':'))+';\n')
 print('analyzed',len(items))
except Exception as e:print('analysis error',e);raise
