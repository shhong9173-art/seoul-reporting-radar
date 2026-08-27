from __future__ import annotations
import json, re
from datetime import datetime, timezone, timedelta
from pathlib import Path

DATA = Path('data.json')
DART = Path('dart.json')
OUT = Path('strategic_shifts.json')
items = json.loads(DATA.read_text(encoding='utf-8')) if DATA.exists() else []
try:
    dart_doc = json.loads(DART.read_text(encoding='utf-8')) if DART.exists() else {'items': []}
except Exception:
    dart_doc = {'items': []}
dart_items = dart_doc.get('items', []) if isinstance(dart_doc, dict) else []
now = datetime.now(timezone.utc)
AUTO = {'완성차','부품','배터리','정책·관세','중국차','노조·생산','리콜·안전','수주·투자'}
IND = {'철강','비철금속','전력기기','전선·전력','에너지','재생에너지','화학·소재'}
NOISE = {'주가','주식','증권','목표주가','급등','급락','관련주','테마주','특징주'}
SIGNALS = {
    '투자': ['투자','출자','증설','CAPEX','신규법인','증자'],
    '생산': ['생산능력','가동','라인','공장','증산','감산'],
    '수주': ['수주','계약','납품','공급계약','수주잔고'],
    '가격·원가': ['가격','원가','마진','스프레드','관세','반덤핑'],
    '사업재편': ['철수','매각','재편','구조조정','거점축소','합병','분할','합작'],
    '기술·상용화': ['양산','상용화','개발','자율주행','로보택시','로봇','배터리','소재']
}
NUM_RE = re.compile(r'(?<!\d)(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?:조원|억원|만원|만대|천대|대|명|%|GWh|MWh|kWh|톤|km|MW|GW)(?!\w)', re.I)

def dt(x):
    raw = str(x.get('published') or x.get('date') or '').strip()
    try:
        value = datetime.fromisoformat(raw.replace('Z', '+00:00'))
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)

def company(x): return (x.get('companies') or [None])[0]
def text(x): return ' '.join(str(x.get(k) or '') for k in ('title','koTitle','summary','koSummary')).strip()
def numbers(x): return list(dict.fromkeys(NUM_RE.findall(text(x))))
def signals(x):
    t = text(x).lower()
    return [name for name, words in SIGNALS.items() if any(w.lower() in t for w in words)]
def relevant(x):
    if x.get('global') or company(x) is None or x.get('category') not in AUTO | IND: return False
    t = text(x).lower()
    return not any(n in t for n in NOISE)

recent = [x for x in items if relevant(x) and now - dt(x) <= timedelta(days=30)]
by_company = {}
for x in recent:
    c = company(x); row = by_company.setdefault(c, {'company': c,'categories':set(),'signals':set(),'numbers':set(),'sources':set(),'titles':[],'latest':x})
    row['categories'].add(x.get('category') or '산업'); row['signals'].update(signals(x)); row['numbers'].update(numbers(x))
    if x.get('sourceName'): row['sources'].add(x['sourceName'])
    if dt(x) > dt(row['latest']): row['latest'] = x
    if len(row['titles']) < 6: row['titles'].append(x.get('title') or x.get('koTitle') or '')

dart_by = {}
for d in dart_items:
    corp = str(d.get('corpName') or '').strip()
    if not corp or now - dt(d) > timedelta(days=45): continue
    dart_by.setdefault(corp, []).append(d)

candidates=[]
for c,row in by_company.items():
    darts=[]
    for name,vals in dart_by.items():
        if name==c or c in name or name in c: darts.extend(vals)
    dart_numbers=[]; dart_reports=[]
    for d in darts:
        report=str(d.get('reportName') or d.get('signalText') or '').strip()
        if report: dart_reports.append(report)
        for n in d.get('numbers') or []:
            s=str(n).strip()
            if s and s not in dart_numbers: dart_numbers.append(s)
    article_numbers=list(row['numbers']); uncovered=[n for n in dart_numbers if n not in article_numbers]; combined=list(dict.fromkeys(article_numbers+dart_numbers)); sig=row['signals']
    if not darts and len(sig)<3: continue
    score=0; reasons=[]
    if darts: score+=35; reasons.append('최근 DART 공시 확인')
    if len(sig)>=2: score+=25; reasons.append('서로 다른 사업 신호 동시 포착')
    if len(row['sources'])>=2: score+=15; reasons.append('복수 매체에서 변화 확인')
    if uncovered: score+=20; reasons.append('기사에서 아직 확인되지 않은 공시 숫자 존재')
    elif len(combined)>=3: score+=10; reasons.append('구체적 수치 다수 확인')
    if '사업재편' in sig: score+=10; reasons.append('사업재편 신호')
    score=min(100,score)
    if score<60: continue
    if '투자' in sig and '수주' in sig:
        headline=f'{c}, 수주 늘자 투자 확대…생산능력 따라가나'; angle=f'{c}의 수주 증가와 투자 확대가 실제 생산능력 확충으로 이어지는지 확인'
    elif '사업재편' in sig:
        headline=f'{c}, 사업재편 본격화…공장·투자 전략 어디로'; angle=f'{c}의 사업재편이 단순 비용 절감인지 실제 사업 포트폴리오 전환인지 확인'
    elif '가격·원가' in sig and '투자' in sig:
        headline=f'{c}, 원가 부담 속 투자 확대…수익성 방어 전략은'; angle=f'{c}의 투자 확대가 가격·원가 압박을 돌파하기 위한 전략인지 확인'
    elif '생산' in sig and '투자' in sig:
        headline=f'{c}, 생산능력 키운다…증설이 수익성으로 이어질까'; angle=f'{c}의 생산능력 확대가 실제 수요와 수익성 개선으로 이어지는지 확인'
    elif uncovered:
        headline=f'{c}, 공시에 새 숫자 나왔다…실제 투자·사업 변화는'; angle='DART에서 확인된 미보도 숫자가 기존 공개 계획과 실제 사업 집행의 차이를 보여주는지 확인'
    else:
        headline=f'{c}, 최근 사업 변화 확대…전략 전환 실체는'; angle=f'{c}에서 최근 나타난 사업 변화가 일시적 움직임인지 전략 전환인지 확인'
    latest=row['latest']
    candidates.append({'company':c,'category':sorted(row['categories'])[0] if row['categories'] else '산업','score':score,'headline':headline,'angle':angle,'signals':sorted(sig),'numbers':combined[:10],'uncoveredDartNumbers':uncovered[:10],'sources':sorted(row['sources']),'recentArticles':row['titles'],'latestTitle':latest.get('title') or latest.get('koTitle') or '','latestPublished':latest.get('published') or '','dartReports':list(dict.fromkeys(dart_reports))[:4],'dartNumbers':dart_numbers[:12],'reasons':reasons,'questions':['최근 30일 변화가 기존에 공개된 계획과 무엇이 다른가?','공시의 투자·생산·수주 숫자가 최근 기사에서 충분히 설명됐는가?','미보도 공시 숫자가 실제 생산능력·원가·수익성 변화와 연결되는가?','경쟁사에서도 같은 방향의 변화가 나타나는가?'],'detectedAt':now.isoformat(),'windowDays':30})

candidates.sort(key=lambda x:(bool(x['uncoveredDartNumbers']),x['score'],len(x['signals']),len(x['numbers'])),reverse=True)
final=[]; seen=set()
for x in candidates:
    if x['company'] in seen: continue
    seen.add(x['company']); final.append(x)
    if len(final)>=15: break
OUT.write_text(json.dumps({'generatedAt':now.isoformat(),'items':final,'sourceWindow':'30d-news-45d-dart','note':'최근 30일 뉴스와 최근 45일 DART를 결합한 전략 변화 및 미보도 숫자 후보. 발제 전 원문 확인 필요.'},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
print(f'strategic shift radar: {len(final)} candidates')