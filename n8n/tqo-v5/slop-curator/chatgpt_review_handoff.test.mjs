import test from "node:test";
import assert from "node:assert/strict";
import { createHmac } from "node:crypto";
import { prepareChatgptReviewHandoff, verifySignedChatgptReview } from "./chatgpt_review_handoff.mjs";

const SECRET = "synthetic-test-key-this-is-not-a-production-secret";
const SCRIPT = "I compared the tool output with its cited documentation and recorded the omitted caveats.";
const newPacket = () => prepareChatgptReviewHandoff({
  brand: "TQO", script: SCRIPT, voiceCardRef: "idiolect-card-v3",
  doctorRubricRef: "tqo-doctor-v90", approvedSourceRefs: ["synthetic-source-receipt-1"],
});
function signed(packet, score = 90) {
  const hash = packet.scriptSha256;
  const payload = {
    brand: "TQO", packetId: packet.packetId, draftSha256: hash,
    verifierRole: "independent-review-verifier",
    verifierId: "trusted-fixture-only",
    verifiedAt: "2026-10-19T23:00:00.000Z",
    editorial: { schemaVersion: "tqo-slop-v1", draftSha256: hash, score,
      verdict: "PASS", voicePreserved: true, factualFidelity: true, constraintsPassed: true,
      hardFailures: [], reviewFlags: [] },
    scriptDoctor: { draftSha256: hash, score, verdict: "PASS" },
    evidenceReceipt: { draftSha256: hash, verified: true },
  };
  return { payload, signature: createHmac("sha256", SECRET).update(JSON.stringify(payload)).digest("hex") };
}
const verify = (packet, signedReturn) => verifySignedChatgptReview({
  packet, signedReturn, signingSecret: SECRET,
});

test("packet is a non-publishing handoff with exact final script hash and evidence references", () => {
  const packet = newPacket();
  assert.equal(packet.status, "AWAITING_CHATGPT_REVIEW");
  assert.equal(packet.brand, "TQO");
  assert.equal(packet.script, SCRIPT);
  assert.match(packet.packetId, /^[0-9a-f]{64}$/);
  assert.throws(() => prepareChatgptReviewHandoff({
    brand: "TQO", script: SCRIPT, voiceCardRef: "x", doctorRubricRef: "y",
    approvedSourceRefs: [],
  }), /approved source/);
});
test("trusted verified 90-point fixture only advances to existing gates, never release", () => {
  const packet = newPacket();
  const result = verify(packet, signed(packet));
  assert.equal(result.state, "READY_FOR_EXISTING_GATES", JSON.stringify(result));
  assert.equal(result.humanApprovalRequired, true);
  assert.equal(result.reviewVerifier, "trusted-fixture-only");
});
test("signed 89-point return fails, even when other flags are true", () => {
  const packet = newPacket();
  assert.equal(verify(packet, signed(packet, 89)).state, "HOLD");
});
test("unsigned, forged or tampered response always holds", () => {
  const packet = newPacket();
  const response = signed(packet);
  assert.equal(verify(packet, { payload: response.payload, signature: "0".repeat(64) }).state, "HOLD");
  const tampered = structuredClone(response);
  tampered.payload.editorial.score = 100;
  assert.equal(verify(packet, tampered).state, "HOLD");
  assert.equal(verify(packet, null).state, "HOLD");
});
test("modified script cannot reuse signed prior review or a copied packet ID", () => {
  const packet = newPacket();
  const response = signed(packet);
  const changed = { ...packet, script: SCRIPT + " More text." };
  assert.equal(verify(changed, response).state, "HOLD");
  const fresh = prepareChatgptReviewHandoff({
    brand: "TQO", script: SCRIPT + " More text.", voiceCardRef: "idiolect-card-v3",
    doctorRubricRef: "tqo-doctor-v90", approvedSourceRefs: ["synthetic-source-receipt-1"],
  });
  assert.equal(verify(fresh, response).state, "HOLD");
});
test("a valid signature on the wrong brand, role or stale evidence cannot advance", () => {
  const packet = newPacket();
  const wrong = signed(packet);
  wrong.payload.verifierRole = "model-self-attested";
  wrong.signature = createHmac("sha256", SECRET).update(JSON.stringify(wrong.payload)).digest("hex");
  assert.equal(verify(packet, wrong).state, "HOLD");
  const stale = signed(packet);
  stale.payload.evidenceReceipt.draftSha256 = "0".repeat(64);
  stale.signature = createHmac("sha256", SECRET).update(JSON.stringify(stale.payload)).digest("hex");
  assert.equal(verify(packet, stale).state, "HOLD");
});
