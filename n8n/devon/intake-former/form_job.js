// DEVON Intake Former, Build 14. Turns one capture into one v1 job envelope.
// Contract: SYS_DATA_job-envelope-schema_v1_2026-08-23.json, Drive 1mH0T1B5MK-qFT1W71ZoezPcrfgg7GPoj
// Accepts either a structured job or free text. Free text is tagged by Cerebras
// downstream, validated against the closed vocabularies, and NEVER trusted for
// anything the vocabularies do not allow. Fails closed: an unreadable job is
// refused with the reason, not filed with a guess.
const AREAS = ['TQO', 'Podcast', 'NCO', 'ACX', 'Health', 'Money', 'Family', 'Learning', 'Systems'];
const BLAST = ['none', 'read', 'reversible_write', 'irreversible_write', 'destructive'];
const ACTORS = ['tee', 'devon', 'meta_supreme', 'cerebras', 'automation', 'external'];
const KINDS = { 'gen-video': 1, voice: 1, avatar: 1 };
const B32 = '0123456789ABCDEFGHJKMNPQRSTVWXYZ';
function ulid() {
  let t = Date.now(); let time = '';
  for (let i = 0; i < 10; i++) { time = B32[t % 32] + time; t = Math.floor(t / 32); }
  let r = '';
  for (let i = 0; i < 16; i++) { r += B32[Math.floor(Math.random() * 32)]; }
  return time + r;
}
function s(v) { return String(v === undefined || v === null ? '' : v).trim(); }
function pickArea(v) { const x = s(v); for (const a of AREAS) { if (a.toLowerCase() === x.toLowerCase()) { return a; } } return ''; }
function pickBlast(v) { const x = s(v).toLowerCase(); return BLAST.indexOf(x) !== -1 ? x : ''; }
function refuse(msg) { return [{ json: { refused: true, reason: msg, needs_tagging: false } }]; }

const it = $input.first().json || {};
const b = (it.body && typeof it.body === 'object') ? it.body : it;
const text = s(b.text);
const summaryIn = s(b.summary).slice(0, 2000);
if (!text && !summaryIn) { return refuse('POST { text } for free text, or { summary, area, blast_radius, level } for a structured job. Nothing was filed.'); }

const actorIn = (b.actor && typeof b.actor === 'object') ? b.actor : {};
let actorType = s(actorIn.type || b.actor_type).toLowerCase();
if (ACTORS.indexOf(actorType) === -1) { actorType = 'external'; }
const actorSource = s(actorIn.source || b.source) || 'devon_intake_webhook';

const payloadIn = (b.payload && typeof b.payload === 'object') ? b.payload : {};
const payload = {};
if (payloadIn.editforge && typeof payloadIn.editforge === 'object') {
  const ef = payloadIn.editforge;
  const kind = s(ef.kind);
  if (!KINDS[kind]) { return refuse('payload.editforge.kind must be gen-video, voice or avatar. Nothing was filed.'); }
  if (!s(ef.prompt)) { return refuse('payload.editforge.prompt is required. Nothing was filed.'); }
  payload.editforge = { kind: kind, prompt: s(ef.prompt).slice(0, 4000), provider: s(ef.provider) || 'mock' };
  if (s(ef.label)) { payload.editforge.label = s(ef.label).slice(0, 120); }
  if (ef.options && typeof ef.options === 'object' && !Array.isArray(ef.options)) {
    // Options reach the provider verbatim, so they are bounded here: flat,
    // at most 12 keys, plain names, string, number or boolean values only.
    const o = {}; let n = 0;
    for (const k of Object.keys(ef.options)) {
      if (!/^[a-zA-Z][a-zA-Z0-9_]{0,40}$/.test(k)) { continue; }
      if (/provider|kind|prompt|model|token|key|secret|auth|url/i.test(k)) { continue; }
      const v = ef.options[k];
      if (typeof v === 'string') { o[k] = v.slice(0, 200); } else if (typeof v === 'number' || typeof v === 'boolean') { o[k] = v; } else { continue; }
      n++; if (n >= 12) { break; }
    }
    if (n) { payload.editforge.options = o; }
  }
}
if (payloadIn.auto_verify === true) { payload.auto_verify = true; }
if (s(payloadIn.note)) { payload.note = s(payloadIn.note).slice(0, 1000); }
// Build 17: a structural Airtable row request rides through as the poster declared
// it, bounded here for shape only. The Airtable Row Writer holds the table and
// field allowlist and refuses anything outside it; this node keeps a table name,
// a flat fields object of strings, lists of strings, numbers or booleans, at most
// 12 fields and 20000 characters per value. It never adds a field the poster did
// not name, so the approval card lists exactly what will be written.
if (payloadIn.airtable && typeof payloadIn.airtable === 'object' && !Array.isArray(payloadIn.airtable)) {
  const at = payloadIn.airtable;
  const table = s(at.table).slice(0, 80);
  if (!table) { return refuse('payload.airtable.table is required. Nothing was filed.'); }
  if (!at.fields || typeof at.fields !== 'object' || Array.isArray(at.fields)) { return refuse('payload.airtable.fields must be an object of field name to value. Nothing was filed.'); }
  const fields = {}; let n = 0;
  for (const k of Object.keys(at.fields)) {
    const key = String(k).trim().slice(0, 80);
    if (!key) { continue; }
    const v = at.fields[k];
    if (typeof v === 'string') { fields[key] = v.slice(0, 20000); }
    else if (Array.isArray(v) && v.every(function (x) { return typeof x === 'string'; })) { fields[key] = v.slice(0, 20).map(function (x) { return x.slice(0, 80); }); }
    else if (typeof v === 'number' || typeof v === 'boolean') { fields[key] = v; }
    else { return refuse('payload.airtable.fields.' + key + ' must be a string, a list of strings, a number or a boolean. Nothing was filed.'); }
    n++; if (n >= 12) { break; }
  }
  if (!n) { return refuse('payload.airtable.fields is empty. Nothing was filed.'); }
  payload.airtable = { table: table, fields: fields };
}

const area = pickArea(b.area);
const blast = pickBlast(b.blast_radius);
const levelIn = Number(b.level);
const level = Number.isInteger(levelIn) && levelIn >= 0 && levelIn <= 4 ? levelIn : null;
const needsTagging = !summaryIn || !area || !blast;

const id = ulid();
const now = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
const idem = s(b.idempotency_key) || ('intake-' + id);
if (idem.length < 8 || idem.length > 128) { return refuse('idempotency_key must be 8 to 128 characters. Nothing was filed.'); }

return [{ json: {
  refused: false,
  needs_tagging: needsTagging,
  dry_run: b.dry_run === true,
  text: text.slice(0, 6000),
  draft: {
    intent_id: id,
    idempotency_key: idem,
    summary: summaryIn,
    area: area,
    blast_radius: blast,
    level: level,
    actor: { type: actorType, source: actorSource, on_behalf_of: s(actorIn.on_behalf_of || b.on_behalf_of) || null },
    payload: payload,
    created_at: now
  }
} }];
