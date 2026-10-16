const fs=require("node:fs");
const assert=require("node:assert/strict");
const html=fs.readFileSync("reporting-queue.html","utf8");
assert.ok(html.includes("digests/reporting_evidence_queue_latest.json"));
for(const name of [
 "new_official_receipt_review","verified_historical_investment_delta",
 "verified_historical_numeric_delta","issuer_only_correction_unverified_original",
 "older_public_contract_reference","officialDocumentDate",
 "원공시 미대조 정정","기보도 전문·사업 영향·단독성 미검증",
 "sourceCoverage","sourceHealth"
])assert.ok(html.includes(name),name);
assert.ok(html.includes('data.confirmedScoops!==0'));
assert.ok(html.includes("x.approvedForPitch!==false"));
assert.ok(html.includes("x.pressFulltextReviewed!==false"));
assert.ok(html.includes("x.officialDateIsSourcePublicationNotScrape!==true"));
assert.ok(!html.includes("innerHTML"));
const scripts=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
assert.equal(scripts.length,1);
new Function(scripts[0][1]);
console.log("PASS evidence-tier newsroom source, date, editorial status, safe DOM rendering");
