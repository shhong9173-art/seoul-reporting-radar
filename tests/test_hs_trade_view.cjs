const assert=require('node:assert/strict');
const fs=require('node:fs');
const page=fs.readFileSync('data-lab.html','utf8');
for(const code of [...page.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(v=>v[1]))
  new Function(code);
for(const str of ['digests/hs_trends_latest.json','hs-status','exportWeightYoYPercent',
                  'unitValueYoYPercent','개별 기업 수출액이 아님']){
  assert(page.includes(str),"missing "+str);
}
assert(!page.includes('innerHTML'));
console.log('HS external evidence viewer syntax and source labeling passed');
