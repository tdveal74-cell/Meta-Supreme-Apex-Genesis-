import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { buildLiveUniversal90Candidate, LIVE_V5_CAPTURE } from "./live_v5_universal90_candidate.mjs";

const read = relative => readFileSync(new URL(relative, import.meta.url), "utf8");
const oldExport = read("../exports/qEkGOUsNyVaRAmm6_active.json");

test("live safety capture records the precise export and four gate fingerprints", () => {
  assert.equal(LIVE_V5_CAPTURE.workflowId, "qEkGOUsNyVaRAmm6");
  assert.equal(LIVE_V5_CAPTURE.nodeCount, 274);
  assert.match(LIVE_V5_CAPTURE.exportSha256, /^[a-f0-9]{64}$/);
  assert.deepEqual(Object.keys(LIVE_V5_CAPTURE.nodeCodeSha256), [
    "Script Gate: Quality", "Parse QC + Set Verdict",
    "QC Doctor Gate", "OS 28: Publish Gate",
  ]);
  for (const digest of Object.values(LIVE_V5_CAPTURE.nodeCodeSha256)) {
    assert.match(digest, /^[a-f0-9]{64}$/);
  }
});
test("refuses archived 70/80 export rather than clobber current live 90/99 changes", () => {
  assert.throws(() => buildLiveUniversal90Candidate(oldExport),
    /HOLD: captured live export fingerprint mismatch/);
});
test("rejects manipulated or missing live export instead of best-guess patching", () => {
  for (const raw of ["", "{}", oldExport + " ", oldExport.replace("Script Gate: Quality", "Script Gate Changed")]) {
    assert.throws(() => buildLiveUniversal90Candidate(raw),
      /HOLD: captured live export fingerprint mismatch/);
  }
});
test("captured live SHA differs from superseded repository export", async () => {
  const { createHash } = await import("node:crypto");
  const archivedSha = createHash("sha256").update(oldExport, "utf8").digest("hex");
  assert.notEqual(archivedSha, LIVE_V5_CAPTURE.exportSha256);
});
