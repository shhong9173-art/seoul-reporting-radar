const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const html=fs.readFileSync('patent-rnd-dossiers.html','utf8');
const scripts=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
assert.equal(scripts.length,1);
new vm.Script(scripts[0][1],{filename:'patent-rnd-dossiers-page-followup.js'});
for(const str of [
 'id="ntis-page-followup-status"',
 'digests/ntis_project_page_followup_pc_latest.json',
 'ntisRemainingResult.generatedAt==="2026-10-15T10:52:32+09:00"',
 'obj.offlineSynthetic===false',
 'obj.currentQueryTotalHits===11',
 'obj.distinctResultIDs===11',
 'obj.currentQueryFullyInspected===true',
 'obj.planGeneratedAt===ntisReversePlan.generatedAt',
 'targets.has(x.publicationNumber+"|"+x.applicationNumber)',
 'ntisPageFollowup?.records||[]',
 '11번째 항목 미확인',
 '기존 10건의 당시 성과ID는 미보존',
 '단독/사업화 증명 아님'
])assert(html.includes(str),'Required NTIS provenance/gap marker missing: '+str);
assert(!html.includes('innerHTML'),'Untrusted official data must not use innerHTML');
console.log('PASS NTIS 11th row gap visible and only verified followup included in review leads');
