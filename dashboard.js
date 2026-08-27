(function(){
  const main=document.querySelector('main'), toolbar=document.querySelector('.toolbar');
  if(!main||!toolbar)return;
  let box=document.querySelector('#dashboard');
  if(!box){box=document.createElement('section');box.id='dashboard';box.className='dashboard hidden';toolbar.parentNode.insertBefore(box,toolbar)}
  const esc=v=>String(v??'').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));
  const titleOf=x=>x?.global&&x?.koTitle?x.koTitle:x?.title||'';
  const summaryOf=x=>x?.global&&x?.koSummary?x.koSummary:x?.summary||'';
  const time=x=>{const t=new Date(x?.published||0).getTime();return Number.isFinite(t)?t:0};
  const recent=(arr,ms)=>arr.filter(x=>Date.now()-time(x)<=ms);
  const company=x=>(x?.companies||[])[0]||'';
  const nums=s=>[...new Set((String(s||'').match(/(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?:조원|억원|만원|만대|천대|대|명|%|GWh|MWh|kWh|톤|km|MW|GW)/g)||[]))];
  const topic=s=>{const t=String(s||'').toLowerCase();if(/수소환원|hyrex|고로|제철|철강/.test(t))return'철강';if(/구리|아연|니켈|제련/.test(t))return'비철금속';if(/변압기|hvdc|해저케이블|전력망/.test(t))return'전력기기·전선';if(/풍력|해상풍력/.test(t))return'풍력';if(/석유화학|스페셜티|화학/.test(t))return'화학·소재';if(/전기차|배터리/.test(t))return'전기차·배터리';if(/로보택시|자율주행|피지컬 ai|로봇/.test(t))return'자동차 미래기술';return''};
  const key=s=>{const c=(s?.companies||[])[0]||'';return c+'|'+(topic(titleOf(s)+' '+summaryOf(s))||s?.category||'')};
  const card=(label,title,body,meta,cls='')=>`<article class="dash-card ${cls}"><div class="dash-kicker">${esc(label)}</div><div class="dash-title">${esc(title)}</div><div class="dash-body">${esc(body)}</div>${meta?`<div class="dash-meta">${esc(meta)}</div>`:''}</article>`;
  const hide=()=>box.classList.add('hidden'); const show=()=>box.classList.remove('hidden');
  async function render(){
    show();
    const all=Array.isArray(window.ITEMS)?window.ITEMS:[]; const domestic=all.filter(x=>!x.global); const auto=domestic.filter(x=>!x.industrySource); const industry=domestic.filter(x=>x.industrySource);
    let pitches=[];try{const r=await fetch('pitch.json?v='+Date.now(),{cache:'no-store'});const j=await r.json();pitches=Array.isArray(j)?j:[]}catch(e){}
    pitches=pitches.slice().sort((a,b)=>(b.pitchScore||0)-(a.pitchScore||0)).slice(0,3);
    const must=auto.filter(x=>x.priority==='must').sort((a,b)=>(b.score||0)-(a.score||0)).slice(0,3);
    const r24=recent(domestic,86400000), prev48=domestic.filter(x=>Date.now()-time(x)>86400000&&Date.now()-time(x)<=259200000);
    const r={},p={}; r24.forEach(x=>{const k=key(x);r[k]=(r[k]||0)+1}); prev48.forEach(x=>{const k=key(x);p[k]=(p[k]||0)+1});
    const changes=Object.entries(r).map(([k,n])=>{const [c,t]=k.split('|');const old=p[k]||0;return{c,t,n,old,growth:n-old}}).filter(x=>x.n>=2||x.growth>=2).sort((a,b)=>b.growth-a.growth||b.n-a.n).slice(0,6);
    const groups={};domestic.filter(x=>(x.clusterCount||1)>=2).forEach(x=>{const k=x.clusterId||x.id;(groups[k]??=[]).push(x)});
    const competition=Object.values(groups).sort((a,b)=>new Set(b.map(x=>x.sourceName)).size-new Set(a.map(x=>x.sourceName)).size||b.length-a.length).slice(0,3);
    const newNums=[];const seen=new Set();r24.sort((a,b)=>time(b)-time(a)).forEach(x=>{nums(titleOf(x)+' '+summaryOf(x)).forEach(n=>{if(!seen.has(n)){seen.add(n);newNums.push({n,x})}})});
    const indStats={};industry.forEach(x=>{const c=x.category||'산업부';(indStats[c]??={recent:0,old:0});Date.now()-time(x)<=86400000?indStats[c].recent++:indStats[c].old++});
    const ind=Object.entries(indStats).map(([c,v])=>({c,...v,growth:v.recent-v.old})).sort((a,b)=>b.growth-a.growth||b.recent-a.recent).slice(0,7);
    box.innerHTML=`<div class="dash-head"><div><div class="eyebrow">REPORTING CONTROL ROOM</div><h2>오늘 취재 상황판</h2><p>오늘 달라진 것과 실제로 파볼 만한 기사만 먼저 봅니다.</p></div><button class="dash-refresh" type="button">다시 계산</button></div>
    <div class="dash-grid">
      <section class="dash-section dash-feature"><div class="dash-section-head"><b>오늘 발제</b><span>검증 통과 최대 3개</span></div>${pitches.map((p,i)=>card(`발제 ${i+1}`,p.headline,p.angle||'이 자료를 연결해 무엇을 확인할지 살펴보세요.',(p.numbers||[]).slice(0,4).join(' · '),'pitch-highlight')).join('')||'<div class="dash-empty">오늘 바로 쓸 발제가 없습니다.</div>'}</section>
      <section class="dash-section"><div class="dash-section-head"><b>자동차에서 반드시 볼 것</b><span>1순위</span></div>${must.map(x=>card(x.category||'자동차',titleOf(x),summaryOf(x),x.sourceName||'')).join('')||'<div class="dash-empty">핵심 기사가 없습니다.</div>'}</section>
      <section class="dash-section"><div class="dash-section-head"><b>어제와 달라진 것</b><span>24시간 vs 직전 48시간</span></div>${changes.map(x=>card(x.t||'변화',`${x.c||'기업'} · ${x.t||''}`,`최근 24시간 ${x.n}건 / 직전 48시간 ${x.old}건. ${x.growth>0?'기사·공시를 더 파볼 가치가 커진 신호입니다.':'최근 새로 잡힌 신호입니다.'}`,x.growth>0?`증가 ${x.growth}건`:'신규')).join('')||'<div class="dash-empty">뚜렷한 변화 신호가 없습니다.</div>'}</section>
      <section class="dash-section"><div class="dash-section-head"><b>경쟁지가 먼저 쓴 것</b><span>그대로 따라가지 말고 다음 사실 찾기</span></div>${competition.map(g=>{const l=g.slice().sort((a,b)=>time(b)-time(a))[0],s=[...new Set(g.map(x=>x.sourceName).filter(Boolean))];return card(`${s.length}개 매체`,titleOf(l),`${s.join(', ')}에서 보도된 이슈. 우리 쪽에서 추가 숫자·계약·투자·생산 변화가 있는지 확인.`,'추가 취재 여부 판단')}).join('')||'<div class="dash-empty">경쟁지 선행 이슈가 없습니다.</div>'}</section>
      <section class="dash-section"><div class="dash-section-head"><b>기사 발굴용 숫자</b><span>최근 24시간</span></div>${newNums.slice(0,6).map(o=>card(o.x.category||'산업',o.n,titleOf(o.x),company(o.x)||'관련 기업')).join('')||'<div class="dash-empty">새 숫자 신호가 없습니다.</div>'}</section>
      <section class="dash-section"><div class="dash-section-head"><b>산업별 변화</b><span>기사 수보다 증가폭</span></div><div class="dash-industries">${ind.map(x=>`<button type="button" data-cat="${esc(x.c)}"><strong>${esc(x.c)}</strong><span>${x.growth>0?'+':''}${x.growth} · 최근 ${x.recent}건</span></button>`).join('')||'<div class="dash-empty">산업 데이터가 없습니다.</div>'}</div></section>
    </div>`;
    box.querySelector('.dash-refresh')?.addEventListener('click',render);
    box.querySelectorAll('.dash-industries button').forEach(b=>b.addEventListener('click',()=>{cat=b.dataset.cat;view='industryMust';syncNav();hide();render()}));
  }
  const existingNav=document.querySelector('.nav.dashboard-nav');
  if(!existingNav){const n=document.createElement('button');n.className='nav dashboard-nav';n.type='button';n.textContent='오늘 취재 상황판';document.querySelector('.sidebar nav')?.prepend(n);n.addEventListener('click',render)}
  document.querySelectorAll('.nav:not(.dashboard-nav)').forEach(n=>n.addEventListener('click',hide));
  render();
})();
