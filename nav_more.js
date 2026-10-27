// Sidebar '더보기': count what is inside (scripts may add buttons there) and remember open/closed per viewer.
(function(){
  const KEY = 'radar.navMoreOpen';
  function setup(){
    const more = document.querySelector('.nav-more');
    if (!more) return;
    const n = more.querySelectorAll('.nav-more-body .nav').length;
    const badge = more.querySelector('summary span');
    if (badge) badge.textContent = n;
    try { if (localStorage.getItem(KEY) === '1') more.open = true; } catch (e) {}
    more.addEventListener('toggle', () => { try { localStorage.setItem(KEY, more.open ? '1' : '0'); } catch (e) {} });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', setup, {once: true}); else setup();
})();
