const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const html=fs.readFileSync('patent-rnd-dossiers.html','utf8');
const embedded=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
assert.equal(embedded.length,1,'Only one inline page script');
new vm.Script(embedded[0][1],{filename:'patent-rnd-dossiers.js'});
for(const marker of [
  'id="ntis-followup-status"',
  'ntis_patent_followup_pc_latest.json',
  't.sourceDiscoveryGeneratedAt===ntisDiscovery.generatedAt',
  't.sourceDossierGeneratedAt===ntisDiscovery.dossierGeneratedAt',
  't.officialPatentProjectLinksConfirmed===0',
  't.commercializationConfirmed===0',
  't.exclusiveConfirmed===0',
  'ntisFollowup.additionalScannedRows',
  'ntisFollowup.exactApplicationProjectNumberReviewCandidates',
  'ntisFollowup.actualHttpRequests',
  'q.targets.some(t=>t.publicationNumber===x.publicationNumber)',
  'q.pagesCompleted.join(",")',
  '미확인 페이지가 남아 있으며',
  '특허 성과 0건 판정은 불가합니다',
]){
  assert(html.includes(marker),'Missing NTIS evidence scope guard '+marker);
}
assert(!html.includes('innerHTML'),'Raw NTIS data must use textContent, not innerHTML');
assert(!html.includes('apprvKey'),'API credential must not be exposed to client');
console.log('PASS: NTIS registered-PC follow-up view, provenance and uncertainty guards');
