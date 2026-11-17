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

// 지금(여유를 뺀 시각)까지 지난 예약 시각 중 기록이 없는 것. 기록은 그 예약 시각부터 다음 예약 시각 전까지 적힌 것을 센다
// (대화에서 늦게 대신 보낸 것 포함). '조회 실패' 줄은 돈 것으로 치지 않는다.
export function alertGaps(nowMs, runs, { since = ALERT_RECORD_SINCE } = {}) {
  const ok = runs.filter((r) => !r.failed).map((r) => r.at);
  const until = nowMs - GRACE_MIN * 60000;
  const from = Math.max(since, nowMs - LOOKBACK_H * 3600000);
  const day0 = Math.floor((nowMs + KST_MS) / 86400000) * 86400000 - KST_MS;
  const slots = [];
  for (let d = 2; d >= 0; d--) for (const [h, mi] of ALERT_SLOTS) slots.push(day0 - d * 86400000 + (h * 60 + mi) * 60000);
  const missed = [];
  slots.forEach((s, i) => {
    if (s < from || s > until) return;
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
