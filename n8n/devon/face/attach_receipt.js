// Appends the intake receipt to the reply so Tee sees where the job stopped.
const p = $('Parse Reply').first().json || {};
const res = $input.first().json || {};
const code = res.statusCode;
let body = res.body;
if (typeof body === 'string') { try { body = JSON.parse(body); } catch (e) { body = { reason: String(res.body).slice(0, 300) }; } }
body = (body && typeof body === 'object') ? body : {};
function why(b) { const r = String((b && b.reason) || '').trim().replace(/[.]+$/, ''); return r ? ': ' + r : ''; }
function planLine(b) { return 'Plan: ' + b.plan.map((s, i) => String(i + 1) + ') ' + String(s).trim().replace(/[.]+$/, '')).join('. ') + '.'; }
const lines = [];
if (code === 200 && body.filed === true) {
  lines.push('Filed job ' + body.intent_id + '. It stopped at ' + body.state + ' (' + String(body.outcome || '') + ').');
  if (body.approval_card) { lines.push('Approval card ' + body.approval_card + ' is in your inbox. Two taps to decide; no decision is a rejection after 72 hours.'); }
  if (body.verify_card) { lines.push('Verification card ' + body.verify_card + ' is in your inbox. Approve only after watching the output.'); }
  if (body.brief && Array.isArray(body.brief.plan) && body.brief.plan.length) { lines.push(planLine(body.brief)); lines.push('DEVON recommends ' + String(body.brief.recommendation) + why(body.brief) + '.'); }
} else if (code === 200 && body.dry_run === true && body.envelope) {
  const e = body.envelope; const it = e.intent || {}; const b = (it.payload && it.payload.brief) || null;
  lines.push('Dry run, nothing filed. I would file: ' + String(it.summary) + ' | area ' + String(e.area) + ' | level ' + String(it.level) + ' | blast radius ' + String(it.blast_radius) + '.');
  if (b && Array.isArray(b.plan) && b.plan.length) { lines.push(planLine(b)); if (Array.isArray(b.done_when) && b.done_when.length) { lines.push('Done when: ' + b.done_when.map(s => String(s).trim().replace(/[.]+$/, '')).join('; ') + '.'); } lines.push('I recommend ' + String(b.recommendation) + why(b) + '.'); }
  lines.push('Say file it and I will.');
} else if (code === 200 && body.duplicate === true) {
  lines.push('That job already exists: ' + String(body.intent_id) + ' (' + String(body.state) + '). Nothing new was filed.');
} else if (code === 400) {
  lines.push('The intake refused it: ' + String(body.reason || 'no reason given'));
} else {
  lines.push('The intake did not answer (HTTP ' + String(code || 'no response') + '). Nothing was filed.');
}
return [{ json: Object.assign({}, p, { reply: p.reply + '\n\n' + lines.join('\n'), intent_id: body.intent_id || '' }) }];
