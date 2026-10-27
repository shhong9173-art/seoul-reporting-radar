// radar_today: one private digest over the seven private watches. It reads what the collectors already stored
// (no new fetching), keeps what is new since a cutoff, and ranks it. Failed or stale watches are listed first:
// their silence is "미확인", not "nothing new".
import { readFeed } from './screen.mjs';
import { storeOp } from './store.mjs';
import { dispatchHealth } from './dispatch.mjs';
import { clampInt, textResult } from './common.mjs';

const KST_MS = 9 * 3600000;
const kstDate = (ms) => new Date(ms + KST_MS).toISOString().slice(0, 10);
const kstStamp = (v) => { const t = Date.parse(v); return Number.isFinite(t) ? new Date(t + KST_MS).toISOString().slice(5, 16).replace('T', ' ') : String(v ?? '').slice(0, 16); };
// EDGAR hits count as direct changes only when the excerpt reads like a deal with the beat company.
const DEAL_WORDS = /\b(agreement|supply|offtake|off-take|joint venture|\bJV\b|memorandum|MOU|partnership|collaborat\w*|acquisition|acquire[sd]?|merger|purchase order|contract\w*|guarantee\w*|licen[cs]e|investment in|strategic|customer|order[s]? from)\b/i;
const has = (q, ...fields) => !q || fields.some((f) => String(f ?? '').toLowerCase().includes(q.toLowerCase()));

const WATCHES = [
  { feed: 'scoop-screen', label: '단독 후보 심사', tool: 'scoop_screen', schedule: '평일 07:10·15:10' },
  { feed: 'kr-official', label: '공장등록·관보', tool: 'kr_official', schedule: '평일 08:10' },
  { feed: 'trade-remedy', label: '무역구제', tool: 'trade_remedies', schedule: '평일 07:40' },
  { feed: 'us-litigation', label: '미국 소송·ITC', tool: 'us_litigation', schedule: '평일 07:50' },
  { feed: 'partner-filings', label: '해외 파트너 공시', tool: 'partner_filings', schedule: '평일 07:00' },
  { feed: 'us-comments', label: '미 연방 의견서', tool: 'us_comments', schedule: '평일 08:20' },
  { feed: 'page-watch', label: '해외 공식 페이지', tool: 'page_changes', schedule: '평일 06:30·18:30' },
];

// Items first seen in a watch's very first run are a baseline, not news: they only count when their own date is recent.
function baselineOf(rows, key = 'firstSeen') {
  const times = rows.map((x) => Date.parse(x[key])).filter(Number.isFinite);
  return times.length ? Math.min(...times) : null;
}

function isFresh(x, cut, cutDay, base, dateKey) {
  const seen = Date.parse(x.firstSeen);
  const own = String(x[dateKey] ?? '').slice(0, 10);
  if (own && own >= cutDay) return true;
  return Number.isFinite(seen) && seen >= cut && !(base !== null && Math.abs(seen - base) < 120000);
}

function collect(docs, cut, cutDay) {
  const items = [];
  const push = (tier, w, x) => items.push({ tier, watch: w.label, tool: w.tool, ...x });
  const W = Object.fromEntries(WATCHES.map((w) => [w.feed, w]));

  const scoop = docs['scoop-screen'];
  for (const c of scoop?.candidates ?? []) {
    const fl = c.filing;
    const brief = fl && !fl.error && (fl.facts ?? []).length ? ` · ${fl.facts.slice(0, 4).map(([k, v]) => `${k} ${v}`).join(' · ')}` : '';
    const cmp = fl && (fl.compare ?? []).length ? ` · ${fl.compare[0]}` : '';
    if (c.verdict === '미보도 후보' && fl?.routine) push('B', W['scoop-screen'], { id: c.id, date: c.published ?? c.filedOn, company: c.company, fact: `${c.title} — 일상 공시로 보임(${fl.routine})${brief}`, url: c.url });
    else if (c.verdict === '미보도 후보') push('A', W['scoop-screen'], { id: c.id, date: c.published ?? c.filedOn, company: c.company, fact: `${c.title} (${c.kind ?? ''}) — 보도 대조 '미보도 후보'${brief}${cmp}`, url: c.url });
    else if (c.verdict === '미확인') push('B', W['scoop-screen'], { id: c.id, date: c.published ?? c.filedOn, company: c.company, fact: `${c.title} — 보도 대조 미확인(채널 실패)`, url: c.url });
    else push('C', W['scoop-screen'], { id: c.id, company: c.company, fact: `${c.verdict}: ${c.title}` });
  }

  const kr = docs['kr-official'];
  for (const e of kr?.events ?? []) {
    if (Date.parse(e.detectedAt) < cut) continue;
    push(e.kind === '목록에서 빠짐' ? 'B' : 'A', W['kr-official'], { id: e.id, date: e.detectedAt, company: e.company, fact: `${e.kind}: ${e.text}` });
  }
  const evFactories = new Set((kr?.events ?? []).filter((e) => Date.parse(e.detectedAt) >= cut).map((e) => e.factoryId));
  for (const f of kr?.factories ?? []) {
    if (f.registeredOn && f.registeredOn >= cutDay && !evFactories.has(f.id)) push('A', W['kr-official'], { id: f.id, date: f.registeredOn, company: f.company, fact: `공장 등록 ${f.cmpnyNm} · ${f.rnAdres} · 주생산품 ${f.mainProductCn || '미기재'} · 업종 ${f.indutyNm || '미기재'} · 고용 ${f.employees ?? '?'}명${f.nameCheck ? ` (⚠ ${f.nameCheck})` : ''}` });
  }
  const gzBase = baselineOf(kr?.gazette ?? []);
  for (const g of kr?.gazette ?? []) {
    if (isFresh(g, cut, cutDay, gzBase, 'date')) push('B', W['kr-official'], { id: g.id, date: g.date, company: (g.teams ?? []).join('·'), fact: `관보 입법예고 ${g.org}: ${g.title}`, url: g.url });
  }

  const tr = docs['trade-remedy'];
  for (const e of tr?.events ?? []) {
    if (Date.parse(e.detectedAt) < cut) continue;
    push(e.pageId === 'taric' && /한국 전용/.test(e.label) ? 'A' : 'B', W['trade-remedy'], { id: e.id, date: e.detectedAt, company: e.country, fact: `${e.label}: ${e.text}`, url: e.url });
  }
  const frBase = baselineOf(tr?.federalRegister ?? []);
  for (const x of tr?.federalRegister ?? []) {
    if (!isFresh(x, cut, cutDay, frBase, 'date')) continue;
    const names = (x.named ?? []).map((n) => n.company);
    push(names.length ? 'B' : 'C', W['trade-remedy'], { id: x.id, date: x.date, company: names.join('·'), fact: `미국 관보 ${x.stage}: ${x.title}${names.length ? ` — 본문에 ${names.join('·')}` : ''}`, url: x.url });
  }

  const lit = docs['us-litigation'];
  const litBase = baselineOf(lit?.cases ?? []);
  for (const x of lit?.cases ?? []) {
    if (!isFresh(x, cut, cutDay, litBase, 'dateFiled')) continue;
    const tier = x.priority <= 1 ? 'A' : x.priority === 2 ? 'B' : 'C';
    push(tier, W['us-litigation'], { id: x.id, date: x.dateFiled, company: (x.beat ?? []).join('·'), fact: `${x.category} · ${x.role}: ${x.court ?? x.courtId} 「${x.caseName}」 접수`, url: x.url });
  }
  const itcBase = baselineOf(lit?.itc ?? []);
  for (const x of lit?.itc ?? []) {
    if (isFresh(x, cut, cutDay, itcBase, 'date')) push('A', W['us-litigation'], { id: x.id, date: x.date, company: (x.named ?? []).map((n) => n.company).join('·'), fact: `ITC 337조 ${x.stage}: ${x.title}`, url: x.url });
  }

  const pf = docs['partner-filings'];
  const pfBase = baselineOf(pf?.items ?? []);
  for (const x of pf?.items ?? []) {
    if (!isFresh(x, cut, cutDay, pfBase, 'date')) continue;
    let tier;
    if (x.source === 'ASX') tier = (x.flags ?? []).length ? 'A' : 'C';
    else tier = DEAL_WORDS.test(String(x.snippet ?? '')) ? 'A' : 'B';
    const deal = x.source !== 'ASX' && tier === 'B' ? ' — 발췌에 계약·공급·합작 낱말 없음(이름만 언급일 수 있음)' : '';
    push(tier, W['partner-filings'], { id: x.id, date: x.date, company: (x.beat ?? []).join('·'), fact: `${x.source} ${x.filer}: ${x.title}${(x.flags ?? []).length ? ` (낱말 ${x.flags.join(',')})` : ''}${deal}`, url: x.url });
  }

  const uc = docs['us-comments'];
  const ucBase = baselineOf(uc?.items ?? []);
  for (const x of uc?.items ?? []) {
    if (isFresh(x, cut, cutDay, ucBase, 'postedDate')) push('B', W['us-comments'], { id: x.id, date: x.postedDate, company: x.company, fact: `${x.submitter} → ${x.agency} 의견서${x.docketTitle ? ` 「${x.docketTitle}」` : ''}`, url: x.url });
  }

  const pw = docs['page-watch'];
  for (const e of pw?.events ?? []) {
    if (Date.parse(e.detectedAt) < cut) continue;
    const added = Object.values(e.added ?? {}).flat().slice(0, 3).join(' / ');
    push(e.scope === 'page' ? 'A' : 'C', W['page-watch'], { id: `${e.pageId}:${e.detectedAt}`, date: e.detectedAt, company: e.company, fact: `${e.label ?? e.pageId}${e.scope === 'site' ? ' [사이트 공통]' : ''} 문구 변화${added ? `: + ${added}` : ''}`, url: e.url });
  }
  return items;
}

function health(ctx, docs) {
  const lines = [];
  for (const w of WATCHES) {
    const d = docs[w.feed];
    if (!d) { lines.push(`- ${w.label}: 결과 없음 — 미확인(${w.schedule} 실행 확인)`); continue; }
    if (d.broken) { lines.push(`- ${w.label}: 저장 형식 오류 — 미확인`); continue; }
    const ageH = (ctx.now.getTime() - Date.parse(d.generatedAt)) / 3600000;
    const failed = (d.checks ?? []).filter((c) => c.status && c.status !== 'ok' && !String(c.source ?? '').startsWith('공장등록 이름 규칙'));
    const issues = [];
    if (Number.isFinite(ageH) && ageH > 36) issues.push(`⚠ ${Math.round(ageH)}시간 전 결과`);
    if (failed.length) issues.push(`일부 실패 ${failed.length}건(${failed.slice(0, 3).map((c) => c.source ?? c.company ?? c.target).join(', ')})`);
    if (issues.length) lines.push(`- ${w.label}: ${issues.join(' · ')} — 해당 부분 0건은 미확인`);
  }
  return lines;
}

export async function radarToday(ctx, args) {
  const nowMs = ctx.now.getTime();
  const monday = new Date(nowMs + KST_MS).getUTCDay() === 1;
  const hours = clampInt(args.hours, 1, 336, monday ? 72 : 24);
  const cut = nowMs - hours * 3600000;
  const cutDay = kstDate(cut);
  const q = String(args.company ?? '').trim();
  const limit = clampInt(args.limit, 1, 60, 15);
  const showC = args.include_minor === true || args.include_minor === 'true';
  const docs = Object.fromEntries(await Promise.all(WATCHES.map(async (w) => [w.feed, await readFeed(ctx, w.feed)])));
  const { rows: fb } = await storeOp(ctx, 'feedback.latest', {});
  const judged = new Map(fb.map((r) => [r.item_id, r.verdict]));
  const showJudged = args.include_judged === true || args.include_judged === 'true';
  const found = collect(docs, cut, cutDay).filter((x) => has(q, x.company, x.fact, x.watch));
  const hiddenBy = {};
  const all = found.filter((x) => {
    const v = judged.get(x.id);
    if (!v || showJudged) return true;
    hiddenBy[v] = (hiddenBy[v] ?? 0) + 1;
    return false;
  });
  const byTier = (t) => all.filter((x) => x.tier === t).sort((a, b) => String(b.date ?? '').localeCompare(String(a.date ?? '')));

  const out = [`오늘의 레이더 · ${kstStamp(ctx.now.toISOString())} KST 기준 최근 ${hours}시간${monday && !args.hours ? '(월요일: 주말 포함)' : ''} · 기자 전용 감시 ${WATCHES.length}개`];
  const h = health(ctx, docs);
  const dh = await dispatchHealth(ctx);
  if (dh) h.unshift(`- ${dh}`);
  out.push(h.length ? `\n[먼저 볼 것: 수집 상태]\n${h.join('\n')}` : '\n[수집 상태] 7개 감시 모두 최근 정상');
  const tiers = [['A', '단독 후보·직접 변화 — 원문·보도 대조부터'], ['B', '확인할 공식 변화'], ['C', '참고(접힘)']];
  for (const [t, title] of tiers) {
    const rows = byTier(t);
    if (t === 'C' && !showC) {
      if (rows.length) out.push(`\n[C · ${title}] ${rows.length}건 — 소비자 소송·사이트 공통 문구·기보도 후보 등 (include_minor=true)`);
      continue;
    }
    out.push(`\n[${t} · ${title}] ${rows.length}건`);
    for (const x of rows.slice(0, limit)) {
      out.push(`- ${x.date ? `${String(x.date).length > 10 ? kstStamp(x.date) : x.date} · ` : ''}${x.watch}${x.company ? ` · ${x.company}` : ''}`);
      out.push(`   ${x.fact}`);
      out.push(`   ${x.url ? `원문: ${x.url} · ` : ''}자세히: ${x.tool} · id ${x.id}${judged.get(x.id) ? ` 〔판정: ${judged.get(x.id)}〕` : ''}`);
    }
    if (rows.length > limit) out.push(`… 남은 ${rows.length - limit}건(limit 또는 company로 좁히기)`);
    if (!rows.length) out.push('없음');
  }
  const hiddenN = Object.values(hiddenBy).reduce((a, b) => a + b, 0);
  if (hiddenN) out.push(`\n(판정한 ${hiddenN}건 숨김: ${Object.entries(hiddenBy).map(([v, n]) => `${v} ${n}`).join(' · ')} — include_judged=true로 보기)`);
  out.push('정리: 다 본 항목은 candidate_feedback(verdict=봤음, item_ids=[…])로 표시하면 다음부터 안 뜬다.');
  out.push('\n규칙: 모두 자동 수집 단계다. A도 단독 확정이 아니다 — 원문 확인 → news_check(낱말 바꿔 2~3번) → 회사 확인 → candidate_check. 첫 실행에 잡힌 기존 항목은 자기 날짜가 최근일 때만 새 항목으로 센다.');
  return textResult(out.join('\n'));
}
