// Advance half, mirrors the Airtable Row Writer. n8n MAY write execution,
// artifacts, trace and state within legal transitions. It MUST NOT write
// approval.state or soul_refs; neither is touched below. The bus returned envelope
// is authoritative after every report (ruled 2026-08-23), so the advance starts
// from it. Reached from two places: a reused call (the call log already held a
// succeeded row for this key, intent id and fingerprint) and a fresh call.
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
const c = $('Check Ledger and Log').first().json;
const reused = c.reuse === true;
let rowId = '';
let resultHead = '';
let artifactUri = '';
let callStatus = null;
let finishedAt = '';
if (reused) {
  rowId = String(c.existing_row_id || '');
  resultHead = String(c.existing_result_head || '');
  callStatus = c.existing_call_status;
  finishedAt = String(c.existing_finished_at || '');
  const m = resultHead.match(/https?:\/\/[^\s"'<>]+/);
  artifactUri = m ? m[0] : '';
} else {
  const r = $('Call Result').first().json;
  if (r.call_state !== 'succeeded') { throw new Error('Advance Envelope reached with call_state ' + String(r.call_state) + '. This is a fault, not a refusal.'); }
  rowId = String($('Log Call Started').first().json.id || '');
  resultHead = String(r.result_head || '');
  artifactUri = String(r.artifact_uri || '');
  callStatus = r.call_status;
  finishedAt = String(r.finished_at || '');
}
if (!rowId) { throw new Error('Advance Envelope reached with no call log row id. This is a fault, not a refusal.'); }

const entry = busResult($('Report Entry to Bus').first().json, v.intent_id);
const env = entry.envelope || v.envelope;
const now = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
const eventId = ulid();
const name = v.tool + ' via Zapier MCP';

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
const already = env.artifacts.some(function (a) { return a && String(a.call_log_row_id || '') === rowId; });
if (!already) {
  env.artifacts.push({ kind: 'zapier_call', uri: artifactUri, name: name, tool: v.tool, tool_blast_radius: v.tool_blast_radius, fingerprint: v.fingerprint,
    argument_keys: v.argument_keys, result_head: resultHead, call_status: callStatus, call_log_row_id: rowId,
    created_at: finishedAt || now, by: 'zapier.mcp', executor_execution_id: String($execution.id), reused: reused });
}
if (!Array.isArray(env.trace)) { env.trace = []; }
env.trace.push({ event_id: eventId, at: now, type: 'ACTION_STARTED', actor: 'n8n',
  note: 'AUTHORIZED to EXECUTING on workflow ' + $workflow.id + ' execution ' + String($execution.id) + ': ' + (reused ? 'earlier call reused (matched by idempotency key, intent id and fingerprint ' + v.fingerprint + '), ' : 'tool called, ') + v.tool + ' on the Zapier MCP server, call log row ' + rowId + (resultHead ? ', result: ' + resultHead.slice(0, 160) : '') });

return [{ json: {
  envelope: env, intent_id: env.intent_id, from_state: 'AUTHORIZED', to_state: 'EXECUTING',
  artifact_uri: artifactUri, artifact_name: name, reused: reused, call_log_row_id: rowId,
  entry_bus_reconciled: entry.envelope !== null,
  entry_ledger_persisted: entry.persisted,
  entry_ledger_outcome: entry.outcome,
  entry_ledger_said: entry.said,
  entry_ledger_retryable: entry.retryable
} }];
