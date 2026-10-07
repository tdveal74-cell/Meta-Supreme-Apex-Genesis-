/**
 * Does the length check after the doctor lengthen only a script the doctor
 * left under the floor, and refuse a lengthening that moves the hook, moves
 * the close or adds a figure?
 *
 *   node n8n/tqo-v5/length_after_doctor.test.mjs
 *
 * Test 2357 (2026-10-07) is the case: expanded to 1,292, trimmed by the doctor
 * to 1,124, failed at the gate.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const load = (f) => new Function("$", "$input", "$json", readFileSync(new URL("./" + f, import.meta.url), "utf8"));
const check = load("length_after_doctor.js");
const parse = load("parse_expanded_after_doctor.js");
const budget = { json: { body: { model: "gpt-oss-120b", max_completion_tokens: 9000, messages: [{ role: "system", content: "SYS" }, { role: "user", content: "BRIEF" }] } } };
const words = (n) => Array.from({ length: n }, () => "word").join(" ");
const HOOK = "Middle managers made up one-third of all layoffs in 2023. Here is why.";
const CLOSE = "In the comments, which task will you test first?";
const doctored = (n) => ({ script: HOOK + " " + words(n) + ". " + CLOSE, title: "T", lastFeedback: "fb", expansion: "expanded" });
const $ = (name) => ({ first: () => (name === "Token Budget: Script" ? budget : null) });

// At or over the floor it passes through untouched.
let out = check($, null, doctored(1300))[0].json;
assert.equal(out.needsExpansion3, false);
assert.equal(out.expandBody, undefined);

// Under it, one expansion is prepared that pins the close and forbids new figures.
const short = doctored(1100);
out = check($, null, short)[0].json;
assert.equal(out.needsExpansion3, true);
assert.equal(out.expandBody.max_completion_tokens, 9000);
const ask = out.expandBody.messages[1].content;
assert.match(ask, /Keep the last sentence exactly as written and keep it last\. It reads: In the comments, which task will you test first\?/);
assert.match(ask, /Never add a number, a company, a person, a study/);

// The parse step.
const prev = out;
const $p = (name) => ({ first: () => ({ json: name === "Script: Short After Doctor?" ? prev : null }) });
const reply = (script) => ({ choices: [{ finish_reason: "stop", message: { content: JSON.stringify({ script }) } }] });

const MID = words(1100) + ".";
const add = (extra) => [HOOK, MID, extra, CLOSE].join(" ");
const plenty = "The mechanism is that each " + words(240) + ".";

let r = parse($p, null, reply(add(plenty)))[0].json;
assert.ok(r.script.split(/\s+/).length > 1300);
assert.equal(r.expandBody, undefined);
assert.match(r.lastFeedback, /every doctored sentence kept in order, no number, number word, name or dash added/);

// The third critic's cases, 2026-10-07, plus the first version's own.
for (const [bad, why] of [
  [add(plenty + " And 150 managers left."), /added figure\(s\).*150/],
  [add(plenty + " Seventy thousand managers left."), /number word\(s\).*seventy/],
  [add(plenty + " Twelve companies cut managers."), /number word\(s\).*twelve/],
  [add(plenty + " That is 2023 in millions of managers."), /number word|name|figure/],
  [add(plenty + " At the plant, Andy Jassy cut managers in a Stanford study."), /name\(s\).*Andy/],
  [add(plenty + " The cut \u2014 sharp."), /dash/],
  [[HOOK, "Cuts " + words(1200) + ".", plenty, CLOSE].join(" "), /changed or dropped/],
  [[HOOK, plenty, "The mechanism is that every " + words(1200) + ".", CLOSE].join(" "), /changed or dropped/],
  [add(plenty + " " + CLOSE), /appears twice/],
  ["A new hook. Here is why. " + MID + " " + plenty + " " + CLOSE, /the hook changed/],
  [[HOOK, MID, plenty, "Subscribe for more."].join(" "), /the last sentence changed/],
  [HOOK + " " + words(50) + ". " + CLOSE, /no longer/],
  // The fourth critic's cases, 2026-10-07.
  [add(plenty + " Amazon cut its managers the same way."), /name\(s\).*Amazon/],
  [add(plenty + " (Jassy) cut managers."), /name\(s\).*Jassy/],
  [add(plenty + " Gartner predicts the same."), /name\(s\).*Gartner/],
  [add(plenty + " Nine out of ten managers felt it."), /number word\(s\).*nine/],
  [add(plenty + " Nine per cent of managers felt it."), /number word\(s\)/],
  [add(plenty + " A fifth of managers quit within weeks."), /number word\(s\).*fifth/],
  [add(plenty + " The plant had 2023 workers."), /carried fewer times: 2023/],
  [[HOOK, MID, MID, CLOSE].join(" "), /appears more often/],
  [[HOOK, MID, HOOK, CLOSE].join(" "), /appears more often/],
]) {
  r = parse($p, null, reply(bad))[0].json;
  assert.equal(r.script, short.script, String(why));
  assert.match(r.lastFeedback, why);
}
r = parse($p, null, { choices: [{ finish_reason: "length", message: { content: "{" } }] })[0].json;
assert.equal(r.script, short.script);
assert.match(r.lastFeedback, /truncated/);

console.log("Length after doctor: every case behaves");
