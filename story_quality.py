import json,re

def quality(items):
    for x in items:
        score=int(x.get('score') or 0); reasons=[]
        cross=x.get('crossSource') or []
        comps=x.get('comparisons') or []
        inv=x.get('investigation') or {}
        verified=bool(x.get('documentVerified'))
        confidence=float(x.get('comparisonConfidence') or 0)
        # A public release is never an S-grade scoop by itself.
        strong_change=(bool(comps) and confidence>=75 and bool(cross) and verified)
        x['standaloneEligible']=bool(strong_change)
        if strong_change:
            reasons.append('과거 수치 변화 + 교차자료 + 첨부문서 검증을 모두 확인')
        if cross:
            score+=min(8,len(cross)*2);reasons.append('서울시·타 자치구 교차자료 존재')
        found=set(inv.get('pipelineFound',[]))
        if '계약' in found and '변경계약' in found:
            score+=6;reasons.append('계약→변경계약 흐름 확인')
        if '감사' in found:
            score+=8;reasons.append('감사자료 연결')
        if '회의' in found:
            score+=4;reasons.append('회의자료 연결')
        if verified:
            score+=4;reasons.append('첨부문서 본문 분석 완료')
        x['score']=min(100,score)
        x['qualityReasons']=reasons
        if strong_change and x['score']>=85:
            x['level']='S'
        elif x['score']>=70:
            x['level']='A'
        else:
            x['level']='follow' if x.get('level')=='follow' else 'B'
        x['why']=((' / '.join(reasons)+'. ') if reasons else '')+'공식자료 자체만으로 단독기사라고 판정하지 않습니다. '+x.get('why','')
    return items

raw=open('data.js',encoding='utf-8').read();items=json.loads(raw.split('=',1)[1].rstrip(' ;\n'));items=quality(items);open('data.js','w',encoding='utf-8').write('const ITEMS = '+json.dumps(items,ensure_ascii=False,separators=(',',':'))+';\n')
print('story quality scored',len(items),'items')
