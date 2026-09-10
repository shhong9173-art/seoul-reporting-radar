(function(){
  const CORE_CATS=new Set(['철강','비철금속','전력기기','전선·전력','에너지','재생에너지','화학·소재']);
  const MUST=['수주','계약','공급','증설','투자','신규공장','생산중단','가동','감산','철수','매각','인수','합작','관세','반덤핑','통상','가격','원가','마진','LME','전력망','변압기','HVDC','해저케이블','해상풍력','풍력','태양광','구조조정','스페셜티','배터리소재'];
  const SCOOP=['단독','취재결과','본지 취재','취재를 종합하면','확인한 결과','확인됐다'];
  const NOISE=['주가','증권','목표주가','급등','급락','추천','관련주','테마주','특징주','주목할 종목','증시','시장 기대','주목받고 있다','전망치'];
  const EVENT=['인베스터데이','주주총회','설명회','세미나','포럼','엑스포','컨퍼런스','부스투어','기조연설','발표회'];
  const TARGETS={
    '철강':['포스코홀딩스','포스코','현대제철','동국제강','세아제강'],
    '비철금속':['고려아연','영풍','LS MnM','풍산'],
    '전력기기':['두산에너빌리티','HD현대일렉트릭','LS ELECTRIC','효성중공업','일진전기'],
    '전선·전력':['LS전선','대한전선','가온전선','대원전선'],
    '에너지':['두산에너빌리티','GS','GS칼텍스'],
    '재생에너지':['한화솔루션','OCI홀딩스','씨에스윈드','두산에너빌리티'],
    '화학·소재':['LG화학','롯데케미칼','금호석유화학','효성첨단소재','코오롱인더']
  };
  function text(x){return ((x.title||'')+' '+(x.summary||'')).toLowerCase();}
  function scoops(t){return SCOOP.filter(w=>t.includes(w.toLowerCase())).length;}
  function signals(t){return MUST.filter(w=>t.includes(w.toLowerCase())).length;}
  function hasNumber(x,t){return !!x.concreteNumber || /\d[\d,.]*\s*(조원|억원|만원|억달러|달러|만대|천대|대|명|%|톤|mw|gw|gwh|mwh)/i.test(t);}
  function targetHit(x){const list=TARGETS[x.category]||[];const blob=(x.title||'')+' '+(x.summary||'');return list.filter(c=>blob.includes(c)).length;}
  function isCore(x){
    if(!x||x.global||!x.industrySource||!CORE_CATS.has(x.category)) return false;
    const t=text(x), sg=signals(t), sc=scoops(t), unique=(x.clusterCount||1)<=1, num=hasNumber(x,t), th=targetHit(x);
    const noise=NOISE.filter(w=>t.includes(w.toLowerCase())).length;
    const event=EVENT.some(w=>(x.title||'').includes(w));
    if(noise>0 || (event && sc===0)) return false;
    if(sc>0) return true;
    if((x.score||0)<75) return false;
    if(sg<2) return false;
    if(!num && !th) return false;
    if(!unique && !num) return false;
    return true;
  }
  function scoopScore(x){
    const t=text(x), sc=scoops(t), sg=signals(t), unique=(x.clusterCount||1)<=1, num=hasNumber(x,t), th=targetHit(x);
    return sc*80 + (unique?24:0) + (num?18:0) + Math.min(18,sg*2) + Math.min(10,th*5) + Math.min(10,x.strategySignalCount||0) + Math.min(8,(x.score||0)/12);
  }
  function badge(x){
    const t=text(x);
    if(scoops(t)>0) return '단독·취재확인';
    if((x.clusterCount||1)<=1 && hasNumber(x,t)) return '새 이슈';
    return '산업부 핵심';
  }
  function badgeClass(x){
    const t=text(x);
    return scoops(t)>0?'exclusive':((x.clusterCount||1)<=1&&hasNumber(x,t)?'must':'normal');
  }
  function esc(v){return String(v??'').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));}
  function renderCore(){
    const items=Array.isArray(window.ITEMS)?window.ITEMS:[];
    const rows=items.filter(isCore).sort((a,b)=>scoopScore(b)-scoopScore(a)||new Date(b.published)-new Date(a.published)).slice(0,16);
    const cards=document.querySelector('#cards'); if(!cards)return;
    document.querySelector('#viewTitle').textContent='산업부 핵심';
    document.querySelector('#resultCount').textContent=rows.length+'건';
    document.querySelector('#headline').textContent='산업부에서 오늘 파볼 것';
    document.querySelector('#today').textContent='단독·취재확인 → 새 이슈 → 구체적 숫자와 사업 변화 순으로 선별합니다.';
    cards.innerHTML=rows.length?rows.map(x=>{
      const bc=badgeClass(x),label=badge(x),t=text(x);
      const reason=x.exclusive?'단독·취재 신호가 잡혔습니다.':((x.clusterCount||1)<=1?'관련 보도가 한 곳에 머물러 있습니다.':'산업 변화 신호가 복수로 겹칩니다.');
      const proof=[hasNumber(x,t)?'숫자 확인':'',targetHit(x)?'출입처 핵심기업':'' ,(x.clusterCount||1)<=1?'확산 전':'' ].filter(Boolean);
      return `<article class="card ${bc}" onclick="openItem('${esc(x.id)}')"><div class="card-top"><span class="badge ${bc}">${label}</span><span class="score">${Math.round(scoopScore(x))}점</span></div><div class="meta">${esc(x.category)} · ${esc(x.sourceName)} · ${esc(x.publishedLabel||x.published)}</div><div class="title">${esc(x.title)}</div><div class="summary"><b class="why">${esc(reason)}</b><br>${esc(x.summary||'')}</div><div class="signal-row"><span class="signal">${proof.map(esc).join(' · ')}</span>${(x.companies||[]).slice(0,3).map(c=>`<span class="signal">${esc(c)}</span>`).join('')}</div><div class="bottom"><span class="tag">${esc(x.category)}</span>${(x.companies||[]).slice(0,4).map(c=>`<span class="tag">${esc(c)}</span>`).join('')}</div></article>`;
    }).join(''):'<div class="card"><div class="summary">현재 단독·취재확인 또는 구체적인 산업 변화 신호가 없습니다.</div></div>';
  }
  function refreshCount(){
    const n=(Array.isArray(window.ITEMS)?window.ITEMS:[]).filter(isCore).length;
    const el=document.querySelector('#countIndustryMust'); if(el)el.textContent=Math.min(16,n);
  }
  function bind(){
    const btn=document.querySelector('.nav[data-view="industryMust"]');
    refreshCount();
    if(btn) btn.addEventListener('click',()=>setTimeout(()=>{refreshCount();renderCore();},0));
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',bind);else bind();
})();