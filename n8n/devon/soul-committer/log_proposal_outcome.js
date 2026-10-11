// A queued response is read back, never assumed. A failed POST leaves no
// commit-log row; the next poll reconciles against the queue by evidence and
// adopts the request if the queue stored it anyway, so a lost response cannot
// raise the same card twice.
const responses = $input.all();
const nowIso = new Date().toISOString();
const rows = [];
const failures = [];
for (let i = 0; i < responses.length; i++) {
  const res = responses[i].json || {};
  let src = {};
  try { src = ($('Only Post Item').itemMatching(i) || {}).json || {}; } catch (e) { src = {}; }
  const body = (res.body && typeof res.body === 'object') ? res.body : {};
  const ok = (res.statusCode === 200 || res.statusCode === 201) && body.queued === true && body.request_id;
  if (ok) {
    rows.push({ intent_id: src.intent_id, state: 'PROPOSED', request_id: String(body.request_id), record_id: '', claim: src.claim || '', area: src.area || '', proposed_at: nowIso, resolved_at: '', note: 'awaiting decision, expires ' + String(body.expires_at || ''), lesson_key: String(src.lesson_key || ''), source_intent_ids: String(src.source_intent_ids || '[]') });
  } else {
    failures.push({ intent_id: src.intent_id || 'unknown', status: String(res.statusCode || 'no response'), detail: JSON.stringify(res.body || res.error || res).slice(0, 300) });
  }
}
const lines = ['SOUL COMMITTER PROPOSE ' + nowIso, ''];
for (const f of failures) {
  lines.push('PROPOSE FAILED ' + f.intent_id + ' (HTTP ' + f.status + '): ' + f.detail);
  lines.push('  No commit-log row written. Next poll reconciles by evidence: if the queue stored this request anyway, it is adopted rather than raised twice.');
}
return [{ json: { rows: rows, failed_count: failures.length, subject: 'Soul Committer: ' + failures.length + ' proposal(s) FAILED to queue', body: lines.join(String.fromCharCode(10)) } }];