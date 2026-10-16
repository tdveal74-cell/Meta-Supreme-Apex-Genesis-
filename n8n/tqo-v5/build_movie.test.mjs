/**
 * Does Build Movie keep today's clip choice while Jev ships in shadow, and does
 * it report what Jev would choose instead?
 *
 *   node n8n/tqo-v5/build_movie.test.mjs
 *
 * build_movie.js is the Build Movie node as exported (version 9320520f of
 * TQO FINAL V5) plus the Jev shadow reader. The unmodified node is read straight
 * out of the export JSON here, never retyped, and run beside the new body on the
 * same stubs. With no Jev node run, the two must agree on everything but the
 * three keys the shadow adds. The Jev nodes are stubbed: nothing here touches a
 * network, and no TypeSafe key is funded yet, so these answers are written by
 * hand in the shape the API documents (a score answer carries `score` 0 to 3).
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const NEW_SRC = readFileSync(new URL("./build_movie.js", import.meta.url), "utf8");
const EXPORT = JSON.parse(readFileSync(new URL("./exports/qEkGOUsNyVaRAmm6_active.json", import.meta.url), "utf8"));
const ORIGINAL = EXPORT.nodes.find((n) => n.name === "Build Movie").parameters.jsCode;
assert.equal(typeof ORIGINAL, "string");
assert.ok(ORIGINAL.length > 5000, "the export must carry the Build Movie body");

// ---- stubs ------------------------------------------------------------------

const A = "https://videos.pexels.example/a.mp4";
const B = "https://videos.pexels.example/b.mp4";
const C = "https://videos.pexels.example/c.mp4";
const D = "https://videos.pexels.example/d.mp4";
const E = "https://videos.pexels.example/e.mp4";
const F = "https://videos.pexels.example/f.mp4";

const seg = (i, narration = "Sentence " + i + " of the script.") =>
  ({ json: { segIndex: i, start: i * 8, duration: 8, query: "q" + i, narration, uploadId: "upload1", videoTitle: "The Quiet Operator" } });

// A Pexels /videos/search response whose best file for each video is `links[n]`:
// a 4K file that is over the cap, the 1080p file the rule takes, and a small one.
const pex = (...links) => ({ json: { videos: links.map((link, n) => ({
  id: 1000 + n,
  image: "https://images.pexels.com/videos/" + (1000 + n) + "/pictures/preview-0.jpeg",
  video_files: [
    { file_type: "video/mp4", width: 4096, link: link + "?uhd" },
    { file_type: "video/mp4", width: 1920, link },
    { file_type: "video/mp4", width: 640, link: link + "?sd" },
    { file_type: "video/webm", width: 1920, link: link + "?webm" },
  ],
})) } });

const ROW = { rowId: "46", videoTitle: "The Middle Is the Target" };

// n8n's `$('X')` throws when node X did not run, so the stub does too.
const stubs = ({ segs, px, jevNodes = {} }) => (name) => {
  if (name === "Plan B-Roll Segments") return { all: () => segs, first: () => segs[0] };
  if (name === "Pexels Search") return { all: () => px, first: () => px[0] };
  if (name === "Presenter: Attach Clips") return { all: () => [{ json: ROW }], first: () => ({ json: ROW }) };
  if (Object.hasOwn(jevNodes, name)) {
    const v = jevNodes[name];
    return { all: () => { if (v instanceof Error) throw v; return v; }, first: () => v[0] };
  }
  throw new Error("Node '" + name + "' hasn't been executed");
};

const compile = (code) => new Function("$", "$json", code);
const run = (code, fx, json = { presenterClips: [] }) => compile(code)(stubs(fx), json)[0].json;
const runNew = (fx, opts = {}) => run(opts.apply ? NEW_SRC.replace("const JEV_APPLY = false;", "const JEV_APPLY = true;") : NEW_SRC, fx, opts.json);
const runOld = (fx, json) => run(ORIGINAL, fx, json);
const strip = ({ jevRanked, jevWouldChange, jevApplied, ...rest }) => rest;
const srcs = (out) => out.j2vBody.scenes[0].elements.filter((e) => e.type === "video").map((e) => e.src);

// The Jev nodes as they would hand data over. One entry per question asked:
// `q(link, k, score)` is candidate k of the segment, its link, and the score the
// response carries for it (undefined: asked, but no answer came back).
const q = (link, k, score) => ({ link, k, score });
const jevNodes = (plans, opts = {}) => {
  const model = "model" in opts ? opts.model : "jev-1.14";
  const mutate = opts.mutate || ((a) => a);
  const bodies = [], ranks = [];
  plans.forEach((entries, i) => {
    if (!entries) return;
    const questions = {}, answers = {};
    for (const e of entries) {
      const name = "s" + i + "c" + e.k;
      questions[name] = { type: "score", instructions: "How well does <" + name + "> work?", criteria: ["0", "1", "2", "3"] };
      if (e.score !== undefined) answers[name] = { type: "score", score: e.score, confidence: 0.9, legend: {}, probabilities: {} };
    }
    bodies.push({ json: { segIndex: i, links: entries.map((e) => e.link), body: { model: "jev-latest", state: { sentence: "x" }, questions, assets: {} } } });
    ranks.push({ json: mutate({ model, answers, usage: {} }) });
  });
  return { "Jev: B-Roll Bodies": bodies, "Jev: Rank B-Roll": ranks };
};

// ---- the edit is as small as it claims to be ---------------------------------

// The whole difference between the export's Build Movie and build_movie.js is
// pinned, not only what is missing from it. This check used to ask which export
// lines were gone and nothing else, so a line ADDED outside the Jev code passed:
// a verifier added `if (segs.length > 40) throw` and every test stayed green.
// Now the line diff is computed here and its hunks are listed below, each with its
// kind and its line range on both sides, the text of every line it removes, and
// the code of every line it adds.
//
// A CHANGE TO THE JEV CODE MEANS UPDATING THESE LISTS, ON PURPOSE. Adding,
// removing or moving a line in build_movie.js shifts a range below and turns this
// check red, and that is meant: whoever made the edit reads the hunks and says
// again, in this file, that every line added is Jev's. Do not loosen the check to
// let an edit through. A new live version of Build Movie turns it red too, and
// the fix there is to bring the mirror up to date first.
//
// The diff is a longest common subsequence walk, so a blank line cannot stand in
// for a missing one. Ranges count lines from 1. For an add, `inExport` is
// [n, n] with n the export line the new lines follow (as in diff's `105a106,184`).
const lineDiff = (a, b) => {
  const lcs = Array.from({ length: a.length + 1 }, () => new Array(b.length + 1).fill(0));
  for (let i = a.length - 1; i >= 0; i--) for (let j = b.length - 1; j >= 0; j--)
    lcs[i][j] = a[i] === b[j] ? lcs[i + 1][j + 1] + 1 : Math.max(lcs[i + 1][j], lcs[i][j + 1]);
  const hunks = [];
  let open = null;
  const close = () => { if (open) hunks.push(open); open = null; };
  for (let i = 0, j = 0; i < a.length || j < b.length;) {
    if (i < a.length && j < b.length && a[i] === b[j]) { close(); i++; j++; continue; }
    open ??= { i, j, removed: [], added: [] };
    if (j < b.length && (i === a.length || lcs[i][j + 1] >= lcs[i + 1][j])) open.added.push(b[j++]);
    else open.removed.push(a[i++]);
  }
  close();
  return hunks.map((h) => ({
    kind: !h.removed.length ? "add" : !h.added.length ? "delete" : "change",
    inExport: h.removed.length ? [h.i + 1, h.i + h.removed.length] : [h.i, h.i],
    inFile: h.added.length ? [h.j + 1, h.j + h.added.length] : [h.j, h.j],
    removed: h.removed,
    added: h.added,
  }));
};
const oldLines = ORIGINAL.split("\n");
const newLines = NEW_SRC.replace(/\n$/, "").split("\n");
const hunks = lineDiff(oldLines, newLines);

assert.deepEqual(hunks.map(({ kind, inExport, inFile }) => ({ kind, inExport, inFile })), [
  { kind: "add", inExport: [105, 105], inFile: [106, 184] },     // the Jev block, and the blank line after it
  { kind: "add", inExport: [106, 106], inFile: [186, 186] },     // the two Jev counters
  { kind: "add", inExport: [109, 109], inFile: [190, 190] },     // the call that reads Jev's scores
  { kind: "add", inExport: [110, 110], inFile: [192, 199] },     // the selection rule, as a function
  { kind: "change", inExport: [118, 122], inFile: [207, 219] },  // the rule's call site: two picks, one used
  { kind: "change", inExport: [234, 234], inFile: [331, 332] },  // the return, with the Jev keys appended
], "the diff against the export is not the one listed here; read the note above before editing this list");

// Every line the export has and build_movie.js does not: the five lines of the
// selection rule that moved into a function, and the last line of the return.
assert.deepEqual(hunks.flatMap((h) => h.removed), [
  "  let src = cands.find(c => !usedAll.has(c))",
  "         || cands.find(c => !recent.includes(c))",
  "         || cands.find(c => c !== lastSrc)",
  "         || cands[0]",
  "         || null;",
  "                  leadPad: LEAD_PAD, runtimeSec: Math.round(bodyEnd), srt, rowId: ROW.rowId, videoTitle: TITLE } }];",
]);

// Every line build_movie.js adds belongs to the Jev code. The first hunk is the
// Jev block: the header comment through the end of jevOrder, then a blank line.
// Outside functions its only code is the two constants and the two functions, so
// a statement of any other kind dropped between them shows here.
const [block, ...glue] = hunks.map((h) => h.added);
assert.match(block[0], /^\/\/ JEV SHADOW/);
assert.deepEqual(block.slice(-2), ["}", ""]);
assert.deepEqual(block.filter((l) => l.trim() && !l.startsWith("//") && !l.startsWith(" ")),
  ["const JEV_APPLY = false;", "const JEV_FLOOR = 2;", "function readJev() {", "}", "function jevOrder(list, scores) {", "}"]);
// The other five hunks are glue. Their comment and blank lines carry no code. Their
// code is exactly this, in this order: the counters, the reader call, the
// selection rule (the export's own, moved so that it runs over two orders), the
// two picks with the flag choosing between them, and the three keys returned.
const GLUE_CODE = [
  "let jevRanked = 0, jevWouldChange = 0;",
  "const jev = readJev();",
  "const pickFrom = (list) => list.find(c => !usedAll.has(c))",
  "                        || list.find(c => !recent.includes(c))",
  "                        || list.find(c => c !== lastSrc)",
  "                        || list[0]",
  "                        || null;",
  "  const scores = jev.get(i);",
  "  const todayPick = pickFrom(cands);",
  "  const jevPick = pickFrom(jevOrder(cands, scores));",
  "  if (scores && cands.some(c => scores.has(c))) jevRanked++;",
  "  if (jevPick !== todayPick) jevWouldChange++;",
  "  let src = JEV_APPLY ? jevPick : todayPick;",
  "                  leadPad: LEAD_PAD, runtimeSec: Math.round(bodyEnd), srt, rowId: ROW.rowId, videoTitle: TITLE,",
  "                  jevRanked, jevWouldChange, jevApplied: JEV_APPLY } }];",
];
assert.deepEqual(glue.flat().filter((l) => l.trim() && !/^\s*\/\//.test(l)), GLUE_CODE);

// It ships in shadow, and it follows the house writing rules (no em or en dash).
assert.equal(NEW_SRC.match(/^const JEV_APPLY = false;$/gm).length, 1);
assert.equal(NEW_SRC.match(/^const JEV_FLOOR = 2;$/gm).length, 1);
const DASHES = new RegExp("[" + String.fromCharCode(0x2013, 0x2014) + "]");
assert.doesNotMatch(NEW_SRC, DASHES);
assert.doesNotMatch(readFileSync(new URL(import.meta.url), "utf8"), DASHES);

// ---- no Jev node ran: the output is the export's output ----------------------

const PLAIN = {
  segs: [0, 1, 2, 3, 4, 5].map((i) => seg(i)),
  px: [pex(A, B, C), pex(A, B), pex(A), pex(), pex(D, A)],       // segment 5 has no Pexels item at all
};
const oldOut = runOld(PLAIN);
assert.equal(oldOut.heldClips, 2, "the fixture must exercise the hold path");
assert.equal(oldOut.clipCount, 6);
assert.deepEqual(srcs(oldOut), [A, B, A, A, D, D]);

const noJev = runNew(PLAIN);
assert.deepEqual(strip(noJev), oldOut);
assert.deepEqual(Object.keys(noJev).filter((k) => !(k in oldOut)).sort(), ["jevApplied", "jevRanked", "jevWouldChange"]);
assert.equal(noJev.jevRanked, 0);
assert.equal(noJev.jevWouldChange, 0);
assert.equal(noJev.jevApplied, false);
// The flag on changes nothing when there is nothing to read.
assert.deepEqual(strip(runNew(PLAIN, { apply: true })), oldOut);
assert.equal(runNew(PLAIN, { apply: true }).jevApplied, true);

// Nothing at all for the opening segment is skipped, not held (the `continue`).
const NO_OPENER = { segs: [seg(0), seg(1), seg(2)], px: [pex(), pex(B, C), pex(B)] };
assert.deepEqual(strip(runNew(NO_OPENER)), runOld(NO_OPENER));
assert.equal(runOld(NO_OPENER).clipCount, 2);

// One Jev node missing, or both throwing for another reason, is still no data.
const full = jevNodes([[q(A, 1, 0), q(B, 2, 3), q(C, 3, 2)]]);
for (const only of [{ "Jev: B-Roll Bodies": full["Jev: B-Roll Bodies"] }, { "Jev: Rank B-Roll": full["Jev: Rank B-Roll"] },
  { "Jev: B-Roll Bodies": new Error("boom"), "Jev: Rank B-Roll": new Error("boom") }]) {
  for (const apply of [false, true]) {
    const out = runNew({ ...PLAIN, jevNodes: only }, { apply });
    assert.deepEqual(strip(out), oldOut);
    assert.equal(out.jevRanked, 0);
    assert.equal(out.jevWouldChange, 0);
  }
}

// The refusals the node already had still fire with the same message.
const unverified = { presenterClips: [{ segmentIndex: 2, file: "p.mp4", publicUrl: "https://x/y", shareVerified: false, start: 0, duration: 4 }] };
const refusal = (code) => { try { run(code, PLAIN, unverified); } catch (e) { return e.message; } return null; };
assert.match(refusal(ORIGINAL), /^PRESENTER REFUSAL/);
assert.equal(refusal(NEW_SRC), refusal(ORIGINAL));

// ---- the two middle tiers of the selection rule, against the export -----------

// pickFrom is the export's rule moved into a function: the first clip not used
// anywhere in the episode, else the first not among the last three, else the
// first that is not the previous source, else the first. No case above needs
// either middle tier to get its answer, so deleting either one left this file
// green. Each fixture below runs with no Jev node, is compared with the export's
// own output the way PLAIN is, and pins the clips it expects. The pins prove the
// two outputs agree; the scratch mutation runs that delete each tier are what
// proved these fixtures reach it, so an edit to a fixture here should repeat
// them.
const sameAsExport = (fx, expected, label) => {
  assert.deepEqual(srcs(runOld(fx)), expected, label + ": the export's own picks");
  for (const apply of [false, true]) {
    const out = runNew(fx, { apply });
    assert.deepEqual(srcs(out), expected, label);
    assert.deepEqual(strip(out), runOld(fx), label);
    assert.equal(out.jevRanked, 0, label);
    assert.equal(out.jevWouldChange, 0, label);
  }
};

// Not-recent tier. Segments 0 to 3 take A, B, C, D, so the memory of the last
// three is [B, C, D]. Segment 4 offers [B, A]: both were used, B is recent and A
// is not, so A. Without the tier, the not-the-previous-source tier would give B.
// Memory is then [C, D, A]. Segment 5 offers [D, C, B]: all used, D and C are
// recent and B is not, so B. Without the tier it would give D.
sameAsExport({ segs: [0, 1, 2, 3, 4, 5].map((i) => seg(i)), px: [pex(A), pex(B), pex(C), pex(D), pex(B, A), pex(D, C, B)] },
  [A, B, C, D, A, B], "not-recent tier");

// Not-the-previous-source tier. Segments 0 to 2 take A, B, C, so the memory is
// [A, B, C] and the previous source is C. Segment 3 offers [C, B]: both were
// used and both are recent, so only the previous-source test is left, and it
// passes over C for B. Without the tier the first clip, C, would play twice in a
// row, which is the repeat this tier exists to stop.
sameAsExport({ segs: [0, 1, 2, 3].map((i) => seg(i)), px: [pex(A), pex(B), pex(C), pex(C, B)] },
  [A, B, C, B], "not-the-previous-source tier");

// ---- scored cases, shadow on (JEV_APPLY false): today's clips, Jev reported --

const ONE = { segs: [seg(0)], px: [pex(A, B, C)] };
const oneOld = runOld(ONE);
assert.deepEqual(srcs(oneOld), [A]);

// Reorder: Jev likes B best, then C, then A. Today's pick stays A.
let fx = { ...ONE, jevNodes: jevNodes([[q(A, 1, 1.5), q(B, 2, 2.8), q(C, 3, 2.0)]]) };
let out = runNew(fx);
assert.deepEqual(strip(out), oneOld, "shadow must not change the render body or any other key");
assert.equal(out.jevRanked, 1);
assert.equal(out.jevWouldChange, 1);
assert.equal(out.jevApplied, false);
// Apply on: the same clip order drives the existing rule, so the pick is B.
out = runNew(fx, { apply: true });
assert.deepEqual(srcs(out), [B]);
assert.equal(out.jevApplied, true);
assert.equal(out.jevRanked, 1);
assert.equal(out.jevWouldChange, 1);
assert.equal(out.clipCount, 1);

// Jev agrees with Pexels order: ranked, not changed, even with the flag on.
fx = { ...ONE, jevNodes: jevNodes([[q(A, 1, 3), q(B, 2, 2), q(C, 3, 1)]]) };
for (const apply of [false, true]) {
  out = runNew(fx, { apply });
  assert.equal(out.jevRanked, 1);
  assert.equal(out.jevWouldChange, 0);
  assert.deepEqual(srcs(out), [A]);
}

// The floor. JEV_FLOOR is 2, level 2 of the rubric, "fits". A clip scored 2 or
// more goes first, best first. A clip Jev did not score keeps its Pexels place
// behind those. A clip scored under 2 goes last, best first. A Jev score is a mean
// of the level numbers, so 1.999 is a clip that does not quite fit, and a clip
// that is certainly level 1, clean but about something else, scores exactly 1.
// The boundary is pinned on both sides. `vs(a, b)` is clips A then B in Pexels
// order with the scores given (undefined: asked about, not answered).
const vs = (scoreA, scoreB) => ({ segs: [seg(0)], px: [pex(A, B)], jevNodes: jevNodes([[q(A, 1, scoreA), q(B, 2, scoreB)]]) });
const picked = (fx) => srcs(runNew(fx, { apply: true }));
// A later clip jumps an unscored first clip only from exactly 2 up.
assert.deepEqual(picked(vs(undefined, 2)), [B], "2 is in front of a clip nobody scored");
assert.deepEqual(picked(vs(undefined, 3)), [B]);
assert.deepEqual(picked(vs(undefined, 1.999)), [A], "1.999 is behind a clip nobody scored");
assert.deepEqual(picked(vs(undefined, 1)), [A], "1 was in front under the old floor and is behind now");
// A scored first clip is pushed behind an unscored one only under 2.
assert.deepEqual(picked(vs(2, undefined)), [A]);
assert.deepEqual(picked(vs(1.999, undefined)), [B]);
assert.deepEqual(picked(vs(1, undefined)), [B]);
assert.deepEqual(picked(vs(0, undefined)), [B]);
// Whichever side of the line, shadow keeps today's clip and still reports the segment ranked.
for (const [a, b] of [[undefined, 2], [undefined, 1.999], [2, undefined], [1.999, undefined], [1, undefined]]) {
  out = runNew(vs(a, b));
  assert.deepEqual(srcs(out), [A], a + "/" + b);
  assert.equal(out.jevRanked, 1, a + "/" + b);
}
assert.equal(runNew(vs(undefined, 2)).jevWouldChange, 1);
assert.equal(runNew(vs(undefined, 1.999)).jevWouldChange, 0);
assert.equal(runNew(vs(2, undefined)).jevWouldChange, 0);
assert.equal(runNew(vs(1.999, undefined)).jevWouldChange, 1);
// Both scored, either side: a score at the floor beats one just under it, in either Pexels order.
assert.deepEqual(picked(vs(1.999, 2)), [B]);
assert.deepEqual(picked(vs(2, 1.999)), [A]);
// All three tiers in one order. A is 1.999 (low), B is not scored, C is exactly 2.
// Three segments with the same candidates walk it one clip at a time: C, B, A.
fx = { segs: [seg(0), seg(1), seg(2)], px: [pex(A, B, C), pex(A, B, C), pex(A, B, C)],
  jevNodes: jevNodes([0, 1, 2].map(() => [q(A, 1, 1.999), q(B, 2, undefined), q(C, 3, 2)])) };
assert.deepEqual(srcs(runNew(fx)), [A, B, C]);
assert.deepEqual(picked(fx), [C, B, A]);
assert.equal(runNew(fx).jevRanked, 3);
// Score 0 never leads: A is 0, B is not scored, so B goes first.
fx = { segs: [seg(0)], px: [pex(A, B)], jevNodes: jevNodes([[q(A, 1, 0), q(B, 2, undefined)]]) };
assert.deepEqual(srcs(runNew(fx, { apply: true })), [B]);
assert.equal(runNew(fx).jevWouldChange, 1);
// Several low scores order by score, best first, so 0.5 leads 0.
fx = { segs: [seg(0), seg(1), seg(2)], px: [pex(A, B), pex(A, B), pex(A, B)],
  jevNodes: jevNodes([[q(A, 1, 0), q(B, 2, 0.5)], [q(A, 1, 0), q(B, 2, 0.5)], [q(A, 1, 0), q(B, 2, 0.5)]]) };
assert.deepEqual(srcs(runNew(fx, { apply: true })), [B, A, B]);
assert.deepEqual(srcs(runOld(fx)), [A, B, A]);
// Nothing is ever dropped: every clip is scored 0 and the segment still gets one.
fx = { segs: [seg(0), seg(1)], px: [pex(A), pex(A)], jevNodes: jevNodes([[q(A, 1, 0)], [q(A, 1, 0)]]) };
out = runNew(fx, { apply: true });
assert.deepEqual(srcs(out), [A, A]);
assert.equal(out.heldClips, 0);
assert.equal(out.clipCount, 2);
assert.deepEqual(strip(out), runOld(fx));

// Ties keep Pexels order. B and C tie at 2, A scores 1 and is under the floor, so
// it is last. Three segments with the same candidates walk the order one clip at
// a time: B, then C, then A.
const same = [q(A, 1, 1), q(B, 2, 2), q(C, 3, 2)];
fx = { segs: [seg(0), seg(1), seg(2)], px: [pex(A, B, C), pex(A, B, C), pex(A, B, C)], jevNodes: jevNodes([same, same, same]) };
assert.deepEqual(srcs(runNew(fx, { apply: true })), [B, C, A]);
assert.deepEqual(srcs(runNew(fx)), [A, B, C]);
assert.equal(runNew(fx).jevRanked, 3);
// In shadow the memory follows today's picks (A, B, C), so Jev differs only on
// the first segment: B against A. Once applied it follows Jev's own picks, and
// differs from Pexels order on the first two segments (B for A, C for A).
assert.equal(runNew(fx).jevWouldChange, 1);
assert.equal(runNew(fx, { apply: true }).jevWouldChange, 2);
// Equal scores everywhere is Pexels order, so nothing would change.
const flat = [q(A, 1, 2), q(B, 2, 2), q(C, 3, 2)];
fx = { segs: [seg(0), seg(1), seg(2)], px: [pex(A, B, C), pex(A, B, C), pex(A, B, C)], jevNodes: jevNodes([flat, flat, flat]) };
assert.equal(runNew(fx).jevWouldChange, 0);
assert.equal(runNew(fx).jevRanked, 3);
assert.deepEqual(srcs(runNew(fx, { apply: true })), srcs(runOld(fx)));

// jevWouldChange is an estimate for the ruling, not a forecast (the note beside the
// count in build_movie.js says so). In shadow it is worked out against today's
// memory of the clips used, and once the flag is on that memory holds Jev's clips
// instead, so the number of clips that really change can be higher or lower than
// it. `moved` counts the clips that differ between the shadow run and the applied
// run. Higher: Jev takes B for segment 0, which leaves A free for segment 1, where
// today's rule had to take B. The estimate is 1 and 2 clips move.
const moved = (fx) => { const s = srcs(runNew(fx)), a = srcs(runNew(fx, { apply: true })); return s.filter((x, n) => x !== a[n]).length; };
fx = { segs: [seg(0), seg(1)], px: [pex(A, B), pex(A, B)], jevNodes: jevNodes([[q(A, 1, 1), q(B, 2, 3)], null]) };
assert.deepEqual(srcs(runNew(fx)), [A, B]);
assert.deepEqual(picked(fx), [B, A]);
assert.equal(runNew(fx).jevWouldChange, 1);
assert.equal(moved(fx), 2);
// Lower: Jev takes A for segment 0, and in segment 1 it ranks A first again. In
// shadow A is not yet used there, so Jev's pick differs from today's B. Once
// applied A is used by then, Jev falls through to B, and it is today's clip. The
// estimate is 2 and 1 clip moves.
fx = { segs: [seg(0), seg(1)], px: [pex(C, B, A), pex(B, A)],
  jevNodes: jevNodes([[q(C, 1, 1.5), q(B, 2, 0), q(A, 3, 2)], [q(B, 1, 1.5), q(A, 2, 2)]]) };
assert.deepEqual(srcs(runNew(fx)), [C, B]);
assert.deepEqual(picked(fx), [A, B]);
assert.equal(runNew(fx).jevWouldChange, 2);
assert.equal(moved(fx), 1);

// Scores 0 and 3 are in range. A single scored candidate is still a ranked segment.
fx = { segs: [seg(0)], px: [pex(A, B)], jevNodes: jevNodes([[q(A, 1, 0), q(B, 2, 3)]]) };
assert.equal(runNew(fx).jevRanked, 1);
assert.deepEqual(srcs(runNew(fx, { apply: true })), [B]);

// The memory is shared: a Jev pick that is already used falls through the same
// rule. Segment 1 prefers A, but A was just used, so it takes the next unused.
fx = { segs: [seg(0), seg(1)], px: [pex(A, B), pex(A, B, C)], jevNodes: jevNodes([[q(A, 1, 3), q(B, 2, 1)], [q(A, 1, 3), q(B, 2, 2), q(C, 3, 1)]]) };
assert.deepEqual(srcs(runNew(fx, { apply: true })), [A, B]);

// Only some segments carry scores: the rest follow Pexels order and are not counted.
fx = { segs: [seg(0), seg(1), seg(2)], px: [pex(A, B), pex(C, D), pex(A, B, D)], jevNodes: jevNodes([[q(A, 1, 0), q(B, 2, 3)], null, [q(B, 2, 3)]]) };
out = runNew(fx);
assert.equal(out.jevRanked, 2);
assert.deepEqual(strip(out), runOld(fx));

// ---- the link pairing: the bodies node leaves out stills it could not use ----

// A had no usable still, so the bodies node asked only about c2 and c3 and sent
// links [B, C]. Reading links[k-1] would score B as C. B is 0.5, C is 2.5.
fx = { ...ONE, jevNodes: jevNodes([[q(B, 2, 0.5), q(C, 3, 2.5)]]) };
assert.deepEqual(srcs(runNew(fx, { apply: true })), [C]);
assert.equal(runNew(fx).jevWouldChange, 1);
// Swap the scores and B leads instead.
fx = { ...ONE, jevNodes: jevNodes([[q(B, 2, 2.5), q(C, 3, 0.5)]]) };
assert.deepEqual(srcs(runNew(fx, { apply: true })), [B]);
// Links and questions that do not line up are trusted for nothing.
fx = { ...ONE, jevNodes: jevNodes([[q(A, 1, 0), q(B, 2, 3)]]) };
fx.jevNodes["Jev: B-Roll Bodies"][0].json.links = [A];
for (const apply of [false, true]) {
  out = runNew(fx, { apply });
  assert.equal(out.jevRanked, 0);
  assert.deepEqual(strip(out), oneOld);
}
// A bodies item with no body at all falls back to links[k-1] by name.
fx = { ...ONE, jevNodes: jevNodes([[q(A, 1, 0), q(B, 2, 3)]]) };
delete fx.jevNodes["Jev: B-Roll Bodies"][0].json.body;
assert.deepEqual(srcs(runNew(fx, { apply: true })), [B]);

// ---- answers that must be ignored --------------------------------------------

// The control: B scored 3 moves B to the front.
const control = { ...ONE, jevNodes: jevNodes([[q(A, 1, 1), q(B, 2, 3)]]) };
assert.deepEqual(srcs(runNew(control, { apply: true })), [B]);

// A response from another model, an error item, or no model at all is ignored.
for (const model of ["gpt-5", "jev", "Jev-1.14", "", undefined, null, 14, { name: "jev-1.14" }]) {
  fx = { ...ONE, jevNodes: jevNodes([[q(A, 1, 1), q(B, 2, 3)]], { model }) };
  for (const apply of [false, true]) {
    out = runNew(fx, { apply });
    assert.equal(out.jevRanked, 0, String(model));
    assert.deepEqual(strip(out), oneOld, String(model));
  }
}
fx = { ...ONE, jevNodes: { ...control.jevNodes, "Jev: Rank B-Roll": [{ json: { error: { message: "402 Payment Required" } } }] } };
assert.deepEqual(strip(runNew(fx, { apply: true })), oneOld);
assert.equal(runNew(fx, { apply: true }).jevRanked, 0);

// A model name that starts with jev- is taken, whatever follows.
fx = { ...ONE, jevNodes: jevNodes([[q(A, 1, 1), q(B, 2, 3)]], { model: "jev-preview" }) };
assert.deepEqual(srcs(runNew(fx, { apply: true })), [B]);

// Malformed answers for B, each of which would move B to the front if believed.
const bad = {
  "wrong type": { type: "noul", score: 3, noul: 0.9 },
  "no type": { score: 3 },
  "string score": { type: "score", score: "3" },
  "NaN": { type: "score", score: NaN },
  "Infinity": { type: "score", score: Infinity },
  "negative": { type: "score", score: -0.1 },
  "over range": { type: "score", score: 3.01 },
  "null score": { type: "score", score: null },
  "no score": { type: "score" },
  "boolean": { type: "score", score: true },
  "null answer": null,
  "string answer": "3",
  "array answer": [3],
};
// A is scored 2, the floor, so it leads and a believed B at 3 would take its place.
for (const [label, answer] of Object.entries(bad)) {
  fx = { ...ONE, jevNodes: jevNodes([[q(A, 1, 2), q(B, 2, 3)]], { mutate: (r) => ({ ...r, answers: { ...r.answers, s0c2: answer } }) }) };
  for (const apply of [false, true]) {
    out = runNew(fx, { apply });
    assert.deepEqual(srcs(out), [A], label);
    assert.equal(out.jevWouldChange, 0, label);
  }
}
// The same answers placed FIRST in the response, with a good answer behind them.
// The guards skip a bad answer with `continue`. A `break` in the score range guard
// would drop every good answer after the bad one, and no case above can tell,
// because in each of them the bad answer is last or alone. Here the answer for A
// is the bad one and the answer for B, behind it, is a 3 that must still count.
for (const [label, answer] of Object.entries(bad)) {
  fx = { ...ONE, jevNodes: jevNodes([[q(A, 1, undefined), q(B, 2, undefined)]], { mutate: (r) => ({ ...r, answers: { s0c1: answer, s0c2: { type: "score", score: 3 } } }) }) };
  assert.deepEqual(Object.keys(fx.jevNodes["Jev: Rank B-Roll"][0].json.answers), ["s0c1", "s0c2"], "the bad answer comes first: " + label);
  out = runNew(fx);
  assert.deepEqual(srcs(out), [A], label);
  assert.equal(out.jevRanked, 1, label);
  assert.equal(out.jevWouldChange, 1, label);
  assert.deepEqual(srcs(runNew(fx, { apply: true })), [B], label);
}
// The same answers on the first candidate, with nothing else scored. A bad value
// that looks low (negative, NaN) would demote A or drop it from the order, and
// one that looks high would rank it, so none of them may leave a trace.
for (const [label, answer] of Object.entries(bad)) {
  fx = { ...ONE, jevNodes: jevNodes([[q(A, 1, undefined), q(B, 2, undefined)]], { mutate: (r) => ({ ...r, answers: { s0c1: answer } }) }) };
  for (const apply of [false, true]) {
    out = runNew(fx, { apply });
    assert.equal(out.jevRanked, 0, label);
    assert.equal(out.jevWouldChange, 0, label);
    assert.deepEqual(strip(out), oneOld, label);
  }
}
// One bad answer does not take its neighbours down: A stays scored 2 and B is bad.
fx = { ...ONE, jevNodes: jevNodes([[q(A, 1, 2), q(B, 2, 3)]], { mutate: (r) => ({ ...r, answers: { ...r.answers, s0c2: bad["over range"] } }) }) };
assert.equal(runNew(fx).jevRanked, 1);
// Answers under a name nobody asked, a name that is not ours, and no answers at all.
for (const answers of [{ s0c9: { type: "score", score: 3 } }, { s7c1: { type: "score", score: 3 } }, { c2: { type: "score", score: 3 } },
  { "s0c2 ": { type: "score", score: 3 } }, { S0C2: { type: "score", score: 3 } }, {}, null, "answers", [], undefined]) {
  fx = { ...ONE, jevNodes: jevNodes([[q(A, 1, 1), q(B, 2, undefined)]], { mutate: (r) => ({ ...r, answers }) }) };
  for (const apply of [false, true]) {
    out = runNew(fx, { apply });
    assert.equal(out.jevRanked, 0, JSON.stringify(answers));
    assert.deepEqual(strip(out), oneOld, JSON.stringify(answers));
  }
}

// Malformed nodes: items with no json, links that are not an array, questions
// that are not an object. Each reads as no data and none of them throws.
const garbage = [
  { "Jev: B-Roll Bodies": [null, undefined, {}, { json: null }, { json: { segIndex: 0, links: "no", body: 3 } }, { json: { segIndex: 0, links: [A, B], body: { questions: {} } } }], "Jev: Rank B-Roll": control.jevNodes["Jev: Rank B-Roll"] },
  { "Jev: B-Roll Bodies": control.jevNodes["Jev: B-Roll Bodies"], "Jev: Rank B-Roll": [null, undefined, {}, { json: null }, { json: { model: "jev-1", answers: 5 } }] },
  { "Jev: B-Roll Bodies": [], "Jev: Rank B-Roll": [] },
];
for (const jn of garbage) {
  fx = { ...ONE, jevNodes: jn };
  for (const apply of [false, true]) {
    out = runNew(fx, { apply });
    assert.equal(out.jevRanked, 0);
    assert.deepEqual(strip(out), oneOld);
  }
}

// Scores that name a link the segment does not have change nothing.
fx = { ...ONE, jevNodes: jevNodes([[q("https://elsewhere.example/z.mp4", 1, 3), q(B, 2, undefined)]]) };
out = runNew(fx, { apply: true });
assert.equal(out.jevRanked, 0);
assert.deepEqual(strip(out), oneOld);

// ---- one bad item among good ones: the shape production has ------------------

// Jev: Rank B-Roll is an HTTP Request node fed one item per segment, so it hands
// back one item per segment, and one segment's request can fail or come back
// malformed while its neighbours are fine. Every case above feeds its damaged
// rank data as a single item, where a guard that lets the bad item throw and a
// guard that skips it look the same: readJev's outer catch returns an empty map and the answer is "no data"
// either way. With three segments they differ, because a throw also takes the
// two good segments' scores with it. Segment 1 is the damaged one below. Segment
// 0 prefers B (A scores 1, B scores 3) and segment 2 prefers F (E 1, F 3), and
// both must keep that whatever happens to segment 1.
const THREE = {
  segs: [seg(0), seg(1), seg(2)],
  px: [pex(A, B), pex(C, D), pex(E, F)],
  plan: [[q(A, 1, 1), q(B, 2, 3)], [q(C, 1, 1), q(D, 2, 1)], [q(E, 1, 1), q(F, 2, 3)]],
};
const damaged = (damage) => {
  const jn = jevNodes(THREE.plan);
  damage(jn);
  return { segs: THREE.segs, px: THREE.px, jevNodes: jn };
};
const GOOD3 = { type: "score", score: 3, confidence: 0.9, legend: {}, probabilities: {} };
const rankOf1 = (item) => (jn) => { jn["Jev: Rank B-Roll"][1] = item; };
const answersOf1 = (answers, model = "jev-1.14") => rankOf1({ json: { model, answers, usage: {} } });

// What every damaged case must show. Today's clips are A, C, E and shadow keeps
// them. Applied, segments 0 and 2 take B and F, and segment 1 takes `mid`.
// `ranked` counts the segments Jev scored, and each of those would change a pick.
const keepsNeighbours = (fx, label, mid = C, ranked = 2) => {
  const shadow = runNew(fx);
  assert.deepEqual(strip(shadow), runOld(fx), label);
  assert.deepEqual(srcs(shadow), [A, C, E], label);
  assert.equal(shadow.jevRanked, ranked, label);
  assert.equal(shadow.jevWouldChange, ranked, label);
  const applied = runNew(fx, { apply: true });
  assert.deepEqual(srcs(applied), [B, mid, F], label);
  assert.equal(applied.jevRanked, ranked, label);
  assert.equal(applied.jevWouldChange, ranked, label);
};

// The control: nothing damaged. All three segments are scored, and segment 1
// scores C and D alike, so it keeps C and only segments 0 and 2 would change.
let three = damaged(() => {});
assert.equal(three.jevNodes["Jev: Rank B-Roll"].length, 3, "one rank item per segment");
assert.deepEqual(srcs(runNew(three, { apply: true })), [B, C, F]);
assert.equal(runNew(three).jevRanked, 3);
assert.equal(runNew(three).jevWouldChange, 2);

// (a) Segment 1's request failed or answered with something that is not a Jev
// response: an HTTP error item with no model and an error field, a model that is
// not a string, a model from another family, an item with nothing in it. Where
// the item carries answers at all, they would put D ahead if they were believed.
const lure = { s1c2: GOOD3 };
for (const [label, item] of Object.entries({
  "HTTP error item": { json: { error: { message: "The service is unavailable", code: 503 } } },
  "no model": { json: { answers: lure, usage: {} } },
  "null model": { json: { model: null, answers: lure } },
  "numeric model": { json: { model: 14, answers: lure } },
  "object model": { json: { model: { name: "jev-1.14" }, answers: lure } },
  "other model": { json: { model: "gpt-5", answers: lure } },
  "item with no json": {},
  "null item": null,
})) keepsNeighbours(damaged(rankOf1(item)), "bad item: " + label);

// (b) A valid model whose answer for one question is not an answer. null is the
// one that throws if it is read (null.type); the others must simply not count.
// With nothing else answered, segment 1 is not scored and keeps C.
for (const [label, answer] of Object.entries(bad))
  keepsNeighbours(damaged(answersOf1({ s1c1: answer })), "bad answer: " + label);
// With a good answer beside it the good one counts, whichever comes first: D
// scores 3 and C has no score, so segment 1 would take D and is ranked.
keepsNeighbours(damaged(answersOf1({ s1c1: null, s1c2: GOOD3 })), "null answer, then a good one", D, 3);
keepsNeighbours(damaged(answersOf1({ s1c2: GOOD3, s1c1: null })), "a good answer, then null", D, 3);

// (c) A valid model whose answers are not an object. null and a missing field are
// the shapes that throw if read (Object.keys of either). A number or true yields
// no keys, and a string or an array yields index numbers, which are no name of
// ours, so those four are kept as controls: they read as no data with the guard
// or without it.
for (const [label, answers] of Object.entries({
  "null": null, "undefined": undefined, "number": 5, "string": "s1c2", "true": true, "empty array": [], "array of answers": [GOOD3],
})) keepsNeighbours(damaged(answersOf1(answers)), "answers is " + label);
keepsNeighbours(damaged(rankOf1({ json: { model: "jev-1.14", usage: {} } })), "answers field missing");

// (d) A question whose name is not s{n}c{k}. The bodies node never writes one, so
// this is a guard against a damaged bodies item, and it has to be one that still
// pairs the name with a link or the link test would skip it first. Segment 1 asks
// two questions, the odd one and s1c2, and both are answered with a 3. The odd
// one is ignored and D, behind s1c2, is what Jev picks for segment 1.
const renamed = (name) => (jn) => {
  const ask = { type: "score", instructions: "How well does it work?", criteria: ["0", "1", "2", "3"] };
  jn["Jev: B-Roll Bodies"][1] = { json: { segIndex: 1, links: [C, D], body: { model: "jev-latest", state: { sentence: "x" }, questions: { [name]: ask, s1c2: ask }, assets: {} } } };
  jn["Jev: Rank B-Roll"][1] = { json: { model: "jev-1.14", answers: { [name]: GOOD3, s1c2: GOOD3 }, usage: {} } };
};
for (const name of ["bogus", "s1c", "sc2", "s1c2x", "xs1c2", " s1c2", "S1C2", "s1-c2", "s1c2\n", "s1c2 ", "", "s", "1"])
  keepsNeighbours(damaged(renamed(name)), "question named " + JSON.stringify(name), D, 3);
// The same through the path with no body: a bodies item that has no segIndex names
// its questions "sundefinedc1" and "sundefinedc2", and links them all the same.
keepsNeighbours(damaged((jn) => {
  jn["Jev: B-Roll Bodies"][1] = { json: { links: [C, D] } };
  jn["Jev: Rank B-Roll"][1] = { json: { model: "jev-1.14", answers: { sundefinedc1: GOOD3, sundefinedc2: GOOD3 }, usage: {} } };
}), "bodies item with no segIndex");

console.log("Build Movie: shadow output matches the export, Jev ranking behaves");
