// Morning collectors on time: GitHub's own cron is often hours late (2026-10-27: 06:30 → 09:41, 07:00 → 09:57),
// so a Cloudflare cron (every 10 minutes in the KST morning and late-afternoon windows) asks GitHub to run each
// watch at its slot through workflow_dispatch. GitHub's cron stays as a fallback. Results go to a private log blob.
import { storeOp } from './store.mjs';

const REPO = 'shhong9173-art/seoul-reporting-radar';
const KST_MS = 9 * 3600000;
const LOG_BLOB = 'dispatch_log';
const LOG_KEEP = 200;

// KST weekday (Mon–Fri) slots, matching each workflow's GitHub cron.
export const SLOTS = [
  { at: '06:30', workflow: 'page-watch.yml' },
  // 공식 원자료 직접 수집(pre_scoop.json: 대법원·NTIS·IRIS 등). GitHub 예약 '7,37 * * * *'은 10-28에 4번만 돌았다.
  // 07:10 단독 후보 심사·08:50 보도 대조·08:57 아침 발제 전에 한 번씩 새로 받는다.
  { at: '06:40', workflow: 'scoop-radar.yml' },
  { at: '07:00', workflow: 'partner-filings.yml' },
  { at: '07:10', workflow: 'scoop-screen.yml' },
  { at: '07:30', workflow: 'kr-stats.yml' },
  { at: '07:40', workflow: 'trade-remedy.yml' },
  { at: '07:50', workflow: 'us-litigation.yml' },
  { at: '08:00', workflow: 'scoop-radar.yml' },
  { at: '08:10', workflow: 'kr-official.yml' },
  { at: '08:20', workflow: 'us-comments.yml' },
  { at: '08:30', workflow: 'kr-signals.yml' },
  { at: '08:40', workflow: 'assembly-bills.yml' },
  { at: '08:50', workflow: 'radar-press-check.yml' },
  { at: '15:00', workflow: 'scoop-radar.yml' },
  { at: '15:10', workflow: 'scoop-screen.yml' },
  { at: '15:20', workflow: 'kr-signals.yml' },
  { at: '17:10', workflow: 'us-recalls.yml' },
  { at: '17:40', workflow: 'assembly-bills.yml' },
  { at: '18:00', workflow: 'scoop-radar.yml' },
  { at: '18:30', workflow: 'page-watch.yml' },
  { at: '18:50', workflow: 'radar-press-check.yml' },
];

export function dueAt(when) {
  const k = new Date(when.getTime() + KST_MS);
  const day = k.getUTCDay();
  if (day === 0 || day === 6) return [];
  const slot = `${String(k.getUTCHours()).padStart(2, '0')}:${String(Math.floor(k.getUTCMinutes() / 10) * 10).padStart(2, '0')}`;
  return SLOTS.filter((s) => s.at === slot).map((s) => s.workflow);
}

async function appendLog(ctx, entries) {
  const { row } = await storeOp(ctx, 'blobs.get', { name: LOG_BLOB });
  let log = [];
  try { log = row ? JSON.parse(row.body) : []; } catch { log = []; }
  log = [...entries, ...log].slice(0, LOG_KEEP);
  await storeOp(ctx, 'blobs.put', { name: LOG_BLOB, body: JSON.stringify(log) });
}

export async function runSchedule(env, when, deps = {}) {
  const ctx = { env, now: when };
  const due = dueAt(when);
  if (!due.length) return [];
  const stamp = when.toISOString();
  if (!env?.GITHUB_DISPATCH_TOKEN) {
    const entries = due.map((workflow) => ({ at: stamp, workflow, status: 'no-token' }));
    await appendLog(ctx, entries);
    return entries;
  }
  const doFetch = deps.fetch ?? fetch;
  const entries = [];
  for (const workflow of due) {
    let status;
    try {
      const r = await doFetch(`https://api.github.com/repos/${REPO}/actions/workflows/${workflow}/dispatches`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${env.GITHUB_DISPATCH_TOKEN}`, Accept: 'application/vnd.github+json',
          'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'seoul-reporting-radar-cron', 'Content-Type': 'application/json' },
        body: JSON.stringify({ ref: 'main' }),
      });
      status = r.status === 204 ? 'ok' : `HTTP ${r.status}`;
    } catch (e) {
      status = e?.name ?? 'error';
    }
    entries.push({ at: stamp, workflow, status });
  }
  await appendLog(ctx, entries);
  return entries;
}

// The next KST weekday slot after `when` (for telling the reporter when the first request will go out).
export function nextSlot(when) {
  for (let i = 1; i <= 7 * 24 * 6; i++) {
    const t = new Date(when.getTime() + i * 600000);
    const due = dueAt(t);
    if (due.length) {
      const k = new Date(t.getTime() + KST_MS);
      return `${k.toISOString().slice(5, 10)} ${String(k.getUTCHours()).padStart(2, '0')}:${String(Math.floor(k.getUTCMinutes() / 10) * 10).padStart(2, '0')} ${due.join(',')}`;
    }
  }
  return null;
}

// One line for radar_today: how the requests went, and whether the worker can see the token right now
// (only presence is checked — the value is never read out).
export async function dispatchHealth(ctx) {
  const hasToken = Boolean(ctx.env?.GITHUB_DISPATCH_TOKEN);
  const missingNow = '지금도 워커에서 GITHUB_DISPATCH_TOKEN이 보이지 않음 — Cloudflare → Workers → seoul-reporting-radar → Settings → Variables and Secrets(Build 아님)에 종류 Secret, 이름 정확히 확인';
  const { row } = await storeOp(ctx, 'blobs.get', { name: LOG_BLOB });
  if (!row) return hasToken ? null : `예약 요청(Cloudflare): 기록 없음 · ${missingNow}`;
  let log = [];
  try { log = JSON.parse(row.body); } catch { return '예약 요청(Cloudflare): 기록 형식 오류'; }
  const day = new Date(ctx.now.getTime() + KST_MS).toISOString().slice(0, 10);
  const today = log.filter((e) => new Date(Date.parse(e.at) + KST_MS).toISOString().slice(0, 10) === day);
  if (!today.length) return hasToken ? null : `예약 요청(Cloudflare): ${missingNow}`;
  if (today.every((e) => e.status === 'no-token')) {
    return hasToken
      ? `예약 요청(Cloudflare): 오늘 앞선 칸은 토큰 없이 지나감 · 지금은 토큰 보임 — 다음 칸(${nextSlot(ctx.now) ?? '?'})부터 요청`
      : `예약 요청(Cloudflare): 토큰 없음 — GitHub 예약만 사용 중(지연 가능) · ${missingNow}`;
  }
  const bad = today.filter((e) => e.status !== 'ok');
  return bad.length ? `예약 요청(Cloudflare): 오늘 ${today.length}건 중 실패 ${bad.length}건(${bad.slice(0, 3).map((e) => `${e.workflow} ${e.status}`).join(', ')})` : null;
}
