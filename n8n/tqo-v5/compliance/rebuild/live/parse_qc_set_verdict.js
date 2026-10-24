// Fails closed on both verdicts. If QC cannot run, the episode is HOLD and the
// batch is ungraded, which gate 10 treats as a block. Never an unchecked SHIP.
const SHIP_AT = 90; // universal ecosystem score floor, 2026-10-19
const ctx = $('Show Context: Publish').first().json;
const row = $('One Row at a Time').first().json;
const f = row.fields || row;
const airtableId = $('Build QC Prompt').first().json.airtableId;
const prior = String(f['Score History'] || '');
const stamp = new Date().toISOString();

function hold(reason) {
  return [{ json: { airtableId, qcVerdict: 'HOLD', qcScore: 0,
    packagingGrade: null, packagingGradeReport: 'Not graded. ' + reason,
    qcFindings: 'QC could not run at ' + stamp + '. ' + reason +
      '\n\nNothing auto-ships unchecked. A manual waiver cannot bypass the universal quality score.',
    scoreHistory: (prior ? prior + '\n' : '') + stamp + ' | QC UNAVAILABLE | ' + reason } }];
}

const out = $json || {};
if ((out.stop_reason === 'max_tokens' || out.choices?.[0]?.finish_reason === 'length')) return hold('QC response truncated at max_tokens.');
let raw = out.choices?.[0]?.message ? String(out.choices[0].message.content ?? '') : (out.content || []).filter(c => c.type === 'text').map(c => c.text).join('');
if (!raw.trim()) return hold('QC returned nothing. Check the Anthropic credential on Run QC (Claude).');
raw = String(raw).trim().replace(/^```(json)?/i, '').replace(/```$/, '').trim();

let q;
try { q = JSON.parse(raw); }
catch (e) {
  const s = raw.indexOf('{'), en = raw.lastIndexOf('}');
  if (s === -1 || en === -1) return hold('QC did not return JSON.');
  try { q = JSON.parse(raw.slice(s, en + 1)); } catch (e2) { return hold('QC JSON unparseable.'); }
}

const sc = q.scores || {};
const total = Number(q.total) || Object.values(sc).reduce((a, b) => a + (Number(b) || 0), 0);
const blockers = Array.isArray(q.blockers) ? q.blockers.filter(Boolean) : [];
const findings = Array.isArray(q.findings) ? q.findings : [];
const verdict = (blockers.length === 0 && total >= SHIP_AT) ? 'SHIP' : 'HOLD';

const bScore = Number(q.batch_score);
const bAssets = Array.isArray(q.batch_assets) ? q.batch_assets : [];
const gradeReport = [
  'PACKAGING GRADE ' + (isFinite(bScore) ? bScore.toFixed(1) : '?') + '/10 (hook weighted 50%)',
  q.batch_weakest ? 'WEAKEST: ' + q.batch_weakest : '',
  ...bAssets.map(a => '  ' + String(a.asset || '?').padEnd(16) + ' hook ' + (a.hook ?? '?') + '  total ' + (a.total ?? '?') + '\n      fix: ' + String(a.fix || '')),
  ...(Array.isArray(q.batch_notes) && q.batch_notes.length ? ['', 'BATCH:', ...q.batch_notes.map(n => '  - ' + n)] : []),
  ...(Array.isArray(q.batch_fixes) && q.batch_fixes.length ? ['', 'TOP FIXES:', ...q.batch_fixes.map(n => '  - ' + n)] : [])
].filter(Boolean).join('\n');

const report = [
  'QC ' + verdict + ' - ' + total + '/100 (ship threshold ' + SHIP_AT + ') at ' + stamp,
  ctx.channel + ' | ' + (f.Show || 'unassigned show') + ' S' + (f.Season || '?') + 'E' + (f.Episode || '?'),
  '',
  Object.entries(sc).map(([k, v]) => '  ' + k + ': ' + v).join('\n'),
  blockers.length ? '\nHARD BLOCKERS:\n' + blockers.map(b => '  - ' + b).join('\n') : '',
  findings.length ? '\nFINDINGS:\n' + findings.map(x =>
    '  - [' + (x.dimension || '?') + '] ' + (x.issue || '') + '\n      fix: ' + (x.fix || '')).join('\n') : '',
  q.strongest ? '\nSTRONGEST: ' + q.strongest : '',
  q.one_change ? 'ONE CHANGE THAT BUYS THE MOST: ' + q.one_change : '',
  '\n' + gradeReport
].filter(Boolean).join('\n');

return [{ json: {
  airtableId, qcVerdict: verdict, qcScore: total, qcFindings: report,
  packagingGrade: isFinite(bScore) ? bScore : null,
  packagingGradeReport: gradeReport,
  scoreHistory: (prior ? prior + '\n' : '') + stamp + ' | ' + total + '/100 ' + verdict +
    ' | batch ' + (isFinite(bScore) ? bScore.toFixed(1) : '?') + '/10' +
    ' | ' + Object.entries(sc).map(([k, v]) => k + ':' + v).join(' ') +
    (blockers.length ? ' | BLOCKED: ' + blockers.join('; ') : '')
} }];