// Reads the entry report's ledger answer and the Drive search answer, in that order.
// The ledger must have taken this job at AUTHORIZED (with the running lock) before
// anything is written: a refusal there means the row has moved on, or the bus is
// unreachable, and either way nothing is written this pass. A failed search refuses
// rather than risk a duplicate draft: the idempotency key is what makes a retry safe.
function busResult(raw, intentId) {
  const empty = { envelope: null, persisted: null, outcome: null, said: null };
  try {
    const txt = (typeof raw === 'string') ? raw : (raw && typeof raw.data === 'string') ? raw.data : '';
    if (!txt) { return empty; }
    const parsed = JSON.parse(txt);
    const r = (Array.isArray(parsed) ? parsed : [parsed])[0];
    if (!r) { return empty; }
    const e = r.envelope ? r.envelope : null;
    return { envelope: (e && e.intent_id === intentId) ? e : null, persisted: (typeof r.persisted === 'boolean') ? r.persisted : null, outcome: r.outcome ? String(r.outcome) : null, said: r.ledger_said ? String(r.ledger_said) : null };
  } catch (err) { return empty; }
}
const v = $('Validate and Plan').first().json;
function refuse(reason) { return [{ json: { refused: true, outcome: 'refused', action: 'drive.draft', intent_id: v.intent_id, state: 'AUTHORIZED', reason: reason } }]; }
const entry = busResult($('Report Entry to Bus').first().json, v.intent_id);
if (entry.persisted !== true) {
  return refuse('REFUSED: the ledger did not record this job at AUTHORIZED with the writing lock (' + String(entry.outcome || 'bus unreachable') + (entry.said ? ': ' + entry.said.slice(0, 160) : '') + '); nothing was written. The next pass retries.');
}
const items = $input.all().map(function (i) { return i.json || {}; });
const bad = items.find(function (r) { return r && r.error; });
if (bad) {
  return refuse('REFUSED: could not check Drive for an existing draft (' + String((bad.error && bad.error.message) || bad.error).slice(0, 120) + '). Nothing was written; the next pass retries.');
}
// The search matched on the idempotency properties OR on the deterministic name.
// A properties match is this job's document beyond doubt. A name match is accepted
// only when the file's properties do not name a DIFFERENT job, which is the case
// where the properties never persisted; that is the retry the name fallback exists
// for. A file carrying another job's intent id is ignored, not adopted.
function props(r) { return (r && r.appProperties && typeof r.appProperties === 'object') ? r.appProperties : {}; }
let byProps = null;
let byName = null;
for (const r of items) {
  if (!r || !r.id) { continue; }
  const pr = props(r);
  if (String(pr.devon_intent_id || '') === String(v.intent_id) && String(pr.devon_idempotency_key || '') === String(v.idem)) { byProps = r; break; }
  if (!byName && String(r.name || '') === String(v.doc_name) && !pr.devon_intent_id) { byName = r; }
}
const found = byProps || byName;
return [{ json: Object.assign({}, v, {
  existing_file_id: found ? String(found.id) : '',
  existing_name: found ? String(found.name || '') : '',
  existing_link: found ? String(found.webViewLink || '') : '',
  existing_created: found ? String(found.createdTime || '') : '',
  existing_matched_by: found ? (byProps ? 'idempotency_properties' : 'deterministic_name') : ''
}) }];
