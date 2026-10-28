/**
 * The compliance laws on the LIVE TQO FINAL V5, read from the export:
 *
 *   node n8n/tqo-v5/compliance/rebuild/rebuild.test.mjs
 *
 * This began as PR #367 rebuilt on live version dd734ea2 (ruled by Tee on
 * 2026-10-24): draft node bodies pinned to a copy of live plus a list of
 * replacements, and a Quality90 AI review that had to hold. Those drafts have
 * since been published, and on 2026-10-28 Tee ruled "Drop the AI review from
 * the publish gate", so the review requirement is gone from Preflight, the QC
 * Doctor Gate and OS 28. The drafts, the pinned copy and the replacement list
 * are deleted. Every check below runs on exportCode(name), read from
 * ../../exports/qEkGOUsNyVaRAmm6_active.json, so it cannot pass on code the
 * workflow does not run. Re-export the workflow and this test follows it.
 *
 *   OS 28: Publish Gate       title laws (whole word tension words, proper noun,
 *                             no dash), the C4 line in the first three lines,
 *                             "Not required" never passes, authorship is the
 *                             human approval approved:<sha256 of the script>.
 *   Script: Fill Run Fields   the line always first, once.
 *   QC Doctor Gate            the script doctor verdict (PASS or REPAIRED at
 *                             90 or more) plus the QC verdict; PASS WITH NOTES
 *                             holds; no AI review receipt is needed.
 *   Preflight: Can This Clear Mirrors OS 28 and the Doctor Gate through byte
 *                             copies of their rules, so it refuses to pay for
 *                             a row they will hold.
 *
 * Nothing here touches n8n or the network. Rows are synthetic.
 */

import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const read = (rel) => readFileSync(new URL(rel, import.meta.url), "utf8");
const sha = (s) => createHash("sha256").update(s, "utf8").digest("hex");
const EXPORT = JSON.parse(read("../../exports/qEkGOUsNyVaRAmm6_active.json"));
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
const liveNode = (name) => node(exportCode(name));

// What AI Review: Verified Result hands on. Since 2026-10-28 it gates nothing,
// so most rows below carry none; a receipt that exists must change nothing.
const SCRIPT = "A calm script about what changed this month.";
const noReview = {};
const passedReview = (script = SCRIPT) => ({ aiReviewPassed: true, artifactSha256: sha(script), scope: "script", score: 93, reviewId: "r1" });

// ---- OS 28: Publish Gate --------------------------------------------------
const OS28 = liveNode("OS 28: Publish Gate");
const BLOCK = ["YOUTUBE TAGS", "PINNED COMMENT", "TIKTOK", "INSTAGRAM", "FACEBOOK", "LINKEDIN 1", "X THREAD 1", "X VALUE POST", "SHORT SCRIPT 1", "THUMBNAIL TEXT"].join("\n\nbody\n\n");
const DESC_BODY = "A calm walk through what changed in the tooling this month and what it costs a manager who waits. ".repeat(2).trim();
const cleanRow = (edit = {}) => ({
  Channel: "The Quiet Operator", "Human Review": "approved:" + sha(SCRIPT), Script: SCRIPT,
  "Video Title": "The Quiet Mistake Managers Make With Copilot",
  Description: C4 + "\n\n" + DESC_BODY, Tags: "ai, career, the quiet operator", "AI Disclosure": "Disclosed in description",
  "QC Verdict": "SHIP", Show: "TQO", Season: 1, Episode: 3, "Asset Type": "Flagship", ...edit,
});
const runGate = (fields, { qcScore = 91, review = noReview } = {}) => OS28(dollar({
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

// A clean row clears the live gate, with no AI review receipt.
let out = runGate(cleanRow());
assert.deepEqual(out.os28_blocking, [], "the clean row clears the gate");
assert.equal(out.os28_allowed, true);

// Authorship, per the 2026-10-28 ruling: approval bound to the script hash
// clears without a review receipt, a receipt changes nothing either way, and a
// wrong or missing hash blocks.
assert.equal(runGate(cleanRow(), { review: noReview }).os28_allowed, true, "approval bound to the script hash clears with no receipt");
assert.equal(runGate(cleanRow(), { review: passedReview() }).os28_allowed, true, "a verified receipt changes nothing");
assert.equal(runGate(cleanRow(), { review: passedReview("another script") }).os28_allowed, true, "a receipt for another script neither blocks nor is required");
for (const [why, hr] of [
  ["approved for another script hash", "approved:" + sha("another")],
  ["ticked yes", "yes"], ["ticked true", "true"], ["empty", ""],
]) {
  assert.equal(runGate(cleanRow({ "Human Review": hr })).os28_allowed, false, "Human Review " + why + " blocks");
}
assert.equal(runGate(cleanRow({ Script: SCRIPT + " Edited." })).os28_allowed, false, "approval does not survive a script edit");
assert.equal(runGate(cleanRow({ "Human Review": "" }), { review: passedReview() }).os28_allowed, false, "a receipt alone does not clear authorship");
// The numeric floor and the waiver, unchanged.
assert.equal(runGate(cleanRow(), { qcScore: 89 }).os28_allowed, false, "a QC score of 89 blocks");
assert.equal(runGate(cleanRow(), { qcScore: 90 }).os28_allowed, true, "90 clears");
assert.equal(runGate(cleanRow({ "QC Verdict": "WAIVED" }), { qcScore: 100 }).os28_allowed, false, "a WAIVED QC verdict does not bypass the floor");

// "Not required" with no line at all is held.
const notRequired = cleanRow({ "AI Disclosure": "Not required", Description: DESC_BODY });
out = runGate(notRequired);
assert.equal(out.os28_allowed, false);
assert.equal(blocked(out, "disclosure: AI Disclosure is \"Not required\"").length, 1);
assert.equal(blocked(out, "disclosure: the Description does not contain the exact C4 line").length, 1);
assert.equal(runGate(cleanRow({ "AI Disclosure": "Not required" })).os28_allowed, false, "refused with the line in place too");

// The line below the first three lines is held.
const lowLine = cleanRow({ Description: "one\ntwo\nthree\n" + C4 + "\n" + DESC_BODY });
out = runGate(lowLine);
assert.equal(out.os28_allowed, false);
assert.equal(blocked(out, "disclosure: the C4 line is in the Description but not on a line of its own in its first three lines").length, 1);
for (const d of ["Disclaimer: " + C4 + "\n" + DESC_BODY, DESC_BODY + " " + C4, C4 + " (not really)\n" + DESC_BODY]) {
  assert.equal(runGate(cleanRow({ Description: d })).os28_allowed, false, JSON.stringify(d.slice(0, 40)));
}
assert.equal(runGate(cleanRow({ Description: C4 + "\r\n" + DESC_BODY })).os28_allowed, true, "a CRLF line ending is still the line");
assert.equal(runGate(cleanRow({ Description: "one\ntwo\n" + C4 + "\n" + DESC_BODY })).os28_allowed, true, "line three is inside");
assert.equal(runGate(cleanRow({ Description: C4.replace("consent.", "consent") + "\n\n" + DESC_BODY })).os28_allowed, false, "a variant is not the line");
assert.equal(runGate(cleanRow({ "AI Disclosure": "Disclosed on-screen + description" })).os28_allowed, true);
assert.equal(blocked(runGate(cleanRow({ "AI Disclosure": "" })), "disclosure: AI Disclosure is unset").length, 1);

// The title laws.
for (const [title, why] of [
  ["Copilot Settings Explained Simply", "no tension word"],
  ["Costume Ideas For Copilot Managers", "no tension word"],
  ["Lostwithiel And The Copilot Rollout", "no tension word"],
  ["Copilot Unstoppable Settings Guide", "no tension word"],
  // A word that ends in one: only the leading boundary holds these.
  ["Accost The Copilot Rollout Plan", "no tension word"],
  ["Copilot As A Backstop For Managers", "no tension word"],
  ["Nonstop Copilot Meetings For Managers", "no tension word"],
  ["Why Coster Diamonds Chose Copilot", "no tension word"],
  ["the quiet mistake managers make", "no proper noun"],
  ["The Quiet Mistake " + String.fromCharCode(0x2014) + " Copilot", "em or en dash"],
  ["The Quiet Mistake " + String.fromCharCode(0x2013) + " Copilot", "em or en dash"],
]) {
  out = runGate(cleanRow({ "Video Title": title }));
  assert.equal(out.os28_allowed, false, "gate: " + title);
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
  assert.deepEqual(blocked(runGate(cleanRow({ "Video Title": title })), "quality law titles:"), [], title);
}

// ---- Script: Fill Run Fields ----------------------------------------------
const FILL = liveNode("Script: Fill Run Fields");
const runFill = (description) => FILL(dollar({
  "Show Context: Script": [{ json: { show: "TQO", tableId: "t", tableRef: "r", channel: "The Quiet Operator" } }],
  "One Idea at a Time": [{ json: { fields: {} } }],
  "Originality Scan": [{ json: { recordId: "rec1", script: "A script.", title: "The Quiet Mistake", description, broll: ["desk"] } }],
}), undefined, undefined, require)[0].json.body.records[0].fields;
const head3 = (s) => s.split("\n").slice(0, 3).join("\n");
const loose = "Made with AI-assisted research.\n\n" + DESC_BODY;
assert.ok(head3(runFill(loose).Description).includes(C4));
const low = runFill("one\ntwo\nthree\nfour\n" + C4 + "\n" + DESC_BODY).Description;
assert.ok(low.startsWith(C4 + "\n\n"));
assert.equal(low.split(C4).length, 2, "the line appears once");
for (const d of ["intro\n" + C4 + "\n" + DESC_BODY, C4 + "\n" + C4 + "\n" + DESC_BODY, C4 + "\n\n" + DESC_BODY + "\n" + C4]) {
  const filled = runFill(d).Description;
  assert.ok(filled.startsWith(C4 + "\n\n"), JSON.stringify(d.slice(0, 30)));
  assert.equal(filled.split(C4).length, 2, "once: " + JSON.stringify(d.slice(0, 30)));
  assert.equal(runFill(filled).Description, filled, "a second fill changes nothing");
}
assert.equal(runFill(C4 + "\n\n" + DESC_BODY).Description, C4 + "\n\n" + DESC_BODY);
assert.equal(runFill(DESC_BODY)["AI Disclosure"], "Disclosed in description", "the fill writes the placed value");
for (const d of [loose, "", DESC_BODY, "one\ntwo\nthree\nfour\n" + C4]) {
  const filled = runFill(d).Description;
  const gate = runGate(cleanRow({ Description: filled + (filled.length < 120 ? "\n" + DESC_BODY : "") }));
  assert.equal(blocked(gate, "disclosure:").length, 0, "filled from: " + JSON.stringify(d.slice(0, 30)));
}

// ---- QC Doctor Gate, on the shapes the live lane produces ------------------
// A raw data table row goes through the live DT Shim: Ready Rows and the live
// Parse QC + Set Verdict, fed a model answer, before it reaches the gate.
const SHIM = liveNode("DT Shim: Ready Rows");
const PARSE_QC = liveNode("Parse QC + Set Verdict");
const GATE = liveNode("QC Doctor Gate");
const line = (score, v) => "2026-10-24T10:00:00Z | doctor " + score + "/100 " + v + " | originality 71/100 (rhythm 70, similarity 12) | gate Scripted at 1540 words";
const realDoctor = ({ history, total = 92, blockers = [], review = noReview } = {}) => {
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
  return GATE(dollar({ ...nodes, "Parse QC + Set Verdict": [{ json: qc }] }), undefined, undefined, require)[0].json;
};

// The gate needs a doctor PASS or REPAIRED at the floor plus a SHIP QC verdict,
// and no AI review receipt (ruled 2026-10-28).
let real = realDoctor({ history: line(90, "PASS") });
assert.equal(real.doctorGate, "READY_FOR_HUMAN_REVIEW", JSON.stringify(real));
assert.equal(real.qc_verdict, "SHIP");
assert.equal(real.qc_score, 92);
assert.equal(realDoctor({ history: line(96, "REPAIRED") }).doctorGate, "READY_FOR_HUMAN_REVIEW");
assert.equal(realDoctor({ history: line(90, "pass") }).doctorGate, "READY_FOR_HUMAN_REVIEW", "case does not matter");
assert.equal(realDoctor({ history: line(90.5, "PASS") }).doctorGate, "READY_FOR_HUMAN_REVIEW", "a decimal score at the floor");
assert.equal(realDoctor({ history: line(89.9, "PASS") }).doctorGate, "HOLD", "a decimal score under the floor");
// Only a doctor entry counts: the words "doctor 95/100 PASS" inside other
// text, with no bar in front, are not the doctor's verdict.
assert.equal(realDoctor({ history: "2026-10-24T10:00:00Z note: asked the doctor 95/100 PASS" }).doctorGate, "HOLD", "no bar, no doctor entry");
assert.notEqual(realDoctor({ history: line(100, "PASS") }).doctorGate, "RELEASE_ELIGIBLE", "never releases on its own");
// A QC line appended under the doctor line does not hide it.
assert.equal(realDoctor({ history: line(90, "PASS") + "\n2026-10-24T11:00:00Z | 92/100 SHIP | batch 8.0/10" }).doctorGate, "READY_FOR_HUMAN_REVIEW");
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
  [{ history: line(95, "PASS"), review: noReview }, "READY_FOR_HUMAN_REVIEW", "no AI review receipt is needed"],
  [{ history: line(95, "PASS"), review: passedReview() }, "READY_FOR_HUMAN_REVIEW", "a receipt changes nothing"],
  [{ history: line(95, "PASS"), review: passedReview("another script") }, "READY_FOR_HUMAN_REVIEW", "a receipt for another script changes nothing"],
  [{ history: line(89, "PASS"), review: passedReview() }, "HOLD", "a receipt does not lift a doctor score under 90"],
]) assert.equal(realDoctor(input).doctorGate, state, why);
assert.equal(realDoctor({ history: line(95, "PASS WITH NOTES") }).doctorGateReason, "Presenter script unchecked");
assert.equal(realDoctor({ history: line(95, "FAIL") + "\n" + line(95, "PASS") }).doctorGate, "READY_FOR_HUMAN_REVIEW", "a newer PASS after a FAIL clears");

// ---- Preflight: Can This Clear? --------------------------------------------
const PRE = liveNode("Preflight: Can This Clear?");
const preRow = (edit = {}) => ({
  Show: "TQO", Season: 1, Episode: 3, "Asset Type": "Flagship", "Video Title": "The Quiet Mistake Managers Make With Copilot",
  Description: C4 + "\n\n" + DESC_BODY, Script: SCRIPT, "AI Disclosure": "Disclosed in description",
  "Score History": line(95, "PASS"),
  "Human Review": "approved:" + sha(SCRIPT), aiReview: noReview, aiReviewIdentity: { artifactSha256: sha(SCRIPT) }, ...edit,
});
const runPre = (fields) => PRE(dollar({ "Show Context: Publish": [{ json: { channel: "The Quiet Operator" } }] }), undefined, fields, require)[0].json;
assert.equal(runPre(preRow())._preflightOk, true, "a clean row clears preflight with no AI review receipt");
const pre = runPre(preRow({ "AI Disclosure": "Not required" }));
assert.equal(pre._preflightOk, false);
assert.equal(pre._preflightBlockers.filter((b) => b.startsWith("AI Disclosure is \"Not required\"")).length, 1);
assert.equal(runPre(preRow({ "AI Disclosure": "Disclosed on-screen + description" }))._preflightOk, true);
assert.equal(runPre(preRow({ "AI Disclosure": "" }))._preflightBlockers.includes("AI Disclosure is unset"), true);
assert.equal(runPre(preRow({ "AI Disclosure": "Maybe" }))._preflightBlockers.includes("AI Disclosure is \"Maybe\""), true);
// Authorship in preflight, per the 2026-10-28 ruling: the approval is bound to
// the script hash (carried on aiReviewIdentity), and a receipt neither helps nor hurts.
assert.equal(runPre(preRow({ aiReview: passedReview() }))._preflightOk, true, "a receipt changes nothing");
assert.equal(runPre(preRow({ "Human Review": "yes" }))._preflightOk, false);
assert.equal(runPre(preRow({ "Human Review": "approved:" + sha("another") }))._preflightOk, false, "approval for another script hash blocks");
assert.equal(runPre(preRow({ "Human Review": "" }))._preflightOk, false);

// The mirrors, ruled 2026-10-24: Preflight refuses to pay for a run that OS 28
// or the QC Doctor Gate will hold. Each constant and pattern is a byte copy of
// its source line; the rule lines that use them are held to the gates by the
// behaviour comparison below.
const lineOf = (code, start) => {
  const found = code.split("\n").filter((l) => l.startsWith(start));
  assert.equal(found.length, 1, "one line starts with " + start);
  return found[0];
};
const preCode = exportCode("Preflight: Can This Clear?");
const os28Code = exportCode("OS 28: Publish Gate");
const doctorCode = exportCode("QC Doctor Gate");
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
const descriptions = [
  C4 + "\n\n" + DESC_BODY, "one\ntwo\n" + C4 + "\n" + DESC_BODY, "one\ntwo\nthree\n" + C4 + "\n" + DESC_BODY, DESC_BODY + " " + C4, DESC_BODY,
  // Whitespace both sides trim the same way, and text both sides refuse.
  C4 + "\r\n" + DESC_BODY, "   " + C4 + "   \n" + DESC_BODY, "\n\n\n" + C4 + "\n" + DESC_BODY, "\n\n\n\n" + C4 + "\n" + DESC_BODY,
  "one\n\n\n" + C4 + "\n" + DESC_BODY, C4 + " And more.\n" + DESC_BODY, "one\r\ntwo\r\n" + C4 + "\r\n" + DESC_BODY,
];
const histories = [line(95, "PASS"), line(90, "REPAIRED"), line(89.9, "PASS"), line(95, "PASS WITH NOTES"), line(95, "PASS") + "\n" + line(95, "FAIL"), "", "note: asked the doctor 95/100 PASS"];
const mirrored = (b) => /^(the C4 line|title carries|title has no|script doctor:)/.test(b);
let compared = 0;
for (const title of titles) for (const description of descriptions) {
  const preBlocks = runPre(preRow({ "Video Title": title, Description: description }))._preflightBlockers.filter((b) => /^(the C4 line|title carries|title has no)/.test(b));
  const gate = runGate(cleanRow({ "Video Title": title, Description: description }));
  const gateBlocks = gate.os28_blocking.filter((b) => b.startsWith("quality law titles:") || b.startsWith("disclosure: the C4 line") || b.startsWith("disclosure: the Description does not contain"));
  assert.equal(preBlocks.length > 0, gateBlocks.length > 0, "Preflight and OS 28 agree on " + JSON.stringify([title, description.slice(0, 20)]));
  compared++;
}
for (const history of histories) {
  const pre = runPre(preRow({ "Score History": history }))._preflightBlockers.filter((b) => b.startsWith("script doctor:"));
  const doctor = realDoctor({ history });
  assert.equal(pre.length > 0, doctor.doctorGateReason === "Presenter script unchecked", "Preflight and the Doctor Gate agree on " + JSON.stringify(history.slice(-40)));
  compared++;
}
assert.equal(compared, titles.length * descriptions.length + histories.length);
// A row that clears Preflight carries none of the mirrored blockers.
assert.deepEqual(runPre(preRow())._preflightBlockers.filter(mirrored), []);
// Preflight refuses to pay for each of these.
for (const edit of [{ "Video Title": "Copilot Settings Explained Simply" }, { Description: "one\ntwo\nthree\n" + C4 + "\n" + DESC_BODY }, { "Score History": "" }]) {
  assert.equal(runPre(preRow(edit))._preflightOk, false, "preflight refuses " + JSON.stringify(edit));
}

console.log("Live TQO FINAL V5: disclosure, title and doctor laws hold, authorship is the script hash approval, Preflight mirrors the gates");
