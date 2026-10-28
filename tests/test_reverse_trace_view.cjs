const fs=require("node:fs");
const assert=require("node:assert/strict");
const page=fs.readFileSync("reverse-trace.html","utf8");
const scripts=[...page.matchAll(/<script>([\s\S]*?)<\/script>/g)];
assert.equal(scripts.length,1);
new Function(scripts[0][1]);
for(const tag of [
 "digests/reverse_trace_latest.json",
 "digests/press_coverage_index_latest.json",
 "digests/historical_exclusive_press_index_latest.json",
 "digests/recent_exclusive_recall_audit_latest.json",
 "recent-index-audit",
 "newsOnlyObserved",
 "historyOnlyObserved",
 "gap.historySourceAt!==historical.generatedAt",
 "단독기사 수집 경로 교차검사",
 "digests/reverse_trace_dart_followups_latest.json",
 "dart-receipt-research",
 "matches.reverseTraceSourceAt!==data.generatedAt",
 "matches.dartOfficialSourceAt!==beat.generatedAt",
 "DART 접수공시 원문 확인",
 "m.publicFactOverlapVerified!==false",
 "original-review-checklist",
 "공식 원자료 후보 발견 · 보도 전 공개 여부 미확인",
 "data.locatedOriginalCandidateArticleCount",
 "recent-exclusive-status",
 "recent-exclusives",
 "recentBeatQueriesSucceeded",
 "recentSearchCoverageExhaustive",
 "recent.length",
 "최근 72시간 관측",
 "원본 기사 전문",
 "data.availableObservedExclusiveHeadlinesBeforeCap",
 "data.evidencePriorityObservedItemsRetained",
 "표시 한도 전 관측된 기사",
 "data.primaryDocumentPublishedBeforeMediaVerifiedCount!==0",
 "source.documentAndStoryFactsCompared!==false",
 "발행사 공식 원자료 열기",
 "연결된 SEC 해외 공시(기사)",
 "sec.secAcceptedAtOfficialEastern",
 "공식 SEC 원문 열기",
 "미국 SEC 8-K",
 "firstPublicAvailabilityClockVerified!==false",
 "원자료 검색 출발점(원문 존재 미확인)",
 "data.historicalSearchIndexAt!==historical.generatedAt",
 "row.historicalSearchHeadlineOnly",
 "전문·원본 미확인",
 "reliablePopulationReachEstimated!==false",
 "humanReviewedYPN!==data.Y+data.P+data.N",
 "U · 아직 미검증",
 "source timestamp",
 "confirmedExclusive!==false",
 "기사 전문·보도 전 원자료 교차검증 미완료",
 "replaceChildren()",
 "textContent",
]){
 assert(page.includes(tag),"Missing Y/P/N safety display marker: "+tag);
}
assert(!page.includes("innerHTML"),"Untrusted press headlines must be rendered only with textContent");
const index=fs.readFileSync("index.html","utf8")+fs.readFileSync("pages.html","utf8");  // 홈 메뉴 또는 모든 페이지 목록
assert(index.includes('href="reverse-trace.html"'));
console.log("PASS reverse trace source, verified label gating, and safe DOM view");
