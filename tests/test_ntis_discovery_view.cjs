const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');

const html=fs.readFileSync('patent-rnd-dossiers.html','utf8');
const scripts=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
assert.equal(scripts.length,1,'single patent dossier script expected');
new vm.Script(scripts[0][1],{filename:'patent-rnd-dossiers.js'});
for(const text of [
  'ntis-discovery-status',
  'ntis_patent_discovery_pc_latest.json',
  'parsed.dossierGeneratedAt===data.generatedAt',
  'parsed.verifiedDirectPatentProjectLinks===0',
  'parsed.commercializationConfirmed===0',
  'parsed.exclusiveConfirmed===0',
  'parsed.collectionMethod==="approved_pc_rpatent_keyword_discovery"',
  'ntisDiscovery.scannedOutcomeRows',
  'ntisDiscovery.totalSearchHitsAcrossQueries',
  '중복 검색 포함',
  '중복 가능',
  'q.truncated',
  '미확인 페이지 존재',
  '정확한 출원번호',
  '성과 부재의 증거가 아닙니다.',
]){
  assert(html.includes(text),'missing provenance/uncertainty guard: '+text);
}
assert(!html.includes('innerHTML'),'no raw NTIS HTML injection');
assert(!html.includes('apprvKey'),'never expose NTIS API key in page');
console.log('PASS: NTIS keyword discovery UI parses; exact-number gates, pagination and overlap caveats present');
