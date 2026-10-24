/**
 * The live Script: Hydrate from Row fix, ruled by Tee on 2026-10-24, "Draft and
 * publish":
 *
 *   node n8n/tqo-v5/live-hydrate-fix/hydrate_fix.test.mjs
 *
 * The DT shim builds its fields object from its MAP only. The MAP has no
 * learning_objective and spells the b-roll column Broll Keywords, so Hydrate,
 * which read row.fields, sent the doctor no learning objective and no b-roll
 * for any Idea row that already carried a script. after.js is before.js with
 * the one line in replacement.json replaced, published as the version
 * manifest.json names and read back. Rows here are synthetic.
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
eq(M.before.versionId, "9f80c967-a649-488a-91ac-3f354178dfa8", "the fix was made on the version published that morning");
eq(before, read("../doctor-score-only/live/script_hydrate_from_row.js"), "before.js is the body the score-only doctor pinned from the same version");
eq(before.split(R.old).length, 2, "the replaced line occurs once");
eq(before.replace(R.old, () => R.new), after, "after.js is before.js with that one line replaced and nothing else");
eq(new RegExp("[" + String.fromCharCode(0x2013, 0x2014) + "]").test(R.new), false, "the new text carries no em or en dash");
eq(/\\u[0-9a-fA-F]{4}/.test(R.new), false, "the new text carries no escape for n8n to decode");

const shim = read("../doctor-score-only/live/dt_shim_idea_rows.js");
const RAW = { id: 7, status: "Idea", topic: "Topic 7", video_title: "Title 7", description: "Description 7", tags: "a", broll_keywords: "desk, notebook", learning_objective: "By the end, you will have one thing.", checklist: null, script: "The script." };
const run = (code, nodes, input) => {
  const it = input.map((json) => ({ json }));
  const $ = (n) => { const items = nodes[n].map((json) => ({ json })); return { first: () => items[0], all: () => items }; };
  return new Function("$", "$input", "$json", code)($, { first: () => it[0], all: () => it }, input[0]).map((i) => i.json);
};
const row = run(shim, {}, [RAW])[0];
const fixed = run(after, { "One Idea at a Time": [row] }, [row])[0];
const broken = run(before, { "One Idea at a Time": [row] }, [row])[0];
eq([fixed.learningObjective, fixed.broll], [RAW.learning_objective, RAW.broll_keywords], "the fixed body hands on the row's objective and b-roll");
eq([broken.learningObjective, broken.broll], ["", ""], "the old body dropped both");
for (const k of ["recordId", "title", "script", "description", "tags", "checklist", "__source"]) eq(fixed[k], broken[k], k + " is unchanged by the fix");
console.log("live hydrate fix: " + checks + " checks passed");
