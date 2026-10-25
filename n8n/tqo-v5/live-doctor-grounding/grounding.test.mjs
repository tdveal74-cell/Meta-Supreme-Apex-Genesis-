/**
 * The live doctor grounding, ruled by Tee on 2026-10-25 on a card:
 *
 *   node n8n/tqo-v5/live-doctor-grounding/grounding.test.mjs
 *
 * "Both shows, live too": the doctor in TQO FINAL V5 gets what the score-only
 * doctor was given, Tee's ruling on first person that only addresses the
 * viewer and the measured position of the learning objective with the brief's
 * lines named, through a new node, Doctor: Ground the Request, between Token
 * Budget: Doctor and Run Script Doctor (Cerebras).
 *
 * "Allow a comments question": an NCO episode may end on one specific question
 * for the comments or on a quiet action, and the NCO branch of Build Doctor
 * Prompt says such a question is not engagement bait. after.js is before.js
 * with the one text in replacement.json replaced. The score-only doctor makes
 * the same replacement from the same file.
 *
 * The new node is Score Only: Final Word without its score-only clause. This
 * test runs both on the same requests and fails if they differ in anything but
 * that clause. Rows here are synthetic.
 */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { NCO_CLOSE } from "../doctor-score-only/build.mjs";

const read = (rel) => readFileSync(new URL(rel, import.meta.url), "utf8");
const sha = (s) => createHash("sha256").update(s, "utf8").digest("hex");
const M = JSON.parse(read("./manifest.json"));
const R = JSON.parse(read("./replacement.json"));
const before = read("./before.js");
const after = read("./after.js");
const ground = read("./ground_request.js");
const SO = JSON.parse(read("../doctor-score-only/workflow.json"));
const finalWord = SO.nodes.find((n) => n.name === "Score Only: Final Word").parameters.jsCode;
let checks = 0;
const eq = (a, b, msg) => { assert.deepEqual(a, b, msg); checks++; };
const ok = (v, msg) => { assert.ok(v, msg); checks++; };
const DASH = new RegExp("[" + String.fromCharCode(0x2013, 0x2014) + "]");

// ---- The bodies are the ones the manifest names --------------------------------
eq(M.workflowId, "qEkGOUsNyVaRAmm6", "TQO FINAL V5");
eq(sha(before), M.before.sha256, "before.js is the body the manifest names");
eq(before, read("../live-doctor-checklist-fix/after.js"), "before.js is the live Build Doctor Prompt the checklist fix published");
eq(M.before.versionId, JSON.parse(read("../live-doctor-checklist-fix/manifest.json")).after.versionId, "and the version it starts from is the one that fix published");
eq(sha(after), M.change[0].sha256, "after.js is the body the manifest names");
eq(sha(ground), M.change[1].sha256, "ground_request.js is the body the manifest names");
eq(before.split(R.old).length, 2, "the replaced text occurs once");
eq(before.replace(R.old, () => R.new), after, "after.js is before.js with that text replaced and nothing else");
eq(R, NCO_CLOSE, "the score-only doctor makes the same replacement");
for (const [name, text] of [["after.js", after], ["ground_request.js", ground], ["replacement.json", JSON.stringify(R)]]) {
  eq(DASH.test(text), false, name + " carries no em or en dash");
  eq(/\\u20[12][34]/.test(text), false, name + " carries no escaped dash for n8n to decode");
}
eq(M.change[1].node.name, "Doctor: Ground the Request", "the new node's name");
eq([M.change[1].node.type, M.change[1].node.typeVersion], ["n8n-nodes-base.code", 2], "a Code node, the version the live Code nodes use");
eq(M.change[2].remove, ["Token Budget: Doctor", "Run Script Doctor (Cerebras)"], "the one edge it replaces");
eq(M.change[2].add, [["Token Budget: Doctor", "Doctor: Ground the Request"], ["Doctor: Ground the Request", "Run Script Doctor (Cerebras)"]], "and the two edges that replace it");

// ---- The live chain on synthetic rows -----------------------------------------
const dollar = (nodes) => (name) => {
  if (!(name in nodes)) throw new Error("no node " + name);
  const items = nodes[name].map((json) => ({ json }));
  return { first: () => items[0], all: () => items, item: items[0] };
};
const exec = (code, nodes, json) => {
  const items = [{ json }];
  return new Function("$", "$input", "$json", "require", code)(dollar(nodes), { first: () => items[0], all: () => items }, json, () => { throw new Error("no require"); })[0].json;
};
const LIVE = (f) => read("../doctor-score-only/live/" + f);
const LO = "By the end, you will have a one-page work sample that shows your judgment and separates measured results from proposed improvements.";
const words = (n, w = "word") => Array.from({ length: n }, (_, i) => w + i).join(" ");
const chain = (show, script, lo) => {
  const ctx = { show, channel: show === "NCO" ? "NCO Forge" : "The Quiet Operator" };
  const row = { id: 7, sources: "" };
  const d = { recordId: 7, title: "T", description: "D", broll: "b", learningObjective: lo, checklist: ["one", "two", "three"], script };
  const pr = exec(after, { "Show Context: Script": [ctx], "One Idea at a Time": [row], "DEVON Recall: Merge": [{ devonRecall: "" }] }, d);
  const so = exec(LIVE("doctor_sources.js"), { "One Idea at a Time": [row] }, pr);
  const bu = exec(LIVE("token_budget_doctor.js"), {}, so);
  const nodes = { "Build Doctor Prompt": [pr], "Show Context: Script": [ctx] };
  return { pr, bu, nodes };
};
const FINAL = new Function("return " + finalWord.match(/^const FINAL = ('[^\n]*');$/m)[1])();
const VOICE = new Function("return " + ground.match(/^const VOICE = ('[^\n]*');$/m)[1])();
eq(VOICE, new Function("return " + finalWord.match(/^const VOICE = ('[^\n]*');$/m)[1])(), "the live node carries the score-only voice ruling word for word");
ok(VOICE.includes("is the viewer being addressed, not Terrance"), "and it says whom the line is about");
const cases = [
  ["TQO, objective at word 31", "TQO", "Years of experience can be hard to inspect when somebody sees only a job title. Show the decisions that made the work dependable. That gives them evidence they can question. " + LO + " " + words(100), LO],
  ["TQO, objective past 70 words", "TQO", words(80) + " " + LO + " " + words(10, "tail"), LO],
  ["TQO, objective spoken twice", "TQO", "Open here. " + LO + " " + words(20) + " " + LO.toUpperCase().replace(/,/g, ""), LO],
  ["TQO, objective never spoken", "TQO", words(40), LO],
  ["TQO, no objective stored", "TQO", words(40), ""],
  ["NCO", "NCO", "Walk into the room. " + words(60), LO],
  // Found by the verifier on db5fc1b: with no case for these, a live node that
  // dropped digits or joined hyphens in its normaliser, or moved the window by
  // one word, passed every check but the hash pin.
  ["TQO, objective ending on word 70", "TQO", words(49) + " " + LO + " " + words(10, "tail"), LO],
  ["TQO, objective ending on word 71", "TQO", words(50) + " " + LO + " " + words(10, "tail"), LO],
  ["TQO, objective with digits and a hyphen", "TQO", "Start. In 3 steps, the one page plan for Q4 2026 is ready. " + words(10), "In 3 steps the one-page plan for Q4 2026 is ready"],
  ["TQO, a different digit", "TQO", "Start. Step 4 comes first here. " + words(10), "Step 3 comes first here"],
  ["TQO, a hyphen against a word run together", "TQO", "Start. The onepage plan is ready. " + words(10), "The one-page plan is ready"]
];
for (const [label, show, script, lo] of cases) {
  const { bu, nodes } = chain(show, script, lo);
  const live = exec(ground, nodes, bu).claudeBody;
  const so = exec(finalWord, nodes, bu).claudeBody;
  eq(live.messages[1].content, so.messages[1].content, label + ": the live user message is the score-only one");
  eq(live.messages[0].content + FINAL, so.messages[0].content, label + ": the live system message is the score-only one less its score-only clause");
  eq(live.messages[0].content, bu.claudeBody.messages[0].content + VOICE, label + ": the system message gains the voice ruling and nothing else");
  ok(live.messages[1].content.endsWith("\n\nSCRIPT:\n" + script), label + ": the script after SCRIPT: is untouched");
  eq({ ...live, messages: null }, { ...bu.claudeBody, messages: null }, label + ": every other field of the request is unchanged");
  ok(!live.messages[0].content.includes("Score only"), label + ": the live doctor is not told to score only, so it still repairs");
}
{
  const { bu, nodes } = chain("TQO", "Years of experience can be hard to inspect when somebody sees only a job title. Show the decisions that made the work dependable. That gives them evidence they can question. " + LO + " " + words(100), LO);
  const user = exec(ground, nodes, bu).claudeBody.messages[1].content;
  ok(user.includes("from word 31 to word 51 of 151, inside the first 70 words. Its position meets the brief; do not mark it down for where it sits. The script speaks it once."), "row 49's shape is measured at word 31");
  const bad = { claudeBody: { ...bu.claudeBody, messages: [bu.claudeBody.messages[0], { role: "user", content: bu.claudeBody.messages[1].content + " extra" }] } };
  assert.throws(() => exec(ground, nodes, bad), /Doctor: Ground the Request could not find the script after SCRIPT:/, "a message whose script is not the row's stops before the call"); checks++;
  assert.throws(() => exec(ground, nodes, { claudeBody: { ...bu.claudeBody, messages: [...bu.claudeBody.messages, { role: "assistant", content: "x" }] } }), /one system message and one user message/, "a third message stops before the call"); checks++;
}

// ---- The NCO close sentence ----------------------------------------------------
// Build Doctor Prompt keeps the system text in claudeBody.system; Token Budget:
// Doctor moves it into the messages later.
for (const show of ["TQO", "NCO"]) {
  const pr = chain(show, words(40), LO).pr.claudeBody;
  const sys = pr.system.split("\n");
  eq(sys.filter((l) => l === R.sentence).length, show === "NCO" ? 1 : 0, show + (show === "NCO" ? ": the NCO close sentence is said once" : ": TQO is not given the NCO close sentence"));
  ok(sys.some((l) => l.includes("a specific question for the comments is not a solicitation or engagement bait")) === (show === "TQO"), show + ": the TQO sentence stays TQO's own");
  const was = (() => {
    const ctx = { show, channel: show === "NCO" ? "NCO Forge" : "The Quiet Operator" };
    const d = { recordId: 7, title: "T", description: "D", broll: "b", learningObjective: LO, checklist: ["one", "two", "three"], script: words(40) };
    return exec(before, { "Show Context: Script": [ctx], "One Idea at a Time": [{ id: 7, sources: "" }], "DEVON Recall: Merge": [{ devonRecall: "" }] }, d).claudeBody;
  })();
  eq(sys.filter((l) => l !== R.sentence), was.system.split("\n"), show + ": nothing else in the system text changes");
  eq(pr.messages, was.messages, show + ": and the user message is unchanged");
}
ok(R.sentence.includes("an NCO episode may end on one or on a quiet action"), "the sentence allows a closing question and does not require one");
ok(R.sentence.endsWith("A request to like, to subscribe, or to visit a link or an audit is a solicitation; remove it."), "and keeps TQO's line on solicitations");

console.log("live doctor grounding: " + checks + " checks passed");
