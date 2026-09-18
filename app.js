let items=Array.isArray(window.ITEMS)?window.ITEMS:[];
let view='today',cat='',company='',query='';
const $=s=>document.querySelector(s);
const esc=v=>String(v??'').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));
const toks=t=>new Set(String(t||'').toLowerCase().match(/[가-힣A-Za-z0-9]{2,}/g)||[]);
const AUTO_CATS=new Set(['완성차','부품','배터리','정책·관세','중국차','노조·생산','리콜·안전','수주·투자','단독','미국·글로벌']);
const INDUSTRY_CATS=new Set(['철강','비철금속','전력기기','전선·전력','에너지','재생에너지','화학·소재']);
const INDUSTRY_ITEMS=()=>items.filter(x=>!x.global&&x.industrySource);
const AUTO_ITEMS=()=>items.filter(x=>!x.global&&(!x.industrySource||AUTO_CATS.has(x.category)));
function badge(x){return x.global?'글로벌':x.exclusive?'단독·속보 후보':x.priority==='must'?'오늘 핵심':x.priority==='follow'||x.followUp?'후속 검토':x.industrySource?'산업부':'모니터링'}
function cls(x){return x.global?'normal':x.exclusive?'exclusive':x.priority==='must'?'must':x.followUp?'follow':'normal'}
function titleOf(x){return x.global&&x.koTitle?x.koTitle:x.title}
function summaryOf(x){return x.global&&x.koSummary?x.koSummary:x.summary}
function isAuto(x){return !x.global && AUTO_CATS.has(x.category) && !x.industrySource}
function isIndustry(x){return !x.global && x.industrySource && INDUSTRY_CATS.has(x.category)}

function beatOf(x){return x.industrySource?'산업부':'자동차'}
function hasConcrete(x){return !!x.concreteNumber||/\d[\d,.]*\s*(조원|억원|만원|억달러|달러|만대|천대|대|명|%|톤|mw|gw|gwh|mwh)/i.test((x.title||'')+' '+(x.summary||''))}
function unifiedScore(x){
  const base=Number(x.score||x.industryPriorityScore||0);
  const spread=Math.max(1,Number(x.clusterCount||1));
  const exclusive=x.exclusive?12:0;
  const newIssue=spread===1?8:0;
  const concrete=hasConcrete(x)?6:0;
  const strategy=Math.min(8,Number(x.strategySignalCount||0)*2);
  const target=x.industrySource&&Array.isArray(x.companies)&&x.companies.length?4:0;
  return Math.min(99,Math.round(base+exclusive+newIssue+concrete+strategy+target));
}
function isTodayPriority(x){
  if(!x||x.global)return false;
  if(isAuto(x))return !!x.exclusive||x.priority==='must'||Number(x.score||0)>=78;
  if(isIndustry(x))return !!x.industryRelevant||!!x.exclusive||Number(x.industryPriorityScore||x.score||0)>=70;
  return false;
}
function priorityReason(x){
  const t=(x.title||'')+' '+(x.summary||'');
  if(x.exclusive)return '단독·취재확인 신호';
  if(isIndustry(x)&&hasConcrete(x))return '산업 변화 + 구체적 숫자';
  if(hasConcrete(x))return '구체적 숫자 확인';
  if(Number(x.clusterCount||1)===1)return '확산 전 단일 보도';
  if(Number(x.clusterCount||1)>=2)return '복수 매체 확산';
  if(/수주|계약|공급|증설|투자|공장|감산|철수|매각|관세|리콜|파업|풍력|HVDC|전력망/.test(t))return '사업 변화 신호';
  return beatOf(x)+' 핵심 모니터링';
}
function filtered(){
  let a=items.slice();
  if(view==='today')a=a.filter(isTodayPriority);
  if(view==='must')a=a.filter(x=>isAuto(x)&&x.priority==='must');
  if(view==='industryMust')a=a.filter(x=>isIndustry(x)).sort((a,b)=>(b.score||0)-(a.score||0)).slice(0,80);
  if(view==='all')a=a.filter(x=>!x.global);
  if(view==='exclusive')a=a.filter(x=>x.exclusive);
  if(view==='follow')a=a.filter(x=>x.followUp&&!x.global);
  if(view==='competition')a=a.filter(x=>(x.clusterCount||1)>=2&&!x.global);
  if(view==='global')a=a.filter(x=>x.global);
  if(view==='company'&&company)a=a.filter(x=>(x.companies||[]).includes(company));
  if(cat)a=a.filter(x=>x.category===cat);
  if(query){const q=query.toLowerCase();a=a.filter(x=>(titleOf(x)+' '+summaryOf(x)+' '+x.sourceName+' '+x.category+' '+(x.companies||[]).join(' ')).toLowerCase().includes(q));}
  const s=$('#sort')?.value||'score';
  if(view==='today')return a.sort((a,b)=>unifiedScore(b)-unifiedScore(a)||new Date(b.published)-new Date(a.published)).slice(0,24);
  return a.sort((a,b)=>s==='new'?new Date(b.published)-new Date(a.published):s==='coverage'?((b.clusterCount||1)-(a.clusterCount||1))||b.score-a.score:(b.score||b.industryPriorityScore||0)-(a.score||a.industryPriorityScore||0));
}
function article(x){
  const score=view==='today'?unifiedScore(x):(x.score||x.industryPriorityScore||0);
  const industryLabel=x.industrySource?'<span class="tag">'+esc(x.category)+'</span>':'';
  return '<article class="card '+cls(x)+'" onclick="openItem(\''+esc(x.id)+'\')"><div class="card-top"><span class="badge '+cls(x)+'">'+badge(x)+'</span><span class="score">'+score+'점</span></div><div class="meta"><b>'+esc(beatOf(x))+'</b> · '+esc(x.sourceName)+' · '+esc(x.publishedLabel||x.published)+' · '+esc(x.category)+'</div><div class="title">'+esc(titleOf(x))+'</div>'+(x.global&&x.title!==x.koTitle?'<div class="muted" style="font-size:11px;margin-bottom:7px">원문: '+esc(x.title)+'</div>':'')+'<div class="summary"><b class="why">'+esc(view==='today'?priorityReason(x):(x.whyNow||''))+'</b><br>'+esc(summaryOf(x))+'</div><div class="signal-row"><span class="signal">이슈 '+esc(x.clusterId||'-')+'</span><span class="signal">관련 '+(x.clusterCount||1)+'건</span>'+(hasConcrete(x)?'<span class="signal">숫자 확인</span>':'')+(x.earliestObservedSource?'<span class="signal">최초 '+esc(x.earliestObservedSource)+'</span>':'')+'</div><div class="bottom">'+industryLabel+(x.companies||[]).slice(0,5).map(t=>'<span class="tag">'+esc(t)+'</span>').join('')+(x.tags||[]).slice(0,4).map(t=>'<span class="tag">'+esc(t)+'</span>').join('')+'</div></article>';
}
function render(){
  const cards=$('#cards');
  if(view==='keywords')return renderKeywords();
  if(view==='issues')return renderIssues();
  if(view==='calls')return renderCalls();
  if(view==='company'&&!company)return renderCompanies();
  const a=filtered();
  cards.innerHTML=a.length?a.map(article).join(''):'<div class="card"><div class="summary">현재 조건에 맞는 기사가 없습니다.</div></div>';
  $('#resultCount').textContent=a.length+'건';
}
function renderCalls(){
  const a=items.filter(x=>x.followUp||x.exclusive).filter(x=>!x.global).sort((a,b)=>(b.followScore||0)-(a.followScore||0)).slice(0,15);
  $('#cards').innerHTML=a.length?a.map(x=>'<article class="card follow"><div class="card-top"><span class="badge follow">오늘 전화할 곳</span><span class="score">'+(x.followScore||0)+'점</span></div><div class="meta"><b>'+esc(beatOf(x))+'</b> · '+esc(x.sourceName)+' · '+esc(x.publishedLabel||x.published)+' · '+esc(x.category)+'</div><div class="title">'+esc(titleOf(x))+'</div><div class="summary"><b>왜 전화?</b> '+esc(x.whyNow||'')+'</div><div class="quote"><b>우선 확인 질문</b><ul>'+(x.questions||[]).slice(0,3).map(q=>'<li>'+esc(q)+'</li>').join('')+'</ul></div><div class="bottom">'+(x.companies||[]).map(c=>'<span class="tag">'+esc(c)+'</span>').join('')+'</div></article>').join(''):'<div class="card"><div class="summary">현재 전화 우선순위 후보가 없습니다.</div></div>';
  $('#resultCount').textContent=a.length+'건';
}
function renderCompanies(){
  const a=companyCounts().slice(0,40);
  $('#cards').innerHTML=a.map(([c,n])=>'<article class="card" onclick="company=\''+esc(c).replace(/\'/g,"\\\'")+'\';view=\'company\';syncNav();render()"><div class="card-top"><span class="badge normal">기업</span><span class="score">'+n+'건</span></div><div class="title">'+esc(c)+'</div><div class="summary">최근 72시간 관련 기사 '+n+'건. 클릭하면 기업 타임라인을 봅니다.</div></article>').join('');
  $('#resultCount').textContent=a.length+'개 기업';
}
function companyCounts(){const m={};items.filter(x=>!x.global).forEach(x=>(x.companies||[]).forEach(c=>m[c]=(m[c]||0)+1));return Object.entries(m).sort((a,b)=>b[1]-a[1]);}
function renderKeywords(){
  const now=Date.now(),recent=items.filter(x=>now-new Date(x.published)<36*3600*1000),old=items.filter(x=>now-new Date(x.published)>=36*3600*1000);
  const count=a=>{const m={};a.forEach(x=>toks(titleOf(x)+' '+summaryOf(x)).forEach(w=>{if(w.length<2||STOP_K.has(w))return;m[w]=(m[w]||0)+1}));return m};
  const r=count(recent),o=count(old);const rows=Object.entries(r).map(([w,n])=>({w,n,old:o[w]||0,growth:n-(o[w]||0)})).filter(x=>x.n>=2).sort((a,b)=>b.growth-a.growth||b.n-a.n).slice(0,30);
  $('#cards').innerHTML='<div class="card"><div class="title">최근 36시간 급상승 키워드</div><div class="bottom">'+rows.map(x=>'<span class="tag" style="font-size:12px">'+esc(x.w)+' · '+x.n+'회 <b>▲'+x.growth+'</b></span>').join('')+'</div></div>'+rows.slice(0,10).map(x=>'<article class="card"><div class="card-top"><span class="badge normal">급상승</span><span class="score">'+x.n+'회</span></div><div class="title">'+esc(x.w)+'</div><div class="summary">최근 36시간 '+x.n+'회 / 이전 36시간 '+x.old+'회. 증가분 '+x.growth+'회.</div></article>').join('');
  $('#resultCount').textContent=rows.length+'개';
}
const STOP_K=new Set('자동차 전기차 배터리 현대차 기아 관련 올해 오늘 최근 한국 글로벌 industry auto automotive news company market vehicle vehicles 산업부 산업 기업 관련 시장 올해 지난해'.split(' '));
function clusterGroups(){const m={};items.filter(x=>!x.global).forEach(x=>{const k=x.clusterId||x.id;(m[k]??=[]).push(x)});return Object.entries(m).sort((a,b)=>b[1].length-a[1].length)}
function renderIssues(){const groups=clusterGroups().slice(0,30);$('#cards').innerHTML=groups.map(([id,g])=>'<article class="card" onclick="openCluster(\''+esc(id)+'\')"><div class="card-top"><span class="badge normal">이슈 타임라인</span><span class="score">'+g.length+'건</span></div><div class="title">'+esc(titleOf(g[g.length-1]))+'</div><div class="meta">'+esc(g[0].publishedLabel||g[0].published)+' → '+esc(g[g.length-1].publishedLabel||g[g.length-1].published)+' · '+esc(g.map(x=>x.sourceName).filter(Boolean).filter((v,i,a)=>a.indexOf(v)===i).join(', '))+'</div><div class="summary">'+g.map(x=>'<div style="margin:6px 0"><b>'+esc(x.sourceName)+'</b> · '+esc(titleOf(x))+'</div>').join('')+'</div></article>').join('');$('#resultCount').textContent=groups.length+'개 이슈'}
function openCluster(id){const g=items.filter(x=>x.clusterId===id);$('#detail').innerHTML='<div class="badge normal">이슈 '+esc(id)+'</div><h2>'+esc(titleOf(g[g.length-1]))+'</h2><div class="scorebox"><div><small>관련 기사</small><b>'+g.length+'</b></div><div><small>매체</small><b>'+new Set(g.map(x=>x.sourceName)).size+'</b></div></div><h3>진행 타임라인</h3>'+g.map(x=>'<div style="padding:10px 0;border-bottom:1px solid #eee"><b>'+esc(x.publishedLabel||x.published)+'</b> · '+esc(x.sourceName)+'<br>'+esc(titleOf(x))+'</div>').join('')+'<h3>후속 취재 질문</h3>'+list(g[g.length-1].questions);$('#modal').classList.remove('hidden')}
function list(a){return Array.isArray(a)&&a.length?'<ul>'+a.map(v=>'<li>'+esc(v)+'</li>').join('')+'</ul>':'<p>등록된 항목이 없습니다.</p>'}
function openItem(id){
  const x=items.find(i=>String(i.id)===String(id));if(!x)return;
  const sources=(x.coveredBy||[]).map(s=>'<span class="tag">'+esc(s)+'</span>').join('');
  $('#detail').innerHTML='<span class="badge '+cls(x)+'">'+badge(x)+'</span><h2>'+esc(titleOf(x))+'</h2>'+(x.global?'<p class="muted">원문: '+esc(x.title)+'</p>':'')+'<div class="meta"><b>'+esc(beatOf(x))+'</b> · '+esc(x.sourceName)+' · '+esc(x.publishedLabel||x.published)+' · '+esc(x.category)+'</div><div class="scorebox"><div><small>취재가치</small><b>'+((view==='today')?unifiedScore(x):(x.score||x.industryPriorityScore||0))+'</b></div><div><small>단독</small><b>'+(x.exclusiveScore??'-')+'</b></div><div><small>후속</small><b>'+(x.followScore??'-')+'</b></div><div><small>이슈 확산</small><b>'+(x.clusterCount||1)+'개</b></div></div><div class="quote"><b>왜 지금 봐야 하나</b><br>'+esc(x.whyNow||priorityReason(x))+'</div><h3>'+(x.global?'한국어 요약':'기사 핵심')+'</h3><p>'+esc(summaryOf(x)||'')+'</p>'+(x.global?'<h3>국내 취재 포인트</h3>'+list(x.points): '')+'<h3>경쟁지·매체 동향</h3><p>확인 매체: '+(sources||esc(x.sourceName||'1개 매체'))+'</p><p class="muted">최초 관측: '+esc(x.earliestObservedAt||'-')+' · '+esc(x.earliestObservedSource||'-')+'</p><h3>취재 포인트</h3>'+list(x.points)+'<h3>추가 확인 질문</h3>'+list(x.questions)+'<h3>관련 기업</h3>'+list(x.companies)+'<h3>원문</h3><p><a href="'+esc(x.url||'#')+'" target="_blank" rel="noopener">원문 기사 열기 ↗</a></p>';
  $('#modal').classList.remove('hidden');
}
function counts(){
  const auto=AUTO_ITEMS().length, industry=INDUSTRY_ITEMS().length, global=items.filter(x=>x.global).length, must=items.filter(isTodayPriority).length;
  $('#countAll').textContent=items.filter(x=>!x.global).length; $('#countMust').textContent=must; if($('#countAutoMust'))$('#countAutoMust').textContent=items.filter(x=>isAuto(x)&&x.priority==='must').length; $('#countIndustryMust').textContent=industry; $('#countExclusive').textContent=items.filter(x=>x.exclusive).length; $('#countFollow').textContent=items.filter(x=>x.followUp&&!x.global).length; $('#countCompetition').textContent=items.filter(x=>(x.clusterCount||1)>=2&&!x.global).length; $('#countGlobal').textContent=global;
  $('#statAuto').textContent=auto; $('#statIndustry').textContent=industry; $('#statGlobal').textContent=global;
}
function setupCompanies(){const c=[...new Set(items.flatMap(x=>x.companies||[]))].filter(Boolean).sort();$('#companyChips').innerHTML=c.slice(0,50).map(v=>'<button class="chip" data-company="'+esc(v)+'">'+esc(v)+'</button>').join('');document.querySelectorAll('[data-company]').forEach(b=>b.onclick=()=>{company=company===b.dataset.company?'':b.dataset.company;view='company';syncNav();render()});}
function syncNav(){
  document.querySelectorAll('.nav').forEach(n=>n.classList.toggle('active',n.dataset.view===view));
  const names={today:'오늘 취재 우선순위',must:'자동차 핵심',industryMust:'산업부 핵심',all:'전체 모니터링',exclusive:'단독·속보 후보',follow:'후속 취재 후보',competition:'경쟁지 선행 이슈',calls:'오늘 전화할 곳',company:company?company+' 타임라인':'기업 타임라인',keywords:'키워드 급상승',issues:'이슈 타임라인',global:'글로벌 레이더'};
  $('#viewTitle').textContent=names[view]||'산업부 종합 취재 레이더';
  $('#headline').textContent=view==='global'?'글로벌 자동차·산업판에서 놓치면 안 되는 것':view==='must'?'자동차판에서 오늘 놓치면 안 되는 것':view==='industryMust'?'산업부에서 오늘 파볼 것':'산업부 전체 출입처에서 오늘 파볼 것';
  if(view==='today')$('#today').textContent='자동차 + 산업부 전 출입처를 한 화면에서 통합. 단독·새 이슈·숫자·사업 변화 순으로 정렬합니다.';
}
function bind(){
  document.querySelectorAll('.nav:not(.pitch-nav):not(.archive-nav)').forEach(b=>b.onclick=()=>{view=b.dataset.view||'today';company='';syncNav();render();});
  document.querySelectorAll('.chip[data-cat]').forEach(b=>b.onclick=()=>{cat=cat===b.dataset.cat?'':b.dataset.cat;if(cat)view='all';syncNav();render();});
  $('#search').oninput=e=>{query=e.target.value;render()}; $('#sort').onchange=render;
  $('#reset').onclick=()=>{view='today';cat='';company='';query='';$('#search').value='';syncNav();render();};
  $('#close').onclick=()=>$('#modal').classList.add('hidden'); $('#modal').onclick=e=>{if(e.target.id==='modal')$('#modal').classList.add('hidden')};
}
bind();counts();setupCompanies();syncNav();render();$('#today').textContent='자동차 + 산업부 전 출입처를 한 화면에서 통합. 단독·새 이슈·숫자·사업 변화 순으로 정렬합니다.';
