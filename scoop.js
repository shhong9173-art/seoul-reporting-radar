(function(){
  const nav=document.querySelector('.scoop-nav'),cards=document.querySelector('#cards'),title=document.querySelector('#viewTitle'),result=document.querySelector('#resultCount');
  if(!nav||!cards)return;
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let doc={items:[]};
  // 오늘의 레이더(워커 /b/open) — 11-01 기자 결정: 열쇠 없이 홈페이지 탭에 바로 띄운다(누구나 볼 수 있음을 알고 고름).
  const RB_API='https://seoul-reporting-radar.shhong9173.workers.dev/b/open';
  let rbHours='';
  function loadPrivate(){
    if(typeof fetch!=='function')return Promise.resolve({state:'error',error:'fetch 없음'});
    return fetch(RB_API+(rbHours?'?hours='+rbHours:''),{cache:'no-store',credentials:'omit'})
      .then(r=>r.ok?r.text().then(html=>({state:'ok',html})):{state:'error',error:'HTTP '+r.status})
      .catch(e=>({state:'error',error:String(e&&e.message||e)}));
  }
  function setCount(html){const m=/data-a="(\d+)" data-b="(\d+)"/.exec(html||'');const c=document.querySelector('#countScoop');if(m&&c)c.textContent=String(Number(m[1])+Number(m[2]));}
  function privateBox(){
    return '<section class="rb-home"><h2 class="scoop-section-title">오늘의 레이더 <span>기자 전용 감시 23곳의 새 항목 A·B · 자동 보도 대조(미보도 후보)</span></h2>'+
      '<div class="rb-home-tools" style="display:flex;gap:8px;margin:6px 0 10px"><select id="rbHours"><option value="">기본(24시간, 월요일 72시간)</option><option value="72">72시간</option><option value="168">7일</option></select></div>'+
      '<div id="rbBody"><div class="card"><div class="summary">불러오는 중…</div></div></div></section>';
  }
  function fillPrivate(){
    const body=document.querySelector('#rbBody');if(!body)return;
    const sel=document.querySelector('#rbHours');if(sel){sel.value=rbHours;sel.onchange=()=>{rbHours=sel.value;fillPrivate();};}
    loadPrivate().then(r=>{
      if(r.state==='ok'){body.innerHTML=r.html;setCount(r.html);return;}
      body.innerHTML='<div class="card"><div class="summary"><b>오늘의 레이더를 불러오지 못했습니다</b>('+esc(r.error)+') — 미확인이지 0건이 아닙니다. Claude에서 radar_today로 볼 수 있습니다.</div></div>';
    });
  }
  function load(){return fetch('scoop.json?v='+Date.now(),{cache:'no-store'}).then(r=>r.ok?r.json():{items:[]}).then(x=>{doc=x||{items:[]};});}
  function render(){
    document.querySelectorAll('.nav').forEach(n=>n.classList.remove('active'));nav.classList.add('active');
    title.textContent='단독감 레이더 — 취재 단서와 검증 후보';
    const items=doc.items||[];
    const leads=(doc.leadSignals||[]).filter(l=>!items.some(x=>(x.originalSourceUrl&&x.originalSourceUrl===l.url)||(x.whatConfirmed&&x.whatConfirmed===l.title)));
    const publicSignals=doc.publicSignals||[];
    result.textContent='공개 수집기: '+items.length+'건 단독 후보 · '+leads.length+'건 미확정 단서 · '+publicSignals.length+'건 공개 원자료';
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
        '<div class="scoop-status"><span>관련 기사 색인 '+(x.coverageCount===0?'강한 매칭 0건 (미보도 확인 아님)':'유사 보도 '+esc(x.coverageCount)+'건 (전문 미확인)')+'</span><span>'+esc(x.verification||'원문·기보도 전문 확인 필요')+'</span></div>'+
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
      privateBox()+
      '<h2 class="scoop-section-title" style="margin-top:28px">참고: 공개 수집기 결과 <span>누구나 보는 공개 자료 · 단독 후보 관문을 통과한 것만 후보로 표시</span></h2>'+
      '<div class="scoop-overview">'+
      '<div><b>원자료 탐색</b><span>'+esc(c.primaryHits||0)+'건</span></div>'+
      '<div><b>공개 원자료 추적</b><span>'+esc(publicSignals.length)+'건</span></div>'+
      '<div><b>취재 단서</b><span>'+esc(leads.length)+'건</span></div>'+
      '<div><b>단독 후보</b><span>'+esc(c.candidates||0)+'건</span></div>'+
      '</div>'+
      '<div class="scoop-rule">구분 원칙: ‘취재 단서’는 확인이 필요한 신호일 뿐 단독이 아닙니다. ‘단독 후보’도 원문·보도 여부·출입처 확인 전에는 확정하지 않습니다.</div>'+
      (doc.sourceHealth&&doc.sourceHealth.dart&&['error','partial'].includes(doc.sourceHealth.dart.status)?'<div class="scoop-rule" style="border-left:3px solid #b66a00;padding:10px 12px;background:#fffaf0"><b>소스 상태 경고 · DART</b><p>공시 원자료 수집이 정상 작동하지 않습니다. '+esc((doc.sourceHealth.dart.errors||[]).map(e=>e.error||e.message||JSON.stringify(e)).join(' / ')||'공시 데이터 0건')+'</p></div>':'')+
      (doc.sourceHealth&&doc.sourceHealth.dartNumeric&&doc.sourceHealth.dartNumeric.errorCount>0?'<details class="pitch-details"><summary>DART 원문 수치 추출: '+esc(doc.sourceHealth.dartNumeric.count||0)+'건 중 '+esc(doc.sourceHealth.dartNumeric.errorCount||0)+'건 숫자 못 뽑음'+(doc.sourceHealth.dartNumeric.maintenanceCount?' · 시스템 점검 응답 '+esc(doc.sourceHealth.dartNumeric.maintenanceCount)+'건':'')+' (숫자가 없는 공시일 수 있음 — 해당 공시 숫자는 원문으로 확인)</summary><p class="muted">'+esc((doc.sourceHealth.dartNumeric.errors||[]).map(e=>(e.company||'')+' '+(e.report||'')).join(' / '))+'</p></details>':'')+
      (doc.sourceHealth&&(doc.sourceHealth.dartCandidateAlignment!=='current'||doc.sourceHealth.dartNumeric?.sourceAlignment!=='current')?'<div class="scoop-rule"><b>DART 자료 갱신 확인 필요</b><p>현재 공시 파일과 이 후보·수치 분석에 사용한 자료가 일치하는지 확인되지 않았습니다. 아래 후보는 이전 분석 결과일 수 있습니다.</p></div>':'')+
      (doc.sourceHealth&&doc.sourceHealth.dart?.status==='empty'?'<div class="scoop-rule">DART 목록 조회 완료 · 해당 조회 범위의 관련 공시 0건</div>':'')+
      (doc.sourceHealth?.dartRefresh?.status==='error'?'<div class="scoop-rule"><b>DART 갱신 실패 · 이전 자료 표시 중</b><p>최근 조회에 실패해 기존 자료를 유지했습니다. 새 공시가 없다는 뜻이 아닙니다. 마지막 자료 생성: '+esc(doc.sourceHealth.dart?.generatedAt||'미확인')+' / 조회 시도: '+esc(doc.sourceHealth.dartRefresh.attemptedAt||'미확인')+'</p></div>':'')+
      (doc.leadDiagnostics?'<details class="pitch-details"><summary>취재 단서 탐색 진단</summary><div class="signal-row">'+Object.entries(doc.leadDiagnostics).map(([k,v])=>'<span class="signal">'+esc(k)+' '+esc(v)+'</span>').join('')+'</div></details>':'')+
      '<h2 class="scoop-section-title">1. 공개 원자료 추적 <span>공개 사실 · 단독으로 다루지 않음</span></h2>'+
      (publicSignals.length?publicCards:'<div class="card"><div class="summary">현재 추적할 만한 공개 원자료가 없습니다.</div></div>')+
      (leads.length?'<h2 class="scoop-section-title">2. 취재 선행신호 <span>전화 취재로 확인할 미확정 단서</span></h2>'+leadCards:'<div class="card"><div class="summary">현재 검증 기준을 통과한 미확정 취재 단서가 없습니다. 공개 발표를 단독 후보로 대체하지 않았습니다.</div></div>')+
      '<h2 class="scoop-section-title">3. 단독 후보 <span>보도 매칭·원자료 검토 단계</span></h2>'+
      (items.length?candidateCards:'<div class="card"><div class="summary">현재 검증 관문을 통과한 단독 후보가 없습니다. 숫자를 채우기 위해 공개 발표를 단독 후보로 올리지 않습니다.</div></div>')+
      (doc.dropStats?'<details class="pitch-details"><summary>레이더 진단 · 탈락 사유</summary><div class="signal-row">'+Object.entries(doc.dropStats).map(([k,v])=>'<span class="signal">'+esc(k)+' '+esc(v)+'</span>').join('')+'</div></details>':'');
  }
  nav.addEventListener('click',async e=>{e.preventDefault();await load();render();fillPrivate();});
  load().then(()=>{
    loadPrivate().then(r=>{if(r.state==='ok')setCount(r.html);});   // 탭 숫자는 오늘의 레이더 A+B
  });
})();