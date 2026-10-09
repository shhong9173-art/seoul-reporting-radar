(function(){
  const nav=document.querySelector('.scoop-nav'),cards=document.querySelector('#cards'),title=document.querySelector('#viewTitle'),result=document.querySelector('#resultCount');
  if(!nav||!cards)return;
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let doc={items:[]};
  function load(){return fetch('scoop.json?v='+Date.now(),{cache:'no-store'}).then(r=>r.ok?r.json():{items:[]}).then(x=>{doc=x||{items:[]};});}
  function render(){
    document.querySelectorAll('.nav').forEach(n=>n.classList.remove('active'));nav.classList.add('active');
    title.textContent='단독감 레이더 — 취재 단서와 검증 후보';
    const items=doc.items||[];
    const leads=(doc.leadSignals||[]).filter(l=>!items.some(x=>(x.originalSourceUrl&&x.originalSourceUrl===l.url)||(x.whatConfirmed&&x.whatConfirmed===l.title)));
    const publicSignals=doc.publicSignals||[];
    result.textContent=items.length+'건 단독 후보 · '+leads.length+'건 미확정 단서 · '+publicSignals.length+'건 공개 원자료';
    const count=document.querySelector('#countScoop');if(count)count.textContent=items.length;
    const c=doc.counts||{};
    const leadCards=leads.map(x=>{
      const numbers=(x.numbers||[]).slice(0,4), qs=(x.questions||[]).slice(0,3);
      return '<article class="card scoop-lead-card">'+
        '<div class="card-top"><span class="badge normal">취재 단서 · 단독 미확정</span><span class="score" style="color:#53616b">'+esc(x.leadStrength||'보통')+' 신호</span></div>'+
        '<div class="meta"><b>'+esc((x.companies||[]).join(', ')||x.beat||'산업 전반')+'</b> · '+esc(x.originalSource||x.sourceName||'원자료')+' · '+esc(x.published||'-')+'</div>'+
        '<div class="title">'+esc(x.title||'')+'</div>'+
        (x.summary?'<div class="summary">'+esc(x.summary)+'</div>':'')+
        '<div class="scoop-block"><b>왜 추적하나</b><p>'+esc(x.whyLead||'최근 원자료에서 포착된 신호입니다. 실제 변화와 기존 계획 대비 차이를 확인해야 합니다.')+'</p></div>'+
        (numbers.length?'<div class="signal-row compact-signals">'+numbers.map(n=>'<span class="signal">'+esc(n)+'</span>').join('')+'</div>':'')+
        '<div class="scoop-block"><b>우선 확인 질문</b><ul>'+qs.map(q=>'<li>'+esc(q)+'</li>').join('')+'</ul></div>'+
        '<div class="scoop-rule">'+esc(x.coverageStatus||'언론 전체 보도 여부 미검증')+'</div>'+
        '<div class="scoop-actions"><a href="'+esc(x.url||'#')+'" target="_blank" rel="noopener">원문 확인 ↗</a><span>'+esc(x.kind||'산업 신호')+'</span></div>'+
        '</article>';
    }).join('');
    const publicCards=publicSignals.map(x=>{
      const qs=(x.questions||[]).slice(0,3), details=(x.details||[]).slice(0,8);
      return '<article class="card scoop-lead-card">'+
        '<div class="card-top"><span class="badge normal">공개 원자료 · 단독 아님</span><span class="score" style="color:#53616b">'+esc(x.signalGroup||x.kind||'원자료')+'</span></div>'+
        '<div class="meta"><b>'+esc((x.companies||[]).join(', ')||'산업 전반')+'</b> · '+esc(x.sourceName||'공식자료')+' · '+esc(x.published||'-')+'</div>'+
        '<div class="title">'+esc(x.title||'')+'</div>'+
        (details.length?'<div class="scoop-block"><b>원자료 항목</b><ul>'+details.map(t=>'<li>'+esc(t)+'</li>').join('')+'</ul></div>':'')+
        '<div class="scoop-block"><b>후속 취재 가능성</b><p>'+esc(x.whyFollowup||'공개 원자료에서 확인된 변화를 바탕으로 추가 취재 가치를 점검합니다.')+'</p></div>'+
        '<div class="scoop-block"><b>확인 질문</b><ul>'+qs.map(q=>'<li>'+esc(q)+'</li>').join('')+'</ul></div>'+
        '<div class="scoop-rule">'+esc(x.coverageStatus||'공개 자료입니다. 단독 여부를 주장하지 않습니다.')+'</div>'+
        '<div class="scoop-actions"><a href="'+esc(x.url||'#')+'" target="_blank" rel="noopener">공식 원문 ↗</a><span>'+esc(x.verification||'공개 원자료 · 단독 아님')+'</span></div>'+
        '</article>';
    }).join('');
    const candidateCards=items.map(x=>{
      const sources=(x.sources||[]).slice(0,4), nums=(x.numbers||[]).slice(0,5), matches=(x.newsroomMatches||[]).slice(0,4);
      return '<article class="card scoop-card">'+
        '<div class="card-top"><span class="badge '+(x.score>=88?'must':'follow')+'">'+esc(x.status||'단독 후보')+'</span><span class="score">'+esc(x.score||0)+'점</span></div><div class="meta" style="margin-top:-2px"><span class="tag">'+esc(x.kind||'단독 후보')+'</span></div>'+
        '<div class="meta"><b>'+esc(x.beat||'정책·통상')+'</b> · 원자료 '+esc(x.originalSource||x.firstSeenSource||'-')+' · '+esc(x.firstSeenAt||'-')+'</div>'+
        '<div class="title">'+esc(x.title||'')+'</div>'+
        '<div class="scoop-status"><span>보도 매칭 '+(x.coverageCount===0?'없음':'△ '+esc(x.coverageCount)+'건')+'</span><span>'+esc(x.verification||'원문 확인 필요')+'</span></div>'+
        '<div class="scoop-block"><b>왜 후보인가?</b><p>'+esc(x.why||'')+'</p></div>'+
        '<div class="scoop-block"><b>원자료에서 확인된 사실</b><p>'+esc(x.whatConfirmed||'')+'</p></div>'+
        '<div class="scoop-pitch"><b>취재 각도</b><p>'+esc(x.pitch||'')+'</p></div>'+
        '<div class="scoop-block"><b>실제 확인할 것</b><p>'+esc(x.angle||'')+'</p></div>'+
        (nums.length?'<div class="signal-row compact-signals">'+nums.map(n=>'<span class="signal">'+esc(n)+'</span>').join('')+'</div>':'')+
        '<details class="pitch-details"><summary>원문·기존 보도·확인 질문</summary>'+
        '<div class="quote"><b>원자료</b><ul>'+sources.map(s=>'<li>'+esc(s.label||s.source||'-')+' · '+esc(s.title||'')+(s.url?' <a href="'+esc(s.url)+'" target="_blank" rel="noopener">원문↗</a>':'')+'</li>').join('')+'</ul></div>'+
        (matches.length?'<div class="quote"><b>검색된 기존 기사</b><ul>'+matches.map(m=>'<li>'+esc(m.source||'-')+' · '+esc(m.title||'')+'</li>').join('')+'</ul></div>':'<div class="quote"><b>검색된 기존 기사</b><p>동일 사실 매칭 없음. 미보도 확정은 아닙니다.</p></div>')+
        ((x.history||[]).length?'<div class="quote"><b>과거 유사 기사</b><ul>'+x.history.slice(0,3).map(h=>'<li>'+esc(h.source||'-')+' · '+esc(h.title||'')+'</li>').join('')+'</ul></div>':'')+
        '<div class="quote"><b>바로 확인할 질문</b><ul>'+(x.questions||[]).slice(0,4).map(q=>'<li>'+esc(q)+'</li>').join('')+'</ul></div>'+
        '</details></article>';
    }).join('');
    cards.innerHTML=
      '<div class="scoop-overview">'+
      '<div><b>원자료 탐색</b><span>'+esc(c.primaryHits||0)+'건</span></div>'+
      '<div><b>공개 원자료 추적</b><span>'+esc(publicSignals.length)+'건</span></div>'+
      '<div><b>취재 단서</b><span>'+esc(leads.length)+'건</span></div>'+
      '<div><b>단독 후보</b><span>'+esc(c.candidates||0)+'건</span></div>'+
      '</div>'+
      '<div class="scoop-rule">구분 원칙: ‘취재 단서’는 확인이 필요한 신호일 뿐 단독이 아닙니다. ‘단독 후보’도 원문·보도 여부·출입처 확인 전에는 확정하지 않습니다.</div>'+
      (doc.sourceHealth&&doc.sourceHealth.dart&&doc.sourceHealth.dart.status!=='ok'?'<div class="scoop-rule" style="border-left:3px solid #b66a00;padding:10px 12px;background:#fffaf0"><b>소스 상태 경고 · DART</b><p>공시 원자료 수집이 정상 작동하지 않습니다. '+esc((doc.sourceHealth.dart.errors||[]).map(e=>e.error||e.message||JSON.stringify(e)).join(' / ')||'공시 데이터 0건')+'</p></div>':'')+
      (doc.sourceHealth&&doc.sourceHealth.dartNumeric&&doc.sourceHealth.dartNumeric.errorCount>0?'<div class="scoop-rule" style="border-left:3px solid #b66a00;padding:10px 12px;background:#fffaf0"><b>원문 수치 추출 경고 · DART</b><p>공시 목록 '+esc(doc.sourceHealth.dartNumeric.count||0)+'건 중 원문 수치 추출 '+esc(doc.sourceHealth.dartNumeric.errorCount||0)+'건 실패, 시스템 점검 응답 '+esc(doc.sourceHealth.dartNumeric.maintenanceCount||0)+'건. 상세 숫자는 복구 전까지 취재 사실로 사용하지 않습니다.</p><p>'+esc((doc.sourceHealth.dartNumeric.errors||[]).map(e=>(e.company||'')+' '+(e.error||'')).join(' / '))+'</p></div>':'')+
      (doc.leadDiagnostics?'<details class="pitch-details"><summary>취재 단서 탐색 진단</summary><div class="signal-row">'+Object.entries(doc.leadDiagnostics).map(([k,v])=>'<span class="signal">'+esc(k)+' '+esc(v)+'</span>').join('')+'</div></details>':'')+
      '<h2 class="scoop-section-title">1. 공개 원자료 추적 <span>공개 사실 · 단독으로 다루지 않음</span></h2>'+
      (publicSignals.length?publicCards:'<div class="card"><div class="summary">현재 추적할 만한 공개 원자료가 없습니다.</div></div>')+
      (leads.length?'<h2 class="scoop-section-title">2. 취재 선행신호 <span>전화 취재로 확인할 미확정 단서</span></h2>'+leadCards:'<div class="card"><div class="summary">현재 검증 기준을 통과한 미확정 취재 단서가 없습니다. 공개 발표를 단독 후보로 대체하지 않았습니다.</div></div>')+
      '<h2 class="scoop-section-title">3. 단독 후보 <span>보도 매칭·원자료 검토 단계</span></h2>'+
      (items.length?candidateCards:'<div class="card"><div class="summary">현재 검증 관문을 통과한 단독 후보가 없습니다. 숫자를 채우기 위해 공개 발표를 단독 후보로 올리지 않습니다.</div></div>')+
      (doc.dropStats?'<details class="pitch-details"><summary>레이더 진단 · 탈락 사유</summary><div class="signal-row">'+Object.entries(doc.dropStats).map(([k,v])=>'<span class="signal">'+esc(k)+' '+esc(v)+'</span>').join('')+'</div></details>':'');
  }
  nav.addEventListener('click',async e=>{e.preventDefault();await load();render();});
  load().then(()=>{const count=document.querySelector('#countScoop');if(count)count.textContent=(doc.items||[]).length;});
})();