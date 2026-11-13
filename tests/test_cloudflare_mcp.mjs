import test from 'node:test';
import assert from 'node:assert/strict';
import { deflateRawSync } from 'node:zlib';
import { createHash } from 'node:crypto';
import { DatabaseSync } from 'node:sqlite';
import worker from '../cloudflare/worker.mjs';
import { handleMcp, TOOLS } from '../cloudflare/mcp.mjs';
import { LINK_LINE, RadarStore, packageLinks } from '../cloudflare/store.mjs';
import { annotateHandled, codesOf, companiesIn, companiesInSlow, ledgerEntries, matchHandled } from '../cloudflare/handled.mjs';
import { deskType } from '../cloudflare/desk.mjs';
import { browserUpload, lastBrowserSlot } from '../cloudflare/local_browser.mjs';
import { checkCandidate } from '../cloudflare/scoring.mjs';
import { readZip } from '../cloudflare/zip.mjs';
import { publicationDate, verifyEvidence } from '../cloudflare/evidence.mjs';
import { allowedUrl, relayKey } from '../cloudflare/live_tools.mjs';
import { ageNote, handleIngest, lastReturnedWatch, returnedWatch, weekdayHours } from '../cloudflare/screen.mjs';
import { dueAt, newsDue, nextSlot, runSchedule } from '../cloudflare/dispatch.mjs';
import { failStreak, mergeRuns, pollDue } from '../cloudflare/gh_runs.mjs';
import { memoGloss, productKo, tradePoint } from '../cloudflare/overseas.mjs';
import { boardKey, factParts, groupSame, splitTop } from '../cloudflare/board.mjs';
import { cleanOutput, cleanSummary, LLM_MODELS, MT_MODEL } from '../cloudflare/translate.mjs';
import { background, billHint, clipAt, convergence, convergenceRows, countForms, hint, insolvencyWord, ktcHint, ktcNewDumping, maintenanceMemo, stackSiteKey, usRecallHint, usRecallModels, kepcoHint, localWord, plantTokens, radarItems, siteCity, splitByPlant, stackAlert, stackHint, workforceHint, zeroOnlyLongStop } from '../cloudflare/digest.mjs';

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
        employees: { count: 9500, changePct: 5.6, asOf: '2026.09.30', avgSalary: 51234567, salaryPct: 4.2 },
        capex: { current: 767945535814, prior: 904537052601, changePct: -15.1 }, tags: ['[원가율 +3.5%p]', '[직원 +5.6%]'] },
      { company: '고려아연', team: '철강·비철', status: 'not_filed' },
      { company: '영풍', team: '철강·비철', status: 'failed', error: 'HTTP 503' }],
    peers: { groups: [{ group: '석유화학', members: ['LG화학', '롯데케미칼', '금호석유화학', '한화솔루션'], filed: ['LG화학', '롯데케미칼', '금호석유화학', '한화솔루션'], metrics: {} },
      { group: '철강', members: ['현대제철', 'KG스틸', '세아제강', '동국제강', '동국씨엠'], filed: ['현대제철'], metrics: {} }],
    leads: [
      { id: 'p1', group: '석유화학', metric: 'opMarginPp', company: '금호석유화학', value: 2.1, why: '혼자 반대 방향', filedOn: '2026-11-13', url: 'https://dart.fss.or.kr/k',
        text: '석유화학 4곳 2026년 3분기 누적 영업이익률 변화: 금호석유화학 +2.1%p — 나머지 3곳 -3.1%p~-1.0%p(나머지 중앙값 -2.0%p) · 혼자 반대 방향',
        question: '왜 석유화학에서 금호석유화학만 누적 영업이익률 변화이(가) 다른 방향 — 회사 IR·공시 원문(사업의 내용·주석)으로 먼저 확인할 것', firstSeen: '2026-10-25T18:40:00+09:00' },
      { id: 'p2', group: '석유화학', metric: 'capexPct', company: '한화솔루션', value: 95, why: '혼자 반대 방향', filedOn: '2026-11-12',
        text: '석유화학 4곳 2026년 3분기 설비투자(유형자산 취득) 증감률: 한화솔루션 +95.0% — 나머지 3곳 -64.8%~-20.0%(나머지 중앙값 -30.0%) · 혼자 반대 방향',
        question: '질문2', firstSeen: '2026-10-20T18:40:00+09:00' }] } },
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

async function rpc(method, params = {}, { path = '/mcp', env = {}, fetch = fakeFetch(), id = 1, now = NOW } = {}) {
  const request = new Request(ORIGIN + path, { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ jsonrpc: '2.0', id, method, params }) });
  const response = await handleMcp(request, env, { fetch, now });
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
  // 11-04: 설비투자·평균 급여, 업종 비교 데이터 기사 후보
  assert.match(r.text, /1인 평균 급여\(누적\) 5,123만원\(전년 같은 보고서 대비 \+4\.2%\)/);
  assert.match(r.text, /설비투자\(유형자산 취득, 누적\) 7,679억원\(전년 같은 기간 9,045억원 대비 -15\.1%\)/);
  assert.match(r.text, /\[업종 비교 · 데이터 기사 후보 — 2026년 3분기 공시 수치\] 2건 · 제출: 석유화학 4\/4, 철강 1\/5/);
  assert.match(r.text, /- 석유화학 4곳 2026년 3분기 누적 영업이익률 변화: 금호석유화학 \+2\.1%p[^\n]*혼자 반대 방향 · 2026-11-13 제출\n   질문: 왜 석유화학에서 금호석유화학만/);
  assert.ok(r.text.indexOf('[업종 비교') < r.text.indexOf('■ 철강·비철'));
  assert.doesNotMatch((await call('earnings_compare', { team: '자동차' })).text, /금호석유화학 \+2\.1%p/);
});

test('radar_today: 실적 업종 비교 후보는 최근 72시간 안에 처음 본 것만', async () => {
  const r = (await call('radar_today', {}, PRIVATE())).text;
  assert.match(r, /\[업종 비교 · 데이터 기사 후보 — 2026년 3분기 공시 수치\] 1건/);
  assert.match(r, /금호석유화학 \+2\.1%p/);
  assert.doesNotMatch(r, /한화솔루션 \+95\.0%/);   // 10-20에 처음 본 후보는 radar_today에서 뺀다(earnings_compare에는 남음)
  assert.ok(r.indexOf('[업종 비교') < r.indexOf('[A · '));
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
  // 11-12: 구글 503은 Worker에서만 막히는 것 — 고장처럼 'failed'만 찍지 않는다
  assert.match(f.text, /구글 뉴스: 이 서버\(Cloudflare Worker\)에서는 구글이 접속을 막음\(HTTP 503\) — 레이더 고장 아님/);
  assert.match(f.text, /네이버 뉴스: not_configured/);
  assert.match(f.text, /판정: 미확인/);
  // 다른 실패(시간 초과 등)는 그대로 failed
  const slow = fakeFetch({ 'https://news.google.com/': () => { throw Object.assign(new Error('t'), { name: 'TimeoutError' }); } });
  assert.match((await call('news_check', { q: '낱말 두개' }, { ...PRIVATE(), fetch: slow })).text, /구글 뉴스: failed — 시간 초과/);
});

test('news_check: 구글이 막히면 GitHub 경유로 맡기고, 받아 둔 결과를 구글 채널로 쓴다(11-12)', async () => {
  const { env } = PRIVATE({ NAVER_CLIENT_ID: 'i', NAVER_CLIENT_SECRET: 's' });
  const opts = (extra = {}, fetch) => ({ path: `/mcp/${TOKEN}`, env: { ...env, ...extra }, fetch });
  const routes = (gh = new Response(null, { status: 204 })) => fakeFetch({ 'https://news.google.com/': new Response('x', { status: 503 }),
    'https://api.github.com/': gh, 'https://naverapihub.apigw.ntruss.com/': Response.json({ items: [] }) });
  // 토큰이 없으면 맡기지 않고 그 사실만
  const none = await call('news_check', { q: 'LG화학 2-EHA', days: 30 }, opts({}, routes()));
  assert.match(none.text, /레이더 고장 아님 · GitHub 경유 조회 미설정\(Cloudflare 비밀값 GITHUB_DISPATCH_TOKEN\)/);
  // 토큰이 있으면 낱말은 기자 전용 저장소에, GitHub엔 입력값 없이 작업만 부른다
  const f1 = routes();
  const r1 = await call('news_check', { q: 'LG화학 2-EHA', days: 30 }, opts({ GITHUB_DISPATCH_TOKEN: 'ghp_test' }, f1));
  assert.match(r1.text, /GitHub에 구글 조회를 맡김 — 1~2분 뒤 같은 낱말·기간으로 다시 부르면 붙음/);
  const gh = f1.calls.filter((c) => c.url.startsWith('https://api.github.com/'));
  assert.equal(gh.length, 1);
  assert.equal(gh[0].url, 'https://api.github.com/repos/shhong9173-art/seoul-reporting-radar/actions/workflows/google-news-relay.yml/dispatches');
  assert.equal(gh[0].init.body, JSON.stringify({ ref: 'main' }));          // 낱말을 GitHub에 싣지 않는다
  assert.doesNotMatch(gh[0].init.body, /LG화학/);
  const book = await (await worker.fetch(new Request(ORIGIN + '/ingest/google-relay-pending', { headers: { Authorization: `Bearer ${TOKEN}` } }), env, {})).json();
  assert.equal(book.pending[0].q, 'LG화학 2-EHA');
  assert.equal(book.pending[0].qid, await relayKey('LG화학 2-EHA', 30));
  assert.equal(book.count, 1);
  // 10분 안 같은 낱말은 다시 안 부름
  const f2 = routes();
  assert.match((await call('news_check', { q: 'LG화학 2-EHA', days: 30 }, opts({ GITHUB_DISPATCH_TOKEN: 'ghp_test' }, f2))).text, /GitHub에 구글 조회를 맡겨 둠/);
  assert.equal(f2.calls.filter((c) => c.url.startsWith('https://api.github.com/')).length, 0);
  // 토큰 권한 문제는 그대로 알린다
  const f3 = routes(new Response('{}', { status: 403 }));
  assert.match((await call('news_check', { q: '다른 낱말', days: 30 }, opts({ GITHUB_DISPATCH_TOKEN: 'ghp_test' }, f3))).text, /GitHub 경유 조회 요청 실패\(HTTP 403 — 토큰 권한·만료 확인\)/);
  // GitHub가 받아 온 결과가 있으면 구글 채널로 쓴다(판정의 웹 색인에도 든다)
  const at = new Date(NOW.getTime() - 3 * 60000).toISOString();
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/google-relay', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` },
    body: JSON.stringify({ schema: 'google_relay/v1', generatedAt: at, results: [{ qid: await relayKey('LG화학 2-EHA', 30), q: 'LG화학 2-EHA', days: 30,
      fetchedAt: at, status: 'ok', returned: 2, items: [{ title: '[단독] LG화학, 수입산 점착제 원료 반덤핑 조사 신청', url: 'https://n/1', date: '2026-10-25', source: '아이뉴스24' },
        { title: '오래된 기사', url: 'https://n/2', date: '2026-01-01', source: 'x' }] }] }) }), env, {})).status, 200);
  const f4 = routes();
  const r4 = await call('news_check', { q: 'LG화학 2-EHA', days: 30 }, opts({ GITHUB_DISPATCH_TOKEN: 'ghp_test' }, f4));
  assert.match(r4.text, /■ 구글 뉴스\(GitHub 경유 \d\d-\d\d \d\d:\d\d 조회\): 1건 \(응답 2건\)/);
  assert.match(r4.text, /2026-10-25 \| 아이뉴스24 \| \[단독\] LG화학, 수입산 점착제 원료 반덤핑 조사 신청 ★단독/);
  assert.equal(f4.calls.filter((c) => c.url.startsWith('https://api.github.com/')).length, 0);
  // 공개 연결은 맡기지 않는다
  const pub = await call('news_check', { q: 'LG화학 2-EHA', days: 30 }, { fetch: routes() });
  assert.doesNotMatch(pub.text, /GitHub 경유/);
});

test('news_check: 구글이 막히면 자동 보도 대조(GitHub)의 마지막 구글 성적을 함께 보인다(11-12)', async () => {
  const env = PRIVATE().env;
  const at = new Date(NOW.getTime() - 2 * 3600000).toISOString();
  const ch = (g) => ({ naver: { status: 'ok' }, bing: { status: 'ok' }, google: { status: g } });
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/radar-check', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` },
    body: JSON.stringify({ schema: 'radar_check/v1', generatedAt: at, items: [
      { id: 'a', verdict: '미보도 후보', checkedAt: at, queries: ['x'], evidence: [], channels: ch('ok') },
      { id: 'b', verdict: '관련 보도 있음', checkedAt: at, queries: ['y'], evidence: [], channels: ch('ok') },
      { id: 'c', verdict: '미확인', checkedAt: at, queries: ['z'], evidence: [], channels: ch('failed') },
      { id: 'd', verdict: '관련 보도 있음', checkedAt: '2026-10-01T00:00:00Z', queries: ['w'], evidence: [], channels: ch('failed') }] }) }), env, {})).status, 200);
  const failing = fakeFetch({ 'https://news.google.com/': new Response('x', { status: 503 }) });
  const r = await call('news_check', { q: '낱말 두개' }, { path: `/mcp/${TOKEN}`, env, fetch: failing });
  assert.match(r.text, /구글 뉴스: 이 서버\(Cloudflare Worker\)에서는 구글이 접속을 막음\(HTTP 503\) — 레이더 고장 아님 · 자동 보도 대조\(GitHub\) 마지막 실행 \d\d-\d\d \d\d:\d\d 구글 2\/3 정상/);
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
  assert.match(r.text, /구글 뉴스: 이 서버\(Cloudflare Worker\)에서는 구글이 접속을 막음\(HTTP 503\) — 레이더 고장 아님/);
  assert.match(r.text, /빙 뉴스: 1건/);
  assert.match(r.text, /https:\/\/www\.example-news\.kr\/a\/1/);
  assert.match(r.text, /판정: 관련 보도 후보 1건/);
  const bothDown = fakeFetch({ 'https://news.google.com/': new Response('x', { status: 503 }), 'https://www.bing.com/': new Response('x', { status: 503 }),
    'https://naverapihub.apigw.ntruss.com/': Response.json({ items: [] }) });
  const d = await call('news_check', { q: '동국씨엠 컬러강판' }, { ...PRIVATE({ NAVER_CLIENT_ID: 'i', NAVER_CLIENT_SECRET: 's' }), fetch: bothDown });
  assert.match(d.text, /판정: 미확인 — 웹 색인\(구글·빙 모두\)/);
});

test('news_check: Bing adds its newest-first list, and English words also the US edition (Korean words stay KR)', async () => {
  const item = (title, url, day) => `<item><title>${title}</title><link>https://www.bing.com/news/apiclick.aspx?url=${encodeURIComponent(url)}</link><pubDate>${day}</pubDate></item>`;
  const rss = (...items) => new Response(`<rss><channel>${items.join('')}</channel></rss>`);
  const env = PRIVATE({ NAVER_CLIENT_ID: 'i', NAVER_CLIENT_SECRET: 's' });
  const B = 'https://www.bing.com/news/search?q=Qcells%20Cartersville%20air%20permit&format=rss&';
  const NEW = '&qft=sortbydate%3d%221%22';
  const kr = item('Qcells adds line', 'https://kr.example/1', 'Fri, 23 Oct 2026 03:00:00 GMT');
  const routes = (us) => ({
    'https://news.google.com/': new Response('blocked', { status: 503 }),
    // 최신순 주소가 기본 주소로 시작하므로 먼저 둔다
    [B + 'setlang=ko-KR&cc=KR' + NEW]: rss(kr, item('Qcells Georgia hiring', 'https://kr.example/3', 'Sun, 25 Oct 2026 01:00:00 GMT')),
    [B + 'setlang=ko-KR&cc=KR']: rss(kr),
    [B + 'setlang=en-US&cc=US' + NEW]: us,
    [B + 'setlang=en-US&cc=US']: us,
    'https://www.bing.com/news/search?q=': rss(),
    'https://naverapihub.apigw.ntruss.com/': Response.json({ items: [] }),
  });
  const fetch = fakeFetch(routes(rss(kr, item('Qcells seeks air permit for Cartersville plant', 'https://local.example/2', 'Sat, 24 Oct 2026 12:00:00 GMT'))));
  const r = await call('news_check', { q: 'Qcells Cartersville air permit', days: 30 }, { ...env, fetch });
  assert.match(r.text, /빙 뉴스: 3건 \(응답 7건\) · 한국판 1건 · 한국판 최신순 \+1건 · 미국판 \+1건 · 미국판 최신순 \+0건 \(겹침 뺌\)/);
  assert.match(r.text, /https:\/\/local\.example\/2/);
  assert.match(r.text, /https:\/\/kr\.example\/3/);
  assert.match(r.text, /구글 뉴스: 이 서버\(Cloudflare Worker\)에서는 구글이 접속을 막음\(HTTP 503\) — 레이더 고장 아님[^\n]* \(웹 색인은 빙이 대신 — 판정에 영향 없음\)/);
  assert.match(r.text, /판정: 관련 보도 후보 3건/);
  // 미국판 실패는 현지 보도 미확인으로만 — 한국판이 정상이면 판정 기준은 그대로
  const down = fakeFetch(routes(new Response('x', { status: 503 })));
  const d = await call('news_check', { q: 'Qcells Cartersville air permit', days: 30 }, { ...env, fetch: down });
  assert.match(d.text, /빙 뉴스: 2건 .*미국판 실패\(HTTP 503\) · 미국판 최신순 실패\(HTTP 503\) \(겹침 뺌\) — 미국판 실패분은 현지 보도 미확인/);
  assert.match(d.text, /판정: 관련 보도 후보 2건/);
  // 한글 낱말은 한국판(관련도 순·최신순)만
  const ko = fakeFetch(routes(rss()));
  await call('news_check', { q: '한화큐셀 조지아 허가', days: 30 }, { ...env, fetch: ko });
  const bingUrls = ko.calls.filter((c) => c.url.startsWith('https://www.bing.com/')).map((c) => c.url);
  assert.equal(bingUrls.length, 2);
  assert.ok(bingUrls.every((u) => u.includes('setlang=ko-KR&cc=KR')));
  assert.ok(bingUrls.some((u) => u.endsWith(NEW)));
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
        kind: '반덤핑조사', review: '원심', country: '중국', beat: true, timeline: [['조사개시', '2026-10-08']], pending: ['예비조사', '공청회', '최종판정'], url: 'https://www.ktc.go.kr/v?875',
        applicant: { names: ['일진제강'], beat: [], newsId: '00002297', title: '무역위, 중국산 아연도금냉연, 옵셋인쇄판 덤핑조사 최종판정', posted: '2026-10-26' } },
      { id: '00000859', no: '구제 23-2025-13호', title: '중국산 인쇄제판용 평면모양 사진플레이트', product: '인쇄제판용 평면모양 사진플레이트', opened: '2026-01-08', stage: '조사실행',
        kind: '반덤핑조사', review: '재심', country: '중국', beat: false, timeline: [['조사개시', '2026-01-08']], pending: ['최종판정'], url: 'https://www.ktc.go.kr/v?859',
        // 11-12: 재심 사건에 붙은 이름은 원심 보도자료의 신청인(시험 값)
        applicant: { names: ['테스트인쇄판'], beat: [], newsId: '00001723', title: '옵셋인쇄판 반덤핑 원심 최종판정', posted: '2021-11-08' } },
      { id: '00000493', no: '제 4-1-2008-6', title: '낚싯대케이스', product: '낚싯대케이스', opened: '2008-07-23', stage: '조사실행', beat: false, url: 'https://www.ktc.go.kr/v?493' }],
    left: [{ id: '00000868', no: '구제23-2026-5호', title: '중국산 석도강판의 덤핑사실 및 국내산업피해 유무', product: '석도강판', leftAt: '2026-10-30T07:40:00+09:00', result: '부정 · 조사종결' }],
    meetings: [{ id: '00000312', title: '제479차 11월 무역위원회 개최 안내', posted: '2026-11-13', meetingOn: '2026-11-20', summary: '3건(정기보고1, 의결2)',
      url: 'https://www.ktc.go.kr/noticeScheduleView.do?dltnc_id=00000312&menuId=24',
      agenda: [{ kind: '의결', no: '2026-27', text: '중국산 석도강판의 덤핑사실및국내산업피해유무 예비판정(원심)', beat: true,
        applicant: { names: ['케이지스틸', '테스트석도'], beat: ['KG스틸'], newsId: '00002050', title: '무역위, 중국산 석도강판 덤핑조사 개시', posted: '2026-07-14' } },
        { kind: '보고', no: '2026-21', text: '화장품 상표권 침해 조사개시 보고', beat: false }] },
      { id: '00000311', title: '제478차 10월 무역위원회 개최 안내', posted: '2026-10-16', agenda: null, agendaError: 'PDF 받기 실패' }],
    news: [{ id: '00002297', title: '무역위, 중국산 아연도금냉연, 옵셋인쇄판 덤핑조사 최종판정', posted: '2026-10-26',
      applicants: [{ product: '중국산 아연도금냉연', names: ['동국씨엠', '케이지스틸', '세아씨엠'], beat: ['동국씨엠', 'KG스틸'], how: '표' }] },
    // 11-12: PDF 없이 한글 파일만 붙은 옛 보도자료(probe 214) — 신청인은 한글 파일에서
    { id: '00001776', title: '무역위, 스테인리스강 냉간압연 및 평판압연 반덤핑조사 개시', posted: '2024-06-03', older: true, applicantsFrom: 'hwpx',
      applicants: [{ product: '베트남산 스테인리스강 냉간압연 제품', names: ['포스코'], beat: ['포스코'], how: '개요' }] }] };
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
  assert.match(r.text, /최근 보도자료: 무역위, 중국산 아연도금냉연, 옵셋인쇄판 덤핑조사 최종판정\(2026-10-26\) \[신청인\(첨부 PDF\) 중국산 아연도금냉연: 동국씨엠·케이지스틸·세아씨엠\(출입처 동국씨엠·KG스틸\)\]/);
  // 11-12 판정 예고: 사건·안건에 보도자료 신청인
  assert.match(r.text, /의결\(출입 업종 품목\): 중국산 석도강판의 덤핑사실및국내산업피해유무 예비판정\(원심\) · 신청인\(보도자료 「무역위, 중국산 석도강판 덤핑조사 개시」 2026-07-14 첨부\) 케이지스틸·테스트석도\(출입처 KG스틸\)/);
  assert.match(r.text, /구제 23-2026-9호 · 중국산 무계목강관[^\n]* · 신청인\(보도자료 「무역위, 중국산 아연도금냉연, 옵셋인쇄판 덤핑조사 최종」 2026-10-26 첨부\) 일진제강\n/);
  assert.doesNotMatch(r.text, /EU 철강 쿼터/);
  const steel = await call('trade_remedies', { section: 'ktc', company: '석도' }, opts);
  assert.doesNotMatch(steel.text, /커넥티드/);
  assert.match(steel.text, /제479차/);
  // 11-12: 재심 사건의 신청인은 그 보도자료(원심) 때 이름이라고 적는다 — 원심 사건·안건엔 안 붙는다
  assert.match(r.text, /구제 23-2025-13호 · 중국산 인쇄제판용 평면모양 사진플레이트[^\n]*반덤핑조사\/재심[^\n]* · 신청인\(보도자료 「옵셋인쇄판 반덤핑 원심 최종판정」 2021-11-08 첨부\) 테스트인쇄판 — 재심 건: 그 보도자료 때 신청인\(재심 요청인은 다를 수 있음\)\n/);
  assert.doesNotMatch(r.text, /일진제강 — 재심 건/);
  assert.doesNotMatch(r.text, /케이지스틸·테스트석도\(출입처 KG스틸\) — 재심 건/);
  // 11-12: 한글 파일에서 읽은 신청인 표시, 신청인 이름으로 찾기(사건·안건·보도자료)
  assert.match(r.text, / \/ 무역위, 스테인리스강 냉간압연 및 평판압연 반덤핑조사 개시\(2024-06-03\) \[신청인\(첨부 한글 파일\) 베트남산 스테인리스강 냉간압연 제품: 포스코\(출입처 포스코\)\]/);
  const byApplicant = await call('trade_remedies', { section: 'ktc', company: 'KG스틸' }, opts);
  assert.match(byApplicant.text, /제479차[^\n]*\n   의결\(출입 업종 품목\): 중국산 석도강판[^\n]*케이지스틸·테스트석도\(출입처 KG스틸\)/);
  assert.match(byApplicant.text, /최근 보도자료: 무역위, 중국산 아연도금냉연, 옵셋인쇄판 덤핑조사 최종판정/);
  assert.doesNotMatch(byApplicant.text, /스테인리스강 냉간압연 및 평판압연/);
  const byName = await call('trade_remedies', { section: 'ktc', company: '일진제강' }, opts);
  assert.match(byName.text, /구제 23-2026-9호 · 중국산 무계목강관/);
  assert.doesNotMatch(byName.text, /커넥티드/);
  const today = await call('radar_today', { include_minor: true }, opts);
  const b = today.text.split('[B · ')[1].split('[C · ')[0];
  assert.match(b, /무역구제\n   무역위원회 회의 안내\(개최 2026-11-20\): 제479차 — 의결: 중국산 석도강판 예비판정/);
  assert.doesNotMatch(b, /플라스틱 필름|아연도금냉연 덤핑조사 최종판정/);
  // 보도 대조로 넘기는 항목: 무역위 항목은 회사 이름이 없어 넘기지 않는다(11-05 안내 글자가 힌트 자리에 들어가 대조가 멈춤)
  const items = await (await radarItems(new Request(ORIGIN + '/ingest/radar-items?hours=168', { headers: { Authorization: `Bearer ${TOKEN}` } }), env, { now: new Date() })).json();
  assert.ok(items.items.every((x) => x.check && typeof x.check === 'object'));
  assert.ok(!items.items.some((x) => String(x.id).startsWith('ktc:')));   // 이 묶음의 B 항목(회의 안내)은 품목이 없어 대조하지 않음
  // 11-08 품목 이름으로 대조: 짧은 품목 + 덤핑·세이프가드만
  const k = (product, text, extra = {}) => ktcHint({ ktcKind: 'case', product, label: '무역위 새 조사', text, ...extra });
  assert.deepEqual(k('석도강판', '중국산 석도강판의 덤핑사실 및 국내산업피해 유무 조사'), { who: '석도강판', terms: ['반덤핑', '무역위원회'], alts: { 반덤핑: ['반덤핑', '덤핑'] } });
  assert.equal(k('석도강판', '세이프가드 조사').terms[0], '세이프가드');
  assert.equal(k('인쇄제판용 평면모양 사진플레이트', '덤핑'), undefined);   // 긴 정식 품목명
  assert.equal(k('커넥티드 전기자동차', '특허권 침해 불공정무역행위'), undefined);
  assert.equal(k('낚싯대케이스', '원산지 표시위반'), undefined);            // 덤핑·세이프가드 아님
  assert.equal(k('석도강판', '덤핑', { ktcKind: 'news' }), undefined);
  assert.equal(ktcHint({ ktcKind: 'meeting', text: '의결: 중국산 석도강판 예비판정' }), undefined);
  // 11-11: 띄어쓰기 한 번인 품목('아크릴산 2-에틸헥실'), 제목에 '덤핑'이 없어도 누리집 조사 유형 코드 10100001이면 덤핑
  const u = (code) => ({ url: `https://www.ktc.go.kr/viewInvest.do?menuId=11&masterId=00000873&invstg_type_code=${code}` });
  const ehaText = '중국, 미국, 말레이시아산 아크릴산 2-에틸헥실 — 품목 아크릴산 2-에틸헥실, 개시 2026-11-05';
  assert.deepEqual(k('아크릴산 2-에틸헥실', ehaText, u('10100001')), { who: '아크릴산 2-에틸헥실', terms: ['반덤핑', '무역위원회'], alts: { 반덤핑: ['반덤핑', '덤핑'] } });
  assert.equal(k('아크릴산 2-에틸헥실', ehaText, u('10100002')), undefined);   // 불공정무역행위 코드
  assert.equal(k('아크릴산 2-에틸헥실', ehaText), undefined);                  // 유형을 모르면 대조 안 함
  const ev = (text, extra = {}) => ({ ktcKind: 'case', beat: true, tier: 'B', label: '무역위 새 조사 · 구제23-2026-10호', text, product: '아크릴산 2-에틸헥실', ...u('10100001'), ...extra });
  assert.equal(ktcNewDumping(ev(ehaText)), true);
  assert.equal(ktcNewDumping(ev('대만, 태국, 아랍에미리트연합산 PET 필름 종료재심사(2차)')), false);   // 재심은 B 그대로
  assert.equal(ktcNewDumping(ev(ehaText, { beat: false })), false);                                    // 출입 업종 품목 아님
  assert.equal(ktcNewDumping(ev('자동차용 배터리팩 특허권 침해', u('10100002'))), false);              // 불공정무역행위
  assert.equal(ktcNewDumping(ev('중국산 석도강판의 덤핑사실 및 국내산업피해 유무 조사', { url: 'https://k/c' })), true);   // 제목에 덤핑
  assert.equal(ktcNewDumping(ev(ehaText, { ktcKind: 'step' })), false);                                // 진행일정은 새 조사 아님
});

test('무역위 새 반덤핑 조사(출입 업종 품목)는 A — 신청인 확인 문구·유형 코드 표시·품목 이름 보도 대조(11-11 2-EHA)', async () => {
  const env = PRIVATE().env;
  const recent = new Date(NOW.getTime() - 3600000).toISOString();
  const url = (id, code) => `https://www.ktc.go.kr/viewInvest.do?menuId=11&masterId=${id}&invstg_type_code=${code}`;
  const doc = { schema: 'trade_remedy/v1', generatedAt: recent, quarter: '2026-10-01', rules: [], quotas: [], federalRegister: [], pages: [],
    checks: [{ source: '무역위원회', status: 'ok', returned: 45 }], ktc: { checkedAt: recent, cases: [], meetings: [], news: [],
      producers: { 'ktc:case:00000873': { line: '품목 이름이 나온 출입처 2025 사업보고서(II. 사업의 내용): LG화학 1곳 「아크릴산 2-에틸헥실」(접수 20260310000001) — 신청인 확정 아님(회사 확인)' } } },
    events: [
      { id: 'ktc:case:00000873', pageId: 'ktc', country: 'KR', label: '무역위 새 조사 · 구제23-2026-10호', text: '중국, 미국, 말레이시아산 아크릴산 2-에틸헥실 — 품목 아크릴산 2-에틸헥실, 개시 2026-11-05',
        url: url('00000873', '10100001'), detectedAt: recent, tier: 'B', beat: true, ktcKind: 'case', product: '아크릴산 2-에틸헥실' },
      { id: 'ktc:case:00000870', pageId: 'ktc', country: 'KR', label: '무역위 새 조사 · 구제23-2026-7호', text: '대만, 태국, 아랍에미리트연합산 PET 필름 종료재심사(2차) — 품목 PET 필름, 개시 2026-08-26, 반덤핑조사/재심',
        url: url('00000870', '10100001'), detectedAt: recent, tier: 'B', beat: true, ktcKind: 'case', product: 'PET 필름' },
      // 11-11: 판정 보도자료 첨부 PDF에 출입처가 신청인 — 회사 항목 B, 회사 이름으로 보도 대조
      { id: 'ktc:news:00002297', pageId: 'ktc', country: 'KR', label: '무역위 보도자료', url: 'https://www.ktc.go.kr/boardView.do?bbs_id=00002297&menuId=57&pageIndex=1&searchCondition=&searchKeyword=',
        text: '무역위, 중국산 아연도금냉연, 옵셋인쇄판 덤핑조사 최종판정 (등록 2026-10-26) · 첨부 PDF의 신청인 — 중국산 아연도금냉연: 동국씨엠, 케이지스틸, 세아씨엠',
        detectedAt: recent, tier: 'B', beat: true, ktcKind: 'news', company: '동국씨엠·KG스틸' }] };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/trade-remedy', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const r = (await call('radar_today', {}, { path: `/mcp/${TOKEN}`, env })).text;
  const a = r.split('[A · ')[1].split('[B · ')[0];
  const b = r.split('[B · ')[1].split('[C · ')[0];
  assert.match(a, /무역구제 · 아크릴산 2-에틸헥실\n   무역위 새 조사 · 구제23-2026-10호: 중국, 미국, 말레이시아산 아크릴산 2-에틸헥실 — 품목 아크릴산 2-에틸헥실, 개시 2026-11-05 · 덤핑 조사\(누리집 조사 유형 코드 — 상세 유형은 아직 비어 있음\) — 국내 생산자가 신청해야 열리는 조사\. 신청인 이름은 누리집에 없음: 출입처가 이 품목을 만드는지·신청했는지 회사 확인/);
  assert.match(a, /회사 확인 · 품목 이름이 나온 출입처 2025 사업보고서\(II\. 사업의 내용\): LG화학 1곳 「아크릴산 2-에틸헥실」\(접수 20260310000001\) — 신청인 확정 아님\(회사 확인\)/);
  assert.match(b, /PET 필름 종료재심사\(2차\)/);   // 재심은 B 그대로
  assert.doesNotMatch(b, /아크릴산/);
  const items = await (await radarItems(new Request(ORIGIN + '/ingest/radar-items?hours=72', { headers: { Authorization: `Bearer ${TOKEN}` } }), env, { now: NOW })).json();
  assert.deepEqual(items.items.find((x) => x.id === 'ktc:case:00000873').check.terms, ['반덤핑', '무역위원회']);
  assert.match(b, /무역구제 · 동국씨엠·KG스틸\n   무역위 보도자료: 무역위, 중국산 아연도금냉연, 옵셋인쇄판 덤핑조사 최종판정 \(등록 2026-10-26\) · 첨부 PDF의 신청인 — 중국산 아연도금냉연: 동국씨엠, 케이지스틸, 세아씨엠/);
  assert.deepEqual(items.items.find((x) => x.id === 'ktc:news:00002297').check, { who: '동국씨엠', terms: ['반덤핑', '무역위원회'], alts: { 반덤핑: ['반덤핑', '덤핑'] } });
  assert.equal(items.items.find((x) => x.id === 'ktc:case:00000873').tier, 'A');
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
        stacks: { 1: { lastDt: '2026-10-31 09:00', obs: Array(9).fill(['x', 0]) },
          2: { lastDt: '2026-10-31 09:00', obs: Array(9).fill(['x', 0]), stopLog: [['2026-10-20 03:00', '2026-10-20 12:00'], ['2026-10-25 06:00', '2026-10-26 09:00']] } } },
      { id: 'b', company: '포스코', name: '㈜포스코 광양제철소', area: '전라남도', meaningful: 150, stopped: ['17'],
        stacks: { 17: { lastDt: '2026-10-31 09:00', obs: Array(9).fill(['x', 0]), stoppedSince: '2026-10-27 21:00', longStopFor: '2026-10-27 21:00', status: ['보수중', '2026-10-27 21:00'] },
          135: { lastDt: '2026-10-31 09:00', obs: [], status: ['가동중지', '2026-10-31 08:00'] }, 3: { lastDt: '2026-10-31 09:00', obs: [], status: ['미수신', '2026-10-31 09:00'] } },
        exceedLog: [{ stack: '40', pollutant: 'nox', value: 61.2, limit: 50, at: '2026-10-31 06:00' }, { stack: '40', pollutant: 'nox', value: 70.5, limit: 50, at: '2026-10-31 09:00' }] },
      { id: 'c', company: '고려아연', name: '고려아연㈜온산제련소', area: '울산광역시', meaningful: 0, stopped: [], stacks: { 11: { obs: [['x', 5]] } } },
      { id: 'e', company: 'SK이노베이션', name: '에스케이이노베이션 주식회사', area: '전라남도', meaningful: 0, stopped: [], note: '발전 사업장으로 보임(공장등록 화력 발전업)',
        stacks: { 1: { obs: [], status: ['가동중지', '2026-10-31 08:00'] } } },
      { id: 'd', company: '동국제강', name: '동국제강㈜ 포항공장', area: '경상북도', meaningful: 3, stopped: [], missingRuns: 3, workMissing: 1,
        lastSeen: '2026-10-31T06:20:00+09:00', stacks: { 1: { obs: Array(9).fill(['x', 5]) } } }],
    events: [{ id: 'stk:down:a:2026-10-31', kind: '사업장 가동 중단 신호', tier: 'A', company: '현대제철', site: '현대제철㈜포항2공장', detectedAt: recent,
      text: '현대제철㈜포항2공장: 평소 움직이던 배출구 2개 중 2개가 3번 연속 평소의 10% 아래' },
      { id: 'stk:exceed2:b:40:nox:2026-10-31 06:00', kind: '배출허용기준 초과 지속', tier: 'A', company: '포스코', site: '㈜포스코 광양제철소', detectedAt: recent,
        text: '㈜포스코 광양제철소 배출구 40번 질소산화물 측정값 70.5이 배출허용기준 50을 넘음(기준의 1.4배, 측정 2026-10-31 09:00) — 2026-10-31 06:00 측정부터 이 감시의 실행 2번 연속 초과(처음 61.2)' },
      ...['3', '58', '4'].map((c) => ({ id: `stk:gone:영풍:x:${c}:d`, kind: '배출구 목록에서 빠짐', tier: 'C', company: '영풍', site: '㈜영풍석포제련소', detectedAt: recent,
        text: `㈜영풍석포제련소 배출구 ${c}번이 굴뚝 자동측정 목록에서 2번 연속 빠짐 — 이후 다시 나타남(측정 x, 일시적 누락)` })),
      { id: 'stk:sitegone:영풍:x:d', kind: '사업장 목록에서 빠짐(굴뚝 측정)', tier: 'C', company: '영풍', site: '㈜영풍석포제련소', detectedAt: recent,
        text: '㈜영풍석포제련소이 굴뚝 자동측정 목록에서 2번 연속 빠짐 — 이후 다시 나타남(확인 x, 일시적 누락)' },
      { id: 'stk:halt:s-oil:x', kind: '배출구 보수·가동중지 전환', tier: 'B', company: 'S-OIL', site: 'S-OIL㈜ 온산공장', detectedAt: recent,
        text: 'S-OIL㈜ 온산공장: 배출구 8개가 이번 측정에서 상태 글자 보수중으로 바뀜' }] };
  const post = await worker.fetch(new Request(ORIGIN + '/ingest/kr-stacks', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {});
  assert.equal(post.status, 200);
  const opts = { path: `/mcp/${TOKEN}`, env };
  const r = await call('kr_official', { section: 'stacks' }, opts);
  assert.match(r.text, /\[굴뚝 측정\(공장 가동 신호\) · 출입처 사업장 5곳 · 배출구 8개/);
  // 설정 메모(siteNotes)가 있는 사업장은 '가동중지' 줄에 메모를 붙인다
  assert.match(r.text, /SK이노베이션 · 에스케이이노베이션 주식회사\(전라남도\) · 배출구 1개 중 1개: 1번\(10-31 08:00\) · ⓘ 발전 사업장으로 보임\(공장등록 화력 발전업\)/);
  assert.match(r.text, /- 지금 목록에서 빠져 있는 사업장 1곳\n  동국제강 · 동국제강㈜ 포항공장\(경상북도\) · 연속 3번 빠짐\(평일 일하는 시간 1번\) · 마지막으로 보인 실행 2026-10-31T06:20/);
  assert.match(r.text, /멈춤으로 판단한 배출구가 있는 사업장 2곳/);
  assert.ok(r.text.indexOf('포항2공장(경상북도)') < r.text.indexOf('광양제철소(전라남도)'));  // 멈춘 비율 높은 순
  assert.match(r.text, /평소 움직이던 배출구 2개 중 멈춤 2개: 1번\(측정 2026-10-31 09:00\), 2번\(측정 2026-10-31 09:00, 앞선 멈춤 2번\(마지막 10-25 06:00~10-26 09:00\)\)/);
  assert.match(r.text, /멈춤 1개: 17번\(측정 2026-10-31 09:00, 멈춤 2026-10-27 21:00부터·사흘 넘음, 상태 '보수중'\)/);
  assert.match(r.text, /- 측정값 대신 상태 글자가 온 배출구: 가동중지 2 · 미수신 1 · 보수중 1 \(가동중지 = 사업장이 보낸 시설 멈춤 신고, 보수중·기기점검·미수신·측정자료확인중 = 측정기 쪽 상태\)\n  포스코 · ㈜포스코 광양제철소 · 미수신 1 · 보수중 1 · 가동중지 1/);
  assert.match(r.text, /관측이 아직 6번이 안 된 사업장 2곳/);
  assert.match(r.text, /A · .* · 사업장 가동 중단 신호 · 현대제철/);
  // 빠졌다 다시 나타난 것은 사업장·날짜별 한 줄(11-03: 14일 98건 대부분)
  assert.match(r.text, /감지된 변화 · 최근 14일 7건\(빠졌다 다시 나타난 것 4건은 아래에 사업장·날짜별로 접음\)/);
  assert.match(r.text, /- 목록에서 빠졌다가 다시 나타남\(일시적 누락\) · 1묶음\n  \d{4}-\d{2}-\d{2} · 영풍 · ㈜영풍석포제련소: 사업장 통째 · 배출구 3·4·58번 \(이벤트 4건\)/);
  assert.ok(!/C · .* · 배출구 목록에서 빠짐 · 영풍/.test(r.text));
  // 가동중지 신고 배출구 목록(11-03)
  assert.match(r.text, /- 시설 멈춤 신고\('가동중지'\) 배출구가 있는 사업장 2곳\(번호·이 감시가 처음 본 측정 — 그 전부터였을 수 있음\)\n  포스코 · ㈜포스코 광양제철소\(전라남도\) · 배출구 3개 중 1개: 135번\(10-31 08:00\)/);
  assert.match(r.text, /- 배출허용기준 넘은 측정값\(이 감시가 본 것, 사업장마다 최근 20건\) 2건\n  2026-10-31 09:00 · 포스코 · ㈜포스코 광양제철소 배출구 40번 질소산화물 70\.5\(기준 50\)/);
  assert.match(r.text, /기준 초과 값은 확정 전 실시간 값/);
  const today = (await call('radar_today', {}, opts)).text;
  const a = today.split('[A · ')[1].split('[B · ')[0];
  // 상태 글자 전환은 저장분이 B여도 레이더에서는 C(검증 전, 11-03)
  assert.doesNotMatch(today.split('[C · ')[0], /배출구 8개가 이번 측정에서 상태 글자/);
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
  // 사흘 넘게 멈춘 배출구(굴뚝 감시 '오래 멈춤')는 큰 제철소의 한두 개라도 배경(11-02 경향 [단독] '포스코 광양 2고로 전면 개수')
  const long = structuredClone(docs);
  long['kr-stacks'].sites[1].stacks = { 129: { stoppedSince: '2026-10-31 02:00', longStopFor: '2026-10-31 02:00' }, 135: { stoppedSince: '2026-11-01 08:00' } };
  const s2 = background(long, now).find((x) => x.id === 'bg:stk:s2');
  assert.equal(s2.fact, '㈜포스코 광양제철소 굴뚝 배출구 멈춤 2개(평소 움직이던 137개 중) · 사흘 넘게 멈춤 1개(129번 2026-10-31 02:00부터)');
  const fresh = [{ id: 'l1', tier: 'A', tool: 'kr_official', watch: '지자체 고시·공고', company: '기아', date: '2026-10-29', fact: '화성시 고시 「기아 오토랜드 화성 PBV 2공장」' }];
  const g = convergence([...fresh, ...bg], { cut: Date.parse('2026-10-29T03:00:00Z') });  // 10-29 12:00 KST(24시간 창)
  assert.deepEqual(g.map((x) => [x.company, x.place, x.watches.length, x.fresh]), [['기아', '화성', 2, true]]);
  assert.equal(convergence([...fresh, ...bg], { cut: Date.parse('2026-10-29T15:00:00Z') })[0].fresh, false);  // 10-30 00:00 KST부터면 10-29 공고는 새 항목 아님
  // 당진: 공사 현장 + 멈춘 굴뚝은 둘 다 배경이라 묶지 않는다
  assert.ok(!g.some((x) => x.place === '당진'));
});

test('굴뚝 즉시 알림 대상(11-04·11-08 기자 결정): 다른 감시가 같은 공장 이름을 가리키거나 배출구 절반 넘게 사흘 넘게 가동중지일 때만 표시', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const recent = new Date(NOW.getTime() - 2 * 3600000).toISOString();
  const kst = (h) => new Date(NOW.getTime() + 9 * 3600000 - h * 3600000).toISOString().slice(0, 16).replace('T', ' ');
  const post = (feed, doc) => worker.fetch(new Request(ORIGIN + `/ingest/${feed}`, { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {});
  const ev = (id, kind, tier, company, site, text) => ({ id, kind, tier, company, site, text, detectedAt: recent });
  const halt = (h) => ({ status: ['가동중지', kst(h)], obs: [] });
  await post('kr-stacks', { schema: 'kr_stacks/v1', generatedAt: recent, status: 'complete', baselineSince: '2026-10-01T00:00:00+09:00', checks: [{ source: '굴뚝 자동측정(CleanSYS)', status: 'ok' }],
    sites: [
      { id: '현대제철:현대제철(주)순천공장', company: '현대제철', name: '현대제철㈜순천공장', stopped: ['81'], meaningful: 7, stacks: { 81: halt(80) } },
      { id: 'KG스틸:케이지스틸(주)인천공장', company: 'KG스틸', name: '케이지스틸㈜ 인천공장', stopped: ['5', '6', '9', '10'], meaningful: 6,
        stacks: { 5: halt(90), 6: halt(90), 9: halt(80), 10: { ...halt(20), stoppedSince: kst(75) }, 12: halt(20), 11: { obs: [] } } },   // 10번: 상태는 20시간 전 처음 봤지만 숫자는 75시간 전부터 끊김
      { id: '세아:(주)세아창원특수강', company: '세아', name: '㈜세아창원특수강', stopped: ['191'], meaningful: 9, stacks: { 191: halt(100) } }],
    events: [
      ev('stk:down:현대제철:현대제철(주)순천공장:d', '사업장 가동 중단 신호', 'A', '현대제철', '현대제철㈜순천공장', '현대제철㈜순천공장: 평소 움직이던 배출구 7개 중 4개가 3번 연속 평소의 10% 아래'),
      ev('stk:down:KG스틸:케이지스틸(주)인천공장:d', '사업장 가동 중단 신호', 'A', 'KG스틸', '케이지스틸㈜ 인천공장', '케이지스틸㈜ 인천공장: 평소 움직이던 배출구 6개 중 4개가 3번 연속 평소의 10% 아래'),
      ev('stk:longstop:세아:(주)세아창원특수강:191:d', '배출구 오래 멈춤', 'B', '세아', '㈜세아창원특수강', '㈜세아창원특수강: 배출구 1개가 사흘 넘게 평소의 10% 아래')] });
  await post('kr-workforce', { schema: 'kr_workforce/v1', generatedAt: recent, month: '202610', sites: [], projects: [], checks: [], events: [
    { id: 'wf:delta:현대제철:순천', kind: '인력 감소', tier: 'B', company: '현대제철', month: '202610', detectedAt: recent, text: '현대제철(전라남도 순천시) 국민연금 가입자 1,020→940명(-80명)' }] });
  const r = (await call('radar_today', {}, opts)).text;
  const idLine = (id) => r.split('\n').find((l) => l.includes(`id ${id}`) && l.includes('자세히:'));
  // 11-08: 시군까지만 맞는 겹침(공장 이름 없는 국민연금 순천)은 세지 않는다
  assert.doesNotMatch(idLine('stk:down:현대제철:현대제철(주)순천공장:d'), /즉시 알림 대상/);
  assert.match(idLine('stk:down:KG스틸:케이지스틸(주)인천공장:d'), /〔즉시 알림 대상: 장기 가동중지 신고 — 평소 움직이던 배출구 6개 중 4개가 사흘 넘게 '가동중지'〕$/);
  assert.doesNotMatch(idLine('stk:longstop:세아:(주)세아창원특수강:191:d'), /즉시 알림 대상/);   // 굴뚝 신호만(9개 중 1개)
  assert.doesNotMatch(idLine('wf:delta:현대제철:순천'), /즉시 알림 대상/);   // 굴뚝 아닌 항목엔 붙이지 않는다
  // 겹친 신호를 킬하면 그 항목은 증거로 세지 않는다(include_judged로 볼 때도)
  await call('candidate_feedback', { item_id: 'wf:delta:현대제철:순천', verdict: '킬', reason: '작음' }, opts);
  for (const args of [{}, { include_judged: true }]) {
    const r2 = (await call('radar_today', args, opts)).text;
    assert.doesNotMatch(r2.split('\n').find((l) => l.includes('id stk:down:현대제철:현대제철(주)순천공장:d') && l.includes('자세히:')), /즉시 알림 대상/);
  }
});

test('정기보수 메모(11-08): 기자가 굴뚝 항목을 정기보수 사유로 판정하면 그 사업장 멈춤·빠짐 신호를 30일(또는 적힌 날까지) 접는다', async () => {
  assert.equal(stackSiteKey('stk:longstop:현대제철:현대제철(주)순천공장:81:2026-11-03'), '현대제철:현대제철(주)순천공장');
  assert.equal(stackSiteKey('dart:123'), null);
  const at = '2026-11-07T03:00:00.000Z';
  const memo = maintenanceMemo([
    { item_id: 'stk:longstop:현대제철:현대제철(주)순천공장:81:2026-11-03', verdict: '킬', reason: '현대제철 확인 결과 정기보수(순천·당진 배출구 가동중지)', created_at: at },
    { item_id: 'stk:down:세아:(주)세아창원특수강:2026-11-04', verdict: '킬', reason: '회사 확인: 대정비 12월 5일까지', created_at: at },
    { item_id: 'stk:exceed:포스코:(주)포스코포항제철소:65:sox:x', verdict: '킬', reason: '기자 판단: 실시간 기준 초과 값만으로는 아직 애매', created_at: at }]);
  assert.deepEqual([...memo.keys()], ['현대제철:현대제철(주)순천공장', '세아:(주)세아창원특수강']);
  assert.equal(new Date(memo.get('현대제철:현대제철(주)순천공장').until).toISOString(), '2026-12-07T03:00:00.000Z');   // 30일
  assert.equal(new Date(memo.get('세아:(주)세아창원특수강').until).toISOString(), '2026-12-05T14:59:00.000Z');      // 12-05 23:59 KST
  assert.equal(new Date(memo.get('현대제철:현대제철(주)순천공장').from).toISOString(), '2026-10-31T03:00:00.000Z');  // 7일 전부터
  // radar_today: 판정 뒤 같은 사업장(순천)의 가동 중단 신호는 C로 접고, 다른 사업장(당진 현대제철㈜)은 그대로 B
  const opts = PRIVATE();
  const recent = new Date(NOW.getTime() - 2 * 3600000).toISOString();
  const kst = (h) => new Date(NOW.getTime() + 9 * 3600000 - h * 3600000).toISOString().slice(0, 16).replace('T', ' ');
  const halt = (h) => ({ status: ['가동중지', kst(h)], obs: [] });
  await call('candidate_feedback', { item_id: 'stk:longstop:현대제철:현대제철(주)순천공장:81:old', verdict: '킬', reason: '회사 확인(기자): 순천공장 정기 보수를 순차 진행 중' },
    { ...opts, now: new Date(NOW.getTime() - 86400000) });
  const ev = (id, kind, tier, company, site) => ({ id, kind, tier, company, site, text: `${site}: ${kind}`, detectedAt: recent });
  await worker.fetch(new Request(ORIGIN + '/ingest/kr-stacks', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify({
    schema: 'kr_stacks/v1', generatedAt: recent, status: 'complete', baselineSince: '2026-10-01T00:00:00+09:00', checks: [{ source: '굴뚝 자동측정(CleanSYS)', status: 'ok' }],
    sites: [{ id: '현대제철:현대제철(주)순천공장', company: '현대제철', name: '현대제철㈜순천공장', meaningful: 4, stacks: { 81: halt(90), 82: halt(90), 83: halt(90) } },
      { id: '현대제철:현대제철(주)', company: '현대제철', name: '현대제철㈜', meaningful: 50, stacks: {} }],
    events: [ev('stk:down:현대제철:현대제철(주)순천공장:d', '사업장 가동 중단 신호', 'B', '현대제철', '현대제철㈜순천공장'),
      ev('stk:down:현대제철:현대제철(주):d', '사업장 가동 중단 신호', 'B', '현대제철', '현대제철㈜'),
      ev('stk:newstack:현대제철:현대제철(주)순천공장:99', '새 배출구', 'B', '현대제철', '현대제철㈜순천공장')] }) }), opts.env, {});
  const r = (await call('radar_today', { include_minor: true, limit: 30 }, opts)).text;
  const block = (t) => r.split(`[${t} · `)[1]?.split('\n[')[0] ?? '';
  assert.match(block('C'), /현대제철㈜순천공장: 사업장 가동 중단 신호 · ⓘ 기자 판정\(\d\d-\d\d '회사 확인\(기자\): 순천공장 정기 보수를 순차 진행 중'\) — \d\d-\d\d까지 이 사업장 멈춤·빠짐 신호는 접음/);
  assert.match(block('B'), /현대제철㈜: 사업장 가동 중단 신호/);              // 당진(다른 사업장)
  assert.match(block('B'), /현대제철㈜순천공장: 새 배출구/);                  // 멈춤·빠짐이 아닌 신호는 그대로
  // 사흘 넘는 가동중지가 절반 넘어도(4개 중 3개) 정기보수 메모가 있으면 즉시 알림 대상이 아니다
  assert.doesNotMatch(r, /즉시 알림 대상: 장기 가동중지 신고/);
  const x = { id: 'stk:down:현대제철:현대제철(주)순천공장:d', tier: 'B', watch: '굴뚝 측정(공장 가동 신호)', company: '현대제철', site: '현대제철㈜순천공장' };
  const sdoc = { sites: [{ company: '현대제철', name: '현대제철㈜순천공장', meaningful: 4, stacks: { 81: halt(90), 82: halt(90), 83: halt(90) } }] };
  assert.match(stackAlert(x, [], sdoc, NOW.getTime()), /장기 가동중지 신고 — 평소 움직이던 배출구 4개 중 3개/);
  assert.equal(stackAlert(x, [], sdoc, NOW.getTime(), new Map(), maintenanceMemo([{ item_id: x.id, reason: '정기보수', created_at: new Date(NOW.getTime() - 86400000).toISOString() }])), null);
  // 11-12 기자 결정: '가동중지' 신고가 없어도 측정값 0만 사흘 넘게 이어진 배출구도 센다(KG스틸 당진 34번 — 11-04 19:00부터 값 0, 신고 없음)
  const obsOf = (n, v = 0, from = 80) => Array.from({ length: n }, (_, i) => [kst(from - i * 3), v]);
  const zx = { id: 'stk:down:KG스틸:케이지스틸(주) 당진공장:d', tier: 'B', watch: '굴뚝 측정(공장 가동 신호)', company: 'KG스틸', site: '케이지스틸(주) 당진공장' };
  const zdoc = (stacks, stopped, meaningful = 3) => ({ sites: [{ company: 'KG스틸', name: '케이지스틸(주) 당진공장', meaningful, stopped, stacks }] });
  const z34 = { stoppedSince: kst(190), longStopFor: kst(190), obs: obsOf(20) };
  const running = { obs: obsOf(20, 15) };
  assert.equal(stackAlert(zx, [], zdoc({ 6: halt(80), 34: z34, 7: running }, ['34', '6']), NOW.getTime()),
    "장기 멈춤 — 평소 움직이던 배출구 3개 중 2개가 사흘 넘게 멈춤('가동중지' 신고 1개 · 신고 없이 측정값 0만 1개: 34번)");
  assert.equal(stackAlert(zx, [], zdoc({ 34: z34, 35: { ...z34 }, 7: running }, ['34', '35']), NOW.getTime()),
    "장기 멈춤 — 평소 움직이던 배출구 3개 중 2개가 사흘 넘게 멈춤('가동중지' 신고 0개 · 신고 없이 측정값 0만 2개: 34번, 35번)");
  assert.equal(stackAlert(zx, [], zdoc({ 34: z34, 6: running, 7: running }, ['34']), NOW.getTime()), null);                    // 3개 중 1개
  assert.equal(stackAlert(zx, [], zdoc({ 34: z34, 6: running }, ['34'], 2), NOW.getTime()), null);                              // 2개 중 1개(지금 당진) — 절반을 넘지 않음
  // 세지 않는 것: 낮게 도는 배출구(0이 아님), 측정기 쪽 상태, 사흘이 안 된 멈춤(감시가 오래 멈춤으로 표시 안 함), 지금 멈춤 목록에 없는 배출구, 멈춘 뒤 숫자가 3번 안 됨
  const not = (st, stopped = ['34', '6']) => assert.equal(stackAlert(zx, [], zdoc({ 6: halt(80), 34: st, 7: running }, stopped), NOW.getTime()), null);
  not({ ...z34, obs: obsOf(20, 0.8) });
  for (const word of ['기기점검', '보수중', '미수신', '측정자료확인중']) not({ ...z34, status: [word, kst(100)] });
  not({ stoppedSince: kst(30), obs: obsOf(10, 0, 30) });
  not(z34, ['6']);
  not({ ...z34, obs: obsOf(2) });
  not({ ...z34, obs: [...obsOf(5), [kst(20), 0.3]] });                                                                           // 중간에 값이 돌아온 적 있음
  // 멈추기 전 숫자는 보지 않는다(멈춘 뒤 관측만), 숫자가 아닌 칸(null)은 건너뛴다
  assert.equal(zeroOnlyLongStop({ stoppedSince: kst(75), longStopFor: kst(75), obs: [[kst(90), 12.8], [kst(84), 13.1], [kst(72), 0], [kst(60), null], [kst(48), 0], [kst(24), 0]] }), true);
  assert.equal(zeroOnlyLongStop({ stoppedSince: kst(75), longStopFor: kst(75), status: ['가동중지', kst(70)], obs: obsOf(20) }), false);    // 신고가 있으면 신고 쪽에서 센다
  // 정기보수 메모가 있으면 이 경우도 알리지 않는다
  assert.equal(stackAlert(zx, [], zdoc({ 6: halt(80), 34: z34, 7: running }, ['34', '6']), NOW.getTime(), new Map(),
    maintenanceMemo([{ item_id: zx.id, reason: '정기보수', created_at: new Date(NOW.getTime() - 86400000).toISOString() }])), null);
  // kr_official 굴뚝 화면에 메모를 보인다
  const st = (await call('kr_official', { section: 'stacks' }, opts)).text;
  assert.match(st, /- 정기보수 메모\(기자 판정 — 이 기간 멈춤·빠짐 신호는 레이더에서 접음\) 1곳: 현대제철\(주\)순천공장 \d\d-\d\d '회사 확인\(기자\): 순천공장 정기 보수를 순차 진행 중' → \d\d-\d\d까지/);
});

test('굴뚝 겹친 신호 공장 이름 맞춤: 같은 시군의 다른 공장 이름은 증거 아님, 같은 공장 이름은 맞음 표시, 숫자뿐인 공장 이름은 무시', () => {
  assert.deepEqual(plantTokens('롯데케미칼㈜울산2공장'), ['울산2공장']);
  assert.deepEqual(plantTokens('㈜엘지화학 여수공장(용성1단지)'), ['여수공장', '용성1단지']);
  assert.deepEqual(plantTokens('기아 오토랜드 화성 PBV 2공장 증설'), []);
  assert.deepEqual(plantTokens('㈜포스코 포항제철소'), ['포항제철소']);
  const label = '굴뚝 측정(공장 가동 신호)';
  const x = { id: 'stk:down:롯데케미칼:롯데케미칼(주)울산2공장:d', tier: 'A', watch: label, company: '롯데케미칼', site: '롯데케미칼㈜울산2공장' };
  const g = (fact, watch = '지자체 고시·공고') => [{ place: '울산', items: [x, { id: 'o', tier: 'A', watch, company: '롯데케미칼', fact }] }];
  const doc = { sites: [{ company: '롯데케미칼', name: '롯데케미칼㈜울산2공장', meaningful: 3, stacks: {} }] };
  assert.equal(stackAlert(x, g('울주군 공고 「롯데케미칼 울산1공장 증설 공사」'), doc, Date.now()), null);   // 다른 공장
  assert.match(stackAlert(x, g('울주군 공고 「롯데케미칼 울산2공장 설비 철거」'), doc, Date.now()), /공장 이름까지 맞음/);
  assert.equal(stackAlert(x, g('롯데케미칼(울산광역시 남구) 국민연금 가입자 -40명', '사업장 인력(국민연금)'), doc, Date.now()), null);   // 11-08: 시군까지만 맞으면 아님
});

test('겹친 신호 공장별 묶음: 같은 시군의 다른 공장 이름은 따로, 회사 이름이 붙은 공장 이름은 같은 공장, 일반 낱말 공장은 무시', () => {
  assert.deepEqual(plantTokens('기아 화성 증설공장 착공'), []);
  assert.deepEqual(plantTokens('「금호타이어함평공장정련동외철근콘크리트공사」'), ['금호타이어함평공장']);
  assert.deepEqual(plantTokens('제2공장 신공장 새공장'), []);
  const it = (id, watch, fact, extra = {}) => ({ id, tier: 'B', tool: 'kr_official', watch, company: '롯데케미칼', date: '2026-11-04', fact, ...extra });
  const items = [it('s1', '굴뚝 측정(공장 가동 신호)', '롯데케미칼㈜울산2공장: 배출구 2개 멈춤'), it('l1', '지자체 고시·공고', '울주군 공고 「롯데케미칼 울산1공장 증설 공사」'),
    it('w1', '사업장 인력(국민연금)', '롯데케미칼(울산광역시 남구) 국민연금 가입자 -40명')];
  const parts = splitByPlant({ company: '롯데케미칼', place: '울산', items });
  assert.deepEqual(parts.map((g) => [g.plant, g.items.map((x) => x.id)]), [['울산2공장', ['s1', 'w1']], ['울산1공장', ['l1', 'w1']]]);
  const g = convergence(items, { cut: Date.parse('2026-11-03T15:00:00Z') });
  assert.deepEqual(g.map((x) => [x.plant, x.watches.length]), [['울산2공장', 2], ['울산1공장', 2]]);
  // 회사 이름이 붙어 뽑힌 공장 이름은 같은 공장
  const ham = [it('h1', '굴뚝 측정(공장 가동 신호)', '금호타이어㈜ 함평공장 배출구 멈춤', { company: '금호타이어' }), it('h2', '사업장 인력(국민연금)', '국민연금 공사 현장 「금호타이어함평공장정련동외철근콘크리트공사」', { company: '금호타이어' })];
  assert.equal(splitByPlant({ company: '금호타이어', place: '함평', items: ham }).length, 1);
  // 공장 이름이 한쪽에만 있으면 나누지 않는다
  assert.equal(splitByPlant({ company: '롯데케미칼', place: '울산', items: [items[0], items[2]] }).length, 1);
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
  // 11-01: 감시 도중 더한 회사의 첫 읽기(baseline: true)는 오래된 의견서라면 새 항목이 아니다
  await post('us-comments', { schema: 'us_comments/v1', generatedAt: '2026-10-22T08:20:00+09:00', checks: [], items: [
    { id: 'OLD-1', company: '기아', submitter: 'Kia America', agency: 'EPA', postedDate: '2026-05-01', firstSeen: '2026-10-20T08:20:00+09:00' },
    { id: 'USTR-1', company: '롯데케미칼', submitter: 'Lotte Chemical California, Inc.', agency: 'USTR', postedDate: '2026-06-03', firstSeen: '2026-10-25T08:20:00+09:00', baseline: true },
    { id: 'EPA-2', company: '현대차', submitter: 'Hyundai Motor Group', agency: 'EPA', postedDate: '2026-10-20', firstSeen: '2026-10-25T08:20:00+09:00' }] });
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
  assert.match(b, /Hyundai Motor Group → EPA 의견서/);
  assert.doesNotMatch(r.text, /Lotte Chemical California|Kia America → EPA/);
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
      // 공개 2026-10-07, 레이더가 처음 본 때 10-25 — 밀린 공개(KIPRIS 조회가 풀린 뒤 한꺼번에)라 C
      { id: 'p3', verdict: '미보도 후보', company: '현대제철', title: '상변태 기반 판재 냉각', kind: '특허', published: '2026-10-07', firstSeen: '2026-10-25T20:00:00+09:00' },
      { id: 'p4', verdict: '미보도 후보', company: '기아', title: '배터리 냉각판', kind: '특허', published: '2026-10-20', firstSeen: '2026-10-25T20:00:00+09:00' },
      { id: 'rc1', verdict: '미보도 후보', company: '기아', title: '기아, 10월 30일 리콜 공지 1건 — [기아] 쏘렌토 - 저압연료라인 어셈블리 관련 리콜', kind: '리콜' },
      // 11-02 운영: 새 출입처의 80일 전 반기보고서 표 숫자 — 첫 심사라 firstSeen은 오늘
      { id: 'st1', verdict: '미보도 후보', company: '금호석유화학', title: '금호석유화학 · 운 송/서비스 — 공식 2025→2026 동일기간·단위 숫자 4426 → 5577 (백만원)', kind: '단서',
        staleDays: 80, url: 'https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260814002302', firstSeen: '2026-10-26T07:10:00+09:00' }] });
  const r = await call('radar_today', {}, opts);
  const a = r.text.split('[A · ')[1].split('[B · ')[0];
  const b = r.text.split('[B · ')[1].split('[C · ')[0];
  assert.match(a, /ACME METALS: 8-K/);
  assert.doesNotMatch(a + b, /CLEVELAND-CLIFFS/);  // 위험 고지 문구 속 MOU 언급은 참고(C)
  assert.match(b, /HARTFORD INSURANCE GROUP: 8-K EX-99\.2 — 발췌에 계약·공급·합작 낱말 없음/);
  assert.match(b, /id p1/);  // 특허 공개 미보도 후보는 B(그 자체로 단독 아님, 10-31)
  assert.doesNotMatch(a, /고정자 냉각 장치/);
  assert.match(b, /고정자 냉각 장치 \(특허\) — 보도 대조 '미보도 후보' · 특허 공개만으로는 단독이 아님/);
  assert.match(b, /배터리 냉각판 \(특허\)/);   // 공개 5일 뒤 처음 봄 — B
  assert.doesNotMatch(b, /상변태 기반 판재 냉각/);
  assert.doesNotMatch(a + b, /운 송\/서비스/);  // 오래된 표 숫자는 A·B가 아니다
  const minor = await call('radar_today', { include_minor: true }, opts);
  assert.match(minor.text.split('[C · ')[1], /운 송\/서비스[^\n]* · 오래된 자료\(접수 80일 전 — 새 시점 고리 필요\)/);
  assert.match(minor.text.split('[C · ')[1], /상변태 기반 판재 냉각 \(특허\)[^\n]* · 공개 18일 뒤에 레이더가 처음 봄\(밀린 공개\)/);
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
  assert.deepEqual(dueAt(new Date('2026-10-26T22:40:05Z')), ['trade-remedy.yml', 'dart-beat-monitor.yml', 'governance-watch.yml']);        // Tue 07:40 KST
  assert.deepEqual(dueAt(new Date('2026-10-26T22:10:30Z')), ['scoop-screen.yml', 'trademark-watch.yml']);  // Tue 07:10 KST(상표는 실패한 회사만 재시도)
  assert.deepEqual(dueAt(new Date('2026-10-27T06:10:00Z')), ['scoop-screen.yml']);        // 15:10 KST
  assert.deepEqual(dueAt(new Date('2026-10-27T07:00:00Z')), []);                          // no slot (16:00 KST)
  assert.deepEqual(dueAt(new Date('2026-11-02T00:31:00Z')), ['union-notices.yml', 'g2b-tender-official.yml']);  // Mon 09:30 KST(GitHub 예약은 4.5~6시간 늦었다) + 노조 성명(매일)
  assert.deepEqual(dueAt(new Date('2026-11-01T00:30:00Z')), ['union-notices.yml']);       // Sun(노조 성명만 매일)
  assert.deepEqual(dueAt(new Date('2026-11-01T00:20:00Z')), ['kr-stacks.yml']);           // Sun 09:20 KST 굴뚝(주말 포함 3시간 칸)
  assert.deepEqual(dueAt(new Date('2026-11-01T15:25:00Z')), ['kr-stacks.yml']);           // Mon 00:20 KST
  assert.deepEqual(dueAt(new Date('2026-11-01T16:20:00Z')), []);                          // Mon 01:20 KST(3시간 칸 아님)
  assert.deepEqual(dueAt(new Date('2026-10-31T22:40:00Z')), ['dart-beat-monitor.yml']);   // Sun 07:40 KST — DART 공시 감시만(매일)
  assert.deepEqual(dueAt(new Date('2026-11-01T01:40:00Z')), ['dart-beat-monitor.yml']);   // Sun 10:40 KST 재시도 칸(직전 결과가 4시간 안이면 워크플로가 건너뜀)
  const opts = PRIVATE({ GITHUB_DISPATCH_TOKEN: 'ghp_test' });
  const seen = [];
  const fetchMock = async (url, init) => { seen.push({ url, init }); return new Response(null, { status: 204 }); };
  const res = await runSchedule(opts.env, new Date('2026-10-26T22:40:05Z'), { fetch: fetchMock });
  assert.deepEqual(res.map((e) => [e.workflow, e.status]), [['trade-remedy.yml', 'ok'], ['dart-beat-monitor.yml', 'ok'], ['governance-watch.yml', 'ok']]);
  assert.equal(seen[0].url, 'https://api.github.com/repos/shhong9173-art/seoul-reporting-radar/actions/workflows/trade-remedy.yml/dispatches');
  assert.equal(seen[0].init.headers.Authorization, 'Bearer ghp_test');
  assert.deepEqual(JSON.parse(seen[0].init.body), { ref: 'main' });
  const fail = await runSchedule(opts.env, new Date('2026-10-26T22:50:00Z'), { fetch: async () => new Response('{}', { status: 403 }) });
  assert.deepEqual(fail.map((e) => [e.workflow, e.status]), [['us-litigation.yml', 'HTTP 403'], ['kr-exec.yml', 'HTTP 403'], ['auto-desk.yml', 'HTTP 403']]);   // 07:50 칸(임원 명단 11-05) + 뉴스(50분)
  // 뉴스 수집은 20분마다(KST 매시 10·30·50분), 주말에도 — GitHub 예약 '*/15'가 하루 5번만 돌았다(10-31~11-01)
  assert.equal(newsDue(new Date('2026-11-01T01:10:30Z')), true);    // 일 10:10 KST
  assert.equal(newsDue(new Date('2026-11-01T01:20:00Z')), false);
  assert.equal(newsDue(new Date('2026-11-01T01:50:00Z')), true);
  const newsSeen = [];
  const sunday = await runSchedule(opts.env, new Date('2026-11-01T01:30:00Z'), { fetch: async (url) => { newsSeen.push(url); return new Response(null, { status: 204 }); } });
  assert.deepEqual(sunday.map((e) => [e.workflow, e.status]), [['auto-desk.yml', 'ok']]);
  assert.match(newsSeen[0], /workflows\/auto-desk\.yml\/dispatches$/);
  assert.deepEqual(await runSchedule(opts.env, new Date('2026-11-01T01:20:00Z'), { fetch: async () => { throw new Error('must not call'); } }), []);
  const none = PRIVATE();
  // Mon 2026-10-26 07:40 KST — the same KST day as the test clock (09:00 KST)
  const skipped = await runSchedule(none.env, new Date('2026-10-25T22:40:00Z'), { fetch: async () => { throw new Error('must not call'); } });
  assert.deepEqual(skipped.map((e) => e.status), ['no-token', 'no-token', 'no-token']);
  const today = await call('radar_today', {}, none);
  assert.match(today.text, /예약 요청\(Cloudflare\): 토큰 없음 — GitHub 예약만 사용 중\(지연 가능\) · 지금도 워커에서 GITHUB_DISPATCH_TOKEN이 보이지 않음/);
  // the reporter adds the secret after the morning slots: the line says so before the next slot comes round
  const later = await call('radar_today', {}, { ...none, env: { ...none.env, GITHUB_DISPATCH_TOKEN: 'ghp_test' } });
  assert.match(later.text, /예약 요청\(Cloudflare\): 오늘 앞선 칸은 토큰 없이 지나감 · 지금은 토큰 보임 — 다음 칸\(10-26 09:10 council-minutes\.yml\)부터 요청/);
  assert.equal(nextSlot(new Date('2026-10-30T10:00:00Z')), '10-30 19:10 india-filings.yml');  // Fri 19:00 KST → 19:10 인도 공시 칸(평일)
  assert.equal(nextSlot(new Date('2026-10-30T13:00:00Z')), '10-30 22:10 india-filings.yml');  // Fri 22:00 KST → 22:10 인도 공시 마지막 칸
  assert.equal(nextSlot(new Date('2026-10-30T13:15:00Z')), '10-31 00:20 kr-stacks.yml');  // Fri 22:15 KST → Sat 00:20(인도 공시 22:10 칸 뒤)
  assert.equal(nextSlot(new Date('2026-11-01T09:30:00Z')), '11-01 19:40 my-articles.yml');  // Sun 18:30 KST → 19:40 기자 기사 대조(매일, 11-03 추가)
  assert.equal(nextSlot(new Date('2026-11-01T10:45:00Z')), '11-01 20:40 dart-beat-monitor.yml');  // Sun 19:45 KST → 20:40 DART 재시도 칸
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

test('주간 점검: 즉시 알림 성적(보낸 id ↔ 판정), 킬이 몰린 감시에 사유·제안, 이미 바꾼 기준(굴뚝 11-04)은 바뀐 뒤 판정만 본다', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const recent = new Date(NOW.getTime() - 3600000).toISOString();
  const post = (feed, doc) => worker.fetch(new Request(ORIGIN + `/ingest/${feed}`, { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {});
  const day = new Date(NOW.getTime() + 9 * 3600000).toISOString().slice(0, 10);
  const lab = [1, 2, 3, 4, 5].map((i) => ({ id: `labor:04:2026조정${i}:${day}`, company: 'LG화학', commission: '충남', commissionName: '충남지방노동위원회', meeting: '조정회의', day, time: '15:00',
    caseNo: `2026조정${i}`, caseName: '주식회사 LG화학 노동쟁의 조정신청사건', tier: 'A', url: 'https://www.nlrc.go.kr/x', firstSeen: recent }));
  await post('kr-labor', { schema: 'kr_labor/v1', generatedAt: recent, status: 'complete', checks: [], counts: {}, seen: {}, notices: lab,
    events: lab.map((n) => ({ id: n.id, tier: 'A', kind: '노동위 조정 회의', company: 'LG화학', caseNo: n.caseNo, word: '노동쟁의', url: n.url, detectedAt: recent, text: `충남지방노동위원회 조정회의 ${n.caseNo}` })) });
  const stk = [1, 2, 3, 4, 5].map((i) => ({ id: `stk:longstop:현대제철:현대제철(주)순천공장:8${i},82:d`, kind: '배출구 오래 멈춤', tier: 'B', company: '현대제철', site: '현대제철㈜순천공장', text: `현대제철㈜순천공장: 배출구 ${i}`, detectedAt: recent }));
  await post('kr-stacks', { schema: 'kr_stacks/v1', generatedAt: recent, status: 'complete', baselineSince: '2026-10-01T00:00:00+09:00', checks: [], sites: [], events: stk });
  await call('candidate_feedback', { item_ids: lab.map((x) => x.id), verdict: '킬', reason: '조정 신청만으로는 약함' }, opts);
  await call('candidate_feedback', { item_ids: stk.map((x) => x.id), verdict: '킬', reason: '굴뚝 신호만' }, opts);
  await call('package_save', { name: `alert-${day.replaceAll('-', '')}`, state: '미발제·확인 필요', title: '단독 후보 즉시 알림',
    body: `[단독 후보 알림 10:45] 4건\n…\n보낸 id: ${stk[0].id}, ${lab[0].id}, ${lab[1].id}, ${lab[2].id}, ins:000249:20263030000212:72:1` }, opts);
  const r = (await call('candidate_weekly_review', {}, opts)).text;
  assert.match(r, /노동위 회의\(조정·심판\): 5개 중 킬 5 — 등급·문턱 점검 후보 · 킬 사유 '조정 신청만으로는 약함'\(5\) · 제안: 즉시 알림·아침 발제는 다른 감시와 겹칠 때만/);
  // 같은 감시에 기준을 두 번 바꿨으면(11-04·11-08) 가장 최근 것으로 센다
  assert.match(r, /굴뚝 측정\(공장 가동 신호\): 5개 중 킬 5 — 11-08에 기준을 이미 바꿈\(실시간 신호는 A 없음[^)]*\) · 바뀐 뒤 판정 0건\(킬 0\)이라 아직 판단 안 함/);
  assert.match(r, /\[즉시 알림 성적 · 최근 7일\] 알림 1일치 · 보낸 항목 5건 — 킬 4 · 판정 없음 1/);
  assert.match(r, /- 협력사 회생·파산 1 — 판정 없음 1/);   // 목록에 없는 id는 앞말로 감시를 짐작
  assert.match(r, /- 노동위 회의\(조정·심판\) 3 — 킬 3 · 제안: 이 감시 즉시 알림 기준 좁히기/);   // id 안 쉼표('8x,82')에도 4건으로 나눔
  assert.match(r, /- 굴뚝 측정\(공장 가동 신호\) 1 — 킬 1 · 11-08 기준 변경 뒤 보낸 것 0건/);
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
    ftcPress: [{ id: 'ftcpress:48163', title: '현대자동차 (주) 의 하도급법 위반행위 제재', kind: '보도', dept: '제조하도급과', date: '2026-10-24', companies: ['현대차'], related: [],
        isNew: true, url: 'https://www.ftc.go.kr/www/selectBbsNttView.do?bordCd=3&key=12&searchCtgry=01,02&nttSn=48163' },
      { id: 'ftcpress:48160', title: '정유 4사의 석유제품 가격 담합 제재', kind: '보도', dept: '카르텔조사국', date: '2026-10-24', companies: [], related: [],
        url: 'https://www.ftc.go.kr/www/selectBbsNttView.do?bordCd=3&key=12&searchCtgry=01,02&nttSn=48160' }],
    briefing: [{ id: 'briefing:156787100', title: '기아 등 5개사 12개 차종 3만 2천여 대 자발적 시정조치(리콜)', date: '2026-10-24', ministry: '국토교통부', companies: ['기아'],
        isNew: true, url: 'https://www.korea.kr/briefing/pressReleaseView.do?newsId=156787100' },
      { id: 'briefing:156787389', title: '2026년 수소발전 입찰시장 개설', date: '2026-10-24', ministry: '기후에너지환경부', companies: [],
        url: 'https://www.korea.kr/briefing/pressReleaseView.do?newsId=156787389' }],
    g2bAwards: [{ id: 'g2baward:R26BK01-000-1-0', kind: '물품', noticeNo: 'R26BK01-000', title: '다목적 방사광가속기 전력인입공사 관급자재(전력케이블 부속재) 구입', winner: '엘에스전선 주식회사',
        bizno: '1388147634', companies: ['LS전선'], related: [], amount: 2073720000, rate: '87.745', buyer: '충청북도', date: '2026-10-24', bidders: '5', big: true, isNew: true },
      { id: 'g2baward:R26BK02-000-1-0', kind: '물품', noticeNo: 'R26BK02-000', title: '수원시 장안구청 대형버스 교체 구입', winner: '현대자동차 주식회사', bizno: '1018109147',
        companies: ['현대차'], related: [], amount: 228480000, rate: '', buyer: '경기도 수원시 장안구', date: '2026-10-24', bidders: '', big: false }],
    province: [{ id: 'province:울산광역시:184850', site: '울산광역시', title: '울산시, 고려아연과 온산제련소 이차전지 소재 증설 투자협약', dept: '투자유치과',
        date: '2026-10-24', companies: ['고려아연'], isNew: true, url: 'https://www.ulsan.go.kr/u/rep/bbs/view.do?mId=001004003001000000&bbsId=BBS_0000000000000027&dataId=184850' }],
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
  const fp = await call('kr_signals', { section: 'ftc_press' }, opts);
  assert.match(fp.text, /\[공정위 보도·참고·설명자료 · 제목에 출입처 이름·출입 업종 낱말 · 최근 60일\] 2건/);
  assert.match(fp.text, /\[신규\] 2026-10-24 · 제조하도급과 · 보도\n   제목: 현대자동차 \(주\) 의 하도급법 위반행위 제재 · 출입처 이름: 현대차/);
  assert.doesNotMatch(fp.text, /\[한전 전자입찰|\[산업통상부 보도|\[공정위 의결서/);  // section only
  const bf = await call('kr_signals', { section: 'briefing' }, opts);
  assert.match(bf.text, /\[부처 보도자료\(정책브리핑 목록: 기후부·국토부·관세청·조달청\) · 제목에 출입처 이름·업종 낱말 · 최근 60일\] 2건/);
  assert.match(bf.text, /\[신규\] 2026-10-24 · 국토교통부\n   제목: 기아 등 5개사 12개 차종 3만 2천여 대 자발적 시정조치\(리콜\) · 출입처 이름: 기아/);
  const g2 = await call('kr_signals', { section: 'g2b' }, opts);
  assert.match(g2.text, /\[나라장터 낙찰 · 출입처가 낙찰자 · 낙찰일 최근 60일 · 금액 큰 순\] 2건/);
  assert.match(g2.text, /\[신규\] 2026-10-24 · 물품 · 엘에스전선 주식회사 · 큰 낙찰 · 2,073,720,000원\(약 20\.7억원\) · 낙찰률 87\.745%\n   공고: 「다목적 방사광가속기/);
  const pv = await call('kr_signals', { section: 'province' }, opts);
  assert.match(pv.text, /\[시·도 보도자료\(울산·충남·전남광주\) · 제목에 출입처 이름, 또는 투자협약·증설·위기\+업종 낱말 · 최근 60일\] 1건/);
  assert.match(pv.text, /\[신규\] 2026-10-24 · 울산광역시 · 투자유치과\n   제목: 울산시, 고려아연과 온산제련소 이차전지 소재 증설 투자협약 · 출입처 이름: 고려아연/);
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
  assert.match(b, /공정위 보도\(제조하도급과\): 현대자동차 \(주\) 의 하도급법 위반행위 제재/);  // beat name in an FTC release → B
  assert.doesNotMatch(a + b, /정유 4사의 석유제품 가격 담합/);  // industry word only → C
  assert.match(b, /국토교통부 보도자료: 기아 등 5개사 12개 차종/);  // beat name → B
  assert.match(b, /울산광역시 보도자료\(투자유치과\): 울산시, 고려아연과 온산제련소/);
  assert.match(b, /나라장터 물품 낙찰: 엘에스전선 주식회사 · 「다목적 방사광가속기/);  // 출입처 10억원 이상 → B
  assert.doesNotMatch(a + b, /대형버스 교체/);  // 관용차 소액 → C  // province release naming a beat company → B
  assert.doesNotMatch(a + b, /수소발전 입찰시장/);  // ministry topic word only → C
  assert.doesNotMatch(a + b, /롯데케미칼|배전용 변압기|재고 \+37\.3%/);  // body mention, small bid, stock move → C
  const minor = await call('radar_today', { include_minor: true }, opts);
  assert.match(minor.text, /「\(연간단가\)고효율주상변압기,50KVA\(광유\)-2,338대-0\d\(일반\)」 외 같은 공고 2건\(합계 약 149억원\) · 추정가격 약 50억원/);
  assert.equal((minor.text.match(/고효율주상변압기/g) ?? []).length, 1);  // three lots, one line
  assert.match(r.text, /기자 전용 감시 35개/);
  assert.deepEqual(dueAt(new Date('2026-10-26T23:30:00Z')), ['kr-signals.yml', 'kipris-patent-hunt.yml']);  // Tue 08:30 KST
  assert.deepEqual(dueAt(new Date('2026-10-27T06:20:00Z')), ['kr-signals.yml', 'kr-stacks.yml']);  // Tue 15:20 KST
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
    d('898800', 'C', 'Response', { onBehalfOf: 'First Solar, Inc.', why: '관련 일상 문서', securityLevel: 'Confidential' }),
    d('896718', 'B', 'Motion Response/Reply', { officialReceivedDate: '2026/10/05 16:35:00', firmOrganization: 'Covington & Burling LLP',
      onBehalfOf: `${'JinkoSolar Holding Co., Ltd., Jinko Solar Co., Ltd., '.repeat(5)}Hanwha Solutions Corporation, Hanwha Q CELLS USA, Inc.`,
      partyHits: ['Hanwha Solutions Corporation', 'Hanwha Q CELLS USA, Inc.'], companies: ['한화솔루션'] })];
  const ev = (x) => ({ id: `edis:${x.id}`, pageId: 'edis', country: '미국', tier: x.tier, label: `USITC ${x.investigationNumber} ${x.documentType}`,
    text: `${x.documentTitle} — 제출 ${x.firmOrganization} · ${x.why}`, companies: x.companies, url: x.url, detectedAt: recent });
  const doc = { schema: 'trade_remedy/v1', generatedAt: recent, status: 'partial', quotas: [], federalRegister: [], pages: [], rules: [],
    checks: [{ source: 'USITC EDIS 문서', status: 'ok', returned: 180, pages: 2, bodiesRead: 3 }],
    edis: { checkedAt: recent, baselineSince: '2026-11-02T07:40:00+09:00', docs, watched: { '337-1494': 'seed', '337-3900': '2026/11/02 14:00:00' },
      tokenNote: "EDIS 토큰 2026-11-14 만료 예정 — 'API Token Generator'에서 다시 발급해 GitHub 비밀값 EDIS_API_TOKEN 교체" },
    events: [ev(docs[0]), ev(docs[1]), ev(docs[2])] };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/trade-remedy', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const t = await call('trade_remedies', { section: 'edis' }, opts);
  assert.match(t.text, /\[미국 ITC 문서\(EDIS\) · 확인 [^\]]*\] A·B 4건 · 일상 C 1건 숨김\(show_all=true\) · 지켜보는 337 조사 337-1494, 337-3900/);
  assert.match(t.text, /⚠ EDIS 토큰 2026-11-14 만료 예정/);
  assert.ok(t.text.indexOf('337-3900 Complaint') < t.text.indexOf('337-1494 Notice'));  // A first
  assert.ok(t.text.indexOf('337-1494 Notice') < t.text.indexOf('337-1494 Petition'));  // then newest B
  assert.match(t.text, /제출 Sidley Austin LLP \(당사자 Hanwha Solutions Corporation; Hanwha Q CELLS USA, Inc\.\) · 출입처가 당사자인 서면 · 출입처 한화솔루션/);
  assert.match(t.text, /본문\(41쪽, 공개본 첫 첨부\) 발췌: "Respondents respectfully request[^"]*with prejudice\."/);
  assert.match(t.text, /본문 미확인\(첨부 없음\)/);
  assert.match(t.text, /원문: https:\/\/edis\.usitc\.gov\/data\/document\/898408 \(EDIS 문서 번호 898408\)/);
  assert.doesNotMatch(t.text, /First Solar/);
  assert.match(t.text, /제출 Covington & Burling LLP \(공동 당사자 \d+자 중 출입처: Hanwha Solutions Corporation; Hanwha Q CELLS USA, Inc\.\)/);
  const all = await call('trade_remedies', { section: 'edis', show_all: true }, opts);
  assert.match(all.text, /C \[신규\] · 접수 2026\/10\/21 16:30 · 337-1494 Response[\s\S]*비공개 문서 — 본문 없음/);
  const q = await call('trade_remedies', { section: 'edis', company: 'Hanwha' }, opts);
  assert.match(q.text, /A·B 2건/);
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
        { dealNear: false }),
      // 11-04 운영: 이미 있던 거래를 다시 적은 정기 보고서가 A였다(Rhythm 10-Q 2024-01-04 계약, Aptiv 10-Q 08-14 투자). 새 계약 개정을 알린 실적 자료는 A 그대로
      ed('r1', 'RHYTHM PHARMACEUTICALS, INC.  (RYTM)', '3. Asset Acquisitions LG Chem, Ltd. On January 4, 2024, the Company entered into a license agreement and share issuance agreement with Hyundai Motor Company,',
        { dealNear: true, title: '10-Q 10-Q', date: '2026-10-25' }),
      ed('a1', 'Aptiv PLC  (APTV)', 'Motional Joint Venture Funding and Ownership Restructuring Transactions On August 14, 2026, Hyundai Motor Group ("Hyundai") invested approximately $ 250 million in Motional',
        { dealNear: true, title: '10-Q 10-Q', date: '2026-10-25' }),
      ed('r2', 'RHYTHM PHARMACEUTICALS, INC.  (RYTM)', '-- Rhythm and Hyundai Motor Company amend bivamelagon licensing agreement -- -- Five-year term loan facility secured',
        { dealNear: true, title: '8-K EX-99.1', date: '2026-10-25' }),
      ed('p1', 'POWERBANK Corp  (PBK)', 'm the Company a total of four ground-mount solar power projects (the "Qcells Projects"). Qcells is a subsidiary of Hyundai Motor Company. agreement',
        { dealNear: true, title: '20-F 20-F', date: '2026-10-25' })],
    confirmedScoops: 0 };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/partner-filings', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const r = await call('radar_today', { include_minor: true, limit: 60 }, opts);
  const sec = (t) => r.text.split(`[${t} · `)[1].split(/\n\[[ABC] · /)[0];
  assert.match(sec('A'), /CELL MAKER INC/);
  assert.match(sec('B'), /KT CORP: 6-K EX-99\.1 — 재무제표 주석/);
  assert.match(sec('C'), /HARTFORD INSURANCE GROUP: 6-K EX-99\.1 — 투자 보유 목록/);
  assert.doesNotMatch(sec('A'), /KT CORP|HARTFORD|NEXA|MINER/);
  assert.match(sec('B'), /RHYTHM PHARMACEUTICALS, INC\.  \(RYTM\): 10-Q 10-Q — 발췌의 거래 날짜 2024-01-04\(공시일보다 45일 넘게 전\) — 이미 있던 거래를 다시 적은 것일 수 있음/);
  assert.match(sec('B'), /Aptiv PLC  \(APTV\): 10-Q 10-Q — 발췌의 거래 날짜 2026-08-14/);
  assert.match(sec('B'), /POWERBANK Corp  \(PBK\): 20-F 20-F — 정기 보고서 속 서술\(날짜 없음 — 새 내용인지 원문 확인\)/);
  assert.match(sec('A'), /RHYTHM PHARMACEUTICALS, INC\.  \(RYTM\): 8-K EX-99\.1/);
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
  assert.deepEqual(dueAt(new Date('2026-10-28T08:40:00Z')), ['earnings-compare.yml', 'assembly-bills.yml', 'dart-beat-monitor.yml']);  // Wed 17:40 KST(실적 업종 비교 11-04 추가)
});

test('trademarks: weekly filings grouped by name, new names in core classes are B, waits are not failures and radar_today keeps them a week', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const filing = (company, title, date, classes, extra = {}) => ({ id: `tm:${company}:${title.toLowerCase().replace(/\W/g, '')}:${date.replace(/-/g, '')}`, company, related: false, title,
    applicationDate: date, applicationNumbers: classes.map((c, i) => `40202601${c}${String(i).padStart(3, '0')}`), newNumbers: [], classes, coreClasses: classes.filter((c) => ['12', '09'].includes(c)),
    statuses: ['출원'], agent: '대리인', applicants: '현대자동차주식회사', isNew: false, titleNew: false, tier: null, firstSeen: '2026-10-19T07:10:00+09:00', ...extra });
  const doc = { schema: 'trademarks/v1', generatedAt: '2026-10-26T07:10:00+09:00', source: 'KIPRIS Plus 상표 출원 속보(getAdvancedSearch)', status: 'partial',
    window: { from: '2026-07-28', to: '2026-10-26', field: '출원일' }, baselineSince: '2026-10-19T07:10:00+09:00',
    retry: { at: '2026-10-27T07:10:12+09:00', companies: ['영풍'] },
    eu: { source: 'EUIPO', generatedAt: '2026-10-26T07:10:30+09:00', status: 'partial', window: { from: '2026-06-28', to: '2026-10-26' }, blocked: null,
      checks: [{ company: '현대자동차', status: 'ok', rawTotal: 3, kept: 2 }, { company: '포스코', status: 'ok', rawTotal: 0, kept: 0 }, { company: 'LG화학', status: 'failed', error: 'HTTP 500' }],
      filings: [{ id: 'euipo:019000002', company: '현대자동차', applicationNumber: '019000002', title: 'AERO DRIVE', applicationDate: '2026-10-20', classes: ['12', '35'],
        coreClasses: ['12'], status: 'RECEIVED', applicants: ['Hyundai Motor Company'], firstSeen: '2026-10-26T07:10:30+09:00', isNew: true, titleNew: true, tier: 'B',
        url: 'https://euipo.europa.eu/eSearch/#details/trademarks/019000002' }] },
    checks: [{ source: '상표 현대자동차', status: 'ok', rawTotal: 4, kept: 4, filings: 3, requests: 1 },
      { source: '상표 KG모빌리티', status: 'ok', rawTotal: 0, kept: 0, filings: 0, requests: 1, nameVerified: false },
      { source: '상표 포스코', status: 'waiting', reason: 'provider_22_cooldown', until: '2026-10-29T07:10:00+09:00' },
      { source: '상표 영풍', status: 'ok', rawTotal: 1, kept: 0, filings: 0, requests: 1, otherApplicants: 1, note: '응답 1건은 이름 일부만 같은 다른 출원인(영풍제약 주식회사) — 이 회사 출원 없음' }],
    filings: [filing('현대자동차', 'AERO DRIVE', '2026-10-20', ['12', '35'], { isNew: true, titleNew: true, tier: 'B', firstSeen: '2026-10-26T07:10:00+09:00' }),
      filing('현대자동차', 'NUTRIMACY', '2026-09-10', ['07', '09', '12'], { isNew: true, tier: 'C', addedClassesAt: '2026-10-26T07:10:00+09:00' }),
      filing('현대자동차', 'PLEOS', '2026-08-01', ['09']),
      filing('현대자동차', 'OLDNEW', '2026-10-01', ['12'], { isNew: true, titleNew: true, tier: 'B', firstSeen: '2026-10-12T07:10:00+09:00' })],
    fresh: [], seen: {}, titles: {},
    kipris: { month: '2026-10', counted: 40, monthlyLimit: 900, groupUsed: { patent: 30, trademark: 10, diagnostic: 0 }, groupLimits: { patent: 730, trademark: 150, diagnostic: 20 } },
    rules: ['상표 출원은 출원 사실이다. 제품 출시·사업 진출·차명 확정이 아니다(방어 출원·예비 출원이 흔함).'], confirmedScoops: 0 };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/trademarks', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const t = await call('trademarks', {}, opts);
  assert.match(t.text, /이름 일부만 같은 다른 출원인만 나온 곳\(이 회사 0건\): 영풍\(영풍제약 주식회사\)/);
  assert.match(t.text, /평일 재시도 10-27T07:10: 영풍 — 월요일에 실패·대기한 회사만 다시 조회/);
  assert.match(t.text, /\[유럽 상표 출원\(EUIPO\) · 출원일 2026-06-28~2026-10-26 · 확인 2026-10-26T07:10\] 조회 정상 2\/3/);
  assert.match(t.text, /미확인\(0건 아님\): LG화학\(HTTP 500\)\n검색 0건\(영문 출원인 이름 형식 확인\): 포스코/);
  assert.match(t.text, /- \[B · 처음 보는 이름\] 현대자동차 · 「AERO DRIVE」 · 출원 2026-10-20 · 12류\(차량·부품\), 35류\(광고·사업관리\) · 출원번호 019000002 · 출원인 Hyundai Motor Company/);
  assert.match(t.text, /조회 정상 3\/4 · 대기 1곳\(제공기관 응답 22 뒤 72시간 대기, 2026-10-29T07:10부터 재시도\)/);
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
  assert.match(r.text, /기자 전용 감시 35개/);
  assert.match(r.text, /- 상표 출원: 대기 1곳\(제공기관 응답 22 뒤 72시간 대기\) — 해당 부분 0건은 미확인/);
  assert.doesNotMatch(r.text, /상표 출원: [^\n]*시간 전 결과/);
  const b = r.text.split('[B · ')[1].split('[C · ')[0];
  assert.match(b, /상표 출원 · 현대자동차\n   상표 출원 「AERO DRIVE」 12류\(차량·부품\), 35류\(광고·사업관리\) — 감시 시작 이후 처음 보는 이름 \(출원 2026-10-20, 출원번호 [0-9]+ 외 1\)/);
  assert.doesNotMatch(r.text, /OLDNEW/);  // first seen two weeks ago: off the digest
  assert.match(b, /유럽연합\(EUIPO\) 상표 출원 「AERO DRIVE」 12류\(차량·부품\), 35류\(광고·사업관리\) — 감시 시작 이후 처음 보는 이름 \(출원 2026-10-20, 출원번호 019000002, 출원인 Hyundai Motor Company\)/);
  const minor = await call('radar_today', { include_minor: true }, opts);
  assert.match(minor.text, /상표 출원 「NUTRIMACY」[^\n]* — 같은 이름 상품류 추가/);
  // 11-09: EUIPO 운영 검색이 막힌 동안 Signa(2차 원천)로 대신 읽은 유럽 출원 — 원천·남은 크레딧·원문 확인·마드리드 지정 표시
  {
    const s = JSON.parse(JSON.stringify(doc));
    s.generatedAt = '2026-10-26T07:20:00+09:00';
    Object.assign(s.eu, { generatedAt: '2026-10-26T07:20:30+09:00', status: 'partial', blocked: '상품 구독 운영 승인 대기(403 access-forbidden)', provider: 'signa',
      providerNote: 'Signa(EUIPO 자료를 매일 맞추는 2차 원천)', signaCreditsLeft: 10390,
      checks: [{ company: '현대자동차', status: 'ok', rawTotal: 3, kept: 2, via: 'signa' }, { company: '포스코', status: 'ok', rawTotal: 1, kept: 1, via: 'signa' },
        { company: 'LG화학', status: 'waiting', reason: 'Signa 크레딧 부족(남은 20) — 다음 달 초기화 뒤', via: 'signa' }] });
    s.eu.filings = [{ ...s.eu.filings[0], via: 'signa' }, { id: 'euipo:W11481965', company: '포스코', applicationNumber: 'W11481965', title: 'PosZET', applicationDate: '2026-10-22',
      classes: ['06', '12'], coreClasses: ['06'], status: 'UNDER_EXAMINATION', applicants: ['POSCO Co.'], firstSeen: '2026-10-26T07:20:30+09:00', isNew: true, titleNew: true,
      tier: 'B', via: 'signa', route: '마드리드 지정', url: 'https://euipo.europa.eu/eSearch/#details/trademarks/W11481965' }];
    assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/trademarks', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(s) }), env, {})).status, 200);
    const st = (await call('trademarks', {}, opts)).text;
    assert.match(st, /원천: EUIPO 직접 조회는 구독 승인 대기 — Signa\(EUIPO 자료를 매일 맞추는 2차 원천\)로 대신 읽음 2곳 · 남은 크레딧 10390 — 2차 자료라 기사 전 EUIPO eSearch 원문\(출원번호\) 확인/);
    assert.doesNotMatch(st, /대기: 상품 구독 운영 승인 대기/);
    assert.match(st, /미확인\(0건 아님\): LG화학\(Signa 크레딧 부족\(남은 20\) — 다음 달 초기화 뒤\)/);
    assert.match(st, /「PosZET」 · 출원 2026-10-22 · [^\n]* · 출원번호 W11481965\(마드리드 지정\) · 출원인 POSCO Co\. · 상태 UNDER_EXAMINATION · Signa/);
    assert.match(st, /Signa 2차 자료 — 불완전·부정확할 수 있음[^\n]*마드리드 지정의 출원일은 유럽 지정일이다/);
    const sb = (await call('radar_today', {}, opts)).text;
    assert.match(sb, /유럽연합\(EUIPO\) 상표 출원 「PosZET」[^\n]*\(출원 2026-10-22\(마드리드 지정\), 출원번호 W11481965, 출원인 POSCO Co\.\) · Signa 2차 자료 — EUIPO eSearch 원문 확인/);
    // 미국(USPTO, Signa 경유) 구역 — 'us' 칸, 크레딧 아끼려 이번 주 안 물은 곳 표시
    s.generatedAt = '2026-10-26T07:30:00+09:00';
    s.us = { source: 'USPTO 상표 출원(Signa 경유)', office: 'US', generatedAt: '2026-10-26T07:30:30+09:00', status: 'complete', window: { from: '2026-06-28', to: '2026-10-26' },
      provider: 'signa', providerNote: 'Signa(USPTO 자료를 매일 맞추는 2차 원천)', signaCreditsLeft: 2500, carried: ['포스코'],
      checks: [{ company: '현대자동차', status: 'ok', rawTotal: 5, kept: 5, via: 'signa' }, { company: '포스코', status: 'ok', rawTotal: 2, kept: 1, via: 'signa', carried: true },
        { company: 'LG화학', status: 'ok', rawTotal: 0, kept: 0, via: 'signa' }],
      filings: [{ id: 'uspto:50141613', company: '현대자동차', applicationNumber: '50141613', title: 'GENESIS BOX BUGGY', applicationDate: '2026-10-02', classes: ['28'],
        coreClasses: [], status: 'NEW_APPLICATION', applicants: ['HYUNDAI MOTOR COMPANY'], firstSeen: '2026-10-26T07:30:30+09:00', isNew: true, titleNew: true, tier: 'C', via: 'signa',
        url: 'https://tsdr.uspto.gov/#caseNumber=50141613&caseType=SERIAL_NO&searchType=statusSearch' }] };
    assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/trademarks', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(s) }), env, {})).status, 200);
    const us = (await call('trademarks', {}, opts)).text;
    assert.match(us, /\[미국 상표 출원\(USPTO · Signa 경유\) · 출원일 2026-06-28~2026-10-26 · 확인 2026-10-26T07:30\] 조회 정상 3\/3/);
    assert.match(us, /원천: USPTO 직접 API\(ID\.me 인증 실패\)는 막힘 — Signa\(USPTO 자료를 매일 맞추는 2차 원천\)로 읽음 2곳 · 크레딧 아끼려 이번 주 안 물음 1곳\(직전 결과\) · 남은 크레딧 2500 — 2차 자료라 기사 전 USPTO TSDR 원문\(일련번호\) 확인/);
    assert.match(us, /\[새로 본 미국 출원\] 1건\n- \[C · 처음 보는 이름\] 현대자동차 · 「GENESIS BOX BUGGY」 · 출원 2026-10-02 · 28류/);
    assert.match(us, /검증 상태: USPTO 공개 출원 정보\(자동 수집, Signa 2차 자료/);
    assert.match(us, /출원일 창 안 0건: LG화학 — 이름은 11-09 탐침으로 확인\(2년 안 출원이 있던 곳은 최근 출원이 없는 것, 0건 확정은 아님\)/);   // Signa 0건(11-10)
    assert.doesNotMatch(us.slice(us.indexOf('[미국 상표 출원')), /영문 출원인 이름 형식 확인/);
    const minorUs = (await call('radar_today', { include_minor: true }, opts)).text;
    assert.match(minorUs, /미국\(USPTO\) 상표 출원 「GENESIS BOX BUGGY」 28류[^\n]* — 감시 시작 이후 처음 보는 이름 \(출원 2026-10-02, 일련번호 50141613, 출원인 HYUNDAI MOTOR COMPANY\) · Signa 2차 자료 — USPTO TSDR 원문 확인/);
  }
  const list = await rpc('tools/list', {}, { path: `/mcp/${TOKEN}`, env });
  assert.ok(list.body.result.tools.some((x) => x.name === 'trademarks'));
  assert.match(list.body.result.tools.find((x) => x.name === 'radar_today').description, /감시 35개\([^)]*상표 출원, 해외 특허 공개\(EP·WO\), 국회 법안, 미국 리콜, 미국 EPA 인증, 국내 연비 신고, 해외 발주처 낙찰, 협력사 회생·파산, 전기위·원안위, 공장 부지 건축허가, 해외 법인 등기, 지자체 고시·공고, 사업장 인력, 굴뚝 측정, 노동위 회의, 노조 성명, 지방의회 회의록, 인도 법인 공시, 타사 공시 속 출입처, 지분·자사주 변동, 임원 명단 변화, 수시 임원 공시·타사 임원 명단, 문제 임원 점검, 출입처 외신\)/);
  assert.ok(!(await rpc('tools/list', {}, { env })).body.result.tools.some((x) => x.name === 'trademarks'));  // private only
});

test('patents_abroad: EPO OPS EP·WO publications are private, families grouped, throttle stops shown as unverified, radar_today lists them as C', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const pub = (id, country, date, title, extra = {}) => ({ id, country, number: id.slice(2, -2), kind: id.slice(-2), date, title, titleLang: 'en',
    applicants: ['HYUNDAI MOTOR CO LTD', 'Hyundai Motor Company', '현대자동차주식회사'], ipc: ['B60L 53/80', 'H01M 50/204'], applicationDate: '2025-04-30',
    priority: { number: 'KR20240123456', date: '2024-05-02' }, family: '90001', companies: ['현대자동차', '기아'], firstSeen: '2026-11-14T06:40:00+09:00', isNew: true,
    url: `https://worldwide.espacenet.com/patent/search?q=pn%3D${id}`, ...extra });
  const doc = { schema: 'epo_patents/v1', generatedAt: '2026-11-14T06:40:00+09:00', status: 'partial', source: 'EPO OPS 3.2',
    window: { to: '2026-11-14', field: '공개일', firstDays: 120, weeklyDays: 35 }, baselineSince: '2026-11-07T06:40:00+09:00',
    baselinedCompanies: ['현대자동차', '기아', '포스코'],
    throttle: { state: 'overloaded', search: 'black', perMinute: 0, stopped: 'EPO 검색 black(서버 overloaded) — 공정 이용 규칙상 이번 실행 멈춤' },
    checks: [{ company: '현대자동차', status: 'ok', total: 3, got: 3, matched: 3 }, { company: '기아', status: 'ok', total: 3, got: 3, matched: 3 },
      { company: '포스코', status: 'ok', total: 2, got: 2, matched: 1, otherApplicants: ['POSCO FUTURE M CO., LTD.'] }, { company: 'KG모빌리티', status: 'ok', total: 0, got: 0, matched: 0 },
      { company: 'LG화학', status: 'waiting', reason: 'EPO 검색 black(서버 overloaded) — 공정 이용 규칙상 이번 실행 멈춤' }],
    filings: [pub('EP4567890A1', 'EP', '2026-11-11', 'WIRELESS CHARGING PAD FOR ELECTRIC VEHICLE'),
      pub('WO2026200000A1', 'WO', '2026-11-12', 'WIRELESS CHARGING PAD FOR ELECTRIC VEHICLE'),
      pub('EP4000001A1', 'EP', '2026-09-02', 'OLD BASELINE SEAT', { isNew: false, family: '90002', firstSeen: '2026-11-07T06:40:00+09:00' }),
      pub('WO2026111111A1', 'WO', '2026-11-12', 'HOT-ROLLED STEEL SHEET', { family: '90003', companies: ['포스코'], applicants: ['POSCO Co., Ltd'], ipc: ['C22C 38/02'], priority: null })],
    fresh: ['EP4567890A1', 'WO2026200000A1', 'WO2026111111A1'], seen: [], rules: ['특허 공개는 출원 뒤 약 18개월(또는 조기 공개)에 나오는 공보다. 개발 완료·양산·사업 진출이 아니다.'], confirmedScoops: 0,
    krLinks: { linked: 1, krOutside: 1, krPct: 0, pct: 0, abroad: 1, none: 0, kiprisDocs: 994, newField: 1, at: '2026-11-14T06:40:00+09:00' },
    ipcHistorySince: '2026-07-17', newFieldFrom: '2027-01-13' };
  // 국내 공개 연결(11-10): 현대차 패밀리 WO는 KIPRIS 감시의 국내 공개와 이어짐, EP는 우선권만, 포스코 WO는 해외 우선권 + 처음 보는 기술 분야
  doc.filings[1].kr = { applicationNumber: '1020240123456', publicationNumber: '1020260159700', publicationDate: '2026-11-05', title: '전기차용 무선 충전 패드', company: '현대자동차', status: '공개' };
  doc.filings[0].krPriority = '1020240123456';
  Object.assign(doc.filings[3], { priorities: [{ number: 'US202563123456', date: '2025-03-01', country: 'US' }], priorityAbroad: ['US'], newField: { 포스코: ['C25B'] }, ipc: ['C25B 1/04'] });
  const at = { ...opts, now: new Date('2026-11-14T00:00:00Z') };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/epo-patents', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const t = (await call('patents_abroad', {}, at)).text;
  assert.match(t, /조회 정상 4\/5 · 대기 1곳\(EPO 검색 black\(서버 overloaded\) — 공정 이용 규칙상 이번 실행 멈춤\) — 같은 주말 재시도 칸/);
  assert.match(t, /EPO 서버 신호\(마지막 응답\): overloaded · 검색 black\(분당 0\)/);
  assert.match(t, /이름 낱말만 같은 다른 출원인\(걸러 냄\): 포스코\(POSCO FUTURE M CO\., LTD\.\)/);
  assert.match(t, /조회 창 안 공개 0건: KG모빌리티 \(조회는 정상/);
  assert.match(t, /\[새로 본 공개 · 최근 30일\] 3건/);
  assert.match(t, /국내 공개 연결\(저장된 공개 전체, 11-14 06:40\): 레이더 특허 감시\(KIPRIS\)와 이어짐 1 · 국내 우선권이지만 레이더 창 밖 1 · 한국 특허청 PCT 0 · 다른 수리관청 PCT 0 · 외국 출원 우선권 1 · 우선권 없음 0 \(KIPRIS 감시 문서 994건/);
  assert.match(t, /기술 분야 이력: 2026-07-17부터 쌓는 중 — 2027-01-13부터 '처음 보는 기술 분야' 표시/);
  assert.match(t, /- \[새 공개\] 현대자동차·기아 · 「전기차용 무선 충전 패드」\(국내 공개 제목\) · 영문 「WIRELESS CHARGING PAD FOR ELECTRIC VEHICLE」/);
  assert.match(t, /   국내 공개: 1020260159700\(2026-11-05, 공개\) · 출원 1020240123456 — 레이더 특허 감시\(KIPRIS\)에도 있음\(현대자동차\)/);
  assert.match(t, /- \[새 공개\] \[처음 보는 기술 분야\] 포스코 · 「HOT-ROLLED STEEL SHEET」/);
  assert.match(t, /⚑ 외국 출원 우선권\(US\) — 국내 출원 없이 해외에서 먼저 냈을 수 있음/);
  assert.match(t, /⚑ 처음 보는 기술 분야: 포스코 C25B 1\/04\(전기분해\(수소\)\)|⚑ 처음 보는 기술 분야: 포스코 C25B/);
  assert.match((await call('patents_abroad', { query: '무선 충전' }, at)).text, /WIRELESS CHARGING PAD/);
  assert.doesNotMatch((await call('patents_abroad', { link: 'kr' }, at)).text, /HOT-ROLLED/);
  assert.match((await call('patents_abroad', { link: 'abroad' }, at)).text, /HOT-ROLLED/);
  assert.match((await call('patents_abroad', { link: 'new_field' }, at)).text, /\] 1건/);
  // EP와 WO 같은 패밀리는 한 묶음
  assert.match(t, /- \[새 공개\] 현대자동차·기아 · 「전기차용 무선 충전 패드」\(국내 공개 제목\) · 영문 「WIRELESS CHARGING PAD FOR ELECTRIC VEHICLE」\n   WO2026200000A1\(국제특허\(PCT·WO\) 공개 2026-11-12\) · EP4567890A1\(유럽특허\(EP\) 공개 2026-11-11\)/);
  assert.equal((t.match(/WIRELESS CHARGING PAD/g) ?? []).length, 1);
  assert.match(t, /IPC B60L 53\/80\(전기차 동력·충전\), H01M 50\/204\(전지\) · 출원 2025-04-30 · 우선권 KR20240123456\(2024-05-02\)/);
  assert.match(t, /원문: https:\/\/worldwide\.espacenet\.com\/patent\/search\?q=pn%3DWO2026200000A1/);
  assert.doesNotMatch(t, /OLD BASELINE SEAT/);
  assert.match((await call('patents_abroad', { show_all: true, days: 120 }, at)).text, /OLD BASELINE SEAT/);
  assert.doesNotMatch((await call('patents_abroad', { company: '포스코' }, at)).text, /WIRELESS/);
  assert.match((await call('patents_abroad', { query: 'C25B' }, at)).text, /HOT-ROLLED STEEL SHEET/);
  assert.doesNotMatch((await call('patents_abroad', { office: 'EP' }, at)).text, /HOT-ROLLED/);
  const r = (await call('radar_today', { include_minor: true }, at)).text;
  assert.match(r, /- 해외 특허 공개\(EP·WO\): 대기 1곳\(EPO 검색 black/);
  assert.equal((r.match(/WIRELESS CHARGING PAD/g) ?? []).length, 1);   // 패밀리 한 줄
  // 패밀리 한 줄 — 국내 공개와 이어진 WO를 대표로 한글 제목을 앞에, 묶인 공개번호를 함께
  assert.match(r, /국제특허\(PCT·WO\) 공개 「전기차용 무선 충전 패드」\(영문 「WIRELESS CHARGING PAD FOR ELECTRIC VEHICLE」\) \(공개 2026-11-12, EP4567890A1·WO2026200000A1, IPC B60L 53\/80·H01M 50\/204, 국내 공개 1020260159700\(2026-11-05\)\)/);
  // 처음 보는 기술 분야는 B(확인할 변화), 해외 우선권 표시
  assert.match(r.split('[C · ')[0], /국제특허\(PCT·WO\) 공개 「HOT-ROLLED STEEL SHEET」 \(공개 2026-11-12, WO2026111111A1, IPC C25B 1\/04, 외국 출원 우선권\(US\) — 국내보다 해외 먼저일 수 있음\) · 처음 보는 기술 분야\(이력 2026-07-17부터\): 포스코 C25B — 새 사업 단서일 뿐 진출 확정 아님/);
  const list = await rpc('tools/list', {}, { path: `/mcp/${TOKEN}`, env });
  assert.ok(list.body.result.tools.some((x) => x.name === 'patents_abroad'));
  assert.ok(!(await rpc('tools/list', {}, { env })).body.result.tools.some((x) => x.name === 'patents_abroad'));  // 약관 3.2: 공개 연결엔 없음
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
      channels: { naver: { status: 'ok', returned: 3 } }, firstVerdict: '미보도 후보', firstCheckedAt: '2026-10-25T18:50:00+09:00', recheck: true },
    { id: 'cl:7', verdict: '미보도 후보', since: '2026-10-20', queries: ['LS일렉트릭 항소', 'LS일렉트릭 항소 특허'],
      evidence: [{ date: '2026-10-24', channel: 'naver', title: '전력기기 업계 美 소송 잇따라', url: 'https://n/2', why: '본문에만 회사·낱말(항소, 특허) — 제목 불일치, 같은 사건 가능성 낮음' },
        { date: '2026-10-23', channel: 'bing', title: 'LS일렉트릭, ESS 특허 폭증', url: 'https://n/4', why: '제목에 회사·낱말(특허)이 있으나 PTAB 없음 — 다른 사업장·다른 건 기사일 수 있음' },
        { date: '2026-08-02', channel: 'naver', title: 'LS일렉트릭, 美 특허심판원 결정 불복', url: 'https://n/3', before: true, why: '항목 날짜보다 앞선 기사(항소) — 판정에 안 셈' }],
      channels: { naver: { status: 'ok', returned: 0 }, bing: { status: 'ok', returned: 0 }, google: { status: 'ok', returned: 0 } } },
    { id: 'fac:1:x', verdict: '미확인', since: '2026-10-22', queries: ['KG스틸 인력'], evidence: [], checkedAt: '2026-10-23T12:50:00+09:00',
      channels: { naver: { status: 'failed', error: 'ConnectTimeout' }, bing: { status: 'ok', returned: 0 } } }] });
  const r = await call('radar_today', {}, opts);
  const a = r.text.split('[A · ')[1].split('[B · ')[0];
  assert.match(a, /\(보도 대조 자동 10-26 08:50: 미보도 후보 1 · 관련 보도 있음 1 · 미확인 1 · 대조 안 함 1 — 미보도 후보부터\)/);
  const order = ['In re: LS Electric', 'KG스틸', 'SeAH Steel'].map((w) => a.indexOf(w));
  assert.ok(order.every((i) => i > 0) && order[0] < order[1] && order[1] < order[2], a);
  assert.match(a, /보도 대조\(자동 10-26 08:50\): 미보도 후보 — "LS일렉트릭 항소", "LS일렉트릭 항소 특허"로 2026-10-20 이후 관련 기사 못 찾음\(검색 범위 결과, 단독 판정 아님\)/);
  assert.match(a, /보도 대조\(자동 10-26 08:50\): 관련 보도 있음 — "세아제강 국제무역법원", "세아제강 국제무역법원 소송" · 처음\(10-25 18:50\) 미보도 후보 · 대조 규칙이 바뀌어 72시간 지난 뒤 다시 봄/);
  assert.match(a, /↳ 2026-10-25 \[naver\] 세아제강, 美 국제무역법원에 반덤핑 소송 https:\/\/n\/1\n/);
  assert.match(a, /↳ 2026-10-24 \[naver\] 전력기기 업계 美 소송 잇따라 https:\/\/n\/2 \(약한 근거: 본문에만, 제목 불일치\)/);
  // must가 없는 근거(10-31 퍼스트솔라 ↔ '한화솔루션 특허 폭증')도 꼬리표
  assert.match(a, /↳ 2026-10-23 \[bing\] LS일렉트릭, ESS 특허 폭증 https:\/\/n\/4 \(약한 근거: PTAB 없음 — 다른 건일 수 있음\)/);
  // 판정에 안 세는 앞선 기사(10-31): 미보도 후보에 맥락 한 줄
  assert.match(a, /↳ 2026-08-02 \[naver\] LS일렉트릭, 美 특허심판원 결정 불복 https:\/\/n\/3 \(앞선 기사: 항목 날짜 전이라 판정에 안 셈 — 같은 사업의 앞선 보도일 수 있음\)/);
  // 앞 실행에서 규칙이 바뀌어 다시 본 항목이 이번 실행엔 안 보임: 한 줄로
  {
    const { pressLines } = await import('../cloudflare/digest.mjs');
    const line = pressLines({ verdict: '관련 보도 있음', queries: ['현대제철 강관 관세'], evidence: [], checkedAt: '2026-11-09T11:02:00+09:00', recheck: true },
      '11-09 12:50', '2026-11-09T12:50:00+09:00')[0];
    assert.match(line, /보도 대조\(자동 11-09 11:02\): 관련 보도 있음 — "현대제철 강관 관세" · 대조 규칙이 바뀌어 72시간 지난 뒤 11-09 11:02에 한 번 다시 봄\(그 뒤로는 범위 밖\)$/);
    // 근거 기사 제목 숫자가 항목 숫자와 같은지(11-09)
    const lines = pressLines({ verdict: '관련 보도 있음', queries: ['현대제철 강관 관세'], checkedAt: '2026-11-09T12:50:00+09:00', evidence: [
      { date: '2026-11-05', channel: 'naver', title: '[단독] 美, 현대제철 강관 반덤핑 4.20% 확정', url: 'https://a', numbers: { article: ['4.20%'], found: ['4.20%'] } },
      { date: '2026-11-05', channel: 'naver', title: '현대제철 강관 예비 4.19%', url: 'https://b', numbers: { article: ['4.19%'], found: [] } }] },
    '11-09 12:50', '2026-11-09T12:50:00+09:00');
    assert.match(lines[0], / · 제목 숫자까지 항목과 같은 기사 1건 — 같은 사건일 가능성 높음$/);
    assert.match(lines[1], /4\.20% 확정 https:\/\/a \(숫자 4\.20% 항목과 같음\)$/);
    assert.match(lines[2], /예비 4\.19% https:\/\/b \(숫자 4\.19% — 항목 숫자와 다름, 다른 건일 수 있음\)$/);
  }
  // 이번 실행에서 다시 대조하지 않은 항목(11-09 강관 관보): 자기 대조 시각과 '다시 안 봄'
  assert.match(a, /보도 대조\(자동 10-23 12:50\): 미확인 — 채널 naver failed\(ConnectTimeout\)\(0건 아님\) · 그 뒤 대조에서는 다시 안 봄\(최근 72시간 범위 밖 등\) — 질의·판정은 10-23 12:50 것/);
  assert.match(r.text, /보도 대조\(자동\)는 네이버 뉴스 API·빙·구글에서 항목 날짜 3일 전부터 찾은 결과다/);
  assert.doesNotMatch(r.text, /보도 대조\(자동\): 결과 없음/);
  const none = await call('radar_today', {}, PRIVATE());
  assert.match(none.text, /보도 대조\(자동\): 결과 없음 — 미확인\(평일 08:50·12:50·18:50 실행 확인\)/);
});

test('press check is dispatched after the morning watches and after the evening page watch', () => {
  assert.deepEqual(dueAt(new Date('2026-10-27T23:50:00Z')), ['radar-press-check.yml']);  // Wed 08:50 KST
  assert.deepEqual(dueAt(new Date('2026-10-28T03:50:00Z')), ['radar-press-check.yml']);  // Wed 12:50 KST — 오전에 새로 잡힌 A·B
  // 공식 원자료 직접 수집: 06:40·08:00·15:00·18:00 KST 평일
  assert.deepEqual(dueAt(new Date('2026-10-28T21:40:00Z')), ['us-osha.yml', 'scoop-radar.yml']);  // Thu 06:40 KST
  assert.deepEqual(dueAt(new Date('2026-10-28T23:00:00Z')), ['scoop-radar.yml']);  // Thu 08:00 KST
  assert.deepEqual(dueAt(new Date('2026-10-29T06:00:00Z')), ['scoop-radar.yml']);  // Thu 15:00 KST
  assert.deepEqual(dueAt(new Date('2026-10-29T09:00:00Z')), ['scoop-radar.yml']);  // Thu 18:00 KST
  assert.deepEqual(dueAt(new Date('2026-10-31T23:00:00Z')), []);                   // Sun 08:00 KST
  assert.deepEqual(dueAt(new Date('2026-10-28T21:10:00Z')), ['kr-fuel.yml']);      // Thu 06:10 KST
  assert.deepEqual(dueAt(new Date('2026-10-28T21:20:00Z')), ['us-epa.yml', 'kr-exec-market.yml', 'kr-stacks.yml']);       // Thu 06:20 KST(수시 임원 공시 11-05)
  assert.deepEqual(dueAt(new Date('2026-10-28T09:50:00Z')), ['radar-press-check.yml']);  // Wed 18:50 KST
  // 주말: 매일 감시(연비·EPA·OSHA)와 미국 리콜만 — 10-31 토 OSHA GitHub 예약이 돌지 않았다
  assert.deepEqual(dueAt(new Date('2026-10-30T21:10:00Z')), ['kr-fuel.yml']);      // Sat 06:10 KST
  assert.deepEqual(dueAt(new Date('2026-10-30T21:20:00Z')), ['us-epa.yml', 'kr-exec-market.yml', 'kr-stacks.yml']);       // Sat 06:20 KST(수시 임원 공시는 매일)
  assert.deepEqual(dueAt(new Date('2026-10-30T21:40:00Z')), ['us-osha.yml', 'epo-ops-watch.yml']);      // Sat 06:40 KST (scoop-radar는 평일만, 해외 특허 공개는 토요일 11-10)
  assert.deepEqual(dueAt(new Date('2026-10-31T05:40:00Z')), ['epo-ops-watch.yml']);   // Sat 14:40 KST — EPO 과부하로 멈춘 회사 재시도 칸
  assert.deepEqual(dueAt(new Date('2026-10-31T21:40:00Z')), ['us-osha.yml', 'epo-ops-watch.yml']);   // Sun 06:40 KST — 재시도 칸
  assert.ok(!dueAt(new Date('2026-10-28T21:40:00Z')).includes('epo-ops-watch.yml'));   // Thu 06:40 KST — 평일 아침엔 안 돎
  assert.ok(dueAt(new Date('2026-10-29T01:50:00Z')).includes('epo-ops-watch.yml'));    // Thu 10:50 KST — EPO 없이 국내 공개 다시 잇기
  assert.ok(!dueAt(new Date('2026-10-31T01:50:00Z')).includes('epo-ops-watch.yml'));   // Sat 10:50 KST — 주말은 06:40·14:40 칸만
  assert.deepEqual(dueAt(new Date('2026-10-31T08:10:00Z')), ['us-recalls.yml']);   // Sat 17:10 KST — 미국 금요일 파일
  assert.deepEqual(dueAt(new Date('2026-11-01T08:10:00Z')), ['us-recalls.yml']);   // Sun 17:10 KST
  assert.deepEqual(dueAt(new Date('2026-10-30T21:30:00Z')), []);                   // Sat 06:30 KST (page-watch·kr-local 평일만)
  assert.deepEqual(dueAt(new Date('2026-10-31T09:50:00Z')), []);                   // Sat 18:50 KST (보도 대조 평일만)
  // 주 1회(월) 감시: 상표 07:10·공장 부지 건축허가 07:50 — 화요일·일요일에는 없음
  assert.deepEqual(dueAt(new Date('2026-11-01T22:10:00Z')), ['scoop-screen.yml', 'trademark-watch.yml']);   // Mon 07:10 KST
  assert.deepEqual(dueAt(new Date('2026-11-01T22:50:00Z')), ['us-litigation.yml', 'kr-exec.yml', 'kr-building.yml']);      // Mon 07:50 KST
  assert.deepEqual(dueAt(new Date('2026-11-02T22:10:00Z')), ['scoop-screen.yml', 'trademark-watch.yml']);   // Tue 07:10 KST — 월요일에 실패·대기한 회사만(스크립트가 판단)
  assert.deepEqual(dueAt(new Date('2026-11-06T22:10:00Z')), []);                                            // Sat 07:10 KST
  assert.deepEqual(dueAt(new Date('2026-10-31T22:10:00Z')), []);                                            // Sun 07:10 KST
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

test('무역구제 기사 포인트(11-08): 결정문 쟁점 한국어 풀이·품목 이름·세율 비교, 보도 대조는 품목 낱말까지', () => {
  assert.equal(memoGloss('Comment 5: Whether the Provision of KAUs Confers a Countervailable Benefit'), '탄소배출권(K-ETS 할당)을 보조금으로 볼지');
  assert.equal(memoGloss('Comment 8: Whether the Constructing and Operation of Workplace Nursery Program is Countervailable'), '직장어린이집 운영 지원을 보조금으로 볼지');
  assert.equal(memoGloss('Comment 4: Whether a Particular Market Situation Exists in Korea'), '특별시장상황(PMS) 적용 여부');
  assert.equal(memoGloss('Comment 9: Something Else Entirely'), null);
  assert.deepEqual(productKo('Circular Welded Non-Alloy Steel Pipe From the Republic of Korea: Final Results'), { ko: '강관', words: ['강관'] });
  assert.deepEqual(productKo('Certain Cut-To-Length Carbon-Quality Steel Plate From the Republic of Korea: Final Results').ko, '후판');
  assert.deepEqual(productKo('Certain Corrosion-Resistant Steel Products From the Republic of Korea').words, ['도금강판', '도금']);
  assert.equal(productKo('Large Power Transformers From the Republic of Korea').ko, '변압기');
  const plate = { title: 'Certain Cut-To-Length Carbon-Quality Steel Plate From the Republic of Korea: Final Results of Countervailing Duty Administrative Review; 2024',
    stage: '최종 판정', rateTable: { kind: '상계관세', rates: { 현대제철: { rate: 1.39, via: '표' }, 동국제강: { rate: 1.89, via: '표' } } },
    prior: { final: { date: '2026-02-20', rates: { 현대제철: 1.31, 동국제강: 2.21 } } },
    memoUnusual: ['Comment 1: Whether Commerce Inadvertently Excluded U.S. Sales from the Margin Calculation', 'Comment 5: Whether the Provision of KAUs Confers a Countervailable Benefit'] };
  assert.equal(tradePoint(plate), '미국 후판 상계관세 최종 — 현대제철 1.39%(직전 최종 1.31%, +0.08%p) · 동국제강 1.89%(직전 최종 2.21%, −0.32%p) · 쟁점: 탄소배출권(K-ETS 할당)을 보조금으로 볼지(결정문 Comment 5)');
  assert.equal(tradePoint({ title: 'Some Notice', stage: '개시' }), '');
});

test('trade remedies: a beat duty rate far from the last final of the same docket reaches A with both rates; same rates stay B', async () => {
  // 10-08 도금강판 반덤핑 예비(KG스틸 23.40%·동국씨엠 19.43%, 직전 최종 2026-05-14 모두 0.00%) → 10-30 경쟁지 [단독] '美 도금강판 관세 70%대'
  const opts = PRIVATE();
  const env = opts.env;
  const core = { id: 'fr:2026-20698', date: '2026-10-24', stage: '예비 판정', url: 'https://www.federalregister.gov/d/2026-20698',
    title: 'Certain Corrosion-Resistant Steel Products From the Republic of Korea: Preliminary Results and Rescission, in Part, of Antidumping Duty Administrative Review; 2024-2025',
    named: [{ company: 'KG스틸', mentions: 3, lines: ['KG Dongbu Steel Co., Ltd........ 23.40'] }, { company: '동국씨엠', mentions: 2, lines: ['Dongkuk Coated Metal'] }],
    rateTable: { kind: '반덤핑', othersRate: 20.58, rows: 3, rates: { 'KG스틸': { rate: 23.4, name: 'KG Dongbu Steel Co., Ltd', via: '표' },
      '동국씨엠': { rate: 19.43, name: 'Dongkuk Coated Metal Co., Ltd./Aju Steel Co., Ltd', via: '표' }, '포스코': { rate: 20.58, name: '비선정 업체', via: '비선정' } } },
    prior: { docket: 'A-580-878', final: { id: 'fr:2026-09691', date: '2026-05-14', title: 'Final Results', rates: { 'KG스틸': 0, '동국씨엠': 0, '포스코': 0 }, othersRate: null } },
    rateChange: [{ company: 'KG스틸', rate: 23.4, before: 0 }, { company: '동국씨엠', rate: 19.43, before: 0 }, { company: '포스코', rate: 20.58, before: 0 }],
    firstSeen: '2026-10-25T07:40:00+09:00' };
  const lpt = { id: 'fr:2026-22343', date: '2026-10-24', stage: '예비 판정', url: 'https://www.federalregister.gov/d/2026-22343',
    title: 'Large Power Transformers From the Republic of Korea: Preliminary Results of Antidumping Duty Administrative Review; 2024-2025',
    named: [{ company: 'LS일렉트릭', mentions: 2, lines: ['LS Electric Co., Ltd........ 4.32'] }, { company: 'HD현대일렉트릭', mentions: 2, lines: ['HD Hyundai Electric'] }],
    rateTable: { kind: '반덤핑', othersRate: null, rows: 4, rates: { 'HD현대일렉트릭': { rate: 0, name: 'HD Hyundai Electric Co., Ltd', via: '표' }, 'LS일렉트릭': { rate: 4.32, name: 'LS Electric Co., Ltd', via: '표' } } },
    prior: { docket: 'A-580-867', final: { id: 'fr:2026-16663', date: '2026-08-14', rates: { 'HD현대일렉트릭': 0, 'LS일렉트릭': 4.32 }, othersRate: null } },
    firstSeen: '2026-10-25T07:40:00+09:00' };
  const unread = { id: 'fr:x', date: '2026-10-24', stage: '최종 판정', url: 'https://x', title: 'Welded Line Pipe From the Republic of Korea: Final Results of Antidumping Duty Administrative Review; 2024-2025',
    named: [{ company: '세아제강', mentions: 1, lines: ['SeAH'] }], rateTable: { kind: '반덤핑', rates: {}, othersRate: null, rows: 0 }, firstSeen: '2026-10-25T07:40:00+09:00' };
  await worker.fetch(new Request(ORIGIN + '/ingest/trade-remedy', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify({
    schema: 'trade_remedy/v1', generatedAt: '2026-10-25T07:40:00+09:00', checks: [], quotas: [], events: [], federalRegister: [core, lpt, unread] }) }), env, {});
  const r = await call('radar_today', { hours: 72 }, opts);
  const a = r.text.split('[A · ')[1].split('[B · ')[0];
  assert.match(a, /무역구제 · KG스틸·동국씨엠·포스코\n   미국 관보 예비 판정: Certain Corrosion-Resistant[^\n]* — 세율 크게 바뀜: KG스틸 0\.00%→23\.40%, 동국씨엠 0\.00%→19\.43%, 포스코 0\.00%→20\.58% — 본문에 KG스틸·동국씨엠 · 반덤핑 세율\(관보 표\): KG스틸 23\.40%\(직전 최종 0\.00%\) · 동국씨엠 19\.43%\(직전 최종 0\.00%\) · 포스코 20\.58%\(비선정 업체 세율\)\(직전 최종 0\.00%\) \[직전 최종 2026-05-14\]/);
  // 11-04 기사 준비: 다음 절차(미국 법정 기한, 게재일 기준)와 회사에 물을 것
  assert.match(a, /\[직전 최종 2026-05-14\]\n   〔기사 포인트〕 미국 도금강판 반덤핑 예비 — KG스틸 23\.40%\(직전 최종 0\.00%, \+23\.40%p\) · 동국씨엠 19\.43%\(직전 최종 0\.00%, \+19\.43%p\) · 포스코 20\.58%\(비선정 업체 세율\)\(직전 최종 0\.00%, \+20\.58%p\)\n   〔기사 준비〕 다음 절차: 연례 재심 최종 판정은 예비 게재\(10-24\)부터 120일 안\(02-21까지, 최대 180일 04-22로 연장 가능\) — 최종에서 세율이 바뀔 수 있음 · 의견서\(사건 요지서\) 마감은 관보 본문 날짜 확인\n   물을 것: 회사: 최종 판정 전 의견서 제출 계획/);
  const b = r.text.split('[B · ')[1].split('[C · ')[0];
  assert.match(b, /Large Power Transformers[^\n]* — 본문에 LS일렉트릭·HD현대일렉트릭 · 반덤핑 세율\(관보 표\): HD현대일렉트릭 0\.00%\(직전 최종 0\.00%\) · LS일렉트릭 4\.32%\(직전 최종 4\.32%\) \[직전 최종 2026-08-14\]/);
  assert.match(b, /Welded Line Pipe[^\n]*\n   〔기사 준비〕 다음 절차: 미국 국제무역법원\(CIT\) 제소 기한은 게재\(10-24\)부터 30일\(11-23\) · 확정 세율로 수입 정산 지시는 보통 게재 15일 뒤\(11-08 무렵\)\n   물을 것: 회사: CIT 제소 여부/);
  assert.match(b, /Welded Line Pipe[^\n]* · 세율 표 못 읽음\(원문 표 확인\)/);
  const items = await (await radarItems(new Request(ORIGIN + '/ingest/radar-items?hours=72', { headers: { Authorization: `Bearer ${TOKEN}` } }), env, { now: NOW })).json();
  const hit = items.items.find((x) => x.id === 'fr:2026-20698');
  assert.deepEqual([hit.tier, hit.check.who, hit.check.terms], ['A', 'KG스틸', ['관세', '반덤핑']]);
  const t = await call('trade_remedies', { section: 'us' }, opts);
  assert.match(t.text, /세율 크게 바뀜: KG스틸 0\.00%→23\.40%/);
  assert.match(t.text, /세율 — 반덤핑 세율\(관보 표\): HD현대일렉트릭 0\.00%/);
});

test('trade remedies: ITC votes on Korean beat products show the outcome; revocation or no-injury is A, continuation is B', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const seen = '2026-10-25T07:40:00+09:00';
  const commerce = { id: 'fr:octg', date: '2026-10-24', stage: '최종 판정', agency: 'International Trade Administration', url: 'https://x/octg',
    title: 'Certain Oil Country Tubular Goods From the Republic of Korea: Final Results of Antidumping Duty Administrative Review; 2023-2024',
    named: [{ company: '세아제강', mentions: 1, lines: ['SeAH'] }, { company: '현대제철', mentions: 1, lines: ['Hyundai Steel'] }], beatProduct: true, firstSeen: seen };
  const keep = { id: 'fr:itc1', date: '2026-10-24', stage: '기타', agency: 'International Trade Commission', url: 'https://x/itc1', beatProduct: true, named: [],
    title: 'Oil Country Tubular Goods From India, South Korea, Turkey, Ukraine, and Vietnam; Determinations', firstSeen: seen,
    itcOutcome: { phase: '일몰 재심', korea: '긍정', quote: "determines that revocation of the antidumping duty orders on oil country tubular goods from India, South Korea … would be likely to lead to continuation", dissent: [] } };
  const gone = { id: 'fr:itc2', date: '2026-10-24', stage: '기타', agency: 'International Trade Commission', url: 'https://x/itc2', beatProduct: true, named: [],
    title: 'Large Power Transformers From Korea; Determinations', firstSeen: seen,
    itcOutcome: { phase: '일몰 재심', korea: '부정', quote: 'determines that revocation of the antidumping duty order on large power transformers from Korea would not be likely to lead to continuation', dissent: [] } };
  await worker.fetch(new Request(ORIGIN + '/ingest/trade-remedy', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify({
    schema: 'trade_remedy/v1', generatedAt: seen, checks: [], quotas: [], events: [], federalRegister: [commerce, keep, gone] }) }), env, {});
  const r = await call('radar_today', { hours: 72 }, opts);
  const a = r.text.split('[A · ')[1].split('[B · ')[0];
  const b = r.text.split('[B · ')[1].split('[C · ')[0];
  assert.match(a, /미국 ITC 일몰 재심 판정: Large Power Transformers From Korea; Determinations — 한국산 관세 철폐\(피해 재발 가능성 없음\)/);
  assert.match(b, /무역구제 · 세아제강·현대제철\n   미국 ITC 일몰 재심 판정: Oil Country Tubular Goods[^\n]* — 한국산 관세 유지\(철폐하면 피해 재발 — 5년 더\) · 같은 품목 상무부 고시의 출입처: 세아제강·현대제철 · 원문 "determines that revocation/);
  const items = await (await radarItems(new Request(ORIGIN + '/ingest/radar-items?hours=72', { headers: { Authorization: `Bearer ${TOKEN}` } }), env, { now: NOW })).json();
  assert.deepEqual(items.items.find((x) => x.id === 'fr:itc1').check.terms, ['ITC', '유지']);
  const t = await call('trade_remedies', { section: 'us' }, opts);
  assert.match(t.text, /ITC 일몰 재심 판정: 한국산 관세 철폐\(피해 재발 가능성 없음\) — 원문 "determines that revocation/);
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

test('us_recalls: NHTSA manufacturer communications by campaign — powertrain warranty extension A, campaign B, C hidden unless show_all, baseline not pushed', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const now = new Date(Date.now() - 3600000).toISOString();
  const base = new Date(Date.now() - 5 * 86400000).toISOString();
  const today = now.slice(0, 10);
  const item = (id, extra) => ({ id, ids: ['11012001'], doc: '26-EE-007H', docCount: 1, added: '2026-07-20', lastAdded: '2026-07-20', mfrDate: '2026-07-18', type: 'WARRANTY PROGRAM/EXTENSION', kindName: '보증 연장',
    summary: 'Warranty extension for the Integrated Charging Control Unit (ICCU) to 15 years.', companies: ['현대차'], brands: ['현대차'],
    models: [{ model: 'IONIQ 5', years: ['2023', '2024'] }, { model: 'IONIQ 6', years: ['2023'] }], modelCount: 2, components: ['ELECTRICAL SYSTEM'], systems: [],
    rows: 3, otherRows: 0, tier: 'A', firstSeen: base, isNew: false, url: 'https://static.nhtsa.gov/odi/tsbs/2026/MC-11012001-0001.pdf', ...extra });
  const doc = { schema: 'us_recalls/v1', generatedAt: now, windowDays: 21, rules: [], recalls: [], investigations: [],
    checks: [{ source: 'NHTSA 전체 리콜 파일', status: 'ok' }, { source: 'NHTSA 제조사 통신(TSB)', status: 'ok', rows: 4 }],
    tsbs: { windowDays: 120, baselineSince: base, fileModified: 'Sat, 31 Oct 2026 10:08:16 GMT', rules: ['딜러용 통신이라 결함 인정·리콜이 아니다.'], items: [
      item('HMA:LA07'),                                                                                     // 기준선(이미 있던 통신) — 레이더에 안 올림
      item('KIA:WTY052', { added: today, lastAdded: today, firstSeen: now, isNew: true, summary: 'Kia is extending the warranty for engine damage to 15 years/150,000 miles.', companies: ['기아'], brands: ['기아'],
        campaign: 'WTY052', doc: 'WTY052_DP', docCount: 3, url: 'https://static.nhtsa.gov/odi/tsbs/2026/MC-11012101-0001.pdf', docs: [{ id: '11012100', doc: 'WTY052_OWNR' }, { id: '11012101', doc: 'WTY052_DP' }, { id: '11012102', doc: 'WTY052_QA' }],
        models: [{ model: 'TELLURIDE', years: ['2026'] }], modelCount: 1, components: ['ENGINE'] }),
      item('KIA:SC123', { added: today, lastAdded: today, firstSeen: now, isNew: true, type: 'SERVICE CAMPAIGN', kindName: '서비스 캠페인', tier: 'B', campaign: 'SC123',
        summary: 'Service campaign to update the trailer hitch module.', companies: ['기아'], brands: ['기아'], models: [{ model: 'SORENTO', years: ['2026'] }], modelCount: 1 }),
      item('HMA:doc:26-AV-011H', { added: today, lastAdded: today, firstSeen: now, isNew: true, type: 'SERVICE BULLETIN/REPAIR INSTRUCTIONS', kindName: '서비스 공지(수리 지침)', tier: 'C',
        summary: 'Radio display software update.', models: [{ model: 'TUCSON', years: ['2025'] }], modelCount: 1 })] } };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/us-recalls', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const t = await call('us_recalls', {}, opts);
  assert.match(t.text, /\[제조사 통신\(서비스 캠페인·보증 연장·서비스 공지, 캠페인 단위\) · 파일 추가일 최근 120일\] 4건\(A 2·B 1·참고 C 1 — C는 show_all=true\)/);
  assert.match(t.text, new RegExp(`\\[신규\\] A · ${today} · 보증 연장 · 기아 TELLURIDE\\(2026\\)`));
  assert.match(t.text, /캠페인 WTY052 · 문서 3건\(WTY052_OWNR, WTY052_DP, WTY052_QA\)/);
  assert.match(t.text, /A · 2026-07-20 · 보증 연장 · 현대차 IONIQ 5\(2023·2024\), IONIQ 6\(2023\)/);
  assert.match(t.text, /캠페인 SC123 · 문서 26-EE-007H/);
  assert.match(t.text, /원문: https:\/\/static\.nhtsa\.gov\/odi\/tsbs\/2026\/MC-11012101-0001\.pdf/);
  assert.doesNotMatch(t.text, /Radio display/);
  assert.match((await call('us_recalls', { show_all: true }, opts)).text, /C · [^\n]*서비스 공지\(수리 지침\) · 현대차 TUCSON\(2025\)/);
  const r = await call('radar_today', { include_minor: true }, opts);
  const a = r.text.split('[A · ')[1].split('[B · ')[0];
  assert.match(a, /미국 NHTSA 제조사 통신 보증 연장 · 추가 [^\n]*기아 TELLURIDE\(2026년형\) · 캠페인 WTY052 · 문서 3건 · 「Kia is extending the warranty for engine damage/);
  assert.doesNotMatch(r.text, /IONIQ 5/);    // 기준선 통신은 레이더에 안 올림
  assert.match(r.text.split('[B · ')[1], /서비스 캠페인 · 추가 [^\n]*기아 SORENTO\(2026년형\) · 캠페인 SC123 · 문서 26-EE-007H/);
  const items = await (await radarItems(new Request(ORIGIN + '/ingest/radar-items?hours=72', { headers: { Authorization: `Bearer ${TOKEN}` } }), env, { now: NOW })).json();
  const tl = items.items.find((x) => x.id === 'tsb:KIA:WTY052').check;
  assert.deepEqual([tl.who, tl.terms, tl.places, tl.alts['무상수리'].includes('보증 연장')], ['기아', ['텔루라이드', '무상수리'], ['텔루라이드'], true]);
});

test('reporter board /r/<token> and homepage fragment /b/open: no scripts, no referrer, cards from radar_today data with unreported marked', async () => {
  const env = { MCP_ACCESS_TOKEN: TOKEN, STORE: storeBinding() };
  const get = (path, init) => worker.fetch(new Request(ORIGIN + path, init), env, {});
  assert.equal((await get('/r/wrong-token-0123456789abc')).status, 404);
  assert.equal((await get('/r/short')).status, 404);
  assert.equal((await get(`/r/${TOKEN}`, { method: 'POST' })).status, 405);
  const recent = new Date(Date.now() - 3600000).toISOString();
  const post = (name, doc) => worker.fetch(new Request(ORIGIN + `/ingest/${name}`, { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {});
  assert.equal((await post('kr-local', { schema: 'kr_local/v1', generatedAt: recent, checks: [], items: [
    { id: 'local:당진시:2', city: '당진시', company: '현대제철', tier: 'A', title: '현대제철㈜ 당진 전기로 설치 공유수면 점용 허가 <b>', date: recent.slice(0, 10), firstSeen: recent,
      url: 'https://www.dangjin.go.kr/a?b=1&c=2' }] })).status, 200);
  assert.equal((await post('radar-check', { schema: 'radar_check/v1', generatedAt: recent, items: [
    { id: 'local:당진시:2', verdict: '미보도 후보', since: '2026-10-28', queries: ['현대제철 당진'], channels: {},
      evidence: [{ date: '2026-10-20', channel: '네이버', title: '현대제철, 당진 전기로 검토', url: 'https://n.news/1', before: true }] }] })).status, 200);
  const r = await get(`/r/${TOKEN}?hours=72`);
  assert.equal(r.status, 200);
  assert.equal(r.headers.get('Referrer-Policy'), 'no-referrer');
  assert.match(r.headers.get('X-Robots-Tag'), /noindex/);
  assert.match(r.headers.get('Cache-Control'), /no-store/);
  assert.match(r.headers.get('Content-Security-Policy'), /default-src 'none'/);
  const html = await r.text();
  assert.doesNotMatch(html, /<script/i);
  assert.doesNotMatch(html, new RegExp(TOKEN));      // 토큰은 화면에 안 찍는다(링크는 ?hours= 상대 주소)
  assert.match(html, /<article class="rb-card rb-tA">\s*<div class="rb-top"><span class="rb-tier">A<\/span><span class="rb-pv pnew">미보도 후보<\/span><span class="rb-watch">지자체 고시·공고<\/span>/);
  assert.match(html, /공유수면 점용 허가 &lt;b&gt;/);  // 원문 글자는 이스케이프
  assert.match(html, /<a class="rb-btn" href="https:\/\/www\.dangjin\.go\.kr\/a\?b=1&amp;c=2" target="_blank" rel="noopener noreferrer">원문 열기<\/a>/);
  assert.match(html, /보도 대조\(자동 [^)]*\): 미보도 후보<\/b> · “현대제철 당진”로 2026-10-28 이후 관련 기사를 못 찾음/);
  assert.match(html, /앞선 기사: 항목 날짜 전이라 판정에 안 셈/);
  assert.match(html, /<summary>Claude에 넘길 id<\/summary><code>local:당진시:2<\/code>/);   // id는 접어 둔다
  assert.match(html, /<a class="rb-chip on" href="\?hours=72">72시간<\/a>/);
  assert.match(html, /<div><b>1<\/b><span>A 단독 후보·직접 변화<\/span><\/div>/);
  assert.equal((await get(`/r/${TOKEN}/?q=${encodeURIComponent('없는회사')}`)).status, 200);
  // 홈페이지 탭 조각: 읽기 전용 열쇠(토큰에서 HMAC)로만, 홈페이지 주소에만 CORS. 토큰 자체로는 안 열린다.
  const key = await boardKey(env);
  assert.match(key, /^[A-Za-z0-9_-]{32}$/);
  assert.notEqual(key, TOKEN);
  assert.match(html, /<a href="https:\/\/shhong9173-art\.github\.io\/seoul-reporting-radar\/" rel="noreferrer">홈페이지<\/a>/);
  assert.doesNotMatch(html, new RegExp(key));
  assert.equal((await get(`/b/${TOKEN}`)).status, 404);
  assert.equal((await get('/b/wrong-key-0123456789abcdef0123')).status, 404);
  const part = await get(`/b/${key}?hours=72`, { headers: { Origin: 'https://shhong9173-art.github.io' } });
  assert.equal(part.status, 200);
  assert.equal(part.headers.get('Access-Control-Allow-Origin'), 'https://shhong9173-art.github.io');
  assert.match(part.headers.get('Cache-Control'), /no-store/);
  const frag = await part.text();
  assert.doesNotMatch(frag, /<script|<html/i);
  assert.match(frag, /^<style>/);
  assert.match(frag, /<div class="rb-sum" data-a="1" data-b="0" data-new="1">/);
  assert.match(frag, /<span class="rb-pv pnew">미보도 후보<\/span>/);
  assert.doesNotMatch(frag, new RegExp(key));
  assert.equal((await get(`/b/${key}`, { headers: { Origin: 'https://evil.example' } })).headers.get('Access-Control-Allow-Origin'), null);
  assert.equal((await get(`/b/${key}`, { method: 'POST', headers: { Origin: 'https://shhong9173-art.github.io' } })).status, 405);
  // 11-01 기자 결정: 홈페이지 탭은 열쇠 없이(/b/open). 같은 조각, 홈페이지 주소에만 CORS.
  const open = await get('/b/open', { headers: { Origin: 'https://shhong9173-art.github.io' } });
  assert.equal(open.status, 200);
  assert.equal(open.headers.get('Access-Control-Allow-Origin'), 'https://shhong9173-art.github.io');
  const openHtml = await open.text();
  assert.match(openHtml, /<span class="rb-pv pnew">미보도 후보<\/span>/);
  assert.doesNotMatch(openHtml, /<script/i);
  assert.equal((await get('/b/open', { method: 'POST' })).status, 405);
  assert.equal((await get('/b/opened')).status, 404);
  // 숫자만 다른 같은 곳 같은 유형은 한 카드
  const row = (n) => ({ tier: 'B', watch: '굴뚝 측정(공장 가동 신호)', company: '현대제철', id: `stk:${n}`, fact: `현대제철㈜포항1공장 배출구 ${n}번이 굴뚝 자동측정 목록에서 2번 연속 빠짐 — 설비 폐쇄·측정 대상 변경일 수 있음(회사 확인)` });
  assert.deepEqual(groupSame([row(10), row(2), row(5), { ...row(7), company: '포스코' }], () => undefined).map((g) => g.length), [3, 1]);
  // 괄호 안 구분자는 자르지 않고, ' — ' 뒤 단서 달기는 주의로·핵심 사실은 세부 줄로
  assert.deepEqual(splitTop("변경(종료일 +7개월 · 사유 '연장') · 계약상대 ㈜야월", ' · '), ["변경(종료일 +7개월 · 사유 '연장')", '계약상대 ㈜야월']);
  assert.deepEqual(factParts('엘에스엠앤엠(주): 배출구 1개가 3번 연속 평소의 10% 아래 — 5번(평소 50.8→최근 0.18) · 정비·점검일 수 있음(회사 확인)'),
    { title: '엘에스엠앤엠(주): 배출구 1개가 3번 연속 평소의 10% 아래', details: ['5번(평소 50.8→최근 0.18)'], notes: ['정비·점검일 수 있음(회사 확인)'] });
  assert.deepEqual(factParts('금호타이어 · [기재정정]유형자산취득결정 — 정정 중 큰 변경(취득예정일자 -36개월)').title, '금호타이어 · [기재정정]유형자산취득결정');
});

test('homepage login: ID/password secrets give a 30-day signed session for /b/me; /b/open closes once login is set; lockout after repeated failures', async () => {
  const H = 'https://shhong9173-art.github.io';
  const base = { MCP_ACCESS_TOKEN: TOKEN, STORE: storeBinding() };
  const req = (env, path, init = {}) => worker.fetch(new Request(ORIGIN + path, { ...init, headers: { Origin: H, ...(init.headers ?? {}) } }), env, {});
  const login = (env, id, pw, ip = '1.1.1.1') => req(env, '/auth/login', { method: 'POST', headers: { 'Content-Type': 'text/plain', 'CF-Connecting-IP': ip }, body: JSON.stringify({ id, pw }) });
  // 비밀값 등록 전: 로그인 503, /b/open 공개, /b/me 503
  assert.equal((await login(base, 'a', 'b')).status, 503);
  assert.equal((await req(base, '/b/open')).status, 200);
  assert.equal((await req(base, '/b/me')).status, 503);
  const env = { ...base, BOARD_USER: 'hong', BOARD_PASSWORD: 'correct-horse-battery' };
  // 사전 요청(Authorization 헤더) 허용
  const pre = await req(env, '/b/me', { method: 'OPTIONS', headers: { 'Access-Control-Request-Headers': 'authorization' } });
  assert.equal(pre.status, 204);
  assert.equal(pre.headers.get('Access-Control-Allow-Origin'), H);
  assert.match(pre.headers.get('Access-Control-Allow-Headers'), /Authorization/);
  // 등록 후: 공개 조각은 닫힘
  assert.equal((await req(env, '/b/open')).status, 401);
  assert.equal((await req(env, '/b/me')).status, 401);
  const bad = await login(env, 'hong', 'wrong');
  assert.equal(bad.status, 401);
  assert.equal(bad.headers.get('Access-Control-Allow-Origin'), H);
  const ok = await login(env, 'hong', 'correct-horse-battery');
  assert.equal(ok.status, 200);
  const { session, exp } = await ok.json();
  assert.match(session, /^v1\.\d{13}\.[A-Za-z0-9_-]{43}$/);
  assert.ok(exp - Date.now() > 29 * 86400000);
  assert.doesNotMatch(session, /correct-horse|hong/);
  const me = await req(env, '/b/me?hours=72', { headers: { Authorization: `Bearer ${session}` } });
  assert.equal(me.status, 200);
  assert.equal(me.headers.get('Access-Control-Allow-Origin'), H);
  assert.match(await me.text(), /^<style>[\s\S]*<div class="rb-sum"/);
  // 위조·만료·비밀번호 변경 뒤 세션은 무효
  assert.equal((await req(env, '/b/me', { headers: { Authorization: `Bearer ${session.slice(0, -2)}xx` } })).status, 401);
  assert.equal((await req(env, '/b/me', { headers: { Authorization: `Bearer v1.${Date.now() - 1000}.${session.split('.')[2]}` } })).status, 401);
  assert.equal((await req({ ...env, BOARD_PASSWORD: 'changed-password-123' }, '/b/me', { headers: { Authorization: `Bearer ${session}` } })).status, 401);
  // 같은 아이피 8번 실패면 맞는 비밀번호도 1시간 잠금, 다른 아이피는 그대로
  for (let i = 0; i < 7; i += 1) assert.equal((await login(env, 'hong', `nope${i}`)).status, 401);
  assert.equal((await login(env, 'hong', 'correct-horse-battery')).status, 429);
  assert.equal((await login(env, 'hong', 'correct-horse-battery', '2.2.2.2')).status, 200);
  assert.equal((await req(env, '/auth/login')).status, 405);
  // 사이트 첫 화면 잠금(gate.js): /auth/check — 세션 맞으면 200, 없거나 틀리면 401, 미설정 503, 사전 요청 허용
  assert.equal((await req(env, '/auth/check', { headers: { Authorization: `Bearer ${session}` } })).status, 200);
  assert.equal((await req(env, '/auth/check')).status, 401);
  assert.equal((await req(env, '/auth/check', { headers: { Authorization: 'Bearer v1.9999999999999.' + 'x'.repeat(43) } })).status, 401);
  assert.equal((await req(base, '/auth/check', { headers: { Authorization: `Bearer ${session}` } })).status, 503);
  const pc = await req(env, '/auth/check', { method: 'OPTIONS' });
  assert.equal(pc.status, 204);
  assert.equal(pc.headers.get('Access-Control-Allow-Origin'), H);
});

test('foreign-news translation /ingest/translate: bearer only, Workers AI language model first (missing models skipped), m2m100 fallback, clean output', async () => {
  const calls = [];
  const AI = { run: async (model, input) => {
    calls.push(model);
    if (model === LLM_MODELS[0]) throw new Error('No such model');                                // 목록에 없는 모델은 건너뛴다
    if (model === LLM_MODELS[1] && input.messages[0].content.includes('요약한다')) return { response: input.messages[1].content.includes('FAIL') ? 'Sorry, I cannot.' : '요약:\n- 현대차가 앨라배마 공장에 4억5000만달러를 투자한다.\n- 신형 투싼을 생산한다.' };
    if (model === LLM_MODELS[1]) return { response: input.messages[1].content.includes('FAIL') ? 'Sorry, I cannot.' : '번역: "고려아연, 미국 제련소 검토"' };
    if (model === MT_MODEL) return { translated_text: '실패 대비 번역' };
    return { response: 'no korean' };
  } };
  const env = { MCP_ACCESS_TOKEN: TOKEN, STORE: storeBinding(), AI };
  const post = (body, auth = `Bearer ${TOKEN}`) => worker.fetch(new Request(ORIGIN + '/ingest/translate', { method: 'POST', headers: { Authorization: auth, 'Content-Type': 'application/json' }, body: JSON.stringify(body) }), env, {});
  assert.equal((await post({ texts: ['x'] }, 'Bearer wrong-token-0123456789')).status, 404);
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/translate', { headers: { Authorization: `Bearer ${TOKEN}` } }), env, {})).status, 405);
  assert.equal((await post({ texts: [] })).status, 400);
  const r = await (await post({ texts: ['Korea Zinc starts US smelter study - Reuters', 'FAIL here', ''] })).json();
  assert.deepEqual(r.results.map((x) => [x.ko, x.status]), [['고려아연, 미국 제련소 검토', 'translated_ai'], ['실패 대비 번역', 'translated_ai_mt'], ['', 'empty']]);
  assert.equal(r.results[0].model, LLM_MODELS[1]);
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/translate', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: '{"texts":["a"]}' }), { MCP_ACCESS_TOKEN: TOKEN }, {})).status, 503);
  assert.equal(cleanOutput('제목: 「현대차, 美 공장 증설」\n설명'), '현대차, 美 공장 증설');
  assert.equal(cleanOutput('English only'), '');
  // 요약(kind:'summary'): 언어 모델만, 번역 전용 모델로 대신하지 않는다
  const mtBefore = calls.filter((m) => m === MT_MODEL).length;
  const s1 = await (await post({ kind: 'summary', texts: ['Hyundai Alabama\n\nHyundai will invest $450m.', 'FAIL summary text'] })).json();
  assert.deepEqual(s1.results.map((x) => [x.ko, x.status]), [['현대차가 앨라배마 공장에 4억5000만달러를 투자한다. 신형 투싼을 생산한다.', 'summarized_ai'], ['', 'failed']]);
  assert.equal(calls.filter((m) => m === MT_MODEL).length, mtBefore);   // 요약 실패는 번역 전용 모델로 대신하지 않는다
  assert.equal(cleanSummary('요약:\n- 현대차가 미국 앨라배마 공장에 4억5000만달러를 투자한다.\n- 신형 투싼을 생산한다.'), '현대차가 미국 앨라배마 공장에 4억5000만달러를 투자한다. 신형 투싼을 생산한다.');
  assert.equal(cleanSummary('Too short English'), '');
  assert.equal(cleanOutput('샤오미, 선우다 EVB 투자 계획 발표… 배터리 협력 강화 -'), '샤오미, 선우다 EVB 투자 계획 발표… 배터리 협력 강화');
});

test('출입처 외신 (global-beat): event words → B with press-check hint, none → C, old baseline items stay out', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const now = new Date(NOW.getTime() - 3600000).toISOString();
  const base = new Date(NOW.getTime() - 6 * 86400000).toISOString();
  const it = (id, extra) => ({ id, url: `https://www.world-nuclear-news.org/articles/${id}`, title: 'Doosan to manufacture upper reactor vessel for NuScale SMR',
    koTitle: '두산, 뉴스케일 소형모듈원전 상부 원자로 용기 제작', koSummary: '두산에너빌리티가 뉴스케일파워와 상부 원자로 용기 제작 계약을 맺었다.', source: 'World Nuclear News',
    published: now, firstSeen: now, beatCompanies: ['두산에너빌리티'], checkTerms: ['원자로'], ...extra });
  const doc = { schema: 'global_beat/v1', generatedAt: now, checks: [{ source: '외신 수집', status: 'ok' }], feedErrors: ['Automotive News'],
    fx: { rates: { 달러: { rate: 1462.3, date: '2026-11-10', label: '원/달러', per: 1 }, 유로: { rate: 1550.2, date: '2026-11-10', label: '원/유로', per: 1 },
      엔: { rate: 905.1, date: '2026-11-10', label: '원/100엔', per: 100 } }, source: '한국은행 ECOS 731Y001' }, items: [
    it('gl:a'),
    it('gl:b', { title: 'Nexen Tire receives EcoVadis Gold', koTitle: '넥센타이어, 에코바디스 골드 3년 연속', koSummary: '넥센타이어가 약 30억 원 규모 상을 받았다.', source: 'Tyrepress', beatCompanies: ['넥센타이어'], checkTerms: [], numbersNotInSource: ['30억 원'] }),
    it('gl:old', { published: base, firstSeen: base, koTitle: '포스코, 오래된 기사', beatCompanies: ['포스코'], checkTerms: ['투자'] }),
    // 11-02 운영: 나라 이름이 든 외신 — 대조 낱말에 나라를 더하고 기사에 그 나라가 있어야 같은 건
    it('gl:cz', { title: 'KHNP ends negotiations with construction consortium for Czech units', koTitle: '한국수력원자력, 체코 원전 건설 컨소시엄과 협상 종료' }),
    it('gl:us', { title: 'Hyundai to invest US$450m in Alabama plant', koTitle: '현대차, 4억 5천만 달러 미국 앨라배마 공장 투자', beatCompanies: ['현대차'], checkTerms: ['공장', '투자'],
      krw: [{ usd: '4억 5천만 달러', krw: '약 6580억원' }] }),   // 예전 꼴(usd, 통화 없음 = 달러)
    it('gl:eu', { title: 'Hyundai Motor to invest EUR 2 billion in Czech plant', koTitle: '현대차, 체코 공장에 20억유로 투자', beatCompanies: ['현대차'], titleCompanies: ['현대차'], checkTerms: ['공장', '투자'],
      krw: [{ amount: '20억유로', cur: '유로', krw: '약 3조1004억원' }, { amount: '1조엔', cur: '엔', krw: '약 9조51억원' }, { amount: '5억파운드', cur: '파운드', krw: '약 8800억원' }] }),
    it('gl:id', { title: 'Hyundai expands Indonesia plant', koTitle: '현대차, 인도네시아 공장 투자', beatCompanies: ['현대차'], checkTerms: ['투자'] }),
    it('gl:dl', { title: 'Kia deliveries', koTitle: '기아, 3분기 인도량 늘려 투자', beatCompanies: ['기아'], checkTerms: ['투자'] }),
    // 11-03 운영: 영어 제목은 그룹 이름, 본문 주체는 계열사 → 참고(C)·대조 안 함
    it('gl:af', { title: 'Posco to supply new battery materials to LGES', koTitle: '포스코, LG에너지솔루션에 신규 배터리 소재 공급', beatCompanies: ['포스코'],
      checkTerms: ['배터리'], affiliateLead: ['포스코퓨처엠'] }),
    // 11-10 운영: 출입처 이름이 본문에만(제목은 혼다) → 참고(C)·대조 안 함. 제목에 출입처가 있으면 그대로 B
    it('gl:honda', { title: 'Honda confirms $3 billion assembly plant in Ohio that will add 2,000 jobs', koTitle: '혼다, 30억달러 규모 오하이오 조립 공장 신설',
      beatCompanies: ['현대차'], titleCompanies: [], checkTerms: ['공장'] }),
    it('gl:hy', { title: 'Hyundai Motor opens Georgia battery line', koTitle: '현대차, 조지아 배터리 라인 가동', beatCompanies: ['현대차'], titleCompanies: ['현대차'], checkTerms: ['배터리'] }),
    it('gl:ko', { title: 'Korean automaker opens plant', koTitle: '현대차, 멕시코 공장 가동', beatCompanies: ['현대차'], titleCompanies: [], checkTerms: ['공장'] }),
    // 11-10 운영: 제목 주체는 기아 — 출입처 목록 순서(현대차 먼저)가 아니라 제목에 나온 회사로 대조
    it('gl:kia', { title: 'Kia to build new EV plant in Gwangju', koTitle: '기아, 광주에 새 전기차 공장 짓는다', beatCompanies: ['현대차', '기아'], titleCompanies: ['기아'], checkTerms: ['공장'] }),
    // 11-10 운영: 나라 이름 없는 외신 — 제목의 라틴 고유어(HTWO)가 기사에 있어야 같은 건(MOU·회사 영문 이름은 고유어 아님)
    it('gl:htwo', { title: 'HTWO Guangzhou and Air Liquide China sign hydrogen mobility MoU', koTitle: '현대차 HTWO 광저우와 에어리퀴드 차이나, 수소 모빌리티 MOU 체결',
      beatCompanies: ['현대차'], titleCompanies: [], checkTerms: ['MOU'] }),
    it('gl:pv5', { title: 'Kia reveals UK prices for PV5 Chassis', koTitle: '기아, PV5 Chassis 및 고성능 EV 밴 가격 공개', beatCompanies: ['기아'], titleCompanies: ['기아'], checkTerms: ['투자'] })] };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/global-beat', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const r = await call('radar_today', { include_minor: true }, opts);
  const b = r.text.split('[B · ')[1].split('[C · ')[0];
  assert.match(b, /출입처 외신 · 두산에너빌리티\n   외신 World Nuclear News 「두산, 뉴스케일 소형모듈원전 상부 원자로 용기 제작」 — 두산에너빌리티가 뉴스케일파워와[^\n]*원제 "Doosan to manufacture upper reactor vessel for NuScale SMR" \(AI 번역·요약 — 원문 확인\)/);
  assert.match(r.text.split('[C · ')[1], /넥센타이어, 에코바디스 골드 3년 연속[^\n]*· ⚠ 원문 발췌에 없는 숫자: 30억 원 — 기사에 쓰기 전 원문 대조/);
  assert.doesNotMatch(b, /원문 발췌에 없는 숫자/);   // 숫자가 다 맞으면 표시 없음
  assert.doesNotMatch(r.text, /오래된 기사/);
  assert.doesNotMatch(r.text, /출입처 외신: /);   // 수집 상태 정상
  const items = await (await radarItems(new Request(ORIGIN + '/ingest/radar-items?hours=72', { headers: { Authorization: `Bearer ${TOKEN}` } }), env, { now: NOW })).json();
  const hit = items.items.find((x) => x.id === 'gl:a');
  assert.deepEqual([hit.tier, hit.check.who, hit.check.terms, hit.check.alts['원자로'].includes('SMR')], ['B', '두산에너빌리티', ['원자로'], true]);
  assert.ok(!items.items.find((x) => x.id === 'gl:b'));   // 참고(C)는 보도 대조 안 함
  const cz = items.items.find((x) => x.id === 'gl:cz');
  assert.deepEqual([cz.check.terms, cz.check.places, cz.check.must], [['원자로', '체코'], ['체코'], ['체코']]);
  // 외신은 국내 기사보다 늦게 나오는 일이 많아 대조 시작을 게재일 7일 전으로(대조기가 3일을 더 당긴다)
  assert.equal(cz.check.since, new Date(Date.parse(now) - 7 * 86400000 + 9 * 3600000).toISOString().slice(0, 10));
  // 美로 줄이는 '미국'은 필수어로 쓰지 않고, 기사에도 그대로 나오는 주 이름(앨라배마)을 둘째 낱말·필수어로(11-03 운영: "현대차 투자"가 새만금 기사를 잡음)
  const us = items.items.find((x) => x.id === 'gl:us');
  assert.deepEqual([us.check.terms, us.check.places, us.check.must], [['공장', '앨라배마', '투자'], ['앨라배마'], ['앨라배마']]);
  // '인도네시아'를 '인도'로 자르지 않고, '인도량'(차량 인도)은 나라로 보지 않는다
  assert.deepEqual(items.items.find((x) => x.id === 'gl:id').check.must, ['인도네시아']);
  assert.equal(items.items.find((x) => x.id === 'gl:dl').check.must, undefined);
  assert.ok(!items.items.find((x) => x.id === 'gl:af'));
  assert.match(r.text.split('[C · ')[1], /⚠ 본문 첫머리 주체가 계열사\(포스코퓨처엠\) — 출입처 외일 수 있음 · 외신 World Nuclear News 「포스코, LG에너지솔루션에 신규 배터리 소재 공급」/);
  assert.ok(!items.items.find((x) => x.id === 'gl:honda'));
  assert.match(r.text.split('[C · ')[1], /⚠ 출입처 이름\(현대차\)이 제목엔 없고 본문에만 — 다른 회사 기사일 수 있음 · 외신 World Nuclear News 「혼다, 30억달러 규모 오하이오 조립 공장 신설」/);
  assert.equal(items.items.find((x) => x.id === 'gl:hy').tier, 'B');
  assert.equal(items.items.find((x) => x.id === 'gl:ko').tier, 'B');   // 영어 제목엔 없어도 한국어 제목에 출입처가 있으면 B
  // 11-11: 달러 금액의 원화 환산(한국은행 매매기준율로 코드가 계산)
  assert.match(b, /현대차, 4억 5천만 달러 미국 앨라배마 공장 투자[^\n]*· 원화 환산\(자동, 한국은행 매매기준율 원\/달러 1,462\.3\(2026-11-10\)\): 4억 5천만 달러\(약 6580억원\)/);
  // 유로·엔은 그 통화 환율, 환율이 없는 통화(파운드)는 빼고 적는다
  assert.match(b, /현대차, 체코 공장에 20억유로 투자[^\n]*· 원화 환산\(자동, 한국은행 매매기준율 원\/유로 1,550\.2\(2026-11-10\) · 원\/100엔 905\.1\(2026-11-10\)\): 20억유로\(약 3조1004억원\), 1조엔\(약 9조51억원\)(?!, 5억파운드)/);
  const kia = items.items.find((x) => x.id === 'gl:kia');
  assert.deepEqual([kia.check.who, kia.company], ['기아', '기아·현대차']);
  assert.equal(kia.check.must, undefined);                                                   // 라틴 고유어 없음 — 예전대로
  assert.deepEqual(items.items.find((x) => x.id === 'gl:htwo').check.must, ['HTWO']);
  assert.deepEqual(items.items.find((x) => x.id === 'gl:pv5').check.must, ['PV5', 'Chassis']);   // EV는 흔한 약어
  assert.deepEqual(us.check.must, ['앨라배마']);                                                // 나라·주 이름이 있으면 그것만(예전대로)
});

test('미국 주 환경 허가·공고(us-state-env): radar_today에 허가 신청 A·제재 B, us_litigation 구역에 기준선·신규', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const now = new Date(NOW.getTime() - 3600000).toISOString();
  const old = new Date(NOW.getTime() - 5 * 86400000).toISOString();
  const doc = { schema: 'us_state_env/v1', generatedAt: now, status: 'complete',
    checks: [{ source: '조지아 EPD 주간 공고', status: 'ok', returned: 2 }, { source: '앨라배마 ADEM 공고', status: 'ok', returned: 38 }, { source: '루이지애나 LDEQ 공고', status: 'ok', returned: 20 }],
    notices: [
      { id: 'ga:30376:pa1026-1', source: 'ga', state: '조지아', company: '한화솔루션', facility: 'Hanwha Q Cells Georgia, Inc.', county: 'Bartow', address: '100 Qcells Pkwy, White, 30184',
        noticeType: 'Permit Application', appNo: '30376', operation: 'Semiconductors and Related Devices', reason: 'The addition of a rotary concentrator, a regenerative thermal oxidizer',
        deadline: '2026-11-06', week: '2026-10-05', code: 'pa1026-1', url: 'https://epd.georgia.gov/document/document/pa1026-1/download', firstSeen: old, baseline: true },
      { id: 'ga:29866:pa1126-1', source: 'ga', state: '조지아', company: '현대차', facility: 'Hyundai Motor Group Metaplant America LLC', county: 'Bryan', noticeType: 'Proposed Permit',
        appNo: '29866', reason: 'Construction of a second paint shop', deadline: '2026-12-04', code: 'pa1126-1', url: 'https://epd.georgia.gov/document/document/pa1126-1/download', firstSeen: now },
      { id: 'gap:3711-029-0015-P-02-0', source: 'gap', state: '조지아', company: '현대차', facility: 'Hyundai Motor Group Metaplant America LLC', fid: '029-00015',
        permit: '3711-029-0015-P-02-0', issued: '2026-10-20', permitType: 'PSD/NSR', noticeType: '대기 허가 발급(PSD/NSR)', reason: '', operation: '',
        docs: [{ label: 'Narrative', url: 'https://air.gaepd.org/Permits/View/ON-31000' }], url: 'https://air.gaepd.org/Permits/View/OP-31000', firstSeen: now },
      { id: 'laci:20240515-A-ITE:2026-12-10', source: 'laci', state: '루이지애나', company: '롯데케미칼', facility: 'Lotte Chemical Louisiana LLC Calcasieu', appNo: '20240515-A-ITE',
        meeting: '2026-12-10', amount: '$3,902,899', noticeType: '상공위원회 안건(세제 감면·고용 인센티브)', reason: '20240515-A-ITE Lotte Chemical Louisiana LLC Calcasieu $3,902,899 $95,000 12',
        url: 'https://admin.opportunitylouisiana.gov/wp-content/uploads/2026/11/CI-Agenda-PUBVer-DEC-10-2026.pdf', firstSeen: now }],
    events: [
      { id: 'ga:29866:pa1126-1', kind: '주 환경청 허가·공고', tier: 'A', company: '현대차', state: '조지아', detectedAt: now, url: 'https://epd.georgia.gov/document/document/pa1126-1/download',
        text: '조지아 주간 공고 pa1126-1 · Hyundai Motor Group Metaplant America LLC(Bryan County) · Proposed Permit · 신청 29866 · 이유 「Construction of a second paint shop」 — 신설·증설 낱말이 있는 신청(회사 확인) · 주 정부 공개 공고(허가 신청≠착공·투자 확정)' },
      { id: 'adem:11-26hpt.html', kind: '주 환경청 제재 공고', tier: 'B', company: 'HD현대일렉트릭', state: '앨라배마', detectedAt: now, url: 'https://adem.alabama.gov/sites/default/files/2026-11/11-26hpt.html',
        text: '앨라배마 공고 · Hyundai Power Transformers USA, Inc. · 동의명령(제재)' }] };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/us-state-env', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const r = await call('radar_today', { include_minor: true }, opts);
  assert.match(r.text.split('[A · ')[1].split('[B · ')[0], /미국 주 환경 허가·공고 · 현대차\n   조지아 주간 공고 pa1126-1 · Hyundai Motor Group Metaplant/);
  assert.match(r.text.split('[B · ')[1].split('[C · ')[0], /미국 주 환경 허가·공고 · HD현대일렉트릭\n   앨라배마 공고 · Hyundai Power Transformers USA, Inc\. · 동의명령\(제재\)/);
  assert.doesNotMatch(r.text, /Hanwha Q Cells/);   // 기준선은 레이더 새 항목이 아니다
  const items = await (await radarItems(new Request(ORIGIN + '/ingest/radar-items?hours=72', { headers: { Authorization: `Bearer ${TOKEN}` } }), env, { now: NOW })).json();
  const hit = items.items.find((x) => x.id === 'ga:29866:pa1126-1');
  assert.deepEqual([hit.check.who, hit.check.terms, hit.check.must], ['현대차', ['조지아', '허가'], ['조지아']]);
  const u = await call('us_litigation', {}, opts);
  assert.match(u.text, /\[미국 주 환경 허가·공고 · 출입처 미국 공장 · 확인 [^\]]+\] 4건 · 원천 조지아 EPD 주간 공고 ok · 앨라배마 ADEM 공고 ok · 루이지애나 LDEQ 공고 ok/);
  assert.match(u.text, /- \[기준선\] 조지아 · 한화솔루션 · Hanwha Q Cells Georgia, Inc\.\(Bartow County · 100 Qcells Pkwy, White, 30184\) · Permit Application · 신청 30376 · 공고 주 2026-10-05 · 의견 마감 2026-11-06/);
  assert.match(u.text, /- \[신규\] 조지아 · 현대차 · Hyundai Motor Group Metaplant America LLC/);
  assert.match(u.text, /신청 이유: 「The addition of a rotary concentrator/);
  assert.match(u.text, /- 조지아 · 현대차 · Hyundai Motor Group Metaplant America LLC · 대기 허가 발급\(PSD\/NSR\) · 허가 3711-029-0015-P-02-0\(시설 029-00015\) · 발급 2026-10-20\n   원문: https:\/\/air\.gaepd\.org\/Permits\/View\/OP-31000\n   문서: Narrative https:\/\/air\.gaepd\.org\/Permits\/View\/ON-31000/);
  assert.match(u.text, /- 루이지애나 · 롯데케미칼 · Lotte Chemical Louisiana LLC Calcasieu · 상공위원회 안건\(세제 감면·고용 인센티브\) · 신청 20240515-A-ITE · 회의 2026-12-10 · 금액 칸 첫 값 \$3,902,899\n   안건 줄: 「20240515-A-ITE Lotte/);
  assert.match(u.text, /\] 4건 · 원천/);
});

test('노동위 회의(kr-labor): radar_today에 조정·부당노동행위 A·해고 B, kr_official labor 구역에 상한·사건, 보도 대조 낱말', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const now = new Date(NOW.getTime() - 3600000).toISOString();
  const u = (id) => `https://www.nlrc.go.kr/nlrc/gyeongbuk/meetingSche/detail.do?mtgId=${id}&mtgSn=1&mtgYmd=20261026&cmitCd=06`;
  const n = (no, company, tier, name, meeting, cmit) => ({ id: `labor:06:${no}:2026-10-26`, company, commission: '경북', commissionName: cmit, meeting, day: '2026-10-26', time: '14:00',
    caseNo: no, caseName: name, party: name.split(' 노동')[0], tier, url: u(no), firstSeen: now });
  const notices = [n('2026조정88', '포스코', 'A', '주식회사 포스코 노동쟁의 조정신청사건', '1차조정회의', '경북지방노동위원회'),
    n('2026부해900', '현대차', 'B', '현대자동차 주식회사 부당해고 구제신청', '심판회의', '경북지방노동위원회')];
  const doc = { schema: 'kr_labor/v1', generatedAt: now, status: 'complete',
    checks: [{ source: '중앙노동위원회', status: 'ok', returned: 5, note: '첫 화면 5건 상한 — 뒤 회의가 빠졌을 수 있음' }, { source: '충남지방노동위원회', status: 'ok', returned: 5, note: '첫 화면 5건 상한 — 뒤 회의가 빠졌을 수 있음' },
      { source: '경북지방노동위원회', status: 'ok', returned: 3 }, { source: '서울지방노동위원회', status: 'failed', error: 'ConnectTimeout: x' },
      { source: '경남지방노동위원회', status: 'partial', returned: 4, error: '회의 상세 1건 읽기 실패' }],
    counts: { meetings: 43, details: 43, cases: 87, '조정 사건': 5 }, seen: {}, notices,
    events: [
      { id: notices[0].id, tier: 'A', kind: '노동위 조정 회의', company: '포스코', commission: '경북지방노동위원회', caseNo: '2026조정88', word: '노동쟁의', url: notices[0].url, detectedAt: now,
        text: '경북지방노동위원회 1차조정회의 2026-10-26 14:00 · 사건 2026조정88 「주식회사 포스코 노동쟁의 조정신청사건」 · 노동위 회의 일정(공개) — 사건명은 신청 주장, 내용·결정은 위원회·당사자 확인' },
      { id: notices[1].id, tier: 'B', kind: '노동위 심판 회의', company: '현대차', commission: '경북지방노동위원회', caseNo: '2026부해900', word: '부당해고', url: notices[1].url, detectedAt: now,
        text: '경북지방노동위원회 심판회의 2026-10-26 14:00 · 사건 2026부해900 「현대자동차 주식회사 부당해고 구제신청」 · 노동위 회의 일정(공개)' }],
    rules: ['사건명은 신청인 주장이다.'] };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/kr-labor', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const r = await call('radar_today', {}, opts);
  assert.match(r.text.split('[A · ')[1].split('[B · ')[0], /노동위 회의\(조정·심판\) · 포스코\n   경북지방노동위원회 1차조정회의 2026-10-26 14:00 · 사건 2026조정88/);
  assert.match(r.text.split('[B · ')[1], /노동위 회의\(조정·심판\) · 현대차\n   경북지방노동위원회 심판회의/);
  const items = await (await radarItems(new Request(ORIGIN + '/ingest/radar-items?hours=72', { headers: { Authorization: `Bearer ${TOKEN}` } }), env, { now: NOW })).json();
  const hit = items.items.find((x) => x.id === notices[0].id);
  assert.deepEqual([hit.check.who, hit.check.terms, hit.check.alts['노동쟁의'].slice(0, 2)], ['포스코', ['노동쟁의'], ['쟁의', '파업']]);
  const k = await call('kr_official', { section: 'labor' }, opts);
  assert.match(k.text, /\[노동위 회의\(조정·심판\) · 출입처가 사건 당사자 · 확인 [^\]]+\]/);
  assert.match(k.text, /원천: 노동위원회 3\/5곳 정상 · 이번 실행 첫 화면 회의 43건 · 오늘 읽은 회의 상세 43건\(사건 87, 조정 5\) · 미확인\(0건 아님\): 서울지방노동위원회 · 일부 미확인: 경남지노위\(회의 상세 1건 읽기 실패\) · 첫 화면 5건 상한\(뒤 회의 빠졌을 수 있음\): 중노위, 충남지노위/);
  assert.match(k.text, /- 출입처 사건 · 최근 30일 2건\n  A · 2026-10-26 14:00 · 포스코 · 경북지방노동위원회 1차조정회의 · 사건 2026조정88 「주식회사 포스코 노동쟁의 조정신청사건」\n     원문: https:\/\/www\.nlrc\.go\.kr\/nlrc\/gyeongbuk\/meetingSche\/detail\.do\?mtgId=2026조정88/);
  assert.match((await call('kr_official', {}, opts)).text, /\[노동위 회의\(조정·심판\)/);   // section 없이도 붙는다
  assert.doesNotMatch((await call('kr_official', { section: 'labor', company: '포스코' }, opts)).text, /현대자동차 주식회사/);
});

test('인도 법인 공시(india-filings): radar_today에 설비 A·이사회 B, 대조 낱말에 인도 필수, partner_filings 구역(NSE)', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const now = new Date(NOW.getTime() - 3600000).toISOString();
  const f = (id, tier, subject, desc, extra = {}) => ({ id, company: '현대차(인도 법인)', issuer: 'Hyundai Motor India Limited', subject, desc, tier,
    published: now, url: `https://nsearchives.nseindia.com/corporate/${id.slice(4)}`, firstSeen: now, ...extra });
  const filings = [f('nse:HMILNSE_cap.pdf', 'A', 'Updates', 'Hyundai Motor India Limited has informed the Exchange regarding capacity expansion at Talegaon plant.',
      { excerpt: 'Talegaon plant capacity will be increased' }),
    f('nse:HMILNSE_board.pdf', 'B', 'Outcome of Board Meeting', 'Hyundai Motor India Limited has informed the Exchange regarding Board meeting held on November 04, 2026.'),
    f('nse:HMILNSE_tr.pdf', 'C', 'Analysts/Institutional Investor Meet/Con. Call Updates', 'Hyundai Motor India Limited has informed the Exchange about Transcript', { baseline: true })];
  const ev = (x) => ({ id: x.id, tier: x.tier, kind: '인도 법인 공시', company: x.company, detectedAt: now, url: x.url, subject: x.subject,
    text: `Hyundai Motor India Limited NSE 공시 · ${x.subject} · 「${x.desc}」 · 거래소 공시 원문(PDF) 확인 — 현대차 자회사(별도 상장사)` });
  const doc = { schema: 'india_filings/v1', generatedAt: now, status: 'complete', span: { oldest: now, newest: now },
    checks: [{ source: 'NSE 공시 RSS', status: 'ok', returned: 1405, note: 'RSS가 덮는 시간 2026-11-03T03:30 ~ 2026-11-03T21:03' }],
    filings, events: [ev(filings[0]), ev(filings[1])], rules: ['NSE 공시 RSS에서 현대차 인도법인 공시만.'] };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/india-filings', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const r = await call('radar_today', {}, opts);
  assert.match(r.text.split('[A · ')[1].split('[B · ')[0], /인도 법인 공시\(현대차 인도\) · 현대차\(인도 법인\)\n   Hyundai Motor India Limited NSE 공시 · Updates/);
  assert.match(r.text.split('[B · ')[1], /인도 법인 공시\(현대차 인도\) · 현대차\(인도 법인\)\n   Hyundai Motor India Limited NSE 공시 · Outcome of Board Meeting/);
  const items = await (await radarItems(new Request(ORIGIN + '/ingest/radar-items?hours=72', { headers: { Authorization: `Bearer ${TOKEN}` } }), env, { now: NOW })).json();
  const cap = items.items.find((x) => x.id === 'nse:HMILNSE_cap.pdf');
  assert.deepEqual([cap.check.who, cap.check.terms, cap.check.must], ['현대차', ['인도', '공장'], ['인도']]);
  assert.deepEqual(items.items.find((x) => x.id === 'nse:HMILNSE_board.pdf').check.terms, ['인도', '이사회']);
  const nse = await call('partner_filings', { source: 'NSE' }, opts);
  assert.match(nse.text, /\[인도 법인 공시 · 현대차 인도법인\(NSE\) · 확인 [^\]]+\] 2건 · 원천 NSE 공시 RSS ok · RSS가 덮는 시간 2026-11-03T03:30 ~ 2026-11-03T21:03/);
  assert.match(nse.text, /- \[신규\] A · [^\n]+ KST · Hyundai Motor India Limited · Updates\n   설명: 「Hyundai Motor India Limited has informed the Exchange regarding capacity expansion at Talegaon plant\.」\n   첨부 첫머리: 「Talegaon plant capacity will be increased」/);
  assert.match(nse.text, /C 1건 숨김 — include_routine=true/);
  assert.doesNotMatch(nse.text, /Transcript/);
  assert.match((await call('partner_filings', { source: 'NSE', include_routine: true }, opts)).text, /\[기준선\] C · [^\n]+ · Analysts\/Institutional Investor Meet/);
  assert.match((await call('partner_filings', {}, opts)).text, /\[인도 법인 공시 · 현대차 인도법인\(NSE\)/);   // source 비우면 함께
});

test('임원 명단 변화(kr-exec): radar_today A·B(사람 이름 필수 대조), kr_signals exec 구역·C 접음·미제출 미확인', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const now = new Date(NOW.getTime() - 3600000).toISOString();
  const ev = (key, tier, kind, text, person, flags = []) => ({ id: `exec:00138242:202611014:${key}`, tier, kind, company: 'KG모빌리티', dartName: 'KG모빌리티',
    corpCode: '00138242', key, person, flags, text, url: 'https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261114000002', baseUrl: 'https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260814000002',
    period: '2026년 3분기(9-30 기준)', base: '2026년 반기(6-30 기준)', season: 'mid', detectedAt: now });
  const doc = { schema: 'kr_exec/v1', generatedAt: now, status: 'partial', season: 'mid',
    period: { year: 2026, report: '11014', label: '2026년 3분기(9-30 기준)', base: { year: 2026, report: '11012', label: '2026년 반기(6-30 기준)' }, deadline: '2026-11-14' },
    checks: [{ source: 'KG모빌리티', status: 'ok', coverage: '원문 표(등기 3·미등기 33)', baseCoverage: '원문 표(등기 3·미등기 31)' },
      { source: '현대제철', status: 'ok', coverage: 'API 줄만(등기 9·미등기 0) — 원문에서 임원 표를 못 찾음' }, { source: '기아', status: 'no_data', note: '3분기 미제출' }],
    counts: { companies: 3, filed: 2, notFiled: 1, failed: 0, waiting: 0, newEvents: 3, A: 1, B: 0, C: 2 }, seen: {}, rosters: {},
    events: [ev('새 임원|유경쟁|197405', 'A', '새 임원', 'KG모빌리티 2026년 3분기(9-30 기준) 임원 명단에 새로 보임 — 유경쟁 1974년생 상무(미등기·상근) · 경력 「현대자동차 글로벌KD사업실장」 · 2026년 반기(6-30 기준)에는 없음',
      { name: '유경쟁', ofcps: '상무', reg: '미등기' }, [{ kind: '경쟁사 출신', text: "경력에 다른 출입처 '현대자동차'" }]),
    ev('명단에서 빠짐|김보통|197001', 'C', '명단에서 빠짐', 'KG모빌리티 2026년 3분기(9-30 기준) 임원 명단에서 빠짐 — 2026년 반기(6-30 기준) 김보통 1970년생 상무(미등기)', { name: '김보통' }),
    ev('count', 'C', '임원 수 변화', 'KG모빌리티 미등기 임원 31→33명', null)], rules: ["'새로 보임'은 두 기준일 사이 변화일 뿐 선임일·사유가 아니다 — 회사 확인."] };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/kr-exec', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const r = await call('radar_today', {}, opts);
  assert.match(r.text.split('[A · ')[1].split('[B · ')[0], /임원 명단 변화\(정기보고서\) · KG모빌리티\n   KG모빌리티 2026년 3분기\(9-30 기준\) 임원 명단에 새로 보임 — 유경쟁 1974년생 상무\(미등기·상근\) · 경력 「현대자동차 글로벌KD사업실장」 · 2026년 반기\(6-30 기준\)에는 없음 〔표시: 경력에 다른 출입처 '현대자동차'〕 \(보고서 명단 비교 — 선임일·영입 경위·사유는 회사 확인\)/);
  assert.doesNotMatch(r.text, /김보통/);
  const radar = await (await radarItems(new Request(ORIGIN + '/ingest/radar-items?hours=72', { headers: { Authorization: `Bearer ${TOKEN}` } }), env, { now: NOW })).json();
  const hit = radar.items.find((x) => x.id === 'exec:00138242:202611014:새 임원|유경쟁|197405');
  assert.deepEqual([hit.check.who, hit.check.terms, hit.check.must, hit.check.alts['인사'].slice(0, 3)], ['KG모빌리티', ['유경쟁', '인사'], ['유경쟁'], ['인사', '영입', '선임']]);
  const k = await call('kr_signals', { section: 'exec' }, opts);
  assert.match(k.text, /\[임원 명단 변화 · 2026년 3분기\(9-30 기준\) ← 2026년 반기\(6-30 기준\) · 확인 [^\]]+ · 최근 60일\] A 1 · B 0 · C 2\(C는 show_all=true 또는 company 낱말로\)/);
  assert.match(k.text, /원천: OpenDART 정기보고서 임원 현황 · 제출 2\/3곳 · 마감 2026-11-14 · 미제출 1곳\(기아\)/);
  assert.match(k.text, /범위: 현대제철는 원문 표를 못 읽어 API 줄\(등기임원\)만 비교 — 미등기 임원 변화는 미확인/);
  assert.match(k.text, /- \[신규\] A · [\d-]+ [\d:]+ · KG모빌리티 · 새 임원\n   잡힌 사실: KG모빌리티 2026년 3분기[^\n]+\n   표시: 경쟁사 출신 — 경력에 다른 출입처 '현대자동차'\n   원문: https:\/\/dart\.fss\.or\.kr\/dsaf001\/main\.do\?rcpNo=20261114000002 \(앞 보고서 https:\/\/dart\.fss\.or\.kr\/dsaf001\/main\.do\?rcpNo=20260814000002\)/);
  assert.doesNotMatch(k.text, /김보통/);
  assert.match((await call('kr_signals', { section: 'exec', show_all: true }, opts)).text, /C · [\d-]+ [\d:]+ · KG모빌리티 · 명단에서 빠짐/);
  assert.match((await call('kr_signals', { section: 'exec', company: '김보통' }, opts)).text, /김보통 1970년생 상무/);
  assert.match((await call('kr_signals', {}, opts)).text, /\[임원 명단 변화 · 2026년 3분기\(9-30 기준\) ← 2026년 반기\(6-30 기준\) · 확인 [^\]]+ · 최근 14일\] A 1/);
});

test('수시 임원 공시·타사 임원 명단(kr-exec-market): radar_today A·B, kr_signals exec 아래 붙음', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const now = new Date(NOW.getTime() - 3600000).toISOString();
  const doc = { schema: 'kr_exec_market/v1', generatedAt: now, status: 'complete',
    checks: [{ source: '공시 목록 기타공시(독립이사 신고·소집공고)', status: 'ok', returned: 120 }, { source: '수시 임원 공시 원문', status: 'ok', returned: 3 },
      { source: '상장사 등기임원 명단 순환', status: 'ok', returned: 400, covered: 800, universe: 4013 }],
    counts: { listed: 160, picked: 3, opened: 3, newEvents: 3, A: 1, B: 1, C: 1 }, seen: {}, industry: {}, companies: {}, cursor: 400,
    alumni: { '00999001': [{ company: '부품사', name: '김전무', birth: '1962', ofcps: '사외이사', reg: '사외이사', beats: ['현대차'], senior: true, text: '현대자동차 구매본부장(전무)', period: '202611012' }],
      '00999005': [{ company: '철강상사', name: '정상무', birth: '1966', ofcps: '대표이사', reg: '사내이사', beats: ['포스코'], senior: false, text: '포스코 마케팅본부 상무', period: '202611012' }] },
    events: [
      { id: 'execm:20260225005348|이승조', tier: 'A', kind: '이사 후보', company: '현대차', source: '주총 소집공고', detectedAt: now, url: 'https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260225005348',
        text: '현대차 주총 소집공고(2026-02-25) 이사 후보 — 이승조 1969년생 사내이사', person: { name: '이승조' },
        flags: [{ kind: '결격·부실 칸', text: '부실기업 경영진 여부 칸 「○○건설(2019 회생절차) 사내이사 재직」(회사 기재 그대로)' }] },
      { id: 'execm:20261104000229|appointed|김전무', tier: 'B', kind: '독립이사 선임', company: '부품사', beat: '현대차', source: '독립이사 신고', detectedAt: now,
        url: 'https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261104000229', text: '부품사 독립이사 선임 신고(2026-11-04 접수) — 김전무 1962년생 · 경력 「현대자동차 구매본부장(전무)」',
        person: { name: '김전무' }, flags: [{ kind: '출입처 출신', text: '경력 「현대자동차 구매본부장(전무)」 · 같은 업종 회사' }] },
      { id: 'execm:00999009|202611012|x', tier: 'C', kind: '타사 등기임원', company: '작은회사', source: '임원 현황', detectedAt: now, url: 'https://dart.fss.or.kr/x', text: '작은회사 … 박작은', person: { name: '박작은' }, flags: [] },
      { id: 'execm:20260811000705|지난후보', tier: 'B', kind: '이사 후보', company: '고려아연', source: '주총 소집공고', detectedAt: now, baseline: true, filed: '2026-08-11',
        url: 'https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260811000705', text: '고려아연 주총 소집공고(2026-08-11) 이사 후보 — 지난후보 1960년생 독립이사', person: { name: '지난후보' },
        flags: [{ kind: '전관', text: '경력에 \'판사\'' }] }],
    rules: ['조회 실패·한도로 못 본 공시·회사는 0건이 아니라 미확인.'] };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/kr-exec-market', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const r = await call('radar_today', {}, opts);
  assert.match(r.text.split('[A · ')[1].split('[B · ')[0], /수시 임원 공시·타사 임원 명단 · 현대차\n   현대차 주총 소집공고\(2026-02-25\) 이사 후보 — 이승조 1969년생 사내이사 〔표시: 부실기업 경영진 여부 칸/);
  assert.match(r.text, /수시 임원 공시·타사 임원 명단 · 부품사\n   부품사 독립이사 선임 신고/);
  assert.doesNotMatch(r.text, /박작은/);
  assert.doesNotMatch(r.text, /지난후보/);                       // 지난 소집공고 되짚기 항목은 오늘의 레이더에 안 올림
  const radar = await (await radarItems(new Request(ORIGIN + '/ingest/radar-items?hours=72', { headers: { Authorization: `Bearer ${TOKEN}` } }), env, { now: NOW })).json();
  const hit = radar.items.find((x) => x.id === 'execm:20261104000229|appointed|김전무');
  assert.deepEqual([hit.check.who, hit.check.terms, hit.check.must], ['부품사', ['김전무', '인사'], ['김전무']]);
  const k = await call('kr_signals', { section: 'exec' }, opts);
  assert.match(k.text, /\[임원 명단 변화\(정기보고서\)\] 아직 수집 전/);
  assert.match(k.text, /\[수시 임원 공시·타사 임원 명단 · 확인 [^\]]+ · 최근 60일\] A 1 · B 2 · C 1\(C는 show_all=true 또는 company 낱말로\)/);
  assert.match(k.text, /명단 순환 800\/4013곳 본 적 있음\(처음 본 회사는 기준선\)/);
  assert.match(k.text, /- \[신규\] B · [\d-]+ [\d:]+ · 부품사 · 독립이사 신고 독립이사 선임 · 출입처 현대차 출신\n   잡힌 사실: 부품사 독립이사 선임 신고/);
  assert.doesNotMatch(k.text, /박작은/);
  assert.match((await call('kr_signals', { section: 'exec', company: '박작은' }, opts)).text, /작은회사 … 박작은/);
  assert.match(k.text, /- \[지난 공고·기준선\] B · [\d-]+ [\d:]+ · 고려아연 · 주총 소집공고 이사 후보/);
  assert.match(k.text, /\[출입처 출신 타사 등기임원 현황 · 명단 순환 800\/4013곳 기준\] 2명 — 현대차 1 · 포스코 1/);
  const ph = (await call('kr_signals', { section: 'exec', company: '포스코' }, opts)).text;
  assert.match(ph, /- 철강상사 · 정상무 1966년생 대표이사\(사내이사\) · 포스코 출신 · 경력 「포스코 마케팅본부 상무」/);
  assert.doesNotMatch(ph, /- 부품사 · 김전무/);
});

test('등급 조정(11-13 기자 결정): 타사 임원 명단 속 출입처 출신은 한 단계 내리고, 해외 파트너 공시는 본문 대목을 붙이며 대목 없는 것은 A를 주지 않는다', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const now = new Date(NOW.getTime() - 3600000).toISOString();
  const post = async (feed, doc) => assert.equal((await worker.fetch(new Request(ORIGIN + `/ingest/${feed}`, { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  // 11-13 운영 A 16건 중 3건: 다른 회사 3분기 임원 명단에 출입처 출신이 새로 보임(애경산업·씨케이솔루션·에이팩트)
  await post('kr-exec-market', { schema: 'kr_exec_market/v1', generatedAt: now, status: 'complete', checks: [{ source: 'DART 임원 현황', status: 'ok' }], roster: {}, rosterMeta: {}, counts: {},
    events: [{ id: 'execm:00139454|202611014|정인철|196307', tier: 'A', kind: '타사 등기임원', company: '애경산업', source: '임원 현황', detectedAt: now, url: 'https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261112000347',
        text: '애경산업 2026년 3분기 등기임원 명단에 새로 보임 — 정인철 1963년생 기타비상무이사 · 출입처 태광 출신', person: { name: '정인철' }, flags: [] },
      { id: 'execm:01210677|202611014|박현식|196110', tier: 'B', kind: '타사 등기임원', company: '씨케이솔루션', source: '임원 현황', detectedAt: now, url: 'https://dart.fss.or.kr/y', text: '씨케이솔루션 … 박현식', person: { name: '박현식' }, flags: [] },
      { id: 'execm:20261110000111|ceo', tier: 'A', kind: '대표이사 변경', company: '부품사', source: '대표이사 변경', detectedAt: now, url: 'https://dart.fss.or.kr/z', text: '부품사 대표이사 변경 — 새 대표 김대표(전 현대모비스 부사장)', person: { name: '김대표' }, flags: [] }] });
  // 11-13 운영 A 3건: 'EDGAR X-Energy, Inc. (XE): 8-K EX-99.1'처럼 서류 이름만 떠서 무엇인지 알 수 없었다
  await post('partner-filings', { schema: 'partner_filings/v1', generatedAt: now, windowDays: 30, checks: [],
    items: [{ id: 'edgar:xe', source: 'EDGAR', filer: 'X-Energy, Inc.  (XE)', beat: ['두산에너빌리티'], date: '2026-10-25', title: '8-K EX-99.1', dealNear: true,
        snippet: 'X-energy and Doosan Enerbility   signed a reservation agreement for forgings and long-lead components for sixteen Xe-100 reactors.', url: 'https://sec/xe' },
      { id: 'edgar:nosnip', source: 'EDGAR', filer: 'GrowHub Ltd  (TGHL)', beat: ['현대차'], date: '2026-10-25', title: 'F-1 F-1', dealNear: true, url: 'https://sec/tghl' }] });
  const r = (await call('radar_today', {}, opts)).text;
  const a = r.split('[A · ')[1].split('[B · ')[0];
  const b = r.split('[B · ')[1].split('[C · ')[0];
  assert.doesNotMatch(a, /애경산업/);
  assert.match(b, /수시 임원 공시·타사 임원 명단 · 애경산업\n   애경산업 2026년 3분기 등기임원 명단에 새로 보임 — 정인철/);
  assert.doesNotMatch(r, /박현식/);                               // 수집기 B는 한 단계 내려 화면(kr_signals)에만
  assert.match(a, /수시 임원 공시·타사 임원 명단 · 부품사\n   부품사 대표이사 변경/);   // 대표이사 변경·이사 후보·독립이사 신고는 그대로
  assert.match(a, /해외 파트너 공시 · 두산에너빌리티\n   EDGAR X-Energy, Inc\.  \(XE\): 8-K EX-99\.1 · 본문 대목 「X-energy and Doosan Enerbility signed a reservation agreement for forgings/);
  assert.doesNotMatch(a, /GrowHub/);
  assert.match(b, /해외 파트너 공시 · 현대차\n   EDGAR GrowHub Ltd  \(TGHL\): F-1 F-1/);
  // 단독 데스크: 본문 대목이 붙은 파트너 공시는 약한 유형이 아니다(제목뿐인 것만 약한 유형)
  const d = (await call('scoop_desk', {}, opts)).text;
  assert.match(d, /- A · [^\n]*해외 파트너 공시 · 두산에너빌리티\n   EDGAR X-Energy/);
  assert.match(d, /약한 유형: 2건 — (?=[^\n]*다른 회사 임원 명단 속 출입처 출신 1)(?=[^\n]*해외 파트너 공시\(제목뿐\) 1)/);
});

test('문제 임원 점검(kr-exec-check): radar_today A·B(단서 표시), kr_signals exec 안 표시 있는 사람만', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const now = new Date(NOW.getTime() - 3600000).toISOString();
  const flag6 = { kind: '법정 한도: 재직 6년 초과 가능', tier: 'A', text: '재직기간 칸 「7년 2개월」 → 7년 2개월(2026년 반기(6-30 기준) 기준) — 상법 시행령 제34조⑤7호' };
  const news = { kind: '과거 논란 기사', tier: 'B', evidenceVersion: 'executive_article/v1', text: '「한빛카드, 소송 휘말려」(2025-01-02, \'소송\') — 같은 이름의 다른 사람일 수 있음, 기사 원문 확인' };
  const doc = { schema: 'kr_exec_check/v1', generatedAt: now, status: 'complete', checks: [{ source: '현대차', status: 'ok', returned: 12 }],
    counts: { people: 420, outside: 180, flagged: 2, A: 1, newEvents: 2, newsChecked: 250 },
    people: [
      { id: '현대자동차|김오래|195501', company: '현대차', name: '김오래', birth: '1955', ofcps: '이사', reg: '사외이사', report: '2026년 반기(6-30 기준)', url: 'https://dart.fss.or.kr/x1', flags: [flag6], news: [] },
      { id: '기아|박논란|196001', company: '기아', name: '박논란', birth: '1960', ofcps: '사장', reg: '미등기', report: '2026년 반기(6-30 기준)', url: 'https://dart.fss.or.kr/x2', flags: [news],
        news: [{ title: '한빛카드, 소송 휘말려', url: 'https://news.example/1', date: '2025-01-02' }] },
      { id: '기아|이무탈|197001', company: '기아', name: '이무탈', birth: '1970', ofcps: '이사', reg: '사외이사', report: '2026년 반기(6-30 기준)', url: 'https://dart.fss.or.kr/x3', flags: [], news: [],
        directorChecks: [{ org: '디비손보', status: 'confirmed', reg: '사외이사', report: '2026년 반기(6-30 기준)' }, { org: '에스부품', status: 'absent' }] }],
    events: [{ id: 'execc:aaaa', reviewStatus: 'active', tier: 'A', kind: flag6.kind, company: '현대차', detectedAt: now, url: 'https://dart.fss.or.kr/x1', person: { name: '김오래' }, flags: [flag6],
      text: `현대차 이사(사외이사) 김오래 1955년생 — ${flag6.kind}: ${flag6.text}` },
    { id: 'execc:bbbb', reviewStatus: 'active', tier: 'B', kind: news.kind, company: '기아', detectedAt: now, url: 'https://dart.fss.or.kr/x2', person: { name: '박논란' }, flags: [news],
      text: `기아 사장(미등기) 박논란 1960년생 — ${news.kind}: ${news.text}` }],
    rules: ['표시는 확인할 단서지 판정이 아니다.'] };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/kr-exec-check', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const r = await call('radar_today', {}, opts);
  assert.match(r.text.split('[A · ')[1].split('[B · ')[0], /문제 임원 점검 · 현대차\n   현대차 이사\(사외이사\) 김오래 1955년생 — 법정 한도: 재직 6년 초과 가능: 재직기간 칸 「7년 2개월」[^\n]*\(확인할 단서 — 결격·비위 단정 아님, 회사·당사자 확인\)/);
  const radar = await (await radarItems(new Request(ORIGIN + '/ingest/radar-items?hours=72', { headers: { Authorization: `Bearer ${TOKEN}` } }), env, { now: NOW })).json();
  assert.deepEqual(radar.items.find((x) => x.id === 'execc:aaaa').check.terms, ['김오래', '사외이사']);
  assert.deepEqual(radar.items.find((x) => x.id === 'execc:bbbb').check.terms, ['박논란', '논란']);
  const k = await call('kr_signals', { section: 'exec' }, opts);
  assert.match(k.text, /\[문제 임원 점검 · 확인 [^\]]+\] 점검 420명\(사외·독립이사 180\) · 표시 2명\(A 1\)/);
  assert.match(k.text, /- \[신규\] A · 현대차 · 김오래 1955년생 이사\(사외이사\) · 2026년 반기\(6-30 기준\)\n   법정 한도: 재직 6년 초과 가능: 재직기간 칸 「7년 2개월」/);
  assert.match(k.text, /- \[신규\] B · 기아 · 박논란 1960년생 사장\(미등기\)[^\n]*\n   과거 논란 기사: [^\n]+\n   기사: https:\/\/news\.example\/1/);
  assert.doesNotMatch(k.text, /이무탈/);
  // 표시가 없어도 이름으로 물으면 겸직 명단 대조 결과(왜 3호가 아닌지)를 보여 준다
  assert.match((await call('kr_signals', { section: 'exec', company: '이무탈' }, opts)).text,
    /표시 0명 · 참고 1명[\s\S]*- 참고 · 기아 · 이무탈 1970년생 이사\(사외이사\)[^\n]*\n   겸직 명단 대조\(3호 해당 안 됨\): 디비손보 명단 확인\(사외이사·2026년 반기\(6-30 기준\)\) \/ 에스부품 최근 명단에 없음/);
  assert.doesNotMatch((await call('kr_signals', { section: 'exec', company: '현대차' }, opts)).text, /박논란/);
  const legacy = structuredClone(doc);
  delete legacy.people[1].flags[0].evidenceVersion;
  delete legacy.events[1].flags[0].evidenceVersion;
  await worker.fetch(new Request(ORIGIN + '/ingest/kr-exec-check', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(legacy) }), env, {});
  const legacyRadar = await (await radarItems(new Request(ORIGIN + '/ingest/radar-items?hours=72', { headers: { Authorization: `Bearer ${TOKEN}` } }), env, { now: NOW })).json();
  assert(!legacyRadar.items.some((x) => x.id === 'execc:bbbb'));
  const legacyScreen = await call('kr_signals', { section: 'exec' }, opts);
  assert.match(legacyScreen.text, /미확인 · 기아 · 박논란/);
  assert.match(legacyScreen.text, /본문 확인: 미검증/);
  // C(본문 언급): 표시·알림 없이 목록에만 근거 문장과 함께
  const withC = structuredClone(doc);
  withC.people[2].news = [{ title: '한빛카드 정보 유출 논란', url: 'https://news.example/c', date: '2025-03-01',
    bodyReview: { status: 'context_mentioned', excerpt: '유출 당시 이무탈 한빛카드 부회장이 회사를 이끌었다', checkedAt: now } }];
  await worker.fetch(new Request(ORIGIN + '/ingest/kr-exec-check', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(withC) }), env, {});
  const cScreen = (await call('kr_signals', { section: 'exec' }, opts)).text;
  assert.match(cScreen, /표시 2명\(A 1\) · C\(본문 언급·공식 제재\) 1명/);
  assert.match(cScreen, /- C · 기아 · 이무탈[^\n]*\n(?:[^\n]*\n)*?   본문 확인: 본문 언급\(C[^\n]*\n   본문 언급: 유출 당시 이무탈 한빛카드 부회장이/);
  const cRadar = await (await radarItems(new Request(ORIGIN + '/ingest/radar-items?hours=72', { headers: { Authorization: `Bearer ${TOKEN}` } }), env, { now: NOW })).json();
  assert(!cRadar.items.some((x) => /이무탈/.test(JSON.stringify(x))));
  // 공식 제재(금감원·개인정보위 × 경력 칸 최고 경영 자리): 겹치고 무거우면 B 알림(대조 낱말 '제재'), 시점 미확인은 C 목록만
  const sanc = structuredClone(withC);
  const sflag = { kind: '공식 제재: 재임 중 소속 회사 제재', tier: 'B', text: '한빛카드 대표이사(경력 칸 2019~2021) — 개인정보위 2022-03-18 제재: 안전조치의무 — 과징금 7,088만원 — 공개 기록엔 개인 이름이 없음' };
  sanc.people[0].flags.push(sflag);
  sanc.people[0].sanctions = [{ agency: '개인정보위', org: '한빛카드', date: '2022-03-18', what: '안전조치의무', inst: '과징금 7,088만원', timing: 'overlap', strong: true, url: 'https://www.pipc.go.kr/x',
    career: { org: '한빛카드', role: '대표이사', start: 2019, end: 2021 } },
  { agency: '금감원', org: '오성증권㈜', date: '2015-01-01', timing: 'timing_unknown', strong: false, count: 3, first: '2013-02-01', last: '2015-01-01', url: 'https://www.fss.or.kr/y', career: { org: '오성증권', role: '사장', start: null, end: null, rosterAbsent: [2014, 2015] } },
  { agency: '금감원', org: '한빛은행', date: '2021-03-01', timing: 'overlap', strong: false, inst: '기관주의', violation: '2016-01~2018-09', violationOutside: true, ceoText: '…한빛은행은 前 은행장 甲 재임 중 내부통제기준을…', url: 'https://www.fss.or.kr/z', career: { org: '한빛은행', role: '은행장', start: 2020, end: 2021, source: '명단' } }];
  sanc.events.push({ id: 'execc:cccc', reviewStatus: 'active', tier: 'B', kind: sflag.kind, company: '현대차', detectedAt: now, url: 'https://dart.fss.or.kr/x1', person: { name: '김오래' }, flags: [sflag],
    text: `현대차 이사(사외이사) 김오래 1955년생 — ${sflag.kind}: ${sflag.text}` });
  await worker.fetch(new Request(ORIGIN + '/ingest/kr-exec-check', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(sanc) }), env, {});
  const sRadar = await (await radarItems(new Request(ORIGIN + '/ingest/radar-items?hours=72', { headers: { Authorization: `Bearer ${TOKEN}` } }), env, { now: NOW })).json();
  assert.deepEqual(sRadar.items.find((x) => x.id === 'execc:cccc').check.terms, ['김오래', '제재']);
  const sScreen = (await call('kr_signals', { section: 'exec', company: '김오래' }, opts)).text;
  assert.match(sScreen, /   공식 제재: 개인정보위 2022-03-18 한빛카드 — 안전조치의무 — 과징금 7,088만원 · 경력 「한빛카드 대표이사 2019~2021」 기간 겹침 · https:\/\/www\.pipc\.go\.kr\/x/);
  assert.match(sScreen, /   공식 제재\(C\): 금감원 오성증권㈜ 제재 3건\(2013-02-01~2015-01-01\) · 경력 「오성증권 사장 \?~\?」 재임 기간 미확인 · 그 회사 연말 등기임원 명단\(2014·2015\)에 없음/);
  assert.match(sScreen, /   공식 제재\(C\): 금감원 2021-03-01 한빛은행 — 기관주의 · 위반 기간 2016-01~2018-09\(재임 기간 밖\) · 사업보고서 임원 명단 「한빛은행 은행장 2020~2021」 기간 겹침/);
  assert.match(sScreen, /기간 겹침 · https:\/\/www\.fss\.or\.kr\/z\n     제재대상사실 최고 경영자 언급\(공개안엔 이름 없음 — 그 사람이라는 근거 아님\): 「…한빛은행은 前 은행장 甲 재임 중 내부통제기준을…」/);
  // 공정위 원문 요약(과징금·사건명·의결서 대표이사 칸)과 주총 이사 후보 점검
  const ftcDoc = structuredClone(sanc);
  ftcDoc.people[0].sanctions = [{ agency: '공정위', org: '한빛리테일', date: '2023-01-19', inst: '과징금', amount: '15억8200만원', title: '(주) 한빛리테일의 대규모유통업법 위반행위에 대한 건',
    ceoSurname: '김○○', timing: 'overlap', strong: true, url: 'https://case.ftc.go.kr/x', career: { org: '한빛리테일', role: '대표이사', start: 2016, end: 2024 } }];
  ftcDoc.candidates = [{ id: '후보|현대차|신후보|196005', company: '현대차', name: '신후보', birth: '1960', ofcps: '이사 후보', reg: '사외이사', report: '주총 소집공고 2026-11-01',
    url: 'https://dart.fss.or.kr/agm', flags: [{ kind: '이사 후보: 선임되면 다른 회사 이사·감사 2곳 이상(3호)', tier: 'A', text: '주총 소집공고 후보 — 같은 이름·출생년월이 다른 회사 등기임원 명단에 2곳' }] },
    { id: '후보|현대차|평온후보|197001', company: '현대차', name: '평온후보', birth: '1970', reg: '사내이사', report: '주총 소집공고 2026-11-01', flags: [] }];
  await worker.fetch(new Request(ORIGIN + '/ingest/kr-exec-check', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(ftcDoc) }), env, {});
  const fScreen = (await call('kr_signals', { section: 'exec' }, opts)).text;
  assert.match(fScreen, /공식 제재: 공정위 2023-01-19 한빛리테일 — 과징금 — 15억8200만원 — 「\(주\) 한빛리테일의 대규모유통업법 위반행위에 대한 건」 — 의결서 피심인 대표이사 칸 '김○○'\(성·글자 수 같음\)/);
  assert.match(fScreen, /\[주총 이사 후보 점검\] 후보 2명 · 표시 1명\n- A · 현대차 · 신후보 1960년생 사외이사 후보 · 주총 소집공고 2026-11-01\n   이사 후보: 선임되면 다른 회사 이사·감사 2곳 이상\(3호\): 주총 소집공고 후보/);
  assert.doesNotMatch(fScreen, /평온후보/);
  for (const status of ['inactive', 'unconfirmed', undefined]) {
    const historical = { ...doc, events: doc.events.map((e) => ({ ...e, reviewStatus: status })) };
    await worker.fetch(new Request(ORIGIN + '/ingest/kr-exec-check', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(historical) }), env, {});
    const hidden = await (await radarItems(new Request(ORIGIN + '/ingest/radar-items?hours=72', { headers: { Authorization: `Bearer ${TOKEN}` } }), env, { now: NOW })).json();
    assert(!hidden.items.some((x) => x.id.startsWith('execc:')), `historical ${status} must not reappear`);
    const screen = await call('radar_today', {}, opts);
    assert.doesNotMatch(screen.text, /김오래|박논란/);
  }
});

test('타사 공시 속 출입처(dart-counterparty): radar_today A·대조 낱말(상대 회사 필수), kr_signals counterparty 구역·같은 그룹 접음', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const now = new Date(NOW.getTime() - 3600000).toISOString();
  const item = (id, filer, report, company, role, tier, extra = {}) => ({ id, company, others: [], filer, report, rceptNo: id.slice(4), date: '20261026', role,
    context: '1. 양수영업 ㈜LG화학 대산 BPA 생산 및 판매 사업일체', amount: 78437000000, tier, sameGroup: false, url: `https://dart.fss.or.kr/dsaf001/main.do?rcpNo=${id.slice(4)}`, firstSeen: now, ...extra });
  const items = [item('dcp:20261026800562', '국도화학', '영업양수결정(종속회사의주요경영사항)', 'LG화학', '자산·영업·지분 거래 상대', 'A'),
    item('dcp:20261027900002', '현대글로비스', '단일판매ㆍ공급계약체결', '현대차', '공급계약 상대', 'C', { sameGroup: true, context: '계약상대 현대자동차 주식회사' })];
  const doc = { schema: 'dart_counterparty/v1', generatedAt: now, status: 'complete',
    checks: [{ source: 'OpenDART 공시검색(시장 전체 B·I)', status: 'ok', returned: 812 }, { source: '공시 원문', status: 'ok', returned: 41 }],
    counts: { listed: 812, candidates: 41, opened: 41, matched: 2 }, seen: {}, items,
    events: [{ id: items[0].id, tier: 'A', kind: '타사 공시 · 자산·영업·지분 거래 상대', company: 'LG화학', filer: '국도화학', report: items[0].report, detectedAt: now, url: items[0].url,
      text: '국도화학 공시 「영업양수결정(종속회사의주요경영사항)」(20261026) — LG화학이(가) 자산·영업·지분 거래 상대 · 금액 78,437,000,000원(약 784억원) · 원문 「1. 양수영업 ㈜LG화학 대산 BPA 생산 및 판매 사업일체」 · 상대 회사 공시(출입처 공시 아님)' }] };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/dart-counterparty', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const r = await call('radar_today', {}, opts);
  assert.match(r.text.split('[A · ')[1].split('[B · ')[0], /타사 공시 속 출입처\(거래상대\) · LG화학\n   국도화학 공시 「영업양수결정\(종속회사의주요경영사항\)」\(20261026\) — LG화학이\(가\) 자산·영업·지분 거래 상대 · 금액 78,437,000,000원\(약 784억원\)/);
  const radar = await (await radarItems(new Request(ORIGIN + '/ingest/radar-items?hours=72', { headers: { Authorization: `Bearer ${TOKEN}` } }), env, { now: NOW })).json();
  const hit = radar.items.find((x) => x.id === 'dcp:20261026800562');
  assert.deepEqual([hit.check.who, hit.check.terms, hit.check.must, hit.check.alts['인수']], ['LG화학', ['인수'], ['국도화학'], ['인수', '매각', 'M&A']]);
  const k = await call('kr_signals', { section: 'counterparty' }, opts);
  assert.match(k.text, /\[타사 공시 속 출입처\(거래상대\) · DART 시장 전체 · 확인 [^\]]+ · 접수 최근 30일\] 1건/);
  assert.match(k.text, /원천: OpenDART 공시검색\(시장 전체 B·I\) ok\(812\) · 공시 원문 ok\(41\) · 이번 실행 목록 812 · 종류로 거른 후보 41 · 원문 41/);
  assert.match(k.text, /- \[신규\] A · 2026-10-26 · 국도화학 「영업양수결정\(종속회사의주요경영사항\)」 → LG화학 · 자산·영업·지분 거래 상대\n   원문 발췌: 「1\. 양수영업 ㈜LG화학 대산 BPA 생산 및 판매 사업일체」 · 금액 78,437,000,000원\n   원문: https:\/\/dart\.fss\.or\.kr\/dsaf001\/main\.do\?rcpNo=20261026800562/);
  assert.match(k.text, /같은 그룹 계열사 공시 1건 접음 — include_mentions=true/);
  assert.match((await call('kr_signals', { section: 'counterparty', include_mentions: true }, opts)).text, /현대글로비스 「단일판매ㆍ공급계약체결」 → 현대차 · 공급계약 상대 · 같은 그룹 계열사 공시/);
});

test('노조 성명·보도자료(union-notices): radar_today A·대조 낱말, kr_official labor 구역에 노동위와 함께', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const now = new Date(NOW.getTime() - 3600000).toISOString();
  const post = (id, title, company, tier, extra = {}) => ({ id, board: '금속노조 보도자료/성명', title, date: now, companies: [company], company, tier, inTitle: true,
    excerpt: `${company} 관련 본문 앞부분`, url: `https://www.kmwu.kr/bbs/board.php?bo_table=ce_B12&wr_id=${id.split(':')[2]}`, firstSeen: now, ...extra });
  const posts = [post('un:ce_B12:220887', '[보도자료] 금호타이어 광주공장 끼임 중대재해 규탄 금속노조 기자회견', '금호타이어', 'A'),
    post('un:ce_B12:220880', '[성명] 노동절 집회 안내', '현대제철', 'C', { inTitle: false })];
  const doc = { schema: 'union_notices/v1', generatedAt: now, status: 'complete', seen: {},
    checks: [{ source: '금속노조 보도자료/성명', status: 'ok', returned: 15 }, { source: '화섬식품노조 보도자료/성명', status: 'ok', returned: 15 }], posts,
    events: [{ id: posts[0].id, tier: 'A', kind: '노조 성명·보도자료', company: '금호타이어', board: posts[0].board, title: posts[0].title, detectedAt: now, url: posts[0].url,
      text: '금속노조 보도자료/성명 「[보도자료] 금호타이어 광주공장 끼임 중대재해 규탄 금속노조 기자회견」 · 노조 발표(한쪽 주장) — 회사 입장·사실관계 확인' }] };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/union-notices', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const r = await call('radar_today', {}, opts);
  assert.match(r.text.split('[A · ')[1].split('[B · ')[0], /노조 성명·보도자료 · 금호타이어\n   금속노조 보도자료\/성명 「\[보도자료\] 금호타이어 광주공장 끼임 중대재해/);
  const items = await (await radarItems(new Request(ORIGIN + '/ingest/radar-items?hours=72', { headers: { Authorization: `Bearer ${TOKEN}` } }), env, { now: NOW })).json();
  const hit = items.items.find((x) => x.id === posts[0].id);
  assert.deepEqual([hit.check.who, hit.check.terms, hit.check.alts['사고'].includes('끼임')], ['금호타이어', ['사고'], true]);
  const k = await call('kr_official', { section: 'labor' }, opts);
  assert.match(k.text, /\[노동위 회의\(조정·심판\)\] 결과 없음 — 미확인/);
  assert.match(k.text, /\[노조 성명·보도자료 · 금속노조·화섬식품노조 공개 게시판 · 확인 [^\]]+ · 최근 14일\] 1건\n원천: 금속노조 보도자료\/성명 ok · 화섬식품노조 보도자료\/성명 ok/);
  assert.match(k.text, /- A · [^\n]+ · 금속노조 보도자료\/성명 · 「\[보도자료\] 금호타이어 광주공장 끼임 중대재해 규탄 금속노조 기자회견」 · 출입처 금호타이어\n   앞부분: 「금호타이어 관련 본문 앞부분」\n   원문: https:\/\/www\.kmwu\.kr\/bbs\/board\.php\?bo_table=ce_B12&wr_id=220887/);
  assert.match(k.text, /이름이 본문에만 있고 사건 낱말 없는 글 1건 접음/);
  assert.match((await call('kr_official', { section: 'labor', show_all: true }, opts)).text, /노동절 집회 안내」 · 출입처 현대제철\(본문에만\)/);
});

test('노동위 ↔ 노조 같은 회사 7일 안 이어 보기: 조정 회의 줄에 노조 글, 노조 글 줄에 노동위 회의, 같은 사건 앞선 회의, 제목에 이름 없는 글·8일 넘은 글은 안 붙음', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const now = new Date(NOW.getTime() - 3600000).toISOString();
  const day = now.slice(0, 10);
  const shift = (d) => new Date(Date.parse(`${day}T09:00:00+09:00`) + d * 86400000).toISOString();
  const nid = `labor:13:2026조정59:${day}`;
  const notices = [{ id: nid, company: 'LG화학', commission: '충남', commissionName: '충남지방노동위원회', meeting: '2차조정회의', day, time: '15:00',
    caseNo: '2026조정59', caseName: '주식회사 LG화학 노동쟁의 조정신청사건', party: '주식회사 LG화학', tier: 'A', url: 'https://www.nlrc.go.kr/nlrc/chungnam/meetingSche/detail.do?mtgId=1&cmitCd=13',
    firstSeen: now, prior: ['2026-10-28'] }];
  const labor = { schema: 'kr_labor/v1', generatedAt: now, status: 'complete', checks: [{ source: '충남지방노동위원회', status: 'ok', returned: 2 }], counts: {}, seen: {}, notices,
    events: [{ id: nid, tier: 'A', kind: '노동위 조정 회의 (같은 사건 다시)', company: 'LG화학', commission: '충남지방노동위원회', caseNo: '2026조정59', word: '노동쟁의', url: notices[0].url,
      detectedAt: now, prior: ['2026-10-28'], text: `충남지방노동위원회 2차조정회의 ${day} 15:00 · 사건 2026조정59 「주식회사 LG화학 노동쟁의 조정신청사건」 · 같은 사건 앞선 회의 10-28` }] };
  const post = (id, title, company, date, extra = {}) => ({ id, board: '화섬식품노조 보도자료/성명', title, date, companies: [company], company, tier: 'B', inTitle: true,
    excerpt: '본문', url: `https://kctfu.org/bbs/${id}`, firstSeen: now, ...extra });
  const posts = [post('un:k:1', '[성명] LG화학 대산공장 교섭 결렬, 쟁의행위 찬반투표 돌입', 'LG화학', shift(-3)),
    post('un:k:2', '[성명] 화학업계 공동 집회', 'LG화학', shift(-2), { inTitle: false }),
    post('un:k:3', '[보도자료] LG화학 여수 하청 임금체불', 'LG화학', shift(-9))];
  const union = { schema: 'union_notices/v1', generatedAt: now, status: 'complete', seen: {}, checks: [{ source: '화섬식품노조 보도자료/성명', status: 'ok', returned: 15 }], posts,
    events: [{ id: 'un:k:1', tier: 'A', kind: '노조 성명·보도자료', company: 'LG화학', board: posts[0].board, title: posts[0].title, detectedAt: now, url: posts[0].url,
      text: `화섬식품노조 보도자료/성명 「${posts[0].title}」 · 노조 발표(한쪽 주장)` }] };
  for (const [feed, doc] of [['kr-labor', labor], ['union-notices', union]]) {
    assert.equal((await worker.fetch(new Request(ORIGIN + `/ingest/${feed}`, { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  }
  const a = (await call('radar_today', {}, opts)).text.split('[A · ')[1].split('[B · ')[0];
  const laborLine = a.split('\n').find((l) => l.includes('2026조정59') && l.includes('2차조정회의'));
  assert.match(laborLine, /같은 사건 앞선 회의 10-28 · 노조 게시판 같은 회사 글\(7일 안\): 「\[성명\] LG화학 대산공장 교섭 결렬, 쟁의행위 찬반투표 돌입」\(화섬식품노조 보도자료\/성명 \d{2}-\d{2}\)$/);
  assert.doesNotMatch(laborLine, /공동 집회|임금체불/);   // 제목에 이름 없는 글, 9일 앞선 글은 안 붙는다
  const unionLine = a.split('\n').find((l) => l.includes('교섭 결렬') && l.startsWith('   화섬식품노조'));
  assert.match(unionLine, / · 노동위 같은 회사 회의\(7일 안\): 충남지방노동위원회 \d{2}-\d{2} 2026조정59 「주식회사 LG화학 노동쟁의 조정신청사건」$/);
  const k = await call('kr_official', { section: 'labor' }, opts);
  assert.match(k.text, /A · [^\n]+ · LG화학 · 충남지방노동위원회 2차조정회의 · 사건 2026조정59 「주식회사 LG화학 노동쟁의 조정신청사건」 · 같은 사건 앞선 회의 10-28\n/);
});

test('노동위 달력(local_notice_submit labor): 고정 위원회·숫자 값만 받아 저장, kr-labor 실행 요청은 5시간에 한 번, kr_official에 달력·예정 표시', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const asked = [];
  env.GITHUB_DISPATCH_TOKEN = 'x';
  opts.fetch = async (url, init) => { asked.push(String(url)); return new Response(null, { status: 204 }); };
  const kst = new Date(NOW.getTime() + 9 * 3600000);
  const ymd = (d) => new Date(kst.getTime() + d * 86400000).toISOString().slice(0, 10).replaceAll('-', '');
  const r = await call('local_notice_submit', { labor: [
    { commission: '충남지방노동위원회', rows: [`2611021110520048685/4/${ymd(0)}/조정회의`, `2611101000000000001/1/${ymd(6)}/2차조정회의`,
      `https://evil.example/x/1/${ymd(1)}/심판회의`, `2612301000000000001/1/${ymd(90)}/심판회의`, `2611101000000000001/1/${ymd(6)}/2차조정회의`] },
    { commission: '서울지방노동위원회', error: 'TypeError: Failed to fetch' },
    { commission: '가짜노동위원회', rows: [] }] }, opts);
  assert.match(r.text, /- 노동위 회의일정 2곳\(정상 1\) · 회의 2건 · 미확인: 서울지노위\(TypeError: Failed to fetch\) · 버린 줄 3/);
  assert.match(r.text, /받지 않은 위원회\(허용 밖\): 가짜노동위원회/);
  assert.match(r.text, /노동위 회의 감시\(kr-labor\) 실행 요청함/);
  assert.equal(asked.filter((u) => u.includes('kr-labor.yml')).length, 1);
  const stored = await (await worker.fetch(new Request(ORIGIN + '/ingest/kr-labor-browser', { headers: { Authorization: `Bearer ${TOKEN}` } }), env, {})).json();
  assert.equal(stored.schema, 'kr_labor_browser/v1');
  assert.deepEqual(stored.commissions[0].rows.map((x) => [x.mtgId, x.mtgSn, x.cmitCd, x.title]), [['2611021110520048685', '4', '04', '조정회의'], ['2611101000000000001', '1', '04', '2차조정회의']]);
  const again = await call('local_notice_submit', { labor: [{ commission: '충남지방노동위원회', rows: [`2611021110520048685/4/${ymd(0)}/`] }] }, opts);
  assert.match(again.text, /노동위 감시 실행 요청은 \d+분 전에 이미 함/);
  assert.equal(asked.filter((u) => u.includes('kr-labor.yml')).length, 1);
  const str = await call('local_notice_submit', { labor: JSON.stringify([{ commission: '제주지방노동위원회', rows: [`2611031444300005590/1/${ymd(1)}/심판회의`] }]) }, opts);
  assert.match(str.text, /- 노동위 회의일정 1곳\(정상 1\) · 회의 1건/);   // 옛 도구 목록을 가진 클라이언트가 JSON 글자로 넘겨도 받는다
  const kept = await (await worker.fetch(new Request(ORIGIN + '/ingest/kr-labor-browser', { headers: { Authorization: `Bearer ${TOKEN}` } }), env, {})).json();
  assert.deepEqual(kept.commissions.map((x) => x.commission), ['제주지방노동위원회', '충남지방노동위원회', '서울지방노동위원회']);   // 이번에 안 올린 위원회는 남긴다

  const now = new Date(NOW.getTime() - 3600000).toISOString();
  const day = (d) => `${ymd(d).slice(0, 4)}-${ymd(d).slice(4, 6)}-${ymd(d).slice(6)}`;
  const notices = [{ id: `labor:04:2026조정59:${day(6)}`, company: 'LG화학', commission: '충남', commissionName: '충남지방노동위원회', meeting: '2차조정회의', day: day(6), time: '10:00',
    caseNo: '2026조정59', caseName: '주식회사 LG화학 노동쟁의 조정신청사건', tier: 'A', url: 'https://www.nlrc.go.kr/nlrc/chungnam/meetingSche/detail.do?mtgId=2611101000000000001', firstSeen: now, ahead: 6 }];
  const doc = { schema: 'kr_labor/v1', generatedAt: now, status: 'complete', checks: [{ source: '충남지방노동위원회', status: 'ok', returned: 5, calendar: 2 }, { source: '서울지방노동위원회', status: 'ok', returned: 5, note: '첫 화면 5건 상한 — 뒤 회의가 빠졌을 수 있음' }],
    counts: { meetings: 10, details: 12, cases: 30, '조정 사건': 2, ahead: 1 }, calendar: { status: 'partial', ahead: 14, meetings: 2, left: 0, fetchedAt: '2026-11-03T23:40:00.000Z', missing: ['서울지방노동위원회'], stale: [] },
    seen: {}, notices, events: [], rules: [] };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/kr-labor', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const k = (await call('kr_official', { section: 'labor' }, opts)).text;
  assert.match(k, /달력\(기자 컴퓨터 브라우저 수집 11-04 08:40 KST\): 오늘부터 14일 회의 2건 · 이번 실행 미리 읽은 회의 1건 · 달력 미확인: 서울지노위/);
  assert.match(k, /첫 화면 5건 상한\(뒤 회의 빠졌을 수 있음\): 서울지노위/);
  assert.match(k, new RegExp(`A · ${day(6)} 10:00\\(예정\\) · LG화학 · 충남지방노동위원회 2차조정회의`));
});

test('노동위 조정 결과 확인: A 조정 회의 다음 날 B로 다시 올려 회의일 이후만 보도 대조, B 사건·킬한 사건은 안 올림, kr_official 앞으로 열릴 회의', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const day = (d) => new Date(NOW.getTime() + 9 * 3600000 + d * 86400000).toISOString().slice(0, 10);
  const seen = new Date(NOW.getTime() - 2 * 86400000).toISOString();
  const n = (no, company, tier, d, extra = {}) => ({ id: `labor:04:${no}:${day(d)}`, company, commission: '충남', commissionName: '충남지방노동위원회', meeting: '조정회의', day: day(d), time: '15:00',
    caseNo: no, caseName: `주식회사 ${company} 노동쟁의 조정신청사건`, tier, url: `https://www.nlrc.go.kr/nlrc/chungnam/meetingSche/detail.do?mtgId=${no}`, firstSeen: seen, ...extra });
  const notices = [n('2026조정59', 'LG화학', 'A', -1), n('2026조정60', '롯데케미칼', 'A', -1), n('2026부해61', '현대차', 'B', -1, { meeting: '심판회의', caseName: '현대자동차 주식회사 부당해고 구제신청' }),
    n('2026조정62', '포스코', 'A', 0), n('2026조정63', '현대제철', 'A', 6), n('2026조정64', '기아', 'A', -5)];
  const doc = { schema: 'kr_labor/v1', generatedAt: seen, status: 'complete', checks: [{ source: '충남지방노동위원회', status: 'ok', returned: 3 }], counts: {}, seen: {}, notices, events: [], rules: [] };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/kr-labor', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  await call('candidate_feedback', { item_id: notices[1].id, verdict: '킬', reason: '작음' }, opts);
  const r = (await call('radar_today', {}, opts)).text;
  const b = r.split('[B · ')[1] ?? '';
  assert.match(b, new RegExp(`노동위 회의\\(조정·심판\\) · LG화학\\n   충남지방노동위원회 조정회의 ${day(-1)} 15:00 회의 지남 · 사건 2026조정59 「주식회사 LG화학 노동쟁의 조정신청사건」 — 조정 중지\\(쟁의권\\)·성립·연장 결과는 공개 일정에 나오지 않음`));
  assert.doesNotMatch(r, /2026조정60[^\n]*회의 지남/);   // 원래 항목을 킬했다
  assert.doesNotMatch(r, /2026부해61[^\n]*회의 지남/);   // B 구제신청은 결과 확인 대상 아님
  assert.doesNotMatch(r, /2026조정62[^\n]*회의 지남|2026조정63[^\n]*회의 지남/);   // 오늘·앞날 회의는 아직
  assert.doesNotMatch(r, /2026조정64[^\n]*회의 지남/);   // 오래된 회의는 창 밖
  const items = await (await radarItems(new Request(ORIGIN + '/ingest/radar-items?hours=72', { headers: { Authorization: `Bearer ${TOKEN}` } }), env, { now: NOW })).json();
  const hit = items.items.find((x) => x.id === `${notices[0].id}:result`);
  assert.deepEqual([hit.tier, hit.check.who, hit.check.terms, hit.check.after, hit.check.alts['조정 결과'].includes('쟁의권')], ['B', 'LG화학', ['조정 결과'], day(-1), true]);
  assert.ok(!items.items.some((x) => x.id === `${notices[1].id}:result`));
  const k = (await call('kr_official', { section: 'labor' }, opts)).text;
  assert.match(k, new RegExp(`- 앞으로 열릴 출입처 회의\\(오늘 포함, 달력·첫 화면\\) 2건 — 미뤄지거나 취소될 수 있음\\n  ${day(0)} 15:00 · A · 포스코 · 충남지방노동위원회 조정회의 · 사건 2026조정62[^\\n]*\\n  ${day(6)} 15:00 · A · 현대제철`));
  // 11-11: 지난 조정 회의마다 결과 확인을 올렸는지 — 킬해서 안 올린 회의는 이유(판정 사유)를 보인다. B 구제신청·오늘·앞날 회의는 대상 아님
  const fu = k.split('- 지난 조정·중재 회의 결과 확인')[1] ?? '';
  assert.match(k, /- 지난 조정·중재 회의 결과 확인 · 회의일 최근 30일 3건 — 조정 중지\(쟁의권\)·성립·연장은 공개 일정에 안 나와 다음 날 B로 다시 올림/);
  assert.match(fu, new RegExp(`  ${day(-1)} 15:00 · LG화학 · 충남지방노동위원회 조정회의 · 사건 2026조정59 — 결과 확인 B를 ${day(0).slice(5)} 09:00 날짜로 올림\\(radar_today 창 안일 때 보임, 회의일 이후 보도만 대조\\)\\n`));
  assert.match(fu, /롯데케미칼 · 충남지방노동위원회 조정회의 · 사건 2026조정60 — 결과 확인 안 올림 — 원래 회의를 킬함\(킬 \d\d-\d\d '작음'\)/);
  assert.match(fu, new RegExp(`${day(-5)} 15:00 · 기아 [^\\n]*2026조정64 — 결과 확인 B를`));   // radar_today 창 밖이어도 kr_official(30일)에는 보인다
  assert.doesNotMatch(fu.split('검증 상태')[0], /2026부해61|2026조정62|2026조정63/);
  // 결과 확인 항목 자체를 판정하면 그 판정도 붙는다
  await call('candidate_feedback', { item_id: `${notices[0].id}:result`, verdict: '봤음', reason: '조정 중지 기사 확인' }, opts);
  const k2 = (await call('kr_official', { section: 'labor', company: 'LG화학' }, opts)).text;
  assert.match(k2, /2026조정59 — 결과 확인 B를 [^\n]*· 결과 확인 판정 봤음 \d\d-\d\d '조정 중지 기사 확인'/);
  assert.doesNotMatch(k2.split('- 지난 조정·중재 회의')[1] ?? '', /롯데케미칼/);   // company로 좁힘
});

test('지분·자사주 변동(governance): 임원 집단 보고·일상 아닌 자사주 처분은 B, 일상 보상 처분은 숨김', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const today = new Date(NOW.getTime() - 3600000).toISOString().slice(0, 10);
  const doc = { schema: 'governance/v1', generatedAt: new Date(NOW.getTime() - 3600000).toISOString(), status: 'complete',
    checks: [{ company: 'KG스틸', endpoint: 'elestock.json', status: 'checked' }, { company: 'KG스틸', endpoint: 'tsstkDpDecsn.json', status: 'no_data' }], items: [
    { company: 'KG스틸', team: '철강·비철', kind: '자사주 처분 결정', date: today, receiptNo: '20261015000414', reporter: 'KG스틸',
      reason: '처분목적 "임직원 지급을 위한 자기주식 처분" · 2,461,991주·136.9억원 · 처분 전 보유 2,461,991주의 100% · 방법 기타', period: '2026년 10월 16일~2027년 01월 15일',
      tags: ['[처분목적: 임직원 보상]', '[보유 자사주의 100%]'], routine: false, url: 'https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261015000414' },
    { company: 'KG스틸', team: '철강·비철', kind: '임원 집단 보고', date: today, receiptNo: null, groupKey: `insider-group|KG스틸|${today}`, reporter: '임원·주요주주 15명',
      reason: '매수 15명·매도 0명 · 순증감 +134,222주(보고서별 합계, 취득 경위는 원문 확인) · 10-15 자기주식 처분 결정(처분목적 "임직원 지급을 위한 자기주식 처분", 2,461,991주) 뒤 — 주식 보상 지급으로 보임',
      tags: ['[같은 날 15명 보고]', '[자사주 처분 연결]'], routine: false, url: 'https://dart.fss.or.kr/x' },
    { company: '현대자동차', team: '자동차', kind: '자사주 처분 결정', date: today, receiptNo: '20260326001343', reason: '처분목적 "임원 대상 자기주식 지급"', tags: ['[처분목적: 임직원 보상]'], routine: true }] };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/governance', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const r = await call('radar_today', {}, opts);
  const b = r.text.split('[B · ')[1].split('[C · ')[0];
  assert.match(b, /지분·자사주 변동 · KG스틸\n   KG스틸 자기주식 처분 결정 — 처분목적 "임직원 지급을 위한 자기주식 처분" · 2,461,991주·136\.9억원 · 처분 전 보유 2,461,991주의 100% · 방법 기타 · 처분 기간 2026년 10월 16일~2027년 01월 15일 \[처분목적: 임직원 보상\] \[보유 자사주의 100%\]/);
  assert.match(b, /KG스틸 임원·주요주주 15명 같은 날 지분 보고 — 매수 15명·매도 0명[^\n]*주식 보상 지급으로 보임 \[같은 날 15명 보고\] \[자사주 처분 연결\]/);
  assert.doesNotMatch(r.text, /임원 대상 자기주식 지급/);   // 보유분 일부의 해마다 하는 임원 지급은 일상
  assert.doesNotMatch(r.text, /지분·자사주 변동: 일부 실패/);   // 'checked'·'no_data'는 정상(11-04 첫 화면 '일부 실패 102건')
  const items = await (await radarItems(new Request(ORIGIN + '/ingest/radar-items?hours=72', { headers: { Authorization: `Bearer ${TOKEN}` } }), env, { now: NOW })).json();
  assert.deepEqual(items.items.find((x) => x.id === 'treasury:20261015000414').check.terms, ['자사주']);
});

test('기자 기사 자동 대조(my-articles): radar_today 항목에 기자 기사 표시, candidate_weekly_review 끝에 감시별 먼저 잡은 수(판정과 별개)', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const now = new Date(NOW.getTime() - 3600000).toISOString();
  const post = (feed, body) => worker.fetch(new Request(ORIGIN + '/ingest/' + feed, { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(body) }), env, {});
  assert.match((await call('candidate_weekly_review', { days: 14 }, opts)).text, /\[자동 대조: 기자 기사 ↔ 레이더\] 아직 수집 전 — 미확인/);
  const ev = { id: 'clik:CLIKC1', tier: 'A', kind: '지방의회 회의록', company: '기아', council: '화성시의회', detectedAt: now,
    text: '화성시의회 제300회 본회의(20261020) 회의록 · 기아 대목 「신차 2000대가 공장 시설로 허가받은 땅에 야적」' };
  assert.equal((await post('council-minutes', { schema: 'council_minutes/v1', generatedAt: now, status: 'complete', items: [], events: [ev],
    checks: [{ source: '국회도서관 지방의회 회의록(CLIK)', status: 'ok', returned: 1, opened: 1 }] })).status, 200);
  const art = { url: 'https://www.inews24.com/view/3000001', title: '기아, 화성 신차 불법 야적 논란⋯시의회 "공장 부지 허가 위반"', published: now, companies: ['기아'], verified: true,
    verdict: '먼저 잡은 후보', sameCompanyItems: 1, best: { source: 'council-minutes', label: '지방의회 회의록', id: 'clik:CLIKC1', text: ev.text, seen: now.slice(0, 16), why: ['신차', '야적'], leadHours: 26.5 } };
  const doc = { schema: 'my_articles/v1', generatedAt: now, status: 'complete', author: '홍성효',
    checks: [{ source: '아이뉴스24 뉴스 사이트맵', status: 'ok', returned: 815, candidates: 40, opened: 40, mineNew: 1 }],
    articles: [{ ...art, kind: '논란·법적', press: '자체', pressN: 0 }, { ...art, url: null, title: '금호타이어, 롯데카드와 제휴카드 출시', companies: ['금호타이어'], verified: false, verdict: '없음', best: null, kind: '제품·마케팅', press: '보도자료·공시', pressN: 3 },
      { ...art, url: null, title: 'KG스틸, 3분기 영업익 248억원', companies: ['KG스틸'], verified: true, verdict: '같은 회사 항목만', best: null, kind: '실적', press: '보도자료·공시', pressN: 5 },
      { ...art, url: null, title: '대미 타이어 수출 25% 감소…유럽이 메웠지만 관세 복병', companies: [], verified: true, verdict: '회사 미상', best: null, kind: '통계·시장', press: '선행', pressN: 2 },
      { ...art, url: null, title: '포스코, 포항 3고로 개수 앞당긴다', companies: ['포스코'], verified: true, verdict: '같은 회사 항목만', sameCompanyItems: 7, best: null, kind: '투자·공장', press: '자체', pressN: 0 }],
    counts: { '먼저 잡은 후보': 1, '같은 회사 항목만': 0, '없음': 1, '회사 미상': 0 },
    itemHits: { 'clik:CLIKC1': { title: art.title, published: now, url: art.url, verified: true } } };
  assert.equal((await post('my-articles', doc)).status, 200);
  const r = await call('radar_today', {}, opts);
  assert.match(r.text, /id clik:CLIKC1 〔기자 기사\(자동 대조\) \d\d-\d\d 「기아, 화성 신차 불법 야적 논란⋯시의회 "공장 부지 허가 위반"」〕/);
  const w = await call('candidate_weekly_review', { days: 14 }, opts);
  assert.match(w.text, /기사 5건\(그중 1건은 첫 실행 구글 색인이라 작성자 미확인\) — 레이더가 먼저 잡은 후보 1 · 같은 회사 항목만 2 · 없음 1 · 회사 미상 1/);
  assert.match(w.text, /보도자료·공시 추정 2 · 자체 2 · 선행 1 — 자체·선행 3건 중 레이더가 먼저 잡은 후보 1 · 같은 회사 항목만 1 · 없음 0 · 회사 미상 1/);
  assert.match(w.text, /기자 기사가 먼저 나오고 다른 매체가 따라온 기사\(선행\) 1건\n  · \d\d-\d\d 「대미 타이어 수출 25% 감소…유럽이 메웠지만 관세 복병」 — 뒤따른 비슷한 기사 2건/);
  assert.doesNotMatch(w.text, /레이더에 같은 회사 항목도 없던 기사/);   // 금호타이어 제휴카드는 보도자료라 '놓친 기사'에서 뺌
  // 11-11: 자체 기사 중 같은 회사 항목만 있던 기사는 제목을 보인다(보도자료로 정해진 KG스틸 실적은 뺌)
  assert.match(w.text, /같은 회사 항목만 있던 기사 1건\(사건은 달랐음\) — 투자·공장 1\n  · \d\d-\d\d \[투자·공장·자체\] 「포스코, 포항 3고로 개수 앞당긴다」 — 같은 회사 레이더 항목 7개\(사건 낱말 안 겹침\)\n/);
  assert.doesNotMatch(w.text, /KG스틸, 3분기 영업익/);
  assert.match(w.text, /감시별\(먼저 잡은 후보\): 지방의회 회의록 1/);
  assert.match(w.text, /레이더: [^\n]*지방의회 회의록 — [^\n]*\(26\.5시간 앞, 겹친 낱말 신차·야적\) · id clik:CLIKC1/);
  assert.match(w.text, /안 쓴 항목은 킬이 아니다/);
});

test('지방의회 회의록(council-minutes): 키 없으면 미설정(0건 아님), 있으면 A·대조 낱말(의회 이름 필수)·kr_official council 구역', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const now = new Date(NOW.getTime() - 3600000).toISOString();
  const unset = { schema: 'council_minutes/v1', generatedAt: now, status: 'not_configured', items: [], events: [],
    checks: [{ source: '국회도서관 지방의회 회의록(CLIK)', status: 'unset', error: 'CLIK_API_KEY 미설정 — clik.nanet.go.kr 로그인 뒤 인증키 신청, GitHub 비밀값으로' }] };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/council-minutes', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(unset) }), env, {})).status, 200);
  assert.match((await call('radar_today', {}, opts)).text, /- 지방의회 회의록: 미설정 국회도서관 지방의회 회의록\(CLIK\)\(CLIK_API_KEY 미설정/);
  assert.match((await call('kr_official', { section: 'council' }, opts)).text, /\[지방의회 회의록\] 미설정 — CLIK_API_KEY 미설정[^\n]*\(0건 아님\)/);
  const it = { id: 'clik:CLIKC1', company: '기아', term: '기아자동차', council: '화성시의회', meeting: '제300회 본회의', date: '20261020', agenda: '1. 시정에 관한 질문',
    snippets: ['김의원: 화성시 우정읍 기아 오토랜드 화성 인근 부지에 신차 2000대가 공장 시설로 허가받은 땅에 야적되고 있습니다. 불법 아닙니까?'], tier: 'A', docid: 'CLIKC1', url: '', firstSeen: now };
  const doc = { schema: 'council_minutes/v1', generatedAt: now, status: 'complete', items: [it, { ...it, id: 'clik:CLIKC2', company: '현대제철', council: '당진시의회', tier: 'C', snippets: ['현대제철 봉사활동 감사'] }],
    checks: [{ source: '국회도서관 지방의회 회의록(CLIK)', status: 'ok', returned: 3, opened: 3 }],
    events: [{ id: it.id, tier: 'A', kind: '지방의회 회의록', company: '기아', council: '화성시의회', detectedAt: now,
      text: '화성시의회 제300회 본회의(20261020) 회의록 · 기아 대목 「…신차 2000대가 공장 시설로 허가받은 땅에 야적되고 있습니다. 불법 아닙니까?」 · 회의록 번호 CLIKC1(국회도서관 지방의정포털) · 의원 질의는 주장' }] };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/council-minutes', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const r = await call('radar_today', {}, opts);
  // 11-13 기자 결정: 지방의회 회의록은 한 단계 내려 B(수집기 등급 A는 kr_official council 구역에 그대로 보인다)
  assert.doesNotMatch(r.text.split('[A · ')[1].split('[B · ')[0], /지방의회 회의록/);
  assert.match(r.text.split('[B · ')[1].split('[C · ')[0], /지방의회 회의록 · 기아\n   화성시의회 제300회 본회의\(20261020\) 회의록 · 기아 대목/);
  const items = await (await radarItems(new Request(ORIGIN + '/ingest/radar-items?hours=72', { headers: { Authorization: `Bearer ${TOKEN}` } }), env, { now: NOW })).json();
  const hit = items.items.find((x) => x.id === 'clik:CLIKC1');
  assert.deepEqual([hit.check.who, hit.check.terms, hit.check.must], ['기아', ['불법'], ['화성시']]);
  const k = await call('kr_official', { section: 'council' }, opts);
  assert.match(k.text, /- A · 2026-10-20 · 화성시의회 제300회 본회의 · 기아 · 안건 1\. 시정에 관한 질문\n   대목: 「김의원: 화성시 우정읍 기아 오토랜드/);
  assert.match(k.text, /원문: 회의록 번호 CLIKC1\(국회도서관 지방의정포털 검색\)/);
  assert.match(k.text, /사건 낱말 없는 언급 1건 접음 — show_all=true/);
});

test('경쟁지 단독 역추적: 종류·매체별 집계(scoop_reverse·주간 점검)', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const at = new Date(NOW.getTime() - 3600000).toISOString();
  const art = (id, title, source, type, verdict) => ({ articleId: id, title, published: at, source, companies: ['포스코'], type, verdict,
    best: verdict === '먼저 잡은 후보' ? { source: 'trade-remedy', label: '무역구제·미국 관보', id: 'fr:1', text: 'Final Results', seen: at, why: ['관세'], leadHours: 37.3 } : null });
  const doc = { schema: 'reverse_check/v1', generatedAt: at, windowDays: 30, memoryItems: 10, feedsLoaded: { 'trade-remedy': true },
    articles: [art('a', '[단독] 포스코, 미국 상계관세 소송서 패소', '뉴스저널리즘', '논란·법적', '먼저 잡은 후보'),
      art('b', '[단독] 美 도금강판 관세 70%대 위협', '철강금속신문', '정책·통상', '먼저 잡은 후보'),
      art('c', '[단독] 현대차 로봇사업 수장 영입', '머니투데이', '인사·조직', '없음'), art('d', '[단독] 현대차 CEO 진단', '머니투데이', '인사·조직', '같은 회사 항목만')],
    counts: { '먼저 잡은 후보': 2, '같은 회사 항목만': 1, '없음': 1, '회사 미상': 0 } };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/reverse-check', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const r = await call('scoop_reverse', {}, opts);
  assert.match(r.text, /종류별: 인사·조직 2\(먼저 0·같은 회사 1·없음 1\) · 논란·법적 1\(먼저 1·같은 회사 0·없음 0\) · 정책·통상 1\(먼저 1·같은 회사 0·없음 0\)/);
  assert.match(r.text, /매체별: 머니투데이 2\(먼저 0·같은 회사 1·없음 1\)/);
  const w = await call('candidate_weekly_review', { days: 14 }, opts);
  assert.match(w.text, /\[경쟁지 단독 · 최근 14일 4건 · 레이더 대조\(자동\)\]\n종류별: 인사·조직 2/);
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
      art('a2', '[단독] LG그룹, 현대차 로봇사업 수장 품었다', '없음', null, '2026-10-23T09:00:00+09:00'),
      // 11-09: 기사 제목 숫자가 레이더 원문에도 있는지
      art('a3', '[단독] 美 변압기 반덤핑 12.5%…LS일렉트릭 대응', '먼저 잡은 후보',
        { source: 'trade-remedy', label: '무역구제·미국 관보', id: 'fr:1', text: 'Large Power Transformers duty 3.10%', seen: '2026-10-24T07:50+09:00', leadHours: 40,
          why: ['관세·무역구제', '변압기'], numbers: { article: ['12.5%'], found: [], comparable: true } }, '2026-10-25T23:50:00+09:00'),
      art('a5', '[단독] LS일렉트릭 변압기 관세 1조원 부담', '먼저 잡은 후보',
        { source: 'trade-remedy', label: '무역구제·미국 관보', id: 'fr:2', text: 'Large Power Transformers duty', seen: '2026-10-24T07:50+09:00', leadHours: 42,
          why: ['관세·무역구제', '변압기'], numbers: { article: ['1조원'], found: [], comparable: false } }, '2026-10-26T01:50:00+09:00'),
      art('a4', '[단독] LS일렉트릭 변압기 반덤핑 3.10% 확정', '먼저 잡은 후보',
        { source: 'trade-remedy', label: '무역구제·미국 관보', id: 'fr:1', text: 'Large Power Transformers duty 3.10%', seen: '2026-10-24T07:50+09:00', leadHours: 41,
          why: ['관세·무역구제', '변압기'], numbers: { article: ['3.10%'], found: ['3.10%'] } }, '2026-10-26T00:50:00+09:00')] };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/reverse-check', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const r = await call('scoop_reverse', {}, opts);
  assert.match(r.text, /먼저 잡은 후보 4\(기사 숫자가 레이더 원문에도 있음 1 · 다름 1 · 비교 못 함 1\) · 같은 회사 항목만 0 · 없음 1 · 회사 미상 0 \(레이더 기억 812건, 감시 2\/3 읽음, 저장 결과 없음 trademarks — 그 감시 항목은 대조 못 함\)/);
  assert.match(r.text, /원천별 먼저 잡은 후보: 무역구제·미국 관보 3건\(중간 41시간 앞\) · 미국 소송·판결 1건\(중간 48시간 앞\)/);
  assert.match(r.text, /\(40시간 앞, 겹친 낱말 관세·무역구제·변압기\) · 기사 숫자 12\.5% 레이더 원문 숫자와 다름 — 같은 분야 다른 사실일 수 있음 · id fr:1/);
  assert.match(r.text, /· 기사 숫자 1조원 — 레이더 글에 비교할 숫자 없음\(원문에서 확인\) · id fr:2/);
  // 레이더 글은 낱말 중간에서 자르지 않는다(세율 '1.21%'가 '1.2'로 잘리지 않게)
  const { reverseClip } = await import('../cloudflare/overseas.mjs');
  assert.equal(reverseClip('Hot-Rolled Final Results duty 1.21% 0.55%', 33), 'Hot-Rolled Final Results duty…');
  assert.equal(reverseClip('short', 33), 'short');
  assert.match(r.text, /\(41시간 앞, 겹친 낱말 관세·무역구제·변압기\) · 기사 숫자 3\.10% 레이더 원문에도 있음 · id fr:1/);
  assert.match(r.text, /레이더: 10-24 07:50 미국 소송·판결 — In re: LS Electric/);
  assert.match(r.text, /48\.2시간 앞, 겹친 낱말 소송·판결·특허·상표\) · id cl:75019340/);
  assert.match(r.text, /\[없음\] 1건\n- 10-23 09:00 · 뉴스저널리즘 「\[단독\] LG그룹, 현대차 로봇사업 수장 품었다」/);
  assert.match(r.text, /사람 판정 Y\/P\/N은 역추적 기록에 따로/);
  // radar_today shows the same automatic candidates (for chats whose connector list lacks scoop_reverse)
  const today = await call('radar_today', { hours: 72 }, opts);
  assert.match(today.text, /\[경쟁지 단독 역추적 · 자동 후보, 사람 판정\(Y\/P\/N\) 전\] 최근 14일 레이더가 먼저 잡은 후보 4건/);
  assert.match(today.text, /· 기사 숫자 3\.10% 레이더 원문에도 있음 · id fr:1/);
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
  assert.deepEqual(dueAt(new Date('2026-10-28T21:50:00Z')), ['reporter-morning.yml', 'overseas-awards.yml']);  // Thu 06:50 KST
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
    items: [{ id: 'bh:Aug 2026 Awarding Report.pdf:0', source: '바레인 입찰위원회', published: null, kind: '낙찰(월간 보고서)', buyer: '정부 발주처(보고서 줄 참조)',
      buyerCountry: 'BHR', winners: [], winnerCountry: [], winnerIds: [], company: '일진전기', companies: ['일진전기'], ocr: true, reportMonth: '2026-08',
      title: 'ILJINELECTRIC COLTD, 1 cle Lasy 400KV and 220KV Feeder t-ilis 5100/2025/4669 17 / 34,968,319.628 SOUTH KOREA SIGE 5 Cable Works for / Awsighl Establishment of New / Sitra 400KV Grid',
      report: '2 Awarded Tenders Report - August 2026 8.7 MB', value: 34968319.628, currency: 'BHD', valueOcr: true, url: 'https://www.tenderboard.gov.bh/MediaHandler/ImageHandler/Pdf/Awarded/Aug%202026%20Awarding%20Report.pdf',
      firstSeen: '2026-10-26T06:50:00+09:00', isNew: true, baseline: false, tier: 'B' },  // 다음 실행에 읽은 보고서(날짜 없는 줄은 처음 본 때로)
      b('bhopen:9001:일진전기'),
      b('bhopen:9001:LS전선', { company: 'LS전선', companies: ['LS전선'], bidder: 'LS CABLE AND SYSTEM LTD', value: 46659985.55, rank: 3, lowest: false, tier: 'B',
        lowestBid: { name: 'ILJIN ELECTRIC', value: 35004118.33 } }),
      b('bhopen:8001:LS일렉트릭', { company: 'LS일렉트릭', companies: ['LS일렉트릭'], bidder: 'LS ELECTRIC CO., LTD.', published: '2026-09-01', value: null,
        rank: null, priced: null, lowest: false, isNew: false, baseline: true, tier: 'B', title: 'PT/CSD/AS/2026/019 Supply of 66KV Switchgear' })] };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/overseas-awards', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const r = await call('radar_today', { hours: 72, include_minor: true }, opts);
  const sec = (t) => r.text.split(`[${t} · `)[1].split(/\n\[[ABC] · /)[0];
  assert.match(sec('A'), /해외 개찰\(바레인 입찰위원회 개찰\): 바레인 Electricity and Water Authority \(Planning\) · 4669\/2025\/5100 400kV[^\n]* — ILJIN ELECTRIC BHD 35,004,118 · 응찰가 1위\/3곳\(최저가\) · 개찰 2026-10-25 · 낙찰 아님/);
  assert.match(sec('B'), /— LS CABLE AND SYSTEM LTD BHD 46,659,986 · 응찰가 3위\/3곳 · 최저 ILJIN ELECTRIC BHD 35,004,118/);
  // 월간 보고서 줄(글자 인식): '바레인 바레인' 겹침 없이, 낙찰자는 이름이 맞은 출입처, 공고일 대신 보고서 달
  assert.match(sec('B'), /해외 낙찰\(월간 보고서\)\(바레인 입찰위원회\): 바레인 정부 발주처\(보고서 줄 참조\) ← 일진전기\(보고서 줄, 글자 인식\) · ILJINELECTRIC COLTD[^\n]*SOUTH KOREA[^\n]*Sitra 400KV Grid · BHD 34,968,320\(글자 인식 값\) · 2026-08 월간 낙찰 보고서/);
  assert.doesNotMatch(r.text, /66KV Switchgear/);  // 이 원천 첫 실행의 예전 개찰(기준선)은 오늘 항목이 아니다
  const t = await call('partner_filings', { company: '일진' }, opts);
  assert.match(t.text, /\[신규\] 2026-10-25 · 바레인 입찰위원회 개찰 개찰\(응찰\) · 일진전기 · 발주 Electricity and Water Authority \(Planning\)\(BHR\)\n   잡힌 사실: 응찰 ILJIN ELECTRIC BHD 35,004,118\.33 · 상태 Accepted · 응찰가 1위\/3곳\(최저가\) · 응찰 3곳 · 다른 응찰 TAIHAN ELECTRIC WIRE CO LTD BHD 45,648,300 \/ LS CABLE AND SYSTEM LTD BHD 46,659,985\.55/);
  assert.match(t.text, /검증 상태: 입찰위원회 개찰 결과\(응찰가 공개\) — 낙찰 아님/);
  assert.match(t.text, /\n범위: 바레인 입찰위원회 개찰 — 목록 40건\(개찰 2026-10-01~2026-10-25\) · 새 개찰 3 · 상세 3\n/);
  const all = await call('partner_filings', {}, opts);
  assert.match(all.text, /2026-09-01 · 바레인 입찰위원회 개찰 개찰\(응찰\) · LS일렉트릭[^\n]*\n   잡힌 사실: 응찰 LS ELECTRIC CO\., LTD\. 응찰가 미공개 · 상태 Accepted · 응찰가 순위 없음/);
  const items = await (await radarItems(new Request(ORIGIN + '/ingest/radar-items?hours=72', { headers: { Authorization: `Bearer ${TOKEN}` } }), env, { now: NOW })).json();
  assert.deepEqual(items.items.find((x) => x.id === 'bhopen:9001:일진전기').check.terms, ['바레인', '입찰']);
  assert.equal(items.items.find((x) => x.id === 'bh:Aug 2026 Awarding Report.pdf:0').check.since, '2026-08-01');  // 보고서 달부터 보도 대조
  assert.deepEqual(items.items.find((x) => x.id === 'bh:Aug 2026 Awarding Report.pdf:0').check.must, ['바레인']);  // 나라 이름이 기사에 있어야 같은 건
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
  assert.deepEqual(dueAt(new Date('2026-10-28T22:20:00Z')), ['kr-insolvency.yml', 'reverse-check.yml']);  // Thu 07:20 KST(+ 경쟁지 단독 역추적, 11-03)
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
      p('bld:5', { bldNm: '공장 목록에서 빠진 공장', orphan: true }),
      // 기본개요에 주용도가 없어 수집기가 동별개요로 채운 허가(11-02 탐침 110)
      p('bld:6', { bldNm: null, mainPurpsCdNm: null, totArea: 1950, dongs: [{ purpose: '기타공장', structure: '경량철골구조', area: 1950 }], purposeFrom: '동별개요' })] };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/kr-building', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const r = await call('radar_today', { hours: 72 }, opts);
  assert.match(r.text.split('[A · ')[1].split('[B · ')[0], /건축허가: 케이지스틸 주식회사 부지\(충청남도 당진시 송악읍 고대리 1-1번지\) · 신축 공장 · 연면적 12,501㎡ · 허가 2026-10-20 · 착공예정 2026-12-01 — 건축주 미표기\(공장과 같은 번지\)/);
  assert.match(r.text.split('[B · ')[1], /케이지스틸 주식회사 부지와 같은 본번의 다른 필지\(충청남도 당진시 송악읍 고대리 1-7번지\) · 증축 공장 · 연면적 12,501㎡\(건물 전체일 수 있음, 증축분 아님\)[^\n]*건축주 미표기\(공장과 본번만 같은 다른 필지, 건물명 '이웃산업\(주\) 공장'\)/);
  assert.doesNotMatch(r.text, /첫 조회 번지의 옛 허가|공장 목록에서 빠진 공장/);
  assert.match(r.text, /부지\(충청남도 당진시 송악읍 고대리 1-1번지\) · 신축 동별 기타공장 1동 · 연면적 1,950㎡/);
  const t = await call('kr_official', { section: 'building' }, opts);
  assert.match(t.text, /\[공장 부지 건축허가 · 출입처 공장 286곳 중 번지 확인 240곳 · 허가일 최근 90일\] 4건 · 소규모 1건/);
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

test('kr_official law: 법제처 confirmed rules — B new rules in radar_today, C hidden unless show_all, section filter', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const recent = new Date(Date.now() - 3600000).toISOString();
  const today = recent.slice(0, 10);
  const it = (id, kind, tier, title, extra = {}) => ({ id, kind, tier, title, date: today, org: '산업통상부', change: '일부개정', type: '고시', no: '2026-301',
    effective: today, teams: ['전력·에너지'], url: `https://www.law.go.kr/행정규칙/${encodeURIComponent(title)}`, firstSeen: recent, isNew: true, ...extra });
  const doc = { schema: 'kr_official/v1', generatedAt: recent, checks: [{ source: '법제처 행정규칙·법령·해석례', status: 'ok', returned: 3100, kept: 3 }],
    factories: [], events: [], gazette: [], eia: [], eiaSeen: [],
    lawRules: { checkedAt: recent, baselineSince: '2026-11-02T08:10:00+09:00', seen: [],
      items: [it('admrul:2100000280001', '행정규칙', 'B', '전기설비기술기준', { siblings: 1 }),
        it('admrul:2100000280009', '행정규칙', 'B', '전기설비기술기준(별표)', { grouped: 'admrul:2100000280001' }),
        it('admrul:2100000280002', '행정규칙', 'C', '관세법 시행세칙 사무처리에 관한 고시', { org: '관세청', teams: ['공통'] }),
        it('expc:330001', '법령해석례', 'B', '산업통상부 - 「전기사업법」 제7조(발전사업 허가) 관련', { org: '법제처', asker: '산업통상부', type: null, change: null,
          url: 'https://www.law.go.kr/LSW/expcInfoP.do?expcSeq=330001' })] } };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/kr-official', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const t = await call('kr_official', { section: 'law' }, opts);
  assert.match(t.text, /\[법제처 확정 발령 · 출입 업종 행정규칙\(고시·훈령·예규\)·법령·법령해석례 · 확인 [^\]]*\] B 2건 · C 1건 숨김\(show_all=true\)/);
  assert.match(t.text, new RegExp(`- \\[신규\\] B · 발령 ${today} · 행정규칙\\(고시\\) 일부개정 · 산업통상부 · 전력·에너지\\n   잡힌 사실: 전기설비기술기준 \\(발령번호 2026-301\\) 외 같은 번호 1건`));
  assert.doesNotMatch(t.text, /전기설비기술기준\(별표\)/);
  assert.match(t.text, new RegExp(`B · 회신 ${today} · 법령해석례 · 법제처 ← 질의 산업통상부`));
  assert.doesNotMatch(t.text, /관세법 시행세칙/);
  assert.doesNotMatch(t.text, /\[공장등록 변화/);
  assert.match((await call('kr_official', { section: 'law', show_all: true }, opts)).text, /C · 발령 [^\n]*관세청[\s\S]*관세법 시행세칙/);
  const r = await call('radar_today', { include_minor: true }, opts);
  const sec = (x) => r.text.split(`[${x} · `)[1].split(/\n\[[ABC] · /)[0];
  assert.match(sec('B'), /행정규칙\(고시\) 일부개정 · 산업통상부: 전기설비기술기준/);
  assert.match(sec('B'), /법령해석례/);
  assert.match(sec('C'), /관세법 시행세칙/);
});

test('us_litigation osha: OSHA inspections ranked fatality first, routine hidden, dropped names listed, radar_today tiers', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const recent = new Date(Date.now() - 3600000).toISOString();
  const x = (id, company, estab, type, typeName, opened, extra = {}) => ({ id, company, estab, city: 'WEST POINT', state: 'GA', opened, type, typeName, scope: 'B',
    closed: null, naics: '336111', employees: 2700, url: `https://www.osha.gov/ords/imis/establishment.inspection_detail?id=${id}`, violations: [], penaltyInitial: 0,
    penaltyCurrent: 0, accidents: [], firstSeen: recent, isNew: false, ...extra });
  const doc = { schema: 'us_osha/v1', generatedAt: recent, status: 'complete', since: '2025-09-28',
    checks: [{ source: '미국 OSHA(노동부 API)', status: 'ok', returned: 87, kept: 39, calls: 9 }],
    inspections: [x('1007', '현대모비스', 'MOBIS ALABAMA LLC', 'H', '정기(계획)', '2026-10-29'),
      x('1002', '현대차', 'HYUNDAI MOTOR MANUFACTURING ALABAMA, LLC', 'B', '민원', '2026-10-08', { violations: [{ citation: '01001', type: 'R', typeName: '반복', issued: '2026-10-30', initialPenalty: 48000, currentPenalty: 48000 }], penaltyInitial: 48000, penaltyCurrent: 48000 }),
      x('1001', '기아', 'KIA GEORGIA INC', 'M', '사망·중대사고', '2026-09-01', { accidents: [{ summary: '777', date: '2026-08-28', fatality: true, desc: 'Worker struck by press', abstract: '' }] }),
      x('2001', '기아', 'ACME STEEL ERECTORS LLC', 'M', '사망·중대사고', '2026-10-30', { atSite: true, address: '7777 KIA PARKWAY' }),
      x('2003', '기아', 'JOHN DOE PLUMBING', 'B', '민원', '2026-10-31', { atSite: true, address: '7777 KIA PARKWAY' })],
    sites: { '7777 KIA PARKWAY': { raw: '7777 KIA PARKWAY', company: '기아' } },
    events: [{ id: 'osha:viol:1002:2026-10-30', kind: '위반 통지', tier: 'A', company: '현대차', inspection: '1002', text: 'OSHA 위반 통지 2026-10-30 · 1건(반복) · 최초 벌금 합 $48,000 · HYUNDAI MOTOR MANUFACTURING ALABAMA, LLC (MONTGOMERY, AL)', url: 'https://www.osha.gov/x', detectedAt: recent },
      { id: 'osha:insp:1007', kind: '점검 개시', tier: 'C', company: '현대모비스', inspection: '1007', text: 'OSHA 점검 개시 2026-10-29 · 정기(계획)(H)', url: 'https://www.osha.gov/y', detectedAt: recent }],
    dropped: [['PAT PECK KIA OF GULFPORT', 1], ["ARMANDO'S MANDO GRILL", 1]] };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/us-osha', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {})).status, 200);
  const t = await call('us_litigation', {}, opts);
  assert.match(t.text, /미국 소송·ITC 결과가 아직 없음/);  // 소송 결과가 없어도 OSHA 구역은 나온다
  assert.match(t.text, /\[미국 OSHA 점검·위반 · 출입처 미국 법인·공장 · 개시 2025-09-28 이후 · 확인 [^\]]*\] 3건 · 정기·후속·모니터링 점검과 공장 주소 하도급의 일반 점검 2건 숨김\(include_routine=true\) · 원천 ok · 지켜보는 공장 주소 1곳/);
  assert.match(t.text, /개시 2026-10-30 · 기아\(공장 주소 하도급\) · 사망·중대사고\(M\) 점검[^\n]*\n   사업장: ACME STEEL ERECTORS LLC — 출입처\(기아\) 공장 주소 7777 KIA PARKWAY/);
  assert.doesNotMatch(t.text, /JOHN DOE PLUMBING/);
  assert.ok(t.text.indexOf('KIA GEORGIA') < t.text.indexOf('HYUNDAI MOTOR MANUFACTURING'));  // 사망·중대사고 먼저
  assert.match(t.text, /사고 요약 2026-08-28 · 사망: Worker struck by press/);
  assert.match(t.text, /위반 통지 1건\(반복\) · 최초 벌금 합 \$48,000/);
  assert.doesNotMatch(t.text, /MOBIS ALABAMA/);
  assert.match(t.text, /뺀 사업장 2곳[^\n]*PAT PECK KIA OF GULFPORT\(1\)/);
  assert.match((await call('us_litigation', { include_routine: true }, opts)).text, /MOBIS ALABAMA/);
  const r = await call('radar_today', { include_minor: true }, opts);
  const sec = (k) => r.text.split(`[${k} · `)[1].split(/\n\[[ABC] · /)[0];
  assert.match(sec('A'), /OSHA 위반 통지 2026-10-30 · 1건\(반복\)[^\n]*회사 책임 확정 아님/);
  assert.match(sec('C'), /OSHA 점검 개시 2026-10-29/);
});

test('weekday watches are not stale over the weekend (11-01: 미국 소송·ITC 37시간 전 경고 on a Sunday)', async () => {
  const fri = Date.parse('2026-10-30T13:33:00+09:00');
  assert.equal(Math.round(weekdayHours(fri, Date.parse('2026-11-01T02:50:00+09:00')) * 10) / 10, 10.5);  // Fri 13:33 → Sat 00:00 only
  assert.equal(weekdayHours(fri, Date.parse('2026-11-02T07:00:00+09:00')), 10.45 + 7);
  assert.equal(ageNote({ now: new Date('2026-11-01T02:50:00+09:00') }, '2026-10-30T13:33:00+09:00'), '');
  assert.match(ageNote({ now: new Date('2026-11-01T02:50:00+09:00') }, '2026-10-30T13:33:00+09:00', 36, true), /⚠ 37시간 전/);  // daily watch
  assert.match(ageNote({ now: new Date('2026-11-03T09:00:00+09:00') }, '2026-10-30T13:33:00+09:00'), /⚠ 91시간 전/);  // Mon run missed too
  const opts = PRIVATE();
  const doc = { schema: 'us_litigation/v1', generatedAt: '2026-10-30T13:33:00+09:00', windowDays: 45, checks: [{ source: 'CourtListener', status: 'ok', returned: 1 }], cases: [], decisions: [], itc: [] };
  assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/us-litigation', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), opts.env, {})).status, 200);
  const sun = await call('radar_today', { hours: 48 }, { ...opts, now: new Date('2026-11-01T02:50:00+09:00') });
  assert.doesNotMatch(sun.text, /미국 소송·ITC: ⚠/);
  const tue = await call('radar_today', { hours: 48 }, { ...opts, now: new Date('2026-11-03T09:00:00+09:00') });
  assert.match(tue.text, /미국 소송·ITC: ⚠ 91시간 전 결과/);
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
  assert.deepEqual(stackHint({ company: '포스코', site: '㈜포스코 광양제철소', kind: '배출구 오래 멈춤' }).terms, ['광양', '가동 중단', '개수', '정비']);
  // 사흘 넘게 목록에서 빠진 배출구·사업장은 폐쇄 기사와 맞춰 본다
  assert.deepEqual(stackHint({ company: '롯데케미칼', site: '롯데케미칼㈜ 울산1공장', kind: '배출구 오래 빠짐' }).terms, ['울산', '폐쇄', '가동 중단']);
  assert.deepEqual(stackHint({ company: '금호석유화학', site: '금호석유화학㈜ 울산고무공장', kind: '사업장 오래 빠짐(굴뚝 측정)' }).terms, ['울산', '폐쇄', '가동 중단']);
  // 지명은 출입처 공장 시·군 목록에서 먼저 찾는다('공장' 앞 두 글자는 '고무'·'무제'가 됐다)
  assert.deepEqual(['금호석유화학(주)여수고무제1공장', '현대제철㈜ 인천공장', '한화솔루션㈜ 진천사업장', '기아㈜ 광주2공장', '고려아연㈜온산제련소', '에스케이이노베이션 주식회사'].map(siteCity),
    ['여수', '인천', '진천', '광주', '온산', undefined]);
  const kh = kepcoHint('765kV 전력용변압기 1Bank(3대) - 신안성S/S');  // 10-31 운영: 예전엔 "한국전력공사 한전"으로 찾았다
  assert.deepEqual([kh.who, kh.terms, kh.places], ['한전', ['765kV', '변압기', '발주'], ['765kV']]);
  assert.deepEqual(kepcoHint('배전용 자재 구매').terms, ['발주']);
  assert.deepEqual(wf('새 공사 현장', '…'), ['공사', '착공']);
  assert.deepEqual(wf('사업장 탈퇴', '…'), ['공장', '폐쇄']);
});

test('조용한 0건: 정상 응답인데 원천이 두 번 연달아 0줄·급감하면 형식 변경 의심, 줄 수가 돌아오면 사라진다', async () => {
  const run = (prev, checks) => returnedWatch(prev, { checks }, '2026-11-09T00:00:00Z');
  const seq = (source, ns, extra = {}) => ns.reduce((rw, n) => run(rw, [{ source, status: 'ok', returned: n, ...extra }]), null);
  assert.deepEqual(seq('울주군', [10, 12, 11, 9, 0]).silent, undefined);              // 한 번 0은 아직
  const z = seq('울주군', [10, 12, 11, 9, 0, 0]);
  assert.deepEqual(z.silent, [{ source: '울주군', kind: 'zero', now: 0, before: [9, 11, 12, 10], limit: 0, since: '2026-11-09T00:00:00Z' }]);
  assert.deepEqual(z.hist['울주군'], [0, 0, 9, 11, 12, 10]);
  assert.equal(run(z, [{ source: '울주군', status: 'ok', returned: 0 }]).silent.length, 1);  // 0이 이어지면 의심도 이어 간다
  assert.equal(run(z, [{ source: '울주군', status: 'failed', error: 'x' }]).silent.length, 1);  // 실패한 실행은 이력·의심을 그대로
  assert.equal(run(z, [{ source: '울주군', status: 'ok', returned: 8 }]).silent, undefined);  // 돌아오면 사라짐
  assert.deepEqual(seq('굴뚝', [300, 280, 310, 290, 12, 9]).silent.map((x) => [x.kind, x.now, x.limit]), [['drop', 9, 29]]);  // 1/10 아래로 두 번
  assert.equal(seq('굴뚝', [300, 280, 310, 290, 40, 35]).silent, undefined);
  assert.equal(seq('의회', [1, 2, 1, 1, 0, 0]).silent, undefined);                   // 원래 적은 원천(3줄 미만)은 세지 않음
  const noted = [0, 0].reduce((rw, n) => run(rw, [{ source: '국민연금', status: 'ok', returned: n, note: '새 달 없음' }]), seq('국민연금', [5, 6, 5, 6]));
  assert.equal(noted.silent, undefined);  // 감시가 이유를 적은 0은 세지 않는다
  assert.deepEqual(noted.hist['국민연금'], [6, 5, 6, 5]);
  assert.equal(run(null, [{ source: 'x', status: 'ok' }]), null);                      // 줄 수 없는 원천만 있으면 붙이지 않음
  // 저장: 원래 글자는 그대로 두고 끝에 덧붙인다(파이썬 감시가 다시 읽을 때 1.0 → 1처럼 바뀌지 않게) → radar_today 수집 상태
  const opts = PRIVATE();
  const post = async (n, at) => {
    const text = `{"schema": "kr_local/v1", "generatedAt": "${at}", "status": "ok", "score": 1.0, "checks": [{"source": "울주군", "status": "ok", "returned": ${n}}], "items": []}`;
    assert.equal((await worker.fetch(new Request(ORIGIN + '/ingest/kr-local', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: text }), opts.env, {})).status, 200);
    return text;
  };
  let last = '';
  for (const [i, n] of [10, 12, 11, 9, 0, 0].entries()) last = await post(n, `2026-11-0${3 + i}T06:30:00+09:00`);
  const stored = await (await worker.fetch(new Request(ORIGIN + '/ingest/kr-local', { headers: { Authorization: `Bearer ${TOKEN}` } }), opts.env, {})).text();
  assert.ok(stored.startsWith(last.slice(0, -1) + ',"_returnedWatch":'));
  assert.match(stored, /"score": 1\.0/);
  assert.equal(lastReturnedWatch(stored).silent[0].source, '울주군');
  const h = (await call('radar_today', { hours: 24 }, { ...opts, now: new Date('2026-11-08T22:00:00Z') })).text;
  assert.match(h, /^- 지자체 고시·공고: ⚠ 형식 변경 의심 1곳\(울주군: 정상 응답인데 0줄, 이전 9·11·12·10줄\) — 원문 사이트 목록이 보이는지 확인 — 해당 부분 0건은 미확인$/m);
  // 이전 문서를 통째로 이어 쓴 감시(옛 이력 키가 들어 있음)도 다시 직렬화하지 않고 덧붙인다 — 마지막 키가 이긴다
  const carried = JSON.parse(stored);
  carried.generatedAt = '2026-11-08T16:20:00+09:00';
  const ctext = JSON.stringify(carried);
  await worker.fetch(new Request(ORIGIN + '/ingest/kr-local', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: ctext }), opts.env, {});
  const stored2 = await (await worker.fetch(new Request(ORIGIN + '/ingest/kr-local', { headers: { Authorization: `Bearer ${TOKEN}` } }), opts.env, {})).text();
  assert.ok(stored2.startsWith(ctext.slice(0, -1) + ',"_returnedWatch":'));
  assert.equal(JSON.parse(stored2)._returnedWatch.hist['울주군'].length, 6);
  assert.deepEqual(JSON.parse(stored2)._returnedWatch, lastReturnedWatch(stored2));
  await post(14, '2026-11-09T06:30:00+09:00');
  assert.doesNotMatch((await call('radar_today', { hours: 24 }, { ...opts, now: new Date('2026-11-08T22:00:00Z') })).text, /형식 변경 의심/);
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
  // 첨부 공고문에서 뽑은 사업 개요(11-02 탐침 104 울주 68156 공고문.hwpx): 레이더 줄은 본문 앞부분 대신 개요, 화면에는 개요·못 읽은 첨부·안 연 첨부
  doc.items.push(it('local:울주군:68160', { no: '울산광역시 울주군 공고 제2026-2799호', title: '건설공사 안전점검 수행기관 지정 공고[온산 고려아연(주), #3 TANK 토건공사]',
    detail: { title: '건설공사 안전점검 수행기관 지정 공고[온산 고려아연(주), #3 TANK 토건공사]', body: '우리 군 온산읍 일원 공장 용도 건축공사', files: ['예정공정표.pdf', '공고문.hwpx', '붙임1.hwpx'] },
    attachments: [{ name: '공고문.hwpx', chars: 2542, facts: { 사업명: '#3 TANK 토건공사', 공사기간: '2026. 9. ~ 2027. 2.', 위치: '울주군 온산읍 원산리 892번지 일원',
      '발주자/시공자': '고려아연(주) / 서동건설산업(주)', 규모: '철근콘크리트구조 지상1층', 착공일: '2026. 9. 8.' } },
      { name: '예정공정표.pdf', chars: 2, note: '글자 없음(스캔 이미지일 수 있음)' }] }));
  // 감시가 남긴 운영 제안(11-08 직접 조회 실패가 잦은 시·군)은 수집 상태와 kr_official local에 그대로
  doc.healthNote = '직접 조회 실패·일부 실패가 잦은 시·군: 평택시 3/20번 — 기자 컴퓨터 대신 수집 후보(추가는 기자 결정, 실패한 날 그 시·군 0건은 미확인)';
  await worker.fetch(new Request(ORIGIN + '/ingest/kr-local', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {});
  const r3 = await call('radar_today', { hours: 72 }, opts);
  assert.match(r3.text, /^- 지자체 고시·공고: 직접 조회 실패·일부 실패가 잦은 시·군: 평택시 3\/20번 — 기자 컴퓨터 대신 수집 후보\(추가는 기자 결정, 실패한 날 그 시·군 0건은 미확인\)$/m);
  assert.match(r3.text, /#3 TANK 토건공사\]」 · 건축과 · 등록 2026-10-25 · 첨부 개요: 공사기간 2026\. 9\. ~ 2027\. 2\. · 착공일 2026\. 9\. 8\. · 발주자\/시공자 고려아연\(주\) \/ 서동건설산업\(주\) · 규모 철근콘크리트구조 지상1층 — 제목·본문·첨부 개요 자동 추출/);
  const t3 = await call('kr_official', { section: 'local', company: '고려아연' }, opts);
  assert.match(t3.text, /\n직접 조회 실패·일부 실패가 잦은 시·군: 평택시 3\/20번 — 기자 컴퓨터 대신 수집 후보/);
  assert.match(t3.text, /첨부 원문에서 뽑은 사업 개요\(자동 — 첨부 원문 확인\): 사업명 #3 TANK 토건공사 · 공사기간 2026\. 9\. ~ 2027\. 2\. · 착공일 2026\. 9\. 8\. · 위치 울주군 온산읍 원산리 892번지 일원 · 발주자\/시공자 고려아연\(주\) \/ 서동건설산업\(주\) · 규모 철근콘크리트구조 지상1층/);
  assert.match(t3.text, /못 읽은 첨부: 예정공정표\.pdf\(글자 없음\(스캔 이미지일 수 있음\)\)\n   첨부 파일\(열지 않음\): 붙임1\.hwpx/);
  assert.deepEqual(dueAt(new Date('2026-10-26T21:30:00Z')), ['page-watch.yml', 'kr-local.yml']);  // Tue 06:30 KST
  assert.deepEqual(dueAt(new Date('2026-10-27T07:20:00Z')), ['kr-local.yml']);                    // Tue 16:20 KST
});

test('Aside 직접 올리기(/upload/browser): 등록한 열쇠 지문과 맞을 때만 local_notice_submit과 같은 규칙으로 저장, 틀리면 404', async () => {
  const seen = [];
  const fetch = async (url) => { seen.push(url); return new Response(null, { status: 204 }); };
  const opts = { ...PRIVATE({ GITHUB_DISPATCH_TOKEN: 'ghp_test' }), fetch };
  const page = await worker.fetch(new Request(ORIGIN + '/upload/browser'), opts.env, {});
  assert.equal(page.status, 200);
  assert.match(page.headers.get('Content-Security-Policy'), /connect-src 'self'/);
  assert.doesNotMatch(await page.text(), /script/i);
  const sha = (k) => createHash('sha256').update(k).digest('hex');
  const key = 'k'.repeat(43);
  const post = (k, body) => browserUpload(new Request(ORIGIN + '/upload/browser', { method: 'POST',
    headers: { Authorization: `Bearer ${k}`, 'Content-Type': 'application/json' }, body: JSON.stringify(body) }), opts.env, { fetch });
  assert.equal((await post(key, { via: 'aside' })).status, 404);  // 등록 전
  assert.match((await call('browser_upload_key', {}, opts)).text, /등록된 열쇠 없음/);
  assert.ok((await call('browser_upload_key', { sha256: 'xyz' }, opts)).isError);
  assert.match((await call('browser_upload_key', { sha256: sha(key) }, opts)).text, /열쇠 등록함 · 지문 [0-9a-f]{8}…/);
  assert.equal((await post('w'.repeat(43), { via: 'aside' })).status, 404);  // 틀린 열쇠
  assert.equal((await worker.fetch(new Request(ORIGIN + '/upload/browser', { method: 'POST', body: '{}' }), opts.env, {})).status, 404);  // 열쇠 없음
  const ok = await (await post(key, { via: 'aside', cities: [{ city: '나주시', rows: [{ mgt: '42465',
    cells: ['나주시 고시 제2026-253호', '도로명주소 부여 고시', '시민봉사과', '2026-11-06'] }, { mgt: "1');x", cells: ['x'] }] }, { city: '서울 강남구' }] })).json();
  assert.equal(ok.ok, true);
  assert.match(ok.text, /· Aside · 시·군 1곳 \(정상 1\)/);
  assert.match(ok.text, /- 나주시: 1줄 · 버린 줄 1/);
  assert.match(ok.text, /받지 않은 이름\(허용 목록 밖\): 서울 강남구/);
  assert.deepEqual(seen.map((u) => u.split('/').slice(-2)[0]), ['kr-local.yml']);
  const got = await (await worker.fetch(new Request(ORIGIN + '/ingest/kr-local-browser', { headers: { Authorization: `Bearer ${TOKEN}` } }), opts.env, {})).json();
  assert.equal(got.cities.find((c) => c.city === '나주시').via, 'aside');
  assert.match((await call('browser_upload_key', {}, opts)).text, /마지막 올림 20\d\d-/);
  assert.equal((await (await post(key, {})).json()).ok, false);  // 빈 인자는 저장하지 않음
  assert.equal((await browserUpload(new Request(ORIGIN + '/upload/browser', { method: 'POST', headers: { Authorization: `Bearer ${key}` }, body: 'x'.repeat(400_001) }), opts.env, { fetch })).status, 413);
  // 새 열쇠를 등록하면 이전 열쇠는 못 쓴다 — local_notice_submit으로도 등록(새 도구를 모르는 세션용)
  const viaSubmit = await call('local_notice_submit', { uploadKeySha256: sha('n'.repeat(43)) }, opts);
  assert.ok(!viaSubmit.isError);
  assert.match(viaSubmit.text, /열쇠 등록함 · 지문 [0-9a-f]{8}… · .*이전 열쇠는 이제 못 씀/);
  assert.equal((await post(key, { via: 'aside' })).status, 404);
  assert.equal((await post('n'.repeat(43), { via: 'aside', labor: [{ commission: '제주지방노동위원회', error: '시험' }] })).status, 200);
  assert.ok((await call('local_notice_submit', { uploadKeySha256: 'zz' }, opts)).isError);
});

test('GitHub 실행 실패 감시: 매시 00·30분에 main 실행을 읽어 쌓고, 두 번 이상 연달아 실패한 프로그램을 radar_today 맨 위에', async () => {
  assert.equal(pollDue(new Date('2026-11-08T00:00:30Z')), true);   // 09:00 KST
  assert.equal(pollDue(new Date('2026-11-08T00:35:00Z')), true);   // 09:30 칸
  assert.equal(pollDue(new Date('2026-11-08T00:20:00Z')), false);
  const run = (id, path, at, c, name = 'Radar Press Check', status = 'completed') => ({ id, path: `.github/workflows/${path}`, name, run_started_at: at, created_at: at, status, conclusion: c, event: 'schedule' });
  // 취소는 건너뛰고, 성공을 만나면 멈춘다
  const wf = mergeRuns({}, [run(1, 'p.yml', '2026-11-05T03:50:00Z', 'success'), run(2, 'p.yml', '2026-11-05T09:50:00Z', 'failure'),
    run(3, 'p.yml', '2026-11-05T17:40:00Z', 'cancelled'), run(4, 'p.yml', '2026-11-05T23:50:00Z', 'timed_out'), run(5, 'p.yml', '2026-11-06T01:00:00Z', null, 'x', 'in_progress')],
  Date.parse('2026-11-06T02:00:00Z'));
  assert.deepEqual(wf['p.yml'].runs.map((r) => r.id), [4, 3, 2, 1]);
  assert.equal(failStreak(wf['p.yml']), 2);
  assert.equal(wf['p.yml'].lastSuccessAt, '2026-11-05T03:50:00Z');
  // 다시 실행해 결과가 바뀌면 같은 id를 덮는다, 오래 안 돈 워크플로는 잊는다
  const again = mergeRuns(wf, [run(4, 'p.yml', '2026-11-05T23:50:00Z', 'success')], Date.parse('2026-11-06T02:00:00Z'));
  assert.equal(failStreak(again['p.yml']), 0);
  assert.deepEqual(mergeRuns(wf, [], Date.parse('2026-12-10T00:00:00Z')), {});
  // 예약(00분 칸) → GitHub 목록 읽기 → radar_today 맨 위
  const opts = PRIVATE({ GITHUB_DISPATCH_TOKEN: 'ghp_test' });
  const seen = [];
  const list = [run(10, 'radar-press-check.yml', '2026-11-05T03:50:00Z', 'success'), run(11, 'radar-press-check.yml', '2026-11-05T09:50:00Z', 'failure'),
    run(12, 'radar-press-check.yml', '2026-11-06T09:50:00Z', 'failure'), run(13, 'radar-press-check.yml', '2026-11-06T16:57:00Z', 'failure'),
    run(20, 'kr-local.yml', '2026-11-07T15:21:00Z', 'success', 'Local Government Notices Watch'), run(21, 'kr-local.yml', '2026-11-07T07:20:00Z', 'failure', 'Local Government Notices Watch'),
    // 배포 뒤 운영 점검은 한 번만 실패해도 알린다(11-13 오류 1102)
    run(30, 'worker-smoke.yml', '2026-11-07T12:00:00Z', 'success', 'Worker 배포 뒤 운영 점검'), run(31, 'worker-smoke.yml', '2026-11-07T14:40:00Z', 'failure', 'Worker 배포 뒤 운영 점검')];
  const fetchMock = async (url, init) => { seen.push({ url, init }); return url.includes('/actions/runs?') ? Response.json({ workflow_runs: list }) : new Response(null, { status: 204 }); };
  await runSchedule(opts.env, new Date('2026-11-07T15:00:00Z'), { fetch: fetchMock });  // 일 00:00 KST(요청 칸 없음, 확인 칸)
  const get = seen.find((x) => x.url.includes('/actions/runs?'));
  assert.equal(get.url, 'https://api.github.com/repos/shhong9173-art/seoul-reporting-radar/actions/runs?branch=main&status=completed&per_page=100&exclude_pull_requests=true');
  assert.equal(get.init.headers.Authorization, 'Bearer ghp_test');
  assert.equal(get.init.method, undefined);  // 읽기만
  const top = async (iso) => (await call('radar_today', { hours: 24 }, { ...opts, now: new Date(iso) })).text.split('[먼저 볼 것: 수집 상태]\n')[1]?.split('\n\n')[0] ?? '';
  const h = await top('2026-11-07T15:20:00Z');
  assert.match(h, /^- ⚠ GitHub 실행 3회 연속 실패: Radar Press Check\(radar-press-check\.yml\) · 마지막 실패 11-07 01:57 KST · 마지막 성공 11-05 12:50 KST — 이 프로그램이 만드는 결과는 그 성공 때 것, 그 뒤 0건은 미확인$/m);
  assert.doesNotMatch(h, /kr-local\.yml/);  // 마지막이 성공
  assert.match(h, /^- ⚠ 배포 뒤 운영 점검 실패\(1회 연속\): 기자 전용 도구 일부가 운영에서 끊겼을 수 있다\(오류 1102 등\) · 마지막 실패 11-07 23:40 KST · 마지막 성공 11-07 21:00 KST — 실패한 도구의 0건·오류는 미확인$/m);
  assert.doesNotMatch(h, /GitHub 실행 상태/);  // 확인 정상
  // 확인이 두 시간 넘게 멈추면(예약 꺼짐 등) 그 자체를 알린다
  assert.match(await top('2026-11-07T18:00:00Z'), /- GitHub 실행 상태\(30분마다 확인\): 확인이 멈춤 · 마지막 정상 확인 11-08 00:00 KST — 그 뒤 실패는 미확인/);
  // 읽기 실패(권한 등)는 그대로 적고, 쌓아 둔 기록은 지우지 않는다
  await runSchedule(opts.env, new Date('2026-11-07T15:30:00Z'), { fetch: async () => new Response('{}', { status: 403 }) });
  const h2 = await top('2026-11-07T15:35:00Z');
  assert.match(h2, /GitHub 실행 상태\(30분마다 확인\): 읽기 실패\(HTTP 403\) · 마지막 정상 확인 11-08 00:00 KST/);
  assert.match(h2, /3회 연속 실패: Radar Press Check/);
  // 고친 뒤 성공하면 줄이 사라진다
  list.push(run(14, 'radar-press-check.yml', '2026-11-07T15:29:00Z', 'success'));
  await runSchedule(opts.env, new Date('2026-11-07T16:00:00Z'), { fetch: fetchMock });
  assert.doesNotMatch(await top('2026-11-07T16:05:00Z'), /GitHub 실행/);
  // 토큰이 없으면 확인하지 못했다고 적는다
  const none = PRIVATE();
  await runSchedule(none.env, new Date('2026-11-07T16:00:00Z'), { fetch: async () => { throw new Error('must not call'); } });
  assert.match((await call('radar_today', {}, { ...none, now: new Date('2026-11-07T16:05:00Z') })).text, /GitHub 실행 상태\(30분마다 확인\): 워커에 GITHUB_DISPATCH_TOKEN 없음/);
});

test('radar_today 수집 상태: 기자 컴퓨터(Aside) 수집이 예정 시각 뒤 안 올라오거나 이 길뿐인 시·군을 못 읽으면 알린다', async () => {
  const slot = (iso) => new Date(lastBrowserSlot(Date.parse(iso))).toISOString();
  assert.equal(slot('2026-11-09T00:00:00Z'), '2026-11-06T07:00:00.000Z');  // 월 09:00 KST → 금 16:00(월 09:00은 여유 45분 안) — 11-11부터 09:00·16:00
  assert.equal(slot('2026-11-09T00:30:00Z'), '2026-11-06T07:00:00.000Z');  // 월 09:30 → 아직 금 16:00
  assert.equal(slot('2026-11-09T01:00:00Z'), '2026-11-09T00:00:00.000Z');  // 월 10:00 → 월 09:00
  assert.equal(slot('2026-11-07T03:00:00Z'), '2026-11-06T07:00:00.000Z');  // 토 12:00 → 금 16:00
  assert.equal(slot('2026-11-10T05:00:00Z'), '2026-11-10T00:00:00.000Z');  // 화 14:00 → 화 09:00
  const fetch = async () => new Response(null, { status: 204 });
  const opts = { ...PRIVATE({ GITHUB_DISPATCH_TOKEN: 'ghp_test' }), fetch };
  const line = async (iso) => ((await call('radar_today', { hours: 24 }, { ...opts, now: new Date(iso) })).text.match(/^- 기자 컴퓨터 수집.*$/m) ?? [null])[0];
  assert.match(await line('2026-11-09T00:00:00Z'), /^- 기자 컴퓨터 수집\(Aside 예약 작업, 평일 09:00·16:00[^)]*\): 결과 없음 — 미확인$/);
  const rows = [{ mgt: '1', cells: ['제2026-1호', '고시', '과', '2026-11-06'] }];
  const cities = ['인천 부평구', '구미시', '청주시', '순천시', '함평군', '양산시']
    .map((city) => (city === '구미시' ? { city, error: 'ReadTimeout' } : city === '양산시' ? { city, error: '시간 초과' } : { city, rows }));
  const submit = (via, iso) => call('local_notice_submit', { via, cities, labor: [{ commission: '중앙노동위원회', error: '시험' }],
    pages: [{ id: 'au-trn', error: '시험' }] }, { ...opts, now: new Date(iso) });
  assert.ok(!(await submit('aside', '2026-11-06T07:42:00Z')).isError);  // 금 16:42 KST
  // 월 09:00: 가장 최근 예정(금 16:00)은 올라옴 — 이 길뿐인 시·군 중 못 읽은 곳만(양산은 GitHub 직접 조회가 있어 뺌)
  assert.equal(await line('2026-11-09T00:00:00Z'), '- 기자 컴퓨터 수집(Aside 예약 작업, 평일 09:00·16:00 — 해외 IP 차단 시·군 고시·공고·노동위 회의·호주 TRN): '
    + '시·군 못 읽음 1곳(구미: ReadTimeout) — 해당 부분 0건은 미확인');
  // 월 10:00: 09:00 예정 수집이 안 올라옴(컴퓨터 꺼짐 등)
  assert.match(await line('2026-11-09T01:00:00Z'), /: ⚠ 마지막 11-06 16:42 KST\(65시간 전\) — 11-09 09:00 KST 예정 수집이 안 올라옴\(기자 컴퓨터·Claude 앱·Aside가 켜져 있는지 확인\. 예정 시각에 컴퓨터 연결이 없으면 예약 작업이 저절로 꺼질 수 있다 — Claude 앱 예약 작업 목록에서 '새올 고시·공고 브라우저 수집'이 켜져 있는지도 확인\)\. 그 뒤 인천 부평구·구미·청주·순천·함평 고시·공고는 미확인 — /);
  // 직접 올리기 열쇠가 있는데 대화로 옮겨 올린 경우, 내장 브라우저로 대신한 경우
  const sha = createHash('sha256').update('k'.repeat(43)).digest('hex');
  await call('browser_upload_key', { sha256: sha }, { ...opts, now: new Date('2026-11-09T00:00:00Z') });
  assert.ok(!(await submit('aside', '2026-11-10T00:03:00Z')).isError);  // 화 09:03
  assert.match(await line('2026-11-10T01:00:00Z'), /구미: ReadTimeout\) · 직접 올리기가 안 돼 대화로 옮겨 올림\(올리기 열쇠 확인 — browser_upload_key\) — /);
  assert.ok(!(await submit('browser', '2026-11-10T07:45:00Z')).isError);  // 화 16:45
  assert.match(await line('2026-11-10T08:30:00Z'), / · Aside가 안 돼 내장 브라우저로 대신 수집함 — /);
  // 시·군만 올리고 노동위·TRN이 빠진 경우
  await call('local_notice_submit', { via: 'aside', cities: [{ city: '청주시', rows }] }, { ...opts, now: new Date('2026-11-11T00:02:00Z') });   // 수 09:02
  assert.match(await line('2026-11-11T01:00:00Z'), /노동위 회의일정은 이번 수집에 빠짐\(마지막 11-10 16:45 KST\) · 호주 TRN은 이번 수집에 빠짐\(마지막 11-10 16:45 KST\)/);
});

test('local_notice_submit via Aside: 출입처 줄 상세(제목·본문 앞·첨부 이름)를 글자만 크기 제한해 받고, 수집 길(via)을 남긴다', async () => {
  const fetch = async () => new Response(null, { status: 204 });
  const opts = { ...PRIVATE({ GITHUB_DISPATCH_TOKEN: 'ghp_test' }), fetch };
  const tool = (await rpc('tools/list', {}, opts)).body.result.tools.find((x) => x.name === 'local_notice_submit');
  assert.deepEqual(tool.inputSchema.properties.via.enum, ['aside', 'browser']);
  assert.ok(tool.inputSchema.properties.cities.items.properties.rows.items.properties.detail);
  const rows = Array.from({ length: 10 }, (_, i) => ({ mgt: String(500 + i), cells: [`공고 ${i}`, '2026-11-06'],
    detail: { title: `LG화학 나주공장 공고 ${i} `.repeat(30), body: '본문 '.repeat(300), files: ['a.hwp', ' ', 'b.pdf', 'c', 'd', 'e', 'f', 'g'] } }));
  rows[0].detail.attachments = [{ name: '공고문.hwpx', text: '공 사 명 : 시험 '.repeat(600) }, { name: '도면.pdf', error: 'pdf — 기자 컴퓨터에서는 안 읽음' },
    { name: '' }, { name: '빈.hwpx' }, { name: '넷째.hwpx', text: 'x' }];
  rows.push({ mgt: '999', cells: ['제목 없는 상세'], detail: { body: 'x' } });
  const r = await call('local_notice_submit', { via: 'aside', cities: [{ city: '나주시', rows }] }, opts);
  assert.equal(r.isError, false);
  assert.match(r.text, /브라우저 수집 저장 · [^\n]*· Aside · 시·군 1곳/);
  assert.match(r.text, /- 나주시: 11줄 · 상세 8/);
  const got = await (await worker.fetch(new Request(ORIGIN + '/ingest/kr-local-browser', { headers: { Authorization: `Bearer ${TOKEN}` } }), opts.env, {})).json();
  assert.equal(got.via, 'aside');
  const city = got.cities.find((c) => c.city === '나주시');
  assert.equal(city.via, 'aside');
  assert.equal(city.details, 8);
  const d = city.rows[0].detail;
  assert.ok(d.title.length <= 300 && d.body.length <= 420);
  assert.deepEqual(d.files, ['a.hwp', 'b.pdf', 'c', 'd', 'e']);  // 6개까지, 빈 이름은 버림
  assert.equal(d.attachments.length, 2);                            // 3개까지 보고 이름 없는 것은 버림
  assert.equal(d.attachments[0].text.length, 4000);
  assert.deepEqual(d.attachments[1], { name: '도면.pdf', error: 'pdf — 기자 컴퓨터에서는 안 읽음' });
  assert.equal(city.rows[1].detail.attachments, undefined);
  assert.equal(city.rows.filter((x) => x.detail).length, 8);     // 시·군마다 8줄까지
  assert.equal(city.rows.at(-1).detail, undefined);              // 제목 없는 상세는 버림
  // 모르는 수집 길은 남기지 않는다
  await call('local_notice_submit', { via: 'evil', cities: [{ city: '구미시', rows: [{ mgt: '7', cells: ['x'] }] }] }, opts);
  const got2 = await (await worker.fetch(new Request(ORIGIN + '/ingest/kr-local-browser', { headers: { Authorization: `Bearer ${TOKEN}` } }), opts.env, {})).json();
  assert.equal(got2.via, undefined);
  assert.equal(got2.cities.find((c) => c.city === '구미시').via, undefined);
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
    checks: [{ source: '인천 부평구', status: 'ok', returned: 30, via: '기자 컴퓨터 브라우저 수집 2026-10-25T23:45' }, { source: '당진시', status: 'ok', returned: 60 },
      { source: '나주시', status: 'ok', returned: 30, via: '기자 컴퓨터 브라우저 수집 2026-11-06T08:45 KST · Aside' }] };
  doc.items.push({ id: 'local:나주시:7001', city: '나주시', no: '나주시 공고 제2026-900호', title: 'LG화학(주) 관련 공고', dept: '건축과', date: '2026-11-06',
    company: 'LG화학', companies: ['LG화학'], tier: 'A', listTier: 'B', firstSeen: '2026-11-06T08:50:00+09:00', isNew: true, detailVia: 'browser',
    detail: { title: '건설공사 안전점검 수행기관 지정 공고[LG화학 나주공장 증설공사]', body: '나주시 송월동 일원', files: ['공고문.hwpx'] },
    url: 'https://eminwon.naju.go.kr/x', listUrl: 'https://eminwon.naju.go.kr/y' });
  doc.generatedAt = '2026-11-06T08:50:00+09:00';
  await worker.fetch(new Request(ORIGIN + '/ingest/kr-local', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), opts.env, {});
  const local = (await call('kr_official', { section: 'local' }, opts)).text;
  assert.match(local, /기자 컴퓨터 브라우저로 읽은 곳\(해외 IP 차단\): 인천 부평구\(2026-10-25 23:45\), 나주시\(2026-11-06 08:45 Aside\)/);
  assert.match(local, /본문 앞부분\(상세 페이지, 기자 컴퓨터에서 읽음\): 나주시 송월동 일원/);
  assert.match(local, /첨부 파일\(열지 않음 — 해외 IP 차단 시·군이라 첨부는 기자가 직접\): 공고문\.hwpx/);
  doc.items.at(-1).attachments = [{ name: '공고문.hwpx', chars: 900, facts: { 공사기간: '2026. 11. ~ 2027. 6.' } }];
  doc.generatedAt = '2026-11-06T09:50:00+09:00';
  await worker.fetch(new Request(ORIGIN + '/ingest/kr-local', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), opts.env, {});
  const local2 = (await call('kr_official', { section: 'local' }, opts)).text;
  assert.match(local2, /첨부 원문에서 뽑은 사업 개요\(자동·기자 컴퓨터에서 읽음 — 첨부 원문 확인\): 공사기간 2026\. 11\. ~ 2027\. 6\./);
  assert.doesNotMatch(local2, /첨부는 기자가 직접/);
  assert.match(local, /등급: 목록 제목으로 B → 전체 제목으로 A/);
});

test('처리 장부(11-13): 기자가 접음·보류·발제함으로 남긴 패키지와 이어진 항목은 radar_today에서 숨기고 구역 도구엔 〔이미 처리〕를 붙인다', async () => {
  // 실제 패키지 제목(11-13 운영)과 실제 항목 글 발췌
  const pk = (name, title, state, updated_at, body = '') => ({ name, title, state, updated_at, created_at: updated_at, body });
  const L = ledgerEntries([
    pk('posco-hyrex-site-fishing-refusal', '포스코 수소환원제철 부지 한정어업 거절(포항시의회 행감) — 기자 판단 11/12 접음', '접음', '2026-11-12T09:03:00Z'),
    pk('hyundai-factory-delisted-anseong-guess', '[킬] 현대차 안성 공장등록 목록에서 빠짐 — 앞서 킬, 재추천 금지', '접음', '2026-11-13T06:45:00Z'),
    pk('lscable-nlrc-review-20261110', '중노위, LS전선 부당노동행위 재심(2026부노46) 11/10 심문 — 기자 판단 11/12 접음', '접음', '2026-11-12T09:03:00Z'),
    pk('hanwha-itc-1494-with-prejudice', '[예약 중] 한화 ITC 337-1494 재검토 — 11/24 예약 확인 걸려 있음, 그 전 재추천 금지', '보류', '2026-11-13T06:45:00Z'),
    pk('kia-georgia-osha-fatcat-0901', '[답변 대기] 기아 조지아 OSHA Fat/Cat 점검(9/1 개시) — 기자 문의 중, 답 오기 전 재추천 금지', '보류', '2026-11-13T06:45:00Z',
      '원문 https://www.osha.gov/ords/imis/establishment.inspection_detail?id=349146811 확인'),
    pk('uk-tra-plate-ad0071-provisional-rejected', '[킬] 영국 한국산 후판 반덤핑(AD0071) — 기자 판단: 판 작고 계기 없음', '접음', '2026-11-13T07:39:00Z'),
    pk('posco-hr-cvd-cit-2023ar', '[단독 작성] 포스코, 美 열연 상계관세(2023년분 3.68%) CIT 제소(11/2 현지) — 11/9 18:35 기준 미보도', '발제함', '2026-11-09T09:35:00Z'),
    pk('hmgma-sep-ioniq-shipments-drop', '현대차 메타플랜트(HMGMA) 9월 판매 1,121대 — 직전 3개월 평균의 30%', '미발제·확인 필요', '2026-11-09T12:30:00Z', `본문\n${LINK_LINE} sales:hmgma:202609`),
    pk('alert-20261112', '단독 후보 즉시 알림 11-12 · 누적 3건', '미발제·확인 필요', '2026-11-12T09:45:00Z', '알림 전문\n보낸 id: clik:AAA, execm:BBB'),
    pk('afternoon-20261112', '오후 출입처 체크 11-12', '미발제·확인 필요', '2026-11-12T05:25:00Z', '본 접수번호: 2026…'),
  ], []);
  assert.deepEqual(L.entries.map((e) => e.state), ['접음', '접음', '접음', '보류', '보류', '접음', '발제함', '앞서 추천']);   // 자동 기록(오후 체크·알림)은 장부 줄이 아니다
  assert.deepEqual([...L.alerted], [['clik:AAA', '11-12'], ['execm:BBB', '11-12']]);
  const of = (x) => { const r = matchHandled(x, L); return r?.entry ? `${r.entry.state}:${r.entry.key}` : r?.similar ? `비슷:${r.similar.key}` : null; };
  const fishing = { id: 'clik:1', watch: '지방의회 회의록', kind: '지방의회 회의록', company: '포스코', date: '2026-11-12T00:10:00Z',
    fact: '경상북도 포항시의회 경제산업위원회행정사무감사(20261020) 회의록 · 포스코 대목 「어업인들이 수소환원제철소 예정 부지 인근 해역에 한정어업 허가 신청을 했거든요. 그런데 포스코가 이를 받아들이지 않는」' };
  assert.equal(of(fishing), '접음:posco-hyrex-site-fishing-refusal');
  // 같은 날 같은 의회의 다른 발언(악취 민원 — 수소환원제철소는 지나가는 말)은 다른 건
  assert.equal(of({ ...fishing, id: 'clik:2', fact: '포항시의회 자치행정위원회행정사무감사 회의록 · 포스코 대목 「포스코에서도 수소환원제철소를 내년도에 건립할 예정이 있습니다마는 협화라고하는 비료공장이 있어요 악취가」' }), null);
  const gone = { id: 'fac:415502024161684:gone:2026-11-12', watch: '공장등록·관보', kind: '공장 목록에서 빠짐', company: '현대차', date: '2026-11-11T23:10:00Z',
    fact: '목록에서 빠짐: 현대자동차(주) ·  — 이번 조회 목록에 없음(폐업·이전·이름 변경 가능, 확인 필요) · 이 회사 조회 공장 22→21곳' };
  assert.equal(of(gone), '접음:hyundai-factory-delisted-anseong-guess');
  // 처리한 뒤(하루 넘게) 새로 잡힌 같은 종류 항목은 숨기지 않고 이력만 알린다 — 다른 공장일 수 있다
  assert.equal(of({ ...gone, id: 'fac:9:gone:2026-12-01', date: '2026-12-01T23:10:00Z' }), '비슷:hyundai-factory-delisted-anseong-guess');
  assert.equal(of({ id: 'fac:10:new', watch: '공장등록·관보', kind: '공장 새 등록', company: '현대차', date: '2026-11-10', fact: '공장 등록 현대자동차(주) 울산 · 주생산품 전기차 배터리팩' }), null);
  // 사건 번호·문서 번호
  assert.equal(of({ id: 'labor:00:2026부노46:2026-11-10', watch: '노동위 회의(조정·심판)', kind: '노동위 심판 회의', company: 'LS전선', date: '2026-11-04T01:28:00Z',
    fact: '중앙노동위원회 심판회의 2026-11-10 13:30 · 사건 2026부노46 「엘에스전선 주식회사 부당노동행위 구제 재심신청」' }), '접음:lscable-nlrc-review-20261110');
  const edis = { id: 'edis:1', watch: '무역구제', kind: '미국 ITC 337(특허) 문서', company: '한화솔루션', date: '2026-11-01', fact: 'EDIS 337-TA-1494 Petition for Review (Hanwha Solutions)' };
  assert.equal(of(edis), '보류:hanwha-itc-1494-with-prejudice');
  assert.equal(of({ ...edis, id: 'edis:2', date: '2026-11-24', fact: 'EDIS 337-TA-1494 Commission Determination' }), '비슷:hanwha-itc-1494-with-prejudice');   // 예약해 둔 결정이 실제로 나오면 새 항목
  assert.equal(of({ id: 'trade:uk:1', watch: '무역구제', kind: '해외 조사 uk', company: '', date: '2026-11-10', fact: '영국 TRA AD0071 Hot-rolled plate from Korea — provisional' }), '접음:uk-tra-plate-ad0071-provisional-rejected');
  // 원문 주소, 영문 원문의 한글 지명(조지아 ↔ GEORGIA)
  const osha = { id: 'osha:insp:349146811', watch: '미국 OSHA 점검·위반', kind: '미국 OSHA 점검 개시', company: '기아', date: '2026-10-30', fact: 'KIA GEORGIA, INC. (WEST POINT, GA) 사망·중대사고(M) 점검 개시 2026-09-01' };
  assert.equal(matchHandled({ ...osha, url: 'https://www.osha.gov/ords/imis/establishment.inspection_detail?id=349146811' }, L).how, '원문 주소');
  assert.match(matchHandled(osha, L).how, /^낱말\(조지아·OSHA/);
  // 기자가 쓴 단독(열연 상계관세 CIT 제소)과 같은 회사의 다른 사건(후판 상계관세 판결 고시)은 가른다 — 흔한 낱말 둘로는 안 잇는다
  assert.equal(of({ id: 'cl:1', watch: '미국 소송·ITC', kind: '국제무역법원', company: '포스코', date: '2026-11-03', fact: 'POSCO v. United States — 국제무역법원(CIT) 접수 · 열연 상계관세 연례재심' }), '발제함:posco-hr-cvd-cit-2023ar');
  assert.equal(of({ id: 'fr:1', watch: '무역구제', kind: '미국 관보', company: '포스코', date: '2026-11-09T07:17:00Z',
    fact: 'Certain Carbon and Alloy Steel Cut-to-Length Plate From the Republic of Korea: Notice of Court Decision Not in Harmony — 후판 상계관세 CIT 판결' }), null);
  assert.equal(of({ id: 'cl:75108202', watch: '미국 소송·ITC', kind: '분류 없음', company: '기아', date: '2026-11-12', fact: 'District Court, S.D. California 「Mora v. Kia America, Inc.」 접수' }), null);
  // 패키지에 적어 둔 레이더 id(package_save item_ids) — 앞서 추천(미발제)도 이어진다
  assert.equal(of({ id: 'sales:hmgma:202609', watch: '월간 통계(물가·생산·수입차·완성차 판매)', kind: '판매 급감', company: '현대차', date: '2026-11-03', fact: '9월 1,121대' }), '앞서 추천:hmgma-sep-ioniq-shipments-drop');
  // 부호: 연도·날짜·금액·차종 이름은 부호가 아니다
  assert.deepEqual([...codesOf('한화 ITC 337-1494 재검토 2026년 11/24 4882억원 EV6 GV70 AD0071 kia georgia osha 0901 2026부노46 26V539000')].sort(), ['1494', '2026부노46', '26V539000', 'AD0071']);
  assert.deepEqual([...companiesIn('KIA GEORGIA, INC. · 엘지화학 · Hanwha Qcells')].sort(), ['LG화학', '기아', '한화솔루션']);

  // 구역 도구 글에 붙이는 표시: 처리한 건은 〔이미 처리〕, 처리한 뒤 날짜의 줄은 〔처리 이력 있음〕
  const txt = ['[미국 OSHA 점검·위반 · 출입처 미국 법인·공장] 2건', '규칙: 점검은 위반 확정이 아니다', '- 개시 2026-09-01 · 기아 · 사망·중대사고(M) 점검 · 진행 중',
    '   사업장: KIA GEORGIA, INC. (WEST POINT, GA) · 종업원 3000명', '   원문: https://www.osha.gov/ords/imis/establishment.inspection_detail?id=349146811',
    '- 개시 2026-10-01 · 현대차 · 민원 점검', '   사업장: HYUNDAI MOTOR MANUFACTURING ALABAMA', '- 2026-11-24 · 한화솔루션 · EDIS 337-TA-1494 Commission Determination'].join('\n');
  const a = annotateHandled(txt, L);
  assert.equal(a.marked, 2);
  assert.match(a.text, /- 개시 2026-09-01 · 기아 · 사망·중대사고\(M\) 점검 · 진행 중 〔이미 처리: \[보류·답변 대기\] 기아 조지아 OSHA Fat\/Cat 점검\(9\/1 개시\) · 11-13 — 단독 추천에서 뺀다\(새 사실이 붙었을 때만 다시\)〕\n/);
  assert.match(a.text, /- 개시 2026-10-01 · 현대차 · 민원 점검\n/);
  assert.match(a.text, /Commission Determination 〔처리 이력 있음: \[보류·예약 중\] 한화 ITC 337-1494 재검토 · 11-13 — 그 뒤 새 항목일 수 있음\(새 사실인지 확인\)〕$/);
  assert.equal(annotateHandled(txt, { entries: [] }).marked, 0);

  // 11-13 운영에서 본 잘못 붙은 표시와 빠진 표시
  // ① 영문 낱말은 낱말 경계로만: 'Fat/Cat'의 Cat이 'Application'에 걸려 기아 조지아 대기 허가 기준선 줄에 OSHA 건이 붙었다
  const air = ['- [기준선] 조지아 · 기아 · KIA Georgia, Inc. · 대기 허가 발급(PSD/NSR) · 허가 3711-285-0084-P-01-0(시설 285-00084) · 발급 2007-07-27',
    '   원문: https://air.gaepd.org/Permits/View/PI-17363', '   문서: Preliminary Determination https://air.gaepd.org/Permits/View/PP-17363 · Application Summary https://air.gaepd.org/Permits/View/PA-17363'].join('\n');
  assert.equal(annotateHandled(air, L).marked, 0);
  assert.equal(of({ id: 'gaair:1', watch: '미국 주 환경 허가·공고', kind: '대기 허가 발급', company: '기아', date: '2026-11-01', fact: '조지아 · KIA Georgia, Inc. · 대기 허가 발급(PSD/NSR) · Application Summary' }), null);
  // ② EDIS 접수일은 2026/11/24 꼴 — 예약해 둔 결정이 나온 날의 줄은 〔이미 처리〕가 아니라 〔처리 이력 있음〕
  const ed = annotateHandled(['- B · 접수 2026/10/29 16:14 · 337-1494 Notice · Commission Determination to Extend the Due Date', '   제출 USITC',
    '- A · 접수 2026/11/24 10:02 · 337-1494 Notice · Commission Determination to Review'].join('\n'), L).text.split('\n');
  assert.match(ed[0], /Due Date 〔이미 처리: \[보류·예약 중\] 한화 ITC 337-1494 재검토/);
  assert.match(ed[2], /to Review 〔처리 이력 있음: \[보류·예약 중\] 한화 ITC 337-1494 재검토 · 11-13 — 그 뒤 새 항목일 수 있음/);
  // ③ 묶음 머리줄 아래 여러 사건: 표시는 처리한 그 사건 줄에만(머리줄에 붙으면 묶음 전체가 처리된 것으로 읽힌다)
  const grp = annotateHandled(['- 출입처 사건 · 최근 30일 2건', '  A · 2026-11-10 13:30 · LS전선 · 중앙노동위원회 심판회의 · 사건 2026부노46 「엘에스전선 주식회사 부당노동행위 구제 재심신청」',
    '     원문: https://www.nlrc.go.kr/a', '  B · 2026-11-19 16:00 · 한국GM · 인천지방노동위원회 심판회의 · 사건 2026부해920 「한국지엠 주식회사 부당해고 구제신청」', '     원문: https://www.nlrc.go.kr/b',
    '   검증 상태: 노동위원회 공개 회의 일정(자동). 사건명은 신청 주장'].join('\n'), L);
  assert.equal(grp.marked, 1);
  assert.deepEqual(grp.text.split('\n').map((l) => l.includes('〔이미 처리')), [false, true, false, false, false, false]);
  // 날짜로 시작하는 항목 줄(앞으로 열릴 회의 3건 중 처리한 1건) — 11-13 운영에서 머리줄에 붙어 기아·한국GM 회의까지 처리된 것처럼 보였다
  const up = annotateHandled(['- 앞으로 열릴 출입처 회의(오늘 포함, 달력·첫 화면) 3건 — 미뤄지거나 취소될 수 있음', '  2026-11-10 13:30 · A · LS전선 · 중앙노동위원회 심판회의 · 사건 2026부노46 「엘에스전선 주식회사 부당노동행위 구제 재심신청」',
    '  2026-11-16 13:30 · B · 기아 · 강원지방노동위원회 심판회의 · 사건 2026부해346 「기아 주식회사 부당해고 구제신청 사건」', '  2026-11-19 16:00 · B · 한국GM · 인천지방노동위원회 심판회의 · 사건 2026부해920 「한국지엠 주식회사 부당해고 구제신청」'].join('\n'), L);
  assert.deepEqual(up.text.split('\n').map((l) => l.includes('〔이미 처리')), [false, true, false, false]);
  // 낱말만 맞은 오래된 기준선 줄에는 붙이지 않는다(11-13 운영: 한화큐셀 조지아 대기허가 신청 보류 건이 2018~2024년 발급 허가 10줄에 붙음). 신청 번호가 같은 줄은 붙인다.
  const LQ = ledgerEntries([pk('hanwha-qcells-georgia-air-permit', '한화큐셀 조지아 카터스빌 대기허가 신청(30376, RTO·비상발전기 5대) + 달튼 Title V 재분류 — 설비 용도 회사 확인 전 보류', '보류', '2026-11-03T08:22:00Z')], []);
  const qc = annotateHandled(['- [기준선] 조지아 · 한화솔루션 · Hanwha Q Cells USA, Inc. · 대기 허가 발급(SIP) · 허가 3674-313-0165-S-01-0(시설 313-00165) · 발급 2018-09-07', '   원문: https://air.gaepd.org/Permits/View/OP-26648',
    '- [기준선] 조지아 · 한화솔루션 · Hanwha Q Cells USA, Inc. · 대기 허가 발급(SIP) · 허가 3674-313-0165-E-02-0(시설 313-00165) · 발급 2026-06-01',
    '- 조지아 · 한화솔루션 · Hanwha Q Cells Georgia, Inc. · 대기 허가 발급(SIP) · 허가 3674-015-0150-S-03-0 · 발급 2026-10-20',
    '- [기준선] 조지아 · 한화솔루션 · Hanwha Q Cells Georgia, Inc.(Bartow County) · Permit Application · 신청 30376 · 의견 마감 2026-11-06'].join('\n'), LQ).text.split('\n');
  assert.deepEqual(qc.map((l) => (l.includes('〔이미 처리') ? '처리' : l.includes('〔처리 이력') ? '이력' : '-')), ['-', '-', '-', '처리', '이력']);
  assert.deepEqual([...codesOf('대기허가 신청(30376, RTO·비상발전기 5대) 판매 1,121대 · 12,345대 · 세율 3.68% · 공고 제2026-2760호')].sort(), ['2760', '30376']);
  // 패키지에 원문 주소가 적혀 있으면 줄에 적힌 날짜(의견 마감일)가 뒤여도 같은 문서다 → 〔이미 처리〕
  const LQ2 = ledgerEntries([pk('hanwha-qcells-georgia-air-permit', '한화큐셀 조지아 카터스빌 대기허가 신청 — 보류', '보류', '2026-11-03T08:22:00Z', '원문 https://epd.georgia.gov/document/document/pa1026-1/download')], []);
  assert.match(annotateHandled('- [기준선] 조지아 · 한화솔루션 · Hanwha Q Cells Georgia, Inc. · Permit Application · 의견 마감 2026-11-06\n   원문: https://epd.georgia.gov/document/document/pa1026-1/download (pa1026-1)', LQ2).text, /의견 마감 2026-11-06 〔이미 처리: \[보류\] 한화큐셀 조지아 카터스빌 대기허가 신청/);
  // ④ 흔한 말뿐인 제목(굴뚝 '가동중지')도 같은 회사 + 지역·품목 낱말 둘이면 잇는다 — 처리한 뒤 새로 잡힌 줄은 이력만
  const L2 = ledgerEntries([pk('kgsteel-incheon-dangjin-stacks', "KG스틸 인천·당진 굴뚝 동시 '가동중지' — 당진은 회사 '설비 합리화 투자 공사' 답변, 인천 미확인", '보류', '2026-11-04T01:23:00Z'),
    pk('uk-tra-pvc-korea-pms-1113', '[보강 메모] 영국 S-PVC(AD0092) PMS — 11/9 정부·수출자 PMS 질의서(회신 11/24)', '접음', '2026-11-13T07:16:00Z')], []);
  const stack = { id: 'stk:down:KG스틸:케이지스틸(주)당진공장:2026-11-13', watch: '굴뚝 측정(공장 가동 신호)', kind: '사업장 가동 중단 신호', company: 'KG스틸', date: '2026-11-12T15:20:00Z',
    fact: "케이지스틸(주) 당진공장: 평소 움직이던 배출구 3개 중 2개가 3번 연속 평소의 10% 아래 — 6번(상태 '가동중지')" };
  assert.equal(matchHandled(stack, L2).similar?.key, 'kgsteel-incheon-dangjin-stacks');
  assert.equal(matchHandled({ ...stack, date: '2026-11-03T15:20:00Z' }, L2).entry?.key, 'kgsteel-incheon-dangjin-stacks');
  assert.equal(matchHandled({ ...stack, company: '현대제철', fact: "현대제철㈜ 당진제철소 굴뚝: 상태 '가동중지'" }, L2), null);   // 다른 회사
  assert.equal(matchHandled({ ...stack, fact: 'KG스틸 당진공장 건축허가 신축 1,200㎡' , watch: '공장 부지 건축허가', kind: '새 허가' }, L2), null);   // 같은 회사 다른 일
  assert.match(annotateHandled('- 2026-11-10T07:40 · 영국 · 영국 무역구제청(TRA) 조사 목록\n   잡힌 사실: No. AD0092 Case Suspension Polyvinyl Chloride', L2).text, /〔이미 처리: \[접음·보강 메모\] 영국 S-PVC\(AD0092\) PMS · 11-13/);
});

test('처리 장부 CPU(11-13 운영 오류 1102): 회사 찾기는 정규식 두 번, 장부 줄 정규식은 한 번만 만들고, 저장소가 연결만 뽑아 보낸다', async () => {
  // 11-13 운영: #795~#797 배포 뒤 scoop_desk·radar_today(168시간)·us_litigation이 'Error 1102: Worker exceeded resource limits'(HTTP 503)로 끊겼다.
  // 항목 하나를 장부 줄마다 다시 손보고 별칭 100여 개를 하나씩(영문은 그때마다 정규식을 새로 만들어) 찾던 탓 — 항목 900개에 CPU 0.4초.
  // ① 빠른 회사 찾기는 느린 기준 구현과 답이 같다(긴 별칭 안의 짧은 별칭 포함)
  for (const t of ['KIA GEORGIA, INC. · 엘지화학 · Hanwha Qcells', 'Hyundai Steel Company v. United States', '포스코홀딩스와 포스코퓨처엠', 'HD Hyundai Electric America', 'LS Cable & System Ltd.',
    '현대자동차(주) 울산공장 · 현대모비스', 'S-OIL 온산 · GS칼텍스 여수', '한국지엠 주식회사 부당해고', 'Kumho Tire Georgia', '케이지스틸(주) 당진공장', 'Korea Zinc · 고려아연㈜온산제련소', 'OCI홀딩스 · DL케미칼',
    'skia graphics · mobisys · posconnect', '태광산업㈜ 대표이사', 'Hyundai Mobis, Hyundai Motor America, Genesis', '', '출입처 이름 없는 글 Thibodeaux v. Example']) {
    assert.deepEqual([...companiesIn(t)].sort(), [...companiesInSlow(t)].sort(), t);
  }
  // ② 저장소가 본문에서 연결만 뽑는다 — Worker는 패키지 본문을 받지 않는다
  assert.deepEqual(packageLinks('kia-georgia-osha', `문의 중\nid osha:insp:349146811 확인\n원문 https://www.osha.gov/ords/imis/establishment.inspection_detail?id=349146811.\n${LINK_LINE} sales:hmgma:202609, https://example.com/a/b/c/d/e/f`),
    { ids: ['sales:hmgma:202609', 'https://example.com/a/b/c/d/e/f', 'osha:insp:349146811'], urls: ['https://www.osha.gov/ords/imis/establishment.inspection_detail?id=349146811', 'https://example.com/a/b/c/d/e/f'], sent: [] });
  assert.deepEqual(packageLinks('alert-20261112', '알림 전문\n보낸 id: clik:AAA, execm:BBB'), { ids: [], urls: [], sent: ['clik:AAA', 'execm:BBB'] });
  const opts = PRIVATE();
  await call('package_save', { name: 'kia-georgia-osha', title: '[답변 대기] 기아 조지아 OSHA 점검', state: '보류', body: '본문 '.repeat(500), item_ids: ['osha:insp:349146811'] }, opts);
  const stub = opts.env.STORE.get('reporter');
  const digest = await (await stub.fetch('https://store.internal/op', { method: 'POST', body: JSON.stringify({ action: 'packages.digest', args: {}, now: NOW.toISOString() }) })).json();
  assert.deepEqual(Object.keys(digest.rows[0]).sort(), ['created_at', 'ids', 'name', 'sent', 'state', 'title', 'updated_at', 'urls']);   // body 없음
  assert.deepEqual(digest.rows[0].ids, ['osha:insp:349146811']);
  // ③ 항목 2,000개 × 장부 30줄: 예전 구현은 이 기계에서 1초를 넘겼다. 넉넉한 상한으로 되돌아가는 것만 막는다.
  const pk = (i) => ({ name: `pkg-${i}`, title: [`[킬] 영국 한국산 후판 반덤핑(AD00${70 + i})`, `[답변 대기] 기아 조지아 OSHA Fat/Cat 점검 ${i}차`, `포스코 수소환원제철 부지 한정어업 거절 ${i}`, `현대차 안성 공장등록 목록에서 빠짐 ${i}`,
    `KG스틸 인천·당진 굴뚝 동시 '가동중지' ${i}`, `한화 ITC 337-${1490 + i} 재검토`][i % 6], state: '접음', updated_at: '2026-11-13T06:00:00Z', body: '' });
  const big = ledgerEntries(Array.from({ length: 30 }, (_, i) => pk(i)), []);
  const facts = ['케이지스틸(주) 당진공장: 평소 움직이던 배출구 3개 중 2개가 3번 연속 평소의 10% 아래', 'EDGAR X-Energy, Inc. (XE): 8-K EX-99.1 Doosan Enerbility', '경상북도 포항시의회 본회의 회의록 · 포스코 대목 「위원회안으로 채택」',
    'District Court, S.D. California 「Mora v. Kia America, Inc.」 접수', '진흥산업 주식회사 파산 선고 (울산지방법원 2026하합 104)'];
  const cos = ['KG스틸', '두산에너빌리티', '포스코', '기아', '진흥산업 주식회사'];
  const many = Array.from({ length: 2000 }, (_, i) => ({ id: `x:n${i}`, watch: '굴뚝 측정(공장 가동 신호)', kind: '종류', company: cos[i % 5], date: '2026-11-10T00:00:00Z', fact: `${facts[i % 5]} n${i}`, url: `https://example.com/item/n${i}` }));
  const t0 = performance.now();
  let hits = 0;
  for (const x of many) if (matchHandled(x, big)) hits += 1;
  const ms = performance.now() - t0;
  assert.equal(hits, 0);
  assert.ok(ms < 400, `항목 2,000개 대조 ${Math.round(ms)}ms — 상한 400ms`);
  // 숫자뿐인 부호는 수량에 걸리지 않는다(337-1494 ↔ '종업원 1494명'), 사건 번호 꼴에는 걸린다
  const itc = ledgerEntries([{ name: 'hanwha-itc-1494-with-prejudice', title: '[예약 중] 한화 ITC 337-1494 재검토 — 11/24 예약', state: '보류', updated_at: '2026-11-13T06:45:00Z', body: '' }], []);
  const hw = (fact) => matchHandled({ id: `t:${fact.length}`, watch: '사업장 인력(국민연금)', kind: '가입자', company: '한화솔루션', date: '2026-11-01', fact }, itc)?.entry?.key ?? null;
  assert.equal(hw('한화솔루션(주) 여수공장 · 가입자 1494명 (지난달 +12)'), null);
  assert.equal(hw('한화솔루션 울산공장 · 연면적 1494㎡ 증축'), null);
  assert.equal(hw('EDIS 337-TA-1494 Commission Determination (Hanwha Solutions)'), 'hanwha-itc-1494-with-prejudice');
  assert.equal(hw('Inv. No. 337-1494 Notice'), 'hanwha-itc-1494-with-prejudice');
  // 같은 요청 안에서 같은 항목을 다시 물으면 적어 둔 답을 쓴다(새 항목 목록 + 14일 겹친 신호)
  assert.equal(big.memo.size, 2000);
});

test('단독 데스크(11-13): 처리한 것·이미 보도된 것·여러 번 킬한 유형을 걷어내고 실적 있는 유형부터, 후보가 없으면 없다고 한다', async () => {
  const opts = PRIVATE();
  const env = opts.env;
  const recent = new Date(NOW.getTime() - 2 * 3600000).toISOString();
  const post = (feed, doc) => worker.fetch(new Request(ORIGIN + `/ingest/${feed}`, { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: JSON.stringify(doc) }), env, {});
  const fishing = '경상북도 포항시의회 경제산업위원회행정사무감사(20261020) 회의록 · 포스코 대목 「어업인들이 수소환원제철소 예정 부지 인근 해역에 한정어업 허가 신청을 했거든요. 그런데 포스코가 이를 받아들이지 않는」';
  const odor = '경상북도 포항시의회 자치행정위원회행정사무감사(20261020) 회의록 · 포스코 대목 「포스코에서도 수소환원제철소를 내년도에 건립할 예정이 있습니다마는 협화라고하는 비료공장 악취가」';
  assert.equal((await post('council-minutes', { schema: 'council_minutes/v1', generatedAt: recent, status: 'complete', items: [], checks: [{ source: '국회도서관 지방의회 회의록(CLIK)', status: 'ok' }],
    events: [{ id: 'clik:FISH', tier: 'A', kind: '지방의회 회의록', company: '포스코', council: '포항시의회', detectedAt: recent, text: fishing },
      { id: 'clik:ODOR', tier: 'A', kind: '지방의회 회의록', company: '포스코', council: '포항시의회', detectedAt: recent, text: odor }] })).status, 200);
  await post('kr-official', { schema: 'kr_official/v1', generatedAt: recent, checks: [{ source: '공장등록 현대차', status: 'ok' }], factories: [], gazette: [],
    events: [{ id: 'fac:415:gone', kind: '목록에서 빠짐', company: '현대차', factoryId: 'fac:415', name: '현대자동차(주)', text: '현대자동차(주) ·  — 이번 조회 목록에 없음(폐업·이전·이름 변경 가능, 확인 필요)', detectedAt: recent }] });
  const eha = { id: 'ktc:case:00000873', pageId: 'ktc', ktcKind: 'case', country: 'KR', tier: 'B', beat: true, product: '아크릴산 2-에틸헥실', label: '무역위 새 조사 · 구제23-2026-10호',
    text: '중국, 미국, 말레이시아산 아크릴산 2-에틸헥실 — 품목 아크릴산 2-에틸헥실, 개시 2026-10-25', url: 'https://www.ktc.go.kr/viewInvest.do?menuId=11&masterId=00000873&invstg_type_code=10100001', detectedAt: recent };
  const ahead = new Date(NOW.getTime() + 9 * 3600000 + 10 * 86400000).toISOString().slice(0, 10);
  const TRADE_DOC = { schema: 'trade_remedy/v1', generatedAt: recent, quotas: [], notices: [], events: [eha], checks: [{ source: '무역위원회', status: 'ok' }],
    ktc: { checkedAt: recent, listComplete: true, meetings: [], news: [], cases: [
      { id: '00000867', no: '구제 23-2026-4호', title: '중국산 폴리염화비닐 서스펜션 수지의 덤핑사실 및 국내산업피해 유무', product: '폴리염화비닐 서스펜션 수지', opened: '2026-07-08', kind: '반덤핑조사', review: '원심',
        country: '중국', beat: true, timeline: [['조사개시', '2026-07-08'], ['예비조사', ahead]], pending: ['공청회', '최종판정'], url: 'https://www.ktc.go.kr/v?867',
        applicant: { names: ['한화솔루션'], beat: ['한화솔루션'], newsId: '00002147', title: '무역위, 중국산 부틸 아크릴레이트에 덤핑방지관세 부과 건의' } },
      { id: '00000868', no: '구제23-2026-5호', title: '중국산 석도강판의 덤핑사실 및 국내산업피해 유무', product: '석도강판', opened: '2026-07-10', kind: '반덤핑조사', review: '원심', country: '중국', beat: true,
        timeline: [['조사개시', '2026-07-10'], ['예비조사', ahead]], pending: [], url: 'https://www.ktc.go.kr/v?868', applicant: { names: ['티씨씨스틸'], beat: [], newsId: '00002147', title: 't' } }] }  };
  await post('trade-remedy', TRADE_DOC);
  const stk = (i) => ({ id: `stk:down:KG스틸:당진:${i}`, kind: '사업장 가동 중단 신호', tier: 'B', company: 'KG스틸', site: '케이지스틸(주) 당진공장', text: `케이지스틸(주) 당진공장: 평소 움직이던 배출구 3개 중 2개 (${i})`, detectedAt: recent });
  await post('kr-stacks', { schema: 'kr_stacks/v1', generatedAt: recent, status: 'complete', baselineSince: '2026-10-01T00:00:00+09:00', checks: [{ source: '굴뚝 자동측정(CleanSYS)', status: 'ok' }], sites: [], events: [stk(1), stk(2)] });

  // 아직 아무것도 처리하지 않았을 때: 실적 있는 유형(무역위 새 조사)이 맨 위, 굴뚝·의회 발언·공장 목록 변동은 약한 유형으로 접힌다
  const d0 = (await call('scoop_desk', {}, opts)).text;
  assert.match(d0, /^단독 데스크 · 10-26 09:00 KST · 최근 7일 · 레이더 항목 6건 → 걷어낸 뒤 후보 1건\n/);
  assert.match(d0, /\[1\. 새 후보 — 실적 있는 유형부터\] 1건\n〈실적 있는 유형〉\n- A · [^\n]* · 국내 무역위\(출입처 신청·판정 예고\) · 아크릴산 2-에틸헥실\n   무역위 새 조사 · 구제23-2026-10호: 중국, 미국, 말레이시아산 아크릴산 2-에틸헥실/);
  assert.match(d0, /   〔이 유형 실적〕 11-06 \[단독\] LG화학 2-EHA 반덤핑 신청/);
  assert.match(d0, /자세히: trade_remedies · id ktc:case:00000873\n/);
  assert.match(d0, new RegExp(`\\[2\\. 다가오는 일정 — 출입처가 신청인인 무역위 사건, 앞으로 21일\\] 1건\\n- ${ahead} 예비조사 · 구제 23-2026-4호 중국산 폴리염화비닐 서스펜션 수지[^\\n]* · 신청인 출입처 한화솔루션 · 원문: https://www.ktc.go.kr/v\\?867`));
  assert.doesNotMatch(d0, /석도강판의 덤핑사실/);   // 신청인이 출입처가 아닌 사건은 일정에 안 올린다
  assert.match(d0, /- 이미 처리\(다시 내지 않음\): 처리 장부 0건 · 판정 0건\n- 이미 보도\(자동 대조 '관련 보도 있음'\): 0건\n- 약한 유형: 5건 — (?=[^\n]*굴뚝 측정 2)(?=[^\n]*지방의회 회의록 발언 2)(?=[^\n]*공장등록 고용·목록 변동 1)[^\n]* \(include_weak=true로 펼침\)/);
  assert.match(d0, /\[5\. 기자가 이미 처리한 건 — 최근 30일 0건\]/);
  assert.doesNotMatch(d0, /한정어업 허가 신청/);   // 약한 유형은 펼치기 전엔 글이 안 나온다
  // 해외 목록 줄(이름 없이 한국산 줄만)은 실적 있는 유형이 아니다 — 같은 조사의 세 줄은 한 줄만. 출입처 이름이 적힌 문서는 실적 있는 유형.
  const dg = (n, text, url) => ({ id: `dgtr:${n}`, pageId: 'dgtr', country: '인도', label: '인도 DGTR 반덤핑 조사', text, url, detectedAt: recent });
  const tdi = 'https://www.dgtr.gov.in/en/anti-dumping-cases/anti-dumping-investigation-concerning-imports-toluene-diisocyanate-tdi';
  await post('trade-remedy', { schema: 'trade_remedy/v1', generatedAt: recent, quotas: [], notices: [], checks: [{ source: '인도 DGTR 반덤핑 조사', status: 'ok' }],
    events: [eha, dg(1, 'Anti-dumping investigation concerning imports of Toluene DiIsocyanate-(TDI) originating in or exported from China PR, Japan and Korea RP', tdi),
      dg(2, 'Ongoing Investigation Anti-dumping investigation concerning imports of Toluene DiIsocyanate-(TDI) originating in or exported from China PR, Japan and Korea RP', tdi),
      { id: 'tra:1', pageId: 'tra', country: '영국', label: '영국 무역구제청(TRA) 공개 기록', text: 'AD0092 Submission by LG Chem Ltd and Hanwha Solutions — particular market situation', url: 'https://www.trade-remedies.service.gov.uk/public/case/AD0092/submission/1/', detectedAt: recent }] });
  const df = (await call('scoop_desk', {}, opts)).text;
  assert.match(df, /후보 3건\n/);
  assert.match(df, /\[1\. 새 후보 — 실적 있는 유형부터\] 3건 \(같은 날 같은 종류·같은 원문 1건 접음\)\n〈실적 있는 유형〉\n/);
  assert.match(df, /- B · [^\n]* · 해외 무역구제·규제 문서\(출입처·한국 정부 이름\) · 영국\n   영국 무역구제청\(TRA\) 공개 기록: AD0092 Submission by LG Chem Ltd and Hanwha Solutions[^\n]*\n   〔이 유형 실적〕 11-10 \[단독\] 英 S-PVC/);
  assert.match(df, /〈그 밖 — 원문·회사 확인으로 가를 것〉\n- B · [^\n]* · 해외 무역구제 목록 새 줄\(한국산\) · 인도\n   인도 DGTR 반덤핑 조사: Anti-dumping investigation concerning imports of Toluene[^\n]*\n   〔볼 것〕 목록에 한국산 줄이 생겼다는 것뿐/);
  assert.equal((df.match(/Toluene DiIsocyanate/g) ?? []).length, 1);
  // 후보는 있는데 실적 있는 유형이 없는 날은 그렇다고 먼저 말한다
  await post('trade-remedy', { schema: 'trade_remedy/v1', generatedAt: recent, quotas: [], notices: [], checks: [{ source: '인도 DGTR 반덤핑 조사', status: 'ok' }], events: [dg(1, 'Anti-dumping investigation concerning imports of Toluene DiIsocyanate-(TDI) from Korea RP', tdi)] });
  assert.match((await call('scoop_desk', {}, opts)).text, /\[1\. 새 후보 — 실적 있는 유형부터\] 1건\n〈실적 있는 유형〉 없음 — 기자가 단독을 쓴 유형[^\n]*\n〈그 밖 — 원문·회사 확인으로 가를 것〉\n- B · /);
  // 원래 자료로 되돌린다(아래 단언은 무역위 사건·일정이 있는 자료 기준)
  await post('trade-remedy', TRADE_DOC);
  // 유형 가르기: 입법예고·법제처 확정 발령은 공개 공고라 약한 유형, 새 공장 등록·환경영향평가는 그대로 보통
  assert.equal(deskType({ watch: '공장등록·관보', kind: '관보 입법예고', tier: 'B' }).key, 'gazette');
  assert.equal(deskType({ watch: '공장등록·관보', kind: '법제처 행정규칙', tier: 'B' }).strength, 'weak');
  assert.equal(deskType({ watch: '공장등록·관보', kind: '공장 새 등록', tier: 'A' }).strength, 'normal');
  assert.equal(deskType({ watch: '공장등록·관보', kind: '환경영향평가 초안', tier: 'A' }).strength, 'normal');
  assert.equal(deskType({ watch: '무역구제', kind: '해외 조사 dgtr', tier: 'B', company: '인도', fact: '인도 DGTR 반덤핑 조사: TDI from Korea RP' }).key, 'foreignlist');
  assert.equal(deskType({ watch: '무역구제', kind: '대한 수입규제', tier: 'B', company: '미국', fact: '미국 반덤핑 예비판정 — POSCO 3.2%' }).key, 'foreigndoc');
  // 기자가 이미 쓴 기사와 자동 대조로 이어진 항목은 후보에서 빼고 4구역에 기사 제목과 함께 적는다(패키지를 안 남긴 기사)
  assert.equal((await post('my-articles', { schema: 'my_articles/v1', generatedAt: recent, status: 'complete', checks: [{ source: '아이뉴스24 뉴스 사이트맵', status: 'ok' }], articles: [], counts: {},
    itemHits: { 'ktc:case:00000873': { title: '[단독] LG화학, 수입산 점착제 원료 반덤핑 조사 신청', published: recent, url: 'https://www.inews24.com/view/1', verified: true } } })).status, 200);
  const dm = (await call('scoop_desk', {}, opts)).text;
  assert.match(dm, /후보 0건\n/);
  assert.match(dm, /- 기자가 이미 쓴 기사\(아이뉴스24 자동 대조\): 1건\n   \d\d-\d\d 「\[단독\] LG화학, 수입산 점착제 원료 반덤핑 조사 신청」 ← 무역구제 · 아크릴산 2-에틸헥실 · id ktc:case:00000873\n/);
  await post('my-articles', { schema: 'my_articles/v1', generatedAt: recent, status: 'complete', checks: [{ source: '아이뉴스24 뉴스 사이트맵', status: 'ok' }], articles: [], counts: {}, itemHits: {} });
  // company로 좁히면 일정도 그 낱말이 든 사건만
  assert.doesNotMatch((await call('scoop_desk', { company: '포스코' }, opts)).text, /다가오는 일정/);
  assert.match((await call('scoop_desk', { company: '한화솔루션' }, opts)).text, /\[2\. 다가오는 일정[^\n]*\] 1건/);
  const dw = (await call('scoop_desk', { include_weak: true }, opts)).text;
  assert.match(dw, /   〈지방의회 회의록 발언〉 접음 1건\(11-12 포스코 한정어업\)[^\n]*\n   · B · 2026-10-25 · 포스코 · [^\n]*id clik:(?:FISH|ODOR)/);
  assert.match(dw, /   〈굴뚝 측정〉 킬 16건/);

  // 기자가 처리: 한정어업 건은 접음(낱말로 이어짐), 공장 목록 빠짐은 킬(레이더 id로), 무역위 새 조사는 회사에 문의해 답변 대기(보류 + item_ids)
  const saved = await call('package_save', { name: 'posco-hyrex-site-fishing-refusal', title: '포스코 수소환원제철 부지 한정어업 거절(포항시의회 행감) — 기자 판단 접음', state: '접음', body: '의원 질의뿐, 판 작음' }, opts);
  assert.match(saved.text, /^새로 저장: \[접음\] posco-hyrex-site-fishing-refusal/);
  const linked = await call('package_save', { name: 'lgchem-2eha-ad-ask', title: '[답변 대기] LG화학 2-EHA 반덤핑 신청 여부 — 홍보팀 문의 중', state: '보류', body: '신청인 확인 질문 보냄', item_ids: ['ktc:case:00000873', ' ', 'ktc:case:00000873'] }, opts);
  assert.match(linked.text, /· 연결한 레이더 항목 1건$/);
  assert.match((await call('scoop_packages', { name: 'lgchem-2eha-ad-ask' }, opts)).text, /신청인 확인 질문 보냄\n연결한 레이더 항목: ktc:case:00000873$/);
  await call('package_save', { name: 'lgchem-2eha-ad-ask', title: '[답변 대기] LG화학 2-EHA 반덤핑 신청 여부 — 홍보팀 문의 중', state: '보류',
    body: '신청인 확인 질문 보냄\n연결한 레이더 항목: ktc:case:00000873', item_ids: ['ktc:case:00000873'] }, opts);
  assert.equal((await call('scoop_packages', { name: 'lgchem-2eha-ad-ask' }, opts)).text.split('연결한 레이더 항목:').length, 2);   // 다시 저장해도 줄이 겹치지 않는다
  await call('candidate_feedback', { item_id: 'fac:415:gone', verdict: '킬', reason: '안성 — 앞서 확인' }, opts);

  const t = (await call('radar_today', {}, opts)).text;
  assert.doesNotMatch(t, /한정어업 허가 신청/);
  assert.doesNotMatch(t, /id ktc:case:00000873/);
  assert.match(t, /id clik:ODOR/);                // 같은 의회의 다른 발언은 그대로
  assert.match(t, /\(처리 장부로 숨김 2건 — 기자가 이미 처리한 취재 패키지와 이어진 항목 · include_judged=true로 보기\)\n(?=[\s\S]*   \[보류·답변 대기\] LG화학 2-EHA 반덤핑 신청 여부 ← 1건\(무역구제, id\))(?=[\s\S]*   \[접음\] 포스코 수소환원제철 부지 한정어업 거절\(포항시의회 행감\) ← 1건\(지방의회 회의록, 낱말\(수소환원제철·한정어업)/);
  assert.match(t, /\(판정한 1건 숨김: 킬 1/);
  const tj = (await call('radar_today', { include_judged: true }, opts)).text;
  assert.match(tj, /id clik:FISH 〔이미 처리: \[접음\] 포스코 수소환원제철 부지 한정어업 거절\(포항시의회 행감\) — 단독 추천에서 뺀다〕/);
  assert.match(tj, /id fac:415:gone 〔판정: 킬〕/);

  // 데스크: 남는 후보가 없으면 없다고 하고, 처리한 건 목록을 준다
  const d1 = (await call('scoop_desk', {}, opts)).text;
  assert.match(d1, /레이더 항목 5건 → 걷어낸 뒤 후보 0건/);
  assert.match(d1, /\[1\. 새 후보 — 실적 있는 유형부터\] 0건\n없음 — 오늘은 걷어내고 남는 후보가 없다\. 약한 유형에서 억지로 올리지 않는다/);
  assert.match(d1, /- 이미 처리\(다시 내지 않음\): 처리 장부 2건 · 판정 1건\(킬 1\)\n(?=[\s\S]*   \[보류·답변 대기\] LG화학 2-EHA 반덤핑 신청 여부 ← 1건\(무역구제\))(?=[\s\S]*   \[접음\] 포스코 수소환원제철 부지 한정어업 거절\(포항시의회 행감\) ← 1건\(지방의회 회의록\))/);
  assert.match(d1, /- 약한 유형: 3건 — /);
  assert.match(d1, /\[5\. 기자가 이미 처리한 건 — 최근 30일 2건\][^\n]*\n(?=[\s\S]*- \[보류·답변 대기\] LG화학 2-EHA 반덤핑 신청 여부 · 10-26)(?=[\s\S]*- \[접음\] 포스코 수소환원제철 부지 한정어업 거절\(포항시의회 행감\) · 10-26)/);

  // 구역 도구: 원문 주소를 적어 둔 건(예약 걸어 둔 PVC 예비판정)의 사건 줄에 표시가 붙고, 다른 사건에는 안 붙는다
  await call('package_save', { name: 'hanwha-pvc-suspension-prelim', title: '[예약 중] 한화솔루션 중국산 PVC 서스펜션 예비판정 — 회의 뒤 확인 예약', state: '보류', body: '예비조사 일정 확인',
    item_ids: ['https://www.ktc.go.kr/v?867'] }, opts);
  const sec = (await call('trade_remedies', { section: 'ktc' }, opts)).text;
  assert.match(sec, /- 구제 23-2026-4호 · 중국산 폴리염화비닐 서스펜션 수지[^\n]* 〔이미 처리: \[보류·예약 중\] 한화솔루션 중국산 PVC 서스펜션 예비판정 · 10-26 — 단독 추천에서 뺀다\(새 사실이 붙었을 때만 다시\)〕\n   원문: https:\/\/www\.ktc\.go\.kr\/v\?867/);
  assert.equal(sec.split('\n').filter((l) => l.startsWith('- ') && l.includes('〔이미 처리:')).length, 1);
  assert.match(sec, /\n처리 장부: 〔이미 처리〕 1건은 기자가 킬·보류\(답변 대기·예약·후배에게 넘김\)·작성 중으로 남긴 건이다/);

  // 처리하고 사흘 뒤 같은 사건에 새 항목(예: 무역위 진행일정 새 줄)이 잡히면 숨기지 않고 이력만 붙인다
  const later = new Date(NOW.getTime() + 3 * 86400000);
  const lateOpts = { ...opts, now: later };
  await post('trade-remedy', { schema: 'trade_remedy/v1', generatedAt: later.toISOString(), quotas: [], notices: [], checks: [{ source: '무역위원회', status: 'ok' }],
    events: [{ ...eha, id: 'ktc:case:00000999', label: '무역위 새 조사 · 구제23-2026-11호', text: '중국산 아크릴산 2-에틸헥실 우회덤핑 아님 — 품목 아크릴산 2-에틸헥실 신규 덤핑 조사', detectedAt: new Date(later.getTime() - 3600000).toISOString() }] });
  const d2 = (await call('scoop_desk', {}, lateOpts)).text;
  assert.match(d2, /id ktc:case:00000999/);
  assert.match(d2, /\[1\. 새 후보 — 실적 있는 유형부터\] 1건/);

  // 장부를 못 읽으면 숨기지 않는다(판정으로 숨기는 것은 그대로)
  const tools = (await rpc('tools/list', {}, opts)).body.result.tools;
  assert.ok(tools.some((x) => x.name === 'scoop_desk'));
  assert.match(tools.find((x) => x.name === 'package_save').description, /item_ids에 관련 레이더 항목 id나 원문 주소/);
  assert.ok(!(await rpc('tools/list')).body.result.tools.some((x) => x.name === 'scoop_desk'));   // 공개 연결엔 없다
  assert.match((await rpc('initialize', { protocolVersion: '2025-03-26' }, opts)).body.result.instructions, /단독 후보를 달라는 요청에는 scoop_desk부터/);
});
