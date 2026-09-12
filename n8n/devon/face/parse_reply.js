// Parses the Cerebras answer. JSON is expected; anything else becomes the reply
// verbatim with action none, so a formatting slip never files a job.
const c = $('Compose Prompt').first().json || {};
const res = $input.first().json || {};
const code = res.statusCode;
let reply = '';
let action = 'none';
let job = null;
if (code !== 200) {
  reply = 'I could not reach my language lane (HTTP ' + String(code || 'no response') + '). The ledger still stands; ask again in a minute.';
} else {
  const body = res.body || {};
  const choice = (body.choices && body.choices[0]) || {};
  const msg = choice.message || {};
  let txt = String(msg.content || '').trim();
  if (txt.indexOf('```') !== -1) { const parts = txt.split('```'); if (parts.length > 1) { txt = parts[1]; } if (txt.indexOf('json') === 0) { txt = txt.slice(4); } txt = txt.trim(); }
  let parsed = null;
  try { parsed = JSON.parse(txt); } catch (e) { parsed = null; }
  if (!parsed) { const s = txt.indexOf('{'); const z = txt.lastIndexOf('}'); if (s !== -1 && z > s) { try { parsed = JSON.parse(txt.slice(s, z + 1)); } catch (e) { parsed = null; } } }
  if (parsed && typeof parsed === 'object' && typeof parsed.reply === 'string') {
    reply = parsed.reply.trim();
    const a = String(parsed.action || 'none').trim().toLowerCase();
    if ((a === 'file_job' || a === 'dry_run') && parsed.job && typeof parsed.job === 'object' && String(parsed.job.summary || '').trim()) {
      action = a;
      job = { summary: String(parsed.job.summary).trim().slice(0, 2000), area: String(parsed.job.area || '').trim(), blast_radius: String(parsed.job.blast_radius || '').trim().toLowerCase(), level: Number.isInteger(Number(parsed.job.level)) ? Number(parsed.job.level) : 2 };
      if (parsed.job.editforge && typeof parsed.job.editforge === 'object') { job.payload = { editforge: parsed.job.editforge }; }
      // Build 17: an Airtable row rides through as the model declared it, table and
      // fields only. The intake bounds the shape and the Airtable Row Writer holds
      // the table and field allowlist, so nothing here decides what is writable.
      const at = parsed.job.airtable;
      if (at && typeof at === 'object' && !Array.isArray(at) && typeof at.table === 'string' && at.fields && typeof at.fields === 'object' && !Array.isArray(at.fields)) {
        job.payload = Object.assign({}, job.payload || {}, { airtable: { table: at.table, fields: at.fields } });
      }
      // Accepting a proposal files the proposal Tee saw, not a re-derivation of it.
      const prop = c.last_proposal;
      const norm = v => String(v || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
      if (a === 'file_job' && prop && prop.summary && norm(prop.summary) === norm(job.summary)) { job = JSON.parse(JSON.stringify(prop)); }
      // A job filed from chat always passes Tee: level 2 is the floor and 4 the ceiling, whatever the model said.
      const lv = Number(job.level);
      job.level = Math.min(Math.max(Number.isInteger(lv) ? lv : 2, 2), 4);
    }
  } else {
    reply = txt || 'I have nothing to say to that.';
  }
}
reply = reply.split(String.fromCharCode(8212)).join(',').split(String.fromCharCode(8211)).join(',');
function hash(s) { let h = 2166136261; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619) >>> 0; } return h.toString(36); }
const jobKey = job ? ('face-' + String(c.session_id || 'nosession').slice(0, 40) + '-' + hash(String(job.summary || '').toLowerCase())) : '';
return [{ json: { session_id: c.session_id, chat_input: c.chat_input, reply: reply, action: action, job: job, job_key: jobKey } }];
