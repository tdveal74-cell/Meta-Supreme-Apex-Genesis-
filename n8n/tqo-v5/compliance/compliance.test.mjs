/**
 * The three compliance fixes ruled by Tee on 2026-10-17, driven over the real
 * node bodies:
 *
 *   node n8n/tqo-v5/compliance/compliance.test.mjs
 *
 * OS 28: Publish Gate now enforces quality law 13 (the exact C4 line in the
 * first three lines of the description, for every episode, with no "Not
 * required" escape) and quality laws 6 and 7 on the title. Both had been
 * written on 2026-09-30 into a nested parameters.jsCode copy that n8n never
 * runs. Script: Fill Run Fields now always puts the exact line first. QC
 * Doctor Gate now builds the script report it required and never built, so a
 * row with a passing script doctor verdict can reach human review.
 *
 * Each file is pinned to the live export: applying replacements.json to the
 * export code must give the file exactly, so any other change fails here.
 * Nothing here touches n8n or the network. The rows are synthetic.
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const read = (rel) => readFileSync(new URL(rel, import.meta.url), "utf8");
const EXPORT = JSON.parse(read("../exports/qEkGOUsNyVaRAmm6_active.json"));
const exportCode = (name) => EXPORT.nodes.find((n) => n.name === name).parameters.jsCode;
const REPLACEMENTS = JSON.parse(read("./replacements.json"));
const FILES = {
  "OS 28: Publish Gate": "os28_publish_gate.js",
  "Script: Fill Run Fields": "fill_run_fields.js",
  "QC Doctor Gate": "qc_doctor_gate.js",
};
const C4 = "Presented with a synthetic voice and synthetic likeness of Terrance Veal, used with his consent.";

// ---- each file is the export plus exactly the listed replacements -----------
for (const [name, file] of Object.entries(FILES)) {
  let code = exportCode(name);
  for (const [oldText, newText] of REPLACEMENTS[name]) {
    assert.equal(code.split(oldText).length, 2, name + ": a replaced fragment occurs once in the export");
    code = code.replace(oldText, () => newText);
  }
  assert.equal(read("./" + file) === code, true, name + ": the file is the export plus the listed replacements and nothing else");
  // The live code carries literal dashes inside its own dash checks; what this
  // change adds carries none.
  for (const [, newText] of REPLACEMENTS[name]) assert.equal(/[\u2013\u2014]/.test(newText), false, name + ": an added fragment carries a literal dash");
}

const dollar = (nodes) => (name) => {
  if (!(name in nodes)) throw new Error("node did not run: " + name);
  const items = nodes[name];
  return { first: () => items[0], all: () => items };
};
const node = (code) => new Function("$", "$input", code);

// ---- OS 28: Publish Gate --------------------------------------------------
const OS28_NEW = node(read("./os28_publish_gate.js"));
const OS28_OLD = node(exportCode("OS 28: Publish Gate"));
const BLOCK = ["YOUTUBE TAGS", "PINNED COMMENT", "TIKTOK", "INSTAGRAM", "FACEBOOK", "LINKEDIN 1", "X THREAD 1", "X VALUE POST", "SHORT SCRIPT 1", "THUMBNAIL TEXT"].join("\n\nbody\n\n");
const DESC_BODY = "A calm walk through what changed in the tooling this month and what it costs a manager who waits. ".repeat(2).trim();
const cleanRow = (edit = {}) => ({
  Channel: "The Quiet Operator", "Human Review": "true", "Video Title": "The Quiet Mistake Managers Make With Copilot",
  Description: C4 + "\n\n" + DESC_BODY, Tags: "ai, career, the quiet operator", "AI Disclosure": "Disclosed in description",
  "QC Verdict": "SHIP", Show: "TQO", Season: 1, Episode: 3, "Asset Type": "Flagship", ...edit,
});
const runGate = (code, fields) => code(dollar({
  "Show Context: Publish": [{ json: { channel: "The Quiet Operator", requiredTags: ["the quiet operator"] } }],
  "One Row at a Time": [{ json: { fields } }],
  "Parse Packaging": [{ json: { airtableId: "rec1", packagingBlock: BLOCK, youtubeTags: "", linkedinCount: 3, xThreadCount: 5, shortScriptCount: 2 } }],
  "Parse Manifest": [{ json: {} }],
  "Parse QC + Set Verdict": [{ json: { qcScore: 91, qcVerdict: "SHIP", packagingGrade: 8.2, packagingGradeReport: "" } }],
  "Shim: Thumbnail To Binary": [{ json: { thumb_rendered: true } }],
  "Upload Thumbnail": [{ json: { webViewLink: "https://drive.example/thumb" } }],
}), undefined)[0].json;
const blocked = (out, prefix) => out.os28_blocking.filter((b) => b.startsWith(prefix));

// A row with everything in place clears, under both the old and the new code.
let out = runGate(OS28_NEW, cleanRow());
assert.deepEqual(out.os28_blocking, [], "the clean row clears the new gate");
assert.equal(out.os28_allowed, true);
assert.equal(runGate(OS28_OLD, cleanRow()).os28_allowed, true);

// "Not required" with no line at all passed the old gate. It is held now.
const notRequired = cleanRow({ "AI Disclosure": "Not required", Description: DESC_BODY });
assert.equal(runGate(OS28_OLD, notRequired).os28_allowed, true, "the old gate let a presenter-led episode through with no disclosure");
out = runGate(OS28_NEW, notRequired);
assert.equal(out.os28_allowed, false);
assert.equal(blocked(out, "disclosure: AI Disclosure is \"Not required\"").length, 1);
assert.equal(blocked(out, "disclosure: the Description does not contain the exact C4 line").length, 1);
// "Not required" is refused even when the line is in place.
assert.equal(runGate(OS28_NEW, cleanRow({ "AI Disclosure": "Not required" })).os28_allowed, false);

// The line below the first three lines passed the old gate. It is held now.
const lowLine = cleanRow({ Description: "one\ntwo\nthree\n" + C4 + "\n" + DESC_BODY });
assert.equal(runGate(OS28_OLD, lowLine).os28_allowed, true, "the old gate accepted the line anywhere");
out = runGate(OS28_NEW, lowLine);
assert.equal(out.os28_allowed, false);
assert.equal(blocked(out, "disclosure: the C4 line is in the Description but not in its first three lines").length, 1);
// Line three is still inside; a variant of the line is not the line.
assert.equal(runGate(OS28_NEW, cleanRow({ Description: "one\ntwo\n" + C4 + "\n" + DESC_BODY })).os28_allowed, true);
assert.equal(runGate(OS28_NEW, cleanRow({ Description: C4.replace("consent.", "consent") + "\n\n" + DESC_BODY })).os28_allowed, false);
// On-screen plus description is accepted with the line in place; unset is not.
assert.equal(runGate(OS28_NEW, cleanRow({ "AI Disclosure": "Disclosed on-screen + description" })).os28_allowed, true);
out = runGate(OS28_NEW, cleanRow({ "AI Disclosure": "" }));
assert.equal(blocked(out, "disclosure: AI Disclosure is unset").length, 1);

// The title laws. The old gate never held a title for these.
for (const [title, why] of [
  ["Copilot Settings Explained Simply", "no tension word"],
  ["the quiet mistake managers make", "no proper noun"],
  ["The Quiet Mistake " + String.fromCharCode(0x2014) + " Copilot", "em or en dash"],
]) {
  assert.equal(runGate(OS28_OLD, cleanRow({ "Video Title": title })).os28_allowed, true, "old gate: " + title);
  out = runGate(OS28_NEW, cleanRow({ "Video Title": title }));
  assert.equal(out.os28_allowed, false, "new gate: " + title);
  assert.ok(blocked(out, "quality law titles:")[0].includes(why), title);
}

// ---- Script: Fill Run Fields ----------------------------------------------
const FILL_NEW = node(read("./fill_run_fields.js"));
const FILL_OLD = node(exportCode("Script: Fill Run Fields"));
const runFill = (code, description) => code(dollar({
  "Show Context: Script": [{ json: { show: "TQO", tableId: "t", tableRef: "r", channel: "The Quiet Operator" } }],
  "One Idea at a Time": [{ json: { fields: {} } }],
  "Originality Scan": [{ json: { recordId: "rec1", script: "A script.", title: "The Quiet Mistake", description, broll: ["desk"] } }],
}), undefined)[0].json.body.records[0].fields.Description;
const head3 = (s) => s.split("\n").slice(0, 3).join("\n");
// A looser phrase used to stop the line being added at all.
const loose = "Made with AI-assisted research.\n\n" + DESC_BODY;
assert.ok(!runFill(FILL_OLD, loose).includes(C4), "the old fill skipped the line after a looser phrase");
assert.ok(head3(runFill(FILL_NEW, loose)).includes(C4));
// A line sitting lower down is moved to the top, and appears once.
const low = runFill(FILL_NEW, "one\ntwo\nthree\nfour\n" + C4 + "\n" + DESC_BODY);
assert.ok(low.startsWith(C4 + "\n\n"));
assert.equal(low.split(C4).length, 2, "the line appears once");
// A description that already opens with the line is left alone.
assert.equal(runFill(FILL_NEW, C4 + "\n\n" + DESC_BODY), C4 + "\n\n" + DESC_BODY);
// Every filled description clears the new OS 28 disclosure rules.
for (const d of [loose, "", DESC_BODY, "one\ntwo\nthree\nfour\n" + C4]) {
  const filled = runFill(FILL_NEW, d);
  const gate = runGate(OS28_NEW, cleanRow({ Description: filled + (filled.length < 120 ? "\n" + DESC_BODY : "") }));
  assert.equal(blocked(gate, "disclosure:").length, 0, "filled from: " + JSON.stringify(d.slice(0, 30)));
}

// ---- QC Doctor Gate --------------------------------------------------------
const GATE_NEW = node(read("./qc_doctor_gate.js"));
const GATE_OLD = node(exportCode("QC Doctor Gate"));
const runDoctor = (code, { history, verdict = "SHIP", total = 91 } = {}) => code(dollar({
  "One Row at a Time": [{ json: { fields: { id: 7, updatedAt: "2026-10-17", ...(history === undefined ? {} : { score_history: history }) } } }],
  "Parse QC + Set Verdict": [{ json: { qc_verdict: verdict, total } }],
}), undefined)[0].json;
const line = (score, v) => "2026-10-17T10:00:00Z | doctor " + score + "/100 " + v + " | originality 71/100 (rhythm 70, similarity 12) | gate Scripted at 1540 words";

// The old gate held every row, a clean one included.
assert.equal(runDoctor(GATE_OLD, { history: line(84, "PASS") }).doctorGate, "EVIDENCE_REQUIRED");
assert.equal(runDoctor(GATE_OLD, { history: line(84, "PASS") }).doctorGateReason, "script");
// With a passing script doctor line and a SHIP QC verdict a row reaches human review.
assert.equal(runDoctor(GATE_NEW, { history: line(84, "PASS") }).doctorGate, "READY_FOR_HUMAN_REVIEW");
assert.equal(runDoctor(GATE_NEW, { history: line(70, "REPAIRED") }).doctorGate, "READY_FOR_HUMAN_REVIEW");
// It never reaches release on its own: no approval is ever built here.
assert.notEqual(runDoctor(GATE_NEW, { history: line(99, "PASS") }).doctorGate, "RELEASE_ELIGIBLE");
// Everything else still stops it.
const stops = [
  [{}, "HOLD", "no doctor line at all"],
  [{ history: "" }, "HOLD", "an empty history"],
  [{ history: line(84, "UNCHECKED") }, "HOLD", "the doctor did not run"],
  [{ history: line(84, "FAIL") }, "HOLD", "a failing doctor verdict"],
  [{ history: line(69, "PASS") }, "REVISE", "a doctor score under the floor"],
  [{ history: line(84, "PASS"), verdict: "CONDITIONAL" }, "REVISE", "a CONDITIONAL QC verdict"],
  [{ history: line(84, "PASS"), verdict: "SHIP", total: 84 }, "REVISE", "a QC score under 85"],
];
for (const [input, state, why] of stops) assert.equal(runDoctor(GATE_NEW, input).doctorGate, state, why);
// The verdict comes from the doctor line, not from the QC verdict any more.
assert.equal(runDoctor(GATE_NEW, { history: line(84, "UNCHECKED"), verdict: "SHIP" }).doctorGateReason, "Presenter script unchecked");

console.log("Compliance fixes: OS 28 holds what the law says, Fill puts the line first, the Doctor Gate can clear");
