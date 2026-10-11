const closed = $('Resolve Closed').all().map(i => i.json);
if (!closed.length) { return []; }
const nowIso = new Date().toISOString();
const lines = ['SOUL COMMITTER CLOSURES ' + nowIso, ''];
for (const c of closed) {
  lines.push(c.state + ' ' + c.intent_id + ': ' + c.note);
  lines.push('  ' + (c.claim || ''));
  if (c.lesson_key) { lines.push('  lesson ' + c.lesson_key + '; these jobs can never back another lesson: ' + (c.source_intent_ids || 'none listed')); }
}
lines.push('');
lines.push('Closed proposals stay closed; nothing re-raises a rejected or expired request. A closed lesson' + String.fromCharCode(39) + 's key stays open for different jobs. If Tee tapped a decision and it still shows EXPIRED here, the queue lost the decision after showing Recorded: check approval_queue decided_at before trusting either side.');
return [{ json: { subject: 'Soul Committer: ' + closed.length + ' proposal(s) closed without commit', body: lines.join(String.fromCharCode(10)) } }];