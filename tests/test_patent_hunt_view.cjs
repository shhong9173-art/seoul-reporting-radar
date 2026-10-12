const assert=require('node:assert/strict');
const fs=require('node:fs');
const html=fs.readFileSync('patents.html','utf8');
const scripts=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(x=>x[1]);
assert.equal(scripts.length,5);
for(const script of scripts)new Function(script);
for(const token of ['digests/patent_run_health_latest.json','patent-health-status','digests/patent_story_latest.json','patent-story-status','outsideBeatCoApplicants','기보도 검색','digests/patent_hunt_latest.json','KIPRIS_SERVICE_KEY',
     'publicationNumber','applicationDate','publicationDate','단독 확정','textContent','companyChecks']){
  assert(html.includes(token),'missing KIPRIS audit label '+token);
}
assert(!html.includes('innerHTML'),'official patent fields must not be injected as HTML');
assert(fs.readFileSync('index.html','utf8').includes('patents.html'));
console.log('KIPRIS official patent reader UI passes');
