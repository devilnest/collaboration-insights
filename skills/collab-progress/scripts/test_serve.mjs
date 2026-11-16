// Checks for serve.mjs: serves only the dashboard, read-only, loopback hosts only.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import { createServer, locateData } from './serve.mjs';

const root = fs.mkdtempSync(path.join(os.tmpdir(), 'collab-serve-'));
const reports = path.join(root, 'reports'); fs.mkdirSync(reports);
fs.writeFileSync(path.join(reports, 'dashboard.html'), '<!doctype html><title>t</title>');
fs.writeFileSync(path.join(reports, 'dashboard.js'), 'console.log(1)');
fs.writeFileSync(path.join(root, 'progress.sqlite'), 'secret');
fs.writeFileSync(path.join(reports, 'latest.json'), '{"secret":true}');

const server = createServer(reports);
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const port = server.address().port;
const request = (pathname, { method = 'GET', host = `127.0.0.1:${port}` } = {}) => new Promise((resolve, reject) => {
  const req = http.request({ host: '127.0.0.1', port, path: pathname, method, headers: { host } }, res => {
    let body = ''; res.on('data', c => body += c); res.on('end', () => resolve({ status: res.statusCode, type: res.headers['content-type'], cache: res.headers['cache-control'], body }));
  });
  req.on('error', reject); req.end();
});

try {
  let r = await request('/');
  assert.equal(r.status, 200); assert.match(r.type, /text\/html/); assert.equal(r.cache, 'no-store');
  assert.match((await request('/dashboard.js')).type, /text\/javascript/);
  r = await request('/dashboard-data.js');
  assert.equal(r.status, 404); assert.match(r.body, /progress\.py snapshot/);
  fs.writeFileSync(path.join(reports, 'dashboard-data.js'), 'window.PROGRESS_DATA={}');
  assert.equal((await request('/dashboard-data.js')).status, 200, 'fresh files are picked up without a restart');
  for (const p of ['/latest.json', '/../progress.sqlite', '/%2e%2e/progress.sqlite', '/reports/dashboard.html', '/history/index.json'])
    assert.equal((await request(p)).status, 404, p + ' must not be served');
  assert.equal((await request('/', { method: 'POST' })).status, 405);
  assert.equal((await request('/', { host: 'evil.example:' + port })).status, 403, 'DNS-rebinding hosts are refused');
  assert.equal((await request('/', { host: 'localhost:' + port })).status, 200);
  assert.equal(server.address().address, '127.0.0.1');

  const skill = path.join(root, 'skill'); fs.mkdirSync(skill);
  assert.equal(locateData(null, {}, skill).dir, null);
  fs.writeFileSync(path.join(skill, 'config.json'), JSON.stringify({ data_dir: 'data' }));
  assert.equal(locateData(null, {}, skill).dir, path.join(skill, 'data'));
  assert.equal(locateData(null, { COLLAB_PROGRESS_HOME: root }, skill).dir, path.resolve(root));
  assert.equal(locateData('/x/y', { COLLAB_PROGRESS_HOME: root }, skill).how, '--data');
  console.log('Server checks passed: dashboard-only routes, read-only, loopback hosts, live reload, data resolution.');
} finally {
  server.close(); fs.rmSync(root, { recursive: true, force: true });
}
