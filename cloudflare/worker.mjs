// Worker entry: /mcp (Claude connector) + the existing 307 redirect to Pages.
import redirect from './redirect.mjs';
import { handleMcp } from './mcp.mjs';
import { handleIngest } from './screen.mjs';
import { runSchedule } from './dispatch.mjs';
import { radarItems } from './digest.mjs';
export { RadarStore } from './store.mjs';

export default {
  async fetch(request, env, ctx) {
    const { pathname } = new URL(request.url);
    if (pathname === '/mcp' || pathname.startsWith('/mcp/')) return handleMcp(request, env);
    if (pathname === '/ingest/radar-items') return radarItems(request, env);
    if (pathname.startsWith('/ingest/')) return handleIngest(request, env);
    return redirect.fetch(request, env, ctx);
  },
  // Cloudflare cron (wrangler.json triggers): ask GitHub to run the morning watches on time.
  async scheduled(event, env, ctx) {
    ctx.waitUntil(runSchedule(env, new Date(event.scheduledTime)));
  },
};
