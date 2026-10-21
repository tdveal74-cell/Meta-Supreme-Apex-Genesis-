import test from "node:test";
import assert from "node:assert/strict";
import { once, buildContinuityCandidates } from "./live_universal90_continuity_candidate.mjs";

test("guarded offline transformer refuses empty or altered source exports",()=>{
  for(const bad of ["", "[]", "{}", "not json"]) {
    assert.throws(()=>buildContinuityCandidates(bad,bad,bad));
  }
});
test("exact-once repair refuses duplicate or missing anchors",()=>{
  assert.equal(once("foo bar","foo","baz","fixture"),"baz bar");
  assert.throws(()=>once("foo foo","foo","baz","duplicate"),/HOLD/);
  assert.throws(()=>once("bar","foo","baz","absent"),/HOLD/);
});
