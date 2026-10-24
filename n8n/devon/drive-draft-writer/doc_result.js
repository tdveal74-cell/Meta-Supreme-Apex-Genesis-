// Reads the Drive create answer, the confirmation search under the key, and the
// text read back from the new file, and records the draft only when all three
// hold. Since 2026-10-24 the create is one multipart upload (build_upload.js),
// so a refused create leaves no document. The read back is the measurement:
// the artifact's word count is what Drive holds, not what this pass sent, and
// a file that reads back short is refused rather than recorded as written.
const FLOOR = 120;
const DOC = 'application/vnd.google-apps.document';
const BOM = new RegExp(String.fromCharCode(0xfeff), 'g');
const p = $('Parse Draft').first().json;
const r = $('Create Doc').first().json || {};
function refuse(reason) {
  return [{ json: { refused: true, outcome: 'refused', action: 'drive.draft', intent_id: p.intent_id, state: 'AUTHORIZED', reason: reason } }];
}
if (r.error || !r.id) {
  // n8n's message for a 403 is generic; Google's own reason rides in description.
  const msg = String((r.error && (r.error.description || r.error.message)) || r.error || 'no file id returned').slice(0, 160);
  return refuse('REFUSED: Drive did not create the document, or did not answer with a file id (' + msg + '). The create is one call, so a refused create leaves no document; if it timed out instead, the next pass finds any file it left by the idempotency properties or by the name and reads its text before adopting it.');
}
if (String(r.mimeType || '') !== DOC) {
  return refuse('REFUSED: Drive created file ' + String(r.id) + ' as ' + String(r.mimeType || 'an unstated type') + ' rather than a Google Doc, so it is not recorded as the draft. The file is left in place for a person to look at.');
}
const confirm = $('Confirm Properties').all().map(function (i) { return i.json || {}; });
const verified = confirm.some(function (c) { return c && String(c.id || '') === String(r.id); });
const back = $input.first().json || {};
if (back.error || typeof back.data !== 'string') {
  const why = back.error ? String((back.error && (back.error.description || back.error.message)) || back.error).slice(0, 160) : 'no text came back';
  return refuse('REFUSED: Drive created file ' + String(r.id) + ' but this pass could not read its text back (' + why + '), so it is not recorded as written. The next pass finds it by the idempotency properties and reads its text before adopting it.');
}
const words = back.data.replace(BOM, '').split(/\s+/).filter(Boolean).length;
if (words < FLOOR) {
  return refuse('REFUSED: Drive created file ' + String(r.id) + ' but it reads back with ' + words + ' words, under the ' + FLOOR + ' word floor, against ' + String(p.draft_words) + ' sent. It is not recorded as the draft and is left in place for a person to look at.');
}
return [{ json: { refused: false, id: String(r.id), name: String(r.name || p.doc_name), created_time: String(r.createdTime || ''), draft_words: words, draft_by: p.draft_by, intent_id: p.intent_id, properties_verified: verified } }];
