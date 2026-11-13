// GitHub 실행 실패 감시(11-08): 보도 대조(radar-press-check.yml)가 11-05 18:50부터 7번 연달아 실패했는데, radar_today에는
// 36시간 뒤에야 '⚠ 60시간 전 결과'로 드러났다(감시 결과 문서의 나이만 보기 때문). Cloudflare 예약(10분마다) 중 KST 매시 00·30분 칸에
// main 가지의 끝난 실행 100개를 읽어 워크플로마다 최근 결과를 비공개 저장소에 이어 쌓고, radar_today가 두 번 이상 연달아 실패한
// 워크플로를 맨 위에 알린다. 저장소가 공개라 실행 목록 자체도 공개 정보다(로그·결과 내용은 읽지 않는다).
import { storeOp } from './store.mjs';

const REPO = 'shhong9173-art/seoul-reporting-radar';
const KST_MS = 9 * 3600000;
const BLOB = 'gh_runs';
const KEEP = 8;                          // 워크플로마다 남기는 최근 실행 수
const DROP_DAYS = 30;                    // 30일 넘게 안 돈 워크플로(지운 것 등)는 잊는다
export const FAIL = new Set(['failure', 'timed_out', 'startup_failure']);
const IGNORE = new Set(['cancelled', 'skipped', 'neutral', 'action_required', 'stale']);  // 세지 않음(성공도 실패도 아님)
export const STREAK_ALERT = 2;
// 한 번만 실패해도 알리는 워크플로: 배포 뒤 운영 점검(worker-smoke.yml)은 실패 = 운영 도구가 끊겼을 수 있다는 뜻이다(11-13 오류 1102).
const ALERT_AT = { 'worker-smoke.yml': 1 };
const STALE_MS = 2 * 3600000;            // 확인이 두 시간 넘게 없으면 이 감시 자체가 미확인

const kst = (ms) => new Date(ms + KST_MS).toISOString().slice(5, 16).replace('T', ' ');

export function pollDue(when) {
  const m = new Date(when.getTime() + KST_MS).getUTCMinutes();
  return Math.floor(m / 10) === 0 || Math.floor(m / 10) === 3;  // 매시 00·30분 칸
}

// 이전 상태 + 새로 읽은 실행 → 워크플로별 최근 실행(같은 id는 새 값으로 덮음: 다시 실행하면 결과가 바뀐다)
export function mergeRuns(prev, runs, nowMs) {
  const out = {};
  for (const [k, w] of Object.entries(prev ?? {})) out[k] = { ...w, runs: [...(w.runs ?? [])] };
  for (const r of runs ?? []) {
    if (r?.status !== 'completed' || !r.path || !r.id) continue;
    const key = String(r.path).replace(/^\.github\/workflows\//, '').replace(/@.*$/, '');
    const w = out[key] ?? { name: r.name, runs: [] };
    w.name = String(r.name ?? key).slice(0, 80);
    const run = { id: r.id, at: r.run_started_at ?? r.created_at, c: r.conclusion ?? null, e: r.event ?? null };
    w.runs = [run, ...w.runs.filter((x) => x.id !== r.id)].sort((a, b) => String(b.at).localeCompare(String(a.at))).slice(0, KEEP);
    if (run.c === 'success' && !(Date.parse(w.lastSuccessAt ?? '') >= Date.parse(run.at))) w.lastSuccessAt = run.at;
    out[key] = w;
  }
  for (const [k, w] of Object.entries(out)) if (!(Date.parse(w.runs[0]?.at ?? '') > nowMs - DROP_DAYS * 86400000)) delete out[k];
  return out;
}

// 가장 최근부터 연달아 실패한 수(취소·건너뜀은 세지 않고 지나감, 성공을 만나면 멈춤)
export function failStreak(w) {
  let n = 0;
  for (const r of w?.runs ?? []) {
    if (IGNORE.has(r.c)) continue;
    if (FAIL.has(r.c)) { n += 1; continue; }
    break;
  }
  return n;
}

async function readState(ctx) {
  const { row } = await storeOp(ctx, 'blobs.get', { name: BLOB });
  if (!row) return null;
  try { return JSON.parse(row.body); } catch { return { broken: true }; }
}

export async function pollRuns(env, when, doFetch = fetch) {
  const ctx = { env, now: when };
  const prev = await readState(ctx);
  const base = prev && !prev.broken ? prev : {};
  let status = 'ok';
  let runs = [];
  if (!env?.GITHUB_DISPATCH_TOKEN) status = 'no-token';
  else {
    try {
      const r = await doFetch(`https://api.github.com/repos/${REPO}/actions/runs?branch=main&status=completed&per_page=100&exclude_pull_requests=true`, {
        headers: { Authorization: `Bearer ${env.GITHUB_DISPATCH_TOKEN}`, Accept: 'application/vnd.github+json',
          'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'seoul-reporting-radar-cron' } });
      if (r.status !== 200) status = `HTTP ${r.status}`;
      else {
        const body = await r.json();
        if (!Array.isArray(body?.workflow_runs)) status = '형식 오류';
        else runs = body.workflow_runs;
      }
    } catch (e) {
      status = e?.name ?? 'error';
    }
  }
  const doc = { checkedAt: when.toISOString(), status, ...(status === 'ok' ? { okAt: when.toISOString() } : { okAt: base.okAt ?? null }),
    workflows: mergeRuns(base.workflows, runs, when.getTime()) };
  await storeOp(ctx, 'blobs.put', { name: BLOB, body: JSON.stringify(doc) });
  return { status, runs: runs.length };
}

// radar_today 맨 위 줄들(없으면 빈 배열)
export async function runsHealth(ctx) {
  const doc = await readState(ctx);
  const label = 'GitHub 실행 상태(30분마다 확인)';
  if (!doc) return [`${label}: 확인 기록 없음 — 감시 프로그램 실패 여부 미확인`];
  if (doc.broken) return [`${label}: 저장 형식 오류 — 미확인`];
  const nowMs = ctx.now.getTime();
  const lines = [];
  const okAt = Date.parse(doc.okAt ?? '');
  if (doc.status !== 'ok' || !(okAt > nowMs - STALE_MS)) {
    const why = doc.status === 'no-token' ? '워커에 GITHUB_DISPATCH_TOKEN 없음' : doc.status !== 'ok' ? `읽기 실패(${doc.status})` : '확인이 멈춤';
    lines.push(`${label}: ${why} · 마지막 정상 확인 ${Number.isFinite(okAt) ? `${kst(okAt)} KST` : '없음'} — 그 뒤 실패는 미확인`);
  }
  const bad = Object.entries(doc.workflows ?? {}).map(([file, w]) => ({ file, w, n: failStreak(w) })).filter((x) => x.n >= (ALERT_AT[x.file] ?? STREAK_ALERT))
    .sort((a, b) => b.n - a.n || String(b.w.runs[0]?.at).localeCompare(String(a.w.runs[0]?.at)));
  for (const { file, w, n } of bad.slice(0, 6)) {
    const last = Date.parse(w.runs[0]?.at ?? '');
    const ok = Date.parse(w.lastSuccessAt ?? '');
    if (file === 'worker-smoke.yml') {
      lines.push(`⚠ 배포 뒤 운영 점검 실패(${n}회 연속): 기자 전용 도구 일부가 운영에서 끊겼을 수 있다(오류 1102 등) · 마지막 실패 ${Number.isFinite(last) ? `${kst(last)} KST` : '?'}`
        + ` · 마지막 성공 ${Number.isFinite(ok) ? `${kst(ok)} KST` : '기록 없음'} — 실패한 도구의 0건·오류는 미확인`);
      continue;
    }
    lines.push(`⚠ GitHub 실행 ${n}회 연속 실패: ${w.name}(${file}) · 마지막 실패 ${Number.isFinite(last) ? `${kst(last)} KST` : '?'}`
      + ` · 마지막 성공 ${Number.isFinite(ok) ? `${kst(ok)} KST` : `기록 없음(최근 ${w.runs.length}번 안)`} — 이 프로그램이 만드는 결과는 그 성공 때 것, 그 뒤 0건은 미확인`);
  }
  if (bad.length > 6) lines.push(`⚠ GitHub 실행 연속 실패 ${bad.length - 6}개 더: ${bad.slice(6).map((x) => x.file).join(', ')}`);
  return lines;
}
