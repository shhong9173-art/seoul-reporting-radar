// Judgments and the weekly quality review. A judgment is stored with what the item was when judged
// (watch, kind such as 'DART 채무보증', tier, '일상' flag) so the review can show which watches and filing types
// the reporter actually uses or kills. It only shows counts — weights and tier rules never change automatically.
import { storeOp, candidateFeedback } from './store.mjs';
import { itemIndex } from './digest.mjs';
import { clampInt, kstStamp, textResult } from './common.mjs';

const VERDICTS = ['씀', '킬', '보류', '봤음'];
const MIN_SAMPLE = 5;   // groups smaller than this get counts only, no "점검 후보" note
const KILL_SHARE = 0.6; // kill share at or above this (with enough items) is worth a look

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
    return textResult(out.join('\n'));
  }

  out.push('\n[감시별] 항목 수 — 판정 | 판정 때 등급');
  const notes = [];
  for (const [watch, rs] of groupBy(items, (r) => r.watch)) {
    const tiers = groupBy(rs.filter((r) => r.tier), (r) => r.tier).sort((a, b) => a[0].localeCompare(b[0]));
    out.push(`- ${watch} ${rs.length} — ${fmt(rs)}${tiers.length ? ` | ${tiers.map(([t, x]) => `${t} ${x.length}(${fmt(x)})`).join(' · ')}` : ''}`);
    const killed = rs.filter((r) => r.verdict === '킬').length;
    if (rs.length >= MIN_SAMPLE && killed / rs.length >= KILL_SHARE) notes.push(`${watch}: ${rs.length}개 중 킬 ${killed} — 등급·문턱 점검 후보`);
  }

  const kinds = groupBy(items.filter((r) => r.kind), (r) => `${r.watch} · ${r.kind}`);
  if (kinds.length) {
    out.push('\n[종류별] (DART는 공시 종류)');
    for (const [k, rs] of kinds.slice(0, 15)) {
      const routine = rs.filter((r) => r.flag === '일상');
      out.push(`- ${k} ${rs.length} — ${fmt(rs)}${routine.length ? ` | 일상(B) ${routine.length}: ${fmt(routine)}` : ''}`);
      const killed = rs.filter((r) => r.verdict === '킬').length;
      if (rs.length >= MIN_SAMPLE && killed / rs.length >= KILL_SHARE) notes.push(`${k}: ${rs.length}개 중 킬 ${killed} — 등급·문턱 점검 후보`);
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
  return textResult(out.join('\n'));
}
