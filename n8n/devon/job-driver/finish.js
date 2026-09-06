// One row per pass in devon_driver_log, this workflow's own receipt of what it did.
const last = $input.first().json || {};
const env = last.envelope || null;
const log = Array.isArray(last.log) ? last.log : [];
const outcome = String(last.reason || (last.stop ? 'stopped' : 'slots exhausted, more to do next pass'));
const mem = last.memory || {};
// A refusal that repeats the last pass's reason is a parked job, not news, and the
// poll's digest mails a refusal once per distinct reason (Tee's ruling, 2026-09-05).
// BAD is the outcome vocabulary the driver actually writes, not a substring match on
// prose: a cancellation whose log mentions ACTION_FAILED is not a failure, and an
// unreachable organ is, whatever its sentence happens to read like.
const BAD = { organ_refused: 1, organ_unreachable: 1, executor_failed: 1, ledger_refused: 1,
  card_post_failed: 1, bus_returned_no_envelope: 1, editforge_organ_failed: 1,
  bound_action_mismatch: 1, no_envelope: 1 };
// A reason that embeds a time or an execution id differs every pass; comparison runs
// on the shape of the line, not its instance.
function normalize(v) {
  return String(v || '')
    .replace(/\d{4}-\d{2}-\d{2}T[0-9:.]+Z?/g, '<time>')
    .replace(/\b\d{3,}\b/g, '<n>')
    .replace(/\s+/g, ' ')
    .trim();
}
function refusalLine(d) {
  const parts = String(d || '').split(' | ');
  for (const x of parts) { if (/refused|FAILED|NOT persisted|unreachable/i.test(x)) { return normalize(x); } }
  return '';
}
const lp = (last.last_pass && typeof last.last_pass === 'object') ? last.last_pass : null;
const detailNow = log.join(' | ').slice(0, 2000);
const bad = BAD[outcome] === 1;
const repeat = !!(lp && bad && lp.outcome === outcome && refusalLine(lp.detail) !== '' && refusalLine(lp.detail) === refusalLine(detailNow));
return [{ json: {
  intent_id: env ? String(env.intent_id) : '',
  pass_at: String(last.pass_at || ''),
  execution_id: String($execution.id),
  origin: String(last.origin || ''),
  entry_state: String(last.entry_state || ''),
  exit_state: env ? String(env.state) : '',
  outcome: outcome,
  steps: log.length,
  detail: detailNow,
  bad_pass: bad,
  repeat_refusal: repeat,
  last_pass_at: lp ? String(lp.pass_at || '') : '',
  approval_card: mem.approval_card ? String(mem.approval_card.request_id || '') : '',
  verify_card: mem.verify_card ? String(mem.verify_card.request_id || '') : '',
  envelope: env,
  log: log
} }];
