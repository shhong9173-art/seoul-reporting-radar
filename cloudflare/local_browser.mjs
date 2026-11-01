// Notices of cities whose 새올(eminwon) sites time out from GitHub runners (overseas IPs) but open from the reporter's
// computer in Korea (checked 10-30 in the built-in browser). A scheduled session on that computer reads the first list
// page of each city there and submits only the cell texts of each row here. kr_local_notice_watch.py reads them with the
// same rules as its own fetches (parse_cells) and runs right after (workflow_dispatch). Fixed city list, size caps,
// no URLs or HTML accepted: the session cannot point the watch anywhere else.
import { storeOp } from './store.mjs';
import { textResult } from './common.mjs';
import { dispatchNow } from './dispatch.mjs';

export const BROWSER_CITIES = {
  '인천 부평구': 'https://eminwon.icbp.go.kr',
  구미시: 'https://eminwon.gumi.go.kr',
  청주시: 'https://www.cheongju.go.kr',  // 새올 목록이 국내에서도 시간 초과 → 홈페이지 고시공고 게시판
  순천시: 'https://eminwon.suncheon.go.kr',
  함평군: 'https://eminwon.hampyeong.go.kr',
  // GitHub에서 들쑥날쑥한 곳: 직접 조회가 실패한 날만 이 수집으로 대신한다.
  양산시: 'https://eminwon.yangsan.go.kr',
  '광주 광산구': 'https://eminwon.gwangsan.go.kr',
  나주시: 'https://eminwon.naju.go.kr',  // 11-01 석유화학 출입처(LG화학 나주공장) — GitHub 직접 조회가 안 되는 날 대신
};
const BLOB = 'kr_local_browser';
const SCHEMA = 'kr_local_browser/v1';
const MAX_ROWS = 60;
const MAX_CELLS = 14;
const MAX_CELL = 300;
const MGT = /^[0-9A-Za-z_-]{1,40}$/;
const DISPATCH_GAP_MS = 60 * 60000;  // 같은 시간 안에 다시 올려도 kr-local은 한 번만 요청

const clean = (s, n) => String(s ?? '').replace(/\s+/g, ' ').trim().slice(0, n);

// 무역구제 공고 목록 중 해외 IP에서 막히는 곳(10-27: 호주 TRN은 GitHub 응답 없음·Cloudflare 중계 HTTP 520, 10-30 기자 컴퓨터에서는
// 0.3초 안 200, 101줄 중 한국 22줄, robots.txt 허용). 한국이 든 줄의 칸 글자와 그 줄 링크(같은 사이트 경로만)만 받는다.
// trade_remedy_watch.py가 읽는다. 한국 줄을 받은 날 처음 한 번만 무역구제 감시를 바로 돌린다(하루 한 번까지) — 정기 실행(평일
// 07:40)은 전날 16:40 수집을 읽어, 처음 올린 날(10-30 금요일 TRN 추가 뒤 첫 수집은 월요일 08:40)엔 하루 넘게 '미확인'으로 남았다.
export const BROWSER_PAGES = {
  'au-trn': { host: 'www.industry.gov.au', url: 'https://www.industry.gov.au/australian-trade-remedies-commission/trade-remedies-notices-trns' },
};
const PAGES_DISPATCH_GAP_MS = 20 * 3600000;  // 무역구제 감시는 하루 한 번까지(아침 수집 뒤)
const PAGES_BLOB = 'trade_remedy_browser';
const PAGES_SCHEMA = 'trade_remedy_browser/v1';
const MAX_PAGE_ROWS = 200;

function pageLink(host, href) {
  const h = String(href ?? '').trim();
  if (/^\/[^/]/.test(h)) return h.slice(0, 400);
  try { const u = new URL(h); return u.protocol === 'https:' && u.hostname === host ? u.pathname + u.search : null; } catch { return null; }
}

async function submitPages(ctx, given, nowIso) {
  const accepted = [];
  const refused = [];
  for (const p of given.slice(0, 5)) {
    const id = clean(p?.id, 30);
    const def = BROWSER_PAGES[id];
    if (!def) { refused.push(id || '(이름 없음)'); continue; }
    if (accepted.some((x) => x.id === id)) continue;
    const error = clean(p?.error, 120);
    const rows = [];
    let dropped = 0;
    for (const r of Array.isArray(p?.rows) ? p.rows : []) {
      const cells = (Array.isArray(r?.cells) ? r.cells : []).slice(0, 10).map((x) => clean(x, MAX_CELL)).filter(Boolean);
      const links = (Array.isArray(r?.links) ? r.links : []).slice(0, 4).map((x) => pageLink(def.host, x)).filter(Boolean);
      if (!cells.length || rows.length >= MAX_PAGE_ROWS) { dropped += 1; continue; }
      rows.push({ cells, links });
    }
    accepted.push({ id, fetchedAt: nowIso, rows, dropped, ...(error ? { error } : {}),
      ...(!error && !rows.length ? { error: '한국 줄 0줄(사이트 형식 변경 또는 빈 응답) — 0건 아님' } : {}) });
  }
  if (!accepted.length) return { lines: refused.length ? [`받지 않은 목록(허용 밖): ${refused.join(', ')}`] : [] };
  const { row } = await storeOp(ctx, 'blobs.get', { name: PAGES_BLOB });
  let prev = {};
  try { prev = row ? JSON.parse(row.body) : {}; } catch { prev = {}; }
  const keep = (Array.isArray(prev.pages) ? prev.pages : []).filter((x) => BROWSER_PAGES[x?.id] && !accepted.some((a) => a.id === x.id));
  const doc = { schema: PAGES_SCHEMA, updatedAt: nowIso, pages: [...accepted, ...keep], lastDispatchAt: prev.lastDispatchAt ?? null };
  let dispatch = '무역구제 감시 실행 요청 안 함(한국 줄을 받은 목록 없음) — 다음 정기 감시(평일 07:40)에 반영';
  if (accepted.some((x) => !x.error)) {
    const last = Date.parse(prev.lastDispatchAt ?? '');
    if (Number.isFinite(last) && ctx.now.getTime() - last < PAGES_DISPATCH_GAP_MS) {
      dispatch = `무역구제 감시 실행 요청은 ${Math.round((ctx.now.getTime() - last) / 3600000)}시간 전에 이미 함(하루 한 번) — 다음 정기 감시(평일 07:40)에 반영`;
    } else {
      const status = await dispatchNow(ctx, 'trade-remedy.yml', 'browser');
      if (status === 'ok') doc.lastDispatchAt = nowIso;
      dispatch = status === 'ok' ? '무역구제 감시(trade-remedy) 실행 요청함 — 몇 분 뒤 trade_remedies에 반영'
        : `무역구제 감시 실행 요청 실패(${status}) — 다음 정기 감시(평일 07:40)에 반영`;
    }
  }
  await storeOp(ctx, 'blobs.put', { name: PAGES_BLOB, body: JSON.stringify(doc) });
  return { lines: [...accepted.map((x) => `- 무역구제 ${x.id}: ${x.error ? `미확인(${x.error})` : `한국 줄 ${x.rows.length}`}${x.dropped ? ` · 버린 줄 ${x.dropped}` : ''}`),
    ...(refused.length ? [`받지 않은 목록(허용 밖): ${refused.join(', ')}`] : []), dispatch] };
}

export async function localNoticeSubmit(ctx, args) {
  const given = Array.isArray(args.cities) ? args.cities : [];
  const pages = Array.isArray(args.pages) ? args.pages : [];
  if (!given.length && !pages.length) return textResult('cities·pages가 비었음 — 저장하지 않음.', true);
  const nowIso = ctx.now.toISOString();
  const pageResult = pages.length ? await submitPages(ctx, pages, nowIso) : { lines: [] };
  if (!given.length) return textResult([`브라우저 수집 저장 · ${nowIso.slice(0, 16)}Z`, ...pageResult.lines].join('\n'));
  const accepted = [];
  const refused = [];
  for (const c of given.slice(0, 20)) {
    const city = clean(c?.city, 40);
    if (!Object.hasOwn(BROWSER_CITIES, city)) { refused.push(city || '(이름 없음)'); continue; }
    if (accepted.some((x) => x.city === city)) continue;
    const error = clean(c?.error, 120);
    const rows = [];
    let dropped = 0;
    for (const r of Array.isArray(c?.rows) ? c.rows : []) {
      const mgt = clean(r?.mgt, 40);
      const cells = (Array.isArray(r?.cells) ? r.cells : []).slice(0, MAX_CELLS).map((x) => clean(x, MAX_CELL)).filter(Boolean);
      if (!MGT.test(mgt) || !cells.length || rows.some((x) => x.mgt === mgt)) { dropped += 1; continue; }
      if (rows.length >= MAX_ROWS) { dropped += 1; continue; }
      rows.push({ mgt, cells });
    }
    accepted.push({ city, fetchedAt: nowIso, rows, dropped, ...(error ? { error } : {}),
      ...(!error && !rows.length ? { error: '목록 0줄(사이트 형식 변경 또는 빈 응답) — 0건 아님' } : {}) });
  }
  if (!accepted.length) {
    return textResult([`허용된 시·군이 없음(받지 않음: ${refused.join(', ')}) — 시·군은 저장하지 않음.`, ...pageResult.lines].join('\n'), !pageResult.lines.length);
  }
  const { row } = await storeOp(ctx, 'blobs.get', { name: BLOB });
  let prev = {};
  try { prev = row ? JSON.parse(row.body) : {}; } catch { prev = {}; }
  const keep = (Array.isArray(prev.cities) ? prev.cities : []).filter((x) => Object.hasOwn(BROWSER_CITIES, x?.city)
    && !accepted.some((a) => a.city === x.city));
  const doc = { schema: SCHEMA, updatedAt: nowIso, cities: [...accepted, ...keep], lastDispatchAt: prev.lastDispatchAt ?? null };
  const ok = accepted.filter((x) => !x.error);
  let dispatch = '감시 실행 요청 안 함(성공한 시·군 없음)';
  if (ok.length) {
    const last = Date.parse(prev.lastDispatchAt ?? '');
    if (Number.isFinite(last) && ctx.now.getTime() - last < DISPATCH_GAP_MS) {
      dispatch = `감시 실행 요청은 ${Math.round((ctx.now.getTime() - last) / 60000)}분 전에 이미 함 — 다시 요청하지 않음(다음 정기 실행에 반영)`;
    } else {
      const status = await dispatchNow(ctx, 'kr-local.yml', 'browser');
      if (status === 'ok') doc.lastDispatchAt = nowIso;
      dispatch = status === 'ok' ? '지자체 고시·공고 감시(kr-local) 실행 요청함 — 몇 분 뒤 kr_official에 반영'
        : `감시 실행 요청 실패(${status}) — 다음 정기 실행(평일 06:30·16:20)에 반영`;
    }
  }
  await storeOp(ctx, 'blobs.put', { name: BLOB, body: JSON.stringify(doc) });
  const lines = [`브라우저 수집 저장 · ${nowIso.slice(0, 16)}Z · 시·군 ${accepted.length}곳 (정상 ${ok.length})`,
    ...accepted.map((x) => `- ${x.city}: ${x.error ? `미확인(${x.error})` : `${x.rows.length}줄`}${x.dropped ? ` · 버린 줄 ${x.dropped}` : ''}`),
    ...(refused.length ? [`받지 않은 이름(허용 목록 밖): ${refused.join(', ')}`] : []),
    dispatch, ...pageResult.lines];
  return textResult(lines.join('\n'));
}
