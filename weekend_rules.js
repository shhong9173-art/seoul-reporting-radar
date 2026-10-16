/* Pure newsroom source gates. A clue is not a scoop. */
(function(root,factory){
 const api=factory();
 if(typeof module==="object"&&module.exports)module.exports=api;
 else root.WeekendDeskRules=api;
})(typeof globalThis==="object"?globalThis:this,function(){
"use strict";
const DART=/^https:\/\/dart\.fss\.or\.kr\/dsaf001\/main\.do\?rcpNo=20\d{12}$/;
function day(s){
 if(typeof s!=="string"||!/^20\d{6}$/.test(s))return null;
 const y=+s.slice(0,4),m=+s.slice(4,6),d=+s.slice(6,8),t=Date.UTC(y,m-1,d),v=new Date(t);
 if(v.getUTCFullYear()!==y||v.getUTCMonth()!==m-1||v.getUTCDate()!==d)return null;
 return t;
}
function todayKst(){
 const parts=new Intl.DateTimeFormat("en-US",{timeZone:"Asia/Seoul",year:"numeric",month:"2-digit",day:"2-digit"}).formatToParts(new Date());
 const get=t=>parts.find(p=>p.type===t).value;
 return get("year")+get("month")+get("day");
}
function recent(date,today,maxDays){
 const a=day(date),b=day(today);
 return a!==null&&b!==null&&b>=a&&b-a<=maxDays*86400000;
}
function dartRows(data,today){
 if(!data||data.classification!=="공개자료·단독 여부 미확정"||!Array.isArray(data.items))return [];
 const seen=new Set(),out=[];
 for(const x of data.items){
  if(!x||!recent(String(x.published||""),today,3))continue;
  if(typeof x.receiptNo!=="string"||!/^20\d{12}$/.test(x.receiptNo)||
    x.url!=="https://dart.fss.or.kr/dsaf001/main.do?rcpNo="+x.receiptNo||
    !x.company||!x.report)continue;
  const id=x.company+"|"+x.receiptNo;
  if(seen.has(id))continue;
  seen.add(id);out.push({company:x.company,report:x.report,date:x.published,url:x.url,
   status:"public_filing_not_scoop",sameAnglePressVerified:false,impactVerified:false,articleApproved:false});
 }
 return out.slice(0,30);
}
function investigations(data){
 if(!data||data.status!=="source_changes_detected_not_exclusive"||
    !Array.isArray(data.investigations))return [];
 return data.investigations.filter(x=>x&&x.deskVerdict&&Array.isArray(x.projects)&&x.projects.some(p=>
   p&&p.company===x.company&&p.factVerified&&p.alreadyPublic===true&&
   Array.isArray(p.originalUrls)&&p.originalUrls.length===2&&p.originalUrls.every(u=>DART.test(u))
 )).slice(0,8).map(x=>({title:x.headline,company:x.company,
   questions:(x.deskChecks||[]).filter(v=>typeof v==="string").slice(0,4),
   links:x.projects.flatMap(p=>p.originalUrls||[]).filter(u=>DART.test(u)).slice(0,6),
   impactVerified:false,sameAnglePressVerified:false,articleApproved:false}));
}
function officialState(data,today){
 if(!data||data.status!=="official_date_triage"||!Array.isArray(data.feedHealth)||
   !Array.isArray(data.freshOfficialReview))return {status:"unavailable",items:[]};
 const items=data.freshOfficialReview.filter(x=>x&&typeof x.officialDate==="string"&&
   recent(x.officialDate.replaceAll("-",""),today,3)&&
   x.companyImpactVerified===false&&typeof x.sourceUrl==="string"&&
   x.sourceUrl.startsWith("https://")).slice(0,8);
 return {status:data.sourceCompletenessVerified===true?"checked":"incomplete_source",items};
}
function identityGaps(data){
 if(!data||data.status!=="official_corp_code_registry_checked"||
   !Array.isArray(data.companies))return {status:"unavailable",items:[]};
 return {status:"official_registry_partial",items:data.companies.filter(x=>x&&
    x.corpCode===null&&["no_exact_official_legal_name_match","ambiguous_official_legal_name"].includes(x.status))
   .map(x=>({company:x.company,status:x.status,officialMatches:x.officialMatchCount,
     noFilingsVerified:false})).slice(0,30)};
}
function recallReadiness(data){
 return {status:"awaiting_api_approval_and_documented_schema",
  publicScreen:data&&data.status==="public_search_screen_not_complete_official_or_press_audit"&&
    data.recallApiAuthorization==="required_not_connected"?"first_page_clues_only":"not_verified",
  officialApiConnected:false,absenceOfRecallVerified:false,identicalPartVerified:false,exclusiveConfirmed:false};
}
function sourceAge(stamp){
 const date=Date.parse(stamp||"");
 if(!Number.isFinite(date))return "unavailable";
 const hours=(Date.now()-date)/3600000;
 return hours<(-1)?"future_or_clock_error":hours>48?"stale":"recent";
}
function draft(row){
 if(!row||row.status!=="public_filing_not_scoop"||row.articleApproved!==false||
    row.impactVerified!==false||row.sameAnglePressVerified!==false)return "";
 return "*공시 원문 확인: "+row.company+" "+row.report+" (홍성효, 발제 검토)\n"+
 "- 실제 접수일 "+row.date+" · "+row.url+"\n"+
 "- 계약 상세 수치·상대방·기업 영향은 원문 및 회사 확인 필요\n"+
 "- 동일 사건 선행 보도·단독 미확정 — 기사 출고 문안 아님";
}
return {todayKst,recent,dartRows,investigations,officialState,identityGaps,recallReadiness,sourceAge,draft};
});
