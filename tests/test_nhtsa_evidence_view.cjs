const assert=require('node:assert/strict');
const {describe}=require('../nhtsa-evidence-view.js');
const data={generatedAt:'2026-10-17T17:08:38+09:00',newlyObserved:2,items:[{
 actionNumber:'EA25003',openedDate:'20250101',closedDate:'20260918',model:'RIDGELINE',
 vehicles:[{make:'HONDA',model:'RIDGELINE',modelYear:'2017'},{make:'HONDA',model:'RIDGELINE',modelYear:'2018'}]}]};
const fail=describe(data,{generatedAt:'2026-10-17T18:00:00+09:00',status:'source_error'});
assert(fail.status.includes('최신 NHTSA 원천 수집 실패'));
assert(fail.status.includes('보존·참고 자료 1건'));
assert(fail.rows[0].text.includes('종결일 20260918'));
assert(fail.rows[0].text.includes('2행'));
assert(fail.status.includes('신규 발표 아님'));
assert(describe(data,{generatedAt:data.generatedAt,status:'checked'}).status.includes('공식 원천 조회 확인'));
assert(describe(data,{generatedAt:'invalid',status:'checked'}).status.includes('미확인'));
assert(describe(null,null).status.includes('0건으로 해석 금지'));
console.log('NHTSA cached evidence/latest failure and closure display passed');
