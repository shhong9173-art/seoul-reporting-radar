import { CP949_TABLE_B64 } from './cp949_table.mjs';
// Shared helpers for the radar MCP connector. No secrets are ever echoed.
export const KST_OFFSET_MS = 9 * 3600 * 1000;
export const MAX_TEXT = 20000;
export const DEFAULT_DATA_BASE =
  'https://raw.githubusercontent.com/shhong9173-art/seoul-reporting-radar/main/';

// Reporter-confirmed direct beats (2026-10-26, 41 companies).
export const BEAT_TEAMS = {
  '자동차': ['현대차', '기아', '현대모비스', '현대위아', 'HL만도', '한국GM', 'KG모빌리티', '르노코리아',
    '메르세데스벤츠코리아', 'BMW코리아', '폭스바겐코리아', '아우디코리아', '혼다코리아', '한국타이어',
    '넥센타이어', '금호타이어'],
  '철강·비철': ['포스코홀딩스', '포스코', '현대제철', 'KG스틸', '세아홀딩스', '세아제강', '동국제강', '동국씨엠',
    '고려아연', '영풍'],
  '전력·에너지': ['HD현대일렉트릭', 'LS일렉트릭', '대한전선', 'LS전선', 'LS MnM', 'LS지주', '두산에너빌리티',
    'GS', 'GS칼텍스'],
  '화학·소재': ['한화솔루션', 'OCI', 'OCI홀딩스', '태광', '동성케미칼', 'DL케미칼'],
};
export const DIRECT_BEATS = new Set(Object.values(BEAT_TEAMS).flat());
export const TEAM_ORDER = ['자동차', '철강·비철', '전력·에너지', '화학·소재', '해외', '조달', '특허', '그 외'];
const TEAM_ALIASES = {
  auto: '자동차', car: '자동차', '자동차': '자동차', '완성차': '자동차', '부품': '자동차', '타이어': '자동차',
  steel: '철강·비철', '철강': '철강·비철', '비철': '철강·비철', '철강·비철': '철강·비철',
  power: '전력·에너지', energy: '전력·에너지', '전력': '전력·에너지', '전선': '전력·에너지', '에너지': '전력·에너지',
  '전력·에너지': '전력·에너지', chem: '화학·소재', '화학': '화학·소재', '소재': '화학·소재', '화학·소재': '화학·소재',
  overseas: '해외', '해외': '해외', g2b: '조달', '조달': '조달', '나라장터': '조달', patent: '특허', '특허': '특허',
  other: '그 외', '그외': '그 외', '그 외': '그 외',
};
// Exact registry spellings (DART legal names, English) → beat name.
export const REGISTRY_NAMES = {
  '현대자동차': '현대차', '기아자동차': '기아', '한국타이어앤테크놀로지': '한국타이어', '엘에스일렉트릭': 'LS일렉트릭',
  'LS ELECTRIC': 'LS일렉트릭', '엘에스전선': 'LS전선', '엘에스엠앤엠': 'LS MnM', 'LS M&M': 'LS MnM',
  '케이지스틸': 'KG스틸', '케이지모빌리티': 'KG모빌리티', '한국지엠': '한국GM', '오씨아이': 'OCI',
  '에이치디현대일렉트릭': 'HD현대일렉트릭', '디엘케미칼': 'DL케미칼', 'LS': 'LS지주', '엘에스': 'LS지주',
  '에이치엘만도': 'HL만도', '만도': 'HL만도', '메르세데스-벤츠 코리아': '메르세데스벤츠코리아',
};

export function beatName(raw) {
  const name = String(raw ?? '').trim();
  const mapped = REGISTRY_NAMES[name] ?? name;
  return DIRECT_BEATS.has(mapped) ? mapped : null;
}

export function teamsFromParam(value) {
  const out = new Set();
  for (const part of String(value ?? '').split(',')) {
    const key = part.trim().toLowerCase();
    if (!key) continue;
    const team = TEAM_ALIASES[key] ?? TEAM_ALIASES[part.trim()];
    if (team) out.add(team);
  }
  return out;
}

export function kstNow(now = new Date()) {
  return new Date(now.getTime() + KST_OFFSET_MS);
}
export function kstDate(now = new Date(), minusDays = 0) {
  return new Date(kstNow(now).getTime() - minusDays * 86400000).toISOString().slice(0, 10);
}
export function kstStamp(now = new Date()) {
  return kstNow(now).toISOString().slice(0, 16).replace('T', ' ') + ' KST';
}
export function ymd(date) {
  return String(date).replaceAll('-', '');
}

export function clampInt(value, lo, hi, fallback) {
  const n = Number.parseInt(value, 10);
  if (!Number.isFinite(n)) return fallback;
  return Math.min(hi, Math.max(lo, n));
}

export function textResult(text, isError = false) {
  const body = text.length > MAX_TEXT
    ? text.slice(0, MAX_TEXT) + '\n…(응답 예산 2만 자 초과로 잘림. q=·limit=·team=으로 좁혀 다시 조회)'
    : text;
  return { content: [{ type: 'text', text: body }], ...(isError ? { isError: true } : {}) };
}

export async function sha256Hex(text) {
  const data = typeof text === 'string' ? new TextEncoder().encode(text) : text;
  const digest = await crypto.subtle.digest('SHA-256', data);
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

export async function safeEqual(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string' || !a || !b) return false;
  const [x, y] = await Promise.all([sha256Hex(a), sha256Hex(b)]);
  let diff = 0;
  for (let i = 0; i < x.length; i++) diff |= x.charCodeAt(i) ^ y.charCodeAt(i);
  return diff === 0;
}

const ENTITIES = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ', middot: '·', hellip: '…',
  lsquo: '‘', rsquo: '’', ldquo: '“', rdquo: '”', ndash: '–', mdash: '—' };
export function decodeEntities(text) {
  return String(text ?? '').replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (m, code) => {
    if (code[0] === '#') {
      const n = code[1].toLowerCase() === 'x' ? Number.parseInt(code.slice(2), 16) : Number.parseInt(code.slice(1), 10);
      return Number.isFinite(n) && n > 0 && n < 0x110000 ? String.fromCodePoint(n) : m;
    }
    return ENTITIES[code.toLowerCase()] ?? m;
  });
}

export function htmlToText(html) {
  return decodeEntities(String(html ?? '')
    .replace(/<!--[\s\S]*?-->/g, ' ')
    .replace(/<(script|style|noscript|svg)[\s\S]*?<\/\1>/gi, ' ')
    .replace(/<\s*(br|\/p|\/div|\/tr|\/li|\/h\d|\/table|\/title)\b[^>]*>/gi, '\n')
    .replace(/<\/t[dh]>/gi, ' | ')
    .replace(/<[^>]+>/g, ' '))
    .replace(/[ \t ]+/g, ' ')
    .replace(/ *\n[ \n]*/g, '\n')
    .trim();
}

let cp949Table = null;
function cp949() {
  if (!cp949Table) {
    const bin = atob(CP949_TABLE_B64);
    cp949Table = new Uint16Array(bin.length / 2);
    for (let i = 0; i < cp949Table.length; i++) cp949Table[i] = bin.charCodeAt(2 * i) | (bin.charCodeAt(2 * i + 1) << 8);
  }
  return cp949Table;
}

// Workers documents only a UTF-8 TextDecoder; DART and many go.kr pages are MS949.
export function decodeCp949(bytes) {
  const table = cp949();
  const out = [];
  let chunk = '';
  for (let i = 0; i < bytes.length; i++) {
    const b = bytes[i];
    if (b < 0x80) { chunk += String.fromCharCode(b); }
    else if (b >= 0x81 && b <= 0xfe && i + 1 < bytes.length && bytes[i + 1] >= 0x41 && bytes[i + 1] <= 0xfe) {
      chunk += String.fromCharCode(table[(b - 0x81) * 190 + (bytes[i + 1] - 0x41)]);
      i++;
    } else { chunk += '\ufffd'; }
    if (chunk.length > 8192) { out.push(chunk); chunk = ''; }
  }
  out.push(chunk);
  return out.join('');
}

const KOREAN_LEGACY = new Set(['euc-kr', 'cp949', 'ms949', 'windows-949', 'x-windows-949', 'ks_c_5601-1987', 'ksc5601', 'ks_c_5601', 'uhc']);

export function decodeBytes(bytes, contentType = '') {
  let charset = (/charset=([\w-]+)/i.exec(contentType) || [])[1];
  if (!charset) {
    const head = String.fromCharCode(...bytes.slice(0, 4096));
    charset = (/<meta[^>]+charset=["']?([\w-]+)/i.exec(head) || /encoding=["']([\w-]+)["']/i.exec(head) || [])[1];
  }
  const label = (charset || 'utf-8').toLowerCase();
  if (KOREAN_LEGACY.has(label)) return { text: decodeCp949(bytes), charset: `${label} (CP949 표)` };
  try {
    return { text: new TextDecoder(label).decode(bytes), charset: label };
  } catch {
    return { text: new TextDecoder('utf-8').decode(bytes), charset: `utf-8 (요청 문자셋 ${label} 미지원)` };
  }
}

export async function readCapped(response, maxBytes) {
  const reader = response.body?.getReader();
  if (!reader) return new Uint8Array(await response.arrayBuffer()).slice(0, maxBytes);
  const chunks = [];
  let total = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    total += value.byteLength;
    if (total > maxBytes) {
      await reader.cancel();
      throw new Error(`응답이 ${Math.round(maxBytes / 1e6)}MB를 넘어 중단`);
    }
    chunks.push(value);
  }
  const out = new Uint8Array(total);
  let offset = 0;
  for (const c of chunks) { out.set(c, offset); offset += c.byteLength; }
  return out;
}

export async function fetchJson(ctx, path) {
  const base = ctx.env?.RADAR_DATA_BASE || DEFAULT_DATA_BASE;
  const response = await ctx.fetch(base + path, { cf: { cacheTtl: 120, cacheEverything: true } });
  if (!response.ok) throw new Error(`${path} HTTP ${response.status}`);
  return response.json();
}

export function matchesQuery(q, ...fields) {
  const terms = String(q ?? '').toLowerCase().split(/\s+/).filter(Boolean);
  if (!terms.length) return true;
  const hay = fields.flat().map((f) => String(f ?? '').toLowerCase()).join(' ');
  return terms.every((t) => hay.includes(t));
}

// 공장등록 주생산품처럼 같은 항목이 되풀이된 목록('액슬 등 구동부품, 액슬 등 구동부품, …')을 한 번씩만(순서·글자 유지).
export function uniqueList(text) {
  const seen = new Set();
  const out = [];
  for (const part of String(text ?? '').split(/\s*[,，、]\s*/)) {
    const key = part.replace(/\s+/g, '').replace(/등$/, '').toLowerCase();
    if (!part.trim() || seen.has(key)) continue;
    seen.add(key);
    out.push(part.trim());
  }
  return out.join(', ');
}
