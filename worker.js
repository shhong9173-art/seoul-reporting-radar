const SEOUL_PRESS_URL = 'https://www.seoul.go.kr/news/news_report.do?tr_code=rsite';

function clean(s='') {
  return s.replace(/<[^>]*>/g, ' ').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/\s+/g, ' ').trim();
}

function category(title='') {
  if (/정비|주택|부동산|도시계획|용적률|재개발|재건축|공급|역세권/.test(title)) return '부동산';
  if (/예산|재정|사업비|지원금|소상공인|채용|기업|투자/.test(title)) return '예산·재정';
  if (/교통|지하철|버스|도로|횡단보도|철도/.test(title)) return '교통';
  if (/복지|출생|청년|어르신|장애|돌봄|지원/.test(title)) return '복지';
  if (/안전|폭염|재난|화재|사고|수사/.test(title)) return '안전';
  return '행정';
}

function score(title='') {
  let n = 55;
  const rules = [
    [/전국 최초|최초/, 14], [/증가|급증|확대|감소|급감/, 8], [/억|조원|억원|가구|세대|명/, 7],
    [/예산|사업비|계약|공모|민간|위탁/, 8], [/정비|재개발|재건축|도시계획|용적률/, 9], [/논란|의혹|주의|단속|적발|수사/, 12]
  ];
  for (const [re, pts] of rules) if (re.test(title)) n += pts;
  return Math.min(98, n);
}

function parseSeoul(html) {
  const items = [];
  const re = /<a[^>]+href=["']([^"']*news_report\.do\?[^"']*|[^"']*nttNo=[^"']+)["'][^>]*>([\s\S]*?)<\/a>/gi;
  let m;
  const seen = new Set();
  while ((m = re.exec(html)) && items.length < 30) {
    const href = m[1].replace(/&amp;/g, '&');
    const title = clean(m[2]);
    if (!title || title.length < 8 || /RSS|검색|목록|페이지/.test(title)) continue;
    const source = new URL(href, SEOUL_PRESS_URL).href;
    if (seen.has(source)) continue;
    seen.add(source);
    const sc = score(title);
    items.push({
      id: `seoul-${items.length + 1}`,
      level: sc >= 82 ? 'S' : sc >= 72 ? 'A' : 'B',
      category: category(title), org: '서울시', date: new Date().toISOString().slice(0,10), score: sc,
      title, summary: '서울시 공식 보도자료에서 자동 수집된 항목입니다. 원문과 첨부파일을 교차 확인해 단독 가능성을 판단합니다.',
      tags: ['실제수집', category(title)],
      questions: ['세부 사업비·대상 규모는?', '전년 또는 기존 사업과 무엇이 달라졌나?', '관련 계약·공모·심의 자료가 있는가?', '첨부파일에 추가 숫자나 조건이 있는가?'],
      data: '원문·첨부파일·예산서·계약자료·의회자료', source
    });
  }
  return items;
}

async function getRadar() {
  const res = await fetch(SEOUL_PRESS_URL, { headers: { 'User-Agent': 'Seoul-Reporting-Radar/1.0' } });
  if (!res.ok) throw new Error(`서울시 수집 실패: ${res.status}`);
  return parseSeoul(await res.text());
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === '/api/radar') {
      try {
        const items = await getRadar();
        return Response.json({ ok: true, updatedAt: new Date().toISOString(), items });
      } catch (e) {
        return Response.json({ ok: false, error: String(e), items: [] }, { status: 502 });
      }
    }
    return env.ASSETS.fetch(request);
  },
  async scheduled(event, env, ctx) {
    ctx.waitUntil((async () => {
      try {
        const items = await getRadar();
        console.log(JSON.stringify({ type: 'daily-seoul-crawl', count: items.length, updatedAt: new Date().toISOString() }));
      } catch (e) {
        console.error('daily crawl failed', e);
      }
    })());
  }
};
