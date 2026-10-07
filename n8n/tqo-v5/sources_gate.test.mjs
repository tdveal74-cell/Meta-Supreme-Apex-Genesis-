/**
 * Does the Sources Gate refuse what the approved sources do not hold?
 *
 *   node n8n/tqo-v5/sources_gate.test.mjs
 *
 * The node body runs inside a Function with `$` and `$input` stubbed. The
 * sources are row 46's four, approved by TQO Research execution 2350, and the
 * failing sentences are copied from manual execution 2351, the first script
 * written under the Sources Rule: it cited all four sources correctly and then
 * invented a division, a plant and an interview around them.
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const gate = new Function("$", "$input", readFileSync(new URL("./sources_gate.js", import.meta.url), "utf8"));
const SOURCES = [
  { url: "https://ramp.com/r", publisher: "Ramp", origin: "Bloomberg and Live Data Technologies", quote: "x", quote_text: "Middle managers made up one-third of all layoffs in 2023, according to a Bloomberg and Live Data Technologies analysis.", claim: "In 2023, middle managers accounted for one-third of all layoffs." },
  { url: "https://ramp.com/r", publisher: "Ramp", origin: "Korn Ferry", quote: "x", quote_text: "And last year, 41% of professionals in a Korn Ferry survey said their company had cut roles at the manager level.", claim: "c" },
  { url: "https://ramp.com/r", publisher: "Ramp", origin: "Gallup", quote: "x", quote_text: "According to Gallup, the average number of people reporting to managers climbed from 10.9 in 2024 to 12.1 last year.", claim: "c" },
  { url: "https://y.com/v", publisher: "Full Disclosure", origin: "Gartner", quote: "x", quote_text: "Gartner predicts that by 2026, one in five companies will use AI to eliminate over half of their managers.", claim: "c" },
];
const ROW = { topic: "The Middle Is the Target", angle: "AI did not come for the bottom of the org chart.", idea: "Where the 2026 AI layoffs actually land", video_title: "The Middle Is the Target", sources: JSON.stringify(SOURCES) };
const PASSED = "SCRIPT GATE PASS at t\n  words 1300\n  writer: w\n\nCleared for Promote.";
const run = (script, { show = "TQO", row = ROW, report = PASSED } = {}) => {
  const d = { status: report.startsWith("SCRIPT GATE PASS") ? "Scripted" : "Error", gateFailures: [], gateReport: report, lastFeedback: "earlier\n\n" + report, script };
  const $ = (node) => ({ first: () => ({ json: node === "Show Context: Script" ? { show } : row }) });
  return gate($, { first: () => ({ json: d }) })[0].json;
};

const CITED = "Middle managers made up one-third of all layoffs in 2023, according to Bloomberg and Live Data Technologies. A Korn Ferry survey found that 41 percent of professionals saw manager roles cut. According to Gallup, span of control grew from 10.9 direct reports in 2024 to 12.1 last year. Gartner projects that by 2026 one in five companies will cut over half of their managers. Here are the 3 steps.";

let out = run(CITED);
assert.equal(out.status, "Scripted", out.gateReason);
assert.match(out.gateReport, /sources: 4 approved \| \d+ numeral\(s\) \| 0 unsourced/);

// Execution 2351's inventions.
out = run(CITED + " For example, in a software division that cut 150 positions, roughly one third (about 50) were middle level managers. In a follow up interview with a senior HR director at a manufacturing firm, the director confirmed it: out of a 300 person plant, 124 managers had been reduced in the previous 12 months.");
assert.equal(out.status, "Error");
assert.match(out.gateReason, /figure\(s\) not in the approved sources: 150, 50, 300, 124, 12/);
assert.match(out.gateReason, /an unnamed person cited as a source/);
assert.match(out.lastFeedback, /^earlier\n\nSCRIPT GATE FAIL/);

// Execution 2344's inventions: salary bands, a price, and an attribution to someone not approved.
out = run(CITED + " Salaries run from $110,000 to $150,000 and the course costs $199. According to Challenger, the share keeps rising.");
assert.match(out.gateReason, /\$110,000, \$150,000, \$199/);
assert.match(out.gateReason, /attributed to Challenger, which is not an approved source/);

// A year the idea does not name, or a percentage no source holds, is a figure like any other.
assert.equal(run(CITED + " It began in 2019.").status, "Error");
assert.equal(run(CITED + " About 7% noticed.").status, "Error");

// No sources means no figures beyond small counts.
out = run("Here are 3 steps and 5 questions.", { row: { ...ROW, sources: "" } });
assert.equal(out.status, "Scripted");
assert.equal(run("Cuts hit 41% of teams.", { row: { ...ROW, sources: "" } }).status, "Error");

// A failure the earlier gate already found is kept, not replaced.
const failedEarlier = "SCRIPT GATE FAIL at t\n  words 900\n  writer: w\n\nFAILED BECAUSE:\n  - script is 900 words";
out = run(CITED + " Costs reached $90.", { report: failedEarlier });
assert.equal(out.status, "Error");
assert.match(out.gateReport, /FAILED BECAUSE:\n  - script is 900 words/);
assert.match(out.gateReport, /SOURCES GATE FAILED BECAUSE:/);

// NCO was not ruled, so NCO passes through untouched.
const nco = run("Cuts hit 41% of teams.", { show: "NCO" });
assert.equal(nco.status, "Scripted");
assert.equal(nco.gateReport, PASSED);

// A named person is not an unnamed source.
assert.equal(run(CITED + " In an interview with Gallup chief scientist Jim Harter, he said spans keep widening.").status, "Scripted");

console.log("Sources Gate: every case behaves");
