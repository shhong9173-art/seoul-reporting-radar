(function(){
  const pitchButton=document.querySelector('.pitch-nav'), archiveButton=document.querySelector('.archive-nav'), cards=document.querySelector('#cards'), title=document.querySelector('#viewTitle'), result=document.querySelector('#resultCount');
  if(!pitchButton||!cards) return;
  const esc=v=>String(v??'').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));
  const items=Array.isArray(window.ITEMS)?window.ITEMS:[]; let archive=[];
  fetch('archive.json?v=20260825-10',{cache:'no-store'}).then(r=>r.ok?r.json():[]).then(v=>{archive=Array.isArray(v)?v:[];const c=document.querySelector('#countArchive');if(c)c.textContent=archive.length}).catch(()=>{});
  function setActive(btn){document.querySelectorAll('.nav').forEach(n=>n.classList.remove('active'));btn.classList.add('active')}
  function renderPitch(){
    setActive(pitchButton);title.textContent='오늘 발제할 만한 것';
    const out=items.filter(x=>!x.exclusive&&Number(x.pitchScore||0)>=70).sort((a,b)=>(b.pitchScore||0)-(a.pitchScore||0)||new Date(b.published)-new Date(a.published)).slice(0,12);result.textContent=out.length+'건';
    cards.innerHTML=out.length?out.map((x,i)=>`<article class="card ${x.pitchScore>=85?'must':'follow'} pitch-card" onclick="openItem('${esc(x.id)}')"><div class="card-top"><span class="badge ${x.pitchScore>=85?'must':'follow'}">발제 가능성 ${x.pitchScore}</span><span class="score">${i+1}위</span></div><div class="meta">${esc(x.sourceName)} · ${esc(x.publishedLabel||x.published)} · ${x.global?'해외 신호':'국내 단일·전문지'}</div><div class="title">${esc(x.global&&x.koTitle?x.koTitle:x.title)}</div>${x.global&&x.title!==x.koTitle?`<div class="muted" style="font-size:11px;margin-bottom:7px">원문: ${esc(x.title)}</div>`:''}<div class="summary"><b class="why">발제 근거</b><br>${(x.pitchReasons||[]).map(esc).join(' · ')}</div><div class="signal-row"><span class="signal">관련 ${x.clusterCount||1}건</span><span class="signal">최초 ${esc(x.earliestObservedSource||x.sourceName||'-')}</span></div><div class="quote"><b>먼저 확인할 질문</b><ul>${(x.questions||[]).slice(0,3).map(q=>`<li>${esc(q)}</li>`).join('')}</ul></div><div class="bottom">${(x.companies||[]).slice(0,5).map(c=>`<span class="tag">${esc(c)}</span>`).join('')}</div></article>`).join(''):'<div class="card"><div class="summary">현재 국내 보도 공백이 뚜렷한 발제 후보가 없습니다.</div></div>';
  }
  function renderArchive(){
    setActive(archiveButton);title.textContent='단독·발제 아카이브';result.textContent=archive.length+'건';
    cards.innerHTML=archive.length?archive.map(x=>`<article class="card ${x.exclusive?'exclusive':'follow'}" onclick="openItem('${esc(x.id)}')"><div class="card-top"><span class="badge ${x.exclusive?'exclusive':'follow'}">${x.exclusive?'단독 발견':'발제 후보 기록'}</span><span class="score">${x.exclusive?'단독':'발제 '+(x.pitchScore||0)}</span></div><div class="meta">최초 발견 ${esc(x.earliestObservedAt||x.published||'-')} · ${esc(x.earliestObservedSource||x.sourceName||'-')}</div><div class="title">${esc(x.global&&x.koTitle?x.koTitle:x.title)}</div><div class="summary">발견 당시 기사와 후속 확산 여부를 보존합니다. 현재 관련 매체: ${esc((x.coveredBy||[]).join(', ')||x.sourceName||'-')}</div><div class="bottom">${(x.companies||[]).slice(0,5).map(c=>`<span class="tag">${esc(c)}</span>`).join('')}</div></article>`).join(''):'<div class="card"><div class="summary">아카이브가 아직 없습니다. 첫 수집부터 중요한 단독·발제 후보를 보존합니다.</div></div>';
  }
  pitchButton.addEventListener('click',renderPitch);archiveButton.addEventListener('click',renderArchive);
  document.querySelectorAll('.nav:not(.pitch-nav):not(.archive-nav)').forEach(n=>n.addEventListener('click',()=>{pitchButton.classList.remove('active');archiveButton.classList.remove('active')}));
  const pcount=items.filter(x=>!x.exclusive&&Number(x.pitchScore||0)>=70).length;const pc=document.querySelector('#countPitch');if(pc)pc.textContent=pcount;const ps=document.querySelector('#statPitch');if(ps)ps.textContent=pcount;
})();
