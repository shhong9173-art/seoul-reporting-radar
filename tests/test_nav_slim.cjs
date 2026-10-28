// 홈 메뉴를 줄여도 페이지는 지우지 않고 모든 페이지 목록에서 열린다. 숨긴 화면 버튼은 DOM에 남아 app.js 카운트가 깨지지 않는다.
const fs = require('fs');
const assert = require('assert');
const home = fs.readFileSync('index.html', 'utf8');
const list = fs.readFileSync('pages.html', 'utf8');
const pages = fs.readdirSync('.').filter((f) => f.endsWith('.html') && !['index.html', 'pages.html'].includes(f));
for (const f of pages) assert(home.includes(`href="${f}"`) || list.includes(`href="${f}"`), `${f}가 메뉴에도 목록에도 없음`);
assert(home.includes('href="pages.html"'));
for (const id of ['countGlobal', 'countFollow', 'countCompetition', 'countAll', 'countMust']) assert(home.includes(`id="${id}"`), `${id} 사라짐`);
for (const v of ['calls', 'keywords', 'issues', 'global']) {
  assert(new RegExp(`data-view="${v}" hidden`).test(home), `${v} 버튼은 숨김으로 남아야 함`);
  assert(list.includes(`index.html#view=${v}`), `${v} 화면 링크 없음`);
}
const navLinks = (home.match(/class="nav nav-link"/g) || []).length;
assert(navLinks <= 6, `메뉴 링크 ${navLinks}개 — 너무 많음`);
assert(fs.readFileSync('nav_more.js', 'utf8').includes(':not([hidden])'));
console.log('nav slim ok', { pages: pages.length, navLinks });
