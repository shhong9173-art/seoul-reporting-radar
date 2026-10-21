const fs=require("node:fs");
const assert=require("node:assert/strict");
const html=fs.readFileSync("primary-dossiers.html","utf8");
const snippets=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
assert.equal(snippets.length,1);
new Function(snippets[0][1]);
const home=fs.readFileSync("index.html","utf8");
assert(home.includes('href="primary-dossiers.html"'));
for(const value of [
 "digests/primary_research_dossiers_latest.json",
 "registryIsManuallyCuratedNotAutomatedDiscovery",
 "allDomesticPressChecked!==false",
 "data.confirmedScoops!==0",
 "caseFile.factsFromMatchedPrimaryPages",
 "originalDocumentsVerified",
 "noPriorPressProved",
 "source_unavailable",
 "addLink(box,fact.sourceUrl",
])assert(html.includes(value),"Missing evidence-safe view gate: "+value);
assert(!html.includes("innerHTML"),"Remote text must never be raw HTML");
assert(html.includes("textContent"));
assert(html.includes("noopener noreferrer"));
console.log("PASS first-party evidence-safe dossier view and homepage navigation");
