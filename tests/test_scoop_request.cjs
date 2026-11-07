const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const {build,matches}=require("../scoop_request.js");
const {reviewUrl}=require("../scoop_request.js");
assert(reviewUrl("https://news.google.com/rss/articles/abc?oc=5","press"));
assert(reviewUrl("https://github.com/shhong9173-art/seoul-reporting-radar/actions/runs/40225704947","run"));
assert.equal(reviewUrl("https://github.com/other/repo/actions/runs/1","run"),null);
assert.equal(reviewUrl("https://news.google.com.attacker.com/rss/articles/a","press"),null);
assert.equal(reviewUrl("javascript:alert(1)","press"),null);
assert.equal(reviewUrl("https://user:secret@news.google.com/rss/articles/a","press"),null);
const report={
 status:"primary_original_reporter_dossiers_not_exclusive",
 generatedAt:"2026-10-21T22:44:02+09:00",
 cases:[
 {id:"supernal",company:"슈퍼널·현대차그룹",title:"슈퍼널 모하비 두 차례 자산 경매",
  sourceDate:"2026-10-14",editorialPriority:1,angle:"두 번 경매 사실 검증, 폐쇄는 미확인",
  originalDocumentsVerified:2,originalDocumentsExpected:2,
  exclusiveConfirmed:false,noPriorPressProved:false,publisherFulltextCompared:false,
  factsFromMatchedPrimaryPages:[
    {text:"9월 경매 공식 공고",sourceUrl:"https://svdisposition.com/auction-detail/884",attribution:"경매업체"},
    {text:"10월 경매 공식 공고",sourceUrl:"https://svdisposition.com/auction-detail/891",attribution:"경매업체"}],
  possiblePriorPressTitles:[],priorPressIndexStatus:"partial_index_not_fulltext_checked",
  questionsForPublicConfirmation:[{recipient:"경매업체",text:"두 차례 실제 처분량 공개자료가 있습니까?"}],
  unresolved:["운영 중인 회사를 철수로 단정하지 않음"]},
 {id:"ipgate",company:"현대차·현대모비스",title:"현대차 독일 제동특허 소송",
  sourceDate:"2026-10-19",editorialPriority:2,angle:"원고 주장은 법원 판결 아님",
  originalDocumentsVerified:1,originalDocumentsExpected:1,
  exclusiveConfirmed:false,noPriorPressProved:false,publisherFulltextCompared:false,
  factsFromMatchedPrimaryPages:[
    {text:"EP 3 145 771 B1 관련 발표",sourceUrl:"https://www.ipgate.ch/blog/hyundai-legal-action",attribution:"IPGATE 원고 주장"}],
  possiblePriorPressTitles:[],priorPressIndexStatus:"partial_index_not_fulltext_checked",
  questionsForPublicConfirmation:[{recipient:"원고",text:"공개 소장 및 사건번호가 있습니까?"}],
  unresolved:["대상 차종 확인 전"]},
 {id:"ses-old",company:"현대차·SES AI",title:"현대차 B샘플 후속 개발",
  sourceDate:"2026-03-04",editorialPriority:4,angle:"후속 협력 여부 미확인",
  originalDocumentsVerified:1,originalDocumentsExpected:2,
  exclusiveConfirmed:false,noPriorPressProved:false,publisherFulltextCompared:false,
  factsFromMatchedPrimaryPages:[
    {text:"2026년 3월 주주서한의 개발 완료",sourceUrl:"https://www.sec.gov/Archives/edgar/data/1819142/filing.htm",attribution:"SEC 공개"}],
  possiblePriorPressTitles:[],priorPressIndexStatus:"partial_index_not_fulltext_checked",
  questionsForPublicConfirmation:[{recipient:"SES IR",text:"후속 계약 공시가 있습니까?"}],
  unresolved:["개발 종료는 협력 결렬과 다름"]}
 ]};
const discovery={
 status:"official_listing_links_observed_not_verified_scoops",
 generatedAt:"2026-10-21T22:44:02+09:00",
 candidates:[{
 url:"https://svdisposition.com/auction-detail/884",
 title:"Supernal equipment earlier auction",
 companiesMentionedInListingAndOriginal:["Supernal"],
 originalPageRead:true,confirmedExclusive:false,
 eventFieldsQuotedFromOriginal:[{field:"announced_auction_dates",verbatimValue:"Sep 21–23, 2026",
  originalQuote:"Auction Dates Sep 21–23, 2026",notIndependentlyVerified:true}],
 publicConfirmationQuestions:["경매 공고 원문의 기간 확인 가능한가?"]
 },{
 url:"https://svdisposition.com/auction-detail/891",
 title:"Supernal repeated equipment auction",
 companiesMentionedInListingAndOriginal:["Supernal"],
 originalPageRead:true,confirmedExclusive:false,
 eventFieldsQuotedFromOriginal:[{field:"announced_auction_dates",verbatimValue:"Oct 12–14, 2026",
  originalQuote:"Auction Dates Oct 12–14, 2026",notIndependentlyVerified:true}],
 publicConfirmationQuestions:["모하비 공개 사용허가 변경은 확인되는가?"]
 }]};
const nhtsa={
 status:"us_official_part573_pdf_passages_not_korean_recall_conclusion",
 generatedAt:"2026-10-21T22:40:03+09:00",
 reports:[
 {campaign:"26V588000",status:"nhtsa_original_part573_pdf_passages_for_review",
 officialPdfDownloaded:true,campaignNumberFoundInPdf:true,
 officialPdfUrl:"https://static.nhtsa.gov/odi/rcl/2026/RCLRPT-26V588-0403.pdf",
 sourcePassages:[{page:1,section:"defect",literalPdfExcerpt:"A second row seat condition that may fail to detect a person in the path of folding."}]},
 {campaign:"26V588000",status:"nhtsa_original_part573_pdf_passages_for_review",
 officialPdfDownloaded:true,campaignNumberFoundInPdf:true,
 officialPdfUrl:"https://static.nhtsa.gov/odi/rcl/2026/RCLRPT-26V588-0402.pdf",
 sourcePassages:[{page:1,section:"defect",literalPdfExcerpt:"The same earlier filed campaign for the second row seat motor folding concerns."}]},
 {campaign:"26V664000",status:"nhtsa_original_part573_pdf_passages_for_review",
 officialPdfDownloaded:true,campaignNumberFoundInPdf:true,
 officialPdfUrl:"https://static.nhtsa.gov/odi/rcl/2026/RCLRPT-26V664-0000.pdf",
 sourcePassages:[{page:1,section:"defect",literalPdfExcerpt:"Genesis power seat adjuster switch may stick leading to potential thermal damage."}]}
 ]};
const queue={status:"reporter_evidence_queue_not_exclusive",generatedAt:"2026-10-21T22:44:12+09:00",
 items:[{id:"DART:123",tier:"new_official_receipt_review",company:"LS일렉트릭",
 title:"2027년 북미 데이터센터 전력설비 프로젝트",officialDocumentDate:"2026-10-21",
 officialUrls:["https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261021800151"],
 exclusiveConfirmed:false,approvedForPitch:false,
 evidenceSummary:"최신 공시 접수 확인, 원문 세부내용 미확인",
 nextChecks:["공식 원문 계약 상대를 확인","동일 논점 선행보도 확인"]},
 {id:"DART:456",tier:"new_official_receipt_review",company:"현대차",
 title:"미확인 신문 보도 제목만",officialDocumentDate:"2026-10-21",
 officialUrls:[],exclusiveConfirmed:false,approvedForPitch:false}]};
const sources={dossiers:report,discovery,nhtsa,queue};
const now=new Date("2026-10-21T14:00:00Z");
const result=build(sources,{company:"현대차",now,limit:5});
assert.equal(result.totalCandidates,5,"3 source dossiers + 2 unique NHTSA campaigns");
assert.equal(result.rows.length,5);
assert.equal(result.confirmedScoops,0);
assert.equal(result.pressAbsenceProved,false);
assert.equal(result.rows.filter(x=>x.id.startsWith("case:supernal")).length,1);
assert.equal(result.rows.filter(x=>x.id.startsWith("nhtsa:26V588000")).length,1);
assert(result.rows[0].id.startsWith("case:"));
assert(result.rows[0].facts.some(x=>x.text.includes("Oct 12–14")));
const compare=result.rows.find(x=>x.id==="case:supernal").originalDocumentComparisons;
assert.equal(compare.length,1);
assert.equal(compare[0].field,"announced_auction_dates");
assert.deepEqual(compare[0].records.map(x=>x.value),
 ["Sep 21–23, 2026","Oct 12–14, 2026"]);
assert.equal(compare[0].actualCompanyOperationalChangeVerified,false);
assert.equal(compare[0].originalPublicationOrderVerified,false);
assert(result.rows.every(x=>x.businessImpactVerified===false));
assert(result.rows.every(x=>x.noPriorNewsProved===false));
assert(result.rows.every(x=>x.sameAngleFullTextReviewed===false));
assert(result.rows.every(x=>x.exclusivity==="단독 미확정"));
assert(result.rows.some(x=>x.reporterStage.includes("과거 원자료")));
const low=build({dossiers:{...report,cases:[report.cases[0]]}},
 {company:"현대차",limit:5,now});
assert.equal(low.rows.length,1);
assert(low.gap.includes("5건을 채우기 위해"));
const ls=build({queue}, {company:"LS일렉트릭",limit:5,now});
assert.equal(ls.rows.length,1);
assert.equal(ls.rows[0].sourceGroup,"국내 DART 공식 접수");
assert(ls.rows[0].reporterStage.includes("본문"));
assert.equal(build(sources,{company:"포스코",now}).rows.length,0);
assert(matches("현대차","Supernal"));
assert(!matches("현대차","현대제철"));
const page=fs.readFileSync("scoop-request.html","utf8");
const failedCase={...report.cases[0],factsFromMatchedPrimaryPages:[],
 originalDocuments:[{url:"https://svdisposition.com/auction-detail/884",status:"source_unavailable",
  comparisonStatus:"current_fetch_failed",checkedAt:"2026-10-21T22:44:02+09:00"}],
 pressRecheck:{status:"search_failed",items:[]}};
const failedPreview=build({dossiers:{...report,cases:[failedCase]}},{company:"현대차",now});
assert.equal(failedPreview.rows.length,0,"failed originals must not create candidates");
assert.equal(failedPreview.rechecks.length,1,"failure must remain visible outside candidate list");
assert.equal(failedPreview.rechecks[0].press.status,"search_failed");
assert(page.includes("text_changed_requires_review"));
assert(page.includes("정상 RSS 응답에서 유효 제목 미확보 · 미보도 증거 아님"));
const script=page.match(/<script>\s*([\s\S]*?)<\/script>/);
assert(script,"inline UI script not found");
new vm.Script(script[1]);
assert(page.includes("scoop_request.js"));
assert(page.includes("단독거리 5건 찾아줘"));
assert(page.includes("기존 등록 조사 사례 · 새 단독 발견 아님"));
assert(page.includes("공식 문서 사이의 표기 변화"));
assert(!page.includes("innerHTML"),"No source text may be injected as raw HTML");
assert(page.includes("textContent"));
assert(page.includes('addReviewLink(line,item.url,"보도 검색 결과 열기 ↗","press")'));
assert(page.includes('addReviewLink(box,check.workflowRunUrl,"이 재조회 실행 기록 ↗","run")'));
assert(page.includes("noopener noreferrer"));
const home=fs.readFileSync("index.html","utf8");
assert(home.includes("scoop-request.html"));
console.log("PASS on-demand source dossier 5-case merge, gap, recent DART, no fake scoops and safe UI");
