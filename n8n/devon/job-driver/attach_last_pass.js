// Carries the last driver log row FOR THIS JOB into the pass, so Finish can tell a
// refusal that merely repeats from one that is news. The data table filter already
// asks for this intent, and the check below does not trust it: a row for another
// job would make Finish compare this pass against someone else's refusal.
const it = Object.assign({}, $('Load Job').first().json);
const id = (it.envelope && it.envelope.intent_id) ? String(it.envelope.intent_id) : '';
const rows = $input.all().map(function (i) { return i.json || {}; })
  .filter(function (r) { return r && id && String(r.intent_id || '') === id; });
function at(r) { const a = Date.parse(String(r.pass_at || '')); if (!Number.isNaN(a)) { return a; } const b = Date.parse(String(r.createdAt || '')); return Number.isNaN(b) ? 0 : b; }
let last = null;
for (const r of rows) { if (!last || at(r) > at(last)) { last = r; } }
it.last_pass = last ? { pass_at: String(last.pass_at || ''), outcome: String(last.outcome || ''), detail: String(last.detail || ''), execution_id: String(last.execution_id || '') } : null;
return [{ json: it }];
