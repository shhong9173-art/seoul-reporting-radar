(() => {
  const OWN_RE = /아이뉴스24|iNews24|inews24/i;
  const EVENT_RE = /인베스터데이|주주총회|설명회|세미나|포럼|엑스포|컨퍼런스|부스투어|기조연설|발표회/;
  const STRATEGY_RE = /수주|계약|공급|증설|투자|공장|생산중단|생산 중단|가동|감산|철수|매각|인수|합작|구조조정|관세|반덤핑|통상|가격|원가|마진|리콜|화재|노조|파업|임단협|판매|자율주행|HVDC|변압기|전력망|해상풍력|풍력|태양광|석유화학|스페셜티|배터리소재/i;

  // 보도자료 원문·배포 서비스는 이 레이더에서 하드 제외한다.
  const PRESS_SOURCE_RE = /뉴스와이어|Newswire|PRNewswire|Business Wire|GlobeNewswire|EIN Presswire|PRWeb|Accesswire|Press Release/i;
  const OFFICIAL_RELEASE_SOURCE_RE = /뉴스룸|미디어센터|프레스센터|press room|media center/i;
  const PRESS_TITLE_RE = /^\s*(?:\[[^\]]*\s*)?(?:보도자료|자료제공|자료배포|보도자료 배포)(?:\]|[:：)]|\s|$)/i;
  const PRESS_PREFIX_RE = /^\s*(?:보도자료|자료제공|자료배포|보도자료 배포|press release)\b/i;
  const PRESS_TEMPLATE_RE = /언론보도자료|본 자료는 .*보도자료|배포일시|담당부서\s*[:：].*(?:홍보|커뮤니케이션)|문의처\s*[:：].*(?:홍보|커뮤니케이션)/i;

  const STOP = new Set('및 의 을 를 이 가 은 는 에서 으로 로 와 과 에 대한 관련 올해 오늘 최근 국내 글로벌 업계 시장 기업 사업 계획 추진 전망 기자 보도 밝혔다 따르면 통해 위한 대한 있다 없다 것으로 가운데 당시 이후 이전 현재 이번 등 전 the and for with from this that auto automotive news company market vehicle vehicles'.split(' '));
  const ACTION = new Set('수주 계약 공급 증설 투자 공장 생산능력 생산중단 가동 감산 철수 매각 인수 합작 구조조정 관세 반덤핑 통상 가격 원가 마진 리콜 화재 노조 파업 임단협 판매 자율주행 HVDC 변압기 전력망 해상풍력 풍력 태양광 석유화학 스페셜티 배터리소재'.split(' '));

  const ownSource = (name='') => OWN_RE.test(String(name));
  const cleanTitle = (t='') => String(t).replace(/^\s*[\[\(][^\]\)]{0,30}[\]\)]\s*/, '').replace(/\s*[-|｜]\s*[^-||｜]{1,30}\s*$/, '').trim();
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

  function pressReleaseInfo(x) {
    const title = String(x?.title || '');
    const source = String(x?.sourceName || '');
    const summary = String(x?.summary || '');
    let score = 0;
    const reasons = [];
    if (PRESS_SOURCE_RE.test(source)) { score += 5; reasons.push('배포서비스'); }
    if (OFFICIAL_RELEASE_SOURCE_RE.test(source)) { score += 5; reasons.push('기업·기관 원문 채널'); }
    if (PRESS_TITLE_RE.test(title)) { score += 5; reasons.push('보도자료 제목'); }
    if (PRESS_PREFIX_RE.test(summary)) { score += 4; reasons.push('본문 보도자료 머리말'); }
    if (PRESS_TEMPLATE_RE.test(`${title} ${summary}`)) { score += 3; reasons.push('배포문 템플릿'); }
    return {isPressRelease: score >= 5, score, reasons};
  }

  function pairAnalysis(base, item) {
    const titleSim = jaccard(cleanTitle(base?.title || ''), cleanTitle(item?.title || ''));
    const summarySim = jaccard(base?.summary || '', item?.summary || '');
    const baseNums = nums(unionText(base));
    const itemNums = nums(unionText(item));
    const newNumbers = [...itemNums].filter(n => !baseNums.has(n));
    const baseActions = actionTokens(unionText(base));
    const itemActions = actionTokens(unionText(item));
    const newActions = [...itemActions].filter(a => !baseActions.has(a));
    const baseCompanies = companySet(base);
    const itemCompanies = companySet(item);
    const newCompanies = [...itemCompanies].filter(c => !baseCompanies.has(c));
    const newFactCount = Math.min(5, newNumbers.length + newActions.length + newCompanies.length);
    const copyScore = (titleSim * 0.65) + (summarySim * 0.35);
    const copyLike = copyScore >= 0.70 && titleSim >= 0.58 && newFactCount === 0;
    const independentLike = !copyLike && (titleSim < 0.58 || summarySim < 0.30 || newFactCount >= 2);
    return {titleSim, summarySim, newNumbers, newActions, newCompanies, newFactCount, copyScore, copyLike, independentLike};
  }

  function groupMap() {
    const m = {};
    items.filter(x => !x.global).forEach(x => {
      const k = x.clusterId || x.id;
      (m[k] ??= []).push(x);
    });
    return m;
  }

  function analyzeGroup(id, group) {
    const raw = group.slice().sort((a,b) => new Date(a.published) - new Date(b.published));
    const releaseItems = raw.filter(x => pressReleaseInfo(x).isPressRelease);
    const media = raw.filter(x => !pressReleaseInfo(x).isPressRelease);
    const sources = [...new Set(media.map(x => String(x.sourceName || '').trim()).filter(Boolean))];
    const own = sources.some(ownSource);
    const latest = media.length ? media[media.length - 1] : raw[raw.length - 1];
    const anchor = media[0];
    const latestAge = Math.max(0, (Date.now() - new Date(latest?.published || 0)) / 3600000);
    const eventOnly = media.length > 0 && media.every(x => x.event || EVENT_RE.test(x.title || '')) && !media.some(x => x.concreteNumber || STRATEGY_RE.test(unionText(x)));

    const details = media.map((x, idx) => idx === 0
      ? {item:x, titleSim:1, summarySim:1, newNumbers:[], newActions:[], newCompanies:[], newFactCount:0, copyScore:1, copyLike:false, independentLike:false}
      : {item:x, ...pairAnalysis(anchor, x)}
    );
    const later = details.slice(1);
    const copyLikes = later.filter(x => x.copyLike).length;
    const independentLikes = later.filter(x => x.independentLike).length;
    const materialAdds = later.filter(x => x.newFactCount > 0).length;

    // 배포자료가 실질적인 원문이고 이후 언론 기사들이 사실상 그대로 재전달한 경우 제외한다.
    let releaseRelays = 0;
    let releaseMaterialAdds = 0;
    if (releaseItems.length && media.length) {
      media.forEach(item => {
        const comparisons = releaseItems.map(r => ({item, ...pairAnalysis(r, item)}));
        const best = comparisons.sort((a,b) => b.copyScore - a.copyScore)[0];
        if (!best) return;
        if (best.copyLike) releaseRelays += 1;
        if (best.newFactCount > 0) releaseMaterialAdds += 1;
      });
    }
    const releaseDriven = releaseItems.length > 0 && media.length >= 2 && releaseRelays / media.length >= 0.67 && releaseMaterialAdds === 0 && materialAdds === 0 && independentLikes === 0;
    const releaseOnly = media.length === 0;

    const score = Math.min(99,
      42 + Math.min(24, sources.length * 8) + Math.min(12, media.length * 3) +
      (materialAdds >= 1 ? 8 : 0) + (independentLikes >= 1 ? 8 : 0) +
      (latestAge <= 12 ? 10 : latestAge <= 24 ? 6 : latestAge <= 48 ? 3 : 0)
    );
    const independenceScore = Math.min(99,
      35 + independentLikes * 18 + materialAdds * 8 + Math.min(15, sources.length * 3) + (releaseItems.length === 0 ? 6 : 0)
    );
    return {id, raw, releaseItems, media, sources, own, latest, anchor, latestAge, eventOnly, details, copyLikes, independentLikes, materialAdds, releaseRelays, releaseMaterialAdds, releaseDriven, releaseOnly, score, independenceScore};
  }

  const gapGroups = () => Object.entries(groupMap())
    .map(([id,g]) => analyzeGroup(id,g))
    .filter(c => !c.own && !c.releaseOnly && !c.releaseDriven && c.sources.length >= 2 && c.media.length >= 2 && c.latestAge <= 72 && !c.eventOnly)
    .sort((a,b) => b.independenceScore - a.independenceScore || b.score - a.score || b.sources.length - a.sources.length || new Date(b.latest.published) - new Date(a.latest.published));

  const gapById = id => gapGroups().find(c => c.id === id);
  const isGapItem = x => !!x && !x.global && !!gapById(x.clusterId || x.id);
  const safe = v => esc(v);
  const pct = v => `${Math.round((v || 0) * 100)}%`;
  const timeLabel = x => x?.publishedLabel || String(x?.published || '').replace('T',' ').slice(0,16);

  function renderGap() {
    const groups = gapGroups().slice(0, 15);
    const cards = document.querySelector('#cards');
    if (!cards) return;
    cards.innerHTML = groups.length ? groups.map(c => {
      const lead = c.latest;
      const title = lead.title;
      const freshness = c.latestAge < 24 ? '오늘 확산' : c.latestAge < 48 ? '최근 48시간' : '최근 72시간';
      const companies = [...new Set(c.media.flatMap(x => x.companies || []))].slice(0,5);
      const reason = c.independentLikes > 0
        ? `${c.independentLikes}개 매체에서 독립 취재 정황, ${c.materialAdds}건에서 추가 팩트가 확인됩니다.`
        : `${c.sources.length}개 매체가 같은 이슈를 다루고 있으며, 매체별 차이를 확인할 필요가 있습니다.`;
      return `<article class="card follow" onclick="openCrossMediaGap('${safe(c.id).replace(/'/g,"\\'")}')">
        <div class="card-top"><span class="badge follow">타사 다매체 · 미보도</span><span class="score">${c.independenceScore}점</span></div>
        <div class="meta">${freshness} · ${safe(lead.category || '')} · ${c.sources.length}개 매체 · 최초 ${safe(c.anchor.sourceName || '미상')} ${safe(timeLabel(c.anchor))}</div>
        <div class="title">${safe(title)}</div>
        <div class="summary"><b class="why">복수 매체 별도 취재 정황</b><br>${safe(reason)}</div>
        <div class="signal-row"><span class="signal">관련 ${c.media.length}건</span><span class="signal">매체 ${c.sources.length}곳</span><span class="signal">추가 팩트 ${c.materialAdds}건</span></div>
        <div class="quote"><b>팔로업 포인트</b><ul>
          <li>최초 관측 매체가 확보한 추가 취재 사실이 무엇인지 확인</li>
          <li>매체별 숫자·고객사·계약조건·사업내용 차이를 대조</li>
          <li>아이뉴스24가 추가로 확인할 수 있는 국내 기업·정부의 공식 입장과 숫자를 확인</li>
        </ul></div>
        <div class="bottom">${companies.map(cn=>`<span class="tag">${safe(cn)}</span>`).join('')}<span class="tag">${safe(c.sources.join(', '))}</span></div>
      </article>`;
    }).join('') : '<div class="card"><div class="title">현재 타사 다매체·아이뉴스24 미보도 이슈가 없습니다.</div><div class="summary">보도자료 원문·배포 서비스는 제외하고, 복수 매체의 실제 기사 확산만 비교합니다.</div></div>';
    document.querySelector('#resultCount').textContent = `${groups.length}개 이슈`;
  }

  window.openCrossMediaGap = function(id) {
    const c = gapById(id);
    if (!c) return;
    const timeline = c.details.map((d,idx) => {
      const item = d.item;
      const relation = idx === 0 ? '최초 관측' : d.independentLike ? '별도 취재 정황' : d.copyLike ? '재전파 유사' : d.newFactCount > 0 ? '추가 정보 포함' : '유사 보도';
      const extras = [];
      if (d.newNumbers.length) extras.push(`새 숫자 ${d.newNumbers.slice(0,4).join(', ')}`);
      if (d.newCompanies.length) extras.push(`새 기업 ${d.newCompanies.slice(0,3).join(', ')}`);
      if (d.newActions.length) extras.push(`새 신호 ${d.newActions.slice(0,3).join(', ')}`);
      return `<div style="padding:11px 0;border-bottom:1px solid #eee"><div><b>${safe(item.sourceName || '매체 미상')}</b> · ${safe(timeLabel(item))} <span class="tag">${relation}</span></div><div style="margin-top:5px">${safe(item.title || '')}</div><div class="muted" style="margin-top:5px;font-size:11px">최초 기사 제목 유사도 ${pct(d.titleSim)} · 본문 유사도 ${pct(d.summarySim)}${extras.length ? ' · ' + safe(extras.join(' / ')) : ''}</div></div>`;
    }).join('');
    const releaseNote = c.releaseItems.length ? `<p class="muted">보도자료 원문 ${c.releaseItems.length}건은 비교 대상에서 제외했습니다. 언론 기사에 실질적인 추가 취재가 있는지 별도로 판별합니다.</p>` : '<p class="muted">보도자료 원문·배포 서비스는 하드 제외했습니다.</p>';
    const detail = document.querySelector('#detail');
    if (!detail) return;
    detail.innerHTML = `<div class="badge follow">타사 다매체 · 미보도</div><h2>${safe(c.latest.title)}</h2>${releaseNote}<div class="scorebox"><div><small>매체</small><b>${c.sources.length}</b></div><div><small>기사</small><b>${c.media.length}</b></div><div><small>독립취재 정황</small><b>${c.independentLikes}</b></div><div><small>추가 팩트 기사</small><b>${c.materialAdds}</b></div></div><h3>매체별 확산 비교</h3>${timeline}<h3>아이뉴스24 팔로업 포인트</h3><ul><li>최초 취재원이 무엇인지 확인</li><li>후발 기사에서 새로 추가된 숫자·고객사·계약조건 확인</li><li>기업·정부 공식 답변으로 사실관계 교차확인</li></ul>`;
    document.querySelector('#modal')?.classList.remove('hidden');
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
    b.title = '보도자료 원문·배포 서비스 제외';
    b.onclick = () => { view='crossMediaGap'; cat=''; company=''; query=''; syncNav(); render(); };
    const anchor = nav.querySelector('[data-view="competition"]');
    if (anchor) anchor.insertAdjacentElement('afterend', b); else nav.appendChild(b);
    window.counts();
  }

  addNav();
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', addNav, {once:true});
})();
