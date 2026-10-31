import test from 'node:test';
import assert from 'node:assert/strict';
import { deflateRawSync } from 'node:zlib';
import { DatabaseSync } from 'node:sqlite';
import worker from '../cloudflare/worker.mjs';
import { handleMcp, TOOLS } from '../cloudflare/mcp.mjs';
import { RadarStore } from '../cloudflare/store.mjs';
import { checkCandidate } from '../cloudflare/scoring.mjs';
import { readZip } from '../cloudflare/zip.mjs';
import { publicationDate, verifyEvidence } from '../cloudflare/evidence.mjs';
import { allowedUrl } from '../cloudflare/live_tools.mjs';
import { handleIngest } from '../cloudflare/screen.mjs';
import { dueAt, nextSlot, runSchedule } from '../cloudflare/dispatch.mjs';
import { background, billHint, clipAt, convergence, convergenceRows, countForms, hint, insolvencyWord, usRecallHint, usRecallModels, kepcoHint, localWord, radarItems, siteCity, stackHint, workforceHint } from '../cloudflare/digest.mjs';

const ORIGIN = 'https://seoul-reporting-radar.shhong9173.workers.dev';
const TOKEN = 'test-token-0123456789abcdef';
const NOW = new Date('2026-10-26T00:00:00Z'); // 09:00 KST
const DATA = 'https://raw.githubusercontent.com/shhong9173-art/seoul-reporting-radar/main/';

const VIEWS = {
  'tools/clues.json': { generatedAt: '2026-10-25T23:30:00Z', items: [
    { id: 'a1', team: '철강·비철', published: '2026-10-24', source: '팩토리온', title: '동국씨엠 부산공장 공장등록 변경',
      url: 'https://www.factoryon.go.kr/a', companies: ['동국씨엠'], tier: '공개 원자료 추적', routine: false, note: '',
      firstSeen: '2026-10-25T10:00:00+09:00', coverage: { status: 'none_in_index', label: '색인 0건 — 미보도 증거 아님', matches: [] } },
    { id: 'a2', team: '철강·비철', published: '2026-10-24', source: 'DART', title: '현대제철 · 단일판매ㆍ공급계약체결',
      url: 'https://dart.fss.or.kr/x', companies: ['현대제철'], tier: '공개 원자료 추적', routine: false, note: '',
      firstSeen: '2026-10-24T10:00:00+09:00', coverage: { status: 'similar_headlines', label: '색인 유사 제목 1건',
        matches: [{ title: '현대제철, 공급계약', source: '매체', published: '2026-10-24' }] } },
    { id: 'a3', team: '자동차', published: '2026-10-24', source: 'DART', title: '현대위아 · 주주명부폐쇄기간또는기준일설정',
      url: null, companies: ['현대위아'], tier: '공개 원자료 추적', routine: true, note: '',
      firstSeen: '2026-10-24T10:00:00+09:00', coverage: { status: 'none_in_index', label: '', matches: [] } },
    { id: 'a4', team: '자동차', published: '2026-10-01', source: 'DART', title: '기아 · 오래된 공시', url: null,
      companies: ['기아'], tier: '공개 원자료 추적', routine: false, note: '', firstSeen: '2026-10-01T10:00:00+09:00',
      coverage: { status: 'none_in_index', label: '', matches: [] } },
  ] },
  'tools/dandok.json': { generatedAt: '2026-10-25T23:30:00Z', sourceGeneratedAt: '2026-10-25T22:00:00+09:00', status: 'ok',
    note: '제목 색인', items: [
      { published: '2026-10-25', source: '매체A', title: '[단독] 현대제철, 인천 전기로 신설', url: 'https://n/1', companies: ['현대제철'], team: '철강·비철' },
    ] },
  'tools/big_picture.json': { generatedAt: '2026-10-25T23:30:00Z', cluesLast7DaysByTeam: [{ team: '철강·비철', count: 2, lead: 0, indexZero: 1, routine: 0 }],
    topStats: [{ label: '철강제품 수출', changePercent: 42.6, tags: ['[급변]'], period: '202610-20', caveat: '잠정치' }],
    dandokLast7DaysByCompany: [{ company: '현대제철', count: 1 }], latestDandok: [], healthProblems: [{ source: '나라장터 입찰공고', status: 'not_connected' }] },
  'tools/stats.json': { generatedAt: '2026-10-25T23:30:00Z', rules: ['규칙'], items: [
    { label: '철강제품 수출', team: '철강·비철', tags: ['[급변]'], prior: '1814', current: '2588', unit: '천달러', changePercent: 42.6,
      period: '202610-20', source: '관세청', caveat: '잠정치', sourceUrls: [] }] },
  'tools/health.json': { generatedAt: '2026-10-25T23:30:00Z', rule: '0건이 아니다', problemCount: 1,
    items: [{ source: '나라장터 입찰공고', status: 'not_connected', problem: true, ageHours: 7 }] },
  'dart_corp_codes.json': { companies: { '현대제철': { corp_code: '00160500' } } },
  'digests/earnings_compare_latest.json': { generatedAt: '2026-11-13T18:40:00+09:00', status: 'partial', unresolvedCompanies: [],
    period: { year: 2026, report: '11014', label: '2026년 3분기', deadline: '2026-11-14' },
    counts: { filed: 1, not_filed: 1, failed: 1, no_comparable_accounts: 0 },
    companies: [
      { company: '현대제철', team: '철강·비철', status: 'filed', basis: '연결', filedOn: '2026-11-13', url: 'https://dart.fss.or.kr/a',
        quarter: { ratios: { costRatio: 92, sgaRatio: 6, opMargin: 2 }, deltaPp: { costRatio: 3.54, sgaRatio: 1.19, opMargin: -4.73 } },
        cumulative: { ratios: { costRatio: 90.32 }, deltaPp: {} },
        employees: { count: 9500, changePct: 5.6, asOf: '2026.09.30' }, tags: ['[원가율 +3.5%p]', '[직원 +5.6%]'] },
      { company: '고려아연', team: '철강·비철', status: 'not_filed' },
      { company: '영풍', team: '철강·비철', status: 'failed', error: 'HTTP 503' }] },
  'digests/governance_latest.json': { generatedAt: '2026-10-26T07:40:00+09:00', status: 'partial', unresolvedCompanies: ['태광'],
    checks: [{ company: '영풍', endpoint: 'majorstock.json', status: 'failed', error: 'HTTP 503' }],
    items: [
      { company: '고려아연', team: '철강·비철', kind: '대량보유(5%)', date: '2026-10-20', receiptNo: '20261020000111', reporter: '영풍',
        ratio: 24.1, ratioChange: -1.45, tags: ['[지분율 -1.45%p]'], reason: '보유주식 처분', routine: false, url: 'https://dart.fss.or.kr/x' },
      { company: 'KG스틸', team: '철강·비철', kind: '임원 집단 보고', date: '2026-10-23', receiptNo: null, groupKey: 'insider-group|KG스틸|2026-10-23',
        reporter: '임원·주요주주 15명', role: '', sharesChange: 134222, ratioChange: null, tags: ['[같은 날 15명 보고]'],
        reason: '매수 15명·매도 0명', routine: false, url: 'https://dart.fss.or.kr/z' },
      { company: '현대차', team: '자동차', kind: '대량보유(5%)', date: '2026-10-21', receiptNo: '20261021000222', reporter: '국민연금공단',
        ratioChange: 0.05, tags: [], reason: '단순투자', routine: true, url: 'https://dart.fss.or.kr/y' }] },
};

const RSS = `<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>[단독] 동국씨엠, 부산공장 증설 - 매체B</title><link>https://news/1</link><pubDate>Fri, 24 Oct 2026 03:00:00 GMT</pubDate><source url="x">매체B</source></item>
<item><title>오래된 기사</title><link>https://news/2</link><pubDate>Mon, 01 Jan 2024 03:00:00 GMT</pubDate><source url="x">매체C</source></item>
</channel></rss>`;

function fakeFetch(routes = {}) {
  const calls = [];
  const fn = async (input, init = {}) => {
    const url = typeof input === 'string' ? input : input.url;
    calls.push({ url, init });
    for (const [prefix, handler] of Object.entries(routes)) {
      if (url.startsWith(prefix)) return typeof handler === 'function' ? handler(url, init) : handler.clone();
    }
    if (url.startsWith(DATA)) {
      const body = VIEWS[url.slice(DATA.length)];
      return body ? Response.json(body) : new Response('nf', { status: 404 });
    }
    return new Response('blocked', { status: 599 });
  };
  fn.calls = calls;
  return fn;
}

function sqliteStorage() {
  const db = new DatabaseSync(':memory:');
  return { sql: { exec(query, ...params) {
    const stmt = db.prepare(query);
    if (/^\s*(SELECT|WITH)/i.test(query)) { const rows = stmt.all(...params); return { toArray: () => rows }; }
    if (/^\s*CREATE/i.test(query)) { db.exec(query); return { toArray: () => [] }; }
    stmt.run(...params); return { toArray: () => [] };
  } } };
}

function storeBinding() {
  const store = new RadarStore({ storage: sqliteStorage() }, {});
  return { idFromName: (n) => n, get: () => ({ fetch: (url, init) => store.fetch(new Request(url, init)) }) };
}

async function rpc(method, params = {}, { path = '/mcp', env = {}, fetch = fakeFetch(), id = 1 } = {}) {
  const request = new Request(ORIGIN + path, { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ jsonrpc: '2.0', id, method, params }) });
  const response = await handleMcp(request, env, { fetch, now: NOW });
  return { status: response.status, body: response.status === 200 ? await response.json() : null };
}
const call = async (name, args, opts) => {
  const { body } = await rpc('tools/call', { name, arguments: args }, opts);
  return { text: body.result.content[0].text, isError: !!body.result.isError };
};
const PRIVATE = (extra = {}) => ({ path: `/mcp/${TOKEN}`, env: { MCP_ACCESS_TOKEN: TOKEN, STORE: storeBinding(), ...extra } });

test('initialize echoes a supported protocol version and gives instructions', async () => {
  const { body } = await rpc('initialize', { protocolVersion: '2025-03-26', capabilities: {}, clientInfo: { name: 'claude' } });
  assert.equal(body.result.protocolVersion, '2025-03-26');
  assert.equal(body.result.serverInfo.name, 'seoul-reporting-radar');
  assert.match(body.result.serverInfo.version, /^1\.\d+\.0$/);
  assert.match(body.result.instructions, /0건이 아니라 미확인/);
  const unknown = await rpc('initialize', { protocolVersion: '1999-01-01' });
  assert.equal(unknown.body.result.protocolVersion, '2025-06-18');
});

test('notifications get 202 and GET is not served', async () => {
  const r = await handleMcp(new Request(ORIGIN + '/mcp', { method: 'POST', body: JSON.stringify({ jsonrpc: '2.0', method: 'notifications/initialized' }) }), {});
  assert.equal(r.status, 202);
  const g = await handleMcp(new Request(ORIGIN + '/mcp'), {});
  assert.equal(g.status, 405);
});

test('private tools need the exact token; wrong or unset tokens look like 404', async () => {
  const pub = await rpc('tools/list');
  const names = pub.body.result.tools.map((t) => t.name);
  assert.ok(names.includes('radar_clues') && names.includes('news_check'));
  assert.ok(!names.includes('dart_filings') && !names.includes('scoop_packages'));
  const priv = await rpc('tools/list', {}, PRIVATE());
  assert.equal(priv.body.result.tools.length, TOOLS.length);
  assert.equal((await rpc('tools/list', {}, { path: `/mcp/${TOKEN}x`, env: { MCP_ACCESS_TOKEN: TOKEN } })).status, 404);
  assert.equal((await rpc('tools/list', {}, { path: `/mcp/${TOKEN}`, env: {} })).status, 404);
  const blocked = await rpc('tools/call', { name: 'scoop_packages', arguments: {} });
  assert.equal(blocked.body.error.code, -32602);
});

test('clues filter by days and team, hide procedural filings, keep the 0-건 rule visible', async () => {
  const all = await call('radar_clues', { days: 3 });
  assert.match(all.text, /색인 0건은 미보도 증거가 아님/);
  assert.match(all.text, /동국씨엠 부산공장/);
  assert.doesNotMatch(all.text, /주주명부폐쇄/);
  assert.match(all.text, /절차 공시 1건 숨김/);
  assert.doesNotMatch(all.text, /오래된 공시/);
  assert.ok(all.text.indexOf('동국씨엠') < all.text.indexOf('현대제철 · 단일'), 'index-zero line first in team');
  const steel = await call('radar_clues', { days: 3, team: '자동차', include_routine: true });
  assert.match(steel.text, /주주명부폐쇄/);
  assert.doesNotMatch(steel.text, /동국씨엠/);
  const recent = await call('radar_clues', { since_hours: 24 });
  assert.match(recent.text, /동국씨엠/);
  assert.doesNotMatch(recent.text, /현대제철 · 단일/);
});

test('big picture, stats, dandok and health render the published views', async () => {
  assert.match((await call('radar_big_picture', {})).text, /나라장터 입찰공고: not_connected/);
  assert.match((await call('radar_stats', { team: '철강' })).text, /\[급변\] 철강제품 수출/);
  assert.match((await call('dandok_monitor', { days: 7, q: '현대제철' })).text, /인천 전기로/);
  assert.match((await call('radar_health', {})).text, /⚠ 나라장터/);
});

test('governance_changes shows stake moves, hides routine reports and keeps failures visible', async () => {
  const r = await call('governance_changes', { days: 14 });
  assert.match(r.text, /고려아연 \| 대량보유\(5%\) \| 영풍 -1\.45%p → 보고서 기재 보유비율 24\.1%\(특별관계자 포함 가능\)/);
  assert.match(r.text, /단순 보고 1건 숨김/);
  assert.match(r.text, /조회 실패 영풍\(0건 아님\)/);
  assert.match(r.text, /고유번호 미해결 태광/);
  assert.doesNotMatch(r.text, /국민연금공단/);
  assert.match(r.text, /KG스틸 \| 임원 집단 보고 \| 임원·주요주주 15명 순증감 \+134,222주 \[같은 날 15명 보고\]/);
  assert.match((await call('governance_changes', { include_routine: true })).text, /국민연금공단/);
});

test('earnings_compare shows same-period deltas and keeps not-filed and failed apart', async () => {
  const r = await call('earnings_compare', {});
  assert.match(r.text, /2026년 3분기 \(제출 마감 2026-11-14\) · 제출 1 · 미제출 1 · 조회 실패 1/);
  assert.match(r.text, /3개월: 원가율 92\.0%\(\+3\.5%p\) · 판관비율 6\.0%\(\+1\.2%p\) · 영업이익률 2\.0%\(-4\.7%p\)/);
  assert.match(r.text, /누적: 원가율 90\.3%\(전년 미확인\)/);
  assert.match(r.text, /직원 9,500명\(전년 같은 보고서 대비 \+5\.6%\)/);
  assert.match(r.text, /고려아연 — 2026년 3분기 보고서 미제출/);
  assert.match(r.text, /영풍 — 조회 실패\(0 아님\): HTTP 503/);
  const f = await call('earnings_compare', { flagged_only: true });
  assert.doesNotMatch(f.text, /고려아연/);
});

test('news_check: public naver is unavailable so the verdict stays 미확인', async () => {
  const fetch = fakeFetch({ 'https://news.google.com/': new Response(RSS) });
  const r = await call('news_check', { q: '동국씨엠 부산공장', days: 30 }, { fetch });
  assert.match(r.text, /판정: 미확인/);
  assert.match(r.text, /구글 뉴스: 1건/);
  assert.match(r.text, /★단독/);
  assert.doesNotMatch(r.text, /오래된 기사/);
});

test('news_check: all channels ok and empty is not proof of non-coverage', async () => {
  const fetch = fakeFetch({
    'https://news.google.com/': new Response('<rss><channel></channel></rss>'),
    'https://naverapihub.apigw.ntruss.com/': Response.json({ items: [] }),
  });
  const r = await call('news_check', { q: '없는 사건 낱말' }, { ...PRIVATE({ NAVER_CLIENT_ID: 'i', NAVER_CLIENT_SECRET: 's' }), fetch });
  assert.match(r.text, /모두 0건 — 미보도 증거 아님/);
  const failing = fakeFetch({ 'https://news.google.com/': new Response('x', { status: 503 }) });
  const f = await call('news_check', { q: '낱말 두개' }, { ...PRIVATE(), fetch: failing });
  assert.match(f.text, /구글 뉴스: failed — HTTP 503/);
  assert.match(f.text, /네이버 뉴스: not_configured/);
  assert.match(f.text, /판정: 미확인/);
});

test('news_check: the collector status of the [단독] index counts as healthy; unknown or stale ones fail', async () => {
  // Production tools/dandok.json since 10-26: status is the collector's constant, not 'ok' (운영 10-28: 모든 보도 대조가 미확인).
  const index = (status, sourceGeneratedAt = '2026-10-25T22:00:00+09:00') => fakeFetch({
    'https://news.google.com/': new Response('<rss><channel></channel></rss>'),
    'https://naverapihub.apigw.ntruss.com/': Response.json({ items: [] }),
    [DATA + 'tools/dandok.json']: Response.json({ status, sourceGeneratedAt, items: [] }),
  });
  const env = PRIVATE({ NAVER_CLIENT_ID: 'i', NAVER_CLIENT_SECRET: 's' });
  const real = await call('news_check', { q: '없는 사건 낱말' }, { ...env, fetch: index('historical_industry_exclusive_rss_partial_index') });
  assert.match(real.text, /\[단독\] 색인: 0건/);
  assert.match(real.text, /모두 0건 — 미보도 증거 아님/);
  for (const bad of [index('broken'), index('historical_industry_exclusive_rss_partial_index', '2026-10-20T00:00:00+09:00')]) {
    const r = await call('news_check', { q: '없는 사건 낱말' }, { ...env, fetch: bad });
    assert.match(r.text, /\[단독\] 색인: failed — 단독 색인 실패·오래됨·생성일 미확인/);
    assert.match(r.text, /판정: 미확인/);
  }
});

test('news_check: Bing stands in for Google and unwraps the original link', async () => {
  const bingRss = `<rss><channel><item><title>동국씨엠 컬러강판 증설</title><link>https://www.bing.com/news/apiclick.aspx?ref=FexRss&amp;url=https%3a%2f%2fwww.example-news.kr%2fa%2f1&amp;c=1</link><pubDate>Fri, 24 Oct 2026 03:00:00 GMT</pubDate></item></channel></rss>`;
  const fetch = fakeFetch({
    'https://news.google.com/': new Response('blocked', { status: 503 }),
    'https://www.bing.com/news/search': new Response(bingRss),
    'https://naverapihub.apigw.ntruss.com/': Response.json({ items: [] }),
  });
  const r = await call('news_check', { q: '동국씨엠 컬러강판', days: 30 }, { ...PRIVATE({ NAVER_CLIENT_ID: 'i', NAVER_CLIENT_SECRET: 's' }), fetch });
  assert.match(r.text, /구글 뉴스: failed — HTTP 503/);
  assert.match(r.text, /빙 뉴스: 1건/);
  assert.match(r.text, /https:\/\/www\.example-news\.kr\/a\/1/);
  assert.match(r.text, /판정: 관련 보도 후보 1건/);
  const bothDown = fakeFetch({ 'https://news.google.com/': new Response('x', { status: 503 }), 'https://www.bing.com/': new Response('x', { status: 503 }),
    'https://naverapihub.apigw.ntruss.com/': Response.json({ items: [] }) });
  const d = await call('news_check', { q: '동국씨엠 컬러강판' }, { ...PRIVATE({ NAVER_CLIENT_ID: 'i', NAVER_CLIENT_SECRET: 's' }), fetch: bothDown });
  assert.match(d.text, /판정: 미확인 — 웹 색인\(구글·빙 모두\)/);
});

test('news_check: Naver pages past the newest 100 until the window is covered', async () => {
  const env = PRIVATE({ NAVER_CLIENT_ID: 'i', NAVER_CLIENT_SECRET: 's' });
  const item = (i, day) => ({ title: `기아 광명 ${i}`, originallink: `https://news.example.kr/${i}`, link: 'x', pubDate: `${day} 09:00:00 +0900` });
  const page = (url) => {
    const start = Number(new URL(url).searchParams.get('start'));
    if (start === 1) return Response.json({ items: Array.from({ length: 100 }, (_, i) => item(i, 'Fri, 23 Oct 2026')) });
    return Response.json({ items: Array.from({ length: 30 }, (_, i) => item(100 + i, 'Mon, 01 Jun 2026')) });
  };
  const fetch = fakeFetch({ 'https://news.google.com/': new Response('<rss><channel></channel></rss>'), 'https://naverapihub.apigw.ntruss.com/': page });
  const r = await call('news_check', { q: '기아 광명 증축', days: 180 }, { ...env, fetch });
  assert.match(r.text, /네이버 뉴스\(API HUB\): 130건 \(응답 130건\) · 최신순 130건까지 읽음/);
  assert.doesNotMatch(r.text, /100건 상한/);
  assert.equal(fetch.calls.filter((c) => c.url.startsWith('https://naverapihub')).length, 2);
  // every page full and inside the window: stops at the API limit and says so
  const full = fakeFetch({ 'https://news.google.com/': new Response('<rss><channel></channel></rss>'),
    'https://naverapihub.apigw.ntruss.com/': () => Response.json({ items: Array.from({ length: 100 }, (_, i) => item(i, 'Fri, 23 Oct 2026')) }) });
  const f = await call('news_check', { q: '기아', days: 30 }, { ...env, fetch: full });
  assert.match(f.text, /네이버 뉴스: partial — 최신순 1000건 상한 — 그 이전 기사는 못 봄/);
  assert.equal(full.calls.filter((c) => c.url.startsWith('https://naverapihub')).length, 10);
});

test('news_check: Naver goes through API HUB first and old Developers Center keys only when HUB refuses', async () => {
  const env = PRIVATE({ NAVER_CLIENT_ID: 'i', NAVER_CLIENT_SECRET: 's' });
  const hub = fakeFetch({ 'https://naverapihub.apigw.ntruss.com/search/v1/news': Response.json({ items: [
    { title: '<b>현대제철</b> 전기로', originallink: 'https://news.example.kr/1', link: 'x', pubDate: 'Fri, 24 Oct 2026 09:00:00 +0900' }] }) });
  const r = await call('news_check', { q: '현대제철 전기로', days: 30 }, { ...env, fetch: hub });
  assert.match(r.text, /네이버 뉴스\(API HUB\): 1건/);
  const naverCall = hub.calls.find((c) => c.url.startsWith('https://naverapihub'));
  assert.equal(naverCall.init.headers['X-NCP-APIGW-API-KEY-ID'], 'i');
  assert.ok(!hub.calls.some((c) => c.url.startsWith('https://openapi.naver.com')));
  const legacy = fakeFetch({ 'https://naverapihub.apigw.ntruss.com/': new Response('denied', { status: 401 }),
    'https://openapi.naver.com/v1/search/news.json': Response.json({ items: [] }) });
  const l = await call('news_check', { q: '현대제철 전기로', days: 30 }, { ...env, fetch: legacy });
  assert.match(l.text, /네이버 뉴스\(개발자센터\): 0건/);
  assert.equal(legacy.calls.find((c) => c.url.startsWith('https://openapi.naver.com')).init.headers['X-Naver-Client-Id'], 'i');
  const refused = fakeFetch({ 'https://naverapihub.apigw.ntruss.com/': new Response('denied', { status: 401 }),
    'https://openapi.naver.com/': new Response('denied', { status: 401 }) });
  const x = await call('news_check', { q: '현대제철 전기로', days: 30 }, { ...env, fetch: refused });
  assert.match(x.text, /네이버 뉴스: failed — 키 거부\(API HUB HTTP 401, 개발자센터 HTTP 401\)/);
  assert.match(x.text, /판정: 미확인/);
});

test('source_document reads the DART filing body instead of the frame page', async () => {
  const frame = `<html><body>잠시만 기다려주세요<script>
    node1['text'] = "기업가치제고계획(자율공시)"; node1['rcpNo'] = "20261021800308"; node1['dcmNo'] = "11111"; node1['eleId'] = "0";
    node1['offset'] = "0"; node1['length'] = "0"; node1['dtd'] = "HTML";
    viewDoc('20261021800308', '22222', '1', '10', '20', 'dart4.xsd', '');
  </script></body></html>`;
  const fetch = fakeFetch({
    'https://dart.fss.or.kr/dsaf001/main.do': new Response(frame, { headers: { 'Content-Type': 'text/html; charset=utf-8' } }),
    'https://dart.fss.or.kr/report/viewer.do': (url) => new Response(`<html><body><p>${url.includes('dcmNo=22222') ? '본문 PBR 1.2배 목표' : '첨부'}</p></body></html>`,
      { headers: { 'Content-Type': 'text/html; charset=utf-8' } }),
  });
  const r = await call('source_document', { url: 'https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261021800308' }, { fetch });
  assert.match(r.text, /DART 본문 문서 2개/);
  assert.match(r.text, /본문 PBR 1\.2배 목표/);
  assert.doesNotMatch(r.text, /잠시만 기다려주세요/);
  assert.match(r.text, /기업가치제고계획\(자율공시\): https:\/\/dart\.fss\.or\.kr\/report\/viewer\.do\?rcpNo=20261021800308&dcmNo=11111/);
});

test('source_document only opens allowlisted hosts and returns a content hash', async () => {
  assert.equal(allowedUrl('https://evil.example/x'), null);
  assert.equal(allowedUrl('https://user:pw@dart.fss.or.kr/'), null);
  assert.equal(allowedUrl('https://dart.fss.or.kr.evil.example/'), null);
  assert.ok(allowedUrl('https://www.motie.go.kr/a'));
  const refused = await call('source_document', { url: 'https://evil.example/x' });
  assert.ok(refused.isError);
  const html = '<html><head><meta charset="utf-8"><script>x()</script></head><body><p>계약금액 1,812억원</p></body></html>';
  const fetch = fakeFetch({
    'https://www.motie.go.kr/redirect': new Response(null, { status: 302, headers: { Location: 'https://evil.example/' } }),
    'https://www.motie.go.kr/a': new Response(html, { headers: { 'Content-Type': 'text/html; charset=utf-8' } }),
  });
  const ok = await call('source_document', { url: 'https://www.motie.go.kr/a' }, { fetch });
  assert.match(ok.text, /계약금액 1,812억원/);
  assert.match(ok.text, /sha256:[0-9a-f]{64}/);
  assert.doesNotMatch(ok.text, /x\(\)/);
  const hop = await call('source_document', { url: 'https://www.motie.go.kr/redirect' }, { fetch });
  assert.ok(hop.isError);
});

test('source_document sends the declared SEC User-Agent from the Cloudflare secret only to sec.gov', async () => {
  // 10-31 운영: 퍼스트솔라 10-Q가 HTTP 403. SEC는 '회사명 연락이메일' 형식의 접속 표시를 요구한다.
  const doc = 'https://www.sec.gov/Archives/edgar/data/1274494/000127449426000212/fslr-20260930.htm';
  const html = '<html><body><p>USITC Proceeding On February 24, 2026, First Solar filed a petition</p></body></html>';
  const denied = fakeFetch({ 'https://www.sec.gov/': new Response('Request Rate Threshold Exceeded', { status: 403 }) });
  const r = await call('source_document', { url: doc }, { fetch: denied });
  assert.ok(r.isError);
  assert.match(r.text, /HTTP 403 \(SEC 접속 표시 SEC_USER_AGENT가 Cloudflare 비밀값에 없음/);
  const ok = fakeFetch({ 'https://www.sec.gov/': new Response(html, { headers: { 'Content-Type': 'text/html; charset=utf-8' } }),
    'https://www.motie.go.kr/': new Response('<p>보도자료</p>', { headers: { 'Content-Type': 'text/html; charset=utf-8' } }) });
  const env = { SEC_USER_AGENT: 'Test Newsroom radar-test@example.com\n' };
  const r2 = await call('source_document', { url: doc }, { fetch: ok, env });
  assert.match(r2.text, /USITC Proceeding/);
  assert.equal(ok.calls.find((c) => c.url.startsWith('https://www.sec.gov/')).init.headers['User-Agent'], 'Test Newsroom radar-test@example.com');
  await call('source_document', { url: 'https://www.motie.go.kr/a' }, { fetch: ok, env });
  assert.doesNotMatch(ok.calls.find((c) => c.url.startsWith('https://www.motie.go.kr/')).init.headers['User-Agent'], /example\.com/);  // 다른 곳엔 안 보냄
  const still = await call('source_document', { url: doc }, { fetch: denied, env });
  assert.match(still.text, /SEC 접속 표시는 보냈음 — SEC가 이 서버 접속을 막았을 수 있다/);
  // 한글이 섞인 값은 머리글로 보낼 수 없어 쓰지 않고 안내한다
  const ko = fakeFetch({ 'https://www.sec.gov/': new Response('denied', { status: 403 }) });
  const k = await call('source_document', { url: doc }, { fetch: ko, env: { SEC_USER_AGENT: '아이뉴스24 radar-test@example.com' } });
  assert.match(k.text, /영문 밖 글자가 있어 보내지 않음/);
  assert.doesNotMatch(ko.calls[0].init.headers['User-Agent'], /example\.com/);
});

test('dart tools require the private connection and a key, and search inside document.xml', async () => {
  assert.ok((await call('dart_find_text', { rcp_no: '20261023000111', word: '건설중인자산' }, PRIVATE())).isError);
  const xml = Buffer.from('<?xml version="1.0" encoding="utf-8"?><DOC><P>건설중인자산 1,234백만원 증가</P></DOC>');
  const zip = makeZip('20261023000111.xml', xml);
  const fetch = fakeFetch({ 'https://opendart.fss.or.kr/api/document.xml': new Response(zip) });
  const r = await call('dart_find_text', { rcp_no: '20261023000111', word: '건설중인자산' }, { ...PRIVATE({ DART_API_KEY: 'k' }), fetch });
  assert.match(r.text, /1곳/);
  assert.match(r.text, /1,234백만원/);
  assert.ok(!fetch.calls.some((c) => String(c.url).includes('k') && r.text.includes('crtfc_key')));
  const list = fakeFetch({ 'https://opendart.fss.or.kr/api/list.json': Response.json({ status: '000', total_count: 1, total_page: 1,
    list: [{ rcept_dt: '20261023', report_nm: '단일판매ㆍ공급계약체결', rcept_no: '20261023000111', flr_nm: '현대제철', rm: '유' }] }) });
  const l = await call('dart_filings', { company: '현대제철' }, { ...PRIVATE({ DART_API_KEY: 'k' }), fetch: list });
  assert.match(l.text, /00160500/);
  assert.match(l.text, /20261023000111/);
  for (const c of [...list.calls, ...fetch.calls].filter((x) => x.url.startsWith('https://opendart'))) {
    assert.match(c.init.headers?.['User-Agent'] ?? '', /Mozilla/, 'OpenDART calls send browser-like headers');
  }
  const fail = fakeFetch({ 'https://opendart.fss.or.kr/api/list.json': Response.json({ status: '020', message: '요청 제한' }) });
  const f = await call('dart_filings', { company: '현대제철' }, { ...PRIVATE({ DART_API_KEY: 'k' }), fetch: fail });
  assert.match(f.text, /조회 실패\(0건 아님\)/);
});

test('MS949 pages decode through the built-in CP949 table', async () => {
  const { decodeBytes } = await import('../cloudflare/common.mjs');
  const bytes = new Uint8Array([0x3c, 0x70, 0x3e, 0xb5, 0xbf, 0xb1, 0xb9, 0xbe, 0xbe, 0xbf, 0xa5, 0x20, 0x50, 0x42, 0x52, 0x3c, 0x2f, 0x70, 0x3e]);
  const r = decodeBytes(bytes, 'text/html; charset=MS949');
  assert.equal(r.text, '<p>동국씨엠 PBR</p>');
  assert.match(r.charset, /CP949/);
  const meta = new TextEncoder().encode('<meta charset="euc-kr">');
  const mixed = new Uint8Array([...meta, 0xb0, 0xa1]);
  assert.ok(decodeBytes(mixed, 'text/html').text.endsWith('가'));
});

test('zip reader handles stored and deflated entries', async () => {
  const entries = await readZip(makeZip('a.xml', Buffer.from('안녕 DART')));
  assert.equal(new TextDecoder().decode(entries[0].data), '안녕 DART');
});

// Synthetic official response: never uploaded as an operating candidate.
async function verifiedFixture(opts, { date = '2026-10-24', news = {}, body = null } = {}) {
  const url = 'https://www.motie.go.kr/evidence-test';
  const fact = '현대제철 인천 전기로 투자금액 100억원을 공개했다.';
  const html = body ?? `<html><body>게시일: ${date}<p>${fact}</p></body></html>`;
  opts.fetch = fakeFetch({
    [url]: new Response(html, { headers: { 'Content-Type': 'text/html; charset=utf-8' } }),
    'https://news.google.com/': new Response('<rss><channel></channel></rss>'),
    'https://www.bing.com/': new Response('<rss><channel></channel></rss>'),
    'https://naverapihub.': Response.json({ items: [] }),
    [DATA + 'tools/dandok.json']: Response.json({ ...VIEWS['tools/dandok.json'], items: [] }), ...news,
  });
  const original = await call('source_document', { url }, opts);
  const id = (r) => /검증 기록 ID: ([0-9a-f-]{36})/.exec(r.text)?.[1];
  const ids = [];
  for (const q of ['현대제철 인천 전기로', '현대제철 전기로 투자']) ids.push(id(await call('news_check', { q, days: 365 }, opts)));
  return { title: '현대제철 인천 전기로 100억원 투자 확인', companies: ['현대제철'], source_url: url,
    source_date: date, content_hash: /sha256:([0-9a-f]{64})/.exec(original.text)?.[1], source_evidence_id: id(original),
    news_evidence_ids: ids, event_terms: ['인천', '전기로'], facts: [fact], numbers: ['100억원'],
    coverage: { google: 'ok', naver: 'ok', dandok: 'ok', verdict: '단독 확실' },
    company_disclosed: false, comparison: '이전 자료와 비교할 항목', impact: '공급 영향 추가 확인', questions: ['일정?', '공개된 투자 범위?'] };
}
const evidencePrivate = () => PRIVATE({ NAVER_CLIENT_ID: 'test-id', NAVER_CLIENT_SECRET: 'test-secret' });

test('candidate_check refuses caller assertions and uses real tool receipts', async () => {
  const thin = checkCandidate({ title: '현대제철, 전기로 2배 확대', companies: ['현대제철'] });
  assert.equal(thin.status, '조사대기');
  assert.ok(thin.hold.some((h) => h.includes('제목 숫자 근거 없음')));
  const opts = evidencePrivate();
  const c = await verifiedFixture(opts);
  assert.equal(checkCandidate(c).status, '조사대기'); // raw fields cannot bypass validation
  const good = await call('candidate_check', { candidate: c }, opts);
  assert.match(good.text, /판정: 추천/);
  assert.match(good.text, /단독 미확정/);
  assert.doesNotMatch(good.text, /단독 확실/);
  assert.match((await call('candidate_check', { candidate: c })).text, /판정: 조사대기/); // private receipt cannot be read publicly
  assert.match((await call('candidate_check', { candidate: { ...c, coverage: { verdict: '이미 남' } } }, opts)).text, /판정: 탈락/);
});

test('receipts bind source URL, hash, dates, excerpts, company and search queries', async () => {
  const opts = evidencePrivate();
  const c = await verifiedFixture(opts);
  const mutations = [
    { source_url: 'https://example.com/not-verified' }, { content_hash: 'not-a-real-hash' },
    { source_evidence_id: crypto.randomUUID() }, { source_date: '2000-01-01' }, { source_date: '2030-01-01' },
    { facts: ['현대제철 인천 전기로 999억원 투자라는 없는 문장'] }, { numbers: ['999억원'] },
    { title: '현대제철 전기로 999억원', numbers: ['100억원'] },
    { companies: ['포스코'] }, { news_evidence_ids: [c.news_evidence_ids[0], c.news_evidence_ids[0]] },
    { event_terms: ['기부'] }, { derived_numbers: [{ value: '2배', method: '증감률' }] },
  ];
  for (const patch of mutations) {
    const r = await call('candidate_check', { candidate: { ...c, ...patch } }, opts);
    assert.match(r.text, /판정: 조사대기/, JSON.stringify(patch) + r.text);
  }
  const ctx = { private: true, env: opts.env, now: new Date('2026-10-28T00:00:00Z') };
  assert.equal((await verifyEvidence(ctx, c)).sourceOk, false); // expired
  const sub = await call('candidate_submit', { candidates: [{ ...c, source_evidence_id: 'fake' }] }, opts);
  assert.match(sub.text, /\[조사대기\]/);
  assert.doesNotMatch(sub.text, /\[추천\]/);
});

test('old, missing and future publication dates do not get refreshed by retrieval', async () => {
  for (const date of ['2000-01-01', '2030-01-01', '2026-02-30']) {
    const opts = evidencePrivate();
    const c = await verifiedFixture(opts, { date });
    assert.match((await call('candidate_check', { candidate: c }, opts)).text, /판정: 조사대기/);
  }
  const opts = evidencePrivate();
  const c = await verifiedFixture(opts, { body: '접수 마감일: 2026-10-24 현대제철 인천 전기로 투자금액 100억원을 공개했다.' });
  assert.match((await call('candidate_check', { candidate: c }, opts)).text, /게시일을 원문에서 확인하지 못했거나/);
  assert.equal(publicationDate('접수 마감일: 2026-10-24', 'https://www.motie.go.kr/a'), null);
  assert.equal(publicationDate('게시일: 2026.10.24 마감일: 2026.11.30', 'https://www.motie.go.kr/a'), '2026-10-24');
});

test('self-reported ok cannot override actual failed, malformed, stale or nonzero searches', async () => {
  for (const news of [
    { 'https://naverapihub.': new Response('failure', { status: 500 }) },
    { 'https://naverapihub.': Response.json({ error: 'not items' }) },
    { 'https://naverapihub.': Response.json({ items: [{ title: '현대제철 전기로 투자', pubDate: 'Tue, 01 Jan 2030 09:00:00 +0900' }] }) },
    { 'https://news.google.com/': new Response('<rss><channel><item><title>날짜 없음</title></item></channel></rss>'),
      'https://www.bing.com/': new Response('<rss><channel><item><title>날짜 없음</title></item></channel></rss>') },
    { [DATA + 'tools/dandok.json']: Response.json({ status: 'ok', sourceGeneratedAt: '2026-01-01', items: [] }) },
    { 'https://naverapihub.': Response.json({ items: [{ title: '현대제철 전기로 투자', pubDate: 'Sun, 25 Oct 2026 09:00:00 +0900', link: 'https://news.example/1' }] }) },
  ]) {
    const opts = evidencePrivate();
    const c = await verifiedFixture(opts, { news });
    assert.match((await call('candidate_check', { candidate: c }, opts)).text, /판정: 조사대기/);
  }
});

test('DART frame failures issue no source proof; document ZIP gives full hash and receipt', async () => {
  const opts = evidencePrivate();
  const url = 'https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261024000001';
  opts.fetch = fakeFetch({ [url]: new Response(`<html><script>viewDoc('20261024000001','1','0','0','100','dart3.xsd');</script>틀 페이지</html>`,
    { headers: { 'Content-Type': 'text/html' } }) });
  const frame = await call('source_document', { url }, opts);
  assert.match(frame.text, /본문 조회 실패/);
  assert.doesNotMatch(frame.text, /검증 기록 ID:/);
  opts.env.DART_API_KEY = 'test-dart-key';
  opts.fetch = fakeFetch({ 'https://opendart.fss.or.kr/api/document.xml': new Response(makeZip('a.xml', Buffer.from('<DOC>현대제철 인천 전기로 투자 100억원</DOC>'))) });
  const doc = await call('dart_find_text', { rcp_no: '20261024000001', word: '전기로' }, opts);
  assert.match(doc.text, /sha256:[0-9a-f]{64}/);
  assert.match(doc.text, /검증 기록 ID: [0-9a-f-]{36}/);
});

test('packages, daily limit and feedback live in the private store', async () => {
  const opts = PRIVATE();
  assert.match((await call('package_save', { name: 'LS 부산 CAPA', title: 'LS일렉 부산 증설', state: '미발제·확인 필요', body: '근거…' }, opts)).text, /새로 저장/);
  assert.match((await call('package_save', { name: 'LS 부산 CAPA', title: 'LS일렉 부산 증설', state: '발제함', body: '근거2' }, opts)).text, /갱신/);
  const list = await call('scoop_packages', {}, opts);
  assert.match(list.text, /\[발제함\] ls-부산-capa/);
  assert.match((await call('scoop_packages', { name: 'ls-부산-capa' }, opts)).text, /근거2/);
  assert.ok((await call('package_save', { name: 'x', title: 't', state: '모름', body: 'b' }, opts)).isError);
  Object.assign(opts.env, { NAVER_CLIENT_ID: 'test-id', NAVER_CLIENT_SECRET: 'test-secret' });
  const base = await verifiedFixture(opts);
  const many = Array.from({ length: 7 }, (_, i) => ({ ...base, title: `후보 ${i}` }));
  const sub = await call('candidate_submit', { candidates: many }, opts);
  assert.equal((sub.text.match(/\[추천\]/g) ?? []).length, 5);
  assert.equal((sub.text.match(/하루 한도 초과/g) ?? []).length, 2);
  assert.match((await call('candidate_submit', { candidates: [many[0]] }, opts)).text, /중복/);
  await call('candidate_feedback', { item_id: '#1', verdict: '킬', reason: '이미 남' }, opts);
  await call('candidate_feedback', { item_id: '#2', verdict: '씀', reason: '지면 박스' }, opts);
  const review = await call('candidate_weekly_review', {}, opts);
  assert.match(review.text, /판정한 항목 2개: 씀 1 · 킬 1/);
  assert.match(review.text, /- 제출 후보 2 — 씀 1 · 킬 1/);
  assert.match(review.text, /자동으로 바꾸지 않는다/);
});

test('scoop screening arrives only through the bearer ingest and is read on the private path', async () => {
  const env = PRIVATE().env;
  const doc = { schema: 'scoop_screen/v1', generatedAt: '2026-10-26T07:10:00+09:00',
    counts: { '미보도 후보': 1, '관련 보도 있음': 1, '같은 수치 선행': 0, '미확인': 1 },
    rules: ['미보도 후보는 검색 범위 안에서 못 찾았다는 뜻이다.'],
    candidates: [
      { id: 'clue:a1', kind: '단서', team: '자동차', company: '현대차', title: '현대자동차 · HMTR/튀르키예 117600 → 95900 (대)',
        url: 'https://dart.fss.or.kr/x', source: 'DART_METRIC', queries: ['현대차 HMTR', '현대차 HMTR 튀르키예'], verdict: '미보도 후보',
        channels: { naver: { status: 'ok', returned: 12, via: 'API HUB' }, bing: { status: 'ok', returned: 3 }, google: { status: 'failed', returned: 0, error: 'HTTP 503' } },
        evidence: [] },
      { id: 'clue:a2', kind: '단서', team: '자동차', company: '현대위아', title: '현대위아 · 영업양도결정', verdict: '관련 보도 있음',
        queries: ['현대위아 영업양도'], firstQueries: ['현대위아 영업양도결정'], firstVerdict: '미보도 후보', channels: {},
        evidence: [{ date: '2026-10-20', channel: 'naver', title: '현대위아 영업양도', why: '낱말(영업양도)', url: 'https://n/1' }] },
      { id: 'stat:s9', kind: '수치', team: '철강·비철', company: '고려아연', title: '고려아연 황산', verdict: '미확인', queries: ['고려아연 황산'], channels: {}, evidence: [] }] };
  const post = (headers, body = JSON.stringify(doc)) => worker.fetch(new Request(ORIGIN + '/ingest/scoop-screen', { method: 'POST', headers, body }), env, {});
  assert.equal((await post({})).status, 404);
  assert.equal((await post({ Authorization: 'Bearer wrong-token-0123456789' })).status, 404);
  assert.equal((await post({ Authorization: `Bearer ${TOKEN}` }, JSON.stringify({ schema: 'x', candidates: [] }))).status, 400);
  assert.equal((await post({ Authorization: `Bearer ${TOKEN}` })).status, 200);
  const pub = await rpc('tools/call', { name: 'scoop_screen', arguments: {} });
  assert.match(JSON.stringify(pub.body), /Unknown tool/);
  const opts = { path: `/mcp/${TOKEN}`, env };
  const r = await call('scoop_screen', {}, opts);
  assert.match(r.text, /후보 3 · 미보도 후보 1 · 관련 보도 있음 1/);
  assert.match(r.text, /■ 미보도 후보 \(1\)\n1\. \[자동차\] 현대차\n   잡힌 사실: 현대자동차 · HMTR/);
  assert.match(r.text, /검증 상태: 자동 심사\(원문 본문·회사 확인 전\)/);
  assert.match(r.text, /네이버\(API HUB\) ok 12건 · 빙 ok 3건 · 구글 failed\(HTTP 503\)/);
  assert.match(r.text, /↳ 2026-10-20 \[naver\] 현대위아 영업양도 — 낱말\(영업양도\)/);
  assert.match(r.text, /재대조: 처음 질의 "현대위아 영업양도결정"\(→ 미보도 후보\) 대신 원문 사건명·결과로 다시 찾음/);
  await call('candidate_feedback', { item_id: 'clue:a2', verdict: '킬', reason: '이미 남' }, opts);
  const after = await call('scoop_screen', {}, opts);
  assert.doesNotMatch(after.text, /현대위아 · 영업양도결정/);
  assert.match(after.text, /킬'로 판정한 1건 숨김/);
  assert.match((await call('scoop_screen', { include_killed: true }, opts)).text, /기자 판정: 킬 — 이미 남/);
  const empty = await call('scoop_screen', {}, PRIVATE());
  assert.ok(empty.isError);
  const get = (name, headers = { Authorization: `Bearer ${TOKEN}` }) => worker.fetch(new Request(ORIGIN + `/ingest/${name}`, { headers }), env, {});
  const stored = await get('scoop-screen');
  assert.equal(stored.status, 200);
  assert.equal((await stored.json()).candidates.length, 3);
  assert.equal((await get('page-watch')).status, 204);
  assert.equal((await get('page-watch', {})).status, 404);
  assert.equal((await get('unknown-feed')).status, 404);
  const wrongSchema = await worker.fetch(new Request(ORIGIN + '/ingest/us-comments', { method: 'POST',
    headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify({ schema: 'scoop_screen/v1', candidates: [] }) }), env, {});
  assert.equal(wrongSchema.status, 400);
});

test('us_comments reads the private regulations.gov feed', async () => {
  const env = PRIVATE().env;
  const doc = { schema: 'us_comments/v1', generatedAt: '2026-10-26T08:20:00+09:00', lookbackDays: 180, keyType: 'DEMO_KEY',
    checks: [{ company: '현대차', phrase: 'Hyundai Motor', status: 'ok', returned: 12, own: 2 }, { company: '포스코', phrase: 'POSCO', status: 'failed', error: 'HTTP 429 호출 한도' }],
    rules: ['제출자가 제목에 출입처로 적힌 의견서만.'],
    items: [{ id: 'NHTSA-2026-1585-0008', company: '현대차', submitter: 'Hyundai Motor Group', agency: 'NHTSA', docketId: 'NHTSA-2026-1585',
      docketTitle: 'Part 555 exemptions', postedDate: '2026-08-31', url: 'https://www.regulations.gov/comment/NHTSA-2026-1585-0008',
      attachments: ['https://downloads.regulations.gov/x.pdf'], excerpt: 'Please see attached comments from Hyundai Motor Group.', isNew: true }] };
  const post = await worker.fetch(new Request(ORIGIN + '/ingest/us-comments', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {});
  assert.equal(post.status, 200);
  const r = await call('us_comments', {}, { path: `/mcp/${TOKEN}`, env });
  assert.match(r.text, /출입처 명의 1건/);
  assert.match(r.text, /미확인\(0건 아님\): 포스코\(HTTP 429 호출 한도\)/);
  assert.match(r.text, /\[신규\] 2026-08-31 · 현대차 · Hyundai Motor Group → NHTSA/);
  assert.match(r.text, /도켓 「Part 555 exemptions」\(NHTSA-2026-1585\)에 의견서 제출/);
  assert.match(r.text, /첨부 https:\/\/downloads\.regulations\.gov\/x\.pdf/);
  assert.ok((await call('us_comments', {}, PRIVATE())).isError);
  const pub = await rpc('tools/call', { name: 'us_comments', arguments: {} });
  assert.match(JSON.stringify(pub.body), /Unknown tool/);
});

test('page_changes shows before/after lines from the private page-watch feed', async () => {
  const env = PRIVATE().env;
  const doc = { schema: 'page_watch/v1', generatedAt: '2026-10-26T06:30:00+09:00', status: 'partial', rules: ['페이지 문구 변화는 공식 발표가 아니다.'],
    pages: [{ id: 'hyundai-us-ioniq-6-n', company: '현대차', label: '현대차 미국 아이오닉6 N', url: 'https://www.hyundaiusa.com/us/en/vehicles/ioniq-6-n', status: 'ok',
      signals: { timing: ['Coming Spring 2027'], limited: ['extremely limited availability'] } },
      { id: 'kia-us-ev4', company: '기아', label: '기아 미국 EV4', url: 'https://www.kia.com/us/en/ev4', status: 'failed', error: 'HTTP 403' }],
    events: [{ pageId: 'hyundai-us-ioniq-6-n', scope: 'page', company: '현대차', label: '현대차 미국 아이오닉6 N', url: 'https://www.hyundaiusa.com/us/en/vehicles/ioniq-6-n',
      detectedAt: '2026-10-26T06:30:00+09:00', baselineSource: '웹 아카이브 사본', baselineDate: '2026-09-10',
      added: { timing: ['Coming Spring 2027'], limited: ['extremely limited availability'], price: ['$27,600 * Starting MSRP'] },
      removed: { timing: ['Coming 2026'], price: ['$26,900 * Starting MSRP'] },
      priceModels: { '$27,600 * starting msrp': 'ELANTRA', '$26,900 * starting msrp': 'ELANTRA' } }] };
  const post = await worker.fetch(new Request(ORIGIN + '/ingest/page-watch', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {});
  assert.equal(post.status, 200);
  const r = await call('page_changes', { show_current: true }, { path: `/mcp/${TOKEN}`, env });
  assert.match(r.text, /최근 14일 1건 · 페이지 1\/2 열림/);
  assert.match(r.text, /미확인\(변화 없음 아님\): 기아 미국 EV4\(HTTP 403\)/);
  assert.match(r.text, /비교 기준: 웹 아카이브 사본 2026-09-10 → 2026-10-2/);
  assert.match(r.text, /− 출시 시점: Coming 2026/);
  assert.match(r.text, /\+ 출시 시점: Coming Spring 2027/);
  assert.match(r.text, /− 가격: \$26,900 \* Starting MSRP\(근처 차명 ELANTRA\)/);  // 가격 줄에 페이지에서 그 앞 차명(10-31)
  assert.match(r.text, /\+ 가격: \$27,600 \* Starting MSRP\(근처 차명 ELANTRA\)/);
  const rt = await call('radar_today', { hours: 336 }, { path: `/mcp/${TOKEN}`, env });
  assert.match(rt.text, /현대차 미국 아이오닉6 N 문구 변화: \+ Coming Spring 2027 \/ extremely limited availability \/ \$27,600 \* Starting MSRP\(근처 차명 ELANTRA\)/);
  const items = await (await radarItems(new Request(ORIGIN + '/ingest/radar-items?hours=336', { headers: { Authorization: `Bearer ${TOKEN}` } }), env, { now: new Date('2026-10-27T00:00:00Z') })).json();
  assert.deepEqual(items.items.find((x) => x.watch === '해외 공식 페이지')?.check?.terms, ['아반떼', '가격', '미국']);  // 근처 차명으로 질의
  assert.match(r.text, /현대차 미국 아이오닉6 N: Coming Spring 2027 · extremely limited availability/);
});

test('page_changes: a redirected page is not a failure, moved/opened are events, old changes of a redirected address are C', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const now = new Date(Date.now() - 3600000).toISOString();
  const doc = { schema: 'page_watch/v1', generatedAt: now, status: 'complete', rules: [],
    pages: [{ id: 'kia-us-ev4', company: '기아', label: '기아 미국 EV4', url: 'https://www.kia.com/us/en/ev4', status: 'redirected', finalUrl: 'https://www.kia.com/us/en', signals: {} },
      { id: 'kia-us-ev9', company: '기아', label: '기아 미국 EV9', url: 'https://www.kia.com/us/en/ev9', status: 'ok', finalUrl: 'https://www.kia.com/us/en/ev9', signals: {} }],
    events: [
      { pageId: 'kia-us-ev4', scope: 'page', company: '기아', label: '기아 미국 EV4', url: 'https://www.kia.com/us/en/ev4', detectedAt: now, baselineSource: '직전 확인',
        added: { price: ['STARTING AT $ 22,390'] }, removed: {}, redirectNote: '이 주소는 https://www.kia.com/us/en(으)로 넘어가 있어 이 문구는 그 페이지 것이다 — 기아 미국 EV4 문구 아님(2026-10-31 확인)' },
      { pageId: 'kia-us-ev9', scope: 'page', kind: 'moved', company: '기아', label: '기아 미국 EV9', url: 'https://www.kia.com/us/en/ev9', detectedAt: now, baselineSource: '직전 확인',
        movedTo: 'https://www.kia.com/us/en/vehicles', added: {}, removed: { price: ['$54,900'] } },
      { pageId: 'genesis-gv90', scope: 'page', kind: 'opened', company: '제네시스', label: '제네시스 미국 GV90', url: 'https://www.genesis.com/us/en/gv90', detectedAt: now,
        baselineSource: 'x', openedFrom: 'https://www.genesis.com/us/en/home', added: { timing: ['Coming Spring 2027'] }, removed: {} }] };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/page-watch', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const t = await call('page_changes', {}, opts);
  assert.match(t.text, /페이지 2\/2 열림/);
  assert.doesNotMatch(t.text, /미확인\(변화 없음 아님\)/);
  assert.match(t.text, /다른 주소로 넘어가는 페이지\(문구 비교 안 함[^)]*\): 기아 미국 EV4 → https:\/\/www\.kia\.com\/us\/en/);
  assert.match(t.text, /페이지 넘어감: 이 주소가 https:\/\/www\.kia\.com\/us\/en\/vehicles\(으\)로 넘어간다/);
  assert.match(t.text, /주의: 이 주소는 https:\/\/www\.kia\.com\/us\/en\(으\)로 넘어가 있어/);
  const r = await call('radar_today', { include_minor: true }, opts);
  const a = r.text.split('[A · ')[1].split('[B · ')[0];
  assert.match(a, /기아 미국 EV9 페이지 넘어감 → https:\/\/www\.kia\.com\/us\/en\/vehicles/);
  assert.match(a, /제네시스 미국 GV90 페이지 열림\(전에는 https:\/\/www\.genesis\.com\/us\/en\/home\(으\)로 넘어가던 주소 — 출시 준비 신호일 수 있음\): Coming Spring 2027/);
  assert.doesNotMatch(a, /기아 미국 EV4/);
  assert.match(r.text.split('[C · ')[1], /기아 미국 EV4 문구 변화: \+ STARTING AT \$ 22,390 — 이 주소는/);
});

test('partner_filings reads ASX and EDGAR items from the private feed', async () => {
  const env = PRIVATE().env;
  const doc = { schema: 'partner_filings/v1', generatedAt: '2026-10-26T07:00:00+09:00', windowDays: 30, rules: ['파트너 공시는 그 회사의 발표다.'],
    checks: [{ source: 'ASX', target: 'Arafura Rare Earths(ARU)', status: 'ok', returned: 30 }, { source: 'EDGAR', target: 'Taihan', status: 'failed', error: 'HTTP 403' }],
    items: [
      { id: 'asx:ARU:2026-10-20:x', source: 'ASX', filer: 'Arafura Rare Earths (ARU)', beat: ['현대차', '기아'], relation: 'NdPr 공급계약', relationEvidence: 'https://example/aru',
        date: '2026-10-20', title: 'Offtake update', url: 'https://x/pdf', priceSensitive: true, flags: ['offtake'], isNew: true },
      { id: 'asx:ARU:2026-10-10:y', source: 'ASX', filer: 'Arafura Rare Earths (ARU)', beat: ['현대차'], date: '2026-10-10', title: 'Quarterly report', flags: [], isNew: false },
      { id: 'edgar:a:b', source: 'EDGAR', filer: 'Acme Metals Inc  (ACME)', beat: ['현대제철'], date: '2026-10-21', title: '8-K Current report',
        url: 'https://www.sec.gov/Archives/edgar/data/1/a/b.htm', snippet: 'supply agreement with Hyundai Steel', isNew: true }] };
  const post = await worker.fetch(new Request(ORIGIN + '/ingest/partner-filings', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {});
  assert.equal(post.status, 200);
  const opts = { path: `/mcp/${TOKEN}`, env };
  const r = await call('partner_filings', {}, opts);
  assert.match(r.text, /질의 1\/2 정상 · 미확인\(0건 아님\): Taihan\(HTTP 403\)/);
  assert.match(r.text, /\[신규\] 2026-10-20 · ASX · Arafura Rare Earths \(ARU\) · 관련 출입처 현대차·기아/);
  assert.match(r.text, /관계: NdPr 공급계약 \(근거 https:\/\/example\/aru\)/);
  assert.match(r.text, /본문 발췌: …supply agreement with Hyundai Steel…/);
  assert.doesNotMatch(r.text, /Quarterly report/);
  assert.match(r.text, /일상 공시 1건 숨김 — ASX 주총·임원 지분/);
  const all = await call('partner_filings', { include_routine: true, source: 'ASX' }, opts);
  assert.match(all.text, /Quarterly report/);
});

test('partner filings: HKEX partner deal titles reach A with Hong Kong time; routine HKEX notices fold', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const doc = { schema: 'partner_filings/v1', generatedAt: '2026-10-26T07:00:00+09:00', windowDays: 30, checks: [{ source: 'HKEX', target: 'BAIC Motor(01958)', status: 'ok', returned: 3 }],
    items: [
      { id: 'hkex:01958:11906001', source: 'HKEX', filer: 'BAIC Motor (01958)', beat: ['현대차'], relation: '베이징현대 합작 상대', relationEvidence: 'https://example/baic',
        date: '2026-10-25', time: '18:33', title: 'MAJOR TRANSACTION - EXIT OF BAIC INVESTMENT FROM ITS INVESTMENT IN BHAF', url: 'https://www1.hkexnews.hk/x.pdf',
        flags: ['exit', 'major transaction'], firstSeen: '2026-10-25T19:00:00+09:00', isNew: true },
      { id: 'hkex:01958:1', source: 'HKEX', filer: 'BAIC Motor (01958)', beat: ['현대차'], date: '2026-10-25', time: '16:44', title: 'NOTICE OF BOARD MEETING',
        flags: [], routine: '정기·형식 공시(월간 증권 변동·이사회 일정·정기보고서 등)', firstSeen: '2026-10-25T19:00:00+09:00', isNew: true }] };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/partner-filings', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const r = await call('partner_filings', { source: 'HKEX' }, opts);
  assert.match(r.text, /\[신규\] 2026-10-25 18:33\(홍콩시각\) · HKEX · BAIC Motor \(01958\) · 관련 출입처 현대차/);
  assert.doesNotMatch(r.text, /NOTICE OF BOARD MEETING/);
  assert.match(r.text, /HKEX 월간 증권 변동·이사회 일정/);
  const today = await call('radar_today', { hours: 72 }, opts);
  const a = today.text.split('[A · ')[1].split('[B · ')[0];
  assert.match(a, /HKEX BAIC Motor \(01958\) 18:33 홍콩시각: MAJOR TRANSACTION - EXIT OF BAIC INVESTMENT FROM ITS INVESTMENT IN BHAF \(낱말 exit,major transaction\)/);
  assert.doesNotMatch(a, /NOTICE OF BOARD MEETING/);
  const items = await (await radarItems(new Request(ORIGIN + '/ingest/radar-items?hours=72', { headers: { Authorization: `Bearer ${TOKEN}` } }), env, { now: NOW })).json();
  const hk = items.items.find((x) => x.id === 'hkex:01958:11906001');
  assert.deepEqual(hk.check.terms, ['BAIC', '합작']);
  assert.deepEqual(hk.check.alts.BAIC, ['BAIC', '베이징자동차', '베이징기차', '北汽']);
});

test('trade_remedies shows quota exhaustion, named US notices and listing changes from the private feed', async () => {
  const env = PRIVATE().env;
  const recent = new Date(Date.now() - 3600000).toISOString();
  const doc = { schema: 'trade_remedy/v1', generatedAt: '2026-10-27T07:40:00+09:00', baselineSince: '2026-10-26T21:33:00+09:00', quarter: '2026-10-01', rules: ["'한국 전용'과 '공동'을 구분한다."],
    checks: [{ source: 'EU TARIC', status: 'ok', returned: 3 }, { source: '미국 관보', status: 'ok', returned: 2 },
      { source: '인도 DGTR 반덤핑 조사', status: 'failed', returned: 0, error: 'HTTP 403' }],
    quotas: [
      { order: '099843', status: 'ok', product: '컬러강판(유기코팅)', scope: '한국 전용', initialT: 41828.1, balanceT: 0, usedPct: 100,
        exhaustedOn: '2026-10-10', tags: ['[소진 2026-10-10 · 분기 10일째]', '[직전 분기보다 15일 빨리 소진]'],
        lastQuarter: { exhaustedOn: '2026-07-25', daysToExhaust: 24, usedPct: 100 }, url: 'https://ec.europa.eu/q?Code=099843' },
      { order: '099854', status: 'ok', product: '후판', scope: '한국 전용', initialT: 136000, balanceT: 34153.9, usedPct: 74.9, tags: [] },
      { order: '099507', status: 'ok', product: '컬러강판(유기코팅)', scope: '공동(한국 포함)', initialT: 12575.7, balanceT: 0, usedPct: 100,
        exhaustedOn: '2026-10-16', tags: ['[소진 2026-10-16 · 분기 16일째]'] }],
    federalRegister: [
      { id: 'fr:2026-20698', date: '2026-10-08', stage: '예비 판정', title: 'Certain Corrosion-Resistant Steel Products From the Republic of Korea: Preliminary Results',
        url: 'https://www.federalregister.gov/d/2026-20698', beatProduct: true, isNew: true,
        named: [{ company: '현대제철', mentions: 3, lines: ['Hyundai Steel Company ........ 1.12'] }] },
      { id: 'fr:2026-20694', date: '2026-10-08', stage: '예비 판정', title: 'Certain Steel Nails From the Republic of Korea', url: 'https://x', named: [], isNew: false }],
    pages: [{ id: 'in-dgtr', label: '인도 DGTR 반덤핑 조사', status: 'failed', error: 'HTTP 403' }, { id: 'au-adn', label: '호주 ADN', status: 'ok' },
      { id: 'xx', label: '시험 목록', status: 'disabled', error: '주소 확인 전' }],
    events: [{ id: 'au-adn:x', pageId: 'au-adn', country: '호주', label: '호주 ADN', text: 'ADN 2026/101 Zinc coated steel from China, Korea and Taiwan', url: 'https://www.industry.gov.au/adn/2026/101', detectedAt: recent }] };
  const post = await worker.fetch(new Request(ORIGIN + '/ingest/trade-remedy', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {});
  assert.equal(post.status, 200);
  const opts = { path: `/mcp/${TOKEN}`, env };
  const r = await call('trade_remedies', {}, opts);
  assert.match(r.text, /인도 DGTR 반덤핑 조사 failed\(0, HTTP 403\)/);
  assert.match(r.text, /\[EU 철강 쿼터 · 2026-10-01 분기\] 3개\(한국 전용 2 · 공동 1\)/);
  assert.match(r.text, /099843 컬러강판\(유기코팅\) · 한국 전용 · 초기 41,828\.1t · 잔량 0t · 사용 100% \[소진 2026-10-10 · 분기 10일째\] \[직전 분기보다 15일 빨리 소진\] · 직전 분기 소진 2026-07-25\(25일째\)/);
  assert.ok(r.text.indexOf('099843') < r.text.indexOf('099507'));  // Korea-only first
  assert.doesNotMatch(r.text, /099854/);
  assert.match(r.text, /여유 있는 쿼터 1개 숨김/);
  assert.match(r.text, /\[신규\] 2026-10-08 · 예비 판정 · Certain Corrosion-Resistant/);
  assert.match(r.text, /본문의 현대제철\(3곳\): "Hyundai Steel Company \.\.\.\.\.\.\.\. 1\.12"/);
  assert.match(r.text, /미확인\(변화 없음 아님\): 인도 DGTR 반덤핑 조사\(HTTP 403\)/);
  assert.match(r.text, /잡힌 사실: ADN 2026\/101 Zinc coated steel from China, Korea and Taiwan/);
  assert.match(r.text, /\[감지된 변화 · 감지일 기준 최근 30일\] 1건/);
  assert.match(r.text, /기준선 2026-10-26 이후 새로 생긴 공고 줄·새 소진만/);
  assert.match(r.text, /공고 목록 1\/2 열림/);
  assert.match(r.text, /감시 안 함: 시험 목록\(주소 확인 전\)/);
  const quota = await call('trade_remedies', { section: 'quota', show_all: true }, opts);
  assert.match(quota.text, /099854 후판/);
  assert.doesNotMatch(quota.text, /미국 상무부/);
  assert.ok((await call('trade_remedies', {}, PRIVATE())).isError);
});

test('trade_remedies and radar_today drop rows re-caught only because the list renumbered (DGTR 10-28·10-31)', async () => {
  const env = PRIVATE().env;
  const t = (h) => new Date(Date.now() - h * 3600000).toISOString();
  const ipa = 'Ongoing Investigation Anti-dumping investigation concerning imports of Isopropyl Alcohol from the European Union, South Korea';
  const doc = { schema: 'trade_remedy/v1', generatedAt: '2026-10-31T13:20:00+09:00', quarter: '2026-10-01', rules: [], quotas: [], federalRegister: [],
    checks: [{ source: '인도 DGTR 반덤핑 조사', status: 'ok', returned: 6 }], pages: [{ id: 'in-dgtr', label: '인도 DGTR 반덤핑 조사', status: 'ok' }],
    events: [
      { id: 'in-dgtr:4', pageId: 'in-dgtr', country: '인도', label: '인도 DGTR 반덤핑 조사', text: `4 - ${ipa}`, url: 'https://www.dgtr.gov.in/x', detectedAt: t(1), renumbered: true },
      { id: 'in-dgtr:3', pageId: 'in-dgtr', country: '인도', label: '인도 DGTR 반덤핑 조사', text: `3 - ${ipa}`, url: 'https://www.dgtr.gov.in/x', detectedAt: t(20), repeats: 1 }] };
  const post = await worker.fetch(new Request(ORIGIN + '/ingest/trade-remedy', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {});
  assert.equal(post.status, 200);
  const opts = { path: `/mcp/${TOKEN}`, env };
  const r = await call('trade_remedies', { section: 'notices' }, opts);
  assert.match(r.text, /\[감지된 변화 · 감지일 기준 최근 30일\] 1건/);
  assert.doesNotMatch(r.text, /잡힌 사실: 4 - /);
  assert.match(r.text, /잡힌 사실: 3 - Ongoing Investigation[^\n]*\n   주의: 목록 일련번호만 바뀌어 1번 다시 잡힌 줄 — 이 감지도 번호 이동일 수 있음/);
  assert.match(r.text, /목록 일련번호만 바뀐 재감지 1건은 뺐다/);
  const today = await call('radar_today', { include_minor: true }, opts);
  assert.doesNotMatch(today.text, /4 - Ongoing Investigation/);
  const c = today.text.split('[C · ')[1] ?? '';
  assert.match(c, /3 - Ongoing Investigation[^\n]*목록 일련번호만 바뀌어 1번 다시 잡힌 줄이라 이 감지도 번호 이동일 수 있음/);
  assert.doesNotMatch(today.text.split('[C · ')[0], /Isopropyl/);
});

test('trade_remedies ktc: meeting agenda before the meeting, recent cases with last step, old cases hidden; radar_today tiers by beat product', async () => {
  const env = PRIVATE().env;
  const recent = new Date(Date.now() - 3600000).toISOString();
  const ktc = { checkedAt: '2026-10-30T07:40:00+09:00', listComplete: true,
    cases: [
      { id: '00000845', no: '구제 4-1-2025-1', title: '커넥티드 전기자동차 특허권 침해 불공정무역행위 조사', product: '커넥티드 전기자동차', opened: '2025-06-30', stage: '조사실행',
        kind: '불공정무역행위', review: '원심', country: null, beat: true, timeline: [['조사개시', '2025-06-30'], ['판정시한 2차 연장', '2026-02-25']], pending: [],
        url: 'https://www.ktc.go.kr/viewInvest.do?menuId=11&masterId=00000845&invstg_type_code=10100002' },
      { id: '00000875', no: '구제 23-2026-9호', title: '중국산 무계목강관의 덤핑사실 및 국내산업피해 유무 조사', product: '무계목강관', opened: '2026-10-08', stage: '조사실행',
        kind: '반덤핑조사', review: '원심', country: '중국', beat: true, timeline: [['조사개시', '2026-10-08']], pending: ['예비조사', '공청회', '최종판정'], url: 'https://www.ktc.go.kr/v?875' },
      { id: '00000859', no: '구제 23-2025-13호', title: '중국산 인쇄제판용 평면모양 사진플레이트', product: '인쇄제판용 평면모양 사진플레이트', opened: '2026-01-08', stage: '조사실행',
        kind: '반덤핑조사', review: '재심', country: '중국', beat: false, timeline: [['조사개시', '2026-01-08']], pending: ['최종판정'], url: 'https://www.ktc.go.kr/v?859' },
      { id: '00000493', no: '제 4-1-2008-6', title: '낚싯대케이스', product: '낚싯대케이스', opened: '2008-07-23', stage: '조사실행', beat: false, url: 'https://www.ktc.go.kr/v?493' }],
    left: [{ id: '00000868', no: '구제23-2026-5호', title: '중국산 석도강판의 덤핑사실 및 국내산업피해 유무', product: '석도강판', leftAt: '2026-10-30T07:40:00+09:00', result: '부정 · 조사종결' }],
    meetings: [{ id: '00000312', title: '제479차 11월 무역위원회 개최 안내', posted: '2026-11-13', meetingOn: '2026-11-20', summary: '3건(정기보고1, 의결2)',
      url: 'https://www.ktc.go.kr/noticeScheduleView.do?dltnc_id=00000312&menuId=24',
      agenda: [{ kind: '의결', no: '2026-27', text: '중국산 석도강판의 덤핑사실및국내산업피해유무 예비판정(원심)', beat: true },
        { kind: '보고', no: '2026-21', text: '화장품 상표권 침해 조사개시 보고', beat: false }] },
      { id: '00000311', title: '제478차 10월 무역위원회 개최 안내', posted: '2026-10-16', agenda: null, agendaError: 'PDF 받기 실패' }],
    news: [{ id: '00002297', title: '무역위, 중국산 아연도금냉연, 옵셋인쇄판 덤핑조사 최종판정', posted: '2026-10-26' }] };
  const doc = { schema: 'trade_remedy/v1', generatedAt: '2026-10-30T07:40:00+09:00', quarter: '2026-10-01', rules: [], quotas: [], federalRegister: [], pages: [],
    checks: [{ source: '무역위원회', status: 'ok', returned: 4 }], ktc,
    events: [
      { id: 'ktc:meeting:00000312', pageId: 'ktc', country: 'KR', label: '무역위원회 회의 안내(개최 2026-11-20)', text: '제479차 — 의결: 중국산 석도강판 예비판정', url: 'https://k/m', detectedAt: recent, tier: 'B', beat: true, ktcKind: 'meeting' },
      { id: 'ktc:case:00000900', pageId: 'ktc', country: 'KR', label: '무역위 새 조사 · 구제 4-2-2026-2', text: '플라스틱 필름 원산지 표시위반', url: 'https://k/c', detectedAt: recent, tier: 'C', beat: false, ktcKind: 'case', product: '플라스틱 필름' },
      { id: 'ktc:news:00002297', pageId: 'ktc', country: 'KR', label: '무역위 보도자료', text: '무역위, 중국산 아연도금냉연 덤핑조사 최종판정', url: 'https://k/n', detectedAt: recent, tier: 'C', beat: true, ktcKind: 'news' }] };
  const post = await worker.fetch(new Request(ORIGIN + '/ingest/trade-remedy', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {});
  assert.equal(post.status, 200);
  const opts = { path: `/mcp/${TOKEN}`, env };
  const r = await call('trade_remedies', { section: 'ktc' }, opts);
  assert.match(r.text, /\[국내 무역위원회 · 확인 2026-10-30T07:40\] 진행 목록 4건 · 2019년 이후 개시 3건\(출입 업종 품목 2\)/);
  assert.match(r.text, /- 회의: 제479차 11월 무역위원회 개최 안내 · 개최 2026-11-20 · 게시 2026-11-13 · 안건 3건\(정기보고1, 의결2\)\n   의결\(출입 업종 품목\): 중국산 석도강판/);
  assert.match(r.text, /안건 미확인\(PDF 받기 실패\) — 0건 아님/);
  assert.match(r.text, /구제 4-1-2025-1 · 커넥티드 전기자동차 특허권 침해 불공정무역행위 조사 · 대상국 미기재 · 불공정무역행위\/원심 · 개시 2025-06-30 · 최근 판정시한 2차 연장 2026-02-25 · 출입 업종 품목/);
  assert.ok(r.text.indexOf('무계목강관') < r.text.indexOf('커넥티드'));  // beat products, latest step first
  assert.ok(r.text.indexOf('커넥티드') < r.text.indexOf('사진플레이트'));  // non-beat after beat
  assert.match(r.text, /남은 단계 예비조사·공청회·최종판정/);
  assert.match(r.text, /2019년 전 개시 1건은 목록에 '조사실행'으로 남은 옛 사건 — 숨김/);
  assert.doesNotMatch(r.text, /낚싯대케이스/);
  assert.match(r.text, /진행 목록에서 빠짐 2026-10-30: 구제23-2026-5호 중국산 석도강판의 덤핑사실 및 국내산업피해 유무 · 판정결과 부정 · 조사종결/);
  assert.match(r.text, /최근 보도자료: 무역위, 중국산 아연도금냉연, 옵셋인쇄판 덤핑조사 최종판정\(2026-10-26\)/);
  assert.doesNotMatch(r.text, /EU 철강 쿼터/);
  const steel = await call('trade_remedies', { section: 'ktc', company: '석도' }, opts);
  assert.doesNotMatch(steel.text, /커넥티드/);
  assert.match(steel.text, /제479차/);
  const today = await call('radar_today', { include_minor: true }, opts);
  const b = today.text.split('[B · ')[1].split('[C · ')[0];
  assert.match(b, /무역구제\n   무역위원회 회의 안내\(개최 2026-11-20\): 제479차 — 의결: 중국산 석도강판 예비판정/);
  assert.doesNotMatch(b, /플라스틱 필름|아연도금냉연 덤핑조사 최종판정/);
});

test('kr_official workforce: member counts ranked by monthly drop with year-ago, events and new construction sites; radar_today tiers', async () => {
  const env = PRIVATE().env;
  const recent = new Date(Date.now() - 3600000).toISOString();
  const doc = { schema: 'kr_workforce/v1', generatedAt: '2026-10-31T15:50:00+09:00', status: 'partial', month: '202609', scanStatus: 'complete',
    checks: [{ source: '국민연금 사업장(출입처 검색)', status: 'ok', returned: 58 }, { source: '국민연금 사업장(지난 12개월 채우기)', status: 'ok', returned: 120, pending: 12 }],
    rules: ['국민연금 가입자 수는 사업장 전체 직원 수가 아니다.'],
    sites: [
      { id: 's1', company: '현대제철', name: '현대제철(주)포항1공장', region: '47111', status: '1',
        history: { 202609: { members: 1150, acq: 4, loss: 106 }, 202608: { members: 1252 }, 202509: { members: 1300 } } },
      { id: 's2', company: '기아', name: '기아(주)AutoLand화성', region: '41591', status: '1', history: { 202609: { members: 11560, acq: 49, loss: 75 }, 202608: { members: 11586 } } },
      { id: 's3', company: '현대제철', name: '현대제철 순천공장', region: '12150', status: '1', history: { 202609: { members: 310 } } }],
    projects: [
      { id: 'p1', company: '현대제철', title: '현대제철 당진 전기로 신설공사', names: ['(주)대한건설/일용/현대제철 당진 전기로 신설공사'], sites: 1, month: '202609', tier: 'A', adptDt: '20260905', members: 41, baseline: false },
      { id: 'p2', company: '기아', title: '기아 오토랜드 화성 PBV 2공장 신축공사', names: ['삼우기전/상용/기아 오토랜드 화성 PBV 2공장 신축공사'], sites: 7, month: '202609', tier: 'A', baseline: true },
      { id: 'p3', company: '기아', title: '기아 화성 전기공사', names: ['영일전설/일용/기아 화성 전기공사'], sites: 1, month: '202609', tier: 'B', baseline: true }],
    events: [
      { id: 'wf:delta:s1:202609', kind: '인력 감소', tier: 'A', company: '현대제철', month: '202609', detectedAt: recent,
        text: '현대제철(주)포항1공장(경북 시군구코드 111) 국민연금 가입자 1,252→1,150명(-102명, -8.1%) · 그달 신규 취득 4·상실 106 — 2026-09 자료' },
      { id: 'wf:projs:기아:202609:3', kind: '새 공사 현장 묶음', tier: 'B', company: '기아', month: '202609', detectedAt: recent, text: '기아 이름이 든 새 공사 3건' }] };
  const post = await worker.fetch(new Request(ORIGIN + '/ingest/kr-workforce', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {});
  assert.equal(post.status, 200);
  const opts = { path: `/mcp/${TOKEN}`, env };
  const r = await call('kr_official', { section: 'workforce' }, opts);
  assert.match(r.text, /\[사업장 인력\(국민연금 가입 사업장\) · 자료 2026-09/);
  assert.match(r.text, /남은 채우기 12곳/);
  assert.match(r.text, /자사 사업장 3곳\(지난달 비교 가능 2곳 · 1년 전 비교 가능 1곳\)/);
  assert.match(r.text, /현대제철 · 현대제철\(주\)포항1공장 · 가입자 1,150명 \(지난달 -102, -8\.1%\) · 1년 전 1,300명 대비 -11\.5% · 그달 취득 4·상실 106 · 3개월 보관/);
  assert.ok(r.text.indexOf('포항1공장 · 가입자') < r.text.indexOf('AutoLand화성 · 가입자'));
  assert.match(r.text, /현대제철 순천공장 · 가입자 310명 \(지난달 미수집\)/);
  assert.match(r.text, /새로 잡힌 1건 · 첫 조회 기준선 2건\(투자 낱말 1\)/);
  assert.match(r.text, /A · 현대제철 · 「현대제철 당진 전기로 신설공사」 · 현장 1곳 · 2026-09 자료 · 첫 현장 적용 20260905 · 가입자 41명/);
  assert.match(r.text, /\[기준선\] A · 기아 · 「기아 오토랜드 화성 PBV 2공장 신축공사」 · 현장 7곳/);
  assert.doesNotMatch(r.text, /기아 화성 전기공사/);
  const kia = await call('kr_official', { section: 'workforce', company: '기아' }, opts);
  assert.doesNotMatch(kia.text, /포항1공장/);
  const today = await call('radar_today', {}, opts);
  const a = today.text.split('[A · ')[1].split('[B · ')[0];
  assert.match(a, /사업장 인력\(국민연금\)[\s\S]*국민연금 가입자 1,252→1,150명/);
  const b = today.text.split('[B · ')[1].split('[C · ')[0];
  assert.match(b, /기아 이름이 든 새 공사 3건/);
});

test('kr_official stacks: plants with stopped stacks first, events, young sites not judged; radar_today A for a plant-wide stop', async () => {
  const env = PRIVATE().env;
  const recent = new Date(Date.now() - 3600000).toISOString();
  const doc = { schema: 'kr_stacks/v1', generatedAt: '2026-10-31T09:20:00+09:00', status: 'complete', baselineSince: '2026-10-30T12:20:00+09:00',
    checks: [{ source: '굴뚝 자동측정(CleanSYS)', status: 'ok', returned: 3, terms: '24/24' }], rules: ['배출구 이름·설비 종류는 자료에 없다(번호만).'],
    sites: [
      { id: 'a', company: '현대제철', name: '현대제철㈜포항2공장', area: '경상북도', meaningful: 2, stopped: ['1', '2'],
        stacks: { 1: { lastDt: '2026-10-31 09:00', obs: Array(9).fill(['x', 0]) }, 2: { lastDt: '2026-10-31 09:00', obs: Array(9).fill(['x', 0]) } } },
      { id: 'b', company: '포스코', name: '㈜포스코 광양제철소', area: '전라남도', meaningful: 150, stopped: ['17'], stacks: { 17: { lastDt: '2026-10-31 09:00', obs: Array(9).fill(['x', 0]) } },
        exceedLog: [{ stack: '40', pollutant: 'nox', value: 61.2, limit: 50, at: '2026-10-31 06:00' }, { stack: '40', pollutant: 'nox', value: 70.5, limit: 50, at: '2026-10-31 09:00' }] },
      { id: 'c', company: '고려아연', name: '고려아연㈜온산제련소', area: '울산광역시', meaningful: 0, stopped: [], stacks: { 11: { obs: [['x', 5]] } } }],
    events: [{ id: 'stk:down:a:2026-10-31', kind: '사업장 가동 중단 신호', tier: 'A', company: '현대제철', site: '현대제철㈜포항2공장', detectedAt: recent,
      text: '현대제철㈜포항2공장: 평소 움직이던 배출구 2개 중 2개가 3번 연속 평소의 10% 아래' },
      { id: 'stk:exceed2:b:40:nox:2026-10-31 06:00', kind: '배출허용기준 초과 지속', tier: 'A', company: '포스코', site: '㈜포스코 광양제철소', detectedAt: recent,
        text: '㈜포스코 광양제철소 배출구 40번 질소산화물 측정값 70.5이 배출허용기준 50을 넘음(기준의 1.4배, 측정 2026-10-31 09:00) — 2026-10-31 06:00 측정부터 이 감시의 실행 2번 연속 초과(처음 61.2)' }] };
  const post = await worker.fetch(new Request(ORIGIN + '/ingest/kr-stacks', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {});
  assert.equal(post.status, 200);
  const opts = { path: `/mcp/${TOKEN}`, env };
  const r = await call('kr_official', { section: 'stacks' }, opts);
  assert.match(r.text, /\[굴뚝 측정\(공장 가동 신호\) · 출입처 사업장 3곳 · 배출구 4개/);
  assert.match(r.text, /멈춤으로 판단한 배출구가 있는 사업장 2곳/);
  assert.ok(r.text.indexOf('포항2공장(경상북도)') < r.text.indexOf('광양제철소(전라남도)'));  // 멈춘 비율 높은 순
  assert.match(r.text, /평소 움직이던 배출구 2개 중 멈춤 2개: 1번\(측정 2026-10-31 09:00\), 2번/);
  assert.match(r.text, /관측이 아직 6번이 안 된 사업장 1곳/);
  assert.match(r.text, /A · .* · 사업장 가동 중단 신호 · 현대제철/);
  assert.match(r.text, /- 배출허용기준 넘은 측정값\(이 감시가 본 것, 사업장마다 최근 20건\) 2건\n  2026-10-31 09:00 · 포스코 · ㈜포스코 광양제철소 배출구 40번 질소산화물 70\.5\(기준 50\)/);
  assert.match(r.text, /기준 초과 값은 확정 전 실시간 값/);
  const today = (await call('radar_today', {}, opts)).text;
  const a = today.split('[A · ')[1].split('[B · ')[0];
  assert.match(a, /굴뚝 측정\(공장 가동 신호\)[\s\S]*포항2공장: 평소 움직이던 배출구 2개 중 2개/);
  assert.match(a, /광양제철소 배출구 40번 질소산화물 측정값 70\.5이 배출허용기준 50을 넘음/);
});

test('radar_today: scoop candidates count as new only when first screened inside the window', async () => {
  const env = PRIVATE().env;
  const now = Date.now();
  const iso = (h) => new Date(now - h * 3600000).toISOString();
  const doc = { schema: 'scoop_screen/v1', generatedAt: iso(1), counts: {}, candidates: [
    { id: 'clue:old', kind: '특허', company: '현대제철', title: '상변태 기반 판재 냉각 제어 장치 및 방법 (현대제철)', verdict: '미보도 후보', published: '2026-10-07', firstSeen: iso(24 * 9) },
    { id: 'clue:new', kind: '단서', company: '기아', title: '기아 · 신규시설투자등', verdict: '미보도 후보', published: '2026-10-30', firstSeen: iso(2) },
    { id: 'clue:legacy', kind: '단서', company: '포스코', title: '포스코 · 단일판매ㆍ공급계약체결', verdict: '미보도 후보', published: '2026-10-29' }] };
  const post = await worker.fetch(new Request(ORIGIN + '/ingest/scoop-screen', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {});
  assert.equal(post.status, 200);
  const r = await call('radar_today', {}, { path: `/mcp/${TOKEN}`, env });
  const a = r.text.split('[A · ')[1].split('[B · ')[0];
  assert.match(a, /기아 · 신규시설투자등/);
  assert.match(a, /포스코 · 단일판매ㆍ공급계약체결/);  // 시각이 없는 옛 결과는 그대로 보인다
  assert.doesNotMatch(a, /상변태 기반 판재 냉각/);
  const s = await call('scoop_screen', {}, { path: `/mcp/${TOKEN}`, env });
  assert.match(s.text, /상변태 기반 판재 냉각/);  // 후보 목록에는 남는다
});

test('scoop candidates: a correction filing shows what changed before the same-counterparty comparison', async () => {
  const env = PRIVATE().env;
  const now = Date.now();
  const iso = (h) => new Date(now - h * 3600000).toISOString();
  // 10-31 운영: 효성중공업 Statnett 정정 — 실제 정정은 계약금액 -0.5%, 같은 상대의 다른 계약 비교가 '-71%'로 보였다
  const line = '정정(계약 사양 일부 변경에 따른 계약금액 조정): 계약내역 - 계약금액(원) 113,586,046,173원(약 1,136억원) → 113,044,698,813원(약 1,130억원)(-0.5%)';
  const doc = { schema: 'scoop_screen/v1', generatedAt: iso(1), counts: {}, candidates: [
    { id: 'clue:hy', kind: '단서', company: '효성중공업', title: '효성중공업 · [기재정정]단일판매ㆍ공급계약체결', verdict: '미보도 후보', published: '2026-10-27',
      firstSeen: iso(2), url: 'https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261027800518',
      filing: { type: '공급계약', facts: [['체결계약명', '420kV 변압기 등 공급계약']], correctionLine: line,
        correctionShort: '정정: 계약금액 1,136억→1,130억(-0.5%) · 매출액대비 3.24→3.22 · 문구 1곳',
        compare: ['같은 계약상대의 다른 계약 직전 공시 2026-09-30(접수 20260930800924, 계약일 2025-06-01 ↔ 이번 2023-11-08) · 금액 383,338,819,710원(약 3,833억원)'] } }] };
  await worker.fetch(new Request(ORIGIN + '/ingest/scoop-screen', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {});
  const s = await call('scoop_screen', {}, { path: `/mcp/${TOKEN}`, env });
  assert.match(s.text, /정정 내용\(원문 정정 표\): 정정\(계약 사양 일부 변경에 따른 계약금액 조정\): 계약내역 - 계약금액\(원\) 113,586,046,173원/);
  assert.ok(s.text.indexOf('정정 내용') < s.text.indexOf('직전 비교'));
  const r = await call('radar_today', {}, { path: `/mcp/${TOKEN}`, env });
  assert.match(r.text, /효성중공업 · \[기재정정\]단일판매ㆍ공급계약체결 \(단서\) — 보도 대조 '미보도 후보' · 체결계약명 420kV 변압기 등 공급계약 · 정정: 계약금액 1,136억→1,130억\(-0\.5%\) · 매출액대비 3\.24→3\.22 · 문구 1곳/);
  assert.match(r.text, /· 같은 계약상대의 다른 계약 직전 공시 2026-09-30/);
  // 정정 중 큰 변경은 '관련 보도 있음'이어도 B(10-31 두산 영광 야월 EPC 종료일 +7개월)
  doc.candidates.push({ id: 'clue:ds', kind: '단서', company: '두산에너빌리티', title: '두산에너빌리티 [기재정정]단일판매ㆍ공급계약체결 — 변경 항목 대조 필요', verdict: '관련 보도 있음',
    published: '2026-10-26', firstSeen: iso(2), url: 'https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261026800529',
    filing: { type: '공급계약', facts: [['체결계약명', '영광 야월 해상풍력 발전소 설계 구매 시공 (EPC) 계약']], correctionShort: '정정: 계약기간종료일 2029-07-01→2030-01-28',
      correction: { reason: '계약기간 종료일 변경', changes: [['계약기간종료일', '2029-07-01', '2030-01-28']], material: ['계약기간종료일 +7개월'] } } },
  { id: 'clue:hy2', kind: '단서', company: '효성중공업', title: '효성중공업 · 작은 정정', verdict: '관련 보도 있음', published: '2026-10-27', firstSeen: iso(2),
    filing: { type: '공급계약', facts: [], correction: { reason: 'x', changes: [] } } });
  await worker.fetch(new Request(ORIGIN + '/ingest/scoop-screen', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {});
  const r2 = await call('radar_today', { include_minor: true }, { path: `/mcp/${TOKEN}`, env });
  const b2 = r2.text.split('[B · ')[1].split('[C · ')[0];
  assert.match(b2, /두산에너빌리티 \[기재정정\]단일판매ㆍ공급계약체결 — 정정 중 큰 변경\(계약기간종료일 \+7개월 · 사유 '계약기간 종료일 변경'\)[^\n]*정정: 계약기간종료일 2029-07-01→2030-01-28[^\n]*원 계약 기사일 수 있음/);
  assert.match(r2.text.split('[C · ')[1], /관련 보도 있음: 효성중공업 · 작은 정정/);
  // 정정 내용 보도 대조(scoop_screen check_corrections) 결과가 있으면 그 결과로 바꿔 적는다
  doc.candidates[1].correctionCheck = { word: '연장', subject: ['영광', '야월'], since: '2026-10-26', verdict: '미보도 후보',
    queries: ['두산에너빌리티 영광 야월', '두산에너빌리티 야월 연장'], evidence: [{ title: '두산에너빌리티 해상풍력 공사기간 연장', date: '2026-10-27',
      channel: 'naver', url: 'https://n/other', why: '제목에 회사·낱말(연장)이 있으나 영광·야월 없음 — 다른 사업장·다른 건 기사일 수 있음' }], channels: { naver: 'ok' } };
  await worker.fetch(new Request(ORIGIN + '/ingest/scoop-screen', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {});
  const r3 = await call('radar_today', {}, { path: `/mcp/${TOKEN}`, env });
  assert.match(r3.text, /정정 내용 보도 대조: 미보도 후보 — "두산에너빌리티 영광 야월", "두산에너빌리티 야월 연장"로 2026-10-26 이후 '연장' 기사 못 찾음\(검색 범위 결과, 단독 판정 아님\)/);
  assert.doesNotMatch(r3.text, /정정 내용 보도 여부는 따로 확인/);
  assert.doesNotMatch(r3.text, /변경 항목 대조 필요/);  // 정정 표를 읽었으면 단서 제목 꼬리는 뺀다
  const s3 = await call('scoop_screen', { company: '두산' }, { path: `/mcp/${TOKEN}`, env });
  assert.match(s3.text, /잡힌 사실: 두산에너빌리티 \[기재정정\]단일판매ㆍ공급계약체결 \(단서/);
  assert.match(s3.text, /정정 내용 보도 대조\(정정 중 큰 변경 → '연장' 낱말\): 미보도 후보 — 질의 "두산에너빌리티 영광 야월", "두산에너빌리티 야월 연장" · 2026-10-26 이후 · 제목에 회사·'연장', 제목·요약에 영광·야월/);
  assert.match(s3.text, /↳ 2026-10-27 \[naver\] 두산에너빌리티 해상풍력 공사기간 연장 — 제목에 회사·낱말\(연장\)이 있으나 영광·야월 없음/);
  doc.candidates[1].correctionCheck = { ...doc.candidates[1].correctionCheck, verdict: '관련 보도 있음', evidence: [{ title: '두산에너빌리티, 영광 야월 해상풍력 계약기간 7개월 연장',
    date: '2026-10-29', channel: 'naver', url: 'https://n/hit', why: '제목에 회사·낱말(연장) — 동일 사건 미확정' }] };
  await worker.fetch(new Request(ORIGIN + '/ingest/scoop-screen', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {});
  const r4 = await call('radar_today', {}, { path: `/mcp/${TOKEN}`, env });
  assert.match(r4.text, /정정 내용 보도 대조: 관련 보도 있음 — 2026-10-29 「두산에너빌리티, 영광 야월 해상풍력 계약기간 7개월 연장」\(같은 내용인지 열어 볼 것\)/);
});

test('converging signals: same beat company and same city from two or more watches, place from the text, C and other tools ignored', () => {
  const t = (h) => new Date(Date.parse('2026-10-30T03:00:00Z') - h * 3600000).toISOString();
  const items = [
    { id: 'b1', tier: 'B', tool: 'kr_official', watch: '공장 부지 건축허가', company: '기아', date: '2026-10-22', fact: '건축허가: 기아 부지(경기도 화성시 우정읍) · 신축 공장' },
    { id: 'l1', tier: 'A', tool: 'kr_official', watch: '지자체 고시·공고', company: '기아', date: '2026-10-29', fact: '화성시 고시 「기아 오토랜드 화성 PBV 2공장 도시계획시설 결정」' },
    { id: 'w1', tier: 'A', tool: 'kr_official', watch: '사업장 인력(국민연금)', company: '기아', date: t(2), fact: '「AutoLand 화성 기아 LW 프로젝트」 · 첫 현장 적용 2026-10-05' },
    { id: 's1', tier: 'B', tool: 'kr_official', watch: '굴뚝 측정(공장 가동 신호)', company: '현대제철', date: t(3), fact: '현대제철㈜: 배출구 2개가 3번 연속 평소의 10% 아래' },
    { id: 'l2', tier: 'B', tool: 'kr_official', watch: '지자체 고시·공고', company: '현대제철', date: '2026-10-25', fact: '당진시 공고 「현대제철㈜ 전기로 설치 관련 공유수면 점용」' },
    { id: 'c1', tier: 'C', tool: 'kr_official', watch: '지자체 고시·공고', company: '포스코', date: '2026-10-25', fact: '포항시 고시 「영일만 산업단지」' },
    { id: 'p1', tier: 'B', tool: 'kr_official', watch: '공장 부지 건축허가', company: '포스코', date: '2026-10-25', fact: '건축허가: 포스코 부지(경상북도 포항시)' },
    { id: 'x1', tier: 'A', tool: 'us_recalls', watch: '미국 리콜', company: '기아', date: '2026-10-29', fact: '화성 공장 생산 차량 리콜' },
    { id: 'n1', tier: 'B', tool: 'kr_official', watch: '공장등록·관보', company: '현대차', date: '2026-10-29', fact: '공장 등록 내용 변경(주소 없음)' }];
  const g = convergence(items, { cut: Date.parse('2026-10-29T15:00:00Z') });
  assert.deepEqual(g.map((x) => [x.company, x.place, x.watches.length, x.fresh]), [['기아', '화성', 3, true], ['현대제철', '당진', 2, true]]);
  assert.ok(!g[0].items.some((x) => x.id === 'x1'));  // 미국 리콜은 장소 묶음 대상이 아님
  assert.ok(!g.some((x) => x.company === '포스코'));  // C는 세지 않아 감시 한 곳뿐
});

test('converging signals: background (workforce project, recent permit, stopped stack) joins a fresh item but never forms a group alone', () => {
  const now = Date.parse('2026-10-30T03:00:00Z');
  const docs = {
    'kr-workforce': { projects: [{ id: 'p1', company: '기아', title: 'AutoLand 화성 기아 LW 프로젝트', sites: 46, tier: 'A', firstSeen: '2026-10-30T09:43:00+09:00' },
      { id: 'p2', company: '현대제철', title: '현대제철 당진 유틸리티설비 증설공사', sites: 3, tier: 'A', firstSeen: '2026-10-30T09:43:00+09:00' }] },
    'kr-building': { permits: [{ id: 'bd1', company: '현대제철', kind: '새 허가', tier: 'B', permitted: '2026-09-22', plot: '전남광주통합특별시 순천시 해룡면 신성리 897번지', archGbCdNm: '신축' }] },
    'kr-stacks': { generatedAt: '2026-10-30T12:20:00+09:00', sites: [{ id: 's1', company: '현대제철', name: '현대제철㈜', stopped: ['1', '2', '3'], meaningful: 60 },
      { id: 's2', company: '포스코', name: '㈜포스코 광양제철소', stopped: ['129', '135'], meaningful: 137 },  // 10-31 운영: 137개 중 2개 — 배경 아님
      { id: 's3', company: '영풍', name: '㈜영풍석포제련소', stopped: ['3'], meaningful: 4 }] } };  // 작은 사업장은 하나도 배경
  const bg = background(docs, now);
  assert.equal(bg.length, 5);
  assert.deepEqual(bg.filter((x) => x.id.startsWith('bg:stk:')).map((x) => x.id), ['bg:stk:s1', 'bg:stk:s3']);
  const fresh = [{ id: 'l1', tier: 'A', tool: 'kr_official', watch: '지자체 고시·공고', company: '기아', date: '2026-10-29', fact: '화성시 고시 「기아 오토랜드 화성 PBV 2공장」' }];
  const g = convergence([...fresh, ...bg], { cut: Date.parse('2026-10-29T03:00:00Z') });  // 10-29 12:00 KST(24시간 창)
  assert.deepEqual(g.map((x) => [x.company, x.place, x.watches.length, x.fresh]), [['기아', '화성', 2, true]]);
  assert.equal(convergence([...fresh, ...bg], { cut: Date.parse('2026-10-29T15:00:00Z') })[0].fresh, false);  // 10-30 00:00 KST부터면 10-29 공고는 새 항목 아님
  // 당진: 공사 현장 + 멈춘 굴뚝은 둘 다 배경이라 묶지 않는다
  assert.ok(!g.some((x) => x.place === '당진'));
});

test('converging signals: the new item comes first and background from one watch is one line (10-31 금호타이어 함평)', () => {
  const g = { company: '금호타이어', place: '함평', items: [
    { id: 'bg:wf:a', background: true, tier: 'A', watch: '사업장 인력(국민연금)', date: '2026-10-30T09:43:00+09:00', fact: '국민연금 공사 현장 「금호타이어함평공장정련동외철근콘크리트공사」 현장 1곳' },
    { id: 'bg:wf:b', background: true, tier: 'A', watch: '사업장 인력(국민연금)', date: '2026-10-30T09:43:00+09:00', fact: '국민연금 공사 현장 「금호타이어 함평공장 정련동 외 건설공사」 현장 1곳' },
    { id: 'bg:wf:c', background: true, tier: 'B', watch: '사업장 인력(국민연금)', date: '2026-10-30T09:43:00+09:00', fact: '국민연금 공사 현장 「금호타이어 함평공장 정련동의 건설공사」 현장 1곳' },
    { id: 'clue:f42', tier: 'B', watch: '단독 후보 심사', date: '2026-10-27', fact: '금호타이어 · [기재정정]유형자산취득결정(자율공시) · 취득물건명 전라남도 함평군 빛그린국가산업단지' }] };
  const { rows, more } = convergenceRows(g);
  assert.equal(more, 0);
  assert.deepEqual(rows.map((x) => x.id), ['clue:f42', 'bg:wf:a 외 2']);
  assert.equal(rows[1].fact, '국민연금 공사 현장 3건 · 「금호타이어함평공장정련동외철근콘크리트공사」 · 「금호타이어 함평공장 정련동 외 건설공사」 · 「금호타이어 함평공장 정련동의 건설공사」');
  assert.ok(rows[1].background);
  // 배경이 한 건이면 그대로, 새 신호가 많으면 배경이 뒤로 밀려 '더' 줄로 센다
  const many = { items: [...[1, 2, 3, 4].map((i) => ({ id: `n${i}`, tier: 'B', watch: `감시${i}`, date: `2026-10-2${i}`, fact: `새 항목 ${i}` })), g.items[0]] };
  const r2 = convergenceRows(many);
  assert.deepEqual(r2.rows.map((x) => x.id), ['n4', 'n3', 'n2', 'n1']);
  assert.equal(r2.more, 1);
});

test('radar_today shows converging signals above the tiers', async () => {
  const env = PRIVATE().env;
  const recent = new Date(Date.now() - 2 * 3600000).toISOString();
  const older = new Date(Date.now() - 5 * 86400000).toISOString();
  const post = (feed, doc) => worker.fetch(new Request(ORIGIN + `/ingest/${feed}`, { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {});
  await post('kr-local', { schema: 'kr_local/v1', generatedAt: recent, checks: [], items: [
    { id: 'local:화성시:1', city: '화성시', company: '기아', tier: 'A', title: '기아 오토랜드 화성 공장 증설 관련 도시관리계획 결정', date: older.slice(0, 10), firstSeen: older, url: 'https://e/1' }] });
  await post('kr-workforce', { schema: 'kr_workforce/v1', generatedAt: recent, month: '202610', sites: [], projects: [], checks: [], events: [
    { id: 'wf:proj:x', kind: '새 공사 현장', tier: 'A', company: '기아', month: '202610', detectedAt: recent, text: '「AutoLand 화성 기아 LW 프로젝트」 · 첫 현장 적용 2026-10-05' }] });
  const r = await call('radar_today', {}, { path: `/mcp/${TOKEN}`, env });
  assert.match(r.text, /\[겹친 신호 · 최근 14일 같은 출입처·같은 시군을 감시 여러 곳이 가리킴\] 1곳/);
  assert.match(r.text, /- \[새 항목 포함\] 기아 · 화성 — 감시 2곳\((사업장 인력\(국민연금\), 지자체 고시·공고|지자체 고시·공고, 사업장 인력\(국민연금\))\)/);
  assert.ok(r.text.indexOf('[겹친 신호') < r.text.indexOf('[A · '));
  // 새 신호가 모두 이미 보도된 묶음은 뒤로, 줄마다 보도 대조 결과(10-31 운영: 금호타이어 함평 부지 취득 완료 정정)
  await post('kr-local', { schema: 'kr_local/v1', generatedAt: recent, checks: [], items: [
    { id: 'local:화성시:1', city: '화성시', company: '기아', tier: 'A', title: '기아 오토랜드 화성 공장 증설 관련 도시관리계획 결정', date: older.slice(0, 10), firstSeen: older, url: 'https://e/1' },
    { id: 'local:당진시:2', city: '당진시', company: '현대제철', tier: 'A', title: '현대제철㈜ 당진 전기로 설치 공유수면 점용 허가', date: recent.slice(0, 10), firstSeen: recent, url: 'https://e/2' }] });
  await post('kr-workforce', { schema: 'kr_workforce/v1', generatedAt: recent, month: '202610', sites: [], projects: [], checks: [], events: [
    { id: 'wf:proj:x', kind: '새 공사 현장', tier: 'A', company: '기아', month: '202610', detectedAt: recent, text: '「AutoLand 화성 기아 LW 프로젝트」 · 첫 현장 적용 2026-10-05' },
    { id: 'wf:proj:y', kind: '새 공사 현장', tier: 'A', company: '현대제철', month: '202610', detectedAt: older, text: '「현대제철 당진 전기로 신설공사」 · 첫 현장 적용 2026-10-05' }] });
  await post('radar-check', { schema: 'radar_check/v1', generatedAt: recent, items: [
    { id: 'local:화성시:1', verdict: '관련 보도 있음', since: '2026-10-20', queries: ['기아 화성'], evidence: [], channels: {} },
    { id: 'wf:proj:x', verdict: '관련 보도 있음', since: '2026-10-20', queries: ['기아 화성'], evidence: [], channels: {} },
    { id: 'local:당진시:2', verdict: '미보도 후보', since: '2026-10-28', queries: ['현대제철 당진'], evidence: [], channels: {} }] });
  const r2 = await call('radar_today', {}, { path: `/mcp/${TOKEN}`, env });
  const conv = r2.text.split('[겹친 신호')[1].split('[A · ')[0];
  assert.ok(conv.indexOf('현대제철 · 당진') < conv.indexOf('기아 · 화성'));
  assert.match(conv, /기아 · 화성 — 감시 2곳\([^)]*\)\) · 새 신호는 모두 관련 보도 있음\(같은 사건인지 열어 볼 것\)/);
  assert.match(conv, /A · \[미보도 후보\] \d{4}-\d\d-\d\d · 지자체 고시·공고: 당진시/);
  assert.match(conv, /A · \[관련 보도 있음\] [^\n]*지자체 고시·공고: 화성시/);
  assert.doesNotMatch(conv, /현대제철 · 당진 — [^\n]*관련 보도 있음/);
  // 한 줄 요약은 ' · ' 구분에서 자른다(10-31 운영: '… · 취 · id')
  const line = "금호타이어 · [기재정정]유형자산취득결정(자율공시) — 정정 중 큰 변경(취득예정일자 -36개월 · 사유 '취득완료(취득가액 및 취득일자 확정)에 따른 정정') · 취득물건구분 토지 및 건물 · 취득물건명 전라남도 함평군 빛그린국가산업단지";
  assert.equal(clipAt(line, 110), "금호타이어 · [기재정정]유형자산취득결정(자율공시) — 정정 중 큰 변경(취득예정일자 -36개월 · 사유 '취득완료(취득가액 및 취득일자 확정)에 따른 정정') · 취득물건구분 토지 및 건물 …");
  assert.equal(clipAt('짧은 줄', 110), '짧은 줄');
});

test('workforce: a small rise is reference (C, no press check), a small drop stays B', async () => {
  const env = PRIVATE().env;
  const recent = new Date(Date.now() - 2 * 3600000).toISOString();
  const post = (feed, doc) => worker.fetch(new Request(ORIGIN + `/ingest/${feed}`, { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {});
  // 10-31 운영: 한화솔루션 울산1 +15명이 B '미보도 후보'(질의 '한화솔루션 채용')로 떴다. 예전 저장분은 tier B로 남아 있다.
  await post('kr-workforce', { schema: 'kr_workforce/v1', generatedAt: recent, month: '202609', sites: [], projects: [], checks: [], events: [
    { id: 'wf:delta:up', kind: '인력 변동', tier: 'B', company: '한화솔루션', month: '202609', detectedAt: recent,
      text: '한화솔루션(주) 울산1(울산광역시 남구 상개로) 국민연금 가입자 521→536명(+15명, +2.9%) · 그달 신규 취득 17·상실 4 — 2026-09 자료' },
    { id: 'wf:delta:down', kind: '인력 변동', tier: 'B', company: '기아', month: '202609', detectedAt: recent,
      text: '기아(주)AutoLand화성 국민연금 가입자 11,560→11,300명(-260명, -2.2%) — 2026-09 자료' }] });
  const r = await call('radar_today', { include_minor: true }, { path: `/mcp/${TOKEN}`, env });
  const b = r.text.split('[B · ')[1].split('[C · ')[0];
  const c = r.text.split('[C · ')[1];
  assert.match(b, /11,560→11,300명\(-260명/);
  assert.doesNotMatch(b, /521→536명/);
  assert.match(c, /521→536명\(\+15명/);
  const items = await (await radarItems(new Request(ORIGIN + '/ingest/radar-items?hours=72', { headers: { Authorization: `Bearer ${TOKEN}` } }), env, {})).json();
  assert.equal(items.items.find((x) => x.id === 'wf:delta:up'), undefined);
  assert.deepEqual(items.items.find((x) => x.id === 'wf:delta:down').check.terms, ['감원']);
});

test('us_litigation shows party cases by priority, folds routine ones, and lists ITC 337 names', async () => {
  const env = PRIVATE().env;
  const doc = { schema: 'us_litigation/v1', generatedAt: '2026-10-27T07:50:00+09:00', windowDays: 45, rules: ['당사자 목록에 출입처가 있는 사건만.'],
    checks: [{ source: 'CourtListener "POSCO"', status: 'ok', returned: 3 }, { source: 'CourtListener "Taihan"', status: 'failed', error: 'HTTP 429 호출 한도' }],
    cases: [
      { id: 'cl:4', beat: ['포스코'], caseName: 'POSCO v. United States', court: 'CIT', courtId: 'cit', docketNumber: '1:26-00123', dateFiled: '2026-09-29',
        category: '국제무역법원(무역구제 소송)', priority: 0, role: '원고', matchedParties: ['POSCO'], url: 'https://www.courtlistener.com/docket/4/x/', isNew: true },
      { id: 'cl:1', beat: ['현대차'], caseName: 'Summers v. Hyundai Motor America Inc', court: 'VAED', dateFiled: '2026-10-21', category: '소비자·제조물책임',
        priority: 3, role: '피고·기타 당사자', matchedParties: ['Hyundai Motor America Inc'], cause: '15:2301 Magnuson-Moss Warranty Act', url: 'https://x/1', isNew: false },
      { id: 'cl:75019340', beat: ['LS일렉트릭'], caseName: 'In re: LS Electric Co., Ltd.', court: 'CAFC', courtId: 'cafc', docketNumber: '27-1067', dateFiled: '2026-10-22',
        category: '연방순회항소법원', priority: 0, role: '원고', matchedParties: ['LS Electric Co., Ltd.'], url: 'https://cl/75019340', isNew: true,
        appealFrom: 'United States Patent and Trademark Office', caseType: 'BCA or PTO, Patent Trial and Appeal Board',
        summary: 'LS일렉트릭, 미국 특허청 특허심판원(PTAB) 결정에 불복해 연방순회항소법원에 항소(사건 27-1067, 2026-10-22 접수)' }],
    opinions: [{ id: 'op:11046079', beat: ['포스코'], courtId: 'cit', caseName: 'POSCO v. United States', docketNumber: '24-00006', dateFiled: '2026-10-27',
      role: '원고', url: 'https://www.courtlistener.com/opinion/11046079/posco-v-united-states/', pdf: 'https://www.cit.uscourts.gov/x.pdf', isNew: true,
      holding: "Sustaining the Department of Commerce's second remand redetermination in its countervailing duty order review of certain carbon and alloy steel cut-to-length plate from the Republic of Korea.",
      holdingKo: '유지', reading: '원고 쪽 청구가 받아들여지지 않았다는 뜻으로 읽힘(판결문 본문 확인 전)' }],
    itc: [{ id: 'fr:2026-1', date: '2026-10-15', stage: '조사 개시', title: 'Certain Automotive Headlamps; Notice of Institution of Investigation',
      url: 'https://www.federalregister.gov/d/2026-1', named: [{ company: '현대모비스', mentions: 1, lines: ['Hyundai Mobis Co., Ltd., Seoul, Republic of Korea'] }], isNew: true }] };
  const post = await worker.fetch(new Request(ORIGIN + '/ingest/us-litigation', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {});
  assert.equal(post.status, 200);
  const opts = { path: `/mcp/${TOKEN}`, env };
  const r = await call('us_litigation', {}, opts);
  assert.match(r.text, /질의 1\/2 정상 · 미확인\(0건 아님\): CourtListener "Taihan"\(HTTP 429 호출 한도\)/);
  assert.match(r.text, /\[신규\] 2026-09-29 · 국제무역법원\(무역구제 소송\) · 포스코\(원고\)/);
  assert.match(r.text, /잡힌 사실: CIT 1:26-00123 「POSCO v\. United States」 접수/);
  assert.match(r.text, /\[판결 · 국제무역법원·연방순회항소법원[^\]]*\] 1건/);
  assert.match(r.text, /\[신규\] 2026-10-27 · 국제무역법원 · 포스코\(원고\)/);
  assert.match(r.text, /요지\(판결문 원문\): "Sustaining the Department of Commerce's second remand redetermination[^"]*" → 낱말 풀이: 유지/);
  assert.match(r.text, /읽기\(가설\): 원고 쪽 청구가 받아들여지지 않았다는 뜻으로 읽힘\(판결문 본문 확인 전\)/);
  assert.match(r.text, /PDF https:\/\/www\.cit\.uscourts\.gov\/x\.pdf/);
  assert.ok(r.text.indexOf('[판결 ·') < r.text.indexOf('[사건 접수 ·'));
  assert.match(r.text, /한 줄: LS일렉트릭, 미국 특허청 특허심판원\(PTAB\) 결정에 불복해 연방순회항소법원에 항소\(사건 27-1067, 2026-10-22 접수\)/);
  assert.match(r.text, /원심 United States Patent and Trademark Office · 유형 BCA or PTO, Patent Trial and Appeal Board/);
  assert.doesNotMatch(r.text, /Summers/);
  assert.match(r.text, /일상 사건 1건 숨김/);
  assert.match(r.text, /\[신규\] 2026-10-15 · 조사 개시 · Certain Automotive Headlamps/);
  assert.match(r.text, /본문의 현대모비스\(1곳\): "Hyundai Mobis Co\., Ltd\., Seoul, Republic of Korea"/);
  const all = await call('us_litigation', { include_routine: true, company: '현대차' }, opts);
  assert.match(all.text, /Summers v\. Hyundai Motor America Inc/);
  assert.ok((await call('us_litigation', {}, PRIVATE())).isError);
});

test('kr_official shows factory changes, recent registrations and beat gazette notices', async () => {
  const env = PRIVATE().env;
  const recent = new Date(Date.now() - 3600000).toISOString();
  const doc = { schema: 'kr_official/v1', generatedAt: '2026-10-27T08:10:00+09:00', rules: ['공장등록 정보는 지자체 등록 기준이다.'],
    baselineSince: '2026-10-26T22:24:00+09:00',
    checks: [{ source: '공장등록 포스코', status: 'ok', returned: 4 }, { source: '관보 입법예고', status: 'failed', error: 'HTTP 500' },
      { source: '공장등록 이름 규칙 포스코', status: 'ok', returned: 2, dropped: 2 }],
    factories: [
      { id: 'fac:12', company: '현대차', cmpnyNm: '현대자동차(주)울산EV공장', rnAdres: '울산광역시 북구 염포로 700', registeredOn: '2026-09-15', employees: 2000,
        mainProductCn: '전기자동차', indutyNm: '승용차 제조업', tags: ['[최근 등록 2026-09-15]'] },
      { id: 'fac:1', company: '포스코', cmpnyNm: '(주)포스코 포항제철소', rnAdres: '경상북도 포항시', registeredOn: '1973-07-03', employees: 8000, tags: [] }],
    gazette: [{ id: 'gz:I2', date: '2026-10-24', org: '국토교통부', teams: ['자동차'], title: '국토교통부공고제2026-1500호(「자동차관리법 시행규칙」일부개정령안 입법예고)',
      url: 'https://gwanbo.go.kr/ezpdf/customLayout.jsp?contentId=C', isNew: true }],
    events: [{ id: 'fac:1:x', kind: '등록 내용 변경', company: '포스코', factoryId: 'fac:1', name: '(주)포스코 포항제철소', text: '고용 9,000→8,000명', detectedAt: recent }] };
  const post = await worker.fetch(new Request(ORIGIN + '/ingest/kr-official', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {});
  assert.equal(post.status, 200);
  const opts = { path: `/mcp/${TOKEN}`, env };
  const r = await call('kr_official', {}, opts);
  assert.match(r.text, /질의 1\/2 정상 · 미확인\(0건 아님\): 관보 입법예고\(HTTP 500\)/);
  assert.match(r.text, /포스코 · 등록 내용 변경\n   잡힌 사실: \(주\)포스코 포항제철소 · 경상북도 포항시 — 고용 9,000→8,000명/);
  assert.match(r.text, /\[최근 120일 등록 공장 · 등록일 기준\] 1곳 \(출입처 공장 전체 2곳\)/);
  assert.match(r.text, /\(기준선 2026-10-26 이후 감지된 새 공장/);
  assert.match(r.text, /2026-09-15 · 현대차 · 현대자동차\(주\)울산EV공장/);
  assert.match(r.text, /\[신규\] 2026-10-24 · 국토교통부 · 자동차/);
  assert.doesNotMatch(r.text.split('[최근 120일 등록 공장')[1].split('[관보')[0], /포항제철소/);  // 1973 registration is not recent
  const all = await call('kr_official', { section: 'factory', show_all: true }, opts);
  assert.match(all.text, /포스코 · \(주\)포스코 포항제철소 · 경상북도 포항시 · 고용 8000/);
  assert.doesNotMatch(all.text, /관보 입법예고 · 출입처/);
  assert.ok((await call('kr_official', {}, PRIVATE())).isError);
});

test('relay fetches only fixed trade-remedy hosts, only with the bearer token', async () => {
  const env = { MCP_ACCESS_TOKEN: TOKEN };
  const seen = [];
  const fetchMock = async (url, init) => { seen.push(url); return new Response('<table><tr><td>China, Korea</td></tr></table>', { status: 200 }); };
  const req = (target, headers = { Authorization: `Bearer ${TOKEN}` }, method = 'GET') =>
    new Request(`${ORIGIN}/ingest/relay?url=${encodeURIComponent(target)}`, { method, headers });
  const ok = await handleIngest(req('https://www.industry.gov.au/australian-trade-remedies-commission/trade-remedies-notices-trns'), env, { fetch: fetchMock });
  assert.equal(ok.status, 200);
  assert.equal(ok.headers.get('X-Relay-Status'), '200');
  assert.match(await ok.text(), /China, Korea/);
  assert.equal((await handleIngest(req('https://www.industry.gov.au/x', { Authorization: 'Bearer wrong-token-0123456789' }), env, { fetch: fetchMock })).status, 404);
  assert.equal((await handleIngest(req('https://evil.example.com/'), env, { fetch: fetchMock })).status, 403);
  assert.equal((await handleIngest(req('http://www.industry.gov.au/x'), env, { fetch: fetchMock })).status, 403);
  assert.equal((await handleIngest(req('https://www.industry.gov.au/x', undefined, 'POST'), env, { fetch: fetchMock })).status, 405);
  assert.equal(seen.length, 1);
  const down = await handleIngest(req('https://www.dgtr.gov.in/en/x'), env, { fetch: async () => { throw Object.assign(new Error('t'), { name: 'TimeoutError' }); } });
  assert.equal(down.status, 504);
});

test('radar_today merges the private watches, ranks new items and lists failed or stale watches first', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const post = async (feed, doc) => assert.equal((await worker.fetch(new Request(ORIGIN + `/ingest/${feed}`, { method: 'POST',
    headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  // NOW is Monday 2026-10-26 09:00 KST, so the default window is 72 hours (from 2026-10-23 09:00 KST).
  const base = '2026-10-20T21:00:00+09:00';
  await post('scoop-screen', { schema: 'scoop_screen/v1', generatedAt: '2026-10-26T07:10:00+09:00', counts: {},
    candidates: [{ id: 's1', verdict: '미보도 후보', team: '철강', company: '현대제철', title: '현대제철 당진 설비 변경', kind: '공시', url: 'https://dart/1' },
      { id: 's2', verdict: '미보도 후보', company: '포스코', title: '킬한 후보', url: 'https://dart/2' },
      { id: 's3', verdict: '관련 보도 있음', company: '기아', title: '이미 난 기사' }] });
  await post('kr-official', { schema: 'kr_official/v1', generatedAt: '2026-10-26T08:10:00+09:00', checks: [{ source: '공장등록 포스코', status: 'ok' }],
    factories: [{ id: 'fac:9', company: 'HL만도', cmpnyNm: '에이치엘만도(주)', rnAdres: '경기도 성남시', registeredOn: '2026-10-24', employees: 5, indutyNm: '기타 반도체소자 제조업' }],
    events: [{ id: 'fac:5:new', kind: '새 공장', company: '포스코', factoryId: 'fac:5', text: '(주)포스코 수소환원 공장 · 포항', detectedAt: '2026-10-25T08:10:00+09:00' }],
    gazette: [{ id: 'gz:1', date: '2026-10-24', org: '국토교통부', teams: ['자동차'], title: '「자동차관리법 시행규칙」 입법예고', firstSeen: base, url: 'https://gwanbo.go.kr/a' },
      { id: 'gz:0', date: '2026-10-10', org: '환경부', teams: ['화학'], title: '오래된 공고', firstSeen: base }] });
  await post('trade-remedy', { schema: 'trade_remedy/v1', generatedAt: '2026-10-26T07:40:00+09:00', checks: [{ source: '호주 TRN', status: 'failed', error: 'HTTP 520' }],
    quotas: [], events: [{ id: 'taric:099843:2026-10-01', pageId: 'taric', country: 'EU', label: 'EU 쿼터 099843 컬러강판(한국 전용) 소진', text: '[소진 2026-10-10]', url: 'https://ec.europa.eu/q', detectedAt: '2026-10-24T07:40:00+09:00' }],
    federalRegister: [{ id: 'fr:old', date: '2026-09-10', stage: '최종 판정', title: '오래된 고시', firstSeen: base },
      { id: 'fr:new', date: '2026-10-22', stage: '예비 판정', title: 'Certain Steel From Korea', firstSeen: '2026-10-25T07:40:00+09:00', named: [{ company: '현대제철' }], url: 'https://fr/new' }] });
  await post('us-litigation', { schema: 'us_litigation/v1', generatedAt: '2026-10-26T07:50:00+09:00', checks: [],
    cases: [{ id: 'cl:old', beat: ['포스코'], caseName: 'Old v. POSCO', category: '계약', priority: 1, dateFiled: '2026-09-29', firstSeen: base, role: '피고·기타 당사자' },
      { id: 'cl:4', beat: ['세아제강'], caseName: 'SeAH Steel Corporation v. United States', court: 'CIT', category: '국제무역법원(무역구제 소송)', priority: 0, role: '원고', dateFiled: '2026-10-23', firstSeen: '2026-10-25T10:00:00+09:00', url: 'https://cl/4' },
      { id: 'cl:9', beat: ['현대차'], caseName: 'Lee v. Hyundai Motor America', category: '소비자·제조물책임', priority: 3, role: '피고·기타 당사자', dateFiled: '2026-10-24', firstSeen: '2026-10-25T07:50:00+09:00' }], itc: [],
    opinions: [{ id: 'op:1', beat: ['포스코'], courtId: 'cit', caseName: 'POSCO v. United States', role: '원고', dateFiled: '2026-10-25', firstSeen: '2026-10-26T07:50:00+09:00',
      holding: "Sustaining the Department of Commerce's second remand redetermination in its countervailing duty order review.", holdingKo: '유지',
      reading: '원고 쪽 청구가 받아들여지지 않았다는 뜻으로 읽힘(판결문 본문 확인 전)', url: 'https://cl/op1' },
      { id: 'op:0', beat: ['현대제철'], courtId: 'cafc', caseName: 'Old v. United States', role: '피고·참가인 등', dateFiled: '2026-10-01', firstSeen: base }] });
  await post('us-comments', { schema: 'us_comments/v1', generatedAt: '2026-10-22T08:20:00+09:00', checks: [], items: [] });
  await post('page-watch', { schema: 'page_watch/v1', generatedAt: '2026-10-26T06:30:00+09:00', pages: [],
    events: [{ pageId: 'site:hyundaiusa.com', scope: 'site', company: '현대차', label: '현대차 미국 사이트 공통', detectedAt: '2026-10-25T18:30:00+09:00', added: { timing: ['Coming 2027'] } }] });
  await call('candidate_feedback', { item_id: 's2', verdict: '킬', reason: '이미 확인' }, opts);
  const r = await call('radar_today', {}, opts);
  assert.match(r.text, /최근 72시간\(월요일: 주말 포함\)/);
  assert.match(r.text, /\[먼저 볼 것: 수집 상태\]/);
  assert.match(r.text, /해외 파트너 공시: 결과 없음 — 미확인/);
  assert.match(r.text, /미 연방 의견서: ⚠ \d+시간 전 결과/);
  assert.match(r.text, /무역구제: 일부 실패 1건\(호주 TRN\)/);
  const a = r.text.split('[A · ')[1].split('[B · ')[0];
  assert.match(a, /현대제철 당진 설비 변경/);
  assert.match(a, /새 공장: \(주\)포스코 수소환원 공장/);
  assert.match(a, /공장 등록 에이치엘만도\(주\)/);
  assert.match(a, /EU 쿼터 099843 컬러강판\(한국 전용\) 소진/);
  assert.match(a, /국제무역법원\(무역구제 소송\) · 원고: CIT 「SeAH Steel Corporation v\. United States」/);
  assert.doesNotMatch(a, /킬한 후보|Old v\. POSCO|Old v\. United States/);
  assert.match(a, /국제무역법원 판결 「POSCO v\. United States」\(포스코 원고\) — 요지\(원문\) "Sustaining the Department of Commerce's second remand[^"]*" \(풀이: 유지\) · 원고 쪽 청구가/);
  const b = r.text.split('[B · ')[1].split('[C · ')[0];
  assert.match(b, /관보 입법예고 국토교통부/);
  assert.match(b, /미국 관보 예비 판정: Certain Steel From Korea — 본문에 현대제철/);
  assert.doesNotMatch(r.text, /오래된 고시|오래된 공고/);
  assert.match(r.text, /\[C · 참고\(접힘\)\] 3건/);
  const narrowed = await call('radar_today', { hours: 24, company: '세아' }, opts);
  assert.match(narrowed.text, /최근 24시간/);
  assert.match(narrowed.text, /SeAH Steel Corporation/);
  assert.doesNotMatch(narrowed.text, /현대제철 당진/);
  const minor = await call('radar_today', { include_minor: true }, opts);
  assert.match(minor.text, /Lee v\. Hyundai Motor America/);
  const pub = await rpc('tools/call', { name: 'radar_today', arguments: {} });
  assert.match(JSON.stringify(pub.body), /Unknown tool/);  // private path only
  const empty = await call('radar_today', {}, PRIVATE());
  assert.match(empty.text, /단독 후보 심사: 결과 없음 — 미확인/);
});

test('radar_today ranks EDGAR mentions by deal words and hides items the reporter already judged', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const post = async (feed, doc) => assert.equal((await worker.fetch(new Request(ORIGIN + `/ingest/${feed}`, { method: 'POST',
    headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  await post('partner-filings', { schema: 'partner_filings/v1', generatedAt: '2026-10-26T07:00:00+09:00', windowDays: 30, checks: [],
    items: [{ id: 'edgar:hig', source: 'EDGAR', filer: 'HARTFORD INSURANCE GROUP', beat: ['현대차'], date: '2026-10-25', title: '8-K EX-99.2',
        snippet: 'Corporate bonds: Hyundai Motor Manufacturing 4.3% 2031 ... fair value', url: 'https://sec/hig' },
      { id: 'edgar:acme', source: 'EDGAR', filer: 'ACME METALS', beat: ['현대제철'], date: '2026-10-25', title: '8-K',
        snippet: 'entered into a long-term supply agreement with Hyundai Steel Company', url: 'https://sec/acme' },
      { id: 'edgar:clf', source: 'EDGAR', filer: 'CLEVELAND-CLIFFS INC.  (CLF)', beat: ['포스코'], date: '2026-10-25', title: '8-K EX-99.1', dealNear: true,
        boilerplate: '출입처 이름이 전망·위험 고지 문구(risks and uncertainties 등)에만 나옴 — 새 거래 공시가 아님(이미 있던 약정 언급일 수 있음)',
        snippet: 'risks and uncertainties related to any potential transaction arising out of our Memorandum of Understanding with POSCO', url: 'https://sec/clf' }] });
  await post('scoop-screen', { schema: 'scoop_screen/v1', generatedAt: '2026-10-26T07:10:00+09:00', counts: {},
    candidates: [{ id: 'p1', verdict: '미보도 후보', company: '기아', title: '고정자 냉각 장치', kind: '특허' },
      { id: 'p2', verdict: '미보도 후보', company: '현대제철', title: '판재 냉각 제어', kind: '특허' },
      { id: 'rc1', verdict: '미보도 후보', company: '기아', title: '기아, 10월 30일 리콜 공지 1건 — [기아] 쏘렌토 - 저압연료라인 어셈블리 관련 리콜', kind: '리콜' }] });
  const r = await call('radar_today', {}, opts);
  const a = r.text.split('[A · ')[1].split('[B · ')[0];
  const b = r.text.split('[B · ')[1].split('[C · ')[0];
  assert.match(a, /ACME METALS: 8-K/);
  assert.doesNotMatch(a + b, /CLEVELAND-CLIFFS/);  // 위험 고지 문구 속 MOU 언급은 참고(C)
  assert.match(b, /HARTFORD INSURANCE GROUP: 8-K EX-99\.2 — 발췌에 계약·공급·합작 낱말 없음/);
  assert.match(b, /id p1/);  // 특허 공개 미보도 후보는 B(그 자체로 단독 아님, 10-31)
  assert.doesNotMatch(a, /고정자 냉각 장치/);
  assert.match(b, /고정자 냉각 장치 \(특허\) — 보도 대조 '미보도 후보' · 특허 공개만으로는 단독이 아님/);
  assert.doesNotMatch(a, /쏘렌토/);  // 국내 리콜 공지 미보도 후보도 B(공개 공지, 10-31)
  assert.match(b, /\[기아\] 쏘렌토 - 저압연료라인 어셈블리 관련 리콜 — 보도 대조 '미보도 후보' · 리콜 공지만으로는 단독이 아님/);
  const fb = await call('candidate_feedback', { verdict: '봤음', item_ids: ['p1', 'edgar:hig'] }, opts);
  assert.match(fb.text, /기록: \[봤음\] 2건 — 확인함\(판단 전\)/);
  await call('candidate_feedback', { item_id: 'p2', verdict: '보류', reason: '새 사실 붙으면' }, opts);
  const after = await call('radar_today', {}, opts);
  assert.doesNotMatch(after.text, /고정자 냉각 장치|HARTFORD|판재 냉각 제어/);
  assert.match(after.text, /판정한 3건 숨김: (봤음 2 · 보류 1|보류 1 · 봤음 2)/);
  const all = await call('radar_today', { include_judged: true }, opts);
  assert.match(all.text, /고정자 냉각 장치[\s\S]*id p1 〔판정: 봤음〕/);
  assert.ok((await call('candidate_feedback', { verdict: '씀' }, opts)).isError);  // ids and reason still required
});

test('Cloudflare cron asks GitHub to run each watch at its KST weekday slot and logs the result', async () => {
  assert.deepEqual(dueAt(new Date('2026-10-26T22:40:05Z')), ['trade-remedy.yml']);        // Tue 07:40 KST
  assert.deepEqual(dueAt(new Date('2026-10-26T22:10:30Z')), ['scoop-screen.yml']);
  assert.deepEqual(dueAt(new Date('2026-10-27T06:10:00Z')), ['scoop-screen.yml']);        // 15:10 KST
  assert.deepEqual(dueAt(new Date('2026-10-27T07:00:00Z')), []);                          // no slot (16:00 KST)
  assert.deepEqual(dueAt(new Date('2026-10-31T22:40:00Z')), []);                          // Sun 07:40 KST
  const opts = PRIVATE({ GITHUB_DISPATCH_TOKEN: 'ghp_test' });
  const seen = [];
  const fetchMock = async (url, init) => { seen.push({ url, init }); return new Response(null, { status: 204 }); };
  const res = await runSchedule(opts.env, new Date('2026-10-26T22:40:05Z'), { fetch: fetchMock });
  assert.deepEqual(res.map((e) => [e.workflow, e.status]), [['trade-remedy.yml', 'ok']]);
  assert.equal(seen[0].url, 'https://api.github.com/repos/shhong9173-art/seoul-reporting-radar/actions/workflows/trade-remedy.yml/dispatches');
  assert.equal(seen[0].init.headers.Authorization, 'Bearer ghp_test');
  assert.deepEqual(JSON.parse(seen[0].init.body), { ref: 'main' });
  const fail = await runSchedule(opts.env, new Date('2026-10-26T22:50:00Z'), { fetch: async () => new Response('{}', { status: 403 }) });
  assert.deepEqual(fail.map((e) => e.status), ['HTTP 403']);
  const none = PRIVATE();
  // Mon 2026-10-26 07:40 KST — the same KST day as the test clock (09:00 KST)
  const skipped = await runSchedule(none.env, new Date('2026-10-25T22:40:00Z'), { fetch: async () => { throw new Error('must not call'); } });
  assert.deepEqual(skipped.map((e) => e.status), ['no-token']);
  const today = await call('radar_today', {}, none);
  assert.match(today.text, /예약 요청\(Cloudflare\): 토큰 없음 — GitHub 예약만 사용 중\(지연 가능\) · 지금도 워커에서 GITHUB_DISPATCH_TOKEN이 보이지 않음/);
  // the reporter adds the secret after the morning slots: the line says so before the next slot comes round
  const later = await call('radar_today', {}, { ...none, env: { ...none.env, GITHUB_DISPATCH_TOKEN: 'ghp_test' } });
  assert.match(later.text, /예약 요청\(Cloudflare\): 오늘 앞선 칸은 토큰 없이 지나감 · 지금은 토큰 보임 — 다음 칸\(10-26 15:00 scoop-radar\.yml\)부터 요청/);
  assert.equal(nextSlot(new Date('2026-10-30T10:00:00Z')), '11-02 06:00 overseas-registry.yml');  // Fri 19:00 KST → Mon 06:00
  const fresh = await call('radar_today', {}, PRIVATE());
  assert.match(fresh.text, /예약 요청\(Cloudflare\): 기록 없음 · 지금도 워커에서 GITHUB_DISPATCH_TOKEN이 보이지 않음/);
  const freshWithToken = await call('radar_today', {}, PRIVATE({ GITHUB_DISPATCH_TOKEN: 'ghp_test' }));
  assert.doesNotMatch(freshWithToken.text, /예약 요청\(Cloudflare\)/);
});

test('DART lead facts and prior comparison show in scoop_screen, and routine filings drop to B in radar_today', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const doc = { schema: 'scoop_screen/v1', generatedAt: '2026-10-26T07:10:00+09:00', counts: { '미보도 후보': 2 }, candidates: [
    { id: 'clue:hde', verdict: '미보도 후보', team: '전력', company: 'HD현대일렉트릭', title: 'HD현대일렉트릭 · 타인에대한채무보증결정', kind: '단서',
      url: 'https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261026800468', channels: {}, queries: [],
      filing: { type: '채무보증', rcept_no: '20261026800468', facts: [['채무자', '유럽법인(HD Hyundai Electric Europe GmbH)'], ['채무보증금액(원)', '53,417,160,000원(약 534억원)'], ['자기자본대비(%)', '2.63']],
        related: null, compare: ['같은 채무자 직전 공시 2025-11-03(접수 20251103800200): 48,000,000,000원(약 480억원) → 53,417,160,000원(약 534억원)(+11%)'],
        routine: '같은 자회사 채무자 반복 보증 · 자기자본 대비 2.63%' } },
    { id: 'clue:kz', verdict: '미보도 후보', team: '철강', company: '고려아연', title: '고려아연 · 소송등의판결ㆍ결정', kind: '단서',
      url: 'https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261023801005', channels: {}, queries: [],
      filing: { type: '소송판결', facts: [['사건의명칭', '주주대표소송(손해배상)'], ['판결ㆍ결정내용', '[주문] 1. 원고 공동소송참가인의 공동소송참가신청을 각하한다. 2. 원고의 주위적 및 예비적 청구를 모두 기각한다.'], ['판결ㆍ결정일자', '2026-10-22']], related: '2026-06-10 소송 등의 제기ㆍ신청(경영권 분쟁 소송)',
        compare: ['최근 3년 같은 종류 공시 4건(정정 포함, 목록 기준)'], routine: null } }] };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/scoop-screen', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const s = await call('scoop_screen', {}, opts);
  assert.match(s.text, /원문 요점\(채무보증\): 채무자 유럽법인\(HD Hyundai Electric Europe GmbH\) · 채무보증금액\(원\) 53,417,160,000원\(약 534억원\) · 자기자본대비\(%\) 2\.63/);
  assert.match(s.text, /직전 비교: 같은 채무자 직전 공시 2025-11-03/);
  assert.match(s.text, /일상 공시로 보임: 같은 자회사 채무자 반복 보증/);
  assert.match(s.text, /회사가 적은 관련공시: 2026-06-10 소송 등의 제기ㆍ신청/);
  const r = await call('radar_today', {}, opts);
  const a = r.text.split('[A · ')[1].split('[B · ')[0];
  const b = r.text.split('[B · ')[1].split('[C · ')[0];
  assert.match(a, /고려아연 · 소송등의판결ㆍ결정 \(단서\) — 보도 대조 '미보도 후보' · 사건의명칭 주주대표소송\(손해배상\)/);
  assert.match(a, /판결ㆍ결정내용 \[주문\] 1\. 원고 공동소송참가인의 공동소송참가신청을 각하한다\. 2\. 원고의 주위적 및 예비적 청구를 모두… · 판결ㆍ결정일자/);  // clipped in the digest
  assert.match(s.text, /2\. 원고의 주위적 및 예비적 청구를 모두 기각한다\./);  // full in scoop_screen
  assert.doesNotMatch(a, /HD현대일렉트릭/);
  assert.match(b, /HD현대일렉트릭 · 타인에대한채무보증결정 — 일상 공시로 보임\(같은 자회사 채무자 반복 보증/);
});

test('weekly review groups judgments by watch and DART filing type, and keeps labels after the feed rolls over', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const post = async (feed, doc) => assert.equal((await worker.fetch(new Request(ORIGIN + `/ingest/${feed}`, { method: 'POST',
    headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const empty = await call('candidate_weekly_review', {}, opts);
  assert.match(empty.text, /판정 기록이 없다/);
  await call('candidate_feedback', { item_id: 'clue:late', verdict: '봤음' }, opts);  // judged before it was in any feed
  const guarantee = (n) => ({ id: `clue:g${n}`, verdict: '미보도 후보', company: 'HD현대일렉트릭', title: `HD현대일렉트릭 · 타인에대한채무보증결정 ${n}`, kind: '단서',
    url: `https://dart.fss.or.kr/dsaf001/main.do?rcpNo=2026102680046${n}`, filing: { type: '채무보증', facts: [], compare: [], routine: '같은 자회사 채무자 반복 보증 · 자기자본 대비 2.63%' } });
  await post('scoop-screen', { schema: 'scoop_screen/v1', generatedAt: '2026-10-26T07:10:00+09:00', counts: {}, candidates: [
    guarantee(1), guarantee(2), guarantee(3), guarantee(4), guarantee(5),
    { id: 'clue:kz', verdict: '미보도 후보', company: '고려아연', title: '고려아연 · 소송등의판결ㆍ결정', kind: '단서', url: 'https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261023801005',
      filing: { type: '소송판결', facts: [], compare: [], routine: null } },
    { id: 'clue:pd', verdict: '미보도 후보', company: 'GS', title: 'GS · [기재정정]주요사항보고서(유상증자결정)', kind: '단서', url: 'https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261020000111' },
    { id: 'clue:late', verdict: '미보도 후보', company: '기아', title: '고정자 냉각 장치', kind: '특허' }] });
  await post('partner-filings', { schema: 'partner_filings/v1', generatedAt: '2026-10-26T07:00:00+09:00', windowDays: 30, checks: [],
    items: [{ id: 'edgar:hig', source: 'EDGAR', filer: 'HARTFORD', beat: ['현대차'], date: '2026-10-25', title: '8-K', snippet: 'bonds', url: 'https://sec/hig' }] });
  const one = await call('candidate_feedback', { item_id: 'clue:g4', verdict: '보류', reason: '나중에' }, opts);
  assert.match(one.text, /기록: \[보류\] clue:g4 \(단독 후보 심사 · DART 채무보증 · B\) — 나중에/);
  await call('candidate_feedback', { item_ids: ['clue:g1', 'clue:g2', 'clue:g3', 'clue:g4'], verdict: '킬', reason: '자회사 보증 갱신' }, opts);
  await call('candidate_feedback', { item_id: 'clue:g5', verdict: '씀', reason: '보증 잔액 급증 박스' }, opts);
  await call('candidate_feedback', { item_id: 'clue:kz', verdict: '씀', reason: '판결 단신' }, opts);
  await call('candidate_feedback', { item_id: 'clue:pd', verdict: '보류', reason: '증자 규모 확인' }, opts);
  await call('candidate_feedback', { verdict: '봤음', item_ids: ['edgar:hig', 'gone:1'] }, opts);
  const r = await call('candidate_weekly_review', {}, opts);
  assert.match(r.text, /판정한 항목 10개: 씀 2 · 킬 4 · 보류 1 · 봤음 3 \(기록 11건, 같은 항목은 마지막 판정만 셈\)/);
  // 특허 미보도 후보(clue:late)는 B(10-31)
  assert.match(r.text, /- 단독 후보 심사 8 — 씀 2 · 킬 4 · 보류 1 · 봤음 1 \| A 2\(씀 1 · 보류 1\) · B 6\(씀 1 · 킬 4 · 봤음 1\)/);
  assert.match(r.text, /- 해외 파트너 공시 1 — 봤음 1 \| B 1\(봤음 1\)/);
  assert.match(r.text, /- 감시 미상\(지금 목록에 없음\) 1 — 봤음 1/);
  assert.match(r.text, /- 단독 후보 심사 · DART 채무보증 5 — 씀 1 · 킬 4 \| 일상\(B\) 5: 씀 1 · 킬 4/);
  assert.match(r.text, /- 단독 후보 심사 · DART 소송판결 1 — 씀 1/);
  assert.match(r.text, /- 단독 후보 심사 · DART 주요사항보고서\(유상증자결정\) 1 — 보류 1/);  // unsupported type grouped by report name
  assert.match(r.text, /- 단독 후보 심사 · 특허 1 — 봤음 1/);                           // labelled from the current list
  assert.match(r.text, /\[점검 후보\][\s\S]*단독 후보 심사 · DART 채무보증: 5개 중 킬 4 — 등급·문턱 점검 후보/);
  assert.match(r.text, /일상\(B\)으로 내렸는데 씀: HD현대일렉트릭 · 타인에대한채무보증결정 5 — 일상 판정 규칙 점검 후보/);
  assert.match(r.text, /킬 사유 상위: 자회사 보증 갱신\(4\)/);
  assert.match(r.text, /\[씀\] 단독 후보 심사 · DART 소송판결 · A · 고려아연 · 소송등의판결ㆍ결정 \(단서\) — 판결 단신 \(id clue:kz\)/);
  assert.match(r.text, /일부 항목은 판정 때 표시가 없어 지금 목록 기준/);
  assert.match(r.text, /자동으로 바꾸지 않는다/);
  // the scoop feed is replaced on the next run; stored labels stay, the never-labelled one falls back
  await post('scoop-screen', { schema: 'scoop_screen/v1', generatedAt: '2026-10-26T15:10:00+09:00', counts: {}, candidates: [] });
  const later = await call('candidate_weekly_review', {}, opts);
  assert.match(later.text, /- 단독 후보 심사 · DART 채무보증 5 — 씀 1 · 킬 4/);
  assert.match(later.text, /- 감시 미상\(지금 목록에 없음\) 2 — 봤음 2/);
});

test('kr_signals shows FTC decisions by role, KEPCO bids and commodity prices, and radar_today ranks them', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const doc = { schema: 'kr_signals/v1', generatedAt: '2026-10-26T08:30:00+09:00', baselineSince: '2026-10-20T08:30:00+09:00',
    checks: [{ source: '공정위 의결서', status: 'partial', listed: 68, decisions: 64, read: 40, pending: 24, kept: 4 },
      { source: '한전 전자입찰', status: 'unset', error: 'KEPCO_API_KEY 미설정' }, { source: 'KOMIS 아연', status: 'ok', rows: 714 }],
    rules: ['공정위 의결서는 의결일과 파일 등록이 다르다.'],
    decisions: [
      { id: 'ftc:약식2026-129', decisionNo: '약식2026-129', caseNos: ['2023유대1720'], name: '금호타이어(주)의 대리점법 등 위반행위에 대한 건', action: '시정명령',
        decidedOn: '2026-10-12', fileDate: '2026-10-24 10:59', flags: [], isNew: true, url: 'https://case.ftc.go.kr/ocp/co/openDocView.do?docTy=LTFR&docId=1',
        mentions: [{ company: '금호타이어', role: '피심인', related: false, snippet: '금호타이어 주식회사 광주광역시 광산구', orderAmounts: [] }], orderExcerpt: '1. 피심인은 …' },
      { id: 'ftc:의결2026-200', decisionNo: '의결2026-200', caseNos: ['2025국카2422'], name: '현대자동차(주) 및 기아(주) 발주 차량용 내장재 표면처리 입찰 관련 3개 사업자의 부당한 공동행위에 대한 건',
        action: '과징금', decidedOn: '2026-09-30', fileDate: '2026-10-23 10:00', flags: [], url: 'https://case.ftc.go.kr/x2',
        mentions: [{ company: '현대차', role: '발주처', related: false }, { company: '기아', role: '발주처', related: false }] },
      { id: 'ftc:의결2026-179', decisionNo: '의결2026-179', caseNos: ['2026국결1580'], name: '롯데케미칼 주식회사 등 4개 사업자의 기업결합 제한규정 위반행위에 대한 건',
        action: '시정명령', decidedOn: '2026-08-31', fileDate: '2026-10-24 14:10', flags: ['기업결합'], url: 'https://case.ftc.go.kr/x3',
        mentions: [{ company: '한화솔루션', role: '본문 언급', related: false }] },
      { id: 'ftc:결정2026-040', decisionNo: '결정2026-040', caseNos: ['2026기결0100'], name: '6개 강관 제조사의 부당한 공동행위에 대한 건 관련 현대제철(주)의 과징금 납부기한 연장 및 분할납부 신청에 대한 건',
        action: '인용', decidedOn: '2026-10-10', fileDate: '2026-10-23 09:00', flags: ['과징금 납부기한 연장·분할납부', '이의신청 재결'], note: '개방문서 없음(PDF만) — 사건명만 대조',
        url: 'https://case.ftc.go.kr/ocp/co/ltfr.do?caseNo=2026기결0100', mentions: [{ company: '현대제철', role: '사건명 언급', related: false }] }],
    kepco: [{ id: 'kepco:COM01:R26-1', no: 'R26-1', company: '한국전력공사', name: '154kV 지중 전력케이블 구매', price: 12300000000, big: true, noticeDate: '20261024', state: '공고진행' },
      { id: 'kepco:COM05:R26-3', no: 'R26-3', company: '한국중부발전', name: '배전용 변압기 단가계약', price: 900000000, big: false, noticeDate: '20261023', state: '마감' },
      ...[1, 2, 3].map((i) => ({ id: `kepco:COM01:L${i}`, no: `L${i}`, company: '한국전력공사', name: `(연간단가)고효율주상변압기,50KVA(광유)-2,338대-0${i}(일반)`,
        price: 4967081000, big: false, noticeDate: '20261024', state: '공고진행' }))],
    motir: [{ id: 'motir:172155', title: '무역위, 중국산 아연도금냉연, 옵셋인쇄판 덤핑조사 최종판정', kind: '보도자료', dept: '무역구제정책과', date: '2026-10-23',
        url: 'https://www.motir.go.kr/kor/article/ATCL3f49a5a8c/172155/view', embargo: null, companies: [] },
      { id: 'motir:172254', title: '2026년 9월 수출입 동향', kind: '보도자료', dept: '수출입과', date: '2026-10-24', url: 'https://www.motir.go.kr/x', companies: [],
        trade: { period: '2026-09', exports: { value: '1,209.4', yoy: '+83.5' }, items: { 자동차: { value: '61', yoy: '-5' }, 철강: { value: '22', yoy: '+3' } } } },
      { id: 'motir:172335', title: '자동차·가전부터 한우·수산물까지...최대 50% 할인', kind: '보도자료', dept: '유통물류과', date: '2026-10-25', companies: [],
        embargo: '27석간, 27일(화) 국무회의 종료시 엠바고', url: 'https://www.motir.go.kr/y' }],
    prices: [{ id: 'zinc', name: '아연', basis: 'LME CASH', unit: 'USD/ton', beats: ['고려아연', '영풍'], since: '2024-01-01',
      summary: { date: '2026-10-23', price: 3900, day: 2.9, week: 3.28, month: -3.94, monthFrom: '2026-09-25', ytd: 25.56, ytdFrom: '2026-01-02', stock: 166950, stockMonth: 37.29,
        high: { date: '2026-09-09', price: 4186 }, low: { date: '2024-02-14', price: 2285.5 }, span: ['2024-01-02', '2026-10-23'] },
      signals: [{ kind: 'LME 재고 큰 변동', text: '재고 121,600 → 166,950(+37.3%, 2026-09-25 대비)' }] }],
    events: [{ id: 'px:zinc:최고(기간):2026-10-23', kind: '원자재 가격', signal: '최고(기간)', commodity: 'zinc', company: '고려아연·영풍', detectedAt: '2026-10-25T15:20:00+09:00', text: '아연(LME CASH, USD/ton) 3,900.00 · 2025-03-03(4,000.00) 이후 최고 — 230일 만' },
      { id: 'px:zinc:LME 재고 큰 변동:2026-10-23', kind: '원자재 가격', signal: 'LME 재고 큰 변동', commodity: 'zinc', company: '고려아연·영풍', detectedAt: '2026-10-25T15:20:00+09:00', text: '아연 재고 +37.3%' }],
    confirmedScoops: 0 };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/kr-signals', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const k = await call('kr_signals', {}, opts);
  assert.match(k.text, /질의 1\/3 정상 · 미확인\(0건 아님\): 공정위 의결서\(partial, 전문 대기 24건\), 한전 전자입찰\(KEPCO_API_KEY 미설정\)/);
  assert.match(k.text, /\[공정위 의결서 · 의결일 또는 파일 등록 최근 60일 · 출입처가 피심인·발주처·사건명에 있는 것\] 3건/);
  assert.match(k.text, /\[신규\] 의결 2026-10-12 · 파일 등록 2026-10-24 10:59 · 시정명령[\s\S]*출입처: 금호타이어 피심인[\s\S]*원문 발췌: 금호타이어 주식회사/);
  assert.match(k.text, /출입처: 현대차 발주처 \/ 기아 발주처/);
  assert.doesNotMatch(k.text, /롯데케미칼/);  // body-only mention needs include_mentions
  assert.match((await call('kr_signals', { section: 'ftc', include_mentions: true }, opts)).text, /롯데케미칼/);
  assert.match(k.text, /⚠ 개방문서 없음\(PDF만\)/);
  assert.match(k.text, /\[한전 전자입찰\] 미설정 — GitHub Secrets에 KEPCO_API_KEY/);
  assert.match(k.text, /- 아연 LME CASH\(USD\/ton\) · 2026-10-23 3,900\n   전일 \+2\.9% · 1주 \+3\.28% · 한 달\(2026-09-25~\) -3\.94% · 연초\(2026-01-02~\) \+25\.56% · LME 재고 166,950\(한 달 \+37\.29%\)/);
  assert.match(k.text, /조회 범위\(2024-01-02~2026-10-23\) 최고 2026-09-09 4,186 · 최저 2024-02-14 2,285\.5/);
  const m = await call('kr_signals', { section: 'motir' }, opts);
  assert.match(m.text, /\[산업통상부 보도·참고자료 · 출입처 업종 낱말·출입처 이름 · 최근 60일\] 3건/);
  assert.match(m.text, /2026-10-25 · 유통물류과 · 보도자료 · 엠바고\(27석간, 27일\(화\) 국무회의 종료시 엠바고\)/);
  assert.match(m.text, /2026-09 수출 1,209\.4억달러\(\+83\.5%\) · 출입처 품목: 자동차 61억달러\(-5%\) · 철강 22억달러\(\+3%\)/);
  const r = await call('radar_today', {}, opts);
  assert.match(r.text, /공정위·한전·원자재: 미설정 한전 전자입찰\(KEPCO_API_KEY 미설정\) · 공정위 의결서 원문 대기 24건\(실행당 읽기 한도, 다음 실행에서 읽음\)/);
  assert.doesNotMatch(r.text, /공정위·한전·원자재: 일부 실패/);
  const a = r.text.split('[A · ')[1].split('[B · ')[0];
  const b = r.text.split('[B · ')[1].split('[C · ')[0];
  assert.match(a, /공정위 의결서\(시정명령, 의결 2026-10-12\): 금호타이어\(주\)의 대리점법 등 위반행위에 대한 건 — 금호타이어 피심인/);
  assert.match(a, /현대제철\(주\)의 과징금 납부기한 연장 및 분할납부 신청/);  // installment request by a beat company
  assert.match(b, /현대자동차\(주\) 및 기아\(주\) 발주[\s\S]*현대차 발주처, 기아 발주처/);
  assert.match(b, /한전 전자입찰 한국전력공사 「154kV 지중 전력케이블 구매」 · 추정가격 약 123억원 · 공고진행/);
  assert.match(b, /원자재 가격: 아연\(LME CASH, USD\/ton\) 3,900\.00 · 2025-03-03\(4,000\.00\) 이후 최고/);
  assert.match(b, /산업통상부 보도자료: 무역위, 중국산 아연도금냉연, 옵셋인쇄판 덤핑조사 최종판정/);
  assert.match(b, /산업통상부 보도자료: 2026년 9월 수출입 동향 — 2026-09 수출 1,209\.4억달러\(\+83\.5%\) · 자동차 61억달러\(-5%\) · 철강 22억달러\(\+3%\)/);
  assert.doesNotMatch(b, /한우·수산물/);  // topic word only (자동차 in a sale campaign) → C
  assert.doesNotMatch(a + b, /롯데케미칼|배전용 변압기|재고 \+37\.3%/);  // body mention, small bid, stock move → C
  const minor = await call('radar_today', { include_minor: true }, opts);
  assert.match(minor.text, /「\(연간단가\)고효율주상변압기,50KVA\(광유\)-2,338대-0\d\(일반\)」 외 같은 공고 2건\(합계 약 149억원\) · 추정가격 약 50억원/);
  assert.equal((minor.text.match(/고효율주상변압기/g) ?? []).length, 1);  // three lots, one line
  assert.match(r.text, /기자 전용 감시 22개/);
  assert.deepEqual(dueAt(new Date('2026-10-26T23:30:00Z')), ['kr-signals.yml', 'kipris-patent-hunt.yml']);  // Tue 08:30 KST
  assert.deepEqual(dueAt(new Date('2026-10-27T06:20:00Z')), ['kr-signals.yml']);  // Tue 15:20 KST
});

test('kr_stats shows KAIDA ranks, price and production series with signals, and radar_today ranks records above routine moves', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const series = (id, label, kind, unit, period, value, mom, yoy, signals, beats) => ({ id, source: kind === 'price' ? 'ECOS' : 'KOSIS', label, officialName: label.split(' ').pop(),
    unit, kind, beats, summary: { period, value, mom, yoy, high: { p: '2021-09', v: 169.92 }, low: { p: '2016-02', v: 70.56 }, span: ['2016-01', period] }, signals, points: [] });
  const doc = { schema: 'kr_stats/v1', generatedAt: '2026-10-26T07:30:00+09:00', checks: [{ source: 'ECOS 통계', status: 'ok', ok: 23, failed: 0 },
      { source: 'KOSIS 통계', status: 'ok', ok: 17, failed: 0 }, { source: 'KAIDA 수입 승용차 신규등록', status: 'ok', read: 2, months: 49, latest: '2026-09' }],
    rules: ['같은 품목·같은 지수 기준·같은 단위 안에서만 비교한다.'],
    series: [series('ppi-plate', '생산자물가 중후판', 'price', '2020=100', '2026-09', 150.84, 3.02, 12.38, [{ kind: '최고(기간)', text: '2023-10(153.04) 이후 최고 — 35개월 만' }], ['포스코', '현대제철']),
      series('ppi-switch', '생산자물가 전기개폐용스위치', 'price', '2020=100', '2026-09', 123.74, 0, 4.15, [], ['LS일렉트릭']),
      series('steel-80', '철강 생산 용융아연도강판(철강협회)', 'volume', '천톤', '2026-08', 789, 4.37, 17.76, [{ kind: '조회 범위 최고', text: '2016-01 이후 최고(조회 범위 안)' }], ['동국씨엠']),
      series('us-imp-8504', '미국 수입(한국산) 변압기·전력변환기(HS 8504)', 'trade', '백만달러', '2026-08', 169.83, -1.95, 31.2, [{ kind: '전년 대비 큰 변동', text: '전년 같은 달(2025-08, 129.4) 대비 +31.2%' }], ['HD현대일렉트릭', 'LS일렉트릭'])],
    kaidaMonths: {},
    kaida: { period: '2026-09', total: 34904, brands: [{ brand: 'Tesla', units: 12372, share: 35.45, rank: 1, prevRank: 1, yoy: 36.42 },
      { brand: 'BMW', beat: 'BMW코리아', units: 6066, share: 17.38, rank: 2, prevRank: 2, yoy: -8.23 },
      { brand: 'Mercedes-Benz', beat: '메르세데스-벤츠 코리아', units: 5477, share: 15.69, rank: 3, prevRank: 3, yoy: -20.67 }],
      signals: [{ brand: 'BMW', kind: '최저(기간)', text: 'BMW 신규등록 6,066대 · 2025-01(5,960) 이후 최저 — 20개월 만', top: true }] },
    events: [{ id: 'st:ppi-plate:2026-09:최고(기간)', kind: '월간 통계', signal: '최고(기간)', series: 'ppi-plate', period: '2026-09', company: '포스코·현대제철',
        detectedAt: '2026-10-25T07:30:00+09:00', text: '생산자물가 중후판 2026-09 150.84(2020=100) · 2023-10(153.04) 이후 최고 — 35개월 만' },
      { id: 'st:ppi-plate:2026-09:전년 대비 큰 변동', kind: '월간 통계', signal: '전년 대비 큰 변동', series: 'ppi-plate', period: '2026-09', company: '포스코·현대제철',
        detectedAt: '2026-10-25T07:30:00+09:00', text: '생산자물가 중후판 2026-09 150.84(2020=100) · 전년 같은 달 대비 +12.4%' },
      { id: 'kaida:2026-09:BMW:최저(기간)', kind: '수입차 등록', signal: '최저(기간)', top: true, period: '2026-09', company: 'BMW코리아', detectedAt: '2026-10-25T07:30:00+09:00',
        text: 'KAIDA 2026-09 · BMW 신규등록 6,066대 · 2025-01(5,960) 이후 최저 — 20개월 만' },
      { id: 'kaida:2026-09:Volkswagen:순위 역전', kind: '수입차 등록', signal: '순위 역전', top: false, period: '2026-09', company: '폭스바겐코리아', detectedAt: '2026-10-25T07:30:00+09:00',
        text: 'KAIDA 2026-09 · 순위 역전: Polestar 10위 · Volkswagen 13위(2026-09)' }],
    confirmedScoops: 0 };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/kr-stats', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const k = await call('kr_stats', {}, opts);
  assert.match(k.text, /\[수입 승용차 신규등록 · KAIDA 2026-09 · 전체 34,904대 · 출입처와 주요 브랜드\]\n- 1위 Tesla 12,372대 · 점유 35\.45% · 직전 달 1위 · 전년 같은 달 대비 \+36\.4%\n- 2위 BMW\(BMW코리아\) 6,066대/);
  assert.match(k.text, /출입처 신호: BMW 신규등록 6,066대 · 2025-01\(5,960\) 이후 최저 — 20개월 만/);
  assert.match(k.text, /\[물가지수 · 한국은행 ECOS 품목별\(생산자·수출·수입물가\)\] 1개 계열\(신호 있는 것만, show_all=true로 전부\)\n- 생산자물가 중후판 · 2026-09 150\.84\(2020=100\) · 전월 \+3\.0% · 전년 같은 달 \+12\.4%/);
  assert.match(k.text, /신호: 2023-10\(153\.04\) 이후 최고 — 35개월 만/);
  assert.doesNotMatch(k.text, /전기개폐용스위치/);
  assert.match((await call('kr_stats', { section: 'price', show_all: true }, opts)).text, /전기개폐용스위치/);
  assert.match(k.text, /\[생산·재고 · KOSIS\(철강협회·광공업동향\)\] 1개 계열[\s\S]*용융아연도강판[\s\S]*2016-01 이후 최고\(조회 범위 안\)/);
  const us = await call('kr_stats', { section: 'us_imports' }, opts);
  assert.match(us.text, /\[미국 수입\(한국산\) · US Census 품목별 월간 일반수입액\] 1개 계열[\s\S]*변압기·전력변환기\(HS 8504\) · 2026-08 169\.83\(백만달러\)[\s\S]*\+31\.2%/);
  assert.doesNotMatch(us.text, /용융아연도강판/);
  const r = await call('radar_today', {}, opts);
  const b = r.text.split('[B · ')[1].split('[C · ')[0];
  assert.match(b, /월간 통계: 생산자물가 중후판 2026-09 150\.84\(2020=100\) · 2023-10\(153\.04\) 이후 최고/);
  assert.match(b, /수입차 등록: KAIDA 2026-09 · BMW 신규등록 6,066대 · 2025-01\(5,960\) 이후 최저/);
  assert.doesNotMatch(b, /전년 같은 달 대비 \+12\.4%|Polestar/);  // routine moves and low-rank swaps → C
  assert.match(r.text, /\[C · 참고\(접힘\)\] 2건/);
  assert.deepEqual(dueAt(new Date('2026-10-26T22:30:00Z')), ['kr-stats.yml']);  // Tue 07:30 KST
});

test('kr_stats carsales: latest-month signals A first, model months on query, radar_today puts a stopped model in A and a drop in B', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const sig = (tier, signal, label, scope, text) => ({ id: `cs:x:${label}:2026-10:${signal}`, maker: '현대차', signal, tier, period: '2026-10', scope, label, value: 1, base: 1, yoy: 1, text });
  const doc = { schema: 'kr_stats/v1', generatedAt: '2026-11-16T07:30:00+09:00', checks: [{ source: '완성차 판매(현대차·기아 IR)', status: 'ok', ok: 8, failed: 0, latest: '현대차 모델 2026-10' }],
    rules: [], series: [], kaidaMonths: {}, kaida: {},
    carSales: { latest: { 'hmc:model': '2026-10', 'hmc:plant': '2026-10', 'kia:model': '2026-08' },
      files: { a: { maker: 'hmc', kind: 'model', year: 2026, latest: '2026-10', lastModified: 'Fri, 13 Nov 2026 11:28:08 GMT' },
        b: { maker: 'hmc', kind: 'model', year: 2025, latest: '2025-12', lastModified: 'Mon, 26 Jan 2026 06:37:47 GMT' } },
      rules: ['현대차·기아 IR 엑셀(회사 발표 잠정치).'],
      signals: [sig('B', '급감', 'Sonata (DN8)', '국내 판매', '현대차 국내 판매 · Sonata (DN8) 2026-10 400대 — 직전 3개월 평균 2,198대의 18%, 전년 같은 달 2,500대(16%)'),
        sig('A', '판매 끊김', 'Santa-Fe (MX5a)', '미국 앨라배마 공장 현지 판매', '현대차 미국 앨라배마 공장 현지 판매 · Santa-Fe (MX5a) 2026-10 100대 — 직전 3개월 평균 7,526대, 전년 같은 달 7,000대. 판매(출고)가 거의 끊김')],
      series: [{ id: 'hmc:model:Domestic::Sonata (DN8)', maker: 'hmc', kind: 'model', scope: '국내 판매', label: 'Sonata (DN8)',
        months: { '2026-05': 2241, '2026-06': 2804, '2026-07': 2788, '2026-08': 1642, '2026-09': 2163, '2026-10': 400 } }] },
    events: [{ id: 'cs:hmc:plant:HMMA:Domestic:Santa-Fe (MX5a):2026-10:판매 끊김', kind: '모델별 판매', signal: '판매 끊김', tier: 'A', period: '2026-10', company: '현대차',
        detectedAt: '2026-11-16T07:30:00+09:00', keyword: '싼타페', url: 'https://www.hyundai.com/worldwide/ko/company/ir/ir-resources/sales-results',
        text: '현대차 미국 앨라배마 공장 현지 판매 · Santa-Fe (MX5a) 2026-10 100대 — 직전 3개월 평균 7,526대, 전년 같은 달 7,000대. 판매(출고)가 거의 끊김 (IR 엑셀)' },
      { id: 'cs:hmc:model:Domestic::Sonata (DN8):2026-10:급감', kind: '모델별 판매', signal: '급감', tier: 'B', period: '2026-10', company: '현대차',
        detectedAt: '2026-11-16T07:30:00+09:00', keyword: '쏘나타', url: 'https://www.hyundai.com/worldwide/ko/company/ir/ir-resources/sales-results',
        text: '현대차 국내 판매 · Sonata (DN8) 2026-10 400대 — 직전 3개월 평균 2,198대의 18%, 전년 같은 달 2,500대(16%) (IR 엑셀)' }],
    confirmedScoops: 0 };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/kr-stats', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const k = await call('kr_stats', { section: 'carsales' }, opts);
  assert.match(k.text, /\[완성차 모델별·공장별 판매 · 현대차·기아 IR 엑셀\] 최신 현대차 모델별\(국내 판매·국내 공장 수출\) 2026-10 · 현대차 해외 공장별 2026-10 · 기아 모델별\(국내 판매·국내 공장 수출\) 2026-08/);
  assert.match(k.text, /최신 달 신호 2건\(A 먼저\):\n   - B · 급감: 현대차 국내 판매 · Sonata/);  // 저장 순서 그대로(수집기가 A 먼저 정렬)
  assert.doesNotMatch(k.text, /계열 \d+개/);  // 낱말 없이 부르면 계열 값은 안 펼침
  assert.match(k.text, /현대차 모델별\(국내 판매·국내 공장 수출\) 엑셀 최종수정 Fri, 13 Nov 2026/);  // 지난해 파일(Mon, 26 Jan)이 아니라 최신 달 파일
  assert.doesNotMatch(k.text, /26 Jan 2026/);
  assert.doesNotMatch(k.text, /\[수입 승용차|\[물가지수/);
  assert.match(k.text, /다음: 신호가 있으면 IR 엑셀 원본에서/);
  const q = await call('kr_stats', { section: 'carsales', company: 'Sonata' }, opts);
  assert.match(q.text, /계열 1개 — 최근 6개월:\n   - 현대차 국내 판매 · Sonata \(DN8\): 26-05 2,241 \/ 26-06 2,804 \/ 26-07 2,788 \/ 26-08 1,642 \/ 26-09 2,163 \/ 26-10 400/);
  assert.doesNotMatch(q.text, /Santa-Fe/);
  const r = await call('radar_today', { hours: 24 }, { ...opts, now: new Date('2026-11-16T03:00:00Z') });
  const a = r.text.split('[A · ')[1].split('[B · ')[0];
  assert.match(a, /모델별 판매: 현대차 미국 앨라배마 공장 현지 판매 · Santa-Fe \(MX5a\) 2026-10 100대/);
  const b = r.text.split('[B · ')[1].split('[C · ')[0];
  assert.match(b, /모델별 판매: 현대차 국내 판매 · Sonata \(DN8\) 2026-10 400대/);
});

test('trade_remedies kita: KITA import-regulation events A/B/C in radar_today, recent cases listed, section filter', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const recent = new Date(Date.now() - 3600000).toISOString();
  const ev = (id, tier, kind, text, companies = [], country = 'EAEU') => ({ id, pageId: 'kita', country, tier, kitaKind: kind, label: `${country} 사건`, text, companies,
    url: 'https://docs.wto.org/dol2fe/Pages/SS/directdoc2.aspx?filename=Q%3a%2fG%2fSG%2fN6RUS10.pdf&Open=True', kitaId: id.split(':')[1], detectedAt: recent });
  const doc = { schema: 'trade_remedy/v1', generatedAt: recent, status: 'complete', checks: [{ source: '무역협회 수입규제DB', status: 'ok', returned: 50, detailsRead: 3 }],
    quotas: [], federalRegister: [], pages: [], rules: [],
    kita: { checkedAt: recent, baselineSince: '2026-10-30T07:40:00+09:00', recent: ['ROIL2026100002', 'ROIL2026100006'],
      cases: { ROIL2026100002: { country: 'EAEU', item: '폴리머코팅 평판압연(Flat Steel Products with Polymer Coating)', type: '세이프가드', status: '조사중', updated: '2026-10-27', category: '철강/금속', latestStage: '조사개시|2026-09-07' },
        ROIL2026100006: { country: '마다가스카르', item: '현미(Husked Rice)', type: '세이프가드', status: '조사중', updated: '2026-10-29' } } },
    events: [ev('kita:ROIL2026100010:조사개시|2026-10-20', 'A', '새 대한 수입규제', '튀르키예 반덤핑 · 열연강판(Hot-rolled) — 조사개시 2026-10-20 · 출입처: 포스코·현대제철', ['포스코', '현대제철'], '튀르키예'),
      ev('kita:ROIL2026100002:new', 'B', '새 대한 수입규제', 'EAEU 세이프가드 · 폴리머코팅 평판압연 — 조사개시 2026-09-07 · 품목 분류 철강/금속'),
      ev('kita:ROIL2026100006:new', 'C', '새 대한 수입규제', '마다가스카르 세이프가드 · 현미 — 조사개시 2026-08-31', [], '마다가스카르')] };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/trade-remedy', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const r = await call('radar_today', { include_minor: true }, opts);
  const sec = (t) => r.text.split(`[${t} · `)[1].split(/\n\[[ABC] · /)[0];
  assert.match(sec('A'), /새 대한 수입규제[\s\S]*튀르키예 반덤핑 · 열연강판\(Hot-rolled\) — 조사개시 2026-10-20 · 출입처: 포스코·현대제철/);
  assert.match(sec('B'), /EAEU 세이프가드 · 폴리머코팅 평판압연/);
  assert.match(sec('C'), /마다가스카르 세이프가드 · 현미/);
  const t = await call('trade_remedies', { section: 'kita' }, opts);
  assert.match(t.text, /\[대한 수입규제 · 무역협회 수입규제DB · 확인 [^\]]*\] 아는 사건 2건 · 감지 3건\(기준선 2026-10-30 이후\)\n- A · /);
  assert.match(t.text, /최근 갱신 사건\(갱신순\) 2\/2:\n  2026-10-27 · EAEU 세이프가드 · 폴리머코팅 평판압연\(Flat Steel Products with Polymer Coating\) · 조사중 · 철강\/금속 · 최신 조사개시 2026-09-07/);
  assert.doesNotMatch(t.text, /EU 철강 쿼터|미국 상무부/);
  const q = await call('trade_remedies', { section: 'kita', company: '포스코' }, opts);
  assert.match(q.text, /감지 1건/);
});

test('trade_remedies edis: USITC EDIS docs with snippets by tier, C hidden unless show_all, token note, radar_today A/B with ITC check, notices skip edis', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const recent = new Date(Date.now() - 3600000).toISOString();
  const d = (id, tier, type, extra = {}) => ({ id, tier, documentType: type, documentTitle: `${type} title`, securityLevel: 'Public', investigationNumber: '337-1494',
    investigationPhase: 'Violation', investigationStatus: 'Active', investigationTitle: 'Certain TOPCon Solar Cells', investigationType: 'Sec 337',
    firmOrganization: 'Sidley Austin LLP', filedBy: 'A. Lawyer', onBehalfOf: '', officialReceivedDate: '2026/10/21 16:30:00', firstSeen: recent, isNew: true,
    companies: [], why: '출입처가 당사자인 서면', url: `https://edis.usitc.gov/data/document/${id}`, ...extra });
  const docs = [
    d('898408', 'B', 'Petition', { onBehalfOf: 'Hanwha Solutions Corporation; Hanwha Q CELLS USA, Inc.', companies: ['한화솔루션'], pages: 41,
      snippets: ['Respondents respectfully request that the Commission review the ID and terminate the investigation with prejudice.'] }),
    d('899140', 'B', 'Notice', { firmOrganization: 'USITC', officialReceivedDate: '2026/10/29 09:00:00', why: '지켜보는 조사의 위원회·판사 결정·공고', bodyError: '첨부 없음' }),
    d('900101', 'A', 'Complaint', { investigationNumber: '337-3900', investigationStatus: 'Preinstitution', onBehalfOf: 'Acme Corp.', companies: ['현대모비스'],
      why: '337 제소장 표지에 출입처 이름(피제소인 후보 — 원문 확인)', officialReceivedDate: '2026/11/02 14:00:00', pages: 4, snippets: ['Complainant requests a limited exclusion order.'] }),
    d('898800', 'C', 'Response', { onBehalfOf: 'First Solar, Inc.', why: '관련 일상 문서', securityLevel: 'Confidential' })];
  const ev = (x) => ({ id: `edis:${x.id}`, pageId: 'edis', country: '미국', tier: x.tier, label: `USITC ${x.investigationNumber} ${x.documentType}`,
    text: `${x.documentTitle} — 제출 ${x.firmOrganization} · ${x.why}`, companies: x.companies, url: x.url, detectedAt: recent });
  const doc = { schema: 'trade_remedy/v1', generatedAt: recent, status: 'partial', quotas: [], federalRegister: [], pages: [], rules: [],
    checks: [{ source: 'USITC EDIS 문서', status: 'ok', returned: 180, pages: 2, bodiesRead: 3 }],
    edis: { checkedAt: recent, baselineSince: '2026-11-02T07:40:00+09:00', docs, watched: { '337-1494': 'seed', '337-3900': '2026/11/02 14:00:00' },
      tokenNote: "EDIS 토큰 2026-11-14 만료 예정 — 'API Token Generator'에서 다시 발급해 GitHub 비밀값 EDIS_API_TOKEN 교체" },
    events: [ev(docs[0]), ev(docs[1]), ev(docs[2])] };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/trade-remedy', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const t = await call('trade_remedies', { section: 'edis' }, opts);
  assert.match(t.text, /\[미국 ITC 문서\(EDIS\) · 확인 [^\]]*\] A·B 3건 · 일상 C 1건 숨김\(show_all=true\) · 지켜보는 337 조사 337-1494, 337-3900/);
  assert.match(t.text, /⚠ EDIS 토큰 2026-11-14 만료 예정/);
  assert.ok(t.text.indexOf('337-3900 Complaint') < t.text.indexOf('337-1494 Notice'));  // A first
  assert.ok(t.text.indexOf('337-1494 Notice') < t.text.indexOf('337-1494 Petition'));  // then newest B
  assert.match(t.text, /제출 Sidley Austin LLP \(당사자 Hanwha Solutions Corporation; Hanwha Q CELLS USA, Inc\.\) · 출입처가 당사자인 서면 · 출입처 한화솔루션/);
  assert.match(t.text, /본문\(41쪽, 공개본 첫 첨부\) 발췌: "Respondents respectfully request[^"]*with prejudice\."/);
  assert.match(t.text, /본문 미확인\(첨부 없음\)/);
  assert.match(t.text, /원문: https:\/\/edis\.usitc\.gov\/data\/document\/898408 \(EDIS 문서 번호 898408\)/);
  assert.doesNotMatch(t.text, /First Solar/);
  const all = await call('trade_remedies', { section: 'edis', show_all: true }, opts);
  assert.match(all.text, /C \[신규\] · 접수 2026\/10\/21 16:30 · 337-1494 Response[\s\S]*비공개 문서 — 본문 없음/);
  const q = await call('trade_remedies', { section: 'edis', company: 'Hanwha' }, opts);
  assert.match(q.text, /A·B 1건/);
  const n = await call('trade_remedies', { section: 'notices' }, opts);
  assert.doesNotMatch(n.text, /USITC 337/);
  const r = await call('radar_today', { include_minor: true }, opts);
  const sec = (x) => r.text.split(`[${x} · `)[1].split(/\n\[[ABC] · /)[0];
  assert.match(sec('A'), /무역구제 · 현대모비스\n   USITC 337-3900 Complaint/);
  assert.match(sec('B'), /USITC 337-1494 Petition/);
  assert.match(sec('B'), /USITC 337-1494 Notice/);
});

test('partner filings: EDGAR holdings tables and repeated text fold to C, financial-statement notes never reach A', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const ed = (id, filer, snippet, extra = {}) => ({ id, source: 'EDGAR', filer, form: '6-K', date: '2026-10-25', firstSeen: '2026-10-26T07:00:00+09:00', isNew: true,
    beat: ['현대차'], title: '6-K EX-99.1', url: `https://www.sec.gov/Archives/edgar/data/1/${id}.htm`, snippet, ...extra });
  const doc = { schema: 'partner_filings/v1', generatedAt: '2026-10-26T07:00:00+09:00', windowDays: 30, checks: [{ source: 'EDGAR', target: 'Hyundai Motor Company', status: 'ok' }],
    items: [ed('h1', 'HARTFORD INSURANCE GROUP', 'Top Ten Exposures by Issuer … Hyundai Motor Company 182 178 0.3 %', { routine: '투자 보유 목록(채권·주식 보유 표) — 출입처와의 거래 아님' }),
      ed('k1', 'KT CORP', '(12) The Company has an agreement related to a stock sale contract with HYUNDAI MOTOR COMPANY.', { finNote: '재무제표 주석 — 이미 있던 약정을 다시 적은 것일 수 있음(이전 분기 보고서와 대조)' }),
      ed('c1', 'CELL MAKER INC', 'entered into a binding supply agreement with Hyundai Motor Company for battery cells.', { dealNear: true }),
      // 10-30: 계약 낱말이 출입처 이름과 다른 문장(업계 일반 서술), 보도 인용 문장에만 이름 → A가 아니다
      ed('n1', 'NEXA RESOURCES', 'For third-party suppliers, TCs are based on annually negotiated contracts. The 2026 benchmark TC, reportedly agreed between Hyundai Motor Company and X, was set at US$85/t.',
        { dealNear: false, hearsay: '출입처 이름이 보도 인용 문장(reportedly 등)에만 나옴 — 두 회사 간 거래 공시가 아님' }),
      ed('m1', 'MINER CORP', 'Our supply contracts are with steel mills. Hyundai Motor Company is one of the largest automakers.', { dealNear: false }),
      // 10-31: 퍼스트솔라 10-Q의 특허침해 USITC 청원 문단 — 질의는 한국 표기 + '특허'
      ed('f1', 'FIRST SOLAR, INC.  (FSLR)', 'First Solar filed a petition with the USITC asserting that entities affiliated with Hyundai Motor Company infringe a First Solar patent.',
        { dealNear: false })],
    confirmedScoops: 0 };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/partner-filings', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const r = await call('radar_today', { include_minor: true, limit: 60 }, opts);
  const sec = (t) => r.text.split(`[${t} · `)[1].split(/\n\[[ABC] · /)[0];
  assert.match(sec('A'), /CELL MAKER INC/);
  assert.match(sec('B'), /KT CORP: 6-K EX-99\.1 — 재무제표 주석/);
  assert.match(sec('C'), /HARTFORD INSURANCE GROUP: 6-K EX-99\.1 — 투자 보유 목록/);
  assert.doesNotMatch(sec('A'), /KT CORP|HARTFORD|NEXA|MINER/);
  assert.match(sec('C'), /NEXA RESOURCES: 6-K EX-99\.1 — 출입처 이름이 보도 인용 문장/);  // 기사 인용일 뿐 — 참고(10-31)
  assert.doesNotMatch(sec('B'), /NEXA RESOURCES/);
  assert.match(sec('B'), /MINER CORP: 6-K EX-99\.1 — 계약·공급 낱말이 출입처 이름과 다른 문장에 있음/);
  assert.match(sec('B'), /FIRST SOLAR, INC\.  \(FSLR\): 6-K EX-99\.1 — 소송·특허 절차 서술\(진행 단계·당사자는 원문 확인\)/);  // 10-31: '계약 낱말 없음' 대신
  const items = await (await radarItems(new Request(ORIGIN + '/ingest/radar-items?hours=168', { headers: { Authorization: `Bearer ${TOKEN}` } }), env, { now: new Date('2026-10-26T01:00:00Z') })).json();
  const chk = (id) => items.items.find((x) => x.id === id)?.check;
  assert.deepEqual([chk('f1').who, chk('f1').terms, chk('f1').must], ['현대차', ['퍼스트솔라', '특허'], ['퍼스트솔라']]);
  assert.equal(chk('m1'), undefined);  // 한국 표기를 모르는 회사: 'MINER'로 찾지 않는다(대조 안 함)
  assert.equal(chk('n1'), undefined);  // C
  const t = await call('partner_filings', {}, opts);
  assert.doesNotMatch(t.text, /HARTFORD/);
  assert.match(t.text, /분류: 재무제표 주석/);
  assert.match(t.text, /일상 공시 1건 숨김 — ASX 주총·임원 지분, HKEX 월간 증권 변동·이사회 일정·정기보고서, EDGAR 투자 보유 표·반복 문구/);
  assert.match((await call('partner_filings', { include_routine: true }, opts)).text, /HARTFORD[\s\S]*분류: 투자 보유 목록/);
});

test('assembly bills: same-law same-day filings are one line, core laws are B, stage changes show the previous step', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const b = (id, name, law, date, extra = {}) => ({ id, no: id.slice(4), name, law, committee: null, proposedOn: date, proposer: 'x의원 등 10인', lead: extra.lead ?? '홍길동',
    core: extra.core ?? null, matched: [], stageIndex: extra.stageIndex ?? 0, stage: extra.stage ?? '발의', stageAt: date,
    url: `https://likms.assembly.go.kr/bill/billDetail.do?billId=${id}`, firstSeen: '2026-10-25T08:40:00+09:00', lastChecked: '2026-10-26T08:40:00+09:00', isNew: true });
  const doc = { schema: 'assembly_bills/v1', generatedAt: '2026-10-26T08:40:00+09:00', status: 'complete', baselineSince: '2026-10-20T08:40:00+09:00',
    checks: [{ source: '열린국회정보 발의법률안', status: 'ok', pages: 4, listed: 400, kept: 12 }, { source: '열린국회정보 단계 재확인', status: 'ok', checked: 30, tracked: 30 }],
    bills: [b('PRC_A1', '전기사업법 일부개정법률안', '전기사업법', '2026-10-25', { core: '전력·에너지', lead: '김갑동' }),
      b('PRC_A2', '전기사업법 일부개정법률안', '전기사업법', '2026-10-25', { core: '전력·에너지', lead: '이을동' }),
      b('PRC_S1', '철강산업 경쟁력 강화 및 탄소중립 전환을 위한 특별법 일부개정법률안', '철강산업 경쟁력 강화 및 탄소중립 전환을 위한 특별법', '2026-10-01',
        { core: '철강·비철', stageIndex: 2, stage: '소관위 상정', lead: '박병동' }),
      b('PRC_K1', '산업안전보건법 일부개정법률안', '산업안전보건법', '2026-10-25')],
    events: [{ id: 'bill:PRC_A1:발의', billId: 'PRC_A1', kind: '발의', detectedAt: '2026-10-26T08:40:00+09:00', date: '2026-10-25', core: '전력·에너지', law: '전기사업법', lead: '김갑동' },
      { id: 'bill:PRC_A2:발의', billId: 'PRC_A2', kind: '발의', detectedAt: '2026-10-26T08:40:00+09:00', date: '2026-10-25', core: '전력·에너지', law: '전기사업법', lead: '이을동' },
      { id: 'bill:PRC_S1:소관위 상정', billId: 'PRC_S1', kind: '소관위 상정', detectedAt: '2026-10-26T08:40:00+09:00', date: '2026-10-26', core: '철강·비철',
        law: '철강산업 경쟁력 강화 및 탄소중립 전환을 위한 특별법', lead: '박병동', from: '소관위 회부' },
      { id: 'bill:PRC_K1:발의', billId: 'PRC_K1', kind: '발의', detectedAt: '2026-10-26T08:40:00+09:00', date: '2026-10-25', core: null, law: '산업안전보건법', lead: '홍길동' },
      // 10-31 운영: 발의 다음 날 소관위 회부가 또 B로 떴다 — 회부는 모든 법안이 거치는 절차
      { id: 'bill:PRC_A1:소관위 회부', billId: 'PRC_A1', kind: '소관위 회부', detectedAt: '2026-10-26T08:40:00+09:00', date: '2026-10-26', core: '전력·에너지',
        law: '전기사업법', lead: '김갑동', from: '발의' }],
    rules: ['국회의원 발의법률안(열린국회정보)이다.'], confirmedScoops: 0 };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/assembly-bills', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const t = await call('assembly_bills', {}, opts);
  assert.match(t.text, /\[새 발의 · 최근 14일 · 출입처 직결 법\(core\)\] 1묶음\n- 2026-10-25 · \[전력·에너지\] 법안 발의: 전기사업법 일부개정법률안 등 2건 — 김갑동·이을동 대표발의/);
  assert.match(t.text, /\[단계 변화 · 최근 14일\] 2건\n- 2026-10-26 · \[철강·비철\] 법안 소관위 상정: 철강산업 경쟁력 강화 및 탄소중립 전환을 위한 특별법 일부개정법률안 \(직전 소관위 회부\) — 박병동 대표발의/);
  assert.doesNotMatch(t.text, /산업안전보건법 일부개정/);
  assert.match((await call('assembly_bills', { include_related: true }, opts)).text, /산업안전보건법 일부개정법률안/);
  const r = await call('radar_today', { include_minor: true }, opts);
  const bsec = r.text.split('[B · ')[1].split('[C · ')[0];
  assert.match(bsec, /국회 법안 · 전력·에너지\n   법안 발의: 전기사업법 일부개정법률안 등 2건/);
  assert.match(bsec, /법안 소관위 상정: 철강산업/);
  assert.match(r.text.split('[C · ')[1], /법안 발의: 산업안전보건법 일부개정법률안/);
  assert.match(r.text.split('[C · ')[1], /법안 소관위 회부: 전기사업법 일부개정법률안 \(직전 발의\) — 김갑동 대표발의/);
  assert.doesNotMatch(bsec, /법안 소관위 회부:/);
  const items = await (await radarItems(new Request(ORIGIN + '/ingest/radar-items?hours=168', { headers: { Authorization: `Bearer ${TOKEN}` } }), env, { now: new Date('2026-10-26T01:00:00Z') })).json();
  const bill = items.items.find((x) => x.id === 'bills:발의|전기사업법|2026-10-25');
  assert.deepEqual([bill.check.terms, bill.check.must], [['개정안', '김갑동'], ['김갑동', '이을동']]);  // 대표발의 의원이 기사에 있어야
  assert.equal(bill.check.names, undefined);  // 줄임말 없는 법은 그대로
  const steel = items.items.find((x) => x.id.startsWith('bills:') && x.fact.includes('철강산업'));
  assert.deepEqual([steel.check.who, steel.check.names.at(-1)], ['K-스틸법', '철강산업 경쟁력 강화 및 탄소중립 전환을 위한 특별법']);
  assert.deepEqual(dueAt(new Date('2026-10-27T23:40:00Z')), ['assembly-bills.yml']);  // Wed 08:40 KST
  assert.deepEqual(dueAt(new Date('2026-10-28T08:40:00Z')), ['assembly-bills.yml']);  // Wed 17:40 KST
});

test('trademarks: weekly filings grouped by name, new names in core classes are B, waits are not failures and radar_today keeps them a week', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const filing = (company, title, date, classes, extra = {}) => ({ id: `tm:${company}:${title.toLowerCase().replace(/\W/g, '')}:${date.replace(/-/g, '')}`, company, related: false, title,
    applicationDate: date, applicationNumbers: classes.map((c, i) => `40202601${c}${String(i).padStart(3, '0')}`), newNumbers: [], classes, coreClasses: classes.filter((c) => ['12', '09'].includes(c)),
    statuses: ['출원'], agent: '대리인', applicants: '현대자동차주식회사', isNew: false, titleNew: false, tier: null, firstSeen: '2026-10-19T07:10:00+09:00', ...extra });
  const doc = { schema: 'trademarks/v1', generatedAt: '2026-10-26T07:10:00+09:00', source: 'KIPRIS Plus 상표 출원 속보(getAdvancedSearch)', status: 'partial',
    window: { from: '2026-07-28', to: '2026-10-26', field: '출원일' }, baselineSince: '2026-10-19T07:10:00+09:00',
    checks: [{ source: '상표 현대자동차', status: 'ok', rawTotal: 4, kept: 4, filings: 3, requests: 1 },
      { source: '상표 KG모빌리티', status: 'ok', rawTotal: 0, kept: 0, filings: 0, requests: 1, nameVerified: false },
      { source: '상표 포스코', status: 'waiting', reason: 'provider_22_cooldown', until: '2026-10-29T07:10:00+09:00' }],
    filings: [filing('현대자동차', 'AERO DRIVE', '2026-10-20', ['12', '35'], { isNew: true, titleNew: true, tier: 'B', firstSeen: '2026-10-26T07:10:00+09:00' }),
      filing('현대자동차', 'NUTRIMACY', '2026-09-10', ['07', '09', '12'], { isNew: true, tier: 'C', addedClassesAt: '2026-10-26T07:10:00+09:00' }),
      filing('현대자동차', 'PLEOS', '2026-08-01', ['09']),
      filing('현대자동차', 'OLDNEW', '2026-10-01', ['12'], { isNew: true, titleNew: true, tier: 'B', firstSeen: '2026-10-12T07:10:00+09:00' })],
    fresh: [], seen: {}, titles: {},
    kipris: { month: '2026-10', counted: 40, monthlyLimit: 900, groupUsed: { patent: 30, trademark: 10, diagnostic: 0 }, groupLimits: { patent: 730, trademark: 150, diagnostic: 20 } },
    rules: ['상표 출원은 출원 사실이다. 제품 출시·사업 진출·차명 확정이 아니다(방어 출원·예비 출원이 흔함).'], confirmedScoops: 0 };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/trademarks', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const t = await call('trademarks', {}, opts);
  assert.match(t.text, /조회 정상 2\/3 · 대기 1곳\(제공기관 응답 22 뒤 72시간 대기, 2026-10-29T07:10부터 재시도\)/);
  assert.match(t.text, /KIPRIS 호출 장부\(2026-10\): 상표 10\/150 · 전체 40\/900 — 이 저장소가 센 수, 계정 실제 사용량 아님/);
  assert.match(t.text, /출원인 이름 미확인 \+ 0건: KG모빌리티/);
  assert.match(t.text, /- \[B · 처음 보는 이름\] 현대자동차 · 「AERO DRIVE」 · 출원 2026-10-20\n   상품류: 12류\(차량·부품\), 35류\(광고·사업관리\) · 업종 핵심 12류/);
  assert.match(t.text, /\[C · 상품류 추가\] 현대자동차 · 「NUTRIMACY」/);
  assert.match(t.text, /「OLDNEW」/);  // 14 days ago is inside the tool's 30-day default
  assert.doesNotMatch(t.text, /PLEOS/);  // baseline filings only with show_all
  assert.match((await call('trademarks', { show_all: true, days: 120 }, opts)).text, /PLEOS/);
  assert.doesNotMatch((await call('trademarks', { name: 'aero' }, opts)).text, /NUTRIMACY/);
  assert.doesNotMatch((await call('trademarks', { class: '35' }, opts)).text, /NUTRIMACY/);
  const r = await call('radar_today', {}, opts);
  assert.match(r.text, /기자 전용 감시 22개/);
  assert.match(r.text, /- 상표 출원: 대기 1곳\(제공기관 응답 22 뒤 72시간 대기\) — 해당 부분 0건은 미확인/);
  assert.doesNotMatch(r.text, /상표 출원: [^\n]*시간 전 결과/);
  const b = r.text.split('[B · ')[1].split('[C · ')[0];
  assert.match(b, /상표 출원 · 현대자동차\n   상표 출원 「AERO DRIVE」 12류\(차량·부품\), 35류\(광고·사업관리\) — 감시 시작 이후 처음 보는 이름 \(출원 2026-10-20, 출원번호 [0-9]+ 외 1\)/);
  assert.doesNotMatch(r.text, /OLDNEW/);  // first seen two weeks ago: off the digest
  const minor = await call('radar_today', { include_minor: true }, opts);
  assert.match(minor.text, /상표 출원 「NUTRIMACY」[^\n]* — 같은 이름 상품류 추가/);
  const list = await rpc('tools/list', {}, { path: `/mcp/${TOKEN}`, env });
  assert.ok(list.body.result.tools.some((x) => x.name === 'trademarks'));
  assert.match(list.body.result.tools.find((x) => x.name === 'radar_today').description, /감시 22개\([^)]*상표 출원, 국회 법안, 미국 리콜, 미국 EPA 인증, 국내 연비 신고, 해외 발주처 낙찰, 협력사 회생·파산, 전기위·원안위, 공장 부지 건축허가, 해외 법인 등기, 지자체 고시·공고, 사업장 인력, 굴뚝 측정\)/);
  assert.ok(!(await rpc('tools/list', {}, { env })).body.result.tools.some((x) => x.name === 'trademarks'));  // private only
});

test('live statistics: ECOS, KOSIS and customs lookups state ranges, keep variants apart and never turn failures into zero', async () => {
  const months = (from, n) => Array.from({ length: n }, (_, i) => { const d = new Date(Date.UTC(Number(from.slice(0, 4)), Number(from.slice(4)) - 1 + i, 1)); return `${d.getUTCFullYear()}${String(d.getUTCMonth() + 1).padStart(2, '0')}`; });
  const ecosRows = [];
  for (const [i, m] of months('202401', 33).entries()) {
    ecosRows.push({ STAT_NAME: '4.3.1.3. 수출물가지수(품목별)', ITEM_NAME1: '열연강대및강판', ITEM_NAME2: '원화기준', UNIT_NAME: '2020=100', TIME: m, DATA_VALUE: String(100 + i) });
    ecosRows.push({ STAT_NAME: '4.3.1.3. 수출물가지수(품목별)', ITEM_NAME1: '열연강대및강판', ITEM_NAME2: '계약통화기준', UNIT_NAME: '2020=100', TIME: m, DATA_VALUE: String(200 - i) });
  }
  const customsXml = (from, to) => `<response><header><resultCode>00</resultCode><resultMsg>NORMAL SERVICE.</resultMsg></header><body><items>${
    months(from, 12).filter((m) => m <= to).map((m) => `<item><year>${m.slice(0, 4)}.${m.slice(4)}</year><hsCd>850423</hsCd><statKor>변압기</statKor><expDlr>${m === '202609' ? 300000000 : 100000000}</expDlr><expWgt>1000000</expWgt><impDlr>5000000</impDlr><impWgt>20000</impWgt></item>`).join('')
  }<item><year>총계</year><expDlr>1</expDlr><expWgt>1</expWgt><impDlr>1</impDlr><impWgt>1</impWgt></item></items></body></response>`;
  const routes = {
    'https://ecos.bok.or.kr/api/StatisticTableList/': Response.json({ StatisticTableList: { row: [
      { STAT_CODE: '404Y016', STAT_NAME: '4.1.1.3. 생산자물가지수(품목별)', CYCLE: 'M', SRCH_YN: 'Y' }, { STAT_CODE: '402Y016', STAT_NAME: '4.3.1.3. 수출물가지수(품목별)', CYCLE: 'M', SRCH_YN: 'Y' },
      { STAT_CODE: '0000000001', STAT_NAME: '1. 통화/금융', SRCH_YN: 'N' }] } }),
    'https://ecos.bok.or.kr/api/StatisticItemList/': Response.json({ StatisticItemList: { row: [
      { GRP_NAME: '계정코드', ITEM_CODE: '30712502AA', ITEM_NAME: '열연강대및강판', CYCLE: 'M', START_TIME: '197001', END_TIME: '202609', UNIT_NAME: '2020=100' },
      { GRP_NAME: '계정코드', ITEM_CODE: '30712502AA', ITEM_NAME: '열연강대및강판', CYCLE: 'A', START_TIME: '1970', END_TIME: '2025', UNIT_NAME: '2020=100' },
      { GRP_NAME: '계정코드', ITEM_CODE: '30713102AA', ITEM_NAME: '냉연강대', CYCLE: 'M', START_TIME: '198001', END_TIME: '202609', UNIT_NAME: '2020=100' }] } }),
    'https://ecos.bok.or.kr/api/StatisticSearch/': (url) => (url.includes('/NOPE/') ? Response.json({ RESULT: { CODE: 'INFO-200', MESSAGE: '해당하는 데이터가 없습니다.' } })
      : Response.json({ StatisticSearch: { list_total_count: ecosRows.length, row: ecosRows } })),
    'https://kosis.kr/openapi/statisticsSearch.do': Response.json([{ ORG_ID: '363', TBL_ID: 'TX_36301_A000', TBL_NM: '철강 생산량', ORG_NM: '한국철강협회', STRT_PRD_DE: '2000', END_PRD_DE: '2026' }]),
    'https://kosis.kr/openapi/statisticsData.do': (url) => (url.includes('type=PRD') ? Response.json([{ PRD_SE: '월', STRT_PRD_DE: '2000.01', END_PRD_DE: '2026.08' }])
      : Response.json([{ OBJ_ID: 'ITEM', OBJ_NM: '항목', ITM_ID: '16363AAA0', ITM_NM: '생산량' }, { OBJ_ID: '15363AA1', OBJ_NM: '철강종류별', ITM_ID: '15363AA1AA', ITM_NM: '조강' },
        { OBJ_ID: '15363AA1', OBJ_NM: '철강종류별', ITM_ID: '50', ITM_NM: '열연강판' }])),
    'https://kosis.kr/openapi/Param/statisticsParameterData.do': Response.json(months('202301', 44).map((m, i) => ({ PRD_DE: m, DT: String(m === '202608' ? 4000 : 5000 + (i % 3)), UNIT_NM: '천톤', C1_NM: '조강', ITM_NM: '생산량', TBL_NM: '철강 생산량' }))),
    'https://apis.data.go.kr/1220000/nitemtrade/getNitemtradeList': (url) => { const q = new URL(url).searchParams; return new Response(customsXml(q.get('strtYymm'), q.get('endYymm'))); },
  };
  const none = PRIVATE();
  assert.match((await call('ecos_find', { query: '생산자물가' }, none)).text, /Cloudflare 비밀값 ECOS_API_KEY 미설정 — 조회하지 않음\(0건 아님\)/);
  assert.match((await call('customs_trade', { hs: '8504' }, none)).text, /CUSTOMS_API_KEY\(또는 DATA_GO_KR_KEY\) 미설정/);
  const opts = { ...PRIVATE({ ECOS_API_KEY: 'e', KOSIS_API_KEY: 'k', G2B_API_KEY: 'g' }), fetch: fakeFetch(routes) };
  const tables = await call('ecos_find', { query: '물가 품목별' }, opts);
  assert.match(tables.text, /404Y016 4\.1\.1\.3\. 생산자물가지수\(품목별\)[\s\S]*402Y016/);
  assert.doesNotMatch(tables.text, /통화\/금융/);
  const items = await call('ecos_find', { stat: '404y016', query: '열연' }, opts);
  assert.match(items.text, /\[계정코드\] 30712502AA 열연강대및강판 · 단위 2020=100 · M 197001~202609, A 1970~2025/);
  assert.doesNotMatch(items.text, /냉연강대/);
  const data = await call('ecos_data', { stat: '402Y016', item: '30712502AA', start: '202401', end: '202609' }, opts);
  assert.match(data.text, /■ 열연강대및강판 · 원화기준 \(단위 2020=100\)\n   최신 202609 132 · 직전\(202608\) 대비 \+0\.8% · 전년 같은 기간\(202509, 120\) 대비 \+10%\n   조회 범위\(202401~\) 최고/);
  assert.match(data.text, /■ 열연강대및강판 · 계약통화기준[\s\S]*조회 범위\(202401~\) 최저/);  // the two bases stay separate
  assert.match(data.text, /"역대"는 원표 전체 기간으로 다시 뜬다/);
  const nodata = await call('ecos_data', { stat: 'NOPE', item: 'X' }, opts);
  assert.ok(nodata.isError);
  assert.match(nodata.text, /ECOS 값 없음\(INFO-200 해당하는 데이터가 없습니다\.\) — 미확인/);
  assert.match((await call('kosis_find', { query: '철강 생산량' }, opts)).text, /org 363 · tbl TX_36301_A000 · 철강 생산량 \[한국철강협회\] 2000~2026/);
  const meta = await call('kosis_data', { org: '363', tbl: 'TX_36301_A000' }, opts);
  assert.match(meta.text, /수록 월 2000\.01~2026\.08[\s\S]*itm\(항목\)[\s\S]*16363AAA0 생산량[\s\S]*obj 15363AA1\(철강종류별\) — 2개[\s\S]*15363AA1AA 조강/);
  const kd = await call('kosis_data', { org: '363', tbl: 'TX_36301_A000', obj1: '15363AA1AA', itm: '16363AAA0' }, opts);
  assert.match(kd.text, /■ 조강 · 생산량 \(단위 천톤\)\n   최신 202608 4,000 · 직전\(202607\) 대비 -20% · 전년 같은 기간\(202508, 5,001\) 대비 -20%\n   조회 범위\(202301~\) 최저/);
  const ct = await call('customs_trade', { hs: '변압기 수출', start: '202410', end: '202609' }, opts);
  assert.match(ct.text, /HS 8504 · 전체 국가 · 202410~202609/);
  assert.match(ct.text, /■ 수출금액\n   최신 202609 300,000,000 · 직전\(202608\) 대비 \+200% · 전년 같은 기간\(202509, 100,000,000\) 대비 \+200%\n   조회 범위\(202410~\) 최고/);
  assert.match(ct.text, /수출 단가\(USD\/kg\): 202609 300 · 202509 100\(\+200%\)/);
  assert.match(ct.text, /회사 실적·산업부 품목군 숫자와 섞지 않는다/);
  assert.match((await call('customs_trade', { hs: '우주선' }, opts)).text, /HS 코드\(숫자 2~10자리\)나 다음 낱말/);
  const pub = await rpc('tools/call', { name: 'ecos_data', arguments: { stat: 'x', item: 'y' } });
  assert.match(JSON.stringify(pub.body), /Unknown tool/);  // private path only
});

test('non-MCP paths keep the canonical Pages redirect', async () => {
  const r = await worker.fetch(new Request(ORIGIN + '/scoop.json?v=1'), {}, {});
  assert.equal(r.status, 307);
  assert.equal(r.headers.get('Location'), 'https://shhong9173-art.github.io/seoul-reporting-radar/scoop.json?v=1');
  assert.equal((await worker.fetch(new Request(ORIGIN + '/', { method: 'POST' }), {}, {})).status, 405);
  assert.equal((await worker.fetch(new Request(ORIGIN + '/mcp/short'), {}, {})).status, 404);
});

function makeZip(name, data) {
  const nameBytes = Buffer.from(name);
  const deflated = deflateRawSync(data);
  const crc = crc32(data);
  const local = Buffer.alloc(30);
  local.writeUInt32LE(0x04034b50, 0); local.writeUInt16LE(20, 4); local.writeUInt16LE(0, 6); local.writeUInt16LE(8, 8);
  local.writeUInt32LE(crc, 14); local.writeUInt32LE(deflated.length, 18); local.writeUInt32LE(data.length, 22);
  local.writeUInt16LE(nameBytes.length, 26); local.writeUInt16LE(0, 28);
  const central = Buffer.alloc(46);
  central.writeUInt32LE(0x02014b50, 0); central.writeUInt16LE(20, 4); central.writeUInt16LE(20, 6); central.writeUInt16LE(8, 10);
  central.writeUInt32LE(crc, 16); central.writeUInt32LE(deflated.length, 20); central.writeUInt32LE(data.length, 24);
  central.writeUInt16LE(nameBytes.length, 28); central.writeUInt32LE(0, 42);
  const localPart = Buffer.concat([local, nameBytes, deflated]);
  const centralPart = Buffer.concat([central, nameBytes]);
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50, 0); end.writeUInt16LE(1, 8); end.writeUInt16LE(1, 10);
  end.writeUInt32LE(centralPart.length, 12); end.writeUInt32LE(localPart.length, 16);
  return Buffer.concat([localPart, centralPart, end]);
}
function crc32(buf) {
  let c = ~0;
  for (const b of buf) { c ^= b; for (let k = 0; k < 8; k++) c = (c >>> 1) ^ (0xedb88320 & -(c & 1)); }
  return ~c >>> 0;
}

test('radar-items hands hinted A/B items to the press checker; radar_today shows verdicts, unreported first', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const post = async (feed, doc) => assert.equal((await worker.fetch(new Request(ORIGIN + `/ingest/${feed}`, { method: 'POST',
    headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  await post('us-litigation', { schema: 'us_litigation/v1', generatedAt: '2026-10-26T07:50:00+09:00', checks: [], itc: [], opinions: [],
    cases: [
      { id: 'cl:4', beat: ['세아제강'], caseName: 'SeAH Steel Corporation v. United States', court: 'CIT', courtId: 'cit', category: '국제무역법원(무역구제 소송)',
        priority: 0, role: '원고', dateFiled: '2026-10-25', firstSeen: '2026-10-25T10:00:00+09:00', url: 'https://cl/4' },
      { id: 'cl:5', beat: ['포스코'], caseName: 'POSCO v. United States', court: 'CIT', courtId: 'cit', category: '국제무역법원(무역구제 소송)',
        priority: 0, role: '원고', dateFiled: '2026-10-24', firstSeen: '2026-10-25T10:00:00+09:00', url: 'https://cl/5' },
      { id: 'cl:7', beat: ['LS일렉트릭'], caseName: 'In re: LS Electric Co., Ltd.', court: 'CAFC', courtId: 'cafc', category: '연방순회항소법원', priority: 0,
        role: '신청·항소인(In re)', dateFiled: '2026-10-23', firstSeen: '2026-10-25T10:00:00+09:00', appealFrom: 'United States Patent and Trademark Office',
        summary: 'LS일렉트릭, 미국 특허청 특허심판원(PTAB) 결정에 불복해 연방순회항소법원에 항소', url: 'https://cl/7' },
      { id: 'cl:9', beat: ['현대차'], caseName: 'Lee v. Hyundai Motor America', category: '소비자·제조물책임', priority: 3, role: '피고·기타 당사자',
        dateFiled: '2026-10-24', firstSeen: '2026-10-25T07:50:00+09:00' }] });
  await post('kr-official', { schema: 'kr_official/v1', generatedAt: '2026-10-26T08:10:00+09:00', checks: [], gazette: [],
    factories: [{ id: 'fac:1', company: 'KG스틸', cmpnyNm: 'KG스틸(주)당진공장', rnAdres: '충청남도 당진시 송악읍 북부산업로 1', employees: 690 }],
    events: [
      { id: 'fac:1:x', kind: '등록 내용 변경', company: 'KG스틸', factoryId: 'fac:1', name: 'KG스틸(주)', text: '고용 856→690명', detectedAt: '2026-10-25T11:09:00+09:00' },
      { id: 'fac:2:gone', kind: '목록에서 빠짐', company: '현대위아', factoryId: 'fac:2', text: '현대위아(주)창원2공장 · 경상남도 창원시 성산구 정동로 154 — 이번 조회 목록에 없음', detectedAt: '2026-10-25T11:09:00+09:00' },
      { id: 'fac:3:x', kind: '등록 내용 변경', company: '효성중공업(관련)', factoryId: 'fac:3', text: "업종 'a 외 13 종'→'a 외 14 종'", detectedAt: '2026-10-25T11:09:00+09:00' },
      // 10-30부터 수집기가 등급을 붙인다: 순서만 바뀐 주생산품은 C(보도 대조 안 함)
      { id: 'fac:4:x', kind: '등록 내용 변경', company: 'LS일렉트릭', factoryId: 'fac:4', tier: 'C', text: "주생산품 'a, b'→'b, a' — 순서·표기만 바뀜", detectedAt: '2026-10-25T11:09:00+09:00' }] });
  await call('candidate_feedback', { item_id: 'cl:5', verdict: '봤음', reason: '확인' }, opts);

  const wrong = await worker.fetch(new Request(ORIGIN + '/ingest/radar-items', { headers: { Authorization: 'Bearer wrong-token-0123456789' } }), env, {});
  assert.equal(wrong.status, 404);
  const res = await radarItems(new Request(ORIGIN + '/ingest/radar-items?hours=72', { headers: { Authorization: `Bearer ${TOKEN}` } }), env, { now: NOW });
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.hours, 72);
  const by = Object.fromEntries(body.items.map((x) => [x.id, x]));
  assert.deepEqual(by['cl:4'].check, { who: '세아제강', terms: ['국제무역법원', '소송'], alts: { 국제무역법원: ['국제무역법원', '무역법원', 'CIT'], 소송: ['소송', '제소', '판결', '항소', '불복'] } });
  assert.deepEqual(by['cl:7'].check.terms, ['항소', '특허']);
  assert.deepEqual([by['fac:1:x'].check.terms, by['fac:1:x'].check.must], [['당진', '감원'], ['당진']]);  // 공장 시·군 없는 감원 기사는 다른 공장일 수 있다
  assert.equal(by['fac:1:x'].fact, '등록 내용 변경: KG스틸(주)당진공장 · 충청남도 당진시 송악읍 북부산업로 1 — 고용 856→690명');
  assert.equal(by['fac:2:gone'].fact.split(' — ')[0], '목록에서 빠짐: 현대위아(주)창원2공장 · 경상남도 창원시 성산구 정동로 154');  // already named: unchanged
  const ko = await call('kr_official', { section: 'factory', company: 'KG스틸' }, opts);
  assert.match(ko.text, /잡힌 사실: KG스틸\(주\)당진공장 · 충청남도 당진시 송악읍 북부산업로 1 — 고용 856→690명/);
  assert.deepEqual(by['fac:2:gone'].check.terms, ['창원', '공장', '폐쇄']);
  assert.deepEqual(by['fac:2:gone'].check.places, ['창원']);
  assert.ok(!by['cl:5'], 'judged 봤음 is not checked again');
  assert.ok(!by['cl:9'], 'C tier is not checked');
  assert.ok(!by['fac:4:x'], 'a factory change the collector graded C is not checked');
  assert.ok(!by['fac:3:x'], 'no hint when the change has no search words');
  assert.equal(hint('효성중공업(관련)·일진전기', ['공장', null]).who, '효성중공업');
  assert.equal(hint('', ['x']), undefined);

  await post('radar-check', { schema: 'radar_check/v1', generatedAt: '2026-10-26T08:50:00+09:00', items: [
    { id: 'cl:4', verdict: '관련 보도 있음', since: '2026-10-22', queries: ['세아제강 국제무역법원', '세아제강 국제무역법원 소송'],
      evidence: [{ date: '2026-10-25', channel: 'naver', title: '세아제강, 美 국제무역법원에 반덤핑 소송', url: 'https://n/1', why: '낱말' }],
      channels: { naver: { status: 'ok', returned: 3 } }, firstVerdict: '미보도 후보', firstCheckedAt: '2026-10-25T18:50:00+09:00' },
    { id: 'cl:7', verdict: '미보도 후보', since: '2026-10-20', queries: ['LS일렉트릭 항소', 'LS일렉트릭 항소 특허'],
      evidence: [{ date: '2026-10-24', channel: 'naver', title: '전력기기 업계 美 소송 잇따라', url: 'https://n/2', why: '본문에만 회사·낱말(항소, 특허) — 제목 불일치, 같은 사건 가능성 낮음' },
        { date: '2026-10-23', channel: 'bing', title: 'LS일렉트릭, ESS 특허 폭증', url: 'https://n/4', why: '제목에 회사·낱말(특허)이 있으나 PTAB 없음 — 다른 사업장·다른 건 기사일 수 있음' },
        { date: '2026-08-02', channel: 'naver', title: 'LS일렉트릭, 美 특허심판원 결정 불복', url: 'https://n/3', before: true, why: '항목 날짜보다 앞선 기사(항소) — 판정에 안 셈' }],
      channels: { naver: { status: 'ok', returned: 0 }, bing: { status: 'ok', returned: 0 }, google: { status: 'ok', returned: 0 } } },
    { id: 'fac:1:x', verdict: '미확인', since: '2026-10-22', queries: ['KG스틸 인력'], evidence: [],
      channels: { naver: { status: 'failed', error: 'ConnectTimeout' }, bing: { status: 'ok', returned: 0 } } }] });
  const r = await call('radar_today', {}, opts);
  const a = r.text.split('[A · ')[1].split('[B · ')[0];
  assert.match(a, /\(보도 대조 자동 10-26 08:50: 미보도 후보 1 · 관련 보도 있음 1 · 미확인 1 · 대조 안 함 1 — 미보도 후보부터\)/);
  const order = ['In re: LS Electric', 'KG스틸', 'SeAH Steel'].map((w) => a.indexOf(w));
  assert.ok(order.every((i) => i > 0) && order[0] < order[1] && order[1] < order[2], a);
  assert.match(a, /보도 대조\(자동 10-26 08:50\): 미보도 후보 — "LS일렉트릭 항소", "LS일렉트릭 항소 특허"로 2026-10-20 이후 관련 기사 못 찾음\(검색 범위 결과, 단독 판정 아님\)/);
  assert.match(a, /보도 대조\(자동 10-26 08:50\): 관련 보도 있음 — "세아제강 국제무역법원", "세아제강 국제무역법원 소송" · 처음\(10-25 18:50\) 미보도 후보/);
  assert.match(a, /↳ 2026-10-25 \[naver\] 세아제강, 美 국제무역법원에 반덤핑 소송 https:\/\/n\/1\n/);
  assert.match(a, /↳ 2026-10-24 \[naver\] 전력기기 업계 美 소송 잇따라 https:\/\/n\/2 \(약한 근거: 본문에만, 제목 불일치\)/);
  // must가 없는 근거(10-31 퍼스트솔라 ↔ '한화솔루션 특허 폭증')도 꼬리표
  assert.match(a, /↳ 2026-10-23 \[bing\] LS일렉트릭, ESS 특허 폭증 https:\/\/n\/4 \(약한 근거: PTAB 없음 — 다른 건일 수 있음\)/);
  // 판정에 안 세는 앞선 기사(10-31): 미보도 후보에 맥락 한 줄
  assert.match(a, /↳ 2026-08-02 \[naver\] LS일렉트릭, 美 특허심판원 결정 불복 https:\/\/n\/3 \(앞선 기사: 항목 날짜 전이라 판정에 안 셈 — 같은 사업의 앞선 보도일 수 있음\)/);
  assert.match(a, /보도 대조\(자동 10-26 08:50\): 미확인 — 채널 naver failed\(ConnectTimeout\)\(0건 아님\)/);
  assert.match(r.text, /보도 대조\(자동\)는 네이버 뉴스 API·빙·구글에서 항목 날짜 3일 전부터 찾은 결과다/);
  assert.doesNotMatch(r.text, /보도 대조\(자동\): 결과 없음/);
  const none = await call('radar_today', {}, PRIVATE());
  assert.match(none.text, /보도 대조\(자동\): 결과 없음 — 미확인\(평일 08:50·18:50 실행 확인\)/);
});

test('press check is dispatched after the morning watches and after the evening page watch', () => {
  assert.deepEqual(dueAt(new Date('2026-10-27T23:50:00Z')), ['radar-press-check.yml']);  // Wed 08:50 KST
  // 공식 원자료 직접 수집: 06:40·08:00·15:00·18:00 KST 평일
  assert.deepEqual(dueAt(new Date('2026-10-28T21:40:00Z')), ['scoop-radar.yml']);  // Thu 06:40 KST
  assert.deepEqual(dueAt(new Date('2026-10-28T23:00:00Z')), ['scoop-radar.yml']);  // Thu 08:00 KST
  assert.deepEqual(dueAt(new Date('2026-10-29T06:00:00Z')), ['scoop-radar.yml']);  // Thu 15:00 KST
  assert.deepEqual(dueAt(new Date('2026-10-29T09:00:00Z')), ['scoop-radar.yml']);  // Thu 18:00 KST
  assert.deepEqual(dueAt(new Date('2026-10-31T23:00:00Z')), []);                   // Sun 08:00 KST
  assert.deepEqual(dueAt(new Date('2026-10-28T21:10:00Z')), ['kr-fuel.yml']);      // Thu 06:10 KST
  assert.deepEqual(dueAt(new Date('2026-10-28T21:20:00Z')), ['us-epa.yml']);       // Thu 06:20 KST
  assert.deepEqual(dueAt(new Date('2026-10-28T09:50:00Z')), ['radar-press-check.yml']);  // Wed 18:50 KST
});

test('trade remedies: an unusual decision-memo topic in a notice naming a beat company reaches A with the appendix line', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const odd = 'Comment 8: Whether the Constructing and Operation of Workplace Nursery Program is Countervailable';
  await worker.fetch(new Request(ORIGIN + '/ingest/trade-remedy', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify({
    schema: 'trade_remedy/v1', generatedAt: '2026-10-25T07:40:00+09:00', checks: [], quotas: [], events: [],
    federalRegister: [{ id: 'fr:2026-20778', date: '2026-10-24', stage: '최종 판정', title: 'Certain Hot-Rolled Steel Flat Products From the Republic of Korea: Final Results of Countervailing Duty Administrative Review',
      url: 'https://www.federalregister.gov/d/2026-20778', named: [{ company: '포스코', mentions: 2, lines: ['POSCO'] }, { company: '현대제철', mentions: 1, lines: ['Hyundai Steel'] }],
      memoTopics: [odd], memoUnusual: [odd], memoNamed: ["Comment 6: Whether to Modify POSCO's KEXIM OICP Loan Benchmark"], firstSeen: '2026-10-25T07:40:00+09:00' }] }) }), env, {});
  const r = await call('radar_today', { hours: 72 }, opts);
  const a = r.text.split('[A · ')[1].split('[B · ')[0];
  assert.match(a, /미국 관보 최종 판정: Certain Hot-Rolled Steel Flat Products From the Republic of Korea: Final Results of Countervailing Duty Administrative Review — 본문에 포스코·현대제철 · 결정문 목차에 흔치 않은 항목\(관보 부록 원문\): "Comment 8: Whether the Constructing and Operation of Workplace Nursery Program is Countervailable"/);
  const t = await call('trade_remedies', { section: 'us' }, opts);
  assert.match(t.text, /결정문 목차 — 흔치 않은 항목\(관보 부록 원문\): "Comment 8: Whether the Constructing/);
  assert.match(t.text, /결정문 목차 — 출입처 이름\(관보 부록 원문\): "Comment 6: Whether to Modify POSCO's KEXIM OICP Loan Benchmark"/);
  const items = await (await radarItems(new Request(ORIGIN + '/ingest/radar-items?hours=72', { headers: { Authorization: `Bearer ${TOKEN}` } }), env, { now: NOW })).json();
  assert.deepEqual(items.items.find((x) => x.id === 'fr:2026-20778').check.terms, ['관세', '보조금']);
});

test('us_recalls: NHTSA full-file recalls with Korean links reach A; imports alone are B; tool shows supplier box', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const doc = { schema: 'us_recalls/v1', generatedAt: '2026-10-25T17:10:00+09:00', windowDays: 21, baselineSince: '2026-10-20T17:10:00+09:00',
    checks: [{ source: 'NHTSA 전체 리콜 파일', status: 'ok', rows: 246908 }, { source: 'NHTSA 원보고서(Part 573)', status: 'ok', read: 2, errors: 0 }],
    rules: ['미국 리콜이 국내 판매 차량에 해당하는지는 이 자료로 알 수 없다.'],
    recalls: [
      { id: 'nhtsa:26V698000', campaign: '26V698000', received: '2026-10-24', makes: ['AUDI'], models: 'Q4 E-TRON 2024~2025', component: 'ELECTRICAL SYSTEM:PROPULSION',
        affected: 9048, parkOutside: true, defect: 'The high voltage battery may fail and cause a fire.', supplierBox: 'Component Manufacturer Name: SK On Co., Ltd.',
        report: 'https://static.nhtsa.gov/odi/rcl/2026/RCLRPT-26V698-3069.pdf', url: 'https://www.nhtsa.gov/recalls?nhtsaId=26V698',
        why: [{ role: '제조사(출입처 브랜드)', beat: '아우디코리아', name: '아우디' }, { role: '부품 공급사(원보고서, 출입처 아님)', beat: null, name: 'SK온' }],
        firstSeen: '2026-10-25T17:10:00+09:00', isNew: true },
      { id: 'nhtsa:26V701000', campaign: '26V701000', received: '2026-10-24', makes: ['BMW'], models: 'X5 2026', component: 'BRAKES', affected: 300,
        defect: 'Brake hose.', url: 'https://www.nhtsa.gov/recalls?nhtsaId=26V701', why: [{ role: '제조사(출입처 브랜드)', beat: 'BMW코리아', name: 'BMW' }],
        firstSeen: '2026-10-25T17:10:00+09:00', isNew: true },
      // 10-31: 수입 브랜드만 걸린 큰 리콜은 B, 출입처 직접 리콜도 1,000대 미만이면 B
      { id: 'nhtsa:26V702000', campaign: '26V702000', received: '2026-10-24', makes: ['BMW'], models: 'X3 2025', component: 'AIR BAGS', affected: 52000,
        defect: 'Air bag.', url: 'https://www.nhtsa.gov/recalls?nhtsaId=26V702', why: [{ role: '제조사(출입처 브랜드)', beat: 'BMW코리아', name: 'BMW' }],
        firstSeen: '2026-10-25T17:10:00+09:00', isNew: true },
      { id: 'nhtsa:26V692000', campaign: '26V692000', received: '2026-10-24', makes: ['HYUNDAI'], models: 'ELANTRA 2026', component: 'SUSPENSION', affected: 24,
        defect: 'Strut fasteners.', url: 'https://www.nhtsa.gov/recalls?nhtsaId=26V692', why: [{ role: '제조사(출입처 브랜드)', beat: '현대차', name: '현대차' }],
        firstSeen: '2026-10-25T17:10:00+09:00', isNew: true }],
    invLookbackDays: 120,
    investigations: [
      { id: 'odi:PE26010', action: 'PE26010', type: '예비조사(PE)', kind: '조사 개시', opened: '2026-10-24', closed: null, models: 'HYUNDAI TUCSON 2025',
        component: 'ELECTRICAL', subject: 'ICCU failure', summary: 'Loss of drive power.', recallCampaigns: [], tier: 'A',
        why: [{ role: '제조사(출입처 브랜드)', beat: '현대차', name: '현대차' }], beat: ['현대차'], url: 'https://www.nhtsa.gov/recalls?nhtsaId=PE26010',
        firstSeen: '2026-10-25T17:10:00+09:00', isNew: true },
      { id: 'odi:EA25001', action: 'EA25001', type: '공학분석(EA, 격상 단계)', kind: '조사 개시', opened: '2026-07-01', closed: null, models: 'KIA EV6 2023',
        component: 'SEATS', subject: 'Old probe', summary: '', recallCampaigns: [], tier: 'A', why: [{ role: '제조사(출입처 브랜드)', beat: '기아', name: '기아' }],
        url: 'https://www.nhtsa.gov/recalls?nhtsaId=EA25001', firstSeen: '2026-10-20T17:10:00+09:00', isNew: false }] };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/us-recalls', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const t = await call('us_recalls', {}, opts);
  assert.match(t.text, /\[신규\] 2026-10-24 · 26V698000 · 아우디\(제조사\(출입처 브랜드\)\) · SK온\(부품 공급사\(원보고서, 출입처 아님\)\)/);
  assert.match(t.text, /잡힌 사실: AUDI Q4 E-TRON 2024~2025 · ELECTRICAL SYSTEM:PROPULSION · 대상 9,048대 · 실외 주차 권고/);
  assert.match(t.text, /원보고서 공급사 칸\(원문\): Component Manufacturer Name: SK On Co\., Ltd\./);
  assert.match(t.text, /국내 판매 차량 해당 여부·국내 리콜 계획은 회사·국토부 확인 필요/);
  const r = await call('radar_today', { hours: 72 }, opts);
  const a = r.text.split('[A · ')[1].split('[B · ')[0];
  const b = r.text.split('[B · ')[1].split('[C · ')[0];
  assert.match(a, /미국 리콜 26V698000 접수 2026-10-24 · Q4 E-TRON 2024~2025 · ELECTRICAL SYSTEM:PROPULSION · 대상 9,048대 · 실외 주차 권고 — 아우디\(제조사\(출입처 브랜드\)\)·SK온/);
  assert.match(b, /미국 리콜 26V702000/);
  assert.match(b, /미국 리콜 26V692000 접수 2026-10-24 · ELANTRA 2026 · SUSPENSION · 대상 24대/);
  assert.doesNotMatch(a + b, /26V701000/);  // 수입 브랜드 300대 → 참고(C)
  assert.match(r.text, /\[C · 참고\(접힘\)\] \d+건/);
  assert.match(a, /미국 NHTSA 예비조사\(PE\) PE26010 조사 개시 · HYUNDAI TUCSON 2025 · ELECTRICAL · 「ICCU failure」 · 개시 2026-10-24 — 조사 개시는 결함 확정 아님/);
  assert.doesNotMatch(r.text, /Old probe/);  // first-read baseline with an old date
  assert.match(t.text, /\[결함조사\(ODI\) · 최근 120일 개시·종결\] 출입처 관련 2건/);
  assert.match(t.text, /\[신규\] 2026-10-24 · PE26010 예비조사\(PE\) 조사 개시 · 현대차\(제조사\(출입처 브랜드\)\)/);
  const items = await (await radarItems(new Request(ORIGIN + '/ingest/radar-items?hours=72', { headers: { Authorization: `Bearer ${TOKEN}` } }), env, { now: NOW })).json();
  const hit = items.items.find((x) => x.id === 'nhtsa:26V698000');
  assert.deepEqual([hit.check.who, hit.check.terms, hit.check.must], ['SK온', ['리콜', '아우디'], ['Q4', '9,048', '9048']]);
  // 브랜드만으로 찾지 않는다: 차종·대상 대수가 제목·요약에 하나는 있어야(10-31 운영: 아반떼 스트럿 24대 ↔ 투싼 에어백 남아공 기사)
  const bmw = items.items.find((x) => x.id === 'nhtsa:26V702000').check;
  assert.deepEqual([bmw.who, bmw.terms, bmw.places, bmw.must], ['BMW', ['X3', '리콜'], ['X3'], ['X3', '52,000', '52000', '5만2000', '5만2,000', '5만 2000', '5만2천']]);
  const hy = items.items.find((x) => x.id === 'nhtsa:26V692000').check;
  assert.deepEqual([hy.who, hy.terms, hy.must], ['현대차', ['아반떼', '리콜'], ['아반떼', '엘란트라']]);
  assert.equal(items.items.find((x) => x.id === 'nhtsa:26V701000'), undefined);  // C는 보도 대조 안 함
  // 영문 부품사(원보고서 공급사 칸)는 국내 기사에 안 나온다 — 브랜드로 찾는다(10-08 26V664000 제네시스 G80 9만4,622대 · NIDEC MOBILITY KOREA)
  const g80 = usRecallHint({ models: 'GENESIS·HYUNDAI G80 2017~2020, GENESIS 2015~2016', affected: 94622 },
    [{ role: '제조사(출입처 브랜드)', name: '제네시스' }, { role: '부품 공급사(원보고서, 한국 소재)', name: 'NIDEC MOBILITY KOREA CORPORATION' }]);
  assert.deepEqual([g80.who, g80.terms, g80.must], ['제네시스', ['G80', '리콜'], ['G80', '94,622', '94622', '9만4622', '9만4,622', '9만 4622']]);
  assert.deepEqual(usRecallModels('HYUNDAI ELANTRA 2026, TUCSON HYBRID 2026'), ['아반떼', '엘란트라', '투싼']);
  assert.deepEqual(countForms(999), []);
  assert.deepEqual(dueAt(new Date('2026-10-28T08:10:00Z')), ['us-recalls.yml']);  // Wed 17:10 KST
});

test('us_recalls: consumer complaint spikes (pre-recall signal) are B, C after a same-part recall, and never A', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const now = new Date(Date.now() - 3600000).toISOString();
  const spike = (id, extra) => ({ id, make: 'HYUNDAI', model: 'SANTA FE HYBRID', beat: '현대차', brand: '현대차', window: ['2026-09-30', '2026-10-28'],
    complaints: 10, parts: [{ component: 'FUEL/PROPULSION SYSTEM', recent: 10, baselinePer28: 2.3, fire: 0, crash: 0, injured: 0, deaths: 0 },
      { component: 'POWER TRAIN', recent: 8, baselinePer28: 2.7, fire: 0, crash: 1, injured: 1, deaths: 0 }],
    fire: 0, crash: 1, injured: 1, deaths: 0, years: '2025(8)·2026(2)', samples: [{ odino: '11774001', year: '2025', received: '2026-10-20', text: 'The car lost power on the highway.' }],
    recentRecalls: [], sameComponentRecall: [], tier: 'B', url: 'https://api.nhtsa.gov/complaints/complaintsByVehicle?make=HYUNDAI&model=SANTA%20FE%20HYBRID&modelYear=2025',
    firstSeen: now, lastSeen: now, active: true, isNew: true, ...extra });
  const doc = { schema: 'us_recalls/v1', generatedAt: now, windowDays: 21, checks: [{ source: 'NHTSA 전체 리콜 파일', status: 'ok' }, { source: 'NHTSA 소비자 결함 신고', status: 'ok', rows: 25639 }],
    rules: [], recalls: [], investigations: [],
    complaints: { window: ['2026-09-30', '2026-10-28'], windowDays: 28, rules: ['소비자 결함 신고는 결함 확정이 아니다.'], spikes: [
      spike('cmpl:HYUNDAI:SANTA FE HYBRID'),
      spike('cmpl:KIA:SORENTO', { make: 'KIA', model: 'SORENTO', beat: '기아', brand: '기아', complaints: 9, tier: 'C', parts: [{ component: 'STEERING', recent: 9, baselinePer28: 1.0 }],
        recentRecalls: [{ campaign: '26V700000', received: '2026-10-22', component: 'STEERING:GEAR BOX' }], sameComponentRecall: ['26V700000'] }),
      spike('cmpl:HYUNDAI:TUCSON', { model: 'TUCSON', active: false })] } };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/us-recalls', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const t = await call('us_recalls', {}, opts);
  assert.match(t.text, /\[소비자 결함 신고 급증 · 최근 28일\(2026-09-30~2026-10-28\), 앞 24주와 비교\] 2건/);
  assert.match(t.text, /\[신규\] B · 현대차 SANTA FE HYBRID · 연식 2025\(8\)·2026\(2\) · 신고 10건 · 충돌 1·부상 1/);
  assert.match(t.text, /부품별: FUEL\/PROPULSION SYSTEM 10건\(평소 28일 2\.3\), POWER TRAIN 8건\(평소 28일 2\.7\)/);
  assert.match(t.text, /신고 11774001\(2025년형, 접수 2026-10-20\): "The car lost power on the highway\."/);
  assert.match(t.text, /최근 60일 같은 차종 리콜: 26V700000\(2026-10-22, STEERING:GEAR BOX\) — 같은 부품이라 리콜 공지 뒤 신고일 수 있음/);
  assert.doesNotMatch(t.text, /TUCSON/);  // 지금은 안 튀는 지난 급증
  const r = await call('radar_today', { include_minor: true }, opts);
  const b = r.text.split('[B · ')[1].split('[C · ')[0];
  assert.match(b, /미국 소비자 결함 신고 급증 · 현대차 SANTA FE HYBRID\(연식 2025\(8\)·2026\(2\)\) · 최근 28일\(2026-09-30~2026-10-28\) 신고 10건 · FUEL\/PROPULSION SYSTEM 10건/);
  assert.doesNotMatch(r.text.split('[A · ')[1].split('[B · ')[0], /결함 신고 급증/);
  assert.match(r.text.split('[C · ')[1], /기아 SORENTO[^\n]*같은 부품 리콜 26V700000 뒤 신고일 수 있음/);
  const items = await (await radarItems(new Request(ORIGIN + '/ingest/radar-items?hours=72', { headers: { Authorization: `Bearer ${TOKEN}` } }), env, { now: NOW })).json();
  const sf = items.items.find((x) => String(x.id).startsWith('cmpl:HYUNDAI:SANTA FE HYBRID')).check;
  assert.deepEqual([sf.who, sf.terms, sf.places], ['현대차', ['싼타페', '리콜'], ['싼타페']]);
});

test('scoop_reverse shows automatic prior-capture candidates by source with lead time, separate from human Y/P/N', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const art = (id, title, verdict, best, published = '2026-10-26T08:00:00+09:00') => ({ articleId: id, title, published, source: '뉴스저널리즘', companies: ['LS일렉트릭'], verdict, best, sameCompanyItems: best ? 1 : 0 });
  const doc = { schema: 'reverse_check/v1', generatedAt: '2026-10-26T19:20:00+09:00', windowDays: 30, memoryItems: 812, feedsLoaded: { 'us-litigation': true, 'partner-filings': true, trademarks: false }, feedsFailed: [], feedsEmpty: ['trademarks'],
    counts: {}, rules: ['자동 후보다. 사람 판정 Y/P/N과 다르다.'],
    articles: [
      art('a1', '[단독] LS일렉트릭, 미국 전기차 충전 특허 거절에 불복…연방항소법원 항소', '먼저 잡은 후보',
        { source: 'us-litigation', label: '미국 소송·판결', id: 'cl:75019340', text: 'In re: LS Electric Co., Ltd. LS일렉트릭, 미국 특허청 특허심판원(PTAB) 결정에 불복해 연방순회항소법원에 항소',
          seen: '2026-10-24T07:50+09:00', leadHours: 48.2, why: ['소송·판결', '특허·상표'] }),
      art('a2', '[단독] LG그룹, 현대차 로봇사업 수장 품었다', '없음', null, '2026-10-23T09:00:00+09:00')] };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/reverse-check', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const r = await call('scoop_reverse', {}, opts);
  assert.match(r.text, /먼저 잡은 후보 1 · 같은 회사 항목만 0 · 없음 1 · 회사 미상 0 \(레이더 기억 812건, 감시 2\/3 읽음, 저장 결과 없음 trademarks — 그 감시 항목은 대조 못 함\)/);
  assert.match(r.text, /원천별 먼저 잡은 후보: 미국 소송·판결 1건\(중간 48시간 앞\)/);
  assert.match(r.text, /레이더: 10-24 07:50 미국 소송·판결 — In re: LS Electric/);
  assert.match(r.text, /48\.2시간 앞, 겹친 낱말 소송·판결·특허·상표\) · id cl:75019340/);
  assert.match(r.text, /\[없음\] 1건\n- 10-23 09:00 · 뉴스저널리즘 「\[단독\] LG그룹, 현대차 로봇사업 수장 품었다」/);
  assert.match(r.text, /사람 판정 Y\/P\/N은 역추적 기록에 따로/);
  // radar_today shows the same automatic candidates (for chats whose connector list lacks scoop_reverse)
  const today = await call('radar_today', { hours: 72 }, opts);
  assert.match(today.text, /\[경쟁지 단독 역추적 · 자동 후보, 사람 판정\(Y\/P\/N\) 전\] 최근 14일 레이더가 먼저 잡은 후보 1건/);
  assert.match(today.text, /- 기사 10-26 08:00 · 뉴스저널리즘 「\[단독\] LS일렉트릭, 미국 전기차 충전 특허 거절에 불복…연방항소법원 항소」 · 기사 id a1/);
  assert.match(today.text, /레이더: 10-24 07:50 미국 소송·판결 — In re: LS Electric[^\n]*\(48\.2시간 앞, 겹친 낱말 소송·판결·특허·상표\) · id cl:75019340/);
  assert.doesNotMatch((await call('radar_today', { hours: 72, company: '포스코' }, opts)).text, /경쟁지 단독 역추적/);
  assert.ok((await call('scoop_reverse', {}, PRIVATE())).isError);
});

test('us_epa: a new model is A, an EV range change B, carryover C; tool shows EPA facts', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const v = (id, kind, extra = {}) => ({ id, company: '제네시스', make: 'Genesis', year: '2027', model: 'GV90 AWD', baseModel: 'GV90', atvType: 'EV', range: 300, comb: 88,
    vclass: 'Standard Sport Utility Vehicle 4WD', drive: 'All-Wheel Drive', trany: 'Automatic (A1)', created: '2026-10-25', kind, url: 'https://www.fueleconomy.gov/x',
    firstSeen: '2026-10-26T06:20:00+09:00', isNew: true, ...extra });
  const doc = { schema: 'us_epa/v1', generatedAt: '2026-10-26T06:20:00+09:00', checks: [{ source: 'EPA fueleconomy.gov 차량 파일', status: 'ok', fileModified: 'Tue, 29 Sep 2026 19:47:00 GMT' }],
    vehicles: [v('epa:6', '새 모델'), v('epa:5', '주행거리 변화', { company: '현대차', make: 'Hyundai', model: 'Ioniq 5', baseModel: 'Ioniq 5', range: 318, compare: { previousYear: 2025, previousRanges: [303] } }),
      v('epa:4', '연식 변경', { company: '기아', make: 'Kia', model: 'Sorento AWD', baseModel: 'Sorento', atvType: '', range: null, comb: 26 })], rules: ['미국 사양이다.'] };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/us-epa', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const r = await call('radar_today', { hours: 72, include_minor: true }, opts);
  const sec = (t) => r.text.split(`[${t} · `)[1].split(/\n\[[ABC] · /)[0];
  assert.match(sec('A'), /미국 EPA 등록\(새 모델\): 2027 Genesis GV90 AWD · EV · EPA 주행거리 300마일 · 복합 88MPGe · 등록 2026-10-25/);
  assert.match(sec('B'), /미국 EPA 등록\(주행거리 변화\): 2027 Hyundai Ioniq 5 · EV · EPA 주행거리 318마일 \(직전 2025년형 303마일\)/);
  assert.match(sec('C'), /미국 EPA 등록\(연식 변경\): 2027 Kia Sorento AWD/);
  const t = await call('us_epa', { kind: '주행거리 변화' }, opts);
  assert.match(t.text, /비교: 직전 2025년형 주행거리 303마일/);
  // NHTSA vPIC new model name → A
  const withVin = { ...doc, generatedAt: '2026-10-26T06:20:00+09:00', vpicModels: [{ id: 'vin:kia|ev4', company: '기아', make: 'Kia', model: 'EV4', years: [2027, 2028],
    kind: 'VIN 모델명 등록', url: 'https://vpic.nhtsa.dot.gov/api/vehicles/GetModelsForMakeIdYear/makeId/499/modelyear/2027?format=json', firstSeen: '2026-10-26T06:20:00+09:00', isNew: true }] };
  await worker.fetch(new Request(ORIGIN + '/ingest/us-epa', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(withVin) }), env, {});
  const r3 = await call('radar_today', { hours: 72 }, opts);
  assert.match(r3.text.split('[A · ')[1].split('[B · ')[0], /미국 NHTSA에 새 모델명 등록\(VIN 해독\): Kia 'EV4' · 2027·2028년형 — 출시·국내 도입은 미확인/);
  assert.match((await call('us_epa', {}, opts)).text, /\[NHTSA vPIC 새 모델명\(VIN 등록\)\] 1건\n- \[신규\] 2026-10-26 · Kia 'EV4' · 2027·2028년형/);
  const items = await (await radarItems(new Request(ORIGIN + '/ingest/radar-items?hours=72', { headers: { Authorization: `Bearer ${TOKEN}` } }), env, { now: NOW })).json();
  assert.deepEqual(items.items.find((x) => x.id === 'epa:6').check.terms, ['GV90', 'EPA']);
  assert.ok(!items.items.find((x) => x.id === 'epa:4'));
});

test('kr_fuel: a new model name is A, an EV range change B, other rows C; unset key is 미확인', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const v = (id, kind, extra = {}) => ({ id, company: '현대차', maker: '현대자동차(주)', model: '아반떼 N 2.0 터보', year: '2027', carKind: '승용', carType: '준중형',
    fuel: '휘발유', displacement: '1998', gear: '자동 8단', eff: '10.6', urban: '9.4', highway: '12.6', co2: '160', grade: '4', range: '', registered: '2026-10-25',
    kind, bulk: false, url: 'https://www.data.go.kr/data/15139827/openapi.do', firstSeen: '2026-10-26T06:10:00+09:00', isNew: true, ...extra });
  const doc = { schema: 'kr_fuel/v1', generatedAt: '2026-10-26T06:10:00+09:00', status: 'complete', dataset: 'https://www.data.go.kr/data/15139827/openapi.do',
    checks: [{ source: '에너지공단 자동차 표시연비(공공데이터포털 15139827)', status: 'ok', rows: 9000, beatRows: 3100 }],
    vehicles: [v('kf:1', '새 모델명'),
      v('kf:2', '주행거리 변화', { company: '기아', maker: '기아(주)', model: 'EV3 롱레인지', fuel: '전기', displacement: '', eff: '5.6', range: '525', compare: { previousRanges: [501] } }),
      v('kf:3', '사양·연식 추가', { model: '아반떼 1.6 가솔린', eff: '15.0' })], rules: ['연비 신고는 출시 확정이 아니다.'] };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/kr-fuel', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const r = await call('radar_today', { hours: 72, include_minor: true }, opts);
  const sec = (t) => r.text.split(`[${t} · `)[1].split(/\n\[[ABC] · /)[0];
  assert.match(sec('A'), /국내 연비 신고\(새 모델명\): 현대자동차\(주\) 아반떼 N 2\.0 터보 · 2027년 · 휘발유 1998cc · 표시연비 10\.6km\/L · 등록 2026-10-25/);
  assert.match(sec('B'), /국내 연비 신고\(주행거리 변화\): 기아\(주\) EV3 롱레인지 · 2027년 · 전기 · 표시연비 5\.6km\/kWh · 1회 충전 525km \(같은 모델명 이전 501km\)/);
  assert.match(sec('C'), /국내 연비 신고\(사양·연식 추가\): 현대자동차\(주\) 아반떼 1\.6 가솔린/);
  const t = await call('kr_fuel', { kind: '주행거리 변화' }, opts);
  assert.match(t.text, /목록 정상 · 전체 9000행 · 출입처 3100행/);
  assert.match(t.text, /비교: 같은 모델명 이전 행 1회 충전 501km/);
  const items = await (await radarItems(new Request(ORIGIN + '/ingest/radar-items?hours=72', { headers: { Authorization: `Bearer ${TOKEN}` } }), env, { now: NOW })).json();
  assert.deepEqual(items.items.find((x) => x.id === 'kf:1').check.terms, ['아반떼', '연비']);
  assert.ok(!items.items.find((x) => x.id === 'kf:3'));
  // before the dataset is approved for the key: the watch says 미설정, not 0건
  const unset = { ...doc, status: 'unset', vehicles: [], checks: [{ source: '에너지공단 자동차 표시연비(공공데이터포털 15139827)', status: 'unset', error: '공공데이터포털 활용신청 필요(15139827) — 응답 30 SERVICE_KEY_IS_NOT_REGISTERED_ERROR' }] };
  await worker.fetch(new Request(ORIGIN + '/ingest/kr-fuel', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(unset) }), env, {});
  const r2 = await call('radar_today', { hours: 72 }, opts);
  assert.match(r2.text, /- 국내 연비 신고: 미설정 에너지공단 자동차 표시연비\(공공데이터포털 15139827\)\(공공데이터포털 활용신청 필요/);
  assert.match((await call('kr_fuel', {}, opts)).text, /미확인\(0건 아님\): 공공데이터포털 활용신청 필요/);
});

test('overseas awards: a beat company in the TED winner field is A; other Korean winners stay in the tool', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const a = (id, extra = {}) => ({ id, source: 'EU TED', published: '2026-10-25', kind: '낙찰', buyer: 'Energinet Eltransmission A/S', buyerCountry: 'DNK',
    winners: ['Hyosung Heavy Industires Corporation'], winnerCountry: ['KOR'], winnerIds: ['578-87-00896'], company: '효성중공업', companies: ['효성중공업'],
    title: '400/220 kV Autotransformers for SLF02', value: 15923696, currency: 'EUR', concluded: '2026-06-19', noticeType: 'can-standard',
    url: 'https://ted.europa.eu/en/notice/-/detail/545946-2026', firstSeen: '2026-10-25T17:30:00+09:00', isNew: true, tier: 'A', ...extra });
  const doc = { schema: 'overseas_awards/v1', generatedAt: '2026-10-25T17:30:00+09:00', status: 'partial', coverage: 'EU TED · 영국 Find a Tender · 세계은행 · 바레인',
    checks: [{ source: 'EU TED', query: '한국 국적 낙찰자', status: 'ok', returned: 20, matched: 3 }, { source: '세계은행 조달', query: 'LS Cable', status: 'failed', error: 'HTTP 503' }],
    rules: ['낙찰자 칸에 이름이 있을 때만 잡는다.'],
    items: [a('ted:545946-2026'),
      a('ted:546637-2026', { kind: '계약 변경', tier: 'B', company: 'HD현대일렉트릭', winners: ['HD Hyundai Electric Europe GmbH'], winnerCountry: ['DEU'], winnerIds: [], value: null, concluded: null }),
      a('ted:721359-2026', { tier: 'C', company: null, companies: [], winners: ['Nano Co., Ltd.'], buyer: 'Enea Elektrownia Połaniec', buyerCountry: 'POL', value: null }),
      a('pcc:3.13.31:0081520071:BDM-1-71300001', { source: '대만 정부조달(PCC)', published: '2026-10-24', buyer: '台灣電力股份有限公司', buyerCountry: 'TWN', company: 'LS전선', companies: ['LS전선'],
        winners: ['LS Cable & System Ltd.'], winnerCount: 2, winnerCountry: [], winnerIds: [], value: 276084986, currency: 'TWD', priceKind: '출입처 낙찰 품목 결정 금액 합',
        title: '115年度超耐熱鋼心鋁線 — 2번 품목 LS Cable & System Ltd. NT$276,084,986(원산지 南韓(Republic of Korea))', concluded: '2026-10-24',
        url: 'https://openfunltd.github.io/pcc-viewer/tender.html?unit_id=3.13.31&job_number=0081520071',
        official: 'https://web.pcc.gov.tw/prkms/tender/common/noticeDate/redirectPublic?ds=20261024&fn=BDM-1-71300001.xml' })] };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/overseas-awards', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const r = await call('radar_today', { hours: 72, include_minor: true }, opts);
  const sec = (t) => r.text.split(`[${t} · `)[1].split(/\n\[[ABC] · /)[0];
  assert.match(sec('A'), /해외 낙찰\(EU TED\): 덴마크 Energinet Eltransmission A\/S ← Hyosung Heavy Industires Corporation · 400\/220 kV Autotransformers for SLF02 · EUR 15,923,696 · 계약 2026-06-19 · 공고 2026-10-25/);
  assert.match(sec('B'), /해외 계약 변경\(EU TED\): 덴마크 Energinet Eltransmission A\/S ← HD Hyundai Electric Europe GmbH · 400\/220 kV Autotransformers for SLF02 · 금액 미기재/);
  assert.match(sec('C'), /폴란드 Enea Elektrownia Połaniec ← Nano Co\., Ltd\./);
  assert.match(r.text, /- 해외 발주처 낙찰: 일부 실패 1건\(세계은행 조달\)/);
  assert.match(sec('A'), /해외 낙찰\(대만 정부조달\(PCC\)\): 대만 台灣電力股份有限公司 ← LS Cable & System Ltd\. 외 1곳 · 115年度超耐熱鋼心鋁線 — 2번 품목[^\n]* · TWD 276,084,986 · 계약 2026-10-24/);
  const t = await call('partner_filings', {}, opts);
  assert.match(t.text, /\[해외 발주처 낙찰 · EU TED · 영국 Find a Tender · 세계은행 · 바레인 · 공고 최근 120일\] 출입처 3건 · 출입처 밖 한국 기업 1건/);
  assert.match(t.text, /원문: https:\/\/openfunltd\.github\.io\/pcc-viewer\/tender\.html\?unit_id=3\.13\.31&job_number=0081520071 · 정부전자조달망 https:\/\/web\.pcc\.gov\.tw\/[^\n]*\n   검증 상태: 공고의 낙찰자 칸\(대만 PCC 공고의 得標廠商/);
  assert.match(t.text, /원천: EU TED 1\/1 정상 · 세계은행 조달 0\/1 정상\(미확인: LS Cable\(HTTP 503\)\)/);
  assert.match(t.text, /\[신규\] 2026-10-25 · EU TED 낙찰 · 효성중공업 · 발주 Energinet Eltransmission A\/S\(DNK\)\n   잡힌 사실: 낙찰자 Hyosung Heavy Industires Corporation\(KOR, 식별번호 578-87-00896\) · 400\/220 kV Autotransformers for SLF02 · EUR 15,923,696 · 계약 2026-06-19/);
  assert.doesNotMatch(t.text, /Nano Co/);
  assert.match((await call('partner_filings', { company: 'Nano' }, opts)).text, /출입처 밖 한국 기업 · 발주 Enea/);
  assert.doesNotMatch((await call('partner_filings', { source: 'EDGAR' }, opts)).text, /해외 발주처 낙찰/);
  const items = await (await radarItems(new Request(ORIGIN + '/ingest/radar-items?hours=72', { headers: { Authorization: `Bearer ${TOKEN}` } }), env, { now: NOW })).json();
  assert.deepEqual(items.items.find((x) => x.id === 'ted:545946-2026').check.terms, ['덴마크', '수주']);
  assert.deepEqual(dueAt(new Date('2026-10-28T21:50:00Z')), ['overseas-awards.yml']);  // Thu 06:50 KST
  assert.deepEqual(dueAt(new Date('2026-10-29T08:30:00Z')), ['overseas-awards.yml']);  // Thu 17:30 KST
});

test('overseas awards: a Bahrain opened bid is a bid, not an award — lowest big bid A, others B, its first run a baseline', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const b = (id, extra = {}) => ({ id, source: '바레인 입찰위원회 개찰', published: '2026-10-25', kind: '개찰(응찰)', buyer: 'Electricity and Water Authority (Planning)',
    buyerCountry: 'BHR', winners: [], winnerCountry: [], winnerIds: [], company: '일진전기', companies: ['일진전기'],
    title: '4669/2025/5100 400kV and 220kV Feeder Cable Works for Establishment of New Sitra 400kV Grid Substation', bidder: 'ILJIN ELECTRIC',
    bidStatus: 'Accepted', value: 35004118.33, currency: 'BHD', options: 1, rank: 1, priced: 3, bidCount: 3, lowest: true,
    others: [{ name: 'TAIHAN ELECTRIC WIRE CO LTD', value: 45648300 }, { name: 'LS CABLE AND SYSTEM LTD', value: 46659985.55 }], lowestBid: null,
    url: 'https://www.tenderboard.gov.bh/OpenedTenderDetails/?id=4669%2f2025%2f5100&source=New&envelope=PB&type=1',
    firstSeen: '2026-10-25T17:30:00+09:00', isNew: true, baseline: false, tier: 'A', ...extra });
  const doc = { schema: 'overseas_awards/v1', generatedAt: '2026-10-25T17:30:00+09:00', status: 'complete', coverage: 'EU TED · 바레인 입찰위원회 월간 낙찰 보고서·개찰 결과',
    checks: [{ source: '바레인 입찰위원회 개찰', query: '개찰 결과(응찰 회사·응찰가)', status: 'ok', returned: 40, matched: 3,
      note: '목록 40건(개찰 2026-10-01~2026-10-25) · 새 개찰 3 · 상세 3' }], rules: [],
    items: [b('bhopen:9001:일진전기'),
      b('bhopen:9001:LS전선', { company: 'LS전선', companies: ['LS전선'], bidder: 'LS CABLE AND SYSTEM LTD', value: 46659985.55, rank: 3, lowest: false, tier: 'B',
        lowestBid: { name: 'ILJIN ELECTRIC', value: 35004118.33 } }),
      b('bhopen:8001:LS일렉트릭', { company: 'LS일렉트릭', companies: ['LS일렉트릭'], bidder: 'LS ELECTRIC CO., LTD.', published: '2026-09-01', value: null,
        rank: null, priced: null, lowest: false, isNew: false, baseline: true, tier: 'B', title: 'PT/CSD/AS/2026/019 Supply of 66KV Switchgear' })] };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/overseas-awards', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const r = await call('radar_today', { hours: 72, include_minor: true }, opts);
  const sec = (t) => r.text.split(`[${t} · `)[1].split(/\n\[[ABC] · /)[0];
  assert.match(sec('A'), /해외 개찰\(바레인 입찰위원회 개찰\): 바레인 Electricity and Water Authority \(Planning\) · 4669\/2025\/5100 400kV[^\n]* — ILJIN ELECTRIC BHD 35,004,118 · 응찰가 1위\/3곳\(최저가\) · 개찰 2026-10-25 · 낙찰 아님/);
  assert.match(sec('B'), /— LS CABLE AND SYSTEM LTD BHD 46,659,986 · 응찰가 3위\/3곳 · 최저 ILJIN ELECTRIC BHD 35,004,118/);
  assert.doesNotMatch(r.text, /66KV Switchgear/);  // 이 원천 첫 실행의 예전 개찰(기준선)은 오늘 항목이 아니다
  const t = await call('partner_filings', { company: '일진' }, opts);
  assert.match(t.text, /\[신규\] 2026-10-25 · 바레인 입찰위원회 개찰 개찰\(응찰\) · 일진전기 · 발주 Electricity and Water Authority \(Planning\)\(BHR\)\n   잡힌 사실: 응찰 ILJIN ELECTRIC BHD 35,004,118\.33 · 상태 Accepted · 응찰가 1위\/3곳\(최저가\) · 응찰 3곳 · 다른 응찰 TAIHAN ELECTRIC WIRE CO LTD BHD 45,648,300 \/ LS CABLE AND SYSTEM LTD BHD 46,659,985\.55/);
  assert.match(t.text, /검증 상태: 입찰위원회 개찰 결과\(응찰가 공개\) — 낙찰 아님/);
  assert.match(t.text, /\n범위: 바레인 입찰위원회 개찰 — 목록 40건\(개찰 2026-10-01~2026-10-25\) · 새 개찰 3 · 상세 3\n/);
  const all = await call('partner_filings', {}, opts);
  assert.match(all.text, /2026-09-01 · 바레인 입찰위원회 개찰 개찰\(응찰\) · LS일렉트릭[^\n]*\n   잡힌 사실: 응찰 LS ELECTRIC CO\., LTD\. 응찰가 미공개 · 상태 Accepted · 응찰가 순위 없음/);
  const items = await (await radarItems(new Request(ORIGIN + '/ingest/radar-items?hours=72', { headers: { Authorization: `Bearer ${TOKEN}` } }), env, { now: NOW })).json();
  assert.deepEqual(items.items.find((x) => x.id === 'bhopen:9001:일진전기').check.terms, ['바레인', '입찰']);
  assert.deepEqual(items.items.find((x) => x.id === 'bhopen:9001:일진전기').check.places, ['바레인']);
});

test('kr insolvency: a beat-industry manufacturer entering court proceedings is A and listed under kr_official', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const ev = (id, extra = {}) => ({ id, source: '대법원 회생·파산 공고', kind: '회생 개시', stage: 'start', title: '회생절차 개시결정 공고', company: '주식회사 엠디스틸',
    court: '서울회생법원', task: '법인회생', caseNo: '2026회합 1129', division: '제17부', posted: '2026-10-25',
    industry: { match: 'core', label: '1차 철강', code: '24121', industry: '냉간 압연 및 압출 제품 제조업', product: '냉연강판', employees: 85, address: '경기도 화성시 팔탄면 …', factories: 1 },
    match: 'core', watch: null, tier: 'A', url: 'https://ecfs.scourt.go.kr/sgvo/websquare/websquare.html?w2xPath=/sgvo/ui/sgvo200/SGVO201M01.xml?paramData=e30=',
    listUrl: 'https://www.scourt.go.kr/portal/notice/insolvency/insolvency.jsp', firstSeen: '2026-10-25T17:20:00+09:00', baseline: false, isNew: true, ...extra });
  const doc = { schema: 'kr_insolvency/v1', generatedAt: '2026-10-25T17:20:00+09:00', status: 'partial', watchlistSize: 0, rules: ['법원 공고는 절차 단계다.'],
    checks: [{ source: '서울회생법원 법인회생', status: 'ok', returned: 40 }, { source: '부산회생법원 법인회생', status: 'failed', error: 'ConnectTimeout' },
      { source: '회생회사 M&A 공고 제조업(기계,금속,중공업)', status: 'ok', returned: 21 }, { source: '공장등록 업종 조회', status: 'partial', returned: 120, pending: 68 }],
    events: [ev('ins:1'),
      ev('ins:2', { kind: '포괄적 금지명령', company: '주식회사 한빛오토텍', tier: 'B', match: 'product', industry: { match: 'product', label: '금속가공제품', code: '25912', product: '자동차 차체 프레스 부품, 자동차 차체 프레스 부품, 자동차 차체 프레스 부품', employees: 120, address: '충청남도 아산시 …', factories: 1 } }),
      ev('ins:3', { company: '주식회사 메탈153', tier: 'C', match: 'name', industry: { match: null, factories: 0 } }),
      ev('ins:4', { company: '삼보산업 주식회사', court: '수원회생법원', tier: 'B', industry: { match: 'core', label: '자동차 부품', code: '30332', product: '자동차부품', employees: 22, address: '대구광역시 서구 염색공단천로', factories: 13, owners: 4, regionMismatch: true } })] };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/kr-insolvency', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const r = await call('radar_today', { hours: 72, include_minor: true }, opts);
  const sec = (t) => r.text.split(`[${t} · `)[1].split(/\n\[[ABC] · /)[0];
  assert.match(sec('A'), /회생 개시: 주식회사 엠디스틸 \(서울회생법원 2026회합 1129\) · 공장등록 업종 1차 철강 · 주생산품 냉연강판 · 종업원 85명 · 경기도 화성시 · 공고 2026-10-25 — 거래 관계·납품 영향 미확인/);
  assert.match(sec('B'), /포괄적 금지명령: 주식회사 한빛오토텍 \(서울회생법원 2026회합 1129\) · 공장등록 업종 금속가공제품 · 주생산품 자동차 차체 프레스 부품 · 종업원 120명/);  // 같은 항목 반복은 한 번만
  assert.match(sec('C'), /주식회사 메탈153 [^\n]*공장등록 없음 — 이름 낱말만/);
  assert.match(sec('B'), /삼보산업 주식회사 \(수원회생법원 2026회합 1129\) · 공장등록 업종 자동차 부품 [^\n]*· 대구광역시 서구 · ⚠ 공장 주소가 관할 법원 지역 밖\(다른 회사일 수 있음\) · 같은 이름 공장 대표자 4명/);
  assert.match(r.text, /- 협력사 회생·파산: 일부 실패 1건\(부산회생법원 법인회생\)/);
  const t = await call('kr_official', { section: 'insolvency' }, opts);
  assert.match(t.text, /\[협력사 회생·파산 · 대법원 회생·파산 공고\(법원 2곳 목록\)·회생회사 M&A 공고 · 공고 최근 30일\] 출입 업종 3건 · 이름 낱말만 1건/);
  assert.match(t.text, /종업원 22명 · 대구광역시 서구 염색공단천로 · 같은 이름 등록 공장 13곳 · ⚠ 공장 주소가 관할 법원 지역 밖/);
  assert.match(t.text, /원천: 법원 목록 1\/2 정상\(미확인: 부산회생법원 법인회생\(ConnectTimeout\)\) · 회생회사 M&A 공고 제조업\(기계,금속,중공업\) ok · 공장등록 업종 조회 partial\(업종 조회 대기 68곳 — 다음 실행\) · 협력사 명단 비어 있음/);
  assert.match(t.text, /\[신규\] 2026-10-25 · 회생 개시 · 주식회사 엠디스틸 · 서울회생법원 2026회합 1129\(제17부\)\n   잡힌 사실: 공고 「회생절차 개시결정 공고」 · 공장등록 업종 1차 철강\(24121 냉간 압연 및 압출 제품 제조업\) · 주생산품 냉연강판 · 종업원 85명/);
  assert.doesNotMatch(t.text, /메탈153/);
  assert.match((await call('kr_official', { section: 'insolvency', company: '메탈' }, opts)).text, /주식회사 메탈153/);
  // without the kr-official feed the insolvency section still shows
  assert.match((await call('kr_official', {}, opts)).text, /공장등록·관보 입법예고 결과가 아직 없음[\s\S]*\[협력사 회생·파산/);
  const items = await (await radarItems(new Request(ORIGIN + '/ingest/radar-items?hours=72', { headers: { Authorization: `Bearer ${TOKEN}` } }), env, { now: NOW })).json();
  assert.deepEqual(items.items.find((x) => x.id === 'ins:1').check, { who: '엠디스틸', terms: ['회생'], alts: { 회생: ['회생', '법정관리', '파산', '기업회생', '워크아웃'] } });
  // 파산 선고는 '파산'으로, M&A 매각 공고는 '매각'으로 찾는다(10-31 운영: 케이아이씨 파산 선고를 "케이아이씨 회생"으로 대조)
  assert.deepEqual([insolvencyWord('파산 선고'), insolvencyWord('파산 폐지'), insolvencyWord('M&A 매각 공고'), insolvencyWord('포괄적 금지명령'), insolvencyWord('회생 개시')],
    ['파산', '파산', '매각', '회생', '회생']);
  assert.deepEqual(dueAt(new Date('2026-10-28T22:20:00Z')), ['kr-insolvency.yml']);  // Thu 07:20 KST
  assert.deepEqual(dueAt(new Date('2026-10-29T08:20:00Z')), ['kr-insolvency.yml']);  // Thu 17:20 KST
});

test('kr energy: beat-group power permits and nuclear agenda results show in radar_today and kr_signals', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const it = (id, extra) => ({ id, source: '전기위원회', kind: '조건부 허가', title: 'GS 당진 바이오 발전사업', meeting: '제329차', held: '2026-10-24', posted: '2026-10-25',
    company: 'GS', tier: 'A', url: 'https://www.korec.go.kr/commonfile/fileDownLoad.do?x', firstSeen: '2026-10-25T18:10:00+09:00', baseline: false, isNew: true, ...extra });
  const doc = { schema: 'kr_energy/v1', generatedAt: '2026-10-25T18:10:00+09:00', status: 'complete', rules: ['허가는 착공이 아니다.'],
    checks: [{ source: '전기위원회 개최결과', status: 'ok', returned: 11, read: 1 }, { source: '원자력안전위원회 회의', status: 'ok', returned: 15 }],
    items: [it('korec:329:gs'),
      it('korec:329:wind', { title: '신안 우이 해상풍력 발전사업', company: null, tier: 'B' }),
      it('korec:329:sun', { title: '고흥 가야신양해밀솔라 태양광 발전사업', company: null, tier: 'C' }),
      it('nssc:1:1', { source: '원자력안전위원회', kind: '심의·의결 안건', title: '고리 원자력발전소 3·4호기 계속운전 허가(안)', meeting: '제2026-17회(10.27) 원자력안전위원회',
        held: '2026-10-27', posted: '2026-10-21', company: null, tier: 'B', result: '원안의결', firstSeen: '2026-10-21T18:10:00+09:00', resultSeen: '2026-10-25T18:10:00+09:00' })] };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/kr-energy', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const r = await call('radar_today', { hours: 72, include_minor: true }, opts);
  const sec = (t) => r.text.split(`[${t} · `)[1].split(/\n\[[ABC] · /)[0];
  assert.match(sec('A'), /전기위원회 제329차 조건부 허가: GS 당진 바이오 발전사업 · 회의·허가일 2026-10-24/);
  assert.match(sec('B'), /전기위원회 제329차 조건부 허가: 신안 우이 해상풍력 발전사업/);
  assert.match(sec('B'), /원자력안전위원회 심의·의결 안건: 고리 원자력발전소 3·4호기 계속운전 허가\(안\) → 원안의결 · 회의 2026-10-27/);  // 결과가 새로 붙어 다시 올라옴
  assert.match(sec('C'), /고흥 가야신양해밀솔라/);
  const t = await call('kr_signals', { section: 'energy' }, opts);
  assert.match(t.text, /\[전기위원회·원안위 · 최근 60일\] 출입처·주요 3건 · 기타 1건/);
  assert.match(t.text, /- \[신규\] 2026-10-24 · 전기위원회 제329차 · 조건부 허가 · GS\n   잡힌 사실: GS 당진 바이오 발전사업/);
  assert.match(t.text, /고리 원자력발전소 3·4호기 계속운전 허가\(안\) → 결과 원안의결/);
  assert.match((await call('kr_signals', {}, opts)).text, /공정위 의결서·한전 입찰·원자재 가격 결과가 아직 없음[\s\S]*\[전기위원회·원안위/);
  const items = await (await radarItems(new Request(ORIGIN + '/ingest/radar-items?hours=72', { headers: { Authorization: `Bearer ${TOKEN}` } }), env, { now: NOW })).json();
  assert.deepEqual(items.items.find((x) => x.id === 'korec:329:gs').check.terms, ['허가']);
  assert.deepEqual(dueAt(new Date('2026-10-29T06:40:00Z')), ['kr-energy.yml']);  // Thu 15:40 KST
  assert.deepEqual(dueAt(new Date('2026-10-29T09:10:00Z')), ['kr-energy.yml']);  // Thu 18:10 KST
});

test('kr building: a permit on a beat factory parcel is A; unset datasets show as 미설정', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const p = (id, extra) => ({ id, company: 'KG스틸', companies: ['KG스틸'], factory: '케이지스틸 주식회사', factoryId: 'fac:1', plot: '충청남도 당진시 송악읍 고대리 1-1번지',
    bldNm: '제강공장', archGbCdNm: '신축', mainPurpsCdNm: '공장', totArea: 12500.5, permitted: '2026-10-20', startPlanned: '2026-12-01', started: null, useApproved: null,
    kind: '새 허가', tier: 'A', firstSeen: '2026-10-26T07:45:00+09:00', baseline: false, isNew: true, ...extra });
  const doc = { schema: 'kr_building/v1', generatedAt: '2026-10-26T07:45:00+09:00', status: 'complete', plants: 286, parcelsResolved: 240, rules: ['건축주 비공개.'],
    unresolved: [{ company: '세아', plant: '세아베스틸', road: '전북특별자치도 군산시 동장산로 1', error: '지번 못 찾음' }],
    archFailed: [{ company: 'LS일렉트릭', plant: '엘에스일렉트릭(주)청주1공장', parcel: '충청북도 청주시 흥덕구 송정동 1', error: '빈 응답' }],
    checks: [{ source: '주소 변환', status: 'ok', returned: 240 }, { source: '건축인허가', status: 'ok', returned: 200 }],
    permits: [p('bld:1'), p('bld:2', { archGbCdNm: '대수선', totArea: 150, tier: 'C' }),
      p('bld:0', { permitted: '2026-08-01', firstSeen: '2026-10-19T07:45:00+09:00', baseline: true, isNew: false }),  // 지난주 기준선
      p('bld:3', { plot: '충청남도 당진시 송악읍 고대리 1-7번지', bldNm: '이웃산업(주) 공장', archGbCdNm: '증축', sameLot: false, tier: 'B' }),
      p('bld:4', { bldNm: '첫 조회 번지의 옛 허가', permitted: '2026-06-01', baseline: true, isNew: false }),  // 이 번지는 이번에 처음 봄
      p('bld:5', { bldNm: '공장 목록에서 빠진 공장', orphan: true })] };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/kr-building', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const r = await call('radar_today', { hours: 72 }, opts);
  assert.match(r.text.split('[A · ')[1].split('[B · ')[0], /건축허가: 케이지스틸 주식회사 부지\(충청남도 당진시 송악읍 고대리 1-1번지\) · 신축 공장 · 연면적 12,501㎡ · 허가 2026-10-20 · 착공예정 2026-12-01 — 건축주 미표기\(공장과 같은 번지\)/);
  assert.match(r.text.split('[B · ')[1], /케이지스틸 주식회사 부지와 같은 본번의 다른 필지\(충청남도 당진시 송악읍 고대리 1-7번지\) · 증축 공장 · 연면적 12,501㎡\(건물 전체일 수 있음, 증축분 아님\)[^\n]*건축주 미표기\(공장과 본번만 같은 다른 필지, 건물명 '이웃산업\(주\) 공장'\)/);
  assert.doesNotMatch(r.text, /첫 조회 번지의 옛 허가|공장 목록에서 빠진 공장/);
  const t = await call('kr_official', { section: 'building' }, opts);
  assert.match(t.text, /\[공장 부지 건축허가 · 출입처 공장 286곳 중 번지 확인 240곳 · 허가일 최근 90일\] 3건 · 소규모 1건/);
  assert.doesNotMatch(t.text, /공장 목록에서 빠진 공장/);
  assert.match(t.text, /번지 못 찾은 공장 1곳\(허가 미확인\): 세아 세아베스틸\(전북특별자치도 군산시 동장산로 1, 지번 못 찾음\)/);
  assert.match(t.text, /조회 실패 번지 1곳\(허가 미확인\): LS일렉트릭 엘에스일렉트릭\(주\)청주1공장\(충청북도 청주시 흥덕구 송정동 1, 빈 응답\)/);
  assert.match(t.text, /검증 상태: 건축주 미표기 — 공장과 본번만 같은 다른 필지라 이웃 회사 건물일 수 있음\(건물명 '이웃산업\(주\) 공장'\)/);
  const items = await (await radarItems(new Request(ORIGIN + '/ingest/radar-items?hours=72', { headers: { Authorization: `Bearer ${TOKEN}` } }), env, { now: NOW })).json();
  assert.deepEqual(items.items.find((x) => x.id === 'bld:1').check.terms, ['당진', '공장', '신설']);
  const unset = { ...doc, status: 'unset', permits: [], checks: [{ source: '주소 변환', status: 'unset', error: 'JUSO_CONFM_KEY 없음 — 도로명주소 검색API 승인키(business.juso.go.kr) 필요' },
    { source: '건축인허가', status: 'unset', error: '조회할 번지 없음 — 주소 변환 활용신청 후' }] };
  await worker.fetch(new Request(ORIGIN + '/ingest/kr-building', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(unset) }), env, {});
  assert.match((await call('radar_today', { hours: 72 }, opts)).text, /- 공장 부지 건축허가: 미설정 주소 변환\(JUSO_CONFM_KEY 없음 — 도로명주소 검색API 승인키\(business\.juso\.go\.kr\) 필요\)/);
});

test('overseas registry: a new UK company with a beat parent as PSC is A; a missing key is 미설정', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const c = (id, extra) => ({ id, company: '효성중공업(관련)', name: 'HYOSUNG HEAVY INDUSTRIES UK LTD', number: '16000001', status: 'active', type: 'ltd',
    created: '2026-10-24', sic: ['27110'], address: '1 Grid Way, London', url: 'https://find-and-update.company-information.service.gov.uk/company/16000001',
    psc: ['Hyosung Heavy Industries Corporation'], pscMatch: true, tier: 'A', firstSeen: '2026-10-25T06:00:00+09:00', baseline: false, isNew: true, ...extra });
  const doc = { schema: 'overseas_registry/v1', generatedAt: '2026-10-25T06:00:00+09:00', status: 'complete', windowStart: '2025-10-25', rules: ['PSC로 판단.'],
    checks: [{ source: '영국 Companies House hyosung', status: 'ok', returned: 3, matched: 1 }],
    companies: [c('ch:16000001'), c('ch:16000002', { company: '현대차', name: 'HYUNDAI OF BRISTOL LIMITED', number: '16000002', psc: ['John Smith'], pscMatch: false, tier: 'C' }),
      c('ch:16848629', { company: '넥센타이어', name: 'NEXEN TYRE U.K. LIMITED', number: '16848629', psc: [], pscMatch: false, nameStrong: true, tier: 'B' })] };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/overseas-registry', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const r = await call('radar_today', { hours: 72, include_minor: true }, opts);
  const sec = (t) => r.text.split(`[${t} · `)[1].split(/\n\[[ABC] · /)[0];
  assert.match(sec('A'), /영국 법인 설립 등기: HYOSUNG HEAVY INDUSTRIES UK LTD\(16000001\) · 설립 2026-10-24 · SIC 27110 · 지배 주주 Hyosung Heavy Industries Corporation/);
  assert.match(sec('C'), /HYUNDAI OF BRISTOL LIMITED[^\n]*출입처 본사 지배 주주 아님\(이름만 같음\)/);
  assert.match(sec('B'), /NEXEN TYRE U\.K\. LIMITED\(16848629\)[^\n]*지배 주주 미기재 — 지배 주주 아직 미기재, 이름이 본사 전체 이름/);
  const t = await call('partner_filings', {}, opts);
  assert.match(t.text, /\[해외 법인 등기 · 영국 Companies House · 보관 3곳\(첫 실행은 1년 전 설립부터, 이번 조회는 설립 2025-10-25 이후\)\] 출입처 지배 주주 1건 · 지배 주주 미기재·본사 이름 1건 · 이름만 같은 법인 1건\(company 낱말로 보기\)/);
  assert.match(t.text, /- \[신규\] 2026-10-24 설립 · 효성중공업\(관련\) · HYOSUNG HEAVY INDUSTRIES UK LTD \(16000001, active\)/);
  const unset = { ...doc, status: 'unset', companies: [], checks: [{ source: '영국 Companies House', status: 'unset', error: 'COMPANIES_HOUSE_API_KEY 없음(무료 발급)' }] };
  await worker.fetch(new Request(ORIGIN + '/ingest/overseas-registry', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(unset) }), env, {});
  assert.match((await call('radar_today', { hours: 72 }, opts)).text, /- 해외 법인 등기\(영국\): 미설정 영국 Companies House\(COMPANIES_HOUSE_API_KEY 없음\(무료 발급\)\)/);
  assert.deepEqual(dueAt(new Date('2026-10-28T21:00:00Z')), ['overseas-registry.yml']);  // Thu 06:00 KST
});

test('kr_official: 환경영향평가 new stage of a beat project is A and listed in the tool', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const doc = { schema: 'kr_official/v1', generatedAt: '2026-10-26T08:10:00+09:00', checks: [{ source: '환경영향평가(EIASS)', status: 'ok', returned: 66 }],
    factories: [], events: [], gazette: [], eiaSeen: [],
    eia: [{ id: 'eia:ND2026O009:2026-10-25:초안(진행)', company: '고려아연', kind: '환경영향평가', code: 'ND2026O009', category: '폐기물처리시설',
      name: '고려아연(주) 온산제련소 제2 폐기물처리시설 증설', received: '2026-10-25', completed: '', stage: '초안(진행)',
      url: 'https://www.eiass.go.kr/biz/base/info/searchListNew.do?menu=biz&biz_gubn=', firstSeen: '2026-10-26T08:10:00+09:00', isNew: true }] };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/kr-official', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const r = await call('radar_today', { hours: 72 }, opts);
  assert.match(r.text.split('[A · ')[1].split('[B · ')[0], /환경영향평가\(환경영향평가\) 초안\(진행\): 고려아연\(주\) 온산제련소 제2 폐기물처리시설 증설 · 폐기물처리시설 · 접수 2026-10-25 — 계획 단계, 착공·투자 확정 아님/);
  const t = await call('kr_official', {}, opts);
  assert.match(t.text, /\[환경영향평가 · 사업명에 출입처 이름 · 새 단계\] 1건\n- \[신규\] 2026-10-25 접수 · 고려아연 · 환경영향평가 초안\(진행\)/);
  const items = await (await radarItems(new Request(ORIGIN + '/ingest/radar-items?hours=72', { headers: { Authorization: `Bearer ${TOKEN}` } }), env, { now: NOW })).json();
  assert.deepEqual(items.items.find((x) => x.id.startsWith('eia:')).check.terms, ['온산제련소', '환경영향평가']);
});

test('bill hints: formal law names are searched by the short name headlines use', () => {
  // 10-31 운영: '산업기술의 유출방지 및 보호에 관한 법률 개정안 백혜련'으로 찾아 미보도 후보
  const h = billHint({ law: '산업기술의 유출방지 및 보호에 관한 법률', leads: ['백혜련'] });
  assert.deepEqual([h.who, h.terms, h.must, h.names], ['산업기술보호법', ['개정안', '백혜련'], ['백혜련'], ['산업기술보호법', '산업기술의 유출방지 및 보호에 관한 법률']]);
  // 가운뎃점 표기가 달라도(· / ㆍ) 같은 법, 주어가 '·'에서 잘리지 않는다
  assert.equal(billHint({ law: '신에너지 및 재생에너지 개발·이용·보급 촉진법', leads: ['홍길동'] }).who, '신재생에너지법');
  assert.equal(billHint({ law: '노동조합 및 노동관계조정법', leads: ['이종배'] }).who, '노조법');
  const plain = billHint({ law: '전기사업법', leads: ['박덕흠'] });
  assert.deepEqual([plain.who, plain.names], ['전기사업법', undefined]);
});

test('press-check hints: place words narrow the search but are marked, workforce words follow the direction, local notices use the project word', () => {
  const h = hint('고려아연', ['울주', localWord("건설공사 안전점검 수행기관 지정 공고[온산 고려아연(주), Ga' 2차 ..."), '공장'], ['울주']);
  assert.deepEqual([h.terms, h.places, Object.keys(h.alts)], [['울주', '신설', '공장'], ['울주'], ['신설', '공장']]);
  // 산소공장(ASU): 기사는 '산소공장 증설'(10-20 전자신문) — '#2ASU'처럼 숫자가 붙어도, 'CASUAL' 같은 낱말 속은 아님
  assert.deepEqual(["…[온산 고려아연(주), #2ASU O2 COMPRESSOR ROOM 토건공사]", '산소플랜트 증설', 'CASUAL 공장'].map(localWord), ['산소공장', '산소공장', '신설']);
  assert.equal(hint('LS전선', ['입찰'], ['바레인']).places, undefined);  // a place not among the terms is dropped
  assert.equal(hint('LS전선', ['바레인', '입찰']).places, undefined);
  assert.deepEqual(['온산제련소 환경영향평가 초안 공람', '○○ 일반산업단지 계획 변경', '공장 이전 부지', '폐기물 매립시설'].map(localWord),
    ['환경영향평가', '산업단지', '이전', '매립']);
  const wf = (kind, text) => workforceHint({ company: '포스코', kind, text }).terms;
  // 사업장 시·군을 넣고 그 지명이 없는 기사는 세지 않는다(10-31 포스코 포항 +866명 ↔ 美 제철소 채용 기사)
  const pw = workforceHint({ company: '포스코', kind: '인력 증가', text: '주식회사포스코(경상북도 포항시 남구) 국민연금 가입자 15,852→16,718명(+866명, +5.5%)' });
  assert.deepEqual([pw.terms, pw.places, pw.must], [['포항', '채용'], ['포항'], ['포항']]);
  assert.deepEqual(workforceHint({ company: '기아', kind: '인력 감소', text: '기아(서울특별시 서초구) 가입자 2,100→2,060명(-40명)' }).must, undefined);  // 시·군 없으면 그대로
  assert.deepEqual(wf('인력 변동', '포스코 가입자 2,100→2,060명(-40명)'), ['감원']);
  assert.deepEqual(wf('인력 감소', '형식 모름'), ['감원']);
  assert.ok(!workforceHint({ company: '기아', kind: '인력 증가', text: '가입자 1→2명' }).alts.채용.includes('고용'));  // 흔한 말 빼기
  assert.deepEqual(['㈜포스코 광양제철소', '현대자동차㈜ 울산공장', '㈜영풍석포제련소', '현대제철㈜포항2공장', '현대제철㈜'].map(siteCity), ['광양', '울산', '석포', '포항', undefined]);
  const sh = stackHint({ company: '포스코', site: '㈜포스코 광양제철소', kind: '배출구 멈춤 신호' });
  assert.deepEqual([sh.terms, sh.places, sh.must], [['광양', '가동 중단', '정비'], ['광양'], ['광양']]);
  assert.deepEqual(stackHint({ company: '현대제철', site: '현대제철㈜', kind: '배출구 멈춤 신호' }).must, undefined);
  const kh = kepcoHint('765kV 전력용변압기 1Bank(3대) - 신안성S/S');  // 10-31 운영: 예전엔 "한국전력공사 한전"으로 찾았다
  assert.deepEqual([kh.who, kh.terms, kh.places], ['한전', ['765kV', '변압기', '발주'], ['765kV']]);
  assert.deepEqual(kepcoHint('배전용 자재 구매').terms, ['발주']);
  assert.deepEqual(wf('새 공사 현장', '…'), ['공사', '착공']);
  assert.deepEqual(wf('사업장 탈퇴', '…'), ['공장', '폐쇄']);
});

test('kr local notices: a beat plant notice in a city is A, a city baseline is hidden, kr_official section=local lists it', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const it = (id, extra) => ({ id, city: '울주군', plants: '고려아연·LS MnM·현대차', no: '울산광역시 울주군 공고 제2026-2727호',
    title: "건설공사 안전점검 수행기관 지정 공고[온산 고려아연(주), Ga' 2차 ...", dept: '건축과', date: '2026-10-25', companies: ['고려아연'], company: '고려아연',
    tier: 'A', url: 'http://eminwon.ulju.ulsan.kr/emwp/gov/mogaha/ntis/web/ofr/action/OfrAction.do?method=selectOfrNotAncmt&not_ancmt_mgt_no=68118',
    firstSeen: '2026-10-25T06:30:00+09:00', baseline: false, isNew: true, ...extra });
  const doc = { schema: 'kr_local/v1', generatedAt: '2026-10-25T06:30:00+09:00', status: 'partial', rules: ['제목만 본다.'],
    checks: [{ source: '울주군', status: 'ok', returned: 60 }, { source: '포항시', status: 'failed', error: 'ReadTimeout' }],
    items: [it('local:울주군:68118'),
      it('local:당진시:1', { city: '당진시', title: '현대제철 옛 공고', company: '현대제철', companies: ['현대제철'], baseline: true, isNew: false }),
      it('local:여수시:2', { city: '여수시', title: '여수국가산업단지 계획 변경 승인 고시', company: null, companies: [], tier: 'C' }),
      // 수집기가 일상 행정으로 표시한 저장분(10-30 예산 태양광 양수인가)은 어디에도 안 보인다
      it('local:예산군:47455', { city: '예산군', title: '전기사업(태양광발전) 양수인가 공고', company: null, companies: [], tier: 'C', routine: true })] };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/kr-local', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const r = await call('radar_today', { hours: 72 }, opts);
  assert.match(r.text.split('[A · ')[1].split('[B · ')[0], /울주군 울산광역시 울주군 공고 제2026-2727호 「건설공사 안전점검 수행기관 지정 공고\[온산 고려아연\(주\), Ga' 2차 \.\.\.」 · 건축과 · 등록 2026-10-25 — 제목만 확인/);
  assert.doesNotMatch(r.text, /현대제철 옛 공고/);
  assert.match(r.text, /지자체 고시·공고: 일부 실패 1건\(포항시\)|지자체 고시·공고: 일부/);
  const t = await call('kr_official', { section: 'local' }, opts);
  assert.match(t.text, /\[지자체 고시·공고 · 출입처 공장 시·군 2곳 새올 목록 · 처음 본 날 최근 30일\] 출입처 관련 2건 · 참고\(제철소·산업단지 계획 등\) 1건/);
  assert.match(t.text, /- \[첫 조회 기준선\] 2026-10-25 · 당진시 · 현대제철 · A/);
  assert.match(t.text, /미확인\(0건 아님\): 포항시\(ReadTimeout\)/);
  assert.match(t.text, /이 시·군의 출입처 공장: 고려아연·LS MnM·현대차/);
  assert.doesNotMatch((await call('kr_official', { section: 'local', company: '예산' }, opts)).text, /양수인가/);
  assert.doesNotMatch((await call('radar_today', { hours: 72, include_minor: true }, opts)).text, /양수인가/);
  // 상세 페이지를 읽은 공고: 전체 제목·본문 앞부분·첨부 파일 이름, 대조 낱말은 전체 제목에서(10-31 울주 68156)
  doc.items.push(it('local:울주군:68156', { no: '울산광역시 울주군 공고 제2026-2760호', title: '건설공사 안전점검 수행기관 지정 공고[온산 고려아연(주), #2ASU O...',
    detail: { title: '건설공사 안전점검 수행기관 지정 공고[온산 고려아연(주), #2ASU O2 COMPRESSOR ROOM 토건공사]',
      body: '우리 군 온산읍 원산리 892번지 일원 상 공장 용도의 건축공사에 대하여 건설공사 안전점검 수행기관을 지정하고자 다음과 같이 모집 공고합니다.',
      files: ['예정공정표.pdf'] } }),
  it('local:울주군:68157', { title: '고려아연(주) 온산제련소 ...', tier: 'B', detailError: 'ReadTimeout' }));
  await worker.fetch(new Request(ORIGIN + '/ingest/kr-local', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {});
  const r2 = await call('radar_today', { hours: 72 }, opts);
  assert.match(r2.text, /「건설공사 안전점검 수행기관 지정 공고\[온산 고려아연\(주\), #2ASU O2 COMPRESSOR ROOM 토건공사\]」 · 건축과 · 등록 2026-10-25 · 본문: 우리 군 온산읍 원산리 892번지 일원 상 공장 용도의 건축공사/);
  assert.match(r2.text, /토건공사\]」[^\n]*— 제목·본문 앞부분 확인/);
  const t2 = await call('kr_official', { section: 'local' }, opts);
  assert.match(t2.text, /본문 앞부분\(상세 페이지\): 우리 군 온산읍 원산리 892번지/);
  assert.match(t2.text, /첨부 파일\(열지 않음\): 예정공정표\.pdf/);
  assert.match(t2.text, /상세 페이지: 못 읽음\(ReadTimeout\) — 제목만 확인/);
  const items = await (await radarItems(new Request(ORIGIN + '/ingest/radar-items?hours=168', { headers: { Authorization: `Bearer ${TOKEN}` } }), env, { now: new Date('2026-10-26T01:00:00Z') })).json();
  assert.deepEqual(items.items.find((x) => x.id === 'local:울주군:68156').check.terms, ['울주', '산소공장', '공장']);
  assert.deepEqual(dueAt(new Date('2026-10-26T21:30:00Z')), ['page-watch.yml', 'kr-local.yml']);  // Tue 06:30 KST
  assert.deepEqual(dueAt(new Date('2026-10-27T07:20:00Z')), ['kr-local.yml']);                    // Tue 16:20 KST
});

test('local_notice_submit: the reporter computer posts browser-read 새올 rows for fixed cities, kr-local runs once an hour at most', async () => {
  const seen = [];
  const fetch = async (url, init) => { seen.push({ url, init }); return new Response(null, { status: 204 }); };
  const opts = { ...PRIVATE({ GITHUB_DISPATCH_TOKEN: 'ghp_test' }), fetch };
  assert.ok(!(await rpc('tools/list')).body.result.tools.some((x) => x.name === 'local_notice_submit'));  // private only
  const r = await call('local_notice_submit', { cities: [
    { city: '인천 부평구', rows: [
      { mgt: '91001', cells: ['120', '부평구 공고 제2026-1500호', '  한국지엠 부평공장\n도장공장 증축 건축허가 사항 공고 ', '건축과', '2026-10-29', '7', ''] },
      { mgt: "1');alert(1", cells: ['x'] },
      { mgt: '91001', cells: ['중복'] }] },
    { city: '구미시', error: 'TypeError: Failed to fetch' },
    { city: '서울 강남구', rows: [{ mgt: '1', cells: ['x'] }] }] }, opts);
  assert.equal(r.isError, false);
  assert.match(r.text, /- 인천 부평구: 1줄 · 버린 줄 2/);
  assert.match(r.text, /- 구미시: 미확인\(TypeError: Failed to fetch\)/);
  assert.match(r.text, /받지 않은 이름\(허용 목록 밖\): 서울 강남구/);
  assert.match(r.text, /지자체 고시·공고 감시\(kr-local\) 실행 요청함/);
  assert.deepEqual(seen.map((x) => x.url), ['https://api.github.com/repos/shhong9173-art/seoul-reporting-radar/actions/workflows/kr-local.yml/dispatches']);
  // the watch reads it back through the bearer ingest path
  const got = await (await worker.fetch(new Request(ORIGIN + '/ingest/kr-local-browser', { headers: { Authorization: `Bearer ${TOKEN}` } }), opts.env, {})).json();
  assert.equal(got.schema, 'kr_local_browser/v1');
  assert.deepEqual(got.cities.find((c) => c.city === '인천 부평구').rows,
    [{ mgt: '91001', cells: ['120', '부평구 공고 제2026-1500호', '한국지엠 부평공장 도장공장 증축 건축허가 사항 공고', '건축과', '2026-10-29', '7'] }]);
  // a second submit in the same hour keeps the other cities and does not ask GitHub again
  const again = await call('local_notice_submit', { cities: [{ city: '구미시', rows: [{ mgt: '7', cells: ['구미시 공고', '도로 공고', '2026-10-30'] }] }] }, opts);
  assert.match(again.text, /이미 함 — 다시 요청하지 않음/);
  assert.equal(seen.length, 1);
  const got2 = await (await worker.fetch(new Request(ORIGIN + '/ingest/kr-local-browser', { headers: { Authorization: `Bearer ${TOKEN}` } }), opts.env, {})).json();
  assert.deepEqual(got2.cities.map((c) => [c.city, c.rows.length]).sort(), [['구미시', 1], ['인천 부평구', 1]]);
  assert.ok((await call('local_notice_submit', { cities: [{ city: '서울 강남구' }] }, opts)).isError);
  // 무역구제 목록(호주 TRN): 한국 줄 칸 글자 + 같은 사이트 링크만, 받은 날 처음 한 번 무역구제 감시를 돌린다(하루 한 번까지)
  const pg = await call('local_notice_submit', { pages: [{ id: 'au-trn', rows: [
    { cells: ['2026/141 [PDF 270.2 KB]', '706', 'Zinc coated (galvanised) steel', 'Extension of time for SEF and Final Report', 'Korea, Vietnam', '02/10/2026'],
      links: ['/sites/default/files/atrc/public-record/2026-10/706-22.pdf', 'https://evil.example/x', 'https://www.industry.gov.au/australian-trade-remedies-commission/current-cases-and-electronic-public-record-epr/706'] }] },
  { id: 'xx-page', rows: [] }] }, opts);
  assert.equal(pg.isError, false);
  assert.match(pg.text, /- 무역구제 au-trn: 한국 줄 1/);
  assert.match(pg.text, /받지 않은 목록\(허용 밖\): xx-page/);
  assert.match(pg.text, /무역구제 감시\(trade-remedy\) 실행 요청함/);
  assert.deepEqual(seen.map((x) => x.url.split('/').slice(-2)[0]), ['kr-local.yml', 'trade-remedy.yml']);
  const tb = await (await worker.fetch(new Request(ORIGIN + '/ingest/trade-remedy-browser', { headers: { Authorization: `Bearer ${TOKEN}` } }), opts.env, {})).json();
  assert.deepEqual(tb.pages[0].rows[0].links, ['/sites/default/files/atrc/public-record/2026-10/706-22.pdf',
    '/australian-trade-remedies-commission/current-cases-and-electronic-public-record-epr/706']);  // 다른 사이트 링크는 버림
  const pg2 = await call('local_notice_submit', { pages: [{ id: 'au-trn', rows: [{ cells: ['2026/142', 'Korea', 'x'] }] }] }, opts);
  assert.match(pg2.text, /이미 함\(하루 한 번\)/);  // 같은 날 오후 수집은 요청하지 않음
  const pg3 = await call('local_notice_submit', { pages: [{ id: 'au-trn', error: 'HTTP 503' }] }, opts);
  assert.match(pg3.text, /- 무역구제 au-trn: 미확인\(HTTP 503\)[\s\S]*실행 요청 안 함\(한국 줄을 받은 목록 없음\)/);
  assert.equal(seen.length, 2);
  assert.ok((await call('local_notice_submit', {}, opts)).isError);
  // kr_official names the cities read on the reporter's computer
  const doc = { schema: 'kr_local/v1', generatedAt: '2026-10-26T08:50:00+09:00', status: 'complete', items: [],
    checks: [{ source: '인천 부평구', status: 'ok', returned: 30, via: '기자 컴퓨터 브라우저 수집 2026-10-25T23:45' }, { source: '당진시', status: 'ok', returned: 60 }] };
  await worker.fetch(new Request(ORIGIN + '/ingest/kr-local', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), opts.env, {});
  assert.match((await call('kr_official', { section: 'local' }, opts)).text, /기자 컴퓨터 브라우저로 읽은 곳\(해외 IP 차단\): 인천 부평구\(2026-10-25 23:45\)/);
});
