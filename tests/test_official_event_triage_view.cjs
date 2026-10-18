const assert=require("node:assert/strict");
const fs=require("node:fs");
const html=fs.readFileSync("official-today.html","utf8");
const scripts=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
assert.equal(scripts.length,1);
new Function(scripts[0][1]);
for(const phrase of [
 "digests/official_event_triage_latest.json",
 "officialDate","officialFact","firstRunBaseline","firstObservedThisRun",
 "freshOfficialReview","backgroundReference","incompleteOrStaleFeeds",
 "snapshot_older_than_24h","partial_collection","feedHealth",
 "exclusiveConfirmed!==false","approvedForPitch!==false",
 "companyImpactVerified!==false","기보도","원문 공개일",
 "미보도 증명 아님","기존 관측 자료","오래됐으면",
 "DART_FILING","FOREIGN_NOTICE",
 "originalEvidenceStage","official_valueup_text_only_attachment_unverified",
 "official_table_filing_fields_checked","official_receipt_only_original_not_checked",
 "partial_issuer_coverage","unresolvedCompanies","sourceSnapshotAt"
]){
 assert(html.includes(phrase),"Missing event-date and source-proof review token: "+phrase);
}
assert(!html.includes("innerHTML"),"Untrusted source must not be rendered via innerHTML");
assert(html.includes('href="official-leads.html"'),"Keep old research queue accessible");
console.log("PASS official event date review page: source gaps, no false novelty or exclusivity");
