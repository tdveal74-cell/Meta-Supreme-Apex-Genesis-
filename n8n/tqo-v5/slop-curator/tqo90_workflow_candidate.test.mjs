import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { buildUniversal90Candidate } from "./tqo90_workflow_candidate.mjs";

const read = relative => readFileSync(new URL(relative, import.meta.url), "utf8");
const pinned = JSON.parse(read("../exports/qEkGOUsNyVaRAmm6_active.json"));
const qcMirror = read("../compliance/qc_doctor_gate.js");
const before = JSON.stringify(pinned);
const { candidate, scriptCode, parseCode, qcCode } = buildUniversal90Candidate(pinned, qcMirror);
const originalNodes = Object.fromEntries(pinned.nodes.map(n => [n.name, n]));
const execute = code => new Function("$", "$json", "$input", code);
const dollar = entries => name => {
  if (!(name in entries)) throw Error("unexpected node read: " + name);
  return { first: () => ({ json: entries[name] }) };
};

function scriptGate(show, doctorScore) {
  const objective = "Check what this model returned";
  const script = objective + " " + "A workplace test starts with a source and a human check. ".repeat(120)
    + "What evidence would you share in the comments?";
  const json = {
    script, title: "The Quiet Test", description: "A careful source check.",
    broll: "desk,screen,report,notebook,team,source",
    learningObjective: objective, checklist: ["Compare source", "Test output", "Record gaps"],
    doctorScore, doctorVerdict: "PASS", rhythmScore: 75, similarityScore: 75,
  };
  return execute(scriptCode)(dollar({
    "Build Doctor Prompt": { original: { draftWords: 1400, expansion: "not needed" } },
    "DEVON Recall: Merge": { devonRecallNote: "mock recall, no claims" },
    "Show Context: Script": { show },
  }), json, undefined)[0].json;
}

function qcGate(brand, doctorScore) {
  return execute(qcCode)(dollar({
    "One Row at a Time": { fields: {
      id: 7, updatedAt: "2026-10-19", brand, show: brand,
      score_history: "2026-10-19 | doctor " + doctorScore + "/100 PASS | original",
    } },
    "Parse QC + Set Verdict": { qcVerdict: "SHIP", qcScore: 92 },
  }), undefined, undefined)[0].json;
}
function parseQc(total, blockers = []) {
  return execute(parseCode)(dollar({
    "One Row at a Time": { fields: { id: 7, Show: "TQO", Season: 1, Episode: 1 } },
    "Show Context: Publish": { channel: "The Quiet Operator" },
    "Build QC Prompt": { airtableId: 7 },
  }), {
    choices: [{ finish_reason: "stop", message: { content: JSON.stringify({
      scores: { hook: 20 }, total, blockers, findings: [], batch_score: 9,
    }) } }],
  }, undefined)[0].json;
}

test("offline universal-90 candidate changes exactly three node bodies, never pinned export", () => {
  assert.equal(JSON.stringify(pinned), before);
  const changed = candidate.nodes.filter(n => {
    const old = originalNodes[n.name];
    return JSON.stringify(n) !== JSON.stringify(old);
  }).map(n => n.name).sort();
  assert.deepEqual(changed, ["Parse QC + Set Verdict", "QC Doctor Gate", "Script Gate: Quality"]);
  assert.match(originalNodes["Script Gate: Quality"].parameters.jsCode, /DOCTOR_FLOOR = 70/);
  assert.match(originalNodes["Parse QC + Set Verdict"].parameters.jsCode, /SHIP_AT = 80/);
  assert.match(qcMirror, /DOCTOR_FLOOR = 90/);
});
test("Script Doctor acceptance is 90 for TQO and both NCO aliases", () => {
  for (const brand of ["TQO","NCO","NCO_FORGE"]) {
    const low = scriptGate(brand, 89);
    assert.equal(low.status, "Error", brand + " 89");
    assert.ok(low.gateFailures.some(f => f.includes("under the floor of 90")));
    for (const score of [90, 100]) {
      const result = scriptGate(brand, score);
      assert.equal(result.status, "Error", brand + " pending verifier");
      assert.ok(result.gateFailures.some(f => f.includes("signed final-text review adapter not yet wired")));
      assert.ok(!result.gateFailures.some(f => f.includes("under the floor of 90")));
    }
  }
});
test("QC score acceptance is 90 and a blocker overrides even a 100", () => {
  assert.equal(parseQc(89).qcVerdict, "HOLD");
  assert.equal(parseQc(90).qcVerdict, "SHIP");
  assert.equal(parseQc(100).qcVerdict, "SHIP");
  assert.equal(parseQc(100, ["unsupported claim"]).qcVerdict, "HOLD");
});
test("downstream QC Doctor 90 boundary applies equally to TQO and NCO", () => {
  for (const brand of ["TQO","NCO","NCO_FORGE"]) {
    assert.equal(qcGate(brand, 89).doctorGate, "REVISE", brand + " 89");
    for (const score of [90,100]) {
      const result = qcGate(brand, score);
      assert.equal(result.doctorGate, "HOLD", brand + " pending signed receipt");
      assert.match(result.doctorGateReason, /signed final-text review adapter/);
    }
  }
});
test("candidate fails on drift, duplicate nodes, or stale compliance mirror", () => {
  const broken = structuredClone(pinned);
  broken.nodes.find(n => n.name === "Script Gate: Quality").parameters.jsCode = "other";
  assert.throws(() => buildUniversal90Candidate(broken, qcMirror), /anchor drifted/);
  const duplicate = structuredClone(pinned);
  duplicate.nodes.push(structuredClone(duplicate.nodes.find(n => n.name === "QC Doctor Gate")));
  assert.throws(() => buildUniversal90Candidate(duplicate, qcMirror), /exactly one/);
  assert.throws(() => buildUniversal90Candidate(pinned, qcMirror.replace("const DOCTOR_FLOOR = 90;", "const DOCTOR_FLOOR = 70;")), /mirror missing or invalid/);
});
