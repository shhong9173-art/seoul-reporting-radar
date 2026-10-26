// Worker entry: /mcp (Claude connector) + the existing 307 redirect to Pages.
import redirect from './redirect.mjs';
import { handleMcp } from './mcp.mjs';
import { handleIngest } from './screen.mjs';
export { RadarStore } from './store.mjs';

export default {
  async fetch(request, env, ctx) {
    const { pathname } = new URL(request.url);
    if (pathname === '/mcp' || pathname.startsWith('/mcp/')) return handleMcp(request, env);
    if (pathname.startsWith('/ingest/')) return handleIngest(request, env);
    return redirect.fetch(request, env, ctx);
  },
};
