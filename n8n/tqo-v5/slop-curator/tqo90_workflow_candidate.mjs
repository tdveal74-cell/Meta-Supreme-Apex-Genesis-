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
    "const DOCTOR_FLOOR = ['NCO', 'NCO_FORGE'].includes(String($('Show Context: Script').first().json.show || '').toUpperCase()) ? 70 : 90; // TQO only, 2026-10-19"
  );
  // Explicit fail-closed staging boundary. A score of 90 is not equivalent to
  // a trusted signed handoff; until an authenticated adapter is wired, no TQO
  // script may advance even if the old Script Doctor score was high enough.
  const pendingAnchor = "const failures = [];";
  if (nextScriptCode.split(pendingAnchor).length !== 2) throw new Error("Script Gate failures anchor drifted");
  const stageScriptCode = nextScriptCode.replace(
    pendingAnchor,
    pendingAnchor + "\nif (!['NCO','NCO_FORGE'].includes(String($('Show Context: Script').first().json.show || '').toUpperCase())) failures.push('TQO signed final-text review adapter not yet wired');"
  );
  const showAnchor = "const show = (String(f.brand || '').toUpperCase() === 'NCO') ? 'NCO_FORGE' : (String(f.show || '').toUpperCase() === 'TSWS' ? 'TSWS' : 'TQO');";
  if (complianceQcCode.split(showAnchor).length !== 2) throw new Error("QC show/brand anchor drifted");
  const aliasSafeQcCode = complianceQcCode.replace(
    showAnchor,
    "const brandTag = String(f.brand || f.show || '').toUpperCase();\\nconst show = ['NCO','NCO_FORGE'].includes(brandTag) ? 'NCO_FORGE' : (brandTag === 'TSWS' ? 'TSWS' : 'TQO');"
  );
  const qcAnchor = "const DOCTOR_FLOOR = 70;";
  if (aliasSafeQcCode.split(qcAnchor).length !== 2) throw new Error("QC Doctor floor anchor drifted");
  const nextQcCode = aliasSafeQcCode.replace(
    qcAnchor,
    "const DOCTOR_FLOOR = show === 'TQO' ? 90 : 70; // preserve NCO floor, 2026-10-19"
  );

  const qcResultAnchor = "const result = gate(gateInput);";
  if (nextQcCode.split(qcResultAnchor).length !== 2) throw new Error("QC Gate final result anchor drifted");
  const stageQcCode = nextQcCode.replace(
    qcResultAnchor,
    qcResultAnchor + "\nif (show === 'TQO' && result.state === 'READY_FOR_HUMAN_REVIEW') return [{ json: { doctorGate: 'HOLD', doctorGateReason: 'TQO signed final-text review adapter not yet wired', qc_score: score, qc_verdict: verdict, rowId: f.id } }];"
  );
  const candidate = structuredClone(pinnedExport);
  candidate.nodes.find(n => n.name === "Script Gate: Quality").parameters.jsCode = stageScriptCode;
  candidate.nodes.find(n => n.name === "QC Doctor Gate").parameters.jsCode = stageQcCode;
  return { candidate, scriptCode: stageScriptCode, qcCode: stageQcCode };
}
