/**
 * Does the Jev thumbnail lane name the right photos, build the one TypeSafe
 * request, and leave Thumb: Pick Still exactly as it is today until Tee flips
 * JEV_APPLY?
 *
 *   node n8n/tqo-v5/jev_thumb_rank.test.mjs
 *
 * Covers jev_thumb_stills.js, jev_thumb_body.js and thumb_pick_still.js. Each
 * body runs inside a Function with `$`, `$json` and `$input` stubbed, the same
 * way sources_gate.test.mjs does it. `$('X')` THROWS when node X did not run,
 * which is what n8n does, so every stub here throws for a node it was not given.
 *
 * The Pexels photos below are SYNTHETIC. They follow the documented
 * /v1/search photo shape (id, width, height, url, photographer, src with
 * original, large2x, large, medium, small, portrait, landscape and tiny, alt),
 * and they are synthetic because no execution in retention ran Thumb: Find
 * Still, so there is no real response to copy. The Pick Still check does not
 * depend on them looking real. It runs the UNMODIFIED code of Thumb: Pick Still
 * read out of the workflow export, runs the shipped file on the same stubs, and
 * requires the same output apart from the two keys the shipped file adds.
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const here = (f) => new URL("./" + f, import.meta.url);
const EXPORT = JSON.parse(readFileSync(here("exports/qEkGOUsNyVaRAmm6_active.json"), "utf8"));
const exportCode = (name) => {
  const node = EXPORT.nodes.find((n) => n.name === name);
  assert.ok(node, name + " is in the export");
  return node.parameters.jsCode;
};
const src = (f) => readFileSync(here(f), "utf8");
// n8n throws when a node did not run; so do these stubs.
const notRun = (name) => { throw new Error("Node '" + name + "' hasn't been executed"); };

// ---- synthetic Pexels /v1/search response -------------------------------------
const photo = (id, extra = {}) => {
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
    ...extra,
  };
};
const response = (photos) => ({ page: 1, per_page: 3, photos, total_results: 8000, next_page: "https://api.pexels.com/v1/search/?page=2&per_page=3&query=desk" });
const P1 = photo(1001), P2 = photo(1002), P3 = photo(1003);
const U1 = P1.src.landscape, U2 = P2.src.landscape, U3 = P3.src.landscape;
const THREE = response([P1, P2, P3]);

const PLAN = { airtableId: "rec1", brand: "The Quiet Operator", kicker: "THE QUIET OPERATOR", headline: "THE MIDDLE IS THE TARGET", query: "professional desk window", queryRaw: "professional desk window evening", isNCO: false };

// ---- jev_thumb_stills.js --------------------------------------------------------
const stillsFn = new Function("$", "$input", src("jev_thumb_stills.js"));
const stills = (findStill) => stillsFn((node) => (node === "Thumb: Find Still" ? { first: () => ({ json: findStill }) } : notRun(node)), { all: () => [] });
const stillsOf = (findStill) => stills(findStill).map((i) => i.json);

// The same photos Pick Still would consider, in order, with the url it would draw.
assert.deepEqual(stillsOf(THREE), [
  { k: 1, photoId: 1001, url: U1, fetchUrl: U1 },
  { k: 2, photoId: 1002, url: U2, fetchUrl: U2 },
  { k: 3, photoId: 1003, url: U3, fetchUrl: U3 },
]);
// At most three, even if Pexels sent more.
assert.deepEqual(stillsOf(response([P1, P2, P3, photo(1004), photo(1005)])).map((s) => s.k), [1, 2, 3]);
// landscape, then large2x, then large.
const noLandscape = photo(2001); delete noLandscape.src.landscape;
const onlyLarge = photo(2002); delete onlyLarge.src.landscape; delete onlyLarge.src.large2x;
assert.deepEqual(stillsOf(response([noLandscape, onlyLarge])).map((s) => s.url), [noLandscape.src.large2x, onlyLarge.src.large]);
// url stays what Pick Still draws, because Pick Still matches scores by it. fetchUrl
// is what the HTTP fetch node reads: landscape, else large, never large2x.
// TypeSafe takes 280 to 1568 pixels a side and one rejected image fails the whole
// request. The synthetic large2x above carries dpr=2 with w=940, which is about
// 1880 pixels wide if Pexels documents it so; that is unverified here, no live
// Pexels response was read, and the test only pins that large2x is never fetched.
// Landscape missing, large2x and large present: url is large2x, fetchUrl is large.
assert.deepEqual(stillsOf(response([noLandscape])), [{ k: 1, photoId: 2001, url: noLandscape.src.large2x, fetchUrl: noLandscape.src.large }]);
assert.notEqual(noLandscape.src.large2x, noLandscape.src.large);
// Only large2x: nothing to fetch inside the size limit, so no item, and k keeps its place.
const onlyLarge2x = photo(2006); delete onlyLarge2x.src.landscape; delete onlyLarge2x.src.large;
assert.deepEqual(stillsOf(response([onlyLarge2x])), []);
assert.deepEqual(stillsOf(response([P1, onlyLarge2x, P3])).map((s) => s.k), [1, 3]);
// Only large: url and fetchUrl are both large.
assert.deepEqual(stillsOf(response([onlyLarge])), [{ k: 1, photoId: 2002, url: onlyLarge.src.large, fetchUrl: onlyLarge.src.large }]);
// Normal case: url and fetchUrl are both landscape, and every item is just these four keys.
assert.deepEqual(stillsOf(response([P1]))[0], { k: 1, photoId: 1001, url: U1, fetchUrl: U1 });
for (const s of stillsOf(THREE)) assert.equal(s.url, s.fetchUrl);
// fetchUrl obeys the Pexels host rule as well: a large on another host is not fetched.
const foreignLarge = photo(2007); delete foreignLarge.src.landscape; foreignLarge.src.large = "https://evil.example/photos/2007.jpeg";
assert.deepEqual(stillsOf(response([foreignLarge])), []);
// Only the Pexels image host is fetched. The photo is skipped and k keeps its place.
const foreign = photo(2003); foreign.src.landscape = "https://evil.example/photos/2003.jpeg";
const lookalike = photo(2004); lookalike.src.landscape = "https://images.pexels.com.evil.example/x.jpeg";
const insecure = photo(2005); insecure.src.landscape = "http://images.pexels.com/x.jpeg";
assert.deepEqual(stillsOf(response([P1, foreign, P3])).map((s) => s.k), [1, 3]);
assert.deepEqual(stillsOf(response([lookalike, insecure, P3])).map((s) => [s.k, s.url]), [[3, U3]]);
// A photo with no src, a null entry, a src with no url: skipped, nothing thrown.
assert.deepEqual(stillsOf(response([null, { id: 7 }, P3, P1])).map((s) => s.k), [3]);
assert.deepEqual(stillsOf(response([{ id: 8, src: {} }, { id: 9, src: { landscape: 5 } }, { id: 10, src: { landscape: "" } }])), []);
// Fail open: no photos, no list, an error item, a node that did not run.
assert.deepEqual(stillsOf(response([])), []);
assert.deepEqual(stillsOf({ error: { message: "Forbidden" } }), []);
assert.deepEqual(stillsOf({ photos: "none" }), []);
assert.deepEqual(stills(null), []);
assert.deepEqual(stillsFn((node) => notRun(node), { all: () => [] }), []);

// ---- jev_thumb_body.js ---------------------------------------------------------
// Headers only. The node finds the format from the base64 prefix and reads the
// size from the first bytes, so these are real file headers and not whole images.
const u16 = (n) => [(n >> 8) & 255, n & 255];
const u32 = (n) => [Math.floor(n / 16777216) & 255, (n >> 16) & 255, (n >> 8) & 255, n & 255];
const ascii = (s) => [...s].map((c) => c.charCodeAt(0));
const CRC_TABLE = Array.from({ length: 256 }, (_, n) => { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; return c >>> 0; });
const crc32 = (bytes) => { let c = 0xffffffff; for (const b of bytes) c = CRC_TABLE[(c ^ b) & 255] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; };
assert.equal(crc32(ascii("123456789")), 0xcbf43926, "the CRC used for the PNG headers is CRC-32");
const b64of = (bytes) => Buffer.from(bytes).toString("base64");
// A PNG header: the signature, then IHDR (length 13, type, width, height, 8 bit
// RGB, no interlace, CRC), the chunk every PNG starts with.
const PNG_SIG = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];
const pngBytes = (w, h) => {
  const ihdr = [...ascii("IHDR"), ...u32(w), ...u32(h), 8, 2, 0, 0, 0];
  return [...PNG_SIG, ...u32(13), ...ihdr, ...u32(crc32(ihdr))];
};
const pngOf = (w, h) => b64of(pngBytes(w, h));
// A JPEG header: SOI, an APP0 JFIF segment, optional segments, the SOF segment
// (three components), and the start of the scan.
const APP0 = [0xff, 0xe0, 0x00, 0x10, 0x4a, 0x46, 0x49, 0x46, 0x00, 0x01, 0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00];
const SOS = [0xff, 0xda, 0x00, 0x0c, 0x03, 0x01, 0x00, 0x02, 0x11, 0x03, 0x11, 0x00, 0x3f, 0x00];
const sofSeg = (w, h, marker = 0xc0) => [0xff, marker, 0x00, 0x11, 0x08, ...u16(h), ...u16(w), 0x03, 0x01, 0x22, 0x00, 0x02, 0x11, 0x01, 0x03, 0x11, 0x01];
const jpegBytes = (w, h, { marker = 0xc0, between = [], tail = [] } = {}) => [0xff, 0xd8, ...APP0, ...between, ...sofSeg(w, h, marker), ...SOS, ...tail];
const jpegOf = (w, h, opts) => b64of(jpegBytes(w, h, opts));
// A segment with the given marker byte and payload.
const segment = (marker, payload) => [0xff, marker, ...u16(payload.length + 2), ...payload];

// JPEG has no SOF here, so its size cannot be read and it is kept. PNG is a real
// header 1200 by 627, inside the limits.
const JPEG = Buffer.from([0xff, 0xd8, 0xff, 0xe0, 0x00, 0x10, 0x4a, 0x46, 0x49, 0x46, 0x00, 0x01, 0x01, 0x00]).toString("base64");
const PNG = pngOf(1200, 627);
const GIF = "R0lGODlhAQABAAAAACw=";
const WEBP = "UklGRhYAAABXRUJQVlA4TAoAAAAvAAAAAAfQ";
assert.ok(JPEG.startsWith("/9j/") && PNG.startsWith("iVBORw0KGgo"));
assert.ok(jpegOf(1200, 627).startsWith("/9j/") && pngOf(1, 1).startsWith("iVBORw0KGgo"));

const bodyFn = new Function("$", "$input", src("jev_thumb_body.js"));
const STILLS = [{ k: 1, photoId: 1001, url: U1 }, { k: 2, photoId: 1002, url: U2 }, { k: 3, photoId: 1003, url: U3 }];
const bodyOf = (files, { stillItems = STILLS, plan = PLAN, planThrows = false, stillsThrow = false } = {}) =>
  bodyFn(
    (node) => {
      if (node === "Jev: Thumb Stills" && !stillsThrow) return { all: () => stillItems.map((json) => ({ json })) };
      if (node === "Thumb: Plan" && !planThrows) return { first: () => ({ json: plan }) };
      return notRun(node);
    },
    { all: () => files.map((b64) => ({ json: b64 === undefined ? {} : { still_b64: b64 } })) },
  );
const QUESTION = (ref) => "How well does <" + ref + "> work as the photograph behind a YouTube thumbnail about `subject`, where a dark panel covers its left 60 percent and `headline` sits on that panel?";
const CRITERIA = [
  "Unusable: dark, cluttered, blurred, or carrying text or a watermark",
  "Usable, but about something other than the subject",
  "Fits the subject, but what matters sits on the left 60 percent of the frame, under the dark panel",
  "Fits the subject, and what matters sits in the right part of the frame, where it stays visible",
];
// The levels are distinct, one situation each, and plain ASCII.
assert.equal(new Set(CRITERIA).size, 4);
assert.ok(CRITERIA.every((c) => /^[\x20-\x7e]+$/.test(c)));

// Three usable stills make one item, one score question each.
let out = bodyOf([JPEG, PNG, JPEG]);
assert.equal(out.length, 1);
assert.deepEqual(out[0].json.urls, [U1, U2, U3]);
let body = out[0].json.body;
assert.equal(body.model, "jev-1.14.0", "pinned, ruled 2026-10-27");
assert.deepEqual(body.state, { subject: "professional desk window evening", headline: "THE MIDDLE IS THE TARGET" });
assert.deepEqual(Object.keys(body.questions), ["p1", "p2", "p3"]);
for (const k of [1, 2, 3]) {
  assert.deepEqual(body.questions["p" + k], { type: "score", instructions: QUESTION("p" + k), criteria: CRITERIA });
}
assert.deepEqual(body.assets, {
  "<p1>": { type: "image", format: "jpeg", data_base64: JPEG },
  "<p2>": { type: "image", format: "png", data_base64: PNG },
  "<p3>": { type: "image", format: "jpeg", data_base64: JPEG },
});
// Every asset is referenced by a question, and the body survives JSON.
for (const ref of Object.keys(body.assets)) assert.ok(Object.values(body.questions).some((q) => q.instructions.includes(ref)), ref);
assert.deepEqual(JSON.parse(JSON.stringify(body)), body);
// No question shares its criteria array with another.
body.questions.p1.criteria.push("x");
assert.equal(body.questions.p2.criteria.length, 4);

// Only PNG and JPEG go. A GIF, a WebP, an empty string, a missing field and a
// non string are skipped, the question numbers keep the photo's k, and urls
// holds null where no question was asked.
out = bodyOf([GIF, PNG, WEBP]);
assert.deepEqual(Object.keys(out[0].json.body.questions), ["p2"]);
assert.deepEqual(Object.keys(out[0].json.body.assets), ["<p2>"]);
assert.deepEqual(out[0].json.urls, [null, U2]);
out = bodyOf([JPEG, "", undefined]);
assert.deepEqual(Object.keys(out[0].json.body.questions), ["p1"]);
assert.deepEqual(out[0].json.urls, [U1]);
assert.deepEqual(Object.keys(bodyOf([42, JPEG, null])[0].json.body.questions), ["p2"]);
// The whole prefix is checked: text that only starts like one is not an image.
assert.deepEqual(Object.keys(bodyOf(["/9jAAAAAAAA", "iVBORAAAAAAA", PNG])[0].json.body.questions), ["p3"]);
// No usable photo at all: nothing is asked.
assert.deepEqual(bodyOf([GIF, WEBP, ""]), []);
assert.deepEqual(bodyOf([]), []);

// Pairing is by position and needs equal lengths.
assert.deepEqual(bodyOf([JPEG, JPEG]), []);
assert.deepEqual(bodyOf([JPEG, JPEG, JPEG, JPEG]), []);
// A photo the stills node skipped leaves k 3, and the pairing follows position.
out = bodyOf([JPEG, PNG], { stillItems: [STILLS[0], STILLS[2]] });
assert.deepEqual(Object.keys(out[0].json.body.questions), ["p1", "p3"]);
assert.deepEqual(out[0].json.urls, [U1, null, U3]);

// Fail open: a node that did not run, no subject, no headline.
assert.deepEqual(bodyOf([JPEG, JPEG, JPEG], { stillsThrow: true }), []);
assert.deepEqual(bodyOf([JPEG, JPEG, JPEG], { planThrows: true }), []);
assert.deepEqual(bodyOf([JPEG, JPEG, JPEG], { plan: { ...PLAN, queryRaw: "" } }), []);
assert.deepEqual(bodyOf([JPEG, JPEG, JPEG], { plan: { ...PLAN, headline: "  " } }), []);
assert.deepEqual(bodyOf([JPEG, JPEG, JPEG], { plan: {} }), []);
// A subject of only whitespace is no subject: no request is built. This is the
// .trim() on queryRaw, which an empty string alone does not exercise.
for (const queryRaw of ["   ", "\t", " \n ", String.fromCharCode(0xa0) + " "]) {
  assert.deepEqual(bodyOf([JPEG, JPEG, JPEG], { plan: { ...PLAN, queryRaw } }), [], JSON.stringify(queryRaw));
}
// A stills item with no usable k or url is not trusted.
assert.deepEqual(bodyOf([JPEG], { stillItems: [{ k: 0, url: U1 }] }), []);
assert.deepEqual(bodyOf([JPEG], { stillItems: [{ k: 1 }] }), []);
// A bad stills item in the MIDDLE skips only its own photo: the photos after it
// are still asked about, and the bad one leaves a null in urls.
for (const bad of [{ k: 0, url: U2 }, { k: 1.5, url: U2 }, { k: "2", url: U2 }, { k: 2 }, { k: 2, url: 7 }, null, {}]) {
  out = bodyOf([JPEG, JPEG, JPEG], { stillItems: [STILLS[0], bad, STILLS[2]] });
  assert.deepEqual(Object.keys(out[0].json.body.questions), ["p1", "p3"], JSON.stringify(bad));
  assert.deepEqual(out[0].json.urls, [U1, null, U3], JSON.stringify(bad));
}
// The same when it is the first item: the photos after it still count.
out = bodyOf([JPEG, JPEG, JPEG], { stillItems: [{ k: 0, url: U1 }, STILLS[1], STILLS[2]] });
assert.deepEqual(Object.keys(out[0].json.body.questions), ["p2", "p3"]);

// One request body stays under 20,000,000 characters of base64. The later
// photos, the lower ranked in Pexels order, are the ones dropped.
const BIG = "/9j/" + "A".repeat(11000000);
out = bodyOf([BIG, BIG, BIG]);
assert.deepEqual(Object.keys(out[0].json.body.questions), ["p1"]);
assert.deepEqual(out[0].json.urls, [U1]);
assert.ok(Object.values(out[0].json.body.assets).reduce((n, a) => n + a.data_base64.length, 0) <= 20000000);
assert.deepEqual(Object.keys(bodyOf([BIG, JPEG, BIG])[0].json.body.questions), ["p1", "p2"]);
// Once one photo overflows, every photo after it goes too, small or not.
assert.deepEqual(Object.keys(bodyOf([BIG, BIG, JPEG])[0].json.body.questions), ["p1"]);
assert.deepEqual(bodyOf(["/9j/" + "A".repeat(20000001), JPEG, JPEG]), []);
// The cap itself. Two stills of exactly 10,000,000 characters each total exactly
// 20,000,000 and both fit, because only a total OVER the cap is refused. A third
// still of any size, even the four characters of a bare JPEG prefix, is dropped.
const HALF = "/9j/" + "A".repeat(10000000 - 4);
assert.equal(HALF.length, 10000000);
// bodyOf pairs files with stills by position and needs equal lengths, so the two
// file case is given two stills items.
out = bodyOf([HALF, HALF], { stillItems: STILLS.slice(0, 2) });
assert.deepEqual(Object.keys(out[0].json.body.questions), ["p1", "p2"]);
assert.equal(Object.values(out[0].json.body.assets).reduce((n, a) => n + a.data_base64.length, 0), 20000000);
assert.deepEqual(out[0].json.urls, [U1, U2]);
// One character over the cap is refused: 10,000,001 and 10,000,000 total
// 20,000,001, so the second still goes and only the first is asked about.
out = bodyOf([HALF + "A", HALF], { stillItems: STILLS.slice(0, 2) });
assert.deepEqual(Object.keys(out[0].json.body.questions), ["p1"]);
for (const third of ["/9j/", JPEG, PNG, HALF]) {
  out = bodyOf([HALF, HALF, third]);
  assert.deepEqual(Object.keys(out[0].json.body.questions), ["p1", "p2"], "third of length " + third.length);
  assert.deepEqual(out[0].json.urls, [U1, U2]);
}
// Landing on the cap exactly at the third still fits as well: 10,000,000 plus
// 9,999,996 plus a four character prefix is 20,000,000.
out = bodyOf([HALF, "/9j/" + "A".repeat(9999996 - 4), "/9j/"]);
assert.deepEqual(Object.keys(out[0].json.body.questions), ["p1", "p2", "p3"]);
assert.equal(Object.values(out[0].json.body.assets).reduce((n, a) => n + a.data_base64.length, 0), 20000000);

// ---- the size check in jev_thumb_body.js ---------------------------------------
// TypeSafe rejects an image under 280 or over 1568 pixels on either side, and one
// rejected image fails the whole request (images.md, Limits). A still whose size is
// read and is out of limits is skipped. A still whose size cannot be read is kept,
// so the check fails open to what the node did before it. The headers below are
// built here, PNG by IHDR with a real CRC and JPEG by SOI, APP0, SOF and SOS.
// The total pixel range in the docs is the area of the smallest and the largest
// square, so a side inside 280 to 1568 can never leave it.
assert.equal(280 * 280, 78400);
assert.equal(1568 * 1568, 2458624);
// Each still sits in the middle, so the photos either side show who was skipped.
const askedFor = (files) => { const o = bodyOf(files); return o.length ? Object.keys(o[0].json.body.questions) : []; };
const GOOD = jpegOf(1200, 627);
const kept = (still) => askedFor([GOOD, still, GOOD]).includes("p2");
assert.deepEqual(askedFor([GOOD, GOOD, GOOD]), ["p1", "p2", "p3"]);
assert.deepEqual(askedFor([GOOD, jpegOf(100, 100), GOOD]), ["p1", "p3"]);
assert.deepEqual(bodyOf([GOOD, GOOD, GOOD])[0].json.urls, [U1, U2, U3]);
assert.deepEqual(bodyOf([GOOD, jpegOf(100, 100), GOOD])[0].json.urls, [U1, null, U3]);
// All three out of limits: nothing is asked.
assert.deepEqual(bodyOf([jpegOf(100, 100), pngOf(1, 1), jpegOf(4000, 2667)]), []);

// In limits, the edges included, on either side, PNG and JPEG alike.
for (const [w, h] of [[1200, 627], [1280, 720], [280, 280], [1568, 1568], [280, 1568], [1568, 280], [1568, 600], [600, 1568], [280, 900], [900, 280]]) {
  assert.ok(kept(pngOf(w, h)), "png " + w + "x" + h);
  assert.ok(kept(jpegOf(w, h)), "jpeg " + w + "x" + h);
}
// Under 280 on either side.
for (const [w, h] of [[1, 1], [100, 100], [279, 279], [279, 600], [600, 279], [279, 1568], [1568, 279], [1200, 1], [1, 627]]) {
  assert.ok(!kept(pngOf(w, h)), "png " + w + "x" + h);
  assert.ok(!kept(jpegOf(w, h)), "jpeg " + w + "x" + h);
}
// Over 1568 on either side. 4000 by 2667 is the size of a Pexels original.
for (const [w, h] of [[1569, 600], [600, 1569], [1569, 1569], [1569, 280], [280, 1569], [4000, 2667], [2667, 4000], [65535, 65535]]) {
  assert.ok(!kept(pngOf(w, h)), "png " + w + "x" + h);
  assert.ok(!kept(jpegOf(w, h)), "jpeg " + w + "x" + h);
}
// A PNG side is 32 bits. 65836 reads as 300 without its third byte and 16777516
// reads as 300 without its first, so each is out of limits only when all four
// bytes are read.
for (const [w, h] of [[65836, 400], [400, 65836], [70000, 400], [400, 70000], [16777516, 400], [400, 16777516]]) assert.ok(!kept(pngOf(w, h)), "png " + w + "x" + h);

// Every JPEG SOF marker reads, 0xC0 to 0xCF except 0xC4, 0xC8 and 0xCC.
const SOF_MARKERS = [0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf];
for (const marker of SOF_MARKERS) {
  assert.ok(!kept(jpegOf(100, 100, { marker })), "sof 0x" + marker.toString(16));
  assert.ok(kept(jpegOf(1200, 627, { marker })), "sof 0x" + marker.toString(16));
}
// 0xC4 (DHT), 0xC8 and 0xCC (DAC) are segments with a length, not frames. Each is
// given a payload that reads as a frame size, so a node that took one for a SOF
// would read the decoy: 1200 by 627 in front of a real 100 by 100, and the
// reverse. Fill bytes before a marker are skipped.
for (const marker of [0xc4, 0xc8, 0xcc]) {
  const decoy = (w, h) => segment(marker, [8, ...u16(h), ...u16(w), 0, 0, 0, 0, 0, 0, 0, 0, 0]);
  assert.ok(!kept(jpegOf(100, 100, { between: decoy(1200, 627) })), "decoy 0x" + marker.toString(16) + " before a small frame");
  assert.ok(kept(jpegOf(1200, 627, { between: decoy(100, 100) })), "decoy 0x" + marker.toString(16) + " before a good frame");
}
assert.ok(!kept(jpegOf(100, 100, { between: [0xff, 0xff] })));
// The first SOF is the frame. A thumbnail inside an EXIF APP1 segment has a SOF of
// its own, and the segment is skipped by its length, whichever size it carries.
const exif = (embedded) => segment(0xe1, [...ascii("Exif"), 0, 0, ...embedded]);
assert.ok(kept(jpegOf(1200, 627, { between: exif(jpegBytes(100, 100)) })));
assert.ok(!kept(jpegOf(100, 100, { between: exif(jpegBytes(1200, 627)) })));
// A scan after the first frame is never read for a size.
assert.ok(!kept(jpegOf(100, 100, { tail: jpegBytes(1200, 627) })));

// A size that cannot be read keeps the still, whatever the numbers beyond the break.
const noPad = (bytes) => { const b = bytes.slice(); while (b.length % 3) b.push(0); return b; };
const unreadable = {
  "bare jpeg header": JPEG,
  "jpeg SOI and nothing else": b64of([0xff, 0xd8, 0xff]),
  "jpeg cut in the middle of the size": b64of(jpegBytes(100, 100).slice(0, 2 + APP0.length + 6)),
  "jpeg cut one byte short of the width": b64of(jpegBytes(100, 100).slice(0, 2 + APP0.length + 8)),
  "jpeg scan before any frame": b64of([0xff, 0xd8, ...APP0, ...SOS, ...sofSeg(100, 100)]),
  "jpeg end of image before any frame": b64of([0xff, 0xd8, ...APP0, 0xff, 0xd9, ...sofSeg(100, 100)]),
  "jpeg byte that is not a marker": b64of([0xff, 0xd8, ...APP0, 0x00, ...sofSeg(100, 100)]),
  "jpeg stuffed zero where a marker should be": b64of([0xff, 0xd8, ...APP0, 0xff, 0x00, ...sofSeg(100, 100)]),
  "jpeg segment length of 0": b64of([0xff, 0xd8, 0xff, 0xe0, 0x00, 0x00, ...sofSeg(100, 100)]),
  "jpeg segment length of 1": b64of([0xff, 0xd8, 0xff, 0xe0, 0x00, 0x01, ...sofSeg(100, 100)]),
  "jpeg segment longer than the data": b64of([0xff, 0xd8, 0xff, 0xe0, 0xff, 0xff, ...sofSeg(100, 100)]),
  "jpeg frame of height 0": jpegOf(100, 0),
  "jpeg frame of width 0": jpegOf(0, 100),
  "jpeg frame too short to hold a size": b64of([0xff, 0xd8, ...APP0, 0xff, 0xc0, 0x00, 0x05, 0x08, 0x00, 0x64, 0x00, 0x64]),
  "png cut inside IHDR": b64of(pngBytes(100, 100).slice(0, 20)),
  "png with no chunk after the signature": b64of(PNG_SIG),
  "png first chunk is not IHDR": b64of([...PNG_SIG, ...u32(13), ...ascii("IDAT"), ...u32(100), ...u32(100), 8, 2, 0, 0, 0, 0, 0, 0, 0]),
  "png IHDR of length 12": b64of([...PNG_SIG, ...u32(12), ...ascii("IHDR"), ...u32(100), ...u32(100), 8, 2, 0, 0, 0, 0, 0, 0, 0]),
  "png of width 0": pngOf(0, 100),
  "png of height 0": pngOf(100, 0),
  "png with a tag where IHDR should be": b64of([...PNG_SIG, 0, 0, 0, 13, ...ascii("|abc|"), ...u32(100), ...u32(100)]),
};
for (const [label, still] of Object.entries(unreadable)) {
  assert.ok(still.startsWith("/9j/") || still.startsWith("iVBORw0KGgo"), label + " still reads as a PNG or a JPEG");
  assert.ok(kept(still), label);
}
// The same garbage that is kept alone is kept with a good photo beside it, and a
// wholly unreadable set still asks about every photo.
assert.deepEqual(askedFor(Object.values(unreadable).slice(0, 3)), ["p1", "p2", "p3"]);

// Only the first 65,536 base64 characters are read, which is 49,152 bytes. A frame
// whose size bytes end on the last byte of that window is read; one byte later it
// is not, the still is kept, and the numbers behind the window are never looked at.
const WINDOW = 65536 / 4 * 3;
assert.equal(WINDOW, 49152);
const framedAt = (lastSizeByte, w, h) => jpegOf(w, h, { between: segment(0xfe, new Array(lastSizeByte - 32).fill(0x20)), tail: new Array(2000).fill(0) });
const atEdge = framedAt(WINDOW - 1, 100, 100);
const pastEdge = framedAt(WINDOW, 100, 100);
assert.ok(atEdge.length > 65536 && pastEdge.length > 65536, "both stills are longer than the window");
assert.equal(Buffer.from(atEdge, "base64").readUInt16BE(WINDOW - 1 - 3), 100, "the height ends two bytes before the last size byte");
assert.ok(!kept(atEdge), "size bytes ending on the last byte of the window are read");
assert.ok(kept(pastEdge), "size bytes one byte past the window are not read, and the still is kept");
// A PNG always has its size at the start, so a long PNG is read.
assert.ok(!kept(pngOf(100, 100) + "A".repeat(100000)));

// A skipped still is not counted against the body cap. The first is out of limits
// and 11,000,000 characters long, and the two after it fit between them.
const SKIPPED_BIG = b64of(noPad(jpegBytes(100, 100)));
assert.ok(!SKIPPED_BIG.includes("="));
assert.deepEqual(askedFor([SKIPPED_BIG + "A".repeat(11000000 - SKIPPED_BIG.length), BIG, JPEG]), ["p2", "p3"]);
// The size check runs before the cap: a skipped still over the whole cap on its
// own must not stop the photos after it.
assert.deepEqual(askedFor([SKIPPED_BIG + "A".repeat(20000001 - SKIPPED_BIG.length), JPEG, JPEG]), ["p2", "p3"]);
// Nothing here throws on a string that is not base64 at all.
assert.ok(kept("/9j/" + "!".repeat(100)) && kept("iVBORw0KGgo" + "!".repeat(100)));

// ---- thumb_pick_still.js -------------------------------------------------------
// Today's Pick Still is the export's with the layout fix Tee ruled on 2026-10-27
// ("Fix both, prove first"), published as de4ac645. Each pair must occur once.
const LAYOUT = JSON.parse(src("live-thumb-layout/replacement.json"));
const ORIGINAL = LAYOUT.pairs.reduce((s, p) => {
  assert.equal(s.split(p.old).length, 2, "a layout pair occurs once in the export's Pick Still");
  return s.replace(p.old, () => p.new);
}, exportCode("Thumb: Pick Still"));
const SHIPPED = src("thumb_pick_still.js");
const flipped = SHIPPED.replace("const JEV_APPLY = false;", "const JEV_APPLY = true;");
assert.notEqual(flipped, SHIPPED, "the shipped file declares JEV_APPLY = false");
assert.match(SHIPPED, /^const JEV_APPLY = false;$/m);
// The floor is a named constant and it is 2, the level that reads "fits the subject".
assert.match(SHIPPED, /^const JEV_FLOOR = 2;$/m);

// The shipped file is the export code plus the Jev block. Take the block out,
// put the two consts back and drop the two output keys, and the export is left.
const stripped = SHIPPED
  .replace(/\n\/\/ Jev scoring, ruled by Tee[\s\S]*?\nif \(JEV_APPLY && jevPhoto\) \{ pick = jevPhoto; src = jevPick; \}\n/, "")
  .replace("let pick = ", "const pick = ")
  .replace("let src = ", "const src = ")
  .replace(",\n  jevPick,\n  jevApplied: JEV_APPLY\n", "\n");
assert.equal(stripped, ORIGINAL, "thumb_pick_still.js is the exported Pick Still code plus the Jev block");

const runPick = (code, { json, plan = PLAN, jev = {} }) => {
  const $ = (node) => {
    if (node === "Thumb: Plan") return { first: () => ({ json: plan }) };
    if (node in jev) return jev[node];
    return notRun(node);
  };
  return new Function("$", "$json", code)($, json)[0].json;
};
const withoutJev = ({ jevPick, jevApplied, ...rest }) => rest;
const reply = (answers, model = "jev-latest") => ({ json: { model, answers, usage: {} } });
const score = (n) => ({ type: "score", score: n, confidence: 0.9, legend: {}, probabilities: {} });
const jevNodes = (urls, ...responses) => ({
  "Jev: Thumb Body": { first: () => ({ json: { urls, body: {} } }) },
  "Jev: Rank Stills": { all: () => responses },
});

// With no Jev node run, the output is the unmodified export's output plus
// jevPick null and jevApplied false, for every shape of Find Still output.
const PLANS = [
  PLAN,
  { ...PLAN, headline: "STOP HIRING MANAGERS NOW", isNCO: true, show: "NCO" },
  { ...PLAN, headline: "A HEADLINE LONG ENOUGH TO USE THE SMALLEST TYPE", show: "TSWS" },
  { ...PLAN, show: "ACX", kicker: undefined },
  { ...PLAN, show: "SOMETHING ELSE", headline: undefined },
];
const noLandscapeOrLarge2x = photo(3001); delete noLandscapeOrLarge2x.src.landscape; delete noLandscapeOrLarge2x.src.large2x;
const SHAPES = {
  "three photos": THREE,
  "first photo without landscape": response([noLandscape, P2, P3]),
  "only large on the first photo": response([noLandscapeOrLarge2x, onlyLarge]),
  "no photos": response([]),
  "no photos key": { error: { message: "Forbidden" } },
  "null entry first": response([null, P2]),
};
for (const [label, json] of Object.entries(SHAPES)) {
  for (const plan of PLANS) {
    const want = runPick(ORIGINAL, { json, plan });
    const got = runPick(SHIPPED, { json, plan });
    assert.deepEqual(withoutJev(got), want, label);
    assert.equal(got.jevPick, null, label);
    assert.equal(got.jevApplied, false, label);
    assert.deepEqual(Object.keys(got).filter((key) => !(key in want)), ["jevPick", "jevApplied"], label);
    // Flipped on with nothing to apply, it is still today's choice.
    const on = runPick(flipped, { json, plan });
    assert.deepEqual(withoutJev(on), want, label + " (applied, no scores)");
    assert.equal(on.jevPick, null);
    assert.equal(on.jevApplied, true);
  }
}
// Jev nodes that ran but gave nothing usable leave today's output as well.
for (const jev of [
  jevNodes([U1, U2, U3]),
  jevNodes([U1, U2, U3], { json: { error: { message: "402" } } }),
  jevNodes([U1, U2, U3], reply({ p1: score(3) }, "gpt-5")),
]) {
  assert.deepEqual(withoutJev(runPick(flipped, { json: THREE, jev })), runPick(ORIGINAL, { json: THREE }));
}

const today = runPick(ORIGINAL, { json: THREE });
assert.equal(today.photoUsed, U1);
const pickWith = (code, urls, ...responses) => runPick(code, { json: THREE, jev: jevNodes(urls, ...responses) });
const URLS = [U1, U2, U3];

// Shadow: Jev prefers photo 2, the report says so, and the photo used does not move.
let r = pickWith(SHIPPED, URLS, reply({ p1: score(1), p2: score(3), p3: score(2) }));
assert.equal(r.jevPick, U2);
assert.equal(r.jevApplied, false);
assert.deepEqual(withoutJev(r), today);
// Applied: the photo and its credit follow Jev, and nothing else in the layout moves.
r = pickWith(flipped, URLS, reply({ p1: score(1), p2: score(3), p3: score(2) }));
assert.equal(r.jevPick, U2);
assert.equal(r.jevApplied, true);
assert.equal(r.photoUsed, U2);
assert.equal(r.photographer, "Photographer 1002");
const { photoUsed: _a, photographer: _b, ...restApplied } = withoutJev(r);
const { photoUsed: _c, photographer: _d, ...restToday } = today;
assert.deepEqual(restApplied, restToday);

// Ties keep Pexels order.
assert.equal(pickWith(SHIPPED, URLS, reply({ p1: score(2), p2: score(3), p3: score(3) })).jevPick, U2);
assert.equal(pickWith(SHIPPED, URLS, reply({ p1: score(2), p2: score(2), p3: score(1) })).jevPick, U1);
assert.equal(pickWith(SHIPPED, URLS, reply({ p1: score(2), p2: score(2), p3: score(2) })).jevPick, U1);
// Scores are floats; 2.6 beats 2.4. Exactly 2 qualifies and 1.999 does not.
assert.equal(pickWith(SHIPPED, URLS, reply({ p1: score(2.4), p2: score(1.1), p3: score(2.6) })).jevPick, U3);
assert.equal(pickWith(SHIPPED, URLS, reply({ p1: score(1.999), p2: score(2) })).jevPick, U2);
// The floor is JEV_FLOOR, 2, the level that reads "fits the subject". A Jev score
// is a probability weighted mean of the level numbers (score.md), so a picture Jev
// is certain is "usable, but about something other than the subject" scores
// exactly 1, and at a floor of 1 it qualified. It no longer does. A lone score
// under 2 is not a pick and a lone score of exactly 2 is. A 1.999 beside a 2 gave
// the right photo with or without the floor, so the lone cases are what pin it.
assert.equal(pickWith(SHIPPED, URLS, reply({ p1: score(0.5) })).jevPick, null);
assert.equal(pickWith(SHIPPED, URLS, reply({ p1: score(1) })).jevPick, null);
assert.equal(pickWith(SHIPPED, URLS, reply({ p1: score(1.5) })).jevPick, null);
assert.equal(pickWith(SHIPPED, URLS, reply({ p1: score(1.999) })).jevPick, null);
assert.equal(pickWith(SHIPPED, URLS, reply({ p1: score(2) })).jevPick, U1);
assert.equal(pickWith(SHIPPED, URLS, reply({ p2: score(1.999) })).jevPick, null);
assert.equal(pickWith(SHIPPED, URLS, reply({ p2: score(2) })).jevPick, U2);
assert.equal(pickWith(SHIPPED, URLS, reply({ p3: score(0.5) })).jevPick, null);
// Three photos all at 1.999 give no pick, and all at 1 give none.
assert.equal(pickWith(SHIPPED, URLS, reply({ p1: score(1.999), p2: score(1.999), p3: score(1.999) })).jevPick, null);
assert.equal(pickWith(SHIPPED, URLS, reply({ p1: score(1), p2: score(1), p3: score(1) })).jevPick, null);
// Applied, a lone 1.999 or 1 on photo 2 moves nothing and a lone 2 on photo 2 does.
for (const below of [0.5, 1, 1.999]) {
  r = pickWith(flipped, URLS, reply({ p2: score(below) }));
  assert.equal(r.jevPick, null, "applied, lone " + below);
  assert.equal(r.photoUsed, U1, "applied, lone " + below);
}
r = pickWith(flipped, URLS, reply({ p2: score(2) }));
assert.equal(r.jevPick, U2);
assert.equal(r.photoUsed, U2);
// A photo scored 0 is never chosen, and neither is one nobody scored.
r = pickWith(flipped, URLS, reply({ p1: score(0), p2: score(0), p3: score(0) }));
assert.equal(r.jevPick, null);
assert.equal(r.photoUsed, U1);
r = pickWith(flipped, URLS, reply({ p1: score(0), p2: score(2) }));
assert.equal(r.jevPick, U2);
assert.equal(r.photoUsed, U2);
// A photo at the floor is picked over the photos before it that sit under it.
r = pickWith(flipped, URLS, reply({ p1: score(1), p2: score(1.999), p3: score(2) }));
assert.equal(r.jevPick, U3);
assert.equal(r.photoUsed, U3);
r = pickWith(flipped, URLS, reply({ p3: score(2) }));
assert.equal(r.jevPick, U3);
assert.equal(r.photoUsed, U3);
// Today's choice (photo 1) is demoted when Jev scores it 0 and another is usable.
assert.equal(pickWith(flipped, URLS, reply({ p1: score(0), p2: score(2), p3: score(0) })).photoUsed, U2);

// A response from another model, or with no model, is ignored whole. The model
// name has to start with "jev-", so "jev" and "jevx" are not Jev models, and the
// same answer under "jev-latest" and "jev-1.13.0" does count.
for (const bad of [reply({ p2: score(3) }, "gpt-5"), reply({ p2: score(3) }, ""), reply({ p2: score(3) }, "jev"), reply({ p2: score(3) }, "jevx"), { json: { answers: { p2: score(3) } } }, { json: { model: 7, answers: { p2: score(3) } } }]) {
  assert.equal(pickWith(flipped, URLS, bad).jevPick, null, JSON.stringify(bad.json && bad.json.model));
  assert.equal(pickWith(flipped, URLS, bad).photoUsed, U1);
}
for (const good of ["jev-latest", "jev-1.13.0", "jev-1.14.0"]) assert.equal(pickWith(flipped, URLS, reply({ p2: score(3) }, good)).jevPick, U2, good);
// A malformed answer is ignored while a good one beside it still counts.
const malformed = [
  { type: "noul", noul: 0.9 },
  { type: "score", score: NaN },
  { type: "score", score: Infinity },
  { type: "score", score: 3.5 },
  { type: "score", score: -0.5 },
  { type: "score", score: "3" },
  { type: "score" },
  { score: 3 },
  null,
  "3",
  3,
];
for (const bad of malformed) {
  assert.equal(pickWith(SHIPPED, URLS, reply({ p1: bad })).jevPick, null, JSON.stringify(bad));
  assert.equal(pickWith(SHIPPED, URLS, reply({ p1: bad, p3: score(2) })).jevPick, U3, JSON.stringify(bad));
}
// A response with no answers, answers that are not an object, a null item and an error item.
for (const bad of [{ json: { model: "jev-latest" } }, { json: { model: "jev-latest", answers: null } }, { json: { model: "jev-latest", answers: "p1" } }, null, {}, { json: { error: { message: "timeout" } } }]) {
  assert.equal(pickWith(SHIPPED, URLS, bad).jevPick, null);
  assert.equal(pickWith(SHIPPED, URLS, bad, reply({ p2: score(2) })).jevPick, U2);
}

// FIRST WINS, twice. The spec is silent on both, so these pin the shipped choice
// rather than a ruling, and a change to either is a decision to make on purpose.
// A url that two questions were about keeps the score of the first of them. Here
// p1 and p3 are both about U1: p1 scores 1 and p3 scores 3. First wins, so U1
// stays at 1 and U2 at 2 is the best; last wins would make U1 the pick at 3.
assert.equal(pickWith(SHIPPED, [U1, U2, U1], reply({ p1: score(1), p2: score(2), p3: score(3) })).jevPick, U2);
assert.equal(pickWith(SHIPPED, [U1, U2, U1], reply({ p1: score(3), p2: score(2), p3: score(1) })).jevPick, U1);
// With several Rank items, the first item to answer a name keeps it. The first
// reply says p1 is 1 and p2 is 3, the second says the reverse. First wins gives
// U2; the second reply winning would give U1. A name only the later reply
// answers still counts, so the replies are merged and not just the first read.
assert.equal(pickWith(SHIPPED, URLS, reply({ p1: score(1), p2: score(3) }), reply({ p1: score(3), p2: score(1) })).jevPick, U2);
assert.equal(pickWith(SHIPPED, URLS, reply({ p1: score(3), p2: score(1) }), reply({ p1: score(1), p2: score(3) })).jevPick, U1);
assert.equal(pickWith(SHIPPED, URLS, reply({ p1: score(1) }), reply({ p1: score(2), p3: score(2) })).jevPick, U3);

// A score is matched to a photo by the url the question was about, not by the
// photo's place in the list. urls[k-1] is what p{k} was asked about.
assert.equal(pickWith(SHIPPED, [U3, U1], reply({ p1: score(3), p2: score(1) })).jevPick, U3);
assert.equal(pickWith(SHIPPED, [U1, null, U3], reply({ p2: score(3), p3: score(2) })).jevPick, U3);
// An answer with no url behind it, and a url that is not one of the photos, score nothing.
assert.equal(pickWith(SHIPPED, [U1], reply({ p2: score(3) })).jevPick, null);
assert.equal(pickWith(SHIPPED, ["https://images.pexels.com/photos/9/other.jpeg"], reply({ p1: score(3) })).jevPick, null);
// Fail open when either Jev node did not run, or urls is not a list.
const bodyNode = jevNodes(URLS)["Jev: Thumb Body"];
const rankNode = { all: () => [reply({ p2: score(3) })] };
assert.equal(runPick(flipped, { json: THREE, jev: { "Jev: Rank Stills": rankNode } }).jevPick, null);
assert.equal(runPick(flipped, { json: THREE, jev: { "Jev: Thumb Body": bodyNode } }).jevPick, null);
assert.equal(runPick(flipped, { json: THREE, jev: { "Jev: Thumb Body": { first: () => ({ json: { urls: "none" } }) }, "Jev: Rank Stills": rankNode } }).jevPick, null);
assert.equal(runPick(flipped, { json: THREE, jev: { "Jev: Thumb Body": { first: () => { throw new Error("no item"); } }, "Jev: Rank Stills": rankNode } }).jevPick, null);
assert.equal(runPick(flipped, { json: THREE, jev: { "Jev: Thumb Body": bodyNode, "Jev: Rank Stills": { all: () => { throw new Error("no items"); } } } }).photoUsed, U1);
// A Jev pick on a photo whose src has only a large url still reports that url.
const bigOnly = photo(4001); delete bigOnly.src.landscape; delete bigOnly.src.large2x;
r = runPick(flipped, { json: response([P1, bigOnly]), jev: jevNodes([U1, bigOnly.src.large], reply({ p1: score(2), p2: score(3) })) });
assert.equal(r.jevPick, bigOnly.src.large);
assert.equal(r.photoUsed, bigOnly.src.large);
// A photo with large2x and no landscape is matched on its large2x url, the same
// key Jev: Thumb Stills builds (landscape, then large2x, then large). The photo
// also has a large url, a different one, so a fallback that skipped large2x would
// look for a key nobody scored. The urls come from the Stills node itself.
const twoX = photo(4002); delete twoX.src.landscape;
assert.notEqual(twoX.src.large2x, twoX.src.large);
const twoXJson = response([P1, twoX]);
const twoXUrls = stillsOf(twoXJson).map((s) => s.url);
assert.deepEqual(twoXUrls, [U1, twoX.src.large2x]);
r = runPick(flipped, { json: twoXJson, jev: jevNodes(twoXUrls, reply({ p1: score(2), p2: score(3) })) });
assert.equal(r.jevPick, twoX.src.large2x);
assert.equal(r.photoUsed, twoX.src.large2x);
assert.equal(r.photographer, "Photographer 4002");
// In shadow it reports the same pick and moves nothing.
r = runPick(SHIPPED, { json: twoXJson, jev: jevNodes(twoXUrls, reply({ p1: score(2), p2: score(3) })) });
assert.equal(r.jevPick, twoX.src.large2x);
assert.equal(r.photoUsed, U1);
// A score filed under that photo's large url is not its score, because Pick Still
// keys the photo by large2x. Only photo 1 is scored here, so it is the pick.
r = runPick(flipped, { json: twoXJson, jev: jevNodes([U1, twoX.src.large], reply({ p1: score(2), p2: score(3) })) });
assert.equal(r.jevPick, U1);
assert.equal(r.photoUsed, U1);

console.log("Jev thumbnail rank: every case behaves");
