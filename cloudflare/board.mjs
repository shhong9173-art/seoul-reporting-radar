// 기자 전용 브라우저 화면: GET /r/<MCP_ACCESS_TOKEN>. 커넥터 주소(/mcp/<토큰>)와 같은 비밀 경로 방식이고, 자료는 radar_today와 같다.
// 공개 홈페이지(GitHub Pages)에는 미보도 단서를 싣지 않는다 — 누구나 볼 수 있어서다(11-01: 홈페이지 '단독감·미보도' 탭이 비어 보인다는 문의).
// 11-01 첫 화면은 도구 글을 그대로 옮겨 id·도구 이름·긴 주소가 섞여 읽기 어려웠다(기자: "평소 설명처럼 안 나오고 이상하다") —
// 항목 자료로 카드를 그린다: 무엇이 잡혔나(제목·사실 줄) / 보도 대조 / 원문 버튼. id·도구 이름은 접어 둔다. 같은 곳 같은 유형은 한 카드.
// 스크립트 없는 HTML. 토큰이 든 주소가 바깥 사이트로 새지 않게 Referrer-Policy no-referrer, 검색엔진·캐시 금지.
import { clampInt, safeEqual } from './common.mjs';
import { clipAt, convergenceRows, evidenceNote, kstStamp, radarTodayData, WATCHES } from './digest.mjs';

const HEADERS = {
  'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store, private', 'Referrer-Policy': 'no-referrer',
  'X-Robots-Tag': 'noindex, nofollow, noarchive', 'X-Content-Type-Options': 'nosniff',
  'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
};
export const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const when = (d) => (!d ? '' : String(d).length > 10 ? kstStamp(d) : String(d));
const safeUrl = (u) => (/^https?:\/\//i.test(String(u ?? '')) ? String(u) : '');
const link = (u, label, cls = 'btn') => (safeUrl(u) ? `<a class="${cls}" href="${esc(u)}" target="_blank" rel="noopener noreferrer">${esc(label)}</a>` : '');

// 괄호·낫표 안의 구분자는 건너뛰고 바깥의 구분자에서만 자른다('사유 '…' · …)' 같은 괄호 안 ' · '가 줄을 깨지 않게).
export function splitTop(text, sep) {
  const s = String(text ?? '');
  const out = [];
  let depth = 0;
  let start = 0;
  for (let i = 0; i < s.length; i += 1) {
    const c = s[i];
    if ('(「[（'.includes(c)) depth += 1;
    else if (')」]）'.includes(c)) depth = Math.max(0, depth - 1);
    else if (depth === 0 && s.startsWith(sep, i)) { out.push(s.slice(start, i)); start = i + sep.length; i += sep.length - 1; }
  }
  out.push(s.slice(start));
  return out.map((x) => x.trim()).filter(Boolean);
}

// 사실 줄 → 제목 한 줄 + 세부 줄 + 주의. ' — ' 뒤가 '…일 수 있음(회사 확인)'·'결함 확정 아님' 같은 단서 달기면 주의로,
// 아니면('— 정정 중 큰 변경(…)', '— 5번(평소 50.8→최근 0.18)') 핵심 사실이라 세부 줄에 둔다.
const HEDGE = /일 수 있음|회사 확인|확정 아님|확인 대상/;
export function factParts(fact) {
  const notes = [];
  const details = [];
  for (const seg of splitTop(fact, ' · ')) {
    const [main, ...rest] = splitTop(seg, ' — ');
    if (!rest.length && details.length && main.length < 60 && HEDGE.test(main)) { notes.push(main); continue; }
    details.push(main);
    const tail = rest.join(' — ');
    if (tail) (HEDGE.test(tail) ? notes : details).push(tail);
  }
  let title = details.shift() ?? '';
  // 첫 조각이 회사 이름뿐이면('금호타이어 · [기재정정]…') 다음 조각까지 제목으로
  if (title.length < 12 && details.length) title = `${title} · ${details.shift()}`;
  return { title, details, notes };
}

const PRESS = { '미보도 후보': 'pnew', '관련 보도 있음': 'pcov', '같은 수치 선행': 'pcov', 미확인: 'punk' };
function pressHtml(r, stamp) {
  if (!r) return '';   // 대조 전은 구역 머리의 '대조 전 N'으로만(카드마다 같은 줄이 되풀이돼 읽기 방해)
  const qs = (r.queries ?? []).map((q) => `“${esc(q)}”`).join(', ');
  const failed = Object.entries(r.channels ?? {}).filter(([, v]) => v.status !== 'ok').map(([k]) => k);
  const msg = r.verdict === '미보도 후보' ? `${qs}로 ${esc(r.since ?? '')} 이후 관련 기사를 못 찾음 — 검색 결과일 뿐 단독 판정 아님`
    : r.verdict === '미확인' ? `${failed.length ? `검색 채널 실패(${esc(failed.join(', '))})` : '사건을 특정하지 못함'} — 0건 아님`
      : `${qs}로 찾은 기사가 있음 — 같은 사건인지 열어 볼 것`;
  const ev = r.evidence ?? [];
  const shown = [...ev.filter((e) => !e.before).slice(0, 2), ...ev.filter((e) => e.before).slice(0, 1)];
  return `<div class="press ${PRESS[r.verdict] ?? 'punk'}"><b>보도 대조(자동 ${esc(stamp)}): ${esc(r.verdict)}</b> · ${msg}`
    + (shown.length ? `<ul>${shown.map((e) => `<li>${esc(e.date ?? '날짜?')} · ${esc(e.channel ?? '')} · ${safeUrl(e.url) ? link(e.url, e.title ?? '기사', 'plain') : esc(e.title ?? '')}<span class="muted">${esc(evidenceNote(e, r.verdict))}</span></li>`).join('')}</ul>` : '')
    + '</div>';
}

// 같은 등급·감시·회사·보도 대조 결과에 숫자만 다른 사실(현대제철 포항1공장 배출구 2·5·10번)은 한 카드로.
export function groupSame(rows, pressOf) {
  const groups = [];
  const at = new Map();
  for (const x of rows) {
    const key = [x.tier, x.watch, x.company, pressOf(x) ?? '', String(x.fact ?? '').replace(/\d[\d,.]*/g, '#')].join('|');
    if (at.has(key)) at.get(key).push(x);
    else { const g = [x]; at.set(key, g); groups.push(g); }
  }
  return groups;
}

function cardHtml(g, d) {
  const x = g[0];
  const v = d.pressOf(x);
  const { title, details, notes } = factParts(x.fact);
  const who = x.company && !title.includes(String(x.company).split('·')[0]) ? `${x.company} — ` : '';
  const more = g.slice(1);
  return `<article class="card t${esc(x.tier)}">
<div class="top"><span class="tier">${esc(x.tier)}</span>${v ? `<span class="pv ${PRESS[v] ?? 'punk'}">${esc(v)}</span>` : ''}<span class="watch">${esc(x.watch)}</span><span class="date">${esc(when(x.date))}</span></div>
<h3>${esc(who)}${esc(title)}</h3>
${details.length ? `<ul class="facts">${details.map((t) => `<li>${esc(t)}</li>`).join('')}</ul>` : ''}
${more.length ? `<p class="same">같은 곳 같은 유형 ${more.length}건 더</p><ul class="facts">${more.map((y) => `<li>${esc(factParts(y.fact).title)}</li>`).join('')}</ul>` : ''}
${notes.length ? `<p class="caution">${esc([...new Set(notes)].join(' / '))}</p>` : ''}
${pressHtml(d.checked.get(String(x.id)), kstStamp(d.press?.generatedAt))}
<div class="foot">${link(x.url, '원문 열기')}<details><summary>Claude에 넘길 id</summary><code>${g.map((y) => esc(y.id)).join('<br>')}</code><span class="muted"> · 자세히: ${esc(x.tool ?? '')}${d.judged.get(x.id) ? ` · 판정 ${esc(d.judged.get(x.id))}` : ''}</span></details></div>
</article>`;
}

function tierSection(t, label, d) {
  const rows = d.tiers[t];
  const groups = groupSame(rows, d.pressOf);
  const n = (v) => rows.filter((x) => d.pressOf(x) === v).length;
  const sum = rows.length ? `<span class="pill pnew">미보도 후보 ${n('미보도 후보')}</span><span class="pill pcov">관련 보도 있음 ${n('관련 보도 있음') + n('같은 수치 선행')}</span><span class="pill punk">미확인 ${n('미확인')}</span><span class="pill">대조 전 ${rows.filter((x) => !d.pressOf(x)).length}</span>` : '';
  return `<section><h2 class="h${t}">${esc(t)} · ${esc(label)} <span class="count">${rows.length}건</span></h2>${sum ? `<div class="pills">${sum}</div>` : ''}
${groups.length ? groups.map((g) => cardHtml(g, d)).join('\n') : '<p class="empty">이 기간 새 항목 없음</p>'}</section>`;
}

function convHtml(d) {
  if (!d.conv.length) return '';
  const groups = d.conv.slice(0, 6).map((g) => {
    const { rows, more } = convergenceRows(g);
    return `<article class="card conv"><h3>${g.fresh ? '<span class="pv pnew">새 항목</span> ' : ''}${esc(g.company)} · ${esc(g.place)} <span class="muted">감시 ${g.watches.length}곳이 가리킴</span></h3>
<p class="muted small">${esc(g.watches.join(' · '))}${d.coveredGroup(g) ? ' — 새 신호는 모두 관련 보도 있음(같은 사건인지 열어 볼 것)' : ''}</p>
<ul class="convrows">${rows.map((x) => `<li>${x.background ? '<span class="tag bg">배경</span>' : `<span class="tag t${esc(x.tier)}">${esc(x.tier)}</span>${d.pressOf(x) ? `<span class="pv ${PRESS[d.pressOf(x)] ?? 'punk'}">${esc(d.pressOf(x))}</span>` : ''}`}<span class="date">${esc(when(x.date))}</span> ${esc(x.watch)}: ${esc(clipAt(x.fact, 140))}${safeUrl(x.url) ? ` ${link(x.url, '원문', 'plain')}` : ''}</li>`).join('')}</ul>
${more ? `<p class="muted small">같은 묶음 ${more}줄 더</p>` : ''}</article>`;
  }).join('\n');
  return `<section><h2 class="hX">겹친 신호 <span class="count">${d.conv.length}곳</span></h2>
<p class="lead">최근 14일, 같은 출입처·같은 시군을 감시 여러 곳이 가리킨 곳. 하나씩은 공개 자료지만 함께 보면 투자·가동 변화 단서다. 같은 시군 이름으로 묶었을 뿐 같은 공장·사업이라는 확인은 아니다.</p>
${groups}${d.conv.length > 6 ? `<p class="muted">… 남은 ${d.conv.length - 6}곳(회사로 좁히기)</p>` : ''}</section>`;
}

function reverseHtml(d) {
  if (!d.firsts.length) return '';
  return `<section><h2 class="hX">경쟁지 단독 역추적 <span class="count">${d.firsts.length}건</span></h2>
<p class="lead">최근 14일 경쟁지 [단독] 가운데 레이더가 먼저 잡은 후보(자동). 같은 사실인지는 기자가 판정한다.</p>
${d.firsts.slice(0, 6).map((a) => `<article class="card rev"><div class="top"><span class="watch">${esc(a.source ?? '?')}</span><span class="date">${esc(kstStamp(a.published))}</span></div>
<h3>${esc(a.title ?? '')}</h3>
<p>레이더가 <b>${esc(a.best.leadHours)}시간 먼저</b>: ${esc(kstStamp(a.best.seen))} ${esc(a.best.label)} — ${esc(clipAt(a.best.text ?? '', 140))}</p>
<div class="foot"><details><summary>Claude에 넘길 id</summary><code>기사 ${esc(a.articleId)}<br>레이더 ${esc(a.best.id)}</code></details></div></article>`).join('\n')}</section>`;
}

export function boardPage(d, { hours, q, minor }) {
  const all = [...d.tiers.A, ...d.tiers.B];
  const unreported = all.filter((x) => d.pressOf(x) === '미보도 후보').length;
  const health = d.health.map((h) => h.replace(/^- /, ''));
  const chip = (label, params, on) => `<a class="chip${on ? ' on' : ''}" href="?${new URLSearchParams(params).toString()}">${esc(label)}</a>`;
  const base = { ...(q ? { q } : {}), ...(minor ? { minor: '1' } : {}) };
  const nav = [chip('24시간', { ...base, hours: 24 }, d.hours === 24), chip('72시간', { ...base, hours: 72 }, d.hours === 72), chip('7일', { ...base, hours: 168 }, d.hours === 168),
    chip(minor ? '참고(C) 숨기기' : '참고(C) 보기', { ...(q ? { q } : {}), ...(hours ? { hours } : {}), ...(minor ? {} : { minor: '1' }) }, false)].join('');
  const cRows = d.tiers.C;
  const hiddenN = Object.values(d.hiddenBy).reduce((a, b) => a + b, 0);
  return `<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><meta name="referrer" content="no-referrer"><title>오늘의 레이더 · 기자 전용</title>
<style>
:root{--bg:#f6f6f3;--fg:#1c2228;--mute:#5f6a74;--line:#dfe2e6;--card:#fff;--a:#b3261e;--b:#1f5fa8;--c:#6b7480;--new:#fff0a6;--newfg:#5a4300;--cov:#e8ecef;--unk:#fde7d6;--link:#0b5cad}
@media (prefers-color-scheme:dark){:root{--bg:#141719;--fg:#e6e9ec;--mute:#9aa5b0;--line:#2c3339;--card:#1c2125;--a:#ff8a80;--b:#8ab8ff;--c:#a5adb6;--new:#5a4b00;--newfg:#ffe9a0;--cov:#2a3137;--unk:#4a2f1c;--link:#8ab8ff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.6 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Malgun Gothic",sans-serif}
main{max-width:860px;margin:0 auto;padding:16px}a{color:var(--link)}
h1{font-size:21px;margin:0}.stamp{color:var(--mute);margin:2px 0 12px;font-size:14px}
.nav{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:0 0 14px}.chip{border:1px solid var(--line);border-radius:999px;padding:3px 11px;color:var(--fg);text-decoration:none;background:var(--card);font-size:14px}.chip.on{border-color:var(--fg);font-weight:700}
form{display:flex;gap:6px}input{font:inherit;font-size:14px;padding:3px 8px;border:1px solid var(--line);border-radius:6px;background:var(--card);color:var(--fg);width:140px}button{font:inherit;font-size:14px;padding:3px 10px;border:1px solid var(--line);border-radius:6px;background:var(--card);color:var(--fg)}
.summary{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:0 0 14px}.summary div{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:8px 10px}.summary b{display:block;font-size:22px;line-height:1.2}.summary span{font-size:12px;color:var(--mute)}
.warn{background:var(--unk);border-radius:10px;padding:8px 12px;margin:0 0 14px;font-size:14px}.warn ul{margin:4px 0 0;padding-left:18px}
section{margin:22px 0}h2{font-size:17px;margin:0 0 6px;padding-bottom:4px;border-bottom:2px solid var(--line)}h2 .count{font-weight:400;color:var(--mute);font-size:14px}
h2.hA{color:var(--a);border-color:var(--a)}h2.hB{color:var(--b);border-color:var(--b)}h2.hC{color:var(--c)}
.lead{color:var(--mute);font-size:14px;margin:4px 0 8px}.pills{display:flex;flex-wrap:wrap;gap:6px;margin:6px 0}.pill{font-size:12px;border-radius:999px;padding:1px 8px;background:var(--cov)}
.card{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--line);border-radius:10px;padding:10px 12px;margin:10px 0;overflow-wrap:anywhere}
.card.tA{border-left-color:var(--a)}.card.tB{border-left-color:var(--b)}.card.tC{border-left-color:var(--c)}
.top{display:flex;flex-wrap:wrap;gap:6px;align-items:center;font-size:12px;color:var(--mute)}.tier{font-weight:800;color:var(--fg)}.card.tA .tier{color:var(--a)}.card.tB .tier{color:var(--b)}
.watch{background:var(--cov);border-radius:4px;padding:0 6px}.date{margin-left:auto}.convrows .date{margin:0 4px}
.pv{font-size:12px;border-radius:4px;padding:0 6px;font-weight:700}.pnew{background:var(--new);color:var(--newfg)}.pcov{background:var(--cov)}.punk{background:var(--unk)}
h3{font-size:16px;margin:6px 0 4px;line-height:1.45}.facts{margin:4px 0;padding-left:18px}.facts li{margin:1px 0}
.same{margin:6px 0 0;font-size:13px;color:var(--mute)}.caution{margin:6px 0;font-size:13px;color:var(--mute)}
.press{margin:8px 0 4px;font-size:13px;border-radius:8px;padding:6px 8px;background:var(--cov)}.press.pnew{background:var(--new);color:var(--newfg)}.press.punk{background:var(--unk)}.press.none{background:none;padding:0;color:var(--mute)}.press ul{margin:4px 0 0;padding-left:18px}
.foot{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-top:6px}.btn{display:inline-block;border:1px solid var(--line);border-radius:6px;padding:2px 10px;text-decoration:none;font-size:14px}
details{font-size:12px;color:var(--mute)}summary{cursor:pointer}code{font-size:12px}.muted{color:var(--mute)}.small{font-size:13px}.empty{color:var(--mute)}
.convrows{list-style:none;padding:0;margin:6px 0}.convrows li{margin:4px 0;font-size:14px}.tag{font-size:11px;font-weight:800;border-radius:4px;padding:0 5px;margin-right:4px;background:var(--cov)}.tag.tA{color:var(--a)}.tag.tB{color:var(--b)}.tag.bg{font-weight:400}
.plain{color:var(--link)}footer{color:var(--mute);font-size:13px;margin:28px 0 8px}
@media (max-width:520px){.summary{grid-template-columns:repeat(2,1fr)}}
</style></head><body><main>
<h1>오늘의 레이더</h1>
<p class="stamp">${esc(kstStamp(d.now.toISOString()))} 기준 최근 ${esc(d.hours)}시간${d.monday && d.defaultHours ? '(월요일: 주말 포함)' : ''} · 기자 전용 감시 ${WATCHES.length}개${q ? ` · “${esc(q)}”로 좁힘` : ''}</p>
<div class="nav">${nav}<form method="get">${hours ? `<input type="hidden" name="hours" value="${esc(hours)}">` : ''}${minor ? '<input type="hidden" name="minor" value="1">' : ''}<input name="q" value="${esc(q)}" placeholder="회사·낱말"><button>찾기</button></form></div>
<div class="summary"><div><b>${d.tiers.A.length}</b><span>A 단독 후보·직접 변화</span></div><div><b>${d.tiers.B.length}</b><span>B 확인할 공식 변화</span></div><div><b>${unreported}</b><span>자동 대조 미보도 후보</span></div><div><b>${health.length}</b><span>수집 문제</span></div></div>
${health.length ? `<div class="warn"><b>먼저 볼 것: 수집 상태</b> — 실패한 곳의 0건은 '없음'이 아니라 미확인<ul>${health.map((h) => `<li>${esc(h)}</li>`).join('')}</ul></div>` : ''}
${tierSection('A', '단독 후보·직접 변화', d)}
${tierSection('B', '확인할 공식 변화', d)}
${convHtml(d)}
${reverseHtml(d)}
${minor ? tierSection('C', '참고', d) : (cRows.length ? `<section><h2 class="hC">C · 참고 <span class="count">${cRows.length}건</span></h2><p class="lead">소비자 소송·사이트 공통 문구·기보도 후보 등. ${chip('펼쳐 보기', { ...(q ? { q } : {}), ...(hours ? { hours } : {}), minor: '1' }, false)}</p></section>` : '')}
${hiddenN ? `<p class="muted small">판정한 ${hiddenN}건은 숨김(${esc(Object.entries(d.hiddenBy).map(([v, n]) => `${v} ${n}`).join(' · '))})</p>` : ''}
<footer><details><summary>읽는 법·규칙</summary><p>모두 자동 수집 단계다. A도 단독 확정이 아니다 — 원문 확인 → 보도 대조(낱말 바꿔 2~3번) → 회사 확인. 보도 대조(자동)는 네이버 뉴스 API·빙·구글에서 항목 날짜 3일 전부터 찾은 결과다. '미보도 후보'도 단독 판정이 아니고, '관련 보도 있음'은 같은 사건인지 열어 봐야 한다. 채널 실패는 미확인.</p>
<p>다 본 항목은 Claude에 id를 주고 "봤음"으로 표시하면 다음부터 안 뜬다(candidate_feedback).</p></details>
<p>이 주소는 비밀 열쇠가 든 기자 전용 주소다 — 공유하지 말 것.</p></footer>
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
  let html;
  try {
    html = boardPage(await radarTodayData(ctx, { hours, company: q, limit: 60, include_minor: minor }), { hours, q, minor });
  } catch (e) {
    html = `<!doctype html><meta charset="utf-8"><title>오늘의 레이더</title><p>불러오기 실패: ${esc(String(e?.message ?? e).slice(0, 200))} — 미확인(0건 아님)</p>`;
  }
  return new Response(request.method === 'HEAD' ? null : html, { status: 200, headers: HEADERS });
}
