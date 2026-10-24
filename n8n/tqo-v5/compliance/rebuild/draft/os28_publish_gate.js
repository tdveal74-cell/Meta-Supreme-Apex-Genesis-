// OS 30 - the publish gate. Show-aware, board-aware, time-aware, asset-aware.
const ctx  = $('Show Context: Publish').first().json;
const row  = $('One Row at a Time').first().json;
const f    = row.fields || row;
const pk   = $('Parse Packaging').first().json;
const mf   = $('Parse Manifest').first().json;
const qc   = $('Parse QC + Set Verdict').first().json;
const thumb = $('Shim: Thumbnail To Binary').first().json;
const link = $('Upload Thumbnail').first().json || {};

const str = (v) => String(v ?? '').trim();
const blocking = [];
const aiReview=$('AI Review: Verified Result').first().json.aiReview || {};
const aiFinalHash=require('crypto').createHash('sha256').update(typeof f.Script==='string'?f.Script:'','utf8').digest('hex');
if (aiReview.aiReviewPassed!==true || aiReview.artifactSha256!==aiFinalHash || aiReview.scope!=='script') blocking.push('AI final-script review unavailable, stale, or below 90');
const gates = {};
const notes = [];

// -- gate 1: brand, with legacy aliases. ------------------------------------
const ALIASES = {
  'The Quiet Operator': ['the quiet operator', 'tqo', 'tqo main'],
  'NCO Forge': ['nco forge', 'nco', 'ncoforge']
};
const allowed = (ALIASES[ctx.channel] || [ctx.channel.toLowerCase()]);
const rowChannel = str(f.Channel);
if (!rowChannel) {
  gates.brand = true;
  notes.push('Channel field empty. Inherited "' + ctx.channel + '" from the schedule context.');
} else if (allowed.includes(rowChannel.toLowerCase())) {
  gates.brand = true;
  if (rowChannel !== ctx.channel) notes.push('brand: "' + rowChannel + '" accepted as a legacy alias of ' + ctx.channel + '.');
} else {
  gates.brand = false;
  blocking.push('brand: row Channel "' + rowChannel + '" is not ' + ctx.channel + ' or a known alias. Identity bleed, refusing to publish');
}

// -- gate 2: authorship. -----------------------------------------------------
// The one gate a human sets by hand, which makes it the one most exposed to how
// the field is stored. On Airtable 'Human Review' is a checkbox and arrives as
// boolean true. tqo_content and nco_content store it as a STRING column,
// verified 11 Sep 2026: column human_review, type string. So `=== true` could
// never be satisfied by a data table row and this gate failed closed on every
// one of them, silently, since the lane was repointed. TSWS still reads
// Airtable, so boolean true has to keep working.
//
// Deliberately strict, because authorship has no exception path. Only the forms
// below are accepted and the refusal names them, so nobody has to guess what to
// type into a string column that used to be a checkbox. A wrong refusal holds
// the row, which is safe. A wrong acceptance publishes under Tee's name, which
// is not. TICKED must stay identical to the copy in 'Preflight: Can This
// Clear?'; if the two drift, preflight pays for runs this gate will refuse or
// skips rows it would clear.
const TICKED = ['true', 'yes', 'y', '1', 'checked', 'ticked'];
const reviewRaw = f['Human Review'];
const reviewStr = String(reviewRaw ?? '').trim().toLowerCase();
gates.authorship = aiReview.aiReviewPassed === true && reviewStr === 'approved:' + aiFinalHash;
if (!gates.authorship) {
  blocking.push('authorship: Human Review is not approved for the current script hash'
    + (reviewStr ? ' (found "' + String(reviewRaw).trim() + '")' : ' (empty)')
    + '. Required: approved:' + aiFinalHash);
}

// -- gate 3: platform policy. ------------------------------------------------
const title = str(f['Video Title']);
const desc  = str(f['Description']);
const tags  = str(f['Tags'] || pk.youtubeTags);
const policy = [];
if (!title) policy.push('no Video Title');
else if (title.length > 95) policy.push('title is ' + title.length + ' chars (house limit 95)');
if (!desc) policy.push('no Description');
else if (desc.length < 120) policy.push('description is only ' + desc.length + ' chars');
if (!tags) policy.push('no Tags');
gates.platform_policy = policy.length === 0;
if (!gates.platform_policy) blocking.push('platform policy: ' + policy.join('; '));

// -- gate 3c: QUALITY LAW rev2 checks 6+7, outcome title and drama discipline.
// Written 2026-09-30 into a nested parameters.jsCode copy that n8n never runs,
// so until 2026-10-17 no title was held for these. Moved here, unchanged, on
// Tee's ruling of 2026-10-17 to fix the dead gates now.
// The two dash characters are built from their code points so that no tool
// on the way into n8n can decode an escape into the literal characters.
const DASH = new RegExp('[' + String.fromCharCode(0x2014, 0x2013) + ']');
const lawTitle = [];
if (DASH.test(title)) lawTitle.push('title carries an em or en dash. Restructure the sentence, never swap the punctuation');
// Whole words only, ruled 2026-10-24. Without boundaries a word that merely
// contains one of these passed: 'Costume' carried 'cost', 'Lostwithiel'
// carried 'lost'. A plain inflection still counts ('mistakes', 'quietly',
// 'stopped', 'quieter', 'mistaken', 'wrongful').
const tensionWord = /\b(?:stop|never|no one|wrong|truth|lie|lost|cost|failed|mistaken|mistake|quiet|hidden|invisible|exposed|before|instead)(?:s|es|d|ed|ped|ping|ing|ly|er|est|en|ful)?\b/i;
const properNoun = /\b[A-Z][a-z]+\b/;
if (title && !tensionWord.test(title)) lawTitle.push('no tension word: outcome/stakes not stated (quality law 6)');
if (title && !properNoun.test(title)) lawTitle.push('no proper noun or concrete object in the title (quality law 7)');
if (lawTitle.length) {
  gates.quality_law_titles = false;
  blocking.push('quality law titles: ' + lawTitle.join('; '));
} else gates.quality_law_titles = true;


// -- gate 4: monetisation. ---------------------------------------------------
const block = str(pk.packagingBlock);
const REQUIRED_BLOCKS = ['YOUTUBE TAGS','PINNED COMMENT','TIKTOK','INSTAGRAM','FACEBOOK','LINKEDIN 1','X THREAD 1','X VALUE POST','SHORT SCRIPT 1','THUMBNAIL TEXT'];
const missingBlocks = REQUIRED_BLOCKS.filter(b => !block.includes(b));
const tagsLower = tags.toLowerCase();
const missingTags = (ctx.requiredTags || []).filter(t => !tagsLower.includes(t.toLowerCase()));
gates.monetization = missingBlocks.length === 0 && missingTags.length === 0;
if (missingBlocks.length) blocking.push('monetization: packaging is missing ' + missingBlocks.join(', '));
if (missingTags.length) blocking.push('monetization: required brand tags missing: ' + missingTags.join(', '));

// -- gate 5: disclosure, and QUALITY LAW rev2 check 13. ----------------------
// Ruled 2026-09-30, Tee, 'Make it law' and 'Lanes are presenter led with my
// avatar': every presenter-led asset carries the exact C4 line, on a line of
// its own, in the first three lines of its description. Both lanes of this workflow are presenter
// led, so 'Not required' is never a valid answer here. Until 2026-10-17 the
// first-three-lines rule sat in a nested copy n8n never runs, and 'Not
// required' passed with no line at all. Metadata enum alone cannot demonstrate
// compliance (MASTER_PROMPT rule): the Description itself must carry the line,
// word for word. Fails closed; there is no waiver path.
const C4_LINE = 'Presented with a synthetic voice and synthetic likeness of Terrance Veal, used with his consent.';
const disc = str(f['AI Disclosure']);
const descText = str(f['Description']);
const descHead = descText.split('\n').slice(0, 3);
const PLACED = ['Disclosed in description', 'Disclosed on-screen + description'];
gates.c4_disclosure = descHead.some(l => l.trim() === C4_LINE);
gates.disclosure = PLACED.includes(disc) && gates.c4_disclosure;
if (disc === 'Not required') {
  blocking.push('disclosure: AI Disclosure is "Not required", but every episode of this workflow is presenter led with a synthetic voice and likeness (ruled 2026-09-30), so the C4 line is always required.');
} else if (!PLACED.includes(disc)) {
  blocking.push(disc ? 'disclosure: AI Disclosure is "' + disc + '"' : 'disclosure: AI Disclosure is unset');
}
if (!gates.c4_disclosure) {
  blocking.push(descText.includes(C4_LINE)
    ? 'disclosure: the C4 line is in the Description but not on a line of its own in its first three lines (quality law 13). Fill Run Fields puts it first; re-run the fill step rather than moving it by hand.'
    : 'disclosure: the Description does not contain the exact C4 line (quality law 13). Fill Run Fields adds it automatically; if it is missing, re-run the fill step rather than pasting a variant.');
}

// -- gate 6: temporal validity. ----------------------------------------------
const recheck = str(f['Recheck By']);
const validity = str(f['Claim Validity']);
if (recheck && new Date(recheck + 'T23:59:59Z') < new Date()) {
  gates.temporal = false;
  blocking.push('temporal: Recheck By ' + recheck + ' is past. Re-verify the claims, move the date, then publish');
} else {
  gates.temporal = true;
  if (validity === 'Real-Time Sensitive') notes.push('temporal: Real-Time Sensitive. The Human Review tick is the at-publish verification');
  if (validity === 'Frequently Changing' && !recheck) notes.push('temporal: Frequently Changing row has no Recheck By date');
}

// -- gate 7: idempotency. ----------------------------------------------------
const already = str(f['Published URL']) || str(f['Live Links']);
const claimTag = str(f['System Status']);
const claimed = claimTag.startsWith('publishing');
gates.idempotency = !already && !claimed;
if (already) blocking.push('idempotency: row already carries a published/live URL');
if (claimed) blocking.push('idempotency: claimed by an unfinished publish attempt (' + claimTag + '). The reaper releases these after 3h.');

// -- thumbnail. --------------------------------------------------------------
const thumbLink = str(link.webViewLink);
gates.thumbnail = !!(thumb.thumb_rendered && thumbLink);
if (!gates.thumbnail) blocking.push('thumbnail: ' + (thumb.thumb_error || 'no Drive link after upload'));
if (thumb.thumb_warning) notes.push('thumbnail warning: ' + thumb.thumb_warning);

// -- gate 8: QC verdict. -----------------------------------------------------
const verdict = str(f['QC Verdict']) || str(qc.qcVerdict);
gates.qc = verdict === 'SHIP' && Number.isFinite(Number(qc.qcScore)) && Number(qc.qcScore) >= 90; // universal 90, no waiver
if (!gates.qc) blocking.push(verdict ? 'qc: QC Verdict is "' + verdict + '" (score ' + (qc.qcScore ?? '?') + '/100). See QC Findings' : 'qc: QC Verdict is unset');
if (verdict === 'WAIVED') notes.push('qc: WAIVED cannot override a missing or failing quality receipt');

// -- gate 9: content identity. -----------------------------------------------
const identity = [];
if (!str(f.Show)) identity.push('no Show');
if (f.Season == null || f.Season === '') identity.push('no Season');
if (f.Episode == null || f.Episode === '') identity.push('no Episode');
if (!str(f['Asset Type'])) identity.push('no Asset Type');
gates.content_identity = identity.length === 0;
if (!gates.content_identity) blocking.push('content identity: ' + identity.join(', ') + '. Every upload belongs to a Show, Season and Episode or it is an orphan');

// -- gate 10: asset native fit + the pre-publish checklist. ------------------
const fit = [];
if ((pk.linkedinCount || 0) < 3) fit.push('only ' + (pk.linkedinCount || 0) + '/3 LinkedIn posts');
if ((pk.xThreadCount || 0) < 5) fit.push('only ' + (pk.xThreadCount || 0) + '/5 X threads');
if ((pk.shortScriptCount || 0) < 2) fit.push('only ' + (pk.shortScriptCount || 0) + '/2 short-form scripts');
if (mf.manifestError) fit.push('manifest unavailable (' + mf.manifestError + ')');

const dashes = (block.match(/[—–]/g) || []).length;
if (dashes) fit.push(dashes + ' em or en dash(es) in the packaging. The voice profile forbids them absolutely');

const FILLER = ["in today's world", 'in todays world', 'let me tell you', 'in this day and age', 'we all know that'];
const hitFiller = FILLER.filter(x => block.toLowerCase().includes(x));
if (hitFiller.length) fit.push('filler opener(s): ' + hitFiller.join(', '));

function section(label, next) {
  const i = block.indexOf(label);
  if (i === -1) return '';
  const j = next ? block.indexOf(next, i + 1) : -1;
  return block.slice(i, j === -1 ? Math.min(block.length, i + 1400) : j);
}
const tags_ = s => (s.match(/#[A-Za-z0-9_]+/g) || []).length;
const ig = tags_(section('INSTAGRAM', 'LINKEDIN 1'));
const tk = tags_(section('TIKTOK', 'INSTAGRAM'));
const fb = tags_(section('FACEBOOK', 'LINKEDIN 1'));
if (ig > 5) fit.push('Instagram has ' + ig + ' hashtags (max 5)');
if (tk > 5) fit.push('TikTok has ' + tk + ' hashtags (max 5)');
if (fb > 0) fit.push('Facebook carries ' + fb + ' hashtag(s). It should carry none');

const liBlock = section('LINKEDIN 1', 'X THREAD 1');
if (/https?:\/\//i.test(liBlock)) fit.push('a LinkedIn post has a link in the body. Move it to the first comment');

// Batch grade now arrives from the merged QC pass.
const grade = qc.packagingGrade;
const GRADE_FLOOR = 7.0;
if (grade == null) fit.push('packaging was never graded (' + str(qc.packagingGradeReport) + ')');
else if (grade < GRADE_FLOOR) fit.push('packaging graded ' + grade.toFixed(1) + '/10, floor is ' + GRADE_FLOOR.toFixed(1) + '. Hook is 50% of that score');

gates.asset_native_fit = fit.length === 0;
if (!gates.asset_native_fit) blocking.push('asset native fit: ' + fit.join('; '));

const cleared = blocking.length === 0;
const stamp = new Date().toISOString();
const report = [
  'OS 30 - ' + (cleared ? 'CLEARED' : 'HELD') + ' at ' + stamp,
  'show: ' + ctx.channel + ' / row Channel: ' + (rowChannel || '(empty)'),
  (str(f.Show) ? f.Show + ' S' + f.Season + 'E' + f.Episode + ' - ' + str(f['Asset Type']) : 'unassigned'),
  'qc: ' + (qc.qcScore ?? '?') + '/100 ' + verdict + '   packaging: ' + (grade != null ? grade.toFixed(1) + '/10' : 'ungraded'),
  '',
  ...Object.entries(gates).map(([k, v]) => (v ? '[x] ' : '[ ] ') + k),
  ...(blocking.length ? ['', 'blocking:', ...blocking.map(b => '  - ' + b)] : []),
  ...(notes.length ? ['', 'notes:', ...notes.map(n => '  - ' + n)] : []),
  ...(str(qc.packagingGradeReport) ? ['', str(qc.packagingGradeReport)] : [])
].join('\n');

return [{ json: { airtableId: pk.airtableId, os28_allowed: cleared, os28_blocking: blocking, os28_report: report } }];