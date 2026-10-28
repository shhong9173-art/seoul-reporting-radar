const assert=require('node:assert/strict');
const fs=require('node:fs');
const page=fs.readFileSync('hunt.html','utf8');
const scripts=[...page.matchAll(/<script>([\s\S]*?)<\/script>/g)];
assert.equal(scripts.length,2);
for(const x of scripts)new Function(x[1]);
for(const s of ['digests/investigation_hunt_latest.json','단독 확정','deskChecks',
                'endMonthShift','newPlannedEnd','oldPlannedEnd','textContent','reporterStatus']){
  assert(page.includes(s),'missing evidence marker: '+s);
}
assert(page.includes('digests/recent_metric_changes_latest.json'));
assert(page.includes('동일 행/단위'));
assert(!page.includes('innerHTML'),'external source must not inject HTML');
assert((fs.readFileSync('index.html','utf8')+fs.readFileSync('pages.html','utf8')).includes('hunt.html'));  // 홈 메뉴 또는 모든 페이지 목록
console.log('Senior-style source-delta hunt UI safety passed');
