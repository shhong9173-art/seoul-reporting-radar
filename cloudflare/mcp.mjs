// Streamable-HTTP MCP endpoint (JSON responses, no SSE) for the radar.
import { safeEqual, textResult } from './common.mjs';
import { bigPicture, clues, dandok, earnings, governance, health, stats } from './radar_tools.mjs';
import { dartFilings, dartFindText, g2bBids, newsCheck, sourceDocument } from './live_tools.mjs';
import { candidateSubmit, packageSave, scoopPackages, FEEDBACK_VERDICTS, PACKAGE_STATES } from './store.mjs';
import { judgeItems, weeklyReview } from './review.mjs';
import { customsTrade, ecosData, ecosFind, kosisData, kosisFind } from './stats_live.mjs';
import { POLICY, checkVerifiedCandidate, formatCheck } from './scoring.mjs';
import { scoopScreen } from './screen.mjs';
import { krOfficial, krSignals, krStats, pageChanges, partnerFilings, scoopReverse, tradeRemedies, usComments, usEpa, usLitigation, usRecalls } from './overseas.mjs';
import { trademarks } from './trademarks.mjs';
import { assemblyBills } from './assembly.mjs';
import { radarToday } from './digest.mjs';

export const SUPPORTED_VERSIONS = ['2025-06-18', '2025-03-26', '2024-11-05'];
const SERVER_INFO = { name: 'seoul-reporting-radar', title: '산업부 취재 레이더', version: '1.0.0' };
const INSTRUCTIONS = [
  '산업부(자동차·철강·전력기기·에너지·화학) 취재 레이더. 기자는 홍성효.',
  '하루 시작은 radar_today(기자 전용): 감시 13개의 새 항목을 A(단독 후보·직접 변화)/B(확인할 공식 변화)로 모아 보여 주고, 실패·오래된 감시를 먼저 알린다. 항목마다 자세히 볼 도구가 붙어 있다.',
  '순서: radar_today → scoop_screen(기자 전용, 미보도 후보부터) → page_changes·us_comments·partner_filings·trade_remedies·us_litigation·us_recalls·us_epa(기자 전용, 해외 원천) → kr_official(기자 전용, 공장등록·관보) → kr_signals(기자 전용, 공정위 의결서·한전 입찰·원자재 가격) → kr_stats(기자 전용, 물가지수·철강 생산·수입차 등록; 발제 검증은 ecos_find·ecos_data·kosis_find·kosis_data·customs_trade 즉석 조회) → trademarks(기자 전용, 출입처 상표 출원 주 1회) → assembly_bills(기자 전용, 출입 업종 국회 법안 발의·단계) → radar_big_picture → radar_clues(days=3) → radar_stats → governance_changes → earnings_compare(실적 시즌) → dandok_monitor → scoop_packages(기자 전용).',
  '후보마다: source_document 또는 dart_find_text로 원문 확인 → news_check로 보도 대조(낱말 바꿔 2~3번, 한 번에 하나씩) → candidate_check.',
  '조회 실패·미설정·일부 성공은 0건이 아니라 미확인. 색인 0건은 미보도 증거가 아님. 단계(공개 원자료 추적/취재 단서·단독 미확정/단독 후보)를 올리지 않음.',
  '추천 심사에는 기자 전용 원문·보도 조회의 검증 기록 ID가 필요하다. facts는 원문 직접 인용, 게시일은 명시된 공개일만. 오래된 원문·검색된 기사·파생 계산은 추가 확인 전 조사대기다.',
  '최종 단독 판단은 기자가 한다. 관계자 발언을 만들지 않는다.',
  '후보 보고 형식(후보마다): 잡힌 사실(원문에 적힌 것만, 날짜·수치 그대로) / 기사 가치(지금 왜, 무엇이 새로운가, 약점) / 확인 질문(회사에 물을 2~3개, 공개자료로 답할 수 있는 건 먼저 찾아본 뒤 남는 것만) / 원문(URL·접수번호·게시일·열람일) / 판단(추천·취재 착수·보류·접음과 이유).',
  '후보마다 붙일 것: 보도 대조(채널별 결과·질의·선행 기사) / 검증 상태(원문 확인·원문 미확인·회사 확인 필요·외부 자료 정정 — 다른 시스템·자료·제보의 주장이 원문과 다르면 무엇이 다른지).',
].join('\n');

const obj = (properties, required = []) => ({ type: 'object', properties, required, additionalProperties: false });
const str = (description) => ({ type: 'string', description });
const int = (description, minimum, maximum) => ({ type: 'integer', description, minimum, maximum });
const bool = (description) => ({ type: 'boolean', description });
const strList = (description) => ({ type: 'array', items: { type: 'string' }, description });

const CANDIDATE_SCHEMA = obj({
  title: str('발제 제목(숫자는 원문에 있는 것만)'),
  companies: strList('관련 기업'),
  source_url: str('원자료 URL'),
  source_date: str('원자료 게시일 YYYY-MM-DD'),
  content_hash: str('source_document·dart_find_text가 준 sha256'),
  source_evidence_id: str('기자 전용 원문 도구가 발급한 검증 기록 ID(24시간)'),
  news_evidence_ids: strList('news_check가 발급한 서로 다른 질의의 검증 기록 ID 2~5개(365일 조회)'),
  event_terms: strList('원문 인용과 검색 질의 양쪽에 있는 구체적 사건·사업장 낱말'),
  facts: strList('실제 조회 구간의 직접 인용. 해석·요약은 impact에 구분'),
  numbers: strList('원문에 적힌 수치 그대로(예: 1,812억원)'),
  derived_numbers: { type: 'array', items: obj({ value: str('계산값'), method: str(POLICY.derivedMethods.join('/')) }, ['value', 'method']) },
  coverage: obj({ google: str('ok/failed/not_checked'), bing: str('ok/failed/not_checked'), naver: str('ok/failed/not_configured'), dandok: str('ok/failed'),
    verdict: str(POLICY.verdicts.join('/')) }),
  company_disclosed: { type: ['boolean', 'null'], description: '회사가 이미 밝혔나(true/false), 확인 안 했으면 null' },
  comparison: str('이전 발표·경쟁사와 같은 기준 비교'),
  impact: str('향후 영향'),
  questions: strList('회사·기관에 물을 질문 2~3개'),
  size_scores: obj(Object.fromEntries(POLICY.sizeKeys.map((k) => [k, int(`${POLICY.sizeLabels[k]} 0~2`, 0, 2)]))),
  flags: obj(Object.fromEntries(POLICY.penalties.filter((p) => p.key !== 'non_beat').map((p) => [p.key, bool(p.label)]))),
}, ['title']);

export const TOOLS = [
  { name: 'radar_big_picture', access: 'public', handler: bigPicture,
    description: '큰 그림. 팀별 최근 7일 원자료 단서 수, 강한 통계 신호, 최근 7일 [단독] 흐름, 문제 원천. 제일 먼저 부른다.',
    inputSchema: obj({}) },
  { name: 'radar_clues', access: 'public', handler: clues,
    description: '최근 N일 공식 원자료 단서를 팀별(자동차/철강·비철/전력·에너지/화학·소재/해외/조달/특허/그 외)로. 줄마다 게시일·출처·제목·보도 색인 대조·단계. 색인 0건 줄이 팀 맨 앞.',
    inputSchema: obj({ days: int('게시일 기준 최근 N일(기본 3, 월요일·연휴 뒤 4~5)', 1, 45),
      team: str('팀 거르기, 쉼표로 여럿: 자동차,철강,전력,화학,해외,조달,특허'), q: str('제목·출처·기업 낱말(띄어쓰기=AND)'),
      limit: int('팀당 줄 수(기본 40)', 1, 200), since_hours: int('최근 N시간 안에 새로 잡힌 줄만(증분 조회)', 0, 336),
      include_routine: bool('IR 개최·주총 소집 같은 절차 공시까지 보기') }) },
  { name: 'radar_stats', access: 'public', handler: stats,
    description: '정기 통계·공시 표 숫자가 선을 넘은 것(급변·N배·관측 구간 최대). 관세청 10일 잠정치·지역별·HS 추세, DART 사업의 내용 표 변동, 경쟁사 비교. 수치 기획감의 출발점.',
    inputSchema: obj({ team: str('팀 거르기'), q: str('낱말'), limit: int('줄 수(기본 25)', 1, 80) }) },
  { name: 'dandok_monitor', access: 'public', handler: dandok,
    description: '최근 온라인 [단독] 기사(출입처 관련, 제목 색인). 남이 쓴 걸 새것처럼 내지 않으려고 본다.',
    inputSchema: obj({ days: int('최근 N일(기본 7, 최대 120)', 1, 120), q: str('기업·낱말'), team: str('팀'),
      limit: int('줄 수', 1, 200) }) },
  { name: 'governance_changes', access: 'public', handler: governance,
    description: '출입처 지분·지배구조 공시(5% 대량보유·임원/주요주주 소유보고) 최근 N일. 지분율 변동·공시 사유 낱말(담보·계약·특수관계 등)·최고경영진 매매·같은 날 임원 집단 보고를 표시하고, 기관의 단순 보고와 소액 임원 보고는 숨김(include_routine=true로 전체). 고려아연·영풍, LS, 포스코 등 지배구조 취재의 출발점.',
    inputSchema: obj({ company: str('기업·보고자 낱말'), team: str('팀'), days: int('최근 N일(기본 14, 최대 30)', 1, 30),
      include_routine: bool('기관 약식·단순 보고까지'), limit: int('줄 수', 1, 100) }) },
  { name: 'earnings_compare', access: 'public', handler: earnings,
    description: '공시 시즌 비교표: 출입처별 원가율·판관비율·영업이익률(3개월·누적)과 직원 수를 같은 보고기간 전년 동기와 비교. 제출·미제출·조회 실패를 구분. 실적 시즌 기사 재료 찾기.',
    inputSchema: obj({ company: str('기업 낱말'), team: str('팀'), flagged_only: bool('기준선(원가율 ±3%p·판관비율 ±2%p·영업이익률 ±3%p·직원 ±5%)을 넘은 회사만'),
      limit: int('회사 수', 1, 60) }) },
  { name: 'radar_health', access: 'public', handler: health,
    description: '원천별 수집 상태. 실패·미연결·오래된 원천에서 나온 0건은 미확인으로 적어야 한다.',
    inputSchema: obj({}) },
  { name: 'news_check', access: 'public', handler: newsCheck,
    description: '이미 났나: 구글·빙 뉴스(실시간)·네이버 뉴스(기자 전용, 키 필요)·[단독] 색인을 조회. 네이버 + 웹 색인(구글 또는 빙) + [단독] 색인이 모두 정상이어야 판정한다. 채널별로 조회 실패와 0건을 구분해 돌려준다. 낱말 2~3개, 한 번에 하나씩, 낱말을 바꿔 2~3번.',
    inputSchema: obj({ q: str('검색 낱말 2~3개'), days: int('최근 N일(기본 365)', 1, 365), limit: int('채널당 표시 줄 수', 1, 30) }, ['q']) },
  { name: 'source_document', access: 'public', handler: sourceDocument,
    description: '공식 원문(go.kr·DART·KIND·KIPRIS·.gov·EU·출입처 홈페이지)을 열어 텍스트 구간과 내용 해시(sha256)를 돌려준다. DART 공시 링크는 틀 대신 본문 문서를 읽고 다른 첨부 문서 주소도 준다. 긴 문서는 offset으로 이어 읽는다.',
    inputSchema: obj({ url: str('원문 주소'), offset: int('시작 글자 위치', 0, 5000000), limit: int('읽을 글자 수(최대 16000)', 500, 16000) }, ['url']) },
  { name: 'candidate_check', access: 'public', handler: async (ctx, args) => textResult(formatCheck(await checkVerifiedCandidate(ctx, args.candidate ?? args))),
    description: '후보 하나를 점수 정책으로 점검: 가점·감점, 추천/조사대기/탈락, 채울 것(원문·해시·보도 채널·질문·비교), 제목 숫자 근거, 지면감(톱/박스/단신). 저장하지 않는다.',
    inputSchema: obj({ candidate: CANDIDATE_SCHEMA }, ['candidate']) },
  { name: 'dart_filings', access: 'private', handler: dartFilings,
    description: 'OpenDART 공시 목록(실시간). 출입처 이름 또는 고유번호, 기간 YYYYMMDD. 조회 실패는 0건이 아니다.',
    inputSchema: obj({ company: str('출입처 이름(예: 현대제철)'), corp_code: str('DART 고유번호 8자리'),
      start: str('시작일 YYYYMMDD(기본 90일 전)'), end: str('종료일 YYYYMMDD') }) },
  { name: 'dart_find_text', access: 'private', handler: dartFindText,
    description: 'DART 공시 원문(document.xml)에서 낱말을 찾아 앞뒤 문맥과 파일별 해시를 준다. 건설중인자산·계약상대방·생산능력 같은 확인용.',
    inputSchema: obj({ rcp_no: str('접수번호 14자리'), word: str('찾을 낱말'), limit: int('문맥 수(기본 8)', 1, 20) }, ['rcp_no', 'word']) },
  { name: 'ecos_find', access: 'private', handler: ecosFind,
    description: '한국은행 ECOS 통계표·항목 코드 찾기(실시간). query만 주면 통계표, stat(예: 404Y016 생산자물가 품목별)과 query를 주면 항목 코드·주기·수록 기간.',
    inputSchema: obj({ query: str('통계표·품목 낱말(예: 생산자물가, 열연)'), stat: str('통계표 코드'), limit: int('줄 수', 1, 60) }) },
  { name: 'ecos_data', access: 'private', handler: ecosData,
    description: '한국은행 ECOS 값 조회(실시간): 최신값·직전·전년 같은 기간 대비, 조회 범위 안 "그때(값) 이후 최고·최저", 최근 13개. 수출입물가처럼 기준(원화·달러·계약통화)이 여러 개면 따로 보여 준다.',
    inputSchema: obj({ stat: str('통계표 코드'), item: str('항목 코드1'), item2: str('항목 코드2(있으면)'), item3: str('항목 코드3(있으면)'),
      cycle: { type: 'string', enum: ['M', 'Q', 'A'] }, start: str('시작(YYYYMM·YYYYQn·YYYY, 기본 10년 전)'), end: str('끝(기본 최근)') }, ['stat', 'item']) },
  { name: 'kosis_find', access: 'private', handler: kosisFind,
    description: 'KOSIS 국가통계포털 통계표 찾기(실시간): 낱말 → 기관 ID·통계표 ID·수록 기간.',
    inputSchema: obj({ query: str('통계표 낱말(예: 철강 생산량, 광공업 품목별)'), limit: int('줄 수', 1, 40) }, ['query']) },
  { name: 'kosis_data', access: 'private', handler: kosisData,
    description: 'KOSIS 값 조회(실시간). obj1 없이 부르면 분류·항목 코드 목록, obj1·itm을 주면 계열별 최신값·전년 대비·조회 범위 안 최고·최저·최근 13개.',
    inputSchema: obj({ org: str('기관 ID'), tbl: str('통계표 ID'), obj1: str('첫 분류 코드'), obj2: str('둘째 분류 코드'), itm: str('항목 코드(기본 ALL)'),
      prd: { type: 'string', enum: ['M', 'Q', 'Y'] }, start: str('시작(YYYYMM 등)'), end: str('끝'), query: str('분류 이름 거르기(목록 볼 때)') }, ['org', 'tbl']) },
  { name: 'customs_trade', access: 'private', handler: customsTrade,
    description: '관세청 품목별·국가별 수출입실적(실시간, HS 기준): 월별 수출·수입 금액, 최신 달 전월·전년 대비, 조회 범위 안 최고·최저, 수출 단가(USD/kg). hs에 숫자 대신 변압기·전선·승용차·열연·아연괴 같은 낱말도 된다.',
    inputSchema: obj({ hs: str('HS 코드(2~10자리) 또는 품목 낱말'), country: str('국가 코드(US, CN …, 비우면 전체)'), start: str('YYYYMM(기본 36개월 전)'), end: str('YYYYMM(기본 지난달)') }, ['hs']) },
  { name: 'g2b_bids', access: 'private', handler: g2bBids,
    description: '나라장터 입찰공고 낱말 검색(공고≠낙찰·계약). 키가 없으면 공개 스냅샷만 본다.',
    inputSchema: obj({ q: str('낱말(예: 변압기, 해저케이블)'), days: int('최근 N일(최대 7)', 1, 7) }, ['q']) },
  { name: 'scoop_packages', access: 'private', handler: scoopPackages,
    description: `취재 패키지 목록(name 비우면) 또는 전문. 상태: ${PACKAGE_STATES.join('/')}. 발제함은 후속만, 접음은 다시 내지 않는다.`,
    inputSchema: obj({ name: str('패키지 이름(비우면 목록)') }) },
  { name: 'package_save', access: 'private', handler: packageSave,
    description: '취재 패키지 저장·갱신(비공개 저장소). 발제문·근거·이미 났나·약점·확인 필요·물을 곳을 body에.',
    inputSchema: obj({ name: str('짧은 영문/한글 이름(예: lselectric-busan-capa)'), title: str('한 줄 요약'),
      state: { type: 'string', enum: PACKAGE_STATES }, body: str('패키지 전문') }, ['name', 'title', 'state', 'body']) },
  { name: 'candidate_submit', access: 'private', handler: candidateSubmit,
    description: `후보를 재점검해 저장(하루 추천 ${POLICY.dailyLimit}건 한도, 같은 날 중복 제목 제외).`,
    inputSchema: obj({ candidates: { type: 'array', items: CANDIDATE_SCHEMA, maxItems: 10 } }, ['candidates']) },
  { name: 'radar_today', access: 'private', handler: radarToday,
    description: '오늘의 레이더(하루 시작): 기자 전용 감시 13개(단독 후보 심사, 공장등록·관보, 공정위·한전·원자재, 월간 통계, 무역구제, 미국 소송, 해외 파트너 공시, 미 의견서, 해외 페이지, 상표 출원, 국회 법안, 미국 리콜, 미국 EPA 인증)에서 최근 N시간(기본 24, 월요일 72) 새 항목만 모아 A(단독 후보·직접 변화)/B(확인할 공식 변화)/C(참고)로 정렬. A·B 항목마다 자동 보도 대조 결과(평일 08:50·18:50, 항목 날짜 3일 전 이후 네이버·빙·구글: 미보도 후보·관련 보도 있음·미확인)를 붙이고 미보도 후보를 먼저 보여 줌. 실패·오래된 감시를 맨 위에 표시. 기자가 판정(씀·킬·보류·봤음)한 항목은 숨김, 줄마다 id.',
    inputSchema: obj({ hours: int('최근 N시간(기본 24, 월요일 72)', 1, 336), company: str('기업·낱말로 거르기'),
      include_minor: bool('C(참고)도 펼쳐 보기'), include_judged: bool('씀·킬·보류·봤음으로 판정한 항목도 보기'),
      limit: int('등급별 줄 수(기본 15)', 1, 60) }) },
  { name: 'scoop_screen', access: 'private', handler: scoopScreen,
    description: '단독 후보 자동 심사 결과(평일 07:10·15:10). 레이더 단서·사업보고서 수치 변화를 네이버·빙·구글로 기보도 대조해 미보도 후보/관련 보도 있음/같은 수치 선행/미확인으로 나눔. 하루 시작은 여기서. 기자가 킬한 후보는 숨김.',
    inputSchema: obj({ verdict: { type: 'string', enum: ['미보도 후보', '관련 보도 있음', '미확인', '같은 수치 선행'] },
      company: str('기업·낱말'), team: str('팀'), include_killed: bool('킬한 후보도 보기'), limit: int('줄 수', 1, 60) }) },
  { name: 'us_comments', access: 'private', handler: usComments,
    description: '미 연방 규제 의견서(regulations.gov): 현대차·기아·포스코·LS일렉트릭 등 출입처 명의로 NHTSA·EPA·IRS·재무부 등에 낸 의견서(최근 180일, 신규 표시, 도켓 제목·첨부 링크). 다른 단체의 인용은 제외.',
    inputSchema: obj({ company: str('기업·제출자·도켓 낱말'), only_new: bool('신규(최근 14일·처음 본 것)만'), limit: int('줄 수', 1, 60) }) },
  { name: 'page_changes', access: 'private', handler: pageChanges,
    description: '출입처 해외 공식 페이지 변경(현대차·기아·제네시스 미국 사이트): 출시 시점·한정 물량·가격·판매 상태·연식 문구가 직전 확인(첫 확인은 웹 아카이브 사본) 대비 바뀐 것. 공식 발표 아님 — 회사 확인 필요.',
    inputSchema: obj({ company: str('기업·페이지 낱말'), days: int('최근 N일(기본 14)', 1, 90), limit: int('줄 수', 1, 40),
      show_current: bool('페이지별 현재 문구도 보기') }) },
  { name: 'partner_filings', access: 'private', handler: partnerFilings,
    description: '해외 파트너 공시: 출입처와 계약·합작한 해외 상장사(ASX: 아라푸라·필바라, HKEX: BAIC Motor(베이징현대 합작 상대), 관계 근거 포함)의 최근 공시와, 출입처 이름이 들어간 미국 SEC EDGAR 공시(출입처 자신의 공시 제외)·본문 발췌.',
    inputSchema: obj({ company: str('기업·파트너·낱말'), source: { type: 'string', enum: ['ASX', 'HKEX', 'EDGAR'] }, only_new: bool('신규만'),
      include_routine: bool('일상 공시도 보기(ASX 주총·임원 지분, HKEX 월간 증권 변동·이사회 일정, EDGAR 투자 보유 표·같은 회사 반복 문구)'), limit: int('줄 수', 1, 60) }) },
  { name: 'trade_remedies', access: 'private', handler: tradeRemedies,
    description: '해외 무역구제 감시: EU 철강 쿼터(TARIC) 한국 관련 분기 쿼터 소진·사용률·직전 분기 비교(한국 전용/공동 구분), 미국 상무부·ITC 고시 중 한국산(본문에 나온 출입처 이름·줄), 호주·캐나다·인도 반덤핑 공고 목록의 한국 관련 새 줄.',
    inputSchema: obj({ section: { type: 'string', enum: ['quota', 'us', 'notices'] }, company: str('기업·품목·쿼터번호 낱말'),
      days: int('공고 변화 최근 N일(기본 30)', 1, 120), only_new: bool('미국 고시 신규만'), show_all: bool('여유 있는 쿼터까지 전부'),
      limit: int('구역별 줄 수', 1, 60) }) },
  { name: 'us_recalls', access: 'private', handler: usRecalls,
    description: '미국 리콜(NHTSA 전체 리콜 파일, 매일): 출입처 브랜드(현대차·기아·제네시스·아우디·폭스바겐·BMW·미니·벤츠·혼다), 한국GM 생산 차종(트랙스·트레일블레이저·엔비스타·앙코르 GX), 한국 타이어 3사, 결함 설명·원보고서(Part 573) 공급사 칸에 한국 부품사(모비스·만도·위아·SK온·LG에너지솔루션·삼성SDI 등) 이름이 나온 새 리콜. 대상 대수·부품·결함 원문.',
    inputSchema: obj({ company: str('브랜드·회사·차종·부품 낱말'), only_new: bool('신규만'), limit: int('줄 수', 1, 60) }) },
  { name: 'scoop_reverse', access: 'private', handler: scoopReverse,
    description: '경쟁지 [단독] 자동 역추적(매일): 최근 30일 업종 [단독] 기사마다 레이더가 기사 전에 같은 회사(그룹)·같은 사건 낱말 항목을 잡았는지 — 먼저 잡은 후보/같은 회사 항목만/없음, 원천별 건수와 몇 시간 앞섰는지. 자동 후보일 뿐 사람 판정(Y/P/N)과 별개.',
    inputSchema: obj({ verdict: { type: 'string', enum: ['먼저 잡은 후보', '같은 회사 항목만', '없음', '회사 미상'] }, company: str('기업·낱말'),
      days: int('최근 N일(기본 14, 최대 30)', 1, 30), limit: int('구역별 줄 수', 1, 60) }) },
  { name: 'us_epa', access: 'private', handler: usEpa,
    description: '미국 EPA 인증(fueleconomy.gov 차량 파일): 현대차·기아·제네시스의 새 EPA 등록 — 같은 회사에 이전 연식이 없는 새 모델, 전기차 주행거리 변화(직전 연식 대비), 연식 변경. 등록일·주행거리·연비. 국내 연비 신고는 해외 접속 차단으로 못 봄.',
    inputSchema: obj({ company: str('회사·차종 낱말'), kind: { type: 'string', enum: ['새 모델', '주행거리 변화', '연식 변경'] }, limit: int('줄 수', 1, 60) }) },
  { name: 'us_litigation', access: 'private', handler: usLitigation,
    description: '미국 소송·ITC 337조: 국제무역법원·연방순회항소법원 판결 중 출입처가 당사자로 적힌 것(판결문 첫머리 요지 원문·낱말 풀이), 출입처(미국 법인 포함)가 당사자인 연방법원 사건 접수(CourtListener, 국제무역법원·특허·계약·반독점 우선, 연방순회항소법원 사건은 원심·유형 한 줄, 소비자 소송은 접음)와 본문에 출입처 이름이 나온 ITC 337조 고시.',
    inputSchema: obj({ company: str('기업·사건명·분류 낱말'), only_new: bool('신규만'), include_routine: bool('소비자·제조물책임·개인 고용·위조품 단속 사건도 보기'),
      limit: int('줄 수', 1, 60) }) },
  { name: 'kr_official', access: 'private', handler: krOfficial,
    description: '국내 공식 원천: 출입처 공장등록(팩토리온) 새 공장·고용·주생산품·주소 변화와 최근 120일 등록 공장(계열사 제외), 관보 입법예고 중 출입처 업종(자동차·철강·전력·화학·통상) 관련.',
    inputSchema: obj({ section: { type: 'string', enum: ['factory', 'gazette'] }, company: str('기업·공장·법령 낱말'),
      days: int('공장 변화 최근 N일(기본 30)', 1, 120), show_all: bool('출입처 공장 전체 목록'), limit: int('구역별 줄 수', 1, 80) }) },
  { name: 'kr_signals', access: 'private', handler: krSignals,
    description: '국내 신호: 공정위 의결서(출입처가 피심인·발주처·사건명에 나온 것, 주문 발췌·과징금 분할납부 등), 한전 전자입찰(전력기기·전선 품목, 추정가격), 산업통상부 보도·참고자료(출입처 업종·이름, 엠바고, 월간 수출입 동향의 출입처 품목 수출액), 원자재 가격(KOMIS: LME 아연·동·연·니켈·알루미늄, 금·은, 철광석·원료탄, 탄산리튬 — 같은 기준 비교, 조회 범위 안 최고·최저와 한 달 변동).',
    inputSchema: obj({ section: { type: 'string', enum: ['ftc', 'kepco', 'motir', 'price'] }, company: str('기업·광종·낱말'),
      days: int('공정위 최근 N일(기본 60)', 1, 365), include_mentions: bool('공정위 본문 언급만 있는 것도 보기'), limit: int('구역별 줄 수', 1, 60) }) },
  { name: 'kr_stats', access: 'private', handler: krStats,
    description: '국내 월간 통계: 한국은행 ECOS 품목별 생산자·수출·수입물가(열연·냉연·후판·도금·철근·강관·나동선·아연·알루미늄·변압기·개폐기·승용차·타이어), KOSIS 철강협회 강종별 생산·광공업동향 품목(나동선·칼라강판·에틸렌·폴리에틸렌 생산·재고), KAIDA 수입 승용차 브랜드별 신규등록(순위·점유), 미국 Census 한국산 수입액(변압기·배전반·케이블·승용차·부품·타이어·열연·냉연·도금강판·강관·아연·석유제품·태양광 모듈). 새 달 수치의 조회 범위 안 최고·최저(날짜·값), 전년 대비, 연속 증감, 출입처 브랜드 순위 변화.',
    inputSchema: obj({ section: { type: 'string', enum: ['kaida', 'price', 'production', 'us_imports'] }, company: str('기업·품목·브랜드 낱말'),
      show_all: bool('신호 없는 계열도 보기'), limit: int('구역별 줄 수', 1, 60) }) },
  { name: 'trademarks', access: 'private', handler: trademarks,
    description: '출입처 상표 출원(KIPRIS Plus, 주 1회 월요일 수집): 새로 본 출원을 회사·상표명·상품류로 묶어 보여 줌(같은 날 같은 이름은 한 건). 처음 보는 이름+업종 핵심 상품류는 B. 저장된 결과만 읽고 KIPRIS를 새로 부르지 않음. 출원은 출시·진출 확정이 아님.',
    inputSchema: obj({ company: str('회사 낱말'), name: str('상표명 낱말'), class: str('상품류 번호(예: 12)'),
      days: int('최근 N일(기본 30)', 1, 120), show_all: bool('기존(기준선) 출원도 보기'), limit: int('줄 수', 1, 80) }) },
  { name: 'assembly_bills', access: 'private', handler: assemblyBills,
    description: '국회 법안: 열린국회정보 국회의원 발의법률안 중 출입 업종 법(자동차관리법·철강산업 특별법·전기사업법·전력망·분산에너지·관세법·화학물질·노조법 등) 새 발의(같은 법 같은 날은 한 줄)와 단계 변화(소관위 회부·상정·처리, 법사위, 본회의), 진행 중 법안 단계 요약. 저장된 결과만 읽음.',
    inputSchema: obj({ law: str('법 이름·의원·낱말'), days: int('최근 N일(기본 14)', 1, 120), include_related: bool('관련 낱말 법안(C)까지'),
      limit: int('구역별 줄 수', 1, 80) }) },
  { name: 'candidate_feedback', access: 'private', handler: judgeItems,
    description: '기자 판정 기록: 씀/킬/보류/봤음과 이유. 판정한 항목은 radar_today에서 숨김(봤음=판단 전이지만 다시 안 보기). item_ids로 여러 건 한 번에.',
    inputSchema: obj({ item_id: str('후보 번호(#id)·패키지 이름·단서 id(radar_today 줄의 id)'),
      item_ids: strList('여러 id를 한 번에(최대 60)'), verdict: { type: 'string', enum: FEEDBACK_VERDICTS },
      reason: str('이유 한 줄(봤음은 생략 가능)') }, ['verdict']) },
  { name: 'candidate_weekly_review', access: 'private', handler: weeklyReview,
    description: '주간 품질 점검: 최근 N일 판정(씀·킬·보류·봤음)을 감시별·종류별(DART는 공시 종류)·판정 때 등급별로 묶고, 킬이 몰린 묶음·일상(B)/C로 내렸는데 쓴 항목을 점검 후보로 표시. 가중치는 자동으로 바꾸지 않는다.',
    inputSchema: obj({ days: int('최근 N일(기본 7, 최대 60)', 1, 60) }) },
];

function rpcError(id, code, message) {
  return { jsonrpc: '2.0', id: id ?? null, error: { code, message } };
}

async function handleMessage(msg, ctx) {
  if (!msg || msg.jsonrpc !== '2.0' || typeof msg.method !== 'string') {
    return rpcError(msg?.id, -32600, 'Invalid Request');
  }
  const isNotification = !('id' in msg);
  if (isNotification) return null;
  const { id, method, params = {} } = msg;
  if (method === 'initialize') {
    const requested = params.protocolVersion;
    return { jsonrpc: '2.0', id, result: {
      protocolVersion: SUPPORTED_VERSIONS.includes(requested) ? requested : SUPPORTED_VERSIONS[0],
      capabilities: { tools: { listChanged: false } },
      serverInfo: SERVER_INFO,
      instructions: INSTRUCTIONS + (ctx.private ? '' : '\n(공개 연결: DART·네이버·나라장터 실시간·패키지 도구는 기자 전용 연결에서만)'),
    } };
  }
  if (method === 'ping') return { jsonrpc: '2.0', id, result: {} };
  if (method === 'tools/list') {
    const tools = TOOLS.filter((t) => t.access === 'public' || ctx.private)
      .map(({ name, description, inputSchema }) => ({ name, description, inputSchema }));
    return { jsonrpc: '2.0', id, result: { tools } };
  }
  if (method === 'tools/call') {
    const tool = TOOLS.find((t) => t.name === params.name);
    if (!tool || (tool.access === 'private' && !ctx.private)) return rpcError(id, -32602, `Unknown tool: ${params.name}`);
    try {
      return { jsonrpc: '2.0', id, result: await tool.handler(ctx, params.arguments ?? {}) };
    } catch (e) {
      return { jsonrpc: '2.0', id, result: textResult(`도구 실행 실패: ${String(e.message ?? e)} — 이 도구의 결과는 미확인으로 적는다.`, true) };
    }
  }
  return rpcError(id, -32601, `Method not found: ${method}`);
}

export async function authorize(pathname, env) {
  if (pathname === '/mcp' || pathname === '/mcp/') return { ok: true, private: false };
  const m = /^\/mcp\/([A-Za-z0-9_-]{16,128})\/?$/.exec(pathname);
  if (!m) return { ok: false };
  return (await safeEqual(m[1], env?.MCP_ACCESS_TOKEN)) ? { ok: true, private: true } : { ok: false };
}

export async function handleMcp(request, env, deps = {}) {
  const url = new URL(request.url);
  const auth = await authorize(url.pathname, env);
  if (!auth.ok) return new Response('Not found', { status: 404 });
  if (request.method === 'GET' || request.method === 'DELETE') {
    return new Response('This MCP server uses JSON responses over POST only.', { status: 405, headers: { Allow: 'POST' } });
  }
  if (request.method !== 'POST') return new Response('Method not allowed', { status: 405, headers: { Allow: 'POST' } });
  let payload;
  try { payload = await request.json(); } catch {
    return Response.json(rpcError(null, -32700, 'Parse error'), { status: 400 });
  }
  const ctx = { env, private: auth.private, fetch: deps.fetch ?? ((...a) => fetch(...a)), now: deps.now ?? new Date() };
  const batch = Array.isArray(payload);
  const messages = batch ? payload : [payload];
  const responses = (await Promise.all(messages.map((m) => handleMessage(m, ctx)))).filter(Boolean);
  if (!responses.length) return new Response(null, { status: 202 });
  const headers = { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' };
  return new Response(JSON.stringify(batch ? responses : responses[0]), { status: 200, headers });
}
