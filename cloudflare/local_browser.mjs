// Notices of cities whose 새올(eminwon) sites time out from GitHub runners (overseas IPs) but open from the reporter's
// computer in Korea (checked 10-30 in the built-in browser). A scheduled session on that computer reads the first list
// page of each city there and submits only the cell texts of each row here. kr_local_notice_watch.py reads them with the
// same rules as its own fetches (parse_cells) and runs right after (workflow_dispatch). Fixed city list, size caps,
// no URLs or HTML accepted: the session cannot point the watch anywhere else.
import { storeOp } from './store.mjs';
import { safeEqual, sha256Hex, textResult } from './common.mjs';
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
  광양시: 'https://eminwon.gwangyang.go.kr',  // 11-07 포스코 광양제철소 — GitHub에서 시간 초과가 잦음
  천안시: 'https://eminwon.cheonan.go.kr',    // 11-07 LS일렉트릭 — GitHub에서 ReadTimeout이 잦음
  평택시: 'https://eminwon.pyeongtaek.go.kr',  // 11-08 KG모빌리티 — 11-03~07 직접 조회 24번 중 3번 실패
  원주시: 'https://eminwon.wonju.go.kr',       // 11-08 HL만도 — 같은 기간 3번 실패
};
const BLOB = 'kr_local_browser';
const SCHEMA = 'kr_local_browser/v1';
const MAX_ROWS = 60;
const MAX_CELLS = 14;
const MAX_CELL = 300;
const MGT = /^[0-9A-Za-z_-]{1,40}$/;
const MAX_DETAILS = 8;          // 시·군마다 상세 페이지 줄
const MAX_DETAIL_TITLE = 300;
const MAX_DETAIL_BODY = 420;    // 본문 앞 400자 + '…'
const MAX_ATTACH_TEXT = 4000;   // 첨부 공고문 글자 앞부분
export const VIAS = ['aside', 'browser'];
const DISPATCH_GAP_MS = 60 * 60000;  // 같은 시간 안에 다시 올려도 kr-local은 한 번만 요청

const clean = (s, n) => String(s ?? '').replace(/\s+/g, ' ').trim().slice(0, n);

// 무역구제 공고 목록 중 해외 IP에서 막히는 곳(10-27: 호주 TRN은 GitHub 응답 없음·Cloudflare 중계 HTTP 520, 10-30 기자 컴퓨터에서는
// 0.3초 안 200, 101줄 중 한국 22줄, robots.txt 허용). 한국이 든 줄의 칸 글자와 그 줄 링크(같은 사이트 경로만)만 받는다.
// trade_remedy_watch.py가 읽는다. 한국 줄을 받은 날 처음 한 번만 무역구제 감시를 바로 돌린다(하루 한 번까지) — 정기 실행(평일
// 07:40)은 전날 16:40 수집을 읽어, 처음 올린 날(10-30 금요일 TRN 추가 뒤 첫 수집은 월요일 08:40)엔 하루 넘게 '미확인'으로 남았다.
export const BROWSER_PAGES = {
  'au-trn': { host: 'www.industry.gov.au', url: 'https://www.industry.gov.au/australian-trade-remedies-commission/trade-remedies-notices-trns' },
  // 호주 진행 사건 목록의 한국 줄과 그 사건 페이지의 사건 정보·주요 일정·공개기록(EPR) 문서 표(11-14 기자 승인). 줄 첫 칸이 종류
  // (list·case·title·info·date·doc·error), 둘째 칸이 사건 번호 — au_epr_cases.py가 읽는다. 사건 6건 x 문서 60줄까지라 줄 한도를 따로 둔다.
  'au-epr': { host: 'www.industry.gov.au', url: 'https://www.industry.gov.au/australian-trade-remedies-commission/current-cases-and-electronic-public-record-epr',
    maxRows: 600, what: '사건·문서 줄' },
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
      if (!cells.length || rows.length >= (def.maxRows ?? MAX_PAGE_ROWS)) { dropped += 1; continue; }
      rows.push({ cells, links });
    }
    accepted.push({ id, fetchedAt: nowIso, rows, dropped, ...(error ? { error } : {}),
      ...(!error && !rows.length ? { error: `${def.what ?? '한국 줄'} 0줄(사이트 형식 변경 또는 빈 응답) — 0건 아님` } : {}) });
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
  return { lines: [...accepted.map((x) => `- 무역구제 ${x.id}: ${x.error ? `미확인(${x.error})` : `${BROWSER_PAGES[x.id].what ?? '한국 줄'} ${x.rows.length}`}${x.dropped ? ` · 버린 줄 ${x.dropped}` : ''}`),
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
const LABOR_DISPATCH_GAP_MS = 5 * 3600000;  // 아침(09:00)·오후(16:00) 수집마다 한 번씩(11-11 전엔 08:40·16:40)
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
  // 직접 올리기 열쇠 지문 등록(browser_upload_key와 같음) — 도구 목록을 옛것으로 가진 세션(새 도구를 못 부름)도 이 도구로 등록할 수 있게
  const keyLine = args.uploadKeySha256 !== undefined ? (await browserUploadKey(ctx, { sha256: args.uploadKeySha256 })) : null;
  if (keyLine && !given.length && !pages.length && !labor.length) return keyLine;
  if (!given.length && !pages.length && !labor.length) return textResult('cities·pages·labor가 비었음 — 저장하지 않음.', true);
  const nowIso = ctx.now.toISOString();
  const laborResult = labor.length ? await submitLabor(ctx, labor, nowIso) : { lines: [] };
  const pageResult = pages.length ? await submitPages(ctx, pages, nowIso) : { lines: [] };
  pageResult.lines.push(...laborResult.lines);
  if (keyLine) pageResult.lines.push(keyLine.content[0].text);
  if (!given.length) return textResult([`브라우저 수집 저장 · ${nowIso.slice(0, 16)}Z`, ...pageResult.lines].join('\n'));
  const accepted = [];
  const refused = [];
  const via = VIAS.includes(args.via) ? args.via : null;     // 수집 길(aside = Aside REPL, browser = 내장 브라우저)
  for (const c of given.slice(0, 20)) {
    const city = clean(c?.city, 40);
    if (!Object.hasOwn(BROWSER_CITIES, city)) { refused.push(city || '(이름 없음)'); continue; }
    if (accepted.some((x) => x.city === city)) continue;
    const error = clean(c?.error, 120);
    const rows = [];
    let dropped = 0;
    let details = 0;
    for (const r of Array.isArray(c?.rows) ? c.rows : []) {
      const mgt = clean(r?.mgt, 40);
      const cells = (Array.isArray(r?.cells) ? r.cells : []).slice(0, MAX_CELLS).map((x) => clean(x, MAX_CELL)).filter(Boolean);
      if (!MGT.test(mgt) || !cells.length || rows.some((x) => x.mgt === mgt)) { dropped += 1; continue; }
      if (rows.length >= MAX_ROWS) { dropped += 1; continue; }
      // 상세 페이지(11-06 Aside 수집 — 수집 쪽이 출입처 이름 든 줄만 읽음): 제목·본문 앞·첨부 이름 글자만 받는다(HTML·주소는 받지 않음)
      const d = r?.detail && typeof r.detail === 'object' ? r.detail : null;
      // 첨부 공고문 글자(11-06 Aside: hwpx만, 공고마다 3개, 앞 4000자) — 사업 개요 뽑기는 감시(attachment_facts)가 한다
      const atts = Array.isArray(d?.attachments) ? d.attachments.slice(0, 3).map((a) => {
        const name = clean(a?.name, 120);
        if (!name) return null;
        const text = clean(a?.text, MAX_ATTACH_TEXT);
        return text ? { name, text } : { name, error: clean(a?.error, 60) || '못 읽음' };
      }).filter(Boolean) : null;
      const detail = details < MAX_DETAILS && d && clean(d.title, MAX_DETAIL_TITLE) ? { title: clean(d.title, MAX_DETAIL_TITLE),
        body: clean(d.body, MAX_DETAIL_BODY), files: (Array.isArray(d.files) ? d.files : []).slice(0, 6).map((x) => clean(x, 120)).filter(Boolean),
        ...(atts ? { attachments: atts } : {}) } : null;
      if (detail) details += 1;
      rows.push({ mgt, cells, ...(detail ? { detail } : {}) });
    }
    accepted.push({ city, fetchedAt: nowIso, rows, dropped, ...(via ? { via } : {}), ...(details ? { details } : {}), ...(error ? { error } : {}),
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
  const doc = { schema: SCHEMA, updatedAt: nowIso, ...(via ? { via } : {}), cities: [...accepted, ...keep], lastDispatchAt: prev.lastDispatchAt ?? null };
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
  const lines = [`브라우저 수집 저장 · ${nowIso.slice(0, 16)}Z${via ? ` · ${via === 'aside' ? 'Aside' : '내장 브라우저'}` : ''} · 시·군 ${accepted.length}곳 (정상 ${ok.length})`,
    ...accepted.map((x) => `- ${x.city}: ${x.error ? `미확인(${x.error})` : `${x.rows.length}줄`}${x.details ? ` · 상세 ${x.details}` : ''}${x.dropped ? ` · 버린 줄 ${x.dropped}` : ''}`),
    ...(refused.length ? [`받지 않은 이름(허용 목록 밖): ${refused.join(', ')}`] : []),
    dispatch, ...pageResult.lines];
  return textResult(lines.join('\n'));
}

// 기자 컴퓨터 Aside가 직접 올리는 길(11-06): 예약 작업 모델이 50KB 가까운 인자를 그대로 옮겨 적지 않게 한다.
// 열쇠(32바이트 난수)는 기자 컴퓨터 Aside 브라우저 프로필의 이 사이트 저장소(localStorage)에만 있고, Worker는 그 SHA-256만 둔다
// (browser_upload_key 도구로 등록 — 열쇠 글자는 대화·저장소·로그 어디에도 나오지 않는다). 받은 인자는 local_notice_submit과 같은 규칙으로 걸러
// 같은 문서에 넣고 같은 간격으로만 감시 실행을 요청한다. 열쇠가 틀리면 404(경로가 있는지도 알리지 않음).
const KEY_BLOB = 'browser_upload_key';
const UPLOAD_MAX = 400_000;
const UPLOAD_PAGE = '<!doctype html><meta charset="utf-8"><title>radar upload</title><p>취재 레이더 기자 컴퓨터 수집 올리기 창(내용 없음)</p>';

async function readKey(ctx) {
  const { row } = await storeOp(ctx, 'blobs.get', { name: KEY_BLOB });
  try { return row ? JSON.parse(row.body) : null; } catch { return null; }
}

export async function browserUploadKey(ctx, args) {
  const prev = await readKey(ctx);
  const hash = String(args?.sha256 ?? '').trim().toLowerCase();
  if (!hash) {
    return textResult(prev?.sha256 ? `등록된 열쇠: 지문 ${prev.sha256.slice(0, 8)}… · 등록 ${String(prev.registeredAt).slice(0, 16)}Z`
      + ` · 마지막 올림 ${prev.lastUploadAt ? `${String(prev.lastUploadAt).slice(0, 16)}Z` : '없음'}` : '등록된 열쇠 없음 — Aside 직접 올리기 꺼짐(예약 작업은 local_notice_submit으로 올림)');
  }
  if (!/^[0-9a-f]{64}$/.test(hash)) return textResult('sha256은 16진수 64자여야 함 — 등록하지 않음.', true);
  const nowIso = ctx.now.toISOString();
  await storeOp(ctx, 'blobs.put', { name: KEY_BLOB, body: JSON.stringify({ sha256: hash, registeredAt: nowIso, lastUploadAt: null }) });
  return textResult(`열쇠 등록함 · 지문 ${hash.slice(0, 8)}… · ${nowIso.slice(0, 16)}Z${prev?.sha256 && prev.sha256 !== hash ? ' · 이전 열쇠는 이제 못 씀' : ''}`);
}

export async function browserUpload(request, env, deps = {}) {
  if (request.method === 'GET') {
    return new Response(UPLOAD_PAGE, { headers: { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store', 'X-Robots-Tag': 'noindex',
      'Content-Security-Policy': "default-src 'none'; connect-src 'self'; frame-ancestors 'none'" } });
  }
  if (request.method !== 'POST') return new Response('Method not allowed', { status: 405, headers: { Allow: 'GET, POST' } });
  const notFound = new Response('Not found', { status: 404 });
  const m = /^Bearer\s+([A-Za-z0-9_-]{32,128})$/.exec(request.headers.get('Authorization') ?? '');
  if (!m) return notFound;
  const ctx = { env, private: true, fetch: deps.fetch ?? ((...a) => fetch(...a)), now: deps.now ?? new Date() };
  const key = await readKey(ctx);
  if (!key?.sha256 || !(await safeEqual(await sha256Hex(m[1]), key.sha256))) return notFound;
  const text = await request.text();
  if (text.length > UPLOAD_MAX) return Response.json({ error: 'too large' }, { status: 413 });
  let args;
  try { args = JSON.parse(text); } catch { return Response.json({ error: 'bad json' }, { status: 400 }); }
  if (!args || typeof args !== 'object' || Array.isArray(args)) return Response.json({ error: 'bad json' }, { status: 400 });
  const result = await localNoticeSubmit(ctx, { cities: args.cities, pages: args.pages, labor: args.labor, via: args.via });
  await storeOp(ctx, 'blobs.put', { name: KEY_BLOB, body: JSON.stringify({ ...key, lastUploadAt: ctx.now.toISOString() }) });
  return Response.json({ ok: !result.isError, text: result.content?.[0]?.text ?? '' }, { headers: { 'Cache-Control': 'no-store' } });
}

// 기자 컴퓨터 수집 상태(11-08): 예약 작업(평일 08:40·16:40 KST)은 기자 컴퓨터가 꺼져 있거나 Claude 앱·Aside가 안 떠 있으면 돌지 못하고,
// 그러면 해외 IP 차단 시·군 고시·공고·노동위 회의·호주 TRN이 조용히 멈춘다(radar_health는 공개 도구라 이 수집을 싣지 않는다).
// radar_today 수집 상태에 이상이 있을 때만 한 줄로 알린다: 가장 최근 예정 시각 뒤 올림 없음 / 이번 수집에서 못 읽은 시·군 / 대신 쓴 길.
// 11-09: 월 08:40 예정 시각에 기자 컴퓨터가 연결돼 있지 않자 예약 작업이 '기기 없음'으로 정지·꺼짐(enabled=false)이 됐다 — 컴퓨터를 켜도 저절로
// 다시 켜지는지 확인되지 않아, 놓친 줄에 예약 작업 목록에서 켜져 있는지 보라고 붙인다.
// 11-11 기자 결정: 08:40은 사흘 연속 컴퓨터 연결 전이라 빠져 09:00으로(한 예약 작업은 분을 하나만 써 오후도 16:00)
export const BROWSER_SLOTS = [[9, 0], [16, 0]];  // 예약 작업 '새올 고시·공고 브라우저 수집'(KST, 평일)
// 이 수집 말고는 길이 없는 시·군(GitHub 직접 조회가 늘 시간 초과) — 나머지는 직접 조회가 실패한 날만 대신 쓰는 곳
export const BROWSER_ONLY = ['인천 부평구', '구미시', '청주시', '순천시', '함평군'];
const SLOT_GRACE_MIN = 45;  // 예약 작업이 돌고 올리기까지 기다리는 시간
const SLOT_EARLY_MIN = 10;
const KST_MS = 9 * 3600000;
const kstStamp = (ms) => `${new Date(ms + KST_MS).toISOString().slice(5, 16).replace('T', ' ')} KST`;

// 지금(여유 45분을 뺀 시각) 이전의 가장 최근 예정 시각(ms). 토·일은 건너뛴다(공휴일은 예약 작업도 돌기 때문에 세지 않음).
export function lastBrowserSlot(nowMs) {
  const t = nowMs - SLOT_GRACE_MIN * 60000;
  const day0 = Math.floor((t + KST_MS) / 86400000) * 86400000 - KST_MS;  // 오늘 KST 자정
  for (let d = 0; d < 8; d++) {
    const base = day0 - d * 86400000;
    const dow = new Date(base + KST_MS).getUTCDay();
    if (dow === 0 || dow === 6) continue;
    for (const [h, m] of [...BROWSER_SLOTS].reverse()) {
      const s = base + (h * 60 + m) * 60000;
      if (s <= t) return s;
    }
  }
  return null;
}

export async function browserHealth(ctx) {
  const nowMs = ctx.now.getTime();
  const slot = lastBrowserSlot(nowMs);
  const read = async (name) => {
    const { row } = await storeOp(ctx, 'blobs.get', { name });
    if (!row) return null;
    try { return JSON.parse(row.body); } catch { return { broken: true }; }
  };
  const [doc, labor, pages, key] = await Promise.all([read(BLOB), read(LABOR_BLOB), read(PAGES_BLOB), read(KEY_BLOB)]);
  const label = '기자 컴퓨터 수집(Aside 예약 작업, 평일 09:00·16:00 — 해외 IP 차단 시·군 고시·공고·노동위 회의·호주 TRN·사건 공개기록)';
  if (!doc) return `${label}: 결과 없음 — 미확인`;
  if (doc.broken) return `${label}: 저장 형식 오류 — 미확인`;
  const missed = (t) => slot != null && !(t >= slot - SLOT_EARLY_MIN * 60000);
  const at = Date.parse(doc.updatedAt ?? '');
  const short = (c) => c.replace(/^(.+?)(?:시|군)$/, '$1');
  const issues = [];
  if (missed(at)) {
    issues.push(`⚠ 마지막 ${Number.isFinite(at) ? `${kstStamp(at)}(${Math.round((nowMs - at) / 3600000)}시간 전)` : '시각 없음'} — ${kstStamp(slot)} 예정 수집이 안 올라옴`
      + `(기자 컴퓨터·Claude 앱·Aside가 켜져 있는지 확인. 예정 시각에 컴퓨터 연결이 없으면 예약 작업이 저절로 꺼질 수 있다 — Claude 앱 예약 작업 목록에서 '새올 고시·공고 브라우저 수집'이 켜져 있는지도 확인)`
      + `. 그 뒤 ${BROWSER_ONLY.map(short).join('·')} 고시·공고는 미확인`);
  } else {
    const bad = (doc.cities ?? []).filter((c) => c.fetchedAt === doc.updatedAt && c.error && BROWSER_ONLY.includes(c.city));
    if (bad.length) issues.push(`시·군 못 읽음 ${bad.length}곳(${bad.map((c) => `${short(c.city)}: ${String(c.error).slice(0, 40)}`).join(', ')})`);
    if (doc.via === 'browser') issues.push('Aside가 안 돼 내장 브라우저로 대신 수집함');
    else if (doc.via === 'aside' && key?.sha256 && !(Date.parse(key.lastUploadAt ?? '') >= at - 15 * 60000)) {
      issues.push('직접 올리기가 안 돼 대화로 옮겨 올림(올리기 열쇠 확인 — browser_upload_key)');
    }
    for (const [name, d] of [['노동위 회의일정', labor], ['호주 TRN', pages]]) {
      const t = Date.parse(d?.updatedAt ?? '');
      if (missed(t)) issues.push(`${name}은 이번 수집에 빠짐(마지막 ${Number.isFinite(t) ? kstStamp(t) : '없음'})`);
    }
  }
  return issues.length ? `${label}: ${issues.join(' · ')} — 해당 부분 0건은 미확인` : null;
}
