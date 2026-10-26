// Streamable-HTTP MCP endpoint (JSON responses, no SSE) for the radar.
import { safeEqual, textResult } from './common.mjs';
import { bigPicture, clues, dandok, earnings, governance, health, stats } from './radar_tools.mjs';
import { dartFilings, dartFindText, g2bBids, newsCheck, sourceDocument } from './live_tools.mjs';
import { candidateFeedback, candidateSubmit, packageSave, scoopPackages, weeklyReview, PACKAGE_STATES } from './store.mjs';
import { POLICY, checkCandidate, formatCheck } from './scoring.mjs';
import { scoopScreen } from './screen.mjs';
import { pageChanges, usComments } from './overseas.mjs';

export const SUPPORTED_VERSIONS = ['2025-06-18', '2025-03-26', '2024-11-05'];
const SERVER_INFO = { name: 'seoul-reporting-radar', title: '산업부 취재 레이더', version: '1.0.0' };
const INSTRUCTIONS = [
  '산업부(자동차·철강·전력기기·에너지·화학) 취재 레이더. 기자는 홍성효.',
  '순서: scoop_screen(기자 전용, 미보도 후보부터) → radar_big_picture → radar_clues(days=3) → radar_stats → governance_changes → earnings_compare(실적 시즌) → dandok_monitor → scoop_packages(기자 전용).',
  '후보마다: source_document 또는 dart_find_text로 원문 확인 → news_check로 보도 대조(낱말 바꿔 2~3번, 한 번에 하나씩) → candidate_check.',
  '조회 실패·미설정·일부 성공은 0건이 아니라 미확인. 색인 0건은 미보도 증거가 아님. 단계(공개 원자료 추적/취재 단서·단독 미확정/단독 후보)를 올리지 않음.',
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
  facts: strList('원문으로 확인한 사실 문장'),
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
  { name: 'candidate_check', access: 'public', handler: async (ctx, args) => textResult(formatCheck(checkCandidate(args.candidate ?? args))),
    description: '후보 하나를 점수 정책으로 점검: 가점·감점, 추천/조사대기/탈락, 채울 것(원문·해시·보도 채널·질문·비교), 제목 숫자 근거, 지면감(톱/박스/단신). 저장하지 않는다.',
    inputSchema: obj({ candidate: CANDIDATE_SCHEMA }, ['candidate']) },
  { name: 'dart_filings', access: 'private', handler: dartFilings,
    description: 'OpenDART 공시 목록(실시간). 출입처 이름 또는 고유번호, 기간 YYYYMMDD. 조회 실패는 0건이 아니다.',
    inputSchema: obj({ company: str('출입처 이름(예: 현대제철)'), corp_code: str('DART 고유번호 8자리'),
      start: str('시작일 YYYYMMDD(기본 90일 전)'), end: str('종료일 YYYYMMDD') }) },
  { name: 'dart_find_text', access: 'private', handler: dartFindText,
    description: 'DART 공시 원문(document.xml)에서 낱말을 찾아 앞뒤 문맥과 파일별 해시를 준다. 건설중인자산·계약상대방·생산능력 같은 확인용.',
    inputSchema: obj({ rcp_no: str('접수번호 14자리'), word: str('찾을 낱말'), limit: int('문맥 수(기본 8)', 1, 20) }, ['rcp_no', 'word']) },
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
  { name: 'candidate_feedback', access: 'private', handler: candidateFeedback,
    description: '기자 판정 기록: 씀/킬/보류와 이유.',
    inputSchema: obj({ item_id: str('후보 번호(#id)·패키지 이름·단서 id'), verdict: { type: 'string', enum: ['씀', '킬', '보류'] },
      reason: str('이유 한 줄') }, ['item_id', 'verdict', 'reason']) },
  { name: 'candidate_weekly_review', access: 'private', handler: weeklyReview,
    description: '최근 N일 판정 성과(씀·킬·보류, 킬 사유 상위). 가중치는 자동으로 바꾸지 않는다.',
    inputSchema: obj({ days: int('최근 N일(기본 7)', 1, 60) }) },
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
