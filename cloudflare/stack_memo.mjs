// 굴뚝 정기보수 메모 — radar_today(digest.mjs)와 kr_official 굴뚝 화면(overseas.mjs)이 같이 쓴다(서로 가져오면 순환 import라 따로 둠).
const KST_MS = 9 * 3600000;
// 정기보수 메모(11-08): 굴뚝 킬 사유 1위가 '회사 확인 결과 정기보수'였다(11-04~07 굴뚝 판정 16건 중 8건 — 현대제철 순천·당진).
// 기자가 굴뚝 항목을 정기보수·정비 사유로 판정하면(킬·보류·봤음 무엇이든) 그 사업장(id의 '회사:사업장')의 멈춤·빠짐 신호를
// 판정 7일 전부터 30일 뒤까지(사유에 '12-05까지'·'12월 5일까지'가 있으면 그날 끝까지) C로 접고 까닭을 붙인다. 기준 초과·새 배출구는 그대로.
export const MAINT_RE = /정기\s*보수|정기\s*점검|대정비|정비|보수\s*(?:중|작업|공사|진행)|대수리|오버홀|셧다운/;
export const MAINT_KINDS = new Set(['사업장 가동 중단 신호', '배출구 멈춤 신호', '배출구 오래 멈춤', '배출구 가동중지 전환',
  '배출구 목록에서 빠짐', '배출구 오래 빠짐', '사업장 목록에서 빠짐(굴뚝 측정)', '사업장 오래 빠짐(굴뚝 측정)']);
const MAINT_DAYS = 30;
const MAINT_BEFORE_DAYS = 7;
export const stackSiteKey = (id) => { const p = String(id ?? '').split(':'); return p[0] === 'stk' && p.length >= 4 ? `${p[2]}:${p[3]}` : null; };
export const kstMD = (ms) => new Date(ms + KST_MS).toISOString().slice(5, 10);
function maintUntil(reason, at) {
  const m = /(\d{1,2})\s*(?:-|\.|\/|월)\s*(\d{1,2})\s*일?\s*까지/.exec(String(reason ?? ''));
  if (!m) return null;
  const y = new Date(at + KST_MS).getUTCFullYear();
  let end = Date.UTC(y, Number(m[1]) - 1, Number(m[2]), 23, 59) - KST_MS;
  if (end < at - 86400000) end = Date.UTC(y + 1, Number(m[1]) - 1, Number(m[2]), 23, 59) - KST_MS;
  return Number.isFinite(end) ? end : null;
}
export function maintenanceMemo(rows) {
  const out = new Map();
  for (const r of rows ?? []) {
    const key = stackSiteKey(r?.item_id);
    const at = Date.parse(r?.created_at ?? '');
    if (!key || !Number.isFinite(at) || !MAINT_RE.test(String(r.reason ?? ''))) continue;
    const until = maintUntil(r.reason, at) ?? at + MAINT_DAYS * 86400000;
    const old = out.get(key);
    const from = Math.min(at - MAINT_BEFORE_DAYS * 86400000, old?.from ?? Infinity);
    if (!old || until > old.until) out.set(key, { from, until, at, reason: String(r.reason).slice(0, 60) });
    else old.from = from;
  }
  return out;
}
export function maintFolded(e, maint) {
  const m = maint?.get(stackSiteKey(e?.id));
  const t = Date.parse(e?.detectedAt ?? '');
  return m && MAINT_KINDS.has(e.kind) && t >= m.from && t <= m.until ? m : null;
}

