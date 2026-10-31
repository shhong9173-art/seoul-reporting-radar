// 기자 전용 브라우저 화면: GET /r/<MCP_ACCESS_TOKEN>. 커넥터 주소(/mcp/<토큰>)와 같은 비밀 경로 방식이고, 자료는 radar_today와 같다.
// 공개 홈페이지(GitHub Pages)에는 미보도 단서를 싣지 않는다 — 누구나 볼 수 있어서다(11-01: 홈페이지 '단독감·미보도' 탭이 비어 보인다는 문의).
// 11-01 첫 화면은 도구 글을 그대로 옮겨 id·도구 이름·긴 주소가 섞여 읽기 어려웠다(기자: "평소 설명처럼 안 나오고 이상하다") —
// 항목 자료로 카드를 그린다: 무엇이 잡혔나(제목·사실 줄) / 보도 대조 / 원문 버튼. id·도구 이름은 접어 둔다. 같은 곳 같은 유형은 한 카드.
// 스크립트 없는 HTML. 토큰이 든 주소가 바깥 사이트로 새지 않게 Referrer-Policy no-referrer, 검색엔진·캐시 금지.
import { clampInt, safeEqual } from './common.mjs';
import { corsHeaders, HOMEPAGE, loginConfigured, preflight, sessionOf, verifySession } from './auth.mjs';
import { clipAt, convergenceRows, evidenceNote, kstStamp, radarTodayData, WATCHES } from './digest.mjs';

const HEADERS = {
  'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store, private', 'Referrer-Policy': 'no-referrer',
  'X-Robots-Tag': 'noindex, nofollow, noarchive', 'X-Content-Type-Options': 'nosniff',
  'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
};
export const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const when = (d) => (!d ? '' : String(d).length > 10 ? kstStamp(d) : String(d));
const safeUrl = (u) => (/^https?:\/\//i.test(String(u ?? '')) ? String(u) : '');
const link = (u, label, cls = 'rb-btn') => (safeUrl(u) ? `<a class="${cls}" href="${esc(u)}" target="_blank" rel="noopener noreferrer">${esc(label)}</a>` : '');

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
  return `<div class="rb-press ${PRESS[r.verdict] ?? 'punk'}"><b>보도 대조(자동 ${esc(stamp)}): ${esc(r.verdict)}</b> · ${msg}`
    + (shown.length ? `<ul>${shown.map((e) => `<li>${esc(e.date ?? '날짜?')} · ${esc(e.channel ?? '')} · ${safeUrl(e.url) ? link(e.url, e.title ?? '기사', 'rb-plain') : esc(e.title ?? '')}<span class="rb-muted">${esc(evidenceNote(e, r.verdict))}</span></li>`).join('')}</ul>` : '')
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
  return `<article class="rb-card rb-t${esc(x.tier)}">
<div class="rb-top"><span class="rb-tier">${esc(x.tier)}</span>${v ? `<span class="rb-pv ${PRESS[v] ?? 'punk'}">${esc(v)}</span>` : ''}<span class="rb-watch">${esc(x.watch)}</span><span class="rb-date">${esc(when(x.date))}</span></div>
<h3>${esc(who)}${esc(title)}</h3>
${details.length ? `<ul class="rb-facts">${details.map((t) => `<li>${esc(t)}</li>`).join('')}</ul>` : ''}
${more.length ? `<p class="rb-same">같은 곳 같은 유형 ${more.length}건 더</p><ul class="rb-facts">${more.map((y) => `<li>${esc(factParts(y.fact).title)}</li>`).join('')}</ul>` : ''}
${notes.length ? `<p class="rb-caution">${esc([...new Set(notes)].join(' / '))}</p>` : ''}
${pressHtml(d.checked.get(String(x.id)), kstStamp(d.press?.generatedAt))}
<div class="rb-foot">${link(x.url, '원문 열기')}<details><summary>Claude에 넘길 id</summary><code>${g.map((y) => esc(y.id)).join('<br>')}</code><span class="rb-muted"> · 자세히: ${esc(x.tool ?? '')}${d.judged.get(x.id) ? ` · 판정 ${esc(d.judged.get(x.id))}` : ''}</span></details></div>
</article>`;
}

function tierSection(t, label, d) {
  const rows = d.tiers[t];
  const groups = groupSame(rows, d.pressOf);
  const n = (v) => rows.filter((x) => d.pressOf(x) === v).length;
  const sum = rows.length ? `<span class="rb-pill pnew">미보도 후보 ${n('미보도 후보')}</span><span class="rb-pill pcov">관련 보도 있음 ${n('관련 보도 있음') + n('같은 수치 선행')}</span><span class="rb-pill punk">미확인 ${n('미확인')}</span><span class="rb-pill">대조 전 ${rows.filter((x) => !d.pressOf(x)).length}</span>` : '';
  return `<section><h2 class="rb-h${t}">${esc(t)} · ${esc(label)} <span class="rb-count">${rows.length}건</span></h2>${sum ? `<div class="rb-pills">${sum}</div>` : ''}
${groups.length ? groups.map((g) => cardHtml(g, d)).join('\n') : '<p class="rb-empty">이 기간 새 항목 없음</p>'}</section>`;
}

function convHtml(d) {
  if (!d.conv.length) return '';
  const groups = d.conv.slice(0, 6).map((g) => {
    const { rows, more } = convergenceRows(g);
    return `<article class="rb-card rb-conv"><h3>${g.fresh ? '<span class="rb-pv pnew">새 항목</span> ' : ''}${esc(g.company)} · ${esc(g.place)} <span class="rb-muted">감시 ${g.watches.length}곳이 가리킴</span></h3>
<p class="rb-muted rb-small">${esc(g.watches.join(' · '))}${d.coveredGroup(g) ? ' — 새 신호는 모두 관련 보도 있음(같은 사건인지 열어 볼 것)' : ''}</p>
<ul class="rb-convrows">${rows.map((x) => `<li>${x.background ? '<span class="rb-tag bg">배경</span>' : `<span class="rb-tag t${esc(x.tier)}">${esc(x.tier)}</span>${d.pressOf(x) ? `<span class="rb-pv ${PRESS[d.pressOf(x)] ?? 'punk'}">${esc(d.pressOf(x))}</span>` : ''}`}<span class="rb-date">${esc(when(x.date))}</span> ${esc(x.watch)}: ${esc(clipAt(x.fact, 140))}${safeUrl(x.url) ? ` ${link(x.url, '원문', 'rb-plain')}` : ''}</li>`).join('')}</ul>
${more ? `<p class="rb-muted rb-small">같은 묶음 ${more}줄 더</p>` : ''}</article>`;
  }).join('\n');
  return `<section><h2 class="rb-hX">겹친 신호 <span class="rb-count">${d.conv.length}곳</span></h2>
<p class="rb-lead">최근 14일, 같은 출입처·같은 시군을 감시 여러 곳이 가리킨 곳. 하나씩은 공개 자료지만 함께 보면 투자·가동 변화 단서다. 같은 시군 이름으로 묶었을 뿐 같은 공장·사업이라는 확인은 아니다.</p>
${groups}${d.conv.length > 6 ? `<p class="rb-muted">… 남은 ${d.conv.length - 6}곳(회사로 좁히기)</p>` : ''}</section>`;
}

function reverseHtml(d) {
  if (!d.firsts.length) return '';
  return `<section><h2 class="rb-hX">경쟁지 단독 역추적 <span class="rb-count">${d.firsts.length}건</span></h2>
<p class="rb-lead">최근 14일 경쟁지 [단독] 가운데 레이더가 먼저 잡은 후보(자동). 같은 사실인지는 기자가 판정한다.</p>
${d.firsts.slice(0, 6).map((a) => `<article class="rb-card rb-rev"><div class="rb-top"><span class="rb-watch">${esc(a.source ?? '?')}</span><span class="rb-date">${esc(kstStamp(a.published))}</span></div>
<h3>${esc(a.title ?? '')}</h3>
<p>레이더가 <b>${esc(a.best.leadHours)}시간 먼저</b>: ${esc(kstStamp(a.best.seen))} ${esc(a.best.label)} — ${esc(clipAt(a.best.text ?? '', 140))}</p>
<div class="rb-foot"><details><summary>Claude에 넘길 id</summary><code>기사 ${esc(a.articleId)}<br>레이더 ${esc(a.best.id)}</code></details></div></article>`).join('\n')}</section>`;
}

// 화면 모양(카드)은 기자 전용 화면(/r)과 홈페이지 '단독감·미보도' 탭(/b 조각) 둘이 같이 쓴다. 홈페이지 style.css의 .card·.summary·.tag와
// 부딪치지 않게 모든 클래스에 rb- 를 붙이고 규칙은 .rb 안으로 한정한다. 어두운 화면은 단독 화면에서만(홈페이지는 밝은 화면뿐).
const CSS_RULES = `
.rb{--fg:#1c2228;--mute:#5f6a74;--line:#dfe2e6;--card:#fff;--a:#b3261e;--b:#1f5fa8;--c:#6b7480;--new:#fff0a6;--newfg:#5a4300;--cov:#e8ecef;--unk:#fde7d6;--link:#0b5cad;color:var(--fg);font-size:15px;line-height:1.6}
.rb a{color:var(--link)}.rb h2{font-size:17px;margin:0 0 6px;padding-bottom:4px;border-bottom:2px solid var(--line);letter-spacing:0}.rb h3{font-size:16px;margin:6px 0 4px;line-height:1.45;letter-spacing:0}
.rb section{margin:22px 0}.rb .rb-count{font-weight:400;color:var(--mute);font-size:14px}
.rb .rb-hA{color:var(--a);border-color:var(--a)}.rb .rb-hB{color:var(--b);border-color:var(--b)}.rb .rb-hC{color:var(--c)}
.rb .rb-sum{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:0 0 14px}.rb .rb-sum div{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:8px 10px}.rb .rb-sum b{display:block;font-size:22px;line-height:1.2}.rb .rb-sum span{font-size:12px;color:var(--mute)}
.rb .rb-warn{background:var(--unk);border-radius:10px;padding:8px 12px;margin:0 0 14px;font-size:14px}.rb .rb-warn ul{margin:4px 0 0;padding-left:18px}
.rb .rb-lead{color:var(--mute);font-size:14px;margin:4px 0 8px}.rb .rb-pills{display:flex;flex-wrap:wrap;gap:6px;margin:6px 0}.rb .rb-pill{font-size:12px;border-radius:999px;padding:1px 8px;background:var(--cov)}
.rb .rb-card{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--line);border-radius:10px;padding:10px 12px;margin:10px 0;overflow-wrap:anywhere;cursor:auto;transform:none}
.rb .rb-card:hover{transform:none}.rb .rb-tA{border-left-color:var(--a)}.rb .rb-tB{border-left-color:var(--b)}.rb .rb-tC{border-left-color:var(--c)}
.rb .rb-top{display:flex;flex-wrap:wrap;gap:6px;align-items:center;font-size:12px;color:var(--mute)}.rb .rb-tier{font-weight:800;color:var(--fg)}.rb .rb-tA .rb-tier{color:var(--a)}.rb .rb-tB .rb-tier{color:var(--b)}
.rb .rb-watch{background:var(--cov);border-radius:4px;padding:0 6px}.rb .rb-date{margin-left:auto}.rb .rb-convrows .rb-date{margin:0 4px}
.rb .rb-pv{font-size:12px;border-radius:4px;padding:0 6px;font-weight:700}.rb .pnew{background:var(--new);color:var(--newfg)}.rb .pcov{background:var(--cov)}.rb .punk{background:var(--unk)}
.rb .rb-facts{margin:4px 0;padding-left:18px}.rb .rb-facts li{margin:1px 0}.rb .rb-same,.rb .rb-caution{margin:6px 0;font-size:13px;color:var(--mute)}
.rb .rb-press{margin:8px 0 4px;font-size:13px;border-radius:8px;padding:6px 8px;background:var(--cov)}.rb .rb-press.pnew{background:var(--new);color:var(--newfg)}.rb .rb-press.punk{background:var(--unk)}.rb .rb-press ul{margin:4px 0 0;padding-left:18px}
.rb .rb-foot{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-top:6px}.rb .rb-btn{display:inline-block;border:1px solid var(--line);border-radius:6px;padding:2px 10px;text-decoration:none;font-size:14px}
.rb details{font-size:12px;color:var(--mute)}.rb summary{cursor:pointer}.rb code{font-size:12px}.rb .rb-muted{color:var(--mute)}.rb .rb-small{font-size:13px}.rb .rb-empty{color:var(--mute)}
.rb .rb-convrows{list-style:none;padding:0;margin:6px 0}.rb .rb-convrows li{margin:4px 0;font-size:14px}.rb .rb-tag{font-size:11px;font-weight:800;border-radius:4px;padding:0 5px;margin-right:4px;background:var(--cov)}.rb .rb-tag.tA{color:var(--a)}.rb .rb-tag.tB{color:var(--b)}.rb .rb-tag.bg{font-weight:400}
.rb .rb-chip{border:1px solid var(--line);border-radius:999px;padding:3px 11px;color:var(--fg);text-decoration:none;background:var(--card);font-size:14px}.rb .rb-chip.on{border-color:var(--fg);font-weight:700}
@media (max-width:520px){.rb .rb-sum{grid-template-columns:repeat(2,1fr)}}`;
const CSS_DARK = '@media (prefers-color-scheme:dark){.rb{--fg:#e6e9ec;--mute:#9aa5b0;--line:#2c3339;--card:#1c2125;--a:#ff8a80;--b:#8ab8ff;--c:#a5adb6;--new:#5a4b00;--newfg:#ffe9a0;--cov:#2a3137;--unk:#4a2f1c;--link:#8ab8ff}}';

// 맨 위 숫자·수집 상태·A·B·겹친 신호·역추적·C(접힘). cLink: C 펼치기 링크(단독 화면) 또는 없음(홈페이지는 C를 접은 채 숫자만).
export function boardSections(d, { cLink = '' } = {}) {
  const all = [...d.tiers.A, ...d.tiers.B];
  const unreported = all.filter((x) => d.pressOf(x) === '미보도 후보').length;
  const health = d.health.map((h) => h.replace(/^- /, ''));
  const cRows = d.tiers.C;
  const hiddenN = Object.values(d.hiddenBy).reduce((a, b) => a + b, 0);
  return `<div class="rb-sum" data-a="${d.tiers.A.length}" data-b="${d.tiers.B.length}" data-new="${unreported}"><div><b>${d.tiers.A.length}</b><span>A 단독 후보·직접 변화</span></div><div><b>${d.tiers.B.length}</b><span>B 확인할 공식 변화</span></div><div><b>${unreported}</b><span>자동 대조 미보도 후보</span></div><div><b>${health.length}</b><span>수집 문제</span></div></div>
${health.length ? `<div class="rb-warn"><b>먼저 볼 것: 수집 상태</b> — 실패한 곳의 0건은 '없음'이 아니라 미확인<ul>${health.map((h) => `<li>${esc(h)}</li>`).join('')}</ul></div>` : ''}
${tierSection('A', '단독 후보·직접 변화', d)}
${tierSection('B', '확인할 공식 변화', d)}
${convHtml(d)}
${reverseHtml(d)}
${d.showC ? tierSection('C', '참고', d) : (cRows.length ? `<section><h2 class="rb-hC">C · 참고 <span class="rb-count">${cRows.length}건</span></h2><p class="rb-lead">소비자 소송·사이트 공통 문구·기보도 후보 등.${cLink ? ` ${cLink}` : ''}</p></section>` : '')}
${hiddenN ? `<p class="rb-muted rb-small">판정한 ${hiddenN}건은 숨김(${esc(Object.entries(d.hiddenBy).map(([v, n]) => `${v} ${n}`).join(' · '))})</p>` : ''}
<details class="rb-rules"><summary>읽는 법·규칙</summary><p>모두 자동 수집 단계다. A도 단독 확정이 아니다 — 원문 확인 → 보도 대조(낱말 바꿔 2~3번) → 회사 확인. 보도 대조(자동)는 네이버 뉴스 API·빙·구글에서 항목 날짜 3일 전부터 찾은 결과다. '미보도 후보'도 단독 판정이 아니고, '관련 보도 있음'은 같은 사건인지 열어 봐야 한다. 채널 실패는 미확인.</p>
<p>다 본 항목은 Claude에 id를 주고 "봤음"으로 표시하면 다음부터 안 뜬다(candidate_feedback).</p></details>`;
}

// 홈페이지 탭 연결용 읽기 전용 열쇠: MCP 토큰에서 HMAC으로 뽑는다(새 비밀 등록 없이). 이 열쇠로는 이 화면 조각만 읽힌다 —
// 커넥터·저장소 쓰기·수집기 전송은 안 된다. 바꾸려면 BOARD_KEY_LABEL을 올린다(예전 열쇠는 바로 404).
const BOARD_KEY_LABEL = 'board-read-v1';
export async function boardKey(env) {
  const token = env?.MCP_ACCESS_TOKEN;
  if (!token) return '';
  const key = await crypto.subtle.importKey('raw', new TextEncoder().encode(token), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  const sig = new Uint8Array(await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(BOARD_KEY_LABEL)));
  return btoa(String.fromCharCode(...sig)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '').slice(0, 32);
}
const HOMEPAGE_PATH = `${HOMEPAGE}/seoul-reporting-radar/`;

export function boardPage(d, { hours, q, minor }) {
  const chip = (label, params, on) => `<a class="rb-chip${on ? ' on' : ''}" href="?${new URLSearchParams(params).toString()}">${esc(label)}</a>`;
  const base = { ...(q ? { q } : {}), ...(minor ? { minor: '1' } : {}) };
  const nav = [chip('24시간', { ...base, hours: 24 }, d.hours === 24), chip('72시간', { ...base, hours: 72 }, d.hours === 72), chip('7일', { ...base, hours: 168 }, d.hours === 168),
    chip(minor ? '참고(C) 숨기기' : '참고(C) 보기', { ...(q ? { q } : {}), ...(hours ? { hours } : {}), ...(minor ? {} : { minor: '1' }) }, false)].join('');
  const cLink = chip('펼쳐 보기', { ...(q ? { q } : {}), ...(hours ? { hours } : {}), minor: '1' }, false);
  return `<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><meta name="referrer" content="no-referrer"><title>오늘의 레이더 · 기자 전용</title>
<style>${CSS_RULES}
${CSS_DARK}
*{box-sizing:border-box}body{margin:0;background:#f6f6f3;font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Malgun Gothic",sans-serif}
@media (prefers-color-scheme:dark){body{background:#141719}}
main{max-width:860px;margin:0 auto;padding:16px}.rb h1{font-size:21px;margin:0}.rb .rb-stamp{color:var(--mute);margin:2px 0 12px;font-size:14px}
.rb .rb-nav{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:0 0 14px}.rb form{display:flex;gap:6px}
.rb input{font:inherit;font-size:14px;padding:3px 8px;border:1px solid var(--line);border-radius:6px;background:var(--card);color:var(--fg);width:140px}.rb button{font:inherit;font-size:14px;padding:3px 10px;border:1px solid var(--line);border-radius:6px;background:var(--card);color:var(--fg)}
.rb footer{color:var(--mute);font-size:13px;margin:28px 0 8px}.rb .rb-link{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:8px 12px;font-size:13px}
</style></head><body><main class="rb">
<h1>오늘의 레이더</h1>
<p class="rb-stamp">${esc(kstStamp(d.now.toISOString()))} 기준 최근 ${esc(d.hours)}시간${d.monday && d.defaultHours ? '(월요일: 주말 포함)' : ''} · 기자 전용 감시 ${WATCHES.length}개${q ? ` · “${esc(q)}”로 좁힘` : ''}</p>
<div class="rb-nav">${nav}<form method="get">${hours ? `<input type="hidden" name="hours" value="${esc(hours)}">` : ''}${minor ? '<input type="hidden" name="minor" value="1">' : ''}<input name="q" value="${esc(q)}" placeholder="회사·낱말"><button>찾기</button></form></div>
${boardSections(d, { cLink })}
<footer><p class="rb-link">같은 내용이 홈페이지 '단독감·미보도' 탭 맨 위에도 뜬다(로그인 설정 전에는 공개, 설정 후에는 아이디·비밀번호 로그인): <a href="${esc(HOMEPAGE_PATH)}" rel="noreferrer">홈페이지</a></p>
<p>이 주소는 비밀 열쇠가 든 기자 전용 주소다 — 공유하지 말 것.</p></footer>
</main></body></html>`;
}

// 홈페이지 탭이 읽는 조각: GET /b/<읽기 전용 열쇠>. 홈페이지 주소에서만 읽히게 CORS를 연다. 스크립트 없는 조각(style 하나 + 카드).
export function boardFragment(d) {
  return `<style>${CSS_RULES}</style><div class="rb" data-generated="${esc(d.now.toISOString())}"><p class="rb-muted rb-small">${esc(kstStamp(d.now.toISOString()))} 기준 최근 ${esc(d.hours)}시간${d.monday && d.defaultHours ? '(월요일: 주말 포함)' : ''} · 기자 전용 감시 ${WATCHES.length}개${d.q ? ` · “${esc(d.q)}”로 좁힘` : ''}</p>
${boardSections(d)}</div>`;
}

function args(url) {
  const p = url.searchParams;
  const hours = p.has('hours') ? clampInt(p.get('hours'), 1, 336, 24) : undefined;
  const q = String(p.get('q') ?? '').trim().slice(0, 60);
  const minor = p.get('minor') === '1';
  return { hours, q, minor };
}

export async function board(request, env, deps = {}) {
  const url = new URL(request.url);
  const m = /^\/r\/([A-Za-z0-9_-]{16,128})\/?$/.exec(url.pathname);
  if (!m || !(await safeEqual(m[1], env?.MCP_ACCESS_TOKEN))) return new Response('Not found', { status: 404 });
  if (request.method !== 'GET' && request.method !== 'HEAD') return new Response('Method not allowed', { status: 405, headers: { Allow: 'GET' } });
  const ctx = { env, private: true, fetch: deps.fetch ?? ((...a) => fetch(...a)), now: deps.now ?? new Date() };
  const { hours, q, minor } = args(url);
  let html;
  try {
    html = boardPage(await radarTodayData(ctx, { hours, company: q, limit: 60, include_minor: minor }), { hours, q, minor });
  } catch (e) {
    html = `<!doctype html><meta charset="utf-8"><title>오늘의 레이더</title><p>불러오기 실패: ${esc(String(e?.message ?? e).slice(0, 200))} — 미확인(0건 아님)</p>`;
  }
  return new Response(request.method === 'HEAD' ? null : html, { status: 200, headers: HEADERS });
}

// 홈페이지 탭 조각.
// - GET /b/me (Authorization: Bearer <세션>): 로그인한 브라우저(11-01 기자 요청: 아이디·비밀번호 로그인).
// - GET /b/open: 열쇠 없이 — 11-01 기자 결정(누구나 볼 수 있음을 알고 고름). 로그인 비밀값(BOARD_USER·BOARD_PASSWORD)을
//   등록하면 자동으로 닫힌다(401) — 공개는 로그인을 아직 설정하지 않은 동안만.
// - GET /b/<읽기 전용 열쇠>: 예전 방식, 되돌릴 때 쓰게 남겨 둠.
// 같은 조건 조각은 한 실행 환경 안에서 60초 재사용(저장소 읽기 23개를 매번 하지 않게).
const OPEN_TTL_MS = 60000;
const fragCache = new WeakMap();   // 저장소 바인딩마다 따로(시험에서 저장소가 다르면 섞이지 않게)
export async function boardPart(request, env, deps = {}) {
  const url = new URL(request.url);
  if (request.method === 'OPTIONS') return preflight(request);
  const cors = corsHeaders(request);
  const headers = { ...HEADERS, ...cors };
  const now = deps.now ?? new Date();
  const mode = /^\/b\/open\/?$/.test(url.pathname) ? 'open' : /^\/b\/me\/?$/.test(url.pathname) ? 'me' : 'key';
  if (mode === 'open' && loginConfigured(env)) return Response.json({ error: '로그인 필요' }, { status: 401, headers: { ...cors, 'Cache-Control': 'no-store' } });
  if (mode === 'me' && !(await verifySession(env, sessionOf(request), now.getTime()))) {
    return Response.json({ error: loginConfigured(env) ? '로그인 필요' : '로그인 미설정' }, { status: loginConfigured(env) ? 401 : 503, headers: { ...cors, 'Cache-Control': 'no-store' } });
  }
  if (mode === 'key') {
    const m = /^\/b\/([A-Za-z0-9_-]{16,64})\/?$/.exec(url.pathname);
    const key = await boardKey(env);
    if (!m || !key || !(await safeEqual(m[1], key))) return new Response('Not found', { status: 404, headers: cors });
  }
  if (request.method !== 'GET') return new Response('Method not allowed', { status: 405, headers: { Allow: 'GET', ...cors } });
  const ctx = { env, private: true, fetch: deps.fetch ?? ((...a) => fetch(...a)), now };
  const { hours, q, minor } = args(url);
  const ck = `${hours ?? ''}|${q}|${minor ? 1 : 0}`;
  const cache = env?.STORE && typeof env.STORE === 'object' ? (fragCache.get(env.STORE) ?? fragCache.set(env.STORE, new Map()).get(env.STORE)) : null;
  const hit = cache && !deps.noCache ? cache.get(ck) : null;
  if (hit && now.getTime() - hit.at < OPEN_TTL_MS && hit.at <= now.getTime()) return new Response(hit.body, { status: 200, headers });
  try {
    const body = boardFragment(await radarTodayData(ctx, { hours, company: q, limit: 60, include_minor: minor }));
    if (cache) { cache.set(ck, { at: now.getTime(), body }); if (cache.size > 20) cache.delete(cache.keys().next().value); }
    return new Response(body, { status: 200, headers });
  } catch (e) {
    return new Response(`<p>불러오기 실패: ${esc(String(e?.message ?? e).slice(0, 200))} — 미확인(0건 아님)</p>`, { status: 503, headers });
  }
}
