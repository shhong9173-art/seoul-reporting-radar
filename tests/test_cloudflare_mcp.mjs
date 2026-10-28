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
import { hint, radarItems } from '../cloudflare/digest.mjs';

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
    events: [{ pageId: 'hyundai-us-ioniq-6-n', company: '현대차', label: '현대차 미국 아이오닉6 N', url: 'https://www.hyundaiusa.com/us/en/vehicles/ioniq-6-n',
      detectedAt: '2026-10-26T06:30:00+09:00', baselineSource: '웹 아카이브 사본', baselineDate: '2026-09-10',
      added: { timing: ['Coming Spring 2027'], limited: ['extremely limited availability'] }, removed: { timing: ['Coming 2026'] } }] };
  const post = await worker.fetch(new Request(ORIGIN + '/ingest/page-watch', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {});
  assert.equal(post.status, 200);
  const r = await call('page_changes', { show_current: true }, { path: `/mcp/${TOKEN}`, env });
  assert.match(r.text, /최근 14일 1건 · 페이지 1\/2 열림/);
  assert.match(r.text, /미확인\(변화 없음 아님\): 기아 미국 EV4\(HTTP 403\)/);
  assert.match(r.text, /비교 기준: 웹 아카이브 사본 2026-09-10 → 2026-10-2/);
  assert.match(r.text, /− 출시 시점: Coming 2026/);
  assert.match(r.text, /\+ 출시 시점: Coming Spring 2027/);
  assert.match(r.text, /현대차 미국 아이오닉6 N: Coming Spring 2027 · extremely limited availability/);
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
  assert.match(r.text, /포스코 · 등록 내용 변경\n   잡힌 사실: 고용 9,000→8,000명/);
  assert.match(r.text, /\[최근 120일 등록 공장 · 등록일 기준\] 1곳 \(출입처 공장 전체 2곳\)/);
  assert.match(r.text, /\(기준선 2026-10-26 이후 감지된 새 공장/);
  assert.match(r.text, /2026-09-15 · 현대차 · 현대자동차\(주\)울산EV공장/);
  assert.match(r.text, /\[신규\] 2026-10-24 · 국토교통부 · 자동차/);
  assert.doesNotMatch(r.text, /포항제철소 · 경상북도/);
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
        snippet: 'entered into a long-term supply agreement with Hyundai Steel Company', url: 'https://sec/acme' }] });
  await post('scoop-screen', { schema: 'scoop_screen/v1', generatedAt: '2026-10-26T07:10:00+09:00', counts: {},
    candidates: [{ id: 'p1', verdict: '미보도 후보', company: '기아', title: '고정자 냉각 장치', kind: '특허' },
      { id: 'p2', verdict: '미보도 후보', company: '현대제철', title: '판재 냉각 제어', kind: '특허' }] });
  const r = await call('radar_today', {}, opts);
  const a = r.text.split('[A · ')[1].split('[B · ')[0];
  const b = r.text.split('[B · ')[1].split('[C · ')[0];
  assert.match(a, /ACME METALS: 8-K/);
  assert.match(b, /HARTFORD INSURANCE GROUP: 8-K EX-99\.2 — 발췌에 계약·공급·합작 낱말 없음/);
  assert.match(a, /id p1/);
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
  assert.deepEqual(dueAt(new Date('2026-10-26T22:20:00Z')), []);                          // no slot
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
  assert.match(later.text, /예약 요청\(Cloudflare\): 오늘 앞선 칸은 토큰 없이 지나감 · 지금은 토큰 보임 — 다음 칸\(10-26 15:10 scoop-screen\.yml\)부터 요청/);
  assert.equal(nextSlot(new Date('2026-10-30T10:00:00Z')), '11-02 06:30 page-watch.yml');  // Fri 19:00 KST → Mon 06:30
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
  assert.match(r.text, /- 단독 후보 심사 8 — 씀 2 · 킬 4 · 보류 1 · 봤음 1 \| A 3\(씀 1 · 보류 1 · 봤음 1\) · B 5\(씀 1 · 킬 4\)/);
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
  assert.match(r.text, /기자 전용 감시 11개/);
  assert.deepEqual(dueAt(new Date('2026-10-26T23:30:00Z')), ['kr-signals.yml']);  // Tue 08:30 KST
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

test('partner filings: EDGAR holdings tables and repeated text fold to C, financial-statement notes never reach A', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const ed = (id, filer, snippet, extra = {}) => ({ id, source: 'EDGAR', filer, form: '6-K', date: '2026-10-25', firstSeen: '2026-10-26T07:00:00+09:00', isNew: true,
    beat: ['현대차'], title: '6-K EX-99.1', url: `https://www.sec.gov/Archives/edgar/data/1/${id}.htm`, snippet, ...extra });
  const doc = { schema: 'partner_filings/v1', generatedAt: '2026-10-26T07:00:00+09:00', windowDays: 30, checks: [{ source: 'EDGAR', target: 'Hyundai Motor Company', status: 'ok' }],
    items: [ed('h1', 'HARTFORD INSURANCE GROUP', 'Top Ten Exposures by Issuer … Hyundai Motor Company 182 178 0.3 %', { routine: '투자 보유 목록(채권·주식 보유 표) — 출입처와의 거래 아님' }),
      ed('k1', 'KT CORP', '(12) The Company has an agreement related to a stock sale contract with HYUNDAI MOTOR COMPANY.', { finNote: '재무제표 주석 — 이미 있던 약정을 다시 적은 것일 수 있음(이전 분기 보고서와 대조)' }),
      ed('c1', 'CELL MAKER INC', 'entered into a binding supply agreement with Hyundai Motor Company for battery cells.')],
    confirmedScoops: 0 };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/partner-filings', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const r = await call('radar_today', { include_minor: true, limit: 60 }, opts);
  const sec = (t) => r.text.split(`[${t} · `)[1].split(/\n\[[ABC] · /)[0];
  assert.match(sec('A'), /CELL MAKER INC/);
  assert.match(sec('B'), /KT CORP: 6-K EX-99\.1 — 재무제표 주석/);
  assert.match(sec('C'), /HARTFORD INSURANCE GROUP: 6-K EX-99\.1 — 투자 보유 목록/);
  assert.doesNotMatch(sec('A'), /KT CORP|HARTFORD/);
  const t = await call('partner_filings', {}, opts);
  assert.doesNotMatch(t.text, /HARTFORD/);
  assert.match(t.text, /분류: 재무제표 주석/);
  assert.match(t.text, /일상 공시 1건 숨김 — ASX 주총·임원 지분, EDGAR 투자 보유 표·반복 문구/);
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
      { id: 'bill:PRC_K1:발의', billId: 'PRC_K1', kind: '발의', detectedAt: '2026-10-26T08:40:00+09:00', date: '2026-10-25', core: null, law: '산업안전보건법', lead: '홍길동' }],
    rules: ['국회의원 발의법률안(열린국회정보)이다.'], confirmedScoops: 0 };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/assembly-bills', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const t = await call('assembly_bills', {}, opts);
  assert.match(t.text, /\[새 발의 · 최근 14일 · 출입처 직결 법\(core\)\] 1묶음\n- 2026-10-25 · \[전력·에너지\] 법안 발의: 전기사업법 일부개정법률안 등 2건 — 김갑동·이을동 대표발의/);
  assert.match(t.text, /\[단계 변화 · 최근 14일\] 1건\n- 2026-10-26 · \[철강·비철\] 법안 소관위 상정: 철강산업 경쟁력 강화 및 탄소중립 전환을 위한 특별법 일부개정법률안 \(직전 소관위 회부\) — 박병동 대표발의/);
  assert.doesNotMatch(t.text, /산업안전보건법 일부개정/);
  assert.match((await call('assembly_bills', { include_related: true }, opts)).text, /산업안전보건법 일부개정법률안/);
  const r = await call('radar_today', { include_minor: true }, opts);
  const bsec = r.text.split('[B · ')[1].split('[C · ')[0];
  assert.match(bsec, /국회 법안 · 전력·에너지\n   법안 발의: 전기사업법 일부개정법률안 등 2건/);
  assert.match(bsec, /법안 소관위 상정: 철강산업/);
  assert.match(r.text.split('[C · ')[1], /법안 발의: 산업안전보건법 일부개정법률안/);
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
  assert.match(r.text, /기자 전용 감시 11개/);
  assert.match(r.text, /- 상표 출원: 대기 1곳\(제공기관 응답 22 뒤 72시간 대기\) — 해당 부분 0건은 미확인/);
  assert.doesNotMatch(r.text, /상표 출원: [^\n]*시간 전 결과/);
  const b = r.text.split('[B · ')[1].split('[C · ')[0];
  assert.match(b, /상표 출원 · 현대자동차\n   상표 출원 「AERO DRIVE」 12류\(차량·부품\), 35류\(광고·사업관리\) — 감시 시작 이후 처음 보는 이름 \(출원 2026-10-20, 출원번호 [0-9]+ 외 1\)/);
  assert.doesNotMatch(r.text, /OLDNEW/);  // first seen two weeks ago: off the digest
  const minor = await call('radar_today', { include_minor: true }, opts);
  assert.match(minor.text, /상표 출원 「NUTRIMACY」[^\n]* — 같은 이름 상품류 추가/);
  const list = await rpc('tools/list', {}, { path: `/mcp/${TOKEN}`, env });
  assert.ok(list.body.result.tools.some((x) => x.name === 'trademarks'));
  assert.match(list.body.result.tools.find((x) => x.name === 'radar_today').description, /감시 11개\([^)]*상표 출원, 국회 법안\)/);
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
  await post('kr-official', { schema: 'kr_official/v1', generatedAt: '2026-10-26T08:10:00+09:00', checks: [], factories: [], gazette: [],
    events: [
      { id: 'fac:1:x', kind: '등록 내용 변경', company: 'KG스틸', factoryId: 'fac:1', text: '고용 856→690명', detectedAt: '2026-10-25T11:09:00+09:00' },
      { id: 'fac:2:gone', kind: '목록에서 빠짐', company: '현대위아', factoryId: 'fac:2', text: '현대위아(주)창원2공장 · 경상남도 창원시 성산구 정동로 154 — 이번 조회 목록에 없음', detectedAt: '2026-10-25T11:09:00+09:00' },
      { id: 'fac:3:x', kind: '등록 내용 변경', company: '효성중공업(관련)', factoryId: 'fac:3', text: "업종 'a 외 13 종'→'a 외 14 종'", detectedAt: '2026-10-25T11:09:00+09:00' }] });
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
  assert.deepEqual(by['fac:1:x'].check.terms, ['인력', '감축']);
  assert.deepEqual(by['fac:2:gone'].check.terms, ['창원', '공장', '폐쇄']);
  assert.ok(!by['cl:5'], 'judged 봤음 is not checked again');
  assert.ok(!by['cl:9'], 'C tier is not checked');
  assert.ok(!by['fac:3:x'], 'no hint when the change has no search words');
  assert.equal(hint('효성중공업(관련)·일진전기', ['공장', null]).who, '효성중공업');
  assert.equal(hint('', ['x']), undefined);

  await post('radar-check', { schema: 'radar_check/v1', generatedAt: '2026-10-26T08:50:00+09:00', items: [
    { id: 'cl:4', verdict: '관련 보도 있음', since: '2026-10-22', queries: ['세아제강 국제무역법원', '세아제강 국제무역법원 소송'],
      evidence: [{ date: '2026-10-25', channel: 'naver', title: '세아제강, 美 국제무역법원에 반덤핑 소송', url: 'https://n/1', why: '낱말' }],
      channels: { naver: { status: 'ok', returned: 3 } }, firstVerdict: '미보도 후보', firstCheckedAt: '2026-10-25T18:50:00+09:00' },
    { id: 'cl:7', verdict: '미보도 후보', since: '2026-10-20', queries: ['LS일렉트릭 항소', 'LS일렉트릭 항소 특허'],
      evidence: [{ date: '2026-10-24', channel: 'naver', title: '전력기기 업계 美 소송 잇따라', url: 'https://n/2', why: '본문에만 회사·낱말(항소, 특허) — 제목 불일치, 같은 사건 가능성 낮음' }],
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
  assert.match(a, /보도 대조\(자동 10-26 08:50\): 미확인 — 채널 naver failed\(ConnectTimeout\)\(0건 아님\)/);
  assert.match(r.text, /보도 대조\(자동\)는 네이버 뉴스 API·빙·구글에서 항목 날짜 3일 전부터 찾은 결과다/);
  assert.doesNotMatch(r.text, /보도 대조\(자동\): 결과 없음/);
  const none = await call('radar_today', {}, PRIVATE());
  assert.match(none.text, /보도 대조\(자동\): 결과 없음 — 미확인\(평일 08:50·18:50 실행 확인\)/);
});

test('press check is dispatched after the morning watches and after the evening page watch', () => {
  assert.deepEqual(dueAt(new Date('2026-10-27T23:50:00Z')), ['radar-press-check.yml']);  // Wed 08:50 KST
  assert.deepEqual(dueAt(new Date('2026-10-28T09:50:00Z')), ['radar-press-check.yml']);  // Wed 18:50 KST
});
