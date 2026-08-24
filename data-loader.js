(async()=>{
  const showError=(message)=>{
    const cards=document.querySelector('#cards');
    if(cards) cards.innerHTML=`<div class="card must"><div class="title">데이터 로딩 오류</div><div class="summary">${String(message).replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]))}</div></div>`;
    const today=document.querySelector('#today');
    if(today) today.textContent='뉴스 데이터 연결을 확인하세요.';
  };
  try{
    const res=await fetch(`./data.json?v=${Date.now()}`,{cache:'no-store'});
    if(!res.ok) throw new Error(`data.json HTTP ${res.status}`);
    const payload=await res.json();
    if(!Array.isArray(payload)) throw new Error('data.json 형식 오류');
    if(typeof items==='undefined'||typeof render!=='function'||typeof counts!=='function'||typeof setupCompanies!=='function') throw new Error('페이지 스크립트 초기화 오류');
    items=payload;
    counts();
    setupCompanies();
    render();
    const today=document.querySelector('#today');
    if(today) today.textContent=`${items.length}건 로드 · 30분 주기 자동 수집 · 경쟁지 선행 이슈와 후속 취재 후보를 분리`;
  }catch(err){
    console.error('Auto Desk feed load failed',err);
    showError(err&&err.message?err.message:'알 수 없는 오류');
  }
})();
