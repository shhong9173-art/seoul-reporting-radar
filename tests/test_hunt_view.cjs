const assert=require('node:assert/strict');
const fs=require('node:fs');
const page=fs.readFileSync('hunt.html','utf8');
const scripts=[...page.matchAll(/<script>([\s\S]*?)<\/script>/g)];
assert.equal(scripts.length,1);
new Function(scripts[0][1]);
for(const s of ['digests/investigation_hunt_latest.json','단독 확정','deskChecks',
                'endMonthShift','newPlannedEnd','oldPlannedEnd','textContent','reporterStatus']){
  assert(page.includes(s),'missing evidence marker: '+s);
}
assert(!page.includes('innerHTML'),'external source must not inject HTML');
assert(fs.readFileSync('index.html','utf8').includes('hunt.html'));
console.log('Senior-style source-delta hunt UI safety passed');
