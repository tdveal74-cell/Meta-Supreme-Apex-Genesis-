import test from "node:test";
import assert from "node:assert/strict";
import { checkScaledAcceptance } from "./scaled_acceptance_floor.mjs";

const assess = (earned, maximum, scorePurpose="acceptance") =>
  checkScaledAcceptance({ earned, maximum, scorePurpose });

test("0-100 boundary: 89 fails and 90 meets only numeric acceptance", () => {
  assert.equal(assess(89,100).state, "HOLD");
  const pass = assess(90,100);
  assert.equal(pass.required, 90);
  assert.equal(pass.state, "MEETS_NUMERIC_FLOOR_ONLY");
  assert.equal(pass.releaseAuthorized, false);
  assert.equal(pass.humanApprovalRequired, true);
});
test("TSWS 0-18 acceptance normalized: 16/18 is under 90 and 17/18 meets only numeric floor", () => {
  assert.equal(assess(15,18).state, "HOLD");
  assert.equal(assess(16,18).state, "HOLD");
  const result = assess(17,18);
  assert.equal(result.required, 17);
  assert.equal(result.state, "MEETS_NUMERIC_FLOOR_ONLY");
});
test("cannot apply acceptance rule to diagnostically scored stages or unrelated metrics", () => {
  for (const purpose of ["diagnostic", "similarity", "confidence", ""])
    assert.equal(assess(18,18,purpose).state, "HOLD");
});
test("invalid numeric and decimal inputs never round upward to passing", () => {
  for (const earned of [89.9, "90", null, NaN, Infinity, -1, 101]) {
    assert.equal(assess(earned,100).state, "HOLD", String(earned));
  }
  assert.equal(assess(10,0).state, "HOLD");
  assert.equal(assess(1.2,18).state, "HOLD");
});
