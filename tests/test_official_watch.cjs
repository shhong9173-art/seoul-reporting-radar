const assert=require('node:assert/strict');
const fs=require('node:fs');
const page=fs.readFileSync('official-watch.html','utf8');
const scripts=[...page.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(x=>x[1]);
assert.equal(scripts.length,1);
new Function(scripts[0]);
for(const phrase of ["digests/overseas_official_latest.json",
                     "digests/recent_contracts_latest.json",
                     "원공시 독립 대조","검색 결과 0건","단독","textContent"]){
  assert(page.includes(phrase),"official source evidence missing: "+phrase);
}
assert(!page.includes('innerHTML'),'never put public API text into HTML markup');
assert(fs.readFileSync('pages.html','utf8').includes('official-watch.html'));  // 메뉴에서 뺐지만 모든 페이지 목록에서 열린다
console.log('Official overseas and contract source evidence UI passed');
