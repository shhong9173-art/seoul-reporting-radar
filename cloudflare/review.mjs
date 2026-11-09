// Judgments and the weekly quality review. A judgment is stored with what the item was when judged
// (watch, kind such as 'DART 채무보증', tier, '일상' flag) so the review can show which watches and filing types
// the reporter actually uses or kills. It only shows counts — weights and tier rules never change automatically.
import { storeOp, candidateFeedback } from './store.mjs';
import { itemIndex, WATCHES } from './digest.mjs';
import { clampInt, kstStamp, textResult } from './common.mjs';
import { readFeed, ageNote } from './screen.mjs';
import { reverseClip, reverseNumbersNote, reverseTallyLines } from './overseas.mjs';

const VERDICTS = ['씀', '킬', '보류', '봤음'];
const MIN_SAMPLE = 5;   // groups smaller than this get counts only, no "점검 후보" note
const KILL_SHARE = 0.6; // kill share at or above this (with enough items) is worth a look
const ALERT_MIN = 3;    // 즉시 알림 성적: 이 감시로 보낸 알림이 이만큼 넘어야 제안을 붙인다
// 기자가 이미 바꾼 알림·발제 기준(11-04~). 이 시각 앞 판정은 바뀐 기준의 성적이 아니라 따로 센다.
export const DECIDED = [
  { watch: '굴뚝 측정(공장 가동 신호)', since: '2026-11-04T05:13:00Z',
    rule: '즉시 알림·아침 발제는 〔즉시 알림 대상〕(다른 감시와 겹친 신호·배출구 절반 넘게 72시간 넘는 가동중지 신고)만' },
  // 11-08 기자: '굴뚝 측정 쓸데없는게 너무 많이 와' — 실시간 신호는 A 없음, 배출구 하나하나의 신호는 C, 즉시 알림 겹침은 공장 이름까지 맞을 때만
  { watch: '굴뚝 측정(공장 가동 신호)', since: '2026-11-08T07:00:00Z',
    rule: '실시간 신호는 A 없음·배출구 하나하나의 초과/멈춤/전환/빠짐은 C, 즉시 알림 겹침은 공장 이름까지 맞을 때만' },
];
// 같은 감시에 기준을 여러 번 바꿨으면 가장 최근 것
const decidedFor = (watch) => DECIDED.filter((x) => x.watch === watch).sort((a, b) => b.since.localeCompare(a.since))[0];
const topReasons = (rs, n = 2) => {
  const c = {};
  for (const r of rs.filter((x) => x.verdict === '킬')) c[r.reason || '사유 없음'] = (c[r.reason || '사유 없음'] ?? 0) + 1;
  return Object.entries(c).sort((a, b) => b[1] - a[1]).slice(0, n).map(([k, v]) => `'${String(k).slice(0, 40)}'(${v})`).join(', ');
};
// 킬이 몰린 묶음의 점검 문구: 이미 바꾼 기준이면 바뀐 뒤 판정만 보고, 아니면 사유와 함께 바꿀 안을 붙인다(바꾸는 건 기자).
function killNote(label, rs, killed, watch) {
  const d = decidedFor(watch);
  if (d) {
    const after = rs.filter((r) => String(r.created_at) >= d.since);
    const ak = after.filter((r) => r.verdict === '킬').length;
    if (after.length < MIN_SAMPLE) return `${label}: ${rs.length}개 중 킬 ${killed} — ${d.since.slice(5, 10)}에 기준을 이미 바꿈(${d.rule}) · 바뀐 뒤 판정 ${after.length}건(킬 ${ak})이라 아직 판단 안 함`;
    if (ak / after.length < KILL_SHARE) return `${label}: 바뀐 기준(${d.since.slice(5, 10)}) 뒤 판정 ${after.length}건 중 킬 ${ak} — 기준 변경 뒤 나아짐`;
    return `${label}: 바뀐 기준(${d.since.slice(5, 10)}) 뒤에도 ${after.length}건 중 킬 ${ak} — 더 좁힐지 점검 · 킬 사유 ${topReasons(after)}`;
  }
  return `${label}: ${rs.length}개 중 킬 ${killed} — 등급·문턱 점검 후보 · 킬 사유 ${topReasons(rs)} · 제안: 즉시 알림·아침 발제는 다른 감시와 겹칠 때만(굴뚝 11-04 방식) 또는 등급 한 단계 내림 — 바꿀지는 기자가 정함`;
}

// 즉시 알림 성적(11-04): 단독 후보 즉시 알림이 저장한 alert-YYYYMMDD 패키지의 '보낸 id:' 줄과 기자 판정을 맞춘다.
// id 안의 쉼표(배출구 '83,82')는 띄어쓰기가 없어 ', '로만 나눈다.
async function alertLines(ctx, days, judgedById, index) {
  let rows = [];
  try { ({ rows } = await storeOp(ctx, 'packages.list', {})); } catch { return []; }
  const from = new Date(ctx.now.getTime() + 9 * 3600000 - days * 86400000).toISOString().slice(0, 10).replaceAll('-', '');
  const names = (rows ?? []).filter((r) => /^alert-\d{8}$/.test(r.name) && r.name.slice(6) >= from).map((r) => r.name);
  if (!names.length) return [`\n[즉시 알림 성적 · 최근 ${days}일] 저장된 알림 없음(alert-YYYYMMDD 패키지)`];
  const sent = [];
  for (const name of names) {
    const { row } = await storeOp(ctx, 'packages.get', { name });
    const line = [...String(row?.body ?? '').matchAll(/보낸 id:\s*(.+)$/gm)].pop();
    for (const id of line ? line[1].split(/,\s+/).map((x) => x.trim()).filter(Boolean) : []) if (!sent.some((x) => x.id === id)) sent.push({ id, day: name.slice(6) });
  }
  const real = (w) => (w && !String(w).startsWith('감시 미상') ? w : null);
  // 판정·지금 목록에 없는 id는 앞말로 감시를 짐작한다(11-03 알림의 회생 공고 'ins:'가 '감시 미상'으로 떴다)
  const PREFIX = { stk: 'kr-stacks', labor: 'kr-labor', ins: 'kr-insolvency', un: 'union-notices', clik: 'council-minutes', fac: 'kr-official',
    wf: 'kr-workforce', local: 'kr-local', bld: 'kr-building', edgar: 'partner-filings', nse: 'india-filings', clue: 'scoop-screen', gl: 'global-beat',
    gov: 'governance', cp: 'dart-counterparty', exec: 'kr-exec', execm: 'kr-exec-market', execc: 'kr-exec-check' };
  const byPrefix = (id) => WATCHES.find((w) => w.feed === PREFIX[String(id).split(':')[0]])?.label;
  const watchOf = (id) => real(judgedById.get(id)?.watch) || real(index.get(id)?.watch) || byPrefix(id) || '감시 미상';
  const rowsOut = sent.map((x) => ({ ...x, watch: watchOf(x.id), verdict: judgedById.get(x.id)?.verdict ?? '판정 없음', r: judgedById.get(x.id) }));
  const count = (rs) => ['씀', '킬', '보류', '봤음', '판정 없음'].map((v) => [v, rs.filter((x) => x.verdict === v).length]).filter(([, n]) => n).map(([v, n]) => `${v} ${n}`).join(' · ');
  const out = [`\n[즉시 알림 성적 · 최근 ${days}일] 알림 ${names.length}일치 · 보낸 항목 ${rowsOut.length}건 — ${count(rowsOut)}`];
  for (const [watch, rs] of groupBy(rowsOut, (x) => x.watch)) {
    const killed = rs.filter((x) => x.verdict === '킬').length;
    const d = decidedFor(watch);
    const afterRs = d ? rs.filter((x) => `${x.day.slice(0, 4)}-${x.day.slice(4, 6)}-${x.day.slice(6)}T23:59:59Z` >= d.since && (!x.r || String(x.r.created_at) >= d.since)) : rs;
    let note = '';
    if (d) note = ` · ${d.since.slice(5, 10)} 기준 변경 뒤 보낸 것 ${afterRs.length}건${afterRs.length ? `(${count(afterRs)})` : ''}`;
    else if (rs.length >= ALERT_MIN && killed / rs.length >= KILL_SHARE) note = ` · 제안: 이 감시 즉시 알림 기준 좁히기(다른 감시와 겹칠 때만·A만 등) — 킬 사유 ${topReasons(rs.map((x) => x.r).filter(Boolean))} · 바꿀지는 기자가 정함`;
    out.push(`- ${watch} ${rs.length} — ${count(rs)}${note}`);
  }
  out.push('   읽는 법: 알림이 보낸 항목만 센다(화면에만 있던 항목 제외). 판정 없음은 기자가 아직 안 본 것일 수 있다 — 킬로 세지 않는다.');
  return out;
}

async function safeIndex(ctx) {
  try { return await itemIndex(ctx); } catch { return new Map(); }  // labels are best-effort; the judgment still saves
}

export async function judgeItems(ctx, args) {
  return candidateFeedback(ctx, args, await safeIndex(ctx));
}

const counts = (rows) => VERDICTS.map((v) => [v, rows.filter((r) => r.verdict === v).length]).filter(([, n]) => n);
const fmt = (rows) => counts(rows).map(([v, n]) => `${v} ${n}`).join(' · ') || '없음';

function groupBy(rows, key) {
  const m = new Map();
  for (const r of rows) { const k = key(r); if (!m.has(k)) m.set(k, []); m.get(k).push(r); }
  return [...m.entries()].sort((a, b) => b[1].length - a[1].length || a[0].localeCompare(b[0]));
}

// 기자 기사 자동 대조(my_articles_check.py): 기자가 쓴 출입처 기사마다 레이더가 먼저 잡은 항목이 있었는지. 판정과 별개인 자동 기록 —
// 쓴 기사는 자동으로 찾지만, 안 쓴 항목은 이유를 모르므로 킬로 세지 않는다.
// 경쟁지 단독 역추적 종류·매체별 한 묶음(scoop_reverse 전문)
async function rivalLines(ctx, days) {
  const doc = await readFeed(ctx, 'reverse-check');
  if (!doc || doc.broken) return [];
  const from = Date.parse(doc.generatedAt) - Math.min(days, 30) * 86400000;
  const rows = (doc.articles ?? []).filter((x) => Date.parse(x.published) >= from);
  const lines = reverseTallyLines(rows, 6);
  return lines.length ? [`\n[경쟁지 단독 · 최근 ${Math.min(days, 30)}일 ${rows.length}건 · 레이더 대조(자동)]`, ...lines, '자세히: scoop_reverse'] : [];
}

export async function myArticlesLines(ctx, days) {
  const doc = await readFeed(ctx, 'my-articles');
  if (!doc) return ['\n[자동 대조: 기자 기사 ↔ 레이더] 아직 수집 전 — 미확인(매일 13:00·19:40)'];
  if (doc.broken) return ['\n[자동 대조: 기자 기사 ↔ 레이더] 저장 형식 오류 — 미확인'];
  const c = (doc.checks ?? [])[0] ?? {};
  const from = new Date(ctx.now.getTime() - days * 86400000).toISOString();
  const rows = (doc.articles ?? []).filter((a) => String(a.published) >= from);
  const n = (v) => rows.filter((a) => a.verdict === v).length;
  const unverified = rows.filter((a) => a.verified === false).length;
  const out = [`\n[자동 대조: 기자 기사 ↔ 레이더 · 아이뉴스24 ${doc.author ?? ''} 기사 · 확인 ${String(doc.generatedAt).slice(0, 16)}${ageNote(ctx, doc.generatedAt)} · 최근 ${days}일]`,
    `기사 ${rows.length}건${unverified ? `(그중 ${unverified}건은 첫 실행 구글 색인이라 작성자 미확인)` : ''} — 레이더가 먼저 잡은 후보 ${n('먼저 잡은 후보')} · 같은 회사 항목만 ${n('같은 회사 항목만')} · 없음 ${n('없음')}${n('회사 미상') ? ` · 회사 미상 ${n('회사 미상')}(제목에 출입처 이름 없음 — 업계·당직 기사)` : ''}`,
    `원천: ${c.source ?? '?'} ${c.status ?? '?'}(사이트맵 ${c.returned ?? 0}, 출입처 제목 새 기사 ${c.candidates ?? 0}, 작성자 확인 ${c.opened ?? 0}${c.error ? `, ${c.error}` : ''})`];
  const by = {};
  for (const a of rows.filter((x) => x.verdict === '먼저 잡은 후보' && x.best)) (by[a.best.label] ??= []).push(a);
  const groups = Object.entries(by).sort((a, b) => b[1].length - a[1].length);
  if (groups.length) out.push('감시별(먼저 잡은 후보): ' + groups.map(([k, v]) => `${k} ${v.length}`).join(' · '));
  for (const a of rows.filter((x) => x.verdict === '먼저 잡은 후보' && x.best).slice(0, 8)) {
    out.push(`- 기사 ${String(a.published).slice(5, 16).replace('T', ' ')} 「${String(a.title).slice(0, 60)}」${a.verified === false ? '(작성자 미확인)' : ''}`);
    out.push(`   레이더: ${String(a.best.seen).slice(5, 16).replace('T', ' ')} ${a.best.label} — ${reverseClip(a.best.text, 90)} (${a.best.leadHours}시간 앞${(a.best.why ?? []).length ? `, 겹친 낱말 ${a.best.why.join('·')}` : ''})${reverseNumbersNote(a.best)} · id ${a.best.id}`);
  }
  // 레이더가 놓친 기사(11-04 기자 요청 뒤): 어떤 원천을 더할지 보려고 종류별로 묶고 '없음' 제목을 보여 준다(기자 전용 화면).
  const byKind = (rs) => Object.entries(rs.reduce((m, a) => ({ ...m, [a.kind ?? '기타']: (m[a.kind ?? '기타'] ?? 0) + 1 }), {}))
    .sort((a, b) => b[1] - a[1]).map(([k, v]) => `${k} ${v}`).join(' · ');
  // 보도자료·공시 기사 가리기(11-04 기자: "내 기사 대부분이 보도자료") — 레이더는 자체·선행 기사로만 본다
  const pc = (k) => rows.filter((a) => (a.press ?? '미확인') === k).length;
  const own = rows.filter((a) => a.press === '자체' || a.press === '선행');
  if (rows.some((a) => a.press)) {
    const on = (v) => own.filter((a) => a.verdict === v).length;
    out.push(`보도자료·공시 추정 ${pc('보도자료·공시')} · 자체 ${pc('자체')} · 선행 ${pc('선행')}${pc('미확인') ? ` · 미확인 ${pc('미확인')}` : ''} — 자체·선행 ${own.length}건 중 레이더가 먼저 잡은 후보 ${on('먼저 잡은 후보')} · 같은 회사 항목만 ${on('같은 회사 항목만')} · 없음 ${on('없음')}${on('회사 미상') ? ` · 회사 미상 ${on('회사 미상')}` : ''}`);
    const lead = rows.filter((a) => a.press === '선행');
    if (lead.length) {
      out.push(`기자 기사가 먼저 나오고 다른 매체가 따라온 기사(선행) ${lead.length}건`);
      for (const a of lead.slice(0, 8)) out.push(`  · ${String(a.published).slice(5, 10)} 「${String(a.title).slice(0, 60)}」 — 뒤따른 비슷한 기사 ${a.pressN ?? '?'}건`);
    }
  }
  const pool = rows.some((a) => a.press) ? own.concat(rows.filter((a) => !a.press)) : rows;   // 보도자료로 정해진 기사는 '놓친 기사'에서 뺀다
  const miss = pool.filter((a) => a.verdict === '없음');
  const sameOnly = pool.filter((a) => a.verdict === '같은 회사 항목만');
  if (miss.length) {
    out.push(`레이더에 같은 회사 항목도 없던 기사 ${miss.length}건${rows.some((a) => a.press) ? '(보도자료·공시 추정 뺌)' : ''} — ${byKind(miss)}`);
    for (const a of miss.slice(0, 15)) out.push(`  · ${String(a.published).slice(5, 10)} [${a.kind ?? '기타'}${a.press ? `·${a.press}` : ''}] 「${String(a.title).slice(0, 60)}」${a.verified === false ? '(작성자 미확인)' : ''}`);
    if (miss.length > 15) out.push(`  … ${miss.length - 15}건 더`);
  }
  if (sameOnly.length) out.push(`같은 회사 항목만 있던 기사 ${sameOnly.length}건(사건은 달랐음) — ${byKind(sameOnly)}`);
  out.push('읽는 법: 자동 대조다(같은 사건인지는 열어 봐야 함). 쓴 기사만 찾는다 — 안 쓴 항목은 킬이 아니다(이유 모름). 출입처 이름이 제목에 없는 업계 기사·당직 기사는 빠진다. 실적·인사·제품 기사는 보도자료·공시로 나와 공개 원천이 앞서기 어렵다.');
  return out;
}

export async function weeklyReview(ctx, args) {
  const days = clampInt(args.days, 1, 60, 7);
  const since = new Date(ctx.now.getTime() - days * 86400000).toISOString();
  const { rows, candidates } = await storeOp(ctx, 'feedback.since', { since });
  // one line per item: its latest judgment in the window (rows come newest first)
  const latest = new Map();
  for (const r of rows) if (!latest.has(r.item_id)) latest.set(r.item_id, r);
  let items = [...latest.values()];
  const index = items.some((r) => !r.watch) ? await safeIndex(ctx) : new Map();
  items = items.map((r) => {
    if (r.watch) return r;
    const m = index.get(r.item_id);
    if (m) return { ...r, ...m, labelled: 'now' };
    return { ...r, watch: String(r.item_id).startsWith('#') ? '제출 후보' : '감시 미상(지금 목록에 없음)', kind: '', tier: '', flag: '', title: '' };
  });

  const out = [`최근 ${days}일 판정 · ${kstStamp(ctx.now)}`,
    `제출 후보 ${candidates.length}건(추천 ${candidates.filter((c) => c.status === '추천').length}) · 판정한 항목 ${items.length}개: ${fmt(items)}` +
      (rows.length > items.length ? ` (기록 ${rows.length}건, 같은 항목은 마지막 판정만 셈)` : '')];
  if (!items.length) {
    out.push('판정 기록이 없다. radar_today·scoop_screen 줄의 id로 candidate_feedback(씀·킬·보류·봤음)을 남기면 감시별·공시 종류별로 묶어 보여 준다.');
    out.push('가중치는 자동으로 바꾸지 않는다. 바꿀지는 기자가 정한다.');
    out.push(...await alertLines(ctx, days, new Map(), new Map()));
    out.push(...await myArticlesLines(ctx, days), ...await rivalLines(ctx, days));
    return textResult(out.join('\n'));
  }

  out.push('\n[감시별] 항목 수 — 판정 | 판정 때 등급');
  const notes = [];
  for (const [watch, rs] of groupBy(items, (r) => r.watch)) {
    const tiers = groupBy(rs.filter((r) => r.tier), (r) => r.tier).sort((a, b) => a[0].localeCompare(b[0]));
    out.push(`- ${watch} ${rs.length} — ${fmt(rs)}${tiers.length ? ` | ${tiers.map(([t, x]) => `${t} ${x.length}(${fmt(x)})`).join(' · ')}` : ''}`);
    const killed = rs.filter((r) => r.verdict === '킬').length;
    if (rs.length >= MIN_SAMPLE && killed / rs.length >= KILL_SHARE) notes.push(killNote(watch, rs, killed, watch));
  }

  const kinds = groupBy(items.filter((r) => r.kind), (r) => `${r.watch} · ${r.kind}`);
  if (kinds.length) {
    out.push('\n[종류별] (DART는 공시 종류)');
    for (const [k, rs] of kinds.slice(0, 15)) {
      const routine = rs.filter((r) => r.flag === '일상');
      out.push(`- ${k} ${rs.length} — ${fmt(rs)}${routine.length ? ` | 일상(B) ${routine.length}: ${fmt(routine)}` : ''}`);
      const killed = rs.filter((r) => r.verdict === '킬').length;
      if (rs.length >= MIN_SAMPLE && killed / rs.length >= KILL_SHARE) notes.push(killNote(k, rs, killed, rs[0].watch));
    }
    if (kinds.length > 15) out.push(`… 종류 ${kinds.length - 15}개 더`);
  }

  // The routine rule moves filings to B; a used routine filing means the rule hid a story.
  const usedRoutine = items.filter((r) => r.flag === '일상' && r.verdict === '씀');
  for (const r of usedRoutine) notes.push(`일상(B)으로 내렸는데 씀: ${r.title || r.item_id} — 일상 판정 규칙 점검 후보`);
  const usedC = items.filter((r) => r.tier === 'C' && r.verdict === '씀');
  for (const r of usedC) notes.push(`C(참고)였는데 씀: ${r.title || r.item_id} — 등급 규칙 점검 후보`);
  out.push(notes.length ? `\n[점검 후보]\n${notes.map((n) => `- ${n}`).join('\n')}` : `\n[점검 후보] 없음(묶음 ${MIN_SAMPLE}개 이상·킬 ${Math.round(KILL_SHARE * 100)}% 이상, 일상·C로 내린 것 중 씀 기준)`);

  const reasons = {};
  for (const r of items.filter((x) => x.verdict === '킬')) reasons[r.reason] = (reasons[r.reason] ?? 0) + 1;
  const top = Object.entries(reasons).sort((a, b) => b[1] - a[1]).slice(0, 5);
  if (top.length) out.push('\n킬 사유 상위: ' + top.map(([k, v]) => `${k}(${v})`).join(' / '));

  out.push('\n[최근 판정]');
  for (const r of items.slice(0, 20)) {
    const label = [r.watch, r.kind, r.tier].filter(Boolean).join(' · ');
    out.push(`- ${String(r.created_at).slice(5, 10)} [${r.verdict}] ${label}${r.title ? ` · ${r.title.slice(0, 70)}` : ''} — ${r.reason} (id ${r.item_id})`);
  }
  if (items.some((r) => r.labelled === 'now')) out.push('※ 일부 항목은 판정 때 표시가 없어 지금 목록 기준으로 붙였다.');
  out.push(`읽는 법: ${MIN_SAMPLE}개 미만 묶음은 비율로 판단하지 않는다. 점검 후보는 기자가 볼 목록일 뿐 — 가중치·등급 규칙은 자동으로 바꾸지 않는다. 바꿀지는 기자가 정한다.`);
  const judgedById = new Map(items.map((r) => [r.item_id, r]));
  out.push(...await alertLines(ctx, days, judgedById, index));
  out.push(...await myArticlesLines(ctx, days), ...await rivalLines(ctx, days));
  return textResult(out.join('\n'));
}
