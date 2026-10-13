/* Newspaper-style KIPRIS briefing drafts: source-backed facts only.
 * This is a client-side display adapter, never an automated scoop verdict.
 */
(function(root,factory){
  const formatter=factory();
  if(typeof module==="object" && module.exports)module.exports=formatter;
  if(root)root.PatentPitch=formatter;
})(typeof window!=="undefined"?window:null,function(){
"use strict";
function clean(value){return String(value==null?"":value).replace(/\s+/g," ").trim();}
function company(value){
  return clean(value).replace(/^주식회사\s*/,"").replace(/\s*주식회사$/,"")
    .replace(/\s*\(주\)$/,"").replace("현대자동차","현대차")
    .replace(/산학협력단$/,"산학협력단");
}
function issuers(item){
  const raw=[...(item.coveredCompanies||[]),...(item.outsideBeatCoApplicants||[])];
  return [...new Set(raw.map(company).filter(Boolean))];
}
function focus(item){
  const title=clean(item.title),abstract=clean(item.sourceAbstractExcerpt);
  if(title.includes("부분방전") && title.includes("케이블"))return "케이블 부분방전 센서";
  if(title.includes("상변태") && title.includes("냉각"))return "판재 냉각 제어 기술";
  if(title.includes("침투탐상") && title.includes("압력용기"))return "압력용기 침투탐상 검사장치";
  if(title.includes("도어") && abstract.includes("휠체어"))return "휠체어 승하차 보조 도어";
  if(title.includes("고정자") && title.includes("냉각"))return "고정자 냉각장치";
  if(title.length>36)return title.slice(0,36).replace(/\s+\S*$/,"")+"…";
  return title||"공개특허";
}
function technology(item){
  const title=clean(item.title),abstract=clean(item.sourceAbstractExcerpt);
  // These explanations are guarded by actual words in the KIPRIS excerpt.
  if(title.includes("부분방전") && abstract.includes("노이즈") && abstract.includes("탈부착"))
    return "공식 초록에는 배전 환경의 노이즈 속 부분방전 검출과 케이블 탈부착이 가능한 센서 구조가 기재돼 있음. 실제 성능 개선 여부는 미검증";
  if(title.includes("상변태") && abstract.includes("조직정보") && abstract.includes("냉각수"))
    return "공식 초록에는 판재의 조직·온도 정보를 바탕으로 상변태와 변형을 분석하고 냉각수 공급량을 제어하는 구조가 기재돼 있음";
  if(title.includes("침투탐상") && abstract.includes("내부") && abstract.includes("외부"))
    return "공식 초록에는 대형 압력용기 내·외부 표면의 액체침투탐상 검사를 수행하는 장치 구조가 기재돼 있음";
  if(title.includes("도어") && abstract.includes("휠체어") && abstract.includes("램프"))
    return "공식 초록에는 휠체어 승하차 보조 램프와 간섭 없이 작동하도록 설계한 차량 도어 구조가 기재돼 있음";
  if(title.includes("고정자") && abstract.includes("냉각 유로"))
    return "공식 초록에는 고정자 플레이트와 복수 냉각 유로를 조합하는 냉각장치 구조가 기재돼 있음";
  if(abstract)return "공식 초록에는 '"+abstract.slice(0,135)+(abstract.length>135?"…":"")+"' 등이 기재돼 있음. 기술 효과는 별도 검증 필요";
  return "공식 기술 초록이 확보되지 않아 구성·기술 효과 확인이 필요함";
}
function dateText(value){
  const s=String(value||"");
  if(!/^\d{8}$/.test(s))return "공개일 미확인";
  return Number(s.slice(0,4))+"년 "+Number(s.slice(4,6))+"월 "+Number(s.slice(6))+"일";
}
function kstTime(date){
  const x=date instanceof Date?date:new Date();
  const parts=new Intl.DateTimeFormat("en-GB",{timeZone:"Asia/Seoul",
    hour:"2-digit",minute:"2-digit",hourCycle:"h23"}).formatToParts(x);
  const hour=parts.find(x=>x.type==="hour");
  const minute=parts.find(x=>x.type==="minute");
  return hour&&minute?hour.value+":"+minute.value:"--:--";
}
function title(item){
  const people=issuers(item),orgs=people.slice(0,3).join("·");
  const suffix=people.length>3?" 등":"";
  return (orgs||"출원인 확인 필요")+suffix+", "+focus(item)+(people.length>=2?" 공동출원":" 특허 공개");
}
function points(item){
  const parties=issuers(item),number=clean(item.publicationNumber);
  const count=parties.length;
  const owners=parties.slice(0,4).join("·")+(count>4?" 등":"");
  const fact="- "+dateText(item.publicationDate)+" 공개된 특허공보("+number+")에 "+owners+
    (count>=2?"이 공동출원인으로 등재됨":"이 출원인으로 등재됨");
  const tech="- "+technology(item);
  const media=item.mediaReview||{},prior=item.olderSameTitle||{};
  const press=media.state==="index_no_hits_not_proof"?"일부 뉴스 색인 검색에서 관련 기사 미발견(미보도 증명 아님)":
    media.state==="indexed_potential_same_technology"?"유사 기사 검색돼 원문 대조 필요":
    media.checked?"기보도 여부 전체 검증 전":"언론 선행 보도 미검색";
  const former=prior.state==="searched_same_title_only"?
    "과거 동일 제목 일부 대조":"과거 특허 비교 미실시";
  const issue="- "+press+"·"+former+
    ". 제품·공정 적용, 성능·사업 규모와 기업 답변은 아직 확인되지 않아 발제 보고 전 추가 취재 필요";
  return [fact,tech,issue];
}
function format(item,time){
  return "*"+title(item)+" (홍성효, "+(time||kstTime())+")\n"+points(item).join("\n");
}
function validDataset(desk){
  if(!desk||desk.status!=="research_priorities_only"||
     !Array.isArray(desk.shortlist)||desk.shortlist.length>5||
     !desk.storySourceGeneratedAt||!desk.generatedAt)return false;
  return desk.shortlist.every(x=>/^\d{13}$/.test(String(x.publicationNumber||"")) &&
    Array.isArray(x.coveredCompanies)&&typeof x.title==="string" &&
    x.scoopConfirmed!==true&&x.companyResponsesVerified!==true);
}
return {company,issuers,focus,technology,dateText,kstTime,title,points,format,validDataset};
});
