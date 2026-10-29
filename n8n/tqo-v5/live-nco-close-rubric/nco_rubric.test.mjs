/**
 * The NCO comments question in the rubric lines, ruled by Tee on 2026-10-26 on
 * a card, "Move it next to the rules":
 *
 *   node n8n/tqo-v5/live-nco-close-rubric/nco_rubric.test.mjs
 *
 * The NCO preservation rules say one specific question for the comments is not
 * bait. In execution 4512 two of three reads still held NCO 30 for its closing
 * comments question, citing the later "No engagement bait" and "close 15"
 * lines and never that sentence. after.js is before.js with those two lines
 * given an NCO clause each. before.js is the live Build Doctor Prompt at the
 * version the manifest names. The score-only doctor makes the same two
 * replacements from the same file. Rows here are synthetic.
 */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { NCO_RUBRIC } from "../doctor-score-only/build.mjs";

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
eq(M.node, "Build Doctor Prompt", "the node it changes");
eq(sha(before), M.before.sha256, "before.js is the body the manifest names");
eq(sha(after), M.after.sha256, "after.js is the body the manifest names");
eq(before, read("../live-doctor-grounding/after.js"), "before.js is the Build Doctor Prompt the grounding published");
eq(M.before.versionId, JSON.parse(read("../live-doctor-grounding/manifest.json")).after.versionId, "and the version it starts from is the one that publish read back");
eq(R.pairs.length, 2, "two lines change");
for (const p of R.pairs) eq(before.split(p.old).length, 2, "each replaced line occurs once: " + p.old.trim().slice(0, 30));
eq(R.pairs.reduce((s, p) => s.replace(p.old, () => p.new), before), after, "after.js is before.js with those two lines replaced and nothing else");
eq(R, NCO_RUBRIC, "the score-only doctor makes the same replacements");
const DASH = new RegExp("[" + String.fromCharCode(0x2013, 0x2014) + "]");
eq(DASH.test(after), false, "after.js carries no em or en dash");
eq(/\\u20[12][34]/.test(JSON.stringify(R)), false, "the new text carries no escaped dash for n8n to decode");

// ---- What the doctor is told ------------------------------------------------------
const run = (code, show) => {
  const d = { recordId: 7, title: "T", description: "D", broll: "b", learningObjective: "LO", checklist: [], script: "Words. In the comments, which step will you try first?" };
  const nodes = { "Show Context: Script": { show, channel: show === "NCO" ? "NCO Forge" : "The Quiet Operator" }, "One Idea at a Time": { id: 7 }, "DEVON Recall: Merge": { devonRecall: "" } };
  const $ = (n) => ({ first: () => ({ json: nodes[n] }) });
  return new Function("$", "$json", code)($, d)[0].json.claudeBody;
};
const BAIT = "No engagement bait. No Agree? No Thoughts? No What would you add?";
const CLOSE = "close 15: a clean implication or a real action. Never a solicitation.";
for (const show of ["TQO", "NCO"]) {
  const a = run(after, show), b = run(before, show);
  const as = a.system.split("\n"), bs = b.system.split("\n");
  eq(as.length, bs.length, show + ": no line is added or removed");
  const changed = as.map((l, i) => (l === bs[i] ? null : i)).filter((i) => i !== null);
  if (show === "NCO") {
    eq(changed.map((i) => bs[i]), [BAIT, CLOSE], "NCO: only the bait line and the close 15 line change");
    eq(changed.map((i) => as[i]), [BAIT + " For NCO, one specific question for the comments is allowed and is not bait.", CLOSE + " For NCO, one specific question for the comments is allowed."], "NCO: each says one specific comments question is allowed");
  } else {
    eq(changed, [], "TQO: the system text is unchanged");
  }
  eq(a.messages, b.messages, show + ": the user message is unchanged");
  eq({ ...a, system: null }, { ...b, system: null }, show + ": every other field of the request is unchanged");
}
eq(/remove|cut it|subscribe/i.test(R.pairs.map((p) => p.new).join(" ")), false, "the clauses tell the doctor to remove nothing and say nothing of a subscribe line");

eq(M.rollbackAtPublish, "publish " + M.before.versionId, "at publish, rollback was the version before");
eq(!M.rollback.startsWith("publish ") && M.rollback.includes(M.before.versionId.slice(0, 8) + " on 2026-10-29 returned 404") && M.rollback.includes((M.node || M.before.node) + " in the live version"), true, "the before version is pruned, so rollback is an edit, not a publish");
console.log("live NCO close rubric: " + checks + " checks passed");
