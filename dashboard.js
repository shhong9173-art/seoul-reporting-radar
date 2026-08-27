(function(){
  const main=document.querySelector('main');
  const toolbar=document.querySelector('.toolbar');
  if(!main||!toolbar)return;
  const box=document.createElement('section');
  box.id='dashboard';
  box.className='dashboard hidden';
  toolbar.parentNode.insertBefore(box,toolbar);

  const esc=v=>String(v??'').replace(/[&<>\\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\\"':'&quot;',"'":'&#39;'}[c]));
  const titleOf=x=>x?.global&&x?.koTitle?x.koTitle:x?.title||'';
  const summaryOf=x=>x?.global&&x?.koSummary?x.koSummary:x?.summary||'';
  const dt=x=>{const d=new Date(x?.published||0);return isNaN(d)?0:d.getTime()};
  const recent=items=>items.slice().sort((a,b)=>dt(b)-dt(a));
  const companyName=x=>(x?.companies||[])[0]||'';
  const industry=x=>x?.industrySource&&!x?.global;
  const nums=s=>{const m=String(s||'').match(/(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?:조원|억원|만원|만대|천대|대|명|%|GWh|MWh|kWh|톤|km|MW|GW)/g);return [...new Set(m||[])];};
  const topic=s=>{
    const t=String(s||'').toLowerCase();
    if(/수소환원|hyrex|고로|제철/.test(t))return '철강';
    if(/전력망|hvdc|해저케이블|변압기/.test(t))return '전력기기·전선';
    if(/풍력|해상풍력/.test(t))return '풍력';
    if(/석유화학|스페셜티|화학/.test(t))return '화학·소재';
    if(/구리|아연|니켈|제련/.test(t))return '비철금속';
    if(/전기차|배터리/.test(t))return '전기차·배터리';
    if(/로보택시|자율주행|피지컬 ai|로봇/.test(t))return '자동차 미래기술';
    return '';
  };
  function close(){box.classList.add('hidden');}
  function show(){box.classList.remove('hidden');}
  function card(p){return `<article class="dash-card"><div class="dash-kicker">${esc(p.kicker||'오늘 볼 것')}</div><div class="dash-title">${esc(p.title||'')}</div><div class="dash-body">${esc(p.body||'')}</div>${p.meta?`<div class="dash-meta">${esc(p.meta)}</div>`:''}</article>`}
  async function renderDashboard(){
    show();
    const all=Array.isArray(window.ITEMS)?window.ITEMS:[];
    let pitches=[];try{const r=await fetch('pitch.json?v='+Date.now(),{cache:'no-store'});pitches=await r.json();if(!Array.isArray(pitches))pitches=[];}catch(e){pitches=[]}
    const domestic=all.filter(x=>!x.global);
    const must=recent(domestic.filter(x=>x.priority==='must')).slice(0,3);
    const fresh=recent(domestic.filter(x=>!x.global&&nums(titleOf(x)+' '+summaryOf(x)).length)).slice(0,8);
    const clusters={};domestic.filter(x=>(x.clusterCount||1)>=2).forEach(x=>{const k=x.clusterId||x.id;(clusters[k]??=[]).push(x)});
    const comp=Object.values(clusters).sort((a,b)=>b.length-a.length).slice(0,3);
    const indCount={};domestic.filter(industry).forEach(x=>indCount[x.category]=(indCount[x.category]||0)+1);
    const indTop=Object.entries(indCount).sort((a,b)=>b[1]-a[1]).slice(0,4);
    const numsTop=[];const seenNum=new Set();for(const x of fresh){for(const n of nums(titleOf(x)+' '+summaryOf(x))){if(seenNum.has(n))continue;seenNum.add(n);numsTop.push({n,x});if(numsTop.length>=6)break;}if(numsTop.length>=6)break;}
    box.innerHTML=`
      <div class="dash-head"><div><div class="eyebrow">REPORTING CONTROL ROOM</div><h2>오늘 취재 상황판</h2><p>뉴스를 읽는 화면이 아니라, 오늘 무엇을 확인하고 어떤 기사로 만들지 고르는 화면</p></div><button class="dash-refresh" type="button">새로고침</button></div>
      <div class="dash-grid">
        <section class="dash-section dash-pitches"><div class="dash-section-head"><b>오늘 발제</b><span>${pitches.length}개 후보</span></div>${pitches.slice(0,3).map((p,i)=>card({kicker:`발제 ${i+1}`,title:p.headline,body:p.angle||p.newFact,meta:(p.numbers||[]).slice(0,4).join(' · ')})).join('')||'<div class="dash-empty">통과한 발제가 없습니다.</div>'}</section>
        <section class="dash-section"><div class="dash-section-head"><b>반드시 볼 것</b><span>자동차 우선</span></div>${must.map(x=>card({kicker:'자동차 핵심',title:titleOf(x),body:summaryOf(x),meta:`${x.sourceName||''} · ${x.category||''}`})).join('')||'<div class="dash-empty">현재 핵심 기사가 없습니다.</div>'}</section>
        <section class="dash-section"><div class="dash-section-head"><b>새로 생긴 변화</b><span>최근 업데이트</span></div>${fresh.slice(0,5).map(x=>card({kicker:topic(titleOf(x)+' '+summaryOf(x))||x.category||'산업',title:titleOf(x),body:summaryOf(x),meta:nums(titleOf(x)+' '+summaryOf(x)).slice(0,3).join(' · ')})).join('')||'<div class="dash-empty">새로운 변화가 없습니다.</div>'}</section>
        <section class="dash-section"><div class="dash-section-head"><b>경쟁지가 먼저 쓴 것</b><span>놓치면 안 되는 이슈</span></div>${comp.map(g=>card({kicker:`관련 매체 ${g.length}곳`,title:titleOf(g[0]),body:`${[...new Set(g.map(x=>x.sourceName).filter(Boolean))].join(', ')}에서 확산된 이슈`,meta:`이슈 ${g[0].clusterId||'-'}`})).join('')||'<div class="dash-empty">확산 이슈가 없습니다.</div>'}</section>
        <section class="dash-section dash-numbers"><div class="dash-section-head"><b>오늘 새로 눈에 들어온 숫자</b><span>기사 발굴용</span></div><div class="dash-number-list">${numsTop.map(o=>`<div><strong>${esc(o.n)}</strong><span>${esc(companyName(o.x)||o.x.category||'')}</span><p>${esc(titleOf(o.x))}</p></div>`).join('')||'<div class="dash-empty">숫자 신호가 없습니다.</div>'}</div></section>
        <section class="dash-section"><div class="dash-section-head"><b>산업별 레이더</b><span>수집량이 아니라 변화 감지</span></div><div class="dash-industries">${indTop.map(([c,n])=>`<button type="button" data-cat="${esc(c)}"><strong>${esc(c)}</strong><span>${n}건</span></button>`).join('')||'<div class="dash-empty">산업 데이터가 없습니다.</div>'}</div></section>
      </div>`;
    box.querySelector('.dash-refresh')?.addEventListener('click',renderDashboard);
    box.querySelectorAll('.dash-industries button').forEach(b=>b.addEventListener('click',()=>{cat=b.dataset.cat;view='industryMust';syncNav();close();render();}));
  }
  function activate(){renderDashboard();document.querySelectorAll('.nav').forEach(n=>n.classList.remove('active'));const n=document.querySelector('.nav.dashboard-nav');n?.classList.add('active');}
  const nav=document.querySelector('.nav[data-view="must"]');
  if(nav){nav.classList.remove('active');}
  const existing=document.querySelector('.nav.dashboard-nav');
  if(!existing){const n=document.createElement('button');n.className='nav dashboard-nav';n.type='button';n.textContent='오늘 취재 상황판';n.style.order='-1';const parent=n.parentNode;document.querySelector('.sidebar nav')?.prepend(n);n.addEventListener('click',activate)}
  document.querySelectorAll('.nav:not(.dashboard-nav)').forEach(n=>n.addEventListener('click',close));
  activate();
})();
