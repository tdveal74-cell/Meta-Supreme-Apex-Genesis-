import test from "node:test";
import { createHash } from "node:crypto";
import assert from "node:assert/strict";
import { assessTqoDraft, lintTqoText, TQO_SLOP_POLICY } from "./tqo_curator_gate.mjs";

const SCRIPT = "I tested the output, checked the sources, and recorded what the model left out. The next step is to test those gaps.";
const SHA = createHash("sha256").update(SCRIPT, "utf8").digest("hex");
const clean = () => ({
  brand: "TQO",
  draftSha256: SHA,
  script: SCRIPT,
  editorial: {
    schemaVersion: TQO_SLOP_POLICY.version, draftSha256: SHA,
    score: 90, verdict: "PASS", voicePreserved: true,
    factualFidelity: true, constraintsPassed: true, hardFailures: []
  },
  scriptDoctor: { draftSha256: SHA, score: 90, verdict: "PASS" },
  evidenceReceipt: { draftSha256: SHA, verified: true }
});

test("TQO exactly 90 can proceed only to existing quality and approval gates", () => {
  const outcome = assessTqoDraft(clean());
  assert.equal(outcome.state, "READY_FOR_EXISTING_GATES");
  assert.equal(outcome.humanApprovalRequired, true);
  assert.equal(outcome.threshold, 90);
});
test("89 fails at either score and no automatic release is possible", () => {
  for (const field of ["editorial", "scriptDoctor"]) {
    const input = clean(); input[field].score = 89;
    assert.equal(assessTqoDraft(input).state, "HOLD", field);
  }
});
test("tampered script with unchanged report hashes fails even when scores are 100", () => {
  const input = clean();
  input.script = SCRIPT + " One extra word.";
  input.editorial.score = 100;
  input.scriptDoctor.score = 100;
  const result = assessTqoDraft(input);
  assert.equal(result.state, "HOLD");
  assert.ok(result.failures.includes("trusted final-draft SHA-256 does not match script text"));
});
test("valid-looking invented or stale SHA-256 fails", () => {
  const input = clean();
  const fakeHash = "a".repeat(64);
  input.draftSha256 = fakeHash;
  input.editorial.draftSha256 = fakeHash;
  input.scriptDoctor.draftSha256 = fakeHash;
  input.evidenceReceipt.draftSha256 = fakeHash;
  assert.equal(assessTqoDraft(input).state, "HOLD");
});
test("unscored, out-of-range and string scores cannot pass", () => {
  for (const value of ["99", NaN, 101, -1, undefined]) {
    const input = clean(); input.editorial.score = value;
    assert.equal(assessTqoDraft(input).state, "HOLD", String(value));
  }
});
test("stale or missing hash, doctor verdict, hard failure, or independent source check holds", () => {
  const cases = [
    x => { x.draftSha256 = "not a hash"; },
    x => { x.editorial.draftSha256 = "b".repeat(64); },
    x => { x.scriptDoctor.draftSha256 = "b".repeat(64); },
    x => { x.scriptDoctor.verdict = "UNCHECKED"; },
    x => { x.editorial.hardFailures = ["invented source"]; },
    x => { x.evidenceReceipt.verified = false; },
    x => { delete x.evidenceReceipt; },
    x => { x.editorial.voicePreserved = false; },
    x => { x.editorial.verdict = "REVISE"; }
  ];
  for (const modify of cases) {
    const input = clean(); modify(input);
    assert.equal(assessTqoDraft(input).state, "HOLD");
  }
});
test("ban enforcement does not remove prose or invent replacements", () => {
  const text = "Actually; it's not this, it's that. Free audit linked below.";
  const result = lintTqoText(text);
  assert.ok(result.hardFailures.some(x => x.includes("actually")));
  assert.ok(result.hardFailures.some(x => x.includes("semicolon")));
  assert.ok(result.hardFailures.some(x => x.includes("retired CTA")));
  assert.equal(result.reviewFlags.length, 1);
  assert.ok(lintTqoText(SCRIPT).hardFailures.length === 0);
});
test("TQO gate is brand-specific, never substitutes for TSWS or NCO", () => {
  for (const brand of ["TSWS", "NCO", "NCO_FORGE", "ACX"]) {
    const input = clean(); input.brand = brand;
    assert.equal(assessTqoDraft(input).state, "HOLD");
  }
});
