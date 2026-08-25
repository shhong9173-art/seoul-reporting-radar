(function(){
  const CORE_CATS=new Set(['철강','비철금속','전력기기','전선·전력','에너지','재생에너지','화학·소재']);
  const MUST=['수주','계약','공급','증설','투자','공장','생산중단','가동','감산','철수','매각','인수','합작','관세','반덤핑','통상','가격','원가','마진','LME','전력망','변압기','HVDC','해저케이블','해상풍력','풍력','태양광','구조조정','스페셜티'];
  const NOISE=['주가','증권','목표주가','급등','급락','추천','관련주','테마주','특징주','주목할 종목','증시','전망','시장 기대'];
  const NATIVE=window.filtered;
  function industryCore(x){
    if(!x||x.global||!x.industrySource||!CORE_CATS.has(x.category)) return false;
    const t=(x.title||'')+' '+(x.summary||'');
    const positives=MUST.filter(w=>t.includes(w)).length;
    const negatives=NOISE.filter(w=>t.includes(w)).length;
    const company=(x.companies||[]).length;
    const concrete=/(\d[\d,.]*\s*(조|억|만|천)?원|\d+(?:\.\d+)?\s*%|\d[\d,.]*\s*(톤|GWh|MWh|km|대|MW|GW))/i.test(t);
    return (x.score||0)>=72 && positives>=1 && negatives===0 && (company>=1 || concrete || positives>=2);
  }
  window.filtered=function(){
    let a=Array.isArray(window.ITEMS)?window.ITEMS.slice():[];
    if(window.view==='industryMust'){
      a=a.filter(industryCore).sort((a,b)=>{
        const ac=(a.companies||[]).length,bc=(b.companies||[]).length;
        const as=(a.score||0)+(a.signalCount||0)*2+(ac?4:0),bs=(b.score||0)+(b.signalCount||0)*2+(bc?4:0);
        return bs-as || new Date(b.published)-new Date(a.published);
      }).slice(0,20);
    }else{
      // Preserve the existing site behavior for every other view.
      return NATIVE();
    }
    if(window.cat)a=a.filter(x=>x.category===window.cat);
    if(window.query){const q=String(window.query).toLowerCase();a=a.filter(x=>(x.title+' '+(x.summary||'')+' '+x.sourceName+' '+x.category+' '+(x.companies||[]).join(' ')).toLowerCase().includes(q));}
    return a;
  };
})();
