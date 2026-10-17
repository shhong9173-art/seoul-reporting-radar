const fs=require('node:fs'),assert=require('node:assert/strict');
const page=fs.readFileSync('federal-register-evidence.html','utf8');
for(const [,script] of page.matchAll(/<script>([\s\S]*?)<\/script>/g))new Function(script);
assert(!page.includes('innerHTML'));
for(const marker of ['textContent','failedDocuments','unqueriedDocuments','과거·날짜 미확인','www.federalregister.gov','단독 확정 0건'])assert(page.includes(marker));
console.log('Federal Register evidence UI guards passed');
