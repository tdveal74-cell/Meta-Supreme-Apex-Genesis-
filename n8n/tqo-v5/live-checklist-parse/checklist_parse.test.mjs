/**
 * The live Script: Hydrate from Row checklist parse, ruled by Tee on 2026-10-26
 * on a card, "Fill and parse":
 *
 *   node n8n/tqo-v5/live-checklist-parse/checklist_parse.test.mjs
 *
 * The checklist column of both content tables is text, so a list stored there
 * arrives as a JSON string, and Hydrate's list line kept arrays only: a stored
 * checklist reached the doctor as none. after.js is before.js with the one line
 * in replacement.json replaced. before.js is the live Hydrate at the version the
 * manifest names, which is the body the 2026-10-24 fix published. The
 * score-only doctor makes the same replacement from the same file. Rows here
 * are synthetic, except the four steps, which are TQO 49's.
 */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { CHECKLIST_PARSE } from "../doctor-score-only/build.mjs";

const read = (rel) => readFileSync(new URL(rel, import.meta.url), "utf8");
const sha = (s) => createHash("sha256").update(s, "utf8").digest("hex");
const M = JSON.parse(read("./manifest.json"));
const R = JSON.parse(read("./replacement.json"));
const before = read("./before.js");
const after = read("./after.js");
let checks = 0;
const eq = (a, b, msg) => { assert.deepEqual(a, b, msg); checks++; };

// ---- The bodies are the ones the manifest names --------------------------------
eq(M.workflowId, "qEkGOUsNyVaRAmm6", "TQO FINAL V5");
eq(M.node, "Script: Hydrate from Row", "the node it changes");
eq(sha(before), M.before.sha256, "before.js is the body the manifest names");
eq(sha(after), M.after.sha256, "after.js is the body the manifest names");
eq(before, read("../live-hydrate-fix/after.js"), "before.js is the Hydrate the 2026-10-24 fix published");
eq(M.before.versionId, "fd873714-7acf-482b-8ab1-e101e1afb5ac", "and the version it starts from is the one live when this was built");
eq(before.split(R.old).length, 2, "the replaced line occurs once");
eq(before.replace(R.old, () => R.new), after, "after.js is before.js with that line replaced and nothing else");
eq(R, CHECKLIST_PARSE, "the score-only doctor makes the same replacement");
eq(new RegExp("[" + String.fromCharCode(0x2013, 0x2014) + "]").test(after), false, "after.js carries no em or en dash");
eq(/\\u[0-9a-fA-F]{4}/.test(R.new), false, "the new text carries no escape for n8n to decode");

// ---- Behaviour, through the live shim -------------------------------------------
const shim = read("../doctor-score-only/live/dt_shim_idea_rows.js");
const run = (code, nodes, input) => {
  const it = input.map((json) => ({ json }));
  const $ = (n) => { const items = nodes[n].map((json) => ({ json })); return { first: () => items[0], all: () => items }; };
  return new Function("$", "$input", "$json", code)($, { first: () => it[0], all: () => it }, input[0]).map((i) => i.json);
};
const RAW = { id: 7, status: "Idea", topic: "Topic 7", video_title: "Title 7", description: "Description 7", tags: "a", broll_keywords: "desk, notebook", learning_objective: "By the end, you will have one thing.", checklist: null, script: "The script." };
const STEPS = ["Choose one recurring problem.", "Show the decision you made.", "Separate evidence from proposals.", "Prepare a shareable sample."];
const hydrate = (code, checklist) => {
  const row = run(shim, {}, [{ ...RAW, checklist }])[0];
  return run(code, { "One Idea at a Time": [row] }, [row])[0];
};

eq(hydrate(after, JSON.stringify(STEPS)).checklist, STEPS, "a list stored as JSON text reaches the doctor as the list");
eq(hydrate(before, JSON.stringify(STEPS)).checklist, [], "the live body read the same stored list as none, which is the defect");
eq(hydrate(after, STEPS).checklist, STEPS, "an array still reads as the array");
eq(hydrate(after, JSON.stringify([" a ", "", "b"])).checklist, ["a", "b"], "steps are trimmed and empty ones dropped, as an array's always were");
for (const [label, v] of [["null", null], ["empty text", ""], ["text that is not JSON", "Choose one recurring problem."], ["a JSON string", "\"one step\""], ["a JSON object", "{\"a\":1}"], ["a JSON number", "4"]]) {
  eq(hydrate(after, v).checklist, [], label + " reads as no checklist, as before");
}
// Pinned after the verifier on 27f3d32 found three mutants no test killed.
eq(hydrate(after, "  \n" + JSON.stringify(STEPS) + "\n ").checklist, STEPS, "JSON text with whitespace around it still reads as the list");
eq(hydrate(after, "[1,{\"a\":1},true]").checklist, ["1", "[object Object]", "true"], "elements that are not text are turned into text, as an array's always were");
eq(hydrate(after, JSON.stringify(JSON.stringify(STEPS))).checklist, [], "JSON encoded twice is one string, not a list, and reads as none");
for (const v of [null, JSON.stringify(STEPS), "not json"]) {
  const a = hydrate(after, v), b = hydrate(before, v);
  for (const k of ["recordId", "title", "script", "description", "tags", "broll", "learningObjective", "__source"]) eq(a[k], b[k], k + " is unchanged by the parse");
}

// ---- What the doctor is then shown ----------------------------------------------
// The live Build Doctor Prompt, as the grounding draft carries it, prints a
// stored checklist as numbered steps in place of the "not stored" note.
const prompt = read("../live-doctor-grounding/after.js");
const user = (d) => run(prompt, { "Show Context: Script": [{ show: "TQO", channel: "The Quiet Operator" }], "One Idea at a Time": [{ id: 7 }], "DEVON Recall: Merge": [{ devonRecall: "" }] }, [d])[0].claudeBody.messages[0].content;
const shown = user(hydrate(after, JSON.stringify(STEPS)));
eq(shown.includes("CHECKLIST (keep these steps as spoken, in order): 1. Choose one recurring problem. 2. Show the decision you made. 3. Separate evidence from proposals. 4. Prepare a shareable sample."), true, "the doctor is shown the four steps, numbered, in order");
eq(user(hydrate(before, JSON.stringify(STEPS))).includes("(not stored on this row; judge the spoken steps in the script itself)"), true, "where the live body told it none was stored");

eq(M.rollbackAtPublish, "publish " + M.before.versionId, "at publish, rollback was the version before");
eq(!M.rollback.startsWith("publish ") && M.rollback.includes(M.before.versionId.slice(0, 8) + " on 2026-10-29 returned 404") && M.rollback.includes((M.node || M.before.node) + " in the live version"), true, "the before version is pruned, so rollback is an edit, not a publish");
console.log("live checklist parse: " + checks + " checks passed");
