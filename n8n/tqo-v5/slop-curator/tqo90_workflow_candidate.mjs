/**
 * Produce an OFFLINE, NON-DEPLOYED candidate from the pinned TQO/NCO V5 export.
 * Never modifies the source JSON or writes to n8n. This is deliberately NOT
 * a production activation: final-draft review and a trusted ChatGPT handoff
 * remain mandatory before any deployment.
 */
export function buildTqo90Candidate(pinnedExport, complianceQcCode) {
  if (!pinnedExport || !Array.isArray(pinnedExport.nodes)) throw new Error("pinned export missing nodes");
  if (typeof complianceQcCode !== "string" || !complianceQcCode.length) throw new Error("QC mirror missing");
  const targetNames = ["Script Gate: Quality", "QC Doctor Gate"];
  for (const name of targetNames) {
    if (pinnedExport.nodes.filter(n => n.name === name).length !== 1) {
      throw new Error("expected exactly one " + name);
    }
  }
  const originalScriptCode = pinnedExport.nodes.find(n => n.name === "Script Gate: Quality").parameters?.jsCode;
  if (typeof originalScriptCode !== "string") throw new Error("Script Gate code missing");
  const scriptAnchor = "const DOCTOR_FLOOR = 70;      // out of 100; QC ships at 80, the doctor holds at 70";
  if (originalScriptCode.split(scriptAnchor).length !== 2) throw new Error("Script Gate floor anchor drifted");

  // In this shared workflow Show Context: Script uses NCO for the military lane.
  const nextScriptCode = originalScriptCode.replace(
    scriptAnchor,
    "const DOCTOR_FLOOR = $('Show Context: Script').first().json.show === 'NCO' ? 70 : 90; // TQO only, 2026-10-19"
  );
  const qcAnchor = "const DOCTOR_FLOOR = 70;";
  if (complianceQcCode.split(qcAnchor).length !== 2) throw new Error("QC Doctor floor anchor drifted");
  const nextQcCode = complianceQcCode.replace(
    qcAnchor,
    "const DOCTOR_FLOOR = show === 'TQO' ? 90 : 70; // preserve NCO floor, 2026-10-19"
  );

  const candidate = structuredClone(pinnedExport);
  candidate.nodes.find(n => n.name === "Script Gate: Quality").parameters.jsCode = nextScriptCode;
  candidate.nodes.find(n => n.name === "QC Doctor Gate").parameters.jsCode = nextQcCode;
  return { candidate, scriptCode: nextScriptCode, qcCode: nextQcCode };
}
