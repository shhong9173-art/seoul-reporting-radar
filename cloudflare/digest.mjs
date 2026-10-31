// radar_today: one private digest over the eleven private watches. It reads what the collectors already stored
// (no new fetching), keeps what is new since a cutoff, and ranks it. Failed or stale watches are listed first:
// their silence is "미확인", not "nothing new".
import { readFeed } from './screen.mjs';
import { storeOp } from './store.mjs';
import { dispatchHealth } from './dispatch.mjs';
import { clampInt, safeEqual, textResult, uniqueList } from './common.mjs';
import { classLabel, waitReason } from './trademarks.mjs';
import { billLine, groupBillEvents } from './assembly.mjs';
import { buildingLine, factoryEventText, identityNote } from './overseas.mjs';

const KST_MS = 9 * 3600000;
const kstDate = (ms) => new Date(ms + KST_MS).toISOString().slice(0, 10);
const kstStamp = (v) => { const t = Date.parse(v); return Number.isFinite(t) ? new Date(t + KST_MS).toISOString().slice(5, 16).replace('T', ' ') : String(v ?? '').slice(0, 16); };
// EDGAR hits count as direct changes only when the excerpt reads like a deal with the beat company.
const DEAL_WORDS = /\b(agreement|supply|offtake|off-take|joint venture|\bJV\b|memorandum|MOU|partnership|collaborat\w*|acquisition|acquire[sd]?|merger|purchase order|contract\w*|guarantee\w*|licen[cs]e|investment in|strategic|customer|order[s]? from)\b/i;
const ymd8 = (v) => (/^\d{8}/.test(String(v ?? '')) ? `${String(v).slice(0, 4)}-${String(v).slice(4, 6)}-${String(v).slice(6, 8)}` : String(v ?? '').slice(0, 10));
const has = (q, ...fields) => !q || fields.some((f) => String(f ?? '').toLowerCase().includes(q.toLowerCase()));

const KTC_KIND = { case: '무역위 새 조사', step: '무역위 진행일정', left: '무역위 진행 목록에서 빠짐', meeting: '무역위 회의 안건', agenda: '무역위 회의 안건',
  news: '무역위 보도자료' };

export const WATCHES = [
  { feed: 'scoop-screen', label: '단독 후보 심사', tool: 'scoop_screen', schedule: '평일 07:10·15:10' },
  { feed: 'kr-official', label: '공장등록·관보', tool: 'kr_official', schedule: '평일 08:10' },
  { feed: 'kr-signals', label: '공정위·한전·원자재', tool: 'kr_signals', schedule: '평일 08:30·15:20' },
  { feed: 'kr-stats', label: '월간 통계(물가·생산·수입차·완성차 판매)', tool: 'kr_stats', schedule: '평일 07:30' },
  { feed: 'trade-remedy', label: '무역구제', tool: 'trade_remedies', schedule: '평일 07:40' },
  { feed: 'us-litigation', label: '미국 소송·ITC', tool: 'us_litigation', schedule: '평일 07:50' },
  { feed: 'partner-filings', label: '해외 파트너 공시', tool: 'partner_filings', schedule: '평일 07:00' },
  { feed: 'us-comments', label: '미 연방 의견서', tool: 'us_comments', schedule: '평일 08:20' },
  { feed: 'page-watch', label: '해외 공식 페이지', tool: 'page_changes', schedule: '평일 06:30·18:30' },
  { feed: 'trademarks', label: '상표 출원', tool: 'trademarks', schedule: '월 07:10', staleHours: 192 },
  { feed: 'assembly-bills', label: '국회 법안', tool: 'assembly_bills', schedule: '평일 08:40·17:40' },
  { feed: 'us-recalls', label: '미국 리콜(NHTSA 전체)', tool: 'us_recalls', schedule: '평일 17:10' },
  { feed: 'us-epa', label: '미국 EPA 인증', tool: 'us_epa', schedule: '매일 06:20', staleHours: 60 },
  { feed: 'kr-fuel', label: '국내 연비 신고', tool: 'kr_fuel', schedule: '매일 06:10', staleHours: 60 },
  { feed: 'overseas-awards', label: '해외 발주처 낙찰', tool: 'partner_filings', schedule: '평일 06:50·17:30' },
  { feed: 'kr-insolvency', label: '협력사 회생·파산', tool: 'kr_official', schedule: '평일 07:20·17:20' },
  { feed: 'kr-energy', label: '전기위·원안위', tool: 'kr_signals', schedule: '평일 15:40·18:10' },
  { feed: 'kr-building', label: '공장 부지 건축허가', tool: 'kr_official', schedule: '월 07:45', staleHours: 192 },
  { feed: 'overseas-registry', label: '해외 법인 등기(영국)', tool: 'partner_filings', schedule: '평일 06:00' },
  { feed: 'kr-local', label: '지자체 고시·공고', tool: 'kr_official', schedule: '평일 06:30·16:20' },
  { feed: 'kr-workforce', label: '사업장 인력(국민연금)', tool: 'kr_official', schedule: '평일 15:50', staleHours: 80 },
  { feed: 'kr-stacks', label: '굴뚝 측정(공장 가동 신호)', tool: 'kr_official', schedule: '3시간마다', staleHours: 12 },
];

// Items first seen in a watch's very first run are a baseline, not news: they only count when their own date is recent.
function baselineOf(rows, key = 'firstSeen') {
  const times = rows.map((x) => Date.parse(x[key])).filter(Number.isFinite);
  return times.length ? Math.min(...times) : null;
}

function isFresh(x, cut, cutDay, base, dateKey) {
  const seen = Date.parse(x.firstSeen);
  const own = String(x[dateKey] ?? '').slice(0, 10);
  if (own && own >= cutDay) return true;
  return Number.isFinite(seen) && seen >= cut && !(base !== null && Math.abs(seen - base) < 120000);
}

// Press-check hints (radar_press_check.py): the subject a story would name and the words it would use. Only items whose
// subject is a beat company (or a bill's law name) get one; the checker screens nothing else. Hints are search words,
// not facts — the item's own line stays as collected.
const ALT = {
  소송: ['소송', '제소', '판결', '항소', '불복'], 국제무역법원: ['국제무역법원', '무역법원', 'CIT'], 항소: ['항소', '불복', '소송', '항소법원'],
  특허: ['특허', '특허심판원', 'PTAB', '무효'], 판결: ['판결', '패소', '승소', '기각', '판정', '결정'], 상계관세: ['상계관세', '보조금'],
  반덤핑: ['반덤핑', '덤핑'], ITC: ['ITC', '무역위원회'], 특허침해: ['특허', '침해', '337조', '수입 금지', '제소'],
  공장: ['공장', '사업장', '생산기지'], 폐쇄: ['폐쇄', '매각', '철수', '가동 중단', '문 닫', '공장 이전', '생산 중단'],
  신설: ['신설', '준공', '가동', '건설', '착공', '신축', '증설', '새 공장'], 인력: ['인력', '인원', '직원', '고용', '근로자', '임직원'],
  감축: ['감축', '감소', '구조조정', '희망퇴직', '감원', '줄여', '줄었'], 증원: ['증원', '늘려', '늘었', '확대', '증가'],
  // 인력 변화(국민연금·공장등록 고용): 한 낱말 묶음만 쓴다 — '고용·인력·감소·확대'처럼 흔한 말은 다른 기사도 잡는다
  // (10-31 운영: 기아 가입자 증가가 「'효율·고용' 절충…현대차·기아 공장 재편안」으로 '관련 보도 있음').
  채용: ['채용', '증원', '충원', '신입', '공채', '인력 확대', '인원 확대', '인력 증가', '인원 증가'],
  감원: ['감원', '감축', '구조조정', '희망퇴직', '인력 감소', '인원 감소', '인력 축소', '정리해고'],
  공정위: ['공정위', '공정거래위원회'], 과징금: ['과징금', '제재', '시정명령', '고발', '경고'], 한전: ['한전', '한국전력'],
  수주: ['수주', '입찰', '낙찰', '공급', '계약'], 관세: ['관세', '반덤핑', '상계관세', '덤핑'], 판정: ['판정', '예비', '최종', '재심', '연례재심'],
  계약: ['계약', '협약', '합의', '공급', '합작', 'MOU'], 의견서: ['의견서', '의견', '제출', '요청'], 상표: ['상표', '출원', '브랜드', '명칭'],
  개정안: ['개정안', '발의', '법안', '개정', '대표발의'], BAIC: ['BAIC', '베이징자동차', '베이징기차', '北汽'],
  합작: ['합작', '지분', '매각', '정리', '철수', '계약', '합작사'], 보조금: ['보조금', '상계관세', '어린이집', '직장', '지원'],
  리콜: ['리콜', '결함', '시정조치', '화재 위험'], 가격: ['가격', '판매가', '출고가', 'MSRP', '값'], 미국: ['미국', '美'],
  EPA: ['EPA', '환경보호청', '인증', '주행거리', '연비'],
  회생: ['회생', '법정관리', '파산', '기업회생', '워크아웃'],
  허가: ['허가', '인가', '승인', '전기위원회'], 법인: ['법인', '현지법인', '자회사', '설립'], 영국: ['영국', 'UK'], 원안위: ['원안위', '원자력안전위원회', '의결', '심의'],
  발주: ['발주', '입찰', '낙찰', '구매'],
  산소공장: ['산소공장', '산소 공장', '산소플랜트', 'ASU', '공기분리'],
  환경영향평가: ['환경영향평가', '환경평가'], 산업단지: ['산업단지', '산단'], 이전: ['이전', '옮겨', '옮긴다'], 매립: ['매립', '매립장'],
};
const ASX_KO = { PLS: '필바라', ARU: '아라푸라', '01958': 'BAIC' };
// EDGAR 공시 회사의 한국 기사 표기(앞부분만 — '넥사 리소시스'·'클리블랜드-클리프스' 모두 맞게). 표기를 모르면 보도 대조를 하지 않는다:
// 영문 첫 낱말('FIRST' 등)로 찾으면 아무 기사도 못 찾아 '미보도 후보'가 된다(10-31 운영: 한화솔루션 FIRST SOLAR 10-Q).
const EDGAR_KO = { FSLR: '퍼스트솔라', NEXA: '넥사', CLF: '클리블랜드', KT: 'KT', PBK: '파워뱅크', ALB: '앨버말', TSLA: '테슬라', GM: 'GM', F: '포드',
  RIVN: '리비안', NUE: '뉴코어', STLD: '스틸다이내믹스', X: 'US스틸', FCX: '프리포트', SQM: 'SQM', LAC: '리튬아메리카스', ENPH: '엔페이즈', NEE: '넥스트에라' };
// 발췌가 소송·특허 서술이면 '계약' 대신 '특허'로 찾는다(10-31: 퍼스트솔라 10-Q의 한화큐셀 특허침해 USITC 청원 문단)
const LITIGATION = /\b(?:infring\w*|lawsuit|complaint|petition|USITC|litigation|patent\w*)\b/i;
const COUNTRY_KO = {
  DNK: '덴마크', SWE: '스웨덴', FIN: '핀란드', NOR: '노르웨이', ESP: '스페인', PRT: '포르투갈', GBR: '영국', DEU: '독일', NLD: '네덜란드', BEL: '벨기에',
  FRA: '프랑스', ITA: '이탈리아', IRL: '아일랜드', AUT: '오스트리아', POL: '폴란드', CZE: '체코', SVK: '슬로바키아', HUN: '헝가리', ROU: '루마니아',
  BGR: '불가리아', GRC: '그리스', HRV: '크로아티아', SVN: '슬로베니아', EST: '에스토니아', LVA: '라트비아', LTU: '리투아니아', CHE: '스위스', BHR: '바레인', TWN: '대만',
  Iraq: '이라크', Jordan: '요르단', 'Egypt, Arab Republic of': '이집트', Morocco: '모로코', Tunisia: '튀니지', Lebanon: '레바논', Uzbekistan: '우즈베키스탄',
  Kazakhstan: '카자흐스탄', India: '인도', Bangladesh: '방글라데시', Pakistan: '파키스탄', 'Viet Nam': '베트남', Philippines: '필리핀', Indonesia: '인도네시아',
  Ukraine: '우크라이나', 'South Africa': '남아공', Kenya: '케냐', Nigeria: '나이지리아', Ethiopia: '에티오피아', Turkiye: '튀르키예', Mongolia: '몽골',
};
export const countryKo = (c) => COUNTRY_KO[String(c ?? '').trim()];
export const firmName = (n) => String(n ?? '').replace(/주식회사|\(주\)|㈜|\(\d{3}-\d{2}-\d{5}\)/g, '').trim();
export function insolvencyLine(e) {
  const ind = e.industry ?? {};
  const what = e.watch ? `출입처 협력사 명단(${[e.watch.beat, e.watch.relation].filter(Boolean).join(' · ')})`
    : ind.label ? `공장등록 업종 ${ind.label}${ind.product ? ` · 주생산품 ${uniqueList(ind.product).slice(0, 40)}` : ''}${ind.employees != null ? ` · 종업원 ${ind.employees}명` : ''}`
      : '공장등록 없음 — 이름 낱말만';
  const where = ind.address ? ` · ${String(ind.address).split(/\s+/).slice(0, 2).join(' ')}` : '';
  return `${e.company} (${e.court}${e.caseNo ? ` ${e.caseNo}` : ''}) · ${what}${where}${identityNote(ind)}`;
}
// places: search words that narrow the query (시·군, 나라) but cannot mark a story alone — a headline with the company and
// its city is often another story (10-31: 고려아연 울주 안전점검 공고가 '고려아연 온산제련소 지원 울주군 집수리' 기사로 '관련 보도 있음').
// must: an article has to name one of these (title or text) to count — for a site of a company with several (포스코 광양·포항).
export function hint(who, terms, places = [], must = [], names = []) {
  const subject = String(who ?? '').split('·')[0].replace(/\(.*?\)/g, '').trim();
  const t = [...new Set(terms.filter(Boolean).map(String))];
  if (!subject || !t.length) return undefined;
  const p = [...new Set(places.filter(Boolean).map(String))].filter((w) => t.includes(w));
  const m = [...new Set(must.filter(Boolean).map(String))];
  const n = [...new Set(names.filter(Boolean).map(String))];
  return { who: subject, terms: t, alts: Object.fromEntries(t.filter((w) => ALT[w]).map((w) => [w, ALT[w]])),
    ...(p.length ? { places: p } : {}), ...(m.length ? { must: m } : {}), ...(n.length ? { names: n } : {}) };
}
// 법 이름 → 기사 제목이 쓰는 줄임말. 정식 이름으로만 찾으면 '산업기술보호법 개정안' 기사를 못 찾는다(10-31 운영: '산업기술의 유출방지 및
// 보호에 관한 법률 개정안 백혜련'으로 찾아 미보도 후보). 질의는 첫 줄임말, 기사 대조는 줄임말·정식 이름 어느 것이든.
const LAW_SHORT = {
  '산업기술의 유출방지 및 보호에 관한 법률': ['산업기술보호법'],
  '국가첨단전략산업 경쟁력 강화 및 보호에 관한 특별조치법': ['국가첨단전략산업법', '첨단전략산업법'],
  '분산에너지 활성화 특별법': ['분산에너지법', '분산에너지 특별법', '분산에너지특별법'],
  '노동조합 및 노동관계조정법': ['노조법', '노란봉투법'],
  '석유 및 석유대체연료 사업법': ['석유사업법'],
  '신에너지 및 재생에너지 개발ㆍ이용ㆍ보급 촉진법': ['신재생에너지법', '재생에너지법'],
  '국가기간 전력망 확충 특별법': ['전력망특별법', '전력망법', '전력망 특별법'],
  '중대재해 처벌 등에 관한 법률': ['중대재해처벌법', '중대재해법'],
  '기후위기 대응을 위한 탄소중립ㆍ녹색성장 기본법': ['탄소중립기본법', '탄소중립법'],
  '온실가스 배출권의 할당 및 거래에 관한 법률': ['배출권거래법'],
  '화학물질의 등록 및 평가 등에 관한 법률': ['화평법'],
  화학물질관리법: ['화학물질관리법', '화관법'],
  '환경친화적 자동차의 개발 및 보급 촉진에 관한 법률': ['친환경차법'],
  '수소경제 육성 및 수소 안전관리에 관한 법률': ['수소법', '수소경제법'],
  '자율주행자동차 상용화 촉진 및 지원에 관한 법률': ['자율주행차법', '자율주행법'],
  '불공정무역행위 조사 및 산업피해구제에 관한 법률': ['불공정무역행위법', '산업피해구제법'],
  '해상풍력 보급 촉진 및 산업 육성에 관한 특별법': ['해상풍력특별법', '해상풍력법'],
  '고준위 방사성폐기물 관리 특별법': ['고준위특별법', '고준위방폐물법', '고준위법'],
  '공급망 안정화 등 경제안보를 위한 기본법': ['공급망기본법', '공급망법'],
  '외국인투자 촉진법': ['외국인투자촉진법', '외투법'],
  '철강산업 경쟁력 강화 및 탄소중립 전환을 위한 특별법': ['K-스틸법', 'K스틸법', '철강특별법', '철강산업 특별법'],
};
const lawKey = (law) => String(law ?? '').replace(/\s+/g, '').replace(/[·・]/g, 'ㆍ');
const LAW_SHORT_BY_KEY = Object.fromEntries(Object.entries(LAW_SHORT).map(([k, v]) => [lawKey(k), v]));
export function billHint(g) {
  const short = LAW_SHORT_BY_KEY[lawKey(g.law)] ?? [];
  // 줄임말이 있으면 그것을 주어로(법 이름의 '·'에서 잘리지 않게), 기사 대조는 줄임말·정식 이름 모두
  return hint(short[0] ?? g.law, ['개정안', (g.leads ?? [])[0]], [], g.leads ?? [], short.length ? [...short, g.law] : []);
}
// 굴뚝 측정 사업장 이름의 지명(㈜포스코 광양제철소 → 광양, 현대자동차㈜ 울산공장 → 울산, ㈜영풍석포제련소 → 석포)
export function siteCity(site) {
  const s = String(site ?? '').replace(/㈜|\(주\)|주식회사/g, ' ');
  return (/([가-힣]{2})\s*\d*\s*(?:제철소|제련소|공장|사업장|사업소)/.exec(s) ?? [])[1];
}
// 지자체 고시·공고 제목의 사업 낱말 → 기사가 쓸 낱말(안전점검·건설공사 공고의 기사는 '증설·신설·착공'으로 난다)
export function localWord(title) {
  const t = String(title ?? '');
  // 산소공장(공기분리장치 ASU): 기사는 '산소공장 증설'로 쓴다(10-20 전자신문 「고려아연, 산소공장 증설 발주 87% 완료」)
  if (/(?<![A-Za-z])ASU\b|산소\s*(?:공장|플랜트)|공기\s*분리/.test(t)) return '산소공장';
  if (/환경영향평가/.test(t)) return '환경영향평가';
  if (/산업단지/.test(t)) return '산업단지';
  if (/매립/.test(t)) return '매립';
  if (/이전/.test(t)) return '이전';
  return '신설';
}
// 한전 입찰: 기사는 '한전, 765kV 변압기 발주'처럼 한전과 품목으로 난다. 예전엔 발주처 이름(한국전력공사)을 회사로, '한전'을 낱말로 넣어
// "한국전력공사 한전"으로 찾았다(10-31 운영: 765kV 전력용변압기 신안성S/S 입찰).
export function kepcoHint(name) {
  const t = String(name ?? '');
  const volt = (/(\d{2,3})\s*k[vV]/.exec(t) ?? [])[1];
  const product = (/(변압기|차단기|개폐기|GIS|가스절연|리액터|전선|케이블|철탑|애자|변성기|계량기|조상설비|STATCOM|ESS)/.exec(t) ?? [])[1];
  return hint('한전', [volt ? `${volt}kV` : null, product, '발주'], volt ? [`${volt}kV`] : []);
}
// 굴뚝 측정: 사업장 지명을 검색에 넣고, 그 지명이 없는 기사는 같은 사건으로 치지 않는다(10-31: 포스코 광양 배출구 멈춤 ↔ 포항제철소 기사)
export function stackHint(e) {
  const city = siteCity(e.site ?? e.text);
  const words = /배출허용기준/.test(e.kind) ? ['배출허용기준', '초과'] : /재가동/.test(e.kind) ? ['재가동'] : /새/.test(e.kind) ? ['신설', '가동'] : ['가동 중단', '정비'];
  return hint(e.company, [city, ...words], [city], [city]);
}
// 국민연금 가입자 변화의 방향 → 기사 낱말(늘면 채용·증원, 줄면 인력 감축). 사업장 주소의 시·군을 넣고, 그 지명이 없는 기사는
// 같은 사건으로 치지 않는다(10-31 운영: 포스코 포항 가입자 +866명 ↔ '현대제철·포스코 美 제철소 1000명 채용' 기사로 '관련 보도 있음')
// 미국 리콜 보도 대조: 브랜드만으로 찾으면 같은 브랜드의 다른 리콜 기사가 근거로 붙는다(10-31 운영: 현대차 26V692000 아반떼·투싼
// 하이브리드 스트럿 체결 24대 ↔ 「현대차 '측면 에어백 센서' 리콜 남아공 확산…투싼 253대」). 차종(국문 이름·영문)과 대상 대수가
// 기사 제목·요약에 하나는 있어야 같은 리콜로 센다. 부품사 이름이 영문뿐이면(원보고서 공급사 칸: SAMJIN NUT·NIDEC MOBILITY KOREA)
// 그 이름으로는 국내 기사를 못 찾으니 브랜드로 찾는다(한글 이름 부품사 — SK온 등 — 은 그대로 부품사로).
const US_MODEL_KO = {
  elantra: ['아반떼', '엘란트라'], sonata: ['쏘나타'], tucson: ['투싼'], 'santa fe': ['싼타페'], 'santa cruz': ['싼타크루즈'],
  palisade: ['팰리세이드'], kona: ['코나'], venue: ['베뉴'], ioniq: ['아이오닉'], nexo: ['넥쏘'], sorento: ['쏘렌토'], sportage: ['스포티지'],
  telluride: ['텔루라이드'], carnival: ['카니발'], forte: ['포르테', 'K3'], soul: ['쏘울'], niro: ['니로'], seltos: ['셀토스'],
  trax: ['트랙스'], trailblazer: ['트레일블레이저'], envista: ['엔비스타'], encore: ['앙코르'],
};
const BRAND_WORDS = /^(HYUNDAI|KIA|GENESIS|AUDI|VOLKSWAGEN|VW|BMW|MINI|MERCEDES-BENZ|MERCEDES|HONDA|ACURA|CHEVROLET|BUICK|GMC)$/;
export function usRecallModels(models) {
  const s = ` ${String(models ?? '').toLowerCase()} `;
  const out = [];
  for (const [k, v] of Object.entries(US_MODEL_KO)) if (new RegExp(`[^a-z0-9]${k}[^a-z0-9]`).test(s)) out.push(...v);
  if (!out.length) {  // 수입차·영문 그대로 쓰는 차종(X3·Q4·GLC·CR-V·K5·EV6·G80): 브랜드 낱말·연식 뺀 첫 낱말
    const w = String(models ?? '').split(/[\s,·]+/).find((t) => /^[A-Z0-9][A-Z0-9.-]{1,9}$/i.test(t) && !BRAND_WORDS.test(t.toUpperCase()) && !/^\d{4}(~\d{4})?$/.test(t));
    if (w) out.push(w.toUpperCase());
  }
  return [...new Set(out)];
}
export function countForms(n) {
  if (!(n >= 1000)) return [];
  const man = Math.floor(n / 10000), rest = n % 10000;
  const out = [n.toLocaleString('en-US'), String(n)];
  if (man) {
    out.push(`${man}만${rest || ''}`, `${man}만${rest ? rest.toLocaleString('en-US') : ''}`, `${man}만 ${rest || ''}`.trim());
    if (rest && rest % 1000 === 0) out.push(`${man}만${rest / 1000}천`);
  }
  return [...new Set(out)];
}
export function usRecallHint(x, why) {
  const supplier = why.find((w) => String(w.role).startsWith('부품'));
  const brand = why.find((w) => String(w.role).startsWith('제조사'));
  const models = usRecallModels(x.models);
  const ids = [...models, ...countForms(Number(x.affected ?? 0))];
  if (supplier && /[가-힣]/.test(String(supplier.name)) && brand) return hint(supplier.name, ['리콜', brand.name], [], ids);
  const who = brand?.name ?? supplier?.name ?? why[0]?.name;
  return models.length ? hint(who, [models[0], '리콜'], [models[0]], ids) : hint(who, ['리콜', '미국'], [], ids);
}
// 정정사유를 큰 변경 옆에 붙인다 — 날짜가 크게 당겨진 이유가 '취득완료'인지 '계약 해지'인지 줄에서 바로 보이게
// (10-31 운영: 금호타이어 함평 부지 취득 정정 '취득예정일자 -36개월'은 사유가 '취득완료(취득가액 및 취득일자 확정)에 따른 정정')
// 한 줄 요약용: 낱말 중간에서 자르지 않고 ' · ' 구분에서 자른다(10-31 운영: '… · 취득물건구분 토지 및 건물 · 취 · id …')
export function clipAt(text, n) {
  const s = String(text ?? '');
  if (s.length <= n) return s;
  const cut = s.slice(0, n);
  const at = cut.lastIndexOf(' · ');
  return `${(at > n * 0.5 ? cut.slice(0, at) : cut.replace(/\s+\S*$/, '')).trimEnd()} …`;
}

// 정정 내용 보도 대조(scoop_screen check_corrections): 원 공시 기사와 따로, 변경 낱말(연장·감액·해지 등)로 찾은 결과
export function correctionNote(cc) {
  const base = "원 공시 보도 대조 '관련 보도 있음'은 원 계약 기사일 수 있음";
  if (!cc || !cc.verdict) return `${base}(정정 내용 보도 여부는 따로 확인)`;
  const q = (cc.queries ?? []).map((x) => `"${x}"`).join(', ');
  const top = (cc.evidence ?? []).find((e) => !e.before && /동일 사건 미확정/.test(e.why ?? ''));
  if (cc.verdict === '관련 보도 있음' && top) return `정정 내용 보도 대조: 관련 보도 있음 — ${top.date ?? ''} 「${String(top.title ?? '').slice(0, 60)}」(같은 내용인지 열어 볼 것)`;
  if (cc.verdict === '미보도 후보') return `정정 내용 보도 대조: 미보도 후보 — ${q}로 ${cc.since} 이후 '${cc.word}' 기사 못 찾음(검색 범위 결과, 단독 판정 아님) · ${base}`;
  return `정정 내용 보도 대조: ${cc.verdict}(채널 실패 등) · ${base}`;
}
const fixReason = (r) => (r ? ` · 사유 '${String(r).length > 40 ? `${String(r).slice(0, 39)}…` : r}'` : '');
export function workforceHint(e) {
  if (/공사 현장/.test(e.kind)) return hint(e.company, ['공사', '착공']);
  if (/새 자사/.test(e.kind)) return hint(e.company, ['공장', '신설']);
  if (/탈퇴|빠짐/.test(e.kind)) return hint(e.company, ['공장', '폐쇄']);
  const m = /가입자 ([\d,]+)→([\d,]+)명/.exec(String(e.text ?? ''));
  const down = m ? Number(m[2].replace(/,/g, '')) < Number(m[1].replace(/,/g, '')) : /감소/.test(e.kind);
  const city = cityOf(e.text);
  return hint(e.company, [city, down ? '감원' : '채용'], [city], [city]);
}
const cityOf = (text) => ((/(?:특별시|광역시|특별자치시|특별자치도|도)\s+([가-힣]{1,4}?)[시군](?![가-힣])/.exec(String(text ?? '')) ?? [])[1]);
function factoryHint(company, kind, text) {
  const city = cityOf(text);
  if (/빠짐/.test(kind)) return hint(company, [city, '공장', '폐쇄'], [city]);
  if (/새 (공장|등록)/.test(kind)) return hint(company, [city, '공장', '신설'], [city]);
  const m = /고용 (\d+)→(\d+)/.exec(String(text ?? ''));
  if (m) return hint(company, [city, Number(m[2]) < Number(m[1]) ? '감원' : '채용'], [city], [city]);  // 사업장 지명 없는 기사는 다른 사업장일 수 있다
  return undefined;  // 업종·주생산품 문구 변경: 기사 낱말을 정할 수 없음
}
function caseHint(x) {
  const who = (x.beat ?? [])[0];
  if (x.courtId === 'cafc') return hint(who, ['항소', /Patent/i.test(`${x.appealFrom ?? ''} ${x.caseType ?? ''}`) ? '특허' : '소송']);
  if (x.courtId === 'cit') return hint(who, ['국제무역법원', '소송']);
  return hint(who, ['소송', /특허/.test(x.category ?? '') ? '특허' : null]);
}
function opinionHint(x) {
  const duty = /countervailing/i.test(x.holding ?? '') ? '상계관세' : /anti-?dumping/i.test(x.holding ?? '') ? '반덤핑' : null;
  return hint((x.beat ?? [])[0], [x.courtId === 'cit' ? '국제무역법원' : '항소', '판결', duty]);
}
function pageHint(e, added) {
  if (!/\$\s?\d/.test(added)) return undefined;  // price lines only; other wording changes have no reliable search words
  // 차종 목록 페이지는 가격 줄 근처 차명(국문으로)으로 찾는다 — 없으면 페이지 이름의 차명(아이오닉6 N 등)
  const near = Object.values(e.priceModels ?? {})[0];
  const model = (near ? usRecallModels(near)[0] : undefined) ?? (/\b([A-Z]{1,4}\d{1,2}[A-Za-z]?)\b/.exec(String(e.label ?? '')) ?? [])[1];
  return hint(e.company, [model, '가격', '미국']);
}

// DART report name as filed, without '[기재정정]' style prefixes — the review groups unsupported types by it.
const reportOf = (title) => String(title ?? '').split(' · ').pop().replace(/^\s*\[[^\]]*\]\s*/, '').trim().slice(0, 30);

function scoopKind(c) {
  if (c.filing?.type) return `DART ${c.filing.type}`;
  if (c.kind === '단서' && /dart\.fss\.or\.kr/.test(String(c.url ?? ''))) return `DART ${reportOf(c.title) || '기타'}`;
  if (c.kind === '단서') return `단서${c.source ? ` ${String(c.source).slice(0, 20)}` : ''}`;
  return c.kind ?? '기타';
}

// all=true: every stored item regardless of date (used to label judgments), same tiers as the digest.
function collect(docs, cut, cutDay, { all = false, now = Date.now() } = {}) {
  const items = [];
  const push = (tier, w, x) => items.push({ tier, watch: w.label, tool: w.tool, ...x });
  const W = Object.fromEntries(WATCHES.map((w) => [w.feed, w]));
  const fresh = (x, base, key) => all || isFresh(x, cut, cutDay, base, key);
  const recent = (at) => all || !(Date.parse(at) < cut);  // same as before: an unreadable date is not dropped

  const scoop = docs['scoop-screen'];
  for (const c of scoop?.candidates ?? []) {
    // 후보 목록은 판정 전까지 매 실행 다시 실린다 — 처음 심사한 때가 창 밖이면 새 항목이 아니다(scoop_screen에서는 계속 보임).
    if (c.firstSeen && !recent(c.firstSeen)) continue;
    const fl = c.filing;
    // one line per item: long cells (판결 주문, 당사자 목록) are clipped here; scoop_screen shows them in full
    const clip = (v) => { const t = String(v ?? '').replace(/\s+/g, ' ').trim(); return t.length > 60 ? `${t.slice(0, 60).trimEnd()}…` : t; };
    // 정정 표를 읽었으면 단서 제목의 '변경 항목 대조 필요'는 이미 답이 있다(정정: … 줄)
    const title = fl?.correction ? String(c.title ?? '').replace(/\s*—\s*변경 항목 대조 필요$/, '') : c.title;
    const brief = fl && !fl.error && (fl.facts ?? []).length ? ` · ${fl.facts.slice(0, 4).map(([k, v]) => `${k} ${clip(v)}`).join(' · ')}` : '';
    // 정정 공시는 무엇이 바뀌었는지가 먼저다(10-31 효성중공업 Statnett 정정: 계약금액 1,135.9억 → 1,130.4억, -0.5%)
    const fix = fl?.correctionShort ?? (fl?.correctionLine ? clip(fl.correctionLine) : '');
    const cmp = (fix ? ` · ${fix}` : '') + (fl && (fl.compare ?? []).length ? ` · ${fl.compare[0]}` : '');
    const kind = scoopKind(c);
    const flag = fl?.routine ? '일상' : '';
    if (c.verdict === '미보도 후보' && fl?.routine) push('B', W['scoop-screen'], { kind, flag, verdict: c.verdict, id: c.id, date: c.published ?? c.filedOn, company: c.company, fact: `${title} — 일상 공시로 보임(${fl.routine})${brief}`, url: c.url });
    // 특허 공개는 거의 기사가 안 나므로 '미보도 후보'가 늘 나온다 — 그 자체로 단독이 아니고 사업화·생산·수주 연결을 확인할 B
    // (10-31 운영: 10-07·10-12 공개특허 두 건이 A에 남아 A 3건 중 2건)
    // 국내 리콜 공지(자동차리콜센터)는 공개 공지라 그 자체로 단독이 아니다 — 미보도 후보여도 B(대상 대수·생산기간·반복 결함 확인)
    else if (c.verdict === '미보도 후보' && c.kind === '리콜') push('B', W['scoop-screen'], { kind, verdict: c.verdict, id: c.id, date: c.published ?? c.filedOn, company: c.company, fact: `${title} — 보도 대조 '미보도 후보' · 리콜 공지만으로는 단독이 아님(대상 대수·생산기간·같은 결함 반복 확인)`, url: c.url });
    else if (c.verdict === '미보도 후보' && c.kind === '특허') push('B', W['scoop-screen'], { kind, verdict: c.verdict, id: c.id, date: c.published ?? c.filedOn, company: c.company, fact: `${title} (특허) — 보도 대조 '미보도 후보' · 특허 공개만으로는 단독이 아님(사업화·생산·수주 연결 확인)`, url: c.url });
    else if (c.verdict === '미보도 후보') push('A', W['scoop-screen'], { kind, verdict: c.verdict, id: c.id, date: c.published ?? c.filedOn, company: c.company, fact: `${title} (${c.kind ?? ''}) — 보도 대조 '미보도 후보'${brief}${cmp}`, url: c.url });
    else if (c.verdict === '미확인') push('B', W['scoop-screen'], { kind, verdict: c.verdict, id: c.id, date: c.published ?? c.filedOn, company: c.company, fact: `${title} — 보도 대조 미확인(채널 실패)`, url: c.url });
    // 정정 중 큰 변경(금액 ±10%·기간 90일+·해지): '관련 보도 있음'이어도 그 기사는 원 계약 기사일 수 있다 — B로 올린다
    // (10-31 두산에너빌리티 영광 야월 해상풍력 EPC 정정: 계약기간 종료일 2029-07-01 → 2030-01-28, 보도 대조는 다른 기사)
    else if (c.verdict === '관련 보도 있음' && (fl?.correction?.material ?? []).length) push('B', W['scoop-screen'], { kind, flag: '정정', verdict: c.verdict, id: c.id, date: c.published ?? c.filedOn, company: c.company,
      fact: `${title} — 정정 중 큰 변경(${fl.correction.material.join(', ')}${fixReason(fl.correction.reason)})${brief}${cmp} · ${correctionNote(c.correctionCheck)}`, url: c.url });
    else push('C', W['scoop-screen'], { kind, id: c.id, company: c.company, fact: `${c.verdict}: ${title}` });
  }

  const kr = docs['kr-official'];
  for (const e of kr?.events ?? []) {
    if (!recent(e.detectedAt)) continue;
    const text = factoryEventText(kr, e);
    push(e.tier ?? (e.kind === '목록에서 빠짐' ? 'B' : 'A'), W['kr-official'], { kind: `공장 ${e.kind}`, id: e.id, date: e.detectedAt, company: e.company, fact: `${e.kind}: ${text}`,
      check: factoryHint(e.company, e.kind, text) });
  }
  const evFactories = all ? new Set() : new Set((kr?.events ?? []).filter((e) => Date.parse(e.detectedAt) >= cut).map((e) => e.factoryId));
  for (const f of kr?.factories ?? []) {
    if (f.registeredOn && (all || f.registeredOn >= cutDay) && !evFactories.has(f.id)) push('A', W['kr-official'], { kind: '공장 새 등록', id: f.id, date: f.registeredOn, company: f.company, fact: `공장 등록 ${f.cmpnyNm} · ${f.rnAdres} · 주생산품 ${uniqueList(f.mainProductCn) || '미기재'} · 업종 ${f.indutyNm || '미기재'} · 고용 ${f.employees ?? '?'}명${f.nameCheck ? ` (⚠ ${f.nameCheck})` : ''}`,
      check: factoryHint(f.company, '새 등록', f.rnAdres) });
  }
  // 환경영향평가: a new stage (초안·본안·변경협의) of a project whose name carries a beat company — plans before announcements.
  for (const x of kr?.eia ?? []) {
    if (!recent(x.firstSeen) && !all) continue;
    const words = String(x.name ?? '').replace(/\(주\)|㈜|주식회사/g, ' ').split(/\s+/).filter((w) => w.length >= 2 && !w.includes(String(x.company ?? '').slice(0, 2)));
    push('A', W['kr-official'], { kind: `환경영향평가 ${x.stage}`, id: x.id, date: x.received || x.firstSeen, company: x.company,
      fact: `환경영향평가(${x.kind}) ${x.stage}: ${x.name} · ${x.category} · 접수 ${x.received}${x.completed ? ` · 완료 ${x.completed}` : ''} — 계획 단계, 착공·투자 확정 아님`,
      url: x.url, check: hint(x.company, [words[0] ?? '환경영향평가', '환경영향평가']) });
  }
  const gzBase = baselineOf(kr?.gazette ?? []);
  for (const g of kr?.gazette ?? []) {
    if (fresh(g, gzBase, 'date')) push('B', W['kr-official'], { kind: '관보 입법예고', id: g.id, date: g.date, company: (g.teams ?? []).join('·'), fact: `관보 입법예고 ${g.org}: ${g.title}`, url: g.url });
  }

  const ks = docs['kr-signals'];
  const ksBase = baselineOf(ks?.decisions ?? []);
  for (const d of ks?.decisions ?? []) {
    const fd = String(d.fileDate ?? '').slice(0, 10);  // file registration = when the decision went up
    if (!(all || (fd ? fd >= cutDay : isFresh(d, cut, cutDay, ksBase, 'decidedOn')))) continue;
    const ms = d.mentions ?? [];
    const direct = ms.filter((m) => !m.related);
    const named = direct.filter((m) => m.role !== '본문 언급');
    const installment = (d.flags ?? []).some((f) => f.startsWith('과징금 납부기한'));
    const tier = direct.some((m) => m.role === '피심인') || (installment && named.length) ? 'A' : named.length ? 'B' : 'C';
    const lead = direct.find((m) => m.role === '피심인') ?? named[0] ?? ms[0];
    push(tier, W['kr-signals'], { kind: `공정위 ${lead?.role ?? '언급'}`, id: d.id, date: fd || d.decidedOn, company: [...new Set(ms.map((m) => m.company))].join('·'),
      fact: `공정위 의결서(${d.action}${(d.flags ?? []).length ? ` · ${d.flags.join('·')}` : ''}, 의결 ${d.decidedOn}): ${d.name} — ${ms.map((m) => `${m.company} ${m.role}`).join(', ')}`, url: d.url,
      check: hint(lead?.company, ['공정위', '과징금']) });
  }
  // one line per tender: lots of the same notice ('…-01(일반)', '…-02(일반)') are grouped
  const lots = new Map();
  for (const x of ks?.kepco ?? []) {
    const nd = ymd8(x.noticeDate);
    if (!(all || nd >= cutDay)) continue;
    if (!all && !x.big && !((x.price ?? 0) >= 1e9)) continue;  // small lots stay in kr_signals only
    const key = `${x.company}|${nd}|${String(x.name).replace(/-\d{1,2}(\([^)]*\))?\s*$/, '')}`;
    const g = lots.get(key);
    if (g) { g.n += 1; g.sum += x.price ?? 0; g.big = g.big || x.big; } else lots.set(key, { x, nd, n: 1, sum: x.price ?? 0, big: x.big });
  }
  for (const { x, nd, n, sum, big } of lots.values()) {
    const won = (v) => `약 ${Math.round(v / 1e8).toLocaleString('en-US')}억원`;
    push(big ? 'B' : 'C', W['kr-signals'], { kind: '한전 입찰', id: x.id, date: nd, company: x.company,
      fact: `한전 전자입찰 ${x.company} 「${x.name}」${n > 1 ? ` 외 같은 공고 ${n - 1}건(합계 ${won(sum)})` : ''} · 추정가격 ${x.price ? won(x.price) : '미기재'} · ${x.state}`,
      check: kepcoHint(x.name) });
  }
  for (const x of ks?.motir ?? []) {
    if (!(all || String(x.date ?? '') >= cutDay)) continue;
    const t = x.trade;
    const strong = (x.companies ?? []).length || /무역위|덤핑|상계|세이프가드/.test(x.title ?? '') || t;
    const tradeLine = t?.items ? ` — ${t.period} 수출${t.exports ? ` ${t.exports.value}억달러(${t.exports.yoy}%)` : ''} · ${Object.entries(t.items).slice(0, 6).map(([k, v]) => `${k} ${v.value}억달러(${v.yoy}%)`).join(' · ')}` : '';
    push(strong ? 'B' : 'C', W['kr-signals'], { kind: '산업부 발표', id: x.id, date: x.date, company: (x.companies ?? []).join('·') || x.dept,
      fact: `산업통상부 ${x.kind}: ${x.title}${x.embargo ? ` (엠바고: ${x.embargo})` : ''}${tradeLine}`, url: x.url });
  }
  for (const e of ks?.events ?? []) {
    if (!recent(e.detectedAt)) continue;
    const tier = e.kind === '원자재 가격' ? (/최고|최저/.test(e.signal ?? '') ? 'B' : 'C') : 'B';
    push(tier, W['kr-signals'], { kind: e.kind === '원자재 가격' ? `원자재 ${e.signal}` : e.kind, id: e.id, date: e.detectedAt, company: e.company, fact: `${e.kind}: ${e.text}` });
  }

  for (const e of docs['kr-stats']?.events ?? []) {
    if (!recent(e.detectedAt)) continue;
    if (e.kind === '모델별 판매') {  // 현대차·기아 IR 엑셀: 끊김·공장 멈춤 A, 급감·급증·첫 판매·세대 교체 B(이유는 회사 확인)
      push(['A', 'B'].includes(e.tier) ? e.tier : 'C', W['kr-stats'], { kind: `판매 ${e.signal}`, id: e.id, date: e.detectedAt, company: e.company,
        fact: `모델별 판매: ${e.text}`, url: e.url, check: hint(e.company, [e.keyword ?? '판매', /급증|첫/.test(e.signal ?? '') ? '판매' : '감산']) });
      continue;
    }
    const record = /최고|최저/.test(e.signal ?? '');
    const tier = e.kind === '수입차 등록' ? (e.top ? 'B' : 'C') : record ? 'B' : 'C';
    push(tier, W['kr-stats'], { kind: `${e.kind === '수입차 등록' ? '수입차' : '통계'} ${e.signal}`, id: e.id, date: e.detectedAt, company: e.company, fact: `${e.kind}: ${e.text}` });
  }

  const tr = docs['trade-remedy'];
  for (const e of tr?.events ?? []) {
    if (!recent(e.detectedAt) || e.renumbered) continue;  // 목록 일련번호만 밀린 재감지(수집기 표시)
    if (e.pageId === 'ktc') {
      // 국내 무역위원회: 공식 변화(B)는 출입 업종 품목만. 보도자료는 이미 공개된 뉴스(C). 회사 이름은 누리집에 대개 없다.
      push(e.tier === 'B' ? 'B' : 'C', W['trade-remedy'], { kind: KTC_KIND[e.ktcKind] ?? '무역위원회', id: e.id, date: e.detectedAt,
        company: e.product ?? '', fact: `${e.label}: ${e.text}`, url: e.url,
        check: e.ktcKind === 'news' ? undefined : '품목의 국내 생산자(신청인)를 협회·회사에 확인 → 판정·세율은 회의 뒤 의결서·보도자료로' });
      continue;
    }
    if (e.pageId === 'kita') {
      // 무역협회 대한 수입규제DB: 출입처 업체가 최신 단계(마진)에 나오면 A(새 사건)·B(진행), 출입 업종 품목 B·C, 미국은 관보 감시가 먼저라 한 단계 낮춤(수집기에서).
      const firms = e.companies ?? [];
      push(['A', 'B'].includes(e.tier) ? e.tier : 'C', W['trade-remedy'], { kind: e.kitaKind ?? '대한 수입규제', id: e.id, date: e.detectedAt,
        company: firms.join('·') || e.country, fact: `${e.kitaKind ?? '대한 수입규제'}(무역협회 DB): ${e.text}`, url: e.url,
        check: firms.length ? hint(firms[0], [e.country, '관세'], [e.country]) : undefined });
      continue;
    }
    // repeats: 같은 줄이 목록 일련번호만 바뀌어 다시 잡힌 적 있음 → 이 첫 감지도 번호 이동일 수 있어 C(원문 개시일 확인)
    push(e.repeats ? 'C' : e.pageId === 'taric' && /한국 전용/.test(e.label) ? 'A' : 'B', W['trade-remedy'], { kind: e.pageId === 'taric' ? 'EU 쿼터(TARIC)' : `해외 조사 ${e.pageId}`, id: e.id, date: e.detectedAt, company: e.country,
      fact: `${e.label}: ${e.text}${e.repeats ? ` — 목록 일련번호만 바뀌어 ${e.repeats}번 다시 잡힌 줄이라 이 감지도 번호 이동일 수 있음(원문 개시일 확인)` : ''}`, url: e.url });
  }
  const frBase = baselineOf(tr?.federalRegister ?? []);
  for (const x of tr?.federalRegister ?? []) {
    if (!fresh(x, frBase, 'date')) continue;
    const names = (x.named ?? []).map((n) => n.company);
    // An unusual topic in the decision-memo appendix of a notice naming a beat company is the story (10-09 열연 'Workplace Nursery' → 10-23 [단독]).
    const odd = names.length ? (x.memoUnusual ?? []) : [];
    const memo = odd.length ? ` · 결정문 목차에 흔치 않은 항목(관보 부록 원문): "${String(odd[0]).slice(0, 160)}"${odd.length > 1 ? ` 외 ${odd.length - 1}` : ''}`
      : (x.memoNamed ?? []).length ? ` · 결정문 목차에 출입처: "${String(x.memoNamed[0]).slice(0, 120)}"` : '';
    push(odd.length ? 'A' : names.length ? 'B' : 'C', W['trade-remedy'], { kind: odd.length ? '미국 관보 결정문 목차' : '미국 관보', id: x.id, date: x.date, company: names.join('·'),
      fact: `미국 관보 ${x.stage}: ${x.title}${names.length ? ` — 본문에 ${names.join('·')}` : ''}${memo}`, url: x.url,
      check: hint(names[0], ['관세', odd.length ? '보조금' : '판정']) });
  }

  const lit = docs['us-litigation'];
  const litBase = baselineOf(lit?.cases ?? []);
  for (const x of lit?.cases ?? []) {
    if (!fresh(x, litBase, 'dateFiled')) continue;
    const tier = x.priority <= 1 ? 'A' : x.priority === 2 ? 'B' : 'C';
    const what = x.summary ? `${x.summary} 「${x.caseName}」` : `${x.category} · ${x.role}: ${x.court ?? x.courtId} 「${x.caseName}」 접수`;
    push(tier, W['us-litigation'], { kind: x.category ?? '소송', id: x.id, date: x.dateFiled, company: (x.beat ?? []).join('·'), fact: what, url: x.url, check: caseHint(x) });
  }
  // Rulings of the trade court / Federal Circuit in a beat party's case are the news itself (POSCO CIT 10-27 → [단독] 10-28).
  const opBase = baselineOf(lit?.opinions ?? []);
  for (const x of lit?.opinions ?? []) {
    if (!fresh(x, opBase, 'dateFiled')) continue;
    const h = x.holding ? ` — 요지(원문) "${x.holding.length > 140 ? `${x.holding.slice(0, 140).trimEnd()}…` : x.holding}"${x.holdingKo ? ` (풀이: ${x.holdingKo})` : ''}` : ' — 요지 미추출(판결문 확인)';
    push('A', W['us-litigation'], { kind: '미국 법원 판결', id: x.id, date: x.dateFiled, company: (x.beat ?? []).join('·'),
      fact: `${x.courtId === 'cit' ? '국제무역법원' : '연방순회항소법원'} 판결 「${x.caseName}」(${(x.beat ?? []).join('·')} ${x.role})${h}${x.reading ? ` · ${x.reading}` : ''}`, url: x.url,
      check: opinionHint(x) });
  }
  const itcBase = baselineOf(lit?.itc ?? []);
  for (const x of lit?.itc ?? []) {
    if (fresh(x, itcBase, 'date')) push('A', W['us-litigation'], { kind: 'ITC 337조', id: x.id, date: x.date, company: (x.named ?? []).map((n) => n.company).join('·'), fact: `ITC 337조 ${x.stage}: ${x.title}`, url: x.url,
      check: hint((x.named ?? [])[0]?.company, ['ITC', '특허침해']) });
  }

  // US recalls (NHTSA full file): Korean brands, GM Korea models, Korean tires and Korean supplier names are direct (A from 1,000 cars);
  // imports alone are B from 10,000 cars, smaller ones C. Park-outside / do-not-drive advisories keep the higher tier.
  const ur = docs['us-recalls'];
  const urBase = baselineOf(ur?.recalls ?? []);
  for (const x of ur?.recalls ?? []) {
    if (!fresh(x, urBase, 'received')) continue;
    const why = x.why ?? [];
    const direct = why.some((w) => ['현대차', '기아', '한국GM'].includes(w.beat) || w.role === '타이어 제조사' || String(w.role).startsWith('부품'));
    const lead = why.find((w) => String(w.role).startsWith('부품')) ?? why[0] ?? {};
    const brand = why.find((w) => String(w.role).startsWith('제조사'))?.name;
    const roles = why.map((w) => `${w.name}(${w.role})`).join('·');
    // 대상 대수: 출입처 직접 리콜도 1,000대 미만은 B, 수입 브랜드만 걸린 리콜은 1만 대 미만이면 참고(C) — 실외 주차·운행 중지 권고는 그대로 올린다
    // (10-31 운영: 현대차 24대·17대 리콜이 A, BMW 45대 리콜이 B '관련 보도 있음'(다른 BMW 리콜 기사)으로 떴다).
    const n = Number(x.affected ?? 0);
    const urgent = x.parkOutside || x.doNotDrive;
    const tier = direct ? (n >= 1000 || urgent ? 'A' : 'B') : (n >= 10000 || urgent ? 'B' : 'C');
    push(tier, W['us-recalls'], { kind: 'NHTSA 리콜', id: x.id, date: x.received, company: [...new Set(why.map((w) => w.name))].join('·'),
      fact: `미국 리콜 ${x.campaign} 접수 ${x.received} · ${x.models} · ${x.component} · 대상 ${Number(x.affected ?? 0).toLocaleString('en-US')}대${x.parkOutside ? ' · 실외 주차 권고' : ''} — ${roles}${x.supplierBox ? ` · 원보고서 공급사 칸: ${String(x.supplierBox).slice(0, 80)}` : ''}`,
      url: x.url, check: tier === 'C' ? undefined : usRecallHint(x, why) });
  }
  // NHTSA defect investigations (ODI) on beat cars or naming a Korean supplier: opened on 현대·기아·한국GM 차종 A, closed B.
  const invBase = baselineOf(ur?.investigations ?? []);
  for (const x of ur?.investigations ?? []) {
    if (!fresh(x, invBase, x.closed ? 'closed' : 'opened') && !(x.changedAt && recent(x.changedAt))) continue;
    const who = [...new Set((x.why ?? []).map((w) => w.name))].join('·');
    push(x.tier ?? 'B', W['us-recalls'], { kind: `NHTSA 결함조사 ${x.kind}`, id: x.id, date: x.closed ?? x.opened, company: who,
      fact: `미국 NHTSA ${x.type} ${x.action} ${x.kind} · ${x.models} · ${x.component} · 「${x.subject}」 · 개시 ${x.opened}${x.closed ? ` · 종결 ${x.closed}` : ''}${(x.recallCampaigns ?? []).length ? ` · 연결 리콜 ${x.recallCampaigns.join(',')}` : ''} — 조사 개시는 결함 확정 아님`,
      url: x.url, check: x.tier === 'C' ? undefined : hint((x.why ?? [])[0]?.name, ['미국', '조사']) });
  }

  // US EPA certification file: a model new to the company is A, an EV range change B, model-year carryover C.
  for (const v of docs['us-epa']?.vehicles ?? []) {
    if (!recent(v.firstSeen) && !(all || String(v.created ?? '') >= cutDay)) continue;  // first seen in the window, or registered in it
    const tier = v.kind === '새 모델' ? 'A' : v.kind === '주행거리 변화' ? 'B' : 'C';
    const range = v.range ? ` · EPA 주행거리 ${v.range}마일` : '';
    const cmp = v.compare ? ` (직전 ${v.compare.previousYear}년형 ${v.compare.previousRanges.join('/')}마일)` : '';
    push(tier, W['us-epa'], { kind: `EPA ${v.kind}`, id: v.id, date: v.created ?? v.firstSeen, company: v.company,
      fact: `미국 EPA 등록(${v.kind}): ${v.year} ${v.make} ${v.model}${v.atvType ? ` · ${v.atvType}` : ''}${range}${cmp}${v.comb ? ` · 복합 ${v.comb}${v.atvType === 'EV' ? 'MPGe' : 'mpg'}` : ''} · 등록 ${v.created ?? '?'}`,
      url: v.url, check: tier === 'C' ? undefined : hint(v.company, [String(v.baseModel ?? '').split(' ')[0], 'EPA']) });
  }

  // NHTSA vPIC: a model name new to Hyundai/Kia/Genesis (VIN decoding registered before launch) is A.
  for (const v of docs['us-epa']?.vpicModels ?? []) {
    if (!recent(v.firstSeen) && !all) continue;
    push('A', W['us-epa'], { kind: 'VIN 모델명 등록', id: v.id, date: v.firstSeen, company: v.company,
      fact: `미국 NHTSA에 새 모델명 등록(VIN 해독): ${v.make} '${v.model}' · ${(v.years ?? []).join('·')}년형 — 출시·국내 도입은 미확인`,
      url: v.url, check: hint(v.company, [String(v.model ?? ''), '미국']) });
  }

  // Korean fuel-economy filings (에너지공단 표시연비): a model name new to the maker is A, an EV range change B, other rows C.
  // A bulk reload of the list (many rows at once) is reference only.
  for (const v of docs['kr-fuel']?.vehicles ?? []) {
    if (!recent(v.firstSeen) && !(all || String(v.registered ?? '') >= cutDay)) continue;
    const tier = v.bulk ? 'C' : v.kind === '새 모델명' ? 'A' : v.kind === '주행거리 변화' ? 'B' : 'C';
    const eff = v.eff ? ` · 표시연비 ${v.eff}${/전기/.test(v.fuel ?? '') ? 'km/kWh' : 'km/L'}` : '';
    const range = v.range ? ` · 1회 충전 ${v.range}km` : '';
    const cmp = v.compare ? ` (같은 모델명 이전 ${v.compare.previousRanges.join('/')}km)` : '';
    push(tier, W['kr-fuel'], { kind: `연비 신고 ${v.kind}`, id: v.id, date: v.registered ?? v.firstSeen, company: v.company,
      fact: `국내 연비 신고(${v.kind}${v.bulk ? ', 일괄 갱신' : ''}): ${v.maker} ${v.model} · ${v.year}년 · ${v.fuel}${v.displacement ? ` ${v.displacement}cc` : ''}${eff}${range}${cmp} · 등록 ${v.registered ?? '?'}`,
      url: v.url, check: tier === 'C' ? undefined : hint(v.company, [String(v.model ?? '').split(/\s+/)[0], '연비']) });
  }

  const pf = docs['partner-filings'];
  const pfBase = baselineOf(pf?.items ?? []);
  for (const x of pf?.items ?? []) {
    if (!fresh(x, pfBase, 'date')) continue;
    let tier;
    if (x.routine) tier = 'C';
    else if (x.source === 'ASX' || x.source === 'HKEX') tier = (x.flags ?? []).length ? 'A' : 'C';
    // dealNear(수집기): 계약 낱말이 출입처 이름과 같은 문장에 있나. 예전 저장분은 발췌 전체로 본다.
    // 보도 인용 문장에만 이름이 나온 것은 그 회사 공시가 아니라 기사 인용이다 — 참고(10-31: 넥사 6-K의 '고려아연·텍 벤치마크 TC' 인용)
    else if (x.hearsay || x.boilerplate) tier = 'C';  // 전망·위험 고지 문구 속 언급도 참고(10-31: Cleveland-Cliffs 8-K의 'MOU with POSCO' 위험 요인)
    else tier = (x.dealNear ?? DEAL_WORDS.test(String(x.snippet ?? ''))) && !x.finNote ? 'A' : 'B';
    const deal = x.routine ? ` — ${x.routine}` : x.source === 'ASX' || x.source === 'HKEX' ? '' : x.hearsay ? ` — ${x.hearsay}` : x.boilerplate ? ` — ${x.boilerplate}` : x.finNote ? ` — ${x.finNote}`
      : tier === 'B' && x.dealNear === false && DEAL_WORDS.test(String(x.snippet ?? '')) ? ' — 계약·공급 낱말이 출입처 이름과 다른 문장에 있음(업계 일반 서술일 수 있음)'
      // 소송·특허 서술은 '계약 낱말 없음'이 아니라 절차 서술이다 — 단계(청원·답변 기한·철회)는 원문으로(10-31: FSLR 10-Q의 USITC 청원 문단)
      : tier === 'B' && LITIGATION.test(String(x.snippet ?? '')) ? ' — 소송·특허 절차 서술(진행 단계·당사자는 원문 확인)'
      : tier === 'B' ? ' — 발췌에 계약·공급·합작 낱말 없음(이름만 언급일 수 있음)' : '';
    const ticker = (/\(([A-Z0-9]{1,5})(?:,[^)]*)?\)\s*$/.exec(String(x.filer ?? '')) ?? [])[1];
    const partner = x.source === 'EDGAR' ? EDGAR_KO[ticker] : ASX_KO[ticker] ?? String(x.filer ?? '').split(/[\s,(]/)[0];
    const word = x.source === 'HKEX' ? '합작' : LITIGATION.test(String(x.snippet ?? '')) ? '특허' : '계약';
    const when = x.source === 'HKEX' && x.time ? ` ${x.time} 홍콩시각` : '';
    push(tier, W['partner-filings'], { kind: x.source ?? '공시', id: x.id, date: x.date, company: (x.beat ?? []).join('·'), fact: `${x.source} ${x.filer}${when}: ${x.title}${(x.flags ?? []).length ? ` (낱말 ${x.flags.join(',')})` : ''}${deal}`, url: x.url,
      // 공시 회사 이름이 기사에 있어야 같은 건(10-31: '한화솔루션 퍼스트솔라 특허'가 「한화솔루션, ESS·태양전지 특허 폭증」으로 '관련 보도 있음')
      check: partner ? hint((x.beat ?? [])[0], [partner, word], [], [partner]) : undefined });
  }

  // Overseas public-buyer award notices (EU TED·영국 FTS·세계은행·바레인 월간 보고서·대만 PCC): a beat company in the winner field is A;
  // contract modifications and Bahrain report lines B; other Korean winners C. TED notices trail the contract by weeks.
  // 바레인 개찰(응찰가 공개): a beat company's lowest bid on a big tender is A, its other bids B — never an award.
  const oa = docs['overseas-awards'];
  const oaBase = baselineOf(oa?.items ?? []);
  // A source added later (바레인 개찰) marks its own first run as baseline: those rows count only by their own date.
  for (const x of oa?.items ?? []) {
    if (!fresh(x, x.baseline ? Date.parse(x.firstSeen) : oaBase, 'published')) continue;
    const tier = x.tier ?? (x.company ? 'A' : 'C');
    const money = (v) => `${x.currency ?? ''} ${Number(v).toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
    const value = x.value ? ` · ${money(x.value)}` : ' · 금액 미기재';
    const where = countryKo(x.buyerCountry);
    if (x.bidder) {  // 개찰(응찰가 공개) — 낙찰 아님
      const rank = x.rank ? `응찰가 ${x.rank}위/${x.priced}곳${x.lowest ? '(최저가)' : x.lowestBid ? ` · 최저 ${x.lowestBid.name} ${money(x.lowestBid.value)}` : ''}` : '응찰가 순위 없음(가격 미공개·탈락)';
      push(tier, W['overseas-awards'], { kind: `${x.source} ${x.kind}`, id: x.id, date: x.published ?? x.firstSeen, company: x.company ?? '',
        fact: `해외 개찰(${x.source}): ${where ? `${where} ` : ''}${x.buyer} · ${String(x.title ?? '').slice(0, 120)} — ${x.bidder}${x.value ? ` ${money(x.value)}` : ' 응찰가 미공개'} · ${rank} · 개찰 ${x.published ?? '?'} · 낙찰 아님`,
        url: x.url, check: tier === 'C' ? undefined : hint(x.company, [where, '입찰'], [where]) });
      continue;
    }
    const more = (x.winnerCount ?? (x.winners ?? []).length) - Math.min(2, (x.winners ?? []).length);
    const who = ((x.winners ?? []).slice(0, 2).join('·') + (more > 0 ? ` 외 ${more}곳` : '')) || '보고서 줄 참조';
    push(tier, W['overseas-awards'], { kind: `${x.source} ${x.kind}`, id: x.id, date: x.published ?? x.firstSeen, company: x.company ?? '',
      fact: `해외 ${x.kind}(${x.source}): ${where ? `${where} ` : ''}${x.buyer} ← ${who} · ${String(x.title ?? '').slice(0, 120)}${value}${x.concluded ? ` · 계약 ${x.concluded}` : ''} · 공고 ${x.published ?? '?'}`,
      url: x.url, check: tier === 'C' ? undefined : hint(x.company, [where, '수주'], [where]) });
  }

  // Court insolvency notices (대법원 회생·파산 공고, 회생회사 M&A 공고): a beat-industry manufacturer (공장등록 업종) entering
  // proceedings is A, a related industry with a beat product word or a 폐지 B, other related industries and name words only C. A court notice is a procedure, not a supply effect.
  const ins = docs['kr-insolvency'];
  const insBase = baselineOf(ins?.events ?? []);
  for (const e of ins?.events ?? []) {
    if (!fresh(e, insBase, 'posted')) continue;
    push(e.tier ?? 'C', W['kr-insolvency'], { kind: e.kind, id: e.id, date: e.posted ?? e.firstSeen, company: e.company,
      fact: `${e.kind}: ${insolvencyLine(e)} · 공고 ${e.posted ?? '?'} — 거래 관계·납품 영향 미확인`, url: e.url ?? e.listUrl,
      check: e.tier === 'C' ? undefined : hint(firmName(e.company), ['회생']) });
  }

  // 전기위원회 발전사업 허가(회차 개최결과·허가대장)·원안위 안건: 출입처 그룹 사업명·원전 건설/운영허가·SMR A, 해상풍력 허가·계속운전 B.
  // 원안위 안건은 의결 결과가 새로 붙을 때 다시 올린다.
  const en = docs['kr-energy'];
  const enBase = baselineOf(en?.items ?? []);
  for (const x of en?.items ?? []) {
    if (!fresh(x, enBase, 'posted') && !(x.resultSeen && recent(x.resultSeen))) continue;
    const nssc = x.source === '원자력안전위원회';
    const res = x.result ? ` → ${x.result}` : nssc ? ' (상정 — 의결 결과 전)' : '';
    const who = x.company || String(x.title ?? '').replace(/\(안\)|발전사업/g, '').split(/\s+/).slice(0, 3).join(' ');
    push(x.tier ?? 'C', W['kr-energy'], { kind: `${x.source} ${x.kind}`, id: x.id, date: x.held ?? x.posted ?? x.firstSeen, company: x.company ?? '',
      fact: `${x.source}${x.meeting && !nssc ? ` ${x.meeting}` : ''} ${x.kind}: ${String(x.title ?? '').slice(0, 140)}${res}${x.held ? ` · ${nssc ? '회의' : '회의·허가일'} ${x.held}` : ''}`,
      url: x.url, check: x.tier === 'C' ? undefined : hint(who, [nssc ? '원안위' : '허가']) });
  }

  // 출입처 공장과 같은 번지의 건축인허가(건축주 비공개): 신축 1,000㎡ 이상 A, 증축·사용승인(준공)·그 밖 B, 300㎡ 미만 C.
  const bd = docs['kr-building'];
  const bdBase = baselineOf(bd?.permits ?? []);
  for (const x of bd?.permits ?? []) {
    // a lot looked at for the first time after the first run (new plant, a lot left over, more pages) is its own baseline
    if (x.orphan) continue;  // its plant left the plant list
    if (x.baseline && !(x.changedAt && recent(x.changedAt))) continue;
    if (!fresh(x, bdBase, 'permitted') && !(x.changedAt && recent(x.changedAt))) continue;
    push(x.tier ?? 'C', W['kr-building'], { kind: `건축 ${x.kind}`, id: x.id, date: x.changedAt ? String(x.changedAt).slice(0, 10) : x.permitted ?? x.firstSeen, company: x.company,
      fact: `${buildingLine(x)} — 건축주 미표기(${x.sameLot === false ? `공장과 본번만 같은 다른 필지${x.bldNm ? `, 건물명 '${x.bldNm}'` : ''}` : '공장과 같은 번지'})`,
      check: x.tier === 'C' ? undefined : hint(x.company, [cityOf(x.plot), '공장', x.archGbCdNm === '신축' ? '신설' : '증설'], [cityOf(x.plot)]) });
  }

  // 출입처 공장이 있는 시·군의 고시·공고(새올): 출입처 이름+사업 낱말 A, 이름만 B, 제철소·산업단지 계획 등 C. 시·군별 첫 조회는 기준선.
  for (const x of docs['kr-local']?.items ?? []) {
    if (x.baseline || !recent(x.firstSeen)) continue;
    // 상세 페이지를 읽었으면 전체 제목·본문 앞부분(목록 제목은 '...'로 잘린다 — 10-31 울주 '#2ASU O...' → 'O2 COMPRESSOR ROOM 토건공사')
    const d = x.detail;
    const title = d?.title ?? x.title;
    const body = d?.body ? ` · 본문: ${String(d.body).slice(0, 140)}${String(d.body).length > 140 ? '…' : ''}` : '';
    const scope = d ? '제목·본문 앞부분 확인(첨부 원문·규모는 지자체·회사 확인)' : '제목만 확인(첨부 원문·규모는 지자체·회사 확인)';
    push(x.tier ?? 'C', W['kr-local'], { kind: '지자체 고시·공고', id: x.id, date: x.date ?? String(x.firstSeen).slice(0, 10), company: x.company ?? x.city,
      fact: `${x.city} ${x.no ?? ''} 「${title}」 · ${x.dept ?? '담당 부서 미기재'} · 등록 ${x.date ?? '?'}${body} — ${scope}`,
      url: x.url, check: x.tier === 'C' || !x.company ? undefined
        : hint(x.company, [String(x.city).replace(/(시|군|구)$/, ''), localWord(title), '공장'], [String(x.city).replace(/(시|군|구)$/, '')]) });
  }

  // 국민연금 사업장(월 자료): 자사 사업장 가입자 급감·탈퇴·새 사업장·투자 낱말 공사 현장 A, 급증·변동·목록에서 빠짐·공사 현장 묶음 B.
  for (const e of docs['kr-workforce']?.events ?? []) {
    if (!recent(e.detectedAt)) continue;
    // 늘어난 '인력 변동'(지난달 대비 +max(15명, 1.5%) 이상, 급증 기준 max(30명, 3%) 미만)은 참고 — 공채 입사 같은 달마다의 출렁임이다
    // (10-31 운영: 한화솔루션 울산1 +15명·기아 본사 +112명(+1.7%)·현대위아 창원 +50명이 B '미보도 후보'로 떴다). 줄어든 변동은 B 그대로.
    const grew = /\(\+[\d,]+명/.test(String(e.text ?? ''));
    const tier = e.kind === '인력 변동' && grew ? 'C' : e.tier ?? 'B';
    push(tier, W['kr-workforce'], { kind: e.kind, id: e.id, date: e.detectedAt, company: e.company, fact: e.text,
      check: tier === 'C' ? undefined : workforceHint(e) });
  }

  // 굴뚝 자동측정(TMS): 사업장 가동 중단 신호·(14일 넘게 지켜본 뒤의) 새 배출구·새 사업장 A, 배출구 멈춤·목록에서 빠짐·재가동 B. 측정값만으로는 정지·정비·점검을 가르지 못한다.
  for (const e of docs['kr-stacks']?.events ?? []) {
    if (!recent(e.detectedAt)) continue;
    push(e.tier ?? 'B', W['kr-stacks'], { kind: e.kind, id: e.id, date: e.detectedAt, company: e.company, fact: e.text,
      check: stackHint(e) });
  }

  // 영국 Companies House 새 법인: 출입처 본사가 지배 주주(PSC)로 적히면 A, 지배 주주 미기재·본사 전체 이름이면 B, 이름만 같으면 C.
  const rg = docs['overseas-registry'];
  const rgBase = baselineOf(rg?.companies ?? []);
  for (const x of rg?.companies ?? []) {
    if (!fresh(x, rgBase, 'created')) continue;
    push(x.tier ?? 'C', W['overseas-registry'], { kind: '영국 법인 설립', id: x.id, date: x.created ?? x.firstSeen, company: x.company,
      fact: `영국 법인 설립 등기: ${x.name}(${x.number}) · 설립 ${x.created ?? '?'} · SIC ${(x.sic ?? []).join(',') || '미기재'}${(x.psc ?? []).length ? ` · 지배 주주 ${x.psc.slice(0, 2).join(', ')}` : ' · 지배 주주 미기재'}${x.pscMatch ? '' : x.tier === 'B' ? ' — 지배 주주 아직 미기재, 이름이 본사 전체 이름(본사 법인인지 확인)' : ' — 출입처 본사 지배 주주 아님(이름만 같음)'}`,
      url: x.url, check: x.tier === 'C' ? undefined : hint(x.company, ['영국', '법인'], ['영국']) });
  }

  const uc = docs['us-comments'];
  const ucBase = baselineOf(uc?.items ?? []);
  for (const x of uc?.items ?? []) {
    if (fresh(x, ucBase, 'postedDate')) push('B', W['us-comments'], { kind: `의견서${x.agency ? ` ${x.agency}` : ''}`, id: x.id, date: x.postedDate, company: x.company, fact: `${x.submitter} → ${x.agency} 의견서${x.docketTitle ? ` 「${x.docketTitle}」` : ''}`, url: x.url,
      check: hint(x.company, ['의견서', '미국']) });
  }

  // Weekly feed: a new filing stays on the digest for 7 days from first sighting (or until judged).
  for (const f of docs.trademarks?.filings ?? []) {
    if (!f.isNew) continue;
    const at = f.addedClassesAt ?? f.firstSeen;
    if (!all && !(Date.parse(at) >= Math.min(cut, now - 7 * 86400000))) continue;
    const classes = (f.classes ?? []).map(classLabel).join(', ');
    push(f.tier === 'B' ? 'B' : 'C', W.trademarks, { kind: f.titleNew ? '상표 새 이름' : '상표 출원', id: f.id, date: f.applicationDate, company: f.company,
      fact: `상표 출원 「${f.title}」 ${classes}${f.addedClassesAt ? ' — 같은 이름 상품류 추가' : ''}${f.titleNew ? ' — 감시 시작 이후 처음 보는 이름' : ''} (출원 ${f.applicationDate}, 출원번호 ${(f.applicationNumbers ?? [])[0] ?? '?'}${(f.applicationNumbers ?? []).length > 1 ? ` 외 ${f.applicationNumbers.length - 1}` : ''})`,
      check: hint(f.company, ['상표', f.title]) });
  }

  const ab = docs['assembly-bills'];
  for (const g of groupBillEvents(ab, { all: true })) {
    if (!recent(g.detectedAt)) continue;
    // 소관위 회부는 발의 며칠 뒤 모든 법안이 거치는 절차라 참고(C) — 발의 줄이 이미 B로 떠 있다(10-31: 대외무역법·산업기술보호법이 발의·회부로 두 번씩 B).
    // 보도 대조는 대표발의 의원 이름이 기사에 있어야 같은 법안으로 친다(같은 주에 같은 법 개정안이 여럿 나온다).
    const tier = g.core && g.kind !== '소관위 회부' ? 'B' : 'C';
    push(tier, W['assembly-bills'], { kind: g.kind === '발의' ? '법안 발의' : `법안 ${g.kind}`, id: g.id, date: g.date,
      company: g.core ?? '', fact: billLine(g), url: g.urls[0], check: tier === 'B' ? billHint(g) : undefined });
  }

  const pw = docs['page-watch'];
  for (const e of pw?.events ?? []) {
    if (!recent(e.detectedAt)) continue;
    // 가격 줄에는 페이지에서 그 앞 차명(배치로 추정)을 붙인다(10-31: 현대차 미국 차종 목록 가격만 바뀌어 어느 차인지 몰랐다)
    const added = Object.entries(e.added ?? {}).flatMap(([cat, list]) => list.map((x) => (cat === 'price' && e.priceModels?.[String(x).toLowerCase()]
      ? `${x}(근처 차명 ${e.priceModels[String(x).toLowerCase()]})` : x))).slice(0, 3).join(' / ');
    // 다른 주소로 넘어가던 페이지의 예전 '변경'은 넘어간 곳의 문구(10-31: kia.com/us/en/ev4 → 기아 미국 홈페이지) — C
    const tier = e.redirectNote ? 'C' : e.scope === 'page' ? 'A' : 'C';
    const what = e.kind === 'moved' ? ` 페이지 넘어감 → ${e.movedTo}(차종 페이지 내림·판매 중단·개편 가능성)`
      : e.kind === 'opened' ? ` 페이지 열림(전에는 ${e.openedFrom}(으)로 넘어가던 주소 — 출시 준비 신호일 수 있음)${added ? `: ${added}` : ''}`
      : ` 문구 변화${added ? `: + ${added}` : ''}${e.redirectNote ? ` — ${e.redirectNote}` : ''}`;
    push(tier, W['page-watch'], { kind: e.scope === 'site' ? '사이트 공통 문구' : e.kind === 'moved' ? '페이지 넘어감' : e.kind === 'opened' ? '페이지 열림' : '페이지 문구',
      id: `${e.pageId}:${e.detectedAt}`, date: e.detectedAt, company: e.company, fact: `${e.label ?? e.pageId}${e.scope === 'site' ? ' [사이트 공통]' : ''}${what}`, url: e.url,
      check: e.scope === 'page' && tier === 'A' && !e.kind ? pageHint(e, added) : undefined });
  }
  return items;
}

// Bearer-only list for radar_press_check.py: A/B items that carry a press-check hint, minus ones the reporter closed.
const PRESS_SKIP = new Set(['킬', '씀', '봤음']);
export async function radarItems(request, env, deps = {}) {
  const m = /^Bearer\s+([A-Za-z0-9_-]{16,128})$/.exec(request.headers.get('Authorization') ?? '');
  if (!m || !(await safeEqual(m[1], env?.MCP_ACCESS_TOKEN))) return new Response('Not found', { status: 404 });
  if (request.method !== 'GET') return new Response('Method not allowed', { status: 405, headers: { Allow: 'GET' } });
  const ctx = { env, now: deps.now ?? new Date() };
  const nowMs = ctx.now.getTime();
  const hours = clampInt(new URL(request.url).searchParams.get('hours'), 1, 168, 72);
  const cut = nowMs - hours * 3600000;
  const docs = Object.fromEntries(await Promise.all(WATCHES.map(async (w) => [w.feed, await readFeed(ctx, w.feed)])));
  const { rows: fb } = await storeOp(ctx, 'feedback.latest', {});
  const judged = new Map(fb.map((r) => [r.item_id, r.verdict]));
  const items = collect(docs, cut, kstDate(cut), { now: nowMs })
    .filter((x) => (x.tier === 'A' || x.tier === 'B') && x.check && !PRESS_SKIP.has(judged.get(x.id)))
    .map(({ tier, watch, id, date, company, fact, url, check }) => ({ tier, watch, id: String(id), date, company, fact: String(fact ?? '').slice(0, 300), url, check }));
  return Response.json({ generatedAt: ctx.now.toISOString(), hours, items }, { headers: { 'Cache-Control': 'no-store' } });
}

const PRESS_RANK = { '미보도 후보': 0, 미확인: 1, '관련 보도 있음': 2, '같은 수치 선행': 2 };
function pressLines(r, stamp) {
  if (!r) return [];
  const failed = Object.entries(r.channels ?? {}).filter(([, v]) => v.status !== 'ok').map(([k, v]) => `${k} ${v.status}${v.error ? `(${v.error})` : ''}`);
  const qs = (r.queries ?? []).map((q) => `"${q}"`).join(', ');
  const tail = r.verdict === '미보도 후보' ? ` — ${qs}로 ${r.since} 이후 관련 기사 못 찾음(검색 범위 결과, 단독 판정 아님)`
    : r.verdict === '미확인' ? ` — ${failed.length ? `채널 ${failed.join(', ')}` : '기사 날짜 오류 또는 사건 식별 불가'}(0건 아님)` : ` — ${qs}`;
  const was = r.firstVerdict && r.firstVerdict !== r.verdict ? ` · 처음(${kstStamp(r.firstCheckedAt)}) ${r.firstVerdict}` : '';
  // 판정에 안 세는 앞선 기사(항목 날짜 전, 제목에 회사·사건 낱말)는 미보도 후보에 한 줄 맥락으로(10-31 울주 산소공장 안전점검 공고 ↔ 10-20 증설 기사)
  const ev = r.evidence ?? [];
  const shown = [...ev.filter((e) => !e.before).slice(0, 2), ...ev.filter((e) => e.before).slice(0, 1)];
  return [`   보도 대조(자동 ${stamp}): ${r.verdict}${tail}${was}`,
    ...shown.map((e) => `     ↳ ${e.date ?? '날짜?'} [${e.channel}] ${e.title}${e.url ? ` ${e.url}` : ''}${evidenceNote(e, r.verdict)}`)];
}
// 근거 줄 꼬리표. 미보도 후보에 붙은 근거는 모두 판정에 안 센 약한 근거다 — 꼬리표가 없으면 뒷받침 기사로 읽힌다
// (10-31 운영: 퍼스트솔라 10-Q 항목에 「한화솔루션, ESS·태양전지 특허 폭증」이 꼬리표 없이 붙었다 — 퍼스트솔라 없음).
function evidenceNote(e, verdict) {
  const why = String(e.why ?? '');
  if (e.before) return ' (앞선 기사: 항목 날짜 전이라 판정에 안 셈 — 같은 사업의 앞선 보도일 수 있음)';
  if (/^본문에만/.test(why)) return ' (약한 근거: 본문에만, 제목 불일치)';
  const missing = (/있으나 (.+?) 없음/.exec(why) ?? [])[1] ?? (/낱말\(.*?\)은 겹치나 (.+?) 없음/.exec(why) ?? [])[1];
  if (missing) return ` (약한 근거: ${missing} 없음 — 다른 건일 수 있음)`;
  return verdict === '미보도 후보' ? ' (약한 근거: 판정에 안 셈)' : '';
}

// id → how radar_today would show it now (watch, kind, tier, short title). Used to label judgments.
export async function itemIndex(ctx) {
  const docs = Object.fromEntries(await Promise.all(WATCHES.map(async (w) => [w.feed, await readFeed(ctx, w.feed)])));
  const index = new Map();
  for (const x of collect(docs, 0, '', { all: true })) {
    if (!x.id || index.has(x.id)) continue;
    const head = String(x.fact ?? '').split(' — ')[0];  // the headline, without the digest's notes
    index.set(String(x.id), { watch: x.watch, kind: x.kind ?? '', tier: x.tier, flag: x.flag ?? '',
      title: `${x.company && !head.startsWith(x.company) ? `${x.company} · ` : ''}${head}`.slice(0, 120) });
  }
  return index;
}

function health(ctx, docs) {
  const lines = [];
  for (const w of WATCHES) {
    const d = docs[w.feed];
    if (!d) { lines.push(`- ${w.label}: 결과 없음 — 미확인(${w.schedule} 실행 확인)`); continue; }
    if (d.broken) { lines.push(`- ${w.label}: 저장 형식 오류 — 미확인`); continue; }
    const ageH = (ctx.now.getTime() - Date.parse(d.generatedAt)) / 3600000;
    const waiting = (d.checks ?? []).filter((c) => c.status === 'partial' && !c.error && c.pending);  // read budget, not a failure
    const paused = (d.checks ?? []).filter((c) => c.status === 'waiting');  // call budget or provider cooldown: 미확인, not a failure
    const failed = (d.checks ?? []).filter((c) => c.status && !['ok', 'unset', 'waiting'].includes(c.status) && !waiting.includes(c) && !String(c.source ?? '').startsWith('공장등록 이름 규칙'));
    const unset = (d.checks ?? []).filter((c) => c.status === 'unset');
    const issues = [];
    if (Number.isFinite(ageH) && ageH > (w.staleHours ?? 36)) issues.push(`⚠ ${Math.round(ageH)}시간 전 결과`);
    if (failed.length) issues.push(`일부 실패 ${failed.length}건(${failed.slice(0, 3).map((c) => c.source ?? c.company ?? c.target).join(', ')})`);
    if (unset.length) issues.push(`미설정 ${unset.map((c) => `${c.source}(${c.error ?? '열쇠 없음'})`).join(', ')}`);
    if (waiting.length) issues.push(`${waiting.map((c) => `${c.source} 원문 대기 ${c.pending}건`).join(', ')}(실행당 읽기 한도, 다음 실행에서 읽음)`);
    if (paused.length) issues.push(`대기 ${paused.length}곳(${[...new Set(paused.map((c) => waitReason(c.reason)))].join(', ')})`);
    if (issues.length) lines.push(`- ${w.label}: ${issues.join(' · ')} — 해당 부분 0건은 미확인`);
  }
  return lines;
}

// 겹친 신호: 공장·부지에 닿는 감시(공장등록·건축허가·지자체 고시·국민연금 사업장·굴뚝 측정·단독 후보·전기위)가 14일 안에
// 같은 출입처·같은 시군을 가리키면 묶는다. 하나씩은 공개 자료여도, 여러 감시가 한곳을 가리키면 투자·가동 변화일 가능성이 커진다.
// 장소는 항목 문장에서 시군 이름(공장 이름 포함)을 찾는다 — 못 찾으면 묶지 않는다.
const PLACE_WATCHES = new Set(['kr_official', 'kr_signals', 'scoop_screen']);
const PLACES = [['당진'], ['아산'], ['화성'], ['광양'], ['포항'], ['울산', /울산|온산|울주/], ['여수'], ['순천'], ['인천', /인천|부평/], ['창원'],
  ['평택'], ['군산', /군산|새만금/], ['익산'], ['서산', /서산|대산/], ['대전', /대전|대덕/], ['금산'], ['곡성'], ['함평'], ['광주', /광주(?:광역시|1공장|2공장|\s*기아|공장)|AutoLand\s*광주|광산구/],
  ['완주', /완주|전주공장/], ['봉화', /봉화|석포/], ['구미'], ['청주'], ['원주'], ['예산'], ['진천'], ['음성'], ['동해'], ['부산'], ['양산'],
  ['창녕'], ['안성'], ['광명'], ['천안'], ['영주'], ['삼척'], ['김해'], ['세종']].map(([name, rx]) => [name, rx ?? new RegExp(name)]);
// 사업장 이름에 시군이 없는 큰 공장(굴뚝 측정·국민연금 이름 그대로)
const SITE_PLACE = [[/현대제철㈜(?![가-힣])|현대제철주식회사(?![가-힣])/, '당진'], [/지에스칼텍스㈜|GS칼텍스주식회사/, '여수'], [/두산에너빌리티\(주\)/, '창원'],
  [/엘에스엠앤엠/, '울산'], [/동국제강㈜(?![가-힣\s]*공장)/, '인천'], [/르노코리아 주식회사/, '부산'], [/케이지모빌리티 주식회사/, '평택'], [/한국지엠주식회사/, '인천']];
const canonCompany = (c) => String(c ?? '').replace(/\s+|\(주\)|㈜|주식회사/g, '').replace(/^현대자동차$/, '현대차').replace(/^기아자동차$/, '기아');

// 묶음의 배경: 새 항목은 아니지만 같은 곳에서 이미 진행 중인 것(국민연금 공사 현장 A·B, 120일 안 건축허가, 지금 멈춘 굴뚝).
export function background(docs, nowMs) {
  const out = [];
  const W = Object.fromEntries(WATCHES.map((w) => [w.feed, w]));
  for (const p of docs['kr-workforce']?.projects ?? []) {
    if (p.tier === 'C' || !p.company) continue;
    out.push({ id: `bg:wf:${p.id}`, background: true, tier: p.tier, tool: 'kr_official', watch: W['kr-workforce'].label, company: p.company, date: p.firstSeen,
      fact: `국민연금 공사 현장 「${p.title ?? p.name ?? ''}」 현장 ${p.sites ?? 1}곳${p.addr ? ` · ${p.addr}` : ''}` });
  }
  const from = new Date(nowMs - 120 * 86400000).toISOString().slice(0, 10);
  for (const x of docs['kr-building']?.permits ?? []) {
    if (x.orphan || x.tier === 'C' || !x.company || String(x.permitted ?? '') < from) continue;
    out.push({ id: `bg:bd:${x.id}`, background: true, tier: x.tier, tool: 'kr_official', watch: W['kr-building'].label, company: x.company, date: x.permitted,
      fact: `건축 ${x.kind ?? ''} ${buildingLine(x)}` });
  }
  for (const s of docs['kr-stacks']?.sites ?? []) {
    if (!(s.stopped ?? []).length) continue;
    // 배출구가 많은 제철소의 한두 개 멈춤은 일상 정비 수준이라 배경으로도 묶지 않는다(굴뚝 감시의 B 기준과 같은 5%)
    // (10-31 운영: 포스코 광양 137개 중 2개·포항 101개 중 2개가 '겹친 신호' 배경으로 붙어 감시 2곳 묶음을 만들었다)
    if ((s.meaningful ?? 0) >= 40 && s.stopped.length < Math.ceil(s.meaningful * 0.05)) continue;
    out.push({ id: `bg:stk:${s.id}`, background: true, tier: 'B', tool: 'kr_official', watch: W['kr-stacks'].label, company: s.company, date: docs['kr-stacks'].generatedAt,
      fact: `${s.name} 굴뚝 배출구 멈춤 ${s.stopped.length}개(평소 움직이던 ${s.meaningful ?? '?'}개 중)` });
  }
  return out;
}

export function convergence(items, { cut } = {}) {
  const groups = new Map();
  for (const x of items) {
    if (x.tier === 'C' || !x.company || !PLACE_WATCHES.has(x.tool)) continue;
    const text = `${x.fact ?? ''} ${x.company ?? ''}`;
    const places = new Set(PLACES.filter(([, rx]) => rx.test(text)).map(([name]) => name));
    for (const [rx, name] of SITE_PLACE) if (rx.test(text)) places.add(name);
    for (const place of places) {
      const key = `${canonCompany(x.company)}|${place}`;
      if (!groups.has(key)) groups.set(key, { company: canonCompany(x.company), place, items: [] });
      const g = groups.get(key);
      if (!g.items.some((y) => y.id === x.id)) g.items.push(x);
    }
  }
  const out = [];
  for (const g of groups.values()) {
    const watches = [...new Set(g.items.map((x) => x.watch))];
    // 배경(기준선 공사 현장·최근 허가·지금 멈춘 굴뚝)만으로는 묶지 않는다 — 최근 14일 A·B 항목이 하나는 있어야 한다
    if (watches.length < 2 || !g.items.some((x) => !x.background)) continue;
    const times = g.items.map((x) => Date.parse(x.date)).filter(Number.isFinite);
    const latest = times.length ? Math.max(...times) : null;
    // 날짜만 있는 항목(공고일·허가일)은 한국 날짜로 견준다
    const isNew = (x) => { if (x.background || cut == null) return false; const d = String(x.date ?? ''); if (/^\d{4}-\d{2}-\d{2}$/.test(d)) return d >= kstDate(cut); const t = Date.parse(d); return Number.isFinite(t) && t >= cut; };
    out.push({ ...g, watches, latest, fresh: g.items.some(isNew),
      hasA: g.items.some((x) => x.tier === 'A') });
  }
  return out.sort((a, b) => b.watches.length - a.watches.length || Number(b.fresh) - Number(a.fresh) || Number(b.hasA) - Number(a.hasA) || (b.latest ?? 0) - (a.latest ?? 0));
}

// 묶음에 보일 줄: 새 신호(배경 아님)를 먼저, 배경은 감시별로 한 줄로 합친다
// (10-31 운영: 금호타이어 함평 정련동 공사가 시공사마다 이름이 조금씩 달라 국민연금 공사 현장 배경 3줄이 묶음 4줄 중 3줄을 채웠다).
export function convergenceRows(g, max = 4) {
  const byDate = (a, b) => String(b.date ?? '').localeCompare(String(a.date ?? ''));
  const fore = g.items.filter((x) => !x.background).sort(byDate);
  const back = new Map();
  for (const x of g.items.filter((y) => y.background).sort(byDate)) {
    if (!back.has(x.watch)) back.set(x.watch, []);
    back.get(x.watch).push(x);
  }
  const merged = [...back.values()].map((xs) => {
    if (xs.length === 1) return xs[0];
    const titles = xs.map((x) => /「([^」]+)」/.exec(x.fact ?? '')?.[1]);
    const lead = /^[^「]*/.exec(xs[0].fact ?? '')[0].trim();
    const fact = titles.every(Boolean)
      ? `${lead} ${xs.length}건 · ${titles.map((t) => `「${clipAt(t, 40)}」`).join(' · ')}`
      : `${xs.length}건 · ${xs.map((x) => clipAt(x.fact, 50)).join(' · ')}`;
    return { ...xs[0], fact, id: `${xs[0].id} 외 ${xs.length - 1}` };
  });
  const rows = [...fore, ...merged];
  return { rows: rows.slice(0, max), more: Math.max(0, rows.length - max) };
}

export async function radarToday(ctx, args) {
  const nowMs = ctx.now.getTime();
  const monday = new Date(nowMs + KST_MS).getUTCDay() === 1;
  const hours = clampInt(args.hours, 1, 336, monday ? 72 : 24);
  const cut = nowMs - hours * 3600000;
  const cutDay = kstDate(cut);
  const q = String(args.company ?? '').trim();
  const limit = clampInt(args.limit, 1, 60, 15);
  const showC = args.include_minor === true || args.include_minor === 'true';
  const docs = Object.fromEntries(await Promise.all(WATCHES.map(async (w) => [w.feed, await readFeed(ctx, w.feed)])));
  const { rows: fb } = await storeOp(ctx, 'feedback.latest', {});
  const judged = new Map(fb.map((r) => [r.item_id, r.verdict]));
  const showJudged = args.include_judged === true || args.include_judged === 'true';
  const found = collect(docs, cut, cutDay, { now: nowMs }).filter((x) => has(q, x.company, x.fact, x.watch));
  const hiddenBy = {};
  const all = found.filter((x) => {
    const v = judged.get(x.id);
    if (!v || showJudged) return true;
    hiddenBy[v] = (hiddenBy[v] ?? 0) + 1;
    return false;
  });
  // Automatic press check (radar_press_check.py): unreported first, then unchecked/미확인, then already covered.
  const press = await readFeed(ctx, 'radar-check');
  const checked = new Map((press?.broken ? [] : press?.items ?? []).map((r) => [String(r.id), r]));
  const pressOf = (x) => x.verdict ?? checked.get(String(x.id))?.verdict;
  const rank = (x) => PRESS_RANK[pressOf(x)] ?? 1;
  const byTier = (t) => all.filter((x) => x.tier === t)
    .sort((a, b) => rank(a) - rank(b) || String(b.date ?? '').localeCompare(String(a.date ?? '')));

  const out = [`오늘의 레이더 · ${kstStamp(ctx.now.toISOString())} KST 기준 최근 ${hours}시간${monday && !args.hours ? '(월요일: 주말 포함)' : ''} · 기자 전용 감시 ${WATCHES.length}개`];
  const h = health(ctx, docs);
  const dh = await dispatchHealth(ctx);
  if (dh) h.unshift(`- ${dh}`);
  if (!press) h.push('- 보도 대조(자동): 결과 없음 — 미확인(평일 08:50·18:50 실행 확인)');
  else if (press.broken) h.push('- 보도 대조(자동): 저장 형식 오류 — 미확인');
  else {
    const ageH = (nowMs - Date.parse(press.generatedAt)) / 3600000;
    if (Number.isFinite(ageH) && ageH > 36) h.push(`- 보도 대조(자동): ⚠ ${Math.round(ageH)}시간 전 결과 — 이후 항목은 대조 전`);
  }
  out.push(h.length ? `\n[먼저 볼 것: 수집 상태]\n${h.join('\n')}` : `\n[수집 상태] ${WATCHES.length}개 감시 모두 최근 정상`);
  const span = nowMs - 14 * 86400000;
  const conv = convergence([...collect(docs, span, kstDate(span), { now: nowMs }).filter((x) => !(judged.get(x.id) && !showJudged)), ...background(docs, nowMs)]
    .filter((x) => has(q, x.company, x.fact, x.watch)), { cut });
  if (conv.length) {
    out.push(`\n[겹친 신호 · 최근 14일 같은 출입처·같은 시군을 감시 여러 곳이 가리킴] ${conv.length}곳 — 하나씩은 공개 자료, 함께 보면 투자·가동 변화 단서(배경: 국민연금 공사 현장·120일 안 건축허가·지금 멈춘 굴뚝)`);
    for (const g of conv.slice(0, 5)) {
      out.push(`- ${g.fresh ? '[새 항목 포함] ' : ''}${g.company} · ${g.place} — 감시 ${g.watches.length}곳(${g.watches.join(', ')})`);
      const { rows, more } = convergenceRows(g);
      for (const x of rows) out.push(`   ${x.background ? '(배경) ' : `${x.tier} · `}${x.date ? `${String(x.date).length > 10 ? kstStamp(x.date) : x.date} · ` : ''}${x.watch}: ${clipAt(x.fact, 110)} · id ${x.id}`);
      if (more) out.push(`   … 같은 묶음 ${more}줄 더`);
    }
    if (conv.length > 5) out.push(`… 남은 ${conv.length - 5}곳(company로 좁히기)`);
    out.push('   읽는 법: 같은 시군 이름이 문장에 있으면 묶는다(같은 공장·같은 사업이라는 확인이 아님). 각 원문을 열어 같은 부지·사업인지 본다.');
  }
  const tiers = [['A', '단독 후보·직접 변화 — 원문·보도 대조부터'], ['B', '확인할 공식 변화'], ['C', '참고(접힘)']];
  for (const [t, title] of tiers) {
    const rows = byTier(t);
    if (t === 'C' && !showC) {
      if (rows.length) out.push(`\n[C · ${title}] ${rows.length}건 — 소비자 소송·사이트 공통 문구·기보도 후보 등 (include_minor=true)`);
      continue;
    }
    out.push(`\n[${t} · ${title}] ${rows.length}건`);
    if (press && !press.broken && rows.length) {
      const n = (v) => rows.filter((x) => checked.get(String(x.id))?.verdict === v).length;
      const none = rows.filter((x) => x.watch !== WATCHES[0].label && !checked.has(String(x.id))).length;
      out.push(`(보도 대조 자동 ${kstStamp(press.generatedAt)}: 미보도 후보 ${n('미보도 후보')} · 관련 보도 있음 ${n('관련 보도 있음') + n('같은 수치 선행')} · 미확인 ${n('미확인')} · 대조 안 함 ${none} — 미보도 후보부터)`);
    }
    for (const x of rows.slice(0, limit)) {
      out.push(`- ${x.date ? `${String(x.date).length > 10 ? kstStamp(x.date) : x.date} · ` : ''}${x.watch}${x.company ? ` · ${x.company}` : ''}`);
      out.push(`   ${x.fact}`);
      out.push(...pressLines(checked.get(String(x.id)), kstStamp(press?.generatedAt)));
      out.push(`   ${x.url ? `원문: ${x.url} · ` : ''}자세히: ${x.tool} · id ${x.id}${judged.get(x.id) ? ` 〔판정: ${judged.get(x.id)}〕` : ''}`);
    }
    if (rows.length > limit) out.push(`… 남은 ${rows.length - limit}건(limit 또는 company로 좁히기)`);
    if (!rows.length) out.push('없음');
  }
  // Competitor exclusives the radar had first (reverse_prior_capture.py). Shown here too, so the reporter can prepare Y/P/N
  // judgments even when the chat's connector list is stale and scoop_reverse is not offered.
  const rev = await readFeed(ctx, 'reverse-check');
  if (rev && !rev.broken) {
    const from = Date.parse(rev.generatedAt) - 14 * 86400000;
    const firsts = (rev.articles ?? []).filter((a) => a.verdict === '먼저 잡은 후보' && Date.parse(a.published) >= from && a.best
      && (!q || has(q, a.title, (a.companies ?? []).join(' '), a.best.text)))
      .sort((a, b) => String(b.published).localeCompare(String(a.published)));
    if (firsts.length) {
      out.push(`\n[경쟁지 단독 역추적 · 자동 후보, 사람 판정(Y/P/N) 전] 최근 14일 레이더가 먼저 잡은 후보 ${firsts.length}건 · 확인 ${kstStamp(rev.generatedAt)}`);
      for (const a of firsts.slice(0, 5)) {
        out.push(`- 기사 ${kstStamp(a.published)} · ${a.source ?? '?'} 「${String(a.title ?? '').slice(0, 70)}」 · 기사 id ${a.articleId}`);
        out.push(`   레이더: ${kstStamp(a.best.seen)} ${a.best.label} — ${String(a.best.text ?? '').slice(0, 90)} (${a.best.leadHours}시간 앞${(a.best.why ?? []).length ? `, 겹친 낱말 ${a.best.why.join('·')}` : ''}) · id ${a.best.id}`);
      }
      if (firsts.length > 5) out.push(`… 남은 ${firsts.length - 5}건`);
      out.push('판정은 기자가 한다: 기사 원문(매체 사이트)·최초 게재 시각과 레이더 원천 원문을 열어 같은 사실인지 본다. 자세히: scoop_reverse.');
    }
  }
  const hiddenN = Object.values(hiddenBy).reduce((a, b) => a + b, 0);
  if (hiddenN) out.push(`\n(판정한 ${hiddenN}건 숨김: ${Object.entries(hiddenBy).map(([v, n]) => `${v} ${n}`).join(' · ')} — include_judged=true로 보기)`);
  out.push('정리: 다 본 항목은 candidate_feedback(verdict=봤음, item_ids=[…])로 표시하면 다음부터 안 뜬다.');
  out.push('\n규칙: 모두 자동 수집 단계다. A도 단독 확정이 아니다 — 원문 확인 → news_check(낱말 바꿔 2~3번) → 회사 확인 → candidate_check. 첫 실행에 잡힌 기존 항목은 자기 날짜가 최근일 때만 새 항목으로 센다.');
  out.push("보도 대조(자동)는 네이버 뉴스 API·빙·구글에서 항목 날짜 3일 전부터 찾은 결과다. '미보도 후보'도 단독 판정이 아니고, '관련 보도 있음'은 같은 사건인지 열어 봐야 한다. 채널 실패는 미확인.");
  return textResult(out.join('\n'));
}
