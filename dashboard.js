(function(){
  const main=document.querySelector('main'), toolbar=document.querySelector('.toolbar');
  if(!main||!toolbar)return;
  let box=document.querySelector('#dashboard');
  if(!box){box=document.createElement('section');box.id='dashboard';box.className='dashboard hidden';toolbar.parentNode.insertBefore(box,toolbar)}
  const esc=v=>String(v??'').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));
  const titleOf=x=>x?.global&&x?.koTitle?x.koTitle:x?.title||'';
  const summaryOf=x=>x?.global&&x?.koSummary?x.koSummary:x?.summary||'';
  const time=x=>{const t=new Date(x?.published||0).getTime();return Number.isFinite(t)?t:0};
  const company=x=>(x?.companies||[])[0]||'';
  const nums=s=>[...new Set((String(s||'').match(/(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?:조원|억원|만원|만대|천대|대|명|%|GWh|MWh|kWh|톤|km|MW|GW)/g)||[]))];
  const card=(label,title,body,meta,cls='')=>`<article class="dash-card ${cls}"><div class="dash-kicker">${esc(label)}</div><div class="dash-title">${esc(title)}</div><div class="dash-body">${esc(body)}</div>${meta?`<div class="dash-meta">${esc(meta)}</div>`:''}</article>`;
  const hide=()=>box.classList.add('hidden'); const show=()=>box.classList.remove('hidden');
  async function render(){
    show();
    const all=Array.isArray(window.ITEMS)?window.ITEMS:[]; const domestic=all.filter(x=>!x.global); const auto=domestic.filter(x=>!x.industrySource); const industry=domestic.filter(x=>x.industrySource);
    let pitches=[],changes=[],shifts=[];
    try{const r=await fetch('pitch.json?v='+Date.now(),{cache:'no-store'});const j=await r.json();pitches=Array.isArray(j)?j:[]}catch(e){}
    try{const r=await fetch('changes.json?v='+Date.now(),{cache:'no-store'});const j=await r.json();changes=j&&Array.isArray(j.changes)?j.changes:[]}catch(e){}
    try{const r=await fetch('strategic_shifts.json?v='+Date.now(),{cache:'no-store'});const j=await r.json();shifts=j&&Array.isArray(j.items)?j.items:[]}catch(e){}
    pitches=pitches.slice().sort((a,b)=>(b.pitchScore||0)-(a.pitchScore||0)).slice(0,3);
    changes=changes.filter(x=>x.company).slice(0,6);
    shifts=shifts.slice().sort((a,b)=>(b.score||0)-(a.score||0)).slice(0,5);
    const must=auto.filter(x=>x.priority==='must').sort((a,b)=>(b.score||0)-(a.score||0)).slice(0,3);
    const groups={};domestic.filter(x=>(x.clusterCount||1)>=2).forEach(x=>{const k=x.clusterId||x.id;(groups[k]??=[]).push(x)});
    const competition=Object.values(groups).sort((a,b)=>new Set(b.map(x=>x.sourceName)).size-new Set(a.map(x=>x.sourceName)).size||b.length-a.length).slice(0,3);
    const r24=domestic.filter(x=>Date.now()-time(x)<=86400000).sort((a,b)=>time(b)-time(a));
    const newNums=[];const seen=new Set();r24.forEach(x=>nums(titleOf(x)+' '+summaryOf(x)).forEach(n=>{if(!seen.has(n)){seen.add(n);newNums.push({n,x})}}));
    const indStats={};industry.forEach(x=>{const c=x.category||'산업부';(indStats[c]??={recent:0,old:0});Date.now()-time(x)<=86400000?indStats[c].recent++:indStats[c].old++});
    const ind=Object.entries(indStats).map(([c,v])=>({c,...v,growth:v.recent-v.old})).sort((a,b)=>b.growth-a.growth||b.recent-a.recent).slice(0,7);
    box.innerHTML=`<div class="dash-head"><div><div class="eyebrow">REPORTING CONTROL ROOM</div><h2>오늘 취재 상황판</h2><p>뉴스를 읽는 화면이 아니라, 오늘 무엇을 쓸지 고르는 화면입니다.</p></div><button class="dash-refresh" type="button">다시 계산</button></div>
    <div class="dash-grid">
      <section class="dash-section dash-feature"><div class="dash-section-head"><b>오늘 발제</b><span>바로 보고할 수 있는 후보</span></div>${pitches.map((p,i)=>card(`발제 ${i+1}`,p.headline,p.angle||'자료를 연결해 실제 취재할 포인트를 확인하세요.',(p.numbers||[]).slice(0,4).join(' · '),'pitch-highlight')).join('')||'<div class="dash-empty">오늘 바로 쓸 발제가 없습니다.</div>'}</section>
      <section class="dash-section dash-feature"><div class="dash-section-head"><b>30일간 전략이 달라진 기업</b><span>공시 + 뉴스 교차</span></div>${shifts.map(s=>card(`${s.category||'산업'} · ${(s.signals||[]).slice(0,3).join(' · ')}`,s.headline,s.angle,(s.numbers||[]).slice(0,4).join(' · '),'shift-highlight')).join('')||'<div class="dash-empty">누적 데이터가 아직 부족합니다.</div>'}</section>
      <section class="dash-section"><div class="dash-section-head"><b>자동차에서 반드시 볼 것</b><span>자동차 1순위</span></div>${must.map(x=>card(x.category||'자동차',titleOf(x),summaryOf(x),x.sourceName||'')).join('')||'<div class="dash-empty">핵심 기사가 없습니다.</div>'}</section>
      <section class="dash-section"><div class="dash-section-head"><b>최근 누적된 변화</b><span>최근 31일</span></div>${changes.map(x=>card(`${x.category||'산업'} · ${(x.signals||[]).slice(0,3).join(' · ')||'변화'}`,x.company,`최근 24시간 ${x.count24h||0}건 · 전체 변화 ${x.delta>=0?'+':''}${x.delta}건`,(x.newNumbers||[]).slice(0,4).join(' · ')||'추가 숫자 확인')).join('')||'<div class="dash-empty">아직 누적 변화가 없습니다.</div>'}</section>
      <section class="dash-section"><div class="dash-section-head"><b>경쟁지가 먼저 쓴 것</b><span>그대로 따라가지 말고 다음 사실</span></div>${competition.map(g=>{const l=g.slice().sort((a,b)=>time(b)-time(a))[0],s=[...new Set(g.map(x=>x.sourceName).filter(Boolean))];return card(`${s.length}개 매체`,titleOf(l),`${s.join(', ')}에서 보도된 이슈. 추가 숫자·계약·투자·생산 변화 확인.`,'추가 취재 여부 판단')}).join('')||'<div class="dash-empty">확산 이슈가 없습니다.</div>'}</section>
      <section class="dash-section"><div class="dash-section-head"><b>기사 발굴용 숫자</b><span>최근 24시간</span></div>${newNums.slice(0,6).map(o=>card(o.x.category||'산업',o.n,titleOf(o.x),company(o.x)||'관련 기업')).join('')||'<div class="dash-empty">새 숫자 신호가 없습니다.</div>'}</section>
      <section class="dash-section"><div class="dash-section-head"><b>산업별 변화</b><span>수집량보다 변화폭</span></div><div class="dash-industries">${ind.map(x=>`<button type="button" data-cat="${esc(x.c)}"><strong>${esc(x.c)}</strong><span>${x.growth>0?'+':''}${x.growth} · 최근 ${x.recent}</span></button>`).join('')||'<div class="dash-empty">산업 데이터가 없습니다.</div>'}</div></section>
    </div>`;
    box.querySelector('.dash-refresh')?.addEventListener('click',render);
    box.querySelectorAll('.dash-industries button').forEach(b=>b.addEventListener('click',()=>{if(typeof cat!=='undefined'){cat=b.dataset.cat;view='industryMust';syncNav();hide();render()}}));
  }
  const existingNav=document.querySelector('.nav.dashboard-nav');
  if(!existingNav){const n=document.createElement('button');n.className='nav dashboard-nav';n.type='button';n.textContent='오늘 취재 상황판';document.querySelector('.sidebar nav')?.prepend(n);n.addEventListener('click',render)}
  document.querySelectorAll('.nav:not(.dashboard-nav)').forEach(n=>n.addEventListener('click',hide));
  render();
})();
