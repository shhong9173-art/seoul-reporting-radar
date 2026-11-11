// radar_today: one private digest over the eleven private watches. It reads what the collectors already stored
// (no new fetching), keeps what is new since a cutoff, and ranks it. Failed or stale watches are listed first:
// their silence is "미확인", not "nothing new".
import { readFeed, weekdayHours } from './screen.mjs';
import { storeOp } from './store.mjs';
import { dispatchHealth } from './dispatch.mjs';
import { browserHealth } from './local_browser.mjs';
import { runsHealth } from './gh_runs.mjs';
import { MAINT_KINDS, MAINT_RE, kstMD, maintFolded, maintenanceMemo, stackSiteKey } from './stack_memo.mjs';
export { MAINT_KINDS, MAINT_RE, maintFolded, maintenanceMemo, stackSiteKey };
import { clampInt, fetchJson, safeEqual, textResult, uniqueList } from './common.mjs';
import { peerLines } from './radar_tools.mjs';
import { classLabel, waitReason } from './trademarks.mjs';
import { billLine, groupBillEvents } from './assembly.mjs';
import { attachmentOutline, buildingLine, factoryEventText, identityNote, itcText, mediationPast, memoGloss, productKo, productOf, rateChangeText, rateText, reverseClip, reverseNumbersNote, tradePoint } from './overseas.mjs';

const KST_MS = 9 * 3600000;
const kstDate = (ms) => new Date(ms + KST_MS).toISOString().slice(0, 10);
export const kstStamp = (v) => { const t = Date.parse(v); return Number.isFinite(t) ? new Date(t + KST_MS).toISOString().slice(5, 16).replace('T', ' ') : String(v ?? '').slice(0, 16); };
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
  // 11-10: 출입처 유럽(EP)·국제(WO) 특허 공개(EPO OPS) — EP 수요일·WO 목요일 공개 뒤 토요일 아침 주 1회. 약관상 기자 전용 연결에서만.
  { feed: 'epo-patents', label: '해외 특허 공개(EP·WO)', tool: 'patents_abroad', schedule: '토 06:40', staleHours: 192 },
  { feed: 'assembly-bills', label: '국회 법안', tool: 'assembly_bills', schedule: '평일 08:40·17:40' },
  { feed: 'us-recalls', label: '미국 리콜(NHTSA 전체)', tool: 'us_recalls', schedule: '매일 17:10' },
  { feed: 'us-epa', label: '미국 EPA 인증', tool: 'us_epa', schedule: '매일 06:20', staleHours: 60 },
  { feed: 'us-osha', label: '미국 OSHA 점검·위반', tool: 'us_litigation', schedule: '매일 06:40', staleHours: 60 },
  // 미국 주 환경청 허가·공고(us_state_env_watch.py): 조지아 EPD 주간 공고 PDF·앨라배마 ADEM·루이지애나 LDEQ — 출입처 미국 공장의 대기 허가 신청·제재
  { feed: 'us-state-env', label: '미국 주 환경 허가·공고', tool: 'us_litigation', schedule: '매일 07:05', staleHours: 60 },
  { feed: 'kr-fuel', label: '국내 연비 신고', tool: 'kr_fuel', schedule: '매일 06:10', staleHours: 60 },
  { feed: 'overseas-awards', label: '해외 발주처 낙찰', tool: 'partner_filings', schedule: '평일 06:50·17:30' },
  { feed: 'kr-insolvency', label: '협력사 회생·파산', tool: 'kr_official', schedule: '평일 07:20·17:20' },
  { feed: 'kr-energy', label: '전기위·원안위', tool: 'kr_signals', schedule: '평일 15:40·18:10' },
  { feed: 'kr-building', label: '공장 부지 건축허가', tool: 'kr_official', schedule: '월 07:50', staleHours: 192 },
  { feed: 'overseas-registry', label: '해외 법인 등기(영국)', tool: 'partner_filings', schedule: '평일 06:00' },
  { feed: 'kr-local', label: '지자체 고시·공고', tool: 'kr_official', schedule: '평일 06:30·16:20' },
  { feed: 'kr-workforce', label: '사업장 인력(국민연금)', tool: 'kr_official', schedule: '평일 15:50', staleHours: 80 },
  { feed: 'kr-stacks', label: '굴뚝 측정(공장 가동 신호)', tool: 'kr_official', schedule: '3시간마다', staleHours: 12 },
  // 노동위원회 회의(kr_labor_watch.py): 중앙·지방 14곳 첫 화면 '오늘 회의'의 사건명 앞 당사자가 출입처인 것 — 노동쟁의 조정·교섭·부당노동행위 A
  { feed: 'kr-labor', label: '노동위 회의(조정·심판)', tool: 'kr_official', schedule: '평일 08:20', staleHours: 80 },
  // 노조 성명·보도자료(union_watch.py): 금속노조·화섬식품노조 공개 게시판 새 글에 출입처 이름 — 사망·사고·파업·매각·분할·가처분 등 A
  { feed: 'union-notices', label: '노조 성명·보도자료', tool: 'kr_official', schedule: '매일 09:30·12:30·15:30·18:30·21:30', staleHours: 30 },
  // 지방의회 회의록(council_watch.py): 국회도서관 지방의정포털 회의록 API — 출입처 이름 대목에 인허가·불법·오염·감면·증설·이전 등이면 A
  { feed: 'council-minutes', label: '지방의회 회의록', tool: 'kr_official', schedule: '매일 09:10', staleHours: 60 },
  // 인도 상장 법인 공시(india_filings_watch.py): NSE 공시 RSS의 현대차 인도법인 공시 — 인수·설비·로열티 A, 이사회 결과·보도자료 B
  { feed: 'india-filings', label: '인도 법인 공시(현대차 인도)', tool: 'partner_filings', schedule: '평일 13:10·16:10·19:10·22:10', staleHours: 80 },
  // 타사 공시 속 출입처(dart_counterparty_watch.py): 출입처 아닌 회사의 양수도·공급계약·생산중단 공시에 출입처가 거래상대로 적힌 것
  { feed: 'dart-counterparty', label: '타사 공시 속 출입처(거래상대)', tool: 'kr_signals', schedule: '평일 10:50·13:50·16:50·19:50', staleHours: 80 },
  // 지분·자사주 변동(governance_watch.py, OpenDART 지분공시·자기주식 처분 결정): 임원 집단 보고·보유분 절반 넘는 임직원 보상 자사주 처분·매각 목적 처분 B
  { feed: 'governance', label: '지분·자사주 변동', tool: 'governance_changes', schedule: '평일 07:40' },
  // 임원 명단 변화(kr_exec_watch.py, 11-05 기자 요청 — 선배 매의눈이 보고서 속 한 회사 전 대표 이사 등재를 잡은 것처럼, 출입처 회사에):
  // 분기·반기·사업보고서 '임원 현황'을 바로 앞 보고서와 비교 — 오너 일가·주의 회사 출신·임기 중 빠짐·수시 인사 철 경쟁사 출신 영입 A
  { feed: 'kr-exec', label: '임원 명단 변화(정기보고서)', tool: 'kr_signals', schedule: '평일 07:50·21:50', staleHours: 60 },
  // 수시 임원 공시·타사 임원 명단(kr_exec_market.py, 11-05): 독립이사 선임·중도퇴임 신고·대표이사 변경(시장 전체, 출입처 회사 출신만 — 고위 출신 A)과
  // 출입처 소집공고 이사 후보(부실기업 경영진 여부 등), 상장사 등기임원 명단 순환 조회
  { feed: 'kr-exec-market', label: '수시 임원 공시·타사 임원 명단', tool: 'kr_signals', schedule: '매일 06:20·12:20·18:20', staleHours: 30 },
  // 문제 임원 점검(kr_exec_check.py, 11-05 기자: "임원에 대한 단독 — 문제 있는 임원"): 출입처 등기임원·미등기 사장급 한 사람씩
  // 독립이사 법정 결격 가능(상법 시행령 제34조⑤ 7호 6년·3호 겸직·1호 계열사 최근 근무)과 과거 논란 기사(이름+회사, 제목에 비위·사고·제재 낱말)
  { feed: 'kr-exec-check', label: '문제 임원 점검', tool: 'kr_signals', schedule: '매일 05:50', staleHours: 40 },
  // 해외 매체 기사 중 직접 출입처 이름이 나온 것(global_collector.py, 뉴스 수집 20분마다) — AI 번역·요약이라 원문 확인
  { feed: 'global-beat', label: '출입처 외신', tool: 'source_document', schedule: '20분마다', staleHours: 6 },
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
  // 감시 도중 더한 출입처·원천의 첫 읽기(항목에 baseline: true)는 그 항목 날짜로만 센다
  // (11-01: 석유화학 6곳을 더한 첫 실행에 롯데케미칼 6월 의견서 3건이 오늘 B로 떴다).
  if (x.baseline === true) return false;
  return Number.isFinite(seen) && seen >= cut && !(base !== null && Math.abs(seen - base) < 120000);
}

// Press-check hints (radar_press_check.py): the subject a story would name and the words it would use. Only items whose
// subject is a beat company (or a bill's law name) get one; the checker screens nothing else. Hints are search words,
// not facts — the item's own line stays as collected.
const ALT = {
  // 출입처 외신 사건 낱말(global_collector.py KO_EVENTS)
  원자로: ['원자로', '원전', 'SMR', '소형모듈원전', '소형원전', '원자로 용기'], 해상풍력: ['해상풍력', '풍력'], 해저케이블: ['해저케이블', '해저 케이블', 'HVDC', '케이블'], 변압기: ['변압기', '전력기기'], 모노파일: ['모노파일', '하부구조물'], 제련소: ['제련소', '제련'], 투자: ['투자', '증설', '건설'], MOU: ['MOU', '양해각서', '협약', '협력'], 입찰: ['입찰', '경쟁입찰'], 인수: ['인수', '매각', 'M&A'], 파업: ['파업', '노조', '쟁의'], 감산: ['감산', '생산 중단', '가동 중단'], ESS: ['ESS', '에너지저장'], 태양광: ['태양광', '폴리실리콘', '모듈'], 철강: ['철강', '강판', '열연', '냉연'], 배터리: ['배터리', '이차전지'], 타이어: ['타이어'],
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
  // 노동위 회의(kr-labor): 사건 종류 낱말 — 회사 이름과 함께 제목에 있어야 같은 사건 후보
  노동쟁의: ['쟁의', '파업', '조정 신청', '조정신청', '조정 중지', '조정중지', '노동위', '중노위', '지노위'],
  // 조정 회의 다음 날 결과 확인(11-04): 회의일 이후 기사만 센다(check.after) — 중지·성립·연장·파업권 낱말
  // 임원 명단 변화(kr-exec): 사람 이름과 함께 인사 낱말 — 기사엔 그 사람 이름이 있어야 같은 건(must)
  인사: ['인사', '영입', '선임', '승진', '퇴임', '사임', '물러', '교체', '발탁', '내정', '임원', '이사회'],
  사외이사: ['사외이사', '독립이사', '겸직', '결격', '임기', '연임'], 논란: ['논란', '의혹', '사퇴', '책임', '수사', '기소', '고발', '징계', '해킹', '유출', '횡령', '배임'],
  '조정 결과': ['조정 중지', '조정중지', '조정 성립', '조정안', '조정 연장', '조정 결렬', '쟁의권', '파업권', '쟁의행위', '파업 찬반', '파업'],
  부당노동행위: ['부당노동행위', '노동위', '중노위', '지노위'], 교섭: ['교섭', '하청', '원청', '노란봉투'],
  부당해고: ['부당해고', '해고', '노동위', '중노위', '지노위'], 노동위: ['노동위', '중노위', '지노위', '노동위원회'],
  // 지분·자사주 변동(governance)
  자사주: ['자사주', '자기주식'], 임원: ['임원', '지분', '주식 보상'],
  // 노조 성명·보도자료(union-notices): 사고·고발 낱말 묶음
  불법: ['불법', '위반', '야적', '행정처분'], 오염: ['오염', '유출', '악취', '배출'], 의회: ['의회', '시의회', '도의회', '군의회', '의원'],
  고발: ['고발', '고소', '가처분', '소송'],
  // 미국 주 상공위원회 안건(us-state-env): 세제 감면·인센티브
  감면: ['감면', '세제 혜택', '세금 혜택', '인센티브', '세액'],
  OSHA: ['OSHA', '산업안전보건청', '미국 노동부', '산업안전'], 벌금: ['벌금', '과징금', '제재', '위반'], 사고: ['사고', '사망', '부상', '숨져', '중상', '끼임', '추락', '화재', '폭발', '중대재해', '산재'],   // 노조 성명(11-03)도 같은 묶음
    공정위: ['공정위', '공정거래위원회'], 과징금: ['과징금', '제재', '시정명령', '고발', '경고'], 한전: ['한전', '한국전력'],
  수주: ['수주', '입찰', '낙찰', '공급', '계약'], 관세: ['관세', '반덤핑', '상계관세', '덤핑'], 판정: ['판정', '예비', '최종', '재심', '연례재심'],
  계약: ['계약', '협약', '합의', '공급', '합작', 'MOU'], 의견서: ['의견서', '의견', '제출', '요청'], 상표: ['상표', '출원', '브랜드', '명칭'],
  개정안: ['개정안', '발의', '법안', '개정', '대표발의'], BAIC: ['BAIC', '베이징자동차', '베이징기차', '北汽'],
  합작: ['합작', '지분', '매각', '정리', '철수', '계약', '합작사'], 보조금: ['보조금', '상계관세', '어린이집', '직장', '지원'],
  리콜: ['리콜', '결함', '시정조치', '화재 위험'], 무상수리: ['무상수리', '무상 수리', '보증 연장', '보증기간', '서비스 캠페인', '무상 교체', '무상 점검'], 가격: ['가격', '판매가', '출고가', 'MSRP', '값'], 미국: ['미국', '美'],
  EPA: ['EPA', '환경보호청', '인증', '주행거리', '연비'],
  회생: ['회생', '법정관리', '파산', '기업회생', '워크아웃'], 파산: ['파산', '청산', '회생', '법정관리'], 매각: ['매각', '인수', 'M&A', '새 주인'],
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
// 발췌에 적힌 거래 날짜(11-04: Rhythm 10-Q 'On January 4, 2024, … entered into a license agreement … with LG Chem', Aptiv 10-Q
// 'On August 14, 2026, Hyundai … invested approximately $250 million in Motional'이 A — 이미 있던 거래를 다시 적은 것이다)
const MONTHS = { january: 1, february: 2, march: 3, april: 4, may: 5, june: 6, july: 7, august: 8, september: 9, october: 10, november: 11, december: 12 };
export function snippetDates(text) {
  const out = [];
  for (const m of String(text ?? '').matchAll(/\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(?:(\d{1,2}),\s*)?(20\d\d)\b/gi)) {
    out.push(`${m[3]}-${String(MONTHS[m[1].toLowerCase()]).padStart(2, '0')}-${String(m[2] ?? 1).padStart(2, '0')}`);
  }
  return out;
}
const PERIODIC = /^(?:10-Q|10-K|20-F|40-F|10-KT|10-QT)\b/i;   // 정기 보고서 — 날짜 없는 계약 서술은 기존 약정 반복일 때가 많다
const OLD_DEAL_DAYS = 45;
function oldDealOf(x) {
  if (x.source !== 'EDGAR') return null;
  const filed = Date.parse(String(x.date ?? '').slice(0, 10));
  const ds = snippetDates(x.snippet).filter((d) => Number.isFinite(Date.parse(d)));
  if (!ds.length || !Number.isFinite(filed)) return null;
  const recent = ds.some((d) => (filed - Date.parse(d)) / 86400000 <= OLD_DEAL_DAYS);
  return recent ? null : ds.sort().at(-1);
}
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
// 회생·파산 공고의 보도 대조 낱말은 절차대로: 파산 선고를 '회생'으로 찾으면 '○○ 파산' 기사를 못 찾는다
// (10-31 운영: 케이아이씨·남양테크 파산 선고가 "케이아이씨 회생"으로 대조돼 '미보도 후보').
export const insolvencyWord = (kind) => (/파산/.test(String(kind ?? '')) ? '파산' : /M&A|매각/.test(String(kind ?? '')) ? '매각' : '회생');

// 출입처 외신 대조 낱말: 나라·주 이름이 있으면 검색어 둘째 낱말로 넣고(places — 사건 낱말로는 안 셈) 기사 본문에 있어야 같은 건(must).
// 둘째에 넣어야 두 번째 질의('회사 사건 지명')가 좁혀진다 — 셋째면 질의에 안 들어간다(scoop_screen.queries는 앞 두 낱말만).
// since: 외신은 국내 기사보다 늦게 나오는 일이 많아 대조 시작을 게재일 GB_LEAD_DAYS일 전으로 당긴다(대조기의 3일 여유를 더해 10일).
export const GB_LEAD_DAYS = 7;
// 한국어 제목의 라틴 글자 고유어(HTWO·PV5·EV7·CATL 등) — 나라 이름이 없을 때 기사에 이 중 하나는 있어야 같은 건으로 센다(없으면 약한 근거).
// 11-10 운영: Just Auto 「현대차 HTWO 광저우와 에어리퀴드 차이나, 수소 모빌리티 MOU 체결」이 "현대차 MOU"로 대조돼 포스코퓨처엠·현대차
// 흑연 협력 기사로 '관련 보도 있음'. 회사 영문 이름·흔한 약어(MOU·EV·SUV·ESS·H2 등)는 고유어가 아니다.
const GB_LATIN_SKIP = new Set(['MOU', 'EV', 'EVS', 'SUV', 'SUVS', 'AI', 'ESS', 'CEO', 'CFO', 'CTO', 'COO', 'IPO', 'OE', 'OEM', 'US', 'USA', 'UK', 'EU', 'IRA',
  'HVDC', 'SMR', 'LNG', 'LPG', 'GW', 'MW', 'GWH', 'MWH', 'KWH', 'KW', 'CO2', 'ESG', 'IT', 'SW', 'SDV', 'HEV', 'PHEV', 'BEV', 'FCEV', 'ICE', 'NCC', 'KRW',
  'USD', 'EUR', 'JV', 'B2B', 'B2C', 'Q1', 'Q2', 'Q3', 'Q4', 'PE', 'PP', 'ABS', 'NEV', 'LFP', 'NCM', 'NCA', 'RE100', 'H2', 'R&D', 'M&A', 'TV', 'PR', 'VS',
  'HYUNDAI', 'KIA', 'POSCO', 'LG', 'SK', 'LS', 'HD', 'GS', 'OCI', 'KG', 'HL', 'DL', 'S-OIL', 'MOBIS', 'MANDO', 'HANKOOK', 'NEXEN', 'KUMHO', 'HANWHA',
  'DOOSAN', 'HYOSUNG', 'TAIHAN', 'LOTTE', 'GENESIS']);
export const gbNames = (koTitle) => [...new Set((String(koTitle ?? '').match(/[A-Za-z][A-Za-z0-9&-]*[A-Za-z0-9]/g) ?? [])
  .filter((w) => !GB_LATIN_SKIP.has(w.toUpperCase())))].slice(0, 3);

export const gbHint = (who, terms, country, published, koTitle = '') => {
  const names = country ? [] : gbNames(koTitle);
  const h = country ? hint(who, [terms[0], country, ...terms.slice(1)], [country], [country])
    : names.length ? hint(who, terms, [], names) : hint(who, terms);
  const t = Date.parse(published ?? '');
  return h && Number.isFinite(t) ? { ...h, since: kstDate(t - GB_LEAD_DAYS * 86400000) } : h;
};

const sinceMonth = (h, month) => (h && /^\d{4}-\d{2}$/.test(String(month ?? '')) ? { ...h, since: `${month}-01` } : h);

// 무역위 항목 보도 대조(11-08): 회사 이름이 누리집에 대개 없어 품목 이름으로 찾는다('석도강판 반덤핑'). 기사 제목은 짧은 품목 이름을 쓰고
// '인쇄제판용 평면모양 사진플레이트' 같은 긴 정식 품목명은 제목에 잘 안 나와 '미보도 후보'로 잘못 보일 수 있어, 띄어쓰기·쉼표 없는 10자 이하만.
// 덤핑·세이프가드 조사만(특허·원산지 같은 불공정무역행위는 사건 낱말이 제각각이라 뺌). 보도자료(news)는 이미 공개된 뉴스라 대조하지 않는다.
// 무역위 조사 유형(11-11): 누리집 사건 주소의 invstg_type_code — 10100001은 덤핑(사건번호 '구제 23-…', 운영 진행 목록의 이 코드 사건은
// 모두 반덤핑조사), 10100002는 불공정무역행위('구제 4-1-…'). 막 개시한 사건은 상세에 유형이 비어 있다
// (11-05 '중국, 미국, 말레이시아산 아크릴산 2-에틸헥실' — 유형 미상·제목에 '덤핑' 없음).
export function ktcType(e) {
  const code = /invstg_type_code=(\d+)/.exec(String(e?.url ?? ''))?.[1];
  return code === '10100001' ? '덤핑' : code === '10100002' ? '불공정무역행위' : null;
}

// 무역위 새 반덤핑 원심 조사(출입 업종 품목)는 A(11-11): 11-05 16:49 레이더가 B로 잡은 '아크릴산 2-에틸헥실' 새 조사가 다음 날
// 기자 [단독] 「LG화학, 수입산 점착제 원료 반덤핑 조사 신청」(11-06 14:42)이 됐다(Claude가 이 항목으로 11-06 발제 추천 → 기자 취재로
// 신청인 확인). 자동 등급은 B, 자동 보도 대조는 안 함(품목 띄어쓰기·유형 미상)이라 Claude가 따로 보지 않았으면 위로 안 올라왔다.
// 국내 생산자가 신청해야 열리는 조사라 출입처가 신청인일 수 있다(누리집엔 신청인 이름이 없다). 재심(종료·연장)·불공정무역행위는 그대로.
export function ktcNewDumping(e) {
  if (e?.ktcKind !== 'case' || !e?.beat) return false;
  const t = `${e?.label ?? ''} ${e?.text ?? ''}`;
  if (/재심|종료|연장|우회|불공정|원산지|특허|상표|디자인|영업비밀/.test(t)) return false;
  return ktcType(e) === '덤핑' || /덤핑/.test(t);
}

export function ktcHint(e) {
  const p = String(e?.product ?? '').trim();
  // 품목 이름은 두 낱말·14자까지(11-11: '아크릴산 2-에틸헥실'이 띄어쓰기 하나 때문에 대조에서 빠졌다). 긴 정식 품목명은 그대로 뺀다.
  if (e?.ktcKind === 'news' || !p || /[,·]/.test(p) || p.split(/\s+/).length > 2 || p.length > 14) return undefined;
  const t = `${e?.label ?? ''} ${e?.text ?? ''}`;
  const word = /세이프가드|긴급관세/.test(t) ? '세이프가드' : /덤핑/.test(t) || ktcType(e) === '덤핑' ? '반덤핑' : null;
  return word ? hint(p, [word, '무역위원회']) : undefined;
}

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
// 출입처 공장이 있는 시·군·읍 이름을 먼저 찾는다 — '공장' 앞 두 글자만 보면 '울산고무공장'은 '고무', '여수고무제1공장'은 '무제'가 됐다(11-03).
const SITE_CITIES = ['울산', '온산', '울주', '여수', '광양', '포항', '당진', '순천', '아산', '인천', '부평', '서산', '대산', '창원', '부산', '군산', '진천',
  '화성', '광주', '금산', '대전', '평택', '구미', '청주', '오창', '천안', '익산', '전주', '완주', '김천', '경주', '삼척', '동해', '보령', '태안', '나주',
  '목포', '영암', '안산', '시흥', '김해', '양산', '함안', '거제', '사천', '진주', '칠곡', '영천', '봉화', '석포', '달성', '대구', '세종', '충주', '음성',
  '파주', '이천', '안성', '오산', '용인', '수원', '함평', '장성', '영광', '고흥', '해남', '하동', '포천', '김포', '고양', '의왕', '광명', '부천', '서천', '논산', '공주', '홍성', '예산'];
export function siteCity(site) {
  const s = String(site ?? '').replace(/㈜|\(주\)|주식회사/g, ' ');
  const hits = SITE_CITIES.map((c) => [s.indexOf(c), c]).filter(([i]) => i >= 0).sort((a, b) => a[0] - b[0] || b[1].length - a[1].length);
  if (hits.length) return hits[0][1];
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
  // 사흘 넘게 멈춘 배출구는 개수(고로·설비 보수) 기사와도 맞춰 본다(11-02 경향 [단독] '포스코 광양 2고로 전면 개수')
  const words = /배출허용기준/.test(e.kind) ? ['배출허용기준', '초과'] : /재가동/.test(e.kind) ? ['재가동'] : /새/.test(e.kind) ? ['신설', '가동']
    : /해제/.test(e.kind) ? ['재가동', '정비'] : /오래 빠짐/.test(e.kind) ? ['폐쇄', '가동 중단'] : /오래 멈춤|보수·가동중지/.test(e.kind) ? ['가동 중단', '개수', '정비'] : ['가동 중단', '정비'];
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
function collect(docs, cut, cutDay, { all = false, now = Date.now(), maint = null } = {}) {
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
    // 공개된 지 14일 넘은 특허를 레이더가 늦게 본 것은 새 신호가 아니다 — KIPRIS 조회가 막혔다 풀리면 밀린 공개가 한꺼번에 들어온다
    // (11-01 운영: 10-07·10-12 공개특허가 10-31에 처음 심사돼 월요일 B에 남음 — KIPRIS는 10-13 이후 응답 22로 멈춤)
    else if (c.verdict === '미보도 후보' && c.kind === '특허') {
      const lag = ((c.firstSeen ? Date.parse(c.firstSeen) : now) - Date.parse(c.published ?? c.filedOn ?? '')) / 86400000;
      const late = Number.isFinite(lag) && lag > 14;
      push(late ? 'C' : 'B', W['scoop-screen'], { kind, verdict: c.verdict, id: c.id, date: c.published ?? c.filedOn, company: c.company,
        fact: `${title} (특허) — 보도 대조 '미보도 후보' · 특허 공개만으로는 단독이 아님(사업화·생산·수주 연결 확인)${late ? ` · 공개 ${Math.floor(lag)}일 뒤에 레이더가 처음 봄(밀린 공개)` : ''}`, url: c.url });
    }
    // 반기·연간 보고서 표 숫자가 오래된 것(staleDays, scoop_screen.age_mark)은 새 시점 고리가 없으면 오늘 단서가 아니다 — 참고
    // (11-02 운영: 11-01 출입처에 더한 금호석유화학의 08-14 반기보고서 '운송/서비스 4426→5577'이 첫 심사에서 A로 떴다)
    else if (c.verdict === '미보도 후보' && c.staleDays) push('C', W['scoop-screen'], { kind, verdict: c.verdict, id: c.id, date: c.published ?? c.filedOn, company: c.company,
      fact: `${title} (${c.kind ?? ''}) — 보도 대조 '미보도 후보' · 오래된 자료(접수 ${c.staleDays}일 전 — 새 시점 고리 필요)`, url: c.url });
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
  // 법제처 확정 발령: 출입 업종 부처의 행정규칙(고시·훈령·예규) 새 제정·개정은 B, 관세청 통관 사무처럼 공통 낱말만 걸린 것·법령 일부개정은 C(수집기 등급).
  const lawItems = kr?.lawRules?.items ?? [];
  const lawBase = baselineOf(lawItems);
  for (const x of lawItems) {
    if (x.grouped || !fresh(x, lawBase, 'date')) continue;
    push(x.tier === 'B' ? 'B' : 'C', W['kr-official'], { kind: `법제처 ${x.kind}`, id: x.id, date: x.date, company: (x.teams ?? []).join('·'),
      fact: `${x.kind}${x.type ? `(${x.type})` : ''} ${x.change ?? ''} · ${x.org}: ${x.title}${x.siblings ? ` 외 같은 번호 ${x.siblings}건` : ''} — ${x.kind === '법령해석례' ? '회신' : '발령'} ${x.date}`, url: x.url });
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
  // 공정위 보도·참고·설명자료: 제목에 출입처 이름이 있으면 B, 업종 낱말·관련 기업만이면 C(공개 발표 — 단독 근거 아님)
  for (const x of ks?.ftcPress ?? []) {
    if (!(all || String(x.date ?? '') >= cutDay)) continue;
    const named = (x.companies ?? []).length;
    push(named ? 'B' : 'C', W['kr-signals'], { kind: x.kind === '설명' ? '공정위 설명자료' : '공정위 발표', id: x.id, date: x.date,
      company: [...(x.companies ?? []), ...(x.related ?? [])].join('·') || x.dept,
      fact: `공정위 ${x.kind}${x.dept ? `(${x.dept})` : ''}: ${x.title}`, url: x.url, check: named ? hint(x.companies[0], ['공정위']) : undefined });
  }
  // 정책브리핑 부처 보도자료(기후에너지환경부·국토교통부): 제목에 출입처 이름이면 B, 부처별 업종 낱말만이면 C
  for (const x of ks?.briefing ?? []) {
    if (!(all || String(x.date ?? '') >= cutDay)) continue;
    const named = (x.companies ?? []).length;
    push(named ? 'B' : 'C', W['kr-signals'], { kind: `${x.ministry} 발표`, id: x.id, date: x.date, company: (x.companies ?? []).join('·') || x.ministry,
      fact: `${x.ministry} 보도자료: ${x.title}`, url: x.url, check: named ? hint(x.companies[0], [x.ministry.replace(/부$/, '')]) : undefined });
  }
  // 나라장터 낙찰: 출입처가 낙찰자이고 10억원 이상이면 B(낙찰 ≠ 계약), 그 밖(관용차 등 소액·관련 기업)은 C
  for (const x of ks?.g2bAwards ?? []) {
    if (!(all || String(x.date ?? '') >= cutDay)) continue;
    const eokW = (v) => (v ? `약 ${Math.round(v / 1e8).toLocaleString('en-US')}억원` : '금액 미기재');
    push(x.big ? 'B' : 'C', W['kr-signals'], { kind: `나라장터 낙찰(${x.kind})`, id: x.id, date: x.date, company: [...(x.companies ?? []), ...(x.related ?? [])].join('·'),
      fact: `나라장터 ${x.kind} 낙찰: ${x.winner} · 「${x.title}」 · ${eokW(x.amount)} · 수요기관 ${x.buyer} · 공고 ${x.noticeNo} — 낙찰은 계약 체결이 아님`,
      check: x.big ? hint((x.companies ?? [])[0], ['수주', '납품'].filter(Boolean)) : undefined });
  }
  // 시·도 보도자료(울산·충남): 제목에 출입처 이름이면 B(지자체 발표 — 투자 규모는 회사 확인 전 지자체 주장), 투자·위기+업종 낱말만이면 C
  for (const x of ks?.province ?? []) {
    if (!(all || String(x.date ?? '') >= cutDay)) continue;
    const named = (x.companies ?? []).length;
    push(named ? 'B' : 'C', W['kr-signals'], { kind: `${x.site} 발표`, id: x.id, date: x.date, company: (x.companies ?? []).join('·') || x.site,
      fact: `${x.site} 보도자료${x.dept ? `(${x.dept})` : ''}: ${x.title}`, url: x.url, check: named ? hint(x.companies[0], [x.site.replace(/광역시|도$/, '')]) : undefined });
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
      const fresh = e.tier === 'B' && ktcNewDumping(e);
      const typeNote = ktcType(e) === '덤핑' && !/덤핑/.test(`${e.label} ${e.text}`) ? ' · 덤핑 조사(누리집 조사 유형 코드 — 상세 유형은 아직 비어 있음)' : '';
      push(fresh ? 'A' : e.tier === 'B' ? 'B' : 'C', W['trade-remedy'], { kind: fresh ? '무역위 새 반덤핑 조사' : KTC_KIND[e.ktcKind] ?? '무역위원회', id: e.id, date: e.detectedAt,
        company: e.product ?? '', fact: `${e.label}: ${e.text}${typeNote}`
          + (fresh ? ' — 국내 생산자가 신청해야 열리는 조사. 신청인 이름은 누리집에 없음: 출입처가 이 품목을 만드는지·신청했는지 회사 확인' : '')
          // 품목 낱말이 나온 출입처 사업보고서(11-11, scripts/ktc_producers.py) — 신청인 확인 질문을 누구에게 먼저 할지
          + (fresh && docs['trade-remedy']?.ktc?.producers?.[e.id]?.line ? ` · ${docs['trade-remedy'].ktc.producers[e.id].line}` : ''), url: e.url,
        // 보도 대조: 회사 이름이 없어 품목 이름으로(ktcHint). (11-05~11-08 이 자리에 안내 글자를 넣어 두었더니 보도 대조가
        // 힌트를 객체로 읽다 멈췄다 — radar_press_check.py AttributeError, 7회 연속 실패. 힌트는 hint()가 만든 객체이거나 undefined만)
        check: ktcHint(e) });
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
    if (e.pageId === 'edis') {
      // 미국 ITC 문서(EDIS): 한국산 청원·표지에 출입처가 든 337 제소장(A), 출입처 서면·지켜보는 337 결정·한국 조사 판정(B). 등급은 수집기.
      const firms = e.companies ?? [];
      const is337 = /^337-/.test(String(e.label).replace(/^USITC\s+/, ''));
      push(['A', 'B'].includes(e.tier) ? e.tier : 'C', W['trade-remedy'], { kind: is337 ? '미국 ITC 337(특허) 문서' : '미국 ITC 무역구제 문서', id: e.id, date: e.detectedAt,
        company: firms.join('·') || '미국 ITC', fact: `${e.label}: ${e.text}`, url: e.url,
        check: firms.length ? hint(firms[0], is337 ? ['ITC', '특허'] : ['ITC', '반덤핑']) : undefined });
      continue;
    }
    // repeats: 같은 줄이 목록 일련번호만 바뀌어 다시 잡힌 적 있음 → 이 첫 감지도 번호 이동일 수 있어 C(원문 개시일 확인)
    push(e.repeats ? 'C' : e.pageId === 'taric' && /한국 전용/.test(e.label) ? 'A' : 'B', W['trade-remedy'], { kind: e.pageId === 'taric' ? 'EU 쿼터(TARIC)' : `해외 조사 ${e.pageId}`, id: e.id, date: e.detectedAt, company: e.country,
      fact: `${e.label}: ${e.text}${e.repeats ? ` — 목록 일련번호만 바뀌어 ${e.repeats}번 다시 잡힌 줄이라 이 감지도 번호 이동일 수 있음(원문 개시일 확인)` : ''}`, url: e.url });
  }
  // 기사 준비(11-04): 레이더가 먼저 잡은 경쟁지 [단독] 5건 중 4건이 무역구제(철강금속신문) — 판정이 뜬 날 바로 쓸 수 있게
  // 다음 절차(미국 법정 기한)와 회사에 물을 것을 붙인다. 기한은 관보 게재일 기준 법정 기한이고, 관보 본문 날짜가 있으면 그 날짜가 우선.
  const tradeReady = (x) => {
    const t = String(x.title ?? '');
    const day = /^\d{4}-\d{2}-\d{2}/.test(String(x.date ?? '')) ? String(x.date).slice(0, 10) : null;
    if (!day) return {};
    const plus = (n) => new Date(Date.parse(`${day}T00:00:00Z`) + n * 86400000).toISOString().slice(5, 10);
    const review = /administrative review/i.test(t);
    const invest = /investigation|less[- ]than[- ]fair[- ]value|affirmative (?:preliminary|final) determination/i.test(t) && !review;
    if (x.stage === '예비 판정' && review) {
      return { next: `연례 재심 최종 판정은 예비 게재(${day.slice(5)})부터 120일 안(${plus(120)}까지, 최대 180일 ${plus(180)}로 연장 가능) — 최종에서 세율이 바뀔 수 있음 · 의견서(사건 요지서) 마감은 관보 본문 날짜 확인`,
        ask: '회사: 최종 판정 전 의견서 제출 계획 · 이 세율로 확정될 때 대미 수출 물량·가격 대응 · 미국 현지 생산 대응 여부' };
    }
    if (x.stage === '최종 판정' && review) {
      return { next: `미국 국제무역법원(CIT) 제소 기한은 게재(${day.slice(5)})부터 30일(${plus(30)}) · 확정 세율로 수입 정산 지시는 보통 게재 15일 뒤(${plus(15)} 무렵)`,
        ask: '회사: CIT 제소 여부(기한 안) · 확정 세율로 정산될 관세 규모(예치금 대비) · 다음 연례 재심 요청 여부' };
    }
    if (x.stage === '예비 판정' && invest) {
      return { next: `원심 최종 판정은 예비 게재(${day.slice(5)})부터 75일 안(${plus(75)}, 연기 시 135일 ${plus(135)}) → 그 뒤 ITC 최종 피해 판정`,
        ask: '회사: 예비 세율 현금 예치 영향 · 최종 판정 전 대응(검증 실사·의견서) · 대미 수출 계약 조정' };
    }
    if (x.stage === '최종 판정' && invest) {
      return { next: `ITC 최종 피해 판정은 상무부 최종(${day.slice(5)}) 뒤 보통 45일 안(${plus(45)} 무렵) — 긍정이면 부과 명령`,
        ask: '회사: ITC 최종 판정 대응 · 부과 시 대미 수출 계획 · CIT 제소 검토' };
    }
    return {};
  };
  const frBase = baselineOf(tr?.federalRegister ?? []);
  // ITC 고시에는 회사 이름이 거의 없다 — 같은 품목의 상무부 고시에 나온 출입처를 빌려 쓴다(유정용 강관 → 세아제강·현대제철)
  const byProduct = new Map();
  for (const y of tr?.federalRegister ?? []) {
    const n = (y.named ?? []).map((v) => v.company);
    if (n.length && !/International Trade Commission/.test(y.agency ?? '')) byProduct.set(productOf(y.title), [...new Set([...(byProduct.get(productOf(y.title)) ?? []), ...n])]);
  }
  for (const x of tr?.federalRegister ?? []) {
    if (!fresh(x, frBase, 'date')) continue;
    const itc = x.itcOutcome;
    if (itc?.korea && x.beatProduct) {
      // 한국산 철폐·종결·최종 부과는 A, 일몰 유지·예비 계속·섞임은 B(09-29 유정용 강관 일몰 재심: 한국산 반덤핑 유지)
      const linked = (x.named ?? []).map((n) => n.company);
      const who = linked.length ? linked : byProduct.get(productOf(x.title)) ?? [];
      const tierI = itc.korea === '부정' || (itc.korea === '긍정' && itc.phase === '최종') ? 'A' : 'B';
      push(tierI, W['trade-remedy'], { kind: '미국 ITC 피해 판정', id: x.id, date: x.date, company: who.join('·') || '한국산',
        fact: `미국 ITC ${itc.phase} 판정: ${x.title} — ${itcText(itc)}${who.length && !linked.length ? ` · 같은 품목 상무부 고시의 출입처: ${who.join('·')}` : ''} · 원문 "${String(itc.quote ?? '').slice(0, 200)}"`,
        url: x.url, check: hint(who[0], ['ITC', itc.korea === '부정' ? (itc.phase === '일몰 재심' ? '철폐' : '종결') : itc.phase === '일몰 재심' ? '유지' : '판정']) });
      continue;
    }
    const names = (x.named ?? []).map((n) => n.company);
    // An unusual topic in the decision-memo appendix of a notice naming a beat company is the story (10-09 열연 'Workplace Nursery' → 10-23 [단독]).
    const odd = names.length ? (x.memoUnusual ?? []) : [];
    const gl = odd.length ? memoGloss(odd[0]) : null;
    const memo = odd.length ? ` · 결정문 목차에 흔치 않은 항목(관보 부록 원문): "${String(odd[0]).slice(0, 160)}"${gl ? `(풀이: ${gl})` : ''}${odd.length > 1 ? ` 외 ${odd.length - 1}` : ''}`
      : (x.memoNamed ?? []).length ? ` · 결정문 목차에 출입처: "${String(x.memoNamed[0]).slice(0, 120)}"` : '';
    // 출입처 세율이 같은 사건 직전 판정보다 5%p 넘게 바뀌거나 0.5% 미만↔5% 이상(새 조사는 처음 5% 이상)이면 A(10-08 도금강판 0%→23.40% → 10-30 [단독])
    const changed = x.rateChange ?? [];
    const rates = names.length || changed.length ? rateText(x) : '';
    const kind = changed.length ? '미국 관보 세율 변화' : odd.length ? '미국 관보 결정문 목차' : '미국 관보';
    const who = changed.length ? changed.map((c) => c.company) : names;
    const frTier = odd.length || changed.length ? 'A' : names.length ? 'B' : 'C';
    push(frTier, W['trade-remedy'], { kind, id: x.id, date: x.date, company: [...new Set([...who, ...names])].join('·'),
      fact: `미국 관보 ${x.stage}: ${x.title}${changed.length ? ` — 세율 크게 바뀜: ${rateChangeText(x)}` : ''}${names.length ? ` — 본문에 ${names.join('·')}` : ''}${rates}${memo}`, url: x.url,
      ...(frTier === 'A' || (frTier === 'B' && x.rateTable) ? { ...tradeReady(x), point: tradePoint(x) || undefined } : {}),
      // 보도 대조는 품목 낱말까지(11-05 강관 최종이 '현대제철 관세' 일반 기사로 '관련 보도 있음'이 됐다) — 품목이 없는 기사는 약한 근거로만 남는다
      check: hint(who[0], ['관세', changed.length ? (x.rateTable?.kind === '상계관세' ? '상계관세' : '반덤핑') : odd.length ? '보조금' : '판정'], [], productKo(x.title)?.words ?? []) });
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

  // 미국 소비자 결함 신고 급증(리콜·조사 전 단계): 출입처 차종의 부품별 최근 28일 신고가 앞 24주 평균의 2.5배 넘게 튄 것 B,
  // 같은 부품 리콜이 60일 안에 있으면 C. 신고는 소비자가 낸 것이라 A로 올리지 않는다(수집기 nhtsa_complaints.py).
  for (const x of ur?.complaints?.spikes ?? []) {
    if (!x.active || !recent(x.firstSeen)) continue;
    const models = usRecallModels(x.model);
    const parts = (x.parts ?? []).map((p) => `${p.component} ${p.recent}건(평소 28일 ${p.baselinePer28})`).join(', ');
    const harm = [x.fire && `화재 ${x.fire}`, x.crash && `충돌 ${x.crash}`, x.injured && `부상 ${x.injured}`, x.deaths && `사망 ${x.deaths}`].filter(Boolean).join('·');
    const recall = (x.sameComponentRecall ?? []).length ? ` · 같은 부품 리콜 ${x.sameComponentRecall.join(',')} 뒤 신고일 수 있음` : '';
    push(x.tier ?? 'B', W['us-recalls'], { kind: '미국 결함 신고 급증', id: `${x.id}:${String(x.firstSeen).slice(0, 10)}`, date: x.firstSeen, company: x.brand,
      fact: `미국 소비자 결함 신고 급증 · ${x.brand} ${x.model}(연식 ${x.years}) · 최근 28일(${(x.window ?? []).join('~')}) 신고 ${x.complaints}건 · ${parts}${harm ? ` · ${harm}` : ''}${recall} — 소비자 신고라 결함 확정 아님, 국내 판매 차종 해당 여부는 회사 확인`,
      url: x.url, check: x.tier === 'C' ? undefined : (models.length ? hint(x.brand, [models[0], '리콜'], [models[0]], models) : hint(x.brand, ['리콜', '미국'])) });
  }

  // 미국 제조사 통신(nhtsa_tsbs.py, 캠페인 단위): 동력계통 보증 연장 A, 그 밖 보증 연장·서비스 캠페인·안전 낱말 통신 B, 나머지·재통지 C.
  // 딜러용 통신이라 리콜·결함 인정이 아니다 — 국내 무상수리 여부는 회사 확인.
  const tsItems = ur?.tsbs?.items ?? [];
  const tsBase = baselineOf(tsItems);
  for (const x of tsItems) {
    if (!fresh(x, tsBase, 'added')) continue;
    const modelText = (x.models ?? []).map((m) => m.model).join(', ');
    const models = usRecallModels(modelText);
    const brand = (x.brands ?? [])[0] ?? (x.companies ?? [])[0];
    const years = (x.models ?? []).flatMap((m) => m.years ?? []).sort();
    push(['A', 'B'].includes(x.tier) ? x.tier : 'C', W['us-recalls'], { kind: `미국 제조사 통신(${x.kindName ?? x.type})`, id: `tsb:${x.id}`, date: x.added,
      company: (x.companies ?? []).join('·'),
      fact: `미국 NHTSA 제조사 통신 ${x.kindName ?? x.type} · 추가 ${x.added} · ${(x.brands ?? []).join('·')} ${(x.models ?? []).slice(0, 4).map((m) => m.model).join(', ')}${x.modelCount > 4 ? ` 외 ${x.modelCount - 4}개` : ''}`
        + `${years.length ? `(${years[0]}${years.length > 1 && years[years.length - 1] !== years[0] ? `~${years[years.length - 1]}` : ''}년형)` : ''} · ${x.campaign ? `캠페인 ${x.campaign} · ` : ''}문서 ${x.docCount > 1 ? `${x.docCount}건` : x.doc} · 「${clipAt(x.summary ?? '', 160)}」`
        + ' — 딜러용 통신이라 리콜·결함 인정 아님, 국내 무상수리 해당 여부는 회사 확인',
      url: x.url, check: x.tier === 'C' ? undefined : (models.length ? hint(brand, [models[0], '무상수리'], [models[0]], models) : hint(brand, ['무상수리', '미국'])) });
  }

  // 출입처 외신(global_collector.py): 한국어 제목에 사건 낱말(공장·투자·수주·원자로 등)이 있으면 B(자동 보도 대조), 없으면 참고(C).
  // 첫 수집에 잡힌 기존 기사는 자기 게재일이 최근일 때만(fresh). AI 번역·요약 — 원문 확인.
  // 한국어 제목의 나라 이름은 검색을 좁히고 기사 본문에 있어야 같은 건으로 센다(11-02 운영: KHNP '체코 원전 컨소시엄 협상 종료' 외신이
  // "두산에너빌리티 원자로"로 대조돼 뉴스케일 SMR 계약 기사로 '관련 보도 있음'). 美·中·日처럼 제목에서 한 글자로 줄이는 나라는 쓰지 않는다.
  // 미국은 주 이름을 쓴다 — 국내 기사도 '美 앨라배마'처럼 주 이름을 그대로 적는다(11-03 운영: WardsAuto '현대차 앨라배마 4억5천만 달러 투자'가
  // "현대차 투자"로 대조돼 새만금 기사로 '관련 보도 있음'). '인도량'(차량 인도)은 나라가 아니다.
  const GB_COUNTRY = /체코|폴란드|루마니아|불가리아|헝가리|슬로바키아|멕시코|캐나다|브라질|칠레|페루|아르헨티나|콜롬비아|튀르키예|이집트|카타르|쿠웨이트|오만|사우디|아랍에미리트|이라크|요르단|모로코|남아공|필리핀|태국|말레이시아|베트남|싱가포르|인도네시아|인도(?!량|분)|대만|몽골|호주|뉴질랜드|우즈베키스탄|카자흐스탄|네덜란드|스웨덴|노르웨이|핀란드|덴마크|스페인|포르투갈|이탈리아|그리스|아일랜드|독일|영국|프랑스|오스트리아|벨기에|스위스|앨라배마|조지아|텍사스|테네시|사우스캐롤라이나|노스캐롤라이나|미시간|오하이오|켄터키|인디애나|애리조나|루이지애나|캘리포니아|일리노이|펜실베이니아|버지니아|뉴저지|네바다|미시시피|오클라호마|캔자스|위스콘신|미네소타|아이오와|유타|콜로라도|온타리오|퀘벡|누에보레온/;
  const gbItems = docs['global-beat']?.items ?? [];
  const gbFx = docs['global-beat']?.fx;
  // 예전 문서(원/달러 하나: {rate, date})와 지금 문서({rates: {달러: {rate, date, label, per}}}) 둘 다 읽는다
  const gbRates = gbFx?.rates ?? (gbFx?.rate ? { 달러: { rate: gbFx.rate, date: gbFx.date, label: '원/달러' } } : {});
  const gbKrw = (krw) => {
    if (!Array.isArray(krw) || !krw.length) return '';
    const used = [...new Set(krw.map((k) => k.cur ?? '달러'))].filter((c) => gbRates[c]);
    if (!used.length) return '';
    const label = used.map((c) => `${gbRates[c].label ?? `원/${c}`} ${Number(gbRates[c].rate).toLocaleString('en-US')}(${gbRates[c].date ?? '?'})`).join(' · ');
    return ` · 원화 환산(자동, 한국은행 매매기준율 ${label}): ${krw.filter((k) => gbRates[k.cur ?? '달러']).map((k) => `${k.amount ?? k.usd}(${k.krw})`).join(', ')}`;
  };
  const gbBase = baselineOf(gbItems);
  for (const x of gbItems) {
    if (!fresh(x, gbBase, 'published')) continue;
    const companies = x.beatCompanies ?? [];
    // 본문 첫머리 주체가 계열사(global_collector.affiliate_lead) — 참고(C)로 내리고 보도 대조도 하지 않는다(11-03 운영: 포스코퓨처엠 계약이 '포스코' B)
    const affiliate = (x.affiliateLead ?? []).filter(Boolean);
    // 출입처 이름이 영어 제목에도 한국어 제목에도 없고 본문(RSS 발췌)에만 있으면 다른 회사 기사일 수 있다 — 참고(C), 대조 안 함
    // (11-10 운영: Automotive News '혼다, 오하이오 조립 공장' 외신이 본문의 Hyundai 언급으로 '현대차' B·"현대차 공장 오하이오" 대조).
    // titleCompanies가 없는 예전 항목은 그대로 둔다.
    const bodyOnly = Array.isArray(x.titleCompanies) && companies.length
      && !companies.some((c) => x.titleCompanies.includes(c) || String(x.koTitle ?? '').includes(c));
    // 보도 대조·표시의 주체는 제목에 나온 출입처를 먼저(한국어 제목에서 앞에 나온 순). 출입처 목록 순서(현대차가 기아보다 앞)를 쓰면
    // 11-10 운영: Just Auto 「기아, 광주에 새 전기차 공장」이 "현대차 공장"으로 대조돼 '미보도 후보'가 떴다.
    const ko = String(x.koTitle ?? '');
    const at = (c) => (ko.includes(c) ? ko.indexOf(c) : (x.titleCompanies ?? []).includes(c) ? 5000 : 9999);
    const ordered = [...companies].sort((a, b) => at(a) - at(b));
    const terms = affiliate.length || bodyOnly ? [] : (x.checkTerms ?? []).slice(0, 2);
    push(terms.length ? 'B' : 'C', W['global-beat'], { kind: '출입처 외신', id: x.id, date: x.published, company: ordered.join('·'),
      fact: (affiliate.length ? `⚠ 본문 첫머리 주체가 계열사(${affiliate.join('·')}) — 출입처 외일 수 있음 · ` : '')
        + (bodyOnly ? `⚠ 출입처 이름(${companies.join('·')})이 제목엔 없고 본문에만 — 다른 회사 기사일 수 있음 · ` : '')
        + `외신 ${x.source ?? ''} 「${x.koTitle || x.title}」${x.koSummary ? ` — ${clipAt(x.koSummary, 220)}` : ''} · 원제 "${clipAt(x.title ?? '', 140)}" (AI 번역·요약 — 원문 확인)`
        // AI가 받은 영어(제목·RSS 발췌)에서 같은 값을 못 찾은 숫자 — 지어냈거나 환산했거나 표기가 달라 못 맞춘 것(global_news_pipeline.check_numbers)
        + (Array.isArray(x.numbersNotInSource) && x.numbersNotInSource.length ? ` · ⚠ 원문 발췌에 없는 숫자: ${x.numbersNotInSource.slice(0, 4).join(', ')} — 기사에 쓰기 전 원문 대조` : '')
        // 외화 금액의 원화(11-11): 한국은행 매매기준율로 코드가 계산(달러·유로·엔·파운드·위안). 기사에 쓸 땐 작성일 환율로 다시
        + gbKrw(x.krw),
      url: x.url, check: terms.length && companies.length ? gbHint(ordered[0], terms, (GB_COUNTRY.exec(String(x.koTitle ?? '')) ?? [])[0], x.published, x.koTitle) : undefined });
  }

  // US OSHA: new inspection (fatality/accident A, complaint/referral B), new citations (willful/repeat or $100k+ A, serious B), fatal accident summary A.
  for (const e of docs['us-osha']?.events ?? []) {
    if (!recent(e.detectedAt)) continue;
    push(['A', 'B'].includes(e.tier) ? e.tier : 'C', W['us-osha'], { kind: `미국 OSHA ${e.kind}`, id: e.id, date: e.detectedAt, company: e.company,
      fact: `${e.text} — 점검·통지는 회사 책임 확정 아님(이의 제기 가능)`, url: e.url,
      check: e.tier === 'C' ? undefined : hint(e.company, ['OSHA', e.kind === '위반 통지' ? '벌금' : '사고']) });
  }

  // US EPA certification file: a model new to the company is A, an EV range change B, model-year carryover C.
  // 미국 주 환경청 허가·공고: 신설·증설 낱말이 든 허가 신청 A, 나머지 허가 공고·제재 공고 B(첫 실행 기준선은 이벤트 없음)
  for (const e of docs['us-state-env']?.events ?? []) {
    if (!recent(e.detectedAt)) continue;
    push(['A', 'B'].includes(e.tier) ? e.tier : 'C', W['us-state-env'], { kind: e.kind, id: e.id, date: e.detectedAt, company: e.company,
      fact: e.text, url: e.url, check: hint(e.company, [e.state, /제재/.test(e.kind ?? '') ? '과징금' : /상공위원회/.test(e.kind ?? '') ? '감면' : '허가'], [e.state], [e.state]) });
  }

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
    else if (x.signer) tier = 'B';  // 계약 서명란의 당사자(11-01: Forge Nano 등록권 계약의 LG CHEM FUND I LLC) — 계약 종류는 원문으로
    else if (oldDealOf(x)) tier = 'B';   // 발췌의 거래 날짜가 공시일보다 45일 넘게 오래됨 — 이미 있던 거래 서술(11-04)
    else if (x.source === 'EDGAR' && PERIODIC.test(String(x.title ?? '')) && !snippetDates(x.snippet).length) tier = 'B';   // 날짜 없는 정기 보고서 서술
    else tier = (x.dealNear ?? DEAL_WORDS.test(String(x.snippet ?? ''))) && !x.finNote ? 'A' : 'B';
    const old = tier === 'B' && !LITIGATION.test(String(x.snippet ?? '')) ? oldDealOf(x) : null;   // 소송 문단은 절차 서술로 따로 적는다
    const deal = x.routine ? ` — ${x.routine}` : x.source === 'ASX' || x.source === 'HKEX' ? '' : x.hearsay ? ` — ${x.hearsay}` : x.boilerplate ? ` — ${x.boilerplate}` : x.signer ? ` — ${x.signer}` : x.finNote ? ` — ${x.finNote}`
      : old ? ` — 발췌의 거래 날짜 ${old}(공시일보다 ${OLD_DEAL_DAYS}일 넘게 전) — 이미 있던 거래를 다시 적은 것일 수 있음`
      : tier === 'B' && x.source === 'EDGAR' && PERIODIC.test(String(x.title ?? '')) && !snippetDates(x.snippet).length ? ' — 정기 보고서 속 서술(날짜 없음 — 새 내용인지 원문 확인)'
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
    const value = x.value ? ` · ${money(x.value)}${x.valueOcr ? '(글자 인식 값)' : ''}` : ' · 금액 미기재';
    const where = countryKo(x.buyerCountry);
    if (x.bidder) {  // 개찰(응찰가 공개) — 낙찰 아님
      const rank = x.rank ? `응찰가 ${x.rank}위/${x.priced}곳${x.lowest ? '(최저가)' : x.lowestBid ? ` · 최저 ${x.lowestBid.name} ${money(x.lowestBid.value)}` : ''}` : '응찰가 순위 없음(가격 미공개·탈락)';
      push(tier, W['overseas-awards'], { kind: `${x.source} ${x.kind}`, id: x.id, date: x.published ?? x.firstSeen, company: x.company ?? '',
        fact: `해외 개찰(${x.source}): ${where ? `${where} ` : ''}${x.buyer} · ${String(x.title ?? '').slice(0, 120)} — ${x.bidder}${x.value ? ` ${money(x.value)}` : ' 응찰가 미공개'} · ${rank} · 개찰 ${x.published ?? '?'} · 낙찰 아님`,
        url: x.url, check: tier === 'C' ? undefined : hint(x.company, [where, '입찰'], [where], [where]) });
      continue;
    }
    const more = (x.winnerCount ?? (x.winners ?? []).length) - Math.min(2, (x.winners ?? []).length);
    // 바레인 월간 보고서 줄은 낙찰자 칸이 따로 없다 — 이름이 맞은 출입처로 적고, 공고일 대신 보고서 달(낙찰 결정 달)
    const who = ((x.winners ?? []).slice(0, 2).join('·') + (more > 0 ? ` 외 ${more}곳` : '')) || (x.company ? `${x.company}(보고서 줄${x.ocr ? ', 글자 인식' : ''})` : '보고서 줄 참조');
    const buyer = where && String(x.buyer ?? '').startsWith(where) ? String(x.buyer).slice(where.length).trim() : x.buyer;
    push(tier, W['overseas-awards'], { kind: `${x.source} ${x.kind}`, id: x.id, date: x.published ?? x.firstSeen, company: x.company ?? '',
      fact: `해외 ${x.kind}(${x.source}): ${where ? `${where} ` : ''}${buyer} ← ${who} · ${String(x.title ?? '').slice(0, x.ocr ? 220 : 120)}${value}${x.concluded ? ` · 계약 ${x.concluded}` : ''} · ${x.published ? `공고 ${x.published}` : x.reportMonth ? `${x.reportMonth} 월간 낙찰 보고서` : '공고 ?'}`,
      // 월간 보고서 줄은 낙찰 결정 달이 기준 — 보도 대조는 그 달부터 본다(11-02: 8월 보고서 일진전기 낙찰을 11-02부터 찾아 10-20 더구루 [단독]을
      // '앞선 기사'로 두고 미보도 후보라 했다)
      // 나라 이름이 기사에 있어야 같은 건(11-02 12:55: 바레인 낙찰 줄이 '일진전기 2분기 영업익…해외수주'·'영국 해상풍력 추가 수주'로 '관련 보도 있음')
      url: x.url, check: tier === 'C' ? undefined : sinceMonth(hint(x.company, [where, '수주'], [where], [where]), x.reportMonth) });
  }

  // Court insolvency notices (대법원 회생·파산 공고, 회생회사 M&A 공고): a beat-industry manufacturer (공장등록 업종) entering
  // proceedings is A, a related industry with a beat product word or a 폐지 B, other related industries and name words only C. A court notice is a procedure, not a supply effect.
  const ins = docs['kr-insolvency'];
  const insBase = baselineOf(ins?.events ?? []);
  for (const e of ins?.events ?? []) {
    if (!fresh(e, insBase, 'posted')) continue;
    push(e.tier ?? 'C', W['kr-insolvency'], { kind: e.kind, id: e.id, date: e.posted ?? e.firstSeen, company: e.company,
      fact: `${e.kind}: ${insolvencyLine(e)} · 공고 ${e.posted ?? '?'} — 거래 관계·납품 영향 미확인`, url: e.url ?? e.listUrl,
      check: e.tier === 'C' ? undefined : hint(firmName(e.company), [insolvencyWord(e.kind)]) });
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
    if (x.baseline || x.routine || !recent(x.firstSeen)) continue;  // routine: 이름 없는 일상 행정(수집기 표시)
    // 상세 페이지를 읽었으면 전체 제목·본문 앞부분(목록 제목은 '...'로 잘린다 — 10-31 울주 '#2ASU O...' → 'O2 COMPRESSOR ROOM 토건공사')
    const d = x.detail;
    const title = d?.title ?? x.title;
    // 첨부 공고문에서 뽑은 사업 개요가 있으면 본문 앞부분 대신(공사기간·시공자·규모가 본문보다 쓸모 있다 — 11-02 울주 고려아연 #2ASU)
    const outline = attachmentOutline(x, ['공사기간', '착공일', '발주자/시공자', '시공자', '규모', '공사비']);
    const body = outline ? ` · 첨부 개요: ${outline}` : d?.body ? ` · 본문: ${String(d.body).slice(0, 140)}${String(d.body).length > 140 ? '…' : ''}` : '';
    const scope = outline ? '제목·본문·첨부 개요 자동 추출(첨부 원문·회사 확인)' : d ? '제목·본문 앞부분 확인(첨부 원문·규모는 지자체·회사 확인)' : '제목만 확인(첨부 원문·규모는 지자체·회사 확인)';
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

  // 노동위 회의 ↔ 노조 게시판 같은 회사 7일 안(11-04): 조정 신청과 노조 성명(파업·교섭 결렬)은 한 사건의 두 면이다 — 한 줄로 이어 보여 준다
  const WEEK = 7 * 86400000;
  const near = (list, company, at, dateOf) => (list ?? []).filter((y) => (y.company === company || (y.companies ?? []).includes(company))
    && Math.abs(Date.parse(dateOf(y)) - Date.parse(at)) <= WEEK);
  // 노조 글은 회사 이름이 제목에 든 것만(본문에만 이름이 있는 글은 다른 회사 이야기일 때가 많다), 날짜는 글 작성일(없으면 처음 본 때)
  const unionPosts = (docs['union-notices']?.posts ?? []).filter((y) => y.inTitle !== false);
  const laborNotices = docs['kr-labor']?.notices ?? [];
  const postDay = (y) => y.date ?? y.firstSeen;
  const meetingDay = (y) => `${y.day}T09:00:00+09:00`;
  // 노동위 조정 회의 다음 날 결과 확인(11-04): 조정 중지(쟁의권 확보)·성립·연장은 공개 일정에 나오지 않는다. A 조정 회의가 끝난 다음 날
  // 09시 날짜로 B를 다시 올려 자동 보도 대조(회의일 이후 기사만)에 태운다. '미보도 후보'면 결과를 노사에 물을 차례. 원래 항목을 킬했으면 안 올린다(parent).
  const todayKst = kstDate(now);
  for (const n of laborNotices) {
    if (!mediationPast(n, todayKst)) continue;
    const next = new Date(Date.parse(`${n.day}T09:00:00+09:00`) + 86400000);
    if (!Number.isFinite(next.getTime()) || !recent(next.toISOString())) continue;
    push('B', W['kr-labor'], { kind: '노동위 조정 결과 확인', id: `${n.id}:result`, parent: n.id, date: next.toISOString(), company: n.company,
      fact: `${n.commissionName ?? ''} ${n.meeting ?? ''} ${n.day} ${n.time ?? ''} 회의 지남 · 사건 ${n.caseNo} 「${n.caseName}」 — 조정 중지(쟁의권)·성립·연장 결과는 공개 일정에 나오지 않음. 회의일 이후 보도 대조가 '미보도 후보'면 노사에 결과 확인`,
      url: n.url, check: { ...hint(n.company, ['조정 결과']), after: n.day } });
  }
  // 노동위 회의: 출입처가 사건명 앞 당사자인 오늘 회의 — 노동쟁의 조정·교섭·부당노동행위 A, 그 밖의 구제신청(해고·징계 등) B
  for (const e of docs['kr-labor']?.events ?? []) {
    if (!recent(e.detectedAt)) continue;
    const day = /:(\d{4}-\d{2}-\d{2})$/.exec(String(e.id))?.[1];   // id 끝이 회의 날짜 — 노조 글은 회의 날짜 앞뒤 7일
    const posts = near(unionPosts, e.company, day ? `${day}T09:00:00+09:00` : e.detectedAt, postDay).slice(0, 2);
    const link = posts.length ? ` · 노조 게시판 같은 회사 글(7일 안): ${posts.map((y) => `「${String(y.title).slice(0, 50)}」(${y.board ?? ''} ${String(y.date ?? '').slice(5, 10)})`).join(' / ')}` : '';
    push(['A', 'B'].includes(e.tier) ? e.tier : 'C', W['kr-labor'], { kind: e.kind, id: e.id, date: e.detectedAt, company: e.company,
      fact: `${e.text}${link}`, url: e.url, check: hint(e.company, [e.word || '노동위']) });
  }

  // 지분·자사주 변동(11-04): 기자 기사 「주주가치 높인다며 산 자사주…KG스틸, 임직원 보상에 쓴다」(10-24)는 10-15 처분 결정과 10-23 임원 15명
  // 같은 날 보고로 쓸 수 있었다. 임원 집단 보고(같은 날 5명 이상)·일상 아닌 자사주 처분 결정만 B(공개 공시 — 각도는 기자가 만든다)
  for (const x of docs.governance?.items ?? []) {
    if (x.routine || !['임원 집단 보고', '자사주 처분 결정'].includes(x.kind) || !fresh(x, null, 'date')) continue;
    const treasury = x.kind === '자사주 처분 결정';
    push('B', W.governance, { kind: x.kind, id: x.groupKey ?? `treasury:${x.receiptNo}`, date: x.date, company: x.company, url: x.url ?? undefined,
      fact: treasury ? `${x.company} 자기주식 처분 결정 — ${x.reason}${x.period && x.period !== '~' ? ` · 처분 기간 ${x.period}` : ''} ${(x.tags ?? []).join(' ')}`
        : `${x.company} ${x.reporter} 같은 날 지분 보고 — ${x.reason} ${(x.tags ?? []).join(' ')}`,
      check: hint(x.company, [treasury ? '자사주' : '임원']) });
  }

  // 임원 명단 변화(kr-exec): A·B만. 공개 정기보고서지만 '새로 보임'은 두 기준일 사이 변화일 뿐 — 선임일·영입 경위는 회사 확인
  for (const e of docs['kr-exec']?.events ?? []) {
    if (!['A', 'B'].includes(e.tier) || !recent(e.detectedAt)) continue;
    const name = String(e.person?.name ?? '').trim();
    const flags = (e.flags ?? []).map((f) => f.text).filter(Boolean).join(' / ');
    push(e.tier, W['kr-exec'], { kind: `임원 ${e.kind}`, id: e.id, date: e.detectedAt, company: e.company, url: e.url ?? undefined,
      fact: `${e.text}${flags ? ` 〔표시: ${flags}〕` : ''} (보고서 명단 비교 — 선임일·영입 경위·사유는 회사 확인)`,
      check: name ? hint(e.company, [name, '인사'], [], [name]) : hint(e.company, ['인사', '감원']) });
  }

  // 수시 임원 공시·타사 임원 명단(kr-exec-market): A·B만. 회사는 공시 낸 회사(타사면 그 회사) — 기사엔 그 사람 이름이 있어야 같은 건
  for (const e of docs['kr-exec-market']?.events ?? []) {
    if (!['A', 'B'].includes(e.tier) || !recent(e.detectedAt) || e.baseline) continue;   // 지난 소집공고 되짚기 후보는 기준선
    const name = String(e.person?.name ?? '').trim();
    const flags = (e.flags ?? []).map((f) => f.text).filter(Boolean).join(' / ');
    push(e.tier, W['kr-exec-market'], { kind: `${e.source ?? '임원 공시'} · ${e.kind}`, id: e.id, date: e.detectedAt, company: e.company, url: e.url ?? undefined,
      fact: `${e.text}${flags ? ` 〔표시: ${flags}〕` : ''}${e.source === '임원 현황' ? ' (보고서 명단 비교 — 선임일·경위는 회사 확인)' : ''}`,
      check: name ? hint(e.company, [name, '인사'], [], [name]) : hint(e.company, ['인사']) });
  }

  // 문제 임원 점검(kr-exec-check): A·B. 법정 한도는 '사외이사', 과거 논란은 '논란' 낱말과 그 사람 이름으로 보도 대조
  for (const e of docs['kr-exec-check']?.events ?? []) {
    if (e.kind === '과거 논란 기사' && !(e.flags ?? []).some((f) => f.evidenceVersion === 'executive_article/v1')) continue;
    if (e.reviewStatus !== 'active') continue; // 과거 오탐·재검색 실패·구버전 미검증 기록은 알림으로 재노출하지 않음
    if (!['A', 'B'].includes(e.tier) || e.baseline || !recent(e.detectedAt)) continue;   // 첫 실행 표시는 kr_signals 목록으로만
    const name = String(e.person?.name ?? '').trim();
    const word = /논란 기사/.test(e.kind) ? '논란' : /공식 제재/.test(e.kind) ? '제재' : '사외이사';
    push(e.tier, W['kr-exec-check'], { kind: e.kind, id: e.id, date: e.detectedAt, company: e.company, url: e.url ?? undefined,
      fact: `${e.text} (확인할 단서 — 결격·비위 단정 아님, 회사·당사자 확인)`,
      check: name ? hint(e.company, [name, word], [], [name]) : hint(e.company, [word]) });
  }

  // 지방의회 회의록: 출입처 이름 대목에 인허가·불법·위반·오염·민원·특혜·감면·증설·이전·폐쇄·야적 낱말 A(그 밖은 저장만). 의원 질의는 주장
  for (const e of docs['council-minutes']?.events ?? []) {
    if (!recent(e.detectedAt)) continue;
    const t = String(e.text ?? '');
    const word = /야적|불법|위반|행정처분/.test(t) ? '불법' : /오염|유출|악취/.test(t) ? '오염' : /감면|보조금|특혜|지방세|체납/.test(t) ? '감면'
      : /증설|신설/.test(t) ? '증설' : /이전|폐쇄|철수/.test(t) ? '폐쇄' : '의회';
    const council = String(e.council ?? '').replace(/의회$/, '');
    push(['A', 'B'].includes(e.tier) ? e.tier : 'C', W['council-minutes'], { kind: e.kind ?? '지방의회 회의록', id: e.id, date: e.detectedAt, company: e.company,
      fact: e.text, url: e.url ?? undefined, check: hint(e.company, [word], [], council ? [council] : []) });
  }

  // 노조 성명·보도자료: 사망·사고·파업·매각·분할·가처분 등 A, 그 밖 B(이름이 본문에만 있으면 한 단계 내림). 노조 발표는 한쪽 주장
  for (const e of docs['union-notices']?.events ?? []) {
    if (!recent(e.detectedAt)) continue;
    const t = String(e.title ?? '');
    const word = /사망|숨|중대재해|끼임|추락|폭발|화재|사고/.test(t) ? '사고' : /파업|쟁의|결렬/.test(t) ? '파업' : /매각|분할/.test(t) ? '인수'
      : /구조조정|희망퇴직|해고/.test(t) ? '감원' : /가처분|고발|고소/.test(t) ? '고발' : /교섭/.test(t) ? '교섭' : '노조';
    const own = unionPosts.find((y) => y.id === e.id);
    const cases = near(laborNotices, e.company, own ? postDay(own) : e.detectedAt, meetingDay).slice(0, 2);
    const link = cases.length ? ` · 노동위 같은 회사 회의(7일 안): ${cases.map((y) => `${y.commissionName ?? ''} ${String(y.day).slice(5)} ${y.caseNo} 「${String(y.caseName).slice(0, 40)}」`).join(' / ')}` : '';
    push(['A', 'B'].includes(e.tier) ? e.tier : 'C', W['union-notices'], { kind: e.kind ?? '노조 성명·보도자료', id: e.id, date: e.detectedAt, company: e.company,
      fact: `${e.text}${link}`, url: e.url, check: hint(e.company, [word]) });
  }

  // 타사 공시 속 출입처: 자산·영업·지분 거래 상대·공급계약 해지 A, 공급계약 500억원 이상 A·그 밖 B, 생산중단·투자판단 B. 기사엔 상대 회사 이름이 있어야 같은 건
  for (const e of docs['dart-counterparty']?.events ?? []) {
    if (!recent(e.detectedAt)) continue;
    const rep = String(e.report ?? '');
    const word = /해지/.test(rep) ? '해지' : /생산중단/.test(rep) ? '감산' : /공급계약|단일판매/.test(rep) ? '공급' : /합병/.test(rep) ? '합병'
      : /분할/.test(rep) ? '분할' : /양수|양도|영업|취득|처분/.test(rep) ? '인수' : '거래';
    const filer = String(e.filer ?? '').replace(/주식회사|㈜|\(주\)/g, '').trim();
    push(['A', 'B'].includes(e.tier) ? e.tier : 'C', W['dart-counterparty'], { kind: e.kind ?? '타사 공시', id: e.id, date: e.detectedAt, company: e.company,
      fact: e.text, url: e.url, check: hint(e.company, [word], [], filer ? [filer] : []) });
  }

  // 인도 법인 공시(NSE): 현대차 인도법인 — 인수·설비·로열티 A, 이사회 결과·보도자료·임원 변경 B. 기사 제목엔 '인도'가 있어야 같은 건
  for (const e of docs['india-filings']?.events ?? []) {
    if (!recent(e.detectedAt)) continue;
    const subj = `${e.subject ?? ''} ${e.text ?? ''}`;   // 종류(Updates 등)만으로는 모자라 설명 문장까지 본다
    const word = /acqui|amalgamat|merger/i.test(subj) ? '인수' : /plant|capacity|expansion|capex|capital expenditure/i.test(subj) ? '공장'
      : /board meeting/i.test(subj) ? '이사회' : /director|management|key managerial|kmp|appoint|resign/i.test(subj) ? '선임'
        : /rating/i.test(subj) ? '신용등급' : /royalt|related party/i.test(subj) ? '로열티' : '인도법인';
    push(['A', 'B'].includes(e.tier) ? e.tier : 'C', W['india-filings'], { kind: e.kind ?? '인도 법인 공시', id: e.id, date: e.detectedAt, company: e.company,
      fact: e.text, url: e.url, check: hint(e.company, ['인도', word], [], ['인도']) });
  }

  // 굴뚝 자동측정(TMS): 사업장 가동 중단 신호·(14일 넘게 지켜본 뒤의) 새 배출구·새 사업장 A, 배출구 멈춤·목록에서 빠짐·재가동 B. 측정값만으로는 정지·정비·점검을 가르지 못한다.
  for (const e of docs['kr-stacks']?.events ?? []) {
    if (!recent(e.detectedAt)) continue;
    // 예전 이름('보수·가동중지 전환·해제', 11-03 11:45 첫 읽기 17개 사업장 B)은 C. 새 이름('가동중지 전환·해제')은 굴뚝 감시가 정한 등급 그대로
    const m = maintFolded(e, maint);
    const tier = m || /보수·가동중지 (전환|해제)/.test(e.kind ?? '') ? 'C' : e.tier ?? 'B';
    push(tier, W['kr-stacks'], { kind: e.kind, id: e.id, date: e.detectedAt, company: e.company, site: e.site,
      fact: m ? `${e.text} · ⓘ 기자 판정(${kstMD(m.at)} '${m.reason}') — ${kstMD(m.until)}까지 이 사업장 멈춤·빠짐 신호는 접음` : e.text,
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
  // 유럽 상표 출원(EUIPO, 같은 주 1회 실행의 'eu' 칸): 처음 보는 이름+업종 핵심 상품류 B, 그 밖의 새 출원 C.
  for (const f of docs.trademarks?.eu?.filings ?? []) {
    if (!f.isNew) continue;
    if (!all && !(Date.parse(f.firstSeen) >= Math.min(cut, now - 7 * 86400000))) continue;
    push(f.tier === 'B' ? 'B' : 'C', W.trademarks, { kind: f.titleNew ? '유럽 상표 새 이름' : '유럽 상표 출원', id: f.id, date: f.applicationDate, company: f.company,
      fact: `유럽연합(EUIPO) 상표 출원 「${f.title}」 ${(f.classes ?? []).map(classLabel).join(', ')}${f.titleNew ? ' — 감시 시작 이후 처음 보는 이름' : ''} (출원 ${f.applicationDate || '?'}${f.route ? `(${f.route})` : ''}, 출원번호 ${f.applicationNumber}, 출원인 ${(f.applicants ?? [])[0] ?? '?'})${f.via === 'signa' ? ' · Signa 2차 자료 — EUIPO eSearch 원문 확인' : ''}`,
      url: f.url, check: hint(f.company, ['상표', f.title]) });
  }

  // 미국 상표 출원(USPTO, Signa 경유 — 11-09, 같은 실행의 'us' 칸): 유럽과 같은 등급
  for (const f of docs.trademarks?.us?.filings ?? []) {
    if (!f.isNew) continue;
    if (!all && !(Date.parse(f.firstSeen) >= Math.min(cut, now - 7 * 86400000))) continue;
    push(f.tier === 'B' ? 'B' : 'C', W.trademarks, { kind: f.titleNew ? '미국 상표 새 이름' : '미국 상표 출원', id: f.id, date: f.applicationDate, company: f.company,
      fact: `미국(USPTO) 상표 출원 「${f.title}」 ${(f.classes ?? []).map(classLabel).join(', ')}${f.titleNew ? ' — 감시 시작 이후 처음 보는 이름' : ''} (출원 ${f.applicationDate || '?'}${f.route ? `(${f.route})` : ''}, 일련번호 ${f.applicationNumber}, 출원인 ${(f.applicants ?? [])[0] ?? '?'}) · Signa 2차 자료 — USPTO TSDR 원문 확인`,
      url: f.url, check: hint(f.company, ['상표', f.title]) });
  }

  // 해외 특허 공개(EPO OPS, 주 1회 토요일): 새로 본 EP·WO 공개는 참고(C) — 공개는 출원 약 18개월 뒤라 개발 완료·양산이 아니다.
  // 같은 패밀리(EP와 WO)는 한 줄. 보도 대조는 하지 않는다(기술 낱말이 영문 제목뿐이라 네이버 대조가 맞지 않음 — patents_abroad에서 직접).
  const epoFam = new Map();
  for (const f of docs['epo-patents']?.filings ?? []) {
    if (!f.isNew) continue;
    if (!all && !(Date.parse(f.firstSeen) >= Math.min(cut, now - 7 * 86400000))) continue;
    const famKey = f.family ? `fam:${f.family}` : f.id;
    if (!epoFam.has(famKey)) epoFam.set(famKey, []);
    epoFam.get(famKey).push(f);
  }
  for (const group of epoFam.values()) {
    // 11-10: 같은 패밀리(EP·WO)는 한 줄 — 국내 공개(KIPRIS 감시)와 이어진 쪽을 대표로, 한글 제목을 앞에.
    // '처음 보는 기술 분야'(이력 180일 뒤부터)는 확인할 변화(B), 나머지는 참고(C)
    const f = group.find((g) => g.kr) ?? group.find((g) => g.newField) ?? group[0];
    const kr = group.find((g) => g.kr)?.kr;
    const krp = group.find((g) => g.krPriority)?.krPriority;
    const abroad = group.find((g) => g.priorityAbroad)?.priorityAbroad;
    const krPct = group.find((g) => g.krPct)?.krPct;
    const pct = group.find((g) => g.pctPriority)?.pctPriority;
    const nfm = group.find((g) => g.newField)?.newField;
    const nf = nfm ? Object.entries(nfm).map(([c, v]) => `${c} ${v.join('·')}`).join(', ') : '';
    const pr = f.priorities ?? (f.priority ? [f.priority] : []);
    const ids = group.map((g) => g.id).join('·');
    push(nf ? 'B' : 'C', W['epo-patents'], { kind: `${f.country === 'WO' ? '국제특허(PCT) 공개' : '유럽특허 공개'}${nf ? '(처음 보는 기술 분야)' : ''}`, id: `epo:${f.id}`, date: f.date, company: (f.companies ?? []).join('·'),
      fact: `${f.country === 'WO' ? '국제특허(PCT·WO)' : '유럽특허(EP)'} 공개 ${kr?.title ? `「${kr.title}」(영문 「${f.title ?? '?'}」)` : `「${f.title ?? '제목 없음'}」`} (공개 ${f.date ?? '?'}, ${ids}${(f.ipc ?? []).length ? `, IPC ${f.ipc.slice(0, 2).join('·')}` : ''}`
        + `${kr ? `, 국내 공개 ${kr.publicationNumber ?? kr.applicationNumber}(${kr.publicationDate ?? '?'})` : krp ? `, 국내 우선권 출원 ${krp}` : krPct ? `, 우선권 한국 특허청 PCT ${krPct}` : pct ? `, 우선권 PCT ${pct[0]}(먼저 낸 곳 미확인)` : abroad ? `, 외국 출원 우선권(${abroad.join('·')}) — 국내보다 해외 먼저일 수 있음` : pr[0] ? `, 우선권 ${pr[0].number}` : ''})`
        + `${nf ? ` · 처음 보는 기술 분야(이력 ${docs['epo-patents']?.ipcHistorySince ?? '?'}부터): ${nf} — 새 사업 단서일 뿐 진출 확정 아님` : ''}`,
      url: f.url });
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
  const items = collect(docs, cut, kstDate(cut), { now: nowMs, maint: maintenanceMemo(fb) })
    .filter((x) => (x.tier === 'A' || x.tier === 'B') && x.check && typeof x.check === 'object' && !PRESS_SKIP.has(judged.get(x.id)) && !(x.parent && judged.get(x.parent) === '킬'))
    .map(({ tier, watch, id, date, company, fact, url, check }) => ({ tier, watch, id: String(id), date, company, fact: String(fact ?? '').slice(0, 300), url, check }));
  return Response.json({ generatedAt: ctx.now.toISOString(), hours, items }, { headers: { 'Cache-Control': 'no-store' } });
}

const PRESS_RANK = { '미보도 후보': 0, 미확인: 1, '관련 보도 있음': 2, '같은 수치 선행': 2 };
// 항목마다 자기 대조 시각을 쓴다(11-09: 11-05 강관·후판 관보 항목은 72시간 대조 범위를 벗어나 08:50에 다시 대조되지 않았는데,
// 이전 결과(바뀌기 전 낱말 '현대제철 관세 보조금')가 '자동 11-09 08:50'으로 보였다).
export function pressLines(r, stamp, docAt) {
  if (!r) return [];
  const at = Date.parse(r.checkedAt ?? '');
  const own = Number.isFinite(at) ? kstStamp(r.checkedAt) : stamp;
  const old = Number.isFinite(at) && at < Date.parse(docAt ?? '') - 60000;
  const stale = old && !r.recheck ? ` · 그 뒤 대조에서는 다시 안 봄(최근 72시간 범위 밖 등) — 질의·판정은 ${own} 것` : '';
  const failed = Object.entries(r.channels ?? {}).filter(([, v]) => v.status !== 'ok').map(([k, v]) => `${k} ${v.status}${v.error ? `(${v.error})` : ''}`);
  const qs = (r.queries ?? []).map((q) => `"${q}"`).join(', ');
  const tail = r.verdict === '미보도 후보' ? ` — ${qs}로 ${r.since} 이후 관련 기사 못 찾음(검색 범위 결과, 단독 판정 아님)`
    : r.verdict === '미확인' ? ` — ${failed.length ? `채널 ${failed.join(', ')}` : '기사 날짜 오류 또는 사건 식별 불가'}(0건 아님)` : ` — ${qs}`;
  const was = r.firstVerdict && r.firstVerdict !== r.verdict ? ` · 처음(${kstStamp(r.firstCheckedAt)}) ${r.firstVerdict}` : '';
  // 판정에 안 세는 앞선 기사(항목 날짜 전, 제목에 회사·사건 낱말)는 미보도 후보에 한 줄 맥락으로(10-31 울주 산소공장 안전점검 공고 ↔ 10-20 증설 기사)
  const ev = r.evidence ?? [];
  const shown = [...ev.filter((e) => !e.before).slice(0, 2), ...ev.filter((e) => e.before).slice(0, 1)];
  // 다시 본 항목은 그 뒤 실행에서 또 보지 않는다 — 두 표시를 한 줄로(11-09 13:10: '다시 봄 · 다시 안 봄'이 함께 떠 헷갈림)
  const again = r.recheck ? (old ? ` · 대조 규칙이 바뀌어 72시간 지난 뒤 ${own}에 한 번 다시 봄(그 뒤로는 범위 밖)` : ' · 대조 규칙이 바뀌어 72시간 지난 뒤 다시 봄') : '';
  // 근거 기사 제목 숫자가 항목 숫자와 같은지(11-09, scoop_screen.title_numbers) — 같은 사건인지 가르는 근거, 판정은 그대로
  const sameNum = ev.filter((e) => !e.before && e.numbers?.found?.length).length;
  const numSum = r.verdict === '관련 보도 있음' && sameNum ? ` · 제목 숫자까지 항목과 같은 기사 ${sameNum}건 — 같은 사건일 가능성 높음` : '';
  return [`   보도 대조(자동 ${own}): ${r.verdict}${tail}${was}${numSum}${again}${stale}`,
    ...shown.map((e) => `     ↳ ${e.date ?? '날짜?'} [${e.channel}] ${e.title}${e.url ? ` ${e.url}` : ''}${evidenceNote(e, r.verdict)}${numberNote(e)}`)];
}
function numberNote(e) {
  const n = e.numbers;
  if (!n?.article?.length) return '';
  return n.found?.length ? ` (숫자 ${n.found.join('·')} 항목과 같음)` : ` (숫자 ${n.article.join('·')} — 항목 숫자와 다름, 다른 건일 수 있음)`;
}
// 근거 줄 꼬리표. 미보도 후보에 붙은 근거는 모두 판정에 안 센 약한 근거다 — 꼬리표가 없으면 뒷받침 기사로 읽힌다
// (10-31 운영: 퍼스트솔라 10-Q 항목에 「한화솔루션, ESS·태양전지 특허 폭증」이 꼬리표 없이 붙었다 — 퍼스트솔라 없음).
export function evidenceNote(e, verdict) {
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
    const rawH = (ctx.now.getTime() - Date.parse(d.generatedAt)) / 3600000;
    // 평일에만 도는 감시는 토·일을 빼고 잰다(screen.mjs weekdayHours). 주 1회(월) 감시는 문턱(192시간)이 이미 주말을 품는다
    const ageH = /^평일/.test(w.schedule) ? weekdayHours(Date.parse(d.generatedAt), ctx.now.getTime()) : rawH;
    const waiting = (d.checks ?? []).filter((c) => c.status === 'partial' && !c.error && c.pending);  // read budget, not a failure
    const paused = (d.checks ?? []).filter((c) => c.status === 'waiting');  // call budget or provider cooldown: 미확인, not a failure
    // 지분 감시(governance)는 정상 조회를 'checked', 자료 없음을 'no_data'로 적는다(11-04 첫 화면: '일부 실패 102건'으로 잘못 보임)
    const failed = (d.checks ?? []).filter((c) => c.status && !['ok', 'unset', 'waiting', 'checked', 'no_data'].includes(c.status) && !waiting.includes(c) && !String(c.source ?? '').startsWith('공장등록 이름 규칙'));
    const unset = (d.checks ?? []).filter((c) => c.status === 'unset');
    const issues = [];
    if (Number.isFinite(ageH) && ageH > (w.staleHours ?? 36)) issues.push(`⚠ ${Math.round(rawH)}시간 전 결과`);
    if (failed.length) issues.push(`일부 실패 ${failed.length}건(${failed.slice(0, 3).map((c) => c.source ?? c.company ?? c.target).join(', ')})`);
    if (unset.length) issues.push(`미설정 ${unset.map((c) => `${c.source}(${c.error ?? '열쇠 없음'})`).join(', ')}`);
    if (waiting.length) issues.push(`${waiting.map((c) => `${c.source} 원문 대기 ${c.pending}건`).join(', ')}(실행당 읽기 한도, 다음 실행에서 읽음)`);
    if (paused.length) issues.push(`대기 ${paused.length}곳(${[...new Set(paused.map((c) => waitReason(c.reason)))].join(', ')})`);
    // 조용한 0건(screen.mjs returnedWatch): 감시는 '정상'인데 원천이 두 번 연달아 0줄·급감 — 사이트 형식이 바뀌었을 수 있다
    const silent = Array.isArray(d._returnedWatch?.silent) ? d._returnedWatch.silent : [];
    if (silent.length) {
      issues.push(`⚠ 형식 변경 의심 ${silent.length}곳(${silent.slice(0, 3).map((x) => `${x.source}: ${x.kind === 'zero' ? '정상 응답인데 0줄' : `${x.now}줄로 급감`}`
        + `, 이전 ${(x.before ?? []).join('·')}줄`).join(' / ')}) — 원문 사이트 목록이 보이는지 확인`);
    }
    if (issues.length) lines.push(`- ${w.label}: ${issues.join(' · ')} — 해당 부분 0건은 미확인`);
    // 감시가 남긴 운영 제안(11-08 지자체: 직접 조회 실패가 잦은 시·군 → 기자 컴퓨터 대신 수집 후보)은 실패 줄과 따로
    if (typeof d.healthNote === 'string' && d.healthNote) lines.push(`- ${w.label}: ${d.healthNote.slice(0, 300)}`);
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
  ['창녕'], ['안성'], ['광명'], ['천안'], ['영주'], ['삼척'], ['김해'], ['세종'], ['나주']].map(([name, rx]) => [name, rx ?? new RegExp(name)]);
// 사업장 이름에 시군이 없는 큰 공장(굴뚝 측정·국민연금 이름 그대로)
const SITE_PLACE = [[/현대제철㈜(?![가-힣])|현대제철주식회사(?![가-힣])/, '당진'], [/지에스칼텍스㈜|GS칼텍스주식회사/, '여수'], [/두산에너빌리티\(주\)/, '창원'],
  [/엘에스엠앤엠/, '울산'], [/동국제강㈜(?![가-힣\s]*공장)/, '인천'], [/르노코리아 주식회사/, '부산'], [/케이지모빌리티 주식회사/, '평택'], [/한국지엠주식회사/, '인천'],
  // 11-01 석유화학·정유: 굴뚝 측정 사업장 이름이 회사 이름뿐(대산공장)
  [/에이치디현대오일뱅크(?![^·]*지점)/, '서산']];
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
    // 다만 사흘 넘게 멈춘 배출구(굴뚝 감시가 '오래 멈춤'으로 알린 것)는 일상 정비보다 길어 개수와 상관없이 묶는다
    const long = s.stopped.filter((c) => s.stacks?.[c]?.longStopFor);
    if (!long.length && (s.meaningful ?? 0) >= 40 && s.stopped.length < Math.ceil(s.meaningful * 0.05)) continue;
    out.push({ id: `bg:stk:${s.id}`, background: true, tier: 'B', tool: 'kr_official', watch: W['kr-stacks'].label, company: s.company, date: docs['kr-stacks'].generatedAt,
      fact: `${s.name} 굴뚝 배출구 멈춤 ${s.stopped.length}개(평소 움직이던 ${s.meaningful ?? '?'}개 중)`
        + (long.length ? ` · 사흘 넘게 멈춤 ${long.length}개(${long.slice(0, 3).map((c) => `${c}번 ${s.stacks[c].stoppedSince}부터`).join(', ')})` : '') });
  }
  return out;
}

// 굴뚝 측정 항목이 즉시 알림 대상인지(11-04): ① 같은 출입처·같은 시군을 다른 감시의 새 항목(배경 아님, 킬 안 한 것)이 함께 가리킴,
// ② 그 사업장에서 평소 움직이던 배출구의 절반 넘게가 사흘 넘게 '가동중지'(사업장이 보낸 시설 멈춤 신고). 아니면 null.
export const STACK_ALERT_HOURS = 72;
// 공장 이름 조각(11-04): '현대제철㈜순천공장' → 순천공장, '롯데케미칼㈜울산2공장' → 울산2공장, '㈜엘지화학 여수공장(용성1단지)' → 여수공장·용성1단지.
// 숫자뿐인 앞말('PBV 2공장'의 2공장)은 어느 공장인지 말해 주지 않아 뺀다.
// 앞말이 '신·새·증설·전기차' 같은 일반 낱말이면 어느 공장인지 말해 주지 않는다('기아 화성 증설공장'은 화성공장과 다른 공장이 아님).
const GENERIC_PLANT = /^(?:[가-힣]|증설|신설|신규|전용|전기차|배터리|합작|해외|국내|현지|생산|완성차|부품|소재|기존|제2|제3|미국|중국|인도|유럽|베트남|멕시코|산업)$/;
export function plantTokens(text) {
  const t = String(text ?? '').replace(/㈜|\(주\)|주식회사/g, ' ');
  return [...new Set([...t.matchAll(/([가-힣0-9]{1,8})(공장|제철소|제련소|단지)/g)]
    .filter((m) => /[가-힣]/.test(m[1]) && !GENERIC_PLANT.test(m[1].replace(/\d/g, '')) && !GENERIC_PLANT.test(m[1])).map((m) => m[1] + m[2]))];
}
// 같은 공장 이름인가: 회사 이름이 붙어 '금호타이어함평공장'처럼 뽑혀도 '함평공장'과 같은 공장으로 본다(끝이 같으면 같음).
export const samePlant = (a, b) => a.endsWith(b) || b.endsWith(a);
// 같은 출입처·같은 시군 묶음을 공장 이름으로 나눈다(11-04): 공장 이름이 적힌 항목끼리 겹치지 않으면 다른 공장 묶음.
// 공장 이름이 없는 항목(국민연금 주소·공장등록 주소)은 어느 공장인지 몰라 나뉜 묶음 모두에 붙는다.
export function splitByPlant(g) {
  const tok = new Map(g.items.map((x) => [x.id, plantTokens(`${x.fact ?? ''} ${x.site ?? ''}`)]));
  const clusters = [];
  for (const x of g.items.filter((y) => tok.get(y.id).length)) {
    const mine = tok.get(x.id);
    const hit = clusters.filter((c) => [...c.tokens].some((k) => mine.some((m) => samePlant(k, m))));
    const merged = { tokens: new Set(mine), items: [x] };
    for (const c of hit) { c.tokens.forEach((k) => merged.tokens.add(k)); merged.items.push(...c.items); clusters.splice(clusters.indexOf(c), 1); }
    clusters.push(merged);
  }
  if (clusters.length < 2) return [g];
  const plain = g.items.filter((x) => !tok.get(x.id).length);
  const short = (ks) => [...ks].sort((a, b) => a.length - b.length)[0];
  return clusters.map((c) => ({ ...g, plant: short(c.tokens), items: [...c.items, ...plain] }));
}
export function stackAlert(x, conv, stacksDoc, nowMs, judged = new Map(), maint = null) {
  const label = WATCHES.find((w) => w.feed === 'kr-stacks')?.label;
  if (!label || x.watch !== label || !['A', 'B'].includes(x.tier)) return null;
  const s = (stacksDoc?.sites ?? []).find((y) => y.company === x.company && (y.name === x.site || String(x.id).includes(`:${y.name}:`)));
  const mine = plantTokens(s?.name ?? x.site ?? '');
  for (const g of conv ?? []) {
    if (!g.items.some((y) => y.id === x.id)) continue;
    // 킬한 항목은 증거로 세지 않는다(include_judged로 화면에 보일 때도). 같은 시군이라도 다른 공장 이름이 적힌 항목
    // (울산1공장 굴뚝 ↔ 울산2공장 공고)은 다른 공장이라 세지 않는다.
    // 11-08: 시군까지만 맞는 겹침은 세지 않고 공장 이름까지 맞을 때만 — 포항·광양·당진처럼 큰 제철소 도시는 도로점용 공고·의회 회의록이
    // 늘 함께 걸려, 기준의 1.0~1.1배 실시간 초과 값까지 즉시 알림으로 갔다(굴뚝 알림 21건 중 킬 9·판정 없음 12, 판정한 굴뚝 16건 모두 킬).
    const ev = g.items.filter((y) => !y.background && y.watch !== label && judged.get(y.id) !== '킬').map((y) => {
      const theirs = plantTokens(y.fact);
      return { y, same: theirs.length && mine.length ? theirs.some((k) => mine.some((m) => samePlant(k, m))) : null };
    }).filter((e) => e.same === true);
    if (ev.length) {
      const others = [...new Set(ev.map((e) => e.y.watch))];
      return `겹친 신호 — ${g.place}에서 ${others.join('·')}도 이 공장을 가리킴(공장 이름까지 맞음)`;
    }
  }
  const m = s?.meaningful ?? 0;
  // 정기보수 메모가 있는 사업장은 '장기 가동중지 신고'로 알리지 않는다(회사가 이미 정기보수라고 확인함)
  const mm = maint?.get(stackSiteKey(x.id));
  if (m >= 2 && !(mm && nowMs <= mm.until)) {
    const at = (v) => Date.parse(`${String(v ?? '').replace(' ', 'T')}:00+09:00`);
    // 멈춘 때는 숫자가 끊긴 첫 측정(stoppedSince)을 먼저 쓴다 — 상태 글자는 11-03부터 읽어 '처음 본 때'가 실제 멈춤보다 늦다(순천 10-31 멈춤 → 11-03 10:30 처음 봄)
    const long = Object.values(s.stacks ?? {}).filter((st) => (st.status ?? [])[0] === '가동중지'
      && nowMs - Math.min(...[at(st.stoppedSince), at(st.status[1])].filter(Number.isFinite)) >= STACK_ALERT_HOURS * 3600000).length;
    if (long * 2 > m) return `장기 가동중지 신고 — 평소 움직이던 배출구 ${m}개 중 ${long}개가 사흘 넘게 '가동중지'`;
  }
  return null;
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
  for (const g of [...groups.values()].flatMap(splitByPlant)) {
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

// 최근 72시간 안에 처음 본 업종 비교 후보가 있을 때만 줄을 낸다(머리·읽는 법만 남으면 빼기)
function recentPeers(v, q, nowMs) {
  if (!v) return [];
  const lines = peerLines(v, { q, limit: 6, since: new Date(nowMs - 72 * 3600000).toISOString() });
  return lines.some((l) => l.startsWith('- ')) ? lines : [];
}

export async function radarToday(ctx, args) {
  return textResult(await radarTodayText(ctx, args));
}

// 오늘의 레이더 자료(도구 글과 기자 전용 화면 board.mjs가 같이 쓴다). 글 모양은 radarTodayText, 카드 모양은 board.mjs.
export async function radarTodayData(ctx, args) {
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
  const maint = maintenanceMemo(fb);
  const showJudged = args.include_judged === true || args.include_judged === 'true';
  // 이어 올린 항목(노동위 조정 결과 확인 등)은 원래 항목을 킬했으면 숨긴다
  const found = collect(docs, cut, cutDay, { now: nowMs, maint }).filter((x) => has(q, x.company, x.fact, x.watch) && !(x.parent && judged.get(x.parent) === '킬'));
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
  const byTierRows = { A: byTier('A'), B: byTier('B'), C: byTier('C') };
  const h = health(ctx, docs);
  const dh = await dispatchHealth(ctx);
  if (dh) h.unshift(`- ${dh}`);
  // GitHub 실행이 연달아 실패한 프로그램(11-08 보도 대조 7회 연속 실패가 36시간 뒤에야 보였다) — 감시 결과 나이보다 먼저 본다
  const gh = await runsHealth(ctx).catch((e) => [`GitHub 실행 상태: 읽기 실패(${String(e?.message ?? e).slice(0, 60)}) — 미확인`]);
  h.unshift(...gh.map((x) => `- ${x}`));
  // 기자 컴퓨터 Aside 수집(11-08): 컴퓨터가 꺼져 예약 수집이 빠져도 다른 감시 상태로는 안 보인다
  // 상태 읽기가 실패하면 줄을 숨기지 않고 미확인으로 적는다(줄이 없으면 '이상 없음'으로 읽히기 때문)
  const bh = await browserHealth(ctx).catch((e) => `기자 컴퓨터 수집: 상태 읽기 실패(${String(e?.message ?? e).slice(0, 60)}) — 미확인`);
  if (bh) h.push(`- ${bh}`);
  if (!press) h.push('- 보도 대조(자동): 결과 없음 — 미확인(평일 08:50·12:50·18:50 실행 확인)');
  else if (press.broken) h.push('- 보도 대조(자동): 저장 형식 오류 — 미확인');
  else {
    const ageH = (nowMs - Date.parse(press.generatedAt)) / 3600000;
    if (Number.isFinite(ageH) && ageH > 36) h.push(`- 보도 대조(자동): ⚠ ${Math.round(ageH)}시간 전 결과 — 이후 항목은 대조 전`);
  }
  const span = nowMs - 14 * 86400000;
  const conv = convergence([...collect(docs, span, kstDate(span), { now: nowMs, maint }).filter((x) => !(judged.get(x.id) && !showJudged)), ...background(docs, nowMs)]
    .filter((x) => has(q, x.company, x.fact, x.watch)), { cut });
  // 묶음을 만든 새 신호(배경 아님)가 모두 이미 보도된 묶음은 뒤로(10-31 운영: 금호타이어 함평 묶음의 유일한 새 신호인
  // 부지 취득 완료 정정은 10-28 '함평 이전 부지 1160억원에 취득 완료' 기사로 '관련 보도 있음'인데 맨 위에 표시 없이 떴다)
  const coveredGroup = (g) => g.items.filter((x) => !x.background).every((x) => rank(x) === 2);
  conv.sort((a, b) => Number(coveredGroup(a)) - Number(coveredGroup(b)));
  // 굴뚝 측정 항목의 즉시 알림 대상(11-04 기자 결정: 굴뚝 실시간 신호만 있는 항목 9건을 모두 킬 — '뒷받침할 증거가 없음').
  // 화면에는 그대로 두고, 아래 둘 중 하나일 때만 〔즉시 알림 대상〕을 붙인다(즉시 알림 예약 작업이 이 표시만 본다).
  for (const t of ['A', 'B']) for (const x of byTierRows[t]) { const why = stackAlert(x, conv, docs['kr-stacks'], nowMs, judged, maint); if (why) x.alert = why; }
  // 실적 업종 비교(11-04, earnings_compare 공개 결과): 최근 72시간 안에 처음 본 데이터 기사 후보만 radar_today에 올린다.
  let peerV = null;
  try { peerV = await fetchJson(ctx, 'digests/earnings_compare_latest.json'); } catch { peerV = null; }
  // Competitor exclusives the radar had first (reverse_prior_capture.py). Shown here too, so the reporter can prepare Y/P/N
  // judgments even when the chat's connector list is stale and scoop_reverse is not offered.
  const rev = await readFeed(ctx, 'reverse-check');
  // 기자 기사 자동 대조(my_articles_check.py): 레이더 항목 id → 그 뒤 기자가 쓴 아이뉴스24 기사(같은 회사·사건 낱말). 판정이 아니라 표시만.
  const mine = await readFeed(ctx, 'my-articles');
  const wrote = new Map(Object.entries(mine && !mine.broken ? mine.itemHits ?? {} : {}));
  let firsts = [];
  if (rev && !rev.broken) {
    const from = Date.parse(rev.generatedAt) - 14 * 86400000;
    firsts = (rev.articles ?? []).filter((a) => a.verdict === '먼저 잡은 후보' && Date.parse(a.published) >= from && a.best
      && (!q || has(q, a.title, (a.companies ?? []).join(' '), a.best.text)))
      .sort((a, b) => String(b.published).localeCompare(String(a.published)));
  }
  return { now: ctx.now, hours, monday, defaultHours: !args.hours, q, limit, showC, judged, hiddenBy, press, checked, pressOf, rank,
    tiers: byTierRows, health: h, conv, coveredGroup, rev, firsts, wrote,
    peers: recentPeers(peerV, q, nowMs) };
}

export async function radarTodayText(ctx, args) {
  const d = await radarTodayData(ctx, args);
  const { hours, monday, limit, showC, judged, hiddenBy, press, checked, pressOf, conv, coveredGroup, rev, firsts } = d;
  const h = d.health;
  const out = [`오늘의 레이더 · ${kstStamp(d.now.toISOString())} KST 기준 최근 ${hours}시간${monday && d.defaultHours ? '(월요일: 주말 포함)' : ''} · 기자 전용 감시 ${WATCHES.length}개`];
  out.push(h.length ? `\n[먼저 볼 것: 수집 상태]\n${h.join('\n')}` : `\n[수집 상태] ${WATCHES.length}개 감시 모두 최근 정상`);
  if (conv.length) {
    out.push(`\n[겹친 신호 · 최근 14일 같은 출입처·같은 시군을 감시 여러 곳이 가리킴] ${conv.length}곳 — 하나씩은 공개 자료, 함께 보면 투자·가동 변화 단서(배경: 국민연금 공사 현장·120일 안 건축허가·지금 멈춘 굴뚝)`);
    for (const g of conv.slice(0, 5)) {
      out.push(`- ${g.fresh ? '[새 항목 포함] ' : ''}${g.company} · ${g.place}${g.plant ? ` · ${g.plant}` : ''} — 감시 ${g.watches.length}곳(${g.watches.join(', ')})${coveredGroup(g) ? ' · 새 신호는 모두 관련 보도 있음(같은 사건인지 열어 볼 것)' : ''}`);
      const { rows, more } = convergenceRows(g);
      for (const x of rows) out.push(`   ${x.background ? '(배경) ' : `${x.tier} · ${pressOf(x) ? `[${pressOf(x)}] ` : ''}`}${x.date ? `${String(x.date).length > 10 ? kstStamp(x.date) : x.date} · ` : ''}${x.watch}: ${clipAt(x.fact, 110)} · id ${x.id}`);
      if (more) out.push(`   … 같은 묶음 ${more}줄 더`);
    }
    if (conv.length > 5) out.push(`… 남은 ${conv.length - 5}곳(company로 좁히기)`);
    out.push('   읽는 법: 같은 시군 이름이 문장에 있으면 묶는다(같은 공장·같은 사업이라는 확인이 아님). 같은 시군이라도 서로 다른 공장 이름(울산1공장·울산2공장)이 적힌 항목은 공장별로 나눠 묶고, 공장 이름이 없는 항목(주소만 있는 국민연금·공장등록)은 양쪽에 붙인다. 각 원문을 열어 같은 부지·사업인지 본다.');
  }
  if ((d.peers ?? []).length) out.push(...d.peers);
  const tiers = [['A', '단독 후보·직접 변화 — 원문·보도 대조부터'], ['B', '확인할 공식 변화'], ['C', '참고(접힘)']];
  for (const [t, title] of tiers) {
    const rows = d.tiers[t];
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
      // 기사 준비(무역구제 등): 다음 절차·회사에 물을 것
      if (x.point) out.push(`   〔기사 포인트〕 ${x.point}`);
      if (x.next) out.push(`   〔기사 준비〕 다음 절차: ${x.next}`);
      if (x.ask) out.push(`   물을 것: ${x.ask}`);
      out.push(...pressLines(checked.get(String(x.id)), kstStamp(press?.generatedAt), press?.generatedAt));
      const w = d.wrote?.get(String(x.id));
      out.push(`   ${x.url ? `원문: ${x.url} · ` : ''}자세히: ${x.tool} · id ${x.id}${judged.get(x.id) ? ` 〔판정: ${judged.get(x.id)}〕` : ''}${w ? ` 〔기자 기사(자동 대조) ${String(w.published).slice(5, 10)} 「${String(w.title).slice(0, 40)}」〕` : ''}${x.alert ? ` 〔즉시 알림 대상: ${x.alert}〕` : ''}`);
    }
    if (rows.length > limit) out.push(`… 남은 ${rows.length - limit}건(limit 또는 company로 좁히기)`);
    if (!rows.length) out.push('없음');
  }
  if (firsts.length) {
    out.push(`\n[경쟁지 단독 역추적 · 자동 후보, 사람 판정(Y/P/N) 전] 최근 14일 레이더가 먼저 잡은 후보 ${firsts.length}건 · 확인 ${kstStamp(rev.generatedAt)}`);
    for (const a of firsts.slice(0, 5)) {
      out.push(`- 기사 ${kstStamp(a.published)} · ${a.source ?? '?'} 「${String(a.title ?? '').slice(0, 70)}」 · 기사 id ${a.articleId}`);
      out.push(`   레이더: ${kstStamp(a.best.seen)} ${a.best.label} — ${reverseClip(a.best.text, 90)} (${a.best.leadHours}시간 앞${(a.best.why ?? []).length ? `, 겹친 낱말 ${a.best.why.join('·')}` : ''})${reverseNumbersNote(a.best)} · id ${a.best.id}`);
    }
    if (firsts.length > 5) out.push(`… 남은 ${firsts.length - 5}건`);
    out.push('판정은 기자가 한다: 기사 원문(매체 사이트)·최초 게재 시각과 레이더 원천 원문을 열어 같은 사실인지 본다. 자세히: scoop_reverse.');
  }
  const hiddenN = Object.values(hiddenBy).reduce((a, b) => a + b, 0);
  if (hiddenN) out.push(`\n(판정한 ${hiddenN}건 숨김: ${Object.entries(hiddenBy).map(([v, n]) => `${v} ${n}`).join(' · ')} — include_judged=true로 보기)`);
  out.push('정리: 다 본 항목은 candidate_feedback(verdict=봤음, item_ids=[…])로 표시하면 다음부터 안 뜬다.');
  out.push('\n규칙: 모두 자동 수집 단계다. A도 단독 확정이 아니다 — 원문 확인 → news_check(낱말 바꿔 2~3번) → 회사 확인 → candidate_check. 첫 실행에 잡힌 기존 항목은 자기 날짜가 최근일 때만 새 항목으로 센다.');
  out.push("보도 대조(자동)는 네이버 뉴스 API·빙·구글에서 항목 날짜 3일 전부터 찾은 결과다. '미보도 후보'도 단독 판정이 아니고, '관련 보도 있음'은 같은 사건인지 열어 봐야 한다. 채널 실패는 미확인.");
  return out.join('\n');
}
