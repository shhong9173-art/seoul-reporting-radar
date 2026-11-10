// 출입처 유럽(EP)·국제(WO) 특허 공개(EPO OPS 3.2, epo_ops_watch.py 주 1회 토 06:40). 저장된 결과만 읽는다 — 여기서 EPO를 부르지 않는다.
// EPO OPS 약관 3.2: 자료 그 자체를 공개하지 않는다 — 기자 전용 연결(private)에서만 보인다.
import { ageNote, readFeed } from './screen.mjs';
import { clampInt, textResult } from './common.mjs';

const KST_MS = 9 * 3600000;
const has = (q, ...fields) => !q || fields.some((f) => String(f ?? '').toLowerCase().includes(q.toLowerCase()));
const KIND = { EP: '유럽특허(EP) 공개', WO: '국제특허(PCT·WO) 공개' };
// IPC 앞 네 자리만 — 기자가 '무슨 기술인지' 가늠하는 정도. 정확한 분류명은 원문에서.
const IPC = {
  B60L: '전기차 동력·충전', B60K: '차량 동력 배치', B60W: '차량 통합 제어', B62D: '차체·조향', B60R: '차량 전기·안전 장치', B60H: '차량 공조',
  B60C: '타이어', B60T: '제동', F16H: '변속기·기어', H01M: '전지', H01G: '축전기', H01B: '케이블·도체', H01F: '변압기·코일',
  H01H: '개폐기', H02J: '전력 계통·충전', H02M: '전력 변환', H02K: '전동기', H02B: '배전반', C21D: '강 열처리', C22C: '합금', C22B: '금속 제련',
  C21C: '제강', B21B: '압연', C08L: '고분자 조성물', C08F: '고분자 중합', C08K: '고분자 첨가제', C08J: '고분자 가공', C10G: '석유 정제',
  C07C: '유기 화합물', B01J: '촉매', C01B: '비금속 화합물', C01G: '금속 화합물(전구체)', G06N: 'AI·학습', G06Q: '사업 방법', G05D: '자율 제어',
  G01R: '전기 측정', B25J: '로봇', F01D: '터빈', G21C: '원자로', F02C: '가스터빈', C25B: '전기분해(수소)', H01L: '반도체',
};
const ipcLabel = (code) => {
  const k = String(code ?? '').slice(0, 4);
  return IPC[k] ? `${code}(${IPC[k]})` : code;
};

export async function patentsAbroad(ctx, args) {
  const doc = await readFeed(ctx, 'epo-patents');
  if (!doc) return textResult('해외 특허 공개(EPO OPS) 감시 결과가 아직 없음 — 첫 정기 실행(토 06:40)과 GitHub Secrets(EPO_OPS_KEY·EPO_OPS_SECRET·MCP_ACCESS_TOKEN)를 확인. 0건이 아니라 미확인.', true);
  if (doc.broken) return textResult('저장된 해외 특허 공개 결과 형식 오류 — 미확인.', true);
  const q = String(args.company ?? '').trim();
  const word = String(args.query ?? '').trim();
  const office = String(args.office ?? '').trim().toUpperCase();
  const days = clampInt(args.days, 1, 200, 30);
  const limit = clampInt(args.limit, 1, 80, 25);
  const all = args.show_all === true || args.show_all === 'true';
  const from = new Date(ctx.now.getTime() + KST_MS - days * 86400000).toISOString().slice(0, 10);
  const checks = doc.checks ?? [];
  const ok = checks.filter((c) => c.status === 'ok');
  const waiting = checks.filter((c) => c.status === 'waiting');
  const bad = checks.filter((c) => !['ok', 'waiting'].includes(c.status));
  const th = doc.throttle ?? {};
  const out = [`해외 특허 공개(유럽 EP·국제 WO · EPO OPS) · 출입처 ${checks.length}곳 · 확인 ${String(doc.generatedAt).slice(0, 16)}${ageNote(ctx, doc.generatedAt, 192, true)}`,
    `조회 정상 ${ok.length}/${checks.length}${waiting.length ? ` · 대기 ${waiting.length}곳(${[...new Set(waiting.map((c) => c.reason))].join(', ')}) — 같은 주말 재시도 칸(토 14:40·일 06:40)에 그 회사만 다시` : ''}`
      + `${bad.length ? ` · 미확인(0건 아님): ${bad.slice(0, 6).map((c) => `${c.company}(${c.error ?? c.status})`).join(', ')}` : ''}`,
    th.state || th.search ? `EPO 서버 신호(마지막 응답): ${th.state ?? '?'} · 검색 ${th.search ?? '?'}${th.perMinute != null ? `(분당 ${th.perMinute})` : ''}${th.stopped ? ` · 멈춤: ${th.stopped}` : ''}` : '',
    doc.retry ? `재시도 ${String(doc.retry.at).slice(5, 16)}: ${(doc.retry.companies ?? []).join(', ')} — 나머지 회사는 직전 결과` : '',
    `창: 공개일 기준 — 회사 첫 조회 ${doc.window?.firstDays ?? 120}일(기준선), 이후 매주 최근 ${doc.window?.weeklyDays ?? 35}일을 겹쳐 읽음`,
    ...(doc.rules ?? []).map((r) => `규칙: ${r}`)].filter(Boolean);
  if (!doc.baselineSince) out.push('\n아직 기준선 없음(첫 성공 실행 전) — 새 공개 판단은 회사별 첫 성공 다음 실행부터.');
  const noted = ok.filter((c) => (c.otherApplicants ?? []).length);
  if (noted.length) out.push(`이름 낱말만 같은 다른 출원인(걸러 냄): ${noted.slice(0, 8).map((c) => `${c.company}(${c.otherApplicants.slice(0, 2).join(' / ')})`).join(', ')}`);
  const cut = ok.filter((c) => c.truncated);
  if (cut.length) out.push(`⚠ 300건 넘어 앞 300건만 읽은 회사: ${cut.map((c) => `${c.company}(${c.total})`).join(', ')} — 나머지는 미확인`);
  const zero = ok.filter((c) => !c.total);
  if (zero.length) out.push(`조회 창 안 공개 0건: ${zero.map((c) => c.company).join(', ')} (조회는 정상 — 0건 확정은 아님, 색인 지연 가능)`);

  const rows = (doc.filings ?? [])
    .filter((f) => all || f.isNew)
    .filter((f) => String(all ? f.date ?? f.firstSeen : f.firstSeen ?? '').slice(0, 10) >= from)
    .filter((f) => has(q, ...(f.companies ?? [])) && has(word, f.title, ...(f.ipc ?? []), ...(f.applicants ?? [])) && (!office || f.country === office))
    .sort((a, b) => String(b.date).localeCompare(String(a.date)) || String(a.id).localeCompare(String(b.id)));
  out.push(`\n[${all ? '저장된 공개' : '새로 본 공개'} · 최근 ${days}일${q ? ` · ${q}` : ''}${word ? ` · "${word}"` : ''}${office ? ` · ${office}` : ''}] ${rows.length}건`);
  // 같은 패밀리(EP와 WO 등)는 한 묶음으로 보인다
  const fam = new Map();
  for (const f of rows) {
    const k = f.family ? `fam:${f.family}` : f.id;
    if (!fam.has(k)) fam.set(k, []);
    fam.get(k).push(f);
  }
  let shown = 0;
  for (const [, group] of fam) {
    if (shown >= limit) break;
    shown += 1;
    const f = group[0];
    const ids = group.map((g) => `${g.id}(${KIND[g.country] ?? g.country} ${g.date ?? '?'})`).join(' · ');
    out.push(`- ${f.isNew ? '[새 공개] ' : ''}${(f.companies ?? []).join('·')} · 「${f.title ?? '제목 없음'}」${f.titleLang && f.titleLang !== 'en' ? `(${f.titleLang})` : ''}`);
    out.push(`   ${ids} · 출원인 ${(f.applicants ?? []).filter((n) => !/^[A-Z0-9 ,.&()'-]+$/.test(n) || !(f.applicants ?? []).some((m) => m !== n && m.toUpperCase() === n)).slice(0, 4).join(' / ') || '?'}`);
    out.push(`   IPC ${(f.ipc ?? []).map(ipcLabel).join(', ') || '미기재'} · 출원 ${f.applicationDate ?? '?'}${f.priority ? ` · 우선권 ${f.priority.number}(${f.priority.date ?? '?'})` : ''} · 처음 본 날 ${String(f.firstSeen ?? '').slice(0, 10)}`);
    out.push(`   원문: ${f.url}`);
  }
  if (fam.size > limit) out.push(`… 남은 ${fam.size - limit}묶음(company·query·office로 좁히기)`);
  if (!rows.length) out.push(waiting.length || bad.length ? '없음 — 다만 대기·실패한 회사는 미확인' : '없음');
  out.push('\n검증 상태: EPO OPS 서지(자동 수집). 원문은 Espacenet 링크에서 청구항·도면·패밀리(국내 KR 출원) 확인.');
  out.push('다음: 우선권 KR 번호로 KIPRIS 국내 공개 여부 확인 → news_check(회사+기술 낱말) → 회사에 "출원 사실과 적용 계획(양산·제품 연결 여부)" 확인. 공개만으로 개발 완료·양산을 쓰지 않는다.');
  return textResult(out.join('\n'));
}
