const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const html=fs.readFileSync('patent-rnd-dossiers.html','utf8');
const inline=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
assert.equal(inline.length,1);
new vm.Script(inline[0][1],{filename:'patent-rnd-dossiers.js'});
for(const label of [
  'id="ntis-project-remaining-status"',
  'digests/ntis_project_field_probe_pc_latest.json',
  'projectIndexControl.exactReferenceOutcomeRecoveredInAnyMode===true',
  '[tiControl,biControl,ti03Control].every(controlRecovered)',
  'digests/ntis_project_reverse_remaining_23_pc_latest.json',
  'ntisReversePlan.projects.slice(3)',
  'payload.plannedUniqueProjects===23',
  'payload.maximumHttpRequests===46',
  'payload.actualHttpRequests<=46',
  'payload.confirmedCommercialization===0',
  'payload.confirmedExclusives===0',
  'actualIds.every((id,index)=>id===expectedIds[index])',
  'ntisRemainingResult?.records||[]',
  '전체 26개 중 첫 3개 실조회 완료',
  '남은 23개 공식 역조회 실행 대기',
  '0건도 성과 부재 판정 아님',
]){
  assert(html.includes(label),'Missing approved-PC historical index evidence '+label);
}
assert(!html.includes('innerHTML'),'Official NTIS data must not be rendered as raw HTML');
assert(!html.includes('apprvKey'),'Do not expose credentials in view');
console.log('PASS: 3+23 NTIS reverse state preserves pilot and live ProjectID control provenance');
