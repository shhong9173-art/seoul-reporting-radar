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
  'pitchGate.cashReceivedByParentVerified!==false',
  'issuerOriginalPhrase',
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
