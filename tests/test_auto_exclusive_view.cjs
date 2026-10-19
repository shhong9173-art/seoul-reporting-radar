const fs=require("node:fs");
const assert=require("node:assert/strict");
const vm=require("node:vm");
const source=fs.readFileSync("auto_exclusive.js","utf8");
new Function(source);
assert(source.includes("뉴스색인에 관측된 자동차 [단독] 제목"));
assert(source.includes("수집 누락 가능성이 있어 실제 단독기사 0건을 뜻하지 않습니다"));
assert(source.includes("단독표기"));
assert(!source.includes("단독·취재 신호 0건"),
       "Observed zero cannot be presented as zero actual competitor exclusives");
// Reproduce the real production failure: industry_collector rows have no id.
function nav(){
  const items=[];
  return {items,querySelector:sel=>items.find(x=>"#"+x.id===sel)||null,
    appendChild:x=>items.push(x)};
}
const mainNav=nav(),industryNav=nav(),today={textContent:"자동차는"},count={textContent:""};
const selectors={
  '.nav[data-view="must"]':mainNav,
  '.nav[data-view="industryMust"]':industryNav,
  "#today":today,"#countMust":count,
};
const headline=(title,category,url)=>({
  title,category,url,sourceName:"신문",
  published:"2026-10-19T18:00:00+09:00",
  industrySource:true,global:false,tags:[],priority:"normal",
});
const first=headline("[단독] 포스코 구조조정","철강",
                     "https://news.google.com/rss/articles/p1");
const second=headline("[단독] LS전선 새 계약","전선·전력",
                      "https://news.google.com/rss/articles/p2");
const duplicate={...first};
const document={
  readyState:"complete",
  querySelector:selector=>selectors[selector]||null,
  createElement:tag=>({tag,textContent:"",className:"",id:"",title:""}),
};
vm.runInNewContext(source,{
  window:{ITEMS:[first,second,duplicate]},
  document,
});
assert.equal(industryNav.items.length,1);
assert.equal(industryNav.items[0].textContent," · 단독표기 2",
             "Distinct industry [단독] articles without id cannot collapse into one");
assert(first.exclusive&&second.exclusive);
console.log("PASS safe wording and distinct industrial headlines without IDs");
