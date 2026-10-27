/**
 * Do the two Jev b-roll nodes choose the same clips Build Movie would, ask Jev
 * the question the spec writes, and fail open on everything else?
 *
 *   node n8n/tqo-v5/jev_broll_bodies.test.mjs
 *
 * Jev: B-Roll Stills runs on the real Pexels response from execution 2221
 * (fixtures/pexels_video_search_2221.json, query "workflow dashboard screen"),
 * and its candidate rule is checked against candidates() read straight out of
 * the Build Movie node in the live export, so the two cannot drift apart
 * without this test going red. Jev: B-Roll Bodies runs on synthetic base64
 * built from real JPEG and PNG magic bytes, because the real stills are fetched
 * by a node this test cannot run. No network, no database.
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const read = (rel) => readFileSync(new URL(rel, import.meta.url), "utf8");
const stills = new Function("$", "$input", read("./jev_broll_stills.js"));
const bodies = new Function("$", "$input", read("./jev_broll_bodies.js"));

// n8n's `$('Node')` throws when that node did not run, so an unknown name throws.
const dollar = (nodes) => (name) => {
  if (!(name in nodes)) throw new Error("Node '" + name + "' hasn't been executed");
  const items = nodes[name];
  return { all: () => items, first: () => items[0] };
};
const item = (json) => ({ json });
const noInput = { all: () => [], first: () => undefined };

// ---------------------------------------------------------------------------
// Jev: B-Roll Stills, on the real fixture.
// ---------------------------------------------------------------------------

const fixture = JSON.parse(read("./fixtures/pexels_video_search_2221.json"));
const exported = JSON.parse(read("./exports/qEkGOUsNyVaRAmm6_active.json"));
const movieSource = exported.nodes.find((n) => n.name === "Build Movie").parameters.jsCode;
const exportCandidates = new Function(/function candidates\(resp\)\{[\s\S]*?\n\}/.exec(movieSource)[0] + "\nreturn candidates;")();

const runStills = (segs, px) => stills(dollar({ "Plan B-Roll Segments": segs, "Pexels Search": px }), noInput);

let out = runStills([item(fixture.segment)], [item(fixture.pexels)]);
const wanted = exportCandidates(fixture.pexels);
assert.equal(wanted.length, 5, "the fixture offers five clips to Build Movie");
assert.equal(out.length, 4, "K_BROLL keeps the first four");
assert.deepEqual(out.map((i) => i.json.segIndex), [0, 0, 0, 0]);
assert.deepEqual(out.map((i) => i.json.cand), [1, 2, 3, 4]);
// Same links as Build Movie's own candidates(), in the same order.
assert.deepEqual(out.map((i) => i.json.link), wanted.slice(0, 4));
assert.deepEqual(out.map((i) => i.json.videoId), fixture.pexels.videos.slice(0, 4).map((v) => v.id));
assert.deepEqual(out.map((i) => i.json.stillUrl), fixture.pexels.videos.slice(0, 4).map((v) => v.image));
// One value pinned by hand, so the check above cannot pass by both sides being wrong together.
assert.deepEqual(out[0].json, {
  segIndex: 0,
  cand: 1,
  link: "https://videos.pexels.com/video-files/7252674/7252674-hd_1920_1080_25fps.mp4",
  stillUrl: "https://images.pexels.com/videos/7252674/pexels-photo-7252674.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=630&w=1200",
  videoId: 7252674,
});
assert.ok(!out.some((i) => i.json.videoId === 33897540), "the fifth clip is past K_BROLL");
// Only these five keys leave the node.
assert.deepEqual(Object.keys(out[0].json), ["segIndex", "cand", "link", "stillUrl", "videoId"]);

// Several segments: segment order, then candidate order, and item i answers segment i.
// Segment 1 got a failed Pexels call (an error item, no videos) and adds nothing.
const seg = (i) => item({ ...fixture.segment, segIndex: i });
const two = { videos: fixture.pexels.videos.slice(3) };
out = runStills([seg(0), seg(1), seg(2)], [item(fixture.pexels), item({ error: { message: "timeout" } }), item(two)]);
assert.deepEqual(out.map((i) => [i.json.segIndex, i.json.cand]), [[0, 1], [0, 2], [0, 3], [0, 4], [2, 1], [2, 2]]);
assert.deepEqual(out.slice(4).map((i) => i.json.videoId), [2516162, 33897540]);

// The candidate rule is Build Movie's, including its odd corners: an mp4 file
// with no width is not a candidate, a video with no mp4 is skipped, and when
// every file is wider than 3840 the smallest is taken.
const vid = (id, files, image = "https://images.pexels.com/videos/" + id + "/x.jpeg") => ({ id, image, video_files: files });
const file = (width, tag, type = "video/mp4") => ({ file_type: type, width, link: "https://videos.pexels.com/" + tag + ".mp4" });
const corners = {
  videos: [
    vid(1, [file(640, "a-640"), file(1920, "a-1920"), file(null, "a-nowidth")]),
    vid(2, [file(1280, "b-webm", "video/webm")]),
    vid(3, [file(5000, "c-5000"), file(7680, "c-7680")]),
    vid(4, [{ file_type: "video/mp4", width: 1920 }]),
    vid(5, [file(1280, "e-1280")]),
  ],
};
out = runStills([seg(0)], [item(corners)]);
assert.deepEqual(out.map((i) => i.json.link), exportCandidates(corners));
assert.deepEqual(out.map((i) => i.json.link), [
  "https://videos.pexels.com/a-1920.mp4",
  "https://videos.pexels.com/c-5000.mp4",
  "https://videos.pexels.com/e-1280.mp4",
]);
assert.deepEqual(out.map((i) => i.json.cand), [1, 2, 3]);

// A video whose ONLY mp4 file has no width is not a candidate, whatever form the
// missing width takes (null, absent or 0), exactly as in Build Movie. The case
// above leaves its width-less file beside a usable one, so it cannot tell a rule
// that drops width-less files from one that keeps them; here nothing else is
// left to pick. A width-less mp4 next to a webm that has a width is the same
// case, since only mp4 files count. The clips that are skipped use up no place:
// the one usable clip is cand 1.
const noWidth = {
  videos: [
    vid(21, [file(null, "w-null")]),
    vid(22, [{ file_type: "video/mp4", link: "https://videos.pexels.com/w-absent.mp4" }]),
    vid(23, [file(0, "w-zero")]),
    vid(24, [file(undefined, "w-undefined")]),
    vid(25, [file(undefined, "w-mixed"), file(1280, "w-webm", "video/webm")]),
    vid(26, [file(1920, "w-ok")]),
  ],
};
assert.deepEqual(exportCandidates(noWidth), ["https://videos.pexels.com/w-ok.mp4"], "Build Movie skips every width-less only-mp4 video");
out = runStills([seg(0)], [item(noWidth)]);
assert.deepEqual(out.map((i) => i.json.link), exportCandidates(noWidth));
assert.deepEqual(out.map((i) => [i.json.cand, i.json.videoId, i.json.link]), [[1, 26, "https://videos.pexels.com/w-ok.mp4"]]);
// A response made only of such videos leaves the segment with nothing, and the branch stops.
out = runStills([seg(0)], [item({ videos: noWidth.videos.slice(0, 5) })]);
assert.deepEqual(out, []);

// A still that is not on the Pexels image host is never fetched, and it does not
// use up one of the four places: cand counts the clips that were kept.
const hosts = {
  videos: [
    vid(10, [file(1920, "h10")], "https://images.pexels.com.evil.example/x.jpeg"),
    vid(11, [file(1920, "h11")], "http://images.pexels.com/x.jpeg"),
    vid(12, [file(1920, "h12")], null),
    vid(13, [file(1920, "h13")], 42),
    vid(14, [file(1920, "h14")], "https://videos.pexels.com/x.jpeg"),
    vid(15, [file(1920, "h15")]),
    vid(16, [file(1920, "h16")]),
    vid(17, [file(1920, "h17")]),
    vid(18, [file(1920, "h18")]),
    vid(19, [file(1920, "h19")]),
  ],
};
out = runStills([seg(0)], [item(hosts)]);
assert.deepEqual(out.map((i) => i.json.videoId), [15, 16, 17, 18]);
assert.deepEqual(out.map((i) => i.json.cand), [1, 2, 3, 4]);

// Fail open. No candidates anywhere, a Pexels list shorter than the segments, a
// malformed video, and either node missing all give no items and no throw.
assert.deepEqual(runStills([seg(0)], [item({ videos: [] })]), []);
assert.deepEqual(runStills([seg(0)], [item({})]), []);
assert.deepEqual(runStills([seg(0), seg(1)], [item(fixture.pexels)]).map((i) => i.json.segIndex), [0, 0, 0, 0]);
assert.deepEqual(runStills([seg(0)], [item({ videos: [{ video_files: "x" }] })]), []);
// A null video throws inside candidates(), as it does in Build Movie, and the
// segment is left with no list; the segments after it still get theirs.
assert.deepEqual(runStills([seg(0), seg(1)], [item({ videos: [null, ...fixture.pexels.videos] }), item(fixture.pexels)]).map((i) => i.json.segIndex), [1, 1, 1, 1]);
assert.deepEqual(stills(dollar({ "Pexels Search": [item(fixture.pexels)] }), noInput), []);
assert.deepEqual(stills(dollar({ "Plan B-Roll Segments": [seg(0)] }), noInput), []);
assert.deepEqual(stills(dollar({}), noInput), []);
// The segments are not changed.
const before = JSON.stringify(fixture);
runStills([item(fixture.segment)], [item(fixture.pexels)]);
assert.equal(JSON.stringify(fixture), before);

// ---------------------------------------------------------------------------
// Jev: B-Roll Bodies, on synthetic base64 with real magic bytes.
// ---------------------------------------------------------------------------

const b64 = (magic, pad = 24) => Buffer.concat([Buffer.from(magic), Buffer.alloc(pad, 7)]).toString("base64");
const JPEG = b64([0xff, 0xd8, 0xff, 0xe0, 0x00, 0x10, 0x4a, 0x46, 0x49, 0x46]);
const PNG = b64([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00, 0x00, 0x00, 0x0d]);
const GIF = b64(Buffer.from("GIF89a"));
const WEBP = b64(Buffer.from("RIFF\x00\x00\x00\x00WEBPVP8 "));
assert.ok(JPEG.startsWith("/9j/") && PNG.startsWith("iVBORw0KGgo") && !GIF.startsWith("/9j/") && !GIF.startsWith("iVBORw0KGgo"));
const JPEG2 = b64([0xff, 0xd8, 0xff, 0xdb, 0x00, 0x43, 0x00], 40);
const PNG2 = b64([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00, 0x00, 0x00, 0x0d], 40);

const NARRATION = ["First we open the dashboard.", "Then we check the queue.", "Last we send the report."];
const segments = NARRATION.map((narration, i) => item({ segIndex: i, narration, start: i * 8, duration: 8, query: "q" + i }));
const still = (segIndex, cand) => item({ segIndex, cand, link: "https://videos.pexels.com/s" + segIndex + "c" + cand + ".mp4", stillUrl: "https://images.pexels.com/s" + segIndex + "c" + cand + ".jpeg", videoId: segIndex * 10 + cand });
const fetched = (v) => item(typeof v === "object" && v !== null ? v : { still_b64: v });

const runBodies = (stillItems, extracted, segs = segments) =>
  bodies(dollar({ "Jev: B-Roll Stills": stillItems, "Plan B-Roll Segments": segs }), { all: () => extracted, first: () => extracted[0] });

const CRITERIA = [
  "Unusable as b-roll: mostly black or blank, blurred, or carrying a watermark, a logo or large text",
  "A clean, usable shot about something other than the sentence",
  "A clean shot that fits the general topic of the sentence",
  "A clean shot that clearly shows what the sentence describes",
];
const ask = (name) => "How well does <" + name + "> work as b-roll on screen while a narrator says the sentence in `sentence`?";

// Segment 0: a JPEG, a GIF that must be skipped, and a PNG. Segment 1: two error
// items. Segment 2: one JPEG. So two requests come out, in segment order.
const inputs = [still(0, 1), still(0, 2), still(0, 3), still(1, 1), still(1, 2), still(2, 1)];
const extracted = [fetched(JPEG), fetched(GIF), fetched(PNG), fetched({ error: "fetch failed" }), fetched({ error: { message: "x" } }), fetched(JPEG2)];
out = runBodies(inputs, extracted);
assert.equal(out.length, 2);
assert.deepEqual(out.map((i) => i.json.segIndex), [0, 2]);
assert.deepEqual(Object.keys(out[0].json), ["segIndex", "links", "body"]);

// Segment 0: the GIF is gone, and the questions are numbered over what is left,
// so s0c2 is the PNG and scores links[1], which is the third clip.
const first = out[0].json;
assert.deepEqual(first.links, ["https://videos.pexels.com/s0c1.mp4", "https://videos.pexels.com/s0c3.mp4"]);
assert.equal(first.body.model, "jev-1.14.0", "pinned, ruled 2026-10-27");
assert.deepEqual(first.body.state, { sentence: "First we open the dashboard." });
assert.deepEqual(Object.keys(first.body.questions), ["s0c1", "s0c2"]);
assert.deepEqual(first.body.questions.s0c1, { type: "score", instructions: ask("s0c1"), criteria: CRITERIA });
assert.deepEqual(first.body.questions.s0c2, { type: "score", instructions: ask("s0c2"), criteria: CRITERIA });
assert.deepEqual(first.body.assets, {
  "<s0c1>": { type: "image", format: "jpeg", data_base64: JPEG },
  "<s0c2>": { type: "image", format: "png", data_base64: PNG },
});
assert.deepEqual(Object.keys(first.body), ["model", "state", "questions", "assets"]);

// The four levels are told apart, one dimension each beyond the unusable one
// (score.md: each level is judged on its own, so describe them distinctly). Level
// 0 is about the picture alone and no longer says "unrelated", which level 1
// covers; the three above it climb from off topic to on topic to clearly shown.
const levels = first.body.questions.s0c1.criteria;
assert.equal(levels.length, 4);
assert.equal(new Set(levels).size, 4, "no two levels read alike");
assert.ok(!/unrelated|sentence|relate/i.test(levels[0]), "level 0 is about the picture alone: " + levels[0]);
assert.match(levels[1], /other than the sentence/);
assert.match(levels[2], /fits the general topic of the sentence/);
assert.match(levels[3], /clearly shows what the sentence describes/);
assert.ok(levels.slice(1).every((l) => l.startsWith("A clean")), "levels 1 to 3 all start from a clean shot");

// Segment 2 carries its own sentence and its own numbering from 1.
const last = out[1].json;
assert.deepEqual(last.links, ["https://videos.pexels.com/s2c1.mp4"]);
assert.deepEqual(last.body.state, { sentence: "Last we send the report." });
assert.deepEqual(Object.keys(last.body.questions), ["s2c1"]);
assert.deepEqual(last.body.assets, { "<s2c1>": { type: "image", format: "jpeg", data_base64: JPEG2 } });

// Every request is a plain JSON body, every asset is referenced from a question
// (TypeSafe refuses an asset nothing refers to), and every link has a question.
for (const o of out) {
  const body = JSON.parse(JSON.stringify(o.json.body));
  assert.deepEqual(body, o.json.body);
  for (const ref of Object.keys(body.assets)) {
    assert.ok(Object.values(body.questions).some((q) => q.instructions.includes(ref)), ref + " is never referenced");
  }
  assert.equal(Object.keys(body.questions).length, o.json.links.length);
  assert.equal(Object.keys(body.assets).length, o.json.links.length);
  for (const f of Object.values(body.assets).map((a) => a.format)) assert.ok(f === "jpeg" || f === "png");
}

// Build Movie reads the answer to s{segIndex}c{k} as links[k-1]. Prove the two
// agree in the hole case: the PNG is the third clip and answers s0c2.
const name = Object.keys(first.body.questions)[1];
assert.equal(first.links[Number(name.split("c")[1]) - 1], "https://videos.pexels.com/s0c3.mp4");

// Only JPEG and PNG are usable. A GIF, a WebP, a data URL, a bare error page, an
// empty string, a missing field and a non-string are skipped; nothing is emitted
// when no still in a segment survives.
const junkJson = [
  { still_b64: GIF },
  { still_b64: WEBP },
  { still_b64: "data:image/jpeg;base64," + JPEG },
  { still_b64: Buffer.from("<html>404</html>").toString("base64") },
  { still_b64: "" },
  { other: 1 },
  { still_b64: 12 },
  { still_b64: null },
];
out = runBodies(junkJson.map((_, n) => still(0, n + 1)), junkJson.map(item));
assert.deepEqual(out, []);
out = runBodies(junkJson.concat([{ still_b64: PNG }]).map((_, n) => still(0, n + 1)), junkJson.concat([{ still_b64: PNG }]).map(item));
assert.deepEqual(out.map((i) => i.json.links), [["https://videos.pexels.com/s0c9.mp4"]]);
assert.deepEqual(Object.keys(out[0].json.body.questions), ["s0c1"]);

// Unequal lengths fail open, in both directions: position no longer pairs them.
assert.deepEqual(runBodies(inputs, extracted.slice(0, 5)), []);
assert.deepEqual(runBodies(inputs.slice(0, 5), extracted), []);
assert.deepEqual(runBodies([], []), []);

// A segment with no sentence is left out, and so is a still whose segment is not in the plan.
out = runBodies([still(0, 1), still(1, 1), still(7, 1)], [fetched(JPEG), fetched(PNG), fetched(JPEG2)], [segments[0], item({ segIndex: 1, narration: "   " }), segments[2]]);
assert.deepEqual(out.map((i) => i.json.segIndex), [0]);

// A malformed stills item is skipped without costing the others.
out = runBodies([item({ segIndex: 0, link: "" }), item({ segIndex: "0", link: "https://videos.pexels.com/x.mp4" }), item({}), still(2, 1)], [fetched(JPEG), fetched(JPEG), fetched(JPEG), fetched(PNG)]);
assert.deepEqual(out.map((i) => i.json.segIndex), [2]);

// Either upstream node missing gives no output and no throw.
assert.deepEqual(bodies(dollar({ "Plan B-Roll Segments": segments }), { all: () => [] }), []);
assert.deepEqual(bodies(dollar({ "Jev: B-Roll Stills": inputs }), { all: () => extracted }), []);
assert.deepEqual(bodies(dollar({}), { all: () => [] }), []);
assert.deepEqual(bodies(dollar({ "Jev: B-Roll Stills": inputs, "Plan B-Roll Segments": segments }), undefined), []);

// One request body holds at most 20,000,000 base64 characters. The later stills,
// which Pexels ranked lower, are the ones dropped.
const big = (magic, n) => magic + "A".repeat(n - magic.length);
const bigA = big("/9j/", 12000000);
const bigB = big("iVBORw0KGgo", 8000000);
const bigC = big("/9j/", 100);
out = runBodies([still(0, 1), still(0, 2), still(0, 3)], [fetched(bigA), fetched(bigB), fetched(bigC)]);
assert.deepEqual(out[0].json.links, ["https://videos.pexels.com/s0c1.mp4", "https://videos.pexels.com/s0c2.mp4"], "12M + 8M is exactly the cap, so the third is the one dropped");
assert.equal(Object.keys(out[0].json.body.assets).length, 2);
out = runBodies([still(0, 1), still(0, 2)], [fetched(bigA), fetched(big("/9j/", 8000001))]);
assert.deepEqual(out[0].json.links, ["https://videos.pexels.com/s0c1.mp4"], "one character over the cap drops the later still");
assert.deepEqual(runBodies([still(0, 1)], [fetched(big("/9j/", 20000001))]), [], "a single still over the cap leaves nothing to ask about");
// The cap stops at the FIRST still that would push the total past it, and no
// later still is kept, even one small enough to fit (break, not skip). Here 12M
// then 9M reaches 21M, so the second is refused, and the 100 character third
// would fit beside the first (12,000,100) but is ranked below the refused one,
// so it must not be asked about either.
const bigD = big("/9j/", 9000000);
out = runBodies([still(0, 1), still(0, 2), still(0, 3)], [fetched(bigA), fetched(bigD), fetched(bigC)]);
assert.equal(out.length, 1);
assert.deepEqual(out[0].json.links, ["https://videos.pexels.com/s0c1.mp4"], "only the first survives: the small third still is not kept past the refused second");
assert.deepEqual(Object.keys(out[0].json.body.questions), ["s0c1"]);
assert.deepEqual(Object.keys(out[0].json.body.assets), ["<s0c1>"]);

// A bad segment skips only itself. Both guards that leave a segment out, a blank
// sentence and no still left under the cap, are a continue, so a bad segment in
// the MIDDLE must not take the good one after it down with it (a break there
// would). The good segment after it gets its own request, with its own sentence.
const trio = [still(0, 1), still(1, 1), still(2, 1)];
const trioPics = [fetched(JPEG), fetched(PNG), fetched(JPEG2)];
for (const blank of [item({ segIndex: 1, narration: "   " }), item({ segIndex: 1, narration: "" }), item({ segIndex: 1 }), item({ segIndex: 1, narration: 7 })]) {
  out = runBodies(trio, trioPics, [segments[0], blank, segments[2]]);
  assert.deepEqual(out.map((i) => i.json.segIndex), [0, 2], "a blank sentence in the middle: " + JSON.stringify(blank.json));
  assert.deepEqual(out[1].json.links, ["https://videos.pexels.com/s2c1.mp4"]);
  assert.deepEqual(out[1].json.body.state, { sentence: "Last we send the report." });
}
out = runBodies(trio, trioPics, [item({ segIndex: 0, narration: " " }), segments[1], segments[2]]);
assert.deepEqual(out.map((i) => i.json.segIndex), [1, 2], "a blank sentence first");
// No still left under the cap: the middle segment's only still is over it on its own.
out = runBodies(trio, [fetched(JPEG), fetched(big("/9j/", 20000001)), fetched(JPEG2)]);
assert.deepEqual(out.map((i) => i.json.segIndex), [0, 2], "an over-cap segment in the middle");
assert.deepEqual(out[1].json.links, ["https://videos.pexels.com/s2c1.mp4"]);
assert.deepEqual(out[1].json.body.state, { sentence: "Last we send the report." });
assert.deepEqual(Object.keys(out[1].json.body.assets), ["<s2c1>"]);
out = runBodies(trio, [fetched(big("/9j/", 20000001)), fetched(PNG), fetched(JPEG2)]);
assert.deepEqual(out.map((i) => i.json.segIndex), [1, 2], "an over-cap segment first");

// Each question holds its own criteria array. A body that shared one array would
// let a change to one question's levels reach every other question in the same
// request and in the other requests.
out = runBodies(inputs, extracted);
const levelsA = out[0].json.body.questions.s0c1.criteria;
const levelsB = out[0].json.body.questions.s0c2.criteria;
const levelsC = out[1].json.body.questions.s2c1.criteria;
assert.notEqual(levelsA, levelsB, "two questions in one request do not share an array");
assert.notEqual(levelsA, levelsC, "two requests do not share an array");
levelsA[0] = "changed in place";
levelsA.push("an extra level");
assert.deepEqual(levelsB, CRITERIA, "changing s0c1 leaves s0c2 as it was");
assert.deepEqual(levelsC, CRITERIA, "changing s0c1 leaves the other request as it was");
assert.deepEqual(runBodies(inputs, extracted)[0].json.body.questions.s0c1.criteria, CRITERIA, "and the next run starts from the original");

// Image size. TypeSafe rejects a PNG or JPEG under 280 or over 1568 pixels on a
// side (images.md, Limits; both ends are in), never resizes it, and one rejected
// image fails the whole request. The node reads width and height from the first
// bytes: a PNG IHDR, or the first JPEG frame header. Headers are built here, not
// typed, so the numbers a case claims are the numbers in its bytes.
const be16 = (n) => [(n >>> 8) & 255, n & 255];
const be32 = (n) => [(n >>> 24) & 255, (n >>> 16) & 255, (n >>> 8) & 255, n & 255];
const toB64 = (bytes, tail = 0) => Buffer.concat([Buffer.from(bytes), Buffer.alloc(tail, 7)]).toString("base64");
const PNG_SIG = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];
const IHDR = [0x49, 0x48, 0x44, 0x52];
// Signature, IHDR (length 13, name, width, height, depth 8, colour type 2, three zero bytes), its CRC, then the start of the next chunk.
const pngBytes = (w, h) => [...PNG_SIG, 0, 0, 0, 13, ...IHDR, ...be32(w), ...be32(h), 8, 2, 0, 0, 0, 1, 2, 3, 4, 0, 0, 0, 0, 0x49, 0x44, 0x41, 0x54];
const pngOf = (w, h, tail) => toB64(pngBytes(w, h), tail);
const JFIF = [0xff, 0xe0, 0x00, 0x10, 0x4a, 0x46, 0x49, 0x46, 0x00, 0x01, 0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00];
// A frame header: marker, length 17, depth 8, height, width, three components.
const sof = (code, w, h) => [0xff, code, 0x00, 0x11, 0x08, ...be16(h), ...be16(w), 0x03, 0x01, 0x22, 0x00, 0x02, 0x11, 0x01, 0x03, 0x11, 0x01];
// A segment of 16 bytes that is not a frame header, filled with one value, so a reader that took it for one would read that value as a size.
const table = (code, fill) => [0xff, code, 0x00, 0x12, ...new Array(16).fill(fill)];
const SOS = [0xff, 0xda, 0x00, 0x0c, 0x03, 0x01, 0x00, 0x02, 0x11, 0x03, 0x11, 0x00, 0x3f, 0x00];
const jpegBytes = (w, h, { code = 0xc0, before = [] } = {}) => [0xff, 0xd8, ...JFIF, ...before, ...sof(code, w, h), ...SOS, 1, 2, 3, 4];
const jpegOf = (w, h, opts, tail) => toB64(jpegBytes(w, h, opts), tail);
assert.ok(jpegOf(640, 480).startsWith("/9j/") && pngOf(640, 480).startsWith("iVBORw0KGgo"), "the headers are read as a JPEG and a PNG");

// The cand numbers of the stills the node keeps, out of the given stills in one segment.
const keeps = (...pics) => {
  const r = runBodies(pics.map((_, n) => still(0, n + 1)), pics.map((p) => fetched(p)));
  return r.length ? r[0].json.links.map((l) => Number(/c(\d+)\.mp4$/.exec(l)[1])) : [];
};

// In limits are kept: the real b-roll size, and both ends of both ranges.
for (const [w, h] of [[1200, 630], [640, 480], [280, 280], [1568, 1568], [280, 1568], [1568, 280]]) {
  assert.deepEqual(keeps(pngOf(w, h)), [1], "png " + w + "x" + h + " is in limits");
  assert.deepEqual(keeps(jpegOf(w, h)), [1], "jpeg " + w + "x" + h + " is in limits");
}
// Under 280 or over 1568 on either side is skipped, in either format.
for (const [w, h] of [[279, 400], [400, 279], [100, 100], [1, 1], [1569, 400], [400, 1569], [1569, 1569], [4000, 3000]]) {
  assert.deepEqual(keeps(pngOf(w, h)), [], "png " + w + "x" + h + " is out of limits");
  assert.deepEqual(keeps(jpegOf(w, h)), [], "jpeg " + w + "x" + h + " is out of limits");
}
// Every JPEG frame header marker is read: baseline, extended, progressive, lossless, differential and arithmetic.
for (const code of [0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf]) {
  assert.deepEqual(keeps(jpegOf(640, 480, { code })), [1], "SOF 0x" + code.toString(16) + " in limits");
  assert.deepEqual(keeps(jpegOf(100, 100, { code })), [], "SOF 0x" + code.toString(16) + " out of limits");
}
// 0xC4, 0xCC and 0xC8 are tables and a reserved code, not frame headers. Filled with 1 a table reads as 257 by 257, which would
// skip a good picture; filled with 2 it reads as 514 by 514, which would keep a bad one. Neither may happen.
for (const code of [0xc4, 0xcc, 0xc8]) {
  assert.deepEqual(keeps(jpegOf(640, 480, { before: table(code, 1) })), [1], "0x" + code.toString(16) + " is not a frame header (small fill)");
  assert.deepEqual(keeps(jpegOf(100, 100, { before: table(code, 2) })), [], "0x" + code.toString(16) + " is not a frame header (large fill)");
}
assert.deepEqual(keeps(jpegOf(100, 100, { before: [...table(0xc4, 2), ...table(0xcc, 2), ...table(0xc8, 2)] })), [], "all three, then the real header");
// Fill bytes before a marker and a marker with no length are stepped over.
assert.deepEqual(keeps(jpegOf(100, 100, { before: [0xff, 0x01, 0xff, 0xff] })), [], "fill and a no length marker, then a header out of limits");
assert.deepEqual(keeps(jpegOf(640, 480, { before: [0xff, 0x01, 0xff, 0xff] })), [1], "fill and a no length marker, then a header in limits");
// A big still is read from its head only: the tail is never needed.
assert.deepEqual(keeps(pngOf(100, 100, 3000000)), [], "a 4 MB png out of limits");
assert.deepEqual(keeps(jpegOf(640, 480, {}, 3000000)), [1], "a 4 MB jpeg in limits");

// A size that cannot be read is kept, whatever it might have been: the check fails
// open to today. Each of these carries a header that WOULD be out of limits if it
// were read, so a kept still here is a size that was not read, not a size that fit.
const unreadable = {
  "a jpeg with magic bytes and no header": JPEG,
  "a png with magic bytes and no header": PNG,
  "a png whose first chunk is not IHDR": toB64([...PNG_SIG, 0, 0, 0, 13, 0x49, 0x44, 0x41, 0x54, ...be32(100), ...be32(100), 8, 2, 0, 0, 0]),
  "a png cut off inside IHDR": toB64(pngBytes(100, 100).slice(0, 20)),
  "a png cut off after the name": toB64(pngBytes(100, 100).slice(0, 16)),
  "a jpeg cut off after the first segment": toB64([0xff, 0xd8, ...JFIF]),
  "a jpeg cut off inside the frame header": toB64([0xff, 0xd8, ...JFIF, ...sof(0xc0, 100, 100).slice(0, 8)]),
  "a jpeg that reaches the scan before any frame header": toB64([0xff, 0xd8, ...JFIF, ...SOS, ...sof(0xc0, 100, 100)]),
  "a jpeg with a stuffed zero where a marker should be": toB64([0xff, 0xd8, ...JFIF, 0xff, 0x00, ...sof(0xc0, 100, 100)]),
  "a jpeg whose next segment has length 0": toB64([0xff, 0xd8, ...JFIF, 0xff, 0xe1, 0x00, 0x00, ...sof(0xc0, 100, 100)]),
  "a jpeg whose next segment has no marker byte": toB64([0xff, 0xd8, ...JFIF, 0x07, ...sof(0xc0, 100, 100)]),
  "a jpeg that ends at the end marker": toB64([0xff, 0xd8, ...JFIF, 0xff, 0xd9, ...sof(0xc0, 100, 100)]),
  "a png with a zero width": pngOf(0, 100),
  "a png with a zero height": pngOf(100, 0),
  "a jpeg with a zero height (defined later)": jpegOf(100, 0),
  "a jpeg with a zero width": jpegOf(0, 100),
  "a png that is not base64 after the magic": "iVBORw0KGgo@@@@@@@@",
  "a jpeg that is not base64 after the magic": "/9j/@@@@@@@@",
};
for (const [what, pic] of Object.entries(unreadable)) assert.deepEqual(keeps(pic), [1], what + " is kept");
// Only the first 65,536 base64 characters are decoded, which is 49,152 bytes. A
// frame header that needs bytes past that is not found and the still is kept; one
// that ends on the last byte decoded is found. The header here is 100 by 100, so
// kept means not read and skipped means read. It needs nine bytes from its marker.
const withHeaderAt = (offset) => toB64([0xff, 0xd8, ...JFIF, 0xff, 0xe1, ...be16(offset - 20 - 2), ...new Array(offset - 24).fill(0), ...sof(0xc0, 100, 100), ...SOS], 1000);
assert.deepEqual(keeps(withHeaderAt(49143)), [], "a header that ends on byte 49,152 is read");
assert.deepEqual(keeps(withHeaderAt(49144)), [1], "a header that needs byte 49,153 is not read, so the still is kept");
assert.ok(withHeaderAt(49143).length > 65536 && withHeaderAt(49144).length > 65536, "both stills are longer than the head that is read");

// A skipped still is not asked about and does not use a number: Build Movie scores
// links[k-1] from s{seg}c{k}, so k counts what is left. Here the first and the
// last are out of limits, the second is read and in, the third cannot be read.
out = runBodies([still(0, 1), still(0, 2), still(0, 3), still(0, 4)], [pngOf(100, 100), jpegOf(640, 480), JPEG, pngOf(2000, 2000)].map((p) => fetched(p)));
assert.equal(out.length, 1);
assert.deepEqual(out[0].json.links, ["https://videos.pexels.com/s0c2.mp4", "https://videos.pexels.com/s0c3.mp4"]);
assert.deepEqual(Object.keys(out[0].json.body.questions), ["s0c1", "s0c2"]);
assert.deepEqual(Object.keys(out[0].json.body.assets), ["<s0c1>", "<s0c2>"]);
assert.equal(out[0].json.body.assets["<s0c1>"].data_base64, jpegOf(640, 480));
assert.equal(out[0].json.body.assets["<s0c2>"].data_base64, JPEG);
// A segment whose stills are all out of limits asks nothing, and the next one is untouched.
out = runBodies([still(0, 1), still(0, 2), still(1, 1)], [pngOf(100, 100), jpegOf(5000, 100), JPEG].map((p) => fetched(p)));
assert.deepEqual(out.map((i) => i.json.segIndex), [1]);
assert.deepEqual(out[0].json.links, ["https://videos.pexels.com/s1c1.mp4"]);

// The two nodes chained on the real fixture: whatever the stills node keeps is
// what the bodies node asks about, and each link keeps its place.
const kept = runStills([item(fixture.segment)], [item(fixture.pexels)]);
const fetchedAll = kept.map((_, n) => fetched(n % 2 ? PNG2 : JPEG2));
out = bodies(dollar({ "Jev: B-Roll Stills": kept, "Plan B-Roll Segments": [item(fixture.segment)] }), { all: () => fetchedAll });
assert.equal(out.length, 1);
assert.deepEqual(out[0].json.links, kept.map((i) => i.json.link));
assert.deepEqual(Object.keys(out[0].json.body.questions), ["s0c1", "s0c2", "s0c3", "s0c4"]);
assert.deepEqual(out[0].json.body.assets["<s0c2>"].format, "png");
assert.equal(out[0].json.body.state.sentence, fixture.segment.narration);

// The nodes' own text follows the house rules: no em or en dash, none of the
// banned words. The dash pattern is built from code points so this file carries
// no dash itself, and the word list is not applied to this file, which has to
// spell the words out to check the others.
const DASH = new RegExp("[" + String.fromCharCode(0x2013, 0x2014) + "]");
const BANNED = new RegExp("\\b(?:" + ["leverag", "robust", "seamless", "enhanc", "foster", "highlight", "underscor", "showcas", "pivotal", "delv"].join("|") + ")", "i");
for (const f of ["./jev_broll_stills.js", "./jev_broll_bodies.js", "./jev_broll_bodies.test.mjs"]) {
  assert.ok(!DASH.test(read(f)), f + " carries an em or en dash");
}
// The bodies node and this file are plain ASCII, so the check above cannot be dodged by a look alike.
for (const f of ["./jev_broll_bodies.js", "./jev_broll_bodies.test.mjs"]) {
  assert.ok(readFileSync(new URL(f, import.meta.url)).every((b) => b < 128), f + " is plain ASCII");
}
for (const f of ["./jev_broll_stills.js", "./jev_broll_bodies.js"]) {
  assert.ok(!BANNED.test(read(f)), f + " carries a banned word");
}

console.log("Jev b-roll nodes: every case behaves");
