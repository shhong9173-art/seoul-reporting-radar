// Aside(기자 컴퓨터의 AI 브라우저) REPL에서 돌리는 수집 코드 — 예약 작업 '새올 고시·공고 브라우저 수집'이 아래 여섯 토막을
// 차례로 mcp aside repl(code=…)에 그대로 넣는다. 11-06 기자 승인: 내장 브라우저로 시·군 목록을 하나씩 열던 방식(한 번에 8분 넘게)을 대신한다.
// 하는 일(읽기만): 해외 IP(GitHub)에서 막히거나 들쑥날쑥한 시·군 12곳 새올 고시·공고 목록 첫 쪽, 호주 무역구제 공지(TRN) 목록과 한국이 든 진행 사건의
// 공개기록(EPR) 문서 표(11-14 기자 승인 — 사건 6건까지, 사건마다 최근 60줄), 노동위원회 회의일정 달력 14곳. 시·군 목록에서 출입처 이름이 든 줄은 상세 페이지(제목 전체·본문 앞 400자·첨부 파일 이름)까지 읽고,
// 그 공고의 첨부 공고문(hwpx·hwp, 공고마다 3개까지 — 11-06·11-07 기자 승인)을 같은 사이트에서 내려받아 글자만 앞 4000자 보낸다(파일은 저장하지 않음).
// 마지막 토막이 레이더(Worker /upload/browser)에 직접 올린다 — 열쇠는 Aside 브라우저의 그 사이트 저장소에만 있고(scripts/aside/register_upload_key.js로 한 번 만듦)
// Worker는 SHA-256 지문만 안다. 열쇠가 없거나 실패하면 sdds local_notice_submit 인자 한 줄 JSON(SUBMIT)을 찍고, 예약 작업이 글자를 고치지 않고 올린다.
// 지킬 것: 아래 12개 사이트와 레이더 올리기 창 밖은 열지 않는다. 로그인·글쓰기 없음. 첨부는 출입처 줄의 공고문만(디스크에 저장 안 함). 사이트마다 목록 요청 한 번(실패 시 subCheck=N 한 번).
// REPL 사정(11-06 시험):
// - DOMParser·euc-kr 해독은 REPL엔 없고 브라우저 탭 안에만 있다 — 받은 바이트를 빈 탭으로 넘겨 읽는다.
// - 기자 컴퓨터 중계가 한 번 호출을 60초까지만 기다린다(전부 한 번에 돌리면 끊김) — 토막마다 45초 안에 끝나게 자른다.
// - 호출이 끝나면 뒤에서 도는 작업은 멈춘다(시작만 하고 나중에 확인하는 방식 불가) — 토막마다 끝까지 기다린다.
// - 맨 위 이름은 세션 안에서 계속 남는다 — 결과는 globalThis.__R에 두고, 코드는 블록 { } 안에 둔다.
// 출입처 이름 정규식(BEAT)은 scripts/kr_local_notice_watch.py COMPANIES를 이은 것 — tests/test_aside_collect.py가 같음을 확인한다.

// ===== 토막 1: 시·군 12곳 목록(동시에, 40초 안) =====
{
  const T0 = Date.now();
  const CITIES = [
    ['인천 부평구', 'https://eminwon.icbp.go.kr'], ['구미시', 'https://eminwon.gumi.go.kr'], ['청주시', 'https://www.cheongju.go.kr'],
    ['순천시', 'https://eminwon.suncheon.go.kr'], ['함평군', 'https://eminwon.hampyeong.go.kr'], ['양산시', 'https://eminwon.yangsan.go.kr'],
    ['광주 광산구', 'https://eminwon.gwangsan.go.kr'], ['나주시', 'https://eminwon.naju.go.kr'],
    ['광양시', 'https://eminwon.gwangyang.go.kr'], ['천안시', 'https://eminwon.cheonan.go.kr'],
    ['평택시', 'https://eminwon.pyeongtaek.go.kr'], ['원주시', 'https://eminwon.wonju.go.kr'],
  ];
  const P = '/emwp/gov/mogaha/ntis/web/ofr/action/OfrAction.do';
  const form = (sub) => new URLSearchParams({ method: 'selectListOfrNotAncmt', methodnm: 'selectListOfrNotAncmtHomepage', homepage_pbs_yn: 'Y',
    subCheck: sub, ofr_pageSize: '30', not_ancmt_se_code: '01,02,03,04,05', initValue: 'Y', countYn: 'Y', list_gubun: 'A',
    jndinm: 'OfrNotAncmtEJB', context: 'NTIS', method_type: '', pageIndex: '1' }).toString();
  const within = (p, ms, what) => Promise.race([p, new Promise((_, no) => setTimeout(() => no(new Error(`${what} 시간 초과 ${ms / 1000}초`)), ms))]);
  const isCj = (base) => base.includes('cheongju');
  const listReq = (base, sub) => isCj(base) ? fetch(base + '/www/selectEminwonNoticeList.do?key=281&pageUnit=60')
    : fetch(base + P, { method: 'POST', body: form(sub), headers: { 'Content-Type': 'application/x-www-form-urlencoded', Referer: base + P } });
  const bytes = async (r) => {
    const cs = (/charset=([\w-]+)/i.exec(r.headers.get('content-type') || '') || [])[1] || 'utf-8';
    return [Buffer.from(await r.arrayBuffer()).toString('base64'), cs];
  };
  // 목록 → [{mgt, cells}] (예전 내장 브라우저 [시작 코드]와 같은 규칙: 번호·조회수·게시 기간 칸은 뺌, 최근 7일 줄(적어도 맨 위 5줄))
  const parseList = (args) => {
    const [b64, cs] = args;
    const u = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
    let text; try { text = new TextDecoder(cs).decode(u); } catch (e) { text = new TextDecoder('utf-8').decode(u); }
    const doc = new DOMParser().parseFromString(text, 'text/html');
    const rows = []; const seen = new Set();
    for (const b of [...doc.querySelectorAll('tr'), ...doc.querySelectorAll('.dbody ul')]) {
      if (b.tagName === 'TR' && b.querySelector('tr')) continue;
      const m = /searchDetail\(\s*'([^']+)'/.exec(b.innerHTML) || /not_?[aA]ncmt_?[mM]gt_?[nN]o=([0-9A-Za-z_-]+)/.exec(b.innerHTML);
      if (!m || seen.has(m[1])) continue;
      const cells = [...b.querySelectorAll(b.tagName === 'TR' ? ':scope > td' : ':scope > li')].map((c) => c.textContent.replace(/\s+/g, ' ').trim())
        .filter((c) => c && !/^[\d,]+$/.test(c) && !/^\d{4}-\d\d-\d\d ~ \d{4}-\d\d-\d\d$/.test(c));
      if (cells.length) { seen.add(m[1]); rows.push({ mgt: m[1], cells }); }
    }
    const since = new Date(Date.now() + 9 * 3600e3 - 7 * 86400e3).toISOString().slice(0, 10);
    return rows.filter((x, i) => i < 5 || x.cells.some((c) => /^\d{4}-\d\d-\d\d$/.test(c) && c >= since));
  };
  try { if (globalThis.__R && globalThis.__R.tab) await closeTab(globalThis.__R.tab); } catch (e) { /* 지난 실행이 중간에 끊겨 남은 탭 */ }
  const tab = await openTab('about:blank');
  globalThis.__R = { at: Date.now(), P, within, isCj, bytes, listReq, parseList, tab, cities: [], pages: null, labor: null, timing: {} };
  const one = async ([name, base]) => {
    const t = Date.now();
    try {
      let r = await within(listReq(base, 'Y'), 38000, '목록');
      if (r.status === 500 && !isCj(base)) r = await within(listReq(base, 'N'), Math.max(5000, 40000 - (Date.now() - t)), '목록(subCheck=N)');
      if (r.status !== 200) throw new Error('HTTP ' + r.status);
      const rows = await tab.evaluate(parseList, await bytes(r));
      return { city: name, base, ...(rows.length ? { rows } : { error: '목록 0줄' }), ms: Date.now() - t };
    } catch (e) { return { city: name, base, error: String(e && e.message || e).slice(0, 100), ms: Date.now() - t }; }
  };
  globalThis.__R.cities = await Promise.all(CITIES.map(one));
  globalThis.__R.timing.lists = Date.now() - T0;
  console.log('LISTS ' + globalThis.__R.cities.map((c) => `${c.city} ${c.error ? '실패(' + c.error + ')' : c.rows.length + '줄'} ${(c.ms / 1000).toFixed(1)}초`).join(' · '));
}

// ===== 토막 2: 시간 초과한 시·군만 목록 한 번 더(동시에, 40초 안) =====
{
  // 11-06 운영 시험: 첫 요청에서 구미·양산·광산이 38초 시간 초과 → 바로 다시 요청하니 7.5~15.1초에 200. 첫 연결이 느린 날이 있다.
  const R = globalThis.__R;
  const bad = R && R.listReq ? R.cities.filter((c) => c.error) : [];
  if (!bad.length) { console.log('RETRY 없음'); } else {
    const T0 = Date.now();
    await Promise.all(bad.map(async (c) => {
      const t = Date.now();
      try {
        let r = await R.within(R.listReq(c.base, 'Y'), 38000, '다시');
        if (r.status === 500 && !R.isCj(c.base)) r = await R.within(R.listReq(c.base, 'N'), Math.max(5000, 40000 - (Date.now() - t)), '다시(subCheck=N)');
        if (r.status !== 200) throw new Error('HTTP ' + r.status);
        const rows = await R.tab.evaluate(R.parseList, await R.bytes(r));
        if (!rows.length) throw new Error('목록 0줄');
        delete c.error; c.rows = rows; c.retried = true;
      } catch (e) { c.error = `${c.error} → ${String(e && e.message || e).slice(0, 50)}`; }
      c.ms += Date.now() - t;
    }));
    R.timing.retry = Date.now() - T0;
    console.log('RETRY ' + bad.map((c) => `${c.city} ${c.error ? '실패(' + c.error + ')' : c.rows.length + '줄'}`).join(' · ') + ` · ${((Date.now() - T0) / 1000).toFixed(1)}초`);
  }
}

// ===== 토막 3: 출입처 이름이 든 줄의 상세 페이지(시·군마다 4건까지, 동시에, 40초 안) =====
{
  const R = globalThis.__R;
  if (!R || !R.cities.length) { console.log('DETAILS 건너뜀(토막 1 결과 없음 — 세션이 바뀜)'); } else {
    const T0 = Date.now();
    const BEAT = /현대자동차|현대차(?!증권)|기아(?:\s*\(주\)|㈜|자동차|\s*오토랜드)|현대모비스|현대위아|HL만도|에이치엘만도|한국지엠|한국GM|케이지모빌리티|KG모빌리티|르노코리아|한국타이어|넥센타이어|금호타이어|포스코(?!퓨처엠|인터내셔널|이앤씨|DX|엠텍|스틸리온|모빌리티솔루션)|POSCO|현대제철|KG스틸|케이지스틸|세아(?:제강|베스틸|창원특수강|홀딩스|씨엠)|동국제강|동국씨엠|고려아연|영풍\s*(?:석포|\(주\)|㈜)|석포제련소|HD현대일렉트릭|에이치디현대일렉트릭|현대일렉트릭|LS일렉트릭|엘에스일렉트릭|대한전선|LS전선|엘에스전선|LS\s*MnM|엘에스엠앤엠|LS엠앤엠|두산에너빌리티|GS칼텍스|지에스칼텍스|한화솔루션|OCI(?![A-Za-z])|오씨아이|태광산업|동성케미[칼컬]|DL케미칼|디엘케미칼|효성중공업|LG화학|엘지화학|롯데케미칼|금호석유화학|금호석화|S-OIL|S-Oil|(?<![가-힣])에쓰-?오일|현대오일뱅크|SK이노베이션|에스케이이노베이션/;
    const DETAIL_MAX = 4;
    // 제목 칸: kr_local_notice_watch.parse_cells와 같은 규칙(공고번호 칸 다음 칸, 없으면 숫자·날짜 아닌 첫 칸)
    const titleOf = (cells) => {
      const i = cells.findIndex((c) => /(?:고시|공고|공시)\s*제?\s*[\d-]+\s*호/.test(c));
      if (i >= 0 && i + 1 < cells.length) return cells[i + 1];
      return cells.find((c) => !/^[\d,]+$/.test(c) && !/^\d{4}-\d{2}-\d{2}$/.test(c)) || cells.join(' ');
    };
    const detailUrl = (base, mgt) => R.isCj(base) ? `${base}/www/selectEminwonNoticeView.do?key=281&notAncmtMgtNo=${encodeURIComponent(mgt)}`
      : `${base}${R.P}?method=selectOfrNotAncmt&methodnm=selectOfrNotAncmtRegst&not_ancmt_mgt_no=${encodeURIComponent(mgt)}&homepage_pbs_yn=Y&subCheck=Y&jndinm=OfrNotAncmtEJB&context=NTIS`;
    // 상세 → {title, body, files} (kr_local_notice_watch.parse_detail과 같은 규칙: 목록 제목 앞 30자가 든 글 조각부터 '첨부 파일·목록' 전까지)
    const parseDetail = (args) => {
      const [b64, cs, title] = args;
      const u = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
      let html; try { html = new TextDecoder(cs).decode(u); } catch (e) { html = new TextDecoder('utf-8').decode(u); }
      html = html.replace(/<(script|style)\b[\s\S]*?<\/\1>/gi, ' ');
      const ta = document.createElement('textarea');
      const un = (s) => { ta.innerHTML = s; return ta.value; };
      const nodes = [...html.matchAll(/>([^<]+)</g)].map((m) => un(m[1]).replace(/\s+/g, ' ').trim()).filter(Boolean);
      const prefix = title.replace(/\s+/g, ' ').replace(/(?:\.{2,}|…)\s*$/, '').trim().slice(0, 30);
      if (prefix.length < 6) return { error: '목록 제목이 짧음' };
      const i = nodes.findIndex((t) => t.includes(prefix));
      if (i < 0) return { error: '상세 형식 미상' };
      const body = [];
      for (const t of nodes.slice(i + 1)) { if (/^(?:첨부\s*파일|목록\s*보기|목록|이전\s*글|다음\s*글)(?![가-힣A-Za-z0-9_])/.test(t)) break; body.push(t); }   // 끝 낱말 규칙은 파이썬 \b와 같게
      const files = [...new Set(nodes.slice(i + 1).filter((t) => /\.(?:pdf|hwpx?|docx?|xlsx?|zip|jpg|png)$/i.test(t)))].slice(0, 6).map((t) => t.slice(0, 120));
      const text = body.join(' ').replace(/\s+/g, ' ').trim();
      // 새올 첨부 링크: javascript:goDownLoad('보이는 이름','저장 이름','경로') — 토막 4가 내려받는다(파이썬 parse_detail의 links와 같음)
      const un2 = (s) => { ta.innerHTML = s; return ta.value; };
      const links = [...html.matchAll(/goDownLoad\(\s*'([^']*)'\s*,\s*'([^']*)'\s*,\s*'([^']*)'\s*\)/g)].slice(0, 6).map((m) => ({ name: un2(m[1]).slice(0, 120), sys: un2(m[2]), path: un2(m[3]) }));
      return { title: nodes[i].slice(0, 300), body: text.slice(0, 400) + (text.length > 400 ? '…' : ''), files, links };
    };
    let read = 0, failed = 0;
    await Promise.all(R.cities.filter((c) => c.rows).map(async (c) => {
      for (const row of c.rows.filter((x) => BEAT.test(titleOf(x.cells))).slice(0, DETAIL_MAX)) {
        if (Date.now() - T0 > 36000) { failed += 1; continue; }          // 45초 안에 끝내기
        try {
          const d = await R.within(fetch(detailUrl(c.base, row.mgt), { headers: { Referer: c.base + (R.isCj(c.base) ? '/www/' : R.P) } }), 10000, '상세');
          if (d.status !== 200) throw new Error('HTTP ' + d.status);
          const got = await R.tab.evaluate(parseDetail, [...(await R.bytes(d)), titleOf(row.cells)]);
          if (got.error) throw new Error(got.error);
          row.links = got.links; row.ref = detailUrl(c.base, row.mgt); delete got.links;
          row.detail = got; read += 1;
        } catch (e) { failed += 1; }
      }
    }));
    R.timing.details = Date.now() - T0;
    console.log(`DETAILS 읽음 ${read} · 못 읽음 ${failed} · ${((Date.now() - T0) / 1000).toFixed(1)}초`);
  }
}

// ===== 토막 4: 상세를 읽은 줄의 첨부 공고문(hwpx·hwp) 글자(공고마다 3개까지, 40초 안) =====
{
  // 파이썬 read_attachments와 같은 고르기(hwpx·hwp·pdf 중 이름에 공고문·공고·개요·계획서·고시문·열람이 든 것 먼저)와 같은 내려받기 주소
  // (/emwp/jsp/ofr/FileDown.jsp). hwpx(zip 안 Contents/section*.xml)와 hwp(OLE 안 BodyText/Section*)를 기자 컴퓨터에서 글자로 푼다 — pdf는 '못 읽음'으로 남긴다.
  // 글자는 앞 4000자까지 보내고 사업 개요(공사기간·위치·발주자 등) 뽑기는 레이더(파이썬 attachment_facts)가 한다. 11-06 시험: 구미 74608 공고문.hwpx 0.1초·491자.
  const R = globalThis.__R;
  const rows = R && R.cities ? R.cities.flatMap((c) => (c.rows || []).filter((x) => x.detail && x.links && x.links.length).map((x) => [c, x])) : [];
  if (!rows.length) { console.log('ATTACH 없음(상세에 첨부 링크가 있는 출입처 줄 없음)'); } else {
    const T0 = Date.now();
    const READ = /\.(?:hwpx|hwp|pdf)$/i;
    const FIRST = /공고문|공고|개요|계획서|고시문|열람/;
    const hwpxText = async (b64) => {
      const u8 = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
      const dv = new DataView(u8.buffer);
      let e = -1;
      for (let i = u8.length - 22; i >= Math.max(0, u8.length - 65557); i--) if (dv.getUint32(i, true) === 0x06054b50) { e = i; break; }
      if (e < 0) return { error: 'hwpx 형식 미상' };
      const secs = [];
      let p = dv.getUint32(e + 16, true);
      for (let k = dv.getUint16(e + 10, true); k > 0 && dv.getUint32(p, true) === 0x02014b50; k--) {
        const method = dv.getUint16(p + 10, true), size = dv.getUint32(p + 20, true), nl = dv.getUint16(p + 28, true);
        const name = new TextDecoder().decode(u8.subarray(p + 46, p + 46 + nl)), lho = dv.getUint32(p + 42, true);
        p += 46 + nl + dv.getUint16(p + 30, true) + dv.getUint16(p + 32, true);
        if (!/^Contents\/section\d+\.xml$/.test(name)) continue;
        const start = lho + 30 + dv.getUint16(lho + 26, true) + dv.getUint16(lho + 28, true);
        const data = u8.subarray(start, start + size);
        const xml = method === 0 ? new TextDecoder().decode(data) : method === 8
          ? await new Response(new Blob([data]).stream().pipeThrough(new DecompressionStream('deflate-raw'))).text() : '';
        secs.push([name, xml]);
      }
      secs.sort((a, b) => (a[0] < b[0] ? -1 : 1));   // 파이썬 sorted()와 같은 순서
      const ta = document.createElement('textarea');
      const text = secs.map(([, x]) => { ta.innerHTML = x.replace(/<[^>]+>/g, ' ').replace(/</g, ' '); return ta.value; }).join(' ').replace(/\s+/g, ' ').trim();
      return { text: text.slice(0, 4000), chars: text.length };
    };
    // <hwpText> HWP 5.0(OLE 복합 문서): 파이썬 hwp_text·hwp_section_text와 같은 규칙 — FileHeader 36번째 바이트 1비트가 압축,
    // BodyText/Section* 스트림(숫자 순)을 raw deflate로 풀고 레코드(태그 10비트·크기 12비트, 0xFFF면 다음 4바이트) 중 문단 글자(67)만.
    const hwpText = async (b64) => {
      const u8 = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
      const dv = new DataView(u8.buffer);
      const U = (o) => dv.getUint32(o, true);
      const ss = 1 << dv.getUint16(30, true), ms = 1 << dv.getUint16(32, true), cutoff = U(56);
      const off = (s) => (s + 1) * ss;
      const fatSecs = [];
      for (let i = 0; i < 109; i++) { const x = U(76 + i * 4); if (x < 0xFFFFFFFA) fatSecs.push(x); }
      for (let s = U(68), n = 0; s < 0xFFFFFFFA && n < 1000; n++) {          // DIFAT 사슬(큰 파일)
        for (let i = 0; i < ss / 4 - 1; i++) { const x = U(off(s) + i * 4); if (x < 0xFFFFFFFA) fatSecs.push(x); }
        s = U(off(s) + ss - 4);
      }
      const fat = [];
      for (const s of fatSecs) for (let i = 0; i < ss / 4; i++) fat.push(U(off(s) + i * 4));
      const chain = (start, table) => { const out = []; for (let s = start; s < 0xFFFFFFFA && out.length <= table.length; s = table[s]) out.push(s); return out; };
      const read = (start) => {
        const secs = chain(start, fat).filter((s) => off(s) + ss <= u8.length);
        const b = new Uint8Array(secs.length * ss);
        secs.forEach((s, i) => b.set(u8.subarray(off(s), off(s) + ss), i * ss));
        return b;
      };
      const dir = read(U(48));
      const ents = [];
      for (let o = 0; o + 128 <= dir.length; o += 128) {
        const d = new DataView(dir.buffer, o, 128);
        ents.push({ name: new TextDecoder('utf-16le').decode(dir.subarray(o, o + Math.max(0, Math.min(64, d.getUint16(64, true)) - 2))), type: dir[o + 66],
          left: d.getUint32(68, true), right: d.getUint32(72, true), child: d.getUint32(76, true), start: d.getUint32(116, true), size: d.getUint32(120, true) });
      }
      const kids = (i, out = [], seen = new Set()) => {
        if (i >= ents.length || seen.has(i)) return out;
        seen.add(i); kids(ents[i].left, out, seen); out.push(ents[i]); kids(ents[i].right, out, seen);
        return out;
      };
      if (!ents.length || ents[0].type !== 5) return { error: 'hwp 형식 미상' };
      const top = kids(ents[0].child);
      const mini = read(ents[0].start);
      const mf = read(U(60)), mfv = new DataView(mf.buffer);
      const minifat = [];
      for (let i = 0; i + 4 <= mf.length; i += 4) minifat.push(mfv.getUint32(i, true));
      const stream = (e) => {
        if (e.size >= cutoff) return read(e.start).subarray(0, e.size);
        const secs = chain(e.start, minifat);
        const b = new Uint8Array(secs.length * ms);
        secs.forEach((s, i) => b.set(mini.subarray(s * ms, s * ms + ms), i * ms));
        return b.subarray(0, e.size);
      };
      const fh = top.find((e) => e.name === 'FileHeader' && e.type === 2), body = top.find((e) => e.name === 'BodyText' && e.type === 1);
      if (!fh || !body) return { error: 'hwp 형식 미상' };
      const compressed = (stream(fh)[36] & 1) === 1;
      const num = (e) => Number(e.name.replace(/\D/g, '') || 0);
      // 제어 문자(0x00~0x1f)·사용자 영역(0xE000~0xF8FF) 글자는 빈칸, 깨진 글자(0xFFFD)는 뺀다 — 파이썬 decode('ignore') + re.sub와 같게.
      // (예약 작업 지시문으로 옮길 때 역슬래시-u 이스케이프가 글자로 바뀌어 정규식이 깨진 일이 있어(11-07) 숫자로 비교한다)
      const clean = (t) => Array.from(t, (ch) => { const c = ch.charCodeAt(0); return c === 0xfffd ? '' : (c < 0x20 || (c >= 0xe000 && c <= 0xf8ff)) ? ' ' : ch; }).join('');
      const secs = kids(body.child).filter((e) => e.type === 2).sort((a, b) => num(a) - num(b));
      const out = [];
      for (const e of secs) {
        let data = stream(e);
        if (compressed) data = new Uint8Array(await new Response(new Blob([data]).stream().pipeThrough(new DecompressionStream('deflate-raw'))).arrayBuffer());
        const v = new DataView(data.buffer, data.byteOffset, data.byteLength);
        const parts = [];
        for (let i = 0; i + 4 <= data.length;) {
          const head = v.getUint32(i, true);
          let size = (head >>> 20) & 0xFFF;
          i += 4;
          if (size === 0xFFF) { size = v.getUint32(i, true); i += 4; }
          if ((head & 0x3FF) === 67) parts.push(clean(new TextDecoder('utf-16le').decode(data.subarray(i, i + size))));
          i += size;
        }
        out.push(parts.join(' ').replace(/\s+/g, ' ').trim());
      }
      const text = out.join(' ').replace(/\s+/g, ' ').trim();
      return { text: text.slice(0, 4000), chars: text.length };
    };
    // </hwpText>
    let read = 0, failed = 0;
    for (const [c, row] of rows.slice(0, 8)) {
      const pick = row.links.filter((l) => READ.test(l.name)).sort((a, b) => (FIRST.test(a.name) ? 0 : 1) - (FIRST.test(b.name) ? 0 : 1)).slice(0, 3);
      const out = [];
      for (const l of pick) {
        if (Date.now() - T0 > 34000) { out.push({ name: l.name, error: '시간 부족 — 다음 수집' }); failed += 1; continue; }   // 45초 안에 끝내기
        try {
          const url = c.base + '/emwp/jsp/ofr/FileDown.jsp?' + new URLSearchParams({ user_file_nm: l.name, sys_file_nm: l.sys, file_path: l.path }).toString();
          const r = await R.within(fetch(url, { headers: { Referer: row.ref } }), 15000, '첨부');
          if (r.status !== 200) throw new Error('HTTP ' + r.status);
          const buf = Buffer.from(await r.arrayBuffer());
          if (buf.length > 6000000) throw new Error('파일이 큼');
          const head = buf.subarray(0, 4).toString('hex');
          if (head.startsWith('504b') || head === 'd0cf11e0') {
            const got = await R.tab.evaluate(head === 'd0cf11e0' ? hwpText : hwpxText, buf.toString('base64'));
            if (got.error) throw new Error(got.error);
            out.push({ name: l.name, text: got.text }); read += 1;
          } else {
            throw new Error(head === '25504446' ? 'pdf — 기자 컴퓨터에서는 안 읽음' : '형식 미상');
          }
        } catch (e) { out.push({ name: l.name, error: String(e && e.message || e).slice(0, 40) }); failed += 1; }
      }
      row.detail.attachments = out;
    }
    R.timing.attachments = Date.now() - T0;
    console.log(`ATTACH 읽음 ${read} · 못 읽음 ${failed} · ${((Date.now() - T0) / 1000).toFixed(1)}초`);
  }
}

// ===== 토막 5: 호주 무역구제 공지(TRN)·진행 사건 공개기록(EPR)과 노동위 달력 14곳(동시에, 40초 안) =====
{
  const R = globalThis.__R || (globalThis.__R = { cities: [], timing: {} });
  const T0 = Date.now();
  const within = (p, ms, what) => Promise.race([p, new Promise((_, no) => setTimeout(() => no(new Error(`${what} 시간 초과 ${ms / 1000}초`)), ms))]);
  const TRN = 'https://www.industry.gov.au/australian-trade-remedies-commission/trade-remedies-notices-trns';
  const EPR = 'https://www.industry.gov.au/australian-trade-remedies-commission/current-cases-and-electronic-public-record-epr';
  const LABOR = 'https://www.nlrc.go.kr/nlrc/meetingSche/index.do';
  const NAMES = ['중앙노동위원회', '서울지방노동위원회', '부산지방노동위원회', '경기지방노동위원회', '인천지방노동위원회', '강원지방노동위원회',
    '충북지방노동위원회', '충남지방노동위원회', '전북지방노동위원회', '전남지방노동위원회', '경북지방노동위원회', '경남지방노동위원회',
    '울산지방노동위원회', '제주지방노동위원회'];
  const trn = async () => {
    try {
      const r = await within(fetch(TRN), 35000, 'TRN');
      if (r.status !== 200) throw new Error('HTTP ' + r.status);
      const tab = R.tab || (R.tab = await openTab('about:blank'));   // 토막 6이 닫는다
      const b64 = Buffer.from(await r.arrayBuffer()).toString('base64');
      const rows = await tab.evaluate((a) => {
        const u = Uint8Array.from(atob(a), (c) => c.charCodeAt(0));
        const d = new DOMParser().parseFromString(new TextDecoder('utf-8').decode(u), 'text/html');
        return [...d.querySelectorAll('tr')].filter((tr) => /korea/i.test(tr.textContent)).map((tr) => ({
          cells: [...tr.querySelectorAll('td,th')].map((c) => c.textContent.replace(/\s+/g, ' ').trim()).filter(Boolean),
          links: [...tr.querySelectorAll('a')].map((x) => x.getAttribute('href')).filter(Boolean).slice(0, 4) })).filter((x) => x.cells.length).slice(0, 200);
      }, b64);
      return rows.length ? { id: 'au-trn', rows } : { id: 'au-trn', error: '한국 줄 0줄' };
    } catch (e) { return { id: 'au-trn', error: String(e && e.message || e).slice(0, 100) }; }
  };
  // 호주 진행 사건 목록에서 한국이 든 줄 → 그 사건 페이지의 사건 정보·주요 일정·공개기록(EPR) 문서 표(번호·종류·제목·날짜·첫 PDF 링크).
  // 11-14 내장 브라우저 확인: 진행 28건 중 한국 3건(698·706·710), 사건 페이지 약 180KB·2.5~3.5초, 문서 13~22줄, 쪽 나눔 없음.
  // 줄 첫 칸이 종류(list·case·title·info·date·doc·error), 둘째 칸이 사건 번호 — 레이더(au_epr_cases.py)가 읽는다. 빈 칸은 '-'(칸 순서를 지키려고).
  const epr = async () => {
    try {
      const tab = R.tab || (R.tab = await openTab('about:blank'));   // 토막 6이 닫는다
      const left = () => Math.max(4000, 36000 - (Date.now() - T0));      // TRN 뒤에 남은 시간(토막을 45초 안에 끝내기)
      const page = async (url, what) => {
        const r = await within(fetch(url), left(), what);
        if (r.status !== 200) throw new Error('HTTP ' + r.status);
        return Buffer.from(await r.arrayBuffer()).toString('base64');
      };
      const list = await tab.evaluate((a) => {
        const u = Uint8Array.from(atob(a), (c) => c.charCodeAt(0));
        const d = new DOMParser().parseFromString(new TextDecoder('utf-8').decode(u), 'text/html');
        const t = (n) => n.textContent.replace(/\s+/g, ' ').trim();
        const all = [...(d.querySelector('main') || d.body).querySelectorAll('tr')].filter((tr) => tr.querySelector('td'));
        const rows = [];
        for (const tr of all.filter((x) => /korea/i.test(x.textContent))) {
          const m = [...tr.querySelectorAll('a')].map((x) => /\/current-cases-and-electronic-public-record-epr\/([A-Za-z0-9-]{1,20})\/?$/.exec(x.getAttribute('href') || '')).find(Boolean);
          if (m && !rows.some((x) => x.no === m[1])) rows.push({ no: m[1], cells: [...tr.querySelectorAll('td')].slice(0, 7).map((c) => t(c).slice(0, 200) || '-') });
        }
        return { total: all.length, rows };
      }, await page(EPR, 'EPR 목록'));
      if (!list.total) throw new Error('진행 사건 목록 0줄');
      const parseCase = (a) => {
        const u = Uint8Array.from(atob(a), (c) => c.charCodeAt(0));
        const d = new DOMParser().parseFromString(new TextDecoder('utf-8').decode(u), 'text/html');
        const t = (n) => n.textContent.replace(/\s+/g, ' ').trim();
        const main = d.querySelector('main') || d.body;
        const h1 = main.querySelector('h1');
        const got = { title: h1 ? t(h1).slice(0, 200) : '', info: [], dates: [], docs: [], total: 0 };
        for (const tb of main.querySelectorAll('table')) {
          const trs = [...tb.querySelectorAll('tr')];
          const head = trs.length ? t(trs[0]) : '';                       // 표 이름은 머리 줄(thead)에 있기도, 첫 줄 한 칸에 있기도 하다(698)
          if (/^EPR number/i.test(head)) {
            const body = trs.slice(1).filter((tr) => tr.children.length >= 4);
            got.total += body.length;
            for (const tr of body.slice(0, 60)) {
              const a1 = tr.querySelector('a[href]');
              got.docs.push({ cells: [...tr.children].slice(0, 4).map((c) => t(c).slice(0, 280) || '-'), link: a1 ? a1.getAttribute('href') : null });
            }
          } else if (/^(?:Case information|Key Dates)$/i.test(head)) {
            const into = /^Key/i.test(head) ? got.dates : got.info;
            for (const tr of trs.slice(1)) {
              const c = [...tr.children].map(t);
              for (let i = 0; i + 1 < c.length; i += 2) if (c[i] && c[i + 1] && !/contact|mailing/i.test(c[i])) into.push([c[i].slice(0, 120), c[i + 1].slice(0, 280)]);
            }
          }
        }
        return got;
      };
      const cases = list.rows.slice(0, 6);
      const per = await Promise.all(cases.map(async (c) => {
        try {
          const got = await tab.evaluate(parseCase, await page(EPR + '/' + c.no, '사건 ' + c.no));
          if (!got.title && !got.docs.length) throw new Error('사건 페이지 형식 미상');
          return [{ cells: ['title', c.no, got.title || '-', String(got.total)] },
            ...got.info.slice(0, 6).map(([k, v]) => ({ cells: ['info', c.no, k, v] })),
            ...got.dates.slice(0, 12).map(([k, v]) => ({ cells: ['date', c.no, k, v] })),
            ...got.docs.map((x) => ({ cells: ['doc', c.no, ...x.cells], ...(x.link ? { links: [x.link] } : {}) }))];
        } catch (e) { return [{ cells: ['error', c.no, String(e && e.message || e).slice(0, 100)] }]; }
      }));
      return { id: 'au-epr', rows: [{ cells: ['list', String(list.total), String(list.rows.length)] },
        ...cases.map((c) => ({ cells: ['case', c.no, ...c.cells], links: [EPR.replace('https://www.industry.gov.au', '') + '/' + c.no] })), ...per.flat()] };
    } catch (e) { return { id: 'au-epr', error: String(e && e.message || e).slice(0, 100) }; }
  };
  const labor = async () => {
    try {
      const lt = await within(openTab(LABOR), 20000, '노동위 달력 열기');
      const out = await within(lt.evaluate(async () => {   // 달력 화면 자신의 요청(같은 사이트·같은 세션) — 예전 [노동위 시작 코드]와 같음
        const C = [['중앙노동위원회', '', '00'], ['서울지방노동위원회', 'seoul', '01'], ['부산지방노동위원회', 'busan', '02'], ['경기지방노동위원회', 'gyeonggi', '03'],
          ['인천지방노동위원회', 'incheon', '08'], ['강원지방노동위원회', 'gangwon', '09'], ['충북지방노동위원회', 'chungbuk', '10'], ['충남지방노동위원회', 'chungnam', '04'],
          ['전북지방노동위원회', 'jeonbuk', '11'], ['전남지방노동위원회', 'jeonnam', '05'], ['경북지방노동위원회', 'gyeongbuk', '06'], ['경남지방노동위원회', 'gyeongnam', '07'],
          ['울산지방노동위원회', 'ulsan', '13'], ['제주지방노동위원회', 'jeju', '12']];
        const day = (d) => new Date(Date.now() + 9 * 3600e3 + d * 86400e3).toISOString().slice(0, 10);
        const from = day(0), to = day(14);
        const res = [];
        for (const [commission, slug, cd] of C) {
          try {
            if (typeof $ === 'undefined' || !$.ajax) throw new Error('달력 화면이 아님(jQuery 없음)');
            const r = await $.ajax({ url: slug ? `/nlrc/${slug}/meetingSche/selectMeetingSche.do` : '/nlrc/meetingSche/selectMeetingSche.do', method: 'post',
              dataType: 'json', timeout: 15000, data: { cmitCd: cd, icdnNo: '', kornIcdnNo: '', likeColumn: 'ICDN_NO', initialDate: from, whereStartDate: from, whereEndDate: to } });
            const lo = from.replaceAll('-', ''), hi = to.replaceAll('-', '');
            const rows = [...new Set((r.mtgScdlList || []).filter((x) => x.cmitCd === cd && x.mtgYmd >= lo && x.mtgYmd <= hi)
              .map((x) => `${x.mtgId}/${x.mtgSn}/${x.mtgYmd}/${String(x.mtgNm || '').replace(/[\/\s]+/g, ' ').trim().slice(0, 30)}`))].slice(0, 300);
            res.push(rows.length ? { commission, rows } : { commission, error: '회의 0건' });
          } catch (e) { res.push({ commission, error: String(e && (e.statusText || e.message) || e).slice(0, 100) }); }
          await new Promise((ok) => setTimeout(ok, 300));
        }
        return res;
      }), 38000, '노동위 달력');
      try { await closeTab(lt); } catch (e) { /* 탭은 남아도 된다 */ }
      return out;
    } catch (e) { return NAMES.map((commission) => ({ commission, error: String(e && e.message || e).slice(0, 100) })); }
  };
  // TRN 다음에 EPR(같은 사이트라 차례로), 노동위 달력은 그와 동시에
  [[R.pages, R.epr], R.labor] = await Promise.all([(async () => [await trn(), await epr()])(), labor()]);
  R.timing.trnLabor = Date.now() - T0;
  const kind = (k) => (R.epr.rows || []).filter((x) => x.cells[0] === k).length;
  console.log(`TRN ${R.pages.error ? '실패(' + R.pages.error + ')' : R.pages.rows.length + '줄'} · `
    + `EPR ${R.epr.error ? '실패(' + R.epr.error + ')' : `사건 ${kind('case')}건·문서 ${kind('doc')}줄${kind('error') ? '·못 읽은 사건 ' + kind('error') : ''}`} · 노동위 ${R.labor.filter((x) => !x.error).length}/14곳 `
    + `${R.labor.reduce((n, x) => n + (x.rows ? x.rows.length : 0), 0)}건 · ${((Date.now() - T0) / 1000).toFixed(1)}초`);
}

// ===== 토막 6: 레이더에 직접 올리기(열쇠가 없거나 실패하면 SUBMIT 줄 — 예약 작업이 그 JSON을 고치지 말고 local_notice_submit으로 올린다) =====
{
  const R = globalThis.__R;
  const UPLOAD = 'https://seoul-reporting-radar.shhong9173.workers.dev/upload/browser';
  const CITY_NAMES = ['인천 부평구', '구미시', '청주시', '순천시', '함평군', '양산시', '광주 광산구', '나주시', '광양시', '천안시', '평택시', '원주시'];
  const lost = '수집 세션이 끊김(Aside 재시작 등) — 다시 수집 필요';
  const cities = CITY_NAMES.map((name) => {
    const c = R && R.cities.find((x) => x.city === name);
    return !c ? { city: name, error: lost } : c.error ? { city: name, error: c.error }
      : { city: name, rows: c.rows.map((x) => ({ mgt: x.mgt, cells: x.cells, ...(x.detail ? { detail: x.detail } : {}) })) };   // 첨부 링크·Referer는 보내지 않음
  });
  const pages = [R && R.pages ? R.pages : { id: 'au-trn', error: lost }, R && R.epr ? R.epr : { id: 'au-epr', error: lost }];
  const labor = R && R.labor ? R.labor : ['중앙노동위원회', '서울지방노동위원회', '부산지방노동위원회', '경기지방노동위원회', '인천지방노동위원회',
    '강원지방노동위원회', '충북지방노동위원회', '충남지방노동위원회', '전북지방노동위원회', '전남지방노동위원회', '경북지방노동위원회',
    '경남지방노동위원회', '울산지방노동위원회', '제주지방노동위원회'].map((commission) => ({ commission, error: lost }));
  const payload = { cities, pages, labor, via: 'aside' };
  // 대화로 옮겨 올릴 때(SUBMIT)는 사건 공개기록(au-epr)을 뺀다 — 양이 많아 옮겨 적다 틀리기 쉽다. 레이더는 직전에 올린 것을 그대로 둔다(오래되면 미확인)
  const small = { ...payload, pages: pages.slice(0, 1) };
  try { if (R && R.tab) await closeTab(R.tab); } catch (e) { /* 그대로 둔다 */ }
  console.log('TIMING ' + JSON.stringify(R ? R.timing : {}));
  if (!R || !R.cities || !R.cities.length) {
    // 토막 사이에 Aside REPL이 새로 시작돼 앞 결과가 사라졌다 — 오류만 든 인자를 올리지 않고 예약 작업이 토막 1부터 한 번 다시 한다
    console.log('LOST 앞 토막 결과가 없음(REPL 새로 시작) — 토막 1부터 한 번 다시. 두 번째도 LOST면 아래 SUBMIT을 그대로 올린다');
    console.log('SUBMIT ' + JSON.stringify(small));
  } else {
    // 직접 올리기(11-06): 열쇠는 이 사이트 저장소(localStorage)에만 있다 — 코드는 읽어서 보내기만 하고 찍지 않는다
    let up = null;
    try {
      const ut = await openTab(UPLOAD);
      try {
        up = await ut.evaluate(async (body) => {
          const k = localStorage.getItem('radarUploadKey');
          if (!k) return { skip: '열쇠 없음' };
          const r = await fetch('/upload/browser', { method: 'POST', headers: { Authorization: 'Bearer ' + k, 'Content-Type': 'application/json' }, body });
          return { status: r.status, body: (await r.text()).slice(0, 6000) };
        }, JSON.stringify(payload));
      } finally { try { await closeTab(ut); } catch (e) { /* 그대로 둔다 */ } }
    } catch (e) { up = { error: String(e && e.message || e).slice(0, 100) }; }
    let done = false;
    if (up && up.status === 200) {
      try { const j = JSON.parse(up.body); if (j.ok) { console.log('UPLOADED ' + j.text); done = true; } else { up = { error: '레이더가 거절: ' + String(j.text).slice(0, 200) }; } } catch (e) { up = { error: '응답 형식' }; }
    }
    if (!done) {
      console.log('UPLOAD 못 함(' + (up ? (up.skip || up.error || 'HTTP ' + up.status) : '?') + ') — 아래 SUBMIT을 local_notice_submit으로 올린다');
      console.log('SUBMIT ' + JSON.stringify(small));
    }
  }
}
