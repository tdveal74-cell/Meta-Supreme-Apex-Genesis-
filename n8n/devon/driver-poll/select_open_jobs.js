// DEVON Driver Poll, Build 14. Selects the jobs the driver may resume.
// Terminal rows never resume. FAILED and BLOCKED wait for a human or the Janitor.
// A row written in the last 3 minutes is skipped so a pass still running from
// intake is never driven twice at once.
const RESUME = { RECEIVED: 1, UNDERSTANDING: 1, PLANNING: 1, WAITING_APPROVAL: 1, ESCALATED: 1, AUTHORIZED: 1, EXECUTING: 1, VERIFYING: 1 };
const nowMs = Date.now();
const out = [];
const skipped = [];
for (const it of $input.all()) {
  const r = it.json || {};
  if (!r.intent_id) { continue; }
  const state = String(r.state || '');
  if (r.terminal === true || !RESUME[state]) { continue; }
  const written = Date.parse(String(r.ledger_written_at || r.updatedAt || ''));
  if (!Number.isNaN(written) && nowMs - written < 3 * 60000) { skipped.push(r.intent_id + ' (written ' + Math.round((nowMs - written) / 1000) + 's ago)'); continue; }
  let env = null;
  try { env = JSON.parse(String(r.envelope || '')); } catch (e) { env = null; }
  if (!env || env.intent_id !== r.intent_id) { skipped.push(r.intent_id + ' (envelope unreadable)'); continue; }
  out.push({ json: { envelope: env, origin: 'poll', ledger_state: state } });
}
if (out.length === 0) { return []; }
out[0].json.skipped = skipped.join(String.fromCharCode(10));
return out;
