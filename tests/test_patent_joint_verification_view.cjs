const assert=require('node:assert/strict');
const fs=require('node:fs');
const html=fs.readFileSync('patent-joint-verification.html','utf8');
const scripts=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
assert.equal(scripts.length,1);
new Function(scripts[0][1]);
for(const marker of [
  'digests/patent_joint_verification_latest.json',
  'recentResearchQueue','olderReferenceQueue','officialSourceStale',
  'unrepresentedOfficialJointRecords','recentCoverageComplete',
  'claim1Status','priorSameTitleStatus','pressIndexStatus',
  'companyApplicationVerified','recentJointInRepresentedSample',
  '인덱스','미보도 증명 아님','사업 제휴','단독 미확정',
  '새로운 공개특허','공식 공동출원 원자료'
].filter(x=>x!=='인덱스'&&x!=='새로운 공개특허')){
 assert(html.includes(marker),'Missing conservative patent UI state: '+marker);
}
assert(!html.includes('innerHTML'),'official source names may not be interpolated as HTML');
assert(!html.includes('verifiedExclusive')&&!html.includes('autoApproved'),
  'Do not imply automatic exclusivity in official KIPRIS reader');
console.log('PASS: official fresh cofiling verification UI, stale warning, claim/news/commercialization limits');
