import json,re
from pathlib import Path

raw=Path('data.js').read_text(encoding='utf-8')
items=json.loads(raw.split('=',1)[1].strip().rstrip(';'))

STOP=set('자동차 현대차 기아 관련 업계 시장 올해 오늘 최근 밝혔다 따르면 대한 통해 위한 국내 글로벌 전기차 차량 기업 사업 계획 뉴스 기사'.split())

def toks(s):
    return {t for t in re.findall(r'[가-힣A-Za-z0-9]{2,}',(s or '').lower()) if t not in STOP and not t.isdigit()}

def numbers(s):
    return set(re.findall(r'(?<!\d)(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?:조원|억원|만원|억|조|만대|천대|대|명|%|GWh|MWh|kWh|톤|km)',s or '',re.I))

# Keep follow-up only when there is a real unanswered/new fact.
# Widespread stories with essentially the same headline are monitoring items, not follow-up pitches.
by_cluster={}
for x in items:
    if x.get('global'): continue
    by_cluster.setdefault(x.get('clusterId') or x.get('id'),[]).append(x)

kept_clusters=set()
for cid, group in by_cluster.items():
    group.sort(key=lambda x:x.get('published',''), reverse=True)
    if not group: continue
    # Candidate novelty is measured against the rest of the same issue cluster.
    all_other_tokens=set().union(*(toks(x.get('title','')+' '+x.get('summary','')) for x in group[1:])) if len(group)>1 else set()
    all_other_numbers=set().union(*(numbers(x.get('title','')+' '+x.get('summary','')) for x in group[1:])) if len(group)>1 else set()
    for x in group:
        company_count=len(x.get('companies') or [])
        title_tokens=toks(x.get('title',''))
        novel_tokens=title_tokens-all_other_tokens
        novel_numbers=numbers(x.get('title','')+' '+x.get('summary',''))-all_other_numbers
        spread=int(x.get('clusterCount') or len(group) or 1)
        # Existing exclusive/first-source signals are retained.
        if x.get('exclusive'):
            x['followUp']=False
            continue
        # A cluster with 3+ outlets is generally already saturated unless the newest item adds a concrete new fact.
        saturated=spread>=3
        concrete_new=len(novel_numbers)>=1 or len(novel_tokens)>=2
        strong_questions=any(k in (x.get('title','')+' '+x.get('summary','')) for k in ['금액','투자','증설','수주','계약','생산능력','가동','정확히','언제','어디','몇','관세','리콜','결함','화재','임단협','파업'])
        real_follow=(x.get('followUp') is True) and (not saturated or (concrete_new and strong_questions))
        if real_follow:
            if cid in kept_clusters:
                x['followUp']=False
                continue
            kept_clusters.add(cid)
            x['followUp']=True
            x['followScore']=min(95,max(60,int(x.get('followScore') or 0)+(10 if concrete_new else 0)))
            x['followReason']='기존 기사와 다른 구체적 확인 포인트가 있어 후속 취재 가치가 있습니다.' if concrete_new else '확산 전 단계의 이슈로 회사·공시·현장 확인 가치가 있습니다.'
        else:
            x['followUp']=False
            x['followScore']=min(45,int(x.get('followScore') or 45))
            x['followReason']='동일 이슈의 반복 보도가 많아 후속 후보에서 제외했습니다.'

Path('data.json').write_text(json.dumps(items,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
Path('data.js').write_text('window.ITEMS = '+json.dumps(items,ensure_ascii=False,separators=(',',':'))+';\n',encoding='utf-8')
print(f'follow-up filter: {sum(1 for x in items if x.get("followUp"))} retained')
