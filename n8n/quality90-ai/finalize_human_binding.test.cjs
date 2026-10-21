'use strict';
// Fixtures only. These tests never call n8n, record human approval, or publish.
const test = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const {patchQC, patchRepurpose, patchWorkflow} = require('./finalize_human_binding.cjs');
const hash = text => crypto.createHash('sha256').update(text, 'utf8').digest('hex');
const qcSource = `
const b = $('QC Record In').first().json.body;
const stage=b.stage;
const bad=error=>[{json:{ok:false,error}}];
const fp = (str) => { return String(Math.imul(str.length, 123)); };
const row=(passed,verdict,score,report,script)=>[{json:{ok:true,record:{passed,script_fingerprint:script==null?'':fp(script)}}}];
if (stage === 'human') {
  const reviewRaw = b.humanReview;
  const scriptUnused='not the artifact';
  const disc=String(b.aiDisclosure||'');
  const who=String(b.reviewedBy||'');
  const blockers=[];
  if(reviewRaw!==true||!who||!disc) blockers.push('human review missing');
  return row(blockers.length === 0, blockers.length ? 'BLOCKED' : 'CLEARED', null, (blockers.length ? 'BLOCKED: ' + blockers.join('; ') : 'Human review by ' + who + '. AI disclosure: ' + disc) , null);
}
return row(true,'PASS',90,'fixture numeric stage',b.script);
`;
const repSource = `
const v=$('Validate Handoff').first().json;
const blocks=[];
const finalHash=require('crypto').createHash('sha256').update(v.finalScript||'','utf8').digest('hex');
const {s,q,h}=$input.first().json;
const legacyFp=(str)=>{return String(Math.imul(str.length,123));};
const actualFp=legacyFp(v.finalScript||'');
if(!s||!q||s.script_fingerprint!==actualFp||q.script_fingerprint!==actualFp) blocks.push('script or QC changed');
if (h && h.script_fingerprint !== actualFp) blocks.push('Human approval is not bound to the exact final script');
if(!h||h.passed!==true)blocks.push('human approval missing');
return [{json:{ok:blocks.length===0,blocks}}];
`;
function runQC(body) {
  return new Function('$','$input','require',patchQC(qcSource))(
    ()=>({first:()=>({json:{body}})}),{},require)[0].json;
}
function runRep(script, fingerprint, human=true) {
  const records={s:{script_fingerprint:fingerprint},q:{script_fingerprint:fingerprint},h:{script_fingerprint:fingerprint,passed:human}};
  return new Function('$','$input','require',patchRepurpose(repSource))(
    ()=>({first:()=>({json:{finalScript:script}})}),{first:()=>({json:records})},require)[0].json;
}
const human={stage:'human',humanReview:true,reviewedBy:'test fixture, not a live approval',aiDisclosure:'test disclosure'};
test('human verdict stores the exact final UTF-8 SHA-256',()=>{
  const script='Final fixture text. Café.';
  const result=runQC({...human,script});
  assert.equal(result.record.script_fingerprint,hash(script));
  assert.equal(result.record.passed,true);
});
test('human stage refuses missing, blank, or nonstring scripts',()=>{
  for(const script of [undefined,null,'','  ',42,{}])assert.equal(runQC({...human,script}).ok,false);
});
test('identity binding never supplies human approval',()=>{
  assert.equal(runQC({...human,humanReview:false,script:'fixture'}).record.passed,false);
  assert.equal(runRep('fixture',hash('fixture'),false).ok,false);
});
test('new script and QC stage identities use the same SHA-256',()=>{
  for(const stage of ['script','qc'])assert.equal(runQC({stage,script:'fixture'}).record.script_fingerprint,hash('fixture'));
});
test('repurpose accepts matching SHA-256 and rejects edited or legacy text',()=>{
  assert.equal(runRep('fixture',hash('fixture')).ok,true);
  assert.equal(runRep('fixture edited',hash('fixture')).ok,false);
  assert.equal(runRep('fixture','861').ok,false);
  assert.equal(runRep('fixture','').ok,false);
});
test('patch refuses wrong workflow and unexpected or repeated source',()=>{
  assert.throws(()=>patchQC('changed code'),/drift/);
  assert.throws(()=>patchQC(patchQC(qcSource)),/drift/);
  assert.throws(()=>patchRepurpose('changed code'),/drift/);
  assert.throws(()=>patchWorkflow({id:'unrelated',nodes:[]}),/unsupported/);
});
test('workflow patch preserves graph, credentials and all unrelated nodes',()=>{
  const original={id:'MmFNWeewHEuG5x8T',active:true,settings:{x:1},connections:{a:{main:[]}},nodes:[{name:'Run Gate',parameters:{jsCode:qcSource},credentials:{existing:'reference'}},{name:'Other',parameters:{x:'unchanged'}}]};
  const updated=patchWorkflow(original);
  assert.deepEqual(updated.connections,original.connections);
  assert.deepEqual(updated.settings,original.settings);
  assert.deepEqual(updated.nodes[0].credentials,original.nodes[0].credentials);
  assert.deepEqual(updated.nodes[1],original.nodes[1]);
  assert.equal(original.nodes[0].parameters.jsCode,qcSource);
});
