import test from "node:test";
import assert from "node:assert/strict";
import { generateKeyPairSync, sign } from "node:crypto";
import { prepareEcosystemReview } from "./ecosystem_review_gate.mjs";
import { verifyPublicKeyReview } from "./public_key_review_verifier.mjs";

const keys = generateKeyPairSync("ed25519");
const TRUST = Object.freeze({
  independent1: {
    issuerId: "source-review-office",
    publicKeyPem: keys.publicKey.export({type:"spki",format:"pem"}),
  }
});
const make = brand => prepareEcosystemReview({
  brand, finalArtifact:"Synthetic final text. No real publication.",
  rubricRef:"rubric-v90",brandRulesRef:"brand-canon-v2",
  canonRef:"locked-fiction-v216", evidenceRefs:["synthetic-evidence-source-1"],
});
const envelope = (packet, score=90) => ({
  schemaVersion:"ecosystem-review-ed25519-v1",
  keyId:"independent1", issuerId:"source-review-office",
  issuerRole:"independent-evidence-verifier",
  packetId:packet.packetId, policyVersion:packet.policyVersion,
  brand:packet.brand, finalArtifactSha256:packet.finalArtifactSha256,
  rubricRef:packet.rubricRef, brandRulesRef:packet.brandRulesRef,
  canonRef:packet.requiredCanon, evidenceRefs:[...packet.evidenceRefs],
  producerId:"writer-1", editorialReviewerId:"judge-2",
  evidenceVerifierId:"source-review-office", verifiedAt:"2026-10-19T23:59:00.000Z",
  quality:{score,verdict:"PASS",hardFailures:[],criticalOrHigh:0,
    factualFidelityVerified:true,voiceVerified:true,brandRulesVerified:true},
  evidenceVerified:true, lockedCanonVerified:true,
});
function signed(body, overrideKey=keys.privateKey) {
  const payload=JSON.stringify(body);
  return {keyId:"independent1",payload,
    signature:sign(null,Buffer.from(payload,"utf8"),overrideKey).toString("base64")};
}
const check=(packet,attestation)=>verifyPublicKeyReview({
  packet,attestation,trustedKeys:TRUST,
});
const resign = payload => signed(payload);

test("public-key-only contract applies 89/90 to TQO, NCO, TSWS, ACX, EditForge, WhatBroke, DEVON",()=>{
  for(const brand of ["TQO","NCO","TSWS","ACX","EditForge","WhatBroke","DEVON","Meta Supreme X"]){
    const packet=make(brand);
    assert.equal(check(packet,signed(envelope(packet,89))).state,"HOLD",brand+" 89");
    const pass=check(packet,signed(envelope(packet,90)));
    assert.equal(pass.state,"READY_FOR_EXISTING_GATES",brand+" 90");
    assert.equal(pass.humanApprovalRequired,true);
    assert.equal(check(packet,signed(envelope(packet,100))).state,"READY_FOR_EXISTING_GATES");
  }
});
test("issuer private key is never required by verifier and fake signatures fail",()=>{
  const packet=make("TQO"), att=signed(envelope(packet));
  assert.equal(check(packet,att).state,"READY_FOR_EXISTING_GATES");
  const tampered=structuredClone(att);
  tampered.payload=tampered.payload.replace('"score":90','"score":100');
  assert.equal(check(packet,tampered).state,"HOLD");
  const other=generateKeyPairSync("ed25519");
  assert.equal(check(packet,signed(envelope(packet),other.privateKey)).state,"HOLD");
  assert.equal(check(packet,{...att,keyId:"unknown"}).state,"HOLD");
});
test("changed artifact, changed rubric, changed source references always hold",()=>{
  const packet=make("TSWS"), att=signed(envelope(packet));
  assert.equal(check({...packet,finalArtifact:packet.finalArtifact+" Edited."},att).state,"HOLD");
  assert.equal(check({...packet,rubricRef:"rubric-v99"},att).state,"HOLD");
  assert.equal(check({...packet,evidenceRefs:["different-source"]},att).state,"HOLD");
  assert.equal(check({...packet,requiredCanon:"new-canon"},att).state,"HOLD");
});
test("a valid signature cannot pass hard failures, incomplete evidence or unresolved criticals",()=>{
  const packet=make("ACX");
  for(const change of [
    p=>p.quality.hardFailures.push("fabricated claim"),
    p=>p.quality.criticalOrHigh=1,
    p=>p.quality.voiceVerified=false,
    p=>p.quality.brandRulesVerified=false,
    p=>p.quality.factualFidelityVerified=false,
    p=>p.evidenceVerified=false,
    p=>p.lockedCanonVerified=false,
    p=>p.quality.score=NaN,
    p=>p.quality.score="90",
    p=>p.quality.score=undefined,
  ]){
    const payload=envelope(packet,100);change(payload);
    assert.equal(check(packet,resign(payload)).state,"HOLD");
  }
});
test("independent identities and signer role are mandatory",()=>{
  const packet=make("TQO");
  for(const change of [
    p=>p.evidenceVerifierId=p.producerId,
    p=>p.editorialReviewerId=p.producerId,
    p=>p.editorialReviewerId=p.evidenceVerifierId,
    p=>p.issuerRole="self-graded-model",
    p=>p.evidenceVerifierId="another-issuer",
    p=>p.issuerId="unknown-verifier",
  ]){
    const payload=envelope(packet);change(payload);
    assert.equal(check(packet,resign(payload)).state,"HOLD");
  }
});
test("no release authorization exists in a passing public-key proof",()=>{
  const packet=make("NCO"), result=check(packet,signed(envelope(packet)));
  assert.equal(result.state,"READY_FOR_EXISTING_GATES");
  assert.equal(Object.hasOwn(result,"releaseEligible"),false);
  assert.equal(Object.hasOwn(result,"approval"),false);
});
