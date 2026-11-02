// Morning collectors on time: GitHub's own cron is often hours late (2026-10-27: 06:30 → 09:41, 07:00 → 09:57),
// so a Cloudflare cron (every 10 minutes, all day) asks GitHub to run each
// watch at its slot through workflow_dispatch. GitHub's cron stays as a fallback. Results go to a private log blob.
import { storeOp } from './store.mjs';

const REPO = 'shhong9173-art/seoul-reporting-radar';
const KST_MS = 9 * 3600000;
const LOG_BLOB = 'dispatch_log';
const LOG_KEEP = 200;

// KST weekday (Mon–Fri) slots, matching each workflow's GitHub cron. `days: [1]` limits a slot to those KST days (0=일 … 6=토).
// `daily: true` slots also run on Sat·Sun:
// 주말에 GitHub 예약만 믿던 매일 감시가 늦거나 빠졌다(10-31 토: OSHA 06:40 예약이 돌지 않음, EPA·연비는 3시간 반 늦게).
export const SLOTS = [
  // 영국 Companies House: 영국 업무일이 끝난 뒤.
  { at: '06:00', workflow: 'overseas-registry.yml' },
  { at: '06:10', workflow: 'kr-fuel.yml', daily: true },
  // EPA·vPIC: GitHub 예약('20 21 * * *')이 10-29 아침에 돌지 않았다.
  { at: '06:20', workflow: 'us-epa.yml', daily: true },
  { at: '06:30', workflow: 'page-watch.yml' },
  // 미국 OSHA: 노동부 API는 매일 적재. 호출 간 12초라 2~3분.
  { at: '06:40', workflow: 'us-osha.yml', daily: true },
  // 지자체 고시·공고(새올): 아침·오후 한 번씩.
  { at: '06:30', workflow: 'kr-local.yml' },
  // 공식 원자료 직접 수집(pre_scoop.json: 대법원·NTIS·IRIS 등). GitHub 예약 '7,37 * * * *'은 10-28에 4번만 돌았다.
  // 07:10 단독 후보 심사·08:50 보도 대조·08:57 아침 발제 전에 한 번씩 새로 받는다.
  { at: '06:40', workflow: 'scoop-radar.yml' },
  // 해외 발주처 낙찰(TED는 평일 17시께 KST에 그날 공고를 낸다): 아침에 밤사이 FTS·세계은행, 저녁에 그날 TED.
  { at: '06:50', workflow: 'overseas-awards.yml' },
  { at: '07:00', workflow: 'partner-filings.yml' },
  { at: '07:10', workflow: 'scoop-screen.yml' },
  // 주 1회(월) 감시: GitHub 예약만 믿으면 늦거나 한 주를 통째로 거를 수 있다(10-31 토 OSHA 예약 누락). 상표는 KIPRIS 무료 한도를 쓰므로
  // 수집기가 6시간 안 직전 결과가 있으면 건너뛴다(GitHub 예약과 겹쳐도 한 번만 호출).
  { at: '07:10', workflow: 'trademark-watch.yml', days: [1] },
  // 협력사 회생·파산(대법원 공고): 아침에 전날 공고, 저녁에 그날 공고.
  { at: '07:20', workflow: 'kr-insolvency.yml' },
  { at: '07:30', workflow: 'kr-stats.yml' },
  { at: '07:40', workflow: 'trade-remedy.yml' },
  { at: '07:50', workflow: 'us-litigation.yml' },
  { at: '07:50', workflow: 'kr-building.yml', days: [1] },
  { at: '08:00', workflow: 'scoop-radar.yml' },
  { at: '08:10', workflow: 'kr-official.yml' },
  { at: '08:20', workflow: 'us-comments.yml' },
  { at: '08:30', workflow: 'kr-signals.yml' },
  // KIPRIS 특허 공보: GitHub 예약 06:30이 10-29에 10시까지 오지 않아 22 재조회(08:25 이후)가 밀렸다. 늦은 예약 실행은 워크플로가 건너뛴다.
  { at: '08:30', workflow: 'kipris-patent-hunt.yml' },
  { at: '08:40', workflow: 'assembly-bills.yml' },
  { at: '08:50', workflow: 'radar-press-check.yml' },
  // 나라장터 입찰공고: GitHub 예약(00:35 UTC = 09:35 KST)이 10-16~10-30 평일 내내 14:00~15:30 KST에야 돌았다(4.5~6시간 늦음).
  { at: '09:30', workflow: 'g2b-tender-official.yml' },
  // 공장등록·관보·법제처 낮 재시도: 아침 실행이 실패·시간 상한으로 못 읽은 질의가 있을 때만 스크립트가 다시 읽는다(11-02 공장등록 API 아침 시간 초과).
  { at: '13:10', workflow: 'kr-official.yml' },
  { at: '15:00', workflow: 'scoop-radar.yml' },
  { at: '15:10', workflow: 'scoop-screen.yml' },
  { at: '15:20', workflow: 'kr-signals.yml' },
  // 전기위원회 개최결과(오후 게시)·원안위 안건(회의 며칠 전 아침 게시).
  { at: '15:40', workflow: 'kr-energy.yml' },
  // 국민연금 사업장(월 자료): 표지 조회로 새 달만 전체를 읽고, 남는 시간에 지난 12개월을 채운다(최대 22분).
  { at: '15:50', workflow: 'kr-workforce.yml' },
  { at: '16:20', workflow: 'kr-local.yml' },
  // 미국 리콜·소비자 신고·TSB: 토요일 17:10이 미국 금요일 파일을 받는다(평일만 돌면 금요일 리콜이 월요일 저녁에야 잡혔다).
  { at: '17:10', workflow: 'us-recalls.yml', daily: true },
  { at: '17:20', workflow: 'kr-insolvency.yml' },
  { at: '17:30', workflow: 'overseas-awards.yml' },
  { at: '17:40', workflow: 'assembly-bills.yml' },
  { at: '18:00', workflow: 'scoop-radar.yml' },
  { at: '18:10', workflow: 'kr-energy.yml' },
  { at: '18:30', workflow: 'page-watch.yml' },
  { at: '18:50', workflow: 'radar-press-check.yml' },
  // 굴뚝 자동측정(3시간 칸, 주말 포함): GitHub 예약('23 */3 * * *')이 10-30~11-01에 4~10시간 간격으로만 돌아 평일 '2번 연속 빠짐'
  // 확인(동국제강 포항·KG스틸 당진·세아제강 창원)이 반나절 늦었다. 늦게 온 GitHub 예약은 스크립트가 100분 간격 규칙으로 건너뛴다.
  ...['00:20', '03:20', '06:20', '09:20', '12:20', '15:20', '18:20', '21:20'].map((at) => ({ at, workflow: 'kr-stacks.yml', daily: true })),
];

// 뉴스 수집(auto-desk.yml: 국내·산업·외신 기사)은 GitHub 예약('*/15 * * * *')이 10-31~11-01 24시간에 5번만 돌았다 —
// 코드가 올라올 때만 새로 고쳐졌다. 워커 예약(10분마다, 하루 종일)으로 20분마다(KST 매시 10·30·50분) 주말에도 요청한다.
// 성공은 기록하지 않고(기록이 아침 칸 기록을 밀어내지 않게) 실패만 남긴다. 같은 동시 실행 묶음이라 GitHub가 대기 실행을 하나로 줄인다.
export const NEWS_WORKFLOW = 'auto-desk.yml';
export function newsDue(when) {
  const m = new Date(when.getTime() + KST_MS).getUTCMinutes();
  return (Math.floor(m / 10) * 10) % 20 === 10;
}

export function dueAt(when) {
  const k = new Date(when.getTime() + KST_MS);
  const day = k.getUTCDay();
  const weekend = day === 0 || day === 6;
  const slot = `${String(k.getUTCHours()).padStart(2, '0')}:${String(Math.floor(k.getUTCMinutes() / 10) * 10).padStart(2, '0')}`;
  return SLOTS.filter((s) => s.at === slot && (s.days ? s.days.includes(day) : (!weekend || s.daily))).map((s) => s.workflow);
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
  const news = newsDue(when);
  if (!due.length && !news) return [];
  const stamp = when.toISOString();
  if (!env?.GITHUB_DISPATCH_TOKEN) {
    const entries = due.map((workflow) => ({ at: stamp, workflow, status: 'no-token' }));
    if (entries.length) await appendLog(ctx, entries);
    return entries;
  }
  const doFetch = deps.fetch ?? fetch;
  const entries = [];
  for (const workflow of due) entries.push({ at: stamp, workflow, status: await requestRun(env, workflow, doFetch) });
  const toLog = [...entries];
  if (news) {
    const e = { at: stamp, workflow: NEWS_WORKFLOW, status: await requestRun(env, NEWS_WORKFLOW, doFetch), kind: 'news' };
    entries.push(e);
    if (e.status !== 'ok') toLog.push(e);
  }
  if (toLog.length) await appendLog(ctx, toLog);
  return entries;
}

async function requestRun(env, workflow, doFetch) {
  try {
    const r = await doFetch(`https://api.github.com/repos/${REPO}/actions/workflows/${workflow}/dispatches`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${env.GITHUB_DISPATCH_TOKEN}`, Accept: 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'seoul-reporting-radar-cron', 'Content-Type': 'application/json' },
      body: JSON.stringify({ ref: 'main' }),
    });
    return r.status === 204 ? 'ok' : `HTTP ${r.status}`;
  } catch (e) {
    return e?.name ?? 'error';
  }
}

// One run asked outside the slots (e.g. right after the reporter's computer submitted browser-read notices). Logged like
// the slot requests, with who asked.
export async function dispatchNow(ctx, workflow, by) {
  const status = ctx.env?.GITHUB_DISPATCH_TOKEN ? await requestRun(ctx.env, workflow, ctx.fetch ?? fetch) : 'no-token';
  await appendLog(ctx, [{ at: ctx.now.toISOString(), workflow, status, by }]);
  return status;
}

// The next KST slot after `when` (for telling the reporter when the first request will go out).
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
