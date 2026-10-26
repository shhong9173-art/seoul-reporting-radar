// Scoop screening results: written by GitHub Actions through a bearer-token ingest,
// read only through the private connector path. Never in the public repo or Pages.
import { storeOp } from './store.mjs';
import { clampInt, kstStamp, safeEqual, textResult } from './common.mjs';

const MAX_BODY = 2_000_000;
const VERDICTS = ['미보도 후보', '관련 보도 있음', '미확인', '같은 수치 선행'];

export async function handleIngest(request, env, deps = {}) {
  const { pathname } = new URL(request.url);
  const notFound = new Response('Not found', { status: 404 });
  if (pathname !== '/ingest/scoop-screen') return notFound;
  const m = /^Bearer\s+([A-Za-z0-9_-]{16,128})$/.exec(request.headers.get('Authorization') ?? '');
  if (!m || !(await safeEqual(m[1], env?.MCP_ACCESS_TOKEN))) return notFound;
  if (request.method !== 'POST') return new Response('Method not allowed', { status: 405, headers: { Allow: 'POST' } });
  const text = await request.text();
  if (text.length > MAX_BODY) return Response.json({ error: 'too large' }, { status: 413 });
  let doc;
  try { doc = JSON.parse(text); } catch { return Response.json({ error: 'bad json' }, { status: 400 }); }
  if (doc?.schema !== 'scoop_screen/v1' || !Array.isArray(doc.candidates)) {
    return Response.json({ error: 'schema' }, { status: 400 });
  }
  const ctx = { env, now: deps.now ?? new Date() };
  await storeOp(ctx, 'blobs.put', { name: 'scoop_screen', body: text });
  return Response.json({ saved: true, candidates: doc.candidates.length });
}

function channelLine(chs = {}) {
  const label = { naver: '네이버', bing: '빙', google: '구글' };
  return Object.entries(chs).map(([k, v]) => `${label[k] ?? k}${v.via ? `(${v.via})` : ''} ${v.status}${v.status === 'ok' ? ` ${v.returned}건` : v.error ? `(${v.error})` : ''}`).join(' · ');
}

export async function scoopScreen(ctx, args) {
  const { row } = await storeOp(ctx, 'blobs.get', { name: 'scoop_screen' });
  if (!row) {
    return textResult('단독 후보 심사 결과가 아직 없음 — GitHub Secrets의 MCP_ACCESS_TOKEN 설정과 다음 정기 실행(평일 07:10·15:10)을 확인. 0건이 아니라 미확인.', true);
  }
  let doc;
  try { doc = JSON.parse(row.body); } catch { return textResult('저장된 심사 결과를 읽지 못함(형식 오류) — 미확인.', true); }
  const { rows: fb } = await storeOp(ctx, 'feedback.latest', {});
  const verdictOf = new Map(fb.map((r) => [r.item_id, r]));
  const want = VERDICTS.includes(args.verdict) ? [args.verdict] : VERDICTS;
  const includeKilled = args.include_killed === true || args.include_killed === 'true';
  const limit = clampInt(args.limit, 1, 60, 25);
  const q = String(args.company ?? '').trim();
  const team = String(args.team ?? '').trim();
  const ageH = (ctx.now.getTime() - Date.parse(doc.generatedAt)) / 3600000;
  const c = doc.counts ?? {};
  const out = [`단독 후보 심사 · ${String(doc.generatedAt).slice(0, 16)}${ageH > 36 ? ` (⚠ ${Math.round(ageH)}시간 전 — 최근 실행 실패 가능)` : ''}`
    + ` · 후보 ${doc.candidates.length} · ${VERDICTS.map((v) => `${v} ${c[v] ?? 0}`).join(' · ')}`,
    ...(doc.rules ?? []).map((r) => `규칙: ${r}`)];
  let shown = 0; let hidden = 0;
  for (const v of want) {
    const group = doc.candidates.filter((x) => x.verdict === v && (!q || String(x.company).includes(q) || String(x.title).includes(q))
      && (!team || x.team === team));
    const visible = group.filter((x) => includeKilled || verdictOf.get(x.id)?.verdict !== '킬');
    hidden += group.length - visible.length;
    if (!visible.length) continue;
    out.push(`\n■ ${v} (${visible.length})`);
    for (const x of visible) {
      if (shown >= limit) break;
      shown++;
      const mark = verdictOf.get(x.id);
      out.push(`${shown}. [${x.team ?? '?'}] ${x.title}${mark ? `  〔기자 판정: ${mark.verdict} — ${mark.reason}〕` : ''}`);
      out.push(`   ${x.kind} · ${x.source ?? ''}${x.published ? ` · ${x.published}` : ''}${x.url ? ` · ${x.url}` : ''}`);
      out.push(`   질의 ${(x.queries ?? []).map((s) => `"${s}"`).join(', ')} · ${channelLine(x.channels)}`);
      for (const e of (x.evidence ?? []).slice(0, 3)) out.push(`   ↳ ${e.date ?? '날짜?'} [${e.channel}] ${e.title} — ${e.why} ${e.url ?? ''}`);
      out.push(`   id ${x.id}`);
    }
  }
  if (hidden) out.push(`\n(기자가 '킬'로 판정한 ${hidden}건 숨김: include_killed=true)`);
  if (!shown) out.push('\n조건에 맞는 후보 없음.');
  out.push('\n다음: 미보도 후보는 source_document·dart_find_text로 원문 → news_check로 낱말 바꿔 재검색 → candidate_check. 판정은 candidate_feedback(item_id=id).');
  return textResult(out.join('\n'));
}
