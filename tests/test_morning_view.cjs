const assert = require('node:assert/strict');
const fs = require('node:fs');
const source = fs.readFileSync('morning.html', 'utf8');
const inline = source.match(/<script>([\s\S]*?)<\/script>/);
assert(inline, 'missing inline viewer');
new Function(inline[1]);
for (const expected of ['digests/latest.json','digests/review_latest.json',
                        '정례 공개·후순위','정정표 변경 검토','originalDocumentVerified',
                        'textContent','DART 공시']) {
  assert(source.includes(expected), 'viewer missing evidence/status marker: '+expected);
}
assert(!source.includes('innerHTML'), 'do not insert untrusted filing content as HTML');
console.log('Morning evidence viewer syntax and safety labels verified');
