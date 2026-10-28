const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const code=fs.readFileSync("pitch-format.js","utf8");
const context={module:{exports:{}},Intl,Date};
vm.runInNewContext(code,context,{timeout:1000,filename:"pitch-format.js"});
const f=context.module.exports;
const page=fs.readFileSync("patent-pitches.html","utf8");
const home=fs.readFileSync("index.html","utf8")+fs.readFileSync("pages.html","utf8");  // 홈 메뉴 또는 모든 페이지 목록
const patents=fs.readFileSync("patents.html","utf8");
assert(page.includes('src="pitch-format.js"'));
assert(home.includes('href="patent-pitches.html"'));
assert(patents.includes('href="patent-pitches.html"'));
assert(!page.includes("innerHTML"));
for(const token of ["patent_reporting_triage_latest.json","triage-status",
 "count-human","count-hit","record-patent-editorial-review.yml",
 "source_review_company_call","측정 불가","finalHumanSample","editorialOutcome",
 "result.deskSourceGeneratedAt===desk.generatedAt",
 "result.crossSourceGeneratedAt===cross.generatedAt"])
 assert(page.includes(token),"missing reporter feedback ranking marker "+token);
for(const term of ["patent_cross_evidence_latest.json","cross-status",
  "record-patent-public-factcheck.yml","localStorage.getItem","localStorage.setItem",
  "공식 DART 교차검증","기자 취재 체크","실제 출고·단독 자동 확정 아님"])
  assert(page.includes(term),"missing DART reporter checklist control "+term);
assert(page.includes("최신 자동실행 실패 · 이전 검증 자료 표시"),"stale official evidence must remain viewable but clearly dated");
assert(code.includes("companyResponsesVerified"),"source guard belongs to pitch-format.js");
assert.equal([...page.matchAll(/<script>/g)].length,1);
for(const match of page.matchAll(/<script>([\s\S]*?)<\/script>/g))new Function(match[1]);
for(const token of ["btn-copy-all","btn-refresh-time","pitch-cards","pitch-status","navigator.clipboard","aria-label",
 "patent_run_health_latest.json","publicationReady","수정"])assert(page.includes(token),token);
const known=[
 {publicationNumber:"1020260145290",publicationDate:"20261007",title:"케이블 부착식 부분방전 센서 및 이를 포함하는 부분방전 검출 시스템",coveredCompanies:["LS전선"],outsideBeatCoApplicants:["한빛이디에스(주)"],sourceAbstractExcerpt:"배전 환경에 노이즈가 많아도 검출할 수 있고 케이블 탈부착이 용이한 구조",mediaReview:{state:"index_no_hits_not_proof"},olderSameTitle:{state:"searched_same_title_only"}},
 {publicationNumber:"1020260145560",publicationDate:"20261007",title:"상변태 기반 판재 냉각 제어 장치 및 방법",coveredCompanies:["현대제철"],outsideBeatCoApplicants:["서울대학교산학협력단"],sourceAbstractExcerpt:"판재 조직정보와 온도정보를 측정하고 냉각수 공급량을 제어",mediaReview:{state:"index_no_hits_not_proof"},olderSameTitle:{state:"searched_same_title_only"}},
 {publicationNumber:"1020260143786",publicationDate:"20261002",title:"압력용기의 내외부 표면 침투탐상 검사장치 및 이를 이용한 압력용기의 내외부 표면 침투탐상 검사방법",coveredCompanies:["두산에너빌리티"],outsideBeatCoApplicants:["나우 주식회사"],sourceAbstractExcerpt:"대형 압력용기의 내부와 외부에 침투탐상검사를 수행",mediaReview:{state:"index_no_hits_not_proof"},olderSameTitle:{state:"searched_same_title_only"}},
 {publicationNumber:"1020260147965",publicationDate:"20261012",title:"도어 및 이를 갖춘 차량",coveredCompanies:["현대자동차","기아"],outsideBeatCoApplicants:["주식회사 광진"],sourceAbstractExcerpt:"휠체어 승하차를 보조하는 램프 장치와 차량 도어",mediaReview:{state:"index_no_hits_not_proof"},olderSameTitle:{state:"not_checked"}},
 {publicationNumber:"1020260148086",publicationDate:"20261012",title:"고정자 냉각 장치",coveredCompanies:["현대자동차","기아"],outsideBeatCoApplicants:["중앙대학교 산학협력단"],sourceAbstractExcerpt:"고정자 플레이트 및 냉각 유로가 구비",mediaReview:{state:"not_checked"},olderSameTitle:{state:"not_checked"}}
];
for(const row of known){
 const result=f.format(row,"11:33");
 assert(result.startsWith("*"),result);
 assert(result.endsWith("추가 취재 필요"),result);
 assert(result.includes("(홍성효, 11:33)"));
 assert.equal(result.split("\n").length,4,result);
 assert.equal(result.split("\n").slice(1).filter(x=>x.startsWith("- ")).length,3,result);
 assert(result.includes(row.publicationNumber));
 assert(!result.includes("양산 확정"));
 assert(!result.includes("단독 확인"));
}
assert(f.title(known[0]).startsWith("LS전선·한빛이디에스"));
assert(f.points(known[0])[0].includes("한빛이디에스가 공동출원인"));
assert(f.points(known[2])[0].includes("나우가 공동출원인"));
assert(f.title(known[1]).includes("현대제철·서울대"));
assert(f.title(known[1]).includes("판재 냉각"));
assert(f.title(known[2]).includes("압력용기"));
assert(f.title(known[3]).includes("휠체어"));
assert(f.title(known[4]).includes("중앙대"));
assert(f.title(known[4]).includes("고정자"));
const kst=f.kstTime(new Date("2026-10-13T02:33:00.000Z"));
assert.equal(kst,"11:33");
const snap={status:"research_priorities_only",generatedAt:"2026-10-13T11:00:00+09:00",
storySourceGeneratedAt:"2026-10-13T10:58:00+09:00",shortlist:known};
assert.equal(f.validDataset(snap),true);
assert.equal(f.validDataset({...snap,shortlist:[{...known[0],scoopConfirmed:true}]}),false);
assert.equal(f.validDataset({...snap,shortlist:known.concat(known[0])}),false);
assert.equal(f.validDataset({...snap,status:"unknown"}),false);
const alone={...known[0],coveredCompanies:["LS전선"],outsideBeatCoApplicants:[]};
assert(f.title(alone).includes("특허 공개"));
console.log("Patent newsroom pitch view: 5 example reports, 3 bullets, KST clock, sourcing, UI syntax and source guard PASS");
