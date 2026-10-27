// Live statistics lookups for drafting: 한국은행 ECOS, KOSIS, 관세청 품목별·국가별 수출입실적(공공데이터포털).
// Private path only (keys live in Cloudflare secrets). A failed or unconfigured call is 미확인, never "0".
// Every series answer states the range it looked at: "highest since D" is a fact about that range, not "역대".
import { clampInt, kstDate, textResult } from './common.mjs';

const TIMEOUT_MS = 20000;
const signal = () => AbortSignal.timeout(TIMEOUT_MS);
const HEADERS = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
  Accept: 'application/json,application/xml;q=0.9,*/*;q=0.8',
};
const ECOS = 'https://ecos.bok.or.kr/api';
const KOSIS_SEARCH = 'https://kosis.kr/openapi/statisticsSearch.do';
const KOSIS_META = 'https://kosis.kr/openapi/statisticsData.do';
const KOSIS_DATA = 'https://kosis.kr/openapi/Param/statisticsParameterData.do';
const CUSTOMS = 'https://apis.data.go.kr/1220000/nitemtrade/getNitemtradeList';

// Beat items → HS codes (broad headings; company performance is not HS data).
export const HS_HINTS = {
  승용차: '8703', 자동차: '8703', 자동차부품: '8708', 부품: '8708', 타이어: '4011', 변압기: '8504', 전선: '8544', 케이블: '8544',
  차단기: '8535', 개폐기: '8536', 배전반: '8537', 열연: '7208', 냉연: '7209', 도금강판: '7210', 아연도금강판: '7210', 철근: '7214',
  선재: '7213', 형강: '7216', 무계목강관: '7304', 용접강관: '7306', 강관: '7306', 아연괴: '7901', 아연: '7901', 정제동: '7403', 동: '7403',
  알루미늄괴: '7601', 알루미늄: '7601', 에틸렌: '2901', 폴리에틸렌: '3901', 이차전지: '8507', 배터리: '8507', 태양광: '8541',
};

const fmt = (v) => (v === null || v === undefined || !Number.isFinite(v) ? '?' : v.toLocaleString('en-US', { maximumFractionDigits: 2 }));
const pct = (a, b) => (Number.isFinite(a) && Number.isFinite(b) && b !== 0 ? Math.round(((a - b) / b) * 1000) / 10 : null);
const signed = (v) => (v === null ? '?' : `${v > 0 ? '+' : ''}${v}%`);
const unset = (name, what) => textResult(`${what}: Cloudflare 비밀값 ${name} 미설정 — 조회하지 않음(0건 아님). Cloudflare → Workers → seoul-reporting-radar → Settings → Variables and Secrets에 Secret으로 추가.`, true);

async function getJson(ctx, url) {
  const r = await ctx.fetch(url, { signal: signal(), headers: HEADERS });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const text = await r.text();
  try { return JSON.parse(text); } catch { throw new Error(`JSON 아님(${text.slice(0, 60).replace(/\s+/g, ' ')})`); }
}

const errText = (e) => (e?.name === 'TimeoutError' ? '시간 초과' : String(e?.message ?? e).slice(0, 120));

// Period key arithmetic for monthly (YYYYMM), quarterly (YYYYQn), annual (YYYY).
function periodBack(p, n, cycle) {
  if (cycle === 'M' && /^\d{6}$/.test(p)) {
    let y = Number(p.slice(0, 4)); let m = Number(p.slice(4)) - n;
    while (m <= 0) { y -= 1; m += 12; }
    return `${y}${String(m).padStart(2, '0')}`;
  }
  if (cycle === 'Q' && /^\d{4}Q\d$/.test(p)) {
    let y = Number(p.slice(0, 4)); let q = Number(p.slice(5)) - n;
    while (q <= 0) { y -= 1; q += 4; }
    return `${y}Q${q}`;
  }
  if (cycle === 'A' && /^\d{4}$/.test(p)) return String(Number(p) - n);
  return null;
}
const yearLag = { M: 12, Q: 4, A: 1 };

// Statements about the newest point of one series (oldest→newest), each with dates and values.
export function seriesFacts(pts, cycle) {
  if (!pts.length) return { lines: ['값 없음'] };
  const cur = pts[pts.length - 1];
  const by = new Map(pts.map((p) => [p.p, p.v]));
  const prev = pts.length > 1 ? pts[pts.length - 2] : null;
  const lag = yearLag[cycle];
  const lyKey = lag ? periodBack(cur.p, lag, cycle) : null;
  const ly = lyKey ? by.get(lyKey) : undefined;
  const lines = [`최신 ${cur.p} ${fmt(cur.v)} · 직전(${prev?.p ?? '?'}) 대비 ${signed(prev ? pct(cur.v, prev.v) : null)}${lyKey ? ` · 전년 같은 기간(${lyKey}${ly === undefined ? ', 값 없음' : `, ${fmt(ly)}`}) 대비 ${signed(ly === undefined ? null : pct(cur.v, ly))}` : ''}`];
  for (const high of [true, false]) {
    const word = high ? '최고' : '최저';
    const prior = [...pts.slice(0, -1)].reverse().find((p) => (high ? p.v >= cur.v : p.v <= cur.v));
    if (!prior) lines.push(`조회 범위(${pts[0].p}~) ${word}`);
    else if (pts.indexOf(prior) < pts.length - 2) lines.push(`${prior.p}(${fmt(prior.v)}) 이후 ${word}${prior.v === cur.v ? '(그때와 같은 값)' : ''}`);
  }
  const hi = pts.reduce((a, b) => (b.v > a.v ? b : a));
  const lo = pts.reduce((a, b) => (b.v < a.v ? b : a));
  lines.push(`조회 범위 ${pts[0].p}~${cur.p}: 최고 ${hi.p} ${fmt(hi.v)} · 최저 ${lo.p} ${fmt(lo.v)}`);
  return { lines, cur, ly };
}

const tail = (pts, n = 13) => pts.slice(-n).map((p) => `${p.p} ${fmt(p.v)}`).join(' | ');

// ---------- ECOS ----------

export async function ecosFind(ctx, args) {
  const key = ctx.env?.ECOS_API_KEY;
  if (!key) return unset('ECOS_API_KEY', '한국은행 ECOS');
  const q = String(args.query ?? '').trim();
  const stat = String(args.stat ?? '').trim().toUpperCase();
  if (!q && !stat) return textResult('query(통계표·항목 낱말) 또는 stat(통계표 코드)가 필요하다.', true);
  try {
    if (stat) {
      const body = await getJson(ctx, `${ECOS}/StatisticItemList/${encodeURIComponent(key)}/json/kr/1/5000/${encodeURIComponent(stat)}`);
      const rows = body?.StatisticItemList?.row;
      if (!rows) return textResult(`ECOS 항목 목록 응답 없음(${body?.RESULT?.CODE ?? '형식'} ${body?.RESULT?.MESSAGE ?? ''}) — 미확인`, true);
      const words = q.split(/\s+/).filter(Boolean);
      const hit = rows.filter((x) => words.every((w) => String(x.ITEM_NAME ?? '').includes(w)));
      const byCode = new Map();
      for (const x of hit) {
        const k = `${x.GRP_NAME}|${x.ITEM_CODE}`;
        const g = byCode.get(k) ?? { ...x, cycles: [] };
        g.cycles.push(`${x.CYCLE} ${x.START_TIME}~${x.END_TIME}`);
        byCode.set(k, g);
      }
      const out = [`ECOS 통계표 ${stat} 항목 "${q}" — ${byCode.size}개(전체 ${rows.length}행)`];
      for (const x of [...byCode.values()].slice(0, clampInt(args.limit, 1, 60, 25))) {
        out.push(`- ${x.GRP_NAME ? `[${x.GRP_NAME}] ` : ''}${x.ITEM_CODE} ${x.ITEM_NAME} · 단위 ${x.UNIT_NAME ?? '?'} · ${x.cycles.join(', ')}`);
      }
      out.push('다음: ecos_data(stat, item, cycle)로 값을 본다. 같은 품목 안에서만 비교(지수 기준이 품목마다 다를 수 있음).');
      return textResult(out.join('\n'));
    }
    const body = await getJson(ctx, `${ECOS}/StatisticTableList/${encodeURIComponent(key)}/json/kr/1/1000/`);
    const rows = body?.StatisticTableList?.row ?? [];
    const words = q.split(/\s+/).filter(Boolean);
    const hit = rows.filter((x) => x.SRCH_YN === 'Y' && words.every((w) => String(x.STAT_NAME ?? '').includes(w)));
    const out = [`ECOS 통계표 "${q}" — ${hit.length}개`];
    for (const x of hit.slice(0, clampInt(args.limit, 1, 60, 25))) out.push(`- ${x.STAT_CODE} ${x.STAT_NAME} (${x.CYCLE ?? '?'})`);
    if (!hit.length) out.push('없음 — 낱말을 줄이거나(예: "생산자물가") 바꿔 본다.');
    out.push('다음: ecos_find(stat=코드, query=품목 낱말)로 항목 코드를 찾는다.');
    return textResult(out.join('\n'));
  } catch (e) {
    return textResult(`ECOS 조회 실패(${errText(e)}) — 미확인`, true);
  }
}

export async function ecosData(ctx, args) {
  const key = ctx.env?.ECOS_API_KEY;
  if (!key) return unset('ECOS_API_KEY', '한국은행 ECOS');
  const stat = String(args.stat ?? '').trim().toUpperCase();
  const items = [args.item, args.item2, args.item3].map((x) => String(x ?? '').trim()).filter(Boolean);
  const cycle = ['M', 'Q', 'A'].includes(String(args.cycle ?? 'M').toUpperCase()) ? String(args.cycle ?? 'M').toUpperCase() : 'M';
  if (!stat || !items.length) return textResult('stat(통계표 코드)와 item(항목 코드)이 필요하다. 모르면 ecos_find.', true);
  const now = kstDate(ctx.now);
  const yNow = Number(now.slice(0, 4));
  const defStart = { M: `${yNow - 10}01`, Q: `${yNow - 10}Q1`, A: String(yNow - 20) }[cycle];
  const defEnd = { M: now.slice(0, 4) + now.slice(5, 7), Q: `${yNow}Q4`, A: String(yNow) }[cycle];
  const start = String(args.start ?? defStart).replace(/[-.]/g, '');
  const end = String(args.end ?? defEnd).replace(/[-.]/g, '');
  const url = `${ECOS}/StatisticSearch/${encodeURIComponent(key)}/json/kr/1/2000/${encodeURIComponent(stat)}/${cycle}/${encodeURIComponent(start)}/${encodeURIComponent(end)}/${items.map(encodeURIComponent).join('/')}`;
  let body;
  try { body = await getJson(ctx, url); } catch (e) { return textResult(`ECOS 조회 실패(${errText(e)}) — 미확인`, true); }
  const rows = body?.StatisticSearch?.row;
  if (!rows) return textResult(`ECOS 값 없음(${body?.RESULT?.CODE ?? '형식'} ${body?.RESULT?.MESSAGE ?? ''}) — 미확인(코드·주기·기간 확인)`, true);
  // one series per remaining item dimension (e.g. 원화/달러/계약통화 기준)
  const groups = new Map();
  for (const x of rows) {
    const k = [x.ITEM_NAME1, x.ITEM_NAME2, x.ITEM_NAME3, x.ITEM_NAME4].filter(Boolean).join(' · ');
    const g = groups.get(k) ?? { unit: x.UNIT_NAME, pts: [] };
    const v = Number(String(x.DATA_VALUE).replace(/,/g, ''));
    if (Number.isFinite(v)) g.pts.push({ p: String(x.TIME), v });
    groups.set(k, g);
  }
  const out = [`ECOS ${rows[0]?.STAT_NAME ?? stat} · ${cycle} · ${start}~${end}`];
  for (const [name, g] of groups) {
    g.pts.sort((a, b) => a.p.localeCompare(b.p));
    const f = seriesFacts(g.pts, cycle);
    out.push(`\n■ ${name} (단위 ${g.unit ?? '?'})`);
    for (const l of f.lines) out.push(`   ${l}`);
    out.push(`   최근: ${tail(g.pts)}`);
  }
  out.push('\n규칙: 조회 범위 안의 사실만 적었다. "역대"는 원표 전체 기간으로 다시 뜬다. 지수는 기준 시점 대비 변화이고, 기준이 다른 품목끼리 비교하지 않는다. 출처: 한국은행 경제통계시스템(ECOS).');
  return textResult(out.join('\n'));
}

// ---------- KOSIS ----------

export async function kosisFind(ctx, args) {
  const key = ctx.env?.KOSIS_API_KEY;
  if (!key) return unset('KOSIS_API_KEY', 'KOSIS 국가통계포털');
  const q = String(args.query ?? '').trim();
  if (!q) return textResult('query(통계표 낱말)가 필요하다.', true);
  const n = clampInt(args.limit, 1, 40, 15);
  try {
    const url = `${KOSIS_SEARCH}?method=getList&apiKey=${encodeURIComponent(key)}&searchNm=${encodeURIComponent(q)}&format=json&jsonVD=Y&startCount=1&resultCount=${n}&sort=RANK`;
    const body = await getJson(ctx, url);
    if (!Array.isArray(body)) return textResult(`KOSIS 검색 응답 오류(${body?.err ?? ''} ${body?.errMsg ?? '형식'}) — 미확인`, true);
    const out = [`KOSIS 통계표 "${q}" — ${body.length}개(관련도 순)`];
    for (const x of body) out.push(`- org ${x.ORG_ID} · tbl ${x.TBL_ID} · ${x.TBL_NM} [${x.ORG_NM}] ${x.STRT_PRD_DE ?? ''}~${x.END_PRD_DE ?? ''}`);
    out.push('다음: kosis_data(org, tbl)로 분류·항목 코드를 본 뒤 obj1·itm을 정해 값을 받는다.');
    return textResult(out.join('\n'));
  } catch (e) {
    return textResult(`KOSIS 검색 실패(${errText(e)}) — 미확인`, true);
  }
}

export async function kosisData(ctx, args) {
  const key = ctx.env?.KOSIS_API_KEY;
  if (!key) return unset('KOSIS_API_KEY', 'KOSIS 국가통계포털');
  const org = String(args.org ?? '').trim();
  const tbl = String(args.tbl ?? '').trim();
  if (!org || !tbl) return textResult('org(기관 ID)와 tbl(통계표 ID)이 필요하다. 모르면 kosis_find.', true);
  const obj1 = String(args.obj1 ?? '').trim();
  try {
    if (!obj1) {
      const meta = await getJson(ctx, `${KOSIS_META}?method=getMeta&apiKey=${encodeURIComponent(key)}&format=json&jsonVD=Y&type=ITM&orgId=${encodeURIComponent(org)}&tblId=${encodeURIComponent(tbl)}`);
      const prd = await getJson(ctx, `${KOSIS_META}?method=getMeta&apiKey=${encodeURIComponent(key)}&format=json&jsonVD=Y&type=PRD&orgId=${encodeURIComponent(org)}&tblId=${encodeURIComponent(tbl)}`).catch(() => null);
      if (!Array.isArray(meta)) return textResult(`KOSIS 표 정보 오류(${meta?.err ?? ''} ${meta?.errMsg ?? '형식'}) — 미확인`, true);
      const q = String(args.query ?? '').trim();
      const byObj = new Map();
      for (const x of meta) {
        const g = byObj.get(x.OBJ_ID) ?? { name: x.OBJ_NM, rows: [] };
        g.rows.push(x);
        byObj.set(x.OBJ_ID, g);
      }
      const out = [`KOSIS ${org}/${tbl} 분류·항목${Array.isArray(prd) ? ` · 수록 ${prd.map((p) => `${p.PRD_SE} ${p.STRT_PRD_DE}~${p.END_PRD_DE}`).join(', ')}` : ''}`];
      for (const [id, g] of byObj) {
        const rows = g.rows.filter((x) => !q || id === 'ITEM' || String(x.ITM_NM).includes(q));
        out.push(`\n■ ${id === 'ITEM' ? 'itm(항목)' : `obj ${id}(${g.name})`} — ${g.rows.length}개${q && id !== 'ITEM' ? `, "${q}" ${rows.length}개` : ''}`);
        for (const x of rows.slice(0, 40)) out.push(`   ${x.ITM_ID} ${x.ITM_NM}${x.UNIT_NM ? ` (${x.UNIT_NM})` : ''}`);
      }
      out.push('\n다음: kosis_data(org, tbl, obj1=첫 분류 코드, itm=항목 코드, prd=M/Q/Y)로 값을 받는다(obj2는 두 번째 분류가 있을 때).');
      return textResult(out.join('\n'));
    }
    const prd = ['M', 'Q', 'Y'].includes(String(args.prd ?? 'M').toUpperCase()) ? String(args.prd ?? 'M').toUpperCase() : 'M';
    const now = kstDate(ctx.now);
    const y = Number(now.slice(0, 4));
    const start = String(args.start ?? { M: `${y - 10}01`, Q: `${y - 10}01`, Y: String(y - 20) }[prd]).replace(/[-.]/g, '');
    const end = String(args.end ?? { M: now.slice(0, 4) + now.slice(5, 7), Q: `${y}04`, Y: String(y) }[prd]).replace(/[-.]/g, '');
    const itm = String(args.itm ?? 'ALL').trim() || 'ALL';
    const obj2 = String(args.obj2 ?? '').trim();
    const url = `${KOSIS_DATA}?method=getList&apiKey=${encodeURIComponent(key)}&itmId=${encodeURIComponent(itm)}&objL1=${encodeURIComponent(obj1)}` +
      `${obj2 ? `&objL2=${encodeURIComponent(obj2)}` : ''}&format=json&jsonVD=Y&prdSe=${prd}&startPrdDe=${start}&endPrdDe=${end}&orgId=${encodeURIComponent(org)}&tblId=${encodeURIComponent(tbl)}`;
    const body = await getJson(ctx, url);
    if (!Array.isArray(body)) return textResult(`KOSIS 값 오류(${body?.err ?? ''} ${body?.errMsg ?? '형식'}) — 미확인(코드·주기·기간 확인)`, true);
    const groups = new Map();
    for (const x of body) {
      const k = [x.C1_NM, x.C2_NM, x.C3_NM, x.ITM_NM].filter(Boolean).join(' · ');
      const g = groups.get(k) ?? { unit: x.UNIT_NM, pts: [], tbl: x.TBL_NM };
      const v = Number(String(x.DT).replace(/,/g, ''));
      const p = prd === 'Q' ? `${String(x.PRD_DE).slice(0, 4)}Q${Number(String(x.PRD_DE).slice(4)) || ''}` : String(x.PRD_DE);
      if (Number.isFinite(v)) g.pts.push({ p, v });
      groups.set(k, g);
    }
    const cycle = prd === 'Y' ? 'A' : prd;
    const out = [`KOSIS ${body[0]?.TBL_NM ?? tbl} (${org}/${tbl}) · ${prd} · ${start}~${end} · 계열 ${groups.size}개`];
    for (const [name, g] of [...groups].slice(0, 12)) {
      g.pts.sort((a, b) => a.p.localeCompare(b.p));
      const f = seriesFacts(g.pts, cycle);
      out.push(`\n■ ${name} (단위 ${g.unit ?? '?'})`);
      for (const l of f.lines) out.push(`   ${l}`);
      out.push(`   최근: ${tail(g.pts)}`);
    }
    if (groups.size > 12) out.push(`\n… 계열 ${groups.size - 12}개 더 — obj1·itm으로 좁힌다.`);
    out.push('\n규칙: 조회 범위 안의 사실만. "역대"는 수록 기간 전체로 다시 뜬다. 출처: KOSIS 국가통계포털(작성기관 표기 그대로).');
    return textResult(out.join('\n'));
  } catch (e) {
    return textResult(`KOSIS 조회 실패(${errText(e)}) — 미확인`, true);
  }
}

// ---------- 관세청 품목별·국가별 수출입실적 ----------

export function parseCustomsXml(xml) {
  const code = /<resultCode>([^<]*)<\/resultCode>/.exec(xml)?.[1];
  const msg = /<resultMsg>([^<]*)<\/resultMsg>/.exec(xml)?.[1];
  if (code && !['00', '0'].includes(code)) throw new Error(`관세청 코드 ${code} ${msg ?? ''}`.trim());
  const rows = [];
  for (const m of xml.matchAll(/<item>([\s\S]*?)<\/item>/g)) {
    const get = (t) => (new RegExp(`<${t}>([^<]*)</${t}>`).exec(m[1])?.[1] ?? '').trim();
    rows.push({ year: get('year'), hs: get('hsCd'), name: get('statKor'), expDlr: get('expDlr'), expWgt: get('expWgt'), impDlr: get('impDlr'), impWgt: get('impWgt') });
  }
  if (!code && !rows.length) throw new Error('응답 형식(resultCode·item 없음)');
  return rows;
}

function monthAdd(yyyymm, n) {
  let y = Number(yyyymm.slice(0, 4)); let m = Number(yyyymm.slice(4)) + n;
  while (m > 12) { y += 1; m -= 12; }
  while (m <= 0) { y -= 1; m += 12; }
  return `${y}${String(m).padStart(2, '0')}`;
}

export async function customsTrade(ctx, args) {
  const key = ctx.env?.CUSTOMS_API_KEY || ctx.env?.DATA_GO_KR_KEY || ctx.env?.G2B_API_KEY;
  if (!key) return unset('CUSTOMS_API_KEY(또는 DATA_GO_KR_KEY)', '관세청 수출입실적');
  let hs = String(args.hs ?? '').trim();
  if (hs && !/^\d{2,10}$/.test(hs)) {
    const hit = Object.entries(HS_HINTS).find(([k]) => hs.includes(k));
    if (!hit) return textResult(`HS 코드(숫자 2~10자리)나 다음 낱말 중 하나: ${Object.keys(HS_HINTS).join(', ')}. 정확한 범위는 무역통계(tradedata.go.kr)에서 확인.`, true);
    hs = hit[1];
  }
  if (!hs) return textResult(`hs가 필요하다. 예: 8504(변압기), 8544(전선), 8703(승용차), 7208(열연). 낱말도 된다: ${Object.keys(HS_HINTS).slice(0, 12).join(', ')} …`, true);
  const country = String(args.country ?? '').trim().toUpperCase();
  const now = kstDate(ctx.now);
  const lastMonth = monthAdd(now.slice(0, 4) + now.slice(5, 7), -1);
  const end = String(args.end ?? lastMonth).replace(/[-.]/g, '');
  const start = String(args.start ?? monthAdd(end, -36)).replace(/[-.]/g, '');
  if (!/^\d{6}$/.test(start) || !/^\d{6}$/.test(end) || start > end) return textResult('start·end는 YYYYMM, start ≤ end.', true);
  const by = new Map();
  let s = start; let calls = 0;
  try {
    while (s <= end && calls < 6) {  // the API answers at most one year per call
      const e = monthAdd(s, 11) < end ? monthAdd(s, 11) : end;
      const url = `${CUSTOMS}?serviceKey=${encodeURIComponent(key)}&strtYymm=${s}&endYymm=${e}&hsSgn=${hs}${country ? `&cntyCd=${encodeURIComponent(country)}` : ''}`;
      const r = await ctx.fetch(url, { signal: signal(), headers: HEADERS });
      calls += 1;
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      for (const x of parseCustomsXml(await r.text())) {
        if (/총|합계/.test(x.year)) continue;
        const p = x.year.replace(/[^\d]/g, '').slice(0, 6);
        if (!/^\d{6}$/.test(p)) continue;
        const g = by.get(p) ?? { exp: 0, expW: 0, imp: 0, impW: 0 };
        g.exp += Number(x.expDlr) || 0; g.expW += Number(x.expWgt) || 0; g.imp += Number(x.impDlr) || 0; g.impW += Number(x.impWgt) || 0;
        by.set(p, g);
      }
      s = monthAdd(e, 1);
    }
  } catch (e) {
    return textResult(`관세청 수출입실적 조회 실패(${errText(e)}) — 미확인. 공공데이터포털에서 '관세청_품목별 국가별 수출입실적' 활용신청이 된 키인지 확인.`, true);
  }
  if (!by.size) return textResult(`관세청: HS ${hs} ${country || '전체 국가'} ${start}~${end} 값 없음 — 미확인(코드·기간 확인, 0건으로 쓰지 않음)`, true);
  const months = [...by.keys()].sort();
  const series = (k) => months.map((p) => ({ p, v: by.get(p)[k] }));
  const out = [`관세청 품목별·국가별 수출입실적 · HS ${hs} · ${country || '전체 국가'} · ${months[0]}~${months.at(-1)} (금액 USD, 중량 kg)`];
  for (const [label, k] of [['수출금액', 'exp'], ['수입금액', 'imp']]) {
    const pts = series(k);
    const f = seriesFacts(pts, 'M');
    out.push(`\n■ ${label}`);
    for (const l of f.lines) out.push(`   ${l}`);
  }
  const last = by.get(months.at(-1));
  const lyKey = periodBack(months.at(-1), 12, 'M');
  const ly = by.get(lyKey);
  const unit = (d, w) => (w > 0 ? d / w : null);
  out.push(`\n■ 수출 단가(USD/kg): ${months.at(-1)} ${fmt(unit(last.exp, last.expW))}${ly ? ` · ${lyKey} ${fmt(unit(ly.exp, ly.expW))}(${signed(pct(unit(last.exp, last.expW), unit(ly.exp, ly.expW)))})` : ''}`);
  out.push('\n월별(수출 / 수입, 만 달러):');
  for (const p of months.slice(-13)) out.push(`   ${p} ${fmt(by.get(p).exp / 1e4)} / ${fmt(by.get(p).imp / 1e4)}`);
  out.push('\n규칙: HS 단위 통관 통계다. 회사 실적·산업부 품목군 숫자와 섞지 않는다. 최신 달은 확정치 갱신 전일 수 있다. 출처: 관세청 수출입무역통계(공공데이터포털).');
  return textResult(out.join('\n'));
}
