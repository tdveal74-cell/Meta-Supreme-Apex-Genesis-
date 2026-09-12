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
// Off by default so the existing suites read cleanly. The logging section below
// turns it on around the assertions that need it, which also exercises the
// switch in both directions.
process.env.LOG_REQUESTS = '0';

const { server, authFailureReason, logLine } = require('./server.js');

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
t('an oversized body is refused by the size guard, not by the JSON parser', async () => {
  // An earlier version sent 2 MiB of 'x', which is refused as invalid JSON
  // whether or not MAX_BODY is enforced: raising MAX_BODY to 1 GiB still passed
  // it. Send WELL FORMED JSON that is only oversized, so the size guard is the
  // only thing that can reject it.
  const big = JSON.stringify({ type: 'exists', params: { path: '.', pad: 'x'.repeat(2 * 1024 * 1024) } });
  assert.ok(big.length > 2 * 1024 * 1024);
  const r = await req('POST', '/jobs', { raw: big }).catch(() => ({ status: 'reset' }));
  assert.ok(r.status === 400 || r.status === 'reset', 'got ' + r.status + ', size guard not enforced');
});

section('\n-- /health must not leak, and /status must be behind the token --');
t('health carries the job list and nothing operational', async () => {
  const r = await req('GET', '/health', { token: null });
  for (const leak of ['work_root', 'queued', 'running', 'concurrency']) {
    assert.ok(!(leak in r.body), `/health leaks ${leak} to anyone who can reach it`);
  }
});
t('status carries the operational detail and requires the token', async () => {
  assert.strictEqual((await req('GET', '/status', { token: null })).status, 401);
  const r = await req('GET', '/status');
  assert.strictEqual(r.status, 200);
  assert.ok('work_root' in r.body && 'queued' in r.body);
});

section('\n-- the queue is bounded --');
t('a full queue is refused with 503, not grown without limit', async () => {
  // White box on purpose. `exists` finishes in under a millisecond, so firing
  // requests at it never fills the queue: an earlier version of this test
  // reported "80 accepted, 0 refused" and passed while proving nothing. Fill
  // the real queue the server reads, then submit for real over HTTP.
  const { queue } = require('./server.js');
  const before = queue.length;
  // A valid-shaped spec: with the cap removed these drain harmlessly instead of
  // crashing the dispatcher, so a regression shows up as a failed assertion.
  for (let i = 0; i < 64; i++) {
    queue.push({ id: 'filler' + i, type: 'exists', status: 'queued',
                 spec: { native: async () => ({ filler: true }) },
                 started: null, ended: null });
  }
  try {
    const r = await req('POST', '/jobs', { body: { type: 'exists', params: { path: '.' } } });
    assert.strictEqual(r.status, 503, 'a full queue returned ' + r.status + ', not 503');
    assert.ok(/queue is full/.test(r.body.error), r.body.error);
  } finally {
    queue.length = before;
  }
  // and it accepts again once there is room
  const ok = await req('POST', '/jobs', { body: { type: 'exists', params: { path: '.' } } });
  assert.strictEqual(ok.status, 202, 'a drained queue must accept again, got ' + ok.status);
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


section('\n-- why a 401 happened, which is the whole point of the log --');

/** Minimal request stand-in. authFailureReason only ever reads headers. */
const hreq = (headers) => ({ headers });

t('a token one character too long says so, with both lengths', async () => {
  // The 2026-09-12 regression, pinned. A 64 character token arrived as 65
  // because a terminal wrapped the line during a copy and the wrap became a
  // space. Four rounds of diagnosis and a packet capture went into finding
  // that. This line finds it for free.
  const r = authFailureReason(hreq({ authorization: `Bearer ${TOKEN}X` }));
  assert.strictEqual(r, `token-is-${TOKEN.length + 1}-chars-expected-${TOKEN.length}`);
});
t('a token with an interior space is reported by length, not silently', async () => {
  const wrapped = TOKEN.slice(0, 10) + ' ' + TOKEN.slice(10);
  const r = authFailureReason(hreq({ authorization: `Bearer ${wrapped}` }));
  assert.strictEqual(r, `token-is-${TOKEN.length + 1}-chars-expected-${TOKEN.length}`);
});
t('a missing header is distinguished from a wrong token', async () => {
  assert.strictEqual(authFailureReason(hreq({})), 'no-authorization-header');
});
t('an auth-like header under the wrong name is named', async () => {
  const r = authFailureReason(hreq({ 'x-api-key': TOKEN }));
  assert.ok(r.includes('x-api-key'), r);
  assert.ok(r.startsWith('no-authorization-header'), r);
});
t('a lowercase bearer scheme is distinguished from a wrong token', async () => {
  const r = authFailureReason(hreq({ authorization: `bearer ${TOKEN}` }));
  assert.strictEqual(r, 'scheme-is-not-capitalised-Bearer');
});
t('two spaces after Bearer is distinguished from a wrong token', async () => {
  const r = authFailureReason(hreq({ authorization: `Bearer  ${TOKEN}` }));
  assert.strictEqual(r, 'more-than-one-space-after-Bearer');
});
t('a known scheme is named', async () => {
  const r = authFailureReason(hreq({ authorization: `Basic ${TOKEN}` }));
  assert.strictEqual(r, 'scheme-is-Basic-not-Bearer');
});
t('an unknown scheme is NOT echoed, because it may be a pasted credential', async () => {
  const r = authFailureReason(hreq({ authorization: `${TOKEN} ${TOKEN}` }));
  assert.strictEqual(r, 'scheme-is-unrecognised-not-Bearer');
});
t('a bare value with no scheme says so and prints nothing of it', async () => {
  const r = authFailureReason(hreq({ authorization: TOKEN }));
  assert.strictEqual(r, 'authorization-header-has-no-scheme-just-a-value');
});
t('a right-length wrong token says exactly that', async () => {
  const r = authFailureReason(hreq({ authorization: `Bearer ${'X'.repeat(TOKEN.length)}` }));
  assert.strictEqual(r, 'token-is-the-right-length-but-does-not-match');
});
t('NO failure reason ever contains the real token or a slice of it', async () => {
  // The security property. A reason string lands in journald and in whatever a
  // half-asleep operator pastes into a chat window, which is exactly how a live
  // token reached a transcript on 2026-09-12.
  const cases = [
    {}, { authorization: TOKEN }, { authorization: `Bearer ${TOKEN}X` },
    { authorization: `bearer ${TOKEN}` }, { authorization: `Bearer  ${TOKEN}` },
    { authorization: `Basic ${TOKEN}` }, { 'x-api-key': TOKEN },
    { authorization: `Bearer ${'X'.repeat(TOKEN.length)}` },
  ];
  for (const h of cases) {
    const r = authFailureReason(hreq(h));
    assert.ok(!r.includes(TOKEN), `leaked the whole token: ${r}`);
    for (let i = 0; i + 8 <= TOKEN.length; i++) {
      assert.ok(!r.includes(TOKEN.slice(i, i + 8)), `leaked a token slice: ${r}`);
    }
  }
});

section('\n-- the access and job lines themselves --');

/** Run fn with logging on, returning every line console.log emitted. */
async function captureLog(fn) {
  const lines = [];
  const real = console.log;
  const prev = process.env.LOG_REQUESTS;
  process.env.LOG_REQUESTS = '1';
  console.log = (...a) => lines.push(a.join(' '));
  try { await fn(); }
  finally {
    console.log = real;
    if (prev === undefined) delete process.env.LOG_REQUESTS; else process.env.LOG_REQUESTS = prev;
  }
  return lines;
}

t('a successful request writes one access line with method, path, status and ms', async () => {
  const lines = await captureLog(() => req('GET', '/health', { token: null }));
  const access = lines.filter(l => l.includes('path=/health'));
  assert.strictEqual(access.length, 1, 'expected one line, got ' + JSON.stringify(lines));
  assert.ok(/method=GET/.test(access[0]), access[0]);
  assert.ok(/status=200/.test(access[0]), access[0]);
  assert.ok(/ms=[0-9.]+/.test(access[0]), access[0]);
});
t('a 401 access line carries the reason', async () => {
  const lines = await captureLog(() =>
    req('POST', '/jobs', { token: 'short', body: { type: 'exists', params: { path: '.' } } }));
  const l = lines.find(x => x.includes('status=401'));
  assert.ok(l, 'no 401 line in ' + JSON.stringify(lines));
  assert.ok(l.includes('auth=token-is-5-chars-expected-' + TOKEN.length), l);
});
t('no log line ever contains the token', async () => {
  const lines = await captureLog(async () => {
    await req('GET', '/health', { token: null });
    const sub = await req('POST', '/jobs', { body: { type: 'exists', params: { path: '.' } } });
    await pollUntilFinished(sub.body.id);
    await req('POST', '/jobs', { token: TOKEN + 'X', body: { type: 'exists', params: { path: '.' } } });
  });
  assert.ok(lines.length > 0, 'nothing was logged at all');
  for (const l of lines) assert.ok(!l.includes(TOKEN), 'a log line carried the token: ' + l);
});
t('a job writes a start line and an end line joinable by id', async () => {
  let id;
  const lines = await captureLog(async () => {
    const sub = await req('POST', '/jobs', { body: { type: 'exists', params: { path: '.' } } });
    id = sub.body.id;
    await pollUntilFinished(id);
  });
  const start = lines.find(l => l.includes('job=start') && l.includes(`id=${id}`));
  const end = lines.find(l => l.includes('job=end') && l.includes(`id=${id}`));
  assert.ok(start, 'no start line: ' + JSON.stringify(lines));
  assert.ok(end, 'no end line: ' + JSON.stringify(lines));
  assert.ok(start.includes('type=exists'), start);
  assert.ok(end.includes('status=done'), end);
  assert.ok(/seconds=[0-9.]+/.test(end), end);
  // The access line for the submit must carry the same id, or the two logs
  // cannot be joined and the access log is decoration.
  assert.ok(lines.some(l => l.includes('path=/jobs') && l.includes(`id=${id}`)),
    'no access line carried the job id');
});
t('LOG_REQUESTS=0 silences every line', async () => {
  const lines = [];
  const real = console.log;
  process.env.LOG_REQUESTS = '0';
  console.log = (...a) => lines.push(a.join(' '));
  try {
    const sub = await req('POST', '/jobs', { body: { type: 'exists', params: { path: '.' } } });
    await pollUntilFinished(sub.body.id);
    await req('GET', '/health', { token: null });
  } finally { console.log = real; }
  assert.strictEqual(lines.length, 0, 'logged while off: ' + JSON.stringify(lines));
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
