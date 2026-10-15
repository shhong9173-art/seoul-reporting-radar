const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const html=fs.readFileSync('patent-rnd-dossiers.html','utf8');
const inline=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
assert.equal(inline.length,1);
new vm.Script(inline[0][1],{filename:'patent-rnd-dossiers.js'});
for(const term of [
 'id="ntis-project-id-index-control-status"',
 'ntis_project_field_probe_pc_latest.json',
 'control.profile==="ntis_rpatent_project_id_index_control_v1"',
 'control.controlProjectIdExported===false',
 'control.controlResultIdExported===false',
 'control.verifiedPatentProjectOutcomeLinks===0',
 'control.commercializationConfirmed===0',
 'control.exclusiveConfirmed===0',
 'control.searchModes.length',
 'controlRecovered(tiControl)',
 'controlRecovered(biControl)',
 'controlRecovered(ti03Control)',
 '나머지 23개 일괄조회 보류',
 '과제번호 검색 자체가 검증되지 않아',
 '국가R&D 특허 성과 부재 증명 아님',
]){
  assert(html.includes(term),'Missing NTIS ProjectID control evidence caveat '+term);
}
assert(!html.includes('innerHTML'),'Never render official NTIS data as markup');
assert(!html.includes('apprvKey'),'Never expose API secret');
console.log('PASS: positive control UI syntax, source/data guards and no false reverse search claims');
