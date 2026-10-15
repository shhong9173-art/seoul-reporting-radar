const fs=require("node:fs");
const assert=require("node:assert/strict");
const html=fs.readFileSync("dart-correction-history.html","utf8");
const scripts=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
assert.equal(scripts.length,1);
new Function(scripts[0][1]);
for(const marker of [
  "digests/dart_correction_history_latest.json",
  "UNLINKED_same_company_category_reference_date",
  "sameContractVerified!==false",
  "sameRevisionVerified!==false",
  "articleFulltextRead",
  "revisionFirstReportedAfterPreviousCoverageVerified",
  "confirmedScoops!==0",
  "approvedArticles!==0",
  "기보도","같은 계약","원공시","이전 언론","변경 없음",
  "24시간 이상","미보도·단독 증명 아님"
])assert(html.includes(marker),"Missing cautious prior amendment provenance marker: "+marker);
assert(!html.includes("innerHTML"),"official DART/news titles must use textContent");
console.log("PASS prior DART amended history view: unlinked candidate, media fulltext and no exclusive flags");
