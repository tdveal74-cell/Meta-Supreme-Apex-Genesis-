'use strict';
/** Pure, fail-closed patch of the two existing QC workflows. Never deploys,
 * publishes, grants human approval, or rewrites historical verdict records.
 * Old empty/cyrb53 records need fresh authorized review; they are not upgraded.
 */
const fs = require('node:fs');
const crypto = require('node:crypto');
const sha256 = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
function once(text, before, after, label) {
  if (typeof text !== 'string' || text.split(before).length !== 2) {
    throw new Error('HOLD: source drift at ' + label);
  }
  return text.replace(before, after);
}
function lineMatch(code, pattern, label) {
  const matches = code.split('\n').filter(line => pattern.test(line));
  if (matches.length !== 1 || !matches[0].includes('Math.imul')) {
    throw new Error('HOLD: source drift at ' + label);
  }
  return matches[0];
}
function patchQC(code) {
  const old = lineMatch(code, /^const fp = \(str\) => \{/, 'legacy QC fingerprint');
  let out = once(code, old,
    "const fp = (str) => require('crypto').createHash('sha256').update(str, 'utf8').digest('hex');",
    'QC SHA-256');
  out = once(out, "if (stage === 'human') {\n  const reviewRaw = b.humanReview;",
    "if (stage === 'human') {\n  const script = typeof b.script === 'string' ? b.script : '';\n  if (!script.trim()) return bad('human review requires the exact final script');\n  const reviewRaw = b.humanReview;",
    'human final artifact');
  out = once(out, "+ disc) , null);", "+ disc) , script);", 'human record identity');
  out = out.replace('// cyrb53: a fingerprint of the exact script text, so a verdict earned by one\n// draft cannot clear an edited one. Not a security hash; it detects change.',
    '// SHA-256 of the exact UTF-8 final script for every recorded stage.\n// Historical empty/cyrb53 identities never stand in for a fresh human review.');
  out = out.replace('. HOLD: trusted independent final-script receipt not yet connected.',
    '. Numerical stage only. Signed AI review and current human approval are required downstream.');
  return out;
}
function patchRepurpose(code) {
  const legacy = lineMatch(code, /^const legacyFp=\(str\)=>\{/, 'legacy repurpose fingerprint');
  let out = once(code, legacy, '// SHA-256 must match all three recorded stages.', 'remove legacy fingerprint');
  out = once(out, "const actualFp=legacyFp(v.finalScript||'');", 'const actualFp=finalHash;', 'repurpose SHA-256');
  if (!out.includes('h.script_fingerprint !== actualFp')) {
    throw new Error('HOLD: source drift at mandatory human identity comparison');
  }
  return out;
}
function patchWorkflow(workflow) {
  if (!workflow || !['MmFNWeewHEuG5x8T','wXl6p7hKN74lKH0e'].includes(workflow.id)) {
    throw new Error('HOLD: unsupported workflow');
  }
  const out = structuredClone(workflow);
  const name = out.id === 'MmFNWeewHEuG5x8T' ? 'Run Gate' : 'QC Gate';
  const targets = out.nodes.filter(node => node.name === name);
  if (targets.length !== 1) throw new Error('HOLD: missing or duplicate gate');
  const params = targets[0].parameters;
  params.jsCode = out.id === 'MmFNWeewHEuG5x8T' ? patchQC(params.jsCode) : patchRepurpose(params.jsCode);
  return out;
}
if (require.main === module) {
  const [input, output, expectedSHA] = process.argv.slice(2);
  if (!input || !output || !/^[a-f0-9]{64}$/.test(expectedSHA || '')) {
    throw new Error('usage: node finalize_human_binding.cjs INPUT OUTPUT EXPECTED_SHA256');
  }
  const raw = fs.readFileSync(input);
  if (sha256(raw) !== expectedSHA) throw new Error('HOLD: input checksum changed');
  const source = JSON.parse(raw), workflow = Array.isArray(source) ? source[0] : source;
  if (Array.isArray(source) && source.length !== 1) throw new Error('HOLD: exactly one workflow required');
  const changed = patchWorkflow(workflow);
  const bytes = Buffer.from(JSON.stringify(Array.isArray(source) ? [changed] : changed));
  fs.writeFileSync(output, bytes, {mode:0o600,flag:'wx'});
  console.log(JSON.stringify({workflow:changed.id,nodes:changed.nodes.length,inputSHA256:expectedSHA,outputSHA256:sha256(bytes),humanApprovalCreated:false}));
}
module.exports = {patchQC, patchRepurpose, patchWorkflow};
