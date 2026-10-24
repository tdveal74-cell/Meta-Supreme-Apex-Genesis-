/**
 * The score-only script doctor, ruled by Tee on 2026-10-24, "Score only, never
 * rewrite":
 *
 *   node n8n/tqo-v5/doctor-score-only/score_only.test.mjs
 *
 * Twenty Scripted rows were loaded by hand (TQO 49 to 60, NCO 30 to 37) and
 * none carries a doctor line, because the doctor in TQO FINAL V5 only runs for
 * rows at Idea. The QC Doctor Gate and Preflight therefore hold all twenty.
 * workflow.json is a separate workflow, started by hand only, that runs the
 * live doctor prompt in a score-only form and appends one doctor line to Score
 * History and one note to Last Feedback. It writes no other column.
 *
 * What this file proves, without touching n8n or the network:
 *   - live/ is the published doctor lane, pinned by live/manifest.json, and
 *     workflow.json is current with build.mjs;
 *   - the score-only prompt is the live prompt line for line except the output
 *     contract, for both shows;
 *   - the line it writes parses through the published QC Doctor Gate and
 *     Preflight patterns, and only PASS at 90 or above clears them;
 *   - every reply that is not PASS or NEEDS_REVISION with a score from 0 to 100
 *     writes nothing, REPAIRED included;
 *   - Save Score Line is the only write, to two columns, by row id.
 * What it cannot prove: that Cerebras answers, that the recall credential is
 * accepted, or how the data table node behaves. The first run, on one row, is
 * the proof of those. Rows here are synthetic.
 */

import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { buildWorkflow, LIVE_CONTRACT, SCORE_ONLY_CONTRACT, scoreOnlyPrompt } from "./build.mjs";

const read = (rel) => readFileSync(new URL(rel, import.meta.url), "utf8");
const sha = (s) => createHash("sha256").update(s, "utf8").digest("hex");
const MANIFEST = JSON.parse(read("./live/manifest.json"));
const DASHES = new RegExp("[" + String.fromCharCode(0x2013, 0x2014) + "]");
const WORKFLOW = JSON.parse(read("./workflow.json"));
const byName = Object.fromEntries(WORKFLOW.nodes.map((n) => [n.name, n]));
let checks = 0;
const ok = (cond, msg) => { assert.ok(cond, msg); checks++; };
const eq = (a, b, msg) => { assert.deepEqual(a, b, msg); checks++; };

// ---- live/ is the published doctor lane, byte for byte ----------------------
eq(MANIFEST.workflowId, "qEkGOUsNyVaRAmm6", "pinned from TQO FINAL V5");
eq(MANIFEST.versionId, "9f80c967-a649-488a-91ac-3f354178dfa8", "pinned at the version published 2026-10-24");
eq(MANIFEST.activeVersionId, MANIFEST.versionId, "read when nothing sat in draft");
for (const [name, entry] of Object.entries(MANIFEST.nodes)) {
  const body = read("./live/" + entry.file);
  if (entry.file.endsWith(".js")) {
    eq(sha(body), entry.sha256, name + ": the live copy matches the manifest");
    // Build Doctor Prompt is the one changed body; the prompt section proves the change.
    const want = name === "Build Doctor Prompt" ? scoreOnlyPrompt() : body;
    eq(byName[name].parameters.jsCode, want, name + ": the workflow carries the live body" + (name === "Build Doctor Prompt" ? " with its contract replaced" : " unchanged"));
  } else {
    const pinned = JSON.parse(body);
    const sorted = (v) => Array.isArray(v) ? v.map(sorted) : v && typeof v === "object" ? Object.fromEntries(Object.keys(v).sort().map((k) => [k, sorted(v[k])])) : v;
    eq(sha(JSON.stringify(sorted(pinned.parameters))), entry.sha256, name + ": the pinned parameters match the manifest");
    eq(byName[name].parameters, pinned.parameters, name + ": the workflow carries the live parameters unchanged");
    eq(byName[name].credentials, pinned.credentials, name + ": the workflow uses the live credential");
    eq(byName[name].type, pinned.type, name + ": same node type");
    eq(byName[name].typeVersion, pinned.typeVersion, name + ": same node version");
  }
}

// ---- workflow.json is current with build.mjs ---------------------------------
eq(JSON.stringify(buildWorkflow(), null, 1) + "\n", read("./workflow.json"), "workflow.json is what build.mjs builds");
execFileSync(process.execPath, [fileURLToPath(new URL("./build.mjs", import.meta.url)), "--check"], { stdio: "pipe" });
checks++;

// ---- the shape: started by hand, one write, two columns ----------------------
const triggers = WORKFLOW.nodes.filter((n) => /trigger|webhook/i.test(n.type));
eq(triggers.map((n) => n.type), ["n8n-nodes-base.manualTrigger"], "the only way in is a person starting it");
const tables = WORKFLOW.nodes.filter((n) => n.type === "n8n-nodes-base.dataTable");
eq(tables.filter((n) => n.parameters.operation !== "get").map((n) => n.name), ["Save Score Line"], "one data table write");
const save = byName["Save Score Line"].parameters;
eq(save.operation, "update", "it updates and never inserts");
eq(save.columns.mappingMode, "defineBelow", "no automatic mapping");
eq(Object.keys(save.columns.value).sort(), ["last_feedback", "score_history"], "it writes two columns and no other");
eq(save.filters.conditions.map((c) => [c.keyName, c.condition]), [["id", "eq"]], "by row id only");
eq(save.matchType, "allConditions", "all conditions");
const http = WORKFLOW.nodes.filter((n) => n.type === "n8n-nodes-base.httpRequest").map((n) => n.parameters.url).sort();
eq(http, ["https://api.cerebras.ai/v1/chat/completions", "https://devon-soul.vercel.app/api/v1/soul/recall"], "two calls out, both the live ones");
for (const n of tables.filter((x) => x.parameters.operation === "get" && /Scripted/.test(x.name))) {
  eq(n.parameters.filters.conditions, [{ keyName: "status", condition: "eq", keyValue: "Scripted" }], n.name + ": Scripted rows only");
}
eq(byName["Get TQO Scripted Rows"].parameters.dataTableId.value, "2GtmrFcTNqVMbddh", "tqo_content");
eq(byName["Get NCO Scripted Rows"].parameters.dataTableId.value, "DSH1tn4TZjzAEKxp", "nco_content");
eq(WORKFLOW.connections["One Idea at a Time"].main[0][0].node, "Run Report", "the loop's done output reports");
eq(WORKFLOW.connections["One Idea at a Time"].main[1][0].node, "DEVON Recall: Ask", "the loop's batch output scores");
eq(WORKFLOW.connections["Write It?"].main[0][0].node, "Save Score Line", "true writes");
eq(WORKFLOW.connections["Write It?"].main[1][0].node, "One Idea at a Time", "false writes nothing and moves on");
eq(WORKFLOW.settings.saveDataSuccessExecution, "all", "a clean run leaves an execution to read");
ok(!DASHES.test(read("./workflow.json")), "no em or en dash anywhere in the workflow");
for (const f of ["build.mjs", "nodes/run_config.js", "nodes/select_rows.js", "nodes/parse_score_only.js", "nodes/compose_write.js", "nodes/confirm_write.js", "nodes/run_report.js"]) {
  const body = read("./" + f);
  ok(!DASHES.test(body), f + ": no em or en dash");
  ok(!/\\u[0-9a-fA-F]{4}/.test(body), f + ": no \\u escape for n8n to decode on the way in");
}

// ---- running a node body ------------------------------------------------------
const dollar = (nodes) => (name) => {
  if (!(name in nodes)) throw new Error("node did not run: " + name);
  const items = nodes[name].map((json) => ({ json }));
  return { first: () => items[0], all: () => items };
};
const run = (name, nodes, inputItems) => {
  const items = inputItems.map((json) => ({ json }));
  const input = { first: () => items[0], all: () => items };
  return new Function("$", "$input", "$json", "require", byName[name].parameters.jsCode)(dollar(nodes), input, items[0] && items[0].json, () => { throw new Error("no require"); });
};

// ---- the prompt is the live prompt except its output contract ----------------
ok(scoreOnlyPrompt().includes(SCORE_ONLY_CONTRACT) && !scoreOnlyPrompt().includes(LIVE_CONTRACT), "the contract is replaced");
// What the contract must keep saying, whatever its wording becomes.
ok(SCORE_ONLY_CONTRACT.includes("never repairs it"), "the contract says the pass never repairs");
ok(SCORE_ONLY_CONTRACT.includes('"verdict":"PASS or NEEDS_REVISION"'), "the contract asks for PASS or NEEDS_REVISION");
ok(SCORE_ONLY_CONTRACT.includes("return NEEDS_REVISION"), "the contract maps a would-be repair to NEEDS_REVISION");
ok(/PASS only when the draft is already sound as written\. A high score never makes a broken draft PASS/.test(SCORE_ONLY_CONTRACT), "the contract ties PASS to a sound draft, not to the score");
const ROW = { id: 49, fields: { Show: "The Quiet Operator", Season: 1, Episode: 9, Idea: "the idea" }, sources: "" };
const D = { recordId: 49, title: "A title", description: "A description", broll: "desk, notebook", learningObjective: "You will learn one thing.", checklist: ["one", "two", "three"], script: "The script." };
const promptFor = (code, show) => {
  const ctx = show === "NCO" ? { show: "NCO", channel: "NCO Forge" } : { show: "TQO", channel: "The Quiet Operator" };
  const nodes = { "Show Context: Script": [ctx], "One Idea at a Time": [ROW], "DEVON Recall: Merge": [{ devonRecall: "- [tee, score 0.91] a record" }] };
  const items = [{ json: D }];
  return new Function("$", "$input", "$json", code)(dollar(nodes), { first: () => items[0], all: () => items }, D)[0].json;
};
const liveLines = (s) => s.split("\n");
const contractLines = (src) => src.split("\n").map((l) => l.trim().replace(/,$/, "")).map((l) => JSON.parse('"' + l.slice(1, -1).replace(/\\'/g, "'").replace(/"/g, '\\"') + '"'));
for (const show of ["TQO", "NCO"]) {
  const a = promptFor(read("./live/build_doctor_prompt.js"), show);
  const b = promptFor(byName["Build Doctor Prompt"].parameters.jsCode, show);
  const live = liveLines(a.claudeBody.system), mine = liveLines(b.claudeBody.system);
  const cut = live.indexOf("Return ONLY valid JSON, no fences:");
  ok(cut > 20, show + ": the live contract is found in the evaluated prompt");
  eq(mine.slice(0, cut), live.slice(0, cut), show + ": every line before the contract is the live line");
  eq(mine.slice(cut), contractLines(SCORE_ONLY_CONTRACT), show + ": after it, the score-only contract and nothing else");
  eq(b.claudeBody.messages, a.claudeBody.messages, show + ": the user message is the live one");
  eq(b.original, a.original, show + ": the draft handed on is the live one");
  ok(!/"script"|"title"|"description"|"broll"/.test(mine.slice(cut).join("\n")), show + ": the contract asks for no rewritten field");
}

// ---- the doctor line, read the way the published gates read it ----------------
const gateSource = read("../compliance/rebuild/draft/qc_doctor_gate.js");
const preflightSource = read("../compliance/rebuild/draft/preflight_can_this_clear.js");
const REGEX_LINE = "const doctorLines = [...history.matchAll(/\\|\\s*doctor\\s+(\\d+(?:\\.\\d+)?)\\/100\\s+([^|\\n]*?)\\s*(?=\\||\\n|$)/g)];";
ok(gateSource.includes(REGEX_LINE), "the QC Doctor Gate reads the doctor line with this pattern");
ok(preflightSource.includes(REGEX_LINE), "Preflight reads it with the same pattern");
for (const n of ["Select Rows", "Compose Write"]) {
  ok(byName[n].parameters.jsCode.includes("const DOCTOR = /\\|\\s*doctor\\s+(\\d+(?:\\.\\d+)?)\\/100\\s+([^|\\n]*?)\\s*(?=\\||\\n|$)/;"), n + ": the same pattern, so a scored row is never scored again");
}
const gateClears = (history) => {
  const lines = [...history.matchAll(/\|\s*doctor\s+(\d+(?:\.\d+)?)\/100\s+([^|\n]*?)\s*(?=\||\n|$)/g)];
  const last = lines.length ? lines[lines.length - 1] : null;
  const score = last ? Number(last[1]) : NaN;
  const verdict = last ? last[2].trim().toUpperCase() : "UNCHECKED";
  return { verdict, score, clear: ["PASS", "REPAIRED"].includes(verdict) && score >= 90 };
};

// ---- Parse Score Only ----------------------------------------------------------
const PARSE_NODES = { "One Idea at a Time": [{ id: 49, video_title: "Row 49 title" }], "Show Context: Script": [{ show: "TQO", tableRef: "2GtmrFcTNqVMbddh" }] };
const reply = (content, extra = {}) => ({ model: "gpt-oss-120b", choices: [{ finish_reason: "stop", message: { content: typeof content === "string" ? content : JSON.stringify(content) } }], ...extra });
const parse = (out) => run("Parse Score Only", PARSE_NODES, [out])[0].json;
const good = parse(reply({ score: 92, verdict: "PASS", preserved: ["the cold open"], diagnosis: "none broken", notes: ["tighten line 4"] }));
ok(good.ok && good.verdict === "PASS" && good.score === 92, "PASS 92 is a result");
ok(/^\d{4}-\d\d-\d\dT[\d:.]+Z \| doctor 92\/100 PASS \| score only, no rewrite, gpt-oss-120b$/.test(good.line), "the line: " + good.line);
eq(gateClears(good.line), { verdict: "PASS", score: 92, clear: true }, "the gates read PASS 92 and clear it");
ok(good.feedback.startsWith("SCRIPT DOCTOR, SCORE ONLY: PASS at 92/100") && good.feedback.includes("The script was not changed."), "the note says nothing was changed");
ok(good.feedback.includes("NOTES:\n  - tighten line 4") && good.feedback.includes("PRESERVED:\n  - the cold open"), "the notes and the preserved list are kept");
eq(Object.keys(good).sort(), ["feedback", "line", "model", "ok", "reason", "rowId", "score", "show", "stamp", "tableRef", "title", "verdict", "written"], "nothing from the reply but the score, the verdict and the note travels on");
const held = (content) => { const r = parse(reply(content)); ok(r.ok, JSON.stringify(content) + " is a result"); return gateClears(r.line); };
eq(held({ score: 96, verdict: "NEEDS_REVISION" }).clear, false, "NEEDS_REVISION holds at any score");
eq(held({ score: 85, verdict: "PASS" }).clear, false, "PASS under 90 holds");
eq(held({ score: 90, verdict: "PASS" }).clear, true, "PASS at exactly 90 clears");
eq(held({ score: "92", verdict: "pass" }), { verdict: "PASS", score: 92, clear: true }, "a numeric string and a lowercase verdict are read");
eq(parse(reply({ score: 92.46, verdict: "PASS" })).score, 92.4, "one decimal, rounded down");
// Found by the verifier on 805060d: rounding to nearest wrote 89.95 as 90 and cleared the gate.
for (const s of [89.95, 89.99, "89.95"]) {
  const r = parse(reply({ score: s, verdict: "PASS" }));
  eq([r.score, gateClears(r.line).clear], [89.9, false], JSON.stringify(s) + " is written as 89.9 and held, never 90");
}
eq(parse(reply("```json\n" + JSON.stringify({ score: 91, verdict: "PASS" }) + "\n```")).verdict, "PASS", "a fenced reply is read");
eq(parse(reply("Here it is: " + JSON.stringify({ score: 91, verdict: "PASS" }) + " done")).verdict, "PASS", "a reply wrapped in prose is read");
const refused = [
  [reply({ score: 95, verdict: "REPAIRED", script: "rewritten" }), "REPAIRED, which no score-only pass can give"],
  [reply({ score: 95, verdict: "PASS WITH NOTES" }), "PASS WITH NOTES"],
  [reply({ score: 95 }), "no verdict, which the live parser would call PASS"],
  [reply({ score: 95, verdict: "" }), "an empty verdict"],
  [reply({ score: 95, verdict: ["PASS"] }), "a verdict that is not a string"],
  [reply({ score: 95, verdict: "pa\u00df" }), "a verdict whose letters only upper-case into PASS"],
  [reply({ score: 95, verdict: "PAS\u017f" }), "a long s that upper-cases into PASS"],
  [reply({ score: 92, verdict: "PASS" }, { choices: [{ message: { content: '{"score":92,"verdict":"PASS"}' } }] }), "a completion with no finish_reason"],
  [reply({ score: 92, verdict: "PASS" }, { choices: [{ finish_reason: "content_filter", message: { content: '{"score":92,"verdict":"PASS"}' } }] }), "a completion stopped by a content filter"],
  [reply({ verdict: "PASS" }), "no score"],
  [reply({ score: "92%", verdict: "PASS" }), "a score with a unit"],
  [reply({ score: 101, verdict: "PASS" }), "a score above 100"],
  [reply({ score: -1, verdict: "PASS" }), "a score below 0"],
  [reply({ score: null, verdict: "PASS" }), "a null score"],
  [reply({ score: true, verdict: "PASS" }), "a boolean score"],
  [reply("[]"), "an array"],
  [reply("not json at all"), "prose"],
  [reply("{ broken"), "broken JSON"],
  [reply(""), "an empty completion"],
  [reply({ score: 92, verdict: "PASS" }, { choices: [{ finish_reason: "length", message: { content: '{"score":92,"verdict":"PASS"}' } }] }), "a truncated completion"],
  [{ error: { message: "402 - Payment Required" } }, "a refused call"],
  [{}, "an empty response"],
  [{ choices: [] }, "no choices"]
];
for (const [out, why] of refused) {
  const r = parse(out);
  ok(r.ok === false && r.verdict === "UNCHECKED" && r.written === false && !("line" in r), why + " writes nothing: " + r.reason);
}

// ---- Compose Write -------------------------------------------------------------
const compose = (p, fresh) => run("Compose Write", { "Parse Score Only": [p] }, fresh)[0].json;
const ROW49 = { id: 49, status: "Scripted", score_history: "", last_feedback: "" };
const c1 = compose(good, [ROW49]);
ok(c1.write === true && c1.scoreHistory === good.line && c1.lastFeedback === good.feedback, "an empty row takes the line and the note");
const c2 = compose(good, [{ ...ROW49, score_history: "2026-10-01T00:00:00Z | 88/100 CONDITIONAL", last_feedback: "older note" }]);
eq(c2.scoreHistory, "2026-10-01T00:00:00Z | 88/100 CONDITIONAL\n" + good.line, "Score History is appended to, never replaced");
eq(c2.lastFeedback, "older note\n\n" + good.feedback, "Last Feedback is appended to, never replaced");
eq(gateClears(c2.scoreHistory).clear, true, "the appended line is the newest doctor line");
const skips = [
  [compose(parse({}), [ROW49]), "a failed parse"],
  [compose(good, [{}]), "a row that does not read back"],
  [compose(good, []), "no row at all"],
  [compose(good, [ROW49, ROW49]), "two rows under one id"],
  [compose(good, [{ ...ROW49, status: "Ready" }]), "a row that left Scripted"],
  [compose(good, [{ ...ROW49, score_history: "x | doctor 70/100 REPAIRED | y" }]), "a doctor line that landed during the run"]
];
for (const [r, why] of skips) ok(r.write === false && r.written === false && r.ok === false && !("scoreHistory" in r), why + " writes nothing: " + r.reason);

// ---- Confirm Write -------------------------------------------------------------
const confirm = (back) => run("Confirm Write", { "Compose Write": [c1] }, back)[0].json;
eq(confirm([{ id: 49, score_history: c1.scoreHistory, last_feedback: c1.lastFeedback }]).written, true, "written only when both columns read back as sent");
eq(confirm([{ id: 49, score_history: c1.scoreHistory, last_feedback: "" }]).written, false, "a column that did not land is not written");
eq(confirm([{}]).written, false, "nothing read back is not written");

// ---- the shipped Run Config -------------------------------------------------------
// Found by the verifier on 805060d: the tests used their own config and never read
// the shipped one, so FIRST_RUN_LIMIT could be raised without a failure.
eq(run("Run Config", {}, [{}]).map((i) => i.json), [{ FIRST_RUN_LIMIT: 1, ROW_LIMIT: 20, ONLY_ROWS: [] }], "the first run scores one row, later runs up to 20, no row named");

// ---- Select Rows ---------------------------------------------------------------
const CONFIG = { FIRST_RUN_LIMIT: 1, ROW_LIMIT: 20, ONLY_ROWS: [] };
const tqoRow = (id, extra = {}) => ({ id, status: "Scripted", script: "A script.", score_history: "", ...extra });
const select = (tqo, nco, cfg = CONFIG) => run("Select Rows", { "Run Config": [cfg], "Get TQO Scripted Rows": tqo, "Get NCO Scripted Rows": nco }, [{}]).map((i) => i.json.__key);
const TQO = [tqoRow(51), tqoRow(49), tqoRow(50, { script: " " }), tqoRow(48, { score_history: "t | doctor 93/100 PASS | x" }), tqoRow(47, { status: "Idea" })];
const NCO = [tqoRow(31), tqoRow(30)];
eq(select(TQO, NCO), ["TQO:49"], "the first run takes one row, TQO first, lowest id, never one already scored");
const PROOF = tqoRow(52, { score_history: "2026-10-24T09:00:00.000Z | doctor 92/100 PASS | score only, no rewrite, gpt-oss-120b" });
eq(select([...TQO, PROOF], NCO), ["TQO:49", "TQO:51", "NCO:30", "NCO:31"], "once a score-only line exists, the rest in order");
eq(select([...TQO, tqoRow(52, { score_history: "t | doctor 92/100 PASS | from the live doctor" })], NCO), ["TQO:49"], "a live doctor line is not the proof");
eq(select(TQO, NCO, { ...CONFIG, ONLY_ROWS: ["NCO:31"] }), ["NCO:31"], "ONLY_ROWS picks the named row");
eq(select([{}], NCO), ["NCO:30"], "an empty table's placeholder item is ignored");
const throws = (fn, re, why) => { assert.throws(fn, re, why); checks++; };
throws(() => select(TQO, NCO, { ...CONFIG, ONLY_ROWS: ["TQO:48"] }), /ONLY_ROWS names TQO:48/, "a scored row cannot be named");
throws(() => select([tqoRow(48, { score_history: "t | doctor 93/100 PASS | x" })], [{}]), /No row to score/, "nothing to score stops the run");
throws(() => select(TQO, NCO, { ...CONFIG, FIRST_RUN_LIMIT: 0 }), /whole numbers above 0/, "a zero limit stops the run");
throws(() => select(TQO, NCO, { ...CONFIG, ROW_LIMIT: "20" }), /whole numbers above 0/, "a limit that is not a number stops the run");
const picked = run("Select Rows", { "Run Config": [CONFIG], "Get TQO Scripted Rows": TQO, "Get NCO Scripted Rows": NCO }, [{}])[0].json;
eq([picked.nco, picked.__tableRef, picked.__show], [false, "2GtmrFcTNqVMbddh", "TQO"], "the row carries its show for Show Context: Script");

// ---- Run Report ----------------------------------------------------------------
const report = (results) => run("Run Report", { "Select Rows": [{ __selectNote: "select: test" }] }, results);
const r1 = report([{ show: "TQO", rowId: 49, title: "T", written: true, verdict: "PASS", score: 92 }, { show: "NCO", rowId: 30, title: "N", written: true, verdict: "NEEDS_REVISION", score: 74 }])[0].json;
ok(r1.summary.startsWith("Score-only doctor run: 2 row(s), 2 written, 1 clear the doctor check at 90, 0 not written."), r1.summary);
ok(r1.summary.includes('NCO row 30 "N": NEEDS_REVISION 74/100, the doctor line holds the row'), "a held row says so");
throws(() => report([{ show: "TQO", rowId: 49, title: "T", written: false, verdict: "UNCHECKED", score: null, reason: "the Cerebras call failed: 402" }]), /1 not written[\s\S]*NOT WRITTEN, the Cerebras call failed: 402/, "a row not written ends the run in error");
throws(() => report([{ id: 49, status: "Scripted" }]), /could not read the loop results/, "rows instead of results end the run in error");

console.log("score-only doctor: " + checks + " checks passed");
