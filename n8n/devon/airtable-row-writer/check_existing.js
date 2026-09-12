// Reads the entry report's ledger answer and the Airtable search answer, in that
// order. The ledger must have taken this job at AUTHORIZED (with the running lock)
// before anything is written: a refusal there means the row has moved on, or the
// bus is unreachable, and either way nothing is written this pass. A search that
// did not answer HTTP 200 refuses rather than risk a duplicate row: the key is what
// makes a retry safe, and a retry that cannot read the key would write twice.
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
// The HTTP node answers with the full response (statusCode, body). Airtable sends
// JSON, so body is usually parsed already; a proxy error page is a string. Neither
// shape is assumed, and Airtable's own error type and message are carried into the
// refusal so a human reads what Airtable said, not what this node guessed.
function airtableAnswer(res) {
  const code = (res && typeof res.statusCode === 'number') ? res.statusCode : null;
  let body = res ? res.body : null;
  if (typeof body === 'string') { try { body = JSON.parse(body); } catch (err) { body = { raw: body.slice(0, 200) }; } }
  if (!body || typeof body !== 'object') { body = {}; }
  const err = body.error;
  const msg = !err ? '' : (typeof err === 'string' ? err : (String(err.type || '') + (err.message ? ': ' + String(err.message) : '')));
  return { code: code, body: body, error: msg.replace(/\s+/g, ' ').trim().slice(0, 200) };
}
const v = $('Validate and Plan').first().json;
function refuse(reason) { return [{ json: { refused: true, outcome: 'refused', action: 'airtable.row', intent_id: v.intent_id, state: 'AUTHORIZED', reason: reason } }]; }
const entry = busResult($('Report Entry to Bus').first().json, v.intent_id);
if (entry.persisted !== true) {
  return refuse('REFUSED: the ledger did not record this job at AUTHORIZED with the writing lock (' + String(entry.outcome || 'bus unreachable') + (entry.said ? ': ' + entry.said.slice(0, 160) : '') + '); nothing was written. The next pass retries.');
}
const a = airtableAnswer($input.first().json || {});
if (a.code !== 200) {
  return refuse('REFUSED: could not check Airtable for an existing row (HTTP ' + String(a.code || 'no response') + (a.error ? ', ' + a.error : '') + '). Nothing was written; the next pass retries.');
}
// The formula already filtered on both DEVON fields. They are read again here so
// a filter that matched loosely cannot hand this job another job's row.
const records = Array.isArray(a.body.records) ? a.body.records : [];
let found = null;
for (const r of records) {
  const f = (r && r.fields && typeof r.fields === 'object') ? r.fields : {};
  if (r && r.id && String(f[v.key_field] || '') === String(v.idem) && String(f[v.job_field] || '') === String(v.intent_id)) { found = r; break; }
}
const ff = found ? (found.fields || {}) : {};
return [{ json: Object.assign({}, v, {
  existing_record_id: found ? String(found.id) : '',
  existing_title: found ? String(ff.Title || '') : '',
  existing_created: found ? String(found.createdTime || '') : '',
  existing_url: found ? v.record_url_base + String(found.id) : ''
}) }];
