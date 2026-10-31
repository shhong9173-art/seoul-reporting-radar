// Worker entry: /mcp (Claude connector), /r/<token> (reporter-only browser view), /b/<read key> (homepage tab fragment) + the existing 307 redirect to Pages.
import redirect from './redirect.mjs';
import { handleMcp } from './mcp.mjs';
import { handleIngest } from './screen.mjs';
import { runSchedule } from './dispatch.mjs';
import { radarItems } from './digest.mjs';
import { board, boardPart } from './board.mjs';
export { RadarStore } from './store.mjs';

export default {
  async fetch(request, env, ctx) {
    const { pathname } = new URL(request.url);
    if (pathname === '/mcp' || pathname.startsWith('/mcp/')) return handleMcp(request, env);
    if (pathname === '/ingest/radar-items') return radarItems(request, env);
    if (pathname.startsWith('/r/')) return board(request, env);   // 기자 전용 브라우저 화면(비밀 경로)
    if (pathname.startsWith('/b/')) return boardPart(request, env);   // 홈페이지 탭이 읽는 조각(읽기 전용 열쇠)
    if (pathname.startsWith('/ingest/')) return handleIngest(request, env);
    return redirect.fetch(request, env, ctx);
  },
  // Cloudflare cron (wrangler.json triggers): ask GitHub to run the morning watches on time.
  async scheduled(event, env, ctx) {
    ctx.waitUntil(runSchedule(env, new Date(event.scheduledTime)));
  },
};
