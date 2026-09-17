(() => {
  const OWN_RE = /아이뉴스24|iNews24|inews24/i;
  const EVENT_RE = /인베스터데이|주주총회|설명회|세미나|포럼|엑스포|컨퍼런스|부스투어|기조연설|발표회/;
  const STRATEGY_RE = /수주|계약|공급|증설|투자|공장|생산중단|생산 중단|가동|감산|철수|매각|인수|합작|구조조정|관세|반덤핑|통상|가격|원가|마진|리콜|화재|노조|파업|임단협|판매|자율주행|HVDC|변압기|전력망|해상풍력|풍력|태양광|석유화학|스페셜티|배터리소재/i;

  const ownSource = (name='') => OWN_RE.test(String(name));
  const groupMap = () => {
    const m = {};
    items.filter(x => !x.global).forEach(x => {
      const k = x.clusterId || x.id;
      (m[k] ??= []).push(x);
    });
    return m;
  };
  const gapGroups = () => Object.entries(groupMap()).map(([id, g]) => {
    const sources = [...new Set(g.map(x => String(x.sourceName || '').trim()).filter(Boolean))];
    const own = sources.some(ownSource);
    const latest = g.slice().sort((a,b) => new Date(b.published) - new Date(a.published))[0];
    const latestAge = Math.max(0, (Date.now() - new Date(latest?.published || 0)) / 3600000);
    const blob = g.map(x => `${x.title || ''} ${x.summary || ''}`).join(' ');
    const concrete = g.some(x => x.concreteNumber) || /\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?(?:조원|억원|만원|달러|만대|천대|대|명|%|톤|MW|GW|GWh|MWh)/.test(blob);
    const strategy = g.some(x => x.strategySignalCount >= 1) || STRATEGY_RE.test(blob);
    const eventOnly = g.every(x => x.event || EVENT_RE.test(x.title || '')) && !concrete && !strategy;
    const score = Math.min(99, 45 + Math.min(24, sources.length * 8) + Math.min(12, g.length * 3) + (concrete ? 8 : 0) + (strategy ? 8 : 0) + (latestAge <= 12 ? 10 : latestAge <= 24 ? 6 : latestAge <= 48 ? 3 : 0));
    return {id, g, sources, own, latest, latestAge, concrete, strategy, eventOnly, score};
  }).filter(x => !x.own && x.sources.length >= 2 && x.g.length >= 2 && x.latestAge <= 72 && !x.eventOnly)
    .sort((a,b) => b.score-a.score || b.sources.length-a.sources.length || new Date(b.latest.published)-new Date(a.latest.published));

  const originalSyncNav = window.syncNav;
  const originalRender = window.render;
  const originalCounts = window.counts;

  function isGapItem(x) {
    if (!x || x.global) return false;
    const id = x.clusterId || x.id;
    return gapGroups().some(c => c.id === id);
  }

  function renderGap() {
    const groups = gapGroups().slice(0, 15);
    const cards = document.querySelector('#cards');
    if (!cards) return;
    cards.innerHTML = groups.length ? groups.map(c => {
      const lead = c.g.slice().sort((a,b)=>new Date(b.published)-new Date(a.published))[0];
      const title = lead.global && lead.koTitle ? lead.koTitle : lead.title;
      const sources = c.sources.slice(0, 8).join(', ');
      const companies = [...new Set(c.g.flatMap(x=>x.companies || []))].slice(0,5);
      const freshness = c.latestAge < 24 ? '오늘 확산' : c.latestAge < 48 ? '최근 48시간' : '최근 72시간';
      const reason = c.sources.length >= 3 ? `${c.sources.length}개 매체가 같은 이슈를 다루고 있습니다. 아이뉴스24 보도는 아직 확인되지 않습니다.` : '복수 매체에서 확인된 이슈입니다. 아이뉴스24 보도는 아직 확인되지 않습니다.';
      const questions = (lead.questions || []).slice(0,3);
      return `<article class="card follow" onclick="openItem('${String(lead.id||'').replace(/'/g,"\\'")}')"><div class="card-top"><span class="badge follow">타사 다매체 · 미보도</span><span class="score">${c.score}점</span></div><div class="meta">${freshness} · ${lead.category || ''} · ${c.sources.length}개 매체</div><div class="title">${esc(title)}</div><div class="summary"><b class="why">${esc(reason)}</b><br>${esc(lead.summary || '')}</div><div class="signal-row"><span class="signal">이슈 ${esc(c.id)}</span><span class="signal">관련 ${c.g.length}건</span><span class="signal">매체 ${c.sources.length}곳</span></div><div class="quote"><b>팔로업 포인트</b><ul>${(questions.length ? questions : ['아이뉴스24가 확인하지 못한 새 사실·숫자가 무엇인지 확인','복수 매체가 각각 같은 사실을 취재한 것인지 원출처를 추적','국내 기업·정부의 공식 입장과 추가 숫자를 확인']).map(q=>`<li>${esc(q)}</li>`).join('')}</ul></div><div class="bottom">${companies.map(cn=>`<span class="tag">${esc(cn)}</span>`).join('')}<span class="tag">${esc(sources)}</span></div></article>`;
    }).join('') : '<div class="card"><div class="title">현재 타사 다매체·아이뉴스24 미보도 이슈가 없습니다.</div><div class="summary">복수 매체 확산 + 최근 72시간 + 아이뉴스24 미보도 조건을 동시에 충족한 이슈만 표시합니다.</div></div>';
    document.querySelector('#resultCount').textContent = `${groups.length}개 이슈`;
  }

  window.crossMediaGapCount = () => gapGroups().length;
  window.crossMediaGapOpen = renderGap;
  window.crossMediaGapItem = isGapItem;

  window.render = function(){
    if (view === 'crossMediaGap') return renderGap();
    return originalRender();
  };

  window.syncNav = function(){
    if (originalSyncNav) originalSyncNav();
    const button = document.querySelector('.cross-media-gap-nav');
    if (button) button.classList.toggle('active', view === 'crossMediaGap');
    if (view === 'crossMediaGap') {
      const title = document.querySelector('#viewTitle');
      if (title) title.textContent = '타사 다매체·미보도 이슈';
    }
  };

  window.counts = function(){
    if (originalCounts) originalCounts();
    const el = document.querySelector('#countCrossMediaGap');
    if (el) el.textContent = gapGroups().length;
  };

  function addNav() {
    const nav = document.querySelector('nav');
    if (!nav || nav.querySelector('.cross-media-gap-nav')) return;
    const b = document.createElement('button');
    b.className = 'nav cross-media-gap-nav';
    b.type = 'button';
    b.innerHTML = `타사 다매체·미보도 <span id="countCrossMediaGap">0</span>`;
    b.onclick = () => { view='crossMediaGap'; cat=''; company=''; query=''; syncNav(); render(); };
    const anchor = nav.querySelector('[data-view="competition"]');
    if (anchor) anchor.insertAdjacentElement('afterend', b); else nav.appendChild(b);
    window.counts();
  }

  addNav();
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', addNav, {once:true});
})();
