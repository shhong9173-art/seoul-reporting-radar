// GitHub Pages is the canonical, validated publisher. Never mirror stale JSON.
const BASE = 'https://shhong9173-art.github.io';
const PREFIX = '/seoul-reporting-radar';

export default {
  fetch(request) {
    if (!['GET', 'HEAD'].includes(request.method)) {
      return new Response('Method not allowed', {
        status: 405, headers: { Allow: 'GET, HEAD' }
      });
    }
    const source = new URL(request.url);
    const target = new URL(BASE);
    // Assign pathname rather than resolving an untrusted relative URL:
    // //other-host and query parameters can never change the destination host.
    target.pathname = source.pathname === PREFIX ? PREFIX + '/' :
      source.pathname.startsWith(PREFIX + '/') ? source.pathname :
      PREFIX + source.pathname;
    target.search = source.search;
    return new Response(null, {
      status: 307,
      headers: { Location: target.href, 'Cache-Control': 'no-store' }
    });
  }
};
