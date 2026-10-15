const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const html=fs.readFileSync('patent-rnd-dossiers.html','utf8');
const scripts=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
assert.equal(scripts.length,1);
new vm.Script(scripts[0][1],{filename:'patent-rnd-dossiers.js'});
for(const text of [
  'ntis-project-reverse-status',
  'digests/ntis_project_reverse_plan_latest.json',
  'digests/ntis_project_reverse_pc_latest.json',
  'plan.projectCount===26',
  'record.planGeneratedAt===ntisReversePlan.generatedAt',
  'record.kiprisDossierGeneratedAt===ntisReversePlan.kiprisDossierGeneratedAt',
  'record.verifiedPatentProjectOutcomes===0',
  'record.confirmedCommercialization===0',
  'record.confirmedExclusives===0',
  'ntisReverseResult.completedProjects',
  'ntisReverseResult.reviewedNumberPairs',
  '...ntisReverseResult.records',
  '...ntisRemainingResult?.records||[]',
  '.filter(a=>a.publicationNumber===x.publicationNumber)',
  'PC 수집 아직 미실행',
  '첫 페이지만 확인',
  '전체 NTIS 성과가 없다는 뜻은 아닙니다.'
]){
  assert(html.includes(text),'missing source guard or reverse result explanation '+text);
}
assert(!html.includes('innerHTML'));
assert(!html.includes('apprvKey'));
console.log('PASS: reverse NTIS status uses strict provenance and no scoop/absence overclaims');
