// Scoop screening results: written by GitHub Actions through a bearer-token ingest,
// read only through the private connector path. Never in the public repo or Pages.
import { storeOp } from './store.mjs';
import { clampInt, kstStamp, safeEqual, textResult } from './common.mjs';

const MAX_BODY = 2_000_000;
const VERDICTS = ['미보도 후보', '관련 보도 있음', '미확인', '같은 수치 선행'];

// Private feeds written by GitHub Actions (bearer = MCP_ACCESS_TOKEN). GET returns the last stored
// document so a collector can diff against its own previous private state.
export const FEEDS = {
  'scoop-screen': { blob: 'scoop_screen', schema: 'scoop_screen/v1', list: 'candidates' },
  'us-comments': { blob: 'us_comments', schema: 'us_comments/v1', list: 'items' },
  'page-watch': { blob: 'page_watch', schema: 'page_watch/v1', list: 'pages' },
  'partner-filings': { blob: 'partner_filings', schema: 'partner_filings/v1', list: 'items' },
  'trade-remedy': { blob: 'trade_remedy', schema: 'trade_remedy/v1', list: 'quotas' },
  'us-litigation': { blob: 'us_litigation', schema: 'us_litigation/v1', list: 'cases' },
  'kr-official': { blob: 'kr_official', schema: 'kr_official/v1', list: 'factories' },
  'kr-signals': { blob: 'kr_signals', schema: 'kr_signals/v1', list: 'prices' },
  'kr-stats': { blob: 'kr_stats', schema: 'kr_stats/v1', list: 'series' },
  trademarks: { blob: 'trademarks', schema: 'trademarks/v1', list: 'filings' },
  'assembly-bills': { blob: 'assembly_bills', schema: 'assembly_bills/v1', list: 'bills' },
  'radar-check': { blob: 'radar_check', schema: 'radar_check/v1', list: 'items' },
  'us-recalls': { blob: 'us_recalls', schema: 'us_recalls/v1', list: 'recalls' },
  'reverse-check': { blob: 'reverse_check', schema: 'reverse_check/v1', list: 'articles' },
  'us-epa': { blob: 'us_epa', schema: 'us_epa/v1', list: 'vehicles' },
  'us-osha': { blob: 'us_osha', schema: 'us_osha/v1', list: 'inspections' },
  'us-state-env': { blob: 'us_state_env', schema: 'us_state_env/v1', list: 'notices' },
  'kr-labor': { blob: 'kr_labor', schema: 'kr_labor/v1', list: 'notices' },
  'india-filings': { blob: 'india_filings', schema: 'india_filings/v1', list: 'filings' },
  'dart-counterparty': { blob: 'dart_counterparty', schema: 'dart_counterparty/v1', list: 'items' },
  'union-notices': { blob: 'union_notices', schema: 'union_notices/v1', list: 'posts' },
  'council-minutes': { blob: 'council_minutes', schema: 'council_minutes/v1', list: 'items' },
  'my-articles': { blob: 'my_articles', schema: 'my_articles/v1', list: 'articles' },
  'governance': { blob: 'governance', schema: 'governance/v1', list: 'items' },
  'kr-fuel': { blob: 'kr_fuel', schema: 'kr_fuel/v1', list: 'vehicles' },
  'overseas-awards': { blob: 'overseas_awards', schema: 'overseas_awards/v1', list: 'items' },
  'kr-local': { blob: 'kr_local', schema: 'kr_local/v1', list: 'items' },
  'kr-insolvency': { blob: 'kr_insolvency', schema: 'kr_insolvency/v1', list: 'events' },
  'kr-energy': { blob: 'kr_energy', schema: 'kr_energy/v1', list: 'items' },
  'kr-building': { blob: 'kr_building', schema: 'kr_building/v1', list: 'permits' },
  'overseas-registry': { blob: 'overseas_registry', schema: 'overseas_registry/v1', list: 'companies' },
  'kr-workforce': { blob: 'kr_workforce', schema: 'kr_workforce/v1', list: 'sites' },
  'kr-stacks': { blob: 'kr_stacks', schema: 'kr_stacks/v1', list: 'sites' },
  // 기자 컴퓨터 브라우저로 읽은 새올 목록(local_notice_submit이 쓰고, kr-local 감시가 GET으로 읽는다).
  'kr-local-browser': { blob: 'kr_local_browser', schema: 'kr_local_browser/v1', list: 'cities' },
  // 기자 컴퓨터 브라우저로 읽은 무역구제 공고 목록(호주 TRN 등; local_notice_submit pages → trade-remedy 감시가 GET).
  'trade-remedy-browser': { blob: 'trade_remedy_browser', schema: 'trade_remedy_browser/v1', list: 'pages' },
  // 기자 컴퓨터 브라우저로 읽은 노동위 회의일정 달력(local_notice_submit labor → kr-labor 감시가 GET).
  'kr-labor-browser': { blob: 'kr_labor_browser', schema: 'kr_labor_browser/v1', list: 'commissions' },
  // 출입처 정기보고서 '임원 현황' 비교(kr_exec_watch.py, 11-05) — 새로 보인·빠진 임원과 경력·관계 칸 표시
  'kr-exec': { blob: 'kr_exec', schema: 'kr_exec/v1', list: 'events' },
  // 수시 임원 공시(독립이사 신고·대표이사 변경·출입처 소집공고)와 상장사 등기임원 명단 속 출입처 출신(kr_exec_market.py, 11-05)
  'kr-exec-market': { blob: 'kr_exec_market', schema: 'kr_exec_market/v1', list: 'events' },
  // 문제 임원 점검(kr_exec_check.py, 11-05): 출입처 임원 한 사람씩 법정 결격·한도와 과거 논란 기사
  'kr-exec-check': { blob: 'kr_exec_check', schema: 'kr_exec_check/v1', list: 'people' },
  'global-beat': { blob: 'global_beat', schema: 'global_beat/v1', list: 'items' },
  // 출입처 유럽(EP)·국제(WO) 특허 공개(epo_ops_watch.py, 11-10) — EPO OPS 약관 3.2: 자료 그 자체 공개 금지라 이 기자 전용 저장소에만
  'epo-patents': { blob: 'epo_patents', schema: 'epo_patents/v1', list: 'filings' },
};

// Official trade-remedy listing pages that do not answer GitHub runners (ReadTimeout). Collectors fetch them through
// this bearer-only relay: fixed hosts, GET, https, size-capped. Not a general proxy.
export const RELAY_HOSTS = new Set(['www.industry.gov.au', 'www.dgtr.gov.in']);
const RELAY_MAX = 3_000_000;
const RELAY_HEADERS = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
  Accept: 'text/html,application/xhtml+xml;q=0.9,*/*;q=0.8', 'Accept-Language': 'en-AU,en;q=0.9',
};

async function relay(request, deps) {
  if (request.method !== 'GET') return new Response('Method not allowed', { status: 405, headers: { Allow: 'GET' } });
  let target;
  try { target = new URL(new URL(request.url).searchParams.get('url') ?? ''); } catch { return Response.json({ error: 'bad url' }, { status: 400 }); }
  if (target.protocol !== 'https:' || !RELAY_HOSTS.has(target.hostname)) return Response.json({ error: 'host not allowed' }, { status: 403 });
  const doFetch = deps.fetch ?? fetch;
  let r;
  try {
    r = await doFetch(target.toString(), { headers: RELAY_HEADERS, redirect: 'follow', signal: AbortSignal.timeout(25000) });
  } catch (e) {
    return Response.json({ error: `upstream ${e?.name ?? 'error'}` }, { status: 504 });
  }
  const text = await r.text();
  if (text.length > RELAY_MAX) return Response.json({ error: 'too large' }, { status: 413 });
  return new Response(text, { status: 200, headers: { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store',
    'X-Relay-Status': String(r.status), 'X-Relay-Url': r.url || target.toString() } });
}

export async function handleIngest(request, env, deps = {}) {
  const { pathname } = new URL(request.url);
  const notFound = new Response('Not found', { status: 404 });
  const name = (/^\/ingest\/([a-z-]+)$/.exec(pathname) ?? [])[1];
  const feed = FEEDS[name];
  if (!feed && name !== 'relay') return notFound;
  const m = /^Bearer\s+([A-Za-z0-9_-]{16,128})$/.exec(request.headers.get('Authorization') ?? '');
  if (!m || !(await safeEqual(m[1], env?.MCP_ACCESS_TOKEN))) return notFound;
  if (name === 'relay') return relay(request, deps);
  const ctx = { env, now: deps.now ?? new Date() };
  if (request.method === 'GET') {
    const { row } = await storeOp(ctx, 'blobs.get', { name: feed.blob });
    if (!row) return new Response(null, { status: 204 });
    return new Response(row.body, { status: 200, headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' } });
  }
  if (request.method !== 'POST') return new Response('Method not allowed', { status: 405, headers: { Allow: 'GET, POST' } });
  const text = await request.text();
  if (text.length > MAX_BODY) return Response.json({ error: 'too large' }, { status: 413 });
  let doc;
  try { doc = JSON.parse(text); } catch { return Response.json({ error: 'bad json' }, { status: 400 }); }
  if (doc?.schema !== feed.schema || !Array.isArray(doc[feed.list])) {
    return Response.json({ error: 'schema' }, { status: 400 });
  }
  // 조용한 0건 감시(11-08): 원천별 '받아 온 줄 수(returned)' 이력을 이 문서 끝에 붙여 둔다(원래 글자는 그대로 두고 덧붙임 —
  // 파이썬 감시가 이전 문서를 다시 읽을 때 숫자 모양(1.0 → 1 등)이 바뀌지 않게)
  const prevRw = await storeOp(ctx, 'blobs.get', { name: feed.blob }).then(({ row }) => lastReturnedWatch(row?.body)).catch(() => null);
  const rw = returnedWatch(prevRw, doc, ctx.now.toISOString());
  // 실패한 실행에서 이전 문서를 통째로 이어 쓰는 감시(council·dart 거래상대·인도: {**prev, …})는 옛 이력 키를 그대로 들고 온다.
  // 그래도 다시 직렬화하지 않고 끝에 새 키를 덧붙인다 — 같은 키가 두 번이면 자바스크립트·파이썬 JSON 모두 마지막 것을 쓴다.
  const body = !rw ? text : text.replace(/\}\s*$/, () => `,"${RW_KEY}":${JSON.stringify(rw)}}`);  // 함수로 — 글자 속 $ 기호가 치환 문법으로 읽히지 않게
  await storeOp(ctx, 'blobs.put', { name: feed.blob, body });
  return Response.json({ saved: true, items: doc[feed.list].length });
}

// 조용한 0건(형식 변경 의심, 11-08): 감시가 '정상'으로 끝났는데 원천이 아무것도 안 돌려주면 실패 감시(#736)로도 안 잡힌다.
// 원천(checks[].source)마다 정상 실행의 받아 온 줄 수(returned, 없으면 listed)를 최근 6번까지 쌓고,
// 이전 4번이 모두 3줄 이상이던 원천이 두 번 연달아 0줄이거나 1/10 아래로 줄면(이전 중앙값 20줄 이상일 때) 의심으로 적는다.
// 감시가 이유를 적은 줄(note: '새 달 없음' 등)은 세지 않는다. 의심은 줄 수가 돌아올 때까지 이어 간다.
const RW_KEY = '_returnedWatch';
const RW_KEEP = 6;
const RW_FLOOR = 3;
export function lastReturnedWatch(body) {
  if (typeof body !== 'string') return null;
  const tag = `,"${RW_KEY}":`;
  const i = body.lastIndexOf(tag);
  if (i < 0) return null;
  try { return JSON.parse(body.slice(i + tag.length, body.replace(/\s+$/, '').length - 1)); } catch { return null; }
}
const median = (xs) => { const v = [...xs].sort((a, b) => a - b); return v.length % 2 ? v[(v.length - 1) / 2] : (v[v.length / 2 - 1] + v[v.length / 2]) / 2; };
export function returnedWatch(prev, doc, nowIso) {
  const checks = Array.isArray(doc?.checks) ? doc.checks : [];
  const hist0 = prev && typeof prev.hist === 'object' ? prev.hist : {};
  const was = new Map((Array.isArray(prev?.silent) ? prev.silent : []).map((x) => [x.source, x]));
  const hist = {};
  const silent = [];
  for (const c of checks) {
    const source = String(c?.source ?? c?.company ?? c?.target ?? '').slice(0, 80);
    if (!source || Object.hasOwn(hist, source)) continue;
    const n = typeof c.returned === 'number' ? c.returned : typeof c.listed === 'number' ? c.listed : null;
    const before = (Array.isArray(hist0[source]) ? hist0[source] : []).filter(Number.isFinite);
    if (n === null || c.status !== 'ok' || c.note) {          // 실패·일부·사유 있는 0은 이력에 넣지 않고 지난 이력만 이어 간다
      if (before.length) hist[source] = before.slice(0, RW_KEEP);
      if (was.has(source)) silent.push(was.get(source));
      continue;
    }
    hist[source] = [n, ...before].slice(0, RW_KEEP);
    const old = was.get(source);
    if (old && n <= (old.limit ?? 0)) { silent.push({ ...old, now: n }); continue; }
    const ref = before.slice(1, 5);
    if (ref.length < 4 || !ref.every((x) => x >= RW_FLOOR)) continue;
    const med = median(ref);
    const limit = n === 0 && before[0] === 0 ? 0 : med >= 20 ? Math.floor(med / 10) : -1;
    if (limit >= 0 && n <= limit && before[0] <= limit) silent.push({ source, kind: n === 0 ? 'zero' : 'drop', now: n, before: ref, limit, since: nowIso });
  }
  return Object.keys(hist).length || silent.length ? { hist, ...(silent.length ? { silent: silent.slice(0, 20) } : {}) } : null;
}

export async function readFeed(ctx, name) {
  const feed = FEEDS[name];
  const { row } = await storeOp(ctx, 'blobs.get', { name: feed.blob });
  if (!row) return null;
  try { return JSON.parse(row.body); } catch { return { broken: true }; }
}

// 평일에만 도는 감시의 '오래됨'은 토·일(KST)을 빼고 잰다. 금요일 오후 결과가 일요일에 '37시간 전 — 실행 실패 가능'으로 뜨면
// 진짜 실패가 묻힌다(운영 11-01 02:50: 미국 소송·ITC 37시간 전 경고 — 평일 07:50 감시라 토·일엔 원래 안 돈다). 공휴일은 세지 않는다.
export function weekdayHours(fromMs, toMs) {
  if (!Number.isFinite(fromMs) || !Number.isFinite(toMs)) return NaN;
  const KST = 9 * 3600000;
  let h = 0;
  for (let t = fromMs; t < toMs;) {
    const next = Math.min(toMs, (Math.floor((t + KST) / 86400000) + 1) * 86400000 - KST);  // 다음 KST 자정
    const dow = new Date(t + KST).getUTCDay();
    if (dow !== 0 && dow !== 6) h += (next - t) / 3600000;
    t = next;
  }
  return h;
}

// daily=true: 매일 도는 감시(주말도 센다). 기본은 평일 감시라 토·일을 뺀다.
export function ageNote(ctx, generatedAt, hours = 36, daily = false) {
  const from = Date.parse(generatedAt);
  const ageH = (ctx.now.getTime() - from) / 3600000;
  const counted = daily ? ageH : weekdayHours(from, ctx.now.getTime());
  return Number.isFinite(counted) && counted > hours ? ` (⚠ ${Math.round(ageH)}시간 전 — 최근 실행 실패 가능)` : '';
}

function channelLine(chs = {}) {
  const label = { naver: '네이버', bing: '빙', google: '구글' };
  return Object.entries(chs).map(([k, v]) => `${label[k] ?? k}${v.via ? `(${v.via})` : ''} ${v.status}${v.status === 'ok' ? ` ${v.returned}건` : v.error ? `(${v.error})` : ''}`).join(' · ');
}

export async function scoopScreen(ctx, args) {
  const doc = await readFeed(ctx, 'scoop-screen');
  if (!doc) {
    return textResult('단독 후보 심사 결과가 아직 없음 — GitHub Secrets의 MCP_ACCESS_TOKEN 설정과 다음 정기 실행(평일 07:10·15:10)을 확인. 0건이 아니라 미확인.', true);
  }
  if (doc.broken) return textResult('저장된 심사 결과를 읽지 못함(형식 오류) — 미확인.', true);
  const { rows: fb } = await storeOp(ctx, 'feedback.latest', {});
  const verdictOf = new Map(fb.map((r) => [r.item_id, r]));
  const want = VERDICTS.includes(args.verdict) ? [args.verdict] : VERDICTS;
  const includeKilled = args.include_killed === true || args.include_killed === 'true';
  const limit = clampInt(args.limit, 1, 60, 25);
  const q = String(args.company ?? '').trim();
  const team = String(args.team ?? '').trim();
  const c = doc.counts ?? {};
  const out = [`단독 후보 심사 · ${String(doc.generatedAt).slice(0, 16)}${ageNote(ctx, doc.generatedAt)}`
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
      out.push(`${shown}. [${x.team ?? '?'}] ${x.company ?? ''}${mark ? `  〔기자 판정: ${mark.verdict} — ${mark.reason}〕` : ''}`);
      out.push(`   잡힌 사실: ${x.filing?.correction ? String(x.title ?? '').replace(/\s*—\s*변경 항목 대조 필요$/, '') : x.title} (${x.kind} · ${x.source ?? ''}${x.published ? ` · ${x.published}` : ''})`);
      out.push(`   원문: ${x.url ?? '링크 없음'}${x.filedOn ? ` · 접수 ${x.filedOn}` : ''}`);
      const fl = x.filing;
      if (fl?.error) out.push(`   원문 요점: ${fl.error}`);
      else if (fl) {
        if ((fl.facts ?? []).length) out.push(`   원문 요점(${fl.type}): ${fl.facts.map(([k, v]) => `${k} ${v}`).join(' · ')}`);
        if (fl.correctionLine) out.push(`   정정 내용(원문 정정 표): ${fl.correctionLine}`);
        if (fl.related) out.push(`   회사가 적은 관련공시: ${fl.related}`);
        for (const line of (fl.compare ?? []).slice(0, 3)) out.push(`   직전 비교: ${line}`);
        if (fl.routine) out.push(`   일상 공시로 보임: ${fl.routine} — 오늘의 레이더에서는 B`);
      }
      out.push(`   보도 대조: 질의 ${(x.queries ?? []).map((s) => `"${s}"`).join(', ')} · ${channelLine(x.channels)}`);
      if (x.firstQueries) out.push(`   재대조: 처음 질의 ${x.firstQueries.map((s) => `"${s}"`).join(', ')}(→ ${x.firstVerdict}) 대신 원문 사건명·결과로 다시 찾음`);
      for (const e of (x.evidence ?? []).slice(0, 3)) out.push(`     ↳ ${e.date ?? '날짜?'} [${e.channel}] ${e.title} — ${e.why} ${e.url ?? ''}`);
      const cc = x.correctionCheck;
      if (cc) {
        out.push(`   정정 내용 보도 대조(정정 중 큰 변경 → '${cc.word}' 낱말): ${cc.verdict} — 질의 ${(cc.queries ?? []).map((q) => `"${q}"`).join(', ')} · ${cc.since} 이후 · 제목에 회사·'${cc.word}', 제목·요약에 ${(cc.subject ?? []).join('·')}`);
        for (const e of (cc.evidence ?? []).slice(0, 2)) out.push(`     ↳ ${e.date ?? '날짜?'} [${e.channel}] ${e.title} — ${e.why} ${e.url ?? ''}`);
      }
      out.push(`   검증 상태: 자동 심사(원문 본문·회사 확인 전)${x.staleDays ? ` · 오래된 자료(접수 ${x.staleDays}일 전 — 새 시점 고리 필요)` : ''}`);
      if (x.note) out.push(`   주의: ${x.note}`);
      out.push(`   id ${x.id}`);
    }
  }
  if (hidden) out.push(`\n(기자가 '킬'로 판정한 ${hidden}건 숨김: include_killed=true)`);
  if (!shown) out.push('\n조건에 맞는 후보 없음.');
  out.push('\n다음: 미보도 후보는 source_document·dart_find_text로 원문 → news_check로 낱말 바꿔 재검색 → candidate_check. 보고는 잡힌 사실/기사 가치/확인 질문/원문/판단 순. 판정은 candidate_feedback(item_id=id).');
  return textResult(out.join('\n'));
}
