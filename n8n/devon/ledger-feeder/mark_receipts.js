// Reads the Event Bus answer for every LEARNING_CAPTURED post. The bus answers with
// its receipt (persisted true means the ledger took the same state update; false or
// absent means it did not), and a mark that did not persist is reported, never
// assumed. Nothing is retried here: the row still reads not_captured, so the next
// daily run marks it again.
const responses = $input.all();
const sources = $('Select Unmarked Jobs').all();
const marked = [];
const failed = [];
for (let i = 0; i < responses.length; i++) {
  const res = responses[i].json || {};
  const src = (sources[i] || {}).json || {};
  const code = res.statusCode;
  let body = res.body;
  if (typeof body === 'string') { try { body = JSON.parse(body); } catch (err) { body = { raw: body.slice(0, 200) }; } }
  const r = Array.isArray(body) ? (body[0] || {}) : ((body && typeof body === 'object') ? body : {});
  const ok = (code === 200 || code === 201) && r.persisted === true;
  const errText = res.error ? (typeof res.error === 'string' ? res.error : String(res.error.message || JSON.stringify(res.error))) : '';
  const said = String(r.ledger_said || r.outcome || (body && body.raw) || errText || '').replace(/[.\s]+$/, '').slice(0, 200);
  if (ok) { marked.push({ intent_id: src.intent_id || '', gate_decision: src.gate_decision || '', said: said }); }
  else { failed.push({ intent_id: src.intent_id || 'unknown', status: String(code || 'no response'), said: said }); }
}
const lines = ['BUILD 12 LEDGER FEEDER, learning marks ' + new Date().toISOString(), ''];
for (const m of marked) { lines.push('MARKED ' + m.intent_id + ' learning.state captured (gate ' + (m.gate_decision || 'none') + '; ' + m.said + ')'); }
for (const f of failed) { lines.push('NOT RECORDED ' + f.intent_id + ' (HTTP ' + f.status + '): ' + (f.said || 'no receipt') + '. The row still reads not_captured; the next daily run tries again.'); }
lines.push('');
lines.push('A mark mirrors the feed log onto the job envelope. It approves nothing and writes no soul.');
return [{ json: {
  marked_count: marked.length,
  failed_count: failed.length,
  subject: 'Build 12 feeder: ' + failed.length + ' learning mark(s) NOT recorded, ' + marked.length + ' marked',
  body: lines.join('\n'),
  marked: marked,
  failed: failed
} }];
