// 처리 장부(11-13 기자: "단독 달라고 했는데 같은 것만 반복해 가져온다").
// 기자가 킬·보류(답변 대기·예약·후배 토스)·작성 중으로 남긴 취재 패키지와 판정을 레이더 항목에 잇는다.
// 그날 단독 요청에 나온 6건(영국 후판 AD0071, 영국 PVC, 한화 ITC 1494, 기아 조지아 OSHA, HPLS 루이지애나, 현대차 안성 공장)이
// 모두 이미 처리한 건이었다 — 패키지는 이름이 따로라 레이더 항목 id와 이어지지 않았고, 11-12에 접은 포스코 한정어업 회의록도
// A·'미보도 후보'로 계속 떴다.
//
// 잇는 길 세 가지(위에서부터 확실한 순):
//  ① 패키지에 적힌 레이더 항목 id(package_save의 item_ids → 본문 끝 '연결한 레이더 항목:' 줄, 본문 속 'id …')
//  ② 패키지 본문에 적힌 원문 주소가 항목 원문 주소와 같음
//  ③ 낱말: 같은 출입처 + (사건 번호·문서 번호 같은 부호 1개, 또는 주제 낱말 2개 이상이고 그중 하나는 흔하지 않은 낱말)
// ③은 그 패키지를 남긴 때(+하루)보다 먼저 잡힌 항목에만 쓴다 — 그 뒤 새로 잡힌 항목은 새 사실일 수 있어 숨기지 않고
// '비슷한 건 처리 이력'으로만 알린다(예: 답변 대기 중인 OSHA 점검에 위반 통지가 새로 붙는 경우).
import { BEAT_TEAMS, REGISTRY_NAMES } from './common.mjs';
import { LINK_LINE, storeOp } from './store.mjs';

export const LOG_NAME = /^(?:morning|afternoon|alert)-\d{8}$/;
// 단독 추천에서 빼는 상태. '앞서 추천'(미발제·확인 필요 패키지)은 빼지 않고 따로 보여 준다.
export const EXCLUDING = new Set(['접음', '보류', '발제함', '킬', '씀', '봤음']);
const STATE_OF = { 접음: '접음', 보류: '보류', 발제함: '발제함', '미발제·확인 필요': '앞서 추천' };
const DAY = 86400000;

// 출입처 이름과 흔한 다른 표기(공시 법인명·영문·그룹 약칭). 제목에서 회사를 찾는 데만 쓴다.
const EXTRA = { 현대차: ['현대자동차', 'Hyundai', 'HMGMA', '제네시스'], 기아: ['KIA', 'Kia'], 포스코: ['POSCO'], 한화솔루션: ['한화큐셀', '한화', 'Hanwha', 'Qcells'],
  한국타이어: ['Hankook'], 금호타이어: ['Kumho Tire'], 현대제철: ['Hyundai Steel'], 고려아연: ['Korea Zinc'], LG화학: ['LG Chem'], 롯데케미칼: ['Lotte Chemical'],
  두산에너빌리티: ['Doosan'], 한국GM: ['GM Korea', '한국지엠'], HL만도: ['만도'], 현대모비스: ['Mobis', '모비스'], 태광: ['태광산업'], OCI: ['OCI홀딩스'],
  LS전선: ['LS Cable'], LS일렉트릭: ['LS Electric'], HD현대일렉트릭: ['HD Hyundai Electric'], 세아제강: ['SeAH'], KG스틸: ['KG Steel'] };
const ALIASES = (() => {
  const out = [];
  for (const b of Object.values(BEAT_TEAMS).flat()) out.push([b, b]);
  for (const [raw, b] of Object.entries(REGISTRY_NAMES)) if (raw.length >= 3) out.push([raw, b]);
  for (const [b, list] of Object.entries(EXTRA)) for (const a of list) out.push([a, b]);
  return out.sort((a, b) => b[0].length - a[0].length);
})();
export function companiesIn(text) {
  const t = String(text ?? '');
  const low = t.toLowerCase();
  const out = new Set();
  for (const [alias, beat] of ALIASES) {
    if (/^[A-Za-z .&-]+$/.test(alias) ? new RegExp(`(?<![A-Za-z])${alias.toLowerCase().replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(?![A-Za-z])`).test(low) : t.includes(alias)) out.add(beat);
  }
  return out;
}

// 제목 앞머리 표시([킬]·[답변 대기] …)와 ' — ' 뒤 사유를 뗀 주제 부분
export const subjectOf = (title) => String(title ?? '').replace(/^(?:\s*\[[^\]]*\]\s*)+/, '').split(/\s+[—–]\s+/)[0].trim();

// 낱말 대조에서 빼는 것: 기록 자체의 말(판단·접음…), 어느 건에나 붙는 말, 기관 이름
const STOP = new Set(['기자', '판단', '접음', '보류', '답변', '대기', '재추천', '금지', '관련', '확인', '회사', '단독', '작성', '기사', '보강', '메모', '예약', '후배', '토스',
  '문의', '가능성', '검증용', '공식', '서면', '미상', '약함', '약한', '단서', '용도', '이미', '보도', '무응답', '이유', '의미', '없음', '기준', '미보도', '현지', '출입처',
  '한국산', '중국산', '국내', '해외', '사업장', '주식회사', '앞서', '추천', '가치', '각도', '이후', '진행', '예정', '결과', '여부', '필요', '종합']);
// 흔한 업무 낱말: 맞아도 '흔하지 않은 낱말'로는 안 센다(같은 회사의 다른 건과 겹치기 쉽다)
const COMMON = new Set(['반덤핑', '상계관세', '세이프가드', '공장등록', '건축허가', '가동중지', '서비스', '캠페인', '보증연장', '공급계약', '계약해지', '구제신청',
  '부당노동행위', '부당해고', '행정소송', '손해배상', '최종판정', '예비판정', '잠정관세', '덤핑방지관세', '유상증자', '자기주식', '임원명단', '사외이사', '대표이사',
  '무상수리', '리콜', '결함조사', '회생절차', '가처분', '임단협', '쟁의행위', '조정신청', '수출', '수입', '생산', '판매', '증설', '신축', '증축', '투자', '특허', '상표',
  '소송', '제소', '판결', '조사', '신청', '개시', '계약', '해지', '점검', '통지', '공시', '정정', '인사', '선임', '사임', '파업', '교섭', '조정', '심판', '공장', '목록']);
// 기관 약칭: 맞아도 흔한 낱말로 센다(같은 회사의 다른 건에도 늘 붙는다)
const AGENCY = new Set(['CIT', 'ITC', 'EPA', 'OSHA', 'NHTSA', 'DART', 'TRA', 'FERC', 'USITC', 'EDIS', 'KTC', 'CBSA', 'DGTR', 'CAFC', 'DOC', 'SEC', 'FTA', 'WTO', 'PMS']);
const INSTITUTION = /(?:의회|위원회|노동위|지노위|중노위|무역위|법원|지법|고법|공단|공사|세관|시청|군청|구청|도청)$/;
const MODEL = /^(?:EV\d+|GV\d+|G\d{2}|K\d|Q\d|X\d|iX\d?|ID\d|EX\d+|PV\d|N\d|i\d{2})$/i;

// 부호: 영문+숫자 섞인 4자 이상(AD0071·LA41·WTY050·26V539000), 사건번호(2026부노46), 연도·금액이 아닌 4자리 이상 숫자(337-1494의 1494)
export function codesOf(text) {
  const t = String(text ?? '');
  const out = new Set();
  for (const m of t.matchAll(/(?<![A-Za-z0-9])(?=[A-Za-z0-9]*[A-Za-z])(?=[A-Za-z0-9]*\d)[A-Za-z0-9]{4,}(?![A-Za-z0-9])/g)) if (!MODEL.test(m[0])) out.add(m[0].toUpperCase());
  for (const m of t.matchAll(/\d{4}[가-힣]{1,3}\d{1,6}/g)) out.add(m[0]);
  for (const m of t.matchAll(/(?<![A-Za-z0-9.,])\d{4,}(?![A-Za-z0-9.,]|\s*(?:원|달러|명|대|톤|건|억|만|조|%|년|㎡|주|kg|MW|GWh))/g)) {
    const n = Number(m[0]);
    if (m[0].length === 4 && n >= 1990 && n <= 2039) continue;
    if (m[0].length === 4 && /^(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])$/.test(m[0])) continue;   // 패키지 이름 끝의 날짜(1104·0901)
    if (/^20\d{6}$/.test(m[0])) continue;   // 20261113 같은 날짜
    out.add(m[0]);
  }
  return out;
}
// 주제 낱말: 큰 낱말(한글 3자 이상·영문 3자 이상)과 작은 낱말(한글 2자 — 열연·후판·안성처럼 품목·지역을 가르는 말)
export function wordsOf(subject, companies = new Set()) {
  const names = new Set([...companies, ...ALIASES.filter(([, b]) => companies.has(b)).map(([a]) => a)]);
  const major = new Set();
  const minor = new Set();
  for (const tok of String(subject ?? '').split(/[^0-9A-Za-z가-힣]+/)) {
    if (!tok || /\d/.test(tok) || STOP.has(tok) || names.has(tok) || INSTITUTION.test(tok)) continue;
    if (tok.length >= 3) major.add(tok);
    else if (tok.length === 2 && /^[가-힣]+$/.test(tok) && !COMMON.has(tok)) minor.add(tok);
  }
  return { major, minor };
}
// 한글 지명 ↔ 원문 영문 표기(미국 주 정부·OSHA 자료는 영문뿐이다)
const PLACE_EN = { 조지아: 'georgia', 앨라배마: 'alabama', 테네시: 'tennessee', 루이지애나: 'louisiana', 텍사스: 'texas', 인디애나: 'indiana', 미시간: 'michigan',
  오하이오: 'ohio', 켄터키: 'kentucky', 영국: 'united kingdom', 호주: 'australia', 캐나다: 'canada', 인도네시아: 'indonesia', 베트남: 'vietnam' };
const rare = (w) => !COMMON.has(w) && !AGENCY.has(w.toUpperCase());
// 영문 낱말은 낱말 경계로만 맞춘다 — 붙여 쓴 글에서 찾으면 'Cat'이 'Application'에 걸린다(11-13 운영: 기아 조지아 OSHA 건이 대기 허가 기준선 줄에 붙음)
const esc = (w) => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const latinIn = (low, w) => new RegExp(`(?<![a-z])${esc(w.toLowerCase()).replace(/\s+/g, '\\s+')}(?![a-z])`).test(low);
const inText = (flat, low, w) => (/^[A-Za-z]+$/.test(w) ? latinIn(low, w) : flat.includes(w.toLowerCase())) || (PLACE_EN[w] ? latinIn(low, PLACE_EN[w]) : false);

const idsIn = (body) => {
  const out = new Set();
  const line = String(body ?? '').split('\n').reverse().find((l) => l.startsWith(LINK_LINE));
  for (const id of (line ?? '').slice(LINK_LINE.length).split(',')) if (id.trim()) out.add(id.trim());
  // 본문에 옮겨 적힌 'id xxx' (radar_today·scoop_desk 줄 끝 표기)
  for (const m of String(body ?? '').matchAll(/(?:^|[\s·(])id[ :]+([A-Za-z][A-Za-z0-9_-]*:[^\s,)〕]+|[0-9a-f]{16})/g)) out.add(m[1]);
  return out;
};
const urlsIn = (body) => new Set([...String(body ?? '').matchAll(/https?:\/\/[^\s)\]〕"'<>]+/g)].map((m) => m[0].replace(/[.,;]+$/, '')).filter((u) => u.length >= 25));

// 패키지·판정 → 장부 줄
export function ledgerEntries(packages = [], feedback = []) {
  const byName = new Map();
  const fbOf = new Map(feedback.map((r) => [String(r.item_id), r]));
  const alerted = new Map();   // 레이더 id → 알림 보낸 날(MM-DD)
  for (const p of packages) {
    const m = /^alert-(\d{4})(\d{2})(\d{2})$/.exec(p.name);
    if (m) {
      const line = String(p.body ?? '').split('\n').reverse().find((l) => /^보낸 id\s*:/.test(l.trim()));
      for (const id of (line ?? '').replace(/^.*?:/, '').split(',')) if (id.trim()) alerted.set(id.trim(), `${m[2]}-${m[3]}`);
      continue;
    }
    if (LOG_NAME.test(p.name)) continue;
    const fb = fbOf.get(p.name);
    const subject = subjectOf(p.title);
    const companies = companiesIn(`${subject} ${p.name}`);
    const state = fb && EXCLUDING.has(fb.verdict) && p.state === '미발제·확인 필요' ? fb.verdict : STATE_OF[p.state] ?? '앞서 추천';
    const tag = (/^\s*\[([^\]]+)\]/.exec(p.title) ?? [])[1] ?? '';
    byName.set(p.name, { key: p.name, source: '패키지', state, tag, title: String(p.title ?? ''), subject, reason: fb?.reason ?? '',
      at: Date.parse(p.updated_at) || 0, companies, codes: codesOf(`${subject} ${p.name.replace(/-/g, ' ')}`), words: wordsOf(subject, companies),
      ids: idsIn(p.body), urls: urlsIn(p.body) });
  }
  return { entries: [...byName.values()], alerted };
}

const itemTime = (x) => { const t = Date.parse(String(x.date ?? '').length === 10 ? `${x.date}T00:00:00+09:00` : x.date ?? ''); return Number.isFinite(t) ? t : 0; };
const squash = (s) => String(s ?? '').replace(/\s+/g, '').toLowerCase();

// 낱말 대조(③) — { codes, words } 또는 null. companyText: 회사를 찾을 글(항목의 회사 칸, 글 덩어리면 전체)
export function wordMatch(text, companyText, e) {
  const itemCos = companiesIn(companyText);
  const known = e.companies.size > 0 && itemCos.size > 0;
  if (known && ![...e.companies].some((c) => itemCos.has(c))) return null;
  const up = String(text).toUpperCase();
  const codes = [...e.codes].filter((c) => new RegExp(`(?<![A-Z0-9])${c.toUpperCase().replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(?![A-Z0-9])`).test(up));
  if (codes.length) return { codes, words: [] };
  const flat = squash(text);
  const low = String(text).toLowerCase();
  const major = [...e.words.major].filter((w) => inText(flat, low, w));
  const minor = [...e.words.minor].filter((w) => flat.includes(w));
  const R = major.filter(rare).length;
  // 마지막 조건: 흔한 큰 낱말 하나 + 품목·지역 낱말 둘(같은 회사) — 'KG스틸 인천·당진 굴뚝 … 가동중지'처럼 흔한 말뿐인 제목
  const ok = known ? (R >= 2 || (R >= 1 && (major.length >= 2 || minor.length >= 1)) || (major.length >= 2 && minor.length >= 1) || (major.length >= 1 && minor.length >= 2))
    : (R >= 2 && major.length + minor.length >= 3);   // 회사를 못 맞춘 쪽은 더 엄격하게
  return ok ? { codes, words: [...major, ...minor] } : null;
}
const itemText = (x) => `${x.watch ?? ''} ${x.kind ?? ''} ${x.fact ?? ''} ${x.id ?? ''} ${x.url ?? ''}`;

// 항목 하나 → { entry, how } (다시 내지 않을 것) · { similar } (비슷한 건 처리 이력, 숨기지 않음) · null
export function matchHandled(item, ledger) {
  const id = String(item.id ?? '');
  let similar = null;
  for (const e of ledger?.entries ?? []) {
    if (e.ids.has(id) || (item.parent && e.ids.has(String(item.parent)))) return { entry: e, how: 'id' };
    if (item.url && e.urls.has(String(item.url).replace(/[.,;]+$/, ''))) return { entry: e, how: '원문 주소' };
    const w = wordMatch(itemText(item), `${item.company ?? ''} ${String(item.fact ?? '').slice(0, 200)}`, e);
    if (!w) continue;
    const t = itemTime(item);
    if (!t || t <= e.at + DAY) return { entry: e, how: `낱말(${[...w.codes, ...w.words].slice(0, 4).join('·')})` };
    similar ??= e;
  }
  return similar ? { similar } : null;
}

const mmdd = (ms) => new Date(ms + 9 * 3600000).toISOString().slice(5, 10);
// 도구 글의 항목 덩어리(들여쓰지 않은 줄 + 뒤따르는 들여쓴 줄)마다 처리 이력을 붙인다 — 구역 도구(us_litigation·trade_remedies·kr_official …)는
// 오늘 새 항목이 아니라 '지금 상태'를 보여 줘서, 기자가 이미 처리한 건(답변 대기 중인 OSHA 점검 등)이 볼 때마다 다시 나온다.
export function annotateHandled(text, ledger) {
  const entries = (ledger?.entries ?? []).filter((e) => EXCLUDING.has(e.state));
  if (!entries.length || !text) return { text, marked: 0 };
  const lines = String(text).split('\n');
  const skip = /^(?:\s|\[|규칙|다음:|\(|…|정리:|판정은|읽는 법|$)/;
  const indent = (l) => /^\s*/.exec(l)[0].length;
  // 묶음 머리줄('- 출입처 사건 · 최근 30일 3건') 아래 들여쓴 항목 줄 — 표시는 머리줄이 아니라 그 항목 줄에 붙인다(머리줄에 붙이면 묶음 전체가 처리된 것으로 읽힌다)
  const SUB = /^\s+(?:[ABC] · |\[기준선\]|\[신규\])/;
  const TAIL = /^\s*(?:검증 상태|규칙|읽는 법)/;
  let marked = 0;
  const mark = (from, to) => {
    const block = lines.slice(from, to).join('\n');
    if (block.length < 12 || block.includes('〔이미 처리') || block.includes('〔처리 이력')) return;
    let hit = null;
    for (const e of entries) {
      if ([...e.urls].some((u) => block.includes(u)) || [...e.ids].some((id) => block.includes(`id ${id}`))) { hit = e; break; }
      if (wordMatch(block, block, e)) { hit = e; break; }
    }
    if (!hit) return;
    const d = /(?<!\d)(20\d{2})[-/.](\d{2})[-/.](\d{2})(?!\d)/.exec(lines[from]);   // 2026-11-24 · 2026/11/24(EDIS 접수일)
    const later = d && Date.parse(`${d[1]}-${d[2]}-${d[3]}T00:00:00+09:00`) > hit.at + DAY;
    lines[from] += later ? ` 〔처리 이력 있음: ${entryLabel(hit)} · ${mmdd(hit.at)} — 그 뒤 새 항목일 수 있음(새 사실인지 확인)〕`
      : ` 〔이미 처리: ${entryLabel(hit)} · ${mmdd(hit.at)} — 단독 추천에서 뺀다(새 사실이 붙었을 때만 다시)〕`;
    marked += 1;
  };
  for (let i = 0; i < lines.length; i += 1) {
    if (skip.test(lines[i])) continue;
    let j = i + 1;
    while (j < lines.length && /^\s+\S/.test(lines[j])) j += 1;
    const subs = [];
    for (let k = i + 1; k < j; k += 1) if (SUB.test(lines[k])) subs.push(k);
    if (!subs.length) mark(i, j);
    else subs.forEach((k, n) => {
      let end = k + 1;
      const stop = subs[n + 1] ?? j;
      while (end < stop && indent(lines[end]) > indent(lines[k]) && !TAIL.test(lines[end])) end += 1;
      mark(k, end);
    });
    i = j - 1;
  }
  return { text: lines.join('\n'), marked };
}

export function entryLabel(e) { return entryLabelOf(e); }
const entryLabelOf = (e) => `[${e.state}${e.tag && e.tag !== e.state && e.tag !== '킬' ? `·${e.tag}` : ''}] ${e.subject || e.key}`;

export async function loadLedger(ctx, feedback = null) {
  const [{ rows: packages }, fb] = await Promise.all([storeOp(ctx, 'packages.digest', {}),
    feedback ? Promise.resolve({ rows: feedback }) : storeOp(ctx, 'feedback.latest', {})]);
  return { ...ledgerEntries(packages ?? [], fb.rows ?? []), feedback: fb.rows ?? [] };
}
