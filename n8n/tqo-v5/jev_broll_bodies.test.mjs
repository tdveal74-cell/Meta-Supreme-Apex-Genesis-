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
  "Unusable as b-roll: mostly black or blank, blurred, carrying a watermark, a logo or large text, or showing something unrelated to the sentence",
  "A clean, usable shot that does not relate to the sentence",
  "Fits the general topic of the sentence",
  "Clearly shows what the sentence describes",
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
assert.equal(first.body.model, "jev-latest");
assert.deepEqual(first.body.state, { sentence: "First we open the dashboard." });
assert.deepEqual(Object.keys(first.body.questions), ["s0c1", "s0c2"]);
assert.deepEqual(first.body.questions.s0c1, { type: "score", instructions: ask("s0c1"), criteria: CRITERIA });
assert.deepEqual(first.body.questions.s0c2, { type: "score", instructions: ask("s0c2"), criteria: CRITERIA });
assert.deepEqual(first.body.assets, {
  "<s0c1>": { type: "image", format: "jpeg", data_base64: JPEG },
  "<s0c2>": { type: "image", format: "png", data_base64: PNG },
});
assert.deepEqual(Object.keys(first.body), ["model", "state", "questions", "assets"]);

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
for (const f of ["./jev_broll_stills.js", "./jev_broll_bodies.js"]) {
  assert.ok(!BANNED.test(read(f)), f + " carries a banned word");
}

console.log("Jev b-roll nodes: every case behaves");
