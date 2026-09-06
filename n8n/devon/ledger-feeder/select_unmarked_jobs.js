// DEVON Ledger Feeder, Build 18 (learning capture, build b of the 2026-09-06 order).
// The feed log is this workflow's own idempotency table and stays the only dedupe key
// (house rule: never borrow another organ's column). What was missing is the mirror:
// a fed job's envelope kept reading learning.state not_captured forever, because the
// envelope belongs to the ledger and nothing wrote the fact back. This node mirrors
// the feed log onto the envelope, once per job: every COMPLETED row whose feed log
// entry answered 2xx and whose learning.state is not yet captured gets ONE
// LEARNING_CAPTURED event through the Event Bus. That is a same state update,
// COMPLETED to COMPLETED, which the Build 02 guard already allows as
// update_same_state; the terminal rule is not widened. Idempotent by data shape: a
// marked row is skipped next run, and a mark the bus refused is retried next run
// because the row still reads not_captured. Feeding is not approval and neither is
// this mark: PROMOTE alone writes the subconscious, and the soul is written only by
// the committer behind a card. This node never touches approval, soul or state.
const now = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
// This node hangs off Fetch Feed Log, not off the feed branch, so it runs on a quiet
// day too (proof run 6261: with nothing to feed, a branch hung off Log Or Alert never
// ran and a failed mark would have waited for the next new job). Under execution
// order v1 the feed branch, which sits above this one on the canvas, completes first,
// so Log Or Alert has run whenever there was something to feed; when there was not,
// it never ran and asking for it throws, which is the quiet day, not a fault.
let run = {};
try { run = $('Log Or Alert').first().json || {}; } catch (err) { run = {}; }
const fedOk = {};
for (const it of $('Fetch Feed Log').all()) {
  const r = it.json || {};
  if (typeof r.intent_id !== 'string' || !r.intent_id) { continue; }
  const code = Number(r.webhook_status);
  if (code === 200 || code === 201) { fedOk[r.intent_id] = r; }
}
// This run's own feeds: the table write runs on the other branch and may still be in
// flight, so they are taken from the digest rather than re-read.
for (const l of (Array.isArray(run.logs) ? run.logs : [])) {
  if (l && typeof l.intent_id === 'string' && l.intent_id) { fedOk[l.intent_id] = l; }
}
const MAX_PER_RUN = 25;
const out = [];
for (const it of $('Fetch Completed Jobs').all()) {
  const j = it.json || {};
  if (!j.intent_id || !fedOk[j.intent_id]) { continue; }
  if (String(j.learning_state || '') === 'captured') { continue; }
  let env = null;
  try { env = JSON.parse(String(j.envelope || '')); } catch (err) { env = null; }
  if (!env || typeof env !== 'object' || env.intent_id !== j.intent_id) { continue; }
  if (env.state !== 'COMPLETED') { continue; }
  if (env.learning && typeof env.learning === 'object' && env.learning.state === 'captured') { continue; }
  const f = fedOk[j.intent_id];
  const fedAt = String(f.fed_at || now);
  const decision = String(f.gate_decision || '');
  const status = Number(f.webhook_status || 0);
  env.learning = { state: 'captured', captured_at: fedAt, by: 'ledger-feeder', gate_decision: decision, feed_status: status };
  out.push({ json: {
    intent_id: j.intent_id,
    envelope: env,
    gate_decision: decision,
    fed_at: fedAt,
    note: 'Ledger Feeder fed this job to the Build 12 learning gate at ' + fedAt + ' (HTTP ' + status + (decision ? ', gate ' + decision : '') + '); learning.state captured. Feeding is not approval: PROMOTE alone writes the subconscious, and the soul is written only through the committer and a card.'
  } });
  if (out.length >= MAX_PER_RUN) { break; }
}
return out;
