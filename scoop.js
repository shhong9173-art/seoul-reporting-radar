(function(){
  const nav=document.querySelector('.scoop-nav'),cards=document.querySelector('#cards'),title=document.querySelector('#viewTitle'),result=document.querySelector('#resultCount');
  if(!nav||!cards)return;
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let doc={items:[]};
  function load(){return fetch('scoop.json?v='+Date.now(),{cache:'no-store'}).then(r=>r.ok?r.json():{items:[]}).then(x=>{doc=x||{items:[]};});}
  function render(){
    document.querySelectorAll('.nav').forEach(n=>n.classList.remove('active'));nav.classList.add('active');
    title.textContent='단독감 레이더 — 원자료 우선';
    const items=doc.items||[]; result.textContent=items.length+'건';
    const count=document.querySelector('#countScoop');if(count)count.textContent=items.length;
    const c=doc.counts||{};
    cards.innerHTML=
      '<div class="scoop-overview">'+
      '<div><b>원자료 탐색</b><span>'+esc(c.primaryHits||0)+'건</span></div>'+
      '<div><b>언론 미보도</b><span>'+esc(c.uncovered||0)+'건</span></div>'+
      '<div><b>후보</b><span>'+esc(c.candidates||0)+'건</span></div>'+
      '<div><b>탐색 범위</b><span>14일 · 원자료</span></div>'+
      '</div>'+
      '<div class="scoop-rule">언론 기사 자체를 단독감으로 올리지 않습니다. DART·정부·조달·특허·기업 원자료에서 먼저 신호를 찾고, 같은 사실이 이미 보도됐는지 대조합니다.</div>'+
      (items.length?items.map(x=>{
        const sources=(x.sources||[]).slice(0,4), nums=(x.numbers||[]).slice(0,5), matches=(x.newsroomMatches||[]).slice(0,4);
        return '<article class="card scoop-card">'+
          '<div class="card-top"><span class="badge '+(x.score>=88?'must':'follow')+'">'+esc(x.status||'미보도 후보')+'</span><span class="score">'+esc(x.score||0)+'점</span></div><div class="meta" style="margin-top:-2px"><span class="tag">'+esc(x.kind||'단독 후보')+'</span></div>'+
          '<div class="meta"><b>'+esc(x.beat||'정책·통상')+'</b> · 원자료 '+esc(x.originalSource||x.firstSeenSource||'-')+' · '+esc(x.firstSeenAt||'-')+'</div>'+
          '<div class="title">'+esc(x.title||'')+'</div>'+
          '<div class="scoop-status"><span>미보도 '+(x.coverageCount===0?'✓':'△ '+esc(x.coverageCount)+'건')+'</span><span>'+esc(x.verification||'원문 확인 필요')+'</span></div>'+
          '<div class="scoop-block"><b>왜 단독감?</b><p>'+esc(x.why||'')+'</p></div>'+
          '<div class="scoop-block"><b>원자료에서 잡힌 것</b><p>'+esc(x.whatConfirmed||'')+'</p></div>'+
          '<div class="scoop-pitch"><b>기사 각도</b><p>'+esc(x.pitch||'')+'</p></div>'+
          '<div class="scoop-block"><b>실제 확인할 것</b><p>'+esc(x.angle||'')+'</p></div>'+
          (nums.length?'<div class="signal-row compact-signals">'+nums.map(n=>'<span class="signal">'+esc(n)+'</span>').join('')+'</div>':'')+
          '<details class="pitch-details"><summary>원문·기존 보도·확인 질문</summary>'+
          '<div class="quote"><b>원자료</b><ul>'+sources.map(s=>'<li>'+esc(s.label||s.source||'-')+' · '+esc(s.title||'')+(s.url?' <a href="'+esc(s.url)+'" target="_blank" rel="noopener">원문↗</a>':'')+'</li>').join('')+'</ul></div>'+
          (matches.length?'<div class="quote"><b>검색된 기존 기사</b><ul>'+matches.map(m=>'<li>'+esc(m.source||'-')+' · '+esc(m.title||'')+'</li>').join('')+'</ul></div>':'<div class="quote"><b>검색된 기존 기사</b><p>동일 사실의 기사 매칭 없음</p></div>')+
          ((x.history||[]).length?'<div class="quote"><b>과거 유사 기사</b><ul>'+x.history.slice(0,3).map(h=>'<li>'+esc(h.source||'-')+' · '+esc(h.title||'')+'</li>').join('')+'</ul></div>':'')+
          '<div class="quote"><b>바로 확인할 질문</b><ul>'+(x.questions||[]).slice(0,4).map(q=>'<li>'+esc(q)+'</li>').join('')+'</ul></div>'+
          '</details></article>';
      }).join(''):'<div class="card"><div class="summary">현재 원자료에서 잡힌 미보도 후보가 없습니다. 다음 탐색 주기에 다시 확인합니다.</div></div>');
  }
  nav.addEventListener('click',async e=>{e.preventDefault();await load();render();});
  load().then(()=>{const count=document.querySelector('#countScoop');if(count)count.textContent=(doc.items||[]).length;});
})();