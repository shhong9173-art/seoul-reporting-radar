const assert=require('node:assert/strict');
const fs=require('node:fs');
const s=fs.readFileSync('data-lab.html','utf8');
const scripts=[...s.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(x=>x[1]);
assert(scripts.length>=3);
for(const code of scripts)new Function(code);
for(const wanted of ["digests/business_metrics_latest.json","sourceGeneratedAt","validated-business-results",
                     "원자료와 검산 파일 생성시각 불일치","단독 미확정","DART"]){
  assert(s.includes(wanted),"Missing secure evidence marker "+wanted);
}
assert(!s.includes("innerHTML"),"No untrusted HTML injection");
console.log("Validated business metric viewer passed static safety check");
