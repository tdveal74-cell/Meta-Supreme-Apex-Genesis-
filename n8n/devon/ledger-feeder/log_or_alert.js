// A success response is a claim, not a receipt: the status code is read back
// (neverError + fullResponse) rather than assumed. A failed POST is NOT logged
// as fed, so the next poll retries it.
const responses = $input.all();
const sources = $('Select Unfed Jobs').all();
const now = new Date().toISOString();
const logs = [];
const failures = [];
for (let i = 0; i < responses.length; i++) {
  const res = responses[i].json || {};
  const src = (sources[i] || {}).json || {};
  const code = res.statusCode;
  if (code === 200 || code === 201) {
    let decision = '';
    const b = res.body;
    if (b && typeof b === 'object') {
      decision = b.decision || b.gate_decision || (b.gate && b.gate.decision) || '';
    }
    logs.push({ intent_id: src.intent_id || '', fed_at: now, webhook_status: code, gate_decision: String(decision || ''), claim: src.claim || '' });
  } else {
    const detail = JSON.stringify(res.body || res.error || res).slice(0, 300);
    failures.push({ intent_id: src.intent_id || 'unknown', status: String(code || 'no response'), detail: detail });
  }
}
const subject = failures.length
  ? 'Build 12 feeder: ' + logs.length + ' fed, ' + failures.length + ' FAILED'
  : 'Build 12 feeder: ' + logs.length + ' job(s) fed to the learning gate';
const lines = ['BUILD 12 LEDGER FEEDER ' + now, ''];
for (const l of logs) {
  lines.push('FED ' + l.intent_id + ' (HTTP ' + l.webhook_status + (l.gate_decision ? ', gate ' + l.gate_decision : '') + ')');
  lines.push('  ' + l.claim);
}
for (const f of failures) {
  lines.push('FAILED ' + f.intent_id + ' (HTTP ' + f.status + '): ' + f.detail);
  lines.push('  Not logged as fed; it will be retried on the next poll.');
}
lines.push('');
lines.push('Feeding starts the learning gate; it approves nothing. The gate still rules PROMOTE or REQUIRES_HUMAN, and only PROMOTE writes.');
return [{ json: { subject: subject, body: lines.join('\n'), logs: logs, fed_count: logs.length, failed_count: failures.length } }];