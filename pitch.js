(function(){
  const pitchButton=document.querySelector('.pitch-nav'), archiveButton=document.querySelector('.archive-nav'), cards=document.querySelector('#cards'), title=document.querySelector('#viewTitle'), result=document.querySelector('#resultCount');
  if(!pitchButton||!cards)return;
  const esc=v=>String(v??'').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));
  let archive=[], pitches=[];
  fetch('archive.json?v='+Date.now(),{cache:'no-store'}).then(r=>r.ok?r.json():[]).then(v=>{archive=Array.isArray(v)?v:[];const c=document.querySelector('#countArchive');if(c)c.textContent=archive.length}).catch(()=>{});
  fetch('pitch.json?v='+Date.now(),{cache:'no-store'}).then(r=>r.ok?r.json():[]).then(v=>{pitches=Array.isArray(v)?v:[];const c=document.querySelector('#countPitch');if(c)c.textContent=pitches.length;const s=document.querySelector('#statPitch');if(s)s.textContent=pitches.length}).catch(()=>{});
  function setActive(btn){document.querySelectorAll('.nav').forEach(n=>n.classList.remove('active'));btn.classList.add('active')}
  function renderPitch(){
    setActive(pitchButton);title.textContent='오늘 발제 아이템';
    const out=pitches.slice().sort((a,b)=>(b.pitchScore||0)-(a.pitchScore||0)); result.textContent=out.length+'건';
    cards.innerHTML=out.length?out.map((x,i)=>`<article class="card ${x.grade==='A'?'must':'follow'} pitch-card"><div class="card-top"><span class="badge ${x.grade==='A'?'must':'follow'}">발제 ${x.grade} · ${x.pitchScore}점</span><span class="score">${i+1}위</span></div><div class="meta">${esc(x.category||'산업')} · ${esc((x.companies||[]).join(', ')||'관련 기업 확인 필요')} · 출처 ${x.sourceCount||0}곳</div><div class="title">${esc(x.headline)}</div><div class="summary"><b class="why">기사 각도</b><br>${esc(x.angle||'복수 출처를 교차해 새로운 정보 조합을 찾은 후보입니다.')}</div><div class="signal-row"><span class="signal">숫자 신호 ${esc((x.numbers||[]).join(', ')||'없음')}</span><span class="signal">글로벌 ${x.globalSignals||0}건</span></div><div class="quote"><b>확인된 근거</b><ul>${(x.evidence||[]).map(e=>`<li><b>${esc(e.source||'-')}</b> · ${esc(e.title||'-')}</li>`).join('')}</ul></div><div class="quote"><b>먼저 확인할 질문</b><ul>${(x.questions||[]).map(q=>`<li>${esc(q)}</li>`).join('')}</ul></div><div class="bottom">${(x.numbers||[]).map(n=>`<span class="tag">${esc(n)}</span>`).join('')}</div></article>`).join(''):'<div class="card"><div class="summary">현재 복수 출처를 교차해 만들 수 있는 발제 아이템이 없습니다. 다음 수집 주기에 다시 계산합니다.</div></div>';
  }
  function renderArchive(){
    setActive(archiveButton);title.textContent='단독·발제 아카이브';result.textContent=archive.length+'건';
    cards.innerHTML=archive.length?archive.map(x=>`<article class="card ${x.exclusive?'exclusive':'follow'}" onclick="openItem('${esc(x.id)}')"><div class="card-top"><span class="badge ${x.exclusive?'exclusive':'follow'}">${x.exclusive?'단독 발견':'발제 후보 기록'}</span><span class="score">${x.exclusive?'단독':'발제 '+(x.pitchScore||0)}</span></div><div class="meta">최초 발견 ${esc(x.earliestObservedAt||x.published||'-')} · ${esc(x.earliestObservedSource||x.sourceName||'-')}</div><div class="title">${esc(x.global&&x.koTitle?x.koTitle:x.title)}</div><div class="summary">발견 당시 기사와 후속 확산 여부를 보존합니다. 현재 관련 매체: ${esc((x.coveredBy||[]).join(', ')||x.sourceName||'-')}</div><div class="bottom">${(x.companies||[]).slice(0,5).map(c=>`<span class="tag">${esc(c)}</span>`).join('')}</div></article>`).join(''):'<div class="card"><div class="summary">아카이브가 아직 없습니다.</div></div>';
  }
  pitchButton.addEventListener('click',renderPitch);archiveButton.addEventListener('click',renderArchive);
  document.querySelectorAll('.nav:not(.pitch-nav):not(.archive-nav)').forEach(n=>n.addEventListener('click',()=>{pitchButton.classList.remove('active');archiveButton.classList.remove('active')}));
  renderPitch();
})();
