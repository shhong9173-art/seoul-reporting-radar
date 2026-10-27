(function(){
  const AUTO_CATS=new Set(['완성차','부품','배터리','정책·관세','중국차','노조·생산','수주·투자','리콜·안전','단독','미국·글로벌']);
  const INDUSTRY_CATS=new Set(['철강','비철금속','전력기기','전선·전력','에너지','재생에너지','화학·소재']);
  const AUTO_RE=/현대차|현대자동차|기아|제네시스|현대모비스|현대위아|현대트랜시스|HL만도|LG에너지솔루션|삼성SDI|SK온|CATL|BYD|테슬라|폭스바겐|GM|포드|토요타|BMW|벤츠|르노코리아|한국GM|KG모빌리티|볼보|파나소닉|노스볼트|전기차|자동차|차량|배터리|자율주행|충전기|리콜|결함/i;
  const PATTERNS=[
    /(^|[\s\[\(])단독(?:보도|취재|입수|확인|인터뷰|공개)?(?=[:：\]\)\s]|$)/i,
    /본지\s*(?:단독|취재|취재결과)/i,
    /단독\s*(?:입수|확인|포착|취재|인터뷰)/i,
    /단독보도/i,
    /단독취재/i
  ];
  function explicit(x){
    if(!x || x.global || !PATTERNS.some(re=>re.test(x.title||''))) return false;
    const t=(x.title||'')+' '+(x.summary||'');
    if(!x.industrySource) return AUTO_CATS.has(x.category)&&AUTO_RE.test(t);
    return INDUSTRY_CATS.has(x.category);
  }
  function uniquePush(arr,x){
    // The industrial merger does not supply stable article IDs. Comparing
    // undefined === undefined silently collapsed ALL industrial headlines to
    // one displayed [단독] item, even when they came from different outlets.
    const same=(a,b)=>{
      if(a.id && b.id) return a.id===b.id;
      if(a.url && b.url) return a.url===b.url;
      return a.sourceName===b.sourceName&&a.title===b.title&&
             a.published===b.published;
    };
    if(!arr.some(v=>same(v,x)))arr.push(x);
  }
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
      el.textContent='단독표기 '+autoEx.length;
      el.title='수집된 자동차 기사에 관측된 [단독] 제목 수(전체 보도 건수 아님)';
    }
    const industryNav=document.querySelector('.nav[data-view="industryMust"]');
    if(industryNav){
      let el=industryNav.querySelector('#industryExclusiveCount');
      if(!el){el=document.createElement('span');el.id='industryExclusiveCount';el.className='auto-exclusive-count';industryNav.appendChild(el)}
      el.textContent='단독표기 '+industryEx.length;
      el.title='수집된 산업부 기사에 관측된 [단독] 제목 수(전체 보도 건수 아님)';
    }
    const today=document.querySelector('#today');
    if(today){
      if(autoEx.length){
        const names=autoEx.slice(0,3).map(x=>x.sourceName).filter(Boolean);
        today.textContent='최근 72시간 뉴스색인에 관측된 자동차 [단독] 제목 '+autoEx.length+'건'+(names.length?' · '+names.join(' · '):'')+' | 일부 매체·기사는 검색에 누락될 수 있고 실제 미보도 단독을 의미하지 않습니다.';
      }else if(/뉴스 데이터를 불러오는 중입니다|자동차는|산업부/.test(today.textContent||'')){
        today.textContent='최근 72시간 뉴스색인에 자동차 [단독] 제목이 관측되지 않았습니다. 수집 누락 가능성이 있어 실제 단독기사 0건을 뜻하지 않습니다.';
      }
    }
    if(industryEx.length){
      const industryBtn=document.querySelector('.nav[data-view="industryMust"]');
      if(industryBtn) industryBtn.title='최근 72시간 산업부 [단독] 제목 관측 '+industryEx.length+'건 (불완전한 뉴스색인)';
    }
    const count=document.querySelector('#countMust');
    if(count){const n=items.filter(x=>!x.global&&!x.industrySource&&x.priority==='must').length;count.textContent=n;}
    if(typeof render==='function') render();
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',apply); else apply();
})();
