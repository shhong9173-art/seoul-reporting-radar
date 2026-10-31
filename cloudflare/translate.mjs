// 외신 제목 번역·본문 요약(POST /ingest/translate, Bearer MCP 토큰, kind 'title'|'summary') — Cloudflare Workers AI(무료 일일 한도 안).
// 11-01 운영: 외신 수집기(global_collector.py)의 주 번역기(구글 비공식 주소)가 Actions에서 막혀 거의 전부 보조 번역기(MyMemory)로
// 넘어갔고 품질이 낮았다('jailbreaking FSD' → '탈옥 금감원'). 언어 모델로 신문 제목체 한국어로 옮기고, 안 되면 번역 전용 모델(m2m100).
// 모델 이름은 Workers AI 목록에 따라 없을 수 있어 차례로 시도하고, 처음 성공한 모델을 이 실행 환경에서 기억한다.
import { safeEqual } from './common.mjs';

export const LLM_MODELS = ['@cf/meta/llama-4-scout-17b-16e-instruct', '@cf/google/gemma-3-12b-it', '@cf/meta/llama-3.3-70b-instruct-fp8-fast', '@cf/meta/llama-3.1-8b-instruct'];
export const MT_MODEL = '@cf/meta/m2m100-1.2b';
const MAX_TEXTS = 20;
const MAX_CHARS = 1200;
let goodModel = null;

const SYSTEM = '너는 한국 경제신문의 외신 담당 번역 기자다. 영어 기사 제목을 한국 신문 제목체의 자연스러운 한국어 한 줄로 옮긴다. '
  + '회사·제품 이름은 한국 언론이 쓰는 표기로(Hyundai Motor→현대차, Kia→기아, Hyundai Mobis→현대모비스, POSCO→포스코, Hyundai Steel→현대제철, '
  + 'Korea Zinc→고려아연, LS Electric→LS일렉트릭, HD Hyundai Electric→HD현대일렉트릭, Hyosung Heavy Industries→효성중공업, LS Cable→LS전선, '
  + 'Hanwha Qcells→한화큐셀, Hankook Tire→한국타이어, Tesla→테슬라, BYD→BYD), 숫자·단위·고유명사는 그대로 둔다. 뜻을 더하거나 빼지 않는다. '
  + '끝에 붙은 매체 이름(" - Reuters" 등)은 옮기지 않는다. 제목에 없는 사실(상표 출원·확정·계약 체결 등)을 지어내지 않는다 — '
  + "hints at·plans·considers·may·reportedly 같은 불확실한 표현은 '시사'·'검토'·'계획'·'~할 듯'·'~한 것으로 알려져'처럼 그대로 살린다. "
  + '번역문 한 줄만 출력한다(설명·따옴표·접두어 없이).';

// 요약(kind:'summary'): 매체 RSS 본문 발췌로 한국어 2~3문장. 발췌에 없는 사실은 쓰지 않는다.
const SUMMARY_SYSTEM = '너는 한국 경제신문의 외신 담당 기자다. 아래 영어 기사(제목과 본문 발췌)를 한국어 2~3문장으로 요약한다. '
  + '발췌에 있는 사실만 쓰고 추측·평가·배경 지식·전망을 더하지 않는다. 숫자·단위·날짜는 정확히, 회사·제품 이름은 한국 언론 표기로'
  + '(Hyundai Motor→현대차, Kia→기아, LG Energy Solution→LG에너지솔루션, Samsung SDI→삼성SDI, SK On→SK온, POSCO→포스코, Korea Zinc→고려아연, '
  + 'Hanwha Qcells→한화큐셀, LS Electric→LS일렉트릭, HD Hyundai Electric→HD현대일렉트릭, Tesla→테슬라). '
  + "'may·plans·reportedly·could' 같은 불확실한 표현은 '~할 수 있다·계획·~한 것으로 알려졌다'로 살린다. 요약문만 출력한다(제목·머리말·목록 기호 없이).";
const SUMMARY_MAX_CHARS = 2600;

export function cleanSummary(text) {
  const lines = String(text ?? '').split('\n').map((l) => l.replace(/^\s*(?:[-•*·]|\d+[.)])\s*/, '').replace(/^(요약|한국어 요약)\s*[:：]\s*/, '').trim()).filter(Boolean);
  const t = lines.join(' ').replace(/\s+/g, ' ').trim();
  return /[가-힣]/.test(t) && t.length >= 20 && t.length <= 700 ? t : '';
}

export function cleanOutput(text) {
  let t = String(text ?? '').trim().split('\n').find((l) => l.trim()) ?? '';
  t = t.replace(/^(번역|한국어|제목)\s*[:：]\s*/, '').replace(/^["'“”‘’「」]+|["'“”‘’「」]+$/g, '').trim();
  t = t.replace(/\s+-\s*$/, '').trim();   // 끝에 남은 ' -'(매체 이름을 빼다 남은 것)
  return /[가-힣]/.test(t) && t.length <= 400 ? t : '';
}

async function viaLlm(env, text, kind = 'title') {
  const order = goodModel ? [goodModel, ...LLM_MODELS.filter((m) => m !== goodModel)] : LLM_MODELS;
  const summary = kind === 'summary';
  for (const model of order) {
    try {
      const r = await env.AI.run(model, { messages: [{ role: 'system', content: summary ? SUMMARY_SYSTEM : SYSTEM }, { role: 'user', content: text }],
        max_tokens: summary ? 360 : 160, temperature: 0.1 });
      const raw = r?.response ?? r?.result?.response;
      const ko = summary ? cleanSummary(raw) : cleanOutput(raw);
      if (ko) { goodModel = model; return { ko, status: summary ? 'summarized_ai' : 'translated_ai', model }; }
    } catch { /* 없는 모델·한도 초과 — 다음 모델 */ }
  }
  return null;
}

async function viaMt(env, text) {
  try {
    const r = await env.AI.run(MT_MODEL, { text, source_lang: 'english', target_lang: 'korean' });
    const ko = cleanOutput(r?.translated_text ?? r?.result?.translated_text);
    if (ko) return { ko, status: 'translated_ai_mt', model: MT_MODEL };
  } catch { /* 아래 실패 */ }
  return null;
}

export async function translateRoute(request, env) {
  const m = /^Bearer\s+([A-Za-z0-9_-]{16,128})$/.exec(request.headers.get('Authorization') ?? '');
  if (!m || !(await safeEqual(m[1], env?.MCP_ACCESS_TOKEN))) return new Response('Not found', { status: 404 });
  if (request.method !== 'POST') return new Response('Method not allowed', { status: 405, headers: { Allow: 'POST' } });
  if (!env.AI || typeof env.AI.run !== 'function') return Response.json({ error: 'Workers AI 바인딩 없음' }, { status: 503 });
  let body;
  try { body = await request.json(); } catch { return Response.json({ error: 'bad json' }, { status: 400 }); }
  const kind = body?.kind === 'summary' ? 'summary' : 'title';
  const texts = Array.isArray(body?.texts) ? body.texts.slice(0, MAX_TEXTS).map((t) => String(t ?? '').slice(0, kind === 'summary' ? SUMMARY_MAX_CHARS : MAX_CHARS)) : [];
  if (!texts.length) return Response.json({ error: 'texts 없음' }, { status: 400 });
  const results = [];
  for (const text of texts) {
    if (!text.trim()) { results.push({ ko: '', status: 'empty' }); continue; }
    // 요약은 언어 모델로만(번역 전용 모델로 긴 본문을 옮기면 요약이 아니라 번역이 된다)
    results.push((await viaLlm(env, text, kind)) ?? (kind === 'title' ? await viaMt(env, text) : null) ?? { ko: '', status: 'failed' });
  }
  return Response.json({ results }, { headers: { 'Cache-Control': 'no-store' } });
}
