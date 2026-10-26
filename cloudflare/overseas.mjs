// Overseas private watches (regulations.gov comments, official page changes, partner filings).
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

export async function partnerFilings(ctx, args) {
  const doc = await readFeed(ctx, 'partner-filings');
  if (!doc) return missing('해외 파트너 공시', '평일 07:00');
  if (doc.broken) return textResult('저장된 파트너 공시 결과 형식 오류 — 미확인.', true);
  const q = String(args.company ?? '').trim();
  const src = ['ASX', 'EDGAR'].includes(args.source) ? args.source : null;
  const onlyNew = args.only_new === true || args.only_new === 'true';
  // Routine ASX notices (AGM, director interests) are hidden unless asked for.
  const onlyFlagged = !(args.include_routine === true || args.include_routine === 'true');
  const limit = clampInt(args.limit, 1, 60, 20);
  const failed = (doc.checks ?? []).filter((c) => c.status !== 'ok');
  const base = (doc.items ?? []).filter((x) => (!src || x.source === src) && (!onlyNew || x.isNew)
    && matches(q, x.filer, x.title, (x.beat ?? []).join(' '), x.snippet));
  const rows = base.filter((x) => !onlyFlagged || x.source !== 'ASX' || (x.flags ?? []).length);
  const hiddenRoutine = base.length - rows.length;
  const out = [`해외 파트너 공시 · 최근 ${doc.windowDays}일 수집(보관 120일) · ${rows.length}건 · 확인 ${String(doc.generatedAt).slice(0, 16)}${ageNote(ctx, doc.generatedAt)}`,
    `질의 ${(doc.checks ?? []).length - failed.length}/${(doc.checks ?? []).length} 정상${failed.length ? ` · 미확인(0건 아님): ${failed.slice(0, 6).map((c) => `${c.target}(${c.error})`).join(', ')}` : ''}`,
    ...(doc.rules ?? []).map((r) => `규칙: ${r}`)];
  for (const x of rows.slice(0, limit)) {
    out.push(`\n${x.isNew ? '[신규] ' : ''}${x.date} · ${x.source} · ${x.filer} · 관련 출입처 ${(x.beat ?? []).join('·')}`);
    out.push(`   잡힌 사실: ${x.title}${x.priceSensitive ? ' (주가 민감 공시)' : ''}${(x.flags ?? []).length ? ` · 낱말 ${x.flags.join(',')}` : ''}`);
    if (x.relation) out.push(`   관계: ${x.relation} (근거 ${x.relationEvidence})`);
    if (x.snippet) out.push(`   본문 발췌: …${x.snippet.slice(0, 400)}…`);
    else if (x.snippetError) out.push(`   본문 발췌 실패: ${x.snippetError}`);
    out.push(`   원문: ${x.url ?? '링크 없음'}`);
    out.push('   검증 상태: 파트너 측 공시 제목·발췌. 출입처와의 계약 변경 여부는 원문 전체와 출입처 확인 필요');
  }
  if (rows.length > limit) out.push(`… 남은 ${rows.length - limit}건`);
  if (!rows.length) out.push('\n조건에 맞는 공시 없음(위 미확인 질의는 0건 아님).');
  if (hiddenRoutine) out.push(`(ASX 일상 공시 ${hiddenRoutine}건 숨김 — 주총·임원 지분 등: include_routine=true)`);
  out.push('\n다음: EDGAR 원문은 source_document(sec.gov)로, ASX 공시 PDF는 브라우저로 연다 → 출입처 이름·물량·가격·조건 문구 확인 → news_check.');
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
      if (x.bodyError) out.push(`   본문 조회 실패(${x.bodyError}) — 업체명 미확인`);
      out.push(`   원문: ${x.url}`);
    }
    if (sorted.length > limit) out.push(`… 남은 ${sorted.length - limit}건`);
    out.push('   검증 상태: 관보 제목·본문 줄(자동). 세율·판정은 원문 표로 확인. 회사명 일치≠해당 회사 사건 — 조사 대상 목록 확인');
  }

  if (!section || section === 'notices') {
    const from = new Date(ctx.now.getTime() - days * 86400000).toISOString();
    const ev = (doc.events ?? []).filter((e) => new Date(e.detectedAt).toISOString() >= from && matches(q, e.label, e.text, e.country));
    const off = (doc.pages ?? []).filter((p) => p.status === 'disabled');
    const pages = (doc.pages ?? []).filter((p) => p.status !== 'disabled');
    const failed = pages.filter((p) => p.status !== 'ok');
    out.push(`\n[해외 공고·쿼터 변화 · 최근 ${days}일] ${ev.length}건 · 공고 목록 ${pages.length - failed.length}/${pages.length} 열림`);
    if (failed.length) out.push(`미확인(변화 없음 아님): ${failed.map((p) => `${p.label}(${p.error})`).join(', ')}`);
    if (off.length) out.push(`감시 안 함: ${off.map((p) => `${p.label}(${p.error})`).join(', ')}`);
    for (const e of ev.slice(0, limit)) {
      out.push(`- ${String(e.detectedAt).slice(0, 16)} · ${e.country} · ${e.label}`);
      out.push(`   잡힌 사실: ${e.text}`);
      out.push(`   원문: ${e.url}`);
    }
    if (!ev.length) out.push('이 기간 새 줄·새 소진 없음(첫 확인은 기준선만 저장, 열리지 않은 목록은 미확인).');
  }
  out.push('\n다음: 원문은 source_document로 연다(미국 관보·EU) → 대상 품목·업체·세율·소진일 확인 → news_check로 보도 대조 → 회사·협회 확인.');
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
  for (const x of rows.slice(0, limit)) {
    out.push(`\n${x.isNew ? '[신규] ' : ''}${x.dateFiled} · ${x.category} · ${(x.beat ?? []).join('·')}(${x.role})`);
    out.push(`   잡힌 사실: ${x.court ?? x.courtId} ${x.docketNumber ?? ''} 「${x.caseName}」 접수${x.dateTerminated ? ` · 종결 ${x.dateTerminated}` : ''}`);
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
  out.push('\n다음: 사건 페이지에서 소장(Complaint) 열람 → 청구 원인·금액·상대방 확인 → news_check로 보도 대조 → 회사 확인. ITC 고시는 source_document(federalregister.gov)로 연다.');
  return textResult(out.join('\n'));
}
