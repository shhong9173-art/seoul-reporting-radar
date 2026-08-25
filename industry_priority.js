(function(){
  const CORE_CATS=new Set(['철강','비철금속','전력기기','전선·전력','에너지','재생에너지','화학·소재']);
  const MUST=['수주','계약','공급','증설','투자','공장','생산중단','가동','감산','철수','매각','인수','합작','관세','반덤핑','통상','가격','원가','마진','LME','전력망','변압기','HVDC','해저케이블','해상풍력','풍력','태양광','구조조정','스페셜티'];
  const NOISE=['주가','증권','목표주가','급등','급락','추천','관련주','테마주','특징주','주목할 종목','증시','전망','시장 기대'];

  function isCore(x){
    if(!x||x.global||!x.industrySource||!CORE_CATS.has(x.category)) return false;
    const t=((x.title||'')+' '+(x.summary||'')).toLowerCase();
    const positives=MUST.filter(w=>t.includes(w.toLowerCase())).length;
    const negatives=NOISE.filter(w=>t.includes(w.toLowerCase())).length;
    const company=(x.companies||[]).length;
    const concrete=/(\d[\d,.]*\s*(조|억|만|천)?원|\d+(?:\.\d+)?\s*%|\d[\d,.]*\s*(톤|GWh|MWh|km|대|MW|GW))/i.test(t);
    return negatives===0 && (x.score||0)>=72 && positives>=1 && (company>=1 || concrete || positives>=2);
  }

  function esc(v){return String(v??'').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));}

  function renderCore(){
    const items=Array.isArray(window.ITEMS)?window.ITEMS:[];
    const rows=items.filter(isCore).sort((a,b)=>{
      const ac=(a.companies||[]).length,bc=(b.companies||[]).length;
      const as=(a.score||0)+(a.signalCount||0)*3+(ac?5:0)+(/\d/.test(a.title||'')?4:0);
      const bs=(b.score||0)+(b.signalCount||0)*3+(bc?5:0)+(/\d/.test(b.title||'')?4:0);
      return bs-as || new Date(b.published)-new Date(a.published);
    }).slice(0,20);

    const cards=document.querySelector('#cards');
    if(!cards)return;
    document.querySelector('#viewTitle').textContent='산업부 핵심';
    document.querySelector('#resultCount').textContent=rows.length+'건';
    document.querySelector('#headline').textContent='산업부에서 오늘 놓치면 안 되는 것';
    document.querySelector('#today').textContent='실제 산업 변화·투자·수주·생산·관세 등 취재가치가 확인된 핵심만 최대 20건 선별합니다.';
    const badge=x=>x.priority==='must'?'오늘 핵심':x.followUp?'후속 검토':'산업부 핵심';
    cards.innerHTML=rows.length?rows.map(x=>`<article class="card ${x.priority==='must'?'must':'normal'}" onclick="openItem('${esc(x.id)}')">
      <div class="card-top"><span class="badge ${x.priority==='must'?'must':'normal'}">${badge(x)}</span><span class="score">${x.score||0}점</span></div>
      <div class="meta">${esc(x.category)} · ${esc(x.sourceName)} · ${esc(x.publishedLabel||x.published)}</div>
      <div class="title">${esc(x.title)}</div>
      <div class="summary"><b class="why">${esc(x.whyNow||'산업 변화의 구체적인 사실관계를 우선 확인')}</b><br>${esc(x.summary||'')}</div>
      <div class="signal-row"><span class="signal">관련 ${x.clusterCount||1}건</span>${(x.companies||[]).slice(0,3).map(c=>`<span class="signal">${esc(c)}</span>`).join('')}</div>
      <div class="bottom"><span class="tag">${esc(x.category)}</span>${(x.companies||[]).slice(0,4).map(c=>`<span class="tag">${esc(c)}</span>`).join('')}</div>
    </article>`).join(''):'<div class="card"><div class="summary">현재 원자료와 구체적인 산업 변화 신호를 함께 확인할 수 있는 핵심 이슈가 없습니다.</div></div>';
  }

  function bind(){
    const btn=document.querySelector('.nav[data-view="industryMust"]');
    const count=document.querySelector('#countIndustryMust');
    const refresh=()=>{
      const n=(Array.isArray(window.ITEMS)?window.ITEMS:[]).filter(isCore).length;
      if(count)count.textContent=Math.min(20,n);
    };
    refresh();
    if(btn){
      btn.addEventListener('click',()=>setTimeout(()=>{refresh();renderCore();},0));
    }
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',bind);else bind();
})();
