// 단독 후보 즉시 알림(Claude 앱 예약 작업)이 예약 시각마다 돌았는지 — 11-17 기자 결정('전부 추천대로').
// 11-16 23:43·11-17 08:43 실행이 사용 한도로 실패했는데 알림이 안 온 것만으로는 '보낼 게 없었다'와 구별이 안 됐다.
// 11-17 12:43부터 알림 작업은 0건이어도 alert-YYYYMMDD 패키지에 '[단독 후보 알림 HH:MM] 0건' 줄을 남긴다(지시문 0·1단계).
// 여기서는 그 줄을 읽어 기록이 빈 예약 시각을 수집 상태에 한 줄로 띄운다. 패키지 본문은 기자 전용 저장소에만 있다.
import { storeOp } from './store.mjs';

const KST_MS = 9 * 3600000;
export const ALERT_SLOTS = [[8, 43], [12, 43], [15, 43], [18, 43], [21, 43], [23, 43]];  // 예약 작업 '단독 후보 즉시 알림'(KST, 매일)
export const ALERT_RECORD_SINCE = Date.parse('2026-11-17T12:43:00+09:00');  // 이때부터 0건도 기록 — 그 전 시각은 묻지 않는다
const GRACE_MIN = 50;   // 실행·원문 확인·저장까지 기다리는 시간
const EARLY_MIN = 5;
const LOOKBACK_H = 36;
const RECORD = /^\[단독 후보 알림 (\d{1,2}):(\d{2})\]\s*(.*)$/;
const kstStamp = (ms) => `${new Date(ms + KST_MS).toISOString().slice(5, 16).replace('T', ' ')} KST`;
const kstDay = (ms) => new Date(ms + KST_MS).toISOString().slice(0, 10).replaceAll('-', '');

// 패키지 본문의 실행 기록 줄 → [{ at, failed }]. 시각은 패키지 이름의 날짜(KST) 기준.
export function alertRuns(name, body) {
  const m = /^alert-(\d{4})(\d{2})(\d{2})$/.exec(String(name ?? ''));
  if (!m) return [];
  const out = [];
  for (const line of String(body ?? '').split('\n')) {
    const r = RECORD.exec(line.trim());
    if (!r) continue;
    const at = Date.parse(`${m[1]}-${m[2]}-${m[3]}T${r[1].padStart(2, '0')}:${r[2]}:00+09:00`);
    if (Number.isFinite(at)) out.push({ at, failed: /조회 실패/.test(r[3]) });
  }
  return out;
}

// 지금(여유를 뺀 시각)까지 지난 예약 시각 중 기록이 없는 것(마지막으로 돈 기록 뒤만). 기록은 그 예약 시각부터 다음 예약 시각 전까지 적힌 것을 센다
// (대화에서 늦게 대신 보낸 것 포함). '조회 실패' 줄은 돈 것으로 치지 않는다.
export function alertGaps(nowMs, runs, { since = ALERT_RECORD_SINCE } = {}) {
  const ok = runs.filter((r) => !r.failed).map((r) => r.at);
  const until = nowMs - GRACE_MIN * 60000;
  const from = Math.max(since, nowMs - LOOKBACK_H * 3600000);
  const day0 = Math.floor((nowMs + KST_MS) / 86400000) * 86400000 - KST_MS;
  const slots = [];
  for (let d = 2; d >= 0; d--) for (const [h, mi] of ALERT_SLOTS) slots.push(day0 - d * 86400000 + (h * 60 + mi) * 60000);
  const missed = [];
  // 11-18: 08:43이 빈 뒤 12:43·15:43이 돌았는데도 08:43 '기록 없음'이 36시간 동안 떴다. 알림 작업은 0단계에서 마지막 기록부터 범위를 넓혀
  // 다시 보므로, 마지막으로 돈 기록보다 앞선 빈 시각은 이미 다시 본 것이다 — 마지막 기록 뒤의 빈 시각만 센다.
  const lastOk = ok.length ? Math.max(...ok) : -Infinity;
  slots.forEach((s, i) => {
    if (s < from || s > until || s < lastOk - EARLY_MIN * 60000) return;
    const next = slots[i + 1] ?? s + 24 * 3600000;
    if (!ok.some((t) => t >= s - EARLY_MIN * 60000 && t < next)) missed.push(s);
  });
  return { missed, last: ok.length ? Math.max(...ok) : null };
}

export async function alertHealth(ctx) {
  const nowMs = ctx.now.getTime();
  if (nowMs < ALERT_RECORD_SINCE + GRACE_MIN * 60000) return null;
  const names = [kstDay(nowMs - 86400000), kstDay(nowMs)].map((d) => `alert-${d}`);
  const rows = await Promise.all(names.map((name) => storeOp(ctx, 'packages.get', { name })));
  const runs = rows.flatMap((r, i) => alertRuns(names[i], r?.row?.body));
  const { missed, last } = alertGaps(nowMs, runs);
  if (!missed.length) return null;
  const today = kstDay(nowMs);
  const when = missed.map((s) => (kstDay(s) === today ? kstStamp(s).slice(6, 11) : kstStamp(s).slice(0, 11))).join('·');
  return `단독 후보 즉시 알림(Claude 앱 예약 작업, 매일 08:43·12:43·15:43·18:43·21:43·23:43): ⚠ 예약 ${missed.length}번 기록 없음(${when})`
    + ` · 마지막 기록 ${last ? kstStamp(last) : '없음'} — 실행이 실패했을 수 있다(사용 한도 등). 그 사이 알림 대상은 미확인 — 다음 실행이 범위를 넓혀 다시 본다.`
    + `${missed.length >= 2 ? ' 여러 번 빠졌으니 Claude 앱 예약 작업의 실행 기록을 확인' : ''}`;
}

// 아침 발제 초안·오후 출입처 공시 체크(Claude 앱 예약 작업)가 오늘 저장본(morning-·afternoon-YYYYMMDD)을 남겼는지 — 11-18 기자 '다음 업데이트'.
// 11-18 08:57 아침 발제가 28초 만에 끝나 시작 표시(지시문 0단계)조차 없이 빈 날이 됐고, 같은 날 08:43 알림도 25초 만에 끝났다.
// 알림은 위 alertHealth가 다음 날 기록 줄로 잡지만 아침 발제는 아무 화면에도 안 보였다(11-13 등 평일 저장본 없는 날이 이미 여러 번).
// 아침 발제는 0단계에서 '진행 중(시작 HH:MM)'을 먼저 저장한다 — 저장본이 아예 없으면 첫 도구 호출 전에 끝난 것, '진행 중'이 남아 있으면 중간에 끊긴 것.
// 오후 체크는 끝에서 한 번만 저장한다. 공휴일은 따로 보지 않는다(평일 공휴일에 아침 발제가 쉬면 이 줄이 뜬다).
// 11-19 기자가 아침 발제 초안 예약 작업을 직접 지웠다("필요없어서") — 그 뒤 '저장본 없음'이 이틀 떴다. 목록에서 뺀다
// (taskGap의 '진행 중' 처리(start)는 그대로 둔다 — 다시 시작 표시를 남기는 작업이 생기면 쓴다).
export const DAILY_TASKS = [
  { label: '오후 출입처 공시 체크', prefix: 'afternoon', at: [14, 20], weekdays: false, graceMin: 40, sched: '매일 14:20', start: false },
];
const STALL_MIN = 60;

const kstMinutes = (k) => k.getUTCHours() * 60 + k.getUTCMinutes();
const dueAt = (task) => task.at[0] * 60 + task.at[1] + task.graceMin;
// 오늘 그 작업을 물을 때인가(평일만 도는 작업의 주말, 예약 시각+여유 전은 묻지 않는다)
export function taskDue(nowMs, task) {
  const k = new Date(nowMs + KST_MS);
  const wd = k.getUTCDay();
  return !(task.weekdays && (wd === 0 || wd === 6)) && kstMinutes(k) >= dueAt(task);
}

// 오늘 그 작업의 저장본(row: packages 줄 또는 null)을 보고 문제 줄(없으면 null)
export function taskGap(nowMs, task, row) {
  if (!taskDue(nowMs, task)) return null;
  const k = new Date(nowMs + KST_MS);
  const minutes = kstMinutes(k);
  const due = dueAt(task);
  const head = `${task.label}(Claude 앱 예약 작업, ${task.sched}): ⚠ 오늘(${k.toISOString().slice(5, 10)})`;
  if (!row) {
    return `${head} 저장본 없음${task.start ? ' — 시작 표시도 없어 실행이 첫 조회 전에 끝났을 수 있다(사용 한도·커넥터 연결 등)' : ' — 실행이 실패했을 수 있다(사용 한도 등)'}.`
      + ` 오늘 ${task.label} 내용은 미확인 — 대화에서 다시 요청하거나 Claude 앱 예약 작업 실행 기록 확인`;
  }
  if (/진행 중/.test(String(row.title ?? '')) && minutes >= due + STALL_MIN) {
    const at = Date.parse(row.updated_at);
    return `${head} '진행 중' 표시 그대로${Number.isFinite(at) ? `(마지막 저장 ${kstStamp(at).slice(6, 11)})` : ''} — 실행이 중간에 끊겼다. 남은 본문까지만 확인됨`;
  }
  return null;
}

export async function taskHealth(ctx) {
  const nowMs = ctx.now.getTime();
  const day = kstDay(nowMs);
  const due = DAILY_TASKS.filter((t) => taskDue(nowMs, t));
  const rows = await Promise.all(due.map((t) => storeOp(ctx, 'packages.get', { name: `${t.prefix}-${day}` })));
  return due.map((t, i) => taskGap(nowMs, t, rows[i]?.row ?? null)).filter(Boolean);
}
