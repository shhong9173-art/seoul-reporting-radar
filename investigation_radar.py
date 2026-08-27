from __future__ import annotations
import json, re
from pathlib import Path
from datetime import datetime, timezone, timedelta

DATA=Path('data.json'); DART=Path('dart.json'); NUM=Path('dart_numeric.json'); GLOBAL=Path('global.json'); OUT=Path('dig_today.json')
items=json.loads(DATA.read_text(encoding='utf-8')) if DATA.exists() else []
dart=json.loads(DART.read_text(encoding='utf-8')).get('items',[]) if DART.exists() else []
numeric=json.loads(NUM.read_text(encoding='utf-8')).get('items',[]) if NUM.exists() else []
global_items=json.loads(GLOBAL.read_text(encoding='utf-8')) if GLOBAL.exists() else []
now=datetime.now(timezone.utc)

AUTO={'완성차','부품','배터리','정책·관세','중국차','노조·생산','수주·투자','리콜·안전'}
IND={'철강','비철금속','전력기기','전선·전력','에너지','재생에너지','화학·소재'}
NOISE=('주가','주식','증권','목표주가','급등','급락','추천주','관련주','테마주','특징주','리포트','목표가')
EVENT=('인베스터데이','주주총회','설명회','세미나','포럼','엑스포','컨퍼런스','부스투어','기조연설','발표회')
SIGNALS={
 '투자':('투자','출자','증설','CAPEX','신규공장','신규법인','증자'),
 '생산':('생산능력','가동','라인','공장','증산','감산','생산량'),
 '수주':('수주','계약','공급계약','납품','수주잔고'),
 '가격·원가':('가격','원가','마진','스프레드','관세','반덤핑'),
 '사업재편':('철수','매각','재편','구조조정','거점축소','합병','분할','합작'),
 '기술·상용화':('양산','상용화','개발','자율주행','로보택시','로봇','배터리','소재')}
NUM_RE=re.compile(r'(?<!\\d)(?:\\d{1,3}(?:,\\d{3})+|\\d+(?:\\.\\d+)?)(?:조원|억원|만원|만대|천대|대|명|%|GWh|MWh|kWh|톤|km|MW|GW|달러|USD|EUR)(?!\\w)',re.I)
ALIASES={'현대차':('현대자동차','Hyundai'),'기아':('기아자동차','Kia'),'제네시스':('Genesis',),'현대모비스':('MOBIS','Hyundai Mobis'),'현대위아':('Hyundai WIA',),'현대트랜시스':('Hyundai TRANSYS',),'HL만도':('HL Mando',),'포스코':('POSCO','포스코홀딩스'),'현대제철':('Hyundai Steel',),'HD현대일렉트릭':('HD Hyundai Electric',),'효성중공업':('Hyosung Heavy Industries',),'LS ELECTRIC':('LS Electric',),'LS전선':('LS Cable',),'대한전선':('Taihan',),'LG에너지솔루션':('LG Energy Solution','LGES'),'삼성SDI':('Samsung SDI',),'SK온':('SK On',),'두산에너빌리티':('Doosan Enerbility',),'GS칼텍스':('GS Caltex',)}
COMPETITORS={'완성차':['현대차','기아'],'부품':['현대모비스','현대위아','현대트랜시스','HL만도'],'배터리':['LG에너지솔루션','삼성SDI','SK온'],'철강':['포스코','현대제철'],'전력기기':['HD현대일렉트릭','효성중공업','LS ELECTRIC'],'전선·전력':['LS전선','대한전선'],'에너지':['두산에너빌리티','GS칼텍스'],'재생에너지':['두산에너빌리티'],'화학·소재':['GS칼텍스']}
GLOBAL_KW={'완성차':('automotive','EV','vehicle','tariff'),'부품':('supplier','auto parts','automotive'),'배터리':('battery','EV','lithium'),'철강':('steel','iron','tariff'),'비철금속':('copper','aluminum','zinc','nickel'),'전력기기':('grid','transformer','HVDC','power equipment','data center'),'전선·전력':('cable','HVDC','grid'),'에너지':('energy','gas','turbine'),'재생에너지':('wind','renewable','offshore wind'),'화학·소재':('chemical','material','petrochemical')}

def parse_dt(x):
    raw=str(x.get('published') or x.get('date') or '').strip()
    if raw.isdigit() and len(raw)==8:
        try:return datetime.strptime(raw,'%Y%m%d').replace(tzinfo=timezone.utc)
        except ValueError: pass
    try:
        d=datetime.fromisoformat(raw.replace('Z','+00:00'))
        return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d
    except Exception:return datetime.min.replace(tzinfo=timezone.utc)

def text(x):return ' '.join(str(x.get(k) or '') for k in ('title','koTitle','summary','koSummary')).strip()
def companies(x):return [c for c in (x.get('companies') or []) if c]
def numbers(s):return list(dict.fromkeys(NUM_RE.findall(s or '')))
def signals(s):
    t=(s or '').lower();return {k for k,ws in SIGNALS.items() if any(w.lower() in t for w in ws)}
def usable(x):
    if x.get('global') or x.get('category') not in AUTO|IND or not companies(x):return False
    t=text(x).lower();return not any(n in t for n in NOISE) and not any(e in t for e in EVENT)
def recent_news(c,days=45):return [x for x in items if usable(x) and c in companies(x) and parse_dt(x)>=now-timedelta(days=days)]
def dart_for(c,days=60):
    return [d for d in dart if (lambda corp: bool(corp and (corp==c or c in corp or corp in c)))(str(d.get('corpName') or '')) and parse_dt(d)>=now-timedelta(days=days)]
def numeric_for(c):
    return [d for d in numeric if (lambda corp: bool(corp and (corp==c or c in corp or corp in c)))(str(d.get('corpName') or ''))]
def money_vals(r):return [str(n) for n in (r.get('numbers') or []) if re.search(r'(조원|억원|만원|달러|USD|EUR)$',str(n))]
def article_numbers(c):return {n for x in recent_news(c,60) for n in numbers(text(x))}
def uncovered(c):
    seen=article_numbers(c); out=[]
    for r in numeric_for(c):
        for n in money_vals(r):
            if n not in seen and n not in out:out.append(n)
    return out
def globals_for(c,cat):
    aliases=(c,)+ALIASES.get(c,()); kws=GLOBAL_KW.get(cat,()); out=[]
    for g in global_items:
        t=text(g).lower()
        if any(a.lower() in t for a in aliases if a) or any(k.lower() in t for k in kws):out.append(g)
    return sorted(out,key=parse_dt,reverse=True)[:3]
def evidence_line(x):
    return f"{x.get('sourceName') or '매체'}: {(x.get('koTitle') or x.get('title') or '')[:120]}"
def topic(cat,news):
    t=' '.join(text(x) for x in news[:10]).lower()
    for keys,label in [(('수소환원','hyrex'),'수소환원제철'),(('변압기','hvdc','해저케이블','전력망'),'전력망·전력기기'),(('풍력','해상풍력'),'풍력'),(('전기차','배터리'),'전기차·배터리'),(('로봇','자율주행','로보택시'),'자동차 미래사업')]:
        if any(k in t for k in keys):return label
    return cat

cands=[]
# A. 공시의 새 금액이 최근 기사에서 충분히 설명되지 않은 후보
for r in numeric:
    c=str(r.get('corpName') or '')
    fresh=[n for n in money_vals(r) if n not in article_numbers(c)]
    if not c or not fresh:continue
    rel=[x for x in recent_news(c,45) if signals(text(x))]
    if not rel:continue
    cat=rel[0].get('category') or '산업'; sig=set().union(*(signals(text(x)) for x in rel[:10])); top=topic(cat,rel)
    if len(sig)<2 and len(fresh)<2:continue
    if '수주' in sig and '투자' in sig:head=f'{c}, 수주 늘자 투자 확대…생산능력 확충이 관건'
    elif top=='수소환원제철':head=f'{c}, 수소환원제철 투자 확대…탄소보다 원가가 관건'
    elif cat=='전력기기' and '투자' in sig:head=f'{c}, 전력망 호황에 {fresh[0]} 투자…증설 속도전'
    elif '사업재편' in sig:head=f'{c}, 사업재편 속 {fresh[0]} 새로 확인…실제 전략은'
    else:head=f'{c}, 공시에 새 {fresh[0]}…사업전략 얼마나 달라졌나'
    lines=[f'DART {r.get("reportName") or "공시"}에서 {", ".join(fresh[:4])} 확인',*[evidence_line(x) for x in rel[:2]],'공시 숫자를 기존 투자·생산·수주 계획과 대조해 실제 변화인지 확인']
    if '가격·원가' in sig:lines.append('원재료·전력·관세 변화를 붙여 원가와 마진 영향 확인')
    elif '수주' in sig:lines.append('수주잔고·가동률·생산능력을 연결해 증설 필요성 확인')
    elif '사업재편' in sig:lines.append('재편 전후 공장·인력·자산 변화를 비교해 실제 사업 전환 여부 확인')
    else:lines.append('경쟁사와 투자·생산·수주 속도를 비교해 차이 확인')
    cands.append({'kind':'공시 미보도 숫자','score':min(100,92+len(fresh)*2+len(sig)),'headline':head,'why':f'DART의 {fresh[0]}이 최근 기사에서 충분히 설명됐는지 확인할 가치가 있는 후보.','lines':lines[:5],'questions':['이 숫자는 기존 공개 계획보다 얼마나 늘거나 줄었나?','실제 생산능력·수주·원가 변화와 연결되는가?','경쟁사도 같은 방향으로 움직이는가?'],'company':c,'category':cat,'numbers':fresh[:6],'sources':['DART']+[x.get('sourceName') for x in rel[:2] if x.get('sourceName')],'competitors':[x for x in COMPETITORS.get(cat,[]) if x!=c][:3],'global':globals_for(c,cat)})

# B. 한 회사에서 서로 다른 사업 신호가 동시에 움직이는 후보
for c in sorted({cc for x in items if usable(x) for cc in companies(x)}):
    rel=[x for x in recent_news(c,30) if signals(text(x))]
    if len(rel)<3:continue
    sig=set().union(*(signals(text(x)) for x in rel[:12]));cat=rel[0].get('category') or '산업'
    if len(sig)<2:continue
    ds=dart_for(c); nums_all=list(dict.fromkeys(n for x in rel for n in numbers(text(x))))
    if not ds and len(nums_all)<3:continue
    comp=[x for x in COMPETITORS.get(cat,[]) if x!=c][:3]
    if '사업재편' in sig:head=f'{c}, 사업재편 본격화…줄이는 사업·키우는 사업은'
    elif '수주' in sig and '투자' in sig:head=f'{c}, 수주 늘자 투자 확대…생산능력 확충이 관건'
    elif '가격·원가' in sig and '투자' in sig:head=f'{c}, 원가 부담 속 투자 확대…수익성 방어 시험대'
    elif '생산' in sig and '투자' in sig:head=f'{c}, 생산능력 키운다…증설이 수익성으로 이어질까'
    else:head=f'{c}, 사업 신호 겹쳤다…전략 변화 본격화하나'
    lines=[f'최근 30일 {", ".join(sorted(sig)[:4])} 신호가 동시에 확인됨',*[evidence_line(x) for x in rel[:2]],'기존 사업계획·공시 수치와 실제 투자·생산·수주 흐름을 대조']
    if comp:lines.append(f'경쟁사 {", ".join(comp)}와 투자·생산·수주 속도를 비교')
    cands.append({'kind':'전략 변화','score':82+min(12,len(sig)*2)+min(5,len(ds)),'headline':head,'why':'한 회사에서 서로 다른 사업 신호가 동시에 움직여 단일 뉴스보다 전략 변화로 볼 근거가 있는 후보.','lines':lines[:5],'questions':['기존 중장기 계획에서 무엇이 실제로 달라졌나?','경쟁사와 비교해 무엇이 다른가?','투자 확대가 매출·생산능력·수익성으로 이어지는가?'],'company':c,'category':cat,'numbers':nums_all[:6],'sources':list(dict.fromkeys(x.get('sourceName') for x in rel[:3] if x.get('sourceName'))),'competitors':comp,'global':globals_for(c,cat)})

# C. 글로벌 변화와 국내 기업을 연결할 수 있는 후보. 글로벌이 국내 기업 기사에 실제로 연결되는 경우만 통과.
for c in sorted({cc for x in items if usable(x) for cc in companies(x)}):
    news=recent_news(c,30)
    if not news:continue
    cat=news[0].get('category') or '산업'; gl=globals_for(c,cat)
    if not gl:continue
    gtext=' '.join(text(g) for g in gl).lower(); sig=set().union(*(signals(text(x)) for x in news[:8]))
    if not sig:continue
    if cat=='전력기기':head=f'글로벌 전력망 투자 확대…{c}, 수주·증설 어디까지 왔나'
    elif cat in ('완성차','정책·관세'):head=f'글로벌 자동차 통상 변수 확대…{c}, 현지 생산 대응은'
    elif cat=='철강':head=f'글로벌 철강 통상장벽 높아진다…{c}, 수출전략 바뀌나'
    elif cat=='배터리':head=f'글로벌 배터리 경쟁 심화…{c}, 투자·수주 전략 달라지나'
    else:head=f'글로벌 산업 변화 커지는데…{c}, 국내 사업 영향은'
    lines=[f'해외 주요 매체 {gl[0].get("sourceName") or "글로벌"}에서 관련 변화 확인',evidence_line(gl[0]),*[evidence_line(x) for x in news[:2]],'국내 공시·수주·생산 자료와 연결해 실제 영향 확인']
    cands.append({'kind':'글로벌→국내','score':76+min(12,len(gl)*4)+min(8,len(sig)*2),'headline':head,'why':'해외 산업 변화와 국내 기업의 최근 사업 움직임을 한 기사로 연결할 수 있는 후보.','lines':lines[:5],'questions':['해외 변화가 국내 기업의 수주·가격·생산에 실제 영향을 주는가?','국내 경쟁사도 같은 대응을 하는가?','국내 공시에서 숫자로 확인되는 변화가 있는가?'],'company':c,'category':cat,'numbers':list(dict.fromkeys(n for x in news for n in numbers(text(x))))[:6],'sources':list(dict.fromkeys([g.get('sourceName') for g in gl if g.get('sourceName')]+[x.get('sourceName') for x in news[:2] if x.get('sourceName')])), 'competitors':[x for x in COMPETITORS.get(cat,[]) if x!=c][:3],'global':gl})

rank={'공시 미보도 숫자':3,'전략 변화':2,'글로벌→국내':1}
cands.sort(key=lambda x:(rank.get(x['kind'],0),x['score'],len(x.get('numbers',[])),len(x.get('sources',[]))),reverse=True)
final=[];seen=set()
for x in cands:
    if x['company'] in seen or x['score']<78:continue
    # Never surface a lead that lacks a concrete evidence trail.
    if len(x.get('lines',[]))<3 or len(x.get('sources',[]))<2:continue
    seen.add(x['company']);final.append(x)
    if len(final)>=5:break
OUT.write_text(json.dumps({'generatedAt':now.isoformat(),'items':final,'note':'오늘 파볼 것: 공시 미보도 숫자·전략 변화·글로벌→국내 연결을 우선 선별. 기사화 전 원문 확인 필요.'},ensure_ascii=False,indent=2),encoding='utf-8')
print(f'investigation radar: {len(final)} leads')
