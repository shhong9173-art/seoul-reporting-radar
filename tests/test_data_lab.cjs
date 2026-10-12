// Static safe-render smoke test, no network or browser access.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const page=fs.readFileSync('data-lab.html','utf8');
const js=page.match(/<script>([\s\S]*?)<\/script>/);
assert(js,'missing research renderer');
new Function(js[1]);
for(const text of ['digests/peer_financial_latest.json','최근 사업보고서',
                  '최근 반기 누적','단독 미확정','textContent','공시 원문']){
  assert(page.includes(text),'missing report/source marker '+text);
}
assert(!page.includes('innerHTML'),'untrusted external rows must use textContent');
const index=fs.readFileSync('index.html','utf8');
assert(index.includes('data-lab.html'),'missing main navigation');
console.log('Data lab rendering source/limitations checks passed');
