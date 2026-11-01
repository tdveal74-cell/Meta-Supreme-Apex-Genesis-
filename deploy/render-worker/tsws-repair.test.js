'use strict';
/**
 * tsws_repair tests.
 *
 * The job and the server's claim hook ran on the box from 2026-10-17 with no
 * copy in this repository and no test anywhere; the box's own package.json
 * named this file and it did not exist. tsws-repair.js here is byte identical
 * to the live file (sha256 4af32fea930ef4bb..., read back 2026-10-31). These
 * tests pin what it does today. They fix nothing in it.
 *
 * The interpreter is this Node binary and the "repair package" is three small
 * scripts that keep the package's file names. The bridge does not care what the
 * interpreter is: it spawns TSWS_REPAIR_PYTHON with the script, the method, the
 * staged job and --out. So these prove the bridge and the HTTP path, and prove
 * nothing about the real Python package, Blender or the box's runtime.
 *
 *   node tsws-repair.test.js
 */
const assert = require('assert');
const crypto = require('crypto');
const fs = require('fs');
const http = require('http');
const os = require('os');
const path = require('path');

const TMP = fs.realpathSync(os.tmpdir());
const ROOT = fs.mkdtempSync(path.join(TMP, 'tsws-repair-root-'));
const PKG = fs.mkdtempSync(path.join(TMP, 'tsws-repair-pkg-'));
const CACHE = fs.mkdtempSync(path.join(TMP, 'tsws-repair-cache-'));
const TOKEN = 'test-token-that-is-long-enough-0123456789';
process.env.WORKER_TOKEN = TOKEN;
process.env.WORK_ROOT = ROOT;
process.env.PORT = '0';
process.env.LOG_REQUESTS = '0';
process.env.JOB_TIMEOUT_MS = '20000';
// Small, so the queue-full test can fill it with three slow envelopes.
process.env.MAX_QUEUE = '2';

const J = require('./jobs.js');
const R = require('./tsws-repair.js');
const { server } = require('./server.js');
J.setRoot(ROOT);

const ORIGIN = 'http://172.16.0.9:8080';
const ENV = {
  TSWS_REPAIR_PACKAGE_ROOT: PKG,
  TSWS_REPAIR_CACHE_ROOT: CACHE,
  TSWS_REPAIR_PYTHON: process.execPath,
  TSWS_REPAIR_PUBLIC_ORIGIN: ORIGIN,
};
const setEnv = (over) => {
  for (const [k, v] of Object.entries(Object.assign({}, ENV, over || {}))) {
    if (v === null) delete process.env[k]; else process.env[k] = v;
  }
};
setEnv();

// A stand-in package. Each script reads the staged job, writes its pid beside
// the output folder, and after test_sleep_ms writes RESULT.json (echoing the
// source path it was handed) and one frame into --out, then exits with
// test_exit (0 when absent). test_flood writes 20 MiB to stdout first;
// test_symlink leaves a symlink in the output.
const FAKE = `
const fs = require('fs'), path = require('path');
const a = process.argv.slice(2);
const job = JSON.parse(fs.readFileSync(a[a.indexOf(a[1]) + 1], 'utf8'));
const out = a[a.indexOf('--out') + 1];
fs.writeFileSync(path.join(path.dirname(out), 'fake.pid'), String(process.pid));
if (job.test_flood) { const chunk = 'x'.repeat(1 << 20); for (let i = 0; i < 20; i++) process.stdout.write(chunk); }
setTimeout(() => {
  if (!job.test_no_result) {
    fs.writeFileSync(path.join(out, 'RESULT.json'), JSON.stringify({ verdict: job.test_verdict || 'PASS', method: a[0],
      seen_path: job.source && job.source.path }));
    fs.mkdirSync(path.join(out, 'frames'));
    fs.writeFileSync(path.join(out, 'frames', 'f0001.png'), 'frame-bytes');
  }
  if (job.test_symlink) fs.symlinkSync('/etc/hostname', path.join(out, 'escape'));
  console.log('fake repair ran', a[0]);
  process.exit(job.test_exit || 0);
}, job.test_sleep_ms || 0);
`;
for (const rel of Object.values(R.METHODS).map(m => m[0])) {
  fs.mkdirSync(path.join(PKG, path.dirname(rel)), { recursive: true });
  fs.writeFileSync(path.join(PKG, rel), FAKE);
}

const sha = (b) => crypto.createHash('sha256').update(b).digest('hex');
/** Put bytes in the cache under CACHE/DRIVE_ID/SHA256, the pre-stage convention. */
function stage(driveId, bytes, nameSha) {
  const h = nameSha || sha(bytes);
  fs.mkdirSync(path.join(CACHE, driveId), { recursive: true });
  fs.writeFileSync(path.join(CACHE, driveId, h), bytes);
  return h;
}
let n = 0;
/** A valid composer envelope with its job file and one input already staged. */
function envelope(jobOver, over) {
  const id = 'env' + (++n);
  const job = Object.assign({ workflow: 'TSWS_SHOT_COMPOSER', status: 'DRAFT',
    source: { path: 'plate.png', first_frame: 1, last_frame: 48, fps: 24 } }, jobOver || {});
  const jobBytes = JSON.stringify(job);
  const plate = 'plate-bytes-' + id;
  return Object.assign({
    envelope_id: id, workflow: 'TSWS_SHOT_COMPOSER',
    job: { job_file_drive_id: 'job' + id, job_file_sha256: stage('job' + id, jobBytes) },
    inputs: [{ drive_id: 'in' + id, sha256: stage('in' + id, plate), role: 'plate.png', bytes: Buffer.byteLength(plate) }],
  }, over || {});
}
const build = (p) => J.JOBS.tsws_repair.build(p);
const refuses = (p, re, code) => assert.throws(() => build(p),
  (e) => re.test(e.message) && (code === undefined || e.statusCode === code), 'expected ' + re);

let pass = 0, fail = 0;
const QUEUE = [];
const t = (name, fn) => QUEUE.push([name, fn]);
const section = (name) => QUEUE.push([name, null]);

section('\n-- refused at submit, before anything touches the disk --');
t('a bad envelope id, an unknown workflow and a command that does not match are refused', () => {
  refuses(envelope({}, { envelope_id: '../x' }), /invalid envelope_id/, 400);
  refuses(envelope({}, { workflow: 'TSWS_NOPE' }), /unsupported repair workflow/, 400);
  refuses(envelope({}, { command: 'other.py run' }), /fixed workflow mapping/, 400);
  assert.ok(build(envelope({}, { command: 'tsws_shot_composer.py run' })).claim);
});
t('generation is refused however it is asked for', () => {
  refuses(envelope({}, { generation_requested: true }), /generation is not supported/);
  refuses(envelope({}, { generation_jobs: [{}] }), /generation is not supported/);
});
t('a job with no Drive id or SHA-256, and empty or malformed inputs, are refused', () => {
  refuses(envelope({}, { job: { job_file_drive_id: 'x' } }), /Drive id and SHA-256/);
  refuses(envelope({}, { inputs: [] }), /1\.\.10000 files/);
  const e = envelope();
  refuses(Object.assign({}, e, { inputs: [e.inputs[0], e.inputs[0]] }), /duplicate input role/);
  refuses(Object.assign({}, e, { inputs: [Object.assign({}, e.inputs[0], { role: '../etc/passwd' })] }), /no dot traversal/);
  refuses(Object.assign({}, e, { inputs: [Object.assign({}, e.inputs[0], { bytes: -1 })] }), /invalid byte count/);
});

section('\n-- the operator owns the configuration --');
t('any missing TSWS_REPAIR_ variable is a 503 naming BLOCKED_CONFIGURATION', () => {
  for (const k of Object.keys(ENV)) {
    setEnv({ [k]: null });
    try { refuses(envelope(), /BLOCKED_CONFIGURATION/, 503); } finally { setEnv(); }
  }
});
t('an origin with a path, credentials or a query is a 503, never used', () => {
  for (const o of [ORIGIN + '/x', 'http://u:p@172.16.0.9:8080', ORIGIN + '/?q=1', 'ftp://172.16.0.9']) {
    setEnv({ TSWS_REPAIR_PUBLIC_ORIGIN: o });
    try { refuses(envelope(), /repair origin|invalid configured repair origin/, 503); } finally { setEnv(); }
  }
});

section('\n-- the durable claim --');
t('native() refuses to run without a claim', async () => {
  const b = build(envelope());
  await assert.rejects(b.native(), /durable claim required/);
});
t('a claim writes CLAIM.json with retry REFUSED, and a second claim of the same envelope is a 409', () => {
  const p = envelope();
  build(p).claim('job-a');
  const runRoot = path.join(ROOT, 'repair', p.envelope_id);
  const c = JSON.parse(fs.readFileSync(path.join(runRoot, 'CLAIM.json'), 'utf8'));
  assert.strictEqual(c.retry, 'REFUSED');
  assert.strictEqual(c.job_id, 'job-a');
  assert.strictEqual(c.request_sha256, sha(JSON.stringify(p)));
  assert.strictEqual(fs.statSync(runRoot).mode & 0o777, 0o700);
  assert.throws(() => build(p).claim('job-b'), (e) => e.statusCode === 409 && /automatic retry refused/.test(e.message));
});

section('\n-- the run --');
t('a claimed run stages the inputs read only, runs the package, and returns a DRAFT receipt that needs a human', async () => {
  const p = envelope();
  const b = build(p);
  b.claim('job-run');
  const r = await b.native();
  assert.strictEqual(r.status, 'DRAFT');
  assert.strictEqual(r.verdict, 'PASS');
  assert.strictEqual(r.exit_code, 0);
  assert.strictEqual(r.complete_shot_accepted, false);
  assert.strictEqual(r.human_review_required, true);
  assert.strictEqual(r.continuous_playback, 'UNVERIFIED');
  assert.strictEqual(r.artifacts.length, 2);
  const runRoot = path.join(ROOT, 'repair', p.envelope_id);
  for (const a of r.artifacts) {
    const file = path.join(runRoot, 'output', a.relative_path);
    assert.strictEqual(a.sha256, sha(fs.readFileSync(file)));
    assert.ok(a.url.startsWith(ORIGIN + '/files/repair/' + p.envelope_id + '/output/'), a.url);
  }
  assert.strictEqual(fs.statSync(path.join(runRoot, 'inputs', 'plate.png')).mode & 0o777, 0o400);
  assert.ok(fs.existsSync(path.join(runRoot, 'DELIVERY.json')));
  assert.ok(/fake repair ran/.test(fs.readFileSync(path.join(runRoot, 'PROCESS.log'), 'utf8')));
  // the package is handed the staged copy, never the caller's relative name
  assert.strictEqual(r.result.seen_path, path.join(runRoot, 'inputs', 'plate.png'));
});
t('a cache entry that is a symlink is refused, even when its target holds the right bytes', async () => {
  const p = envelope();
  const real = path.join(TMP, 'outside-' + p.envelope_id);
  fs.writeFileSync(real, 'plate-bytes-' + p.envelope_id);
  const entry = path.join(CACHE, p.inputs[0].drive_id, p.inputs[0].sha256);
  fs.unlinkSync(entry); fs.symlinkSync(real, entry);
  const b = build(p); b.claim('job-link');
  try { await assert.rejects(b.native(), /symlink or path escape refused/); } finally { fs.rmSync(real, { force: true }); }
});
t('a cache entry that is a symlink to another file inside the cache is refused too', async () => {
  const p = envelope();
  const entry = path.join(CACHE, p.inputs[0].drive_id, p.inputs[0].sha256);
  const twin = entry + '.twin';
  fs.renameSync(entry, twin); fs.symlinkSync(twin, entry);
  const b = build(p); b.claim('job-twin');
  await assert.rejects(b.native(), /symlink or path escape refused/);
});
t('a staged input whose size differs from the declared bytes fails the run', async () => {
  const p = envelope();
  p.inputs[0] = Object.assign({}, p.inputs[0], { bytes: p.inputs[0].bytes + 1 });
  const b = build(p); b.claim('job-bytes');
  await assert.rejects(b.native(), /byte count mismatch/);
});
t('a symlink the package leaves in its output is refused', async () => {
  const b = build(envelope({ test_symlink: true })); b.claim('job-outlink');
  await assert.rejects(b.native(), /output symlink refused/);
});
t('abort() kills the package\'s whole process group, and the run reports it', async () => {
  const p = envelope({ test_sleep_ms: 30000 });
  const b = build(p); b.claim('job-abort');
  const run = b.native();
  const pidFile = path.join(ROOT, 'repair', p.envelope_id, 'fake.pid');
  for (let i = 0; i < 200 && !fs.existsSync(pidFile); i++) await new Promise(s => setTimeout(s, 25));
  const pid = Number(fs.readFileSync(pidFile, 'utf8'));
  b.abort();
  await assert.rejects(run, /repair aborted/);
  let alive = true;
  for (let i = 0; i < 40 && alive; i++) {
    try { process.kill(pid, 0); await new Promise(s => setTimeout(s, 25)); } catch (e) { alive = e.code !== 'ESRCH'; }
  }
  assert.strictEqual(alive, false, 'the package process outlived abort()');
});
t('more than 16 MiB of package output stops the run and the log stays under the cap', async () => {
  const p = envelope({ test_flood: true, test_sleep_ms: 30000 });
  const b = build(p); b.claim('job-flood');
  await assert.rejects(b.native(), /log limit exceeded/);
  assert.ok(fs.statSync(path.join(ROOT, 'repair', p.envelope_id, 'PROCESS.log')).size <= 16 * 1024 ** 2);
});
t('a staged input whose bytes do not match its SHA-256 fails the run and writes ERROR.json', async () => {
  const p = envelope();
  const wrong = stage('bad' + p.envelope_id, 'other-bytes', sha('the bytes the caller promised'));
  p.inputs[0] = { drive_id: 'bad' + p.envelope_id, sha256: wrong, role: 'plate.png' };
  const b = build(p); b.claim('job-sha');
  await assert.rejects(b.native(), /input SHA-256 mismatch/);
  const err = JSON.parse(fs.readFileSync(path.join(ROOT, 'repair', p.envelope_id, 'ERROR.json'), 'utf8'));
  assert.strictEqual(err.automatic_retry, false);
});
t('an input that was never staged is BLOCKED_INPUT_DELIVERY, with no fetch', async () => {
  const p = envelope();
  p.inputs[0] = Object.assign({}, p.inputs[0], { drive_id: 'never-staged', bytes: undefined });
  const b = build(p); b.claim('job-missing');
  await assert.rejects(b.native(), /BLOCKED_INPUT_DELIVERY/);
});
t('an exit code outside 0, 1 and 3, or no RESULT.json, fails the run', async () => {
  const b = build(envelope({ test_exit: 2 })); b.claim('job-exit');
  await assert.rejects(b.native(), /repair process failed: exit 2/);
  const c = build(envelope({ test_no_result: true })); c.claim('job-noresult');
  await assert.rejects(c.native(), /repair process failed: exit 0/);
});
t('the staged job is refused when it names an undeclared input, an unsafe pattern or impossible frames', () => {
  const roles = ['plate.png'];
  const job = (over) => Object.assign({ workflow: 'TSWS_SHOT_COMPOSER', status: 'DRAFT',
    source: { first_frame: 1, last_frame: 48, fps: 24 } }, over);
  assert.throws(() => R.rewriteJob(job({ mask: { path: 'other.png' } }), 'TSWS_SHOT_COMPOSER', ROOT, roles), /undeclared input/);
  assert.throws(() => R.rewriteJob(job({ out: { pattern: '../x%04d.png' } }), 'TSWS_SHOT_COMPOSER', ROOT, roles), /unsafe frame pattern/);
  assert.throws(() => R.rewriteJob(job({ source: { first_frame: 5, last_frame: 5, fps: 24 } }), 'TSWS_SHOT_COMPOSER', ROOT, roles), /frame count/);
  assert.throws(() => R.rewriteJob(job({ source: { first_frame: 1, last_frame: 48, fps: 0 } }), 'TSWS_SHOT_COMPOSER', ROOT, roles), /fps outside/);
  assert.throws(() => R.rewriteJob(job({ status: 'FINAL' }), 'TSWS_SHOT_COMPOSER', ROOT, roles), /workflow\/status mismatch/);
});

section('\n-- through the server, which is where the claim hook lives --');
let BASE;
const req = (method, p, body) => new Promise((resolve, reject) => {
  const payload = body === undefined ? null : JSON.stringify(body);
  const headers = { authorization: `Bearer ${TOKEN}` };
  if (payload) { headers['content-type'] = 'application/json'; headers['content-length'] = Buffer.byteLength(payload); }
  const r = http.request(BASE + p, { method, headers }, res => {
    let d = ''; res.on('data', c => (d += c));
    res.on('end', () => { let j = null; try { j = JSON.parse(d); } catch { /* null */ } resolve({ status: res.statusCode, body: j }); });
  });
  r.on('error', reject); if (payload) r.write(payload); r.end();
});
async function poll(id) {
  for (let i = 0; i < 400; i++) {
    const r = await req('GET', `/jobs/${id}`);
    if (['done', 'error', 'invalid'].includes(r.body.status)) return r.body;
    await new Promise(s => setTimeout(s, 25));
  }
  throw new Error('job never finished');
}
t('/health lists tsws_repair among 25 job types', async () => {
  const r = await req('GET', '/health');
  assert.strictEqual(r.status, 200);
  assert.ok(r.body.jobs.includes('tsws_repair'));
  assert.strictEqual(r.body.job_count, 25);
});
t('a submitted envelope is claimed at submit, runs to done, and its second submit is a 409, not a 500', async () => {
  const p = envelope();
  const a = await req('POST', '/jobs', { type: 'tsws_repair', params: p });
  assert.strictEqual(a.status, 202, JSON.stringify(a.body));
  const claim = JSON.parse(fs.readFileSync(path.join(ROOT, 'repair', p.envelope_id, 'CLAIM.json'), 'utf8'));
  assert.strictEqual(claim.job_id, a.body.id);
  const done = await poll(a.body.id);
  assert.strictEqual(done.status, 'done', done.error);
  assert.strictEqual(done.result.verdict, 'PASS');
  const b = await req('POST', '/jobs', { type: 'tsws_repair', params: p });
  assert.strictEqual(b.status, 409);
  assert.ok(/automatic retry refused/.test(b.body.error));
});
t('a full queue answers 503 before the claim, so the envelope is never burned', async () => {
  const slow = [envelope({ test_sleep_ms: 400 }), envelope({ test_sleep_ms: 400 }), envelope({ test_sleep_ms: 400 })];
  const ids = [];
  for (const p of slow) {
    const r = await req('POST', '/jobs', { type: 'tsws_repair', params: p });
    assert.strictEqual(r.status, 202, JSON.stringify(r.body));
    ids.push(r.body.id);
  }
  const extra = envelope();
  const r = await req('POST', '/jobs', { type: 'tsws_repair', params: extra });
  assert.strictEqual(r.status, 503, JSON.stringify(r.body));
  assert.ok(/queue is full/.test(r.body.error));
  assert.ok(!fs.existsSync(path.join(ROOT, 'repair', extra.envelope_id)), 'a refused submit claimed the envelope');
  for (const id of ids) assert.strictEqual((await poll(id)).status, 'done');
  const again = await req('POST', '/jobs', { type: 'tsws_repair', params: extra });
  assert.strictEqual(again.status, 202, 'the refused envelope could not be submitted once the queue drained');
  assert.strictEqual((await poll(again.body.id)).status, 'done');
});
t('an unconfigured box answers 503 at submit, and claims nothing', async () => {
  const p = envelope();
  setEnv({ TSWS_REPAIR_CACHE_ROOT: null });
  try {
    const r = await req('POST', '/jobs', { type: 'tsws_repair', params: p });
    assert.strictEqual(r.status, 503);
    assert.ok(/BLOCKED_CONFIGURATION/.test(r.body.error));
  } finally { setEnv(); }
  assert.ok(!fs.existsSync(path.join(ROOT, 'repair', p.envelope_id)));
});

(async () => {
  await new Promise(r => server.listen(0, '127.0.0.1', r));
  BASE = `http://127.0.0.1:${server.address().port}`;
  for (const [name, fn] of QUEUE) {
    if (!fn) { console.log(name); continue; }
    try { await fn(); pass++; console.log('  ok   ' + name); }
    catch (e) { fail++; console.log('  FAIL ' + name + '\n       ' + String(e && e.message || e).split('\n')[0]); }
  }
  server.close();
  for (const d of [ROOT, PKG, CACHE]) fs.rmSync(d, { recursive: true, force: true });
  console.log(`\n${pass} passed, ${fail} failed`);
  process.exit(fail ? 1 : 0);
})();
