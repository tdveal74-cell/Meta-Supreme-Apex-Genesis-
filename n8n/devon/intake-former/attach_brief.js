// Attaches the Cerebras brief to the envelope. The brief is advice: it feeds the
// approval card Tee reads and the runtime's plan. It never widens the job. A
// hold recommendation raises the level to at least 2 so the router sends the
// job to Tee (fail closed toward approval). A missing or unparseable brief
// never blocks a job; it is noted and the job proceeds without one.
const a = $('Apply Tags').first().json || {};
if (a.refused) { return [{ json: a }]; }
const out = JSON.parse(JSON.stringify(a));
const res = $input.first().json || {};
const notes = out.notes ? [out.notes] : [];
let brief = null;
if (res.statusCode === 200) {
  const body = res.body || {};
  const choice = (body.choices && body.choices[0]) || {};
  const msg = choice.message || {};
  let txt = String(msg.content || '').trim();
  if (txt.indexOf('```') !== -1) { const parts = txt.split('```'); if (parts.length > 1) { txt = parts[1]; } if (txt.indexOf('json') === 0) { txt = txt.slice(4); } txt = txt.trim(); }
  try { brief = JSON.parse(txt); } catch (e) { brief = null; }
  if (!brief) { const s = txt.indexOf('{'); const z = txt.lastIndexOf('}'); if (s !== -1 && z > s) { try { brief = JSON.parse(txt.slice(s, z + 1)); } catch (e) { brief = null; } } }
  if (!brief) { notes.push('brief unparseable, job proceeds without one'); }
} else {
  notes.push('brief unavailable (HTTP ' + String(res.statusCode || 'no response') + '), job proceeds without one');
}
function strs(v, max) { if (!Array.isArray(v)) { return []; } const r = []; for (const x of v) { const t = String(x === undefined || x === null ? '' : x).trim().slice(0, 200); if (t) { r.push(t); } if (r.length >= max) { break; } } return r; }
if (brief && typeof brief === 'object') {
  const rec = String(brief.recommendation || '').trim().toLowerCase() === 'proceed' ? 'proceed' : 'hold';
  const intent = out.envelope.intent;
  intent.payload = (intent.payload && typeof intent.payload === 'object') ? intent.payload : {};
  intent.payload.brief = {
    plan: strs(brief.plan, 5),
    done_when: strs(brief.done_when, 4),
    risks: strs(brief.risks, 3),
    recommendation: rec,
    reason: String(brief.reason || '').trim().slice(0, 300),
    by: 'cerebras gpt-oss-120b'
  };
  notes.push('brief by cerebras, recommends ' + rec);
  if (rec === 'hold' && Number(intent.level) < 2) { intent.level = 2; notes.push('level raised to 2 on hold, Tee decides'); }
}
out.notes = notes.join(' | ');
return [{ json: out }];
