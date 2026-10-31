// 사이트 첫 화면 로그인(11-01 기자 요청: "사이트 첫화면부터 로그인하게"). 모든 화면 <head> 맨 앞에서 읽혀
// 로그인 확인 전까지 화면을 가리고, 워커(/auth/check)가 세션을 확인하면 연다. 로그인은 워커 /auth/login
// (아이디·비밀번호는 워커 비밀값 BOARD_USER·BOARD_PASSWORD) — 세션 30일, '단독감·미보도' 탭의 오늘의 레이더와 같은 세션.
// 주의: GitHub Pages는 정적 공개 사이트라 이 잠금은 화면을 가릴 뿐이다. 공개 저장소의 자료 파일(JSON 등)은 주소를 알면
// 누구나 받을 수 있다. 기자 전용 단서(오늘의 레이더)는 워커가 세션을 확인해야만 내준다.
(function(){
  var API='https://seoul-reporting-radar.shhong9173.workers.dev';
  var KEY='radarSession';
  var root=document.documentElement;
  root.classList.add('gate-locked');
  var css=document.createElement('style');
  css.textContent='html.gate-locked body>*:not(#gate){display:none!important}'+
    '#gate{min-height:100vh;display:flex;align-items:center;justify-content:center;background:#f4f6f8;padding:20px;font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Malgun Gothic",sans-serif}'+
    '#gate form{background:#fff;border:1px solid #e1e5e9;border-radius:12px;padding:24px;width:min(360px,100%);display:grid;gap:10px;box-shadow:0 6px 24px #0000000d}'+
    '#gate h1{font-size:19px;margin:0 0 4px;color:#17202a}#gate p{margin:0;font-size:13px;color:#69747d;line-height:1.5}'+
    '#gate input{font:inherit;font-size:15px;padding:11px 12px;border:1px solid #dfe3e7;border-radius:8px}'+
    '#gate button{font:inherit;font-size:15px;padding:11px;border:0;border-radius:8px;background:#17202a;color:#fff;cursor:pointer}#gate button[disabled]{opacity:.6}'+
    '#gate .gate-msg{color:#b3261e;min-height:1em}';
  (document.head||root).appendChild(css);
  function getS(){try{return localStorage.getItem(KEY)||'';}catch(e){return '';}}
  function setS(v){try{localStorage.setItem(KEY,v);}catch(e){}}
  function dropS(){try{localStorage.removeItem(KEY);}catch(e){}}
  function unlock(){root.classList.remove('gate-locked');var g=document.getElementById('gate');if(g&&g.parentNode)g.parentNode.removeChild(g);}
  function ready(fn){if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',fn);else fn();}
  function form(msg,checking){
    ready(function(){
      var g=document.getElementById('gate');
      if(!g){g=document.createElement('div');g.id='gate';document.body.insertBefore(g,document.body.firstChild);}
      if(checking){g.innerHTML='<form><h1>산업부 종합 취재 레이더</h1><p>로그인 확인 중…</p></form>';return;}
      g.innerHTML='<form id="gateForm" autocomplete="on"><h1>산업부 종합 취재 레이더</h1><p>기자 전용입니다. 로그인하면 이 브라우저에서 30일 유지됩니다.</p>'+
        '<input id="gateId" name="username" autocomplete="username" placeholder="아이디" required>'+
        '<input id="gatePw" name="password" type="password" autocomplete="current-password" placeholder="비밀번호" required>'+
        '<button type="submit">로그인</button><p class="gate-msg" id="gateMsg"></p></form>';
      var m=document.getElementById('gateMsg');if(m&&msg)m.textContent=msg;
      document.getElementById('gateForm').onsubmit=function(e){
        e.preventDefault();
        var b=g.querySelector('button');b.disabled=true;
        fetch(API+'/auth/login',{method:'POST',cache:'no-store',credentials:'omit',headers:{'Content-Type':'text/plain'},
          body:JSON.stringify({id:document.getElementById('gateId').value,pw:document.getElementById('gatePw').value})})
          .then(function(r){return r.json().catch(function(){return {};}).then(function(j){return {status:r.status,body:j};});})
          .then(function(x){
            if(x.status===200&&x.body&&x.body.session){setS(x.body.session);unlock();return;}
            form(x.status===401?'아이디 또는 비밀번호가 맞지 않습니다.':x.status===429?'실패가 많아 1시간 잠겼습니다. 잠시 뒤 다시 해 주세요.':x.status===503?'로그인이 아직 설정되지 않았습니다.':'로그인 실패('+((x.body&&x.body.error)||x.status)+')');
          })
          .catch(function(err){form('서버에 연결하지 못했습니다('+(err&&err.message||err)+'). 잠시 뒤 다시 해 주세요.');});
      };
    });
  }
  var s=getS();
  if(!s||typeof fetch!=='function'){form('');return;}
  form('',true);
  fetch(API+'/auth/check',{cache:'no-store',credentials:'omit',headers:{Authorization:'Bearer '+s}})
    .then(function(r){
      if(r.status===200){unlock();return;}
      if(r.status===503){unlock();return;}   // 로그인 미설정(비밀값 없음) — 잠그지 않는다
      dropS();form('로그인이 만료됐습니다. 다시 로그인해 주세요.');
    })
    .catch(function(){form('서버에 연결하지 못했습니다. 잠시 뒤 새로고침해 주세요.');});
  window.radarLogout=function(){dropS();location.reload();};
})();
