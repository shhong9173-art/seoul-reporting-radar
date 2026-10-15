const fs=require('node:fs');
const assert=require('node:assert/strict');
const html=fs.readFileSync('dart-beat-monitor.html','utf8');
const scripts=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
assert.equal(scripts.length,1);
new Function(scripts[0][1]);
for(const token of [
 "digests/dart_beat_monitor_latest.json",
 "digests/dart_beat_run_health_latest.json",
 "latestDatasetGeneratedAt",
 "newCollectionVerified",
 "registryRefreshVerified",
 "수집 또는 게시 실패",
 "digests/dart_beat_changes_latest.json",
 "two_official_documents_changed_terms",
 "issuer_stated_correction_only",
 "same_receipt_data_reparse_discrepancy",
 "same_receipt_first_document_field_recovery",
 "reportedOfficialTableTerms",
 "reportedCounterpartyIsAffiliate",
 "ultimateExternalCustomerVerified",
 "actualShipmentVerified",
 "공시상 계약금액",
 "외부 최종 고객",
 "검토 대기 원문",
 "companiesCodeVerified","companiesUnresolved",
 "companiesWithSourceErrors","baselineOnly",
 "priorNewsFulltextChecked!==false",
 "businessImpactVerified!==false",
 "scoopConfirmed!==false",
 "newObservation===null",
 "원공시·정정문","공시 없음으로 판정 불가",
 "DART 공시 원문","동일 공시번호 재파싱"
])assert(html.includes(token),'Missing safety/coverage marker: '+token);
assert(!html.includes('innerHTML'),'Untrusted official titles must use safe DOM text');
console.log('PASS: industry beat dashboard keeps official news/contract/first observed claims separate');
