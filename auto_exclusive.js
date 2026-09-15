(function(){
  const AUTO_CATS=new Set(['완성차','부품','배터리','정책·관세','중국차','노조·생산','수주·투자','리콜·안전','단독','미국·글로벌']);
  const INDUSTRY_CATS=new Set(['철강','비철금속','전력기기','전선·전력','에너지','재생에너지','화학·소재']);
  const PATTERNS=[
    /(^|[\s\[\(])단독(?:보도|취재|입수|확인|인터뷰|공개)?(?=[:：\]\)\s]|$)/i,
    /본지\s*(?:단독|취재|취재결과)/i,
    /단독\s*(?:입수|확인|포착|취재|인터뷰)/i,
    /단독보도/i,
    /단독취재/i
  ];
  function explicit(x){
    if(!x || x.global || !PATTERNS.some(re=>re.test(x.title||''))) return false;
    return (!x.industrySource && AUTO_CATS.has(x.category)) || (x.industrySource && INDUSTRY_CATS.has(x.category));
  }
  function uniquePush(arr,x){if(!arr.some(v=>v.id===x.id))arr.push(x)}
  function apply(){
    const items=Array.isArray(window.ITEMS)?window.ITEMS:[];
    const autoEx=[], industryEx=[];
    items.forEach(x=>{
      if(explicit(x)){
        x.exclusive=true;
        x.exclusiveScore=Math.max(Number(x.exclusiveScore)||0,98);
        x.tags=Array.isArray(x.tags)?Array.from(new Set(x.tags.concat('단독'))):['단독'];
        x.priority='must';
        if(x.industrySource) uniquePush(industryEx,x); else uniquePush(autoEx,x);
      }
    });
    const autoNav=document.querySelector('.nav[data-view="must"]');
    if(autoNav){
      let el=autoNav.querySelector('#autoExclusiveCount');
      if(!el){el=document.createElement('span');el.id='autoExclusiveCount';el.className='auto-exclusive-count';autoNav.appendChild(el)}
      el.textContent=' · 단독 '+autoEx.length;
      el.title='최근 72시간 자동차 단독·취재 신호';
    }
    const industryNav=document.querySelector('.nav[data-view="industryMust"]');
    if(industryNav){
      let el=industryNav.querySelector('#industryExclusiveCount');
      if(!el){el=document.createElement('span');el.id='industryExclusiveCount';el.className='auto-exclusive-count';industryNav.appendChild(el)}
      el.textContent=' · 단독 '+industryEx.length;
      el.title='최근 72시간 산업부 단독·취재 신호';
    }
    const today=document.querySelector('#today');
    if(today){
      if(autoEx.length){
        const names=autoEx.slice(0,3).map(x=>x.sourceName).filter(Boolean);
        today.textContent='최근 72시간 자동차 단독·취재 신호 '+autoEx.length+'건'+(names.length?' · '+names.join(' · '):'')+' | 단독은 자동차 핵심 최상단에 우선 노출합니다.';
      }else if(/뉴스 데이터를 불러오는 중입니다|자동차는|산업부/.test(today.textContent||'')){
        today.textContent='최근 72시간 자동차 단독·취재 신호 0건 | 새 단독이 들어오면 자동차 핵심 최상단에 우선 노출합니다.';
      }
    }
    if(industryEx.length){
      const industryBtn=document.querySelector('.nav[data-view="industryMust"]');
      if(industryBtn) industryBtn.title='최근 72시간 산업부 단독·취재 신호 '+industryEx.length+'건';
    }
    const count=document.querySelector('#countMust');
    if(count){const n=items.filter(x=>!x.global&&!x.industrySource&&x.priority==='must').length;count.textContent=n;}
    if(typeof render==='function') render();
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',apply); else apply();
})();
