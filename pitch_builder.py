from __future__ import annotations
import json,re
from pathlib import Path
from datetime import datetime, timezone, timedelta

DATA=Path('data.json')
DART=Path('dart.json')
NUM=Path('dart_numeric.json')
OUT=Path('pitch.json')

items=json.loads(DATA.read_text(encoding='utf-8')) if DATA.exists() else []
dart=json.loads(DART.read_text(encoding='utf-8')).get('items',[]) if DART.exists() else []
numeric=json.loads(NUM.read_text(encoding='utf-8')).get('items',[]) if NUM.exists() else []

GENERIC=set('자동차 현대차 기아 배터리 전기차 관련 업계 시장 최근 오늘 미국 한국 중국 차량 회사 산업 기업 뉴스 기사 전망 올해 지난해 국내 해외'.split())
NOISE=set('주가 주식 증권 목표주가 투자자 리서치센터 급등 급락 추천'.split())
SPECIFIC=set('슈퍼널 모셔널 아이오닉5 아이오닉 아이오닉6 로보택시 AAM ESS LFP FC-BGA 전고체 샤힌프로젝트 북미 라스베이거스 멕시코 캐나다 울산 대산 여수 중국 유럽 미국'.lower().split())
MATERIAL_UNITS=re.compile(r'(?<!\d)(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?:조원|억원|만원|억|조|만대|천대|대|명|%|GWh|MWh|kWh|톤|km)(?!\w)',re.I)
DATE_NOISE=re.compile(r'\b(?:19|20)\d{2}[./-]\d{1,2}[./-]\d{1,2}\b|\b(?:19|20)\d{2}년\b')

THEMES={
 'investment':['투자','시설투자','출자','유상증자','증설','capex','funding'],
 'production':['생산','생산능력','공장','라인','가동','증설','production','capacity','plant'],
 'restructure':['감원','인력감축','축소','철수','조직개편','거점축소','재편','layoff','restructure'],
 'order':['수주','계약','납품','공급','order','contract'],
 'tariff':['관세','통상','공급망','tariff','trade','supply chain'],
 'ev_ess':['ESS','에너지저장','EV battery','storage','전환'],
 'mobility':['AAM','로보택시','자율주행','모셔널','슈퍼널','모빌리티'],
 'sales':['판매','출하','인도량','점유율','sales','deliveries','share'],
 'labor':['임금','임협','노조','파업','노사','wage','union','strike'],
 'product':['신차','출시','양산','모델','차종','product','launch','model'],
 'asset_sale':['매각','처분','지분양도','타법인주식','sell','divestment'],
}

def title(x):
    return (x.get('koTitle') if x.get('global') and x.get('koTitle') else x.get('title','')).strip()

def text(x):
    return ' '.join(str(v or '') for v in (title(x),x.get('summary',''),x.get('koSummary','')))

def toks(s):
    return set(re.findall(r'[가-힣A-Za-z0-9]{2,}',s.lower()))

def clean_tokens(s):
    return toks(s)-GENERIC-NOISE

def material_numbers(s):
    vals=[]
    for m in MATERIAL_UNITS.findall(s or ''):
        v=m.replace(' ','')
        if not DATE_NOISE.search(v): vals.append(v)
    return list(dict.fromkeys(vals))

def theme_set(s):
    low=(s or '').lower()
    return {k for k,ws in THEMES.items() if any(w.lower() in low for w in ws)}

def company_names(x):
    return [c for c in (x.get('companies') or []) if c and c not in NOISE]

def source_name(x): return str(x.get('sourceName') or '').strip()

def pubdt(x):
    try: return datetime.fromisoformat(str(x.get('published','')).replace('Z','+00:00'))
    except Exception: return datetime.now(timezone.utc)

def dart_key(c):
    return {'현대차':'현대자동차','한국타이어':'한국타이어앤테크놀로지'}.get(c,c)

def dart_company_rows(c): return [r for r in dart if r.get('corpName')==dart_key(c)]
def numeric_company_rows(c): return [r for r in numeric if r.get('corpName')==dart_key(c) and r.get('numbers')]

def dart_materials(row):
    out=[]
    for n in row.get('numbers') or []:
        if MATERIAL_UNITS.search(n) and not DATE_NOISE.search(n): out.append(n)
    return list(dict.fromkeys(out))

def strong_overlap(a,b):
    inter=clean_tokens(title(a)) & clean_tokens(title(b))
    return {t for t in inter if t in SPECIFIC or len(t)>=4}

def recent_news(company, days=7):
    cutoff=datetime.now(timezone.utc)-timedelta(days=days)
    return [x for x in items if company in company_names(x) and pubdt(x)>=cutoff]

def already_explicitly_reported(amount, company, news):
    if not amount: return False
    return any(amount in text(x) for x in news)

def build_dart_led():
    cands=[]
    for r in numeric:
        corp=r.get('corpName')
        if not corp or not r.get('numbers'): continue
        mats=dart_materials(r)
        if not mats: continue
        report=str(r.get('reportName') or '')
        corp_news=recent_news(corp)
        # Keep only materially interesting disclosure families.
        if not any(k in report for k in ('시설투자','출자','유상증자','타법인','지분','생산중단','영업양수도','합병','분할','주요사항','사업보고서','반기보고서','분기보고서')):
            continue
        exact_coverage=any(already_explicitly_reported(m,corp,corp_news) for m in mats)
        # Need either a fresh disclosure not covered by news, or a disclosure that changes a live business story.
        if exact_coverage and not ('생산중단' in report or '타법인' in report or '시설투자' in report):
            continue
        snippets=' '.join(s.get('context','') for s in (r.get('snippets') or []))
        sn_text=(report+' '+snippets)
        t=theme_set(sn_text)
        news_themes=set(); specific=set()
        for n in corp_news[:25]:
            news_themes |= theme_set(text(n))
            specific |= (clean_tokens(title(n)) & SPECIFIC)
        # Avoid inventing a linkage: require either explicit material disclosure or a concrete shared signal.
        if not exact_coverage and mats:
            confidence=84
        else:
            confidence=78
        if specific: confidence += 5
        if len(corp_news)>=2: confidence += 4
        if '생산중단' in report and mats: confidence += 4
        confidence=min(96,confidence)
        if confidence < 86 and not (not exact_coverage and mats): continue

        if '타법인' in report or '지분' in report or '양도' in report:
            action='처분·출자 금액이 실제로 어디로 재배치되는지 확인'
        elif '시설투자' in report or '공장' in sn_text:
            action='투자금액이 어느 공장·생산라인·지역에 실제 집행되는지 확인'
        elif '생산중단' in report:
            action='생산중단이 생산량·매출·납기·가동일수에 미친 실제 영향을 확인'
        else:
            action='공시 수치가 기존 사업계획과 어떻게 달라졌는지 확인'

        if '생산중단' in report:
            headline=f'{corp}, 생산중단 영향 가시화…공시상 매출 기준 {mats[0]} 규모 사업에 차질'
        elif '타법인' in report or '지분' in report:
            headline=f'{corp}, {mats[0]} 규모 자산·지분 거래…공시가 밝힌 자금 활용처는'
        elif '시설투자' in report:
            headline=f'{corp}, {mats[0]} 시설투자…어디에 얼마나 집행하나'
        else:
            headline=f'{corp}, 공시에서 드러난 {mats[0]} 규모 변화…기존 계획과 달라졌나'

        evidence=[]
        if r.get('url'): evidence.append({'source':'DART','title':report,'url':r.get('url'),'published':r.get('date'),'numbers':mats[:8]})
        for n in corp_news[:4]:
            evidence.append({'source':source_name(n),'title':title(n),'url':n.get('url'),'published':n.get('published'),'numbers':material_numbers(text(n))[:5]})

        cands.append({
            'type':'dart-led','grade':'A' if confidence>=90 and not exact_coverage else 'B','pitchScore':confidence,
            'headline':headline,'category':(corp_news[0].get('category') if corp_news else '산업'),'companies':[corp],
            'angle':action,'newFact':f'DART {report}에서 {", ".join(mats[:5])} 규모의 수치가 확인됨.',
            'differentiator':'공시 원문 수치와 기존 기사 보도 범위를 대조해 새로 확인할 사실을 찾는 아이템.',
            'whyNow':'최근 7일 공시와 기사 흐름을 교차해 현재 시점에서 추가 취재 가치가 있는지 선별.',
            'numbers':mats[:8],'sourceCount':len({e['source'] for e in evidence}),'globalSignals':sum(1 for n in corp_news if n.get('global')),
            'domesticSignals':sum(1 for n in corp_news if not n.get('global')),'sources':sorted({e['source'] for e in evidence if e.get('source')}),
            'evidence':evidence[:6],'dartSignals':dart_company_rows(corp)[:6],'dartNumericSignals':[r],
            'dartNumericCount':len(mats),'questions':['공시 수치와 최근 기사 숫자가 정확히 일치하는지 대조','해당 거래·투자가 전년 또는 직전 계획 대비 얼마나 달라졌는지 확인','회사 공식 설명 외에 실제 자금·생산·인력 변화가 있는지 확인','아직 기사화되지 않은 후속 숫자·일정이 있는지 확인'],
            'rawSignals':[report]+[title(n) for n in corp_news[:3]]
        })
    return cands

def build_cross_source():
    cands=[]
    by_company={}
    for x in items:
        for c in company_names(x): by_company.setdefault(c,[]).append(x)
    for company,arr in by_company.items():
        arr=sorted(arr,key=pubdt,reverse=True)[:40]
        for i,a in enumerate(arr):
            for b in arr[i+1:]:
                if source_name(a)==source_name(b): continue
                ov=strong_overlap(a,b)
                if not ov: continue
                ta,tb=theme_set(text(a)),theme_set(text(b))
                # Only create a new angle when the two sources cover meaningfully different themes.
                if ta==tb or not (ta-tb or tb-ta): continue
                ns=list(dict.fromkeys(material_numbers(text(a))+material_numbers(text(b))))
                if not ns: continue
                # Cross-source item must either be domestic+global or have a concrete third-party DART check.
                dom=[x for x in (a,b) if not x.get('global')]; glob=[x for x in (a,b) if x.get('global')]
                dr=numeric_company_rows(company)
                if not (dom and glob) and not dr: continue
                dart_match=[]
                for r in dr:
                    ctxt=(str(r.get('reportName') or '')+' '+' '.join(s.get('context','') for s in (r.get('snippets') or []))).lower()
                    if ov & set(re.findall(r'[가-힣A-Za-z0-9]{2,}',ctxt)):
                        dart_match.append(r)
                # Strong only when third-party fact corroborates the relationship.
                if not dart_match and not (dom and glob): continue
                score=86 + (5 if dom and glob else 0) + (4 if len(ov)>=2 else 0) + (4 if dart_match else 0)
                score=min(97,score)
                headline=f'{company}, {"·".join(sorted(ov)[:2])} 관련 움직임 엇갈려…실제 사업 변화 확인'
                cands.append({
                    'type':'cross-source','grade':'A' if score>=93 and dart_match else 'B','pitchScore':score,
                    'headline':headline,'category':a.get('category') or b.get('category') or '산업','companies':[company],
                    'angle':'서로 다른 출처에서 확인된 별개의 움직임이 실제 같은 사업 변화로 연결되는지 검증.',
                    'newFact':f'{len({source_name(a),source_name(b)})}개 출처에서 {", ".join(sorted(ov)[:4])} 공통 신호와 서로 다른 사업 테마가 확인됨.',
                    'differentiator':'단순 기사 요약이 아니라 서로 다른 사실의 연결 여부 자체를 취재 대상으로 삼음.',
                    'whyNow':'최근 기사 흐름과 글로벌/공시 신호를 함께 비교할 수 있는 시점.',
                    'numbers':ns[:8],'sourceCount':2,'globalSignals':len(glob),'domesticSignals':len(dom),
                    'sources':sorted({source_name(a),source_name(b)}),
                    'evidence':[{'source':source_name(a),'title':title(a),'url':a.get('url'),'published':a.get('published'),'numbers':material_numbers(text(a))[:5]},{'source':source_name(b),'title':title(b),'url':b.get('url'),'published':b.get('published'),'numbers':material_numbers(text(b))[:5]}],
                    'dartSignals':dr[:4],'dartNumericSignals':dart_match[:4],'dartNumericCount':sum(len(r.get('numbers') or []) for r in dart_match),
                    'questions':['두 기사에서 말하는 사업·제품·공장이 실제 동일한 대상을 가리키는지 확인','DART·IR·사업보고서에서 관련 숫자를 대조','회사 설명과 실제 집행·생산·인력 변화가 같은지 확인','경쟁사 대비 차별화된 움직임인지 확인'],
                    'rawSignals':[title(a),title(b)]
                })
    return cands

candidates=build_dart_led()+build_cross_source()
# Remove near-duplicates and suppress weak B items. The system may legitimately return zero.
candidates.sort(key=lambda x:(x['grade']=='A',x['pitchScore'],x.get('dartNumericCount',0),x.get('globalSignals',0),x.get('sourceCount',0)),reverse=True)
final=[];seen=set()
for p in candidates:
    sig=(tuple(p.get('companies',[])),p.get('headline','')[:30],tuple(p.get('numbers',[])[:2]))
    if sig in seen: continue
    seen.add(sig); final.append(p)
    if len(final)>=6: break

OUT.write_text(json.dumps(final,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
print(f'pitch builder: {len(final)} items / A-grade={sum(1 for x in final if x.get("grade")=="A")} / DART-led={sum(1 for x in final if x.get("type")=="dart-led")}')
