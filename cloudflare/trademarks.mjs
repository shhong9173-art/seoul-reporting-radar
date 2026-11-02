// 출입처 상표 출원(KIPRIS Plus 상표 출원 속보, 주 1회 수집). 저장된 결과만 읽는다 — 여기서 KIPRIS를 부르지 않는다.
import { ageNote, readFeed } from './screen.mjs';
import { clampInt, textResult } from './common.mjs';

const KST_MS = 9 * 3600000;
const matches = (q, ...fields) => !q || fields.some((f) => String(f ?? '').toLowerCase().includes(q.toLowerCase()));
const CLASS = {
  '01': '화학품', '03': '화장품·세제', '04': '연료·윤활유', '06': '금속재', '07': '기계·엔진', '09': '전기·전자·SW', '11': '조명·냉난방·태양광',
  12: '차량·부품', 14: '귀금속', 16: '인쇄물', 17: '고무·절연재', 18: '가죽·가방', 19: '비금속 건축재', 21: '생활용품', 25: '의류',
  28: '완구·스포츠', 35: '광고·사업관리', 36: '금융·부동산', 37: '건설·수리', 38: '통신', 39: '운송·물류', 40: '재료 가공',
  41: '교육·오락', 42: '과학기술·SW 서비스', 43: '음식·숙박',
};
export const classLabel = (c) => `${c}류${CLASS[c] ?? CLASS[Number(c)] ? `(${CLASS[c] ?? CLASS[Number(c)]})` : ''}`;
const REASON = { provider_22_cooldown: '제공기관 응답 22 뒤 72시간 대기', monthly_trademark_limit: '이번 달 상표 호출 몫(150회) 소진', run_cap: '실행당 호출 한도',
  trademark_limit_reached: '이번 달 상표 호출 몫 소진', monthly_limit_reached: 'KIPRIS 월 900회 소진', ledger_invalid_manual_review: '호출 장부 손상 — 수동 확인' };
export const waitReason = (r) => REASON[r] ?? r ?? '대기';

export async function trademarks(ctx, args) {
  const doc = await readFeed(ctx, 'trademarks');
  if (!doc) return textResult('상표 출원 감시 결과가 아직 없음 — 첫 정기 실행(월 07:10)과 GitHub Secrets(MCP_ACCESS_TOKEN·KIPRIS_SERVICE_KEY)를 확인. 0건이 아니라 미확인.', true);
  if (doc.broken) return textResult('저장된 상표 출원 결과 형식 오류 — 미확인.', true);
  const q = String(args.company ?? '').trim();
  const name = String(args.name ?? '').trim();
  const cls = String(args.class ?? '').trim().padStart(2, '0');
  const days = clampInt(args.days, 1, 120, 30);
  const limit = clampInt(args.limit, 1, 80, 25);
  const all = args.show_all === true || args.show_all === 'true';
  const from = new Date(ctx.now.getTime() + KST_MS - days * 86400000).toISOString().slice(0, 10);
  const checks = doc.checks ?? [];
  const ok = checks.filter((c) => c.status === 'ok');
  const waiting = checks.filter((c) => c.status === 'waiting');
  const bad = checks.filter((c) => !['ok', 'waiting'].includes(c.status));
  const kip = doc.kipris ?? {};
  const out = [`상표 출원(출입처 ${checks.length}곳 · 출원일 ${doc.window?.from ?? '?'}~${doc.window?.to ?? '?'}) · 확인 ${String(doc.generatedAt).slice(0, 16)}${ageNote(ctx, doc.generatedAt, 192, true)}`,
    `조회 정상 ${ok.length}/${checks.length}${waiting.length ? ` · 대기 ${waiting.length}곳(${[...new Set(waiting.map((c) => waitReason(c.reason)))].join(', ')}${waiting[0]?.until ? `, ${String(waiting[0].until).slice(0, 16)}부터 재시도` : ''})` : ''}`
      + `${bad.length ? ` · 미확인(0건 아님): ${bad.slice(0, 6).map((c) => `${c.source.replace('상표 ', '')}(${c.error ?? c.status})`).join(', ')}` : ''}`,
    doc.retry ? `평일 재시도 ${String(doc.retry.at).slice(5, 16)}: ${(doc.retry.companies ?? []).join(', ')} — 월요일에 실패·대기한 회사만 다시 조회(나머지는 월요일 결과)` : '',
    kip.month ? `KIPRIS 호출 장부(${kip.month}): 상표 ${kip.groupUsed?.trademark ?? '?'}/${kip.groupLimits?.trademark ?? '?'} · 전체 ${kip.counted ?? '?'}/${kip.monthlyLimit ?? '?'} — 이 저장소가 센 수, 계정 실제 사용량 아님` : '',
    ...(doc.rules ?? []).map((r) => `규칙: ${r}`)].filter(Boolean);
  if (!doc.baselineSince) out.push('\n아직 기준선 없음(첫 성공 실행 전) — 새 출원 판단은 첫 성공 다음 주부터.');
  const unverified = checks.filter((c) => c.nameVerified === false && c.status === 'ok' && !c.rawTotal);
  if (unverified.length) out.push(`⚠ 출원인 이름 미확인 + 0건: ${unverified.map((c) => c.source.replace('상표 ', '')).join(', ')} — 이름 불일치일 수 있음(0건 아님)`);
  // KIPRIS 출원인 검색은 이름 일부만 같아도 돌려준다 — 다른 회사만 나온 곳은 그 회사 0건(11-02 영풍 → 영풍제약)
  const others = checks.filter((c) => c.status === 'ok' && !c.kept && c.otherApplicants && c.note);
  if (others.length) out.push(`이름 일부만 같은 다른 출원인만 나온 곳(이 회사 0건): ${others.map((c) => `${c.source.replace('상표 ', '')}(${String(c.note).replace(/^응답 \d+건은 이름 일부만 같은 다른 출원인\(|\) — 이 회사 출원 없음$/g, '')})`).join(', ')}`);

  const rows = (doc.filings ?? [])
    .filter((f) => all || f.isNew)
    .filter((f) => String(f.addedClassesAt ?? f.firstSeen ?? '').slice(0, 10) >= from || (all && String(f.applicationDate ?? '') >= from))
    .filter((f) => matches(q, f.company) && matches(name, f.title) && (!args.class || (f.classes ?? []).includes(cls)))
    .sort((a, b) => (a.tier ?? 'Z').localeCompare(b.tier ?? 'Z') || String(b.applicationDate).localeCompare(String(a.applicationDate)));
  out.push(`\n[${all ? '저장된 출원' : '새로 본 출원'} · 최근 ${days}일${q ? ` · ${q}` : ''}${name ? ` · 이름 "${name}"` : ''}${args.class ? ` · ${classLabel(cls)}` : ''}] ${rows.length}건(같은 날 같은 이름은 한 건)`);
  for (const f of rows.slice(0, limit)) {
    const tag = f.isNew ? `[${f.tier ?? 'C'}${f.titleNew ? ' · 처음 보는 이름' : ''}${f.addedClassesAt ? ' · 상품류 추가' : ''}] ` : '';
    out.push(`- ${tag}${f.company}${f.related ? '(관련 기업)' : ''} · 「${f.title}」 · 출원 ${f.applicationDate}`);
    out.push(`   상품류: ${(f.classes ?? []).map(classLabel).join(', ') || '미기재'}${(f.coreClasses ?? []).length ? ` · 업종 핵심 ${f.coreClasses.join('·')}류` : ''} · 상태 ${(f.statuses ?? []).join('·') || '?'}`);
    out.push(`   출원번호 ${(f.applicationNumbers ?? []).slice(0, 6).join(', ')}${(f.applicationNumbers ?? []).length > 6 ? ` 외 ${f.applicationNumbers.length - 6}건` : ''} · 처음 본 날 ${String(f.firstSeen ?? '').slice(0, 10)}${f.applicants && !f.applicants.includes('|') ? '' : ` · 공동 출원인 ${f.applicants}`}`);
  }
  if (rows.length > limit) out.push(`… 남은 ${rows.length - limit}건(company·name·class로 좁히기)`);
  if (!rows.length) out.push(waiting.length || bad.length ? '없음 — 다만 대기·실패한 회사는 미확인' : '없음');
  out.push('\n검증 상태: KIPRIS 공개 출원 정보(자동 수집). 원문은 KIPRIS(kipris.or.kr)에서 출원번호로 조회 — 견본 이미지·지정상품 확인.');
  out.push('다음: 같은 이름 과거 출원(KIPRIS 상표명 검색) → news_check(상표명·회사명) → 회사에 "출원 사실과 용도(차명·서비스명·방어 출원)" 확인. 상표 출원만으로 출시·진출을 쓰지 않는다.');
  return textResult(out.join('\n'));
}
