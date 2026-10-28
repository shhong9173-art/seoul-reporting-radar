/* Query-driven official-source reporter shortlist, NOT an exclusive classifier.
 * Uses the existing published primary document, discovery, NHTSA and DART
 * sources. Does not manufacture five stories, legal outcomes or press absence.
 */
(function(root){
"use strict";
const ALIASES={
 "현대차":["현대차","현대자동차","현대차그룹","슈퍼널","supernal","hyundai","제네시스","genesis","블루링크","bluelink","현대모비스","mobis","현대캐피탈","hyundai capital","hma"],
 "기아":["기아","kia","kask","kia slovakia"],
 "포스코":["포스코","posco"],
 "현대제철":["현대제철","hyundai steel"],
 "hd현대일렉트릭":["hd현대일렉트릭","hd hyundai electric"],
 "ls일렉트릭":["ls일렉트릭","엘에스일렉트릭","ls electric"],
 "대한전선":["대한전선","taihan"],
 "고려아연":["고려아연","korea zinc"],
 "두산에너빌리티":["두산에너빌리티","doosan enerbility"]
};
const norm=t=>String(t||"").toLocaleLowerCase().replace(/[\s·()[\]_-]+/g,"");
function identifiers(term){
 const key=norm(term);
 if(!key||key.length<2)return [];
 const entry=Object.entries(ALIASES).find(([k,a])=>norm(k)===key||a.some(z=>norm(z)===key));
 return entry?[...new Set(entry[1].map(norm))]:[key];
}
function matches(term,...values){
 const terms=identifiers(term);
 return terms.length>0&&values.some(value=>{
   const hay=norm(value);
   return terms.some(t=>t.length>1&&hay.includes(t));
 });
}
function validHttps(x){
 try{const u=new URL(x);return u.protocol==="https:"&&!u.username&&!u.password&&u.hostname.indexOf(".")>0} catch{return false}
}
function reviewUrl(value,kind){
 try{
  const u=new URL(value);
  if(u.protocol!=="https:"||u.username||u.password||u.port)return null;
  if(kind==="press"&&u.hostname==="news.google.com"&&/^\/(?:rss\/)?articles\/[^/]+$/.test(u.pathname))return u.href;
  if(kind==="run"&&u.hostname==="github.com"&&/^\/shhong9173-art\/seoul-reporting-radar\/actions\/runs\/\d+$/.test(u.pathname))return u.href;
 }catch{}
 return null;
}
function dateMs(text){
 if(typeof text!=="string")return null;
 const d=Date.parse(text.length===8&&/^\d{8}$/.test(text)?
    text.slice(0,4)+"-"+text.slice(4,6)+"-"+text.slice(6):text);
 return Number.isFinite(d)?d:null;
}
function ageDays(d,now){
 const t=dateMs(d);return t===null?null:Math.floor((now-t)/86400000);
}
function safeLine(x,len=260){
 return String(x||"").replace(/\s+/g," ").trim().slice(0,len);
}
function factsFromCase(c){
 return (c.factsFromMatchedPrimaryPages||[]).filter(f=>typeof f.text==="string"&&validHttps(f.sourceUrl))
 .slice(0,5).map(f=>({
  text:safeLine(f.text),sourceUrl:f.sourceUrl,
  scope:safeLine(f.attribution,140),basis:"matched_original_page"
 }));
}
function questions(items){
 return (Array.isArray(items)?items:[]).slice(0,3).map(q=>{
  const t=typeof q==="string"?q:(q.recipient+" — "+q.text);
  return safeLine(t,260);
 }).filter(t=>t.endsWith("?"));
}
function statuses(item,now){
 const days=ageDays(item.officialDate,now);
 if(!item.facts.length)return "원문 내용 확인 전";
 if(item.evidenceType==="registered_original"){
   if(item.originalDocumentsVerified===item.originalDocumentsExpected&&days!==null&&days<=21&&days>=0)
     return "공식 원문 확보·추가 취재 우선";
   if(days!==null&&days>45)return "과거 원자료·현재 변화 재검증";
   return "공식 원문 일부 확인·핵심 추가 검증";
 }
 if(item.evidenceType==="nhtsa_part573")return "미국 원문 확인·국내 동일 부품 미검증";
 if(item.evidenceType==="dart_receipt")return "당일 접수·본문 및 기보도 대조 전";
 return "공식 목록 관측·문서 사실 확인 전";
}
function stageRank(s){
 if(s==="공식 원문 확보·추가 취재 우선")return 0;
 if(s==="미국 원문 확인·국내 동일 부품 미검증")return 1;
 if(s==="공식 원문 일부 확인·핵심 추가 검증")return 2;
 if(s==="당일 접수·본문 및 기보도 대조 전")return 3;
 if(s==="과거 원자료·현재 변화 재검증")return 4;
 return 5;
}
function documentIdentity(value){
 if(!validHttps(value))return null;
 const u=new URL(value);
 // A home page is not a document. Keep all document-identifying query values.
 if(u.pathname==="/"&&!u.search)return null;
 u.hash="";
 for(const key of [...u.searchParams.keys()])
  if(/^utm_/i.test(key))u.searchParams.delete(key);
 u.searchParams.sort();
 return u.href;
}
function researchGroups(rows){
 const documents=new Map();
 for(const row of rows){
  for(const url of new Set((row.officialUrls||[]).map(documentIdentity).filter(Boolean))){
   if(!documents.has(url))documents.set(url,[]);
   const members=documents.get(url);
   if(!members.some(m=>m.id===row.id))members.push(row);
  }
 }
 return [...documents.entries()].filter(([,members])=>members.length>1).map(([url,members])=>({
  documentUrl:url,memberIds:members.map(r=>r.id),
  titles:members.map(r=>r.title),
  relationship:"동일 원문 URL에서 나온 단서 · 동일 사건·사업장 관계는 별도 확인",
  confirmedExclusive:false
 }));
}
function build(sources,{company="현대차",limit=5,now=new Date()}={}){
 if(!(now instanceof Date)||!Number.isFinite(+now))throw Error("유효한 현재시각 필요");
 limit=Math.max(1,Math.min(8,Number(limit)||5));
 const meta={company,sourceHealth:[],totalCandidates:0,notFullPressCoverage:true,
   pressAbsenceProved:false,confirmedScoops:0,gap:"",generatedAt:now.toISOString()};
 const rows=[],byUrl=new Map();
 meta.rechecks=[];
 function healthy(src,expected){
  const value=sources&&sources[src];
  if(!value||value.status!==expected){
   meta.sourceHealth.push({source:src,status:"unavailable_or_wrong_schema"});
   return null;
  }
  const at=dateMs(value.generatedAt);
  meta.sourceHealth.push({source:src,generatedAt:value.generatedAt||null,
   status:at!==null&&(+now-at)>=0&&(+now-at)<=3*86400000?"observed_recently":"stale_or_unknown_timestamp"});
  return value;
 }
 const dossiers=healthy("dossiers","primary_original_reporter_dossiers_not_exclusive");
 const discovered=healthy("discovery","official_listing_links_observed_not_verified_scoops");
 const nhtsa=healthy("nhtsa","us_official_part573_pdf_passages_not_korean_recall_conclusion");
 const queue=healthy("queue","reporter_evidence_queue_not_exclusive");
 if(dossiers&&Array.isArray(dossiers.cases)){
  for(const c of dossiers.cases){
   if(!matches(company,c.company,c.title))continue;
   if(c.exclusiveConfirmed!==false||c.noPriorPressProved!==false||
      c.publisherFulltextCompared!==false)continue;
   // Keep failed originals visible even when their facts cannot enter a candidate.
   meta.rechecks.push({title:safeLine(c.title),runId:safeLine(dossiers.verificationRunId,80),
    workflowRunUrl:validHttps(dossiers.workflowRunUrl)?dossiers.workflowRunUrl:null,
    documents:(Array.isArray(c.originalDocuments)?c.originalDocuments:[]).filter(d=>validHttps(d.url)).map(d=>({
     url:d.url,status:safeLine(d.status),checkedAt:safeLine(d.checkedAt),
     comparisonStatus:safeLine(d.comparisonStatus)||"comparison_not_available",
     previousSuccessfulCheckAt:safeLine(d.previousSuccessfulCheckAt),errorType:safeLine(d.errorType)
    })),
    press:c.pressRecheck||{status:"not_queried",items:[]}});
   const facts=factsFromCase(c);
   if(!facts.length)continue;
   const officialUrls=[...new Set(facts.map(f=>f.sourceUrl))];
   const item={
    id:"case:"+c.id,sourceGroup:"해외 기업·법원·공시 원문",
    evidenceType:"registered_original",
    company:safeLine(c.company,90),title:safeLine(c.title,220),
    officialDate:c.sourceDate,dateBasis:"사전 등록된 원문 기준일(기계 확인 전)",
    facts,officialUrls,angle:safeLine(c.angle,400),
    questions:questions(c.questionsForPublicConfirmation),
    unresolved:(c.unresolved||[]).slice(0,3).map(x=>safeLine(x,360)),
    existingCoverage:c.priorPressIndexStatus==="partial_index_not_fulltext_checked"?
      "부분 언론 색인만 대조·동일 논점 선행보도 미확정":"선행보도 미검증",
    possiblePriorTitles:(c.possiblePriorPressTitles||[]).slice(0,2).map(x=>safeLine(x.title)),
    originalDocumentsVerified:c.originalDocumentsVerified||0,
    originalDocumentsExpected:c.originalDocumentsExpected||0,
    editorPriority:c.editorialPriority||9,
    registeredHistoricalCase:true,originalDocumentBodyRead:true
   };
   rows.push(item);officialUrls.forEach(u=>byUrl.set(u,item));
  }
 }
 if(discovered&&Array.isArray(discovered.candidates)){
  for(const c of discovered.candidates){
   if(c.confirmedExclusive!==false||c.originalPageRead!==true)continue;
   if(!matches(company,c.title,(c.companiesMentionedInListingAndOriginal||[]).join(" ")))continue;
   const url=c.url;if(!validHttps(url))continue;
   const quotations=(c.eventFieldsQuotedFromOriginal||[]).filter(f=>
      f.notIndependentlyVerified===true&&typeof f.originalQuote==="string"
      &&typeof f.verbatimValue==="string")
    .slice(0,5).map(f=>({text:f.field+": "+safeLine(f.verbatimValue,145),
      sourceUrl:url,scope:"공식 원문 발췌: "+safeLine(f.originalQuote,210),
      basis:"first_party_original_quote_not_independent"}));
   const earlier=byUrl.get(url);
   if(earlier){
    // Enrich an already registered event; do not show the same auction twice.
    if(!Array.isArray(earlier.originalFieldProvenance))earlier.originalFieldProvenance=[];
    for(const f of (c.eventFieldsQuotedFromOriginal||[])){
      if(f.notIndependentlyVerified!==true||typeof f.verbatimValue!=="string")continue;
      earlier.originalFieldProvenance.push({sourceUrl:url,
        field:safeLine(f.field,70),value:safeLine(f.verbatimValue,140)});
    }
    earlier.facts.push(...quotations);
    earlier.facts=earlier.facts.slice(0,9);
    if(c.notRecheckedThisRun)earlier.unresolved.push("이 공식 링크는 이번 수집에서 재확인되지 않음");
    continue;
   }
   if(!quotations.length)continue;
   rows.push({id:"discovered:"+url,evidenceType:"discovered_original",sourceGroup:"해외 신규 관측 원문",
     company:safeLine((c.companiesMentionedInListingAndOriginal||[]).join("·"),90),
     title:safeLine(c.title,230),officialDate:null,dateBasis:"공식 게시일 미검증·최초 관측일은 공개일 아님",
     facts:quotations,officialUrls:[url],
     angle:"원문 게시 내용과 사업·법률상의 변화는 구별해야 함",
     questions:questions(c.publicConfirmationQuestions),
     unresolved:["실제 공표일·후속 이행·동일 논점 국내 선행보도 확인 전"],
     existingCoverage:"언론사 전문 미대조",
     possiblePriorTitles:[],originalDocumentsVerified:1,originalDocumentsExpected:1,
     editorPriority:10,registeredHistoricalCase:false,originalDocumentBodyRead:true});
  }
 }
 if(nhtsa&&Array.isArray(nhtsa.reports)&&
    matches(company,"현대차","현대자동차","Hyundai","Genesis")){
  const grouped=new Map();
  for(const r of nhtsa.reports){
   if(r.status!=="nhtsa_original_part573_pdf_passages_for_review"||
      !r.officialPdfDownloaded||!r.campaignNumberFoundInPdf||!validHttps(r.officialPdfUrl))continue;
   const passages=(r.sourcePassages||[]).filter(x=>
      typeof x.literalPdfExcerpt==="string"&&x.literalPdfExcerpt.length>35);
   if(!passages.length)continue;
   if(!grouped.has(r.campaign))grouped.set(r.campaign,r);
   else if(passages.length>(grouped.get(r.campaign).sourcePassages||[]).length)
      grouped.set(r.campaign,r);
  }
  for(const [campaign,r] of grouped){
   const passages=(r.sourcePassages||[]).filter(x=>x.literalPdfExcerpt?.length>35)
    .slice(0,4);
   rows.push({id:"nhtsa:"+campaign,evidenceType:"nhtsa_part573",sourceGroup:"미국 안전 리콜 제조사 원문",
    company:"현대차 미국법인·제네시스",title:"美 NHTSA "+campaign+" Part 573 제조사 원문 · 한국 판매차 비교 필요",
    officialDate:null,dateBasis:"원문 PDF 발행일 이 색인에서 독립 대조하지 않음",
    officialUrls:[r.officialPdfUrl],facts:passages.map(p=>({
       text:safeLine("Part 573 "+p.section+"(p."+p.page+"): "+p.literalPdfExcerpt,270),
       sourceUrl:r.officialPdfUrl,scope:"미국 판매시장 제조사 제출 PDF 원문",basis:"nhtsa_original_pdf_passage"
    })),angle:"미국 리콜의 실제 결함·대상·조치 확인. 국내 동종 모델의 동일 부품 사용·국내 리콜 부재를 유추할 수 없음",
    questions:["국내 판매사양의 동일 부품번호·생산기간이 공식 인증·리콜 자료와 일치하는가?",
      "국토부 공개 리콜·무상수리 기록에 동일 결함·부품의 국내 조치가 있는가?",
      "현대차 홍보팀이 미국 공식 리콜의 해당 차종·결함 범위에 대해 공개 답변할 수 있는가?"],
    unresolved:["국내 동일 사양·부품번호 미검증","국내 리콜 부재 미확정","동일 논점 국내 선행보도 전문 미확인"],
    existingCoverage:"국내 기사 전문 미대조",possiblePriorTitles:[],
    originalDocumentsVerified:1,originalDocumentsExpected:1,
    originalDocumentBodyRead:true,editorPriority:6,registeredHistoricalCase:false});
  }
 }
 if(queue&&Array.isArray(queue.items)){
  let added=0;
  for(const q of queue.items){
   if(!matches(company,q.company,q.title))continue;
   if(q.exclusiveConfirmed!==false||q.approvedForPitch!==false)continue;
   if(!["new_official_receipt_review","verified_historical_investment_delta"].includes(q.tier))continue;
   const day=q.officialDocumentDate,days=ageDays(day,now);
   if(days===null||days<0||days>10)continue;
   const urls=(q.officialUrls||[]).filter(validHttps).slice(0,3);
   if(!urls.length)continue;
   rows.push({id:"dart:"+q.id,evidenceType:"dart_receipt",sourceGroup:"국내 DART 공식 접수",
    company:safeLine(q.company,90),title:safeLine(q.title,220),officialDate:day,
    dateBasis:"DART 공식 접수일·문서 본문 미검증",
    facts:[{text:safeLine(q.evidenceSummary||"공시 접수 제목과 접수일만 확인",250),
       sourceUrl:urls[0],scope:"공시 접수 사실·현재 기업 영향 미확정",basis:"official_receipt_heading_only"}],
    officialUrls:urls,angle:"공시 접수 사실에서 출발. 금액·계약 상대·실제 사업 변화를 원문 확인 전 기사화 불가",
    questions:(q.nextChecks||[]).slice(0,3).map(x=>safeLine(x.replace(/[.。]\s*$/,""),230)+"?"),
    unresolved:["문서 본문 미검증","사업 영향 및 선행보도 확인 전"],
    existingCoverage:"국내 선행보도 전문 미검증",possiblePriorTitles:[],
    originalDocumentsVerified:0,originalDocumentsExpected:1,
    originalDocumentBodyRead:false,editorPriority:20,registeredHistoricalCase:false
   });
   if(++added>=15)break;
  }
 }
 for(const item of rows){
   // Only compare separately recorded official fields; don't claim that
   // company facilities or operations changed because the notices differ.
   item.originalDocumentComparisons=[];
   const fields=Array.isArray(item.originalFieldProvenance)?
      item.originalFieldProvenance:[];
   const grouped=new Map();
   for(const f of fields){
     if(!validHttps(f.sourceUrl)||!f.field||!f.value)continue;
     if(!grouped.has(f.field))grouped.set(f.field,new Map());
     grouped.get(f.field).set(f.sourceUrl,f.value);
   }
   for(const [field,values] of grouped){
     if(values.size<2||new Set(values.values()).size<2)continue;
     item.originalDocumentComparisons.push({
       field,records:[...values].slice(0,4).map(([url,value])=>({url,value})),
       wording:"동일 항목의 서로 다른 공개 문서 표기 비교",
       actualCompanyOperationalChangeVerified:false,
       originalPublicationOrderVerified:false
     });
   }
   item.reporterStage=statuses(item,+now);
   item.exclusivity="단독 미확정";
   item.reporterAction="검증된 원문 범위를 먼저 확인한 후 공개 사실만 취재";
   item.businessImpactVerified=false;
   item.sameAngleFullTextReviewed=false;
   item.noPriorNewsProved=false;
   item.publishedFirstByReporter=false;
   item.requestedCompany=company;
 }
 // If there is a rich, separately catalogued original dossier for the same
 // event, its discovery URL must not produce a second candidate.
 rows.sort((a,b)=>stageRank(a.reporterStage)-stageRank(b.reporterStage)
   ||a.editorPriority-b.editorPriority
   ||((dateMs(b.officialDate)||0)-(dateMs(a.officialDate)||0))
   ||a.id.localeCompare(b.id));
 meta.totalCandidates=rows.length;
 meta.researchGroups=researchGroups(rows);
 meta.displayed=Math.min(rows.length,limit);
 meta.rows=rows.slice(0,limit);
 meta.gap=rows.length<limit?
   "원문·취재 근거를 갖춘 서로 다른 후보가 "+rows.length+"건뿐이므로 "+limit+
   "건을 채우기 위해 예전 기사나 원문이 불분명한 항목을 추가하지 않았습니다.":
   "상단 후보는 발제 우선순위이며 단독 확정 건수가 아닙니다.";
 return meta;
}
const API={build,identifiers,matches,documentIdentity,researchGroups,reviewUrl};
if(typeof module!=="undefined"&&module.exports)module.exports=API;
root.ScoopRequest=API;
})(typeof window!=="undefined"?window:globalThis);
