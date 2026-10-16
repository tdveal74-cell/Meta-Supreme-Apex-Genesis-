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
// Headers only. The node reads the base64 prefix and never decodes the image.
const JPEG = Buffer.from([0xff, 0xd8, 0xff, 0xe0, 0x00, 0x10, 0x4a, 0x46, 0x49, 0x46, 0x00, 0x01, 0x01, 0x00]).toString("base64");
const PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==";
const GIF = "R0lGODlhAQABAAAAACw=";
const WEBP = "UklGRhYAAABXRUJQVlA4TAoAAAAvAAAAAAfQ";
assert.ok(JPEG.startsWith("/9j/") && PNG.startsWith("iVBORw0KGgo"));

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
  "Unusable: dark, cluttered, blurred, carrying text or a watermark, or unrelated to the subject",
  "Usable but unrelated to the subject",
  "Fits the subject, but what matters sits under the dark panel on the left",
  "Fits the subject, and what matters sits in the right part of the frame where it stays visible",
];

// Three usable stills make one item, one score question each.
let out = bodyOf([JPEG, PNG, JPEG]);
assert.equal(out.length, 1);
assert.deepEqual(out[0].json.urls, [U1, U2, U3]);
let body = out[0].json.body;
assert.equal(body.model, "jev-latest");
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
// A stills item with no usable k or url is not trusted.
assert.deepEqual(bodyOf([JPEG], { stillItems: [{ k: 0, url: U1 }] }), []);
assert.deepEqual(bodyOf([JPEG], { stillItems: [{ k: 1 }] }), []);

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

// ---- thumb_pick_still.js -------------------------------------------------------
const ORIGINAL = exportCode("Thumb: Pick Still");
const SHIPPED = src("thumb_pick_still.js");
const flipped = SHIPPED.replace("const JEV_APPLY = false;", "const JEV_APPLY = true;");
assert.notEqual(flipped, SHIPPED, "the shipped file declares JEV_APPLY = false");
assert.match(SHIPPED, /^const JEV_APPLY = false;$/m);

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
assert.equal(pickWith(SHIPPED, URLS, reply({ p1: score(1), p2: score(1), p3: score(1) })).jevPick, U1);
// Scores are floats; 2.6 beats 2.4. Exactly 1 qualifies and 0.99 does not.
assert.equal(pickWith(SHIPPED, URLS, reply({ p1: score(2.4), p2: score(1.1), p3: score(2.6) })).jevPick, U3);
assert.equal(pickWith(SHIPPED, URLS, reply({ p1: score(0.99), p2: score(1) })).jevPick, U2);
// The rule is a highest score of 1 or more: a lone score under 1 is not a pick,
// and a lone score of exactly 1 is. Before this, nothing pinned the floor on its
// own, because a 0.99 beside a 1 still gave the right photo by the tie rule.
assert.equal(pickWith(SHIPPED, URLS, reply({ p1: score(0.5) })).jevPick, null);
assert.equal(pickWith(SHIPPED, URLS, reply({ p1: score(1) })).jevPick, U1);
assert.equal(pickWith(SHIPPED, URLS, reply({ p1: score(0.99) })).jevPick, null);
assert.equal(pickWith(SHIPPED, URLS, reply({ p3: score(0.5) })).jevPick, null);
// Applied, a lone 0.5 on photo 2 moves nothing and a lone 1 on photo 2 does.
r = pickWith(flipped, URLS, reply({ p2: score(0.5) }));
assert.equal(r.jevPick, null);
assert.equal(r.photoUsed, U1);
r = pickWith(flipped, URLS, reply({ p2: score(1) }));
assert.equal(r.jevPick, U2);
assert.equal(r.photoUsed, U2);
// A photo scored 0 is never chosen, and neither is one nobody scored.
r = pickWith(flipped, URLS, reply({ p1: score(0), p2: score(0), p3: score(0) }));
assert.equal(r.jevPick, null);
assert.equal(r.photoUsed, U1);
r = pickWith(flipped, URLS, reply({ p1: score(0), p2: score(1) }));
assert.equal(r.jevPick, U2);
assert.equal(r.photoUsed, U2);
r = pickWith(flipped, URLS, reply({ p3: score(2) }));
assert.equal(r.jevPick, U3);
assert.equal(r.photoUsed, U3);
// Today's choice (photo 1) is demoted when Jev scores it 0 and another is usable.
assert.equal(pickWith(flipped, URLS, reply({ p1: score(0), p2: score(2), p3: score(0) })).photoUsed, U2);

// A response from another model, or with no model, is ignored whole.
for (const bad of [reply({ p2: score(3) }, "gpt-5"), reply({ p2: score(3) }, ""), { json: { answers: { p2: score(3) } } }, { json: { model: 7, answers: { p2: score(3) } } }]) {
  assert.equal(pickWith(flipped, URLS, bad).jevPick, null);
}
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
  assert.equal(pickWith(SHIPPED, URLS, reply({ p1: bad, p3: score(1) })).jevPick, U3, JSON.stringify(bad));
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
r = runPick(flipped, { json: response([P1, bigOnly]), jev: jevNodes([U1, bigOnly.src.large], reply({ p1: score(1), p2: score(3) })) });
assert.equal(r.jevPick, bigOnly.src.large);
assert.equal(r.photoUsed, bigOnly.src.large);

console.log("Jev thumbnail rank: every case behaves");
