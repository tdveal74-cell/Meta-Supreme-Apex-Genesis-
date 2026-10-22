import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync, readdirSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { randomUUID } from 'node:crypto';
import { Readable } from 'node:stream';
import { createServer, request } from 'node:http';
import { BrowserWorker, handlerFor } from './worker.mjs';
import { rendererSandboxEvidence } from './sandbox-proof.mjs';
import { ChromePipe } from './chrome-pipe.mjs';
const owner = randomUUID(), session = randomUUID();
function payload(action, overrides = {}) { return { protocol: 'devon-browser-v1', owner_id: owner,
  session_id: session, request_id: 'REQ-' + randomUUID().replaceAll('-', '').toUpperCase(),
  approval_binding: 'a'.repeat(64), allowed_hosts: ['example.org'], action, ...overrides }; }
function setup() {
  const root = mkdtempSync(join(tmpdir(), 'devon-worker-')); const calls = [];
  const factory = profile => ({ async open() { calls.push(['open', profile]); },
    async snapshot() { calls.push(['snapshot']); return Buffer.from('fixture-png'); }, close() { calls.push(['close']); } });
  const config = { owner, key: 'x'.repeat(32), root, browserFactory: factory };
  return { root, calls, config, worker: new BrowserWorker(config), cleanup() { rmSync(root, { recursive: true, force: true }); } };
}

test('auth, owner and strict action contracts refuse before browser creation', async () => {
  const f = setup(); try {
    assert.equal(f.worker.authenticated('Bearer ' + 'x'.repeat(32)), true);
    assert.equal(f.worker.authenticated('Bearer incorrect'), false);
    for (const changes of [{ owner_id: randomUUID() }, { action: 'shell' }, { session_id: '../tee' }, { command: 'rm' }])
      await assert.rejects(f.worker.action(payload('open', changes)));
    assert.deepEqual(f.calls, []);
  } finally { await f.worker.shutdown(); f.cleanup(); }
});

test('blank open snapshot close are owned; duplicate action returns saved receipt', async () => {
  const f = setup(); try {
    const open = payload('open'); const result = await f.worker.action(open);
    assert.equal(result.state, 'completed'); assert.equal(result.network_policy, 'deny-all-v1');
    assert.deepEqual(await f.worker.action(open), result); assert.equal(f.calls.length, 1);
    assert.ok(f.calls[0][1].startsWith(join(f.root, owner, session, 'profile')));
    await assert.rejects(f.worker.action({ ...open, action: 'close' }));
    assert.equal((await f.worker.action(payload('snapshot', { session_id: randomUUID() }))).state, 'refused');
    const shot = await f.worker.action(payload('snapshot'));
    assert.equal(shot.state, 'completed');
    assert.deepEqual(readdirSync(join(f.root, owner, session, 'snapshots')), [shot.receipt_id + '.png']);
    assert.equal((await f.worker.action(payload('close'))).state, 'completed');
    assert.equal((await f.worker.action(payload('open'))).state, 'refused', 'closed UUID cannot reopen an old profile');
  } finally { await f.worker.shutdown(); f.cleanup(); }
});

test('all navigation refused without browser command even with allowed public host', async () => {
  const f = setup(); try {
    for (const url of ['https://example.org/', 'https://127.0.0.1/', 'http://169.254.169.254/', 'wss://example.org/', 'file:///etc/passwd']) {
      const result = await f.worker.action(payload('navigate', { url })); assert.equal(result.state, 'refused');
    }
    assert.deepEqual(f.calls, []);
  } finally { await f.worker.shutdown(); f.cleanup(); }
});

test('crash claim persists; restart never repeats ambiguous browser action or reuses profile', async () => {
  const f = setup(); const open = payload('open');
  f.worker.db.prepare('INSERT INTO requests(id,digest) VALUES (?,?)').run(open.request_id,
    (await import('node:crypto')).createHash('sha256').update(JSON.stringify(Object.fromEntries(Object.keys(open).sort().map(k => [k, open[k]])))).digest('hex'));
  await f.worker.shutdown(); const restarted = new BrowserWorker(f.config);
  try { assert.equal((await restarted.action(open)).state, 'unknown'); assert.deepEqual(f.calls, []); }
  finally { await restarted.shutdown(); f.cleanup(); }
});

test('browser failure records unknown once and redacts exceptions', async () => {
  const f = setup(); f.worker.factory = () => ({ async open() { throw new Error('PRIVATE KEY'); }, close() {} });
  try { const open = payload('open'); const first = await f.worker.action(open);
    assert.equal(first.state, 'unknown'); assert.ok(!JSON.stringify(first).includes('PRIVATE'));
    assert.deepEqual(await f.worker.action(open), first);
  } finally { await f.worker.shutdown(); f.cleanup(); }
});

test('real sandboxed Chromium opens blank and captures PNG through CDP pipe', { skip: !process.env.DEVON_TEST_CHROMIUM }, async () => {
  const root = mkdtempSync(join(tmpdir(), 'devon-chrome-'));
  const browser = new ChromePipe(process.env.DEVON_TEST_CHROMIUM, root);
  try { await browser.open(); const png = await browser.snapshot();
    assert.equal(png.subarray(0, 8).toString('hex'), '89504e470d0a1a0a');
    assert.ok(rendererSandboxEvidence().renderer_user_namespace_differs);
    await browser.close();
    assert.equal(browser.groupAlive(), false);
    assert.ok(browser.process.exitCode !== null || browser.process.signalCode !== null);
  } finally { await browser.close(); rmSync(root, { recursive: true, force: true }); }
});


test('local Unix socket integration authenticates before dispatch and deduplicates lost response', { skip: !process.env.DEVON_TEST_UDS }, async () => {
  const f = setup(); const socket = join(f.root, 'worker.sock'); const server = createServer(handlerFor(f.worker));
  await new Promise(resolve => server.listen(socket, resolve));
  const call = (body, auth) => new Promise((resolve, reject) => {
    const req = request({ socketPath: socket, method: 'POST', path: '/v1/action', headers: { authorization: auth } }, res => {
      let data = ''; res.on('data', chunk => { data += chunk; }); res.on('end', () => resolve({ status: res.statusCode, body: JSON.parse(data) }));
    }); req.on('error', reject); req.end(JSON.stringify(body));
  });
  try {
    const open = payload('open'); assert.equal((await call(open, 'Bearer wrong')).status, 401); assert.equal(f.calls.length, 0);
    const first = await call(open, 'Bearer ' + 'x'.repeat(32)); assert.equal(first.status, 200);
    const second = await call(open, 'Bearer ' + 'x'.repeat(32)); assert.deepEqual(second.body, first.body); assert.equal(f.calls.length, 1);
  } finally { await new Promise(resolve => server.close(resolve)); await f.worker.shutdown(); f.cleanup(); }
});


test('HTTP handler integration authenticates before interpreting local fixture body', async () => {
  const f = setup(); const handle = handlerFor(f.worker);
  async function call(payload, auth) {
    const req = Readable.from([Buffer.from(JSON.stringify(payload))]);
    req.headers = { authorization: auth }; req.method = 'POST'; req.url = '/v1/action';
    const res = { writeHead(status) { this.status = status; }, end(body) { this.body = JSON.parse(body); } };
    await handle(req, res); return res;
  }
  try {
    const open = payload('open'); assert.equal((await call(open, 'wrong')).status, 401); assert.equal(f.calls.length, 0);
    const first = await call(open, 'Bearer ' + 'x'.repeat(32));
    const repeated = await call(open, 'Bearer ' + 'x'.repeat(32));
    assert.deepEqual(repeated.body, first.body); assert.equal(f.calls.length, 1);
  } finally { await f.worker.shutdown(); f.cleanup(); }
});

// This checks preservation of modern baseline restrictions, not just the names
// added for Chromium user namespaces. No old full Playwright profile is used.
test('seccomp preserves every pinned Moby rule and adds only reviewed sandbox rules', () => {
  const base = JSON.parse(readFileSync(new URL('./seccomp-moby-base.json', import.meta.url)));
  const profile = JSON.parse(readFileSync(new URL('./seccomp-browser.json', import.meta.url)));
  assert.deepEqual(profile.syscalls.slice(0, -2), base.syscalls);
  const added = profile.syscalls.at(-2);
  assert.deepEqual(added.names, ['clone', 'setns', 'unshare']); assert.equal(added.action, 'SCMP_ACT_ALLOW');
  assert.deepEqual(profile.syscalls.at(-1).names, ['chroot']);
  assert.equal(profile.syscalls.at(-1).action, 'SCMP_ACT_ALLOW');
  profile.syscalls.pop(); profile.syscalls.pop(); assert.deepEqual(profile, base);
  assert.equal(profile.defaultAction, 'SCMP_ACT_ERRNO');
  assert.ok(!profile.syscalls.some(rule => rule.names.includes('socket') && !rule.args && rule.action === 'SCMP_ACT_ALLOW'));
});

test('SIGKILL socket remains a manual fail-closed restart gate; never auto-unlink', { skip: !process.env.DEVON_TEST_UDS }, async () => {
  const { spawn } = await import('node:child_process');
  const { lstatSync } = await import('node:fs');
  const directory = mkdtempSync(join(tmpdir(), 'devon-stale-')); const socket = join(directory, 'worker.sock');
  const child = spawn(process.execPath, ['--input-type=module', '-e',
    "import{createServer}from'node:http';createServer().listen(process.argv[1],()=>console.log('ready'))", socket], { stdio: ['ignore', 'pipe', 'ignore'] });
  try {
    await new Promise((resolve, reject) => { child.stdout.once('data', resolve); child.once('error', reject); child.once('exit', code => { if (code !== null) reject(new Error('fixture stopped')); }); });
    const exited = new Promise(resolve => child.once('exit', resolve)); child.kill('SIGKILL'); await exited;
    assert.ok(lstatSync(socket).isSocket());
    const restarted = createServer();
    await assert.rejects(new Promise((resolve, reject) => { restarted.once('error', reject); restarted.listen(socket, resolve); }), { code: 'EADDRINUSE' });
    assert.ok(lstatSync(socket).isSocket(), 'no socket/file/symlink removal is performed automatically');
  } finally { child.kill('SIGKILL'); rmSync(directory, { recursive: true, force: true }); }
});

test('real worker UDS blank lifecycle, deny-navigation, PNG receipt and duplicate suppression', {
  skip: !process.env.DEVON_TEST_CHROMIUM || !process.env.DEVON_TEST_UDS,
}, async () => {
  const root = mkdtempSync(join(tmpdir(), 'devon-real-worker-'));
  const worker = new BrowserWorker({ owner, key: 'x'.repeat(32), root, chromium: process.env.DEVON_TEST_CHROMIUM });
  const socket = join(root, 'worker.sock'); const server = createServer(handlerFor(worker));
  await new Promise(resolve => server.listen(socket, resolve));
  const call = body => new Promise((resolve, reject) => {
    const req = request({ socketPath: socket, method: 'POST', path: '/v1/action', headers: { authorization: 'Bearer ' + 'x'.repeat(32) } }, res => {
      let data = ''; res.on('data', chunk => { data += chunk; }); res.on('end', () => resolve(JSON.parse(data)));
    }); req.on('error', reject); req.end(JSON.stringify(body));
  });
  try {
    const open = payload('open'); const opened = await call(open); assert.equal(opened.state, 'completed');
    assert.deepEqual(await call(open), opened);
    const refused = await call(payload('navigate', { url: 'https://example.org/' })); assert.equal(refused.state, 'refused');
    const snapshot = await call(payload('snapshot')); assert.equal(snapshot.state, 'completed');
    const png = readFileSync(join(root, owner, session, 'snapshots', snapshot.receipt_id + '.png'));
    assert.equal(png.subarray(0, 8).toString('hex'), '89504e470d0a1a0a');
    const proof = rendererSandboxEvidence(); assert.ok(proof.renderer_user_namespace_differs);
    console.log('real-worker-sandbox-receipt', JSON.stringify({ ...proof, png_bytes: png.length, navigation: refused.state }));
    assert.equal((await call(payload('close'))).state, 'completed');
  } finally { await new Promise(resolve => server.close(resolve)); await worker.shutdown(); rmSync(root, { recursive: true, force: true }); }
});

test('close records completed only after cleanup promise resolves', async () => {
  const f = setup(); let release; let settled = false;
  try {
    await f.worker.action(payload('open'));
    f.worker.sessions.get(session).close = () => new Promise(resolve => { release = resolve; });
    const request = payload('close');
    const closing = f.worker.action(request).then(result => { settled = true; return result; });
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(settled, false); assert.ok(f.worker.sessions.has(session));
    assert.equal((await f.worker.action(request)).state, 'unknown', 'pending claim never lies about completion');
    release(); const completed = await closing;
    assert.equal(completed.state, 'completed'); assert.equal(f.worker.sessions.has(session), false);
    assert.deepEqual(await f.worker.action(request), completed);
  } finally { await f.worker.shutdown(); f.cleanup(); }
});

test('unproven close remains unknown and duplicate never attempts cleanup again', async () => {
  const f = setup(); let calls = 0;
  try {
    await f.worker.action(payload('open'));
    f.worker.sessions.get(session).close = async () => { calls++; throw new Error('termination unproven'); };
    const request = payload('close'); const result = await f.worker.action(request);
    assert.equal(result.state, 'unknown'); assert.equal(calls, 1);
    assert.deepEqual(await f.worker.action(request), result); assert.equal(calls, 1);
    assert.ok(f.worker.sessions.has(session), 'failed cleanup remains quarantined');
  } finally { await f.worker.shutdown(); f.cleanup(); }
});

test('CDP parser preserves multilingual text across every split UTF-8 byte', { skip: !process.env.DEVON_TEST_CHROMIUM }, async () => {
  const root = mkdtempSync(join(tmpdir(), 'devon-utf8-'));
  const browser = new ChromePipe(process.env.DEVON_TEST_CHROMIUM, root);
  try {
    await browser.open();
    const expected = 'Tee: café, 日本語, العربية, e\u0301, 😀';
    const id = 900001;
    const result = new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('fixture parser timed out')), 1000);
      browser.pending.set(id, { resolve, reject, timer });
    });
    const encoded = Buffer.from(JSON.stringify({ id, result: { value: expected } }) + '\0');
    // Exercise the production data listener. Each emitted chunk is one byte,
    // so every multibyte codepoint crosses actual parser callback boundaries.
    for (const byte of encoded) browser.process.stdio[4].emit('data', Buffer.from([byte]));
    assert.deepEqual(await result, { value: expected });
  } finally { await browser.close(); rmSync(root, { recursive: true, force: true }); }
});

test('one action budget spans sequential CDP commands and expires before dispatch', { skip: !process.env.DEVON_TEST_CHROMIUM }, async () => {
  const root = mkdtempSync(join(tmpdir(), 'devon-budget-'));
  const browser = new ChromePipe(process.env.DEVON_TEST_CHROMIUM, root, { proxy: 'http://10.0.0.2:3128', allowedHosts: ['example.org'] });
  let clock = 0; browser.now = () => clock; browser.beginAction();
  const command = browser.command.bind(browser); let completed = 0;
  browser.command = async (...args) => { const result = await command(...args); completed++; clock += 6000; return result; };
  try {
    await assert.rejects(browser.open(), /deadline/);
    assert.equal(completed, 5, 'five6s commands spend the shared30s budget; the next never dispatches');
    await browser.close(); assert.equal(browser.groupAlive(), false);
  } finally { await browser.close(); rmSync(root, { recursive: true, force: true }); }
});

test('fresh action budget allows snapshot after a long idle session', { skip: !process.env.DEVON_TEST_CHROMIUM }, async () => {
  const root = mkdtempSync(join(tmpdir(), 'devon-idle-'));
  const browser = new ChromePipe(process.env.DEVON_TEST_CHROMIUM, root);
  let clock = 0; browser.now = () => clock; browser.beginAction();
  try {
    await browser.open(); clock = 600000;
    browser.beginAction();
    const png = await browser.snapshot();
    assert.equal(png.subarray(0, 8).toString('hex'), '89504e470d0a1a0a');
  } finally { await browser.close(); rmSync(root, { recursive: true, force: true }); }
});

test('expired action stays busy until cleanup, then persists unknown without replay', async () => {
  const f = setup(); let release; let cleaned = false; let settled = false;
  f.worker.factory = () => ({
    beginAction() {}, async open() {},
    assertActionDeadline() { throw new Error('deadline exceeded'); },
    close() { return new Promise(resolve => { release = () => { cleaned = true; resolve(); }; }); },
  });
  const request = payload('open');
  try {
    const action = f.worker.action(request).then(value => { settled = true; return value; });
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(settled, false); assert.equal(f.worker.busy, true); assert.equal(cleaned, false);
    assert.equal((await f.worker.action(request)).state, 'unknown');
    release(); const result = await action;
    assert.equal(result.state, 'unknown'); assert.equal(cleaned, true); assert.equal(f.worker.busy, false);
    assert.deepEqual(await f.worker.action(request), result);
  } finally { await f.worker.shutdown(); f.cleanup(); }
});

test('worker begins a fresh budget for each supported action including idle snapshot', async () => {
  const f = setup(); let starts = 0; let checks = 0;
  f.worker.factory = () => ({ beginAction() { starts++; }, assertActionDeadline() { checks++; },
    async open() {}, async snapshot() { return Buffer.from('fixture-png'); }, async close() {} });
  try {
    assert.equal((await f.worker.action(payload('open'))).state, 'completed');
    assert.equal((await f.worker.action(payload('snapshot'))).state, 'completed');
    assert.equal((await f.worker.action(payload('close'))).state, 'completed');
    assert.equal(starts, 3); assert.equal(checks, 3);
  } finally { await f.worker.shutdown(); f.cleanup(); }
});
