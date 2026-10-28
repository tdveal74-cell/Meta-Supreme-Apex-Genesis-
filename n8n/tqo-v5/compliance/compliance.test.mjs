/**
 * The compliance laws ruled by Tee on 2026-10-17 and restored on 2026-10-24,
 * driven over the LIVE node bodies read from the export:
 *
 *   node n8n/tqo-v5/compliance/compliance.test.mjs
 *
 * These began as candidate patches (replacements.json applied to the export).
 * They have since been published, so nothing is patched here any more: every
 * behaviour check runs on exportCode(name) from
 * ../exports/qEkGOUsNyVaRAmm6_active.json, so the test cannot pass on code the
 * workflow does not run. Re-export the workflow and this test follows it.
 *
 * OS 28: Publish Gate holds quality law 13 (the exact C4 line in the first
 * three lines of the description, for every episode, with no "Not required"
 * escape) and quality laws 6 and 7 on the title. Script: Fill Run Fields puts
 * the exact line first, once. QC Doctor Gate clears a row to human review on
 * the script doctor verdict at a floor of 90 plus a SHIP QC verdict.
 *
 * Authorship, ruled 2026-10-28 ("Drop the AI review from the publish gate"):
 * the AI review receipt gates nothing. The human approval
 * approved:<sha256 of the script> is still required.
 *
 * The Doctor Gate is proved on the real shapes: a data table row is passed
 * through the export's own DT Shim: Ready Rows and Parse QC + Set Verdict
 * before it reaches the gate. Nothing here touches n8n or the network. The rows
 * are synthetic.
 */

import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";

const require = createRequire(import.meta.url);
const read = (rel) => readFileSync(new URL(rel, import.meta.url), "utf8");
const sha = (s) => createHash("sha256").update(s, "utf8").digest("hex");
const EXPORT = JSON.parse(read("../exports/qEkGOUsNyVaRAmm6_active.json"));
const exportCode = (name) => {
  const found = EXPORT.nodes.filter((n) => n.name === name);
  assert.equal(found.length, 1, name + ": one node of that name in the export");
  return found[0].parameters.jsCode;
};
const C4 = "Presented with a synthetic voice and synthetic likeness of Terrance Veal, used with his consent.";

const dollar = (nodes) => (name) => {
  if (!(name in nodes)) throw new Error("node did not run: " + name);
  const items = nodes[name];
  return { first: () => items[0], all: () => items };
};
const node = (code) => new Function("$", "$input", "$json", "require", code);
const SCRIPT = "A calm script about what changed this month.";
// What AI Review: Verified Result hands on. It gates nothing now.
const emptyReview = {};
const passedReview = (script = SCRIPT) => ({ aiReviewPassed: true, artifactSha256: sha(script), scope: "script", score: 93, reviewId: "r1" });

// ---- OS 28: Publish Gate --------------------------------------------------
const OS28 = node(exportCode("OS 28: Publish Gate"));
const BLOCK = ["YOUTUBE TAGS", "PINNED COMMENT", "TIKTOK", "INSTAGRAM", "FACEBOOK", "LINKEDIN 1", "X THREAD 1", "X VALUE POST", "SHORT SCRIPT 1", "THUMBNAIL TEXT"].join("\n\nbody\n\n");
const DESC_BODY = "A calm walk through what changed in the tooling this month and what it costs a manager who waits. ".repeat(2).trim();
const cleanRow = (edit = {}) => ({
  Channel: "The Quiet Operator", "Human Review": "approved:" + sha(SCRIPT), Script: SCRIPT,
  "Video Title": "The Quiet Mistake Managers Make With Copilot",
  Description: C4 + "\n\n" + DESC_BODY, Tags: "ai, career, the quiet operator", "AI Disclosure": "Disclosed in description",
  "QC Verdict": "SHIP", Show: "TQO", Season: 1, Episode: 3, "Asset Type": "Flagship", ...edit,
});
const runGate = (fields, { qcScore = 91, review = emptyReview } = {}) => OS28(dollar({
  "Show Context: Publish": [{ json: { channel: "The Quiet Operator", requiredTags: ["the quiet operator"] } }],
  "One Row at a Time": [{ json: { fields } }],
  "Parse Packaging": [{ json: { airtableId: "rec1", packagingBlock: BLOCK, youtubeTags: "", linkedinCount: 3, xThreadCount: 5, shortScriptCount: 2 } }],
  "Parse Manifest": [{ json: {} }],
  "Parse QC + Set Verdict": [{ json: { qcScore, qcVerdict: "SHIP", packagingGrade: 8.2, packagingGradeReport: "" } }],
  "Shim: Thumbnail To Binary": [{ json: { thumb_rendered: true } }],
  "Upload Thumbnail": [{ json: { webViewLink: "https://drive.example/thumb" } }],
  "AI Review: Verified Result": [{ json: { aiReview: review } }],
}), undefined, undefined, require)[0].json;
const blocked = (out, prefix) => out.os28_blocking.filter((b) => b.startsWith(prefix));

// A row with everything in place clears. The numeric floor is 90.
let out = runGate(cleanRow());
assert.deepEqual(out.os28_blocking, [], "the clean row clears the gate");
assert.equal(out.os28_allowed, true);
assert.equal(runGate(cleanRow(), { qcScore: 89 }).os28_allowed, false, "89 can never clear publish QC");
assert.equal(runGate(cleanRow(), { qcScore: 90 }).os28_allowed, true, "90 meets QC numeric minimum with other checks");
assert.equal(runGate(cleanRow({ "QC Verdict": "WAIVED" }), { qcScore: 100 }).os28_allowed, false, "WAIVED does not bypass the 90 floor");

// Authorship, per the 2026-10-28 ruling. Approval bound to the script hash
// clears with no review receipt; a wrong hash, or none, blocks.
assert.equal(runGate(cleanRow(), { review: emptyReview }).os28_allowed, true, "approval bound to the script hash clears without a review receipt");
assert.equal(runGate(cleanRow(), { review: passedReview("another script") }).os28_allowed, true, "a receipt for another script neither blocks nor is required");
assert.equal(runGate(cleanRow(), { review: passedReview() }).os28_allowed, true, "a verified receipt is welcome and changes nothing");
for (const [why, hr] of [
  ["approved for another script hash", "approved:" + sha("another")],
  ["ticked yes", "yes"], ["ticked true", "true"], ["empty", ""],
]) {
  out = runGate(cleanRow({ "Human Review": hr }));
  assert.equal(out.os28_allowed, false, "Human Review " + why + " blocks");
  assert.equal(blocked(out, "authorship:").length, 1, "Human Review " + why + " names the authorship gate");
}
// The approval is bound to the Script on the row, so editing the script voids it.
assert.equal(runGate(cleanRow({ Script: SCRIPT + " Edited." })).os28_allowed, false, "approval does not survive a script edit");
// And a receipt cannot stand in for the human: it never clears a row by itself.
assert.equal(runGate(cleanRow({ "Human Review": "" }), { review: passedReview() }).os28_allowed, false, "a receipt alone does not clear authorship");

// "Not required" with no line at all is held.
const notRequired = cleanRow({ "AI Disclosure": "Not required", Description: DESC_BODY });
out = runGate(notRequired);
assert.equal(out.os28_allowed, false);
assert.equal(blocked(out, "disclosure: AI Disclosure is \"Not required\"").length, 1);
assert.equal(blocked(out, "disclosure: the Description does not contain the exact C4 line").length, 1);
// "Not required" is refused even when the line is in place.
assert.equal(runGate(cleanRow({ "AI Disclosure": "Not required" })).os28_allowed, false);

// The line below the first three lines is held.
const lowLine = cleanRow({ Description: "one\ntwo\nthree\n" + C4 + "\n" + DESC_BODY });
out = runGate(lowLine);
assert.equal(out.os28_allowed, false);
assert.equal(blocked(out, "disclosure: the C4 line is in the Description but not on a line of its own in its first three lines").length, 1);
// The line must be a line of its own: inside a longer line, or at the end of a
// one-line description, it is not the line.
for (const d of ["Disclaimer: " + C4 + "\n" + DESC_BODY, DESC_BODY + " " + C4, C4 + " (not really)\n" + DESC_BODY]) {
  assert.equal(runGate(cleanRow({ Description: d })).os28_allowed, false, JSON.stringify(d.slice(0, 40)));
}
assert.equal(runGate(cleanRow({ Description: C4 + "\r\n" + DESC_BODY })).os28_allowed, true, "a CRLF line ending is still the line");
// Line three is still inside; a variant of the line is not the line.
assert.equal(runGate(cleanRow({ Description: "one\ntwo\n" + C4 + "\n" + DESC_BODY })).os28_allowed, true);
assert.equal(runGate(cleanRow({ Description: C4.replace("consent.", "consent") + "\n\n" + DESC_BODY })).os28_allowed, false);
// On-screen plus description is accepted with the line in place; unset is not.
assert.equal(runGate(cleanRow({ "AI Disclosure": "Disclosed on-screen + description" })).os28_allowed, true);
out = runGate(cleanRow({ "AI Disclosure": "" }));
assert.equal(blocked(out, "disclosure: AI Disclosure is unset").length, 1);

// The title laws.
for (const [title, why] of [
  ["Copilot Settings Explained Simply", "no tension word"],
  ["the quiet mistake managers make", "no proper noun"],
  ["The Quiet Mistake " + String.fromCharCode(0x2014) + " Copilot", "em or en dash"],
]) {
  out = runGate(cleanRow({ "Video Title": title }));
  assert.equal(out.os28_allowed, false, "gate: " + title);
  assert.ok(blocked(out, "quality law titles:")[0].includes(why), title);
}

// ---- Script: Fill Run Fields ----------------------------------------------
const FILL = node(exportCode("Script: Fill Run Fields"));
const runFill = (description) => FILL(dollar({
  "Show Context: Script": [{ json: { show: "TQO", tableId: "t", tableRef: "r", channel: "The Quiet Operator" } }],
  "One Idea at a Time": [{ json: { fields: {} } }],
  "Originality Scan": [{ json: { recordId: "rec1", script: "A script.", title: "The Quiet Mistake", description, broll: ["desk"] } }],
}), undefined, undefined, require)[0].json.body.records[0].fields.Description;
const head3 = (s) => s.split("\n").slice(0, 3).join("\n");
// A looser phrase does not stop the line being added.
const loose = "Made with AI-assisted research.\n\n" + DESC_BODY;
assert.ok(head3(runFill(loose)).includes(C4));
// A line sitting lower down is moved to the top, and appears once.
const low = runFill("one\ntwo\nthree\nfour\n" + C4 + "\n" + DESC_BODY);
assert.ok(low.startsWith(C4 + "\n\n"));
assert.equal(low.split(C4).length, 2, "the line appears once");
// A line on line two or three is moved to the top too, and a second copy goes.
for (const d of ["intro\n" + C4 + "\n" + DESC_BODY, C4 + "\n" + C4 + "\n" + DESC_BODY, C4 + "\n\n" + DESC_BODY + "\n" + C4]) {
  const filled = runFill(d);
  assert.ok(filled.startsWith(C4 + "\n\n"), JSON.stringify(d.slice(0, 30)));
  assert.equal(filled.split(C4).length, 2, "once: " + JSON.stringify(d.slice(0, 30)));
  assert.equal(runFill(filled), filled, "a second fill changes nothing");
}
// A description that already opens with the line is left alone.
assert.equal(runFill(C4 + "\n\n" + DESC_BODY), C4 + "\n\n" + DESC_BODY);
// Every filled description clears the OS 28 disclosure rules.
for (const d of [loose, "", DESC_BODY, "one\ntwo\nthree\nfour\n" + C4]) {
  const filled = runFill(d);
  const gate = runGate(cleanRow({ Description: filled + (filled.length < 120 ? "\n" + DESC_BODY : "") }));
  assert.equal(blocked(gate, "disclosure:").length, 0, "filled from: " + JSON.stringify(d.slice(0, 30)));
}

// ---- QC Doctor Gate --------------------------------------------------------
const GATE_CODE = exportCode("QC Doctor Gate");
const GATE = node(GATE_CODE);
const line = (score, v) => "2026-10-17T10:00:00Z | doctor " + score + "/100 " + v + " | originality 71/100 (rhythm 70, similarity 12) | gate Scripted at 1540 words";
const runDoctor = ({ history, verdict = "SHIP", total = 91, review = emptyReview } = {}) => GATE(dollar({
  "One Row at a Time": [{ json: { fields: { id: 7, updatedAt: "2026-10-17", Script: SCRIPT, ...(history === undefined ? {} : { score_history: history }) } } }],
  "Parse QC + Set Verdict": [{ json: { qc_verdict: verdict, total } }],
  "AI Review: Verified Result": [{ json: { aiReview: review } }],
}), undefined, undefined, require)[0].json;
// With a passing script doctor line and a SHIP QC verdict a row reaches human
// review, with no AI review receipt.
assert.equal(runDoctor({ history: line(90, "PASS") }).doctorGate, "READY_FOR_HUMAN_REVIEW");
assert.equal(runDoctor({ history: line(90, "REPAIRED") }).doctorGate, "READY_FOR_HUMAN_REVIEW");
// A receipt, present or for another script, neither helps nor hurts.
assert.equal(runDoctor({ history: line(90, "PASS"), review: passedReview() }).doctorGate, "READY_FOR_HUMAN_REVIEW");
assert.equal(runDoctor({ history: line(90, "PASS"), review: passedReview("another script") }).doctorGate, "READY_FOR_HUMAN_REVIEW");
assert.equal(runDoctor({ history: line(84, "PASS"), review: passedReview() }).doctorGate, "HOLD", "a receipt does not lift a doctor score under the floor");
// It never reaches release on its own: no approval is ever built here.
assert.notEqual(runDoctor({ history: line(99, "PASS") }).doctorGate, "RELEASE_ELIGIBLE");
// Everything else still stops it.
const stops = [
  [{}, "HOLD", "no doctor line at all"],
  [{ history: "" }, "HOLD", "an empty history"],
  [{ history: line(84, "UNCHECKED") }, "HOLD", "the doctor did not run"],
  [{ history: line(84, "FAIL") }, "HOLD", "a failing doctor verdict"],
  [{ history: line(89, "PASS") }, "HOLD", "a doctor score under the floor"],
  [{ history: line(90, "PASS"), verdict: "CONDITIONAL" }, "REVISE", "a CONDITIONAL QC verdict"],
  [{ history: line(90, "PASS"), verdict: "SHIP", total: 89 }, "REVISE", "a QC score under 90"],
];
for (const [input, state, why] of stops) assert.equal(runDoctor(input).doctorGate, state, why);
// The doctor verdict must be a whole word: PASS-ISH is not PASS.
assert.equal(runDoctor({ history: line(84, "PASS-ISH") }).doctorGate, "HOLD");
// The verdict comes from the doctor line, not from the QC verdict.
assert.equal(runDoctor({ history: line(84, "UNCHECKED"), verdict: "SHIP" }).doctorGateReason, "Presenter script unchecked");

// ---- the Doctor Gate on the shapes the live lane produces -----------------
// A raw data table row goes through the export's own DT Shim: Ready Rows (which
// is what feeds One Row at a Time) and the export's own Parse QC + Set Verdict,
// fed a model answer. Hand made inputs passed while the real lane still held
// every row, so this chain is the proof the gate can clear.
const SHIM = node(exportCode("DT Shim: Ready Rows"));
const PARSE_QC = node(exportCode("Parse QC + Set Verdict"));
const realDoctor = ({ history, total = 91, blockers = [], review = emptyReview } = {}) => {
  const raw = { id: 7, createdAt: "2026-10-16T10:00:00Z", updatedAt: "2026-10-17T10:00:00Z", status: "Ready", system_status: "",
    brand: "TQO", show: "TQO", script: SCRIPT, ai_disclosure: "Disclosed in description", ...(history === undefined ? {} : { score_history: history }) };
  const shimmed = SHIM(dollar({}), { all: () => [{ json: raw }] }, undefined, require);
  assert.equal(shimmed.length, 1, "the shim keeps the row");
  const answer = { choices: [{ finish_reason: "stop", message: { content: JSON.stringify({ scores: { hook: 20 }, total, blockers, findings: [] }) } }] };
  const nodes = {
    "Show Context: Publish": [{ json: { channel: "The Quiet Operator" } }],
    "One Row at a Time": [shimmed[0]],
    "Build QC Prompt": [{ json: { airtableId: 7 } }],
    "AI Review: Verified Result": [{ json: { aiReview: review } }],
  };
  const qc = PARSE_QC(dollar(nodes), undefined, answer, require)[0].json;
  return GATE(dollar({ ...nodes, "Parse QC + Set Verdict": [{ json: qc }] }), undefined, undefined, require)[0].json;
};
// The gate reads the real keys and clears a clean row to human review.
let real = realDoctor({ history: line(90, "PASS") });
assert.equal(real.doctorGate, "READY_FOR_HUMAN_REVIEW", JSON.stringify(real));
assert.equal(real.qc_verdict, "SHIP");
assert.equal(real.qc_score, 91);
// A later QC line appended under the doctor line does not hide it.
assert.equal(realDoctor({ history: line(90, "PASS") + "\n2026-10-17T11:00:00Z | 91/100 SHIP | batch 8.0/10" }).doctorGate, "READY_FOR_HUMAN_REVIEW");
// And on the real shapes everything else still stops it.
for (const [input, state, why] of [
  [{}, "HOLD", "no score history"],
  [{ history: line(84, "FAIL") }, "HOLD", "a failing doctor verdict"],
  [{ history: line(89, "PASS") }, "HOLD", "a doctor score under the floor"],
  [{ history: line(90, "PASS"), total: 75 }, "REVISE", "a QC total under the ship line"],
  [{ history: line(90, "PASS"), blockers: ["claim unsourced"] }, "REVISE", "a QC hard blocker"],
]) assert.equal(realDoctor(input).doctorGate, state, why);

// Universal acceptance contract: same numerical floor across all four brands,
// no waiver of hard findings, no automatic release at 90.
const gatePrefix = GATE_CODE.split("const row = $('One Row at a Time').first().json;")[0];
assert.ok(gatePrefix.includes("function gate(x)"), "QC gate core function found");
const underlyingGate = new Function(gatePrefix + "\nreturn gate;")();
for (const brand of ["TQO", "NCO_FORGE", "TSWS", "ACX"]) {
  const make = score => ({
    show: brand,
    artifactHash: "fixture-sha", rubricVersion: "universal-90-v1",
    requiredScopes: ["script","episode"],
    reports: ["script","episode"].map(scope => ({
      scope, artifactHash: "fixture-sha", rubricVersion: "universal-90-v1",
      evidenceComplete: true, qcVerdict: "PASS",
      openP0P1: 0, criticalOrHigh: 0, score
    })),
    presenterDoctorVerdict: "PASS", dramaticDoctorVerdict: "RECOMMEND",
    policyValidated: true, releaseEvidenceValidated: true, approval: null,
  });
  assert.equal(underlyingGate(make(89)).state, "REVISE", brand + " 89");
  assert.equal(underlyingGate(make(90)).state, "READY_FOR_HUMAN_REVIEW", brand + " 90");
  assert.equal(underlyingGate(make(100)).state, "READY_FOR_HUMAN_REVIEW", brand + " 100");
  const missing = make(100);
  missing.reports[0].evidenceComplete = false;
  assert.equal(underlyingGate(missing).state, "EVIDENCE_REQUIRED", brand + " missing evidence");
  const hard = make(100);
  hard.reports[1].criticalOrHigh = 1;
  assert.equal(underlyingGate(hard).state, "REVISE", brand + " high finding");
}
console.log("Compliance fixes: OS 28 holds what the law says, Fill puts the line first, the Doctor Gate can clear");
