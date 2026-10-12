// Minimal DOM harness: verify the user-visible distinctions, without network.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const code = fs.readFileSync(path.join(__dirname, '..', 'scoop.js'), 'utf8');

async function render(status, alignment) {
  let click;
  const cards = {innerHTML: ''};
  const nav = {classList: {add() {}}, addEventListener(_, fn) {click = fn;}};
  const document = {
    querySelector(selector) {return selector === '.scoop-nav' ? nav : selector === '#cards' ? cards : {textContent: ''};},
    querySelectorAll() {return [];}
  };
  const doc = {items: [], sourceHealth: {
    dart: {status, errors: status === 'error' ? [{error: 'TimeoutError'}] : []},
    dartNumeric: {sourceAlignment: alignment}, dartCandidateAlignment: alignment
  }};
  vm.runInNewContext(code, {document, fetch: async () => ({ok: true, json: async () => doc})});
  await click({preventDefault() {}});
  return cards.innerHTML;
}

(async () => {
  const empty = await render('empty', 'current');
  assert.match(empty, /목록 조회 완료/);
  assert.doesNotMatch(empty, /소스 상태 경고/);
  const failed = await render('error', 'changed');
  assert.match(failed, /소스 상태 경고/);
  assert.match(failed, /자료 갱신 확인 필요/);
  assert.doesNotMatch(failed, /목록 조회 완료/);
  const unknown = await render('ok', 'unverified');
  assert.match(unknown, /자료 갱신 확인 필요/);
  assert.doesNotMatch(unknown, /소스 상태 경고/);
  console.log('DART UI: 3 cases passed');
})().catch(error => {console.error(error); process.exitCode = 1;});
