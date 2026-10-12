const assert=require('node:assert/strict');
const fs=require('node:fs');
const page=fs.readFileSync('data-lab.html','utf8');
const scripts=[...page.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(x=>x[1]);
assert(scripts.length>=4,'expected isolated source/chart/audit scripts');
for(const s of scripts)new Function(s);
for(const key of ['digests/business_coverage_latest.json','metricsGeneratedAt',
                  'business-news-status','단독','news.google.com']){
  assert(page.includes(key),'missing '+key);
}
assert(!page.includes('innerHTML'),'no untrusted external content as HTML');
console.log('Business news evidence UI validated');
