const assert=require('node:assert/strict');
const fs=require('node:fs');
const html=fs.readFileSync('patents.html','utf8');
const scripts=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(x=>x[1]);
assert.equal(scripts.length,7);
for(const script of scripts)new Function(script);
for(const token of ['digests/patent_desk_latest.json','patent-desk-status','patent-desk-cards','patent-source-errors','digests/patent_source_status_latest.json','digests/patent_run_health_latest.json','patent-health-status','patent-quality-status','digests/patent_quality_latest.json','record-patent-editorial-review.yml','patent-story-expand','patent-story-extra','digests/patent_story_latest.json','patent-story-status','outsideBeatCoApplicants','기보도 검색','digests/patent_hunt_latest.json','KIPRIS_SERVICE_KEY',
     'publicationNumber','applicationDate','publicationDate','단독 확정','textContent','companyChecks']){
  assert(html.includes(token),'missing KIPRIS audit label '+token);
}
assert(!html.includes('innerHTML'),'official patent fields must not be injected as HTML');
assert((fs.readFileSync('index.html','utf8')+fs.readFileSync('pages.html','utf8')).includes('patents.html'));  // 홈 메뉴 또는 모든 페이지 목록
console.log('KIPRIS official patent reader UI passes');
