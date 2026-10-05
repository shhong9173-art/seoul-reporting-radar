(function(){
  const nav=document.querySelector('.scoop-nav');
  const cards=document.querySelector('#cards');
  const title=document.querySelector('#viewTitle');
  const result=document.querySelector('#resultCount');
  if(!nav||!cards)return;
  const esc=v=>String(v??'').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));
  let doc={items:[]};

  function setActive(){
    document.querySelectorAll('.nav').forEach(n=>n.classList.remove('active'));
    nav.classList.add('active');
  }

  function load(){
    return fetch('scoop.json?v='+Date.now(),{cache:'no-store'})
      .then(r=>r.ok?r.json():{items:[]})
      .then(x=>{doc=(x&&Array.isArray(x.items))?x:{items:[]};});
  }

  function render(){
    setActive();
    title.textContent='단독감 레이더';
    const items=doc.items||[];
    result.textContent=items.length+'건';
    const count=document.querySelector('#countScoop');
    if(count)count.textContent=items.length;
    const meta=doc.counts||{};
    cards.innerHTML=
      '<div class="scoop-overview">'+
      '<div><b>웹 탐색</b><span>'+esc(meta.hits||0)+'건</span></div>'+
      '<div><b>단독감</b><span>'+esc(meta.candidates||0)+'건</span></div>'+
      '<div><b>출처</b><span>Google·Bing</span></div>'+
      '<div><b>최근</b><span>7일</span></div>'+
      '</div>'+
      (items.length?items.map((x,i)=>{
        const srcs=(x.sources||[]).slice(0,4);
        const nums=(x.numbers||[]).slice(0,4);
        return '<article class="card scoop-card">'+
          '<div class="card-top"><span class="badge '+(x.score>=80?'must':'follow')+'">'+esc(x.kind||'단독감')+'</span><span class="score">'+esc(x.score||0)+'점</span></div>'+
          '<div class="meta"><b>'+esc(x.beat||'산업부')+'</b> · '+esc(x.firstSeenSource||'-')+' · '+esc(x.firstSeenAt||'-')+'</div>'+
          '<div class="title">'+esc(x.title||'')+'</div>'+
          '<div class="scoop-block"><b>왜 기사감?</b><p>'+esc(x.why||'')+'</p></div>'+
          '<div class="scoop-block"><b>확인된 것</b><p>'+esc(x.whatConfirmed||'')+'</p></div>'+
          '<div class="scoop-block"><b>취재 포인트</b><p>'+esc(x.angle||'')+'</p></div>'+
          '<div class="scoop-pitch"><b>발제 문장</b><p>'+esc(x.pitch||'')+'</p></div>'+
          (nums.length?'<div class="signal-row compact-signals">'+nums.map(n=>'<span class="signal">'+esc(n)+'</span>').join('')+'</div>':'')+
          '<details class="pitch-details"><summary>원문·지난 기사·확인 질문</summary>'+
          '<div class="quote"><b>검색에서 확인된 매체</b><ul>'+srcs.map(s=>'<li>'+esc(s.source||'-')+' · '+esc(s.title||'')+(s.url?' <a href="'+esc(s.url)+'" target="_blank" rel="noopener">원문↗</a>':'')+'</li>').join('')+'</ul></div>'+
          ((x.history||[]).length?'<div class="quote"><b>과거 DB 유사 기사</b><ul>'+x.history.slice(0,3).map(h=>'<li>'+esc(h.source||'-')+' · '+esc(h.title||'')+'</li>').join('')+'</ul></div>':'')+
          '<div class="quote"><b>바로 확인할 질문</b><ul>'+(x.questions||[]).slice(0,4).map(q=>'<li>'+esc(q)+'</li>').join('')+'</ul></div>'+
          '</details></article>';
      }).join(''):'<div class="card"><div class="summary">현재 확산 전 기사감 후보가 없습니다. 다음 탐색 주기에 다시 검색합니다.</div></div>');
  }

  nav.addEventListener('click',async e=>{
    e.preventDefault();
    await load();
    render();
  });
  load().then(()=>{
    const count=document.querySelector('#countScoop');
    if(count)count.textContent=(doc.items||[]).length;
  });
})();