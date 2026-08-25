from __future__ import annotations
import json,re
from pathlib import Path

items=json.loads(Path('data.json').read_text(encoding='utf-8'))
OUT=Path('pitch.json')
DART_PATH=Path('dart.json')
DART_NUM_PATH=Path('dart_numeric.json')

try:
    dart=json.loads(DART_PATH.read_text(encoding='utf-8')).get('items',[]) if DART_PATH.exists() else []
except Exception: dart=[]
try:
    dart_numeric=json.loads(DART_NUM_PATH.read_text(encoding='utf-8')).get('items',[]) if DART_NUM_PATH.exists() else []
except Exception: dart_numeric=[]

THEMES={
    'investment':['투자','증자','자금','억원','조원','investment','funding','capex','시설투자'],
    'capacity':['증설','공장','생산','라인','가동','capacity','plant','production','factory','생산능력'],
    'restructuring':['감원','인력감축','축소','철수','조직개편','거점축소','거점 재편','재편','layoff','shutdown','restructure'],
    'tariff':['관세','통상','공급망','tariff','trade','supply chain'],
    'ev_to_ess':['ESS','에너지저장','전환','EV battery','storage','ESS 라인'],
    'order':['수주','계약','납품','고객사','order','contract'],
    'mobility':['AAM','로보택시','자율주행','모셔널','슈퍼널','모빌리티','robotaxi','autonomous'],
    'sales':['판매','출하','인도량','점유율','sales','deliveries','share'],
    'labor':['임금','임협','노조','파업','노사','wage','union','strike'],
    'product':['신차','출시','양산','모델','차종','product','launch','model'],
}
GENERIC=set('자동차 현대차 기아 배터리 전기차 관련 업계 시장 최근 오늘 미국 한국 중국 차량 자동 회사 산업 기업 뉴스 기사 전망 올해 지난해 국내 해외'.split())
NOISE=set('주가 주식 증권 목표주가 투자자 고액자산가 네카오 급등 급락 추천 리서치센터'.split())
SPECIFIC=set('슈퍼널 모셔널 아이오닉 아이오닉5 로보택시 AAM ESS LFP FC-BGA 반도체 전고체 샤힌프로젝트 북미 라스베이거스 멕시코 캐나다 미국 중국 일본 유럽'.lower().split())

PAIR_FRAMES={
    ('investment','restructuring'):('투자 확대와 조직·거점 재편이 동시에','투자는 이어가는데 조직·거점은 재편되는 배경과 실제 전략 전환 폭을 확인'),
    ('investment','capacity'):('투자 확대와 생산능력 재편이 동시에','투자액이 실제 공장·라인 증설과 가동 변화로 이어지는지 확인'),
    ('capacity','tariff'):('관세 대응이 생산·공급망 재편으로','관세 변화가 생산거점·조달선·국내 투자에 미친 실제 변화를 확인'),
    ('order','capacity'):('수주 확대와 생산능력 증설이 맞물려','수주가 실제 설비투자·생산능력 확대로 이어지는지 확인'),
    ('order','investment'):('수주 확대가 추가 투자로 번지는지','신규 수주가 실제 자본지출·고용·생산 확대까지 이어지는지 확인'),
    ('ev_to_ess','capacity'):('EV에서 ESS로 생산축이 이동','EV 수요 변화가 어느 공장·라인의 ESS 전환으로 이어졌는지 확인'),
    ('mobility','investment'):('미래 모빌리티 투자와 사업 재편이 동시에','투자액·상용화 일정과 조직·거점 변화가 어떤 전략 전환을 의미하는지 확인'),
    ('sales','restructuring'):('판매 변화와 조직 재편이 동시에','판매·가동률 변화가 인력·거점 재편으로 이어졌는지 확인'),
    ('sales','investment'):('판매 흐름과 투자 방향이 엇갈려','수요 변화와 실제 투자 방향 사이의 간극과 이유를 확인'),
    ('labor','capacity'):('노사 변화와 생산계획이 직접 연결되는지','임단협 결과가 채용·가동일수·생산량에 실제 영향을 주는지 확인'),
    ('labor','investment'):('노사 비용 변화와 투자계획이 동시에','임금·채용 변화가 투자규모와 생산전략에 미치는 영향을 확인'),
    ('product','capacity'):('신차 확대와 생산능력 재편이 맞물려','신차 계획이 공장·라인·가동 변화로 어떻게 연결되는지 확인'),
}

def title(x): return x.get('koTitle') if x.get('global') and x.get('koTitle') else x.get('title','')
def text(x): return ' '.join(str(v or '') for v in [title(x),x.get('summary',''),x.get('koSummary','')])
def toks(s): return set(re.findall(r'[가-힣A-Za-z0-9]{2,}',s.lower()))
def nums(s): return list(dict.fromkeys(re.findall(r'\d+(?:\.\d+)?\s*(?:조원|억원|만원|억|조|만대|천대|%|명|개|곳|년|개월|GWh|kWh|km)',s,re.I)))
def themes(s):
    low=s.lower(); return {k for k,ws in THEMES.items() if any(w.lower() in low for w in ws)}
def company_names(x): return [c for c in (x.get('companies') or []) if c and c not in NOISE]
def meaningful_tokens(s): return toks(s)-GENERIC-NOISE
def specific_overlap(a,b):
    both=meaningful_tokens(title(a)) & meaningful_tokens(title(b)); return {t for t in both if t in SPECIFIC or len(t)>=4}
def same_signal(a,b):
    overlap=specific_overlap(a,b)
    if len(overlap)>=2: return True,overlap
    na=set(nums(text(a))); nb=set(nums(text(b)))
    if overlap and (na & nb): return True,overlap
    if a.get('global') != b.get('global') and overlap and (themes(text(a)) & themes(text(b))): return True,overlap
    return False,overlap

def dart_key(name):
    aliases={'현대차':'현대자동차','현대자동차':'현대자동차','한국타이어':'한국타이어앤테크놀로지'}
    return aliases.get(name,name)
def dart_rows(company): return [r for r in dart if r.get('corpName')==dart_key(company)]
def numeric_rows(company): return [r for r in dart_numeric if r.get('corpName')==dart_key(company) and r.get('numbers')]

buckets={}
for x in items:
    if x.get('exclusive'): continue
    for c in company_names(x): buckets.setdefault(c,[]).append(x)

candidates=[]
for company,arr in buckets.items():
    arr=sorted(arr,key=lambda x:x.get('published',''),reverse=True)[:60]
    uniq=[];seen=set()
    for x in arr:
        sig=(x.get('sourceName'),re.sub(r'\W','',title(x)).lower()[:100])
        if sig in seen: continue
        seen.add(sig); uniq.append(x)
    company_dart=dart_rows(company); company_numeric=numeric_rows(company)
    for i,a in enumerate(uniq):
        ta=themes(text(a)); na=nums(text(a))
        if not ta: continue
        for b in uniq[i+1:]:
            tb=themes(text(b)); nb=nums(text(b)); pair=None
            for p in PAIR_FRAMES:
                if p[0] in ta and p[1] in tb: pair=p; break
                if p[1] in ta and p[0] in tb: pair=(p[1],p[0]); break
            if not pair: continue
            ok,overlap=same_signal(a,b)
            if not ok: continue
            sources={a.get('sourceName'),b.get('sourceName')}-{None,''}
            domestic=[x for x in (a,b) if not x.get('global')]; globals_=[x for x in (a,b) if x.get('global')]
            if len(sources)<2 and not (domestic and globals_): continue
            all_numbers=list(dict.fromkeys(na+nb))[:8]
            if not all_numbers: continue
            matched=[]
            for row in company_numeric:
                report=str(row.get('reportName','')).lower(); snippets=' '.join(s.get('context','') for s in (row.get('snippets') or []))
                if not overlap or any(k.lower() in report+snippets for k in overlap): matched.append(row)
            has_numeric_dart=bool(matched); has_any_dart=bool(company_dart)
            if pair in {('investment','restructuring'),('investment','capacity'),('capacity','tariff'),('order','capacity'),('order','investment'),('ev_to_ess','capacity'),('mobility','investment')} and not has_numeric_dart: continue
            frame,angle=PAIR_FRAMES[pair]
            score=78 + (8 if len(overlap)>=2 else 0) + (8 if len(sources)>=3 else 0) + (7 if domestic and globals_ else 0) + (7 if len(all_numbers)>=2 else 0) + (10 if has_numeric_dart else 0) + (5 if has_any_dart else 0) + (5 if pair in {('investment','restructuring'),('ev_to_ess','capacity'),('capacity','tariff'),('mobility','investment')} else 0)
            score=min(100,score)
            if score<86: continue
            grade='A' if score>=92 and has_numeric_dart else 'B'
            evidence=[{'source':a.get('sourceName'),'title':title(a),'url':a.get('url'),'published':a.get('published'),'themes':sorted(ta),'numbers':na[:4]},{'source':b.get('sourceName'),'title':title(b),'url':b.get('url'),'published':b.get('published'),'themes':sorted(tb),'numbers':nb[:4]}]
            dart_evidence=[{'source':'DART','corpName':r.get('corpName'),'reportName':r.get('reportName'),'date':r.get('date'),'url':r.get('url'),'numbers':(r.get('numbers') or [])[:12],'contexts':[(s.get('context') or '')[:500] for s in (r.get('snippets') or [])[:4]]} for r in matched[:4]]
            if pair==('investment','restructuring'): headline=f'{company}, 투자 확대하는데 조직·거점은 재편…사업 전략 바뀌나'
            elif pair==('ev_to_ess','capacity'): headline=f'{company}, EV 수요 변화에 ESS로 생산축 이동…어디까지 전환했나'
            elif pair==('capacity','tariff'): headline=f'{company}, 관세 대응에 생산·공급망 재편…국내 투자도 바뀌나'
            elif pair==('order','capacity'): headline=f'{company}, 수주 늘자 생산능력도 키운다…설비투자 본격화하나'
            elif pair==('order','investment'): headline=f'{company}, 수주 확대에 추가 투자…실제 증설 규모는'
            elif pair==('mobility','investment'): headline=f'{company}, 미래 모빌리티 투자는 계속…사업 전열은 재편'
            elif pair==('product','capacity'): headline=f'{company}, 신차 확대 맞춰 생산능력 재편…공장별 변화는'
            else: headline=f'{company}, {frame}'
            candidates.append({'id':f'P{len(candidates)+1:03d}','pitchScore':score,'grade':grade,'headline':headline,'frame':frame,'angle':angle,'category':a.get('category') or b.get('category') or '완성차','companies':[company],'sourceCount':len(sources),'sources':sorted(sources),'globalSignals':len(globals_),'domesticSignals':len(domestic),'numbers':all_numbers,'themes':sorted(ta|tb),'sharedSignals':sorted(overlap),'evidence':evidence,'dartSignals':company_dart[:6],'dartNumericSignals':dart_evidence,'dartNumericCount':sum(len(x.get('numbers') or []) for x in dart_evidence),'whyNow':f'{len(sources)}개 출처와 DART {len(dart_evidence)}개 수치 공시를 교차 확인했습니다. 기사만으로는 드러나지 않는 숫자·사업 변화 연결을 추가 확인할 수 있습니다.','questions':[f'{company}의 {pair[0]}·{pair[1]} 변화가 실제로 동시에 진행되는지 확인','DART 원문 수치가 기사에 나온 투자·생산·계약 숫자와 일치하는지 대조','전년 또는 직전 계획 대비 달라진 투자·생산·인력·일정을 확인','경쟁사에도 같은 변화가 나타나는지 비교'],'rawSignals':[title(a),title(b)]})

candidates.sort(key=lambda x:(x['grade']=='A',x['pitchScore'],x['dartNumericCount'],x['sourceCount'],x['globalSignals'],len(x['sharedSignals']),len(x['numbers'])),reverse=True)
final=[];seen=set()
for p in candidates:
    sig=(tuple(p['companies']),p['frame'],tuple(p['sharedSignals'][:3]))
    if sig in seen: continue
    seen.add(sig); final.append(p)
    if len(final)>=6: break
OUT.write_text(json.dumps(final,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
print(f'pitch builder: {len(final)} high-confidence pitch items / A-grade {sum(1 for x in final if x.get("grade")=="A")}')
