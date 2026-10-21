/**
 * On authorized n8n host only:
 * QUALITY90_CAPTURE_PATH=/private/live-export.json node live_v5_offline_smoke.mjs
 *
 * Pure offline tests against a fingerprint-verified live export. No network,
 * credentials, provider invocations, workflow updates, or publication.
 * Never commit real export files or print source scripts.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { buildLiveUniversal90Candidate } from "./live_v5_universal90_candidate.mjs";

const path = process.env.QUALITY90_CAPTURE_PATH;
if (!path) throw new Error("private, attested live export path required");
const sourceText = readFileSync(path, "utf8");
const baseline = JSON.parse(sourceText);
const original = Array.isArray(baseline) ? baseline[0] : baseline;
const { candidate, report } = buildLiveUniversal90Candidate(sourceText);
const changed = Array.isArray(candidate) ? candidate[0] : candidate;
const originalNodes = Object.fromEntries(original.nodes.map(n => [n.name, n]));
const candidates = Object.fromEntries(changed.nodes.map(n => [n.name, n]));
const names = changed.nodes.filter(n =>
  n.parameters?.jsCode !== originalNodes[n.name]?.parameters?.jsCode
).map(n => n.name).sort();
assert.deepEqual(names, [
  "OS 28: Publish Gate", "Parse QC + Set Verdict",
  "QC Doctor Gate", "Script Gate: Quality",
]);
assert.equal(original.active, true);
assert.equal(changed.active, false);
assert.equal(Object.hasOwn(changed, "id"), false);
assert.deepEqual(changed.connections, original.connections);
assert.deepEqual(changed.settings, original.settings);
assert.deepEqual(changed.nodes.map(n => n.credentials),
                 original.nodes.map(n => n.credentials));

const executable = name => new Function("$", "$json", "$input",
  candidates[name].parameters.jsCode);
for (const name of names) executable(name);

const stub = data => name => {
  if (!(name in data)) throw new Error("synthetic node missing: " + name);
  return { first: () => ({ json: data[name] }) };
};
let assertions = 0;
function scriptGate(brand, score) {
  const obj = "Check what this model returned";
  const script = obj + " " +
    "A workplace test begins with the published source and a human check. ".repeat(115)
    + "What evidence would you share in the comments?";
  const json = {
    script, title:"The Quiet Test", description:"Source checks for a working manager.",
    broll:"desk,screen,report,notebook,team,source",
    learningObjective:obj, checklist:["Compare source","Test output","Record gaps"],
    doctorScore:score, doctorVerdict:"PASS", rhythmScore:75, similarityScore:75,
  };
  return executable("Script Gate: Quality")(stub({
    "Show Context: Script": { show: brand },
    "Build Doctor Prompt": {original:{draftWords:1400,expansion:"not needed"}},
    "DEVON Recall: Merge": {devonRecallNote:"synthetic recall fixture"},
  }), json, undefined)[0].json;
}
for (const brand of ["TQO","NCO"]) {
  const fail = scriptGate(brand, 89);
  assert.equal(fail.status, "Error");
  assert.ok(fail.gateFailures.some(x => x.includes("under the floor of 90")));
  for (const score of [90,100]) {
    const result = scriptGate(brand, score);
    assert.equal(result.status, "Error");
    assert.ok(result.gateFailures.some(x => x.includes("independent final-script receipt not yet integrated")));
    assert.ok(!result.gateFailures.some(x => x.includes("under the floor of 90")));
    assertions += 2;
  }
}
function episodeGate(show, total, blockers=[]) {
  const response = {choices:[{finish_reason:"stop",message:{content:JSON.stringify({
    scores:{hook:20}, total, blockers, findings:[], batch_score:9,
  })}}]};
  return executable("Parse QC + Set Verdict")(stub({
    "Show Context: Publish":{show,channel:show},
    "One Row at a Time":{fields:{id:7,Show:show,Season:1,Episode:1}},
    "Build QC Prompt":{airtableId:7},
  }),response,undefined)[0].json;
}
for (const brand of ["TQO","NCO"]) {
  assert.equal(episodeGate(brand,89).qcVerdict,"HOLD");
  assert.equal(episodeGate(brand,90).qcVerdict,"SHIP");
  assert.equal(episodeGate(brand,100,["unsourced claim"]).qcVerdict,"HOLD");
  assertions += 3;
}
function downstreamGate(brand, score) {
  return executable("QC Doctor Gate")(stub({
    "One Row at a Time": { fields: {
      id:7, brand, show:brand, updatedAt:"2026-10-19",
      score_history:"2026-10-19 | doctor "+score+"/100 PASS |",
    }},
    "Parse QC + Set Verdict":{qcScore:92,qcVerdict:"SHIP"},
  }),undefined,undefined)[0].json;
}
for (const brand of ["TQO","NCO"]) {
  for (const score of [89,90,100]) {
    const g=downstreamGate(brand,score);
    assert.notEqual(g.doctorGate,"READY_FOR_HUMAN_REVIEW");
    assert.notEqual(g.doctorGate,"RELEASE_ELIGIBLE");
    assertions+=2;
  }
}
// Publication is held until the independent final artifact review is connected.
// Both the manual WAIVED escape hatch and an otherwise passing 100 are blocked.
const pubCode=candidates["OS 28: Publish Gate"].parameters.jsCode;
assert.match(pubCode,/blocking\.push\('Universal 90 independent final-script receipt not yet integrated'\)/);
assert.match(pubCode,/gates\.qc = verdict === 'SHIP' &&/);
assert.doesNotMatch(pubCode,/gates\.qc = verdict === 'SHIP' \|\| verdict === 'WAIVED'/);
assertions += 3;

console.log(JSON.stringify({
  result:"PASS", tests:"synthetic 89/90/100, evidence HOLD, manual-waiver check",
  assertions, workflowSourceSha256:report.sourceSha256,
  changedNodes:names, preservedNodes:original.nodes.length-names.length,
  candidateActive:false, candidateHasLiveId:false,
  actualLiveWorkflowAltered:false
}));
