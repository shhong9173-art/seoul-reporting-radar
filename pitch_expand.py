from __future__ import annotations
import json,re
from pathlib import Path
from datetime import datetime, timezone, timedelta

DATA=Path('data.json'); OUT=Path('pitch.json')
items=json.loads(DATA.read_text(encoding='utf-8')) if DATA.exists() else []
base=json.loads(OUT.read_text(encoding='utf-8')) if OUT.exists() else []

AUTO=set(['완성차','부품','배터리','정책·관세','중국차','노조·생산','리콜·안전','수주·투자','단독','미국·글로벌'])
INDUSTRY=set(['철강','비철금속','전력기기','전선·전력','에너지','재생에너지','화학·소재'])
NOISE={'주가','증권','목표주가','추천주','관련주','테마주','급등','급락','주목할 종목','전망'}
GENERIC={'관련','업계','시장','최근','오늘','올해','지난해','국내','글로벌','사업','기업','회사','계획','전망','대한','통해','위한','기자','보도','밝혀','따르면'}
STRATEGY={
 '투자':['투자','시설투자','출자','유상증자','증설','capex'],
 '생산':['생산','생산능력','공장','라인','가동','양산','감산','생산중단'],
 '포트폴리오':['전환','재편','사업개편','구조조정','철수','매각','인수','합병','스페셜티'],
 '수주':['수주','계약','공급','납품','고객사'],
 '통상':['관세','반덤핑','통상','공급망','미국','중국','유럽'],
 '가격·원가':['가격','원가','마진','정제마진','LME','구리','아연','니켈'],
 '기술':['자율주행','로보택시','AAM','ESS','PIM','CXL','HBM','HVDC','해저케이블','해상풍력','풍력','태양광']
}
NUMBER_RE=re.compile(r'(?<!\d)(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?:조원|억원|만원|억|조|만대|천대|대|명|%|GWh|MWh|kWh|톤|km|MW|GW)(?!\w)',re.I)

def title(x): return str(x.get('koTitle') if x.get('global') and x.get('koTitle') else x.get('title','')).strip()
def text(x): return ' '.join(str(v or '') for v in (title(x),x.get('summary',''),x.get('koSummary','')))
def companies(x): return [c for c in (x.get('companies') or []) if c]
def nums(s): return list(dict.fromkeys(NUMBER_RE.findall(s or '')))
def themes(s):
    low=(s or '').lower(); return {k for k,ws in STRATEGY.items() if any(w.lower() in low for w in ws)}
def pubdt(x):
    try:return datetime.fromisoformat(str(x.get('published','')).replace('Z','+00:00'))
    except:return datetime.now(timezone.utc)
def toks(s): return set(re.findall(r'[가-힣A-Za-z0-9]{2,}',(s or '').lower()))-GENERIC-NOISE

def strong_seed(x):
    if x.get('global'): return False
    cat=x.get('category')
    if cat not in AUTO and cat not in INDUSTRY and not x.get('industrySource'): return False
    if x.get('score',0)<78: return False
    t=text(x)
    if any(n in t for n in NOISE): return False
    ts=themes(t); ns=nums(t)
    return len(ts)>=1 and (bool(ns) or len(ts)>=2 or x.get('clusterCount',1)>=2)

def related_articles(seed, window_days=7):
    cs=set(companies(seed)); cutoff=pubdt(seed)-timedelta(days=window_days)
    out=[]
    for x in items:
        if x.get('global'): continue
        if pubdt(x)<cutoff or pubdt(x)>pubdt(seed)+timedelta(hours=12): continue
        if cs and cs.intersection(companies(x)): out.append(x)
    return sorted(out,key=pubdt,reverse=True)

def build_strategy(seed):
    t=text(seed); ts=themes(t); ns=nums(t); cs=companies(seed); cat=seed.get('category') or ('산업부' if seed.get('industrySource') else '자동차')
    related=related_articles(seed)
    related_text=' '.join(text(r) for r in related[:12])
    related_numbers=set(nums(related_text))
    fresh_numbers=[n for n in ns if n not in related_numbers]

    if cat=='철강':
        headline=f"{cs[0] if cs else '철강업계'}, 생산·가격 변화 본격화…중국산·관세가 전략 바꾸나"
        angle='중국산·가격·관세 변화가 국내 생산·가동률·제품 믹스에 어떤 변화를 만드는지 확인'
        plan=['최근 철강 가격·중국 공급량·관세 변화를 수치로 정리','고로·전기로·압연라인의 감산·증설·가동률 변화를 확인','주요 업체의 제품 믹스와 수익성 변화로 연결']
    elif cat=='비철금속':
        headline=f"{cs[0] if cs else '비철금속업계'}, 금속가격·제련 전략 변화…수익성 어디서 갈리나"
        angle='국제 금속가격과 제련·원료 확보 변화가 실제 수익성과 생산전략을 어떻게 바꾸는지 확인'
        plan=['LME 가격과 원료·제련 조건 변화 확인','제련·생산능력·가동률 및 투자 변화를 대조','중국 공급망 및 해외 자산 확보 전략 변화 확인']
    elif cat=='전력기기':
        headline=f"{cs[0] if cs else '전력기기업계'}, 북미 수주 늘자 증설 본격화…생산능력 얼마나 커지나"
        angle='미국 전력망·데이터센터 수요가 국내 전력기기 업체의 수주잔고·증설·북미 전략으로 어떻게 이어지는지 확인'
        plan=['수주 규모와 수주잔고 증가폭을 전년 대비 비교','변압기·차단기·HVDC 등 어느 제품에서 증설이 일어나는지 확인','미국 현지 생산·공장 투자와 매출 인식 시점을 확인']
    elif cat=='전선·전력':
        headline=f"{cs[0] if cs else '전선업계'}, 해저케이블·HVDC 수주 확대…생산거점도 바뀌나"
        angle='해저케이블·HVDC 수요 증가가 실제 공장 증설·수주잔고·북미 생산거점 변화로 이어지는지 확인'
        plan=['수주액·공급 대상·계약기간 확인','국내외 생산능력과 증설 규모 비교','북미·유럽 프로젝트 확보가 수익성에 미치는 영향 확인']
    elif cat=='에너지':
        headline=f"{cs[0] if cs else '에너지업계'}, 투자 방향 전환…기존 사업과 신규 성장축 격차 커지나"
        angle='두산에너빌리티·GS·GS칼텍스·풍력 사업의 투자 방향이 에너지 사업 포트폴리오를 어떻게 바꾸는지 확인'
        plan=['최근 투자·수주·프로젝트 확보 규모 확인','기존 사업 대비 신규 사업 비중 변화 확인','프로젝트 착공·가동 일정과 수익성 전환 시점 확인']
    elif cat=='재생에너지':
        headline=f"{cs[0] if cs else '재생에너지업계'}, 프로젝트 확대 본격화…수익성 개선으로 이어지나"
        angle='재생에너지 확대가 실제 프로젝트·생산능력·수익성 개선으로 이어지고 있는지 확인'
        plan=['프로젝트 수·규모·착공 일정 확인','생산능력·수주잔고·원가 구조 변화 대조','미국·유럽 정책 변화가 국내 기업 투자전략에 미치는 영향 확인']
    elif cat=='화학·소재':
        headline=f"{cs[0] if cs else '화학·소재업계'}, 구조조정 넘어 스페셜티 전환…투자축 어디로"
        angle='중국 공급과잉·가동률 저하 속에서 화학·소재 업체가 범용 제품에서 어디로 사업을 옮기는지 확인'
        plan=['가동률·가격·스프레드 변화 확인','감산·매각·구조조정과 증설 움직임을 비교','스페셜티·첨단소재 전환의 투자액과 매출 기여도 확인']
    else:
        if '투자' in ts and '생산' in ts:
            headline=f"{cs[0] if cs else cat}, 투자·생산 축 이동…실제 사업전략 바뀌나"
            angle='투자 확대와 생산능력 변화가 실제 사업전략 전환으로 이어지는지 확인'
            plan=['투자액·증설 규모를 기존 계획과 비교','공장·라인·가동 시점 확인','생산능력 변화가 판매·수주·수익성에 미치는 영향 확인']
        elif '포트폴리오' in ts:
            headline=f"{cs[0] if cs else cat}, 사업 재편 본격화…무엇을 줄이고 어디에 집중하나"
            angle='회사의 사업 포트폴리오 재편이 실제 자본·생산·인력 배분 변화로 이어지는지 확인'
            plan=['줄이는 사업과 키우는 사업을 구분','투자·매각·감원 등 실행 수단 확인','재편 이후 매출·생산·수익성 목표 확인']
        elif '수주' in ts and ('투자' in ts or '생산' in ts):
            headline=f"{cs[0] if cs else cat}, 수주 늘자 증설 본격화…생산능력 얼마나 커지나"
            angle='수주 증가가 실제 생산능력·투자·매출 확대로 이어지는지 확인'
            plan=['수주액·고객·기간 확인','증설 및 생산능력 변화 확인','매출 인식과 손익 기여 시점 확인']
        elif '통상' in ts:
            headline=f"{cs[0] if cs else cat}, 관세·공급망 변화에 대응…생산·조달전략 바뀌나"
            angle='관세와 공급망 변화가 실제 생산·조달·거점 전략을 바꾸는지 확인'
            plan=['관세 적용범위와 원가 영향 확인','생산·조달 거점 변화 확인','가격 전가와 수익성 영향을 확인']
        else:
            headline=title(seed)
            angle='최근 숫자와 사업 움직임을 연결해 실제 전략 변화 여부를 확인'
            plan=['새로 확인된 숫자를 기존 계획과 대조','생산·투자·수주 중 실제 행동 변화를 확인','경쟁사 대비 전략 차이를 확인']

    new_fact=f"새 숫자 {', '.join(fresh_numbers[:4])}이 확인됐다." if fresh_numbers else '최근 보도·공시에서 전략 변화 신호가 겹친다.'
    evidence=[{'source':seed.get('sourceName','-'),'title':title(seed),'url':seed.get('url'),'published':seed.get('published'),'numbers':ns[:6]}]
    for r in related[:4]:
        if r.get('url')!=seed.get('url'):
            evidence.append({'source':r.get('sourceName','-'),'title':title(r),'url':r.get('url'),'published':r.get('published'),'numbers':nums(text(r))[:5]})
    score=min(96,max(84,(seed.get('score') or 78)+5+min(8,len(fresh_numbers)*2)+min(6,len(related))))
    return {
      'type':'strategy-led','grade':'A' if score>=91 else 'B','pitchScore':score,
      'headline':headline,'category':cat,'companies':cs,'angle':angle,
      'newFact':new_fact,'differentiator':'단일 기사 요약이 아니라 투자·생산·수주·가격·통상 등 서로 다른 신호를 연결해 전략 변화 여부를 취재 대상으로 삼는다.',
      'whyNow':f"최근 {seed.get('sourceName','기사')}의 변화가 실제 사업행동으로 이어지는지 확인할 시점.",
      'numbers':list(dict.fromkeys(ns+fresh_numbers))[:8],
      'sourceCount':len({e['source'] for e in evidence if e.get('source')}),'globalSignals':0,'domesticSignals':len(evidence),
      'sources':sorted({e['source'] for e in evidence if e.get('source')}),'evidence':evidence[:6],
      'articlePlan':plan,
      'reportingBrief':[f"{seed.get('sourceName','-')} · {title(seed)}",f"관련 전략 신호 {', '.join(sorted(ts))}"]+([f"새 숫자 {', '.join(fresh_numbers[:4])}"] if fresh_numbers else []),
      'questions':['기존 계획·전년 대비 실제로 달라진 숫자는 무엇인가?','회사 내부에서 바뀐 투자·생산·수주 계획은 무엇인가?','이 변화가 언제 매출·생산·수익성에 반영되는가?','경쟁사와 비교해 같은 변화가 나타나는가?'],
      'rawSignals':[title(seed)]+[title(r) for r in related[:3]]
    }

# Keep only strategy/industry-oriented legacy candidates; event-led candidates are intentionally discarded.
kept=[]
for p in base:
    if p.get('type')=='event-led': continue
    if p.get('type') not in {'dart-led','cross-source','strategy-led'}: continue
    p['type']='strategy-led'
    kept.append(p)

new=[build_strategy(x) for x in items if strong_seed(x)]

allp=kept+new
allp.sort(key=lambda x:(x.get('grade')=='A',x.get('pitchScore',0),x.get('sourceCount',0),len(x.get('numbers',[]))),reverse=True)
final=[]
for p in allp:
    ps=toks(p.get('headline','')+' '+' '.join(p.get('companies',[])))
    dup=False
    for q in final:
        common=set(p.get('companies',[])) & set(q.get('companies',[]))
        qs=toks(q.get('headline','')+' '+' '.join(q.get('companies',[])))
        sim=len(ps&qs)/max(1,len(ps|qs))
        if common and sim>=0.45:
            dup=True; break
    if not dup: final.append(p)
    if len(final)>=8: break

OUT.write_text(json.dumps(final,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
print(f'pitch strategy/industry: seeds={len(new)} kept={len(kept)} final={len(final)} A={sum(1 for x in final if x.get("grade")=="A")}')
