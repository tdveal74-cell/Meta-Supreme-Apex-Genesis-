// Copies ONLY status and timing fields off the matching card rows. The token
// column is never referenced. approved beats pending; newest beats older.
const dec = $('Read Decide').first().json;
const out = Object.assign({}, dec);
delete out.call; delete out.marker;
if (!dec.call) { return [{ json: out }]; }
let best = null;
for (const it of $input.all()) {
  const r = it.json || {};
  if (!r.request_id) { continue; }
  if (String(r.requested_by || '') !== 'job-driver') { continue; }
  if (!best) { best = r; continue; }
  if (r.status === 'approved' && best.status !== 'approved') { best = r; continue; }
  if (r.status === best.status && String(r.requested_at || '') > String(best.requested_at || '')) { best = r; }
}
const mem = Object.assign({}, dec.memory || {});
const key = dec.card_kind === 'verify' ? 'verify_card' : 'approval_card';
const log = Array.isArray(dec.log) ? dec.log.slice() : [];
if (best) {
  mem[key] = { request_id: String(best.request_id), status: String(best.status || ''), decided_at: String(best.decided_at || ''), expires_at: String(best.expires_at || ''), requested_at: String(best.requested_at || '') };
  log.push('queue read: ' + dec.card_kind + ' card ' + String(best.request_id) + ' is ' + String(best.status || 'unknown'));
} else {
  mem[key] = { request_id: '', status: 'absent' };
  log.push('queue read: no ' + dec.card_kind + ' card row for this job');
}
out.memory = mem; out.log = log;
return [{ json: out }];
