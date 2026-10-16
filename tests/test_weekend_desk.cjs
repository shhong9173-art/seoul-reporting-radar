const assert=require("node:assert/strict"),fs=require("node:fs"),r=require("../weekend_rules.js");
const today="20261016";
const input={classification:"공개자료·단독 여부 미확정",items:[
{company:"대한전선",report:"단일판매ㆍ공급계약체결",published:"20261015",receiptNo:"20261015800054",url:"https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261015800054"},
{company:"대한전선",report:"단일판매ㆍ공급계약체결",published:"20261015",receiptNo:"20261015800054",url:"https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261015800054"},
{company:"기아",report:"과거 공시",published:"20260901",receiptNo:"20260901000001",url:"https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260901000001"},
{company:"현대차",report:"가짜",published:"20261016",receiptNo:"20261016000001",url:"https://invalid.test/no"}]};
const rows=r.dartRows(input,today);assert.equal(rows.length,1);
assert.equal(rows[0].articleApproved,false);
assert.ok(r.draft(rows[0]).includes("단독 미확정"));
assert.equal(r.draft({...rows[0],articleApproved:true}),"");
assert.equal(r.recent("20261013",today,3),true);
assert.equal(r.recent("20261012",today,3),false);
assert.equal(r.recent("20261017",today,3),false);
assert.equal(r.recent("20260230",today,3),false);
const gaps=r.identityGaps({status:"official_corp_code_registry_checked",companies:[
{company:"KG스틸",corpCode:null,status:"ambiguous_official_legal_name",officialMatchCount:2},
{company:"BMW코리아",corpCode:null,status:"no_exact_official_legal_name_match",officialMatchCount:0},
{company:"기아",corpCode:"00106641",status:"existing_code_verified_in_official_registry"}]});
assert.equal(gaps.items.length,2);assert.equal(gaps.items[0].noFilingsVerified,false);
assert.equal(r.identityGaps(null).status,"unavailable");
const gate=r.recallReadiness({status:"public_search_screen_not_complete_official_or_press_audit",recallApiAuthorization:"required_not_connected"});
assert.equal(gate.officialApiConnected,false);assert.equal(gate.absenceOfRecallVerified,false);
const inv={status:"source_changes_detected_not_exclusive",investigations:[
{company:"HD현대일렉트릭",headline:"3개 프로젝트",deskVerdict:"발제 미확정",projects:[
{company:"HD현대일렉트릭",factVerified:"확인",alreadyPublic:true,
originalUrls:["https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260316000940",
"https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260814003228"]}]}]};
assert.equal(r.investigations(inv).length,1);
assert.equal(r.investigations(inv)[0].articleApproved,false);
const html=fs.readFileSync("weekend-desk.html","utf8");
for(const marker of ["주말 발제","국내 리콜 API 준비","DART 법인명","weekend_rules.js","기보도"]){
 assert.ok(html.includes(marker),marker);
}
assert.ok(html.includes("kipris_source_request_budget_latest.json"));
assert.ok(html.includes("patent_source_status_latest.json"));
assert.ok(html.includes("코드 의미 자동 단정 금지"));
assert.ok(!html.includes("innerHTML"));
const scripts=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
assert.equal(scripts.length,1);
new Function(scripts[0][1]);
console.log("PASS: weekend newsroom fact-only 72h gating, DART identities, API readiness and scripts");
