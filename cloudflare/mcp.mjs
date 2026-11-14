// Streamable-HTTP MCP endpoint (JSON responses, no SSE) for the radar.
import { safeEqual, textResult } from './common.mjs';
import { bigPicture, clues, dandok, earnings, governance, health, stats } from './radar_tools.mjs';
import { dartFilings, dartFindText, g2bBids, newsCheck, sourceDocument } from './live_tools.mjs';
import { candidateSubmit, packageSave, scoopPackages, FEEDBACK_VERDICTS, PACKAGE_STATES } from './store.mjs';
import { judgeItems, weeklyReview } from './review.mjs';
import { customsTrade, ecosData, ecosFind, kosisData, kosisFind } from './stats_live.mjs';
import { POLICY, checkVerifiedCandidate, formatCheck } from './scoring.mjs';
import { scoopScreen } from './screen.mjs';
import { krFuel, krOfficial, krSignals, krStats, pageChanges, partnerFilings, scoopReverse, tradeRemedies, usComments, usEpa, usLitigation, usRecalls } from './overseas.mjs';
import { trademarks } from './trademarks.mjs';
import { patentsAbroad } from './patents_abroad.mjs';
import { assemblyBills } from './assembly.mjs';
import { radarToday } from './digest.mjs';
import { scoopDesk } from './desk.mjs';
import { annotateHandled, loadLedger } from './handled.mjs';
import { BROWSER_CITIES, BROWSER_LABOR, BROWSER_PAGES, VIAS, browserUploadKey, localNoticeSubmit } from './local_browser.mjs';

export const SUPPORTED_VERSIONS = ['2025-06-18', '2025-03-26', '2024-11-05'];
const SERVER_INFO = { name: 'seoul-reporting-radar', title: '산업부 취재 레이더', version: '1.0.0' };
const INSTRUCTIONS = [
  '산업부(자동차·철강·전력기기·에너지·화학) 취재 레이더. 기자는 홍성효.',
  '하루 시작은 radar_today(기자 전용): 감시 35개의 새 항목을 A(단독 후보·직접 변화)/B(확인할 공식 변화)로 모아 보여 주고, 실패·오래된 감시를 먼저 알린다. 항목마다 자세히 볼 도구가 붙어 있다.',
  "단독 후보를 달라는 요청에는 scoop_desk부터(기자 전용): 기자가 이미 처리한 건(킬·보류·답변 대기·예약·후배에게 넘김·작성 중)과 이미 보도된 것, 여러 번 킬한 유형을 걷어내고 기자가 실제로 단독을 쓴 유형부터 보여 준다. 맨 아래 '기자가 이미 처리한 건' 목록과 같은 사건은 어디서 찾았든 다시 내지 않는다 — 새 사실이 붙었을 때만, 무엇이 새로운지 밝히고 낸다. 구역 도구의 줄 끝 〔이미 처리: …〕 표시도 같은 뜻이다. 후보가 약하면 약하다고 말하고 개수를 채우지 않는다.",
  '기자가 후보를 킬·보류하거나 회사에 문의해 답을 기다리거나 후배에게 넘기거나 예약을 걸면 그 자리에서 기록한다: 레이더 항목은 candidate_feedback(item_ids, verdict, reason), 그 밖은 package_save(state=접음/보류/발제함, item_ids=[관련 레이더 id·원문 주소]). 기록하지 않으면 다음에 또 나온다.',
  '순서: radar_today → scoop_screen(기자 전용, 미보도 후보부터) → page_changes·us_comments·partner_filings(해외 낙찰·영국 법인 등기·인도 법인 공시 포함)·trade_remedies(국내 무역위원회 회의 안건 포함)·us_litigation·us_recalls·us_epa(기자 전용, 해외 원천) → kr_official(기자 전용, 공장등록·관보·협력사 회생·파산·공장 부지 건축허가·지자체 고시·공고·사업장 인력(국민연금)·굴뚝 측정(가동 신호)·노동위 회의(조정·심판)·노조 성명·지방의회 회의록) → kr_fuel(기자 전용, 국내 연비 신고·자동차리콜센터 무상점검·수리 공지) → kr_signals(기자 전용, 타사 공시 속 출입처·임원 명단 변화·공정위 의결서·한전 입찰·원자재 가격·전기위원회 발전사업 허가·원안위 안건) → kr_stats(기자 전용, 물가지수·철강 생산·수입차 등록·완성차 모델별·공장별 판매; 발제 검증은 ecos_find·ecos_data·kosis_find·kosis_data·customs_trade 즉석 조회) → trademarks(기자 전용, 출입처 상표 출원 주 1회) → patents_abroad(기자 전용, 출입처 유럽·국제 특허 공개 주 1회) → assembly_bills(기자 전용, 출입 업종 국회 법안 발의·단계) → radar_big_picture → radar_clues(days=3) → radar_stats → governance_changes → earnings_compare(실적 시즌) → dandok_monitor → scoop_packages(기자 전용).',
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
    description: '공식 원문(go.kr·DART·KIND·KIPRIS·.gov·EU·해외 무역구제 기관(인도 DGTR·캐나다 CBSA·영국 TRA 등 정부 도메인)·출입처 홈페이지)을 열어 텍스트 구간과 내용 해시(sha256)를 돌려준다. DART 공시 링크는 틀 대신 본문 문서를 읽고 다른 첨부 문서 주소도 준다. 긴 문서는 offset으로 이어 읽는다.',
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
    description: '취재 패키지 저장·갱신(비공개 저장소). 발제문·근거·이미 났나·약점·확인 필요·물을 곳을 body에. 기자가 처리한 건(킬=접음, 답변 대기·예약·후배에게 넘김=보류, 작성 중=발제함)은 item_ids에 관련 레이더 항목 id나 원문 주소를 넣어 저장한다 — 그 항목이 단독 추천(scoop_desk·radar_today)에서 빠지고 구역 도구에 〔이미 처리〕 표시가 붙는다. 제목은 사건이 드러나게(회사·사건 번호·품목), 처리 상태는 제목 앞 [답변 대기]·[예약 중]·[후배 토스]·[킬]로.',
    inputSchema: obj({ name: str('짧은 영문/한글 이름(예: lselectric-busan-capa)'), title: str('한 줄 요약'),
      state: { type: 'string', enum: PACKAGE_STATES }, body: str('패키지 전문'),
      item_ids: strList('이 건과 이어지는 레이더 항목 id(줄 끝 id …)나 원문 주소(최대 30)') }, ['name', 'title', 'state', 'body']) },
  { name: 'candidate_submit', access: 'private', handler: candidateSubmit,
    description: `후보를 재점검해 저장(하루 추천 ${POLICY.dailyLimit}건 한도, 같은 날 중복 제목 제외).`,
    inputSchema: obj({ candidates: { type: 'array', items: CANDIDATE_SCHEMA, maxItems: 10 } }, ['candidates']) },
  { name: 'local_notice_submit', access: 'private', handler: localNoticeSubmit,
    description: `기자 컴퓨터 브라우저로 읽은 목록 올리기(예약 작업용). cities: 해외 IP에서 막히는 시·군 새올 고시·공고(${Object.keys(BROWSER_CITIES).join('·')}) — 목록 첫 쪽 줄마다 관리번호(searchDetail 안 숫자)와 칸 글자만, 저장 뒤 지자체 고시·공고 감시를 한 번 실행 요청(1시간 안 재요청 없음). pages: 해외 IP에서 막히는 무역구제 공고 목록(${Object.keys(BROWSER_PAGES).join('·')}) — 한국이 든 줄의 칸 글자와 그 줄 링크(같은 사이트)만, 다음 정기 무역구제 감시에 반영. labor: 노동위원회 회의일정 달력(중앙·지방 14곳)이 돌려준 회의마다 '회의번호/순번/회의일/회의명' 한 줄(오늘부터 45일 안), 저장 뒤 노동위 회의 감시를 한 번 실행 요청(5시간 안 재요청 없음). 글자를 고치거나 요약하지 말 것. 읽지 못한 곳은 rows 없이 error에 이유. rows[].detail: 출입처 이름이 든 줄의 상세 페이지 글자(전체 제목·본문 앞 400자·첨부 파일 이름, 시·군마다 8줄까지, attachments는 첨부 공고문 글자 앞 4000자) — Aside 수집 코드가 붙인 그대로. via: 수집 길(aside·browser).`,
    inputSchema: obj({ labor: { type: 'array', maxItems: 14, items: obj({ commission: { type: 'string', enum: BROWSER_LABOR },
      rows: { type: 'array', maxItems: 300, items: { type: 'string' }, description: "회의마다 '회의번호/순번/회의일/회의명' 한 줄(예: 2611021110520048685/4/20261104/조정회의)" },
      error: str('읽지 못했을 때 이유') }, ['commission']) },
    pages: { type: 'array', maxItems: 5, items: obj({ id: { type: 'string', enum: Object.keys(BROWSER_PAGES) },
      rows: { type: 'array', maxItems: 200, items: obj({ cells: { type: 'array', maxItems: 10, items: { type: 'string' } },
        links: { type: 'array', maxItems: 4, items: { type: 'string' } } }, ['cells']) },
      error: str('읽지 못했을 때 이유') }, ['id']) },
    cities: { type: 'array', maxItems: 20, items: obj({
      city: { type: 'string', enum: Object.keys(BROWSER_CITIES) },
      rows: { type: 'array', maxItems: 60, items: obj({ mgt: str('관리번호(searchDetail(\'…\') 안의 값)'),
        cells: { type: 'array', maxItems: 14, items: { type: 'string' }, description: '그 줄 칸 글자(빈 칸 빼고 화면 순서대로)' },
        detail: obj({ title: str('상세 페이지 전체 제목'), body: str('본문 앞 400자'), files: { type: 'array', maxItems: 6, items: { type: 'string' }, description: '첨부 파일 이름' },
          attachments: { type: 'array', maxItems: 3, description: '첨부 공고문 글자(hwpx 앞 4000자) 또는 못 읽은 이유',
            items: obj({ name: str('첨부 파일 이름'), text: str('공고문 글자 앞부분'), error: str('못 읽은 이유') }, ['name']) } }) }, ['mgt', 'cells']) },
      error: str('읽지 못했을 때 이유(예: TypeError: Failed to fetch)') }, ['city']) },
    via: { type: 'string', enum: VIAS, description: '수집 길: aside(기자 컴퓨터 Aside REPL) · browser(내장 브라우저)' },
    uploadKeySha256: str('Aside 직접 올리기 열쇠의 SHA-256 지문(16진수 64자, 등록 코드가 찍은 FINGERPRINT) — browser_upload_key와 같은 등록. 새로 등록하면 이전 열쇠는 못 씀') }) },
  { name: 'browser_upload_key', access: 'private', handler: browserUploadKey,
    description: '기자 컴퓨터 Aside가 수집 결과를 직접 올릴 때 쓰는 열쇠의 SHA-256 지문 등록(열쇠 글자는 받지 않는다 — 열쇠는 기자 컴퓨터 Aside 브라우저의 이 사이트 저장소에만 있다). sha256 없이 부르면 등록 상태(지문 앞 8자·등록·마지막 올림 시각). 새로 등록하면 이전 열쇠는 못 쓴다.',
    inputSchema: obj({ sha256: str('열쇠의 SHA-256 16진수 64자(Aside 등록 코드가 찍은 FINGERPRINT 값)') }) },
  { name: 'scoop_desk', access: 'private', handler: scoopDesk,
    description: "단독 데스크 — 단독 후보를 달라는 요청에는 여기부터. radar_today와 같은 항목(최근 N일)에서 ① 기자가 이미 처리한 것(처리 장부: 접음·보류(답변 대기·예약·후배에게 넘김)·발제함 패키지와 판정) ② 자동 보도 대조가 '관련 보도 있음'인 것 ③ 기자가 여러 번 킬한 유형(굴뚝 측정·미국 서비스 캠페인·국민연금 현장명·지방의회 발언·다른 회사 임원 명단·제목뿐인 해외 파트너 공시 등)을 걷어내고, 기자가 실제로 단독을 쓴 유형(국내 무역위 신청·판정 예고, 미국 법원·ITC 당사자 사건, 해외 무역구제·규제 문서, 공시 정정·소송·계약, 공장 부지 건축허가)부터 보여 준다. 출입처가 신청인인 무역위 사건의 다가오는 일정(21일), 앞서 추천했고 판정 없는 것, 걷어낸 건수와 이유, 기자가 최근 30일 처리한 건 목록을 함께 준다. 등급(A·B·C)은 바꾸지 않는다. 후보가 없으면 없다고 나온다 — 약한 것으로 채우지 않는다.",
    inputSchema: obj({ days: int('최근 N일(기본 7, 최대 14)', 1, 14), company: str('기업·낱말로 거르기'),
      include_weak: bool('걷어낸 약한 유형도 펼쳐 보기'), limit: int('후보 줄 수(기본 12)', 1, 40) }) },
  { name: 'radar_today', access: 'private', handler: radarToday,
    description: '오늘의 레이더(하루 시작): 기자 전용 감시 35개(단독 후보 심사, 공장등록·관보, 공정위·한전·원자재, 월간 통계, 무역구제, 미국 소송, 미국 OSHA, 미국 주 환경 허가·공고, 해외 파트너 공시, 미 의견서, 해외 페이지, 상표 출원, 해외 특허 공개(EP·WO), 국회 법안, 미국 리콜, 미국 EPA 인증, 국내 연비 신고, 해외 발주처 낙찰, 협력사 회생·파산, 전기위·원안위, 공장 부지 건축허가, 해외 법인 등기, 지자체 고시·공고, 사업장 인력, 굴뚝 측정, 노동위 회의, 노조 성명, 지방의회 회의록, 인도 법인 공시, 타사 공시 속 출입처, 지분·자사주 변동, 임원 명단 변화, 수시 임원 공시·타사 임원 명단, 문제 임원 점검, 출입처 외신)에서 최근 N시간(기본 24, 월요일 72) 새 항목만 모아 A(단독 후보·직접 변화)/B(확인할 공식 변화)/C(참고)로 정렬. A·B 항목마다 자동 보도 대조 결과(평일 08:50·12:50·18:50, 항목 날짜 3일 전 이후 네이버·빙·구글: 미보도 후보·관련 보도 있음·미확인)를 붙이고 미보도 후보를 먼저 보여 줌. 실패·오래된 감시를 맨 위에 표시. 기자가 판정(씀·킬·보류·봤음)한 항목은 숨김, 줄마다 id.',
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
    description: '해외 파트너 공시: 출입처와 계약·합작한 해외 상장사(ASX: 아라푸라·필바라, HKEX: BAIC Motor(베이징현대 합작 상대), 관계 근거 포함)의 최근 공시와, 출입처 이름이 들어간 미국 SEC EDGAR 공시(출입처 자신의 공시 제외)·본문 발췌. 아래에 해외 발주처 낙찰 공고(EU TED·영국 Find a Tender·세계은행·바레인 월간 보고서·대만 정부조달(대만전력 등)에서 출입처가 낙찰자 칸에 적힌 것, 금액·계약일)와 영국 법인 설립 등기(Companies House, 출입처 본사가 지배 주주인 새 법인; 키 COMPANIES_HOUSE_API_KEY), 인도 상장 법인 공시(NSE 공시 RSS의 현대차 인도법인 — 인수·설비·로열티 A, 이사회 결과·보도자료·임원 변경 B, 첨부 PDF 첫머리; source=NSE면 이것만)도 붙인다(source를 비울 때).',
    inputSchema: obj({ company: str('기업·파트너·낱말'), source: { type: 'string', enum: ['ASX', 'HKEX', 'EDGAR', 'NSE'] }, only_new: bool('신규만'),
      include_routine: bool('일상 공시도 보기(ASX 주총·임원 지분, HKEX 월간 증권 변동·이사회 일정, EDGAR 투자 보유 표·같은 회사 반복 문구)'), limit: int('줄 수', 1, 60) }) },
  { name: 'trade_remedies', access: 'private', handler: tradeRemedies,
    description: '무역구제 감시: EU 철강 쿼터(TARIC) 한국 관련 분기 쿼터 소진·사용률·직전 분기 비교(한국 전용/공동 구분), 미국 상무부·ITC 고시 중 한국산(본문에 나온 출입처 이름·줄), 캐나다·인도·영국·인도네시아·베트남 무역구제 기관 목록의 한국 관련 새 줄, 국내 무역위원회(section=ktc: 회의 약 1주 전 공개되는 안건(개요 PDF의 의결·보고 목록), 2019년 이후 개시한 진행 사건의 진행일정 새 줄·판정시한 연장·진행 목록에서 빠짐, 보도자료), 무역협회 대한 수입규제DB(section=kita: 세계 각국의 한국산 반덤핑·상계관세·세이프가드 새 사건과 진행 단계·업체별 마진, 출입처 업체 이름), 미국 ITC 문서 시스템 EDIS(section=edis: 한국산 반덤핑·상계관세 청원, 출입처가 당사자인 서면(337 재검토 청원·답변서 등), 표지에 출입처 이름이 든 새 337 특허 제소장, 지켜보는 337 조사의 위원회·판사 결정 — 공개본 본문 발췌 포함, show_all=true면 출석 통지·상대방 서면 등 일상 문서까지), 영국 무역구제청 공개기록(section=tra: 한국산 진행 조사에 당사자들이 낸 문서 — 출입처·한국 정부가 낸 문서, 조사기관의 판단·쟁점 문서(특별시장상황·대표 제3국·잠정/최종 판정 등), 본문에 출입처 이름이 나온 다른 당사자 문서; 낸 곳·제목·파일 이름·첫 PDF 본문 대목). 캐나다 CBSA(section=cbsa: 조사·종료재심·행정재심 목록의 한국 관련 사건 — 결론 예정일·문서 줄, 시행 중 조치에서 정상가격을 받은 한국 수출자 표(출입처 이름·협조 시작·마지막 개정); 기준선 뒤 새 문서·상태 바뀜).',
    inputSchema: obj({ section: { type: 'string', enum: ['quota', 'us', 'notices', 'ktc', 'kita', 'edis', 'tra', 'cbsa'] }, company: str('기업·품목·쿼터번호·나라 낱말'),
      days: int('공고 변화 최근 N일(기본 30)', 1, 120), only_new: bool('미국 고시 신규만'), show_all: bool('여유 있는 쿼터까지 전부'),
      limit: int('구역별 줄 수', 1, 60) }) },
  { name: 'us_recalls', access: 'private', handler: usRecalls,
    description: '미국 리콜(NHTSA 전체 리콜 파일, 매일): 출입처 브랜드(현대차·기아·제네시스·아우디·폭스바겐·BMW·미니·벤츠·혼다), 한국GM 생산 차종(트랙스·트레일블레이저·엔비스타·앙코르 GX), 한국 타이어 3사, 결함 설명·원보고서(Part 573) 공급사 칸에 한국 부품사(모비스·만도·위아·SK온·LG에너지솔루션·삼성SDI 등) 이름이 나온 새 리콜. 대상 대수·부품·결함 원문. 아래에 NHTSA 결함조사(ODI) 개시·종결(최근 120일, 리콜 전 단계 신호), 출입처 차종 소비자 결함 신고 급증(최근 28일 대 앞 24주), 제조사 통신(현대차·기아·제네시스·한국GM 생산 차종의 서비스 캠페인·보증 프로그램·안전 관련 서비스 공지, 최근 120일 — 리콜 아닌 무상수리·보증 연장 신호, 문서 PDF 링크)도 붙인다.',
    inputSchema: obj({ company: str('브랜드·회사·차종·부품 낱말'), only_new: bool('신규만'), show_all: bool('제조사 통신 참고(C)까지'), limit: int('줄 수', 1, 60) }) },
  { name: 'scoop_reverse', access: 'private', handler: scoopReverse,
    description: '경쟁지 [단독] 자동 역추적(매일): 최근 30일 업종 [단독] 기사마다 레이더가 기사 전에 같은 회사(그룹)·같은 사건 낱말 항목을 잡았는지 — 먼저 잡은 후보/같은 회사 항목만/없음, 원천별 건수와 몇 시간 앞섰는지. 자동 후보일 뿐 사람 판정(Y/P/N)과 별개.',
    inputSchema: obj({ verdict: { type: 'string', enum: ['먼저 잡은 후보', '같은 회사 항목만', '없음', '회사 미상'] }, company: str('기업·낱말'),
      days: int('최근 N일(기본 14, 최대 30)', 1, 30), limit: int('구역별 줄 수', 1, 60) }) },
  { name: 'kr_fuel', access: 'private', handler: krFuel,
    description: '국내 자동차 표시연비 신고(에너지공단 공공데이터): 출입처 브랜드(현대차·기아·KG모빌리티·르노코리아·한국GM·벤츠·BMW·폭스바겐·아우디·혼다)의 새 연비 신고 — 같은 업체에 처음 보는 모델명, 전기차 1회 충전 주행거리 변화, 사양·연식 추가. 등록일·연비·CO2·주행거리. 출시 확정 아님. 아래에 자동차리콜센터 무상점검·수리 게시판의 출입처 브랜드 새 공지(매일 06:10, 평일 11:30·14:30·16:30)도 붙인다 — 제작사·차명·대상 대수·생산기간·내용·조치(공지 원문). 무상수리는 리콜이 아니고 보도자료가 따로 없는 경우가 많다. kind를 주면 연비 신고만.',
    inputSchema: obj({ company: str('회사·차종 낱말'), kind: { type: 'string', enum: ['새 모델명', '주행거리 변화', '사양·연식 추가'] }, show_all: bool('무상점검·수리: 다른 브랜드 글까지'), limit: int('줄 수', 1, 60) }) },
  { name: 'us_epa', access: 'private', handler: usEpa,
    description: '미국 EPA 인증(fueleconomy.gov 차량 파일): 현대차·기아·제네시스의 새 EPA 등록 — 같은 회사에 이전 연식이 없는 새 모델, 전기차 주행거리 변화(직전 연식 대비), 연식 변경. 등록일·주행거리·연비. 국내 연비 신고는 kr_fuel.',
    inputSchema: obj({ company: str('회사·차종 낱말'), kind: { type: 'string', enum: ['새 모델', '주행거리 변화', '연식 변경'] }, limit: int('줄 수', 1, 60) }) },
  { name: 'us_litigation', access: 'private', handler: usLitigation,
    description: '미국 소송·ITC 337조: 국제무역법원·연방순회항소법원 판결 중 출입처가 당사자로 적힌 것(판결문 첫머리 요지 원문·낱말 풀이), 출입처(미국 법인 포함)가 당사자인 연방법원 사건 접수(CourtListener, 국제무역법원·특허·계약·반독점 우선, 연방순회항소법원 사건은 원심·유형 한 줄, 소비자 소송은 접음)와 본문에 출입처 이름이 나온 ITC 337조 고시, 미국 OSHA(산업안전보건청) 점검·위반 — 출입처 미국 법인·공장(현대차 앨라배마·기아 조지아·현대모비스·한국타이어 테네시·한화큐셀 등)의 사망·중대사고·사고·민원 점검, 위반 통지(고의·반복·중대)와 벌금, 사고 요약(정기·후속 점검은 include_routine). · 미국 주 환경청 허가·공고(조지아 EPD 주간 공고·앨라배마 ADEM·루이지애나 LDEQ — 출입처 미국 공장의 대기 허가 신청·허가안·제재 공고, 조지아 대기 허가 발급 목록(PSD/NSR 등), 루이지애나 상공위원회 안건의 세제 감면(ITEP)·고용 인센티브 줄, 매일 07:05) 구역 함께',
    inputSchema: obj({ company: str('기업·사건명·분류 낱말'), only_new: bool('신규만'), include_routine: bool('소비자·제조물책임·개인 고용·위조품 단속 사건도 보기'),
      limit: int('줄 수', 1, 60) }) },
  { name: 'kr_official', access: 'private', handler: krOfficial,
    description: '국내 공식 원천: 출입처 공장등록(팩토리온) 새 공장·고용·주생산품·주소 변화와 최근 120일 등록 공장(계열사 제외), 관보 입법예고 중 출입처 업종(자동차·철강·전력·화학·통상) 관련, 법제처 확정 발령(section=law: 출입 업종 행정규칙(고시·훈령·예규)·법령의 새 제정·개정과 법제처 법령해석례 — 현행 목록에 새로 생긴 일련번호, 부처·발령일·시행일), 협력사 회생·파산 공고(대법원 회생·파산 공고 15개 법원·회생회사 M&A 공고에서 공장등록 업종이 철강·비철·자동차 부품·전기장비·화학인 제조사; 업종·주생산품·종업원 수 붙임), 출입처 공장과 같은 번지의 건축인허가(신축·증축·사용승인, 연면적·허가일·착공예정일; 건축주는 비공개; section=building), 출입처 공장이 있는 시·군(당진·아산·여수·울주·울산 북구·포항·광양·완주·봉화·광주 광산·서구·광명·나주·인천 부평·구미·청주·순천·함평 등 40곳 — 부평·구미·청주·순천·함평은 해외 IP 차단으로 기자 컴퓨터 브라우저 예약 수집)의 고시·공고 중 제목에 출입처 이름·공장 사업이 나온 것(건설공사 안전점검 수행기관 지정·환경영향평가 공람·산업단지 계획·공유수면 등; section=local), 출입처 사업장 인력(국민연금 가입 사업장 월 자료: 자사 본사·공장의 가입자 수 지난달·1년 전 대비, 그달 신규 취득·상실, 탈퇴·새 사업장, 시공사가 출입처 이름을 넣어 만든 새 공사·용역 현장(신설·증설 낱말); section=workforce), 출입처 공장 굴뚝 자동측정(TMS) 가동 신호(배출구별 측정값을 3시간마다 쌓아 평소 움직이던 배출구가 멈춘 사업장·새 배출구·목록에서 빠진 배출구, 그 배출구 배출허용기준을 넘은 측정값; section=stacks), 노동위원회 회의(중앙·지방 14곳 첫 화면 오늘 회의의 사건명 앞 당사자가 출입처인 노동쟁의 조정·교섭·부당노동행위·구제신청, 위원회마다 첫 화면 5건 상한)와 노조 성명·보도자료(금속노조·화섬식품노조 공개 게시판 새 글에 출입처 이름 — 사망·사고·파업·매각·분할·가처분 등 A; section=labor), 지방의회 회의록(국회도서관 지방의정포털: 출입처 이름 대목에 인허가·불법·오염·감면·증설·이전·야적 등; 키 CLIK_API_KEY; section=council).',
    inputSchema: obj({ section: { type: 'string', enum: ['factory', 'gazette', 'law', 'insolvency', 'building', 'local', 'workforce', 'stacks', 'labor', 'council'] }, company: str('기업·공장·법령·회생 회사 낱말'),
      days: int('공장 변화 최근 N일(기본 30)', 1, 120), show_all: bool('출입처 공장 전체 목록'), limit: int('구역별 줄 수', 1, 80) }) },
  { name: 'kr_signals', access: 'private', handler: krSignals,
    description: '국내 신호: 타사 공시 속 출입처(출입처가 아닌 회사의 DART 양수도·영업양수·지분 거래·공급계약·생산중단 공시에 출입처가 거래상대·계약상대로 적힌 것 — 예: 국도화학 공시의 ㈜LG화학 대산 BPA 영업양수; section=counterparty), 공정위 의결서(출입처가 피심인·발주처·사건명에 나온 것, 주문 발췌·과징금 분할납부 등), 공정위 보도·참고·설명자료(제목에 출입처 이름·출입 업종 낱말; 의결서보다 먼저 나옴; section=ftc_press), 한전 전자입찰(전력기기·전선 품목, 추정가격), 나라장터 낙찰(출입처가 낙찰자인 물품·공사·용역·외자, 10억원 이상은 큰 낙찰; section=g2b), 산업통상부 보도·참고자료(출입처 업종·이름, 엠바고, 월간 수출입 동향의 출입처 품목 수출액), 기후에너지환경부·국토교통부·관세청·조달청 보도자료(정책브리핑 목록, 제목에 출입처 이름·업종 낱말; 리콜·배출가스·전력망·원전·수소·우회수출·원산지·공공비축 등; section=briefing), 시·도 보도자료(울산·충남·전남광주: 출입처 이름이나 투자협약·증설·산업위기+업종 낱말; section=province), 원자재 가격(KOMIS: LME 아연·동·연·니켈·알루미늄, 금·은, 철광석·원료탄, 탄산리튬 — 같은 기준 비교, 조회 범위 안 최고·최저와 한 달 변동), 전기위원회 발전사업 허가(회차별 개최결과 PDF·3MW 초과 허가대장)와 원자력안전위원회 상정 안건·의결 결과(section=energy), 임원 명단 변화(출입처 분기·반기·사업보고서 \'임원 현황\'을 바로 앞 보고서와 비교 — 새로 보인·빠진 임원, 직위·등기 변경, \'보고서 제출일 현재 변동사항\'; 오너 일가(관계 칸)·경쟁사·해외 경쟁사 출신·전관·임기 중 빠짐·다른 출입처 임원 표시; 같은 칸 아래 수시 임원 공시 — 시장 전체 독립이사 선임·해임·중도퇴임 신고와 대표이사 변경 중 출입처 회사 출신(전 대표·고위 임원이면 A), 출입처 주총 소집공고 이사 후보(부실기업 경영진 여부·체납·결격 칸), 상장사 등기임원 명단 순환 조회 속 출입처 임원 출신과 출입처 출신 타사 등기임원 현황(company에 출입처·회사·사람 낱말), 문제 임원 점검(출입처 등기임원·미등기 사장급 한 사람씩: 독립이사 법정 결격 가능 — 상법 시행령 제34조⑤ 7호 6년 초과·3호 다른 회사 이사·감사 2곳 이상·1호 계열사 최근 3년 근무 — 와 과거 논란 기사); section=exec, show_all=true면 C까지).',
    inputSchema: obj({ section: { type: 'string', enum: ['ftc', 'ftc_press', 'kepco', 'g2b', 'motir', 'briefing', 'province', 'price', 'energy', 'counterparty', 'exec'] }, company: str('기업·광종·사업·사람·낱말'),
      days: int('공정위 최근 N일(기본 60)', 1, 365), include_mentions: bool('공정위 본문 언급만 있는 것도 보기'), show_all: bool('임원 명단 변화의 C(일반 미등기 변동)까지'), limit: int('구역별 줄 수', 1, 80) }) },
  { name: 'kr_stats', access: 'private', handler: krStats,
    description: '국내 월간 통계: 한국은행 ECOS 품목별 생산자·수출·수입물가(나프타·휘발유·경유·제트유·에틸렌·프로필렌·PE·PP·합성고무, 열연·냉연·후판·도금·철근·강관·나동선·아연·알루미늄·변압기·개폐기·승용차·타이어), KOSIS 철강협회 강종별 생산·광공업동향 품목(나동선·칼라강판·에틸렌·폴리에틸렌 생산·재고, 휘발유·경유·프로필렌·PP·합성고무 생산, 경유·제트유·합성고무 수출), KAIDA 수입 승용차 브랜드별 신규등록(순위·점유), 미국 Census 한국산 수입액(변압기·배전반·케이블·승용차·부품·타이어·열연·냉연·도금강판·강관·아연·석유제품·태양광 모듈), 현대차·기아 IR 엑셀 모델별(국내 판매·국내 공장 수출)·해외 공장별 월간 판매(끊김·급감·급증·첫 판매·세대 교체, 직전 3개월 평균과 전년 같은 달 비교; section=carsales, company에 모델·공장 낱말이면 최근 6개월 값). 새 달 수치의 조회 범위 안 최고·최저(날짜·값), 전년 대비, 연속 증감, 출입처 브랜드 순위 변화.',
    inputSchema: obj({ section: { type: 'string', enum: ['kaida', 'price', 'production', 'us_imports', 'carsales'] }, company: str('기업·품목·브랜드·모델·공장 낱말'),
      show_all: bool('신호 없는 계열도 보기'), limit: int('구역별 줄 수', 1, 60) }) },
  { name: 'trademarks', access: 'private', handler: trademarks,
    description: '출입처 상표 출원(KIPRIS Plus, 주 1회 월요일 수집 · 유럽연합 EUIPO 출원 구역 함께): 새로 본 출원을 회사·상표명·상품류로 묶어 보여 줌(같은 날 같은 이름은 한 건). 처음 보는 이름+업종 핵심 상품류는 B. 저장된 결과만 읽고 KIPRIS를 새로 부르지 않음. 출원은 출시·진출 확정이 아님.',
    inputSchema: obj({ company: str('회사 낱말'), name: str('상표명 낱말'), class: str('상품류 번호(예: 12)'),
      days: int('최근 N일(기본 30)', 1, 120), show_all: bool('기존(기준선) 출원도 보기'), limit: int('줄 수', 1, 80) }) },
  { name: 'patents_abroad', access: 'private', handler: patentsAbroad,
    description: '출입처 해외 특허 공개(EPO OPS 3.2, 주 1회 토요일 수집): 유럽특허(EP)·국제특허(PCT·WO) 공개 중 출원인이 출입처인 것(공동 출원 포함) — 새로 본 공개를 회사·제목·IPC(기술 분야)·우선권·Espacenet 원문으로, 같은 패밀리는 한 묶음. 우선권 한국 출원이 레이더 특허 감시(KIPRIS)에 있으면 국내 공개(한글 제목)를 붙이고, 한국 출원 없이 해외 우선권만 있으면 표시, 회사 기술 분야(IPC) 이력에 없던 분야는 "처음 보는 기술 분야"(이력 180일 뒤부터). 공개는 출원 약 18개월 뒤라 개발 완료·양산이 아님. EPO 서버 과부하로 멈춘 회사는 미확인. 저장된 결과만 읽고 EPO를 새로 부르지 않음(약관상 기자 전용).',
    inputSchema: obj({ company: str('회사 낱말'), query: str('제목·IPC·출원인 낱말(예: battery, H01M)'), office: { type: 'string', enum: ['EP', 'WO'] },
      link: { type: 'string', enum: ['kr', 'abroad', 'new_field'], description: 'kr=국내 공개(KIPRIS)와 이어진 것만, abroad=해외 우선권(국내보다 해외 먼저일 수 있음)만, new_field=처음 보는 기술 분야만' },
      days: int('처음 본 날 기준 최근 N일(기본 30)', 1, 200), show_all: bool('기준선(기존) 공개도 보기(공개일 기준)'), limit: int('묶음 수', 1, 80) }) },
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
    description: '주간 품질 점검: 최근 N일 판정(씀·킬·보류·봤음)을 감시별·종류별(DART는 공시 종류)·판정 때 등급별로 묶고, 킬이 몰린 묶음·일상(B)/C로 내렸는데 쓴 항목을 점검 후보로 표시. 끝에 자동 대조: 기자(홍성효)가 쓴 아이뉴스24 출입처 기사마다 레이더가 먼저 잡은 항목이 있었는지(감시별). 가중치는 자동으로 바꾸지 않는다.',
    inputSchema: obj({ days: int('최근 N일(기본 7, 최대 60)', 1, 60) }) },
];

// 구역 도구는 '지금 상태'를 보여 줘서 기자가 이미 처리한 건(답변 대기 중인 OSHA 점검, 접은 무역구제 사건)이 볼 때마다 다시 나온다(11-13).
// 결과 글의 항목마다 처리 장부와 맞춰 줄 끝에 〔이미 처리: …〕를 붙인다. 장부를 못 읽으면 결과를 그대로 둔다.
const MARK_HANDLED = new Set(['kr_official', 'kr_signals', 'kr_stats', 'kr_fuel', 'trade_remedies', 'us_litigation', 'us_recalls', 'us_epa', 'us_comments',
  'partner_filings', 'page_changes', 'trademarks', 'patents_abroad', 'assembly_bills', 'scoop_screen', 'governance_changes', 'radar_clues']);
async function markHandled(ctx, result) {
  try {
    const part = (result?.content ?? []).find((c) => c.type === 'text');
    if (!part || result.isError) return result;
    const { text, marked } = annotateHandled(part.text, await loadLedger(ctx));
    if (!marked) return result;
    part.text = `${text}\n\n처리 장부: 〔이미 처리〕 ${marked}건은 기자가 킬·보류(답변 대기·예약·후배에게 넘김)·작성 중으로 남긴 건이다 — 단독 후보로 다시 내지 않는다. 〔처리 이력 있음〕은 처리한 뒤 새로 잡힌 줄이라 새 사실인지 확인한다.`;
    return result;
  } catch {
    return result;
  }
}

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
      // 도구가 늘면 버전도 바뀌게(1.<도구 수>.0): 버전으로 도구 목록을 기억하는 클라이언트가 다시 받도록.
      serverInfo: { ...SERVER_INFO, version: `1.${TOOLS.length}.0` },
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
      const result = await tool.handler(ctx, params.arguments ?? {});
      return { jsonrpc: '2.0', id, result: ctx.private && MARK_HANDLED.has(tool.name) ? await markHandled(ctx, result) : result };
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
