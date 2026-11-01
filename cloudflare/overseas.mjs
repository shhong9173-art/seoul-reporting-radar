// Private watches: overseas sources (regulations.gov comments, page changes, partner filings, trade remedies, US litigation)
// and domestic official sources (factory registry, gazette legislative notices).
// Data arrives through the bearer ingest; tools read it only on the private connector path.
import { ageNote, readFeed } from './screen.mjs';
import { clampInt, textResult, uniqueList } from './common.mjs';

const missing = (what, when) => textResult(`${what} 결과가 아직 없음 — GitHub Secrets의 MCP_ACCESS_TOKEN 설정과 다음 정기 실행(${when})을 확인. 0건이 아니라 미확인.`, true);
const matches = (q, ...fields) => !q || fields.some((f) => String(f ?? '').toLowerCase().includes(q.toLowerCase()));

export async function usComments(ctx, args) {
  const doc = await readFeed(ctx, 'us-comments');
  if (!doc) return missing('미 연방 의견서', '평일 08:20');
  if (doc.broken) return textResult('저장된 의견서 결과 형식 오류 — 미확인.', true);
  const q = String(args.company ?? '').trim();
  const onlyNew = args.only_new === true || args.only_new === 'true';
  const limit = clampInt(args.limit, 1, 60, 20);
  const failed = (doc.checks ?? []).filter((c) => c.status !== 'ok');
  const rows = (doc.items ?? []).filter((x) => matches(q, x.company, x.submitter, x.docketTitle) && (!onlyNew || x.isNew));
  const out = [`미 연방 규제 의견서(regulations.gov) · 최근 ${doc.lookbackDays}일 · 출입처 명의 ${rows.length}건 · 수집 ${String(doc.generatedAt).slice(0, 16)}${ageNote(ctx, doc.generatedAt)}`,
    `질의 ${(doc.checks ?? []).length - failed.length}/${(doc.checks ?? []).length} 정상${failed.length ? ` · 미확인(0건 아님): ${failed.map((c) => `${c.company}(${c.error ?? c.status})`).join(', ')}` : ''} · 키 ${doc.keyType}`,
    ...(doc.rules ?? []).map((r) => `규칙: ${r}`)];
  for (const x of rows.slice(0, limit)) {
    out.push(`\n${x.isNew ? '[신규] ' : ''}${x.postedDate} · ${x.company} · ${x.submitter} → ${x.agency}`);
    out.push(`   잡힌 사실: ${x.docketTitle ? `도켓 「${x.docketTitle}」(${x.docketId})에 의견서 제출` : `도켓 ${x.docketId}에 의견서 제출(도켓 제목 미조회)`}`);
    if (x.excerpt) out.push(`   본문 첫머리: ${x.excerpt.slice(0, 200)}`);
    out.push(`   원문: ${x.url}${(x.attachments ?? []).length ? ` · 첨부 ${x.attachments.join(' ')}` : ' · 첨부 미조회'}`);
    out.push('   검증 상태: 목록·제목 확인. 첨부 본문의 요청 내용·수치는 원문 열어 확인 필요');
  }
  if (rows.length > limit) out.push(`… 남은 ${rows.length - limit}건`);
  if (!rows.length) out.push('\n조건에 맞는 의견서 없음(위 미확인 질의는 0건 아님).');
  out.push('\n다음: 첨부 PDF는 source_document(downloads.regulations.gov)로 연다 → 같은 도켓의 규정안·마감일 확인 → news_check로 보도 대조.');
  return textResult(out.join('\n'));
}

const CAT_KO = { timing: '출시 시점', limited: '한정 물량', price: '가격', status: '판매 상태', models: '연식·차명' };

export async function pageChanges(ctx, args) {
  const doc = await readFeed(ctx, 'page-watch');
  if (!doc) return missing('해외 공식 페이지 변경', '평일 06:30·18:30');
  if (doc.broken) return textResult('저장된 페이지 감시 결과 형식 오류 — 미확인.', true);
  const days = clampInt(args.days, 1, 90, 14);
  const q = String(args.company ?? '').trim();
  const from = new Date(ctx.now.getTime() - days * 86400000).toISOString();
  const events = (doc.events ?? []).filter((e) => new Date(e.detectedAt).toISOString() >= from && matches(q, e.company, e.label, e.url));
  const pages = (doc.pages ?? []).filter((p) => matches(q, p.company, p.label, p.url));
  const failed = pages.filter((p) => p.status === 'failed');
  const moved = pages.filter((p) => p.status === 'redirected');
  const out = [`해외 공식 페이지 변경 · 최근 ${days}일 ${events.length}건 · 페이지 ${pages.length - failed.length}/${pages.length} 열림 · 확인 ${String(doc.generatedAt).slice(0, 16)}${ageNote(ctx, doc.generatedAt)}`];
  if (failed.length) out.push(`미확인(변화 없음 아님): ${failed.map((p) => `${p.label}(${p.error})`).join(', ')}`);
  if (moved.length) out.push(`다른 주소로 넘어가는 페이지(문구 비교 안 함 — 제 페이지로 열리면 '페이지 열림'): ${moved.map((p) => `${p.label} → ${p.finalUrl}`).join(', ')}`);
  out.push(...(doc.rules ?? []).map((r) => `규칙: ${r}`));
  for (const e of events.slice(0, clampInt(args.limit, 1, 40, 15))) {
    out.push(`\n${String(e.detectedAt).slice(0, 16)} · ${e.label}${e.scope === 'site' ? ' [사이트 공통]' : ''}`);
    if (!e.scope) out.push('   주의: 사이트 공통 메뉴 문구를 걸러내기 전 기록 — 메뉴·배너 문구 변화일 수 있음');
    out.push(`   비교 기준: ${e.baselineSource}${e.baselineDate ? ` ${e.baselineDate}` : ''} → ${String(e.detectedAt).slice(0, 10)}`);
    if (e.kind === 'moved') out.push(`   페이지 넘어감: 이 주소가 ${e.movedTo}(으)로 넘어간다 — 차종 페이지 내림·판매 중단·개편 가능성(회사 확인)`);
    if (e.kind === 'opened') out.push(`   페이지 열림: 전에는 ${e.openedFrom}(으)로 넘어가던 주소가 제 페이지로 열렸다 — 출시 준비 신호일 수 있음(회사 확인)`);
    if (e.redirectNote) out.push(`   주의: ${e.redirectNote}`);
    // 가격 줄은 페이지에서 그 앞에 있던 차명을 붙인다(배치로 추정 — '근처 차명')
    const near = (cat, x) => (cat === 'price' && e.priceModels?.[String(x).toLowerCase()] ? `${x}(근처 차명 ${e.priceModels[String(x).toLowerCase()]})` : x);
    for (const [cat, list] of Object.entries(e.removed ?? {})) out.push(`   − ${CAT_KO[cat] ?? cat}: ${list.slice(0, 6).map((x) => near(cat, x)).join(' / ')}`);
    for (const [cat, list] of Object.entries(e.added ?? {})) out.push(`   + ${CAT_KO[cat] ?? cat}: ${list.slice(0, 6).map((x) => near(cat, x)).join(' / ')}`);
    out.push(`   원문: ${e.url}`);
    out.push('   검증 상태: 페이지 문구 비교(자동). 공식 발표·변경 사유는 미확인 — 회사 확인과 과거 발표(보도자료·모터쇼) 대조 필요');
  }
  if (!events.length) out.push('\n이 기간 잡힌 문구 변화 없음(열리지 않은 페이지는 미확인).');
  if (args.show_current === true || args.show_current === 'true') {
    out.push('\n현재 문구:');
    for (const [dom, site] of Object.entries(doc.sites ?? {})) {
      const sig = site.signals ?? {};
      const line = ['timing', 'limited', 'price', 'status'].map((k) => (sig[k] ?? []).slice(0, 3).join(' / ')).filter(Boolean).join(' · ');
      if (line && matches(q, site.company, dom)) out.push(`- [${dom} 공통 메뉴·배너] ${line}`);
    }
    for (const p of pages.filter((x) => x.status === 'ok')) {  // 넘어가는 페이지는 문구가 없다
      const sig = p.signals ?? {};
      out.push(`- ${p.label}: ${['timing', 'limited', 'price', 'status'].map((k) => (sig[k] ?? []).slice(0, 3).join(' / ')).filter(Boolean).join(' · ') || '신호 문구 없음'}`);
    }
  }
  return textResult(out.join('\n'));
}

const AWARD_DAYS = 120;

// Overseas public-buyer award notices (overseas-awards feed), shown under partner_filings so no new connector tool is needed.
async function awardSection(ctx, q, onlyNew, limit) {
  const doc = await readFeed(ctx, 'overseas-awards');
  if (!doc) return ['\n[해외 발주처 낙찰] 결과 없음 — 미확인(평일 06:50·17:30 실행 확인)'];
  if (doc.broken) return ['\n[해외 발주처 낙찰] 저장 형식 오류 — 미확인'];
  const by = {};
  for (const c of doc.checks ?? []) {
    const b = (by[c.source] ??= { ok: 0, all: 0, failed: [] });
    b.all += 1;
    if (c.status === 'failed') b.failed.push(`${c.query}(${c.error ?? '실패'})`); else b.ok += 1;
    if (c.note && /미확인/.test(c.note)) b.failed.push(`${c.query}(${c.note})`);
    else if (c.note && c.source === '바레인 입찰위원회 개찰') b.scope = c.note;  // 읽은 개찰 범위(0건이 어디까지인지)
  }
  const from = new Date(ctx.now.getTime() - AWARD_DAYS * 86400000).toISOString().slice(0, 10);
  const all = (doc.items ?? []).filter((x) => String(x.published ?? x.firstSeen).slice(0, 10) >= from && (!onlyNew || x.isNew)
    && matches(q, x.company, (x.winners ?? []).join(' '), x.bidder, x.buyer, x.title, x.buyerCountry));
  const rank = { A: 0, B: 1, C: 2 };
  const rows = all.filter((x) => q || x.tier !== 'C').sort((a, b) => (rank[a.tier] ?? 3) - (rank[b.tier] ?? 3)
    || String(b.published ?? '').localeCompare(String(a.published ?? '')));
  const others = all.length - rows.length;
  const out = [`\n[해외 발주처 낙찰 · ${doc.coverage ?? 'EU TED·영국 FTS·세계은행·바레인'} · 공고 최근 ${AWARD_DAYS}일] 출입처 ${rows.length}건${others ? ` · 출입처 밖 한국 기업 ${others}건(company 낱말로 보기)` : ''} · 확인 ${String(doc.generatedAt).slice(0, 16)}${ageNote(ctx, doc.generatedAt)}`,
    `원천: ${Object.entries(by).map(([k, b]) => `${k} ${b.ok}/${b.all} 정상${b.failed.length ? `(미확인: ${b.failed.slice(0, 3).join(', ')})` : ''}`).join(' · ')}`,
    ...Object.entries(by).filter(([, b]) => b.scope).map(([k, b]) => `범위: ${k} — ${b.scope}`),
    ...(doc.rules ?? []).map((r) => `규칙: ${r}`)];
  for (const x of rows.slice(0, limit)) {
    const value = x.value ? `${x.currency ?? ''} ${Number(x.value).toLocaleString('en-US', { maximumFractionDigits: 0 })}` : '금액 미기재';
    const ids = (x.winnerIds ?? []).length ? `, 식별번호 ${x.winnerIds.join('·')}` : '';
    out.push(`\n${x.isNew ? '[신규] ' : ''}${x.published ?? '공고일 미기재'} · ${x.source} ${x.kind} · ${x.company ?? '출입처 밖 한국 기업'} · 발주 ${x.buyer}${x.buyerCountry ? `(${x.buyerCountry})` : ''}`);
    if (x.bidder) {  // 바레인 개찰: 응찰 회사·응찰가 공개(낙찰 아님)
      const money = (v) => `${x.currency ?? ''} ${Number(v).toLocaleString('en-US', { maximumFractionDigits: 3 })}`;
      const rank = x.rank ? `응찰가 ${x.rank}위/${x.priced}곳${x.lowest ? '(최저가)' : ''}` : '응찰가 순위 없음(가격 미공개 단계이거나 탈락)';
      const others = (x.others ?? []).map((o) => `${o.name} ${money(o.value)}`).join(' / ');
      out.push(`   잡힌 사실: 응찰 ${x.bidder} ${x.value ? money(x.value) : '응찰가 미공개'}${x.options > 1 ? `(옵션 ${x.options}개 중 낮은 값)` : ''} · 상태 ${x.bidStatus || '미기재'} · ${rank} · 응찰 ${x.bidCount ?? '?'}곳${others ? ` · 다른 응찰 ${others}` : ''} · ${x.title}`);
      out.push(`   원문: ${x.url ?? '링크 없음'}`);
      out.push('   검증 상태: 입찰위원회 개찰 결과(응찰가 공개) — 낙찰 아님. 최저가도 기술 평가·협상으로 바뀔 수 있다. 낙찰 여부는 입찰위원회 결정·월간 낙찰 보고서·회사로, 보도 여부는 news_check로 확인');
      continue;
    }
    const more = (x.winnerCount ?? (x.winners ?? []).length) - Math.min(2, (x.winners ?? []).length);
    const who = (x.winners ?? []).slice(0, 2).join(' / ') + (more > 0 ? ` 외 ${more}곳` : '');
    out.push(`   잡힌 사실: 낙찰자 ${who || '보고서 줄 참조'}${(x.winnerCountry ?? []).length ? `(${more > 0 ? '낙찰자 전체 국가 ' : ''}${x.winnerCountry.join('·')}${ids})` : ''} · ${x.title} · ${value}${x.priceKind ? `(${x.priceKind})` : ''}${x.concluded ? ` · 계약 ${x.concluded}` : ''}${x.report ? ` · ${x.report}` : ''}`);
    out.push(`   원문: ${x.url ?? '링크 없음'}${x.official ? ` · 정부전자조달망 ${x.official}` : ''}`);
    out.push(`   검증 상태: 공고의 낙찰자 칸${x.source === '바레인 입찰위원회' ? '(월간 보고서 줄 — 발주처·금액은 PDF 원문 확인)' : x.official ? '(대만 PCC 공고의 得標廠商 — g0v 공개 미러로 찾음, 금액 NT$)' : ''}. 계약 범위·금액·출입처 공시·보도 여부는 원문과 news_check로 확인`);
  }
  if (rows.length > limit) out.push(`… 남은 ${rows.length - limit}건`);
  if (!rows.length) out.push('조건에 맞는 출입처 낙찰 없음(위 미확인 원천은 0건 아님).');
  return out;
}

// UK Companies House new incorporations (overseas-registry feed), shown under partner_filings.
async function registrySection(ctx, q, onlyNew, limit) {
  const doc = await readFeed(ctx, 'overseas-registry');
  if (!doc) return ['\n[해외 법인 등기(영국)] 결과 없음 — 미확인(평일 06:00 실행 확인)'];
  if (doc.broken) return ['\n[해외 법인 등기(영국)] 저장 형식 오류 — 미확인'];
  const checks = doc.checks ?? [];
  const bad = checks.filter((c) => c.status !== 'ok');
  const all = (doc.companies ?? []).filter((x) => (!onlyNew || x.isNew) && matches(q, x.company, x.name, (x.psc ?? []).join(' '), x.address));
  const rows = all.filter((x) => q || x.tier !== 'C');
  const nA = all.filter((x) => x.tier === 'A').length;
  const nB = all.filter((x) => x.tier === 'B').length;
  const nC = all.length - nA - nB;
  const out = [`\n[해외 법인 등기 · 영국 Companies House · 보관 ${(doc.companies ?? []).length}곳(첫 실행은 1년 전 설립부터, 이번 조회는 설립 ${doc.windowStart ?? '?'} 이후)] 출입처 지배 주주 ${nA}건 · 지배 주주 미기재·본사 이름 ${nB}건 · 이름만 같은 법인 ${nC}건${q ? ` · 낱말 '${q}'로 ${rows.length}건 표시` : nC ? '(company 낱말로 보기)' : ''} · 확인 ${String(doc.generatedAt).slice(0, 16)}${ageNote(ctx, doc.generatedAt)}`,
    `원천: 질의 ${checks.length - bad.length}/${checks.length} 정상${bad.length ? `(미확인: ${bad.slice(0, 3).map((c) => `${c.source}(${c.error ?? c.status})`).join(', ')})` : ''}`,
    ...(doc.rules ?? []).map((r) => `규칙: ${r}`)];
  for (const x of rows.slice(0, limit)) {
    out.push(`- ${x.isNew ? '[신규] ' : ''}${x.created ?? '?'} 설립 · ${x.company} · ${x.name} (${x.number}, ${x.status ?? '상태 미상'})${x.note ? ` — ${x.note}` : ''}`);
    out.push(`   잡힌 사실: 지배 주주 ${(x.psc ?? []).join(', ') || '미기재'} · SIC ${(x.sic ?? []).join(',') || '미기재'} · 등기 주소 ${x.address || '미기재'}`);
    out.push(`   원문: ${x.url}`);
  }
  if (rows.length > limit) out.push(`… 남은 ${rows.length - limit}건`);
  if (!rows.length) out.push('출입처가 지배 주주인 새 법인 없음(위 미설정·실패는 0건 아님).');
  else if (!nA) out.push('(지배 주주가 출입처 본사로 확인된 법인은 없음 — 위 줄은 이름만 같거나 지배 주주 미기재)');
  return out;
}

export async function partnerFilings(ctx, args) {
  const q = String(args.company ?? '').trim();
  const onlyNewArg = args.only_new === true || args.only_new === 'true';
  const limitArg = clampInt(args.limit, 1, 60, 20);
  const src = ['ASX', 'HKEX', 'EDGAR'].includes(args.source) ? args.source : null;
  const awards = src ? [] : [...await awardSection(ctx, q, onlyNewArg, limitArg), ...await registrySection(ctx, q, onlyNewArg, limitArg)];
  const doc = await readFeed(ctx, 'partner-filings');
  if (!doc) return awards.length ? textResult([missing('해외 파트너 공시', '평일 07:00').content[0].text, ...awards].join('\n')) : missing('해외 파트너 공시', '평일 07:00');
  if (doc.broken) return textResult(['저장된 파트너 공시 결과 형식 오류 — 미확인.', ...awards].join('\n'), true);
  const onlyNew = onlyNewArg;
  // Routine ASX notices (AGM, director interests) are hidden unless asked for.
  const onlyFlagged = !(args.include_routine === true || args.include_routine === 'true');
  const limit = clampInt(args.limit, 1, 60, 20);
  const failed = (doc.checks ?? []).filter((c) => c.status !== 'ok');
  const base = (doc.items ?? []).filter((x) => (!src || x.source === src) && (!onlyNew || x.isNew)
    && matches(q, x.filer, x.title, (x.beat ?? []).join(' '), x.snippet));
  const rows = base.filter((x) => !onlyFlagged || (!x.routine && (x.source === 'ASX' || x.source === 'HKEX' ? (x.flags ?? []).length : true)));
  const hiddenRoutine = base.length - rows.length;
  const out = [`해외 파트너 공시 · 최근 ${doc.windowDays}일 수집(보관 120일) · ${rows.length}건 · 확인 ${String(doc.generatedAt).slice(0, 16)}${ageNote(ctx, doc.generatedAt)}`,
    `질의 ${(doc.checks ?? []).length - failed.length}/${(doc.checks ?? []).length} 정상${failed.length ? ` · 미확인(0건 아님): ${failed.slice(0, 6).map((c) => `${c.target}(${c.error})`).join(', ')}` : ''}`,
    ...(doc.rules ?? []).map((r) => `규칙: ${r}`)];
  for (const x of rows.slice(0, limit)) {
    out.push(`\n${x.isNew ? '[신규] ' : ''}${x.date}${x.time ? ` ${x.time}(홍콩시각)` : ''} · ${x.source} · ${x.filer} · 관련 출입처 ${(x.beat ?? []).join('·')}`);
    out.push(`   잡힌 사실: ${x.title}${x.priceSensitive ? ' (주가 민감 공시)' : ''}${(x.flags ?? []).length ? ` · 낱말 ${x.flags.join(',')}` : ''}`);
    if (x.relation) out.push(`   관계: ${x.relation} (근거 ${x.relationEvidence})`);
    if (x.routine || x.finNote || x.hearsay || x.boilerplate) out.push(`   분류: ${x.routine ?? x.hearsay ?? x.boilerplate ?? x.finNote}`);
    if (x.snippet) out.push(`   본문 발췌: …${x.snippet.slice(0, 400)}…`);
    else if (x.snippetError) out.push(`   본문 발췌 실패: ${x.snippetError}`);
    out.push(`   원문: ${x.url ?? '링크 없음'}`);
    out.push('   검증 상태: 파트너 측 공시 제목·발췌. 출입처와의 계약 변경 여부는 원문 전체와 출입처 확인 필요');
  }
  if (rows.length > limit) out.push(`… 남은 ${rows.length - limit}건`);
  if (!rows.length) out.push('\n조건에 맞는 공시 없음(위 미확인 질의는 0건 아님).');
  if (hiddenRoutine) out.push(`(일상 공시 ${hiddenRoutine}건 숨김 — ASX 주총·임원 지분, HKEX 월간 증권 변동·이사회 일정·정기보고서, EDGAR 투자 보유 표·반복 문구: include_routine=true)`);
  out.push(...awards);
  out.push('\n다음: EDGAR 원문은 source_document(sec.gov)로, ASX·HKEX 공시 PDF는 브라우저로 연다 → 출입처 이름·지분·물량·가격·조건 문구 확인 → news_check.'
    + (awards.length ? ' 해외 낙찰은 공고 원문(TED·FTS·세계은행)에서 낙찰자·금액·계약일 확인 → 출입처 DART 단일판매·공급계약 공시 여부(dart_find_text) → news_check.' : ''));
  return textResult(out.join('\n'));
}

const fmtT = (v) => (v == null ? '?' : `${Number(v).toLocaleString('en-US', { maximumFractionDigits: 1 })}t`);

function quotaLine(q) {
  if (q.status !== 'ok') return `${q.order} · 조회 실패(${q.error ?? '미확인'}) — 0이 아니라 미확인`;
  const last = q.lastQuarter ? ` · 직전 분기 ${q.lastQuarter.exhaustedOn ? `소진 ${q.lastQuarter.exhaustedOn}(${q.lastQuarter.daysToExhaust + 1}일째)` : `사용 ${q.lastQuarter.usedPct}%`}` : '';
  return `${q.order} ${q.product ?? '품목 미분류'} · ${q.scope} · 초기 ${fmtT(q.initialT)} · 잔량 ${fmtT(q.balanceT)} · 사용 ${q.usedPct}%${(q.tags ?? []).length ? ` ${q.tags.join(' ')}` : ''}${last}${q.stale ? ' · ⚠ 이번 조회 실패, 직전 값' : ''}`;
}

// 국내 무역위원회(ktc_watch.py): 회의 약 1주 전에 올라오는 개요 PDF의 안건, 2019년 이후 개시한 진행 사건과 마지막 진행일정,
// 진행 목록에서 빠진 사건. 진행 목록에는 2000년대 옛 불공정무역행위 사건도 '조사실행'으로 남아 있어(10-30 44건 중 20건) 숨긴다.
// 미국 관보 판정의 출입처 세율(관보 원문 표)과 같은 사건 직전 판정 세율(trade_remedy_watch.rate_table·prior_rates).
// 11-01 역추적: 10-08 도금강판 반덤핑 예비 KG스틸 23.40%·동국씨엠 19.43%(직전 최종 0.00%)를 레이더가 79.5시간 먼저 잡았지만 세율이 없었다.
const pct = (v) => `${Number(v).toFixed(2)}%`;
export function rateText(x) {
  const t = x.rateTable;
  if (!t) return '';
  const fin = x.prior?.final;
  const pre = x.prior?.prelim && (!fin || String(x.prior.prelim.date) > String(fin.date)) ? x.prior.prelim : null;
  const before = (p, c, v) => p?.rates?.[c] ?? (v.via === '비선정' ? p?.othersRate : undefined);
  const entries = Object.entries(t.rates ?? {});
  if (!entries.length) {
    return t.rows ? ` · 세율 표에 출입처 줄 없음${t.othersRate != null ? `(비선정 업체 ${pct(t.othersRate)})` : ''}` : ' · 세율 표 못 읽음(원문 표 확인)';
  }
  const parts = entries.map(([c, v]) => {
    const prior = [fin && before(fin, c, v) != null ? `직전 최종 ${pct(before(fin, c, v))}` : fin ? '직전 최종에 없음' : '',
      pre && before(pre, c, v) != null ? `예비 ${pct(before(pre, c, v))}` : ''].filter(Boolean).join('·');
    return `${c} ${pct(v.rate)}${v.via === '비선정' ? '(비선정 업체 세율)' : ''}${prior ? `(${prior})` : ''}`;
  });
  const when = fin ? ` [직전 최종 ${fin.date}${pre ? `·예비 ${pre.date}` : ''}]` : pre ? ` [직전 예비 ${pre.date}]`
    : x.prior?.none ? ' [같은 사건 직전 판정 세율 못 찾음]' : x.priorError ? ` [직전 판정 조회 실패(${x.priorError}) — 미확인]` : '';
  return ` · ${t.kind} 세율(관보 표): ${parts.join(' · ')}${t.othersRate != null && !entries.some(([, v]) => v.via === '비선정') ? ` · 비선정 업체 ${pct(t.othersRate)}` : ''}${when}`;
}

// 미국 ITC 피해 판정(trade_remedy_watch.itc_outcome): 한국산에 대한 결과를 한국어로.
const ITC_LABEL = {
  '일몰 재심': { 긍정: '관세 유지(철폐하면 피해 재발 — 5년 더)', 부정: '관세 철폐(피해 재발 가능성 없음)' },
  예비: { 긍정: '피해 가능성 있음 — 조사 계속(상무부 판정으로)', 부정: '피해 가능성 없음 — 한국산 조사 종결' },
  최종: { 긍정: '피해 있음 — 관세 부과 확정', 부정: '피해 없음 — 관세 부과 안 함' },
};
export function itcText(o) {
  if (!o?.korea) return '';
  const label = o.korea === '섞임' ? '한국 관련 결과가 둘 이상(긍정·부정) — 원문 확인' : ITC_LABEL[o.phase]?.[o.korea] ?? o.korea;
  return `한국산 ${label}${(o.dissent ?? []).length ? ` · 반대 의견: "${String(o.dissent[0]).slice(0, 120)}"` : ''}`;
}
export const productOf = (title) => String(title ?? '').split(/\s+From\s+/i)[0].replace(/^Certain\s+/i, '').trim().toLowerCase();

export function rateChangeText(x) {
  const ch = x.rateChange ?? [];
  if (!ch.length) return '';
  return ch.slice(0, 5).map((c) => (c.before == null ? `${c.company} 새 조사에서 ${pct(c.rate)}` : `${c.company} ${pct(c.before)}→${pct(c.rate)}`)).join(', ');
}

export function ktcSection(k, q = '', limit = 15) {
  if (!k) return ['\n[국내 무역위원회] 아직 수집 전 — 미확인'];
  const out = [];
  const lastStep = (c) => (c.timeline ?? []).at(-1) ?? null;
  const live = (k.cases ?? []).filter((c) => !c.stale);
  const cases = (k.cases ?? []).filter((c) => matches(q, c.title, c.product, c.no, c.country, c.kind));
  const active = cases.filter((c) => String(c.opened ?? '') >= '2019-01-01');
  out.push(`\n[국내 무역위원회 · 확인 ${String(k.checkedAt).slice(0, 16)}${k.stale ? ' · ⚠ 이번 조회 실패, 직전 목록' : ''}] 진행 목록 ${live.length}건`
    + ` · 2019년 이후 개시 ${active.length}건(출입 업종 품목 ${active.filter((c) => c.beat).length})${k.listComplete === false ? ' · 목록 일부만 읽음' : ''}`);
  for (const m of (k.meetings ?? []).filter((m) => !q || matches(q, m.title, (m.agenda ?? []).map((a) => a.text).join(' '))).slice(0, 2)) {
    out.push(`- 회의: ${m.title}${m.meetingOn ? ` · 개최 ${m.meetingOn}` : ''}${m.posted ? ` · 게시 ${m.posted}` : ''}${m.summary ? ` · 안건 ${m.summary}` : ''}`);
    if (m.agenda) for (const a of m.agenda.slice(0, 8)) out.push(`   ${a.kind}${a.beat ? '(출입 업종 품목)' : ''}: ${a.text}`);
    else out.push(`   안건 미확인(${m.agendaError ?? '읽지 않음'}) — 0건 아님`);
    out.push(`   원문: ${m.url}`);
  }
  const key = (c) => String(lastStep(c)?.[1] ?? c.opened ?? '');
  const sorted = [...active].sort((a, b) => Number(Boolean(b.beat)) - Number(Boolean(a.beat)) || key(b).localeCompare(key(a)));
  for (const c of sorted.slice(0, limit)) {
    const ls = lastStep(c);
    out.push(`- ${c.no} · ${c.title} · ${c.country || '대상국 미기재'} · ${c.kind ?? '유형 미상'}${c.review ? `/${c.review}` : ''} · 개시 ${c.opened ?? '?'}`
      + `${ls ? ` · 최근 ${ls[0]} ${ls[1]}` : ''}${(c.pending ?? []).length ? ` · 남은 단계 ${c.pending.join('·')}` : ''}${c.beat ? ' · 출입 업종 품목' : ''}`
      + `${c.detailError ? ` · ${c.detailError}` : ''}${c.stale ? ' · 이번 목록에서 확인 못 함' : ''}`);
    out.push(`   원문: ${c.url}`);
  }
  if (sorted.length > limit) out.push(`… 남은 ${sorted.length - limit}건`);
  const old = cases.length - active.length;
  if (old) out.push(`(2019년 전 개시 ${old}건은 목록에 '조사실행'으로 남은 옛 사건 — 숨김)`);
  for (const x of (k.left ?? []).filter((x) => matches(q, x.title, x.product)).slice(0, 5)) {
    out.push(`- 진행 목록에서 빠짐 ${String(x.leftAt).slice(0, 10)}: ${x.no} ${x.title}${x.result ? ` · 판정결과 ${x.result}` : ''}`);
  }
  const news = (k.news ?? []).filter((n) => matches(q, n.title)).slice(0, 5);
  if (news.length) out.push(`- 최근 보도자료: ${news.map((n) => `${n.title}${n.posted ? `(${n.posted})` : ''}`).join(' / ')}`);
  out.push('   검증 상태: 무역위 누리집 목록·상세·회의 개요 PDF(자동). 신청인(국내 생산자)·피신청인 이름은 누리집에 대개 없어 회사 확인 필요. '
    + '회의 안건은 결과가 아니다 — 판정·세율은 회의 뒤 보도자료·의결서로 확인');
  return out;
}

// 무역협회 대한 수입규제DB(kita_watch.py): 세계 각국의 한국산 조치를 한 곳에 — 새 사건·진행 단계(업체 마진)를 감지 이벤트로, 최근 갱신 사건을 목록으로.
export function kitaSection(ki, events, q = '', limit = 15, fromIso = '') {
  if (!ki) return ['\n[대한 수입규제 · 무역협회 수입규제DB] 아직 수집 전 — 미확인'];
  const out = [];
  const ev = (events ?? []).filter((e) => e.pageId === 'kita' && String(e.detectedAt) >= fromIso && matches(q, e.label, e.text, e.country, (e.companies ?? []).join(' ')));
  const rank = { A: 0, B: 1, C: 2 };
  out.push(`\n[대한 수입규제 · 무역협회 수입규제DB · 확인 ${String(ki.checkedAt).slice(0, 16)}${ki.stale ? ' · ⚠ 이번 조회 실패, 직전 목록' : ''}] 아는 사건 ${Object.keys(ki.cases ?? {}).length}건 · 감지 ${ev.length}건(기준선 ${String(ki.baselineSince ?? '').slice(0, 10)} 이후)`);
  for (const e of [...ev].sort((a, b) => (rank[a.tier] ?? 3) - (rank[b.tier] ?? 3) || String(b.detectedAt).localeCompare(String(a.detectedAt))).slice(0, limit)) {
    out.push(`- ${e.tier} · ${String(e.detectedAt).slice(0, 10)} · ${e.kitaKind} · ${e.text}`);
    out.push(`   원문: ${e.url}`);
  }
  const recent = (ki.recent ?? []).map((id) => ({ id, ...(ki.cases ?? {})[id] })).filter((c) => matches(q, c.country, c.item, c.type, c.category));
  out.push(`- 최근 갱신 사건(갱신순) ${Math.min(recent.length, limit)}/${recent.length}:`);
  for (const c of recent.slice(0, limit)) {
    out.push(`  ${c.updated ?? '?'} · ${c.country} ${c.type} · ${c.item} · ${c.status}${c.category ? ` · ${c.category}` : ''}${c.latestStage ? ` · 최신 ${String(c.latestStage).replace('|', ' ')}` : ''}`);
  }
  out.push('   검증 상태: 무역협회가 각국 조치를 정리한 2차 자료(자동). 마진·판정·대상 업체는 단계마다 붙은 원문(관보·WTO 통보 등)으로 확인. 미국 사건은 관보 감시가 먼저 잡는다');
  return out;
}

// 미국 ITC 문서 시스템 EDIS(edis_watch.py): 한국산 제소·출입처가 당사자인 서면·출입처 이름이 표지에 든 337 제소장·지켜보는 337 조사의 결정.
// 운영 근거: 337-TA-1494 종결 예비 결정에 한화솔루션·한화큐셀 등이 재검토를 청원(10-07·10-21) — 10-Q·국내 보도엔 없던 사실.
export function edisSection(ed, q = '', limit = 15, showAll = false, fromIso = '') {
  if (!ed) return ['\n[미국 ITC 문서(EDIS)] 아직 수집 전 — 미확인'];
  const rank = { A: 0, B: 1, C: 2 };
  const all = (ed.docs ?? []).filter((x) => String(x.firstSeen ?? '') >= fromIso || !fromIso)
    .filter((x) => matches(q, x.investigationNumber, x.investigationTitle, x.documentTitle, x.onBehalfOf, (x.companies ?? []).join(' ')));
  const shown = showAll ? all : all.filter((x) => x.tier !== 'C');
  const sorted = [...shown].sort((a, b) => (rank[a.tier] ?? 3) - (rank[b.tier] ?? 3) || String(b.officialReceivedDate).localeCompare(String(a.officialReceivedDate)));
  const watched = Object.keys(ed.watched ?? {});
  const out = [`\n[미국 ITC 문서(EDIS) · 확인 ${String(ed.checkedAt).slice(0, 16)}${ed.stale ? ' · ⚠ 이번 조회 실패, 직전 상태' : ''} · 기준선 ${String(ed.baselineSince ?? '').slice(0, 10)}] `
    + `A·B ${all.filter((x) => x.tier !== 'C').length}건${showAll ? '' : ` · 일상 C ${all.length - shown.length}건 숨김(show_all=true)`} · 지켜보는 337 조사 ${watched.join(', ') || '없음'}`];
  if (ed.tokenNote) out.push(`⚠ ${ed.tokenNote}`);
  for (const x of sorted.slice(0, limit)) {
    // 공동 피제소인 20여 곳을 한 줄에 적은 서면은 출입처가 뒤에서 잘린다(운영 10-31) — 출입처로 잡힌 법인 이름을 따로
    const long = String(x.onBehalfOf ?? '').length > 200;
    const party = !x.onBehalfOf || String(x.firmOrganization).toUpperCase() === 'USITC' ? ''
      : (x.partyHits ?? []).length && long ? ` (공동 당사자 ${String(x.onBehalfOf).length}자 중 출입처: ${x.partyHits.join('; ')})` : ` (당사자 ${String(x.onBehalfOf).slice(0, 240)})`;
    out.push(`- ${x.tier}${x.isNew ? ' [신규]' : ''} · 접수 ${String(x.officialReceivedDate).slice(0, 16)} · ${x.investigationNumber} ${x.documentType} · ${x.documentTitle}`);
    out.push(`   제출 ${x.firmOrganization || x.filedBy}${party} · ${x.why}${(x.companies ?? []).length ? ` · 출입처 ${x.companies.join('·')}` : ''}`);
    out.push(`   사건: ${x.investigationTitle} (${x.investigationPhase}·${x.investigationStatus})`);
    if ((x.snippets ?? []).length) out.push(`   본문(${x.pages}쪽, 공개본 첫 첨부) 발췌: ${x.snippets.map((t) => `"${t}"`).join(' / ')}`);
    else if (x.bodyError) out.push(`   본문 미확인(${x.bodyError})`);
    else if (String(x.securityLevel).toLowerCase() !== 'public') out.push('   비공개 문서 — 본문 없음(공개본은 뒤에 따로 올라온다)');
    out.push(`   원문: ${x.url} (EDIS 문서 번호 ${x.id})`);
  }
  if (sorted.length > limit) out.push(`… 남은 ${sorted.length - limit}건`);
  if (!sorted.length) out.push('이 기간 새로 본 관련 문서 없음(조회 실패·토큰 문제는 위 원천 상태 — 미확인).');
  out.push('   검증 상태: EDIS 문서 목록(자동)·공개본 첫 첨부 발췌(자동, API 토큰). 제소장·청원·서면은 당사자 주장 — 결론은 위원회·판사 문서로. '
    + '출입처 이름이 나와도 피제소인·제3자·고객 중 무엇인지 원문 확인. 로펌 하나가 여러 피제소인을 대리하면 회사별 입장은 원문에서');
  return out;
}

export async function tradeRemedies(ctx, args) {
  const doc = await readFeed(ctx, 'trade-remedy');
  if (!doc) return missing('무역구제 감시(해외·국내 무역위원회)', '평일 07:40');
  if (doc.broken) return textResult('저장된 무역구제 결과 형식 오류 — 미확인.', true);
  const section = ['quota', 'us', 'notices', 'ktc', 'kita', 'edis'].includes(args.section) ? args.section : null;
  const q = String(args.company ?? '').trim();
  const days = clampInt(args.days, 1, 120, 30);
  const limit = clampInt(args.limit, 1, 60, 15);
  const onlyNew = args.only_new === true || args.only_new === 'true';
  const showAll = args.show_all === true || args.show_all === 'true';
  const checks = doc.checks ?? [];
  const out = [`무역구제 감시(해외·국내 무역위원회) · 확인 ${String(doc.generatedAt).slice(0, 16)}${ageNote(ctx, doc.generatedAt)}`,
    `원천: ${checks.map((c) => `${c.source} ${c.status}(${c.returned ?? 0}${c.error ? `, ${c.error}` : ''})`).join(' · ')}`,
    ...(doc.rules ?? []).map((r) => `규칙: ${r}`)];

  if (!section || section === 'quota') {
    const all = (doc.quotas ?? []).filter((x) => matches(q, x.order, x.product, x.scope, (x.cn ?? []).join(' ')));
    const rank = (x) => (x.status !== 'ok' ? 2 : (x.tags ?? []).length ? 0 : 1);
    const sorted = [...all].sort((a, b) => rank(a) - rank(b) || (a.scope === '한국 전용' ? -1 : 0) - (b.scope === '한국 전용' ? -1 : 0)
      || String(a.exhaustedOn ?? '9').localeCompare(String(b.exhaustedOn ?? '9')));
    const shown = showAll ? sorted : sorted.filter((x) => rank(x) !== 1);
    const kr = all.filter((x) => x.scope === '한국 전용').length;
    out.push(`\n[EU 철강 쿼터 · ${doc.quarter} 분기] ${all.length}개(한국 전용 ${kr} · 공동 ${all.length - kr}) · 소진·임박·실패 ${shown.length}개${showAll ? '' : ' 표시'}`);
    for (const x of shown.slice(0, showAll ? 60 : limit)) {
      out.push(`- ${quotaLine(x)}`);
      if (x.url) out.push(`   원문: ${x.url}`);
    }
    if (!showAll && all.length > shown.length) out.push(`(여유 있는 쿼터 ${all.length - shown.length}개 숨김 — show_all=true)`);
    out.push('   검증 상태: EU 집계 수치(자동). 공동 쿼터는 한국 몫이 따로 없음. 업체별 물량·영향은 회사·철강협회 확인 필요');
  }

  if (!section || section === 'us') {
    const fr = (doc.federalRegister ?? []).filter((x) => (!onlyNew || x.isNew)
      && matches(q, x.title, (x.named ?? []).map((n) => n.company).join(' ')));
    const rank = (x) => ((x.named ?? []).length ? 0 : x.beatProduct ? 1 : 2);
    const sorted = [...fr].sort((a, b) => rank(a) - rank(b) || String(b.date).localeCompare(String(a.date)));
    out.push(`\n[미국 상무부·ITC 고시 · 최근 45일] ${fr.length}건 · 본문에 출입처 이름 ${fr.filter((x) => (x.named ?? []).length).length}건`);
    for (const x of sorted.slice(0, limit)) {
      out.push(`- ${x.isNew ? '[신규] ' : ''}${x.date} · ${x.stage}${x.section337 ? ' · 337조' : ''} · ${x.title}`);
      if (x.itcOutcome?.korea) out.push(`   ITC ${x.itcOutcome.phase} 판정: ${itcText(x.itcOutcome)} — 원문 "${String(x.itcOutcome.quote ?? '').slice(0, 220)}"`);
      if (x.rateChange?.length) out.push(`   세율 크게 바뀜: ${rateChangeText(x)}`);
      if (x.rateTable) out.push(`   세율${rateText(x).replace(/^ · /, ' — ')}`);
      for (const n of (x.named ?? []).slice(0, 5)) out.push(`   본문의 ${n.company}(${n.mentions}곳): ${n.lines.map((l) => `"${l}"`).join(' / ')}`);
      for (const t of (x.memoUnusual ?? []).slice(0, 3)) out.push(`   결정문 목차 — 흔치 않은 항목(관보 부록 원문): "${t}"`);
      for (const t of (x.memoNamed ?? []).slice(0, 3)) out.push(`   결정문 목차 — 출입처 이름(관보 부록 원문): "${t}"`);
      if (x.bodyError) out.push(`   본문 조회 실패(${x.bodyError}) — 업체명 미확인`);
      out.push(`   원문: ${x.url}`);
    }
    if (sorted.length > limit) out.push(`… 남은 ${sorted.length - limit}건`);
    out.push('   검증 상태: 관보 제목·본문 줄(자동). 세율은 관보 원문 표에서 자동으로 읽은 값(예비 판정은 확정 아님 — 최종에서 바뀔 수 있음, 기사 전 원문 표 대조). \'비선정 업체 세율\'은 개별 조사를 받지 않은 업체에 매긴 세율. 직전 판정은 같은 사건 번호(docket)의 최근 최종(·예비) 판정. 회사명 일치≠해당 회사 사건 — 조사 대상 목록 확인. 결정문 목차는 쟁점 제목일 뿐 결론이 아니다(\'흔치 않은\'은 자주 나오는 보조금 낱말이 없다는 뜻)');
  }

  if (!section || section === 'ktc') out.push(...ktcSection(doc.ktc, q, limit));
  if (!section || section === 'kita') out.push(...kitaSection(doc.kita, doc.events, q, limit, new Date(ctx.now.getTime() - days * 86400000).toISOString()));
  if (!section || section === 'edis') out.push(...edisSection(doc.edis, q, limit, showAll, new Date(ctx.now.getTime() - days * 86400000).toISOString()));

  if (!section || section === 'notices') {
    const from = new Date(ctx.now.getTime() - days * 86400000).toISOString();
    // EDIS 문서는 위 [미국 ITC 문서] 구역에 본문 발췌와 함께 나온다
    const ev = (doc.events ?? []).filter((e) => !e.renumbered && e.pageId !== 'edis' && new Date(e.detectedAt).toISOString() >= from && matches(q, e.label, e.text, e.country));
    const renumbered = (doc.events ?? []).filter((e) => e.renumbered && new Date(e.detectedAt).toISOString() >= from).length;
    const off = (doc.pages ?? []).filter((p) => p.status === 'disabled');
    const pages = (doc.pages ?? []).filter((p) => p.status !== 'disabled');
    const failed = pages.filter((p) => p.status !== 'ok');
    out.push(`\n[감지된 변화 · 감지일 기준 최근 ${days}일] ${ev.length}건 · 공고 목록 ${pages.length - failed.length}/${pages.length} 열림`);
    out.push(`(기준선 ${String(doc.baselineSince ?? doc.generatedAt).slice(0, 10)} 이후 새로 생긴 공고 줄·새 소진만 센다. 기준선 전에 이미 소진된 쿼터는 위 쿼터 표에 있다.)`);
    if (failed.length) out.push(`미확인(변화 없음 아님): ${failed.map((p) => `${p.label}(${p.error})`).join(', ')}`);
    if (off.length) out.push(`감시 안 함: ${off.map((p) => `${p.label}(${p.error})`).join(', ')}`);
    for (const e of ev.slice(0, limit)) {
      out.push(`- ${String(e.detectedAt).slice(0, 16)} · ${e.country} · ${e.label}`);
      out.push(`   잡힌 사실: ${e.text}`);
      if (e.repeats) out.push(`   주의: 목록 일련번호만 바뀌어 ${e.repeats}번 다시 잡힌 줄 — 이 감지도 번호 이동일 수 있음. 원문의 개시일·공고일로 새 사건인지 확인`);
      out.push(`   원문: ${e.url}`);
    }
    if (renumbered) out.push(`(목록 일련번호만 바뀐 재감지 ${renumbered}건은 뺐다 — 같은 줄의 첫 감지에 표시)`);
    if (!ev.length) out.push('이 기간 감지된 새 공고 줄·새 소진 없음(열리지 않은 목록은 미확인).');
  }
  out.push('\n다음: 원문은 source_document로 연다(미국 관보·EU·무역위 상세; EDIS 첨부 PDF는 토큰이 필요해 EDIS 누리집에서 문서 번호로) → 대상 품목·업체·세율·소진일·회의 안건 확인 → news_check로 보도 대조 → 회사·협회 확인.');
  return textResult(out.join('\n'));
}

// Change events carry only the changed fields; name·address come from the stored factory row (운영 10-28: 'KG스틸 고용
// 856→690명'만 떠서 어느 공장인지 몰랐다). Text that already names the plant is left as it is.
export function factoryEventText(doc, e) {
  const f = (doc?.factories ?? []).find((x) => x.id === e.factoryId);
  const name = f?.cmpnyNm ?? e.name;
  if (!name || String(e.text ?? '').includes(name)) return e.text;
  return `${name}${f?.rnAdres ? ` · ${f.rnAdres}` : ''} — ${e.text}`;
}

export async function usRecalls(ctx, args) {
  const doc = await readFeed(ctx, 'us-recalls');
  if (!doc) return missing('미국 리콜(NHTSA 전체)', '매일 17:10');
  if (doc.broken) return textResult('저장된 미국 리콜 결과 형식 오류 — 미확인.', true);
  const q = String(args.company ?? '').trim();
  const onlyNew = args.only_new === true || args.only_new === 'true';
  const limit = clampInt(args.limit, 1, 60, 20);
  const checks = doc.checks ?? [];
  const failed = checks.filter((c) => c.status !== 'ok');
  const rows = (doc.recalls ?? []).filter((x) => (!onlyNew || x.isNew)
    && matches(q, (x.why ?? []).map((w) => `${w.name} ${w.beat ?? ''}`).join(' '), x.makes?.join(' '), x.models, x.component, x.defect, x.supplierBox));
  const out = [`미국 리콜(NHTSA 전체 리콜 파일) · 접수 최근 ${doc.windowDays ?? 21}일 수집(보관 120일) · 출입처 관련 ${rows.length}건 · 확인 ${String(doc.generatedAt).slice(0, 16)}${ageNote(ctx, doc.generatedAt)}`,
    `점검 ${checks.length - failed.length}/${checks.length} 정상${failed.length ? ` · 미확인(0건 아님): ${failed.map((c) => `${c.source}(${c.error ?? `${c.errors}건 실패`})`).join(', ')}` : ''}`,
    ...(doc.rules ?? []).map((r) => `규칙: ${r}`)];
  for (const x of rows.slice(0, limit)) {
    out.push(`\n${x.isNew ? '[신규] ' : ''}${x.received} · ${x.campaign} · ${(x.why ?? []).map((w) => `${w.name}(${w.role})`).join(' · ')}`);
    out.push(`   잡힌 사실: ${(x.makes ?? []).join('·')} ${x.models} · ${x.component} · 대상 ${Number(x.affected ?? 0).toLocaleString('en-US')}대${x.doNotDrive ? ' · 운행 중지 권고' : ''}${x.parkOutside ? ' · 실외 주차 권고' : ''}`);
    out.push(`   결함(원문): ${String(x.defect ?? '').slice(0, 300)}`);
    if (x.supplierBox) out.push(`   원보고서 공급사 칸(원문): ${x.supplierBox}`);
    else if (x.reportError) out.push(`   원보고서: ${x.reportError}`);
    out.push(`   원문: ${x.url}${x.report ? ` · Part 573 ${x.report}` : ''}`);
    out.push('   검증 상태: NHTSA 공개 자료(자동). 국내 판매 차량 해당 여부·국내 리콜 계획은 회사·국토부 확인 필요');
  }
  if (rows.length > limit) out.push(`… 남은 ${rows.length - limit}건`);
  if (!rows.length) out.push('\n조건에 맞는 리콜 없음(점검 실패면 미확인).');
  const invs = (doc.investigations ?? []).filter((x) => (!onlyNew || x.isNew)
    && matches(q, (x.why ?? []).map((w) => `${w.name} ${w.beat ?? ''}`).join(' '), x.models, x.component, x.subject, x.summary, x.action));
  const invCheck = checks.find((c) => c.source === 'NHTSA 결함조사(ODI)');
  out.push(`\n[결함조사(ODI) · 최근 ${doc.invLookbackDays ?? 120}일 개시·종결] 출입처 관련 ${invs.length}건${invCheck && invCheck.status !== 'ok' ? ' — 조회 실패, 미확인(0건 아님)' : ''}${doc.investigations ? '' : ' — 아직 수집 전'}`);
  for (const x of invs.slice(0, limit)) {
    out.push(`${x.isNew ? '[신규] ' : ''}${x.closed ?? x.opened} · ${x.action} ${x.type} ${x.kind} · ${(x.why ?? []).map((w) => `${w.name}(${w.role})`).join(' · ')}`);
    out.push(`   잡힌 사실: ${x.models} · ${x.component} · 「${x.subject}」 · 개시 ${x.opened}${x.closed ? ` · 종결 ${x.closed}` : ''}${(x.recallCampaigns ?? []).length ? ` · 연결 리콜 ${x.recallCampaigns.join(',')}` : ''}`);
    if (x.summary) out.push(`   요약(원문): ${String(x.summary).slice(0, 300)}`);
    out.push(`   원문: ${x.url}`);
    out.push('   검증 상태: NHTSA 공개 자료(자동). 조사 개시는 결함 확정이 아니고 종결은 결함 없음 판정이 아님. 국내 판매 차량 해당 여부는 회사·국토부 확인');
  }
  const cm = doc.complaints;
  const cmCheck = checks.find((c) => c.source === 'NHTSA 소비자 결함 신고');
  const spikes = (cm?.spikes ?? []).filter((x) => x.active && (!onlyNew || x.isNew)
    && matches(q, x.brand, x.beat, x.model, (x.parts ?? []).map((p) => p.component).join(' ')));
  out.push(`\n[소비자 결함 신고 급증 · 최근 ${cm?.windowDays ?? 28}일${cm?.window ? `(${cm.window.join('~')})` : ''}, 앞 24주와 비교] ${spikes.length}건${cmCheck && cmCheck.status !== 'ok' ? ' — 조회 실패, 미확인(0건 아님)' : ''}${cm ? '' : ' — 아직 수집 전'}`);
  for (const r of cm?.rules ?? []) out.push(`규칙: ${r}`);
  for (const x of spikes.slice(0, limit)) {
    const harm = [x.fire && `화재 ${x.fire}`, x.crash && `충돌 ${x.crash}`, x.injured && `부상 ${x.injured}`, x.deaths && `사망 ${x.deaths}`].filter(Boolean).join('·');
    out.push(`${x.isNew ? '[신규] ' : ''}${x.tier} · ${x.brand} ${x.model} · 연식 ${x.years} · 신고 ${x.complaints}건${harm ? ` · ${harm}` : ''} · 처음 본 날 ${String(x.firstSeen).slice(0, 10)}`);
    out.push(`   부품별: ${(x.parts ?? []).map((p) => `${p.component} ${p.recent}건(평소 28일 ${p.baselinePer28})`).join(', ')}`);
    if ((x.recentRecalls ?? []).length) {
      out.push(`   최근 60일 같은 차종 리콜: ${x.recentRecalls.map((r) => `${r.campaign}(${r.received}, ${r.component})`).join(' · ')}${(x.sameComponentRecall ?? []).length ? ' — 같은 부품이라 리콜 공지 뒤 신고일 수 있음' : ''}`);
    }
    for (const smp of x.samples ?? []) out.push(`   신고 ${smp.odino}(${smp.year}년형, 접수 ${smp.received}): "${smp.text}"`);
    out.push(`   원문: ${x.url}`);
    out.push('   검증 상태: 소비자가 낸 신고(자동 집계) — 결함 확정 아님. 같은 원인인지·국내 판매 차종 해당 여부는 회사·국토부 확인');
  }
  out.push(...tsbSection(doc.tsbs, checks.find((c) => c.source === 'NHTSA 제조사 통신(TSB)'), q, limit, onlyNew, args.show_all === true || args.show_all === 'true'));
  out.push('\n다음: NHTSA 리콜 페이지(source_document)로 대상 차대·부품 확인 — 원보고서(Part 573)·제조사 통신 PDF는 source_document가 못 읽어 링크를 직접 연다 → 국내 판매 여부·자동차리콜센터 → news_check.');
  return textResult(out.join('\n'));
}

// NHTSA 제조사 통신(서비스 캠페인·보증 프로그램·안전 관련 서비스 공지) — 수집기 scripts/nhtsa_tsbs.py. 참고(C)는 show_all일 때만 줄로 보인다.
export function tsbSection(ts, check, q, limit, onlyNew, showAll) {
  const out = [];
  const all = (ts?.items ?? []).filter((x) => (!onlyNew || x.isNew)
    && matches(q, (x.companies ?? []).join(' '), (x.brands ?? []).join(' '), (x.models ?? []).map((m) => m.model).join(' '), x.summary, (x.components ?? []).join(' '), x.campaign, x.doc, x.kindName));
  const order = { A: 0, B: 1, C: 2 };
  const shown = all.filter((x) => showAll || x.tier !== 'C')
    .sort((a, b) => (Number(b.isNew) - Number(a.isNew)) || (order[a.tier] - order[b.tier]) || String(b.lastAdded ?? b.added).localeCompare(String(a.lastAdded ?? a.added)));
  const n = (t) => all.filter((x) => x.tier === t).length;
  out.push(`\n[제조사 통신(서비스 캠페인·보증 연장·서비스 공지, 캠페인 단위) · 파일 추가일 최근 ${ts?.windowDays ?? 120}일] ${all.length}건(A ${n('A')}·B ${n('B')}·참고 C ${n('C')}${showAll ? '' : ' — C는 show_all=true'})`
    + `${check && check.status !== 'ok' ? ' — 조회 실패, 미확인(0건 아님)' : ''}${ts ? '' : ' — 아직 수집 전'}${ts?.fileModified ? ` · 파일 갱신 ${ts.fileModified}` : ''}`);
  for (const r of ts?.rules ?? []) out.push(`규칙: ${r}`);
  for (const x of shown.slice(0, limit)) {
    const models = (x.models ?? []).map((m) => `${m.model}${(m.years ?? []).length ? `(${m.years.length > 3 ? `${m.years[0]}~${m.years[m.years.length - 1]}` : m.years.join('·')})` : ''}`);
    out.push(`${x.isNew ? '[신규] ' : ''}${x.tier} · ${x.added} · ${x.kindName ?? x.type} · ${(x.brands ?? []).join('·')} ${models.slice(0, 6).join(', ')}${x.modelCount > 6 ? ` 외 ${x.modelCount - 6}개 차종` : ''}`);
    out.push(`   ${x.campaign ? `캠페인 ${x.campaign} · ` : ''}문서 ${x.docCount > 1 ? `${x.docCount}건(${(x.docs ?? []).map((d) => d.doc).slice(0, 6).join(', ')}${x.docCount > 6 ? ' …' : ''})` : (x.doc || '?')}`
      + `${x.mfrDate ? ` · 제조사 통신일 ${x.mfrDate}` : ''}${x.lastAdded && x.lastAdded !== x.added ? ` · 마지막 문서 ${x.lastAdded}` : ''}${(x.components ?? []).length ? ` · 부품 ${x.components.slice(0, 4).join(', ')}` : ''}`
      + `${x.otherRows ? ` · GM 다른 차종 함께(${x.otherRows}줄)` : ''}${x.renotice ? ' · 재통지' : ''}`);
    out.push(`   요약(원문): ${x.summary}`);
    out.push(`   원문: ${x.url}`);
  }
  if (shown.length > limit) out.push(`… 남은 ${shown.length - limit}건`);
  if (all.length) out.push('   검증 상태: NHTSA 공개 파일(자동). 딜러용 통신이라 결함 인정·리콜 아님. 국내 판매 차량·국내 무상수리 해당 여부는 회사 확인');
  return out;
}

const kmd = (v) => { const t = Date.parse(v); return Number.isFinite(t) ? new Date(t + 9 * 3600000).toISOString().slice(5, 16).replace('T', ' ') : String(v ?? '').slice(5, 16); };

// Competitor exclusives checked against what the radar had seen before them (reverse_prior_capture.py). Automatic candidates only.
export async function scoopReverse(ctx, args) {
  const doc = await readFeed(ctx, 'reverse-check');
  if (!doc) return missing('경쟁지 단독 자동 역추적', '매일 19:20');
  if (doc.broken) return textResult('저장된 역추적 결과 형식 오류 — 미확인.', true);
  const q = String(args.company ?? '').trim();
  const want = ['먼저 잡은 후보', '같은 회사 항목만', '없음', '회사 미상'].includes(args.verdict) ? args.verdict : null;
  const days = clampInt(args.days, 1, 30, 14);
  const limit = clampInt(args.limit, 1, 60, 15);
  const from = Date.parse(doc.generatedAt) - days * 86400000;
  const rows = (doc.articles ?? []).filter((x) => Date.parse(x.published) >= from && matches(q, x.title, (x.companies ?? []).join(' ')));
  const n = (v) => rows.filter((x) => x.verdict === v).length;
  const by = {};
  for (const x of rows) if (x.verdict === '먼저 잡은 후보') (by[x.best.label] ??= []).push(x.best.leadHours);
  const med = (a) => { const s = [...a].sort((p, q2) => p - q2); return s.length % 2 ? s[(s.length - 1) / 2] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2; };
  const loaded = Object.values(doc.feedsLoaded ?? {}).filter(Boolean).length;
  const out = [`경쟁지 [단독] 자동 역추적 · 최근 ${days}일 ${rows.length}건 · 확인 ${String(doc.generatedAt).slice(0, 16)}${ageNote(ctx, doc.generatedAt, 48)}`,
    `먼저 잡은 후보 ${n('먼저 잡은 후보')} · 같은 회사 항목만 ${n('같은 회사 항목만')} · 없음 ${n('없음')} · 회사 미상 ${n('회사 미상')} (레이더 기억 ${doc.memoryItems}건, 감시 ${loaded}/${Object.keys(doc.feedsLoaded ?? {}).length} 읽음${(doc.feedsFailed ?? []).length ? `, 실패 ${doc.feedsFailed.join('·')} — 미확인` : ''}${(doc.feedsEmpty ?? []).length ? `, 저장 결과 없음 ${doc.feedsEmpty.join('·')} — 그 감시 항목은 대조 못 함` : ''})`,
    `원천별 먼저 잡은 후보: ${Object.entries(by).sort((a, b) => b[1].length - a[1].length).map(([k, v]) => `${k} ${v.length}건(중간 ${Math.round(med(v))}시간 앞)`).join(' · ') || '없음'}`,
    ...(doc.rules ?? []).map((r) => `규칙: ${r}`)];
  for (const v of want ? [want] : ['먼저 잡은 후보', '같은 회사 항목만', '없음']) {
    const g = rows.filter((x) => x.verdict === v);
    if (!g.length) continue;
    out.push(`\n[${v}] ${g.length}건`);
    for (const x of g.slice(0, v === '없음' && !want ? Math.min(limit, 8) : limit)) {
      out.push(`- ${kmd(x.published)} · ${x.source ?? ''} 「${x.title}」(${(x.companies ?? []).join('·')})`);
      if (x.best) out.push(`   레이더: ${kmd(x.best.seen)} ${x.best.label} — ${x.best.text.slice(0, 140)} (${x.best.leadHours}시간 앞${x.best.why?.length ? `, 겹친 낱말 ${x.best.why.join('·')}` : ''}) · id ${x.best.id}`);
    }
    if (g.length > limit) out.push(`… 남은 ${g.length - limit}건`);
  }
  out.push('\n다음: 먼저 잡은 후보는 기사 전문과 레이더 원문을 열어 같은 사건인지 확인한다(사람 판정 Y/P/N은 역추적 기록에 따로). 없음이 많은 종류(인사·일정·내부 계획)는 공개 원천으로 앞서기 어렵다.');
  return textResult(out.join('\n'));
}

export async function usEpa(ctx, args) {
  const doc = await readFeed(ctx, 'us-epa');
  if (!doc) return missing('미국 EPA 인증', '매일 06:20');
  if (doc.broken) return textResult('저장된 EPA 결과 형식 오류 — 미확인.', true);
  const q = String(args.company ?? '').trim();
  const kind = ['새 모델', '주행거리 변화', '연식 변경'].includes(args.kind) ? args.kind : null;
  const limit = clampInt(args.limit, 1, 60, 20);
  const failed = (doc.checks ?? []).filter((c) => c.status !== 'ok');
  const rows = (doc.vehicles ?? []).filter((v) => (!kind || v.kind === kind) && matches(q, v.company, v.make, v.model, v.baseModel));
  const out = [`미국 EPA 인증(fueleconomy.gov) · 현대차·기아·제네시스 새 등록 ${rows.length}건 · 확인 ${String(doc.generatedAt).slice(0, 16)}${ageNote(ctx, doc.generatedAt, 60, true)}`,
    failed.length ? `미확인(0건 아님): ${failed.map((c) => `${c.source}(${c.error})`).join(', ')}` : `파일 정상 · 갱신 ${(doc.checks ?? [])[0]?.fileModified ?? '?'}`,
    ...(doc.rules ?? []).map((r) => `규칙: ${r}`)];
  for (const v of rows.slice(0, limit)) {
    out.push(`\n${v.isNew ? '[신규] ' : ''}${v.created ?? '?'} · ${v.kind} · ${v.year} ${v.make} ${v.model}`);
    out.push(`   잡힌 사실: ${v.vclass ?? ''} · ${v.drive ?? ''} · ${v.trany ?? ''}${v.atvType ? ` · ${v.atvType}` : ''}${v.evMotor ? ` · 모터 ${v.evMotor}` : ''}${v.range ? ` · 주행거리 ${v.range}마일` : ''}${v.comb ? ` · 복합 ${v.comb}${v.atvType === 'EV' ? 'MPGe' : 'mpg'}` : ''}`);
    if (v.compare) out.push(`   비교: 직전 ${v.compare.previousYear}년형 주행거리 ${v.compare.previousRanges.join('/')}마일`);
    out.push(`   원문: ${v.url}`);
  }
  if (rows.length > limit) out.push(`… 남은 ${rows.length - limit}건`);
  if (!rows.length) out.push('\n새 등록 없음(첫 실행은 기준선, 조회 실패면 미확인).');
  const vins = (doc.vpicModels ?? []).filter((v) => matches(q, v.company, v.make, v.model));
  if (vins.length) {
    out.push(`\n[NHTSA vPIC 새 모델명(VIN 등록)] ${vins.length}건`);
    for (const v of vins.slice(0, limit)) out.push(`- ${v.isNew ? '[신규] ' : ''}${String(v.firstSeen).slice(0, 10)} · ${v.make} '${v.model}' · ${(v.years ?? []).join('·')}년형 · ${v.url}`);
  }
  out.push('\n다음: 미국 사양이다 — 국내 출시·인증 여부와 사양은 회사 확인. 새 모델·주행거리 변화·새 모델명은 news_check로 보도 대조.');
  return textResult(out.join('\n'));
}

export async function krFuel(ctx, args) {
  const doc = await readFeed(ctx, 'kr-fuel');
  if (!doc) return missing('국내 연비 신고', '매일 06:10');
  if (doc.broken) return textResult('저장된 연비 신고 결과 형식 오류 — 미확인.', true);
  const q = String(args.company ?? '').trim();
  const kind = ['새 모델명', '주행거리 변화', '사양·연식 추가'].includes(args.kind) ? args.kind : null;
  const limit = clampInt(args.limit, 1, 60, 20);
  const c = (doc.checks ?? [])[0] ?? {};
  const rows = (doc.vehicles ?? []).filter((v) => (!kind || v.kind === kind) && matches(q, v.company, v.maker, v.model));
  const out = [`국내 자동차 표시연비 신고(에너지공단, 공공데이터포털) · 출입처 브랜드 새 신고 ${rows.length}건 · 확인 ${String(doc.generatedAt).slice(0, 16)}${ageNote(ctx, doc.generatedAt, 60, true)}`,
    c.status === 'ok' ? `목록 정상 · 전체 ${c.rows}행 · 출입처 ${c.beatRows}행${c.note ? ` · ${c.note}` : ''}` : `미확인(0건 아님): ${c.error ?? c.status}${c.status === 'unset' ? ` — ${doc.dataset ?? ''}` : ''}`,
    ...(doc.rules ?? []).map((r) => `규칙: ${r}`)];
  for (const v of rows.slice(0, limit)) {
    out.push(`\n${v.isNew ? '[신규] ' : ''}${v.registered ?? '?'} · ${v.kind}${v.bulk ? '(일괄 갱신)' : ''} · ${v.company} · ${v.maker} ${v.model}`);
    out.push(`   잡힌 사실: ${v.year}년 · ${v.carKind ?? ''} ${v.carType ?? ''} · ${v.fuel ?? ''}${v.displacement ? ` ${v.displacement}cc` : ''}${v.gear ? ` · ${v.gear}` : ''} · 표시연비 ${v.eff ?? '?'}(도심 ${v.urban ?? '?'}·고속 ${v.highway ?? '?'})${v.co2 ? ` · CO2 ${v.co2}g/km` : ''}${v.grade ? ` · ${v.grade}등급` : ''}${v.range ? ` · 1회 충전 ${v.range}km` : ''}`);
    if (v.compare) out.push(`   비교: 같은 모델명 이전 행 1회 충전 ${v.compare.previousRanges.join('/')}km`);
  }
  if (rows.length > limit) out.push(`… 남은 ${rows.length - limit}건`);
  if (!rows.length) out.push('\n새 신고 없음(첫 실행은 기준선, 조회 실패·활용신청 전이면 미확인).');
  out.push('\n다음: 연비 신고는 출시 확정이 아니다 — 출시 시점·가격·사양은 회사 확인. 새 모델명은 news_check로 보도 대조.');
  return textResult(out.join('\n'));
}

export async function usLitigation(ctx, args) {
  const doc = await readFeed(ctx, 'us-litigation');
  const q = String(args.company ?? '').trim();
  const onlyNew = args.only_new === true || args.only_new === 'true';
  const routine = args.include_routine === true || args.include_routine === 'true';
  const limit = clampInt(args.limit, 1, 60, 20);
  // 소송 결과가 없거나 깨져도 OSHA 구역은 따로 보여 준다(다른 저장소)
  if (!doc || doc.broken) {
    const head = doc ? '저장된 소송 결과 형식 오류 — 미확인.' : missing('미국 소송·ITC', '평일 07:50').content[0].text;
    return textResult([head, ...oshaSection(await readFeed(ctx, 'us-osha'), q, limit, onlyNew, routine, ctx)].join('\n'), true);
  }
  const checks = doc.checks ?? [];
  const failed = checks.filter((c) => c.status !== 'ok');
  const base = (doc.cases ?? []).filter((x) => (!onlyNew || x.isNew) && matches(q, (x.beat ?? []).join(' '), x.caseName, x.category, x.court));
  const rows = base.filter((x) => routine || x.priority < 3);
  const out = [`미국 소송·ITC 337조 · 최근 ${doc.windowDays}일 수집(보관 120일) · 출입처 당사자 사건 ${rows.length}건 · 확인 ${String(doc.generatedAt).slice(0, 16)}${ageNote(ctx, doc.generatedAt)}`,
    `질의 ${checks.length - failed.length}/${checks.length} 정상${failed.length ? ` · 미확인(0건 아님): ${failed.slice(0, 6).map((c) => `${c.source}(${c.error})`).join(', ')}` : ''}`,
    ...(doc.rules ?? []).map((r) => `규칙: ${r}`)];
  const ops = (doc.opinions ?? []).filter((x) => (!onlyNew || x.isNew) && matches(q, (x.beat ?? []).join(' '), x.caseName, x.holding));
  out.push(`\n[판결 · 국제무역법원·연방순회항소법원, 출입처가 당사자로 적힌 것 최근 21일 조회·120일 보관] ${ops.length}건`);
  for (const x of ops.slice(0, limit)) {
    out.push(`- ${x.isNew ? '[신규] ' : ''}${x.dateFiled} · ${x.courtId === 'cit' ? '국제무역법원' : '연방순회항소법원'} · ${(x.beat ?? []).join('·')}(${x.role})`);
    out.push(`   잡힌 사실: 「${x.caseName}」 사건 ${x.docketNumber ?? '?'}${x.slipOp ? ` · Slip Op. ${x.slipOp}` : ''} 판결 등록`);
    out.push(x.holding ? `   요지(판결문 원문): "${x.holding}"${x.holdingKo ? ` → 낱말 풀이: ${x.holdingKo}` : ''}` : `   요지: 미추출${x.holdingError ? `(${x.holdingError})` : ''} — 판결문에서 확인`);
    if (x.reading) out.push(`   읽기(가설): ${x.reading}`);
    out.push(`   원문: ${x.url}${x.pdf ? ` · PDF ${x.pdf}` : ''}`);
  }
  if (!ops.length) out.push(doc.opinions ? '최근 판결 없음(판결 질의 실패면 미확인).' : '판결 감시 결과 없음 — 다음 수집(평일 07:50) 이후.');
  out.push(`\n[사건 접수 · 출입처 당사자] ${rows.length}건`);
  for (const x of rows.slice(0, limit)) {
    out.push(`\n${x.isNew ? '[신규] ' : ''}${x.dateFiled} · ${x.category} · ${(x.beat ?? []).join('·')}(${x.role})`);
    if (x.summary) out.push(`   한 줄: ${x.summary}`);
    out.push(`   잡힌 사실: ${x.court ?? x.courtId} ${x.docketNumber ?? ''} 「${x.caseName}」 접수${x.dateTerminated ? ` · 종결 ${x.dateTerminated}` : ''}${x.appealFrom ? ` · 원심 ${x.appealFrom}` : ''}${x.caseType ? ` · 유형 ${x.caseType}` : ''}`);
    out.push(`   당사자 중 출입처: ${(x.matchedParties ?? []).join(', ')}${x.suitNature ? ` · 사건 유형 ${x.suitNature}` : ''}${x.cause ? ` · 근거 ${x.cause}` : ''}`);
    out.push(`   원문: ${x.url}`);
    out.push('   검증 상태: 법원 사건 목록(자동). 청구 내용·금액은 소장 원문 확인, 회사 입장 확인 필요');
  }
  if (rows.length > limit) out.push(`… 남은 ${rows.length - limit}건`);
  if (!rows.length) out.push('\n조건에 맞는 사건 없음(미확인 질의는 0건 아님, CourtListener 미수록 사건 가능).');
  if (!routine && base.length > rows.length) out.push(`(일상 사건 ${base.length - rows.length}건 숨김 — 소비자·제조물책임, 개인 고용, 위조품 단속: include_routine=true)`);
  const itc = (doc.itc ?? []).filter((x) => (!onlyNew || x.isNew) && matches(q, x.title, (x.named ?? []).map((n) => n.company).join(' ')));
  out.push(`\n[ITC 337조 · 출입처 이름이 나온 고시] ${itc.length}건`);
  for (const x of itc.slice(0, limit)) {
    out.push(`- ${x.isNew ? '[신규] ' : ''}${x.date} · ${x.stage} · ${x.title}`);
    for (const n of (x.named ?? []).slice(0, 5)) out.push(`   본문의 ${n.company}(${n.mentions}곳): ${n.lines.map((l) => `"${l}"`).join(' / ')}`);
    out.push(`   원문: ${x.url}`);
  }
  out.push(...oshaSection(await readFeed(ctx, 'us-osha'), q, limit, onlyNew, routine, ctx));
  out.push('\n다음: 판결은 PDF(원문)에서 결론·세율·당사자 주장 확인 → news_check로 보도 대조. 사건은 소장(Complaint) 열람 → 청구 원인·금액·상대방 확인 → 회사 확인. ITC 고시는 source_document(federalregister.gov)로 연다. OSHA는 원문(osha.gov 점검 상세)에서 위반 기준·벌금·이의 제기 여부 확인 → 현지 보도·회사 확인.');
  return textResult(out.join('\n'));
}

// 미국 OSHA 점검·위반(us_osha_watch.py): 출입처 미국 법인·공장. 사망·중대사고·사고·민원 점검과 위반 통지가 먼저, 정기·후속 점검은 include_routine.
export function oshaSection(doc, q = '', limit = 20, onlyNew = false, routine = false, ctx = null) {
  if (!doc) return ['\n[미국 OSHA 점검·위반] 아직 수집 전 — 미확인'];
  if (doc.broken) return ['\n[미국 OSHA 점검·위반] 저장 결과 형식 오류 — 미확인'];
  const c = (doc.checks ?? [])[0] ?? {};
  // 출입처 공장 주소의 하도급·협력사 점검(atSite)은 사망·중대사고·사고·사망 사고 요약만 보인다
  const weight = (x) => (['M', 'A'].includes(x.type) || (x.accidents ?? []).some((a) => a.fatality) ? 0 : x.atSite ? 3
    : (x.violations ?? []).some((v) => ['W', 'R'].includes(v.type)) || (x.penaltyInitial ?? 0) >= 100000 ? 1
      : ['B', 'C'].includes(x.type) || (x.violations ?? []).length ? 2 : 3);
  const all = (doc.inspections ?? []).filter((x) => (!onlyNew || x.isNew) && matches(q, x.company, x.estab, x.city, x.state));
  const rows = all.filter((x) => routine || weight(x) < 3).sort((a, b) => weight(a) - weight(b) || String(b.opened).localeCompare(String(a.opened)));
  const out = [`\n[미국 OSHA 점검·위반 · 출입처 미국 법인·공장 · 개시 ${String(doc.since ?? '').slice(0, 10)} 이후 · 확인 ${String(doc.generatedAt).slice(0, 16)}${ctx ? ageNote(ctx, doc.generatedAt, 60, true) : ''}] `
    + `${rows.length}건${routine ? '' : ` · 정기·후속·모니터링 점검과 공장 주소 하도급의 일반 점검 ${all.length - rows.length}건 숨김(include_routine=true)`} · 원천 ${c.status ?? '?'}${c.error ? `(${c.error})` : ''}`
    + ` · 지켜보는 공장 주소 ${Object.keys(doc.sites ?? {}).length}곳`];
  for (const x of rows.slice(0, limit)) {
    const v = x.violations ?? [];
    const kinds = [...new Set(v.map((y) => y.typeName))].join('·');
    out.push(`- ${x.isNew ? '[신규] ' : ''}개시 ${x.opened} · ${x.company}${x.atSite ? '(공장 주소 하도급)' : ''} · ${x.typeName}(${x.type}) 점검${x.closed ? ` · 종결 ${x.closed}` : ' · 진행 중'}${x.stale ? ' · ⚠ 이번 조회 실패, 직전 값' : ''}${x.notReturned ? ' · ⚠ 이번 조회에 안 나옴' : ''}`);
    out.push(x.atSite ? `   사업장: ${x.estab} — 출입처(${x.company}) 공장 주소 ${x.address ?? '?'} (${x.city ?? '?'}, ${x.state ?? '?'})의 하도급·협력사 점검(그 회사 점검, 출입처 책임 아님)${x.naics ? ` · NAICS ${x.naics}` : ''}`
      : `   사업장: ${x.estab} (${x.city ?? '?'}, ${x.state ?? '?'})${x.employees ? ` · 종업원 ${x.employees}명` : ''}${x.naics ? ` · NAICS ${x.naics}` : ''}`);
    out.push(v.length ? `   위반 통지 ${v.length}건(${kinds}) · 최초 벌금 합 $${(x.penaltyInitial ?? 0).toLocaleString('en-US')}${x.penaltyCurrent !== x.penaltyInitial ? ` → 현재 $${(x.penaltyCurrent ?? 0).toLocaleString('en-US')}` : ''} · 통지 ${[...new Set(v.map((y) => y.issued))].join(', ')}`
      : '   위반 통지 없음(아직 미발부일 수 있음 — 개시 뒤 최대 6개월)');
    for (const a of (x.accidents ?? []).slice(0, 2)) out.push(`   사고 요약 ${a.date || '?'}${a.fatality ? ' · 사망' : ''}: ${String(a.desc ?? '').slice(0, 160)}${a.abstract ? ` — "${a.abstract.slice(0, 240)}"` : ''}`);
    out.push(`   원문: ${x.url}`);
  }
  if (rows.length > limit) out.push(`… 남은 ${rows.length - limit}건`);
  if (!rows.length) out.push('조건에 맞는 점검 없음(첫 실행은 기준선, 조회 실패면 미확인).');
  if ((doc.dropped ?? []).length) out.push(`(이름 검색에 걸렸지만 출입처 규칙 밖이라 뺀 사업장 ${doc.dropped.length}곳 — 딜러·이름 겹침 등. 빠진 출입처가 있는지 확인: ${doc.dropped.slice(0, routine ? 60 : 12).map(([n, k]) => `${n}(${k})`).join(', ')}${!routine && doc.dropped.length > 12 ? ' …' : ''})`);
  out.push('   검증 상태: OSHA 노동부 API(자동). 점검≠위반 확정, 벌금은 최초 부과액(이의 제기·합의로 바뀜). 하도급 점검은 출입처 점검과 같은 주소로 열린 것만 — 주소 표기가 다르면 빠진다. 사망자·경위는 원문·현지 보도로');
  return out;
}

// Same-name doubt for a court notice's company (kr_insolvency_watch.pick): factory outside the court's region, several owners.
export const identityNote = (ind) => `${ind?.regionMismatch ? ' · ⚠ 공장 주소가 관할 법원 지역 밖(다른 회사일 수 있음)' : ''}${(ind?.owners ?? 0) >= 2 ? ` · 같은 이름 공장 대표자 ${ind.owners}명` : ''}`;

// Building permits on the same parcel as a beat company's registered factory (kr-building feed), shown under kr_official.
export function buildingLine(x) {
  const area = x.totArea ? `연면적 ${Number(x.totArea).toLocaleString('en-US', { maximumFractionDigits: 0 })}㎡${x.archGbCdNm === '증축' ? '(건물 전체일 수 있음, 증축분 아님)' : ''}` : '연면적 미기재';
  const what = [x.archGbCdNm, x.mainPurpsCdNm].filter(Boolean).join(' ') || '용도 미기재';
  const where = x.sameLot === false ? `${x.factory ?? x.company} 부지와 같은 본번의 다른 필지(${x.plot})` : `${x.factory ?? x.company} 부지(${x.plot})`;
  return `${x.kind === '새 허가' ? '건축허가' : x.kind}: ${where} · ${what} · ${area} · 허가 ${x.permitted ?? '?'}`
    + `${x.startPlanned ? ` · 착공예정 ${x.startPlanned}` : ''}${x.started ? ` · 착공 ${x.started}` : ''}${x.useApproved ? ` · 사용승인 ${x.useApproved}` : ''}`;
}
async function buildingSection(ctx, q, days, limit) {
  const doc = await readFeed(ctx, 'kr-building');
  if (!doc) return ['\n[공장 부지 건축허가] 결과 없음 — 미확인(월 07:50 실행 확인)'];
  if (doc.broken) return ['\n[공장 부지 건축허가] 저장 형식 오류 — 미확인'];
  const checks = doc.checks ?? [];
  const from = new Date(ctx.now.getTime() + 9 * 3600000 - days * 86400000).toISOString().slice(0, 10);
  const all = (doc.permits ?? []).filter((x) => !x.orphan && (String(x.permitted ?? '') >= from || String(x.changedAt ?? '').slice(0, 10) >= from)
    && matches(q, x.company, x.factory, x.plot, x.mainPurpsCdNm, x.bldNm));
  const rank = { A: 0, B: 1, C: 2 };
  const rows = all.filter((x) => q || x.tier !== 'C').sort((a, b) => (rank[a.tier] ?? 3) - (rank[b.tier] ?? 3)
    || String(b.permitted ?? '').localeCompare(String(a.permitted ?? '')));
  const out = [`\n[공장 부지 건축허가 · 출입처 공장 ${doc.plants ?? '?'}곳 중 번지 확인 ${doc.parcelsResolved ?? 0}곳 · 허가일 최근 ${days}일] ${rows.length}건${all.length - rows.length ? ` · 소규모 ${all.length - rows.length}건` : ''} · 확인 ${String(doc.generatedAt).slice(0, 16)}${ageNote(ctx, doc.generatedAt)}`,
    `원천: ${checks.map((c) => `${c.source} ${c.status}${c.error ? `(${c.error})` : ''}`).join(' · ')}`,
    ...(doc.rules ?? []).map((r) => `규칙: ${r}`)];
  // Coverage gaps: plants whose lot is unknown and lots whose query failed have unknown permits, not none.
  const gap = (label, list, fmt) => {
    const hit = (list ?? []).filter((x) => matches(q, x.company, x.plant, x.road, x.parcel));
    if (hit.length) out.push(`${label} ${hit.length}곳(허가 미확인): ${hit.slice(0, q ? 20 : 5).map(fmt).join(' · ')}${hit.length > (q ? 20 : 5) ? ' …' : ''}`);
  };
  gap('번지 못 찾은 공장', doc.unresolved, (x) => `${x.company} ${x.plant ?? ''}(${x.road ?? '?'}, ${x.error ?? '?'})`);
  gap('조회 실패 번지', doc.archFailed, (x) => `${x.company} ${x.plant ?? ''}(${x.parcel ?? '?'}, ${x.error ?? '?'})`);
  for (const x of rows.slice(0, limit)) {
    out.push(`- ${x.isNew ? '[신규] ' : ''}${x.permitted ?? '?'} · ${x.company} · ${x.kind}${x.bldNm ? ` · ${x.bldNm}` : ''}`);
    out.push(`   잡힌 사실: ${buildingLine(x)}`);
    out.push(x.sameLot === false
      ? `   검증 상태: 건축주 미표기 — 공장과 본번만 같은 다른 필지라 이웃 회사 건물일 수 있음${x.bldNm ? `(건물명 '${x.bldNm}')` : ''}. 건축주는 지자체(건축과) 확인`
      : '   검증 상태: 건축주 미표기 — 같은 번지의 허가일 뿐. 건축주·용도·투자 규모는 회사·지자체(건축과) 확인');
  }
  if (rows.length > limit) out.push(`… 남은 ${rows.length - limit}건`);
  if (!rows.length) out.push('조건에 맞는 허가 없음(위 미설정·실패는 0건 아님).');
  return out;
}

// Court insolvency notices of beat-industry manufacturers (kr-insolvency feed), shown under kr_official (no new connector tool).
async function insolvencySection(ctx, q, days, limit) {
  const doc = await readFeed(ctx, 'kr-insolvency');
  if (!doc) return ['\n[협력사 회생·파산] 결과 없음 — 미확인(평일 07:20·17:20 실행 확인)'];
  if (doc.broken) return ['\n[협력사 회생·파산] 저장 형식 오류 — 미확인'];
  const checks = doc.checks ?? [];
  const courts = checks.filter((c) => !/^(회생회사|공장등록)/.test(String(c.source)));
  const bad = courts.filter((c) => c.status !== 'ok');
  const other = checks.filter((c) => /^(회생회사|공장등록)/.test(String(c.source)));
  const from = new Date(ctx.now.getTime() - days * 86400000).toISOString().slice(0, 10);
  const all = (doc.events ?? []).filter((e) => String(e.posted ?? e.firstSeen).slice(0, 10) >= from
    && matches(q, e.company, e.court, e.kind, e.industry?.label, e.industry?.product, e.industry?.industry, e.watch?.beat));
  const rank = { A: 0, B: 1, C: 2 };
  const rows = all.filter((e) => q || e.tier !== 'C').sort((a, b) => (rank[a.tier] ?? 3) - (rank[b.tier] ?? 3)
    || String(b.posted ?? '').localeCompare(String(a.posted ?? '')));
  const minor = all.length - rows.length;
  const out = [`\n[협력사 회생·파산 · 대법원 회생·파산 공고(법원 ${courts.length}곳 목록)·회생회사 M&A 공고 · 공고 최근 ${days}일] 출입 업종 ${rows.length}건${minor ? ` · 이름 낱말만 ${minor}건(company 낱말로 보기)` : ''} · 확인 ${String(doc.generatedAt).slice(0, 16)}${ageNote(ctx, doc.generatedAt)}`,
    `원천: 법원 목록 ${courts.length - bad.length}/${courts.length} 정상${bad.length ? `(미확인: ${bad.slice(0, 4).map((c) => `${c.source}(${c.error ?? c.status})`).join(', ')})` : ''} · ${other.map((c) => `${c.source} ${c.status}${c.pending ? `(업종 조회 대기 ${c.pending}곳 — 다음 실행)` : ''}${c.error ? `(${c.error})` : ''}`).join(' · ')}${doc.watchlistSize ? ` · 협력사 명단 ${doc.watchlistSize}곳` : ' · 협력사 명단 비어 있음'}`,
    ...(doc.rules ?? []).map((r) => `규칙: ${r}`)];
  for (const e of rows.slice(0, limit)) {
    const ind = e.industry ?? {};
    out.push(`\n${e.isNew ? '[신규] ' : ''}${e.posted ?? '게시일 미상'} · ${e.kind} · ${e.company} · ${e.court}${e.caseNo ? ` ${e.caseNo}` : ''}${e.division ? `(${e.division})` : ''}`);
    out.push(`   잡힌 사실: 공고 「${e.title}」${ind.label ? ` · 공장등록 업종 ${ind.label}${ind.code ? `(${ind.code}${ind.industry ? ` ${ind.industry}` : ''})` : ''}` : ''}${ind.product ? ` · 주생산품 ${uniqueList(ind.product)}` : ''}${ind.employees != null ? ` · 종업원 ${ind.employees}명` : ''}${ind.address ? ` · ${ind.address}` : ''}${ind.factories > 1 ? ` · 같은 이름 등록 공장 ${ind.factories}곳` : ''}${identityNote(ind)}${e.watch ? ` · 협력사 명단: ${[e.watch.beat, e.watch.relation, e.watch.evidence].filter(Boolean).join(' · ')}` : ''}${!ind.label && !e.watch ? ' · 공장등록 없음(이름 낱말만)' : ''}`);
    out.push(`   원문: ${e.url ?? e.listUrl}${e.url && e.listUrl ? ` (안 열리면 ${e.listUrl} 에서 법원·사건번호로 검색)` : ''}`);
    out.push('   검증 상태: 법원 공고(절차 단계). 같은 이름의 다른 회사일 수 있음(주소·대표자 대조). 출입처와의 거래·납품 영향은 회사·출입처 확인 필요');
  }
  if (rows.length > limit) out.push(`… 남은 ${rows.length - limit}건`);
  if (!rows.length) out.push('조건에 맞는 출입 업종 회생·파산 공고 없음(위 미확인 법원·업종 조회 대기는 0건 아님).');
  return out;
}

// Notices of the cities and counties where beat plants are (kr-local feed, 새올 고시·공고), shown under kr_official.
async function localSection(ctx, q, days, limit) {
  const doc = await readFeed(ctx, 'kr-local');
  if (!doc) return ['\n[지자체 고시·공고] 결과 없음 — 미확인(평일 06:30·16:20 실행 확인)'];
  if (doc.broken) return ['\n[지자체 고시·공고] 저장 형식 오류 — 미확인'];
  const checks = doc.checks ?? [];
  const bad = checks.filter((c) => c.status !== 'ok');
  const from = new Date(ctx.now.getTime() - days * 86400000).toISOString();
  const all = (doc.items ?? []).filter((x) => !x.routine && String(x.firstSeen) >= from && matches(q, x.city, x.title, x.company, x.dept, x.plants));
  const rank = { A: 0, B: 1, C: 2 };
  const rows = all.filter((x) => q || x.tier !== 'C').sort((a, b) => (rank[a.tier] ?? 3) - (rank[b.tier] ?? 3)
    || String(b.date ?? '').localeCompare(String(a.date ?? '')));
  const out = [`\n[지자체 고시·공고 · 출입처 공장 시·군 ${checks.length}곳 새올 목록 · 처음 본 날 최근 ${days}일] 출입처 관련 ${rows.length}건${all.length - rows.length ? ` · 참고(제철소·산업단지 계획 등) ${all.length - rows.length}건(company 낱말로 보기)` : ''} · 확인 ${String(doc.generatedAt).slice(0, 16)}${ageNote(ctx, doc.generatedAt)}`,
    `원천: 시·군 ${checks.length - bad.length}/${checks.length} 정상${bad.length ? ` · 미확인(0건 아님): ${bad.slice(0, 8).map((c) => `${c.source}(${c.status === 'failed' ? c.error ?? '실패' : '일부'})`).join(', ')}` : ''}`,
    ...(checks.some((c) => c.via) ? [`기자 컴퓨터 브라우저로 읽은 곳(해외 IP 차단): ${checks.filter((c) => c.via).map((c) => `${c.source}(${String(c.via).match(/\d{4}-\d\d-\d\dT\d\d:\d\d/)?.[0]?.replace('T', ' ') ?? '?'})`).join(', ')}`] : []),
    ...(doc.rules ?? []).map((r) => `규칙: ${r}`)];
  for (const x of rows.slice(0, limit)) {
    out.push(`- ${x.isNew ? '[신규] ' : x.baseline ? '[첫 조회 기준선] ' : ''}${x.date ?? '?'} · ${x.city} · ${x.company ?? '출입처 이름 없음'} · ${x.tier}`);
    out.push(`   잡힌 사실: ${x.no ?? ''} 「${x.detail?.title ?? x.title}」 · ${x.dept ?? '담당 부서 미기재'}${x.plants ? ` (이 시·군의 출입처 공장: ${x.plants})` : ''}`);
    if (x.detail?.body) out.push(`   본문 앞부분(상세 페이지): ${x.detail.body}`);
    if ((x.detail?.files ?? []).length) out.push(`   첨부 파일(열지 않음): ${x.detail.files.join(' · ')}`);
    if (x.listTier) out.push(`   등급: 목록 제목으로 ${x.listTier} → 전체 제목으로 ${x.tier}`);
    if (x.detailError) out.push(`   상세 페이지: 못 읽음(${x.detailError}) — 제목만 확인`);
    out.push(`   원문: ${x.url}`);
  }
  if (rows.length > limit) out.push(`… 남은 ${rows.length - limit}건`);
  if (!rows.length) out.push('조건에 맞는 고시·공고 없음(위 미확인 시·군은 0건 아님).');
  return out;
}

// Beat companies' workplaces in the national pension (국민연금 가입 사업장, kr-workforce feed): monthly member counts of own
// sites and construction sites that carry a beat company's name. Shown under kr_official.
const ymLabel = (ym) => (ym ? `${String(ym).slice(0, 4)}-${String(ym).slice(4, 6)}` : '?');
const monthBefore = (ym, n = 1) => { let y = Number(String(ym).slice(0, 4)); let m = Number(String(ym).slice(4, 6)) - n; while (m <= 0) { y -= 1; m += 12; } return `${y}${String(m).padStart(2, '0')}`; };
export async function workforceSection(ctx, q, days, limit) {
  const doc = await readFeed(ctx, 'kr-workforce');
  if (!doc) return ['\n[사업장 인력(국민연금)] 결과 없음 — 미확인(평일 15:50 실행 확인)'];
  if (doc.broken) return ['\n[사업장 인력(국민연금)] 저장 형식 오류 — 미확인'];
  const m = doc.month;
  const out = [`\n[사업장 인력(국민연금 가입 사업장) · 자료 ${ymLabel(m)} · 확인 ${String(doc.generatedAt).slice(0, 16)}${ageNote(ctx, doc.generatedAt)}]`,
    `원천: ${(doc.checks ?? []).map((c) => `${c.source} ${c.status}(${c.returned ?? 0}${c.error ? `, ${c.error}` : ''}${c.note ? `, ${c.note}` : ''}${c.pending ? `, 남은 채우기 ${c.pending}곳` : ''})`).join(' · ')}`,
    ...(doc.rules ?? []).map((r) => `규칙: ${r}`)];
  const fmt = (n) => (n == null ? '?' : Number(n).toLocaleString('en-US'));
  const rows = (doc.sites ?? []).filter((s) => matches(q, s.company, s.name, s.addr, s.industry)).map((s) => {
    const h = s.history ?? {};
    const cur = h[m]?.members; const prev = h[monthBefore(m)]?.members; const year = h[monthBefore(m, 12)]?.members;
    return { s, cur, prev, year, d: cur != null && prev ? cur - prev : null, pct: cur != null && prev ? ((cur - prev) / prev) * 100 : null,
      ypct: cur != null && year ? ((cur - year) / year) * 100 : null };
  });
  rows.sort((a, b) => (a.pct ?? 0) - (b.pct ?? 0) || (b.cur ?? 0) - (a.cur ?? 0));
  const months = (s) => Object.keys(s.history ?? {}).length;
  out.push(`- 자사 사업장 ${rows.length}곳(지난달 비교 가능 ${rows.filter((r) => r.d != null).length}곳 · 1년 전 비교 가능 ${rows.filter((r) => r.ypct != null).length}곳) — 지난달 대비 많이 줄어든 순`);
  for (const r of rows.slice(0, limit)) {
    const h = r.s.history?.[m] ?? {};
    out.push(`  ${r.s.company} · ${r.s.name}${r.s.status === '2' ? ' · 탈퇴' : ''} · 가입자 ${fmt(r.cur)}명`
      + `${r.d != null ? ` (지난달 ${r.d >= 0 ? '+' : ''}${fmt(r.d)}, ${r.pct >= 0 ? '+' : ''}${r.pct.toFixed(1)}%)` : ' (지난달 미수집)'}`
      + `${r.ypct != null ? ` · 1년 전 ${fmt(r.year)}명 대비 ${r.ypct >= 0 ? '+' : ''}${r.ypct.toFixed(1)}%` : ''}`
      + `${h.acq != null ? ` · 그달 취득 ${h.acq}·상실 ${h.loss}` : ''} · ${months(r.s)}개월 보관`);
  }
  if (rows.length > limit) out.push(`  … 남은 ${rows.length - limit}곳(company 낱말로 좁히기)`);
  const from = new Date(ctx.now.getTime() - days * 86400000).toISOString();
  const ev = (doc.events ?? []).filter((e) => String(e.detectedAt) >= from && matches(q, e.company, e.text));
  out.push(`- 감지된 변화 · 최근 ${days}일 ${ev.length}건`);
  for (const e of ev.slice(0, limit)) out.push(`  ${e.tier} · ${String(e.detectedAt).slice(0, 10)} · ${e.kind} · ${e.company}: ${e.text}`);
  const pj = (doc.projects ?? []).filter((p) => !p.baseline && matches(q, p.company, p.title, (p.names ?? []).join(' ')));
  const base = (doc.projects ?? []).filter((p) => p.baseline && matches(q, p.company, p.title, (p.names ?? []).join(' ')));
  out.push(`- 출입처 이름이 든 공사(시공사 현장 사업장을 공사 이름으로 묶음): 새로 잡힌 ${pj.length}건 · 첫 조회 기준선 ${base.length}건(투자 낱말 ${base.filter((p) => p.tier === 'A').length})`);
  const bySites = (a, b) => (b.sites ?? 1) - (a.sites ?? 1);
  for (const p of [...pj.sort(bySites), ...base.filter((x) => x.tier === 'A').sort(bySites)].slice(0, limit)) {
    out.push(`  ${p.baseline ? '[기준선] ' : ''}${p.tier} · ${p.company} · 「${p.title}」 · 현장 ${p.sites ?? 1}곳 · ${ymLabel(p.month)} 자료${p.adptDt ? ` · 첫 현장 적용 ${p.adptDt}` : ''}${p.members != null ? ` · 가입자 ${p.members}명` : ''}`);
  }
  out.push('   검증 상태: 국민연금 공개 자료(자동). 가입자 수≠전체 직원 수, 본사 일괄 신고는 공장별 수치 아님. 증감 이유·공사 규모는 회사 확인 전 미확인');
  return out;
}

// Stack monitoring of beat plants (kr-stacks feed, 굴뚝 자동측정 TMS): which plants have stacks that stopped, and recent events.
export async function stacksSection(ctx, q, days, limit) {
  const doc = await readFeed(ctx, 'kr-stacks');
  if (!doc) return ['\n[굴뚝 측정(공장 가동 신호)] 결과 없음 — 미확인(3시간마다 실행 확인)'];
  if (doc.broken) return ['\n[굴뚝 측정(공장 가동 신호)] 저장 형식 오류 — 미확인'];
  const sites = (doc.sites ?? []).filter((s) => matches(q, s.company, s.name, s.area));
  const stacks = sites.reduce((n, s) => n + Object.keys(s.stacks ?? {}).length, 0);
  const obsOf = (s) => Math.max(0, ...Object.values(s.stacks ?? {}).map((st) => (st.obs ?? []).length));
  const out = [`\n[굴뚝 측정(공장 가동 신호) · 출입처 사업장 ${sites.length}곳 · 배출구 ${stacks}개 · 확인 ${String(doc.generatedAt).slice(0, 16)}${ageNote(ctx, doc.generatedAt)}]`,
    `원천: ${(doc.checks ?? []).map((c) => `${c.source} ${c.status}(${c.returned ?? 0}${c.terms ? `, 검색 ${c.terms}` : ''}${c.error ? `, ${c.error}` : ''})`).join(' · ')} · 기준선 ${String(doc.baselineSince ?? '').slice(0, 10)}`,
    ...(doc.rules ?? []).map((r) => `규칙: ${r}`)];
  const down = sites.filter((s) => (s.stopped ?? []).length).sort((a, b) => (b.stopped.length / Math.max(1, b.meaningful ?? 1)) - (a.stopped.length / Math.max(1, a.meaningful ?? 1)));
  out.push(`- 지금 멈춤으로 판단한 배출구가 있는 사업장 ${down.length}곳(관측 6번 전 사업장은 판단 안 함)`);
  for (const s of down.slice(0, limit)) {
    out.push(`  ${s.company} · ${s.name}(${s.area ?? '지역 미상'}) · 평소 움직이던 배출구 ${s.meaningful ?? '?'}개 중 멈춤 ${s.stopped.length}개: ${s.stopped.slice(0, 8).map((c) => `${c}번(측정 ${s.stacks?.[c]?.lastDt ?? '?'})`).join(', ')}`);
  }
  const young = sites.filter((s) => obsOf(s) < 6).length;
  if (young) out.push(`  (관측이 아직 6번이 안 된 사업장 ${young}곳 — 판단 전)`);
  const KO = { tsp: '먼지', sox: '황산화물', nox: '질소산화물', hcl: '염화수소', hf: '불화수소', nh3: '암모니아', co: '일산화탄소' };
  const over = sites.flatMap((s) => (s.exceedLog ?? []).map((x) => ({ ...x, site: s.name, company: s.company }))).sort((a, b) => String(b.at).localeCompare(String(a.at)));
  out.push(`- 배출허용기준 넘은 측정값(이 감시가 본 것, 사업장마다 최근 20건) ${over.length}건${over.length ? '' : ' — 없음'}`);
  for (const x of over.slice(0, limit)) out.push(`  ${x.at} · ${x.company} · ${x.site} 배출구 ${x.stack}번 ${KO[x.pollutant] ?? x.pollutant} ${x.value}(기준 ${x.limit})`);
  const from = new Date(ctx.now.getTime() - days * 86400000).toISOString();
  const ev = (doc.events ?? []).filter((e) => String(e.detectedAt) >= from && matches(q, e.company, e.site, e.text));
  out.push(`- 감지된 변화 · 최근 ${days}일 ${ev.length}건`);
  for (const e of ev.slice(0, limit)) out.push(`  ${e.tier} · ${String(e.detectedAt).slice(0, 16)} · ${e.kind} · ${e.company}: ${e.text}`);
  out.push('   검증 상태: 한국환경공단 굴뚝 자동측정 실시간 값(자동)을 이 감시가 쌓은 이력. 배출구 이름·설비 종류 없음, 값 하락은 정지·정비·점검 중 무엇인지 모름 — 회사 확인 전 미확인. 기준 초과 값은 확정 전 실시간 값(측정기 점검·교정 가능) — 초과 판정·처분은 환경공단·지자체 확인');
  return out;
}

export async function krOfficial(ctx, args) {
  const section = ['factory', 'gazette', 'law', 'insolvency', 'building', 'local', 'workforce', 'stacks'].includes(args.section) ? args.section : null;
  const q = String(args.company ?? '').trim();
  if (section === 'local') return textResult((await localSection(ctx, q, clampInt(args.days, 1, 120, 30), clampInt(args.limit, 1, 80, 20))).join('\n').trim());
  if (section === 'workforce') return textResult((await workforceSection(ctx, q, clampInt(args.days, 1, 120, 45), clampInt(args.limit, 1, 80, 20))).join('\n').trim());
  if (section === 'stacks') return textResult((await stacksSection(ctx, q, clampInt(args.days, 1, 60, 14), clampInt(args.limit, 1, 80, 20))).join('\n').trim());
  const insolvency = !section || section === 'insolvency'
    ? await insolvencySection(ctx, q, clampInt(args.days, 1, 120, 30), clampInt(args.limit, 1, 80, 20)) : [];
  if (section === 'insolvency') return textResult(insolvency.join('\n').trim());
  const building = !section || section === 'building'
    ? await buildingSection(ctx, q, clampInt(args.days, 1, 400, 90), clampInt(args.limit, 1, 80, 20)) : [];
  if (section === 'building') return textResult(building.join('\n').trim());
  insolvency.push(...building);
  if (!section) insolvency.push(...await localSection(ctx, q, clampInt(args.days, 1, 120, 30), clampInt(args.limit, 1, 80, 20)));
  if (!section) insolvency.push(...await workforceSection(ctx, q, clampInt(args.days, 1, 120, 45), clampInt(args.limit, 1, 80, 10)));
  if (!section) insolvency.push(...await stacksSection(ctx, q, clampInt(args.days, 1, 60, 14), clampInt(args.limit, 1, 80, 10)));
  const doc = await readFeed(ctx, 'kr-official');
  if (!doc) return insolvency.length ? textResult([missing('공장등록·관보 입법예고', '평일 08:10').content[0].text, ...insolvency].join('\n'), true) : missing('공장등록·관보 입법예고', '평일 08:10');
  if (doc.broken) return textResult(['저장된 국내 공식 원천 결과 형식 오류 — 미확인.', ...insolvency].join('\n'), true);
  const days = clampInt(args.days, 1, 120, 30);
  const limit = clampInt(args.limit, 1, 80, 20);
  const checks = (doc.checks ?? []).filter((c) => !String(c.source).startsWith('공장등록 이름 규칙'));
  const failed = checks.filter((c) => c.status !== 'ok');
  const out = [`국내 공식 원천(공장등록·관보 입법예고) · 확인 ${String(doc.generatedAt).slice(0, 16)}${ageNote(ctx, doc.generatedAt)}`,
    `질의 ${checks.length - failed.length}/${checks.length} 정상${failed.length ? ` · 미확인(0건 아님): ${failed.slice(0, 6).map((c) => `${c.source}(${c.error})`).join(', ')}` : ''}`,
    ...(doc.rules ?? []).map((r) => `규칙: ${r}`)];
  if (!section || section === 'factory') {
    const from = new Date(ctx.now.getTime() - days * 86400000).toISOString();
    const ev = (doc.events ?? []).filter((e) => new Date(e.detectedAt).toISOString() >= from && matches(q, e.company, e.name, e.text));
    out.push(`\n[공장등록 변화 · 감지일 기준 최근 ${days}일] ${ev.length}건`);
    out.push(`(기준선 ${String(doc.baselineSince ?? doc.generatedAt).slice(0, 10)} 이후 감지된 새 공장·고용·주생산품·업종·주소 변화만 센다. 등록일로 본 새 공장은 아래 '최근 120일 등록 공장'.)`);
    for (const e of ev.slice(0, limit)) {
      out.push(`- ${String(e.detectedAt).slice(0, 10)} · ${e.company} · ${e.kind}${e.tier ? ` · ${e.tier}` : ''}`);
      out.push(`   잡힌 사실: ${factoryEventText(doc, e)}`);
    }
    if (!ev.length) out.push('이 기간 감지된 변화 없음(조회 실패 회사는 미확인).');
    const facs = (doc.factories ?? []).filter((f) => matches(q, f.company, f.cmpnyNm, f.rnAdres, f.mainProductCn));
    const recent = facs.filter((f) => (f.tags ?? []).some((t) => t.startsWith('[최근 등록')));
    out.push(`\n[최근 120일 등록 공장 · 등록일 기준] ${recent.length}곳 (출입처 공장 전체 ${facs.length}곳${q ? ', 낱말 거름' : ''})`);
    for (const f of recent.slice(0, limit)) {
      out.push(`- ${f.registeredOn} · ${f.company} · ${f.cmpnyNm} · ${f.rnAdres}`);
      out.push(`   주생산품 ${uniqueList(f.mainProductCn) || '미기재'} · 업종 ${f.indutyNm || '미기재'} · 고용 ${f.employees ?? '미기재'}명${f.irsttNm ? ` · ${f.irsttNm}` : ''}${f.nameCheck ? ` · ⚠ ${f.nameCheck}` : ''}`);
    }
    if (args.show_all === true || args.show_all === 'true') {
      out.push('\n[출입처 공장 목록]');
      for (const f of facs.slice(0, 200)) out.push(`- ${f.company} · ${f.cmpnyNm} · ${f.rnAdres} · 고용 ${f.employees ?? '?'} · 등록 ${f.registeredOn ?? '?'}${f.stale ? ' · ⚠ 이번 조회 실패, 직전 값' : ''}${f.nameCheck ? ` · ⚠ ${f.nameCheck}` : ''}`);
    }
    out.push('   검증 상태: 지자체 공장등록 신고값(자동). 가동·투자 규모는 회사·지자체 확인 필요');
  }
  if (!section || section === 'gazette') {
    const gz = (doc.gazette ?? []).filter((g) => matches(q, g.title, g.org, (g.teams ?? []).join(' '), g.summary));
    out.push(`\n[관보 입법예고 · 출입처 업종 관련] ${gz.length}건`);
    for (const g of gz.slice(0, limit)) {
      out.push(`- ${g.isNew ? '[신규] ' : ''}${g.date} · ${g.org} · ${(g.teams ?? []).join('·')}${g.corrected ? ' · 정정' : ''}`);
      out.push(`   잡힌 사실: ${g.title}`);
      if (g.summary) out.push(`   개정이유 첫머리: ${g.summary.slice(0, 200)}`);
      out.push(`   원문: ${g.url ?? '링크 없음'}`);
    }
    out.push('   검증 상태: 관보 게재 목록(자동). 같은 날 보도자료가 나왔는지 news_check로 확인');
  }
  if (!section || section === 'law') out.push(...lawRulesSection(doc.lawRules, q, args.limit ? limit : 15, args.show_all === true || args.show_all === 'true'));
  if (!section) {
    const eia = (doc.eia ?? []).filter((x) => matches(q, x.company, x.name, x.category));
    out.push(`\n[환경영향평가 · 사업명에 출입처 이름 · 새 단계] ${eia.length}건`);
    for (const x of eia.slice(0, limit)) out.push(`- ${x.isNew ? '[신규] ' : ''}${x.received} 접수 · ${x.company} · ${x.kind} ${x.stage}\n   ${x.name} · ${x.category}${x.completed ? ` · 완료 ${x.completed}` : ''} · 사업코드 ${x.code}`);
    if (!eia.length) out.push('새 단계 없음(첫 실행은 기준선, 조회 실패면 미확인).');
  }
  out.push(...insolvency);
  out.push('\n다음: 새 공장·변경은 회사·지자체에 가동 시점·투자액·인력 확인 → news_check. 입법예고는 원문(관보 PDF)에서 시행일·대상 확인. 법제처 확정 발령은 law.go.kr 원문의 신구조문·개정이유로 무엇이 바뀌었는지 확인. 환경영향평가는 EIASS에서 사업코드로 평가서 원문(규모·일정) 확인.'
    + (insolvency.length ? ' 회생·파산은 공고 원문(관리인·신청일)과 공장 주소 대조 → 출입처 DART 사업보고서 주요 매입처·협력사 확인(dart_find_text) → 회사·출입처에 거래 규모·대체 공급 확인 → news_check.' : ''));
  return textResult(out.join('\n'));
}

// 법제처 확정 발령(law_rules_watch.py): 출입 업종 행정규칙·법령의 새 일련번호와 법제처 법령해석례. 입법예고(관보)의 다음 단계.
export function lawRulesSection(lr, q = '', limit = 15, showAll = false) {
  if (!lr) return ['\n[법제처 확정 발령 · 행정규칙·법령·해석례] 아직 수집 전 — 미확인'];
  const rank = { B: 0, C: 1 };
  // 같은 발령번호로 단지·품목마다 따로 올라온 고시는 첫 항목에 '같은 번호 N건'으로 묶는다(수집기 grouped·siblings)
  const all = (lr.items ?? []).filter((x) => !x.grouped && matches(q, x.title, x.org, x.type, (x.teams ?? []).join(' ')));
  const shown = (showAll ? all : all.filter((x) => x.tier === 'B'))
    .sort((a, b) => Number(b.isNew) - Number(a.isNew) || String(b.date).localeCompare(String(a.date)) || (rank[a.tier] ?? 2) - (rank[b.tier] ?? 2));
  const out = [`\n[법제처 확정 발령 · 출입 업종 행정규칙(고시·훈령·예규)·법령·법령해석례 · 확인 ${String(lr.checkedAt).slice(0, 16)}${lr.stale ? ' · ⚠ 이번 조회 실패, 직전 목록' : ''} · 기준선 ${String(lr.baselineSince ?? '').slice(0, 10)}] `
    + `B ${all.filter((x) => x.tier === 'B').length}건${showAll ? '' : ` · C ${all.length - shown.length}건 숨김(show_all=true)`} · 최근 90일 안에 처음 본 것`];
  for (const x of shown.slice(0, limit)) {
    const when = x.kind === '법령해석례' ? `회신 ${x.date}` : `${x.kind === '법령' ? '공포' : '발령'} ${x.date}${x.effective && x.effective !== x.date ? ` · 시행 ${x.effective}` : ''}`;
    out.push(`- ${x.isNew ? '[신규] ' : ''}${x.tier} · ${when} · ${x.kind}${x.type ? `(${x.type})` : ''}${x.change ? ` ${x.change}` : ''} · ${x.org}${x.asker ? ` ← 질의 ${x.asker}` : ''} · ${(x.teams ?? []).join('·')}`);
    out.push(`   잡힌 사실: ${x.title}${x.no ? ` (${x.kind === '법령해석례' ? '안건' : x.kind === '법령' ? '공포' : '발령'}번호 ${x.no})` : ''}${x.siblings ? ` 외 같은 번호 ${x.siblings}건` : ''}`);
    out.push(`   원문: ${x.url}`);
  }
  if (shown.length > limit) out.push(`… 남은 ${shown.length - limit}건`);
  if (!shown.length) out.push('이 기간 새로 본 출입 업종 확정 발령 없음(첫 실행은 기준선, 조회 실패면 미확인).');
  out.push('   검증 상태: 법제처 현행 목록의 제목·부처·발령일(자동). 무엇이 바뀌었는지는 원문 신구조문으로 확인. 발령일과 법제처 반영일은 며칠 다를 수 있다. 같은 날 보도자료 여부는 news_check');
  return out;
}

const eok = (v) => (Number.isFinite(v) && v > 0 ? `${v.toLocaleString('en-US')}원(약 ${(v / 1e8).toLocaleString('en-US', { maximumFractionDigits: v >= 1e10 ? 0 : 1 })}억원)` : '미기재');
const signed = (v) => (v === null || v === undefined ? '?' : `${v > 0 ? '+' : ''}${v}%`);
const ymd8 = (s) => (/^\d{8}/.test(String(s ?? '')) ? `${String(s).slice(0, 4)}-${String(s).slice(4, 6)}-${String(s).slice(6, 8)}` : String(s ?? ''));

// 국내 신호: 공정위 의결서(출입처 이름) · 한전 전자입찰(전력기기·전선) · 원자재 가격(KOMIS)
// 전기위원회 발전사업 허가·원안위 안건(kr-energy feed), shown under kr_signals (no new connector tool).
async function energySection(ctx, q, days, limit) {
  const doc = await readFeed(ctx, 'kr-energy');
  if (!doc) return ['\n[전기위원회·원안위] 결과 없음 — 미확인(평일 15:40·18:10 실행 확인)'];
  if (doc.broken) return ['\n[전기위원회·원안위] 저장 형식 오류 — 미확인'];
  const from = new Date(ctx.now.getTime() + 9 * 3600000 - days * 86400000).toISOString().slice(0, 10);
  const all = (doc.items ?? []).filter((x) => String(x.held ?? x.posted ?? x.firstSeen).slice(0, 10) >= from
    && matches(q, x.title, x.company, x.meeting, x.kind, x.source));
  const rank = { A: 0, B: 1, C: 2 };
  const rows = all.filter((x) => q || x.tier !== 'C').sort((a, b) => (rank[a.tier] ?? 3) - (rank[b.tier] ?? 3)
    || String(b.held ?? b.posted ?? '').localeCompare(String(a.held ?? a.posted ?? '')));
  const minor = all.length - rows.length;
  const checks = doc.checks ?? [];
  const out = [`\n[전기위원회·원안위 · 최근 ${days}일] 출입처·주요 ${rows.length}건${minor ? ` · 기타 ${minor}건(company 낱말로 보기)` : ''} · 확인 ${String(doc.generatedAt).slice(0, 16)}${ageNote(ctx, doc.generatedAt)}`,
    `원천: ${checks.map((c) => `${c.source} ${c.status}${c.error ? `(${c.error})` : c.note ? `(${c.note})` : ''}`).join(' · ')}`,
    ...(doc.rules ?? []).map((r) => `규칙: ${r}`)];
  for (const x of rows.slice(0, limit)) {
    const nssc = x.source === '원자력안전위원회';
    out.push(`- ${x.isNew ? '[신규] ' : ''}${x.held ?? x.posted ?? '날짜 미상'} · ${x.source}${x.meeting ? ` ${x.meeting}` : ''} · ${x.kind}${x.company ? ` · ${x.company}` : ''}`);
    out.push(`   잡힌 사실: ${x.title}${nssc ? (x.result ? ` → 결과 ${x.result}` : ' (상정 — 의결 결과 전)') : ''}${x.ledger ? ` · ${x.ledger}` : ''}`);
    out.push(`   원문: ${x.url ?? '링크 없음'}`);
  }
  if (rows.length > limit) out.push(`… 남은 ${rows.length - limit}건`);
  if (!rows.length) out.push('조건에 맞는 항목 없음(위 실패 원천은 0건 아님).');
  return out;
}

export async function krSignals(ctx, args) {
  const energyQ = String(args.company ?? '').trim();
  const energy = !args.section || args.section === 'energy'
    ? await energySection(ctx, energyQ, clampInt(args.days, 1, 365, 60), clampInt(args.limit, 1, 60, 15)) : [];
  if (args.section === 'energy') return textResult(energy.join('\n').trim());
  const doc = await readFeed(ctx, 'kr-signals');
  if (!doc) return energy.length ? textResult([missing('공정위 의결서·한전 입찰·원자재 가격', '평일 08:30·15:20').content[0].text, ...energy].join('\n'), true) : missing('공정위 의결서·한전 입찰·원자재 가격', '평일 08:30·15:20');
  if (doc.broken) return textResult(['저장된 국내 신호 결과 형식 오류 — 미확인.', ...energy].join('\n'), true);
  const section = ['ftc', 'kepco', 'motir', 'price'].includes(args.section) ? args.section : null;
  const q = String(args.company ?? '').trim();
  const days = clampInt(args.days, 1, 365, 60);
  const limit = clampInt(args.limit, 1, 60, 15);
  const checks = doc.checks ?? [];
  const bad = checks.filter((c) => c.status !== 'ok');
  const out = [`국내 신호(공정위 의결서·한전 전자입찰·원자재 가격) · 확인 ${String(doc.generatedAt).slice(0, 16)}${ageNote(ctx, doc.generatedAt)}`,
    `질의 ${checks.length - bad.length}/${checks.length} 정상${bad.length ? ` · 미확인(0건 아님): ${bad.slice(0, 6).map((c) => `${c.source}(${c.error ?? c.status}${c.pending ? `, 전문 대기 ${c.pending}건` : ''})`).join(', ')}` : ''}`,
    ...(doc.rules ?? []).map((r) => `규칙: ${r}`)];
  if (!section || section === 'ftc') {
    const from = new Date(ctx.now.getTime() + 9 * 3600000 - days * 86400000).toISOString().slice(0, 10);
    const rows = (doc.decisions ?? []).filter((d) => String(d.decidedOn ?? '') >= from || String(d.fileDate ?? '') >= from)
      .filter((d) => matches(q, d.name, ...(d.mentions ?? []).map((m) => m.company)))
      .filter((d) => args.include_mentions === true || args.include_mentions === 'true' || (d.mentions ?? []).some((m) => m.role !== '본문 언급' && !m.related));
    const f = checks.find((c) => c.source === '공정위 의결서');
    out.push(`\n[공정위 의결서 · 의결일 또는 파일 등록 최근 ${days}일 · 출입처가 피심인·발주처·사건명에 있는 것] ${rows.length}건${f ? ` (목록 ${f.listed ?? '?'}건, 전문 읽음 ${f.read ?? 0}·대기 ${f.pending ?? 0})` : ''}`);
    out.push('(본문에만 이름이 나오는 의결서는 include_mentions=true로 본다 — 시장점유율 표·경쟁사 언급이 대부분)');
    for (const d of rows.slice(0, limit)) {
      const roles = (d.mentions ?? []).map((m) => `${m.company} ${m.role}${m.related ? '(관련 기업)' : ''}${(m.orderAmounts ?? []).length ? ` · 주문 금액 ${m.orderAmounts.join(', ')}` : ''}`).join(' / ');
      out.push(`- ${d.isNew ? '[신규] ' : ''}의결 ${d.decidedOn} · 파일 등록 ${d.fileDate ?? '?'} · ${d.action}${(d.flags ?? []).length ? ` · ${d.flags.join('·')}` : ''}`);
      out.push(`   사건명: ${d.name}`);
      out.push(`   출입처: ${roles}`);
      const resp = (d.mentions ?? []).find((m) => m.role === '피심인');
      if (resp?.snippet) out.push(`   원문 발췌: ${resp.snippet.slice(0, 220)}`);
      else if (d.orderExcerpt && (d.mentions ?? []).some((m) => m.role !== '본문 언급')) out.push(`   주문 첫머리: ${d.orderExcerpt.slice(0, 200)}`);
      if (d.note) out.push(`   ⚠ ${d.note}`);
      out.push(`   원문: ${d.url} · ${d.decisionNo} · 사건번호 ${(d.caseNos ?? []).join(', ')}`);
    }
    if (!rows.length) out.push('없음(전문 대기·목록 실패분은 미확인)');
    out.push('   검증 상태: 공정위 공개 의결서(자동 대조). 보도자료·선행 기사 여부는 news_check, 금액·감경은 원문에서 확인');
  }
  if (!section || section === 'kepco') {
    const k = checks.find((c) => c.source === '한전 전자입찰');
    if (k?.status === 'unset') out.push('\n[한전 전자입찰] 미설정 — GitHub Secrets에 KEPCO_API_KEY(전력데이터개방포털 40자리 키) 필요. 0건이 아니라 미확인.');
    else {
      const rows = (doc.kepco ?? []).filter((x) => matches(q, x.name, x.company, x.place))
        .sort((a, b) => (b.price ?? 0) - (a.price ?? 0) || String(b.noticeDate).localeCompare(String(a.noticeDate)));
      out.push(`\n[한전 전자입찰 · 전력기기·전선 자재구매(+HVDC·765kV급 공사) · 추정가격 큰 순] ${rows.length}건`);
      for (const x of rows.slice(0, limit)) {
        out.push(`- ${x.isNew ? '[신규] ' : ''}공고 ${ymd8(x.noticeDate)} · ${x.company} · ${x.state}${x.big ? ' · 대형' : ''} · 추정가격 ${eok(x.price)}`);
        out.push(`   입찰건명: ${x.name}${x.closeAt ? ` · 신청 마감 ${ymd8(x.closeAt)}` : ''}`);
        out.push(`   공고번호 ${x.no}${(x.files ?? []).length ? ` · 첨부 ${x.files.slice(0, 2).join(', ')}` : ''} (원문: 한전 전자조달 srm.kepco.net에서 공고번호로)`);
      }
      if (!rows.length) out.push('없음');
      out.push('   검증 상태: 발주 공고(추정가격). 낙찰사·계약금액이 아니다');
    }
  }
  if (!section || section === 'motir') {
    const from = new Date(ctx.now.getTime() + 9 * 3600000 - Math.min(days, 60) * 86400000).toISOString().slice(0, 10);
    const rows = (doc.motir ?? []).filter((x) => String(x.date ?? '') >= from && matches(q, x.title, x.dept, ...(x.companies ?? [])));
    out.push(`\n[산업통상부 보도·참고자료 · 출입처 업종 낱말·출입처 이름 · 최근 ${Math.min(days, 60)}일] ${rows.length}건`);
    for (const x of rows.slice(0, limit)) {
      out.push(`- ${x.isNew ? '[신규] ' : ''}${x.date} · ${x.dept} · ${x.kind}${x.embargo ? ` · 엠바고(${x.embargo})` : ''}`);
      out.push(`   제목: ${x.title}${(x.companies ?? []).length ? ` · 출입처 이름: ${x.companies.join('·')}` : ''}`);
      const t = x.trade;
      if (t?.items) {
        const parts = Object.entries(t.items).map(([k, v]) => `${k} ${v.value}억달러(${v.yoy}%)`);
        out.push(`   ${t.period} 수출${t.exports ? ` ${t.exports.value}억달러(${t.exports.yoy}%)` : ''} · 출입처 품목: ${parts.join(' · ') || '표 해석 실패 — 원문 확인'}${t.tableError ? ` (⚠ ${t.tableError})` : ''}`);
      } else if (t?.error) out.push(`   ⚠ 본문 조회 실패(${t.error}) — 원문 확인`);
      out.push(`   원문: ${x.url}`);
    }
    if (!rows.length) out.push('없음');
    out.push('   검증 상태: 정부 공개 발표. 단독 근거가 아니다 — 같은 날 기사 확인(news_check), 엠바고 준수');
  }
  if (!section || section === 'price') {
    const rows = (doc.prices ?? []).filter((p) => matches(q, p.name, p.id, ...(p.beats ?? [])));
    out.push(`\n[원자재 가격 · KOMIS 게시값 · 같은 기준·단위만 비교] ${rows.length}종`);
    for (const p of rows) {
      const s = p.summary ?? {};
      out.push(`- ${p.name} ${p.basis}(${p.unit}) · ${s.date ?? '?'} ${Number(s.price ?? 0).toLocaleString('en-US')}${p.stale ? ' · ⚠ 이번 조회 실패, 직전 값' : ''}`);
      out.push(`   전일 ${signed(s.day)} · 1주 ${signed(s.week)} · 한 달(${s.monthFrom ?? '?'}~) ${signed(s.month)} · 연초(${s.ytdFrom ?? '?'}~) ${signed(s.ytd)}${s.stock ? ` · LME 재고 ${Number(s.stock).toLocaleString('en-US')}(한 달 ${signed(s.stockMonth)})` : ''}`);
      if (s.high && s.low) out.push(`   조회 범위(${(s.span ?? []).join('~')}) 최고 ${s.high.date} ${Number(s.high.price).toLocaleString('en-US')} · 최저 ${s.low.date} ${Number(s.low.price).toLocaleString('en-US')}${p.sinceNote ? ` · ${p.sinceNote}` : ''}`);
      if ((p.signals ?? []).length) out.push(`   신호: ${p.signals.map((x) => x.text).join(' / ')}`);
      out.push(`   관련 출입처: ${(p.beats ?? []).join('·')}`);
    }
    out.push('   검증 상태: KOMIS(한국광해광업공단) 게시 가격. 기사에 쓸 땐 같은 기준(LME CASH 등)·날짜를 그대로, "역대"는 쓰지 않는다');
  }
  out.push(...energy);
  out.push('\n다음: 공정위는 원문(개방문서)에서 피심인·주문·과징금 확인 → news_check(사건명 낱말·회사명) → 회사 확인. 가격은 출입처 실적·판가 영향은 회사·IR로 확인.'
    + (energy.length ? ' 전기위원회 허가는 개최결과 PDF·허가대장에서 사업자·용량 확인 → 사업자·지자체 확인. 원안위는 안건 원문(PDF)과 결과 확인.' : ''));
  return textResult(out.join('\n'));
}

const pct2 = (v) => (v === null || v === undefined ? '?' : `${v > 0 ? '+' : ''}${Number(v).toFixed(1)}%`);
const fmtN = (v) => (v === null || v === undefined ? '?' : Number(v).toLocaleString('en-US', { maximumFractionDigits: 2 }));

// 국내 월간 통계: ECOS 품목별 물가지수 · KOSIS(철강협회 생산·광공업동향) · KAIDA 수입 승용차 브랜드별 신규등록
export async function krStats(ctx, args) {
  const doc = await readFeed(ctx, 'kr-stats');
  if (!doc) return missing('국내 월간 통계(ECOS·KOSIS·KAIDA)', '평일 07:30');
  if (doc.broken) return textResult('저장된 국내 월간 통계 형식 오류 — 미확인.', true);
  const section = ['kaida', 'price', 'production', 'us_imports', 'carsales'].includes(args.section) ? args.section : null;
  const q = String(args.company ?? '').trim();
  const limit = clampInt(args.limit, 1, 60, 12);
  const onlySignals = !(args.show_all === true || args.show_all === 'true');
  const checks = doc.checks ?? [];
  const bad = checks.filter((c) => c.status !== 'ok');
  const out = [`국내 월간 통계(한국은행 ECOS 물가·KOSIS 생산·KAIDA 수입차·현대차·기아 판매) · 확인 ${String(doc.generatedAt).slice(0, 16)}${ageNote(ctx, doc.generatedAt, 60)}`,
    `질의 ${checks.length - bad.length}/${checks.length} 정상${bad.length ? ` · 미확인(0건 아님): ${bad.map((c) => `${c.source}(${c.error ?? c.status})`).join(', ')}` : ''}`,
    ...(doc.rules ?? []).map((r) => `규칙: ${r}`)];
  if (!section || section === 'kaida') {
    const k = doc.kaida ?? {};
    const rows = (k.brands ?? []).filter((b) => matches(q, b.brand, b.beat));
    out.push(`\n[수입 승용차 신규등록 · KAIDA ${k.period ?? '?'} · 전체 ${fmtN(k.total)}대 · 출입처와 주요 브랜드]`);
    for (const b of rows.slice(0, limit)) {
      out.push(`- ${b.rank}위 ${b.brand}${b.beat ? `(${b.beat})` : ''} ${fmtN(b.units)}대 · 점유 ${fmtN(b.share)}% · 직전 달 ${b.prevRank ?? '?'}위 · 전년 같은 달 대비 ${pct2(b.yoy)}`);
    }
    const sig = (k.signals ?? []).filter((s) => matches(q, s.brand, s.text));
    if (sig.length) out.push(`   출입처 신호: ${sig.map((s) => s.text).join(' / ')}`);
    out.push('   검증 상태: KAIDA 회원사 신규등록(월 1회 공개). 같은 날 협회 보도자료가 나온다 — 순위·기록은 보도 대조 필수');
  }
  const showSeries = (kind, title) => {
    const rows = (doc.series ?? []).filter((s) => s.kind === kind && matches(q, s.label, ...(s.beats ?? [])))
      .filter((s) => !onlySignals || (s.signals ?? []).length);
    out.push(`\n[${title}] ${rows.length}개 계열${onlySignals ? '(신호 있는 것만, show_all=true로 전부)' : ''}`);
    for (const s of rows.slice(0, limit)) {
      const m = s.summary ?? {};
      out.push(`- ${s.label} · ${m.period ?? '?'} ${fmtN(m.value)}(${s.unit}) · 전월 ${pct2(m.mom)} · 전년 같은 달 ${pct2(m.yoy)}${s.stale ? ' · ⚠ 이번 조회 실패, 직전 값' : ''}`);
      if (m.high && m.low) out.push(`   조회 범위(${(m.span ?? []).join('~')}) 최고 ${m.high.p} ${fmtN(m.high.v)} · 최저 ${m.low.p} ${fmtN(m.low.v)}`);
      if ((s.signals ?? []).length) out.push(`   신호: ${s.signals.map((x) => x.text).join(' / ')}`);
      out.push(`   관련 출입처: ${(s.beats ?? []).join('·')} · 원표: ${s.source}${s.officialName ? ` 「${s.officialName}」` : ''}`);
    }
    if (!rows.length) out.push('없음');
  };
  if (!section || section === 'price') showSeries('price', '물가지수 · 한국은행 ECOS 품목별(생산자·수출·수입물가)');
  if (!section || section === 'production') showSeries('volume', '생산·재고 · KOSIS(철강협회·광공업동향)');
  if (!section || section === 'us_imports') showSeries('trade', '미국 수입(한국산) · US Census 품목별 월간 일반수입액');
  if (!section || section === 'carsales') {
    const cs = doc.carSales ?? {};
    const name = { 'hmc:model': '현대차 모델별(국내 판매·국내 공장 수출)', 'hmc:plant': '현대차 해외 공장별', 'kia:model': '기아 모델별(국내 판매·국내 공장 수출)', 'kia:plant': '기아 해외 공장별 출고' };
    const files = Object.values(cs.files ?? {});
    // 최신 달을 실은 파일(올해 파일)의 최종수정 — Last-Modified 문자열은 요일로 시작해 정렬로 고르면 안 된다
    const lm = (key) => files.find((f) => `${f.maker}:${f.kind}` === key && f.latest === (cs.latest ?? {})[key])?.lastModified;
    out.push(`\n[완성차 모델별·공장별 판매 · 현대차·기아 IR 엑셀] 최신 ${Object.entries(cs.latest ?? {}).map(([k, v]) => `${name[k] ?? k} ${v}`).join(' · ') || '없음(아직 수집 전)'}`);
    for (const r of cs.rules ?? []) out.push(`   규칙: ${r}`);
    const sig = (cs.signals ?? []).filter((x) => matches(q, x.maker, x.label, x.scope, x.text));
    if (sig.length) {
      out.push(`   최신 달 신호 ${sig.length}건(A 먼저):`);
      for (const x of sig.slice(0, limit)) out.push(`   - ${x.tier} · ${x.signal}: ${x.text}`);
    } else out.push('   최신 달 신호 없음(급감·끊김·급증·첫 판매 조건에 든 계열 없음)');
    if (q || !onlySignals) {
      const rows = (cs.series ?? []).filter((x) => matches(q, x.label, x.scope, x.maker === 'hmc' ? '현대차' : '기아'));
      out.push(`   계열 ${rows.length}개${rows.length > limit ? `(앞 ${limit}개)` : ''} — 최근 6개월:`);
      for (const x of rows.slice(0, limit)) {
        const ms = Object.keys(x.months ?? {}).sort().slice(-6);
        out.push(`   - ${x.maker === 'hmc' ? '현대차' : '기아'} ${x.scope} · ${x.label}: ${ms.map((m) => `${m.slice(2)} ${fmtN(x.months[m])}`).join(' / ')}`);
      }
    }
    const src = Object.keys(name).filter((k) => lm(k)).map((k) => `${name[k]} 엑셀 최종수정 ${lm(k)}`);
    if (src.length) out.push(`   원천: ${src.join(' · ')} — 현대차 ${'https://www.hyundai.com/worldwide/ko/company/ir/ir-resources/sales-results'} · 기아 ${'https://worldwide.kia.com/ko/company/investor-relations/library/performance-and-plans'}`);
    out.push('   검증 상태: 회사 IR 공개 엑셀(잠정치). 이유는 엑셀에 없다 — 단종·생산 중단·물량 조정·재고 조정은 회사 확인. 국내 모델별 수치는 매달 1일 보도자료로 이미 났을 수 있다(news_check).');
  }
  out.push(section === 'carsales'
    ? '\n다음: 신호가 있으면 IR 엑셀 원본에서 같은 행·같은 달을 다시 본다 → news_check(회사+차명+감산·단종·생산 중단) → 회사에 생산·물량 계획 확인. 이유를 짐작해 쓰지 않는다.'
    : '\n다음: 신호가 있으면 원표(ECOS·KOSIS·Census)에서 같은 기준·기간으로 다시 뜬다 → news_check(품목·숫자) → 회사에 판가·가동·재고 대응 확인. 지수는 수준이 아니라 변화다.');
  return textResult(out.join('\n'));
}
