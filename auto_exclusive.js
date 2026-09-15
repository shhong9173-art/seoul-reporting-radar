(function(){
  const AUTO_CATS=new Set(['완성차','부품','배터리','정책·관세','중국차','노조·생산','수주·투자','리콜·안전','단독','미국·글로벌']);
  const PATTERNS=[
    /(^|[\s\[\(])단독(?:보도|취재|입수|확인|인터뷰|공개)?(?=[:：\]\)\s]|$)/i,
    /본지\s*(?:단독|취재|취재결과)/i,
    /단독\s*(?:입수|확인|포착|취재|인터뷰)/i,
    /단독보도/i,
    /단독취재/i
  ];
  function text(x){return ((x.title||'')+' '+(x.summary||'')).replace(/\s+/g,' ')}
  function explicit(x){
    if(!x || x.global || x.industrySource || !AUTO_CATS.has(x.category)) return false;
    const title=x.title||'';
    return PATTERNS.some(re=>re.test(title));
  }
  function apply(){
    const items=Array.isArray(window.ITEMS)?window.ITEMS:[];
    let ex=[];
    items.forEach(x=>{
      if(explicit(x)){
        x.exclusive=true;
        x.exclusiveScore=Math.max(Number(x.exclusiveScore)||0,98);
        x.priority='must';
        x.tags=Array.isArray(x.tags)?Array.from(new Set(x.tags.concat('단독'))):['단독'];
        ex.push(x);
      }
    });
    const nav=document.querySelector('.nav[data-view="must"]');
    if(nav){
      let el=nav.querySelector('#autoExclusiveCount');
      if(!el){el=document.createElement('span');el.id='autoExclusiveCount';el.className='auto-exclusive-count';nav.appendChild(el)}
      el.textContent=' · 단독 '+ex.length;
      el.title='최근 72시간 자동차 단독·취재 신호';
    }
    const today=document.querySelector('#today');
    if(today){
      if(ex.length){
        const names=ex.slice(0,3).map(x=>x.sourceName).filter(Boolean);
        today.textContent='최근 72시간 자동차 단독·취재 신호 '+ex.length+'건'+(names.length?' · '+names.join(' · '):'')+' | 단독은 자동차 핵심 최상단에 우선 노출합니다.';
      }else if(/뉴스 데이터를 불러오는 중입니다|자동차는|산업부/.test(today.textContent||'')){
        today.textContent='최근 72시간 자동차 단독·취재 신호 0건 | 새 단독이 들어오면 자동차 핵심 최상단에 우선 노출합니다.';
      }
    }
    const count=document.querySelector('#countMust');
    if(count){
      const n=items.filter(x=>!x.global&&!x.industrySource&&x.priority==='must').length;
      count.textContent=n;
    }
    if(typeof render==='function') render();
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',apply); else apply();
})();
