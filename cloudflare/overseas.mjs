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
