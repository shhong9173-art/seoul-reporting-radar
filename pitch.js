(function(){
  const pitchButton=document.querySelector('.pitch-nav'), archiveButton=document.querySelector('.archive-nav'), cards=document.querySelector('#cards'), title=document.querySelector('#viewTitle'), result=document.querySelector('#resultCount');
  if(!pitchButton||!cards)return;
  const esc=v=>String(v??'').replace(/[&<>\\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\\"':'&quot;',"'":'&#39;'}[c]));
  let archive=[],pitches=[];
  const load=()=>Promise.all([
    fetch('archive.json?v='+Date.now(),{cache:'no-store'}).then(r=>r.ok?r.json():[]).catch(()=>[]),
    fetch('pitch.json?v='+Date.now(),{cache:'no-store'}).then(r=>r.ok?r.json():[]).catch(()=>[])
  ]).then(([a,p])=>{
    archive=Array.isArray(a)?a:[];pitches=Array.isArray(p)?p:[];
    const c=document.querySelector('#countArchive');if(c)c.textContent=archive.length;
    const s=document.querySelector('#statPitch');if(s)s.textContent=pitches.length;
    const pc=document.querySelector('#countPitch');if(pc)pc.textContent=pitches.length;
  });
  function setActive(btn){document.querySelectorAll('.nav').forEach(n=>n.classList.remove('active'));btn.classList.add('active')}
  function evidenceLines(x){
    return (x.evidence||[]).slice(0,4).map(e=>{
      const nums=(e.numbers||[]).slice(0,4).join(', ');
      const body=[e.source||'-',e.title||'-',nums].filter(Boolean).join(' · ');
      return e.url?`<li>${esc(body)} <a href="${esc(e.url)}" target="_blank" rel="noopener">원문↗</a></li>`:`<li>${esc(body)}</li>`;
    }).join('');
  }
  function renderPitch(){
    setActive(pitchButton);title.textContent='오늘 발제 아이템';
    const out=pitches.slice().sort((a,b)=>(b.pitchScore||0)-(a.pitchScore||0));result.textContent=out.length+'개 아이템';
    cards.innerHTML=out.length?out.map((x,i)=>{
      const plan=(x.articlePlan||[]).slice(0,4);
      const numbers=(x.numbers||[]).slice(0,6);
      return `<article class="card ${x.grade==='A'?'must':'follow'} pitch-card">
        <div class="card-top"><span class="badge ${x.grade==='A'?'must':'follow'}">발제 ${esc(x.grade||'B')} · ${esc(x.pitchScore)}점</span><span class="score">${i+1}위</span></div>
        <div class="meta">${esc(x.category||'산업')} · ${esc((x.companies||[]).join(', ')||'관련 기업')} · 근거 ${Math.max(x.sourceCount||0, (x.evidence||[]).length)}개</div>
        <div class="title">${esc(x.headline||'발제 아이템')}</div>
        <div class="pitch-lead"><span>무엇을 쓸 기사인가</span><strong>${esc(x.angle||x.newFact||'')}</strong></div>
        ${plan.length?`<div class="pitch-plan"><b>기사 흐름</b><ol>${plan.map(v=>`<li>${esc(v)}</li>`).join('')}</ol></div>`:''}
        ${x.newFact?`<div class="pitch-fact"><b>핵심 근거</b><p>${esc(x.newFact)}</p></div>`:''}
        ${numbers.length?`<div class="signal-row compact-signals">${numbers.map(n=>`<span class="signal">${esc(n)}</span>`).join('')}</div>`:''}
        <details class="pitch-details">
          <summary>근거·DART·확인 질문 보기</summary>
          ${x.differentiator?`<div class="summary"><b class="why">기존 기사와 다른 점</b><br>${esc(x.differentiator)}</div>`:''}
          ${x.whyNow?`<div class="summary"><b class="why">왜 지금?</b><br>${esc(x.whyNow)}</div>`:''}
          ${x.dartNumericSignals?.length?`<div class="quote"><b>DART 원자료</b><ul>${x.dartNumericSignals.slice(0,4).map(e=>`<li><b>${esc(e.reportName||'공시')}</b> · ${esc((e.numbers||[]).slice(0,8).join(', '))}${e.url?` <a href="${esc(e.url)}" target="_blank" rel="noopener">원문↗</a>`:''}</li>`).join('')}</ul></div>`:''}
          <div class="quote"><b>확인된 근거</b><ul>${evidenceLines(x)}</ul></div>
          <div class="quote"><b>먼저 확인할 질문</b><ul>${(x.questions||[]).slice(0,4).map(q=>`<li>${esc(q)}</li>`).join('')}</ul></div>
        </details>
        <div class="bottom">${(x.companies||[]).map(c=>`<span class="tag">${esc(c)}</span>`).join('')}</div>
      </article>`;
    }).join(''):'<div class="card"><div class="summary">현재 원자료·복수 출처 교차검증을 통과한 발제 아이템이 없습니다. 다음 수집 주기에 다시 계산합니다.</div></div>';
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