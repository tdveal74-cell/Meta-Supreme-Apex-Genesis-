// One receipt for the poster. A refusal names its reason; a duplicate names the
// job that already exists; a drive names where the job stopped.
// Attach Brief runs only for jobs that were not refused; fall back to Apply Tags otherwise.
let d = {};
try { d = $('Dedupe').first().json || {}; } catch (e) { d = {}; }
if (d.refused === true && d.reason) { return [{ json: { filed: false, reason: d.reason } }]; }
if (d.duplicate === true && d.existing) {
  return [{ json: { filed: false, duplicate: true, intent_id: d.existing.intent_id, state: d.existing.state, terminal: d.existing.terminal, reason: 'A job with this idempotency_key already exists (' + d.existing.intent_id + ', ' + d.existing.state + '). Nothing new was filed.' } }];
}
let a = {};
try { a = $('Attach Brief').first().json || {}; } catch (e) { a = $('Apply Tags').first().json || {}; }
if (a.refused) { return [{ json: { filed: false, reason: a.reason } }]; }
if (a.dry_run) { return [{ json: { filed: false, dry_run: true, envelope: a.envelope, notes: a.notes } }]; }
const r = $input.first().json || {};
const payload = (a.envelope && a.envelope.intent && a.envelope.intent.payload) ? a.envelope.intent.payload : {};
return [{ json: {
  filed: true,
  intent_id: r.intent_id || a.envelope.intent_id,
  state: r.exit_state || 'unknown',
  outcome: r.outcome || 'driver returned nothing',
  approval_card: r.approval_card || '',
  verify_card: r.verify_card || '',
  brief: payload.brief || null,
  log: r.log || [],
  notes: a.notes || ''
} }];
