const assert=require('node:assert/strict');
const fs=require('node:fs');
const html=fs.readFileSync('patents.html','utf8');
for(const match of html.matchAll(/<script>([\s\S]*?)<\/script>/g))new Function(match[1]);
for(const marker of ['digests/patent_deep_latest.json','patentDatasetGeneratedAt',
 'uniquePublicationCount','jointApplications','relatedRecent','techNoveltyStatus',
 '원문·청구항 찾기','textContent']){
 assert(html.includes(marker),'missing '+marker);
}
assert(!html.includes('innerHTML'),'never permit KIPRIS API field HTML injections');
console.log('KIPRIS deep-compare UI syntax and data provenance checks passed');