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
 *   - Save Score Line is the only write, to two columns, by row id;
 *   - Score Only: Final Word tells the doctor where the learning objective is
 *     spoken, by the Script Gate's own rule, and which lines are the brief;
 *   - workflow.measure.json differs from workflow.json in Run Config alone,
 *     and a run built from it writes nothing;
 *   - each row is read READS times and only the strictest read is written, and
 *     the doctor is told first person that only addresses the viewer stands.
 * What it cannot prove: that Cerebras answers, that the recall credential is
 * accepted, or how the data table node behaves. The first run, on one row, is
 * the proof of those. Rows here are synthetic.
 */

import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { buildWorkflow, LIVE_CHECKLIST_EMPTY, LIVE_CONTRACT, LIVE_HYDRATE_FIELDS, NCO_CLOSE, RUN_CONFIG_MEASURE, RUN_CONFIG_REAL, runConfig, SCORE_ONLY_CHECKLIST_EMPTY, SCORE_ONLY_CONTRACT, SCORE_ONLY_HYDRATE_FIELDS, scoreOnlyHydrate, scoreOnlyPrompt } from "./build.mjs";

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
    // Two bodies are changed, each by one replacement; their own sections prove the change.
    const CHANGED = { "Build Doctor Prompt": scoreOnlyPrompt, "Script: Hydrate from Row": scoreOnlyHydrate };
    const want = CHANGED[name] ? CHANGED[name]() : body;
    eq(byName[name].parameters.jsCode, want, name + ": the workflow carries the live body" + (CHANGED[name] ? " with its one replacement" : " unchanged"));
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
eq(JSON.stringify(buildWorkflow({ measure: true }), null, 1) + "\n", read("./workflow.measure.json"), "workflow.measure.json is what build.mjs builds");
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
eq(WORKFLOW.settings.availableInMCP, true, "a session can start it through the n8n tools, as it can TQO FINAL V5");
ok(!DASHES.test(read("./workflow.json")), "no em or en dash anywhere in the workflow");
ok(!DASHES.test(read("./workflow.measure.json")), "nor in the measurement body");
for (const f of ["build.mjs", "README.md", "nodes/run_config.js", "nodes/select_rows.js", "nodes/recall_required.js", "nodes/final_word.js", "nodes/reads.js", "nodes/parse_score_only.js", "nodes/compose_write.js", "nodes/confirm_write.js", "nodes/run_report.js"]) {
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
// Ruled by Tee 2026-10-25, "Allow a comments question": the NCO branch of the
// preservation rules carries the sentence in NCO_CLOSE, the same replacement the
// live doctor gets, so the live line it is compared with is the pinned one with
// that replacement made.
eq(read("./live/build_doctor_prompt.js").split(NCO_CLOSE.old).length, 2, "the NCO branch the replacement fills occurs once in the pinned live body");
for (const show of ["TQO", "NCO"]) {
  const a = promptFor(read("./live/build_doctor_prompt.js").replace(NCO_CLOSE.old, () => NCO_CLOSE.new), show);
  const b = promptFor(byName["Build Doctor Prompt"].parameters.jsCode, show);
  const live = liveLines(a.claudeBody.system), mine = liveLines(b.claudeBody.system);
  const cut = live.indexOf("Return ONLY valid JSON, no fences:");
  ok(cut > 20, show + ": the live contract is found in the evaluated prompt");
  eq(mine.slice(0, cut), live.slice(0, cut), show + ": every line before the contract is the live line");
  eq(mine.slice(cut), contractLines(SCORE_ONLY_CONTRACT), show + ": after it, the score-only contract and nothing else");
  // D carries a checklist, so the empty checklist text is not in play here.
  eq(b.claudeBody.messages, a.claudeBody.messages, show + ": the user message is the live one");
  eq(b.original, a.original, show + ": the draft handed on is the live one");
  ok(!/"script"|"title"|"description"|"broll"/.test(mine.slice(cut).join("\n")), show + ": the contract asks for no rewritten field");
  const said = mine.filter((l) => l === NCO_CLOSE.sentence).length;
  eq(said, show === "NCO" ? 1 : 0, show + (show === "NCO" ? ": the NCO close sentence is said once" : ": TQO is not given the NCO close sentence"));
  ok(mine.some((l) => l.includes("a specific question for the comments is not a solicitation or engagement bait")) === (show === "TQO"), show + ": the TQO sentence stays TQO's own");
}
ok(NCO_CLOSE.sentence.includes("an NCO episode may end on one or on a quiet action") && NCO_CLOSE.new.includes(NCO_CLOSE.sentence) && !NCO_CLOSE.old.includes(NCO_CLOSE.sentence), "the NCO sentence allows a comments question and does not require one");
ok(NCO_CLOSE.sentence.includes("asking the viewer to subscribe is the NCO call to action, and it stands. It is not a solicitation under the close score.") && !/remove it|cut it/.test(NCO_CLOSE.sentence), "and leaves the NCO writer's subscribe line alone, as Tee ruled");
eq(new RegExp("[" + String.fromCharCode(0x2013, 0x2014) + "]").test(NCO_CLOSE.new), false, "and carries no em or en dash");

// ---- Hydrate shows the doctor what the row holds -------------------------------
// Found by the review on 805060d: the live Hydrate reads the shim's fields, which
// carry no learning_objective and spell the b-roll Broll Keywords, so the doctor
// was told the learning objective was none returned for every TQO row.
eq(scoreOnlyHydrate().split(SCORE_ONLY_HYDRATE_FIELDS).length, 2, "the fields line is replaced once");
eq(read("./live/script_hydrate_from_row.js").replace(LIVE_HYDRATE_FIELDS, () => SCORE_ONLY_HYDRATE_FIELDS), byName["Script: Hydrate from Row"].parameters.jsCode, "and nothing else in Hydrate changes");
const RAW = { id: 49, status: "Scripted", show: "TQO", season: 1, episode: 9, topic: "Topic 49", idea: "Idea 49", video_title: "Title 49", description: "Description 49", tags: "a, b", broll_keywords: "desk, notebook", learning_objective: "By the end, you will have one thing.", checklist: null, script: "  The script.  ", score_history: null, sources: null };
const shimmed = run("DT Shim: Idea Rows", {}, [RAW])[0].json;
const hydrateWith = (code) => new Function("$", "$input", "$json", code)(dollar({ "One Idea at a Time": [shimmed] }), { first: () => ({ json: shimmed }), all: () => [{ json: shimmed }] }, shimmed)[0].json;
const fixed = hydrateWith(byName["Script: Hydrate from Row"].parameters.jsCode);
eq([fixed.learningObjective, fixed.broll, fixed.title, fixed.description, fixed.script, fixed.tags, fixed.checklist, fixed.recordId],
  ["By the end, you will have one thing.", "desk, notebook", "Title 49", "Description 49", "The script.", "a, b", [], 49], "the doctor is shown the row's objective, b-roll, title, description and script");
const liveHydrated = hydrateWith(read("./live/script_hydrate_from_row.js"));
eq([liveHydrated.learningObjective, liveHydrated.broll], ["", ""], "the live copy drops both, which is the defect the replacement fixes");
const noTitle = run("DT Shim: Idea Rows", {}, [{ ...RAW, video_title: null }])[0].json;
eq(new Function("$", "$input", "$json", byName["Script: Hydrate from Row"].parameters.jsCode)(dollar({ "One Idea at a Time": [noTitle] }), null, noTitle)[0].json.title, "Topic 49", "with no title the topic stands in, as live");

// ---- the request the provider receives ---------------------------------------------
// Found by the review on 805060d: Token Budget: Doctor ends the live system message
// with "write the full length the brief asks for, never shorter", which says it
// overrides anything above. Score Only: Final Word comes after it.
eq(WORKFLOW.connections["Token Budget: Doctor"].main[0][0].node, "Score Only: Final Word", "the final word runs after the budget");
eq(WORKFLOW.connections["Score Only: Final Word"].main[0][0].node, "Score Only: Reads", "then the reads");
eq(WORKFLOW.connections["Score Only: Reads"].main[0][0].node, "Run Script Doctor (Cerebras)", "and right before the call");
eq(WORKFLOW.connections["Run Script Doctor (Cerebras)"].main[0][0].node, "Parse Score Only", "every reply goes to the parse");
const prompted = run("Build Doctor Prompt", { "Show Context: Script": [{ show: "TQO", channel: "The Quiet Operator" }], "One Idea at a Time": [shimmed], "DEVON Recall: Merge": [{ devonRecall: "" }] }, [fixed])[0].json;
const sourced = run("Doctor Sources", { "One Idea at a Time": [shimmed] }, [prompted])[0].json;
const budgeted = run("Token Budget: Doctor", {}, [sourced])[0].json;
const FW_NODES = (show, prompt) => ({ "Build Doctor Prompt": [prompt], "Show Context: Script": [{ show, channel: show === "NCO" ? "NCO Forge" : "The Quiet Operator" }] });
const finalReq = run("Score Only: Final Word", FW_NODES("TQO", prompted), [budgeted])[0].json.claudeBody;
eq(Object.keys(finalReq).sort(), ["max_completion_tokens", "messages", "model", "reasoning_effort", "response_format"], "the request carries the live Cerebras fields and no others");
eq([finalReq.model, finalReq.max_completion_tokens, finalReq.response_format], ["gpt-oss-120b", 12000, { type: "json_object" }], "the live model, ceiling and JSON mode");
eq(finalReq.messages.map((m) => m.role), ["system", "user"], "one system message and one user message");
const sysText = finalReq.messages[0].content;
ok(sysText.indexOf("write the full length the brief asks for") < sysText.indexOf("Score only, and this overrides the full-length rule above"), "the final word comes after the full-length rule");
ok(sysText.trimEnd().endsWith("The rule against em and en dashes still stands."), "and it is the last thing the model reads");
ok(finalReq.messages[1].content.includes("LEARNING OBJECTIVE (keep word for word, inside the first 30 seconds): By the end, you will have one thing."), "the user message carries the row's learning objective");
ok(finalReq.messages[1].content.includes("BROLL: desk, notebook"), "and its b-roll");
ok(finalReq.messages[1].content.includes("APPROVED SOURCES: none."), "and the sources block the live doctor sees");
assert.throws(() => run("Score Only: Final Word", {}, [{ claudeBody: { messages: [{ role: "user", content: "x" }] } }]), /expected the request to open with a system message/); checks++;

// ---- the measured facts ------------------------------------------------------------
// Found by execution 4300: the doctor guessed the learning objective's position
// ("Probably not before 30 seconds") when it starts at word 31, and took the
// LEARNING OBJECTIVE field line for a second copy of it. Ruled by Tee 2026-10-24:
// measure it the Script Gate's way and give the doctor the fact.
const EXPORT = JSON.parse(read("../exports/qEkGOUsNyVaRAmm6_active.json"));
const gateCode = (EXPORT.nodes || EXPORT.activeVersion.nodes).find((n) => n.name === "Script Gate: Quality").parameters.jsCode;
const fwCode = byName["Score Only: Final Word"].parameters.jsCode;
const NORM_LINE = "const norm = (s) => String(s || '').toLowerCase().replace(/[^a-z0-9\\s]/g, ' ').split(/\\s+/).filter(Boolean).join(' ');";
ok(gateCode.includes("const LO_WINDOW = 70;") && fwCode.includes("const LO_WINDOW = 70;"), "the same 70 word window as the Script Gate");
ok(gateCode.includes(NORM_LINE) && fwCode.includes(NORM_LINE), "and the same normaliser, character for character");
ok(gateCode.includes("const loOk = !!lo && (' ' + norm(opening) + ' ').includes(' ' + lo + ' ');") && fwCode.includes("(' ' + norm(tokens.slice(0, LO_WINDOW).join(' ')) + ' ').includes(' ' + lo + ' ')"), "and the same test for inside the window");
const LO49 = "By the end, you will have a one-page work sample that shows your judgment and separates measured results from proposed improvements.";
const words = (n, w = "word") => Array.from({ length: n }, (_, i) => w + i).join(" ");
const measureFor = (script, lo, show = "TQO") => {
  const raw = { ...RAW, script, learning_objective: lo };
  const sh = run("DT Shim: Idea Rows", {}, [raw])[0].json;
  const hy = new Function("$", "$input", "$json", byName["Script: Hydrate from Row"].parameters.jsCode)(dollar({ "One Idea at a Time": [sh] }), { first: () => ({ json: sh }), all: () => [{ json: sh }] }, sh)[0].json;
  const ctx = [{ show, channel: show === "NCO" ? "NCO Forge" : "The Quiet Operator" }];
  const pr = run("Build Doctor Prompt", { "Show Context: Script": ctx, "One Idea at a Time": [sh], "DEVON Recall: Merge": [{ devonRecall: "" }] }, [hy])[0].json;
  const so = run("Doctor Sources", { "One Idea at a Time": [sh] }, [pr])[0].json;
  const bu = run("Token Budget: Doctor", {}, [so])[0].json;
  const out = run("Score Only: Final Word", FW_NODES(show, pr), [bu])[0].json.claudeBody;
  return { before: bu.claudeBody, after: out, user: out.messages[1].content, script: hy.script };
};
{
  // Row 49's shape: three sentences, 30 words, then the objective.
  const s49 = "Years of experience can be hard to inspect when somebody sees only a job title. Show the decisions that made the work dependable. That gives them evidence they can question. " + LO49 + " " + words(100);
  const m = measureFor(s49, LO49);
  ok(m.user.includes("the learning objective is spoken word for word from word 31 to word 51 of 151, inside the first 70 words. Its position meets the brief; do not mark it down for where it sits. The script speaks it once."), "row 49's shape is measured at word 31, inside, once");
  ok(m.user.endsWith("\n\nSCRIPT:\n" + m.script) && m.user.indexOf("MEASURED BEFORE THIS PASS") < m.user.indexOf("\n\nSCRIPT:\n"), "the facts sit just above SCRIPT: and the script after it is untouched");
  ok(m.user.includes("Every line above SCRIPT: is the brief") && m.user.includes("the LEARNING OBJECTIVE and CHECKLIST lines") && m.user.includes("none is a second copy of a script sentence"), "the brief's lines are named as not script");
  // Found by the verifier on 7d57ca6: the first version of this check compared the
  // message with itself. The final word is read out of the node's own code.
  const constant = (name) => new Function("return " + fwCode.match(new RegExp("^const " + name + " = ('[^\\n]*');$", "m"))[1])();
  const FINAL_TEXT = constant("FINAL"), VOICE_TEXT = constant("VOICE");
  ok(FINAL_TEXT.startsWith("\n\nScore only, and this overrides the full-length rule above") && FINAL_TEXT.endsWith("The rule against em and en dashes still stands."), "the final word is read from the node");
  ok(VOICE_TEXT.includes('"I am talking to the person who has spent years handling problems other people never even saw."') && VOICE_TEXT.includes("never marked down") && VOICE_TEXT.includes("The rule against invented experience still applies"), "the voice ruling names its example and keeps the invented experience rule");
  // Sharpened by Tee 2026-10-25 after execution 4364, where one read took that person for Terrance.
  ok(VOICE_TEXT.includes("In that line, the person who has spent years handling problems other people never even saw is the viewer being addressed, not Terrance, so the line says nothing about what he has done."), "and says the person in that line is the viewer");
  eq(m.after.messages[0].content, m.before.messages[0].content + VOICE_TEXT + FINAL_TEXT, "the system message only gains the voice ruling and the final word at its end");
  eq(m.user.replace(/\n\nMEASURED BEFORE THIS PASS[^\n]*\nEvery line above SCRIPT:[^\n]*(?=\n\nSCRIPT:\n)/, ""), m.before.messages[1].content, "and the user message gains the two lines and nothing else");
  const late = measureFor(words(80) + " " + LO49 + " " + words(10, "tail"), LO49);
  ok(late.user.includes("from word 81 to word 101 of 111, which is past the first 70 words, so its position does not meet the brief. The script speaks it once."), "an objective past 70 words is measured as outside");
  const edge = measureFor(words(49) + " " + LO49 + " " + words(10, "tail"), LO49);
  ok(edge.user.includes("from word 50 to word 70 of 80, inside the first 70 words"), "ending on word 70 is inside, as the gate counts it");
  const over = measureFor(words(50) + " " + LO49 + " " + words(10, "tail"), LO49);
  ok(over.user.includes("from word 51 to word 71 of 81, which is past the first 70 words"), "ending on word 71 is outside");
  const twice = measureFor("Open here. " + LO49 + " " + words(20) + " " + LO49.toUpperCase().replace(/,/g, ""), LO49);
  ok(twice.user.includes("The script speaks it 2 times."), "case and punctuation do not hide a second copy");
  const absent = measureFor(words(40), LO49);
  ok(absent.user.includes("the learning objective is not spoken word for word anywhere in the script."), "an objective the script never speaks is measured as missing");
  // Found by the verifier on 7d57ca6: no fixture had a digit or a hyphen spelled
  // differently in the script, so only the text check guarded the normaliser.
  const digits = measureFor("Start. In 3 steps, the one page plan for Q4 2026 is ready. " + words(10), "In 3 steps the one-page plan for Q4 2026 is ready");
  ok(digits.user.includes("from word 2 to word 13 of 23, inside the first 70 words"), "digits count and a hyphen matches a space, as the gate reads them");
  const otherDigit = measureFor("Start. Step 4 comes first here. " + words(10), "Step 3 comes first here");
  ok(otherDigit.user.includes("is not spoken word for word anywhere in the script."), "a different digit is a different objective");
  const glued = measureFor("Start. The onepage plan is ready. " + words(10), "The one-page plan is ready");
  ok(glued.user.includes("is not spoken word for word anywhere in the script."), "but a hyphen never matches a word run together, as the gate reads it");
  const none = measureFor(words(40), "");
  ok(none.user.includes("MEASURED BEFORE THIS PASS: no learning objective is stored for this row."), "no stored objective is said so");
  const nco = measureFor(s49, LO49, "NCO");
  ok(!nco.user.includes("MEASURED BEFORE THIS PASS") && nco.user.includes("Every line above SCRIPT: is the brief") && !nco.user.includes("LEARNING OBJECTIVE and CHECKLIST"), "NCO gets the brief line and no objective measure");
  eq(nco.after.messages[0].content, nco.before.messages[0].content + VOICE_TEXT + FINAL_TEXT, "and the same voice ruling, which is Tee's for both shows");
  const bad = { claudeBody: { ...m.before, messages: [m.before.messages[0], { role: "user", content: m.before.messages[1].content + " extra" }] } };
  assert.throws(() => run("Score Only: Final Word", FW_NODES("TQO", { original: { script: m.script, learningObjective: LO49 } }), [bad]), /could not find the script after SCRIPT:/, "a message whose script is not the row's stops before the call"); checks++;
  assert.throws(() => run("Score Only: Final Word", FW_NODES("TQO", { original: { script: m.script } }), [{ claudeBody: { ...m.before, messages: [...m.before.messages, { role: "assistant", content: "x" }] } }]), /one system message and one user message/, "a third message stops before the call"); checks++;
}

// ---- Score Only: Reads ---------------------------------------------------------------
// Ruled by Tee 2026-10-24 after executions 4354 to 4356 scored one request 85, 100 and 90.
const readsOut = run("Score Only: Reads", { "Run Config": [{ READS: 3 }] }, [{ claudeBody: { x: 1 } }]).map((i) => i.json);
eq(readsOut, [1, 2, 3].map((read) => ({ claudeBody: { x: 1 }, read })), "three reads of the same request");
assert.throws(() => run("Score Only: Reads", { "Run Config": [{ READS: 3 }] }, [{}, {}]), /expected one request and received 2/, "two requests in is refused"); checks++;

// ---- Recall Required ---------------------------------------------------------------
// Found by the review on 805060d: a failed recall left TEE'S RECORD empty, the doctor
// then treats first person material as invented, and nothing reported it.
const recallNodes = (ask) => ({ "DEVON Recall: Ask": [ask], "One Idea at a Time": [{ id: 49, __key: "TQO:49" }] });
const merged = { id: 49, devonRecall: "- [tee] x", devonRecallNote: "DEVON recall: 1 record(s), 1 from Tee and 0 from DEVON" };
eq(run("Recall Required", recallNodes({ statusCode: 200, body: { records: [{ text: "x" }] } }), [merged]).map((i) => i.json), [merged], "a recall that answered passes the row on unchanged");
eq(run("Recall Required", recallNodes({ statusCode: 200, body: JSON.stringify({ records: [] }) }), [merged]).length, 1, "an answer with no records is still an answer");
for (const [ask, why] of [[{ statusCode: 401, body: { detail: "Invalid token" } }, "a 401"], [{ error: { message: "timeout of 15000ms exceeded" } }, "a timeout"], [{ statusCode: 200, body: "not json" }, "an unreadable 200"], [{ statusCode: 503, body: {} }, "a 503"]]) {
  assert.throws(() => run("Recall Required", recallNodes(ask), [{ ...merged, devonRecallNote: "DEVON recall unavailable (HTTP 401, Invalid token); the script was written without it" }]),
    /DEVON recall did not answer for TQO:49, so it was not scored and the run stopped before calling the provider\. DEVON recall unavailable/, why + " stops the run before the provider is paid");
  checks++;
}
// Found by the fix verifier on 8f311fb: the soul service answers 200 with an errors
// entry when Tee's own index is down, which is a recall without Tee's record.
ok(read("../../../deploy/soul/services/intelligence/soul.py").includes('errors.append(f"tee-soul-layer unavailable: {exc}")'), "the soul service still names Tee's index this way");
assert.throws(() => run("Recall Required", recallNodes({ statusCode: 200, body: { records: [], errors: ["tee-soul-layer unavailable: 503"] } }), [merged]), /did not answer for TQO:49/, "a 200 without Tee's index stops the run"); checks++;
eq(run("Recall Required", recallNodes({ statusCode: 200, body: { records: [{ text: "x" }], errors: ["devon-soul was not searched: no host is configured"] } }), [merged]).length, 1, "a recall missing only DEVON's index goes on");
eq(WORKFLOW.connections["DEVON Recall: Merge"].main[0][0].node, "Recall Required", "the recall is checked right after it is merged");
eq(WORKFLOW.connections["Recall Required"].main[0][0].node, "Show Context: Script", "and before anything else runs");

// ---- a row that stores no checklist --------------------------------------------
// Found by the first run (execution 4292): row 49 stores no checklist, the live line
// said "(none returned)", and the doctor held the row on a checklist its script
// speaks. Ruled by Tee 2026-10-24: tell the doctor to judge the spoken steps.
eq(scoreOnlyPrompt().split(SCORE_ONLY_CHECKLIST_EMPTY).length, 2, "the empty checklist text is replaced once");
ok(!scoreOnlyPrompt().includes(LIVE_CHECKLIST_EMPTY), "and the live text is gone");
{
  const noList = { ...D, checklist: [] };
  const runPrompt = (code) => new Function("$", "$input", "$json", code)(dollar({ "Show Context: Script": [{ show: "TQO", channel: "The Quiet Operator" }], "One Idea at a Time": [ROW], "DEVON Recall: Merge": [{ devonRecall: "" }] }), { first: () => ({ json: noList }), all: () => [{ json: noList }] }, noList)[0].json;
  const liveUser = runPrompt(read("./live/build_doctor_prompt.js")).claudeBody.messages[0].content;
  const mineUser = runPrompt(byName["Build Doctor Prompt"].parameters.jsCode).claudeBody.messages[0].content;
  ok(liveUser.includes("CHECKLIST (keep these steps as spoken, in order): (none returned)"), "live says none returned when the row stores none");
  eq(mineUser, liveUser.replace("CHECKLIST (keep these steps as spoken, in order): (none returned)", "CHECKLIST (keep these steps as spoken, in order): (not stored on this row; judge the spoken steps in the script itself)"), "the score-only message differs from live in that line and nowhere else");
  ok(mineUser.includes("LEARNING OBJECTIVE (keep word for word, inside the first 30 seconds): You will learn one thing."), "the learning objective line is untouched");
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
const PARSE_NODES = { "One Idea at a Time": [{ id: 49, video_title: "Row 49 title" }], "Show Context: Script": [{ show: "TQO", tableRef: "2GtmrFcTNqVMbddh" }], "DEVON Recall: Merge": [{ devonRecallNote: "DEVON recall: 3 record(s), 2 from Tee and 1 from DEVON" }] };
const reply = (content, extra = {}) => ({ model: "gpt-oss-120b", choices: [{ finish_reason: "stop", message: { content: typeof content === "string" ? content : JSON.stringify(content) } }], ...extra });
const parse = (out) => run("Parse Score Only", { ...PARSE_NODES, "Run Config": [{ READS: 1 }] }, [out])[0].json;
const parse3 = (outs, reads = 3) => run("Parse Score Only", { ...PARSE_NODES, "Run Config": [{ READS: reads }] }, outs)[0].json;
const good = parse(reply({ score: 92, verdict: "PASS", preserved: ["the cold open"], diagnosis: "none broken", notes: ["tighten line 4"] }));
ok(good.ok && good.verdict === "PASS" && good.score === 92, "PASS 92 is a result");
ok(/^\d{4}-\d\d-\d\dT[\d:.]+Z \| doctor 92\/100 PASS \| score only, no rewrite, gpt-oss-120b$/.test(good.line), "the line: " + good.line);
eq(gateClears(good.line), { verdict: "PASS", score: 92, clear: true }, "the gates read PASS 92 and clear it");
ok(good.feedback.startsWith("SCRIPT DOCTOR, SCORE ONLY: PASS at 92/100") && good.feedback.includes("The script was not changed."), "the note says nothing was changed");
ok(good.feedback.includes("NOTES:\n  - tighten line 4") && good.feedback.includes("PRESERVED:\n  - the cold open"), "the notes and the preserved list are kept");
eq(Object.keys(good).sort(), ["feedback", "line", "model", "ok", "reason", "recall", "rowId", "score", "show", "stamp", "tableRef", "title", "verdict", "written"], "nothing from the reply but the score, the verdict and the note travels on");
ok(good.feedback.includes("\nTEE'S RECORD: DEVON recall: 3 record(s), 2 from Tee and 1 from DEVON.\n"), "the note says what the doctor was shown of Tee's record");
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

// ---- the strictest of three reads ----------------------------------------------
{
  const r3 = parse3([reply({ score: 85, verdict: "NEEDS_REVISION", diagnosis: "the first person line", notes: ["rephrase it"] }), reply({ score: 100, verdict: "PASS", diagnosis: "None" }), reply({ score: 90, verdict: "NEEDS_REVISION", diagnosis: "the same line" })]);
  ok(r3.ok && r3.verdict === "NEEDS_REVISION" && r3.score === 85, "row 49's three reads write NEEDS_REVISION 85");
  ok(/^\d{4}-\d\d-\d\dT[\d:.]+Z \| doctor 85\/100 NEEDS_REVISION \| score only, no rewrite, 3 reads \(85, 100, 90\), gpt-oss-120b$/.test(r3.line), "the line names the three reads: " + r3.line);
  eq(gateClears(r3.line), { verdict: "NEEDS_REVISION", score: 85, clear: false }, "the gates read the strictest read and hold");
  ok(r3.feedback.startsWith("SCRIPT DOCTOR, SCORE ONLY, STRICTEST OF 3 READS: NEEDS_REVISION at 85/100") && r3.feedback.includes("READS: 1 NEEDS_REVISION 85, 2 PASS 100, 3 NEEDS_REVISION 90."), "the note lists every read");
  ok(r3.feedback.includes("DIAGNOSIS: the first person line") && r3.feedback.includes("NOTES:\n  - rephrase it") && r3.feedback.includes("OTHER READS:\n  - PASS 100: None\n  - NEEDS_REVISION 90: the same line"), "the lowest read is shown in full and the others by diagnosis");
  const allPass = parse3([reply({ score: 92, verdict: "PASS" }), reply({ score: 95, verdict: "PASS" }), reply({ score: 90, verdict: "PASS" })]);
  eq([allPass.verdict, allPass.score, gateClears(allPass.line).clear], ["PASS", 90, true], "three passes at 90 or above write PASS at the lowest and clear");
  const lowPass = parse3([reply({ score: 92, verdict: "PASS" }), reply({ score: 89.9, verdict: "PASS" }), reply({ score: 99, verdict: "PASS" })]);
  eq([lowPass.verdict, lowPass.score, gateClears(lowPass.line).clear], ["NEEDS_REVISION", 89.9, false], "a pass under 90 among passes holds the row");
  // Found by the verifier on 31e0f73: no fixture had a NEEDS_REVISION read scoring
  // above the lowest PASS, so a verdict taken from the lowest read alone passed.
  const highRevision = parse3([reply({ score: 92, verdict: "PASS" }), reply({ score: 95, verdict: "NEEDS_REVISION", diagnosis: "a revision" }), reply({ score: 90, verdict: "PASS" })]);
  eq([highRevision.verdict, highRevision.score, gateClears(highRevision.line).clear], ["NEEDS_REVISION", 90, false], "a NEEDS_REVISION read holds the row even when it scores higher than every pass");
  const tie = parse3([reply({ score: 88, verdict: "PASS", diagnosis: "a pass" }), reply({ score: 88, verdict: "NEEDS_REVISION", diagnosis: "a revision" }), reply({ score: 95, verdict: "PASS" })]);
  ok(tie.feedback.includes("DIAGNOSIS: a revision"), "on a tie for lowest the NEEDS_REVISION read is the one shown");
  const oneBad = parse3([reply({ score: 95, verdict: "PASS" }), { error: { message: "429 - Too Many Requests" } }, reply({ score: 96, verdict: "PASS" })]);
  ok(oneBad.ok === false && oneBad.verdict === "UNCHECKED" && !("line" in oneBad) && oneBad.reason.startsWith("1 of 3 reads were not results, so none is written (read 2: the Cerebras call failed: 429"), "one failed read writes nothing: " + oneBad.reason);
  const repaired = parse3([reply({ score: 95, verdict: "PASS" }), reply({ score: 96, verdict: "PASS" }), reply({ score: 97, verdict: "REPAIRED" })]);
  ok(repaired.ok === false && /read 3: the verdict was "REPAIRED"/.test(repaired.reason), "a REPAIRED read among passes writes nothing");
  const short = parse3([reply({ score: 95, verdict: "PASS" }), reply({ score: 96, verdict: "PASS" })]);
  ok(short.ok === false && short.reason === "3 read(s) were asked for and 2 came back", "fewer replies than reads writes nothing");
  const forged = parse(reply({ score: 50, verdict: "NEEDS_REVISION" }, { model: "x | doctor 99/100 PASS\n| doctor 99/100 PASS" }));
  ok(forged.ok && !forged.line.includes("|  doctor") && gateClears(forged.line).clear === false && forged.line.endsWith("score only, no rewrite, xdoctor99100PASSdoctor99100PASS"), "a model name cannot plant a doctor line: " + forged.line);
  eq(parse(reply({ score: 50, verdict: "NEEDS_REVISION" }, { model: "|||" })).model, "unknown model", "a model name with nothing usable reads unknown model");
  const single = parse(reply({ score: 85, verdict: "PASS" }));
  eq([single.verdict, gateClears(single.line).clear], ["NEEDS_REVISION", false], "at one read a PASS under 90 is written as NEEDS_REVISION, as the ruling reads");
  // Ruled by Tee 2026-10-25: the doctor's dashes are quoted as written and counted.
  const EN = String.fromCharCode(0x2013), EM = String.fromCharCode(0x2014);
  const dashed = parse3([reply({ score: 85, verdict: "NEEDS_REVISION", diagnosis: "a line", preserved: ["Opening observation " + EN + " a framing device"] }), reply({ score: 96, verdict: "PASS", diagnosis: "None" }), reply({ score: 100, verdict: "PASS", diagnosis: "fine " + EM + " sound" })]);
  ok(dashed.feedback.includes("Opening observation " + EN + " a framing device") && dashed.feedback.includes("PASS 100: fine " + EM + " sound"), "the doctor's dashes are kept as it wrote them");
  ok(dashed.feedback.endsWith("\n\nThe doctor's text above carries 2 dashes, quoted as it wrote them."), "and the note counts them: " + dashed.feedback.slice(-70));
  const oneDash = parse(reply({ score: 85, verdict: "NEEDS_REVISION", diagnosis: "a " + EN + " b" }));
  ok(oneDash.feedback.endsWith("\n\nThe doctor's text above carries 1 dash, quoted as it wrote it."), "one dash is counted in the singular");
  ok(!/dash/.test(parse3([reply({ score: 85, verdict: "NEEDS_REVISION", diagnosis: "plain" }), reply({ score: 96, verdict: "PASS" }), reply({ score: 100, verdict: "PASS" })]).feedback), "no dash, no flag line");
  ok(!new RegExp("[" + EN + EM + "]").test(dashed.feedback.replace(/Opening observation . a framing device/, "").replace(/fine . sound/, "")), "the node's own words carry no dash");
  eq([dashed.verdict, dashed.score], ["NEEDS_REVISION", 85], "and the flag changes neither the verdict nor the score");
  // Found by the verifier on e0351e1: the fixtures above could not show a dash
  // flipping a PASS, breaking the line, or being edited in the fields doctors use most.
  const unstamp = (r) => ({ ...r, stamp: "", line: r.line.replace(/^\S+/, ""), feedback: r.feedback.replace(/at \S+Z\./, "at T.") });
  const passes = (d) => [reply({ score: 96.5, verdict: "PASS", diagnosis: "sound" + d + "tight", notes: ["keep it" + d + "as is", "a" + d + "b" + d + "c"] }), reply({ score: 97, verdict: "PASS" }), reply({ score: 98, verdict: "PASS" })];
  const plainPass = unstamp(parse3(passes(" ")));
  const dashPass = unstamp(parse3(passes(EN)));
  eq([dashPass.ok, dashPass.verdict, dashPass.score, dashPass.line, gateClears("t" + dashPass.line).clear], [true, "PASS", 96.5, plainPass.line, true], "a dash leaves a passing row PASS, its line unchanged and clear");
  ok(dashPass.feedback.includes("DIAGNOSIS: sound" + EN + "tight") && dashPass.feedback.includes("  - keep it" + EN + "as is") && dashPass.feedback.includes("  - a" + EN + "b" + EN + "c"), "dashes in the diagnosis and the notes are kept as written");
  ok(dashPass.feedback.endsWith("The doctor's text above carries 4 dashes, quoted as it wrote them."), "and every one is counted, two in one note included");
  eq(dashPass.feedback.replace(/\n\nThe doctor's text above carries 4 dashes, quoted as it wrote them\.$/, "").split(EN).join(" "), plainPass.feedback, "and that line is all the flag adds");
  const recallDash = run("Parse Score Only", { ...PARSE_NODES, "Run Config": [{ READS: 3 }], "DEVON Recall: Merge": [{ devonRecallNote: "DEVON recall partial: devon-soul unavailable " + EN + " boom" }] }, [reply({ score: 96, verdict: "PASS", diagnosis: "plain" }), reply({ score: 97, verdict: "PASS" }), reply({ score: 98, verdict: "PASS" })])[0].json;
  ok(recallDash.feedback.includes("unavailable " + EN + " boom") && !/carries \d+ dash/.test(recallDash.feedback), "a dash in the recall line is not counted as the doctor's");
  const objNote = parse(reply({ score: 85, verdict: "NEEDS_REVISION", diagnosis: { where: "line 3" }, notes: [{ issue: "cut the " + EN + " range" }] }));
  ok(objNote.feedback.includes('DIAGNOSIS: {"where":"line 3"}') && objNote.feedback.includes('  - {"issue":"cut the ' + EN + ' range"}') && objNote.feedback.endsWith("carries 1 dash, quoted as it wrote it."), "a field that is not text is quoted as JSON and its dash counted");
  const noReads = run("Parse Score Only", { ...PARSE_NODES, "Run Config": [{}] }, [reply({ score: 95, verdict: "PASS" })])[0].json;
  ok(noReads.ok === false && /READS is undefined/.test(noReads.reason), "a missing READS writes nothing");
}

// ---- Compose Write -------------------------------------------------------------
const ROW49 = { id: 49, status: "Scripted", score_history: "", last_feedback: "", script: "  The script.  ", video_title: "Title 49", topic: "Topic 49", description: "Description 49", learning_objective: "By the end, you will have one thing.", broll_keywords: "desk, notebook", checklist: null, show: "TQO", season: 1, episode: 9, idea: "Idea 49", sources: '[{"url":"https://example.org","quote":"q"}]' };
const SNAPSHOT = run("DT Shim: Idea Rows", {}, [{ ...ROW49, __key: "TQO:49" }])[0].json;
const compose = (p, fresh, cfg = { WRITE: true }) => run("Compose Write", { "Parse Score Only": [p], "One Idea at a Time": [SNAPSHOT], "Run Config": [cfg] }, fresh)[0].json;
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
  [compose(good, [{ ...ROW49, score_history: "x | doctor 70/100 REPAIRED | y" }]), "a doctor line that landed during the run"],
  // Found by the review on 805060d: a hand edit during the run got a line for text the doctor never saw.
  [compose(good, [{ ...ROW49, script: "A script edited by hand during the run." }]), "a script edited during the run"],
  [compose(good, [{ ...ROW49, script: "" }]), "a script blanked during the run"],
  [compose(good, [{ ...ROW49, video_title: "A new title" }]), "a title edited during the run"],
  [compose(good, [{ ...ROW49, description: "A new description" }]), "a description edited during the run"],
  [compose(good, [{ ...ROW49, learning_objective: "A new objective." }]), "a learning objective edited during the run"],
  [compose(good, [{ ...ROW49, broll_keywords: "" }]), "b-roll cleared during the run"],
  // Found by the residual verifier on b38bdb2: sources, idea, checklist and the
  // episode fields reach the doctor too.
  [compose(good, [{ ...ROW49, sources: "" }]), "sources cleared during the run"],
  [compose(good, [{ ...ROW49, idea: "A new idea" }]), "the idea edited during the run"],
  [compose(good, [{ ...ROW49, checklist: '["one"]' }]), "a checklist added during the run"],
  [compose(good, [{ ...ROW49, episode: 10 }]), "the episode number changed during the run"],
  [compose(good, [{ ...ROW49, topic: "A new topic" }]), "the topic edited during the run"]
];
for (const [r, why] of skips) ok(r.write === false && r.written === false && r.ok === false && !("scoreHistory" in r), why + " writes nothing: " + r.reason);
ok(compose(good, [{ ...ROW49, last_feedback: "a note QC wrote", score_history: "t | 88/100 CONDITIONAL" }]).write === true, "a column the doctor was not shown may change and the line is still written");
ok(compose(good, [{ ...ROW49, script: "A script edited by hand during the run." }]).reason.startsWith("script changed on the row during the run"), "the reason names the column that changed");
const cm = compose(good, [ROW49], { WRITE: false });
ok(cm.write === false && cm.written === false && cm.measured === true && cm.ok === true && cm.verdict === "PASS" && cm.score === 92 && !("scoreHistory" in cm), "a measurement run keeps the score and writes nothing: " + cm.reason);

// ---- Confirm Write -------------------------------------------------------------
const confirm = (back) => run("Confirm Write", { "Compose Write": [c1] }, back)[0].json;
eq(confirm([{ id: 49, score_history: c1.scoreHistory, last_feedback: c1.lastFeedback }]).written, true, "written only when both columns read back as sent");
eq(confirm([{ id: 49, score_history: c1.scoreHistory, last_feedback: "" }]).written, false, "a column that did not land is not written");
eq(confirm([{}]).written, false, "nothing read back is not written");

// ---- the shipped Run Config -------------------------------------------------------
// Found by the verifier on 805060d: the tests used their own config and never read
// the shipped one, so FIRST_RUN_LIMIT could be raised without a failure.
eq(run("Run Config", {}, [{}]).map((i) => i.json), [{ FIRST_RUN_LIMIT: 1, ROW_LIMIT: 20, ONLY_ROWS: [], WRITE: true, READS: 3 }], "the first run scores one row, later runs up to 20, no row named, it writes, and each row is read three times");
// The measurement body, ruled by Tee 2026-10-24: TQO 49, nothing written.
const MEASURE = JSON.parse(read("./workflow.measure.json"));
const mByName = Object.fromEntries(MEASURE.nodes.map((n) => [n.name, n]));
eq(new Function("$", "$input", "$json", mByName["Run Config"].parameters.jsCode)(() => null, null, null).map((i) => i.json), [{ FIRST_RUN_LIMIT: 1, ROW_LIMIT: 20, ONLY_ROWS: ["TQO:49"], WRITE: false, READS: 3 }], "the measurement body reads TQO 49 three times and writes nothing");
eq(MEASURE.nodes.filter((n) => JSON.stringify(n) !== JSON.stringify(byName[n.name])).map((n) => n.name), ["Run Config"], "and differs from the real body in Run Config alone");
eq([JSON.stringify(MEASURE.connections), JSON.stringify(MEASURE.settings), MEASURE.name, MEASURE.nodes.length], [JSON.stringify(WORKFLOW.connections), JSON.stringify(WORKFLOW.settings), WORKFLOW.name, WORKFLOW.nodes.length], "same wiring, settings, name and node count");
eq(runConfig(true), runConfig().replace(RUN_CONFIG_REAL, RUN_CONFIG_MEASURE), "the swap is the one return line");

// ---- Select Rows ---------------------------------------------------------------
const CONFIG = { FIRST_RUN_LIMIT: 1, ROW_LIMIT: 20, ONLY_ROWS: [], WRITE: true, READS: 3 };
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
throws(() => select(TQO, NCO, { FIRST_RUN_LIMIT: 1, ROW_LIMIT: 20, ONLY_ROWS: [], READS: 3 }), /WRITE must be true or false, and it reads null/, "a config with no WRITE stops the run");
throws(() => select(TQO, NCO, { ...CONFIG, READS: undefined }), /READS must be a whole number from 1 to 5, and it reads null/, "a config with no READS stops the run");
throws(() => select(TQO, NCO, { ...CONFIG, READS: 6 }), /READS must be a whole number from 1 to 5/, "more than five reads stops the run");
throws(() => select(TQO, NCO, { ...CONFIG, READS: 0 }), /READS must be a whole number from 1 to 5/, "zero reads stops the run");
throws(() => select(TQO, NCO, { ...CONFIG, READS: "3" }), /READS must be a whole number from 1 to 5/, "READS as a string stops the run");
throws(() => select(TQO, NCO, { ...CONFIG, WRITE: "false" }), /WRITE must be true or false/, "a WRITE that is a string stops the run");
const picked = run("Select Rows", { "Run Config": [CONFIG], "Get TQO Scripted Rows": TQO, "Get NCO Scripted Rows": NCO }, [{}])[0].json;
eq([picked.nco, picked.__tableRef, picked.__show], [false, "2GtmrFcTNqVMbddh", "TQO"], "the row carries its show for Show Context: Script");

// ---- Run Report ----------------------------------------------------------------
const report = (results, cfg = { WRITE: true }) => run("Run Report", { "Select Rows": [{ __selectNote: "select: test" }], "Run Config": [cfg] }, results);
const r1 = report([{ show: "TQO", rowId: 49, title: "T", written: true, verdict: "PASS", score: 92 }, { show: "NCO", rowId: 30, title: "N", written: true, verdict: "NEEDS_REVISION", score: 74 }])[0].json;
ok(r1.summary.startsWith("Score-only doctor run: 2 row(s), 2 written, 1 clear the doctor check at 90, 0 not written."), r1.summary);
ok(r1.summary.includes('NCO row 30 "N": NEEDS_REVISION 74/100, the doctor line holds the row'), "a held row says so");
throws(() => report([{ show: "TQO", rowId: 49, title: "T", written: false, verdict: "UNCHECKED", score: null, reason: "the Cerebras call failed: 402" }]), /1 not written[\s\S]*NOT WRITTEN, the Cerebras call failed: 402/, "a row not written ends the run in error");
throws(() => report([{ id: 49, status: "Scripted" }]), /could not read the loop results/, "rows instead of results end the run in error");
const rm = report([{ ...cm, title: "T" }], { WRITE: false })[0].json;
ok(rm.summary.startsWith("MEASUREMENT RUN, Run Config WRITE is false: 1 row(s) scored and nothing written.") && rm.summary.includes('TQO row 49 "T": MEASURED, NOT WRITTEN: PASS 92/100. DIAGNOSIS: none broken'), "a measurement run reports the score and does not fail: " + rm.summary.split("\n")[2]);
throws(() => report([{ ...cm, title: "T" }]), /1 not written/, "the same result in a real run is a failure");
throws(() => report([{ show: "TQO", rowId: 49, title: "T", written: false, ok: false, verdict: "UNCHECKED", score: null, reason: "the Cerebras call failed: 402" }], { WRITE: false }), /NOT WRITTEN, the Cerebras call failed: 402/, "a failed call in a measurement run still ends it in error");

console.log("score-only doctor: " + checks + " checks passed");
