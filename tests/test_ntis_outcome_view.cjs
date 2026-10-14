const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const html=fs.readFileSync('patent-rnd-dossiers.html','utf8');
const scripts=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
assert.equal(scripts.length,1);
new vm.Script(scripts[0][1],{filename:'patent-rnd-dossiers.js'});
for(const phrase of [
 'ntis-outcome-status','ntis_patent_outcome_links_latest.json',
 'parsed.dossierGeneratedAt===data.generatedAt',
 'parsed.confirmedPatentProjectLinks===0',
 'parsed.exclusiveConfirmed===0',
 'parsed.commercializationConfirmed===0',
 'outcomeAudit.potentialExactNumberPairsNeedingHumanReview',
 'outcomeAudit.outcomeQueriesCompleted',
 'outcomeAudit.outcomeSearchTotalHits',
 '특허 성과 부재 판정 아님',
 '15077316/openapi.do',
]){
 assert(html.includes(phrase),'missing evidence gate: '+phrase)
}
assert(!html.includes('innerHTML'));
assert(!html.includes('apprvKey'));
console.log('NTIS patent outcome audit UI parse and fail-closed gates passed');
