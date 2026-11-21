// 다가오는 해외 판정 일정(11-19 기자 "단독을 위해서 더 노력해봐").
// 레이더는 해외 판정을 '나온 뒤' 잡았다(영국 정부 고시·EU 관보·CBSA 문서). 판정 전에 준비할 수 있게, 이미 모아 둔 자료에 적힌 날짜만 모은다:
//   캐나다 CBSA 사건 목록의 결론 예정일(Concludes on …) · 캐나다 CITT 사건 일정 표 · 호주 ATRC 사건 페이지의 PAD·SEF·최종 권고 기한
//   · EU 개시 공고에서 규정으로 계산한 시한(eu_trade_defence_watch.proceedings — 반덤핑 기본규정 제7조 1항·제6조 9항·제11조 5항·제19a조, 세이프가드 공고 8항).
// 날짜는 누리집 표기이거나 규정상 시한이다 — 발표 예정일이 아니다. 새로 지어낸 날짜는 없다(호주 장관 결정 시한만 '최종 권고 기한+30일' 추정이라고 적는다).

const CBSA_KIND = { 'i-e': '조사', 'er-rre': '종료재심', 'ar-ra': '행정재심' };
const AU_KIND = { investigation: '조사', continuation: '종료재심', review: '재심', 'accelerated review': '신속 재심', 'anti-circumvention': '우회 조사',
  exemption: '면제 조사', 'duty assessment': '관세 정산' };
const AU_STEPS = [['PAD earliest date', '예비 판정(PAD) 가능일부터'], ['SEF no later than', '필수사실 보고서(SEF) 공개 기한'],
  ['Final recommendation due no later than', '최종 권고(장관 보고) 기한']];
const MONTHS = { january: 1, february: 2, march: 3, april: 4, may: 5, june: 6, july: 7, august: 8, september: 9, october: 10, november: 11, december: 12 };
const AU_MINISTER = '호주 관세법(2011 개정 Customs Amendment (Anti-dumping Improvements) Act): 장관은 권고를 받은 뒤 30일 안에 결정 — 특별한 사정이면 공고하고 연장, 종료재심은 조치 만료일 전';

const kstDay = (ms) => new Date(ms + 9 * 3600000).toISOString().slice(0, 10);
const addDays = (iso, n) => new Date(Date.parse(`${iso}T00:00:00Z`) + n * 86400000).toISOString().slice(0, 10);
const addMonths = (iso, n) => {
  const [y, m, d] = iso.split('-').map(Number);
  const t = new Date(Date.UTC(y, m - 1 + n, 1));
  const last = new Date(Date.UTC(t.getUTCFullYear(), t.getUTCMonth() + 1, 0)).getUTCDate();
  return new Date(Date.UTC(t.getUTCFullYear(), t.getUTCMonth(), Math.min(d, last))).toISOString().slice(0, 10);
};
// 인도 반덤핑 규칙(Customs Tariff Anti-Dumping Rules 1995): 조사는 개시 1년 안 최종 판정(Rule 17(1), 중앙정부가 6개월 연장 가능),
// 재심은 개시 12개월 안 종결(Rule 23(2)). 우회 조사는 계산하지 않는다(11-21 — 규정 확인 전)
// 출입 업종 품목 낱말(eu_trade_defence_watch.BEAT_PRODUCT와 같은 결 + 운영 11-21: 인도 TDI 재심이 '업종 밖'으로 붙음 — 한화솔루션 TDI)
const BEAT_PRODUCT = /steel|iron|stainless|plate|coil|tube|pipe|wire rod|rebar|tinplate|ferro|electrical steel|zinc|lead\b|copper|alumin|cable|wire|transformer|tyre|tire|vehicle|battery|lithium|polyvinyl|\bPVC\b|polyethylene|polypropylene|\bPET\b|acryl|epoxy|styrene|\bABS\b|rubber|glycol|ethylene|propylene|butadiene|phenol|acetone|caprolactam|polycarbonate|polyamide|methyl|alcohol|isocyanate|\bTDI\b|\bMDI\b|naphtha|solar|silicon/i;
const DGTR_RULE = { original: 'Rule 17(1) — 개시 1년 안 최종 판정, 중앙정부가 6개월 연장 가능', review: 'Rule 23(2) — 재심은 개시 12개월 안 종결' };
// 호주 사건 페이지 날짜('31 March 2027', '5 March 2027') → ISO. 못 읽으면 ''
export function dmyIso(s) {
  const m = String(s ?? '').match(/\b(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\b/);
  const mon = m && MONTHS[m[2].toLowerCase()];
  return mon ? `${m[3]}-${String(mon).padStart(2, '0')}-${m[1].padStart(2, '0')}` : '';
}
const auDate = (dates, key) => Object.entries(dates ?? {}).find(([k]) => k.replace(/\*+/g, '').trim() === key)?.[1];

// docs: 피드 이름 → 저장 문서(radarTodayData의 d.docs). 돌려주는 줄은 날짜순.
// { date, approx, country, agency, what, title, who[], whoNote, note, basis, url, beat, src }
export function foreignAhead(docs, nowMs, { days = 45, past = 60 } = {}) {
  const today = kstDay(nowMs);
  const until = addDays(today, days);
  const inWin = (d) => d && d >= today && d <= until;
  const out = [];
  const tr = docs?.['trade-remedy'] ?? {};

  // 캐나다 CBSA — 사건 목록의 '결론 예정일'
  const measures = Object.values(tr.cbsa?.measures ?? {});
  for (const [list, v] of Object.entries(tr.cbsa?.lists ?? {})) {
    for (const [key, c] of Object.entries(v?.cases ?? {})) {
      if (c?.state !== 'Concludes' || !inWin(c.stateDate)) continue;
      // 사건 열쇠는 'ar-ra/lp22026/lp2202601'(cbsa_cases.case_key) — 가운데 폴더에서 연도를 떼면 조치 코드(LP2)
      const folder = String(key).split('/')[1] ?? String(key);
      const code = folder.replace(/\d{4}$/, '').toUpperCase();
      const m = measures.find((x) => String(x.code ?? '').toUpperCase() === code);
      const last = [...(c.docs ?? [])].sort((a, b) => String(b.date ?? '').localeCompare(String(a.date ?? '')))[0];
      out.push({ date: c.stateDate, country: '캐나다', agency: 'CBSA', what: `${CBSA_KIND[list] ?? list} 결론 예정`, src: 'cbsa', beat: true,
        title: String(c.title ?? '').replace(/\s*[—-]\s*Conclud.*$/i, ''), who: [...new Set([...(c.companies ?? []), ...(m?.companies ?? [])])],
        whoNote: (m?.companies ?? []).length ? `시행 중 조치 ${m.code} 한국 수출자 표` : '', basis: 'CBSA 사건 목록에 적힌 결론 예정일', url: last?.url ?? m?.url ?? '' });
    }
  }
  // 캐나다 CITT — 사건 일정 표(아직 안 나온 문서)
  for (const [no, c] of Object.entries(tr.citt?.cases ?? {})) {
    for (const r of c?.rows ?? []) {
      if (r.url || !inWin(r.date)) continue;
      out.push({ date: r.date, country: '캐나다', agency: 'CITT', what: /order|finding|determination/i.test(r.doc ?? '') ? `${r.doc}(피해·조치 연장 결정)` : r.doc, src: 'citt', beat: true,
        title: `${no} ${c.title ?? ''}`.trim(), who: [], basis: 'CITT 사건 일정 표(CITT가 바꿀 수 있음)', url: tr.citt?.url ?? '' });
    }
  }
  // 호주 ATRC — 진행 사건의 PAD·SEF·최종 권고 기한, 그리고 최종 권고 기한이 지났는데 진행 목록에 남은 사건(장관 결정 대기)
  for (const [no, c] of Object.entries(tr.auEpr?.cases ?? {})) {
    if (!c || c.archived || c.missing || c.gone) continue;
    const base = { country: '호주', agency: 'ATRC', src: 'au', beat: true, title: `사건 ${no} · ${c.title ?? c.commodity ?? ''}`, who: c.companies ?? [],
      whoNote: (c.companies ?? []).length ? '문서 제목에 나온 출입처 이름' : '', url: c.url ?? '' };
    const kind = AU_KIND[String(c.kind ?? '').toLowerCase()] ?? c.kind ?? '사건';
    for (const [key, ko] of AU_STEPS) {
      const d = dmyIso(auDate(c.dates, key));
      if (inWin(d)) out.push({ ...base, date: d, what: `${kind} ${ko}`, basis: '사건 페이지 일정(연장 공고로 바뀔 수 있음)' });
    }
    const fr = dmyIso(auDate(c.dates, 'Final recommendation due no later than'));
    if (fr && fr < today && fr >= addDays(today, -past)) {
      out.push({ ...base, date: addDays(fr, 30), approx: true, what: `${kind} 장관 결정 시한(추정 — 최종 권고 기한+30일)`,
        note: `최종 권고 기한 ${fr} 지남 · 진행 목록에 남아 있음(다음 단계 ${c.milestone || '?'}) — 결정 공고(ADN) 전`, basis: AU_MINISTER });
    }
  }
  // 영국 — TRA 사건 예정표(공개기록 'External/Case timeline', 구속력 없음, 달 단위가 많다) 가운데 잠정 판정·SEF·최종 권고·공청회(11-21)
  const UK_KO = [[/Statement of Essential Facts|\bSEF\b/i, '필수사실 고지(SEF) 공개'], [/Final Recommendation|Final Determination/i, '최종 권고(국무장관에게)'],
    [/Provisional/i, '잠정 판정(필요 시)'], [/hearing/i, '공청회']];
  for (const c of tr.tra?.cases ?? []) {
    const tl = c?.timeline;
    for (const it of tl?.items ?? []) {
      const ko = UK_KO.find(([rx]) => rx.test(it.label ?? ''))?.[1];
      if (!ko || !it.to || it.to < today || it.from > until) continue;
      const span = it.exact ? '' : ` — 예정표 '${it.when}'`;
      out.push({ date: it.exact ? it.from : (it.from < today ? it.to : it.from), approx: !it.exact, country: '영국', agency: 'TRA', src: 'uk', beat: true,
        what: `${ko}${span}${it.exact ? '' : '(달 단위)'}`, title: `${c.id} ${c.commodity || c.title || ''}`.trim(), who: c.beatParties ?? [],
        whoNote: (c.beatParties ?? []).length ? '공개기록 당사자' : '', basis: `TRA 사건 예정표(구속력 없음 — ${tl.file ?? tl.title ?? '?'}, 게시 ${tl.published ?? '?'})`, url: tl.url ?? c.url ?? '' });
    }
  }
  // 미국 — 상무부·ITC 관보 고시에 적힌 날짜(명시·게재일+N일), 반덤핑 행정재심 예비 결과는 법정 시한(19 U.S.C. 1675(a)(3)(A), 11-20)
  const US_KO = { prelim: '예비 판정·결과 시한', final: '최종 판정·결과 시한', hearing: '공청회', vote: '표결', itcDet: '판정 시한' };
  for (const it of tr.usAhead ?? []) {
    if (!it || !inWin(it.date)) continue;
    const itc = ['hearing', 'vote', 'itcDet'].includes(it.kind);
    // 상무부 제목은 '품목 From 나라: 단계; 기간', ITC 제목은 '품목 From 나라; 단계'
    const t = String(it.title ?? '');
    const per = t.match(/;\s*(20\d\d(?:-20\d\d)?)\s*$/)?.[1];
    const [head, ...rest] = t.includes(':') ? t.split(':') : t.split(';');
    const stage = rest.join(':').replace(/;\s*20\d\d(?:-20\d\d)?\s*$/, '').replace(/;.*$/, '').trim();
    out.push({ date: it.date, country: '미국', agency: itc ? 'ITC' : '상무부', src: 'us', beat: Boolean(it.beat),
      what: `${US_KO[it.kind] ?? it.kind}${it.extended ? `(연장 추정 — 법정 120일 ${it.first} 지나도록 판정 고시 없음, 법정 최대 180일)` : it.statutory ? '(법정 — 연장 최대 180일)' : ''}`,
      title: `${head.trim().slice(0, 90)}${per ? ` (${per})` : ''}${stage ? ` · ${stage.slice(0, 70)}` : ''}(관보 ${it.pub})`,
      who: it.named ?? [], whoNote: (it.named ?? []).length ? '관보 본문 속 출입처 이름' : '',
      basis: `${it.how} — "${String(it.quote ?? '').slice(0, 200)}"`, url: it.url ?? '' });
    // 11-21: ITC 표결 날짜는 관보에 없다(Sunshine Act 공고가 2026-06 뒤 관보에 0건, usitc.gov 일정표 403). 원심 조사(LTFV·상계 판정)의
    // 상무부 최종 시한이 있으면 ITC 최종 피해 판정의 법정 시한을 덧붙인다 — 상무부 최종 긍정 판정 뒤 45일 안(19 U.S.C. 1673d(b)(2)·1671d(b)(2)).
    // 상무부 최종이 부정이면 ITC 판정은 없다. 행정재심·일몰재심에는 붙이지 않는다
    if (it.kind === 'final' && !itc && /Less Than Fair Value|Countervailable Subsid/i.test(t) && !/Administrative Review|Sunset|Five-Year/i.test(t)) {
      const d45 = addDays(it.date, 45);
      if (inWin(d45)) {
        out.push({ date: d45, approx: true, country: '미국', agency: 'ITC', src: 'us', beat: Boolean(it.beat),
          what: 'ITC 최종 피해 판정(법정 — 상무부 최종 긍정 판정 뒤 45일 안, 상무부 최종이 부정이면 없음)',
          title: `${head.trim().slice(0, 90)}${stage ? ` · ${stage.slice(0, 70)}` : ''}(상무부 최종 시한 ${it.date})`,
          who: it.named ?? [], whoNote: (it.named ?? []).length ? '관보 본문 속 출입처 이름' : '',
          basis: '19 U.S.C. 1673d(b)(2)·1671d(b)(2) — 상무부 최종 시한(관보 고시)+45일로 계산한 최대치. ITC 표결일은 관보에 공고되지 않는다', url: it.url ?? '' });
      }
    }
  }
  // 미국 ITC — EDIS 결정 문서 본문 속 기한(11-21, edis_watch.schedule_from): 지켜보는 337 조사(출입처 당사자)·한국 조사 위원회 판정 문서가
  // 적은 서면 제출 기한·연장 날짜(예: 337-1494 재검토 결정의 서면 마감). 문서에 적힌 날짜 그대로
  // '재검토 여부 결정 기한 연장' 공고의 날짜는 같은 조사에서 그 뒤 재검토 결정(Decision to Review·Not to Review)이 나오면 지난 일이다
  // (11-21 운영: 337-1494 899140 '11-23까지 연장' — 11-20 901438 재검토 결정이 이미 나옴)
  const decidedLater = (x) => /Extend the Due Date for Determining Whether to Review/i.test(x.documentTitle ?? '') && (tr.edis?.docs ?? []).some((y) => y
    && y.investigationNumber === x.investigationNumber && String(y.officialReceivedDate ?? '') > String(x.officialReceivedDate ?? '')
    && /(?:Decision|Determination|Determined)\s+(?:Not\s+)?to\s+Review/i.test(y.documentTitle ?? '') && !/Extend/i.test(y.documentTitle ?? ''));
  for (const x of tr.edis?.docs ?? []) {
    if (!x || !['A', 'B'].includes(x.tier) || !(x.schedule ?? []).length || decidedLater(x)) continue;
    const watched = x.why === '지켜보는 조사의 위원회·판사 결정·공고';
    for (const s of x.schedule) {
      if (!inWin(s.date)) continue;
      out.push({ date: s.date, country: '미국', agency: 'ITC', src: 'us', beat: watched || (x.companies ?? []).length > 0 || /korea/i.test(x.investigationTitle ?? ''),
        what: `${x.investigationNumber} ${x.documentType} 본문 속 기한`, title: `${String(x.investigationTitle ?? '').slice(0, 80)} — 「${String(x.documentTitle ?? '').slice(0, 90)}」(접수 ${String(x.officialReceivedDate ?? '').slice(0, 10)})`,
        who: x.companies ?? [], whoNote: (x.companies ?? []).length ? '문서 속 출입처 이름' : watched ? '지켜보는 337 조사(출입처가 당사자)' : '',
        basis: `EDIS 문서 ${x.id} 본문 — "${String(s.quote ?? '').slice(0, 220)}"`, url: x.url ?? '' });
    }
  }
  // 미국 — 새 한국산 반덤핑·상계관세 청원(EDIS 'Petition', 701·731 조사)의 접수일에서 법정 시한(11-21). 관보 고시가 나오면 그 날짜가 우선이고
  // 이 계산은 고시 전 며칠~몇 주의 준비용이다: 상무부 개시 결정 20일(19 U.S.C. 1671a(c)·1673a(c)), ITC 예비 판정 45일(1671b(a)·1673b(a)),
  // 상무부 예비 판정 — 상계관세 개시+65일(1671b(b)), 반덤핑 개시+140일(1673b(b)) — 개시일은 접수+20일로 어림('~')
  {
    const seen = new Set();
    for (const d of tr.edis?.docs ?? []) {
      if (!d || d.why !== '한국산 조사 제소장·청원' || !/^(?:701|731)-/.test(String(d.investigationNumber ?? '')) || !/^Petition/i.test(d.documentType ?? '')) continue;
      const filed = String(d.officialReceivedDate ?? '').slice(0, 10).replace(/\//g, '-');
      if (!/^\d{4}-\d{2}-\d{2}$/.test(filed) || seen.has(d.investigationNumber)) continue;
      seen.add(d.investigationNumber);
      const cvd = /^701-/.test(d.investigationNumber);
      const name = `${String(d.investigationTitle || d.documentTitle || '').slice(0, 90)} (${d.investigationNumber}, 청원 접수 ${filed})`;
      const beat = BEAT_PRODUCT.test(d.investigationTitle ?? '') || (d.companies ?? []).length > 0;
      const base = { country: '미국', src: 'us', beat, who: d.companies ?? [], whoNote: (d.companies ?? []).length ? 'EDIS 서면 속 출입처 이름' : '', title: name, url: d.url ?? '' };
      const steps = [
        { date: addDays(filed, 20), agency: '상무부', what: '조사 개시 여부 결정(법정 — 청원 접수 20일, 업계 지지 조사 시 최대 40일)', basis: '19 U.S.C. 1671a(c)·1673a(c) — EDIS 청원 접수일+20일' },
        { date: addDays(filed, 45), agency: 'ITC', what: '예비 피해 판정(법정 — 청원 접수 45일)', basis: '19 U.S.C. 1671b(a)·1673b(a) — EDIS 청원 접수일+45일' },
        { date: addDays(filed, 20 + (cvd ? 65 : 140)), approx: true, agency: '상무부', what: `${cvd ? '상계관세' : '반덤핑'} 예비 판정(법정 — 개시 ${cvd ? 65 : 140}일, 연장 시 ${cvd ? 130 : 190}일)`,
          basis: `19 U.S.C. ${cvd ? '1671b(b)' : '1673b(b)'} — 개시일을 접수+20일로 어림` },
      ];
      for (const st of steps) if (inWin(st.date)) out.push({ ...base, ...st });
    }
  }
  // 인도 — DGTR 사건 페이지의 '이번 절차 개시일'에서 규칙으로 계산(진행 중이고 최종 판정문이 아직 없는 한국 관련 사건, 11-21)
  const dgSeen = new Set();
  for (const e of tr.events ?? []) {
    const c = /^in-dgtr/.test(e?.pageId ?? '') ? tr.dgtrCases?.[e.url] : null;
    if (!c || dgSeen.has(e.url) || !c.initiated) continue;
    dgSeen.add(e.url);
    const t = `${c.initTitle ?? ''} ${e.text ?? ''}`;
    if (/circumvention/i.test(t)) continue;
    if (/final\s+finding/i.test(c.findingsTitle ?? '') && String(c.findingsDate ?? '') >= c.initiated) continue;   // 최종 판정문이 나왔다
    const kind = /sunset|review|\bSSR\b|\bMTR\b/i.test(t) ? 'review' : 'original';
    const due = addMonths(c.initiated, 12);
    const late = due < today;
    if (late && kind === 'review') continue;
    const date = late ? addMonths(c.initiated, 18) : due;
    if (!inWin(date)) continue;
    const beatNames = c.parties?.beat ?? [];
    const prod = (String(e.text ?? '').match(/imports? of\s+[“"]?(.+?)[”"]?\s+(?:from|originating)/i) ?? [])[1];
    out.push({ date, country: '인도', agency: 'DGTR', src: 'in', beat: beatNames.length > 0 || BEAT_PRODUCT.test(prod ?? e.text ?? ''),
      what: late ? `최종 판정 시한 지남 → 연장 시 최대(개시 18개월) — 최종 판정문 아직 안 보임` : `${kind === 'review' ? '재심 종결 시한(개시 12개월)' : '최종 판정 시한(개시 1년, 연장 최대 18개월 ' + addMonths(c.initiated, 18) + ')'}`,
      title: `${prod ? prod.slice(0, 70) : String(e.url).split('/').pop().slice(0, 70)} (개시 ${c.initiated})`, who: beatNames,
      whoNote: beatNames.length ? '이해관계자 명단 속 출입처 영문 이름' : '', basis: `인도 반덤핑 규칙 ${DGTR_RULE[kind]} · 개시일은 DGTR 사건 페이지 표기`, url: e.url });
  }
  // 태국 — 재심 중 담보(징수) 끝 날짜(사건 쪽 표기). 11-15 다른 매체 단독(석도·크롬도금 재심, KG스틸)이 '최장 2027-11-12까지'로 쓴 날짜
  for (const x of docs?.['th-trade-remedy']?.cases ?? []) {
    if (!x?.read || !inWin(x.dutyTo) || !/ทบทวน/.test(x.status ?? '')) continue;
    out.push({ date: x.dutyTo, country: '태국', agency: '반덤핑위', what: '재심 중 담보 기간 끝(최종 결정이 먼저 나오면 앞당겨짐)', src: 'th', beat: Boolean(x.productKo),
      title: `${x.code} ${x.productKo ?? String(x.product ?? '').slice(0, 40)}`, who: [], whoNote: x.koreaRate ? `한국 세율 ${x.koreaRate}%(CIF)` : '',
      basis: '태국 무역구제과 사건 쪽 징수 끝 날짜', url: x.url ?? '' });
  }
  // 태국 — 조사 단계 표에서 최근 60일 안에 시작해 끝 날짜가 앞으로인 줄(예: 재심 예비 결과 공개 11-06 → 의견 마감 11-23)
  for (const x of docs?.['th-trade-remedy']?.cases ?? []) {
    for (const st of x?.steps ?? []) {
      const [from, to] = st.dates ?? [];
      if (!from || !to || to <= from || from < addDays(today, -past) || !inWin(to)) continue;
      out.push({ date: to, country: '태국', agency: '반덤핑위', what: `단계 표 끝 날짜 — ${st.no} 「${String(st.label).slice(0, 60)}」(${from} 시작)`, src: 'th', beat: Boolean(x.productKo),
        title: `${x.code} ${x.productKo ?? String(x.product ?? '').slice(0, 40)}`, who: [], whoNote: x.koreaRate ? `한국 세율 ${x.koreaRate}%(CIF)` : '',
        basis: '태국 무역구제과 사건 쪽 조사 단계 표(태국어 단계 이름 — 무엇의 마감인지는 원문)', url: x.url ?? '' });
    }
  }
  // 일본 — 재무성 공고(jp_trade_remedy_watch.py, 11-21). 사건(원산지+품목)마다: 잠정 관세 끝(공고 본문), 조사 끝(연장 공고 본문의 날짜, 없으면
  // 개시+1년 — 관세정률법: 조사는 원칙 1년, 필요하면 6개월까지 연장), 일몰 재심(과세 기간 연장 조사) 결론(개시+1년, 원칙). 확정·종료 공고가 나온 사건은 뺀다
  {
    const groups = new Map();
    for (const e of docs?.['jp-trade-remedy']?.entries ?? []) {
      if (!e?.case || !(e.korea || e.index === 'SG')) continue;
      if (!groups.has(e.case)) groups.set(e.case, []);
      groups.get(e.case).push(e);
    }
    for (const list of groups.values()) {
      list.sort((a, b) => String(a.date).localeCompare(String(b.date)));
      const head = list[list.length - 1];
      const name = `${head.productKo ?? String(head.case).slice(0, 40)}${head.index === 'SG' ? ' 세이프가드' : head.index === 'CVD' ? ' 상계관세' : ' 반덤핑'}`;
      const sg = head.index === 'SG' && !head.korea;
      const base = { country: '일본', agency: '재무성·경산성', src: 'jp', beat: Boolean(head.beat), who: [], safeguard: sg };
      const init = [...list].reverse().find((e) => e.kind === '조사 개시');
      const review = [...list].reverse().find((e) => /^일몰 재심/.test(e.kind ?? ''));
      const doneAfter = (d) => list.some((e) => ['확정 관세 결정', '조사 종료(관세 안 매김)'].includes(e.kind) && e.date >= d);
      const prov = [...list].reverse().find((e) => e.kind === '잠정 관세 결정' && e.detail?.dutyTo);
      // 특수관세부회가 같은 품목 부과를 '적당'이라 한 회의 자료(각의 결정 전 신호) — 그 뒤 확정 공고가 없을 때만
      const council = (docs?.['jp-trade-remedy']?.council?.meetings ?? []).filter((m) => (m.items ?? []).some((i) => i.korea && i.productKo === head.productKo && i.pdf?.recommends))
        .sort((a, b) => String(b.date).localeCompare(String(a.date)))[0];
      const cNote = council && !doneAfter(council.date) ? `특수관세부회 ${council.date} 자료에 부과 '적당'(각의 결정 전)` : '';
      if (prov && !doneAfter(prov.date) && inWin(prov.detail.dutyTo)) {
        out.push({ ...base, date: prov.detail.dutyTo, what: '잠정 관세 끝 — 그 전에 확정 관세를 정하지 않으면 잠정 관세가 끝난다', title: `${name}(잠정 관세 결정 ${prov.date})`, note: cNote,
          whoNote: [prov.detail.rates && `잠정 관세율 ${prov.detail.rates}`, sg ? '세이프가드 — 모든 나라산(한국 포함)' : ''].filter(Boolean).join(' · '),
          basis: '일본 재무성 잠정 관세 결정 공고 본문의 부과 기간', url: prov.url });
      }
      if (init && !doneAfter(init.date)) {
        const ext = [...list].reverse().find((e) => e.kind === '조사 기간 연장' && e.detail?.until && e.date >= init.date);
        const date = ext ? ext.detail.until : addMonths(init.date, 12);
        if (inWin(date)) {
          out.push({ ...base, date, approx: !ext, what: ext ? `조사 기간 끝(연장 공고 ${ext.date}) — 이 날까지 확정 관세 여부 결정` : `조사 기간 끝(원칙 1년 — 연장하면 최대 ${addMonths(init.date, 18)})`,
            title: `${name}(개시 ${init.date})`, whoNote: sg ? '세이프가드 — 모든 나라산(한국 포함)' : '', note: cNote,
            basis: ext ? '일본 재무성 조사 기간 연장 공고 본문의 날짜' : '관세정률법 — 조사는 원칙 1년 안, 필요하면 6개월까지 연장(개시일은 재무성 공고)', url: (ext ?? init).url });
        }
      }
      if (review && !list.some((e) => /^과세 기간 연장 (결정|안 함)/.test(e.kind ?? '') && e.date >= review.date)) {
        const date = addMonths(review.date, 12);
        if (inWin(date)) {
          out.push({ ...base, date, approx: true, what: '일몰 재심(과세 기간 연장 조사) 결론(원칙 1년)', title: `${name}(재심 개시 ${review.date})`, whoNote: '',
            basis: '관세정률법 — 과세 기간 연장 조사는 원칙 1년 안(개시일은 재무성 공고)', url: review.url });
        }
      }
    }
  }
  // EU — 개시 공고에서 규정으로 계산한 시한(진행 사건만)
  for (const p of docs?.['eu-trade-defence']?.proceedings ?? []) {
    if (!p || p.stage === 'done') continue;
    for (const x of p.deadlines ?? []) {
      if (!inWin(x.date)) continue;
      out.push({ date: x.date, country: 'EU', agency: '집행위', what: `${p.typeKo} ${x.label}`, src: 'eu', beat: Boolean(p.beat), safeguard: ['sg', 'sgr'].includes(p.type),
        title: `${p.product || p.title}(개시 ${p.date}${p.stage === 'provisional' ? ` · ${['sg', 'sgr'].includes(p.type) ? '잠정 조치' : '잠정 관세'} 나옴` : ''})`, who: [],
        whoNote: ['sg', 'sgr'].includes(p.type) ? '세이프가드 — 모든 나라산(한국 포함)' : p.korea ? '제목에 한국' : '', basis: `규정상 시한 — ${x.basis}`, url: p.url });
    }
  }
  return out.sort((a, b) => a.date.localeCompare(b.date) || a.country.localeCompare(b.country));
}

export function aheadLine(a) {
  const who = (a.who ?? []).length ? ` · 출입처 ${a.who.join('·')}${a.whoNote ? `(${a.whoNote})` : ''}` : a.whoNote ? ` · ${a.whoNote}` : '';
  return [`- ${a.approx ? '~' : ''}${a.date} · ${a.country} ${a.agency} · ${a.what} · ${a.title}${who}${a.note ? ` · ${a.note}` : ''}`,
    `   근거: ${a.basis}${a.url ? ` · 원문: ${a.url}` : ''}`];
}

export const AHEAD_NOTE = '   날짜는 누리집 표기이거나 규정상 시한이다 — 발표 예정일이 아니다(보통 더 이르고, 연장 공고로 늦어질 수 있다). '
  + 'EU는 잠정 관세 4주 전 당사자(수출자)에게 계산 내용을 먼저 알린다(반덤핑 기본규정 제19a조) — 그 사이는 회사 확인 구간. 결과는 발표 전 미확인.';

// EU 진행 사건 한눈에(trade_remedies section=ahead) — 단계·다음 시한·개시 공고 일정 문장
export function euProceedingLines(eu, todayIso, q = '', matches = () => true) {
  const procs = (eu?.proceedings ?? []).filter((p) => matches(q, p.title, p.product, p.typeKo));
  if (!eu) return ['\n[EU 진행 사건] 아직 수집 전 — 미확인'];
  const out = [`\n[EU 진행 사건 — 제목에 한국이 든 개시 공고·출입 업종 품목 세이프가드, 최근 470일 · 목록 ${String(eu.historyAt ?? '?').slice(0, 16)}] ${procs.length}건`];
  const sg = (p) => ['sg', 'sgr'].includes(p.type);
  const stageKo = (p) => ({ open: ['ad', 'as'].includes(p.type) ? '진행(잠정 관세 전)' : sg(p) && p.type === 'sg' ? '진행(잠정 조치 전)' : '진행',
    provisional: sg(p) ? '잠정 조치 나옴' : '잠정 관세 나옴', done: '끝남(최근 60일)' })[p.stage] ?? p.stage;
  for (const p of procs) {
    const next = (p.deadlines ?? []).find((x) => x.date >= todayIso);
    out.push(`- ${p.date} 개시 · ${p.typeKo} · ${p.product || p.title}${p.beat ? '' : ' (출입 업종 품목 아님)'}${p.korea ? '' : ' · 제목에 나라 없음(세이프가드)'} · ${stageKo(p)}`
      + `${(p.steps ?? []).length ? ` · 지난 단계 ${p.steps.map((s) => `${s.date} ${s.kind} ${s.number}`).join(' / ')}` : ''}`
      + `${next ? ` · 다음 시한 ${next.date} ${next.label}` : ''}`);
    if ((p.schedule ?? []).length) out.push(`   개시 공고의 일정 문장: ${p.schedule.slice(0, 2).map((t) => `"${String(t).trim()}"`).join(' / ')}`);
    else if (p.scheduleError) out.push(`   개시 공고 본문 못 읽음(${p.scheduleError.error}) — 일정 문장 미확인`);
    out.push(`   원문: ${p.url}`);
  }
  if (!procs.length) out.push('없음(목록을 못 읽었으면 미확인)');
  out.push('   검증 상태: EU 관보 목록 제목으로 묶은 것(자동) — 같은 품목 이름의 뒤 규정을 단계로 붙였다. 시한은 개시일부터 규정으로 계산한 최대치. 대상 업체·세율은 규정 본문');
  return out;
}
