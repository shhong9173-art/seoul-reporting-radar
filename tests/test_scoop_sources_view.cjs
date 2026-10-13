const fs=require("node:fs");
const assert=require("node:assert/strict");
const page=fs.readFileSync("scoop-sources.html","utf8");
const home=fs.readFileSync("index.html","utf8");
assert(home.includes('href="scoop-sources.html"'));
assert(!page.includes("innerHTML"));
for(const term of ["investigation_hunt_latest.json","recent_metric_changes_latest.json",
"overseas_official_latest.json","nhtsa_investigations_latest.json","epa_facilities_latest.json","epa-status","nhtsa_source_status_latest.json",
"research_procurement_latest.json","customs_hs6_latest.json",
"공식 단독 단서","결함 확정","낙찰","기업 귀속 불가","연구공모",
"0건 주장 금지","EPA ECHO","NTIS"])assert(page.includes(term),term);
const scripts=[...page.matchAll(/<script>([\s\S]*?)<\/script>/g)];
assert.equal(scripts.length,1);
for(const s of scripts)new Function(s[1]);
console.log("Official multi-source evidence hub: all source routes and DOM injection tests PASS");
