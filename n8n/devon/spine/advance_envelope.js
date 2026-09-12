// DEVON Organism Spine v1, n8n adapter. Advance half.
// Adapter lane, from SYS_SPEC_organism-spine_v1: n8n MAY write execution, artifacts,
// trace and state within legal transitions. It MUST NOT write approval.state or soul_refs.
// Those two are never touched below, and that is the point of this node existing at all.
// Validation now lives in Validate Envelope, upstream of the entry report.

const B32 = '0123456789ABCDEFGHJKMNPQRSTVWXYZ'; // Crockford, no I L O U

function ulid() {
  let t = Date.now();
  let time = '';
  for (let i = 0; i < 10; i++) { time = B32[t % 32] + time; t = Math.floor(t / 32); }
  let rand = '';
  for (let i = 0; i < 16; i++) { rand += B32[Math.floor(Math.random() * 32)]; }
  return time + rand;
}

// RULED 2026-08-23. The bus-returned envelope is authoritative after every report.
// Advancing the pre-report copy would overwrite the INTENT_RECEIVED entry the bus just
// appended, which is how an append-only trace stops being append-only. Proven by
// execution 3186 in Build 03.
//
// RULED 2026-08-24, approval_mode delegated. The bus also reports whether the LEDGER
// persisted, and every organ was discarding it. A true reconcile flag only means the bus
// answered with a matching envelope. It does NOT mean the row reached the ledger.
// null means the bus never answered. false means the ledger refused. Never collapse them.
// This matters most here: for a RECEIVED envelope, THIS is the insert that creates the
// ledger row every later organ updates. If it did not persist, nothing downstream can.
function busResult(raw, intentId) {
  const empty = { envelope: null, persisted: null, outcome: null, said: null, retryable: null };
  try {
    const txt = (typeof raw === 'string') ? raw
      : (raw && typeof raw.data === 'string') ? raw.data : '';
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

const v = $('Validate Envelope').first().json;
const b = busResult($input.first().json, v.intent_id);
const env = b.envelope || v.envelope;

const from = v.from_state;
const to = v.to_state;

const now = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
const eventId = ulid();

env.state = to;
// A state change clears the reason the previous state carried (2026-09-05).
env.state_reason = null;
env.event_id = eventId;
env.updated_at = now;

const prior = (env.execution && typeof env.execution === 'object') ? env.execution : { state: 'not_started' };
if (from === 'EXECUTING' && prior.state === 'succeeded') {
  // RULED 2026-09-05 by Tee. A succeeded execution block is the executor's record:
  // its workflow_id, execution_id, attempts and timestamps name who did the work.
  // This hop advances the state and appends its own trace entry, and leaves that
  // block exactly as it found it.
  env.execution = prior;
} else {
  env.execution = {
    state: to === 'EXECUTING' ? 'running' : prior.state || 'not_started',
    executor: 'n8n',
    workflow_id: $workflow.id,
    execution_id: String($execution.id),
    attempts: (typeof prior.attempts === 'number' ? prior.attempts : 0) + 1,
    max_attempts: typeof prior.max_attempts === 'number' ? prior.max_attempts : 3,
    started_at: prior.started_at || now
  };
}

if (!Array.isArray(env.trace)) { env.trace = []; }
env.trace.push({
  event_id: eventId,
  at: now,
  type: 'ACTION_STARTED',
  actor: 'n8n',
  note: from + ' to ' + to + ' on workflow ' + $workflow.id
});

return [{ json: {
  envelope: env,
  intent_id: env.intent_id,
  from_state: from,
  to_state: to,
  entry_bus_reconciled: b.envelope !== null,
  entry_ledger_persisted: b.persisted,
  entry_ledger_outcome: b.outcome,
  entry_ledger_said: b.said,
  entry_ledger_retryable: b.retryable
} }];
