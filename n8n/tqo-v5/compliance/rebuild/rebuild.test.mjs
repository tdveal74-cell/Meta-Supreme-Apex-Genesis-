/**
 * PR #367 rebuilt on the live TQO FINAL V5, ruled by Tee on 2026-10-24:
 *
 *   node n8n/tqo-v5/compliance/rebuild/rebuild.test.mjs
 *
 * #367 merged on 2026-10-17 and was written into n8n draft 761302a2. It was
 * never published, and on 2026-10-21 the workflow was re-imported as version
 * dd734ea2 carrying the Quality90 layer and none of #367. That draft is gone
 * from the instance. live/ holds the node bodies of dd734ea2 byte for byte,
 * pinned by live/manifest.json. draft/ is live/ plus exactly the pairs in
 * replacements.json:
 *
 *   OS 28: Publish Gate       #367 gate 3c (title laws) and gate 5 (the C4
 *                             line in the first three lines, no "Not
 *                             required"); the tension word now whole words.
 *   Script: Fill Run Fields   #367: the line always first, once.
 *   QC Doctor Gate            #367's script doctor check, on top of the
 *                             Quality90 AI review; "PASS WITH NOTES" holds;
 *                             the doctor floor is the live 90.
 *   Preflight: Can This Clear "Not required" never passes, as in OS 28; and
 *                             it refuses to pay for a row OS 28 gates 3c and
 *                             5 or the QC Doctor Gate will hold, through byte
 *                             copies of their rules (ruled 2026-10-24).
 *
 * The fourth gap ruled with these, Parse QC shipping under the gate's floor,
 * is already closed live: Parse QC ships at 90 (SHIP_AT, 2026-10-19).
 *
 * Every Quality90 control in live/ must still hold in draft/; the tests below
 * check that too. Nothing here touches n8n or the network. Rows are synthetic.
 */

import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const read = (rel) => readFileSync(new URL(rel, import.meta.url), "utf8");
const sha = (s) => createHash("sha256").update(s, "utf8").digest("hex");
const MANIFEST = JSON.parse(read("./live/manifest.json"));
const REPLACEMENTS = JSON.parse(read("./replacements.json"));
const DRAFT = {
  "OS 28: Publish Gate": "os28_publish_gate.js",
  "Script: Fill Run Fields": "fill_run_fields.js",
  "QC Doctor Gate": "qc_doctor_gate.js",
  "Preflight: Can This Clear?": "preflight_can_this_clear.js",
};
const C4 = "Presented with a synthetic voice and synthetic likeness of Terrance Veal, used with his consent.";
const DASHES = new RegExp("[" + String.fromCharCode(0x2013, 0x2014) + "]");

// ---- live/ is the published version, byte for byte ---------------------------
assert.equal(MANIFEST.workflowId, "qEkGOUsNyVaRAmm6");
assert.equal(MANIFEST.versionId, "dd734ea2-3b17-4633-b7bd-a428b34403bb");
assert.equal(MANIFEST.activeVersionId, MANIFEST.versionId, "read when nothing sat in draft");
for (const [name, { file, sha256 }] of Object.entries(MANIFEST.nodes)) {
  assert.equal(sha(read("./live/" + file)), sha256, name + ": live copy matches the manifest");
}
const liveCode = (name) => read("./live/" + MANIFEST.nodes[name].file);

// ---- draft/ is live/ plus exactly the listed replacements --------------------
assert.deepEqual(Object.keys(REPLACEMENTS).sort(), Object.keys(DRAFT).sort());
for (const [name, file] of Object.entries(DRAFT)) {
  let code = liveCode(name);
  for (const [oldText, newText] of REPLACEMENTS[name]) {
    assert.equal(code.split(oldText).length, 2, name + ": a replaced fragment occurs once in live");
    code = code.replace(oldText, () => newText);
    assert.equal(DASHES.test(newText), false, name + ": an added fragment carries a literal dash");
    // n8n's tools have decoded \u escapes into the literal characters on the
    // way in before (the OS 28 DASH regex, 2026-10-17). Nothing added relies on one.
    assert.equal(/\\u[0-9a-fA-F]{4}/.test(newText), false, name + ": an added fragment carries a \\u escape");
  }
  assert.equal(read("./draft/" + file), code, name + ": the draft is live plus the listed replacements and nothing else");
}

const dollar = (nodes) => (name) => {
  if (!(name in nodes)) throw new Error("node did not run: " + name);
  const items = nodes[name];
  return { first: () => items[0], all: () => items };
};
const node = (code) => new Function("$", "$input", "$json", "require", code);
const draftNode = (name) => node(read("./draft/" + DRAFT[name]));
const liveNode = (name) => node(liveCode(name));

// A signed AI review that matches the script, as AI Review: Verified Result
// hands it on when the receipt verifies.
const SCRIPT = "A calm script about what changed this month.";
const passedReview = (script = SCRIPT) => ({ aiReviewPassed: true, artifactSha256: sha(script), scope: "script", score: 93, reviewId: "r1" });

// ---- OS 28: Publish Gate --------------------------------------------------
const OS28_NEW = draftNode("OS 28: Publish Gate");
const OS28_OLD = liveNode("OS 28: Publish Gate");
const BLOCK = ["YOUTUBE TAGS", "PINNED COMMENT", "TIKTOK", "INSTAGRAM", "FACEBOOK", "LINKEDIN 1", "X THREAD 1", "X VALUE POST", "SHORT SCRIPT 1", "THUMBNAIL TEXT"].join("\n\nbody\n\n");
const DESC_BODY = "A calm walk through what changed in the tooling this month and what it costs a manager who waits. ".repeat(2).trim();
const cleanRow = (edit = {}) => ({
  Channel: "The Quiet Operator", "Human Review": "approved:" + sha(SCRIPT), Script: SCRIPT,
  "Video Title": "The Quiet Mistake Managers Make With Copilot",
  Description: C4 + "\n\n" + DESC_BODY, Tags: "ai, career, the quiet operator", "AI Disclosure": "Disclosed in description",
  "QC Verdict": "SHIP", Show: "TQO", Season: 1, Episode: 3, "Asset Type": "Flagship", ...edit,
});
const runGate = (code, fields, { qcScore = 91, review = passedReview() } = {}) => code(dollar({
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

// A clean row clears both the live gate and the draft.
let out = runGate(OS28_NEW, cleanRow());
assert.deepEqual(out.os28_blocking, [], "the clean row clears the draft gate");
assert.equal(out.os28_allowed, true);
assert.equal(runGate(OS28_OLD, cleanRow()).os28_allowed, true, "and the live gate");

// Quality90 still holds in the draft, unchanged.
for (const [why, fields, opts] of [
  ["a QC score of 89", cleanRow(), { qcScore: 89 }],
  ["no AI review", cleanRow(), { review: {} }],
  ["an AI review of another script", cleanRow(), { review: passedReview("another script") }],
  ["Human Review ticked yes", cleanRow({ "Human Review": "yes" }), {}],
  ["Human Review approved for another hash", cleanRow({ "Human Review": "approved:" + sha("another") }), {}],
  ["a WAIVED QC verdict", cleanRow({ "QC Verdict": "WAIVED" }), { qcScore: 100 }],
]) {
  assert.equal(runGate(OS28_OLD, fields, opts).os28_allowed, runGate(OS28_NEW, fields, opts).os28_allowed, "live and draft agree on " + why);
}
assert.equal(runGate(OS28_NEW, cleanRow(), { qcScore: 89 }).os28_allowed, false);
assert.equal(runGate(OS28_NEW, cleanRow({ "Human Review": "yes" })).os28_allowed, false);
assert.equal(runGate(OS28_NEW, cleanRow(), { review: {} }).os28_allowed, false);

// "Not required" with no line at all clears the live gate. The draft holds it.
const notRequired = cleanRow({ "AI Disclosure": "Not required", Description: DESC_BODY });
assert.equal(runGate(OS28_OLD, notRequired).os28_allowed, true, "the live gate lets a presenter-led episode through with no disclosure");
out = runGate(OS28_NEW, notRequired);
assert.equal(out.os28_allowed, false);
assert.equal(blocked(out, "disclosure: AI Disclosure is \"Not required\"").length, 1);
assert.equal(blocked(out, "disclosure: the Description does not contain the exact C4 line").length, 1);
assert.equal(runGate(OS28_NEW, cleanRow({ "AI Disclosure": "Not required" })).os28_allowed, false, "refused with the line in place too");

// The line below the first three lines clears live. The draft holds it.
const lowLine = cleanRow({ Description: "one\ntwo\nthree\n" + C4 + "\n" + DESC_BODY });
assert.equal(runGate(OS28_OLD, lowLine).os28_allowed, true, "the live gate accepts the line anywhere");
out = runGate(OS28_NEW, lowLine);
assert.equal(out.os28_allowed, false);
assert.equal(blocked(out, "disclosure: the C4 line is in the Description but not on a line of its own in its first three lines").length, 1);
for (const d of ["Disclaimer: " + C4 + "\n" + DESC_BODY, DESC_BODY + " " + C4, C4 + " (not really)\n" + DESC_BODY]) {
  assert.equal(runGate(OS28_NEW, cleanRow({ Description: d })).os28_allowed, false, JSON.stringify(d.slice(0, 40)));
}
assert.equal(runGate(OS28_NEW, cleanRow({ Description: C4 + "\r\n" + DESC_BODY })).os28_allowed, true, "a CRLF line ending is still the line");
assert.equal(runGate(OS28_NEW, cleanRow({ Description: "one\ntwo\n" + C4 + "\n" + DESC_BODY })).os28_allowed, true, "line three is inside");
assert.equal(runGate(OS28_NEW, cleanRow({ Description: C4.replace("consent.", "consent") + "\n\n" + DESC_BODY })).os28_allowed, false, "a variant is not the line");
assert.equal(runGate(OS28_NEW, cleanRow({ "AI Disclosure": "Disclosed on-screen + description" })).os28_allowed, true);
assert.equal(blocked(runGate(OS28_NEW, cleanRow({ "AI Disclosure": "" })), "disclosure: AI Disclosure is unset").length, 1);

// The title laws. The live gate holds none of these.
for (const [title, why] of [
  ["Copilot Settings Explained Simply", "no tension word"],
  ["Costume Ideas For Copilot Managers", "no tension word"],
  ["Lostwithiel And The Copilot Rollout", "no tension word"],
  ["Copilot Unstoppable Settings Guide", "no tension word"],
  // A word that ends in one: only the leading boundary holds these.
  ["Accost The Copilot Rollout Plan", "no tension word"],
  ["Copilot As A Backstop For Managers", "no tension word"],
  ["Nonstop Copilot Meetings For Managers", "no tension word"],
  ["the quiet mistake managers make", "no proper noun"],
  ["The Quiet Mistake " + String.fromCharCode(0x2014) + " Copilot", "em or en dash"],
  ["The Quiet Mistake " + String.fromCharCode(0x2013) + " Copilot", "em or en dash"],
]) {
  assert.equal(runGate(OS28_OLD, cleanRow({ "Video Title": title })).os28_allowed, true, "live gate: " + title);
  out = runGate(OS28_NEW, cleanRow({ "Video Title": title }));
  assert.equal(out.os28_allowed, false, "draft gate: " + title);
  assert.ok(blocked(out, "quality law titles:")[0].includes(why), title + " -> " + out.os28_blocking.join(" / "));
}
// Whole words, with a plain inflection still counting.
for (const title of [
  "The Mistakes Managers Make With Copilot", "Why Copilot Stopped Saving You Time", "What Copilot Costs A Manager",
  "Quietly Replaced By Copilot", "The Truth About Copilot", "No One Told Managers About Copilot",
  "Copilot Lied About Your Calendar", "Before Copilot Takes Your Desk",
  // The live pattern passed these on a substring; the whole-word one must too.
  "The Quieter Way Copilot Replaces You", "Mistaken About Copilot", "The Wrongful Copilot Rollout",
  "The Truthful Copilot Review",
]) {
  assert.deepEqual(blocked(runGate(OS28_NEW, cleanRow({ "Video Title": title })), "quality law titles:"), [], title);
}

// ---- Script: Fill Run Fields ----------------------------------------------
const FILL_NEW = draftNode("Script: Fill Run Fields");
const FILL_OLD = liveNode("Script: Fill Run Fields");
const runFill = (code, description) => code(dollar({
  "Show Context: Script": [{ json: { show: "TQO", tableId: "t", tableRef: "r", channel: "The Quiet Operator" } }],
  "One Idea at a Time": [{ json: { fields: {} } }],
  "Originality Scan": [{ json: { recordId: "rec1", script: "A script.", title: "The Quiet Mistake", description, broll: ["desk"] } }],
}), undefined, undefined, require)[0].json.body.records[0].fields;
const head3 = (s) => s.split("\n").slice(0, 3).join("\n");
const loose = "Made with AI-assisted research.\n\n" + DESC_BODY;
assert.ok(!runFill(FILL_OLD, loose).Description.includes(C4), "the live fill skips the line after a looser phrase");
assert.ok(head3(runFill(FILL_NEW, loose).Description).includes(C4));
const low = runFill(FILL_NEW, "one\ntwo\nthree\nfour\n" + C4 + "\n" + DESC_BODY).Description;
assert.ok(low.startsWith(C4 + "\n\n"));
assert.equal(low.split(C4).length, 2, "the line appears once");
for (const d of ["intro\n" + C4 + "\n" + DESC_BODY, C4 + "\n" + C4 + "\n" + DESC_BODY, C4 + "\n\n" + DESC_BODY + "\n" + C4]) {
  const filled = runFill(FILL_NEW, d).Description;
  assert.ok(filled.startsWith(C4 + "\n\n"), JSON.stringify(d.slice(0, 30)));
  assert.equal(filled.split(C4).length, 2, "once: " + JSON.stringify(d.slice(0, 30)));
  assert.equal(runFill(FILL_NEW, filled).Description, filled, "a second fill changes nothing");
}
assert.equal(runFill(FILL_NEW, C4 + "\n\n" + DESC_BODY).Description, C4 + "\n\n" + DESC_BODY);
assert.equal(runFill(FILL_NEW, DESC_BODY)["AI Disclosure"], "Disclosed in description", "the fill writes the placed value");
for (const d of [loose, "", DESC_BODY, "one\ntwo\nthree\nfour\n" + C4]) {
  const filled = runFill(FILL_NEW, d).Description;
  const gate = runGate(OS28_NEW, cleanRow({ Description: filled + (filled.length < 120 ? "\n" + DESC_BODY : "") }));
  assert.equal(blocked(gate, "disclosure:").length, 0, "filled from: " + JSON.stringify(d.slice(0, 30)));
}

// ---- QC Doctor Gate, on the shapes the live lane produces ------------------
// A raw data table row goes through the live DT Shim: Ready Rows and the live
// Parse QC + Set Verdict, fed a model answer, before it reaches the gate.
const SHIM = node(liveCode("DT Shim: Ready Rows"));
const PARSE_QC = node(liveCode("Parse QC + Set Verdict"));
const GATE_NEW = draftNode("QC Doctor Gate");
const GATE_OLD = liveNode("QC Doctor Gate");
const line = (score, v) => "2026-10-24T10:00:00Z | doctor " + score + "/100 " + v + " | originality 71/100 (rhythm 70, similarity 12) | gate Scripted at 1540 words";
const realDoctor = (code, { history, total = 92, blockers = [], review = passedReview() } = {}) => {
  const raw = { id: 7, createdAt: "2026-10-23T10:00:00Z", updatedAt: "2026-10-24T10:00:00Z", status: "Ready", system_status: "",
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
  return code(dollar({ ...nodes, "Parse QC + Set Verdict": [{ json: qc }] }), undefined, undefined, require)[0].json;
};

// The live gate clears on the QC verdict and the AI review alone; the script
// doctor's verdict plays no part.
assert.equal(realDoctor(GATE_OLD, { history: line(95, "PASS") }).doctorGate, "READY_FOR_HUMAN_REVIEW");
assert.equal(realDoctor(GATE_OLD, { history: line(95, "PASS WITH NOTES") }).doctorGate, "READY_FOR_HUMAN_REVIEW", "live: PASS WITH NOTES clears");
assert.equal(realDoctor(GATE_OLD, {}).doctorGate, "READY_FOR_HUMAN_REVIEW", "live: no doctor line at all clears");

// The draft needs a doctor PASS or REPAIRED at the floor as well.
let real = realDoctor(GATE_NEW, { history: line(90, "PASS") });
assert.equal(real.doctorGate, "READY_FOR_HUMAN_REVIEW", JSON.stringify(real));
assert.equal(real.qc_verdict, "SHIP");
assert.equal(real.qc_score, 92);
assert.equal(realDoctor(GATE_NEW, { history: line(96, "REPAIRED") }).doctorGate, "READY_FOR_HUMAN_REVIEW");
assert.equal(realDoctor(GATE_NEW, { history: line(90, "pass") }).doctorGate, "READY_FOR_HUMAN_REVIEW", "case does not matter");
assert.equal(realDoctor(GATE_NEW, { history: line(90.5, "PASS") }).doctorGate, "READY_FOR_HUMAN_REVIEW", "a decimal score at the floor");
assert.equal(realDoctor(GATE_NEW, { history: line(89.9, "PASS") }).doctorGate, "HOLD", "a decimal score under the floor");
// Only a doctor entry counts: the words "doctor 95/100 PASS" inside other
// text, with no bar in front, are not the doctor's verdict.
assert.equal(realDoctor(GATE_NEW, { history: "2026-10-24T10:00:00Z note: asked the doctor 95/100 PASS" }).doctorGate, "HOLD", "no bar, no doctor entry");
assert.notEqual(realDoctor(GATE_NEW, { history: line(100, "PASS") }).doctorGate, "RELEASE_ELIGIBLE", "never releases on its own");
// A QC line appended under the doctor line does not hide it.
assert.equal(realDoctor(GATE_NEW, { history: line(90, "PASS") + "\n2026-10-24T11:00:00Z | 92/100 SHIP | batch 8.0/10" }).doctorGate, "READY_FOR_HUMAN_REVIEW");
for (const [input, state, why] of [
  [{}, "HOLD", "no score history"],
  [{ history: "" }, "HOLD", "an empty history"],
  [{ history: line(95, "PASS WITH NOTES") }, "HOLD", "PASS WITH NOTES"],
  [{ history: line(95, "PASS_WITH_NOTES") }, "HOLD", "PASS_WITH_NOTES"],
  [{ history: line(95, "PASS-ISH") }, "HOLD", "PASS-ISH is not PASS"],
  [{ history: line(95, "UNCHECKED") }, "HOLD", "the doctor did not run"],
  [{ history: line(95, "FAIL") }, "HOLD", "a failing doctor verdict"],
  [{ history: line(89, "PASS") }, "HOLD", "a doctor score under the live floor of 90"],
  [{ history: line(95, "PASS") + "\n" + line(95, "FAIL") }, "HOLD", "the newest doctor line counts"],
  [{ history: line(95, "PASS"), total: 89 }, "REVISE", "a QC total under 90"],
  [{ history: line(95, "PASS"), blockers: ["claim unsourced"] }, "REVISE", "a QC hard blocker"],
  [{ history: line(95, "PASS"), review: {} }, "EVIDENCE_REQUIRED", "no AI review"],
  [{ history: line(95, "PASS"), review: passedReview("another script") }, "EVIDENCE_REQUIRED", "an AI review of another script"],
]) assert.equal(realDoctor(GATE_NEW, input).doctorGate, state, why);
assert.equal(realDoctor(GATE_NEW, { history: line(95, "PASS WITH NOTES") }).doctorGateReason, "Presenter script unchecked");
assert.equal(realDoctor(GATE_NEW, { history: line(95, "FAIL") + "\n" + line(95, "PASS") }).doctorGate, "READY_FOR_HUMAN_REVIEW", "a newer PASS after a FAIL clears");

// ---- Preflight: Can This Clear? --------------------------------------------
const PRE_NEW = draftNode("Preflight: Can This Clear?");
const PRE_OLD = liveNode("Preflight: Can This Clear?");
const preRow = (edit = {}) => ({
  Show: "TQO", Season: 1, Episode: 3, "Asset Type": "Flagship", "Video Title": "The Quiet Mistake Managers Make With Copilot",
  Description: C4 + "\n\n" + DESC_BODY, Script: SCRIPT, "AI Disclosure": "Disclosed in description",
  "Score History": line(95, "PASS"),
  "Human Review": "approved:" + sha(SCRIPT), aiReview: passedReview(), ...edit,
});
const runPre = (code, fields) => code(dollar({ "Show Context: Publish": [{ json: { channel: "The Quiet Operator" } }] }), undefined, fields, require)[0].json;
assert.equal(runPre(PRE_NEW, preRow())._preflightOk, true, "a clean row clears the draft preflight");
assert.equal(runPre(PRE_OLD, preRow())._preflightOk, true, "and the live one");
assert.equal(runPre(PRE_OLD, preRow({ "AI Disclosure": "Not required" }))._preflightOk, true, "live preflight accepts Not required");
const pre = runPre(PRE_NEW, preRow({ "AI Disclosure": "Not required" }));
assert.equal(pre._preflightOk, false);
assert.equal(pre._preflightBlockers.filter((b) => b.startsWith("AI Disclosure is \"Not required\"")).length, 1);
assert.equal(runPre(PRE_NEW, preRow({ "AI Disclosure": "Disclosed on-screen + description" }))._preflightOk, true);
assert.equal(runPre(PRE_NEW, preRow({ "AI Disclosure": "" }))._preflightBlockers.includes("AI Disclosure is unset"), true);
assert.equal(runPre(PRE_NEW, preRow({ "AI Disclosure": "Maybe" }))._preflightBlockers.includes("AI Disclosure is \"Maybe\""), true);
// Quality90 still holds in the draft preflight.
assert.equal(runPre(PRE_NEW, preRow({ aiReview: {} }))._preflightOk, false);
assert.equal(runPre(PRE_NEW, preRow({ "Human Review": "yes" }))._preflightOk, false);

// The mirrors, ruled 2026-10-24: Preflight refuses to pay for a run that OS 28
// or the QC Doctor Gate will hold. Each mirrored rule is a byte copy of its
// source line, so the two cannot drift apart.
const lineOf = (code, start) => {
  const found = code.split("\n").filter((l) => l.startsWith(start));
  assert.equal(found.length, 1, "one line starts with " + start);
  return found[0];
};
const preCode = read("./draft/" + DRAFT["Preflight: Can This Clear?"]);
const os28Code = read("./draft/" + DRAFT["OS 28: Publish Gate"]);
const doctorCode = read("./draft/" + DRAFT["QC Doctor Gate"]);
for (const start of ["const C4_LINE = ", "const DASH = ", "const tensionWord = ", "const properNoun = "]) {
  assert.equal(lineOf(preCode, start), lineOf(os28Code, start), "Preflight copies OS 28: " + start);
}
for (const start of ["const DOCTOR_FLOOR = ", "const doctorLines = ", "const doctorLine = ", "const doctorScore = ", "const doctorVerdict = "]) {
  assert.equal(lineOf(preCode, start), lineOf(doctorCode, start), "Preflight copies the QC Doctor Gate: " + start);
}
// And they agree in behaviour: Preflight holds exactly the rows the two gates
// hold for these reasons, and lets through the rows they let through.
const titles = [
  "The Quiet Mistake Managers Make With Copilot", "Copilot Settings Explained Simply", "Costume Ideas For Copilot Managers",
  "Accost The Copilot Rollout Plan", "the quiet mistake managers make", "The Quiet Mistake " + String.fromCharCode(0x2014) + " Copilot",
  "The Mistakes Managers Make With Copilot", "Mistaken About Copilot", "Three Leadership Failures Every NCO Should Audit",
];
const descriptions = [C4 + "\n\n" + DESC_BODY, "one\ntwo\n" + C4 + "\n" + DESC_BODY, "one\ntwo\nthree\n" + C4 + "\n" + DESC_BODY, DESC_BODY + " " + C4, DESC_BODY];
const histories = [line(95, "PASS"), line(90, "REPAIRED"), line(89.9, "PASS"), line(95, "PASS WITH NOTES"), line(95, "PASS") + "\n" + line(95, "FAIL"), "", "note: asked the doctor 95/100 PASS"];
const mirrored = (b) => /^(the C4 line|title |script doctor:)/.test(b);
let compared = 0;
for (const title of titles) for (const description of descriptions) {
  const preBlocks = runPre(PRE_NEW, preRow({ "Video Title": title, Description: description }))._preflightBlockers.filter((b) => /^(the C4 line|title )/.test(b));
  const gate = runGate(OS28_NEW, cleanRow({ "Video Title": title, Description: description }));
  const gateBlocks = gate.os28_blocking.filter((b) => b.startsWith("quality law titles:") || b.startsWith("disclosure: the C4 line") || b.startsWith("disclosure: the Description does not contain"));
  assert.equal(preBlocks.length > 0, gateBlocks.length > 0, "Preflight and OS 28 agree on " + JSON.stringify([title, description.slice(0, 20)]));
  compared++;
}
for (const history of histories) {
  const pre = runPre(PRE_NEW, preRow({ "Score History": history }))._preflightBlockers.filter((b) => b.startsWith("script doctor:"));
  const doctor = realDoctor(GATE_NEW, { history });
  assert.equal(pre.length > 0, doctor.doctorGateReason === "Presenter script unchecked", "Preflight and the Doctor Gate agree on " + JSON.stringify(history.slice(-40)));
  compared++;
}
assert.equal(compared, titles.length * descriptions.length + histories.length);
// A row that clears Preflight carries none of the mirrored blockers.
assert.deepEqual(runPre(PRE_NEW, preRow())._preflightBlockers.filter(mirrored), []);
// The live Preflight paid for every one of these.
for (const edit of [{ "Video Title": "Copilot Settings Explained Simply" }, { Description: "one\ntwo\nthree\n" + C4 + "\n" + DESC_BODY }, { "Score History": "" }]) {
  assert.equal(runPre(PRE_OLD, preRow(edit))._preflightOk, true, "live preflight pays for " + JSON.stringify(edit));
  assert.equal(runPre(PRE_NEW, preRow(edit))._preflightOk, false, "draft preflight refuses " + JSON.stringify(edit));
}

console.log("#367 rebuilt on live dd734ea2: disclosure, title and doctor laws hold, Quality90 untouched, the four gaps closed");
