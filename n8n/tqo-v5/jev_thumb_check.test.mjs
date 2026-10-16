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
 * exports/qEkGOUsNyVaRAmm6_active.json, and every case where no Jev node ran
 * must give the same output as the export code, field for field. `$('X')`
 * throws when node X did not run, as it does in n8n, and the stub does too.
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
const exportCode = (name) => {
  const hits = EXPORT.nodes.filter((n) => n.name === name);
  assert.equal(hits.length, 1, name);
  return hits[0].parameters.jsCode;
};
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
    assert.equal(body.model, "jev-preview", "only jev-preview answers a box question");
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
assert.equal(body.model, "jev-preview");
assert.deepEqual(body.state, { headline: HEADLINE });
assert.deepEqual(Object.keys(body.questions), ["headline_present", "headline_box", "headline_readable"]);
assert.deepEqual(body.questions.headline_present.type, "noul");
assert.equal(body.questions.headline_present.instructions, "Does <thumb> show the words in `headline` as text on the image?");
assert.deepEqual(body.questions.headline_box, { type: "box", instructions: "The headline text on <thumb>, the words in `headline`" });
assert.equal(body.questions.headline_readable.type, "noul");
assert.equal(
  body.questions.headline_readable.instructions,
  "Is every word of the headline on <thumb> fully readable at phone size, with no letter cut off by the edge of the image?",
);
assert.deepEqual(body.assets, { "<thumb>": { type: "image", format: "jpeg", data_base64: JPEG } });

// A PNG goes out as a PNG; the headline in the state is the one Pick Still holds.
out = runBody({ json: { still_b64: PNG } }, { "Thumb: Pick Still": [{ json: { headline: "TWO WORDS", photoUsed: "u" } }] });
assert.equal(out[0].json.body.assets["<thumb>"].format, "png");
assert.deepEqual(out[0].json.body.state, { headline: "TWO WORDS" });
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
// on the dark panel, which ends at 760 of 1280 px.
const CLEAN_BOX = { top: 0.31, bottom: 0.62, left: 0.056, right: 0.55 };
// A key given as undefined stays undefined, so the bad cases below can use it.
const answers = (over = {}) => ({
  headline_present: { type: "noul", noul: "present" in over ? over.present : 0.97 },
  headline_box: { type: "box", box: "box" in over ? over.box : CLEAN_BOX, confidence: 0.8 },
  headline_readable: { type: "noul", noul: "readable" in over ? over.readable : 0.93 },
});
const response = (over = {}, model = "jev-preview") => ({ model, answers: answers(over), usage: { input_tokens: 1200 } });
// The verdict reads only its own input, so any other node throwing must not matter.
const verdictThrows = () => { throw new Error("the verdict reads only its input"); };
const runVerdict = (json) => verdictNode(verdictThrows, { first: () => (json === undefined ? undefined : { json }) });
const verdict = (json) => {
  const r = runVerdict(json);
  assert.equal(r.length, 1, "always one item");
  assert.deepEqual(Object.keys(r[0].json), ["jevThumbNote", "jevThumbChecked", "jevHeadlineBox"]);
  return r[0].json;
};
const NOTE = {
  absent: "Jev did not find the headline text on the thumbnail",
  runsOff: "the headline runs off the dark panel onto the photograph",
  edge: "the headline touches the edge of the frame",
  hard: "Jev reads the headline as hard to read at phone size",
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
// Only the box moved. The other two answers are still read when the headline is
// absent, so a bad readable or a bad present still ignores the whole response.
assert.deepEqual(verdict(response({ present: 0.1, readable: NaN })), UNCHECKED);
assert.deepEqual(verdict(response({ present: 0.1, readable: undefined })), UNCHECKED);
assert.deepEqual(verdict(response({ present: NaN, box: BAD_BOXES[0][1] })), UNCHECKED);
assert.deepEqual(verdict(response({ present: undefined, box: BAD_BOXES[0][1] })), UNCHECKED);
// A model that is not a jev- model is ignored first, whatever the answers hold.
assert.deepEqual(verdict(response({ present: 0.1, box: BAD_BOXES[0][1] }, "gpt-4o")), UNCHECKED);

// Each threshold, one step either side.
const withBox = (edit) => verdict(response({ box: { ...CLEAN_BOX, ...edit } }));
assert.equal(withBox({ right: 0.594 }).jevThumbNote, null);
assert.equal(withBox({ right: 0.595 }).jevThumbNote, NOTE.runsOff);
assert.equal(withBox({ right: 0.97 }).jevThumbNote, NOTE.runsOff);
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
// It never throws, even when reading its own input does.
assert.deepEqual(verdictNode(verdictThrows, { first: () => { throw new Error("boom"); } })[0].json, UNCHECKED);
assert.deepEqual(verdictNode(verdictThrows, {})[0].json, UNCHECKED);

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
const note = (jevThumbNote) => [{ json: { jevThumbNote, jevThumbChecked: true, jevHeadlineBox: null } }];

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
      ["no note key", [{ json: { jevThumbChecked: false } }]],
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
const fromVerdict = (json) => [{ json: verdictNode(verdictThrows, { first: () => ({ json }) })[0].json }];
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
    assert.deepEqual(jevOf(got), { ...verdictItems[0].json, jevApplied: false }, label + ", shadow, " + name + ": recorded as found");
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
const boxed = (jevHeadlineBox) => [{ json: { jevThumbNote: null, jevThumbChecked: true, jevHeadlineBox } }];
const copied = runShim(shimNew, { binary: BIG, verdictItems: boxed({ ...CLEAN_BOX, extra: 1 }) })[0].json.jevHeadlineBox;
assert.deepEqual(copied, CLEAN_BOX);
assert.deepEqual(Object.keys(copied), ["top", "bottom", "left", "right"]);
for (const bad of [null, undefined, "box", 7, [], { ...CLEAN_BOX, top: NaN }, { ...CLEAN_BOX, left: "0.05" }, { top: 0.1, bottom: 0.2, left: 0.3 }]) {
  assert.equal(runShim(shimNew, { binary: BIG, verdictItems: boxed(bad) })[0].json.jevHeadlineBox, null, JSON.stringify(bad));
}
// Checked is true only for the boolean true.
for (const checked of [false, "true", 1, null, undefined]) {
  const items = [{ json: { jevThumbNote: null, jevThumbChecked: checked, jevHeadlineBox: null } }];
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
    assert.deepEqual(jevOf(got), { ...VERDICTS[name][0].json, jevApplied: true }, label + ", applied, " + name);
    // Whatever the warning says, no other field of the export moves.
    assert.deepEqual(stripJev(got).map(({ json }) => withoutWarning(json)), want.map(({ json }) => withoutWarning(json)), label + ", applied, " + name);
    assert.equal(got[0].binary, CASES[label].binary);
    assert.equal(got.length, 1);
  }
}
// Pinned strings. A note that does not name Jev gets "Jev: " in front; the two
// notes that already open with the word keep it as their own and get no prefix,
// so the word Jev appears once in the line.
assert.equal(runOn({ binary: BIG }, "runsOff")[0].json.thumb_warning, "Jev: the headline runs off the dark panel onto the photograph");
assert.equal(runOn({ binary: BIG }, "edge")[0].json.thumb_warning, "Jev: the headline touches the edge of the frame");
assert.equal(runOn({ binary: BIG }, "hard")[0].json.thumb_warning, "Jev reads the headline as hard to read at phone size");
assert.equal(runOn({ binary: BIG }, "absent")[0].json.thumb_warning, "Jev did not find the headline text on the thumbnail");
assert.notEqual(runOn({ binary: BIG }, "absent")[0].json.thumb_warning, "Jev: " + NOTE.absent, "no doubled prefix");
for (const name of ["runsOff", "edge", "hard", "absent"]) {
  assert.equal((runOn({ binary: BIG }, name)[0].json.thumb_warning.match(/Jev/g) || []).length, 1, name + ": the word Jev appears once");
}
// A clean frame and an unchecked one add nothing.
assert.equal(runOn({ binary: BIG }, "clean")[0].json.thumb_warning, null);
assert.equal(runOn({ binary: BIG }, "unchecked")[0].json.thumb_warning, null);
assert.equal(runOn({ binary: SMALL }, "clean")[0].json.thumb_warning, SIZE_WARNING);
// It comes after the size warning rather than replacing it, joined with "; ".
assert.equal(runOn({ binary: SMALL }, "edge")[0].json.thumb_warning, SIZE_WARNING + "; Jev: the headline touches the edge of the frame");
assert.equal(runOn({ binary: SMALL }, "absent")[0].json.thumb_warning, SIZE_WARNING + "; Jev did not find the headline text on the thumbnail");
assert.equal(runOn({ binary: SMALL }, "hard")[0].json.thumb_warning, SIZE_WARNING + "; Jev reads the headline as hard to read at phone size");
// Several notes joined by the verdict go in as one line. The prefix test looks
// only at how the whole line starts, and every note keeps its own words, so a
// joined line that carries the hard to read note names Jev in that note too.
assert.equal(
  runShim(shimOn, { binary: BIG, verdictItems: note(NOTE.runsOff + "; " + NOTE.hard) })[0].json.thumb_warning,
  "Jev: " + NOTE.runsOff + "; " + NOTE.hard,
);
// The note is trimmed, and only the first verdict item is read.
assert.equal(runShim(shimOn, { binary: BIG, verdictItems: note("  " + NOTE.edge + " ") })[0].json.thumb_warning, "Jev: " + NOTE.edge);
assert.equal(
  runShim(shimOn, { binary: BIG, verdictItems: [...note(NOTE.edge), ...note(NOTE.hard)] })[0].json.thumb_warning,
  "Jev: " + NOTE.edge,
);

// The shim is the export code plus the Jev block: every line of the export
// appears in the shim in order, and the one line it rewrites is the final
// `return [{`, which now fills `result` so the Jev block can read it.
const exportLines = SHIM_EXPORT.split("\n");
assert.equal(exportLines.filter((l) => l === "return [{").length, 1);
const shimLines = SHIM_SHIPPED.split("\n");
let at = 0;
for (const line of exportLines.map((l) => (l === "return [{" ? "const result = [{" : l))) {
  at = shimLines.indexOf(line, at);
  assert.notEqual(at, -1, "export line missing or out of order: " + line);
  at += 1;
}
assert.ok(shimLines.slice(at).some((l) => l.includes("$('Jev: Thumb Verdict')")), "the Jev block follows the export code");
// JEV_APPLY is declared after the export code, beside a comment that says
// flipping it is a ruling for Tee.
const applyAt = shimLines.indexOf("const JEV_APPLY = false;");
assert.ok(applyAt >= at, "JEV_APPLY sits in the Jev block, after the export code");
assert.match(shimLines.slice(Math.max(0, applyAt - 12), applyAt).join("\n"), /flipping that is a ruling for Tee/);

// Plain ASCII in every file this check touches.
for (const file of ["jev_thumb_check_verdict.js", "shim_thumbnail_to_binary.js", "jev_thumb_check.test.mjs"]) {
  assert.doesNotMatch(read(file), /[^\x00-\x7f]/, file + " is plain ASCII");
}

console.log("Jev thumbnail check: every case behaves");
