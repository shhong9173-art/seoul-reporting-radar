// Aside(기자 컴퓨터) REPL에서 한 번만 돌리는 코드: 레이더 직접 올리기 열쇠를 만든다(11-06).
// 32바이트 난수 열쇠를 Aside 브라우저의 레이더 사이트 저장소(localStorage 'radarUploadKey')에만 두고, SHA-256 지문만 찍는다 — 열쇠 글자는 찍지 않는다.
// 찍힌 FINGERPRINT를 sdds browser_upload_key(sha256=…)로 등록하면 kr_browser_collect.js 토막 5가 그 열쇠로 직접 올린다.
// 다시 돌리면 새 열쇠로 바뀌고, 새 지문을 등록하기 전까지 직접 올리기는 404로 막혀 예약 작업이 local_notice_submit으로 올린다.
{
  const t = await openTab('https://seoul-reporting-radar.shhong9173.workers.dev/upload/browser');
  try {
    const fp = await t.evaluate(async () => {
      const b = crypto.getRandomValues(new Uint8Array(32));
      const k = btoa(String.fromCharCode(...b)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
      localStorage.setItem('radarUploadKey', k);
      const d = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(k));
      return [...new Uint8Array(d)].map((x) => x.toString(16).padStart(2, '0')).join('');
    });
    console.log('FINGERPRINT ' + fp);
  } finally { try { await closeTab(t); } catch (e) { /* 그대로 둔다 */ } }
}
