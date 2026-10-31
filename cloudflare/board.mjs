// 기자 전용 브라우저 화면: GET /r/<MCP_ACCESS_TOKEN>. 커넥터 주소(/mcp/<토큰>)와 같은 비밀 경로 방식이고, 내용은 radar_today와 같다.
// 공개 홈페이지(GitHub Pages)에는 미보도 단서를 싣지 않는다 — 누구나 볼 수 있어서다(11-01: 홈페이지 '단독감·미보도' 탭이 비어 보인다는 문의).
// 스크립트 없는 HTML. 토큰이 든 주소가 바깥 사이트로 새지 않게 Referrer-Policy no-referrer, 검색엔진·캐시 금지.
import { clampInt, safeEqual } from './common.mjs';
import { radarTodayText } from './digest.mjs';

const HEADERS = {
  'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store, private', 'Referrer-Policy': 'no-referrer',
  'X-Robots-Tag': 'noindex, nofollow, noarchive', 'X-Content-Type-Options': 'nosniff',
  'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
};
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const URL_RE = /https?:\/\/[^\s<>"'「」]+/g;

// 한 줄을 이스케이프하고 주소는 새 창 링크로. 끝에 붙은 구두점·괄호는 링크 밖으로.
export function lineHtml(line) {
  let out = '';
  let last = 0;
  for (const m of line.matchAll(URL_RE)) {
    let u = m[0];
    const trail = /[).,·;:…]+$/.exec(u)?.[0] ?? '';
    if (trail && !(trail.startsWith(')') && u.includes('('))) u = u.slice(0, u.length - trail.length);
    out += esc(line.slice(last, m.index)) + `<a href="${esc(u)}" target="_blank" rel="noopener noreferrer">${esc(u)}</a>`;
    last = m.index + u.length;
  }
  out += esc(line.slice(last));
  return out.replace(/미보도 후보/g, '<mark>미보도 후보</mark>').replace(/관련 보도 있음/g, '<span class="cov">관련 보도 있음</span>');
}

export function boardHtml(text, { hours, q, minor }) {
  const lines = text.split('\n');
  const body = [];
  let open = false;
  const close = () => { if (open) { body.push('</section>'); open = false; } };
  lines.forEach((raw, i) => {
    const line = raw.replace(/\s+$/, '');
    if (!line.trim()) return;
    if (i === 0) { body.push(`<p class="stamp">${lineHtml(line)}</p>`); return; }
    const head = /^\[(.+?)\](.*)$/.exec(line);
    if (head) {
      close();
      const tier = /^([ABC]) · /.exec(head[1])?.[1];
      body.push(`<h2 class="${tier ? `t${tier}` : 'sec'}">${lineHtml(`${head[1]}`)}<small>${lineHtml(head[2])}</small></h2>`);
      return;
    }
    if (line.startsWith('- ')) {
      close();
      body.push(`<section class="item"><p class="it">${lineHtml(line.slice(2))}</p>`);
      open = true;
      return;
    }
    if (/^\s{3,}/.test(line) && open) { body.push(`<p class="sub${/보도 대조\(자동/.test(line) ? ' press' : ''}">${lineHtml(line.trim())}</p>`); return; }
    close();
    body.push(`<p class="note">${lineHtml(line.trim())}</p>`);
  });
  close();
  const link = (label, params, on) => `<a class="chip${on ? ' on' : ''}" href="?${new URLSearchParams(params).toString()}">${esc(label)}</a>`;
  const base = { ...(q ? { q } : {}), ...(minor ? { minor: '1' } : {}) };
  const nav = [link('24시간', { ...base, hours: 24 }, hours === 24), link('72시간', { ...base, hours: 72 }, hours === 72), link('7일', { ...base, hours: 168 }, hours === 168),
    link(minor ? '참고(C) 숨기기' : '참고(C) 보기', { ...(q ? { q } : {}), ...(hours ? { hours } : {}), ...(minor ? {} : { minor: '1' }) }, false)].join('');
  return `<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><meta name="referrer" content="no-referrer"><title>오늘의 레이더 · 기자 전용</title>
<style>
:root{--bg:#f7f7f5;--fg:#1d2329;--mute:#5d6873;--line:#dde1e5;--card:#fff;--a:#b3261e;--b:#1f5fa8;--c:#6b7480;--mark:#fff1a8;--link:#0b5cad}
@media (prefers-color-scheme:dark){:root{--bg:#15181b;--fg:#e6e9ec;--mute:#9aa5b0;--line:#2c3339;--card:#1d2226;--a:#ff8a80;--b:#8ab8ff;--c:#a5adb6;--mark:#5a4b00;--link:#8ab8ff}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.6 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Malgun Gothic",sans-serif}
main{max-width:920px;margin:0 auto;padding:16px}
h1{font-size:20px;margin:4px 0 6px}.stamp{color:var(--mute);margin:0 0 10px}
nav{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:8px 0 14px}
.chip{border:1px solid var(--line);border-radius:999px;padding:3px 10px;color:var(--fg);text-decoration:none;background:var(--card)}.chip.on{border-color:var(--fg);font-weight:600}
form{display:flex;gap:6px}input{font:inherit;padding:3px 8px;border:1px solid var(--line);border-radius:6px;background:var(--card);color:var(--fg);width:150px}
button{font:inherit;padding:3px 10px;border:1px solid var(--line);border-radius:6px;background:var(--card);color:var(--fg)}
h2{font-size:16px;margin:22px 0 8px;padding-top:10px;border-top:2px solid var(--line)}h2 small{display:block;font-weight:400;color:var(--mute);font-size:13px}
h2.tA{color:var(--a);border-color:var(--a)}h2.tB{color:var(--b);border-color:var(--b)}h2.tC{color:var(--c)}
.item{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 12px;margin:8px 0;overflow-wrap:anywhere}
.it{margin:0 0 4px;font-weight:600}.sub{margin:2px 0;color:var(--fg)}.press{color:var(--mute)}.note{color:var(--mute);margin:4px 0;overflow-wrap:anywhere}
mark{background:var(--mark);color:inherit;padding:0 2px;font-weight:700}.cov{color:var(--mute);text-decoration:underline dotted}
a{color:var(--link)}footer{color:var(--mute);font-size:13px;margin:24px 0}
</style></head><body><main>
<h1>오늘의 레이더 <small style="font-weight:400;color:var(--mute);font-size:14px">기자 전용 · radar_today와 같은 내용</small></h1>
<nav>${nav}<form method="get">${hours ? `<input type="hidden" name="hours" value="${esc(hours)}">` : ''}${minor ? '<input type="hidden" name="minor" value="1">' : ''}<input name="q" value="${esc(q)}" placeholder="회사·낱말로 좁히기"><button>찾기</button></form></nav>
${body.join('\n')}
<footer>이 주소는 비밀 열쇠가 든 기자 전용 주소다 — 공유하지 말 것. 모두 자동 수집 단계이고 '미보도 후보'도 단독 판정이 아니다. 판정(봤음·Y/P/N)은 Claude에서 candidate_feedback으로.</footer>
</main></body></html>`;
}

export async function board(request, env, deps = {}) {
  const url = new URL(request.url);
  const m = /^\/r\/([A-Za-z0-9_-]{16,128})\/?$/.exec(url.pathname);
  if (!m || !(await safeEqual(m[1], env?.MCP_ACCESS_TOKEN))) return new Response('Not found', { status: 404 });
  if (request.method !== 'GET' && request.method !== 'HEAD') return new Response('Method not allowed', { status: 405, headers: { Allow: 'GET' } });
  const ctx = { env, private: true, fetch: deps.fetch ?? ((...a) => fetch(...a)), now: deps.now ?? new Date() };
  const p = url.searchParams;
  const hours = p.has('hours') ? clampInt(p.get('hours'), 1, 336, 24) : undefined;
  const q = String(p.get('q') ?? '').trim().slice(0, 60);
  const minor = p.get('minor') === '1';
  let text;
  try {
    text = await radarTodayText(ctx, { hours, company: q, limit: 60, include_minor: minor });
  } catch (e) {
    text = `오늘의 레이더 · 불러오기 실패\n[오류] ${String(e?.message ?? e).slice(0, 200)} — 미확인(0건 아님)`;
  }
  return new Response(request.method === 'HEAD' ? null : boardHtml(text, { hours, q, minor }), { status: 200, headers: HEADERS });
}
