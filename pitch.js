(function(){
  const pitchButton=document.querySelector('.pitch-nav'), archiveButton=document.querySelector('.archive-nav'), cards=document.querySelector('#cards'), title=document.querySelector('#viewTitle'), result=document.querySelector('#resultCount');
  if(!pitchButton||!cards)return;
  const esc=v=>String(v??'').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));
  let archive=[], pitches=[];
  const load=()=>Promise.all([
    fetch('archive.json?v='+Date.now(),{cache:'no-store'}).then(r=>r.ok?r.json():[]).catch(()=>[]),
    fetch('pitch.json?v='+Date.now(),{cache:'no-store'}).then(r=>r.ok?r.json():[]).catch(()=>[])
  ]).then(([a,p])=>{
    archive=Array.isArray(a)?a:[]; pitches=Array.isArray(p)?p:[];
    const c=document.querySelector('#countArchive');if(c)c.textContent=archive.length;
    const s=document.querySelector('#statPitch');if(s)s.textContent=pitches.length;
    const pc=document.querySelector('#countPitch');if(pc)pc.textContent=pitches.length;
  });
  function setActive(btn){document.querySelectorAll('.nav').forEach(n=>n.classList.remove('active'));btn.classList.add('active')}
  function renderPitch(){
    setActive(pitchButton); title.textContent='오늘 발제 아이템';
    const out=pitches.slice().sort((a,b)=>(b.pitchScore||0)-(a.pitchScore||0)); result.textContent=out.length+'개 아이템';
    cards.innerHTML=out.length?out.map((x,i)=>`<article class="card ${x.grade==='A'?'must':'follow'} pitch-card">
      <div class="card-top"><span class="badge ${x.grade==='A'?'must':'follow'}">발제 ${esc(x.grade||'B')} · ${esc(x.pitchScore)}점</span><span class="score">${i+1}위</span></div>
      <div class="meta">${esc(x.category||'산업')} · ${esc((x.companies||[]).join(', ')||'관련 기업')} · 출처 ${x.sourceCount||0}곳 · 글로벌 ${x.globalSignals||0}건</div>
      <div class="title">${esc(x.headline||'발제 아이템')}</div>
      <div class="quote"><b>기사 각도</b><br>${esc(x.angle||'복수 출처에서 확인된 사실을 종합해 추가 취재 각도를 제시합니다.')}</div>
      <div class="summary"><b class="why">왜 지금?</b><br>${esc(x.whyNow||'')}</div>
      ${x.numbers?.length?`<div class="signal-row">${x.numbers.slice(0,8).map(n=>`<span class="signal">${esc(n)}</span>`).join('')}</div>`:''}
      <div class="quote"><b>확인된 근거</b><ul>${(x.evidence||[]).slice(0,6).map(e=>`<li><b>${esc(e.source||'-')}</b> · ${esc(e.title||'-')}${e.url?` <a href="${esc(e.url)}" target="_blank" rel="noopener">원문↗</a>`:''}</li>`).join('')}</ul></div>
      <div class="quote"><b>먼저 확인할 질문</b><ul>${(x.questions||[]).slice(0,4).map(q=>`<li>${esc(q)}</li>`).join('')}</ul></div>
      <div class="bottom">${(x.companies||[]).map(c=>`<span class="tag">${esc(c)}</span>`).join('')}</div>
    </article>`).join(''):'<div class="card"><div class="summary">현재 복수 출처 교차검증을 통과한 발제 아이템이 없습니다. 다음 수집 주기에 다시 계산합니다.</div></div>';
  }
  function renderArchive(){
    setActive(archiveButton);title.textContent='단독·발제 아카이브';result.textContent=archive.length+'건';
    cards.innerHTML=archive.length?archive.map(x=>`<article class="card ${x.exclusive?'exclusive':'follow'}"><div class="card-top"><span class="badge ${x.exclusive?'exclusive':'follow'}">${x.exclusive?'단독 발견':'발제 후보 기록'}</span><span class="score">${x.exclusive?'단독':'발제 '+(x.pitchScore||0)}</span></div><div class="meta">최초 발견 ${esc(x.earliestObservedAt||x.published||'-')} · ${esc(x.earliestObservedSource||x.sourceName||'-')}</div><div class="title">${esc(x.global&&x.koTitle?x.koTitle:x.title)}</div><div class="summary">발견 당시 기사와 후속 확산 여부를 보존합니다. 현재 관련 매체: ${esc((x.coveredBy||[]).join(', ')||x.sourceName||'-')}</div><div class="bottom">${(x.companies||[]).slice(0,5).map(c=>`<span class="tag">${esc(c)}</span>`).join('')}</div></article>`).join(''):'<div class="card"><div class="summary">아카이브가 아직 없습니다.</div></div>';
  }
  pitchButton.addEventListener('click',async()=>{await load();renderPitch()});
  archiveButton.addEventListener('click',async()=>{await load();renderArchive()});
  document.querySelectorAll('.nav:not(.pitch-nav):not(.archive-nav)').forEach(n=>n.addEventListener('click',()=>{pitchButton.classList.remove('active');archiveButton.classList.remove('active')}));
  load();
})();
