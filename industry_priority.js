(function(){
  const CORE_CATS=new Set(['철강','비철금속','전력기기','전선·전력','에너지','재생에너지','화학·소재']);
  const MUST=['수주','계약','공급','증설','투자','공장','생산중단','가동','감산','철수','매각','인수','합작','관세','반덤핑','통상','가격','원가','마진','LME','전력망','변압기','HVDC','해저케이블','해상풍력','풍력','태양광','구조조정','스페셜티','배터리소재'];
  const NOISE=['주가','증권','목표주가','급등','급락','추천','관련주','테마주','특징주','주목할 종목','증시','전망','시장 기대','주목받고 있다'];
  const SCOOP=['단독','취재결과','본지 취재','취재를 종합하면','확인한 결과','확인됐다'];
  const EVENT=['인베스터데이','주주총회','설명회','세미나','포럼','엑스포','컨퍼런스','부스투어','기조연설','발표회'];

  function text(x){return ((x.title||'')+' '+(x.summary||'')).toLowerCase()}
  function isCore(x){
    if(!x||x.global||!x.industrySource||!CORE_CATS.has(x.category)) return false;
    const t=text(x);
    const positives=MUST.filter(w=>t.includes(w.toLowerCase())).length;
    const negatives=NOISE.filter(w=>t.includes(w.toLowerCase())).length;
    const event=EVENT.some(w=>(x.title||'').includes(w));
    const company=(x.companies||[]).length;
    const concrete=!!x.concreteNumber;
    const exclusive=!!x.exclusive || SCOOP.some(w=>t.includes(w.toLowerCase()));
    const unique=(x.clusterCount||1)<=1;
    if(negatives>0 || (event && !exclusive)) return false;
    // Core = scoop first. Non-scoop items need stronger evidence to enter at all.
    if(exclusive) return true;
    return (x.score||0)>=80 && positives>=2 && concrete && company>=1 && unique;
  }

  function scoopScore(x){
    const t=text(x);
    const exclusive=!!x.exclusive || SCOOP.some(w=>t.includes(w.toLowerCase()));
    const unique=(x.clusterCount||1)<=1;
    const concrete=!!x.concreteNumber || /\d[\d,.]*\s*(조원|억원|만원|만대|천대|대|명|%|톤|mw|gw|gwh|mwh)/i.test(t);
    const signals=x.signalCount||0;
    const strategy=x.strategySignalCount||0;
    return (exclusive?100:0)+(unique?22:0)+(concrete?15:0)+Math.min(16,signals*2)+Math.min(14,strategy*2)+(x.score||0)*0.12;
  }

  function esc(v){return String(v??'').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));}

  function card(x, lane){
    const exclusive=!!x.exclusive || SCOOP.some(w=>text(x).includes(w.toLowerCase()));
    const label=exclusive?'단독·취재확인':'새 산업 이슈';
    const cls=exclusive?'exclusive':'must';
    return `<article class="card ${cls}" onclick="openItem('${esc(x.id)}')">
      <div class="card-top"><span class="badge ${cls}">${label}</span><span class="score">${Math.round(scoopScore(x))}점</span></div>
      <div class="meta">${esc(x.category)} · ${esc(x.sourceName)} · ${esc(x.publishedLabel||x.published)}</div>
      <div class="title">${esc(x.title)}</div>
      <div class="summary"><b class="why">${esc(x.whyNow||'산업 변화의 구체적 사실관계를 우선 확인')}</b><br>${esc(x.summary||'')}</div>
      <div class="signal-row"><span class="signal">관련 ${x.clusterCount||1}건</span>${exclusive?'<span class="signal">단독·취재확인</span>':''}${x.concreteNumber?'<span class="signal">구체적 숫자</span>':''}${(x.companies||[]).slice(0,3).map(c=>`<span class="signal">${esc(c)}</span>`).join('')}</div>
      <div class="bottom"><span class="tag">${esc(x.category)}</span>${(x.companies||[]).slice(0,4).map(c=>`<span class="tag">${esc(c)}</span>`).join('')}</div>
    </article>`;
  }

  function renderCore(){
    const items=Array.isArray(window.ITEMS)?window.ITEMS:[];
    const rows=items.filter(isCore).sort((a,b)=>scoopScore(b)-scoopScore(a)||new Date(b.published)-new Date(a.published));
    const scoops=rows.filter(x=>!!x.exclusive || SCOOP.some(w=>text(x).includes(w.toLowerCase()))).slice(0,8);
    const fresh=rows.filter(x=>!scoops.includes(x)).slice(0,8);
    const cards=document.querySelector('#cards');
    if(!cards)return;
    document.querySelector('#viewTitle').textContent='산업부 핵심';
    document.querySelector('#resultCount').textContent=(scoops.length+fresh.length)+'건';
    document.querySelector('#headline').textContent='산업부에서 오늘 파볼 것';
    document.querySelector('#today').textContent='단독·취재확인 이슈를 먼저, 그다음 구체적인 투자·수주·생산·가격 변화가 있는 새 이슈만 선별합니다.';
    const section=(title,items)=>items.length?`<div style="grid-column:1/-1;padding:8px 2px 2px;font-weight:800;font-size:13px;color:#334155">${title} <span style="font-weight:500;color:#64748b">${items.length}건</span></div>${items.map(x=>card(x,title)).join('')}`:'';
    cards.innerHTML=section('단독·취재확인',scoops)+section('새로 파볼 산업 이슈',fresh) || '<div class="card"><div class="summary">현재 단독·취재확인 또는 구체적인 산업 변화 신호가 있는 핵심 이슈가 없습니다.</div></div>';
  }

  function bind(){
    const btn=document.querySelector('.nav[data-view="industryMust"]');
    const count=document.querySelector('#countIndustryMust');
    const refresh=()=>{
      const items=Array.isArray(window.ITEMS)?window.ITEMS:[];
      if(count)count.textContent=Math.min(16,items.filter(isCore).length);
    };
    refresh();
    if(btn){
      btn.addEventListener('click',()=>setTimeout(()=>{refresh();renderCore();},0));
    }
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',bind);else bind();
})();
