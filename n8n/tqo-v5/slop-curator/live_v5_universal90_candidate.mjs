/**
 * Generate an offline universal-90 candidate from the OCT 19 ACTUAL LIVE V5
 * n8n export, not the older pinned repository export.
 *
 * SAFETY: No I/O, credentials, n8n API writes, publishing or signing.
 * On any version / code drift throw before returning proposed changes.
 * Human deployment review and trusted post-expansion evidence remain blocked.
 */
import { createHash } from "node:crypto";

const sha = value => createHash("sha256").update(value, "utf8").digest("hex");
export const LIVE_V5_CAPTURE = Object.freeze({
  workflowId: "qEkGOUsNyVaRAmm6",
  updatedAt: "2026-10-19T04:02:42.508Z",
  nodeCount: 274,
  exportSha256: "ec92cddbaa5f2567640d129acfbe926a0f8ddd03df955eac75d0fb8d9e7ef629",
  nodeCodeSha256: Object.freeze({
    "Script Gate: Quality": "6facfceddc5527658592bc36937085f351f964303d66df98eb3885542297338c",
    "Parse QC + Set Verdict": "b1bc7bed4875a8b15a4498e8775d41a3e1a1b8ac1dd70579b674def24370c5ee",
    "QC Doctor Gate": "399723676ec88e5579310086a5161d2fbcdec602c0efd87eeee8fd13b9ccf568",
    "OS 28: Publish Gate": "89ae42797d233a3d01c83df64b1994393c48e3e4c95d02a9b3be53f6feba22e6",
  })
});
const TARGETS = Object.keys(LIVE_V5_CAPTURE.nodeCodeSha256);

function replaceOnce(code, before, after, label) {
  if (code.split(before).length !== 2) {
    throw new Error(label + ": live code unexpectedly changed");
  }
  return code.replace(before, after);
}
function replaceUniqueLine(code, prefix, oldPattern, newLine, label) {
  const lines = code.split("\n");
  const indices = lines.flatMap((s, i) => s.startsWith(prefix) ? [i] : []);
  if (indices.length !== 1 || !oldPattern.test(lines[indices[0]])) {
    throw new Error(label + ": expected single live threshold line");
  }
  lines[indices[0]] = newLine;
  return lines.join("\n");
}

export function buildLiveUniversal90Candidate(rawExport) {
  if (typeof rawExport !== "string" || sha(rawExport) !== LIVE_V5_CAPTURE.exportSha256) {
    throw new Error("HOLD: captured live export fingerprint mismatch; re-read live before changing anything");
  }
  const decoded = JSON.parse(rawExport);
  const workflow = Array.isArray(decoded) ? decoded[0] : decoded;
  if (!workflow || workflow.id !== LIVE_V5_CAPTURE.workflowId
    || workflow.updatedAt !== LIVE_V5_CAPTURE.updatedAt
    || workflow.nodes?.length !== LIVE_V5_CAPTURE.nodeCount
    || workflow.active !== true) {
    throw new Error("HOLD: live workflow identity, state or node count drifted");
  }
  const nodes = Object.fromEntries(TARGETS.map(name => {
    const matches = workflow.nodes.filter(n => n.name === name);
    if (matches.length !== 1 || typeof matches[0].parameters?.jsCode !== "string") {
      throw new Error("HOLD: missing or duplicate node: " + name);
    }
    const code = matches[0].parameters.jsCode;
    if (sha(code) !== LIVE_V5_CAPTURE.nodeCodeSha256[name]) {
      throw new Error("HOLD: node code fingerprint mismatch: " + name);
    }
    return [name, code];
  }));

  let script = replaceUniqueLine(nodes["Script Gate: Quality"],
    "const DOCTOR_FLOOR = ",
    /=== 'TQO'\) \? 90 : 99;/,
    "const DOCTOR_FLOOR = 90; // universal ecosystem score floor, 2026-10-19",
    "Script Doctor");
  script = replaceOnce(script, "const failures = [];",
    "const failures = [];\nfailures.push('Universal 90 independent final-script receipt not yet integrated');",
    "Script Doctor signed review");

  let parse = replaceUniqueLine(nodes["Parse QC + Set Verdict"],
    "const SHIP_AT = ",
    /=== 'TQO'\) \? 90 : 99;/,
    "const SHIP_AT = 90; // universal ecosystem score floor, 2026-10-19",
    "Episode QC");
  parse = replaceOnce(parse,
    "Nothing auto-ships unchecked. Fix the cause, or set QC Verdict to WAIVED by hand if this is a deliberate call.",
    "Nothing auto-ships unchecked. A manual waiver cannot bypass the universal quality score.",
    "Episode QC legacy waiver wording");

  let doctor = replaceOnce(nodes["QC Doctor Gate"],
    "if (x.show === 'TSWS' && (!Number.isFinite(r.score) || r.score < 99 || r.score > 100)) return {state:'REVISE', reason:'TSWS score below 99 or invalid'};",
    "if (!Number.isFinite(r.score) || r.score < 90 || r.score > 100) return {state:'REVISE', reason:'quality score below 90 or invalid'};",
    "Doctor QC TSWS exception");
  doctor = replaceOnce(doctor, "criticalOrHigh: (score < 85 ? 1 : 0), score",
    "criticalOrHigh: (score < 90 ? 1 : 0), score", "Doctor QC episode 85 floor");
  doctor = replaceOnce(doctor, "const result = gate(gateInput);",
    "const result = gate(gateInput);\nif (result.state === 'READY_FOR_HUMAN_REVIEW') return [{ json: { doctorGate: 'HOLD', doctorGateReason: 'Universal 90 independent final-script receipt not yet integrated', qc_score: score, qc_verdict: verdict, rowId: f.id } }];",
    "Doctor QC receipt required");

  let publish = replaceOnce(nodes["OS 28: Publish Gate"],
    "gates.qc = verdict === 'SHIP' || verdict === 'WAIVED';",
    "gates.qc = verdict === 'SHIP' && Number.isFinite(Number(qc.qcScore)) && Number(qc.qcScore) >= 90; // universal 90, no waiver",
    "OS28 manual waiver");
  publish = replaceOnce(publish,
    "if (verdict === 'WAIVED') notes.push('qc: publishing on WAIVED override. Creative call, on the record');",
    "if (verdict === 'WAIVED') notes.push('qc: WAIVED cannot override a missing or failing quality receipt');",
    "OS28 misleading waiver text");
  publish = replaceOnce(publish, "const blocking = [];",
    "const blocking = [];\nblocking.push('Universal 90 independent final-script receipt not yet integrated');",
    "OS28 provenance hold");

  const patch = {
    "Script Gate: Quality": script,
    "Parse QC + Set Verdict": parse,
    "QC Doctor Gate": doctor,
    "OS 28: Publish Gate": publish,
  };
  const candidate = structuredClone(decoded);
  const workflowCopy = Array.isArray(candidate) ? candidate[0] : candidate;
  for (const n of workflowCopy.nodes) if (Object.hasOwn(patch, n.name)) {
    n.parameters.jsCode = patch[n.name];
  }
  // Refuse to emit an import-ready replacement for the live workflow. A
  // separate reviewed deploy tool must bind a target ID and activate after
  // receiving authenticated authorization and a trusted final-draft adapter.
  workflowCopy.active = false;
  workflowCopy.name = "DRAFT Universal 90 Gates - NOT FOR ACTIVATION";
  delete workflowCopy.id;
  return {
    candidate,
    report: {
      sourceSha256: LIVE_V5_CAPTURE.exportSha256,
      workflowId: LIVE_V5_CAPTURE.workflowId,
      changedNodeNames: TARGETS,
      changedCodeSha256: Object.fromEntries(TARGETS.map(n => [n, sha(patch[n])])),
      state: "STAGED_ONLY_NOT_DEPLOYED",
      pending: "Trusted final-text reviewer, independent evidence signer, and human deployment authorization",
    }
  };
}
