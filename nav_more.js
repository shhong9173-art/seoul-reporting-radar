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
  // 휴대폰(900px 아래): 위쪽 막대에 '메뉴' 버튼 — 왼쪽 메뉴를 서랍으로 연다. 메뉴·분야·기업 단추를 누르면 닫힌다.
  function mobileNav(){
    const side = document.querySelector('.sidebar');
    if (!side || document.querySelector('.mobile-bar')) return;
    const bar = document.createElement('div');
    bar.className = 'mobile-bar';
    bar.innerHTML = '<button type="button" class="mb-menu" aria-label="메뉴 열기" aria-expanded="false">☰ 메뉴</button><span class="mb-title">산업부 종합 취재 레이더</span><button type="button" class="mb-scoop">단독감·미보도</button>';
    const back = document.createElement('div');
    back.className = 'nav-backdrop';
    document.body.insertBefore(back, document.body.firstChild);
    document.body.insertBefore(bar, document.body.firstChild);
    const btn = bar.querySelector('.mb-menu');
    const title = bar.querySelector('.mb-title');
    const setOpen = (open) => { document.body.classList.toggle('nav-open', open); btn.setAttribute('aria-expanded', open ? 'true' : 'false'); };
    const syncTitle = () => {
      const a = side.querySelector('.nav.active');
      const t = a ? Array.from(a.childNodes).filter((n) => n.nodeType === 3).map((n) => n.textContent).join('').trim() : '';
      title.textContent = t || '산업부 종합 취재 레이더';
    };
    btn.addEventListener('click', () => setOpen(!document.body.classList.contains('nav-open')));
    back.addEventListener('click', () => setOpen(false));
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') setOpen(false); });
    side.addEventListener('click', (e) => {
      const hit = e.target.closest('button.nav, a.nav, .chip');
      if (!hit) return;
      setTimeout(() => { setOpen(false); syncTitle(); window.scrollTo(0, 0); }, 0);
    });
    bar.querySelector('.mb-scoop').addEventListener('click', () => { const s = side.querySelector('.scoop-nav'); if (s) s.click(); });
    // 화면 이름은 활성 메뉴가 바뀔 때마다(단독감 탭처럼 불러온 뒤에 바뀌는 화면도) 따라간다
    if (typeof MutationObserver === 'function') new MutationObserver(syncTitle).observe(side, { subtree: true, attributes: true, attributeFilter: ['class'] });
    syncTitle();
  }
  function start(){ setup(); mobileNav(); openFromHash(12); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once: true}); else start();
})();
