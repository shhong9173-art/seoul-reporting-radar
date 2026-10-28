// Only server-fetched evidence can satisfy the recommendation gate. Receipts
// are private, expire after 24 hours, and never contain a complete document.
import { beatName, REGISTRY_NAMES } from './common.mjs';

export async function evidenceOp(ctx, action, args) {
  if (!ctx.private || !ctx.env?.STORE) throw new Error('기자 전용 검증 저장소 연결 필요');
  const stub = ctx.env.STORE.get(ctx.env.STORE.idFromName('reporter'));
  const r = await stub.fetch('https://store.internal/op', { method: 'POST',
    body: JSON.stringify({ action, args, now: ctx.now.toISOString() }) });
  if (!r.ok) throw new Error('검증 기록 저장소 조회 실패');
  return r.json();
}

export async function issueEvidence(ctx, kind, data) {
  if (!ctx.private) return '검증 기록: 공개 연결에서는 발급하지 않음(조회만 가능)';
  try {
    const id = crypto.randomUUID();
    await evidenceOp(ctx, 'evidence.put', { id, body: JSON.stringify({ kind, ...data }) });
    return `검증 기록 ID: ${id} (24시간 유효, ${kind})`;
  } catch { return '검증 기록 저장 실패 — 조회 내용은 추천 근거로 인증되지 않음'; }
}

export function validDay(s) {
  if (typeof s !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(s)) return false;
  const t = Date.parse(s + 'T00:00:00Z');
  return Number.isFinite(t) && new Date(t).toISOString().slice(0, 10) === s;
}

// Only explicit publication labels count. A date elsewhere (deadline, footer,
// reporting period) is not a publication date. Unknown remains unknown.
export function publicationDate(raw, url) {
  const u = new URL(url);
  const rcp = u.hostname === 'dart.fss.or.kr' && u.searchParams.get('rcpNo');
  if (rcp && /^\d{14}$/.test(rcp)) {
    const day = `${rcp.slice(0, 4)}-${rcp.slice(4, 6)}-${rcp.slice(6, 8)}`;
    return validDay(day) ? day : null;
  }
  const dates = new Set();
  const patterns = [
    /["']datePublished["']\s*:\s*["'](\d{4}-\d{2}-\d{2})/g,
    /(?:게시일|등록일|작성일|공개일|발행일)\s*(?:<[^>]*>|\s|:)*?(\d{4})[-./년]\s*(\d{1,2})[-./월]\s*(\d{1,2})/g,
  ];
  for (const re of patterns) for (const m of raw.matchAll(re)) {
    const d = m[2] ? `${m[1]}-${m[2].padStart(2, '0')}-${m[3].padStart(2, '0')}` : m[1];
    if (validDay(d)) dates.add(d);
  }
  for (const tag of raw.matchAll(/<meta\b[^>]*>/gi)) {
    if (!/(?:property|name)\s*=\s*["'](?:article:published_time|datePublished)["']/i.test(tag[0])) continue;
    const d = /content\s*=\s*["'](\d{4}-\d{2}-\d{2})/.exec(tag[0])?.[1];
    if (validDay(d)) dates.add(d);
  }
  return dates.size === 1 ? [...dates][0] : null;
}

const entityIn = (name, text) => {
  const escaped = String(name).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return new RegExp(`(?<![A-Za-z0-9가-힣])${escaped}(?:(?:에서는|으로|에서|은|는|이|가|의|을|를|와|과|도))?(?![A-Za-z0-9가-힣])`, 'i').test(text);
};
const norm = (s) => String(s ?? '').replace(/\s+/g, ' ').trim();
export async function verifyEvidence(ctx, c) {
  const hold = [];
  const read = async (id, kind) => {
    if (typeof id !== 'string' || !/^[0-9a-f-]{36}$/.test(id)) return null;
    try {
      const { row } = await evidenceOp(ctx, 'evidence.get', { id });
      const age = ctx.now.getTime() - Date.parse(row?.created_at);
      if (!row || !Number.isFinite(age) || age < 0 || age > 86400000) return null;
      const r = JSON.parse(row.body);
      return r.kind === kind ? r : null;
    } catch { return null; }
  };
  const source = await read(c.source_evidence_id, 'source');
  let sourceOk = false;
  const facts = Array.isArray(c.facts) ? c.facts : [];
  const companies = Array.isArray(c.companies) ? c.companies : [];
  const names = companies.flatMap((n) => [n, beatName(n), ...Object.keys(REGISTRY_NAMES).filter((a) => REGISTRY_NAMES[a] === beatName(n))]).filter(Boolean);
  if (!source) hold.push('유효한 원문 검증 기록 없음 — 기자 전용 source_document·dart_find_text로 다시 조회');
  else {
    if (source.url !== c.source_url || source.hash !== String(c.content_hash ?? '').replace(/^sha256:/, '')) hold.push('원문 URL·해시가 실제 조회 기록과 다름');
    if (!source.date || c.source_date !== source.date) hold.push('원자료 게시일을 원문에서 확인하지 못했거나 입력 날짜와 다름');
    const today = new Date(ctx.now.getTime() + 9 * 3600000).toISOString().slice(0, 10);
    if (!validDay(c.source_date) || c.source_date > today) hold.push('게시일 누락·오류·미래 날짜');
    else if (Date.parse(today) - Date.parse(c.source_date) > 30 * 86400000) hold.push('30일 이전 원자료 — 최근 변화의 별도 원문 확인 필요');
    if (!facts.length || facts.some((f) => typeof f !== 'string' || norm(f).length < 8 || !norm(source.excerpt).includes(norm(f)))) hold.push('facts는 실제 읽은 원문 구간의 직접 인용이어야 함(요약·해석은 impact에 구분)');
    const quotes = facts.map(norm).join('\n');
    if (!names.some((n) => entityIn(n, quotes))) hold.push('원문 인용의 해당 기업명 직접 확인 필요');
    if ((c.numbers ?? []).some((n) => !quotes.includes(norm(n)))) hold.push('원문 인용에서 확인되지 않은 수치');
    sourceOk = hold.length === 0;
  }
  const ids = [...new Set(Array.isArray(c.news_evidence_ids) ? c.news_evidence_ids : [])].slice(0, 5);
  const records = (await Promise.all(ids.map((id) => read(id, 'news')))).filter(Boolean);
  const terms = Array.isArray(c.event_terms) ? c.event_terms.filter((s) => typeof s === 'string' && s.length >= 2) : [];
  const relevant = records.filter((r) => names.some((n) => entityIn(n, r.q)) && terms.some((t) => r.q.includes(t) && facts.some((f) => String(f).includes(t))));
  const distinct = new Set(relevant.map((r) => norm(r.q))).size >= 2;
  if (!distinct) hold.push('동일 기업·원문 사건 낱말로 바꿔 조회한 보도 검증 기록 2개 필요');
  const channelsOk = distinct && relevant.every((r) => r.days >= 365 && r.complete);
  if (!channelsOk) hold.push('실제 보도 조회 기록의 필수 채널 실패·범위 부족·미확인 — 입력한 ok로 대체할 수 없음');
  const hits = relevant.reduce((n, r) => n + r.hits, 0);
  if (hits) hold.push('검색된 관련 기사 있음 — 같은 사건인지 기자가 원문 대조해야 함');
  if ((c.derived_numbers ?? []).length) hold.push('파생 수치 계산은 아직 서버 검증하지 않음 — 원문 수치로 제출');
  return { hold, sourceOk, channelsOk, unreported: channelsOk && !hits,
    verdict: !channelsOk ? '미확인' : hits ? '관련 보도 검토 필요' : '검색 범위 내 미발견·단독 미확정',
    quotes: sourceOk ? facts : [] };
}
