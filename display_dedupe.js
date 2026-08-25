(function(){
  const nativeFiltered=window.filtered;
  const STOP=new Set('자동차 전기차 배터리 현대차 기아 관련 올해 오늘 최근 한국 산업부 산업 기업 시장 업계 사업 국내 글로벌 밝혔다 따르면 위한 통해 대한'.split(' '));
  const WORDS=t=>new Set(String(t||'').toLowerCase().match(/[가-힣A-Za-z0-9]{2,}/g)||[]);
  const cleanTitle=t=>String(t||'').replace(/^\s*\[[^\]]+\]\s*/,'').replace(/\s*[-|｜]\s*[^-–—|｜]+$/,'').replace(/[^가-힣A-Za-z0-9 ]/g,' ').replace(/\s+/g,' ').trim().toLowerCase();
  const informative=t=>new Set([...WORDS(cleanTitle(t))].filter(w=>!STOP.has(w)&&w.length>=2));
  function overlap(a,b){
    const A=informative(a.title),B=informative(b.title);
    if(!A.size||!B.size)return 0;
    let inter=0; for(const w of A)if(B.has(w))inter++;
    return inter/Math.min(A.size,B.size);
  }
  function sameDisplayStory(a,b){
    if(a.global!==b.global)return false;
    const ca=new Set(a.companies||[]),cb=new Set(b.companies||[]);
    const companyOverlap=[...ca].some(c=>cb.has(c));
    if(a.industrySource&&b.industrySource&&a.category===b.category&&overlap(a,b)>=0.58)return true;
    if(companyOverlap&&a.category===b.category&&overlap(a,b)>=0.52)return true;
    if(companyOverlap&&overlap(a,b)>=0.68)return true;
    return cleanTitle(a.title)===cleanTitle(b.title);
  }
  function collapse(arr){
    const groups=[];
    const sorted=[...arr].sort((a,b)=>(b.score||0)-(a.score||0)||new Date(b.published)-new Date(a.published));
    for(const x of sorted){
      const existing=groups.find(g=>{
        const head=g[0];
        if(x.clusterId&&head.clusterId&&x.clusterId===head.clusterId)return true;
        return sameDisplayStory(x,head);
      });
      if(existing)existing.push(x); else groups.push([x]);
    }
    return groups.map(g=>{
      const rep=g[0];
      const sources=[...new Set(g.map(x=>x.sourceName).filter(Boolean))];
      const ids=g.map(x=>x.id).filter(Boolean);
      return Object.assign({},rep,{displayDuplicateCount:g.length,displayCoveredBy:sources,displayDuplicateIds:ids,coveredBy:sources.length>1?sources:(rep.coveredBy||[]),clusterCount:Math.max(rep.clusterCount||1,g.length)});
    });
  }
  window.filtered=function(){
    const a=nativeFiltered();
    if(['competition','issues','keywords'].includes(window.view))return a;
    const out=collapse(a);
    return out;
  };
  window._displayDedupe=collapse;
})();
