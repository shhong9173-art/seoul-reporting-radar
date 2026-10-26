// Candidate policy for the industry desk, adapted from the senior's
// scoring.json (식품팀) to 자동차·철강·전력·화학 beats. This only scores what
// Claude already verified; it never decides 단독 — the reporter does.
import { DIRECT_BEATS, beatName } from './common.mjs';

export const POLICY = {
  version: '2026-10-26',
  gains: [
    { key: 'new_fact', points: 30, label: '원문으로 확인한 새 사실' },
    { key: 'unreported_after_channels', points: 20, label: '보도 채널 대조 후 미발견(단독 확실·유력)' },
    { key: 'impact', points: 15, label: '향후 영향(실적·공급망·가격·고용·규제)' },
    { key: 'direct_beat', points: 10, label: '직접 출입처 기업' },
    { key: 'comparison', points: 10, label: '이전 발표·경쟁사와의 같은 기준 비교' },
    { key: 'original_numbers', points: 10, label: '원문 수치(그래픽 가능)' },
    { key: 'timing', points: 5, label: '시점 고리(실적·판정·시행일)' },
  ],
  penalties: [
    { key: 'repeat_without_new_fact', points: -60, label: '새 사실 없는 반복' },
    { key: 'original_unverified', points: -40, label: '원문 미확인' },
    { key: 'press_release', points: -30, label: '보도자료·행사·MOU·수상' },
    { key: 'patent_only', points: -30, label: '특허만으로 사업 전망' },
    { key: 'macro_general', points: -25, label: '거시 일반론' },
    { key: 'obvious', points: -20, label: '자명한 내용' },
    { key: 'non_beat', points: -20, label: '직접 출입처 밖 주체' },
  ],
  recommendAt: 60,
  alertAt: 70,
  dailyLimit: 5,
  derivedMethods: ['증감률', '차이', '비중', '합계', '단위환산'],
  verdicts: ['단독 확실', '단독 유력', '선행 있음', '이미 남', '미확인'],
  // web = 구글 또는 빙(구글이 Cloudflare 출구를 503으로 막는 경우가 있어 둘 중 하나면 됨)
  channels: ['web', 'naver', 'dandok'],
  sizeKeys: ['novelty', 'numbers', 'scale', 'beat', 'timing', 'expansion', 'exclusivity'],
  sizeLabels: { novelty: '새로움', numbers: '숫자', scale: '판', beat: '출입처', timing: '시점', expansion: '확장', exclusivity: '독점' },
};

const NUMBER_RE = /\d[\d,.]*\s*(?:조원|억원|만원|조|억|만|원|달러|%|%p|배|건|대|톤|명|GW|MW|GWh|kV|개|곳)/g;
const norm = (s) => String(s ?? '').replace(/[\s,]/g, '');

function list(value) {
  return Array.isArray(value) ? value.map((v) => String(v ?? '').trim()).filter(Boolean) : [];
}

export function checkCandidate(input) {
  const c = input && typeof input === 'object' ? input : {};
  const flags = c.flags && typeof c.flags === 'object' ? c.flags : {};
  const coverage = c.coverage && typeof c.coverage === 'object' ? c.coverage : {};
  const facts = list(c.facts);
  const numbers = list(c.numbers);
  const questions = list(c.questions);
  const companies = list(c.companies).map((n) => beatName(n) ?? n);
  const beats = companies.filter((n) => DIRECT_BEATS.has(n));
  const title = String(c.title ?? '').trim();
  const verdict = POLICY.verdicts.includes(c.coverage?.verdict) ? c.coverage.verdict : '미확인';
  const channelState = (ch) => (ch === 'web' ? (coverage.google === 'ok' || coverage.bing === 'ok' || coverage.web === 'ok' ? 'ok' : coverage.google ?? coverage.bing ?? coverage.web) : coverage[ch]);
  const channelsOk = POLICY.channels.every((ch) => channelState(ch) === 'ok');

  const gains = [];
  const penalties = [];
  const hold = [];
  const reject = [];
  const add = (arr, key) => arr.push((POLICY.gains.find((g) => g.key === key) ?? POLICY.penalties.find((p) => p.key === key)));

  if (!title) hold.push('제목 없음');
  if (facts.length && c.source_url && !flags.original_unverified) add(gains, 'new_fact');
  if (['단독 확실', '단독 유력'].includes(verdict) && channelsOk) add(gains, 'unreported_after_channels');
  if (String(c.impact ?? '').trim()) add(gains, 'impact');
  if (beats.length) add(gains, 'direct_beat');
  if (String(c.comparison ?? '').trim()) add(gains, 'comparison');
  if (numbers.length) add(gains, 'original_numbers');
  if (Number(c.size_scores?.timing) >= 1) add(gains, 'timing');

  for (const p of POLICY.penalties) {
    if (p.key === 'non_beat') continue;
    if (flags[p.key]) add(penalties, p.key);
  }
  if (!beats.length) add(penalties, 'non_beat');
  if (!c.source_url && !flags.original_unverified) add(penalties, 'original_unverified');

  // 조사대기: the evidence package is incomplete.
  if (!c.source_url) hold.push('원문 URL 없음');
  if (!c.source_date) hold.push('원자료 게시일 없음');
  if (!c.content_hash) hold.push('원문 내용 해시 없음(source_document로 열면 받음)');
  for (const ch of POLICY.channels) {
    const state = channelState(ch);
    if (state !== 'ok') hold.push(`보도 채널 '${ch === 'web' ? '웹 색인(구글·빙)' : ch}' 조회 ${state ?? '안 함'} — 0건이 아니라 미확인`);
  }
  if (verdict === '미확인') hold.push('이미 났나 판정이 미확인');
  if (questions.length < 2) hold.push('회사·기관에 물을 질문 2~3개 없음');
  if (!String(c.comparison ?? '').trim()) hold.push('이전 발표·경쟁사 비교 없음');
  if (c.company_disclosed === undefined || c.company_disclosed === null) hold.push('회사가 이미 밝혔는지 확인 안 함');

  // 탈락
  if (verdict === '이미 남') reject.push('이미 보도됨');
  if (flags.repeat_without_new_fact) reject.push('새 증거 없는 반복');
  if (c.company_disclosed === true && verdict !== '선행 있음') hold.push('회사가 이미 공개 — 단독 아님 또는 약함');

  // Title numbers must come from the original (or an allowed derivation).
  const allowed = new Set([...numbers, ...facts.flatMap((f) => f.match(NUMBER_RE) ?? [])].map(norm));
  for (const d of Array.isArray(c.derived_numbers) ? c.derived_numbers : []) {
    if (d && POLICY.derivedMethods.includes(d.method)) allowed.add(norm(d.value));
  }
  const unsupported = (title.match(NUMBER_RE) ?? []).filter((n) => !allowed.has(norm(n)));
  if (unsupported.length) hold.push(`제목 숫자 근거 없음: ${unsupported.join(', ')} (원문 수치 또는 허용 계산 5종만)`);
  for (const d of Array.isArray(c.derived_numbers) ? c.derived_numbers : []) {
    if (d && !POLICY.derivedMethods.includes(d.method)) hold.push(`허용되지 않은 파생 계산: ${d.method}`);
  }

  const score = [...gains, ...penalties].reduce((s, g) => s + g.points, 0);
  const sizeScores = c.size_scores && typeof c.size_scores === 'object' ? c.size_scores : null;
  let size = null;
  if (sizeScores) {
    const total = POLICY.sizeKeys.reduce((s, k) => s + Math.max(0, Math.min(2, Number(sizeScores[k]) || 0)), 0);
    size = { total, grade: total >= 10 ? '톱' : total >= 6 ? '박스' : '단신' };
  }
  const status = reject.length ? '탈락' : hold.length ? '조사대기' : score >= POLICY.recommendAt ? '추천' : '보류(점수 미달)';
  return { title, status, score, alert: status === '추천' && score >= POLICY.alertAt, verdict, gains, penalties,
    hold, reject, size, beats };
}

export function formatCheck(r) {
  const lines = [`판정: ${r.status} · 점수 ${r.score} (추천 ${POLICY.recommendAt}↑) · 이미 났나: ${r.verdict}` +
    (r.size ? ` · 지면감 ${r.size.total}/14 → ${r.size.grade}` : ' · 지면감 점수 미입력')];
  if (r.title) lines.push(`제목: ${r.title}`);
  if (r.gains.length) lines.push('가점: ' + r.gains.map((g) => `${g.label} +${g.points}`).join(' / '));
  if (r.penalties.length) lines.push('감점: ' + r.penalties.map((g) => `${g.label} ${g.points}`).join(' / '));
  if (r.reject.length) lines.push('탈락 사유: ' + r.reject.join(' / '));
  if (r.hold.length) lines.push('채울 것: \n- ' + r.hold.join('\n- '));
  lines.push('※ 점수는 정리용이다. 단독 여부의 최종 판단은 기자가 한다.');
  return lines.join('\n');
}
