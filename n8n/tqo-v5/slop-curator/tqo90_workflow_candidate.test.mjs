import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { buildTqo90Candidate } from "./tqo90_workflow_candidate.mjs";

const read = (relative) => readFileSync(new URL(relative, import.meta.url), "utf8");
const pinned = JSON.parse(read("../exports/qEkGOUsNyVaRAmm6_active.json"));
const qcMirror = read("../compliance/qc_doctor_gate.js");
const before = JSON.stringify(pinned);
const { candidate, scriptCode, qcCode } = buildTqo90Candidate(pinned, qcMirror);

const nodes = Object.fromEntries(candidate.nodes.map(n => [n.name, n]));
const originalNodes = Object.fromEntries(pinned.nodes.map(n => [n.name, n]));
const executable = (code) => new Function("$", "$json", "$input", code);
const dollar = (entries) => (name) => {
  if (!(name in entries)) throw Error("unexpected node read: " + name);
  return { first: () => ({ json: entries[name] }) };
};

function scriptGate(show, score) {
  const objective = "Check what this model returned";
  const script = objective + " " + "A useful workplace test starts with a source and a human check. ".repeat(112)
    + "What evidence would you share in the comments?";
  const d = {
    script, title: "The Quiet Test", description: "A careful source check.",
    broll: "desk,screen,report,notebook,team,source",
    learningObjective: objective,
    checklist: ["Compare the source", "Test the output", "Record the gaps"],
    doctorScore: score, doctorVerdict: "PASS",
    rhythmScore: 75, similarityScore: 75,
  };
  const result = executable(scriptCode)(dollar({
    "Build Doctor Prompt": { original: { draftWords: 1300, expansion: "not needed" } },
    "DEVON Recall: Merge": { devonRecallNote: "mock recall, no claims" },
    "Show Context: Script": { show },
  }), d, undefined);
  return result[0].json;
}
function qcGate(brand, score) {
  const out = executable(qcCode)(dollar({
    "One Row at a Time": { fields: { id: 7, updatedAt: "2026-10-19", brand, show: brand,
      score_history: "2026-10-19 | doctor " + score + "/100 PASS | original" } },
    "Parse QC + Set Verdict": { qcVerdict: "SHIP", qcScore: 92 },
  }), undefined, undefined);
  return out[0].json;
}

test("offline candidate changes only two node code bodies, preserving pinned live export", () => {
  assert.equal(JSON.stringify(pinned), before);
  const changed = candidate.nodes.filter(n => {
    const old = originalNodes[n.name];
    return JSON.stringify(n) !== JSON.stringify(old);
  }).map(n => n.name).sort();
  assert.deepEqual(changed, ["QC Doctor Gate", "Script Gate: Quality"]);
  assert.match(originalNodes["Script Gate: Quality"].parameters.jsCode, /DOCTOR_FLOOR = 70/);
  // Pinned raw export still predates the compliance fix and contains no Doctor floor at all.
  assert.doesNotMatch(originalNodes["QC Doctor Gate"].parameters.jsCode, /DOCTOR_FLOOR/);
  assert.match(qcMirror, /DOCTOR_FLOOR = 70/);
});
test("TQO script gate refuses 89 and accepts 90 for existing downstream gates", () => {
  const low = scriptGate("TQO", 89), exact = scriptGate("TQO", 90);
  assert.equal(low.status, "Error", JSON.stringify(low.gateFailures));
  assert.ok(low.gateFailures.some(f => f.includes("under the floor of 90")));
  assert.equal(exact.status, "Scripted", JSON.stringify(exact.gateFailures));
});
test("NCO script gate still accepts 70 and rejects 69", () => {
  assert.equal(scriptGate("NCO", 70).status, "Scripted");
  const low = scriptGate("NCO", 69);
  assert.equal(low.status, "Error");
  assert.ok(low.gateFailures.some(f => f.includes("under the floor of 70")));
});
test("QC Doctor gate uses 90 for TQO while preserving 70 for NCO", () => {
  assert.equal(qcGate("TQO", 89).doctorGate, "REVISE");
  assert.equal(qcGate("TQO", 90).doctorGate, "READY_FOR_HUMAN_REVIEW");
  assert.equal(qcGate("NCO", 69).doctorGate, "REVISE");
  assert.equal(qcGate("NCO", 70).doctorGate, "READY_FOR_HUMAN_REVIEW");
});
test("candidate refuses drifted or ambiguous source exports", () => {
  const corrupted = structuredClone(pinned);
  corrupted.nodes.find(n => n.name === "Script Gate: Quality").parameters.jsCode = "other";
  assert.throws(() => buildTqo90Candidate(corrupted, qcMirror), /anchor drifted/);
  const repeated = structuredClone(pinned);
  repeated.nodes.push(structuredClone(repeated.nodes.find(n => n.name === "QC Doctor Gate")));
  assert.throws(() => buildTqo90Candidate(repeated, qcMirror), /exactly one/);
});
