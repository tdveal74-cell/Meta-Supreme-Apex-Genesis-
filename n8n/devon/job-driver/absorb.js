// DEVON Job Driver, Build 14. Absorbs the organ's answer and loops back to Decide.
// A status code is a claim; the envelope the organ returned is the receipt.
// Nothing here trusts a 200 without an envelope carrying this job's intent_id.
const dec = $('Decide').item.json;
if (!dec || !dec.envelope) { throw new Error('Absorb could not pair with its Decide run. Refusing rather than guessing which call this answer belongs to.'); }
const res = $input.first().json || {};
const out = Object.assign({}, dec);
for (const k of ['call', 'kind', 'url', 'body', 'event_type', 'after', 'card_kind', 'stop_reason']) { delete out[k]; }
const mem = Object.assign({}, dec.memory || {});
const log = Array.isArray(dec.log) ? dec.log.slice() : [];
const env = dec.envelope;
if (!dec.call) { out.memory = mem; out.log = log; return [{ json: out }]; }
const code = (typeof res.statusCode === 'number') ? res.statusCode : null;
let body = res.body;
if (typeof body === 'string') { try { body = JSON.parse(body); } catch (e) { body = res.body; } }
const x = Array.isArray(body) ? body[0] : body;
function envFrom() {
  if (!x || typeof x !== 'object') { return null; }
  if (x.envelope && typeof x.envelope === 'object' && x.envelope.intent_id === env.intent_id) { return x.envelope; }
  if (x.schema_version === '1.0.0' && x.intent_id === env.intent_id) { return x; }
  return null;
}
function brief(v) { return (typeof v === 'string' ? v : JSON.stringify(v === undefined ? null : v)).slice(0, 200); }
const prev = String(env.state);
let stop = dec.stop === true;
let reason = '';
let next = env;
if (dec.kind === 'card') {
  const b = (x && typeof x === 'object') ? x : {};
  if ((code === 200 || code === 201) && b.queued === true && b.request_id) {
    mem[dec.card_kind === 'verify' ? 'verify_card' : 'approval_card'] = { request_id: String(b.request_id), status: 'pending', expires_at: String(b.expires_at || ''), requested_at: new Date().toISOString().replace(/\.\d{3}Z$/, 'Z'), decided_at: '' };
    log.push(dec.card_kind + ' card ' + b.request_id + ' raised, expires ' + String(b.expires_at || 'unknown'));
  } else {
    stop = true; reason = 'card_post_failed';
    log.push(dec.card_kind + ' card POST FAILED: http ' + String(code) + ' ' + brief(body));
  }
} else if (dec.kind === 'bus') {
  const e = envFrom();
  const persisted = !!(x && x.persisted === true);
  if (code === 200 && persisted && e) {
    next = e;
    log.push('bus ' + dec.event_type + ' ' + prev + '->' + String(e.state) + ' (' + String(x.ledger_said || '').slice(0, 80) + ')');
    if (dec.after === 'stop') { stop = true; reason = dec.stop_reason || 'pass complete'; }
  } else {
    stop = true; reason = persisted ? 'bus_returned_no_envelope' : 'ledger_refused';
    log.push('bus ' + dec.event_type + ' NOT persisted: http ' + String(code) + ' outcome ' + String(x && x.outcome) + ' ' + String(x && x.ledger_said).slice(0, 160));
  }
} else if (dec.kind === 'editforge') {
  const e = envFrom();
  mem.editforge_called = true;
  if (code === 200 && e && x && x.ledger_clean === false) {
    stop = true; reason = 'ledger_refused';
    log.push('editforge answered 200 but the ledger refused ' + prev + '->' + String(e.state) + ' (ledger_clean false); pass stopped, the ledger stays the authority');
  } else if (code === 200 && e) {
    next = e;
    log.push('editforge ' + String(x.outcome) + ' job ' + String(x.job_id) + ' status ' + String(x.job_status) + ' live ' + String(x.live) + ' ' + prev + '->' + String(e.state) + ' ledger_clean ' + String(x.ledger_clean));
    if (e.state === 'EXECUTING') { stop = true; reason = 'editforge job running, observe again next pass'; }
  } else {
    stop = true; reason = 'editforge_organ_failed';
    log.push('editforge handoff FAILED: http ' + String(code) + ' ' + brief(body));
  }
} else {
  const e = envFrom();
  const actionName = (dec.kind === 'action' && dec.body && dec.body.action) ? String(dec.body.action) : dec.kind;
  if (dec.kind === 'action' && code === 200 && x && x.refused === true) {
    // A refusal as data, from the router's gate or relayed from the executor, and
    // only at HTTP 200: a 500 whose body happens to carry the flag is a fault, not a
    // designed answer. The reason is the whole point, so it is kept in full, not
    // through brief(). marked true means the router already wrote the reason into the
    // ledger (it holds an executor refusal at the moment it is final and posts the
    // exit report as ACTION_FAILED with state_reason set), so the pass stops. marked
    // false or absent means the reason reached nothing durable, which is every gate
    // refusal and any executor refusal whose bus post failed, so Decide posts the
    // mark on the next slot. Exactly one of the two writes it. See
    // n8n/devon/action-router/report_dispatch.js and reconcile_exit_envelope.js.
    const why = String(x.reason || 'no reason given').slice(0, 600);
    reason = 'organ_refused';
    if (x.marked === true) {
      stop = true;
      log.push('action ' + actionName + ' refused: ' + why + ' (reason recorded in the ledger by the router)');
    } else {
      stop = false;
      mem.park = { intent_id: env.intent_id, action: actionName, reason: why };
      log.push('action ' + actionName + ' refused: ' + why);
    }
  } else if (dec.kind === 'action' && code === 200 && x && x.executor_returned_envelope === false) {
    // The router dispatched but the executor returned nothing usable. The
    // envelope in the receipt is the pre-dispatch copy, so advancing on it would
    // loop this pass back into the same call. Stop; the next pass retries.
    stop = true; reason = 'executor_failed';
    log.push('action ' + actionName + ' dispatched to workflow ' + String(x.target_workflow || 'unknown') + ' but the executor returned nothing usable (' + String(x.outcome || 'no outcome') + '); the job stays ' + prev + ' and the next pass retries');
  } else if (code === 200 && e && x && x.ledger_clean === false) {
    // The organ advanced its copy but the ledger refused the write. Advancing
    // in memory would raise cards for a job the ledger still holds one state
    // back; the next poll re-drives from the ledger, so stop here instead.
    stop = true; reason = 'ledger_refused';
    log.push(dec.kind + ' answered 200 but the ledger refused ' + prev + '->' + String(e.state) + ' (ledger_clean false); pass stopped, the ledger stays the authority');
  } else if (code === 200 && e) {
    next = e;
    const via = (dec.kind === 'action' && x) ? (' via workflow ' + String(x.target_workflow || 'unknown') + ' execution ' + String(x.execution_id || 'unknown') + (x.artifact_uri ? ' artifact ' + String(x.artifact_uri) : '')) : '';
    log.push(actionName + ' ' + prev + '->' + String(e.state) + via + ((x && typeof x.ledger_clean === 'boolean') ? ' ledger_clean ' + String(x.ledger_clean) : ''));
  } else {
    stop = true; reason = 'organ_unreachable';
    log.push(actionName + ' unreachable or no envelope: http ' + String(code) + ' ' + brief(body));
  }
}
out.envelope = next; out.memory = mem; out.log = log; out.stop = stop; out.reason = reason || dec.reason || ''; out.steps = (typeof dec.steps === 'number' ? dec.steps : 0) + 1;
return [{ json: out }];
