import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import worker from '../cloudflare/redirect.mjs';
const origin = 'https://seoul-reporting-radar.shhong9173.workers.dev';
const canonical = 'https://shhong9173-art.github.io/seoul-reporting-radar';

for (const [path, expected] of [
  ['/', '/'],
  ['/reporting-queue.html', '/reporting-queue.html'],
  ['/digests/reporting_evidence_queue_latest.json?v=1', '/digests/reporting_evidence_queue_latest.json?v=1'],
  ['/seoul-reporting-radar/scoop.json', '/scoop.json'],
  ['/seoul-reporting-radar', '/'],
  ['//evil.example/path?next=https://evil.example', '//evil.example/path?next=https://evil.example']
]) {
  test('canonical destination: ' + path, () => {
    const response = worker.fetch(new Request(origin + path));
    assert.equal(response.status, 307);
    assert.equal(response.headers.get('Location'), canonical + expected);
    assert.equal(response.headers.get('Cache-Control'), 'no-store');
  });
}
test('HEAD redirects and has no response body', async () => {
  const response = worker.fetch(new Request(origin, { method: 'HEAD' }));
  assert.equal(response.status, 307);
  assert.equal(await response.text(), '');
});
test('does not forward write requests to another origin', () => {
  for (const method of ['POST', 'PUT', 'DELETE', 'PATCH']) {
    const response = worker.fetch(new Request(origin, { method }));
    assert.equal(response.status, 405);
    assert.equal(response.headers.get('Location'), null);
  }
});
test('Wrangler references the tested worker and does not upload repository assets', () => {
  const config = JSON.parse(readFileSync(new URL('../wrangler.json', import.meta.url)));
  assert.equal(config.name, 'seoul-reporting-radar');
  // worker.mjs serves /mcp and hands every other path to redirect.mjs
  // (covered in test_cloudflare_mcp.mjs). Repository files are never uploaded.
  assert.equal(config.main, 'cloudflare/worker.mjs');
  assert.equal(config.assets, undefined);
  assert.deepEqual(config.migrations, [{ tag: 'v1', new_sqlite_classes: ['RadarStore'] }]);
});
