// 국회 법안(열린국회정보 국회의원 발의법률안, 평일 08:40·17:40 수집). 저장된 결과만 읽는다.
import { ageNote, readFeed } from './screen.mjs';
import { clampInt, textResult } from './common.mjs';

const KST_MS = 9 * 3600000;
const has = (q, ...fields) => !q || fields.some((f) => String(f ?? '').toLowerCase().includes(q.toLowerCase()));

// Same law, same day, same kind → one line (several lawmakers often file amendments to one law together).
export function groupBillEvents(doc, { since = '', all = false } = {}) {
  const bills = new Map((doc?.bills ?? []).map((b) => [b.id, b]));
  const groups = new Map();
  for (const e of doc?.events ?? []) {
    if (!all && String(e.detectedAt ?? '') < since) continue;
    const b = bills.get(e.billId) ?? {};
    const key = e.kind === '발의' ? `발의|${e.law}|${e.date}` : `${e.kind}|${e.billId}`;
    const g = groups.get(key) ?? { id: `bills:${key}`, kind: e.kind, law: e.law, date: e.date, core: e.core ?? null, detectedAt: e.detectedAt,
      leads: [], names: new Set(), urls: [], committee: b.committee ?? null, from: e.from ?? null, count: 0 };
    g.count += 1;
    if (e.lead && !g.leads.includes(e.lead)) g.leads.push(e.lead);
    if (b.name) g.names.add(b.name);
    if (b.url) g.urls.push(b.url);
    if (String(e.detectedAt) > String(g.detectedAt)) g.detectedAt = e.detectedAt;
    groups.set(key, g);
  }
  return [...groups.values()].map((g) => ({ ...g, names: [...g.names] }));
}

export function billLine(g) {
  const who = g.leads.length ? ` — ${g.leads.slice(0, 4).join('·')}${g.leads.length > 4 ? ` 외 ${g.leads.length - 4}` : ''} 대표발의` : '';
  if (g.kind === '발의') return `법안 발의: ${g.names[0] ?? g.law}${g.count > 1 ? ` 등 ${g.count}건` : ''}${who}`;
  return `법안 ${g.kind}: ${g.names[0] ?? g.law}${g.from ? ` (직전 ${g.from})` : ''}${who}`;
}

export async function assemblyBills(ctx, args) {
  const doc = await readFeed(ctx, 'assembly-bills');
  if (!doc) return textResult('국회 법안 감시 결과가 아직 없음 — GitHub Secrets의 ASSEMBLY_API_KEY·MCP_ACCESS_TOKEN과 다음 정기 실행(평일 08:40·17:40)을 확인. 0건이 아니라 미확인.', true);
  if (doc.broken) return textResult('저장된 국회 법안 결과 형식 오류 — 미확인.', true);
  const q = String(args.law ?? '').trim();
  const days = clampInt(args.days, 1, 120, 14);
  const limit = clampInt(args.limit, 1, 80, 25);
  const coreOnly = !(args.include_related === true || args.include_related === 'true');
  const since = new Date(ctx.now.getTime() - days * 86400000).toISOString();
  const sinceDay = new Date(ctx.now.getTime() + KST_MS - days * 86400000).toISOString().slice(0, 10);
  const checks = doc.checks ?? [];
  const bad = checks.filter((c) => !['ok', 'unset'].includes(c.status));
  const out = [`국회 법안(국회의원 발의법률안 · 출입 업종) · 확인 ${String(doc.generatedAt).slice(0, 16)}${ageNote(ctx, doc.generatedAt)}`,
    checks.map((c) => `${c.source} ${c.status}${c.listed !== undefined ? ` ${c.listed}건 중 업종 ${c.kept}건` : ''}${c.checked !== undefined ? ` ${c.checked}/${c.tracked}건 재확인` : ''}${c.error ? `(${c.error})` : ''}`).join(' · '),
    ...(bad.length ? [`미확인(0건 아님): ${bad.map((c) => c.source).join(', ')}`] : []),
    ...(doc.rules ?? []).map((r) => `규칙: ${r}`)];
  if (!doc.baselineSince) out.push('\n아직 기준선 없음 — 첫 성공 실행 뒤부터 새 발의·단계 변화를 센다.');

  const ev = groupBillEvents(doc, { since }).filter((g) => (!coreOnly || g.core) && has(q, g.law, ...g.names, ...g.leads));
  const newOnes = ev.filter((g) => g.kind === '발의').sort((a, b) => String(b.date).localeCompare(String(a.date)));
  const moved = ev.filter((g) => g.kind !== '발의').sort((a, b) => String(b.date).localeCompare(String(a.date)));
  out.push(`\n[새 발의 · 최근 ${days}일${coreOnly ? ' · 출입처 직결 법(core)' : ''}] ${newOnes.length}묶음`);
  for (const g of newOnes.slice(0, limit)) {
    out.push(`- ${g.date} · ${g.core ? `[${g.core}] ` : ''}${billLine(g)}`);
    if (g.urls[0]) out.push(`   의안: ${g.urls[0]}${g.urls.length > 1 ? ` 외 ${g.urls.length - 1}` : ''}`);
  }
  if (!newOnes.length) out.push('없음');
  out.push(`\n[단계 변화 · 최근 ${days}일] ${moved.length}건`);
  for (const g of moved.slice(0, limit)) {
    out.push(`- ${g.date} · ${g.core ? `[${g.core}] ` : ''}${billLine(g)}${g.committee ? ` · ${g.committee}` : ''}`);
    if (g.urls[0]) out.push(`   의안: ${g.urls[0]}`);
  }
  if (!moved.length) out.push('없음');

  const open = (doc.bills ?? []).filter((b) => (!coreOnly || b.core) && b.stageIndex > 0 && b.stageIndex < 7 && has(q, b.law, b.name, b.lead));
  if (open.length) {
    out.push(`\n[진행 중(소관위 회부 이후) · 단계별] ${open.length}건`);
    const byStage = {};
    for (const b of open) (byStage[b.stage] ??= []).push(b);
    for (const [stage, rows] of Object.entries(byStage)) out.push(`- ${stage} ${rows.length}건: ${rows.slice(0, 5).map((b) => `${b.law}(${b.lead || '?'})`).join(', ')}${rows.length > 5 ? ' …' : ''}`);
  }
  const recent = (doc.bills ?? []).filter((b) => b.proposedOn >= sinceDay).length;
  out.push(`\n(저장된 업종 법안 ${doc.bills?.length ?? 0}건 · 최근 ${days}일 발의 ${recent}건${coreOnly ? ' · 관련 낱말(C)까지 보려면 include_related=true' : ''})`);
  out.push('검증 상태: 열린국회정보 공개 의정 정보(자동 수집, 법안 이름으로 분류). 내용·출입처 영향은 의안 원문의 제안이유로 확인.');
  out.push('다음: 의안 링크에서 제안이유·주요내용 확인 → 대표발의 의원실·소관 부처 입장 → news_check(법안명·핵심 낱말) → 출입처에 영향 질의.');
  return textResult(out.join('\n'));
}
