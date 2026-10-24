// PRE-FLIGHT.
//
// The lane used to run Manifest, Packaging, Packaging Grade and a thumbnail
// render before OS 30 asked whether Human Review was ticked. On a row that
// could never clear, that is three model calls and a render worker poll spent
// to reach a conclusion available from the row itself.
//
// This checks only the STATIC gates: the ones whose answer cannot change during
// the run. Anything the run itself produces (packaging, thumbnail, QC, grade)
// is deliberately not checked here, because those are why the run exists.
//
// This is not the gate. OS 30 is the gate. This refuses to pay for a verdict it
// can already predict.

const ctx = $('Show Context: Publish').first().json;
const f = $json;
const s = v => String(v ?? '').trim();
const blockers = [];
const aiReview = $json.aiReview || {};
if (aiReview.aiReviewPassed !== true) blockers.push('AI final-script review: ' + (aiReview.reason || 'verified Claude receipt missing'));

// Authorship, and it must agree with OS 30 exactly. See the long note in
// 'OS 28: Publish Gate': the data tables store human_review as a string, so
// `!== true` blocked every data table row here too. This list is a deliberate
// duplicate of the one there and the two must not drift.
const TICKED = ['true', 'yes', 'y', '1', 'checked', 'ticked'];
const reviewRaw = f['Human Review'];
const reviewStr = String(reviewRaw ?? '').trim().toLowerCase();
if (!(aiReview.aiReviewPassed === true && reviewStr === 'approved:' + aiReview.artifactSha256)) {
  blockers.push('Human Review is not approved for this exact AI-reviewed script'
    + (reviewStr ? ' (found "' + String(reviewRaw).trim() + '")' : '')
    + '. Required: approved:' + (aiReview.artifactSha256 || '<current final-script SHA256>'));
}

// 'Not required' is never valid here, ruled 2026-10-24 to agree with OS 28
// gate 5: every episode of this workflow is presenter led with a synthetic
// voice and likeness (ruled 2026-09-30). Fill Run Fields always writes
// 'Disclosed in description', so 'Not required' only arrives by hand.
const disc = s(f['AI Disclosure']);
if (disc === 'Not required') {
  blockers.push('AI Disclosure is "Not required", but every episode of this workflow is presenter led with a synthetic voice and likeness, so the C4 line is always required');
} else if (!['Disclosed in description', 'Disclosed on-screen + description'].includes(disc)) {
  blockers.push(disc ? 'AI Disclosure is "' + disc + '"' : 'AI Disclosure is unset');
}

const missing = [];
if (!s(f.Show)) missing.push('Show');
if (f.Season == null || f.Season === '') missing.push('Season');
if (f.Episode == null || f.Episode === '') missing.push('Episode');
if (!s(f['Asset Type'])) missing.push('Asset Type');
if (missing.length) blockers.push('content identity: no ' + missing.join(', '));

if (s(f['Published URL']) || s(f['Live Links'])) blockers.push('already carries a published or live URL');
if (s(f['System Status']).startsWith('publishing')) blockers.push('claimed by an unfinished publish attempt (' + s(f['System Status']) + ')');

const recheck = s(f['Recheck By']);
if (recheck && new Date(recheck + 'T23:59:59Z') < new Date()) blockers.push('Recheck By ' + recheck + ' is past');

const title = s(f['Video Title']);
const desc = s(f.Description);
if (!title) blockers.push('no Video Title');
else if (title.length > 95) blockers.push('title is ' + title.length + ' chars, house limit is 95');
if (!desc) blockers.push('no Description');
else if (desc.length < 120) blockers.push('description is only ' + desc.length + ' chars, floor is 120');

if (!s(f.Script)) blockers.push('no Script');

// Mirrors, ruled 2026-10-24: a row that OS 28 gates 3c and 5 or the QC Doctor
// Gate will hold is not paid for. Each rule below is a copy of its source
// line; rebuild.test.mjs fails if a copy drifts from the line it copies.
const C4_LINE = 'Presented with a synthetic voice and synthetic likeness of Terrance Veal, used with his consent.';
if (!desc.split('\n').slice(0, 3).some(l => l.trim() === C4_LINE)) blockers.push('the C4 line is not on a line of its own in the first three lines of the Description (quality law 13)');
const DASH = new RegExp('[' + String.fromCharCode(0x2014, 0x2013) + ']');
const tensionWord = /\b(?:stop|never|no one|wrong|truth|lie|lost|cost|failed|mistaken|mistake|quiet|hidden|invisible|exposed|before|instead)(?:s|es|d|ed|ped|ping|ing|ly|er|est|en|ful)?\b/i;
const properNoun = /\b[A-Z][a-z]+\b/;
if (DASH.test(title)) blockers.push('title carries an em or en dash');
if (title && !tensionWord.test(title)) blockers.push('title has no tension word (quality law 6)');
if (title && !properNoun.test(title)) blockers.push('title has no proper noun or concrete object (quality law 7)');
const DOCTOR_FLOOR = 90;
const history = s(f['Score History'] || f.score_history);
const doctorLines = [...history.matchAll(/\|\s*doctor\s+(\d+(?:\.\d+)?)\/100\s+([^|\n]*?)\s*(?=\||\n|$)/g)];
const doctorLine = doctorLines.length ? doctorLines[doctorLines.length - 1] : null;
const doctorScore = doctorLine ? Number(doctorLine[1]) : NaN;
const doctorVerdict = doctorLine ? doctorLine[2].trim().toUpperCase() : 'UNCHECKED';
if (!(['PASS', 'REPAIRED'].includes(doctorVerdict) && doctorScore >= DOCTOR_FLOOR)) {
  blockers.push('script doctor: ' + (doctorLine ? doctorVerdict + ' at ' + doctorScore + '/100' : 'no doctor line in Score History') + ', and the QC Doctor Gate needs PASS or REPAIRED at ' + DOCTOR_FLOOR);
}

const ok = blockers.length === 0;
const stamp = new Date().toISOString();
const report = ok
  ? 'PRE-FLIGHT CLEARED at ' + stamp + '. Static gates pass; spending the run.'
  : ['PRE-FLIGHT SKIPPED at ' + stamp,
     ctx.channel + ' | ' + (s(f.Show) || 'unassigned') + ' | ' + title,
     '',
     'This row cannot clear OS 30 as it stands, so the run was not paid for:',
     ...blockers.map(b => '  - ' + b),
     '',
     'Nothing was generated and nothing was changed. Fix the above and it enters',
     'the next publish cycle on its own.'].join('\n');

return [{ json: { ...f, _preflightOk: ok, _preflightReport: report, _preflightBlockers: blockers } }];