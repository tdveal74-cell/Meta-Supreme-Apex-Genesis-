/**
 * Do the Jev image lanes work as one chain, and not only node by node?
 *
 *   node n8n/tqo-v5/jev_lanes_chain.test.mjs
 *
 * The lane tests (jev_broll_bodies, jev_thumb_rank, jev_thumb_check, build_movie)
 * each stub the node in front of the one they test. This test runs the real node
 * files one after another, every one fed the real output of the one before. Two
 * steps cannot run here because a Code node cannot do them, the HTTP fetch of a
 * still and the Extract From File that turns it into base64, so a small function
 * stands in for the pair: one output item per input item, same order, with
 * json.still_b64 holding the image. A fetch that fails leaves an item with no
 * still_b64, as n8n does with onError continueRegularOutput.
 *
 * What it pins is what no single-node test can see:
 *   - a score for a picture lands on the clip or photo that picture came from;
 *     on the b-roll side an earlier picture is dropped so the numbering shifts,
 *     and on the photo side the same case is left to jev_thumb_rank.test.mjs;
 *   - every request body meets the request rules in the TypeSafe images page
 *     (docs.typesafe.ai/images): each asset is referenced from state,
 *     instructions or criteria, its format is png, jpg or jpeg, its data is
 *     standard base64, the model is a jev model, and a box question gets a
 *     model that has Box;
 *   - with JEV_APPLY false the clips and the photo are the ones the code in the
 *     workflow export picks, and the Jev choice is only reported.
 *
 * Each synthetic picture carries its own identity inside its bytes, the url it
 * was fetched from, so a synthetic answer is chosen from the picture itself and
 * not from where the picture sits in a list. That is what lets the test tell a
 * score on the right clip from a score on the clip next to it.
 *
 * Not asserted, on purpose: the exact keys of a stills item, the contents of
 * thumb_warning and the wording of any note. Those are still being edited.
 * Nothing here touches a network, a database or n8n, and no TypeSafe key is
 * funded, so every answer below is written by hand from the documented shapes.
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const read = (rel) => readFileSync(new URL(rel, import.meta.url), "utf8");

// This file is plain ASCII, which rules out an em dash and an en dash.
assert.ok(readFileSync(new URL(import.meta.url)).every((b) => b < 128), "this test file is plain ASCII");
const DASHES = new RegExp("[" + String.fromCharCode(0x2013, 0x2014) + "]");

// ---- harness ------------------------------------------------------------------

// A Code node body, compiled the way sources_gate.test.mjs does it.
const body = (file, ...params) => new Function(...params, read("./" + file));
const brollStills = body("jev_broll_stills.js", "$", "$input");
const brollBodies = body("jev_broll_bodies.js", "$", "$input");
const thumbStills = body("jev_thumb_stills.js", "$", "$input");
const thumbBody = body("jev_thumb_body.js", "$", "$input");
const checkBody = body("jev_thumb_check_body.js", "$", "$input");
const checkVerdict = body("jev_thumb_check_verdict.js", "$", "$input");
const MOVIE_SRC = read("./build_movie.js");
const PICK_SRC = read("./thumb_pick_still.js");

// n8n's `$('Node')` throws when that node did not run, so an unknown name throws.
const dollar = (nodes) => (name) => {
  if (!Object.hasOwn(nodes, name)) throw new Error("Node '" + name + "' hasn't been executed");
  const items = nodes[name];
  return { all: () => items, first: () => items[0] };
};
const inputOf = (items) => ({ all: () => items, first: () => items[0] });
const noInput = inputOf([]);

// The unmodified code of the nodes the lanes change, read from the live export.
const EXPORT = JSON.parse(read("./exports/qEkGOUsNyVaRAmm6_active.json"));
const exportCode = (name) => {
  const hits = EXPORT.nodes.filter((n) => n.name === name);
  assert.equal(hits.length, 1, name + " is in the export once");
  return hits[0].parameters.jsCode;
};
const MOVIE_OLD = exportCode("Build Movie");
const PICK_OLD = exportCode("Thumb: Pick Still");

// The shadow flag, flipped in memory only. The files on disk are never touched.
const flip = (code) => {
  const on = code.replace("const JEV_APPLY = false;", "const JEV_APPLY = true;");
  assert.notEqual(on, code, "the file declares const JEV_APPLY = false;");
  return on;
};
const MOVIE_ON = flip(MOVIE_SRC);
const PICK_ON = flip(PICK_SRC);

// ---- synthetic pictures -------------------------------------------------------

// Real file magic bytes, so the prefix Jev nodes read is measured and not typed.
const JPEG_MAGIC = [0xff, 0xd8, 0xff, 0xe0, 0x00, 0x10, 0x4a, 0x46, 0x49, 0x46, 0x00, 0x01];
const PNG_MAGIC = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00, 0x00, 0x00, 0x0d];
// Magic bytes, then |tag| : the tag says which picture this is.
const fakeImage = (magic, tag) => Buffer.concat([Buffer.from(magic), Buffer.from("|" + tag + "|")]).toString("base64");
const tagOf = (b64) => {
  const m = /\|([^|]+)\|/.exec(Buffer.from(b64, "base64").toString("latin1"));
  assert.ok(m, "the picture carries its tag");
  return m[1];
};
assert.ok(fakeImage(JPEG_MAGIC, "x").startsWith("/9j/"));
assert.ok(fakeImage(PNG_MAGIC, "x").startsWith("iVBORw0KGgo"));

// Stands in for the HTTP fetch of each url plus Extract From File. `urlOf` reads
// the url the fetch node would request from the item before it.
const fetchAll = (items, urlOf, { fail = () => false, png = () => false } = {}) => items.map((it) =>
  fail(it.json)
    ? { json: { error: { message: "simulated fetch failure" } } }
    : { json: { still_b64: fakeImage(png(it.json) ? PNG_MAGIC : JPEG_MAGIC, urlOf(it.json)) } });

// ---- the request rules --------------------------------------------------------

const MODELS = ["jev-latest", "jev-preview", "jev-1.13.0", "jev-1.14.0"];
const BOX_MODELS = ["jev-preview", "jev-1.14.0"];   // box.md: Box needs Jev 1.14
const MAX_B64 = 20000000;
const strings = (v) => (typeof v === "string" ? [v]
  : Array.isArray(v) ? v.flatMap(strings)
  : v && typeof v === "object" ? Object.values(v).flatMap(strings) : []);   // values only: object keys are not replaced

const checkRequest = (b, { types }) => {
  assert.deepEqual(JSON.parse(JSON.stringify(b)), b, "the body survives JSON");
  assert.ok(MODELS.includes(b.model), "model is a jev model: " + b.model);
  assert.ok(b.state && typeof b.state === "object");
  const qs = Object.entries(b.questions);
  assert.ok(qs.length > 0, "at least one question");
  for (const [name, q] of qs) {
    assert.ok(types.includes(q.type), name + " is a " + q.type);
    assert.equal(typeof q.instructions, "string");
    assert.ok(q.instructions.length > 0);
    if (q.type === "score") assert.ok(Array.isArray(q.criteria) && q.criteria.length >= 2 && q.criteria.every((c) => typeof c === "string" && c), name + " has score criteria");
    // Noul criteria are optional in the docs; when they are sent they are true and false.
    if (q.type === "noul" && q.criteria !== undefined) assert.deepEqual(Object.keys(q.criteria).sort(), ["false", "true"], name);
    if (q.type === "box") assert.equal(q.criteria, undefined, name + ": box takes no criteria");
    // A name in backticks has to be a field of the state.
    for (const m of q.instructions.matchAll(/`([A-Za-z_][A-Za-z0-9_]*)`/g)) assert.ok(Object.hasOwn(b.state, m[1]), name + " names `" + m[1] + "`");
    assert.doesNotMatch(q.instructions + JSON.stringify(q.criteria), DASHES, name);
  }
  if (qs.some(([, q]) => q.type === "box")) {
    assert.ok(BOX_MODELS.includes(b.model), "a box question needs a model that has Box");
    assert.ok(qs.some(([, q]) => q.type === "noul"), "a box question is paired with a noul question");
  }
  const text = [...strings(b.state), ...qs.flatMap(([, q]) => [q.instructions, ...strings(q.criteria)])];
  const refs = Object.keys(b.assets);
  assert.ok(refs.length > 0, "at least one asset");
  let total = 0;
  for (const ref of refs) {
    assert.ok(ref.trim() && Buffer.byteLength(ref) <= 1024, "reference length");
    assert.ok(text.some((t) => t.includes(ref)), ref + " appears as text in state, instructions or criteria");
    for (const other of refs) if (other !== ref) assert.ok(!other.includes(ref), ref + " does not sit inside " + other);
    const a = b.assets[ref];
    assert.ok(Object.keys(a).every((k) => ["type", "part", "data_base64", "format"].includes(k)), ref + " has only documented fields");
    assert.ok(a.type === undefined || a.type === "image");
    assert.ok(["png", "jpg", "jpeg"].includes(a.format), ref + " format " + a.format);
    assert.equal(typeof a.data_base64, "string");
    assert.match(a.data_base64, /^[A-Za-z0-9+/]+={0,2}$/, ref + " is standard base64: no prefix, no whitespace");
    assert.equal(a.data_base64.length % 4, 0, ref + " is padded");
    assert.equal(Buffer.from(a.data_base64, "base64").toString("base64"), a.data_base64, ref + " round trips");
    const png = a.data_base64.startsWith("iVBORw0KGgo");
    assert.ok(png || a.data_base64.startsWith("/9j/"), ref + " is a PNG or a JPEG");
    assert.equal(a.format === "png", png, ref + " format agrees with the bytes");
    total += a.data_base64.length;
  }
  assert.ok(total <= MAX_B64, "base64 total is under the cap");
  // The other direction: a placeholder in the text with no asset behind it is a bug.
  for (const t of text) for (const ph of t.match(/<[A-Za-z0-9]+>/g) || []) assert.ok(ph in b.assets, ph + " has an asset");
};

const score = (n) => ({ type: "score", score: n, confidence: 0.9, legend: {}, probabilities: {} });

// ==============================================================================
// B-roll chain: Stills -> fetch -> Bodies -> (Jev) -> Build Movie
// ==============================================================================

const fixture = JSON.parse(read("./fixtures/pexels_video_search_2221.json"));
const videos = fixture.pexels.videos;
const exportCandidates = new Function(/function candidates\(resp\)\{[\s\S]*?\n\}/.exec(MOVIE_OLD)[0] + "\nreturn candidates;")();
// The clip link Build Movie takes from one Pexels video, by the export's own rule.
const linkOf = (v) => {
  const c = exportCandidates({ videos: [v] });
  assert.equal(c.length, 1);
  return c[0];
};
assert.equal(exportCandidates(fixture.pexels).length, 5, "the fixture offers five clips to Build Movie");
assert.equal(new Set(videos.map((v) => v.image)).size, 5, "each video has its own still");
const videoByStill = (url) => {
  const hit = videos.filter((v) => v.image === url);
  assert.equal(hit.length, 1, "a still url in the fixture: " + url);
  return hit[0];
};
const indexOfStill = (url) => videos.indexOf(videoByStill(url));

// Six segments. The first is the fixture's own segment. Segments 0 to 4 all get
// the real Pexels response, so Build Movie has to walk the candidates one clip
// at a time. Segment 5 gets a failed Pexels call and so has nothing to rank.
const NARRATION = [
  fixture.segment.narration,
  "Then we open the queue.",
  "Next the report goes out.",
  "There is a pause before the review.",
  "Last we close the loop.",
  "A beat that stock footage cannot fill.",
];
const SEGS = NARRATION.map((narration, i) => (i === 0 ? { json: structuredClone(fixture.segment) } : { json: { ...structuredClone(fixture.segment), segIndex: i, start: i * 8, duration: 8, narration } }));
const PX = [0, 1, 2, 3, 4].map(() => ({ json: structuredClone(fixture.pexels) })).concat([{ json: { error: { message: "simulated Pexels failure" } } }]);

// Runs the four nodes in order. `fail` takes a stills item and says whether its
// fetch fails.
const brollChain = (segs, px, { fail } = {}) => {
  const nodes = { "Plan B-Roll Segments": segs, "Pexels Search": px };
  const stills = brollStills(dollar(nodes), noInput);
  nodes["Jev: B-Roll Stills"] = stills;
  const fetched = fetchAll(stills, (j) => j.stillUrl, { fail });
  const bodies = brollBodies(dollar(nodes), inputOf(fetched));
  return { stills, fetched, bodies };
};

// One synthetic answer per body, for every question in it. The score is chosen
// from the picture sent under that question, by the index of its video.
const answerBroll = (bodies, scoreOf) => bodies.map((b) => {
  const { questions, assets } = b.json.body;
  const answers = {};
  for (const name of Object.keys(questions)) answers[name] = score(scoreOf(indexOfStill(tagOf(assets["<" + name + ">"].data_base64))));
  return { json: { model: "jev-1.13.0", answers, usage: { input_tokens: 1000, output_tokens: 10 } } };
});

const ROW = { rowId: "46", videoTitle: "The Middle Is the Target" };
const runMovie = (code, { segs, px, jev = {} }) => new Function("$", "$json", code)(
  dollar({ "Plan B-Roll Segments": segs, "Pexels Search": px, "Presenter: Attach Clips": [{ json: ROW }], ...jev }),
  { presenterClips: [] },
)[0].json;
const clips = (out) => out.j2vBody.scenes[0].elements.filter((e) => e.type === "video").map((e) => e.src);
// Every key the export's output has comes out the same. Extra keys are allowed.
const sameAsExport = (got, want, label) => { for (const k of Object.keys(want)) assert.deepEqual(got[k], want[k], label + ": " + k); };

// ---- stills ----

const chain = brollChain(SEGS, PX);
const bySeg = (items, i) => items.filter((it) => it.json.segIndex === i);
for (let i = 0; i < 5; i++) {
  const mine = bySeg(chain.stills, i);
  assert.equal(mine.length, 4, "segment " + i + " keeps K_BROLL = 4 clips");
  assert.deepEqual(mine.map((it) => it.json.cand), [1, 2, 3, 4]);
  // The clip is the one Build Movie's own rule takes from that video, in Pexels order.
  assert.deepEqual(mine.map((it) => it.json.link), videos.slice(0, 4).map(linkOf));
  assert.deepEqual(mine.map((it) => it.json.stillUrl), videos.slice(0, 4).map((v) => v.image));
}
assert.equal(bySeg(chain.stills, 5).length, 0, "a failed Pexels call adds no stills");
assert.equal(chain.stills.length, 20);
assert.equal(chain.fetched.length, chain.stills.length);

// ---- bodies ----

assert.deepEqual(chain.bodies.map((b) => b.json.segIndex), [0, 1, 2, 3, 4], "one body per segment that has a usable still");
chain.bodies.forEach((b) => {
  const { segIndex, links } = b.json;
  const names = Object.keys(b.json.body.questions);
  assert.deepEqual(names, links.map((_, n) => "s" + segIndex + "c" + (n + 1)), "questions are s{seg}c{k}, k from 1, one per link");
  assert.equal(Object.keys(b.json.body.assets).length, links.length);
  checkRequest(b.json.body, { types: ["score"] });
  assert.equal(b.json.body.state.sentence, NARRATION[segIndex], "the sentence is the segment's own narration");
  // The picture sent under question k belongs to the clip at links[k-1].
  names.forEach((name, n) => {
    const v = videoByStill(tagOf(b.json.body.assets["<" + name + ">"].data_base64));
    assert.equal(linkOf(v), links[n], name + " is asked about the picture of links[" + n + "]");
  });
});

// ---- scores into Build Movie ----

// Video 0 is scored 0.4 (under 1: demoted), video 1 is the best at 2.9, video 3
// is next, video 2 is 1.2, and video 4 sits past K_BROLL so nothing scored it.
const SCORES = [0.4, 2.9, 1.2, 2.2, undefined];
const ranks = answerBroll(chain.bodies, (idx) => SCORES[idx]);
assert.equal(ranks.length, 5);
const JEV = { "Jev: B-Roll Bodies": chain.bodies, "Jev: Rank B-Roll": ranks };
const FX = { segs: SEGS, px: PX };

const link = (...idx) => idx.map((i) => linkOf(videos[i]));
const old = runMovie(MOVIE_OLD, FX);
assert.deepEqual(clips(old), link(0, 1, 2, 3, 4, 4), "the export takes Pexels order and holds the last clip on the empty beat");
assert.equal(old.heldClips, 1);

// Shadow: the clips are the export's, whatever Jev said, and the report is Jev's.
const shadow = runMovie(MOVIE_SRC, { ...FX, jev: JEV });
assert.deepEqual(clips(shadow), clips(old));
sameAsExport(shadow, old, "shadow");
assert.equal(shadow.jevApplied, false);
assert.equal(shadow.jevRanked, 5, "jevRanked counts segments (20 candidates were scored, one segment had none)");
assert.equal(shadow.jevWouldChange, 2, "Jev would pick differently on segments 0 and 2: on 0 it prefers a later clip to Pexels' first, and on 2 its best clip is already used");

// Applied: every score landed on its own clip. Best first, then the clip nobody
// scored, then the clip scored under 1, and nothing is dropped.
const applied = runMovie(MOVIE_ON, { ...FX, jev: JEV });
assert.deepEqual(clips(applied), link(1, 3, 2, 4, 0, 0));
assert.equal(applied.jevApplied, true);
assert.equal(applied.jevRanked, 5);
assert.equal(applied.heldClips, 1);
assert.equal(applied.clipCount, old.clipCount);

// No Jev node ran: shadow and applied are both the export.
for (const code of [MOVIE_SRC, MOVIE_ON]) {
  const out = runMovie(code, FX);
  sameAsExport(out, old, "no Jev nodes");
  assert.equal(out.jevRanked, 0);
  assert.equal(out.jevWouldChange, 0);
}

// The links[k-1] pairing, one position at a time. One segment, the four clips
// asked about; each in turn is the only high score and has to be the clip chosen.
// Run again with the fetch of video 1 failing: the bodies node then asks three
// questions, s0c1 to s0c3, about videos 0, 2 and 3, so question k is no longer
// the cand number, and the score still has to land on the picture's own clip.
for (const dropped of [null, 1]) {
  const one = { segs: [SEGS[0]], px: [PX[0]] };
  const c = brollChain(one.segs, one.px, { fail: dropped === null ? undefined : (j) => videoByStill(j.stillUrl) === videos[dropped] });
  const kept = [0, 1, 2, 3].filter((i) => i !== dropped);
  assert.equal(c.bodies.length, 1);
  assert.deepEqual(c.bodies[0].json.links, kept.map((i) => linkOf(videos[i])), "only usable stills are asked about");
  assert.deepEqual(Object.keys(c.bodies[0].json.body.questions), kept.map((_, n) => "s0c" + (n + 1)));
  for (const top of kept) {
    const jev = { "Jev: B-Roll Bodies": c.bodies, "Jev: Rank B-Roll": answerBroll(c.bodies, (idx) => (idx === top ? 3 : 1)) };
    const label = "top video " + top + (dropped === null ? "" : " with video " + dropped + " dropped");
    assert.deepEqual(clips(runMovie(MOVIE_ON, { ...one, jev })), [linkOf(videos[top])], label);
    const shown = runMovie(MOVIE_SRC, { ...one, jev });
    assert.deepEqual(clips(shown), clips(runMovie(MOVIE_OLD, one)), label + " (shadow)");
    assert.equal(shown.jevRanked, 1, label);
    assert.equal(shown.jevWouldChange, top === 0 ? 0 : 1, label);
  }
}

// ==============================================================================
// Thumbnail chain: Stills -> fetch -> Body -> (Jev) -> Pick Still -> Check Body -> (Jev) -> Verdict
// ==============================================================================

// SYNTHETIC Pexels /v1/search response in the documented photo shape. No
// execution in retention ran Thumb: Find Still, so there is no real response to
// copy. Nothing below depends on it looking real: the export's own Pick Still
// code is run on the same stubs and the shipped file has to agree with it.
const photo = (id) => {
  const base = "https://images.pexels.com/photos/" + id + "/pexels-photo-" + id + ".jpeg";
  return {
    id, width: 4000, height: 2667,
    url: "https://www.pexels.com/photo/desk-" + id + "/",
    photographer: "Photographer " + id, photographer_url: "https://www.pexels.com/@p" + id, photographer_id: 9000 + id,
    avg_color: "#6E7A8A", liked: false, alt: "A desk by a window, photo " + id,
    src: {
      original: base,
      large2x: base + "?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940",
      large: base + "?auto=compress&cs=tinysrgb&h=650&w=940",
      medium: base + "?auto=compress&cs=tinysrgb&h=350",
      small: base + "?auto=compress&cs=tinysrgb&h=130",
      portrait: base + "?auto=compress&cs=tinysrgb&fit=crop&h=1200&w=800",
      landscape: base + "?auto=compress&cs=tinysrgb&fit=crop&h=627&w=1200",
      tiny: base + "?auto=compress&cs=tinysrgb&dpr=1&fit=crop&h=200&w=280",
    },
  };
};
const PHOTOS = [photo(1001), photo(1002), photo(1003)];
const [U1, U2, U3] = PHOTOS.map((p) => p.src.landscape);
const FIND = { page: 1, per_page: 3, photos: PHOTOS, total_results: 8000 };
const PLAN = {
  airtableId: "rec1", brand: "The Quiet Operator", kicker: "THE QUIET OPERATOR", headline: "THE MIDDLE IS THE TARGET",
  query: "professional desk window", queryRaw: "professional desk window evening", isNCO: false, show: "TQO",
};

// ---- stills, fetch, body ----

const tStills = thumbStills(dollar({ "Thumb: Find Still": [{ json: FIND }] }), noInput);
assert.deepEqual(tStills.map((it) => it.json.url), [U1, U2, U3], "the photos Pick Still considers, in order, by the url it draws");
// Photo 2 comes back as a PNG, so a format other than JPEG goes through the chain too.
const tFetched = fetchAll(tStills, (j) => j.url, { png: (j) => j.url === U2 });
const tBodies = thumbBody(dollar({ "Jev: Thumb Stills": tStills, "Thumb: Plan": [{ json: PLAN }] }), inputOf(tFetched));
assert.equal(tBodies.length, 1);
const tb = tBodies[0].json;
checkRequest(tb.body, { types: ["score"] });
assert.deepEqual(Object.keys(tb.body.questions), ["p1", "p2", "p3"]);
assert.equal(tb.body.state.subject, PLAN.queryRaw);
assert.equal(tb.body.state.headline, PLAN.headline);
assert.deepEqual(tb.body.assets["<p2>"].format, "png");
assert.deepEqual(tb.body.assets["<p1>"].format, "jpeg");
assert.deepEqual(tb.urls, [U1, U2, U3]);
// The picture under question p{k} is the photo at urls[k-1].
Object.keys(tb.body.questions).forEach((name, n) => assert.equal(tagOf(tb.body.assets["<" + name + ">"].data_base64), tb.urls[n], name));

// ---- Jev's answer, then Pick Still ----

// Photo 2 gets the top score of 2. The score is chosen from the picture's own
// url, not from its place in the list.
const SCORE_BY_URL = { [U1]: 1.4, [U2]: 2, [U3]: 1.1 };
const tAnswers = {};
for (const name of Object.keys(tb.body.questions)) tAnswers[name] = score(SCORE_BY_URL[tagOf(tb.body.assets["<" + name + ">"].data_base64)]);
const tRank = { json: { model: "jev-1.13.0", answers: tAnswers, usage: { input_tokens: 1000, output_tokens: 10 } } };

const runPick = (code, nodes) => new Function("$", "$json", code)(dollar({ "Thumb: Plan": [{ json: PLAN }], ...nodes }), FIND)[0].json;
const pickToday = runPick(PICK_OLD, {});
assert.equal(pickToday.photoUsed, U1, "today's pick is the first photo, so Jev's choice below is a real difference");
const JEV_THUMB = { "Jev: Thumb Body": tBodies, "Jev: Rank Stills": [tRank] };

const pickShadow = runPick(PICK_SRC, JEV_THUMB);
sameAsExport(pickShadow, pickToday, "Pick Still in shadow");
assert.equal(pickShadow.jevPick, U2);
assert.equal(pickShadow.jevApplied, false);
// Applied: the photo and its credit follow the score that landed on photo 2.
const pickApplied = runPick(PICK_ON, JEV_THUMB);
assert.equal(pickApplied.jevPick, U2);
assert.equal(pickApplied.jevApplied, true);
assert.equal(pickApplied.photoUsed, U2);
assert.equal(pickApplied.photographer, "Photographer 1002");
// No Jev node ran: the export's output, with nothing reported.
for (const code of [PICK_SRC, PICK_ON]) {
  const out = runPick(code, {});
  sameAsExport(out, pickToday, "Pick Still with no Jev nodes");
  assert.equal(out.jevPick, null);
}

// ---- the post-compose check ----

// Stands in for the 1280x720 frame Thumb: Compose draws, after Extract From File.
const COMPOSED = fakeImage(JPEG_MAGIC, "composed-thumbnail");
const checkOut = checkBody(dollar({ "Thumb: Pick Still": [{ json: pickShadow }] }), inputOf([{ json: { still_b64: COMPOSED } }]));
assert.equal(checkOut.length, 1);
const cb = checkOut[0].json.body;
checkRequest(cb, { types: ["noul", "box"] });
assert.equal(cb.model, "jev-preview", "the check has a box question, and Box needs Jev 1.14");
assert.equal(cb.state.headline, pickShadow.headline);
assert.equal(cb.assets["<thumb>"].data_base64, COMPOSED);
assert.ok(Object.values(cb.questions).some((q) => q.type === "box"));

// A synthetic answer to every question in the body, by type. The verdict reads
// the answers by the question names the body used, so a name that drifted
// between the two nodes shows here as a check that did not happen.
const answerCheck = (box, model = "jev-1.14.0") => ({
  json: {
    model,
    answers: Object.fromEntries(Object.entries(cb.questions).map(([name, q]) => [name, q.type === "box"
      ? { type: "box", box, confidence: 0.9 }
      : { type: "noul", noul: 0.95 }])),
    usage: { input_tokens: 1000, output_tokens: 20 },
  },
});
const verdictOf = (response) => {
  const out = checkVerdict(dollar({}), inputOf([response]));
  assert.equal(out.length, 1);
  for (const f of ["jevThumbNote", "jevThumbChecked", "jevHeadlineBox"]) assert.ok(f in out[0].json, f + " is returned");
  return out[0].json;
};

// The headline sits inside the dark panel (right edge under 0.594) and is clear of the edges.
const INSIDE = { top: 0.3, bottom: 0.62, left: 0.06, right: 0.55 };
let v = verdictOf(answerCheck(INSIDE));
assert.equal(v.jevThumbChecked, true);
assert.equal(v.jevThumbNote, null);
assert.deepEqual(v.jevHeadlineBox, INSIDE);
// The headline runs out past the panel: a note, as text, and the box reported.
const WIDE = { top: 0.3, bottom: 0.62, left: 0.06, right: 0.8 };
v = verdictOf(answerCheck(WIDE));
assert.equal(v.jevThumbChecked, true);
assert.equal(typeof v.jevThumbNote, "string");
assert.ok(v.jevThumbNote.length > 0);
assert.deepEqual(v.jevHeadlineBox, WIDE);
// A response from another model is ignored whole: not checked, no note, no box.
v = verdictOf(answerCheck(INSIDE, "gpt-5"));
assert.equal(v.jevThumbChecked, false);
assert.equal(v.jevThumbNote, null);
assert.equal(v.jevHeadlineBox, null);
// An error item in place of the response is the same.
v = verdictOf({ json: { error: { message: "402 Payment Required" } } });
assert.equal(v.jevThumbChecked, false);
assert.equal(v.jevThumbNote, null);
assert.equal(v.jevHeadlineBox, null);

console.log("Jev image lanes: the chains run end to end, scores land on their own pictures, shadow keeps today's choice");
