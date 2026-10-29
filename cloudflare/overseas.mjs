// Private watches: overseas sources (regulations.gov comments, page changes, partner filings, trade remedies, US litigation)
// and domestic official sources (factory registry, gazette legislative notices).
// Data arrives through the bearer ingest; tools read it only on the private connector path.
import { ageNote, readFeed } from './screen.mjs';
import { clampInt, textResult } from './common.mjs';

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
  const failed = pages.filter((p) => p.status !== 'ok');
  const out = [`해외 공식 페이지 변경 · 최근 ${days}일 ${events.length}건 · 페이지 ${pages.length - failed.length}/${pages.length} 열림 · 확인 ${String(doc.generatedAt).slice(0, 16)}${ageNote(ctx, doc.generatedAt)}`];
  if (failed.length) out.push(`미확인(변화 없음 아님): ${failed.map((p) => `${p.label}(${p.error})`).join(', ')}`);
  out.push(...(doc.rules ?? []).map((r) => `규칙: ${r}`));
  for (const e of events.slice(0, clampInt(args.limit, 1, 40, 15))) {
    out.push(`\n${String(e.detectedAt).slice(0, 16)} · ${e.label}${e.scope === 'site' ? ' [사이트 공통]' : ''}`);
    if (!e.scope) out.push('   주의: 사이트 공통 메뉴 문구를 걸러내기 전 기록 — 메뉴·배너 문구 변화일 수 있음');
    out.push(`   비교 기준: ${e.baselineSource}${e.baselineDate ? ` ${e.baselineDate}` : ''} → ${String(e.detectedAt).slice(0, 10)}`);
    for (const [cat, list] of Object.entries(e.removed ?? {})) out.push(`   − ${CAT_KO[cat] ?? cat}: ${list.slice(0, 6).join(' / ')}`);
    for (const [cat, list] of Object.entries(e.added ?? {})) out.push(`   + ${CAT_KO[cat] ?? cat}: ${list.slice(0, 6).join(' / ')}`);
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
    for (const p of pages.filter((x) => x.status === 'ok')) {
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
  }
  const from = new Date(ctx.now.getTime() - AWARD_DAYS * 86400000).toISOString().slice(0, 10);
  const all = (doc.items ?? []).filter((x) => String(x.published ?? x.firstSeen).slice(0, 10) >= from && (!onlyNew || x.isNew)
    && matches(q, x.company, (x.winners ?? []).join(' '), x.buyer, x.title, x.buyerCountry));
  const rank = { A: 0, B: 1, C: 2 };
  const rows = all.filter((x) => q || x.tier !== 'C').sort((a, b) => (rank[a.tier] ?? 3) - (rank[b.tier] ?? 3)
    || String(b.published ?? '').localeCompare(String(a.published ?? '')));
  const others = all.length - rows.length;
  const out = [`\n[해외 발주처 낙찰 · ${doc.coverage ?? 'EU TED·영국 FTS·세계은행·바레인'} · 공고 최근 ${AWARD_DAYS}일] 출입처 ${rows.length}건${others ? ` · 출입처 밖 한국 기업 ${others}건(company 낱말로 보기)` : ''} · 확인 ${String(doc.generatedAt).slice(0, 16)}${ageNote(ctx, doc.generatedAt)}`,
    `원천: ${Object.entries(by).map(([k, b]) => `${k} ${b.ok}/${b.all} 정상${b.failed.length ? `(미확인: ${b.failed.slice(0, 3).join(', ')})` : ''}`).join(' · ')}`,
    ...(doc.rules ?? []).map((r) => `규칙: ${r}`)];
  for (const x of rows.slice(0, limit)) {
    const value = x.value ? `${x.currency ?? ''} ${Number(x.value).toLocaleString('en-US', { maximumFractionDigits: 0 })}` : '금액 미기재';
    const ids = (x.winnerIds ?? []).length ? `, 식별번호 ${x.winnerIds.join('·')}` : '';
    out.push(`\n${x.isNew ? '[신규] ' : ''}${x.published ?? '공고일 미기재'} · ${x.source} ${x.kind} · ${x.company ?? '출입처 밖 한국 기업'} · 발주 ${x.buyer}${x.buyerCountry ? `(${x.buyerCountry})` : ''}`);
    const more = (x.winnerCount ?? (x.winners ?? []).length) - Math.min(2, (x.winners ?? []).length);
    const who = (x.winners ?? []).slice(0, 2).join(' / ') + (more > 0 ? ` 외 ${more}곳` : '');
    out.push(`   잡힌 사실: 낙찰자 ${who || '보고서 줄 참조'}${(x.winnerCountry ?? []).length ? `(${more > 0 ? '낙찰자 전체 국가 ' : ''}${x.winnerCountry.join('·')}${ids})` : ''} · ${x.title} · ${value}${x.priceKind ? `(${x.priceKind})` : ''}${x.concluded ? ` · 계약 ${x.concluded}` : ''}${x.report ? ` · ${x.report}` : ''}`);
    out.push(`   원문: ${x.url ?? '링크 없음'}`);
    out.push(`   검증 상태: 공고의 낙찰자 칸${x.source === '바레인 입찰위원회' ? '(월간 보고서 줄 — 발주처·금액은 PDF 원문 확인)' : ''}. 계약 범위·금액·출입처 공시·보도 여부는 원문과 news_check로 확인`);
  }
  if (rows.length > limit) out.push(`… 남은 ${rows.length - limit}건`);
  if (!rows.length) out.push('조건에 맞는 출입처 낙찰 없음(위 미확인 원천은 0건 아님).');
  return out;
}

export async function partnerFilings(ctx, args) {
  const q = String(args.company ?? '').trim();
  const onlyNewArg = args.only_new === true || args.only_new === 'true';
  const limitArg = clampInt(args.limit, 1, 60, 20);
  const src = ['ASX', 'HKEX', 'EDGAR'].includes(args.source) ? args.source : null;
  const awards = src ? [] : await awardSection(ctx, q, onlyNewArg, limitArg);
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
    if (x.routine || x.finNote) out.push(`   분류: ${x.routine ?? x.finNote}`);
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

export async function tradeRemedies(ctx, args) {
  const doc = await readFeed(ctx, 'trade-remedy');
  if (!doc) return missing('해외 무역구제 감시', '평일 07:40');
  if (doc.broken) return textResult('저장된 무역구제 결과 형식 오류 — 미확인.', true);
  const section = ['quota', 'us', 'notices'].includes(args.section) ? args.section : null;
  const q = String(args.company ?? '').trim();
  const days = clampInt(args.days, 1, 120, 30);
  const limit = clampInt(args.limit, 1, 60, 15);
  const onlyNew = args.only_new === true || args.only_new === 'true';
  const showAll = args.show_all === true || args.show_all === 'true';
  const checks = doc.checks ?? [];
  const out = [`해외 무역구제 감시 · 확인 ${String(doc.generatedAt).slice(0, 16)}${ageNote(ctx, doc.generatedAt)}`,
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
      for (const n of (x.named ?? []).slice(0, 5)) out.push(`   본문의 ${n.company}(${n.mentions}곳): ${n.lines.map((l) => `"${l}"`).join(' / ')}`);
      for (const t of (x.memoUnusual ?? []).slice(0, 3)) out.push(`   결정문 목차 — 흔치 않은 항목(관보 부록 원문): "${t}"`);
      for (const t of (x.memoNamed ?? []).slice(0, 3)) out.push(`   결정문 목차 — 출입처 이름(관보 부록 원문): "${t}"`);
      if (x.bodyError) out.push(`   본문 조회 실패(${x.bodyError}) — 업체명 미확인`);
      out.push(`   원문: ${x.url}`);
    }
    if (sorted.length > limit) out.push(`… 남은 ${sorted.length - limit}건`);
    out.push('   검증 상태: 관보 제목·본문 줄(자동). 세율·판정은 원문 표로 확인. 회사명 일치≠해당 회사 사건 — 조사 대상 목록 확인. 결정문 목차는 쟁점 제목일 뿐 결론이 아니다(\'흔치 않은\'은 자주 나오는 보조금 낱말이 없다는 뜻)');
  }

  if (!section || section === 'notices') {
    const from = new Date(ctx.now.getTime() - days * 86400000).toISOString();
    const ev = (doc.events ?? []).filter((e) => new Date(e.detectedAt).toISOString() >= from && matches(q, e.label, e.text, e.country));
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
      out.push(`   원문: ${e.url}`);
    }
    if (!ev.length) out.push('이 기간 감지된 새 공고 줄·새 소진 없음(열리지 않은 목록은 미확인).');
  }
  out.push('\n다음: 원문은 source_document로 연다(미국 관보·EU) → 대상 품목·업체·세율·소진일 확인 → news_check로 보도 대조 → 회사·협회 확인.');
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
  if (!doc) return missing('미국 리콜(NHTSA 전체)', '평일 17:10');
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
  out.push('\n다음: NHTSA 리콜 페이지·원보고서(source_document, nhtsa.gov)로 대상 차대·부품·공급사 확인 → 국내 판매 여부·자동차리콜센터 → news_check.');
  return textResult(out.join('\n'));
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
  const out = [`미국 EPA 인증(fueleconomy.gov) · 현대차·기아·제네시스 새 등록 ${rows.length}건 · 확인 ${String(doc.generatedAt).slice(0, 16)}${ageNote(ctx, doc.generatedAt, 60)}`,
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
  const out = [`국내 자동차 표시연비 신고(에너지공단, 공공데이터포털) · 출입처 브랜드 새 신고 ${rows.length}건 · 확인 ${String(doc.generatedAt).slice(0, 16)}${ageNote(ctx, doc.generatedAt, 60)}`,
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
  if (!doc) return missing('미국 소송·ITC', '평일 07:50');
  if (doc.broken) return textResult('저장된 소송 결과 형식 오류 — 미확인.', true);
  const q = String(args.company ?? '').trim();
  const onlyNew = args.only_new === true || args.only_new === 'true';
  const routine = args.include_routine === true || args.include_routine === 'true';
  const limit = clampInt(args.limit, 1, 60, 20);
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
  out.push('\n다음: 판결은 PDF(원문)에서 결론·세율·당사자 주장 확인 → news_check로 보도 대조. 사건은 소장(Complaint) 열람 → 청구 원인·금액·상대방 확인 → 회사 확인. ITC 고시는 source_document(federalregister.gov)로 연다.');
  return textResult(out.join('\n'));
}

// Same-name doubt for a court notice's company (kr_insolvency_watch.pick): factory outside the court's region, several owners.
export const identityNote = (ind) => `${ind?.regionMismatch ? ' · ⚠ 공장 주소가 관할 법원 지역 밖(다른 회사일 수 있음)' : ''}${(ind?.owners ?? 0) >= 2 ? ` · 같은 이름 공장 대표자 ${ind.owners}명` : ''}`;

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
    out.push(`   잡힌 사실: 공고 「${e.title}」${ind.label ? ` · 공장등록 업종 ${ind.label}${ind.code ? `(${ind.code}${ind.industry ? ` ${ind.industry}` : ''})` : ''}` : ''}${ind.product ? ` · 주생산품 ${ind.product}` : ''}${ind.employees != null ? ` · 종업원 ${ind.employees}명` : ''}${ind.address ? ` · ${ind.address}` : ''}${ind.factories > 1 ? ` · 같은 이름 등록 공장 ${ind.factories}곳` : ''}${identityNote(ind)}${e.watch ? ` · 협력사 명단: ${[e.watch.beat, e.watch.relation, e.watch.evidence].filter(Boolean).join(' · ')}` : ''}${!ind.label && !e.watch ? ' · 공장등록 없음(이름 낱말만)' : ''}`);
    out.push(`   원문: ${e.url ?? e.listUrl}${e.url && e.listUrl ? ` (안 열리면 ${e.listUrl} 에서 법원·사건번호로 검색)` : ''}`);
    out.push('   검증 상태: 법원 공고(절차 단계). 같은 이름의 다른 회사일 수 있음(주소·대표자 대조). 출입처와의 거래·납품 영향은 회사·출입처 확인 필요');
  }
  if (rows.length > limit) out.push(`… 남은 ${rows.length - limit}건`);
  if (!rows.length) out.push('조건에 맞는 출입 업종 회생·파산 공고 없음(위 미확인 법원·업종 조회 대기는 0건 아님).');
  return out;
}

export async function krOfficial(ctx, args) {
  const section = ['factory', 'gazette', 'insolvency'].includes(args.section) ? args.section : null;
  const q = String(args.company ?? '').trim();
  const insolvency = !section || section === 'insolvency'
    ? await insolvencySection(ctx, q, clampInt(args.days, 1, 120, 30), clampInt(args.limit, 1, 80, 20)) : [];
  if (section === 'insolvency') return textResult(insolvency.join('\n').trim());
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
      out.push(`- ${String(e.detectedAt).slice(0, 10)} · ${e.company} · ${e.kind}`);
      out.push(`   잡힌 사실: ${factoryEventText(doc, e)}`);
    }
    if (!ev.length) out.push('이 기간 감지된 변화 없음(조회 실패 회사는 미확인).');
    const facs = (doc.factories ?? []).filter((f) => matches(q, f.company, f.cmpnyNm, f.rnAdres, f.mainProductCn));
    const recent = facs.filter((f) => (f.tags ?? []).some((t) => t.startsWith('[최근 등록')));
    out.push(`\n[최근 120일 등록 공장 · 등록일 기준] ${recent.length}곳 (출입처 공장 전체 ${facs.length}곳${q ? ', 낱말 거름' : ''})`);
    for (const f of recent.slice(0, limit)) {
      out.push(`- ${f.registeredOn} · ${f.company} · ${f.cmpnyNm} · ${f.rnAdres}`);
      out.push(`   주생산품 ${f.mainProductCn || '미기재'} · 업종 ${f.indutyNm || '미기재'} · 고용 ${f.employees ?? '미기재'}명${f.irsttNm ? ` · ${f.irsttNm}` : ''}${f.nameCheck ? ` · ⚠ ${f.nameCheck}` : ''}`);
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
  if (!section) {
    const eia = (doc.eia ?? []).filter((x) => matches(q, x.company, x.name, x.category));
    out.push(`\n[환경영향평가 · 사업명에 출입처 이름 · 새 단계] ${eia.length}건`);
    for (const x of eia.slice(0, limit)) out.push(`- ${x.isNew ? '[신규] ' : ''}${x.received} 접수 · ${x.company} · ${x.kind} ${x.stage}\n   ${x.name} · ${x.category}${x.completed ? ` · 완료 ${x.completed}` : ''} · 사업코드 ${x.code}`);
    if (!eia.length) out.push('새 단계 없음(첫 실행은 기준선, 조회 실패면 미확인).');
  }
  out.push(...insolvency);
  out.push('\n다음: 새 공장·변경은 회사·지자체에 가동 시점·투자액·인력 확인 → news_check. 입법예고는 원문(관보 PDF)에서 시행일·대상 확인. 환경영향평가는 EIASS에서 사업코드로 평가서 원문(규모·일정) 확인.'
    + (insolvency.length ? ' 회생·파산은 공고 원문(관리인·신청일)과 공장 주소 대조 → 출입처 DART 사업보고서 주요 매입처·협력사 확인(dart_find_text) → 회사·출입처에 거래 규모·대체 공급 확인 → news_check.' : ''));
  return textResult(out.join('\n'));
}

const eok = (v) => (Number.isFinite(v) && v > 0 ? `${v.toLocaleString('en-US')}원(약 ${(v / 1e8).toLocaleString('en-US', { maximumFractionDigits: v >= 1e10 ? 0 : 1 })}억원)` : '미기재');
const signed = (v) => (v === null || v === undefined ? '?' : `${v > 0 ? '+' : ''}${v}%`);
const ymd8 = (s) => (/^\d{8}/.test(String(s ?? '')) ? `${String(s).slice(0, 4)}-${String(s).slice(4, 6)}-${String(s).slice(6, 8)}` : String(s ?? ''));

// 국내 신호: 공정위 의결서(출입처 이름) · 한전 전자입찰(전력기기·전선) · 원자재 가격(KOMIS)
export async function krSignals(ctx, args) {
  const doc = await readFeed(ctx, 'kr-signals');
  if (!doc) return missing('공정위 의결서·한전 입찰·원자재 가격', '평일 08:30·15:20');
  if (doc.broken) return textResult('저장된 국내 신호 결과 형식 오류 — 미확인.', true);
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
  out.push('\n다음: 공정위는 원문(개방문서)에서 피심인·주문·과징금 확인 → news_check(사건명 낱말·회사명) → 회사 확인. 가격은 출입처 실적·판가 영향은 회사·IR로 확인.');
  return textResult(out.join('\n'));
}

const pct2 = (v) => (v === null || v === undefined ? '?' : `${v > 0 ? '+' : ''}${Number(v).toFixed(1)}%`);
const fmtN = (v) => (v === null || v === undefined ? '?' : Number(v).toLocaleString('en-US', { maximumFractionDigits: 2 }));

// 국내 월간 통계: ECOS 품목별 물가지수 · KOSIS(철강협회 생산·광공업동향) · KAIDA 수입 승용차 브랜드별 신규등록
export async function krStats(ctx, args) {
  const doc = await readFeed(ctx, 'kr-stats');
  if (!doc) return missing('국내 월간 통계(ECOS·KOSIS·KAIDA)', '평일 07:30');
  if (doc.broken) return textResult('저장된 국내 월간 통계 형식 오류 — 미확인.', true);
  const section = ['kaida', 'price', 'production', 'us_imports'].includes(args.section) ? args.section : null;
  const q = String(args.company ?? '').trim();
  const limit = clampInt(args.limit, 1, 60, 12);
  const onlySignals = !(args.show_all === true || args.show_all === 'true');
  const checks = doc.checks ?? [];
  const bad = checks.filter((c) => c.status !== 'ok');
  const out = [`국내 월간 통계(한국은행 ECOS 물가·KOSIS 생산·KAIDA 수입차) · 확인 ${String(doc.generatedAt).slice(0, 16)}${ageNote(ctx, doc.generatedAt, 60)}`,
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
  out.push('\n다음: 신호가 있으면 원표(ECOS·KOSIS·Census)에서 같은 기준·기간으로 다시 뜬다 → news_check(품목·숫자) → 회사에 판가·가동·재고 대응 확인. 지수는 수준이 아니라 변화다.');
  return textResult(out.join('\n'));
}
