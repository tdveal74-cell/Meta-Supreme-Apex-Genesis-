// The executor owns the returned envelope from here. The router records that it
// handed off and what came back, and does not rewrite the executor's answer, with
// one addition from 2026-09-05: a designed refusal from the executor ({ refused: true,
// reason }) is carried through as data, and the pre-dispatch envelope goes out with
// state_reason set so the exit report leaves the reason in the ledger row. Tee ruled
// the same day that a refusal leaves a mark; for executor refusals this router holds
// the reason at the moment it is final, so it posts the mark.
// Reads from Reconcile Entry Envelope so the fallback envelope is the reconciled one.

const g = $('Reconcile Entry Envelope').first().json;
const raw = $input.first().json;
const first = Array.isArray(raw) ? raw[0] : raw;

let returned = null;
if (first && typeof first === 'object' && first.schema_version === '1.0.0') { returned = first; }
const ref = (first && typeof first === 'object' && first.refused === true) ? first : null;
const ok = returned !== null;

let env = ok ? returned : g.envelope;
if (!ok && ref) {
  env = JSON.parse(JSON.stringify(g.envelope));
  env.state_reason = ('Parked at ' + String(env.state) + ': ' + String(ref.reason || 'the executor refused without a reason')).slice(0, 500);
}
const outcome = ok ? 'executor_accepted' : (ref ? 'executor_refused' : 'executor_returned_nothing_usable');
const arts = ok && Array.isArray(returned.artifacts) ? returned.artifacts : [];

return [{ json: {
  intent_id: g.intent_id,
  action: g.action,
  target_workflow: g.target_workflow,
  dispatched: true,
  entry_bus_reconciled: g.entry_bus_reconciled,
  executor_returned_envelope: ok,
  executor_state: ok ? returned.state : null,
  executor: ok && returned.execution ? returned.execution.executor : null,
  execution_id: ok && returned.execution ? returned.execution.execution_id : null,
  artifact_uri: arts.length ? String(arts[arts.length - 1].uri || '') : null,
  refused: ref !== null,
  refusal_reason: ref ? String(ref.reason || '').slice(0, 600) : null,
  outcome: outcome,
  note: ok ? 'Dispatch accepted. The exit report to /devon-event is wired downstream.'
    : (ref ? 'The executor refused as data. The exit report goes out as ACTION_FAILED with the reason in state_reason; the job stays where it was.'
           : 'The executor did not return a v1 envelope. Do not assume the work happened. The exit report goes out as ACTION_FAILED.'),
  envelope: env
} }];
