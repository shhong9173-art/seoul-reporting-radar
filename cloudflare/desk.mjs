// 단독 데스크(scoop_desk, 11-13 기자: "단독 달라고 했는데 너무 약했어 — 제대로 단독거리 뽑을 수 있게").
// 그날 A 16건은 포항시의회 회의록 발언 7, 다른 회사 임원 명단 속 출입처 출신 3, 제목뿐인 해외 파트너 공시 3, 이미 보도된 노조 성명 2,
// 10월에 이미 보도된 금호타이어 이사 교체 1 — 단독감이 없었고, 단독 요청에 나온 6건은 모두 기자가 이미 처리한 건이었다.
//
// 이 화면은 등급(A·B·C)을 바꾸지 않는다. radar_today와 같은 항목에서
//  ① 기자가 이미 처리한 것(처리 장부)과 판정한 것, ② 자동 보도 대조가 '관련 보도 있음'인 것, ③ 기자가 여러 번 킬한 유형을 걷어내고
//  ④ 기자가 실제로 단독을 쓴 유형부터 보여 준다.
// 유형 표(DESK_TYPES)의 근거는 기자의 판정 기록이다 — 바꾸는 건 기자가 정한다.
import { clampInt, textResult } from './common.mjs';
import { clipAt, kstStamp, ledgerMark, pressLines, radarTodayData } from './digest.mjs';
import { EXCLUDING, companiesIn, entryLabel } from './handled.mjs';

const W = { screen: '단독 후보 심사', official: '공장등록·관보', signals: '공정위·한전·원자재', stats: '월간 통계(물가·생산·수입차·완성차 판매)', remedy: '무역구제',
  court: '미국 소송·ITC', partner: '해외 파트너 공시', comments: '미 연방 의견서', page: '해외 공식 페이지', tm: '상표 출원', epo: '해외 특허 공개(EP·WO)',
  bills: '국회 법안', recalls: '미국 리콜(NHTSA 전체)', epa: '미국 EPA 인증', osha: '미국 OSHA 점검·위반', env: '미국 주 환경 허가·공고', fuel: '국내 연비 신고',
  awards: '해외 발주처 낙찰', insolv: '협력사 회생·파산', energy: '전기위·원안위', building: '공장 부지 건축허가', ukreg: '해외 법인 등기(영국)', local: '지자체 고시·공고',
  workforce: '사업장 인력(국민연금)', stacks: '굴뚝 측정(공장 가동 신호)', labor: '노동위 회의(조정·심판)', union: '노조 성명·보도자료', council: '지방의회 회의록',
  india: '인도 법인 공시(현대차 인도)', counter: '타사 공시 속 출입처(거래상대)', gov: '지분·자사주 변동', exec: '임원 명단 변화(정기보고서)',
  execm: '수시 임원 공시·타사 임원 명단', execc: '문제 임원 점검', global: '출입처 외신' };

const foreignDoc = (x) => (x.watch === W.remedy && x.tier !== 'C' && /^(?:미국 ITC|해외 조사|대한 수입규제|영국 TRA)/.test(x.kind ?? '')) || (x.watch === W.comments && x.tier !== 'C');
const GOV = /한국 정부|대한민국 정부|산업통상부|Government of (?:the Republic of )?Korea|Korean [Gg]overnment|MOTIE/;
const namesBeatOrGov = (x) => companiesIn(`${x.company ?? ''} ${x.fact ?? ''}`).size > 0 || GOV.test(x.fact ?? '') || /조사기관의 판단·쟁점 문서/.test(x.fact ?? '');

// 위에서부터 처음 맞는 유형. strength: strong(기자가 단독을 썼거나 기사로 이어진 유형) · normal · weak(기자가 여러 번 킬·접음)
// why는 그 근거(기자 판정·기사 기록). 새 판정이 쌓이면 이 표를 고친다 — 고치는 건 기자가 정한다.
export const DESK_TYPES = [
  { key: 'ktc', strength: 'strong', label: '국내 무역위(출입처 신청·판정 예고)', why: '11-06 [단독] LG화학 2-EHA 반덤핑 신청 — 무역위 새 조사에 회사 확인 한 통',
    test: (x) => x.watch === W.remedy && /^무역위 (?:새 반덤핑 조사|새 조사|회의 예고)/.test(x.kind ?? '') },
  { key: 'uscourt', strength: 'strong', label: '미국 법원·ITC(출입처가 당사자)', why: '11-09 [단독] 포스코 美 열연 상계관세 CIT 제소',
    test: (x) => x.watch === W.court && x.tier === 'A' },
  // 英 S-PVC 단독은 '출입처·한국 정부 이름이 적힌 문서'였다 — 이름 없이 목록에 한국산 줄이 생긴 것(인도 DGTR 목록 등)은 실적 있는 유형으로 올리지 않는다.
  // 11-13 운영: 그날 맨 위 8건이 모두 인도 DGTR 목록 줄(같은 조사가 세 줄씩)이었다.
  { key: 'foreigndoc', strength: 'strong', label: '해외 무역구제·규제 문서(출입처·한국 정부 이름)', why: "11-10 [단독] 英 S-PVC 반덤핑 '한국 특별시장상황' 의견서",
    test: (x) => foreignDoc(x) && namesBeatOrGov(x) },
  { key: 'foreignlist', strength: 'normal', label: '해외 무역구제 목록 새 줄(한국산)', why: '',
    note: "목록에 한국산 줄이 생겼다는 것뿐 — 그 품목을 만드는 출입처가 있는지(사업보고서 '사업의 내용'·회사 확인)부터. 같은 조사가 여러 줄로 잡히면 한 줄만 보인다",
    test: (x) => foreignDoc(x) },
  { key: 'filing', strength: 'strong', label: '공시(정정 중 큰 변경·소송·계약 — 미보도 후보)', why: '11-11 기사(금호석유화학 합병 종료) 12시간 앞 · 11-09 경쟁지 단독(고려아연 소송 정정) 18시간 앞 — 둘 다 자동 대조',
    test: (x) => x.watch === W.screen && x.tier === 'A' },
  { key: 'building', strength: 'strong', label: '공장 부지 건축허가(신축 1,000㎡ 이상)', why: '10-30 기사(LS전선 구미 희토류 영구자석 공장) 18시간 앞 — 자동 대조',
    test: (x) => x.watch === W.building && x.tier === 'A' },
  // --- 약한 유형: 기자가 여러 번 킬·접음 ---
  { key: 'stacks', strength: 'weak', label: '굴뚝 측정', why: '킬 16건(11-04~11-07: 실시간 신호만 있고 뒷받침 없음·정기보수)', test: (x) => x.watch === W.stacks },
  { key: 'tsb', strength: 'weak', label: '미국 제조사 통신(서비스 캠페인·보증 연장)', why: "킬 3건(11-09: '국내 적용 여부를 묻는 유형은 단독감 약함')",
    test: (x) => x.watch === W.recalls && /^미국 제조사 통신/.test(x.kind ?? '') },
  { key: 'complaints', strength: 'weak', label: '미국 결함 신고 급증', why: '킬 1건(11-07: 리콜 부품 지연 — 기사 가치 낮음)', test: (x) => x.watch === W.recalls && x.kind === '미국 결함 신고 급증' },
  { key: 'workforce', strength: 'weak', label: '사업장 인력·공사 현장명(국민연금)', why: '접음 2건(11-09 LG화학 대산 현장명 — 회사 사실무근, 현대제철 — 알려진 사업)', test: (x) => x.watch === W.workforce },
  { key: 'council', strength: 'weak', label: '지방의회 회의록 발언', why: '접음 1건(11-12 포스코 한정어업) · 11-13 A 16건 중 7건이 포항시의회 발언', test: (x) => x.watch === W.council },
  { key: 'hearing', strength: 'weak', label: '노동위 심판·차별시정(개별 구제신청)', why: '접음 3건(11-12 현대차 남양 차별시정·LG화학 부당전보·LS전선 재심)',
    test: (x) => x.watch === W.labor && !/조정|중재|교섭/.test(`${x.kind ?? ''} ${x.fact ?? ''}`.slice(0, 160)) },
  { key: 'execmarket', strength: 'weak', label: '다른 회사 임원 명단 속 출입처 출신', why: '출입처 회사의 변화가 아님(11-13 A 3건: 애경산업·씨케이솔루션·에이팩트)',
    test: (x) => x.watch === W.execm && /타사|명단에 새로 보임|출신/.test(`${x.kind ?? ''} ${x.fact ?? ''}`.slice(0, 200)) },
  { key: 'partner', strength: 'weak', label: '해외 파트너 공시(제목뿐)', why: '출입처 이름이 나온 본문 대목 없이 서류 이름만 뜸(11-13 A 3건)', test: (x) => x.watch === W.partner && !/본문 대목 「/.test(x.fact ?? '') },
  { key: 'factorychange', strength: 'weak', label: '공장등록 고용·목록 변동', why: '킬 2건(11-04 KG스틸 고용 — 담당자 등록 실수, 11-13 현대차 안성 목록 빠짐)',
    test: (x) => x.watch === W.official && /^공장 (?:목록에서 빠짐|등록 내용 변경|고용)/.test(x.kind ?? '') },
  { key: 'smallinsolv', strength: 'weak', label: '거래 관계 모르는 소규모 회생·파산', why: '출입처 협력사 명단에 없고 종업원 수 명~십수 명', test: (x) => x.watch === W.insolv && x.tier !== 'A' },
  { key: 'consumer', strength: 'weak', label: '미국 소비자·개인 소송', why: '출입처 미국 법인을 상대로 한 일상 소송', test: (x) => x.watch === W.court && x.tier === 'C' },
  { key: 'reference', strength: 'weak', label: '참고 자료(상표·특허 공개·통계·외신·EPA·연비)', why: '그 자체로 사건이 아님 — 다른 단서와 겹칠 때만',
    test: (x) => [W.tm, W.epo, W.stats, W.global, W.epa, W.fuel, W.page].includes(x.watch) && x.tier !== 'A' },
  // 레이더 규칙에 이미 '단독 근거로 쓰지 않는다'고 적힌 공개 공고. 11-13 운영: 7일 후보 37건 중 17건이 이 감시(공장등록·관보)였다
  { key: 'gazette', strength: 'weak', label: '관보 입법예고·법제처 확정 발령', why: '공개 공고 — 보도자료와 같은 날 나오는 경우가 많아 단독 근거로 쓰지 않는다(레이더 규칙). 일반 발제 자료',
    test: (x) => x.watch === W.official && /^(?:관보 입법예고|법제처 )/.test(x.kind ?? '') },
  { key: 'quota', strength: 'weak', label: 'EU 쿼터 소진', why: '기자: 일반 통상 통계 발제는 패스(여러 번)', test: (x) => x.watch === W.remedy && /^EU 쿼터/.test(x.kind ?? '') },
];
export function deskType(x) {
  return DESK_TYPES.find((t) => t.test(x)) ?? { key: 'other', strength: 'normal', label: x.watch, why: '' };
}

const RANK = { strong: 0, normal: 1, weak: 2 };
const dayOf = (x) => String(x.date ?? '').slice(0, 10);

// 출입처가 신청인인 무역위 사건 가운데 진행일정에 앞으로 21일 안 날짜가 적힌 것(예고 — 회의 안건이 올라오기 전에도 준비할 수 있게)
export function ktcAhead(docs, nowMs) {
  const today = new Date(nowMs + 9 * 3600000).toISOString().slice(0, 10);
  const until = new Date(nowMs + 9 * 3600000 + 21 * 86400000).toISOString().slice(0, 10);
  const out = [];
  for (const c of docs?.['trade-remedy']?.ktc?.cases ?? []) {
    if (!(c.applicant?.beat ?? []).length) continue;
    for (const [step, date] of c.timeline ?? []) {
      if (date && date >= today && date <= until) out.push({ date, step, title: c.title, no: c.no, beat: c.applicant.beat, url: c.url, review: c.review === '재심' || /재심/.test(c.title ?? '') });
    }
  }
  return out.sort((a, b) => a.date.localeCompare(b.date));
}

export async function scoopDesk(ctx, args) {
  const days = clampInt(args.days, 1, 14, 7);
  const limit = clampInt(args.limit, 1, 40, 12);
  const showWeak = args.include_weak === true || args.include_weak === 'true';
  const d = await radarTodayData(ctx, { hours: days * 24, company: args.company, limit: 60, include_minor: true });
  const nowMs = d.now.getTime();
  const rows = [...d.tiers.A, ...d.tiers.B, ...d.tiers.C].map((x) => {
    const rec = d.checked.get(String(x.id));
    return { x, type: deskType(x), press: d.pressOf(x), rec, before: (rec?.evidence ?? []).find((e) => e.before) ?? null };
  });
  // 기자가 이미 쓴 기사와 자동 대조로 이어진 항목(my-articles)은 후보가 아니다 — 11-13 운영: 14일 화면 '실적 있는 유형'에 기자가 11-06 단독으로 쓴
  // 2-EHA 무역위 조사가 그대로 떴다(패키지를 남기지 않은 기사라 처리 장부에는 없었다). 자동 대조라 숨기지 않고 4구역에 기사 제목과 함께 적는다.
  const wroteOf = (x) => d.wrote?.get(String(x.id)) ?? null;
  const written = rows.filter((r) => wroteOf(r.x));
  const isCovered = (r) => !wroteOf(r.x) && (r.press === '관련 보도 있음' || r.press === '같은 수치 선행');
  const covered = rows.filter(isCovered);
  const open = rows.filter((r) => !isCovered(r) && !wroteOf(r.x));
  const weak = open.filter((r) => r.type.strength === 'weak');
  const prior = open.filter((r) => r.type.strength !== 'weak' && r.x.prior);
  // 참고 등급(C)은 강한 유형이 아니면 후보로 올리지 않는다(등급은 그대로 — 여기서만 접는다)
  const isMinor = (r) => r.type.strength === 'normal' && r.x.tier === 'C' && !r.x.prior;
  const minor = open.filter(isMinor);
  const main = open.filter((r) => r.type.strength !== 'weak' && !r.x.prior && !isMinor(r))
    .sort((a, b) => RANK[a.type.strength] - RANK[b.type.strength] || Number(Boolean(a.before)) - Number(Boolean(b.before))
      || (a.x.tier < b.x.tier ? -1 : a.x.tier > b.x.tier ? 1 : 0) || String(b.x.date ?? '').localeCompare(String(a.x.date ?? '')));
  // 같은 날 같은 감시·회사·종류는 두 줄까지만(같은 회의록·같은 사업장 반복)
  const seen = new Map();
  const shown = [];
  let folded = 0;
  for (const r of main) {
    // 해외 목록 줄은 같은 조사가 제목 줄·상태 줄·나라 줄로 따로 잡힌다 — 같은 원문 주소는 한 줄만
    const listRow = r.type.key === 'foreignlist' && r.x.url;
    const k = listRow ? `${r.x.kind}|${r.x.url}` : `${r.x.watch}|${r.x.company}|${r.x.kind}|${dayOf(r.x)}`;
    seen.set(k, (seen.get(k) ?? 0) + 1);
    if (seen.get(k) > (listRow ? 1 : 2)) { folded += 1; continue; }
    shown.push(r);
  }

  const out = [`단독 데스크 · ${kstStamp(d.now.toISOString())} KST · 최근 ${days}일 · 레이더 항목 ${rows.length + (d.ledgerHidden ?? []).length}건 → 걷어낸 뒤 후보 ${shown.length}건`];
  out.push('읽는 법: 등급(A·B·C)은 그대로 두고, 이미 처리한 것·이미 보도된 것·기자가 여러 번 킬한 유형을 걷어낸 화면이다. 맨 위 유형은 기자가 실제로 단독을 쓴 유형. 후보가 적은 날은 적은 대로 둔다 — 약한 것으로 채우지 않는다.');
  if (d.health.length) out.push(`\n[수집 상태 — 실패·오래됨은 0건이 아니라 미확인]\n${d.health.slice(0, 6).join('\n')}${d.health.length > 6 ? `\n… 그 밖 ${d.health.length - 6}줄(radar_today)` : ''}`);

  out.push(`\n[1. 새 후보 — 실적 있는 유형부터] ${shown.length}건${folded ? ` (같은 날 같은 종류·같은 원문 ${folded}건 접음)` : ''}`);
  // 후보는 있는데 실적 있는 유형이 하나도 없는 날: 그렇다고 먼저 말한다(약한 날을 강한 날처럼 보이게 하지 않는다)
  if (shown.length && shown[0].type.strength !== 'strong') out.push('〈실적 있는 유형〉 없음 — 기자가 단독을 쓴 유형(무역위 신청·미국 법원 제소·출입처 이름이 적힌 해외 문서·큰 공시·신축 허가)에서 새로 잡힌 것이 없다.');
  let lastStrength = null;
  for (const r of shown.slice(0, limit)) {
    const { x, type } = r;
    if (type.strength !== lastStrength) { out.push(type.strength === 'strong' ? '〈실적 있는 유형〉' : '〈그 밖 — 원문·회사 확인으로 가를 것〉'); lastStrength = type.strength; }
    out.push(`- ${x.tier} · ${x.date ? `${String(x.date).length > 10 ? kstStamp(x.date) : x.date} · ` : ''}${type.key === 'other' ? x.watch : type.label}${x.company ? ` · ${x.company}` : ''}`);
    out.push(`   ${clipAt(x.fact, 420)}`);
    if (type.why) out.push(`   〔이 유형 실적〕 ${type.why}`);
    if (type.note) out.push(`   〔볼 것〕 ${type.note}`);
    if (x.point) out.push(`   〔기사 포인트〕 ${x.point}`);
    if (x.ask) out.push(`   물을 것: ${x.ask}`);
    const press = pressLines(r.rec, kstStamp(d.press?.generatedAt), d.press?.generatedAt);
    if (press.length) out.push(...press); else out.push('   보도 대조(자동): 아직 대조 전 — news_check로 직접(낱말 바꿔 2~3번)');
    if (r.before) out.push('   ⚠ 항목 날짜 전 기사가 있다 — 문서가 늦게 나온 옛 사건일 수 있음(임원 명단·정기보고서류). 그 기사부터 열어 볼 것');
    out.push(`   ${x.url ? `원문: ${x.url} · ` : ''}자세히: ${x.tool} · id ${x.id}${ledgerMark(x)}`);
  }
  if (shown.length > limit) out.push(`… 남은 ${shown.length - limit}건(limit 또는 company로 좁히기)`);
  if (!shown.length) out.push('없음 — 오늘은 걷어내고 남는 후보가 없다. 약한 유형에서 억지로 올리지 않는다(include_weak=true로 볼 수는 있다).');

  // company로 좁혀 물었으면 일정도 그 낱말이 든 사건만(11-13 운영: company=포스코에 한화솔루션 신청 사건 일정이 붙었다)
  const qWords = String(args.company ?? '').toLowerCase().split(/\s+/).filter(Boolean);
  const ahead = ktcAhead(d.docs, nowMs).filter((a) => qWords.every((w) => `${a.title} ${a.no ?? ''} ${a.beat.join(' ')}`.toLowerCase().includes(w)));
  if (ahead.length) {
    out.push(`\n[2. 다가오는 일정 — 출입처가 신청인인 무역위 사건, 앞으로 21일] ${ahead.length}건`);
    for (const a of ahead) out.push(`- ${a.date} ${a.step} · ${a.no ?? ''} ${clipAt(a.title, 60)} · 신청인 출입처 ${a.beat.join('·')}${a.review ? '(재심 건 — 그 보도자료 때 신청인)' : ''} · 원문: ${a.url}`);
    out.push('   진행일정의 날짜는 누리집 표기다 — 판정일인지 시한인지는 무역위·회사 확인. 결과는 회의 뒤 보도자료 전에는 미확인.');
  }

  if (prior.length) {
    out.push(`\n[3. 앞서 추천했고 판정이 없는 것] ${prior.length}건 — 새 사실이 붙었을 때만 다시 낸다`);
    for (const r of prior.slice(0, 8)) out.push(`- ${r.x.prior.subject || r.x.prior.key}(패키지 ${r.x.prior.key}) ← ${r.x.watch} · id ${r.x.id}`);
  }

  out.push('\n[4. 걷어낸 것]');
  const hidden = d.ledgerHidden ?? [];
  const judgedN = Object.values(d.hiddenBy).reduce((a, b) => a + b, 0);
  out.push(`- 이미 처리(다시 내지 않음): 처리 장부 ${hidden.length}건 · 판정 ${judgedN}건${judgedN ? `(${Object.entries(d.hiddenBy).map(([v, n]) => `${v} ${n}`).join(' · ')})` : ''}`);
  const byEntry = new Map();
  for (const x of hidden) byEntry.set(x.handled.entry.key, [...(byEntry.get(x.handled.entry.key) ?? []), x]);
  for (const [, xs] of [...byEntry].slice(0, 10)) out.push(`   ${entryLabel(xs[0].handled.entry)} ← ${xs.length}건(${xs[0].watch})`);
  if (written.length) {
    out.push(`- 기자가 이미 쓴 기사(아이뉴스24 자동 대조): ${written.length}건`);
    for (const r of written.slice(0, 8)) { const w = wroteOf(r.x); out.push(`   ${String(w.published ?? '').slice(5, 10)} 「${clipAt(w.title, 50)}」 ← ${r.x.watch}${r.x.company ? ` · ${r.x.company}` : ''} · id ${r.x.id}`); }
  }
  out.push(`- 이미 보도(자동 대조 '관련 보도 있음'): ${covered.length}건`);
  const byType = new Map();
  for (const r of weak) byType.set(r.type.key, [...(byType.get(r.type.key) ?? []), r]);
  out.push(`- 약한 유형: ${weak.length}건${weak.length ? ` — ${[...byType].map(([, rs]) => `${rs[0].type.label} ${rs.length}`).join(' · ')}${showWeak ? '' : ' (include_weak=true로 펼침)'}` : ''}`);
  if (showWeak) {
    for (const [, rs] of byType) {
      out.push(`   〈${rs[0].type.label}〉 ${rs[0].type.why}`);
      for (const r of rs.slice(0, 6)) out.push(`   · ${r.x.tier} · ${dayOf(r.x)} · ${r.x.company ?? ''} · ${clipAt(r.x.fact, 140)} · id ${r.x.id}`);
      if (rs.length > 6) out.push(`   · … ${rs.length - 6}건 더`);
    }
  }
  if (minor.length) out.push(`- 참고 등급(C)이라 접음: ${minor.length}건 (radar_today include_minor=true)`);

  // 장부 전체(최근 30일): 레이더 항목과 안 이어진 건도 다시 내지 않게 — 구역 도구·웹에서 찾은 후보를 낼 때 이 목록과 먼저 맞춰 본다
  const recent = (d.ledger?.entries ?? []).filter((e) => EXCLUDING.has(e.state) && e.at >= nowMs - 30 * 86400000).sort((a, b) => b.at - a.at);
  out.push(`\n[5. 기자가 이미 처리한 건 — 최근 30일 ${recent.length}건] 여기 있는 건과 같은 사건은 어디서 찾았든 다시 내지 않는다(새 사실이 붙었을 때만, 무엇이 새로운지 밝히고)`);
  for (const e of recent.slice(0, 40)) out.push(`- ${entryLabel(e)} · ${new Date(e.at + 9 * 3600000).toISOString().slice(5, 10)}${e.reason ? ` — ${clipAt(e.reason, 70)}` : ''}`);
  if (!d.ledger) out.push('⚠ 처리 장부를 읽지 못했다 — 이미 처리한 건이 섞였을 수 있다(scoop_packages로 직접 확인).');

  out.push('\n처리 기록 남기는 법: 레이더 항목은 candidate_feedback(item_ids=[id…], verdict=킬/보류/씀, reason). 레이더 밖에서 찾은 건·답변 대기·후배 토스·예약은 package_save(state=보류/접음/발제함, item_ids=[관련 레이더 id나 원문 주소…]) — 다음부터 이 화면과 구역 도구에서 빠지거나 표시가 붙는다.');
  out.push("규칙: 여기 뜬 것도 단독 확정이 아니다 — 원문 확인 → news_check(낱말 바꿔 2~3번) → 회사 확인. '미보도 후보'는 검색 범위 결과일 뿐이고, 수집 실패는 미보도의 증거가 아니다. 관계자 발언을 만들지 않는다.");
  return textResult(out.join('\n'));
}
