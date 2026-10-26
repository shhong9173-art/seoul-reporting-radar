import test from 'node:test';
import assert from 'node:assert/strict';
import { deflateRawSync } from 'node:zlib';
import { DatabaseSync } from 'node:sqlite';
import worker from '../cloudflare/worker.mjs';
import { handleMcp, TOOLS } from '../cloudflare/mcp.mjs';
import { RadarStore } from '../cloudflare/store.mjs';
import { checkCandidate } from '../cloudflare/scoring.mjs';
import { readZip } from '../cloudflare/zip.mjs';
import { allowedUrl } from '../cloudflare/live_tools.mjs';

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

test('candidate_check holds incomplete packages and recommends complete ones', async () => {
  const thin = checkCandidate({ title: '현대제철, 전기로 2배 확대', companies: ['현대제철'] });
  assert.equal(thin.status, '조사대기');
  assert.ok(thin.hold.some((h) => h.includes('원문 URL')));
  assert.ok(thin.hold.some((h) => h.includes('제목 숫자 근거 없음')));
  const full = {
    title: 'LS일렉트릭, 부산 변압기 생산능력 2배로', companies: ['엘에스일렉트릭'], source_url: 'https://dart.fss.or.kr/x',
    source_date: '2026-08-14', content_hash: 'ab', facts: ['부산 생산능력 2,286억원→4,840억원'], numbers: ['2,286억원', '4,840억원'],
    derived_numbers: [{ value: '2배', method: '증감률' }], coverage: { google: 'ok', naver: 'ok', dandok: 'ok', verdict: '단독 유력' },
    company_disclosed: false, comparison: 'HD현대일렉트릭 같은 기간 생산능력', impact: '북미 수주 대응', questions: ['증설 완료 시점?', '라인 수?'],
    size_scores: { novelty: 2, numbers: 2, scale: 1, beat: 2, timing: 1, expansion: 1, exclusivity: 2 },
  };
  const ok = checkCandidate(full);
  assert.equal(ok.status, '추천', JSON.stringify(ok.hold));
  assert.equal(ok.size.grade, '톱');
  assert.equal(checkCandidate({ ...full, coverage: { ...full.coverage, verdict: '이미 남' } }).status, '탈락');
  const viaBing = checkCandidate({ ...full, coverage: { ...full.coverage, google: 'failed', bing: 'ok' } });
  assert.equal(viaBing.status, '추천', JSON.stringify(viaBing.hold));
  const noWeb = checkCandidate({ ...full, coverage: { ...full.coverage, google: 'failed', bing: 'failed' } });
  assert.ok(noWeb.hold.some((h) => h.includes('웹 색인')));
  const failedChannel = checkCandidate({ ...full, coverage: { ...full.coverage, naver: 'failed' } });
  assert.equal(failedChannel.status, '조사대기');
  assert.ok(checkCandidate({ ...full, derived_numbers: [{ value: '2배', method: '추정' }] }).hold.some((h) => h.includes('허용되지 않은')));
  const viaTool = await call('candidate_check', { candidate: full });
  assert.match(viaTool.text, /판정: 추천/);
});

test('packages, daily limit and feedback live in the private store', async () => {
  const opts = PRIVATE();
  assert.match((await call('package_save', { name: 'LS 부산 CAPA', title: 'LS일렉 부산 증설', state: '미발제·확인 필요', body: '근거…' }, opts)).text, /새로 저장/);
  assert.match((await call('package_save', { name: 'LS 부산 CAPA', title: 'LS일렉 부산 증설', state: '발제함', body: '근거2' }, opts)).text, /갱신/);
  const list = await call('scoop_packages', {}, opts);
  assert.match(list.text, /\[발제함\] ls-부산-capa/);
  assert.match((await call('scoop_packages', { name: 'ls-부산-capa' }, opts)).text, /근거2/);
  assert.ok((await call('package_save', { name: 'x', title: 't', state: '모름', body: 'b' }, opts)).isError);
  const base = { companies: ['현대제철'], source_url: 'https://dart.fss.or.kr/x', source_date: '2026-10-24', content_hash: 'h',
    facts: ['f'], numbers: ['1건'], coverage: { google: 'ok', naver: 'ok', dandok: 'ok', verdict: '단독 확실' }, company_disclosed: false,
    comparison: 'c', impact: 'i', questions: ['q1', 'q2'] };
  const many = Array.from({ length: 7 }, (_, i) => ({ ...base, title: `후보 ${i}` }));
  const sub = await call('candidate_submit', { candidates: many }, opts);
  assert.equal((sub.text.match(/\[추천\]/g) ?? []).length, 5);
  assert.equal((sub.text.match(/하루 한도 초과/g) ?? []).length, 2);
  assert.match((await call('candidate_submit', { candidates: [many[0]] }, opts)).text, /중복/);
  await call('candidate_feedback', { item_id: '#1', verdict: '킬', reason: '이미 남' }, opts);
  await call('candidate_feedback', { item_id: '#2', verdict: '씀', reason: '지면 박스' }, opts);
  const review = await call('candidate_weekly_review', {}, opts);
  assert.match(review.text, /씀 1 \/ 킬 1/);
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
        queries: ['현대위아 영업양도'], channels: {}, evidence: [{ date: '2026-10-20', channel: 'naver', title: '현대위아 영업양도', why: '낱말(영업양도)', url: 'https://n/1' }] },
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
  assert.match(r.text, /ASX 일상 공시 1건 숨김/);
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
        priority: 3, role: '피고·기타 당사자', matchedParties: ['Hyundai Motor America Inc'], cause: '15:2301 Magnuson-Moss Warranty Act', url: 'https://x/1', isNew: false }],
    itc: [{ id: 'fr:2026-1', date: '2026-10-15', stage: '조사 개시', title: 'Certain Automotive Headlamps; Notice of Institution of Investigation',
      url: 'https://www.federalregister.gov/d/2026-1', named: [{ company: '현대모비스', mentions: 1, lines: ['Hyundai Mobis Co., Ltd., Seoul, Republic of Korea'] }], isNew: true }] };
  const post = await worker.fetch(new Request(ORIGIN + '/ingest/us-litigation', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {});
  assert.equal(post.status, 200);
  const opts = { path: `/mcp/${TOKEN}`, env };
  const r = await call('us_litigation', {}, opts);
  assert.match(r.text, /질의 1\/2 정상 · 미확인\(0건 아님\): CourtListener "Taihan"\(HTTP 429 호출 한도\)/);
  assert.match(r.text, /\[신규\] 2026-09-29 · 국제무역법원\(무역구제 소송\) · 포스코\(원고\)/);
  assert.match(r.text, /잡힌 사실: CIT 1:26-00123 「POSCO v\. United States」 접수/);
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
