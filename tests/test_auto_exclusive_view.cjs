const fs=require("node:fs");
const assert=require("node:assert/strict");
const source=fs.readFileSync("auto_exclusive.js","utf8");
new Function(source);
assert(source.includes("뉴스색인에 관측된 자동차 [단독] 제목"));
assert(source.includes("수집 누락 가능성이 있어 실제 단독기사 0건을 뜻하지 않습니다"));
assert(source.includes("단독표기"));
assert(!source.includes("단독·취재 신호 0건"),
       "Observed zero cannot be presented as zero actual competitor exclusives");
console.log("PASS safe incomplete-data wording for recent [단독] view");
