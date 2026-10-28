// radar_today: one private digest over the eleven private watches. It reads what the collectors already stored
// (no new fetching), keeps what is new since a cutoff, and ranks it. Failed or stale watches are listed first:
// their silence is "미확인", not "nothing new".
import { readFeed } from './screen.mjs';
import { storeOp } from './store.mjs';
import { dispatchHealth } from './dispatch.mjs';
import { clampInt, textResult } from './common.mjs';
import { classLabel, waitReason } from './trademarks.mjs';
import { billLine, groupBillEvents } from './assembly.mjs';

const KST_MS = 9 * 3600000;
const kstDate = (ms) => new Date(ms + KST_MS).toISOString().slice(0, 10);
const kstStamp = (v) => { const t = Date.parse(v); return Number.isFinite(t) ? new Date(t + KST_MS).toISOString().slice(5, 16).replace('T', ' ') : String(v ?? '').slice(0, 16); };
// EDGAR hits count as direct changes only when the excerpt reads like a deal with the beat company.
const DEAL_WORDS = /\b(agreement|supply|offtake|off-take|joint venture|\bJV\b|memorandum|MOU|partnership|collaborat\w*|acquisition|acquire[sd]?|merger|purchase order|contract\w*|guarantee\w*|licen[cs]e|investment in|strategic|customer|order[s]? from)\b/i;
const ymd8 = (v) => (/^\d{8}/.test(String(v ?? '')) ? `${String(v).slice(0, 4)}-${String(v).slice(4, 6)}-${String(v).slice(6, 8)}` : String(v ?? '').slice(0, 10));
const has = (q, ...fields) => !q || fields.some((f) => String(f ?? '').toLowerCase().includes(q.toLowerCase()));

export const WATCHES = [
  { feed: 'scoop-screen', label: '단독 후보 심사', tool: 'scoop_screen', schedule: '평일 07:10·15:10' },
  { feed: 'kr-official', label: '공장등록·관보', tool: 'kr_official', schedule: '평일 08:10' },
  { feed: 'kr-signals', label: '공정위·한전·원자재', tool: 'kr_signals', schedule: '평일 08:30·15:20' },
  { feed: 'kr-stats', label: '월간 통계(물가·생산·수입차)', tool: 'kr_stats', schedule: '평일 07:30' },
  { feed: 'trade-remedy', label: '무역구제', tool: 'trade_remedies', schedule: '평일 07:40' },
  { feed: 'us-litigation', label: '미국 소송·ITC', tool: 'us_litigation', schedule: '평일 07:50' },
  { feed: 'partner-filings', label: '해외 파트너 공시', tool: 'partner_filings', schedule: '평일 07:00' },
  { feed: 'us-comments', label: '미 연방 의견서', tool: 'us_comments', schedule: '평일 08:20' },
  { feed: 'page-watch', label: '해외 공식 페이지', tool: 'page_changes', schedule: '평일 06:30·18:30' },
  { feed: 'trademarks', label: '상표 출원', tool: 'trademarks', schedule: '월 07:10', staleHours: 192 },
  { feed: 'assembly-bills', label: '국회 법안', tool: 'assembly_bills', schedule: '평일 08:40·17:40' },
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

// DART report name as filed, without '[기재정정]' style prefixes — the review groups unsupported types by it.
const reportOf = (title) => String(title ?? '').split(' · ').pop().replace(/^\s*\[[^\]]*\]\s*/, '').trim().slice(0, 30);

function scoopKind(c) {
  if (c.filing?.type) return `DART ${c.filing.type}`;
  if (c.kind === '단서' && /dart\.fss\.or\.kr/.test(String(c.url ?? ''))) return `DART ${reportOf(c.title) || '기타'}`;
  if (c.kind === '단서') return `단서${c.source ? ` ${String(c.source).slice(0, 20)}` : ''}`;
  return c.kind ?? '기타';
}

// all=true: every stored item regardless of date (used to label judgments), same tiers as the digest.
function collect(docs, cut, cutDay, { all = false, now = Date.now() } = {}) {
  const items = [];
  const push = (tier, w, x) => items.push({ tier, watch: w.label, tool: w.tool, ...x });
  const W = Object.fromEntries(WATCHES.map((w) => [w.feed, w]));
  const fresh = (x, base, key) => all || isFresh(x, cut, cutDay, base, key);
  const recent = (at) => all || !(Date.parse(at) < cut);  // same as before: an unreadable date is not dropped

  const scoop = docs['scoop-screen'];
  for (const c of scoop?.candidates ?? []) {
    const fl = c.filing;
    // one line per item: long cells (판결 주문, 당사자 목록) are clipped here; scoop_screen shows them in full
    const clip = (v) => { const t = String(v ?? '').replace(/\s+/g, ' ').trim(); return t.length > 60 ? `${t.slice(0, 60).trimEnd()}…` : t; };
    const brief = fl && !fl.error && (fl.facts ?? []).length ? ` · ${fl.facts.slice(0, 4).map(([k, v]) => `${k} ${clip(v)}`).join(' · ')}` : '';
    const cmp = fl && (fl.compare ?? []).length ? ` · ${fl.compare[0]}` : '';
    const kind = scoopKind(c);
    const flag = fl?.routine ? '일상' : '';
    if (c.verdict === '미보도 후보' && fl?.routine) push('B', W['scoop-screen'], { kind, flag, id: c.id, date: c.published ?? c.filedOn, company: c.company, fact: `${c.title} — 일상 공시로 보임(${fl.routine})${brief}`, url: c.url });
    else if (c.verdict === '미보도 후보') push('A', W['scoop-screen'], { kind, id: c.id, date: c.published ?? c.filedOn, company: c.company, fact: `${c.title} (${c.kind ?? ''}) — 보도 대조 '미보도 후보'${brief}${cmp}`, url: c.url });
    else if (c.verdict === '미확인') push('B', W['scoop-screen'], { kind, id: c.id, date: c.published ?? c.filedOn, company: c.company, fact: `${c.title} — 보도 대조 미확인(채널 실패)`, url: c.url });
    else push('C', W['scoop-screen'], { kind, id: c.id, company: c.company, fact: `${c.verdict}: ${c.title}` });
  }

  const kr = docs['kr-official'];
  for (const e of kr?.events ?? []) {
    if (!recent(e.detectedAt)) continue;
    push(e.kind === '목록에서 빠짐' ? 'B' : 'A', W['kr-official'], { kind: `공장 ${e.kind}`, id: e.id, date: e.detectedAt, company: e.company, fact: `${e.kind}: ${e.text}` });
  }
  const evFactories = all ? new Set() : new Set((kr?.events ?? []).filter((e) => Date.parse(e.detectedAt) >= cut).map((e) => e.factoryId));
  for (const f of kr?.factories ?? []) {
    if (f.registeredOn && (all || f.registeredOn >= cutDay) && !evFactories.has(f.id)) push('A', W['kr-official'], { kind: '공장 새 등록', id: f.id, date: f.registeredOn, company: f.company, fact: `공장 등록 ${f.cmpnyNm} · ${f.rnAdres} · 주생산품 ${f.mainProductCn || '미기재'} · 업종 ${f.indutyNm || '미기재'} · 고용 ${f.employees ?? '?'}명${f.nameCheck ? ` (⚠ ${f.nameCheck})` : ''}` });
  }
  const gzBase = baselineOf(kr?.gazette ?? []);
  for (const g of kr?.gazette ?? []) {
    if (fresh(g, gzBase, 'date')) push('B', W['kr-official'], { kind: '관보 입법예고', id: g.id, date: g.date, company: (g.teams ?? []).join('·'), fact: `관보 입법예고 ${g.org}: ${g.title}`, url: g.url });
  }

  const ks = docs['kr-signals'];
  const ksBase = baselineOf(ks?.decisions ?? []);
  for (const d of ks?.decisions ?? []) {
    const fd = String(d.fileDate ?? '').slice(0, 10);  // file registration = when the decision went up
    if (!(all || (fd ? fd >= cutDay : isFresh(d, cut, cutDay, ksBase, 'decidedOn')))) continue;
    const ms = d.mentions ?? [];
    const direct = ms.filter((m) => !m.related);
    const named = direct.filter((m) => m.role !== '본문 언급');
    const installment = (d.flags ?? []).some((f) => f.startsWith('과징금 납부기한'));
    const tier = direct.some((m) => m.role === '피심인') || (installment && named.length) ? 'A' : named.length ? 'B' : 'C';
    const lead = direct.find((m) => m.role === '피심인') ?? named[0] ?? ms[0];
    push(tier, W['kr-signals'], { kind: `공정위 ${lead?.role ?? '언급'}`, id: d.id, date: fd || d.decidedOn, company: [...new Set(ms.map((m) => m.company))].join('·'),
      fact: `공정위 의결서(${d.action}${(d.flags ?? []).length ? ` · ${d.flags.join('·')}` : ''}, 의결 ${d.decidedOn}): ${d.name} — ${ms.map((m) => `${m.company} ${m.role}`).join(', ')}`, url: d.url });
  }
  // one line per tender: lots of the same notice ('…-01(일반)', '…-02(일반)') are grouped
  const lots = new Map();
  for (const x of ks?.kepco ?? []) {
    const nd = ymd8(x.noticeDate);
    if (!(all || nd >= cutDay)) continue;
    if (!all && !x.big && !((x.price ?? 0) >= 1e9)) continue;  // small lots stay in kr_signals only
    const key = `${x.company}|${nd}|${String(x.name).replace(/-\d{1,2}(\([^)]*\))?\s*$/, '')}`;
    const g = lots.get(key);
    if (g) { g.n += 1; g.sum += x.price ?? 0; g.big = g.big || x.big; } else lots.set(key, { x, nd, n: 1, sum: x.price ?? 0, big: x.big });
  }
  for (const { x, nd, n, sum, big } of lots.values()) {
    const won = (v) => `약 ${Math.round(v / 1e8).toLocaleString('en-US')}억원`;
    push(big ? 'B' : 'C', W['kr-signals'], { kind: '한전 입찰', id: x.id, date: nd, company: x.company,
      fact: `한전 전자입찰 ${x.company} 「${x.name}」${n > 1 ? ` 외 같은 공고 ${n - 1}건(합계 ${won(sum)})` : ''} · 추정가격 ${x.price ? won(x.price) : '미기재'} · ${x.state}` });
  }
  for (const x of ks?.motir ?? []) {
    if (!(all || String(x.date ?? '') >= cutDay)) continue;
    const t = x.trade;
    const strong = (x.companies ?? []).length || /무역위|덤핑|상계|세이프가드/.test(x.title ?? '') || t;
    const tradeLine = t?.items ? ` — ${t.period} 수출${t.exports ? ` ${t.exports.value}억달러(${t.exports.yoy}%)` : ''} · ${Object.entries(t.items).slice(0, 6).map(([k, v]) => `${k} ${v.value}억달러(${v.yoy}%)`).join(' · ')}` : '';
    push(strong ? 'B' : 'C', W['kr-signals'], { kind: '산업부 발표', id: x.id, date: x.date, company: (x.companies ?? []).join('·') || x.dept,
      fact: `산업통상부 ${x.kind}: ${x.title}${x.embargo ? ` (엠바고: ${x.embargo})` : ''}${tradeLine}`, url: x.url });
  }
  for (const e of ks?.events ?? []) {
    if (!recent(e.detectedAt)) continue;
    const tier = e.kind === '원자재 가격' ? (/최고|최저/.test(e.signal ?? '') ? 'B' : 'C') : 'B';
    push(tier, W['kr-signals'], { kind: e.kind === '원자재 가격' ? `원자재 ${e.signal}` : e.kind, id: e.id, date: e.detectedAt, company: e.company, fact: `${e.kind}: ${e.text}` });
  }

  for (const e of docs['kr-stats']?.events ?? []) {
    if (!recent(e.detectedAt)) continue;
    const record = /최고|최저/.test(e.signal ?? '');
    const tier = e.kind === '수입차 등록' ? (e.top ? 'B' : 'C') : record ? 'B' : 'C';
    push(tier, W['kr-stats'], { kind: `${e.kind === '수입차 등록' ? '수입차' : '통계'} ${e.signal}`, id: e.id, date: e.detectedAt, company: e.company, fact: `${e.kind}: ${e.text}` });
  }

  const tr = docs['trade-remedy'];
  for (const e of tr?.events ?? []) {
    if (!recent(e.detectedAt)) continue;
    push(e.pageId === 'taric' && /한국 전용/.test(e.label) ? 'A' : 'B', W['trade-remedy'], { kind: e.pageId === 'taric' ? 'EU 쿼터(TARIC)' : `해외 조사 ${e.pageId}`, id: e.id, date: e.detectedAt, company: e.country, fact: `${e.label}: ${e.text}`, url: e.url });
  }
  const frBase = baselineOf(tr?.federalRegister ?? []);
  for (const x of tr?.federalRegister ?? []) {
    if (!fresh(x, frBase, 'date')) continue;
    const names = (x.named ?? []).map((n) => n.company);
    push(names.length ? 'B' : 'C', W['trade-remedy'], { kind: '미국 관보', id: x.id, date: x.date, company: names.join('·'), fact: `미국 관보 ${x.stage}: ${x.title}${names.length ? ` — 본문에 ${names.join('·')}` : ''}`, url: x.url });
  }

  const lit = docs['us-litigation'];
  const litBase = baselineOf(lit?.cases ?? []);
  for (const x of lit?.cases ?? []) {
    if (!fresh(x, litBase, 'dateFiled')) continue;
    const tier = x.priority <= 1 ? 'A' : x.priority === 2 ? 'B' : 'C';
    const what = x.summary ? `${x.summary} 「${x.caseName}」` : `${x.category} · ${x.role}: ${x.court ?? x.courtId} 「${x.caseName}」 접수`;
    push(tier, W['us-litigation'], { kind: x.category ?? '소송', id: x.id, date: x.dateFiled, company: (x.beat ?? []).join('·'), fact: what, url: x.url });
  }
  // Rulings of the trade court / Federal Circuit in a beat party's case are the news itself (POSCO CIT 10-27 → [단독] 10-28).
  const opBase = baselineOf(lit?.opinions ?? []);
  for (const x of lit?.opinions ?? []) {
    if (!fresh(x, opBase, 'dateFiled')) continue;
    const h = x.holding ? ` — 요지(원문) "${x.holding.length > 140 ? `${x.holding.slice(0, 140).trimEnd()}…` : x.holding}"${x.holdingKo ? ` (풀이: ${x.holdingKo})` : ''}` : ' — 요지 미추출(판결문 확인)';
    push('A', W['us-litigation'], { kind: '미국 법원 판결', id: x.id, date: x.dateFiled, company: (x.beat ?? []).join('·'),
      fact: `${x.courtId === 'cit' ? '국제무역법원' : '연방순회항소법원'} 판결 「${x.caseName}」(${(x.beat ?? []).join('·')} ${x.role})${h}${x.reading ? ` · ${x.reading}` : ''}`, url: x.url });
  }
  const itcBase = baselineOf(lit?.itc ?? []);
  for (const x of lit?.itc ?? []) {
    if (fresh(x, itcBase, 'date')) push('A', W['us-litigation'], { kind: 'ITC 337조', id: x.id, date: x.date, company: (x.named ?? []).map((n) => n.company).join('·'), fact: `ITC 337조 ${x.stage}: ${x.title}`, url: x.url });
  }

  const pf = docs['partner-filings'];
  const pfBase = baselineOf(pf?.items ?? []);
  for (const x of pf?.items ?? []) {
    if (!fresh(x, pfBase, 'date')) continue;
    let tier;
    if (x.source === 'ASX') tier = (x.flags ?? []).length ? 'A' : 'C';
    else if (x.routine) tier = 'C';
    else tier = DEAL_WORDS.test(String(x.snippet ?? '')) && !x.finNote ? 'A' : 'B';
    const deal = x.source === 'ASX' ? '' : x.routine ? ` — ${x.routine}` : x.finNote ? ` — ${x.finNote}`
      : tier === 'B' ? ' — 발췌에 계약·공급·합작 낱말 없음(이름만 언급일 수 있음)' : '';
    push(tier, W['partner-filings'], { kind: x.source ?? '공시', id: x.id, date: x.date, company: (x.beat ?? []).join('·'), fact: `${x.source} ${x.filer}: ${x.title}${(x.flags ?? []).length ? ` (낱말 ${x.flags.join(',')})` : ''}${deal}`, url: x.url });
  }

  const uc = docs['us-comments'];
  const ucBase = baselineOf(uc?.items ?? []);
  for (const x of uc?.items ?? []) {
    if (fresh(x, ucBase, 'postedDate')) push('B', W['us-comments'], { kind: `의견서${x.agency ? ` ${x.agency}` : ''}`, id: x.id, date: x.postedDate, company: x.company, fact: `${x.submitter} → ${x.agency} 의견서${x.docketTitle ? ` 「${x.docketTitle}」` : ''}`, url: x.url });
  }

  // Weekly feed: a new filing stays on the digest for 7 days from first sighting (or until judged).
  for (const f of docs.trademarks?.filings ?? []) {
    if (!f.isNew) continue;
    const at = f.addedClassesAt ?? f.firstSeen;
    if (!all && !(Date.parse(at) >= Math.min(cut, now - 7 * 86400000))) continue;
    const classes = (f.classes ?? []).map(classLabel).join(', ');
    push(f.tier === 'B' ? 'B' : 'C', W.trademarks, { kind: f.titleNew ? '상표 새 이름' : '상표 출원', id: f.id, date: f.applicationDate, company: f.company,
      fact: `상표 출원 「${f.title}」 ${classes}${f.addedClassesAt ? ' — 같은 이름 상품류 추가' : ''}${f.titleNew ? ' — 감시 시작 이후 처음 보는 이름' : ''} (출원 ${f.applicationDate}, 출원번호 ${(f.applicationNumbers ?? [])[0] ?? '?'}${(f.applicationNumbers ?? []).length > 1 ? ` 외 ${f.applicationNumbers.length - 1}` : ''})` });
  }

  const ab = docs['assembly-bills'];
  for (const g of groupBillEvents(ab, { all: true })) {
    if (!recent(g.detectedAt)) continue;
    push(g.core ? 'B' : 'C', W['assembly-bills'], { kind: g.kind === '발의' ? '법안 발의' : `법안 ${g.kind}`, id: g.id, date: g.date,
      company: g.core ?? '', fact: billLine(g), url: g.urls[0] });
  }

  const pw = docs['page-watch'];
  for (const e of pw?.events ?? []) {
    if (!recent(e.detectedAt)) continue;
    const added = Object.values(e.added ?? {}).flat().slice(0, 3).join(' / ');
    push(e.scope === 'page' ? 'A' : 'C', W['page-watch'], { kind: e.scope === 'site' ? '사이트 공통 문구' : '페이지 문구', id: `${e.pageId}:${e.detectedAt}`, date: e.detectedAt, company: e.company, fact: `${e.label ?? e.pageId}${e.scope === 'site' ? ' [사이트 공통]' : ''} 문구 변화${added ? `: + ${added}` : ''}`, url: e.url });
  }
  return items;
}

// id → how radar_today would show it now (watch, kind, tier, short title). Used to label judgments.
export async function itemIndex(ctx) {
  const docs = Object.fromEntries(await Promise.all(WATCHES.map(async (w) => [w.feed, await readFeed(ctx, w.feed)])));
  const index = new Map();
  for (const x of collect(docs, 0, '', { all: true })) {
    if (!x.id || index.has(x.id)) continue;
    const head = String(x.fact ?? '').split(' — ')[0];  // the headline, without the digest's notes
    index.set(String(x.id), { watch: x.watch, kind: x.kind ?? '', tier: x.tier, flag: x.flag ?? '',
      title: `${x.company && !head.startsWith(x.company) ? `${x.company} · ` : ''}${head}`.slice(0, 120) });
  }
  return index;
}

function health(ctx, docs) {
  const lines = [];
  for (const w of WATCHES) {
    const d = docs[w.feed];
    if (!d) { lines.push(`- ${w.label}: 결과 없음 — 미확인(${w.schedule} 실행 확인)`); continue; }
    if (d.broken) { lines.push(`- ${w.label}: 저장 형식 오류 — 미확인`); continue; }
    const ageH = (ctx.now.getTime() - Date.parse(d.generatedAt)) / 3600000;
    const waiting = (d.checks ?? []).filter((c) => c.status === 'partial' && !c.error && c.pending);  // read budget, not a failure
    const paused = (d.checks ?? []).filter((c) => c.status === 'waiting');  // call budget or provider cooldown: 미확인, not a failure
    const failed = (d.checks ?? []).filter((c) => c.status && !['ok', 'unset', 'waiting'].includes(c.status) && !waiting.includes(c) && !String(c.source ?? '').startsWith('공장등록 이름 규칙'));
    const unset = (d.checks ?? []).filter((c) => c.status === 'unset');
    const issues = [];
    if (Number.isFinite(ageH) && ageH > (w.staleHours ?? 36)) issues.push(`⚠ ${Math.round(ageH)}시간 전 결과`);
    if (failed.length) issues.push(`일부 실패 ${failed.length}건(${failed.slice(0, 3).map((c) => c.source ?? c.company ?? c.target).join(', ')})`);
    if (unset.length) issues.push(`미설정 ${unset.map((c) => `${c.source}(${c.error ?? '열쇠 없음'})`).join(', ')}`);
    if (waiting.length) issues.push(`${waiting.map((c) => `${c.source} 원문 대기 ${c.pending}건`).join(', ')}(실행당 읽기 한도, 다음 실행에서 읽음)`);
    if (paused.length) issues.push(`대기 ${paused.length}곳(${[...new Set(paused.map((c) => waitReason(c.reason)))].join(', ')})`);
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
  const found = collect(docs, cut, cutDay, { now: nowMs }).filter((x) => has(q, x.company, x.fact, x.watch));
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
  out.push(h.length ? `\n[먼저 볼 것: 수집 상태]\n${h.join('\n')}` : `\n[수집 상태] ${WATCHES.length}개 감시 모두 최근 정상`);
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
