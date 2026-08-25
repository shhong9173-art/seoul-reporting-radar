from __future__ import annotations
import json,re
from pathlib import Path

DATA=Path('data.json'); DATA_JS=Path('data.js'); IND=Path('industry.json')
if not DATA.exists() or not IND.exists(): raise SystemExit('data.json or industry.json missing')
base=json.loads(DATA.read_text(encoding='utf-8')); ind=json.loads(IND.read_text(encoding='utf-8')).get('items',[])
merged=list(base); seen={(x.get('sourceName'),x.get('title')) for x in base}

# Industry desk should be selective: retain the full feed, but only promote concrete/high-impact items.
POS=['수주','계약','공급','증설','투자','공장','생산중단','가동','감산','철수','매각','인수','합작','관세','반덤핑','통상','가격','원가','마진','LME','전력망','변압기','HVDC','해저케이블','해상풍력','풍력','태양광','구조조정','스페셜티','미국','중국','유럽','북미']
NEG=['주가','증권','목표주가','급등','급락','추천','전망만','관련주','테마주','주목할 종목','특징주','오전장','장중']
COMPANY_WORDS=['포스코','포스코홀딩스','현대제철','동국제강','세아제강','고려아연','영풍','LS MnM','풍산','두산에너빌리티','HD현대일렉트릭','LS ELECTRIC','효성중공업','일진전기','LS전선','대한전선','가온전선','대원전선','GS칼텍스','GS','한화솔루션','OCI홀딩스','씨에스윈드','LG화학','롯데케미칼','금호석유화학','효성첨단소재','코오롱인더']

def score(x):
    text=(x.get('title','')+' '+x.get('summary','')).lower()
    p=sum(1 for w in POS if w.lower() in text)
    n=sum(1 for w in NEG if w.lower() in text)
    c=sum(1 for w in COMPANY_WORDS if w.lower() in text)
    concrete=0
    if re.search(r'\d[\d,.]*\s*(조|억|만|천)?원',text): concrete+=3
    if re.search(r'\d+(?:\.\d+)?\s*%',text): concrete+=2
    if re.search(r'\d[\d,.]*\s*(만대|천대|대|톤|GWh|MWh|km)',text,re.I): concrete+=2
    return max(0,min(99,45+p*5+c*4+concrete*5-n*10))

for x in ind:
    sig=(x.get('sourceName'),x.get('title'))
    if sig in seen: continue
    x['score']=score(x)
    x['priority']='follow' if x['score']>=75 else 'normal'
    x['industryRelevant']=x['score']>=70
    x['tags']=list(dict.fromkeys([x.get('category','산업')] + (['주요기업'] if x.get('companies') else [])))
    x.setdefault('companies',[]); x.setdefault('global',False); x.setdefault('summary','')
    x['pitchScore']=x['score']; x['pitchReasons']=['구체적 산업 이벤트·기업 신호'] if x['score']>=70 else ['산업 동향 모니터링']
    merged.append(x); seen.add(sig)
merged.sort(key=lambda x:x.get('published',''), reverse=True)
DATA.write_text(json.dumps(merged,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
DATA_JS.write_text('window.ITEMS = '+json.dumps(merged,ensure_ascii=False,separators=(',',':'))+';\n',encoding='utf-8')
print(f'merged industrial radar: +{len(merged)-len(base)} / relevant {sum(1 for x in ind if x.get("industryRelevant"))} / total {len(merged)}')
