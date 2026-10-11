// The status code is read back, never assumed. A failed commit keeps the row
// PROPOSED: the approval stands, so the next poll retries the upsert under the
// SAME deterministic record id and cannot duplicate. Repeated identical
// failures are damped: alerts fire on the first failure and then roughly
// every 4 hours (every 4th attempt on the hourly poll; it was every 16th on the
// 15 minute poll until 2026-09-06), not once an hour.
const responses = $input.all();
const nowIso = new Date().toISOString();
const rows = [];
const lines = ['SOUL COMMITTER ' + nowIso, ''];
let committed = 0;
let failed = 0;
let sendEmail = false;
let deferred = 0;
for (let i = 0; i < responses.length; i++) {
  const res = responses[i].json || {};
  let src = {};
  try { src = ($('Resolve Approved').itemMatching(i) || {}).json || {}; } catch (e) { src = {}; }
  deferred = src.deferred || 0;
  const code = res.statusCode;
  if (code === 200 || code === 201) {
    committed++;
    sendEmail = true;
    rows.push({ intent_id: src.intent_id, state: 'COMMITTED', record_id: src.record_id, resolved_at: nowIso, note: 'HTTP ' + code + ', approved at ' + (src.decided_at || 'unknown') });
    lines.push('COMMITTED ' + src.record_id + ' to devon-soul, namespace experience (HTTP ' + code + ')');
    lines.push('  ' + src.claim);
    lines.push('  lesson ' + String(src.lesson_key || 'unnamed') + ', standing on ' + (Array.isArray(src.source_intent_ids) ? src.source_intent_ids.join(', ') : 'no listed jobs'));
  } else {
    failed++;
    const attempt = src.attempt || 1;
    if (attempt === 1 || attempt % 4 === 0) { sendEmail = true; }
    rows.push({ intent_id: src.intent_id, state: 'PROPOSED', record_id: '', resolved_at: '', note: 'commit FAILED HTTP ' + String(code || 'none') + ' attempt ' + attempt + ' at ' + nowIso + '; approval stands, retries under the same record id' });
    lines.push('COMMIT FAILED for ' + String(src.intent_id || 'unknown') + ' (HTTP ' + String(code || 'no response') + ', attempt ' + attempt + '). The approval stands; the write retries every hour under the same record id, so no duplicate can result. Repeated failures alert again roughly every 4 hours; unpublish the workflow to stop retrying.');
  }
}
if (deferred > 0) { lines.push(''); lines.push(deferred + ' more approved commit(s) are queued behind this one: one commit per poll, next within the hour.'); }
lines.push('');
lines.push('Every committed record was individually approved by Tee through the approval queue. Verify the record count in the Pinecone console before trusting this.');
const subject = failed ? 'Soul Committer: ' + committed + ' committed, ' + failed + ' FAILED' : 'Soul Committer: ' + committed + ' record(s) committed to devon-soul';
return [{ json: { rows: rows, subject: subject, body: lines.join(String.fromCharCode(10)), send_email: sendEmail } }];