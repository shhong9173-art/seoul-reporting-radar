let items = Array.isArray(ITEMS) ? ITEMS : [];
let filter="all", cat="", query="";
const $=s=>document.querySelector(s);
function filtered(){
 let a=items.filter(x=>(filter==="all"||x.level===filter||filter==="follow"&&x.level==="follow")&&(cat===""||x.category===cat));
 if(query)a=a.filter(x=>(x.title+x.summary+x.org+x.category+(x.tags||[]).join(" ")).toLowerCase().includes(query.toLowerCase()));
 const sort=$("#sort").value;
 return a.sort((a,b)=>sort==="score"?b.score-a.score:b.date.localeCompare(a.date));
}
function levelName(l){return l==="S"?"S급 단독 후보":l==="A"?"A급 취재 후보":l==="B"?"일반 기사":"추적 취재"}
function render(){
 const a=filtered();
 $("#cards").innerHTML=a.length?a.map(x=>`<article class="card" onclick="openItem('${x.id}')">
 <div class="card-top"><span class="badge ${x.level}">${levelName(x.level)}</span><span class="score">${x.score}점</span></div>
 <div class="meta">${x.org} · ${x.date} · ${x.category}</div>
 <div class="title">${x.title}</div>
 <div class="summary"><b>${x.why||'취재 가치 분석 중'}</b><br>${x.summary||''}</div>
 ${x.keyNumber?`<div class="key-number">${x.keyNumber}</div>`:''}
 <div class="bottom">${(x.tags||[]).map(t=>`<span class="tag">${t}</span>`).join("")}</div></article>`).join(""):`<div class="card"><div class="summary">조건에 맞는 아이템이 없습니다.</div></div>`;
 $("#resultCount").textContent=`${a.length}건`;
}
function openItem(id){
 const x=items.find(i=>String(i.id)===String(id)); if(!x)return;
 $("#detail").innerHTML=`<span class="badge ${x.level}">${levelName(x.level)}</span>
 <h2>${x.title}</h2><div class="meta">${x.org} · ${x.date} · ${x.category} · 기사 가치 ${x.score}점</div>
 ${x.keyNumber?`<div class="key-number large">${x.keyNumber}</div>`:''}
 <div class="quote"><b>왜 기사거리인가</b><br>${x.why||x.summary||''}</div>
 <h3>지금 확인할 것</h3><ul>${(x.questions||[]).map(q=>`<li>${q}</li>`).join("")}</ul>
 <h3>추가 확인 자료</h3><p>${x.data||'추가 자료 확인 필요'}</p>
 <h3>원문</h3><p><a href="${x.source}" target="_blank" rel="noopener">공식 홈페이지 열기 ↗</a></p>`;
 $("#modal").classList.remove("hidden");
}
function counts(){
 $("#countAll").textContent=items.length; $("#countS").textContent=items.filter(x=>x.level==="S").length;
 $("#countA").textContent=items.filter(x=>x.level==="A").length; $("#countB").textContent=items.filter(x=>x.level==="B").length;
 $("#countFollow").textContent=items.filter(x=>x.level==="follow").length;
 $("#statTotal").textContent=items.length; $("#statS").textContent=items.filter(x=>x.level==="S").length; $("#statF").textContent=items.filter(x=>x.level==="follow").length;
}
document.querySelectorAll(".nav").forEach(b=>b.onclick=()=>{document.querySelectorAll(".nav").forEach(n=>n.classList.remove("active"));b.classList.add("active");filter=b.dataset.filter;$("#viewTitle").textContent=b.textContent.trim().replace(/\s+\d+$/,"");render()});
document.querySelectorAll(".chip").forEach(b=>b.onclick=()=>{cat=cat===b.dataset.cat?"":b.dataset.cat;document.querySelectorAll(".chip").forEach(c=>c.style.background=c.dataset.cat===cat?"#1c242d":"");render()});
$("#search").oninput=e=>{query=e.target.value;render()};$("#sort").onchange=render;$("#reset").onclick=()=>{filter="all";cat="";query="";$("#search").value="";document.querySelectorAll(".nav").forEach(n=>n.classList.toggle("active",n.dataset.filter==="all"));document.querySelectorAll(".chip").forEach(c=>c.style.background="");render()};
$("#close").onclick=()=>$("#modal").classList.add("hidden");$("#modal").onclick=e=>{if(e.target.id==="modal")$("#modal").classList.add("hidden")};
async function loadLive(){
 try{const r=await fetch('/api/radar',{cache:'no-store'});const j=await r.json();if(j.ok&&Array.isArray(j.items)&&j.items.length){items=j.items;window.__radarUpdatedAt=j.updatedAt;}}catch(e){console.warn('live radar unavailable; using local data',e)}
 const d=new Date();$("#today").textContent=`${d.getFullYear()}년 ${d.getMonth()+1}월 ${d.getDate()}일 · 서울시 + 25개 자치구 신규자료`;
 counts();render();
}
loadLive();