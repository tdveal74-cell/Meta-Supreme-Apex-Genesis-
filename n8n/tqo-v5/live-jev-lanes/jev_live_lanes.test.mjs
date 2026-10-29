/**
 * The three Jev image lanes as published in TQO FINAL V5, ruled by Tee on
 * 2026-10-27 on three cards: "Standalone harness", "Draft now, publish card
 * next" and "Publish now":
 *
 *   node n8n/tqo-v5/live-jev-lanes/jev_live_lanes.test.mjs
 *
 * published.json is the 14 added nodes, the 3 changed nodes, the 14 added edges
 * and the positions of the 3 sibling nodes, copied from the read back of version
 * 3db61aef. This test holds the repo to that copy: every Code node runs exactly
 * the repo file the manifest names, every other node carries the settings
 * JEV_WIRING.md gives it, and each side branch sits above its sibling so that
 * n8n's v1 order runs it first. It reads no live data. A later live edit that is
 * not copied back here is caught only by a read back, not by this test.
 */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";

const read = (rel) => readFileSync(new URL(rel, import.meta.url), "utf8");
const sha = (s) => createHash("sha256").update(s, "utf8").digest("hex");
const M = JSON.parse(read("./manifest.json"));
const P = JSON.parse(read("./published.json"));
let checks = 0;
const eq = (a, b, msg) => { assert.deepEqual(a, b, msg); checks++; };
const ok = (v, msg) => { assert.ok(v, msg); checks++; };

// ---- The copy is the version the manifest names --------------------------------
eq(M.workflowId, "qEkGOUsNyVaRAmm6", "TQO FINAL V5");
eq(P.workflowId, M.workflowId, "published.json is the same workflow");
eq(P.versionId, M.current.versionId, "published.json is the current version the manifest names");
eq(M.rollbackAtPublish, "publish " + M.before.versionId, "at publish, rollback was the version before");
ok(!M.rollback.startsWith("publish ") && M.rollback.includes(M.before.versionId.slice(0, 8) + " on 2026-10-28 returned 404"), "the before version is pruned, so rollback is an edit, not a publish");
{
  const jev = P.nodes.filter((n) => n.name.startsWith("Jev: ")).length;
  ok(M.rollback.includes("removing the " + jev + " Jev nodes and their " + P.newEdges.length + " edges"), "rollback counts the Jev nodes and edges the published copy holds");
}
const byName = new Map(P.nodes.map((n) => [n.name, n]));
eq(byName.size, P.nodes.length, "no node name appears twice");
eq(P.nodes.length, 17, "14 added nodes and 3 changed ones");

// ---- Every node is pinned whole ---------------------------------------------------
// published.json holds every key of each published node except the id n8n
// assigns, so a setting the live node gained (disabled, retryOnFail,
// executeOnce, a mode, a credential) would sit in the copy and fail here. Each
// node below is compared whole, minus its name and position, which are checked
// on their own further down.
const whole = (n) => { const { name, position, ...rest } = n; return rest; };

// ---- Every Code node runs the repo file, at the sha the manifest names ---------
const CODE = Object.entries(M.code);
eq(CODE.length, 9, "six new Code nodes and three changed ones");
const NOTES = { "Thumb: Pick Still": "Chooses the backdrop and computes the type layout. No render call." };
for (const [name, { file, sha256 }] of CODE) {
  const body = read("../" + file);
  eq(sha(body), sha256, file + " is the body the manifest names");
  const n = byName.get(name);
  ok(n, name + " is in the published copy");
  const want = { type: "n8n-nodes-base.code", typeVersion: 2, parameters: { jsCode: body } };
  if (NOTES[name]) want.notes = NOTES[name];
  eq(whole(n), want, name + " is a Code node 2 running " + file + " byte for byte, run once for all items, with no other setting");
}

// ---- The model is pinned in every request body ---------------------------------
for (const file of ["jev_broll_bodies.js", "jev_thumb_body.js", "jev_thumb_check_body.js"]) {
  const body = read("../" + file);
  const models = [...body.matchAll(/model: '([^']*)'/g)].map((m) => m[1]);
  eq(models, ["jev-1.14.0"], file + " sends the pinned jev-1.14.0 and no other model");
}

// ---- The HTTP and Extract From File nodes carry the settings in JEV_WIRING.md ---
// A custom header goes out only while sendHeaders is true, and without the
// images header TypeSafe refuses every image request with 400, which these
// nodes would swallow. So sendHeaders is pinned with the rest.
const RANK = ["Jev: Rank B-Roll", "Jev: Rank Stills", "Jev: Check Thumb"];
for (const name of RANK) {
  eq(whole(byName.get(name)), {
    type: "n8n-nodes-base.httpRequest", typeVersion: 4.2,
    parameters: {
      method: "POST", url: "https://api.typesafe.ai/v1/systemone",
      authentication: "genericCredentialType", genericAuthType: "httpHeaderAuth",
      sendHeaders: true, headerParameters: { parameters: [{ name: "TypeSafe-Danger-Zone-Images", value: "true" }] },
      sendBody: true, specifyBody: "json", jsonBody: "={{ JSON.stringify($json.body) }}",
      options: { timeout: 30000 },
    },
    credentials: { httpHeaderAuth: { id: "AJM16uvmcW88bSL4", name: "Jev" } },
    onError: "continueRegularOutput", alwaysOutputData: true,
  }, name + " posts its body to System One with the images header and the Jev credential, 30 s, no retry, fails open");
}
const FETCH = { "Jev: Fetch B-Roll Still": "={{ $json.stillUrl }}", "Jev: Fetch Thumb Still": "={{ $json.fetchUrl }}" };
for (const [name, url] of Object.entries(FETCH)) {
  eq(whole(byName.get(name)), {
    type: "n8n-nodes-base.httpRequest", typeVersion: 4.2,
    parameters: { url, options: { response: { response: { responseFormat: "file" } }, timeout: 10000 } },
    onError: "continueRegularOutput", alwaysOutputData: true,
  }, name + " fetches " + url + " as a file in 10 s with no credential, once per item, and keeps an item on failure");
}
const EXTRACT = { "Jev: Still To Base64": "data", "Jev: Thumb To Base64": "data", "Jev: Thumb To Base64 (Composed)": "thumbData" };
for (const [name, prop] of Object.entries(EXTRACT)) {
  eq(whole(byName.get(name)), {
    type: "n8n-nodes-base.extractFromFile", typeVersion: 1.1,
    parameters: { operation: "binaryToPropery", binaryPropertyName: prop, destinationKey: "still_b64" },
    onError: "continueRegularOutput",
  }, name + " moves " + prop + " to still_b64 and fails open");
}
eq(CODE.length + RANK.length + Object.keys(FETCH).length + Object.keys(EXTRACT).length, P.nodes.length, "every published node is checked above");

// ---- The edges, and the order v1 runs them in ----------------------------------
const EDGES = [
  ["Pexels Search", "Jev: B-Roll Stills"], ["Jev: B-Roll Stills", "Jev: Fetch B-Roll Still"],
  ["Jev: Fetch B-Roll Still", "Jev: Still To Base64"], ["Jev: Still To Base64", "Jev: B-Roll Bodies"],
  ["Jev: B-Roll Bodies", "Jev: Rank B-Roll"],
  ["Thumb: Find Still", "Jev: Thumb Stills"], ["Jev: Thumb Stills", "Jev: Fetch Thumb Still"],
  ["Jev: Fetch Thumb Still", "Jev: Thumb To Base64"], ["Jev: Thumb To Base64", "Jev: Thumb Body"],
  ["Jev: Thumb Body", "Jev: Rank Stills"],
  ["Thumb: Compose", "Jev: Thumb To Base64 (Composed)"], ["Jev: Thumb To Base64 (Composed)", "Jev: Thumb Check Body"],
  ["Jev: Thumb Check Body", "Jev: Check Thumb"], ["Jev: Check Thumb", "Jev: Thumb Verdict"],
];
const key = (e) => e.join(" -> ");
eq(P.newEdges.map(key).sort(), EDGES.map(key).sort(), "the 14 added edges and no others");
// v1 runs the children of a node top to bottom on the canvas, one branch to its
// end before the next, so each side branch must sit above the node its consumer
// reaches by the existing edge. Harness execution 4737 ran in that order.
const FORKS = [
  ["Jev: B-Roll Stills", "Plan Presenter Segments"],
  ["Jev: Thumb Stills", "Thumb: Pick Still"],
  ["Jev: Thumb To Base64 (Composed)", "Shim: Thumbnail To Binary"],
];
for (const [side, sibling] of FORKS) {
  ok(byName.get(side).position[1] < P.siblingPositions[sibling][1], side + " sits above " + sibling + ", so it runs first");
  if (byName.has(sibling)) eq(byName.get(sibling).position, P.siblingPositions[sibling], sibling + " has one position in the copy, not two");
}

// ---- Shadow ---------------------------------------------------------------------
for (const file of ["build_movie.js", "thumb_pick_still.js", "shim_thumbnail_to_binary.js"]) {
  const flags = [...read("../" + file).matchAll(/const JEV_APPLY = (\w+);/g)].map((m) => m[1]);
  eq(flags, ["false"], file + " ships with JEV_APPLY false");
}

// ---- No key and no dash in what this folder holds --------------------------------
const DASH = new RegExp("[" + String.fromCharCode(0x2013, 0x2014) + "]");
for (const f of ["./manifest.json", "./published.json"]) {
  const text = read(f);
  ok(!/Bearer|sk-[A-Za-z0-9]/.test(text), f + " carries no key");
  ok(!DASH.test(text), f + " carries no em or en dash");
}

console.log("Jev lanes live: the published copy runs the repo bodies, in shadow, " + checks + " checks");
