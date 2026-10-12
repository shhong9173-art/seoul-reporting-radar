const assert=require('node:assert/strict');
const fs=require('node:fs');
const html=fs.readFileSync('data-lab.html','utf8');
const scripts=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(x=>x[1]);
assert(scripts.length>=2,'separate peer & business source renderers');
for(const script of scripts)new Function(script);
for(const token of ['digests/business_content_latest.json','business-evidence','period.receiptNo','사업보고서 본문','공식 자료']){
  assert(html.includes(token),token+' missing from business evidence viewer');
}
assert(!html.includes('innerHTML'),'external DART content must not be inserted as HTML');
console.log('Business content original-source viewer checks passed');
