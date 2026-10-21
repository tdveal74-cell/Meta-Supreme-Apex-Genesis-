import test from "node:test";
import assert from "node:assert/strict";
import { buildDevonBot90Candidates,DEVON_BOT_CAPTURE } from "./live_devon_bot_universal90_candidate.mjs";

test("captures two exact DEVON bot workflow and Code node snapshots",()=>{
  assert.equal(DEVON_BOT_CAPTURE.record.id,"MmFNWeewHEuG5x8T");
  assert.equal(DEVON_BOT_CAPTURE.repurpose.id,"wXl6p7hKN74lKH0e");
  for(const item of Object.values(DEVON_BOT_CAPTURE)){
    assert.match(item.exportSha256,/^[a-f0-9]{64}$/);
    assert.match(item.codeSha256,/^[a-f0-9]{64}$/);
    assert.ok(item.nodeCount>0);
  }
});
test("refuses missing, tampered, or unrelated exports without best-effort changes",()=>{
  for(const [a,b] of [["",""],["{}","{}"],["not-json","not-json"]]){
    assert.throws(()=>buildDevonBot90Candidates(a,b),/HOLD: live DEVON bot export fingerprint mismatch/);
  }
});
