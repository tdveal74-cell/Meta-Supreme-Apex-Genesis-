import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync, readFileSync, statSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";

const CLI = new URL("./review_handoff_cli.mjs", import.meta.url).pathname;
const SCRIPT = "This confidential final TQO script is a synthetic CLI test.";
test("CLI creates private handoff without leaking script, refuses overwrite or missing signer", () => {
  const dir = mkdtempSync(join(tmpdir(), "tqo-review-cli-"));
  try {
    const input = join(dir, "input.json"), packet = join(dir, "private.json");
    writeFileSync(input, JSON.stringify({ brand:"TQO", script:SCRIPT,
      voiceCardRef:"test-voice-v1", doctorRubricRef:"test-doctor-v90",
      approvedSourceRefs:["synthetic-evidence-1"] }));
    const prepare = spawnSync(process.execPath, [CLI, "prepare", input, packet], { encoding:"utf8" });
    assert.equal(prepare.status, 0, prepare.stderr);
    assert.equal(JSON.parse(prepare.stdout).state, "AWAITING_CHATGPT_REVIEW");
    assert.ok(!prepare.stdout.includes(SCRIPT));
    assert.equal(statSync(packet).mode & 0o777, 0o600);
    assert.equal(JSON.parse(readFileSync(packet, "utf8")).script, SCRIPT);
    const repeat = spawnSync(process.execPath, [CLI, "prepare", input, packet], { encoding:"utf8" });
    assert.notEqual(repeat.status, 0);
    assert.ok(!repeat.stdout.includes(SCRIPT));
    const signed = join(dir, "unsigned.json");
    writeFileSync(signed, JSON.stringify({payload:{},signature:"0".repeat(64)}));
    const verification = spawnSync(process.execPath, [CLI, "verify", packet, signed],
      {encoding:"utf8", env:{...process.env, TQO_REVIEW_SIGNING_SECRET:""}});
    assert.notEqual(verification.status, 0);
    assert.equal(JSON.parse(verification.stdout).state, "HOLD");
    assert.ok(!verification.stdout.includes(SCRIPT));
  } finally { rmSync(dir, { recursive:true, force:true }); }
});
