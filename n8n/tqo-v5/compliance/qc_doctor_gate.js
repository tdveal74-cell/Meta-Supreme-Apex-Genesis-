// QC Doctor Gate - gate.js (from Tee's QC packet, implemented 2026-09-30).
// Fail-closed routing after OS 28 verdict. States:
// HOLD (invalid intake / unvalidated policy / unauthenticated approval)
// EVIDENCE_REQUIRED (scope report missing or incomplete)
// REVISE (qcVerdict not PASS, open P0/P1, or any score < 90)
// READY_FOR_HUMAN_REVIEW (all scopes clear, awaiting authenticated approval)
// RELEASE_ELIGIBLE (approval authenticated and bound to artifact hash)
function gate(x) {
  const hold = reason => ({state:'HOLD', reason});
  if (!x || !['TSWS','TQO','NCO_FORGE','ACX'].includes(x.show) || !x.artifactHash || !x.rubricVersion || !Array.isArray(x.requiredScopes) || !x.requiredScopes.length || !Array.isArray(x.reports)) return hold('Invalid or missing intake');
  if (x.requiredScopes.includes('script')) {
    if (x.show === 'TSWS' || x.show === 'ACX') {
      if (!['RECOMMEND','GREENLIGHT'].includes(x.dramaticDoctorVerdict)) return hold('Dramatic development verdict does not clear script');
    } else if (!['PASS','REPAIRED'].includes(x.presenterDoctorVerdict)) return hold('Presenter script unchecked');
  }
  for (const scope of x.requiredScopes) {
    const r = x.reports.find(r => r.scope === scope && r.artifactHash === x.artifactHash && r.rubricVersion === x.rubricVersion);
    if (!r || r.evidenceComplete !== true) return {state:'EVIDENCE_REQUIRED', reason:scope};
    if (r.qcVerdict !== 'PASS' || r.openP0P1 !== 0 || r.criticalOrHigh !== 0) return {state:'REVISE', reason:scope};
    if (!Number.isFinite(r.score) || r.score < 90 || r.score > 100) return {state:'REVISE', reason:'quality score below 90 or invalid'};
  }
  if (x.policyValidated !== true || x.releaseEvidenceValidated !== true) return hold('Current release policy or release evidence unvalidated');
  const a = x.approval;
  if (!a) return {state:'READY_FOR_HUMAN_REVIEW'};
  if (a.artifactHash !== x.artifactHash || a.rubricVersion !== x.rubricVersion || !a.reviewer || !a.timestamp || !Number.isFinite(Date.parse(a.timestamp)) || a.authenticated !== true) return hold('Approval missing, stale or unauthenticated');
  return {state:'RELEASE_ELIGIBLE', reason:'Requires separately authorized publisher'};
}
const row = $('One Row at a Time').first().json;
const qc = $('Parse QC + Set Verdict').first().json;
const f = row.fields || row;
// The QC result. Parse QC + Set Verdict returns qcVerdict and qcScore. Until
// 2026-10-17 this node read only qc_verdict and total, so on a real row the
// verdict was always empty and every row was held. The older names stay as
// fallbacks.
const verdict = String(qc.qcVerdict || qc.qc_verdict || qc.verdict || f.qc_verdict || '').toUpperCase();
const score = Number(qc.qcScore || qc.total || f.qc_score || 0);
const brandTag = String(f.brand || f.show || '').toUpperCase();
const show = ['NCO', 'NCO_FORGE'].includes(brandTag) ? 'NCO_FORGE' : (['TSWS', 'ACX'].includes(brandTag) ? brandTag : 'TQO');
// The script scope. Until 2026-10-17 the gate required a 'script' report and
// this node never built one, so no row could clear. The evidence is the script
// doctor's verdict, which Save Doctor Verdict writes into the score_history
// column as "| doctor <score>/100 <VERDICT> |". DT Shim: Ready Rows hands that
// column to this node as fields['Score History']. The floor is Script Gate:
// Quality's universal 90. No such line, and the row is held.
const DOCTOR_FLOOR = 90;
const history = String(f['Score History'] || f.score_history || row.score_history || '');
const doctorLine = /\|\s*doctor\s+(\d+(?:\.\d+)?)\/100\s+([A-Z_]+)(?=\s|\||$)/.exec(history);
const doctorScore = doctorLine ? Number(doctorLine[1]) : NaN;
const doctorVerdict = doctorLine ? doctorLine[2] : 'UNCHECKED';
const scriptClear = ['PASS', 'REPAIRED'].includes(doctorVerdict) && doctorScore >= DOCTOR_FLOOR;
const gateInput = {
  show,
  artifactHash: String(qc.artifact_hash || f.id + '-' + (f.updatedAt || '')),
  rubricVersion: String(qc.rubric_version || 'os28-rev2-2026-09-30'),
  requiredScopes: ['script','episode'],
  reports: [{
    scope: 'script', artifactHash: String(qc.artifact_hash || f.id + '-' + (f.updatedAt || '')),
    rubricVersion: String(qc.rubric_version || 'os28-rev2-2026-09-30'),
    qcVerdict: scriptClear ? 'PASS' : 'FAIL',
    evidenceComplete: !!doctorLine, openP0P1: scriptClear ? 0 : 1,
    criticalOrHigh: scriptClear ? 0 : 1, score: doctorScore
  }, {
    scope: 'episode', artifactHash: String(qc.artifact_hash || f.id + '-' + (f.updatedAt || '')),
    rubricVersion: String(qc.rubric_version || 'os28-rev2-2026-09-30'),
    qcVerdict: (verdict === 'SHIP' ? 'PASS' : verdict === 'CONDITIONAL' ? 'CONDITIONAL' : 'FAIL'),
    evidenceComplete: true, openP0P1: (verdict === 'SHIP' ? 0 : 1),
    criticalOrHigh: (score < 90 ? 1 : 0), score
  }],
  presenterDoctorVerdict: doctorVerdict,
  policyValidated: true,
  releaseEvidenceValidated: (verdict === 'SHIP'),
  approval: null
};
const result = gate(gateInput);
return [{ json: { doctorGate: result.state, doctorGateReason: result.reason || '', qc_score: score, qc_verdict: verdict, rowId: f.id } }];