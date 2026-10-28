// Sidebar '더보기': count what is inside (scripts may add buttons there) and remember open/closed per viewer.
(function(){
  const KEY = 'radar.navMoreOpen';
  function setup(){
    const more = document.querySelector('.nav-more');
    if (!more) return;
    const n = more.querySelectorAll('.nav-more-body .nav:not([hidden])').length;
    const badge = more.querySelector('summary span');
    if (badge) badge.textContent = n;
    try { if (localStorage.getItem(KEY) === '1') more.open = true; } catch (e) {}
    more.addEventListener('toggle', () => { try { localStorage.setItem(KEY, more.open ? '1' : '0'); } catch (e) {} });
  }
  // index.html#view=global opens a view whose menu button is hidden (listed on pages.html).
  function openFromHash(tries){
    const m = /(?:^#|&)view=([A-Za-z]+)/.exec(location.hash || '');
    if (!m) return;
    const b = document.querySelector('.nav[data-view="' + m[1] + '"]');
    if (b && typeof b.onclick === 'function') { b.onclick(); return; }
    if (tries > 0) setTimeout(() => openFromHash(tries - 1), 500);
  }
  function start(){ setup(); openFromHash(12); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once: true}); else start();
})();
