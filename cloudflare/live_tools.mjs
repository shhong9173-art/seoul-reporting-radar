// Live lookups: prior coverage, public originals, OpenDART and KONEPS.
// Every channel reports ok / failed / not_configured separately: a failed or
// unconfigured search is never reported as "0건".
import {
  beatName, clampInt, decodeBytes, decodeEntities, fetchJson, htmlToText, kstDate, kstStamp, matchesQuery,
  readCapped, sha256Hex, textResult, ymd,
} from './common.mjs';
import { issueEvidence, publicationDate } from './evidence.mjs';
import { readFeed } from './screen.mjs';
import { storeOp } from './store.mjs';
import { readZip } from './zip.mjs';

const TIMEOUT_MS = 15000;
const signal = () => AbortSignal.timeout(TIMEOUT_MS);
const stripTags = (s) => decodeEntities(String(s ?? '').replace(/<[^>]+>/g, '')).trim();

function rssItems(xml) {
  const items = [];
  for (const m of xml.matchAll(/<item>([\s\S]*?)<\/item>/g)) {
    const get = (tag) => {
      const r = new RegExp(`<${tag}[^>]*>([\\s\\S]*?)<\\/${tag}>`).exec(m[1]);
      return r ? decodeEntities(r[1].replace(/^<!\[CDATA\[|\]\]>$/g, '')).trim() : '';
    };
    items.push({ title: get('title'), url: get('link'), published: get('pubDate'), source: get('source') });
  }
  return items;
}

function kstDay(value) {
  const t = Date.parse(value);
  return Number.isFinite(t) ? new Date(t + 9 * 3600000).toISOString().slice(0, 10) : null;
}

const BROWSER_HEADERS = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
  'Accept': 'application/rss+xml,application/xml;q=0.9,*/*;q=0.8',
  'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.6',
};

// Korean public APIs (OpenDART, data.go.kr) can hang on header-less requests from Workers;
// browser-like headers reach them (verified for opendart.fss.or.kr on 2026-10-26).
const API_HEADERS = {
  'User-Agent': BROWSER_HEADERS['User-Agent'],
  'Accept': 'application/json,application/xml;q=0.9,*/*;q=0.8',
  'Accept-Language': BROWSER_HEADERS['Accept-Language'],
};

async function rssChannel(ctx, url, days, mapItem = (x) => x) {
  try {
    const r = await ctx.fetch(url, { signal: signal(), headers: BROWSER_HEADERS });
    if (!r.ok) return { status: 'failed', error: `HTTP ${r.status}`, items: [] };
    const xml = await r.text();
    if (!/<rss[\s>]/.test(xml) || !/<channel[\s>]/.test(xml)) return { status: 'failed', error: 'RSS 형식 아님(차단·확인 페이지 가능성)', items: [] };
    const from = kstDate(ctx.now, days);
    const all = rssItems(xml).map(mapItem);
    const items = all.map((x) => ({ ...x, date: kstDay(x.published) }))
      .filter((x) => x.date && x.date >= from && x.date <= kstDate(ctx.now));
    const invalid = all.filter((x) => !kstDay(x.published) || kstDay(x.published) > kstDate(ctx.now)).length;
    return { status: invalid ? 'partial' : 'ok', error: invalid ? `기사 날짜 누락·미래 ${invalid}건` : '', returned: all.length, items };
  } catch (e) {
    return { status: 'failed', error: e.name === 'TimeoutError' ? '시간 초과' : String(e.message ?? e), items: [] };
  }
}

function googleNews(ctx, q, days) {
  return rssChannel(ctx, `https://news.google.com/rss/search?q=${encodeURIComponent(q)}&hl=ko&gl=KR&ceid=KR:ko`, days);
}

// Google News answers 503 to many Cloudflare egress IPs, so Bing News RSS is a
// second web index. Its links are click-tracking URLs carrying the original.
// (11-03: 자동 보도 대조 radar_press_check는 GitHub Actions에서 돌아 구글이 정상 — 막히는 건 Worker의 즉석 news_check뿐.)
//
// 빙 RSS 기본 결과는 관련도 순 10여 건이라 날짜가 섞인다 — 11-03 탐침 127: 'Hyundai Metaplant' 한국판 11건 중 60일 안 2건,
// 최신순(qft=sortbydate="1", 빙 화면의 '최신순' 선택)은 12건 모두 10-29~11-02. 둘 다 받아 겹침을 빼고 합친다(오래된 앞선 기사는 관련도 순이 잡는다).
// 한글 없는 영문 낱말이면 미국판(en-US)도 본다 — 미국 공장·주 정부 공고 단서는 현지 매체가 먼저 쓴다(11-03 'Qcells Cartersville air permit').
// 판정 기준(채널 상태)은 한국판 관련도 순 하나다. 나머지는 더해 보는 것이라 실패하면 그 사실만 적는다.
const NEWEST = '&qft=sortbydate%3d%221%22';
const BING_EDITIONS = [
  { label: '한국판', params: 'setlang=ko-KR&cc=KR' },
  { label: '한국판 최신순', params: 'setlang=ko-KR&cc=KR' + NEWEST },
  { label: '미국판', params: 'setlang=en-US&cc=US', latin: true },
  { label: '미국판 최신순', params: 'setlang=en-US&cc=US' + NEWEST, latin: true },
];
function bingEdition(ctx, q, days, params) {
  return rssChannel(ctx, `https://www.bing.com/news/search?q=${encodeURIComponent(q)}&format=rss&${params}`, days, (x) => {
    let url = x.url;
    try { url = new URL(x.url).searchParams.get('url') || x.url; } catch { /* keep */ }
    const host = (/^https?:\/\/(?:www\.)?([^/]+)/.exec(url) || [])[1] ?? '';
    return { ...x, url, source: x.source || host };
  });
}

export const isLatinQuery = (q) => /[A-Za-z]/.test(q) && !/[\uAC00-\uD7A3\u3131-\u318E]/.test(q);

async function bingNews(ctx, q, days) {
  const eds = BING_EDITIONS.filter((e) => !e.latin || isLatinQuery(q));
  const rs = await Promise.all(eds.map((e) => bingEdition(ctx, q, days, e.params)));
  const base = rs[0];
  const seen = new Set(base.items.map((x) => x.url));
  const items = [...base.items];
  const parts = [`${eds[0].label} ${base.items.length}건`];
  let returned = base.returned ?? 0;
  eds.slice(1).forEach((e, i) => {
    const r = rs[i + 1];
    if (r.status !== 'ok' && r.status !== 'partial') { parts.push(`${e.label} 실패(${r.error})`); return; }
    const extra = r.items.filter((x) => !seen.has(x.url) && seen.add(x.url));
    items.push(...extra);
    returned += r.returned ?? 0;
    parts.push(`${e.label} +${extra.length}건`);
  });
  const usDown = eds.some((e, i) => e.latin && rs[i].status !== 'ok' && rs[i].status !== 'partial');
  return { ...base, items, returned, note: parts.join(' · ') + ' (겹침 뺌)' + (usDown ? ' — 미국판 실패분은 현지 보도 미확인' : '') };
}

// Naver news search moved to NAVER API HUB (NCP). HUB keys go first; keys from the old Developers
// Center (still valid for apps registered before the cutoff) are tried only when HUB refuses them.
const NAVER_ENDPOINTS = [
  { label: 'API HUB', url: 'https://naverapihub.apigw.ntruss.com/search/v1/news',
    headers: (id, secret) => ({ 'X-NCP-APIGW-API-KEY-ID': id, 'X-NCP-APIGW-API-KEY': secret }) },
  { label: '개발자센터', url: 'https://openapi.naver.com/v1/search/news.json',
    headers: (id, secret) => ({ 'X-Naver-Client-Id': id, 'X-Naver-Client-Secret': secret }) },
];

// One page is 100 articles, newest first; a busy query fills it within days (10-29: '기아 광명 증축' 180일 → 미확인).
// Further pages (start 101 … 901, the API's limit) are read until the window is covered.
const NAVER_PAGE = 100;
const NAVER_MAX_START = 901;

async function naverNews(ctx, q, days) {
  if (!ctx.private) return { status: 'not_available', error: '기자 전용 연결에서만', items: [] };
  const id = ctx.env?.NAVER_CLIENT_ID; const secret = ctx.env?.NAVER_CLIENT_SECRET;
  if (!id || !secret) return { status: 'not_configured', error: 'Cloudflare에 NAVER_CLIENT_ID/SECRET 미등록', items: [] };
  const refused = [];
  const from = kstDate(ctx.now, days);
  for (const ep of NAVER_ENDPOINTS) {
    const all = [];
    let stopped = '';
    try {
      let refusedHere = false;
      for (let start = 1; start <= NAVER_MAX_START; start += NAVER_PAGE) {
        const url = `${ep.url}?query=${encodeURIComponent(q)}&display=${NAVER_PAGE}&start=${start}&sort=date`;
        const r = await ctx.fetch(url, { signal: signal(), headers: ep.headers(id, secret) });
        if (start === 1 && (r.status === 401 || r.status === 403)) { refused.push(`${ep.label} HTTP ${r.status}`); refusedHere = true; break; }
        if (!r.ok) {
          if (start === 1) return { status: 'failed', error: `${ep.label} HTTP ${r.status}`, items: [] };
          stopped = `${start}번째 기사부터 HTTP ${r.status}`;
          break;
        }
        const body = await r.json();
        if (!Array.isArray(body.items)) {
          if (start === 1) return { status: 'failed', error: '뉴스 items 배열 없음', items: [] };
          stopped = `${start}번째 기사부터 형식 오류`;
          break;
        }
        all.push(...body.items);
        if (body.items.length < NAVER_PAGE) break;
        const oldest = body.items.map((x) => kstDay(x.pubDate)).filter(Boolean).sort()[0];
        if (!oldest || oldest < from) break;
        if (start === NAVER_MAX_START) stopped = `최신순 ${NAVER_MAX_START + NAVER_PAGE - 1}건 상한 — 그 이전 기사는 못 봄`;
      }
      if (refusedHere) continue;
    } catch (e) {
      if (!all.length) return { status: 'failed', error: `${ep.label} ${e.name === 'TimeoutError' ? '시간 초과' : String(e.message ?? e)}`, items: [] };
      stopped = `${all.length + 1}번째 기사부터 ${e.name === 'TimeoutError' ? '시간 초과' : '조회 실패'}`;
    }
    const items = all.map((x) => ({ title: stripTags(x.title), url: x.originallink || x.link,
      published: x.pubDate, date: kstDay(x.pubDate), source: (/https?:\/\/(?:www\.)?([^/]+)/.exec(x.originallink || '') || [])[1] ?? '' }))
      .filter((x) => x.date && x.date >= from && x.date <= kstDate(ctx.now));
    const invalid = all.filter((x) => !kstDay(x.pubDate) || kstDay(x.pubDate) > kstDate(ctx.now)).length;
    const error = [invalid ? `기사 날짜 누락·미래 ${invalid}건` : '', stopped].filter(Boolean).join(' · ');
    return { status: error ? 'partial' : 'ok', error, via: ep.label, returned: all.length, items,
      note: all.length > NAVER_PAGE ? `최신순 ${all.length}건까지 읽음` : '' };
  }
  return { status: 'failed', error: `키 거부(${refused.join(', ')}) — 키 값·API 선택(뉴스) 확인`, items: [] };
}

// The collector (historical_exclusive_press_collector.py) marks a healthy index with this status — the index is
// partial by design (Google News titles only). Other statuses, a stale or undated index stay failures.
const DANDOK_OK = new Set(['ok', 'historical_industry_exclusive_rss_partial_index']);

async function dandokIndex(ctx, q, days) {
  try {
    const v = await fetchJson(ctx, 'tools/dandok.json');
    const age = ctx.now.getTime() - Date.parse(v.sourceGeneratedAt);
    if (!DANDOK_OK.has(v.status) || !Array.isArray(v.items) || !Number.isFinite(age) || age < 0 || age > 48 * 3600000)
      return { status: 'failed', error: '단독 색인 실패·오래됨·생성일 미확인', items: [] };
    const from = kstDate(ctx.now, Math.min(days, 120));
    const items = (v.items ?? []).filter((r) => r.published >= from && r.published <= kstDate(ctx.now) && matchesQuery(q, r.title, r.companies))
      .map((r) => ({ title: r.title, url: r.url, date: r.published, source: r.source }));
    return { status: 'ok', returned: (v.items ?? []).length, items, note: `색인 범위 최근 ${Math.min(days, 120)}일 · ${v.status ?? ''}` };
  } catch (e) {
    return { status: 'failed', error: String(e.message ?? e), items: [] };
  }
}

// 구글 뉴스가 Worker에서 막혔을 때(11-12 기자 질문 '구글뉴스 수집은 왜 계속 실패하지'): 구글은 Cloudflare 서버(Worker)에서 오는
// 요청에 HTTP 503을 준다 — 즉석 news_check만 막히고, GitHub에서 도는 자동 보도 대조(radar_press_check)는 정상이다
// (11-11~12 최근 5회 구글 31/31·32/32·29/29·34/34·40/40). 'failed'만 찍으면 고장처럼 보여, 막힌 곳과 자동 대조의 마지막 구글 성적을 함께 보인다.
async function googleRelayNote(ctx) {
  try {
    const doc = await readFeed(ctx, 'radar-check');
    const at = doc?.generatedAt;
    if (!at || !Array.isArray(doc.items)) return '';
    const ran = doc.items.filter((r) => r.checkedAt === at);
    if (!ran.length) return '';
    const ok = ran.filter((r) => r.channels?.google?.status === 'ok').length;
    return ` · 자동 보도 대조(GitHub) 마지막 실행 ${kstStamp(new Date(at)).slice(5, 16)} 구글 ${ok}/${ran.length} 정상`;
  } catch {
    return '';
  }
}

function googleBlocked(ch) {
  return ch.status === 'failed' && /HTTP 503|HTTP 429|RSS 형식 아님/.test(ch.error ?? '');
}

// 구글 뉴스 GitHub 경유(11-12 기자 승인): 구글은 Worker에 503을 주지만 GitHub Actions에는 정상이다. 기자 전용 연결에서 구글이 막히면
// ① 같은 낱말·기간을 GitHub가 6시간 안에 받아 둔 결과가 있으면 그것을 구글 채널로 쓰고, ② 없으면 낱말을 기자 전용 저장소에 맡기고
// GitHub 작업(google-news-relay.yml)을 부른다 — 1~2분 뒤 같은 낱말로 다시 부르면 붙는다. 낱말은 GitHub 입력값·로그에 싣지 않는다
// (공개 저장소라 기자가 무엇을 확인 중인지 드러나면 안 된다). 하루 RELAY_DAILY번까지, 같은 낱말은 RELAY_REASK분 안에 다시 맡기지 않는다.
export const RELAY_WORKFLOW = 'google-news-relay.yml';
export const RELAY_REPO = 'shhong9173-art/seoul-reporting-radar';
const RELAY_FRESH_MS = 6 * 3600000;
const RELAY_DAILY = 40;
const RELAY_REASK_MS = 10 * 60000;

export async function relayKey(q, days) {
  return (await sha256Hex(`${q.trim().replace(/\s+/g, ' ')}|${days}`)).slice(0, 16);
}

async function googleRelay(ctx, q, days) {
  const qid = await relayKey(q, days);
  const done = await readFeed(ctx, 'google-relay').catch(() => null);
  const hit = (done?.results ?? []).find((r) => r.qid === qid);
  if (hit && ctx.now.getTime() - Date.parse(hit.fetchedAt) <= RELAY_FRESH_MS) {
    if (hit.status !== 'ok') return { used: null, note: ` · GitHub 경유 조회도 실패(${hit.error ?? '원인 미상'}, ${kstStamp(new Date(hit.fetchedAt)).slice(11, 16)})` };
    const from = kstDate(ctx.now, days);
    const items = (hit.items ?? []).filter((x) => x.date && x.date >= from && x.date <= kstDate(ctx.now));
    return { used: { status: 'ok', returned: hit.returned ?? items.length, items, via: `GitHub 경유 ${kstStamp(new Date(hit.fetchedAt)).slice(5, 16)} 조회` } };
  }
  const token = ctx.env?.GH_DISPATCH_TOKEN;
  if (!token) return { used: null, note: ' · GitHub 경유 조회 미설정(Cloudflare 비밀값 GH_DISPATCH_TOKEN)' };
  const now = ctx.now.getTime();
  const today = kstDate(ctx.now);
  const book = (await readFeed(ctx, 'google-relay-pending').catch(() => null)) ?? {};
  const pending = (book.pending ?? []).filter((p) => now - Date.parse(p.askedAt) <= 30 * 60000);
  const count = book.day === today ? (book.count ?? 0) : 0;
  const mine = pending.find((p) => p.qid === qid);
  if (mine && now - Date.parse(mine.askedAt) < RELAY_REASK_MS) return { used: null, note: ' · GitHub에 구글 조회를 맡겨 둠 — 1~2분 뒤 같은 낱말·기간으로 다시 부르면 붙음' };
  if (count >= RELAY_DAILY) return { used: null, note: ` · GitHub 경유 조회 오늘 한도(${RELAY_DAILY}번) 다 씀` };
  const next = { schema: 'google_relay_pending/v1', day: today, count: count + 1,
    pending: [...pending.filter((p) => p.qid !== qid), { qid, q, days, askedAt: ctx.now.toISOString() }].slice(-20) };
  await storeOp(ctx, 'blobs.put', { name: 'google_relay_pending', body: JSON.stringify(next) });
  try {
    const r = await ctx.fetch(`https://api.github.com/repos/${RELAY_REPO}/actions/workflows/${RELAY_WORKFLOW}/dispatches`, {
      method: 'POST', signal: signal(), body: JSON.stringify({ ref: 'main' }),
      headers: { Authorization: `Bearer ${token}`, Accept: 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'seoul-reporting-radar-worker', 'Content-Type': 'application/json' } });
    if (r.status !== 204) return { used: null, note: ` · GitHub 경유 조회 요청 실패(HTTP ${r.status}${r.status === 401 || r.status === 403 || r.status === 404 ? ' — 토큰 권한·만료 확인' : ''})` };
  } catch (e) {
    return { used: null, note: ` · GitHub 경유 조회 요청 실패(${e.name === 'TimeoutError' ? '시간 초과' : e.name})` };
  }
  return { used: null, note: ' · GitHub에 구글 조회를 맡김 — 1~2분 뒤 같은 낱말·기간으로 다시 부르면 붙음' };
}

export async function newsCheck(ctx, args) {
  const q = String(args.q ?? '').trim();
  if (q.length < 2) return textResult('q(검색 낱말 2~3개)를 넣어 주세요.', true);
  const days = clampInt(args.days, 1, 365, 365);
  const limit = clampInt(args.limit, 1, 30, 10);
  let [google, bing, naver, dandok] = await Promise.all([googleNews(ctx, q, days), bingNews(ctx, q, days),
    naverNews(ctx, q, days), dandokIndex(ctx, q, days)]);
  let relayNote = '';
  if (ctx.private && googleBlocked(google)) {
    const relay = await googleRelay(ctx, q, days).catch((e) => ({ used: null, note: ` · GitHub 경유 조회 오류(${e.name})` }));
    if (relay.used) google = relay.used;
    relayNote = relay.note ?? '';
  }
  const channels = { '구글 뉴스': google, '빙 뉴스': bing, '네이버 뉴스': naver, '[단독] 색인': dandok };
  const out = [`보도 대조: "${q}" · 최근 ${days}일 · ${kstStamp(ctx.now)}`];
  let hits = 0;
  // Required coverage: 네이버 + 웹 색인(구글 또는 빙) + [단독] 색인.
  const incomplete = [];
  if (naver.status !== 'ok') incomplete.push('네이버 뉴스');
  if (google.status !== 'ok' && bing.status !== 'ok') incomplete.push('웹 색인(구글·빙 모두)');
  if (dandok.status !== 'ok') incomplete.push('[단독] 색인');
  for (const [name, ch] of Object.entries(channels)) {
    if (ch.status !== 'ok') {
      const standIn = name === '구글 뉴스' && bing.status === 'ok' ? ' (웹 색인은 빙이 대신 — 판정에 영향 없음)' : '';
      if (name === '구글 뉴스' && googleBlocked(ch)) {
        out.push(`\n■ ${name}: 이 서버(Cloudflare Worker)에서는 구글이 접속을 막음(${ch.error}) — 레이더 고장 아님${await googleRelayNote(ctx)}${relayNote}${standIn}`);
        continue;
      }
      out.push(`\n■ ${name}: ${ch.status} — ${ch.error}${standIn}`);
      continue;
    }
    hits += ch.items.length;
    out.push(`\n■ ${name}${ch.via ? `(${ch.via})` : ''}: ${ch.items.length}건 (응답 ${ch.returned}건)${ch.note ? ` · ${ch.note}` : ''}`);
    for (const x of ch.items.slice(0, limit)) {
      out.push(`${x.date} | ${x.source || '-'} | ${x.title}${/\[단독\]|단독/.test(x.title) ? ' ★단독' : ''}`);
      if (x.url) out.push(`   ${x.url}`);
    }
    if (ch.items.length > limit) out.push(`   … 남은 ${ch.items.length - limit}건`);
  }
  const verdict = incomplete.length
    ? `판정: 미확인 — ${incomplete.join('·')} 조회 실패·미설정(0건이 아님). 관련 후보 ${hits}건.` +
      (hits ? ' 후보가 있으면 이미 났을 수 있으니 먼저 연다.' : '')
    : hits ? `판정: 관련 보도 후보 ${hits}건 — 같은 사건·같은 각도인지 열어 봐야 함.`
      : '판정: 필수 채널(네이버·웹 색인·[단독] 색인) 모두 0건 — 미보도 증거 아님. 낱말을 바꿔 2~3번, 전문지·온라인 매체(더벨·딜사이트 등)는 웹검색으로 따로 본다.';
  out.splice(1, 0, verdict, await issueEvidence(ctx, 'news', { q, days, complete: !incomplete.length,
    hits, matches: Object.values(channels).flatMap((r) => r.items.slice(0, 30).map((x) => ({ url: x.url, date: x.date, title: x.title }))), channels: Object.fromEntries(Object.entries(channels).map(([name, r]) => [name, { status: r.status, returned: r.returned, hits: r.items.length }])) }));
  return textResult(out.join('\n'));
}

// --------------------------------------------------------------- originals
const ALLOWED_SUFFIXES = [
  '.go.kr', 'dart.fss.or.kr', 'opendart.fss.or.kr', 'kind.krx.co.kr', 'kipris.or.kr', 'kosis.kr', 'kepco.co.kr',
  'khnp.co.kr', 'kpx.or.kr', 'kogas.or.kr', 'kosa.or.kr', 'koema.or.kr', 'kama.or.kr', 'kaida.co.kr',
  'kita.net', 'bok.or.kr', '.gov', 'europa.eu', 'nhtsa.gov', 'federalregister.gov', 'sec.gov',
  // direct-beat company and IR sites
  'hyundai.com', 'kia.com', 'mobis.com', 'hyundai-wia.com', 'hlmando.com', 'gm-korea.co.kr', 'kg-mobility.com',
  'renault.co.kr', 'mercedes-benz.co.kr', 'bmw.co.kr', 'volkswagen.co.kr', 'audi.co.kr', 'honda.co.kr',
  'hankooktire.com', 'nexentire.com', 'kumhotire.com', 'posco-inc.com', 'posco.com', 'hyundai-steel.com',
  'kg-steel.co.kr', 'seah.co.kr', 'seahsteel.co.kr', 'dongkuk.com', 'dongkukcm.com', 'koreazinc.co.kr',
  'youngpoong.co.kr', 'hd-hyundaielectric.com', 'ls-electric.com', 'taihan.com', 'lscns.co.kr', 'lsmnm.com',
  'lsholdings.com', 'doosanenerbility.com', 'gs.co.kr', 'gscaltex.com', 'hanwhasolutions.com', 'oci.co.kr',
  'oci-holdings.co.kr', 'taekwang.com', 'dongsungchemical.com', 'dlchem.com',
];

export function allowedUrl(raw) {
  let u;
  try { u = new URL(String(raw ?? '')); } catch { return null; }
  if (!['https:', 'http:'].includes(u.protocol) || u.username || u.password || u.port) return null;
  const host = u.hostname.toLowerCase();
  if (/^[\d.]+$/.test(host) || host.includes(':')) return null;
  const ok = ALLOWED_SUFFIXES.some((s) => (s.startsWith('.') ? host.endsWith(s) : host === s || host.endsWith('.' + s)));
  return ok ? u : null;
}

// DART main.do is a frame page; the filing body lives in report/viewer.do.
export function dartViewerDocs(html, rcpNo) {
  const docs = [];
  const seen = new Set();
  const call = /viewDoc\(\s*['"]?(\d{14})['"]?\s*,\s*['"]?(\d+)['"]?\s*,\s*['"]?([\w.-]*)['"]?\s*,\s*['"]?(\d+)['"]?\s*,\s*['"]?(\d+)['"]?\s*,\s*['"]?([A-Za-z0-9_.-]+)['"]?(?:\s*,\s*['"]?([\w.-]*)['"]?)?\s*\)/gi;
  for (const m of html.matchAll(call)) {
    if (m[1] !== rcpNo) continue;
    const doc = { rcpNo: m[1], dcmNo: m[2], eleId: m[3], offset: m[4], length: m[5], dtd: m[6], tocNo: m[7] || '', text: '' };
    const key = [doc.dcmNo, doc.eleId, doc.offset, doc.length].join('|');
    if (!seen.has(key)) { seen.add(key); docs.push(doc); }
  }
  const nodes = {};
  const assign = /([A-Za-z_$][\w$]*)\s*\[\s*['"](text|rcpNo|dcmNo|eleId|offset|length|dtd|tocNo)['"]\s*\]\s*=\s*(['"])(.*?)\3\s*;/gis;
  for (const m of html.matchAll(assign)) (nodes[m[1]] ??= {})[m[2]] = decodeEntities(m[4]).trim();
  for (const f of Object.values(nodes)) {
    if (f.rcpNo !== rcpNo || !['dcmNo', 'eleId', 'offset', 'length', 'dtd'].every((k) => f[k])) continue;
    const key = [f.dcmNo, f.eleId, f.offset, f.length].join('|');
    if (seen.has(key)) {
      const d = docs.find((x) => [x.dcmNo, x.eleId, x.offset, x.length].join('|') === key);
      if (d && !d.text) d.text = f.text ?? '';
      continue;
    }
    seen.add(key);
    docs.push({ rcpNo, dcmNo: f.dcmNo, eleId: f.eleId, offset: f.offset, length: f.length, dtd: f.dtd, tocNo: f.tocNo || '', text: f.text || '' });
  }
  return docs.map((d) => ({ ...d, viewer: 'https://dart.fss.or.kr/report/viewer.do?' + new URLSearchParams(
    Object.fromEntries(Object.entries({ rcpNo: d.rcpNo, dcmNo: d.dcmNo, eleId: d.eleId, offset: d.offset,
      length: d.length, dtd: d.dtd, ...(d.tocNo ? { tocNo: d.tocNo } : {}) }))).toString() }));
}

// SEC EDGAR는 자동 접속에 '회사명 연락이메일' 형식의 접속 표시(User-Agent)를 요구한다(sec.gov 공개 접속 규칙).
// 값은 Cloudflare 비밀값 SEC_USER_AGENT로만 받는다(GitHub Actions의 같은 이름 비밀값과 같은 값) — 코드·저장소에 연락처를 두지 않는다.
// 10-31 운영: 퍼스트솔라 10-Q(sec.gov/Archives)가 HTTP 403이라 USITC 청원 대목을 원문으로 확인하지 못했다.
const isSec = (url) => url.hostname === 'sec.gov' || url.hostname.endsWith('.sec.gov');
const secRaw = (ctx) => String(ctx.env?.SEC_USER_AGENT ?? '').replace(/[\r\n]+/g, ' ').trim().slice(0, 200);
// HTTP 머리글은 영문(ASCII)만 된다 — '아이뉴스24'처럼 한글이 섞이면 fetch가 실패하므로 쓰지 않고 안내한다
const secAgent = (ctx) => (/^[\x20-\x7E]+$/.test(secRaw(ctx)) ? secRaw(ctx) : '');
export function sourceAgent(ctx, url) {
  return isSec(url) && secAgent(ctx) ? secAgent(ctx) : 'Mozilla/5.0 seoul-reporting-radar (reporter research)';
}

export async function sourceDocument(ctx, args) {
  let url = allowedUrl(args.url);
  if (!url) return textResult('허용된 공식·출입처 도메인(go.kr·DART·KIND·KIPRIS·.gov·EU·출입처 홈페이지 등)의 http(s) 주소만 연다.', true);
  const offset = clampInt(args.offset, 0, 5_000_000, 0);
  const limit = clampInt(args.limit, 500, 16000, 16000);
  let response;
  for (let hop = 0; hop < 4; hop++) {
    try {
      response = await ctx.fetch(url.href, { redirect: 'manual', signal: signal(),
        headers: { 'User-Agent': sourceAgent(ctx, url), Accept: 'text/html,application/xhtml+xml,application/xml,text/plain,application/json' } });
    } catch (e) {
      return textResult(`원문 열기 실패: ${e.name === 'TimeoutError' ? '시간 초과' : e.message} — 원문 미확인으로 적는다.`, true);
    }
    if (![301, 302, 303, 307, 308].includes(response.status)) break;
    const next = allowedUrl(new URL(response.headers.get('Location') ?? '', url).href);
    if (!next) return textResult('허용 도메인 밖으로 이동하는 주소라 열지 않음.', true);
    url = next;
  }
  if (!response.ok) {
    const sec = isSec(url) && [403, 429].includes(response.status)
      ? (secAgent(ctx) ? ' (SEC 접속 표시는 보냈음 — SEC가 이 서버 접속을 막았을 수 있다. 브라우저로 원문을 연다)'
        : secRaw(ctx) ? ' (SEC_USER_AGENT에 한글 등 영문 밖 글자가 있어 보내지 않음 — 영문으로 다시 넣는다. 예: iNews24 이름 이메일)'
          : ' (SEC 접속 표시 SEC_USER_AGENT가 Cloudflare 비밀값에 없음 — SEC는 회사명·연락 이메일을 적은 접속만 받는다)') : '';
    return textResult(`원문 HTTP ${response.status}${sec} — 원문 미확인으로 적는다.`, true);
  }
  const type = response.headers.get('Content-Type') ?? '';
  if (/pdf|octet-stream|zip|image/i.test(type)) return textResult(`본문이 ${type} 형식이라 텍스트로 읽지 못함. 원문 링크: ${url.href}`, true);
  let bytes;
  try { bytes = await readCapped(response, 4_000_000); } catch (e) { return textResult(String(e.message), true); }
  let { text: raw, charset } = decodeBytes(bytes, type);
  let sections = [];
  let frameOnly = false;
  const rcp = url.hostname.endsWith('dart.fss.or.kr') && /\/dsaf001\/main\.do$/.test(url.pathname)
    ? url.searchParams.get('rcpNo') : null;
  if (rcp && /^\d{14}$/.test(rcp)) {
    frameOnly = true;
    sections = dartViewerDocs(raw, rcp);
    if (sections.length) {
      try {
        const viewer = await ctx.fetch(sections[0].viewer, { signal: signal(), headers: { 'User-Agent': BROWSER_HEADERS['User-Agent'], Referer: url.href } });
        if (viewer.ok) {
          const vb = await readCapped(viewer, 4_000_000);
          ({ text: raw, charset } = decodeBytes(vb, viewer.headers.get('Content-Type') ?? ''));
          url = new URL(sections[0].viewer);
          frameOnly = false;
        }
      } catch { /* keep the frame page and say so below */ }
    }
  }
  const text = /html|xml/i.test(type) || /<html|<body|<\?xml/i.test(raw.slice(0, 500)) ? htmlToText(raw) : raw;
  const hash = await sha256Hex(text);
  const slice = text.slice(offset, offset + limit);
  const out = [`원문: ${url.href}`, `받은 시각 ${kstStamp(ctx.now)} · 문자셋 ${charset} · 전체 ${text.length}자 · 내용 해시 sha256:${hash}`];
  out.push(`검증 게시일: ${frameOnly ? '미확인' : publicationDate(raw, url.href) ?? '미확인(명시된 게시일을 찾지 못함)'}`);
  if (!frameOnly && slice.trim()) out.splice(1, 0, await issueEvidence(ctx, 'source', {
    url: url.href, hash, date: publicationDate(raw, url.href), excerpt: slice,
  }));
  if (rcp && sections.length && !frameOnly) {
    out.push(`DART 본문 문서 ${sections.length}개 중 첫 문서를 읽음. 다른 문서는 아래 주소로 source_document를 다시 부른다:`);
    for (const d of sections.slice(0, 12)) out.push(`- ${d.text || `문서 ${d.dcmNo}/${d.eleId}`}: ${d.viewer}`);
  } else if (rcp) {
    out.push('DART 본문 주소 추출 또는 본문 조회 실패 — 아래는 틀 페이지 텍스트. dart_find_text(기자 전용)를 쓴다.');
  }
  out.push(

    `구간 ${offset}~${offset + slice.length}${offset + slice.length < text.length ? ` (다음 offset=${offset + slice.length})` : ' (끝)'}`,
    '---', slice);
  return textResult(out.join('\n'));
}

// ------------------------------------------------------------------- DART
async function corpCodeFor(ctx, args) {
  const direct = String(args.corp_code ?? '').trim();
  if (/^\d{8}$/.test(direct)) return { code: direct, name: args.company ?? direct };
  const want = String(args.company ?? '').trim();
  if (!want) return null;
  const registry = await fetchJson(ctx, 'dart_corp_codes.json');
  const companies = registry.companies ?? {};
  const target = beatName(want) ?? want;
  for (const [name, entry] of Object.entries(companies)) {
    if (name === want || name === target || beatName(name) === target) return { code: entry.corp_code, name };
  }
  return null;
}

function dartKey(ctx) {
  const key = ctx.env?.DART_API_KEY;
  return ctx.private && key ? key : null;
}

export async function dartFilings(ctx, args) {
  const key = dartKey(ctx);
  if (!key) return textResult('DART 조회는 기자 전용 연결에서, Cloudflare에 DART_API_KEY를 등록한 뒤에만 된다.', true);
  const corp = await corpCodeFor(ctx, args).catch(() => null);
  if (!corp) return textResult('회사 고유번호를 찾지 못함 — company(출입처 이름) 또는 corp_code(8자리)를 넣어 주세요. 못 찾은 것은 공시 0건이 아니다.', true);
  const end = /^\d{8}$/.test(args.end ?? '') ? args.end : ymd(kstDate(ctx.now));
  const start = /^\d{8}$/.test(args.start ?? '') ? args.start : ymd(kstDate(ctx.now, 90));
  const rows = [];
  let total = null;
  for (let page = 1; page <= 3; page++) {
    const url = `https://opendart.fss.or.kr/api/list.json?crtfc_key=${encodeURIComponent(key)}&corp_code=${corp.code}` +
      `&bgn_de=${start}&end_de=${end}&page_no=${page}&page_count=100`;
    let body;
    try {
      const r = await ctx.fetch(url, { signal: signal(), headers: API_HEADERS });
      if (!r.ok) return textResult(`OpenDART HTTP ${r.status} — 조회 실패(0건 아님)`, true);
      body = await r.json();
    } catch (e) {
      return textResult(`OpenDART 조회 실패: ${e.name === 'TimeoutError' ? '시간 초과' : e.message} (0건 아님)`, true);
    }
    if (body.status === '013') { total = 0; break; }
    if (body.status !== '000') return textResult(`OpenDART 상태 ${body.status}: ${body.message ?? ''} — 조회 실패(0건 아님)`, true);
    total = body.total_count;
    rows.push(...(body.list ?? []));
    if (page >= (body.total_page ?? 1)) break;
  }
  const out = [`DART 공시 목록: ${corp.name}(${corp.code}) ${start}~${end} · ${rows.length}건${total > rows.length ? ` / 전체 ${total}건(앞 300건만)` : ''}`];
  if (total === 0) out.push('OpenDART가 이 기간 공시 0건이라고 응답(조회 성공).');
  for (const x of rows) {
    out.push(`${x.rcept_dt} | ${String(x.report_nm ?? '').replace(/\s+/g, ' ').trim()} | ${x.rcept_no} | ${x.flr_nm}${x.rm ? ` | 비고 ${x.rm}` : ''}`);
    out.push(`   https://dart.fss.or.kr/dsaf001/main.do?rcpNo=${x.rcept_no}`);
  }
  return textResult(out.join('\n'));
}

function decodeXml(bytes) {
  return decodeBytes(bytes, '').text;
}

export async function dartFindText(ctx, args) {
  const key = dartKey(ctx);
  if (!key) return textResult('DART 원문 검색은 기자 전용 연결에서, Cloudflare에 DART_API_KEY를 등록한 뒤에만 된다.', true);
  const rcp = String(args.rcp_no ?? '').trim();
  const word = String(args.word ?? '').trim();
  if (!/^\d{14}$/.test(rcp) || word.length < 1) return textResult('rcp_no(14자리 접수번호)와 word를 넣어 주세요.', true);
  const limit = clampInt(args.limit, 1, 20, 8);
  let bytes;
  try {
    const r = await ctx.fetch(`https://opendart.fss.or.kr/api/document.xml?crtfc_key=${encodeURIComponent(key)}&rcept_no=${rcp}`, { signal: signal(), headers: API_HEADERS });
    if (!r.ok) return textResult(`OpenDART HTTP ${r.status} — 원문 미확인`, true);
    bytes = await readCapped(r, 30_000_000);
  } catch (e) {
    return textResult(`OpenDART 원문 실패: ${e.name === 'TimeoutError' ? '시간 초과' : e.message} — 원문 미확인`, true);
  }
  if (bytes[0] !== 0x50 || bytes[1] !== 0x4b) {
    const msg = new TextDecoder('utf-8').decode(bytes.slice(0, 400));
    return textResult(`OpenDART가 ZIP 대신 응답: ${(/<message>([^<]+)/.exec(msg) || /"message"\s*:\s*"([^"]+)/.exec(msg) || [])[1] ?? '형식 오류'} — 원문 미확인`, true);
  }
  let entries;
  try { entries = await readZip(bytes); } catch (e) { return textResult(`ZIP 해제 실패: ${e.message}`, true); }
  const out = [`DART 원문 검색: ${rcp} "${word}" · 파일 ${entries.length}개`];
  let found = 0;
  for (const entry of entries) {
    const text = htmlToText(decodeXml(entry.data));
    const hash = await sha256Hex(text);
    const hits = [];
    let i = text.indexOf(word);
    while (i >= 0) { hits.push(i); i = text.indexOf(word, i + word.length); }
    out.push(`\n■ ${entry.name} · ${text.length}자 · ${hits.length}곳 · sha256:${hash}`);
    const excerpt = hits.slice(0, Math.max(0, limit - found)).map((at) => text.slice(Math.max(0, at - 160), at + word.length + 160)).join('\n');
    const sourceUrl = `https://dart.fss.or.kr/dsaf001/main.do?rcpNo=${rcp}`;
    if (excerpt) out.push(await issueEvidence(ctx, 'source', { url: sourceUrl, hash,
      date: publicationDate('', sourceUrl), excerpt }));
    for (const at of hits.slice(0, Math.max(0, limit - found))) {
      out.push(`… ${text.slice(Math.max(0, at - 160), at + word.length + 160).replace(/\s+/g, ' ')} …`);
      found++;
    }
  }
  out.push(`\n원문 링크: https://dart.fss.or.kr/dsaf001/main.do?rcpNo=${rcp}`);
  if (!found) out.push('이 낱말은 원문 텍스트에서 찾지 못함(표 이미지·첨부 PDF 안의 글자는 못 봄).');
  return textResult(out.join('\n'));
}

// -------------------------------------------------------------------- G2B
const G2B_BASE = 'https://apis.data.go.kr/1230000/ad/BidPublicInfoService';
const G2B_OPS = { 물품: 'getBidPblancListInfoThng', 공사: 'getBidPblancListInfoCnstwk' };

export async function g2bBids(ctx, args) {
  const q = String(args.q ?? '').trim();
  const key = ctx.private ? (ctx.env?.G2B_API_KEY || ctx.env?.DATA_GO_KR_KEY) : null;
  if (!key) {
    let snap;
    try { snap = await fetchJson(ctx, 'digests/g2b_tender_latest.json'); } catch {
      return textResult('나라장터: 실시간 키 미등록이고 공개 스냅샷도 없음 — 미확인(0건 아님). radar_health의 나라장터 상태를 본다.', true);
    }
    const rows = (snap.notices ?? []).filter((x) => matchesQuery(q, x.title, x.demandAgency, x.issuingAgency));
    const out = [`나라장터 공개 스냅샷(${snap.from}~${snap.to}, 기술 낱말로 거른 공고) · "${q}" ${rows.length}건 — 실시간 검색 아님`];
    for (const x of rows.slice(0, 30)) out.push(`${String(x.issueDate).slice(0, 10)} | ${x.title} | ${x.demandAgency || x.issuingAgency} | ${x.noticeId}`);
    return textResult(out.join('\n'));
  }
  const days = clampInt(args.days, 1, 7, 3);
  const end = ymd(kstDate(ctx.now)) + '2359';
  const start = ymd(kstDate(ctx.now, days)) + '0000';
  const out = [`나라장터 입찰공고 실시간: "${q}" · ${start.slice(0, 8)}~${end.slice(0, 8)} (공고≠낙찰·계약)`];
  for (const [label, op] of Object.entries(G2B_OPS)) {
    const matched = []; let total = null; let read = 0; let error = null;
    for (let page = 1; page <= 5; page++) {
      const url = `${G2B_BASE}/${op}?serviceKey=${encodeURIComponent(key)}&pageNo=${page}&numOfRows=100&type=json&inqryDiv=1&inqryBgnDt=${start}&inqryEndDt=${end}`;
      try {
        const r = await ctx.fetch(url, { signal: signal(), headers: API_HEADERS });
        if (!r.ok) { error = `HTTP ${r.status}`; break; }
        const body = await r.json();
        const header = body?.response?.header ?? {};
        if (!['00', '000'].includes(String(header.resultCode))) { error = `제공기관 코드 ${header.resultCode ?? '?'}`; break; }
        let items = body.response.body?.items;
        if (items && !Array.isArray(items)) items = items.item ?? [];
        items = Array.isArray(items) ? items : items ? [items] : [];
        total = Number(body.response.body?.totalCount ?? 0);
        read += items.length;
        for (const x of items) {
          if (matchesQuery(q, x.bidNtceNm, x.dminsttNm, x.ntceInsttNm)) matched.push(x);
        }
        if (read >= total || !items.length) break;
      } catch (e) { error = e.name === 'TimeoutError' ? '시간 초과' : String(e.message ?? e); break; }
    }
    if (error) { out.push(`\n■ ${label}: 조회 실패 ${error} — 0건 아님`); continue; }
    out.push(`\n■ ${label}: 일치 ${matched.length}건 (읽은 ${read}/${total}건${read < total ? ' — 앞부분만 봄' : ''})`);
    for (const x of matched.slice(0, 20)) {
      out.push(`${String(x.bidNtceDt ?? '').slice(0, 16)} | ${x.bidNtceNm} | ${x.dminsttNm || x.ntceInsttNm} | ${x.bidNtceNo}-${x.bidNtceOrd ?? ''}`);
      if (x.bidNtceDtlUrl) out.push(`   ${x.bidNtceDtlUrl}`);
    }
  }
  return textResult(out.join('\n'));
}
