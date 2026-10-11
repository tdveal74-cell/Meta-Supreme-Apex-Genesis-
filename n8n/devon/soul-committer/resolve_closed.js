// Rejected, refused and expired proposals close terminally; nothing re-raises
// a closed request. EXPIRED wording says NO RECORDED decision on purpose: the
// live queue answers the browser BEFORE writing the decision row and swallows
// a failed write, so in rare cases Tee saw Recorded and the table did not.
// A PROPOSED row whose queue row is gone, unparseable, or in an unknown state
// closes by absence 24h past the 72h TTL, so nothing sticks silently forever.
const decisions = {};
for (const it of $input.all()) {
  const r = it.json || {};
  if (r.request_id) { decisions[String(r.request_id)] = { status: String(r.status || ''), decided_at: String(r.decided_at || ''), expires_at: String(r.expires_at || '') }; }
}
const now = new Date();
const nowIso = now.toISOString();
const graceMs = 96 * 3600000;
function pastGrace(p) {
  const t = Date.parse(String(p.proposed_at || ''));
  return !Number.isNaN(t) && now.getTime() > t + graceMs;
}
const out = [];
for (const it of $('Fetch Pending Commits').all()) {
  const p = it.json || {};
  if (!p.request_id) { continue; }
  const d = decisions[String(p.request_id)];
  if (!d) {
    if (pastGrace(p)) {
      out.push({ json: { intent_id: p.intent_id, state: 'EXPIRED', resolved_at: nowIso, note: 'approval row absent from the queue; closed by absence 24h past the 72h TTL; no recorded decision', claim: String(p.claim || '') } });
    }
    continue;
  }
  if (d.status === 'rejected' || d.status === 'refused' || d.status === 'denied') {
    out.push({ json: { intent_id: p.intent_id, state: 'REJECTED', resolved_at: nowIso, note: 'rejected by Tee at ' + (d.decided_at || 'unknown'), claim: String(p.claim || '') } });
    continue;
  }
  if (d.status === 'expired') {
    out.push({ json: { intent_id: p.intent_id, state: 'EXPIRED', resolved_at: nowIso, note: 'queue marked the request expired; no recorded decision', claim: String(p.claim || '') } });
    continue;
  }
  if (d.status === 'approved') { continue; }
  if (d.status === 'pending') {
    const exp = Date.parse(d.expires_at);
    if (!Number.isNaN(exp)) {
      if (now.getTime() > exp) {
        out.push({ json: { intent_id: p.intent_id, state: 'EXPIRED', resolved_at: nowIso, note: 'expired undecided at ' + d.expires_at + '; no recorded decision in the window, and no decision is a rejection', claim: String(p.claim || '') } });
      }
    } else if (pastGrace(p)) {
      out.push({ json: { intent_id: p.intent_id, state: 'EXPIRED', resolved_at: nowIso, note: 'queue row has no usable expires_at; closed 24h past the 72h TTL; no recorded decision', claim: String(p.claim || '') } });
    }
    continue;
  }
  if (pastGrace(p)) {
    out.push({ json: { intent_id: p.intent_id, state: 'EXPIRED', resolved_at: nowIso, note: 'unrecognized queue status ' + JSON.stringify(d.status) + '; closed 24h past the 72h TTL; no recorded decision', claim: String(p.claim || '') } });
  }
}
return out;