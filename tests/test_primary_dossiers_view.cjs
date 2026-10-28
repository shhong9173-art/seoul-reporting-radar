const fs=require("node:fs");
const assert=require("node:assert/strict");
const html=fs.readFileSync("primary-dossiers.html","utf8");
const snippets=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
assert.equal(snippets.length,1);
new Function(snippets[0][1]);
const home=fs.readFileSync("index.html","utf8")+fs.readFileSync("pages.html","utf8");  // 홈 메뉴 또는 모든 페이지 목록
assert(home.includes('href="primary-dossiers.html"'));
for(const value of [
 "digests/primary_research_dossiers_latest.json",
 "registryIsManuallyCuratedNotAutomatedDiscovery",
 "allDomesticPressChecked!==false",
 "data.confirmedScoops!==0",
 "caseFile.factsFromMatchedPrimaryPages",
 "originalDocumentsVerified",
 "noPriorPressProved",
 "source_unavailable",
 "digests/primary_original_discovery_latest.json",
 "digests/primary_sec_filing_watch_latest.json",
 "sec-source-status",
 "sec.sourceCoverageExhaustive!==false",
 "sec.confirmedScoops!==0",
 "filing.originalDocumentBodyRead!==false",
 "sourceCoverageExhaustive!==false",
 "domesticNoPriorCoverageProved!==false",
 "observed.confirmedScoops!==0",
 "newlyObservedAfterCleanBaseline",
 "eventFieldsQuotedFromOriginal",
 "notIndependentlyVerified!==true",
 "publicConfirmationQuestions",
 "notRecheckedThisRun",
 "원문 일부:",
 "확인 가능한 취재 질문",
 "addLink(box,fact.sourceUrl",
])assert(html.includes(value),"Missing evidence-safe view gate: "+value);
assert(!html.includes("innerHTML"),"Remote text must never be raw HTML");
assert(html.includes("textContent"));
assert(html.includes("noopener noreferrer"));
console.log("PASS first-party evidence-safe dossier view and homepage navigation");
