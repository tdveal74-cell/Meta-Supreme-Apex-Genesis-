import test from "node:test";
import assert from "node:assert/strict";
import { assessTqoDraft, lintTqoText, TQO_SLOP_POLICY } from "./tqo_curator_gate.mjs";

const SHA = "a".repeat(64);
const SCRIPT = "I tested the output, checked the sources, and recorded what the model left out. The next step is to test those gaps.";
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
