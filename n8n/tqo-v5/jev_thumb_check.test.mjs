/**
 * Does the Jev check of the composed thumbnail build a request TypeSafe will
 * take, turn its answers into the right note, and leave the Shim exactly as it
 * is today whenever Jev did not run?
 *
 *   node n8n/tqo-v5/jev_thumb_check.test.mjs
 *
 * Three node bodies run inside a Function with `$` and `$input` stubbed: the
 * request builder (jev_thumb_check_body.js), the verdict
 * (jev_thumb_check_verdict.js) and the Shim (shim_thumbnail_to_binary.js). The
 * Shim is also run beside the UNMODIFIED code read out of the live export,
 * exports/qEkGOUsNyVaRAmm6_active.json. Set the four Jev keys aside and every
 * case gives the export code's output while JEV_APPLY is false; the paths that
 * make no thumbnail match it field for field with nothing set aside. `$('X')`
 * throws when node X did not run, as it does in n8n, and the stub does too.
 *
 * Two things are read out of the live export so a drift turns this red: the
 * Shim's unmodified code, which the shipped Shim must equal outside its Jev
 * block (the strict mirror at the end), and the compositor layout the verdict's
 * right edge is built on (Thumb: Compose and Thumb: Pick Still). The Shim also
 * refuses a verdict built for another row's headline, which is the stale run
 * guard for the Split In Batches loop.
 *
 * Nothing here touches the network. The answers are written by hand from the
 * TypeSafe contract (api.typesafe.ai/openapi.json 0.2.0), so this proves the
 * code against the contract and not against a live Jev: no key is funded yet.
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const read = (file) => readFileSync(new URL("./" + file, import.meta.url), "utf8");
// An en dash or an em dash, built from code points so this file carries neither.
const DASHES = new RegExp("[" + String.fromCharCode(0x2013, 0x2014) + "]");
const make = (file) => new Function("$", "$input", read(file));
const bodyNode = make("jev_thumb_check_body.js");
const verdictNode = make("jev_thumb_check_verdict.js");
// The Shim as shipped (JEV_APPLY false), and a scratch copy with the constant
// flipped to true, the way jev_thumb_rank.test.mjs flips its own. The file on
// disk is never written.
const SHIM_SHIPPED = read("shim_thumbnail_to_binary.js");
const SHIM_FLIPPED = SHIM_SHIPPED.replace("const JEV_APPLY = false;", "const JEV_APPLY = true;");
assert.notEqual(SHIM_FLIPPED, SHIM_SHIPPED, "the shipped Shim declares JEV_APPLY = false");
assert.match(SHIM_SHIPPED, /^const JEV_APPLY = false;$/m);
assert.equal(SHIM_SHIPPED.match(/JEV_APPLY = /g).length, 1, "one declaration");
assert.match(SHIM_FLIPPED, /^const JEV_APPLY = true;$/m);
const shimNew = new Function("$", "$input", SHIM_SHIPPED);
const shimOn = new Function("$", "$input", SHIM_FLIPPED);

// The unmodified Shim, straight from the live export's node.
const EXPORT = JSON.parse(read("exports/qEkGOUsNyVaRAmm6_active.json"));
const exportNode = (name) => {
  const hits = EXPORT.nodes.filter((n) => n.name === name);
  assert.equal(hits.length, 1, name);
  return hits[0];
};
const exportCode = (name) => exportNode(name).parameters.jsCode;
const SHIM_EXPORT = exportCode("Shim: Thumbnail To Binary");
const shimOld = new Function("$", "$input", SHIM_EXPORT);

// n8n's `$('Name')`: an object with all() and first(), and a throw when the
// node did not run.
const dollar = (nodes) => (name) => {
  if (!Object.prototype.hasOwnProperty.call(nodes, name)) throw new Error("Node '" + name + "' hasn't been executed");
  const items = nodes[name];
  return { all: () => items, first: () => items[0] };
};
const NO_NODES = dollar({});

// ---------------------------------------------------------------------------
// The request builder
// ---------------------------------------------------------------------------

const HEADLINE = "THE MIDDLE IS THE TARGET";
// Real file magic bytes, so the prefixes below are measured and not typed.
const JPEG = Buffer.from([0xff, 0xd8, 0xff, 0xe0, 0x00, 0x10, 0x4a, 0x46, 0x49, 0x46, 0x00, 0x01, 0x01]).toString("base64");
const PNG = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00, 0x00, 0x00, 0x0d]).toString("base64");
const GIF = Buffer.from("GIF89a\x01\x00\x01\x00", "latin1").toString("base64");
const WEBP = Buffer.from("RIFF\x24\x00\x00\x00WEBPVP8 ", "latin1").toString("base64");
assert.ok(JPEG.startsWith("/9j/"));
assert.ok(PNG.startsWith("iVBORw0KGgo"));

// `item` is what Jev: Thumb To Base64 (Composed) hands over: json.still_b64.
// `nodes` are the earlier nodes that ran.
const runBody = (item, nodes = { "Thumb: Pick Still": [{ json: { headline: HEADLINE } }] }) =>
  bodyNode(dollar(nodes), { first: () => item });

// The TypeSafe rules this request has to meet, from the contract.
const checkRequest = (body) => {
  assert.equal(JSON.parse(JSON.stringify(body)).model, body.model, "body survives JSON");
  assert.match(body.model, /^jev-/);
  const types = Object.values(body.questions).map((q) => q.type);
  assert.ok(types.every((t) => ["score", "noul", "box"].includes(t)));
  if (types.includes("box")) {
    // box.md: Box questions need Jev 1.14, sent as jev-preview or jev-1.14.0.
    assert.ok(["jev-preview", "jev-1.14.0"].includes(body.model), "a box question needs Jev 1.14, which is jev-preview or jev-1.14.0");
    assert.ok(types.includes("noul"), "a box question is paired with a noul question");
  }
  for (const q of Object.values(body.questions)) {
    assert.equal(typeof q.instructions, "string");
    if (q.type === "noul") assert.deepEqual(Object.keys(q.criteria).sort(), ["false", "true"]);
    if (q.type === "box") assert.equal(q.criteria, undefined);
  }
  // Every asset is referenced by a placeholder, and every placeholder is an asset.
  const text = JSON.stringify({ state: body.state, questions: body.questions });
  for (const ref of Object.keys(body.assets)) assert.ok(text.includes(ref), ref + " is referenced");
  for (const ref of text.match(/<[a-z0-9]+>/g) || []) assert.ok(ref in body.assets, ref + " is an asset");
  // The image goes in state once (images.md, Image placement): the state holds
  // each reference exactly once, and no question holds one, because a reference
  // in a question's instructions sends the image again for that question.
  for (const ref of Object.keys(body.assets)) {
    assert.equal(JSON.stringify(body.state).split(ref).length - 1, 1, ref + " is in state once");
    for (const [name, q] of Object.entries(body.questions)) assert.ok(!JSON.stringify(q).includes(ref), name + " does not hold the reference " + ref);
  }
  // A name in backticks is a field of the state.
  for (const q of Object.values(body.questions)) {
    for (const m of q.instructions.matchAll(/`([A-Za-z_][A-Za-z0-9_]*)`/g)) assert.ok(Object.hasOwn(body.state, m[1]), "`" + m[1] + "` is a field of the state");
  }
  for (const a of Object.values(body.assets)) {
    assert.equal(a.type, "image");
    assert.ok(["jpeg", "png"].includes(a.format));
    assert.equal(typeof a.data_base64, "string");
  }
  // House writing rules: no em or en dash anywhere in what is sent.
  assert.doesNotMatch(JSON.stringify(body), DASHES);
};

let out = runBody({ json: { still_b64: JPEG } });
assert.equal(out.length, 1);
assert.deepEqual(Object.keys(out[0].json), ["body"]);
let body = out[0].json.body;
checkRequest(body);
assert.equal(body.model, "jev-1.14.0", "pinned, ruled 2026-10-27");
// The composed image is sent once, in state, and the questions name it by its
// backtick path. The asset key stays "<thumb>".
assert.deepEqual(body.state, { thumb: "<thumb>", headline: HEADLINE });
assert.deepEqual(Object.keys(body.state), ["thumb", "headline"]);
assert.deepEqual(Object.keys(body.questions), ["headline_present", "headline_box", "headline_readable"]);
assert.deepEqual(body.questions.headline_present.type, "noul");
assert.equal(body.questions.headline_present.instructions, "Does `thumb` show the words in `headline` as text on the image?");
assert.deepEqual(body.questions.headline_box, { type: "box", instructions: "the headline text in `thumb`, the words in `headline`" });
for (const [name, q] of Object.entries(body.questions)) {
  assert.ok(q.instructions.includes("`thumb`"), name + " refers to the image as `thumb`");
  assert.ok(!q.instructions.includes("<thumb>"), name + " never holds the reference string");
}
// headline_readable asks one thing (noul.md: one condition per Noul), and the
// box rules cover a headline touching the edge.
assert.deepEqual(body.questions.headline_readable, {
  type: "noul",
  instructions: "Is every word of the headline in `thumb` easy to read at phone size?",
  criteria: {
    true: "Every word of the headline is easy to read at phone size",
    false: "A word of the headline is hard to read at phone size",
  },
});
assert.doesNotMatch(
  body.questions.headline_readable.instructions + JSON.stringify(body.questions.headline_readable.criteria),
  /\band\b|\bor\b|cut off|edge/i,
  "headline_readable holds one condition",
);
assert.deepEqual(body.assets, { "<thumb>": { type: "image", format: "jpeg", data_base64: JPEG } });

// A PNG goes out as a PNG; the headline in the state is the one Pick Still holds.
out = runBody({ json: { still_b64: PNG } }, { "Thumb: Pick Still": [{ json: { headline: "TWO WORDS", photoUsed: "u" } }] });
assert.equal(out[0].json.body.assets["<thumb>"].format, "png");
assert.deepEqual(out[0].json.body.state, { thumb: "<thumb>", headline: "TWO WORDS" });
checkRequest(out[0].json.body);

// Nothing it cannot send goes out: no image, an empty one, a type that is not a
// string, a format TypeSafe does not take, no headline, or a node that did not run.
for (const item of [
  undefined,
  { json: {} },
  { json: { still_b64: "" } },
  { json: { still_b64: null } },
  { json: { still_b64: 12345 } },
  { json: { still_b64: { data: JPEG } } },
  { json: { still_b64: GIF } },
  { json: { still_b64: WEBP } },
  { json: { still_b64: "data:image/jpeg;base64," + JPEG } },
  { json: { still_b64: " " + JPEG } },
  { json: { error: "The item has no binary field 'thumbData'" } },
]) assert.deepEqual(runBody(item), [], JSON.stringify(item));
for (const headline of ["", "   ", null, undefined]) {
  assert.deepEqual(runBody({ json: { still_b64: JPEG } }, { "Thumb: Pick Still": [{ json: { headline } }] }), [], String(headline));
}
assert.deepEqual(runBody({ json: { still_b64: JPEG } }, {}), []);
assert.deepEqual(runBody({ json: { still_b64: JPEG } }, { "Thumb: Pick Still": [] }), []);
assert.deepEqual(bodyNode(dollar({ "Thumb: Pick Still": [{ json: { headline: HEADLINE } }] }), { first: () => { throw new Error("boom"); } }), []);
assert.deepEqual(bodyNode(NO_NODES, { first: () => ({ json: { still_b64: JPEG } }) }), []);

// The request body is held to 20,000,000 characters of base64.
assert.equal(runBody({ json: { still_b64: "/9j/" + "A".repeat(20000000 - 4) } }).length, 1);
assert.deepEqual(runBody({ json: { still_b64: "/9j/" + "A".repeat(20000000 - 3) } }), []);

// ---------------------------------------------------------------------------
// The verdict
// ---------------------------------------------------------------------------

// A frame laid out the way Thumb: Compose draws it: headline at x 72 and y 225
// on the dark panel, which ends at 760 of 1280 px. The box ends at 0.55, 704 px.
const CLEAN_BOX = { top: 0.31, bottom: 0.62, left: 0.056, right: 0.55 };
// A key given as undefined stays undefined, so the bad cases below can use it.
const answers = (over = {}) => ({
  headline_present: { type: "noul", noul: "present" in over ? over.present : 0.97 },
  headline_box: { type: "box", box: "box" in over ? over.box : CLEAN_BOX, confidence: 0.8 },
  headline_readable: { type: "noul", noul: "readable" in over ? over.readable : 0.93 },
});
const response = (over = {}, model = "jev-preview") => ({ model, answers: answers(over), usage: { input_tokens: 1200 } });
// The verdict reads its own input and, for forHeadline alone, the node in front
// of the request, Jev: Thumb Check Body. Any other node throwing must not matter.
const verdictThrows = () => { throw new Error("the verdict reads only its input and the check body"); };
const CHECK_BODY = "Jev: Thumb Check Body";
// What that node hands over: the request it built, whose state names the headline.
const checkBodyOf = (state) => [{ json: { body: { state } } }];
const verdictDollar = (headline = HEADLINE) => dollar({ [CHECK_BODY]: checkBodyOf({ thumb: "<thumb>", headline }) });
const runVerdict = (json, $ = verdictDollar()) => verdictNode($, { first: () => (json === undefined ? undefined : { json }) });
const VERDICT_KEYS = ["jevThumbNote", "jevThumbChecked", "jevHeadlineBox", "forHeadline"];
// The whole item, forHeadline included.
const verdictFull = (json, $) => {
  const r = runVerdict(json, $);
  assert.equal(r.length, 1, "always one item");
  assert.deepEqual(Object.keys(r[0].json), VERDICT_KEYS);
  return r[0].json;
};
// The three verdict fields. forHeadline is the check body's headline on every
// verdict, checked or not, and is pinned here once for all of them.
const verdict = (json) => {
  const { forHeadline, ...rest } = verdictFull(json);
  assert.equal(forHeadline, HEADLINE, "forHeadline is the headline the request was built for");
  return rest;
};
const NOTE = {
  absent: "the headline text was not found on the thumbnail",
  runsOff: "the headline runs off the dark panel onto the photograph",
  edge: "the headline touches the edge of the frame",
  hard: "the headline is hard to read at phone size",
};
const UNCHECKED = { jevThumbNote: null, jevThumbChecked: false, jevHeadlineBox: null };
const ABSENT = { jevThumbNote: NOTE.absent, jevThumbChecked: true, jevHeadlineBox: null };
// Every box TypeSafe's contract rules out: not four edges in 0..1 with top above
// bottom and left above right. The first entry is the zero area box.
const BAD_BOXES = [
  ["a zero area box", { top: 0, bottom: 0, left: 0, right: 0 }],
  ["null", null],
  ["undefined", undefined],
  ["an array", [0.1, 0.2, 0.3, 0.4]],
  ["a missing edge", { top: 0.3, bottom: 0.6, left: 0.05 }],
  ["NaN", { ...CLEAN_BOX, top: NaN }],
  ["Infinity", { ...CLEAN_BOX, right: Infinity }],
  ["a string edge", { ...CLEAN_BOX, left: "0.05" }],
  ["above 1", { ...CLEAN_BOX, bottom: 1.01 }],
  ["below 0", { ...CLEAN_BOX, top: -0.01 }],
  ["top below bottom reversed", { ...CLEAN_BOX, top: 0.7, bottom: 0.3 }],
  ["no height", { ...CLEAN_BOX, top: 0.4, bottom: 0.4 }],
  ["left right reversed", { ...CLEAN_BOX, left: 0.5, right: 0.1 }],
  ["no width", { ...CLEAN_BOX, left: 0.3, right: 0.3 }],
];

// A clean frame: checked, no note, and the box comes back.
assert.deepEqual(verdict(response()), { jevThumbNote: null, jevThumbChecked: true, jevHeadlineBox: CLEAN_BOX });
// The box is a copy of the four edges and nothing else.
assert.deepEqual(Object.keys(verdict(response()).jevHeadlineBox), ["top", "bottom", "left", "right"]);

// Headline not found: that note alone, the box is ignored and so is readability.
assert.deepEqual(
  verdict(response({ present: 0.2, box: { top: 0.4, bottom: 0.99, left: 0.01, right: 0.99 }, readable: 0.1 })),
  { jevThumbNote: NOTE.absent, jevThumbChecked: true, jevHeadlineBox: null },
);
assert.equal(verdict(response({ present: 0 })).jevThumbNote, NOTE.absent);
assert.equal(verdict(response({ present: 0.499 })).jevThumbNote, NOTE.absent);
// 0.5 is found: the rest of the rules run.
assert.deepEqual(verdict(response({ present: 0.5 })), { jevThumbNote: null, jevThumbChecked: true, jevHeadlineBox: CLEAN_BOX });
assert.equal(verdict(response({ present: 1 })).jevThumbNote, null);

// The check order: with the headline absent the box answer is not validated or
// used at all. TypeSafe's Box has no not-found answer and its docs say to ignore
// the box when the Noul is low, so a box that fails the shape rules beside an
// absent headline still gives the did-not-find note, checked, with no box.
assert.deepEqual(verdict(response({ present: 0.1, box: { top: 0, bottom: 0, left: 0, right: 0 } })), ABSENT);
for (const [what, box] of BAD_BOXES) {
  assert.deepEqual(verdict(response({ present: 0.1, box })), ABSENT, "absent headline beside a box that is " + what);
  assert.deepEqual(verdict(response({ present: 0.499, box })), ABSENT, "0.499 beside a box that is " + what);
  // The same box with the headline found is ignored whole, as before.
  assert.deepEqual(verdict(response({ present: 0.5, box })), UNCHECKED, "0.5 beside a box that is " + what);
  assert.deepEqual(verdict(response({ present: 0.97, box })), UNCHECKED, "0.97 beside a box that is " + what);
}
// A box answer that is missing or of the wrong type is not read either.
{
  const { headline_box: _box, ...noBox } = answers({ present: 0.1 });
  assert.deepEqual(verdict({ model: "jev-preview", answers: noBox }), ABSENT, "no box answer, headline absent");
  assert.deepEqual(verdict({ model: "jev-preview", answers: { ...noBox, headline_box: { type: "noul", noul: 0.5 } } }), ABSENT, "box answered as a noul, headline absent");
  assert.deepEqual(verdict({ model: "jev-preview", answers: { ...noBox, headline_box: null } }), ABSENT, "box answer null, headline absent");
  assert.deepEqual(verdict({ model: "jev-preview", answers: { ...noBox, headline_box: { type: "box", box: CLEAN_BOX } } }), ABSENT, "a good box is dropped too");
  const found = answers({ present: 0.9 });
  delete found.headline_box;
  assert.deepEqual(verdict({ model: "jev-preview", answers: found }), UNCHECKED, "no box answer, headline found");
}
// readable is read only once the headline is found, like the box, so a bad
// readable beside an absent headline changes nothing. Beside a found headline
// it ignores the whole response, and a bad present always does.
assert.deepEqual(verdict(response({ present: 0.1, readable: NaN })), ABSENT);
assert.deepEqual(verdict(response({ present: 0.1, readable: undefined })), ABSENT);
assert.deepEqual(verdict(response({ present: 0.9, readable: NaN })), UNCHECKED);
assert.deepEqual(verdict(response({ present: 0.9, readable: undefined })), UNCHECKED);
assert.deepEqual(verdict(response({ present: NaN, box: BAD_BOXES[0][1] })), UNCHECKED);
assert.deepEqual(verdict(response({ present: undefined, box: BAD_BOXES[0][1] })), UNCHECKED);
// A model that is not a jev- model is ignored first, whatever the answers hold.
assert.deepEqual(verdict(response({ present: 0.1, box: BAD_BOXES[0][1] }, "gpt-4o")), UNCHECKED);

// The upper bound of the unit range is in range. An answer or a box edge of
// exactly 1 is usable (v <= 1), and a hair over 1 is not. The box edge of 1 is
// returned with the box; only bottom and right can reach 1, because top has to
// stay above bottom and left above right.
const CLEAN = { jevThumbNote: null, jevThumbChecked: true, jevHeadlineBox: CLEAN_BOX };
assert.deepEqual(verdict(response({ present: 1 })), CLEAN, "present 1 is checked");
assert.deepEqual(verdict(response({ readable: 1 })), CLEAN, "readable 1 is checked");
assert.deepEqual(verdict(response({ present: 1, readable: 1 })), CLEAN, "present 1 and readable 1 are checked");
assert.deepEqual(
  verdict(response({ box: { ...CLEAN_BOX, bottom: 1 } })),
  { jevThumbNote: NOTE.edge, jevThumbChecked: true, jevHeadlineBox: { ...CLEAN_BOX, bottom: 1 } },
  "a box bottom of exactly 1 gives the edge note, checked, box returned",
);
assert.deepEqual(
  verdict(response({ box: { ...CLEAN_BOX, right: 1 } })),
  { jevThumbNote: NOTE.runsOff, jevThumbChecked: true, jevHeadlineBox: { ...CLEAN_BOX, right: 1 } },
  "a box right of exactly 1 gives the runs off note, checked, box returned",
);
assert.deepEqual(verdict(response({ box: { top: 0.5, bottom: 1, left: 0.1, right: 1 } })), {
  jevThumbNote: NOTE.runsOff + "; " + NOTE.edge, jevThumbChecked: true, jevHeadlineBox: { top: 0.5, bottom: 1, left: 0.1, right: 1 },
}, "both edges at 1 give both notes");
// One step over 1 is out of range, for every number the verdict reads.
const OVER = 1.000001;
assert.deepEqual(verdict(response({ present: OVER })), UNCHECKED, "present over 1");
assert.deepEqual(verdict(response({ readable: OVER })), UNCHECKED, "readable over 1");
assert.deepEqual(verdict(response({ box: { ...CLEAN_BOX, bottom: OVER } })), UNCHECKED, "box bottom over 1");
assert.deepEqual(verdict(response({ box: { ...CLEAN_BOX, right: OVER } })), UNCHECKED, "box right over 1");
// And the lower bound: 0 is in range, a hair under is not.
assert.deepEqual(verdict(response({ readable: 0 })), { jevThumbNote: NOTE.hard, jevThumbChecked: true, jevHeadlineBox: CLEAN_BOX });
assert.deepEqual(verdict(response({ present: 0 })), ABSENT);
assert.deepEqual(verdict(response({ readable: -0.000001 })), UNCHECKED, "readable under 0");
assert.deepEqual(verdict(response({ present: -0.000001 })), UNCHECKED, "present under 0");

// ---------------------------------------------------------------------------
// The layout the right edge is built on, read from the export
// ---------------------------------------------------------------------------

// The verdict's TEXT_RIGHT is the designed right edge of the headline: the x it
// is drawn at plus the width Pick Still wraps it to, over the frame width. All
// four numbers live in the export, so a compositor change that is not carried
// into the verdict turns this red.
const composeOps = exportNode("Thumb: Compose").parameters.operations.operations;
const opsOf = (kind) => composeOps.filter((o) => o.operation === kind);
// The frame is resized to 1280 wide, so the fractions the verdict reads are of 1280.
assert.equal(opsOf("resize").length, 1, "one resize");
assert.equal(opsOf("resize")[0].width, 1280, "Thumb: Compose resizes to width 1280");
// The headline is the text operation that draws the Pick Still headline (the
// kicker is the other one), at x 72.
const headlineOps = opsOf("text").filter((o) => /\.json\.headline\b/.test(String(o.text)));
assert.equal(headlineOps.length, 1, "one headline text operation");
assert.equal(headlineOps[0].positionX, 72, "the headline is drawn at positionX 72");
// The dark panel (scrim) ends at 760, a little inside the headline's designed edge.
assert.equal(opsOf("draw").length, 1, "one scrim");
assert.equal(opsOf("draw")[0].startPositionX, 0);
assert.equal(opsOf("draw")[0].endPositionX, 760, "the scrim ends at endPositionX 760");
// Pick Still wraps the headline to a 700 px budget.
const budget = /Math\.floor\((\d+) \/ \(size \* 0\.52\)\)/.exec(exportCode("Thumb: Pick Still"));
assert.ok(budget, "Thumb: Pick Still wraps the headline with floor(budget / (size * 0.52))");
assert.equal(Number(budget[1]), 700, "Thumb: Pick Still wraps the headline to a 700 px budget");
const TEXT_RIGHT = (headlineOps[0].positionX + Number(budget[1])) / opsOf("resize")[0].width;
assert.equal(TEXT_RIGHT, 0.603125, "the designed right edge of the text is 772 of 1280 px");
assert.ok(TEXT_RIGHT > opsOf("draw")[0].endPositionX / 1280, "a full line ends a little past the scrim, so the scrim edge is not the line");

// Each threshold, one step either side.
const withBox = (edit) => verdict(response({ box: { ...CLEAN_BOX, ...edit } }));
assert.equal(withBox({ right: TEXT_RIGHT - 0.001 }).jevThumbNote, null);
assert.equal(withBox({ right: TEXT_RIGHT }).jevThumbNote, null, "exactly at the designed edge is not over it");
assert.equal(withBox({ right: TEXT_RIGHT + 0.001 }).jevThumbNote, NOTE.runsOff);
assert.equal(withBox({ right: 0.97 }).jevThumbNote, NOTE.runsOff);
// A full line that ends past the scrim (760 px, 0.59375) and inside the text
// budget is the layout working as designed, not a headline that ran off.
assert.equal(withBox({ right: 0.595 }).jevThumbNote, null);
assert.equal(withBox({ right: 0.6 }).jevThumbNote, null);
assert.equal(withBox({ bottom: 0.95 }).jevThumbNote, null);
assert.equal(withBox({ bottom: 0.951 }).jevThumbNote, NOTE.edge);
assert.equal(withBox({ top: 0.02 }).jevThumbNote, null);
assert.equal(withBox({ top: 0.019 }).jevThumbNote, NOTE.edge);
assert.equal(withBox({ left: 0.02 }).jevThumbNote, null);
assert.equal(withBox({ left: 0.019 }).jevThumbNote, NOTE.edge);
assert.equal(withBox({ top: 0, left: 0 }).jevThumbNote, NOTE.edge, "top and left both touching is one note");
assert.equal(verdict(response({ readable: 0.5 })).jevThumbNote, null);
assert.equal(verdict(response({ readable: 0.499 })).jevThumbNote, NOTE.hard);
assert.equal(verdict(response({ readable: 0 })).jevThumbNote, NOTE.hard);

// Several notes join with "; ", in the order the rules are written.
assert.equal(
  verdict(response({ box: { top: 0.3, bottom: 0.97, left: 0.05, right: 0.7 }, readable: 0.2 })).jevThumbNote,
  [NOTE.runsOff, NOTE.edge, NOTE.hard].join("; "),
);
assert.equal(verdict(response({ box: { ...CLEAN_BOX, right: 0.8 }, readable: 0.2 })).jevThumbNote, NOTE.runsOff + "; " + NOTE.hard);
assert.equal(verdict(response({ box: { ...CLEAN_BOX, bottom: 0.99 }, readable: 0.2 })).jevThumbNote, NOTE.edge + "; " + NOTE.hard);
// A noted frame still returns its box, so the next step can see where the text sat.
assert.deepEqual(withBox({ right: 0.8 }).jevHeadlineBox, { ...CLEAN_BOX, right: 0.8 });

// Any jev- model is read; other names and spellings are not.
assert.equal(verdict(response({}, "jev-latest")).jevThumbChecked, true);
assert.equal(verdict(response({}, "jev-preview-2026-10")).jevThumbChecked, true);
for (const model of ["gpt-4o", "jev", "jevpreview", "Jev-preview", " jev-preview", "", null, 7, undefined]) {
  assert.deepEqual(verdict({ ...response(), model }), UNCHECKED, String(model));
}

// A bad or missing response is ignored whole: not checked, no note, no box.
const bad = (label, json) => assert.deepEqual(verdict(json), UNCHECKED, label);
bad("no item at all", undefined);
bad("null json", null);
bad("empty object", {});
bad("an error item from the HTTP node", { error: { message: "Request failed with status code 402", httpCode: "402" } });
bad("a TypeSafe error body", { detail: "Insufficient credits", status: 402 });
bad("no answers", { model: "jev-preview" });
bad("answers null", { model: "jev-preview", answers: null });
bad("answers a string", { model: "jev-preview", answers: "headline_present" });
bad("answers empty", { model: "jev-preview", answers: {} });
for (const [what, value] of [
  ["NaN", NaN],
  ["Infinity", Infinity],
  ["-Infinity", -Infinity],
  ["above 1", 1.2],
  ["below 0", -0.1],
  ["a numeric string", "0.9"],
  ["null", null],
  ["undefined", undefined],
  ["an object", { value: 0.9 }],
]) {
  bad("present " + what, response({ present: value }));
  bad("readable " + what, response({ readable: value }));
  // One bad answer ignores the whole response, even when the others would raise a note.
  bad("present " + what + " beside a rule that would fire", response({ present: value, readable: 0.1 }));
  bad("readable " + what + " beside a rule that would fire", response({ readable: value, box: { ...CLEAN_BOX, right: 0.9 } }));
}
// A bad box beside a found headline ignores the whole response.
for (const [what, box] of BAD_BOXES) bad("box " + what, response({ box }));
// The wrong answer type under the right name.
bad("present given as a score", { ...response(), answers: { ...answers(), headline_present: { type: "score", score: 2, confidence: 0.9 } } });
bad("present given as a box", { ...response(), answers: { ...answers(), headline_present: { type: "box", box: CLEAN_BOX } } });
bad("box given as a noul", { ...response(), answers: { ...answers(), headline_box: { type: "noul", noul: 0.5 } } });
bad("readable given as a score", { ...response(), answers: { ...answers(), headline_readable: { type: "score", score: 3 } } });
bad("an answer with no type", { ...response(), answers: { ...answers(), headline_present: { noul: 0.9 } } });
for (const name of ["headline_present", "headline_box", "headline_readable"]) {
  const { [name]: _left, ...rest } = answers();
  bad("missing " + name, { model: "jev-preview", answers: rest });
}
// It never throws, even when reading its own input does. forHeadline is read
// apart, so it is still the check body's headline, or null when that is unreadable.
assert.deepEqual(verdictNode(verdictThrows, { first: () => { throw new Error("boom"); } })[0].json, { ...UNCHECKED, forHeadline: null });
assert.deepEqual(verdictNode(verdictThrows, {})[0].json, { ...UNCHECKED, forHeadline: null });
assert.deepEqual(verdictNode(verdictDollar(), { first: () => { throw new Error("boom"); } })[0].json, { ...UNCHECKED, forHeadline: HEADLINE });
assert.deepEqual(verdictNode(verdictDollar(), {})[0].json, { ...UNCHECKED, forHeadline: HEADLINE });

// forHeadline: the headline the request was built for, read from the state of
// Jev: Thumb Check Body, so the Shim can tell a verdict from another row's loop pass.
assert.equal(verdictFull(response()).forHeadline, HEADLINE);
assert.equal(verdictFull(response(), verdictDollar("TWO WORDS")).forHeadline, "TWO WORDS");
assert.equal(verdictFull(response({ present: 0.1 })).forHeadline, HEADLINE, "an absent headline verdict carries it");
assert.equal(verdictFull({ error: { message: "402" } }).forHeadline, HEADLINE, "an unchecked verdict carries it");
assert.equal(verdictFull(undefined).forHeadline, HEADLINE, "no response item at all carries it");
// It is the first item of the check body, the way the Shim reads the verdict.
assert.equal(verdictFull(response(), dollar({ [CHECK_BODY]: [...checkBodyOf({ headline: "FIRST" }), ...checkBodyOf({ headline: "SECOND" })] })).forHeadline, "FIRST");
// Unreadable is null, and it changes nothing else: the verdict is the clean one.
for (const [what, $] of [
  ["the check body did not run", verdictThrows],
  ["the check body is the only node and it threw", () => { throw new Error("boom"); }],
  ["no check body items", dollar({ [CHECK_BODY]: [] })],
  ["an item with no json", dollar({ [CHECK_BODY]: [{}] })],
  ["a json with no body", dollar({ [CHECK_BODY]: [{ json: {} }] })],
  ["a body with no state", dollar({ [CHECK_BODY]: [{ json: { body: {} } }] })],
  ["a state with no headline", dollar({ [CHECK_BODY]: checkBodyOf({ thumb: "<thumb>" }) })],
  ["a null headline", dollar({ [CHECK_BODY]: checkBodyOf({ headline: null }) })],
  ["a number headline", dollar({ [CHECK_BODY]: checkBodyOf({ headline: 42 }) })],
  ["an array headline", dollar({ [CHECK_BODY]: checkBodyOf({ headline: ["A"] }) })],
  ["an object headline", dollar({ [CHECK_BODY]: checkBodyOf({ headline: { text: "A" } }) })],
]) {
  const got = verdictFull(response(), $);
  assert.equal(got.forHeadline, null, what);
  assert.deepEqual({ ...got, forHeadline: undefined }, { ...CLEAN, forHeadline: undefined }, what + ": the verdict itself is unchanged");
}

// The two files agree on the names: answer to every question the builder asks.
const built = runBody({ json: { still_b64: JPEG } })[0].json.body;
const answered = Object.fromEntries(
  Object.entries(built.questions).map(([name, q]) => [name, q.type === "box" ? { type: "box", box: CLEAN_BOX, confidence: null } : { type: "noul", noul: 0.9 }]),
);
assert.deepEqual(verdict({ model: "jev-preview", answers: answered }), { jevThumbNote: null, jevThumbChecked: true, jevHeadlineBox: CLEAN_BOX });
assert.doesNotMatch(read("jev_thumb_check_verdict.js"), DASHES);
assert.doesNotMatch(read("jev_thumb_check_body.js"), DASHES);
assert.doesNotMatch(read("shim_thumbnail_to_binary.js"), DASHES);

// ---------------------------------------------------------------------------
// The Shim
// ---------------------------------------------------------------------------

const PLAN = { airtableId: "recTHUMB", headline: HEADLINE, query: "workflow dashboard", queryRaw: "workflow dashboard screen" };
const PICK = { airtableId: "recTHUMB", headline: HEADLINE, photoUsed: "https://images.pexels.com/photos/1/photo.jpeg", photographer: "A Photographer" };
const BIG = { thumbData: { bytes: 182345, fileName: "thumbnail.jpg", mimeType: "image/jpeg", fileExtension: "jpg" } };
const SMALL = { thumbData: { bytes: 9000, fileName: "thumbnail.jpg", mimeType: "image/jpeg", fileExtension: "jpg" } };
const NOBYTES = { thumbData: { fileName: "thumbnail.jpg", mimeType: "image/jpeg" } };
const SIZE_WARNING = "composed image is only 9000 bytes, which usually means the backdrop failed to decode";

// `verdictItems` undefined means the Jev: Thumb Verdict node did not run at all.
const runShim = (fn, { pick = PICK, binary, verdictItems } = {}) => {
  const nodes = { "Thumb: Plan": [{ json: PLAN }], "Thumb: Pick Still": [{ json: pick }] };
  if (verdictItems !== undefined) nodes["Jev: Thumb Verdict"] = verdictItems;
  return fn(dollar(nodes), { first: () => (binary ? { json: {}, binary } : { json: {} }) });
};
// The verdict names the headline its request was built for. PICK.headline is the
// same string, so a verdict item carrying FOR is this row's own, and the Shim
// takes it. The stale run guard further down is what happens without it.
const FOR = { forHeadline: HEADLINE };
const note = (jevThumbNote) => [{ json: { jevThumbNote, jevThumbChecked: true, jevHeadlineBox: null, ...FOR } }];
// The Jev fields of a verdict item, which is everything but forHeadline.
const found = ({ forHeadline, ...rest }) => rest;

const CASES = {
  "rendered, large file": { binary: BIG },
  "rendered, small file": { binary: SMALL },
  "rendered, no byte count": { binary: NOBYTES },
  "no still matched": { pick: { ...PICK, photoUsed: null }, binary: BIG },
  "no still matched, no image": { pick: { ...PICK, photoUsed: null } },
  "still downloaded, compositor returned no image": {},
};

// The sanity half: the export code does what the cases say, so equality below is not empty.
assert.equal(runShim(shimOld, CASES["rendered, large file"])[0].json.thumb_rendered, true);
assert.equal(runShim(shimOld, CASES["rendered, large file"])[0].json.thumb_warning, null);
assert.equal(runShim(shimOld, CASES["rendered, small file"])[0].json.thumb_warning, SIZE_WARNING);
assert.match(runShim(shimOld, CASES["no still matched"])[0].json.thumb_error, /^no Pexels still matched "workflow dashboard"/);
assert.match(runShim(shimOld, CASES["still downloaded, compositor returned no image"])[0].json.thumb_error, /^the still downloaded but the compositor returned no image\./);

// The Jev keys the Shim adds to a rendered thumbnail, in the order it adds them.
// Nothing else in the output may move, so each comparison below strips these
// four keys from the Shim and compares what is left with the export code.
const JEV_KEYS = ["jevThumbNote", "jevThumbChecked", "jevHeadlineBox", "jevApplied"];
const withoutWarning = ({ thumb_warning, ...rest }) => rest;
const stripJev = (items) => items.map(({ json, ...rest }) => {
  const kept = { ...json };
  for (const key of JEV_KEYS) delete kept[key];
  return { ...rest, json: kept };
});
const jevOf = (items) => Object.fromEntries(JEV_KEYS.map((key) => [key, items[0].json[key]]));
const NOTHING = { jevThumbNote: null, jevThumbChecked: false, jevHeadlineBox: null };
const RENDERED = ["rendered, large file", "rendered, small file", "rendered, no byte count"];
const NOT_MADE = ["no still matched", "no still matched, no image", "still downloaded, compositor returned no image"];

// A thumbnail that was never made is the export code's output to the byte, with
// no Jev key and no Jev line, whichever way JEV_APPLY is set and whatever a
// verdict says. Jev cannot have checked a frame that does not exist.
for (const label of NOT_MADE) {
  const want = runShim(shimOld, CASES[label]);
  for (const fn of [shimNew, shimOn]) {
    assert.deepEqual(runShim(fn, CASES[label]), want, label + ", no Jev node ran");
    assert.deepEqual(runShim(fn, { ...CASES[label], verdictItems: note(NOTE.absent) }), want, label + ", with a verdict");
  }
}

// No Jev node ran, or it ran and left nothing usable: thumb_warning and every
// other field are the export code's, and the Jev keys read "nothing found",
// with JEV_APPLY off and on. Only jevApplied tells the two apart.
for (const label of RENDERED) {
  const c = CASES[label];
  const want = runShim(shimOld, c);
  for (const [fn, applied] of [[shimNew, false], [shimOn, true]]) {
    const tag = label + ", JEV_APPLY " + applied;
    assert.deepEqual(stripJev(runShim(fn, c)), want, tag + ", no Jev node ran");
    assert.deepEqual(jevOf(runShim(fn, c)), { ...NOTHING, jevApplied: applied }, tag + ", no Jev node ran");
    assert.deepEqual(Object.keys(runShim(fn, c)[0].json).slice(-4), JEV_KEYS, tag + ", the four keys come last, in order");
    for (const [what, verdictItems] of [
      ["no items", []],
      ["a null note", note(null)],
      ["an empty note", note("")],
      ["a blank note", note("   ")],
      ["a note that is a number", note(42)],
      ["a note that is an array", note(["the headline touches the edge of the frame"])],
      ["a note that is an object", note({ text: "x" })],
      ["no note key", [{ json: { jevThumbChecked: false, ...FOR } }]],
      ["an item with no json", [{}]],
    ]) {
      const got = runShim(fn, { ...c, verdictItems });
      assert.deepEqual(stripJev(got), want, tag + ", verdict with " + what);
      assert.equal(got[0].json.jevThumbNote, null, tag + ", verdict with " + what);
      assert.equal(got[0].json.jevApplied, applied, tag + ", verdict with " + what);
    }
  }
}
// The image is carried through untouched.
assert.equal(runShim(shimNew, { binary: BIG })[0].binary, BIG);
assert.equal(runShim(shimOn, { binary: BIG })[0].binary, BIG);

// What the verdict node really returns, fed to the Shim, for each kind of answer.
// The check body ran for this row's headline, so each verdict carries it.
const fromVerdict = (json, headline = HEADLINE) => [{ json: verdictNode(verdictDollar(headline), { first: () => ({ json }) })[0].json }];
const VERDICTS = {
  clean: fromVerdict(response()),
  runsOff: fromVerdict(response({ box: { ...CLEAN_BOX, right: 0.8 } })),
  edge: fromVerdict(response({ box: { ...CLEAN_BOX, bottom: 0.99 } })),
  hard: fromVerdict(response({ readable: 0.2 })),
  absent: fromVerdict(response({ present: 0.1, box: { top: 0, bottom: 0, left: 0, right: 0 } })),
  unchecked: fromVerdict({ error: { message: "Request failed with status code 402" } }),
};
assert.equal(VERDICTS.runsOff[0].json.jevThumbNote, NOTE.runsOff);
assert.equal(VERDICTS.edge[0].json.jevThumbNote, NOTE.edge);
assert.equal(VERDICTS.hard[0].json.jevThumbNote, NOTE.hard);
assert.equal(VERDICTS.absent[0].json.jevThumbNote, NOTE.absent);

// SHADOW (JEV_APPLY false, as shipped): Jev's findings are recorded, and
// thumb_warning is exactly what the export code makes, with or without a note.
for (const label of RENDERED) {
  const want = runShim(shimOld, CASES[label]);
  for (const [name, verdictItems] of Object.entries(VERDICTS)) {
    const got = runShim(shimNew, { ...CASES[label], verdictItems });
    assert.deepEqual(stripJev(got), want, label + ", shadow, " + name + ": nothing but the Jev keys moves");
    assert.equal(got[0].json.thumb_warning, want[0].json.thumb_warning, label + ", shadow, " + name);
    assert.deepEqual(jevOf(got), { ...found(verdictItems[0].json), jevApplied: false }, label + ", shadow, " + name + ": recorded as found");
    assert.equal(got[0].binary, CASES[label].binary);
    assert.equal(got.length, 1);
  }
}
assert.deepEqual(jevOf(runShim(shimNew, { binary: BIG, verdictItems: VERDICTS.runsOff })), {
  jevThumbNote: NOTE.runsOff, jevThumbChecked: true, jevHeadlineBox: { ...CLEAN_BOX, right: 0.8 }, jevApplied: false,
});
assert.deepEqual(jevOf(runShim(shimNew, { binary: BIG, verdictItems: VERDICTS.absent })), {
  jevThumbNote: NOTE.absent, jevThumbChecked: true, jevHeadlineBox: null, jevApplied: false,
});
assert.deepEqual(jevOf(runShim(shimNew, { binary: SMALL, verdictItems: VERDICTS.clean })), {
  jevThumbNote: null, jevThumbChecked: true, jevHeadlineBox: CLEAN_BOX, jevApplied: false,
});
// The recorded note is trimmed, only the first verdict item is read, the box is a
// copy of its four edges, and a box that is not four finite numbers is dropped.
assert.equal(runShim(shimNew, { binary: BIG, verdictItems: note("  " + NOTE.edge + " ") })[0].json.jevThumbNote, NOTE.edge);
assert.equal(runShim(shimNew, { binary: BIG, verdictItems: [...note(NOTE.edge), ...note(NOTE.hard)] })[0].json.jevThumbNote, NOTE.edge);
const boxed = (jevHeadlineBox) => [{ json: { jevThumbNote: null, jevThumbChecked: true, jevHeadlineBox, ...FOR } }];
const copied = runShim(shimNew, { binary: BIG, verdictItems: boxed({ ...CLEAN_BOX, extra: 1 }) })[0].json.jevHeadlineBox;
assert.deepEqual(copied, CLEAN_BOX);
assert.deepEqual(Object.keys(copied), ["top", "bottom", "left", "right"]);
for (const bad of [null, undefined, "box", 7, [], { ...CLEAN_BOX, top: NaN }, { ...CLEAN_BOX, left: "0.05" }, { top: 0.1, bottom: 0.2, left: 0.3 }]) {
  assert.equal(runShim(shimNew, { binary: BIG, verdictItems: boxed(bad) })[0].json.jevHeadlineBox, null, JSON.stringify(bad));
}
// Checked is true only for the boolean true.
for (const checked of [false, "true", 1, null, undefined]) {
  const items = [{ json: { jevThumbNote: null, jevThumbChecked: checked, jevHeadlineBox: null, ...FOR } }];
  assert.equal(runShim(shimNew, { binary: BIG, verdictItems: items })[0].json.jevThumbChecked, false, String(checked));
}

// APPLIED (JEV_APPLY true, in a scratch copy): jevApplied is true, the same
// findings are recorded, and the note is appended to thumb_warning.
const runOn = (c, name) => runShim(shimOn, { ...c, verdictItems: VERDICTS[name] });
for (const label of RENDERED) {
  for (const name of Object.keys(VERDICTS)) {
    const got = runOn(CASES[label], name);
    const want = runShim(shimOld, CASES[label]);
    assert.equal(got[0].json.jevApplied, true, label + ", applied, " + name);
    assert.deepEqual(jevOf(got), { ...found(VERDICTS[name][0].json), jevApplied: true }, label + ", applied, " + name);
    // Whatever the warning says, no other field of the export moves.
    assert.deepEqual(stripJev(got).map(({ json }) => withoutWarning(json)), want.map(({ json }) => withoutWarning(json)), label + ", applied, " + name);
    assert.equal(got[0].binary, CASES[label].binary);
    assert.equal(got.length, 1);
  }
}
// Pinned strings. No verdict note names Jev and the Shim puts "Jev: " in front
// of the line, so the word appears once, joined notes included.
assert.equal(runOn({ binary: BIG }, "runsOff")[0].json.thumb_warning, "Jev: the headline runs off the dark panel onto the photograph");
assert.equal(runOn({ binary: BIG }, "edge")[0].json.thumb_warning, "Jev: the headline touches the edge of the frame");
assert.equal(runOn({ binary: BIG }, "hard")[0].json.thumb_warning, "Jev: the headline is hard to read at phone size");
assert.equal(runOn({ binary: BIG }, "absent")[0].json.thumb_warning, "Jev: the headline text was not found on the thumbnail");
for (const text of Object.values(NOTE)) assert.ok(!/Jev/.test(text), "no verdict note names Jev: " + text);
for (const name of ["runsOff", "edge", "hard", "absent"]) {
  assert.equal((runOn({ binary: BIG }, name)[0].json.thumb_warning.match(/Jev/g) || []).length, 1, name + ": the word Jev appears once");
}
// A clean frame and an unchecked one add nothing.
assert.equal(runOn({ binary: BIG }, "clean")[0].json.thumb_warning, null);
assert.equal(runOn({ binary: BIG }, "unchecked")[0].json.thumb_warning, null);
assert.equal(runOn({ binary: SMALL }, "clean")[0].json.thumb_warning, SIZE_WARNING);
// It comes after the size warning rather than replacing it, joined with "; ".
assert.equal(runOn({ binary: SMALL }, "edge")[0].json.thumb_warning, SIZE_WARNING + "; Jev: the headline touches the edge of the frame");
assert.equal(runOn({ binary: SMALL }, "absent")[0].json.thumb_warning, SIZE_WARNING + "; Jev: the headline text was not found on the thumbnail");
assert.equal(runOn({ binary: SMALL }, "hard")[0].json.thumb_warning, SIZE_WARNING + "; Jev: the headline is hard to read at phone size");
// Several notes joined by the verdict go in as one line under one prefix.
{
  const joined = runShim(shimOn, { binary: BIG, verdictItems: note(NOTE.runsOff + "; " + NOTE.hard) })[0].json.thumb_warning;
  assert.equal(joined, "Jev: " + NOTE.runsOff + "; " + NOTE.hard);
  assert.equal(joined.match(/Jev/g).length, 1, "a joined line names Jev once");
}
// The note is trimmed, and only the first verdict item is read.
assert.equal(runShim(shimOn, { binary: BIG, verdictItems: note("  " + NOTE.edge + " ") })[0].json.thumb_warning, "Jev: " + NOTE.edge);
assert.equal(
  runShim(shimOn, { binary: BIG, verdictItems: [...note(NOTE.edge), ...note(NOTE.hard)] })[0].json.thumb_warning,
  "Jev: " + NOTE.edge,
);

// ---- Stale run guard ----
// One Row at a Time is a Split In Batches loop. When a later row's Jev branch
// stops early (Jev: Thumb Check Body returns [] for a row with no usable frame
// or headline), $('Jev: Thumb Verdict').first() may hand the Shim an earlier
// row's verdict. That is unverified n8n behaviour, so the Shim does not rely on
// it: it takes a verdict only when forHeadline equals its own row's headline.
const OTHER = "STOP HIRING MANAGERS NOW";
assert.notEqual(OTHER, HEADLINE);
// What the verdict node returned for ANOTHER row's request, every kind of answer.
const STALE = {
  clean: fromVerdict(response(), OTHER),
  runsOff: fromVerdict(response({ box: { ...CLEAN_BOX, right: 0.8 } }), OTHER),
  edge: fromVerdict(response({ box: { ...CLEAN_BOX, bottom: 0.99 } }), OTHER),
  hard: fromVerdict(response({ readable: 0.2 }), OTHER),
  absent: fromVerdict(response({ present: 0.1 }), OTHER),
};
for (const [name, items] of Object.entries(STALE)) assert.equal(items[0].json.forHeadline, OTHER, name);
// Sanity: the same answers built for THIS row's headline are taken, so the cases
// below differ from these in the headline and nothing else.
for (const name of Object.keys(STALE)) {
  assert.deepEqual(found(STALE[name][0].json), found(VERDICTS[name][0].json), name + ": the same answers");
  assert.equal(runShim(shimOn, { binary: BIG, verdictItems: VERDICTS[name] })[0].json.jevThumbChecked, true, name + " is taken when it is this row's");
}
// A verdict for another headline records nothing and adds no note, with JEV_APPLY
// off and on (the flipped scratch copy): the output is the export code's, and the
// Jev keys read "nothing found".
for (const label of RENDERED) {
  const want = runShim(shimOld, CASES[label]);
  for (const [fn, applied] of [[shimNew, false], [shimOn, true]]) {
    for (const [name, verdictItems] of Object.entries(STALE)) {
      const got = runShim(fn, { ...CASES[label], verdictItems });
      const tag = label + ", JEV_APPLY " + applied + ", a " + name + " verdict for another headline";
      assert.deepEqual(stripJev(got), want, tag + ": the export code's output, thumb_warning included");
      assert.deepEqual(jevOf(got), { ...NOTHING, jevApplied: applied }, tag + ": nothing recorded");
      assert.equal(got[0].json.thumb_warning, want[0].json.thumb_warning, tag + ": no note");
      assert.equal(got[0].binary, CASES[label].binary);
    }
  }
}
assert.equal(runShim(shimOn, { binary: BIG, verdictItems: STALE.runsOff })[0].json.thumb_warning, null);
assert.equal(runShim(shimOn, { binary: SMALL, verdictItems: STALE.edge })[0].json.thumb_warning, SIZE_WARNING);
// The same verdict, built for the right headline, is taken and noted: nothing
// else about it differs.
assert.equal(
  runShim(shimOn, { binary: BIG, verdictItems: fromVerdict(response({ box: { ...CLEAN_BOX, right: 0.8 } }), HEADLINE) })[0].json.thumb_warning,
  "Jev: " + NOTE.runsOff,
);
// Only a string equal to the trimmed Pick Still headline counts. Anything else
// is absent, even with a note and checked true.
const withFor = (forHeadline) => [{ json: { jevThumbNote: NOTE.edge, jevThumbChecked: true, jevHeadlineBox: CLEAN_BOX, forHeadline } }];
for (const [what, forHeadline] of [
  ["another headline", OTHER],
  ["missing", undefined],
  ["null", null],
  ["an empty string", ""],
  ["a number", 42],
  ["an array holding the headline", [HEADLINE]],
  ["an object", { headline: HEADLINE }],
  ["the headline with a trailing space", HEADLINE + " "],
  ["the headline with a leading space", " " + HEADLINE],
  ["the headline in lower case", HEADLINE.toLowerCase()],
  ["a prefix of the headline", HEADLINE.slice(0, -1)],
]) {
  for (const fn of [shimNew, shimOn]) {
    const got = runShim(fn, { binary: BIG, verdictItems: withFor(forHeadline) });
    assert.deepEqual(jevOf(got), { ...NOTHING, jevApplied: fn === shimOn }, "forHeadline " + what);
    assert.equal(got[0].json.thumb_warning, null, "forHeadline " + what);
  }
}
{
  const taken = runShim(shimOn, { binary: BIG, verdictItems: withFor(HEADLINE) })[0].json;
  assert.equal(taken.thumb_warning, "Jev: " + NOTE.edge);
  assert.deepEqual(jevOf([{ json: taken }]), { jevThumbNote: NOTE.edge, jevThumbChecked: true, jevHeadlineBox: CLEAN_BOX, jevApplied: true });
}
// The Pick Still headline is trimmed before the comparison, as the request
// builder trims it, so a padded headline still matches the verdict built from it.
{
  const padded = { ...PICK, headline: "  " + HEADLINE + "\n" };
  const got = runShim(shimOn, { pick: padded, binary: BIG, verdictItems: withFor(HEADLINE) })[0].json;
  assert.equal(got.thumb_warning, "Jev: " + NOTE.edge);
  assert.equal(got.jevThumbChecked, true);
  // A verdict built for the padded text itself is not the trimmed headline.
  assert.equal(runShim(shimOn, { pick: padded, binary: BIG, verdictItems: withFor("  " + HEADLINE + "\n") })[0].json.jevThumbChecked, false);
}
// A row whose own headline differs from the stale verdict's is the loop case:
// the verdict is for row 1, the Shim is shaping row 2.
{
  const row2 = { ...PICK, headline: OTHER };
  const got = runShim(shimOn, { pick: row2, binary: BIG, verdictItems: VERDICTS.runsOff })[0].json;
  assert.equal(got.jevThumbChecked, false);
  assert.equal(got.jevThumbNote, null);
  assert.equal(got.thumb_warning, null);
  // The verdict for row 2's own headline is taken.
  assert.equal(runShim(shimOn, { pick: row2, binary: BIG, verdictItems: STALE.runsOff })[0].json.thumb_warning, "Jev: " + NOTE.runsOff);
}
// A Pick Still with no headline matches no verdict that names one.
for (const headline of [undefined, null, ""]) {
  assert.equal(runShim(shimOn, { pick: { ...PICK, headline }, binary: BIG, verdictItems: VERDICTS.runsOff })[0].json.jevThumbChecked, false, String(headline));
}

// The shim is the export code plus the Jev block, and nothing else, STRICTLY:
// take the Jev block out (it runs from its first comment line to the end of the
// file, and ends with `return result;`), turn `const result = [{` back into
// `return [{`, and what is left must EQUAL the export's jsCode, byte for byte.
// So a change to the export part of the Shim, one ordinary line anywhere in it,
// fails here whether or not any case above can see it.
const JEV_MARK = "\n// Jev's check of the composed frame";
const markAt = SHIM_SHIPPED.indexOf(JEV_MARK);
assert.ok(markAt > 0, "the Jev block starts at its first comment line");
assert.equal(SHIM_SHIPPED.indexOf(JEV_MARK, markAt + 1), -1, "and that comment line is there once");
const jevBlock = SHIM_SHIPPED.slice(markAt + 1);
assert.ok(jevBlock.endsWith("\nreturn result;\n"), "the Jev block ends with `return result;`");
const exportPart = SHIM_SHIPPED.slice(0, markAt + 1);
assert.ok(exportPart.endsWith("}];\n\n"), "one blank line sits between the export code and the Jev block");
const exportLines = exportPart.slice(0, -2).split("\n");
assert.equal(exportLines.filter((l) => l === "const result = [{").length, 1, "the export part declares result once");
assert.equal(exportLines.filter((l) => l === "return [{").length, 0, "and has no bare return of its own");
const unmirrored = exportLines.map((l) => (l === "const result = [{" ? "return [{" : l)).join("\n");
assert.equal(unmirrored, SHIM_EXPORT, "shim_thumbnail_to_binary.js is the exported Shim code plus the Jev block");
// JEV_APPLY is declared in the Jev block, beside a comment that says flipping
// it is a ruling for Tee, and the verdict lookup follows it.
assert.equal(jevBlock.match(/^const JEV_APPLY = false;$/gm).length, 1);
assert.equal(exportPart.includes("JEV_APPLY"), false, "JEV_APPLY is not in the export part");
const shimLines = SHIM_SHIPPED.split("\n");
const applyAt = shimLines.indexOf("const JEV_APPLY = false;");
assert.match(shimLines.slice(Math.max(0, applyAt - 12), applyAt).join("\n"), /flipping that is a ruling for Tee/);
assert.ok(shimLines.slice(applyAt).some((l) => l.includes("$('Jev: Thumb Verdict')")), "the verdict lookup follows JEV_APPLY");

// Plain ASCII in every file this check touches.
for (const file of ["jev_thumb_check_body.js", "jev_thumb_check_verdict.js", "shim_thumbnail_to_binary.js", "jev_thumb_check.test.mjs"]) {
  assert.doesNotMatch(read(file), /[^\x00-\x7f]/, file + " is plain ASCII");
}

console.log("Jev thumbnail check: every case behaves");
