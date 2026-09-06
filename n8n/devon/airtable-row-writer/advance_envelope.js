// Advance half, mirrors the Spine adapter and the Drive Draft Writer. n8n MAY write
// execution, artifacts, trace and state within legal transitions. It MUST NOT write
// approval.state or soul_refs; neither is touched below. The bus returned envelope
// is authoritative after every report (ruled 2026-08-23), so the advance starts
// from it.
const B32 = '0123456789ABCDEFGHJKMNPQRSTVWXYZ';
function ulid() {
  let t = Date.now();
  let time = '';
  for (let i = 0; i < 10; i++) { time = B32[t % 32] + time; t = Math.floor(t / 32); }
  let rand = '';
  for (let i = 0; i < 16; i++) { rand += B32[Math.floor(Math.random() * 32)]; }
  return time + rand;
}
function busResult(raw, intentId) {
  const empty = { envelope: null, persisted: null, outcome: null, said: null, retryable: null };
  try {
    const txt = (typeof raw === 'string') ? raw : (raw && typeof raw.data === 'string') ? raw.data : '';
    if (!txt) { return empty; }
    const parsed = JSON.parse(txt);
    const arr = Array.isArray(parsed) ? parsed : [parsed];
    const r = arr[0];
    if (!r) { return empty; }
    const e = r.envelope ? r.envelope : null;
    return {
      envelope: (e && e.intent_id === intentId) ? e : null,
      persisted: (typeof r.persisted === 'boolean') ? r.persisted : null,
      outcome: r.outcome ? String(r.outcome) : null,
      said: r.ledger_said ? String(r.ledger_said) : null,
      retryable: (typeof r.retryable === 'boolean') ? r.retryable : null
    };
  } catch (err) { return empty; }
}

const v = $('Validate and Plan').first().json;
const inp = $input.first().json || {};
let recordId = '';
let reused = false;
let title = v.title;
let createdAt = '';
let verified = null;
if (inp.existing_record_id) { recordId = String(inp.existing_record_id); reused = true; title = inp.existing_title || title; createdAt = String(inp.existing_created || ''); verified = true; }
else { recordId = String(inp.id || ''); title = String(inp.title || title); createdAt = String(inp.created_time || ''); verified = inp.key_verified === true; }
if (!recordId) { throw new Error('Advance Envelope reached with no Airtable record id. This is a fault, not a refusal.'); }

const entry = busResult($('Report Entry to Bus').first().json, v.intent_id);
const env = entry.envelope || v.envelope;
const now = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
const eventId = ulid();
const uri = v.record_url_base + recordId;

env.state = 'EXECUTING';
env.state_reason = null;
env.event_id = eventId;
env.updated_at = now;
const prior = (env.execution && typeof env.execution === 'object') ? env.execution : { state: 'not_started' };
env.execution = {
  state: 'succeeded',
  executor: 'n8n',
  workflow_id: $workflow.id,
  execution_id: String($execution.id),
  attempts: (typeof prior.attempts === 'number' ? prior.attempts : 0) + 1,
  max_attempts: typeof prior.max_attempts === 'number' ? prior.max_attempts : 3,
  started_at: prior.started_at || now,
  finished_at: now
};
if (!Array.isArray(env.artifacts)) { env.artifacts = []; }
const already = env.artifacts.some(function (a) { return a && String(a.record_id || '') === recordId; });
if (!already) {
  env.artifacts.push({ kind: 'airtable_record', uri: uri, name: title, record_id: recordId, base_id: v.base_id, table_id: v.table_id, table: v.table,
    fields: v.field_names, created_at: createdAt || now, by: 'airtable.row', executor_execution_id: String($execution.id), reused: reused, key_verified: verified });
}
if (!Array.isArray(env.trace)) { env.trace = []; }
env.trace.push({ event_id: eventId, at: now, type: 'ACTION_STARTED', actor: 'n8n',
  note: 'AUTHORIZED to EXECUTING on workflow ' + $workflow.id + ' execution ' + String($execution.id) + ': ' + (reused ? 'existing row reused (matched by DEVON key and DEVON job), ' : 'row written, ') + title + ' in ' + v.table + ', ' + uri + (verified === false ? ' (DEVON key NOT confirmed on the record)' : '') });

return [{ json: {
  envelope: env, intent_id: env.intent_id, from_state: 'AUTHORIZED', to_state: 'EXECUTING',
  artifact_uri: uri, artifact_name: title, reused: reused,
  entry_bus_reconciled: entry.envelope !== null,
  entry_ledger_persisted: entry.persisted,
  entry_ledger_outcome: entry.outcome,
  entry_ledger_said: entry.said,
  entry_ledger_retryable: entry.retryable
} }];
