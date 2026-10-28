/**
 * Universal-90 acceptance check for the shared TQO/NCO V5 workflow.
 * No connection to n8n and NO production deployment.
 *
 * History: this file used to patch the pinned export (script doctor floor 70
 * to 90, SHIP 80 to 90) and inject a HOLD for a pending signed AI review
 * adapter. Both are over. The 90 floors are live, and on 2026-10-28 the owner
 * ruled "Drop the AI review from the publish gate": Preflight, QC Doctor Gate
 * and OS 28 no longer require a signed quality90 AI review receipt. The script
 * slot is carried by the script doctor at a floor of 90, and the human
 * approval approved:<sha256 of the script> is still required.
 *
 * So nothing is rewritten now. The function asserts that each live node still
 * carries the anchors the tests depend on, throws on drift, and returns the
 * export unchanged. Re-pinning the export is a separate commit.
 */
const requireOnce = (code, text, label) => {
  if (typeof code !== "string" || code.split(text).length !== 2) {
    throw new Error(label + " anchor drifted");
  }
};
const requireAbsent = (code, text, label) => {
  if (typeof code !== "string" || code.includes(text)) {
    throw new Error(label + " anchor drifted");
  }
};

export function buildUniversal90Candidate(pinnedExport) {
  if (!pinnedExport || !Array.isArray(pinnedExport.nodes)) throw new Error("pinned export missing nodes");
  const names = ["Script Gate: Quality", "Parse QC + Set Verdict", "QC Doctor Gate", "OS 28: Publish Gate"];
  for (const name of names) {
    if (pinnedExport.nodes.filter(n => n.name === name).length !== 1) {
      throw new Error("expected exactly one " + name);
    }
  }
  const sourceNode = name => pinnedExport.nodes.find(n => n.name === name).parameters.jsCode;
  const scriptCode = sourceNode("Script Gate: Quality");
  const parseCode = sourceNode("Parse QC + Set Verdict");
  const qcCode = sourceNode("QC Doctor Gate");
  const publishCode = sourceNode("OS 28: Publish Gate");

  requireOnce(scriptCode, "const DOCTOR_FLOOR = 90;", "Script Gate floor");
  requireOnce(parseCode, "const SHIP_AT = 90;", "QC parser SHIP floor");
  requireOnce(qcCode, "const DOCTOR_FLOOR = 90;", "QC Doctor Gate doctor floor");
  requireOnce(qcCode, "r.score < 90", "QC Doctor Gate score floor");
  requireOnce(qcCode, "score < 90 ? 1 : 0", "QC Doctor Gate episode floor");
  requireOnce(
    publishCode,
    "gates.qc = verdict === 'SHIP' && Number.isFinite(Number(qc.qcScore)) && Number(qc.qcScore) >= 90;",
    "OS 28 QC floor"
  );
  requireOnce(publishCode, "gates.authorship = reviewStr === 'approved:' + aiFinalHash;", "OS 28 approval hash binding");
  // No AI review hold may come back into the publish path.
  for (const [label, code] of [["Script Gate", scriptCode], ["QC Doctor Gate", qcCode], ["OS 28", publishCode]]) {
    requireAbsent(code, "signed final-text review adapter not yet wired", label + " pending AI review hold");
  }
  return { candidate: structuredClone(pinnedExport), scriptCode, parseCode, qcCode, publishCode };
}
// Legacy export preserved for callers created while TQO alone had a 90 target.
export const buildTqo90Candidate = buildUniversal90Candidate;
