// Reads the entry report's ledger answer and this executor's own call log, in that
// order. The ledger must have taken this job at AUTHORIZED (with the running lock)
// before anything is called: a refusal there means the row has moved on, or the
// bus is unreachable, and either way nothing is called this pass. The call log
// (data table devon_zapier_call_log, owned by this workflow and written by nothing
// else) is what makes a retry safe: a call that already succeeded under this key,
// intent id and fingerprint is reused, never repeated; a call still in flight or
// with an outcome nobody could read is refused rather than risked.
const LOCK_MS = 10 * 60 * 1000;
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
function refuse(reason) { return [{ json: { refused: true, outcome: 'refused', action: 'zapier.mcp', intent_id: v.intent_id, state: 'AUTHORIZED', reason: reason } }]; }
const entry = busResult($('Report Entry to Bus').first().json, v.intent_id);
if (entry.persisted !== true) {
  return refuse('REFUSED: the ledger did not record this job at AUTHORIZED with the running lock (' + String(entry.outcome || 'bus unreachable') + (entry.said ? ': ' + entry.said.slice(0, 160) : '') + '); nothing was called. The next pass retries.');
}
// The read node runs with alwaysOutputData so an empty log does not kill the
// chain; the synthetic empty item carries no idempotency_key and is skipped. The
// filter already matched on both stamps; they are read again here so a loose
// match cannot hand this job another job's call.
const rows = [];
for (const it of $input.all()) {
  const r = it.json || {};
  if (String(r.idempotency_key || '') === String(v.idem) && String(r.intent_id || '') === String(v.intent_id)) { rows.push(r); }
}
const now = Date.now();
let reuse = null;
for (const r of rows) {
  const state = String(r.state || '');
  const sameCall = String(r.fingerprint || '') === String(v.fingerprint);
  if (state === 'succeeded') {
    if (!sameCall) { return refuse('REFUSED: idempotency key ' + v.idem + ' already ran tool ' + String(r.tool) + ' with a different payload (fingerprint ' + String(r.fingerprint) + ' then, ' + v.fingerprint + ' now) on ' + String(r.finished_at) + '. One key names one call; nothing was called.'); }
    reuse = r; continue;
  }
  if (state === 'started') {
    const age = now - Date.parse(String(r.started_at || ''));
    if (Number.isNaN(age) || age < LOCK_MS) { return refuse('REFUSED: a call under this key began at ' + String(r.started_at) + ' (executor execution ' + String(r.executor_execution_id) + ') and has not finished; this pass steps back. The lock ages out ten minutes after a readable started_at, and an unreadable one counts as held.'); }
    if (v.retry_after_unknown !== true) { return refuse('REFUSED: a call under this key began at ' + String(r.started_at) + ' and its outcome was never recorded (call log row ' + String(r.id) + '). Tool ' + v.tool + ' is a ' + v.tool_blast_radius + ', so it is not tried again until a human reads Zapier\'s history and closes that row. Nothing was called.'); }
    continue;
  }
  if (state === 'unknown') {
    if (v.retry_after_unknown !== true) { return refuse('REFUSED: a call under this key at ' + String(r.started_at) + ' ended with an outcome nobody could read (' + String(r.error || 'no error text') + '; call log row ' + String(r.id) + '). Tool ' + v.tool + ' is a ' + v.tool_blast_radius + ', so it is not tried again until a human reads Zapier\'s history and closes that row. Nothing was called.'); }
    continue;
  }
  // refused: Zapier or the executor said no and nothing ran; a retry is safe.
}
return [{ json: Object.assign({}, v, {
  entry_ledger_persisted: entry.persisted,
  log_rows_read: rows.length,
  reuse: reuse !== null,
  existing_row_id: reuse ? String(reuse.id) : '',
  existing_finished_at: reuse ? String(reuse.finished_at || '') : '',
  existing_result_head: reuse ? String(reuse.result_head || '') : '',
  existing_call_status: reuse ? Number(reuse.call_status || 0) : null
}) }];
