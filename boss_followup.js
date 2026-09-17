(() => {
  const OWN_RE = /아이뉴스24|iNews24|inews24/i;
  const PRESS_SOURCE_RE = /뉴스와이어|Newswire|PRNewswire|Business Wire|GlobeNewswire|EIN Presswire|PRWeb|Accesswire|Press Release/i;
  const OFFICIAL_RELEASE_SOURCE_RE = /뉴스룸|미디어센터|프레스센터|press room|media center/i;
  const PRESS_TITLE_RE = /^\s*(?:\[[^\]]*\s*)?(?:보도자료|자료제공|자료배포|보도자료 배포)(?:\]|[:：)]|\s|$)/i;
  const PRESS_PREFIX_RE = /^\s*(?:보도자료|자료제공|자료배포|보도자료 배포|press release)\b/i;
  const PRESS_TEMPLATE_RE = /언론보도자료|본 자료는 .*보도자료|배포일시|담당부서\s*[:：].*(?:홍보|커뮤니케이션)|문의처\s*[:：].*(?:홍보|커뮤니케이션)/i;
  const EVENT_RE = /인베스터데이|주주총회|설명회|세미나|포럼|엑스포|컨퍼런스|부스투어|기조연설|발표회/;
  const ACTION_RE = /수주|계약|공급|증설|투자|공장|생산능력|생산중단|가동|감산|철수|매각|인수|합작|구조조정|관세|반덤핑|통상|가격|원가|마진|리콜|화재|노조|파업|임단협|자율주행|HVDC|변압기|전력망|해상풍력|풍력|태양광|석유화학|스페셜티|배터리소재/;
  const STOP = new Set('및 의 을 를 이 가 은 는 에서 으로 로 와 과 에 대한 관련 올해 오늘 최근 국내 글로벌 업계 시장 기업 사업 계획 추진 전망 기자 보도 밝혔다 따르면 통해 위한 대한 있다 없다 것으로 가운데 당시 이후 이전 현재 이번 등 전 the and for with from this that auto automotive news company market vehicle vehicles'.split(' '));

  const esc = v => String(v ?? '').replace(/[&<>\"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));
  const textOf = x => `${x?.title || ''} ${x?.summary || ''}`;
  const pressInfo = x => {
    const title = String(x?.title || ''), source = String(x?.sourceName || ''), summary = String(x?.summary || '');
    let score = 0;
    if (PRESS_SOURCE_RE.test(source)) score += 5;
    if (OFFICIAL_RELEASE_SOURCE_RE.test(source)) score += 5;
    if (PRESS_TITLE_RE.test(title)) score += 5;
    if (PRESS_PREFIX_RE.test(summary)) score += 4;
    if (PRESS_TEMPLATE_RE.test(`${title} ${summary}`)) score += 3;
    return score >= 5;
  };
  const tokens = text => new Set((String(text).toLowerCase().match(/[가-힣A-Za-z0-9]{2,}/g) || []).filter(w => !STOP.has(w) && !/^\d+$/.test(w)));
  const jaccard = (a,b) => {
    const A = tokens(a), B = tokens(b);
    if (!A.size && !B.size) return 1;
    let inter = 0; A.forEach(x => { if (B.has(x)) inter += 1; });
    return inter / Math.max(1, A.size + B.size - inter);
  };
  const nums = text => new Set(String(text).match(/\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?(?:조원|억원|만원|달러|만대|천대|대|명|%|톤|MW|GW|GWh|MWh|억|조)/g) || []);

  function clusters() {
    const m = {};
    items.filter(x => !x.global && !pressInfo(x)).forEach(x => {
      const k = x.clusterId || x.id;
      (m[k] ??= []).push(x);
    });
    return Object.values(m);
  }

  function candidate(g) {
    const media = g.slice().sort((a,b) => new Date(a.published) - new Date(b.published));
    const sources = [...new Set(media.map(x => String(x.sourceName || '').trim()).filter(Boolean))];
    const own = sources.some(s => OWN_RE.test(s));
    if (own || sources.length < 2 || media.length < 2) return null;
    const latest = media[media.length - 1];
    const age = Math.max(0, (Date.now() - new Date(latest.published)) / 3600000);
    if (age > 72) return null;
    if (media.every(x => x.event || EVENT_RE.test(x.title || '')) && !media.some(x => ACTION_RE.test(textOf(x)) || x.concreteNumber)) return null;

    const anchor = media[0];
    let independent = 0, added = 0, copied = 0;
    const details = media.map((x, i) => {
      if (i === 0) return {x, titleSim:1, summarySim:1, newNums:[], copy:false, independent:false, added:false};
      const titleSim = jaccard(anchor.title || '', x.title || '');
      const summarySim = jaccard(anchor.summary || '', x.summary || '');
      const a = nums(textOf(anchor)), b = nums(textOf(x));
      const newNums = [...b].filter(n => !a.has(n));
      const copy = (titleSim * 0.65 + summarySim * 0.35) >= 0.70 && titleSim >= 0.58 && newNums.length === 0;
      const indep = !copy && (titleSim < 0.58 || summarySim < 0.30 || newNums.length >= 1);
      if (copy) copied += 1;
      if (indep) independent += 1;
      if (newNums.length) added += 1;
      return {x, titleSim, summarySim, newNums, copy, independent:indep, added:newNums.length>0};
    });
    const latestAgeLabel = age < 24 ? '오늘' : age < 48 ? '최근 48시간' : '최근 72시간';
    const company = [...new Set(media.flatMap(x => x.companies || []))].slice(0,4);
    const action = ACTION_RE.exec(media.map(textOf).join(' '))?.[0] || '';
    const score = Math.min(99, 48 + sources.length*7 + independent*16 + added*8 + (age <= 12 ? 10 : age <= 24 ? 6 : 3) + (action ? 6 : 0));
    return {media, sources, anchor, latest, age, latestAgeLabel, company, independent, added, copied, action, score, details};
  }

  function ranked() {
    return clusters().map(candidate).filter(Boolean).sort((a,b) => b.score-a.score || b.independent-a.independent || new Date(b.latest.published)-new Date(a.latest.published)).slice(0,8);
  }

  function bossLine(c) {
    const topic = c.latest.title.replace(/^\s*\[[^\]]+\]\s*/, '').trim();
    const src = c.sources.slice(0,3).join(', ');
    const company = c.company.length ? `${c.company.slice(0,2).join(', ')} 관련 ` : '';
    const check = c.independent > 0 ? '매체별 추가 취재 내용과 국내 기업 입장을 확인해보겠습니다.' : '공통 원출처 여부부터 확인해보겠습니다.';
    return `“네. ${company}‘${topic}’ 이슈가 ${src} 등에서 나왔고 아이뉴스24에는 아직 없습니다. ${check}”`;
  }

  function renderBoss() {
    const cards = document.querySelector('#cards');
    if (!cards) return;
    const list = ranked().slice(0,5);
    if (!list.length) {
      cards.innerHTML = `<div class="card"><div class="title">지금 바로 보고할 타사 선행 이슈가 없습니다.</div><div class="summary">보도자료·배포 서비스와 아이뉴스24 자체 보도를 제외하고, 복수 언론의 실제 기사 확산만 확인합니다.</div><div class="quote"><b>부장님께 답할 말</b><p>“현재 타사 다매체 기준으로 확실한 팔로업 후보는 없습니다. 새로 확산되는 이슈가 생기면 바로 확인하겠습니다.”</p></div></div>`;
      document.querySelector('#resultCount').textContent = '0개 이슈';
      return;
    }
    cards.innerHTML = list.map((c, i) => {
      const title = c.latest.title;
      const extra = c.independent > 0 ? `${c.independent}개 매체 별도 취재 정황` : '매체 간 추가 취재 여부 확인 필요';
      return `<article class="card follow">
        <div class="card-top"><span class="badge follow">부장 대응 ${i+1}</span><span class="score">${c.score}점</span></div>
        <div class="meta">${c.latestAgeLabel} · ${esc(c.latest.category || '')} · ${c.sources.length}개 매체 · 최초 ${esc(c.anchor.sourceName || '미상')}</div>
        <div class="title">${esc(title)}</div>
        <div class="summary"><b class="why">${esc(extra)}</b><br>${esc(c.sources.join(', '))} · 아이뉴스24 미보도</div>
        <div class="signal-row"><span class="signal">관련 ${c.media.length}건</span><span class="signal">독립취재 ${c.independent}건</span><span class="signal">추가 숫자 ${c.added}건</span></div>
        <div class="quote"><b>부장님께 바로 답할 문장</b><p>${esc(bossLine(c))}</p></div>
        <div class="quote"><b>바로 확인할 것</b><ul><li>최초 매체가 확보한 원출처·취재원을 확인</li><li>매체별 추가 숫자·고객사·계약조건 차이를 대조</li><li>국내 기업·정부에 전화해 아이뉴스24 추가 팩트 확인</li></ul></div>
        <div class="bottom">${c.company.map(v=>`<span class="tag">${esc(v)}</span>`).join('')}<span class="tag">${esc(c.sources.join(', '))}</span></div>
      </article>`;
    }).join('');
    document.querySelector('#resultCount').textContent = `${list.length}개 이슈`;
  }

  function addNav() {
    const nav = document.querySelector('nav');
    if (!nav || nav.querySelector('.boss-followup-nav')) return;
    const b = document.createElement('button');
    b.className = 'nav boss-followup-nav';
    b.type = 'button';
    b.innerHTML = `부장 대응·팔로업 <span id="countBossFollowup">0</span>`;
    b.onclick = () => { view='bossFollowup'; cat=''; company=''; query=''; syncNav(); renderBoss(); };
    const anchor = nav.querySelector('.cross-media-gap-nav');
    if (anchor) anchor.insertAdjacentElement('beforebegin', b); else nav.appendChild(b);
  }

  const originalSyncNav = window.syncNav;
  window.syncNav = function(){
    if (originalSyncNav) originalSyncNav();
    const b = document.querySelector('.boss-followup-nav');
    if (b) b.classList.toggle('active', view === 'bossFollowup');
    if (view === 'bossFollowup') {
      const title = document.querySelector('#viewTitle');
      if (title) title.textContent = '부장 대응·팔로업';
    }
  };

  const originalRender = window.render;
  window.render = function(){
    if (view === 'bossFollowup') return renderBoss();
    return originalRender();
  };

  function updateCount(){
    const el = document.querySelector('#countBossFollowup');
    if (el) el.textContent = ranked().length;
  }
  addNav();
  updateCount();
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => { addNav(); updateCount(); }, {once:true});
})();
