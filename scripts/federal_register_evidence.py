"""Bounded original-body follow-up; a company mention is never a scoop."""
import argparse
import hashlib
import json
import re
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from overseas_official import ALIASES, exact_mention

KST=timezone(timedelta(hours=9))


def official_url(url, prefix):
    try:
        u=urlsplit(url)
        return u.scheme=='https' and u.netloc=='www.federalregister.gov' and u.path.startswith(prefix) and not u.query and not u.fragment
    except (TypeError, ValueError):
        return False


def fetch(url):
    if not official_url(url,'/'):
        raise ValueError('untrusted official URL')
    with urlopen(Request(url,headers={'User-Agent':'newsroom-public-document-evidence/1.0'}),timeout=18) as r:
        if not official_url(r.geturl(),'/'):
            raise ValueError('unexpected redirect')
        data=r.read(3_000_001)
    if len(data)>3_000_000:raise ValueError('document size limit')
    return data


class Blocks(HTMLParser):
    def __init__(self):
        super().__init__();self.blocks=[];self.parts=[];self.ignored=0
    def flush(self):
        text=re.sub(r'\s+',' ',' '.join(self.parts)).strip()
        if text:self.blocks.append(text)
        self.parts=[]
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'):self.ignored+=1
        if tag in ('p','tr','h1','h2','h3'):self.flush()
    def handle_endtag(self,tag):
        if tag in ('script','style'):self.ignored=max(0,self.ignored-1)
        if tag in ('p','tr','h1','h2','h3'):self.flush()
    def handle_data(self,data):
        if not self.ignored:self.parts.append(data)


def companies(text):
    # Do not turn POSCO Holdings/International/Future M into POSCO steel.
    found=[]
    for company,aliases in ALIASES.items():
        if company=='포스코':
            clean=re.sub(r'\bPOSCO\s+(?:Holdings|International|Future\s*M|Chemical)\b','',text,flags=re.I)
            if exact_mention(clean,'POSCO'):found.append(company)
        elif any(exact_mention(text,a) for a in aliases):found.append(company)
    if exact_mention(text,'POSCO Holdings'):found.append('포스코홀딩스')
    return found


def inspect(row,request=fetch):
    no=str(row.get('sourceId') or '')
    date=str(row.get('published') or '')
    if not re.fullmatch(r'20\d{2}-\d{4,6}',no):raise ValueError('invalid document number')
    datetime.strptime(date,'%Y-%m-%d')
    expected_path='/documents/'+date.replace('-','/')+'/'+no+'/'
    if not official_url(row.get('sourceUrl'),expected_path):raise ValueError('list identity mismatch')
    meta=json.loads(request('https://www.federalregister.gov/api/v1/documents/'+no+'.json'))
    if (meta.get('document_number')!=no or meta.get('publication_date')!=date
        or meta.get('html_url')!=row['sourceUrl']):raise ValueError('detail identity mismatch')
    body_url=meta.get('body_html_url')
    expected='/documents/full_text/html/'+date.replace('-','/')+'/'+no+'.html'
    if not official_url(body_url,expected) or urlsplit(body_url).path!=expected:
        raise ValueError('official body identity unavailable')
    raw=request(body_url)
    parser=Blocks();parser.feed(raw.decode('utf-8-sig'));parser.flush()
    if not parser.blocks or sum(map(len,parser.blocks))<100:
        raise ValueError('official body incomplete')
    evidence=[]
    for block in parser.blocks:
        hits=companies(block)
        if not hits:continue
        # Retain a short source quotation, never inferred duties or award totals.
        excerpt=block[:450]
        if not companies(excerpt):
            matches=[m.start() for aliases in ALIASES.values() for alias in aliases
                     for m in re.finditer(re.escape(alias),block,re.I)]
            start=max(0,min(matches)-80) if matches else 0
            excerpt=block[start:start+450]
        evidence.append({'companies':hits,'text':excerpt,
                         'truncated':len(block)>450})
    all_hits=sorted({c for e in evidence for c in e['companies']})
    return {'sourceId':no,'published':date,'sourceUrl':row['sourceUrl'],
            'bodyUrl':body_url,'title':row.get('title'),
            'status':'body_checked','bodySha256':hashlib.sha256(raw).hexdigest(),
            'companiesMentioned':all_hits,'evidence':evidence[:4],
            'evidenceBlocksTotal':len(evidence),'bodyCompanyMentionVerified':bool(all_hits),
            'sameEventPressCoverage':'not_checked','confirmedScoop':False,
            'companyImpactVerified':False,
            'publicFactQuestion':'이 공식 공보에서 귀사가 명시된 항목과 적용 대상에 관해 이미 공개한 설명·정정 자료가 있습니까?',
            'warning':'본문 기업명과 짧은 문맥만 확인. 세율·계약·효력·국내 영향·미보도는 별도 검증'}


def build(source,request=fetch,limit=8,now=None):
    now=now or datetime.now(KST)
    if not 1<=limit<=8:raise ValueError('document budget 1..8')
    docs=source.get('documents')
    valid=bool(source.get('generatedAt') and isinstance(docs,list))
    eligible=[];seen=set()
    for row in docs if valid else []:
        if not isinstance(row,dict) or row.get('source')!='US Federal Register':continue
        key=row.get('sourceId')
        if key in seen:continue
        seen.add(key);eligible.append(row)
    eligible.sort(key=lambda x:str(x.get('published') or ''),reverse=True)
    items=[];checks=[]
    for row in eligible[:limit]:
        try:
            evidence=inspect(row,request)
            items.append(evidence)
            checks.append({'sourceId':row.get('sourceId'),'status':'body_checked'})
        except (OSError,ValueError,TypeError,UnicodeError) as e:
            reasons={'invalid document number','list identity mismatch','detail identity mismatch',
                     'official body identity unavailable','official body incomplete','document size limit','unexpected redirect'}
            checks.append({'sourceId':row.get('sourceId'),'status':'source_error','errorType':type(e).__name__,
                           'reason':str(e) if str(e) in reasons else 'network_or_response_format_error'})
    failures=sum(c['status']=='source_error' for c in checks)
    unqueried=max(0,len(eligible)-limit)
    source_incomplete=bool(source.get('sourceErrors') or any(c.get('status')!='checked' for c in source.get('checks',[])))
    complete=valid and not source_incomplete and not failures and not unqueried
    return {'generatedAt':now.isoformat(timespec='seconds'),
        'sourceGeneratedAt':source.get('generatedAt'),'status':('checked' if complete else 'incomplete'),
        'checks':checks,'items':items,'sourceSearchIncomplete':source_incomplete,
        'failedDocuments':failures,'unqueriedDocuments':unqueried,
        'verifiedDocumentCount':len(items),
        'companyMentionDocumentCount':sum(bool(x['companiesMentioned']) for x in items) if complete else None,
        'confirmedScoops':0,'warning':'검색 목록 안의 제한된 문서 본문 대조. 원천 오류·미조회는 0건이 아니며 수집일은 발표일이 아님'}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--input',default='digests/overseas_official_latest.json')
    p.add_argument('--output',default='digests/federal_register_evidence_latest.json')
    a=p.parse_args()
    try:source=json.loads(Path(a.input).read_text())
    except (OSError,ValueError):source={}
    d=build(source)
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
    try:previous=json.loads(out.read_text())
    except (OSError,ValueError):previous={}
    if d['status']!='checked':
        failed={c['sourceId'] for c in d['checks'] if c['status']=='source_error'}
        prior=previous.get('items',[])+previous.get('retainedEvidence',[])
        retained={x['sourceId']:x for x in prior if x.get('sourceId') in failed or not d['checks']}
        d['retainedEvidence']=list(retained.values())
        d['retainedEvidenceIsCurrent']=False
    tmp=out.with_suffix('.json.tmp');tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');tmp.replace(out)
    print('FR body verification',d['status'],'checked',d['verifiedDocumentCount'],'errors',d['failedDocuments'])
    print('Document checks',json.dumps(d['checks']))
    for x in d['items']:
        print(x['sourceId'],x['published'],','.join(x['companiesMentioned']),json.dumps(x['evidence'][:1],ensure_ascii=False))


if __name__=='__main__':main()
