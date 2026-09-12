// Applies the Cerebras tags, or the structured fields, into the envelope.
// The model may be wrong or silent; the vocabularies are the authority.
// A missing Area refuses (a wrong tag is permanent and silent). A missing blast
// radius defaults to reversible_write, which routes the job to Tee: fail closed
// toward approval, never toward autonomy.
const AREAS = ['TQO', 'Podcast', 'NCO', 'ACX', 'Health', 'Money', 'Family', 'Learning', 'Systems'];
const BLAST = ['none', 'read', 'reversible_write', 'irreversible_write', 'destructive'];
const form = $('Form Job').first().json;
if (form.refused) { return [{ json: form }]; }
const d = JSON.parse(JSON.stringify(form.draft));
const notes = [];
let tags = null;
if (form.needs_tagging) {
  const res = $input.first().json || {};
  const code = res.statusCode;
  if (code !== 200) {
    notes.push('Cerebras unavailable (HTTP ' + String(code || 'no response') + ').');
  } else {
    const body = res.body || {};
    const choice = (body.choices && body.choices[0]) || {};
    const msg = choice.message || {};
    let txt = String(msg.content || msg.reasoning || '').trim();
    const f = txt.indexOf('```');
    if (f !== -1) { const parts = txt.split('```'); if (parts.length > 1) { txt = parts[1]; } if (txt.indexOf('json') === 0) { txt = txt.slice(4); } txt = txt.trim(); }
    try { tags = JSON.parse(txt); } catch (e) { tags = null; }
    if (!tags) { const a = txt.indexOf('{'); const z = txt.lastIndexOf('}'); if (a !== -1 && z > a) { try { tags = JSON.parse(txt.slice(a, z + 1)); } catch (e) { tags = null; } } }
    if (!tags) { notes.push('Cerebras returned unparseable output.'); }
  }
}
function pickArea(v) { const x = String(v || '').trim(); for (const a of AREAS) { if (a.toLowerCase() === x.toLowerCase()) { return a; } } return ''; }
function pickBlast(v) { const x = String(v || '').trim().toLowerCase(); return BLAST.indexOf(x) !== -1 ? x : ''; }
if (!d.summary) {
  const fromModel = tags ? String(tags.summary || '').trim() : '';
  d.summary = (fromModel || form.text).slice(0, 2000);
  if (fromModel) { notes.push('summary by cerebras'); } else { notes.push('summary is the capture text verbatim'); }
}
if (!d.area) {
  const got = tags ? pickArea(tags.area) : '';
  if (got) { d.area = got; notes.push('area by cerebras'); }
  else if (tags && String(tags.area || '').trim()) { notes.push('cerebras area ' + String(tags.area) + ' is not one of the nine, discarded'); }
}
if (!d.area) {
  return [{ json: { refused: true, reason: 'No Area could be established for this job. State one of ' + AREAS.join(', ') + ' and post again. Nothing was filed. Notes: ' + notes.join(' ') } }];
}
if (!d.blast_radius) {
  const got = tags ? pickBlast(tags.blast_radius) : '';
  if (got) { d.blast_radius = got; notes.push('blast radius by cerebras'); }
  else { d.blast_radius = 'reversible_write'; notes.push('blast radius unknown, defaulted to reversible_write so Tee decides'); }
}
if (d.level === null || d.level === undefined) {
  const got = tags ? Number(tags.level) : NaN;
  d.level = (Number.isInteger(got) && got >= 0 && got <= 4) ? got : 0;
  notes.push('level ' + d.level + (Number.isInteger(got) ? ' by cerebras' : ' by default, the router raises it by blast radius'));
}
// A render is never a note. Any EditForge job floors at reversible_write;
// a paid provider floors at irreversible_write, which the router turns into a
// card. The poster's or the model's label can raise the blast radius, never
// lower it below what the payload actually does.
if (d.payload && d.payload.editforge && typeof d.payload.editforge === 'object') {
  const paid = String(d.payload.editforge.provider || 'mock') !== 'mock';
  const floor = paid ? 'irreversible_write' : 'reversible_write';
  if (BLAST.indexOf(d.blast_radius) < BLAST.indexOf(floor)) {
    notes.push('blast radius raised from ' + d.blast_radius + ' to ' + floor + ' because the job renders' + (paid ? ' with paid provider ' + String(d.payload.editforge.provider) : ''));
    d.blast_radius = floor;
  }
}
// A row is never a note either (Build 17). Any Airtable row job floors at
// reversible_write, which raises a card; the poster's or the model's label can
// raise the radius, never lower it below what the payload does. It cannot raise
// it above reversible_write either: the driver binds airtable.row only at exactly
// that radius, and a wider label would card the job as a spine echo, be approved
// as one, and park at the router with the grant spent (critic, 2026-09-06). A row
// is a reversible write; a job that says otherwise is refused at the door.
if (d.payload && d.payload.airtable && typeof d.payload.airtable === 'object') {
  if (BLAST.indexOf(d.blast_radius) < BLAST.indexOf('reversible_write')) {
    notes.push('blast radius raised from ' + d.blast_radius + ' to reversible_write because the job writes an Airtable row');
    d.blast_radius = 'reversible_write';
  }
  if (BLAST.indexOf(d.blast_radius) > BLAST.indexOf('reversible_write')) {
    return [{ json: { refused: true, reason: 'An Airtable row job is a reversible write and this one is labelled ' + d.blast_radius + '. The row writer runs at reversible_write only, so the job would be carded as something else and never write. Post it as reversible_write or drop the airtable payload. Nothing was filed. Notes: ' + notes.join(' ') } }];
  }
}
const gated = d.blast_radius === 'irreversible_write' || d.blast_radius === 'destructive';
const envelope = {
  schema_version: '1.0.0',
  intent_id: d.intent_id,
  event_id: d.intent_id,
  parent_intent_id: null,
  idempotency_key: d.idempotency_key,
  created_at: d.created_at,
  updated_at: d.created_at,
  state: 'RECEIVED',
  state_reason: null,
  actor: d.actor,
  area: d.area,
  intent: { summary: d.summary, level: d.level, blast_radius: d.blast_radius, payload: d.payload },
  canon_refs: [],
  soul_refs: [],
  approval: { state: gated ? 'pending' : 'not_required' },
  execution: { state: 'not_started', attempts: 0, max_attempts: 3 },
  verification: { state: 'not_required', evidence: [], human_watched: false },
  artifacts: [],
  learning: { state: 'not_captured' },
  receipt: null,
  trace: []
};
return [{ json: { refused: false, dry_run: form.dry_run === true, envelope: envelope, origin: 'intake', notes: notes.join(' | ') } }];
