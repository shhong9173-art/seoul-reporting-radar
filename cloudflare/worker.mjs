// Worker entry: /mcp (Claude connector), /r/<token> (reporter-only browser view), /b/<read key> (homepage tab fragment) + the existing 307 redirect to Pages.
import redirect from './redirect.mjs';
import { handleMcp } from './mcp.mjs';
import { handleIngest } from './screen.mjs';
import { runSchedule } from './dispatch.mjs';
import { radarItems } from './digest.mjs';
import { board, boardPart } from './board.mjs';
import { check, login } from './auth.mjs';
import { translateRoute } from './translate.mjs';
import { browserFileUpload, browserFiles, browserUpload } from './local_browser.mjs';
import { dartTextRoute, dartTextScanRoute } from './dart_text.mjs';
export { RadarStore } from './store.mjs';

export default {
  async fetch(request, env, ctx) {
    const { pathname } = new URL(request.url);
    if (pathname === '/mcp' || pathname.startsWith('/mcp/')) return handleMcp(request, env);
    if (pathname === '/ingest/radar-items') return radarItems(request, env);
    if (pathname.startsWith('/r/')) return board(request, env);   // 기자 전용 브라우저 화면(비밀 경로)
    if (pathname.startsWith('/b/')) return boardPart(request, env);   // 홈페이지 탭이 읽는 조각(로그인 세션·공개·읽기 전용 열쇠)
    if (pathname === '/auth/login') return login(request, env);       // 홈페이지 로그인(아이디·비밀번호 → 30일 세션)
    if (pathname === '/auth/check') return check(request, env);       // 사이트 첫 화면 잠금(gate.js)의 세션 확인
    if (pathname === '/ingest/translate') return translateRoute(request, env);   // 외신 제목 번역(Workers AI)
    if (pathname === '/upload/browser') return browserUpload(request, env);   // 기자 컴퓨터 Aside 직접 올리기(열쇠 지문 확인)
    if (pathname === '/upload/browser-file') return browserFileUpload(request, env);   // 기자 컴퓨터가 받은 호주 사건 문서 PDF 조각(같은 열쇠)
    if (pathname === '/ingest/browser-files') return browserFiles(request, env);       // 무역구제 감시가 그 PDF를 받아 가고 칸을 비운다(MCP 토큰)
    if (pathname === '/ingest/dart-text') return dartTextRoute(request, env);       // 정기보고서 감시가 받은 출입처 보고서 원문 글자(dart_find_text가 먼저 찾음)
    if (pathname === '/ingest/dart-text-scan') return dartTextScanRoute(request, env);   // 보고서 전체 새 낱말(이번·앞 보고서 줄 비교)
    if (pathname.startsWith('/ingest/')) return handleIngest(request, env);
    return redirect.fetch(request, env, ctx);
  },
  // Cloudflare cron (wrangler.json triggers): ask GitHub to run the morning watches on time.
  async scheduled(event, env, ctx) {
    ctx.waitUntil(runSchedule(env, new Date(event.scheduledTime)));
  },
};
