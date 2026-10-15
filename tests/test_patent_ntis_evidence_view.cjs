const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const html=fs.readFileSync('patent-pitches.html','utf8');
const scripts=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
assert.equal(scripts.length,1);
new vm.Script(scripts[0][1],{filename:'patent-pitches-ntis-status.js'});
for(const marker of [
 'rankState.ntisResearchEvidence',
 'keyword_only_no_frozen_kipris_application',
 'partially_inspected_no_official_pair_observed',
 'same_official_hit_number_pair_for_human_review',
 'bounded_inspected_no_official_pair_observed',
 '미확인 과제 페이지',
 '동일 공식 성과행 번호 대조',
 '성공',
 '후보 가점이나 발제 승인이 아닙니다.'
].filter(x=>x!=='성공')){
 assert(html.includes(marker),'Unverified NTIS evidence cannot be hidden: '+marker);
}
console.log('PASS patent pitches distinguish NTIS partial/keyword/official same-hit evidence');
