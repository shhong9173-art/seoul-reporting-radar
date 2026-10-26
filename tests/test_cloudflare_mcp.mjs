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
  assert.match(r.text, /■ 미보도 후보 \(1\)\n1\. \[자동차\] 현대자동차 · HMTR/);
  assert.match(r.text, /네이버\(API HUB\) ok 12건 · 빙 ok 3건 · 구글 failed\(HTTP 503\)/);
  assert.match(r.text, /↳ 2026-10-20 \[naver\] 현대위아 영업양도 — 낱말\(영업양도\)/);
  await call('candidate_feedback', { item_id: 'clue:a2', verdict: '킬', reason: '이미 남' }, opts);
  const after = await call('scoop_screen', {}, opts);
  assert.doesNotMatch(after.text, /현대위아 · 영업양도결정/);
  assert.match(after.text, /킬'로 판정한 1건 숨김/);
  assert.match((await call('scoop_screen', { include_killed: true }, opts)).text, /기자 판정: 킬 — 이미 남/);
  const empty = await call('scoop_screen', {}, PRIVATE());
  assert.ok(empty.isError);
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
