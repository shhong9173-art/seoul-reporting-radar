const assert=require('node:assert/strict');
const fs=require('node:fs');
const page=fs.readFileSync('data-lab.html','utf8');
const scripts=[...page.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(x=>x[1]);
assert(scripts.length>=6,'expected independent source-based panels');
for(const script of scripts)new Function(script);
for(const term of [
 'digests/recent_business_latest.json','recent-business-status',
 '전년 동기 DART 원문','새로운 투자나 미보도 사실로 확정하지 않는다',
 'Latest Interim Business Source Scout','pressLink','textContent'
])assert(page.includes(term),"missing evidence label: "+term);
assert(!page.includes('innerHTML'),'untrusted filing text must use textContent');
console.log('Recent business disclosure panel safety and syntax passed');
