const fs=require("node:fs");
const assert=require("node:assert/strict");
const html=fs.readFileSync("reporting-queue.html","utf8");
assert.ok(html.includes("digests/reporting_evidence_queue_latest.json"));
for(const name of [
 "new_official_receipt_review","new_official_list_heading_review",
 "recentOfficialTitleOnlyCount","officialListTitleOnly",
 "officialDocumentBodyReviewed","disclosedFinancialImpactVerified",
 "crossYearPlanReview","canClaimTwentyPercentagePointIncrease",
 "officialOriginalTextRetrieved","officialOriginalTargetTextExcerpts",
 "originalSourceUnavailableNotZeroTargets",
 "DART 공식 원본문서 XML 접근 불가",
 "officialAttachmentPdfReviewed",
 "denominatorMatched","periodDefinitionMatched",
 "2025년 KG스틸 공식 발표","2026년 이미 보도된 공시 소개",
 "공식 DART 목록 제목·접수일만 검증됨",
 "verified_historical_investment_delta",
 "verified_historical_numeric_delta","issuer_only_correction_unverified_original",
 "older_public_contract_reference","unlinked_correction_text_followup",
 "historicalResearchCount","unlinkedHistoryTextMatchCount",
 "correctionHistorySourceGate","contractLinkVerified",
 "textMatchIsNotContractContinuity","historicalNotNewIncident",
 "원공시 역추적","동일 계약·원계약 연결·실제 계약 효력 미확정",
 "officialDocumentDate",
 "원공시 미대조 정정","기보도 전문·사업 영향·단독성 미검증",
 "sourceCoverage","sourceHealth",
 "officialTableTermsRetrieved","inGroupCounterpartyPerIssuerFiling",
 "발행사 공시상 계약 상대가 계열사","신규 외부 고객·실제 납품은 미확정"
])assert.ok(html.includes(name),name);
assert.ok(html.includes('data.confirmedScoops!==0'));
assert.ok(html.includes("x.approvedForPitch!==false"));
assert.ok(html.includes("x.pressFulltextReviewed!==false"));
assert.ok(html.includes("x.officialDateIsSourcePublicationNotScrape!==true"));
assert.match(html,/<option value="recent" selected>/);
assert.ok(html.includes('tier==="recent"'));
assert.ok(html.includes('x.officialListTitleOnly===true'));
assert.ok(html.includes('value="new_official_list_heading_review"'));
assert.ok(html.includes('value="all">전체 과거 자료 · 직접 선택'));
assert.ok(!html.includes("innerHTML"));
const scripts=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
assert.equal(scripts.length,1);
new Function(scripts[0][1]);
console.log("PASS evidence-tier newsroom source, date, editorial status, safe DOM rendering");
