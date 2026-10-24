// Reads the text of a file this job already left in Drive before it is adopted.
// Until 2026-10-24 a file found under the job's key was adopted on sight, and
// nothing on that path read it, so the empty Doc a half failed create left
// behind on 2026-10-22 was recorded as the draft, carried to a verify card with
// no word count, and marked COMPLETED.
//
// A found file is adopted only when it reads back with at least the same floor
// Parse Draft holds a new draft to. Anything shorter is refused by name and
// left in place: deleting it is a write to Tee's Drive this executor does not
// make, and writing a second document under the same key is what the key
// exists to prevent. Trashing it is the person's call, and once it is in the
// trash the search no longer finds it and the next pass writes fresh.
const FLOOR = 120;
const BOM = new RegExp(String.fromCharCode(0xfeff), 'g');
const c = $('Check Existing').first().json || {};
const r = $input.first().json || {};
function refuse(reason) {
  return [{ json: { refused: true, outcome: 'refused', action: 'drive.draft', intent_id: c.intent_id, state: 'AUTHORIZED', reason: reason } }];
}
const where = String(c.existing_file_id) + (c.existing_link ? ', ' + String(c.existing_link) : '');
if (r.error) {
  const msg = String((r.error && r.error.message) || r.error).slice(0, 120);
  return refuse('REFUSED: a file under this job\'s key already exists (' + where + ') but this pass could not read its text back (' + msg + '), so it is not adopted as the draft. Nothing was written. The next pass retries.');
}
const txt = (typeof r.data === 'string') ? r.data.replace(BOM, '') : null;
if (txt === null) {
  return refuse('REFUSED: a file under this job\'s key already exists (' + where + ') but its text came back as ' + (r.data === undefined ? 'nothing' : typeof r.data) + ' rather than a string, so it is not adopted as the draft. Nothing was written. The next pass retries.');
}
const words = txt.split(/\s+/).filter(Boolean).length;
if (words < FLOOR) {
  return refuse('REFUSED: a file under this job\'s key already exists (' + where + ') but it holds ' + words + ' words, under the ' + FLOOR + ' word floor, so it is not adopted as the draft. It is most likely a half made Doc from an earlier pass. Nothing was written and nothing was deleted. Trash that file in Drive and the next pass writes a fresh draft.');
}
return [{ json: Object.assign({}, c, { draft_words: words }) }];
