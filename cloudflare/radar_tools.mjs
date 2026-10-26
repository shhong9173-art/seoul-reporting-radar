// Read-only tools over the published tool views (tools/*.json).
import {
  TEAM_ORDER, clampInt, fetchJson, kstDate, kstStamp, matchesQuery, teamsFromParam, textResult,
} from './common.mjs';

const COVERAGE_ORDER = { none_in_index: 0, not_compared: 1, index_unavailable: 1, similar_headlines: 2 };
const SHORT_COVERAGE = {
  none_in_index: '색인 0건(미보도 증거 아님)',
  not_compared: '대조 안 함',
  index_unavailable: '대조 불가',
};

function viewAge(view, now) {
  const at = Date.parse(view?.generatedAt ?? '');
  return Number.isFinite(at) ? `${Math.round((now - at) / 3600000 * 10) / 10}시간 전` : '생성 시각 불명';
}

export async function bigPicture(ctx) {
  const v = await fetchJson(ctx, 'tools/big_picture.json');
  const lines = [`큰 그림 · ${kstStamp(ctx.now)} (뷰 생성 ${viewAge(v, ctx.now)})`];
  lines.push('\n■ 최근 7일 원자료 단서(팀별)');
  for (const t of v.cluesLast7DaysByTeam ?? []) {
    lines.push(`- ${t.team}: ${t.count}건 (취재 단서 ${t.lead} · 색인 0건 ${t.indexZero} · 절차 공시 ${t.routine ?? 0})`);
  }
  if (!(v.cluesLast7DaysByTeam ?? []).length) lines.push('- 최근 7일 게시일 기준 단서 없음(수집 실패와 구분: 아래 원천 상태 확인)');
  lines.push('\n■ 강한 통계 신호(정기 통계 한 줄 + 출입처 사례형 기획의 출발점)');
  for (const s of v.topStats ?? []) {
    lines.push(`- ${(s.tags ?? []).join('')} ${s.label} ${s.changePercent ?? ''}% (${s.period}) — ${s.caveat}`);
  }
  lines.push('\n■ 최근 7일 [단독] 흐름(기업별) — 남이 쓴 걸 새것처럼 내지 않으려고 본다');
  lines.push((v.dandokLast7DaysByCompany ?? []).map((d) => `${d.company} ${d.count}`).join(' · ') || '- 없음');
  for (const d of v.latestDandok ?? []) lines.push(`  ${d.published} | ${d.source} | ${d.title}`);
  lines.push('\n■ 문제 원천(여기서 나온 0건은 미확인)');
  for (const h of v.healthProblems ?? []) {
    lines.push(`- ${h.source}: ${h.status}${h.ageHours != null ? ` · ${h.ageHours}시간 전` : ''}${h.note ? ` · ${h.note}` : ''}`);
  }
  if (!(v.healthProblems ?? []).length) lines.push('- 없음');
  lines.push('\n다음: radar_clues(days=3) → radar_stats() → dandok_monitor(days=7)');
  return textResult(lines.join('\n'));
}

export async function clues(ctx, args) {
  const v = await fetchJson(ctx, 'tools/clues.json');
  const days = clampInt(args.days, 1, 45, 3);
  const limit = clampInt(args.limit, 1, 200, 40);
  const sinceHours = clampInt(args.since_hours, 0, 24 * 14, 0);
  const teams = teamsFromParam(args.team);
  const includeRoutine = args.include_routine === true || args.include_routine === 'true' || args.include_routine === 1;
  const fromDate = kstDate(ctx.now, days);
  const sinceMs = sinceHours ? ctx.now.getTime() - sinceHours * 3600000 : 0;
  let routineHidden = 0;
  const rows = (v.items ?? []).filter((r) => {
    if (teams.size && !teams.has(r.team)) return false;
    if (!matchesQuery(args.q, r.title, r.source, r.companies, r.note, r.signal)) return false;
    if (sinceMs && !(Date.parse(r.firstSeen) >= sinceMs)) return false;
    if (!sinceMs) {
      const inWindow = r.published ? r.published >= fromDate : Date.parse(r.firstSeen) >= ctx.now.getTime() - days * 86400000;
      if (!inWindow) return false;
    }
    if (r.routine && !includeRoutine && !args.q) { routineHidden++; return false; }
    return true;
  });
  const head = [`단서 · ${sinceHours ? `최근 ${sinceHours}시간 새로 잡힌 것` : `게시일 최근 ${days}일`}` +
    ` · ${kstStamp(ctx.now)} (뷰 생성 ${viewAge(v, ctx.now)}) · ${rows.length}건` +
    (routineHidden ? ` (절차 공시 ${routineHidden}건 숨김: include_routine=true)` : ''),
  '규칙: 색인 0건은 미보도 증거가 아님 · 게시일≠수집일 · 단계는 출처 표기 그대로(올리지 않음)'];
  const out = [head.join('\n')];
  for (const team of TEAM_ORDER) {
    const group = rows.filter((r) => r.team === team)
      .sort((a, b) => (COVERAGE_ORDER[a.coverage?.status] ?? 1) - (COVERAGE_ORDER[b.coverage?.status] ?? 1) ||
        String(b.published ?? '').localeCompare(String(a.published ?? '')));
    if (!group.length) continue;
    const shown = group.slice(0, limit);
    out.push(`\n■ ${team} (${group.length}건${group.length > shown.length ? `, 앞 ${shown.length}건` : ''})`);
    for (const r of shown) {
      const cov = SHORT_COVERAGE[r.coverage?.status] ?? r.coverage?.label ?? '';
      out.push(`${r.published ?? '게시일 미표기'} | ${r.source} | ${r.title} | ${cov} | ${r.tier} [id:${r.id}]`);
      if (r.url) out.push(`   ${r.url}`);
      if (r.note) out.push(`   메모: ${r.note}`);
      for (const m of (r.coverage?.matches ?? []).slice(0, 2)) {
        out.push(`   유사 제목: ${m.published ?? ''} ${m.source ?? ''} ${m.title}`);
      }
    }
    if (group.length > shown.length) out.push(`   … 남은 ${group.length - shown.length}건: q= 또는 limit=으로 다시 조회`);
  }
  if (rows.length === 0) out.push('\n조건에 맞는 단서 없음. 원천 실패 여부는 radar_health로 확인(실패≠0건).');
  return textResult(out.join('\n'));
}

export async function stats(ctx, args) {
  const v = await fetchJson(ctx, 'tools/stats.json');
  const limit = clampInt(args.limit, 1, 80, 25);
  const teams = teamsFromParam(args.team);
  const rows = (v.items ?? []).filter((s) => (!teams.size || teams.has(s.team)) &&
    matchesQuery(args.q, s.label, s.company, s.source));
  const out = [`통계 신호 · 세기순 · ${kstStamp(ctx.now)} (뷰 생성 ${viewAge(v, ctx.now)}) · ${rows.length}건`,
    ...(v.rules ?? []).map((r) => `규칙: ${r}`)];
  for (const s of rows.slice(0, limit)) {
    out.push(`\n${(s.tags ?? []).join('')} ${s.label}`);
    out.push(`   ${s.prior ?? '?'} → ${s.current ?? '?'} ${s.unit ?? ''} (${s.changePercent ?? '?'}%) · ${s.period} · ${s.source}`);
    if (s.caveat) out.push(`   주의: ${s.caveat}`);
    for (const u of (s.sourceUrls ?? []).slice(0, 2)) out.push(`   ${u}`);
  }
  if (rows.length > limit) out.push(`\n… 남은 ${rows.length - limit}건`);
  return textResult(out.join('\n'));
}

export async function dandok(ctx, args) {
  const v = await fetchJson(ctx, 'tools/dandok.json');
  const days = clampInt(args.days, 1, 120, 7);
  const limit = clampInt(args.limit, 1, 200, 40);
  const from = kstDate(ctx.now, days);
  const teams = teamsFromParam(args.team);
  const rows = (v.items ?? []).filter((r) => r.published >= from && (!teams.size || teams.has(r.team)) &&
    matchesQuery(args.q, r.title, r.source, r.companies));
  const out = [`[단독] 흐름 · 최근 ${days}일 · ${rows.length}건 (색인 갱신 ${viewAge({ generatedAt: v.sourceGeneratedAt }, ctx.now)})`,
    `주의: ${v.note}`];
  for (const r of rows.slice(0, limit)) {
    out.push(`${r.published} | ${r.source} | ${r.title}${r.companies?.length ? ` (${r.companies.join('·')})` : ''}`);
  }
  if (rows.length > limit) out.push(`… 남은 ${rows.length - limit}건: q=로 좁혀 다시 조회`);
  return textResult(out.join('\n'));
}

export async function health(ctx) {
  const v = await fetchJson(ctx, 'tools/health.json');
  const rows = [...(v.items ?? [])].sort((a, b) => Number(b.problem) - Number(a.problem));
  const out = [`원천 상태 · ${kstStamp(ctx.now)} · 문제 ${v.problemCount ?? 0}곳`, `규칙: ${v.rule}`];
  for (const r of rows) {
    out.push(`${r.problem ? '⚠' : '·'} ${r.source}: ${r.status}${r.ageHours != null ? ` · ${r.ageHours}시간 전` : ''}` +
      `${r.problem && r.expectedMaxAgeHours ? ` (기대 ${r.expectedMaxAgeHours}시간 이내)` : ''}${r.note ? ` · ${r.note}` : ''}`);
  }
  return textResult(out.join('\n'));
}

export async function governance(ctx, args) {
  let v;
  try { v = await fetchJson(ctx, 'digests/governance_latest.json'); } catch {
    return textResult('지분공시 수집 결과가 아직 없음(수집 전 또는 실패) — 0건이 아니라 미확인.', true);
  }
  const days = clampInt(args.days, 1, 30, 14);
  const limit = clampInt(args.limit, 1, 100, 30);
  const from = kstDate(ctx.now, days);
  const teams = teamsFromParam(args.team);
  const includeRoutine = args.include_routine === true || args.include_routine === 'true';
  let hidden = 0;
  const rows = (v.items ?? []).filter((x) => {
    if (x.date < from || (teams.size && !teams.has(x.team))) return false;
    if (!matchesQuery(args.company ?? args.q, x.company, x.reporter, x.role, x.reason)) return false;
    if (x.routine && !includeRoutine) { hidden++; return false; }
    return true;
  });
  const failed = (v.checks ?? []).filter((c) => c.status === 'failed');
  const out = [`지분·지배구조 공시 · 최근 ${days}일 · ${rows.length}건${hidden ? ` (단순 보고 ${hidden}건 숨김 — 기관 단순·약식, 소액 임원 보고: include_routine=true)` : ''}`,
    `수집 ${String(v.generatedAt ?? '').slice(0, 16)} · 상태 ${v.status}` +
      (failed.length ? ` · 조회 실패 ${[...new Set(failed.map((c) => c.company))].join('·')}(0건 아님)` : '') +
      ((v.unresolvedCompanies ?? []).length ? ` · 고유번호 미해결 ${v.unresolvedCompanies.join('·')}` : '') +
      (Object.keys(v.dartSpellings ?? {}).length ? ` · DART 표기 ${Object.entries(v.dartSpellings).map(([a, b]) => `${a}→${b}`).join('·')}` : ''),
    '규칙: 공개 공시이며 지분 변동 자체는 단독이 아님. 보고자 관계·개인별 지분은 원문 표에서 확인.'];
  for (const x of rows.slice(0, limit)) {
    const delta = typeof x.ratioChange === 'number' ? ` ${x.ratioChange > 0 ? '+' : ''}${x.ratioChange}%p`
      : (x.groupKey && typeof x.sharesChange === 'number' ? ` 순증감 ${x.sharesChange > 0 ? '+' : ''}${x.sharesChange.toLocaleString('en-US')}주` : '');
    // 5% reports state the holder group's combined ratio (보고자+특별관계자); insider reports are per person.
    const ratio = typeof x.ratio !== 'number' ? '' : x.kind === '대량보유(5%)' ? ` → 보고서 기재 보유비율 ${x.ratio}%(특별관계자 포함 가능)` : ` → ${x.ratio}%`;
    out.push(`${x.date} | ${x.company} | ${x.kind} | ${x.reporter}${x.role ? `(${x.role})` : ''}${delta}${ratio} ${(x.tags ?? []).join('')}`);
    if (x.reason) out.push(`   사유: ${x.reason}`);
    if (x.url) out.push(`   ${x.url}`);
  }
  if (rows.length > limit) out.push(`… 남은 ${rows.length - limit}건`);
  if (!rows.length) out.push('조건에 맞는 보고 없음(위 조회 실패·미해결 회사는 미확인).');
  return textResult(out.join('\n'));
}

const pct = (v) => (typeof v === 'number' ? `${v.toFixed(1)}%` : '—');
const pp = (v) => (typeof v === 'number' ? `${v > 0 ? '+' : ''}${v.toFixed(1)}%p` : '전년 미확인');

function ratioLine(block) {
  if (!block) return '';
  const r = block.ratios ?? {}; const d = block.deltaPp ?? {};
  const parts = [['costRatio', '원가율'], ['sgaRatio', '판관비율'], ['opMargin', '영업이익률']]
    .filter(([k]) => typeof r[k] === 'number').map(([k, label]) => `${label} ${pct(r[k])}(${pp(d[k])})`);
  return parts.join(' · ');
}

export async function earnings(ctx, args) {
  let v;
  try { v = await fetchJson(ctx, 'digests/earnings_compare_latest.json'); } catch {
    return textResult('공시 시즌 비교표가 아직 없음(첫 수집 전 또는 실패) — 0이 아니라 미확인.', true);
  }
  const teams = teamsFromParam(args.team);
  const flaggedOnly = args.flagged_only === true || args.flagged_only === 'true';
  const limit = clampInt(args.limit, 1, 60, 40);
  const c = v.counts ?? {};
  const out = [`공시 시즌 비교표 · ${v.period?.label ?? ''} (제출 마감 ${v.period?.deadline ?? '?'}) · 제출 ${c.filed ?? 0} · 미제출 ${c.not_filed ?? 0} · 조회 실패 ${c.failed ?? 0}` +
      ((v.unresolvedCompanies ?? []).length ? ` · 고유번호 미해결 ${v.unresolvedCompanies.join('·')}` : ''),
    `수집 ${String(v.generatedAt ?? '').slice(0, 16)} · 상태 ${v.status}`,
    '규칙: 같은 보고기간의 전년 동기와만 비교. 회사마다 연결/별도 기준이 다를 수 있음. 비율 변화는 취재 질문이지 원인·단독이 아님. 미제출·실패는 0이 아님.'];
  const rows = (v.companies ?? []).filter((x) => (!teams.size || teams.has(x.team))
    && matchesQuery(args.company ?? args.q, x.company) && (!flaggedOnly || (x.tags ?? []).length));
  let team = null; let shown = 0;
  for (const x of rows) {
    if (shown >= limit) break;
    if (x.team !== team) { team = x.team; out.push(`\n■ ${team}`); }
    shown++;
    if (x.status === 'not_filed') { out.push(`${x.company} — ${v.period?.label ?? ''} 보고서 미제출(아직 없음)`); continue; }
    if (x.status === 'failed') { out.push(`${x.company} — 조회 실패(0 아님): ${x.error ?? ''}`); continue; }
    if (x.status !== 'filed') { out.push(`${x.company} — 비교 가능한 계정 없음(${x.status})`); continue; }
    const head = `${x.company}(${x.basis}, ${x.filedOn ?? '?'} 제출) ${(x.tags ?? []).join('')}`;
    out.push(head);
    if (x.quarter) out.push(`   3개월: ${ratioLine(x.quarter) || '비율 미확인'}`);
    if (x.cumulative) out.push(`   누적: ${ratioLine(x.cumulative) || '비율 미확인'}`);
    if (x.annual) out.push(`   연간: ${ratioLine(x.annual) || '비율 미확인'}`);
    const e = x.employees ?? {};
    if (typeof e.count === 'number') {
      out.push(`   직원 ${e.count.toLocaleString('en-US')}명${typeof e.changePct === 'number' ? `(전년 같은 보고서 대비 ${e.changePct > 0 ? '+' : ''}${e.changePct}%)` : '(전년 미확인)'}${e.asOf ? ` · 기준 ${e.asOf}` : ''}`);
    } else if (e.note || e.error) out.push(`   직원 수 미확인: ${e.note ?? e.error}`);
    if (x.warning) out.push(`   주의: ${x.warning}`);
    if (x.url) out.push(`   ${x.url}`);
  }
  if (rows.length > shown) out.push(`… 남은 ${rows.length - shown}곳`);
  if (!rows.length) out.push('조건에 맞는 회사 없음.');
  return textResult(out.join('\n'));
}
