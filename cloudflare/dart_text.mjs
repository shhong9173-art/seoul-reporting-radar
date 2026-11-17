// 출입처 정기보고서 원문 글자 받기(/ingest/dart-text, 11-17 기자 '추천대로').
// 정기보고서 감시(scripts/dart_text_prewarm.py, GitHub Actions)가 OpenDART 원문(ZIP)을 받아 글자로 바꿔 올린다 — 작업자에서는 큰 보고서 ZIP이
// 15초 안에 안 오고, DART 누리집 나눠 읽기는 호출당 바깥 요청 50개 한도에 걸려 세 번에 나눠 읽어야 했다.
// GET ?rcp=… → 이미 있는지(다시 올리지 않게), POST {schema, rcp, files:[{name, text}]} → 1.8MB씩 잘라 기자 전용 저장소(dart_text)에.
// 인증은 다른 감시와 같은 MCP 토큰. 공개 공시 글이지만 저장소 밖으로 내보내지 않는다(dart_find_text 대목만).
import { safeEqual, sha256Hex } from './common.mjs';
import { storeOp } from './store.mjs';

export const DART_TEXT_SCHEMA = 'dart_text/v1';
const MAX_BODY = 40_000_000;
const CHUNK_BYTES = 1_800_000;

// 줄 단위로 1.8MB(UTF-8)씩 — 한 줄이 그보다 길면 글자 수로 자른다
export function chunkText(text, limit = CHUNK_BYTES) {
  const enc = new TextEncoder();
  const out = [];
  let cur = '';
  let size = 0;
  const flush = () => { if (cur) out.push(cur); cur = ''; size = 0; };
  for (const line of String(text ?? '').split('\n')) {
    const n = enc.encode(line).length + 1;
    if (n > limit) {
      flush();
      for (let i = 0; i < line.length; i += Math.floor(limit / 3)) out.push(line.slice(i, i + Math.floor(limit / 3)));
      continue;
    }
    if (size + n > limit) flush();
    cur += (cur ? '\n' : '') + line;
    size += n;
  }
  flush();
  return out;
}

export async function dartTextRoute(request, env, deps = {}) {
  const notFound = new Response('Not found', { status: 404 });
  const m = /^Bearer\s+([A-Za-z0-9_-]{16,128})$/.exec(request.headers.get('Authorization') ?? '');
  if (!m || !(await safeEqual(m[1], env?.MCP_ACCESS_TOKEN))) return notFound;
  const ctx = { env, now: deps.now ?? new Date() };
  if (request.method === 'GET') {
    const rcp = new URL(request.url).searchParams.get('rcp') ?? '';
    if (!/^\d{14}$/.test(rcp)) return Response.json({ error: 'rcp' }, { status: 400 });
    return Response.json(await storeOp(ctx, 'darttext.have', { rcp }));
  }
  if (request.method !== 'POST') return new Response('Method not allowed', { status: 405, headers: { Allow: 'GET, POST' } });
  const text = await request.text();
  if (text.length > MAX_BODY) return Response.json({ error: 'too large' }, { status: 413 });
  let doc;
  try { doc = JSON.parse(text); } catch { return Response.json({ error: 'bad json' }, { status: 400 }); }
  if (doc?.schema !== DART_TEXT_SCHEMA || !/^\d{14}$/.test(String(doc.rcp ?? '')) || !Array.isArray(doc.files)) return Response.json({ error: 'schema' }, { status: 400 });
  const chunks = [];
  for (const f of doc.files) {
    if (typeof f?.text !== 'string' || !f.text.trim()) continue;
    const parts = chunkText(f.text);
    for (const [i, t] of parts.entries()) chunks.push({ name: `${String(f.name ?? '본문').slice(0, 100)}${parts.length > 1 ? ` (${i + 1}/${parts.length})` : ''}`, text: t, hash: await sha256Hex(t) });
  }
  if (!chunks.length) return Response.json({ error: 'empty' }, { status: 400 });
  const r = await storeOp(ctx, 'darttext.put', { rcp: doc.rcp, chunks });
  return Response.json({ saved: r.saved, chunks: chunks.length });
}

// 보고서 전체 새 낱말(/ingest/dart-text-scan, 11-17): 정기보고서 감시가 회사마다 이번·앞 보고서 접수번호와 감시 낱말을 보내면
// 저장소 안에서 비교해 앞 보고서에 없던 줄 가운데 낱말이 든 줄만 돌려준다(scripts/kr_report_words.py). 둘 중 하나라도 아직 안 넣었으면 missing.
export async function dartTextScanRoute(request, env, deps = {}) {
  const notFound = new Response('Not found', { status: 404 });
  const m = /^Bearer\s+([A-Za-z0-9_-]{16,128})$/.exec(request.headers.get('Authorization') ?? '');
  if (!m || !(await safeEqual(m[1], env?.MCP_ACCESS_TOKEN))) return notFound;
  if (request.method !== 'POST') return new Response('Method not allowed', { status: 405, headers: { Allow: 'POST' } });
  let a;
  try { a = await request.json(); } catch { return Response.json({ error: 'bad json' }, { status: 400 }); }
  if (!/^\d{14}$/.test(String(a?.rcp ?? '')) || !/^\d{14}$/.test(String(a?.base ?? '')) || !Array.isArray(a?.words)) return Response.json({ error: 'schema' }, { status: 400 });
  const ctx = { env, now: deps.now ?? new Date() };
  return Response.json(await storeOp(ctx, 'darttext.newlines', { rcp: a.rcp, base: a.base, words: a.words, max: a.max }));
}
