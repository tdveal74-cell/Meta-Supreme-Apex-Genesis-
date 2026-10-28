import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { buildUniversal90Candidate } from "./tqo90_workflow_candidate.mjs";

const read = relative => readFileSync(new URL(relative, import.meta.url), "utf8");
const pinned = JSON.parse(read("../exports/qEkGOUsNyVaRAmm6_active.json"));
const before = JSON.stringify(pinned);
const { candidate, scriptCode, parseCode, qcCode, publishCode } = buildUniversal90Candidate(pinned);
const originalNodes = Object.fromEntries(pinned.nodes.map(n => [n.name, n]));
import { createRequire } from "node:module";
const nodeRequire = createRequire(import.meta.url); // n8n Code nodes expose require
const execute = code => {
  const fn = new Function("$", "$json", "$input", "require", code);
  return ($, $json, $input) => fn($, $json, $input, nodeRequire);
};
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
    "AI Review: Verified Result": {},
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

test("candidate is the live export unchanged, and the live floors are already 90", () => {
  assert.equal(JSON.stringify(pinned), before);
  assert.equal(JSON.stringify(candidate), before);
  assert.match(originalNodes["Script Gate: Quality"].parameters.jsCode, /DOCTOR_FLOOR = 90/);
  assert.match(originalNodes["Parse QC + Set Verdict"].parameters.jsCode, /SHIP_AT = 90/);
  assert.match(originalNodes["QC Doctor Gate"].parameters.jsCode, /DOCTOR_FLOOR = 90/);
});
test("Script Doctor acceptance is 90 for TQO and both NCO aliases, with no AI review receipt required", () => {
  for (const brand of ["TQO","NCO","NCO_FORGE"]) {
    const low = scriptGate(brand, 89);
    assert.equal(low.status, "Error", brand + " 89");
    assert.ok(low.gateFailures.some(f => f.includes("under the floor of 90")));
    for (const score of [90, 100]) {
      const result = scriptGate(brand, score);
      assert.ok(!result.gateFailures.some(f => f.includes("under the floor of 90")), brand + " " + score);
      assert.ok(!result.gateFailures.some(f => /review|adapter/i.test(f)), JSON.stringify(result.gateFailures));
      assert.deepEqual(result.gateFailures, [], brand + " " + score);
      assert.notEqual(result.status, "Error", brand + " " + score);
    }
  }
});
test("QC score acceptance is 90 and a blocker overrides even a 100", () => {
  assert.equal(parseQc(89).qcVerdict, "HOLD");
  assert.equal(parseQc(90).qcVerdict, "SHIP");
  assert.equal(parseQc(100).qcVerdict, "SHIP");
  assert.equal(parseQc(100, ["unsupported claim"]).qcVerdict, "HOLD");
});
test("downstream QC Doctor 90 boundary applies equally to TQO and NCO, no AI receipt needed", () => {
  for (const brand of ["TQO","NCO","NCO_FORGE"]) {
    // Live code sets presenterDoctorVerdict to UNCHECKED when the doctor is under the floor,
    // so gate() holds ("Presenter script unchecked") before it can reach REVISE. Fail closed either way.
    const low = qcGate(brand, 89);
    assert.equal(low.doctorGate, "HOLD", brand + " 89");
    assert.match(low.doctorGateReason, /Presenter script unchecked/);
    for (const score of [90,100]) {
      const result = qcGate(brand, score);
      assert.equal(result.doctorGate, "READY_FOR_HUMAN_REVIEW", brand + " " + score);
      assert.doesNotMatch(result.doctorGateReason, /review adapter|receipt/i);
    }
  }
});

const SCRIPT_TEXT = "A calm script body that the human approves by its hash.";
const scriptSha = text => createHash("sha256").update(text, "utf8").digest("hex");
function publishGate(qcVerdict, qcScore, humanReview = "approved:" + scriptSha(SCRIPT_TEXT), script = SCRIPT_TEXT) {
  const disclosure = "Presented with a synthetic voice and synthetic likeness of Terrance Veal, used with his consent.";
  const fields = {
    Channel: "The Quiet Operator", "Human Review": humanReview, Script: script,
    "Video Title": "The Quiet Mistake Managers Make With Copilot",
    Description: disclosure + "\n\n" + "A calm sourced explanation of the stakes and the next practical action. ".repeat(3),
    Tags: "ai, career, the quiet operator", "AI Disclosure": "Disclosed in description",
    "QC Verdict": qcVerdict, Show: "TQO", Season: 1, Episode: 3, "Asset Type": "Flagship",
  };
  const labels = ["YOUTUBE TAGS", "PINNED COMMENT", "TIKTOK", "INSTAGRAM", "FACEBOOK", "LINKEDIN 1", "X THREAD 1", "X VALUE POST", "SHORT SCRIPT 1", "THUMBNAIL TEXT"];
  const block = labels.join("\n\nbody\n\n");
  const nodes = {
    "Show Context: Publish": { channel: "The Quiet Operator", requiredTags: ["the quiet operator"] },
    "One Row at a Time": { fields },
    "Parse Packaging": { airtableId: "rec1", packagingBlock: block, youtubeTags: "", linkedinCount: 3, xThreadCount: 5, shortScriptCount: 2 },
    "Parse Manifest": {},
    "Parse QC + Set Verdict": { qcScore, qcVerdict, packagingGrade: 8.2, packagingGradeReport: "" },
    "Shim: Thumbnail To Binary": { thumb_rendered: true },
    "Upload Thumbnail": { webViewLink: "https://example.invalid/test-thumb" },
    "AI Review: Verified Result": {},
  };
  return execute(publishCode)(dollar(nodes), undefined, undefined)[0].json;
}
test("publish clears at QC 90 with the script hash approval and no AI receipt, and WAIVED cannot bypass 90", () => {
  for (const score of [90, 100]) {
    const ok = publishGate("SHIP", score);
    assert.equal(ok.os28_allowed, true, score + " " + JSON.stringify(ok.os28_blocking));
    assert.deepEqual(ok.os28_blocking, []);
  }
  const low = publishGate("SHIP", 89);
  assert.equal(low.os28_allowed, false);
  assert.ok(low.os28_blocking.some(r => r.startsWith("qc:")), JSON.stringify(low.os28_blocking));
  const waived = publishGate("WAIVED", 100);
  assert.equal(waived.os28_allowed, false);
  assert.ok(waived.os28_blocking.some(r => r.startsWith("qc:")), JSON.stringify(waived.os28_blocking));
  for (const r of [low, waived]) {
    assert.ok(!r.os28_blocking.some(b => /review adapter|AI review|receipt/i.test(b)), JSON.stringify(r.os28_blocking));
  }
});
test("human approval is bound to the sha256 of the script", () => {
  const good = "approved:" + scriptSha(SCRIPT_TEXT);
  for (const bad of ["true", "approved", "approved:" + scriptSha("another script"), ""]) {
    const r = publishGate("SHIP", 95, bad);
    assert.equal(r.os28_allowed, false, JSON.stringify(bad));
    assert.ok(r.os28_blocking.some(b => b.startsWith("authorship:")), JSON.stringify(r.os28_blocking));
  }
  const edited = publishGate("SHIP", 95, good, SCRIPT_TEXT + " edited after approval");
  assert.equal(edited.os28_allowed, false);
  assert.ok(edited.os28_blocking.some(b => b.startsWith("authorship:")));
  assert.equal(publishGate("SHIP", 95, good.toUpperCase()).os28_allowed, true, "comparison lowercases the cell");
});
test("candidate fails on drift, duplicate nodes, or a returning AI review hold", () => {
  const setCode = (exp, name, fn) => {
    const node = exp.nodes.find(n => n.name === name);
    node.parameters.jsCode = fn(node.parameters.jsCode);
    return exp;
  };
  const broken = setCode(structuredClone(pinned), "Script Gate: Quality", c => c.replace("DOCTOR_FLOOR = 90;", "DOCTOR_FLOOR = 70;"));
  assert.throws(() => buildUniversal90Candidate(broken), /Script Gate floor anchor drifted/);
  const lowShip = setCode(structuredClone(pinned), "Parse QC + Set Verdict", c => c.replace("SHIP_AT = 90;", "SHIP_AT = 80;"));
  assert.throws(() => buildUniversal90Candidate(lowShip), /QC parser SHIP floor anchor drifted/);
  const duplicate = structuredClone(pinned);
  duplicate.nodes.push(structuredClone(duplicate.nodes.find(n => n.name === "QC Doctor Gate")));
  assert.throws(() => buildUniversal90Candidate(duplicate), /exactly one/);
  const hold = setCode(structuredClone(pinned), "OS 28: Publish Gate",
    c => c.replace("const blocking = [];", "const blocking = [];\nblocking.push('Universal 90 signed final-text review adapter not yet wired');"));
  assert.throws(() => buildUniversal90Candidate(hold), /pending AI review hold anchor drifted/);
});
