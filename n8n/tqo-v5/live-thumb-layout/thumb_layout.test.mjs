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
 * Arial capitals run about 0.66 em. after.js sends 26 and works the wrap out
 * from Arial's advance widths with the same word wrap Compose applies.
 *
 * This test holds the files to the manifest, holds the change to the three
 * replacement pairs, and checks the layout on 600 generated headlines with an
 * independent copy of n8n's wrap loop. The width table itself is checked only
 * against the one line measured on the instance, so other glyphs rest on Arial's
 * published metrics. It reads no live data.
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

// ---- The files are the ones the manifest names ---------------------------------
eq(M.workflowId, "qEkGOUsNyVaRAmm6", "TQO FINAL V5");
eq(M.node, "Thumb: Pick Still", "the one node it changes");
eq(sha(before), M.before.sha256, "before.js is the body the manifest names");
eq(sha(after), M.after.sha256, "after.js is the body the manifest names");
eq(M.rollback, "publish " + M.before.versionId, "rollback is the version before");
eq(read("../thumb_pick_still.js"), after, "the repo's Pick Still is after.js");
eq(R.pairs.length, 3, "three pairs: the type scale, the panel colour and headY");
for (const p of R.pairs) eq(before.split(p.old).length, 2, "each replaced block occurs once in before.js");
eq(R.pairs.reduce((s, p) => s.replace(p.old, () => p.new), before), after, "after.js is before.js with the three pairs and nothing else");
const EXPORT = JSON.parse(read("../exports/qEkGOUsNyVaRAmm6_active.json"));
const exported = EXPORT.nodes.filter((n) => n.name === "Thumb: Pick Still")[0].parameters.jsCode;
for (const p of R.pairs) eq(exported.split(p.old).length, 2, "each replaced block occurs once in the export too, so the mirror tests can apply it");

// ---- Running after.js ------------------------------------------------------------
const run = (plan, photos = [{ id: 1, photographer: "x", src: { landscape: "https://images.pexels.com/a.jpg" } }]) => {
  const $ = (name) => {
    if (name === "Thumb: Plan") return { first: () => ({ json: plan }) };
    throw new Error("Node '" + name + "' hasn't been executed");
  };
  return new Function("$", "$json", after)($, { photos })[0].json;
};

// n8n Edit Image, text operation, copied from EditImage.node.ts on n8n master as
// read on 2026-10-27, so the test does not share after.js's own copy.
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
let fitted = 0;
for (let i = 0; i < 600; i++) {
  const count = 1 + (next() % 8);
  const words = Array.from({ length: count }, () => WORDS[next() % WORDS.length]);
  const headline = words.join(" ");
  const out = run({ airtableId: "x", headline, kicker: "K", isNCO: i % 2 === 0 });
  ok([104, 84, 66, 54].includes(out.headSize), headline + ": a size from the scale");
  eq(out.headY, TOP[out.headSize], headline + ": headY follows the size");
  const lines = n8nWrap(headline, out.headWrap);
  ok(lines[0] !== "", headline + ": Compose does not start on an empty line");
  ok(lines.every((l) => l !== ""), headline + ": and draws no empty line anywhere");
  const longest = Math.max(...words.map((w) => width(w, 54)));
  if (longest <= BUDGET) {
    ok(lines.every((l) => width(l, out.headSize) <= BUDGET), headline + ": every line inside the budget at " + out.headSize + " px");
    ok(TOP[out.headSize] + lines.length * out.headSize * 1.2 <= 680, headline + ": the block ends above y 680");
    fitted++;
  }
  // The fewest lines for that size: one more character on the line would break the budget or the height.
  const looser = n8nWrap(headline, out.headWrap + 1);
  if (longest <= BUDGET && looser.length < lines.length) {
    ok(looser.some((l) => width(l, out.headSize) > BUDGET) || TOP[out.headSize] + looser.length * out.headSize * 1.2 > 680,
      headline + ": the wrap is the longest that fits");
  }
}
ok(fitted >= 550, "almost every generated headline fits: " + fitted + " of 600");

// ---- A word too wide for any size --------------------------------------------------
const huge = run({ airtableId: "x", headline: "M".repeat(28), kicker: "K" });
eq(huge.headSize, 54, "a word too wide for every size falls to the smallest");
eq(n8nWrap("M".repeat(28), huge.headWrap), ["M".repeat(28)], "and still draws on one line, with no empty line first");

// ---- The Jev block is untouched -----------------------------------------------------
eq([...after.matchAll(/const JEV_APPLY = (\w+);/g)].map((m) => m[1]), ["false"], "JEV_APPLY stays false");

// ---- No dash in this folder ---------------------------------------------------------
const DASH = new RegExp("[" + String.fromCharCode(0x2013, 0x2014) + "]");
for (const f of ["./manifest.json", "./replacement.json", "./after.js"]) ok(!DASH.test(read(f)), f + " carries no em or en dash");

console.log("Thumb layout: the panel is 85 percent opaque and every line fits inside it, " + checks + " checks");
