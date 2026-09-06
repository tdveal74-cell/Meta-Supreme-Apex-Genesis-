// Emails only when a job actually moved or something refused. Quiet passes send nothing.
// Classification runs on the driver's own outcome vocabulary rather than a substring
// match on the log: a cancellation whose log names ACTION_FAILED is a job that moved,
// and an unreachable organ is a failure even though its sentence says neither
// REFUSED nor FAILED. The driver already computed both flags; this trusts them and
// falls back to the vocabulary when an older driver answers without them.
const results = $input.all().map(i => i.json || {});
const sel = $('Select Open Jobs').all().map(i => i.json || {});
const NL = String.fromCharCode(10);
const BAD = { organ_refused: 1, organ_unreachable: 1, executor_failed: 1, ledger_refused: 1,
  card_post_failed: 1, bus_returned_no_envelope: 1, editforge_organ_failed: 1,
  bound_action_mismatch: 1, no_envelope: 1 };
const moved = [];
const waiting = [];
const refused = [];
for (let i = 0; i < results.length; i++) {
  const r = results[i];
  const id = String(r.intent_id || (sel[i] && sel[i].envelope ? sel[i].envelope.intent_id : 'unknown'));
  const line = id + ': ' + String(r.entry_state) + ' -> ' + String(r.exit_state) + ' (' + String(r.outcome) + ')';
  const detail = Array.isArray(r.log) ? r.log.join(' | ') : '';
  const bad = (typeof r.bad_pass === 'boolean') ? r.bad_pass : (BAD[String(r.outcome)] === 1);
  if (bad && r.repeat_refusal === true) { waiting.push(line + ' (refusal unchanged since ' + String(r.last_pass_at || 'the last pass') + ', not mailed again)'); }
  else if (bad) { refused.push(line + NL + '    ' + detail); }
  else if (r.entry_state !== r.exit_state || /card .* raised/.test(detail)) { moved.push(line + NL + '    ' + detail); }
  else { waiting.push(line); }
}
const skipped = String((sel[0] && sel[0].skipped) || '');
if (moved.length === 0 && refused.length === 0) { return []; }
const lines = ['DEVON DRIVER POLL ' + new Date().toISOString(), ''];
if (moved.length) { lines.push('MOVED'); for (const m of moved) { lines.push('- ' + m); } lines.push(''); }
if (refused.length) { lines.push('REFUSED OR FAILED (left as-is; read devon_driver_log and the organ execution)'); for (const m of refused) { lines.push('- ' + m); } lines.push(''); }
if (waiting.length) { lines.push('STILL WAITING (no change this pass)'); for (const w of waiting) { lines.push('- ' + w); } lines.push(''); }
if (skipped) { lines.push('SKIPPED THIS PASS'); lines.push(skipped); lines.push(''); }
lines.push('The driver moves jobs only through the organs and the Event Bus. Approval and verification cards arrive separately from DEVON Approvals; no decision is a rejection.');
const subject = 'DEVON driver: ' + moved.length + ' job(s) moved' + (refused.length ? ', ' + refused.length + ' refused' : '');
return [{ json: { subject: subject, body: lines.join(NL) } }];
