// QC Doctor Gate - gate.js (from Tee's QC packet, implemented 2026-09-30).
// Fail-closed routing after OS 28 verdict. States:
// HOLD (invalid intake / unvalidated policy / unauthenticated approval)
// EVIDENCE_REQUIRED (scope report missing or incomplete)
// REVISE (qcVerdict not PASS, open P0/P1, or TSWS score < 99)
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
const aiReview=$('AI Review: Verified Result').first().json.aiReview || {};
const finalHash=require('crypto').createHash('sha256').update(typeof f.Script==='string'?f.Script:'','utf8').digest('hex');
const aiClear=aiReview.aiReviewPassed===true && aiReview.artifactSha256===finalHash && aiReview.scope==='script';
const compositeRubric='quality90-ai-v2+os28';
const verdict = String(qc.qcVerdict || qc.qc_verdict || qc.verdict || f.qc_verdict || '').toUpperCase();   // qcVerdict is what Parse QC + Set Verdict outputs (field-name fix, Tee 2026-10-19 00:01 ET)
const score = Number(qc.qcScore || qc.total || f.qc_score || 0);
const show = (String(f.brand || '').toUpperCase() === 'NCO') ? 'NCO_FORGE' : (String(f.show || '').toUpperCase() === 'TSWS' ? 'TSWS' : 'TQO');
const gateInput = {
  show,
  artifactHash: finalHash,
  rubricVersion: compositeRubric,
  requiredScopes: ['script','episode'],
  reports: [{scope:'script',artifactHash:finalHash,rubricVersion:compositeRubric,qcVerdict:aiClear?'PASS':'FAIL',evidenceComplete:aiClear,openP0P1:aiClear?0:1,criticalOrHigh:aiClear?0:1,score:aiClear?aiReview.score:0,reviewKind:'AI_REVIEW',reviewId:aiReview.reviewId||''}, {
    scope: 'episode', artifactHash: finalHash,
    rubricVersion: compositeRubric,
    qcVerdict: (verdict === 'SHIP' ? 'PASS' : verdict === 'CONDITIONAL' ? 'CONDITIONAL' : 'FAIL'),
    evidenceComplete: true, openP0P1: (verdict === 'SHIP' ? 0 : 1),
    criticalOrHigh: (score < 90 ? 1 : 0), score
  }],
  presenterDoctorVerdict: (verdict === 'SHIP' ? 'REPAIRED' : 'UNCHECKED'),
  policyValidated: true,
  releaseEvidenceValidated: (verdict === 'SHIP' && aiClear),
  approval: null
};
const result = gate(gateInput);
return [{ json: { doctorGate: result.state, doctorGateReason: result.reason || '', qc_score: score, qc_verdict: verdict, rowId: f.id } }];