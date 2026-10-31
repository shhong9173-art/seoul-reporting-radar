// 홈페이지 '단독감·미보도' 탭 로그인(11-01 기자 요청: "아이디 비번 넣고 로그인하게"). 아이디·비밀번호는 워커 비밀값
// BOARD_USER·BOARD_PASSWORD(Cloudflare에서 기자가 직접 등록 — 대화·저장소에 적지 않는다). 맞으면 30일짜리 세션을 준다:
// 'v1.<만료 ms>.<HMAC>' — 서버에 저장하지 않고 서명으로 확인한다. 비밀번호를 바꾸면 이전 세션은 모두 무효.
// 무차별 대입 막기: 아이피별 1시간 8번, 전체 1시간 40번 실패하면 1시간 잠금(실패 기록은 Durable Object).
import { safeEqual } from './common.mjs';
import { storeOp } from './store.mjs';

export const HOMEPAGE = 'https://shhong9173-art.github.io';
export const SESSION_DAYS = 30;
const IP_LIMIT = 8;
const ALL_LIMIT = 40;

export const loginConfigured = (env) => Boolean(env?.BOARD_USER && env?.BOARD_PASSWORD && env?.MCP_ACCESS_TOKEN);

const b64url = (bytes) => btoa(String.fromCharCode(...bytes)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
async function hmac(secret, text) {
  const key = await crypto.subtle.importKey('raw', new TextEncoder().encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  return b64url(new Uint8Array(await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(text))));
}
const secretOf = (env) => `${env.MCP_ACCESS_TOKEN}|${env.BOARD_PASSWORD}`;

export async function makeSession(env, nowMs) {
  const exp = nowMs + SESSION_DAYS * 86400000;
  return { session: `v1.${exp}.${await hmac(secretOf(env), `board-session|${env.BOARD_USER}|${exp}`)}`, exp };
}

export async function verifySession(env, token, nowMs) {
  if (!loginConfigured(env)) return false;
  const m = /^v1\.(\d{13})\.([A-Za-z0-9_-]{43})$/.exec(String(token ?? ''));
  if (!m || Number(m[1]) <= nowMs) return false;
  return safeEqual(m[2], await hmac(secretOf(env), `board-session|${env.BOARD_USER}|${m[1]}`));
}

export const sessionOf = (request) => (/^Bearer\s+(v1\.[0-9]+\.[A-Za-z0-9_-]+)$/.exec(request.headers.get('Authorization') ?? '') ?? [])[1] ?? '';

export function corsHeaders(request, extra = {}) {
  return request.headers.get('Origin') === HOMEPAGE
    ? { 'Access-Control-Allow-Origin': HOMEPAGE, Vary: 'Origin', ...extra } : { Vary: 'Origin' };
}
export function preflight(request) {
  return new Response(null, { status: 204, headers: corsHeaders(request, { 'Access-Control-Allow-Methods': 'GET, POST',
    'Access-Control-Allow-Headers': 'Authorization, Content-Type', 'Access-Control-Max-Age': '86400' }) });
}

// POST /auth/login — 본문 {"id","pw"}(text/plain JSON이라 사전 요청 없이 보낸다). 성공 {session, exp}, 실패 401, 잠금 429, 미설정 503.
export async function login(request, env, deps = {}) {
  if (request.method === 'OPTIONS') return preflight(request);
  const json = (body, status) => Response.json(body, { status, headers: { ...corsHeaders(request), 'Cache-Control': 'no-store' } });
  if (request.method !== 'POST') return json({ error: 'POST만' }, 405);
  if (!loginConfigured(env)) return json({ error: '로그인 미설정(BOARD_USER·BOARD_PASSWORD 비밀값 없음)' }, 503);
  const now = deps.now ?? new Date();
  const ctx = { env, now };
  const ip = request.headers.get('CF-Connecting-IP') ?? 'unknown';
  const since = new Date(now.getTime() - 3600000).toISOString();
  const { ip: ipFails, all } = await storeOp(ctx, 'login.count', { ip, since, purgeBefore: new Date(now.getTime() - 86400000).toISOString() });
  if (ipFails >= IP_LIMIT || all >= ALL_LIMIT) return json({ error: '실패가 많아 1시간 잠금' }, 429);
  let body = {};
  try { body = JSON.parse((await request.text()).slice(0, 2000)); } catch { /* 빈 본문은 실패로 센다 */ }
  const okUser = await safeEqual(String(body.id ?? ''), env.BOARD_USER);
  const okPw = await safeEqual(String(body.pw ?? ''), env.BOARD_PASSWORD);
  if (!(okUser && okPw)) {
    await storeOp(ctx, 'login.fail', { ip });
    return json({ error: '아이디 또는 비밀번호가 맞지 않음' }, 401);
  }
  return json(await makeSession(env, now.getTime()), 200);
}
