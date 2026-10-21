import test from "node:test";
import assert from "node:assert/strict";
import { createHmac } from "node:crypto";
import { prepareEcosystemReview, verifyEcosystemReview,
  ECOSYSTEM_QUALITY_POLICY } from "./ecosystem_review_gate.mjs";

const SECRET = "fixture-only-do-not-use-this-for-real-reviews-2026";
const brandInputs = [
  ["TQO","TQO"], ["NCO", "NCO_FORGE"], ["NCO_FORGE","NCO_FORGE"],
  ["TSWS","TSWS"], ["ACX","ACX"], ["EditForge","EDITFORGE"],
  ["WhatBroke","WHATBROKE"], ["DEVON","DEVON"],
  ["Meta Supreme X","META_SUPREME_X"],
];
const prepare = brand => prepareEcosystemReview({
  brand, finalArtifact: "An example final artifact, including exact punctuation.",
  rubricRef: "quality-rubric-v90", brandRulesRef: "example-canon-v2",
  canonRef: "locked-story-canon-v2", evidenceRefs: ["checked-source-receipt-1"],
});
function signed(packet, score=90) {
  const payload = {
    policyVersion: packet.policyVersion, brand: packet.brand,
    finalArtifactSha256: packet.finalArtifactSha256, packetId: packet.packetId,
    rubricRef: packet.rubricRef, brandRulesRef: packet.brandRulesRef,
    verifierRole: "independent-review-verifier",
    verifierId: "synthetic-verifier-not-usable-in-production",
    verifiedAt: "2026-10-19T21:00:00.000Z",
    qualityReview: { score, verdict: "PASS", hardFailures: [],
      criticalOrHigh: 0, voiceVerified: true, brandRulesVerified: true,
      factualFidelityVerified: true },
    evidenceReceipt: { verified: true, finalArtifactSha256: packet.finalArtifactSha256 },
    canonReceipt: { verified: true, canonRef: packet.requiredCanon,
      finalArtifactSha256: packet.finalArtifactSha256 },
  };
  return { payload,
    signature: createHmac("sha256", SECRET).update(JSON.stringify(payload)).digest("hex") };
}
function check(packet, attestation=signed(packet)) {
  return verifyEcosystemReview({ packet, signedReturn: attestation, signingSecret: SECRET });
}
const resign = attestation => {
  attestation.signature = createHmac("sha256", SECRET)
    .update(JSON.stringify(attestation.payload)).digest("hex");
  return attestation;
};

test("all registered ecosystem brands hold 89 and meet the numeric floor at exactly 90", () => {
  assert.equal(ECOSYSTEM_QUALITY_POLICY.minScore, 90);
  for (const [label, normalized] of brandInputs) {
    const p = prepare(label);
    assert.equal(p.brand, normalized);
    assert.equal(check(p, signed(p, 89)).state, "HOLD", label + " 89");
    const result = check(p, signed(p, 90));
    assert.equal(result.state, "READY_FOR_EXISTING_GATES", label);
    assert.equal(result.humanApprovalRequired, true);
    assert.notEqual(result.state, "RELEASE_ELIGIBLE");
  }
});
test("a score of 100 cannot override hard blockers or absent source verification", () => {
  for (const label of ["TQO","NCO","TSWS","ACX","WhatBroke"]) {
    const p = prepare(label);
    const hard = signed(p, 100);
    hard.payload.qualityReview.hardFailures.push("invented claim or broken canon");
    assert.equal(check(p, resign(hard)).state, "HOLD");
    const critical = signed(p, 100);
    critical.payload.qualityReview.criticalOrHigh = 1;
    assert.equal(check(p, resign(critical)).state, "HOLD");
    const noSources = signed(p, 100);
    noSources.payload.evidenceReceipt.verified = false;
    assert.equal(check(p, resign(noSources)).state, "HOLD");
  }
});
test("locked TSWS/ACX canon receipts remain mandatory after lowering the score floor", () => {
  for (const label of ["TSWS","ACX"]) {
    const p = prepare(label);
    const a = signed(p);
    delete a.payload.canonReceipt;
    assert.equal(check(p, resign(a)).state, "HOLD");
    assert.throws(() => prepareEcosystemReview({
      brand: label, finalArtifact:"story", rubricRef:"r", brandRulesRef:"b",
      evidenceRefs:["source"], 
    }), /locked story canon/);
  }
});
test("modified final text, packet binding, forged signature and stale rubric always hold", () => {
  const p = prepare("TQO");
  const a = signed(p);
  assert.equal(check({ ...p, finalArtifact: p.finalArtifact+" Extra." }, a).state, "HOLD");
  const stale = signed(p);
  stale.payload.rubricRef = "old-rubric-v99";
  assert.equal(check(p, resign(stale)).state, "HOLD");
  const forged = signed(p);
  forged.payload.qualityReview.score = 100;
  assert.equal(check(p, forged).state, "HOLD");
  assert.equal(check(p, null).state, "HOLD");
});
test("unregistered brands and fabricated self-signed roles fail closed", () => {
  assert.throws(() => prepare("new-unknown-brand"), /unregistered brand/);
  const p = prepare("EditForge");
  const a = signed(p);
  a.payload.verifierRole = "model-self-attested";
  assert.equal(check(p, resign(a)).state, "HOLD");
});
test("invalid score types, missing approval fields and empty evidence hold", () => {
  const p = prepare("DEVON");
  for (const score of ["90", NaN, 89.9, -1, 101, undefined]) {
    const a = signed(p);
    a.payload.qualityReview.score = score;
    assert.equal(check(p, resign(a)).state, "HOLD", String(score));
  }
  const absent = signed(p);
  delete absent.payload.qualityReview.voiceVerified;
  assert.equal(check(p, resign(absent)).state, "HOLD");
  assert.throws(() => prepareEcosystemReview({
    brand:"DEVON",finalArtifact:"output",rubricRef:"r",
    brandRulesRef:"b",evidenceRefs:[]
  }), /evidence references/);
});
