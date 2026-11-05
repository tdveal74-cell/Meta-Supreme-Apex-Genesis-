const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const html = fs.readFileSync(path.join(__dirname, '../../deploy/soul/console.html'), 'utf8');
const source = html.split('/* LIVE_RUNTIME_STATUS_BEGIN */')[1].split('/* LIVE_RUNTIME_STATUS_END */')[0];
const canonical = 'https://n8n.editforge.online';
function fixture(options = {}) {
  const session = {token: options.noAuth ? '' : 'synthetic-session-secret'};
  const eventElement = () => ({handlers: {}, addEventListener(type, handler) {this.handlers[type] = handler;}});
  const calls = [], elements = {runtimeRead: {disabled: false}, runtimeOutput: {textContent: ''}, runtimePanel: {}, signForm: eventElement(), soulSave: eventElement()};
  const bodies = {
    '/api/v1/auth/me': {id: 'd98b5ca9-7142-4df2-8d38-353d70102bd9', email: 'private-never-render'},
    '/api/v1/intelligence/status': {provider: 'gemini', model: 'gemini-3.8-flash', simulated: false, token: 'private-never-render'},
    '/api/v1/n8n/workflows': {source: canonical, state: 'ok', read_only: true, complete: true, counts: {observed: 1, active_observed: 1}, workflows: [{id: 'wf1', active: true}]},
    '/api/v1/n8n/executions?limit=1': {instances: [{state: 'ok', host: canonical, status_code: 200, recent: ['private-never-render']}]},
    ...options.bodies
  };
  const context = {module: {exports: {}}, onVercelSoulHost: () => Boolean(options.soul), operatorJwt: () => session.token, $: id => elements[id], fetch: async (url, init) => {
    calls.push({url, init});
    if (options.fetch) return options.fetch(url, init, bodies);
    return {status: 200, json: async () => bodies[url]};
  }};
  vm.runInNewContext(source + '\nmodule.exports={client:LiveRuntimeStatus,wire:wireLiveRuntimeStatus};', context);
  return {client: context.module.exports.client, wire: context.module.exports.wire, calls, elements, session};
}
test('four fixed same-origin GETs use the existing session and render only safe summaries', async () => {
  const f = fixture(); await f.client.act();
  assert.deepEqual(f.calls.map(x => x.url), ['/api/v1/auth/me', '/api/v1/intelligence/status', '/api/v1/n8n/workflows', '/api/v1/n8n/executions?limit=1']);
  for (const {init} of f.calls) {
    assert.equal(init.method, 'GET'); assert.equal(init.mode, 'same-origin'); assert.equal(init.redirect, 'error');
    assert.equal(init.credentials, 'omit'); assert.equal(init.cache, 'no-store');
    assert.equal(init.headers.Authorization, 'Bearer synthetic-session-secret'); assert.equal(init.body, undefined);
  }
  const out = f.elements.runtimeOutput.textContent;
  assert.match(out, /gemini \/ gemini-3\.8-flash/); assert.match(out, /Configuration only, no inference test/);
  assert.match(out, /complete=true; observed=1; active=1/); assert.doesNotMatch(out, /private-never-render|synthetic-session-secret/);
});
test('missing authentication makes no request', async () => {
  const f = fixture({noAuth: true}); await f.client.act(); assert.equal(f.calls.length, 0); assert.match(f.elements.runtimeOutput.textContent, /Sign in/);
});
test('soul-host credentials cannot reach platform metadata', async () => {
  const f = fixture({soul: true}); await f.client.act(); assert.equal(f.calls.length, 0); assert.match(f.elements.runtimeOutput.textContent, /platform operator/);
});
test('caller-controlled and prototype routes are refused', async () => {
  const f = fixture(); for (const kind of ['https://attacker.example', '__proto__', 'constructor']) await assert.rejects(f.client.request(kind));
  assert.equal(f.calls.length, 0);
});
test('refusal bodies and transport errors cannot leak to the page', async () => {
  const f = fixture({fetch: async () => ({status: 503, json: async () => {throw Error('secret-body-must-not-be-read');}})});
  await f.client.act(); assert.match(f.elements.runtimeOutput.textContent, /HTTP 503/); assert.doesNotMatch(f.elements.runtimeOutput.textContent, /secret/);
  const broken = fixture({fetch: async () => {throw Error('synthetic-session-secret');}}); await broken.client.act();
  assert.doesNotMatch(broken.elements.runtimeOutput.textContent, /synthetic-session-secret/); assert.equal(broken.calls.length, 4);
});
test('partial, malformed and mismatched inventory are never complete successes', () => {
  const {client} = fixture(); const base = {source: canonical, read_only: true, state: 'partial', complete: false, counts: {observed: 0, active_observed: 0}, workflows: []};
  assert.match(client.summary('inventory', {status: 200, body: base}), /partial; complete=false/);
  for (const body of [{...base, state: 'ok'}, {...base, source: 'https://old.n8n.cloud'}, {...base, counts: {observed: -1, active_observed: 0}}, {...base, counts: {observed: 2, active_observed: 0}}, {...base, read_only: false}]) {
    assert.equal(client.summary('inventory', {status: 200, body}), 'n8n inventory: response unverified.');
  }
});
test('wrong telemetry hosts and multiple instances are withheld', () => {
  const {client} = fixture(); for (const instances of [[{host: 'https://old.n8n.cloud', state: 'ok', status_code: 200}], [{host: canonical, state: 'ok'}, {host: canonical, state: 'ok'}]]) {
    assert.equal(client.summary('telemetry', {status: 200, body: {instances}}), 'n8n connection: response unverified.');
  }
});
test('overlapping clicks do not duplicate reads', async () => {
  let release; let first = true;
  const f = fixture({fetch: async (url, init, bodies) => { if (first) { first = false; await new Promise(resolve => {release = resolve;}); } return {status: 200, json: async () => bodies[url]}; }});
  const pending = f.client.act(); await f.client.act(); assert.equal(f.calls.length, 1); release(); await pending;
  assert.equal(f.calls.length, 4); assert.equal(f.elements.runtimeRead.disabled, false);
});

test('token changes during a read discard the complete observation', async () => {
  let f;
  f = fixture({fetch: async (url, init, bodies) => ({status: 200, json: async () => {if (url === '/api/v1/auth/me') f.session.token = 'other-session-secret'; return bodies[url];}})});
  await f.client.act(); assert.equal(f.calls.length, 1);
  assert.match(f.elements.runtimeOutput.textContent, /Session changed/);
  assert.doesNotMatch(f.elements.runtimeOutput.textContent, /d98b5ca9|gemini|other-session-secret/);
});
test('a late session change cannot relabel already-read rows', async () => {
  let f;
  f = fixture({fetch: async (url, init, bodies) => ({status: 200, json: async () => {if (url.includes('executions')) f.session.token = ''; return bodies[url];}})});
  await f.client.act(); assert.match(f.elements.runtimeOutput.textContent, /Session changed/);
  assert.doesNotMatch(f.elements.runtimeOutput.textContent, /d98b5ca9|gemini/);
});
test('sign-in and credential-save events clear prior observations', async () => {
  const f = fixture(); f.wire(); await f.client.act();
  assert.match(f.elements.runtimeOutput.textContent, /gemini/);
  f.elements.signForm.handlers.submit(); assert.match(f.elements.runtimeOutput.textContent, /Session changed/);
  await f.client.act(); f.elements.soulSave.handlers.click(); assert.match(f.elements.runtimeOutput.textContent, /Session changed/);
});

test('inventory failures render only fixed public reasons', () => {
  const {client} = fixture();
  const body = {source: canonical, read_only: true, state: 'failed', complete: false, counts: {observed: 0, active_observed: 0}, workflows: [], error: 'inventory response exceeded byte bound'};
  assert.match(client.summary('inventory', {status: 200, body}), /Reason: inventory response exceeded byte bound/);
  const hostile = client.summary('inventory', {status: 200, body: {...body, error: 'private-provider-body-synthetic-session-secret'}});
  assert.doesNotMatch(hostile, /private-provider|synthetic-session-secret/);
});
