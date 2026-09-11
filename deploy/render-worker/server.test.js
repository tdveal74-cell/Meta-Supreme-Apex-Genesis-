'use strict';
/**
 * Render worker server tests.
 *
 * These make real HTTP requests against a real listening server, so they prove
 * the transport, the auth and the job lifecycle end to end. They deliberately
 * use `exists`, which is one of the seven native jobs and spawns no ffmpeg, so
 * the whole contract can be exercised on a box that has no ffmpeg at all.
 *
 * `{"type":"exists","params":{"path":"."}}` is not an arbitrary choice. It is
 * the exact smoke test the sticky note on TSWS 00 tells the operator to run,
 * and that note records that it "has never once succeeded".
 *
 *   node server.test.js
 */
const assert = require('assert');
const http = require('http');
const fs = require('fs');
const os = require('os');
const path = require('path');

const ROOT = fs.mkdtempSync(path.join(os.tmpdir(), 'tsws-server-test-'));
const TOKEN = 'test-token-that-is-long-enough-0123456789';
process.env.WORKER_TOKEN = TOKEN;
process.env.WORK_ROOT = ROOT;
process.env.PORT = '0';

const { server } = require('./server.js');

let BASE;
const req = (method, p, { token = TOKEN, body = null, raw = null } = {}) =>
  new Promise((resolve, reject) => {
    const headers = {};
    if (token !== null) headers['authorization'] = `Bearer ${token}`;
    let payload = raw;
    if (body !== null) { payload = JSON.stringify(body); headers['content-type'] = 'application/json'; }
    if (payload !== null) headers['content-length'] = Buffer.byteLength(payload);
    const r = http.request(BASE + p, { method, headers }, res => {
      let d = '';
      res.on('data', c => (d += c));
      res.on('end', () => {
        let json = null;
        try { json = JSON.parse(d); } catch { /* left null on purpose */ }
        resolve({ status: res.statusCode, body: json, text: d });
      });
    });
    r.on('error', reject);
    if (payload !== null) r.write(payload);
    r.end();
  });

/** Poll exactly the way TSWS 00's Poll Job / Finished? loop does. */
async function pollUntilFinished(id, tries = 60) {
  for (let i = 0; i < tries; i++) {
    const r = await req('GET', `/jobs/${id}`);
    assert.strictEqual(r.status, 200, 'poll returned ' + r.status);
    if (['done', 'error', 'invalid'].includes(r.body.status)) return r.body;
    await new Promise(s => setTimeout(s, 25));
  }
  throw new Error('job never finished');
}

let pass = 0, fail = 0;
const QUEUE = [];
const t = (name, fn) => QUEUE.push([name, fn]);
const section = (name) => QUEUE.push([name, null]);

section('\n-- /health, the one unauthenticated route --');
t('health needs no token and lists the job types', async () => {
  const r = await req('GET', '/health', { token: null });
  assert.strictEqual(r.status, 200);
  assert.strictEqual(r.body.ok, true);
  // The sticky note tells an operator to compare this against 18 to tell a
  // stale jobs.js from a current one.
  assert.strictEqual(r.body.job_count, 18, 'job_count was ' + r.body.job_count);
  assert.ok(r.body.jobs.includes('assemble_cut'));
  assert.ok(r.body.jobs.includes('duck_mix'));
});

section('\n-- auth --');
t('no Authorization header is 401', async () => {
  const r = await req('POST', '/jobs', { token: null, body: { type: 'exists', params: { path: '.' } } });
  assert.strictEqual(r.status, 401);
});
t('a wrong token of the same length is 401', async () => {
  const r = await req('POST', '/jobs', { token: 'X'.repeat(TOKEN.length), body: { type: 'exists', params: { path: '.' } } });
  assert.strictEqual(r.status, 401);
});
t('a wrong token of a different length is 401, not a crash', async () => {
  const r = await req('POST', '/jobs', { token: 'short', body: { type: 'exists', params: { path: '.' } } });
  assert.strictEqual(r.status, 401);
});
t('a token without the Bearer prefix is 401', async () => {
  const r = await new Promise((resolve, reject) => {
    const b = JSON.stringify({ type: 'exists', params: { path: '.' } });
    const q = http.request(BASE + '/jobs', {
      method: 'POST',
      headers: { authorization: TOKEN, 'content-type': 'application/json', 'content-length': b.length },
    }, res => { res.resume(); res.on('end', () => resolve({ status: res.statusCode })); });
    q.on('error', reject); q.write(b); q.end();
  });
  assert.strictEqual(r.status, 401);
});

section('\n-- THE SMOKE TEST FROM THE STICKY NOTE --');
t('{"type":"exists","params":{"path":"."}} returns 202 then ok:true', async () => {
  const sub = await req('POST', '/jobs', { body: { type: 'exists', params: { path: '.' } } });
  // Accepted? in TSWS 00 compares statusCode against 202 exactly.
  assert.strictEqual(sub.status, 202, 'submit returned ' + sub.status + ' ' + sub.text);
  // Poll Job reads $('Submit Job').first().json.body.id
  assert.ok(typeof sub.body.id === 'string' && sub.body.id.length > 0, 'no id on the submit response');
  const fin = await pollUntilFinished(sub.body.id);
  assert.strictEqual(fin.status, 'done', 'status was ' + fin.status + ' ' + JSON.stringify(fin.error));
  assert.strictEqual(fin.ok, true, 'ok was not true');
  assert.ok(typeof fin.seconds === 'number', 'seconds missing');
  console.log('        ok:true  seconds=' + fin.seconds + '  result=' + JSON.stringify(fin.result));
});

t('the poll response carries every field TSWS 00 reads', async () => {
  const sub = await req('POST', '/jobs', { body: { type: 'exists', params: { path: '.' } } });
  const fin = await pollUntilFinished(sub.body.id);
  // Return Result reads id, result, seconds, type.
  // Return Failure reads status, id, error, exitCode, type.
  for (const k of ['id', 'type', 'status', 'ok', 'result', 'error', 'exitCode', 'seconds']) {
    assert.ok(k in fin, `poll response is missing ${k}`);
  }
  assert.strictEqual(fin.type, 'exists');
});

t('a real file reports hit:true with its byte count', async () => {
  fs.writeFileSync(path.join(ROOT, 'plate.jpg'), 'abcdefghij');
  const sub = await req('POST', '/jobs', { body: { type: 'exists', params: { path: 'plate.jpg' } } });
  const fin = await pollUntilFinished(sub.body.id);
  assert.strictEqual(fin.result.hit, true);
  assert.strictEqual(fin.result.bytes, 10);
});

section('\n-- rejection at submit, so a retry is known to be pointless --');
t('an unknown job type is 400 and names the known ones', async () => {
  const r = await req('POST', '/jobs', { body: { type: 'rm_rf', params: {} } });
  assert.strictEqual(r.status, 400);
  assert.ok(/assemble_cut/.test(r.body.error), 'the error should list the known types');
});
t('a BadJob from validation is 400, not 500', async () => {
  const r = await req('POST', '/jobs', { body: { type: 'exists', params: {} } });
  assert.strictEqual(r.status, 400, 'got ' + r.status + ' ' + r.text);
  assert.ok(/missing/.test(r.body.error), r.body.error);
});
t('a path escaping the work root is refused at submit', async () => {
  const r = await req('POST', '/jobs', { body: { type: 'exists', params: { path: '../../etc/passwd' } } });
  assert.strictEqual(r.status, 400);
  assert.ok(/escapes the work root/.test(r.body.error), r.body.error);
});
t('a prototype-pollution style type is refused, not resolved', async () => {
  for (const type of ['constructor', '__proto__', 'toString', 'hasOwnProperty']) {
    const r = await req('POST', '/jobs', { body: { type, params: {} } });
    assert.strictEqual(r.status, 400, `${type} returned ${r.status}`);
  }
});
t('a body that is not JSON is 400', async () => {
  const r = await req('POST', '/jobs', { raw: 'not json at all' });
  assert.strictEqual(r.status, 400);
});
t('an oversized body is refused rather than buffered', async () => {
  const r = await req('POST', '/jobs', { raw: 'x'.repeat(2 * 1024 * 1024) }).catch(e => ({ status: 'reset', e }));
  assert.ok(r.status === 400 || r.status === 'reset', 'got ' + r.status);
});

section('\n-- lifecycle --');
t('polling an unknown id is 404', async () => {
  const r = await req('GET', '/jobs/00000000-0000-0000-0000-000000000000');
  assert.strictEqual(r.status, 404);
});
t('an unrouted path is 404', async () => {
  const r = await req('GET', '/admin');
  assert.strictEqual(r.status, 404);
});

(async () => {
  await new Promise(r => server.listen(0, '127.0.0.1', r));
  BASE = `http://127.0.0.1:${server.address().port}`;
  for (const [name, fn] of QUEUE) {
    if (fn === null) { console.log(name); continue; }
    try { await fn(); pass++; console.log('  PASS  ' + name); }
    catch (e) { fail++; console.log('  FAIL  ' + name + '\n        ' + e.message); }
  }
  console.log(`\n${pass} passed, ${fail} failed\n`);
  server.close();
  fs.rmSync(ROOT, { recursive: true, force: true });
  process.exit(fail ? 1 : 0);
})();
