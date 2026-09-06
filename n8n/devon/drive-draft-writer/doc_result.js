// Reads the Drive create answer and the confirmation search that follows it. An
// error on create becomes a refusal with a short reason; a created file carries its
// id forward, with properties_verified true only when the search under the key found
// that very file, which is the proof the idempotency properties persisted.
const p = $('Parse Draft').first().json;
const r = $('Create Doc').first().json || {};
if (r.error || !r.id) {
  const msg = String((r.error && r.error.message) || r.error || 'no file id returned').slice(0, 120);
  return [{ json: { refused: true, outcome: 'refused', action: 'drive.draft', intent_id: p.intent_id, state: 'AUTHORIZED',
    reason: 'REFUSED: Drive did not create the document, or did not answer with a file id (' + msg + '). No file id came back, so this pass has nothing to record; a create that timed out may still have left a document, and the next pass finds it by the idempotency properties or by the name before writing again.' } }];
}
const confirm = $input.all().map(function (i) { return i.json || {}; });
const verified = confirm.some(function (c) { return c && String(c.id || '') === String(r.id); });
return [{ json: { refused: false, id: String(r.id), name: String(r.name || p.doc_name), created_time: String(r.createdTime || ''), draft_words: p.draft_words, draft_by: p.draft_by, intent_id: p.intent_id, properties_verified: verified } }];
