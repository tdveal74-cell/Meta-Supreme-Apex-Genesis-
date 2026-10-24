'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const { test } = require('node:test');
const path = require('node:path');
const root = path.resolve(__dirname, '../..');
const html = fs.readFileSync(path.join(root, 'deploy/soul/console.html'), 'utf8');
const block = html.split('/* ARF_PANEL_START:')[1].split('/* ARF_PANEL_END */')[0];
const script = '/* ARF_PANEL_START:' + block + '\nglobalThis.panel = ArfPanel; globalThis.wire = wireArfPanel;';
function element() {
  return { value: '', textContent: '', disabled: false, children: [],
    appendChild(child) { this.children.push(child); }, replaceChildren() { this.children = []; },
    set innerHTML(_) { throw new Error('HTML rendering is forbidden'); } };
}
function setup(handler = async () => response(200, []), signedIn = true, soul = false) {
  const elements = Object.fromEntries(['arfTasks','arfTaskId','arfLoad','arfRead','arfBurst','arfOutput'].map(k => [k,element()]));
  let calls = [];
  const context = vm.createContext({ $, document: {createElement:element},
    operatorJwt: () => signedIn ? 'test-credential' : '', onVercelSoulHost: () => soul,
    Soul: {headers: () => ({ Authorization: 'Bearer test-credential', Accept: 'application/json' })},
    performance, fetch: async (...args) => { calls.push(args); return handler(...args); } });
  function $(id) { return elements[id]; }
  vm.runInContext(script, context);
  context.wire();
  return { panel: context.panel, elements, calls };
}
function response(status, body, retry = null) {
  return {status, ok:status >= 200 && status < 300, headers:{get:() => retry}, json:async () => body};
}
function diagnostic(verdict = 'WOULD_HOLD') {
  return {domain:'devon', workflow_stage:'build', scope:'read_only_shadow_observation_not_execution_authority',
    verdict, blocking_reasons:['missing'], evidence_refs:['ref'], private_output:'DO_NOT_DISPLAY'};
}
test('the canonical and deployed consoles stay byte identical', () => {
  assert.equal(html, fs.readFileSync(path.join(root, 'docs/devon/assets/SYS_OPS_devon-console_v10_2026-09-01.html'), 'utf8'));
  for (const id of ['arfTasks','arfTaskId','arfLoad','arfRead','arfBurst','arfOutput']) assert.match(html, new RegExp('id="' + id + '"'));
  assert.match(html, /wireArfPanel\(\);/);
});
test('missing authentication and soul host refuse before fetching', async () => {
  for (const [signedIn,soul] of [[false,false],[true,true]]) {
    const s = setup(undefined,signedIn,soul);
    s.elements.arfTaskId.value='task';
    for (const kind of ['load','read','burst']) await s.panel.act(kind);
    assert.equal(s.calls.length,0);
    assert.equal(s.elements.arfRead.disabled,false);
  }
});
test('list and selection use task_id and only fixed same-origin GET', async () => {
  const s = setup(async () => response(200,[{task_id:'<img src=x onerror=bad>',goal:'DO_NOT_DISPLAY'}, {id:'wrong-shape'}]));
  await s.elements.arfLoad.onclick();
  assert.equal(s.calls.length,1);
  assert.equal(s.calls[0][0],'/api/v1/agent-tasks?limit=50');
  assert.equal(s.elements.arfTasks.children.length,2);
  assert.equal(s.elements.arfTasks.children[1].textContent,'<img src=x onerror=bad>');
  s.elements.arfTasks.value='selected-id';s.elements.arfTasks.onchange();
  assert.equal(s.elements.arfTaskId.value,'selected-id');
  const options=s.calls[0][1];
  assert.equal(options.method,'GET');assert.equal(options.redirect,'error');assert.equal(options.cache,'no-store');
  assert.equal(options.credentials,'same-origin');assert.equal(options.headers.Authorization,'Bearer test-credential');
  assert.ok(!s.elements.arfOutput.textContent.includes('DO_NOT_DISPLAY'));
});
test('diagnostic encodes IDs and renders only fixed summary', async () => {
  const s = setup(async () => response(200,diagnostic()));
  s.elements.arfTaskId.value='a/b?x=#z';await s.elements.arfRead.onclick();
  assert.equal(s.calls[0][0],'/api/v1/agent-tasks/a%2Fb%3Fx%3D%23z/reliability-shadow');
  assert.match(s.elements.arfOutput.textContent,/HTTP 200: WOULD_HOLD/);
  assert.ok(!s.elements.arfOutput.textContent.includes('DO_NOT_DISPLAY'));
  for (const verdict of ['IN_PROGRESS','WOULD_BE_ELIGIBLE_FOR_CLOSURE']) {
    assert.match(s.panel.summary({status:200,body:diagnostic(verdict)}),new RegExp(verdict));
  }
});
test('invalid IDs do not send requests', async () => {
  const s=setup();
  for (const id of ['', '.', '..', 'x'.repeat(101), '\n']) {
    s.elements.arfTaskId.value=id; await s.panel.act('read');
  }
  assert.equal(s.calls.length,0);
});
test('HTTP errors never render arbitrary response bodies', async () => {
  for (const code of [401,404,409,429,503]) {
    const s=setup(async () => response(code,{detail:'SECRET_OR_HTML'},code===429?'2':null));
    s.elements.arfTaskId.value='task';await s.panel.act('read');
    assert.match(s.elements.arfOutput.textContent,new RegExp('HTTP '+code));
    assert.ok(!s.elements.arfOutput.textContent.includes('SECRET_OR_HTML'));
    if(code===404) assert.match(s.elements.arfOutput.textContent,/not proof of cross-account/);
    if(code===429) assert.match(s.elements.arfOutput.textContent,/Retry-After: 2/);
  }
});
test('malformed success, unsupported verdict and network errors fail closed', async () => {
  for(const body of [null, {}, {...diagnostic(),verdict:'APPROVED'}, {...diagnostic(),domain:'tsws'}]) {
    const s=setup(async()=>response(200,body));s.elements.arfTaskId.value='task';await s.panel.act('read');
    assert.match(s.elements.arfOutput.textContent,/not a valid diagnostic/);
  }
  const s=setup(async()=>{throw new Error('PRIVATE NETWORK DETAIL');});
  await s.panel.act('load');assert.match(s.elements.arfOutput.textContent,/did not complete/);
  assert.ok(!s.elements.arfOutput.textContent.includes('PRIVATE'));
});
test('burst is six concurrent reads, no retries, and duplicate clicks cannot overlap', async () => {
  let release;const gate=new Promise(r=>release=r);let index=0;
  const s=setup(async()=>{const status=++index===6?429:404;await gate;return response(status,null,status===429?'2':null);});
  s.elements.arfTaskId.value='test-task';
  const run=s.elements.arfBurst.onclick();
  assert.equal(s.calls.length,6);assert.equal(s.elements.arfBurst.disabled,true);
  await s.panel.act('burst');assert.equal(s.calls.length,6);
  release();await run;assert.equal(s.calls.length,6);
  assert.match(s.elements.arfOutput.textContent,/6\. HTTP 429/);
  assert.match(s.elements.arfOutput.textContent,/Retry-After: 2/);
  assert.equal(s.elements.arfBurst.disabled,false);
});
