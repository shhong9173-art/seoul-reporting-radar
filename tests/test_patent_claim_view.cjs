const assert=require('node:assert/strict');
const fs=require('node:fs');
const page=fs.readFileSync('patents.html','utf8');
const scripts=[...page.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(x=>x[1]);
assert.equal(scripts.length,3);
for(const script of scripts)new Function(script);
for(const part of ['digests/patent_claim_review_latest.json','claim1Excerpt',
 'claim1Length','priorComparisons','textSimilarity','companyQuestions',
 'claimVerified','patentDatasetGeneratedAt','deepDatasetGeneratedAt',
 '기보도','청구항','단독 미확정','textContent']){
 assert(page.includes(part),'claim evidence missing '+part)
}
assert(!page.includes('innerHTML'),'public patent XML must not inject HTML');
console.log('Claim1 official document comparison dashboard passed');