/**
 * The live Build Doctor Prompt checklist fix, ruled by Tee on 2026-10-24, "Same
 * wording, draft and publish":
 *
 *   node n8n/tqo-v5/live-doctor-checklist-fix/checklist_fix.test.mjs
 *
 * The score-only doctor's first run (execution 4292) held TQO row 49 on a
 * missing checklist that its script speaks, because the row stores none and the
 * prompt said "(none returned)". The full doctor in TQO FINAL V5 prints the same
 * line on its Hydrate path and could rewrite a script to add steps it already
 * has. after.js is before.js with the one text in replacement.json replaced.
 * Rows here are synthetic.
 */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";

const read = (rel) => readFileSync(new URL(rel, import.meta.url), "utf8");
const sha = (s) => createHash("sha256").update(s, "utf8").digest("hex");
const M = JSON.parse(read("./manifest.json"));
const R = JSON.parse(read("./replacement.json"));
const before = read("./before.js");
const after = read("./after.js");
let checks = 0;
const eq = (a, b, msg) => { assert.deepEqual(a, b, msg); checks++; };

eq(sha(before), M.before.sha256, "before.js is the body the manifest names");
eq(sha(after), M.after.sha256, "after.js is the body the manifest names");
eq(before, read("../doctor-score-only/live/build_doctor_prompt.js"), "before.js is the body the score-only doctor pinned, unchanged by the Hydrate publish");
eq(before.split(R.old).length, 2, "the replaced text occurs once");
eq(before.replace(R.old, () => R.new), after, "after.js is before.js with that text replaced and nothing else");
eq(R.new, read("../doctor-score-only/build.mjs").match(/SCORE_ONLY_CHECKLIST_EMPTY = "([^"]+)"/)[1], "the live wording is the score-only wording");
eq(new RegExp("[" + String.fromCharCode(0x2013, 0x2014) + "]").test(R.new), false, "no em or en dash");
eq(/\\u[0-9a-fA-F]{4}/.test(R.new), false, "no escape for n8n to decode");

const run = (code, d) => {
  const nodes = { "Show Context: Script": { show: "TQO", channel: "The Quiet Operator" }, "One Idea at a Time": { id: 1, fields: { Show: "The Quiet Operator", Idea: "x" } }, "DEVON Recall: Merge": { devonRecall: "" } };
  const $ = (n) => ({ first: () => ({ json: nodes[n] }), all: () => [{ json: nodes[n] }] });
  return new Function("$", "$input", "$json", code)($, { first: () => ({ json: d }) }, d)[0].json.claudeBody.messages[0].content;
};
const D = { recordId: 1, title: "T", description: "D", broll: "b", learningObjective: "You will learn one thing.", script: "S" };
const LINE = "CHECKLIST (keep these steps as spoken, in order): ";
eq(run(after, { ...D, checklist: [] }).includes(LINE + "(not stored on this row; judge the spoken steps in the script itself)"), true, "with no checklist stored the doctor is told to judge the spoken steps");
eq(run(before, { ...D, checklist: [] }).includes(LINE + "(none returned)"), true, "the old body said none returned");
eq(run(after, { ...D, checklist: ["one", "two", "three"] }), run(before, { ...D, checklist: ["one", "two", "three"] }), "with a checklist stored the message is unchanged");
eq(run(after, { ...D, learningObjective: "" }).includes("LEARNING OBJECTIVE (keep word for word, inside the first 30 seconds): (none returned)"), true, "the learning objective line is untouched");
console.log("live doctor checklist fix: " + checks + " checks passed");
