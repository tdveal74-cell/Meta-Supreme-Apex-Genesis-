/**
 * Does TQO Research keep only quotes that are really on the page?
 *
 *   node n8n/tqo-research/research.test.mjs
 *
 * The node bodies are plain JS that read n8n's `$('Node')` and `$input` and
 * end in a `return`, so they run here inside a Function with both stubbed. No
 * n8n, no network, no model.
 *
 * WHY THESE CASES
 *
 * The real ones come from 2026-10-07. Execution 2349 approved five blog
 * sources that repeated figures without naming who produced them, so the
 * check now demands an origin named inside the quote, and execution 2350's
 * Ramp page is the fixture for a quote that names its origin through a
 * markdown link. The invented 41 percent below is the failure the check
 * exists for: a model copying a sentence and changing one number.
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const load = (name) => new Function("$", "$input", readFileSync(new URL("./" + name, import.meta.url), "utf8"));
const run = (name, input, refs = {}) =>
  load(name)((node) => ({ first: () => ({ json: refs[node] }) }), { first: () => ({ json: input }), all: () => [].concat(input).map((json) => ({ json })) });

const row = { id: 46, topic: "The Middle Is the Target", angle: "a", idea: "i", searchQuery: "q" };
const RAMP = "# The pure manager layoffs\n\nRamp\n\n- Middle managers made up [one-third of all layoffs](https://www.bloomberg.com/x) in 2023, according to a **Bloomberg and Live Data Technologies** analysis.\n\nAnd last year, 41% of professionals in a Korn Ferry survey said their company had [cut roles at the manager level](https://www.kornferry.com/y).\n\nManager headcount at public companies fell 6.1% between 2022 and 2025.\n";

// Build Extract Prompt keeps readable pages and refuses an empty search honestly.
const ex = run("build_extract_prompt.js", { success: true, data: { web: [{ url: "https://ramp.com/r", title: "R", markdown: RAMP }, { url: "https://www.instagram.com/x", markdown: "" }] } }, { "One Row at a Time": row })[0].json;
assert.equal(ex.hasPages, true);
assert.equal(ex.pages.length, 1, "a page with no text is not a page");
const none = run("build_extract_prompt.js", { error: { message: "402 Payment Required" } }, { "One Row at a Time": row })[0].json;
assert.equal(none.hasPages, false);
assert.match(none.research_note, /^No source written: .*402 Payment Required/);

const offer = (sources) => ({ choices: [{ message: { content: JSON.stringify({ sources }) } }] });
const check = (sources) => run("quote_check.js", offer(sources), { "Build Extract Prompt": ex })[0].json;

// A real quote naming its origin through a markdown link and bold survives.
let qc = check([{ page: 1, publisher: "Ramp", origin: "Bloomberg and Live Data Technologies", quote: "- Middle managers made up [one-third of all layoffs](https://www.bloomberg.com/x) in 2023, according to a Bloomberg and Live Data Technologies analysis.", claim: "c" }]);
assert.equal(qc.checked.length, 1, JSON.stringify(qc.dropped));
assert.equal(qc.checked[0].quote_text, "Middle managers made up one-third of all layoffs in 2023, according to a Bloomberg and Live Data Technologies analysis.");

// One changed number is not on the page.
qc = check([{ page: 1, publisher: "Ramp", origin: "Korn Ferry", quote: "And last year, 14% of professionals in a Korn Ferry survey said their company had cut roles at the manager level.", claim: "c" }]);
assert.deepEqual(qc.dropped.map((d) => d.reason), ["quote not found on the page"]);

// A figure on the page whose producer the quote does not name is refused, the 2349 failure.
qc = check([{ page: 1, publisher: "Ramp", origin: "Live Data Technologies", quote: "Manager headcount at public companies fell 6.1% between 2022 and 2025.", claim: "c" }]);
assert.match(qc.dropped[0].reason, /is not named in the quote/);

// No origin, no publisher, a page that does not exist, a duplicate.
const korn = { page: 1, publisher: "Ramp", origin: "Korn Ferry", quote: "And last year, 41% of professionals in a Korn Ferry survey said their company had cut roles at the manager level.", claim: "c" };
qc = check([{ ...korn, origin: "" }, { ...korn, publisher: "" }, { ...korn, page: 9 }, korn, korn]);
assert.deepEqual(qc.dropped.map((d) => d.reason), ["no origin named", "no publisher", "no such page", "duplicate"]);
assert.equal(qc.checked.length, 1);

// A reply that is not JSON writes nothing and says so.
const bad = run("quote_check.js", { choices: [{ message: { content: "not json" } }] }, { "Build Extract Prompt": ex })[0].json;
assert.equal(bad.checked.length, 0);
assert.equal(bad.research_note, "No source written: the extraction reply was not JSON.");

// The doctor only votes. Its verdict cannot change the checked text, and an unreadable verdict approves nothing.
const doctorIn = run("build_doctor_prompt.js", qc, { "One Row at a Time": row })[0].json;
assert.match(doctorIn.body.messages[1].content, /ORIGIN OF THE FIGURE: Korn Ferry/);
const verdict = (content) => run("compose_approved_sources.js", { choices: [{ message: { content } }] }, { "Build Doctor Prompt": doctorIn })[0].json;
const ok = verdict(JSON.stringify({ verdicts: [{ index: 0, verdict: "approve", reason: "named survey", quote: "rewritten by the doctor" }] }));
assert.equal(ok.approved, 1);
assert.equal(JSON.parse(ok.sources)[0].quote, korn.quote);
const rejected = verdict(JSON.stringify({ verdicts: [{ index: 0, verdict: "reject", reason: "vendor" }] }));
assert.equal(rejected.sources, "");
assert.match(rejected.research_note, /doctor approved none: vendor/);
assert.equal(verdict("garbage").sources, "");

// Only locked Idea rows without a usable source are picked, oldest first, two at most.
const picked = run("rows_needing_sources.js", [
  { id: 47, status: "Idea", package_locked: "", sources: null },
  { id: 46, status: "Idea", package_locked: "tee", sources: null },
  { id: 5, status: "Idea", package_locked: "tee", sources: '[{"url":"u","quote":"q"}]' },
  { id: 3, status: "Idea", package_locked: "1", sources: "not json" },
  { id: 2, status: "Scripted", package_locked: "tee", sources: null },
  { id: 1, status: "Idea", package_locked: "tee", sources: "[]" },
]).map((i) => i.json.id);
assert.deepEqual(picked, [1, 3]);

// The balance floor refuses a low balance and a balance it cannot read.
assert.equal(run("credit_floor.js", { success: true, data: { remainingCredits: 1279 } })[0].json.firecrawlCredits, 1279);
assert.throws(() => run("credit_floor.js", { data: { remainingCredits: 99 } }), /under the floor of 100/);
assert.throws(() => run("credit_floor.js", { foo: 1 }), /could not read the Firecrawl balance/);

console.log("TQO Research: every case behaves");
