// One email for every lesson refused this poll. A refusal means the feeder,
// the gate or the ledger disagrees with what the committer read, so it is
// news even though nothing was written. It goes out through Notify Propose
// Failures, the same channel as a card that failed to queue.
const rows = $input.all().map(function (i) { return i.json || {}; });
if (!rows.length) { return []; }
const NL = String.fromCharCode(10);
const lines = ['SOUL COMMITTER REFUSALS ' + new Date().toISOString(), ''];
for (const r of rows) {
  lines.push('REFUSED ' + r.intent_id + (r.lesson_key ? ' (lesson ' + r.lesson_key + ')' : '') + ': ' + r.note);
  lines.push('  ' + (r.claim || '(no claim)'));
}
lines.push('');
lines.push('No card was raised and nothing was written to devon-soul. Each refusal is closed for good in devon_soul_commit_log, and the member ids it lists can never back another lesson. If a refusal is wrong, fix the cause first; deleting its commit-log row on your ruling lets the next poll read it fresh.');
return [{ json: { subject: 'Soul Committer: ' + rows.length + ' lesson(s) refused before a card', body: lines.join(NL) } }];
