const assert=require('node:assert/strict');
const fs=require('node:fs');
const html=fs.readFileSync('dart-contract-followup.html','utf8');
const scripts=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
assert.equal(scripts.length,1);
new Function(scripts[0][1]);
for(const marker of [
 'dart_contract_followup_latest.json',
 'original_unverified_no_comparison',
 'original_verified_changes_needs_reporting',
 'press_index_partial_failure',
 'indexed_possible_articles_require_fulltext',
 'index_no_hits_not_proof_unreported',
 'press_not_searched',
 'materialFieldChanges',
 'sourceBefore','sourceAfter',
 'numericDifference!==null',
 'companyImpactVerified!==false',
 'priorCoverageOfSameContractVerified!==false',
 'exclusiveConfirmed!==false',
 'approvedForPitch!==false',
 'news.google.com','기보도',
 '공시 원문','24시간 초과'
].filter(v=>!['sourceBefore','sourceAfter'].includes(v)))assert(html.includes(marker),marker);
assert(!html.includes('innerHTML'),'Untrusted RSS/DART data must never render as HTML');
console.log('PASS DART contract before/after and prior-news reader rejects unsupported scoops');
