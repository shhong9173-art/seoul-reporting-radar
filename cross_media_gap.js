(() => {
  const OWN_RE = /아이뉴스24|iNews24|inews24/i;
  const EVENT_RE = /인베스터데이|주주총회|설명회|세미나|포럼|엑스포|컨퍼런스|부스투어|기조연설|발표회/;
  const STRATEGY_RE = /수주|계약|공급|증설|투자|공장|생산중단|생산 중단|가동|감산|철수|매각|인수|합작|구조조정|관세|반덤핑|통상|가격|원가|마진|리콜|화재|노조|파업|임단협|판매|자율주행|HVDC|변압기|전력망|해상풍력|풍력|태양광|석유화학|스페셜티|배터리소재/i;
  const RELEASE_RE = /보도자료|자료제공|자료를 배포|배포자료|회사\s*(?:측|관계자)?.{0,8}(?:발표|공개)|정부\s*(?:발표|자료)|산업부\s*(?:발표|자료)|공정위\s*(?:발표|자료)|금감원\s*(?:발표|자료)|공시(?:에|를|했다)?/;
  const STOP = new Set('및 의 을 를 이 가 은 는 에서 으로 로 와 과 에 대한 관련 올해 오늘 최근 국내 글로벌 업계 시장 기업 사업 계획 추진 전망 기자 보도 밝혔다 따르면 통해 위한 대한 있다 없다 것으로 가운데 당시 이후 이전 현재 이번 등 전 the and for with from this that auto automotive news company market vehicle vehicles'.split(' '));
  const ACTION = new Set('수주 계약 공급 증설 투자 공장 생산능력 생산중단 가동 감산 철수 매각 인수 합작 구조조정 관세 반덤핑 통상 가격 원가 마진 리콜 화재 노조 파업 임단협 판매 자율주행 HVDC 변압기 전력망 해상풍력 풍력 태양광 석유화학 스페셜티 배터리소재'.split(' '));

  const ownSource = (name='') => OWN_RE.test(String(name));
  const cleanTitle = (t='') => String(t).replace(/^\s*[\[\(][^\]\)]{0,20}[\]\)]\s*/, '').replace(/\s*[-|｜]\s*[^-||｜]{1,30}\s*$/, '').trim();
  const tokens = (text='') => new Set((String(text).toLowerCase().match(/[가-힣A-Za-z0-9]{2,}/g) || []).filter(w => !STOP.has(w) && !/^\d+$/.test(w)));
  const jaccard = (a,b) => {
    const A = tokens(a), B = tokens(b);
    if (!A.size && !B.size) return 1;
    let inter = 0; A.forEach(x => { if (B.has(x)) inter += 1; });
    return inter / Math.max(1, A.size + B.size - inter);
  };
  const nums = (text='') => new Set((String(text).match(/\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?(?:조원|억원|만원|달러|만대|천대|대|명|%|톤|MW|GW|GWh|MWh|억|조)/g) || []).map(x => x.replace(/\s+/g,'')));
  const actionTokens = (text='') => new Set([...ACTION].filter(k => String(text).toLowerCase().includes(k.toLowerCase())));
  const companySet = (x) => new Set((x?.companies || []).map(String));
  const unionText = (x) => `${x?.title || ''} ${x?.summary || ''}`;

  function pairAnalysis(base, item) {
    const bt = cleanTitle(base?.title || '');
    const it = cleanTitle(item?.title || '');
    const titleSim = jaccard(bt, it);
    const summarySim = jaccard(base?.summary || '', item?.summary || '');
    const bn = nums(unionText(base));
    const inn = nums(unionText(item));
    const newNumbers = [...inn].filter(n => !bn.has(n));
    const ba = actionTokens(unionText(base));
    const ia = actionTokens(unionText(item));
    const newActions = [...ia].filter(a => !ba.has(a));
    const bc = companySet(base);
    const ic = companySet(item);
    const newCompanies = [...ic].filter(c => !bc.has(c));
    const newFactCount = Math.min(5, newNumbers.length + newActions.length + newCompanies.length);
    const releaseHint = RELEASE_RE.test(unionText(item));
    const copyScore = (titleSim * 0.65) + (summarySim * 0.35);
    const copyLike = copyScore >= 0.70 && titleSim >= 0.58 && newFactCount === 0;
    const independentLike = !copyLike && (titleSim < 0.58 || summarySim < 0.30 || newFactCount >= 2);
    return {titleSim, summarySim, newNumbers, newActions, newCompanies, newFactCount, releaseHint, copyScore, copyLike, independentLike};
  }

  const groupMap = () => {
    const m = {};
    items.filter(x => !x.global).forEach(x => {
      const k = x.clusterId || x.id;
      (m[k] ??= []).push(x);
    });
    return m;
  };

  function analyzeGroup(id, group) {
    const g = group.slice().sort((a,b) => new Date(a.published) - new Date(b.published));
    const sources = [...new Set(g.map(x => String(x.sourceName || '').trim()).filter(Boolean))];
    const own = sources.some(ownSource);
    const latest = g[g.length - 1];
    const anchor = g[0];
    const latestAge = Math.max(0, (Date.now() - new Date(latest?.published || 0)) / 3600000);
    const eventOnly = g.every(x => x.event || EVENT_RE.test(x.title || '')) && !g.some(x => x.concreteNumber || STRATEGY_RE.test(unionText(x)));
    const details = g.map((x, idx) => idx === 0
      ? {item:x, titleSim:1, summarySim:1, newNumbers:[], newActions:[], newCompanies:[], newFactCount:0, releaseHint:RELEASE_RE.test(unionText(x)), copyScore:1, copyLike:false, independentLike:false}
      : {item:x, ...pairAnalysis(anchor, x)}
    );
    const later = details.slice(1);
    const copyLikes = later.filter(x => x.copyLike).length;
    const independentLikes = later.filter(x => x.independentLike).length;
    const materialAdds = later.filter(x => x.newFactCount > 0).length;
    const releaseHints = details.filter(x => x.releaseHint).length;
    const relayRatio = later.length ? copyLikes / later.length : 0;
    let spreadType = '혼합 확산';
    if (later.length && relayRatio >= 0.67 && releaseHints >= 1) spreadType = '동일 발표·자료 확산 가능성';
    else if (independentLikes >= 1 || materialAdds >= Math.max(1, Math.ceil(later.length * 0.5))) spreadType = '복수 매체 별도 취재 정황';
    else if (relayRatio >= 0.67) spreadType = '동일 정보 재전달 가능성';

    const score = Math.min(99,
      42 + Math.min(24, sources.length * 8) + Math.min(12, g.length * 3) +
      (materialAdds >= 1 ? 8 : 0) + (independentLikes >= 1 ? 8 : 0) +
      (latestAge <= 12 ? 10 : latestAge <= 24 ? 6 : latestAge <= 48 ? 3 : 0)
    );
    const independenceScore = Math.min(99,
      35 + independentLikes * 18 + materialAdds * 8 + Math.min(15, sources.length * 3) + (releaseHints === 0 ? 6 : 0)
    );
    return {
      id, g, sources, own, latest, anchor, latestAge, eventOnly, details,
      copyLikes, independentLikes, materialAdds, releaseHints, relayRatio,
      spreadType, score, independenceScore
    };
  }

  const gapGroups = () => Object.entries(groupMap())
    .map(([id,g]) => analyzeGroup(id,g))
    .filter(c => !c.own && c.sources.length >= 2 && c.g.length >= 2 && c.latestAge <= 72 && !c.eventOnly)
    .sort((a,b) => b.independenceScore - a.independenceScore || b.score - a.score || b.sources.length - a.sources.length || new Date(b.latest.published) - new Date(a.latest.published));

  const gapById = id => gapGroups().find(c => c.id === id);

  function isGapItem(x) {
    if (!x || x.global) return false;
    const id = x.clusterId || x.id;
    return !!gapById(id);
  }

  function safe(v) { return esc(v); }
  function pct(v) { return `${Math.round((v || 0) * 100)}%`; }
  function timeLabel(x) { return x?.publishedLabel || String(x?.published || '').replace('T',' ').slice(0,16); }

  function renderGap() {
    const groups = gapGroups().slice(0, 15);
    const cards = document.querySelector('#cards');
    if (!cards) return;
    cards.innerHTML = groups.length ? groups.map(c => {
      const lead = c.latest;
      const title = lead.title;
      const freshness = c.latestAge < 24 ? '오늘 확산' : c.latestAge < 48 ? '최근 48시간' : '최근 72시간';
      const companyText = [...new Set(c.g.flatMap(x => x.companies || []))].slice(0,5);
      const reason = c.spreadType === '복수 매체 별도 취재 정황'
        ? `${c.independentLikes}개 매체에서 독립 취재 정황, ${c.materialAdds}건에서 추가 팩트가 확인됩니다.`
        : c.spreadType === '동일 발표·자료 확산 가능성'
          ? `${c.sources.length}개 매체로 확산됐지만 동일 발표·자료 재전파 가능성도 함께 확인됩니다.`
          : `${c.sources.length}개 매체가 같은 이슈를 다룬 타이밍입니다.`;
      return `<article class="card follow" onclick="openCrossMediaGap('${safe(c.id).replace(/'/g,"\\'")}')">
        <div class="card-top"><span class="badge follow">타사 다매체 · 미보도</span><span class="score">${c.independenceScore}점</span></div>
        <div class="meta">${freshness} · ${safe(lead.category || '')} · ${c.sources.length}개 매체 · 최초 ${safe(c.anchor.sourceName || '미상')} ${safe(timeLabel(c.anchor))}</div>
        <div class="title">${safe(title)}</div>
        <div class="summary"><b class="why">${safe(c.spreadType)}</b><br>${safe(reason)}</div>
        <div class="signal-row"><span class="signal">관련 ${c.g.length}건</span><span class="signal">매체 ${c.sources.length}곳</span><span class="signal">추가 팩트 ${c.materialAdds}건</span></div>
        <div class="quote"><b>팔로업 포인트</b><ul>
          <li>${c.spreadType === '동일 발표·자료 확산 가능성' ? '기사들의 공통 원문·보도자료·기관 발표를 추적' : '최초 관측 매체가 확보한 추가 취재 사실이 무엇인지 확인'}</li>
          <li>${c.independentLikes ? '매체별로 서로 다른 숫자·고객사·계약조건이 있는지 대조' : '복수 매체가 동일 소스를 인용한 것인지 확인'}</li>
          <li>아이뉴스24가 추가로 확인할 수 있는 국내 기업·정부의 공식 입장과 숫자를 확인</li>
        </ul></div>
        <div class="bottom">${companyText.map(cn=>`<span class="tag">${safe(cn)}</span>`).join('')}<span class="tag">${safe(c.sources.join(', '))}</span></div>
      </article>`;
    }).join('') : '<div class="card"><div class="title">현재 타사 다매체·아이뉴스24 미보도 이슈가 없습니다.</div><div class="summary">복수 매체 확산 + 최근 72시간 + 아이뉴스24 미보도 조건을 동시에 충족한 이슈만 표시합니다.</div></div>';
    document.querySelector('#resultCount').textContent = `${groups.length}개 이슈`;
  }

  window.openCrossMediaGap = function(id) {
    const c = gapById(id);
    if (!c) return;
    const title = c.latest.title;
    const timeline = c.details.map((d,idx) => {
      const item = d.item;
      const relation = idx === 0 ? '최초 관측' : d.independentLike ? '별도 취재 정황' : d.copyLike ? '재전파 유사' : d.newFactCount > 0 ? '추가 정보 포함' : '유사 보도';
      const extras = [];
      if (d.newNumbers.length) extras.push(`새 숫자 ${d.newNumbers.slice(0,4).join(', ')}`);
      if (d.newCompanies.length) extras.push(`새 기업 ${d.newCompanies.slice(0,3).join(', ')}`);
      if (d.newActions.length) extras.push(`새 신호 ${d.newActions.slice(0,3).join(', ')}`);
      return `<div style="padding:11px 0;border-bottom:1px solid #eee">
        <div><b>${safe(item.sourceName || '매체 미상')}</b> · ${safe(timeLabel(item))} <span class="tag">${relation}</span></div>
        <div style="margin-top:5px">${safe(item.title || '')}</div>
        <div class="muted" style="margin-top:5px;font-size:11px">최초 기사 제목 유사도 ${pct(d.titleSim)} · 본문 유사도 ${pct(d.summarySim)}${extras.length ? ' · ' + safe(extras.join(' / ')) : ''}</div>
      </div>`;
    }).join('');
    const commonSource = c.releaseHints >= 1 ? '보도자료·기관 발표 등 공통 원문 가능성 확인 필요' : '최초 관측 매체를 원출처 후보로 우선 추적';
    const q = [
      `${c.anchor.sourceName || '최초 관측 매체'}가 처음 확인한 원문·취재원은 무엇인가?`,
      c.spreadType === '복수 매체 별도 취재 정황' ? '매체별로 추가 확인한 숫자·계약조건·고객사 등 차별 정보는 무엇인가?' : '여러 매체가 동일 자료를 인용한 것인지, 각자 취재한 것인지 확인',
      '아이뉴스24가 확보할 수 있는 국내 기업·정부의 추가 공식 입장과 새 숫자는 무엇인가?'
    ];
    const companies = [...new Set(c.g.flatMap(x => x.companies || []))];
    $('#detail').innerHTML = `<span class="badge follow">타사 다매체 · 미보도</span><h2>${safe(title)}</h2>
      <div class="scorebox"><div><small>매체</small><b>${c.sources.length}</b></div><div><small>관련 기사</small><b>${c.g.length}</b></div><div><small>별도 취재 정황</small><b>${c.independentLikes}</b></div><div><small>추가 팩트</small><b>${c.materialAdds}</b></div></div>
      <div class="quote"><b>확산 성격</b><br>${safe(c.spreadType)}<br><span class="muted">${safe(commonSource)}</span></div>
      <h3>최초 관측</h3><p>${safe(c.anchor.sourceName || '매체 미상')} · ${safe(timeLabel(c.anchor))}</p>
      <h3>매체별 비교</h3>${timeline}
      <h3>팔로업 질문</h3>${list(q)}
      <h3>관련 기업</h3>${list(companies)}
      <h3>대표 기사 원문</h3><p><a href="${safe(c.latest.url || '#')}" target="_blank" rel="noopener">최신 기사 열기 ↗</a></p>`;
    $('#modal').classList.remove('hidden');
  };

  window.crossMediaGapCount = () => gapGroups().length;
  window.crossMediaGapOpen = renderGap;
  window.crossMediaGapItem = isGapItem;

  const originalSyncNav = window.syncNav;
  const originalRender = window.render;
  const originalCounts = window.counts;

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
