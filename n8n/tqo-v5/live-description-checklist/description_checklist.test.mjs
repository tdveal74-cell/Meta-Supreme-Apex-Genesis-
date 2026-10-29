/**
 * The checklist in the description, ruled by Tee on 2026-10-26 on a card, "Add
 * it in Fill Run Fields":
 *
 *   node n8n/tqo-v5/live-description-checklist/description_checklist.test.mjs
 *
 * Build Script Prompt tells the TQO writer: "Leave the checklist out; the
 * pipeline writes it into the description from the checklist field." A sticky
 * note in TQO FINAL V5 names Script: Fill Run Fields as the node that does it.
 * Its code never read the checklist, and a verifier on 2026-10-25 found all 24
 * stored descriptions without the steps. after.js is before.js with one block
 * added after the disclosure step. before.js is the live node at the version
 * the manifest names. Rows here are synthetic, except the four steps, which are
 * TQO 49's.
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
const ok = (v, msg) => { assert.ok(v, msg); checks++; };

// ---- The bodies are the ones the manifest names --------------------------------
eq(M.workflowId, "qEkGOUsNyVaRAmm6", "TQO FINAL V5");
eq(M.node, "Script: Fill Run Fields", "the node it changes");
eq(sha(before), M.before.sha256, "before.js is the body the manifest names");
eq(sha(after), M.after.sha256, "after.js is the body the manifest names");
eq(M.before.versionId, "fd873714-7acf-482b-8ab1-e101e1afb5ac", "the version it starts from");
eq(before.split(R.old).length, 2, "the anchor line occurs once");
ok(R.new.startsWith(R.old), "the replacement keeps the anchor line and only adds after it");
eq(before.replace(R.old, () => R.new), after, "after.js is before.js with that block added and nothing else");
eq(/checklist/i.test(before.replace(/\/\/[^\n]*/g, "")), false, "the live code never read the checklist, which is the defect");
// The live body already holds both dashes, inside the regex that strips them
// from the thumbnail headline; the added block must hold none.
const DASH = new RegExp("[" + String.fromCharCode(0x2013, 0x2014) + "]", "g");
eq(DASH.test(R.new), false, "the added block carries no em or en dash");
eq((after.match(DASH) || []).length, (before.match(DASH) || []).length, "and after.js holds no dash the live body did not");
eq(/\\u[0-9a-fA-F]{4}/.test(R.new), false, "the new text carries no escape for n8n to decode");

// ---- Behaviour ---------------------------------------------------------------------
const NOW = Date.UTC(2026, 9, 26, 6, 0, 0);
const FixedDate = Object.assign(function (...a) { return a.length ? new Date(...a) : new Date(NOW); }, { now: () => NOW });
const STEPS = ["Choose one recurring problem.", "Show the decision you made.", "Separate evidence from proposals.", "Prepare a shareable sample."];
const DISCLOSURE = "Presented with a synthetic voice and synthetic likeness of Terrance Veal, used with his consent.";
const fill = (code, opts = {}) => {
  const { show = "TQO", description = "Experience you cannot show is hard to use. This episode turns it into evidence." } = opts;
  const checklist = "checklist" in opts ? opts.checklist : STEPS;
  const nodes = {
    "Show Context: Script": { show, channel: show === "NCO" ? "NCO Forge" : "The Quiet Operator", tableId: "t", tableRef: "r" },
    "One Idea at a Time": { id: 49, fields: { "Asset Type": "Flagship" } },
    "Originality Scan": { recordId: 49, script: "The script.", title: "Your Experience Needs Evidence", description, broll: ["desk notebook", "window"], checklist }
  };
  const $ = (n) => { if (!(n in nodes)) throw new Error("no node " + n); return { first: () => ({ json: nodes[n] }) }; };
  return new Function("$", "Date", code)($, FixedDate)[0].json;
};
const fieldsOf = (o) => o.body.records[0].fields;

const a = fill(after), b = fill(before);
const BLOCK = "\n\nThe checklist from this episode:\n1. Choose one recurring problem.\n2. Show the decision you made.\n3. Separate evidence from proposals.\n4. Prepare a shareable sample.";
eq(fieldsOf(a).Description, fieldsOf(b).Description + BLOCK, "a TQO description gains the steps, numbered, after the writer's sentences");
eq(fieldsOf(a).Description.split("\n")[0], DISCLOSURE, "the disclosure is still the first line");
eq({ ...a, body: null }, { ...b, body: null }, "nothing outside the record changes");
for (const k of Object.keys(fieldsOf(b))) if (k !== "Description") eq(fieldsOf(a)[k], fieldsOf(b)[k], k + " is unchanged");
eq(Object.keys(fieldsOf(a)), Object.keys(fieldsOf(b)), "and no field is added");

eq(fieldsOf(fill(after, { description: fieldsOf(a).Description })).Description, fieldsOf(a).Description, "a second pass over its own output leaves one block, not two");
eq(fieldsOf(fill(after, { checklist: ["Only step."] })).Description, fieldsOf(b).Description + "\n\nThe checklist from this episode:\n1. Only step.", "a short list is written as it stands; the Script Gate, not this node, holds the count");
eq(fieldsOf(fill(after, { checklist: [" a ", "", "b"] })).Description, fieldsOf(b).Description + "\n\nThe checklist from this episode:\n1. a\n2. b", "steps are trimmed and empty ones dropped");
for (const [label, checklist] of [["no checklist", []], ["a missing checklist", undefined], ["text in place of a list", JSON.stringify(STEPS)], ["null", null]]) {
  eq(fieldsOf(fill(after, { checklist })).Description, fieldsOf(fill(before, { checklist })).Description, label + ": the description is what it was");
}
eq(fieldsOf(fill(after, { show: "NCO" })).Description, fieldsOf(fill(before, { show: "NCO" })).Description, "NCO: the description is what it was, because only the TQO writer is promised this");
eq(fieldsOf(fill(after, { description: "" })).Description, DISCLOSURE + BLOCK, "with no writer sentences, the steps follow the disclosure");

// Found by the verifier on 27f3d32: the first version cut an earlier block on
// every pass, so a description already carrying one lost it when no steps came
// with the pass, and NCO lost it too. A block is now replaced only when new
// steps are written; otherwise the description is what the live body makes.
const CARRIED = "Sentence one.\n\nThe checklist from this episode:\n1. Old step.\n2. Older step.";
for (const [label, opts] of [["TQO with no steps", { checklist: [] }], ["TQO with a null checklist", { checklist: null }], ["TQO with text in place of a list", { checklist: JSON.stringify(STEPS) }], ["NCO with steps", { show: "NCO" }], ["NCO with no steps", { show: "NCO", checklist: [] }]]) {
  eq(fieldsOf(fill(after, { ...opts, description: CARRIED })).Description, fieldsOf(fill(before, { ...opts, description: CARRIED })).Description, label + ": a block already in the description is left as the live body leaves it");
}
eq(fieldsOf(fill(after, { description: CARRIED })).Description, DISCLOSURE + "\n\nSentence one." + BLOCK, "TQO with new steps: the old block is replaced by the new one, once");
// Found by the verifier on 65556e6: replacing cut everything after the old
// heading, so a paragraph below the block was lost. The block alone is now
// replaced where it stands, up to the next blank line.
const TRAILED = CARRIED + "\n\nA paragraph someone added below the block.";
eq(fieldsOf(fill(after, { description: TRAILED })).Description, DISCLOSURE + "\n\nSentence one." + BLOCK + "\n\nA paragraph someone added below the block.", "a paragraph after the old block is kept, and the new block takes the old one's place");
eq(fieldsOf(fill(after, { description: TRAILED, checklist: [] })).Description, fieldsOf(fill(before, { description: TRAILED, checklist: [] })).Description, "with no steps, the same description is left as the live body leaves it");
// Pinned after the verifier on 766d867: with two old blocks, the first is the
// one replaced and the second is left as it stands.
const TWO = "S1.\n\nThe checklist from this episode:\n1. First old.\n\nMiddle.\n\nThe checklist from this episode:\n1. Second old.";
eq(fieldsOf(fill(after, { description: TWO })).Description, DISCLOSURE + "\n\nS1." + BLOCK + "\n\nMiddle.\n\nThe checklist from this episode:\n1. Second old.", "with two old blocks, the first is replaced and the second stays");

eq(M.rollbackAtPublish, "publish " + M.before.versionId, "at publish, rollback was the version before");
eq(!M.rollback.startsWith("publish ") && M.rollback.includes(M.before.versionId.slice(0, 8) + " on 2026-10-29 returned 404") && M.rollback.includes((M.node || M.before.node) + " in the live version"), true, "the before version is pruned, so rollback is an edit, not a publish");
console.log("description checklist: " + checks + " checks passed");
