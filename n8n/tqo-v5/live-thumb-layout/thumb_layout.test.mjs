/**
 * The thumbnail layout fix in Thumb: Pick Still, ruled by Tee on 2026-10-27 on
 * two cards, "Fix both, prove first" and "Draft and publish now":
 *
 *   node n8n/tqo-v5/live-thumb-layout/thumb_layout.test.mjs
 *
 * Two defects, both measured in harness execution 4737. The navy panel was
 * drawn about 15 percent opaque, because GraphicsMagick reads the last pair of
 * an 8 digit colour as transparency and the code sent D9. And a full headline
 * line ran past the panel, because the wrap assumed 0.52 em a character where
 * Arial capitals run about 0.66 em. The live node sends 26 and works the wrap out
 * from Arial's advance widths with the same word wrap Compose applies.
 *
 * This test holds the live node to the manifest, and checks the layout on 600
 * generated headlines and nine
 * crafted ones with an independent copy of n8n's wrap loop. The width table is
 * checked against the one line measured on the instance and, entry by entry,
 * against Liberation Sans, the metric twin of Arial, read from the font file's
 * own tables by liberation_widths.py. It reads the export, not the instance.
 *
 * A fresh critic on 2026-10-27 showed that the first version of this test let
 * TEXT_BUDGET 760, a looser height rule, a search bound of 1, a drifted wrap and
 * drifted widths through, once every pinned copy was re-baselined together. The
 * layout constants, the replica check and the crafted headlines below each turn
 * one of those back into a failure. Two verifiers then found a budget loosened
 * by a few pixels and a wrap one short of the search's answer still passing,
 * and a third found an untrimmed headline and a raised search floor passing.
 * The last four crafted headlines and the floor pin catch those. This is not a
 * complete specification of the node: it catches each drift a reviewer has
 * found, and a deliberate edit to the live Pick Still still needs its own review.
 */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";

const read = (rel) => readFileSync(new URL(rel, import.meta.url), "utf8");
const sha = (s) => createHash("sha256").update(s, "utf8").digest("hex");
const M = JSON.parse(read("./manifest.json"));
const EXPORT = JSON.parse(read("../exports/qEkGOUsNyVaRAmm6_active.json"));
const picks = EXPORT.nodes.filter((n) => n.name === "Thumb: Pick Still");
// The fix is live, so the code under test is the live node read out of the export.
const after = picks[0].parameters.jsCode;
let checks = 0;
const eq = (a, b, msg) => { assert.deepEqual(a, b, msg); checks++; };
const ok = (v, msg) => { assert.ok(v, msg); checks++; };
const FONT = JSON.parse(read("./liberation_sans_widths.json"));

// ---- The files are the ones the manifest names ---------------------------------
eq(M.workflowId, "qEkGOUsNyVaRAmm6", "TQO FINAL V5");
eq(M.node, "Thumb: Pick Still", "the one node it changes");
eq(picks.length, 1, "the export has one Thumb: Pick Still");
eq(sha(after), M.after.sha256, "the live Pick Still is the body the manifest names");
eq(M.rollbackAtPublish, "publish " + M.before.versionId, "at publish, rollback was the version before");
ok(!M.rollback.startsWith("publish ") && M.rollback.includes("404"), "the before version is pruned, so rollback is an edit, not a publish");
eq(read("../thumb_pick_still.js"), after, "the repo's Pick Still is the live one");

// ---- Running the live Pick Still -------------------------------------------------
const run = (plan, photos = [{ id: 1, photographer: "x", src: { landscape: "https://images.pexels.com/a.jpg" } }]) => {
  const $ = (name) => {
    if (name === "Thumb: Plan") return { first: () => ({ json: plan }) };
    throw new Error("Node '" + name + "' hasn't been executed");
  };
  return new Function("$", "$json", after)($, { photos })[0].json;
};

// n8n Edit Image, text operation, copied from EditImage.node.ts on n8n master as
// read on 2026-10-27, so the test does not share the live Pick Still's own copy.
const n8nWrap = (text, lineLength) => {
  const lines = [];
  let currentLine = "";
  text.split("\n").forEach((textLine) => {
    textLine.split(" ").forEach((textPart) => {
      if (currentLine.length + textPart.length + 1 > lineLength) {
        lines.push(currentLine.trim());
        currentLine = `${textPart} `;
        return;
      }
      currentLine += `${textPart} `;
    });
    lines.push(currentLine.trim());
    currentLine = "";
  });
  return lines;
};

const ARIAL = new Function(after.match(/const ARIAL = (\{[\s\S]*?\});/)[0] + "\nreturn ARIAL;")();
const width = (s, px) => [...s].reduce((w, ch) => w + (ARIAL[ch] || 1000), 0) * px / 1000;
const BUDGET = 680;
const PANEL_RIGHT = 760;
const TEXT_X = 72;
const TOP = { 104: 250, 84: 235, 66: 225, 54: 220 };

// ---- The layout constants are the ones this test checks against ---------------
// The checks below use their own copies of these numbers, so a change to the
// node's copy would otherwise go unseen until a headline happened to land in the
// gap. TEXT_BUDGET 760 is the case the critic found: it passed every check here.
const constant = (name) => (after.match(new RegExp("\\nconst " + name + " = ([^;]+);")) || [])[1];
eq(constant("TEXT_BUDGET"), String(BUDGET), "the live Pick Still keeps the text budget at " + BUDGET + " px");
eq(constant("FLOOR_Y"), "680", "the live Pick Still keeps the block above y 680");
eq(constant("SIZES"), "[104, 84, 66, 54]", "the live Pick Still keeps the four sizes");
eq(constant("TOP"), "{ 104: 250, 84: 235, 66: 225, 54: 220 }", "the live Pick Still keeps the first baseline for each size");
eq(after.split("(ARIAL[ch] || 1000)").length, 2, "an unlisted glyph counts as 1000, in the one width function");
// The 1.2 em pitch over-reads the 1.12 to 1.135 em GraphicsMagick draws, which
// is the safe side. Nothing Thumb: Plan can send reaches the height rule, so it
// is pinned here rather than by a headline.
eq(after.split("TOP[px] + lines.length * px * 1.2 > FLOOR_Y").length, 2, "the height rule reads a 1.2 em line pitch");
// The search starts no lower than the longest word plus one, and judges the
// lines at the lineLength it would return. A higher floor can leave no fitting
// wrap at any size, and judging at len + 1 can pass a line that is too wide.
eq(constant("minLen"), "Math.max(8, ...head.split(' ').map(w => w.length + 1))", "the search floor is the longest word plus one, and at least 8");
eq(after.split("const lines = wrapLines(head, len);").length, 2, "the search judges the lines at the lineLength it returns");

// ---- The width table against the font -------------------------------------------
// Liberation Sans is metric compatible with Arial. liberation_widths.py read these
// widths from the font file's cmap, hhea, head and hmtx tables, so this is a
// second source for the table rather than a copy of it.
eq(FONT.font, "LiberationSans-Regular.ttf", "the fixture names the font it was read from");
eq(FONT.unitsPerEm, 2048, "and its units per em");
eq(Object.keys(FONT.widths).sort(), Object.keys(ARIAL).sort(), "the fixture covers exactly the table's 92 glyphs");
for (const [ch, w] of Object.entries(ARIAL)) eq(w, FONT.widths[ch], JSON.stringify(ch) + " is " + FONT.widths[ch] + " thousandths in Liberation Sans");

// ---- The node's wrap against n8n's -------------------------------------------------
// The search in the live Pick Still predicts Compose's lines with its own wrapLines. If that
// copy drifts from n8n's loop, the size it picks no longer matches what Compose
// draws, so the two are compared line for line on every headline below.
const wrapLines = new Function(after.match(/\nconst wrapLines = \(text, len\) => \{[\s\S]*?\n\};/)[0] + "\nreturn wrapLines;")();
const sameWrap = (headline) => {
  for (let len = 1; len <= 45; len++) eq(wrapLines(headline, len), n8nWrap(headline, len), headline + ": the node's wrap at " + len + " is n8n's");
};

// ---- The width table against the one line measured on the instance ------------
// Execution 4737: "DASHBOARD FIRST" at 84 px, drawn from x 72, showed ink from
// x 79 to x 866, 787 px. An advance width also holds the two side bearings, so
// the table may read a little wider than the ink, never narrower.
const measured = 866 - 79;
const modelled = width("DASHBOARD FIRST", 84);
ok(modelled >= measured && modelled - measured <= 15, "Arial widths reproduce the measured line: " + modelled.toFixed(1) + " px against " + measured + " px of ink");
ok(TEXT_X + BUDGET < PANEL_RIGHT, "the text budget ends inside the panel");

// ---- The panel colour ------------------------------------------------------------
for (const show of ["TQO", "NCO", "ACX", "TSWS", "SOMETHING ELSE"]) {
  const out = run({ airtableId: "x", headline: "A HEADLINE", kicker: "K", show });
  ok(/^#[0-9A-F]{6}26$/.test(out.scrimColor), show + ": the panel colour ends 26, 85 percent opaque in GraphicsMagick terms");
}
eq(Math.round((1 - 0x26 / 255) * 1000) / 1000, 0.851, "26 is 15 percent transparent");

// ---- The layout, on the four proven headlines -----------------------------------
const PROVEN = {
  "READ THE DASHBOARD FIRST": { size: 84, lines: ["READ THE", "DASHBOARD", "FIRST"] },
  "THE QUIET WIN": { size: 104, lines: ["THE QUIET", "WIN"] },
  "WHO MOVES WHEN WORK MOVES": { size: 66, lines: ["WHO MOVES WHEN", "WORK MOVES"] },
  "OVERWHELMINGLY HUMAN": { size: 66, lines: ["OVERWHELMINGLY", "HUMAN"] },
};
for (const [headline, want] of Object.entries(PROVEN)) {
  const out = run({ airtableId: "x", headline, kicker: "K", isNCO: headline.startsWith("OVER") });
  eq(out.headSize, want.size, headline + ": the size executions 4764 to 4767 drew");
  eq(n8nWrap(headline, out.headWrap), want.lines, headline + ": the lines Compose draws");
  eq(out.headY, TOP[out.headSize], headline + ": headY follows the size");
}

// ---- The layout, on 600 generated headlines --------------------------------------
const WORDS = ["THE", "A", "AI", "WHY", "HOW", "QUIET", "OPERATOR", "WORK", "MOVES", "WHEN", "WHO", "MIDDLE", "TARGET",
  "DASHBOARD", "FIRST", "READ", "STOP", "HIRING", "MANAGERS", "NOW", "AUTOMATION", "WAVE", "CAREER", "MISS", "WORKERS",
  "OVERWHELMINGLY", "HUMAN", "MEMO", "I", "WWW", "MMM", "LIST", "YOUR", "JOB", "IS", "NOT", "SAFE", "2026", "$40K",
  "ISN’T", "DON'T", "FOUR", "STEPS", "TO", "KEEP", "SEAT", "ACCOUNTABILITY", "LEADERSHIP"];
let seed = 20261027;
const next = () => (seed = (seed * 1103515245 + 12345) % 2147483648);
// Returns true when every word fits the budget at the smallest size, which is
// when the width and height checks apply.
const checkHeadline = (input, isNCO) => {
  const out = run({ airtableId: "x", headline: input, kicker: "K", isNCO });
  // Compose draws the headline Pick Still returns, so that is what is wrapped.
  const headline = out.headline;
  eq(headline, input.trim(), JSON.stringify(input) + ": Pick Still returns the headline trimmed");
  const words = headline.split(" ");
  ok([104, 84, 66, 54].includes(out.headSize), headline + ": a size from the scale");
  eq(out.headY, TOP[out.headSize], headline + ": headY follows the size");
  sameWrap(headline);
  const lines = n8nWrap(headline, out.headWrap);
  ok(lines[0] !== "", headline + ": Compose does not start on an empty line");
  ok(lines.every((l) => l !== ""), headline + ": and draws no empty line anywhere");
  const longest = Math.max(...words.map((w) => width(w, 54)));
  if (longest > BUDGET) return false;
  ok(lines.every((l) => width(l, out.headSize) <= BUDGET), headline + ": every line inside the budget at " + out.headSize + " px");
  ok(TOP[out.headSize] + lines.length * out.headSize * 1.2 <= 680, headline + ": the block ends above y 680");
  // The fewest lines for that size: one more character on the line would break the budget or the height.
  const looser = n8nWrap(headline, out.headWrap + 1);
  if (looser.length < lines.length) {
    ok(looser.some((l) => width(l, out.headSize) > BUDGET) || TOP[out.headSize] + looser.length * out.headSize * 1.2 > 680,
      headline + ": the wrap is the longest that fits");
  }
  return true;
};
let fitted = 0;
for (let i = 0; i < 600; i++) {
  const count = 1 + (next() % 8);
  const headline = Array.from({ length: count }, () => WORDS[next() % WORDS.length]).join(" ");
  if (checkHeadline(headline, i % 2 === 0)) fitted++;
}
ok(fitted >= 550, "almost every generated headline fits: " + fitted + " of 600");

// ---- The layout, on headlines the generated set never reaches -----------------------
// Each one was found by the 2026-10-27 critic as the input that tells a correct
// node from a drifted one the generated set let through.
const CRAFTED = {
  // At 104 px this one word is 693 px, inside the panel edge but past the budget,
  // so a budget raised to 760 would keep the largest size and run past the panel.
  "AUTOMATION": "the budget",
  // Seven wide words fit the width at 66 px but not the height, so only the
  // height rule steps this one down to 54 px.
  "MMMMMMMMM MMMMMMMMM MMMMMMMMM MMMMMMMMM MMMMMMMMM MMMMMMMMM MMMMMMMMM": "the height rule",
  // The longest word comes first, so a search allowed below it would pick a
  // lineLength that makes Compose start on an empty line.
  "ACCOUNTABILITY WWWW WWWW WORK QUIET WWW IIII": "the search bound",
  // W is the widest capital in the table.
  "WWWW DON'T": "the width of W",
  // An unlisted glyph counts as a full em, so nine of them step the size down.
  "ÉÉÉÉÉÉÉÉÉ": "an unlisted glyph",
  // At 84 px the line "THE MEMO MISS" is 681.4 px, so a budget loosened by even
  // 2 px, or widths scaled down by half a percent, draws it past the budget.
  "THE MEMO MISS TO": "the budget to the pixel",
  // The only wrap that fits is the longest word plus one, and that word comes
  // first, so a wrap one shorter than the search's answer starts on an empty line.
  "ACCOUNTABILITY WORKERS MANAGER": "the wrap the search returns",
  // Thumb: Plan turns a dash at either end of its text into a space, so Pick
  // Still can receive this. Untrimmed, Compose would start on an empty line.
  " ACCOUNTABILITY WORKERS MANAGER ": "the trim",
  // With the search floor raised by four, no wrap fits at any size and this one
  // falls back to a 696 px line at 54 px.
  "WORKFORCE MOMENTUM TRANSFORMATION JOB": "the search floor",
};
for (const [headline, what] of Object.entries(CRAFTED)) {
  ok(checkHeadline(headline, false), headline + ": every word fits the budget at 54 px, so the checks for " + what + " apply");
}

// ---- A word too wide for any size --------------------------------------------------
const huge = run({ airtableId: "x", headline: "M".repeat(28), kicker: "K" });
eq(huge.headSize, 54, "a word too wide for every size falls to the smallest");
eq(n8nWrap("M".repeat(28), huge.headWrap), ["M".repeat(28)], "and still draws on one line, with no empty line first");

// ---- The Jev block is untouched -----------------------------------------------------
eq([...after.matchAll(/const JEV_APPLY = (\w+);/g)].map((m) => m[1]), ["false"], "JEV_APPLY stays false");

// ---- No dash in this folder ---------------------------------------------------------
const DASH = new RegExp("[" + String.fromCharCode(0x2013, 0x2014) + "]");
for (const f of ["./manifest.json", "../thumb_pick_still.js"]) ok(!DASH.test(read(f)), f + " carries no em or en dash");

console.log("Thumb layout: the panel is 85 percent opaque and every line fits inside it, " + checks + " checks");
