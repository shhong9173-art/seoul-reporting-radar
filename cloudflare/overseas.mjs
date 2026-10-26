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
