from __future__ import annotations
import json,re
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
NOISE=('주가','주식','증권','목표주가','급등','급락','추천주','관련주','테마주','특징주','리포트')
SIGNALS={
 '투자':('투자','출자','증설','CAPEX','신규공장','신규법인','증자'),
 '생산':('생산능력','가동','라인','공장','증산','감산','생산량'),
 '수주':('수주','계약','공급계약','납품','수주잔고'),
 '가격·원가':('가격','원가','마진','스프레드','관세','반덤핑'),
 '사업재편':('철수','매각','재편','구조조정','거점축소','합병','분할','합작'),
 '기술·상용화':('양산','상용화','개발','자율주행','로보택시','로봇','배터리','소재')
}
NUM_RE=re.compile(r'(?<!\d)(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?:조원|억원|만원|만대|천대|대|명|%|GWh|MWh|kWh|톤|km|MW|GW)(?!\w)',re.I)
DOMESTIC_ALIASES={
 '현대차':('현대자동차','Genesis','제네시스','Hyundai'),
 '기아':('Kia','기아자동차'),
 '현대모비스':('MOBIS','Hyundai Mobis'),
 '포스코':('POSCO','포스코홀딩스'),
 '현대제철':('Hyundai Steel',),
 'HD현대일렉트릭':('HD Hyundai Electric','Hyundai Electric'),
 '효성중공업':('Hyosung Heavy Industries',),
 'LS ELECTRIC':('LS Electric','LS ELECTRIC'),
 'LS전선':('LS Cable',),
 '대한전선':('Taihan',),
 'LG에너지솔루션':('LG Energy Solution','LGES'),
 '삼성SDI':('Samsung SDI',),
 'SK온':('SK On',),
 '두산에너빌리티':('Doosan Enerbility',),
 'GS칼텍스':('GS Caltex',),
}
COMPETITORS={
 '완성차':['현대차','기아'],
 '부품':['현대모비스','현대위아','현대트랜시스','HL만도'],
 '배터리':['LG에너지솔루션','삼성SDI','SK온'],
 '철강':['포스코','현대제철'],
 '전력기기':['HD현대일렉트릭','효성중공업','LS ELECTRIC'],
 '전선·전력':['LS전선','대한전선'],
 '에너지':['두산에너빌리티','GS칼텍스'],
 '재생에너지':['두산에너빌리티'],
}

def text(x): return ' '.join(str(x.get(k) or '') for k in ('title','koTitle','summary','koSummary')).strip()
def dt(x):
    try:return datetime.fromisoformat(str(x.get('published') or x.get('date') or '').replace('Z','+00:00'))
    except:return datetime.min.replace(tzinfo=timezone.utc)
def companies(x): return [c for c in (x.get('companies') or []) if c]
def nums(s): return list(dict.fromkeys(NUM_RE.findall(s or '')))
def sigs(s):
    t=(s or '').lower(); return {k for k,ws in SIGNALS.items() if any(w.lower() in t for w in ws)}
def clean(s): return not any(n in (s or '').lower() for n in NOISE)
def recent_news(c,days=45): return [x for x in items if not x.get('global') and c in companies(x) and dt(x)>=now-timedelta(days=days) and clean(text(x))]
def has_company_mention(c,x):
    t=text(x).lower(); return c.lower() in t or any(a.lower() in t for a in DOMESTIC_ALIASES.get(c,()))
def dart_for(c):
    out=[]
    for d in dart:
        corp=str(d.get('corpName') or '')
        if corp and (corp==c or c in corp or corp in c) and now-dt(d)<=timedelta(days=60): out.append(d)
    return out
def dart_numeric(c):
    out=[]
    for d in numeric:
        corp=str(d.get('corpName') or '')
        if corp and (corp==c or c in corp or corp in c): out.append(d)
    return out
def money(v): return bool(re.search(r'(조원|억원|만원|달러|USD|EUR)$',str(v)))
def uncovered_numbers(c):
    rows=dart_numeric(c); news=recent_news(c)
    article_nums={n for x in news for n in nums(text(x))}
    vals=[]
    for r in rows:
        for n in r.get('numbers') or []:
            if money(n) and n not in article_nums and n not in vals: vals.append(n)
    return vals

def topic_for(c,news):
    all_text=' '.join(text(x) for x in news[:12]).lower()
    if any(k in all_text for k in ('수소환원','hyrex')): return '수소환원제철'
    if any(k in all_text for k in ('변압기','hvdc','해저케이블','전력망')): return '전력망·전력기기'
    if any(k in all_text for k in ('풍력','해상풍력')): return '풍력'
    if any(k in all_text for k in ('배터리','전기차')): return '전기차·배터리'
    if any(k in all_text for k in ('로봇','자율주행','로보택시')): return '자동차 미래사업'
    if c in ('포스코','현대제철') and any(k in all_text for k in ('철강','고로')): return '철강'
    return news[0].get('category') if news else '산업'

def relevant_news(c,arr):
    return [x for x in arr if has_company_mention(c,x) and sigs(text(x))]

def competitor_rows(cat,c):
    return [x for x in COMPETITORS.get(cat,[]) if x!=c]

def global_related(c,cat):
    aliases=(c,)+DOMESTIC_ALIASES.get(c,())
    kws={'전력기기':('grid','transformer','HVDC','power equipment','data center'),'전선·전력':('cable','HVDC','grid'),'철강':('steel','iron','tariff'),'비철금속':('copper','aluminum','zinc','nickel'),'배터리':('battery','EV','lithium'),'완성차':('automotive','EV','vehicle','tariff'),'부품':('supplier','auto parts','automotive'),'에너지':('energy','gas','turbine'),'재생에너지':('wind','renewable','offshore wind'),'화학·소재':('chemical','material','petrochemical')}.get(cat,())
    out=[]
    for g in global_items:
        t=(str(g.get('title') or '')+' '+str(g.get('summary') or '')).lower()
        if any(a.lower() in t for a in aliases if a) or any(k.lower() in t for k in kws):
            out.append(g)
    return sorted(out,key=dt,reverse=True)[:3]

candidates=[]
# 1) DART number uncovered: strongest single-company candidates
for c in sorted({str(d.get('corpName') or '') for d in dart if d.get('corpName')}):
    ns=uncovered_numbers(c); news=relevant_news(c,recent_news(c))
    if not ns or not news: continue
    cat=news[0].get('category') or '산업'; topic=topic_for(c,news); sig=set().union(*(sigs(text(x)) for x in news[:10]))
    headline=f"{c}, 공시에 새 숫자…{topic} 투자·생산 변화 짚어볼 만"
    if '투자' in sig and '수주' in sig: headline=f"{c}, 수주 늘자 투자 확대…생산능력 확충이 관건"
    elif topic=='수소환원제철': headline=f"{c}, 수소환원제철 대규모 투자…탄소보다 원가가 관건"
    elif '사업재편' in sig: headline=f"{c}, 사업재편 속 공시 숫자 달라졌다…실제 전략은"
    lines=[f"DART에서 {', '.join(ns[:3])}의 구체적 수치 확인",f"최근 보도에서는 관련 사업의 {', '.join(sorted(sig)[:3]) or '사업 변화'}만 주로 다뤄짐",f"공시 숫자와 기존 투자·생산·수주 계획을 대조해 실제 변화 확인"]
    questions=['이 숫자는 과거 공개 계획보다 얼마나 늘거나 줄었나?','실제 생산능력·수주·원가 변화로 연결되는가?']
    score=92+min(8,len(ns)-1)+min(5,len(sig))
    candidates.append({'kind':'공시 미보도 숫자','score':min(100,score),'headline':headline,'why':f'DART에 새 금액이 잡혔지만 최근 기사에서 그 의미가 충분히 설명되지 않은 후보.','lines':lines,'questions':questions,'company':c,'category':cat,'numbers':ns[:5],'sources':['DART']+[x.get('sourceName') for x in news[:3] if x.get('sourceName')],'global':global_related(c,cat)})

# 2) multi-signal company strategy changes
for c in sorted({cc for x in items if not x.get('global') for cc in companies(x)}):
    news=recent_news(c,30); rel=relevant_news(c,news)
    if len(rel)<3: continue
    sig=set().union(*(sigs(text(x)) for x in rel[:12])); cat=rel[0].get('category') or '산업'
    if len(sig)<2: continue
    ds=dart_for(c); nums_all=sorted({n for x in rel for n in nums(text(x))})
    if len(ds)<1 and len(nums_all)<3: continue
    comp=competitor_rows(cat,c)
    headline=f"{c}, 투자·{('수주' if '수주' in sig else '생산')} 동시 확대…전략 전환 본격화되나"
    if '사업재편' in sig: headline=f"{c}, 사업재편 본격화…줄이는 사업·키우는 사업은"
    lines=[f"최근 30일 {', '.join(sorted(sig)[:4])} 관련 보도가 동시에 확인됨",f"관련 숫자 {', '.join(nums_all[:5]) or '다수'}를 기존 사업계획과 대조",f"{'경쟁사 '+', '.join(comp[:3])+'와 비교해 차이를 확인' if comp else '최근 DART 공시와 실제 집행 내용을 확인'}"]
    candidates.append({'kind':'전략 변화','score':84+min(10,len(sig)*2)+min(6,len(ds)*2),'headline':headline,'why':f"한 회사에서 서로 다른 사업 신호가 동시에 움직여 단일 뉴스보다 전략 변화로 볼 근거가 생긴 후보.",'lines':lines,'questions':['이번 변화는 기존 중장기 계획에서 무엇이 달라진 것인가?','경쟁사도 같은 방향으로 움직이는가?','투자 확대가 실제 매출·생산능력·수익성으로 이어지는가?'],'company':c,'category':cat,'numbers':nums_all[:6],'sources':list(dict.fromkeys(x.get('sourceName') for x in rel[:4] if x.get('sourceName'))),'global':global_related(c,cat)})

# 3) global -> domestic linkage
for c in sorted({cc for x in items if not x.get('global') for cc in companies(x)}):
    news=recent_news(c,30); cat=(news[0].get('category') if news else None) or '산업'; gl=global_related(c,cat)
    if not gl or not news: continue
    gtext=' '.join(str(g.get('title') or '') for g in gl).lower(); local= ' '.join(text(x) for x in news[:8]).lower()
    if not any(k in gtext for k in ('tariff','grid','transformer','cable','steel','battery','automotive','renewable','wind','data center','supplier')): continue
    sig=set().union(*(sigs(text(x)) for x in news[:8]));
    headline=f"글로벌 변화 커지는데…{c}, 국내 사업·수주 영향은"
    if '관세' in gtext and '완성차' in cat: headline=f"美 관세 변수 커지는데…{c}의 현지 생산 대응은"
    elif cat=='전력기기': headline=f"글로벌 전력망 투자 확대…{c}, 수주·증설 어디까지 왔나"
    elif cat=='철강': headline=f"글로벌 철강 통상장벽 높아진다…{c}, 수출전략 바뀌나"
    lines=[f"해외 주요 매체에서 {gl[0].get('title','관련 변화')} 보도",f"국내에서 {c}의 최근 {', '.join(sorted(sig)[:3]) or '사업'} 움직임 확인",f"해외 변화가 {c}의 생산·수주·투자에 미치는 실제 영향을 국내 자료와 대조"]
    candidates.append({'kind':'글로벌→국내','score':78+min(12,len(gl)*4)+min(6,len(sig)*2),'headline':headline,'why':f"해외 산업 변화와 국내 기업의 최근 움직임을 연결해 국내 기사로 확장할 수 있는 후보.",'lines':lines,'questions':['해외 변화가 국내 기업의 실제 수주·가격·생산에 반영됐나?','경쟁사와 비교하면 대응 속도가 빠른가?'],'company':c,'category':cat,'numbers':list(dict.fromkeys([n for x in news for n in nums(text(x))]))[:5],'sources':[x.get('sourceName') for x in gl[:2] if x.get('sourceName')]+list(dict.fromkeys(x.get('sourceName') for x in news[:2] if x.get('sourceName'))),'global':gl})

# Deduplicate by company + headline meaning; prioritize stronger candidates and keep category diversity
seen=set(); final=[]
for c in sorted(candidates,key=lambda x:(x['score'],len(x['numbers']),len(x['sources'])),reverse=True):
    key=(c['company'],c['kind'])
    if key in seen: continue
    seen.add(key); final.append(c)
    if len(final)>=8: break

# Prefer at least one auto item when available, then top 5.
auto=[x for x in final if x['company'] in sum(COMPETITORS.values(),[])]
final=final[:5]
if auto and not any(x['company'] in sum(COMPETITORS.values(),[]) for x in final):
    final[-1]=auto[0]

OUT.write_text(json.dumps({'generatedAt':now.isoformat(),'items':final,'rule':'DART uncovered numbers + multi-signal strategy changes + global-to-domestic linkage. Events excluded; candidate only, verify originals before reporting.'},ensure_ascii=False,indent=2),encoding='utf-8')
print(f'investigation radar: {len(final)} items')
