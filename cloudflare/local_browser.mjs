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

// 노동위원회 회의일정 달력(11-04): 첫 화면 '오늘 회의' 칸은 위원회마다 5건까지만 보이고, 달력이 부르는 selectMeetingSche.do(POST)는
// GitHub에서 화면과 같은 값을 보내도 오류 쪽만 돌려준다(탐침 133·134·168). 기자 컴퓨터 브라우저의 달력 화면에서는 그달 회의
// 전체(mtgId·mtgSn·mtgYmd·회의명)가 온다 — 그 네 값만 받는다. 회의 상세(GET, 공개)는 kr_labor_watch.py가 GitHub에서 직접 읽는다.
// 위원회 이름은 고정 목록, 값은 숫자 꼴만 받아 상세 주소를 다른 데로 돌릴 수 없다.
// 위원회 번호(cmitCd)는 각 달력 화면 filterForm 값(11-04 기자 컴퓨터 브라우저에서 확인) — 줄에서 받지 않고 여기서 붙인다.
const LABOR_CMIT = { 중앙노동위원회: '00', 서울지방노동위원회: '01', 부산지방노동위원회: '02', 경기지방노동위원회: '03', 인천지방노동위원회: '08',
  강원지방노동위원회: '09', 충북지방노동위원회: '10', 충남지방노동위원회: '04', 전북지방노동위원회: '11', 전남지방노동위원회: '05',
  경북지방노동위원회: '06', 경남지방노동위원회: '07', 울산지방노동위원회: '13', 제주지방노동위원회: '12' };
export const BROWSER_LABOR = Object.keys(LABOR_CMIT);
const LABOR_ROW = /^(\d{10,22})\/(\d{1,3})\/(\d{8})\/([^/]{0,40})$/;
const LABOR_BLOB = 'kr_labor_browser';
const LABOR_SCHEMA = 'kr_labor_browser/v1';
const MAX_LABOR_ROWS = 300;
const LABOR_DISPATCH_GAP_MS = 5 * 3600000;  // 아침(08:40)·오후(16:40) 수집마다 한 번씩
const DAY = (d) => d.toISOString().slice(0, 10).replaceAll('-', '');

async function submitLabor(ctx, given, nowIso) {
  const accepted = [];
  const refused = [];
  const kst = new Date(ctx.now.getTime() + 9 * 3600000);
  const from = DAY(new Date(kst.getTime() - 86400000));
  const to = DAY(new Date(kst.getTime() + 45 * 86400000));
  for (const c of given.slice(0, 20)) {
    const commission = clean(c?.commission, 30);
    if (!BROWSER_LABOR.includes(commission)) { refused.push(commission || '(이름 없음)'); continue; }
    if (accepted.some((x) => x.commission === commission)) continue;
    const error = clean(c?.error, 120);
    const rows = [];
    let dropped = 0;
    // 줄 하나 = '회의번호/순번/회의일/회의명'(예: 2611021110520048685/4/20261104/조정회의) — 예약 작업이 옮겨 적는 양을 줄이려고 글자 한 줄로 받는다
    for (const r of Array.isArray(c?.rows) ? c.rows : []) {
      const m = LABOR_ROW.exec(clean(r, 90));
      const x = m && { mtgId: m[1], mtgSn: m[2], mtgYmd: m[3], cmitCd: LABOR_CMIT[commission], title: clean(m[4], 30) };
      if (!x || x.mtgYmd < from || x.mtgYmd > to || rows.length >= MAX_LABOR_ROWS || rows.some((y) => y.mtgId === x.mtgId && y.mtgSn === x.mtgSn)) { dropped += 1; continue; }
      rows.push(x);
    }
    accepted.push({ commission, fetchedAt: nowIso, rows, dropped, ...(error ? { error } : {}),
      ...(!error && !rows.length ? { error: '회의 0건(사이트 형식 변경 또는 빈 응답) — 0건 아님' } : {}) });
  }
  if (!accepted.length) return { lines: refused.length ? [`받지 않은 위원회(허용 밖): ${refused.join(', ')}`] : [] };
  const { row } = await storeOp(ctx, 'blobs.get', { name: LABOR_BLOB });
  let prev = {};
  try { prev = row ? JSON.parse(row.body) : {}; } catch { prev = {}; }
  const keep = (Array.isArray(prev.commissions) ? prev.commissions : []).filter((x) => BROWSER_LABOR.includes(x?.commission)
    && !accepted.some((a) => a.commission === x.commission));
  const doc = { schema: LABOR_SCHEMA, updatedAt: nowIso, commissions: [...accepted, ...keep], lastDispatchAt: prev.lastDispatchAt ?? null };
  const ok = accepted.filter((x) => !x.error);
  let dispatch = '노동위 감시 실행 요청 안 함(성공한 위원회 없음)';
  if (ok.length) {
    const last = Date.parse(prev.lastDispatchAt ?? '');
    if (Number.isFinite(last) && ctx.now.getTime() - last < LABOR_DISPATCH_GAP_MS) {
      dispatch = `노동위 감시 실행 요청은 ${Math.round((ctx.now.getTime() - last) / 60000)}분 전에 이미 함 — 다음 정기 실행(평일 08:20)에 반영`;
    } else {
      const status = await dispatchNow(ctx, 'kr-labor.yml', 'browser');
      if (status === 'ok') doc.lastDispatchAt = nowIso;
      dispatch = status === 'ok' ? '노동위 회의 감시(kr-labor) 실행 요청함 — 몇 분 뒤 kr_official labor에 반영'
        : `노동위 감시 실행 요청 실패(${status}) — 다음 정기 실행(평일 08:20)에 반영`;
    }
  }
  await storeOp(ctx, 'blobs.put', { name: LABOR_BLOB, body: JSON.stringify(doc) });
  const short = (n) => n.replace(/지방노동위원회$/, '지노위').replace(/^중앙노동위원회$/, '중노위');
  return { lines: [`- 노동위 회의일정 ${accepted.length}곳(정상 ${ok.length}) · 회의 ${ok.reduce((n, x) => n + x.rows.length, 0)}건`
    + `${accepted.some((x) => x.error) ? ` · 미확인: ${accepted.filter((x) => x.error).map((x) => `${short(x.commission)}(${x.error})`).join(', ')}` : ''}`
    + `${accepted.some((x) => x.dropped) ? ` · 버린 줄 ${accepted.reduce((n, x) => n + x.dropped, 0)}` : ''}`,
    ...(refused.length ? [`받지 않은 위원회(허용 밖): ${refused.join(', ')}`] : []), dispatch] };
}

export async function localNoticeSubmit(ctx, args) {
  const given = Array.isArray(args.cities) ? args.cities : [];
  const pages = Array.isArray(args.pages) ? args.pages : [];
  // 도구 목록을 아직 옛것으로 가진 클라이언트는 새 인자(labor)를 JSON 글자로 넘긴다(11-04 확인) — 글자면 한 번 풀어 본다
  let labor = args.labor;
  if (typeof labor === 'string') { try { labor = JSON.parse(labor); } catch { labor = []; } }
  labor = Array.isArray(labor) ? labor : [];
  if (!given.length && !pages.length && !labor.length) return textResult('cities·pages·labor가 비었음 — 저장하지 않음.', true);
  const nowIso = ctx.now.toISOString();
  const laborResult = labor.length ? await submitLabor(ctx, labor, nowIso) : { lines: [] };
  const pageResult = pages.length ? await submitPages(ctx, pages, nowIso) : { lines: [] };
  pageResult.lines.push(...laborResult.lines);
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
