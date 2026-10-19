/**
 * Offline universal-90 quality candidate for the shared TQO/NCO V5 workflow.
 * No connection to n8n and NO production deployment.
 * Scores below 90 always fail; scores >= 90 remain HOLD until trusted final-
 * script review is wired into both script and downstream quality paths.
 */
const replaceOnce = (code, oldText, newText, label) => {
  if (typeof code !== "string" || code.split(oldText).length !== 2) {
    throw new Error(label + " anchor drifted");
  }
  return code.replace(oldText, newText);
};

export function buildUniversal90Candidate(pinnedExport, complianceQcCode, compliancePublishCode) {
  if (!pinnedExport || !Array.isArray(pinnedExport.nodes)) throw new Error("pinned export missing nodes");
  const names = ["Script Gate: Quality", "Parse QC + Set Verdict", "QC Doctor Gate", "OS 28: Publish Gate"];
  for (const name of names) {
    if (pinnedExport.nodes.filter(n => n.name === name).length !== 1) {
      throw new Error("expected exactly one " + name);
    }
  }
  if (typeof complianceQcCode !== "string" ||
      !complianceQcCode.includes("const DOCTOR_FLOOR = 90;") ||
      !complianceQcCode.includes("r.score < 90") ||
      !complianceQcCode.includes("score < 90 ? 1 : 0")) {
    throw new Error("universal-90 QC compliance mirror missing or invalid");
  }
  const sourceNode = name => pinnedExport.nodes.find(n => n.name === name).parameters.jsCode;
  const scriptCode = replaceOnce(
    sourceNode("Script Gate: Quality"),
    "const DOCTOR_FLOOR = 70;      // out of 100; QC ships at 80, the doctor holds at 70",
    "const DOCTOR_FLOOR = 90; // universal acceptance ruling, 2026-10-19",
    "Script Gate floor"
  );
  const safeScriptCode = replaceOnce(
    scriptCode, "const failures = [];",
    "const failures = [];\nfailures.push('Universal 90 signed final-text review adapter not yet wired');",
    "Script Gate pending review"
  );
  const parseCode = replaceOnce(
    sourceNode("Parse QC + Set Verdict"),
    "const SHIP_AT = 80;",
    "const SHIP_AT = 90; // universal acceptance ruling, 2026-10-19",
    "QC parser SHIP floor"
  );
  const gateCode = replaceOnce(
    complianceQcCode,
    "const result = gate(gateInput);",
    "const result = gate(gateInput);\nif (result.state === 'READY_FOR_HUMAN_REVIEW') return [{ json: { doctorGate: 'HOLD', doctorGateReason: 'Universal 90 signed final-text review adapter not yet wired', qc_score: score, qc_verdict: verdict, rowId: f.id } }];",
    "QC final signed handoff"
  );
  if (typeof compliancePublishCode !== "string" || !compliancePublishCode.includes("gates.qc")) {
    throw new Error("publish compliance mirror missing or invalid");
  }
  const publishQcCode = replaceOnce(
    compliancePublishCode,
    "gates.qc = verdict === 'SHIP' || verdict === 'WAIVED';",
    "gates.qc = verdict === 'SHIP' && Number.isFinite(Number(qc.qcScore)) && Number(qc.qcScore) >= 90; // universal 90, WAIVED cannot bypass",
    "OS 28 quality score and waiver"
  );
  const publishCode = replaceOnce(
    publishQcCode,
    "const blocking = [];",
    "const blocking = [];\nblocking.push('Universal 90 signed final-text review adapter not yet wired');",
    "OS 28 trusted review hold"
  );
  const candidate = structuredClone(pinnedExport);
  const setCode = (name, code) => {candidate.nodes.find(n => n.name === name).parameters.jsCode = code;};
  setCode("Script Gate: Quality", safeScriptCode);
  setCode("Parse QC + Set Verdict", parseCode);
  setCode("QC Doctor Gate", gateCode);
  setCode("OS 28: Publish Gate", publishCode);
  return { candidate, scriptCode: safeScriptCode, parseCode, qcCode: gateCode, publishCode };
}
// Legacy export preserved for callers created while TQO alone had a 90 target.
export const buildTqo90Candidate = buildUniversal90Candidate;
