/**
 * Does the Sources Gate refuse what the approved sources do not hold, and do
 * the writer side nodes hand the writer the sources and the presenter rule?
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
assert.match(out.gateReason, /an unnamed person or organisation cited as a source/);
assert.match(out.lastFeedback, /^earlier\n\nSCRIPT GATE FAIL/);

// Execution 2344's inventions: salary bands, a price, and an attribution to someone not approved.
out = run(CITED + " Salaries run from $110,000 to $150,000 and the course costs $199. According to Challenger, the share keeps rising.");
assert.match(out.gateReason, /\$110,000, \$150,000, \$199/);
assert.match(out.gateReason, /attributed to Challenger, which is not an approved source/);

// A year the idea does not name, or a percentage no source holds, is a figure like any other.
assert.equal(run(CITED + " It began in 2019.").status, "Error");
assert.equal(run(CITED + " About 7% noticed.").status, "Error");

// The critic's cases, 2026-10-07. A raw quote carrying a markdown link must
// not lend the numbers in its URL: 2351 slipped "30 minutes" through on a
// Bloomberg slug ending -30-of-white-collar-layoffs.
const LINKED = [{ ...SOURCES[0], quote: "- Middle managers made up [one-third of all layoffs](https://www.bloomberg.com/news/articles/2024-03-15/middle-manager-jobs-make-up-30-of-white-collar-layoffs) in 2023." }, ...SOURCES.slice(1)];
assert.match(run(CITED + " Send it 30 minutes before the call.", { row: { ...ROW, sources: JSON.stringify(LINKED.map(({ quote_text, ...rest }) => (rest.origin === "Bloomberg and Live Data Technologies" ? rest : { ...rest, quote_text }))) } }).gateReason, /not in the approved sources: 30\b/);
// Figures in words, unnamed firms, a study named after "according to a recent", a name that "found".
for (const bad of [
  "Forty-three percent of managers were cut.",
  "Seventy thousand jobs vanished.",
  "Nearly two thirds of all managers were cut.",
  "A multinational consulting firm reported a sharp reduction.",
  "According to a recent Stanford study, it is worse.",
  "McKinsey found that most managers will be replaced.",
  "Seats cost $41 a month.",
]) assert.equal(run(CITED + " " + bad).status, "Error", bad);
// What the sources do say, in words or with a unit, passes; so do thousands separators.
for (const good of [
  "That is one in five companies, by Gartner's projection.",
  "Exactly one-third of the layoffs hit managers, according to Bloomberg and Live Data Technologies.",
  "Korn Ferry put it at 41% of professionals.",
  "It found nothing new.",
]) assert.equal(run(CITED + " " + good).status, "Scripted", good);
const comma = { ...ROW, sources: JSON.stringify([{ ...SOURCES[1], quote_text: "Korn Ferry counted 1,200 managers." }]) };
assert.equal(run("Korn Ferry counted 1200 managers.", { row: comma }).status, "Scripted");
assert.equal(run("Korn Ferry counted 1,300 managers.", { row: comma }).status, "Error");

// The second critic's cases, 2026-10-07. An approved name ending one sentence
// no longer carries an unapproved one in the next past the check, and a group
// with no name standing in for a source is refused unless an approved origin
// is named in the same sentence.
assert.match(run(CITED + " Spans grew, according to Gallup. Microsoft found that managers are leaving.").gateReason, /attributed to Microsoft/);
assert.match(run(CITED + " Managers who have applied this three step plan report that it frees up time.").gateReason, /unnamed person or organisation cited as a source: "Managers who have applied/);
assert.match(run(CITED + " Companies that tried this found that it works.").gateReason, /unnamed person or organisation/);
assert.equal(run(CITED + " Managers report to directors, and that is the point.").status, "Scripted");
assert.equal(run(CITED + " In the Korn Ferry survey, professionals said that manager roles were cut.").status, "Scripted");

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

// NCO was ruled to the same standard the same day, so the show makes no difference.
assert.equal(run("Cuts hit 41% of teams.", { show: "NCO" }).status, "Scripted");
assert.equal(run("Cuts hit 77% of teams.", { show: "NCO" }).status, "Error");

// A named person is not an unnamed source.
assert.equal(run(CITED + " In an interview with Gallup chief scientist Jim Harter, he said spans keep widening.").status, "Scripted");

// Military identifiers in NCO prose are names, not figures (ruled 2026-10-07),
// and only in their narrow forms.
for (const good of [
  "First formation is at 0600, and it was at 0600 in the 101st Airborne too.",
  "Bring your DD-214 and your DA Form 2166-9 to the counter.",
  "Chow closes after 1800 hours.",
  "I served in the 82nd Airborne Division for three years.",
]) assert.equal(run(CITED + " " + good, { show: "NCO" }).status, "Scripted", good);
// The third critic's leaks, 2026-10-07. Every one passed the first version of
// the blanking and must be refused: a percent or a magnitude behind a form
// prefix, a duration read as a clock time, a count read as an ordinal.
for (const bad of [
  "The VA 70% disability rating changes everything.",
  "The VA 70 percent rating changes everything.",
  "DA 77% of soldiers agree.",
  "The VA 40,000 claim backlog is real.",
  "VA 2.5 million veterans wait.",
  "The course takes 1500 hours to finish.",
  "Soldiers log 2000 hours a year.",
  "Only 0750 soldiers reenlisted.",
  "Retention fell for the 12th consecutive year.",
  "The unit came in 37th in the Army.",
  "The unit finishing 37th in the Army was cut.",
  "He scored in the 90th-percentile band.",
  "Retention fell for the 2,000th time.",
  "By 2030 hours were cut.",
  "I served with the 82nd for three years.",
  "Promotion takes 11B, said nobody.",
  "Pay starts at $50K, and the 1800 recruits all got it.",
  // A unit or magnitude makes a different figure from the sourced numeral.
  "41 million managers lost jobs.",
  "41K managers lost jobs.",
  "10 million jobs vanished.",
  "The share hit 12.1 % of managers.",
  "The share hit 10.9 per cent of managers.",
  "Twelve companies cut managers.",
]) assert.equal(run(CITED + " " + bad, { show: "NCO" }).status, "Error", bad);
assert.equal(run(CITED + " Korn Ferry put it at 41 % of professionals.").status, "Scripted");

// A projection stated as fact needs an approved name in its own sentence, even
// when its figure is sourced (ruled 2026-10-07), and a verb is not a name.
for (const bad of [
  "By 2030, 41% of managers will be gone.",
  "Half of these roles will disappear.",
  "One in five companies is expected to cut managers next.",
  "One-third of all managers will be gone by next year.",
  "One third of all managers will be gone by next year.",
  "41% of managers are going to be gone.",
  "41% of managers could be gone next year.",
  "Managers'll be cut by 41%.",
  "41 percent of managers are likely to be cut.",
  "Hiring will ramp down, and 41% of managers will be gone.",
]) assert.match(run(CITED + " " + bad).gateReason, /a projection with a figure and no approved source named/, bad);
for (const good of [
  "Gartner expects that one in five companies will cut over half of their managers.",
  "You will need 3 things.",
  "This will change how you plan.",
  "You will spend half the meeting listening.",
  "This will take half an hour.",
]) assert.equal(run(CITED + " " + good).status, "Scripted", good);

// The writer side, for both shows: the rule is appended and the sources are listed.
const writerNode = (file, show, body) =>
  new Function("$", "$input", readFileSync(new URL("./" + file, import.meta.url), "utf8"))(
    (node) => ({ first: () => ({ json: node === "Show Context: Script" ? { show } : ROW }) }),
    { first: () => ({ json: { airtableId: 46, body } }) },
  )[0].json;
for (const show of ["TQO", "NCO"]) {
  const w = writerNode("sources_rule.js", show, { system: "SYS", messages: [] });
  assert.equal(w.sourcesApproved, 4);
  assert.match(w.body.system, /^SYS\n\n=== SOURCES YOU MAY CITE/);
  assert.match(w.body.system, /\[S2\] Korn Ferry, reported by Ramp: "And last year, 41%/);
}

// NCO is presenter led from the same ruling. TQO's own prompt already says so,
// so the NCO Presenter Rule leaves TQO untouched.
const ncoPresenter = writerNode("nco_presenter_rule.js", "NCO", { system: "SYS", messages: [] });
assert.match(ncoPresenter.body.system, /Where anything above says narrator, it means him speaking to camera\./);
assert.match(ncoPresenter.body.system, /PRESENTER: Terrance Veal presents every NCO Forge episode himself, on camera, in his own likeness and his own cloned voice\./);
assert.equal(writerNode("nco_presenter_rule.js", "TQO", { system: "SYS", messages: [] }).body.system, "SYS");

// The doctor sees the same approved sources for both shows, NCO included.
for (const show of ["TQO", "NCO"]) {
  const doc = new Function("$", "$input", readFileSync(new URL("./doctor_sources.js", import.meta.url), "utf8"))(
    (node) => ({ first: () => ({ json: node === "Show Context: Script" ? { show } : ROW }) }),
    { first: () => ({ json: { recordId: 46, original: {}, claudeBody: { system: "S", messages: [{ role: "user", content: "SCRIPT: x" }] } } }) },
  )[0].json;
  assert.match(doc.claudeBody.messages[0].content, /^APPROVED SOURCES \(the only figures and named sources that may stand\):\n\[S1\] Bloomberg and Live Data Technologies/, show);
  assert.match(doc.claudeBody.system, /SOURCES: a figure, percentage, dollar amount or named study that is not in APPROVED SOURCES is invented\./, show);
}

console.log("Sources Gate: every case behaves");
