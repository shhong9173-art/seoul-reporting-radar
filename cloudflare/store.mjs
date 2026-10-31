// Private reporter state: scoop packages, submitted candidates, keep/kill
// feedback. Lives in a SQLite-backed Durable Object behind the access token,
// never in the public repository or GitHub Pages.
import { POLICY, checkVerifiedCandidate, formatCheck } from './scoring.mjs';
import { kstDate, textResult } from './common.mjs';

export const PACKAGE_STATES = ['미발제·확인 필요', '발제함', '보류', '접음'];
export const FEEDBACK_VERDICTS = ['씀', '킬', '보류', '봤음'];

const SCHEMA = [
  `CREATE TABLE IF NOT EXISTS evidence (id TEXT PRIMARY KEY, body TEXT NOT NULL, created_at TEXT NOT NULL)`,
  `CREATE TABLE IF NOT EXISTS packages (name TEXT PRIMARY KEY, title TEXT NOT NULL, state TEXT NOT NULL,
     body TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)`,
  `CREATE TABLE IF NOT EXISTS candidates (id INTEGER PRIMARY KEY AUTOINCREMENT, day TEXT NOT NULL, title TEXT NOT NULL,
     status TEXT NOT NULL, score INTEGER NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL)`,
  `CREATE TABLE IF NOT EXISTS feedback (id INTEGER PRIMARY KEY AUTOINCREMENT, item_id TEXT NOT NULL, verdict TEXT NOT NULL,
     reason TEXT NOT NULL, created_at TEXT NOT NULL)`,
  `CREATE TABLE IF NOT EXISTS blobs (name TEXT PRIMARY KEY, body TEXT NOT NULL, updated_at TEXT NOT NULL)`,
  // 홈페이지 로그인 실패 기록(아이피별·전체 1시간 잠금 계산용, 하루 지나면 지움)
  `CREATE TABLE IF NOT EXISTS login_fail (ip TEXT NOT NULL, at TEXT NOT NULL)`,
  // what a judged item was when it was judged (watch, kind, tier) — feeds roll over, the weekly review still needs it
  `CREATE TABLE IF NOT EXISTS feedback_meta (item_id TEXT PRIMARY KEY, watch TEXT NOT NULL, kind TEXT NOT NULL,
     tier TEXT NOT NULL, flag TEXT NOT NULL, title TEXT NOT NULL, updated_at TEXT NOT NULL)`,
];

// Durable Object (fetch-style so it runs without the cloudflare:workers import).
export class RadarStore {
  constructor(state, env) {
    this.sql = state.storage.sql;
    this.env = env;
    for (const q of SCHEMA) this.sql.exec(q);
  }

  all(query, ...params) { return this.sql.exec(query, ...params).toArray(); }

  async fetch(request) {
    let op;
    try { op = await request.json(); } catch { return Response.json({ error: 'bad request' }, { status: 400 }); }
    try {
      return Response.json(await this.run(op));
    } catch (e) {
      return Response.json({ error: String(e.message ?? e) }, { status: 400 });
    }
  }

  run({ action, args = {}, now }) {
    const at = now ?? new Date().toISOString();
    switch (action) {
      case 'evidence.put':
        // Bounded private excerpts, 24-hour retention. No public ingest route.
        this.sql.exec('DELETE FROM evidence WHERE created_at < ?', new Date(Date.parse(at) - 86400000).toISOString());
        this.sql.exec('INSERT INTO evidence (id, body, created_at) VALUES (?, ?, ?)', args.id, args.body, at);
        this.sql.exec('DELETE FROM evidence WHERE id NOT IN (SELECT id FROM evidence ORDER BY created_at DESC LIMIT 1000)');
        return { saved: true };
      case 'evidence.get':
        return { row: this.all('SELECT body, created_at FROM evidence WHERE id = ?', args.id)[0] ?? null };
      case 'packages.list':
        return { rows: this.all('SELECT name, title, state, updated_at FROM packages ORDER BY updated_at DESC LIMIT 200') };
      case 'packages.get':
        return { row: this.all('SELECT * FROM packages WHERE name = ?', args.name)[0] ?? null };
      case 'packages.save': {
        const existing = this.all('SELECT created_at FROM packages WHERE name = ?', args.name)[0];
        this.sql.exec(`INSERT INTO packages (name, title, state, body, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)
          ON CONFLICT(name) DO UPDATE SET title = excluded.title, state = excluded.state, body = excluded.body,
          updated_at = excluded.updated_at`, args.name, args.title, args.state, args.body, existing?.created_at ?? at, at);
        return { saved: true, created: !existing };
      }
      case 'candidates.today':
        return { rows: this.all('SELECT id, title, status, score FROM candidates WHERE day = ? ORDER BY id', args.day) };
      case 'candidates.add': {
        this.sql.exec('INSERT INTO candidates (day, title, status, score, payload, created_at) VALUES (?, ?, ?, ?, ?, ?)',
          args.day, args.title, args.status, args.score, args.payload, at);
        return { id: this.all('SELECT last_insert_rowid() AS id')[0].id };
      }
      case 'feedback.add': {
        this.sql.exec('INSERT INTO feedback (item_id, verdict, reason, created_at) VALUES (?, ?, ?, ?)',
          args.item_id, args.verdict, args.reason, at);
        const m = args.meta;
        if (m?.watch) {
          this.sql.exec(`INSERT INTO feedback_meta (item_id, watch, kind, tier, flag, title, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(item_id) DO UPDATE SET watch = excluded.watch, kind = excluded.kind, tier = excluded.tier,
            flag = excluded.flag, title = excluded.title, updated_at = excluded.updated_at`,
          args.item_id, String(m.watch), String(m.kind ?? ''), String(m.tier ?? ''), String(m.flag ?? ''), String(m.title ?? '').slice(0, 160), at);
        }
        return { saved: true };
      }
      case 'blobs.put':
        this.sql.exec(`INSERT INTO blobs (name, body, updated_at) VALUES (?, ?, ?)
          ON CONFLICT(name) DO UPDATE SET body = excluded.body, updated_at = excluded.updated_at`, args.name, args.body, at);
        return { saved: true };
      case 'blobs.get':
        return { row: this.all('SELECT name, body, updated_at FROM blobs WHERE name = ?', args.name)[0] ?? null };
      case 'login.count': {
        this.sql.exec('DELETE FROM login_fail WHERE at < ?', args.purgeBefore);
        const ip = this.all('SELECT COUNT(*) AS n FROM login_fail WHERE ip = ? AND at >= ?', args.ip, args.since)[0]?.n ?? 0;
        const all = this.all('SELECT COUNT(*) AS n FROM login_fail WHERE at >= ?', args.since)[0]?.n ?? 0;
        return { ip, all };
      }
      case 'login.fail':
        this.sql.exec('INSERT INTO login_fail (ip, at) VALUES (?, ?)', String(args.ip ?? '?').slice(0, 64), at);
        return { saved: true };
      case 'feedback.latest':
        return { rows: this.all(`SELECT f.item_id, f.verdict, f.reason FROM feedback f
          JOIN (SELECT item_id, MAX(id) AS id FROM feedback GROUP BY item_id) m ON f.id = m.id`) };
      case 'feedback.since':
        return { rows: this.all(`SELECT f.item_id, f.verdict, f.reason, f.created_at, m.watch, m.kind, m.tier, m.flag, m.title
            FROM feedback f LEFT JOIN feedback_meta m ON m.item_id = f.item_id WHERE f.created_at >= ? ORDER BY f.id DESC`, args.since),
          candidates: this.all('SELECT id, day, title, status, score FROM candidates WHERE created_at >= ? ORDER BY id DESC', args.since) };
      default:
        throw new Error('unknown action');
    }
  }
}

export async function storeOp(ctx, action, args) {
  return call(ctx, action, args);
}

async function call(ctx, action, args) {
  if (!ctx.env?.STORE) throw new Error('저장소(Durable Object) 바인딩 없음');
  const stub = ctx.env.STORE.get(ctx.env.STORE.idFromName('reporter'));
  const r = await stub.fetch('https://store.internal/op', { method: 'POST',
    body: JSON.stringify({ action, args, now: ctx.now.toISOString() }) });
  const body = await r.json();
  if (!r.ok) throw new Error(body.error ?? `store HTTP ${r.status}`);
  return body;
}

const slug = (s) => String(s ?? '').trim().toLowerCase().replace(/[^a-z0-9가-힣-]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 60);

export async function scoopPackages(ctx, args) {
  const name = slug(args.name);
  if (!name) {
    const { rows } = await call(ctx, 'packages.list', {});
    const out = [`취재 패키지 ${rows.length}건 · 상태: ${PACKAGE_STATES.join(' / ')}`,
      '규칙: 발제함=후속만 · 접음=내지 않음 · 보류=새 사실 붙을 때만 · 미발제·확인 필요=디벨롭 대상'];
    for (const r of rows) out.push(`[${r.state}] ${r.name} — ${r.title} (수정 ${String(r.updated_at).slice(0, 16)})`);
    if (!rows.length) out.push('아직 저장된 패키지 없음. package_save로 만든다.');
    return textResult(out.join('\n'));
  }
  const { row } = await call(ctx, 'packages.get', { name });
  if (!row) return textResult(`패키지 '${name}' 없음`, true);
  return textResult(`[${row.state}] ${row.name} — ${row.title}\n생성 ${row.created_at} · 수정 ${row.updated_at}\n---\n${row.body}`);
}

export async function packageSave(ctx, args) {
  const name = slug(args.name);
  const title = String(args.title ?? '').trim().slice(0, 200);
  const state = PACKAGE_STATES.includes(args.state) ? args.state : null;
  const body = String(args.body ?? '').trim();
  if (!name || !title || !state || !body) {
    return textResult(`name·title·body와 state(${PACKAGE_STATES.join('/')})가 모두 필요하다.`, true);
  }
  if (body.length > 60000) return textResult('본문이 6만 자를 넘는다. 원문은 링크로 남긴다.', true);
  const r = await call(ctx, 'packages.save', { name, title, state, body });
  return textResult(`${r.created ? '새로 저장' : '갱신'}: [${state}] ${name} — ${title}`);
}

export async function candidateSubmit(ctx, args) {
  const list = Array.isArray(args.candidates) ? args.candidates.slice(0, 10) : [];
  if (!list.length) return textResult('candidates 배열이 비어 있다.', true);
  const day = kstDate(ctx.now);
  const { rows } = await call(ctx, 'candidates.today', { day });
  let used = rows.filter((r) => r.status === '추천').length;
  const out = [`후보 제출 · ${day} · 오늘 추천 저장 ${used}/${POLICY.dailyLimit}`];
  for (const c of list) {
    const result = await checkVerifiedCandidate(ctx, c);
    if (rows.some((r) => r.title === result.title)) { out.push(`\n- 중복(오늘 이미 제출): ${result.title}`); continue; }
    let status = result.status;
    if (status === '추천' && used >= POLICY.dailyLimit) status = '조사대기(하루 한도 초과)';
    if (status === '추천') used++;
    const saved = await call(ctx, 'candidates.add', { day, title: result.title, status, score: result.score,
      payload: JSON.stringify(c).slice(0, 60000) });
    out.push(`\n- [${status}] #${saved.id} ${result.title} (점수 ${result.score})`);
    if (status !== '추천') out.push('  ' + formatCheck(result).split('\n').slice(2).join('\n  '));
  }
  out.push('\n※ 저장·점수는 정리용. 단독 판정과 발제 여부는 기자가 정한다.');
  return textResult(out.join('\n'));
}

// index: id → { watch, kind, tier, flag, title } from radar_today's view (review.mjs), so the weekly review can group.
export async function candidateFeedback(ctx, args, index = null) {
  const verdict = FEEDBACK_VERDICTS.includes(args.verdict) ? args.verdict : null;
  // one id, or several at once (e.g. marking today's radar_today items as 봤음)
  const ids = [...new Set([args.item_id, ...(Array.isArray(args.item_ids) ? args.item_ids : [])]
    .map((x) => String(x ?? '').trim().slice(0, 160)).filter(Boolean))].slice(0, 60);
  const reason = String(args.reason ?? '').trim().slice(0, 1000) || (verdict === '봤음' ? '확인함(판단 전)' : '');
  if (!verdict || !ids.length || !reason) return textResult(`item_id(또는 item_ids)·reason과 verdict(${FEEDBACK_VERDICTS.join('/')})가 필요하다. 봤음은 reason 생략 가능.`, true);
  for (const item of ids) await call(ctx, 'feedback.add', { item_id: item, verdict, reason, meta: index?.get(item) ?? null });
  const label = (id) => { const m = index?.get(id); return m ? ` (${m.watch}${m.kind ? ` · ${m.kind}` : ''} · ${m.tier})` : ''; };
  return textResult(ids.length === 1 ? `기록: [${verdict}] ${ids[0]}${label(ids[0])} — ${reason}`
    : `기록: [${verdict}] ${ids.length}건 — ${reason}\n${ids.map((id) => id + label(id)).join('\n')}`);
}
