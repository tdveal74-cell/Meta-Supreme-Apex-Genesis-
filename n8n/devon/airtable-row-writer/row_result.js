// Reads the Airtable create answer. Anything but HTTP 200 with a record id is a
// refusal that names the status and Airtable's own error type, so an option name
// that does not exist on a select field (422 INVALID_MULTIPLE_CHOICE_OPTIONS, since
// typecast is never sent) reads as exactly that. key_verified is true only when the
// record Airtable returned carries this job's key and intent id in the two DEVON
// fields, which is the proof the stamp persisted and the next pass will find the row.
function airtableAnswer(res) {
  const code = (res && typeof res.statusCode === 'number') ? res.statusCode : null;
  let body = res ? res.body : null;
  if (typeof body === 'string') { try { body = JSON.parse(body); } catch (err) { body = { raw: body.slice(0, 200) }; } }
  if (!body || typeof body !== 'object') { body = {}; }
  const err = body.error;
  const msg = !err ? '' : (typeof err === 'string' ? err : (String(err.type || '') + (err.message ? ': ' + String(err.message) : '')));
  return { code: code, body: body, error: msg.replace(/\s+/g, ' ').trim().slice(0, 200) };
}
const c = $('Check Existing').first().json;
const a = airtableAnswer($input.first().json || {});
function refuse(reason) {
  return [{ json: { refused: true, outcome: 'refused', action: 'airtable.row', intent_id: c.intent_id, state: 'AUTHORIZED', reason: reason } }];
}
if (a.code !== 200) {
  const why = a.code === 422
    ? ' A 422 is Airtable refusing the values as sent, most often an option name that does not exist on a select field; this executor never sends typecast, so the fix is in the job, not here.'
    : '';
  return refuse('REFUSED: Airtable did not create the row (HTTP ' + String(a.code || 'no response') + (a.error ? ', ' + a.error : '') + ').' + why + ' No record id came back, so this pass has nothing to record; a create that timed out may still have left a row, and the next pass finds it by DEVON key and DEVON job before writing again.');
}
const rec = (a.body && a.body.id) ? a.body : ((Array.isArray(a.body.records) && a.body.records[0]) ? a.body.records[0] : {});
if (!rec.id) {
  return refuse('REFUSED: Airtable answered HTTP 200 without a record id, so this pass cannot say what it wrote. The next pass finds any row it left by DEVON key and DEVON job before writing again.');
}
const f = (rec.fields && typeof rec.fields === 'object') ? rec.fields : {};
const verified = String(f[c.key_field] || '') === String(c.idem) && String(f[c.job_field] || '') === String(c.intent_id);
return [{ json: { refused: false, id: String(rec.id), created_time: String(rec.createdTime || ''), title: String(f.Title || c.title || ''), intent_id: c.intent_id, key_verified: verified } }];
