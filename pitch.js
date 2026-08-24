(function(){
  const pitchButton=document.querySelector('.pitch-nav');
  const cards=document.querySelector('#cards');
  const title=document.querySelector('#viewTitle');
  const result=document.querySelector('#resultCount');
  if(!pitchButton||!cards) return;

  const esc=v=>String(v??'').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));
  let active=false;
  const majorDomestic=new Set(['연합뉴스','한국경제','매일경제','서울경제','이데일리','머니투데이','전자신문','조선비즈']);

  function build(){
    const arr=Array.isArray(window.ITEMS)?window.ITEMS:[];
    const clusters={};
    arr.forEach(x=>{const k=x.clusterId||x.id;(clusters[k]??=[]).push(x)});

    const out=[];
    Object.values(clusters).forEach(g=>{
      const domestic=g.filter(x=>!x.global);
      const global=g.filter(x=>x.global);
      const domesticSources=[...new Set(domestic.map(x=>x.sourceName).filter(Boolean))];
      const majorCount=domesticSources.filter(s=>majorDomestic.has(s)).length;
      const globalCount=global.length;
      const latest=g.reduce((a,b)=>new Date(a.published)>new Date(b.published)?a:b,g[0]);
      const text=g.map(x=>(x.title+' '+(x.summary||'')).toLowerCase()).join(' ');
      const companies=[...new Set(g.flatMap(x=>x.companies||[]))];
      const hard=['수주','계약','공급','증설','투자','공장','관세','리콜','파업','임단협','화재','배터리','자율주행','tariff','contract','investment','battery','recall','autonomous'];
      const impact=hard.filter(w=>text.includes(w.toLowerCase())).length;
      const age=Math.max(0,(Date.now()-new Date(latest.published).getTime())/3600000);
      let score=0;
      if(globalCount) score+=globalCount>=2?28:22;
      if(majorCount===0) score+=28; else if(majorCount===1) score+=18; else if(majorCount===2) score+=8;
      if(domesticSources.length<=1) score+=18; else if(domesticSources.length===2) score+=10;
      score+=Math.min(14,companies.length*4);
      score+=Math.min(18,impact*3);
      score+=age<12?12:age<24?8:age<48?4:0;
      if(g.some(x=>x.exclusive)) score+=8;
      score=Math.max(0,Math.min(99,score));
      if(score<52) return;
      const reasons=[];
      if(globalCount) reasons.push(`해외 주요 매체 신호 ${globalCount}건`);
      if(majorCount===0) reasons.push('국내 주요 매체 확산 미미');
      else if(majorCount===1) reasons.push('국내 주요 매체 1곳만 확인');
      if(domesticSources.length<=1) reasons.push('국내 보도원 1곳 이하');
      if(companies.length) reasons.push(`관련 기업 ${companies.slice(0,3).join(', ')}`);
      if(impact) reasons.push(`산업 핵심 키워드 ${impact}개`);
      const q=[];
      if(globalCount && majorCount===0) q.push('해외에서 보도된 내용이 국내 사업·생산·공급망에도 적용되는가?');
      if(companies.length) q.push(`${companies.slice(0,2).join('·')} 측에 사실관계와 추가 변동 여부 확인`);
      if(text.includes('수주')||text.includes('contract')) q.push('계약 규모·고객사·공급 기간을 확인');
      if(text.includes('공장')||text.includes('투자')||text.includes('investment')) q.push('투자액·생산능력·가동 시점을 확인');
      if(text.includes('관세')||text.includes('tariff')) q.push('관세 적용 범위와 가격·생산지 영향 확인');
      if(!q.length) q.push('회사 공식 입장과 업계 추가 취재로 새 정보 여부 확인');
      out.push({score,latest,g,domesticSources,majorCount,globalCount,reasons,q});
    });
    return out.sort((a,b)=>b.score-a.score).slice(0,15);
  }

  function render(){
    active=true;
    document.querySelectorAll('.nav').forEach(n=>n.classList.remove('active'));
    pitchButton.classList.add('active');
    title.textContent='오늘 발제할 만한 것';
    const out=build();
    result.textContent=`${out.length}건`;
    cards.innerHTML=out.length?out.map((p,i)=>{
      const x=p.latest;
      const titleText=x.global&&x.koTitle?x.koTitle:x.title;
      return `<article class="card ${p.score>=80?'must':p.score>=65?'follow':'normal'} pitch-card">
        <div class="card-top"><span class="badge ${p.score>=80?'must':'follow'}">발제 가능성 ${p.score}</span><span class="score">${i+1}위</span></div>
        <div class="meta">${esc(x.sourceName)} · ${esc(x.publishedLabel||x.published)} · ${p.globalCount?'글로벌 신호 '+p.globalCount+'건':'국내 이슈'}</div>
        <div class="title">${esc(titleText)}</div>
        ${x.global&&x.title!==titleText?`<div class="muted" style="font-size:11px;margin-bottom:7px">원문: ${esc(x.title)}</div>`:''}
        <div class="summary"><b class="why">왜 발제 후보인가</b><br>${p.reasons.map(esc).join(' · ')}</div>
        <div class="signal-row"><span class="signal">국내 매체 ${p.domesticSources.length}곳</span><span class="signal">주요 매체 ${p.majorCount}곳</span><span class="signal">관련 기사 ${p.g.length}건</span></div>
        <div class="quote"><b>먼저 확인할 질문</b><ul>${p.q.slice(0,3).map(q=>`<li>${esc(q)}</li>`).join('')}</ul></div>
        <div class="bottom">${[...new Set(p.g.flatMap(g=>g.companies||[]))].slice(0,5).map(c=>`<span class="tag">${esc(c)}</span>`).join('')}</div>
      </article>`;
    }).join(''):`<div class="card"><div class="summary">현재 발제 후보로 판단되는 이슈가 없습니다.</div></div>`;
  }

  pitchButton.addEventListener('click',render);
  document.querySelectorAll('.nav:not(.pitch-nav)').forEach(n=>n.addEventListener('click',()=>{
    if(active){active=false;pitchButton.classList.remove('active')}
  }));
})();
