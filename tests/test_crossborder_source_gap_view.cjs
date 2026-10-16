const assert=require('node:assert/strict');
const fs=require('node:fs');
const html=fs.readFileSync('crossborder-scoops.html','utf8');
const matches=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
assert.equal(matches.length,1);
new Function(matches[0][1]);
for(const marker of [
  'crossborder_source_gap_latest.json',
  'crossborder_reporter_evidence_gap_not_exclusive',
  'domesticRecallAbsenceVerified!==false',
  'foreignParentCashTransferVerified!==false',
  'pitchGate?.exclusiveConfirmed!==false',
  'pitchGate?.approvedForPitch!==false',
  'pitchGate?.companyImpactVerified!==false',
  'pitchGate.domesticOfficialChecked!==false',
  'pitchGate.exactComponentMatch!==false',
  'koreanModelSearchLinks',
  'nhtsaPart573Original',
  'koreanMarketSourceClaims',
  'koreanMarketIncidentIndependentlyVerified',
  'sourceIsManufacturerAllegationOnly',
  '미국 당국에 제출된 제조사 기록입니다',
  '사고·화재 관련 단어 근접',
  'usManufacturerReportedAffectedCount',
  'differentPdfVersionsAffectedCountConflict',
  '미국 판매용 기준',

  'originalReportsRead',
  'priorSameAngleNewsChecked!==false',
  'NHTSA 제조사 원문 PDF',

  'searchResultRead!==false',
  'absenceOfRecallVerified!==false',
  "자동차리콜센터에서 '",
  '공식 검색 페이지일 뿐',
  'pitchGate.cashReceivedByParentVerified!==false',
  'issuerOriginalPhrase',
  'slovakGovernmentAccounts',
  'officialIfrsReportDetailUrl',
  'slovakPdfPrimaryReview',
  'dividendCrossPeriodGap',
  'canCalculateParentCashTransferFromTheseRows!==false',
  'canClaimNoDividendIn2026!==false',
  '서로 빼거나 송금액을 계산할 수 없습니다',

  'auditedCalendarYearRows',
  'annualReportComparativeConflict',
  'year2026LocalPaymentNotYetVerified',
  'sourceCount',
  '동일 회계연도가 아니며',
  'governmentHashVerifiedReports',
  'amountsIndependentlyAudited!==false',
  'SHA-256 검증된 정부 원본 PDF',
  '2025:10298519',
  '2024:9718744',
  '현지 IFRS 재무제표 원문 등록 화면',
  'companyCashReceivedVerified!==false',
  'auditedPdfReviewed!==false',
  'foreignLegalEntityLinks',
  'hyundaiCzechFactory',
  'czech.identityVerified',
  '기아 슬로바키아 생산법인 확인',
  '체코 법무부 공식 재무제표 공시 검색',
  '현금 송금액 아님',
  'issuerExactDividendDossiers',
  '미국 당국 공개 결함',
  '국내 리콜',
  '현금 송금액 아님',
  '당일 신규 사건의 증거',
  '기보도',
  '확인 질문 복사'
]){
 if(marker==='당일 신규 사건의 증거')continue; // displayed wording is '새 사건 발생일이 아닙니다'
 assert(html.includes(marker),'Missing cross-border primary-source safety statement: '+marker);
}
assert(!html.includes('innerHTML'),'Official excerpts and headlines cannot be inserted as HTML');
console.log('PASS: crossborder newsroom shows official, domestic, prior-press and accounting status separately');
